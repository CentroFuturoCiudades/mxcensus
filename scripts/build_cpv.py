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
GB) and the encoding is sniffed by streaming the bytes. DBF members (CPV 2010 and older) are
memory-mapped and decoded one field at a time by the stdlib reader ``scripts/_dbf.py``, into
the same all-``string`` faithful-raw form (fixed-width padding trimmed, deleted records
dropped).

Only editions in ``_ENABLED`` build (1990–2010 — DBF —, EIC 2015, CPV 2020, EIC 2025);
``--dry-run`` previews any edition.

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
    .venv/bin/python scripts/build_cpv.py --crosswalk        # → src/mxcensus/_yaml/cpv_iter_crosswalk.yaml (2010 ↔ 2020 ITER/AGEB)
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
from typing import NamedTuple

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import yaml

import _build_common as bc
import _dbf
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

# Editions whose build is enabled (docs/cpv/PLAN.md unit table). The DBF editions are read by
# scripts/_dbf.py (2010 since unit 3b, 2000/2005 since 4a, the 1990/1995 ITER since 5a).
_ENABLED = ("1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025")

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
    """The CSV's column names, the BOM stripped as pyarrow strips it — **before** the CSV
    parse, so a quoted first name keeps no quotes (CPV 2010: ``\ufeff"entidad",…``)."""
    enc, errors = ("utf-8", "replace") if encoding == "utf-8/replace" else (encoding, "strict")
    if enc == "utf-8":
        enc = "utf-8-sig"
    with open(csv_path, encoding=enc, errors=errors, newline="") as f:
        header = next(csv.reader(f), [])
    if header and header[0].startswith("\ufeff"):
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
        deleted = 0
        try:
            if member.lower().endswith(".dbf"):
                dbf = _dbf.read_dbf(extract_dir / member)
                arrow, enc, deleted = dbf.table, dbf.encoding, dbf.deleted
                del dbf
            else:
                arrow, enc = _read_csv_arrow(extract_dir / member)
            info = _table_to_parquet(arrow, out_path)
            del arrow
        except Exception as exc:  # unparsable CSV: report, keep sweeping
            out_path.unlink(missing_ok=True)
            infos.append({**base, "table": table, "status": "malformed", "member": member,
                          "error": f"{type(exc).__name__}: {exc}"})
            continue
        info.update({**base, "table": table, "member": member, "encoding": enc,
                     "deleted": deleted, "file": out_path.name, "status": "ok",
                     "peak_rss_mb": _peak_rss_mb()})
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

# Aggregate products ship their indicator dictionary inside the data ZIP: a
# ``diccionario_datos*.csv`` (2020, 2025) or any CSV in a ``diccionario_de_datos/`` folder
# (CPV 2010: ``fd_iter_cpv2010.csv``).
_INDICATOR_DICT_RE = re.compile(r"(^|/)(diccionario_datos[^/]*|diccionario_de_datos/[^/]+)\.csv$",
                                re.IGNORECASE)
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
# CPV 2010 ITER/AGEB (unit 3c, 32 states): ``*`` in 15.8 M ITER and 62.7 M AGEB cells and
# ``N/D`` in 42 550 / 127 985; no ``N/A``.
_AGG_SPECIALS: dict[str, dict[str, str]] = {
    "2020": {"*": "Dato reservado por confidencialidad", "N/D": "No disponible",
             "N/A": "No aplica"},
    "2010": {"*": "Dato reservado por confidencialidad", "N/D": "No disponible"},
    "2005": {"*": "Dato reservado por confidencialidad"},
    "2000": {"*": "Dato reservado por confidencialidad", "N/D": "No disponible"},
    "1995": {"*": "Dato reservado por confidencialidad"},
    "1990": {"*": "Dato reservado por confidencialidad"},
}


# Aggregate indicators that are class codes, not quantities: the ITER's 14-class locality
# size (2020 writes 01..14, a string; CPV 2010's dictionary gives 1..14, read as a number).
_AGG_CODES = frozenset({"TAMLOC", "TAM_LOC"})


# Indicator-dictionary mnemonics that misspell the data's column, {period: {dict: data}}.
_INDICATOR_RENAMES: dict[str, dict[str, str]] = {
    "1995": {"P_P5HLIYE": "P_PP5HLIYE"},     # the ITER DBF field has the doubled P
}


def _indicator_doc(path: Path, period: str) -> dict:
    """An indicator dictionary parsed with the edition's sentinels, the class codes
    (:data:`_AGG_CODES`) typed as strings."""
    doc = fd.parse_indicator_csv(path, _AGG_SPECIALS.get(period))
    renames = _INDICATOR_RENAMES.get(period, {})
    doc = {renames.get(k.strip().upper(), k): v for k, v in doc.items()}
    for name, meta in doc.items():
        if name.strip().upper() in _AGG_CODES and meta.get("Tipo") == "numeric":
            meta.update(Tipo="string", Especiales={})
            meta.pop("Decimales", None)
    return doc


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
            pdf = DICTIONARY_URLS.get(period, {}).get(f"fd_{table}")
            if pdf:          # 1990/1995: a PDF descriptor instead of a CSV in the ZIP
                out = _indicator_dict_path(dict_dir, period, table)
                rows = fd.parse_iter_fd_tsv(fd.pdf_words(dest / pdf.rsplit("/", 1)[-1]),
                                            _ITER_FD_ALIGN[period])
                fd.write_indicator_csv(rows, out)
                paths.append(out)
                print(f"  {period} {table}: {pdf} → {out.name} ({len(rows)} indicators)")
                continue
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


# How the 1990/1995 ITER descriptor PDFs lay out a row (_dict_fd.parse_iter_fd_tsv): 1990's
# cells are top-aligned on the row number, 1995's vertically centred on it.
_ITER_FD_ALIGN = {"1990": "top", "1995": "center"}


# FD sheet stem → canonical table, where INEGI names the sheet after its own table
# (EIC 2015: TR_Vivienda, TR_Persona; Conteo 2005: FD viviendas, FD hogar, FD personas;
# the CGPV 2000 PDF's file tags VIVHOG, PER, MIN); other sheets are named after the table.
_FD_SHEET_TABLE = {"tr_vivienda": "viviendas", "tr_persona": "personas",
                   "fd viviendas": "viviendas", "fd hogar": "hogares",
                   "fd personas": "personas",
                   "vivhog": "viviendas", "per": "personas", "min": "migrantes",
                   "datgen95": "personas", "migint95": "migrantes"}

# FD names that misspell the data's column, (period, table) → {FD name: data name}.
_FD_RENAMES = {
    ("2000", "viviendas"): {"TIPHOG": "TIPOHOG"},     # «Tipo de hogar», VHO_F's TIPOHOG
    ("2005", "hogares"): {"TOPERHOG": "TOTPEHOG"},    # «Total de personas en el hogar»
    ("1990", "personas"): {"ACT_PRI": "ACT_PRIN"},    # «Actividad principal»
}

# The editions whose FD is a PDF of text tables (read with poppler, _dict_fd.pdf_text), and
# their parsers; the 1990 catalogs are a workbook, 1995's a PDF of their own (6u).
_FD_PDF_PARSERS = {"1990": "parse_fd_1990_text", "1995": "parse_fd_1995_text"}
_CATALOG_PDF_PARSERS = {"1995": "parse_catalogs_1995_text"}

# The member of a dictionary ZIP that holds the FD (CGPV 2000: the PDF annex next to
# the sample design).
_FD_MEMBER_RE = re.compile(r"(^|/)fd_[^/]*\.pdf$", re.IGNORECASE)


