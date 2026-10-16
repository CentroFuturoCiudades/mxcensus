"""CPV census aggregates (unit 3c): ITER/AGEB loaders, the legacy-equal census builder and
the 2010 ↔ 2020 indicator crosswalk.

Offline tests use synthetic frames; the ``_REAL`` ones read the local mirror
(``data/parquet``) — state 01 on the Mac, all 32 states on ``wsl``.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa
import pytest

import mxcensus
from mxcensus import cpv as _cpv
from mxcensus import cpv_aggregates as ca
from mxcensus._resources import cpv_iter_crosswalk, cpv_schema_map, variables_cpv
from mxcensus.data._cpv_catalog import cpv_filename

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_cpv as _bcpv  # noqa: E402

_SM = cpv_schema_map()
_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"


def _gid(table: str, period: str) -> str:
    return next(g for g, m in _SM[table]["groups"].items() if period in m["periods"])


def _no_warnings():
    ctx = warnings.catch_warnings()
    ctx.__enter__()
    warnings.simplefilter("error")
    return ctx


# --- levels and imputation (synthetic) --------------------------------------------------------

def test_nivel_iter_and_ageb():
    it = pd.DataFrame({"CVE_MUN": ["000", "000", "001", "001", "001"],
                       "CVE_LOC": ["0000", "9998", "0000", "0001", "9999"]})
    assert ca._nivel_iter(it).tolist() == ["estatal", "agregado", "municipal", "localidad",
                                           "agregado"]
    assert ca._nivel_iter(it).cat.ordered
    ag = pd.DataFrame({"CVE_MUN": ["000", "001", "001", "001", "001"],
                       "CVE_LOC": ["0000", "0000", "0001", "0001", "0001"],
                       "CVE_AGEB": ["0000", "0000", "0000", "045A", "045A"],
                       "CVE_MZA": ["000", "000", "000", "000", "012"]})
    assert ca._nivel_ageb(ag).tolist() == ["estatal", "municipal", "localidad", "ageb", "manzana"]


def test_impute_zeros_only_where_forced():
    """A missing locality count becomes 0 only when the municipality's total already equals
    the sum of its localities' known values (``impute_zeros_univariate``)."""
    idx = pd.MultiIndex.from_tuples([("01", "001", "0001"), ("01", "001", "0002"),
                                     ("01", "002", "0001"), ("01", "002", "0002")],
                                    names=["CVE_ENT", "CVE_MUN", "CVE_LOC"])
    loc = pd.DataFrame({"A": pd.array([5, None, 3, None], dtype="Int64"),
                        "B": pd.array([None, 2, None, None], dtype="Int64"),
                        "NOM": ["a", "b", "c", "d"]}, index=idx)
    mun = pd.DataFrame({"A": pd.array([5, 4], dtype="Int64"), "B": pd.array([2, 0], dtype="Int64")},
                       index=pd.MultiIndex.from_tuples([("01", "001"), ("01", "002")],
                                                       names=["CVE_ENT", "CVE_MUN"]))
    out = ca._impute_zeros(mun, loc)
    assert out["A"].tolist() == [5, 0, 3, pd.NA]       # 001: 5 = 5 → the gap is 0; 002: 4 ≠ 3
    assert out["B"].tolist() == [0, 2, 0, 0]            # 001: 2 = 2; 002: 0 = 0
    assert out["NOM"].tolist() == loc["NOM"].tolist()   # non-counts untouched
    # the legacy function agrees on the same frames
    from mxcensus.aggregate import impute_zeros_univariate
    legacy = impute_zeros_univariate(mun, loc[["A", "B"]])
    assert legacy.equals(out[["A", "B"]])


def test_zero_empty_blocks():
    f = pd.DataFrame({"POBTOT": pd.array([0, 3, None], dtype="Int64"),
                      "TVIVHAB": pd.array([None, None, None], dtype="Int64"),
                      "VIVPAR_HAB": pd.array([None, 1, None], dtype="Int64")})
    out = ca._zero_empty_blocks(f)
    assert out["TVIVHAB"].tolist() == [0, pd.NA, pd.NA]
    assert out["VIVPAR_HAB"].tolist() == [0, 1, pd.NA]


# --- build: CSV header, dictionaries, sentinels -------------------------------------------------

def test_read_header_bom_before_quote(tmp_path):
    """CPV 2010's ITER/AGEB CSVs start with a BOM followed by a quoted name."""
    path = tmp_path / "x.csv"
    path.write_bytes('﻿"entidad","nom_ent","pobtot"\n01,Ags,10\n'.encode("utf-8"))
    assert _bcpv._read_header(path, "utf-8") == ["entidad", "nom_ent", "pobtot"]
    table, enc = _bcpv._read_csv_arrow(path)
    assert table.column_names == ["entidad", "nom_ent", "pobtot"] and enc == "utf-8"


def test_indicator_dictionary_members_and_sentinels():
    rx = _bcpv._INDICATOR_DICT_RE
    assert rx.search("iter_01_cpv2010/diccionario_de_datos/fd_iter_cpv2010.csv")
    assert rx.search("iter_01_cpv2020/diccionario_datos/diccionario_datos_iter_01CSV20.csv")
    assert not rx.search("iter_01_cpv2010/catalogos/tam_loc.csv")
    assert not rx.search("iter_01_cpv2010/conjunto_de_datos/iter_01_cpv2010.csv")
    assert set(_bcpv._AGG_SPECIALS["2010"]) == {"*", "N/D"}


def test_indicator_doc_codes_and_ageb_fallback(tmp_path):
    head = "numero,indicador,descripcion,mnemonico,rangos,longitud\n"
    d = tmp_path / "2010"
    d.mkdir()
    (d / "diccionario_datos_iter.csv").write_text(
        head + "1,Entidad,Nombre,nom_ent,Alfanumérico,50\n2,Población total,Total,pobtot,"
        "0..999999999,9\n3,Tamaño de localidad,Clase,tam_loc,1..14,2\n", encoding="cp1252")
    (d / "diccionario_datos_ageb.csv").write_text(
        head + "1,Población total,Total,pobtot,0..999999999,9\n", encoding="cp1252")
    it = _bcpv._indicator_doc(d / "diccionario_datos_iter.csv", "2010")
    assert it["tam_loc"]["Tipo"] == "string" and not it["tam_loc"]["Especiales"]
    assert it["pobtot"]["Tipo"] == "numeric" and set(it["pobtot"]["Especiales"]) == {"*", "N/D"}
    doc, prov = _bcpv._doc_for(tmp_path, "ageb", ["2010"])
    assert set(doc) == {"pobtot", "nom_ent", "tam_loc"} and prov.startswith("diccionario_datos_ageb")


