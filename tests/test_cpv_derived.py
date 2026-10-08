"""CPV derived columns (``mxcensus.cpv_derived``, unit 6b) and the constraints per edition.

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


def _codes(meta: dict) -> tuple[str, frozenset[int]]:
    """An item's type and its integer codes (categories + sentinels; numerics: sentinels)."""
    from mxcensus import _schema_groups as _sg

    tipo = _sg.norm_tipo(meta)
    keys = dict(meta.get("Especiales") or {})
    if tipo == "categorical":
        keys.update(meta.get("Categorías") or {})
    return tipo, frozenset(int(k) for k in keys)


_CASES = [(dv.table, period, src) for dv in d._registry() for period in dv.periods
          if period != "2020" for src in dv.sources if src not in d._ALIASES]


@pytest.mark.parametrize("table,period,source", sorted(set(_CASES)))
def test_source_codes_match_2020(table, period, source):
    """Every edition a derivation is declared for has the 2020 code list of each source
    item, after the edition's recode (the dictionaries; catalog items: their sentinels)."""
    new = variables_cpv_labels(table, _gid(table, period))[source]
    ref = variables_cpv_labels(table, _gid(table, "2020"))[source]
    tipo, codes = _codes(new)
    ref_tipo, ref_codes = _codes(ref)
    assert tipo == ref_tipo
    recode = d._RECODE.get(period, {}).get(source, {})
    if tipo == "string":                      # catalog codes (occupation, country…)
        assert ref.get("Catálogo") and new.get("Catálogo")
    assert {recode.get(c, c) for c in codes} == ref_codes


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


def test_cpv_derivations_listing():
    full = mxcensus.cpv_derivations()
    assert set(full.columns) == {"TABLE", "COLUMN", "SOURCES", "PERIODS"}
    assert full["COLUMN"].is_unique
    p25 = set(mxcensus.cpv_derivations("personas", 2025)["COLUMN"])
    p20 = set(mxcensus.cpv_derivations("personas", 2020)["COLUMN"])
    assert p20 - p25 == {"RELIGION_CAT", "IDENT_HIJO_CAT"}       # 2025 lacks the items
    assert {"DHSERSAL_SALUD_PUBLICA", "DHSERSAL_IMSS_BIENESTAR"} <= p25
    assert not set(d.DHSERSAL_RENAMES) & p20                       # legacy names gone
    assert set(mxcensus.cpv_derivations("personas", 2015)["COLUMN"]) == {"EDAD_CAT",
                                                                        "INGTRMEN_CAT"}
    assert set(mxcensus.cpv_derivations("personas", 2010)["COLUMN"]) == {
        "EDAD_CAT", "INGTRMEN_CAT", "HORTRA_CAT", "CONACT_CAT"}
    assert set(mxcensus.cpv_derivations("viviendas", 2010)["COLUMN"]) == {
        "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT", "INGTRHOG_CAT"}
    assert mxcensus.cpv_derivations("personas", 2005).empty
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
    for col, dtype in d.derived_dtypes("personas", "2025").items():
        assert out[col].dtype == dtype, col
    assert out["EDAD_CAT"].cat.ordered


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
                        "DRENAJE": ["5", ""], "INGTRHOG": ["0", "999999"]}, dtype="str")
    out = d.derive(viv, "viviendas", 2015)
    assert list(out["CLAVIVP_CAT"]) == ["Vivienda", "Otro"]
    assert list(out["CUADORM_CAT"]) == ["1", "2+"]
    assert list(out["TOTCUART_CAT"]) == ["2", "No especificado"]
    assert list(out["DRENAJE_CAT"]) == ["No", "Blanco por pase"]
    assert list(out["INGTRHOG_CAT"]) == ["No recibe ingresos", "No especificado"]
    assert "CLAVIVP_CAT" not in d.derive(viv.drop(columns="CLAVIVP"), "viviendas", 2010)
    assert list(d.derive(pd.DataFrame({"EDAD": ["5"], "INGTRMEN": [""], "HORTRA": ["168"],
                                       "CONACT": ["80"]}), "personas", 2010).iloc[0, 4:]) \
        == ["5", "Blanco por pase", "81YMAS", "No trabaja"]


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
        assert d.derive(df, "personas", 2005).equals(df)


