"""CPV family — aggregate products: intercensal estimates and the censuses' ITER/AGEB.

- **Encuesta Intercensal 2025 estimates** (``estimaciones``, :func:`load_cpv_estimaciones`):
  one national file with five rows per geography — the estimate and its standard error,
  90 % confidence limits and coefficient of variation — for the nation, the 32 states,
  every municipality, the 233 localities of 50 000 or more inhabitants, and each state's
  remainder of smaller localities (``CVE_MUN`` 997 / ``CVE_LOC`` 9997).
- **Census ITER and AGEB results** (CPV 2010, 2020): :func:`load_cpv_iter` (state,
  municipality, locality), :func:`load_cpv_ageb` (… urban AGEB and block) and
  :func:`load_cpv_census`, the port of the legacy :func:`mxcensus.load_census` (four count
  levels with the collective-population columns and the zero imputation) onto the ``cpv_``
  files — equal to it for 2020. Indicator names across editions: ``cpv_iter_crosswalk``.

The geography is split on the **string** codes (never cast to int), so the keys stay
joinable with the microdata (:mod:`mxcensus.cpv`) and the Marco Geoestadístico.
"""
from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from mxcensus import _schema_groups as _sg
from mxcensus.cpv import _SKIP, _edition, _labels_for, _load_cpv_raw

# ESTIMADOR (INEGI's row label) → short name, in the published row order.
_ESTIMADOR: dict[str, str] = {
    "Valor": "valor",
    "Error estándar": "ee",
    "Límite inferior de confianza": "li",
    "Límite superior de confianza": "ls",
    "Coeficiente de variación": "cv",
}
ESTIMADORES: tuple[str, ...] = tuple(_ESTIMADOR.values())

# Geographic level of an estimaciones row, coarse to fine (ordered categorical ``NIVEL``).
NIVELES: tuple[str, ...] = ("nacional", "estatal", "municipal", "resto_estatal", "localidad")
_RESTO_MUN, _RESTO_LOC = "997", "9997"
_GEO_INDEX = ["CVE_ENT", "CVE_MUN", "CVE_LOC"]


def _choice(value, allowed: tuple[str, ...], name: str) -> list[str]:
    """``value`` (one name or a sequence; ``None`` = all) → a validated list in
    ``allowed`` order."""
    if value is None:
        return list(allowed)
    wanted = [value] if isinstance(value, str) else list(value)
    unknown = [v for v in wanted if v not in allowed]
    if unknown or not wanted:
        raise ValueError(f"{name} must be one of {list(allowed)} (or a list of them), "
                         f"got {value!r}")
    return [a for a in allowed if a in wanted]


def _nivel(df: pd.DataFrame) -> pd.Series:
    """The geographic level of each row, from its string codes: ``00`` entity → nacional;
    ``000`` municipality → estatal; ``997`` → resto_estatal (the state's localities under
    50 000); ``0000`` locality → municipal; any other locality → localidad (≥ 50 000)."""
    ent, mun, loc = (df[c].to_numpy(dtype=object) for c in _GEO_INDEX)
    level = np.select(
        [ent == "00", mun == "000", (mun == _RESTO_MUN) | (loc == _RESTO_LOC), loc == "0000"],
        ["nacional", "estatal", "resto_estatal", "municipal"], default="localidad",
    )
    return pd.Series(pd.Categorical(level, categories=NIVELES, ordered=True), index=df.index)


