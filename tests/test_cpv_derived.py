"""CPV derived columns (``mxcensus.cpv_derived``, units 6b/6d/6e) and the constraints per
edition.

Offline: the registry's source codes per edition (the bundled dictionaries), ``derive`` on
synthetic raw frames, ``cpv_derivations``/``cpv_constraints``. Real data (skipped without
the local mirror ``data/parquet``): the Censo 2020 columns equal the legacy
``load_extended_*`` ones, every edition derives without an unmapped code, and one
crosstab per edition (the EIC 2025 cells equal its published estimates).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import mxcensus
from mxcensus import cpv_derived as d
from mxcensus._resources import cpv_schema_map
from mxcensus.cpv import variables_cpv_labels

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REAL = (_MIRROR / "cpv_personas_2025_01.parquet").exists() \
    and (_MIRROR / "personas_01.parquet").exists()
_REAL_SKIP = pytest.mark.skipif(not _REAL, reason="no local CPV + legacy mirror (data/parquet/)")


def _gid(table: str, period: str) -> str:
    for gid, group in cpv_schema_map()[table]["groups"].items():
        if period in [str(p) for p in group["periods"]]:
            return gid
    raise KeyError(period)


def _codes(meta: dict, *, numeric_range: bool = False) -> tuple[str, frozenset[int]]:
    """An item's type and its integer codes (categories + sentinels; numerics: sentinels,
    plus the ``Rango`` values with ``numeric_range``)."""
    from mxcensus import _schema_groups as _sg

    tipo = _sg.norm_tipo(meta)
    keys = {int(k) for k in (meta.get("Especiales") or {})}
    if tipo == "categorical":           # the 2005 FD's «1 : 8» ellipsis row left a ':' key
        keys |= {int(k) for k in (meta.get("Categorías") or {}) if str(k).lstrip("-").isdigit()}
    elif numeric_range and tipo == "numeric" and meta.get("Rango"):
        lo, hi = meta["Rango"]
        keys |= set(range(int(lo), int(hi) + 1))
    return tipo, frozenset(keys)


_CASES = [(dv.table, period, src) for dv in d._registry() for period in dv.periods
          if period != "2020" for src in dv.sources if src not in ("ENT", "MUN")]

# Reviewed differences from the 2020 code list after the recode (6d, STEP_6d.md): the 2020
# codes an edition does not distinguish, and the codes it adds.
_GAPS = {
    ("2010", "DHSERSAL1"): {6}, ("2010", "DHSERSAL2"): {6},       # no IMSS-PROSPERA/BIENESTAR
    ("2015", "DHSERSAL1"): {6}, ("2015", "DHSERSAL2"): {5, 6},    # 2015: Seguro Popular only 1st
    ("2010", "NIVACAD"): {5, 12},              # one bachillerato code, no especialidad
    ("2015", "CONACT"): set(range(13, 20)),    # rescued by activity (11–15 → 10), not status
    ("2015", "SITUA_CONYUGAL"): {6, 7},        # casada(o) not split by civil/religious
    # 2015's FD declares only 999; 997/998 are rows of its catalog (TC_ENTIDAD_PAIS_2015)
    ("2015", "ENT_PAIS_NAC"): {997, 998}, ("2015", "ENT_PAIS_RES_5A"): {997, 998},
    ("2015", "ENT_PAIS_ASI"): {997, 998}, ("2015", "ENT_PAIS_TRAB"): {997, 998},     # 7b
    ("2010", "ACTIVIDADES_C"): {9999},         # ACTTRAB_C: a row of TC_SCIAN_2010, no sentinel
    ("2000", "CONACT"): {17},                  # no «limitación, rescued by the activity check»
    # 2000: no bachillerato tecnológico, normal de licenciatura, especialidad, doctorado (in
    # maestría); técnica (6) splits into 6/7/8 by its antecedent (_educ_2000)
    ("2000", "NIVACAD"): {5, 7, 8, 10, 12, 14},
    # 2000/2005/2010 dwelling classes: one «casa independiente» (2020: 1–3 by terrain/dúplex)
    ("2000", "CLAVIVP"): {2, 3}, ("2005", "CLAVIVP"): {2, 3}, ("2010", "CLAVIVP"): {2, 3},
    # 1990/1995 (6j): no activity check; 1995's casada(o) is not split; 1990's dwelling
    # classes (casa sola; departamento or vecindad; no local no construido) and its one
    # drainage code for the ground, a river or a lake (2020: 3/4)
    ("1990", "CONACT"): set(range(13, 20)), ("1995", "CONACT"): set(range(13, 20)),
    ("1995", "SITUA_CONYUGAL"): {6, 7},
    ("1990", "CLAVIVP"): {2, 3, 5, 7}, ("1990", "DRENAJE"): {4},
}
_EXTRAS = {
    ("2010", "DHSERSAL2"): {1}, ("2015", "DHSERSAL2"): {1},       # IMSS as the 2nd option
    ("2015", "ESCOLARI"): {9},                 # in the FD's range; never in the data
}
# Items a derivation reads in the edition's own code space (no 2020 counterpart).
_OWN_CODES = {
    **{("2015", item): set(d._traslado_2015(items[0])) - {d._BLANK}
       for items in (d._ESC, d._TRAB) for item in items},
    **{("2010", f"DISCAP{i}"): {9 + i} for i in range(1, 8)},
    ("2010", "DISCAP8"): {17, 99},
    # Censo 2010's split birthplace/residence: entity items (001–032, 900 topic omitted,
    # 999), country items (catalog TC_PAIS_2010, no sentinel in the FD)
    **{("2010", item): {*range(1, 33), 900, 999} for item in ("LNACEDO_C", "RES05EDO_C")},
    **{("2010", item): set() for item in ("LNACPAIS_C", "RES05PAI_C")},
    # 7b: its place of work (one item, both catalogs: TC_PAIS_2010 in the FD, the data's
    # entity codes, 900 and 999 from TC_ENTIDAD_2010) and the municipalities of work and of
    # the 2005 residence (TC_MUNICIPIO_2010); no sentinel in the FD
    **{("2010", item): set() for item in ("LTRABPAI_C", "LTRABMUN_C", "MUN05OTR_C")},
    # its pointer pairs: the row number (99 = row not given), the code (88 not here, 99)
    **{("2010", item): {99} for item in ("IDMADRE", "IDPADRE", "IDCONYUGE")},
    **{("2010", item): {88, 99} for item in ("IDMADREC", "IDPADREC", "IDCONYUGEC")},
    ("2015", "FINANCIAMIENTO"): set(d._financiamiento_2015()) - {d._BLANK},
    # 7a: the EIC 2025's recognition of an access to the public health services (asked of
    # the not affiliated; Censo 2020 has no such item)
    ("2025", "DHSERSAL_ACCESO"): {1, 3, 9},
    # 2010's 4-digit occupation and 6-digit religion: catalogs, no sentinel in the FD
    # (test_catalog_codes_derive reads the catalogs)
    ("2010", "OCUACTIV_C"): set(), ("2010", "OTRAREL_C"): set(),
    # CGPV 2000 (6i): the SCIAN subsector (110–939) and 999; normal/técnica antecedent; level
    # and antecedent; one item per institution; religion (0001 católica, 1101–9001, 9100
    # ninguna, 9999: 7r, text, its sentinel 9999); the birthplace and 1995 residence items are
    # text in its FD (entity 001–032, country 100–535 as 2020, 600 country unknown, 999); 7q:
    # its income, hours and household income are numeric (build_cpv._QUANTITIES), as 2020's
    ("2000", "ACTTRAB_C"): {999}, ("2000", "ANTESC"): {1, 2, 3, 9},
    ("2000", "NIVELACAD"): {0, 10, 20, 30, 40, 51, 52, 61, 62, 63, 73, 80, 90},
    ("2000", "IMSS"): {1, 9}, ("2000", "ISSSTE"): {2}, ("2000", "PEMEX"): {3},
    ("2000", "OTRINS_V"): {4}, ("2000", "NOTIEDER"): {5}, ("2000", "OTRAREL_C"): {9999},
    # 8e: its CMO occupation (1100–8390, text; its sentinel 9999), placed by the bridge
    ("2000", "OCUACTIV_C"): {9999},
    ("2000", "ENT_PAIS_NAC"): {600, 999}, ("2000", "ENT_PAIS_RES_5A"): {600, 999},
    # 7f: its household number (1–9) and kitchen items (a room for cooking 1/2, slept in 3/4)
    ("2000", "NUMHOG"): set(), ("2000", "COCINA"): {1, 2, 9}, ("2000", "COCDOR"): {3, 4, 9},
    # 7c: its place of work (the birthplace's codes) and the municipalities of work and of
    # the 1995 residence (001–570, 999)
    ("2000", "LTRABPAI_C"): {600, 999}, ("2000", "LTRABMUN_C"): {999},
    ("2000", "MUN_RES_5A"): {999},
    # Conteo 2005: level and antecedent (7r: its catalog TC_ANTES's 14 codes, 99), grade
    # (1–8, 9), one item per institution, residence in 2000 (001–033, 201 the US, 600, 999)
    ("2005", "NIVANTES"): {0, 10, 20, 30, 40, 51, 52, 61, 62, 63, 73, 84, 94, 95, 99},
    ("2005", "GRA_APRO"): set(range(1, 10)),
    ("2005", "IMSS"): {1}, ("2005", "ISSSTE"): {1}, ("2005", "PEMEX"): {1},
    ("2005", "SEGU_POP"): {1}, ("2005", "INST_PRI"): {1}, ("2005", "OTRA_INS"): {1, 2, 3, 9},
    ("2005", "SIN_DERE"): {6, 9}, ("2005", "ENT_PAIS_RES_5A"): {*range(1, 34), 201, 600, 999},
    # CGPV 1990 (6j): approved a grade (0 = under 5), level, its grades (99), preschool,
    # technical and normal years; the income (8 digits, numeric since 7q: 99999997–9 not
    # specified, the FD's note); birthplace and 1985 residence (catalog CATPAISE: 001–032, 033–099, 100–998,
    # 999); religion (0 = under 5)
    ("1990", "APROBO"): {0, 1, 2, 9}, ("1990", "NIV_EST"): set(range(6)),
    ("1990", "ANO_APRO"): {99}, ("1990", "PRESCO"): set(), ("1990", "TEC_PRIM"): set(),
    ("1990", "TEC_SEC"): set(), ("1990", "NOR_BAS"): set(),
    ("1990", "INGTRMEN"): {99999997, 99999998, 99999999},
    ("1990", "ENT_PAIS_NAC"): set(), ("1990", "ENT_PAIS_RES_5A"): set(),
    ("1990", "RELIGION"): {0, 1, 2, 3, 4, 5, 9},
    ("1990", "C_A_ECO"): set(),                # 6o: CMAP (catalog CATACTEC), 00000 not asked
    # Conteo 1995: ever attended, level, grades, technical career and its requisite; the
    # 2-digit birthplace and 1990 residence (its catalog of entities and countries, a PDF
    # read since 6u: 32 states, 33–38 continents, 70 Mexico, 90/99 unspecified)
    ("1995", "P5_3"): {5, 6, 9}, ("1995", "P5_4B"): {*range(8), 9}, ("1995", "P5_4A"): set(),
    ("1995", "P5_5"): {1, 2, 9}, ("1995", "P5_7"): {0, 1, 2, 3, 9},
    **{("1995", item): {*range(1, 39), 70, 90, 99}
       for item in ("ENT_PAIS_NAC", "ENT_PAIS_RES_5A")},
}
# Own-code text items without a catalog in their edition's FD (the code layout is stated in
# its notes, quoted above; 7r: CGPV 2000's activity, religion and municipalities, text since).
_NO_CATALOG = {("2000", "ENT_PAIS_NAC"), ("2000", "ENT_PAIS_RES_5A"),
               ("2000", "LTRABPAI_C"),                                          # 7c
               ("2000", "ACTTRAB_C"), ("2000", "OTRAREL_C"), ("2000", "LTRABMUN_C"),
               ("2000", "MUN_RES_5A"),                                          # 7r
               ("2000", "OCUACTIV_C")}                                          # 8e
_LATER_OPTIONS = {*d._ESC[1:], *d._TRAB[1:]}      # list fewer codes (options are ordered)
# 2020 catalog items whose FD row names no catalog (7b: the municipality of work; its
# school and residence municipalities name «MUN»).
_REF_WITHOUT_CATALOG = {"MUN_TRAB"}
# Numeric in 2010/2015, categorical in 2020 (same values; the pointers: row numbers).
_NUMERIC_CODES = {"ESCOLARI", "IDENT_MADRE", "IDENT_PADRE", "IDENT_PAREJA"}
# Sources a loader brings from another file → (that file's table, the 2020 table and item
# they are compared with): the household head's sex from the person file (cpv._attach_heads;
# 6s dwellings, 6v the Conteo 2005's households: 2020's dwelling item JEFE_SEXO), the 2005
# household's dwelling class (cpv._attach_dwellings, 6v), the persons' household type (6z,
# the same) and the household members' items (cpv._household_members, 6x: HOG_IND on the
# dwellings and the 2005 households).
_BORROWED = {("viviendas", "SEXO"): ("personas", "viviendas", "JEFE_SEXO"),
             ("hogares", "SEXO"): ("personas", "viviendas", "JEFE_SEXO"),
             ("hogares", "CLAVIVP"): ("viviendas", "viviendas", "CLAVIVP"),
             ("personas", "TIPOHOG"): ("viviendas", "viviendas", "TIPOHOG"),
             **{(table, item): ("personas", "personas", item)
                for table in ("viviendas", "hogares")
                for item in ("PARENTESCO", "HLENGUA", "AFRODES")}}            # 7a: AFRODES


# 8f: the relationship items the kinship line reads besides PARENTESCO (each edition's own
# codes: 1990 CVE_PAR, 2005/2010 PARENT, 2010 OTROPARE_C, 2015 PARENT_OTRO_C).
_KIN_ITEMS = {"CVE_PAR", "PARENT", "OTROPARE_C", "PARENT_OTRO_C"}


def _line_of(period: str, source: str) -> dict[int, str]:
    """8f: the kinship line of each code of ``source`` in ``period`` (Censo 2010: PARENT's
    groups but «otro parentesco», OTROPARE_C's detail of it)."""
    if period == "2010":
        return dict(d._PARENT_2010 if source == "PARENT" else d._OTRO_2010)
    return {code: line for line, codes in d._LINEAS[period].items() for code in codes}


# 6w: the labels of the relationship codes (other than the head's) whose language makes a
# household indigenous — partners, parents, step-parents, grandparents, parents-in-law.
_MEMBER_WORDS = ("Espos", "Concubin", "Amasi", "Querid", "Amante", "Madre", "Madrastra",
                 "Abuel", "Bisabuel", "Suegr")


@pytest.mark.parametrize("table,period,source", sorted(set(_CASES)))
def test_source_codes_match_2020(table, period, source):
    """Every edition a derivation is declared for has the 2020 code list of each source
    item, after the edition's recode (the dictionaries; catalog items: their sentinels),
    up to the reviewed gaps and extras; own-code items have their own list. The item is
    the frame's own column (a core entry such as ``EDAD`` labels editions that name it
    otherwise: 1990 ``ANO_CUMP``, 1995 ``P3_6``); 1990/1995 dwellings: the person file's, as
    the household head's sex (6s), compared with 2020's ``JEFE_SEXO``; the Conteo 2005's
    households: their dwelling's class and head's sex (6v), compared with 2020's dwelling
    items; the dwellings' and the 2005 households' indigenous household (6x): the person
    items of their members."""
    ref_table = "viviendas" if table == "hogares" else table       # 2020 has no hogares
    source_table, ref_table, ref_name = _BORROWED.get((table, source),
                                                      (table, ref_table, source))
    group_table, gid, columns = d._frame_group(source_table, period)
    labels = variables_cpv_labels(group_table, gid)
    name = next(a for a in d._ALIASES.get(source, (source,))
                if a in labels and a.upper() in columns)
    new = labels[name]
    if source in _KIN_ITEMS:                  # 8f: every code of the catalog has a line
        tipo, codes = _codes(new)
        lines = set(_line_of(period, source))
        assert tipo == "categorical"
        if period != "2010":
            assert codes <= lines
        elif source == "PARENT":                                   # 08: OTROPARE_C's detail
            assert codes - {8} == lines
        else:
            assert {c for c in codes if 600 <= c < 700} == lines
        return
    if source == "PARENTESCO":                # 6t: own codes; the head's are documented
        tipo, codes = _codes(new)             # (6u: 1995 from its catalog PDF, 2000 from
        heads = set(d._HEAD_CODES[period])    # its FD's code groups)
        labelled = {int(k): v for k, v in (new.get("Categorías") or {}).items()}
        assert tipo == "categorical" and heads <= codes
        assert all(("Jef" in labelled[h]) or labelled[h] == "Persona sola" for h in heads)
        if d._LINEA_ITEMS.get(period) == "PARENTESCO":                      # 8f: a line each
            assert codes <= set(_line_of(period, source))
        if period in d._IND_CODES:            # 6w: the head, partner and ascendants
            members = set(d._IND_CODES[period])
            assert members <= codes and heads <= members
            for code in members - heads:
                assert any(w in labelled[code] for w in _MEMBER_WORDS), (code, labelled[code])
        return
    key = (table, period, source) if (table, period, source) in _OWN_CODES else (period, source)
    if key in _OWN_CODES:
        tipo, codes = _codes(new)
        own = _OWN_CODES[key]
        assert codes <= own if source in _LATER_OPTIONS else codes == own
        assert tipo != "string" or new.get("Catálogo") or (period, source) in _NO_CATALOG
        return
    ref = variables_cpv_labels(ref_table, _gid(ref_table, "2020"))[ref_name]
    expand = source in _NUMERIC_CODES
    tipo, codes = _codes(new, numeric_range=expand)
    ref_tipo, ref_codes = _codes(ref, numeric_range=expand)
    assert tipo == ref_tipo or expand
    recode = d._RECODE.get(period, {}).get(source, {})
    if tipo == "string":                      # catalog codes (occupation, country…)
        assert (ref.get("Catálogo") or source in _REF_WITHOUT_CATALOG) and new.get("Catálogo")
    recoded = {c for c in (recode.get(c, c) for c in codes) if c == c}     # NaN = blank
    assert recoded - ref_codes == _EXTRAS.get((period, source), set())
    assert ref_codes - recoded == _GAPS.get((period, source), set())


def test_recode_tables():
    """A recode covers a source of a derivation declared for that edition, and lands on
    2020 codes; DHSERSAL swaps 05/06, SITUA_CONYUGAL folds the two «separada» codes."""
    for period, items in d._RECODE.items():
        sources = {s for dv in d._registry() if period in dv.periods for s in dv.sources}
        assert set(items) <= sources
    r = d._RECODE["2025"]
    assert r["DHSERSAL1"] == r["DHSERSAL2"] == {5: 6, 6: 5}
    assert r["SITUA_CONYUGAL"][2] == r["SITUA_CONYUGAL"][3] == 2
    assert r["SITUA_CONYUGAL"][99] == 9
    r15, r10 = d._RECODE["2015"], d._RECODE["2010"]
    assert r15["DHSERSAL1"] == r15["DHSERSAL2"] and r10["DHSERSAL1"] == r10["DHSERSAL2"]
    assert r15["DHSERSAL1"][1] == 5 and r15["DHSERSAL1"][2] == 1     # Seguro Popular, IMSS
    assert 6 not in r15["DHSERSAL1"].values() and 6 not in r10["DHSERSAL1"].values()
    assert {r15["CONACT"][c] for c in range(11, 16)} == {10} and r15["CONACT"][20] == 30
    assert r15["SITUA_CONYUGAL"] == {6: 8}
    assert r10["NIVACAD"][5] == 9 and r10["NIVACAD"][12] == 14
    assert r15["IDENT_PAREJA"] == {98: 96}                            # «no sabe» dónde: No
    assert r10["LNACEDO_C"] == r10["RES05EDO_C"] == {900: 999, 999: 997}
    assert r10["LNACPAIS_C"] == r10["RES05PAI_C"]
    assert set(r10["LNACPAIS_C"].values()) == {997, 998}
    # 7b: the place of work holds both catalogs; its 999 is the entity's (08_15A: NE)
    assert r10["LTRABPAI_C"] == {**{k: v for k, v in r10["RES05PAI_C"].items() if k != 999},
                                 **r10["RES05EDO_C"]}
    # SINCO 2019 dropped group 59: 2015's 599 and 2010's 5999 join 52 (529)
    assert r15["OCUPACION_C"] == {599: 529} and r10["OCUACTIV_C"] == {5999: 5299}
    # 1990/1995 (6j): one activity list; 1990's 0 = not asked (blank); 1995's 8 «alguna vez
    # unida, estado civil desconocido» is not specified; countries are OtroPais (998)
    r90, r95 = d._RECODE["1990"], d._RECODE["1995"]
    assert {k: v for k, v in r90["CONACT"].items() if k} == r95["CONACT"]
    assert all(r90[item][0] != r90[item][0] for item in
               ("CONACT", "SITUA_CONYUGAL", "ENT_PAIS_RES_5A", "RELIGION", "CUADORM"))
    assert r95["SITUA_CONYUGAL"][8] == 9 and r95["EDAD"] == r95["HORTRA"] == {99: 999}
    assert set(r90["ENT_PAIS_NAC"].values()) == set(r95["ENT_PAIS_NAC"].values()) - {999} \
        == {997, 998}


_FD = Path(__file__).resolve().parent.parent / "data" / "dict" / "fd"
# The catalog-coded sources: (edition, catalog ZIP, catalog, raw item).
_CATALOGS = [
    ("2010", "catalogos_2010_dbf.zip", "TC_OCUPACION_2010", "OCUACTIV_C"),
    ("2010", "catalogos_2010_dbf.zip", "TC_SCIAN_2010", "ACTTRAB_C"),
    ("2010", "catalogos_2010_dbf.zip", "TC_RELIGION_2010", "OTRAREL_C"),
    ("2015", "eic2015_catalogos.zip", "TC_OCUPACION_2015", "OCUPACION_C"),
    ("2015", "eic2015_catalogos.zip", "TC_SECTOR_2015", "ACTIVIDADES_C"),
    ("2020", "Censo2020_clasificaciones_CPV_csv.zip", "OCUPACION", "OCUPACION_C"),
    ("2020", "Censo2020_clasificaciones_CPV_csv.zip", "ACTIVIDAD", "ACTIVIDADES_C"),
    ("2020", "Censo2020_clasificaciones_CPV_csv.zip", "RELIGION", "RELIGION"),
]


def _catalog(period: str, zip_name: str, stem: str) -> dict[str, str]:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import _dict_fd

    return _dict_fd.read_catalogs(_FD / period / zip_name)[stem]


@pytest.mark.parametrize("period,zip_name,stem,item", _CATALOGS)
def test_catalog_codes_derive(period, zip_name, stem, item):
    """Every code of an edition's occupation, activity and religion catalogs (INEGI's
    classification tables, ``build_cpv.py --dictionary``) has a derived category."""
    if not (_FD / period / zip_name).exists():
        pytest.skip(f"{period} catalogs not fetched (build_cpv.py --dictionary)")
    codes = pd.Series(sorted(_catalog(period, zip_name, stem)))
    derivations = [dv for dv in d._derivations("personas", period)
                   if any(item in d._ALIASES.get(s, (s,)) for s in dv.sources)]
    sector = [dv for dv in derivations if dv.columns == ("SECTOR",)]       # 6o: activity
    derivations = [dv for dv in derivations if dv.columns != ("RELIGION_INEGI",)]   # 7g
    assert len(derivations) - len(sector) == 1 and len(sector) <= 1
    for dv in sector:                    # every activity code has a sector (none blank)
        (source,) = dv.sources
        src = pd.DataFrame({source: d._codes(codes, d._RECODE.get(period, {}).get(source))})
        values = dv.func(src)["SECTOR"]
        assert values.notna().all() and "Blanco por pase" not in set(values)
    dv = next(dv for dv in derivations if dv not in sector)
    (source,) = dv.sources
    src = pd.DataFrame({source: d._codes(codes, d._RECODE.get(period, {}).get(source))})
    ((name, values),) = dv.func(src).items()
    assert values.notna().all(), codes[values.isna().to_numpy()].tolist()
    assert "Blanco por pase" not in set(values)
    if item in ("OCUACTIV_C", "OCUPACION_C"):              # SINCO's group, 59 → 52
        width = len(codes[0])
        groups = {c: int(c[:2]) for c in codes}
        assert set(groups.values()) - {59} <= set(d._legacy_map("personas", name))
        if period != "2020":
            assert {c for c, g in groups.items() if g == 59} == {"5" + "9" * (width - 1)}
    if item == "OTRAREL_C":                                 # the 2010 ITER's groups (6f)
        by = pd.Series(codes.str[:2].to_numpy(), index=values.astype(str).to_numpy())
        assert set(by["Católica"]) == {"11"}
        assert set(by["Protestante/cristiano evangélico"]) == {"13", "14", "15", "22"}
        assert set(by["Otros credos"]) == {"12", *(str(g) for g in range(21, 30))}
        assert set(by["Sin religión / Sin adscripción religiosa"]) == {"31"}
        neo = codes[values.astype(str).eq("Protestante/cristiano evangélico").to_numpy()
                    & codes.str.startswith("22").to_numpy()]
        assert neo.tolist() == ["220100"]                  # neo-Israelites: 2020's grouping
        # 7g: RELIGION_INEGI, Censo 2010's own classification (the neo-Israelites a
        # judaic credo, as its ITER's POTRAS_REL), differs there only
        inegi = d._religion_inegi_2010(src)["RELIGION_INEGI"].astype(str)
        moved = codes[inegi.ne(values.astype(str)).to_numpy()]
        assert moved.tolist() == ["220100"] and set(inegi[moved.index]) == {"Otros credos"}


def test_cpv_derivations_listing():
    full = mxcensus.cpv_derivations()
    assert set(full.columns) == {"TABLE", "COLUMN", "SOURCES", "PERIODS"}
    assert not full.duplicated(["TABLE", "COLUMN", "PERIODS"]).any()
    for period in ("2010", "2015", "2020", "2025"):             # once per edition
        assert not mxcensus.cpv_derivations(period=period).duplicated(["TABLE", "COLUMN"]).any()
    p25 = set(mxcensus.cpv_derivations("personas", 2025)["COLUMN"])
    p20 = set(mxcensus.cpv_derivations("personas", 2020)["COLUMN"])
    assert p20 - p25 == {"RELIGION_CAT", "IDENT_HIJO_CAT",       # 2025 lacks the items
                         "INGTRMEN_SM"}                          # 7c: and the wage table
    assert {"DHSERSAL_SALUD_PUBLICA", "DHSERSAL_IMSS_BIENESTAR"} <= p25
    assert not set(d.DHSERSAL_RENAMES) & p20                       # legacy names gone
    dhsersal = {c for c in p20 if c.startswith("DHSERSAL_")} - {"DHSERSAL_IMSS_BIENESTAR"}
    p15 = set(mxcensus.cpv_derivations("personas", 2015)["COLUMN"])
    commute = {f"{prefix}_{label}" for prefix, item in (("MED_TRASLADO_ESC", d._ESC[0]),
                                                        ("MED_TRASLADO_TRAB", d._TRAB[0]))
               for label in d._traslado_2015(item).values()}
    migration = {"ENT_PAIS_NAC_CAT", "ENT_PAIS_NAC_INEGI",            # 6y: INEGI's too
                 "ENT_PAIS_RES_CAT"}
    # 7a: the residence five years earlier and the place of work by municipality, INEGI's
    # place of work; 7b: in 2010 and 2015 too, with the place of school (not asked in 2010)
    work = {"LUGAR_RES_5A", "LUGAR_TRAB", "ENT_PAIS_TRAB_INEGI"}
    school = {"LUGAR_ASI", "ENT_PAIS_ASI_INEGI"}
    coresidence = {"IDENT_PAREJA_CAT", "MADRE_EN_VIVIENDA", "PADRE_EN_VIVIENDA"}
    coarse = {"OCUPACION_C_COARSE", "ACTIVIDADES_C_COARSE", "SECTOR"}      # 6o: SECTOR
    educ = {"EDUC", "EDUC_INEGI", "EDUC_INEGI_DET"}               # 6k, 6w: every edition
    assert educ <= p20 & p25
    head = {"HOGJEF_SEXO"}                                         # 6t: 1995–2025
    ind = {"HOG_IND"}                                              # 6w: 2000–2025
    clase = {"CLASE_HOG"}                                  # 6z: 2000, 2010–2025 (both tables)
    assert head | ind | clase <= p20 & p25
    sm = {"INGTRMEN_SM"}                                           # 7c: 2000, 2010–2020
    line = {"LINEA_PARENTESCO"}                                    # 8f: 1990, 2005–2025
    assert line <= p20 & p25
    assert p15 == {"EDAD_CAT", "EDAD_QUIN", "INGTRMEN_CAT", *sm, *educ, "CONACT_CAT",
                   "SITUA_CONYUGAL_CAT",
                   "IDENT_MADRE_CAT", "IDENT_PADRE_CAT", *migration, *coresidence,
                   *dhsersal, *commute, *coarse, *head, *ind, *clase, *work, *school, *line}
    assert {"MED_TRASLADO_ESC_Caminando", "MED_TRASLADO_TRAB_Transporte de personal"} <= p15 & p20
    assert {"MADRE_EN_VIVIENDA", "PADRE_EN_VIVIENDA", "SIN_DISC_LIM"} <= p20 & p25
    # 7a: five-year ages (every edition), the residence by municipality, the place of school
    # and work by INEGI's rule, the grouped commute modes (2020/2025); the health access
    # and the Afro-descendant household (2025)
    groups = {f"{p}_{g}" for p in ("MED_TRASLADO_ESC", "MED_TRASLADO_TRAB")
              for g in ("METRO_T", "BUS_T", "TAXI_T")}
    assert {"EDAD_QUIN", *work, *school, *groups} <= p20 & p25
    assert {"DHSERSAL_AFIL_ACCESO", "HOG_AFRO"} <= p25 - p20
    assert set(mxcensus.cpv_derivations("personas", 2010)["COLUMN"]) == {
        "EDAD_CAT", "EDAD_QUIN", "INGTRMEN_CAT", *sm, "HORTRA_CAT", *educ, "CONACT_CAT",
        "SITUA_CONYUGAL_CAT", "LIM_ACTIVIDAD", "RELIGION_CAT", *migration, *coresidence,
        *dhsersal, *coarse, *head, *ind, *clase, *work, "RELIGION_INEGI", *line}    # 7g
    rooms = {"OCUP_CUARTO_CAT"}                                    # 6z: 2010–2025
    assert set(mxcensus.cpv_derivations("viviendas", 2010)["COLUMN"]) == {   # 6n, 6s, 6x
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT", "JEFE_SEXO",
        *ind, *clase, *rooms}
    v15 = set(mxcensus.cpv_derivations("viviendas", 2015)["COLUMN"])
    assert v15 == {"CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT",
                   *(f"FINANCIAMIENTO_{v}" for v in d._financiamiento_2015().values()), *ind,
                   *clase, *rooms, "INGR_OTROS"}                   # 6z: INGR_OTROS 2015–2025
    v20 = set(mxcensus.cpv_derivations("viviendas", 2020)["COLUMN"])
    assert {"FINANCIAMIENTO_Banco", "FINANCIAMIENTO_FONHAPO"} <= v15 & v20
    assert {*clase, *rooms, "INGR_OTROS"} <= v20 & set(
        mxcensus.cpv_derivations("viviendas", 2025)["COLUMN"])
    assert ind <= v20 & set(mxcensus.cpv_derivations("viviendas", 2025)["COLUMN"])   # 6x
    dhs2000 = {"DHSERSAL_IMSS", "DHSERSAL_ISSSTE", "DHSERSAL_P_D_M", "DHSERSAL_Otro",
               "DHSERSAL_No afiliado", "DHSERSAL_ISSSTE_T", "DHSERSAL_PUB", "DHSERSAL_AFIL"}
    assert set(mxcensus.cpv_derivations("personas", 2000)["COLUMN"]) == {     # 6i
        "EDAD_CAT", "EDAD_QUIN", "INGTRMEN_CAT", *sm, "HORTRA_CAT", *educ, "ACTIVIDADES_C_COARSE",
        "SECTOR", "CONACT_CAT", "SITUA_CONYUGAL_CAT", *migration, "RELIGION_CAT", *dhs2000,
        *head, *ind, *clase, *work,                    # 7c: the 1995 residence and work
        "OCUPACION_C_COARSE"}                          # 8e: the CMO through the bridge
    assert set(mxcensus.cpv_derivations("personas", 2005)["COLUMN"]) == {
        "EDAD_CAT", "EDAD_QUIN", *educ, "ENT_PAIS_RES_CAT", *dhs2000, "DHSERSAL_ISSSTE_E",
        "DHSERSAL_SALUD_PUBLICA", "DHSERSAL_Privado", *head, *ind, *line}
    assert set(mxcensus.cpv_derivations("viviendas", 2000)["COLUMN"]) == {
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT", "JEFE_SEXO",
        *ind, *clase,                               # 6x: its dwelling rows are households
        "PRIMER_HOGAR", "TOTCUART_INEGI"}           # 7f
    assert set(mxcensus.cpv_derivations("viviendas", 2005)["COLUMN"]) == {
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "JEFE_SEXO"}
    # 6v: the Conteo 2005's households (the only household table); 6x: HOG_IND there
    hog = mxcensus.cpv_derivations("hogares")
    assert set(hog["COLUMN"]) == {"CLAVIVP_CAT", "JEFE_SEXO", *ind}
    assert set(hog["PERIODS"]) == {"2005"}
    assert d.derived_dtypes("hogares", "2005") == {
        **{c: d.derived_dtypes("viviendas", "2005")[c] for c in ("CLAVIVP_CAT", "JEFE_SEXO")},
        "HOG_IND": d.derived_dtypes("personas", "2005")["HOG_IND"]}
    # 6x: the household's HOG_IND, read from the members' person items
    members = full[full["COLUMN"].eq("HOG_IND") & full["TABLE"].ne("personas")]
    assert set(members["SOURCES"]) == {"PARENTESCO, HLENGUA"}
    assert {p for ps in members["PERIODS"] for p in ps.split(", ")} == set(d._IND_CODES)
    assert d._member_sources("viviendas", "2020") == ("PARENTESCO", "HLENGUA")
    assert d._member_sources("viviendas", "2025") == ("PARENTESCO", "HLENGUA", "AFRODES")
    assert d._member_sources("viviendas", "2005") == d._member_sources("personas", "2025") == ()
    # 6s: 2020/2025 publish JEFE_SEXO as a dwelling item, 1990/1995 no household indicator
    assert all("JEFE_SEXO" not in set(mxcensus.cpv_derivations("viviendas", p)["COLUMN"])
               for p in (1990, 1995, 2015, 2020, 2025))
    oldest = {"EDAD_CAT", "EDAD_QUIN", "INGTRMEN_CAT", "HORTRA_CAT", *educ,          # 6j
              "CONACT_CAT", "SITUA_CONYUGAL_CAT", *migration}
    assert set(mxcensus.cpv_derivations("personas", 1990)["COLUMN"]) == {
        *oldest, "RELIGION_CAT", "SECTOR", *line}
    assert set(mxcensus.cpv_derivations("personas", 1995)["COLUMN"]) == {*oldest, *head}
    assert set(mxcensus.cpv_derivations("viviendas", 1990)["COLUMN"]) == {
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT"}
    assert set(mxcensus.cpv_derivations("viviendas", 1995)["COLUMN"]) == {
        "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT"}
    for period in ("1990", "1995"):
        assert not mxcensus.cpv_derivations(period=period).duplicated(["TABLE", "COLUMN"]).any()
    assert mxcensus.cpv_derivations("personas", 1980).empty
    with pytest.raises(ValueError, match="migrantes"):
        d.derived_dtypes("migrantes", "2025")


# --- derive on synthetic raw frames --------------------------------------------------------

def _persons_2025() -> pd.DataFrame:
    rows = [
        # EDAD INGTRMEN HORTRA NIVACAD ESCOLARI OCUP ACT DIS_VER DHS1 DHS2 TRAB1 CONACT SITUA NAC RES IDM IDP IDPAR
        ("034", "012000", "045", "02", "06", "611", "1110", "3", "05", "", "01", "10", "03",
         "536", "001", "02", "97", "96"),
        ("999", "", "", "", "", "", "", "2", "06", "01", "", "", "99",
         "001", "", "98", "96", "99"),
    ]
    cols = ["EDAD", "INGTRMEN", "HORTRA", "NIVACAD", "ESCOLARI", "OCUPACION_C",
            "ACTIVIDADES_C", "DIS_VER", "DHSERSAL1", "DHSERSAL2", "MED_TRASLADO_TRAB1",
            "CONACT", "SITUA_CONYUGAL", "ENT_PAIS_NAC", "ENT_PAIS_RES_5A", "IDENT_MADRE",
            "IDENT_PADRE", "IDENT_PAREJA"]
    df = pd.DataFrame(rows, columns=cols, dtype="str")
    for col in ("DIS_OIR", "DIS_CAMINAR", "DIS_RECORDAR", "DIS_BANARSE", "DIS_HABLAR"):
        df[col] = "1"
    df["DIS_MENTAL"] = ["6", "9"]
    for col in ("MED_TRASLADO_ESC1", "MED_TRASLADO_ESC2", "MED_TRASLADO_ESC3",
                "MED_TRASLADO_TRAB2", "MED_TRASLADO_TRAB3"):
        df[col] = ""
    df["CVE_ENT"] = "01"
    # 6t: one dwelling, a female head (101) and her son; 6w: only the son speaks an
    # indigenous language (a child does not make the household indigenous)
    df["ID_VIV"], df["PARENTESCO"], df["SEXO"] = "010010000001", ["101", "301"], ["3", "1"]
    df["HLENGUA"] = ["3", "1"]
    df["TIPOHOG"] = "1"         # 6z: the household's type (nuclear), from the dwelling file
    # 7a: the own municipality and its 2020 residence there, the place of work (the first
    # works in the entity), no access item (affiliated), not Afro-descendant
    df["CVE_MUN"], df["MUN_RES_5A"] = "001", ["001", ""]
    df["ENT_PAIS_ASI"], df["ENT_PAIS_TRAB"] = "", ["001", ""]
    df["MUN_ASI"], df["MUN_TRAB"] = "", ["001", ""]                          # 7b
    df["DHSERSAL_ACCESO"], df["AFRODES"] = "", "3"
    return df


def _each_a_household(df: pd.DataFrame) -> pd.DataFrame:
    """Every row its own dwelling and its head (2020/2025 rows replicated for item tests)."""
    return df.assign(ID_VIV=[f"0100{i:08d}" for i in range(len(df))], PARENTESCO="101")


# 6x: a head who speaks no indigenous language, in each edition's codes
_HEAD_ALONE = {"2000": {"OTROPARE_C": "100", "HLENGUA": "2"},
               "2010": {"PARENT": "01", "HLENGUA": "3"}, "2015": {"PARENT": "1", "HLENGUA": "3"},
               "2020": {"PARENTESCO": "101", "HLENGUA": "3"},
               "2025": {"PARENTESCO": "101", "HLENGUA": "3", "AFRODES": "3"}}     # 7a


# 6z: a nuclear household of one person with no income from other sources than work; 7f:
# CGPV 2000's first household, its kitchen slept in (a room)
_HOUSEHOLD_ITEMS = {"TIPOHOG": "1", "NUMPERS": "1", "INGR_PEROTROPAIS": "2",
                    "INGR_PERDENTPAIS": "4", "INGR_AYUGOB": "6", "INGR_JUBPEN": "8",
                    "NUMHOG": "1", "COCINA": "1", "COCDOR": "3"}


def _derive_dwellings(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    """``derive`` on a synthetic dwelling frame: one dwelling (2000: household) per row,
    whose members (6x, ``derive(members=)``) are one head who speaks no indigenous language
    (``HOG_IND`` «No»); the 6z household items a test leaves out (:data:`_HOUSEHOLD_ITEMS`)
    are added."""
    sources = {s for x in d._derivations("viviendas", period) for s in x.sources}
    frame = frame.assign(**{c: v for c, v in _HOUSEHOLD_ITEMS.items()      # 6z, if left out
                            if c in sources and c not in frame})
    if not d._member_sources("viviendas", period):
        return d.derive(frame, "viviendas", period)
    n = len(frame)
    keys = {"ENT": "01", "MUN": "001", "LOC": "0001", "NUMVIV": [f"{i:06d}" for i in range(n)],
            "NUMHOG": "1"} if period == "2000" else \
        {"ENT": "01", "ID_VIV": [f"{i:08d}" for i in range(n)]}
    keyed = frame.assign(**keys)
    out = d.derive(keyed, "viviendas", period,
                   members=keyed[list(keys)].assign(**_HEAD_ALONE[period]))
    assert out["HOG_IND"].eq("No").all()
    assert "HOG_AFRO" not in out or out["HOG_AFRO"].eq("No").all()                # 7a
    return out


def test_derive_persons_2025_recodes():
    out = d.derive(_persons_2025(), "personas", 2025)
    first, second = out.iloc[0], out.iloc[1]
    assert first["EDAD_CAT"] == "25-49" and second["EDAD_CAT"] == "No especificado"
    assert first["INGTRMEN_CAT"] == "10,000-19,999" and second["INGTRMEN_CAT"] == "Blanco por pase"
    assert first["HORTRA_CAT"] == "41-48" and second["HORTRA_CAT"] == "Blanco por pase"
    assert first["EDUC"] == "Primaria_com" and second["EDUC"] == "Blanco por pase"
    assert first["DIS_CON"] == "Sí" and first["DIS_LIMI"] == "No"
    assert second["DIS_CON"] == "No" and second["DIS_LIMI"] == "Sí"
    assert (first["DISCAPACIDAD"], first["LIMITACION"]) == ("Sí", "No")
    assert (second["DISCAPACIDAD"], second["LIMITACION"]) == ("No", "Sí")
    assert list(out["SIN_DISC_LIM"]) == ["No", "No"]
    # 2025's 05 is IMSS-BIENESTAR, its 06 the public health centres (2020: the reverse)
    assert (first["DHSERSAL_IMSS_BIENESTAR"], first["DHSERSAL_SALUD_PUBLICA"]) == (1, 0)
    assert (second["DHSERSAL_IMSS_BIENESTAR"], second["DHSERSAL_SALUD_PUBLICA"]) == (0, 1)
    assert second["DHSERSAL_IMSS"] == 1 and first["DHSERSAL_PUB"] == first["DHSERSAL_AFIL"] == 1
    assert first["MED_TRASLADO_TRAB_Caminando"] == 1
    assert first["MED_TRASLADO_TRAB_Blanco por pase"] == 1          # blank 2nd/3rd item
    assert first["MED_TRASLADO_ESC_Blanco por pase"] == 1 and first["MED_TRASLADO_ESC_Otro"] == 0
    assert first["CONACT_CAT"] == "Trabaja" and second["CONACT_CAT"] == "Blanco por pase"
    assert first["SITUA_CONYUGAL_CAT"] == "separado"                 # 03: separada of a marriage
    assert second["SITUA_CONYUGAL_CAT"] == "No especificado"         # 99
    assert first["ENT_PAIS_NAC_CAT"] == "OtroPais"                   # 536: Palaos (2020: 356)
    assert second["ENT_PAIS_NAC_CAT"] == "EstaEnt"
    assert first["ENT_PAIS_RES_CAT"] == "EstaEnt" and second["ENT_PAIS_RES_CAT"] == "Blanco por pase"
    assert (first["IDENT_MADRE_CAT"], first["IDENT_PADRE_CAT"]) == ("Vive en esta vivienda",
                                                                    "Ya falleció")
    assert first["IDENT_PAREJA_CAT"] == "No" and second["IDENT_MADRE_CAT"] == "No sabe"
    assert list(out["MADRE_EN_VIVIENDA"]) == ["Sí", "No"]           # 02; 98 = no sabe
    assert list(out["PADRE_EN_VIVIENDA"]) == ["No", "No"]           # 97 falleció; 96
    for col, dtype in d.derived_dtypes("personas", "2025").items():
        assert out[col].dtype == dtype, col
    assert out["EDAD_CAT"].cat.ordered



def test_inegi_birthplace_and_issste():
    """6y: ``ENT_PAIS_NAC_INEGI`` is ``ENT_PAIS_NAC_CAT`` with the unspecified entity (997,
    the legacy ``OtraEnt``) «No especificado», as INEGI's ``PNACOE``; ``DHSERSAL_ISSSTE_T``
    is the ISSSTE, federal or state (the EIC 2025's ``PDER_ISTE``)."""
    df = _each_a_household(pd.concat([_persons_2025()] * 2, ignore_index=True)).assign(
        ENT_PAIS_NAC=["997", "014", "001", "999"], DHSERSAL1=["03", "02", "01", "02"],
        DHSERSAL2=["", "", "", "03"])
    out = d.derive(df, "personas", 2025)
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["OtraEnt", "OtraEnt", "EstaEnt", "No especificado"]
    assert list(out["ENT_PAIS_NAC_INEGI"]) == ["No especificado", "OtraEnt", "EstaEnt",
                                               "No especificado"]
    assert out["ENT_PAIS_NAC_INEGI"].dtype == out["ENT_PAIS_NAC_CAT"].dtype
    assert list(out["DHSERSAL_ISSSTE_T"]) == [1, 1, 0, 1]
    assert list(out["DHSERSAL_ISSSTE"]) == [0, 1, 0, 1]
    assert list(out["DHSERSAL_ISSSTE_E"]) == [1, 0, 0, 1]
    assert list(out["DHSERSAL_PUB"]) == [1, 1, 1, 1]

def test_derive_persons_7a():
    """7a: five-year ages; the residence five years earlier by the own municipality and
    entity (the United States apart; 998 another country, 997 not specified); the place of
    school and work by INEGI's rule (as ``ENT_PAIS_NAC_INEGI``); the grouped commute modes
    (metro or metrobús, trolebús or bus, either taxi); affiliated or recognising an access
    to the public services; the Afro-descendant household (the indigenous household's
    members). Unknown codes raise."""
    df = _each_a_household(pd.concat([_persons_2025()] * 4, ignore_index=True)).assign(
        EDAD=["000", "004", "005", "074", "075", "110", "999", "034"],
        ENT_PAIS_RES_5A=["", "001", "001", "001", "014", "221", "998", "997"],
        MUN_RES_5A=["", "001", "005", "999", "", "", "", ""],
        ENT_PAIS_ASI=["", "001", "014", "221", "998", "997", "999", "536"],
        MUN_ASI=["", "002", "", "", "", "", "", ""],                         # 7b
        MED_TRASLADO_ESC1=["", "03", "04", "06", "09", "01", "12", "99"],
        MED_TRASLADO_ESC2=["", "05", "", "", "", "08", "", ""],
        DHSERSAL1=["09", "09", "01", "99", "05", "06", "07", "08"],
        DHSERSAL2="", DHSERSAL_ACCESO=["1", "3", "", "", "", "", "", ""],
        AFRODES=["1", "3", "9", "3", "3", "3", "3", "3"])
    out = d.derive(df, "personas", 2025)
    assert list(out["EDAD_QUIN"]) == ["0-4", "0-4", "5-9", "70-74", "75-130", "75-130",
                                      "No especificado", "30-34"]
    assert out["EDAD_QUIN"].cat.ordered
    assert list(out["LUGAR_RES_5A"]) == [
        "Blanco por pase", "Mismo municipio", "Otro municipio", "Municipio no especificado",
        "Otra entidad", "Estados Unidos", "Otro país", "No especificado"]
    assert list(out["ENT_PAIS_ASI_INEGI"]) == [                      # 536: Palaos (2020: 356)
        "Blanco por pase", "EstaEnt", "OtraEnt", "OtroPais", "OtroPais", "No especificado",
        "No especificado", "OtroPais"]
    assert list(out["LUGAR_ASI"]) == [                                    # 7b: by municipality
        "Blanco por pase", "Otro municipio", "Otra entidad", "Estados Unidos", "Otro país",
        "No especificado", "No especificado", "Otro país"]
    assert out["ENT_PAIS_ASI_INEGI"].dtype == out["ENT_PAIS_RES_CAT"].dtype
    assert list(out["MED_TRASLADO_ESC_METRO_T"]) == [0, 1, 0, 0, 0, 0, 0, 0]   # 03 + 05: once
    assert list(out["MED_TRASLADO_ESC_BUS_T"]) == [0, 0, 1, 1, 0, 0, 0, 0]
    assert list(out["MED_TRASLADO_ESC_TAXI_T"]) == [0, 0, 0, 0, 1, 1, 0, 0]
    assert list(out["DHSERSAL_AFIL_ACCESO"]) == [1, 0, 1, 0, 1, 1, 1, 1]       # 99: neither
    assert list(out["HOG_AFRO"]) == ["Sí", "No", "No", "No", "No", "No", "No", "No"]
    for col in ("EDAD_QUIN", "LUGAR_RES_5A", "ENT_PAIS_TRAB_INEGI", "HOG_AFRO",
                "DHSERSAL_AFIL_ACCESO", "MED_TRASLADO_TRAB_BUS_T"):
        assert out[col].dtype == d.derived_dtypes("personas", "2025")[col], col
    # the household's: the head's partner counts, a child does not (as HOG_IND)
    one = _persons_2025().assign(AFRODES=["3", "1"])
    assert list(d.derive(one, "personas", 2025)["HOG_AFRO"]) == ["No", "No"]
    assert list(d.derive(one.assign(PARENTESCO=["101", "201"]), "personas", 2025)
                ["HOG_AFRO"]) == ["Sí", "Sí"]
    for col, bad in (("HOG_AFRO", {"AFRODES": "7"}), ("DHSERSAL_AFIL_ACCESO",
                                                       {"DHSERSAL_ACCESO": "5"}),
                     ("LUGAR_RES_5A", {"ENT_PAIS_RES_5A": "001", "MUN_RES_5A": ""})):
        with pytest.raises(ValueError, match=col):
            d.derive(df.assign(**bad), "personas", 2025)
    # Censo 2020: the same codes, the own municipality under its raw name
    p20 = df.rename(columns={"CVE_ENT": "ENT", "CVE_MUN": "MUN"}).drop(
        columns=["DHSERSAL_ACCESO", "AFRODES"]).assign(
        ENT_PAIS_ASI="001", MUN_ASI="001", ENT_PAIS_NAC="001", SITUA_CONYUGAL="3",
        RELIGION="1101", IDENT_HIJO="")
    out20 = d.derive(p20, "personas", "2020")
    assert list(out20["LUGAR_RES_5A"]) == list(out["LUGAR_RES_5A"])
    assert "HOG_AFRO" not in out20 and "DHSERSAL_AFIL_ACCESO" not in out20


def test_derive_places_7b():
    """7b: the places by the own municipality and entity in the EIC 2015 (residence in
    2010, school, work: 2020's codes, un-padded entities) and Censo 2010 (residence in
    2005 from its entity or country item; work from its one item holding both catalogs,
    999 = the entity not specified, 900 = topic omitted, 700 «México (país)»); INEGI's
    entity-level place as ``LUGAR_*`` without the municipality. The own entity without a
    municipality raises."""
    p15 = pd.concat([_persons_2015()] * 4, ignore_index=True).assign(
        ID_VIV=[f"0100100{i:04d}" for i in range(8)], PARENT="1",
        ENT_PAIS_RES10=["", "1", "1", "1", "14", "221", "998", "997"],
        MUN_RES10=["", "001", "005", "999", "039", "", "", ""],
        ENT_PAIS_ASI=["", "1", "1", "14", "221", "998", "997", "999"],
        MUN_ASI=["", "001", "999", "", "", "", "", ""],
        ENT_PAIS_TRAB=["999", "997", "998", "415", "221", "30", "1", "1"],
        MUN_TRAB=["", "", "", "", "", "", "999", "002"])
    out = d.derive(p15, "personas", 2015)
    assert list(out["LUGAR_RES_5A"]) == [
        "Blanco por pase", "Mismo municipio", "Otro municipio", "Municipio no especificado",
        "Otra entidad", "Estados Unidos", "Otro país", "No especificado"]
    assert list(out["LUGAR_ASI"]) == [
        "Blanco por pase", "Mismo municipio", "Municipio no especificado", "Otra entidad",
        "Estados Unidos", "Otro país", "No especificado", "No especificado"]
    assert list(out["LUGAR_TRAB"]) == [
        "No especificado", "No especificado", "Otro país", "Otro país", "Estados Unidos",
        "Otra entidad", "Municipio no especificado", "Otro municipio"]
    own = {"Mismo municipio", "Otro municipio", "Municipio no especificado"}
    for place in ("ASI", "TRAB"):                                  # INEGI's, by entity
        inegi = out[f"ENT_PAIS_{place}_INEGI"].astype(object)
        lugar = out[f"LUGAR_{place}"].astype(object)
        assert list(inegi) == [
            "EstaEnt" if v in own else "OtraEnt" if v == "Otra entidad"
            else "OtroPais" if v in ("Estados Unidos", "Otro país") else v for v in lugar]
    for col in ("LUGAR_RES_5A", "LUGAR_ASI", "LUGAR_TRAB"):
        assert out[col].dtype == d.derived_dtypes("personas", "2015")[col] == d._LUGAR_RES
    p10 = pd.concat([_persons_2010()] * 3, ignore_index=True).assign(
        ID_VIV=[f"{i:08d}" for i in range(9)], PARENT="01",
        RES05EDO_C=["", "009", "009", "009", "021", "", "", "900", "999"],
        RES05PAI_C=["", "", "", "", "", "221", "600", "", ""],
        MUN05OTR_C=["", "002", "010", "999", "114", "", "", "", ""],
        LTRABPAI_C=["009", "009", "009", "015", "221", "600", "700", "900", "999"],
        LTRABMUN_C=["002", "005", "999", "033", "", "", "", "", ""])
    out = d.derive(p10, "personas", 2010)
    assert list(out["LUGAR_RES_5A"]) == [
        "Blanco por pase", "Mismo municipio", "Otro municipio", "Municipio no especificado",
        "Otra entidad", "Estados Unidos", "Otro país", "No especificado", "No especificado"]
    assert list(out["LUGAR_TRAB"]) == [
        "Mismo municipio", "Otro municipio", "Municipio no especificado", "Otra entidad",
        "Estados Unidos", "Otro país", "No especificado", "No especificado", "No especificado"]
    assert list(out["ENT_PAIS_TRAB_INEGI"]) == [
        *["EstaEnt"] * 3, "OtraEnt", "OtroPais", "OtroPais", *["No especificado"] * 3]
    assert "LUGAR_ASI" not in out and "ENT_PAIS_ASI_INEGI" not in out        # not asked
    for frame, period, bad in ((p15, 2015, {"MUN_TRAB": ""}),
                               (p10, 2010, {"LTRABMUN_C": ""})):
        with pytest.raises(ValueError, match="LUGAR_TRAB"):
            d.derive(frame.assign(**bad), "personas", period)


def test_derive_places_2000():
    """7c: CGPV 2000's residence in 1995 (``RES95EDO_C`` entity or country + ``MUN95OTR_C``)
    and place of work (``LTRABPAI_C`` + ``LTRABMUN_C``), Censo 2010's layout in one item:
    600 = a country not known, 999 = not specified, 221 the United States."""
    p00 = pd.concat([_persons_2000()] * 2, ignore_index=True).assign(
        NUMVIV=[f"{i:06d}" for i in range(8)], NUMHOG="1", OTROPARE_C="100",
        RES95EDO_C=["", "001", "001", "001", "014", "221", "600", "999"],
        MUN95OTR_C=["", "001", "005", "999", "039", "", "", ""],
        LTRABPAI_C=["001", "001", "001", "015", "221", "415", "600", "999"],
        LTRABMUN_C=["001", "003", "999", "033", "", "", "", ""])
    out = d.derive(p00, "personas", 2000)
    assert list(out["LUGAR_RES_5A"]) == [
        "Blanco por pase", "Mismo municipio", "Otro municipio", "Municipio no especificado",
        "Otra entidad", "Estados Unidos", "Otro país", "No especificado"]
    assert list(out["LUGAR_TRAB"]) == [
        "Mismo municipio", "Otro municipio", "Municipio no especificado", "Otra entidad",
        "Estados Unidos", "Otro país", "Otro país", "No especificado"]
    assert list(out["ENT_PAIS_TRAB_INEGI"]) == [
        *["EstaEnt"] * 3, "OtraEnt", *["OtroPais"] * 3, "No especificado"]
    with pytest.raises(ValueError, match="LUGAR_RES_5A"):          # own entity, no municipality
        d.derive(p00.assign(MUN95OTR_C=""), "personas", 2000)


# 7c: (edition, entity, municipality) → the monthly minimum wage, and incomes on each side of
# its bounds → INEGI's groups. 2000: area C (Aguascalientes) 981; 2010: area A (Ecatepec,
# 15-033) 1,723.80, area B (Coatzintla, 30-040) 1,675.20; 2015: Coatzintla in area B, the
# catalog's Coacoatzintla (30-036) in A; 2020: San Quintín (02-006) in the border zone,
# Hermosillo (26-030) the rest of the country.
_WAGES = {("2000", 1, 1): 981, ("2000", 9, 10): 1137, ("2000", 14, 39): 1053,
          ("2010", 15, 33): 1723.8, ("2010", 30, 40): 1675.2, ("2010", 30, 36): 1634.1,
          ("2015", 30, 40): 1993.5, ("2015", 30, 36): 2103, ("2015", 19, 39): 2103,
          ("2020", 2, 6): 5566.8, ("2020", 26, 30): 3696.6, ("2020", 26, 2): 5566.8,
          ("2020", 8, 37): 5566.8, ("2020", 19, 39): 3696.6}


def test_salario_minimo_7c():
    for (period, ent, mun), wage in _WAGES.items():
        got = d._salario_minimo(period, pd.Series([float(ent)]), pd.Series([float(mun)]))
        assert got.iloc[0] == round(wage * 100), (period, ent, mun)
    # 2000/2010: the same CONASAMI areas (A 65 municipalities and B 55 in INEGI's 2010
    # catalog; whole entities: Baja California, Baja California Sur, the Distrito Federal);
    # 2015: A = both; 2020: the border zone's 43 municipalities and San Quintín
    assert d._SALARIOS_MINIMOS["2000"][1][0][1] is d._SALARIOS_MINIMOS["2010"][1][0][1]
    assert sum(len(m) for m in d._SM_A.values() if m) == 65 - 26
    assert sum(len(m) for m in d._SM_B.values()) == 55
    assert sum(len(m) for m in d._SM_A_2015.values() if m) == 120 - 26
    assert sum(len(m) for m in d._ZLFN.values() if m) == 43 - 5


def test_derive_income_sm_7c():
    """INGTRMEN_SM at each bound, compared in cents (5 × 1,675.20 = 8,376 exactly): 2000's
    groups (below 1; from 1 to 2; above 2, below 3; from 3 to 5; above 5 to 10), 2010–2020's
    (up to 1; above 1 to 2; …), no income, above 999,997 (999998), not specified (999999),
    not employed (blank)."""
    def derive(period, ent, mun, incomes, frame):
        df = pd.concat([frame] * len(incomes), ignore_index=True).iloc[:len(incomes)]
        df = _each_a_household(df) if period in ("2020",) else df
        key = {"2000": "INGRESOS"}.get(period, "INGTRMEN")
        return list(d.derive(df.assign(**{key: incomes, "ENT": ent, "MUN": mun}),
                             "personas", period)["INGTRMEN_SM"])

    p00 = pd.concat([_persons_2000()] * 4, ignore_index=True).assign(
        NUMVIV=[f"{i:06d}" for i in range(16)], NUMHOG="1", OTROPARE_C="100", CONACT="10",
        MUN95OTR_C="", RES95EDO_C="", LTRABPAI_C="001", LTRABMUN_C="001")
    cuts = ["0", "980", "981", "1962", "1963", "2942", "2943", "4905", "4906", "9810", "9811",
            "999998", "999999", ""]
    assert derive("2000", "01", "001", cuts, p00) == [
        "No recibe ingresos", "Menos de 1 s.m.", *["De 1 hasta 2 s.m."] * 2,
        *["Más de 2 y menos de 3 s.m."] * 2, *["De 3 hasta 5 s.m."] * 2,
        *["Más de 5 hasta 10 s.m."] * 2, "Más de 10 s.m.", "Más de 10 s.m.", "No especificado",
        "Blanco por pase"]
    p10 = pd.concat([_persons_2010()] * 4, ignore_index=True).assign(
        ID_VIV=[f"{i:08d}" for i in range(12)], PARENT="01", LTRABPAI_C="", LTRABMUN_C="",
        RES05EDO_C="", RES05PAI_C="", MUN05OTR_C="")
    later = ["No recibe ingresos", "Hasta 1 s.m.", "Más de 1 a 2 s.m.", "Más de 1 a 2 s.m.",
             "Más de 2 a 3 s.m.", "Más de 3 a 5 s.m.", "Más de 5 a 10 s.m.", "Más de 10 s.m."]
    assert derive("2010", "30", "040", ["0", "1675", "1676", "3350", "3351", "8376", "8377",
                                        "16753"], p10) == later
    assert derive("2010", "15", "033", ["1723", "1724"], p10) == later[1:3]
    p15 = pd.concat([_persons_2015()] * 2, ignore_index=True).assign(
        ID_VIV=[f"0100100{i:04d}" for i in range(4)], PARENT="1", ENT_PAIS_TRAB="", MUN_TRAB="")
    assert derive("2015", "30", "040", ["1993", "1994"], p15) == later[1:3]      # area B
    assert derive("2015", "30", "036", ["2103", "2104"], p15) == later[1:3]      # catalog's A
    p20 = _persons_2025().drop(columns=["CVE_ENT", "CVE_MUN"]).assign(   # 2020's own items
        SITUA_CONYUGAL=["3", "9"], RELIGION="1101", IDENT_HIJO="", ENT_PAIS_TRAB="",
        MUN_TRAB="", ENT_PAIS_ASI="", MUN_ASI="", MUN_RES_5A="", ENT_PAIS_RES_5A="",
        ENT_PAIS_NAC="356")                                 # 2025 renumbered Palaos (536)
    assert derive("2020", "02", "006", ["5566", "5567"], p20) == later[1:3]      # San Quintín
    assert derive("2020", "26", "030", ["3696", "3697"], p20) == later[1:3]
    out = d.derive(p00.assign(INGRESOS="1000"), "personas", 2000)
    assert out["INGTRMEN_SM"].dtype == d.derived_dtypes("personas", "2000")["INGTRMEN_SM"] \
        == d._SM_2000
    assert d.derived_dtypes("personas", "2015")["INGTRMEN_SM"] == d._SM
    assert "INGTRMEN_SM" not in d.derived_dtypes("personas", "2025")             # no table


_FD_WAGES = {"2010": ("catalogos_2010_dbf.zip", "TC_TABLA_SALARIOS_MUN_2010.DBF"),
             "2015": ("eic2015_catalogos.zip", "TC_SALARIO_MUN_2015.xls")}


@pytest.mark.parametrize("period", sorted(_FD_WAGES))
def test_wage_tables_equal_inegi_catalogs(period):
    """7c: the 2010/2015 wage areas = INEGI's own municipal catalogs (the monthly wage of
    every municipality; 2015's slip included: Coacoatzintla, not Coatzintla, in area A)."""
    import sys
    import zipfile

    zip_name, member = _FD_WAGES[period]
    if not (_FD / period / zip_name).exists():
        pytest.skip(f"{period} catalogs not fetched (build_cpv.py --dictionary)")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import _dbf
    import _dict_fd

    raw = zipfile.ZipFile(_FD / period / zip_name).read(member)
    if period == "2010":
        t = _dbf.read_dbf(raw).table.to_pandas()
        ent, mun, wage = t["CVE_ENT"], t["CVE_MUN"], t["SALARIO"]
    else:
        rows = next(iter(_dict_fd.read_xls(raw).values()))[1:]
        ent, mun, wage = (pd.Series([r[c] for r in rows]) for c in ("A", "C", "F"))
    ours = d._salario_minimo(period, pd.to_numeric(ent).astype(float),
                             pd.to_numeric(mun).astype(float))
    assert len(ours) > 2400
    assert (ours.to_numpy() == (pd.to_numeric(wage) * 100).round().to_numpy()).all()


def test_educ_inegi():
    """``EDUC_INEGI`` = ``EDUC`` with the técnica studies after primaria (2020's level 6, any
    grade) apart: INEGI's primaria completa (the ITER 1990–2020) leaves them out."""
    legacy = d._legacy_dtypes("personas")["EDUC"]
    assert d._EDUC_INEGI.ordered and legacy.ordered
    assert [c for c in d._EDUC_INEGI.categories if c != "Técnica_primaria"] == list(legacy.categories)
    src = pd.DataFrame({"NIVACAD": [2, 6, 6, 6, 3, 7, 99, np.nan],
                        "ESCOLARI": [6, 1, 4, 99, 3, 2, 99, np.nan]})
    out = d._educ(src)
    assert list(out["EDUC"]) == ["Primaria_com"] * 4 + ["Secundaria_com", "Posbásica",
                                                        "No especificado", "Blanco por pase"]
    assert list(out["EDUC_INEGI"]) == ["Primaria_com", *["Técnica_primaria"] * 3,
                                       *list(out["EDUC"])[4:]]
    assert out["EDUC_INEGI"].dtype == d.derived_dtypes("personas", "2020")["EDUC_INEGI"]
    unknown = d._educ(pd.DataFrame({"NIVACAD": [6.0, 2.0], "ESCOLARI": [7.0, 9.0]}))
    assert unknown["EDUC"].isna().all() and unknown["EDUC_INEGI"].isna().all()   # derive raises
    # Conteo 1995: a technical career after primaria (its requisite P5_7 1) of a primaria
    tec95 = d._educ_1995(pd.DataFrame({"P5_3": [np.nan], "P5_4B": [2.0], "P5_4A": [6.0],
                                       "P5_5": [1.0], "P5_7": [1.0]}))
    assert (tec95["EDUC"].iloc[0], tec95["EDUC_INEGI"].iloc[0]) == ("Primaria_com",
                                                                  "Técnica_primaria")


def test_educ_inegi_det():
    """6w: ``EDUC_INEGI_DET`` = ``EDUC_INEGI`` with «Posbásica» split by the 2020 level:
    media superior (bachillerato 4/5, técnica after secundaria 7, normal básica 9), superior
    (técnica after preparatoria 8, normal de licenciatura 10, licenciatura 11), posgrado
    (12–14); every other category as in ``EDUC_INEGI``."""
    det = d._EDUC_INEGI_DET
    assert det.ordered and det == d.derived_dtypes("personas", "2025")["EDUC_INEGI_DET"]
    assert [c for c in det.categories if c not in ("Media_superior", "Superior", "Posgrado")] \
        == [c for c in d._EDUC_INEGI.categories if c != "Posbásica"]
    levels = [4, 5, 7, 9, 8, 10, 11, 12, 13, 14, 2, 6, 99, np.nan]
    out = d._educ(pd.DataFrame({"NIVACAD": levels, "ESCOLARI": [2] * 10 + [6, 1, 99, np.nan]}))
    assert list(out["EDUC_INEGI_DET"]) == [*["Media_superior"] * 4, *["Superior"] * 3,
                                           *["Posgrado"] * 3, "Primaria_com", "Técnica_primaria",
                                           "No especificado", "Blanco por pase"]
    assert (out["EDUC_INEGI_DET"].astype(object)
            .replace(["Media_superior", "Superior", "Posgrado"], "Posbásica")
            .equals(out["EDUC_INEGI"].astype(object)))
    # each edition's own items: 2000 técnica after preparatoria (ANTESC 3), CGPV 1990's
    # normal básica after secundaria, the Conteo 1995's posgrado
    p00 = d.derive(_persons_2000().assign(ANTESC=["3", "", "", ""], ESCOLARI=["2", "", "", "9"]),
                   "personas", 2000)
    assert list(p00["EDUC_INEGI_DET"])[::3] == ["Superior", "Posgrado"]   # maestría (8 → 13)
    p90 = d.derive(_persons_1990().assign(TEC_SEC=["0"] * 5, NOR_BAS=["2", "0", "0", "0", "0"]),
                   "personas", 1990)
    assert p90["EDUC_INEGI_DET"].iloc[0] == "Media_superior"
    p95 = d.derive(_persons_1995().assign(P5_4B=["7", "2", "", "", ""],
                                          P5_4A=["2", "4", "", "", ""]), "personas", 1995)
    assert p95["EDUC_INEGI_DET"].iloc[0] == "Posgrado"


def test_disability_flags_inegi_vs_legacy():
    """INEGI's rules: code 8 («degree unknown») is a disability; a limitation (some
    difficulty) excludes the disabled. The legacy flags count otherwise."""
    df = _each_a_household(_persons_2025().iloc[[0, 0, 0]].reset_index(drop=True))
    df[list(d._DIS_ITEMS)] = [["1", "8", "1", "1", "1", "1"],     # degree unknown
                              ["2", "3", "1", "1", "1", "1"],     # some and much difficulty
                              ["2", "9", "1", "1", "1", "1"]]     # some + unspecified
    out = d.derive(df, "personas", 2025)
    assert list(out["DISCAPACIDAD"]) == ["Sí", "Sí", "No especificado"]
    assert list(out["LIMITACION"]) == ["No", "No", "Sí"]
    assert list(out["DIS_CON"]) == ["No especificado", "Sí", "No especificado"]
    assert list(out["DIS_LIMI"]) == ["No especificado", "Sí", "Sí"]


def test_sin_disc_lim_inegi_rule():
    """INEGI's PSIND_LIM (6g): no difficulty of any degree, no mental condition; only the
    persons whose seven answers are all unspecified are «No especificado» — one unspecified
    answer among «no» answers counts as none, unlike the legacy cells (all seven «no»)."""
    rows = [("111111", "6", "Sí"), ("191111", "9", "Sí"), ("999999", "6", "Sí"),
            ("999999", "9", "No especificado"), ("111111", "5", "No"),
            ("911112", "9", "No"), ("181111", "6", "No")]
    df = _each_a_household(_persons_2025().iloc[[0] * len(rows)].reset_index(drop=True))
    df[list(d._DIS_ITEMS)] = [list(items) for items, _, _ in rows]
    df["DIS_MENTAL"] = [mental for _, mental, _ in rows]
    out = d.derive(df, "personas", 2025)
    assert list(out["SIN_DISC_LIM"]) == [want for _, _, want in rows]
    assert out["SIN_DISC_LIM"].dtype == d._YES_NO
    with pytest.raises(ValueError, match="SIN_DISC_LIM"):           # an unknown code
        d.derive(df.assign(DIS_MENTAL="7"), "personas", 2025)


def test_derive_2020_has_no_recode():
    """The same codes mean the 2020 categories in 2020 (no recode): 05 = Seguro Popular."""
    df = _persons_2025().rename(columns={"CVE_ENT": "ENT"}).assign(
        SITUA_CONYUGAL=["3", "9"], RELIGION=["1101", "9999"], IDENT_HIJO=["", "96"],
        ENT_PAIS_NAC=["356", "001"])
    out = d.derive(df, "personas", "2020")
    assert out.loc[0, "DHSERSAL_SALUD_PUBLICA"] == 1 and out.loc[0, "DHSERSAL_IMSS_BIENESTAR"] == 0
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["separado", "No especificado"]   # 3 = divorciada
    assert list(out["RELIGION_CAT"]) == ["Católica", "No especificado"]
    assert list(out["IDENT_HIJO_CAT"]) == ["Blanco por pase", "En otra vivienda"]


def test_derive_dwellings_and_older_editions():
    viv = pd.DataFrame({"CLAVIVP": ["1", "7"], "CUADORM": ["1", "03"], "TOTCUART": ["2", "99"],
                        "DRENAJE": ["5", ""], "INGTRHOG": ["0", "999999"],
                        "FINANCIAMIENTO": ["1", ""]}, dtype="str")
    out = _derive_dwellings(viv, "2015")
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]
    assert list(out["CUADORM_CAT"]) == ["1", "2+"]
    assert list(out["TOTCUART_CAT"]) == ["2", "No especificado"]
    assert list(out["DRENAJE_CAT"]) == ["No", "Blanco por pase"]
    assert list(out["INGTRHOG_CAT"]) == ["No recibe ingresos", "No especificado"]
    # 2015's one financing item: its own dummies (1 merges INFONAVIT, FOVISSSTE and PEMEX)
    assert list(out["FINANCIAMIENTO_INFONAVIT, FOVISSSTE o PEMEX"]) == [1, 0]
    assert list(out["FINANCIAMIENTO_Blanco por pase"]) == [0, 1]
    assert "FINANCIAMIENTO_INFONAVIT" not in out
    for col, dtype in d.derived_dtypes("viviendas", "2015").items():
        assert out[col].dtype == dtype, col
    # 6n: 2010's classes are 2000's (5 local, 6 móvil, 7 refugio = «Otro», 9 not specified)
    v10 = viv.drop(columns=["FINANCIAMIENTO"]).assign(SEXO=["1", "3"])   # 6s: the head's
    out10 = _derive_dwellings(v10.assign(CLAVIVP=["4", "5"]), "2010")
    assert list(out10["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]
    assert list(_derive_dwellings(v10.assign(CLAVIVP=["9", "7"]), "2010")["CLAVIVP_CAT"]) \
        == ["Vivienda", "Otro"]


def _persons_2015() -> pd.DataFrame:
    """Two EIC 2015 persons (raw codes, 2015's un-padded spelling; "" = blank)."""
    return pd.DataFrame({
        "EDAD": ["34", "70"], "INGTRMEN": ["8000", ""], "NIVACAD": ["11", "6"],
        "ESCOLARI": ["4", "2"], "DHSERSAL1": ["1", "2"], "DHSERSAL2": ["", "6"],
        "CONACT": ["13", "20"], "SITUA_CONYUGAL": ["5", "6"],
        "MED_TRASLADO_ESC1": ["", ""], "MED_TRASLADO_ESC2": ["", ""],
        "MED_TRASLADO_ESC3": ["", ""], "MED_TRASLADO_TRAB1": ["1", "6"],
        "MED_TRASLADO_TRAB2": ["3", ""], "MED_TRASLADO_TRAB3": ["", ""], "ENT": ["01", "01"],
        "ENT_PAIS_NAC": ["014", "221"], "ENT_PAIS_RES10": ["001", "997"],
        # 7b: their municipality, the 2010 residence's and the places of school and work
        "MUN": ["001", "001"], "MUN_RES10": ["005", ""], "ENT_PAIS_ASI": ["", ""],
        "MUN_ASI": ["", ""], "ENT_PAIS_TRAB": ["001", ""], "MUN_TRAB": ["001", ""],
        "IDENT_MADRE": ["3", "98"], "IDENT_PADRE": ["97", "99"],
        "IDENT_PAREJA": ["98", ""], "OCUPACION_C": ["599", ""],
        "ACTIVIDADES_C": ["9399", ""],
        # 6t: one dwelling (2015's un-padded key), a male head (1) and his wife; 6w: she
        # speaks an indigenous language
        "ID_VIV": ["01001000001"] * 2, "PARENT": ["1", "2"], "SEXO": ["1", "3"],
        "HLENGUA": ["3", "1"], "TIPOHOG": ["1", "1"],                  # 6z: nuclear
        "PARENT_OTRO_C": ["101", "201"]}, dtype="str")                 # 8f: the detail


def test_derive_persons_2015_recodes():
    out = d.derive(_persons_2015(), "personas", 2015)
    first, second = out.iloc[0], out.iloc[1]
    assert list(out["EDUC"]) == ["Posbásica", "Primaria_com"]        # técnicos con primaria
    assert list(out["CONACT_CAT"]) == ["Trabaja", "Buscó trabajo"]   # 13 found working; 20
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["casado", "soltero"]   # 5 casada, 6 soltera
    # 2015's 1 is Seguro Popular, its 2 the IMSS; no IMSS-BIENESTAR column
    assert (first["DHSERSAL_SALUD_PUBLICA"], first["DHSERSAL_IMSS"]) == (1, 0)
    assert (second["DHSERSAL_IMSS"], second["DHSERSAL_Privado"]) == (1, 1)
    assert first["DHSERSAL_PUB"] == first["DHSERSAL_AFIL"] == 1 and second["DHSERSAL_PUB"] == 1
    assert "DHSERSAL_IMSS_BIENESTAR" not in out
    # 2015's own commute dummies: merged modes under 2015's wording, the others as in 2020
    assert first["MED_TRASLADO_TRAB_Camión, taxi, combi o colectivo"] == 1
    vehicle = "MED_TRASLADO_TRAB_Vehículo particular (automóvil, camioneta o motocicleta)"
    assert first[vehicle] == 1
    assert first["MED_TRASLADO_TRAB_Blanco por pase"] == 1                # blank 3rd item
    assert (second["MED_TRASLADO_TRAB_Caminando"], first["MED_TRASLADO_TRAB_Caminando"]) == (1, 0)
    assert first["MED_TRASLADO_ESC_Blanco por pase"] == 1
    assert "MED_TRASLADO_TRAB_Trolebús" not in out
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["OtraEnt", "OtroPais"]
    assert list(out["ENT_PAIS_RES_CAT"]) == ["EstaEnt", "OtraEnt"]   # ENT_PAIS_RES10; 997
    assert list(out["LUGAR_RES_5A"]) == ["Otro municipio", "No especificado"]     # 7b
    assert list(out["LUGAR_TRAB"]) == ["Mismo municipio", "Blanco por pase"]
    assert list(out["IDENT_MADRE_CAT"]) == ["Vive en esta vivienda", "No sabe"]   # un-padded
    assert list(out["IDENT_PADRE_CAT"]) == ["Ya falleció", "No especificado"]
    assert list(out["IDENT_PAREJA_CAT"]) == ["No", "Blanco por pase"]  # 98: no sabe dónde
    assert list(out["MADRE_EN_VIVIENDA"]) == ["Sí", "No"]
    assert list(out["PADRE_EN_VIVIENDA"]) == ["No", "No especificado"]
    # SINCO 2011's 599 (group 59, gone in SINCO 2019) → 52; the SCIAN sector of 9399
    assert list(out["OCUPACION_C_COARSE"]) == [
        "Trabajadores en cuidados personales y del hogar", "Blanco por pase"]
    assert out.loc[0, "ACTIVIDADES_C_COARSE"].startswith("Actividades legislativas")
    for col, dtype in d.derived_dtypes("personas", "2015").items():
        assert out[col].dtype == dtype, col


def _persons_2010() -> pd.DataFrame:
    """Three Censo 2010 persons (raw codes; "" = blank): a child, an adult with two
    limitations born abroad, an unspecified elder."""
    df = pd.DataFrame({
        "EDAD": ["004", "040", "081"], "INGTRMEN": ["", "5000", ""], "HORTRA": ["", "168", ""],
        "NIVACAD": ["01", "05", "99"], "ESCOLARI": ["02", "03", "99"],
        "DHSERSAL1": ["8", "5", "9"], "DHSERSAL2": ["", "6", ""], "CONACT": ["", "10", "80"],
        "ESTCON": ["", "1", "4"], "DISCAP8": ["17", "", "99"], "ENT": ["09", "09", "09"],
        "LNACEDO_C": ["009", "", "999"], "LNACPAIS_C": ["", "221", ""],
        "RES05EDO_C": ["", "", "900"], "RES05PAI_C": ["", "600", ""],
        # 7b: their municipality, the 2005 residence's and the place of work (the adult's
        # entity not specified)
        "MUN": ["002", "002", "002"], "MUN05OTR_C": ["", "", ""],
        "LTRABPAI_C": ["", "999", ""], "LTRABMUN_C": ["", "", ""],
        "IDMADRE": ["02", "", "99"], "IDMADREC": ["", "88", "99"],
        "IDPADRE": ["99", "", ""], "IDPADREC": ["", "88", "88"],
        "IDCONYUGE": ["", "57", ""], "IDCONYUGEC": ["", "", ""],
        "OCUACTIV_C": ["", "5999", "9888"], "ACTTRAB_C": ["", "3110", "9999"],
        "OTRAREL_C": ["110300", "220100", "310100"],
        # 6t: a female-headed dwelling (the child, her head) and a man alone; 6w: she
        # speaks an indigenous language, his answer is not specified
        "ID_VIV": ["00000001", "00000001", "00000002"], "PARENT": ["03", "01", "01"],
        "SEXO": ["1", "3", "1"], "HLENGUA": ["3", "1", "9"],
        "TIPOHOG": ["1", "1", "5"],                     # 6z: nuclear; the man is alone
        "OTROPARE_C": ["", "", ""]}, dtype="str")       # 8f: «otro parentesco»'s detail
    for i in range(1, 8):
        df[f"DISCAP{i}"] = ""
    df.loc[1, ["DISCAP2", "DISCAP7"]] = ["11", "16"]
    return df


def test_derive_persons_2010_recodes():
    out = d.derive(_persons_2010(), "personas", 2010)
    # 05 = normal básica (2020: 09)
    assert list(out["EDUC"]) == ["Sin Educación", "Posbásica", "No especificado"]
    assert list(out["HORTRA_CAT"]) == ["Blanco por pase", "81YMAS", "Blanco por pase"]
    assert list(out["CONACT_CAT"]) == ["Blanco por pase", "Trabaja", "No trabaja"]
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["Blanco por pase", "casado", "separado"]  # ESTCON
    assert list(out["LIM_ACTIVIDAD"]) == ["No", "Sí", "No especificado"]
    assert list(out["DHSERSAL_No afiliado"]) == [1, 0, 0]                 # 8: no entitlement
    assert list(out["DHSERSAL_SALUD_PUBLICA"]) == list(out["DHSERSAL_Privado"]) == [0, 1, 0]
    assert list(out["DHSERSAL_AFIL"]) == [0, 1, 0]                        # 9: not specified
    assert "DIS_CON" not in out and "DHSERSAL_IMSS_BIENESTAR" not in out
    # birthplace and 2005 residence: the entity item, else the country item; entity 999 →
    # 997 (OtraEnt), 900 (topic omitted) → No especificado, country 600 → OtroPais
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["EstaEnt", "OtroPais", "OtraEnt"]
    assert list(out["ENT_PAIS_NAC_INEGI"]) == ["EstaEnt", "OtroPais", "No especificado"]  # 6y
    assert list(out["ENT_PAIS_RES_CAT"]) == ["Blanco por pase", "OtroPais", "No especificado"]
    assert list(out["LUGAR_RES_5A"]) == ["Blanco por pase", "Otro país", "No especificado"]
    assert list(out["LUGAR_TRAB"]) == list(out["ENT_PAIS_TRAB_INEGI"]) == [         # 7b
        "Blanco por pase", "No especificado", "Blanco por pase"]
    # pointer pairs: a row (above 54 too) → Sí, 88 → No, 99 code → NE; a row given as 99
    # (row not given) → NE, as INEGI's tabulado 12_01A (6q; 6e read it «lives here»)
    assert list(out["MADRE_EN_VIVIENDA"]) == ["Sí", "No", "No especificado"]
    assert list(out["PADRE_EN_VIVIENDA"]) == ["No especificado", "No", "No"]
    assert list(out["IDENT_PAREJA_CAT"]) == ["Blanco por pase", "Sí", "Blanco por pase"]
    pareja = d.derive(_persons_2010().assign(IDCONYUGE=["", "99", "99"],
                                             IDCONYUGEC=["88", "", "99"]), "personas", 2010)
    assert list(pareja["IDENT_PAREJA_CAT"]) == ["No", "No especificado", "No especificado"]
    assert "IDENT_MADRE_CAT" not in out                    # 88 merges 2020's 96/97/98
    # 4-digit SINCO: the first two digits (5999: group 59 → 52); SCIAN sector (ACTTRAB_C)
    assert list(out["OCUPACION_C_COARSE"]) == [
        "Blanco por pase", "Trabajadores en cuidados personales y del hogar",
        "Otros trabajadores en actividades elementales y de apoyo, no clasificados anteriormente"]
    assert list(out["ACTIVIDADES_C_COARSE"]) == ["Blanco por pase", "Industrias manufactureras",
                                                 "No especificado"]
    # religion by 2010 group; the neo-Israelite movements (220100) as in 2020 (evangelical)
    assert list(out["RELIGION_CAT"]) == ["Católica", "Protestante/cristiano evangélico",
                                         "Sin religión / Sin adscripción religiosa"]
    # 7g: by Censo 2010's own classification (its ITER's), a judaic credo
    assert list(out["RELIGION_INEGI"]) == ["Católica", "Otros credos",
                                           "Sin religión / Sin adscripción religiosa"]
    for col, dtype in d.derived_dtypes("personas", "2010").items():
        assert out[col].dtype == dtype, col


def _persons_2000() -> pd.DataFrame:
    """Four CGPV 2000 persons (raw codes; "" = blank): an adult with técnica after primaria,
    one never schooled (no level, NIVELACAD 00), a child under 5, one with unknown coverage."""
    return pd.DataFrame({
        "EDAD": ["040", "020", "003", "070"], "INGRESOS": ["004500", "", "", "999999"],
        "HORTRA": ["048", "", "", "999"], "NIVACAD": ["6", "", "", "8"],
        "ANTESC": ["1", "", "", ""], "ESCOLARI": ["2", "", "", "9"],
        "NIVELACAD": ["61", "00", "", "80"], "CONACT": ["14", "40", "", "60"],
        "ESTCON": ["1", "8", "", "4"], "IMSS": ["1", "", "", "9"], "ISSSTE": ["", "", "2", ""],
        "PEMEX": ["", "", "", ""], "OTRINS_V": ["4", "", "", ""],
        "NOTIEDER": ["", "5", "", ""], "ENT": ["01", "01", "01", "01"],
        "LNACEDO_C": ["001", "014", "221", "600"], "RES95EDO_C": ["001", "999", "", "600"],
        "ACTTRAB_C": ["311", "", "", "999"], "OTRAREL_C": ["0001", "2002", "", "9100"],
        # 8e: the CMO occupation (domestic worker; not specified)
        "OCUACTIV_C": ["8200", "", "", "9999"],
        # 6t: one dwelling, two households: a woman heads the first, a man the second
        "MUN": ["001"] * 4, "LOC": ["0001"] * 4, "NUMVIV": ["000001"] * 4,
        "NUMHOG": ["1", "1", "2", "2"], "OTROPARE_C": ["100", "300", "300", "100"],
        "SEXO": ["2", "1", "1", "1"],
        # 6w: the first head speaks an indigenous language (2 = no; the child under 5 not asked)
        "HLENGUA": ["1", "2", "", "2"],
        # 6z: the households' types (from the dwelling file): nuclear, composition unknown
        "TIPOHOG": ["1", "1", "9", "9"],
        # 7c: the 1995 municipality (the adult lived in this one) and the place of work (the
        # employed adult works in another municipality of the entity)
        "MUN95OTR_C": ["001", "", "", ""], "LTRABPAI_C": ["001", "", "", ""],
        "LTRABMUN_C": ["002", "", "", ""],
    }, dtype="str")


def test_derive_persons_2000_recodes():
    out = d.derive(_persons_2000(), "personas", 2000)
    # técnica after primaria = 2020's 6 («Primaria_com»); never schooled; under 5; maestría
    assert list(out["EDUC"]) == ["Primaria_com", "Sin Educación", "Blanco por pase", "Posbásica"]
    assert list(out["EDUC_INEGI"]) == ["Técnica_primaria", *list(out["EDUC"])[1:]]
    assert list(out["CONACT_CAT"]) == ["Trabaja", "No trabaja", "Blanco por pase", "No trabaja"]
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["casado", "soltero", "Blanco por pase", "separado"]
    assert list(out["INGTRMEN_CAT"]) == ["1,000-4,999", "Blanco por pase", "Blanco por pase",
                                         "No especificado"]
    assert list(out["HORTRA_CAT"])[::3] == ["41-48", "No especificado"]
    # 8e: the CMO's domestic workers (8200: SINCO 51 or 96, the ENOE panel's 96), not
    # specified; 8190 (SINCO 2011's 5999, group 59 → 52); 6290 (not in INEGI's table, no
    # group placed: 99); a code the bridge lacks raises
    assert list(out["OCUPACION_C_COARSE"]) == [
        "Trabajadores domésticos, de limpieza, planchadores y otros trabajadores de limpieza",
        "Blanco por pase", "Blanco por pase", "No especificado"]
    other = d.derive(_persons_2000().assign(OCUACTIV_C=["8190", "6290", "", "4100"]),
                     "personas", 2000)
    assert list(other["OCUPACION_C_COARSE"]) == [
        "Trabajadores en cuidados personales y del hogar", "No especificado",
        "Blanco por pase", "Trabajadores en actividades agrícolas y ganaderas"]
    with pytest.raises(ValueError, match="OCUPACION_C_COARSE"):
        d.derive(_persons_2000().assign(OCUACTIV_C=["1234", "", "", ""]), "personas", 2000)
    # 6r: who had a job but did not work (CONACT 20) reported hours; they count at 0
    had = d.derive(_persons_2000().assign(CONACT=["20", "40", "", "60"]), "personas", 2000)
    assert list(had["HORTRA_CAT"])[::3] == ["0-5", "No especificado"]
    # one item per institution: IMSS + other, none, ISSSTE, coverage not known (IMSS 9)
    assert list(out["DHSERSAL_IMSS"]) == [1, 0, 0, 0] and list(out["DHSERSAL_Otro"]) == [1, 0, 0, 0]
    assert list(out["DHSERSAL_No afiliado"]) == [0, 1, 0, 0]
    assert list(out["DHSERSAL_AFIL"]) == [1, 0, 1, 0] and list(out["DHSERSAL_PUB"]) == [1, 0, 1, 0]
    assert "DHSERSAL_SALUD_PUBLICA" not in out and "DHSERSAL_Privado" not in out
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["EstaEnt", "OtraEnt", "OtroPais", "OtroPais"]
    assert list(out["ENT_PAIS_RES_CAT"]) == ["EstaEnt", "No especificado", "Blanco por pase",
                                             "OtroPais"]
    assert list(out["ACTIVIDADES_C_COARSE"])[0] == "Industrias manufactureras"   # subsector 311
    # 7c: the 1995 residence and the place of work by municipality; $4,500 in Aguascalientes
    # (area C: $981 a month) is 4.6 minimum wages
    assert list(out["LUGAR_RES_5A"]) == ["Mismo municipio", "No especificado", "Blanco por pase",
                                         "Otro país"]
    assert list(out["LUGAR_TRAB"]) == ["Otro municipio", *["Blanco por pase"] * 3]
    assert list(out["ENT_PAIS_TRAB_INEGI"]) == ["EstaEnt", *["Blanco por pase"] * 3]
    assert list(out["INGTRMEN_SM"]) == ["De 3 hasta 5 s.m.", "Blanco por pase", "Blanco por pase",
                                        "No especificado"]
    # religion: 0001 católica, 2xxx bíblicas (2020: evangelical), under 5, 9100 ninguna
    assert list(out["RELIGION_CAT"]) == ["Católica", "Protestante/cristiano evangélico",
                                         "Blanco por pase",
                                         "Sin religión / Sin adscripción religiosa"]
    for col, dtype in d.derived_dtypes("personas", "2000").items():
        assert out[col].dtype == dtype, col
    assert "Blanco por pase" not in d.derived_dtypes("personas", "2020")["RELIGION_CAT"].categories
    with pytest.raises(ValueError, match="RELIGION_CAT"):                 # no such group
        d.derive(_persons_2000().assign(OTRAREL_C=["0001", "0500", "", "9100"]), "personas", 2000)
    with pytest.raises(ValueError, match="DHSERSAL_"):                    # an unknown code
        d.derive(_persons_2000().assign(ISSSTE=["", "", "7", ""]), "personas", 2000)


def _persons_2005() -> pd.DataFrame:
    """Three Conteo 2005 persons (raw codes; "" = blank)."""
    return pd.DataFrame({
        "EDAD": ["035", "002", "060"], "NIVANTES": ["62", "", "99"], "GRA_APRO": ["2", "", "3"],
        "IMSS": ["", "", ""], "ISSSTE": ["", "", ""], "PEMEX": ["", "", ""],
        "SEGU_POP": ["1", "", ""], "INST_PRI": ["", "", ""], "OTRA_INS": ["1", "", "3"],
        "SIN_DERE": ["", "9", ""], "ENT": ["09", "09", "09"],
        "LURE2000": ["201", "", "033"],
        # 6t: one dwelling, a household headed by a woman, a man alone (102) in the second
        "MUN": ["002"] * 3, "CONS_MUN": ["000001"] * 3, "CONS_HOG": ["01", "01", "02"],
        "PARENT": ["101", "301", "102"], "SEXO": ["2", "1", "1"],
        "HABLENIN": ["1", "", "2"]}, dtype="str")         # 6w: the first head speaks


def test_derive_persons_2005_recodes():
    df = _persons_2005()
    out = d.derive(df, "personas", 2005)
    # técnica after secundaria (62 → 7); under 5; a grade without a level
    assert list(out["EDUC"]) == ["Posbásica", "Blanco por pase", "No especificado"]
    assert out["EDUC_INEGI"].astype(object).equals(out["EDUC"].astype(object))
    tec = d.derive(df.assign(NIVANTES=["61", "", "99"]), "personas", 2005)     # after primaria
    assert tec["EDUC"].iloc[0] == "Primaria_com" and tec["EDUC_INEGI"].iloc[0] == "Técnica_primaria"
    # Seguro Popular + state institution (OTRA_INS 1 → ISSSTE estatal); NE; subrogated private
    assert list(out["DHSERSAL_SALUD_PUBLICA"]) == [1, 0, 0]
    assert list(out["DHSERSAL_ISSSTE_E"]) == [1, 0, 0] and list(out["DHSERSAL_Privado"]) == [0, 0, 1]
    assert list(out["DHSERSAL_AFIL"]) == [1, 0, 1] and list(out["DHSERSAL_PUB"]) == [1, 0, 0]
    assert list(out["DHSERSAL_No afiliado"]) == [0, 0, 0]
    # residence in 2000: the United States (201 → 221), not asked (under 5), entity 033 → 997
    assert list(out["ENT_PAIS_RES_CAT"]) == ["OtroPais", "Blanco por pase", "OtraEnt"]
    for col, dtype in d.derived_dtypes("personas", "2005").items():
        assert out[col].dtype == dtype, col


def test_derive_dwellings_2000_2005():
    v00 = pd.DataFrame({"CLAVIV": ["01", "05"], "CUADORM": ["01", "99"], "TOTCUART": ["26", "01"],
                        "DRENAJE": ["5", "9"], "INGTRHOG": ["000000", "999999"],
                        "SEXO": ["1", "2"]}, dtype="str")                # 6s: the head's
    out = _derive_dwellings(v00, "2000")
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]          # 05 local no construido
    assert list(out["TOTCUART_CAT"]) == ["3+", "1"] and list(out["CUADORM_CAT"]) == ["1", "No especificado"]
    assert list(out["DRENAJE_CAT"]) == ["No", "No especificado"]
    v05 = pd.DataFrame({"CLAVIVPA": ["2", "7"], "CUARDOM": ["02", "01"], "NUMCUAR": ["03", "02"],
                        "DIS_DREN": ["1", "5"], "SEXO": ["2", "1"]}, dtype="str")
    out = d.derive(v05, "viviendas", 2005)
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]          # 7 refugio
    assert list(out["TOTCUART_CAT"]) == ["3+", "2"] and list(out["DRENAJE_CAT"]) == ["Sí", "No"]


def test_derive_jefe_sexo():
    """6s: the household head's sex (2020's dwelling item ``JEFE_SEXO``, its labels) from the
    head's ``SEXO``, which the dwelling loader attaches from the person file: 2000/2005 write
    a woman 2, 2010 3; a code outside them raises, and so does a frame without it."""
    v00 = pd.DataFrame({"CLAVIV": ["01", "01"], "CUADORM": ["01", "01"], "TOTCUART": ["02", "02"],
                        "DRENAJE": ["1", "1"], "INGTRHOG": ["000100", "000100"],
                        "SEXO": ["1", "2"]}, dtype="str")
    v05 = pd.DataFrame({"CLAVIVPA": ["1", "1"], "CUARDOM": ["01", "01"], "NUMCUAR": ["02", "02"],
                        "DIS_DREN": ["1", "1"], "SEXO": ["2", "1"]}, dtype="str")
    v10 = pd.DataFrame({"CLAVIVP": ["1", "1"], "CUADORM": ["1", "1"], "TOTCUART": ["2", "2"],
                        "DRENAJE": ["1", "1"], "INGTRHOG": ["0", "0"], "SEXO": ["3", "1"]},
                       dtype="str")
    for period, frame, sexes in (("2000", v00, ["Hombre", "Mujer"]),
                                 ("2005", v05, ["Mujer", "Hombre"]),
                                 ("2010", v10, ["Mujer", "Hombre"])):
        out = _derive_dwellings(frame, period)
        assert list(out["JEFE_SEXO"]) == sexes
        assert out["JEFE_SEXO"].dtype == d.derived_dtypes("viviendas", period)["JEFE_SEXO"]
    assert list(d.derived_dtypes("viviendas", "2010")["JEFE_SEXO"].categories) == ["Hombre", "Mujer"]
    with pytest.raises(ValueError, match="JEFE_SEXO"):
        _derive_dwellings(v10.assign(SEXO=["2", "1"]), "2010")      # 2010 has no code 2
    with pytest.raises(ValueError, match="needs 'SEXO'"):
        _derive_dwellings(v10.drop(columns="SEXO"), "2010")


def test_attach_heads(monkeypatch, tmp_path):
    """6s: ``cpv._attach_heads`` brings each household's head (its relationship code) from the
    person file onto the dwelling rows: CGPV 2000 per household, the Conteo 2005 the head of
    the dwelling's first household (102 «persona sola» is a head), Censo 2010 the dwelling
    (``harmonize=True``: its national ``ID_VIV``). A household without exactly one head, or a
    record without a head, raises."""
    from mxcensus import cpv
    from mxcensus.data import _registry

    files = {}
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda fname, **_: str(files[fname]))

    def persons(period, frame):
        name = cpv.cpv_filename("personas", period, 1)
        files[name] = tmp_path / name
        frame.astype("string").to_parquet(files[name])

    persons("2000", pd.DataFrame({
        "ENT": ["01"] * 3, "MUN": ["001"] * 3, "LOC": ["0001"] * 3, "NUMVIV": ["000001"] * 3,
        "NUMHOG": ["1", "1", "2"], "OTROPARE_C": ["100", "300", "100"], "SEXO": ["2", "1", "1"]}))
    v00 = pd.DataFrame({"ID_VIV": ["010010001000001"] * 2,
                        "ID_HOG": ["01001000100000101", "01001000100000102"]})
    assert list(cpv._attach_heads(v00, "2000", 1, False)["SEXO"]) == ["2", "1"]
    persons("2005", pd.DataFrame({
        "ENT": ["01"] * 4, "MUN": ["001"] * 4, "CONS_MUN": ["000001"] * 3 + ["000002"],
        "CONS_HOG": ["01", "01", "02", "01"], "PARENT": ["201", "101", "102", "101"],
        "SEXO": ["1", "2", "1", "1"]}))
    v05 = pd.DataFrame({"ID_VIV": ["010010000002", "010010000001"]})
    assert list(cpv._attach_heads(v05, "2005", 1, False)["SEXO"]) == ["1", "2"]
    persons("2010", pd.DataFrame({
        "ENT": ["01"] * 3, "ID_VIV": ["00000001", "00000001", "00000002"],
        "PARENT": ["03", "01", "01"], "SEXO": ["1", "3", "1"]}))
    assert list(cpv._attach_heads(pd.DataFrame({"ID_VIV": ["00000002", "00000001"]}),
                                  "2010", 1, False)["SEXO"]) == ["1", "3"]
    national = pd.DataFrame({"ID_VIV": ["010000000001", "010000000002"]})
    assert list(cpv._attach_heads(national, "2010", 1, True)["SEXO"]) == ["3", "1"]
    with pytest.raises(ValueError, match="without a household head"):
        cpv._attach_heads(pd.DataFrame({"ID_VIV": ["00000003"]}), "2010", 1, False)
    persons("2010", pd.DataFrame({"ENT": ["01"] * 2, "ID_VIV": ["00000001"] * 2,
                                  "PARENT": ["01", "01"], "SEXO": ["1", "3"]}))
    with pytest.raises(ValueError, match="without exactly one head"):
        cpv._attach_heads(pd.DataFrame({"ID_VIV": ["00000001"]}), "2010", 1, False)


def test_load_hogares_derived(monkeypatch, tmp_path):
    """6v: ``load_cpv_hogares(2005, derived=True)`` gives each household its dwelling's class
    (``cpv._attach_dwellings``, the dwelling file's ``CLAVIVPA``) and its own head's sex (a
    dwelling's second household its own head: 102 «persona sola»), labelled as the dwelling
    columns; the helper columns are dropped, and a household without its dwelling raises."""
    from mxcensus import cpv
    from mxcensus.data import _registry

    files = {}
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda fname, **_: str(files[fname]))

    def write(table, frame):
        name = cpv.cpv_filename(table, "2005", 1)
        files[name] = tmp_path / name
        frame.astype("string").to_parquet(files[name])

    columns = cpv_schema_map()["hogares"]["groups"][_gid("hogares", "2005")]["columns"]
    write("hogares", pd.DataFrame({
        "ENT": ["01"] * 3, "MUN": ["001"] * 3, "CONS_MUN": ["000001", "000001", "000002"],
        "CONS_VIV": ["001", "001", "002"], "CONS_HOG": ["01", "02", "01"],
        "TOTPEHOG": ["2", "1", "1"], "TICLAHOG": ["11", "21", "21"]})[columns])
    write("personas", pd.DataFrame({
        "ENT": ["01"] * 4, "MUN": ["001"] * 4, "CONS_MUN": ["000001"] * 3 + ["000002"],
        "CONS_HOG": ["01", "01", "02", "01"], "PARENT": ["201", "101", "102", "101"],
        "SEXO": ["1", "2", "1", "1"],
        "HABLENIN": ["1", "2", "2", "9"]}))           # 6x: the first household's partner
    dwellings = pd.DataFrame({"ENT": ["01", "01"], "MUN": ["001", "001"],
                              "CONS_MUN": ["000001", "000002"], "CLAVIVPA": ["1", "7"]})
    write("viviendas", dwellings)
    h = mxcensus.load_cpv_hogares(2005, state=1, derived=True)
    assert list(h.index.names) == ["ID_VIV", "ID_HOG"]
    h = h.sort_index()
    assert list(h["JEFE_SEXO"]) == ["Mujer", "Hombre", "Hombre"]
    assert list(h["CLAVIVP_CAT"]) == ["Vivienda", "Vivienda", "Otro"]          # 7 refugio
    assert list(h["HOG_IND"]) == ["Sí", "No", "No"]       # 6x: over its own members only
    assert "SEXO" not in h and "CLAVIVPA" not in h and "HABLENIN" not in h
    for col, dtype in d.derived_dtypes("hogares", "2005").items():
        assert h[col].dtype == dtype
    assert str(h["TICLAHOG"].iloc[0]) == "Familiar nuclear"                      # labelled
    hh = mxcensus.load_cpv_hogares(2005, state=1, derived=True, harmonize=True, labels=False)
    assert hh.index.equals(mxcensus.load_cpv_hogares(2005, state=1).index)
    assert list(hh.sort_index()["JEFE_SEXO"]) == list(h["JEFE_SEXO"])
    assert list(hh.sort_index()["HOG_IND"]) == list(h["HOG_IND"])                 # 6x
    tables = mxcensus.get_tables_dict(mxcensus.cpv_constraints("hogares", 2005), h.dtypes)
    assert set(tables) == {frozenset({"CLAVIVP_CAT"}), frozenset({"CLAVIVP_CAT", "JEFE_SEXO"})}
    write("viviendas", dwellings.iloc[:1])
    with pytest.raises(ValueError, match="without their dwelling"):
        mxcensus.load_cpv_hogares(2005, state=1, derived=True)


