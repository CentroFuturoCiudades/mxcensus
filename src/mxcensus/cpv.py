"""CPV family (censos, conteos y encuestas intercensales 1990–2025) — microdata loaders.

The family is mirrored as ``cpv_{table}_{period}_{NN}.parquet`` (per-state microdata) and
``cpv_{table}_{period}.parquet`` (national aggregates), faithful raw: every column a
string, only empty cells null (see ``mxcensus.data._cpv_catalog``, ``scripts/build_cpv.py``
and ``docs/cpv/PLAN.md``). Like ENOE/ENIGH, every mirrored file is fingerprinted into a
**per-table** schema group (``_yaml/cpv_schema_map.yaml``) and validated against a tight
Pandera schema built from that group's ``variables_cpv_{table}_{gid}.yaml``.

Editions built so far: the **Encuesta Intercensal 2025** (``viviendas``, ``personas``,
``migrantes`` per state; ``estimaciones`` national — see :mod:`mxcensus.cpv_aggregates`),
the **Censo de Población y Vivienda 2020** (the cuestionario ampliado's ``viviendas``,
``personas``, ``migrantes`` and the ``iter``/``ageb`` aggregates, per state; raw names as
INEGI spells them — ``ENT``/``MUN`` in the microdata, ``ENTIDAD``/``MUN``/``LOC`` in the
aggregates), the **Encuesta Intercensal 2015** (``viviendas`` and ``personas`` per state,
no migrant table; ``ENT``/``MUN`` as in 2020, keys and most codes written without their
zero-padding), the **Censo 2010** cuestionario ampliado (DBF; keys unique within a state
only), the **CGPV 2000** muestra censal (its dwelling file has one row per household;
``migrantes``), the **Conteo 2005** sample (``viviendas``, ``hogares``, ``personas``;
no expansion factor), the **Conteo 1995** sample (``personas`` with the dwelling and
household items on each person, ``migrantes``; weights ``FAC_POB``/``FAC_VIV``/
``FAC_PROM``) and the **CGPV 1990** 10% extract (``personas`` only, unweighted). 1990–2005
carry no key column: the keyed loaders derive ``ID_VIV``/``ID_HOG``/``ID_PERSONA``/
``ID_MII`` from the composite parts (:func:`_composite_keys`), and the 1995–2005 indices
carry the household (``ID_HOG``).

Public API:

- :func:`load_cpv` — one raw table (faithful ``dtype=str`` frame) for one edition and one
  or more states.
- :func:`load_cpv_viviendas` / :func:`load_cpv_hogares` (Conteo 2005) /
  :func:`load_cpv_personas` / :func:`load_cpv_migrantes` — analysis-ready frames: numeric
  ``FACTOR``, labelled columns, indexed by the level key.
- :func:`load_cpv_survey` — ``(viviendas, personas, migrantes)`` with a shared nested
  index: persons and international emigrants both hang from the dwelling (``ID_VIV``).
- :func:`variables_cpv_labels` — the labelling dictionary of one ``(table, schema group)``.

``state`` is an INEGI state code (1–32) or a sequence of them. The microdata are mirrored
per state, so it is required there (no accidental multi-GB fetch); a sequence loads the
states one by one and concatenates them. On a national table it filters rows on
``CVE_ENT``.

``harmonize=True`` applies the cross-edition **core** canonicalization (:func:`_harmonize`):
upper-case names, the core renames (2015/2020 ``ENT``/``MUN`` → ``CVE_ENT``/``CVE_MUN``; in
the ITER/AGEB also ``ENTIDAD``/``LOC``/``AGEB``/``MZA`` → ``CVE_ENT``/``CVE_LOC``/``CVE_AGEB``/
``CVE_MZA``), zero-padded geography, keys and ``CLAVIVP`` (2015 writes ``ID_VIV`` without
the leading zero of states 01–09 and ``CLAVIVP`` as ``1``…``9``), ``CVEGEO`` derived or
checked, numeric ``FACTOR``; every other column is kept verbatim. For 2025 — the canonical
edition — it changes nothing but the ``FACTOR`` dtype.

Each call loads **one edition**. To stack editions, load each with ``harmonize=True`` and
concatenate, keeping the edition as an index level::

    frames = {p: load_cpv_personas(p, state=1, harmonize=True, labels=False)
              for p in (2020, 2025)}
    personas = pd.concat(frames, names=["PERIOD"])

Only the core columns are comparable across editions; the other items keep each edition's
own spelling and codes (see ``variables_cpv(table, gid)``).
"""
from __future__ import annotations

import functools
import itertools
import numbers
import warnings
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from mxcensus import _schema_groups as _sg
from mxcensus import cpv_derived as _derived
from mxcensus._resources import (
    cpv_iter_crosswalk,
    cpv_schema_map,
    variables_cpv,
    variables_cpv_core,
)
from mxcensus.data._cpv_catalog import (
    NATIONAL_TABLES,
    TABLES,
    CpvEdition,
    cpv_filename,
    get_edition,
    latest_edition,
)

# Expansion weight — validated as numeric.
_WEIGHTS = {"FACTOR", "FAC_POB", "FAC_VIV", "FAC_PROM"}   # Conteo 1995: three estimators
# The Conteo 1995's estimator for each table's unit, copied to ``FACTOR`` by
# ``harmonize=True`` (FAC_PROM, for health coverage and disability, has no FACTOR copy).
_FACTOR_FROM = {"personas": "FAC_POB", "migrantes": "FAC_VIV", "viviendas": "FAC_VIV"}

# CGPV 1990 and the Conteo 1995 publish one person file each, with the dwelling's items on
# every person (1995: the household's too). Their dwelling frame (load_cpv_viviendas) is
# built from it: one row per ID_VIV, these columns of its first person (constant within a
# dwelling, but for one 1990 dwelling: STEP_5b.md). The Conteo's dwellings are weighted by
# FAC_VIV; 1990's 10% extract is unweighted.
_DWELLINGS_FROM_PERSONS: dict[str, tuple[str, ...]] = {
    "1990": ("TAM_LOC", "FOLIO_VIV", "ENT", "MUN", "T_VIV", "PAREDES", "TECHOS", "PISOS",
             "P_DORMIR", "T_CUARTOS", "CUA_EXCLU", "TAM_DUERME", "TIE_EXCU", "CON_AGUA",
             "AGUA_ENTU", "DRENAJE", "ELECTRI", "COMBUS", "TENENCIA", "NUM_PERS", "F_G_COC",
             "N_F_GPOS"),
    "1995": ("ENT", "ZONA", "ESTRATO", "TAM_LOC", "MUN", "UPM", "VIV", "FAC_VIV", "P1_1",
             "P1_2", "P1_3", "P1_4", "P1_5", "P1_6", "P1_7", "P1_8", "P1_9", "P1_10", "P1_11",
             "P1_13", "P1_16", "P1_17", "P1_18", "P2_2", "P2_3"),
}

