"""Tests for the cross-edition municipal geography (``mxcensus.cpv_geo``, unit 6a).

Offline tests read the bundled ``cpv_mun_lineage.yaml``; the ``_REAL`` tests rebuild it from
the Marco Geoestadístico municipal layers in ``data/parquet`` and join it to the ITER.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

import mxcensus
from mxcensus._resources import cpv_mun_lineage as lineage_doc
from mxcensus.cpv_geo import cpv_mun_lineage, cpv_municipal_units
from mxcensus.data._catalog import mg_filename

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_PERIODS = ("1995", "2000", "2005", "2010", "2015", "2020", "2025")


def test_lineage_document():
    doc = lineage_doc()
    assert doc["periodos"] == list(_PERIODS)
    assert doc["municipios"] == {"1995": 2_428, "2000": 2_443, "2005": 2_454, "2010": 2_456,
                                 "2015": 2_457, "2020": 2_469, "2025": 2_478}
    assert len(doc["claves"]) == len(set(doc["claves"])) == doc["municipios"]["2025"]
    lin = cpv_mun_lineage()
    created = lin.groupby(["PERIOD_FROM", "PERIOD_TO"])["CVEGEO"].nunique()
    for old, new in zip(_PERIODS[:-1], _PERIODS[1:]):   # codes are never retired
        assert created[(old, new)] == doc["municipios"][new] - doc["municipios"][old]
    assert ((lin["SHARE_NEW"] >= 0.05) & (lin["SHARE_NEW"] <= 1)).all()
    assert ((lin["SHARE_PARENT"] > 0) & (lin["SHARE_PARENT"] <= 1)).all()
    assert set(lin["CVEGEO"]) <= set(doc["claves"]) and set(lin["PARENT"]) <= set(doc["claves"])
    main = lin.sort_values("SHARE_NEW").groupby("CVEGEO").tail(1)
    assert (main["CVEGEO"].str[:2] == main["PARENT"].str[:2]).all()    # its main parent's state
    assert lin.loc[lin["CVEGEO"] == "02007", "PARENT"].tolist() == ["02001", "02002"]
    # 6h: the EIC 2015 frame dates Bacalar (2011) to 2010 → 2015, the other 12 to 2015 → 2020
    assert lin.loc[lin["PERIOD_TO"] == "2015", "CVEGEO"].unique().tolist() == ["23010"]


def test_municipal_units():
    u = cpv_municipal_units(2020, 2025)
    assert len(u) == 2_478 and u["CVEGEO"].is_unique
    bc = u.set_index("CVEGEO").loc[["02001", "02002", "02007"]]
    assert set(bc["UNIT"]) == {"02001"} and bc.loc["02007", "FIRST"] == "2025"
    assert (u.loc[u["CVEGEO"] == "01001", ["UNIT", "FIRST"]].values == [["01001", "2020"]]).all()
    assert cpv_municipal_units(2015, 2020).set_index("CVEGEO").loc["23011", "FIRST"] == "2020"
    assert len(cpv_municipal_units(2015, 2015)) == 2_457
    same = cpv_municipal_units("2000", "2000")
    assert len(same) == 2_443 and (same["UNIT"] == same["CVEGEO"]).all()
    wide = cpv_municipal_units(1995, 2025)
    assert len(wide) == 2_478 and wide["UNIT"].nunique() < cpv_municipal_units(2010, 2025)["UNIT"].nunique()
    # Bacalar (23009, 2010) took 5% from Yucatán's 31019 (a boundary dispute): ignored by
    # default, joined only across states and below the default share
    assert wide.set_index("CVEGEO").loc["31019", "UNIT"] == "31019"
    loose = cpv_municipal_units(2005, 2010, min_share=0.05, cross_state=True).set_index("CVEGEO")
    assert loose.loc["31019", "UNIT"] == loose.loc["23009", "UNIT"]
    with pytest.raises(ValueError, match="1990 has none"):
        cpv_municipal_units(1990, 2020)
    with pytest.raises(ValueError, match="after end"):
        cpv_municipal_units(2020, 2000)
    assert mxcensus.cpv_municipal_units is cpv_municipal_units


_REAL = all((_MIRROR / mg_filename("mun", s, p)).exists() for p in _PERIODS for s in range(1, 33))


@pytest.mark.skipif(not _REAL, reason="needs the municipal layers of every MG frame")
def test_lineage_rebuilds_from_the_frames():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_geo_crosswalk as b
    assert b.build(_MIRROR) == {k: v for k, v in lineage_doc().items()}


_ITER = all((_MIRROR / f"cpv_iter_{p}_{s:02d}.parquet").exists() for p in ("2000", "2020")
            for s in range(1, 33))


@pytest.mark.skipif(not _ITER, reason="needs the 2000 and 2020 ITER of every state")
def test_units_cover_the_iter(monkeypatch):
    from mxcensus.data import _registry
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda f, **_: str(_MIRROR / f))
    units = cpv_municipal_units(2000, 2020)
    sums = {}
    for p in ("2000", "2020"):
        it = mxcensus.load_cpv_iter(p, state=list(range(1, 33)), nivel="municipal").reset_index()
        it["CVEGEO"] = it["CVE_ENT"] + it["CVE_MUN"]
        merged = it.merge(units, on="CVEGEO", how="left")
        assert merged["UNIT"].notna().all(), p
        sums[p] = merged.groupby("UNIT")["POBTOT"].sum()
    assert sums["2000"].index.equals(sums["2020"].index)      # one common set of units
    assert int(sums["2000"].sum()) == 97_483_412


# --------------------------------------------------------------------------- localities (7t)

from mxcensus._resources import cpv_loc_lineage as loc_doc  # noqa: E402
from mxcensus.cpv_geo import cpv_loc_lineage, cpv_locality_units  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_LOC_PERIODS = ("1990", "1995", "2000", "2005", "2010", "2020", "2025")
_CUTS = {"1990": "1990-03-12", "1995": "1995-11-05", "2000": "2000-02-14",
         "2005": "2005-10-30", "2010": "2010-10-15", "2020": "2020-12-31",
         "2025": "2025-12-31"}


def _links(lin, frm, to=None):
    rows = lin[lin["FROM"] == frm]
    return rows if to is None else rows[rows["TO"] == to]


def test_locality_lineage_document():
    lin = cpv_loc_lineage()
    assert list(lin.columns) == ["PERIOD", "DATE", "EVENT", "KIND", "FROM", "TO", "CONFIRMED"]
    assert list(lin["KIND"].cat.categories) == ["code", "absorption", "counted_with",
                                                "separation"]
    assert set(lin["PERIOD"]) == set(_LOC_PERIODS)
    assert set(lin["EVENT"]) == {"census", "update", "other"}
    assert lin["FROM"].str.fullmatch(r"\d{9}").all() and lin["TO"].str.fullmatch(r"\d{9}").all()
    assert (lin["FROM"] != lin["TO"]).all()
    assert not lin.duplicated(["PERIOD", "KIND", "FROM", "TO"]).any()
    # each link dated within its edition: after the previous cut, on or before its own —
    # but the few a census shows in effect only later (8b: moved, 44)
    cut = lin["PERIOD"].map(_CUTS).astype("datetime64[us]")
    prev = lin["PERIOD"].map(lambda p: _CUTS[_LOC_PERIODS[max(_LOC_PERIODS.index(p) - 1, 0)]])
    assert (lin["DATE"] <= cut).all()
    later = lin["PERIOD"] != "1990"
    early = lin.loc[later, "DATE"] <= prev[later].astype("datetime64[us]")
    assert early.sum() <= 50
    assert set(lin.loc[early[early].index, "KIND"]) <= {"absorption", "separation"}
    # only the localities counted with another at the 1990 census are in effect by 1990
    assert set(lin.loc[lin["PERIOD"] == "1990", "KIND"]) == {"counted_with"}
    assert set(lin.loc[lin["KIND"] == "counted_with", "PERIOD"]) == {"1990", "1995"}
    confirmed = lin.groupby("KIND", observed=True)["CONFIRMED"].mean()
    assert (confirmed[["code", "absorption", "separation"]] > 0.7).all()
    # Playas de Rosarito: its cabecera moved from Tijuana (004) to the new municipality 005
    # in 1995 (a remnant kept the old code), the remnant was conurbated in 2004
    assert _links(lin, "020040223").set_index("KIND")["TO"].to_dict() == {
        "code": "020050001", "absorption": "020050001"}
    assert _links(lin, "020040223", "020050001")["CONFIRMED"].all()
    # Loreto, BCS: «Pasa al municipio Loreto 009 con la clave 0001» (no parentheses)
    row = _links(lin, "030010002", "030090001").iloc[0]
    assert (row["KIND"], row["PERIOD"], row["CONFIRMED"]) == ("code", "1995", True)
    # Real Cumbres: «Se conurba a Ciudad Monterrey (0001)» (another municipality, placed by
    # its name), which Monterrey's record confirms; Escobedo's rival claim is dropped
    assert _links(lin, "190210134")["TO"].tolist() == ["190390001"]
    # dated by updates: a 2018 move (Censo 2020), a 2025 conurbation (the MG 2025 frame)
    assert _links(lin, "020041198", "020031831")["PERIOD"].tolist() == ["2020"]
    row = _links(lin, "010012150", "010010001").iloc[0]
    assert (row["KIND"], row["PERIOD"], str(row["DATE"].date())) == (
        "absorption", "2025", "2025-06-30")
    assert len(loc_doc()) == len(lin)
    assert mxcensus.cpv_loc_lineage is cpv_loc_lineage


def test_locality_units():
    u = cpv_locality_units(2000, 2020)
    assert list(u.columns) == ["CVEGEO", "UNIT"] and u["CVEGEO"].is_unique
    assert (u["UNIT"] <= u["CVEGEO"]).all() and set(u["UNIT"]) <= set(u["CVEGEO"])
    unit = u.set_index("CVEGEO")["UNIT"]
    assert unit["020040223"] == unit["020050001"]           # conurbated in 2004
    assert "020040001" not in unit or unit["020040001"] != unit["020050001"]
    assert unit["190210134"] == unit["190390001"]           # Real Cumbres → Monterrey
    assert "190210001" not in unit or unit["190210001"] != unit["190390001"]
    early = cpv_locality_units(1990, 1995).set_index("CVEGEO")["UNIT"]
    assert early["020040223"] == early["020050001"]          # the 1995 move
    for start, end in ((1990, 1995), (1990, 2020)):          # San Antonio's rival claims:
        span = cpv_locality_units(start, end).set_index("CVEGEO")["UNIT"]   # Escobedo
        assert span.get("190210001", "a") != span.get("190100001", "b")     # apart from El
    assert "190100027" not in early                                         # Carmen
    assert early["030010002"] == early["030090001"]
    assert early["240370286"] == early["240370037"]          # counted with it in 1990
    late = cpv_locality_units(2010, 2020).set_index("CVEGEO")["UNIT"]
    assert "020040223" not in late                           # nothing in 2010 → 2020
    assert late["020041198"] == late["020031831"]
    assert len(cpv_locality_units(2010, "2010")) == 0
    # a wider span joins at least what a narrower one does
    wide = cpv_locality_units(1990, 2025)
    assert set(u["CVEGEO"]) <= set(wide["CVEGEO"])
    assert wide["UNIT"].nunique() < len(wide)
    # absorptions=False: the same locality under another code only
    codes_only = cpv_locality_units(2020, 2025, absorptions=False).set_index("CVEGEO")["UNIT"]
    full = cpv_locality_units(2020, 2025).set_index("CVEGEO")["UNIT"]
    assert "010012150" in full and "010012150" not in codes_only
    assert len(codes_only) < len(full)
    lin = cpv_loc_lineage()
    conf = lin[(lin["PERIOD"] == "2025") & lin["CONFIRMED"]]
    strict = cpv_locality_units(2020, 2025, confirmed=True)
    assert set(strict["CVEGEO"]) == set(conf["FROM"]) | set(conf["TO"])
    assert len(strict) < len(full)
    with pytest.raises(ValueError, match="no locality codes"):
        cpv_locality_units(2015, 2020)
    with pytest.raises(ValueError, match="no locality codes"):
        cpv_locality_units(1985, 1990)
    with pytest.raises(ValueError, match="after end"):
        cpv_locality_units(2020, 2000)
    assert mxcensus.cpv_locality_units is cpv_locality_units


def _build_module():
    sys.path.insert(0, str(_SCRIPTS))
    import build_loc_lineage
    return build_loc_lineage


def test_loc_lineage_parser():
    b = _build_module()
    from datetime import date
    assert b.event("Censo de 2010. Localidad deshabitada.") == ("census", date(2010, 6, 12))
    assert b.event("Conteo de 1995.") == ("census", date(1995, 11, 5))
    assert b.event("Actualización Geoestadística del 15 de junio de 2019.") == (
        "update", date(2019, 6, 15))
    assert b.event("Actualización Geostadística del 31 de junio de 2004.") == (
        "update", date(2004, 6, 28))
    assert b.event("Decreto No. 872 del 20 de agosto de 1992. Viene del…") == (
        "other", date(1992, 8, 20))
    assert b.event("Sin información.") == ("other", None)
    # an edition's cut: the Conteo 2005 has the update of 30 October 2005, not the next day's
    assert b.edition_of(date(2005, 10, 30)) == "2005"
    assert b.edition_of(date(2005, 10, 31)) == "2010"
    assert b.edition_of(date(2020, 11, 17)) == "2020"
    assert b.edition_of(date(2026, 1, 1)) is None
    st = b.statements
    assert st("Censo de 1990. Pasa al municipio Pabellón de Arteaga (006) con clave (0264).") == {
        "pasa": [("006", "0264")]}
    assert st("Decreto No. 872. Pasa al municipio Loreto 009 con la clave 0001.")["pasa"] == [
        ("009", "0001")]
    assert st("Viene del municipio Comondú (001) y clave de localidad 0002.")["viene"] == [
        ("001", "0002")]
    assert st("Viene del municipio Escárcega (009). con clave de localidad (0350).")["viene"] == [
        ("009", "0350")]
    assert st("Conteo de 1995. Pasa al municipio Nadadores (021).") == {
        "pasa_sin": [("Nadadores", "021")]}
    assert st("Pasa al estado de Oaxaca (20) en el municipio de Juchitán (043) con clave de "
              "localidad (0012).")["pasa_estado"] == [("20", "043", "0012")]
    assert st("A esta localidad se conurban las 010010114, 010010707 y 010012460.")[
        "absorbe"] == [("010010114, 010010707 y 010012460",)]
    assert st("Se conurba a Acatepec (San Antonio) (0054).")["absorbida"] == [
        ("", "", "", "", "", "Acatepec (San Antonio)", "0054", "")]
    assert st("Se fusiona a San Juan (0003) del municipio de Tlaxco (034).")["absorbida"] == [
        ("", "", "", "", "", "San Juan", "0003", "034")]
    assert st("Se conurba a Ciudad Ixtepec, clave (200430001).")["absorbida"] == [
        ("", "Ciudad Ixtepec", "200430001", "", "", "", "", "")]
    assert st("Conurbada a Tenabo, con clave (0001).")["absorbida"] == [
        ("", "Tenabo", "0001", "", "", "", "", "")]
    assert st("Se fusiona a (0321) Los Laureles.")["absorbida"] == [            # name after
        ("", "", "", "0321", "Los Laureles", "", "", "")]
    assert st("Se fusiona a la localidad (0105) del municipio de San Martín Chalchicuautla "
              "(029).")["absorbida"] == [("", "", "", "", "", "", "0105", "029")]
    assert sorted(re.findall(r"\d{9}", st(
        "A esta localidad se conurban las 151060169, 151060189 y parte de las localidades "
        "151060125, 151060152 y 151060158.")["absorbe"][0][0])) == [
        "151060125", "151060152", "151060158", "151060169", "151060189"]
    # «A esta localidad se conurba a …» (an «a» too many) lists the absorbed; «Esta
    # localidad se conurba a …» is the record's own absorption
    assert st("Actualización Geoestadística del 15 de abril de 2015. a esta localidad se "
              "conurba a 220140470.") == {"absorbe": [("220140470",)]}
    assert st("A esta localidad se conurban a las 190060218 y 190060379.") == {
        "absorbe": [("190060218 y 190060379",)]}
    assert st("Censo de 2010. Esta localidad se conurba a Galeana (0001)")["absorbida"] == [
        ("", "", "", "", "", "Galeana", "0001", "")]
    assert st("De esta localidad se desconurba la 110460072.")["separa"] == [("110460072",)]
    assert st("Localidad desagregada de la localidad Xolol (0021).")["separada"] == [
        ("", "", "", "Xolol", "0021", "")]
    assert st("Se desfusiona de (0322) Nuevo Progreso Dos.")["separada"] == [
        ("", "0322", "Nuevo Progreso Dos", "", "", "")]
    assert st("Se censó con la localidad El Potrero (0199).")["censo_con"] == [
        ("El Potrero", "0199")]
    assert st("Es la misma localidad (0046) del municipio (012).")["misma"] == [("0046", "012")]
    assert st("En este evento se censó con clave de localidad (0041).") == {
        "censo_clave": [("0041",)]}
    # the code written another way after the municipality (7t's leftovers)
    for text, key, code in (
            ("Viene del municipio Escárcega 009. Decreto No. 66 del 23 de junio de 1998. con "
             "clave de localidad 0144.", "viene", ("009", "0144")),
            ("Pasa al municipio Hecelchakán (005),con clave de localidad (0064).", "pasa",
             ("005", "0064")),
            ("Pasa al municipio Huichapan (029), localidad El Betel (0119).", "pasa",
             ("029", "0119")),
            ("Viene del municipio Pesquería (041) de la localidad (0077).", "viene",
             ("041", "0077")),
            ("Viene del municipio de Rioverde (024) con nombre y clave El Tepetate (0278).",
             "viene", ("024", "0278")),
            ("Pasa al municipio Huichapan (029), El Jarillal con clave de localidad (0123).",
             "pasa", ("029", "0123")),
            ("Viene del municipio Manuel Doblado (008) en donde tenía la clave (0313).",
             "viene", ("008", "0313")),
            ("Pasa del municipio de San Luis de la Paz (033) en el que tenía la clave (0169) al "
             "municipio de Dolores Hidalgo (014).", "viene", ("033", "0169")),
            ("Esta localidad anteriormente tenía la clave 0135.", "antes", ("0135",)),
            ("Anteriormente tenia la clave 250170584.", "antes", ("250170584",))):
        assert st(text)[key] == [code], text
    # renumbering inside a record: «hasta» closes a code, «cambia» opens the next
    rows = [b.Row("230060378", i, "San Juan", t, *b.event(t), b.statements(t)) for i, t in (
        (1, "Censo de 1980. Hasta este evento la localidad estuvo registrada con clave 230060044."),
        (2, "Censo de 1990. A partir de este evento cambia a la clave 230060378."),
        (3, "Conteo de 1995."))]
    links = b.record_links(rows)
    assert [(l.source, l.target, l.kind, l.day) for l in links] == [
        ("230060044", "230060378", "code", date(1990, 3, 12))]
    # a locality number stated with a name goes to the locality of that name
    rows = [b.Row(c, 1, n, "", "census", date(2000, 2, 14)) for c, n in (
        ("150910001", "Teoloyucan"), ("150240001", "Cuautitlán"),
        ("151210001", "Cuautitlán Izcalli (Cab.)"), ("150910028", "Santa Bárbara"))]
    resolve = b.Resolver(rows)
    assert resolve("15", "091", "0001", "Cuautitlán Izcalli") == ("151210001", True)
    assert resolve("15", "091", "0001", "Teoloyucan") == ("150910001", True)
    assert resolve("15", "091", "0001", "Nowhere") == ("150910001", False)
    assert b.name_match("Playas de Rosarito", "Playas de Rosarito (Cab.)") == 2
    assert b.name_match("El Refugio (El Conejo)", "San Ramón") == 0
    assert b.name_match("Cd. Juarez", "Ciudad Juárez") == 2                # abbreviations
    assert b.name_match("La Elvira I", "La Elvira Uno") == 2                # ordinals
    assert b.name_match("Tlacopa", "Tlacoapa (Cab.)") == 1                  # a misspelling
    assert b.name_match("Tlacopa", "Tlacoapa (Cab.)", fuzzy=False) == 0
    assert b.name_match("Ninguno", "Ninguno") == 0                         # placeholders
    assert b.name_match("Localidad Sin Nombre", "Rancho Sin Nombre") == 0
    assert b.name_match("La Ciudad", "Ciudad") == 1     # generic words only: no placeholder
    rows = [b.Row(c, 1, n, "", "census", date(2000, 2, 14)) for c, n in (
        ("120630001", "Tlacoapa (Cab.)"), ("120010001", "Acapulco de Juárez"))]
    assert b.Resolver(rows)("12", "063", "0001", "Tlacopa") == ("120630001", True)
    # the record's own name with another locality's number: it names itself, no link; a
    # number no record has stays an unverified link
    t = ("Actualización Geoestadística del 15 mayo de 2008 Se conurba a Colinas del "
         "Areopuerto (0001).")
    rows = [b.Row("190410001", 1, "Pesquería (Cab.)", "", "census", date(2010, 6, 12)),
            b.Row("190410337", 1, "Colinas del Aeropuerto", t, *b.event(t), b.statements(t))]
    resolve = b.Resolver(rows)
    assert [l.verified for l in b.record_links(rows[1:], resolve)] == [None]
    assert resolve("19", "041", "4713", "López", "", "Rancho López") == ("190414713", False)
    # parse keeps such a statement only when the other record states the link (San Juan's
    # number was right: Xaltetipa lists it)
    mov = pd.DataFrame([(c, "1", n, t) for c, n, t in (
        ("190410001", "Pesquería (Cab.)", "Censo de 2010."),
        ("190410337", "Colinas del Aeropuerto", t),
        ("211380009", "Xaltetipa", "Actualización Geoestadística del 15 de junio de 2009. A "
                                   "esta localidad se fusiona la 211380013."),
        ("211380013", "San Juan", "Actualización Geoestadística del 15 de junio de 2009. Se "
                                  "fusiona a San Juan (0009).")
    )], columns=["CVE_GEOEST", "INDICE", "NOM_LOC", "ORI_MODIF"])
    rows, links, placed = b.parse(mov)
    assert {(l.source, l.target, l.record, l.verified) for l in links} == {
        ("211380013", "211380009", "211380009", True),
        ("211380013", "211380009", "211380013", True)}
    assert placed["its own name"] == 1 and placed["its own name, stated by the other"] == 1
    # a move stated without the code beside an absorption: the absorber is in the
    # municipality it moves to
    t = "Conteo de 2005. Pasa al municipio Tultitlán (109). Se conurba a San Pablo (0025)."
    rows = [b.Row("151080048", 1, "San Pablo", t, *b.event(t), b.statements(t))]
    assert [(l.source, l.target, l.kind) for l in b.record_links(rows)] == [
        ("151080048", "151090025", "absorption")]


def _history(*records):
    """History rows from (code, [(index, name, text), …]) and every link they state."""
    b = _build_module()
    rows = [b.Row(code, i, name, t, *b.event(t), b.statements(t))
            for code, events in records for i, name, t in events]
    links = [l for code, _ in records
             for l in b.record_links([r for r in rows if r.code == code])]
    return b, rows, links


def test_loc_lineage_unkeyed_moves():
    from datetime import date
    latest = date(2026, 9, 18)
    b, rows, links = _history(
        # confirmed by the other record's unkeyed statement
        ("040032696", [(1, "La Esperanza", "Conteo de 1995."),
                       (2, "La Esperanza", "Censo de 2000. Pasa al municipio Candelaria 011.")]),
        ("040110185", [(1, "La Esperanza", "Censo de 2000. Viene del municipio Carmen (003) "
                                           "con clave de localidad (2696).")]),
        # paired by name though renamed («La Joringa» → «La Jeringa»)
        ("040030063", [(1, "La Joringa", "Censo de 1990."),
                       (2, "La Joringa", "Conteo de 1995. Pasa al municipio Escárcega (009).")]),
        ("040090589", [(1, "La Joringa", "Censo de 1980."),
                       (2, "La Jeringa", "Conteo de 1995. Cambio de nombre de localidad. "
                                         "Viene del municipio Carmen 003.")]),
        # one side: the only «San Carlos» of Ramos Arizpe there in 1995
        ("050300604", [(1, "San Carlos", "Censo de 1990."),
                       (2, "San Carlos", "Conteo de 1995. Pasa al municipio Ramos Arizpe "
                                         "(027).")]),
        ("050270086", [(1, "San Carlos", "Censo de 1910."), (2, "San Carlos", "Censo de 2000.")]),
        ("050270999", [(1, "San Carlos", "Censo de 1960. Baja de localidad.")]))
    extra, counts, left = b.pair_unkeyed(rows, links, latest)
    got = {(l.source, l.target, l.record) for l in extra}
    assert ("040032696", "040110185", "040032696") in got
    assert {("040030063", "040090589", "040030063"),
            ("040030063", "040090589", "040090589")} <= got
    assert ("050300604", "050270086", "050300604") in got          # not the one gone by 1960
    assert counts["confirms a code link"] == 1 and counts["paired by name"] == 2
    assert counts["one side, by name"] == 1 and left.empty
    table, rivals, fixes = b.lineage(rows, links + extra, latest)
    assert table.set_index("FROM").loc["040032696", "CONFIRMED"]


def test_loc_lineage_rival_claims():
    from datetime import date
    latest = date(2026, 9, 18)
    b, rows, links = _history(
        # the old record points to 0129, whose own record names another origin
        ("040030889", [(1, "Las Delicias de los Tres Hermanos", "Censo de 2000. Pasa al "
                        "municipio Candelaria (011) con clave de localidad (0129).")]),
        ("040110127", [(1, "Las Delicias de los Tres Hermanos", "Censo de 2000. Viene del "
                        "municipio Carmen (003) con clave de localidad (0889).")]),
        ("040110129", [(1, "Las Delicias", "Censo de 2000. Viene del municipio Carmen (003) "
                        "con clave de localidad (0887).")]),
        # a locality that goes on under its own code: neither claim is a renumbering
        ("190100027", [(1, "San Antonio", "Censo de 1990. Localidad deshabitada."),
                       (2, "San Antonio", "Conteo de 1995. pasa al municipio de General "
                        "Escobedo(021) con clave de localidad (0001)."),
                       (3, "San Antonio", "Censo de 2010.")]),
        ("190100001", [(1, "El Carmen (Cab.)", "Conteo de 1995. Viene del municipio de China "
                        "(010) con clave de localidad (0027).")]),
        ("190210001", [(1, "General Escobedo (Cab.)", "Censo de 1990.")]),
        # a locality split in two, each part stating it as its origin
        ("300450073", [(1, "Cerro de Torres", "Censo de 2000. Baja de localidad.")]),
        ("302080014", [(1, "Cerro de Torres Dos", "Decreto No. 26 del 30 de noviembre de 1996. "
                        "Viene del municipio de Cosamaloapan (045) con clave de localidad "
                        "(0073).")]),
        ("302080015", [(1, "Cerro de Torres 1", "Decreto No. 26 del 30 de noviembre de 1996. "
                        "Viene del municipio de Cosamaloapan (045) con clave de localidad "
                        "(0073).")]))
    table, rivals, fixes = b.lineage(rows, links, latest)
    to = table.groupby("FROM")["TO"].apply(set).to_dict()
    assert to["040030889"] == {"040110127"} and to["040030887"] == {"040110129"}
    assert "190100027" not in to
    assert to["300450073"] == {"302080014", "302080015"}
    rule = rivals.drop_duplicates("FROM").set_index("FROM")["RULE"]
    assert rule["040030889"] == "the target states another origin"
    assert rule["190100027"].startswith("undecided, the locality keeps its code")
    assert rule["300450073"] == "each states it as its origin (all kept)"


def test_loc_lineage_list_slips():
    from datetime import date
    b, rows, links = _history(
        # Telchac's list names Mayapán's 0052 and 0061 for its own, which state it that day
        ("310820001", [(1, "Telchac (Cab.)", "Actualización Geoestadística del 15 de octubre "
                        "de 2014. A esta localidad se conurba la 310490052 y 310490061")]),
        ("310820052", [(1, "Tres Hermanos", "Actualización Geoestadística del 15 de octubre de "
                        "2014. Se conurba a Telchac Pueblo (0001).")]),
        ("310820061", [(1, "Ninguno", "Censo 2010. Creación de localidad."),
                       (2, "Ninguno", "Actualización Geoestadística del 15 de octubre de 2014. "
                        "Se conurba a Telchac Pueblo (0001).")]),
        ("310490052", [(1, "Mayapán", "Actualización Geoestadística del 15 de marzo de 2009. "
                        "Se conurba a Mayapán (0001).")]))
    fixed, log = b.repair_lists(links)
    assert set(zip(log["LISTED"], log["MEANT"])) == {("310490052", "310820052"),
                                                     ("310490061", "310820061")}
    table, rivals, fixes = b.lineage(rows, fixed, date(2026, 9, 18))
    got = dict(zip(zip(table["FROM"], table["TO"]), table["CONFIRMED"]))
    assert got[("310820052", "310820001")] and got[("310820061", "310820001")]
    assert ("310490052", "310820001") not in got
    assert ("310490052", "310490001") in got


def test_loc_lineage_own_records():
    from datetime import date
    b, rows, links = _history(
        # the same day, Zamora's record says absorbed and Múzquiz's that it left: its own
        ("050200772", [(1, "Zamora", "Conteo de 2005."),
                       (2, "Zamora", "Actualización Geoestadística del 15 de junio de 2009. Se "
                        "conurba a Ciudad Melchor Múzquiz (0001).")]),
        ("050200001", [(1, "Ciudad Melchor Múzquiz", "Actualización Geoestadística del 15 de "
                        "junio de 2009. De esta localidad se desconurban las 050200063 y "
                        "050200772.")]),
        # conurbed and separated again between two editions
        ("300440047", [(1, "La Luz", "Censo de 2000."),
                       (2, "La Luz", "Acuerdo del 23 de febrero de 2001. Se conurba a Córdoba "
                        "(0001)."),
                       (3, "La Luz", "Conteo de 2005. Se desconurba de Córdoba (0001).")]),
        # counted on its own at that edition's census: dropped from another's list, moved
        # when its own record states it
        ("260300001", [(1, "Hermosillo (Cab.)", "Actualización Geoestadística del 15 de julio "
                        "de 2019. A esta localidad se conurban las 260300535 y 260303510.")]),
        ("260303510", [(1, "Maccsa", "Actualización Geoestadística del 15 de julio de 2019. Se "
                        "conurba a Hemosillo (0001).")]),
        ("160530417", [(1, "Lomas de Chapultepec", "Actualización Geoestadística del 15 de "
                        "octubre de 2008. Se conurba a Morelia (0001).")]),
        # stated apart at the Censo 2000, first counted at the Conteo 2005
        ("290260001", [(1, "Santa Cruz Tlaxcala (Cab.)", "Censo de 2000. De esta localidad se "
                        "desconurban las 290260004 y 290260005.")]))
    counted = {"260300535": [date(2010, 6, 12), date(2020, 3, 15)],
               "160530417": [date(2005, 10, 17), date(2010, 6, 12)],
               "290260005": [date(2005, 10, 17), date(2010, 6, 12)]}
    table, rivals, fixes = b.lineage(rows, links, date(2026, 9, 18), counted)
    got = dict(zip(zip(table["FROM"], table["TO"], table["KIND"].astype(str)), table["PERIOD"]))
    assert got[("050200772", "050200001", "absorption")] == "2010"
    assert ("050200772", "050200001", "separation") not in got
    assert not [k for k in got if k[0] == "300440047"]
    assert ("260300535", "260300001", "absorption") not in got
    assert got[("260303510", "260300001", "absorption")] == "2020"
    assert got[("160530417", "160530001", "absorption")] == "2020"
    assert got[("290260005", "290260001", "separation")] == "2005"
    assert got[("290260004", "290260001", "separation")] == "2000"   # never counted: stays
    rule = dict(zip(zip(fixes["FROM"], fixes["KIND"]), fixes["RULE"]))
    assert rule[("050200772", "separation")] == "contradicted the same day"
    assert rule[("300440047", "absorption")] == rule[("300440047", "separation")] == (
        "joined and left")
    assert rule[("260300535", "absorption")] == "counted on its own"
    assert rule[("160530417", "absorption")] == rule[("290260005", "separation")] == "moved"


def test_loc_lineage_large_units():
    b = _build_module()
    table = pd.DataFrame({
        "PERIOD": ["2020", "2020", "2010"], "KIND": ["absorption", "absorption", "code"],
        "FROM": ["010010002", "010010003", "010010004"],
        "TO": ["010010003", "010010001", "010020001"], "CONFIRMED": [True, False, True]})
    locs = pd.DataFrame({
        "CODE": ["010010001", "010010002", "010010003", "010010004", "010020001"],
        "PERIOD": ["2010", "2010", "2010", "2005", "2010"],
        "NAME": ["Ciudad", "Pueblo", "Rancho", "Villa", "Villa"],
        "POP": [100_000, 5_000, 500, 3_000, 3_200]})
    xy = {"010010001": (21.88, -102.29), "010010002": (21.88, -102.0),
          "010010003": (21.88, -102.1)}
    n, large = b.large_units(table, locs, xy)
    assert n == 2              # the town joined through a ranch; the village renumbered
    assert large[["member", "flags"]].values.tolist() == [
        ["010010002 Pueblo", "far, through a smaller one, one record"]]


_AHL = Path(__file__).resolve().parent.parent / "data" / "dict" / "ahl" / "AHL.zip"
_ITERS = all((_MIRROR / f"cpv_iter_{p}_{s:02d}.parquet").exists()
             for p in _LOC_PERIODS[:-1] for s in range(1, 33))


@pytest.mark.skipif(not (_AHL.exists() and _ITERS),
                    reason="needs data/dict/ahl/AHL.zip and every ITER 1990-2020")
def test_loc_lineage_rebuilds_and_checks(tmp_path):
    b = _build_module()
    table, rows, stats = b.build(_AHL)
    out = tmp_path / "lin.csv.gz"
    b.write(table, out)
    bundled = Path(mxcensus.__file__).parent / "_yaml" / "cpv_loc_lineage.csv.gz"
    assert out.read_bytes() == bundled.read_bytes()
    codes = {p: c for p, c in b.edition_codes(_MIRROR).items() if p in _LOC_PERIODS[:-1]}
    result = b.check(table, rows, codes)
    contra = result["contradictions"]
    assert (contra["contradicted"] <= 0.03 * contra["links"]).all()
    for frame in (result["gone"], result["new"]):
        early = frame["span"] == "1990→1995"           # the Conteo 1995's gaps
        assert (frame.loc[~early, "unexplained"] <= 0.01 * frame.loc[~early, "codes"]).all()
        assert (frame.loc[early, "unexplained"] <= 0.015 * frame.loc[early, "codes"]).all()