@functools.cache
def _fd_docs(dict_dir: Path, period: str) -> dict:
    """The edition's FD parsed into ``{table: {VAR: meta}}``, its classification catalogs
    applied; ``{}`` when no FD was fetched. The FD is a workbook (``.xlsx``; the legacy
    ``.xls`` of 2005–2015), for CGPV 2000 a PDF inside a ZIP
    (:func:`_dict_fd.parse_fd_pdf`), for 1990/1995 a PDF of text tables
    (:data:`_FD_PDF_PARSERS`). The catalogs are a ZIP, one ``.xls`` (2005, 1990) or a PDF
    (1995, :data:`_CATALOG_PDF_PARSERS`)."""
    rel = DICTIONARY_URLS.get(period, {})
    book = dict_dir / period / rel.get("fd", "").rsplit("/", 1)[-1]
    if not book.exists() or book.suffix.lower() not in (".xlsx", ".xls", ".zip", ".pdf"):
        return {}
    catalogs = _edition_catalogs(dict_dir, period)
    if book.suffix.lower() == ".pdf":
        docs = getattr(fd, _FD_PDF_PARSERS[period])(fd.pdf_text(book), catalogs)
    elif book.suffix.lower() == ".zip":
        with zipfile.ZipFile(book) as zf:
            hits = [n for n in zf.namelist() if _FD_MEMBER_RE.search(n)]
            if len(hits) != 1:
                raise RuntimeError(f"{book.name}: expected one FD PDF, found {hits}")
            docs = fd.parse_fd_pdf(zf.read(hits[0]), catalogs)
    else:
        docs = fd.parse_fd(book, catalogs)
    out = {}
    for stem, doc in docs.items():
        table = _FD_SHEET_TABLE.get(stem.lower(), stem)
        renames = _FD_RENAMES.get((period, table), {})
        out[table] = {renames.get(k.upper(), k): v for k, v in doc.items()}
    return out


@functools.cache
def _edition_catalogs(dict_dir: Path, period: str) -> dict | None:
    """The edition's classification catalogs ``{stem: {code: label}}`` (a ZIP or ``.xls``,
    :func:`_dict_fd.read_catalogs`; a PDF, :data:`_CATALOG_PDF_PARSERS`); ``None`` when it has
    none or they were not fetched."""
    rel = DICTIONARY_URLS.get(period, {})
    cat = dict_dir / period / rel.get("catalogos", "").rsplit("/", 1)[-1]
    if cat.suffix.lower() in (".zip", ".xls") and cat.exists():
        return fd.read_catalogs(cat)
    if cat.suffix.lower() == ".pdf" and cat.exists():
        return getattr(fd, _CATALOG_PDF_PARSERS[period])(fd.pdf_text(cat))
    return None


def _doc_for(dict_dir: Path, table: str, periods: list[str]) -> tuple[dict | None, str]:
    """The dictionary documenting a schema group: ``table`` in its newest edition that has
    one (the FD workbook sheet; an aggregate's indicator CSV). ``(doc, provenance)``."""
    for period in sorted(periods, key=int, reverse=True):
        if table in AGG_TABLES:
            path = _indicator_dict_path(dict_dir, period, table)
            if path.exists():
                doc = _indicator_doc(path, period)
                # The AGEB file repeats the ITER's names and codes; CPV 2010's AGEB
                # dictionary leaves NOM_ENT/NOM_MUN/NOM_LOC out, so the ITER's fill in.
                fallback = _indicator_dict_path(dict_dir, period, "iter")
                if table == "ageb" and fallback.exists():
                    base = _indicator_doc(fallback, period)
                    lower = {k.lower() for k in doc}
                    doc = {**doc, **{k: v for k, v in base.items() if k.lower() not in lower}}
                return doc, f"{path.name} ({period})"
        elif table in (docs := _fd_docs(dict_dir, period)):
            return docs[table], f"FD {period}/{table}"
    return None, "none"


def _write_variables_yaml(out_dir: Path, map_path: Path, yaml_dir: Path,
                          threshold: int = 64, dict_dir: Path = _DEFAULT_DICT_DIR) -> int:
    """Write one ``variables_cpv_{table}_{gNN}.yaml`` per (table, schema group).

    Per column, in priority: the hand-curated ``variables_cpv_core.yaml`` entry (verbatim,
    when in scope for the table and the group's editions — ``Tablas``/``Periodos``,
    :func:`mxcensus.cpv._in_scope`);
    INEGI's dictionary entry (FD workbook / indicator CSV) reconciled against the codes
    observed in the group's files (:func:`_dict_fd.fd_entry`); else the data-enumerated
    identity map. Observed values are read one column at a time
    (:func:`_dict_ddi.observed_values`). Returns the number of files written.
    """
    from mxcensus.cpv import _in_scope, _scoped_entry

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
        for gid, g in td["groups"].items():
            core_t = {c: _scoped_entry(m, g["periods"]) for c, m in core.items()
                      if _in_scope(m, table, g["periods"])}
            paths = files.get((table, gid), [])
            observed = ddi.observed_values(paths, g["columns"], thr)
            doc, prov = _doc_for(dict_dir, table, g["periods"])
            entries, sources = ddi.group_entries(g["columns"], observed, core_t, doc, thr,
                                                 entry_fn=fd.fd_entry)
            if set(g["periods"]) & _RANGES_FROM_DATA:
                _reconcile_ranges(entries, paths, set(core_t))
            _label_code_groups(entries, paths, doc, g["periods"], set(core_t))
            if set(g["periods"]) & _BLANK_ZERO:
                _label_blank_zero(entries, set(core_t))
            _label_undocumented(entries, g["periods"], set(core_t))
            _label_quantities(entries, g["periods"], set(core_t), doc)
            _label_codes(entries, g["periods"], set(core_t), doc, dict_dir)
            _label_sentinels(entries, g["periods"], set(core_t))
            counts = Counter(sources.values())
            print(f"  {table}/{gid}: {len(paths)}/{g['files']} file(s) read; {prov}; "
                  + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), flush=True)
            for col, src in sources.items():
                if src.endswith("+data") or src == "data":
                    print(f"      {col}: {src} — {entries[col].get('Nota', '')}")
            ddi.dump_yaml(entries, yaml_dir / f"variables_cpv_{table}_{gid}.yaml")
            n += 1
    return n


# Editions whose FD ranges the data overrun: their numeric entries are reconciled with the
# values observed (_reconcile_ranges). The 1990/1995 FDs leave out 0 = none (years of
# technical studies, rooms, income) and some all-nines codes (N_F_GPOS 99).
_RANGES_FROM_DATA = frozenset({"1990", "1995"})


def _reconcile_ranges(entries: dict, paths: list[Path], skip: set[str]) -> None:
    """Fit each numeric entry's ``Rango`` to the values in ``paths``: a value below the range
    extends it down (0 = none); an all-nines value above it (99, 999) is an undocumented
    sentinel (``Especiales``); any other value above extends the range up. Each change is
    noted (``Nota``). The core entries (``skip``) are left alone."""
    for col, meta in entries.items():
        if col in skip or meta.get("Tipo") != "numeric" or not meta.get("Rango"):
            continue
        lo, hi = meta["Rango"]
        special = set(meta.get("Especiales") or {})
        values: set[str] = set()
        for path in paths:
            arr = pq.read_table(path, columns=[col]).column(col)
            values |= {v for v in pc.unique(arr).to_pylist() if v is not None}
        nums = {v for v in values if v not in special and re.fullmatch(r"\d+(\.\d+)?", v)}
        below = sorted((v for v in nums if float(v) < lo), key=float)
        above = sorted((v for v in nums if float(v) > hi), key=float)
        sentinels = [v for v in above if set(v) == {"9"}]
        beyond = [v for v in above if v not in sentinels]
        notes = []
        if below:
            meta["Rango"] = [int(float(below[0])), meta["Rango"][1]]
            notes.append(f"valores observados bajo el rango del FD: {below[:5]}")
        if beyond:
            meta["Rango"] = [meta["Rango"][0], int(float(beyond[-1]))]
            notes.append(f"valores observados sobre el rango del FD: {beyond[-5:]}")
        if sentinels:
            meta["Especiales"] = {**(meta.get("Especiales") or {}), **{v: v for v in sentinels}}
            notes.append(f"códigos observados sin etiqueta en el FD: {sentinels}")
        if notes:
            meta["Nota"] = "; ".join(([meta["Nota"]] if meta.get("Nota") else []) + notes)


