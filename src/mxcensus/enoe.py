"""ENOE (Encuesta Nacional de Ocupación y Empleo) — loader + schema/validation layer.

ENOE is INEGI's quarterly labor-force survey, mirrored per (table, quarter) as
``enoe_{table}_{period}.parquet`` (five tables ``viv``/``hog``/``sdem``/``coe1``/``coe2``;
see ``mxcensus.data._enoe_catalog`` and ``scripts/build_enoe.py``). Like DENUE it drifts
across eras, so every mirrored file is fingerprinted into a **per-table** schema group
(``_yaml/enoe_schema_map.yaml``) and validated against a tight per-group Pandera schema
built from that group's ``variables_enoe_{table}_{gid}.yaml``.

Public API:

- :func:`load_enoe` — one raw table for one quarter (faithful ``dtype=str`` frame), fetched
  from the mirror via Pooch and validated against its group schema (value-level violations
  **warn**, they don't raise — see :func:`_validate`).
- :func:`load_enoe_persons` — the analytical person frame: SDEM left-joined with COE1/COE2 on
  the era-appropriate person key, filtered to the canonical universe, with a canonical
  ``fac_tri`` weight and derived labour-force flags (``is_pea``/``is_ocupado``/``is_informal``).

Analytical-core **harmonization** across eras (the ``FAC``→``FAC_TRI`` unification, key
alignment, precodificado renames) is deferred to a later work unit; ``load_enoe`` currently
supports only ``harmonize=False``. The maintainer ``build_enoe.py --validate`` sweep is the
authoritative per-file hard pass/fail report (``docs/enoe/VALIDATION_REPORT.md``).
"""
from __future__ import annotations

import functools
import json
import warnings
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from mxcensus._resources import enoe_schema_map, variables_enoe
from mxcensus.data._enoe_catalog import QUARTERS_BY_PERIOD, TABLES, latest_quarter

# Expansion weights — validated as numeric (coercible) rather than by category. ``fac`` is
# the pre-2020-T3 factor; ``fac_tri``/``fac_men`` the quarterly/monthly factors after.
_WEIGHTS = {"fac", "fac_tri", "fac_men"}

# Survey keys as ordered logical components, each resolved to the first *alias* present in
# every joined frame. ENOE's household survey nests **dwelling ⊂ household ⊂ person**, and the
# three natural keys are clean *prefixes* of one another — so they double as the hierarchical
# index levels for the ``load_enoe_{viviendas,hogares}`` / ``load_enoe_survey`` loaders.
#
# The panel identifiers ``tipo``/``mes_cal``/``ca`` sit in the **dwelling** portion: they
# distinguish the same physical dwelling across panel visits (in the panel/CATI era the base
# identifiers are NOT unique within a quarter file — a dwelling/person recurs across
# ``tipo``/``mes_cal``), so the household/person keys must extend them. They appear from
# 2020-T3 (``ca`` only for 2020-T3…2021-T2); pre-2020-T3 files simply lack them and the base
# key is used. The entity code was renamed ``ent`` → ``cve_ent`` in 2026-T1 (the ``cve_*``
# geographic-key rename), so it resolves across both names.
_ENT_ALIASES = ("ent", "cve_ent")
_DWELLING_KEY_SPEC: list[tuple[str, ...]] = [
    ("cd_a",), _ENT_ALIASES, ("con",), ("v_sel",), ("tipo",), ("mes_cal",), ("ca",),
]
_HOUSEHOLD_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("n_hog",), ("h_mud",)]
_PERSON_KEY_SPEC: list[tuple[str, ...]] = _HOUSEHOLD_KEY_SPEC + [("n_ren",)]


