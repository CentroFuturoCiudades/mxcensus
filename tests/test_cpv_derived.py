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
          if period != "2020" for src in dv.sources if src != "ENT"]

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
    ("2010", "ACTIVIDADES_C"): {9999},         # ACTTRAB_C: a row of TC_SCIAN_2010, no sentinel
    ("2000", "CONACT"): {17},                  # no «limitación, rescued by the activity check»
    # 2000: no bachillerato tecnológico, normal de licenciatura, especialidad, doctorado (in
    # maestría); técnica (6) splits into 6/7/8 by its antecedent (_educ_2000)
    ("2000", "NIVACAD"): {5, 7, 8, 10, 12, 14},
    # 2000/2005 dwelling classes: one «casa independiente» (2020: 1–3 by terrain/dúplex)
    ("2000", "CLAVIVP"): {2, 3}, ("2005", "CLAVIVP"): {2, 3},
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
    # its pointer pairs: the row number (99 = row not given), the code (88 not here, 99)
    **{("2010", item): {99} for item in ("IDMADRE", "IDPADRE", "IDCONYUGE")},
    **{("2010", item): {88, 99} for item in ("IDMADREC", "IDPADREC", "IDCONYUGEC")},
    ("2015", "FINANCIAMIENTO"): set(d._financiamiento_2015()) - {d._BLANK},
    # 2010's 4-digit occupation and 6-digit religion: catalogs, no sentinel in the FD
    # (test_catalog_codes_derive reads the catalogs)
    ("2010", "OCUACTIV_C"): set(), ("2010", "OTRAREL_C"): set(),
    # CGPV 2000 (6i): the SCIAN subsector (110–939) and 999; normal/técnica antecedent; level
    # and antecedent; one item per institution; religion (0001, 1101–9001, 9100, 9999: the
    # FD declares the last two); the income, hours, birthplace and 1995 residence items are
    # text in its FD (entity 001–032, country 100–535 as 2020, 600 country unknown, 999)
    ("2000", "ACTTRAB_C"): {999}, ("2000", "ANTESC"): {1, 2, 3, 9},
    ("2000", "NIVELACAD"): {0, 10, 20, 30, 40, 51, 52, 61, 62, 63, 73, 80, 90},
    ("2000", "IMSS"): {1, 9}, ("2000", "ISSSTE"): {2}, ("2000", "PEMEX"): {3},
    ("2000", "OTRINS_V"): {4}, ("2000", "NOTIEDER"): {5}, ("2000", "OTRAREL_C"): {9100, 9999},
    ("2000", "INGTRMEN"): set(), ("2000", "HORTRA"): set(),
    ("2000", "ENT_PAIS_NAC"): {600, 999}, ("2000", "ENT_PAIS_RES_5A"): {600, 999},
    ("viviendas", "2000", "INGTRHOG"): set(),
    # Conteo 2005: level and antecedent (0–95, 99), grade (1–8, 9), one item per institution,
    # residence in 2000 (001–033, 201 the US, 600, 999)
    ("2005", "NIVANTES"): {99}, ("2005", "GRA_APRO"): set(range(1, 10)),
    ("2005", "IMSS"): {1}, ("2005", "ISSSTE"): {1}, ("2005", "PEMEX"): {1},
    ("2005", "SEGU_POP"): {1}, ("2005", "INST_PRI"): {1}, ("2005", "OTRA_INS"): {1, 2, 3, 9},
    ("2005", "SIN_DERE"): {6, 9}, ("2005", "ENT_PAIS_RES_5A"): {*range(1, 34), 201, 600, 999},
}
# Own-code text items without a catalog in their edition's FD (the code layout is stated in
# its notes, quoted above).
_NO_CATALOG = {("2000", "INGTRMEN"), ("2000", "HORTRA"), ("2000", "ENT_PAIS_NAC"),
               ("2000", "ENT_PAIS_RES_5A"), ("2000", "INGTRHOG")}
