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

- :func:`load_enoe_viviendas` / :func:`load_enoe_hogares` / :func:`load_enoe_survey` — the
  dwelling/household tables (numeric weights, hierarchical ``MultiIndex``) and the three
  levels together with a shared nested index.

All loaders accept ``harmonize=True`` for cross-era **analytical-core harmonization**
(:func:`_harmonize`): lowercase names, ``fac``→``fac_tri`` (+ ``fac_men``), ``ent``/``mun``→
zero-padded ``cve_ent``/``cve_mun`` + ``cvegeo``, NA ``tipo``/``mes_cal`` before 2020-T3 —
validated against :func:`_latest_schema`. Unlike DENUE it keeps every non-core column
verbatim (the COE ampliado/básico questionnaires have disjoint item sets). The maintainer
``build_enoe.py --validate`` sweep is the authoritative per-file hard pass/fail report
(``docs/enoe/VALIDATION_REPORT.md``).
"""
from __future__ import annotations

import functools
import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from mxcensus import _schema_groups as _sg
from mxcensus._resources import enoe_schema_map, variables_enoe, variables_enoe_core
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
# key is used. The entity code was renamed ``ent`` → ``cve_ent`` in 2025-T3 (the ``cve_*``
# geographic-key rename), so it resolves across both names.
_ENT_ALIASES = ("ent", "cve_ent")
_DWELLING_KEY_SPEC: list[tuple[str, ...]] = [
    ("cd_a",), _ENT_ALIASES, ("con",), ("v_sel",), ("tipo",), ("mes_cal",), ("ca",),
]
_HOUSEHOLD_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("n_hog",), ("h_mud",)]
_PERSON_KEY_SPEC: list[tuple[str, ...]] = _HOUSEHOLD_KEY_SPEC + [("n_ren",)]


def _fingerprint(columns) -> str:
    """Schema-group fingerprint (shared recipe, see :mod:`mxcensus._schema_groups`)."""
    return _sg.fingerprint(columns)


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one ENOE ``(table, schema group)``'s raw frame.

    Built from ``variables_enoe_{table}_{gid}.yaml`` by :func:`_schema_groups.build_group_schema`:
    expansion weights (``_WEIGHTS``) → numeric; ``Categorías`` → strict ``isin`` (complete,
    FD-sourced value-sets for the analytical core); else nullable string.
    """
    cols = enoe_schema_map()[table]["groups"][gid]["columns"]
    return _sg.build_group_schema(cols, variables_enoe(table, gid), weights=_WEIGHTS)


