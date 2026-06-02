"""Build the DENUE geoparquet mirror from INEGI's bulk-download tree.

Maintainer-only — NOT part of the installed package.

Downloads DENUE per-release per-state CSV ZIPs (see ``_denue_catalog.py``),
converts each to GeoParquet (`denue_{YYYYMM}_{NN}.parquet`, point geometry from
latitud/longitud in EPSG:4326), and reports each file's schema fingerprint.

Step 1 scope: catalog discovery + dry run (download → verify → convert one
release/state, print diagnostics; no registry update). Fingerprinting across all
releases, the inconsistency report, schema grouping, harmonization, and the
registry append are added in later steps.

Dry run (one release, one state):
    uv run python scripts/build_denue.py --dry-run --release 202011 --states 9
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import zipfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
import pooch
import pyarrow.parquet as pq
import yaml

import _build_common as bc
from mxcensus.data._denue_catalog import (
    CATALOG_VERIFIED_DATE,
    RELEASES,
    RELEASES_BY_YYYYMM,
    denue_zip_entry,
)
from mxcensus.denue import (
    _CODE_OCU,
    _OCU_ALLOWED,
    _PER_OCU,
    _TIPO_UNI,
    _TIPO_UNI_ALLOWED,
    _TIPO_UNI_LABEL,
    _UPPER_OCU,
    _mnemonic_of,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_SCHEMA_MAP = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "denue_schema_map.yaml"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"

# Continental + insular Mexico bounding box (lon, lat). Coordinates outside this
# are treated as missing (DENUE has occasional 0,0 or transposed values).
_MX_BBOX = (-118.5, 14.3, -86.6, 32.8)  # minlon, minlat, maxlon, maxlat


def _fingerprint_cols(cols) -> str:
    """sha256 over the ordered column names — identifies a release schema.

    Column names (not dtypes) define the DENUE schema: dtypes are noisy across
    states (an all-empty column reads as float in one state, object in another),
    whereas the column set/order is the meaningful drift signal.
    """
    return sha256(json.dumps(list(cols)).encode()).hexdigest()


def _schema_fingerprint(df: pd.DataFrame) -> str:
    return _fingerprint_cols(df.columns)


def _scan_parquet(path: Path) -> dict:
    """Read one mirrored DENUE parquet's schema/metadata for the report (no full load)."""
    _, yyyymm, code = path.stem.split("_")  # denue_{YYYYMM}_{NN}
    pf = pq.ParquetFile(path)
    cols = [c for c in pf.schema_arrow.names if c != "geometry"]
    return {
        "release": yyyymm,
        "state": code,
        "columns": cols,
        "fingerprint": _fingerprint_cols(cols),
        "content_hash": pooch.file_hash(str(path)),
        "rows": pf.metadata.num_rows,
        "size_kb": path.stat().st_size // 1024,
    }


def _all_null_cols(path: Path) -> list[str]:
    """Return the names of columns that are entirely null in one mirrored parquet.

    Surfaces source data-quality gaps — e.g. the 2012 typo variant (group g04, states
    12/14) ships empty ``Entidad federativa``/``Municipio``/``nombre_act`` name columns
    while their numeric code columns are populated. Read fully (not metadata) since
    null-ness isn't in the schema.
    """
    df = pd.read_parquet(path)
    return [c for c in df.columns if c != "geometry" and df[c].isna().all()]


def _locate_data_csv(extract_dir: Path) -> Path:
    """Find the establishments CSV across DENUE layouts.

    Modern releases (2016+) nest it under ``conjunto_de_datos/``; older ones
    (2010–2015) put a flat ``DenueCSV{NN}.csv`` at the root with a PDF dictionary.
    Robust rule: the largest non-dictionary CSV, preferring conjunto_de_datos/.
    """
    csvs = [p for p in extract_dir.glob("**/*.csv")
            if "diccionario" not in p.name.lower()]
    preferred = [p for p in csvs if "conjunto_de_datos" in str(p.parent).lower()]
    candidates = preferred or csvs
    if not candidates:
        raise FileNotFoundError(f"No establishments CSV under {extract_dir}")
    return max(candidates, key=lambda p: p.stat().st_size)


