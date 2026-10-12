"""Tests for the Archivo Histórico de Localidades (``mxcensus.ahl``, unit 7u).

Offline tests write small AHL tables (INEGI's CSV layout, through the builder's reader) and
stub ``POOCH.fetch``; the ``_REAL`` tests read the mirror's files in ``data/parquet`` and the
ITERs, and rebuild a state from ``data/dict/ahl/AHL.zip``.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

import mxcensus
from mxcensus import ahl
from mxcensus.data._ahl_catalog import (
    FILE_RE, SNAPSHOTS, TABLES, ahl_filename, ahl_member, latest_snapshot)

_ROOT = Path(__file__).resolve().parent.parent
_MIRROR = _ROOT / "data" / "parquet"
_AHL_ZIP = _ROOT / "data" / "dict" / "ahl" / "AHL.zip"
sys.path.insert(0, str(_ROOT / "scripts"))
import build_ahl  # noqa: E402

_HEADERS = {
    "habitantes": "CVE_GEOEST,EVE_CENSAL,INDICE_HAB,FUENTE,TOT_HAB,TOT_HOM,TOT_MUJ",
    "maestro": "CVE_GEOEST,LATITUD,LONGITUD,ALTITUD,CARTA_TOPO,TIPO,NOMBRE_EDO,NOMBRE_MUN",
    "movimientos": "CVE_GEOEST,INDICE,NOM_LOC,NOM_MUN,CAT_POLI,CAT_ADMIVA,ORI_MODIF",
    "res_hist": "CVE_GEOEST,DATOS,DATOS_BIBLIOGRAFIA",
}


def _q(v: str) -> str:
    return '"' + v.replace('"', '""') + '"'


@pytest.fixture
def mirror(tmp_path, monkeypatch):
    """Write AHL tables as the mirror holds them; ``fetched`` lists the files read."""
    from mxcensus.data import _registry
    fetched: list[str] = []

    def write(table: str, state: int, rows: list[tuple]):
        text = _HEADERS[table] + "\r\n" + "".join(
            ",".join(_q(str(v)) for v in r) + "\r\n" for r in rows)
        member = ahl_member(table, state)
        arrow = build_ahl.read_member(text.encode("latin-1"), member)
        pq.write_table(arrow, tmp_path / ahl_filename(table, state), compression="zstd")

    def fetch(name, **kw):
        fetched.append(name)
        path = tmp_path / name
        if not path.exists():
            raise ValueError(f"File '{name}' is not in the registry.")
        return str(path)

    monkeypatch.setattr(_registry.POOCH, "fetch", fetch)
    write.fetched = fetched
    return write


# --------------------------------------------------------------------------- catalog

def test_catalog():
    assert latest_snapshot() == SNAPSHOTS[-1] == "20260918"
    assert list(TABLES) == ["habitantes", "maestro", "movimientos", "res_hist"]
    assert ahl_filename("habitantes", 9) == "ahl_habitantes_20260918_09.parquet"
    assert ahl_filename("res_hist", 32, "20260918") == "ahl_res_hist_20260918_32.parquet"
    assert ahl_member("res_hist", 1) == "AHL01Res_hist.csv"
    m = FILE_RE.fullmatch("ahl_movimientos_20260918_07.parquet")
    assert m and m.group("table", "snapshot", "state") == ("movimientos", "20260918", "07")
    with pytest.raises(ValueError, match="unknown AHL table"):
        ahl_filename("localidades", 1)
    with pytest.raises(ValueError, match="unknown AHL snapshot"):
        ahl_filename("maestro", 1, "20250101")
    with pytest.raises(ValueError, match="1-32"):
        ahl_filename("maestro", 33)


def test_registry_has_every_state_and_table():
    from mxcensus.data._registry import POOCH
    names = {n for n in POOCH.registry if n.startswith("ahl_")}
    assert names == {ahl_filename(t, s, snap) for t in TABLES for s in range(1, 33)
                     for snap in SNAPSHOTS}
    assert all(FILE_RE.fullmatch(n) for n in names)


# --------------------------------------------------------------------------- reading

def test_read_member_is_faithful():
    text = ('CVE_GEOEST,INDICE,NOM_LOC,NOM_MUN,CAT_POLI,CAT_ADMIVA,ORI_MODIF\r\n'
            '"010010001","2","Aguascalientes (Cab.)","Aguascalientes","Ciudad","",'
            '"Censo de 2020.\nA esta localidad se conurba la 010012150."\r\n'
            '"010010002","1","Cañada","Calvillo","Rancho"," ","Censo de 1990."\r\n')
    t = build_ahl.read_member(text.encode("latin-1"), "AHL01Movimientos.csv")
    assert t.column_names == _HEADERS["movimientos"].split(",")
    assert all(str(f.type) == "string" for f in t.schema)
    d = t.to_pydict()
    assert d["CAT_ADMIVA"] == [None, " "]                     # only empty cells are null
    assert d["NOM_LOC"][1] == "Cañada"                        # Latin-1
    assert d["ORI_MODIF"][0].endswith("\nA esta localidad se conurba la 010012150.")


def test_load_ahl_raw(mirror):
    mirror("habitantes", 1, [("010010001", "2020", "1", "Censo", "863,893", "419,168",
                              "444,725")])
    mirror("habitantes", 2, [("020010001", "2020", "2", "Censo", "*", "*", "*")])
    df = mxcensus.load_ahl("habitantes", state=[1, 2])
    assert list(df.index) == [0, 1]
    assert df["TOT_HAB"].tolist() == ["863,893", "*"]           # as published
    assert mirror.fetched == ["ahl_habitantes_20260918_01.parquet",
                              "ahl_habitantes_20260918_02.parquet"]
    with pytest.raises(ValueError, match="unknown AHL table"):
        mxcensus.load_ahl("poblacion", state=1)
    with pytest.raises(ValueError, match="mirrored per state"):
        mxcensus.load_ahl("habitantes", state=None)
    with pytest.raises(ValueError, match="1-32"):
        mxcensus.load_ahl("habitantes", state=40)


# --------------------------------------------------------------------------- population

_FROM, _TO = "040010007", "040130001"        # Dzitbalché: Calkiní → Dzitbalché, 2021-02-15


def _campeche(mirror, extra=()):
    mirror("habitantes", 4, [
        (_FROM, "2020", "1", "Censo", "13,208", "6,501", "6,707"),
        (_FROM, "2010", "2", "Censo", "11,686", "5,695", "5,991"),
        (_FROM, "1990", "3", "Censo", "7,628", "3,800", "3,828"),
        (_TO, "2020", "4", "Censo", "13,208", "6,501", "6,707"),       # INEGI's copy
        (_TO, "1990", "5", "Conteo", "7,628", "3,800", "3,828"),       # before 2010: kept
        ("040010001", "1920", "6", "Censo", "4,199", "2,016", "2,183"),
        ("040010001", "2", "7", "Censo", "0", "0", "0"),
        ("040010002", "1990", "8", "Censo", "0", "0", "0"),
        ("040010002", "1990", "9", "Censo", "4", "*", "*"),
        ("040010002", "1970", "10", "Censo", "-", "-", "-"),
        ("040010002", "1995", "11", "Censo", "*", "*", "*"),
        *extra,
    ])
    mirror("movimientos", 4, [
        (_FROM, "4", "Dzitbalché", "Calkiní", "Ciudad", "",
         "Actualización Geoestadística del 15 de febrero de 2021.\nPasa al municipio de "
         "Dzitbalché (013) con clave de localidad (0001)."),
        (_FROM, "3", "Dzitbalché", "Calkiní", "Ciudad", "", "Censo de 2020."),
        (_FROM, "2", "Dzitbalché", "Calkiní", "Ciudad", "", "Censo 2010."),
        (_FROM, "1", "Ditbalché", "Calkiní", "Villa", "Comisaría", "Censo de 1990."),
        (_TO, "1", "Dzitbalché (Cab.)", "Dzitbalché", "Ciudad", "",
         "Actualización Geoestadística del 15 de febrero de 2021.\nViene del municipio de "
         "Calkiní (001) con clave de localidad (0007)."),
        ("040010001", "1", "Calkiní", "Calkiní", "Villa", "", "Censo de 1921."),
        ("040010002", "1", "Rancho A", "Calkiní", "Rancho", " ", "Conteo 1995."),
        ("040010002", "2", "Rancho B", "Calkiní", "Rancho", "", "Conteo de1995.\nCambio de "
         "nombre de localidad."),
        ("040010002", "3", "Rancho B", "Calkiní", "Rancho", "", "Censo Económico 2014."),
        ("040010002", "0", "Rancho Viejo", "Calkiní", "Rancho", "", "censo de 1970."),
    ])


def test_poblacion(mirror):
    _campeche(mirror)
    pop = mxcensus.load_ahl_poblacion(state=4)
    assert pop.index.names == ["CVE_ENT", "CVE_MUN", "CVE_LOC", "EVE_CENSAL"]
    assert list(pop.columns) == ["FUENTE", "POBTOT", "POBMAS", "POBFEM", "NOM_LOC", "NOM_MUN",
                                 "CAT_POLI", "CAT_ADMIVA"]
    assert str(pop["POBTOT"].dtype) == "Int64" and pop.index.is_unique
    assert list(pop["FUENTE"].cat.categories) == list(ahl.FUENTES)
    frm = pop.loc[("04", "001", "0007")]
    assert frm.loc[2020, ["POBTOT", "POBMAS", "POBFEM"]].tolist() == [13208, 6501, 6707]
    assert frm.loc[1990, ["NOM_LOC", "CAT_POLI", "CAT_ADMIVA"]].tolist() == [
        "Ditbalché", "Villa", "Comisaría"]
    assert frm.loc[2010, "NOM_LOC"] == "Dzitbalché"           # «Censo 2010.»
    # the copy of 2020 is dropped; the equal 1990 row (before 2010) is kept, FUENTE by year
    to = pop.loc[("04", "013", "0001")]
    assert list(to.index) == [1990] and to.loc[1990, "FUENTE"] == "Censo"
    assert pd.isna(to.loc[1990, "NOM_LOC"])                   # no census row in its history
    # «1920» is the 1921 census; the row on year «2» is dropped
    cab = pop.loc[("04", "001", "0001")]
    assert list(cab.index) == [1921] and cab.loc[1921, "POBTOT"] == 4199
    # two rows of 1990: the one with population; «-» and «*» missing
    r = pop.loc[("04", "001", "0002")]
    assert r.loc[1990, "POBTOT"] == 4 and pd.isna(r.loc[1990, "POBMAS"])
    assert r.loc[1970, ["POBTOT", "POBMAS", "POBFEM"]].isna().all()
    assert r.loc[1970, "NOM_LOC"] == "Rancho Viejo"           # «censo de 1970.»
    assert r.loc[1995, "FUENTE"] == "Conteo" and pd.isna(r.loc[1995, "POBTOT"])
    assert r.loc[1995, "NOM_LOC"] == "Rancho B"               # the later of two 1995 rows
    assert pd.isna(r.loc[1995, "CAT_ADMIVA"])

    full = mxcensus.load_ahl_poblacion(state=4, copies=True)
    assert full["COPIA"].dtype == bool
    assert full.index[full["COPIA"]].tolist() == [("04", "013", "0001", 2020)]
    assert len(full) == len(pop) + 1


def test_poblacion_copy_across_states(mirror):
    """A locality moved to another state: ``FROM``'s state is read to find the copy."""
    mirror("habitantes", 27, [("270010763", "2010", "1", "Censo", "12", "6", "6"),
                              ("270010763", "2020", "2", "Censo", "15", "8", "7")])
    mirror("movimientos", 27, [("270010763", "1", "El Sitio", "Balancán", "Rancho", "",
                                "Censo de 2020.")])
    mirror("habitantes", 4, [("040110446", "2010", "1", "Censo", "12", "6", "6")])
    pop = mxcensus.load_ahl_poblacion(state=27, copies=True)
    assert pop["COPIA"].tolist() == [True, False]
    assert "ahl_habitantes_20260918_04.parquet" in mirror.fetched
    assert "ahl_movimientos_20260918_04.parquet" not in mirror.fetched