# Coded items whose dictionary documents groups of codes, not each code (6u): every observed
# code is labelled by its own label in the edition's dictionary (catalog) where it has one,
# else by its group's, so the entry is categorical (_label_code_groups). (period, column) →
# the groups (first code, last code, label), transcribed from the FD:
# - CGPV 2000 (fd_muestra_censal_2000.pdf, «Parentesco»: PARENT merged into OTROPARE_C; its
#   701–703 huéspedes went to 501): no catalog, so every code takes its group's label;
# - CGPV 1990 (fd_cgpv1990.pdf, «CATALOGO DE PARENTESCO (CATPAREN) PRIMER DIGITO IGUAL A»): the
#   first digit, labelled as CATPAREN labels its one-digit group code, so the group code G00
#   (1.5M heads: 100) shares its label with the catalog's G01 where they name the same.
_CODE_GROUPS: dict[tuple[str, str], tuple[tuple[int, int, str], ...]] = {
    ("2000", "OTROPARE_C"): ((100, 100, "Jefe(a)"), (200, 200, "Esposo(a)"),
                             (300, 300, "Hijo(a)"), (401, 440, "Trabajador(es) doméstico(s)"),
                             (501, 503, "No tiene parentesco"), (601, 624, "Otro parentesco"),
                             (999, 999, "No especificado")),
    ("1990", "CVE_PAR"): ((100, 199, "JEFE O JEFA"), (200, 299, "ESPOSA(O) O COMPAÑERA(O)"),
                          (300, 399, "HIJO(A)"), (400, 499, "SIRVIENTA(E)"),
                          (500, 599, "NO TIENE PARENTESCO"), (600, 699, "OTRO PARENTESCO"),
                          (700, 799, "PERSONA SOLA"), (900, 999, "NO ESPECIFICADO")),
}


def _label_code_groups(entries: dict, paths: list[Path], doc: dict | None,
                       periods: list[str], skip: set[str]) -> None:
    """Label each :data:`_CODE_GROUPS` item of a schema group's editions: every code observed
    in ``paths`` takes its own label in ``doc`` (the FD with its catalog applied; an identity
    label does not count), else its group's; a «No especificado» label is a sentinel
    (``Especiales``). The entry becomes categorical, and ``Nota`` lists the groups and the
    codes labelled by theirs. A code outside every group raises. The core entries
    (``skip``) are left alone."""
    for (period, col), groups in _CODE_GROUPS.items():
        if period not in periods or col not in entries or col in skip:
            continue
        if set(periods) != {period}:
            raise ValueError(f"{col}: the code groups of {period} in a group of {periods}")
        meta = (doc or {}).get(col) or {}
        own = {c: lab for c, lab in {**(meta.get("Categorías") or {}),
                                     **(meta.get("Especiales") or {})}.items() if lab != c}
        observed: set[str] = set()
        for path in paths:
            arr = pq.read_table(path, columns=[col]).column(col)
            observed |= {v.strip() for v in pc.unique(arr).to_pylist() if v and v.strip()}
        labels, by_group = {}, []
        for code in sorted(observed):
            group = next((lab for lo, hi, lab in groups
                          if code.isdigit() and lo <= int(code) <= hi), None)
            if group is None:
                raise ValueError(f"{period} {col}: code {code!r} outside the FD's groups")
            labels[code] = own.get(code) or group
            if code not in own:
                by_group.append(code)
        entry = entries[col]
        entry["Tipo"] = "categorical"
        entry["Categorías"] = {c: lab for c, lab in labels.items()
                               if not fd._SENTINEL_RE.search(lab)}
        special = {c: lab for c, lab in labels.items() if c not in entry["Categorías"]}
        if special:
            entry["Especiales"] = special
        else:
            entry.pop("Especiales", None)
        spans = "; ".join(f"{lo}{'' if lo == hi else f'..{hi}'} = {lab}"
                          for lo, hi, lab in groups)
        entry["Nota"] = (f"grupos de claves del FD: {spans}; claves con la etiqueta de su "
                         f"grupo: {by_group}")
        entries[col] = {k: entry[k] for k in fd._ORDER if k in entry} | {
            k: v for k, v in entry.items() if k not in fd._ORDER}


# Editions that write 0 for «not asked» without labelling it (CGPV 1990: the schooling and
# religion of the under-5s, the activity and marital status of the under-12s, the refugios'
# dwelling items): a categorical entry's observed 0 is «Blanco por pase», the blank's label
# in the other editions' FDs and the legacy dictionaries (_label_blank_zero).
_BLANK_ZERO = frozenset({"1990"})
_UNLABELLED_RE = re.compile(r"códigos observados sin etiqueta en el FD: \[([^\]]*)\]")


def _label_blank_zero(entries: dict, skip: set[str]) -> None:
    """Label the code 0 «Blanco por pase» in each categorical entry that labels it with
    itself (an observed code the FD leaves out, :func:`_dict_ddi.dictionary_entry`), and say
    so in ``Nota``. The core entries (``skip``) are left alone."""
    for col, meta in entries.items():
        cats = meta.get("Categorías") or {}
        if col in skip or meta.get("Tipo") != "categorical" or cats.get("0") != "0":
            continue
        cats["0"] = "Blanco por pase"
        notes = [n for n in (meta.get("Nota") or "").split("; ") if n]
        for i, note in enumerate(notes):
            if m := _UNLABELLED_RE.fullmatch(note):
                rest = [c for c in m.group(1).split(", ") if c != "'0'"]
                notes[i] = f"códigos observados sin etiqueta en el FD: [{', '.join(rest)}]" \
                    if rest else ""
        notes.append("0 = no aplica (sin etiqueta en el FD): «Blanco por pase»")
        meta["Nota"] = "; ".join(n for n in notes if n)


# Codes a categorical entry labels with themselves because its FD leaves them out (the note
# «códigos observados sin etiqueta en el FD», :func:`_dict_ddi.dictionary_entry`), explained
# from INEGI's other documents and the records (8f). (period, column) → the codes it
# explains: a label makes the code a sentinel (``Especiales``), ``None`` keeps its identity
# label (a code whose meaning is per state); and the note that replaces the FD's.
class _Undocumented(NamedTuple):
    codes: dict[str, str | None]
    nota: str


_UNDOCUMENTED: dict[tuple[str, str], _Undocumented] = {
    # CGPV 1990 (fd_cgpv1990.pdf: «1..5 Y 7»): 6 is every person of the dwellings whose
    # household items were not answered — F_G_COC 9, N_F_GPOS 99 and a 9xx relationship, in
    # those 96,370 records only —; 7 is a household with its members whose type is unknown
    ("1990", "TIP_HOGAR"): _Undocumented(
        {"6": "NO ESPECIFICADO (SIN DATOS DEL HOGAR)"},
        "6 sin etiqueta en el FD («1..5 Y 7»): las personas de las viviendas sin datos del "
        "hogar (F_G_COC 9, N_F_GPOS 99 y un parentesco no especificado, 9xx: 96,370 "
        "personas, toda su vivienda); 7 = el tipo no especificado de un hogar con sus "
        "integrantes"),
    # Conteo 1995 (fd_encuesta_cpv1995.pdf: «01..05» the metropolitan areas, cities of
    # 100,000+ and state capitals, «Ver Catálogo»): its «Catálogo de áreas metropolitanas»
    # numbers each state's zones, Veracruz's up to 7
    ("1995", "ZONA"): _Undocumented(
        {"06": None, "07": None},
        "01..07 = las zonas de la entidad en el «Catálogo de áreas metropolitanas» "
        "(catalogos_cpv1995.pdf; un número por entidad: el código solo no nombra la zona); "
        "06 y 07, fuera del «01..05» del FD, sólo en Veracruz: A.M. de Poza Rica y A.M. de "
        "Veracruz"),
    # CGPV 2000 (fd_muestra_censal_2000.pdf: 0–7, 9): 8 is the cause not specified of who
    # stopped attending school (ASISTEN 2), its tabulados' «No especificado» (C2KED13–15,
    # 1–8; STEP_7z.md); 9 not specified is not among them
    ("2000", "ABANESCO"): _Undocumented(
        {"8": "Causa no especificada"},
        "8 sin etiqueta en el FD: la causa no especificada de quien dejó de asistir a la "
        "escuela (ASISTEN 2), la columna «No especificado» de los tabulados C2KED13–15, que "
        "cuentan 1–8; 9 = no especificado"),
}