# --- bundled metadata: groups, dictionaries, crosswalk ------------------------------------------

def test_schema_map_aggregate_groups():
    """ITER: 1990-2020 (chronological gids); AGEB: 2010 and 2020 only (no AGEB product
    before 2010)."""
    for table, editions in (("iter", {"1990": 46, "1995": 44, "2000": 132, "2005": 130,
                                      "2010": 200, "2020": 286}),
                            ("ageb", {"2010": 198, "2020": 230})):
        g = _SM[table]["groups"]
        assert [m["periods"] for m in g.values()] == [[p] for p in editions]
        assert {p: g[_gid(table, p)]["n_columns"] for p in editions} == editions
        assert all(m["files"] == 32 for m in g.values())
        assert _SM[table]["latest"] == _gid(table, "2020")


def test_aggregate_dictionaries():
    for table in ("iter", "ageb"):
        for period in ("2010", "2020"):
            v = variables_cpv(table, _gid(table, period))
            pob = next(m for k, m in v.items() if k.upper() == "POBTOT")
            assert pob["Tipo"] == "numeric" and "*" in pob["Especiales"]
    tam = {p: next(m for k, m in variables_cpv("iter", _gid("iter", p)).items()
                   if k.upper() in ("TAMLOC", "TAM_LOC")) for p in ("2010", "2020")}
    assert all(m["Tipo"] == "string" for m in tam.values())          # a class code


def test_crosswalk_covers_every_column_once():
    xw = cpv_iter_crosswalk()
    for table, periods in (("iter", ("1990", "1995", "2000", "2005", "2010", "2020")),
                           ("ageb", ("2010", "2020"))):
        for period in periods:
            cols = [c.upper() for c in _SM[table]["groups"][_gid(table, period)]["columns"]]
            sources = [e[period] for e in xw.values() if period in e and table in e["Tablas"]]
            assert sorted(sources) == sorted(cols), (table, period)
    assert all(e.get("Descripción") for e in xw.values())
    renamed = {k: e["Renombrar"] for k, e in xw.items() if e.get("Renombrar")}
    assert renamed["TAMLOC"] == ["2010"] and xw["TAMLOC"]["2010"] == "TAM_LOC"
    assert {p for ps in renamed.values() for p in ps} == {"2010", "2005", "2000", "1995", "1990"}
    assert all(xw[k][p] != k for k, ps in renamed.items() for p in ps)    # only real renames
    assert [k for k, ps in renamed.items() if "2010" in ps] == ["TAMLOC"]
    assert {k for k, e in xw.items() if e.get("Comparable") is False} == {
        "PCLIM_VIS", "PCLIM_MOT2", "PDER_SEGP", "PHOG_IND"}      # 6w: other relatives
    assert xw["PRES2015"]["2010"] == "PRES2005" and not xw["PRES2015"].get("Renombrar")
    assert "2020" not in xw["PCON_LIM"] and "Nota" in xw["PCON_LIM"]


def test_crosswalk_renames_are_table_scoped():
    assert _cpv._renames("iter")["TAM_LOC"] == "TAMLOC"
    assert "TAM_LOC" not in _cpv._renames("ageb")                   # no locality size there
    assert "TAM_LOC" not in _cpv._renames("viviendas")              # 2010 microdata: 4 classes
    h = _cpv._harmonize(pd.DataFrame({"entidad": ["1"], "mun": ["2"], "loc": ["3"],
                                      "tam_loc": ["5"]}, dtype=str), "iter")
    assert list(h.columns) == ["CVEGEO", "CVE_ENT", "CVE_MUN", "CVE_LOC", "TAMLOC"]


@pytest.mark.parametrize("table,col,bad", [
    ("iter", "pobtot", "x"), ("iter", "entidad", "1a"), ("iter", "loc", "x001"),
    ("iter", "vph_pc", "N/A"), ("ageb", "ageb", "01Z1"), ("ageb", "mza", "a12"),
    ("ageb", "pobfem", "-"),
])
def test_group_schema_2010_aggregates_reject(table, col, bad):
    gid = _gid(table, "2010")
    cols = _SM[table]["groups"][gid]["columns"]
    v = variables_cpv(table, gid)
    row = {}
    for c in cols:
        meta = v.get(c) or {}
        row[c] = {"entidad": "01", "mun": "001", "loc": "0001", "ageb": "0010",
                  "mza": "001"}.get(c, "1" if meta.get("Tipo") == "numeric" else "x")
    f = pd.DataFrame([row, row], dtype=str)
    f["vph_pc"] = "*"                                         # a sentinel passes
    _cpv._group_schema(table, gid).validate(f, lazy=True)
    f[col] = bad
    with pytest.raises(pa.errors.SchemaErrors, match=col):
        _cpv._group_schema(table, gid).validate(f, lazy=True)


# --- real data ----------------------------------------------------------------------------

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


_AGG_STATES = {p: [s for s in range(1, 33) if all((_MIRROR / cpv_filename(t, p, s)).exists()
                                                   for t in ("iter", "ageb"))]
               for p in ("2010", "2020")}
_POBTOT = {("2010", 1): 1_184_996, ("2020", 1): 1_425_607}


@pytest.mark.parametrize("period,state", [(p, s) for p in ("2010", "2020")
                                          for s in _AGG_STATES[p][:1]])
def test_aggregate_loaders_real(local_mirror, period, state):
    ctx = _no_warnings()
    it = mxcensus.load_cpv_iter(period, state=state)
    raw_it = mxcensus.load_cpv_iter(period, state=state, impute=False)
    ag = mxcensus.load_cpv_ageb(period, state=state)
    ctx.__exit__(None, None, None)
    assert it.index.names == ["CVE_ENT", "CVE_MUN", "CVE_LOC"] and it.index.is_unique
    assert ag.index.names == ["CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB", "CVE_MZA"]
    assert it["NIVEL"].value_counts()["estatal"] == 1 and "TAMLOC" in it
    ent = f"{state:02d}"
    total = int(it.loc[(ent, "000", "0000"), "POBTOT"])
    if (period, state) in _POBTOT:
        assert total == _POBTOT[(period, state)]
    loc = it[it["NIVEL"] == "localidad"]
    assert int(loc["POBTOT"].sum()) == total                       # localities add up
    counts = [c for c in it.columns if str(it[c].dtype) == "Int64"]
    before, after = raw_it.loc[it.index, counts], it[counts]
    changed = before.isna() & after.notna()
    assert (after[changed].stack() == 0).all() and changed.to_numpy().sum() > 0
    assert (before.fillna(-1) == after.fillna(-1))[~changed].all(axis=None)   # known cells kept
    assert it["CVEGEO"].str.len().eq(9).all() and ag["CVEGEO"].str.len().eq(16).all()
    assert int(ag.loc[(ent, "000", "0000", "0000", "000"), "POBTOT"]) == total
    only = mxcensus.load_cpv_iter(period, state=state, nivel=["municipal", "localidad"])
    assert set(only["NIVEL"]) == {"municipal", "localidad"}


