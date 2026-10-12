"""Tests for the cross-edition municipal geography (``mxcensus.cpv_geo``, unit 6a).

Offline tests read the bundled ``cpv_mun_lineage.yaml``; the ``_REAL`` tests rebuild it from
the Marco Geoestadístico municipal layers in ``data/parquet`` and join it to the ITER.
"""
from __future__ import annotations

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
    # each link dated within its edition: after the previous cut, on or before its own
    cut = lin["PERIOD"].map(_CUTS).astype("datetime64[us]")
    prev = lin["PERIOD"].map(lambda p: _CUTS[_LOC_PERIODS[max(_LOC_PERIODS.index(p) - 1, 0)]])
    assert (lin["DATE"] <= cut).all()
    later = lin["PERIOD"] != "1990"
    assert (lin.loc[later, "DATE"] > prev[later].astype("datetime64[us]")).all()
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
        ("", "", "Acatepec (San Antonio)", "0054", "")]
    assert st("Se fusiona a San Juan (0003) del municipio de Tlaxco (034).")["absorbida"] == [
        ("", "", "San Juan", "0003", "034")]
    assert st("Se conurba a Ciudad Ixtepec, clave (200430001).")["absorbida"] == [
        ("", "200430001", "", "", "")]
    assert st("De esta localidad se desconurba la 110460072.")["separa"] == [("110460072",)]
    assert st("Localidad desagregada de la localidad Xolol (0021).")["separada"] == [
        ("", "Xolol", "0021", "")]
    assert st("Se censó con la localidad El Potrero (0199).")["censo_con"] == [
        ("El Potrero", "0199")]
    assert st("Es la misma localidad (0046) del municipio (012).")["misma"] == [("0046", "012")]
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