def _fingerprint(columns) -> str:
    """sha256 over the ordered column names — identifies a table's schema group.

    Same recipe as ``scripts/build_enoe.py`` uses when writing ``enoe_schema_map.yaml``, so a
    mirrored file's columns hash to the fingerprint recorded there.
    """
    return sha256(json.dumps(list(columns)).encode()).hexdigest()


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one ENOE ``(table, schema group)``'s raw frame.

    Built from the group's bundled ``variables_enoe_{table}_{gid}.yaml``:

    - expansion weights (``_WEIGHTS``) → numeric type check (coercible from the raw strings);
    - any column with a non-empty ``Categorías`` map → strict ``isin`` on its keys. For the
      analytical-core columns those keys are the complete, FD-sourced value-set (so a future
      file with an out-of-catalog value fails here); for other categoricals they are the
      data-enumerated values;
    - everything else → nullable string.

    ``strict=False`` so extra columns are ignored; ``coerce=True`` parses the ``dtype=str``
    frame to the declared types for the checks.
    """
    vars_ = variables_enoe(table, gid)
    cols = enoe_schema_map()[table]["groups"][gid]["columns"]
    schema = {}
    for col in cols:
        cats = (vars_.get(col) or {}).get("Categorías") or {}
        if col in _WEIGHTS:
            schema[col] = pa.Column(float, nullable=True, coerce=True)
        elif cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True, coerce=True)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


def _group_of(table: str, df: pd.DataFrame) -> str:
    """Resolve a loaded ENOE frame to its per-table schema group id (by column fingerprint).

    Raises ``ValueError`` if the column set isn't in ``enoe_schema_map.yaml`` — a structural
    problem (stale mirror or a quarter absent from the map) that should fail loudly, unlike
    the value-level violations :func:`_validate` merely warns about.
    """
    fp = _fingerprint(list(df.columns))
    gid = enoe_schema_map().get(table, {}).get("fingerprints", {}).get(fp)
    if gid is None:
        raise ValueError(
            f"ENOE {table} file schema not found in enoe_schema_map.yaml (stale mirror or "
            f"map, or a quarter not covered by the current — possibly partial — build?)."
        )
    return gid


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise.

    A stray malformed cell should surface a problem, not make a quarter unloadable —
    structural problems (unknown schema) already raise in :func:`_group_of`. The maintainer
    ``build_enoe.py --validate`` sweep is the authoritative hard pass/fail report.
    """
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        fc = exc.failure_cases
        top = fc.groupby(["column", "check"]).size().sort_values(ascending=False).head(6)
        detail = "; ".join(f"{col}/{chk}×{n}" for (col, chk), n in top.items())
        warnings.warn(
            f"ENOE {label}: {len(fc)} schema violation(s) [{detail}]", stacklevel=3
        )


def _filter_ent(df: pd.DataFrame, ent: int) -> pd.DataFrame:
    """Return only the rows for state ``ent`` (1–32).

    Resolves the entity column across the ``ent``→``cve_ent`` rename and coerces numerically,
    so it works whether the codes are un-padded (``'9'``) or zero-padded (``'09'``).
    """
    col = next((c for c in _ENT_ALIASES if c in df.columns), None)
    if col is None:
        raise KeyError(f"no entity column {_ENT_ALIASES} in frame")
    return df[pd.to_numeric(df[col], errors="coerce") == int(ent)].reset_index(drop=True)