def _label_undocumented(entries: dict, periods: list[str], skip: set[str]) -> None:
    """Explain the codes each categorical entry labels with themselves for want of an FD
    label, by :data:`_UNDOCUMENTED`: a labelled code becomes a sentinel (``Especiales``),
    and the spec's note replaces the FD's. An entry whose codes the table does not explain
    raises. The core entries (``skip``) are left alone."""
    for col, meta in entries.items():
        if col in skip or meta.get("Tipo") != "categorical":
            continue
        notes = [n for n in (meta.get("Nota") or "").split("; ") if n]
        found = [(i, m) for i, n in enumerate(notes) if (m := _UNLABELLED_RE.fullmatch(n))]
        if not found:
            continue
        (i, m), = found
        codes = {c.strip("'") for c in m.group(1).split(", ")}
        spec = next((s for (p, c), s in _UNDOCUMENTED.items() if c == col and p in periods),
                    None)
        if spec is None or not codes <= set(spec.codes):
            raise ValueError(f"{periods} {col}: codes {sorted(codes)} without an FD label "
                             f"({spec})")
        cats, special = dict(meta.get("Categorías") or {}), dict(meta.get("Especiales") or {})
        for code, label in spec.codes.items():
            if code in codes and label is not None:
                cats.pop(code)
                special[code] = label
        meta["Categorías"] = cats
        if special:
            meta["Especiales"] = dict(sorted(special.items()))
        notes[i] = spec.nota
        meta["Nota"] = "; ".join(notes)


# FD items that are quantities, not lists of codes (7f, 7q), which the parser reads as codes:
# a zero-padded range (_dict_fd: «0001..9999» is a locality's code) or a range whose only
# rows are its special values (the top code, «no especificado»: a catalog of 1–2 codes).
# (period, column) → the quantity's range (None: the FD's zero-padded range), its sentinels
# (``Especiales``; the FD's label where its layout gives one, else this one) and what the
# FD's text says of its values (``Nota``):
# - 7f: CGPV 1990's and 2000's number of persons in the dwelling, the value of the
#   occupants' averages (cpv_derived.cpv_ratio_constraints), equal to the dwelling's person
#   rows;
# - 7q: CGPV 2000's hours worked (FD {000..999,b}: it says nothing of 999, which 116,755
#   persons have beside 0–168 — Censo 2010's «No especificado», as its FD) and its monthly
#   incomes, of the persons and of the household (fd_muestra_censal_2000.pdf, «Ingresos por
#   trabajo», «Otros ingresos por persona», «Ingresos por hogar»: 000000 = no such income;
#   «si el valor rebasa a 999 999 se asigna el valor 999 998 para distinguirlo de los
#   ingresos no especificados (999 999)»), as Censo 2010/2020 type theirs;
# - 7q: CGPV 1990's monthly income (fd_cgpv1990.pdf, «53 INGRESOS»: 00000000..99999996 the
#   monthly wage; «los siguientes tres rubros se consideran como ingreso no especificado»:
#   99999997 eventual, 99999998 no sabe, 99999999 no especificado), in pesos of before the
#   1993 redenomination; 1990 writes 0 for everyone not employed too (not asked);
# - 7q: the Conteo 1995's income from work and first other income per their period
#   (fd_encuesta_cpv1995.pdf: P7_9A {00000..98000,99999,b}, P7_11A {00001..98000,99999,b}).


class _Quantity(NamedTuple):
    rango: tuple[int, int] | None = None
    especiales: dict[str, str] = {}
    nota: str = ""


_INCOME_2000 = _Quantity((0, 999998), {"999999": "No especificado"},
                         "pesos mensuales; 000000 = no recibe ingresos de este tipo; "
                         "999998 = 999,998 o más; 999999 = no especificado (el texto del FD)")
_QUANTITIES: dict[tuple[str, str], _Quantity] = {
    ("1990", "NUM_PERS"): _Quantity(), ("2000", "NUMPERS"): _Quantity(),
    ("2000", "HORTRA"): _Quantity(
        (0, 168), {"999": "No especificado"},
        "horas trabajadas en la semana; 999 = no especificado (el FD no lo dice: los datos "
        "van de 0 a 168 y 999, como en el FD de 2010)"),
    **{("2000", col): _INCOME_2000
       for col in ("INGRESOS", "JUBPENC", "AYUFAOPC", "AYUFADPC", "PROCAMPC", "OTROTIPC",
                   "OTINGPER", "INGTOPER", "INGTRHOG", "OTINGHOG", "INGTOHOG")},
    ("1990", "INGRESO"): _Quantity(
        (0, 99999996), {"99999997": "Eventual", "99999998": "No sabe",
                        "99999999": "No especificado"},
        "pesos mensuales de antes de la redenominación de 1993; 0 también para quien no "
        "está ocupado (no se le preguntó); el FD: «los siguientes tres rubros se consideran "
        "como ingreso no especificado»"),
    ("1995", "P7_9A"): _Quantity((0, 98000), {"99999": "No especificado"},
                                 "pesos por el periodo de P7_9B"),
    ("1995", "P7_11A"): _Quantity((1, 98000), {"99999": "No especificado"},
                                  "pesos por el periodo de P7_11B"),
}
_CODE_RANGE_RE = re.compile(r"(\d+)\.\.(\d+) = códigos \(no enumerados\)")
_CATALOG_NOTE_RE = re.compile(r"catálogo de \d+ códigos \(no enumerado\)")


def _label_quantities(entries: dict, periods: list[str], skip: set[str],
                      doc: dict | None = None) -> None:
    """Make each :data:`_QUANTITIES` item of a schema group's editions numeric: its
    ``Rango`` (the FD's zero-padded range unless given), its sentinels (``Especiales``) and
    a ``Nota`` with the codes the FD labels within the range. The core entries (``skip``)
    are left alone. An entry the FD no longer documents as codes, or whose FD (``doc``)
    documents a code out of the range that is no sentinel, or no sentinel given, raises."""
    for (period, col), q in sorted(_QUANTITIES.items()):
        if period not in periods or col not in entries or col in skip:
            continue
        entry = entries[col]
        note = entry.get("Nota") or ""
        m = _CODE_RANGE_RE.fullmatch(note)
        if (entry.get("Tipo") != "string" or not (m or _CATALOG_NOTE_RE.fullmatch(note))
                or not (m or q.rango)):
            raise ValueError(f"{period} {col}: not a code range in the FD ({entry})")
        lo, hi = q.rango or (int(m.group(1)), int(m.group(2)))
        meta = (doc or {}).get(col) or {}
        documented = {c: lab for c, lab in {**(meta.get("Categorías") or {}),
                                            **(meta.get("Especiales") or {})}.items()
                      if c.isdigit()}
        inside = {c: lab for c, lab in documented.items()
                  if lo <= int(c) <= hi and c not in q.especiales}
        if set(documented) - set(inside) != (set(q.especiales) if documented else set()):
            raise ValueError(f"{period} {col}: the FD's codes {sorted(documented)} are not "
                             f"the range {lo}..{hi} and the sentinels {sorted(q.especiales)}")
        notes = [f"cantidad: el FD escribe su rango con ceros a la izquierda "
                 f"({m.group(1)}..{m.group(2)}), como el de una clave" if m else
                 "cantidad: el FD lista sus valores especiales como los códigos de un catálogo",
                 *(f"{c} = {lab}" for c, lab in sorted(inside.items())),
                 *([q.nota] if q.nota else [])]
        entry["Tipo"] = "numeric"
        entry["Rango"] = [lo, hi]
        if q.especiales:
            entry["Especiales"] = {c: documented.get(c, lab) for c, lab in q.especiales.items()}
        entry["Nota"] = "; ".join(notes)
        entries[col] = {k: entry[k] for k in fd._ORDER if k in entry} | {
            k: v for k, v in entry.items() if k not in fd._ORDER}


