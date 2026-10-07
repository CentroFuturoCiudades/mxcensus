"""Build the Marco Geoestadístico (MGN) geoparquet mirror for one census period.

This script is for maintainers only — it is NOT part of the installed package.

It downloads INEGI's per-state Marco Geoestadístico shapefile ZIPs for ``--period``
(default 2020: "Marco Geoestadístico, Censo de Población y Vivienda 2020", UPC
889463807469; 2025: "…Encuesta Intercensal 2025", UPC 794551196649 — editions in
``mxcensus.data._catalog.MG_EDITIONS``) and converts each of their layers
(``_catalog.MG_LAYERS``: 15 in every state, plus ``ti`` — territorio insular — in the
island states only) to GeoParquet, one file per layer per state, then appends their
SHA256 hashes to the package registry alongside the census parquet entries.

File names: 2020 keeps the original period-less ``mg_{suffix}_{NN}.parquet``; every
other period is ``mg_{suffix}_{period}_{NN}.parquet`` (``_catalog.mg_filename``). The
ZIP cache / extraction dirs are period-qualified the same way, so two editions never
share a cached ZIP. Editions INEGI publishes as one national ZIP (2010 and the
1995–2005 municipal frames) are not supported yet — see docs/cpv/PLAN.md.

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
    marco_geo_zip_url,
    mg_filename,
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
    state_periods = sorted(p for p, e in MG_EDITIONS.items() if e.layout == "state")
    parser.add_argument("--period", default=MG_LEGACY_PERIOD, choices=state_periods,
                        help=f"MG edition to build (default {MG_LEGACY_PERIOD}); "
                             "national-ZIP editions are not supported yet")
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