def _sniff_encoding(csv_path: Path) -> str:
    """Choose the decoding that preserves the most of a DENUE CSV's accented text.

    DENUE files are a mix of clean UTF-8, UTF-8 with a few corrupt bytes, and Windows
    single-byte (cp1252/latin-1). The old "utf-8 → else cp1252 → else latin-1" rule
    mis-handled a UTF-8 file with even ONE invalid byte: utf-8 strict failed, so the
    whole file was decoded as cp1252, turning every valid ``más`` into ``mÃ¡s``
    (e.g. denue_201811_29 — 6 bad bytes corrupted ~104k cells).

    Discriminator: in a real UTF-8 file the high bytes (≥0x80) form valid multi-byte
    sequences, so utf-8/replace inserts almost no U+FFFD; in a single-byte file nearly
    every high byte is invalid as UTF-8, so replacements ≈ high-byte count. Compare the
    ratio. Returns one of ``"utf-8"`` (read strict) / ``"utf-8/replace"`` /
    ``"cp1252"`` / ``"latin-1"``.
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
    """Read a DENUE CSV with the encoding chosen by ``_sniff_encoding``.

    dtype=str: read every field as text. DENUE columns are categorical/text codes
    (codigo_act, per_ocu, cve_*, numero_ext "123"/"KM 5", …), not arithmetic, so this is
    faithful AND avoids mixed str/float object columns — within a file and across
    multipart concats — that pyarrow can't serialize. lat/lon are re-parsed to float in
    _df_to_geoparquet via pd.to_numeric. A structurally malformed CSV still slips through
    as garbage rows (flagged later by the schema fingerprint / validation sweep).
    """
    enc = _sniff_encoding(csv_path)
    read_enc, errors = (enc.split("/") + ["strict"])[:2]
    df = pd.read_csv(csv_path, encoding=read_enc, encoding_errors=errors,
                     dtype=str, low_memory=False)
    return df, enc


def _read_part(
    entry, raw_dir: Path, cache_dir: Path, retries: int
) -> tuple[pd.DataFrame, str, Path]:
    """Download+verify+extract one ZIP entry and read its establishments CSV.

    Returns (dataframe, encoding, extract_dir) — the caller deletes extract_dir
    after conversion to bound disk use across the full multi-GB sweep.
    """
    # Cache under a release-qualified name: 2013_JULIO and 2013_OCTUBRE both serve a
    # file literally named denue_{NN}_2013_csv.zip, so a basename-only cache key makes
    # the second release silently reuse the first's download. Prefix with the folder
    # segment (e.g. "2013_OCTUBRE_denue_09_2013_csv.zip") to keep them distinct.
    folder, fname = entry.url.rstrip("/").rsplit("/", 2)[-2:]
    zip_name = f"{folder}_{fname}"
    extract_dir = raw_dir / entry.extract_dir
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bc.fetch_zip_verified(entry.url, cache_dir, zip_name, retries)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    csv_path = _locate_data_csv(extract_dir)
    df, enc = _read_csv_robust(csv_path)
    return df, enc, extract_dir


def _df_to_geoparquet(df: pd.DataFrame, parquet_path: Path) -> dict:
    """Write a DENUE DataFrame to GeoParquet (EPSG:4326); return diagnostics.

    Invalid/out-of-Mexico-bbox coordinates become **null** geometry (not empty points).
    Transposed coordinates are recovered: INEGI swapped the Latitud/Longitud columns in
    some files (e.g. 2012 state 14 — all 307k rows), so when a row is out-of-bbox as
    (lon, lat) but in-bbox as (lat, lon), the pair is swapped before building the point.
    """
    fingerprint = _schema_fingerprint(df)
    n_swapped = 0
    # lat/lon column names vary by release era ("latitud" vs "Latitud"); match
    # case-insensitively and tolerate their absence (→ all-null geometry).
    colmap = {c.lower(): c for c in df.columns}
    lat_c, lon_c = colmap.get("latitud"), colmap.get("longitud")
    if lat_c is not None and lon_c is not None:
        lon = pd.to_numeric(df[lon_c], errors="coerce")
        lat = pd.to_numeric(df[lat_c], errors="coerce")
        minlon, minlat, maxlon, maxlat = _MX_BBOX
        direct = lon.between(minlon, maxlon) & lat.between(minlat, maxlat)
        swapped = lat.between(minlon, maxlon) & lon.between(minlat, maxlat)
        use_swap = ~direct & swapped  # the named lat is really a lon, and vice versa
        n_swapped = int(use_swap.sum())
        if n_swapped:
            lon, lat = lon.where(~use_swap, lat), lat.where(~use_swap, lon)
        valid = (direct | swapped).to_numpy()
        geometry = gpd.points_from_xy(lon, lat, crs="EPSG:4326")
    else:
        valid = pd.Series(False, index=df.index).to_numpy()
        geometry = gpd.GeoSeries([None] * len(df), crs="EPSG:4326").values

    # Multipart concat can leave an object column mixing str + float NaN (e.g.
    # numero_ext: text in one part, all-empty→float in another), which pyarrow
    # refuses to write. Replace NaN with None so it serializes as a string column.
    for col in df.columns[df.dtypes == object]:
        df[col] = df[col].where(df[col].notna(), None)

    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    gdf.loc[~valid, "geometry"] = None  # invalid coords → null geometry
    gdf.to_parquet(parquet_path, compression="zstd")
    return {
        "rows": len(gdf),
        "cols": df.shape[1],
        "columns": list(df.columns),
        "fingerprint": fingerprint,
        "has_coords": lat_c is not None and lon_c is not None,
        "geom_null_frac": round(float((~valid).mean()), 4),
        "n_swapped": n_swapped,
        "size_kb": parquet_path.stat().st_size // 1024,
    }


def _build_denue_state(
    yyyymm: str, state: int, raw_dir: Path, cache_dir: Path, out_dir: Path,
    retries: int, cleanup_raw: bool = True,
) -> dict:
    """Download, verify, extract, concat parts and convert one release/state."""
    release = RELEASES_BY_YYYYMM[yyyymm]
    entries = denue_zip_entry(release, state)  # >1 for multipart states (e.g. 15)
    frames, encs, extract_dirs = [], [], []
    for entry in entries:
        df, enc, edir = _read_part(entry, raw_dir, cache_dir, retries)
        frames.append(df)
        encs.append(enc)
        extract_dirs.append(edir)
    if len(frames) > 1:
        # Multipart parts (state 15) sometimes ship the SAME columns in different
        # case (e.g. 2018-03: part1 lowercase, part2 UPPERCASE). Align later parts
        # to the first part's names case-insensitively, else pd.concat unions them
        # into a doubled, half-empty column set.
        canon = {c.lower(): c for c in frames[0].columns}
        frames = [frames[0]] + [
            fr.rename(columns={c: canon.get(c.lower(), c) for c in fr.columns})
            for fr in frames[1:]
        ]
        df = pd.concat(frames, ignore_index=True)
    else:
        df = frames[0]

    code = f"{state:02d}"
    out_path = out_dir / f"denue_{yyyymm}_{code}.parquet"
    info = _df_to_geoparquet(df, out_path)
    info["file"] = out_path.name
    info["release"] = yyyymm
    info["state"] = code
    info["encoding"] = encs[0] if len(set(encs)) == 1 else "/".join(encs)
    info["parts"] = len(entries)
    info["content_hash"] = pooch.file_hash(str(out_path))

    if cleanup_raw:  # bound disk use: drop extracted CSVs once converted
        for edir in extract_dirs:
            shutil.rmtree(edir, ignore_errors=True)
    return info


def _write_report(out_dir: Path, report_path: Path) -> dict:
    """Scan every mirrored DENUE parquet on disk and (re)write the markdown report.

    Decoupled from any single conversion run, so targeted recovery runs produce
    the complete picture. Returns the fingerprint→schema_id mapping (used by Step 3).
    """
    records = [_scan_parquet(p) for p in sorted(out_dir.glob("denue_*.parquet"))]
    releases = sorted({r["release"] for r in records})

    # Missing files: per attempted release, which of states 1..32 are absent.
    present: dict[str, set] = defaultdict(set)
    for r in records:
        present[r["release"]].add(int(r["state"]))
    missing = [(rel.yyyymm, sorted(set(range(1, 33)) - present[rel.yyyymm]))
               for rel in RELEASES
               if rel.yyyymm in present and set(range(1, 33)) - present[rel.yyyymm]]

    # Canonical columns/fingerprint per release + within-release agreement check.
    per_release: dict[str, dict] = {}
    disagreements: list[str] = []
    for yyyymm in releases:
        recs = [r for r in records if r["release"] == yyyymm]
        fps = {r["fingerprint"] for r in recs}
        if len(fps) > 1:
            disagreements.append(f"{yyyymm}: {len(fps)} distinct schemas across states")
        canonical = min(recs, key=lambda r: r["state"])
        per_release[yyyymm] = {
            "fingerprint": canonical["fingerprint"],
            "columns": canonical["columns"],
            "states": len(recs),
            "rows": sum(r["rows"] for r in recs),
            "size_kb": sum(r["size_kb"] for r in recs),
        }

    # Schema groups: stable g01.. assigned per *file* (sorted by release, then state),
    # matching denue_schema_map.yaml — so minority within-release schemas (e.g. the
    # 2012 typo variant in states 12/14) get their own group rather than being hidden
    # behind a release's lowest-state canonical file.
    fp_to_id: dict[str, str] = {}
    fp_cols: dict[str, list] = {}
    rels_per_fp: dict[str, set] = defaultdict(set)
    files_per_fp: dict[str, int] = defaultdict(int)
    for r in sorted(records, key=lambda r: (r["release"], r["state"])):
        fp = r["fingerprint"]
        if fp not in fp_to_id:
            fp_to_id[fp] = f"g{len(fp_to_id) + 1:02d}"
            fp_cols[fp] = r["columns"]
        rels_per_fp[fp].add(r["release"])
        files_per_fp[fp] += 1

    # Duplicate detection: identical output content across (release, state). Reliable
    # within a single build (all files written by the same pyarrow, whose version
    # string is embedded in the footer); do NOT compare these hashes against a
    # registry produced by a different pyarrow version — identical input would hash
    # differently. The genuine same-CSV duplicates this catches are intra-run.
    by_hash: dict[str, list[str]] = {}
    for r in records:
        by_hash.setdefault(r["content_hash"], []).append(f"{r['release']}/{r['state']}")
    dups = {h: v for h, v in by_hash.items() if len(v) > 1}

    n_missing = sum(len(g) for _, g in missing)
    L = ["# DENUE inconsistency report", "",
         f"Generated by `scripts/build_denue.py` (catalog verified {CATALOG_VERIFIED_DATE}).",
         f"Releases: {len(releases)}. Files mirrored: {len(records)}. "
         f"Missing (expected but absent): {n_missing}.", ""]

    L += ["## 1. Release inventory", "",
          "| release | label | schema | states | rows | size (MB) |",
          "|---|---|---|---|---|---|"]
    for yyyymm in releases:
        p = per_release[yyyymm]
        label = RELEASES_BY_YYYYMM[yyyymm].label
        L.append(f"| {yyyymm} | {label} | {fp_to_id[p['fingerprint']]} | {p['states']} "
                 f"| {p['rows']:,} | {p['size_kb'] / 1024:.1f} |")

    L += ["", "## 2. Schema groups", ""]
    for fp, sid in fp_to_id.items():
        cols = fp_cols[fp]
        rels = sorted(rels_per_fp[fp])
        L.append(f"### {sid} — {len(cols)} columns, {files_per_fp[fp]} file(s) "
                 f"(releases: {', '.join(rels)})")
        L.append("`" + ", ".join(cols) + "`")
        L.append("")

    L += ["## 3. Schema drift", ""]
    latest = releases[-1]
    for prev, cur in zip(releases, releases[1:]):
        a, b = set(per_release[prev]["columns"]), set(per_release[cur]["columns"])
        added, removed = sorted(b - a), sorted(a - b)
        if added or removed:
            L.append(f"### {prev} → {cur}")
            if added:
                L.append(f"- added: {added}")
            if removed:
                L.append(f"- removed: {removed}")
            L.append("")
    for yyyymm in releases[:-1]:
        a, b = set(per_release[yyyymm]["columns"]), set(per_release[latest]["columns"])
        miss, extra = sorted(b - a), sorted(a - b)
        if miss or extra:
            L.append(f"### {yyyymm} vs latest {latest}")
            if miss:
                L.append(f"- missing (in latest, absent here → add_null): {miss}")
            if extra:
                L.append(f"- extra (here, dropped in latest): {extra}")
            L.append("")

    L += ["## 4. Duplicate files (identical content)", ""]
    L += [f"- `{h[:12]}…`: {', '.join(v)}" for h, v in dups.items()] or ["None detected."]

    L += ["", "## 5. Missing files (expected but absent from the mirror)", ""]
    L += [f"- {rel}: states {gap}" for rel, gap in missing] or ["None."]

    L += ["", "## 6. Within-release schema disagreements", ""]
    L += [f"- {d}" for d in disagreements] or ["None."]

    # Representative file per schema group (earliest release, lowest state) → its
    # all-null columns. Flags source name-fields that are empty even though their
    # code counterpart is populated (e.g. g04's Entidad federativa/Municipio).
    rep_path: dict[str, Path] = {}
    for p in sorted(out_dir.glob("denue_*.parquet")):
        _, rel, code = p.stem.split("_")
        cols = [c for c in pq.ParquetFile(p).schema_arrow.names if c != "geometry"]
        gid = fp_to_id[_fingerprint_cols(cols)]
        if gid not in rep_path:
            rep_path[gid] = p
    L += ["", "## 7. Empty columns by schema group "
          "(all-null in the group's representative file)", ""]
    empties = []
    for gid in sorted(rep_path):
        nulls = _all_null_cols(rep_path[gid])
        if nulls:
            empties.append(f"- {gid} (`{rep_path[gid].name}`): {nulls}")
    L += empties or ["None — every column populated in all representative files."]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return fp_to_id


def _decode(raw: bytes) -> str:
    """Decode INEGI dictionary bytes (cp1252 → utf-8 → latin-1 fallback)."""
    for enc in ("cp1252", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


_CODE_RE = re.compile(r"(\d+)\s*=\s*([^\n;=]+?)(?=\s*\d+\s*=|\s*$)", re.MULTILINE)


def _parse_codes(text: str) -> dict:
    """Pull a ``code = label`` table out of a dictionary description cell / PDF window."""
    return {m.group(1): " ".join(m.group(2).split()).rstrip(".")
            for m in _CODE_RE.finditer(text)}


def _parse_dict_csv(raw: bytes) -> dict:
    """Parse a CSV data dictionary (2016+) → {'fields': {...}, 'codes': {field: {code:label}}}.

    ``fields`` is keyed by attribute name verbatim AND lowercased (uppercase-era files
    look up case-insensitively). ``codes`` holds any ``code = label`` table embedded in a
    description (e.g. ``per_ocu`` "1 = 0 a 5 … 7 = 251 y más").
    """
    text = _decode(raw)
    lines = text.splitlines()
    hdr = next((i for i, ln in enumerate(lines) if "Atributo en csv" in ln), None)
    if hdr is None:
        return {"fields": {}, "codes": {}}
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), dtype=str)
    cols = {c.strip(): c for c in df.columns}
    name_c = cols.get("Nombre del Atributo en csv")
    if not name_c:
        return {"fields": {}, "codes": {}}
    fields, codes = {}, {}
    for _, r in df.iterrows():
        n = str(r[name_c]).strip()
        if not n or n == "nan":
            continue
        desc = " ".join(str(r.get(cols.get("Descripción", ""), "") or "").split())
        meta = {
            "Tipo": str(r.get(cols.get("Tipo de dato", ""), "") or "").strip(),
            "Longitud": str(r.get(cols.get("Longitud", ""), "") or "").strip(),
            "Descripción": desc,
        }
        fields[n] = fields[n.lower()] = meta
        ct = _parse_codes(desc)
        if ct:
            codes[n.lower()] = ct
    return {"fields": fields, "codes": codes}


# PDF field row: "<Nombre> <mnemónico> <tipo> <longitud> <descripción…>" (run-together).
_PDF_FIELD_RE = re.compile(
    r"([A-Za-zÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .,/()-]+?)\s+([a-z_][a-z0-9_]+)\s+"
    r"(alfanumérico|numérico|fecha)\s+([\d/]+)\s+(.+?)"
    r"(?=[A-Za-zÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .,/()-]+?\s+[a-z_][a-z0-9_]+\s+"
    r"(?:alfanumérico|numérico|fecha)\s+[\d/]+\s+|$)",
    re.DOTALL,
)


def _parse_dict_pdf(raw: bytes) -> dict:
    """Best-effort parse of a PDF data dictionary (2010–2013) → {'fields','codes'}.

    Keys ``fields`` by both the display name and the mnemónico (lowercased). Descriptions
    are noisy (PDF text is run-together) but usable; ``codes`` captures embedded
    ``code = label`` tables (e.g. ``tipo_estab`` "1 y 3 = …fijo, 2 = …semifijo").
    """
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
    text = re.sub(r"[ \t]+", " ", text)
    fields, codes = {}, {}
    for m in _PDF_FIELD_RE.finditer(text):
        name, mnem, tipo, longitud, desc = (g.strip() for g in m.groups())
        desc = " ".join(desc.split())
        meta = {"Tipo": tipo, "Longitud": longitud, "Descripción": desc}
        fields[name] = fields[name.lower()] = fields[mnem.lower()] = meta
        ct = _parse_codes(desc)
        if ct:
            codes[mnem.lower()] = ct
    return {"fields": fields, "codes": codes}


def _extract_dictionary(zip_path: Path) -> dict:
    """Return the bundled dictionary as {'fields','codes'}; CSV preferred, else PDF, else {}."""
    if not zip_path.exists():
        return {"fields": {}, "codes": {}}
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        csv = [n for n in names if "diccionario" in n.lower() and n.lower().endswith(".csv")]
        if csv:
            return _parse_dict_csv(zf.read(csv[0]))
        pdf = [n for n in names if "diccionario" in n.lower() and n.lower().endswith(".pdf")]
        if pdf:
            return _parse_dict_pdf(zf.read(pdf[0]))
    return {"fields": {}, "codes": {}}


def _zip_name_for(rel: str, code: str) -> str:
    """Release-qualified cache filename for a (release, state) dictionary zip."""
    entry = denue_zip_entry(RELEASES_BY_YYYYMM[rel], int(code))[0]
    folder, fname = entry.url.rstrip("/").rsplit("/", 2)[-2:]
    return f"{folder}_{fname}"


def _canonical_mnemonic_dict(cache_dir: Path) -> dict:
    """`mnemonic → {Descripción,Tipo,Longitud}` from the latest release's CSV dictionary."""
    latest = max(RELEASES, key=lambda r: r.yyyymm)
    d = _extract_dictionary(cache_dir / _zip_name_for(latest.yyyymm, "01"))
    return d["fields"]


