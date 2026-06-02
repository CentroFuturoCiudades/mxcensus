"""DENUE schema, harmonization, and validation tests.

The synthetic-frame tests exercise the grouping / harmonization / per-group schema
logic against the bundled YAMLs only — no network, no mirrored parquet — so they run
in CI. The ``@skipif(not _REAL)`` block additionally loads one real file per group when
a local mirror (``data/parquet/``) is present (maintainer machine).
"""
from __future__ import annotations

import glob
import warnings
from pathlib import Path

import geopandas as gpd
import pandera.pandas as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point

import mxcensus
from mxcensus._resources import denue_schema_map, variables_denue
from mxcensus.denue import (
    _CODED_REGEX,
    _NUMERIC,
    _OCU_ALLOWED,
    _PER_OCU,
    _TIPO_UNI,
    _TIPO_UNI_ALLOWED,
    _fingerprint,
    _group_of,
    _group_schema,
    _harmonize,
    _latest_schema,
    _mnemonic_of,
    _normalize_fecha,
    _validate,
)

_SM = denue_schema_map()
_LATEST = _SM["groups"][_SM["latest"]]["columns"]
_GROUPS = list(_SM["groups"])

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


def _valid_value(gid: str, col: str) -> str:
    """A value that should pass ``_group_schema(gid)`` for ``col``."""
    cats = (variables_denue(gid).get(col) or {}).get("Categorías") or {}
    if cats:
        return next(iter(cats))
    mn = _mnemonic_of(gid, col)
    if mn in _CODED_REGEX:
        return {"codigo_act": "461110", "cod_postal": "12345",
                "cve_ent": "09", "cve_mun": "010", "cve_loc": "0001"}[mn]
    if mn in _NUMERIC:
        return "19.4"
    return "x"


def _valid_frame(gid: str, rows=3) -> gpd.GeoDataFrame:
    cols = _SM["groups"][gid]["columns"]
    data = {c: [_valid_value(gid, c)] * rows for c in cols}
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
    assert _group_of(_frame(_SM["groups"][gid]["columns"]), _SM) == gid


# --- mnemonic resolution -----------------------------------------------------

def test_mnemonic_of_fixes_case_and_rename():
    assert _mnemonic_of("g09", "NOM_ESTAB") == "nom_estab"   # UPPERCASE group
    assert _mnemonic_of("g11", "PER_OCU") == "per_ocu"
    assert _mnemonic_of("g10", "clee") == "clee"             # identity
    assert _mnemonic_of("g01", "Razón social") == "raz_social"  # descriptive rename


# --- per_ocu + tipoUniEco harmonization --------------------------------------

def test_per_ocu_uppercase_label_remap():
    gid = "g01"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_PER_OCU[gid][0]] = "251 Y MAS PERSONAS"
    assert set(_harmonize(gdf, gid, _LATEST)["per_ocu"]) == {"251 y más personas"}


def test_per_ocu_numeric_code_remap():
    gid = "g03"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_PER_OCU[gid][0]] = "1"
    assert set(_harmonize(gdf, gid, _LATEST)["per_ocu"]) == {"0 a 5 personas"}


def test_tipo_uni_code3_is_actividad_en_vivienda():
    """2012/2013 'Tipo de establecimiento' code 3 → 'Actividad en vivienda'."""
    gid = "g03"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_TIPO_UNI[gid][0]] = "3"
    assert set(_harmonize(gdf, gid, _LATEST)["tipoUniEco"]) == {"Actividad en vivienda"}


def test_tipo_uni_code_and_label_remap():
    gid = "g05"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_TIPO_UNI[gid][0]] = "1"
    assert set(_harmonize(gdf, gid, _LATEST)["tipoUniEco"]) == {"Fijo"}
    gid = "g01"  # uppercase label era
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf[_TIPO_UNI[gid][0]] = "SEMIFIJO"
    assert set(_harmonize(gdf, gid, _LATEST)["tipoUniEco"]) == {"Semifijo"}


def test_normalize_fecha():
    import pandas as pd
    out = _normalize_fecha(
        pd.Series(["JULIO 2010", "mar-11", "2013 07", "ABRIL 2012  ",
                   "2021-05", "DICIEMBRE 2014", "junk", None])
    ).tolist()
    assert out[:6] == ["2010-07", "2011-03", "2013-07", "2012-04", "2021-05", "2014-12"]
    assert pd.isna(out[6]) and pd.isna(out[7])  # unparseable / null → NA