# --- constraints per edition ----------------------------------------------------------------

def test_cpv_constraints_per_edition():
    per, viv = mxcensus.constraints_personas(), mxcensus.constraints_viviendas()
    assert len(mxcensus.cpv_constraints("personas", 2020)) == len(per)
    assert len(mxcensus.cpv_constraints("viviendas", 2020)) == len(viv)
    assert mxcensus.cpv_constraints("personas", 2015) == {}           # no ITER, no estimates
    p10 = mxcensus.cpv_constraints("personas", 2010)
    assert 0 < len(p10) < len(per) and "PCLIM_VIS" not in p10        # not comparable in 2010
    assert mxcensus.cpv_constraints("viviendas", 2010) == {}          # no CLAVIVP_CAT in 2010
    p25 = mxcensus.cpv_constraints("personas", 2025)
    assert {"POBTOT", "POBFEM", "P_15YMAS_F", "PDER_SS", "POCUPADA"} <= set(p25)
    assert set(mxcensus.cpv_constraints("viviendas", 2025)) == {"TOTHOG", "HOGJEF_F", "HOGJEF_M"}
    c20 = mxcensus.cpv_constraints("personas", 2020)
    assert c20["PDER_SEGP"] == {"DHSERSAL_SALUD_PUBLICA": [1]}        # neutral DHSERSAL name
    v20 = mxcensus.cpv_constraints("viviendas", 2020)
    assert "dentro de la vivienda?" in v20["VPH_AGUADV"]["AGUA_ENTUBADA"]   # the FD's wording
    for period in ("2010", "2020", "2025"):                            # categories all exist
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
    for col in set(new.columns) - set(shared):
        assert (new[col].astype(int) == 0).all(), col


@_REAL_SKIP
@pytest.mark.parametrize("period", ["2010", "2015", "2020", "2025"])
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
@pytest.mark.parametrize("period", ["2010", "2020", "2025"])
def test_crosstab_per_edition(local_mirror, period):
    """One table per edition: the constraints build ``get_tables_dict`` against the derived
    frame's dtypes, and the age × sex table fills."""
    per = mxcensus.load_cpv_personas(period, state=1, derived=True)
    tables = mxcensus.get_tables_dict(mxcensus.cpv_constraints("personas", period), per.dtypes)
    key = frozenset({"SEXO", "EDAD_CAT"})
    assert key in tables
    table = mxcensus.create_cont_table(tables[key])
    assert set(table.columns) <= set(per["EDAD_CAT"].cat.categories) and len(table)
    if period == "2020":
        viv = mxcensus.load_cpv_viviendas(period, state=1, derived=True)
        assert mxcensus.get_tables_dict(mxcensus.cpv_constraints("viviendas", period), viv.dtypes)


# The legacy DIS_CON/DIS_LIMI and the PSIND_LIM cells follow the legacy definitions, not
# INEGI's (which counts code 8, «degree unknown», as a disability and keeps the disabled out
# of «limitación»): their estimates differ.
_DEFINITIONS_DIFFER = {"PCON_DISC", "PCON_LIMI", "PSIND_LIM"}


@_REAL_SKIP
@pytest.mark.parametrize("table", ["personas", "viviendas"])
def test_eic2025_constraints_equal_estimates(local_mirror, table):
    """EIC 2025: Σ ``FACTOR`` over each constraint's cells equals the published state
    estimate exactly (the factors are calibrated to them), but for the disability
    indicators whose definitions differ."""
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(2025, state=1, derived=True)
    est = mxcensus.load_cpv_estimaciones(survey_path=_MIRROR / "cpv_estimaciones_2025.parquet",
                                         nivel="estatal", state=1)
    checked = 0
    for ind, cells in mxcensus.cpv_constraints(table, 2025).items():
        mask = pd.Series(True, index=frame.index)
        for var, cats in cells.items():
            mask &= frame[var].isin(cats)
        total = round(frame.loc[mask, "FACTOR"].sum())
        if ind in _DEFINITIONS_DIFFER:
            assert total != round(est[ind].iloc[0]), ind
        else:
            assert total == round(est[ind].iloc[0]), ind
            checked += 1
    assert checked == {"personas": 22, "viviendas": 3}[table]