# Dictionary-grounded label maps (the catalogs in denue.py are themselves derived from the
# INEGI dictionaries). per_ocu accepts UPPERCASE labels, numeric codes, or the labels
# themselves; tipoUniEco accepts codes/UPPERCASE/labels.
_LABELS_OCU = {**_UPPER_OCU, **_CODE_OCU, **{x: x for x in _OCU_ALLOWED}}
_LABELS_TIPO = {**_TIPO_UNI_LABEL, **{x: x for x in _TIPO_UNI_ALLOWED}}

# Mnemonics validated by regex/date/numeric in the schema → never enumerated as categories.
_CAT_EXCLUDE = {"fecha_alta", "codigo_act", "cod_postal", "ageb", "manzana", "latitud",
                "longitud", "id", "clee", "telefono", "correoelec", "www",
                "numero_ext", "numero_int", "num_local"}


def _build_categories(gid: str, paths: list[Path], threshold: int) -> tuple[dict, list]:
    """Build `{column: {raw_value: label}}` for a group, cross-validated against data.

    Distinct values are enumerated across ALL of the group's files (column-projected
    reads; a column is dropped once it exceeds ``threshold``; high-cardinality / coded
    columns are excluded up front). The per_ocu and tipoUniEco *source* columns are
    labelled via the dictionary-grounded catalogs (``_LABELS_OCU`` / ``_LABELS_TIPO``) and
    any observed value with no catalog entry is flagged; every other categorical maps to
    itself (data is the only source). Returns (categorías, audit_rows).
    """
    cols = [c for c in pq.ParquetFile(paths[0]).schema_arrow.names if c != "geometry"]
    candidates = {c for c in cols if _mnemonic_of(gid, c) not in _CAT_EXCLUDE}
    seen: dict[str, set] = {c: set() for c in candidates}
    for p in paths:
        if not candidates:
            break
        present = [c for c in candidates if c in pq.ParquetFile(p).schema_arrow.names]
        df = pd.read_parquet(p, columns=present)
        for c in present:
            seen[c].update(str(v) for v in df[c].dropna().unique())
            if len(seen[c]) > threshold:
                candidates.discard(c)
                seen[c] = None  # high-cardinality → not a category column

    per_ocu_src = _PER_OCU.get(gid, (None,))[0]
    tipo_src, tipo_vmap = _TIPO_UNI.get(gid, (None, None))
    cats, audit = {}, []
    for col, values in seen.items():
        if values is None:
            continue
        if col == per_ocu_src:
            label_map, kind = _LABELS_OCU, "per_ocu"
        elif col == tipo_src and tipo_vmap is not None:
            label_map, kind = _LABELS_TIPO, "tipoUniEco"
        else:
            cats[col] = {v: v for v in sorted(values)}  # data-only categorical
            continue
        mapping, unmatched = {}, []
        for v in sorted(values):
            lbl = label_map.get(v)
            mapping[v] = lbl if lbl is not None else v
            if lbl is None:
                unmatched.append(v)
        cats[col] = mapping
        # Only flag observed values with no catalog entry (real anomalies). "Catalog
        # entries unseen" is uninformative here — the catalog unions all eras' encodings
        # (codes + UPPERCASE + labels), so each single-era group legitimately uses one.
        if unmatched:
            audit.append((gid, col, kind, unmatched))
    return cats, audit


