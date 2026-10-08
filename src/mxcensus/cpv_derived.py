"""Derived analysis columns on the CPV microdata (the legacy ``load_extended_*`` set) and
the census constraints per edition.

The legacy loaders (``extended_personas``/``extended_viviendas``: Censo 2020 only, frozen)
add coarse categories (``EDAD_CAT``, ``EDUC``, ``CONACT_CAT``…), indicator dummies
(``DHSERSAL_*``, ``MED_TRASLADO_*``, ``FINANCIAMIENTO_*``) and flags (``DIS_CON``/
``DIS_LIMI``) to the cuestionario ampliado. :func:`derive` adds the same columns to a CPV
frame of any edition whose source items carry the same codes. ``load_cpv_personas``/
``load_cpv_viviendas``/``load_cpv_survey`` call it with ``derived=True``.

**How.** Each derivation (:data:`_DERIVATIONS`) names its source items, the editions it is
verified for, and a function of the source codes. The codes are read from the **raw**
frame (before labelling), translated into the Censo 2020 code space by the edition's
recode table (:data:`_RECODE`; identity unless listed), then mapped with the legacy
dictionaries (``variables_personas.yaml``/``variables_viviendas.yaml``). The 2020 columns
therefore equal the legacy ones (tested state by state). Two differences, both deliberate:

- ``DHSERSAL_SALUD_PUBLICA`` / ``DHSERSAL_IMSS_BIENESTAR`` replace the legacy
  ``DHSERSAL_Popular_NGenración_SBienestar`` / ``DHSERSAL_IMSS_Prospera/Bienestar``: the
  EIC 2025 swapped the two codes and widened one (:data:`_RECODE`), so both editions use
  names that fit both.
- The dummy sets (``MED_TRASLADO_ESC_*``, ``MED_TRASLADO_TRAB_*``, ``FINANCIAMIENTO_*``)
  are fixed: one column per code, also for codes no one in the frame reported (the legacy
  loaders only create the observed ones). As in the legacy loaders, a blank second or
  third item sets the ``…_Blanco por pase`` dummy.

Four columns are new: ``DISCAPACIDAD``/``LIMITACION``, INEGI's definitions of disability
and limitation (code 8, «degree unknown», is a disability; a limitation excludes the
disabled; the legacy ``DIS_CON``/``DIS_LIMI`` count otherwise and are kept as they are),
and ``MADRE_EN_VIVIENDA``/``PADRE_EN_VIVIENDA`` (whether the mother/father lives in the
dwelling: the one part of ``IDENT_MADRE``/``IDENT_PADRE`` Censo 2010 also asked).

**Editions.** Censo 2020 and EIC 2025 (same questionnaire family) get every derivation
whose sources exist; 2025 lacks ``RELIGION`` and ``IDENT_HIJO``. EIC 2015 and Censo 2010
get the derivations whose source items map onto the 2020 codes (:data:`_RECODE`; 2010
reads its marital status from ``ESTCON``, 2015 its residence five years earlier from
``ENT_PAIS_RES10``), with these edition-specific sets:

- ``DHSERSAL_*`` without ``DHSERSAL_IMSS_BIENESTAR`` (neither edition offered
  IMSS-PROSPERA/BIENESTAR);
- the EIC 2015 commute dummies, one per 2015 code (7 modes): the 2020 names where the mode
  is the same, 2015's wording for the three modes 2020 splits;
- the EIC 2015 financing dummies, one per code of its one item: the 2020 names where the
  source is the same, 2015's wording for «INFONAVIT, FOVISSSTE o PEMEX»;
- Censo 2010's ``LIM_ACTIVIDAD`` («limitación en la actividad», ``DISCAP1``–``DISCAP8``):
  another question than 2020's difficulty scale, so no ``DIS_*``/``DISCAPACIDAD`` there;
- Censo 2010's birthplace and residence in 2005, each split in an entity and a country
  item (``LNACEDO_C``/``LNACPAIS_C``, ``RES05EDO_C``/``RES05PAI_C``), and its co-residence
  pointer pairs (row number + code item: ``IDMADRE``/``IDMADREC``…), which give
  ``IDENT_PAREJA_CAT`` and the two co-residence flags but not ``IDENT_MADRE_CAT``/
  ``IDENT_PADRE_CAT`` (its «no vive aquí» merges 2020's other dwelling, dead, unknown).

An unspecified entity (2020: 997) counts as ``OtraEnt`` in every edition, the legacy rule;
INEGI's tabulados count it as not specified (a few hundred persons per edition).

:func:`cpv_derivations` lists the columns per edition. The check that the source codes
match after the recode is a test (``tests/test_cpv_derived.py``).

**Constraints.** :func:`cpv_constraints` filters the legacy constraint sets (ITER
indicator → microdata cells, ``constraints_*.yaml``) to the indicators an edition can
reproduce, for :func:`mxcensus.crosstabs.get_tables_dict`, plus the indicators an edition
publishes under its own definition (:data:`_EDITION_CELLS`: Censo 2010's limitation).
"""
from __future__ import annotations

import functools
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from mxcensus._resources import (
    constraints_personas,
    constraints_viviendas,
    variables_personas,
    variables_viviendas,
)
from mxcensus.utils import expand_cat_map

TABLES = ("personas", "viviendas")