# Keys and geographic codes: digit strings (their width is edition-specific, so only the
# all-digits shape is checked here; key widths are checked by the data tests). CPV 2020
# spells the microdata geography ENT/MUN and the aggregates' ENTIDAD/MUN/LOC/MZA.
_DIGIT_CODES = frozenset({"ID_VIV", "ID_HOG", "ID_PERSONA", "ID_MII", "ID_PER", "ID_MIN",
                          "CVEGEO",
                          "CVE_ENT", "CVE_MUN", "LOC50K", "CVE_LOC", "CVE_MZA", "ENT", "MUN",
                          "ENTIDAD", "LOC", "MZA"})
# Coded strings with their own shape: the urban AGEB key is three digits and a check
# character (0-9 or A-P); 0000 marks the ITER/AGEB total rows.
_AGEB_RE = r"\d{3}[0-9A-P]"
_CODE_REGEX = {"AGEB": rf"^{_AGEB_RE}$", "CVE_AGEB": rf"^{_AGEB_RE}$"}

# Record keys (alias tuples: canonical name first, then the CPV 2010 spellings). Persons
# and international emigrants are siblings under the dwelling, so both keys extend the
# dwelling key and the three frames of :func:`load_cpv_survey` align on ``ID_VIV``. CPV
# 2010's raw keys are serials unique within a state only (``ID_VIV`` 8 digits, ``ID_PER``
# 9, ``ID_MIN`` 7): one state per raw keyed call, or ``harmonize=True``, which builds
# national keys nested like 2020's (:func:`_national_keys`). CGPV 2000 and Conteo 2005
# carry no key column at all: the keyed loaders derive ``ID_VIV``/``ID_HOG``/
# ``ID_PERSONA``/``ID_MII`` from their composite parts (:func:`_composite_keys`). Only
# those two editions have a household level, so ``ID_HOG`` (absent elsewhere) drops out of
# the 2010-2025 keys (:func:`mxcensus._schema_groups.level_key`). CGPV 2000's dwelling file
# has one row per household (dwelling items repeated), so its rows are keyed
# ``(ID_VIV, ID_HOG)``; Conteo 2005 has a separate household table (``hogares``).
_DWELLING_KEY_SPEC: list[tuple[str, ...]] = [("ID_VIV",)]
_HOUSEHOLD_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("ID_HOG",)]
_PERSON_KEY_SPEC: list[tuple[str, ...]] = _HOUSEHOLD_KEY_SPEC + [("ID_PERSONA", "ID_PER")]
_MIGRANT_KEY_SPEC: list[tuple[str, ...]] = _HOUSEHOLD_KEY_SPEC + [("ID_MII", "ID_MIN")]
_KEY_SPEC: dict[str, list[tuple[str, ...]]] = {
    "viviendas": _HOUSEHOLD_KEY_SPEC,       # ID_VIV; (ID_VIV, ID_HOG) for CGPV 2000
    "hogares": _HOUSEHOLD_KEY_SPEC,
    "personas": _PERSON_KEY_SPEC,
    "migrantes": _MIGRANT_KEY_SPEC,
}
# Key components a table need not carry: the household exists in 2000/2005 only.
_OPTIONAL_KEYS = {"viviendas": {"ID_HOG"}, "personas": {"ID_HOG"}, "migrantes": {"ID_HOG"}}
# (1990 has no household level either: its ID_HOG is absent, like 2010-2025's.)

# The composite parts of the 2000/2005 records (raw names; the entity and municipality also
# under their harmonized names), from which :func:`_composite_keys` derives the keys, each
# part zero-padded to its width so the concatenation is unambiguous:
# - CGPV 2000: dwelling = ENT + MUN + LOC + NUMVIV (NUMVIV restarts in every locality),
#   household = NUMHOG; persons are not numbered (the file lists each household's members
#   together, not in questionnaire order), so a person is its order in the file within the
#   household; an emigrant = MPER (numbered within the household).
# - Conteo 1995: dwelling = ENT + MUN + ZONA + UPM + VIV (padded to 3: 12 digits), household
#   = HOGAR, person = P3_1, emigrant = P9_1 (the person file datgen95; migint95).
# - CGPV 1990: one person file; dwelling = ENT + FOLIO_VIV (padded to 9) + the folio's
#   occurrence in file order (a few folios are reused within a state): 12 digits; no
#   household; person = NUM_PER.
# - Conteo 2005: dwelling = ENT + MUN + CONS_MUN (a 6-digit serial within the municipality,
#   padded to 7 so ID_VIV has the 12 digits of 2010-2025 and harmonize=True's ID_VIV padding
#   is a no-op — idempotent; CONS_VIV is not a key), household = CONS_HOG, person = CONS_PER
#   (numbered within the household).
_COMPOSITE_KEYS: tuple[dict, ...] = (
    {"dwelling": ((("CVE_ENT", "ENT"), 2), (("CVE_MUN", "MUN"), 3), (("LOC",), 4),
                  (("NUMVIV",), 6)),
     "household": ("NUMHOG", 2), "person": (None, 2), "migrant": ("MPER", 2)},
    {"dwelling": ((("CVE_ENT", "ENT"), 2), (("CVE_MUN", "MUN"), 3), (("CONS_MUN",), 7)),
     "household": ("CONS_HOG", 2), "person": ("CONS_PER", 4), "migrant": (None, 2)},
    {"dwelling": ((("CVE_ENT", "ENT"), 2), (("CVE_MUN", "MUN"), 3), (("ZONA",), 2),
                  (("UPM",), 2), (("VIV",), 3)),
     "household": ("HOGAR", 2), "person": ("P3_1", 2), "migrant": ("P9_1", 2)},
    {"dwelling": ((("CVE_ENT", "ENT"), 2), (("FOLIO_VIV",), 9)), "occurrence": True,
     "household": (None, 2), "person": ("NUM_PER", 4), "migrant": (None, 2)},
)
# The raw identifiers those keys are built from (left as strings by labels=True). CONS_VIV
# (2005) is the dwelling's number in its listing, not part of the key.
_KEY_PARTS = ("NUMVIV", "NUMHOG", "CONS_MUN", "CONS_VIV", "CONS_HOG", "CONS_PER",
              "FOLIO_VIV", "NUM_PER", "VIV", "HOGAR", "P3_1", "P9_1")

# Columns ``labels=True`` leaves as raw strings: the keys and geographic codes (joinable
# across tables and with the Marco Geoestadístico), and the person-number pointers — a
# person's number in the dwelling's list (``NUMPER``) and the fields that point at one
# (mother, father, partner, the dwelling's or — 2015 — the farmland's owners, a returned
# emigrant's own record), so ``(ID_VIV, IDENT_MADRE)`` joins ``(ID_VIV, NUMPER)`` directly.
# Person numbers 01-54 are their own labels (2015: the numbers 1-54); the codes from 96 up
# (lives elsewhere, deceased, no partner, not a resident, don't know, not specified) are
# documented in the dictionary. CPV 2010 spells them IDMADRE/IDPADRE/IDCONYUGE (01-98; its
# 88 "lives elsewhere" is a separate IDMADREC/… column) and names the informant (NUMINF).
_GEO_CODES = ("CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "CVE_LOC", "CVE_AGEB", "CVE_MZA",
              "ENT", "MUN", "ENTIDAD", "LOC", "AGEB", "MZA")