def _group_of(table: str, df: pd.DataFrame) -> str:
    """Resolve a loaded ENOE frame to its per-table schema group id (raises if unknown)."""
    return _sg.group_of("ENOE", enoe_schema_map().get(table), df.columns,
                        map_name="enoe_schema_map.yaml", unit="quarter")


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise."""
    _sg.validate_warn("ENOE", schema, frame, label)


def _filter_ent(df: pd.DataFrame, ent: int) -> pd.DataFrame:
    """Return only the rows for state ``ent`` (1–32).

    Resolves the entity column across the ``ent``→``cve_ent`` rename and coerces numerically,
    so it works whether the codes are un-padded (``'9'``) or zero-padded (``'09'``).
    """
    col = next((c for c in _ENT_ALIASES if c in df.columns), None)
    if col is None:
        raise KeyError(f"no entity column {_ENT_ALIASES} in frame")
    return df[pd.to_numeric(df[col], errors="coerce") == int(ent)].reset_index(drop=True)


# ---------------------------------------------------------------------------------------
# Cross-era harmonization (``harmonize=True``)
# ---------------------------------------------------------------------------------------
# ENOE's schema drift is of two kinds. (1) *Renames of the analytical core* — keys, geographic
# codes, expansion weights and design variables — which are well understood and era-wide:
# 2019-T3/T4 files are UPPERCASE; ``fac``/``est_d``/``t_loc`` became ``fac_tri``/``est_d_tri``/
# ``t_loc_tri`` (+ ``*_men``) in 2020-T3, when the panel identifiers ``tipo``/``mes_cal`` also
# appeared; ``ent``/``mun``/``loc``/``ageb`` became zero-padded ``cve_*`` (+ derived ``cvegeo``)
# in 2025-T3. (2) *Questionnaire changes* — the COE alternates an **ampliado** (Q1) and a
# **básico** (Q2–Q4) instrument with different item sets, and SDEM renumbered items in
# 2025-T3. Unlike DENUE, ENOE therefore must NOT be projected onto the latest group's exact
# column list (that would drop every básico-only item); harmonization here canonicalizes (1)
# and keeps every other column verbatim. The maps are generic (not per-group), so a future
# quarter that only adds a new fingerprint harmonizes without a map edit.
_RENAME_CORE: dict[str, str] = {
    "fac": "fac_tri", "est_d": "est_d_tri", "t_loc": "t_loc_tri",
    "ent": "cve_ent", "mun": "cve_mun", "loc": "cve_loc", "ageb": "cve_ageb",
}
# Zero-padding widths for the geographic codes INEGI pads from 2025-T3 (``cve_loc`` is blank
# and ``cve_ageb`` a ``00000`` placeholder in every era → renamed only, never padded).
_GEO_PAD: dict[str, int] = {"cve_ent": 2, "cve_mun": 3}
# ``cvegeo`` = ``cve_ent`` + ``cve_mun``; INEGI writes ``999`` for an unspecified municipality.
_CVEGEO_UNSPECIFIED_MUN = "999"
# Core columns added as all-NA when an era lacks them (so every harmonized frame has them).
_CORE_ADD: tuple[str, ...] = (
    "fac_men", "est_d_men", "t_loc_men", "tipo", "mes_cal", "cve_loc", "cve_ageb", "cvegeo",
)
# Harmonized-schema regexes for the padded codes (blank = not applicable is allowed).
_GEO_REGEX: dict[str, str] = {
    "cve_ent": r"^(\d{2}|\s*)$", "cve_mun": r"^(\d{3}|\s*)$", "cvegeo": r"^(\d{5}|\s*)$",
}


def _zfill_codes(s: pd.Series, width: int) -> pd.Series:
    """Zero-pad the all-digit values of a string series (NA/blank/non-digit left as is)."""
    digits = s.str.fullmatch(r"\d+").fillna(False).astype(bool)
    return s.where(~digits, s.str.zfill(width))


@functools.cache
def _core_order() -> list[str]:
    """Harmonized names of the analytical-core columns, in ``variables_enoe_core.yaml`` order."""
    return list(dict.fromkeys(_RENAME_CORE.get(c, c) for c in variables_enoe_core()))


def _harmonize(df: pd.DataFrame, table: str, label: str = "") -> pd.DataFrame:
    """Canonicalize one raw ENOE frame's analytical core across eras (see the notes above).

    Steps, in order: lowercase all column names (2019-T3/T4 UPPERCASE files) → apply
    :data:`_RENAME_CORE` to the sources present (a frame that already has both a source and
    its target is refused — nothing is ever silently overwritten) → zero-pad the geographic
    codes (:data:`_GEO_PAD`; idempotent on already-padded 2025-T3+ frames) → derive ``cvegeo``
    when absent → add the :data:`_CORE_ADD` columns an era lacks as NA → reorder so the core
    columns (:func:`_core_order`) lead and every other column follows in its original order.
    Values are otherwise untouched; era-only columns (``ca``, básico-only COE items,
    pre-2025-T3 SDEM item numbering) are kept verbatim. Raw ``dtype=str`` is preserved.
    """
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    rename = {src: tgt for src, tgt in _RENAME_CORE.items() if src in out.columns}
    clash = sorted(tgt for src, tgt in rename.items() if tgt in out.columns)
    if clash:
        raise ValueError(
            f"ENOE {table} {label}: cannot harmonize — both a legacy column and its target "
            f"exist for {clash}; the frame mixes eras or was already harmonized differently."
        )
    out = out.rename(columns=rename)
    for col, width in _GEO_PAD.items():
        if col in out.columns:
            out[col] = _zfill_codes(out[col], width)
    if "cvegeo" not in out.columns and {"cve_ent", "cve_mun"} <= set(out.columns):
        mun = out["cve_mun"]
        mun = mun.where(mun.str.fullmatch(r"\d+").fillna(False).astype(bool), _CVEGEO_UNSPECIFIED_MUN)
        out["cvegeo"] = (out["cve_ent"] + mun).where(out["cve_ent"].notna())
    for col in _CORE_ADD:
        if col not in out.columns:
            out[col] = pd.Series(pd.NA, index=out.index, dtype=out.dtypes.iloc[0])
    # Stale-map guard (mirrors DENUE): every table carries ent + a weight, so their targets
    # must exist after harmonization — a miss means INEGI renamed a source we don't know.
    expected = {"cve_ent", "fac_tri"}
    missing = sorted(expected - set(out.columns))
    if missing:
        warnings.warn(
            f"ENOE {table} {label}: harmonization produced no {missing} — a core source "
            f"column may be renamed in this era; _RENAME_CORE may be stale.", stacklevel=3,
        )
    lead = [c for c in _core_order() if c in out.columns]
    rest = [c for c in out.columns if c not in lead]
    return out[lead + rest]


@functools.cache
def _latest_schema(table: str) -> pa.DataFrameSchema:
    """Tight-where-safe Pandera schema for a **harmonized** ENOE frame of ``table``.

    Analytical-core columns with FD-sourced ``Categorías`` in ``variables_enoe_core.yaml``
    get a strict ``isin`` (their codes are era-stable); the expansion weights are numeric;
    the padded geographic codes get a width regex (blank allowed — "not applicable"); every
    other core column is a nullable string. Only the columns every table carries after
    harmonization (``cve_ent``, ``fac_tri``, :data:`_CORE_ADD`) are *required* — ``viv``/
    ``hog`` have no person-level core. ``strict=False``: the questionnaire items an era
    carries are validated per-era by :func:`_group_schema`, not here.
    """
    always = {"cve_ent", "fac_tri", *_CORE_ADD}
    cols = {_RENAME_CORE.get(raw, raw): (meta.get("Categorías") or {})
            for raw, meta in variables_enoe_core().items()}
    for col in _CORE_ADD:
        cols.setdefault(col, {})
    schema = {}
    for col, cats in cols.items():
        req = col in always
        if col in _WEIGHTS:
            schema[col] = pa.Column(float, nullable=True, coerce=True, required=req)
        elif col in _GEO_REGEX:
            schema[col] = pa.Column(str, pa.Check.str_matches(_GEO_REGEX[col]),
                                    nullable=True, coerce=True, required=req)
        elif cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True,
                                    coerce=True, required=req)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True, required=req)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


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
        If ``True``, canonicalize the analytical core across eras (:func:`_harmonize`):
        lowercase names, ``fac``/``est_d``/``t_loc`` → ``*_tri`` (+ NA ``*_men``), ``ent``/
        ``mun``/``loc``/``ageb`` → zero-padded ``cve_*`` + derived ``cvegeo``, NA ``tipo``/
        ``mes_cal`` before 2020-T3 — keeping every other column verbatim — and validate the
        result against :func:`_latest_schema`. ``False`` returns the raw per-era schema.
    ent : int, optional
        Keep only rows for INEGI state code ``ent`` (1–32). ENOE is national, so this is a
        post-load row filter, not a separate file.

    The frame is validated against its group's tight schema; value-level violations emit a
    ``warnings.warn`` summary (they do not raise). An unrecognized schema raises ``ValueError``.
    """
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}; known: {TABLES}")
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
    label = f"{table} {period or survey_path.stem} ({gid})"
    _validate(_group_schema(table, gid), df, f"{label} raw")
    if harmonize:
        df = _harmonize(df, table, label)
        _validate(_latest_schema(table), df, f"{label} harmonized")
    return df


