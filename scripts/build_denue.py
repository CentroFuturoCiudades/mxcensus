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
import numpy as np
import pandas as pd
import pandera.pandas as pa
import pooch
import pyarrow.parquet as pq
import shapely
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


def _cache_name(url: str, yyyymm: str) -> str:
    """Release-qualified cache filename for a ZIP url.

    Dated editions carry the date in their folder segment (e.g. ``2025_05`` →
    ``2025_05_denue_09_0525_csv.zip``), which already disambiguates them. The current
    *undated* edition sits at ``masiva/denue/denue_{state}_csv.zip`` — its folder segment
    is the generic ``denue`` and the filename is identical across editions, so qualify it
    with the release id (the 2013-Jul/Oct collision class). Both ``_read_part`` (download)
    and ``_zip_name_for`` (dictionary lookup) must agree on this name.
    """
    folder, fname = url.rstrip("/").rsplit("/", 2)[-2:]
    return f"{yyyymm}_{fname}" if folder == "denue" else f"{folder}_{fname}"


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
    zip_name = _cache_name(entry.url, entry.extract_dir.parts[1])  # parts: denue/<yyyymm>/<code>
    extract_dir = raw_dir / entry.extract_dir
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bc.fetch_zip_verified(entry.url, cache_dir, zip_name, retries)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    csv_path = _locate_data_csv(extract_dir)
    df, enc = _read_csv_robust(csv_path)
    return df, enc, extract_dir


# Cache of buffered, EPSG:4326 state-boundary polygons, keyed by (state, buffer_m).
_BOUNDARY_CACHE: dict[tuple[int, float], object] = {}

# Ordered, conservative coordinate-repair candidates. Each maps the raw (lat, lon)
# numeric columns to a candidate (lon, lat) pair representing one plausible data-entry
# error; tried in priority order and accepted only if the point lands inside the row's
# own state (see _recover_geometry). `identity` = coordinates already correct.
_COORD_TRANSFORMS: list[tuple[str, "callable"]] = [
    ("identity",     lambda lat, lon: (lon, lat)),
    ("swap",         lambda lat, lon: (lat, lon)),          # lat/lon transposed
    ("neg_lon",      lambda lat, lon: (-lon, lat)),         # dropped minus on longitude
    ("neg_lat",      lambda lat, lon: (lon, -lat)),         # dropped minus on latitude
    ("neg_both",     lambda lat, lon: (-lon, -lat)),
    ("swap_neg_lon", lambda lat, lon: (-lat, lon)),         # transposed + sign error
    ("swap_neg_lat", lambda lat, lon: (lat, -lon)),
]
_RECOVERY_NAMES = [n for n, _ in _COORD_TRANSFORMS if n != "identity"]


def _load_state_boundary(state: int, boundaries_dir: Path, buffer_m: float):
    """Return the state's `mg_ent` polygon, buffered `buffer_m` metres, in EPSG:4326.

    The Marco Geoestadístico entidad layer is stored in INEGI's metric LCC CRS, so the
    buffer is applied there (true metres) before reprojecting to lon/lat. The result is
    `shapely.prepare`d for fast point-in-polygon tests and cached per (state, buffer).
    """
    key = (int(state), float(buffer_m))
    cached = _BOUNDARY_CACHE.get(key)
    if cached is not None:
        return cached
    path = Path(boundaries_dir) / f"mg_ent_{state:02d}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"State boundary {path} not found — build the Marco Geoestadístico entidad "
            f"layer first (scripts/build_marco_geo.py), or pass --boundaries-dir."
        )
    gdf = gpd.read_parquet(path)
    gs = gpd.GeoSeries([gdf.geometry.union_all()], crs=gdf.crs)
    if buffer_m:
        gs = gs.buffer(buffer_m)
    boundary = gs.to_crs(4326).iloc[0]
    shapely.prepare(boundary)  # speeds up the repeated covers() calls below
    _BOUNDARY_CACHE[key] = boundary
    return boundary