def test_derive_hogjef_sexo():
    """6t: each person's household head's sex (``JEFE_SEXO``'s labels and dtype), from the
    person of the same household whose relationship code is the head's (``_HEAD_CODES``):
    1995–2005 per household — a person of a dwelling's second household gets that
    household's head (2005: 102 «persona sola» is one) —, 2010–2025 per dwelling (Censo
    2010's serials per state). A household without exactly one head raises, and so do an
    unknown sex code and a frame without a household key."""
    p20 = _persons_2025().rename(columns={"CVE_ENT": "ENT"}).assign(
        SITUA_CONYUGAL=["3", "9"], RELIGION=["1101", "9999"], IDENT_HIJO=["", "96"],
        ENT_PAIS_NAC=["356", "001"])
    cases = (("2025", _persons_2025(), ["Mujer", "Mujer"]),
             ("2020", p20, ["Mujer", "Mujer"]),
             ("2015", _persons_2015(), ["Hombre", "Hombre"]),
             ("2010", _persons_2010(), ["Mujer", "Mujer", "Hombre"]),
             ("2005", _persons_2005(), ["Mujer", "Mujer", "Hombre"]),
             ("2000", _persons_2000(), ["Mujer", "Mujer", "Hombre", "Hombre"]),
             ("1995", _persons_1995(), ["Mujer"] * 3 + ["Hombre"] * 2))
    jefe = d.derived_dtypes("viviendas", "2010")["JEFE_SEXO"]
    for period, frame, sexes in cases:
        out = d.derive(frame, "personas", period)
        assert list(out["HOGJEF_SEXO"]) == sexes, period
        assert out["HOGJEF_SEXO"].dtype == jefe == d.derived_dtypes("personas", period)["HOGJEF_SEXO"]
    assert "HOGJEF_SEXO" not in d.derived_dtypes("personas", "1990")       # no household
    # Censo 2010's raw keys repeat across states: the entity tells the households apart
    two = pd.concat([_persons_2010(), _persons_2010().assign(ENT="10", SEXO=["3", "1", "3"])],
                    ignore_index=True)
    assert list(d.derive(two, "personas", 2010)["HOGJEF_SEXO"]) == [
        "Mujer", "Mujer", "Hombre", "Hombre", "Hombre", "Mujer"]
    for parent in (["01", "01", "01"], ["03", "02", "01"]):              # two heads; none
        with pytest.raises(ValueError, match="1 households without exactly one head"):
            d.derive(_persons_2010().assign(PARENT=parent), "personas", 2010)
    with pytest.raises(ValueError, match="HOGJEF_SEXO"):                  # 2010 has no code 2
        d.derive(_persons_2010().assign(SEXO=["1", "2", "1"]), "personas", 2010)
    with pytest.raises(ValueError, match="household key"):
        d.derive(_persons_2025().drop(columns="ID_VIV"), "personas", 2025)


