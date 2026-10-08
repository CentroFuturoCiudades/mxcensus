"""Build the Marco Geoestadístico (MGN) geoparquet mirror for one census period.

This script is for maintainers only — it is NOT part of the installed package.

It downloads INEGI's per-state Marco Geoestadístico shapefile ZIPs for ``--period``
(default 2020: "Marco Geoestadístico, Censo de Población y Vivienda 2020", UPC
889463807469; 2025: "…Encuesta Intercensal 2025", UPC 794551196649; 2015: the EIC 2015's
"Cartografía geoestadística urbana y rural amanzanada. Cierre de la Encuesta Intercensal
2015", one product (UPC) per state, 12 layers — editions in
``mxcensus.data._catalog.MG_EDITIONS``) and converts each of their layers
(``_catalog.MG_LAYERS``: 15 in every state, plus ``ti`` — territorio insular — in the
island states only; ``mg_layers(period)`` for an edition with fewer) to GeoParquet, one
file per layer per state, then appends their
SHA256 hashes to the package registry alongside the census parquet entries.

File names: 2020 keeps the original period-less ``mg_{suffix}_{NN}.parquet``; every
other period is ``mg_{suffix}_{period}_{NN}.parquet`` (``_catalog.mg_filename``). The
ZIP cache / extraction dirs are period-qualified the same way, so two editions never
share a cached ZIP. Editions INEGI publishes as **one national ZIP** (``layout="national"``:
the 2010 v5.0 frame and the 1995–2005 municipal frames) are downloaded once; each layer is
read whole from its nested ZIP (``_NATIONAL_LAYERS`` maps the shapefile name to the suffix)
and split per state on ``CVE_ENT`` (or ``CVEGEO[:2]`` where the layer has no entity column)
into the same ``mg_{suffix}_{period}_{NN}`` files. MG 2010 has five layers: ``ent``, ``mun``,
``a`` (urban AGEBs), ``l`` (urban localities) and ``lpr`` (rural localities, points), in an
LCC on ITRF92 — the mirror keeps it; ``load_mg``'s default EPSG:6372 is a null shift.

Steps
-----
1. For each requested state, download ``{code}_{slug}.zip`` from INEGI (cached), extract
   its ``conjunto_de_datos/{code}{suffix}.shp`` layers, and convert each to
   ``mg_filename(suffix, NN, period)`` (zstd compression, source ``.prj`` CRS preserved —
   INEGI spells the one LCC projection two ways, the custom MEXICO_ITRF_2008_LCC on most
   layers and EPSG:6372 on a few; ``mxcensus.load_mg`` normalises them, the mirror stays
   faithful — docs/cpv/STEP_1d.md). Single-part geometries are promoted to their
   Multi* form (the gpkg-era files were multi-part; ``mxcensus.mg_agebs_ur`` relies on
   ``lpr`` being MultiPoint). Integer attribute columns are cast to int32.
2. Append/update the ``mg_*`` entries in registry.txt, preserving every existing
   (census/DENUE) entry. Disable with --no-registry; ``--update-registry`` upserts the
   hashes of files already built (no download).

Every layer is readable with ``mxcensus.load_mg(layer, state=, period=)``; the legacy
``mxcensus.load_mg_census`` consumes four of the 2020 layers (a, l, lpr, ar).

Quick smoke test (Aguascalientes only, ~37 MB download, no registry write)
--------------------------------------------------------------------------
    uv run python scripts/build_marco_geo.py --states 1 --no-registry

Full build (all 32 states; several GB of downloads, ~2.3 GB of geoparquet)
--------------------------------------------------------------------------
    uv run python scripts/build_marco_geo.py
    uv run python scripts/build_marco_geo.py --period 2025     # EIC 2025 frame
    uv run python scripts/build_marco_geo.py --period 2025 --update-registry   # hashes only

A local copy of the per-state GeoPackages can still be used instead of downloading:
    uv run python scripts/build_marco_geo.py --local-gpkg-dir /path/to/MarcoGeo2020

After running
-------------
- Upload the new files to the Hugging Face bucket: ``python scripts/upload_hf.py upload``.
- Commit the updated src/mxcensus/data/registry.txt.
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import MultiLineString, MultiPoint, MultiPolygon

import _build_common as bc
from mxcensus.data._catalog import (
    MG_EDITIONS,
    MG_LAYERS,
    MG_LEGACY_PERIOD,
    MG_OPTIONAL_LAYERS,
    STATE_CODE_FMT,
    marco_geo_national_url,
    marco_geo_zip_url,
    mg_filename,
    mg_layers,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"

# INEGI per-state layer suffixes (file/layer name == f"{code}{suffix}").
_ALL_SUFFIXES = sorted(MG_LAYERS)
# A layer an edition names in full: the EIC 2015 frame's «NNterritorioinsular».
_SUFFIX_ALIASES = {"territorioinsular": "ti"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MULTI = {"Point": MultiPoint, "LineString": MultiLineString, "Polygon": MultiPolygon}


def _to_multi(geom):
    """Promote a single-part geometry to its Multi* form; leave Multi*/None as-is.

    Shapefiles may return single-part Point/LineString/Polygon features, whereas the
    gpkg-era parquet stored every layer multi-part — promote so geometry types match.
    """
    if geom is None:
        return geom
    ctor = _MULTI.get(geom.geom_type)
    return ctor([geom]) if ctor is not None else geom


def _normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Match the target schema: Multi* geometry and int32 integer attribute columns."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.map(_to_multi)
    for col in gdf.columns:
        if col != "geometry" and pd.api.types.is_integer_dtype(gdf[col].dtype):
            gdf[col] = gdf[col].astype("int32")
    return gdf


def _cache_names(state: int, period: str) -> tuple[str, Path]:
    """(cached ZIP name, extraction subdir) — period-qualified except for legacy 2020,
    whose names are kept so an existing 2020 cache stays valid."""
    code = STATE_CODE_FMT(state)
    if period == MG_LEGACY_PERIOD:
        return f"mg_{code}.zip", Path("mg") / code
    return f"mg_{period}_{code}.zip", Path("mg") / period / code


def _inegi_layer_paths(
    state: int, cache_dir: Path, raw_dir: Path, retries: int,
    period: str = MG_LEGACY_PERIOD,
) -> tuple[dict[str, Path], Path]:
    """Download+extract a state's MG zip; return ({suffix: shp_path}, extract_dir).

    Layers are discovered from the ZIP; a suffix outside ``MG_LAYERS`` is reported
    (and skipped) so a new INEGI layer is noticed rather than silently dropped."""
    code = STATE_CODE_FMT(state)
    zip_name, sub = _cache_names(state, period)
    zip_path = bc.fetch_zip_verified(
        marco_geo_zip_url(state, period), cache_dir, zip_name, retries
    )
    extract_dir = raw_dir / sub
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    paths: dict[str, Path] = {}
    for shp in extract_dir.rglob(f"{code}*.shp"):
        suffix = shp.stem[len(code):]            # 01ent -> ent
        suffix = _SUFFIX_ALIASES.get(suffix, suffix)
        if suffix in _ALL_SUFFIXES:
            paths[suffix] = shp
        else:
            print(f"  ! {shp.name}: unexpected layer suffix {suffix!r} — not converted")
    return paths, extract_dir


def _gpkg_layer_reader(state: int, mg_dir: Path):
    """Legacy local-gpkg source: return a reader(suffix) -> GeoDataFrame | None."""
    code = STATE_CODE_FMT(state)
    matches = sorted(mg_dir.glob(f"{code}_*.gpkg"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one '{code}_*.gpkg' in {mg_dir}, found {len(matches)}: "
            f"{[p.name for p in matches]}"
        )
    gpkg = matches[0]
    available = {name for name, _ in pyogrio.list_layers(gpkg)}

    def reader(suffix: str):
        layer = f"{code}{suffix}"
        return gpd.read_file(gpkg, layer=layer) if layer in available else None

    return reader


def _build_marco_geo_state(
    state: int, reader, out_dir: Path, suffixes: list[str],
    period: str = MG_LEGACY_PERIOD,
) -> list[Path]:
    """Convert one state's MGN layers to geoparquet. ``reader(suffix)`` returns a
    GeoDataFrame or None (layer absent). Returns the files written."""
    code = STATE_CODE_FMT(state)
    written: list[Path] = []
    for suffix in suffixes:
        gdf = reader(suffix)
        if gdf is None:
            if suffix not in MG_OPTIONAL_LAYERS:     # ti: island states only
                print(f"  ! {code}{suffix}: layer not present — skipped")
            continue
        gdf = _normalize(gdf)
        out_path = out_dir / mg_filename(suffix, state, period)
        gdf.to_parquet(out_path, compression="zstd")
        written.append(out_path)
        print(f"  wrote {out_path.name}  ({out_path.stat().st_size // 1024} KB, "
              f"{len(gdf)} feats)")
    return written


def _built_files(
    out_dir: Path, states: list[int], suffixes: list[str], period: str,
) -> tuple[list[Path], list[str]]:
    """(files of ``period`` already in ``out_dir``, missing names) for ``states`` ×
    ``suffixes``. An absent optional layer (``ti`` outside the island states) is not
    reported missing."""
    present: list[Path] = []
    missing: list[str] = []
    for state in states:
        for suffix in suffixes:
            path = out_dir / mg_filename(suffix, state, period)
            if path.exists():
                present.append(path)
            elif suffix not in MG_OPTIONAL_LAYERS:
                missing.append(path.name)
    return present, missing


# ---------------------------------------------------------------------------
# National-ZIP editions (2010 v5.0; 1995–2005 municipal frames)
# ---------------------------------------------------------------------------

# Shapefile name (case-insensitive prefix) → layer suffix, for the national editions.
_NATIONAL_LAYERS: tuple[tuple[str, str], ...] = (
    (r"^entidades", "ent"),
    (r"^municipios", "mun"),
    (r"^agebs?_urb", "a"),                 # 2000: agebs_urb_2000
    (r"^localidades_urbanas", "l"),
    (r"^localidades_rurales", "lpr"),
)


def _national_suffix(stem: str) -> str | None:
    return next((sfx for rx, sfx in _NATIONAL_LAYERS if re.match(rx, stem, re.IGNORECASE)),
                None)


def _national_layer_paths(period: str, cache_dir: Path, raw_dir: Path,
                          retries: int) -> tuple[dict[str, Path], Path]:
    """Download (once) the national ZIP of ``period`` and extract its nested ZIPs; return
    ``({suffix: shp_path}, extract_dir)``. A shapefile no ``_NATIONAL_LAYERS`` entry names
    is reported and skipped."""
    zip_path = bc.fetch_zip_verified(marco_geo_national_url(period), cache_dir,
                                     f"mg_{period}_national.zip", retries)
    extract_dir = raw_dir / "mg" / period / "national"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    for inner in sorted(extract_dir.glob("*.zip")):
        with zipfile.ZipFile(inner) as zf:
            zf.extractall(extract_dir / inner.stem)
    paths: dict[str, Path] = {}
    for shp in sorted(extract_dir.rglob("*.shp")):
        suffix = _national_suffix(shp.stem)
        if suffix is None:
            print(f"  ! {shp.name}: no layer suffix for this shapefile — not converted")
        elif suffix in paths:
            raise RuntimeError(f"two shapefiles for layer {suffix!r}: {paths[suffix]}, {shp}")
        else:
            paths[suffix] = shp
    return paths, extract_dir


def _edition_crs(period: str, paths: dict[str, Path]):
    """The one CRS the edition's layers declare, for a layer shipped without a ``.prj``
    (MG 2005: ``Entidades``/``Municipios`` have none, ``agebs_urb_2005`` has one). Raises
    unless every layer with a ``.prj`` declares the same CRS."""
    from pyproj import CRS
    found = [CRS.from_user_input(c) for p in paths.values()
             if (c := pyogrio.read_info(p).get("crs"))]
    if not found or any(not c.equals(found[0]) for c in found[1:]):
        raise ValueError(f"MG {period}: a layer has no .prj and the others do not declare "
                         f"one common CRS ({len(found)} declared)")
    return found[0]


# Where each national edition keeps the entity: a 2-digit code column, else the first two
# characters of a longer key. 2010: CVE_ENT, or CVEGEO (AGEBs); 2005: CVE_EDO, or CLAVE
# (AGEBs, 13 characters); 2000: CVE_ENT, CVEMUNI (municipalities, entity + municipality),
# CLVAGB (AGEBs, «010010001293-5»); 1995: CVE_ENT.
_ENTITY_COLUMNS = ("CVE_ENT", "CVE_EDO")
_ENTITY_PREFIX_COLUMNS = ("CVEGEO", "CVE_CONCA", "CVEMUNI", "CLVAGB", "CLAVE")


def _state_codes(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Each feature's entity code (:data:`_ENTITY_COLUMNS`, else the first two characters
    of a :data:`_ENTITY_PREFIX_COLUMNS` key)."""
    cols = {c.upper(): c for c in gdf.columns}
    for name in _ENTITY_COLUMNS:
        if name in cols:
            return gdf[cols[name]].astype(str).str.zfill(2)
    for name in _ENTITY_PREFIX_COLUMNS:
        if name in cols:
            return gdf[cols[name]].astype(str).str[:2]
    raise ValueError(f"no entity column ({'/'.join(_ENTITY_COLUMNS + _ENTITY_PREFIX_COLUMNS)}) "
                     f"in {list(gdf.columns)}")