def _legacy_aligned(df: pd.DataFrame) -> pd.DataFrame:
    """A legacy ``load_census`` frame with INEGI's padded string codes and Int64 values."""
    out = df.astype("Int64")
    idx = out.index.to_frame()
    names = ["CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB"][:idx.shape[1]]
    for col, width in zip(idx.columns, (2, 3, 4, 4)):
        idx[col] = idx[col].astype(str).str.zfill(width)
    idx.columns = names
    out.index = pd.MultiIndex.from_frame(idx) if len(names) > 1 else pd.Index(idx[names[0]])
    return out


_LEGACY_STATES = [s for s in _AGG_STATES["2020"]
                  if all((_MIRROR / f"{d}_{s:02d}.parquet").exists() for d in ("iter", "resargebub"))]


@pytest.mark.parametrize("state", _LEGACY_STATES)
def test_census_2020_equals_legacy(local_mirror, state):
    """The 3c gate: ``load_cpv_census(2020, state)`` = the legacy ``load_census(state)``
    (values, columns, missing pattern), once its integer codes are padded strings. States
    08, 15 and 16 have a reserved coarse total, which crashed the legacy collective
    imputation until 6c (``if diff == 0`` on ``pd.NA``)."""
    new = mxcensus.load_cpv_census(2020, state=state)
    old = mxcensus.load_census(state=state)
    for a, b in zip(new, old):
        b = _legacy_aligned(b)
        assert list(a.columns) == list(b.columns) and a.index.equals(b.index)
        assert a.equals(b)


def _collective_frames():
    """A municipality → locality pair for the collective imputation: municipality 001's
    collective population is all in locality 0001 (so 0002's missing POBHOG = its POBTOT),
    002's is not accounted for, and 003's total is reserved (the legacy loop raised on it
    before 6c)."""
    mun = pd.DataFrame({"POBTOT": [100, 50, 30], "POBHOG": [90, 40, pd.NA],
                        "TVIVHAB": [20, 10, 6], "TOTHOG": [20, 10, 6]},
                       index=pd.MultiIndex.from_tuples([("01", m) for m in ("001", "002", "003")],
                                                       names=["CVE_ENT", "CVE_MUN"])).astype("Int64")
    loc = pd.DataFrame({"POBTOT": [80, 20, 45, 5, 30], "POBHOG": [70, pd.NA, 40, pd.NA, pd.NA],
                        "TVIVHAB": [16, 4, 9, 1, 6], "TOTHOG": [16, pd.NA, 9, 1, 6]},
                       index=pd.MultiIndex.from_tuples(
                           [("01", "001", "0001"), ("01", "001", "0002"), ("01", "002", "0001"),
                            ("01", "002", "0002"), ("01", "003", "0001")],
                           names=["CVE_ENT", "CVE_MUN", "CVE_LOC"])).astype("Int64")
    for df in (mun, loc):
        df["POBCOL"], df["TOTCOL"] = df.POBTOT - df.POBHOG, df.TVIVHAB - df.TOTHOG
    return mun, loc


def test_impute_collective_na_safe():
    from mxcensus import aggregate
    mun, loc = _collective_frames()
    out = ca._impute_collective(mun, loc)
    assert out.loc[("01", "001", "0002"), "POBHOG"] == 20            # forced: no collective
    assert out.loc[("01", "001", "0002"), "TOTHOG"] == 4
    assert pd.isna(out.loc[("01", "002", "0002"), "POBHOG"])        # 5 unaccounted for
    assert pd.isna(out.loc[("01", "003", "0001"), "POBHOG"])        # reserved total: nothing
    assert aggregate.impute_collective(mun, loc).equals(out)        # the legacy loop, NA-safe
    known = mun.index[:2]                                            # without the NA total
    fine = loc[loc.index.droplevel("CVE_LOC").isin(known)]
    legacy = aggregate.impute_collective(mun.loc[known], fine)
    assert ca._impute_collective(mun.loc[known], fine).equals(legacy)


def test_census_checks_2010_tvivhab_shortfall():
    """2010's AGEBs may count fewer inhabited dwellings than their locality, never more;
    population and dwellings must add up exactly (2020: all three)."""
    idx = pd.MultiIndex.from_tuples([("01", "001", "0001")], names=["CVE_ENT", "CVE_MUN", "CVE_LOC"])
    st = pd.DataFrame({"POBTOT": [10], "VIVTOT": [5], "TVIVHAB": [4]},
                      index=pd.Index(["01"], name="CVE_ENT")).astype("Int64")
    mun = pd.DataFrame(st.to_numpy(), columns=st.columns,
                       index=pd.MultiIndex.from_tuples([("01", "001")], names=["CVE_ENT", "CVE_MUN"])).astype("Int64")
    loc = pd.DataFrame(st.to_numpy(), columns=st.columns, index=idx).astype("Int64")

    def agebs(tvivhab):
        a = pd.DataFrame({"POBTOT": [6, 4], "VIVTOT": [3, 2], "TVIVHAB": tvivhab},
                         index=pd.MultiIndex.from_tuples([("01", "001", "0001", "0010"),
                                                          ("01", "001", "0001", "0025")],
                                                         names=[*idx.names, "CVE_AGEB"]))
        return a.astype("Int64")
    it = {"estatal": st, "municipal": mun, "localidad": loc}
    ag = {"estatal": st, "municipal": mun, "localidad": loc}
    ca._census_checks("t", it, {**ag, "ageb": agebs([2, 2])}, "2020")
    ca._census_checks("t", it, {**ag, "ageb": agebs([2, 1])}, "2010")
    with pytest.raises(ValueError, match="do not add up to their locality's"):
        ca._census_checks("t", it, {**ag, "ageb": agebs([2, 1])}, "2020")
    with pytest.raises(ValueError, match="more than their locality's"):
        ca._census_checks("t", it, {**ag, "ageb": agebs([3, 2])}, "2010")