def test_derive_hog_ind():
    """6w: whether each person's household is indigenous, by the edition's own definition
    (``_IND_CODES``): one of the head, the partner (up to 2015), the parents and parents-in-law
    (2020) and the step-parents and grandparents (2025) speaks an indigenous language. A child
    who speaks does not count; an unknown language code raises."""
    p20 = _persons_2025().rename(columns={"CVE_ENT": "ENT"}).assign(
        SITUA_CONYUGAL=["3", "9"], RELIGION=["1101", "9999"], IDENT_HIJO=["", "96"],
        ENT_PAIS_NAC=["356", "001"])
    grandparent = {"PARENTESCO": ["101", "406"]}                 # the grandparent speaks
    in_law = {"PARENTESCO": ["101", "416"]}                      # the parent-in-law speaks
    cases = (("2025", _persons_2025(), ["No", "No"]),           # only the son speaks
             ("2025", _persons_2025().assign(**grandparent), ["Sí", "Sí"]),
             ("2020", p20.assign(**grandparent), ["No", "No"]),
             ("2020", p20.assign(**in_law), ["Sí", "Sí"]),
             ("2015", _persons_2015(), ["Sí", "Sí"]),             # the wife speaks
             ("2015", _persons_2015().assign(PARENT=["1", "6"]), ["No", "No"]),   # the mother
             ("2010", _persons_2010(), ["Sí", "Sí", "No"]),       # the head; NE
             ("2010", _persons_2010().assign(HLENGUA=["1", "3", "9"]), ["No"] * 3),
             ("2005", _persons_2005(), ["Sí", "Sí", "No"]),       # the first household's head
             ("2005", _persons_2005().assign(PARENT=["101", "204", "102"],      # a partner
                                             HABLENIN=["2", "1", "2"]), ["Sí", "Sí", "No"]),
             ("2005", _persons_2005().assign(PARENT=["101", "601", "102"],      # a parent
                                             HABLENIN=["2", "1", "2"]), ["No"] * 3),
             ("2000", _persons_2000(), ["Sí", "Sí", "No", "No"]))
    for period, frame, expected in cases:
        out = d.derive(frame, "personas", period)
        assert list(out["HOG_IND"]) == expected, period
        assert out["HOG_IND"].dtype == d._SI_NO == d.derived_dtypes("personas", period)["HOG_IND"]
    for period in ("1990", "1995"):                   # no household / no language item
        assert "HOG_IND" not in d.derived_dtypes("personas", period)
    with pytest.raises(ValueError, match="HOG_IND"):
        d.derive(_persons_2010().assign(HLENGUA=["1", "7", "9"]), "personas", 2010)


