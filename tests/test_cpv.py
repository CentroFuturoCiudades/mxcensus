"""CPV family (censos / conteos / encuestas intercensales 1990–2025) tests.

Phase 0 covers the download catalog (``mxcensus.data._cpv_catalog``) and the
multi-edition Marco Geoestadístico helpers — all offline. The URLs and ZIP member lists
pinned here were verified live against INEGI on 2026-10-07 (``docs/cpv/STEP_0_probe.md``);
loader/schema tests join this file as the family is built (docs/cpv/PLAN.md).
"""
from __future__ import annotations

import pytest

from mxcensus.data._catalog import (
    MG_EDITIONS,
    marco_geo_national_url,
    marco_geo_zip_url,
    mg_filename,
)
from mxcensus.data._cpv_catalog import (
    DICTIONARY_URLS,
    EDITIONS,
    EDITIONS_BY_PERIOD,
    FILE_RE,
    KINDS,
    MICRO_TABLES,
    NATIONAL_TABLES,
    PRODUCT_OF,
    TABLES,
    cpv_filename,
    cpv_zip_entry,
    dictionary_url,
    find_member,
    get_edition,
    latest_edition,
    parse_filename,
)

_P = "https://www.inegi.org.mx/contenidos/programas"

# State-01 (or national) URLs HEAD-verified on 2026-10-07 (ZIP Content-Type).
_VERIFIED_URLS = {
    ("1990", "microdatos"): "ccpv/1990/microdatos/cgpv90p_01_dbf.zip",
    ("1990", "iter"): "ccpv/1990/microdatos/iter/01_aguascalientes_1990_iter_dbf.zip",
    ("1995", "microdatos"): "ccpv/1995/microdatos/cpv95_01_dbf.zip",
    ("1995", "iter"): "ccpv/1995/microdatos/iter/01_aguascalientes_1995_iter_dbf.zip",
    ("2000", "microdatos"): "ccpv/2000/microdatos/muestra/cgpv2000_01_dbf.zip",
    ("2000", "iter"): "ccpv/2000/datosabiertos/cgpv2000_iter_01_csv.zip",
    ("2005", "microdatos"): "ccpv/2005/microdatos/muestra/cpv2005_01_dbf.zip",
    ("2005", "iter"): "ccpv/2005/datosabiertos/cpv2005_iter_01_csv.zip",
    ("2010", "microdatos"): "ccpv/2010/microdatos/mpv/MC2010_01_dbf.zip",
    ("2010", "iter"): "ccpv/2010/datosabiertos/iter_01_2010_csv.zip",
    ("2010", "ageb"): "ccpv/2010/datosabiertos/ageb_y_manzana/resageburb_01_2010_csv.zip",
    ("2015", "microdatos"): "intercensal/2015/microdatos/eic2015_01_csv.zip",
    ("2020", "microdatos"): "ccpv/2020/microdatos/Censo2020_CA_ags_csv.zip",
    ("2020", "iter"): "ccpv/2020/datosabiertos/iter/iter_01_cpv2020_csv.zip",
    ("2020", "ageb"): "ccpv/2020/datosabiertos/ageb_manzana/ageb_mza_urbana_01_cpv2020_csv.zip",
    ("2025", "microdatos"): "eic/2025/microdatos/eic2025_micro_01_csv.zip",
    ("2025", "estimaciones"): "eic/2025/datosabiertos/conjunto_de_datos_eic2025_105_csv.zip",
}