# Edition → source item → {edition code: Censo 2020 code}. Codes not listed are the same.
_RECODE: dict[str, dict[str, dict[int, int]]] = {
    "2025": {
        # 01–09/99; «separada(o)» split into 02 (from a free union) and 03 (from a marriage).
        "SITUA_CONYUGAL": {1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 99: 9},
        # 05 = IMSS-BIENESTAR (2020: 06); 06 = a public health centre, hospital or institute,
        # incl. INSABI and Seguro Popular (2020: 05, Seguro Popular / INSABI).
        "DHSERSAL1": {5: 6, 6: 5},
        "DHSERSAL2": {5: 6, 6: 5},
        # The country catalog renumbered two entries: Isla de Man, Palaos.
        "ENT_PAIS_NAC": {454: 241, 536: 356},
        "ENT_PAIS_RES_5A": {454: 241, 536: 356},
    },
    "2015": {
        # 1 = Seguro Popular (2020: 05) first, then IMSS…otra 2–7 (2020: 01–04, 07, 08),
        # 8 = not affiliated, 9 = not specified; no IMSS-PROSPERA/BIENESTAR (2020: 06).
        "DHSERSAL1": {1: 5, 2: 1, 3: 2, 4: 3, 5: 4, 6: 7, 7: 8, 8: 9, 9: 99},
        "DHSERSAL2": {1: 5, 2: 1, 3: 2, 4: 3, 5: 4, 6: 7, 7: 8, 8: 9, 9: 99},
        # 10 worked, 11–15 found working by the activity check (2020: 10, 13–19 by declared
        # status), 16 had a job (20), 20 searched (30), 31–35 student, retired, home duties,
        # limitation, did not work (50, 40, 60, 70, 80).
        "CONACT": {11: 10, 12: 10, 13: 10, 14: 10, 15: 10, 16: 20, 20: 30,
                   31: 50, 32: 40, 33: 60, 34: 70, 35: 80},
        # 5 = casada(o), not split into civil/religious (2020: 05–07, all «casado»);
        # 6 = soltera(o).
        "SITUA_CONYUGAL": {6: 8},
        # «¿Dónde vive la pareja?»: 98 = does not know where, so not in this dwelling (96).
        "IDENT_PAREJA": {98: 96},
    },
    "2010": {
        # 6 = private, 7 = other, 8 = no entitlement, 9 = not specified (2020: 07, 08, 09, 99);
        # no IMSS-PROSPERA/BIENESTAR (2020: 06).
        "DHSERSAL1": {6: 7, 7: 8, 8: 9, 9: 99},
        "DHSERSAL2": {6: 7, 7: 8, 8: 9, 9: 99},
        # 04 = either bachillerato (2020: 04/05), 05 = normal básica (09), then normal de
        # licenciatura, licenciatura, maestría, doctorado (10, 11, 13, 14); no especialidad.
        "NIVACAD": {5: 9, 9: 10, 10: 11, 11: 13, 12: 14},
        # Birthplace and residence in 2005: an entity item and a country item. Entity 999 =
        # entity not specified (2020: 997), 900 = topic omitted (999); country 600 =
        # insufficiently specified (998), 700 = «México (país)» (997), 999 = country not
        # specified (998).
        "LNACEDO_C": {900: 999, 999: 997},
        "RES05EDO_C": {900: 999, 999: 997},
        "LNACPAIS_C": {600: 998, 700: 997, 999: 998},
        "RES05PAI_C": {600: 998, 700: 997, 999: 998},
    },
}

# A source read under another name in some editions or under harmonize=True.
_ALIASES = {"ENT": ("ENT", "CVE_ENT"), "SITUA_CONYUGAL": ("SITUA_CONYUGAL", "ESTCON"),
            "ENT_PAIS_RES_5A": ("ENT_PAIS_RES_5A", "ENT_PAIS_RES10")}

_BLANK = -1  # a blank (not asked) code, as the legacy dictionaries spell it
_DUMMY = pd.CategoricalDtype([0, 1])
# Derived columns the legacy loaders do not have (the others take the legacy dtype).
_YES_NO = pd.CategoricalDtype(["Sí", "No", "No especificado"])
_DTYPES = {"DISCAPACIDAD": _YES_NO, "LIMITACION": _YES_NO, "LIM_ACTIVIDAD": _YES_NO,
           "MADRE_EN_VIVIENDA": _YES_NO, "PADRE_EN_VIVIENDA": _YES_NO}
_DIS_ITEMS = ("DIS_VER", "DIS_OIR", "DIS_CAMINAR", "DIS_RECORDAR", "DIS_BANARSE", "DIS_HABLAR")
# Censo 2010: one item per activity (DISCAP1–7, its code or blank), DISCAP8 = none (17) or
# not specified (99).
_DISCAP_ITEMS = tuple(f"DISCAP{i}" for i in range(1, 9))

# DHSERSAL1/2 code (2020) → dummy; 1–6 are public institutions, 1–8 any affiliation.
_DHSERSAL = {
    1: "DHSERSAL_IMSS",
    2: "DHSERSAL_ISSSTE",
    3: "DHSERSAL_ISSSTE_E",
    4: "DHSERSAL_P_D_M",
    5: "DHSERSAL_SALUD_PUBLICA",       # legacy DHSERSAL_Popular_NGenración_SBienestar
    6: "DHSERSAL_IMSS_BIENESTAR",      # legacy DHSERSAL_IMSS_Prospera/Bienestar
    7: "DHSERSAL_Privado",
    8: "DHSERSAL_Otro",
    9: "DHSERSAL_No afiliado",
}
_DHSERSAL_NO_BIENESTAR = tuple(c for c in _DHSERSAL if c != 6)   # 2010, 2015
#: Legacy dummy name → the neutral name used here (for the legacy constraints and tests).
DHSERSAL_RENAMES = {
    "DHSERSAL_Popular_NGenración_SBienestar": "DHSERSAL_SALUD_PUBLICA",
    "DHSERSAL_IMSS_Prospera/Bienestar": "DHSERSAL_IMSS_BIENESTAR",
}