def test_derive_hog_ind_households():
    """6x: the household's ``HOG_IND`` on its record — the dwelling (CGPV 2000: one row per
    household; 2010–2025: one household per dwelling) or the Conteo 2005's household —
    computed over its members (``derive(members=)``, the person rows: 6w's rule and codes),
    matched on the entity and the household key whatever their zero padding. A record
    without members raises, and so do a frame without them and an unknown language code."""
    def dwellings(n: int, **cols) -> pd.DataFrame:
        return pd.DataFrame({"CLAVIVP": ["1"] * n, "CUADORM": ["1"] * n, "TOTCUART": ["2"] * n,
                             "DRENAJE": ["1"] * n, "INGTRHOG": ["0"] * n,
                             **{c: [v] * n for c, v in _HOUSEHOLD_ITEMS.items()},     # 6z
                             **cols}, dtype="str")

    fin = {f"FINANCIAMIENTO{i}": [""] for i in (1, 2, 3)}
    v25 = dwellings(1, **fin, CVE_ENT=["01"], ID_VIV=["010010000001"])
    grandparent = _persons_2025().assign(PARENTESCO=["101", "406"])    # the grandparent speaks
    out = d.derive(v25, "viviendas", 2025, members=grandparent)
    assert list(out["HOG_IND"]) == ["Sí"]
    assert out["HOG_IND"].dtype == d._SI_NO == d.derived_dtypes("viviendas", "2025")["HOG_IND"]
    assert list(d.derive(v25, "viviendas", 2025, members=_persons_2025())["HOG_IND"]) == ["No"]
    v20 = v25.rename(columns={"CVE_ENT": "ENT"})
    p20 = grandparent.rename(columns={"CVE_ENT": "ENT"})
    assert list(d.derive(v20, "viviendas", 2020, members=p20)["HOG_IND"]) == ["No"]     # 2020
    assert list(d.derive(v20, "viviendas", 2020, members=p20.assign(PARENTESCO=["101", "416"]))
                ["HOG_IND"]) == ["Sí"]                                     # a parent-in-law
    # EIC 2015: the members' raw keys without the leading zeros, a harmonized dwelling with
    v15 = dwellings(1, FINANCIAMIENTO=[""], CVE_ENT=["01"], ID_VIV=["010010000001"])
    p15 = _persons_2015().assign(ENT="1", ID_VIV="10010000001")
    assert list(d.derive(v15, "viviendas", 2015, members=p15)["HOG_IND"]) == ["Sí"]  # the wife
    # Censo 2010: state-scoped serials, the entity tells the households apart
    v10 = dwellings(3, SEXO=["1", "3", "1"], ENT=["09", "09", "10"],
                    ID_VIV=["00000002", "00000001", "00000001"])
    p10 = pd.concat([_persons_2010(), _persons_2010().assign(ENT="10", HLENGUA=["3", "3", "3"])],
                    ignore_index=True)
    assert list(d.derive(v10, "viviendas", 2010, members=p10)["HOG_IND"]) == ["No", "Sí", "No"]
    # CGPV 2000: the dwelling rows are households (the composite keys from the parts)
    v00 = pd.DataFrame({"CLAVIV": ["01", "01"], "CUADORM": ["01", "01"],
                        "TOTCUART": ["02", "02"], "DRENAJE": ["1", "1"],
                        "INGTRHOG": ["000100", "000100"], "SEXO": ["1", "1"], "ENT": ["01"] * 2,
                        "MUN": ["001"] * 2, "LOC": ["0001"] * 2, "NUMVIV": ["000001"] * 2,
                        "NUMHOG": ["2", "1"], "TIPOHOG": ["1", "1"], "COCINA": ["2", "2"],
                        "COCDOR": ["", ""]}, dtype="str")
    out = d.derive(v00, "viviendas", 2000, members=_persons_2000())
    assert list(out["HOG_IND"]) == ["No", "Sí"]
    assert list(out["PRIMER_HOGAR"]) == ["No", "Sí"]                   # 7f
    # the Conteo 2005: on the households (its dwelling rows are dwellings: no HOG_IND)
    h05 = pd.DataFrame({"CLAVIVPA": ["1", "1"], "SEXO": ["2", "1"], "ENT": ["09"] * 2,
                        "MUN": ["002"] * 2, "CONS_MUN": ["000001"] * 2,
                        "CONS_HOG": ["01", "02"]}, dtype="str")
    out = d.derive(h05, "hogares", 2005, members=_persons_2005())
    assert list(out["HOG_IND"]) == ["Sí", "No"]
    assert out["HOG_IND"].dtype == d.derived_dtypes("hogares", "2005")["HOG_IND"]
    assert "HOG_IND" not in d.derived_dtypes("viviendas", "2005")
    for period in ("1990", "1995"):
        assert "HOG_IND" not in d.derived_dtypes("viviendas", period)
    with pytest.raises(ValueError, match="members="):
        d.derive(v25, "viviendas", 2025)
    with pytest.raises(ValueError, match="records without members"):
        d.derive(v25.assign(ID_VIV="010010000009"), "viviendas", 2025, members=grandparent)
    with pytest.raises(ValueError, match="HOG_IND"):
        d.derive(v25, "viviendas", 2025, members=grandparent.assign(HLENGUA=["1", "7"]))
    with pytest.raises(ValueError, match="needs 'HLENGUA', absent from the members"):
        d.derive(v25, "viviendas", 2025, members=grandparent.drop(columns="HLENGUA"))