_POINTERS = ("NUMPER", "IDENT_MADRE", "IDENT_PADRE", "IDENT_PAREJA", "DUE1_NUM", "DUE2_NUM",
             "MPER", "MPERLS", "NUM_DUE_VIV1", "NUM_DUE_VIV2", "NUM_DUE_TERR", "IDMADRE",
             "IDPADRE", "IDCONYUGE", "NUMINF")
_KEY_COLUMNS = frozenset(c for spec in _KEY_SPEC.values() for aliases in spec for c in aliases)
_SKIP = _KEY_COLUMNS | frozenset(_GEO_CODES) | frozenset(_POINTERS) | frozenset(_KEY_PARTS)


def _fingerprint(columns) -> str:
    """Schema-group fingerprint (shared recipe, see :mod:`mxcensus._schema_groups`)."""
    return _sg.fingerprint(columns)


def _code_rule(col: str, meta: dict) -> pa.Column | None:
    """Raw-string rule for a coded string column: a key/geographic code → digits; a code
    from a classification catalog too large to enumerate (``Catálogo`` + string ``Tipo``:
    occupation, activity, country, municipality, language) → exactly ``Longitud`` digits.
    ``None`` for any other column. Names match case-insensitively (CPV 2010's ITER/AGEB
    headers are lower case)."""
    name = col.upper()
    if name in _CODE_REGEX:
        return _sg.raw_column(pa.Check.str_matches(_CODE_REGEX[name]))
    if name in _DIGIT_CODES:
        return _sg.raw_column(pa.Check.str_matches(r"^\d+$"))
    width = str(meta.get("Longitud") or "").strip()
    if meta.get("Catálogo") and _sg.norm_tipo(meta) == "string" and width.isdigit():
        return _sg.raw_column(pa.Check.str_matches(rf"^\d{{{width}}}$"))
    return None


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one CPV ``(table, schema group)``'s raw frame (weights →
    numeric, ``Categorías`` → strict ``isin``, numerics → number in ``Rango`` or sentinel,
    coded strings → :func:`_code_rule`, else nullable string)."""
    cols = cpv_schema_map()[table]["groups"][gid]["columns"]
    variables = variables_cpv(table, gid)
    return _sg.build_group_schema(cols, variables, weights=_WEIGHTS,
                                  column_rule=lambda c: _code_rule(c, variables.get(c) or {}))


def _in_scope(meta: dict, table: str, periods: Iterable | None = None) -> bool:
    """Whether a core entry applies to ``table`` — its ``Tablas`` list, else every table
    that has the column (the ITER's ``TAMLOC`` is a 14-class size scale, not the microdata's
    five classes) — and to the editions ``periods`` (a schema group's): its ``Periodos``
    list, the editions whose codes it was verified for, else every edition (CPV 2010's
    ``CLAVIVP`` is another classification). ``periods=None`` checks the table only."""
    if table not in (meta.get("Tablas") or (table,)):
        return False
    editions = {str(p) for p in meta.get("Periodos") or ()}
    return not editions or periods is None or {str(p) for p in periods} <= editions


def _group_periods(table: str, gid: str) -> tuple[str, ...] | None:
    """The editions a schema group covers (``cpv_schema_map``); ``None`` for a group the
    map does not know (then no edition-specific rule applies)."""
    group = (cpv_schema_map().get(table) or {}).get("groups", {}).get(gid)
    return tuple(group["periods"]) if group else None


def _scoped_entry(meta: dict, periods: Iterable | None = None) -> dict:
    """A core entry as it applies to the editions ``periods``: an edition's
    ``Recodificar`` map (its own spelling of a code, e.g. 2000/2005 ``SEXO`` 2 = mujer)
    joins the entry's ``Alias``; the key itself is dropped. Unchanged for ``periods=None``
    or editions without a recode."""
    recode = meta.get("Recodificar")
    if not recode:
        return meta
    out = {k: v for k, v in meta.items() if k != "Recodificar"}
    maps = [recode.get(str(p)) or {} for p in (periods or ())]
    if any(maps):
        alias = dict(meta.get("Alias") or {})
        for m in maps:
            alias.update({str(k): str(v) for k, v in m.items()})
        out["Alias"] = alias
    return out


def _core_for(table: str, periods: Iterable | None = None) -> dict:
    """The core entries that apply to ``table`` in ``periods`` (:func:`_in_scope`), each as
    it applies to those editions (:func:`_scoped_entry`)."""
    return {c: _scoped_entry(m, periods) for c, m in variables_cpv_core().items()
            if _in_scope(m, table, periods)}


def _group_of(table: str, df: pd.DataFrame) -> str:
    """Resolve a loaded frame to its per-table schema group id (raises if unknown)."""
    return _sg.group_of("CPV", cpv_schema_map().get(table), df.columns,
                        map_name="cpv_schema_map.yaml", unit="edition")


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise."""
    _sg.validate_warn("CPV", schema, frame, label)


# ---------------------------------------------------------------------------------------
# Cross-edition harmonization (``harmonize=True``)
# ---------------------------------------------------------------------------------------
# Only the core is canonicalized, onto the latest edition's (upper-case) spelling, which is
# also the Marco Geoestadístico's (CVE_ENT/CVE_MUN/CVE_LOC/CVE_AGEB/CVE_MZA, CVEGEO); every
# other column stays verbatim — questionnaire items change codes across editions and must
# not be renamed blindly. A rename joins only once its codes are verified in every edition
# it covers (docs/cpv/PLAN.md §Harmonization): CPV 2020 spells the microdata geography
# ENT/MUN (same codes, zero-padded as 2025's). The aggregates spell the entity ENTIDAD and
# the locality LOC, names a future microdata table may use for something else, so those
# renames are scoped to the ITER/AGEB (as ENIGH's per-table map). EIC 2015 and CPV 2010
# spell the microdata geography as 2020 does (ENT/MUN, zero-padded). CPV 2010's
# TAM_LOC is NOT renamed onto TAMLOC: it has four classes (15 000-99 999 inhabitants in one)
# where 2015-2025 have five. Its keys are rebuilt instead of renamed (_national_keys).
_RENAME_CORE: dict[str, str] = {"ENT": "CVE_ENT", "MUN": "CVE_MUN"}
_RENAME_AGG: dict[str, str] = {"ENTIDAD": "CVE_ENT", "LOC": "CVE_LOC"}
_RENAME_TABLE: dict[str, dict[str, str]] = {
    "iter": _RENAME_AGG,
    "ageb": {**_RENAME_AGG, "AGEB": "CVE_AGEB", "MZA": "CVE_MZA"},
}
_GEO_PAD: dict[str, int] = {"CVE_ENT": 2, "CVE_MUN": 3, "LOC50K": 4, "CVE_LOC": 4,
                            "CVE_AGEB": 4, "CVE_MZA": 3}
# Other core codes zero-padded to their canonical width (``zfill`` only lengthens, so it is a
# no-op on editions already padded). The EIC 2015 CSVs write numbers without their leading
# zeros: ``ID_VIV`` has 11 digits in states 01-09 (its FD documents 12,
# ``{010010000001..}``) and ``ID_PERSONA`` = ``ID_VIV`` + a 2-digit person number has 13
# (14 elsewhere; 2020/2025 person keys have 17 digits); ``CLAVIVP`` is ``1``…``9`` (its core
# ``Alias`` maps those spellings for labelling and validation).
# A column is padded only for the editions its core entry covers (``Periodos``): CPV 2010's
# CLAVIVP 1…9 is another classification, not the 01…09 written short.
_CODE_PAD: dict[str, int] = {"ID_VIV": 12, "ID_PERSONA": 14, "CLAVIVP": 2}
# Editions whose raw keys are unique within a state only.
_STATE_SCOPED_KEYS = frozenset({"2010"})
# CVEGEO is the concatenation of the leading geographic parts a table carries, as in the
# Marco Geoestadístico: entity + municipality in the microdata (5 characters), + locality
# in the estimaciones and the ITER (9), + AGEB + block in the AGEB file (16). Total rows
# keep their zero parts (00/000/0000/0000/000), so CVEGEO is unique per aggregate row and a
# block's CVEGEO is the MG manzana's; an AGEB-level row's MG key is its first 13 characters.
_GEO_PARTS: tuple[str, ...] = ("CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB", "CVE_MZA")
_GEO_REGEX: dict[str, str] = {
    "CVE_ENT": r"^\d{2}$", "CVE_MUN": r"^\d{3}$", "LOC50K": r"^\d{4}$", "CVE_LOC": r"^\d{4}$",
    "CVE_AGEB": rf"^{_AGEB_RE}$", "CVE_MZA": r"^\d{3}$",
    "CVEGEO": rf"^\d{{5}}(\d{{4}}({_AGEB_RE}(\d{{3}})?)?)?$",
}


@functools.cache
def _crosswalk_renames(table: str, periods: tuple[str, ...] | None = None) -> dict[str, str]:
    """Older ITER/AGEB spellings that harmonize=True renames onto the canonical indicator:
    the editions an entry lists under ``Renombrar`` in ``cpv_iter_crosswalk.yaml`` (CPV 2010
    ``TAM_LOC`` → ``TAMLOC``; Conteo 2005 ``P_TOTAL`` → ``POBTOT``…). Only the editions in
    ``periods`` (a frame's; ``None`` = every edition), since one edition's old name may be
    another's indicator."""
    out: dict[str, str] = {}
    for canon, entry in cpv_iter_crosswalk().items():
        editions = entry.get("Renombrar") or ()
        if editions is True:                         # legacy spelling: every edition
            editions = [k for k in entry if str(k).isdigit()]
        if table not in (entry.get("Tablas") or ()):
            continue
        for period in editions:
            src = entry.get(str(period))
            if src and src != canon and (periods is None or str(period) in periods):
                out[src] = canon
    return out


def _renames(table: str, periods: Iterable | None = None) -> dict[str, str]:
    """The core renames that apply to ``table``: :data:`_RENAME_CORE` plus the table's own
    (:data:`_RENAME_TABLE`) and, for the census aggregates, the crosswalk's for the
    editions ``periods`` (:func:`_crosswalk_renames`)."""
    key = None if periods is None else tuple(sorted(str(p) for p in periods))
    extra = _crosswalk_renames(table, key) if table in _RENAME_TABLE else {}
    return {**_RENAME_CORE, **_RENAME_TABLE.get(table, {}), **extra}


def _zfill_codes(s: pd.Series, width: int) -> pd.Series:
    digits = s.str.fullmatch(r"\d+").fillna(False).astype(bool)
    return s.where(~digits, s.str.zfill(width))


def _required(table: str) -> set[str]:
    """Canonical columns a harmonized ``table`` frame must carry: the entity and the
    table's record key (the household key only where every edition has it)."""
    keys = {aliases[0] for aliases in _KEY_SPEC.get(table, [])}
    return {"CVE_ENT", *(keys - _OPTIONAL_KEYS.get(table, set()))}


def _composite_keys(out: pd.DataFrame, table: str) -> pd.DataFrame:
    """Derive ``ID_VIV``, ``ID_HOG`` and the person (``ID_PERSONA``) or emigrant
    (``ID_MII``) key from the composite parts of a 1990–2005 ``table`` frame
    (:data:`_COMPOSITE_KEYS`), inserted as the first columns; raw or harmonized names.

    ``ID_VIV`` = the dwelling parts concatenated (2000: 15 digits; 1990, 1995, 2005: 12 —
    the first two are the entity); ``ID_HOG`` = ``ID_VIV`` + the 2-digit household number
    (1995–2005); ``ID_PERSONA`` = ``ID_HOG`` (1990: ``ID_VIV``) + the person number (1990
    ``NUM_PER``, 1995 ``P3_1``, 2005 ``CONS_PER``; 2000: the 2-digit order of the person
    within the household in file order); ``ID_MII`` = ``ID_HOG`` + the emigrant number
    (2000 ``MPER``, 1995 ``P9_1``). CGPV 1990 reuses a few ``FOLIO_VIV`` within a state, so
    its ``ID_VIV`` ends in the dwelling's occurrence of that folio, in file order (a new
    dwelling starts where the folio changes or ``NUM_PER`` starts again). Orders in file
    order need the mirror's row order. Every raw column is kept. A frame that already has
    ``ID_VIV`` (2010-2025, or a frame already derived) or lacks the parts is returned
    unchanged.
    """
    if "ID_VIV" in out.columns or table not in _KEY_SPEC:
        return out
    for spec in _COMPOSITE_KEYS:
        parts = [(next((c for c in names if c in out.columns), None), width)
                 for names, width in spec["dwelling"]]
        if any(col is None for col, _ in parts):
            continue
        base = functools.reduce(lambda a, b: a + b, (out[c].str.zfill(w) for c, w in parts))
        (per, pwidth), (mig, mwidth) = spec["person"], spec["migrant"]
        if spec.get("occurrence"):
            base = base + _folio_occurrence(base, out[per]).astype(str)
        keys = {"ID_VIV": base}
        hog, width = spec["household"]
        parent = keys["ID_VIV"]
        if hog is not None and hog in out.columns:
            parent = keys["ID_HOG"] = keys["ID_VIV"] + out[hog].str.zfill(width)
        if table == "personas" and per is None and "ID_HOG" in keys:
            rank = parent.groupby(parent, sort=False).cumcount() + 1
            keys["ID_PERSONA"] = parent + rank.astype(str).str.zfill(pwidth)
        elif table == "personas" and per in out.columns:
            keys["ID_PERSONA"] = parent + out[per].str.zfill(pwidth)
        elif table == "migrantes" and mig is not None and mig in out.columns:
            keys["ID_MII"] = parent + out[mig].str.zfill(mwidth)
        out = out.copy()
        for k, (name, col) in enumerate(keys.items()):
            out.insert(k, name, col)
        return out
    return out


def _folio_occurrence(folio: pd.Series, person: pd.Series) -> pd.Series:
    """Which dwelling of a reused folio each row belongs to, in file order (0, 1, …).

    CGPV 1990 numbers dwellings by a folio unique within the state, except a few folios
    INEGI used twice or more (729 of 8.1 million person rows; some rows are exact
    duplicates). Its persons are listed dwelling by dwelling but not in ``NUM_PER`` order.
    So a dwelling is a run of rows with one folio, split again wherever a person number
    repeats within the run; the blocks of a folio are numbered in file order."""
    run = (folio != folio.shift()).cumsum()
    frame = pd.DataFrame({"run": run.to_numpy(), "num": person.to_numpy()}, index=folio.index)
    block = pd.Series(0, index=folio.index)
    for r in frame.loc[frame.duplicated(["run", "num"]), "run"].unique():   # rare runs
        rows = frame.index[frame["run"].to_numpy() == r]
        seen, k = set(), 0
        for i in rows:
            if frame.at[i, "num"] in seen:
                k, seen = k + 1, set()
            seen.add(frame.at[i, "num"])
            block.at[i] = k
    key = run.astype(str) + "_" + block.astype(str)
    first = ~key.duplicated()
    occ = pd.Series(pd.NA, index=folio.index, dtype="Int64")
    occ[first] = folio[first].groupby(folio[first], sort=False).cumcount()
    occ = occ.groupby(key, sort=False).transform("first")
    if occ.max() > 9:
        raise ValueError(f"CPV: a dwelling folio occurs {int(occ.max()) + 1} times")
    return occ.astype(int)


def _national_keys(out: pd.DataFrame, table: str) -> pd.DataFrame:
    """CPV 2010's keys made national and nested like 2020's (harmonized frames only).

    The raw keys are serials unique within a state: ``ID_VIV`` (8 digits), ``ID_PER`` (9)
    and ``ID_MIN`` (7). The harmonized ``ID_VIV`` is the entity followed by the serial
    zero-padded to 10 digits (12 in all, first two the entity, as in 2015-2025);
    ``ID_PERSONA`` = ``ID_VIV`` + the 5-digit ``NUMPER`` (unique within the dwelling: 17
    digits, as in 2020/2025); ``ID_MII`` = ``ID_VIV`` + the emigrant's 2-digit rank in the
    dwelling by ``ID_MIN`` (2010's ``MPERA`` repeats within a dwelling). ``ID_PER`` and
    ``ID_MIN`` stay verbatim. A key already 12 digits long is left as is (idempotent).
    """
    local = out["ID_VIV"].str.len() < 12
    if not local.any():
        return out
    out["ID_VIV"] = out["ID_VIV"].where(~local, out["CVE_ENT"] + out["ID_VIV"].str.zfill(10))
    if "ID_PER" in out.columns and "ID_PERSONA" not in out.columns:
        out.insert(out.columns.get_loc("ID_PER") + 1, "ID_PERSONA",
                   out["ID_VIV"] + out["NUMPER"].str.zfill(5))
    if "ID_MIN" in out.columns and "ID_MII" not in out.columns:
        rank = (pd.to_numeric(out["ID_MIN"]).groupby(out["ID_VIV"]).rank(method="first")
                .astype(int).astype(str).str.zfill(2))
        out.insert(out.columns.get_loc("ID_MIN") + 1, "ID_MII", out["ID_VIV"] + rank)
    return out


def _harmonize(df: pd.DataFrame, table: str, label: str = "",
               periods: Iterable | None = None) -> pd.DataFrame:
    """Canonicalize one raw CPV frame's core across editions.

    Steps: upper-case names → the core renames of ``table`` (:func:`_renames`; refusing a
    frame that already carries both a source and its target) → national keys for an
    edition whose keys are state-scoped (CPV 2010, :func:`_national_keys`) → zero-pad the
    geographic codes, the keys and ``CLAVIVP`` (:data:`_GEO_PAD`, :data:`_CODE_PAD`; a code
    only in the editions its core entry covers) → the core recodes (an in-scope core
    entry's ``Alias`` for the frame's editions, :func:`_scoped_entry`: 2015's ``CLAVIVP``
    ``1``…``9``, 2000/2005's ``SEXO`` ``2`` = mujer → ``3``) → the keys of an edition without key columns (CGPV 2000, Conteo 2005,
    :func:`_composite_keys`) → derive ``CVEGEO`` from the leading
    :data:`_GEO_PARTS` the frame carries (inserted first) or, when present, **check** it
    against them (a mismatch warns) → numeric ``FACTOR`` (the Conteo 1995's has none: a
    copy of the table's estimator, ``FAC_POB`` for persons and ``FAC_VIV`` for emigrants,
    :data:`_FACTOR_FROM`, inserted before it). A missing required core column
    warns (the rename map may be stale). ``periods`` are the frame's editions (its schema
    group's; ``None`` = unknown: no edition-specific step). Column order and every other
    value are kept, so it is idempotent and, for 2025, the identity up to the ``FACTOR``
    dtype; a renamed column keeps its position.
    """
    out = df.copy()
    out.columns = [c.upper() for c in out.columns]
    rename = {s: t for s, t in _renames(table, periods).items() if s in out.columns}
    targets = list(rename.values())
    clash = sorted({t for t in targets if t in out.columns or targets.count(t) > 1})
    if clash:
        raise ValueError(
            f"CPV {table} {label}: cannot harmonize — both a legacy column and its target "
            f"exist for {clash}; the frame mixes editions or was already harmonized differently."
        )
    out = out.rename(columns=rename)
    if periods is not None and {str(p) for p in periods} & _STATE_SCOPED_KEYS \
            and {"ID_VIV", "CVE_ENT"} <= set(out.columns):
        out = _national_keys(out, table)
    core = _core_for(table, periods)
    for col, width in (_GEO_PAD | _CODE_PAD).items():
        if col in out.columns and (col in _GEO_PAD or col in core):
            out[col] = _zfill_codes(out[col], width)
    for col, meta in core.items():           # core recodes (Alias, Recodificar): SEXO 2 → 3
        if meta.get("Alias") and col in out.columns:
            out[col] = out[col].replace({str(k): str(v) for k, v in meta["Alias"].items()})
    out = _composite_keys(out, table)        # 2000/2005, from the padded geography
    parts = list(itertools.takewhile(out.columns.__contains__, _GEO_PARTS))
    if len(parts) >= 2:
        geo = functools.reduce(lambda a, b: a + b, (out[c] for c in parts))
        if "CVEGEO" in out.columns:
            bad = int((geo.notna() & out["CVEGEO"].notna() & (geo != out["CVEGEO"])).sum())
            if bad:
                warnings.warn(f"CPV {table} {label}: CVEGEO differs from {'+'.join(parts)} "
                              f"in {bad} row(s).", stacklevel=3)
        else:
            out.insert(0, "CVEGEO", geo)
    source = _FACTOR_FROM.get(table)
    if "FACTOR" not in out.columns and source in out.columns:     # Conteo 1995
        out.insert(out.columns.get_loc(source), "FACTOR", out[source])
    if "FACTOR" in out.columns:
        out["FACTOR"] = pd.to_numeric(out["FACTOR"], errors="coerce")
    missing = sorted(_required(table) - set(out.columns))
    if missing:
        warnings.warn(f"CPV {table} {label}: harmonized frame lacks core column(s) {missing}; "
                      f"_RENAME_CORE may be stale.", stacklevel=3)
    return out


@functools.cache
def _latest_schema(table: str, periods: tuple[str, ...] | None = None) -> pa.DataFrameSchema:
    """Tight-where-safe Pandera schema for a **harmonized** CPV frame of ``table``.

    Built from the hand-curated core: categoricals get ``isin`` on their codes, numerics and
    the weight are numeric, the geographic codes get width regexes; only the entity and the
    table's record key are required (:func:`_required`). ``strict=False``: every non-core
    column passes through. ``periods`` (the frame's editions) leaves out the core entries
    not verified for them (``Periodos``: CPV 2010's ``CLAVIVP`` stays its own column).
    """
    required = _required(table)
    schema = {}
    for col, meta in _core_for(table, periods).items():
        req = col in required
        tipo = _sg.norm_tipo(meta)
        if col in _WEIGHTS or tipo == "numeric":
            schema[col] = pa.Column(float, nullable=True, coerce=True, required=req)
        elif tipo == "categorical":
            schema[col] = _sg.raw_column(pa.Check.isin(_sg.raw_codes(meta)), required=req)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True, required=req)
    for col, rx in _GEO_REGEX.items():
        schema[col] = _sg.raw_column(pa.Check.str_matches(rx), required=col in required)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