# FD items that are codes, not quantities, which the parser reads as numbers (7r): a code
# space written as one labelled range («001-570 Clave de municipio»: _dict_fd._quantity reads
# a count) or as a range list without rows («{001-032,999}»). (period, column) → its type:
# - «string» where nobody enumerates the codes, as the edition's own birthplace items
#   (CGPV 2000 LNACEDO_C) and 2010–2025's catalog codes: the FD's ranges (first, last code,
#   label) and the codes it labels go into ``Nota``, its sentinels into ``Especiales``;
# - «categorical» where INEGI lists every code: the edition's ``catalog``, or another field
#   of the group (``like``, the FD's «Igual que en …»).
# Transcribed from the FDs:
# - CGPV 2000 (fd_muestra_censal_2000.pdf): the layout's rows and its text — «Municipio de
#   residencia en 1995»: «los valores que toma dependen del rango de municipios que existen en
#   la entidad (RES95EDO_C). Adicionalmente puede tomar el valor 999, que implica municipio no
#   especificado»; «Religión»: «Los códigos precodificados se transforman en claves dentro del
#   mnemónico OTRAREL_C. El código 1 (ninguna) es la clave 9100. El código 2 (católica) es la
#   clave 0001»; «País de destino»: «El código precodificado cuando el país de destino fue
#   Estados Unidos, se cambió de 1 a 221 en MPDESOTR_C». MLUGORI_C and MPDESOTR_C have no
#   rows: their codes and sentinels are LNACEDO_C's (600 «País no especificado»);
# - Conteo 2005 (fd_muestra_2005.xls): NIVANTES's catalog TC_ANTES lists every code (its rows
#   stop at 84; the catalog adds 94/95 doctorado); the data and the FD's rows write 0 unpadded;
# - Conteo 1995 (fd_encuesta_cpv1995.pdf): P7_11D/F «Igual que en PERIODO (1)» (P7_11B).


class _Code(NamedTuple):
    tipo: str
    rangos: tuple[tuple[str, str, str], ...] = ()
    codigos: dict[str, str] = {}
    especiales: dict[str, str] = {}
    nota: str = ""
    catalog: str | None = None
    like: str | None = None


_NOT_SPECIFIED = {"999": "No especificado"}
_CODES: dict[tuple[str, str], _Code] = {
    ("2000", "MUN95OTR_C"): _Code(
        "string", (("001", "570", "Clave de municipio"),), especiales=_NOT_SPECIFIED,
        nota="el municipio en la entidad de RES95EDO_C"),
    ("2000", "LTRABMUN_C"): _Code(
        "string", (("001", "570", "Clave de municipio"),), especiales=_NOT_SPECIFIED,
        nota="el municipio en la entidad de LTRABPAI_C"),
    ("2000", "QDIALECT_C"): _Code(
        "string", (("0111", "1311", "Clave de dialecto o lengua"),),
        {"5010": "Otras lenguas indígenas de México",
         "5020": "Otras lenguas indígenas de América"}, {"9999": "No especificado"}),
    ("2000", "OTRAREL_C"): _Code(
        "string", (("1101", "9001", "Clave de religión"),),
        {"0001": "Católica", "9100": "Ninguna"}, {"9999": "No especificado"},
        "el texto del FD: «El código 1 (ninguna) es la clave 9100. El código 2 (católica) es "
        "la clave 0001»; 9999 sin etiqueta en el FD"),
    ("2000", "OCUACTIV_C"): _Code("string", (("1100", "8390", "Clave de ocupación"),),
                                  especiales={"9999": "No especificado"}),
    ("2000", "ACTTRAB_C"): _Code("string", (("110", "939", "Clave de actividad"),),
                                 especiales=_NOT_SPECIFIED),
    ("2000", "MLUGORI_C"): _Code(
        "string", (("001", "032", "Clave de entidad"),), especiales=_NOT_SPECIFIED,
        nota="sin renglones en el FD: las claves y el 999 de LNACEDO_C"),
    ("2000", "MPDESOTR_C"): _Code(
        "string", (("100", "535", "Clave de país"),),
        especiales={"600": "País no especificado", "999": "No especificado"},
        nota="sin renglones en el FD: las claves, el 600 y el 999 de LNACEDO_C; el texto del "
             "FD: «El código precodificado cuando el país de destino fue Estados Unidos, se "
             "cambió de 1 a 221»"),
    ("2000", "MPAIRES_C"): _Code("string", (("100", "535", "País de destino"),),
                                 {"600": "Extranjero, otro país", "700": "México"},
                                 _NOT_SPECIFIED),
    ("2005", "NIVANTES"): _Code("categorical", catalog="TC_ANTES"),
    **{("1995", col): _Code("categorical", like="P7_11B",
                            nota="Igual que en PERIODO (1) (el FD)")
       for col in ("P7_11D", "P7_11F")},
}


def _label_codes(entries: dict, periods: list[str], skip: set[str], doc: dict | None = None,
                 dict_dir: Path = _DEFAULT_DICT_DIR) -> None:
    """Retype each :data:`_CODES` item of a schema group's editions as the codes it is: a
    «string» with the FD's ranges and labelled codes in ``Nota`` and its sentinels in
    ``Especiales``, or a «categorical» labelled by its catalog or by the field it repeats.
    The core entries (``skip``) are left alone. An entry no longer read as a number, or whose
    FD (``doc``) lists a code not given here, raises (the FD changed)."""
    for (period, col), spec in sorted(_CODES.items()):
        if period not in periods or col not in entries or col in skip:
            continue
        entry = entries[col]
        if entry.get("Tipo") != "numeric":
            raise ValueError(f"{period} {col}: not read as a number ({entry})")
        meta = (doc or {}).get(col) or {}
        rest = [n for n in (entry.get("Nota") or "").split("; ")
                if n and not re.fullmatch(r"\d+ = .*", n)]   # the codes it labelled in range
        out = {k: entry[k] for k in ("Descripción", "Pregunta", "Definición")
               if entry.get(k)}
        out |= {"Tipo": spec.tipo, "Longitud": entry["Longitud"]}
        notes = []
        if spec.tipo == "string":
            listed = set(meta.get("Especiales") or {}) | set(meta.get("Categorías") or {})
            known = set(spec.especiales) | set(spec.codigos)
            first = min(int(lo) for lo, _, _ in spec.rangos)
            last = max(int(hi) for _, hi, _ in spec.rangos)
            span = [min([first, *(int(c) for c in spec.codigos if int(c) < first)]), last]
            if not listed <= known or meta.get("Rango", span) != span:
                raise ValueError(f"{period} {col}: the FD's codes {sorted(listed)} and range "
                                 f"{meta.get('Rango')} are not {spec}")
            notes = [f"{lo}..{hi} = {label} (no enumerados)" for lo, hi, label in spec.rangos]
            notes += [f"{c} = {lab}" for c, lab in spec.codigos.items()]
            out["Especiales"] = dict(spec.especiales)
        elif spec.catalog:
            catalog = (_edition_catalogs(dict_dir, period) or {}).get(spec.catalog)
            if not catalog:
                raise ValueError(f"{period} {col}: catálogo {spec.catalog} no disponible")
            labels = {str(int(c)): lab for c, lab in catalog.items()}
            out["Categorías"] = {c: lab for c, lab in labels.items()
                                 if not fd._SENTINEL_RE.search(lab)}
            out["Especiales"] = {c: lab for c, lab in labels.items()
                                 if c not in out["Categorías"]}
            out["Catálogo"] = spec.catalog
        else:
            like = entries[spec.like]
            if like.get("Tipo") != "categorical" or not set(entry.get("Especiales") or {}) <= (
                    set(like.get("Categorías") or {}) | set(like.get("Especiales") or {})):
                raise ValueError(f"{period} {col}: not coded as {spec.like} ({like})")
            out["Categorías"] = dict(like["Categorías"])
            out["Especiales"] = dict(like.get("Especiales") or {})
        notes += rest + ([spec.nota] if spec.nota else [])
        if notes:
            out["Nota"] = "; ".join(notes)
        entries[col] = {k: out[k] for k in fd._ORDER if k in out} | {
            k: v for k, v in out.items() if k not in fd._ORDER}