@functools.cache
def _variables(table: str) -> dict:
    return variables_personas() if table == "personas" else variables_viviendas()


@functools.cache
def _legacy_map(table: str, var: str) -> dict:
    """The legacy code → label map of ``var`` (int codes, ``-1`` = blank)."""
    return expand_cat_map(_variables(table)[var]["Categorías"])


@functools.cache
def _legacy_dtypes(table: str) -> dict:
    """The dtype each derived column has in the legacy loader's schema."""
    from mxcensus import extended_personas, extended_viviendas

    mod = extended_personas if table == "personas" else extended_viviendas
    return {name: col.dtype.type for name, col in mod._build_schema().columns.items()}


def _as(values, table: str, name: str) -> pd.Series:
    return pd.Series(values).astype(_DTYPES.get(name) or _legacy_dtypes(table)[name])


def _mapped(codes: pd.Series, table: str, var: str, name: str) -> pd.Series:
    """``codes`` through the legacy map of ``var`` (the ``Categorías`` of ``name``)."""
    return _as(codes.fillna(_BLANK).map(_legacy_map(table, var)), table, name)


def _cut(values: pd.Series, table: str, name: str, bins, labels, *, right: bool,
         blank: float | None = None) -> pd.Series:
    """The legacy ``pd.cut`` binning (``blank`` fills the not-asked rows first)."""
    if blank is not None:
        values = values.fillna(blank)
    return _as(pd.cut(values, bins, right=right, labels=labels), table, name)


# --- the derivations (src: the source items as float codes in the 2020 code space) --------

_INCOME_BINS = (0, 1, 1000, 5000, 10000, 20000, 40000, 80000, 150000, 999999, 1e6, 3e6)
_INCOME_LABELS = ["No recibe ingresos", "1-999", "1,000-4,999", "5,000-9,999",
                  "10,000-19,999", "20,000-39,999", "40,000-79,999", "80,000-149,999",
                  "150,000yMas", "No especificado", "Blanco por pase"]


def _edad_cat(src):
    labels = ["0-2", "3-4", "5", "6-7", "8-11", "12-14", "15-17", "18-24", "25-49",
              "50-59", "60-64", "65-130", "No especificado"]
    return {"EDAD_CAT": _cut(src["EDAD"], "personas", "EDAD_CAT",
                             (0, 3, 5, 6, 8, 12, 15, 18, 25, 50, 60, 65, 200, 1e6),
                             labels, right=False)}


def _ingtrmen_cat(src):
    return {"INGTRMEN_CAT": _cut(src["INGTRMEN"], "personas", "INGTRMEN_CAT", _INCOME_BINS,
                                 _INCOME_LABELS, right=False, blank=2e6)}


def _hortra_cat(src):
    labels = ["0-5", "6-10", "11-20", "21-40", "41-48", "49-56", "57-60", "61-80", "81YMAS",
              "No especificado", "Blanco por pase"]
    return {"HORTRA_CAT": _cut(src["HORTRA"], "personas", "HORTRA_CAT",
                               [-1, 5, 10, 20, 40, 48, 56, 60, 80, 998, 1e6, 3e6], labels,
                               right=True, blank=2e6)}


@functools.cache
def _educ_map() -> dict[int, str]:
    """(NIVACAD, ESCOLARI) → EDUC, keyed ``(nivacad + 1) * 1000 + escolari + 1`` (blank =
    -1): the legacy map is keyed by the two items' labels, ``"Primaria_6"``."""
    educ = _variables("personas")["EDUC"]["Categorías"]
    out = {}
    for n, n_label in _legacy_map("personas", "NIVACAD").items():
        for e, e_label in _legacy_map("personas", "ESCOLARI").items():
            if (label := educ.get(f"{n_label}_{e_label}")) is not None:
                out[(n + 1) * 1000 + e + 1] = label
    return out


def _educ(src):
    key = (src["NIVACAD"].fillna(_BLANK) + 1) * 1000 + src["ESCOLARI"].fillna(_BLANK) + 1
    return {"EDUC": _as(key.map(_educ_map()), "personas", "EDUC")}


def _coarse(var: str, name: str, divisor: int):
    def fn(src):
        return {name: _mapped(np.floor(src[var] / divisor), "personas", name, name)}
    return fn


def _dis(src):
    items = src[list(_DIS_ITEMS)]
    unspecified = items.isin([8, 9]).any(axis=1)
    out = {}
    for name, has in (("DIS_CON", items.isin([3, 4]).any(axis=1)),
                      ("DIS_LIMI", items.eq(2).any(axis=1))):
        out[name] = _as(np.select([has, unspecified], ["Sí", "No especificado"], "No"),
                        "personas", name)
    return out


def _dis_inegi(src):
    """INEGI's definitions (the EIC 2025 estimates, matched exactly): a disability is much
    difficulty, not being able, or a difficulty of unknown degree (code 8) in at least one
    activity; a limitation is some difficulty (2) in at least one, without a disability."""
    items = src[list(_DIS_ITEMS)]
    disabled = items.isin([3, 4, 8]).any(axis=1)
    limited = items.eq(2).any(axis=1) & ~disabled
    unspecified = items.eq(9).any(axis=1)
    return {"DISCAPACIDAD": _as(np.select([disabled, unspecified], ["Sí", "No especificado"],
                                          "No"), "personas", "DISCAPACIDAD"),
            "LIMITACION": _as(np.select([limited, disabled, unspecified],
                                        ["Sí", "No", "No especificado"], "No"),
                              "personas", "LIMITACION")}