# --- per-group schemas -------------------------------------------------------

@pytest.mark.parametrize("gid", _GROUPS)
def test_group_schema_builds(gid):
    schema = _group_schema(gid)
    assert set(schema.columns) == set(_SM["groups"][gid]["columns"])


def test_group_schema_isin_on_per_ocu_source():
    """The per_ocu source column carries an isin check sourced from the YAML categories."""
    for gid in ("g01", "g03", "g08"):
        src = _PER_OCU[gid][0]
        checks = _group_schema(gid).columns[src].checks
        assert any(getattr(c, "name", "") == "isin" for c in checks), gid


def test_group_schema_rejects_bad_per_ocu():
    gid = "g01"
    schema = _group_schema(gid)
    schema.validate(_valid_frame(gid).drop(columns="geometry"))  # clean → passes
    bad = _valid_frame(gid)
    bad[_PER_OCU[gid][0]] = "BOGUS STRATUM"
    with pytest.raises(pa.errors.SchemaError):
        schema.validate(bad.drop(columns="geometry"))


def test_harmonized_frame_passes_latest_schema():
    """A clean synthetic frame harmonizes and passes the tight latest schema."""
    gid = "g01"
    gdf = _frame(_SM["groups"][gid]["columns"])
    gdf["Personal ocupado (estrato)"] = "0 A 5 PERSONAS"
    gdf["Tipo de unidad económica"] = "FIJO"
    gdf["Código de la clase de actividad"] = "461110"
    gdf["Código postal"] = "12345"
    gdf["Latitud"], gdf["Longitud"] = "19.4", "-99.1"
    h = _harmonize(gdf, gid, _LATEST)
    _latest_schema().validate(h.drop(columns="geometry"))  # raises on violation


def test_validate_warns_not_raises():
    """_validate surfaces value violations as a warning, never raising."""
    gid = "g01"
    bad = _valid_frame(gid)
    bad[_PER_OCU[gid][0]] = "BOGUS"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _validate(_group_schema(gid), bad.drop(columns="geometry"), "test")
    assert any("schema violation" in str(x.message) for x in w)


def test_coerce_keeps_nulls():
    """coerce=True must not turn None into the string 'None' and break isin."""
    gid = "g01"
    frame = _valid_frame(gid)
    frame[_PER_OCU[gid][0]] = [None, "0 A 5 PERSONAS", None]
    _group_schema(gid).validate(frame.drop(columns="geometry"))  # nulls pass isin


# --- variable YAML completeness ---------------------------------------------

@pytest.mark.parametrize("gid", _GROUPS)
def test_variables_populated(gid):
    """Every group's YAML has per_ocu categories and core descriptions (no empty g09/g11)."""
    v = variables_denue(gid)
    ocu_src = _PER_OCU[gid][0]
    assert v[ocu_src]["Categorías"], f"{gid} per_ocu categories missing"
    mnem_or_desc = [c for c in v if _mnemonic_of(gid, c) in ("nom_estab", "id")]
    assert any(v[c]["Descripción"] for c in mnem_or_desc), f"{gid} descriptions missing"


def test_variables_denue_bundled():
    v = mxcensus.variables_denue("g10")
    assert {"per_ocu", "codigo_act", "id"} <= set(v)
    assert v["per_ocu"]["Categorías"]


def test_load_denue_exported():
    assert callable(mxcensus.load_denue)
    assert "load_denue" in mxcensus.__all__


# --- End-to-end against the real mirror (skipped in CI when no local data) ---