# Numeric sentinels the FD lists without a label (in its header range, «{01..25,99}»), or that
# only the data show (_reconcile_ranges), which the parser labels with their own code (7r).
# (period, column) → their labels and where they come from (``Nota``): INEGI's words where its
# documents give them, else «No especificado», the label of the edition's other sentinels.
class _Sentinel(NamedTuple):
    especiales: dict[str, str]
    nota: str


def _no_label(code: str, more: str = "") -> _Sentinel:
    return _Sentinel({code: "No especificado"},
                     f"{code} sin etiqueta en el FD: «No especificado», como sus demás "
                     f"códigos no especificados{more}")


_INCOME_1995 = "; 98000 = $98,000 o más"
_SENTINELS: dict[tuple[str, str], _Sentinel] = {
    # CGPV 2000 (fd_muestra_censal_2000.pdf)
    ("2000", "CUADORM"): _no_label("99", "; el FD de 2005 la da a CUARDOM"),
    ("2000", "TOTCUART"): _no_label("99", "; el FD de 2005 la da a NUMCUAR"),
    ("2000", "ESCOACUM"): _Sentinel(
        {"99": "No especificado"},
        "el texto del FD: «Toma los valores de 99 cuando los años aprobados no fueron "
        "especificados (ESCOLARI = 9), aunque se tenga especificado el nivel académico»"),
    **{("2000", col): _Sentinel(
        {"99": "No especificado"},
        "el texto del FD (NUMHIJ): «El valor 99 indica que la mujer tuvo hijos pero no se sabe "
        "cuántos, lo cual implica que alguno de los campos de hijos fallecidos (HIJFAL) o hijos "
        "sobrevivientes (HIJSOB) tiene un valor no especificado»")
       for col in ("HIJFAL", "HIJSOB")},
    ("2000", "FECNACM"): _no_label("99"), ("2000", "FECNACA"): _no_label("9999"),
    ("2000", "MEDAD"): _no_label("999", " (EDAD: 999)"),
    ("2000", "MFECEMIM"): _no_label("99"), ("2000", "MFECEMIA"): _no_label("9999"),
    ("2000", "MFECRETM"): _no_label("99"), ("2000", "MFECRETA"): _no_label("9999"),
    # Conteo 1995 (fd_encuesta_cpv1995.pdf): the monthly incomes the FD derives from P7_9A and
    # P7_11A («Mensualizados por persona/hogar»), whose 99999 is «No especificado»; the
    # second and third other incomes, «Igual que en INGRESO (1)»
    **{("1995", col): _Sentinel(
        {"999999": "No especificado"},
        "999999 sin etiqueta en el FD: «No especificado», la del ingreso que mensualiza "
        "(P7_9A, P7_11A: 99999)")
       for col in ("P7_9MP", "P7_9MH", "P7_11MP", "P7_11MH", "INGMENTP", "INGMENTH")},
    ("1995", "P7_11C"): _Sentinel({"99999": "No especificado"},
                                  "Igual que en INGRESO (1) (el FD)" + _INCOME_1995
                                  + "; pesos por el periodo de P7_11D"),
    ("1995", "P7_11E"): _Sentinel({"99999": "No especificado"},
                                  "Igual que en INGRESO (1) (el FD)" + _INCOME_1995
                                  + "; pesos por el periodo de P7_11F"),
    # CGPV 1990 (fd_cgpv1990.pdf: 01..10): 99 only with TIP_HOGAR 6 and a 9xx relationship
    ("1990", "N_F_GPOS"): _Sentinel(
        {"99": "No especificado"},
        "99 = «No especificado»: sus 96,370 personas tienen TIP_HOGAR 6 (sin etiqueta en el "
        "FD) y un parentesco no especificado (9xx)"),
    # Censo 2010: its reference table TC_ESCOACUM_2010 (not a catalog: several levels a code)
    ("2010", "ESCOACUM"): _Sentinel({"99": "No especificado"},
                                    "TC_ESCOACUM_2010 es una tabla de referencia (varios "
                                    "niveles por código), no un catálogo: su 99 = «No "
                                    "Especificado»"),
}


def _label_sentinels(entries: dict, periods: list[str], skip: set[str]) -> None:
    """Label each numeric sentinel a schema group's entries label with its own code, by
    :data:`_SENTINELS`, and say where the label comes from (``Nota``). The core entries
    (``skip``) are left alone. A self-labelled sentinel not listed, or a listed item whose
    sentinels differ, raises."""
    for col, entry in entries.items():
        if col in skip or entry.get("Tipo") != "numeric":
            continue
        own = {c for c, lab in (entry.get("Especiales") or {}).items() if lab == c}
        spec = next((s for (p, c), s in _SENTINELS.items() if c == col and p in periods), None)
        if not own and spec is None:
            continue
        if spec is None or own != set(spec.especiales):
            raise ValueError(f"{periods} {col}: sentinels {sorted(own)} labelled with their "
                             f"own code ({spec})")
        entry["Especiales"] = {**entry["Especiales"], **spec.especiales}
        entry["Nota"] = "; ".join([n for n in [entry.get("Nota"), spec.nota] if n])


# --- ITER/AGEB indicator crosswalk across censuses (cpv_iter_crosswalk.yaml) --------------