# Data members of the state-01 / national ZIPs listed on 2026-10-07 (dictionary CSVs kept
# as decoys where the ZIP has them).
_PROBED_MEMBERS = {
    ("1990", "microdatos"): ["m_1001.dbf"],
    ("1990", "iter"): ["ITER_01DBF90.dbf"],
    ("1995", "microdatos"): ["datgen95.dbf", "migint95.dbf"],
    ("1995", "iter"): ["ITER_01DBF95.dbf"],
    ("2000", "microdatos"): ["MIN_F01.DBF", "PER_F01.DBF", "VHO_F01.DBF"],
    ("2000", "iter"): ["cgpv2000_iter_01/conjunto_de_datos/cgpv2000_iter_01.csv",
                       "cgpv2000_iter_01/diccionario_de_datos/fd_cgpv2000_iter.csv"],
    ("2005", "microdatos"): ["cpv2005_01_dbf/trhmue01.DBF", "cpv2005_01_dbf/trpmue01.DBF",
                             "cpv2005_01_dbf/trvmue01.DBF"],
    ("2005", "iter"): ["cpv2005_iter_01/conjunto_de_datos/cpv2005_iter_01.csv",
                       "cpv2005_iter_01/diccionario_de_datos/fd_cpv2005_iter.csv"],
    ("2010", "microdatos"): ["Migrantes_01.dbf", "Personas_01.dbf", "Viviendas_01.dbf"],
    ("2010", "iter"): ["iter_01_cpv2010/catalogos/tam_loc.csv",
                       "iter_01_cpv2010/conjunto_de_datos/iter_01_cpv2010.csv",
                       "iter_01_cpv2010/diccionario_de_datos/fd_iter_cpv2010.csv"],
    ("2010", "ageb"): [
        "resultados_ageb_urbana_01_cpv2010/conjunto_de_datos/resultados_ageb_urbana_01_cpv2010.csv",
        "resultados_ageb_urbana_01_cpv2010/diccionario_de_datos/fd_resultados_ageb_urbana_cpv2010.csv",
    ],
    ("2015", "microdatos"): ["TR_PERSONA01.CSV", "TR_VIVIENDA01.CSV"],
    ("2020", "microdatos"): ["Migrantes01.CSV", "Personas01.CSV", "Viviendas01.CSV"],
    ("2020", "iter"): ["iter_01_cpv2020/catalogos/tam_loc.csv.csv",
                       "iter_01_cpv2020/conjunto_de_datos/conjunto_de_datos_iter_01CSV20.csv",
                       "iter_01_cpv2020/diccionario_datos/diccionario_datos_iter_01CSV20.csv"],
    ("2020", "ageb"): [
        "ageb_mza_urbana_01_cpv2020/conjunto_de_datos/conjunto_de_datos_ageb_urbana_01_cpv2020.csv",
        "ageb_mza_urbana_01_cpv2020/diccionario_de_datos/diccionario_datos_ageb_urbana_01_cpv2020.csv",
    ],
    ("2025", "microdatos"): ["migrantes01.csv", "personas01.csv", "viviendas01.csv"],
    ("2025", "estimaciones"): ["conjunto_de_datos/conjunto_datos_eic2025_105.csv",
                               "diccionario_datos/diccionario_datos_eic2025_105.csv"],
}


# --- editions -----------------------------------------------------------------------

def test_editions_chronological_and_consistent():
    periods = [e.period for e in EDITIONS]
    assert periods == ["1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025"]
    assert list(EDITIONS_BY_PERIOD) == periods
    for e in EDITIONS:
        assert e.period == str(e.year)
        assert e.kind in KINDS
        assert e.tables and set(e.tables) <= set(TABLES)
        for t in e.tables:
            assert PRODUCT_OF[t] in e.urls
        assert set(e.products) == {PRODUCT_OF[t] for t in e.tables}


def test_edition_table_sets():
    has = {e.period: set(e.tables) for e in EDITIONS}
    assert has["2025"] == {"viviendas", "personas", "migrantes", "estimaciones"}
    assert has["2020"] == {"viviendas", "personas", "migrantes", "iter", "ageb"}
    assert has["2015"] == {"viviendas", "personas"}
    assert has["2010"] == {"viviendas", "personas", "migrantes", "iter", "ageb"}
    assert has["2005"] == {"viviendas", "hogares", "personas", "iter"}
    assert has["2000"] == {"viviendas", "personas", "migrantes", "iter"}
    assert has["1995"] == {"hogares", "migrantes", "iter"}
    assert has["1990"] == {"personas", "iter"}
    # ITER exists for every censo/conteo and no encuesta intercensal.
    for e in EDITIONS:
        assert e.has("iter") == (e.kind != "intercensal")
    assert {e.period for e in EDITIONS if not e.weighted} == {"1990", "2005"}


@pytest.mark.parametrize("key", sorted(_VERIFIED_URLS))
def test_verified_urls(key):
    period, product = key
    ed = get_edition(period)
    state = None if product == "estimaciones" else 1
    assert ed.zip_url(product, state) == f"{_P}/{_VERIFIED_URLS[key]}"


@pytest.mark.parametrize("state", [1, 9, 15, 16, 30, 32])
def test_per_state_urls_format_every_state(state):
    code = f"{state:02d}"
    for e in EDITIONS:
        for product in e.products:
            if product == "estimaciones":
                continue
            url = e.zip_url(product, state)
            assert "{" not in url and url.endswith(".zip")
            assert code in url or e.period == "2020" and product == "microdatos"
            assert e.zip_filename(product, state) == url.rsplit("/", 1)[-1]


