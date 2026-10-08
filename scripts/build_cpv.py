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

Only editions in ``_ENABLED`` build (the CSV editions: EIC 2015, CPV 2020, EIC 2025); ``--dry-run``
previews any edition.

Dry run (URLs + member patterns, no download):
    .venv/bin/python scripts/build_cpv.py --dry-run --periods 2025

Real build (states 01 and 09 + the national estimaciones file):
    .venv/bin/python scripts/build_cpv.py --periods 2025 --states 1 9

Metadata modes (from the parquet on disk; same set as ``build_enigh.py``; order matters —
the map comes first, the dictionaries before the variables, the variables before validate):
    .venv/bin/python scripts/build_cpv.py --dictionary       # FD xlsx + catalogs + indicator dictionaries → data/dict/fd/{period}/
    .venv/bin/python scripts/build_cpv.py --schema-map       # → src/mxcensus/_yaml/cpv_schema_map.yaml
    .venv/bin/python scripts/build_cpv.py --report-only      # → docs/cpv/INCONSISTENCY_REPORT.md
    .venv/bin/python scripts/build_cpv.py --variables        # → src/mxcensus/_yaml/variables_cpv_{table}_{gNN}.yaml
    .venv/bin/python scripts/build_cpv.py --validate         # → docs/cpv/VALIDATION_REPORT.md (--jobs N)
    .venv/bin/python scripts/build_cpv.py --update-registry  # → upsert cpv_* hashes into registry.txt