_LATER_OPTIONS = {*d._ESC[1:], *d._TRAB[1:]}      # list fewer codes (options are ordered)
# Numeric in 2010/2015, categorical in 2020 (same values; the pointers: row numbers).
_NUMERIC_CODES = {"ESCOLARI", "IDENT_MADRE", "IDENT_PADRE", "IDENT_PAREJA"}


@pytest.mark.parametrize("table,period,source", sorted(set(_CASES)))
def test_source_codes_match_2020(table, period, source):
    """Every edition a derivation is declared for has the 2020 code list of each source
    item, after the edition's recode (the dictionaries; catalog items: their sentinels),
    up to the reviewed gaps and extras; own-code items have their own list."""
    labels = variables_cpv_labels(table, _gid(table, period))
    name = next(a for a in d._ALIASES.get(source, (source,)) if a in labels)
    new = labels[name]
    key = (table, period, source) if (table, period, source) in _OWN_CODES else (period, source)
    if key in _OWN_CODES:
        tipo, codes = _codes(new)
        own = _OWN_CODES[key]
        assert codes <= own if source in _LATER_OPTIONS else codes == own
        assert tipo != "string" or new.get("Catálogo") or (period, source) in _NO_CATALOG
        return
    ref = variables_cpv_labels(table, _gid(table, "2020"))[source]
    expand = source in _NUMERIC_CODES
    tipo, codes = _codes(new, numeric_range=expand)
    ref_tipo, ref_codes = _codes(ref, numeric_range=expand)
    assert tipo == ref_tipo or expand
    recode = d._RECODE.get(period, {}).get(source, {})
    if tipo == "string":                      # catalog codes (occupation, country…)
        assert ref.get("Catálogo") and new.get("Catálogo")
    recoded = {recode.get(c, c) for c in codes}
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
    # SINCO 2019 dropped group 59: 2015's 599 and 2010's 5999 join 52 (529)
    assert r15["OCUPACION_C"] == {599: 529} and r10["OCUACTIV_C"] == {5999: 5299}


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
    assert len(derivations) == 1
    dv = derivations[0]
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