def _as_dummies(flags: Mapping[str, pd.Series], unknown: pd.Series) -> dict[str, pd.Series]:
    """Boolean flags → 0/1 dummies, missing on the ``unknown`` rows (a code no dummy names,
    which :func:`derive` reports)."""
    return {k: v.astype(int).astype(_DUMMY).mask(unknown) for k, v in flags.items()}


def _dhsersal(codes: tuple[int, ...]):
    """The dummies of the 2020 ``codes`` an edition offers (1–6 public, 1–8 any)."""
    def fn(src):
        d1, d2 = src["DHSERSAL1"], src["DHSERSAL2"]
        has = {code: d1.eq(code) | d2.eq(code) for code in codes}
        out = {_DHSERSAL[code]: has[code] for code in codes}
        out["DHSERSAL_PUB"] = pd.concat([has[c] for c in codes if c <= 6], axis=1).any(axis=1)
        out["DHSERSAL_AFIL"] = pd.concat([has[c] for c in codes if c <= 8], axis=1).any(axis=1)
        known = [*codes, 99]
        unknown = (d1.notna() & ~d1.isin(known)) | (d2.notna() & ~d2.isin(known))
        return _as_dummies(out, unknown)
    return fn


def _dhsersal_names(codes: tuple[int, ...]) -> tuple[str, ...]:
    return (*(_DHSERSAL[c] for c in codes), "DHSERSAL_PUB", "DHSERSAL_AFIL")


def _dummies(table: str, items: tuple[str, ...], prefix: str,
             labels: Mapping[int, str] | None = None):
    """One 0/1 column per code of ``labels`` (default: the legacy map of ``items[0]``; the
    labels name the columns): 1 when any of ``items`` has that code (a blank item sets the
    ``Blanco por pase`` dummy)."""
    def fn(src):
        codes = src[list(items)].fillna(_BLANK)
        names = labels or _legacy_map(table, items[0])
        flags = {f"{prefix}_{label}": codes.eq(code).any(axis=1) for code, label in names.items()}
        return _as_dummies(flags, ~codes.isin(list(names)).all(axis=1))
    return fn


def _dummy_names(table: str, items: tuple[str, ...], prefix: str,
                 labels: Mapping[int, str] | None = None) -> tuple[str, ...]:
    return tuple(f"{prefix}_{label}" for label in (labels or _legacy_map(table, items[0])).values())


# EIC 2015 commute code → its Censo 2020 code where the mode is the same (4 = transporte
# escolar/laboral, 2020's «de personal»). Codes 1–3 merge 2020 modes (camión + both taxis,
# metro + metrobús, automóvil + motocicleta) and keep 2015's wording; 2020's trolebús has no
# 2015 code.
_TRASLADO_2015_SAME = {4: 7, 5: 2, 6: 1, 7: 12, 9: 99, _BLANK: _BLANK}
_TRASLADO_2015_OWN = {1: "Camión, taxi, combi o colectivo", 2: "Metro, metrobús o tren ligero",
                      3: "Vehículo particular (automóvil, camioneta o motocicleta)"}


@functools.cache
def _traslado_2015(item: str) -> dict[int, str]:
    """EIC 2015 commute code → dummy label (the 2020 ``item``'s label where the mode is
    the same)."""
    legacy = _legacy_map("personas", item)
    same = {code: legacy[ref] for code, ref in _TRASLADO_2015_SAME.items()}
    return {code: _TRASLADO_2015_OWN.get(code) or same[code]
            for code in sorted({*_TRASLADO_2015_OWN, *same}, key=lambda c: (c == _BLANK, c))}


# EIC 2015's one financing item (one answer) → the 2020 code where the source is the same;
# its 1 merges INFONAVIT, FOVISSSTE and PEMEX (2020: 1–3) and keeps 2015's wording.
_FINANCIAMIENTO_2015_SAME = {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 9: 9, _BLANK: _BLANK}


@functools.cache
def _financiamiento_2015() -> dict[int, str]:
    """EIC 2015 financing code → dummy label (the 2020 label where the source is the same)."""
    legacy = _legacy_map("viviendas", "FINANCIAMIENTO1")
    return {1: "INFONAVIT, FOVISSSTE o PEMEX",
            **{code: legacy[ref] for code, ref in _FINANCIAMIENTO_2015_SAME.items()}}


def _lim_actividad(src):
    """Censo 2010's «limitación en la actividad» (its ITER's ``PCON_LIM``/``PSIN_LIM``): a
    difficulty in at least one activity (``DISCAP1``–``DISCAP7``), none (``DISCAP8`` = 17)
    or not specified (99). A row with neither is left missing (:func:`derive` reports it)."""
    limited = src[list(_DISCAP_ITEMS[:7])].notna().any(axis=1)
    none = src["DISCAP8"]
    values = np.select([limited, none.eq(17), none.eq(99)], ["Sí", "No", "No especificado"],
                       None)
    return {"LIM_ACTIVIDAD": _as(values, "personas", "LIM_ACTIVIDAD")}


def _cat(table: str, var: str, name: str):
    def fn(src):
        return {name: _mapped(src[var], table, name, name)}
    return fn


