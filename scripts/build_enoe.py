"""Build the ENOE parquet mirror from INEGI's bulk-download tree.

Maintainer-only — NOT part of the installed package.

ENOE (Encuesta Nacional de Ocupación y Empleo) is Mexico's quarterly labor-force
survey. Unlike the census/DENUE mirrors it is **national** — one CSV ZIP per quarter
(no per-state split) — and each ZIP bundles the **five tables** ``viv``/``hog``/``sdem``
/``coe1``/``coe2`` (see ``mxcensus.data._enoe_catalog`` and ``docs/enoe/STEP_0_probe.md``).

This script fetches each quarter's ZIP once, extracts the CSV member for each requested
table, reads it robustly (faithful raw, ``dtype=str``), and writes one parquet per
(table, quarter): ``enoe_{table}_{period}.parquet`` (e.g. ``enoe_sdem_2023t1.parquet``).
No geometry — ENOE has no coordinates — so conversion is a plain zstd ``to_parquet``.

Variable dictionaries, validation schemas and the registry append are added in later work
units (mirroring the ``build_denue.py`` machinery). Schema fingerprinting/grouping and the
inconsistency report are the ``--schema-map`` / ``--report-only`` modes below.

Dry run (preview one quarter's plan, no download):
    uv run python scripts/build_enoe.py --dry-run --periods 2023t1

Real build (one quarter, all five tables):
    uv run python scripts/build_enoe.py --periods 2023t1

Schema map + inconsistency report (from parquet already on disk, no download):
    uv run python scripts/build_enoe.py --schema-map     # → src/mxcensus/_yaml/enoe_schema_map.yaml
    uv run python scripts/build_enoe.py --report-only    # → docs/enoe/INCONSISTENCY_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

import _build_common as bc
from mxcensus.data._enoe_catalog import (
    CATALOG_VERIFIED_DATE,
    QUARTERS,
    QUARTERS_BY_PERIOD,
    TABLES,
    enoe_zip_entry,
    find_member,
    table_member_name,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_SCHEMA_MAP = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "enoe_schema_map.yaml"
_DEFAULT_REPORT = _REPO_ROOT / "docs" / "enoe" / "INCONSISTENCY_REPORT.md"


# --- CSV reading (copied verbatim from build_denue.py; see its docstrings) ------------
# ENOE CSVs share DENUE's encoding zoo (clean UTF-8, UTF-8 with rare bad bytes, and
# Windows single-byte), so the same sniff/read heuristic applies. Kept local rather than
# imported to keep this build independent of the DENUE loader's module-level imports.

def _sniff_encoding(csv_path: Path) -> str:
    """Choose the decoding that preserves the most of an INEGI CSV's accented text.

    Discriminator: in a real UTF-8 file the high bytes (≥0x80) form valid multi-byte
    sequences, so utf-8/replace inserts almost no U+FFFD; in a single-byte file nearly
    every high byte is invalid as UTF-8, so replacements ≈ high-byte count. Returns one of
    ``"utf-8"`` (read strict) / ``"utf-8/replace"`` / ``"cp1252"`` / ``"latin-1"``.
    """
    raw = csv_path.read_bytes()
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    n_high = sum(b >= 0x80 for b in raw)
    n_rep = raw.decode("utf-8", errors="replace").count("�")
    if n_high and n_rep / n_high < 0.5:   # mostly-valid UTF-8 with rare bad bytes
        return "utf-8/replace"
    try:
        raw.decode("cp1252")              # Windows single-byte
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"                  # has bytes undefined in cp1252 (e.g. 0x90)


def _read_csv_robust(csv_path: Path) -> tuple[pd.DataFrame, str]:
    """Read an INEGI CSV with the encoding chosen by ``_sniff_encoding``.

    ``dtype=str``: read every field as text (faithful, and avoids mixed str/float object
    columns pyarrow can't serialise). Numeric analysis (weights, coordinates) re-parses
    downstream.
    """
    enc = _sniff_encoding(csv_path)
    read_enc, errors = (enc.split("/") + ["strict"])[:2]
    df = pd.read_csv(csv_path, encoding=read_enc, encoding_errors=errors,
                     dtype=str, low_memory=False)
    return df, enc


# --- conversion -----------------------------------------------------------------------

def _df_to_parquet(df: pd.DataFrame, parquet_path: Path) -> dict:
    """Write a faithful-raw ENOE DataFrame to zstd parquet; return diagnostics.

    Under ``dtype=str`` an empty cell reads as float NaN, so an object column can mix str
    with NaN — which pyarrow may refuse to serialise. Replace NaN with None so each stays
    a clean string column (missing values become nulls). No values are otherwise altered.
    """
    for col in df.columns[df.dtypes == object]:
        df[col] = df[col].where(df[col].notna(), None)
    df.to_parquet(parquet_path, compression="zstd")
    return {
        "rows": len(df),
        "cols": df.shape[1],
        "size_kb": parquet_path.stat().st_size // 1024,
    }


def _build_quarter(
    quarter, tables, raw_dir: Path, cache_dir: Path, out_dir: Path,
    retries: int, cleanup_raw: bool = True,
) -> list[dict]:
    """Download+verify a quarter's CSV ZIP once, convert each requested table to parquet.

    Returns one info dict per requested table. A table absent from the ZIP is reported
    with ``status="missing"`` and no file written; the ZIP is fetched only once per
    quarter regardless of how many tables are requested.
    """
    entry = enoe_zip_entry(quarter)
    # ZIP basenames are globally unique across regimes/quarters (e.g. 2019trim1_csv.zip,
    # enoe_n_2021_trim3_csv.zip, enoe_2023_trim1_csv.zip), so the basename is a safe cache key.
    zip_path = bc.fetch_zip_verified(entry.url, cache_dir, quarter.zip_filename, retries)
    extract_dir = raw_dir / entry.extract_dir
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        zf.extractall(extract_dir)

    infos: list[dict] = []
    for table in tables:
        member = find_member(names, quarter, table)
        if member is None:
            infos.append({"table": table, "period": quarter.period, "status": "missing",
                          "member": table_member_name(quarter, table)})
            continue
        df, enc = _read_csv_robust(extract_dir / member)
        out_path = out_dir / f"enoe_{table}_{quarter.period}.parquet"
        info = _df_to_parquet(df, out_path)
        info.update({"table": table, "period": quarter.period, "member": member,
                     "encoding": enc, "file": out_path.name, "status": "ok"})
        infos.append(info)

    if cleanup_raw:  # bound disk use: drop extracted CSVs once converted
        shutil.rmtree(extract_dir, ignore_errors=True)
    return infos


# --- schema fingerprinting + report (per table; the 5 tables drift independently) ----

def _fingerprint_cols(cols) -> str:
    """sha256 over the ordered column names — identifies a table's schema for a period.

    Column names (not dtypes) define the ENOE schema: dtypes are uniform (``dtype=str``),
    whereas the column set/order is the era-drift signal. Same recipe as the loader's
    ``mxcensus.enoe._fingerprint`` will use, so a mirrored file matches its map entry.
    """
    return sha256(json.dumps(list(cols)).encode()).hexdigest()


def _period_key(period: str) -> tuple[int, int]:
    """Sort key ``(year, quarter)`` for a ``"2023t1"``-style period id."""
    year, quarter = period.split("t")
    return int(year), int(quarter)


def _scan_enoe_parquet(path: Path) -> dict:
    """Read one mirrored ENOE parquet's schema/metadata for the map/report (no full load)."""
    _, table, period = path.stem.split("_")  # enoe_{table}_{period}
    pf = pq.ParquetFile(path)
    cols = list(pf.schema_arrow.names)  # ENOE has no geometry column
    return {
        "table": table,
        "period": period,
        "columns": cols,
        "fingerprint": _fingerprint_cols(cols),
        "rows": pf.metadata.num_rows,
        "size_kb": path.stat().st_size // 1024,
    }


def _group_schemas(records: list[dict]) -> dict:
    """Assign stable per-table schema groups (g01.. in period order) from scan records.

    Returns ``{table: {"latest", "fingerprints", "groups"}}`` — the shape written to
    ``enoe_schema_map.yaml``, namespaced by table since the five tables have independent
    schema histories. Group ids restart at g01 within each table; ``latest`` is the group
    of that table's most recent period.
    """
    doc: dict[str, dict] = {}
    for table in TABLES:
        recs = [r for r in records if r["table"] == table]
        if not recs:
            continue
        fp_to_id: dict[str, str] = {}
        fp_cols: dict[str, list] = {}
        for r in sorted(recs, key=lambda r: _period_key(r["period"])):
            if r["fingerprint"] not in fp_to_id:
                fp_to_id[r["fingerprint"]] = f"g{len(fp_to_id) + 1:02d}"
                fp_cols[r["fingerprint"]] = r["columns"]
        files_per_fp: dict[str, int] = defaultdict(int)
        periods_per_fp: dict[str, list] = defaultdict(list)
        for r in recs:
            files_per_fp[r["fingerprint"]] += 1
            periods_per_fp[r["fingerprint"]].append(r["period"])
        latest = max(recs, key=lambda r: _period_key(r["period"]))
        groups = {
            fp_to_id[fp]: {
                "n_columns": len(fp_cols[fp]),
                "files": files_per_fp[fp],
                "periods": sorted(periods_per_fp[fp], key=_period_key),
                "columns": fp_cols[fp],
            }
            for fp in fp_to_id
        }
        doc[table] = {
            "latest": fp_to_id[latest["fingerprint"]],
            "fingerprints": dict(fp_to_id),
            "groups": dict(sorted(groups.items())),
        }
    return doc


def _write_schema_map(out_dir: Path, map_path: Path) -> dict:
    """Group every mirrored ENOE file by its exact schema and write enoe_schema_map.yaml.

    Namespaced per table (top-level keys ``sdem``/``coe1``/…); each table gets its own
    ``latest``/``fingerprints``/``groups`` (see :func:`_group_schemas`). The loader matches
    a file by recomputing the same fingerprint, so no per-file table is stored.
    """
    records = [_scan_enoe_parquet(p) for p in sorted(out_dir.glob("enoe_*.parquet"))]
    doc = _group_schemas(records)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return doc


def _write_report(out_dir: Path, report_path: Path) -> dict:
    """Scan every mirrored ENOE parquet and (re)write the schema inconsistency report.

    Per table: an inventory (period → group), the distinct schema groups (columns),
    period-to-period schema drift (added/removed columns), and the catalog quarters still
    missing from the mirror. Returns the per-table group doc (same as the schema map).
    """
    records = [_scan_enoe_parquet(p) for p in sorted(out_dir.glob("enoe_*.parquet"))]
    doc = _group_schemas(records)
    present_periods = sorted({r["period"] for r in records}, key=_period_key)

    L = ["# ENOE inconsistency report", "",
         f"Generated by `scripts/build_enoe.py` (catalog verified {CATALOG_VERIFIED_DATE}).",
         f"Tables mirrored: {sorted(doc)}. Periods on disk: {len(present_periods)} "
         f"({present_periods[0] if present_periods else '—'}"
         f"…{present_periods[-1] if present_periods else '—'}).", "",
         "Schema groups are assigned **per table** (the five tables drift independently); "
         "group ids restart at `g01` within each table. See also `STEP_*.md` for the era "
         "narrative and `docs/enoe/STEP_0_probe.md` for the download layout.", ""]

    for table in TABLES:
        if table not in doc:
            continue
        recs = {r["period"]: r for r in records if r["table"] == table}
        fps = doc[table]["fingerprints"]
        periods = sorted(recs, key=_period_key)
        L += [f"## {table}", "",
              f"Groups: {len(doc[table]['groups'])}. Latest: `{doc[table]['latest']}`. "
              f"Periods: {len(periods)}.", "",
              "| period | group | cols | rows |", "|---|---|---|---|"]
        for p in periods:
            r = recs[p]
            L.append(f"| {p} | {fps[r['fingerprint']]} | {len(r['columns'])} | "
                     f"{r['rows']:,} |")
        L.append("")
        L.append("### Schema groups")
        for gid, g in doc[table]["groups"].items():
            L.append(f"- **{gid}** — {g['n_columns']} cols, {g['files']} file(s), "
                     f"periods {g['periods']}")
        L.append("")
        # Period-to-period drift (added/removed columns between consecutive periods).
        drift = []
        for prev, cur in zip(periods, periods[1:]):
            a = set(recs[prev]["columns"])
            b = set(recs[cur]["columns"])
            added, removed = sorted(b - a), sorted(a - b)
            if added or removed:
                drift.append(f"- **{prev} → {cur}**: "
                             + (f"added {added}" if added else "")
                             + ("; " if added and removed else "")
                             + (f"removed {removed}" if removed else ""))
        if drift:
            L.append("### Schema drift (consecutive periods on disk)")
            L += drift
            L.append("")

    # Missing quarters: catalog vs on-disk, per table.
    L += ["## Missing quarters (catalog vs mirror)", ""]
    on_disk = {(r["table"], r["period"]) for r in records}
    any_missing = False
    for table in TABLES:
        missing = [q.period for q in QUARTERS if (table, q.period) not in on_disk]
        if missing:
            any_missing = True
            L.append(f"- **{table}**: {len(missing)} missing "
                     f"({missing[0]}…{missing[-1]})")
    if not any_missing:
        L.append("None — every catalog quarter present for every table.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--periods", nargs="+", default=list(QUARTERS_BY_PERIOD),
                        metavar="YYYYtQ", help="Quarter ids (default: all, e.g. 2023t1)")
    parser.add_argument("--tables", nargs="+", default=list(TABLES), metavar="TABLE",
                        help=f"Tables to convert (default: all {list(TABLES)})")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR")
    parser.add_argument("--retries", type=int, default=2, metavar="N")
    parser.add_argument("--keep-raw", dest="cleanup_raw", action="store_false",
                        help="Keep extracted CSVs (default: delete after conversion)")
    parser.add_argument("--schema-map", action="store_true",
                        help="Skip downloading; (re)write enoe_schema_map.yaml from parquet on disk")
    parser.add_argument("--schema-map-path", type=Path, default=_DEFAULT_SCHEMA_MAP,
                        metavar="FILE")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip downloading; (re)write the inconsistency report from parquet on disk")
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT, metavar="FILE")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the planned (quarter, table) → file plan; no download")
    parser.set_defaults(cleanup_raw=True)
    args = parser.parse_args()

    unknown_p = [p for p in args.periods if p not in QUARTERS_BY_PERIOD]
    if unknown_p:
        parser.error(f"unknown periods {unknown_p}; known: {list(QUARTERS_BY_PERIOD)}")
    unknown_t = [t for t in args.tables if t not in TABLES]
    if unknown_t:
        parser.error(f"unknown tables {unknown_t}; known: {list(TABLES)}")

    args.output.mkdir(parents=True, exist_ok=True)

    if args.schema_map:
        doc = _write_schema_map(args.output, args.schema_map_path)
        ng = sum(len(t["groups"]) for t in doc.values())
        print(f"Schema map → {args.schema_map_path}  "
              f"({len(doc)} table(s), {ng} group(s) total)")
        return

    if args.report_only:
        doc = _write_report(args.output, args.report)
        print(f"Report → {args.report}  ({len(doc)} table(s))")
        return

    quarters = [QUARTERS_BY_PERIOD[p] for p in args.periods]

    if args.dry_run:
        print(f"[dry-run] {len(quarters)} quarter(s) × {len(args.tables)} table(s):")
        for q in quarters:
            print(f"  {q.period} ({q.regime}) ← {q.url}")
            for table in args.tables:
                print(f"      {table}: {table_member_name(q, table)} "
                      f"→ enoe_{table}_{q.period}.parquet")
        return

    print(f"Catalog verified {CATALOG_VERIFIED_DATE}; "
          f"{len(quarters)} quarter(s) × {len(args.tables)} table(s)")
    failed = 0
    for q in quarters:
        try:
            infos = _build_quarter(q, args.tables, args.raw_dir, args.cache_dir,
                                   args.output, args.retries, args.cleanup_raw)
        except Exception as exc:  # malformed/unavailable: report, don't abort the sweep
            failed += 1
            print(f"  ! {q.period}: MALFORMED — {type(exc).__name__}: {exc}")
            continue
        for info in infos:
            if info["status"] == "missing":
                failed += 1
                print(f"  ! {q.period}/{info['table']}: MISSING member "
                      f"{info['member']} in ZIP")
            else:
                print(f"  {q.period}/{info['table']}: {info['rows']:,} rows, "
                      f"{info['cols']} cols, enc={info['encoding']}, "
                      f"{info['size_kb'] / 1024:.1f} MB")

    print(f"\nDone: {len(quarters)} quarter(s); {failed} table(s) failed/missing.")


if __name__ == "__main__":
    main()