def test_cpv_derivations_listing():
    full = mxcensus.cpv_derivations()
    assert set(full.columns) == {"TABLE", "COLUMN", "SOURCES", "PERIODS"}
    assert not full.duplicated(["TABLE", "COLUMN", "PERIODS"]).any()
    for period in ("2010", "2015", "2020", "2025"):             # once per edition
        assert mxcensus.cpv_derivations(period=period)["COLUMN"].is_unique
    p25 = set(mxcensus.cpv_derivations("personas", 2025)["COLUMN"])
    p20 = set(mxcensus.cpv_derivations("personas", 2020)["COLUMN"])
    assert p20 - p25 == {"RELIGION_CAT", "IDENT_HIJO_CAT"}       # 2025 lacks the items
    assert {"DHSERSAL_SALUD_PUBLICA", "DHSERSAL_IMSS_BIENESTAR"} <= p25
    assert not set(d.DHSERSAL_RENAMES) & p20                       # legacy names gone
    dhsersal = {c for c in p20 if c.startswith("DHSERSAL_")} - {"DHSERSAL_IMSS_BIENESTAR"}
    p15 = set(mxcensus.cpv_derivations("personas", 2015)["COLUMN"])
    commute = {f"{prefix}_{label}" for prefix, item in (("MED_TRASLADO_ESC", d._ESC[0]),
                                                        ("MED_TRASLADO_TRAB", d._TRAB[0]))
               for label in d._traslado_2015(item).values()}
    migration = {"ENT_PAIS_NAC_CAT", "ENT_PAIS_RES_CAT"}
    coresidence = {"IDENT_PAREJA_CAT", "MADRE_EN_VIVIENDA", "PADRE_EN_VIVIENDA"}
    coarse = {"OCUPACION_C_COARSE", "ACTIVIDADES_C_COARSE"}
    assert p15 == {"EDAD_CAT", "INGTRMEN_CAT", "EDUC", "CONACT_CAT", "SITUA_CONYUGAL_CAT",
                   "IDENT_MADRE_CAT", "IDENT_PADRE_CAT", *migration, *coresidence,
                   *dhsersal, *commute, *coarse}
    assert {"MED_TRASLADO_ESC_Caminando", "MED_TRASLADO_TRAB_Transporte de personal"} <= p15 & p20
    assert {"MADRE_EN_VIVIENDA", "PADRE_EN_VIVIENDA", "SIN_DISC_LIM"} <= p20 & p25
    assert set(mxcensus.cpv_derivations("personas", 2010)["COLUMN"]) == {
        "EDAD_CAT", "INGTRMEN_CAT", "HORTRA_CAT", "EDUC", "CONACT_CAT", "SITUA_CONYUGAL_CAT",
        "LIM_ACTIVIDAD", "RELIGION_CAT", *migration, *coresidence, *dhsersal, *coarse}
    assert set(mxcensus.cpv_derivations("viviendas", 2010)["COLUMN"]) == {
        "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT"}
    v15 = set(mxcensus.cpv_derivations("viviendas", 2015)["COLUMN"])
    assert v15 == {"CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT",
                   *(f"FINANCIAMIENTO_{v}" for v in d._financiamiento_2015().values())}
    v20 = set(mxcensus.cpv_derivations("viviendas", 2020)["COLUMN"])
    assert {"FINANCIAMIENTO_Banco", "FINANCIAMIENTO_FONHAPO"} <= v15 & v20
    dhs2000 = {"DHSERSAL_IMSS", "DHSERSAL_ISSSTE", "DHSERSAL_P_D_M", "DHSERSAL_Otro",
               "DHSERSAL_No afiliado", "DHSERSAL_PUB", "DHSERSAL_AFIL"}
    assert set(mxcensus.cpv_derivations("personas", 2000)["COLUMN"]) == {     # 6i
        "EDAD_CAT", "INGTRMEN_CAT", "HORTRA_CAT", "EDUC", "ACTIVIDADES_C_COARSE",
        "CONACT_CAT", "SITUA_CONYUGAL_CAT", *migration, "RELIGION_CAT", *dhs2000}
    assert set(mxcensus.cpv_derivations("personas", 2005)["COLUMN"]) == {
        "EDAD_CAT", "EDUC", "ENT_PAIS_RES_CAT", *dhs2000, "DHSERSAL_ISSSTE_E",
        "DHSERSAL_SALUD_PUBLICA", "DHSERSAL_Privado"}
    assert set(mxcensus.cpv_derivations("viviendas", 2000)["COLUMN"]) == {
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT"}
    assert set(mxcensus.cpv_derivations("viviendas", 2005)["COLUMN"]) == {
        "CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT"}
    assert mxcensus.cpv_derivations("personas", 1995).empty
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
    return df


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


def test_disability_flags_inegi_vs_legacy():
    """INEGI's rules: code 8 («degree unknown») is a disability; a limitation (some
    difficulty) excludes the disabled. The legacy flags count otherwise."""
    df = _persons_2025().iloc[[0, 0, 0]].reset_index(drop=True)
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
    df = _persons_2025().iloc[[0] * len(rows)].reset_index(drop=True)
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
    out = d.derive(viv, "viviendas", 2015)
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
    assert "CLAVIVP_CAT" not in d.derive(viv.drop(columns=["CLAVIVP", "FINANCIAMIENTO"]),
                                         "viviendas", 2010)


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
        "IDENT_MADRE": ["3", "98"], "IDENT_PADRE": ["97", "99"],
        "IDENT_PAREJA": ["98", ""], "OCUPACION_C": ["599", ""],
        "ACTIVIDADES_C": ["9399", ""]}, dtype="str")


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
        "IDMADRE": ["02", "", "99"], "IDMADREC": ["", "88", "99"],
        "IDPADRE": ["99", "", ""], "IDPADREC": ["", "88", "88"],
        "IDCONYUGE": ["", "57", ""], "IDCONYUGEC": ["", "", ""],
        "OCUACTIV_C": ["", "5999", "9888"], "ACTTRAB_C": ["", "3110", "9999"],
        "OTRAREL_C": ["110300", "220100", "310100"]}, dtype="str")
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
    assert list(out["ENT_PAIS_RES_CAT"]) == ["Blanco por pase", "OtroPais", "No especificado"]
    # pointer pairs: a row (99 = row not given; above 54 too) → Sí, 88 → No, 99/99 → NE
    assert list(out["MADRE_EN_VIVIENDA"]) == ["Sí", "No", "No especificado"]
    assert list(out["PADRE_EN_VIVIENDA"]) == ["Sí", "No", "No"]
    assert list(out["IDENT_PAREJA_CAT"]) == ["Blanco por pase", "Sí", "Blanco por pase"]
    pareja = d.derive(_persons_2010().assign(IDCONYUGE=["", "99", "99"],
                                             IDCONYUGEC=["88", "", "99"]), "personas", 2010)
    assert list(pareja["IDENT_PAREJA_CAT"]) == ["No", "Sí", "No especificado"]
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
    }, dtype="str")