def load_enoe(
    survey_path: Path | None = None,
    *,
    table: str,
    period: str | None = None,
    harmonize: bool = False,
    ent: int | None = None,
) -> pd.DataFrame:
    """Load one raw ENOE table for one quarter as a faithful ``dtype=str`` DataFrame.

    Two calling conventions:

    - ``load_enoe(table="sdem", period="2023t1")`` — fetch from the mxcensus mirror via Pooch
      (``period`` defaults to the latest quarter).
    - ``load_enoe(survey_path=Path("enoe_sdem_2023t1.parquet"), table="sdem")`` — explicit
      local file (still fingerprinted/validated).

    Parameters
    ----------
    table : {"viv", "hog", "sdem", "coe1", "coe2"}
        Which of the quarter's five tables to load.
    period : str, optional
        Quarter id ``"{year}t{quarter}"`` (e.g. ``"2023t1"``); defaults to the latest.
    harmonize : bool, default False
        Cross-era analytical-core harmonization is not implemented yet (planned); only
        ``False`` (the raw schema) is currently supported.
    ent : int, optional
        Keep only rows for INEGI state code ``ent`` (1–32). ENOE is national, so this is a
        post-load row filter, not a separate file.

    The frame is validated against its group's tight schema; value-level violations emit a
    ``warnings.warn`` summary (they do not raise). An unrecognized schema raises ``ValueError``.
    """
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}; known: {TABLES}")
    if harmonize:
        raise NotImplementedError(
            "ENOE cross-era harmonization is not implemented yet; use harmonize=False "
            "(the raw per-era schema)."
        )
    if survey_path is None:
        period = period or latest_quarter().period
        if period not in QUARTERS_BY_PERIOD:
            raise ValueError(
                f"unknown period {period!r}; known: {list(QUARTERS_BY_PERIOD)[:3]}…"
                f"{list(QUARTERS_BY_PERIOD)[-1]}"
            )
        from mxcensus.data._registry import POOCH
        survey_path = Path(POOCH.fetch(f"enoe_{table}_{period}.parquet"))

    df = pd.read_parquet(survey_path)
    if ent is not None:
        df = _filter_ent(df, ent)
    gid = _group_of(table, df)
    _validate(_group_schema(table, gid), df, f"{table} {period or survey_path.stem} ({gid}) raw")
    return df


def _level_key(spec: list[tuple[str, ...]], *frames: pd.DataFrame) -> list[str]:
    """Resolve a key ``spec`` to the columns present in **every** given frame.

    Each logical component (a tuple of aliases) resolves to the first alias present in all
    frames, so the ``ent``/``cve_ent`` rename and the era-specific ``tipo``/``mes_cal``/``ca``
    additions are all handled. Because :data:`_DWELLING_KEY_SPEC` ⊂ :data:`_HOUSEHOLD_KEY_SPEC`
    ⊂ :data:`_PERSON_KEY_SPEC`, the resolved keys are clean prefixes of one another.
    """
    common = set.intersection(*(set(f.columns) for f in frames))
    key = []
    for aliases in spec:
        col = next((c for c in aliases if c in common), None)
        if col is not None:
            key.append(col)
    return key


def _person_key(*frames: pd.DataFrame) -> list[str]:
    """Person-key columns present in every given frame (see :func:`_level_key`)."""
    return _level_key(_PERSON_KEY_SPEC, *frames)