def test_derive_linea_parentesco():
    """8f: each person's kinship line (Censo 2020's nine), from the edition's relationship
    item: CGPV 1990's CVE_PAR, the Conteo 2005's PARENT (102 «persona sola» heads a
    household), Censo 2010's PARENT and, for its «otro parentesco» (08), OTROPARE_C — a
    detail of no line raises, none or «Familiar» (623) is «Otro parentesco» —, the EIC 2015's
    PARENT_OTRO_C, 2020/2025 PARENTESCO. 1995 and 2000 have none."""
    ref, spouse, child = "Persona de referencia", "Esposa(o) o pareja", "Hija(o)"
    cases = (("2025", _persons_2025(), [ref, child]),
             ("2015", _persons_2015(), [ref, spouse]),
             ("2010", _persons_2010(), [child, ref, ref]),
             # the first person (the head's child in the fixture) another relative
             *(("2010", _persons_2010().assign(PARENT=[parent, "01", "01"],
                                               OTROPARE_C=[detail, "", ""]), [line, ref, ref])
               for parent, detail, line in (
                   ("08", "612", "Ascendente"), ("08", "613", "Descendente"),
                   ("08", "603", "Colateral"), ("08", "", "Otro parentesco"),
                   ("08", "623", "Otro parentesco"), ("04", "609", "Descendente"),
                   ("07", "", "Ascendente"), ("09", "501", "Sin parentesco"),
                   ("99", "", "No especificado"))),
             ("2005", _persons_2005(), [ref, child, ref]),
             ("1990", _persons_1990(), [ref, spouse, child, "Descendente", "Ascendente"]))
    for period, frame, expected in cases:
        out = d.derive(frame, "personas", period)
        assert list(out["LINEA_PARENTESCO"]) == expected, period
        assert out["LINEA_PARENTESCO"].dtype == d._LINEA_PARENTESCO
    for period in ("1995", "2000"):
        assert "LINEA_PARENTESCO" not in d.derived_dtypes("personas", period)
    with pytest.raises(ValueError, match="LINEA_PARENTESCO"):          # 699: no such detail
        d.derive(_persons_2010().assign(PARENT=["08", "01", "01"], OTROPARE_C=["699", "", ""]),
                 "personas", 2010)


# 8f: the words of each kinship line's relationship labels (lower case, no accents; at the
# start of a word, so «compadre» is no «padre»)
_LINE_WORDS = {
    "Persona de referencia": ("jef", "persona sola"),
    "Esposa(o) o pareja": ("espos", "companer", "concubin", "amasi", "querid", "amante",
                           "marido"),
    "Hija(o)": ("hij", "entenad", "adopt", "recogid"),
    "Ascendente": ("madre", "padre", "madrastr", "padrastr", "abuel", "bisabuel",
                   "tatarabuel", "tio", "tia", "suegr", "padrino", "madrina"),
    "Descendente": ("niet", "bisniet", "tataraniet", "sobrin", "nuera", "yerno", "ahijad"),
    "Colateral": ("herman", "prim", "cunad", "concun", "consuegr", "compadre", "comadre"),
    "Otro parentesco": ("familiar", "pariente", "otro parentesco"),
    "Sin parentesco": ("domestic", "huesped", "tutor", "tutelad", "no tiene parentesco",
                       "sin parentesco", "amig", "ningun", "sirvient", "criad", "recamarer",
                       "cociner", "lavander", "niner", "mozo", "jardiner", "velador",
                       "vigilante", "porter", "chofer", "ama de llaves", "mayordomo",
                       "dama de compania"),
    "No especificado": ("no especificad", "parentesco no especificad"),
}


def test_linea_parentesco_labels():
    """8f: each relationship code's line agrees with its label in the edition's dictionary
    (the lines were assigned by the labels: 2020 = INEGI's 13-02, Censo 2010 = its 12_04A;
    the others by 2020's rule), and only the «Sin parentesco» labels name a domestic worker,
    a guest or a tutor."""
    import re
    import unicodedata

    def plain(label: str) -> str:
        text = unicodedata.normalize("NFD", label.lower())
        return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    items = {**{p: (item,) for p, item in d._LINEA_ITEMS.items()},
             "2010": ("PARENT", "OTROPARE_C")}
    for period, sources in items.items():
        _, gid, _ = d._frame_group("personas", period)
        labels = variables_cpv_labels("personas", gid)
        for source in sources:
            entry = labels[source]
            codes = {int(k): plain(v) for k, v in {**(entry.get("Categorías") or {}),
                                                   **(entry.get("Especiales") or {})}.items()}
            for code, line in _line_of(period, source).items():
                if code not in codes:                   # a code the edition does not list
                    continue
                # 1990's first digit is the relationship, CATPAREN's word what was written:
                # its 702 «huésped», 703 «abonado» live alone (group 7, «persona sola»)
                label = "persona sola" if (period, code // 100) == ("1990", 7) else codes[code]
                words = "|".join(_LINE_WORDS[line])
                assert re.search(rf"\b({words})", label), (period, code, label, line)
                if line != "Sin parentesco":
                    assert not re.search(r"\b(domestic|huesped|tutor)", label), (period, code)


def test_household_members(monkeypatch, tmp_path):
    """6x: ``cpv._household_members`` reads the members' person items under the edition's
    names (2010: ``PARENT``, though the file also has ``OTROPARE_C``; 2005: ``HABLENIN``) and
    their household key, keyed like the frame: 2000/2005 composite keys, 2010's national
    ``ID_VIV`` under ``harmonize``, the EIC 2025's ``CVE_ENT``."""
    from mxcensus import cpv
    from mxcensus.data import _registry

    files = {}
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda fname, **_: str(files[fname]))

    def persons(period, frame):
        name = cpv.cpv_filename("personas", period, 1)
        files[name] = tmp_path / name
        frame.astype("string").to_parquet(files[name])

    sources = d._member_sources("viviendas", "2010")
    persons("2010", pd.DataFrame({"ENT": ["01"] * 2, "ID_VIV": ["00000001"] * 2,
                                  "PARENT": ["01", "03"], "OTROPARE_C": ["101", "301"],
                                  "HLENGUA": ["1", "3"], "SEXO": ["1", "3"]}))
    m10 = cpv._household_members("2010", 1, False, sources)
    assert list(m10.columns) == ["ENT", "ID_VIV", "PARENT", "HLENGUA"]
    assert list(cpv._household_members("2010", 1, True, sources)["ID_VIV"]) == ["010000000001"] * 2
    persons("2025", pd.DataFrame({"CVE_ENT": ["01"], "ID_VIV": ["010010000001"],
                                  "PARENTESCO": ["101"], "HLENGUA": ["1"], "AFRODES": ["3"]}))
    m25 = cpv._household_members("2025", 1, False, d._member_sources("viviendas", "2025"))
    assert list(m25.columns) == ["CVE_ENT", "ID_VIV", "PARENTESCO", "HLENGUA", "AFRODES"]
    persons("2005", _persons_2005())
    m05 = cpv._household_members("2005", 1, False, d._member_sources("hogares", "2005"))
    assert list(m05.columns) == ["ID_VIV", "ID_HOG", "ENT", "MUN", "CONS_MUN", "CONS_HOG",
                                 "PARENT", "HABLENIN"]
    assert list(m05["ID_HOG"]) == ["09002000000101"] * 2 + ["09002000000102"]


def test_derive_household_items_6z():
    """6z: the occupants per room (``NUMPERS`` ÷ ``TOTCUART``, more than 2.5: the EIC 2025's
    ``VPH_2_5OCU``; 2010–2025), the household's class (``TIPOHOG`` 1–4 familiar, 5–6 not, 9
    unknown; 2000, 2010–2025, dwellings and persons) and its income from other sources than
    work (any of the four items yes, all four no, else not specified; 2015–2025)."""
    rows = [  # NUMPERS TOTCUART TIPOHOG  OTROPAIS DENTPAIS AYUGOB JUBPEN → rooms, class, income
        ("5", "2", "1", "2", "4", "6", "8", "Hasta 2.5", "Familiar", "No"),     # 2.5 exactly
        ("6", "2", "2", "1", "4", "6", "8", "Más de 2.5", "Familiar", "Sí"),
        ("1", "99", "4", "2", "9", "6", "8", "No especificado", "Familiar", "No especificado"),
        ("1", "", "5", "9", "9", "9", "7", "Blanco por pase", "No familiar", "Sí"),
        ("3", "1", "6", "9", "9", "9", "9", "Más de 2.5", "No familiar", "No especificado"),
        ("3", "3", "9", "2", "4", "5", "8", "Hasta 2.5", "No especificado", "Sí"),
    ]
    viv = pd.DataFrame([r[:7] for r in rows], dtype="str",
                       columns=["NUMPERS", "TOTCUART", "TIPOHOG", *d._INGR_OTROS]).assign(
        CLAVIVP="1", CUADORM="1", DRENAJE="1", INGTRHOG="0",
        **{f"FINANCIAMIENTO{i}": "" for i in (1, 2, 3)})
    out = _derive_dwellings(viv, "2025")
    assert list(out["OCUP_CUARTO_CAT"]) == [r[7] for r in rows]
    assert list(out["CLASE_HOG"]) == [r[8] for r in rows]
    assert list(out["INGR_OTROS"]) == [r[9] for r in rows]
    for col, dtype in (("OCUP_CUARTO_CAT", d._OCUP_CUARTO), ("CLASE_HOG", d._CLASE_HOG),
                       ("INGR_OTROS", d._YES_NO)):
        assert out[col].dtype == dtype == d.derived_dtypes("viviendas", "2025")[col]
    # the same codes in the older editions (2015 un-padded; 2000: no rooms nor income)
    v15 = _derive_dwellings(viv.drop(columns=[f"FINANCIAMIENTO{i}" for i in (1, 2, 3)])
                            .assign(FINANCIAMIENTO=""), "2015")
    assert v15[["OCUP_CUARTO_CAT", "CLASE_HOG", "INGR_OTROS"]].equals(
        out[["OCUP_CUARTO_CAT", "CLASE_HOG", "INGR_OTROS"]])
    assert {"OCUP_CUARTO_CAT", "INGR_OTROS"}.isdisjoint(d.derived_dtypes("viviendas", "2000"))
    assert "INGR_OTROS" not in d.derived_dtypes("viviendas", "2010")
    # the persons take their household's type (the loader attaches it: cpv._attach_dwellings)
    assert list(d.derive(_persons_2010(), "personas", 2010)["CLASE_HOG"]) == [
        "Familiar", "Familiar", "No familiar"]
    assert list(d.derive(_persons_2000(), "personas", 2000)["CLASE_HOG"]) == [
        "Familiar", "Familiar", "No especificado", "No especificado"]
    assert d.derived_dtypes("personas", "2025")["CLASE_HOG"] == d._CLASE_HOG
    for period in ("1990", "1995", "2005"):
        assert "CLASE_HOG" not in d.derived_dtypes("personas", period)
    with pytest.raises(ValueError, match="OCUP_CUARTO_CAT"):               # 26 rooms
        _derive_dwellings(viv.assign(TOTCUART="26"), "2025")
    with pytest.raises(ValueError, match="CLASE_HOG"):                     # no type 7
        _derive_dwellings(viv.assign(TIPOHOG="7"), "2025")
    with pytest.raises(ValueError, match="INGR_OTROS"):                    # 3 is DENTPAIS's
        _derive_dwellings(viv.assign(INGR_PEROTROPAIS="3"), "2025")
    with pytest.raises(ValueError, match="needs 'TIPOHOG'"):
        d.derive(_persons_2025().drop(columns="TIPOHOG"), "personas", 2025)


def test_attach_dwellings(monkeypatch, tmp_path):
    """6z: ``cpv._attach_dwellings`` gives each person its household's ``TIPOHOG`` from the
    dwelling file (a column-projected read): CGPV 2000 on ``ID_HOG`` (its dwelling rows are
    households), Censo 2010 on the entity and the serial (national keys under
    ``harmonize``), the EIC 2015 whatever the zero padding; the Conteo 2005's households
    their dwelling's ``CLAVIVPA`` (6v). A record without its dwelling raises."""
    from mxcensus import cpv
    from mxcensus.data import _registry

    files = {}
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda fname, **_: str(files[fname]))

    def dwellings(period, frame):
        name = cpv.cpv_filename("viviendas", period, 1)
        files[name] = tmp_path / name
        frame.astype("string").to_parquet(files[name])

    p00 = cpv._composite_keys(_persons_2000().drop(columns="TIPOHOG"), "personas")
    dwellings("2000", pd.DataFrame({"ENT": ["01"] * 2, "MUN": ["001"] * 2, "LOC": ["0001"] * 2,
                                    "NUMVIV": ["000001"] * 2, "NUMHOG": ["2", "1"],
                                    "TIPOHOG": ["5", "2"], "CLAVIV": ["01", "01"]}))
    out = cpv._attach_dwellings(p00, "personas", "2000", 1, False)
    assert list(out["TIPOHOG"]) == ["2", "2", "5", "5"]          # households 1 and 2
    p10 = _persons_2010().drop(columns="TIPOHOG")
    dwellings("2010", pd.DataFrame({"ENT": ["09"] * 2, "ID_VIV": ["00000002", "00000001"],
                                    "TIPOHOG": ["5", "1"]}))
    assert list(cpv._attach_dwellings(p10, "personas", "2010", 1, False)["TIPOHOG"]) == [
        "1", "1", "5"]
    h10 = p10.assign(CVE_ENT="09", ID_VIV=["090000000001"] * 2 + ["090000000002"])
    assert list(cpv._attach_dwellings(h10, "personas", "2010", 1, True)["TIPOHOG"]) == [
        "1", "1", "5"]
    p15 = _persons_2015().drop(columns="TIPOHOG").assign(ID_VIV="010010000001", ENT="01")
    dwellings("2015", pd.DataFrame({"ENT": ["1"], "ID_VIV": ["10010000001"], "TIPOHOG": ["6"]}))
    assert list(cpv._attach_dwellings(p15, "personas", "2015", 1, True)["TIPOHOG"]) == ["6"] * 2
    with pytest.raises(ValueError, match="2 records without their dwelling"):
        cpv._attach_dwellings(p15.assign(ID_VIV="010010000002"), "personas", "2015", 1, True)
    h05 = pd.DataFrame({"ENT": ["09"] * 2, "MUN": ["002"] * 2, "CONS_MUN": ["000001"] * 2,
                        "CONS_HOG": ["01", "02"]}, dtype="str")
    dwellings("2005", pd.DataFrame({"ENT": ["09"], "MUN": ["002"], "CONS_MUN": ["000001"],
                                    "CLAVIVPA": ["2"]}))
    out = cpv._attach_dwellings(cpv._composite_keys(h05, "hogares"), "hogares", "2005", 1, False)
    assert list(out["CLAVIVPA"]) == ["2", "2"]


def _persons_1990() -> pd.DataFrame:
    """Five CGPV 1990 persons (raw codes; 0 = not asked): an employed adult with complete
    secundaria and technical studies after it, an adult with no grade but preschool, a child
    under 5, a schoolchild aged 10, an adult with technical studies after primaria."""
    return pd.DataFrame({
        "ENT": ["01"] * 5, "ANO_CUMP": ["040", "070", "003", "010", "999"],
        "APROBO": ["1", "2", "0", "1", "1"], "PRESCO": ["0", "2", "0", "3", "0"],
        "NIV_EST": ["2", "0", "0", "1", "1"], "ANO_APRO": ["03", "00", "00", "04", "06"],
        "TEC_PRIM": ["0", "0", "0", "0", "2"], "TEC_SEC": ["2", "0", "0", "0", "0"],
        "NOR_BAS": ["0", "0", "0", "0", "0"],
        "ACT_PRIN": ["1", "5", "0", "0", "2"], "EST_CIVIL": ["2", "7", "0", "0", "5"],
        "HORAS": ["048", "000", "000", "000", "000"],
        "INGRESO": ["00430000", "00000000", "00000000", "00000000", "99999998"],
        "CVE_P_NAC": ["001", "014", "001", "050", "221"],
        "CVE_P_RES": ["001", "999", "000", "001", "300"],
        "RELIGION": ["2", "4", "0", "3", "9"],
        "C_A_ECO": ["31102", "00000", "00000", "00000", "10001"],
        "CVE_PAR": ["100", "200", "300", "608", "614"],         # 8f: grandchild, parent-in-law
    }, dtype="str")


def test_derive_persons_1990_recodes():
    out = d.derive(_persons_1990(), "personas", 1990)
    # técnica after a complete secundaria; preschool only; under 5; primaria 4; técnica after
    # primaria (2020's 6: «Primaria_com», the legacy rule; INEGI's own level, 6k)
    assert list(out["EDUC"]) == ["Posbásica", "Sin Educación", "Blanco por pase",
                                 "Primaria_incom", "Primaria_com"]
    assert list(out["EDUC_INEGI"]) == [*list(out["EDUC"])[:4], "Técnica_primaria"]
    assert list(out["EDAD_CAT"])[::4] == ["25-49", "No especificado"]
    assert list(out["CONACT_CAT"]) == ["Trabaja", "No trabaja", "Blanco por pase",
                                       "Blanco por pase", "Trabaja"]
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["casado", "separado", "Blanco por pase",
                                               "Blanco por pase", "separado"]
    # hours and income: blank unless employed; who had a job worked 0 hours; $430,000 old
    # pesos = $430 new; «no sabe» (99999998) = not specified
    assert list(out["HORTRA_CAT"]) == ["41-48", "Blanco por pase", "Blanco por pase",
                                       "Blanco por pase", "0-5"]
    assert list(out["INGTRMEN_CAT"]) == ["1-999", "Blanco por pase", "Blanco por pase",
                                         "Blanco por pase", "No especificado"]
    # birthplace: here, Jalisco, here, an entity not sufficiently specified (050), a country
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["EstaEnt", "OtraEnt", "EstaEnt", "OtraEnt",
                                             "OtroPais"]
    assert list(out["ENT_PAIS_RES_CAT"]) == ["EstaEnt", "No especificado", "Blanco por pase",
                                             "EstaEnt", "OtroPais"]
    assert list(out["RELIGION_CAT"]) == ["Católica", "Otros credos", "Blanco por pase",
                                         "Protestante/cristiano evangélico", "No especificado"]
    for col, dtype in d.derived_dtypes("personas", "1990").items():
        assert out[col].dtype == dtype, col
    # small amounts stay positive (≥ $1): the ~1% of incomes written in thousands
    small = d.derive(_persons_1990().assign(INGRESO=["00000258"] + ["00000000"] * 4),
                     "personas", 1990)
    assert small["INGTRMEN_CAT"].iloc[0] == "1-999"


def _persons_1995() -> pd.DataFrame:
    """Five Conteo 1995 persons (raw codes; "" = blank)."""
    return pd.DataFrame({
        "ENT": ["09"] * 5, "P3_6": ["35", "99", "03", "60", "20"],
        "P5_3": ["", "5", "", "6", "9"], "P5_4B": ["3", "2", "", "", ""],
        "P5_4A": ["3", "4", "", "", ""], "P5_5": ["1", "2", "", "", ""],
        "P5_7": ["2", "", "", "", ""],
        "P7_1": ["1", "9", "", "5", "4"], "P6_1": ["5", "8", "", "2", "6"],
        "P7_6": ["40", "99", "", "", ""], "P7_9MP": ["001286", "999999", "", "", ""],
        "P3_7B": ["09", "35", "70", "90", "99"], "P4_6A": ["15", "", "", "34", "09"],
        # 6t: one dwelling, two households: a woman heads the first (1), a man the second
        "MUN": ["002"] * 5, "ZONA": ["1"] * 5, "UPM": ["01"] * 5, "VIV": ["001"] * 5,
        "HOGAR": ["1", "1", "1", "2", "2"], "P3_4": ["1", "3", "3", "6", "1"],
        "P3_5": ["2", "1", "1", "2", "1"],
    }, dtype="str")


def test_derive_persons_1995_recodes():
    out = d.derive(_persons_1995(), "personas", 1995)
    # técnica after secundaria; primaria 4; under 5; never attended; attendance unknown
    assert list(out["EDUC"]) == ["Posbásica", "Primaria_incom", "Blanco por pase",
                                 "Sin Educación", "No especificado"]
    assert list(out["EDAD_CAT"])[:2] == ["25-49", "No especificado"]      # 99 = NE
    assert list(out["CONACT_CAT"]) == ["Trabaja", "No especificado", "Blanco por pase",
                                       "No trabaja", "No trabaja"]
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["casado", "No especificado", "Blanco por pase",
                                               "separado", "soltero"]
    assert list(out["HORTRA_CAT"])[:2] == ["21-40", "No especificado"]
    assert list(out["INGTRMEN_CAT"])[:3] == ["1,000-4,999", "No especificado", "Blanco por pase"]
    # 35 the United States, 70 «México (país)» = entity not specified, 90 a country, 99
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["EstaEnt", "OtroPais", "OtraEnt", "OtroPais",
                                             "No especificado"]
    assert list(out["ENT_PAIS_RES_CAT"]) == ["OtraEnt", "Blanco por pase", "Blanco por pase",
                                             "OtroPais", "EstaEnt"]
    for col, dtype in d.derived_dtypes("personas", "1995").items():
        assert out[col].dtype == dtype, col


def test_derive_dwellings_1990_1995():
    v90 = pd.DataFrame({"T_VIV": ["01", "02", "05", "09"], "P_DORMIR": ["01", "03", "00", "99"],
                        "T_CUARTOS": ["26", "02", "00", "99"], "DRENAJE": ["3", "4", "0", "9"]},
                       dtype="str")
    out = d.derive(v90, "viviendas", 1990)
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Vivienda", "Otro", "Vivienda"]   # refugio
    assert list(out["CUADORM_CAT"]) == ["1", "2+", "Blanco por pase", "No especificado"]
    assert list(out["TOTCUART_CAT"]) == ["3+", "2", "Blanco por pase", "No especificado"]
    # 3 «desagüe al suelo, a un río o lago» is drainage; a refugio has no characteristics
    assert list(out["DRENAJE_CAT"]) == ["Sí", "No", "Blanco por pase", "No especificado"]
    v95 = pd.DataFrame({"P1_6": ["02", "99"], "P1_7": ["01", "04"], "P1_13": ["4", "5"]},
                       dtype="str")
    out = d.derive(v95, "viviendas", 1995)
    assert list(out["CUADORM_CAT"]) == ["2+", "No especificado"]
    assert list(out["TOTCUART_CAT"]) == ["1", "3+"] and list(out["DRENAJE_CAT"]) == ["Sí", "No"]
    assert "CLAVIVP_CAT" not in out                                  # no dwelling class


def test_derive_sector():
    """6o: INEGI's three sectors — 1990 from the CMAP division (C_A_ECO's first digit), 2000
    from the SCIAN subsector, 2010–2025 from the 4-digit SCIAN; an unknown sector raises."""
    out = d.derive(_persons_1990(), "personas", 1990)
    assert list(out["SECTOR"]) == ["Secundario", "Blanco por pase", "Blanco por pase",
                                   "Blanco por pase", "Primario"]
    out = d.derive(_persons_2000(), "personas", 2000)
    assert list(out["SECTOR"]) == ["Secundario", "Blanco por pase", "Blanco por pase",
                                   "No especificado"]
    scian = d._sector("ACTIVIDADES_C", 100)
    codes = pd.Series([1110, 2121, 2361, 3111, 4311, 9311, 9999, np.nan])
    assert list(scian(pd.DataFrame({"ACTIVIDADES_C": codes}))["SECTOR"]) == [
        "Primario", "Secundario", "Secundario", "Secundario", "Terciario", "Terciario",
        "No especificado", "Blanco por pase"]
    assert scian(pd.DataFrame({"ACTIVIDADES_C": [1010.0]}))["SECTOR"].isna().all()  # no 10
    cmap = d._sector_1990(pd.DataFrame({"C_A_ECO": [42011.0, 50101, 81000, 99999]}))
    assert list(cmap["SECTOR"]) == ["Secundario", "Terciario", "Terciario", "No especificado"]
    with pytest.raises(ValueError, match="SECTOR"):
        d.derive(_persons_2000().assign(ACTTRAB_C=["101", "", "", "999"]), "personas", 2000)


def test_derive_1990_1995_unknown_codes():
    with pytest.raises(ValueError, match="EDUC"):             # a grade approved, no level
        d.derive(_persons_1990().assign(NIV_EST=["0"] * 5), "personas", 1990)
    with pytest.raises(ValueError, match="RELIGION_CAT"):
        d.derive(_persons_1990().assign(RELIGION=["7"] * 5), "personas", 1990)
    with pytest.raises(ValueError, match="DRENAJE_CAT"):
        d.derive(pd.DataFrame({"T_VIV": ["01"], "P_DORMIR": ["01"], "T_CUARTOS": ["01"],
                               "DRENAJE": ["6"]}, dtype="str"), "viviendas", 1990)


def test_derive_older_editions_unknown_codes():
    """A code outside an edition's list raises, also for the dummy sets and the 2010 flag."""
    for col, value, name in (("MED_TRASLADO_TRAB1", "8", "MED_TRASLADO_TRAB_"),
                             ("DHSERSAL1", "10", "DHSERSAL_")):
        with pytest.raises(ValueError, match=name):
            d.derive(_persons_2015().assign(**{col: [value, "2"]}), "personas", 2015)
    with pytest.raises(ValueError, match="LIM_ACTIVIDAD"):                # no DISCAP answer
        d.derive(_persons_2010().assign(DISCAP8=["17", "", ""]), "personas", 2010)
    with pytest.raises(ValueError, match="MADRE_EN_VIVIENDA"):            # an unknown code
        d.derive(_persons_2010().assign(IDMADREC=["77", "88", "99"]), "personas", 2010)
    with pytest.raises(ValueError, match="ENT_PAIS_NAC_CAT"):             # neither item
        d.derive(_persons_2010().assign(LNACPAIS_C=["", "", ""],
                                        LNACEDO_C=["009", "", "999"]), "personas", 2010)
    with pytest.raises(ValueError, match="EDUC"):                          # Doctorado, 7th year
        d.derive(_persons_2010().assign(NIVACAD=["12", "05", "99"], ESCOLARI=["07", "03", "99"]),
                 "personas", 2010)
    for code in ("410000", "1101", ""):                   # no such group; 2020's code; blank
        with pytest.raises(ValueError, match="RELIGION_CAT"):
            d.derive(_persons_2010().assign(OTRAREL_C=["110300", code, "310100"]),
                     "personas", 2010)


def test_derive_errors():
    df = _persons_2025()
    with pytest.raises(ValueError, match="SITUA_CONYUGAL_CAT"):    # a code no recode knows
        d.derive(df.assign(SITUA_CONYUGAL=["77", "01"]), "personas", 2025)
    with pytest.raises(ValueError, match="needs 'HORTRA'"):
        d.derive(df.drop(columns="HORTRA"), "personas", 2025)
    with pytest.raises(ValueError, match="already present"):
        d.derive(df.assign(EDAD_CAT="x"), "personas", 2025)
    with pytest.raises(ValueError, match="hogares"):
        d.derive(df, "hogares", 2005)
    with pytest.warns(UserWarning, match="no derived columns"):
        assert d.derive(df, "personas", 1980).equals(df)


# --- constraints per edition ----------------------------------------------------------------