def _ent_pais_cat(var: str, name: str, abroad: str | None = None):
    """Entity or country → ``OtraEnt``/``OtroPais``/…, ``EstaEnt`` for the person's entity
    (Censo 2010 splits the answer: the entity item ``var``, else the country item
    ``abroad``)."""
    def fn(src):
        code = src[var] if abroad is None else src[var].fillna(src[abroad])
        cat = _mapped(code, "personas", name, name)
        return {name: cat.mask(code.eq(src["ENT"]), "EstaEnt")}
    return fn


def _pointer_2010(number: pd.Series, code: pd.Series) -> pd.Series:
    """Censo 2010's pointer pair («en esta vivienda, ¿vive…? ¿Quién es?»: the row number,
    99 when the row was not given, and the code item: 88 not here, 99 not specified) → a
    2020 pointer code: 1 (a row of this dwelling), 96 (not here), 99; blank when both are
    blank (not asked). Any other code becomes -99, which no category takes."""
    out = code.replace({88: 96}).mask(code.isna() & number.notna(), 1)
    return out.where(code.isna() | code.isin([88, 99]), -99)


def _pareja_2010(src):
    code = _pointer_2010(src["IDCONYUGE"], src["IDCONYUGEC"])
    return {"IDENT_PAREJA_CAT": _mapped(code, "personas", "IDENT_PAREJA_CAT",
                                        "IDENT_PAREJA_CAT")}


def _en_vivienda(name: str, item: str, code_item: str | None = None):
    """Whether the mother or father lives in the dwelling, from the 2020 pointer codes: a
    row number 01–54 (Sí), 96–98 another dwelling, dead or unknown (No), 99 (No
    especificado). Censo 2010 (``code_item``) reads its pair through :func:`_pointer_2010`."""
    def fn(src):
        codes = src[item] if code_item is None else _pointer_2010(src[item], src[code_item])
        values = np.select([codes.between(1, 54), codes.isin([96, 97, 98]), codes.eq(99)],
                           ["Sí", "No", "No especificado"], None)
        return {name: _as(values, "personas", name)}
    return fn


def _ingtrhog_cat(src):
    return {"INGTRHOG_CAT": _cut(src["INGTRHOG"], "viviendas", "INGTRHOG_CAT", _INCOME_BINS,
                                 _INCOME_LABELS, right=False, blank=2e6)}


@dataclass(frozen=True)
class _Derivation:
    table: str
    columns: tuple[str, ...]
    sources: tuple[str, ...]
    periods: tuple[str, ...]          # editions whose source codes were verified
    func: Callable[[pd.DataFrame], Mapping[str, pd.Series]]


_NEW = ("2020", "2025")
_OLD = ("2010", "2015")
_SINCE_2015 = ("2015", "2020", "2025")
_ALL = ("2010", "2015", "2020", "2025")
_ESC = ("MED_TRASLADO_ESC1", "MED_TRASLADO_ESC2", "MED_TRASLADO_ESC3")
_TRAB = ("MED_TRASLADO_TRAB1", "MED_TRASLADO_TRAB2", "MED_TRASLADO_TRAB3")
_FIN = ("FINANCIAMIENTO1", "FINANCIAMIENTO2", "FINANCIAMIENTO3")