def test_poblacion_repairs_and_errors(mirror):
    mirror("habitantes", 22, [
        ("220120011", "2000", "1", "Censo", "1,960", "3,402", "1,664"),   # one column off
        ("220120011", "1995", "2", "Conteo", "3,146", "1,605", "1,541"),  # listed, consistent
        ("220120012", "2000", "3", "Censo", "1,960", "3,402", "1,664"),   # not listed
        ("220120013", "2013", "4", "Censo", "5", "*", "*"),
    ])
    mirror("movimientos", 22, [("220120011", "1", "La D", "Peñamiller", "Rancho", "",
                                "Censo de 2000.")])
    with pytest.warns(UserWarning, match="1 population rows on no census year"):
        pop = mxcensus.load_ahl_poblacion(state=22)
    cols = ["POBTOT", "POBMAS", "POBFEM"]
    assert pop.loc[("22", "012", "0011", 2000), cols].tolist() == [3402, 1664, 1738]
    assert pop.loc[("22", "012", "0011", 1995), cols].tolist() == [3146, 1605, 1541]
    assert pop.loc[("22", "012", "0012", 2000), cols].tolist() == [1960, 3402, 1664]
    assert ("22", "012", "0013", 2013) not in pop.index
    mirror("habitantes", 23, [("230010001", "2020", "1", "Censo", "12 hab", "*", "*")])
    mirror("movimientos", 23, [])
    with pytest.raises(ValueError, match="unexpected values"):
        mxcensus.load_ahl_poblacion(state=23)