def _level_key(spec: list[tuple[str, ...]], *frames: pd.DataFrame) -> list[str]:
    """Resolve a key ``spec`` to the columns present in every frame (shared helper)."""
    return _sg.level_key(spec, *frames)


def _person_key(*frames: pd.DataFrame) -> list[str]:
    """Person-key columns present in every given frame (see :func:`_level_key`)."""
    return _level_key(_PERSON_KEY_SPEC, *frames)


def load_enoe_persons(
    period: str | None = None,
    *,
    ent: int | None = None,
    canonical_filter: bool = True,
    harmonize: bool = False,
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
    harmonize : bool, default False
        Passed to :func:`load_enoe` for the three tables: canonicalize the analytical core
        across eras (``cve_ent``/``cvegeo``, ``fac_tri``/``fac_men``, ``tipo``/``mes_cal``, …)
        so frames from different quarters stack. The person key resolves either way.

    Added columns
    -------------
    - ``fac_tri`` — canonical trimestral expansion weight, **numeric**, coalescing the raw
      ``fac_tri`` (2020-T3+) or ``fac`` (earlier) string column.
    - ``is_pea`` (``clase1==1``), ``is_ocupado`` (``clase2==1``), ``is_informal``
      (``emp_ppal==1``) — boolean labour-force flags.

    All other columns are the faithful raw ``dtype=str`` values.
    """
    period = period or latest_quarter().period
    sdem = load_enoe(table="sdem", period=period, ent=ent, harmonize=harmonize)
    coe1 = load_enoe(table="coe1", period=period, ent=ent, harmonize=harmonize)
    coe2 = load_enoe(table="coe2", period=period, ent=ent, harmonize=harmonize)

    key = _person_key(sdem, coe1, coe2)
    # Guard against a silent fan-out: if the key isn't unique in SDEM (e.g. a future era
    # renames a key column so it drops out of the join, as 2025-T3 did with ent→cve_ent),
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
    """Set the era-appropriate hierarchical key as a sorted ``MultiIndex`` (shared helper)."""
    return _sg.index_level("ENOE", df, spec)


def load_enoe_viviendas(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> pd.DataFrame:
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
    harmonize : bool, default False
        Canonicalize the analytical core across eras (see :func:`load_enoe`).
    """
    period = period or latest_quarter().period
    viv = load_enoe(table="viv", period=period, ent=ent, harmonize=harmonize)
    return _index_level(_coalesce_fac_tri(viv), _DWELLING_KEY_SPEC)


def load_enoe_hogares(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> pd.DataFrame:
    """Load the ENOE **household** (``hog``) table for one quarter, analysis-ready.

    As :func:`load_enoe_viviendas`, but at the household level: numeric weights and a
    **household key** ``MultiIndex`` (the dwelling key + ``n_hog, h_mud``). Its index extends
    the dwelling index and is itself a prefix of the person index.

    Parameters mirror :func:`load_enoe_viviendas` (``period`` default latest; ``ent`` row
    filter; ``harmonize`` cross-era core canonicalization).
    """
    period = period or latest_quarter().period
    hog = load_enoe(table="hog", period=period, ent=ent, harmonize=harmonize)
    return _index_level(_coalesce_fac_tri(hog), _HOUSEHOLD_KEY_SPEC)


def load_enoe_survey(
    period: str | None = None,
    *,
    ent: int | None = None,
    persons: str = "all",
    harmonize: bool = False,
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
    harmonize : bool, default False
        Canonicalize the analytical core of all three frames across eras (see
        :func:`load_enoe`), so surveys from different quarters share index names
        (``cve_ent`` rather than the era's ``ent``/``cve_ent``) and weight columns.
    """
    if persons not in ("all", "labor"):
        raise ValueError(f"persons must be 'all' or 'labor', got {persons!r}")
    period = period or latest_quarter().period
    viviendas = load_enoe_viviendas(period=period, ent=ent, harmonize=harmonize)
    hogares = load_enoe_hogares(period=period, ent=ent, harmonize=harmonize)
    if persons == "all":
        sdem = load_enoe(table="sdem", period=period, ent=ent, harmonize=harmonize)
        personas = _index_level(_coalesce_fac_tri(sdem), _PERSON_KEY_SPEC)
    else:  # "labor"
        frame = load_enoe_persons(period=period, ent=ent, canonical_filter=True,
                                  harmonize=harmonize)
        personas = _index_level(frame, _PERSON_KEY_SPEC)
    return viviendas, hogares, personas
