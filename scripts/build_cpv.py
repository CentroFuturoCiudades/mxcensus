"""Build the CPV-family parquet mirror (censos / conteos / encuestas intercensales).

Maintainer-only — NOT part of the installed package.

The CPV family (``mxcensus.data._cpv_catalog``, ``docs/cpv/PLAN.md``) spans every census,
conteo and encuesta intercensal 1990–2025. Unlike ENIGH (one ZIP per table), one INEGI
**microdata ZIP per state** carries several tables (``viviendas``/``personas``/``migrantes``
…), and aggregate products (``iter``/``ageb`` per state, ``estimaciones`` national) ship one
ZIP each. This script loops over (edition, product, state), downloads + verifies each ZIP
once (cached, so a re-run resumes without re-downloading), extracts only the requested
tables' members and writes faithful-raw parquet: ``cpv_{table}_{period}_{NN}.parquet``
(per state) / ``cpv_{table}_{period}.parquet`` (national), every column ``string``, only
empty cells null, zstd.

Microdata files are large (Estado de México personas ≈ 0.5 GB of CSV), so CSVs are read with
``pyarrow.csv`` (not ``pandas.read_csv(dtype=str)``, whose object strings would need tens of
GB) and the encoding is sniffed by streaming the bytes.

Only editions in ``_ENABLED`` build (unit 1a: EIC 2025); ``--dry-run`` previews any edition.
Metadata modes (``--schema-map``/``--variables``/``--validate``/…) arrive in unit 1b.

Dry run (URLs + member patterns, no download):
    .venv/bin/python scripts/build_cpv.py --dry-run --periods 2025

Real build (states 01 and 09 + the national estimaciones file):
    .venv/bin/python scripts/build_cpv.py --periods 2025 --states 1 9
"""
from __future__ import annotations

import argparse
import codecs
import csv
import resource
import shutil
import sys
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