_DEFAULT_CROSSWALK = _DEFAULT_YAML_DIR / "cpv_iter_crosswalk.yaml"
# Censuses whose ITER/AGEB the crosswalk spans (newest first: its names are canonical).
_XW_PERIODS = ("2020", "2010", "2005", "2000", "1995", "1990")
# Editions whose differently named indicators pair automatically with a newer indicator of
# the same description (normalized: case, accents, punctuation), renamed by harmonize=True.
# The censuses before 2010 renamed most mnemonics (P_TOTAL, PMASCUL, POBTMAS…) with the
# descriptions unchanged. The review rejects the automatic pairs in _XW_UNPAIR.
_XW_DESC_PERIODS = frozenset({"2005", "2000", "1995", "1990"})
# 2000's VP_CCUART says «con un dormitorio», like 2005's VPH_1DOR, but counts the dwellings
# with one room when an exclusive kitchen is not counted (6n: the sample reproduces it so).
_XW_UNPAIR = frozenset({("2000", "PCONDISC"), ("2000", "VP_CCUART")})
# Hand-reviewed pairs of differently named indicators (canonical → {period: source}) that
# harmonize=True renames onto the canonical name (the same indicator, another name) …
_XW_PAIRS_RENAMED: dict[str, dict[str, str]] = {
    "TAMLOC": {"2010": "TAM_LOC"},
    "P_15A49_F": {"2000": "POBF15_49"},
    "PSINDER": {"2000": "PSDERSS"},
    "PDER_SS": {"2000": "PCDERSS"},
    "PDER_IMSS": {"2000": "PDERIMSS"},
    "PDER_ISTE": {"2000": "PDERISTE"},
    "P15YM_SE": {"2000": "P15_SINSTR"},
    "P5_HLI_NHE": {"2000": "P5_HLIYNE"},
    "P5_HLI_HE": {"2000": "P5_HLIYE"},
    "PE_INAC": {"2000": "PECOINACT"},
    "PHOG_IND": {"2005": "P_HOG_IND"},
    "TOTHOG": {"2005": "TOT_HOG"},
    "POBHOG": {"2005": "P_HOGAR"},
    "HOGJEF_M": {"2005": "HOGAR_JM", "2000": "HOGJEFM"},
    "HOGJEF_F": {"2005": "HOGAR_JF", "2000": "HOGJEFF"},
    "PHOGJEF_M": {"2005": "P_HOG_JM", "2000": "PHOGJEFM"},
    "PHOGJEF_F": {"2005": "P_HOG_JF", "2000": "PHOGJEFF"},
    "OCUPVIVPAR": {"2000": "OCUVIVPAR"},
    "PROM_OCUP": {"2000": "PRO_OVP", "1995": "PRO_O_VP", "1990": "PROM_VIV"},
    "PRO_OCUP_C": {"2000": "PRO_OCVP"},
    "VPH_C_SERV": {"2005": "VPH_DREE", "2000": "VP_AGDREL"},
    "VPH_NDEAED": {"2005": "VPH_NADE", "2000": "VP_NOADE"},
    "VPH_TV": {"2000": "VP_TV"},
    "VPH_RADIO": {"2000": "VP_RADIO"},
    "VPH_TELEF": {"2000": "VP_TELEF"},
    "VPH_AUTOM": {"2000": "VP_AUTOM"},
    # 1995 and 1990 (their descriptors name some indicators differently)
    "POBMAS": {"1995": "POBTMAS", "1990": "HOMBRES"},
    "POBFEM": {"1995": "POBTFEM", "1990": "MUJERES"},
    "REL_H_M": {"1995": "IM"},                       # «Índice de masculinidad», ×100
    "VPH_C_ELEC": {"1995": "VIVP_ELEC", "1990": "C_E_ELECT"},
    "VPH_DRENAJ": {"1995": "VIVP_DREN", "1990": "C_DRENAJE"},
    "VPH_AGUADV": {"2000": "VP_AGUENT", "1995": "VIVP_AGUA", "1990": "C_AGUA_ENT"},
    "VPH_PISODT": {"1990": "PISO_TIE"},
    "VPH_1CUART": {"1990": "VIV_1_C"},
    # indicators of 2000 and older only (the 2000 or 2005 name is canonical)
    "P15_POSPRI": {"1990": "INS_PPRIM"},
    "VP_PARDES": {"1990": "PARED_LA"},
    "VP_TECDES": {"1990": "TECHO_LA"},
    "VP_2CUAR": {"1990": "VIV_2_C"},
    "VP_PROPIA": {"1990": "VIV_PPROP"},
    "P_6A14_AN": {"2000": "POB6_14"},
    "P_15A24": {"2000": "POB15_24"},
    "P_5_NOAE": {"2000": "P5_NAESC"},
    "P6A14NOA": {"2000": "P6_14NAESC"},
    "P_15A24A": {"2000": "P15_24AESC"},
}
# … and pairs that keep their own name (the same concept, another reference date,
# universe or definition: see _XW_NOTES).
_XW_PAIRS_KEPT: dict[str, dict[str, str]] = {
    **{f"PRES2015{s}": {"2010": f"PRES2005{s}"} for s in ("", "_F", "_M")},
    **{f"PRESOE15{s}": {"2010": f"PRESOE05{s}"} for s in ("", "_F", "_M")},
}
for _canon, _src in {"PRES2015": {"2005": "P_RE2000", "2000": "P5_RES95"},
                     "PRESOE15": {"2005": "P_OE2000", "2000": "P5_RESO95"},
                     "PRESOE15_M": {"2005": "P_M_OE2000"},
                     "PRESOE15_F": {"2005": "P_F_OE2000"},
                     "PDER_SEGP": {"2005": "P_SEGPOP"},
                     "PNACOE": {"2000": "PNACOENT"},
                     "PCATOLICA": {"2000": "P5_CATOLIC"},
                     "VPH_AGUADV": {"2005": "VPH_AGDV"},
                     "VPH_AGUAFV": {"2005": "VPH_NOAG"},
                     "VPH_EXCSA": {"2000": "VP_SERSAN"}}.items():
    _XW_PAIRS_KEPT.setdefault(_canon, {}).update(_src)
_XW_PAIRS: dict[str, dict[str, str]] = {
    c: {**_XW_PAIRS_RENAMED.get(c, {}), **_XW_PAIRS_KEPT.get(c, {})}
    for c in {**_XW_PAIRS_RENAMED, **_XW_PAIRS_KEPT}}
# … and the notes of the hand review (definition or wording changes between editions).
_SALUD = ("2010 y antes dicen «derechohabiencia», 2020 «afiliación» a servicios de salud (la "
          "misma pregunta)")
_JEFATURA = ("2000-2010 dicen «jefatura», 2020 «persona de referencia» del hogar (el mismo "
             "concepto)")
_RESIDENCIA = ("residencia cinco años antes: enero de 1995 (2000), octubre de 2000 (2005), junio "
               "de 2005 (2010), marzo de 2015 (2020); el mismo concepto con otra fecha, por eso no "
               "se renombra")
_XW_NOTES: dict[str, str] = {
    "TAMLOC": "la misma escala de 14 clases; 2010 la llama TAM_LOC (harmonize=True la renombra)",
    **{c: _SALUD for c in ("PDER_SS", "PDER_IMSS", "PDER_ISTE", "PDER_ISTEE", "PSINDER")},
    "PDER_SEGP": ("2005 y 2010: Seguro Popular (2010 incluye el Seguro Médico para una Nueva "
                  "Generación); 2020: Instituto de Salud para el Bienestar (INSABI) — programas "
                  "distintos"),
    **{c: _JEFATURA for c in ("HOGJEF_F", "HOGJEF_M", "PHOGJEF_F", "PHOGJEF_M")},
    "VPH_PC": "2020 incluye laptop o tablet; 2005 y 2010 sólo computadora",
    "PSIN_RELIG": "2020 incluye a la población sin adscripción religiosa (creyente)",
    **{c: _RESIDENCIA
       for c in ("PRES2015", "PRES2015_F", "PRES2015_M", "PRESOE15", "PRESOE15_F", "PRESOE15_M")},
    "PRESOE15": _RESIDENCIA + "; 2000 incluye a quien residía en otro país",
    **{c: ("2010 mide la limitación en la actividad con otra pregunta; sin equivalente en 2020 "
           "(PCON_DISC/PCON_LIMI/PSIND_LIM)")
       for c in ("PCON_LIM", "PCLIM_MOT", "PCLIM_LENG", "PCLIM_AUD", "PCLIM_MEN", "PCLIM_MEN2",
                 "PSIN_LIM")},
    **{c: ("el mismo nombre, otro concepto: 2010 cuenta a quien tiene dificultad; 2020 sólo a "
           "quien tiene poca (mucha dificultad o no poder es discapacidad, PCDISC_*)")
       for c in ("PCLIM_VIS", "PCLIM_MOT2")},
    "PNCATOLICA": ("2010: protestantes, evangélicas y bíblicas no evangélicas; 2020 agrupa de otro "
                   "modo (PRO_CRIEVA: protestante/cristiano evangélico) — sin equivalente exacto"),
    "PRO_CRIEVA": "2010 agrupa de otro modo (PNCATOLICA incluye las bíblicas no evangélicas)",
    "POTRAS_REL": ("el contenido depende de la agrupación de cada censo (PNCATOLICA 2010 / "
                   "PRO_CRIEVA 2020)"),
    "PCONDISC": ("2000: población con alguna limitación física o mental (otra pregunta); no se "
                 "empareja con PCON_DISC de 2020, que usa la escala de dificultad"),
    "PNACOE": "2000 (PNACOENT) incluye a la población nacida en otro país",
    "PCATOLICA": "2000 (P5_CATOLIC) cuenta sólo a la población de 5 años y más",
    "VPH_AGUADV": ("1990, 1995 y 2000 (VP_AGUENT): dentro de la vivienda o del terreno, como "
                   "en 2010 y 2020 (en el ámbito de la vivienda; renombradas; 2000: exacto en los "
                   "municipios que su muestra levantó completos); 2005 (VPH_AGDV): agua "
                   "entubada de la red pública — no se renombra"),
    "PROM_OCUP": ("ocupantes de viviendas particulares entre esas viviendas (OCUPVIVPAR / "
                  "VIVPAR_HAB) en todos los censos; 1990 (PROM_VIV) y 1995 (PRO_O_VP) truncan a "
                  "dos decimales. El descriptor de 1995 dice «población total entre el total de "
                  "viviendas», pero sus valores estatales y municipales son ese cociente"),
    "REL_H_M": "1995 lo llama índice de masculinidad (IM): hombres por cada cien mujeres",
    "VPH_AGUAFV": "2005 (VPH_NOAG): sin agua entubada de la red pública",
    "VPH_EXCSA": "2000 (VP_SERSAN): servicio sanitario exclusivo de la vivienda",
    "P15YM_SE": "2000 (P15_SINSTR) dice «sin instrucción»",
    "VP_CCUART": ("el diccionario dice «con un dormitorio», pero cuenta las viviendas con un solo "
                  "cuarto sin contar la cocina exclusiva (la regla de VP2_5CUAR); no se empareja con "
                  "VPH_1DOR"),
    "PHOG_IND": ("hogares donde habla lengua indígena la jefa(e) o su cónyuge (2005, 2010); 2020 "
                 "cuenta además a la madre o el padre y a la suegra(o) de la jefa(e) (exacto en "
                 "los municipios que su muestra levantó completos). 2005 dice «hogares "
                 "indígenas», 2010 y 2020 «hogares censales indígenas»"),
    "VPH_C_SERV": ("2000 y 2005: agua entubada, drenaje y energía eléctrica; la definición de "
                   "agua entubada cambia entre censos (VPH_AGUADV)"),
}
# Indicators present in both editions under the same name that measure different things.
_XW_NOT_COMPARABLE = frozenset({"PCLIM_VIS", "PCLIM_MOT2", "PDER_SEGP", "PHOG_IND"})