def load_cpv_estimaciones(
    period: str | int | None = None,
    *,
    estimador: str | Sequence[str] | None = "valor",
    nivel: str | Sequence[str] | None = None,
    state: int | Sequence[int] | None = None,
    survey_path: Path | None = None,
) -> pd.DataFrame:
    """The intercensal **estimates** as a labelled frame: one row per geography, one
    column per indicator, indexed by ``(CVE_ENT, CVE_MUN, CVE_LOC)``.

    Parameters
    ----------
    period : str or int, optional
        Edition year; defaults to the latest edition publishing estimates (2025).
    estimador : str, sequence of str or None, default ``"valor"``
        Which estimator rows to keep: ``valor`` (the estimate), ``ee`` (standard error),
        ``li``/``ls`` (90 % confidence limits), ``cv`` (coefficient of variation, %). A
        single name returns one row per geography; a list (or ``None`` = all five) adds
        ``ESTIMADOR`` as the last index level, an ordered categorical.
    nivel : str, sequence of str or None
        Keep only these geographic levels (``NIVEL``): ``nacional``, ``estatal``,
        ``municipal``, ``resto_estatal`` (each state's localities under 50 000,
        ``CVE_MUN`` 997 / ``CVE_LOC`` 9997), ``localidad`` (≥ 50 000). ``None`` = all.
    state : int or sequence of int, optional
        Keep only these states' rows (``CVE_ENT``; drops the national row).
    survey_path : Path, optional
        Read a local ``cpv_estimaciones_{period}.parquet`` instead of the mirror.

    Columns: ``NIVEL`` (ordered categorical), ``CVEGEO`` and the names ``NOM_ENT``/
    ``NOM_MUN``/``NOM_LOC``, then the indicators — counts ``Int64`` (``Float64`` when the
    selected rows hold fractions, e.g. standard errors), percentages and averages
    ``Float64``; ``NA`` (no aplica) and ``MI`` (muestra insuficiente) become missing.
    Validated strictly (raises on an out-of-dictionary value); the raw file is available as
    ``load_cpv(table="estimaciones")``.
    """
    wanted = _choice(estimador, ESTIMADORES, "estimador")
    levels = None if nivel is None else _choice(nivel, NIVELES, "nivel")
    raw, gids, label = _load_cpv_raw(survey_path, table="estimaciones", period=period,
                                     state=state)
    est = raw["ESTIMADOR"].map(_ESTIMADOR)
    if est.isna().any():
        raise ValueError(f"CPV {label}: unknown ESTIMADOR value(s) "
                         f"{sorted(raw['ESTIMADOR'][est.isna()].astype(str).unique())}")
    level = _nivel(raw)
    keep = est.isin(wanted)
    if levels is not None:
        keep &= level.isin(levels)

    variables = _labels_for("estimaciones", gids)
    df = raw.loc[keep].drop(columns="ESTIMADOR")
    df = _sg.label_frame(df, variables, family="CPV", skip=_SKIP)
    df.insert(0, "NIVEL", level[keep])
    index = list(_GEO_INDEX)
    if not isinstance(estimador, str):
        df["ESTIMADOR"] = pd.Categorical(est[keep], categories=ESTIMADORES, ordered=True)
        index.append("ESTIMADOR")
    df = df.set_index(index).sort_index()
    if not df.index.is_unique:
        raise ValueError(f"CPV {label}: the estimates are not unique per {index}.")
    schema = _sg.build_labelled_schema(df.columns, variables, skip=_SKIP)
    return _sg.validate_raise("CPV", schema, df, f"{label} labelled")


# ---------------------------------------------------------------------------------------
# Census aggregates: ITER (localities) and AGEB (urban AGEBs and blocks) — CPV 2010, 2020
# ---------------------------------------------------------------------------------------
# Every frame here is harmonized (CVE_* names, zero-padded string codes, CVEGEO) and
# labelled: counts Int64, ratios Float64, INEGI's reserved cells (``*`` — a locality or
# block with one or two inhabited dwellings — ``N/D``, ``N/A``) missing.

# Geographic level of an ITER row (``NIVEL``), coarse to fine. ``agregado`` marks the two
# rows INEGI publishes per state and municipality for the localities of one and of two
# inhabited dwellings (``CVE_LOC`` 9998 / 9999), which are not listed one by one.
NIVELES_ITER: tuple[str, ...] = ("estatal", "municipal", "agregado", "localidad")
# … and of an AGEB-file row.
NIVELES_AGEB: tuple[str, ...] = ("estatal", "municipal", "localidad", "ageb", "manzana")
_ITER_INDEX = ["CVE_ENT", "CVE_MUN", "CVE_LOC"]
_AGEB_INDEX = ["CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB", "CVE_MZA"]
_AGREGADO = ("9998", "9999")


def _nivel_iter(df: pd.DataFrame) -> pd.Series:
    mun, loc = (df[c].to_numpy(dtype=object) for c in ("CVE_MUN", "CVE_LOC"))
    level = np.select([(mun == "000") & (loc == "0000"), loc == "0000", np.isin(loc, _AGREGADO)],
                      ["estatal", "municipal", "agregado"], default="localidad")
    return pd.Series(pd.Categorical(level, categories=NIVELES_ITER, ordered=True), index=df.index)