def _build_national(period: str, states: list[int], suffixes: list[str], out_dir: Path,
                    cache_dir: Path, raw_dir: Path, retries: int,
                    cleanup_raw: bool = True) -> list[Path]:
    """Split a national-ZIP edition's layers into per-state geoparquet files."""
    paths, extract_dir = _national_layer_paths(period, cache_dir, raw_dir, retries)
    wanted = {STATE_CODE_FMT(s) for s in states}
    written: list[Path] = []
    for suffix in suffixes:
        if suffix not in paths:
            continue                       # the edition has no such layer
        gdf = gpd.read_file(paths[suffix])
        if gdf.crs is None:
            gdf = gdf.set_crs(_edition_crs(period, paths))
            print(f"  ! {paths[suffix].name}: no .prj — the edition's CRS of its other layers")
        gdf = _normalize(gdf)
        codes = _state_codes(gdf)
        unknown = sorted(set(codes) - {STATE_CODE_FMT(s) for s in range(1, 33)})
        if unknown:
            raise ValueError(f"MG {period} {suffix}: entity codes outside 01-32: {unknown}")
        print(f"  {paths[suffix].name}: {len(gdf):,} features → layer {suffix!r}")
        for code in sorted(set(codes) & wanted):
            part = gdf.loc[(codes == code).to_numpy()].reset_index(drop=True)
            out_path = out_dir / mg_filename(suffix, int(code), period)
            part.to_parquet(out_path, compression="zstd")
            written.append(out_path)
        missing = sorted(wanted - set(codes))
        if missing:
            print(f"  ! {suffix}: no features for state(s) {missing}")
    if cleanup_raw:
        shutil.rmtree(extract_dir, ignore_errors=True)
    return written