def test_cpv_constraints_per_edition():
    per, viv = mxcensus.constraints_personas(), mxcensus.constraints_viviendas()
    head = {"PHOGJEF_F": {"HOGJEF_SEXO": ["Mujer"]}, "PHOGJEF_M": {"HOGJEF_SEXO": ["Hombre"]}}
    assert len(mxcensus.cpv_constraints("personas", 2020)) == len(per) + len(head) + 2  # 6t,
    #                                                                       6v POBHOG, 6w PHOG_IND
    assert len(mxcensus.cpv_constraints("viviendas", 2020)) == len(viv)
    for period in (2000, 2005, 2010, 2020, 2025):     # the population by its head's sex (6t)
        cons = mxcensus.cpv_constraints("personas", period)
        assert {ind: cons[ind] for ind in head} == head, period
        assert cons["POBHOG"] == cons["POBTOT"] == {}, period   # 6v: in households, all
    for period in (1990, 1995):                       # no household indicator
        cons = mxcensus.cpv_constraints("personas", period)
        assert not {*head, "POBHOG"} & set(cons) and cons["POBTOT"] == {}
    assert "POBHOG" not in per                                         # the legacy set: frozen
    # 6w: the population in indigenous households, each edition's own definition (2005/2010
    # head or partner, own cells: the crosswalk marks 2020's other relatives not comparable)
    for period in (2005, 2010, 2020, 2025):
        assert mxcensus.cpv_constraints("personas", period)["PHOG_IND"] == {"HOG_IND": ["Sí"]}
    for period in ("2005", "2010"):
        assert d._EDITION_CELLS["personas", period]["PHOG_IND"] == {"HOG_IND": ["Sí"]}
    for period in (1990, 1995, 2000):                  # no such indicator (2015: none at all)
        assert "PHOG_IND" not in mxcensus.cpv_constraints("personas", period)
    assert mxcensus.cpv_iter_crosswalk()["PHOG_IND"]["Comparable"] is False
    assert mxcensus.cpv_constraints("personas", 2015) == {}           # no ITER, no estimates
    p10 = mxcensus.cpv_constraints("personas", 2010)
    assert 0 < len(p10) < len(per)
    assert {"PDER_SS", "PDER_IMSS", "PSINDER", "P18YM_PB", "P15YM_SE", "P12YM_SOLT"} <= set(p10)
    # 6o: the Seguro Popular is 2010's own cell (not comparable with 2020's INSABI)
    assert p10["PDER_SEGP"] == {"DHSERSAL_SALUD_PUBLICA": [1]}
    own = d._EDITION_CELLS["personas", "2010"]                         # 2010's own limitation
    assert {ind: p10[ind] for ind in own} == own
    assert p10["PCLIM_VIS"] == {"DISCAP2": ["Ver, aun usando lentes"]}
    # 7g: INEGI's rule (the unspecified entity apart), as the 2010 ITER
    assert p10["PNACOE"] == {"ENT_PAIS_NAC_INEGI": ["OtraEnt"]}
    assert {"PNACENT_F", "PRES2005", "PRESOE05_M"} <= set(p10)        # 7g: its own names
    assert p10["PRESOE05_M"] == {"EDAD_CAT": d._AGES_5PLUS, "LUGAR_RES_5A": ["Otra entidad"],
                                 "SEXO": ["Hombre"]}
    assert not {"PRES2015", "PRESOE15_M"} & set(p10)
    assert {"PCATOLICA", "POTRAS_REL", "PSIN_RELIG"} <= set(p10)       # 6f: 2010 religion
    # 7g: its own classification (the neo-Israelites among the other credos)
    assert p10["PNCATOLICA"] == {"RELIGION_INEGI": ["Protestante/cristiano evangélico"]}
    assert p10["POTRAS_REL"] == {"RELIGION_INEGI": ["Otros credos"]}
    assert p10["PCATOLICA"] == {"RELIGION_CAT": ["Católica"]}
    assert "PRO_CRIEVA" not in p10 and "PNCATOLICA" not in mxcensus.cpv_constraints("personas", 2020)
    assert "PCON_LIM" not in mxcensus.cpv_constraints("personas", 2020)
    v10 = mxcensus.cpv_constraints("viviendas", 2010)                 # 6n: 2010 CLAVIVP_CAT
    assert len(v10) == 28                                            # 6s: + HOGJEF_F/M
    # 6s: the head's sex, from the person file (2000/2005/2010 have no dwelling item); 6v:
    # the Conteo 2005 counts its households on the household frame
    h05 = mxcensus.cpv_constraints("hogares", 2005)
    for v in (v10, mxcensus.cpv_constraints("viviendas", 2000), h05):
        assert v["HOGJEF_F"] == {"JEFE_SEXO": ["Mujer"], "CLAVIVP_CAT": ["Vivienda", "Otro"]}
        assert v["HOGJEF_M"]["JEFE_SEXO"] == ["Hombre"]
    assert h05 == {ind: viv[ind] for ind in ("TOTHOG", "HOGJEF_F", "HOGJEF_M")}
    for period in (1990, 1995, 2000, 2010, 2015, 2020, 2025):
        with pytest.raises(ValueError, match="only the Conteo 2005"):
            mxcensus.cpv_constraints("hogares", period)
    assert v10["VPH_1DOR"] == {"CLAVIVP_CAT": ["Vivienda"], "CUADORM_CAT": ["1"]}     # legacy
    assert v10["VPH_C_ELEC"] == {"CLAVIVP_CAT": ["Vivienda"], "ELECTRI": ["Sí"]}      # own items
    assert set(v10["VPH_SNBIEN"]) == {"CLAVIVP_CAT", *d._SIN_BIENES_2010}            # 9 goods
    p25 = mxcensus.cpv_constraints("personas", 2025)
    assert {"POBTOT", "POBFEM", "P_15YMAS_F", "PDER_SS", "POCUPADA"} <= set(p25)
    v25 = mxcensus.cpv_constraints("viviendas", 2025)                 # 6x: + HOG_IND
    assert {"TOTHOG", "HOGJEF_F", "HOGJEF_M", "HOG_IND"} <= set(v25)
    assert v25["HOG_IND"] == {"HOG_IND": ["Sí"]}
    # 6y: the EIC 2025's percentages, as the counts load_cpv_estimaciones(counts=True) gives
    # (29 + 4 counts → 94 + 31); each indicator is a column of it
    from mxcensus.cpv_aggregates import _PERCENT_BASES, _count_name
    counts = {_count_name(p) for p in _PERCENT_BASES}
    est = set(mxcensus._resources.variables_cpv(
        "estimaciones", mxcensus._resources.cpv_schema_map()["estimaciones"]["latest"]))
    assert len(p25) == 214 and len(v25) == 93    # 6z: + 2 persons, + 38 + 23; 7a: + 118, + 1
    assert set(p25) | set(v25) <= est | counts and counts <= set(p25) | set(v25)
    # 7a: the persons' percentages and the published PUSU_SS, HOG_AFRO, PHOG_AFRO; each new
    # cell stays within its indicator's universe
    assert p25["P_0A4_F"] == {"EDAD_QUIN": ["0-4"], "SEXO": ["Mujer"]}
    assert p25["P_75YMAS"] == {"EDAD_QUIN": ["75-130"]}
    assert p25["PCON_DISC60YM"] == {"DISCAPACIDAD": ["Sí"], "EDAD_QUIN": d._QUIN[12:]}
    assert p25["PRESE20"] == {"EDAD_CAT": d._AGES_5PLUS, "LUGAR_RES_5A": [
        "Mismo municipio", "Otro municipio", "Municipio no especificado"]}
    assert p25["PASIS_OENT"] == {**d._STUDENTS, "ENT_PAIS_ASI_INEGI": ["OtraEnt", "OtroPais"]}
    assert p25["PASIS_MET"] == {**d._STUDENTS, "MED_TRASLADO_ESC_METRO_T": [1]}
    assert p25["POCUP_2HYM"] == {**d._EMPLOYED_CELLS, "TIE_TRASLADO_TRAB": ["Más de 2 horas"]}
    assert p25["PUSU_ISTE"] == {"SERSALUD": ["ISSSTE", "ISSSTE estatal"]}
    assert len(p25["PUSU_SS"]["SERSALUD"]) == 9                       # 01–09: not 10, 99
    assert p25["PcSSyRecAc"] == {"DHSERSAL_AFIL_ACCESO": [1]}
    assert p25["P12YM_CUL_M"] == {"EDAD_CAT": d._AGES_12PLUS,
                                  "SITUA_CONYUGAL_CAT": ["casado"], "SEXO": ["Hombre"]}
    assert p25["P12YM_SOLT"] == per["P12YM_SOLT"]                      # the legacy total
    assert p25["PHOG_AFRO"] == v25["HOG_AFRO"] == {"HOG_AFRO": ["Sí"]}
    assert not {"POCUP_CAM", "P3NHLI_CLI", "HF"} & set(p25)        # 7e: ratio constraints
    for period in (2000, 2010, 2020):                                 # the EIC 2025's only
        assert not {"P_0A4_F", "PRESM20", "PASIS_MET", "PUSU_IMSS", "PHOG_AFRO"} & set(
            mxcensus.cpv_constraints("personas", period))
    # 6z: the dwellings' other characteristics and the household items (the minors' food
    # items over the published HOG_MEN_ALIM, which has no cell), the population by its
    # household's class
    assert v25["VPH_2_5OCU"] == {**d._VIVIENDA, "OCUP_CUARTO_CAT": ["Más de 2.5"]}
    assert len(v25["VPH_PROPIA"]["TENENCIA"]) == 2                    # being paid for too
    assert v25["VPH_ESCRIDES"] == {**d._VIVIENDA, "ESCRITURAS": ["No sabe"]}
    assert v25["HOG_PERC"] == {"INGR_OTROS": ["Sí"]} and v25["HOG_NPERC"] == {"INGR_OTROS": ["No"]}
    assert v25["HOG_ALIM_N"] == {"ALIMENTACION": ["Sí"]}               # ran out of food
    assert v25["ING_MEN3"] == {"ING_ALIM_MEN3": ["Sí"]} and "HOG_MEN_ALIM" not in v25
    assert v25["HOG_FAM"] == p25["POBHOG_FAM"] == {"CLASE_HOG": ["Familiar"]}
    for period in (2000, 2010, 2020):                  # the EIC 2025's only
        assert not {"VPH_PTAB", "HOG_FAM", "HOG_PERC"} & set(
            mxcensus.cpv_constraints("viviendas", period))
        assert "POBHOG_FAM" not in mxcensus.cpv_constraints("personas", period)
    assert p25["PNACENT"] == {"ENT_PAIS_NAC_CAT": ["EstaEnt"]}
    assert p25["PNACOE_F"] == {"ENT_PAIS_NAC_INEGI": ["OtraEnt"], "SEXO": ["Mujer"]}  # no 997
    assert p25["PDER_ISTE"] == {"DHSERSAL_ISSSTE_T": [1]}                # federal or state
    assert p25["P6A14AN"] == {"EDAD_CAT": d._AGES_6_14, "ALFABET": ["No"]}
    assert v25["VIVPARHAB_C"] == d._VIVIENDA                          # the percentages' base
    assert "solo en el patio o terreno?" in v25["VPH_AGUADV"]["AGUA_ENTUBADA"]
    assert v25["VPH_EXCSA"]["SERSAN"][-1] == "letrina (pozo u hoyo)?"   # 2020: the toilet only
    for period in (2000, 2010, 2020):                  # published by the EIC 2025 only
        assert "HOG_IND" not in mxcensus.cpv_constraints("viviendas", period)
    assert "HOG_IND" in d._categories("hogares", "2005")       # 2005: not published either
    c20 = mxcensus.cpv_constraints("personas", 2020)
    assert c20["PDER_SEGP"] == {"DHSERSAL_SALUD_PUBLICA": [1]}        # neutral DHSERSAL name
    assert c20["PCON_DISC"] == {"DISCAPACIDAD": ["Sí"]}                # INEGI's definitions
    assert c20["PCON_LIMI"] == {"LIMITACION": ["Sí"]}
    assert c20["PSIND_LIM"] == p25["PSIND_LIM"] == {"SIN_DISC_LIM": ["Sí"]}   # 6g
    # 6k: the education cells on INEGI's levels (primaria completa without técnica)
    educ = {ind for ind, cells in per.items() if "EDUC" in (cells or {})}
    assert len(educ) == 18 and {"P15PRI_CO", "P18YM_PB_F"} <= educ
    for ind in educ:
        assert c20[ind] == {("EDUC_INEGI" if v == "EDUC" else v): c
                            for v, c in per[ind].items()}, ind
    assert c20["P15PRI_COF"]["EDUC_INEGI"] == ["Primaria_com"]
    v20 = mxcensus.cpv_constraints("viviendas", 2020)
    assert "dentro de la vivienda?" in v20["VPH_AGUADV"]["AGUA_ENTUBADA"]   # the FD's wording
    assert v20["VPH_EXCSA"] == {**d._VIVIENDA, "SERSAN": ["taza de baño (excusado o sanitario)?"]}
    # 6y: INEGI's limitation (LIMITACION) and disability (with the unknown degree, each
    # edition's label) by activity in 2020 and 2025; the legacy YAML stays as it was
    for ind, item in d._LIMITATIONS.items():
        assert c20[ind] == p25[ind] == {item: ["Lo hace con poca dificultad"],
                                        "LIMITACION": ["Sí"]}, ind
        assert "LIMITACION" not in per[ind]
    for ind, item in d._DISABILITIES.items():
        assert c20[ind][item][-1] == "Se desconoce el grado de la discapacidad"
        assert p25[ind][item][-1] == "Se desconoce el grado de la dificultad"
        assert len(per[ind][item]) == 2                                  # legacy: 3, 4
    assert per["PNACOE"] == {"ENT_PAIS_NAC_CAT": ["OtraEnt"]}          # the legacy cells
    # 7g: the 2020 ITER leaves the unspecified entity out (INEGI's rule, as 2025)
    assert c20["PNACOE"] == p25["PNACOE"] == {"ENT_PAIS_NAC_INEGI": ["OtraEnt"]}
    assert c20["PRESOE15_F"] == {"EDAD_CAT": d._AGES_5PLUS, "LUGAR_RES_5A": ["Otra entidad"],
                                 "SEXO": ["Mujer"]}
    assert c20["PDER_ISTE"] == {"DHSERSAL_ISSSTE": [1]}
    p00, p05 = (mxcensus.cpv_constraints("personas", p) for p in (2000, 2005))   # 6i
    # 7g: keyed by the column each edition publishes (the crosswalk's kept pairs)
    assert {"P5_CATOLIC", "PDER_SS", "PSINDER", "P12YM_CASA", "PEA", "PNACOENT"} <= set(p00)
    assert {"PDER_ISTE", "PSINDER", "P_OE2000", "P15YM_SE", "P_SEGPOP"} <= set(p05)
    assert not {"PCATOLICA", "PNACOE", "PRES2015", "PRESOE15"} & (set(p00) | set(p05))
    # 7g: 2000's own definitions — born or living in 1995 abroad too, the 5 and more
    assert p00["PNACOENT"] == {"ENT_PAIS_NAC_INEGI": ["OtraEnt", "OtroPais"]}
    assert p00["P5_RESO95"]["LUGAR_RES_5A"] == ["Otra entidad", "Estados Unidos", "Otro país"]
    for ind in ("P5_CATOLIC", "P5_NCATOLI", "P5_SINRELI", "P5_RESO95", "P5_RES95"):
        assert p00[ind]["EDAD_CAT"] == d._AGES_5PLUS, ind
    # the Conteo 2005 keeps the legacy residence cells (no LUGAR_RES_5A)
    assert p05["P_F_OE2000"] == {"EDAD_CAT": d._AGES_5PLUS, "ENT_PAIS_RES_CAT": ["OtraEnt"],
                                 "SEXO": ["Mujer"]}
    # 6n: the legacy cells on 2000's and 2005's own items; 2000's VP_CCUART is not one
    # bedroom (one room without the exclusive kitchen), so 2000 has no VPH_1DOR
    assert {"P5_HLI", "P5_HLI_NHE", "P5_HLI_HE", "P15A17A", "P15YM_AN"} <= set(p00)
    assert p00["P15YM_AN"]["ALFABET"] == ["No sabe leer y escribir"]
    assert {"P5_HLI", "P5_HLI_HE", "P6A11_NOA", "P12A14NOA"} <= set(p05)
    assert len(p00) == 70 and len(p05) == 87       # 6o: own; 6t: +2; 6v: POBHOG; 6w: +2, +1;
    #                                                7c: 2000's income in minimum wages, +5
    assert p00["P2_5SM"] == {"EDAD_CAT": d._AGES_12PLUS, "CONACT_CAT": ["Trabaja"],
                             "INGTRMEN_SM": ["Más de 2 y menos de 3 s.m.", "De 3 hasta 5 s.m."]}
    assert {p00[i]["INGTRMEN_SM"][0] for i in ("P_1SM", "P1_2SM", "P6_10SM", "P10_SM")} == {
        "Menos de 1 s.m.", "De 1 hasta 2 s.m.", "Más de 5 hasta 10 s.m.", "Más de 10 s.m."}
    # 6w: 2000's media superior and superior apart (its superior holds the posgrado)
    assert p00["P18_CMEDSU"] == {"EDAD_CAT": d._AGES_18PLUS, "EDUC_INEGI_DET": ["Media_superior"]}
    assert p00["P18_CSUPER"]["EDUC_INEGI_DET"] == ["Superior", "Posgrado"]
    assert p00["POCUSECP"] == {"EDAD_CAT": d._AGES_12PLUS, "CONACT_CAT": ["Trabaja"],
                               "SECTOR": ["Primario"]}
    assert p00["P5_SINRELI"]["RELIGION_CAT"][-1] == "Sin religión / Sin adscripción religiosa"
    assert p05["P_15A59_M"] == {"EDAD_CAT": ["15-17", "18-24", "25-49", "50-59"],
                                "SEXO": ["Hombre"]}
    assert len(mxcensus.cpv_constraints("viviendas", 2000)) == 36       # 6s: + HOGJEF_F/M
    v00 = mxcensus.cpv_constraints("viviendas", 2000)                  # 7f: + VIVPAR_HAB
    assert {"TOTHOG", "VPH_1CUART", "VPH_DRENAJ", "VPH_PISODT", "VPH_C_ELEC",
            "VPH_AGUADV", "VP_SERSAN", "VPH_C_SERV", "VPH_NDEAED", "VPH_SNBIEN",
            "VPH_REFRI", "VPH_LAVAD", "VPH_AUTOM", "VPH_RADIO", "VPH_TV", "VPH_TELEF"} <= set(v00)
    assert "VPH_1DOR" not in v00
    # 7f: every class (its locales carry the items), once per dwelling; the households'
    # indicators on every row
    assert v00["VP_PROPIA"] == {"TENVIV": ["Sí"], "PRIMER_HOGAR": ["Sí"]}          # 6o
    assert v00["VIVPAR_HAB"] == {"PRIMER_HOGAR": ["Sí"]}
    assert v00["TOTHOG"] == {"CLAVIVP_CAT": ["Vivienda", "Otro"]}
    assert all(("PRIMER_HOGAR" in cells) == (ind not in d._HOUSEHOLD_INDICATORS)
               and cells.get("CLAVIVP_CAT") != ["Vivienda"] for ind, cells in v00.items())
    assert v00["VP_SERSAN"]["USOEXC"] == ["Sí es exclusivo"]          # 2000: exclusive service
    v05 = mxcensus.cpv_constraints("viviendas", 2005)                 # 6v: households apart
    assert len(v05) == 20 and {"VPH_PISOTI", "VPH_NOAG", "VPH_PC", "VPH_1DOR"} <= set(v05)
    assert not {"TOTHOG", "HOGJEF_F", "HOGJEF_M"} & set(v05)
    assert v05["VPH_SNBIEN"] == {"CLAVIVP_CAT": ["Vivienda"],
                                 "NODISBIE": ["No dispone de ninguno de los bienes captados."]}
    p90, p95 = (mxcensus.cpv_constraints("personas", p) for p in (1990, 1995))       # 6j
    assert set(p90) == {"POBTOT", "OCUPVIVPAR", "POBFEM", "POBMAS", "P5_HLI_HE", "P5_HLI_NHE",
                        "P15YM_AN",
                        "P15YM_SE", "P15PRI_IN", "P15PRI_CO", "PEA", "PE_INAC", "POCUPADA",
                        # 6o: its own
                        "P6_14SLEE", "P6_14NLEE", "P15_ALFAB", "P5_ASIESC", "P_5_NOAE",
                        "P6_14AESC", "P6A14NOA", "P15_POSPRI", "POCUSECP", "POCUSECS",
                        "POCUSECT"}
    assert p90["P5_HLI_NHE"]["HAB_ESP"] == ["NO"] and p90["PEA"] == per["PEA"]
    assert set(p95) == {"POBTOT", "POBFEM", "POBMAS", "P_5YMAS", "P_15YMAS", "P15YM_AN",
                        "P_6A14_AN", "P6_14SLEE", "P6_14NLEE", "P15_ALFAB",           # 6o
                        "OCUPVIVPAR"}                         # 7f: the private dwellings'
    assert p90["OCUPVIVPAR"] == p95["OCUPVIVPAR"] == {}
    assert p95["POBFEM"] == {"P3_5": ["Mujer"]}            # 1995 names sex P3_5: no SEXO cell
    v90 = mxcensus.cpv_constraints("viviendas", 1990)
    assert set(v90) == {"VPH_1CUART", "VPH_DRENAJ", "VPH_PISODT", "VPH_C_ELEC", "VPH_AGUADV",
                        "VP_PARDES", "VP_TECDES", "VP_2CUAR", "VP_PROPIA",           # 6o
                        "VIVPAR_HAB"}                                                # 7f
    assert v90["VPH_1CUART"] == {"TOTCUART_CAT": ["1"]} and v90["VIVPAR_HAB"] == {}  # 7f: móviles
    assert set(mxcensus.cpv_constraints("viviendas", 1995)) == {
        "VPH_C_ELEC", "VPH_AGUADV", "VPH_DRENAJ", "VIVPAR_HAB"}
    assert "SEXO" not in d._categories("personas", "1995")
    assert "T_VIV" in d._categories("viviendas", "1990")        # the person file's dictionary
    assert "ANO_CUMP" not in d._categories("viviendas", "1990")  # a person item
    for table, period in [(t, p) for t in ("personas", "viviendas")       # categories exist
                          for p in ("1990", "1995", "2000", "2005", "2010", "2020", "2025")] \
            + [("hogares", "2005")]:
        cats = d._categories(table, period)
        for cells in mxcensus.cpv_constraints(table, period).values():
            assert all(set(c) <= set(cats[v]) for v, c in cells.items())
            assert "EDUC" not in cells                             # 6k: EDUC_INEGI instead


# 7e: the published shares of an unpublished base and the averages, as ratio constraints
_RATIO_SIZES = {("personas", "2025"): 15, ("viviendas", "2025"): 2, ("personas", "2020"): 4,
                ("viviendas", "2020"): 2, ("personas", "2010"): 4, ("viviendas", "2010"): 2,
                ("viviendas", "2000"): 2, ("viviendas", "1990"): 2,                  # 7f
                ("viviendas", "1995"): 1}
_MODES_TRAB = {f"PCN_POCUP_{m}" for m in ("CAM", "BICI", "MET", "TROL", "TPER", "TAXI", "MOTO",
                                          "AUTO", "OMED")}


def test_cpv_ratio_constraints_per_edition():
    from mxcensus.cpv_aggregates import _PERCENT_BASES

    keys = {"numerator", "numerator_value", "denominator", "denominator_value", "known", "scale"}
    for table in ("personas", "viviendas"):
        for period in ("1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025"):
            ratios = mxcensus.cpv_ratio_constraints(table, period)
            assert len(ratios) == _RATIO_SIZES.get((table, period), 0), (table, period)
            assert not set(ratios) & set(mxcensus.cpv_constraints(table, period))
            published = d._aggregate_indicators(period)
            for ind, spec in ratios.items():
                assert set(spec) == keys and ind in published, ind
                assert spec["scale"] == (100 if ind.startswith("PCN_") else 1), ind
    assert mxcensus.cpv_ratio_constraints("hogares", 2005) == {}
    with pytest.raises(ValueError, match="only the Conteo 2005"):
        mxcensus.cpv_ratio_constraints("hogares", 2020)
    with pytest.raises(ValueError, match="ratio constraints exist"):
        mxcensus.cpv_ratio_constraints("migrantes", 2020)
    # the EIC 2025: the 11 percentages without a count (7a) and the averages
    p25 = mxcensus.cpv_ratio_constraints("personas", 2025)
    assert set(p25) == {"PCN_HF", "PCN_P3NHLI_CLI", *_MODES_TRAB, "PROM_HNV", "GRAPROES",
                        "GRAPROES_F", "GRAPROES_M"}
    assert not set(p25) & set(_PERCENT_BASES)
    assert p25["PCN_POCUP_TPER"] == {
        "numerator": {**d._EMPLOYED_CELLS, "MED_TRASLADO_TRAB_Transporte de personal": [1]},
        "numerator_value": None, "denominator": d._COMMUTERS, "denominator_value": None,
        "known": (), "scale": 100}
    assert p25["PCN_POCUP_MET"]["numerator"]["MED_TRASLADO_TRAB_METRO_T"] == [1]
    assert len(d._COMMUTERS["TIE_TRASLADO_TRAB"]) == 6          # «no es posible determinarlo»
    assert p25["PCN_P3NHLI_CLI"]["denominator"] == {"EDAD_CAT": d._AGES_3PLUS, "HLENGUA": ["No"]}
    assert p25["PCN_HF"] == d._ratio(d._WOMEN_12PLUS, value="HIJOS_FALLECIDOS",
                                     base_value="HIJOS_NAC_VIVOS",
                                     known=("HIJOS_NAC_VIVOS", "HIJOS_FALLECIDOS"), scale=100)
    assert p25["GRAPROES_F"] == d._ratio({"EDAD_CAT": d._AGES_15PLUS, "SEXO": ["Mujer"]},
                                         value="ESCOACUM", known=("ESCOACUM",))
    v25 = mxcensus.cpv_ratio_constraints("viviendas", 2025)
    assert v25["PROM_OCUP"] == d._ratio(d._VIVIENDA, value="NUMPERS")        # VIVPARHAB_C
    # the ITER: every dwelling; Censo 2010 counts the occupants of those without rooms too
    for period, known in (("2010", ()), ("2020", ("TOTCUART",))):
        rooms = mxcensus.cpv_ratio_constraints("viviendas", period)["PRO_OCUP_C"]
        assert rooms == d._ratio({}, value="NUMPERS", base_value="TOTCUART", known=known)
    assert mxcensus.cpv_ratio_constraints("personas", 2010)["PROM_HNV"]["known"] == ("NUMHIJ",)
    # 7f: CGPV 2000 once per dwelling, its rooms without an exclusive kitchen nobody sleeps
    # in; 1990 every occupant over the known rooms (2010's rule); 1995 its persons counted
    v00 = mxcensus.cpv_ratio_constraints("viviendas", 2000)
    assert v00 == {"PRO_OCUP_C": d._ratio({"PRIMER_HOGAR": ["Sí"]}, value="NUMPERS",
                                          base_value="TOTCUART_INEGI", known=("TOTCUART_INEGI",)),
                   "PROM_OCUP": d._ratio({"PRIMER_HOGAR": ["Sí"]}, value="NUMPERS")}
    assert mxcensus.cpv_ratio_constraints("viviendas", 1990)["PRO_OCUP_C"] == d._ratio(
        {}, value="NUM_PERS", base_value="T_CUARTOS")
    assert mxcensus.cpv_ratio_constraints("viviendas", 1995) == {
        "PROM_OCUP": d._ratio({}, value="NUMPERS")}
    for table, period in _RATIO_SIZES:                       # categories and values exist
        cats, numeric = d._categories(table, period), d._numeric_columns(table, period)
        for spec in d._RATIOS[table, period].values():
            for side in ("numerator", "denominator"):
                assert all(set(c) <= set(cats[v]) for v, c in spec[side].items())
            assert {spec["numerator_value"], spec["denominator_value"], *spec["known"]} - {
                None} <= numeric


def test_cpv_ratio_terms():
    """N and D per record: 1 or the value inside the side's cells, 0 outside; a record
    with a ``known`` column missing counts on neither side, another missing value as 0."""
    women = pd.Categorical(["Mujer", "Mujer", "Mujer", "Hombre"], categories=["Hombre", "Mujer"])
    df = pd.DataFrame({"SEXO": women, "HNV": pd.array([2, None, 0, 3], dtype="Int64"),
                       "HF": pd.array([1, None, None, None], dtype="Int64")},
                      index=pd.Index(list("abcd"), name="ID"))
    cells = {"SEXO": ["Mujer"]}
    ratios = {"PROM": d._ratio(cells, value="HNV", known=("HNV",)),
              "PCN": d._ratio(cells, value="HF", base_value="HNV", known=("HNV", "HF"), scale=100),
              "RAW": d._ratio(cells, value="HNV", base_value="HF"),
              "ALL": d._ratio({})}
    num, den = mxcensus.cpv_ratio_terms(df, ratios)
    assert list(num.columns) == list(den.columns) == list(ratios)
    assert num.index.equals(df.index) and (num.dtypes == "float64").all()
    assert num.to_dict("list") == {"PROM": [2, 0, 0, 0], "PCN": [1, 0, 0, 0],
                                   "RAW": [2, 0, 0, 0], "ALL": [1, 1, 1, 1]}
    assert den.to_dict("list") == {"PROM": [1, 0, 1, 0], "PCN": [2, 0, 0, 0],
                                   "RAW": [1, 0, 0, 0], "ALL": [1, 1, 1, 1]}
    with pytest.raises(ValueError, match="labels=True"):                 # raw codes
        mxcensus.cpv_ratio_terms(df.assign(SEXO=df["SEXO"].astype(str)), ratios)
    with pytest.raises(ValueError, match="labels=True"):                 # a category missing
        mxcensus.cpv_ratio_terms(df, {"X": d._ratio({"SEXO": ["Otro"]})})
    with pytest.raises(ValueError, match="not numeric"):
        mxcensus.cpv_ratio_terms(df.assign(HNV=df["HNV"].astype(str)), ratios)