@functools.cache
def _registry() -> tuple[_Derivation, ...]:
    D = _Derivation
    per, viv = "personas", "viviendas"
    esc15, trab15 = _traslado_2015(_ESC[0]), _traslado_2015(_TRAB[0])
    fin15 = _financiamiento_2015()
    return (
        D(per, ("EDAD_CAT",), ("EDAD",), _ALL, _edad_cat),
        D(per, ("INGTRMEN_CAT",), ("INGTRMEN",), _ALL, _ingtrmen_cat),
        D(per, ("HORTRA_CAT",), ("HORTRA",), ("2010", "2020", "2025"), _hortra_cat),
        D(per, ("EDUC",), ("NIVACAD", "ESCOLARI"), _ALL, _educ),
        D(per, ("OCUPACION_C_COARSE",), ("OCUPACION_C",), _NEW,
          _coarse("OCUPACION_C", "OCUPACION_C_COARSE", 10)),
        D(per, ("ACTIVIDADES_C_COARSE",), ("ACTIVIDADES_C",), _NEW,
          _coarse("ACTIVIDADES_C", "ACTIVIDADES_C_COARSE", 100)),
        D(per, ("DIS_CON", "DIS_LIMI"), _DIS_ITEMS, _NEW, _dis),
        D(per, ("DISCAPACIDAD", "LIMITACION"), _DIS_ITEMS, _NEW, _dis_inegi),
        D(per, ("LIM_ACTIVIDAD",), _DISCAP_ITEMS, ("2010",), _lim_actividad),
        D(per, _dhsersal_names(tuple(_DHSERSAL)), ("DHSERSAL1", "DHSERSAL2"), _NEW,
          _dhsersal(tuple(_DHSERSAL))),
        D(per, _dhsersal_names(_DHSERSAL_NO_BIENESTAR), ("DHSERSAL1", "DHSERSAL2"), _OLD,
          _dhsersal(_DHSERSAL_NO_BIENESTAR)),
        D(per, _dummy_names(per, _ESC, "MED_TRASLADO_ESC"), _ESC, _NEW,
          _dummies(per, _ESC, "MED_TRASLADO_ESC")),
        D(per, _dummy_names(per, _ESC, "MED_TRASLADO_ESC", esc15), _ESC, ("2015",),
          _dummies(per, _ESC, "MED_TRASLADO_ESC", esc15)),
        D(per, _dummy_names(per, _TRAB, "MED_TRASLADO_TRAB"), _TRAB, _NEW,
          _dummies(per, _TRAB, "MED_TRASLADO_TRAB")),
        D(per, _dummy_names(per, _TRAB, "MED_TRASLADO_TRAB", trab15), _TRAB, ("2015",),
          _dummies(per, _TRAB, "MED_TRASLADO_TRAB", trab15)),
        D(per, ("CONACT_CAT",), ("CONACT",), _ALL, _cat(per, "CONACT", "CONACT_CAT")),
        D(per, ("SITUA_CONYUGAL_CAT",), ("SITUA_CONYUGAL",), _ALL,
          _cat(per, "SITUA_CONYUGAL", "SITUA_CONYUGAL_CAT")),
        D(per, ("ENT_PAIS_NAC_CAT",), ("ENT_PAIS_NAC", "ENT"), _SINCE_2015,
          _ent_pais_cat("ENT_PAIS_NAC", "ENT_PAIS_NAC_CAT")),
        D(per, ("ENT_PAIS_NAC_CAT",), ("LNACEDO_C", "LNACPAIS_C", "ENT"), ("2010",),
          _ent_pais_cat("LNACEDO_C", "ENT_PAIS_NAC_CAT", abroad="LNACPAIS_C")),
        D(per, ("ENT_PAIS_RES_CAT",), ("ENT_PAIS_RES_5A", "ENT"), _SINCE_2015,
          _ent_pais_cat("ENT_PAIS_RES_5A", "ENT_PAIS_RES_CAT")),
        D(per, ("ENT_PAIS_RES_CAT",), ("RES05EDO_C", "RES05PAI_C", "ENT"), ("2010",),
          _ent_pais_cat("RES05EDO_C", "ENT_PAIS_RES_CAT", abroad="RES05PAI_C")),
        D(per, ("IDENT_MADRE_CAT",), ("IDENT_MADRE",), _SINCE_2015,
          _cat(per, "IDENT_MADRE", "IDENT_MADRE_CAT")),
        D(per, ("IDENT_PADRE_CAT",), ("IDENT_PADRE",), _SINCE_2015,
          _cat(per, "IDENT_PADRE", "IDENT_PADRE_CAT")),
        D(per, ("IDENT_PAREJA_CAT",), ("IDENT_PAREJA",), _SINCE_2015,
          _cat(per, "IDENT_PAREJA", "IDENT_PAREJA_CAT")),
        D(per, ("IDENT_PAREJA_CAT",), ("IDCONYUGE", "IDCONYUGEC"), ("2010",), _pareja_2010),
        D(per, ("MADRE_EN_VIVIENDA",), ("IDENT_MADRE",), _SINCE_2015,
          _en_vivienda("MADRE_EN_VIVIENDA", "IDENT_MADRE")),
        D(per, ("MADRE_EN_VIVIENDA",), ("IDMADRE", "IDMADREC"), ("2010",),
          _en_vivienda("MADRE_EN_VIVIENDA", "IDMADRE", "IDMADREC")),
        D(per, ("PADRE_EN_VIVIENDA",), ("IDENT_PADRE",), _SINCE_2015,
          _en_vivienda("PADRE_EN_VIVIENDA", "IDENT_PADRE")),
        D(per, ("PADRE_EN_VIVIENDA",), ("IDPADRE", "IDPADREC"), ("2010",),
          _en_vivienda("PADRE_EN_VIVIENDA", "IDPADRE", "IDPADREC")),
        D(per, ("IDENT_HIJO_CAT",), ("IDENT_HIJO",), ("2020",),
          _cat(per, "IDENT_HIJO", "IDENT_HIJO_CAT")),
        D(per, ("RELIGION_CAT",), ("RELIGION",), ("2020",),
          _cat(per, "RELIGION", "RELIGION_CAT")),
        D(viv, ("CLAVIVP_CAT",), ("CLAVIVP",), _SINCE_2015,
          _cat(viv, "CLAVIVP", "CLAVIVP_CAT")),
        D(viv, ("CUADORM_CAT",), ("CUADORM",), _ALL, _cat(viv, "CUADORM", "CUADORM_CAT")),
        D(viv, ("TOTCUART_CAT",), ("TOTCUART",), _ALL, _cat(viv, "TOTCUART", "TOTCUART_CAT")),
        D(viv, ("DRENAJE_CAT",), ("DRENAJE",), _ALL, _cat(viv, "DRENAJE", "DRENAJE_CAT")),
        D(viv, ("INGTRHOG_CAT",), ("INGTRHOG",), _ALL, _ingtrhog_cat),
        D(viv, _dummy_names(viv, _FIN, "FINANCIAMIENTO"), _FIN, _NEW,
          _dummies(viv, _FIN, "FINANCIAMIENTO")),
        D(viv, _dummy_names(viv, ("FINANCIAMIENTO",), "FINANCIAMIENTO", fin15),
          ("FINANCIAMIENTO",), ("2015",),
          _dummies(viv, ("FINANCIAMIENTO",), "FINANCIAMIENTO", fin15)),
    )


@functools.cache
def _derivations(table: str, period: str) -> tuple[_Derivation, ...]:
    if table not in TABLES:
        raise ValueError(f"CPV derived columns exist for {list(TABLES)}, not {table!r}")
    return tuple(d for d in _registry() if d.table == table and period in d.periods)