def _national_built(out_dir: Path, states: list[int], suffixes: list[str],
                    period: str) -> list[Path]:
    """The files of a national edition already in ``out_dir`` (its layers are a subset
    of ``MG_LAYERS``, so nothing absent is reported missing)."""
    return [out_dir / mg_filename(sfx, s, period) for s in states for sfx in suffixes
            if (out_dir / mg_filename(sfx, s, period)).exists()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--states", nargs="+", type=int, default=list(range(1, 33)),
        metavar="N", help="State codes to process (default: all 32)",
    )
    parser.add_argument("--period", default=MG_LEGACY_PERIOD, choices=sorted(MG_EDITIONS),
                        help=f"MG edition to build (default {MG_LEGACY_PERIOD}); a national-"
                             "ZIP edition (2010, 1995-2005) is split per state")
    parser.add_argument("--layers", nargs="+", default=_ALL_SUFFIXES, metavar="SUFFIX",
                        help=f"Layer suffixes to convert (default: all {len(_ALL_SUFFIXES)})")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR",
                        help="Output directory for geoparquet files")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR",
                        help="Where downloaded INEGI ZIPs are cached")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR",
                        help="Where ZIPs are extracted")
    parser.add_argument("--retries", type=int, default=2, metavar="N",
                        help="Download retries on transient INEGI failures")
    parser.add_argument("--local-gpkg-dir", type=Path, default=None, metavar="DIR",
                        help="Use local per-state NN_<name>.gpkg files instead of "
                             "downloading from INEGI")
    parser.add_argument("--keep-raw", dest="cleanup_raw", action="store_false",
                        help="Keep extracted shapefiles (default: delete after convert)")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE",
                        help="registry.txt to update")
    parser.add_argument("--no-registry", dest="registry_update", action="store_false",
                        help="Skip updating registry.txt")
    parser.add_argument("--update-registry", dest="registry_only", action="store_true",
                        help="Only upsert the hashes of the --period/--states/--layers files "
                             "already in --output into registry.txt (no download)")
    parser.set_defaults(registry_update=True, cleanup_raw=True)
    args = parser.parse_args(argv)
    if args.local_gpkg_dir is not None and args.period != MG_LEGACY_PERIOD:
        parser.error("--local-gpkg-dir only applies to the 2020 frame")
    if args.registry_only and not args.registry_update:
        parser.error("--update-registry and --no-registry are mutually exclusive")

    national = MG_EDITIONS[args.period].layout == "national"
    if not national:              # an edition with fewer layers (2015: 12) builds only those
        args.layers = [s for s in args.layers if s in mg_layers(args.period)]
    if national and args.local_gpkg_dir is not None:
        parser.error("--local-gpkg-dir only applies to the 2020 frame")
    if args.registry_only and national:
        present = _national_built(args.output, args.states, args.layers, args.period)
        print(f"Upserting {len(present)} MG {args.period} file(s) into {args.registry}")
        bc.update_registry(present, args.registry)
        return
    if args.registry_only:
        present, missing = _built_files(args.output, args.states, args.layers, args.period)
        if missing:
            print(f"  ! {len(missing)} expected file(s) not built: {', '.join(missing[:10])}"
                  + (" …" if len(missing) > 10 else ""))
        print(f"Upserting {len(present)} MG {args.period} file(s) into {args.registry}")
        bc.update_registry(present, args.registry)
        return

    args.output.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    if national:
        written = _build_national(args.period, args.states, args.layers, args.output,
                                  args.cache_dir, args.raw_dir, args.retries,
                                  args.cleanup_raw)
        if args.registry_update:
            bc.update_registry(written, args.registry)
        print(f"\nDone: {len(written)} file(s).")
        return
    for state in args.states:
        print(f"\n=== State {state:02d} ===")
        if args.local_gpkg_dir is not None:
            reader = _gpkg_layer_reader(state, args.local_gpkg_dir)
            written += _build_marco_geo_state(state, reader, args.output, args.layers,
                                              args.period)
        else:
            paths, extract_dir = _inegi_layer_paths(
                state, args.cache_dir, args.raw_dir, args.retries, args.period
            )
            written += _build_marco_geo_state(
                state, lambda s: gpd.read_file(paths[s]) if s in paths else None,
                args.output, args.layers, args.period,
            )
            if args.cleanup_raw:
                shutil.rmtree(extract_dir, ignore_errors=True)

    if args.registry_update:
        bc.update_registry(written, args.registry)

    print("\nDone.")
    print(
        "\nNext steps:\n"
        "  1. python scripts/upload_hf.py upload\n"
        f"  2. Commit {args.registry}."
    )


if __name__ == "__main__":
    main()