# ---------------------------------------------------------------------------------------
# Labelled (human-readable) frames — ``labels=True`` (same design as ``enoe.py``/``enigh.py``)
# ---------------------------------------------------------------------------------------

@functools.cache
def variables_cpv_labels(table: str, gid: str) -> dict:
    """The labelling dictionary of one CPV ``(table, schema group)``: the per-group
    variables overlaid by :func:`~mxcensus.variables_cpv_core` (the entries in scope for
    ``table`` and the group's editions, see :func:`_in_scope`), keyed by both the raw and
    the harmonized column names (upper case, :func:`_renames`)."""
    periods = _group_periods(table, gid)
    rename = _renames(table, periods)
    merged: dict = {}
    for src in (variables_cpv(table, gid), _core_for(table, periods)):
        for col, meta in src.items():
            merged[col] = meta
            merged[rename.get(col.upper(), col.upper())] = meta
    return merged


# The entry keys that decide how a column is labelled and validated (``Descripción``,
# ``Pregunta``, ``Nota``… are wording only).
_LABEL_KEYS = ("Tipo", "Categorías", "Especiales", "Rango", "Ordenada", "Alias", "Decimales")


def _label_spec(meta: dict) -> tuple:
    return (_sg.norm_tipo(meta), *(meta.get(k) or None for k in _LABEL_KEYS[1:]))