def _write_variables_yaml(out_dir: Path, cache_dir: Path, yaml_dir: Path,
                          map_path: Path, threshold: int = 64) -> int:
    """Write one variables_denue_<gNN>.yaml per schema group + a CATEGORY_AUDIT.md.

    Descripción/Tipo/Longitud come from the group's own-era dictionary (CSV or PDF), then
    the canonical latest dictionary keyed by mnemonic, then blank. Categorías come from the
    dictionary code tables (per_ocu, tipoUniEco), cross-validated against the actual data;
    catalog-less categoricals fall back to the distinct data values (≤ threshold).
    """
    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    fp_to_id = schema_map["fingerprints"]
    # all files per group, and the representative (earliest release, lowest state)
    paths_by_gid: dict[str, list[Path]] = defaultdict(list)
    rep: dict[str, dict] = {}
    for p in sorted(out_dir.glob("denue_*.parquet")):
        _, rel, code = p.stem.split("_")
        cols = [c for c in pq.ParquetFile(p).schema_arrow.names if c != "geometry"]
        gid = fp_to_id[_fingerprint_cols(cols)]
        paths_by_gid[gid].append(p)
        if gid not in rep or (rel, code) < (rep[gid]["rel"], rep[gid]["code"]):
            rep[gid] = {"rel": rel, "code": code, "cols": cols}

    canon = _canonical_mnemonic_dict(cache_dir)
    yaml_dir.mkdir(parents=True, exist_ok=True)
    audit_all = []
    for gid, info in sorted(rep.items()):
        own = _extract_dictionary(cache_dir / _zip_name_for(info["rel"], info["code"]))
        ofields = own["fields"]
        cats, audit = _build_categories(gid, paths_by_gid[gid], threshold)
        audit_all += audit

        doc = {}
        for col in info["cols"]:
            mn = _mnemonic_of(gid, col)
            meta = ofields.get(col) or ofields.get(col.lower()) \
                or canon.get(mn) or canon.get(mn.lower()) or {}
            doc[col] = {
                "Descripción": meta.get("Descripción", ""),
                "Tipo": meta.get("Tipo", ""),
                "Longitud": meta.get("Longitud", ""),
                "Categorías": cats.get(col, {}),
            }
        path = yaml_dir / f"variables_denue_{gid}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True,
                           default_flow_style=False)

    _write_category_audit(audit_all, _REPO_ROOT / "docs" / "denue" / "CATEGORY_AUDIT.md")
    return len(rep)