def _parse_coords(values) -> np.ndarray:
    """Parse coordinate strings to float64 with Python's **correctly-rounded** ``float()``.

    INEGI stores lat/lon as full-precision decimal strings (e.g. ``-86.938750799999994``)
    that sit on the midpoint between two adjacent doubles. numpy/pandas fast parsers are
    not always correctly rounded there, so they can pick a 1-ULP-off neighbour — and which
    neighbour depends on the build's libm/compiler/SIMD, i.e. it varies across library
    versions *and CPU architectures*. CPython's ``float()`` (David Gay dtoa) is correctly
    rounded and deterministic everywhere, so the derived geometry — and the file's hash —
    is reproducible regardless of where the mirror is built. Missing/non-numeric → NaN.
    """
    arr = values.to_numpy() if hasattr(values, "to_numpy") else np.asarray(values, dtype=object)
    out = np.empty(len(arr), dtype=float)
    for i, v in enumerate(arr):
        try:
            out[i] = float(v)
        except (TypeError, ValueError):
            out[i] = np.nan
    return out


def _recover_geometry(lat: pd.Series, lon: pd.Series, boundary) -> tuple[np.ndarray, dict]:
    """Build EPSG:4326 point geometry from raw lat/lon, repairing offending coordinates.

    For each row the candidates in `_COORD_TRANSFORMS` are tried in priority order; the
    first whose point falls inside the (buffered) assigned-state `boundary` wins — strong
    evidence the raw value was a mangled form of the true location. Rows where no candidate
    lands in-state get **null** geometry. The raw lat/lon Series are never modified.

    Returns ``(geometry_array, counts)`` where counts has per-pattern tallies plus
    ``out_of_state`` (real-looking coords, wrong state), ``out_of_bbox`` (coords outside
    Mexico entirely), ``no_coords`` (missing/non-numeric), and ``ambiguous`` (>1 candidate
    in-state — the priority pick is used).
    """
    lat_v = _parse_coords(lat)
    lon_v = _parse_coords(lon)
    n = len(lat_v)
    geom = np.empty(n, dtype=object)
    geom[:] = None
    resolved = np.zeros(n, dtype=bool)
    resolved_by = np.full(n, "", dtype=object)
    hits = np.zeros(n, dtype=int)

    for name, fn in _COORD_TRANSFORMS:
        clon, clat = fn(lat_v, lon_v)
        finite = np.isfinite(clon) & np.isfinite(clat)
        inside = np.zeros(n, dtype=bool)
        if finite.any():
            pts = shapely.points(clon[finite], clat[finite])
            inside[finite] = shapely.covers(boundary, pts)
        hits += inside
        newly = inside & ~resolved
        if newly.any():
            idx = np.nonzero(newly)[0]
            geom[idx] = shapely.points(clon[idx], clat[idx])
            resolved[idx] = True
            resolved_by[idx] = name

    counts = {"ok": int((resolved_by == "identity").sum())}
    for name in _RECOVERY_NAMES:
        counts[name] = int((resolved_by == name).sum())
    counts["ambiguous"] = int(((hits >= 2) & (resolved_by != "identity") & resolved).sum())

    # Classify the unresolved (null-geometry) rows.
    minlon, minlat, maxlon, maxlat = _MX_BBOX
    in_bbox = (
        np.isfinite(lon_v) & np.isfinite(lat_v)
        & (lon_v >= minlon) & (lon_v <= maxlon)
        & (lat_v >= minlat) & (lat_v <= maxlat)
    )
    unresolved = ~resolved
    no_coords = ~(np.isfinite(lon_v) & np.isfinite(lat_v))
    counts["out_of_state"] = int((unresolved & in_bbox).sum())
    counts["out_of_bbox"] = int((unresolved & ~in_bbox & ~no_coords).sum())
    counts["no_coords"] = int((unresolved & no_coords).sum())
    counts["n_resolved"] = int(resolved.sum())
    counts["geom_null_frac"] = round(float(unresolved.mean()), 4) if n else 0.0
    return geom, counts