def test_cpv_constraint_terms():
    """8i: each record's term of each count constraint — 1 inside every variable's cells at
    once, 0 elsewhere (``{}`` = every record) —, the guide's ``design()``; raw codes, a
    category the frame lacks or a variable it lacks raise."""
    sex = pd.Categorical(["Mujer", "Mujer", "Hombre", None], categories=["Hombre", "Mujer"])
    age = pd.Categorical(["0-2", "12-14", "12-14", "12-14"], categories=["0-2", "12-14"])
    df = pd.DataFrame({"SEXO": sex, "EDAD_CAT": age}, index=pd.Index(list("abcd"), name="ID"))
    cons = {"POBFEM": {"SEXO": ["Mujer"]}, "P_12YMAS_F": {"SEXO": ["Mujer"],
                                                          "EDAD_CAT": ["12-14"]},
            "POBTOT": {}, "BOTH": {"SEXO": ["Mujer", "Hombre"]}}
    terms = mxcensus.cpv_constraint_terms(df, cons)
    assert list(terms.columns) == list(cons) and terms.index.equals(df.index)
    assert (terms.dtypes == "float64").all()
    assert terms.to_dict("list") == {"POBFEM": [1, 1, 0, 0], "P_12YMAS_F": [0, 1, 0, 0],
                                     "POBTOT": [1, 1, 1, 1], "BOTH": [1, 1, 1, 0]}
    assert mxcensus.cpv_constraint_terms(df, {}).shape == (4, 0)
    with pytest.raises(ValueError, match="labels=True"):                 # raw codes
        mxcensus.cpv_constraint_terms(df.assign(SEXO=["3", "3", "1", None]), cons)
    with pytest.raises(ValueError, match="labels=True"):                 # a category missing
        mxcensus.cpv_constraint_terms(df, {"X": {"SEXO": ["Otro"]}})
    with pytest.raises(ValueError, match="derived=True"):                # a variable missing
        mxcensus.cpv_constraint_terms(df, {"X": {"HOG_IND": ["Sí"]}})


def test_published_name():
    """7g: a constraint's key is the column its edition publishes the indicator under: the
    canonical name, or the older edition's column of a pair the crosswalk keeps apart."""
    pub = d._published_name
    assert pub("PNACOE", "2000") == "PNACOENT" and pub("PNACOE", "2010") == "PNACOE"
    assert pub("PRES2015", "2000") == "P5_RES95" and pub("PRESOE15_F", "2005") == "P_F_OE2000"
    assert pub("PRES2015_M", "2010") == "PRES2005_M" and pub("PRES2015", "2020") == "PRES2015"
    assert pub("PCATOLICA", "2000") == "P5_CATOLIC" and pub("VPH_EXCSA", "2000") == "VP_SERSAN"
    assert pub("VPH_AGUADV", "2000") == "VPH_AGUADV"           # renamed (7f): the same
    assert pub("VPH_AGUADV", "2005") == "VPH_AGDV" and pub("PDER_SEGP", "2005") == "P_SEGPOP"
    assert pub("POBTOT", "1990") == "POBTOT"                    # P_TOTAL, renamed
    assert pub("PNACOE", "2025") == "PNACOE" and pub("NO_SUCH", "2000") == "NO_SUCH"


def test_constraint_keys_are_published_columns():
    """7g: every count and ratio constraint is a column of the edition's published
    aggregate — ``load_cpv_iter(period)`` (its harmonized columns: upper case, the
    crosswalk's renames) or the EIC 2025's ``load_cpv_estimaciones(counts=True)``."""
    from mxcensus._resources import cpv_schema_map
    from mxcensus.cpv import _renames

    groups = cpv_schema_map()["iter"]["groups"]
    for period in ("1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025"):
        if period == "2025":
            columns = d._aggregate_indicators(period)
        else:
            renames = _renames("iter", (period,))
            columns = {renames.get(c.upper(), c.upper()) for g in groups.values()
                       if period in [str(x) for x in g["periods"]] for c in g["columns"]}
        for table in ("personas", "viviendas", "hogares"):
            if table == "hogares" and period != "2005":
                continue
            keys = [*mxcensus.cpv_constraints(table, period),
                    *mxcensus.cpv_ratio_constraints(table, period)]
            assert set(keys) <= columns, (table, period, set(keys) - columns)
            assert len(keys) == len(set(keys))
    assert not mxcensus.cpv_constraints("personas", 2015)                # neither publishes


# --- real data ------------------------------------------------------------------------------

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


def _legacy_names(frame: pd.DataFrame) -> pd.DataFrame:
    """CPV derived columns under the legacy names, on the legacy integer index."""
    out = frame.rename(columns={v: k for k, v in d.DHSERSAL_RENAMES.items()})
    idx = out.index
    out.index = idx.set_levels([lv.astype("int64") for lv in idx.levels]) \
        if isinstance(idx, pd.MultiIndex) else idx.astype("int64")
    return out.sort_index()


@_REAL_SKIP
@pytest.mark.parametrize("state", [1, 9, 15])
@pytest.mark.parametrize("table", ["personas", "viviendas"])
def test_derived_2020_equals_legacy(local_mirror, table, state):
    """Every derived column of ``load_extended_*`` equals the CPV 2020 one (values and
    dtype; dummies under the neutral DHSERSAL names); the fixed dummy sets add only
    all-zero columns (codes no one in the state reported). All 32 states: STEP_6b.md."""
    legacy_loader, loader = {
        "personas": (mxcensus.load_extended_personas, mxcensus.load_cpv_personas),
        "viviendas": (mxcensus.load_extended_viviendas, mxcensus.load_cpv_viviendas)}[table]
    legacy = legacy_loader(state=state)
    cols = list(d.derived_dtypes(table, "2020"))
    new = _legacy_names(loader(2020, state=state, derived=True, labels=False)[cols])
    assert new.index.equals(legacy.index)
    shared = [c for c in new.columns if c in legacy.columns]
    assert len(shared) >= {"personas": 50, "viviendas": 14}[table]
    for col in shared:
        assert new[col].astype(object).equals(legacy[col].astype(object)), col
        if not col.startswith(("DHSERSAL_", "MED_TRASLADO_", "FINANCIAMIENTO_")):
            assert new[col].dtype == legacy[col].dtype, col
    summary = {"DHSERSAL_ISSSTE_T"} & set(new.columns)          # 6y: federal or state
    for col in summary:
        either = legacy["DHSERSAL_ISSSTE"].astype(int) | legacy["DHSERSAL_ISSSTE_E"].astype(int)
        assert new[col].astype(int).equals(either), col
    for prefix in ("MED_TRASLADO_ESC", "MED_TRASLADO_TRAB"):    # 7a: the grouped modes
        if table != "personas":
            break
        labels = d._legacy_map("personas", f"{prefix}1")
        for name, group in d._TRASLADO_T.items():
            either = pd.concat([legacy[f"{prefix}_{labels[c]}"].astype(int)    # unreported
                                if f"{prefix}_{labels[c]}" in legacy        # codes: 0
                                else pd.Series(0, index=legacy.index) for c in group],
                               axis=1).max(axis=1)
            assert new[f"{prefix}_{name}"].astype(int).equals(either), name
            summary.add(f"{prefix}_{name}")
    dummies = set(new.columns) - set(shared) - set(d._DTYPES) - set(d._DTYPE_LIKE) - summary
    for col in dummies:                                         # unobserved codes' dummies
        assert (new[col].astype(int) == 0).all(), col


@_REAL_SKIP
@pytest.mark.parametrize("period", ["1990", "1995", "2000", "2005", "2010", "2015", "2020",
                                    "2025"])
def test_derived_editions_real(local_mirror, period):
    """``derived=True`` on each edition: the declared columns, their dtypes, no missing
    value; the same columns with or without labels and harmonization."""
    _, per, _ = mxcensus.load_cpv_survey(period, state=1, derived=True)
    viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True)
    for table, frame in (("personas", per), ("viviendas", viv)):
        dtypes = d.derived_dtypes(table, period)
        assert dtypes and set(dtypes) <= set(frame.columns)
        for col, dtype in dtypes.items():                 # 7f: a number may be missing
            assert frame[col].dtype == dtype, col
            assert frame[col].notna().all() or not isinstance(dtype, pd.CategoricalDtype), col
    raw = mxcensus.load_cpv_personas(period, state=1, derived=True, labels=False,
                                     harmonize=True)               # other keys: compare counts
    for col in d.derived_dtypes("personas", period):
        assert raw[col].value_counts().equals(per[col].value_counts()), col


@_REAL_SKIP
@pytest.mark.parametrize("period", ["1990", "1995", "2000", "2005", "2010", "2020", "2025"])
def test_crosstab_per_edition(local_mirror, period):
    """One table per edition: the constraints build ``get_tables_dict`` against the derived
    frame's dtypes, and the age × sex table fills (1990: age × activity, 1995: age — their
    ITER splits no age group by sex)."""
    per = mxcensus.load_cpv_personas(period, state=1, derived=True)
    tables = mxcensus.get_tables_dict(mxcensus.cpv_constraints("personas", period), per.dtypes)
    key = frozenset({"EDAD_CAT", *{"1990": ["CONACT_CAT"], "1995": []}.get(period, ["SEXO"])})
    assert key in tables
    table = mxcensus.create_cont_table(tables[key])
    assert set(table.columns) <= set(per["EDAD_CAT"].cat.categories) and len(table)
    if period == "2010":                       # 2010's own limitation cells
        for var in ("LIM_ACTIVIDAD", "DISCAP2"):
            assert len(mxcensus.create_cont_table(tables[frozenset({var})]).columns)
    if period != "2025":                       # 6n: 2000/2005/2010 dwellings too
        viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True)
        vt = mxcensus.get_tables_dict(mxcensus.cpv_constraints("viviendas", period), viv.dtypes)
        assert vt
        if period in ("2000", "2005", "2010"):  # the services table (class × 3 items) builds
            key = next(k for k in vt if len(k) == 4 and "DRENAJE_CAT" in k)
            assert mxcensus.create_cont_table(vt[key]).notna().to_numpy().any()
    if period == "2005":                       # 6v: its households (class × head's sex)
        hog = mxcensus.load_cpv_hogares(period, state=1, derived=True)
        ht = mxcensus.get_tables_dict(mxcensus.cpv_constraints("hogares", period), hog.dtypes)
        table = mxcensus.create_cont_table(ht[frozenset({"CLAVIVP_CAT", "JEFE_SEXO"})])
        assert set(table.index.get_level_values("Indicator")) == {"HOGJEF_F", "HOGJEF_M"}


# INEGI's tabulados, row «Total»: the population and its percentages by birthplace (this
# entity, another, abroad — the US plus other countries —, not specified) or by residence
# five years earlier (same entity, another entity or country, not specified; ages 5–130).
# EIC 2015 «04_migracion.xls» sheets 02/05 (estimator «Valor», 6 decimals); Censo 2010
# ampliado «04_02A_ESTATAL.xls» («Parámetro»). Last: Σ FACTOR of the persons whose entity
# is not specified. All 32 states and the nation: STEP_6e.md.
_TABULADOS = {
    ("2015", 5, "ENT_PAIS_NAC_CAT"): (2_954_915, (86.274224, 12.513456, 0.659816 + 0.132051,
                                                  0.420452), 14),
    ("2015", 5, "ENT_PAIS_RES_CAT"): (2_678_545, (96.43773, 2.793084, 0.769186), 0),
    ("2010", 2, "ENT_PAIS_RES_CAT"): (2_831_647, (91.4524303347133, 7.98701250544294,
                                                  0.56055715984372), 143),
}
# «Entity not specified» (raw item and code): OtraEnt in the derived columns (the legacy
# 2020 rule for 997, kept in every edition), «No especificado» in INEGI's tabulados.
_UNSPECIFIED_ENTITY = {("2015", "ENT_PAIS_NAC_CAT"): ("ENT_PAIS_NAC", "997"),
                       ("2015", "ENT_PAIS_RES_CAT"): ("ENT_PAIS_RES10", "997"),
                       ("2010", "ENT_PAIS_RES_CAT"): ("RES05EDO_C", "999")}


@_REAL_SKIP
@pytest.mark.parametrize("period,state,col", sorted(_TABULADOS))
def test_migration_equals_tabulados(local_mirror, period, state, col):
    """Σ ``FACTOR`` by birthplace / residence five years earlier equals INEGI's tabulado,
    once the persons whose entity is not specified count as «No especificado»."""
    per = mxcensus.load_cpv_personas(period, state=state, derived=True, labels=False)
    item, code = _UNSPECIFIED_ENTITY[period, col]
    cat = per[col].astype(object).mask(per[item].eq(code), "No especificado")
    if col == "ENT_PAIS_RES_CAT":
        keep = pd.to_numeric(per["EDAD"]).between(5, 130)
        per, cat = per[keep], cat[keep]
        groups = (["EstaEnt"], ["OtraEnt", "OtroPais"], ["No especificado"])
    else:
        groups = (["EstaEnt"], ["OtraEnt"], ["OtroPais"], ["No especificado"])
    total, published, unspecified = _TABULADOS[period, state, col]
    assert round(per["FACTOR"].sum()) == total
    shares = [100 * per.loc[cat.isin(g), "FACTOR"].sum() / total for g in groups]
    assert shares == pytest.approx(published, abs=1.5e-6 if period == "2015" else 1e-9)
    assert per.loc[per[item].eq(code), "FACTOR"].sum() == unspecified
    assert (per.loc[per[item].eq(code), col] == "OtraEnt").all()


# 7b: INEGI's tabulados, «01 Aguascalientes», both sexes: the universe (the 5+; the
# students 3+; the employed 12+) and its percentages — the same entity; as % of it, the same
# municipality, another, not specified; another entity or country; not specified. Censo
# 2010 ampliado «04_02A»/«08_15A_ESTATAL.xls» («Parámetro»); EIC 2015 «04_migracion.xls» 05,
# «10_movilidad_cotidiana.xls» 01/04 («Valor», 6 decimals); Censo 2020 ampliado
# «cpv2020_a_eum_10_movilidad_cotidiana.xlsx» 02/08. All 32 states, both sexes and the
# nation: scripts/check_cpv_tabulados.py (STEP_7b.md).
_PLACES_01 = {
    ("2010", "LUGAR_RES_5A"): (1_057_013, (93.6432191467844, 98.4209266119834,
                                           1.21698771798133, 0.36208567003528,
                                           6.07627342331646, 0.28050742989915)),
    ("2010", "LUGAR_TRAB"): (447_267, (96.5942043566818, 91.4983542961896, 6.69553785118764,
                                       1.80610785262271, 2.46318194724851, 0.94261369606968)),
    ("2015", "LUGAR_RES_5A"): (1_184_416, (95.233178, 98.164026, 1.821523, 0.014451,
                                           4.484066, 0.282755)),
    ("2015", "LUGAR_ASI"): (398_978, (97.1128733915153, 95.5306238853659, 4.43969555488451,
                                      0.0296805597495477, 0.48223210302322, 2.40489450546145)),
    ("2015", "LUGAR_TRAB"): (519_719, (97.4051362370819, 88.7293005394749, 11.1865484865664,
                                       0.08415097395863, 1.96952583992503, 0.625337922993)),
    ("2020", "LUGAR_ASI"): (410_833, (99.601298, 95.405613, 4.593653, 0.000733, 0.362434,
                                      0.036268)),
    ("2020", "LUGAR_TRAB"): (629_560, (98.415242, 89.949046, 10.032716, 0.018238, 1.571891,
                                       0.012866)),
}
_YOUNGEST = {"LUGAR_RES_5A": 5, "LUGAR_ASI": 3, "LUGAR_TRAB": 12}


@_REAL_SKIP
@pytest.mark.parametrize("period,col", sorted(_PLACES_01))
def test_places_equal_tabulados(local_mirror, period, col):
    """The places by municipality (7b: Censo 2010's residence in 2005 and work from its
    split items, the EIC 2015's residence in 2010, school and work, Censo 2020's school and
    work) reproduce INEGI's tabulados; the persons of unspecified age, who answer the items,
    are left out as there."""
    per = mxcensus.load_cpv_personas(period, state=1, derived=True, labels=False)
    place = per[col].astype(object)
    keep = pd.to_numeric(per["EDAD"]).between(_YOUNGEST[col], 130) & place.ne("Blanco por pase")
    w, place = per.loc[keep, "FACTOR"], place[keep]
    total, published = _PLACES_01[period, col]
    assert round(w.sum()) == total
    own_cats = ["Mismo municipio", "Otro municipio", "Municipio no especificado"]
    own = w[place.isin(own_cats)].sum()
    shares = [100 * own / total, *(100 * w[place.eq(c)].sum() / own for c in own_cats),
              100 * w[place.isin(["Otra entidad", "Estados Unidos", "Otro país"])].sum() / total,
              100 * w[place.eq("No especificado")].sum() / total]
    assert shares == pytest.approx(published, abs=1e-9 if period == "2010" else 1.5e-6)


# EIC 2015 «14_vivienda.xls» sheet 18 («Valor», «01 Aguascalientes»): the owned dwellings
# bought or built, and their percentages by financing in the order of 2015's codes
# (INFONAVIT/FOVISSSTE/PEMEX, FONHAPO, banks, other institution, a relative or another
# person, own resources, not specified). All 32 states and the nation: STEP_6e.md.
_FINANCIAMIENTO_2015_01 = (207_736, (35.2485847421727, 0.32733854507644, 7.12057611583933,
                                     5.56908768821966, 1.21644779912966, 50.2801632841683,
                                     0.23780182539376))


@_REAL_SKIP
def test_financing_2015_equals_tabulado(local_mirror):
    """The EIC 2015 financing dummies (one item, one answer) reproduce INEGI's tabulado."""
    viv = mxcensus.load_cpv_viviendas(2015, state=1, derived=True)
    labels = [v for k, v in d._financiamiento_2015().items() if k != d._BLANK]
    counts = [viv.loc[viv[f"FINANCIAMIENTO_{v}"] == 1, "FACTOR"].sum() for v in labels]
    total, published = _FINANCIAMIENTO_2015_01
    assert sum(counts) == total
    assert [100 * c / total for c in counts] == pytest.approx(published, abs=1e-9)
    dummies = viv[[f"FINANCIAMIENTO_{v}" for v in d._financiamiento_2015().values()]]
    assert (dummies.astype(int).sum(axis=1) == 1).all()             # exactly one per dwelling


# INEGI's tabulados, row «Total»: the employed aged 12–130 by occupational division (SINCO
# 2011 / CUO 2010 first digit, 1–9, then not specified) and by grouped SCIAN sector
# (agriculture; mining, manufacturing, utilities; construction; trade; services; not
# specified). EIC 2015 «08_caracteristicas_economicas.xls» sheets 06/07 («Valor»); Censo
# 2010 ampliado «08_02A_ESTATAL.xls»/«08_03A_ESTATAL.xls» («Parámetro»). All 32 states,
# both sexes and the nation: STEP_6f.md.
_EMPLOYED = {
    ("2015", 1): ((17_737, 106_317, 34_706, 76_476, 46_240, 21_391, 59_901, 79_558, 74_660,
                   2_733), (27_231, 122_717, 41_258, 94_852, 229_978, 3_683)),
    ("2010", 3): ((20_050, 53_098, 23_149, 41_193, 34_678, 14_175, 34_447, 13_161, 50_540,
                   2_794), (26_361, 22_555, 27_655, 54_657, 153_251, 2_806)),
}
_SECTORS = ({11}, {21, 22, 31, 32, 33}, {23}, {43, 46},
            {48, 49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 93}, {99})


@_REAL_SKIP
@pytest.mark.parametrize("period,state", sorted(_EMPLOYED))
def test_occupation_activity_equal_tabulados(local_mirror, period, state):
    """The coarse occupation and activity reproduce INEGI's tabulados (SINCO's group 59,
    gone in SINCO 2019, stays in division 5 as 52)."""
    per = mxcensus.load_cpv_personas(period, state=state, derived=True, labels=False)
    emp = per[per["OCUPACION_C_COARSE"].ne("Blanco por pase")
              & pd.to_numeric(per["EDAD"]).between(12, 130)]
    code = {name: emp[name].astype(str).map(
                {v: k for k, v in d._legacy_map("personas", name).items()}).astype(int)
            for name in ("OCUPACION_C_COARSE", "ACTIVIDADES_C_COARSE")}
    occ = code["OCUPACION_C_COARSE"]
    division = occ.floordiv(10).where(occ.ne(99), 10)
    divisions = tuple(round(emp.loc[division.eq(i), "FACTOR"].sum()) for i in range(1, 11))
    sectors = tuple(round(emp.loc[code["ACTIVIDADES_C_COARSE"].isin(g), "FACTOR"].sum())
                    for g in _SECTORS)
    assert (divisions, sectors) == _EMPLOYED[period, state]


@_REAL_SKIP
@pytest.mark.parametrize("table", ["personas", "viviendas"])
def test_eic2025_constraints_equal_estimates(local_mirror, table):
    """EIC 2025, state 01 and its municipalities: Σ ``FACTOR`` over each constraint's cells
    equals the published count exactly (the factors are calibrated to them); for a count
    behind a percentage (6y, ``load_cpv_estimaciones(counts=True)``) the share of its base's
    cells is the published percentage within its rounding. ``PCON_DISC``/``PCON_LIMI``/
    ``PSIND_LIM`` through INEGI's flags. All 32 states, 2,478 municipalities and the
    localities of 50,000+: STEP_6b.md, STEP_6g.md, STEP_6y.md, STEP_6z.md, STEP_7a.md."""
    from mxcensus.cpv_aggregates import _PERCENT_BASES, _base_parts, _count_name
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(2025, state=1, derived=True)
    est = mxcensus.load_cpv_estimaciones(survey_path=_MIRROR / "cpv_estimaciones_2025.parquet",
                                         nivel=["estatal", "municipal"], state=1,
                                         counts=True).droplevel([0, 2])
    cons = mxcensus.cpv_constraints(table, 2025)
    # 7a: the disabled of specified age, the true base of the disability by age (not
    # published: those counts take PCON_DISC's)
    base_cells = {"_DISC_EDADESP": {"DISCAPACIDAD": ["Sí"], "EDAD_QUIN": d._QUIN}} \
        if table == "personas" else {}
    # 8i: each record's 0/1 term of each constraint
    terms = mxcensus.cpv_constraint_terms(frame, {**cons, **base_cells})
    by = terms.mul(frame["FACTOR"].astype(float), axis=0).groupby(
        frame["CVE_MUN"].astype(str).to_numpy()).sum()
    got = pd.concat([by, by.sum().to_frame("000").T]).reindex(est.index)
    pct = {_count_name(p): p for p in _PERCENT_BASES}
    by_age = {f"PCON_DISC{a}" for a in ("0A14", "15A29", "30A59", "60YM")}
    for ind in cons:
        if ind in pct:
            pub = est[pct[ind]].astype(float).dropna()
            # 6z: HOG_MEN_ALIM, published, no cell; 7a: a base of several counts
            base = sum(got[b] if b in got else est[b].astype(float)
                       for b in _base_parts(pct[ind]))
            share = 100 * got[ind] / (got["_DISC_EDADESP"] if ind in by_age else base)
            assert (share[pub.index] - pub).abs().max() <= 0.005 + 1e-9, ind
            assert est[ind].notna().all(), ind
        else:
            pub = est[ind].astype(float).dropna()
            assert got.loc[pub.index, ind].round().eq(pub).all(), ind
    assert len(est) == 12
    assert len(cons) == {"personas": 214, "viviendas": 93}[table]   # 6t: PHOGJEF_F/M; 6v:
    #  POBHOG; 6w: PHOG_IND; 6x: HOG_IND; 6y: the percentages (29/4 before); 6z: 2 + 61 more;
    #  7a: 116 percentages + PUSU_SS, PHOG_AFRO (persons), HOG_AFRO (dwellings)


def _ratios_by(frame: pd.DataFrame, ratios: dict, geo: pd.Series) -> pd.DataFrame:
    """scale × Σ w·N / Σ w·D of each ratio constraint per ``geo`` value (and ``"000"``, the
    frame's total)."""
    num, den = mxcensus.cpv_ratio_terms(frame, ratios)
    w = frame["FACTOR"].astype(float)

    def by(terms):
        s = terms.mul(w, axis=0).groupby(geo.to_numpy()).sum()
        return pd.concat([s, s.sum().to_frame("000").T])

    return by(num) / by(den) * pd.Series({ind: r["scale"] for ind, r in ratios.items()})


@_REAL_SKIP
@pytest.mark.parametrize("table", ["personas", "viviendas"])
def test_eic2025_ratio_constraints_equal_estimates(local_mirror, table):
    """7e: EIC 2025, state 01 and its municipalities: each ratio constraint's scale ×
    Σ w·N / Σ w·D is the published share or average within its rounding (two decimals).
    All 32 states, 2,478 municipalities, the localities of 50,000+ and the state
    remainders (2,769 geographies; PROM_OCUP 2,776): STEP_7e.md."""
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(2025, state=1, derived=True)
    est = mxcensus.load_cpv_estimaciones(survey_path=_MIRROR / "cpv_estimaciones_2025.parquet",
                                         nivel=["estatal", "municipal"], state=1).droplevel([0, 2])
    ratios = mxcensus.cpv_ratio_constraints(table, 2025)
    got = _ratios_by(frame, ratios, frame["CVE_MUN"].astype(str)).reindex(est.index)
    pub = est[list(ratios)].astype(float)
    assert len(ratios) == {"personas": 15, "viviendas": 2}[table] and pub.notna().all().all()
    assert (got - pub).abs().max().max() <= 0.005 + 1e-9, (got - pub).abs().max()


@_REAL_SKIP
@pytest.mark.parametrize("period", ["2010", "2020"])
def test_census_ratio_constraints_equal_iter(local_mirror, period):
    """7e: Censo 2010/2020's ITER averages on their samples, in Sonora's municipalities the
    sample enumerated completely (``FACTOR`` 1 for everyone) where the population in
    households and the averages' age groups equal the ITER's: exact to the rounding. All 32
    states (2020: 135–184 municipalities, 2010: 343–364; elsewhere the sample's band):
    STEP_7e.md."""
    per = mxcensus.load_cpv_personas(period, state=26, derived=True)
    mun = per["MUN"].astype(str).str.zfill(3).to_numpy()
    age, sex = per["EDAD_CAT"], per["SEXO"]
    a15 = age.isin(d._AGES_15PLUS)
    counts = pd.DataFrame({"POBHOG": True, "P_15YMAS": a15, "P_15YMAS_F": a15 & sex.eq("Mujer"),
                           "P_15YMAS_M": a15 & sex.eq("Hombre"),
                           "P_12YMAS_F": age.isin(d._AGES_12PLUS) & sex.eq("Mujer")},
                          index=per.index).astype(int).groupby(mun).sum()
    w = per["FACTOR"].groupby(mun)
    full = w.min().eq(1) & w.max().eq(1)
    it = mxcensus.load_cpv_iter(period, state=26, nivel="municipal").reset_index()
    it = it.set_index(it["CVE_MUN"].astype(str)).astype({c: float for c in counts})
    same = counts.index[full & counts.eq(it[counts.columns].reindex(counts.index)).all(axis=1)]
    assert len(same) == {"2010": 31, "2020": 5}[period]
    viv = mxcensus.load_cpv_viviendas(period, state=26, derived=True)
    for table, frame in (("personas", per), ("viviendas", viv)):
        ratios = mxcensus.cpv_ratio_constraints(table, period)
        got = _ratios_by(frame, ratios, frame["MUN"].astype(str).str.zfill(3)).loc[same]
        diff = (got - it.loc[same, list(ratios)].astype(float)).abs()
        assert diff.max().max() <= 0.005 + 1e-9, diff.max()


# 7g: the cells 7g changed, in Oaxaca's municipalities each sample enumerated completely
# (FACTOR 1 for everyone, the population in households = the ITER's) where every age and
# sex count is the ITER's too: exact. All 32 states (2000: 51 municipalities, 2010: 233,
# 2020: 130; the legacy cells miss in 2–31 of them): STEP_7g.md.
_STRICT_7G = {"2000": 50, "2010": 174, "2020": 107}
_CELLS_7G = {
    "2000": ("PNACOENT", "P5_RES95", "P5_RESO95", "P5_CATOLIC", "P5_NCATOLI", "P5_SINRELI"),
    "2010": ("PNACOE", "PNACOE_F", "PNACOE_M", "PRES2005", "PRESOE05", "PRESOE05_F",
             "PRESOE05_M", "PNCATOLICA", "POTRAS_REL"),
    "2020": ("PNACOE", "PNACOE_F", "PNACOE_M", "PRESOE15", "PRESOE15_F", "PRESOE15_M")}