"""
from __future__ import annotations

import argparse
import codecs
import csv
import functools
import re
import resource
import shutil
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import yaml

import _build_common as bc
import _dict_ddi as ddi
import _dict_fd as fd
from mxcensus._schema_groups import fingerprint
from mxcensus.data._catalog import STATE_ABBR, STATE_CODE_FMT
from mxcensus.data._cpv_catalog import (
    AGG_TABLES,
    CATALOG_VERIFIED_DATE,
    DICTIONARY_URLS,
    EDITIONS,
    EDITIONS_BY_PERIOD,
    FILE_RE,
    PRODUCT_OF,
    TABLES,
    CpvEdition,
    cpv_zip_entry,
    dictionary_url,
    find_member,
    parse_filename,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_YAML_DIR = _REPO_ROOT / "src" / "mxcensus" / "_yaml"
_DEFAULT_SCHEMA_MAP = _DEFAULT_YAML_DIR / "cpv_schema_map.yaml"
_CORE_PATH = _DEFAULT_YAML_DIR / "variables_cpv_core.yaml"
_DEFAULT_REPORT = _REPO_ROOT / "docs" / "cpv" / "INCONSISTENCY_REPORT.md"
_DEFAULT_VALIDATE_REPORT = _REPO_ROOT / "docs" / "cpv" / "VALIDATION_REPORT.md"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"
_DEFAULT_DICT_DIR = _REPO_ROOT / "data" / "dict" / "fd"
_DEFAULT_DDI_DIR = _REPO_ROOT / "data" / "dict" / "ddi"

# Editions whose build is enabled (docs/cpv/PLAN.md unit table). DBF editions (2010 and
# earlier) need their own reader (unit 3b+); they stay dry-run-only until then.
_ENABLED = ("2015", "2020", "2025")

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


# --- mirror scan + schema groups (per table; tables drift independently) ---------------

def _mirror_files(out_dir: Path) -> list[Path]:
    """Every CPV mirror file in ``out_dir`` (parsed with ``FILE_RE``, never ``split("_")``)."""
    return sorted(p for p in out_dir.glob("cpv_*.parquet") if FILE_RE.match(p.name))


def _scan_parquet(path: Path) -> dict:
    """One mirrored parquet's schema/metadata for the map and report (no data read)."""
    table, period, state = parse_filename(path.name)
    pf = pq.ParquetFile(path)
    cols = list(pf.schema_arrow.names)
    return {"table": table, "period": period, "state": state, "columns": cols,
            "fingerprint": fingerprint(cols), "rows": pf.metadata.num_rows,
            "size_kb": path.stat().st_size // 1024, "path": path}


def _rec_key(r: dict) -> tuple[int, int]:
    return int(r["period"]), r["state"] or 0


def _group_schemas(records: list[dict]) -> dict:
    """Assign stable per-table schema groups from scan records.

    Returns ``{table: {"latest", "fingerprints", "groups"}}`` — the shape written to
    ``cpv_schema_map.yaml``. Gids restart at ``g01`` in each table and are assigned in
    (edition, state) order, so a newer edition can only add or join a group. A group lists
    its ``periods`` and, only for an edition it covers partially (some states in another
    group), ``states: {period: [NN, …]}``. ``latest`` is the group holding most files of
    the newest edition.
    """
    doc: dict[str, dict] = {}
    for table in TABLES:
        recs = sorted((r for r in records if r["table"] == table), key=_rec_key)
        if not recs:
            continue
        fp_to_id: dict[str, str] = {}
        for r in recs:
            fp_to_id.setdefault(r["fingerprint"], f"g{len(fp_to_id) + 1:02d}")
        groups = {}
        for fp, gid in fp_to_id.items():
            mine = [r for r in recs if r["fingerprint"] == fp]
            periods = sorted({r["period"] for r in mine}, key=int)
            g = {"n_columns": len(mine[0]["columns"]), "files": len(mine), "periods": periods}
            partial = {}
            for p in periods:
                have = {r["state"] for r in mine if r["period"] == p}
                if have != {r["state"] for r in recs if r["period"] == p}:
                    partial[p] = sorted(have)
            if partial:
                g["states"] = partial
            g["columns"] = mine[0]["columns"]
            groups[gid] = g
        newest = max(int(r["period"]) for r in recs)
        counts = Counter(fp_to_id[r["fingerprint"]] for r in recs if int(r["period"]) == newest)
        doc[table] = {"latest": max(counts, key=lambda g: (counts[g], g)),
                      "fingerprints": dict(fp_to_id), "groups": groups}
    return doc


def _write_schema_map(out_dir: Path, map_path: Path) -> dict:
    """Group every mirrored CPV file by its exact schema and write cpv_schema_map.yaml."""
    doc = _group_schemas([_scan_parquet(p) for p in _mirror_files(out_dir)])
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return doc


def _states_text(states) -> str:
    return ", ".join(STATE_CODE_FMT(s) for s in sorted(states)) if states else "national"


def _write_report(out_dir: Path, report_path: Path) -> dict:
    """Scan every mirrored CPV parquet and (re)write the schema inconsistency report.

    Per table: an inventory (edition → group, files, states, rows), the schema groups,
    the column drift between consecutive editions (their ``latest``-style majority groups)
    and, for the editions on disk or enabled for build, the files still missing.
    """
    records = [_scan_parquet(p) for p in _mirror_files(out_dir)]
    doc = _group_schemas(records)
    present = sorted({r["period"] for r in records}, key=int)
    L = ["# CPV inconsistency report", "",
         f"Generated by `scripts/build_cpv.py --report-only` (catalog verified "
         f"{CATALOG_VERIFIED_DATE}). Tables mirrored: {sorted(doc)}. Editions on disk: "
         f"{present}.", "",
         "Schema groups are assigned **per table** (tables drift independently); group ids "
         "restart at `g01` in each table and follow (edition, state) order. Files are "
         "faithful raw (every column a string, only empty cells null; `STEP_1a.md`).", ""]
    for table in TABLES:
        if table not in doc:
            continue
        recs = [r for r in records if r["table"] == table]
        fps = doc[table]["fingerprints"]
        periods = sorted({r["period"] for r in recs}, key=int)
        L += [f"## {table}", "",
              f"Groups: {len(doc[table]['groups'])}. Latest: `{doc[table]['latest']}`. "
              f"Files: {len(recs)}. Rows: {sum(r['rows'] for r in recs):,}.", "",
              "| edition | group | files | states | rows |", "|---|---|---|---|---|"]
        major = {}
        for p in periods:
            by_gid = defaultdict(list)
            for r in recs:
                if r["period"] == p:
                    by_gid[fps[r["fingerprint"]]].append(r)
            major[p] = max(by_gid, key=lambda g: (len(by_gid[g]), g))
            for gid, rs in sorted(by_gid.items()):
                states = [r["state"] for r in rs if r["state"]]
                where = _states_text(states) if len(states) < 32 else "all 32"
                L.append(f"| {p} | {gid} | {len(rs)} | {where} | "
                         f"{sum(r['rows'] for r in rs):,} |")
        L += ["", "### Schema groups"]
        for gid, g in doc[table]["groups"].items():
            part = f"; partial editions {g['states']}" if g.get("states") else ""
            L.append(f"- **{gid}** — {g['n_columns']} cols, {g['files']} file(s), "
                     f"editions {g['periods']}{part}")
        L.append("")
        drift = []
        for prev, cur in zip(periods, periods[1:]):
            a = set(doc[table]["groups"][major[prev]]["columns"])
            b = set(doc[table]["groups"][major[cur]]["columns"])
            added, removed = sorted(b - a), sorted(a - b)
            if added or removed:
                drift.append(f"- **{prev} → {cur}**: "
                             + (f"added {added}" if added else "")
                             + ("; " if added and removed else "")
                             + (f"removed {removed}" if removed else ""))
        if drift:
            L += ["### Schema drift (consecutive editions on disk)"] + drift + [""]

    L += ["## Missing (catalog vs mirror)", ""]
    on_disk = {p.name for p in _mirror_files(out_dir)}
    missing = []
    for e in EDITIONS:
        if e.period not in set(present) | set(_ENABLED):
            continue
        for t in e.tables:
            product = PRODUCT_OF[t]
            states = sorted(STATE_ABBR) if e.per_state(product) else [None]
            gone = [s for s in states if e.filename(t, s) not in on_disk]
            if gone:
                missing.append(f"- {e.period}/{t}: {len(gone)} file(s) — "
                               f"{'national' if gone == [None] else _states_text(gone)}")
    L += missing or ["None — every catalog file of the editions on disk is present."]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return doc


# --- dictionaries (FD workbook + classification catalogs + indicator CSVs) -----------------
# The FD is an .xlsx (2020, 2025) or a legacy .xls (2015), both read with the standard
# library (scripts/_dict_fd.py); RNM DDI codebooks are fetched for reference only.

# Aggregate products ship their indicator dictionary inside the data ZIP.
_INDICATOR_DICT_RE = re.compile(r"(^|/)diccionario_datos[^/]*\.csv$", re.IGNORECASE)
# Per-table --cat-threshold override: the aggregate cells are numbers (and their sentinel
# codes), never worth enumerating as categories.
_TABLE_THRESHOLD = {"estimaciones": 0, "iter": 0, "ageb": 0}
# The non-numeric cell codes of an edition's aggregates when its indicator dictionaries
# carry no footnotes declaring them (EIC 2025's do: NA, MI). CPV 2020 ITER/AGEB, over all 32
# states (unit 2a): ``*`` hides the counts of a locality or block with one or two inhabited
# dwellings (22.4 M ITER and 78.7 M AGEB cells; it is also the TAMLOC of the total rows,
# which have no size class); ``N/D`` fills every indicator but the population and dwelling
# totals of 152 localities and 621 blocks; ``N/A`` is a ratio with a zero denominator
# (REL_H_M, PROM_HNV).
_AGG_SPECIALS: dict[str, dict[str, str]] = {
    "2020": {"*": "Dato reservado por confidencialidad", "N/D": "No disponible",
             "N/A": "No aplica"},
}


def _indicator_dict_path(dict_dir: Path, period: str, table: str) -> Path:
    return dict_dir / period / f"diccionario_datos_{table}.csv"


def _download(url: str, dest: Path, retries: int) -> Path:
    """Fetch one documentation file into ``dest`` (once). ZIP-based formats (xlsx, zip)
    are CRC-verified; anything else (a legacy ``.xls``) is rejected when INEGI answers with
    an HTML page (its soft-404)."""
    if dest.suffix.lower() in (".zip", ".xlsx"):
        return bc.fetch_zip_verified(url, dest.parent, dest.name, retries)
    path = bc.fetch_zip(url, dest.parent, dest.name)
    if path.read_bytes()[:256].lstrip().lower().startswith((b"<!doctype", b"<html")):
        path.unlink()
        raise RuntimeError(f"{url}: INEGI returned an HTML page (soft-404)")
    return path


def _fetch_dictionaries(dict_dir: Path, periods: list[str], cache_dir: Path,
                        retries: int, ddi_dir: Path = _DEFAULT_DDI_DIR) -> list[Path]:
    """Download each edition's dictionary sources into ``dict_dir/{period}/``.

    - the documentation files of ``DICTIONARY_URLS`` (EIC 2025: the FD workbook
      ``eic2025_micro_fd.xlsx`` and the classification catalogs ``889463931966_csv.zip``;
      EIC 2015: ``eic2015_fd.xls`` and ``eic2015_catalogos.zip``);
    - the RNM DDI codebook when the edition has one (``ddi_id``) into ``ddi_dir`` (2015's
      214 and 2020's 632 are fetched for reference; the FD workbooks are complete);
    - each aggregate table's ``diccionario_datos_*.csv``, copied out of its product ZIP
      (fetched into ``cache_dir`` if the build has not cached it) as
      ``diccionario_datos_{table}.csv``.
    """
    paths = []
    for period in periods:
        ed = EDITIONS_BY_PERIOD[period]
        dest = dict_dir / period
        dest.mkdir(parents=True, exist_ok=True)
        for kind, rel in DICTIONARY_URLS.get(period, {}).items():
            paths.append(_download(dictionary_url(period, kind), dest / rel.rsplit("/", 1)[-1],
                                   retries))
            print(f"  {period} {kind}: {paths[-1].name}")
        if ed.ddi_id is not None:
            paths.append(ddi.fetch_ddi(ed.ddi_id, ddi_dir))
            print(f"  {period} DDI {ed.ddi_id}: {paths[-1]}")
        for table in (t for t in ed.tables if t in AGG_TABLES):
            product = PRODUCT_OF[table]
            state = 1 if ed.per_state(product) else None  # the dictionary is national
            zip_path = bc.fetch_zip_verified(ed.zip_url(product, state), cache_dir,
                                             ed.zip_filename(product, state), retries)
            with zipfile.ZipFile(zip_path) as zf:
                hits = [n for n in zf.namelist() if _INDICATOR_DICT_RE.search(n)]
                if len(hits) != 1:
                    raise RuntimeError(f"{zip_path.name}: expected one indicator "
                                       f"dictionary, found {hits}")
                out = _indicator_dict_path(dict_dir, period, table)
                out.write_bytes(zf.read(hits[0]))
            paths.append(out)
            print(f"  {period} {table}: {hits[0]} → {out.name}")
    return paths


# FD sheet stem → canonical table, where INEGI names the sheet after its own table
# (EIC 2015: TR_Vivienda, TR_Persona); other sheets are named after the table already.
_FD_SHEET_TABLE = {"tr_vivienda": "viviendas", "tr_persona": "personas"}


@functools.cache
def _fd_docs(dict_dir: Path, period: str) -> dict:
    """The edition's FD workbook (``.xlsx``, or the legacy ``.xls`` of 2015) parsed into
    ``{table: {VAR: meta}}``, its classification catalogs applied; ``{}`` when no workbook
    was fetched."""
    rel = DICTIONARY_URLS.get(period, {})
    book = dict_dir / period / rel.get("fd", "").rsplit("/", 1)[-1]
    if not rel.get("fd", "").endswith((".xlsx", ".xls")) or not book.exists():
        return {}
    cat = dict_dir / period / rel.get("catalogos", "").rsplit("/", 1)[-1]
    catalogs = fd.read_catalogs(cat) if cat.suffix == ".zip" and cat.exists() else None
    return {_FD_SHEET_TABLE.get(stem, stem): doc
            for stem, doc in fd.parse_fd(book, catalogs).items()}


def _doc_for(dict_dir: Path, table: str, periods: list[str]) -> tuple[dict | None, str]:
    """The dictionary documenting a schema group: ``table`` in its newest edition that has
    one (the FD workbook sheet; an aggregate's indicator CSV). ``(doc, provenance)``."""
    for period in sorted(periods, key=int, reverse=True):
        if table in AGG_TABLES:
            path = _indicator_dict_path(dict_dir, period, table)
            if path.exists():
                return (fd.parse_indicator_csv(path, _AGG_SPECIALS.get(period)),
                        f"{path.name} ({period})")
        elif table in (docs := _fd_docs(dict_dir, period)):
            return docs[table], f"FD {period}/{table}"
    return None, "none"


def _write_variables_yaml(out_dir: Path, map_path: Path, yaml_dir: Path,
                          threshold: int = 64, dict_dir: Path = _DEFAULT_DICT_DIR) -> int:
    """Write one ``variables_cpv_{table}_{gNN}.yaml`` per (table, schema group).

    Per column, in priority: the hand-curated ``variables_cpv_core.yaml`` entry (verbatim,
    when in scope for the table — ``Tablas``, :func:`mxcensus.cpv._in_scope`);
    INEGI's dictionary entry (FD workbook / indicator CSV) reconciled against the codes
    observed in the group's files (:func:`_dict_fd.fd_entry`); else the data-enumerated
    identity map. Observed values are read one column at a time
    (:func:`_dict_ddi.observed_values`). Returns the number of files written.
    """
    from mxcensus.cpv import _in_scope

    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    core = yaml.safe_load(_CORE_PATH.read_text(encoding="utf-8"))
    files: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for p in _mirror_files(out_dir):
        table = parse_filename(p.name)[0]
        cols = pq.ParquetFile(p).schema_arrow.names
        gid = schema_map.get(table, {}).get("fingerprints", {}).get(fingerprint(cols))
        if gid is None:
            raise SystemExit(f"{p.name}: schema not in {map_path.name} — run --schema-map")
        files[(table, gid)].append(p)
    yaml_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for table, td in schema_map.items():
        thr = _TABLE_THRESHOLD.get(table, threshold)
        core_t = {c: m for c, m in core.items() if _in_scope(m, table)}
        for gid, g in td["groups"].items():
            paths = files.get((table, gid), [])
            observed = ddi.observed_values(paths, g["columns"], thr)
            doc, prov = _doc_for(dict_dir, table, g["periods"])
            entries, sources = ddi.group_entries(g["columns"], observed, core_t, doc, thr,
                                                 entry_fn=fd.fd_entry)
            counts = Counter(sources.values())
            print(f"  {table}/{gid}: {len(paths)}/{g['files']} file(s) read; {prov}; "
                  + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), flush=True)
            for col, src in sources.items():
                if src.endswith("+data") or src == "data":
                    print(f"      {col}: {src} — {entries[col].get('Nota', '')}")
            ddi.dump_yaml(entries, yaml_dir / f"variables_cpv_{table}_{gid}.yaml")
            n += 1
    return n