def test_derive_persons_2000_recodes():
    out = d.derive(_persons_2000(), "personas", 2000)
    # técnica after primaria = 2020's 6 («Primaria_com»); never schooled; under 5; maestría
    assert list(out["EDUC"]) == ["Primaria_com", "Sin Educación", "Blanco por pase", "Posbásica"]
    assert list(out["CONACT_CAT"]) == ["Trabaja", "No trabaja", "Blanco por pase", "No trabaja"]
    assert list(out["SITUA_CONYUGAL_CAT"]) == ["casado", "soltero", "Blanco por pase", "separado"]
    assert list(out["INGTRMEN_CAT"]) == ["1,000-4,999", "Blanco por pase", "Blanco por pase",
                                         "No especificado"]
    assert list(out["HORTRA_CAT"])[::3] == ["41-48", "No especificado"]
    # one item per institution: IMSS + other, none, ISSSTE, coverage not known (IMSS 9)
    assert list(out["DHSERSAL_IMSS"]) == [1, 0, 0, 0] and list(out["DHSERSAL_Otro"]) == [1, 0, 0, 0]
    assert list(out["DHSERSAL_No afiliado"]) == [0, 1, 0, 0]
    assert list(out["DHSERSAL_AFIL"]) == [1, 0, 1, 0] and list(out["DHSERSAL_PUB"]) == [1, 0, 1, 0]
    assert "DHSERSAL_SALUD_PUBLICA" not in out and "DHSERSAL_Privado" not in out
    assert list(out["ENT_PAIS_NAC_CAT"]) == ["EstaEnt", "OtraEnt", "OtroPais", "OtroPais"]
    assert list(out["ENT_PAIS_RES_CAT"]) == ["EstaEnt", "No especificado", "Blanco por pase",
                                             "OtroPais"]
    assert list(out["ACTIVIDADES_C_COARSE"])[0] == "Industrias manufactureras"   # subsector 311
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


def test_derive_persons_2005_recodes():
    df = pd.DataFrame({
        "EDAD": ["035", "002", "060"], "NIVANTES": ["62", "", "99"], "GRA_APRO": ["2", "", "3"],
        "IMSS": ["", "", ""], "ISSSTE": ["", "", ""], "PEMEX": ["", "", ""],
        "SEGU_POP": ["1", "", ""], "INST_PRI": ["", "", ""], "OTRA_INS": ["1", "", "3"],
        "SIN_DERE": ["", "9", ""], "ENT": ["09", "09", "09"],
        "LURE2000": ["201", "", "033"]}, dtype="str")
    out = d.derive(df, "personas", 2005)
    # técnica after secundaria (62 → 7); under 5; a grade without a level
    assert list(out["EDUC"]) == ["Posbásica", "Blanco por pase", "No especificado"]
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
                        "DRENAJE": ["5", "9"], "INGTRHOG": ["000000", "999999"]}, dtype="str")
    out = d.derive(v00, "viviendas", 2000)
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]          # 05 local no construido
    assert list(out["TOTCUART_CAT"]) == ["3+", "1"] and list(out["CUADORM_CAT"]) == ["1", "No especificado"]
    assert list(out["DRENAJE_CAT"]) == ["No", "No especificado"]
    v05 = pd.DataFrame({"CLAVIVPA": ["2", "7"], "CUARDOM": ["02", "01"], "NUMCUAR": ["03", "02"],
                        "DIS_DREN": ["1", "5"]}, dtype="str")
    out = d.derive(v05, "viviendas", 2005)
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]          # 7 refugio
    assert list(out["TOTCUART_CAT"]) == ["3+", "2"] and list(out["DRENAJE_CAT"]) == ["Sí", "No"]


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
        assert d.derive(df, "personas", 1995).equals(df)


