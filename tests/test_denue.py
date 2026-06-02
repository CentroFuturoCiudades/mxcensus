"""DENUE harmonization unit tests.

These exercise the schema-grouping + harmonization logic against the bundled
``denue_schema_map.yaml`` only — no network and no mirrored parquet required, so
they run in CI. End-to-end ``load_denue(state=…)`` fetching is covered by the
maintainer build, not here.
"""
from __future__ import annotations

import glob
import warnings
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point

import mxcensus
from mxcensus._resources import denue_schema_map
from mxcensus.denue import _PER_OCU, _fingerprint, _group_of, _harmonize, _latest_schema

_SM = denue_schema_map()
_LATEST = _SM["groups"][_SM["latest"]]["columns"]
_GROUPS = list(_SM["groups"])

# Optional end-to-end coverage: if a local mirror exists (maintainer machine), pick one
# real parquet file per schema group so load_denue is exercised against actual data —
# the synthetic-frame tests below can't catch per_ocu value drift or a stale rename map.
_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"


def _one_file_per_group() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for p in sorted(glob.glob(str(_MIRROR / "denue_*.parquet"))):
        cols = [c for c in pq.ParquetFile(p).schema_arrow.names if c != "geometry"]
        gid = _SM["fingerprints"].get(_fingerprint(cols))
        if gid and gid not in found:
            found[gid] = Path(p)
    return found


_REAL = _one_file_per_group()


def _frame(columns, rows=3):
    data = {c: ["x"] * rows for c in columns}
    return gpd.GeoDataFrame(data, geometry=[Point(-99.1, 19.4)] * rows, crs="EPSG:4326")


def test_latest_is_g10():
    assert _SM["latest"] == "g10"
    assert len(_LATEST) == 42


@pytest.mark.parametrize("gid", _GROUPS)
def test_every_group_harmonizes_to_latest(gid):
    """Any group's columns map onto exactly the latest schema + geometry."""
    h = _harmonize(_frame(_SM["groups"][gid]["columns"]), gid, _LATEST)
    assert list(h.columns) == _LATEST + ["geometry"]
    assert h.crs.to_epsg() == 4326


@pytest.mark.parametrize("gid", _GROUPS)
def test_group_fingerprint_round_trips(gid):
    """A frame built from a group's columns is identified back as that group."""
    assert _group_of(_frame(_SM["groups"][gid]["columns"]), _SM) == gid


def test_per_ocu_uppercase_label_remap():
    gid = "g01"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_PER_OCU[gid][0]] = "251 Y MAS PERSONAS"
    assert set(_harmonize(gdf, gid, _LATEST)["per_ocu"]) == {"251 y más personas"}


def test_per_ocu_numeric_code_remap():
    gid = "g03"  # 2012 stores per_ocu as numeric codes in the code column
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_PER_OCU[gid][0]] = "1"
    assert set(_harmonize(gdf, gid, _LATEST)["per_ocu"]) == {"0 a 5 personas"}


def test_harmonized_frame_passes_pandera():
    gid = "g01"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_PER_OCU[gid][0]] = "0 A 5 PERSONAS"
    gdf["Código de la clase de actividad"] = "461110"  # valid SCIAN (codigo_act regex)
    h = _harmonize(gdf, gid, _LATEST)
    _latest_schema().validate(h.drop(columns="geometry"))  # raises on violation


def test_variables_denue_bundled():
    v = mxcensus.variables_denue("g10")
    assert {"per_ocu", "codigo_act", "id"} <= set(v)
    assert v["per_ocu"]["Categorías"]  # personnel strata present


def test_load_denue_exported():
    assert callable(mxcensus.load_denue)
    assert "load_denue" in mxcensus.__all__


# --- End-to-end against the real mirror (skipped in CI when no local data) ---

@pytest.mark.skipif(not _REAL, reason="no local DENUE mirror (data/parquet/)")
@pytest.mark.parametrize("gid", sorted(_REAL) if _REAL else ["_"])
def test_real_file_loads_and_validates(gid):
    """Each group's real data harmonizes to g10, validates, and yields canonical
    per_ocu — and triggers no stale-rename-map warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a rename-miss warning fails the test
        gdf = mxcensus.load_denue(survey_path=_REAL[gid], harmonize=True)
    assert list(gdf.drop(columns="geometry").columns) == _LATEST
    assert gdf.crs.to_epsg() == 4326
    from mxcensus.denue import _OCU_ALLOWED
    assert set(gdf["per_ocu"].dropna().unique()) <= set(_OCU_ALLOWED)


@pytest.mark.skipif(not _REAL, reason="no local DENUE mirror (data/parquet/)")
@pytest.mark.parametrize("gid", sorted(_REAL) if _REAL else ["_"])
def test_real_file_raw_schema(gid):
    """harmonize=False returns the release's own (raw) columns, still EPSG:4326."""
    gdf = mxcensus.load_denue(survey_path=_REAL[gid], harmonize=False)
    assert set(gdf.columns) - {"geometry"} == set(_SM["groups"][gid]["columns"])
    assert gdf.crs.to_epsg() == 4326
