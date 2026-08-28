"""Build the ENIGH parquet mirror from INEGI's bulk-download tree.

Maintainer-only — NOT part of the installed package.

ENIGH (Encuesta Nacional de Ingresos y Gastos de los Hogares) is Mexico's biennial
household income/expenditure survey. It is **national** and, unlike ENOE, each table ships
as its **own** CSV ZIP (see ``mxcensus.data._enigh_catalog`` and
``docs/enigh/STEP_0_probe.md``). Two regimes: the nueva serie (``ns``, 2016–2024, 11 tables)
and INEGI's conciliated Nueva Construcción de Variables (``ncv``, 2008–2014, 10–12 tables).

This script fetches each (edition, table) ZIP, reads the single CSV member robustly
(faithful raw, ``dtype=str``), and writes ``enigh_{table}_{period}.parquet``
(e.g. ``enigh_concentradohogar_2022.parquet``). No geometry; plain zstd ``to_parquet``.

Schema fingerprinting/grouping, the inconsistency report, the variable dictionaries, the
per-file validation sweep and the registry append are the ``--schema-map`` / ``--report-only``
/ ``--variables`` / ``--validate`` / ``--update-registry`` modes below. See
``docs/enigh/HANDOFF.md`` for the full-mirror build + upload runbook.

Dry run (preview one edition's plan, no download):
    uv run python scripts/build_enigh.py --dry-run --periods 2022

Real build (one edition, all its tables):
    uv run python scripts/build_enigh.py --periods 2022

Metadata modes (from parquet already on disk, no download):
    uv run python scripts/build_enigh.py --schema-map      # → src/mxcensus/_yaml/enigh_schema_map.yaml
    uv run python scripts/build_enigh.py --report-only     # → docs/enigh/INCONSISTENCY_REPORT.md
    uv run python scripts/build_enigh.py --variables       # → src/mxcensus/_yaml/variables_enigh_{table}_{gNN}.yaml
    uv run python scripts/build_enigh.py --validate        # → docs/enigh/VALIDATION_REPORT.md
    uv run python scripts/build_enigh.py --update-registry # → append enigh_* hashes to registry.txt
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

import _build_common as bc
from mxcensus._schema_groups import fingerprint
from mxcensus.data._enigh_catalog import (
    CATALOG_VERIFIED_DATE,
    EDITIONS,
    EDITIONS_BY_PERIOD,
    TABLES,
    enigh_zip_entry,
    find_member,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_SCHEMA_MAP = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "enigh_schema_map.yaml"
_DEFAULT_REPORT = _REPO_ROOT / "docs" / "enigh" / "INCONSISTENCY_REPORT.md"
_DEFAULT_YAML_DIR = _DEFAULT_SCHEMA_MAP.parent
_CORE_PATH = _DEFAULT_YAML_DIR / "variables_enigh_core.yaml"
_DEFAULT_VALIDATE_REPORT = _REPO_ROOT / "docs" / "enigh" / "VALIDATION_REPORT.md"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"

# enigh_{table}_{period}.parquet — table names may themselves contain underscores in the
# future, so parse from the right rather than splitting on "_" (an ENOE-build gotcha).
_FILE_RE = re.compile(r"^enigh_(?P<table>.+)_(?P<period>\d{4})$")


# --- CSV reading (same heuristic as build_denue.py / build_enoe.py) --------------------

def _sniff_encoding(csv_path: Path) -> str:
    """Choose the decoding that preserves the most of an INEGI CSV's accented text.

    Discriminator: in a real UTF-8 file the high bytes (≥0x80) form valid multi-byte
    sequences, so utf-8/replace inserts almost no U+FFFD; in a single-byte file nearly
    every high byte is invalid as UTF-8, so replacements ≈ high-byte count. Returns one of
    ``utf-8`` (clean), ``utf-8/replace`` (UTF-8 with a few bad bytes), ``cp1252``/``latin-1``.
    """
    raw = csv_path.read_bytes()
    high = sum(1 for b in raw if b >= 0x80)
    if high == 0:
        return "utf-8"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    bad = raw.decode("utf-8", errors="replace").count("�")
    if bad < 0.1 * high:
        return "utf-8/replace"
    try:
        raw.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"


def _read_csv_robust(csv_path: Path) -> tuple[pd.DataFrame, str]:
    """Read an INEGI CSV faithfully (every column ``str``) with the sniffed encoding."""
    enc = _sniff_encoding(csv_path)
    kwargs = {"dtype": str, "low_memory": False}
    if enc == "utf-8/replace":
        df = pd.read_csv(csv_path, encoding="utf-8", encoding_errors="replace", **kwargs)
    else:
        df = pd.read_csv(csv_path, encoding=enc, **kwargs)
    return df, enc


def _df_to_parquet(df: pd.DataFrame, parquet_path: Path) -> dict:
    """Write a faithful-raw DataFrame to zstd parquet; return diagnostics.

    Under ``dtype=str`` an empty cell reads as float NaN, so an object column can mix str
    with NaN — replace NaN with None so each stays a clean string column (missing values
    become nulls). No values are otherwise altered.
    """
    for col in df.columns[df.dtypes == object]:
        df[col] = df[col].where(df[col].notna(), None)
    df.to_parquet(parquet_path, compression="zstd")
    return {
        "rows": len(df),
        "cols": df.shape[1],
        "size_kb": parquet_path.stat().st_size // 1024,
    }


def _build_edition(
    edition, tables, raw_dir: Path, cache_dir: Path, out_dir: Path,
    retries: int, cleanup_raw: bool = True,
) -> list[dict]:
    """Download+verify each requested table's ZIP for one edition and convert it.

    One ZIP per table (the structural difference from ENOE). A table INEGI does not publish
    for this edition is reported ``status="absent"`` (not an error); a download/ZIP failure
    is reported ``status="malformed"`` and the sweep continues with the next table.
    """
    infos: list[dict] = []
    for table in tables:
        if table not in edition.tables:
            infos.append({"table": table, "period": edition.period, "status": "absent"})
            continue
        entry = enigh_zip_entry(edition, table)
        try:
            zip_path = bc.fetch_zip_verified(entry.url, cache_dir, edition.zip_filename(table),
                                             retries)
        except Exception as exc:  # soft-404 / truncated / network
            infos.append({"table": table, "period": edition.period, "status": "malformed",
                          "error": f"{type(exc).__name__}: {exc}"})
            continue
        extract_dir = raw_dir / entry.extract_dir
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            zf.extractall(extract_dir)
        member = find_member(names, edition, table)
        if member is None:
            infos.append({"table": table, "period": edition.period, "status": "missing",
                          "member": names})
        else:
            df, enc = _read_csv_robust(extract_dir / member)
            out_path = out_dir / f"enigh_{table}_{edition.period}.parquet"
            info = _df_to_parquet(df, out_path)
            info.update({"table": table, "period": edition.period, "member": member,
                         "encoding": enc, "file": out_path.name, "status": "ok"})
            infos.append(info)
        if cleanup_raw:
            shutil.rmtree(extract_dir, ignore_errors=True)
    return infos


# --- schema fingerprinting + report (per table; tables drift independently) -----------

def _fingerprint_cols(cols) -> str:
    """Schema-group fingerprint — the shared recipe the loader resolves against
    (``mxcensus._schema_groups.fingerprint``), so map and loader can never drift."""
    return fingerprint(cols)


def _period_key(period: str) -> int:
    return int(period)


def _parse_name(path: Path) -> tuple[str, str]:
    m = _FILE_RE.match(path.stem)
    if m is None:
        raise ValueError(f"not an ENIGH mirror file: {path.name}")
    return m["table"], m["period"]


def _scan_parquet(path: Path) -> dict:
    """Read one mirrored parquet's schema/metadata for the map/report (no full load)."""
    table, period = _parse_name(path)
    pf = pq.ParquetFile(path)
    cols = list(pf.schema_arrow.names)
    return {
        "table": table,
        "period": period,
        "columns": cols,
        "fingerprint": _fingerprint_cols(cols),
        "rows": pf.metadata.num_rows,
        "size_kb": path.stat().st_size // 1024,
    }


