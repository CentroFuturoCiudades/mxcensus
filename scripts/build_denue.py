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
import json
import shutil
import zipfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import geopandas as gpd
import pandas as pd
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


def _read_csv_robust(csv_path: Path) -> tuple[pd.DataFrame, str]:
    """Read a DENUE CSV as utf-8, else cp1252 (the INEGI Windows encoding).

    chardet mis-guesses some files (cp850/cp1250 → mojibake), so we don't trust it:
    try utf-8 first (rare), then cp1252, which decodes every DENUE byte cleanly.
    """
    # dtype=str: read every field as text. DENUE columns are categorical/text codes
    # (codigo_act, per_ocu, cve_*, numero_ext "123"/"KM 5", …), not arithmetic, so
    # this is faithful AND avoids mixed str/float object columns — both within a file
    # and when concatenating multipart states — that pyarrow can't serialize.
    # lat/lon are re-parsed to float in _df_to_geoparquet via pd.to_numeric.
    for enc in ("utf-8", "cp1252"):
        try:
            return pd.read_csv(csv_path, encoding=enc, dtype=str, low_memory=False), enc
        except UnicodeDecodeError:
            continue
    # latin-1 decodes any byte, so it never raises UnicodeDecodeError: a structurally
    # malformed CSV slips through as garbage rows rather than failing here. Such a file
    # gets an unrecognised column fingerprint and is rejected loudly at load_denue time
    # (and flagged by the within-release disagreement check in the report).
    return pd.read_csv(csv_path, encoding="latin-1", dtype=str, low_memory=False), "latin-1"


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
    """
    fingerprint = _schema_fingerprint(df)
    # lat/lon column names vary by release era ("latitud" vs "Latitud"); match
    # case-insensitively and tolerate their absence (→ all-null geometry).
    colmap = {c.lower(): c for c in df.columns}
    lat_c, lon_c = colmap.get("latitud"), colmap.get("longitud")
    if lat_c is not None and lon_c is not None:
        lon = pd.to_numeric(df[lon_c], errors="coerce")
        lat = pd.to_numeric(df[lat_c], errors="coerce")
        minlon, minlat, maxlon, maxlat = _MX_BBOX
        valid = (lon.between(minlon, maxlon) & lat.between(minlat, maxlat)).to_numpy()
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


def _extract_dict_csv(zip_path: Path) -> dict:
    """Parse a release's bundled data dictionary → {csv_col: {Tipo, Longitud, Descripción}}.

    Returns {} when no parseable CSV dictionary is present (2010 ships a PDF).
    """
    import io
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist()
                 if "diccionario" in n.lower() and n.lower().endswith(".csv")]
        if not names:
            return {}
        raw = zf.read(names[0])
    text = next((raw.decode(e) for e in ("cp1252", "utf-8")
                 if _safe_decode(raw, e)), raw.decode("latin-1"))
    lines = text.splitlines()
    hdr = next((i for i, ln in enumerate(lines) if "Atributo en csv" in ln), None)
    if hdr is None:
        return {}
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), dtype=str)
    cols = {c.strip(): c for c in df.columns}
    name_c = cols.get("Nombre del Atributo en csv")
    if not name_c:
        return {}
    out = {}
    for _, r in df.iterrows():
        n = str(r[name_c]).strip()
        if not n or n == "nan":
            continue
        out[n] = {
            "Tipo": str(r.get(cols.get("Tipo de dato", ""), "") or "").strip(),
            "Longitud": str(r.get(cols.get("Longitud", ""), "") or "").strip(),
            "Descripción": " ".join(str(r.get(cols.get("Descripción", ""), "") or "").split()),
        }
    return out


def _safe_decode(raw: bytes, enc: str) -> bool:
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def _write_variables_yaml(out_dir: Path, cache_dir: Path, yaml_dir: Path,
                          map_path: Path) -> int:
    """Write one variables_denue_<gNN>.yaml per schema group.

    Seeds each variable's Tipo/Longitud/Descripción from the representative release's
    bundled dictionary, and fills Categorías for the personnel-stratum column from the
    actual data values (the dictionary lists 1–7 codes but the data stores the labels).
    """
    schema_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    fp_to_id = schema_map["fingerprints"]
    # representative (earliest release, lowest state) file per group
    rep: dict[str, dict] = {}
    for p in sorted(out_dir.glob("denue_*.parquet")):
        _, rel, code = p.stem.split("_")
        cols = [c for c in pq.ParquetFile(p).schema_arrow.names if c != "geometry"]
        gid = fp_to_id[_fingerprint_cols(cols)]
        if gid not in rep or (rel, code) < (rep[gid]["rel"], rep[gid]["code"]):
            rep[gid] = {"rel": rel, "code": code, "cols": cols, "path": p}

    yaml_dir.mkdir(parents=True, exist_ok=True)
    for gid, info in sorted(rep.items()):
        entry = denue_zip_entry(RELEASES_BY_YYYYMM[info["rel"]], int(info["code"]))[0]
        folder, fname = entry.url.rstrip("/").rsplit("/", 2)[-2:]
        ddict = _extract_dict_csv(cache_dir / f"{folder}_{fname}")

        # personnel-stratum column: mnemonic "per_ocu"/"PER_OCU" or descriptive
        # "Personal ocupado (estrato)" / "Descripcion estrato personal ocupado".
        ocu_col = next((c for c in info["cols"]
                        if "per_ocu" in c.lower() or "ocup" in c.lower()), None)
        ocu_cats: dict = {}
        if ocu_col is not None:
            vals = pd.read_parquet(info["path"], columns=[ocu_col])[ocu_col].dropna().unique()
            ocu_cats = {str(v): str(v) for v in sorted(vals)}

        doc = {}
        for col in info["cols"]:
            meta = ddict.get(col, {})
            doc[col] = {
                "Descripción": meta.get("Descripción", ""),
                "Tipo": meta.get("Tipo", ""),
                "Longitud": meta.get("Longitud", ""),
                "Categorías": ocu_cats if col == ocu_col else {},
            }
        path = yaml_dir / f"variables_denue_{gid}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True,
                           default_flow_style=False)
    return len(rep)


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
    parser.add_argument("--yaml-dir", type=Path, default=_DEFAULT_SCHEMA_MAP.parent, metavar="DIR")
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
                                  args.schema_map_path)
        print(f"Wrote {n} variables_denue_<gNN>.yaml → {args.yaml_dir}")
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
                      f"parts={info['parts']}")
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