def load_enoe_persons(
    period: str | None = None,
    *,
    ent: int | None = None,
    canonical_filter: bool = True,
) -> pd.DataFrame:
    """Load the analytical person frame for one quarter: SDEM joined with COE1/COE2.

    SDEM (one row per household member) is **left-joined** with COE1 and COE2 (the employment
    questionnaire, present only for the working-age universe) on the era-appropriate person
    key (:func:`_person_key`); COE columns that duplicate an SDEM column are dropped so each
    column appears once (taken from SDEM). The join never fans out — the key is unique in
    every table.

    Parameters
    ----------
    period : str, optional
        Quarter id (e.g. ``"2023t1"``); defaults to the latest quarter.
    ent : int, optional
        Restrict to INEGI state code ``ent`` (1–32).
    canonical_filter : bool, default True
        Keep only the canonical analytical universe ``R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]``
        (padding-robust: the raw codes are un-padded, e.g. ``r_def='0'``). Set ``False`` to
        keep every SDEM row.

    Added columns
    -------------
    - ``fac_tri`` — canonical trimestral expansion weight, **numeric**, coalescing the raw
      ``fac_tri`` (2020-T3+) or ``fac`` (earlier) string column.
    - ``is_pea`` (``clase1==1``), ``is_ocupado`` (``clase2==1``), ``is_informal``
      (``emp_ppal==1``) — boolean labour-force flags.

    All other columns are the faithful raw ``dtype=str`` values.
    """
    period = period or latest_quarter().period
    sdem = load_enoe(table="sdem", period=period, ent=ent)
    coe1 = load_enoe(table="coe1", period=period, ent=ent)
    coe2 = load_enoe(table="coe2", period=period, ent=ent)

    key = _person_key(sdem, coe1, coe2)
    # Guard against a silent fan-out: if the key isn't unique in SDEM (e.g. a future era
    # renames a key column so it drops out of the join, as 2026-T1 did with ent→cve_ent),
    # the left-join inflates rows and weighted totals. Warn loudly rather than mislead.
    if sdem.duplicated(subset=key).any():
        warnings.warn(
            f"ENOE {period}: person key {key} is not unique in SDEM — a key column may be "
            f"renamed in this era; joins/weighted totals may be inflated.", stacklevel=2,
        )
    merged = sdem
    for coe in (coe1, coe2):
        add = [c for c in coe.columns if c not in merged.columns]  # non-key, non-duplicate
        merged = merged.merge(coe[key + add], on=key, how="left")

    if canonical_filter:
        rdef = pd.to_numeric(merged["r_def"], errors="coerce")
        eda = pd.to_numeric(merged["eda"], errors="coerce")
        mask = (rdef == 0) & merged["c_res"].isin(["1", "3"]) & eda.between(15, 98)
        merged = merged[mask].reset_index(drop=True)

    # Canonical trimestral weight (coalesce fac_tri / fac), as numeric for weighted sums.
    wcol = next((c for c in ("fac_tri", "fac") if c in merged.columns), None)
    if wcol is not None:
        merged["fac_tri"] = pd.to_numeric(merged[wcol], errors="coerce")

    # Derived labour-force flags (precodificado are in SDEM; absent → all-NA fallback).
    for name, col, val in (("is_pea", "clase1", "1"), ("is_ocupado", "clase2", "1"),
                           ("is_informal", "emp_ppal", "1")):
        merged[name] = merged[col].eq(val) if col in merged.columns else pd.NA
    return merged


def _coalesce_fac_tri(df: pd.DataFrame) -> pd.DataFrame:
    """Make the expansion weights numeric in place.

    Adds a canonical numeric ``fac_tri`` coalescing the raw ``fac_tri`` (2020-T3+) or ``fac``
    (earlier), and coerces ``fac_men`` when present — so the raw ``dtype=str`` weight columns
    become usable for weighted sums. Same recipe as :func:`load_enoe_persons`.
    """
    wcol = next((c for c in ("fac_tri", "fac") if c in df.columns), None)
    if wcol is not None:
        df["fac_tri"] = pd.to_numeric(df[wcol], errors="coerce")
    if "fac_men" in df.columns:
        df["fac_men"] = pd.to_numeric(df["fac_men"], errors="coerce")
    return df


def _index_level(df: pd.DataFrame, spec: list[tuple[str, ...]]) -> pd.DataFrame:
    """Set the era-appropriate hierarchical key (``spec``) as a sorted ``MultiIndex``.

    The key columns move into the index (as the extended-census loaders do with
    ``ID_VIV``/``ID_PERSONA``). Warns if the key is not unique in this frame (it should be —
    the dwelling/household/person keys are verified unique at their level), so a future era
    that breaks uniqueness surfaces rather than silently producing a non-unique index.
    """
    key = _level_key(spec, df)
    if df.duplicated(subset=key).any():
        warnings.warn(
            f"ENOE level key {key} is not unique in this frame; the index will be non-unique "
            f"(a key column may be renamed/missing in this era).", stacklevel=3,
        )
    return df.set_index(key).sort_index()