# --------------------------------------------------------------------------- localities

def test_localidades(mirror):
    mirror("maestro", 4, [
        ("040010001", "20°22'16.415\"N", "90°03'02.660\"W", "13", "F15D79", "U", "Campeche",
         "Calkiní"),
        ("040010002", "20°07'27.634¨N", "111°23'53.057\"O", "-5", "E13B-54", "R", "Campeche",
         "Calkiní"),
        ("040010003", "18°30'310.00\"N", "102°3'´39.469\"", "", "\tF12B44", "0", "Campeche",
         "Calkiní"),
        ("040010004", "", "", "", "null", "R", "Campeche", "Calkiní"),
        ("040010005", "40°00'00.000\"N", "90°00'00.000\"W", "", "001970", "", "Campeche",
         "Calkiní"),
    ])
    mirror("movimientos", 4, [
        ("040010001", "2", "Calkiní (Cab.)", "Calkiní", "Ciudad", "", "Censo de 2020."),
        ("040010001", "1", "Calkiní", "Calkiní", "Villa", "", "Censo de 1990."),
        ("040010002", "1", "Isla Arena", "Calkiní", "Pueblo", "Comisaría", "Censo de 2020."),
        ("040010003", "1", "Bacabchén", "Calkiní", "Pueblo", "", "Censo de 2020."),
        ("040010004", "1", "Bécal", "Calkiní", "Villa", "", "Censo de 2020."),
        ("040010005", "1", "Concepción", "Calkiní", "Pueblo", "", "Censo de 2020."),
    ])
    loc = mxcensus.load_ahl_localidades(state=4)
    assert loc.index.names == ["CVE_ENT", "CVE_MUN", "CVE_LOC"]
    assert list(loc.columns) == ["NOM_ENT", "NOM_MUN", "NOM_LOC", "CAT_POLI", "CAT_ADMIVA",
                                 "AMBITO", "LATITUD", "LONGITUD", "ALTITUD", "CARTA_TOPO"]
    first = loc.loc[("04", "001", "0001")]
    assert (first["NOM_LOC"], first["CAT_POLI"], first["AMBITO"]) == (
        "Calkiní (Cab.)", "Ciudad", "Urbana")                  # the last event
    assert first["LATITUD"] == pytest.approx(20 + 22 / 60 + 16.415 / 3600)
    assert first["LONGITUD"] == pytest.approx(-(90 + 3 / 60 + 2.660 / 3600))
    second = loc.loc[("04", "001", "0002")]
    assert second["LATITUD"] == pytest.approx(20.124343, abs=1e-6)   # «¨» for «"»
    assert second["LONGITUD"] == pytest.approx(-111.398071, abs=1e-6)  # «O» = oeste
    assert (second["ALTITUD"], second["CARTA_TOPO"]) == (-5, "E13B54")
    third = loc.loc[("04", "001", "0003")]
    assert pd.isna(third["LATITUD"])                          # 310 seconds
    assert third["LONGITUD"] == pytest.approx(-(102 + 3 / 60 + 39.469 / 3600))  # no hemisphere
    assert pd.isna(third["AMBITO"]) and third["CARTA_TOPO"] == "F12B44"
    assert loc.loc[("04", "001", "0004"), ["LATITUD", "CARTA_TOPO"]].isna().all()
    assert pd.isna(loc.loc[("04", "001", "0005"), "LATITUD"])   # outside Mexico
    assert pd.isna(loc.loc[("04", "001", "0005"), "CARTA_TOPO"])
    assert str(loc["LATITUD"].dtype) == "Float64" and str(loc["ALTITUD"].dtype) == "Int64"

    geo = mxcensus.load_ahl_localidades(state=4, geometry=True)
    assert geo.crs == "EPSG:4326" and geo.index.equals(loc.index)
    assert geo.geometry.isna().tolist() == [False, False, True, True, True]
    assert geo.geometry.iloc[0].x == pytest.approx(first["LONGITUD"])