# --- constraints per edition ----------------------------------------------------------------

def test_cpv_constraints_per_edition():
    per, viv = mxcensus.constraints_personas(), mxcensus.constraints_viviendas()
    assert len(mxcensus.cpv_constraints("personas", 2020)) == len(per)
    assert len(mxcensus.cpv_constraints("viviendas", 2020)) == len(viv)
    assert mxcensus.cpv_constraints("personas", 2015) == {}           # no ITER, no estimates
    p10 = mxcensus.cpv_constraints("personas", 2010)
    assert 0 < len(p10) < len(per)
    assert {"PDER_SS", "PDER_IMSS", "PSINDER", "P18YM_PB", "P15YM_SE", "P12YM_SOLT"} <= set(p10)
    assert "PDER_SEGP" not in p10                                      # not comparable in 2010
    own = d._EDITION_CELLS["personas", "2010"]                         # 2010's own limitation
    assert {ind: p10[ind] for ind in own} == own
    assert p10["PCLIM_VIS"] == {"DISCAP2": ["Ver, aun usando lentes"]}
    assert p10["PNACOE"] == {"ENT_PAIS_NAC_CAT": ["OtraEnt"]}          # 6e: migration
    assert {"PNACENT_F", "PRES2015", "PRESOE15_M"} <= set(p10)        # 2010: PRES2005 …
    assert {"PCATOLICA", "POTRAS_REL", "PSIN_RELIG"} <= set(p10)       # 6f: 2010 religion
    assert p10["PNCATOLICA"] == {"RELIGION_CAT": ["Protestante/cristiano evangélico"]}
    assert "PRO_CRIEVA" not in p10 and "PNCATOLICA" not in mxcensus.cpv_constraints("personas", 2020)
    assert "PCON_LIM" not in mxcensus.cpv_constraints("personas", 2020)
    assert mxcensus.cpv_constraints("viviendas", 2010) == {}          # no CLAVIVP_CAT in 2010
    p25 = mxcensus.cpv_constraints("personas", 2025)
    assert {"POBTOT", "POBFEM", "P_15YMAS_F", "PDER_SS", "POCUPADA"} <= set(p25)
    assert set(mxcensus.cpv_constraints("viviendas", 2025)) == {"TOTHOG", "HOGJEF_F", "HOGJEF_M"}
    c20 = mxcensus.cpv_constraints("personas", 2020)
    assert c20["PDER_SEGP"] == {"DHSERSAL_SALUD_PUBLICA": [1]}        # neutral DHSERSAL name
    assert c20["PCON_DISC"] == {"DISCAPACIDAD": ["Sí"]}                # INEGI's definitions
    assert c20["PCON_LIMI"] == {"LIMITACION": ["Sí"]}
    assert c20["PSIND_LIM"] == p25["PSIND_LIM"] == {"SIN_DISC_LIM": ["Sí"]}   # 6g
    v20 = mxcensus.cpv_constraints("viviendas", 2020)
    assert "dentro de la vivienda?" in v20["VPH_AGUADV"]["AGUA_ENTUBADA"]   # the FD's wording
    p00, p05 = (mxcensus.cpv_constraints("personas", p) for p in (2000, 2005))   # 6i
    assert {"PCATOLICA", "PDER_SS", "PSINDER", "P12YM_CASA", "PEA", "PNACOE"} <= set(p00)
    assert {"PDER_ISTE", "PSINDER", "PRESOE15", "P15YM_SE"} <= set(p05)
    assert set(mxcensus.cpv_constraints("viviendas", 2000)) == {
        "TOTHOG", "VPH_1CUART", "VPH_1DOR", "VPH_DRENAJ"}
    for period in ("2000", "2005", "2010", "2020", "2025"):            # categories all exist
        cats = d._categories("personas", period)
        for cells in mxcensus.cpv_constraints("personas", period).values():
            assert all(set(c) <= set(cats[v]) for v, c in cells.items())


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
    for col in set(new.columns) - set(shared) - set(d._DTYPES):     # unobserved codes' dummies
        assert (new[col].astype(int) == 0).all(), col


