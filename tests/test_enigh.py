"""ENIGH loader/schema tests.

Offline tests read the bundled ``enigh_schema_map.yaml`` **dynamically** (no hard-coded
group ids/counts — they depend on the build) and exercise the schema layer, keys and
harmonization on synthetic frames. Real-data tests run only when the local mirror
(``data/parquet/enigh_*.parquet``) is present, via a fixture that redirects ``POOCH.fetch``
to it (no network).
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

import mxcensus
from mxcensus._resources import enigh_schema_map, variables_enigh, variables_enigh_core
from mxcensus.data._enigh_catalog import (
    EDITIONS,
    EDITIONS_BY_PERIOD,
    NS_TABLES,
    TABLES,
    EnighEdition,
    find_member,
    latest_edition,
    ncv_stem,
)
from mxcensus.enigh import (
    _DWELLING_KEY_SPEC,
    _GEO_ADD,
    _HOUSEHOLD_KEY_SPEC,
    _PERSON_KEY_SPEC,
    _RENAME_TABLE,
    _WEIGHTS,
    _core_order,
    _filter_ent,
    _fingerprint,
    _group_of,
    _group_schema,
    _harmonize,
    _latest_schema,
    _level_key,
)

_SM = enigh_schema_map()
_TABLE_GROUPS = [(t, g) for t in TABLES if t in _SM for g in _SM[t]["groups"]]

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REAL = (_MIRROR / "enigh_concentradohogar_2022.parquet").exists()


def _cols(table, gid):
    return _SM[table]["groups"][gid]["columns"]


def _valid_value(table, gid, col):
    if col in _WEIGHTS:
        return "1"
    cats = (variables_enigh(table, gid).get(col) or {}).get("Categorías") or {}
    return next(iter(cats)) if cats else "x"


def _valid_frame(table, gid, rows=3):
    return pd.DataFrame({c: [_valid_value(table, gid, c)] * rows for c in _cols(table, gid)},
                        dtype=str)


# --- catalog -----------------------------------------------------------------

def test_catalog_shape():
    assert [e.period for e in EDITIONS] == ["2008", "2010", "2012", "2014", "2016", "2018",
                                            "2020", "2022", "2024"]
    assert latest_edition().period == "2024"
    assert sum(len(e.tables) for e in EDITIONS) == 99
    assert all(e.tables == NS_TABLES for e in EDITIONS if e.regime == "ns")


def test_catalog_urls_by_regime():
    assert EDITIONS_BY_PERIOD["2022"].url("concentradohogar").endswith(
        "/nc/2022/microdatos/enigh2022_ns_concentradohogar_csv.zip")
    assert EDITIONS_BY_PERIOD["2014"].url("agro").endswith(
        "/nc/2014/microdatos/NCV_Agropecuario_2014_concil_2010_csv.zip")
    assert EDITIONS_BY_PERIOD["2012"].zip_filename("viviendas").startswith("NCV_Viviendas_")
    assert EDITIONS_BY_PERIOD["2014"].zip_filename("viviendas").startswith("NCV_Vivi_")


def test_catalog_absent_tables_raise():
    for y in ("2008", "2010"):
        assert "viviendas" not in EDITIONS_BY_PERIOD[y].tables
        assert "gastos" in EDITIONS_BY_PERIOD[y].tables
        with pytest.raises(ValueError):
            EDITIONS_BY_PERIOD[y].zip_filename("viviendas")
    assert ncv_stem(2016, "gastos") is None or "gastos" not in EDITIONS_BY_PERIOD["2016"].tables
    with pytest.raises(ValueError):
        EDITIONS_BY_PERIOD["2024"].zip_filename("nope")


def test_find_member_spellings():
    e14, e08, e24 = EDITIONS_BY_PERIOD["2014"], EDITIONS_BY_PERIOD["2008"], latest_edition()
    assert find_member(["ncv_gastotarjetas_2014_concil_2010.csv"], e14, "gastotarjetas")
    assert find_member(["erogaciones.csv"], e08, "erogaciones") == "erogaciones.csv"
    assert find_member(["AGRO.CSV"], e24, "agro") == "AGRO.CSV"
    assert find_member(["odd.csv"], e24, "agro") == "odd.csv"       # sole-CSV fallback
    assert find_member(["a.csv", "b.csv"], e24, "agro") is None
    assert find_member(["readme.txt"], e24, "agro") is None


# --- schema map / group schemas ----------------------------------------------

def test_schema_map_per_table():
    for t in _SM:
        assert t in TABLES
        assert set(_SM[t]) == {"latest", "fingerprints", "groups"}
        assert _SM[t]["latest"] in _SM[t]["groups"]


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_fingerprint_round_trips(table, gid):
    fp = _fingerprint(_cols(table, gid))
    assert _SM[table]["fingerprints"][fp] == gid
    assert _group_of(table, _valid_frame(table, gid)) == gid


def test_group_of_unknown_raises():
    with pytest.raises(ValueError, match="not found"):
        _group_of("poblacion", pd.DataFrame({"zzz": ["1"]}))


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_group_schema_accepts_valid_frame(table, gid):
    _group_schema(table, gid).validate(_valid_frame(table, gid), lazy=True)


def test_group_schema_rejects_out_of_catalog_core_value():
    t = "concentradohogar"
    gid = _SM[t]["latest"]
    f = _valid_frame(t, gid)
    f["clase_hog"] = ["9"] * len(f)
    with pytest.raises(pa.errors.SchemaErrors):
        _group_schema(t, gid).validate(f, lazy=True)


def test_group_schema_weights_numeric():
    t = "concentradohogar"
    gid = _SM[t]["latest"]
    f = _valid_frame(t, gid)
    f["factor"] = ["abc"] * len(f)
    with pytest.raises(pa.errors.SchemaErrors):
        _group_schema(t, gid).validate(f, lazy=True)


# --- keys ----------------------------------------------------------------------

def test_key_specs_nest():
    assert _HOUSEHOLD_KEY_SPEC[: len(_DWELLING_KEY_SPEC)] == _DWELLING_KEY_SPEC
    assert _PERSON_KEY_SPEC[: len(_HOUSEHOLD_KEY_SPEC)] == _HOUSEHOLD_KEY_SPEC
    f = pd.DataFrame({"folioviv": ["1"], "foliohog": ["1"], "numren": ["1"], "x": ["1"]})
    assert _level_key(_PERSON_KEY_SPEC, f) == ["folioviv", "foliohog", "numren"]
    assert _level_key(_PERSON_KEY_SPEC, f, f.drop(columns=["numren"])) == ["folioviv", "foliohog"]


def test_filter_ent_uses_folioviv_prefix():
    f = pd.DataFrame({"folioviv": ["0900001201", "1400000301", "090001"], "v": ["a", "b", "c"]})
    out = _filter_ent(f, 9)
    assert list(out["v"]) == ["a", "c"]


# --- harmonization (synthetic) --------------------------------------------------

def _ncv2008_concentrado():
    return pd.DataFrame({
        "folioviv": ["091001"], "foliohog": ["1"], "ubica_geo": ["09010"], "factor": ["10"],
        "sexo": ["2"], "edad": ["45"], "ed_formal": ["7"], "tam_hog": ["3"], "ingcor": ["1000.5"],
        "n_ocup": ["1"], "pering": ["2"], "perocu": ["1"], "clase_hog": ["2"], "otra": ["x"],
    }, dtype=str)


def test_harmonize_ncv_concentrado_renames_and_geo():
    h = _harmonize(_ncv2008_concentrado(), "concentradohogar")
    for src, tgt in _RENAME_TABLE["concentradohogar"].items():
        assert src not in h.columns and tgt in h.columns
    assert h["educa_jefe"].iloc[0] == "07"
    assert h["cve_ent"].iloc[0] == "09" and h["cve_mun"].iloc[0] == "010"
    assert h["cvegeo"].iloc[0] == "09010" and pd.isna(h["cve_loc"].iloc[0])
    assert h["otra"].iloc[0] == "x"                       # non-core kept verbatim
    lead = [c for c in _core_order() if c in h.columns]
    assert list(h.columns[: len(lead)]) == lead


def test_harmonize_nine_char_ubica_geo_and_factor_hog():
    f = pd.DataFrame({"folioviv": ["0100001201"], "foliohog": ["1"], "ubica_geo": ["010010001"],
                      "factor_hog": ["5"], "educa_jefe": ["11"]}, dtype=str)
    h = _harmonize(f, "hogares")
    assert "factor" in h.columns and "factor_hog" not in h.columns
    assert h["cve_loc"].iloc[0] == "0001" and h["cvegeo"].iloc[0] == "01001"
    assert h["educa_jefe"].iloc[0] == "11"


def test_harmonize_poblacion_keeps_person_sexo_edad():
    f = pd.DataFrame({"folioviv": ["0100001201"], "foliohog": ["1"], "numren": ["01"],
                      "sexo": ["1"], "edad": ["30"]}, dtype=str)
    h = _harmonize(f, "poblacion")
    assert {"sexo", "edad"} <= set(h.columns) and "sexo_jefe" not in h.columns
    assert h["cve_ent"].iloc[0] == "01" and pd.isna(h["cvegeo"].iloc[0])


def test_harmonize_idempotent_and_refuses_mixed():
    h = _harmonize(_ncv2008_concentrado(), "concentradohogar")
    pd.testing.assert_frame_equal(h, _harmonize(h, "concentradohogar"))
    f = _ncv2008_concentrado()
    f["ing_cor"] = ["1"]
    with pytest.raises(ValueError, match="both a legacy column and its target"):
        _harmonize(f, "concentradohogar")


def test_harmonize_uppercase_and_stale_warning():
    up = _ncv2008_concentrado().rename(columns=str.upper)
    assert all(c == c.lower() for c in _harmonize(up, "concentradohogar").columns)
    with pytest.warns(UserWarning, match="no cve_ent"):
        _harmonize(pd.DataFrame({"x": ["1"]}), "agro")


@pytest.mark.parametrize("table", TABLES)
def test_latest_schema_builds_and_accepts(table):
    h = _harmonize(_ncv2008_concentrado(), table)
    _latest_schema(table).validate(h, lazy=True)


def test_latest_schema_rejects_bad_core():
    h = _harmonize(_ncv2008_concentrado(), "concentradohogar")
    h["clase_hog"] = ["7"]
    with pytest.raises(pa.errors.SchemaErrors):
        _latest_schema("concentradohogar").validate(h, lazy=True)
    h = _harmonize(_ncv2008_concentrado(), "concentradohogar")
    h["cve_ent"] = ["9"]
    with pytest.raises(pa.errors.SchemaErrors):
        _latest_schema("concentradohogar").validate(h, lazy=True)


def test_core_yaml_and_exports():
    core = variables_enigh_core()
    assert {"folioviv", "foliohog", "numren", "factor", "ing_cor", "clase_hog"} <= set(core)
    assert set(_GEO_ADD) <= set(_core_order())
    for name in ("load_enigh", "load_enigh_hogares", "load_enigh_viviendas",
                 "load_enigh_personas", "load_enigh_survey", "variables_enigh",
                 "variables_enigh_core", "enigh_schema_map"):
        assert callable(getattr(mxcensus, name))


def test_load_enigh_argument_errors():
    with pytest.raises(ValueError):
        mxcensus.load_enigh(table="nope")
    with pytest.raises(ValueError, match="not published"):
        mxcensus.load_enigh(table="viviendas", period="2008")
    with pytest.raises(ValueError, match="unknown period"):
        mxcensus.load_enigh(table="poblacion", period="2015")


# --- real data (skipped without the local mirror) ---------------------------------

@pytest.fixture
def local_mirror(monkeypatch):
    from mxcensus.data import _registry

    def _fetch(fname, **_):
        p = _MIRROR / fname
        if not p.exists():
            raise FileNotFoundError(p)
        return str(p)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)
    return _MIRROR


_ALL = [e.period for e in EDITIONS]
# Published INEGI totals (Σ factor in concentradohogar): households.
_HOUSEHOLDS = {"2014": 31_671_002, "2022": 37_560_123, "2024": 38_830_230}


@pytest.mark.skipif(not _REAL, reason="no local ENIGH mirror (data/parquet/)")
@pytest.mark.parametrize("period", _ALL)
@pytest.mark.parametrize("harmonize", [False, True])
def test_hogares_personas_real(local_mirror, period, harmonize):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        h = mxcensus.load_enigh_hogares(period, harmonize=harmonize)
        p = mxcensus.load_enigh_personas(period, harmonize=harmonize)
    assert not [x for x in w if "violation" in str(x.message) or "not unique" in str(x.message)]
    assert list(h.index.names) == ["folioviv", "foliohog"]
    assert list(p.index.names) == ["folioviv", "foliohog", "numren"]
    assert h.index.is_unique and p.index.is_unique
    assert h["factor"].notna().all() and p["factor"].notna().all()
    if period in _HOUSEHOLDS:
        assert h["factor"].sum() == _HOUSEHOLDS[period]
    if harmonize:
        assert {"ing_cor", "tot_integ", "sexo_jefe", "cve_ent", "cvegeo"} <= set(h.columns)
        assert h["cve_ent"].str.fullmatch(r"\d{2}").all()
        assert "cve_ent" in p.columns


@pytest.mark.skipif(not _REAL, reason="no local ENIGH mirror (data/parquet/)")
@pytest.mark.parametrize("period", _ALL)
def test_harmonized_totals_equal_raw(local_mirror, period):
    raw = mxcensus.load_enigh_hogares(period)
    harm = mxcensus.load_enigh_hogares(period, harmonize=True)
    inc = "ing_cor" if "ing_cor" in raw.columns else "ingcor"
    assert len(raw) == len(harm)
    assert raw["factor"].sum() == harm["factor"].sum()
    assert (raw[inc] * raw["factor"]).sum() == (harm["ing_cor"] * harm["factor"]).sum()


@pytest.mark.skipif(not _REAL, reason="no local ENIGH mirror (data/parquet/)")
@pytest.mark.parametrize("period", ["2012", "2016", "2024"])
def test_survey_nested_index_real(local_mirror, period):
    v, h, p = mxcensus.load_enigh_survey(period, harmonize=True)
    assert list(v.index.names) == ["folioviv"]
    assert list(h.index.names)[:1] == list(v.index.names)
    assert list(p.index.names)[:2] == list(h.index.names)
    assert v.index.is_unique and h.index.is_unique and p.index.is_unique
    # every household's dwelling exists
    assert h.index.get_level_values("folioviv").isin(v.index).all()


@pytest.mark.skipif(not _REAL, reason="no local ENIGH mirror (data/parquet/)")
def test_ent_filter_real(local_mirror):
    h = mxcensus.load_enigh_hogares("2024", ent=9, harmonize=True)
    assert (h["cve_ent"] == "09").all() and 0 < len(h) < 10_000


@pytest.mark.skipif(not _REAL, reason="no local ENIGH mirror (data/parquet/)")
def test_survey_raises_without_dwelling_table(local_mirror):
    with pytest.raises(ValueError, match="not published"):
        mxcensus.load_enigh_survey("2008")
