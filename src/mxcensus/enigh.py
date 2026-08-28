"""ENIGH (Encuesta Nacional de Ingresos y Gastos de los Hogares) — loader + schema layer.

ENIGH is INEGI's biennial household income/expenditure survey, mirrored per (table,
edition) as ``enigh_{table}_{period}.parquet`` (``period`` = the edition year, e.g.
``"2022"``; see ``mxcensus.data._enigh_catalog`` and ``scripts/build_enigh.py``). Like
ENOE it drifts across editions, so every mirrored file is fingerprinted into a **per-table**
schema group (``_yaml/enigh_schema_map.yaml``) and validated against a tight per-group
Pandera schema built from that group's ``variables_enigh_{table}_{gid}.yaml``.

Two series are mirrored: the **nueva serie** (2016–2024) and INEGI's conciliated **Nueva
Construcción de Variables** re-expression of the traditional series (2008–2014). 2014 → 2016
is a **methodological break** (sample redesign, MCS merger, income-capture changes) — the
loaders make the columns line up; they do not make the estimates comparable. See
``docs/enigh/STEP_0_probe.md``.

Public API:

- :func:`load_enigh` — one raw table for one edition (faithful ``dtype=str`` frame).
- :func:`load_enigh_hogares` — the analysis-ready household frame (``concentradohogar``:
  income/expenditure aggregates, numeric weight), indexed by the household key.
- :func:`load_enigh_viviendas` / :func:`load_enigh_personas` — dwelling (``viviendas``) and
  person (``poblacion``) frames with a numeric ``factor`` (joined from the household summary
  when the raw table carries none), indexed by their level key.
- :func:`load_enigh_survey` — ``(viviendas, hogares, personas)`` with a shared nested
  ``MultiIndex`` (dwelling ⊂ household ⊂ person), as the ENOE/extended-census loaders.

All loaders accept ``harmonize=True`` for **analytical-core harmonization** across editions
(:func:`_harmonize`): lowercase names, the 2012–2014 ``factor_hog``/``factor_viv`` → ``factor``,
the 2008/2010 ``concentradohogar`` spellings (``ingcor``→``ing_cor``, ``tam_hog``→``tot_integ``,
head ``sexo``/``edad``/``ed_formal``→``*_jefe``, …), zero-padded ``educa_jefe``, and derived
``cve_ent``/``cve_mun``/``cve_loc``/``cvegeo`` from ``ubica_geo`` (or the entity from
``folioviv``). Every other column is kept verbatim — expenditure/income ``clave`` codes are
NOT bridged across the 2024 CCIF re-basing.
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

from mxcensus._resources import enigh_schema_map, variables_enigh, variables_enigh_core
from mxcensus.data._enigh_catalog import EDITIONS_BY_PERIOD, TABLES, latest_edition

# Expansion weights — validated as numeric. ``factor_hog``/``factor_viv`` are the 2012–2014
# NCV spellings (harmonized to ``factor``).
_WEIGHTS = {"factor", "factor_hog", "factor_viv"}

# Survey keys: dwelling ⊂ household ⊂ person, clean prefixes of one another (verified unique
# at each level in every edition), so they double as the nested MultiIndex levels.
_DWELLING_KEY_SPEC: list[tuple[str, ...]] = [("folioviv",)]
_HOUSEHOLD_KEY_SPEC: list[tuple[str, ...]] = _DWELLING_KEY_SPEC + [("foliohog",)]
_PERSON_KEY_SPEC: list[tuple[str, ...]] = _HOUSEHOLD_KEY_SPEC + [("numren",)]


def _fingerprint(columns) -> str:
    """sha256 over the ordered column names — same recipe as ``scripts/build_enigh.py``."""
    return sha256(json.dumps(list(columns)).encode()).hexdigest()


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one ENIGH ``(table, schema group)``'s raw frame.

    Weights → numeric (coercible); any column with a non-empty ``Categorías`` map → strict
    ``isin`` on its keys (complete, hand-curated value-sets for the analytical core;
    data-enumerated otherwise); everything else → nullable string. ``strict=False``.
    """
    vars_ = variables_enigh(table, gid)
    cols = enigh_schema_map()[table]["groups"][gid]["columns"]
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
    """Resolve a loaded frame to its per-table schema group id (raises if unknown)."""
    fp = _fingerprint(list(df.columns))
    gid = enigh_schema_map().get(table, {}).get("fingerprints", {}).get(fp)
    if gid is None:
        raise ValueError(
            f"ENIGH {table} file schema not found in enigh_schema_map.yaml (stale mirror or "
            f"map, or an edition not covered by the current build?)."
        )
    return gid


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise."""
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        fc = exc.failure_cases
        top = fc.groupby(["column", "check"]).size().sort_values(ascending=False).head(6)
        detail = "; ".join(f"{col}/{chk}×{n}" for (col, chk), n in top.items())
        warnings.warn(f"ENIGH {label}: {len(fc)} schema violation(s) [{detail}]", stacklevel=3)


def _filter_ent(df: pd.DataFrame, ent: int) -> pd.DataFrame:
    """Keep the rows of state ``ent`` (1–32): the first two characters of ``folioviv`` are
    the entity code in every edition and table (equal to ``ubica_geo[:2]`` where present)."""
    col = "folioviv" if "folioviv" in df.columns else "FOLIOVIV"
    return df[pd.to_numeric(df[col].str[:2], errors="coerce") == int(ent)].reset_index(drop=True)


# ---------------------------------------------------------------------------------------
# Cross-edition harmonization (``harmonize=True``)
# ---------------------------------------------------------------------------------------
# Only the analytical core is canonicalized; everything else stays verbatim (questionnaire
# items and expenditure ``clave`` codes change meaning across editions and must not be
# renamed blindly). The rename maps are keyed per table because the 2008/2010 head
# variables (``sexo``/``edad``) collide with the person-level names in ``poblacion``.
_RENAME_ALL: dict[str, str] = {"factor_hog": "factor", "factor_viv": "factor"}
_RENAME_TABLE: dict[str, dict[str, str]] = {
    "concentradohogar": {
        "ingcor": "ing_cor", "tam_hog": "tot_integ", "n_ocup": "ocupados",
        "pering": "percep_ing", "perocu": "perc_ocupa",
        "sexo": "sexo_jefe", "edad": "edad_jefe", "ed_formal": "educa_jefe",
    },
}
_PAD: dict[str, int] = {"educa_jefe": 2}
_GEO_ADD: tuple[str, ...] = ("cve_ent", "cve_mun", "cve_loc", "cvegeo")
_GEO_REGEX: dict[str, str] = {
    "cve_ent": r"^\d{2}$", "cve_mun": r"^\d{3}$", "cve_loc": r"^\d{4}$", "cvegeo": r"^\d{5}$",
}


def _zfill_codes(s: pd.Series, width: int) -> pd.Series:
    digits = s.str.fullmatch(r"\d+").fillna(False).astype(bool)
    return s.where(~digits, s.str.zfill(width))


@functools.cache
def _core_order() -> list[str]:
    """Harmonized names of the analytical-core columns, in ``variables_enigh_core.yaml``
    order, followed by the derived geography."""
    return list(dict.fromkeys(list(variables_enigh_core()) + list(_GEO_ADD)))


def _harmonize(df: pd.DataFrame, table: str, label: str = "") -> pd.DataFrame:
    """Canonicalize one raw ENIGH frame's analytical core across editions.

    Steps: lowercase names → per-table + global core renames (refusing a frame that already
    carries both a source and its target) → zero-pad ``educa_jefe`` → derive ``cve_ent`` /
    ``cve_mun`` / ``cve_loc`` / ``cvegeo`` from ``ubica_geo`` (5 = ent+mun in 2008/2010/2024,
    9 = ent+mun+loc in 2012–2022; ``cve_loc`` NA when absent) or, without ``ubica_geo``, just
    ``cve_ent`` from ``folioviv`` → core columns first. Values are otherwise untouched.
    """
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    rename = {**_RENAME_ALL, **_RENAME_TABLE.get(table, {})}
    rename = {s: t for s, t in rename.items() if s in out.columns}
    clash = sorted(t for s, t in rename.items() if t in out.columns)
    if clash:
        raise ValueError(
            f"ENIGH {table} {label}: cannot harmonize — both a legacy column and its target "
            f"exist for {clash}; the frame mixes editions or was already harmonized differently."
        )
    out = out.rename(columns=rename)
    for col, width in _PAD.items():
        if col in out.columns:
            out[col] = _zfill_codes(out[col], width)
    na = pd.Series(pd.NA, index=out.index, dtype=out.dtypes.iloc[0])
    if "ubica_geo" in out.columns:
        g = out["ubica_geo"].str.strip()
        out["cve_ent"] = g.str[:2]
        out["cve_mun"] = g.str[2:5]
        out["cve_loc"] = g.str[5:9].where(g.str.len() >= 9)
        out["cvegeo"] = g.str[:5]
    elif "folioviv" in out.columns:
        out["cve_ent"] = out["folioviv"].str[:2]
        for col in ("cve_mun", "cve_loc", "cvegeo"):
            out[col] = na
    if "cve_ent" not in out.columns:
        warnings.warn(
            f"ENIGH {table} {label}: harmonization produced no cve_ent — neither ubica_geo "
            f"nor folioviv present; the rename maps may be stale.", stacklevel=3,
        )
    lead = [c for c in _core_order() if c in out.columns]
    rest = [c for c in out.columns if c not in lead]
    return out[lead + rest]


@functools.cache
def _latest_schema(table: str) -> pa.DataFrameSchema:
    """Tight-where-safe Pandera schema for a **harmonized** ENIGH frame of ``table``.

    Core categoricals get ``isin`` on the hand-curated (padded) codes, amounts/weights are
    numeric, the derived geography gets width regexes; only ``folioviv``/``cve_ent`` are
    required (tables differ in which core columns they carry). ``strict=False``.
    """
    core = variables_enigh_core()
    schema = {}
    for col, meta in core.items():
        cats = meta.get("Categorías") or {}
        req = col in ("folioviv",)
        if col == "educa_jefe":
            cats = {k: v for k, v in cats.items() if len(k) == 2}   # padded after _harmonize
        if col in _WEIGHTS or (meta.get("Tipo") in ("int", "float")):
            schema[col] = pa.Column(float, nullable=True, coerce=True, required=req)
        elif cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True, coerce=True,
                                    required=req)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True, required=req)
    for col, rx in _GEO_REGEX.items():
        schema[col] = pa.Column(str, pa.Check.str_matches(rx), nullable=True, coerce=True,
                                required=(col == "cve_ent"))
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


def load_enigh(
    survey_path: Path | None = None,
    *,
    table: str,
    period: str | None = None,
    harmonize: bool = False,
    ent: int | None = None,
) -> pd.DataFrame:
    """Load one raw ENIGH table for one edition as a faithful ``dtype=str`` DataFrame.

    - ``load_enigh(table="concentradohogar", period="2022")`` — fetch from the mirror via
      Pooch (``period`` defaults to the latest edition).
    - ``load_enigh(survey_path=Path("enigh_poblacion_2022.parquet"), table="poblacion")``.

    Parameters
    ----------
    table : str
        One of :data:`mxcensus.data._enigh_catalog.TABLES` (canonical nueva-serie names;
        ``gastotarjetas``/``gastos`` exist only for 2008–2014).
    period : str, optional
        Edition year (``"2008"`` … ``"2024"``); defaults to the latest.
    harmonize : bool, default False
        Canonicalize the analytical core across editions (:func:`_harmonize`) and validate
        against :func:`_latest_schema`.
    ent : int, optional
        Keep only rows of INEGI state ``ent`` (1–32) — a post-load row filter on ``folioviv``.

    Validation warns on value-level violations; an unknown schema raises ``ValueError``.
    """
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}; known: {TABLES}")
    if survey_path is None:
        period = period or latest_edition().period
        if period not in EDITIONS_BY_PERIOD:
            raise ValueError(f"unknown period {period!r}; known: {list(EDITIONS_BY_PERIOD)}")
        edition = EDITIONS_BY_PERIOD[period]
        if table not in edition.tables:
            raise ValueError(f"table {table!r} is not published for {edition.label}; "
                             f"available: {edition.tables}")
        from mxcensus.data._registry import POOCH
        survey_path = Path(POOCH.fetch(f"enigh_{table}_{period}.parquet"))

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


# --- analysis-ready loaders -------------------------------------------------------------

def _level_key(spec: list[tuple[str, ...]], *frames: pd.DataFrame) -> list[str]:
    common = set.intersection(*(set(f.columns) for f in frames))
    key = []
    for aliases in spec:
        col = next((c for c in aliases if c in common), None)
        if col is not None:
            key.append(col)
    return key


def _weight_col(df: pd.DataFrame) -> str | None:
    return next((c for c in ("factor", "factor_hog", "factor_viv") if c in df.columns), None)


def _numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _index_level(df: pd.DataFrame, spec: list[tuple[str, ...]]) -> pd.DataFrame:
    key = _level_key(spec, df)
    if df.duplicated(subset=key).any():
        warnings.warn(f"ENIGH level key {key} is not unique in this frame; the index will be "
                      f"non-unique.", stacklevel=3)
    return df.set_index(key).sort_index()


def _attach_factor(df: pd.DataFrame, period: str, ent: int | None, harmonize: bool,
                   key_spec: list[tuple[str, ...]]) -> pd.DataFrame:
    """Ensure ``df`` has a numeric ``factor`` (+ ``ubica_geo``/``tam_loc`` when it lacks
    geography), joining them from ``concentradohogar`` on the household key if needed.

    Many raw tables carry no weight (``poblacion`` before 2022, ``hogares`` 2016–2020, …);
    the household summary always does, and the expansion factor is constant within a
    dwelling, so the join is exact and never fans out.
    """
    w = _weight_col(df)
    if w is not None and w != "factor":
        df = df.rename(columns={w: "factor"})
    need = [c for c in ("factor", "ubica_geo", "tam_loc") if c not in df.columns]
    if need:
        conc = load_enigh(table="concentradohogar", period=period, ent=ent, harmonize=False)
        wc = _weight_col(conc)
        conc = conc.rename(columns={wc: "factor"}) if wc != "factor" else conc
        key = _level_key(key_spec, df, conc)
        cols = [c for c in need if c in conc.columns]
        extra = conc[key + cols].drop_duplicates(subset=key)
        df = df.merge(extra, on=key, how="left")
        if harmonize and "ubica_geo" in cols:  # keep derived geography consistent
            g = df["ubica_geo"].str.strip()
            df["cve_mun"], df["cvegeo"] = g.str[2:5], g.str[:5]
            df["cve_loc"] = g.str[5:9].where(g.str.len() >= 9)
    return _numeric(df, ["factor"])


def load_enigh_hogares(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> pd.DataFrame:
    """The analysis-ready **household** frame: ``concentradohogar`` (INEGI's per-household
    summary — income/expenditure aggregates, head characteristics, household composition)
    with a numeric ``factor`` and the main aggregates as numbers, indexed by the household
    key ``(folioviv, foliohog)``.

    ``harmonize=True`` folds the 2008–2014 spellings onto the nueva-serie names
    (``ing_cor``, ``tot_integ``, ``sexo_jefe``, …) so editions stack; note the 2014→2016
    series break when comparing levels.
    """
    period = period or latest_edition().period
    df = load_enigh(table="concentradohogar", period=period, ent=ent, harmonize=harmonize)
    df = _attach_factor(df, period, ent, harmonize, _HOUSEHOLD_KEY_SPEC)
    df = _numeric(df, ["ing_cor", "ingcor", "ingtrab", "gasto_mon", "tot_integ", "tam_hog",
                       "edad_jefe"])
    return _index_level(df, _HOUSEHOLD_KEY_SPEC)


def load_enigh_viviendas(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> pd.DataFrame:
    """The **dwelling** frame (``viviendas``, 2012+) with a numeric ``factor``, indexed by
    ``folioviv``. Raises for 2008/2010, which publish no dwelling table (dwelling items live
    in ``hogares`` there)."""
    period = period or latest_edition().period
    df = load_enigh(table="viviendas", period=period, ent=ent, harmonize=harmonize)
    df = _attach_factor(df, period, ent, harmonize, _DWELLING_KEY_SPEC)
    return _index_level(df, _DWELLING_KEY_SPEC)


def load_enigh_personas(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> pd.DataFrame:
    """The **person** frame (``poblacion``) with a numeric ``factor`` (joined from the
    household summary when the raw table carries none) and numeric ``edad``, indexed by the
    person key ``(folioviv, foliohog, numren)``. Σ ``factor`` = the expanded population."""
    period = period or latest_edition().period
    df = load_enigh(table="poblacion", period=period, ent=ent, harmonize=harmonize)
    df = _attach_factor(df, period, ent, harmonize, _HOUSEHOLD_KEY_SPEC)
    df = _numeric(df, ["edad"])
    return _index_level(df, _PERSON_KEY_SPEC)


def load_enigh_survey(
    period: str | None = None, *, ent: int | None = None, harmonize: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three survey levels with a **shared nested** ``MultiIndex``.

    Returns ``(viviendas, hogares, personas)`` = :func:`load_enigh_viviendas`,
    :func:`load_enigh_hogares` (the ``concentradohogar`` summary), :func:`load_enigh_personas`,
    whose indices are clean prefixes of one another (dwelling ⊂ household ⊂ person), as the
    extended-census microdata shares ``ID_VIV`` / ``[ID_VIV, ID_PERSONA]``. Requires an
    edition with a dwelling table (2012+).
    """
    period = period or latest_edition().period
    viviendas = load_enigh_viviendas(period=period, ent=ent, harmonize=harmonize)
    hogares = load_enigh_hogares(period=period, ent=ent, harmonize=harmonize)
    personas = load_enigh_personas(period=period, ent=ent, harmonize=harmonize)
    return viviendas, hogares, personas