def _dup_counts(df: pd.DataFrame) -> tuple[int, int]:
    """Full-row duplicate count and duplicate-key count (id/clee if present)."""
    data = df.drop(columns="geometry") if "geometry" in df.columns else df
    n_dup_rows = int(data.duplicated().sum())
    colmap = {c.lower(): c for c in df.columns}
    id_col = next((colmap[k] for k in ("id", "clee") if k in colmap), None)
    n_dup_ids = int(df[id_col].duplicated().sum()) if id_col else 0
    return n_dup_rows, n_dup_ids


def _df_to_geoparquet(
    df: pd.DataFrame, parquet_path: Path, *,
    state: int, boundaries_dir: Path, buffer_m: float,
) -> dict:
    """Write a DENUE DataFrame to GeoParquet (EPSG:4326); return diagnostics.

    Geometry is derived from the raw latitud/longitud columns and repaired/validated
    against the row's own state boundary (see :func:`_recover_geometry`): offending
    coordinates are recovered by a deterministic transform when one lands the point back
    inside the state, else the geometry is **null**. The raw latitud/longitud columns are
    kept verbatim. Also reports duplicate rows (not removed — faithful mirror).
    """
    fingerprint = _schema_fingerprint(df)
    # lat/lon column names vary by release era ("latitud" vs "Latitud"); match
    # case-insensitively and tolerate their absence (→ all-null geometry).
    colmap = {c.lower(): c for c in df.columns}
    lat_c, lon_c = colmap.get("latitud"), colmap.get("longitud")
    if lat_c is not None and lon_c is not None:
        boundary = _load_state_boundary(state, boundaries_dir, buffer_m)
        geometry, rec = _recover_geometry(df[lat_c], df[lon_c], boundary)
    else:
        geometry = np.full(len(df), None, dtype=object)
        rec = {"ok": 0, "ambiguous": 0, "out_of_state": 0, "out_of_bbox": 0,
               "no_coords": len(df), "n_resolved": 0,
               "geom_null_frac": 1.0 if len(df) else 0.0,
               **{n: 0 for n in _RECOVERY_NAMES}}

    # Multipart concat can leave an object column mixing str + float NaN (e.g.
    # numero_ext: text in one part, all-empty→float in another), which pyarrow
    # refuses to write. Replace NaN with None so it serializes as a string column.
    for col in df.columns[df.dtypes == object]:
        df[col] = df[col].where(df[col].notna(), None)

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.GeoSeries(geometry, index=df.index, crs="EPSG:4326"),
        crs="EPSG:4326",
    )
    gdf.to_parquet(parquet_path, compression="zstd")
    n_dup_rows, n_dup_ids = _dup_counts(df)
    n_recovered = sum(rec[n] for n in _RECOVERY_NAMES)
    return {
        "rows": len(gdf),
        "cols": df.shape[1],
        "columns": list(df.columns),
        "fingerprint": fingerprint,
        "has_coords": lat_c is not None and lon_c is not None,
        "geom_null_frac": rec["geom_null_frac"],
        "n_swapped": rec.get("swap", 0),       # back-compat: recovered-by-transposition
        "n_recovered": n_recovered,
        "recovered": {n: rec[n] for n in _RECOVERY_NAMES if rec[n]},
        "n_out_of_state": rec["out_of_state"],
        "n_dup_rows": n_dup_rows,
        "n_dup_ids": n_dup_ids,
        "size_kb": parquet_path.stat().st_size // 1024,
    }