def _write_category_audit(rows: list, report_path: Path) -> None:
    """Write the observed-vs-dictionary category discrepancy report.

    Lists coded-field (`per_ocu`, `tipoUniEco`) data values that don't map to the
    dictionary-grounded catalog — genuine anomalies (e.g. mojibake, a misaligned row).
    """
    L = ["# DENUE category audit", "",
         "Coded-field values found in the data with no dictionary-catalog entry "
         "(per_ocu, tipoUniEco). Empty = every observed value maps cleanly.", ""]
    if not rows:
        L.append("No discrepancies — every observed coded value maps to a catalog entry.")
    for gid, col, kind, unmatched in sorted(rows):
        L.append(f"## {gid} — `{col}` ({kind})")
        L.append(f"- observed but not in catalog: {unmatched}")
        L.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")


def _write_schema_map(out_dir: Path, map_path: Path) -> dict:
    """Group every mirrored file by its exact schema and write denue_schema_map.yaml.

    Groups are per (release, state) — a file's column-list fingerprint determines its
    group — so within-release disagreements (e.g. the 4 states already on the mnemonic
    schema in Feb-2015) land in their true group. The loader matches a file by computing
    the same fingerprint, so no per-file table is needed in the map. ``latest`` is the
    schema of the most recent release's majority of states (the harmonization target).
    """
    records = [_scan_parquet(p) for p in sorted(out_dir.glob("denue_*.parquet"))]

    fp_to_id: dict[str, str] = {}
    fp_cols: dict[str, list] = {}
    for r in sorted(records, key=lambda r: (r["release"], r["state"])):
        if r["fingerprint"] not in fp_to_id:
            fp_to_id[r["fingerprint"]] = f"g{len(fp_to_id) + 1:02d}"
            fp_cols[r["fingerprint"]] = r["columns"]

    files_per_fp: dict[str, int] = defaultdict(int)
    rels_per_fp: dict[str, set] = defaultdict(set)
    for r in records:
        files_per_fp[r["fingerprint"]] += 1
        rels_per_fp[r["fingerprint"]].add(r["release"])

    latest_release = max(r["release"] for r in records)
    latest_counts: dict[str, int] = defaultdict(int)
    for r in records:
        if r["release"] == latest_release:
            latest_counts[r["fingerprint"]] += 1
    latest_fp = max(latest_counts, key=latest_counts.get)

    groups = {
        fp_to_id[fp]: {
            "n_columns": len(fp_cols[fp]),
            "files": files_per_fp[fp],
            "releases": sorted(rels_per_fp[fp]),
            "columns": fp_cols[fp],
        }
        for fp in fp_to_id
    }
    doc = {
        "latest": fp_to_id[latest_fp],
        "fingerprints": dict(fp_to_id),
        "groups": dict(sorted(groups.items())),
    }
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return doc