def cpv_derivations(table: str | None = None, period: str | int | None = None) -> pd.DataFrame:
    """The derived columns and the editions each one is verified for.

    One row per derived column and derivation: ``TABLE``, ``COLUMN``, ``SOURCES`` (the raw
    items it reads) and ``PERIODS`` (a column computed differently in some editions, such
    as the 2015 commute dummies, has one row per way). ``table``/``period`` filter the rows
    (``period``: the columns ``derived=True`` adds to that edition's frame, each once).
    """
    rows = [(d.table, col, ", ".join(d.sources), ", ".join(d.periods))
            for d in _registry() for col in d.columns
            if (table is None or d.table == table)
            and (period is None or str(period) in d.periods)]
    return pd.DataFrame(rows, columns=["TABLE", "COLUMN", "SOURCES", "PERIODS"])


@functools.cache
def derived_dtypes(table: str, period: str | int) -> dict[str, pd.CategoricalDtype]:
    """The dtype of each derived column of ``table`` in ``period`` (all categorical)."""
    out = {}
    for d in _derivations(table, str(period)):
        for col in d.columns:
            if col.startswith(("DHSERSAL_", "MED_TRASLADO_", "FINANCIAMIENTO_")):
                out[col] = _DUMMY
            else:
                out[col] = _DTYPES.get(col) or _legacy_dtypes(table)[col]
    return out


def derived_schema(table: str, period: str | int) -> pa.DataFrameSchema:
    """Pandera schema of the derived columns: their categorical dtype, no missing value."""
    return pa.DataFrameSchema({col: pa.Column(dtype, nullable=False)
                               for col, dtype in derived_dtypes(table, period).items()},
                              strict=False)


def _source(df: pd.DataFrame, name: str) -> str:
    for alias in _ALIASES.get(name, (name,)):
        if alias in df.columns:
            return alias
    raise KeyError(name)


def _codes(raw: pd.Series, recode: Mapping[int, int] | None) -> pd.Series:
    """A raw code column as float codes (blank → NaN), recoded into the 2020 code space."""
    s = raw if pd.api.types.is_numeric_dtype(raw) else \
        pd.to_numeric(raw.astype("string").str.strip().replace("", pd.NA), errors="raise")
    s = s.astype(float)
    if recode:
        s = s.where(~s.isin(list(recode)), s.map(recode))
    return s


def derive(df: pd.DataFrame, table: str, period: str | int) -> pd.DataFrame:
    """``df`` (a raw CPV ``table`` frame of edition ``period``) plus its derived columns.

    Reads the source items' raw codes (zero-padded or not), so call it before labelling;
    the derived columns are ``Categorical`` (0/1 for the dummies). A source code with no
    derived category raises ``ValueError`` (a code the recode table does not know).
    """
    period = str(period)
    derivations = _derivations(table, period)
    if not derivations:
        warnings.warn(f"CPV {table} {period}: no derived columns are verified for this "
                      f"edition (see cpv_derivations()).", stacklevel=2)
    recode = _RECODE.get(period, {})
    clash = [c for d in derivations for c in d.columns if c in df.columns]
    if clash:
        raise ValueError(f"CPV {table} {period}: derived columns already present: {clash}")
    new: dict[str, pd.Series] = {}
    problems: dict[str, list] = {}
    cache: dict[str, pd.Series] = {}
    for d in derivations:
        try:
            cols = {s: _source(df, s) for s in d.sources}
        except KeyError as exc:
            raise ValueError(f"CPV {table} {period}: {d.columns[0]} needs {exc.args[0]!r}, "
                             f"absent from the frame") from None
        for s, col in cols.items():
            if s not in cache:
                cache[s] = _codes(df[col], recode.get(s))
        src = pd.DataFrame({s: cache[s] for s in cols}, index=df.index)
        for name, values in d.func(src).items():
            values = pd.Series(values, index=df.index) if not isinstance(values, pd.Series) \
                else values.set_axis(df.index)
            if values.isna().any():
                bad = src.loc[values.isna().to_numpy()].drop_duplicates().head(12)
                problems[name] = bad.to_dict("records")
            new[name] = values
    if problems:
        raise ValueError(f"CPV {table} {period}: source codes without a derived category "
                         f"(add them to cpv_derived._RECODE): {problems}")
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# --- constraints per edition ---------------------------------------------------------------

def _period_gid(table: str, period: str) -> str:
    from mxcensus._resources import cpv_schema_map

    for gid, group in cpv_schema_map()[table]["groups"].items():
        if period in [str(p) for p in group["periods"]]:
            return gid
    raise ValueError(f"no CPV {table} schema group for {period}")


@functools.cache
def _relabels(table: str) -> dict[str, dict[str, str]]:
    """Legacy label → the Censo 2020 FD label, for the constrained items whose legacy
    dictionary words them differently (matched through their shared codes)."""
    from mxcensus.cpv import variables_cpv_labels

    fd = variables_cpv_labels(table, _period_gid(table, "2020"))
    out: dict[str, dict[str, str]] = {}
    for var in {v for c in _base_constraints(table).values() for v in (c or {})}:
        meta = fd.get(var)
        if not meta or var not in _variables(table):
            continue
        fd_labels = {int(k): v for k, v in {**(meta.get("Categorías") or {}),
                                            **(meta.get("Especiales") or {})}.items()
                     if str(k).lstrip("-").isdigit()}
        pairs = {old: fd_labels[code] for code, old in _legacy_map(table, var).items()
                 if code in fd_labels and fd_labels[code] != old}
        if pairs:
            out[var] = pairs
    return out