@pytest.mark.skipif(not _REAL, reason="no local DENUE mirror (data/parquet/)")
@pytest.mark.parametrize("gid", sorted(_REAL) if _REAL else ["_"])
def test_real_file_harmonizes(gid):
    """Real data harmonizes to g10 with canonical per_ocu/tipoUniEco and no stale-map warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        gdf = mxcensus.load_denue(survey_path=_REAL[gid], harmonize=True)
    assert not any("rename target" in str(x.message) for x in w)  # structural guard
    assert list(gdf.drop(columns="geometry").columns) == _LATEST
    assert gdf.crs.to_epsg() == 4326
    assert set(gdf["tipoUniEco"].dropna().unique()) <= set(_TIPO_UNI_ALLOWED)


@pytest.mark.skipif(not _REAL, reason="no local DENUE mirror (data/parquet/)")
@pytest.mark.parametrize("gid", sorted(_REAL) if _REAL else ["_"])
def test_real_file_raw_loads(gid):
    """harmonize=False returns the raw columns and runs group-schema validation (warn-only)."""
    gdf = mxcensus.load_denue(survey_path=_REAL[gid], harmonize=False)
    assert set(gdf.columns) - {"geometry"} == set(_SM["groups"][gid]["columns"])
    assert gdf.crs.to_epsg() == 4326


# --------------------------------------------------------------------------- #
# Geometry recovery / out-of-state nulling / duplicates (scripts/build_denue.py)
# --------------------------------------------------------------------------- #
import sys  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from shapely.geometry import box  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_denue as _bd  # noqa: E402

# Synthetic "state": a 1°×1° square inside the Mexico bbox.
_SQUARE = box(-100.0, 19.0, -99.0, 20.0)
shapely.prepare(_SQUARE)


def test_recover_identity_in_state():
    lat, lon = pd.Series([19.5]), pd.Series([-99.5])
    geom, c = _bd._recover_geometry(lat, lon, _SQUARE)
    assert c["ok"] == 1 and c["n_resolved"] == 1
    assert round(geom[0].x, 2) == -99.5 and round(geom[0].y, 2) == 19.5


def test_recover_negated_longitude():
    # Longitude stored without its minus sign → recovered by neg_lon.
    lat, lon = pd.Series([19.5]), pd.Series([99.5])
    geom, c = _bd._recover_geometry(lat, lon, _SQUARE)
    assert c["neg_lon"] == 1
    assert round(geom[0].x, 2) == -99.5 and round(geom[0].y, 2) == 19.5


def test_recover_swapped():
    # lat/lon transposed → recovered by swap.
    lat, lon = pd.Series([-99.5]), pd.Series([19.5])
    geom, c = _bd._recover_geometry(lat, lon, _SQUARE)
    assert c["swap"] == 1
    assert round(geom[0].x, 2) == -99.5 and round(geom[0].y, 2) == 19.5


def test_recover_out_of_state_nulled():
    # In the national bbox but outside the assigned state, no transform recovers → null.
    lat, lon = pd.Series([25.0]), pd.Series([-105.0])
    geom, c = _bd._recover_geometry(lat, lon, _SQUARE)
    assert geom[0] is None and c["out_of_state"] == 1 and c["n_resolved"] == 0


def test_recover_no_coords_nulled():
    lat, lon = pd.Series([np.nan]), pd.Series([np.nan])
    geom, c = _bd._recover_geometry(lat, lon, _SQUARE)
    assert geom[0] is None and c["no_coords"] == 1


def test_recover_leaves_raw_latlon_untouched():
    lat = pd.Series([19.5, 25.0, 99.5])   # in-state, out-of-state, neg-lon-recoverable
    lon = pd.Series([-99.5, -105.0, 99.5])
    lat0, lon0 = lat.copy(), lon.copy()
    _bd._recover_geometry(lat, lon, _SQUARE)
    pd.testing.assert_series_equal(lat, lat0)
    pd.testing.assert_series_equal(lon, lon0)


def test_recover_buffer_rescues_near_border():
    # A point just outside the square is out-of-state unbuffered, in-state once buffered.
    lat, lon = pd.Series([19.5]), pd.Series([-98.995])  # ~ a few hundred m east of the edge
    _, c_strict = _bd._recover_geometry(lat, lon, _SQUARE)
    assert c_strict["out_of_state"] == 1
    buffered = _SQUARE.buffer(0.01)  # ~1 km in degrees, ample for this test
    shapely.prepare(buffered)
    _, c_buf = _bd._recover_geometry(lat, lon, buffered)
    assert c_buf["ok"] == 1


def test_dup_counts():
    df = pd.DataFrame({"id": ["a", "a", "b"], "x": [1, 1, 2]})
    n_rows, n_ids = _bd._dup_counts(df)
    assert n_rows == 1   # rows 0 and 1 identical
    assert n_ids == 1    # id "a" repeated once


@pytest.mark.skipif(not _REAL, reason="no local DENUE mirror (data/parquet/)")
def test_load_state_boundary_real():
    """A real mg_ent layer loads, buffers, and reprojects to a valid 4326 polygon."""
    _bd._BOUNDARY_CACHE.clear()
    boundary = _bd._load_state_boundary(9, _MIRROR, 500.0)
    assert boundary.geom_type in ("Polygon", "MultiPolygon")
    minx, miny, maxx, maxy = boundary.bounds
    assert -120 < minx < -85 and 14 < miny < 33  # CDMX, lon/lat range