@_REAL_SKIP
@pytest.mark.parametrize("period", ["2000", "2005", "2010", "2015", "2020", "2025"])
def test_derived_editions_real(local_mirror, period):
    """``derived=True`` on each edition: the declared columns, their dtypes, no missing
    value; the same columns with or without labels and harmonization."""
    _, per, _ = mxcensus.load_cpv_survey(period, state=1, derived=True)
    viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True)
    for table, frame in (("personas", per), ("viviendas", viv)):
        dtypes = d.derived_dtypes(table, period)
        assert dtypes and set(dtypes) <= set(frame.columns)
        for col, dtype in dtypes.items():
            assert frame[col].dtype == dtype and frame[col].notna().all(), col
    raw = mxcensus.load_cpv_personas(period, state=1, derived=True, labels=False,
                                     harmonize=True)               # other keys: compare counts
    for col in d.derived_dtypes("personas", period):
        assert raw[col].value_counts().equals(per[col].value_counts()), col


@_REAL_SKIP
@pytest.mark.parametrize("period", ["2000", "2005", "2010", "2020", "2025"])
def test_crosstab_per_edition(local_mirror, period):
    """One table per edition: the constraints build ``get_tables_dict`` against the derived
    frame's dtypes, and the age × sex table fills."""
    per = mxcensus.load_cpv_personas(period, state=1, derived=True)
    tables = mxcensus.get_tables_dict(mxcensus.cpv_constraints("personas", period), per.dtypes)
    key = frozenset({"SEXO", "EDAD_CAT"})
    assert key in tables
    table = mxcensus.create_cont_table(tables[key])
    assert set(table.columns) <= set(per["EDAD_CAT"].cat.categories) and len(table)
    if period == "2010":                       # 2010's own limitation cells
        for var in ("LIM_ACTIVIDAD", "DISCAP2"):
            assert len(mxcensus.create_cont_table(tables[frozenset({var})]).columns)
    if period == "2020":
        viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True)
        assert mxcensus.get_tables_dict(mxcensus.cpv_constraints("viviendas", period), viv.dtypes)


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
    """EIC 2025: Σ ``FACTOR`` over each constraint's cells equals the published state
    estimate exactly (the factors are calibrated to them), ``PCON_DISC``/``PCON_LIMI``/
    ``PSIND_LIM`` through INEGI's ``DISCAPACIDAD``/``LIMITACION``/``SIN_DISC_LIM``. All 32
    states (and ``PSIND_LIM`` in 2,471 municipalities): STEP_6b.md, STEP_6g.md."""
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(2025, state=1, derived=True)
    est = mxcensus.load_cpv_estimaciones(survey_path=_MIRROR / "cpv_estimaciones_2025.parquet",
                                         nivel="estatal", state=1)
    checked = 0
    for ind, cells in mxcensus.cpv_constraints(table, 2025).items():
        mask = pd.Series(True, index=frame.index)
        for var, cats in cells.items():
            mask &= frame[var].isin(cats)
        assert round(frame.loc[mask, "FACTOR"].sum()) == round(est[ind].iloc[0]), ind
        checked += 1
    assert checked == {"personas": 25, "viviendas": 3}[table]


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
