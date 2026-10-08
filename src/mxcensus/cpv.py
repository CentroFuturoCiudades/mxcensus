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
aggregates) and the **Encuesta Intercensal 2015** (``viviendas`` and ``personas`` per state,
no migrant table; ``ENT``/``MUN`` as in 2020, keys and most codes written without their
zero-padding).

Public API:

- :func:`load_cpv` — one raw table (faithful ``dtype=str`` frame) for one edition and one
  or more states.
- :func:`load_cpv_viviendas` / :func:`load_cpv_personas` / :func:`load_cpv_migrantes` —
  analysis-ready frames: numeric ``FACTOR``, labelled columns, indexed by the level key.
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
from mxcensus._resources import cpv_schema_map, variables_cpv, variables_cpv_core
from mxcensus.data._cpv_catalog import (
    NATIONAL_TABLES,
    TABLES,
    CpvEdition,
    cpv_filename,
    get_edition,
    latest_edition,
)

# Expansion weight — validated as numeric.
_WEIGHTS = {"FACTOR"}

# Keys and geographic codes: digit strings (their width is edition-specific, so only the
# all-digits shape is checked here; key widths are checked by the data tests). CPV 2020
# spells the microdata geography ENT/MUN and the aggregates' ENTIDAD/MUN/LOC/MZA.
_DIGIT_CODES = frozenset({"ID_VIV", "ID_PERSONA", "ID_MII", "CVEGEO", "CVE_ENT", "CVE_MUN",
                          "LOC50K", "CVE_LOC", "CVE_MZA", "ENT", "MUN", "ENTIDAD", "LOC",
                          "MZA"})
# Coded strings with their own shape: the urban AGEB key is three digits and a check
# character (0-9 or A-P); 0000 marks the ITER/AGEB total rows.
_AGEB_RE = r"\d{3}[0-9A-P]"
_CODE_REGEX = {"AGEB": rf"^{_AGEB_RE}$", "CVE_AGEB": rf"^{_AGEB_RE}$"}

# Record keys (alias tuples: canonical name first, then the CPV 2010 spellings). Persons
# and international emigrants are siblings under the dwelling, so both keys extend the
# dwelling key and the three frames of :func:`load_cpv_survey` align on ``ID_VIV``.
_DWELLING_KEY_SPEC: list[tuple[str, ...]] = [("ID_VIV",)]
_PERSON_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("ID_PERSONA", "ID_PER")]
_MIGRANT_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("ID_MII", "ID_MIN")]
_KEY_SPEC: dict[str, list[tuple[str, ...]]] = {
    "viviendas": _DWELLING_KEY_SPEC,
    "personas": _PERSON_KEY_SPEC,
    "migrantes": _MIGRANT_KEY_SPEC,
}

# Columns ``labels=True`` leaves as raw strings: the keys and geographic codes (joinable
# across tables and with the Marco Geoestadístico), and the person-number pointers — a
# person's number in the dwelling's list (``NUMPER``) and the fields that point at one
# (mother, father, partner, the dwelling's or — 2015 — the farmland's owners, a returned
# emigrant's own record), so ``(ID_VIV, IDENT_MADRE)`` joins ``(ID_VIV, NUMPER)`` directly.
# Person numbers 01-54 are their own labels (2015: the numbers 1-54); the codes from 96 up
# (lives elsewhere, deceased, no partner, not a resident, don't know, not specified) are
# documented in the dictionary.
_GEO_CODES = ("CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "CVE_LOC", "CVE_AGEB", "CVE_MZA",
              "ENT", "MUN", "ENTIDAD", "LOC", "AGEB", "MZA")
_POINTERS = ("NUMPER", "IDENT_MADRE", "IDENT_PADRE", "IDENT_PAREJA", "DUE1_NUM", "DUE2_NUM",
             "MPER", "MPERLS", "NUM_DUE_VIV1", "NUM_DUE_VIV2", "NUM_DUE_TERR")
_KEY_COLUMNS = frozenset(c for spec in _KEY_SPEC.values() for aliases in spec for c in aliases)
_SKIP = _KEY_COLUMNS | frozenset(_GEO_CODES) | frozenset(_POINTERS)


def _fingerprint(columns) -> str:
    """Schema-group fingerprint (shared recipe, see :mod:`mxcensus._schema_groups`)."""
    return _sg.fingerprint(columns)