@pytest.mark.parametrize("state", _AGG_STATES["2010"])
def test_census_2010_checks(local_mirror, state):
    """The same chain on CPV 2010 passes the cross-file checks; localities and AGEBs never
    exceed their totals."""
    st, mun, loc, ageb = mxcensus.load_cpv_census(2010, state=state)
    assert list(st.columns) == list(ageb.columns) and {"POBCOL", "TOTCOL"} <= set(st.columns)
    assert int(mun["POBTOT"].sum()) == int(st["POBTOT"].iloc[0]) == int(loc["POBTOT"].sum())
    if (("2010", state)) in _POBTOT:
        assert int(st["POBTOT"].iloc[0]) == _POBTOT[("2010", state)]


@pytest.mark.skipif(not (_AGG_STATES["2010"] and _AGG_STATES["2020"]), reason="no local aggregates")
def test_iter_editions_stack(local_mirror):
    s = _AGG_STATES["2010"][0]
    both = pd.concat({p: mxcensus.load_cpv_iter(p, state=s) for p in ("2010", "2020")},
                     names=["PERIOD"])
    assert both.index.is_unique and both.index.names[0] == "PERIOD"
    shared = [c for c, e in cpv_iter_crosswalk().items()
              if "2010" in e and "2020" in e and e.get("Comparable", True) and "iter" in e["Tablas"]]
    geography = {"ENTIDAD", "MUN", "LOC"}                      # renamed onto CVE_*
    assert {"POBTOT", "TAMLOC", "VPH_PC"} <= set(shared) - geography <= set(both.columns)
    assert both.loc["2010", "TAMLOC"].notna().any()


# --- unit 4b: CGPV 2000 + Conteo 2005 ITER (renamed mnemonics, crosswalk) -----------------

