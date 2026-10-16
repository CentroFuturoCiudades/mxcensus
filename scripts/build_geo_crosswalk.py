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
- **1990** (8i) has no frame: its step to 1995 comes from the localities. A municipality of
  the 1995 frame that the 1990 ITER lacks (25) takes as parents the 1990 municipalities
  whose localities INEGI's Archivo Histórico de Localidades moves into it at the Conteo
  1995 (the bundled locality lineage's ``code`` and ``absorption`` links of ``PERIOD`` 1995;
  a parent is the municipality of the locality's earlier code), and the shares are of
  **population**, measured at the Conteo 1995 as the frames' areas are on the later frame:
  each 1995 locality a link brings into the new municipality weighs its 1995 ``POBTOT``
  (reserved counts 0), divided among its links' municipalities by their 1990 counts (La
  Magdalena Tlaltelulco, 29048, was two 1990 localities in 29010 and 29029); then
  ``parte_del_nuevo`` = the parent's share of that population, ``parte_del_origen`` = its
  share of the parent's population before the split (the parent's 1995 ``POBTOT`` plus
  everything it lost in the step). The 1990 parts of a locality that the 1990 ITER does not
  list (Valle de Chalco's Xico, then part of Chalco city) need no 1990 count while one
  municipality gives the whole locality. The 1990 codes are a subset of the 1995 frame's
  (checked).

Usage::

    .venv/bin/python scripts/build_geo_crosswalk.py            # needs mg_mun_* of every edition
                                                               # and the 1990 ITER (cpv_iter_1990_*)
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

from mxcensus.cpv_aggregates import load_cpv_iter  # noqa: E402
from mxcensus.cpv_geo import cpv_loc_lineage  # noqa: E402
from mxcensus.data._catalog import mg_filename  # noqa: E402
from mxcensus.data._cpv_catalog import cpv_filename  # noqa: E402
from mxcensus.mg import CANONICAL_CRS  # noqa: E402

_DEFAULT_MIRROR = _REPO_ROOT / "data" / "parquet"
_DEFAULT_OUTPUT = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "cpv_mun_lineage.yaml"

# The editions with a municipal frame, oldest first, and where each keeps the municipality's
# 5-character code; 1990 has no frame (its step to 1995 comes from the localities, 8i).
_FIRST = "1990"
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


def _iter_localities(mirror: Path, period: str) -> pd.DataFrame:
    """An ITER's municipalities and localities: ``CVEGEO`` (5 or 9 characters), ``NIVEL``,
    ``POBTOT``."""
    frames = []
    for state in range(1, 33):
        path = mirror / cpv_filename("iter", period, state)
        if not path.exists():
            raise SystemExit(f"{path.name} missing: build or fetch the CPV {period} ITER first")
        it = load_cpv_iter(period, state=None, survey_path=path, impute=False,
                           nivel=["municipal", "localidad"])
        frames.append(pd.DataFrame({
            "CVEGEO": it["CVEGEO"].str[:5].where(it["NIVEL"] == "municipal", it["CVEGEO"]),
            "NIVEL": it["NIVEL"].astype(str), "POBTOT": it["POBTOT"]}))
    return pd.concat(frames, ignore_index=True)


def _from_localities(it: pd.DataFrame, it_next: pd.DataFrame, frame: set[str]) -> list[dict]:
    """The 1990 → 1995 changes (see the module doc): each municipality of the 1995 frame
    the 1990 ITER (``it``) lacks, with the 1990 municipalities whose localities moved into
    it, weighed by the 1995 ITER (``it_next``)."""
    mun = it[it["NIVEL"] == "municipal"].set_index("CVEGEO")["POBTOT"]
    gone = sorted(set(mun.index) - frame)
    if gone:
        raise SystemExit(f"ITER {_FIRST} → MG {_PERIODS[0]}: codes disappear: {gone}")
    loc = it[it["NIVEL"] == "localidad"].set_index("CVEGEO")["POBTOT"]
    nxt = it_next.set_index("CVEGEO")["POBTOT"]
    created = sorted(frame - set(mun.index))
    lin = cpv_loc_lineage()
    links = lin[(lin["PERIOD"] == _PERIODS[0]) & lin["KIND"].isin(["code", "absorption"])
                & lin["TO"].str[:5].isin(created) & lin["FROM"].str[:5].isin(mun.index)]
    links = links.drop_duplicates("FROM").assign(PARENT=lambda d: d["FROM"].str[:5])
    rows = []                                   # (new municipality, parent, 1995 population)
    for to, group in links.groupby("TO"):
        pob = float(nxt.get(to, 0) if pd.notna(nxt.get(to, 0)) else 0)
        parents = group.groupby("PARENT")["FROM"].agg(list)
        if len(parents) == 1:
            rows.append((to[:5], parents.index[0], pob))
            continue
        weight = {p: sum(int(loc[f]) for f in froms if f in loc.index)
                  for p, froms in parents.items()}
        if any(f not in loc.index for froms in parents for f in froms) or not sum(weight.values()):
            raise SystemExit(f"ITER {_FIRST} → MG {_PERIODS[0]}: {to} comes from "
                             f"{list(parents.index)} without a 1990 count for every part")
        rows += [(to[:5], p, pob * w / sum(weight.values())) for p, w in weight.items()]
    moved = pd.DataFrame(rows, columns=["NEW", "PARENT", "POB"])
    lost = moved.groupby("PARENT")["POB"].sum()
    before = lost + nxt.reindex(lost.index).astype(float)
    moved = moved.groupby(["NEW", "PARENT"])["POB"].sum()
    changes = []
    for code in created:
        pob = moved.loc[code] if code in moved.index.get_level_values("NEW") else None
        if pob is None or pob.sum() <= 0:
            raise SystemExit(f"ITER {_FIRST} → MG {_PERIODS[0]}: no parent for {code}")
        part_new = pob / pob.sum()
        keep = part_new[part_new >= _MIN_SHARE].sort_values(ascending=False, kind="stable")
        changes.append({
            "desde": _FIRST, "hasta": _PERIODS[0], "CVEGEO": code,
            "origen": [{"CVEGEO": p, "parte_del_nuevo": round(float(n), 3),
                        "parte_del_origen": round(float(pob[p] / before[p]), 3)}
                       for p, n in keep.items()],
        })
    print(f"  ITER {_FIRST} → MG {_PERIODS[0]}: {len(mun):,} → {len(frame):,} municipalities, "
          f"{len(created)} new", flush=True)
    return changes


def build(mirror: Path) -> dict:
    """The lineage document (see the module doc)."""
    frames = {p: _municipalities(mirror, p) for p in _PERIODS}
    it = _iter_localities(mirror, _FIRST)
    changes = _from_localities(it, _iter_localities(mirror, _PERIODS[0]),
                               set(frames[_PERIODS[0]]["CVEGEO"]))
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
    return {"periodos": [_FIRST, *_PERIODS],
            "municipios": {_FIRST: int((it["NIVEL"] == "municipal").sum()),
                           **{p: len(f) for p, f in frames.items()}},
            "parte_minima": _MIN_SHARE,
            # every code of the newest frame; an older frame's are these minus the ones
            # created after it
            "claves": sorted(frames[_PERIODS[-1]]["CVEGEO"]),
            "cambios": changes}


_HEADER = """\
# Municipal lineage across the Marco Geoestadístico editions (1995-2025) and from the 1990
# census. Generated by scripts/build_geo_crosswalk.py from the frames' polygons (mg_mun_*,
# EPSG:6372 areas); do not edit by hand. Each change is a municipality code that appears
# between two consecutive editions ('desde' → 'hasta'), with the municipalities of the
# earlier frame its territory came from (those covering at least 'parte_minima' of it):
# 'parte_del_nuevo' = the share of the new municipality's area, 'parte_del_origen' = the
# share of the parent's area that went to it. 1990 has no frame: its changes to 1995 are the
# municipalities the 1990 ITER lacks, their parents those whose localities moved into them
# (the locality lineage's code and absorption links of 1995) and the shares of population
# at the Conteo 1995 instead of area (the moved localities', of the parent's before the
# split). Codes are never retired: a code present in two frames is the same municipality
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