def _nivel_ageb(df: pd.DataFrame) -> pd.Series:
    mun, loc, ageb, mza = (df[c].to_numpy(dtype=object) for c in _AGEB_INDEX[1:])
    level = np.select([mun == "000", loc == "0000", ageb == "0000", mza == "000"],
                      ["estatal", "municipal", "localidad", "ageb"], default="manzana")
    return pd.Series(pd.Categorical(level, categories=NIVELES_AGEB, ordered=True), index=df.index)


def _counts(df: pd.DataFrame) -> list[str]:
    """The count columns of a labelled aggregate frame (``Int64``)."""
    return [c for c in df.columns if str(df[c].dtype) == "Int64"]


def _impute_zeros(coarse: pd.DataFrame, fine: pd.DataFrame) -> pd.DataFrame:
    """Fill a fine level's missing counts with 0 where they must be 0 — the port of
    ``aggregate.impute_zeros_univariate`` onto string keys: for each coarse unit (``coarse``
    indexed by the leading levels of ``fine``'s index) and count column, when the coarse
    total already equals the sum of the fine units' known values, every missing fine value
    of that unit and column is 0."""
    keys = list(coarse.index.names)
    cols = [c for c in _counts(fine) if c in coarse.columns]
    known = fine[cols].groupby(level=keys).sum()
    exact = (coarse[cols] - known.reindex(coarse.index)).eq(0)
    exact = exact.reindex(fine.index.droplevel(list(range(len(keys), fine.index.nlevels))))
    fill = fine[cols].isna().to_numpy() & exact.fillna(False).to_numpy(dtype=bool)
    out = fine.copy()
    out[cols] = fine[cols].mask(fill, 0)
    return out