def _base_constraints(table: str) -> dict:
    if table not in TABLES:
        raise ValueError(f"CPV constraints exist for {list(TABLES)}, not {table!r}")
    return constraints_personas() if table == "personas" else constraints_viviendas()


# Indicators whose CPV cells replace the legacy ones: INEGI's disability definitions.
_CELLS = {"personas": {"PCON_DISC": {"DISCAPACIDAD": ["Sí"]},
                       "PCON_LIMI": {"LIMITACION": ["Sí"]}}}

# Indicators an edition publishes under its own definition, on its own items: Censo 2010's
# limitation in activity (its PCLIM_VIS/PCLIM_MOT2 share 2020's names, not their concept).
_EDITION_CELLS = {
    ("personas", "2010"): {
        "PCON_LIM": {"LIM_ACTIVIDAD": ["Sí"]},
        "PSIN_LIM": {"LIM_ACTIVIDAD": ["No"]},
        "PCLIM_MOT": {"DISCAP1": ["Caminar, moverse, subir o bajar"]},
        "PCLIM_VIS": {"DISCAP2": ["Ver, aun usando lentes"]},
        "PCLIM_LENG": {"DISCAP3": ["Hablar, comunicarse o conversar"]},
        "PCLIM_AUD": {"DISCAP4": ["Oír, aun usando aparato auditivo"]},
        "PCLIM_MOT2": {"DISCAP5": ["Vestirse, bañarse o comer"]},
        "PCLIM_MEN": {"DISCAP6": ["Poner atención o aprender cosas sencillas"]},
        "PCLIM_MEN2": {"DISCAP7": ["Limitación mental"]},
    },
}


@functools.cache
def _cpv_constraints(table: str) -> dict:
    """The legacy constraints in the CPV vocabulary: neutral DHSERSAL names, FD labels,
    INEGI's disability flags (:data:`_CELLS`)."""
    relabel = _relabels(table)
    out = {}
    for ind, cells in _base_constraints(table).items():
        out[ind] = {DHSERSAL_RENAMES.get(var, var): [relabel.get(var, {}).get(c, c) for c in cats]
                    for var, cats in (cells or {}).items()}
    out.update(_CELLS.get(table, {}))
    return out


@functools.cache
def _aggregate_indicators(period: str, comparable: bool = True) -> frozenset[str]:
    """The indicators an edition publishes: its ITER's (through the crosswalk; an older
    edition's only where comparable, unless ``comparable=False``) or, for the EIC 2025,
    its national estimates'."""
    from mxcensus._resources import cpv_iter_crosswalk
    from mxcensus.data._cpv_catalog import get_edition

    edition = get_edition(period)
    if edition.has("iter"):
        # ``Comparable: false`` flags the older editions' columns of that name, never the
        # newest edition's own (the canonical definition).
        return frozenset(ind for ind, e in cpv_iter_crosswalk().items()
                         if e.get(period) and (not comparable
                                               or e.get("Comparable", True) is not False
                                               or period == max(k for k in e if k.isdigit())))
    if edition.has("estimaciones"):
        from mxcensus._resources import cpv_schema_map

        groups = cpv_schema_map()["estimaciones"]["groups"]
        return frozenset(c for g in groups.values() if period in [str(p) for p in g["periods"]]
                         for c in g["columns"])
    return frozenset()


def _categories(table: str, period: str) -> dict[str, tuple]:
    """Each categorical column of the labelled (``derived=True``) frame → its categories."""
    from mxcensus import _schema_groups as _sg
    from mxcensus.cpv import variables_cpv_labels

    out = {}
    for col, meta in variables_cpv_labels(table, _period_gid(table, period)).items():
        if _sg.norm_tipo(meta) == "categorical":
            out[col] = tuple(_sg._categorical_dtype(meta).categories)
    out.update({col: tuple(dt.categories) for col, dt in derived_dtypes(table, period).items()})
    return out


def cpv_constraints(table: str, period: str | int) -> dict:
    """The census constraints an edition can reproduce from its microdata.

    The legacy sets (``constraints_personas``/``constraints_viviendas``: Censo 2020 ITER
    indicator → the microdata cells it counts) in the CPV vocabulary — the neutral
    ``DHSERSAL_*`` names, the Censo 2020 dictionary's labels, ``PCON_DISC``/``PCON_LIMI``
    on INEGI's ``DISCAPACIDAD``/``LIMITACION`` flags — keeping the indicators that
    (1) the edition publishes (its ITER, through ``cpv_iter_crosswalk`` — for 2010 only
    the indicators comparable with 2020's —; the EIC 2025's national estimates) and (2)
    whose variables and
    categories all exist in the edition's labelled frame with ``derived=True``. EIC 2015
    publishes neither, so it has none. An edition's own definitions (Censo 2010's
    limitation in activity: ``PCON_LIM``, ``PSIN_LIM``, ``PCLIM_*`` on ``LIM_ACTIVIDAD``
    and ``DISCAP1``–``DISCAP7``) are added when it publishes the indicator. Feed the
    result and the frame's dtypes to :func:`mxcensus.get_tables_dict`.
    """
    period = str(period)
    own = _EDITION_CELLS.get((table, period), {})
    published = _aggregate_indicators(period) | (
        own.keys() & _aggregate_indicators(period, comparable=False))
    cats = _categories(table, period)
    return {ind: cells for ind, cells in {**_cpv_constraints(table), **own}.items()
            if ind in published
            and all(var in cats and set(c) <= set(cats[var]) for var, c in cells.items())}