import _build_common as bc
from mxcensus.data._catalog import STATE_ABBR, STATE_CODE_FMT
from mxcensus.data._cpv_catalog import (
    CATALOG_VERIFIED_DATE,
    EDITIONS_BY_PERIOD,
    TABLES,
    CpvEdition,
    cpv_zip_entry,
    find_member,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"

# Editions whose build is enabled (docs/cpv/PLAN.md unit table). DBF editions (2010 and
# earlier) need their own reader (unit 3b+); they stay dry-run-only until then.
_ENABLED = ("2025",)

_HIGH_BYTES = bytes(range(0x80, 0x100))
_CHUNK = 1 << 24  # 16 MiB


# --- CSV reading ------------------------------------------------------------------------

def _sniff_encoding(csv_path: Path, chunk_size: int = _CHUNK) -> str:
    """Choose the decoding that preserves the most of an INEGI CSV's accented text.

    Same decision as ``build_enigh._sniff_encoding`` (``utf-8`` clean, ``utf-8/replace`` for
    UTF-8 with a few bad bytes, else ``cp1252``/``latin-1``), but **streamed** in chunks so a
    0.5 GB microdata CSV is never held in memory. Pass 1 counts high bytes (≥0x80) and checks
    strict UTF-8; only a file that fails it gets pass 2 (U+FFFD count under utf-8/replace,
    strict cp1252). Incremental decoders carry multi-byte sequences across chunk boundaries,
    so the result equals the one-shot decode.
    """
    high = 0
    utf8 = codecs.getincrementaldecoder("utf-8")()
    utf8_ok = True
    with open(csv_path, "rb") as f:
        while chunk := f.read(chunk_size):
            high += len(chunk) - len(chunk.translate(None, _HIGH_BYTES))
            if utf8_ok:
                try:
                    utf8.decode(chunk)
                except UnicodeDecodeError:
                    utf8_ok = False
    if high == 0:
        return "utf-8"
    if utf8_ok:
        try:
            utf8.decode(b"", final=True)  # a truncated trailing sequence is invalid
            return "utf-8"
        except UnicodeDecodeError:
            pass

    replace = codecs.getincrementaldecoder("utf-8")(errors="replace")
    cp1252 = codecs.getincrementaldecoder("cp1252")()
    bad, cp1252_ok = 0, True
    with open(csv_path, "rb") as f:
        while chunk := f.read(chunk_size):
            bad += replace.decode(chunk).count("�")
            if cp1252_ok:
                try:
                    cp1252.decode(chunk)
                except UnicodeDecodeError:
                    cp1252_ok = False
    bad += replace.decode(b"", final=True).count("�")
    if bad < 0.1 * high:
        return "utf-8/replace"
    return "cp1252" if cp1252_ok else "latin-1"


def _read_header(csv_path: Path, encoding: str) -> list[str]:
    """The CSV's column names (BOM stripped, as pyarrow strips it)."""
    enc, errors = ("utf-8", "replace") if encoding == "utf-8/replace" else (encoding, "strict")
    with open(csv_path, encoding=enc, errors=errors, newline="") as f:
        header = next(csv.reader(f), [])
    if header and header[0].startswith("﻿"):
        header[0] = header[0][1:]
    return header


def _read_csv_arrow(csv_path: Path) -> tuple[pa.Table, str]:
    """Read an INEGI CSV faithfully as an all-``string`` Arrow table; return it + encoding.

    Every column is typed ``string`` up front (no inference, codes keep their zero-padding);
    only empty cells become null (pandas' default NA list would also null ``NA``/``N/A``/
    ``null``… — ``null_values=[""]`` is the more faithful choice). Quoted fields may span
    lines. ``utf-8/replace`` files are decoded through a replacing recoder (pyarrow's own
    transcoder is strict).
    """
    enc = _sniff_encoding(csv_path)
    header = _read_header(csv_path, enc)
    dupes = sorted({c for c in header if header.count(c) > 1})
    if not header or dupes:
        raise ValueError(f"{csv_path.name}: unusable header (duplicates {dupes})")
    convert = pacsv.ConvertOptions(column_types={c: pa.string() for c in header},
                                   strings_can_be_null=True, null_values=[""])
    parse = pacsv.ParseOptions(newlines_in_values=True)
    if enc == "utf-8/replace":
        with open(csv_path, "rb") as raw:
            src = codecs.EncodedFile(raw, "utf-8", "utf-8", errors="replace")
            table = pacsv.read_csv(src, parse_options=parse, convert_options=convert)
    else:
        table = pacsv.read_csv(csv_path, read_options=pacsv.ReadOptions(encoding=enc),
                               parse_options=parse, convert_options=convert)
    if table.column_names != header:  # pragma: no cover - pyarrow contract
        raise ValueError(f"{csv_path.name}: parsed columns differ from the header")
    return table, enc


def _table_to_parquet(table: pa.Table, parquet_path: Path) -> dict:
    """Write a faithful-raw Arrow table to zstd parquet; return diagnostics."""
    pq.write_table(table, parquet_path, compression="zstd")
    return {
        "rows": table.num_rows,
        "cols": table.num_columns,
        "size_kb": parquet_path.stat().st_size // 1024,
    }


def _peak_rss_mb() -> float:
    """Peak resident memory of this process so far (ru_maxrss: bytes on macOS, KiB on Linux)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 2**20 if sys.platform == "darwin" else rss / 2**10


# --- plan ------------------------------------------------------------------------------

Job = tuple[CpvEdition, str, int | None, tuple[str, ...]]


def _plan(editions: list[CpvEdition], tables: list[str], states: list[int]) -> list[Job]:
    """(edition, product, state, tables) jobs — one per ZIP to fetch.

    A per-state product yields one job per requested state; a national product (EIC 2025
    ``estimaciones``) yields one job with ``state=None`` whatever ``states`` is. Products
    with none of the requested tables are skipped.
    """
    jobs: list[Job] = []
    for e in editions:
        for product in e.products:
            want = tuple(t for t in e.tables_in(product) if t in tables)
            if not want:
                continue
            if e.per_state(product):
                jobs += [(e, product, s, want) for s in states]
            else:
                jobs.append((e, product, None, want))
    return jobs


def _member_plan(names: list[str], edition: CpvEdition, tables: tuple[str, ...],
                 state: int | None) -> dict[str, str | None]:
    """Table → its ZIP member (``None`` when no unique member matches)."""
    plan: dict[str, str | None] = {}
    for t in tables:
        try:
            plan[t] = find_member(names, edition, t, state)
        except LookupError:
            plan[t] = None
    return plan


# --- build -----------------------------------------------------------------------------

def _build_zip(edition: CpvEdition, product: str, state: int | None,
               tables: tuple[str, ...], raw_dir: Path, cache_dir: Path, out_dir: Path,
               retries: int, cleanup_raw: bool = True) -> list[dict]:
    """Download+verify one product ZIP, then convert each requested table's member.

    Statuses per table: ``ok``; ``absent`` (the edition does not publish it); ``malformed``
    (download/ZIP failure — every table of the ZIP — or an unreadable CSV); ``missing`` (no
    unique member matches). The caller's sweep continues past any failure.
    """
    base = {"period": edition.period, "state": state}
    infos = [{**base, "table": t, "status": "absent"} for t in tables if not edition.has(t)]
    tables = tuple(t for t in tables if edition.has(t))
    entry = cpv_zip_entry(edition, product, state)
    try:
        zip_path = bc.fetch_zip_verified(entry.url, cache_dir,
                                         edition.zip_filename(product, state), retries)
    except Exception as exc:  # soft-404 / truncated / network
        err = f"{type(exc).__name__}: {exc}"
        return infos + [{**base, "table": t, "status": "malformed", "error": err}
                        for t in tables]

    # Per-state subdirectory: some members carry no state code (1995 ``datgen95.dbf``).
    extract_dir = raw_dir / entry.extract_dir / (STATE_CODE_FMT(state) if state else "nacional")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        members = _member_plan(names, edition, tables, state)
        for member in filter(None, members.values()):
            zf.extract(member, extract_dir)

    for table, member in members.items():
        if member is None:
            infos.append({**base, "table": table, "status": "missing", "member": names})
            continue
        out_path = out_dir / edition.filename(table, state)
        try:
            arrow, enc = _read_csv_arrow(extract_dir / member)
            info = _table_to_parquet(arrow, out_path)
            del arrow
        except Exception as exc:  # unparsable CSV: report, keep sweeping
            out_path.unlink(missing_ok=True)
            infos.append({**base, "table": table, "status": "malformed", "member": member,
                          "error": f"{type(exc).__name__}: {exc}"})
            continue
        info.update({**base, "table": table, "member": member, "encoding": enc,
                     "file": out_path.name, "status": "ok", "peak_rss_mb": _peak_rss_mb()})
        infos.append(info)
    if cleanup_raw:  # bound disk use: drop extracted CSVs once converted
        shutil.rmtree(extract_dir, ignore_errors=True)
    return infos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--periods", nargs="+", default=list(_ENABLED), metavar="YYYY",
                        help=f"Edition years (default: the build-enabled {list(_ENABLED)}; "
                             f"known {list(EDITIONS_BY_PERIOD)})")
    parser.add_argument("--tables", nargs="+", default=list(TABLES), metavar="TABLE",
                        help=f"Tables to convert (default: all published; known {list(TABLES)})")
    parser.add_argument("--states", nargs="+", type=int, default=sorted(STATE_ABBR),
                        metavar="N", help="State codes 1-32 for per-state products (default: "
                        "all); national products are built regardless")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR")
    parser.add_argument("--retries", type=int, default=2, metavar="N")
    parser.add_argument("--keep-raw", dest="cleanup_raw", action="store_false",
                        help="Keep extracted CSVs (default: delete after conversion)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the (edition, product, state) → member → file plan; no download")
    parser.set_defaults(cleanup_raw=True)
    args = parser.parse_args(argv)

    unknown_p = [p for p in args.periods if p not in EDITIONS_BY_PERIOD]
    if unknown_p:
        parser.error(f"unknown periods {unknown_p}; known: {list(EDITIONS_BY_PERIOD)}")
    unknown_t = [t for t in args.tables if t not in TABLES]
    if unknown_t:
        parser.error(f"unknown tables {unknown_t}; known: {list(TABLES)}")
    bad_s = [s for s in args.states if s not in STATE_ABBR]
    if bad_s:
        parser.error(f"states must be INEGI codes 1-32, got {bad_s}")

    editions = [EDITIONS_BY_PERIOD[p] for p in args.periods]
    jobs = _plan(editions, args.tables, args.states)

    if args.dry_run:
        print(f"[dry-run] {len(editions)} edition(s), {len(jobs)} ZIP(s):")
        for e, product, s, tables in jobs:
            where = STATE_CODE_FMT(s) if s else "national"
            print(f"  {e.period} {product} {where}: {e.zip_url(product, s)}")
            for t in tables:
                print(f"      {t}: /{e.member_regex(t, s).pattern}/i → {e.filename(t, s)}")
        return 0

    disabled = [e.period for e in editions if e.period not in _ENABLED]
    if disabled:
        parser.error(f"editions {disabled} are not enabled for build yet "
                     f"(enabled: {list(_ENABLED)}); use --dry-run to preview them")

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Catalog verified {CATALOG_VERIFIED_DATE}; {len(editions)} edition(s), "
          f"{len(jobs)} ZIP(s)")
    failed = written = 0
    for e, product, s, tables in jobs:
        infos = _build_zip(e, product, s, tables, args.raw_dir, args.cache_dir, args.output,
                           args.retries, args.cleanup_raw)
        for info in infos:
            st = info["status"]
            where = f"{e.period}/{info['table']}/{STATE_CODE_FMT(s) if s else 'national'}"
            if st == "absent":
                continue  # table not published for this edition (by catalog)
            if st == "ok":
                written += 1
                print(f"  {where}: {info['rows']:,} rows, {info['cols']} cols, "
                      f"enc={info['encoding']}, {info['size_kb'] / 1024:.1f} MB "
                      f"(peak RSS {info['peak_rss_mb']:,.0f} MB)", flush=True)
            else:
                failed += 1
                print(f"  ! {where}: {st.upper()} — {info.get('error') or info.get('member')}",
                      flush=True)
    print(f"\nDone: {written} file(s) written; {failed} table(s) failed/missing.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