def load_enoe_viviendas(period: str | None = None, *, ent: int | None = None) -> pd.DataFrame:
    """Load the ENOE **dwelling** (``viv``) table for one quarter, analysis-ready.

    Like :func:`load_enoe_persons` but at the dwelling level: fetches/validates the raw ``viv``
    table (via :func:`load_enoe`), makes the expansion weights numeric (``fac_tri``/``fac_men``,
    coalescing the pre-2020-T3 ``fac``), and returns it indexed by the era-appropriate
    **dwelling key** ``MultiIndex`` (``cd_a, ent|cve_ent, con, v_sel`` + ``tipo, mes_cal[, ca]``
    from 2020-T3). The index is a clean prefix of the household/person index, so frames from
    :func:`load_enoe_hogares` / :func:`load_enoe_survey` align on it.

    Parameters
    ----------
    period : str, optional
        Quarter id (e.g. ``"2023t1"``); defaults to the latest quarter.
    ent : int, optional
        Keep only rows for INEGI state code ``ent`` (1–32). ENOE is national, so this is a
        post-load row filter.
    """
    period = period or latest_quarter().period
    viv = load_enoe(table="viv", period=period, ent=ent)
    return _index_level(_coalesce_fac_tri(viv), _DWELLING_KEY_SPEC)


def load_enoe_hogares(period: str | None = None, *, ent: int | None = None) -> pd.DataFrame:
    """Load the ENOE **household** (``hog``) table for one quarter, analysis-ready.

    As :func:`load_enoe_viviendas`, but at the household level: numeric weights and a
    **household key** ``MultiIndex`` (the dwelling key + ``n_hog, h_mud``). Its index extends
    the dwelling index and is itself a prefix of the person index.

    Parameters mirror :func:`load_enoe_viviendas` (``period`` default latest; ``ent`` row filter).
    """
    period = period or latest_quarter().period
    hog = load_enoe(table="hog", period=period, ent=ent)
    return _index_level(_coalesce_fac_tri(hog), _HOUSEHOLD_KEY_SPEC)


def load_enoe_survey(
    period: str | None = None, *, ent: int | None = None, persons: str = "all"
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all three ENOE household-survey levels with a **shared, nested** ``MultiIndex``.

    Returns ``(viviendas, hogares, personas)`` — dwelling, household, and person frames whose
    key indices are clean prefixes of one another (dwelling ⊂ household ⊂ person), the way the
    extended-census microdata shares ``ID_VIV`` / ``[ID_VIV, ID_PERSONA]``. Because the indices
    nest, the levels align and join naturally (e.g. ``personas.join(hogares, on=<hog levels>)``).

    Parameters
    ----------
    period : str, optional
        Quarter id (e.g. ``"2023t1"``); defaults to the latest quarter.
    ent : int, optional
        Restrict all three frames to INEGI state code ``ent`` (1–32).
    persons : {"all", "labor"}, default "all"
        Which person frame to return, indexed by the person key:

        - ``"all"`` — the full ``sdem`` table (every household member, demographics, numeric
          weight), so each household/dwelling **fully decomposes** into its members.
        - ``"labor"`` — the working-age labor-force analytical frame from
          :func:`load_enoe_persons` (SDEM⋈COE, canonical universe filter, ``is_pea`` /
          ``is_ocupado`` / ``is_informal`` flags). Note this keeps only interviewed 15+ members,
          so per-household person sums do **not** reconstruct full household size.
    """
    if persons not in ("all", "labor"):
        raise ValueError(f"persons must be 'all' or 'labor', got {persons!r}")
    period = period or latest_quarter().period
    viviendas = load_enoe_viviendas(period=period, ent=ent)
    hogares = load_enoe_hogares(period=period, ent=ent)
    if persons == "all":
        sdem = load_enoe(table="sdem", period=period, ent=ent)
        personas = _index_level(_coalesce_fac_tri(sdem), _PERSON_KEY_SPEC)
    else:  # "labor"
        frame = load_enoe_persons(period=period, ent=ent, canonical_filter=True)
        personas = _index_level(frame, _PERSON_KEY_SPEC)
    return viviendas, hogares, personas
