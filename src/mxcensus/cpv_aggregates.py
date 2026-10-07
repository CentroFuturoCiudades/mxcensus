"""CPV family — aggregate products (national/state/municipal/locality estimates).

So far one product: the **Encuesta Intercensal 2025 estimates** (``estimaciones``), one
national file with five rows per geography — the estimate and its standard error, 90 %
confidence limits and coefficient of variation — for the nation, the 32 states, every
municipality, the 233 localities of 50 000 or more inhabitants, and each state's remainder
of smaller localities (``CVE_MUN`` 997 / ``CVE_LOC`` 9997). ITER/AGEB results of the
censuses join this module in later units (``docs/cpv/PLAN.md`` Phase 3).

The geography is split on the **string** codes (never cast to int), so the keys stay
joinable with the microdata (:mod:`mxcensus.cpv`) and the Marco Geoestadístico.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from mxcensus import _schema_groups as _sg
from mxcensus.cpv import _SKIP, _labels_for, _load_cpv_raw

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