def _write_validation_report(out_dir: Path, report_path: Path) -> tuple[int, int]:
    """Validate every mirrored parquet against its tight group schema; write a report.

    Loads each file, resolves its group by fingerprint, validates the raw frame against
    ``_group_schema(gid)`` with ``lazy=True`` (collect ALL failures), and writes per-file
    PASS/FAIL with a (column, check) → count + example breakdown. This is the authoritative
    sweep for current + future releases (the loader only warns). Returns (n_files, n_fail).
    """
    from mxcensus.denue import _fingerprint, _group_schema
    schema_map = yaml.safe_load(_DEFAULT_SCHEMA_MAP.read_text(encoding="utf-8"))
    fps = schema_map["fingerprints"]
    files = sorted(out_dir.glob("denue_*.parquet"))
    results = []
    for p in files:
        cols = [c for c in pq.ParquetFile(p).schema_arrow.names if c != "geometry"]
        gid = fps.get(_fingerprint(cols))
        if gid is None:
            results.append((p.name, "?", "UNKNOWN-SCHEMA", []))
            continue
        gdf = gpd.read_parquet(p)
        try:
            _group_schema(gid).validate(gdf.drop(columns="geometry"), lazy=True)
            results.append((p.name, gid, "PASS", []))
        except pa.errors.SchemaErrors as exc:
            fc = exc.failure_cases
            grp = (fc.groupby(["column", "check"])
                     .agg(count=("failure_case", "size"),
                          example=("failure_case", "first"))
                     .reset_index().sort_values("count", ascending=False))
            results.append((p.name, gid, "FAIL", grp.to_dict("records")))

    failed = [r for r in results if r[2] != "PASS"]
    L = ["# DENUE validation report", "",
         f"Each mirrored file validated against its group's tight schema "
         f"(`_group_schema`). Files: {len(files)}. Failing: {len(failed)}.", ""]
    if not failed:
        L.append("All files pass their group schema.")
    for name, gid, status, fails in failed:
        L.append(f"## {name} ({gid}) — {status}")
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
    parser.add_argument("--releases", nargs="+", default=sorted(RELEASES_BY_YYYYMM),
                        metavar="YYYYMM", help="Release ids (default: all)")
    parser.add_argument("--states", nargs="+", type=int, default=list(range(1, 33)),
                        metavar="N", help="State codes (default: all 32)")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR")
    parser.add_argument("--report", type=Path,
                        default=_REPO_ROOT / "docs" / "denue" / "INCONSISTENCY_REPORT.md",
                        metavar="FILE")
    parser.add_argument("--retries", type=int, default=2, metavar="N")
    parser.add_argument("--keep-raw", dest="cleanup_raw", action="store_false",
                        help="Keep extracted CSVs (default: delete after conversion)")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip downloading; rebuild the report from parquet on disk")
    parser.add_argument("--schema-map", action="store_true",
                        help="Skip downloading; (re)write denue_schema_map.yaml from parquet on disk")
    parser.add_argument("--schema-map-path", type=Path, default=_DEFAULT_SCHEMA_MAP, metavar="FILE")
    parser.add_argument("--variables", action="store_true",
                        help="Skip downloading; write per-group variables_denue_<gNN>.yaml")
    parser.add_argument("--cat-threshold", type=int, default=64, metavar="N",
                        help="Max distinct values for a column to be enumerated as a category")
    parser.add_argument("--yaml-dir", type=Path, default=_DEFAULT_SCHEMA_MAP.parent, metavar="DIR")
    parser.add_argument("--validate", action="store_true",
                        help="Skip downloading; validate every parquet against its group schema")
    parser.add_argument("--validate-report", type=Path,
                        default=_REPO_ROOT / "docs" / "denue" / "VALIDATION_REPORT.md",
                        metavar="FILE")
    parser.add_argument("--update-registry", action="store_true",
                        help="Skip downloading; append denue_* hashes to registry.txt (preserving prior)")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print per-file diagnostics only; skip the report")
    parser.set_defaults(cleanup_raw=True)
    args = parser.parse_args()

    unknown = [r for r in args.releases if r not in RELEASES_BY_YYYYMM]
    if unknown:
        parser.error(f"unknown releases {unknown}; known: {sorted(RELEASES_BY_YYYYMM)}")

    args.output.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        fp_to_id = _write_report(args.output, args.report)
        print(f"Report → {args.report}  ({len(fp_to_id)} schema group(s))")
        return

    if args.schema_map:
        doc = _write_schema_map(args.output, args.schema_map_path)
        print(f"Schema map → {args.schema_map_path}  ({len(doc['groups'])} groups, "
              f"latest={doc['latest']})")
        return

    if args.variables:
        n = _write_variables_yaml(args.output, args.cache_dir, args.yaml_dir,
                                  args.schema_map_path, args.cat_threshold)
        print(f"Wrote {n} variables_denue_<gNN>.yaml → {args.yaml_dir}")
        return

    if args.validate:
        n_files, n_fail = _write_validation_report(args.output, args.validate_report)
        print(f"Validation report → {args.validate_report}  "
              f"({n_fail}/{n_files} file(s) failed their group schema)")
        return

    if args.update_registry:
        written = sorted(args.output.glob("denue_*.parquet"))
        bc.update_registry(written, args.registry)
        return

    print(f"Catalog verified {CATALOG_VERIFIED_DATE}; "
          f"{len(args.releases)} release(s) × {len(args.states)} state(s)")
    failed = 0
    for yyyymm in sorted(args.releases):
        for state in args.states:
            tag = f"{yyyymm}/{state:02d}"
            try:
                info = _build_denue_state(
                    yyyymm, state, args.raw_dir, args.cache_dir, args.output,
                    args.retries, args.cleanup_raw
                )
                print(f"  {tag}: {info['rows']:,} rows, {info['cols']} cols, "
                      f"fp={info['fingerprint'][:8]}, geomnull={info['geom_null_frac']}, "
                      f"swapped={info['n_swapped']}, parts={info['parts']}")
            except Exception as exc:  # malformed: report, don't abort the sweep
                failed += 1
                print(f"  ! {tag}: MALFORMED — {type(exc).__name__}: {exc}")

    if args.dry_run:
        print(f"\n[dry-run] {failed} failed; no report written.")
        return

    fp_to_id = _write_report(args.output, args.report)
    print(f"\nReport → {args.report}  ({len(fp_to_id)} schema group(s); "
          f"{failed} file(s) failed this run)")


if __name__ == "__main__":
    main()