def _code_rule(col: str, meta: dict) -> pa.Column | None:
    """Raw-string rule for a coded string column: a key/geographic code → digits; a code
    from a classification catalog too large to enumerate (``Catálogo`` + string ``Tipo``:
    occupation, activity, country, municipality, language) → exactly ``Longitud`` digits.
    ``None`` for any other column."""
    if col in _CODE_REGEX:
        return _sg.raw_column(pa.Check.str_matches(_CODE_REGEX[col]))
    if col in _DIGIT_CODES:
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


def _in_scope(meta: dict, table: str) -> bool:
    """Whether a core entry applies to ``table``: its ``Tablas`` list, else every table
    that has the column (the ITER's ``TAMLOC`` is a 14-class size scale, not the microdata's
    five classes)."""
    return table in (meta.get("Tablas") or (table,))


def _core_for(table: str) -> dict:
    """The core entries that apply to ``table`` (:func:`_in_scope`)."""
    return {c: m for c, m in variables_cpv_core().items() if _in_scope(m, table)}


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
# renames are scoped to the ITER/AGEB (as ENIGH's per-table map). EIC 2015 spells the
# microdata geography as 2020 does (ENT/MUN, zero-padded). CPV 2010 will add
# ID_PER→ID_PERSONA, ID_MIN→ID_MII and TAM_LOC→TAMLOC (unit 3b).
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
_CODE_PAD: dict[str, int] = {"ID_VIV": 12, "ID_PERSONA": 14, "CLAVIVP": 2}
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


def _renames(table: str) -> dict[str, str]:
    """The core renames that apply to ``table``: :data:`_RENAME_CORE` plus the table's own
    (:data:`_RENAME_TABLE`)."""
    return {**_RENAME_CORE, **_RENAME_TABLE.get(table, {})}


def _zfill_codes(s: pd.Series, width: int) -> pd.Series:
    digits = s.str.fullmatch(r"\d+").fillna(False).astype(bool)
    return s.where(~digits, s.str.zfill(width))


def _required(table: str) -> set[str]:
    """Canonical columns a harmonized ``table`` frame must carry: the entity and the
    table's record key."""
    return {"CVE_ENT", *(aliases[0] for aliases in _KEY_SPEC.get(table, []))}


def _harmonize(df: pd.DataFrame, table: str, label: str = "") -> pd.DataFrame:
    """Canonicalize one raw CPV frame's core across editions.

    Steps: upper-case names → the core renames of ``table`` (:func:`_renames`; refusing a
    frame that already carries both a source and its target) → zero-pad the geographic
    codes, the keys and ``CLAVIVP`` (:data:`_GEO_PAD`, :data:`_CODE_PAD`) → derive ``CVEGEO`` from the leading :data:`_GEO_PARTS` the
    frame carries (inserted first) or, when present, **check** it against them (a mismatch
    warns) → numeric ``FACTOR``. A missing required core column warns (the rename map may be
    stale). Column order and every other value are kept, so it is idempotent and, for 2025,
    the identity up to the ``FACTOR`` dtype; a renamed column keeps its position.
    """
    out = df.copy()
    out.columns = [c.upper() for c in out.columns]
    rename = {s: t for s, t in _renames(table).items() if s in out.columns}
    targets = list(rename.values())
    clash = sorted({t for t in targets if t in out.columns or targets.count(t) > 1})
    if clash:
        raise ValueError(
            f"CPV {table} {label}: cannot harmonize — both a legacy column and its target "
            f"exist for {clash}; the frame mixes editions or was already harmonized differently."
        )
    out = out.rename(columns=rename)
    for col, width in (_GEO_PAD | _CODE_PAD).items():
        if col in out.columns:
            out[col] = _zfill_codes(out[col], width)
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
    if "FACTOR" in out.columns:
        out["FACTOR"] = pd.to_numeric(out["FACTOR"], errors="coerce")
    missing = sorted(_required(table) - set(out.columns))
    if missing:
        warnings.warn(f"CPV {table} {label}: harmonized frame lacks core column(s) {missing}; "
                      f"_RENAME_CORE may be stale.", stacklevel=3)
    return out