def _repair_spilled_names(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Undo INEGI's broken name quoting in an ITER row (harmonized names).

    The CGPV 2000 ITER CSV has two locality rows whose name contains ", " and spilled into
    the next field: Oaxaca 277-0101 «V» + «, LA (R» and Querétaro 012-0011 «D» + «, LA». From
    ``LONGITUD`` on every value sits one column to the right, and the row's last value is
    lost. Such a row (``LONGITUD`` starting with ", ") gets the spill back on ``NOM_LOC``,
    its values one column to the left and the last one missing. Its coordinates stay
    truncated as published. The repaired counts make the localities add up to their
    municipality exactly (POBTOT 143 and 3,402 where the spilled row read the altitude).
    The mirror and :func:`mxcensus.load_cpv` keep the row verbatim."""
    if not {"NOM_LOC", "LONGITUD"} <= set(df.columns):
        return df
    bad = df["LONGITUD"].fillna("").str.match(r"^,\s").to_numpy(bool)
    if not bad.any():
        return df
    df = df.copy()
    rest = list(df.columns[df.columns.get_loc("LONGITUD"):])
    values = df.loc[bad, rest].to_numpy(dtype=object)
    df.loc[bad, "NOM_LOC"] = df.loc[bad, "NOM_LOC"] + df.loc[bad, "LONGITUD"]
    df.loc[bad, rest] = np.concatenate([values[:, 1:], np.full((bad.sum(), 1), None)], axis=1)
    rows = (df.loc[bad, "CVEGEO"] if "CVEGEO" in df.columns else df.index[bad]).tolist()
    warnings.warn(f"CPV {label}: repaired {int(bad.sum())} ITER row(s) whose locality name "
                  f"spilled into LONGITUD (values shifted back one column): {rows}.",
                  stacklevel=3)
    return df


def _load_aggregate(table: str, period, state, survey_path) -> tuple[pd.DataFrame, str]:
    raw, gids, label = _load_cpv_raw(survey_path, table=table, period=period, state=state,
                                     harmonize=True)
    raw = _repair_spilled_names(raw, label)
    variables = _labels_for(table, gids)
    df = _sg.label_frame(raw, variables, family="CPV", skip=_SKIP)
    schema = _sg.build_labelled_schema(df.columns, variables, skip=_SKIP)
    return _sg.validate_raise("CPV", schema, df, f"{label} labelled"), label


def _by_level(df: pd.DataFrame, level: str, index: list[str]) -> pd.DataFrame:
    return df.loc[df["NIVEL"] == level].set_index(index).sort_index()


def load_cpv_iter(
    period: str | int | None = None,
    *,
    state: int | Sequence[int] | None,
    nivel: str | Sequence[str] | None = None,
    impute: bool = True,
    survey_path: Path | None = None,
) -> pd.DataFrame:
    """The census **ITER** (principales resultados por localidad) of one or more states:
    one row per state, municipality and locality, indexed ``(CVE_ENT, CVE_MUN, CVE_LOC)``.

    The frame is harmonized and labelled (see :func:`mxcensus.load_cpv`): counts ``Int64``,
    ratios and averages ``Float64``, INEGI's reserved cells (``*``: localities of one or two
    inhabited dwellings; ``N/D``; ``N/A``) missing. An ordered ``NIVEL`` column gives the
    row's level — ``estatal``, ``municipal``, ``agregado`` (``CVE_LOC`` 9998/9999: the
    localities of one / two dwellings of the state or municipality, published only as
    sums) or ``localidad`` — and ``nivel=`` keeps only those levels. The state's and the
    municipalities' rows are never reserved.

    ``impute=True`` (default) fills the reserved counts that must be 0: when a
    municipality's total equals the sum of its listed localities' known values, the
    missing values of that column in its localities are 0 (``aggregate.impute_zeros_
    univariate`` of the legacy loader).

    ``period`` defaults to the latest census with ITER (2020); 2000, 2005 and 2010 load
    the same way. The frame is harmonized: the indicators the crosswalk renames take the
    canonical (2020) name (CPV 2010 ``TAM_LOC``, Conteo 2005 ``P_TOTAL``/``P_MAS``…, CGPV
    2000 ``PMASCUL``/``OCUVIVPAR``…); every other indicator keeps its edition's name (see
    ``cpv_iter_crosswalk``). Two CGPV 2000 rows whose name spilled into ``LONGITUD`` in
    INEGI's CSV are repaired, with a warning (:func:`_repair_spilled_names`).
    """
    levels = None if nivel is None else _choice(nivel, NIVELES_ITER, "nivel")
    df, label = _load_aggregate("iter", period, state, survey_path)
    df.insert(0, "NIVEL", _nivel_iter(df))
    if impute:
        mun = _by_level(df, "municipal", _ITER_INDEX).droplevel("CVE_LOC")
        loc = _by_level(df, "localidad", _ITER_INDEX)
        loc = _impute_zeros(mun, loc)
        df = pd.concat([df.loc[df["NIVEL"] != "localidad"].set_index(_ITER_INDEX), loc])
    else:
        df = df.set_index(_ITER_INDEX)
    df = df.sort_index()
    if levels is not None:
        df = df.loc[df["NIVEL"].isin(levels)]
    if not df.index.is_unique:
        raise ValueError(f"CPV {label}: the ITER is not unique per {_ITER_INDEX}.")
    return df


# AGEB-file columns a block with no population can only hold as 0 (``aggregate.
# load_resargebub``'s "quick imputation of weird censored block variables").
_EMPTY_BLOCK_ZERO = ("TVIVHAB", "VIVPAR_HAB", "VIVPARH_CV", "TVIVPARHAB")


def load_cpv_ageb(
    period: str | int | None = None,
    *,
    state: int | Sequence[int] | None,
    nivel: str | Sequence[str] | None = None,
    impute: bool = True,
    survey_path: Path | None = None,
) -> pd.DataFrame:
    """The census **AGEB/block** results (urban AGEBs and their blocks) of one or more
    states, indexed ``(CVE_ENT, CVE_MUN, CVE_LOC, CVE_AGEB, CVE_MZA)``.

    Harmonized and labelled like :func:`load_cpv_iter`; the ordered ``NIVEL`` column is
    ``estatal``, ``municipal``, ``localidad`` (urban localities only), ``ageb`` or
    ``manzana``. ``CVEGEO`` (16 characters) is the Marco Geoestadístico's block key; an
    AGEB row's MG key is its first 13 characters.

    ``impute=True`` (default) fills counts that must be 0: the inhabited-dwelling counts of a
    row with no population, and — as :func:`load_cpv_iter` does for localities — an AGEB's
    missing counts when its locality's total already equals the sum of the locality's
    AGEBs' known values. Blocks are left as published: INEGI's block counts do not add up
    to their AGEB's in general.
    """
    levels = None if nivel is None else _choice(nivel, NIVELES_AGEB, "nivel")
    df, label = _load_aggregate("ageb", period, state, survey_path)
    df.insert(0, "NIVEL", _nivel_ageb(df))
    if impute:
        df = _zero_empty_blocks(df)
        loc = _by_level(df, "localidad", _AGEB_INDEX).droplevel(["CVE_AGEB", "CVE_MZA"])
        ageb = _by_level(df, "ageb", _AGEB_INDEX).droplevel("CVE_MZA")
        ageb = _impute_zeros(loc, ageb)
        ageb = ageb.set_index(pd.Index(["000"] * len(ageb), name="CVE_MZA"), append=True)
        df = pd.concat([df.loc[df["NIVEL"] != "ageb"].set_index(_AGEB_INDEX), ageb])
    else:
        df = df.set_index(_AGEB_INDEX)
    df = df.sort_index()
    if levels is not None:
        df = df.loc[df["NIVEL"].isin(levels)]
    if not df.index.is_unique:
        raise ValueError(f"CPV {label}: the AGEB file is not unique per {_AGEB_INDEX}.")
    return df


def _zero_empty_blocks(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _EMPTY_BLOCK_ZERO if c in df.columns]
    out = df.copy()
    empty = out["POBTOT"].eq(0).fillna(False).to_numpy(dtype=bool)
    out.loc[empty, cols] = 0
    return out


# Editions whose urban AGEBs count fewer inhabited dwellings (TVIVHAB) than their locality:
# in CPV 2010, 855 of the 4,525 urban localities, by 1-25 dwellings (never more), while
# POBTOT and VIVTOT add up exactly everywhere. CPV 2020's AGEBs add up exactly.
_AGEB_TVIVHAB_SHORT = frozenset({"2010"})


def _impute_collective(coarse: pd.DataFrame, fine: pd.DataFrame) -> pd.DataFrame:
    """``aggregate.impute_collective``, safe for missing values: where a coarse unit's
    collective population (dwellings) is fully accounted for by its fine units (the
    difference of the ``POBCOL``/``TOTCOL`` totals is 0), a fine unit's missing ``POBHOG``
    (``TOTHOG``) is its ``POBTOT`` (``TVIVHAB``); then ``POBCOL``/``TOTCOL`` are recomputed.
    A difference that is itself missing (a coarse total reserved) imputes nothing — the
    legacy loop's ``if diff == 0`` raises on it instead (``TypeError: boolean value of NA
    is ambiguous``, the legacy ``load_census`` of states 08, 15 and 16)."""
    fine = fine.copy()
    tot = ["POBTOT", "POBHOG", "POBCOL", "TVIVHAB", "TOTHOG", "TOTCOL"]
    keys = list(coarse.index.names)
    diff = coarse[tot] - fine.groupby(level=keys)[tot].sum()
    parent = fine.index.droplevel(list(range(len(keys), fine.index.nlevels)))
    for zero, target, source in (("POBCOL", "POBHOG", "POBTOT"), ("TOTCOL", "TOTHOG", "TVIVHAB")):
        done = diff.index[diff[zero].eq(0).fillna(False).to_numpy(bool)]
        mask = parent.isin(done.intersection(coarse.index)) & fine[target].isna().to_numpy()
        fine.loc[mask, target] = fine.loc[mask, source]
    fine["POBCOL"] = fine["POBTOT"] - fine["POBHOG"]
    fine["TOTCOL"] = fine["TVIVHAB"] - fine["TOTHOG"]
    return fine


def _add_collective_cols(st, mun, loc, ageb):
    """``aggregate.add_collective_cols`` with :func:`_impute_collective`: ``POBCOL`` and
    ``TOTCOL`` on every level, imputed municipality → locality and locality → AGEB."""
    st, mun, loc, ageb = (df.copy() for df in (st, mun, loc, ageb))
    for df in (st, mun, loc, ageb):
        df["POBCOL"] = df["POBTOT"] - df["POBHOG"]
        df["TOTCOL"] = df["TVIVHAB"] - df["TOTHOG"]
    loc = _impute_collective(mun, loc)
    ageb = _impute_collective(loc.loc[ageb.index.droplevel(-1).unique()], ageb)
    return st, mun, loc, ageb


def _census_checks(label: str, it: dict, ag: dict, period: str = "") -> None:
    """``aggregate.sanity_checks`` on string keys: the ITER and AGEB files agree on the
    state, municipalities and (urban) localities; municipalities add up to the state;
    localities add up to their municipality (exactly for the population and dwelling
    totals, never above it otherwise); urban AGEBs add up to their locality (2010's
    inhabited dwellings may fall short, never above: :data:`_AGEB_TVIVHAB_SHORT`)."""
    def check(ok: bool, what: str) -> None:
        if not ok:
            raise ValueError(f"CPV {label}: census check failed — {what}")

    def max_abs(a: pd.DataFrame, b: pd.DataFrame):
        d = (a - b).abs().max(axis=None)
        return 0 if pd.isna(d) else d

    exact = ["POBTOT", "VIVTOT", "TVIVHAB"]
    check(max_abs(ag["estatal"], it["estatal"]) == 0, "AGEB and ITER state rows differ")
    check(max_abs(it["municipal"], ag["municipal"]) == 0, "AGEB and ITER municipal rows differ")
    check(not it["municipal"].isna().any(axis=None), "missing values in municipal rows")
    mun_sum = it["municipal"].groupby(level="CVE_ENT").sum()
    check(bool((mun_sum.reindex(it["estatal"].index) == it["estatal"]).all(axis=None)),
          "municipalities do not add up to the state")
    loc = ag["localidad"]
    check(max_abs(it["localidad"].loc[loc.index, loc.columns], loc) == 0,
          "AGEB and ITER urban locality rows differ")
    delta = it["municipal"] - it["localidad"].groupby(level=["CVE_ENT", "CVE_MUN"]).sum()
    check(bool((delta >= 0).all(axis=None)), "localities add up to more than their municipality")
    check(bool((delta[exact] == 0).all(axis=None)),
          f"localities do not add up to their municipality's {exact}")
    agebs = ag["ageb"].groupby(level=_ITER_INDEX)[exact].sum()
    short = ["TVIVHAB"] if str(period) in _AGEB_TVIVHAB_SHORT else []
    equal = [c for c in exact if c not in short]
    parent = it["localidad"].loc[agebs.index, exact]
    check(bool((agebs[equal] == parent[equal]).all(axis=None)),
          f"AGEBs do not add up to their locality's {equal}")
    check(bool((agebs[short] <= parent[short]).all(axis=None)),
          f"AGEBs add up to more than their locality's {short}")


def load_cpv_census(
    period: str | int | None = None,
    *,
    state: int | Sequence[int] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The census counts at four levels — ``(state, municipality, locality, urban AGEB)`` —
    from the ITER and AGEB files: the port of the legacy :func:`mxcensus.load_census` onto
    the ``cpv_`` mirror and string keys (``CVE_ENT`` ⊂ ``CVE_MUN`` ⊂ ``CVE_LOC`` ⊂
    ``CVE_AGEB``), for any census with both products (2020; 2010 in this unit).

    Same steps as the legacy loader: the count columns only (``Int64``; INEGI's reserved
    cells missing); the AGEB file's empty-block fix; collective population and dwellings
    (``POBCOL`` = ``POBTOT`` − ``POBHOG``, ``TOTCOL`` = ``TVIVHAB`` − ``TOTHOG``) added and
    imputed (``aggregate.add_collective_cols``, safe for reserved totals:
    :func:`_add_collective_cols`); missing locality counts imputed from the
    municipalities and missing AGEB counts from the localities where the totals force them
    to 0 (``aggregate.impute_zeros_univariate``); the cross-file sanity checks; every level
    restricted to the AGEB file's columns. For 2020 the four frames equal
    ``load_census(state=…)`` once its integer codes are written as INEGI's padded strings.
    """
    from mxcensus.aggregate import impute_zeros_univariate

    it = load_cpv_iter(period, state=state, impute=False)
    ag = _zero_empty_blocks(load_cpv_ageb(period, state=state, impute=False))
    label = f"census {it['CVEGEO'].iloc[0][:2] if len(it) else ''}"
    it_cols, ag_cols = _counts(it), _counts(ag)
    index = {"estatal": 1, "municipal": 2, "localidad": 3, "ageb": 4}
    iters = {lvl: it.loc[it["NIVEL"] == lvl, it_cols].droplevel(_ITER_INDEX[index[lvl]:])
             for lvl in ("estatal", "municipal", "localidad")}
    agebs = {lvl: ag.loc[ag["NIVEL"] == lvl, ag_cols].droplevel(_AGEB_INDEX[index[lvl]:])
             for lvl in ("estatal", "municipal", "localidad", "ageb")}
    st, mun, loc, ageb = _add_collective_cols(iters["estatal"], iters["municipal"],
                                              iters["localidad"], agebs["ageb"])
    loc = impute_zeros_univariate(mun, loc)
    ageb = impute_zeros_univariate(loc, ageb)
    _census_checks(label, {"estatal": st, "municipal": mun, "localidad": loc},
                   {**agebs, "ageb": ageb}, _edition("ageb", period).period)
    cols = ageb.columns
    return st[cols], mun[cols], loc[cols], ageb
