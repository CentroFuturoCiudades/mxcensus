"""Build the Marco Geoestadístico (MGN) 2020 geoparquet mirror.

This script is for maintainers only — it is NOT part of the installed package.

It converts INEGI's Marco Geoestadístico 2020 GeoPackages (one per state, held
locally) into GeoParquet, one file per layer per state, and appends their SHA256
hashes to the package registry alongside the census parquet entries.

Steps
-----
1. For each requested state, locate its `NN_<statename>.gpkg` and convert each of
   its 15 layers to `mg_{suffix}_{NN}.parquet` (zstd compression, native CRS
   preserved). The rural-locality-points layer (`lpr`) is defensively promoted to
   MultiPoint, which `mxcensus.mg_agebs_ur` relies on.
2. Append/update the `mg_*` entries in registry.txt, preserving every existing
   (census) entry. Disable with --no-registry.

Only four layers are consumed by the current loaders (a, l, lpr, ar — see
`mxcensus.load_mg_census`); the rest are mirrored for completeness.

Quick smoke test (Aguascalientes only)
--------------------------------------
    uv run python scripts/build_marco_geo.py --states 1

Full build (all 32 states; ~2.3 GB of geoparquet)
-------------------------------------------------
    uv run python scripts/build_marco_geo.py

After running
-------------
- Upload the new files to the existing GitHub Release:
    gh release upload data-v0.1.0 data/parquet/mg_*.parquet --clobber
- Commit the updated src/mxcensus/data/registry.txt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pooch
import pyogrio
from shapely.geometry import MultiPoint

from mxcensus.data._catalog import STATE_CODE_FMT

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MG_DIR = Path("/Users/gperaza/Data/MarcoGeo2020")
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"

# INEGI per-state layer suffixes (layer name == f"{code}{suffix}").
_ALL_SUFFIXES = [
    "a", "ar", "cd", "e", "ent", "fm", "l", "lpr", "m", "mun",
    "pe", "pem", "sia", "sil", "sip",
]

# Prefixes of the census files already in the registry — used to guard against
# accidentally dropping them when we rewrite registry.txt.
_CENSUS_PREFIXES = ("iter_", "resargebub_", "personas_", "viviendas_")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_multipoint(geom):
    """Promote a Point to a single-part MultiPoint; leave other geometries as-is."""
    if geom is not None and geom.geom_type == "Point":
        return MultiPoint([geom])
    return geom


def _build_marco_geo_state(
    state: int, mg_dir: Path, out_dir: Path, suffixes: list[str]
) -> list[Path]:
    """Convert one state's MGN layers to geoparquet. Returns the files written."""
    code = STATE_CODE_FMT(state)
    matches = sorted(mg_dir.glob(f"{code}_*.gpkg"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one '{code}_*.gpkg' in {mg_dir}, found {len(matches)}: "
            f"{[p.name for p in matches]}"
        )
    gpkg = matches[0]
    available = {name for name, _ in pyogrio.list_layers(gpkg)}

    written: list[Path] = []
    for suffix in suffixes:
        layer = f"{code}{suffix}"
        if layer not in available:
            print(f"  ! {layer}: layer not present in {gpkg.name} — skipped")
            continue
        gdf = gpd.read_file(gpkg, layer=layer)
        if suffix == "lpr":
            gdf["geometry"] = gdf.geometry.map(_to_multipoint)
        out_path = out_dir / f"mg_{suffix}_{code}.parquet"
        gdf.to_parquet(out_path, compression="zstd")
        written.append(out_path)
        print(
            f"  wrote {out_path.name}  ({out_path.stat().st_size // 1024} KB, "
            f"{len(gdf)} feats)"
        )
    return written


def _update_registry(written: list[Path], registry_path: Path) -> None:
    """Upsert geoparquet hashes into registry.txt, preserving existing entries."""
    comments: list[str] = []
    entries: dict[str, str] = {}
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                comments.append(line)
                continue
            fname, file_hash = stripped.split()
            entries[fname] = file_hash

    census_before = {k for k in entries if k.startswith(_CENSUS_PREFIXES)}
    for path in written:
        entries[path.name] = pooch.file_hash(str(path))

    lines = comments + [f"{fname} {entries[fname]}" for fname in sorted(entries)]
    registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    census_after = {k for k in entries if k.startswith(_CENSUS_PREFIXES)}
    lost = census_before - census_after
    assert not lost, f"registry lost census entries: {sorted(lost)}"
    print(
        f"\nRegistry updated: {len(written)} geo entries upserted; "
        f"{len(entries)} total ({len(census_after)} census)."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--states", nargs="+", type=int, default=list(range(1, 33)),
        metavar="N", help="State codes to process (default: all 32)",
    )
    parser.add_argument("--marco-geo-dir", type=Path, default=_DEFAULT_MG_DIR, metavar="DIR",
                        help="Directory holding the per-state NN_<name>.gpkg files")
    parser.add_argument("--layers", nargs="+", default=_ALL_SUFFIXES, metavar="SUFFIX",
                        help=f"Layer suffixes to convert (default: all {len(_ALL_SUFFIXES)})")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR",
                        help="Output directory for geoparquet files")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE",
                        help="registry.txt to update")
    parser.add_argument("--no-registry", dest="registry_update", action="store_false",
                        help="Skip updating registry.txt")
    parser.set_defaults(registry_update=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for state in args.states:
        print(f"\n=== State {state:02d} ===")
        written += _build_marco_geo_state(state, args.marco_geo_dir, args.output, args.layers)

    if args.registry_update:
        _update_registry(written, args.registry)

    print("\nDone.")
    print(
        "\nNext steps:\n"
        f"  1. gh release upload data-v0.1.0 {args.output}/mg_*.parquet --clobber\n"
        f"  2. Commit {args.registry}."
    )


if __name__ == "__main__":
    main()