def test_indicator_ranges_2005_counts(tmp_path):
    """Conteo 2005 writes every count's range as 00..9999999999: a quantity (all zeros up to
    all nines), unlike a zero-padded code space (00…32, 001..570)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import _dict_fd as fd
    csv = ("Núm.,Indicador,Descripción,Mnemónico,Rangos,Longitud\n"
           "1,Clave de Entidad,Clave,ENTIDAD,01..32,2\n"
           "2,Clave de entidad (estimaciones),Clave,CVE_ENT,00…32,2\n"
           "3,Población total,Total,P_TOTAL,00..9999999999,10\n"
           "4,Clave de Localidad,Clave,LOC,0001..9999,4\n")
    (tmp_path / "d.csv").write_text(csv, encoding="utf-8")
    doc = fd.parse_indicator_csv(tmp_path / "d.csv", {"*": "Reservado"})
    assert {k: m["Tipo"] for k, m in doc.items()} == {
        "ENTIDAD": "string", "CVE_ENT": "string", "P_TOTAL": "numeric", "LOC": "string"}
    assert doc["P_TOTAL"]["Especiales"] == {"*": "Reservado"}


def test_crosswalk_2000_2005_pairs():
    xw = cpv_iter_crosswalk()
    assert xw["POBTOT"]["2005"] == "P_TOTAL" and xw["POBTOT"]["2000"] == "POBTOT"
    assert xw["POBTOT"]["Renombrar"][:1] == ["2005"]               # 2000 keeps POBTOT
    assert xw["POBFEM"]["2000"] == "PFEMENI" and xw["POBFEM"]["Renombrar"][:2] == ["2005", "2000"]
    assert xw["OCUPVIVPAR"]["2000"] == "OCUVIVPAR" and "2000" in xw["OCUPVIVPAR"]["Renombrar"]
    # another reference date / universe / definition: paired, not renamed, with a note
    for canon, period, src in (("PRES2015", "2005", "P_RE2000"), ("PRES2015", "2000", "P5_RES95"),
                               ("VPH_AGUADV", "2005", "VPH_AGDV"), ("PNACOE", "2000", "PNACOENT"),
                               ("PDER_SEGP", "2005", "P_SEGPOP")):
        assert xw[canon][period] == src and period not in (xw[canon].get("Renombrar") or [])
        assert xw[canon].get("Nota"), canon
    assert "2000" not in xw["PCON_DISC"] and xw["PCONDISC"]["2000"] == "PCONDISC"   # unpaired
    assert xw["P_6A14_AN"] == {**xw["P_6A14_AN"], "2005": "P_6A14_AN", "2000": "POB6_14"}
    assert "2010" not in xw["P_6A14_AN"]                    # an indicator of 2000/2005 only
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_cpv as b
    assert b._xw_norm({"Descripción": "Po blación femenina de 15 a 49 años"}) == \
        b._xw_norm({"Descripción": "Población femenina de 15 a 49 años"})


def test_crosswalk_renames_are_edition_scoped():
    """A rename applies only to the edition it was reviewed for."""
    assert _cpv._renames("iter", ["2005"])["P_TOTAL"] == "POBTOT"
    assert "P_TOTAL" not in _cpv._renames("iter", ["2020"])
    assert _cpv._renames("iter", ["2000"])["PFEMENI"] == "POBFEM"
    assert "TAM_LOC" not in _cpv._renames("iter", ["2005"])
    assert _cpv._renames("iter")["P_TOTAL"] == "POBTOT"            # periods unknown: all
    f = pd.DataFrame({"entidad": ["01"], "mun": ["000"], "loc": ["0000"], "p_total": ["5"],
                      "p_re2000": ["4"]}, dtype=str)
    ctx = _no_warnings()
    h = _cpv._harmonize(f, "iter", periods=("2005",))
    ctx.__exit__(None, None, None)
    assert list(h.columns) == ["CVEGEO", "CVE_ENT", "CVE_MUN", "CVE_LOC", "POBTOT", "P_RE2000"]


_ITER_OLD = {p: [s for s in range(1, 33) if (_MIRROR / cpv_filename("iter", p, s)).exists()]
             for p in ("2000", "2005")}
# INEGI's published totals: XII Censo 2000 and II Conteo 2005 (Aguascalientes; national).
_POBTOT_OLD = {("2000", 1): 944_285, ("2005", 1): 1_065_416}
_NATIONAL_OLD = {"2000": 97_483_412, "2005": 103_263_388}


def test_repair_spilled_names():
    cols = ["CVEGEO", "NOM_LOC", "LONGITUD", "LATITUD", "ALTITUD", "POBTOT", "POBMAS"]
    df = pd.DataFrame([["202770001", "VILLA", "0965840", "163053", "1400", "1722", "772"],
                       ["202770101", "V", ", LA (R", "097003", "1632", "1570", "143"]],
                      columns=cols)
    with pytest.warns(UserWarning, match=r"repaired 1 ITER row.*'202770101'"):
        out = ca._repair_spilled_names(df, "t")
    assert out.iloc[0].tolist() == df.iloc[0].tolist()
    assert out.iloc[1].tolist()[:6] == ["202770101", "V, LA (R", "097003", "1632", "1570", "143"]
    assert pd.isna(out.iloc[1]["POBMAS"])                       # the lost last value
    assert ca._repair_spilled_names(df.iloc[:1], "t") is not None        # nothing to repair


# The 2000 ITER rows whose name spilled into LONGITUD (repaired by the loader, with a warning).
_SPILLED_2000 = {20, 22}


@pytest.mark.parametrize("period,state", [(p, s) for p in ("2000", "2005") for s in _ITER_OLD[p]])
def test_iter_2000_2005_real(local_mirror, period, state):
    if period == "2000" and state in _SPILLED_2000:
        with pytest.warns(UserWarning, match="spilled into LONGITUD"):
            it = mxcensus.load_cpv_iter(period, state=state)
    else:
        ctx = _no_warnings()
        it = mxcensus.load_cpv_iter(period, state=state)
        ctx.__exit__(None, None, None)
    lvl = {n: it[it["NIVEL"] == n] for n in ("estatal", "municipal", "localidad")}
    pob = int(lvl["estatal"]["POBTOT"].iloc[0])
    assert pob == int(lvl["municipal"]["POBTOT"].sum()) == int(lvl["localidad"]["POBTOT"].sum())
    assert (period, state) not in _POBTOT_OLD or pob == _POBTOT_OLD[(period, state)]
    assert {"POBMAS", "POBFEM", "TVIVHAB", "OCUPVIVPAR"} <= set(it.columns)   # renamed
    assert str(it["POBTOT"].dtype) == "Int64" and str(it["PROM_OCUP"].dtype) == "Float64"
    assert it.index.is_unique and set(it["CVEGEO"].str.len()) == {9}


@pytest.mark.skipif(any(len(v) < 32 for v in _ITER_OLD.values()), reason="needs all 32 states")
def test_iter_2000_2005_national(local_mirror):
    for period, total in _NATIONAL_OLD.items():
        assert sum(int(pd.read_parquet(_MIRROR / cpv_filename("iter", period, s),
                                       filters=[("mun", "==", "000"), ("loc", "==", "0000")])
                       .iloc[:, 9].iloc[0]) for s in range(1, 33)) == total


@pytest.mark.skipif(20 not in _ITER_OLD["2000"], reason="no local 2000 ITER for state 20")
def test_iter_2000_broken_rows_kept_verbatim():
    """INEGI's 2000 ITER has two locality rows whose name spills into LONGITUD (Oaxaca 277
    0101, Querétaro 012 0011); the mirror keeps them as published (``load_cpv_iter``
    repairs them, :func:`test_repair_spilled_names`)."""
    df = pd.read_parquet(_MIRROR / cpv_filename("iter", "2000", 20))
    row = df[(df["mun"] == "277") & (df["loc"] == "0101")].iloc[0]
    assert row["nom_loc"] == "V" and row["longitud"] == ", LA (R"


@pytest.mark.skipif(not all(_ITER_OLD[p][:1] == [1] for p in _ITER_OLD), reason="no state 01")
def test_iter_editions_stack_2000_2020(local_mirror):
    frames = {p: mxcensus.load_cpv_iter(p, state=1) for p in ("2000", "2005", "2010", "2020")}
    both = pd.concat(frames, names=["PERIOD"])
    st = both[both["NIVEL"] == "estatal"]["POBTOT"].droplevel(["CVE_ENT", "CVE_MUN", "CVE_LOC"])
    assert st.to_dict() == {"2000": 944_285, "2005": 1_065_416, "2010": 1_184_996,
                            "2020": 1_425_607}
    assert both["OCUPVIVPAR"].notna().groupby(level="PERIOD").any().all()


# --- unit 5a: CGPV 1990 + Conteo 1995 ITER (DBF; PDF descriptors) --------------------------

def _tsv(words: list[tuple]) -> str:
    """``pdftotext -tsv`` rows for ``(page, x, y, text)`` words (level 5; one line per
    distinct (page, y))."""
    head = "level\tpage_num\tpar_num\tblock_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    lines = {}
    out = [head]
    for k, (page, x, y, text) in enumerate(words):
        line = lines.setdefault((page, y), len(lines))
        out.append(f"5\t{page}\t0\t0\t{line}\t{k}\t{x}\t{y}\t20\t9\t100\t{text}")
    return "\n".join(out)


_FD_HDR = [(1, 60, 70, "No."), (1, 95, 70, "Categoría"), (1, 250, 70, "Descripción"),
           (1, 390, 70, "Mnemónico"), (1, 500, 70, "Rango"), (1, 560, 70, "Long.")]


def test_parse_iter_fd_top_aligned():
    """CGPV 1990: a row's number on its cells' first line; a cell may continue on the next
    page (below that page's header)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import _dict_fd as fd
    w = list(_FD_HDR) + [
        (1, 65, 100, "1"), (1, 84, 100, "Población"), (1, 130, 100, "total"),
        (1, 203, 100, "Total"), (1, 230, 100, "de"), (1, 250, 100, "personas"),
        (1, 395, 100, "P_TOTAL"), (1, 490, 100, "0..999999999"), (1, 569, 100, "9"),
        (1, 203, 112, "que"), (1, 225, 112, "residen."),
        (1, 196, 125, "Identificación"), (1, 260, 125, "geográfica"),          # a title
        (1, 65, 140, "2"), (1, 84, 140, "Población"), (1, 130, 140, "de"),
        (1, 203, 140, "Personas"), (1, 395, 140, "POB_LEE"), (1, 490, 140, "0..999999999"),
        (1, 569, 140, "9"), (1, 84, 152, "6"), (1, 95, 152, "a"), (1, 105, 152, "14"),
        (1, 203, 152, "político-"),
        ] + [(2, x, 70, t) for _, x, _, t in _FD_HDR] + [
        (2, 203, 100, "administrativa."),                       # continues row 2
        (2, 65, 120, "3"), (2, 84, 120, "Mujeres"), (2, 203, 120, "Total"),
        (2, 395, 120, "MUJERES"), (2, 490, 120, "0..999999999"), (2, 569, 120, "9"),
        (2, 100, 300, "Total"), (2, 130, 300, "de"), (2, 150, 300, "caracteres"),
        (2, 65, 320, "1/"), (2, 84, 320, "El"), (2, 203, 320, "cálculo"),      # footnote
    ]
    rows = fd.parse_iter_fd_tsv(_tsv(w), "top")
    assert [(r["Núm."], r["Mnemónico"], r["Rangos"], r["Longitud"]) for r in rows] == [
        ("1", "P_TOTAL", "0..999999999", "9"), ("2", "POB_LEE", "0..999999999", "9"),
        ("3", "MUJERES", "0..999999999", "9")]
    assert rows[0]["Indicador"] == "Población total"
    assert rows[0]["Descripción"] == "Total de personas que residen."
    assert rows[1]["Indicador"] == "Población de 6 a 14"
    assert rows[1]["Descripción"] == "Personas político-administrativa."
    assert rows[2]["Descripción"] == "Total"                                 # no footnote


def test_parse_iter_fd_centred_and_csv(tmp_path):
    """Conteo 1995: cells centred on the row number (text above and below it); the rows
    write a ``diccionario_datos_*.csv`` that ``parse_indicator_csv`` reads."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import _dict_fd as fd
    w = list(_FD_HDR) + [
        (1, 196, 100, "Total"), (1, 220, 100, "de"), (1, 235, 100, "personas"),
        (1, 77, 110, "Población"), (1, 196, 110, "que"), (1, 220, 110, "residen"),
        (1, 55, 110, "10"), (1, 390, 110, "POBTOTAL"), (1, 480, 110, "0..999999999"),
        (1, 548, 110, "9"), (1, 196, 120, "en"), (1, 210, 120, "el"), (1, 220, 120, "país."),
        (1, 77, 120, "total"),
        (1, 196, 135, "Cociente"), (1, 240, 135, "entre"),
        (1, 77, 140, "Índice"), (1, 110, 140, "de"), (1, 55, 145, "11"),
        (1, 390, 140, "IM"), (1, 480, 145, "0..999999999"), (1, 548, 145, "9"),
        (1, 77, 150, "masculinidad"), (1, 196, 145, "hombres"), (1, 240, 145, "y"),
        (1, 196, 155, "mujeres."),
    ]
    rows = fd.parse_iter_fd_tsv(_tsv(w), "center")
    assert [(r["Indicador"], r["Mnemónico"]) for r in rows] == [
        ("Población total", "POBTOTAL"), ("Índice de masculinidad", "IM")]
    assert rows[0]["Descripción"] == "Total de personas que residen en el país."
    assert rows[1]["Descripción"] == "Cociente entre hombres y mujeres."
    fd.write_indicator_csv(rows, tmp_path / "d.csv")
    doc = fd.parse_indicator_csv(tmp_path / "d.csv")
    assert doc["POBTOTAL"]["Descripción"] == "Población total" and doc["IM"]["Tipo"] == "numeric"
    assert fd._centred_runs([1, 2, 3, 10, 11], [2, 10.5]) == [(0, 3), (3, 5)]


def test_crosswalk_1990_1995_pairs():
    xw = cpv_iter_crosswalk()
    assert {p: xw["POBTOT"][p] for p in ("1995", "1990")} == {"1995": "POBTOTAL", "1990": "P_TOTAL"}
    assert xw["POBMAS"]["1990"] == "HOMBRES" and xw["POBFEM"]["1995"] == "POBTFEM"
    assert xw["REL_H_M"]["1995"] == "IM" and "1995" in xw["REL_H_M"]["Renombrar"]
    # 7f: 1995's PRO_O_VP is OCUPVIVPAR / VIVPAR_HAB truncated, as 1990's PROM_VIV (its
    # descriptor's «población total entre el total de viviendas» is not what it publishes);
    # 2000's VP_AGUENT is the water within the dwelling or the lot (exact on its sample)
    assert xw["PROM_OCUP"]["1995"] == "PRO_O_VP" and "1995" in xw["PROM_OCUP"]["Renombrar"]
    assert xw["PROM_OCUP"]["1990"] == "PROM_VIV" and "1990" in xw["PROM_OCUP"]["Renombrar"]
    assert xw["VPH_AGUADV"]["2000"] == "VP_AGUENT" and "2000" in xw["VPH_AGUADV"]["Renombrar"]
    assert "2005" not in xw["VPH_AGUADV"]["Renombrar"]                     # the public network
    assert xw["VP_2CUAR"] == {**xw["VP_2CUAR"], "2000": "VP_2CUAR", "1990": "VIV_2_C"}
    assert xw["P_PP5HLIYE"]["1995"] == "P_PP5HLIYE" and xw["P_PP5HLIYE"]["Descripción"]
    # every reviewed pair is in the crosswalk under its canonical name (a duplicate key in
    # the review dicts would silently drop one)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_cpv as b
    for canon, by in b._XW_PAIRS.items():
        for period, src in by.items():
            assert xw[canon][period] == src, (canon, period, src)
    for canon, by in b._XW_PAIRS_RENAMED.items():
        assert set(by) <= set(xw[canon]["Renombrar"]), canon
    import ast
    tree = ast.parse(Path(b.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            assert len(keys) == len(set(keys)), f"duplicate keys in a dict at line {node.lineno}"


def test_repair_spilled_names_without_comma():
    """Conteo 1995's Urique 1781: «Y» + «GRIEGA» — no comma, but a LONGITUD without digits;
    2010/2020 coordinates are text with digits and are never touched."""
    df = pd.DataFrame([["080651781", "Y", "GRIEGA", "108051", "2726", "2020", "40"],
                       ["090020001", "Azcapotzalco", "99°11'12.27\" W", "19°29'", "2240",
                        "5", "6"]],
                      columns=["CVEGEO", "NOM_LOC", "LONGITUD", "LATITUD", "ALTITUD",
                               "POBTOT", "POBMAS"])
    with pytest.warns(UserWarning, match="'080651781'"):
        out = ca._repair_spilled_names(df, "t")
    assert out.iloc[0].tolist()[:6] == ["080651781", "Y GRIEGA", "108051", "2726", "2020", "40"]
    assert out.iloc[1].tolist() == df.iloc[1].tolist()


_ITER_9095 = {p: [s for s in range(1, 33) if (_MIRROR / cpv_filename("iter", p, s)).exists()]
              for p in ("1990", "1995")}
# The ITER's own national rows: 1990 = the XI Censo's published total; 1995 = the
# «TOTAL NACIONAL» row of INEGI's national ITER file (00_nacional_1995_iter_dbf.zip).
_NATIONAL_9095 = {"1990": 81_249_645, "1995": 90_638_604}
_SPILLED_1995 = {8, 20, 22}


@pytest.mark.parametrize("period,state", [(p, s) for p in ("1990", "1995") for s in _ITER_9095[p]])
def test_iter_1990_1995_real(local_mirror, period, state):
    if period == "1995" and state in _SPILLED_1995:
        with pytest.warns(UserWarning, match="spilled into LONGITUD"):
            it = mxcensus.load_cpv_iter(period, state=state)
    else:
        ctx = _no_warnings()
        it = mxcensus.load_cpv_iter(period, state=state)
        ctx.__exit__(None, None, None)
    lvl = {n: it[it["NIVEL"] == n] for n in ("estatal", "municipal", "localidad", "agregado")}
    pob = int(lvl["estatal"]["POBTOT"].iloc[0])
    mun = lvl["municipal"]["POBTOT"].droplevel("CVE_LOC")
    assert pob == int(mun.sum())
    loc = lvl["localidad"].groupby(level=["CVE_ENT", "CVE_MUN"])["POBTOT"].sum()
    if period == "1995":     # its one- and two-dwelling localities exist only as agregados
        agg = lvl["agregado"].drop(index="000", level="CVE_MUN", errors="ignore")
        loc = loc.add(agg.groupby(level=["CVE_ENT", "CVE_MUN"])["POBTOT"].sum(), fill_value=0)
    assert loc.reindex(mun.index, fill_value=0).equals(mun.astype(loc.dtype))
    assert {"POBMAS", "POBFEM", "TVIVHAB", "OCUPVIVPAR", "VPH_AGUADV"} <= set(it.columns)
    assert (lvl["estatal"]["POBMAS"] + lvl["estatal"]["POBFEM"] == lvl["estatal"]["POBTOT"]).all()


@pytest.mark.skipif(any(len(v) < 32 for v in _ITER_9095.values()), reason="needs all 32 states")
def test_iter_1990_1995_national(local_mirror):
    for period, total in _NATIONAL_9095.items():
        assert sum(int(pd.read_parquet(_MIRROR / cpv_filename("iter", period, s),
                                       filters=[("MUN", "==", "000"), ("LOC", "==", "0000")])
                       .iloc[0, 9]) for s in range(1, 33)) == total


# --- the ITER across editions (8i) -------------------------------------------------------------

def test_panel_unit_values():
    """8i: a unit's counts are its members' known values summed (missing when none is
    known); REL_H_M and PROM_OCUP the ratio of its counts over the members giving both;
    the other averages the members' values weighted by their base (PRO_OCUP_C by the rooms
    OCUPVIVPAR / PRO_OCUP_C); an indicator the edition lacks is missing."""
    i64 = lambda *v: pd.array(v, dtype="Int64")         # noqa: E731
    f64 = lambda *v: pd.array(v, dtype="Float64")       # noqa: E731
    df = pd.DataFrame({
        "UNIT": ["A", "A", "B", "C"],
        "POBTOT": i64(10, 20, 5, None), "POBFEM": i64(6, None, 3, None),
        "POBMAS": i64(4, None, 2, None), "P_15YMAS": i64(8, 12, 4, None),
        "GRAPROES": f64(9.0, 7.0, 6.0, None), "REL_H_M": f64(66.67, None, 66.67, None),
        "OCUPVIVPAR": i64(10, 20, 5, None), "VIVPAR_HAB": i64(2, 5, 1, None),
        "PROM_OCUP": f64(5.0, 4.0, 5.0, None), "PRO_OCUP_C": f64(1.0, 2.0, 0.5, None)})
    inds = ["POBTOT", "POBFEM", "GRAPROES", "REL_H_M", "PROM_OCUP", "PRO_OCUP_C", "VPH_X"]
    out = ca._unit_values(df, "2010", inds)
    assert list(out.columns) == inds and out.index.tolist() == ["A", "B", "C"]
    assert out["POBTOT"].tolist() == [30, 5, pd.NA] and str(out["POBTOT"].dtype) == "Int64"
    assert out["POBFEM"].tolist() == [6, 3, pd.NA]
    assert out.loc["A", "GRAPROES"] == pytest.approx((9 * 8 + 7 * 12) / 20)
    assert out.loc["B", "GRAPROES"] == 6.0                     # one member: published value
    assert out.loc["A", "REL_H_M"] == pytest.approx(400 / 6)   # the member giving both
    assert out.loc["A", "PROM_OCUP"] == pytest.approx(30 / 7)
    assert out.loc["A", "PRO_OCUP_C"] == pytest.approx(30 / 20)
    assert out.loc["C"].isna().all() and out["VPH_X"].isna().all()
    assert str(out["VPH_X"].dtype) == "Int64" and str(out["PROM_OCUP"].dtype) == "Float64"
    # 2020 divides the occupants by TVIVPARHAB; the EIC 2025 weighs by VIVPARHAB_C
    assert ca._rule("PROM_OCUP", "2020")[2] == "TVIVPARHAB"
    assert ca._rule("PROM_OCUP", "2025") == ("mean", "VIVPARHAB_C")
    with pytest.raises(ValueError, match="does not publish"):
        ca._unit_values(df.drop(columns="VIVPAR_HAB"), "2010", ["PROM_OCUP"])


def test_panel_arguments():
    with pytest.raises(ValueError, match="periods must be among"):
        mxcensus.load_cpv_iter_panel([2000, 2015], state=1)
    with pytest.raises(ValueError, match="periods must be among"):     # no 2025 localities
        mxcensus.load_cpv_iter_panel([2020, 2025], state=1, nivel="localidad")
    with pytest.raises(ValueError, match="nivel"):
        mxcensus.load_cpv_iter_panel([2020], state=1, nivel="ageb")
    with pytest.raises(ValueError, match="state"):
        mxcensus.load_cpv_iter_panel([2020], state=None)


_PANEL_STATES = [s for s in range(1, 33) if all(
    (_MIRROR / cpv_filename("iter", p, s)).exists() for p in ca.PANEL_PERIODS[:-1])]
_PANEL_SKIP = pytest.mark.skipif(1 not in _PANEL_STATES, reason="no local ITER 1990-2020 of 01")


@_PANEL_SKIP
def test_iter_panel_municipal_real(local_mirror):
    """8i: Aguascalientes 1990/2000/2020: El Llano and San Francisco de los Romo (1995) join
    Aguascalientes; each edition's population once; unchanged units keep their published
    values; the default indicators are the ones every edition publishes."""
    panel = mxcensus.load_cpv_iter_panel([2020, 1990, 2000], state=1)
    assert panel.index.names == ["PERIOD", "UNIT"]
    assert panel.index.get_level_values("PERIOD").unique().tolist() == ["1990", "2000", "2020"]
    assert list(panel.columns[:5]) == ["N_CODES", "N_RESERVED", "RESERVED_POB", "NOM_ENT",
                                       "NOM_MUN"]
    ags = panel.xs("01001", level="UNIT")
    assert ags["N_CODES"].tolist() == [1, 3, 3] and (ags["N_RESERVED"] == 0).all()
    assert ags["POBTOT"].tolist() == [506_274, 678_812, 1_031_840]
    assert len(panel) == 3 * 9 and "REL_H_M" not in panel        # 1990/2000 do not publish it
    for p in ("1990", "2000", "2020"):
        it = mxcensus.load_cpv_iter(p, state=1, nivel="municipal")
        assert int(panel.xs(p)["POBTOT"].sum()) == int(it["POBTOT"].sum())
        one = panel.xs(p)[panel.xs(p)["N_CODES"] == 1]
        pub = it.set_index(it["CVEGEO"].str[:5]).loc[one.index]
        counts = [c for c in one.columns[5:] if c not in ca._AVERAGES]
        assert one[counts].equals(pub[counts].rename_axis("UNIT")), p
        assert (one["PRO_OCUP_C"] - pub["PRO_OCUP_C"]).abs().max() <= 1e-9, p
        assert (one["PROM_OCUP"] - pub["PROM_OCUP"]).abs().max() <= 0.01 + 1e-9  # 1990 truncates
    # an explicit list: missing where an edition lacks the indicator
    rel = mxcensus.load_cpv_iter_panel([1990, 2020], state=1, indicators=["REL_H_M", "POBTOT"])
    assert rel.xs("1990")["REL_H_M"].isna().all() and rel.xs("2020")["REL_H_M"].notna().all()
    with pytest.raises(ValueError, match="publishes"):
        mxcensus.load_cpv_iter_panel([1990, 2020], state=1, indicators=["P_P0A4"])


@pytest.mark.skipif(not (_MIRROR / "cpv_estimaciones_2025.parquet").exists()
                    or 29 not in _PANEL_STATES, reason="no local ITER/estimates of 29")
def test_iter_panel_1990_2025_real(local_mirror):
    """8i: Tlaxcala 1990-2025 (16 municipalities created in 1995): the EIC 2025's estimates
    as the last edition, matched by name; PHOG_IND, defined otherwise in 2025, left out."""
    panel = mxcensus.load_cpv_iter_panel(ca.PANEL_PERIODS, state=29)
    units = panel.index.get_level_values("UNIT").unique()
    assert len(units) < 60 and panel.xs("1990")["N_CODES"].sum() == 44
    assert panel.xs("2025")["N_CODES"].sum() == 60
    est = mxcensus.load_cpv_estimaciones(nivel="estatal", state=29)
    assert int(panel.xs("2025")["POBTOT"].sum()) == int(est["POBTOT"].iloc[0])
    assert {"POBTOT", "OCUPVIVPAR", "PROM_OCUP"} <= set(panel.columns)
    both = mxcensus.load_cpv_iter_panel([2020, 2025], state=29)
    assert "PHOG_IND" not in both and "GRAPROES" in both and "PCON_DISC" in both
    assert "PHOG_IND" in mxcensus.load_cpv_iter_panel([2025], state=29)


@_PANEL_SKIP
def test_iter_panel_localities_real(local_mirror):
    """8i: Aguascalientes city 2000 → 2020 holds 26 localities of 2000: known sums, the
    reserved members' population as the bound, the averages weighted over those known."""
    panel = mxcensus.load_cpv_iter_panel([2000, 2020], state=1, nivel="localidad")
    city = panel.xs("010010001", level="UNIT")
    assert city["N_CODES"].tolist() == [26, 1] and city["POBTOT"].tolist() == [594_934, 863_893]
    assert city.loc["2000", ["N_RESERVED", "RESERVED_POB"]].tolist() == [17, 108]
    assert city[["GRAPROES", "PROM_OCUP"]].notna().all().all()
    for p in ("2000", "2020"):
        it = mxcensus.load_cpv_iter(p, state=1, nivel="localidad")
        assert int(panel.xs(p)["POBTOT"].sum()) == int(it["POBTOT"].sum())
        assert int(panel.xs(p)["N_CODES"].sum()) == len(it)