@functools.cache
def _latest_schema(table: str) -> pa.DataFrameSchema:
    """Tight-where-safe Pandera schema for a **harmonized** CPV frame of ``table``.

    Built from the hand-curated core: categoricals get ``isin`` on their codes, numerics and
    the weight are numeric, the geographic codes get width regexes; only the entity and the
    table's record key are required (:func:`_required`). ``strict=False``: every non-core
    column passes through.
    """
    required = _required(table)
    schema = {}
    for col, meta in _core_for(table).items():
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
    ``table``, see :func:`_in_scope`), keyed by both the raw and
    the harmonized column names (upper case, :func:`_renames`)."""
    rename = _renames(table)
    merged: dict = {}
    for src in (variables_cpv(table, gid), _core_for(table)):
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
            df = _harmonize(df, table, label)
            _validate(_latest_schema(table), df, f"{label} harmonized")
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


def _load_level(table: str, period, state, harmonize: bool, labels: bool) -> pd.DataFrame:
    """Raw ``table`` → numeric ``FACTOR``, labelled (``labels``), indexed by its level key."""
    df, gids, label = _load_cpv_raw(table=table, period=period, state=state,
                                    harmonize=harmonize)
    spec = _KEY_SPEC[table]
    if labels:
        return _finish_labelled(df, _labels_for(table, gids), label, spec)
    for col in _WEIGHTS & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return _index_level(df, spec)


def load_cpv_viviendas(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> pd.DataFrame:
    """The analysis-ready **dwelling** frame (inhabited private dwellings: housing
    characteristics, goods, tenure, household-level income and food-security items), with
    a numeric ``FACTOR`` and indexed by ``ID_VIV``.

    Σ ``FACTOR`` = the expanded number of inhabited private dwellings. ``state`` is
    required (one code or a sequence, see :func:`load_cpv`). ``labels=True`` (default)
    returns labelled ``Categorical``/numeric columns validated strictly (see
    :func:`load_cpv`); keys and geographic codes stay raw strings.
    """
    return _load_level("viviendas", period, state, harmonize, labels)


def load_cpv_personas(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> pd.DataFrame:
    """The analysis-ready **person** frame (residents of inhabited private dwellings), with
    a numeric ``FACTOR``, indexed by the person key ``(ID_VIV, ID_PERSONA)``.

    Σ ``FACTOR`` = the expanded population. Person-number pointers (``NUMPER``,
    ``IDENT_MADRE``/``IDENT_PADRE``/``IDENT_PAREJA``) stay raw strings, so a person's mother
    is the row with the same ``ID_VIV`` and ``NUMPER == IDENT_MADRE``. Labelled by default
    (``labels``, see :func:`load_cpv_viviendas`).
    """
    return _load_level("personas", period, state, harmonize, labels)


def load_cpv_migrantes(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> pd.DataFrame:
    """The analysis-ready **international emigrant** frame (people of the dwelling who left
    to live in another country in the reference period), with a numeric ``FACTOR``,
    indexed by ``(ID_VIV, ID_MII)``.

    Emigrants hang from the dwelling, not from a person. A returned emigrant who lives in
    the dwelling again (``MCONRESACT`` = Sí) carries their number in the person list in
    ``MPERLS``, which joins ``(ID_VIV, NUMPER)`` of :func:`load_cpv_personas`. Labelled by
    default (``labels``, see :func:`load_cpv_viviendas`).
    """
    return _load_level("migrantes", period, state, harmonize, labels)


def load_cpv_survey(
    period: str | int | None = None, *, state: int | Sequence[int] | None,
    harmonize: bool = False, labels: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    """Load the microdata levels with a **shared nested** index.

    Returns ``(viviendas, personas, migrantes)`` = :func:`load_cpv_viviendas`,
    :func:`load_cpv_personas`, :func:`load_cpv_migrantes` (``None`` for an edition without
    a migrant table). The person and emigrant indices both extend the dwelling index
    (``ID_VIV`` ⊂ ``(ID_VIV, ID_PERSONA)``; ``ID_VIV`` ⊂ ``(ID_VIV, ID_MII)``), as the
    extended-census microdata share ``ID_VIV``. The optional emigrant → person link is the
    join ``(ID_VIV, MPERLS) = (ID_VIV, NUMPER)`` (see :func:`load_cpv_migrantes`).
    """
    edition = _edition("personas", period)
    kw = dict(state=state, harmonize=harmonize, labels=labels)
    viviendas = load_cpv_viviendas(edition.period, **kw)
    personas = load_cpv_personas(edition.period, **kw)
    migrantes = load_cpv_migrantes(edition.period, **kw) if edition.has("migrantes") else None
    return viviendas, personas, migrantes