def _labels_for(table: str, gids: list[str]) -> dict:
    """The labelling dictionary for a frame stacked from one or more schema groups (several
    only under ``harmonize=True``). A column labelled differently across the groups (its
    :data:`_LABEL_KEYS` differ; wording does not count) is left out — it stays raw — with a
    warning, rather than labelled with one group's codes. Otherwise the newest group's entry
    is kept."""
    if len(gids) == 1:
        return variables_cpv_labels(table, gids[0])
    merged: dict = {}
    conflicts: set[str] = set()
    for gid in sorted(gids, reverse=True):              # gids are chronological
        for col, meta in variables_cpv_labels(table, gid).items():
            if col in merged and _label_spec(merged[col]) != _label_spec(meta):
                conflicts.add(col)
            merged.setdefault(col, meta)
    if conflicts:
        warnings.warn(f"CPV {table}: {sorted(conflicts)} are labelled differently in schema "
                      f"groups {gids}; left unlabelled.", stacklevel=4)
    return {c: m for c, m in merged.items() if c not in conflicts}


def _finish_labelled(df: pd.DataFrame, variables: dict, label: str,
                     spec: list[tuple[str, ...]] | None = None) -> pd.DataFrame:
    """Label ``df``, set the level index when ``spec`` is given, validate strictly."""
    out = _sg.label_frame(df, variables, weights=_WEIGHTS, family="CPV", skip=_SKIP)
    key = _sg.level_key(spec, out) if spec else None
    if key:
        out = _index_level(out, spec)
    schema = _sg.build_labelled_schema(out.columns, variables, weights=_WEIGHTS,
                                       skip=_SKIP, index_names=key)
    return _sg.validate_raise("CPV", schema, out, f"{label} labelled")