def _xw_norm(meta: dict) -> str:
    """An indicator's description folded for matching (case, accents, punctuation, spaces;
    «Po blación» → «poblacion», the 2000 dictionary's stray space)."""
    text = re.sub(r"[^a-z0-9 ]", " ", fd._fold(meta.get("Descripción") or ""))
    return " ".join(text.replace("po blacion", "poblacion").split())


def _edition_columns(schema_map: dict, table: str, period: str) -> list[str]:
    """The columns (upper case, in file order) of ``table`` in ``period``'s schema groups."""
    cols: list[str] = []
    for g in schema_map.get(table, {}).get("groups", {}).values():
        if period in g["periods"]:
            cols += [c.upper() for c in g["columns"] if c.upper() not in cols]
    return cols


def _write_crosswalk(dict_dir: Path, path: Path, map_path: Path = _DEFAULT_SCHEMA_MAP) -> dict:
    """(Re)write ``cpv_iter_crosswalk.yaml``: every ITER/AGEB column of the censuses in
    :data:`_XW_PERIODS` (from the schema map, i.e. the data), keyed by its canonical
    (newest) name, with each edition's source column — the same name when both editions
    have it, a hand-reviewed pair (:data:`_XW_PAIRS`) otherwise — the tables it appears in,
    ``Renombrar`` for the pairs ``harmonize=True`` renames, ``Comparable: false`` and the
    review's ``Nota``. Descriptions come from the indicator dictionaries fetched by
    ``--dictionary``."""
    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    docs = {}
    for p in _XW_PERIODS:
        for t in ("iter", "ageb"):
            dpath = _indicator_dict_path(dict_dir, p, t)
            if dpath.exists():
                docs[(p, t)] = {k.strip().upper(): v
                                for k, v in _indicator_doc(dpath, p).items()}
    paired = {(p, src): canon for canon, by in _XW_PAIRS.items() for p, src in by.items()}
    renamed = {(p, canon) for canon, by in _XW_PAIRS_RENAMED.items() for p in by}
    out: dict[str, dict] = {}
    by_desc: dict[str, list[str]] = defaultdict(list)       # newer editions' descriptions
    for period in _XW_PERIODS:                       # newest first: canonical names
        new_desc: dict[str, list[str]] = defaultdict(list)
        for table in ("iter", "ageb"):
            for name in _edition_columns(schema_map, table, period):
                meta = docs.get((period, table), {}).get(name) or {}
                canon = name if period == _XW_PERIODS[0] else paired.get((period, name), name)
                if (period in _XW_DESC_PERIODS and (period, name) not in paired
                        and (period, name) not in _XW_UNPAIR and canon not in out):
                    hits = [c for c in dict.fromkeys(by_desc.get(_xw_norm(meta), []))
                            if period not in out[c]]
                    if len(hits) == 1:               # the same description, another name
                        canon = hits[0]
                        renamed.add((period, canon))
                entry = out.setdefault(canon, {"Descripción": meta.get("Descripción", ""),
                                               "Tablas": []})
                if not entry["Descripción"]:
                    entry["Descripción"] = meta.get("Descripción", "")
                if table not in entry["Tablas"]:
                    entry["Tablas"].append(table)
                entry.setdefault(period, name)
                if meta.get("Descripción"):
                    new_desc[_xw_norm(meta)].append(canon)
        for key, canons in new_desc.items():
            by_desc[key] += canons
    for canon, entry in out.items():
        periods = [p for p in _XW_PERIODS if (p, canon) in renamed and entry.get(p, canon) != canon]
        if periods:
            entry["Renombrar"] = periods
        if canon in _XW_NOT_COMPARABLE:
            entry["Comparable"] = False
        if canon in _XW_NOTES:
            entry["Nota"] = _XW_NOTES[canon]
    header = ("# CPV census aggregates (ITER, AGEB) — indicator crosswalk across editions.\n"
              "# Generated by scripts/build_cpv.py --crosswalk from INEGI's indicator\n"
              "# dictionaries and the hand review in build_cpv._XW_*; do not\n"
              "# edit by hand. Key = canonical (newest edition's) mnemonic; '2000'…'2020' = the\n"
              "# column of that edition (upper case, as harmonize=True writes it; absent = the\n"
              "# edition has no such indicator); Renombrar = the editions whose spelling\n"
              "# harmonize=True renames onto the key; Comparable: false = the same name measures\n"
              "# another thing in each edition; Nota = a definition or wording change.\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, default_flow_style=False,
                       width=100)
    return out


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
    meta.add_argument("--crosswalk", action="store_true",
                      help="(Re)write cpv_iter_crosswalk.yaml from the ITER/AGEB dictionaries")
    meta.add_argument("--crosswalk-path", type=Path, default=_DEFAULT_CROSSWALK, metavar="FILE")
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
    if args.crosswalk:
        doc = _write_crosswalk(args.dict_dir, args.crosswalk_path, args.schema_map_path)
        print(f"Crosswalk → {args.crosswalk_path}  ({len(doc)} indicators)")
        return 0
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
                dropped = f", {info['deleted']} deleted record(s) dropped" if info["deleted"] else ""
                print(f"  {where}: {info['rows']:,} rows, {info['cols']} cols, "
                      f"enc={info['encoding']}, {info['size_kb'] / 1024:.1f} MB "
                      f"(peak RSS {info['peak_rss_mb']:,.0f} MB){dropped}", flush=True)
            else:
                failed += 1
                print(f"  ! {where}: {st.upper()} — {info.get('error') or info.get('member')}",
                      flush=True)
    print(f"\nDone: {written} file(s) written; {failed} table(s) failed/missing.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
