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

Schema fingerprinting / grouping, the inconsistency report, variable dictionaries,
validation and the registry append are added in later work units (mirroring the
``build_denue.py`` machinery); this unit is download → convert only.

Dry run (preview one quarter's plan, no download):
    uv run python scripts/build_enoe.py --dry-run --periods 2023t1

Real build (one quarter, all five tables):
    uv run python scripts/build_enoe.py --periods 2023t1
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

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


def _print_inventory(out_dir: Path) -> int:
    """Print an on-disk inventory of mirrored ENOE parquet (period × table → rows, cols)."""
    files = sorted(out_dir.glob("enoe_*.parquet"))
    if not files:
        print("No enoe_*.parquet found on disk.")
        return 0
    print(f"{'file':40s} {'rows':>10s} {'cols':>5s} {'size (MB)':>10s}")
    for p in files:
        pf = pq.ParquetFile(p)
        print(f"{p.name:40s} {pf.metadata.num_rows:>10,} "
              f"{len(pf.schema_arrow.names):>5} {p.stat().st_size / 1e6:>10.1f}")
    return len(files)


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
    parser.add_argument("--report-only", action="store_true",
                        help="Skip downloading; print an inventory of parquet on disk")
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

    if args.report_only:
        n = _print_inventory(args.output)
        print(f"\n{n} file(s) on disk.")
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