# ---------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------

def _edition(table: str, period: str | int | None) -> CpvEdition:
    """The edition to load ``table`` from (``None`` → the latest that publishes it)."""
    if table not in TABLES:
        raise ValueError(f"unknown CPV table {table!r}; known: {list(TABLES)}")
    edition = latest_edition(table) if period is None else get_edition(period)
    if not edition.has(table):
        raise ValueError(f"{table!r} is not published for {edition.label}; "
                         f"available: {list(edition.tables)}")
    return edition


def _states(state: int | Sequence[int] | None) -> list[int] | None:
    """Normalize ``state`` to a list of INEGI codes (1–32), or ``None``."""
    if state is None:
        return None
    if isinstance(state, (numbers.Integral, str, bytes)) or not isinstance(state, Iterable):
        seq = [state]
    else:
        seq = list(state)              # a list/tuple/range/array/Series of codes
    if not seq:
        raise ValueError("state= is an empty sequence")
    for s in seq:
        if isinstance(s, bool) or not isinstance(s, numbers.Integral) or not 1 <= s <= 32:
            raise ValueError(f"state must be an INEGI state code 1-32 (or a sequence of them), "
                             f"got {s!r}")
    return list(dict.fromkeys(int(s) for s in seq))


def _filter_states(df: pd.DataFrame, states: list[int]) -> pd.DataFrame:
    """Keep the rows whose entity code (``CVE_ENT``, or a legacy ``ENT``/``ENTIDAD``) is in
    ``states``."""
    col = next((c for c in ("CVE_ENT", "ENT", "ENTIDAD", "cve_ent", "ent") if c in df.columns),
               None)
    if col is None:
        raise ValueError(f"cannot filter by state: no entity column in {list(df.columns)[:8]}…")
    keep = pd.to_numeric(df[col], errors="coerce").isin(states)
    return df[keep].reset_index(drop=True)


