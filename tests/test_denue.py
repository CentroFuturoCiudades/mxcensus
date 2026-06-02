"""DENUE harmonization unit tests.

These exercise the schema-grouping + harmonization logic against the bundled
``denue_schema_map.yaml`` only — no network and no mirrored parquet required, so
they run in CI. End-to-end ``load_denue(state=…)`` fetching is covered by the
maintainer build, not here.
"""
from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

import mxcensus
from mxcensus._resources import denue_schema_map
from mxcensus.denue import _PER_OCU, _group_of, _harmonize, _latest_schema

_SM = denue_schema_map()
_LATEST = _SM["groups"][_SM["latest"]]["columns"]
_GROUPS = list(_SM["groups"])


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
    h = _harmonize(gdf, gid, _LATEST)
    _latest_schema().validate(h.drop(columns="geometry"))  # raises on violation


def test_variables_denue_bundled():
    v = mxcensus.variables_denue("g10")
    assert {"per_ocu", "codigo_act", "id"} <= set(v)
    assert v["per_ocu"]["Categorías"]  # personnel strata present


def test_load_denue_exported():
    assert callable(mxcensus.load_denue)
    assert "load_denue" in mxcensus.__all__
