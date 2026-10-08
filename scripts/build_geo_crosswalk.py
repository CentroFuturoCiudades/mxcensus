"""Build the cross-edition municipal lineage of the Marco Geoestadístico (maintainer-only).

Writes ``src/mxcensus/_yaml/cpv_mun_lineage.yaml``: for each pair of consecutive MG
editions (1995, 2000, 2005, 2010, 2015, 2020, 2025), every municipality code that appears in
the later one, with the municipalities of the earlier one its territory came from and
the area shares. The table is derived from the frames' own polygons (``mg_mun_*``, read
from the local mirror, EPSG:6372 areas). INEGI's AGEEML catalog has the decrees behind
each change but no download of its history; the polygons give the same parentage and the
amounts, and are checked against the code counts of every edition.

- A **new code** is one the earlier frame lacks. Municipality codes are never retired
  between these editions (checked: the build fails if one disappears). Splits keep the
  parent's code and add a new one for the seceding part.
- Its **parents** are the earlier municipalities that cover at least ``_MIN_SHARE`` (5%)
  of its area. Each comes with ``parte_del_nuevo`` (that share) and ``parte_del_origen``
  (the share of the parent's area that went to the new municipality).
- **Boundary revisions** between frames (a few percent of area, everywhere) are not
  changes: a code present in both frames is the same municipality.

Usage::

    .venv/bin/python scripts/build_geo_crosswalk.py            # needs mg_mun_* of every edition
    .venv/bin/python scripts/build_geo_crosswalk.py --mirror DIR --output FILE
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from mxcensus.data._catalog import mg_filename  # noqa: E402
from mxcensus.mg import CANONICAL_CRS  # noqa: E402

_DEFAULT_MIRROR = _REPO_ROOT / "data" / "parquet"
_DEFAULT_OUTPUT = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "cpv_mun_lineage.yaml"

# The editions with a municipal frame, oldest first (1990 has none), and where each keeps the
# municipality's 5-character code.
_PERIODS = ("1995", "2000", "2005", "2010", "2015", "2020", "2025")
_MUN_KEY: dict[str, str | tuple[str, str]] = {
    "1995": ("CVE_ENT", "CVE_MUN"), "2000": "CVEMUNI", "2005": "CVE_CONCA",
    "2010": ("CVE_ENT", "CVE_MUN"), "2015": "CVEGEO", "2020": "CVEGEO", "2025": "CVEGEO",
}
# A parent covers at least this share of the new municipality's area.
_MIN_SHARE = 0.05


def _municipalities(mirror: Path, period: str) -> gpd.GeoDataFrame:
    """One edition's municipalities: ``CVEGEO`` (5 characters), dissolved (a multi-part
    municipality is several features in MG 2000), in EPSG:6372, with its area."""
    frames = []
    for state in range(1, 33):
        path = mirror / mg_filename("mun", state, period)
        if not path.exists():
            raise SystemExit(f"{path.name} missing: build or fetch MG {period} first")
        frames.append(gpd.read_parquet(path).to_crs(CANONICAL_CRS))
    gdf = pd.concat(frames, ignore_index=True)
    key = _MUN_KEY[period]
    code = gdf[key[0]] + gdf[key[1]] if isinstance(key, tuple) else gdf[key]
    gdf = gpd.GeoDataFrame({"CVEGEO": code.astype(str)}, geometry=gdf.geometry, crs=gdf.crs)
    gdf = gdf.dissolve("CVEGEO").reset_index()
    gdf["area"] = gdf.area
    return gdf


def build(mirror: Path) -> dict:
    """The lineage document (see the module doc)."""
    frames = {p: _municipalities(mirror, p) for p in _PERIODS}
    changes = []
    for old, new in zip(_PERIODS[:-1], _PERIODS[1:]):
        a, b = frames[old], frames[new]
        gone = sorted(set(a["CVEGEO"]) - set(b["CVEGEO"]))
        if gone:
            raise SystemExit(f"MG {old} → {new}: codes disappear: {gone}")
        created = sorted(set(b["CVEGEO"]) - set(a["CVEGEO"]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ov = gpd.overlay(a, b[b["CVEGEO"].isin(created)], how="intersection",
                             keep_geom_type=True)
        ov["part_new"] = ov.area / ov["area_2"]
        ov["part_old"] = ov.area / ov["area_1"]
        for code in created:
            parents = (ov[(ov["CVEGEO_2"] == code) & (ov["part_new"] >= _MIN_SHARE)]
                       .sort_values("part_new", ascending=False))
            if parents.empty:
                raise SystemExit(f"MG {old} → {new}: no parent for {code}")
            changes.append({
                "desde": old, "hasta": new, "CVEGEO": code,
                "origen": [{"CVEGEO": p, "parte_del_nuevo": round(float(n), 3),
                            "parte_del_origen": round(float(o), 3)}
                           for p, n, o in zip(parents["CVEGEO_1"], parents["part_new"],
                                              parents["part_old"])],
            })
        print(f"  MG {old} → {new}: {len(a):,} → {len(b):,} municipalities, "
              f"{len(created)} new", flush=True)
    return {"periodos": list(_PERIODS),
            "municipios": {p: len(f) for p, f in frames.items()},
            "parte_minima": _MIN_SHARE,
            # every code of the newest frame; an older frame's are these minus the ones
            # created after it
            "claves": sorted(frames[_PERIODS[-1]]["CVEGEO"]),
            "cambios": changes}


_HEADER = """\
# Municipal lineage across the Marco Geoestadístico editions (1995-2025). Generated by
# scripts/build_geo_crosswalk.py from the frames' polygons (mg_mun_*, EPSG:6372 areas); do
# not edit by hand. Each change is a municipality code that appears between two consecutive
# editions ('desde' → 'hasta'), with the municipalities of the earlier frame its territory
# came from (those covering at least 'parte_minima' of it): 'parte_del_nuevo' = the share of
# the new municipality's area, 'parte_del_origen' = the share of the parent's area that went
# to it. Codes are never retired: a code present in two frames is the same municipality
# (boundary revisions between frames are not changes); 'claves' lists the newest frame's
# codes. Read by mxcensus.cpv_geo.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mirror", type=Path, default=_DEFAULT_MIRROR, metavar="DIR")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, metavar="FILE")
    args = parser.parse_args(argv)
    doc = build(args.mirror)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(_HEADER)
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=100)
    print(f"Lineage → {args.output}  ({len(doc['cambios'])} new municipalities)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