def _load_cpv_raw(
    survey_path: Path | None = None,
    *,
    table: str,
    period: str | int | None = None,
    state: int | Sequence[int] | None = None,
    harmonize: bool = False,
) -> tuple[pd.DataFrame, list[str], str]:
    """:func:`load_cpv` without labelling, returning ``(frame, gids, label)``."""
    states = _states(state)
    if survey_path is not None:
        sources = [(Path(survey_path), Path(survey_path).stem)]
        row_filter = states
    else:
        from mxcensus.data._registry import POOCH
        edition = _edition(table, period)
        period = edition.period
        if table in NATIONAL_TABLES:
            sources = [(Path(POOCH.fetch(cpv_filename(table, period))), period)]
            row_filter = states
        else:
            if states is None:
                raise ValueError(f"CPV {table!r} is mirrored per state; pass state= (an INEGI "
                                 f"code 1-32 or a sequence of them)")
            sources = [(Path(POOCH.fetch(cpv_filename(table, period, s))), f"{period} {s:02d}")
                       for s in states]
            row_filter = None

    frames, gids = [], []
    for path, where in sources:
        df = pd.read_parquet(path)
        if row_filter is not None:
            df = _filter_states(df, row_filter)
        gid = _group_of(table, df)
        label = f"{table} {where} ({gid})"
        _validate(_group_schema(table, gid), df, f"{label} raw")
        if harmonize:
            periods = _group_periods(table, gid)
            df = _harmonize(df, table, label, periods)
            _validate(_latest_schema(table, periods), df, f"{label} harmonized")
        frames.append(df)
        gids.append(gid)

    groups = list(dict.fromkeys(gids))
    if len(groups) > 1 and not harmonize:
        raise ValueError(f"CPV {table}: the requested states fall in different schema groups "
                         f"{groups}; load them separately or pass harmonize=True.")
    df = frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
    where = sources[0][1] if len(sources) == 1 else f"{period} states {states}"
    return df, groups, f"{table} {where} ({'/'.join(groups)})"


def load_cpv(
    survey_path: Path | None = None,
    *,
    table: str,
    period: str | int | None = None,
    state: int | Sequence[int] | None = None,
    harmonize: bool = False,
    labels: bool = False,
) -> pd.DataFrame:
    """Load one raw CPV-family table as a faithful ``dtype=str`` DataFrame.

    - ``load_cpv(table="personas", period="2025", state=9)`` — fetch from the mirror via
      Pooch (``period`` defaults to the latest edition publishing ``table``).
    - ``load_cpv(table="personas", state=[1, 9])`` — several states, concatenated.
    - ``load_cpv(table="estimaciones")`` — a national table (``state`` filters its rows).
    - ``load_cpv(survey_path=Path("cpv_personas_2025_01.parquet"), table="personas")``.

    Parameters
    ----------
    table : str
        One of :data:`mxcensus.data._cpv_catalog.TABLES` that the edition publishes.
    period : str or int, optional
        Edition year (``"2025"``, …); defaults to the latest edition with ``table``.
    state : int or sequence of int, optional
        INEGI state code(s), 1–32. Required for the per-state microdata tables (unless
        ``survey_path`` is given); on a national table, or with ``survey_path``, a row
        filter on ``CVE_ENT``. Several states must share one schema group unless
        ``harmonize=True``.
    harmonize : bool, default False
        Canonicalize the core across editions (:func:`_harmonize`) and validate against
        :func:`_latest_schema`.
    labels : bool, default False
        Return a **labelled** frame: coded fields become labelled ``Categorical`` columns,
        numeric fields numbers (sentinel codes → NA), validated strictly (raises on an
        out-of-dictionary value) — see :func:`variables_cpv_labels`. Keys, geographic codes
        and person-number pointers stay raw strings.

    Validation of the raw frame warns on value-level violations; an unknown schema raises
    ``ValueError``.
    """
    df, gids, label = _load_cpv_raw(survey_path, table=table, period=period, state=state,
                                    harmonize=harmonize)
    if labels:
        df = _finish_labelled(df, _labels_for(table, gids), label)
    return df


# --- analysis-ready loaders -------------------------------------------------------------

def _level_key(spec: list[tuple[str, ...]], *frames: pd.DataFrame) -> list[str]:
    return _sg.level_key(spec, *frames)


def _index_level(df: pd.DataFrame, spec: list[tuple[str, ...]]) -> pd.DataFrame:
    return _sg.index_level("CPV", df, spec)


def _level_edition(table: str, period: str | int | None) -> CpvEdition:
    """:func:`_edition`, also for the dwelling frames built from a person file (CGPV 1990,
    Conteo 1995: :data:`_DWELLINGS_FROM_PERSONS`)."""
    if table == "viviendas" and period is not None and str(period) in _DWELLINGS_FROM_PERSONS:
        return get_edition(period)
    return _edition(table, period)


def _dwellings_from_persons(period: str, state, harmonize: bool
                            ) -> tuple[pd.DataFrame, list[str], str]:
    """CGPV 1990's or the Conteo 1995's dwelling frame: the raw person file(s) with their
    composite keys, one row per ``ID_VIV`` (its first person's
    :data:`_DWELLINGS_FROM_PERSONS` columns); ``harmonize=True`` then harmonizes it as a
    ``viviendas`` frame (``FACTOR`` = ``FAC_VIV``). Returns ``(frame, the person file's
    gids, label)``."""
    persons, gids, label = _load_cpv_raw(table="personas", period=period, state=state)
    persons = _composite_keys(persons, "personas")
    first = ~persons["ID_VIV"].duplicated()
    df = persons.loc[first, ["ID_VIV", *_DWELLINGS_FROM_PERSONS[period]]].reset_index(drop=True)
    label = f"viviendas from {label}"
    if harmonize:
        periods = tuple(dict.fromkeys(p for g in gids for p in _group_periods("personas", g)))
        df = _harmonize(df, "viviendas", label, periods)
        _validate(_latest_schema("viviendas", periods), df, f"{label} harmonized")
    return df, gids, label


def _load_level(table: str, period, state, harmonize: bool, labels: bool,
                derived: bool = False) -> pd.DataFrame:
    """Raw ``table`` → derived columns (``derived``, from the raw codes), numeric
    ``FACTOR``, labelled (``labels``), indexed by its level key. CGPV 1990's and the
    Conteo 1995's dwellings come from their person files (:func:`_dwellings_from_persons`)."""
    states = _states(state)
    edition = _level_edition(table, period)
    if not harmonize and states and len(states) > 1 and table not in NATIONAL_TABLES \
            and edition.period in _STATE_SCOPED_KEYS:
        raise ValueError(f"CPV {table} {edition.label}: the record keys are "
                         f"unique within a state only, so states {states} cannot share one "
                         f"index; load them one at a time or pass harmonize=True (national "
                         f"keys).")
    source = table
    if table == "viviendas" and not edition.has(table):
        df, gids, label = _dwellings_from_persons(edition.period, state, harmonize)
        source = "personas"                 # labelled by the person file's dictionary
    else:
        df, gids, label = _load_cpv_raw(table=table, period=period, state=state,
                                        harmonize=harmonize)
        if not harmonize:                   # harmonize=True derived them already
            df = _composite_keys(df, table)
    if derived:
        df = _derived.derive(df, table, edition.period)
    spec = _KEY_SPEC[table]
    if labels:
        out = _finish_labelled(df, _labels_for(source, gids), label, spec)
    else:
        for col in _WEIGHTS & set(df.columns):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        out = _index_level(df, spec)
    if derived:
        schema = _derived.derived_schema(table, edition.period)
        out = _sg.validate_raise("CPV", schema, out, f"{label} derived")
    return out