def _mirror_files(out_dir: Path) -> list[Path]:
    return sorted(p for p in out_dir.glob("enigh_*.parquet") if _FILE_RE.match(p.stem))


def _group_schemas(records: list[dict]) -> dict:
    """Assign stable per-table schema groups (g01.. in edition order) from scan records.

    Returns ``{table: {"latest", "fingerprints", "groups"}}`` — the shape written to
    ``enigh_schema_map.yaml``. Group ids restart at g01 within each table and are assigned
    chronologically, so adding a newer edition can only add or join a group.
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
    """Group every mirrored ENIGH file by its exact schema and write enigh_schema_map.yaml."""
    records = [_scan_parquet(p) for p in _mirror_files(out_dir)]
    doc = _group_schemas(records)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return doc


def _write_report(out_dir: Path, report_path: Path) -> dict:
    """Scan every mirrored ENIGH parquet and (re)write the schema inconsistency report.

    Per table: an inventory (edition → group), the distinct schema groups, edition-to-
    edition drift (added/removed columns — the 2014→2016 series break and the 2022→2024
    questionnaire update show up here), and the catalog (edition, table) pairs still missing.
    """
    records = [_scan_parquet(p) for p in _mirror_files(out_dir)]
    doc = _group_schemas(records)
    present = sorted({r["period"] for r in records}, key=_period_key)

    L = ["# ENIGH inconsistency report", "",
         f"Generated by `scripts/build_enigh.py` (catalog verified {CATALOG_VERIFIED_DATE}).",
         f"Tables mirrored: {sorted(doc)}. Editions on disk: {present}.", "",
         "Schema groups are assigned **per table** (tables drift independently); group ids "
         "restart at `g01` within each table. The 2014 → 2016 transition is the nueva-serie "
         "break (see `STEP_0_probe.md`); 2022 → 2024 is the questionnaire/classifier update.", ""]

    for table in TABLES:
        if table not in doc:
            continue
        recs = {r["period"]: r for r in records if r["table"] == table}
        fps = doc[table]["fingerprints"]
        periods = sorted(recs, key=_period_key)
        L += [f"## {table}", "",
              f"Groups: {len(doc[table]['groups'])}. Latest: `{doc[table]['latest']}`. "
              f"Editions: {len(periods)}.", "",
              "| edition | group | cols | rows |", "|---|---|---|---|"]
        for p in periods:
            r = recs[p]
            L.append(f"| {p} | {fps[r['fingerprint']]} | {len(r['columns'])} | {r['rows']:,} |")
        L.append("")
        L.append("### Schema groups")
        for gid, g in doc[table]["groups"].items():
            L.append(f"- **{gid}** — {g['n_columns']} cols, {g['files']} file(s), "
                     f"editions {g['periods']}")
        L.append("")
        drift = []
        for prev, cur in zip(periods, periods[1:]):
            a, b = set(recs[prev]["columns"]), set(recs[cur]["columns"])
            added, removed = sorted(b - a), sorted(a - b)
            if added or removed:
                drift.append(f"- **{prev} → {cur}**: "
                             + (f"added {added}" if added else "")
                             + ("; " if added and removed else "")
                             + (f"removed {removed}" if removed else ""))
        if drift:
            L.append("### Schema drift (consecutive editions on disk)")
            L += drift
            L.append("")

    L += ["## Missing (catalog vs mirror)", ""]
    on_disk = {(r["table"], r["period"]) for r in records}
    missing = [(e.period, t) for e in EDITIONS for t in e.tables if (t, e.period) not in on_disk]
    if missing:
        for p, t in missing:
            L.append(f"- {p}/{t}")
    else:
        L.append("None — every catalog (edition, table) present.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return doc


# --- variable dictionaries (data-derived categories + hand-curated core) ---------------

def _code_sort_key(v: str):
    s = v.lstrip("-")
    return (0, int(v)) if s.isdigit() else (1, v)


def _build_categories(paths: list[Path], threshold: int) -> dict:
    """`{column: {value: value}}` for a group — distinct values enumerated across its files.

    Columns with more than ``threshold`` distinct values (ids, amounts, free text) are
    dropped. Data is the only source: ENIGH ZIPs bundle no dictionary.
    """
    if not paths:
        return {}
    cols = list(pq.ParquetFile(paths[0]).schema_arrow.names)
    seen: dict[str, set | None] = {c: set() for c in cols}
    alive = set(cols)
    for p in paths:
        present = [c for c in alive if c in pq.ParquetFile(p).schema_arrow.names]
        df = pd.read_parquet(p, columns=present)
        for c in present:
            seen[c].update(str(v) for v in df[c].dropna().unique())
            if len(seen[c]) > threshold:
                alive.discard(c)
                seen[c] = None
    return {c: {v: v for v in sorted(seen[c], key=_code_sort_key)}
            for c in cols if seen[c] is not None}


def _write_variables_yaml(out_dir: Path, map_path: Path, yaml_dir: Path,
                          threshold: int = 64) -> int:
    """Write one variables_enigh_{table}_{gNN}.yaml per (table, schema group).

    Categorías are data-derived; Descripción/Tipo/Longitud and the *complete* labelled
    value-sets come from the hand-curated ``variables_enigh_core.yaml`` for the analytical-
    core variables (read, never written here). Returns the number of files written.
    """
    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    core = yaml.safe_load(_CORE_PATH.read_text(encoding="utf-8")) if _CORE_PATH.exists() else {}
    yaml_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for table, td in schema_map.items():
        for gid, g in td["groups"].items():
            paths = [out_dir / f"enigh_{table}_{p}.parquet" for p in g["periods"]]
            paths = [p for p in paths if p.exists()]
            cats = _build_categories(paths, threshold)
            doc = {}
            for col in g["columns"]:
                if col in core:
                    m = core[col]
                    doc[col] = {
                        "Descripción": m.get("Descripción", ""),
                        "Tipo": m.get("Tipo", ""),
                        "Longitud": m.get("Longitud", ""),
                        "Categorías": m.get("Categorías", {}) or {},
                    }
                else:
                    doc[col] = {"Descripción": "", "Tipo": "", "Longitud": "",
                                "Categorías": cats.get(col, {})}
            path = yaml_dir / f"variables_enigh_{table}_{gid}.yaml"
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True,
                               default_flow_style=False)
            n += 1
    return n


# --- validation sweep (per-file, hard pass/fail; the loader only warns) ----------------

def _write_validation_report(out_dir: Path, map_path: Path,
                             report_path: Path) -> tuple[int, int]:
    """Validate every mirrored ENIGH parquet against its (table, group) tight schema."""
    import pandera.pandas as pa
    from mxcensus.enigh import _fingerprint, _group_schema

    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    files = _mirror_files(out_dir)
    results = []
    for p in files:
        table, period = _parse_name(p)
        cols = list(pq.ParquetFile(p).schema_arrow.names)
        gid = schema_map.get(table, {}).get("fingerprints", {}).get(_fingerprint(cols))
        if gid is None:
            results.append((p.name, table, "?", "UNKNOWN-SCHEMA", []))
            continue
        df = pd.read_parquet(p)
        try:
            _group_schema(table, gid).validate(df, lazy=True)
            results.append((p.name, table, gid, "PASS", []))
        except pa.errors.SchemaErrors as exc:
            fc = exc.failure_cases
            grp = (fc.groupby(["column", "check"])
                     .agg(count=("failure_case", "size"),
                          example=("failure_case", "first"))
                     .reset_index().sort_values("count", ascending=False))
            results.append((p.name, table, gid, "FAIL", grp.to_dict("records")))

    failed = [r for r in results if r[3] != "PASS"]
    L = ["# ENIGH validation report", "",
         f"Each mirrored file validated against its (table, group) tight schema "
         f"(`mxcensus.enigh._group_schema`). Files: {len(files)}. Failing: {len(failed)}.", ""]
    if not failed:
        L.append("All files pass their group schema.")
    for name, table, gid, status, fails in failed:
        L.append(f"## {name} ({table}/{gid}) — {status}")
        for f in fails:
            L.append(f"- `{f['column']}` / {f['check']}: {f['count']} row(s), "
                     f"e.g. `{f['example']}`")
        L.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return len(files), len(failed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--periods", nargs="+", default=list(EDITIONS_BY_PERIOD),
                        metavar="YYYY", help="Edition years (default: all, e.g. 2022)")
    parser.add_argument("--tables", nargs="+", default=list(TABLES), metavar="TABLE",
                        help=f"Tables to convert (default: all published per edition; known {list(TABLES)})")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR")
    parser.add_argument("--retries", type=int, default=2, metavar="N")
    parser.add_argument("--keep-raw", dest="cleanup_raw", action="store_false",
                        help="Keep extracted CSVs (default: delete after conversion)")
    parser.add_argument("--schema-map", action="store_true",
                        help="Skip downloading; (re)write enigh_schema_map.yaml from parquet on disk")
    parser.add_argument("--schema-map-path", type=Path, default=_DEFAULT_SCHEMA_MAP,
                        metavar="FILE")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip downloading; (re)write the inconsistency report from parquet on disk")
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT, metavar="FILE")
    parser.add_argument("--variables", action="store_true",
                        help="Skip downloading; write per-group variables_enigh_{table}_{gNN}.yaml")
    parser.add_argument("--cat-threshold", type=int, default=64, metavar="N",
                        help="Max distinct values for a column to be enumerated as a category")
    parser.add_argument("--yaml-dir", type=Path, default=_DEFAULT_YAML_DIR, metavar="DIR")
    parser.add_argument("--validate", action="store_true",
                        help="Skip downloading; validate every parquet against its group schema")
    parser.add_argument("--validate-report", type=Path, default=_DEFAULT_VALIDATE_REPORT,
                        metavar="FILE")
    parser.add_argument("--update-registry", action="store_true",
                        help="Skip downloading; append enigh_* hashes to registry.txt (preserving prior)")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the planned (edition, table) → file plan; no download")
    parser.set_defaults(cleanup_raw=True)
    args = parser.parse_args()

    unknown_p = [p for p in args.periods if p not in EDITIONS_BY_PERIOD]
    if unknown_p:
        parser.error(f"unknown periods {unknown_p}; known: {list(EDITIONS_BY_PERIOD)}")
    unknown_t = [t for t in args.tables if t not in TABLES]
    if unknown_t:
        parser.error(f"unknown tables {unknown_t}; known: {list(TABLES)}")

    args.output.mkdir(parents=True, exist_ok=True)

    if args.schema_map:
        doc = _write_schema_map(args.output, args.schema_map_path)
        ng = sum(len(t["groups"]) for t in doc.values())
        print(f"Schema map → {args.schema_map_path}  ({len(doc)} table(s), {ng} group(s) total)")
        return
    if args.report_only:
        doc = _write_report(args.output, args.report)
        print(f"Report → {args.report}  ({len(doc)} table(s))")
        return
    if args.variables:
        n = _write_variables_yaml(args.output, args.schema_map_path, args.yaml_dir,
                                  args.cat_threshold)
        print(f"Wrote {n} variables_enigh_<table>_<gNN>.yaml → {args.yaml_dir}")
        return
    if args.validate:
        n_files, n_fail = _write_validation_report(args.output, args.schema_map_path,
                                                   args.validate_report)
        print(f"Validation report → {args.validate_report}  "
              f"({n_fail}/{n_files} file(s) failed their group schema)")
        return
    if args.update_registry:
        bc.update_registry(_mirror_files(args.output), args.registry)
        return

    editions = [EDITIONS_BY_PERIOD[p] for p in args.periods]
    if args.dry_run:
        print(f"[dry-run] {len(editions)} edition(s):")
        for e in editions:
            tables = [t for t in args.tables if t in e.tables]
            print(f"  {e.period} ({e.regime}) — {len(tables)} table(s)")
            for t in tables:
                print(f"      {t}: {e.url(t)} → enigh_{t}_{e.period}.parquet")
        return

    print(f"Catalog verified {CATALOG_VERIFIED_DATE}; {len(editions)} edition(s)")
    failed = 0
    for e in editions:
        infos = _build_edition(e, args.tables, args.raw_dir, args.cache_dir, args.output,
                               args.retries, args.cleanup_raw)
        for info in infos:
            st = info["status"]
            if st == "absent":
                continue  # table not published for this edition (by catalog)
            if st == "ok":
                print(f"  {e.period}/{info['table']}: {info['rows']:,} rows, {info['cols']} cols, "
                      f"enc={info['encoding']}, {info['size_kb'] / 1024:.1f} MB")
            else:
                failed += 1
                print(f"  ! {e.period}/{info['table']}: {st.upper()} — "
                      f"{info.get('error') or info.get('member')}")
    print(f"\nDone: {len(editions)} edition(s); {failed} table(s) failed/missing.")


if __name__ == "__main__":
    main()