def _build_denue_state(
    yyyymm: str, state: int, raw_dir: Path, cache_dir: Path, out_dir: Path,
    retries: int, cleanup_raw: bool = True,
    *, boundaries_dir: Path | None = None, buffer_m: float = 500.0,
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
    info = _df_to_geoparquet(
        df, out_path, state=state,
        boundaries_dir=boundaries_dir or out_dir, buffer_m=buffer_m,
    )
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


def _write_schema_matrix_png(cell: dict, releases: list, gid_cols: dict,
                             png_path: Path, dup_cells: set | None = None) -> bool:
    """Render the state × release schema-group matrix as a colour heatmap.

    Rows = states 1–32, columns = releases (chronological), each cell coloured by its
    schema-group id (white = file absent). Cells in ``dup_cells`` (byte-identical
    duplicates, §4) are marked with an ×. Returns False if matplotlib is unavailable.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.patheffects as pe
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.colors import ListedColormap
        from matplotlib.patches import Patch
    except ImportError:
        return False
    dup_cells = dup_cells or set()

    gids = sorted(gid_cols)
    idx = {g: i for i, g in enumerate(gids)}
    states = list(range(1, 33))
    m = np.full((len(states), len(releases)), np.nan)
    for j, rel in enumerate(releases):
        for i, st in enumerate(states):
            g = cell.get((rel, st))
            if g is not None:
                m[i, j] = idx[g]
    cmap = ListedColormap(plt.cm.tab20(np.linspace(0, 1, len(gids))))
    cmap.set_bad("white")

    fig, ax = plt.subplots(figsize=(0.42 * len(releases) + 3, 0.34 * len(states) + 1.5))
    ax.imshow(np.ma.masked_invalid(m), cmap=cmap, aspect="auto",
              vmin=-0.5, vmax=len(gids) - 0.5)
    ax.set_xticks(range(len(releases)))
    ax.set_xticklabels(releases, rotation=90, fontsize=7)
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels([f"{s:02d}" for s in states], fontsize=7)
    ax.set_xlabel("release")
    ax.set_ylabel("state code")
    ax.set_title("DENUE schema group by state × release")
    ax.set_xticks(np.arange(-.5, len(releases), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(states), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.5)
    ax.tick_params(which="minor", length=0)
    for j, rel in enumerate(releases):       # × on byte-identical duplicate cells (§4)
        for i, st in enumerate(states):
            if (rel, st) in dup_cells:
                ax.text(j, i, "×", ha="center", va="center", fontsize=9, color="white",
                        fontweight="bold",
                        path_effects=[pe.withStroke(linewidth=1.6, foreground="black")])
    handles = [Patch(facecolor=cmap(idx[g]), label=f"{g} ({gid_cols[g]} cols)") for g in gids]
    if dup_cells:
        handles.append(Patch(facecolor="none", label="×  byte-identical duplicate"))
    ax.legend(handles=handles, bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7,
              title="schema group")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


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
         f"Missing (expected but absent): {n_missing}.", "",
         "> See also `GEOMETRY_REPORT.md` (coordinate recovery, out-of-state geometry "
         "nulling, duplicate rows) and `VALIDATION_REPORT.md` (per-file schema checks).",
         ""]

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

    # Schema-group matrix: states (rows) × releases (cols), cell = group id. The single
    # best view of the grouping — read across a row for a state's drift over time, down a
    # column for within-release disagreements (§6). Markdown can't colour cells, so the
    # group id is the key.
    cell = {(r["release"], int(r["state"])): fp_to_id[r["fingerprint"]] for r in records}
    gid_cols = {fp_to_id[fp]: len(fp_cols[fp]) for fp in fp_to_id}
    dup_cells = {(m.split("/")[0], int(m.split("/")[1]))
                 for members in dups.values() for m in members}
    png = report_path.parent / "schema_groups.png"
    has_png = _write_schema_matrix_png(cell, releases, gid_cols, png, dup_cells)
    L += ["", "## 8. Schema-group matrix (state × release)", "",
          "States (rows) × releases (columns), each cell coloured by schema-group id "
          "(white = file absent). Read **across a row** for a state's schema drift over "
          "time, **down a column** for within-release disagreements (§6). A **×** marks a "
          "file that is a byte-identical duplicate of another (§4)."]
    L += ["", f"![Schema-group heatmap]({png.name})"] if has_png \
        else ["", "_(matplotlib unavailable — heatmap not generated.)_"]

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
    return _cache_name(entry.url, rel)


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


def _refilter_state_boundaries(
    out_dir: Path, boundaries_dir: Path, buffer_m: float,
    releases: list[str] | None, states: list[int] | None,
) -> list[dict]:
    """Re-derive geometry for existing mirrored parquet using the state-boundary recovery.

    Reads each file, rebuilds the point geometry from the raw latitud/longitud columns via
    :func:`_recover_geometry` (repairing offending coordinates, nulling the unrecoverable),
    counts duplicate rows, and rewrites the file in place. Raw lat/lon columns are untouched.
    No re-download. Returns one findings dict per file.
    """
    rel_set = set(releases) if releases else None
    st_set = set(states) if states else None
    rows: list[dict] = []
    for p in sorted(out_dir.glob("denue_*.parquet")):
        _, yyyymm, code = p.stem.split("_")
        if rel_set and yyyymm not in rel_set:
            continue
        if st_set and int(code) not in st_set:
            continue
        gdf = gpd.read_parquet(p)
        colmap = {c.lower(): c for c in gdf.columns}
        lat_c, lon_c = colmap.get("latitud"), colmap.get("longitud")
        if lat_c is not None and lon_c is not None:
            boundary = _load_state_boundary(int(code), boundaries_dir, buffer_m)
            geometry, rec = _recover_geometry(gdf[lat_c], gdf[lon_c], boundary)
        else:
            geometry = np.full(len(gdf), None, dtype=object)
            rec = {"ok": 0, "ambiguous": 0, "out_of_state": 0, "out_of_bbox": 0,
                   "no_coords": len(gdf), "n_resolved": 0,
                   "geom_null_frac": 1.0 if len(gdf) else 0.0,
                   **{n: 0 for n in _RECOVERY_NAMES}}
        gdf = gdf.set_geometry(
            gpd.GeoSeries(geometry, index=gdf.index, crs="EPSG:4326")
        )
        gdf.to_parquet(p, compression="zstd")
        n_dup_rows, n_dup_ids = _dup_counts(gdf)
        rows.append({
            "file": p.name, "release": yyyymm, "state": code, "rows": len(gdf),
            "recovered": {n: rec[n] for n in _RECOVERY_NAMES if rec[n]},
            "n_recovered": sum(rec[n] for n in _RECOVERY_NAMES),
            "ambiguous": rec["ambiguous"], "out_of_state": rec["out_of_state"],
            "out_of_bbox": rec["out_of_bbox"], "no_coords": rec["no_coords"],
            "n_dup_rows": n_dup_rows, "n_dup_ids": n_dup_ids,
        })
    return rows


def _write_geometry_report(rows: list[dict], report_path: Path, buffer_m: float) -> None:
    """Write docs/denue/GEOMETRY_REPORT.md from the refilter findings (3 sections)."""
    n_files = len(rows)
    tot = lambda k: sum(r[k] for r in rows)  # noqa: E731
    pat_tot: dict[str, int] = defaultdict(int)
    for r in rows:
        for name, c in r["recovered"].items():
            pat_tot[name] += c

    L = [
        "# DENUE geometry & duplicate report", "",
        f"Generated by `build_denue.py --refilter-boundaries` over {n_files} file(s) "
        f"with a {buffer_m:g} m state-boundary buffer.", "",
        "Geometry is derived from the raw `latitud`/`longitud` columns and validated "
        "against each row's own state (`mg_ent`) polygon. Offending coordinates are "
        "**recovered** by a deterministic transform when one lands the point back inside "
        "the state, otherwise the geometry is **null**. The raw `latitud`/`longitud` "
        "columns are kept verbatim; nothing is removed. Duplicate rows are **reported "
        "only** (faithful mirror).", "",
        "## 1. Coordinate recovery", "",
        f"Total points recovered by a non-identity transform: **{tot('n_recovered')}** "
        f"(ambiguous — >1 transform in-state, priority pick used: {tot('ambiguous')}).", "",
    ]
    if pat_tot:
        L.append("| pattern | points |")
        L.append("|---------|--------|")
        for name in _RECOVERY_NAMES:
            if pat_tot.get(name):
                L.append(f"| `{name}` | {pat_tot[name]} |")
        L.append("")
        L.append("Per file:")
        L.append("")
        for r in sorted(rows, key=lambda r: r["n_recovered"], reverse=True):
            if r["n_recovered"]:
                pats = ", ".join(f"{n}={c}" for n, c in r["recovered"].items())
                L.append(f"- `{r['file']}`: {r['n_recovered']} ({pats})")
        L.append("")
    else:
        L.append("No coordinates required recovery.\n")

    L += ["## 2. Out-of-state points (geometry nulled)", "",
          f"Points whose coordinates look real but fall outside their state (and no "
          f"transform recovers them): **{tot('out_of_state')}** across all files. "
          f"Also nulled: {tot('out_of_bbox')} outside Mexico, {tot('no_coords')} "
          f"missing/non-numeric.", ""]
    flagged = [r for r in rows if r["rows"] and r["out_of_state"] / r["rows"] > 0.05]
    oos = [r for r in rows if r["out_of_state"]]
    if flagged:
        L.append(f"**Flagged (>5% out-of-state — review for systematic issues):**")
        for r in sorted(flagged, key=lambda r: r["out_of_state"] / r["rows"], reverse=True):
            L.append(f"- ⚠️ `{r['file']}`: {r['out_of_state']}/{r['rows']} "
                     f"({100 * r['out_of_state'] / r['rows']:.1f}%)")
        L.append("")
    if oos:
        L.append("All files with out-of-state points:")
        for r in sorted(oos, key=lambda r: r["out_of_state"], reverse=True):
            L.append(f"- `{r['file']}`: {r['out_of_state']}/{r['rows']}")
        L.append("")
    else:
        L.append("No out-of-state points.\n")

    L += ["## 3. Duplicate rows", "",
          f"Full-row duplicates: **{tot('n_dup_rows')}** total; duplicate id/clee keys: "
          f"**{tot('n_dup_ids')}** total. (Reported, not removed.)", ""]
    dups = [r for r in rows if r["n_dup_rows"] or r["n_dup_ids"]]
    if dups:
        L.append("| file | dup rows | dup ids |")
        L.append("|------|----------|---------|")
        for r in sorted(dups, key=lambda r: (r["n_dup_rows"], r["n_dup_ids"]), reverse=True):
            L.append(f"| `{r['file']}` | {r['n_dup_rows']} | {r['n_dup_ids']} |")
        L.append("")
    else:
        L.append("No duplicate rows.\n")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(L) + "\n", encoding="utf-8")


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
    parser.add_argument("--refilter-boundaries", action="store_true",
                        help="Re-derive geometry of existing parquet against state "
                             "boundaries (recover/null), report dups; no re-download")
    parser.add_argument("--boundary-buffer-m", type=float, default=500.0, metavar="M",
                        help="State-boundary buffer in metres (default 500)")
    parser.add_argument("--boundaries-dir", type=Path, default=None, metavar="DIR",
                        help="Where mg_ent_*.parquet live (default: --output)")
    parser.add_argument("--geometry-report", type=Path,
                        default=_REPO_ROOT / "docs" / "denue" / "GEOMETRY_REPORT.md",
                        metavar="FILE")
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

    if args.refilter_boundaries:
        bdir = args.boundaries_dir or args.output
        rels = args.releases if args.releases != sorted(RELEASES_BY_YYYYMM) else None
        sts = args.states if args.states != list(range(1, 33)) else None
        rows = _refilter_state_boundaries(args.output, bdir, args.boundary_buffer_m, rels, sts)
        _write_geometry_report(rows, args.geometry_report, args.boundary_buffer_m)
        rec = sum(r["n_recovered"] for r in rows)
        oos = sum(r["out_of_state"] for r in rows)
        print(f"Refiltered {len(rows)} file(s): {rec} recovered, {oos} out-of-state nulled. "
              f"Report → {args.geometry_report}")
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
                    args.retries, args.cleanup_raw,
                    boundaries_dir=args.boundaries_dir or args.output,
                    buffer_m=args.boundary_buffer_m,
                )
                print(f"  {tag}: {info['rows']:,} rows, {info['cols']} cols, "
                      f"fp={info['fingerprint'][:8]}, geomnull={info['geom_null_frac']}, "
                      f"recovered={info['n_recovered']}, outstate={info['n_out_of_state']}, "
                      f"dups={info['n_dup_rows']}, parts={info['parts']}")
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