# --------------------------------------------------------------------------- real data

_REAL = all((_MIRROR / ahl_filename(t, s)).exists() for t in TABLES for s in (4, 22)) and all(
    (_MIRROR / f"cpv_iter_{p}_{s:02d}.parquet").exists()
    for p in (1990, 1995, 2000, 2005, 2010, 2020) for s in (4, 22))


@pytest.fixture
def real(monkeypatch):
    from mxcensus.data import _registry
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda name, **kw: str(_MIRROR / name))


@pytest.mark.skipif(not _REAL, reason="needs the AHL and ITER files of states 04 and 22")
def test_real_against_the_iter(real):
    # Querétaro: every locality and every total 1995–2020 equal to the ITER (2000 and 1995's
    # «D, LA» shifted back); Campeche: INEGI's copies of 2010 and 2020 dropped
    totals = {22: {1990: (1_051_235, 1_051_202), 1995: (1_246_445, 1_246_445),
                   2000: (1_404_306, 1_404_306), 2005: (1_598_139, 1_598_139),
                   2010: (1_827_937, 1_827_937), 2020: (2_368_467, 2_368_467)},
              4: {2000: (690_689, 690_684), 2010: (822_441, 822_450),
                  2020: (928_363, 928_383)}}
    for state, years in totals.items():
        pop = mxcensus.load_ahl_poblacion(state=state)
        for year, (iter_total, ahl_total) in years.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")              # the ITERs' repaired names
                it = mxcensus.load_cpv_iter(year, state=state, nivel="localidad", impute=False)
            a = pop.xs(year, level="EVE_CENSAL")
            assert (int(it["POBTOT"].sum()), int(a["POBTOT"].sum())) == (iter_total, ahl_total)
            j = it[["POBTOT", "POBMAS"]].join(a[["POBTOT", "POBMAS"]], rsuffix="_ahl",
                                              how="inner")
            known = j["POBTOT"].notna() & j["POBTOT_ahl"].notna()
            assert (j.loc[known, "POBTOT"] == j.loc[known, "POBTOT_ahl"]).all(), (state, year)
            sexes = j["POBMAS"].notna()
            assert (j.loc[sexes, "POBMAS"] == j.loc[sexes, "POBMAS_ahl"]).all(), (state, year)
    full = mxcensus.load_ahl_poblacion(state=4, copies=True)
    copies = full[full["COPIA"]].index.get_level_values("EVE_CENSAL").value_counts()
    assert copies.to_dict() == {2020: 65, 2010: 32}
    assert full.loc[("04", "013", "0001", 2020), "COPIA"]
    assert not full.loc[("04", "001", "0007", 2020), "COPIA"]
    loc = mxcensus.load_ahl_localidades(state=4)
    assert len(loc) == 9_378 and loc.index.is_unique
    assert loc.loc[("04", "001", "0007"), "NOM_LOC"] == "Dzitbalché"


@pytest.mark.skipif(not _AHL_ZIP.exists(), reason="needs data/dict/ahl/AHL.zip")
def test_rebuild_matches_the_registry(tmp_path):
    from mxcensus.data._registry import POOCH
    import pooch
    written = build_ahl.build(_AHL_ZIP, tmp_path, [1, 4])
    assert len(written) == 8
    for path in written:
        assert pooch.file_hash(str(path)) == POOCH.registry[path.name], path.name