def test_url_errors():
    e25, e15 = get_edition("2025"), get_edition("2015")
    with pytest.raises(ValueError, match="per state"):
        e25.zip_url("microdatos")
    with pytest.raises(ValueError, match="no 'iter' product"):
        e15.zip_url("iter", 1)
    with pytest.raises(ValueError, match="1-32"):
        e25.zip_url("microdatos", 33)
    with pytest.raises(ValueError, match="does not publish"):
        e15.filename("migrantes", 1)
    with pytest.raises(ValueError, match="unknown CPV edition"):
        get_edition("2016")


def test_latest_edition():
    assert latest_edition().period == "2025"
    assert latest_edition("personas").period == "2025"
    assert latest_edition("estimaciones").period == "2025"
    assert latest_edition("iter").period == "2020"
    assert latest_edition("ageb").period == "2020"
    assert latest_edition("hogares").period == "2005"
    with pytest.raises(ValueError, match="unknown CPV table"):
        latest_edition("nope")


# --- ZIP members --------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(_PROBED_MEMBERS))
def test_find_member_probed(key):
    period, product = key
    ed = get_edition(period)
    state = None if product == "estimaciones" else 1
    names = _PROBED_MEMBERS[key]
    found = {t: find_member(names, ed, t, state) for t in ed.tables_in(product)}
    assert len(set(found.values())) == len(found)            # distinct members
    for member in found.values():
        assert "diccionario" not in member and "fd_" not in member and "catalogos" not in member


def test_find_member_errors():
    ed = get_edition("2025")
    with pytest.raises(LookupError, match="none"):
        find_member(["personas02.csv"], ed, "personas", 1)
    with pytest.raises(ValueError, match="does not publish"):
        find_member(["x.csv"], get_edition("2015"), "migrantes", 1)


# --- mirror filenames ---------------------------------------------------------------

def test_filename_roundtrip():
    for e in EDITIONS:
        for t in e.tables:
            states = [None] if t in NATIONAL_TABLES else [1, 9, 32]
            for s in states:
                name = e.filename(t, s)
                assert FILE_RE.match(name)
                assert parse_filename(name) == (t, e.period, s)
    assert cpv_filename("personas", "2025", 9) == "cpv_personas_2025_09.parquet"
    assert cpv_filename("estimaciones", "2025") == "cpv_estimaciones_2025.parquet"


def test_filename_errors():
    with pytest.raises(ValueError, match="national table"):
        cpv_filename("estimaciones", "2025", 9)
    with pytest.raises(ValueError, match="per state"):
        cpv_filename("personas", "2025")
    for bad in ("cpv_personas_2025.parquet", "cpv_estimaciones_2025_09.parquet",
                "cpv_nope_2025_01.parquet", "enigh_poblacion_2024.parquet",
                "cpv_iter_2020_1.parquet"):
        with pytest.raises(ValueError):
            parse_filename(bad)


def test_microdata_tables_are_per_state():
    assert not (set(MICRO_TABLES) & NATIONAL_TABLES)


def test_zip_entry_and_dictionaries():
    e = get_edition("2025")
    entry = cpv_zip_entry(e, "microdatos", 9)
    assert entry.url.endswith("eic2025_micro_09_csv.zip")
    assert str(entry.extract_dir) == "cpv/2025/microdatos"
    assert cpv_zip_entry(e, "estimaciones").url.endswith("_105_csv.zip")
    assert dictionary_url("2025", "fd") == f"{_P}/eic/2025/microdatos/eic2025_micro_fd.xlsx"
    assert set(DICTIONARY_URLS) == set(EDITIONS_BY_PERIOD)


# --- Marco Geoestadístico editions ----------------------------------------------------

def test_mg_legacy_2020_unchanged():
    url = marco_geo_zip_url(9)
    assert url == ("https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/"
                   "espanol/bvinegi/productos/geografia/marcogeo/889463807469/"
                   "09_ciudaddemexico.zip")
    assert mg_filename("ent", 9) == "mg_ent_09.parquet"


def test_mg_2025_and_national_editions():
    assert marco_geo_zip_url(1, "2025").endswith("/marcogeo/794551196649/01_aguascalientes.zip")
    assert mg_filename("mun", 9, "2025") == "mg_mun_2025_09.parquet"
    assert marco_geo_national_url("2010").endswith("/marc_geo/702825292812_s.zip")
    with pytest.raises(ValueError, match="national ZIP"):
        marco_geo_zip_url(1, "2010")
    with pytest.raises(ValueError, match="per state"):
        marco_geo_national_url("2025")
    with pytest.raises(ValueError, match="unknown Marco"):
        mg_filename("mun", 1, "2015")
    # Every edition that names an MG frame points at a known MG edition.
    for e in EDITIONS:
        assert e.mg_period is None or e.mg_period in MG_EDITIONS