# --- validation sweep (per file, hard pass/fail; the loaders only warn) --------------------

_BATCH_ROWS = 1 << 20


def _validate_file(path: Path, gid: str) -> dict:
    """Validate one mirrored file against its (table, group) tight schema, in row batches
    of ``_BATCH_ROWS`` (bounded memory for the multi-million-row personas files)."""
    import pandera.pandas as pandera
    import pandas as pd
    from mxcensus.cpv import _group_schema

    table = parse_filename(path.name)[0]
    schema = _group_schema(table, gid)
    t0 = time.time()
    failures = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=_BATCH_ROWS):
        frame = pa.Table.from_batches([batch]).to_pandas()
        try:
            schema.validate(frame, lazy=True)
        except pandera.errors.SchemaErrors as exc:
            failures.append(exc.failure_cases[["column", "check", "failure_case"]])
    fails = []
    if failures:
        fc = pd.concat(failures, ignore_index=True)
        fails = (fc.groupby(["column", "check"], dropna=False)
                   .agg(count=("failure_case", "size"), example=("failure_case", "first"))
                   .reset_index().sort_values("count", ascending=False).to_dict("records"))
    return {"name": path.name, "table": table, "gid": gid, "rows": pf.metadata.num_rows,
            "status": "FAIL" if fails else "PASS", "fails": fails,
            "seconds": round(time.time() - t0, 1)}