def load_cpv_viviendas(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True, derived: bool = False,
) -> pd.DataFrame:
    """The analysis-ready **dwelling** frame (inhabited private dwellings: housing
    characteristics, goods, tenure, household-level income and food-security items), with
    a numeric ``FACTOR`` and indexed by ``ID_VIV``.

    Σ ``FACTOR`` = the expanded number of inhabited private dwellings. ``state`` is
    required (one code or a sequence, see :func:`load_cpv`). ``labels=True`` (default)
    returns labelled ``Categorical``/numeric columns validated strictly (see
    :func:`load_cpv`); keys and geographic codes stay raw strings.

    Older editions differ. CGPV 2000's dwelling file has **one row per household**
    (the dwelling's items repeat in each), indexed ``(ID_VIV, ID_HOG)``: count dwellings
    on ``ID_HOG``'s first household (``NUMHOG == "1"``). The Conteo 2005 sample has no
    ``FACTOR``. Both have no key column; the keys are derived from the composite parts
    (:func:`_composite_keys`). CGPV 1990 and the Conteo 1995 publish no dwelling file: their
    frame is built from the person file, one row per dwelling with its first person's
    dwelling items (:data:`_DWELLINGS_FROM_PERSONS`); 1990's is unweighted (a 10% extract),
    1995's carries ``FAC_VIV`` (``harmonize=True``: ``FACTOR`` = ``FAC_VIV``).

    ``derived=True`` adds the legacy ``load_extended_viviendas`` columns the edition
    supports (``CLAVIVP_CAT``, ``CUADORM_CAT``, ``INGTRHOG_CAT``, the ``FINANCIAMIENTO_*``
    dummies…; :func:`mxcensus.cpv_derivations` lists them per edition), computed from the
    raw codes and validated (:mod:`mxcensus.cpv_derived`).
    """
    return _load_level("viviendas", period, state, harmonize, labels, derived)


def load_cpv_hogares(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> pd.DataFrame:
    """The analysis-ready **household** frame of the Conteo 2005 sample (the only edition
    with a household table: number of members and household class), indexed by
    ``(ID_VIV, ID_HOG)``. The 2005 sample has **no expansion factor** (``FACTOR``): counts
    are sample counts. CGPV 2000 has no separate household table — its dwelling file
    (:func:`load_cpv_viviendas`) has one row per household. Labelled by default
    (``labels``, see :func:`load_cpv_viviendas`).
    """
    return _load_level("hogares", period, state, harmonize, labels)


def load_cpv_personas(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True, derived: bool = False,
) -> pd.DataFrame:
    """The analysis-ready **person** frame (residents of inhabited private dwellings), with
    a numeric ``FACTOR``, indexed by the person key ``(ID_VIV, ID_PERSONA)`` — in 1995,
    2000 and 2005 ``(ID_VIV, ID_HOG, ID_PERSONA)``, persons nested in households (2005 and
    1990 have no weight; 1995 has three, ``FAC_POB`` for persons, ``FAC_VIV`` for dwellings
    and households, ``FAC_PROM`` for health coverage and disability — ``harmonize=True``
    adds ``FACTOR`` = ``FAC_POB``, so weight 1995's health and disability items with
    ``FAC_PROM``; 2000's persons are
    unnumbered, so ``ID_PERSONA`` counts them in file order, :func:`_composite_keys`). In
    1990 and 1995 this is the only microdata file: each person carries the dwelling's
    (and household's) items (:func:`load_cpv_viviendas` builds the dwellings from it).

    Σ ``FACTOR`` = the expanded population. Person-number pointers (``NUMPER``,
    ``IDENT_MADRE``/``IDENT_PADRE``/``IDENT_PAREJA``) stay raw strings, so a person's mother
    is the row with the same ``ID_VIV`` and ``NUMPER == IDENT_MADRE``. Labelled by default
    (``labels``, see :func:`load_cpv_viviendas`).

    ``derived=True`` adds the legacy ``load_extended_personas`` columns the edition
    supports (``EDAD_CAT``, ``EDUC``, ``CONACT_CAT``, the ``DHSERSAL_*`` and
    ``MED_TRASLADO_*`` dummies, ``DIS_CON``/``DIS_LIMI``…; :func:`mxcensus.cpv_derivations`
    lists them per edition), computed from the raw codes and validated
    (:mod:`mxcensus.cpv_derived`).
    """
    return _load_level("personas", period, state, harmonize, labels, derived)


def load_cpv_migrantes(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> pd.DataFrame:
    """The analysis-ready **international emigrant** frame (people of the dwelling who left
    to live in another country in the reference period), with a numeric ``FACTOR``,
    indexed by ``(ID_VIV, ID_MII)`` — CGPV 2000: ``(ID_VIV, ID_HOG, ID_MII)``, its
    emigrants hang from the household.

    Emigrants hang from the dwelling, not from a person. A returned emigrant who lives in
    the dwelling again (``MCONRESACT`` = Sí) carries their number in the person list in
    ``MPERLS``, which joins ``(ID_VIV, NUMPER)`` of :func:`load_cpv_personas`. The Conteo
    1995's emigrants carry the dwelling weight ``FAC_VIV`` (``harmonize=True`` copies it to
    ``FACTOR``). Labelled by default (``labels``, see :func:`load_cpv_viviendas`).
    """
    return _load_level("migrantes", period, state, harmonize, labels)


def load_cpv_survey(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True, derived: bool = False,
) -> tuple[pd.DataFrame | None, pd.DataFrame, pd.DataFrame | None]:
    """Load the microdata levels with a **shared nested** index.

    Returns ``(viviendas, personas, migrantes)`` = :func:`load_cpv_viviendas`,
    :func:`load_cpv_personas`, :func:`load_cpv_migrantes` (``None`` for an edition without
    that table: 1990, 2005 and 2015 have no emigrants; the 1990 and 1995 samples are person
    files with the dwelling items on each person, from which their ``viviendas`` is built). The person and emigrant indices both extend the dwelling index
    (``ID_VIV`` ⊂ ``(ID_VIV, ID_PERSONA)``; ``ID_VIV`` ⊂ ``(ID_VIV, ID_MII)``), as the
    extended-census microdata share ``ID_VIV``. The optional emigrant → person link is the
    join ``(ID_VIV, MPERLS) = (ID_VIV, NUMPER)`` (see :func:`load_cpv_migrantes`).

    In CGPV 2000 every index carries the household: ``(ID_VIV, ID_HOG)`` ⊂
    ``(ID_VIV, ID_HOG, ID_PERSONA)``, ``(ID_VIV, ID_HOG, ID_MII)``. Conteo 2005's
    household table is :func:`load_cpv_hogares` (not part of the tuple); its persons are
    indexed ``(ID_VIV, ID_HOG, ID_PERSONA)`` under the dwellings' ``ID_VIV``.

    ``derived=True`` adds the derived columns to ``viviendas`` and ``personas`` (see
    :func:`load_cpv_personas`).
    """
    edition = _edition("personas", period)
    kw = dict(state=state, harmonize=harmonize, labels=labels)
    viviendas = load_cpv_viviendas(edition.period, derived=derived, **kw) \
        if edition.has("viviendas") or edition.period in _DWELLINGS_FROM_PERSONS else None
    personas = load_cpv_personas(edition.period, derived=derived, **kw)
    migrantes = load_cpv_migrantes(edition.period, **kw) if edition.has("migrantes") else None
    return viviendas, personas, migrantes