@_REAL_SKIP
@pytest.mark.parametrize("period", sorted(_CELLS_7G))
def test_7g_cells_equal_iter(local_mirror, period):
    per = mxcensus.load_cpv_personas(period, state=20, derived=True)
    mun = per["MUN"].astype(str).str.zfill(3).to_numpy()
    w = per["FACTOR"].astype(float)
    it = mxcensus.load_cpv_iter(period, state=20, nivel="municipal").reset_index()
    it = it.set_index(it["CVE_MUN"].astype(str))
    cons = mxcensus.cpv_constraints("personas", period)

    def by_mun(cells: dict) -> pd.Series:
        hit = pd.Series(True, index=per.index)
        for var, cats in cells.items():
            hit &= per[var].isin(cats)
        return w.where(hit, 0).groupby(mun).sum()

    g = w.groupby(mun)
    strict = g.min().eq(1) & g.max().eq(1) & g.sum().eq(it["POBHOG"].astype(float))
    for ind, cells in cons.items():
        if cells and set(cells) <= {"EDAD_CAT", "SEXO"}:
            strict &= by_mun(cells).eq(it[ind].astype(float).reindex(strict.index))
    same = strict.index[strict]
    assert len(same) == _STRICT_7G[period]
    for ind in _CELLS_7G[period]:
        assert by_mun(cons[ind]).loc[same].eq(it.loc[same, ind].astype(float)).all(), ind
    if period == "2010":                  # RELIGION_CAT (2020's grouping) misses there
        evangelical = {"RELIGION_CAT": ["Protestante/cristiano evangélico"]}
        assert not by_mun(evangelical).loc[same].eq(it.loc[same, "PNCATOLICA"].astype(float)).all()


def test_derive_primer_hogar_totcuart_inegi():
    """7f: CGPV 2000's first household (``NUMHOG`` 1) and its rooms as its ITER counts them:
    ``TOTCUART`` less an exclusive kitchen nobody sleeps in (``COCINA`` 1 and ``COCDOR``
    4; an unspecified ``COCDOR`` keeps it), missing where ``TOTCUART`` is not specified —
    a number (``Int64``), the first derived column that is no category."""
    v00 = pd.DataFrame({"CLAVIV": ["01"] * 5, "CUADORM": ["01"] * 5,
                        "TOTCUART": ["04", "04", "04", "02", "99"], "DRENAJE": ["1"] * 5,
                        "INGTRHOG": ["000100"] * 5, "SEXO": ["1"] * 5,
                        "COCINA": ["1", "1", "1", "2", "1"], "COCDOR": ["4", "3", "9", "", "4"]},
                       dtype="str")
    out = _derive_dwellings(v00, "2000")
    assert out["TOTCUART_INEGI"].tolist() == [3, 4, 4, 2, pd.NA]
    dtypes = d.derived_dtypes("viviendas", "2000")
    assert dtypes["TOTCUART_INEGI"] == pd.Int64Dtype() and dtypes["PRIMER_HOGAR"] == d._SI_NO
    d.derived_schema("viviendas", "2000").validate(out[list(dtypes)])     # a number may miss
    first = d._primer_hogar(pd.DataFrame({"NUMHOG": [1.0, 2.0, 3.0, np.nan]}))["PRIMER_HOGAR"]
    assert first.tolist()[:3] == ["Sí", "No", "No"] and first.isna().iloc[3]  # derive raises
    # the value columns of the ratio constraints: the dictionaries' numbers (1990's and
    # 2000's occupants, numeric since 7f), the derived ones, the Conteo 1995's person count
    assert {"TOTCUART_INEGI", "NUMPERS", "TOTCUART"} <= d._numeric_columns("viviendas", "2000")
    assert "TOTCUART_INEGI" not in d._categories("viviendas", "2000")
    assert "NUM_PERS" in d._numeric_columns("viviendas", "1990")
    assert d._numeric_columns("viviendas", "1995") >= {"NUMPERS", "P1_7"}


# 7f: CGPV 2000's dwelling indicators once per dwelling (its first household's row) and over
# every class, and its occupants per dwelling and per room (its rooms less an exclusive
# kitchen nobody sleeps in), in Sonora's municipalities its sample enumerated completely
# (FACTOR 1 for everyone, the population in households = the ITER's): the counts to the
# dwelling, the averages to their rounding. All 32 states (186 municipalities): STEP_7f.md.
@_REAL_SKIP
def test_2000_dwellings_equal_iter(local_mirror):
    per = mxcensus.load_cpv_personas(2000, state=26)
    w = per["FACTOR"].groupby(per["MUN"].astype(str).to_numpy())
    it = mxcensus.load_cpv_iter(2000, state=26, nivel="municipal").reset_index()
    it = it.set_index(it["CVE_MUN"].astype(str))
    pop = w.sum()
    full = w.min().eq(1) & w.max().eq(1) & pop.eq(it["POBHOG"].astype(float).reindex(pop.index))
    same = full.index[full]
    assert len(same) == 22
    viv = mxcensus.load_cpv_viviendas(2000, state=26, derived=True)
    first = viv["PRIMER_HOGAR"].eq("Sí")
    assert first.groupby(level="ID_VIV").sum().eq(1).all()        # one first household each
    mun = viv["MUN"].astype(str)
    for ind, cells in mxcensus.cpv_constraints("viviendas", 2000).items():
        hit = pd.Series(True, index=viv.index)
        for var, cats in cells.items():
            hit &= viv[var].isin(cats)
        got = viv["FACTOR"].where(hit, 0).groupby(mun.to_numpy()).sum().reindex(same)
        assert got.eq(it.loc[same, ind].astype(float)).all(), ind         # 7g: VP_SERSAN
    ratios = mxcensus.cpv_ratio_constraints("viviendas", 2000)
    got = _ratios_by(viv, ratios, mun).loc[same]
    diff = (got - it.loc[same, list(ratios)].astype(float)).abs()
    assert diff.max().max() <= 0.005 + 1e-9, diff.max()


# 7f: CGPV 1990's and the Conteo 1995's occupants per dwelling (OCUPVIVPAR / VIVPAR_HAB,
# both published, truncated) and 1990's per room (every occupant over the rooms of the
# dwellings that gave them, the kitchen counted), state 01: 1990's extract holds 10% of the
# dwellings (its sample sits 0.012 over); the Conteo's dwelling weights add up to
# VIVPAR_HAB and its person weights to OCUPVIVPAR, calibrated apart, so its dwelling-
# weighted occupants run 0.19 under. All 32 states: 1990 ≤ 0.073 (PROM_OCUP) and ≤ 0.037,
# 1995 ≤ 0.21 (Chiapas's weights carry its official total, 17% over its ITER): STEP_7f.md.
@_REAL_SKIP
def test_1990_1995_occupants(local_mirror):
    for period, tolerance in (("1990", {"PROM_OCUP": 0.02, "PRO_OCUP_C": 0.02}),
                              ("1995", {"PROM_OCUP": 0.2})):
        viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True, harmonize=True)
        it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
        occupants, dwellings = float(it["OCUPVIVPAR"]), float(it["VIVPAR_HAB"])
        assert float(it["PROM_OCUP"]) == np.floor(100 * occupants / dwellings) / 100
        w = viv["FACTOR"].astype(float) if "FACTOR" in viv else pd.Series(1.0, index=viv.index)
        ratios = mxcensus.cpv_ratio_constraints("viviendas", period)
        assert set(ratios) == set(tolerance)
        num, den = mxcensus.cpv_ratio_terms(viv, ratios)
        got = num.mul(w, axis=0).sum() / den.mul(w, axis=0).sum()
        for ind, tol in tolerance.items():
            assert abs(got[ind] - float(it[ind])) < tol, (period, ind, got[ind])
    assert len(mxcensus.load_cpv_viviendas(1990, state=1)) * 10 == pytest.approx(130599, abs=50)
    per = mxcensus.load_cpv_personas(1995, state=1, harmonize=True)
    viv = mxcensus.load_cpv_viviendas(1995, state=1, harmonize=True)
    assert viv["NUMPERS"].dtype == pd.Int64Dtype()
    assert viv.set_index(viv.index)["NUMPERS"].equals(
        per.groupby(level="ID_VIV").size().reindex(viv.index).astype("Int64").rename("NUMPERS"))
    assert viv["FAC_VIV"].astype(float).sum() == 172443 == float(it["VIVPAR_HAB"])
    assert per["FAC_POB"].astype(float).sum() == 858971 == float(it["OCUPVIVPAR"])


# 6y: INEGI's limitation and disability by activity (a limitation only for the persons with
# one, LIMITACION; a disability with the unknown degree) equal the Censo 2020 ITER to the
# person in the municipalities its sample enumerated completely (FACTOR 1 for everyone) where
# the population in households matches: Sonora's 5; the legacy limitation cells overshoot in
# 29 of their 30. All 32 states (184 municipalities): the limitation in 168–181, the legacy cells
# in 0–4, the disability in 179–183 (STEP_6y.md).
@_REAL_SKIP
def test_disability_by_activity_2020_iter(local_mirror):
    per = mxcensus.load_cpv_personas(2020, state=26, derived=True)
    w, mun = per["FACTOR"], per["MUN"].astype(str)
    full = (w.groupby(mun).transform("min").eq(1) & w.groupby(mun).transform("max").eq(1))
    per, mun = per[full.to_numpy()], mun[full.to_numpy()]
    cons, legacy = mxcensus.cpv_constraints("personas", 2020), mxcensus.constraints_personas()

    def count(cells):
        mask = pd.Series(True, index=per.index)
        for var, cats in cells.items():
            mask &= per[var].isin(cats)
        return mask.groupby(mun).sum()

    inds = [*d._LIMITATIONS, *d._DISABILITIES]
    got = pd.DataFrame({ind: count(cons[ind]) for ind in ["POBHOG", *inds]})
    it = mxcensus.load_cpv_iter(2020, state=26, nivel="municipal").reset_index()
    it = it.set_index(it["CVE_MUN"].astype(str))[["POBHOG", *inds]].astype(float)
    same = got.index[got["POBHOG"].eq(it["POBHOG"].reindex(got.index))]
    assert list(same) == ["007", "008", "015", "050", "067"]
    assert got.loc[same, inds].eq(it.loc[same, inds]).all().all()
    for ind, item in d._LIMITATIONS.items():
        old = count({item: legacy[ind][item]})
        assert (old[same] >= it.loc[same, ind]).all() and old[same].sum() > it.loc[same, ind].sum()


# INEGI's CGPV 2000 ampliado tabulados (C2K*.xls, the sample; percentages with 2 decimals),
# «01 Aguascalientes», total: birthplace (this entity / another or abroad / NE), coverage
# (not covered, covered — % of all —, then IMSS, ISSSTE, PEMEX-Defensa-Marina, other — % of
# the covered —, NE), religion of the 5+ (católica, protestant and evangelical + other
# biblical, other, none, NE), activity of the 12+ (PEA % of all, employed and unemployed %
# of the PEA, inactive, NE). Every state, both sexes and the nation agree within 0.02 points
# outside Chiapas (weights): STEP_6i.md.
_C2K_01 = {
    "MI01": (79.03, 20.51, 0.46),
    "SS04": (43.96, 54.56, 86.54, 13.69, 0.75, 0.22, 1.48),
    "RE02": (96.07, 1.79 + 0.66, 0.1, 0.89, 0.49),
    "EM01": (51.65, 98.88, 1.12, 48.05, 0.3),
}


@_REAL_SKIP
def test_2000_equals_tabulados(local_mirror):
    """CGPV 2000 derived columns reproduce INEGI's ampliado tabulados (state 01)."""
    p = mxcensus.load_cpv_personas(2000, state=1, derived=True, labels=False)
    w = pd.to_numeric(p["FACTOR"])
    age = pd.to_numeric(p["EDAD"], errors="coerce")
    share = lambda m, base: 100 * w[m].sum() / w[base].sum()
    every = w.notna()
    nac = p["ENT_PAIS_NAC_CAT"].astype(str)
    got = {"MI01": (share(nac.eq("EstaEnt"), every), share(nac.isin(["OtraEnt", "OtroPais"]), every),
                    share(nac.eq("No especificado"), every))}
    dummy = {c: p[c].astype(int).eq(1) for c in p if c.startswith("DHSERSAL_")}
    afil, none = dummy["DHSERSAL_AFIL"], dummy["DHSERSAL_No afiliado"]
    got["SS04"] = (share(none, every), share(afil, every),
                   *(share(dummy[c], afil) for c in ("DHSERSAL_IMSS", "DHSERSAL_ISSSTE",
                                                     "DHSERSAL_P_D_M", "DHSERSAL_Otro")),
                   share(~afil & ~none, every))
    five, rel = age.between(5, 130), p["RELIGION_CAT"].astype(str)
    got["RE02"] = tuple(share(five & rel.eq(c), five) for c in (
        "Católica", "Protestante/cristiano evangélico", "Otros credos",
        "Sin religión / Sin adscripción religiosa", "No especificado"))
    twelve, act = age.between(12, 130), p["CONACT_CAT"].astype(str)
    pea = twelve & act.isin(["Trabaja", "Buscó trabajo"])
    got["EM01"] = (share(pea, twelve), share(twelve & act.eq("Trabaja"), pea),
                   share(twelve & act.eq("Buscó trabajo"), pea),
                   share(twelve & act.eq("No trabaja"), twelve),
                   share(twelve & act.eq("No especificado"), twelve))
    for table, published in _C2K_01.items():
        assert got[table] == pytest.approx(published, abs=0.02), table


# 6n: the legacy cells on the CGPV 2000, Conteo 2005 and Censo 2010 samples' own items
# (and every 2010 dwelling cell, which CLAVIVP_CAT enables), and 6o's cells for the ITERs' own
# indicators (2010: the Seguro Popular and 6d's limitation cells), against their ITER, state 01:
# each cell's share of the population or of the dwellings, in points (an indicator the
# crosswalk keeps under the edition's own name is read under it). The sample's dwelling goods
# sit within 1.7 points (2000's boiler, by household rows, 2.6); 2010's bedrooms 2 points
# off (its ampliado questionnaire); the
# persons within 1 point (2005's 15–59, 0.94: the census counts persons without
# characteristics), 2010's Seguro Popular 2.7 (its other affiliation cells sit as far). All 32
# states: STEP_6n.md, STEP_6o.md.
# (period, table) → (cells, largest |Δ| in points)
# 6w: + 2000's P18_CMEDSU/P18_CSUPER (0.26/0.34 points under) and the 2005/2010 PHOG_IND.
# 7c: + 2000's income in minimum wages (P_1SM … P10_SM; P10_SM 0.28 points under).
# 7g: + 2000's PNACOENT/P5_RESO95/P5_CATOLIC, 2005's P_OE2000 (+ _F/_M), 2010's POTRAS_REL.
_CELLS_6N = {("2000", "personas"): (41, 1.25), ("2000", "viviendas"): (31, 2.0),
             ("2005", "personas"): (49, 1.25), ("2005", "viviendas"): (13, 2.5),
             ("2010", "personas"): (13, 3.0), ("2010", "viviendas"): (28, 2.5)}


@_REAL_SKIP
@pytest.mark.parametrize("period,table", sorted(_CELLS_6N))
def test_6n_cells_equal_iter(local_mirror, period, table):
    it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(period, state=1, derived=True)
    base = it["POBTOT" if table == "personas" else "VIVPAR_HAB"]
    w = pd.to_numeric(frame["FACTOR"]) if "FACTOR" in frame else pd.Series(1.0, index=frame.index)
    cons = mxcensus.cpv_constraints(table, period)
    dwellings = pd.Series(True, index=frame.index)        # 7f: 2000's first households
    for var, cats in cons.get("VIVPAR_HAB", {}).items():
        dwellings &= frame[var].isin(cats)
    own = cons if (period, table) == ("2010", "viviendas") else d._EDITION_CELLS[table, period]
    gap = {}
    for ind in own:
        name = d._published_name(ind, period)                    # 7g: the edition's column
        hit = pd.Series(True, index=frame.index)
        for var, cats in cons[name].items():
            hit &= frame[var].isin(cats)
        gap[ind] = 100 * (w[hit].sum() / w[dwellings].sum() - float(it[name]) / float(base))
    cells, tolerance = _CELLS_6N[period, table]
    assert len(gap) == cells
    assert max(abs(v) for v in gap.values()) < tolerance, gap


# 6s: the household head's sex from the person file against the ITER's HOGJEF_F/HOGJEF_M,
# state 01, in points of TOTHOG (households in 2000/2005 — 6v: the Conteo's household
# frame, each household its own head —, dwellings in 2010). Censo 2010's sample sits 1.5
# points under (2020's own sample is up to 1.7 off its ITER); 2000 and 2005 within 0.2. All
# 32 states: STEP_6s.md, STEP_6v.md.
@_REAL_SKIP
@pytest.mark.parametrize("period", ["2000", "2005", "2010"])
def test_jefe_sexo_equals_iter(local_mirror, period):
    it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
    table = "hogares" if period == "2005" else "viviendas"
    loader = mxcensus.load_cpv_hogares if table == "hogares" else mxcensus.load_cpv_viviendas
    viv = loader(period, state=1, derived=True)
    w = viv["FACTOR"] if "FACTOR" in viv else pd.Series(1.0, index=viv.index)
    cons = mxcensus.cpv_constraints(table, period)

    def total(ind):
        hit = pd.Series(True, index=viv.index)
        for var, cats in cons[ind].items():
            hit &= viv[var].isin(cats)
        return w[hit].sum()

    assert total("HOGJEF_F") + total("HOGJEF_M") == pytest.approx(total("TOTHOG"))
    assert total("TOTHOG") == pytest.approx(w.sum())            # every household (6v: 2005's)
    gap = 100 * (total("HOGJEF_F") / total("TOTHOG") - it["HOGJEF_F"] / it["TOTHOG"])
    assert abs(gap) < {"2000": 0.3, "2005": 0.3, "2010": 2.0}[period], gap


# 6v: the population in households (POBHOG, every person of the sample) against the ITER,
# state 01: Censo 2020's weights add up to it (to 2 persons in 1.4 million); CGPV 2000's and
# Censo 2010's sit above it (all 32 states: 2000 0.07–8.9%, 2010 0.06–3.0%) and here below
# POBTOT (three 2010 states exceed it, up to 0.9%; STEP_6v.md). The EIC 2025 publishes
# POBHOG = POBTOT (test_eic2025_constraints_equal_estimates).
@_REAL_SKIP
@pytest.mark.parametrize("period", ["2000", "2010", "2020"])
def test_pobhog_equals_iter(local_mirror, period):
    it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
    per = mxcensus.load_cpv_personas(period, state=1)
    assert mxcensus.cpv_constraints("personas", period)["POBHOG"] == {}
    ratio = per["FACTOR"].sum() / it["POBHOG"]
    if period == "2020":
        assert ratio == pytest.approx(1, abs=1e-5)
    else:
        assert 1 < ratio < {"2000": 1.005, "2010": 1.001}[period]
        assert per["FACTOR"].sum() < it["POBTOT"]


@_REAL_SKIP
def test_head_from_persons_2020(local_mirror):
    """6s's method on Censo 2020, which publishes both: the person whose ``PARENTESCO`` is
    101 (one per dwelling) has the dwelling item ``JEFE_SEXO``'s sex in every dwelling
    (state 01; 01, 07, 09, 15, 19 checked: STEP_6s.md)."""
    per = pd.read_parquet(local_mirror / "cpv_personas_2020_01.parquet",
                          columns=["ID_VIV", "PARENTESCO", "SEXO"])
    viv = pd.read_parquet(local_mirror / "cpv_viviendas_2020_01.parquet",
                          columns=["ID_VIV", "JEFE_SEXO"])
    heads = per[per["PARENTESCO"].eq("101")]
    assert heads["ID_VIV"].is_unique and set(heads["ID_VIV"]) == set(viv["ID_VIV"])
    both = viv.merge(heads, on="ID_VIV", validate="one_to_one")
    assert both["JEFE_SEXO"].equals(both["SEXO"])


# 6t: the population by its household head's sex (HOGJEF_SEXO, the PHOGJEF_F/PHOGJEF_M cells)
# against the ITER, state 01, in points of the household population: the female-headed
# share. Censo 2010's sample sits 1.6 points under, as its dwellings do (6s); the others
# within 0.3. The EIC 2025 equals its estimates in every municipality (its weights are
# calibrated to them). All 32 states: STEP_6t.md.
@_REAL_SKIP
@pytest.mark.parametrize("period", ["2000", "2005", "2010", "2020", "2025"])
def test_hogjef_sexo_equals_published(local_mirror, period):
    per = mxcensus.load_cpv_personas(period, state=1, derived=True)
    w = per["FACTOR"] if "FACTOR" in per else pd.Series(1.0, index=per.index)
    cons = mxcensus.cpv_constraints("personas", period)
    total = {ind: w[per["HOGJEF_SEXO"].isin(cons[ind]["HOGJEF_SEXO"])].sum()
             for ind in ("PHOGJEF_F", "PHOGJEF_M")}
    assert total["PHOGJEF_F"] + total["PHOGJEF_M"] == pytest.approx(w.sum())
    if period == "2025":
        est = mxcensus.load_cpv_estimaciones(
            survey_path=local_mirror / "cpv_estimaciones_2025.parquet", nivel="municipal",
            state=1).droplevel([0, 2])
        got = w.groupby([per["CVE_MUN"], per["HOGJEF_SEXO"]], observed=False).sum().unstack()
        assert len(est) == 11
        assert got["Mujer"].reindex(est.index).round().eq(est["PHOGJEF_F"]).all()
        assert got["Hombre"].reindex(est.index).round().eq(est["PHOGJEF_M"]).all()
        return
    it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
    published = float(it["PHOGJEF_F"]) / (float(it["PHOGJEF_F"]) + float(it["PHOGJEF_M"]))
    gap = 100 * (total["PHOGJEF_F"] / w.sum() - published)
    assert abs(gap) < {"2000": 0.3, "2005": 0.3, "2010": 2.0, "2020": 0.5}[period], gap


# 6w: the population in indigenous households (HOG_IND, the PHOG_IND cell), by each edition's
# own definition. EIC 2025 (state 01): PHOG_IND in every municipality, and HOG_IND through the
# household heads and (6x) the dwellings' own HOG_IND, exactly (its weights are calibrated to
# them; all 32 states: STEP_6x.md). Censo 2010 and 2020: the
# municipalities their sample enumerated completely (FACTOR 1 for everyone) equal the ITER to
# the person wherever their population in households does (Sonora: 34 and 5 municipalities;
# all 32 states: 2010 364, 2020 184 — STEP_6w.md).
@_REAL_SKIP
@pytest.mark.parametrize("period,state", [("2025", 1), ("2010", 26), ("2020", 26)])
def test_hog_ind_equals_published(local_mirror, period, state):
    per = mxcensus.load_cpv_personas(period, state=state, derived=True, labels=False)
    w, ind = pd.to_numeric(per["FACTOR"]), per["HOG_IND"].eq("Sí")
    if period == "2025":
        est = mxcensus.load_cpv_estimaciones(
            survey_path=local_mirror / "cpv_estimaciones_2025.parquet", nivel="municipal",
            state=state).droplevel([0, 2])
        heads = per["PARENTESCO"].eq("101")
        got = pd.DataFrame({"PHOG_IND": w.where(ind, 0), "HOG_IND": w.where(ind & heads, 0)}
                           ).groupby(per["CVE_MUN"]).sum().round()
        assert len(est) == 11
        assert got.reindex(est.index).eq(est[["PHOG_IND", "HOG_IND"]]).all().all()
        # 6x: the dwellings' own HOG_IND (the household's, from the person file)
        viv = mxcensus.load_cpv_viviendas(period, state=state, derived=True)
        dwellings = viv["FACTOR"].where(viv["HOG_IND"].eq("Sí"), 0).groupby(viv["CVE_MUN"]).sum()
        assert dwellings.round().reindex(est.index).eq(est["HOG_IND"]).all()
        return
    mun = per["MUN"]
    full = w.groupby(mun).transform("min").eq(1) & w.groupby(mun).transform("max").eq(1)
    got = pd.DataFrame({"n": 1, "ind": ind.astype(int)})[full.to_numpy()].groupby(mun[full]).sum()
    it = mxcensus.load_cpv_iter(period, state=state, nivel="municipal").reset_index()
    key = next(c for c in it.columns if c.upper() in ("MUN", "CVE_MUN"))
    it = it.set_index(it[key].astype(str))[["POBHOG", "PHOG_IND"]].astype(float)
    both = got.join(it, how="inner")
    same = both[both["n"] == both["POBHOG"]]
    assert len(same) == {"2010": 34, "2020": 5}[period] and same["PHOG_IND"].sum() > 0
    assert same["ind"].eq(same["PHOG_IND"]).all(), same[same["ind"] != same["PHOG_IND"]]


# CGPV 1990 (the 10% extract, unweighted) and the Conteo 1995 sample (FAC_POB/FAC_VIV)
# against their ITER (the counts), state 01: each constraint's share of the population or
# of the dwellings, in points (P15PRI_CO on EDUC_INEGI, without técnica after primaria, as
# INEGI's «primaria completa», 6k). All 32 states and the nation: STEP_6j.md, STEP_6k.md.
_ITER_TOLERANCE = {"1990": 0.7, "1995": 0.5}


@_REAL_SKIP
@pytest.mark.parametrize("period", ["1990", "1995"])
def test_1990_1995_constraints_equal_iter(local_mirror, period):
    it = mxcensus.load_cpv_iter(period, state=1, nivel="estatal").iloc[0]
    viv, per, _ = mxcensus.load_cpv_survey(period, state=1, derived=True, harmonize=True)
    gap = {}
    for table, frame, base in (("personas", per, "POBTOT"), ("viviendas", viv, "VIVPAR_HAB")):
        w = frame["FACTOR"] if "FACTOR" in frame else pd.Series(1.0, index=frame.index)
        for ind, cells in mxcensus.cpv_constraints(table, period).items():
            hit = pd.Series(True, index=frame.index)
            for var, cats in cells.items():
                hit &= frame[var].isin(cats)
            gap[ind] = 100 * (w[hit].sum() / w.sum() - float(it[ind]) / float(it[base]))
    assert len(gap) == {"1990": 34, "1995": 15}[period]   # 6o: own; 7f: VIVPAR_HAB, OCUPVIVPAR
    assert max(abs(v) for v in gap.values()) < _ITER_TOLERANCE[period], gap


# --- 8e: the CMO → SINCO bridge for CGPV 2000 ------------------------------------------------

def test_cmo_sinco_bridge():
    """The bundled bridge: one row per CMO code; a code INEGI's table gives one SINCO group
    takes it, one it splits takes one of its groups (the ENOE panel's), one it lacks takes
    the panel's group on 10+ persons, its CMO subgroup's only group, or 99."""
    from mxcensus._resources import cpv_cmo_sinco
    t = cpv_cmo_sinco()
    assert list(t.columns) == ["CMO", "GROUP", "RULE", "SHARE", "PERSONS", "UNITS"]
    assert t["CMO"].str.fullmatch(r"\d{4}").all() and t["CMO"].is_unique
    assert set(t["GROUP"].astype(int)) - {59} <= set(d._legacy_map("personas",
                                                                   "OCUPACION_C_COARSE"))
    assert set(t["RULE"]) == {"table", "panel", "siblings", "not placed"}
    units = t["UNITS"].str.split().map(lambda us: {u[:2] for u in us} if us else set())
    one = t["RULE"].eq("table")
    assert (units[one].map(len) == 1).all()
    assert all(g in u for g, u in zip(t.loc[one, "GROUP"], units[one]))
    split = t["RULE"].eq("panel") & t["UNITS"].ne("")
    assert (units[split].map(len) > 1).all()
    assert all(g in u for g, u in zip(t.loc[split, "GROUP"], units[split]))
    assert (t.loc[split, "PERSONS"].astype(int) >= 1).all()
    absent = t["UNITS"].eq("")
    on_panel = absent & t["RULE"].eq("panel")
    assert (t.loc[on_panel, "PERSONS"].astype(int) >= 10).all()
    assert (t.loc[on_panel, "SHARE"].astype(float) >= 0.5).all()
    assert (t.loc[absent & t["RULE"].eq("siblings"), "GROUP"] != "99").all()
    assert (t.loc[t["RULE"].eq("not placed"), "GROUP"] == "99").all()
    g = t.set_index("CMO")["GROUP"]
    assert g["9999"] == "99" and g["4100"] == "61"            # not specified; farm workers
    assert (g["8200"], g["8303"], g["4109"]) == ("96", "53", "91")    # the panel's
    assert len(t) == 461 and int(on_panel.sum()) == 0 and int(absent.sum()) == 13


_SINCO_XLS = Path(__file__).resolve().parent.parent / "data" / "dict" / "sinco" / \
    "sinco_tablas_comparativas.xls"


@pytest.mark.skipif(not (_SINCO_XLS.exists() and (_MIRROR / "cpv_personas_2000_01.parquet")
                         .exists()), reason="needs data/dict/sinco/ and the CPV 2000 mirror")
def test_cmo_sinco_rebuilds(tmp_path):
    """``scripts/build_cmo_sinco.py`` writes the bundled bridge byte for byte (ENOE's
    2012-T2/T3 COE1 through the loader)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_cmo_sinco as b
    out = tmp_path / "bridge.csv"
    b.write(b.bridge(b.table_pairs(_SINCO_XLS), b.panel(), b.codes_2000(_MIRROR).index), out)
    bundled = Path(mxcensus.__file__).parent / "_yaml" / "cpv_cmo_sinco.csv"
    assert out.read_bytes() == bundled.read_bytes()