def _write_validation_report(out_dir: Path, map_path: Path, report_path: Path,
                             jobs: int = 1) -> tuple[int, int]:
    """Validate every mirrored CPV parquet against its (table, group) schema
    (``mxcensus.cpv._group_schema``) and write the report; ``jobs`` files in parallel."""
    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    results, todo = [], []
    for p in _mirror_files(out_dir):
        table = parse_filename(p.name)[0]
        cols = pq.ParquetFile(p).schema_arrow.names
        gid = schema_map.get(table, {}).get("fingerprints", {}).get(fingerprint(cols))
        if gid is None:
            results.append({"name": p.name, "table": table, "gid": "?", "rows": 0,
                            "status": "UNKNOWN-SCHEMA", "fails": [], "seconds": 0})
        else:
            todo.append((p, gid))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(_validate_file, p, g) for p, g in todo]
            for fut in futures:
                results.append(fut.result())
                print(f"  {results[-1]['name']}: {results[-1]['status']} "
                      f"({results[-1]['seconds']} s)", flush=True)
    else:
        for p, g in todo:
            results.append(_validate_file(p, g))
            print(f"  {results[-1]['name']}: {results[-1]['status']} "
                  f"({results[-1]['seconds']} s)", flush=True)
    results.sort(key=lambda r: r["name"])

    failed = [r for r in results if r["status"] != "PASS"]
    L = ["# CPV validation report", "",
         "Each mirrored file validated against its (table, group) tight schema "
         "(`mxcensus.cpv._group_schema`: `isin` on every dictionary-coded column, numbers "
         "within `Rango` or a sentinel, digit codes for keys/geography and width-checked "
         "catalog codes). "
         f"Files: {len(results)}. Failing: {len(failed)}.", "",
         "| table | group | files | rows | failing |", "|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in results:
        by[(r["table"], r["gid"])].append(r)
    for (table, gid), rs in sorted(by.items(), key=lambda kv: (TABLES.index(kv[0][0]), kv[0][1])):
        L.append(f"| {table} | {gid} | {len(rs)} | {sum(r['rows'] for r in rs):,} | "
                 f"{sum(r['status'] != 'PASS' for r in rs)} |")
    L.append("")
    if not failed:
        L.append("All files pass their group schema.")
    for r in failed:
        L.append(f"## {r['name']} ({r['table']}/{r['gid']}) — {r['status']}")
        for f in r["fails"]:
            L.append(f"- `{f['column']}` / {f['check']}: {f['count']} row(s), "
                     f"e.g. `{f['example']}`")
        L.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return len(results), len(failed)


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
    meta = parser.add_argument_group("metadata modes (from the parquet on disk; no build)")
    meta.add_argument("--dictionary", action="store_true",
                      help="Download --periods' dictionary sources into --dict-dir")
    meta.add_argument("--dict-dir", type=Path, default=_DEFAULT_DICT_DIR, metavar="DIR")
    meta.add_argument("--schema-map", action="store_true",
                      help="(Re)write cpv_schema_map.yaml from the parquet on disk")
    meta.add_argument("--schema-map-path", type=Path, default=_DEFAULT_SCHEMA_MAP, metavar="FILE")
    meta.add_argument("--report-only", action="store_true",
                      help="(Re)write the schema inconsistency report")
    meta.add_argument("--report", type=Path, default=_DEFAULT_REPORT, metavar="FILE")
    meta.add_argument("--variables", action="store_true",
                      help="Write variables_cpv_{table}_{gNN}.yaml (core > dictionary > data)")
    meta.add_argument("--cat-threshold", type=int, default=64, metavar="N",
                      help="Max distinct values for a column to be enumerated as a category "
                           f"(per-table overrides: {_TABLE_THRESHOLD})")
    meta.add_argument("--yaml-dir", type=Path, default=_DEFAULT_YAML_DIR, metavar="DIR")
    meta.add_argument("--validate", action="store_true",
                      help="Validate every parquet against its group schema → report")
    meta.add_argument("--validate-report", type=Path, default=_DEFAULT_VALIDATE_REPORT,
                      metavar="FILE")
    meta.add_argument("--jobs", type=int, default=1, metavar="N",
                      help="Files validated in parallel (--validate)")
    meta.add_argument("--update-registry", action="store_true",
                      help="Upsert cpv_* hashes into registry.txt (preserving other entries)")
    meta.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE")
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

    if args.dictionary:
        paths = _fetch_dictionaries(args.dict_dir, args.periods, args.cache_dir, args.retries)
        print(f"{len(paths)} dictionary file(s) under {args.dict_dir}")
        return 0
    if args.schema_map:
        doc = _write_schema_map(args.output, args.schema_map_path)
        ng = sum(len(t["groups"]) for t in doc.values())
        print(f"Schema map → {args.schema_map_path}  ({len(doc)} table(s), {ng} group(s))")
        return 0
    if args.report_only:
        doc = _write_report(args.output, args.report)
        print(f"Report → {args.report}  ({len(doc)} table(s))")
        return 0
    if args.variables:
        n = _write_variables_yaml(args.output, args.schema_map_path, args.yaml_dir,
                                  args.cat_threshold, args.dict_dir)
        print(f"Wrote {n} variables_cpv_<table>_<gNN>.yaml → {args.yaml_dir}")
        return 0
    if args.validate:
        n_files, n_fail = _write_validation_report(args.output, args.schema_map_path,
                                                   args.validate_report, args.jobs)
        print(f"Validation report → {args.validate_report}  "
              f"({n_fail}/{n_files} file(s) failed their group schema)")
        return 1 if n_fail else 0
    if args.update_registry:
        bc.update_registry(_mirror_files(args.output), args.registry)
        return 0

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