@pytest.mark.skipif(len(_PANEL_STATES) < 32, reason="needs every ITER 1990-2020 of all states")
@pytest.mark.parametrize("nivel", ["municipal", "localidad"])
def test_iter_panel_national(local_mirror, nivel):
    """8i: every state: each edition's municipalities or localities once, the units that
    span two states (localities moved between them) identical in both states' panels.
    The municipalities over the six ITER editions; the localities 1990 → 2020 (all six
    editions, 4 min: STEP_8i.md)."""
    periods = ca.PANEL_PERIODS[:-1] if nivel == "municipal" else ("1990", "2020")
    panels = pd.concat([mxcensus.load_cpv_iter_panel(periods, state=s, nivel=nivel)
                        for s in range(1, 33)])
    twice = panels.index.duplicated(keep=False)
    assert (nivel == "municipal") == (not twice.any())
    shared = panels[twice].astype(str).groupby(level=["PERIOD", "UNIT"]).nunique()
    assert (shared <= 1).all().all()
    panels = panels[~panels.index.duplicated()]
    for p in periods:
        it = mxcensus.load_cpv_iter(p, state=list(range(1, 33)), nivel=nivel)
        assert int(panels.xs(p)["POBTOT"].sum()) == int(it["POBTOT"].sum()), p
        assert int(panels.xs(p)["N_CODES"].sum()) == len(it), p
