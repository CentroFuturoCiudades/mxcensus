"""Maintainer-only: the CPV derived columns against INEGI's published sample tabulados.

The census samples' derived columns (``derived=True``, :mod:`mxcensus.cpv_derived`) are
checked against the tabulados INEGI computed from the same samples, in every state, both
sexes and the nation, and the result is written to ``docs/cpv/TABULADOS_REPORT.md``:

- **CGPV 2000** — the «Tabulados de la muestra censal» (``ccpv/2000/tabulados/ampliado/
  C2K*.xls``, Excel 95 workbooks, read with :func:`_dict_fd.read_xls`): percentages with
  two decimals. The public sample's weights are a ratio estimator on preliminary counts
  (4a), so the shares agree within a few hundredths of a point, Chiapas worse
  (:data:`_TOLERANCE`).
- **Censo 2010** — the cuestionario ampliado tabulados (``ccpv/2010/tabulados/Ampliado/
  NN_NNA_ESTATAL.xls``, estimator «Parámetro», full precision): exact, in persons.
- **EIC 2015** — the survey's tabulados (``intercensal/2015/tabulados/NN_tema.xls``,
  estimator «Valor», percentages with six decimals): exact, in persons.
- **Censo 2020** — the cuestionario ampliado tabulados (``ccpv/2020/tabulados/ampliado/
  cpv2020_a_eum_NN_tema.xlsx``, «Valor», six decimals; 6p): exact, in persons — the
  derived columns of the base edition (= the frozen legacy ones) against INEGI.

Each check (:data:`CHECKS`) names its tabulado, how to read the published cells
(:func:`_c2k_blocks`, :func:`_c2k_sectors`, :func:`_estimates`) and the same cells from
the derived columns, as (numerator, denominator) masks over a state's frame; the nation is
the sum of the states. Shares are compared in percentage points, counts in persons (2010
and 2015 publish a total and its percentages: count = total × percentage / 100).

7d added the samples' raw items: the EIC 2015's dwelling tabulados (materials, rooms,
cooking, acquisition, water, drainage, electricity, sanitary service, waste, goods and
equipment; the occupants' tables weighted by ``NUMPERS``, :attr:`Check.weight`) and CGPV
2000's employment and migration tabulados — the international migrants of the
``migrantes`` file among them. A cell may count its records in their state of origin
instead of the frame's (:class:`ByOrigin`: the emigrants by their birth state, the
international migrants by the state they left; such checks need all 32 states).

7o added rates of the last child born alive: the fertility rates by five-year age and the
Tasa Global de Fecundidad (Censo 2010, EIC 2015, Censo 2020; by state and, nationally, by
locality size) and the infant mortality by locality size and the mother's age (national;
:func:`_rate_checks`), per 1,000 (unit «rate»; a check's ``combine`` derives the TGF from its
seven rates).

7p added Censo 2020's disability tabulados (disability, limitation and mental condition with
their causes, by sex, age and activity), its return migrants' duration and causes and the
emigrants' causes, and Censo 2010's by-state tabulados 7m left: self-identification (14
states one by one, the others together as :data:`_REST`), fields of study, sector and hours
by division, parents and kinship lines by age.

The tabulados are fetched once into ``data/dict/tabulados/{period}/`` (git-ignored); the
mirror is read from ``data/parquet`` (the full mirror: every state of each edition).

Usage::

    python scripts/check_cpv_tabulados.py                  # 2000, 2010 and 2015, all states
    python scripts/check_cpv_tabulados.py --periods 2000 --states 1 7
    python scripts/check_cpv_tabulados.py --report-only    # no report file, print only

The exit status is 1 when a cell is off by more than its tolerance.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

import _build_common as bc
import _dict_fd as fd

ROOT = Path(__file__).resolve().parents[1]
_BASE = "https://www.inegi.org.mx/contenidos/programas"
_DEFAULT_TAB_DIR = ROOT / "data" / "dict" / "tabulados"
_DEFAULT_MIRROR = ROOT / "data" / "parquet"
_DEFAULT_REPORT = ROOT / "docs" / "cpv" / "TABULADOS_REPORT.md"

# period → (directory under _BASE, the tabulados the checks read)
SOURCES = {
    "2000": ("ccpv/2000/tabulados/ampliado",
             ("C2KMI01.xls", "C2KMI03.xls", "C2KRE02.xls", "C2KSS04.xls", "C2KEC02.xls",
              "C2KEM01.xls", "C2KEM05.xls", "C2KEM07.xls", "C2KED08.xls", "C2KED10.xls",
              "C2KED11.xls", "C2KVI06.xls", "C2KVI10.xls", "C2KHO04.xls",
              "C2KEM08.xls", "C2KEM10.xls", "C2KMI04.xls",
              "C2KEM02.xls", "C2KEM03.xls", "C2KEM04.xls", "C2KEM06.xls", "C2KEM09.xls",
              "C2KEM11.xls", "C2KMI02.xls", "C2KMI05.xls", "C2KMI06.xls", "C2KMI07.xls",
              "C2KMI08.xls", "C2KMI09.xls", "C2KMI10.xls", "C2KMI11.xls", "C2KMI12.xls",
              # 7i: the dwellings
              *(f"C2KVI{n:02d}.xls" for n in (1, 2, 3, 4, 5, 7, 8, 9, 11, 12, 13, 14, 15, 16,
                                              17, 18, 19)),
              # 7k: the persons
              "C2KPO01.xls", "C2KDI01.xls", "C2KDI02.xls", "C2KDI04.xls", "C2KFE03.xls",
              "C2KFE04.xls", "C2KFE05.xls", "C2KLI02.xls",
              # 7l: the households and education
              "C2KHO01.xls", "C2KHO02.xls", "C2KHO05.xls", "C2KHO07.xls", "C2KHO08.xls",
              "C2KED02.xls", "C2KED04.xls", "C2KED06.xls", "C2KED12.xls")),
    "2010": ("ccpv/2010/tabulados/Ampliado",
             ("04_02A_ESTATAL.xls", "06_01A_ESTATAL.xls", "08_02A_ESTATAL.xls",
              "08_03A_ESTATAL.xls", "08_10A_ESTATAL.xls", "08_15A_ESTATAL.xls",
              "12_01A_ESTATAL.xls",
              # 7h: the dwellings by state
              "14_02A_ESTATAL.xls", "14_03A_ESTATAL.xls", "14_05A_ESTATAL.xls",
              "14_07A_ESTATAL.xls", "14_09A_ESTATAL.xls", "14_10A_ESTATAL.xls",
              "14_12A_ESTATAL.xls", "14_14A_ESTATAL.xls",
              # 7m: the persons and the international migrants by state
              "01_02A_ESTATAL.xls", "02_04A_ESTATAL.xls", "04_04A_ESTATAL.xls",
              "04_05A_ESTATAL.xls", "04_06A_ESTATAL.xls", "06_02A_ESTATAL.xls",
              "09_04A_ESTATAL.xls", "10_02A_ESTATAL.xls",
              # 7o: fertility rates and infant mortality
              "02_01A_ESTATAL.xls", "02_02A_ESTATAL.xls", "03_01A_ESTATAL.xls",
              # 7p: self-identification, fields of study, divisions, parents, kinship lines
              "05_01A_ESTATAL.xls", "05_02A_ESTATAL.xls", "07_02A_ESTATAL.xls",
              "07_05A_ESTATAL.xls", "08_06A_ESTATAL.xls", "08_07A_ESTATAL.xls",
              "12_02A_ESTATAL.xls", "12_04A_ESTATAL.xls")),
    "2015": ("intercensal/2015/tabulados",
             ("01_poblacion.xls", "02_fecundidad.xls", "03_mortalidad.xls",           # 7j
              "09_trabajo_no_remunerado.xls", "04_migracion.xls", "05_etnicidad.xls", "06_educacion.xls",
              "07_servicios_de_salud.xls",
              "08_caracteristicas_economicas.xls", "10_movilidad_cotidiana.xls",
              "11_situacion_conyugal.xls", "12_hogares.xls", "14_vivienda.xls")),
    "2020": ("ccpv/2020/tabulados/ampliado",
             ("cpv2020_a_eum_01_poblacion.xlsx", "cpv2020_a_eum_04_migracion.xlsx",   # 7n
              "cpv2020_a_eum_05_etnicidad.xlsx", "cpv2020_a_eum_07_educacion.xlsx",
              "cpv2020_a_eum_08_caracteristicas_economicas.xlsx",
              "cpv2020_a_eum_09_servicios_de_salud.xlsx",
              "cpv2020_a_eum_10_movilidad_cotidiana.xlsx",
              "cpv2020_a_eum_11_situacion_conyugal.xlsx", "cpv2020_a_eum_16_vivienda.xlsx",
              "cpv2020_a_eum_02_fecundidad.xlsx", "cpv2020_a_eum_03_mortalidad.xlsx",   # 7o
              "cpv2020_a_eum_06_discapacidad.xlsx")),                                  # 7p
}

# Raw SEXO codes → the tabulados' sexes (T = both).
_SEXES = {"2000": {"1": "H", "2": "M"}, "2010": {"1": "H", "3": "M"},
          "2015": {"1": "H", "3": "M"}, "2020": {"1": "H", "3": "M"}}
_SEX_LABEL = {"Total": "T", "Hombres": "H", "Mujeres": "M", "HOMBRES": "H", "MUJERES": "M"}

# Largest |Δ| accepted: points (2000 shares: the public sample's weights, a ratio estimator
# on preliminary counts, put every cell within 0.02 of the tabulados but 7 of the 1,683
# sector shares, within 0.04; Chiapas worst, STEP_6i.md, STEP_6m.md) or persons (2010/2015
# counts; 2015's six-decimal percentages leave up to ~0.9 of a person nationally).
_TOLERANCE = {"2000": {None: 0.04, 7: 0.6}, "2010": {None: 1.0}, "2015": {None: 1.0},
              "2020": {None: 1.0}}

_NATION = 0
_UNSPECIFIED = 99          # 7d: the origin not specified (CGPV 2000's «NO ESPECIFICADO» rows)
_REST = 98                 # 7p: the states a tabulado does not publish one by one, together


def fetch(periods: list[str], tab_dir: Path, retries: int = 2) -> dict[str, Path]:
    """Download the periods' tabulados into ``tab_dir/{period}/`` (once)."""
    out = {}
    for period in periods:
        rel, files = SOURCES[period]
        dest = tab_dir / period
        dest.mkdir(parents=True, exist_ok=True)
        for name in files:
            path = dest / name
            if not path.exists():
                bc.fetch_zip(f"{_BASE}/{rel}/{name}", dest, name)
                head = path.read_bytes()[:8]
                if head != fd._OLE_MAGIC and head[:4] != b"PK\x03\x04":
                    path.unlink()
                    raise RuntimeError(f"{rel}/{name}: not a workbook (INEGI's soft-404?)")
            out[f"{period}/{name}"] = path
    return out


# --------------------------------------------------------------------------------------
# published cells
# --------------------------------------------------------------------------------------

_C2K_STATE = re.compile(r"^(\d\d)\s+[^\W\d_]")  # «01 AGUASCALIENTES», not «12 - 14 AÑOS»
_C2K_NATION = "ESTADOS UNIDOS MEXICANOS"
# 7p: a Censo 2010 tabulado names the states without their code (07_02A), in code order;
# 05_01A/02A publish a few states and «the rest of the states» together
_STATE_NAMES_2010 = (
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Coahuila de Zaragoza", "Colima", "Chiapas", "Chihuahua", "Distrito Federal", "Durango",
    "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "México", "Michoacán de Ocampo", "Morelos",
    "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz de Ignacio de la Llave",
    "Yucatán", "Zacatecas")
_REST_NAME = "Resto de las entidades"


def _num(text: str | None) -> float:
    """A published cell; blank or «M.I.» (CGPV 2000: muestra insuficiente; 7k) is missing."""
    return float(text) if text not in (None, "", "M.I.") else np.nan


def _state_of(name: str) -> int | None:
    """0 for the nation, the state code for «NN Name» (7p: or Censo 2010's plain name),
    :data:`_REST` for «Resto de las entidades», else ``None`` (an age-group row such as «50 Y
    MÁS AÑOS» is not a state)."""
    name = name.strip()
    if name.upper() == _C2K_NATION:
        return _NATION
    m = _C2K_STATE.match(name)
    if m and 1 <= int(m.group(1)) <= 32 and "AÑOS" not in name.upper():
        return int(m.group(1))
    if name in _STATE_NAMES_2010:                                           # 7p
        return _STATE_NAMES_2010.index(name) + 1
    if name == _REST_NAME:
        return _REST
    return None


def _c2k_blocks(rows: list[dict], cols: str, level: str = "persons"
                ) -> dict[tuple[int, str], list[float]]:
    """A CGPV 2000 tabulado by state: ``{(state, sex): [cells of cols]}``. Person
    tabulados: the state's row (both sexes) and its first HOMBRES/MUJERES rows (age-group
    rows in between are skipped); dwelling tabulados: the state's VIVIENDAS row (7i:
    ``level="occupants"``, its OCUPANTES row)."""
    out, state = {}, None
    for r in rows:
        a = (r.get("A") or "").strip()
        if (s := _state_of(a)) is not None:
            state = s
            if level == "persons" and r.get("B"):
                out[state, "T"] = [_num(r.get(c)) for c in cols]
        elif state is None:
            continue
        elif level == "persons" and a in ("HOMBRES", "MUJERES"):
            out.setdefault((state, a[0]), [_num(r.get(c)) for c in cols])
        elif (level, a) in (("dwellings", "VIVIENDAS"), ("occupants", "OCUPANTES")):
            out[state, "T"] = [_num(r.get(c)) for c in cols]          # 7i: the occupants' rows
    return out


def _c2k_sectors(rows: list[dict], total: bool = False) -> dict[tuple[int, str], list[float]]:
    """C2KEM05 (sector of the employed), C2KEM04 (occupation): under each state row, one row
    per category (its name may wrap onto the next row, the values on the last) with the
    total, men and women in columns B, C, D. ``total``: the state row's own values first
    (C2KEM03: the rate of the 12+, then one per age group; 7d)."""
    out, state = {}, None
    for r in rows:
        a = (r.get("A") or "").strip()
        if (s := _state_of(a)) is not None:
            state = s
            if not total:
                continue
        if state is not None and a and r.get("B"):
            for sex, col in (("T", "B"), ("H", "C"), ("M", "D")):
                out.setdefault((state, sex), []).append(_num(r.get(col)))
    return out


def _c2k_sex_columns(columns: dict[str, str]):
    """CGPV 2000 tabulados with one row per state and the sexes in columns (C2KEM11:
    ``{"T": "BEH", "H": "CFI", "M": "DGJ"}``; 7d)."""
    def read(wb):
        out = {}
        for r in _sheet(wb, None):
            if (state := _state_of(r.get("A") or "")) is not None and r.get("B"):
                for sex, cols in columns.items():
                    out[state, sex] = [_num(r.get(c)) for c in cols]
        return out
    return read


def _c2k_states(cols: str):
    """CGPV 2000 tabulados with one row per state — of residence or of origin, the
    «NO ESPECIFICADO» origin as :data:`_UNSPECIFIED` — and no sex rows (C2KMI09–12; 7d)."""
    def read(wb):
        out = {}
        for r in _sheet(wb, None):
            a = (r.get("A") or "").strip()
            state = _UNSPECIFIED if a == "NO ESPECIFICADO" else _state_of(a)
            if state is not None and r.get("B"):
                out[state, "T"] = [_num(r.get(c)) for c in cols]
        return out
    return read


def _c2k_national(cols: str, first: bool = True):
    """CGPV 2000's national tabulados by sex (C2KMI07/08; 7d): the nation's block, then
    HOMBRES' and MUJERES', each one row per category (an age group) after its total row
    (kept unless ``first`` is False: C2KMI08's holds counts); the cells row by row."""
    def read(wb):
        blocks, sex = {}, None
        for r in _sheet(wb, None):
            a = (r.get("A") or "").strip()
            if a.upper() == _C2K_NATION:
                sex = "T"
            elif a in ("HOMBRES", "MUJERES"):
                sex = a[0]
            if sex and r.get("B"):
                blocks.setdefault(sex, []).append([_num(r.get(c)) for c in cols])
        return {(_NATION, sex): [v for row in rows[0 if first else 1:] for v in row]
                for sex, rows in blocks.items()}
    return read


def _c2k_items(cols: str):
    """CGPV 2000 tabulados with one row per item under each state's name row (C2KVI16, the
    goods; 7i): the items' cells in order."""
    def read(wb):
        out, state = {}, None
        for r in _sheet(wb, None):
            a = (r.get("A") or "").strip()
            if (s := _state_of(a)) is not None and not r.get("B"):
                state = s
            elif state is not None and a and r.get("B"):
                out.setdefault((state, "T"), []).extend(_num(r.get(c)) for c in cols)
        return out
    return read


def _c2k_rows(cols: str):
    """CGPV 2000 tabulados with the state's own row and then one row per category (an age
    group: C2KPO01, C2KDI01; 7k): every row's cells under its state, in order."""
    def read(wb):
        out, state = {}, None
        for r in _sheet(wb, None):
            a = (r.get("A") or "").strip()
            if (s := _state_of(a)) is not None:
                state = s
            if state is not None and a and r.get("B"):
                out.setdefault((state, "T"), []).extend(_num(r.get(c)) for c in cols)
        return out
    return read


def _c2k_age_shares(wb) -> dict[tuple[int, str], list[float]]:
    """C2KPO01: the population by age group with the sexes in columns (total, men, women)
    → each age group's share of the state's population, per sex (7k)."""
    out = {}
    for (state, _), v in _c2k_rows("BCD")(wb).items():
        rows = [v[i:i + 3] for i in range(0, len(v), 3)]
        for j, sex in enumerate(("T", "H", "M")):
            out[state, sex] = [100 * r[j] / rows[0][j] for r in rows[1:]]
    return out


def _c2k_repeated(cols: str, label: str):
    """CGPV 2000 tabulados with several blocks per state (C2KVI18: all, then each way of
    disposing of the waste; 7i): every ``label`` row (VIVIENDAS or OCUPANTES) of a state,
    in order."""
    def read(wb):
        out, state = {}, None
        for r in _sheet(wb, None):
            a = (r.get("A") or "").strip()
            if (s := _state_of(a)) is not None:
                state = s
            elif state is not None and a == label:
                out.setdefault((state, "T"), []).extend(_num(r.get(c)) for c in cols)
        return out
    return read


def _estimator_rows(rows: list[dict], estimator: str
                    ) -> tuple[dict, list[str], list[tuple[dict, list[float]]]]:
    """A tabulado with an ``Estimador`` column: its header row, the dimension columns (those
    before it, in sheet order) and each row of ``estimator`` with its values (the columns
    after it)."""
    order = lambda c: (len(c), c)  # noqa: E731 — column letters in sheet order
    header = next(r for r in rows if "Estimador" in r.values())
    est = next(c for c in header if header[c] == "Estimador")
    dims = sorted((c for c in header if order(c) < order(est)), key=order)
    data = [r for r in rows if r.get(est) == estimator]
    values = sorted({c for r in data for c in r if order(c) > order(est)}, key=order)
    return header, dims, [(r, [_num(r.get(c)) for c in values]) for r in data]


def _estimates(rows: list[dict], estimator: str) -> dict[tuple, list[float]]:
    """A 2010/2015 tabulado: the header row names the ``Estimador`` column; the columns
    before it are the row's dimensions (state first), those after it its values. Returns
    ``{(state, *other dimensions): [values]}`` for the rows of ``estimator``."""
    header, dims, data = _estimator_rows(rows, estimator)
    out = {}
    for r, values in data:
        if (state := _state_of(r.get(dims[0], ""))) is None:
            continue
        key = [state]
        for c in dims[1:]:
            text = r.get(c, "").strip()
            key.append(_SEX_LABEL.get(text, text) if header[c] == "Sexo" else text)
        out[tuple(key)] = values
    return out


def _national(estimator: str, names: tuple[tuple[str, ...], ...], sheet: str | None = None):
    """7o: a national tabulado by locality size (and the mother's age): the values of each
    row named in ``names`` (its dimension cells as published: the size, «Estados Unidos
    Mexicanos» for the nation, then the age group), in that order, as the nation's; a missing
    row raises."""
    def read(wb):
        _, dims, data = _estimator_rows(_sheet(wb, sheet), estimator)
        found = {tuple(r.get(c, "").strip() for c in dims): v for r, v in data}
        return {(_NATION, "T"): [x for n in names for x in found[n]]}
    return read


def _counts(total: float, shares: list[float], bases: list[int] | None = None) -> list[float]:
    """A total and its percentages → counts; ``bases[i]`` = the index (into the returned
    list, 0 = the total) of the count percentage ``i`` is taken of."""
    out = [total]
    for i, pct in enumerate(shares):
        out.append(pct * out[bases[i] if bases else 0] / 100)
    return out


# --------------------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Check:
    period: str
    key: str
    title: str
    source: str                       # file name in SOURCES[period]
    table: str                        # personas | viviendas | hogares (2000's household
    #                                   rows) | migrantes (7d)
    cells: tuple[str, ...]            # the compared cells' names
    published: Callable[[dict], dict]  # workbook → {(state, sex): [values]}
    ours: Callable[[pd.DataFrame], list]  # frame → [(numerator, denominator | None)]
    unit: str = "points"              # points (shares), persons (counts) or average (7i)
    sheet: str | None = None          # the workbook's sheet (default: its first)
    note: str = ""
    # state (0 = the nation; 7j: None = every state) → its largest |Δ| for this check, over
    # the edition's :data:`_TOLERANCE` (7c: differences of INEGI's own, in the note)
    tolerance: dict[int, float] | None = None
    # 7d: each record's weight (default ``FACTOR``; the occupants: × ``NUMPERS``)
    weight: Callable[[pd.DataFrame], pd.Series] | None = None
    # 7d: some cells are :class:`ByOrigin` — compared only when all 32 states are loaded
    by_origin: bool = False
    # 7o: the computed values → the published cells' (the TGF after each block's rates)
    combine: Callable[[list[float]], list[float]] | None = None


@dataclass(frozen=True)
class ByOrigin:
    """A cell part whose records count in their state of origin, not the frame's (7d: the
    emigrants by their birth state or their state in 1995, the international migrants by
    the state they left). ``origin`` holds state codes; anything outside 1–32 is the
    unspecified origin, :data:`_UNSPECIFIED`, but :data:`_REST` (7p: the states a tabulado
    publishes together)."""
    mask: pd.Series
    origin: pd.Series


@dataclass(frozen=True)
class Weighted:
    """A cell part whose records count their ``values`` (× the weight) instead of 1 (7i: the
    numerators and denominators of an average — occupants, households, rooms)."""
    mask: pd.Series
    values: pd.Series


def _sheet(wb: dict, sheet: str | None) -> list[dict]:
    return wb[sheet] if sheet else next(iter(wb.values()))


def _cat(frame: pd.DataFrame, col: str) -> pd.Series:
    return frame[col].astype(object)


def _age(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame["EDAD"], errors="coerce")


def _dummy(frame: pd.DataFrame, col: str) -> pd.Series:
    return frame[col].astype(int).eq(1)


def _code_of(frame: pd.DataFrame, col: str) -> pd.Series:
    """A derived category → its legacy code (the coarse occupation and activity)."""
    from mxcensus.cpv_derived import _legacy_map
    return _cat(frame, col).map({v: k for k, v in _legacy_map("personas", col).items()})


def _shares(den: pd.Series, *nums: pd.Series) -> list:
    return [(den & n, den) for n in nums]


# 2000 ---------------------------------------------------------------------------------

def _mi01(p):
    nac = _cat(p, "ENT_PAIS_NAC_CAT")
    return _shares(pd.Series(True, index=p.index), nac.eq("EstaEnt"),
                   nac.isin(["OtraEnt", "OtroPais"]), nac.eq("No especificado"))


def _mi03(p):
    res = _cat(p, "ENT_PAIS_RES_CAT")
    return _shares(_age(p).between(5, 130), res.eq("EstaEnt"),
                   res.isin(["OtraEnt", "OtroPais"]), res.eq("No especificado"))


def _re02(p):
    rel = _cat(p, "RELIGION_CAT")
    return _shares(_age(p).between(5, 130), *(rel.eq(c) for c in (
        "Católica", "Protestante/cristiano evangélico", "Otros credos",
        "Sin religión / Sin adscripción religiosa", "No especificado")))


def _ss04(p):
    every = pd.Series(True, index=p.index)
    afil, none = _dummy(p, "DHSERSAL_AFIL"), _dummy(p, "DHSERSAL_No afiliado")
    return [(none, every), (afil, every),
            *_shares(afil, *(_dummy(p, f"DHSERSAL_{c}") for c in ("IMSS", "ISSSTE", "P_D_M",
                                                                  "Otro"))),
            (~afil & ~none, every)]


def _ec02(p):
    sc = _cat(p, "SITUA_CONYUGAL_CAT")
    return _shares(_age(p).between(12, 130),
                   *(sc.eq(c) for c in ("soltero", "casado", "separado", "No especificado")))


def _em01(p):
    twelve, act = _age(p).between(12, 130), _cat(p, "CONACT_CAT")
    pea = twelve & act.isin(["Trabaja", "Buscó trabajo"])
    return [(pea, twelve), (pea & act.eq("Trabaja"), pea), (pea & act.eq("Buscó trabajo"), pea),
            (twelve & act.eq("No trabaja"), twelve), (twelve & act.eq("No especificado"), twelve)]


# C2KEM05's 17 rows, as SCIAN sectors (2000's ACTTRAB_C is the SCIAN subsector, STEP_6i.md)
_SECTORS_2000 = (("Agricultura, ganadería, pesca y caza", {11}), ("Minería", {21}),
                 ("Electricidad y agua", {22}), ("Construcción", {23}),
                 ("Manufacturas", {31, 32, 33}), ("Comercio", {43, 46}),
                 ("Transportes", {48, 49}), ("Información", {51}),
                 ("Financieros e inmobiliarios", {52, 53}),
                 ("Profesionales y de apoyo", {54, 55, 56}), ("Educativos", {61}),
                 ("Salud", {62}), ("Esparcimiento", {71}), ("Hoteles y restaurantes", {72}),
                 ("Otros servicios", {81}), ("Gobierno", {93}), ("No especificado", {99}))


def _employed_2000(p) -> pd.Series:
    """CGPV 2000's employed: the 12+ who worked or had a job (``CONACT_CAT``)."""
    return _age(p).between(12, 130) & _cat(p, "CONACT_CAT").eq("Trabaja")


def _em05(p):
    code = _code_of(p, "ACTIVIDADES_C_COARSE")
    return _shares(_employed_2000(p), *(code.isin(g) for _, g in _SECTORS_2000))


_SUPERIOR = ["Superior", "Posgrado"]          # INEGI's superior holds the posgrado (6w)


def _ed10(p):
    e = _cat(p, "EDUC_INEGI_DET")
    return _shares(_age(p).between(15, 130), e.eq("Sin Educación"), e.eq("Primaria_incom"),
                   e.eq("Primaria_com"),
                   e.isin(["Técnica_primaria", "Secundaria_incom", "Secundaria_com"]),
                   e.eq("Media_superior"), e.isin(_SUPERIOR), e.eq("No especificado"))


def _ed08(p):
    """The 12+ by INEGI's 2000 levels (C2KED08 lists técnica after primaria apart, as
    ``EDUC_INEGI``'s «Técnica_primaria», 6k)."""
    e = _cat(p, "EDUC_INEGI")
    return _shares(_age(p).between(12, 130), e.eq("Sin Educación"), e.eq("Primaria_incom"),
                   e.eq("Primaria_com"), e.isin(["Secundaria_incom", "Secundaria_com"]),
                   e.eq("Técnica_primaria"), e.eq("Posbásica"), e.eq("No especificado"))


def _ed11(p):
    """The 18+ without media superior, with media superior, with superior, not specified."""
    e = _cat(p, "EDUC_INEGI_DET")
    return _shares(_age(p).between(18, 130),
                   e.isin(["Sin Educación", "Primaria_incom", "Primaria_com", "Técnica_primaria",
                           "Secundaria_incom", "Secundaria_com"]),
                   e.eq("Media_superior"), e.isin(_SUPERIOR), e.eq("No especificado"))


def _em07(p):
    """The employed by hours worked (C2KEM07's bins: none and up to 40, 41–48, 49–56, more
    than 56, not specified; ``HORTRA_CAT``'s 0-5 holds who did not work)."""
    h = _cat(p, "HORTRA_CAT")
    return _shares(_employed_2000(p), h.isin(["0-5", "6-10", "11-20", "21-40"]), h.eq("41-48"),
                   h.eq("49-56"), h.isin(["57-60", "61-80", "81YMAS"]), h.eq("No especificado"))


def _em08(p):
    """The employed by their income in minimum wages (7c, ``INGTRMEN_SM``: C2KEM08's groups,
    the municipality's area of February 2000)."""
    from mxcensus.cpv_derived import _SM_2000
    sm = _cat(p, "INGTRMEN_SM")
    return _shares(_employed_2000(p), *(sm.eq(c) for c in _SM_2000.categories[:8]))


def _place_shares(col: str, universe: Callable[[pd.DataFrame], pd.Series],
                  abroad_apart: bool = False):
    """CGPV 2000's places by municipality (7c; C2KEM10, C2KMI04), as shares: the same
    entity (% of the universe) and, as % of it, the same municipality, another, not
    specified; another entity or country (``abroad_apart``: another entity, abroad); not
    specified."""
    away = (["Otra entidad"], ["Estados Unidos", "Otro país"]) if abroad_apart else (_ELSEWHERE,)

    def ours(p):
        u, place = universe(p), _cat(p, col)
        own = u & place.isin(_OWN_ENTITY)
        return [(own, u), *((u & place.eq(c), own) for c in _OWN_ENTITY),
                *((u & place.isin(a), u) for a in away), (u & place.eq("No especificado"), u)]
    return ours


def _vi06(v):
    cd = _cat(v, "CUADORM_CAT")
    return _shares(pd.Series(True, index=v.index), cd.eq("1"), cd.eq("2+"),
                   cd.eq("No especificado"))


def _vi10(v):
    dr = _cat(v, "DRENAJE_CAT")
    return _shares(pd.Series(True, index=v.index), dr.eq("Sí"), dr.eq("No"),
                   dr.eq("No especificado"))


def _head_sex(col: str):
    """The households (``JEFE_SEXO``: CGPV 2000's dwelling rows are its households, 6s) or
    the population in households (``HOGJEF_SEXO``, 6t) by the head's sex, % of all."""
    def ours(frame):
        head = _cat(frame, col)
        return _shares(pd.Series(True, index=frame.index), head.eq("Hombre"), head.eq("Mujer"))
    return ours


# 7d: employment ------------------------------------------------------------------------

def _twelve(p) -> pd.Series:
    return _age(p).between(12, 130)


def _pea_2000(p) -> pd.Series:
    return _twelve(p) & _cat(p, "CONACT_CAT").isin(["Trabaja", "Buscó trabajo"])


def _em02(p):
    """The inactive 12+ (``CONACT`` 40–80) by kind: students, home, retired, unable to work,
    other."""
    conact = pd.to_numeric(p["CONACT"])
    inactive = _twelve(p) & conact.between(40, 80)
    return _shares(inactive, *(conact.eq(c) for c in (40, 50, 60, 70, 80)))


_AGES_EM03 = ((12, 14), (15, 19), (20, 24), (25, 29), (30, 34), (35, 39), (40, 44), (45, 49),
              (50, 54), (55, 59), (60, 64), (65, 130))


def _em03(p):
    """Participation rates: the PEA as % of every 12+ (the unspecified activity included),
    then by five-year age group."""
    pea, age = _pea_2000(p), _age(p)
    return [(pea, _twelve(p)), *((pea & age.between(a, b), age.between(a, b))
                                 for a, b in _AGES_EM03)]


# C2KEM04's 19 rows: the CMO's principal groups, the first two digits of OCUACTIV_C
_CMO_GROUPS = (("profesionistas", "11"), ("técnicos", "12"), ("education workers", "13"),
               ("art workers", "14"), ("officials and managers", "21"),
               ("agricultural workers", "41"), ("industrial inspectors and supervisors", "51"),
               ("artisans and labourers", "52"), ("fixed-machinery operators", "53"),
               ("helpers and labourers", "54"), ("transport operators", "55"),
               ("administrative heads and supervisors", "61"), ("office workers", "62"),
               ("traders and shop assistants", "71"), ("street vendors", "72"),
               ("personal services", "81"), ("domestic workers", "82"),
               ("protection and security", "83"), ("not specified", "99"))


def _em04(p):
    group = p["OCUACTIV_C"].str[:2]
    return _shares(_employed_2000(p), *(group.eq(g) for _, g in _CMO_GROUPS))


def _em06(p):
    """The employed by position at work (``SITTRA``: employee, day labourer, employer,
    own account, unpaid family worker, not specified)."""
    position = pd.to_numeric(p["SITTRA"])
    return _shares(_employed_2000(p), *(position.eq(c) for c in (1, 2, 3, 4, 5, 9)))


# C2KEM09's benefits: each item's «yes» code; «no benefits» = every item answered «no»
_BENEFITS = (("VACACION", "1", "2"), ("AGUINALD", "3", "4"), ("REPUTIL", "5", "6"),
             ("SERVMED", "7", "8"), ("SARAFORE", "1", "2"))


def _em09(p):
    """The wage earners (``SITTRA`` 1, 2: employees, day labourers) with each benefit, and
    without any."""
    earners = _employed_2000(p) & pd.to_numeric(p["SITTRA"]).isin([1, 2])
    none = np.logical_and.reduce([p[item].eq(no) for item, _, no in _BENEFITS])
    return _shares(earners, *(p[item].eq(yes) for item, yes, _ in _BENEFITS), none)


def _em11(p):
    """The open unemployment rate, the part-time and unemployment rate (the employed who
    worked 1–34 hours in the reference week — not who had a job but did not work, ``CONACT``
    20, whose usual hours the sample records —, plus the unemployed) and the rate of income
    below the minimum wage and unemployment (``INGTRMEN_SM`` «Menos de 1 s.m.», those
    without income left out), all % of the PEA."""
    from mxcensus.cpv_derived import _SM_2000
    pea, employed = _pea_2000(p), _employed_2000(p)
    unemployed = _twelve(p) & _cat(p, "CONACT_CAT").eq("Buscó trabajo")
    hours = pd.to_numeric(p["HORTRA"], errors="coerce")
    part_time = hours.between(1, 34) & pd.to_numeric(p["CONACT"]).ne(20)
    below = _cat(p, "INGTRMEN_SM").eq(_SM_2000.categories[1])
    return [(unemployed, pea), (employed & part_time | unemployed, pea),
            (employed & below | unemployed, pea)]


# 7d: migration -------------------------------------------------------------------------

def _flows(place: str, universe: Callable[[pd.DataFrame], pd.Series]):
    """C2KMI02/05: the immigrants (living here, from another state) and the emigrants (born
    here or living here in 1995, now in another state: :class:`ByOrigin`), both % of the
    residents of ``universe`` whose ``place`` is a specified state (the footnote: born or
    living abroad and not specified left out)."""
    def ours(p):
        where = pd.to_numeric(p[place], errors="coerce")
        base = universe(p) & where.between(1, 32)
        moved = base & where.ne(pd.to_numeric(p["ENT"]))
        return [(moved, base), (ByOrigin(moved, where), base)]
    return ours


def _mi06(p):
    """The migrants 5+ (in 1995 in another state or country) by cause (``CAUEMI``: work,
    family, job transfer, study, marriage, health or violence, other, not specified)."""
    cause = pd.to_numeric(p["CAUEMI"])
    migrants = _five(p) & _cat(p, "ENT_PAIS_RES_CAT").isin(["OtraEnt", "OtroPais"])
    return _shares(migrants, *(cause.isin(c) for c in ([1], [2], [3], [4], [5], [6, 7], [8],
                                                       [9])))


# The international migrants' movement (MPAIRES_C, the country of residence: 700 Mexico =
# returned, 999 not specified, else abroad), age at emigrating (MEDAD; 999 not specified)
_MOVEMENTS = ("emigrant", "return migrant", "not specified")
_AGES_MI07 = ((0, 4), (5, 9), (10, 14), (15, 19), (20, 24), (25, 29), (30, 34), (35, 39),
              (40, 44), (45, 49), (50, 130), (999, 999))
_AGES_MI11 = ((0, 14), (15, 24), (25, 34), (35, 49), (50, 130), (999, 999))


def _movement(m) -> list[pd.Series]:
    country = pd.to_numeric(m["MPAIRES_C"])
    return [~country.isin([700, 999]), country.eq(700), country.eq(999)]


def _ages(m, groups) -> list[pd.Series]:
    age = pd.to_numeric(m["MEDAD"])
    return [age.between(a, b) for a, b in groups]


def _mi07(m):
    """The international migrants by movement: all, then each age group at emigrating."""
    every = pd.Series(True, index=m.index)
    return [(g & mv, g) for g in (every, *_ages(m, _AGES_MI07)) for mv in _movement(m)]


def _mi08(m):
    """Each age group at emigrating, % of all the international migrants and of each
    movement."""
    every = pd.Series(True, index=m.index)
    return [(g & u, u) for g in _ages(m, _AGES_MI07) for u in (every, *_movement(m))]


def _mi09(m):
    """The international migrants by movement, by the dwelling's state."""
    return _shares(pd.Series(True, index=m.index), *_movement(m))


def _by_origin(cells: Callable[[pd.DataFrame], list]):
    """C2KMI10–12: shares by the state the migrants left (``MLUGORI_C``; 999 = not
    specified)."""
    def ours(m):
        origin = m["MLUGORI_C"]
        every = ByOrigin(pd.Series(True, index=m.index), origin)
        return [(ByOrigin(c, origin), every) for c in cells(m)]
    return ours


def _destination(m) -> list[pd.Series]:
    """C2KMI12: the United States (221), the rest of the world, not specified (999)."""
    country = pd.to_numeric(m["MPDESOTR_C"])
    return [country.eq(221), ~country.isin([221, 999]), country.eq(999)]


def _c2k(cols: str, combine: Callable[[list], list] = lambda v: v, level: str = "persons"):
    def read(wb):
        return {k: combine(v) for k, v in _c2k_blocks(_sheet(wb, None), cols, level).items()}
    return read


# 2010 / 2015 --------------------------------------------------------------------------

def _counts_of(*masks: pd.Series) -> list:
    return [(m, None) for m in masks]


def _birthplace_2015(p):
    """INEGI's birthplace (``ENT_PAIS_NAC_INEGI``, 6y: the entity not specified, 997, is
    «No especificado»; the legacy ``ENT_PAIS_NAC_CAT`` counts it ``OtraEnt``)."""
    nac = _cat(p, "ENT_PAIS_NAC_INEGI")
    return _counts_of(pd.Series(True, index=p.index), nac.eq("EstaEnt"), nac.eq("OtraEnt"),
                      nac.eq("OtroPais"), nac.eq("No especificado"))


# 7b: the places by municipality (LUGAR_RES_5A, LUGAR_ASI, LUGAR_TRAB): INEGI's 2010–2020
# tabulados publish the universe; the same entity and, as % of it, the same municipality,
# another, not specified; another entity or country; not specified.
_OWN_ENTITY = ("Mismo municipio", "Otro municipio", "Municipio no especificado")
_ELSEWHERE = ["Otra entidad", "Estados Unidos", "Otro país"]
_PLACE_CELLS = ("same entity", "same municipality", "another municipality",
                "municipality not specified", "another entity or country", "not specified")


def _place(col: str, universe: Callable[[pd.DataFrame], pd.Series]):
    def ours(p):
        u, place = universe(p), _cat(p, col)
        return _counts_of(u, u & place.isin(_OWN_ENTITY), *(u & place.eq(c) for c in _OWN_ENTITY),
                          u & place.isin(_ELSEWHERE), u & place.eq("No especificado"))
    return ours


def _place_published(v: list) -> list:
    return _counts(v[0], v[1:7], [0, 1, 1, 1, 0, 0])


def _five(p) -> pd.Series:
    return _age(p).between(5, 130)


def _students(p) -> pd.Series:
    """The students aged 3+ (the place of school is asked of every student: 7b)."""
    return _age(p).between(3, 130) & _cat(p, "LUGAR_ASI").ne("Blanco por pase")


def _activity_2015(p):
    twelve, act = _age(p).between(12, 130), _cat(p, "CONACT_CAT")
    pea = twelve & act.isin(["Trabaja", "Buscó trabajo"])
    return _counts_of(twelve, pea, pea & act.eq("Trabaja"), pea & act.eq("Buscó trabajo"),
                      twelve & act.eq("No trabaja"), twelve & act.eq("No especificado"))


_DIVISIONS = ("Funcionarios, directores y jefes", "Profesionistas y técnicos",
              "Trabajadores auxiliares en actividades administrativas",
              "Comerciantes, empleados en ventas y agentes de ventas",
              "Trabajadores en servicios personales y vigilancia",
              "Trabajadores en actividades agrícolas, ganaderas, forestales, pesca y caza",
              "Trabajadores artesanales",
              "Operadores de maquinaria industrial, ensambladores, choferes y conductores "
              "de transporte",
              "Trabajadores en actividades elementales y de apoyo", "No especificado")
_SECTOR_GROUPS = (
    ("Agricultura, ganadería, aprovechamiento forestal, pesca y caza", {11}),
    ("Minería, industrias manufactureras, electricidad y agua", {21, 22, 31, 32, 33}),
    ("Construcción", {23}), ("Comercio", {43, 46}),
    ("Servicios de transporte, comunicación, profesionales, financieros, sociales, gobierno "
     "y otros", {48, 49, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 93}),
    ("No especificado", {99}))


def _employed(p) -> pd.Series:
    return _cat(p, "OCUPACION_C_COARSE").ne("Blanco por pase") & _age(p).between(12, 130)


# 7c: the income in minimum wages (INGTRMEN_SM), in the 2010–2020 tabulados' order
_SM_CELLS = ("up to 1", "above 1 to 2", "above 2 to 3", "above 3 to 5", "above 5 to 10",
             "above 10", "no income", "not specified")


def _income_sm(p):
    from mxcensus.cpv_derived import _SM
    groups = [*_SM.categories[1:7], _SM.categories[0], _SM.categories[7]]
    e, sm = _employed(p), _cat(p, "INGTRMEN_SM")
    return _counts_of(e, *(e & sm.eq(c) for c in groups))


def _income_sm_published(estimator: str, sheet: str | None = None):
    return _wide(estimator, lambda v: _counts(v[0], v[1:]), sheet=sheet, dims=_total_row)


def _occupation(p):
    occ = _code_of(p, "OCUPACION_C_COARSE")
    division = (occ // 10).where(occ.ne(99), 10)
    return _counts_of(*(_employed(p) & division.eq(i) for i in range(1, 11)))


def _sector(p):
    code = _code_of(p, "ACTIVIDADES_C_COARSE")
    return _counts_of(*(_employed(p) & code.isin(g) for _, g in _SECTOR_GROUPS))


def _financing_2015(v):
    from mxcensus.cpv_derived import _BLANK, _financiamiento_2015
    labels = [lab for code, lab in _financiamiento_2015().items() if code != _BLANK]
    dummies = [_dummy(v, f"FINANCIAMIENTO_{lab}") for lab in labels]
    return _counts_of(np.logical_or.reduce(dummies), *dummies)


def _words(name: str) -> frozenset[str]:
    """A category name as a set of words (2010 «forestales, caza y pesca» = 2015's
    «forestales, pesca y caza»), footnote digits dropped."""
    return frozenset(re.findall(r"[^\W\d_]+", name.lower()))


def _any(frame: pd.DataFrame, *cols: str) -> pd.Series:
    return np.logical_or.reduce([_dummy(frame, c) for c in cols])


def _hours(p):
    """The employed by hours worked: the tabulado's «hasta 32», «33 a 40» and «no trabajó»
    (0 hours) together are ``HORTRA_CAT`` up to 40."""
    h, e = _cat(p, "HORTRA_CAT"), _employed(p)
    return _counts_of(e, e & h.isin(["0-5", "6-10", "11-20", "21-40"]), e & h.eq("41-48"),
                      e & h.eq("49-56"), e & h.isin(["57-60", "61-80", "81YMAS"]),
                      e & h.eq("No especificado"))


def _affiliation(p):
    """Persons by affiliation and institution (one person counts once per institution; the
    tabulado's ISSSTE includes the state ISSSTE)."""
    afil, none = _dummy(p, "DHSERSAL_AFIL"), _dummy(p, "DHSERSAL_No afiliado")
    return _counts_of(pd.Series(True, index=p.index), afil, _dummy(p, "DHSERSAL_IMSS"),
                      _any(p, "DHSERSAL_ISSSTE", "DHSERSAL_ISSSTE_E"),
                      *(_dummy(p, f"DHSERSAL_{c}") for c in (
                          "P_D_M", "SALUD_PUBLICA", "IMSS_BIENESTAR", "Privado", "Otro")),
                      none, ~afil & ~none)


_AFFILIATION_ROWS = (("Total", "Total"), ("Afiliada", "Total"), ("Afiliada", "IMSS"),
                     ("Afiliada", "ISSSTE"), ("Afiliada", "Pemex, Defensa o Marina"),
                     ("Afiliada", "Instituto de Salud para el Bienestar"),
                     ("Afiliada", "IMSS BIENESTAR"), ("Afiliada", "Institución privada"),
                     ("Afiliada", "Otra institución"), ("No afiliada", "Total"),
                     ("No especificado", "Total"))


def _affiliation_published(wb):
    """Servicios de salud 04: one row per (state, affiliation, institution); its count."""
    rows = {(k[0], k[1], k[2].rstrip("0123456789")): v[0]
            for k, v in _estimates(_sheet(wb, "04"), "Valor").items()}
    return {(state, "T"): [rows[state, a, i] for a, i in _AFFILIATION_ROWS]
            for state in {k[0] for k in rows}}


# Commute modes (several per person: each dummy set is «any of the person's three answers»).
_MODES = (("walking", ["Caminando"]), ("bicycle", ["Bicicleta"]),
          ("metro, trolleybus, metrobús", ["Metro, tren ligero, tren suburbano", "Trolebús",
                                            "Metrobús (autobús en carril confinado)"]),
          ("bus", ["Camión, autobús, combi, colectivo"]))
_MODES_END = (("taxi", ["Taxi (sitio, calle, otro)", "Taxi (App Internet)"]),
              ("private vehicle", ["Motocicleta o motoneta", "Automóvil o camioneta"]),
              ("other", ["Otro"]), ("not specified", ["No especificado"]))
_MODES_ESC = (*_MODES, ("school bus", ["Transporte escolar"]), *_MODES_END)
_MODES_TRAB = (*_MODES, ("staff transport", ["Transporte de personal"]), *_MODES_END)


def _commute(prefix: str, modes: tuple, youngest: int):
    """Who travels (a first mode given; the tabulados leave out unspecified ages: students
    3+, the employed 12+) and each mode."""
    def ours(p):
        travels = p[f"{prefix}1"].notna() & _age(p).between(youngest, 130)
        return _counts_of(travels, *(travels & _any(p, *(f"{prefix}_{m}" for m in labels))
                                     for _, labels in modes))
    return ours


def _partner(p):
    """The married or in union aged 12+, by whether the partner lives in the dwelling."""
    union = _age(p).between(12, 130) & _cat(p, "SITUA_CONYUGAL_CAT").eq("casado")
    partner = _cat(p, "IDENT_PAREJA_CAT")
    return _counts_of(union, *(union & partner.eq(c) for c in ("Sí", "No", "No especificado")))


_FINANCING_2020 = ("INFONAVIT", "FOVISSSTE", "PEMEX", "FONHAPO", "Banco", "Otra institución",
                   "Le prestó un familiar, amiga(o) o prestamista", "Usó sus propios recursos",
                   "No especificado")


def _financing_2020(v):
    """The owned dwellings bought or built (a financing answer) by source (up to three)."""
    dummies = [_dummy(v, f"FINANCIAMIENTO_{f}") for f in _FINANCING_2020]
    return _counts_of(np.logical_or.reduce(dummies), *dummies)


# EIC 2015 (6q) ----------------------------------------------------------------------

def _affiliation_2015(p):
    """Persons by affiliation and institution (2015: ISSSTE federal or state together, the
    Seguro Popular, no IMSS-BIENESTAR)."""
    afil, none = _dummy(p, "DHSERSAL_AFIL"), _dummy(p, "DHSERSAL_No afiliado")
    return _counts_of(pd.Series(True, index=p.index), afil, _dummy(p, "DHSERSAL_IMSS"),
                      _any(p, "DHSERSAL_ISSSTE", "DHSERSAL_ISSSTE_E"),
                      *(_dummy(p, f"DHSERSAL_{c}") for c in (
                          "P_D_M", "SALUD_PUBLICA", "Privado", "Otro")),
                      none, ~afil & ~none)


# The EIC 2015's seven commute modes (its own dummies, cpv_derived._traslado_2015), in the
# tabulados' order; the fourth is the school bus or the staff transport.
_MODES_2015 = ("Camión, taxi, combi o colectivo", "Metro, metrobús o tren ligero",
               "Vehículo particular (automóvil, camioneta o motocicleta)", None, "Bicicleta",
               "Caminando", "Otro", "No especificado")


def _commute_2015(prefix: str, fourth: str, youngest: int):
    def ours(p):
        travels = p[f"{prefix}1"].notna() & _age(p).between(youngest, 130)
        return _counts_of(travels, *(travels & _dummy(p, f"{prefix}_{m or fourth}")
                                     for m in _MODES_2015))
    return ours


def _marital(p):
    twelve, sc = _age(p).between(12, 130), _cat(p, "SITUA_CONYUGAL_CAT")
    return _counts_of(twelve, *(twelve & sc.eq(c)
                                for c in ("soltero", "casado", "separado", "No especificado")))


def _educ_2015(p):
    """The 15+ by the legacy ``EDUC`` (the EIC 2015 tabulados, like it, count técnica after
    primaria in primaria; 6k), its «Posbásica» split by ``EDUC_INEGI_DET`` (6w)."""
    f15, e, det = _age(p).between(15, 130), _cat(p, "EDUC"), _cat(p, "EDUC_INEGI_DET")
    return _counts_of(f15, *(f15 & e.isin(g) for g in (
        ["Sin Educación"], ["Primaria_incom", "Primaria_com"], ["Secundaria_incom"],
        ["Secundaria_com"])), f15 & det.eq("Media_superior"), f15 & det.isin(_SUPERIOR),
        f15 & e.eq("No especificado"))


def _educ_2015_published(v: list) -> list:
    """06-11: the 15+ (E); sin escolaridad (F); básica (G) and, as % of it, preescolar,
    primaria, secundaria (H–J); as % of secundaria, incompleta, completa, NE (K–M); media
    superior, superior, NE (N–P). Preschool joins «sin escolaridad» and a secundaria of
    unspecified grade the incomplete one, as in ``EDUC``."""
    c = _counts(v[0], v[1:12], [0, 0, 2, 2, 2, 5, 5, 5, 0, 0, 0])
    return [c[0], c[1] + c[3], c[4], c[6] + c[8], c[7], c[9], c[10], c[11]]


# Censo 2010 national (6q: the tabulados by locality size; their national row) --------

def _limitation(p):
    lim = _cat(p, "LIM_ACTIVIDAD")
    return _counts_of(pd.Series(True, index=p.index),
                      *(lim.eq(c) for c in ("Sí", "No", "No especificado")))


def _parents(p):
    """The population by whether the father, the mother, both or neither live in the dwelling;
    an unspecified answer for either is «No especificado»."""
    m, f = _cat(p, "MADRE_EN_VIVIENDA"), _cat(p, "PADRE_EN_VIVIENDA")
    return _counts_of(pd.Series(True, index=p.index), m.eq("Sí") & f.eq("Sí"),
                      f.eq("Sí") & m.eq("No"), m.eq("Sí") & f.eq("No"), m.eq("No") & f.eq("No"),
                      m.eq("No especificado") | f.eq("No especificado"))


def _population_by_head(p):
    head = _cat(p, "HOGJEF_SEXO")
    return _counts_of(pd.Series(True, index=p.index), head.eq("Hombre"), head.eq("Mujer"))


def _population_by_head_published(wb):
    """EIC 2015 12-05: rows (state, the head's sex — Total/Hombres/Mujeres —, «Hogares» or
    «Población en hogares»); the population's total column, both sexes of the persons."""
    out = {}
    for (state, head, what), values in _estimates(_sheet(wb, "05"), "Valor").items():
        if what == "Población en hogares":
            out.setdefault((state, "T"), {})[head] = values[0]
    return {k: [v["Total"], v["Hombres"], v["Mujeres"]] for k, v in out.items()}


def _indigenous_children(p):
    """The population aged 0–2 in indigenous households (``HOG_IND``: the EIC 2015's head
    or partner speaks an indigenous language; 6w)."""
    young = _age(p).between(0, 2)
    return _counts_of(young & _cat(p, "HOG_IND").eq("Sí"))


def _indigenous_children_published(wb):
    """EIC 2015 05-04: one row per (state, the head's or partner's language), the estimators
    in columns (C = the value); the «Total» row is the count."""
    return {(state, "T"): [_num(r.get("C"))] for r in _sheet(wb, "04")
            if r.get("B") == "Total" and (state := _state_of(r.get("A", ""))) is not None}


def _superior(p):
    """The 18+ with educación superior, the posgrado included (``EDUC_INEGI_DET``; 6w)."""
    return _counts_of(_age(p).between(18, 130) & _cat(p, "EDUC_INEGI_DET").isin(_SUPERIOR))


# EIC 2015 households and dwellings (7b) ------------------------------------------------

def _households_by_class(v):
    """The households (one per dwelling, every class) by ``CLASE_HOG`` and, within each
    class, by the raw ``TIPOHOG``: familiar = nuclear, ampliado, compuesto, not specified
    (1–4); no familiar = unipersonal, corresidentes (5, 6); not specified (9)."""
    kind, cls = pd.to_numeric(v["TIPOHOG"]), _cat(v, "CLASE_HOG")
    return _counts_of(pd.Series(True, index=v.index), cls.eq("Familiar"),
                      *(kind.eq(k) for k in (1, 2, 3, 4)), cls.eq("No familiar"),
                      kind.eq(5), kind.eq(6), cls.eq("No especificado"))


def _population_by_class(p):
    """The population in households by its household's ``CLASE_HOG`` (6z: the persons read
    their household's ``TIPOHOG`` from the dwelling file)."""
    cls = _cat(p, "CLASE_HOG")
    return _counts_of(pd.Series(True, index=p.index),
                      *(cls.eq(c) for c in ("Familiar", "No familiar", "No especificado")))


def _household_class_published(what: str, pick: Callable[[list], list] = lambda c: c):
    """EIC 2015 12-05: rows (state, the head's sex, «Hogares»/«Población en hogares»); the
    head's sex «Total»: the total, familiar and its four types (% of familiar), no familiar
    and its two (% of no familiar), not specified."""
    def read(wb):
        return {(state, "T"): pick(_counts(v[0], v[1:10], [0, 1, 1, 1, 1, 0, 6, 6, 0]))
                for (state, head, kind), v in _estimates(_sheet(wb, "05"), "Valor").items()
                if head == "Total" and kind == what}
    return read


def _dwellings_2015(v) -> pd.Series:
    """The EIC 2015's «viviendas particulares habitadas» of its dwelling tabulados: every
    class but the locales no construidos para habitación, móviles and refugios (7–9)."""
    return ~pd.to_numeric(v["CLAVIVP"]).isin([7, 8, 9])


def _tenure_2015(v):
    """The dwellings by tenure (``TENENCIA``: own, rented, lent, other, not specified)."""
    vph, tenure = _dwellings_2015(v), pd.to_numeric(v["TENENCIA"])
    return _counts_of(vph, *(vph & tenure.eq(c) for c in (1, 2, 3, 4, 9)))


def _deeds_2015(v):
    """The owned dwellings (``TENENCIA`` 1) by deed (``ESCRITURAS_VIV``: in the name of a
    resident, of a non-resident, none, not known, not specified)."""
    own = _dwellings_2015(v) & pd.to_numeric(v["TENENCIA"]).eq(1)
    deed = pd.to_numeric(v["ESCRITURAS_VIV"])
    return _counts_of(own, *(own & deed.eq(c) for c in (1, 2, 3, 8, 9)))


# EIC 2015 dwellings: the raw items (7d) ------------------------------------------------

def _code(v: pd.DataFrame, col: str) -> pd.Series:
    """A raw 2015 item as numbers (the 2015 CSVs drop leading zeros)."""
    return pd.to_numeric(v[col], errors="coerce")


def _is(x: pd.Series, codes) -> pd.Series:
    return x.isin(codes if isinstance(codes, (tuple, list)) else [codes])


def _occupants(v: pd.DataFrame) -> pd.Series:
    """The occupants' weight: the dwelling's ``FACTOR`` × its ``NUMPERS``."""
    return pd.to_numeric(v["FACTOR"]) * pd.to_numeric(v["NUMPERS"])


def _item(col: str, codes: tuple, universe: Callable[[pd.DataFrame], pd.Series] | None = None):
    """The dwellings of ``universe`` (default :func:`_dwellings_2015`), then each code (or
    tuple of codes) of ``col``."""
    def ours(v):
        u = (universe or _dwellings_2015)(v)
        x = _code(v, col)
        return _counts_of(u, *(u & _is(x, c) for c in codes))
    return ours


def _stacked_cells(*parts: Callable[[pd.DataFrame], list]):
    """One check over several categories (a row dimension of the tabulado): each part's
    cells, in order."""
    def ours(v):
        return [cell for part in parts for cell in part(v)]
    return ours


def _tokens(name: str) -> frozenset[str]:
    """A category name as a set of words and numbers («2 ocupantes»); a footnote's digits,
    glued to a word («Otro tipo de vivienda1»), dropped."""
    return frozenset(re.findall(r"(?<![^\W\d_])\d+|[^\W\d_]+", name.lower()))


def _stacked(names: tuple[str, ...], pick: Callable[[list], list], sheet: str | None,
             estimator: str = "Valor"):
    """EIC 2015 tabulados with one row per (state, category) — the class, the number of
    occupants or rooms, the fuel, the item: per state, ``pick`` of each category's values in
    the order of ``names`` (matched as :func:`_tokens`). 7h: Censo 2010's («Parámetro») and
    2020's too."""
    def read(wb):
        out = {}
        for (state, category), values in _estimates(_sheet(wb, sheet), estimator).items():
            out.setdefault(state, {})[_tokens(category)] = pick(values)
        return {(state, "T"): [x for n in names for x in cells[_tokens(n)]]
                for state, cells in out.items()}
    return read


def _all_dwellings(v: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=v.index)


# 14-02: the classes (every dwelling: 06–09 are «otro tipo»)
_CLASSES_2015 = (("Total", tuple(range(1, 10)) + (99,)), ("Casa única en el terreno", 1),
                 ("Casa que comparte terreno con otra(s)", 2),
                 ("Casa dúplex, triple o cuádruple", 3), ("Departamento en edificio", 4),
                 ("Vivienda en vecindad o cuartería", 5), ("Otro tipo de vivienda", (6, 7, 8, 9)),
                 ("No especificado", 99))
_OCCUPANTS_2015 = (("Total", None), ("1 ocupante", 1), ("2 ocupantes", 2), ("3 ocupantes", 3),
                   ("4 ocupantes", 4), ("5 ocupantes", 5), ("6 y más ocupantes", "6+"))
_ROOMS_2015 = (("Total", None), ("1 cuarto", 1), ("2 cuartos", 2), ("3 cuartos", 3),
               ("4 cuartos", 4), ("5 cuartos", 5), ("6 cuartos y más", "6+"),
               ("No especificado", 99))


def _number(x: pd.Series, which) -> pd.Series:
    """A count's category: ``None`` = any, ``"N+"`` = N or more (not the 99 «not
    specified»), else the number."""
    if which is None:
        return pd.Series(True, index=x.index)
    if isinstance(which, str):
        return x.between(int(which[:-1]), 98)
    return x.eq(which)


def _class_2015(v):
    cls = _code(v, "CLAVIVP")
    return _counts_of(*(_is(cls, codes) for _, codes in _CLASSES_2015))


def _by_count(item: str, groups: tuple, rows: str, row_groups: tuple):
    """Dwellings by a count (``TOTCUART`` rooms, ``CUADORM`` bedrooms) within each row of
    another (``NUMPERS`` occupants): per row, the dwellings, then each group (a number,
    ``"N+"`` or 99)."""
    def ours(v):
        u, x, r = _dwellings_2015(v), _code(v, item), _code(v, rows)
        return [cell for _, which in row_groups for cell in _counts_of(
            u & _number(r, which), *(u & _number(r, which) & _number(x, g) for g in groups))]
    return ours


def _cooks_2015(v) -> pd.Series:
    """INEGI's dwellings whose occupants cook: a place (``LUGAR_COCINA`` 1–3) or a fuel
    (``COMBUSTIBLE`` 1–4) given — not «no cocinan» (4, 5), nor a fuel not specified without
    a place (150,929 dwellings nationally)."""
    return _dwellings_2015(v) & (_code(v, "LUGAR_COCINA").between(1, 3)
                                 | _code(v, "COMBUSTIBLE").between(1, 4))


_FUELS_2015 = (("Total", (1, 2, 3, 4, 9)), ("Leña o carbón", 1), ("Gas", 2),
               ("Otro combustible", (3, 4)), ("No especificado", 9))


def _cooking_2015(v):
    """14-11: by fuel (electricity is «otro combustible»), where they cook: the kitchen
    (``COCINA`` 1), elsewhere (3: ``LUGAR_COCINA`` 1, 2, 3, 9), not specified (9)."""
    cooks, kitchen = _cooks_2015(v), _code(v, "COCINA")
    place, fuel = _code(v, "LUGAR_COCINA"), _code(v, "COMBUSTIBLE")
    out = []
    for _, codes in _FUELS_2015:
        u = cooks & _is(fuel, codes)
        elsewhere = u & kitchen.eq(3)
        out += _counts_of(u, u & kitchen.eq(1), elsewhere,
                          *(elsewhere & place.eq(c) for c in (1, 2, 3, 9)), u & kitchen.eq(9))
    return out


def _acquisition_2015(v):
    """14-17: the owned dwellings (``TENENCIA`` 1) by rooms, then by ``FORMA_ADQUI``."""
    own = _dwellings_2015(v) & _code(v, "TENENCIA").eq(1)
    rooms, how = _code(v, "TOTCUART"), _code(v, "FORMA_ADQUI")
    return [cell for _, which in _ROOMS_2015 for cell in _counts_of(
        own & _number(rooms, which),
        *(own & _number(rooms, which) & how.eq(c) for c in (1, 2, 3, 4, 5, 6, 9)))]


def _water_2015(v):
    """14-20/34: piped water (``AGUA_ENTUBADA`` 1 inside, 2 in the yard), carried
    (3: ``ABA_AGUA_NO_ENTU`` community tap 2, another dwelling 3, a pipa 5, a well 1, a
    river 4, rain 6, not specified 9), not specified (9)."""
    u, piped, carried = _dwellings_2015(v), _code(v, "AGUA_ENTUBADA"), _code(v, "ABA_AGUA_NO_ENTU")
    by_hand = u & piped.eq(3)
    return _counts_of(u, u & piped.isin([1, 2]), u & piped.eq(1), u & piped.eq(2), by_hand,
                      *(by_hand & carried.eq(c) for c in (2, 3, 5, 1, 4, 6, 9)), u & piped.eq(9))


_PIPED_2015 = (("Total", (1, 2)), ("Dentro de la vivienda", 1),
               ("Fuera de la vivienda, pero dentro del terreno", 2))


def _water_source_2015(v):
    """14-22/36: the dwellings with piped water, by where (all, inside, in the yard), then
    by its source (``ABA_AGUA_ENTU``: public service, community well, private well, pipa,
    another dwelling, elsewhere, not specified)."""
    u, piped, source = _dwellings_2015(v), _code(v, "AGUA_ENTUBADA"), _code(v, "ABA_AGUA_ENTU")
    return [cell for _, codes in _PIPED_2015 for cell in _counts_of(
        u & _is(piped, codes), *(u & _is(piped, codes) & source.eq(c)
                                 for c in (1, 2, 3, 4, 5, 6, 9)))]


def _sanitary_2015(v):
    """14-28: a toilet (``SERSAN`` 1) or a latrine (2) by how it takes water (``CONAGUA``:
    flush 1, a bucket 2, none 3, not specified 9), neither (3), not specified (9)."""
    u, kind, water = _dwellings_2015(v), _code(v, "SERSAN"), _code(v, "CONAGUA")
    toilet, latrine = u & kind.eq(1), u & kind.eq(2)
    return _counts_of(u, u & kind.isin([1, 2]), toilet, *(toilet & water.eq(c) for c in (1, 2, 3, 9)),
                      latrine, *(latrine & water.eq(c) for c in (2, 3, 9)), u & kind.eq(3),
                      u & kind.eq(9))


# 14-31/32/33: one row per item (its «yes» and «no» codes; 9 = not specified)
_REUSE_2015 = (("Reutilizan residuos para alimentar animales", "SEPARA_ALI", 1, 2),
               ("Reutilizan residuos para las plantas", "SEPARA_ABO", 3, 4),
               ("Reutilizan residuos para vender o regalar", "SEPARA_VEN", 5, 6))
_GOODS_2015 = (("Refrigerador", "REFRIGERADOR", 1, 2), ("Lavadora", "LAVADORA", 3, 4),
               ("Horno de Microondas", "HORNO", 5, 6), ("Automóvil", "AUTOPROP", 7, 8),
               ("Algún aparato para oír radio", "RADIO", 1, 2), ("Televisor", "TELEVISOR", 3, 4),
               ("Televisor de pantalla plana", "TELEVISOR_PP", 5, 6),
               ("Computadora", "COMPUTADORA", 7, 8), ("Teléfono fijo", "TELEFONO", 1, 2),
               ("Teléfono celular", "CELULAR", 3, 4), ("Internet", "INTERNET", 5, 6),
               ("Servicio de televisión de paga", "SERV_TV_PAGA", 7, 8))
_EQUIPMENT_2015 = (("Tinaco", "TINACO", 1, 2), ("Cisterna o aljibe", "CISTERNA", 3, 4),
                   ("Bomba de agua", "BOMBA_AGUA", 5, 6), ("Regadera", "REGADERA", 7, 8),
                   ("Boiler o calentador de agua", "BOILER", 1, 2),
                   ("Calentador solar de agua", "CALENTADOR_SOLAR", 3, 4),
                   ("Aire acondicionado", "AIRE_ACON", 5, 6), ("Panel solar", "PANEL_SOLAR", 7, 8))


def _items(items: tuple, universe: Callable[[pd.DataFrame], pd.Series] | None = None):
    return _stacked_cells(*(_item(col, (yes, no, 9), universe) for _, col, yes, no in items))


def _item_cells(items: tuple) -> tuple[str, ...]:
    return tuple(f"{name}: {c}" for name, *_ in items for c in ("dwellings", "yes", "no", "NE"))


def _row_cells(rows: tuple, cells: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{row}: {c}" for row, _ in rows for c in cells)


def _total_row(k: tuple) -> tuple | None:
    """A (state, sex, category) row → (state, sex) for the category «Total»."""
    return k[:2] if k[2] == "Total" else None


def _long(estimator: str, names: tuple[str, ...], sheet: str | None = None):
    """Tabulados with one row per (state, sex, category): the category's count (the first
    value), in the order of ``names``; a missing category raises."""
    def read(wb):
        rows = _estimates(_sheet(wb, sheet), estimator)
        out = {}
        for (state, sex, cat), values in rows.items():
            out.setdefault((state, sex), {})[_words(cat)] = values[0]
        return {k: [v[_words(n)] for n in names] for k, v in out.items()}
    return read


def _wide(estimator: str, pick: Callable[[list], list], sheet: str | None = None,
          dims: Callable[[tuple], tuple | None] = lambda k: k):
    """Tabulados with one row per (state[, sex …]): ``pick`` turns the row's values into
    the compared counts; ``dims`` maps a row key onto ``(state, sex)`` (``None`` skips it)."""
    def read(wb):
        out = {}
        for key, values in _estimates(_sheet(wb, sheet), estimator).items():
            if (k := dims(key)) is not None:
                out[k] = pick(values)
        return out
    return read


# Censo 2010 and 2020 dwellings: the raw items (7h) -------------------------------------

def _dwellings_2010(v) -> pd.Series:
    """Censo 2010's «viviendas particulares habitadas» of its dwelling tabulados: every
    class but the locales no construidos para habitación, móviles and refugios (5–7; their
    items are blank), the class not specified (9) included."""
    return ~_code(v, "CLAVIVP").isin([5, 6, 7])


def _dwellings_2020(v) -> pd.Series:
    """Censo 2020's: every class but the locales, móviles and refugios (07–09), as the EIC
    2015 (7d) and the 2010 census."""
    return ~_code(v, "CLAVIVP").isin([7, 8, 9])


def _sel(x: pd.Series, which) -> pd.Series:
    """A category of a coded item: ``None`` = any, ``"N+"`` = N or more (not 99, «not
    specified»), a tuple = any of its codes, else the code."""
    if which is None:
        return pd.Series(True, index=x.index)
    if isinstance(which, str):
        return x.between(int(which[:-1]), 98)
    return _is(x, which)


def _crossed(universe: Callable[[pd.DataFrame], pd.Series], rows: str, row_codes: tuple,
             cols: str, col_codes: tuple, bases: Callable | None = None):
    """The dwellings of ``universe`` in each category of ``rows`` (its codes as
    :func:`_sel`), then in each category of ``cols`` within it."""
    def ours(v):
        u, r, c = universe(v), _code(v, rows), _code(v, cols)
        return [cell for rc in row_codes for cell in _counts_of(
            u & _sel(r, rc), *(u & _sel(r, rc) & _sel(c, cc) for cc in col_codes))]
    return ours


def _rows_of(estimator: str, which: str, sheet: str | None = None,
             bases: list[int] | None = None):
    """A tabulado with «Viviendas» and «Ocupantes» rows: the ``which`` rows' total and its
    percentages as counts (``bases`` as :func:`_counts`)."""
    return _wide(estimator, lambda v: _counts(v[0], v[1:], bases), sheet=sheet,
                 dims=lambda k: (k[0], "T") if k[1] == which else None)


def _named(*names: str) -> tuple[str, ...]:
    return names


# 14_02A: walls (rows) × roofs (columns)
_WALLS_2010 = ("Total", "Material de desecho", "Lámina de cartón", "Lámina de asbesto o metálica",
               "Carrizo, bambú o palma", "Embarro o bajareque", "Madera", "Adobe",
               "Tabique, ladrillo, block, piedra, cantera, cemento o concreto",
               "No especificado")
_ROOFS_2010 = ("waste material", "cardboard sheet", "metal sheet", "asbestos sheet",
               "palm or straw", "wood or tejamanil", "terrado with beams", "tile",
               "concrete slab", "NE")
_ROOMS_2010 = ("Total", "1 cuarto", "2 cuartos", "3 cuartos", "4 cuartos", "5 cuartos o más",
               "No especificado")
_EQUIPMENT_2010 = (("Estufa de gas", "ESTUFAG", 1, 2),
                   ("Estufa de leña o carbón con chimenea", "ESTUFAL", 3, 4),
                   ("Tinaco", "TINACO", 1, 2), ("Calentador de agua", "BOILER", 3, 4),
                   ("Cisterna o aljibe", "CISTERNA", 1, 2), ("Regadera", "REGADERA", 3, 4),
                   ("Medidor de luz", "MEDLUZ", 1, 2))


def _toilet_2010(v):
    """14_07A: the dwellings with a toilet (``SERSAN`` 1) by its use (all, shared
    ``USOEXC`` 1, exclusive 3, not specified 9), then by how it takes water (``CONAGU``: it
    can — flush 5 or a bucket 6 —, it cannot 7, not specified 9)."""
    u = _dwellings_2010(v) & _code(v, "SERSAN").eq(1)
    use, water = _code(v, "USOEXC"), _code(v, "CONAGU")
    out = []
    for codes in (None, 1, 3, 9):
        r = u & _sel(use, codes)
        out += _counts_of(r, r & water.isin([5, 6]), r & water.eq(5), r & water.eq(6),
                          r & water.eq(7), r & water.eq(9))
    return out


# 2020 (16_vivienda.xlsx): the equipment and the waste separation, one row per item (its
# «yes» and «no» codes; 9 = not specified), dwellings (its first four values) and occupants
_EQUIPMENT_2020 = (("Bomba de agua", "BOMBA_AGUA", 5, 6), ("Regadera", "REGADERA", 7, 8),
                   ("Boiler o calentador de agua (gas, eléctrico, leña)", "BOILER", 1, 2),
                   ("Calentador solar de agua", "CALENTADOR_SOLAR", 3, 4),
                   ("Aire acondicionado", "AIRE_ACON", 5, 6),
                   ("Panel solar para tener electricidad", "PANEL_SOLAR", 7, 8))
_SEPARATION_2020 = (("En orgánicos e inorgánicos", "SEPARACION1", 1, 2),
                    ("En desperdicios para alimentar animales", "SEPARACION2", 3, 4),
                    ("En desperdicios para echarlos a las plantas", "SEPARACION3", 5, 6),
                    ("En cartón, latas o plástico para vender, regalar, donar o reutilizar",
                     "SEPARACION4", 7, 8))


def _electricity_2020(v) -> pd.Series:
    return _dwellings_2020(v) & _code(v, "ELECTRICIDAD").eq(1)


def _saving_bulbs_2020(v):
    """16-16: the dwellings with electricity by their share of energy-saving bulbs
    (``FOCOS_AHORRA`` of ``FOCOS``): none (0 — whatever the total, also not specified), below
    50%, 50–75%, 75–100%, all; not specified = ``FOCOS_AHORRA`` 999 (or, with some, ``FOCOS``
    999)."""
    u = _electricity_2020(v)
    bulbs, saving = _code(v, "FOCOS"), _code(v, "FOCOS_AHORRA")
    ne = saving.eq(999) | (bulbs.eq(999) & saving.gt(0))
    share = (saving / bulbs).where(~ne & saving.gt(0))
    return _counts_of(u, u & saving.eq(0), u & share.lt(0.5), u & share.ge(0.5) & share.lt(0.75),
                      u & share.ge(0.75) & share.lt(1), u & share.ge(1), u & ne)


def _owned_2020(v) -> pd.Series:
    return _dwellings_2020(v) & _code(v, "TENENCIA").eq(1)


def _credit_2020(v) -> pd.Series:
    """16-36: the owned dwellings bought or built (``FORMA_ADQUI`` 1–3) with a credit (a
    ``FINANCIAMIENTO`` answer 1–7, not only their own resources 8) — the dwellings asked
    ``DEUDA``."""
    credit = np.logical_or.reduce([_code(v, f"FINANCIAMIENTO{i}").between(1, 7)
                                   for i in (1, 2, 3)])
    return _owned_2020(v) & _code(v, "FORMA_ADQUI").isin([1, 2, 3]) & credit


def _two_blocks(names: tuple[str, ...], block: int, sheet: str):
    """2020's tabulados whose rows are items with a dwellings block and an occupants block
    of four values each (total, yes, no, not specified): the ``block``-th, as counts."""
    return _stacked(names, lambda v: _counts(v[4 * block], v[4 * block + 1:4 * block + 4]),
                    sheet)


_VIV_2020 = "cpv2020_a_eum_16_vivienda.xlsx"


def _occupants_title(title: str) -> str:
    """«Dwellings …» / «Owned dwellings …» → «Occupants of the (owned) dwellings …»."""
    head, rest = title.split("wellings", 1)
    return f"Occupants of the {head.lower()}wellings{rest}"


# 7h: the owners (2015 NUM_DUE_VIV1/2, 2020 DUE1_NUM/DUE2_NUM: person rows, 99 = not
# identified), whose sex the dwelling frame takes from the person file (_with_owners)
_OWNERS = {"2015": ("NUM_DUE_VIV1", "NUM_DUE_VIV2"), "2020": ("DUE1_NUM", "DUE2_NUM")}
_MAN, _WOMAN = "1", "3"


def _owners_2020(v):
    """16-28: the owned dwellings by their owners: one woman, one man; co-owners: two women,
    two men, a woman and a man (either order); the owner not identified (``DUE1_NUM`` 99)."""
    own, first, second = _owned_2020(v), v["DUE1_SEXO"], v["DUE2_SEXO"]
    alone, both = second.isna() & first.notna(), first.notna() & second.notna()
    unknown = _code(v, "DUE1_NUM").eq(99)
    return _counts_of(own, own & alone & first.eq(_WOMAN), own & alone & first.eq(_MAN),
                      own & both & first.eq(_WOMAN) & second.eq(_WOMAN),
                      own & both & first.eq(_MAN) & second.eq(_MAN),
                      own & both & first.ne(second), own & unknown)


def _owners_2015(v):
    """14-14: the owned dwellings by their owners, in their order: only a man, only a woman;
    co-owners a man and a woman, a woman and a man, both of one sex; not identified (99)."""
    own, first, second = _dwellings_2015(v) & _code(v, "TENENCIA").eq(1), v["DUE1_SEXO"], v["DUE2_SEXO"]
    alone, both = second.isna() & first.notna(), first.notna() & second.notna()
    return _counts_of(own, own & alone & first.eq(_MAN), own & alone & first.eq(_WOMAN),
                      own & both & first.eq(_MAN) & second.eq(_WOMAN),
                      own & both & first.eq(_WOMAN) & second.eq(_MAN),
                      own & both & first.eq(second), own & _code(v, "NUM_DUE_VIV1").eq(99))


def _deeds_by_owner_2015(v):
    """14-16: the owned dwellings by the (first) owner's sex — a man, a woman, not identified
    (99) — then by deed (``ESCRITURAS_VIV``)."""
    own = _dwellings_2015(v) & _code(v, "TENENCIA").eq(1)
    first, deed = v["DUE1_SEXO"], _code(v, "ESCRITURAS_VIV")
    out = []
    for who in (own & first.eq(_MAN), own & first.eq(_WOMAN),
                own & _code(v, "NUM_DUE_VIV1").eq(99)):
        out += _counts_of(who, *(who & deed.eq(c) for c in (1, 2, 3, 8, 9)))
    return out


def _dwelling_checks_2020() -> tuple[Check, ...]:
    """Censo 2020's dwelling tabulados by state (16_vivienda.xlsx): each, its dwellings and
    (``b``) its occupants (Σ ``FACTOR`` × ``NUMPERS``)."""
    out = []
    specs = (
        ("02", "Dwellings by wall (`PAREDES`)", _dwellings_2020, "PAREDES",
         (*range(1, 9), 9), ("waste material", "cardboard sheet", "asbestos or metal sheet",
                             "reed, bamboo or palm", "embarro or bajareque", "wood", "adobe",
                             "brick, block, stone or concrete", "NE")),
        ("04", "Dwellings by roof (`TECHOS`)", _dwellings_2020, "TECHOS", (*range(1, 11), 99),
         ("waste material", "cardboard sheet", "metal sheet", "asbestos sheet",
          "fibre-cement sheet", "palm or straw", "wood or tejamanil", "terrado with beams",
          "tile", "concrete slab", "NE")),
        ("06", "Dwellings by a room to cook in (`COCINA`)", _dwellings_2020, "COCINA",
         (1, 3, 9), ("yes", "no", "NE")),
        ("08", "Dwellings by where they cook (`LUG_COC`)", _dwellings_2020, "LUG_COC",
         (1, 2, 3, 4, 5, 6, 9), ("inside", "a separate room", "a corridor", "a shed",
                                 "outdoors", "no space to cook", "NE")),
        ("10", "Dwellings by cooking fuel (`COMBUSTIBLE`)", _dwellings_2020, "COMBUSTIBLE",
         (1, 2, 3, 4, 5, 9), ("wood or charcoal", "gas", "electricity", "other",
                              "do not cook", "NE")),
        ("12", "Dwellings cooking with wood or charcoal by chimney (`ESTUFA`)",
         lambda v: _dwellings_2020(v) & _code(v, "COMBUSTIBLE").eq(1), "ESTUFA", (1, 3, 9),
         ("with a chimney", "without", "NE")),
        ("14", "Dwellings with electricity by light bulbs (`FOCOS`)", _electricity_2020,
         "FOCOS", (tuple(range(1, 6)), tuple(range(6, 11)), tuple(range(11, 16)),
                   tuple(range(16, 21)), tuple(range(21, 999)), 999),
         ("1-5", "6-10", "11-15", "16-20", "21+", "NE")),
        ("18", "Dwellings with a toilet or latrine by its use (`USOEXC`)",
         lambda v: _dwellings_2020(v) & _code(v, "SERSAN").isin([1, 2]), "USOEXC", (3, 1, 9),
         ("exclusive", "shared", "NE")),
        ("24", "Dwellings by waste disposal (`DESTINO_BAS`)", _dwellings_2020, "DESTINO_BAS",
         (1, 2, 3, 4, 5, 6, 9), ("collection", "container", "burn", "bury", "public dump",
                                 "elsewhere", "NE")),
        ("26", "Dwellings by tenure (`TENENCIA`)", _dwellings_2020, "TENENCIA",
         (1, 2, 3, 4, 9), ("own", "rented", "a relative's or lent", "other", "NE")),
        ("30", "Owned dwellings by deed (`ESCRITURAS`)", _owned_2020, "ESCRITURAS",
         (1, 2, 3, 8, 9), ("in the resident owner's name", "in a non-resident's name",
                           "none", "not known", "NE")),
        ("32", "Owned dwellings by acquisition (`FORMA_ADQUI`)", _owned_2020, "FORMA_ADQUI",
         (1, 2, 3, 4, 5, 6, 9), ("bought", "had it built", "built it", "inherited",
                                 "government", "other", "NE")),
    )
    for sheet, title, universe, col, codes, names in specs:
        for suffix, which, weight in (("a", "Viviendas", None), ("b", "Ocupantes", _occupants)):
            out.append(Check("2020", f"16-{sheet}{suffix}",
                             title if suffix == "a" else _occupants_title(title),
                             _VIV_2020, "viviendas", ("total", *names),
                             _rows_of("Valor", which, sheet), _item(col, codes, universe),
                             unit="persons", sheet=sheet, weight=weight))
    bulbs = ("total", "none", "below 50%", "50-75%", "75-100%", "all", "NE")
    title = ("Dwellings with electricity by their share of energy-saving bulbs "
             "(`FOCOS_AHORRA`/`FOCOS`)")
    for suffix, which, weight in (("a", "Viviendas", None), ("b", "Ocupantes", _occupants)):
        out.append(Check("2020", f"16-16{suffix}",
                         title if suffix == "a" else _occupants_title(title), _VIV_2020,
                         "viviendas", bulbs, _rows_of("Valor", which, "16"), _saving_bulbs_2020,
                         unit="persons", sheet="16", weight=weight,
                         note="None = no saving bulb, whatever the total (also when it is not "
                              "specified); not specified = the saving bulbs' count (7h)."))
    for sheet, items, title in (("20", _EQUIPMENT_2020, "equipment (`BOMBA_AGUA` … "
                                 "`PANEL_SOLAR`)"),
                                ("22", _SEPARATION_2020, "waste separation (`SEPARACION1`–4)")):
        names = tuple(n for n, *_ in items)
        for block, (suffix, weight) in enumerate((("a", None), ("b", _occupants))):
            out.append(Check("2020", f"16-{sheet}{suffix}",
                             f"{'Dwellings' if block == 0 else 'Occupants'} by {title}",
                             _VIV_2020, "viviendas", _item_cells(items),
                             _two_blocks(names, block, sheet), _items(items, _dwellings_2020),
                             unit="persons", sheet=sheet, weight=weight))
    out.append(Check("2020", "16-28", "Owned dwellings by their owners' sex and number "
                     "(`DUE1_NUM`/`DUE2_NUM` → the person's `SEXO`)", _VIV_2020, "viviendas",
                     ("total", "one woman", "one man", "two women", "two men",
                      "a woman and a man", "not identified"),
                     _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="28",
                           dims=lambda k: (k[0], "T")),
                     _owners_2020, unit="persons", sheet="28",
                     note="The owner items point at the person rows (`NUMPER`), whose `SEXO` "
                          "the person file gives; 99 = the owner not identified (7h)."))
    out.append(Check("2020", "16-36", "Owned dwellings bought or built with a credit by its "
                     "payment (`DEUDA`)", _VIV_2020, "viviendas",
                     ("total", "paid", "being paid", "payment suspended", "not known", "NE"),
                     _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="36",
                           dims=lambda k: (k[0], "T")),
                     _item("DEUDA", (1, 2, 3, 8, 9), _credit_2020), unit="persons", sheet="36",
                     note="Bought or built (`FORMA_ADQUI` 1–3) with a credit: a `FINANCIAMIENTO` "
                          "source 1–7, not only their own resources (7h)."))
    return tuple(out)


def _dwelling_checks_2010() -> tuple[Check, ...]:
    """Censo 2010's dwelling tabulados by state (``14_NNA_ESTATAL.xls``, «Parámetro»): its
    dwellings without the locales, móviles and refugios, the occupants Σ ``FACTOR`` ×
    ``NUMPERS``."""
    est = "Parámetro"
    out = [
        Check("2010", "14_02A", "Dwellings by wall and roof (`PAREDES`, `TECHOS`)",
              "14_02A_ESTATAL.xls", "viviendas", _row_cells(tuple((n, None) for n in _WALLS_2010),
                                                           ("total", *_ROOFS_2010)),
              _stacked(_WALLS_2010, lambda v: _counts(v[0], v[1:]), None, est),
              _crossed(_dwellings_2010, "PAREDES", (None, *range(1, 9), 9), "TECHOS",
                       (*range(1, 10), 99)), unit="persons",
              note="Locales no construidos para habitación, móviles and refugios (`CLAVIVP` "
                   "5–7) left out, as INEGI's 2010 dwelling tabulados (7h)."),
        Check("2010", "14_05A", "Owned dwellings by rooms and acquisition (`TOTCUART`, "
              "`FADQUI`)", "14_05A_ESTATAL.xls", "viviendas",
              _row_cells(tuple((n, None) for n in _ROOMS_2010),
                         ("owned", "bought", "had it built", "built it", "other", "NE")),
              _stacked(_ROOMS_2010, lambda v: _counts(v[0], v[1:]), None, est),
              _crossed(lambda v: _dwellings_2010(v) & _code(v, "TENVIV").eq(1), "TOTCUART",
                       (None, 1, 2, 3, 4, "5+", 99), "FADQUI", (1, 2, 3, 4, 9)),
              unit="persons"),
        Check("2010", "14_07A", "Dwellings with a toilet by use and water (`USOEXC`, `CONAGU`)",
              "14_07A_ESTATAL.xls", "viviendas",
              _row_cells(tuple((n, None) for n in ("all", "shared", "exclusive", "use NE")),
                         ("total", "takes water", "flush", "bucket", "no water", "NE")),
              _stacked(("Total", "De uso compartido", "De uso exclusivo", "Uso no especificado"),
                       lambda v: _counts(v[0], v[1:], [0, 1, 1, 0, 0]), None, est),
              _toilet_2010, unit="persons"),
        Check("2010", "14_09A", "Dwellings by equipment (`ESTUFAG` … `MEDLUZ`)",
              "14_09A_ESTATAL.xls", "viviendas", _item_cells(_EQUIPMENT_2010),
              _stacked(tuple(n for n, *_ in _EQUIPMENT_2010), lambda v: _counts(v[0], v[1:]),
                       None, est), _items(_EQUIPMENT_2010, _dwellings_2010), unit="persons"),
        Check("2010", "14_10A", "Dwellings with piped water by supply (`DOTAGUAD`)",
              "14_10A_ESTATAL.xls", "viviendas",
              ("total", "daily", "every third day", "once or twice a week", "now and then",
               "NE"),
              _wide(est, lambda v: _counts(v[0], v[1:]), dims=lambda k: (k[0], "T")),
              _item("DOTAGUAD", (1, 2, (3, 4), 5, 9),
                    lambda v: _dwellings_2010(v) & _code(v, "DISAGU").isin([1, 2])),
              unit="persons", note="Piped water: inside the dwelling or the lot (`DISAGU` "
                                   "1–2), the dwellings asked `DOTAGUAD` (7h)."),
        Check("2010", "14_12A", "Dwellings by kitchen and cooking fuel (`COCINA`, `COMBUST`)",
              "14_12A_ESTATAL.xls", "viviendas",
              _row_cells(tuple((n, None) for n in ("all", "kitchen", "no kitchen", "NE")),
                         ("total", "LP gas", "natural gas", "wood or charcoal", "other", "NE")),
              _stacked(("Total", "Disponen de cocina", "No disponen de cocina",
                        "No especificado"), lambda v: _counts(v[0], v[1:]), None, est),
              _crossed(_dwellings_2010, "COCINA", (None, 1, 3, 9), "COMBUST",
                       (1, 2, (3, 4), (5, 6), 9)), unit="persons",
              note="Electricity is «otro combustible» (7h)."),
    ]
    for key, source, title, col, codes, names in (
            ("14_03A", "14_03A_ESTATAL.xls", "by tenure (`TENVIV`)", "TENVIV", (1, 2, 3, 9),
             ("own", "rented", "other", "NE")),
            ("14_14A", "14_14A_ESTATAL.xls", "by waste disposal (`ELIBAS`)", "ELIBAS",
             (1, 2, 3, 4, 5, 6, (7, 8), 9),
             ("collection", "public dump", "container", "burn", "bury", "vacant lot or street",
              "ravine, river, lake or sea", "NE"))):
        for suffix, which, weight in (("a", "Viviendas", None), ("b", "Ocupantes", _occupants)):
            out.append(Check("2010", key + suffix,
                             f"{'Dwellings' if suffix == 'a' else 'Occupants'} {title}", source,
                             "viviendas", ("total", *names), _rows_of(est, which),
                             _item(col, codes, _dwellings_2010), unit="persons", weight=weight))
    return tuple(out)


# CGPV 2000 dwellings: the raw items (7i) -------------------------------------------------
# Its dwelling tabulados count every private dwelling (each class: their items are recorded)
# once — the script's dwelling frame keeps the first household's row (_frame) — and the
# occupants Σ FACTOR × NUMPERS (the dwelling's persons); shares in points.

def _of(den: pd.Series, *nums: pd.Series) -> list:
    """Shares of ``den``: each numerator within it."""
    return [(den & n, den) for n in nums]


def _vi_items(v):
    """C2KVI16: per good (its «yes» and «no» codes; 9 = not specified), % of the dwellings."""
    every = pd.Series(True, index=v.index)
    return [cell for _, col, yes, no in _GOODS_2000
            for cell in _of(every, *(_code(v, col).eq(c) for c in (yes, no, 9)))]


_GOODS_2000 = (("RADIO O RADIOGRABADORA", "RADIO", 1, 2), ("TELEVISIÓN", "TELEVI", 3, 4),
               ("VIDEOCASETERA", "VIDEO", 5, 6), ("LICUADORA", "LICUAD", 7, 8),
               ("REFRIGERADOR", "REFRIG", 1, 2), ("LAVADORA", "LAVADORA", 3, 4),
               ("TELÉFONO", "TELEFONO", 5, 6), ("CALENTADOR DE AGUA", "BOILER", 7, 8),
               ("AUTOMÓVIL O CAMIONETA PROPIOS", "AUTOPROP", 1, 2), ("COMPUTADORA", "COMPU", 3, 4))
_GOODS_CELLS_2000 = tuple(f"{n}: {c}" for n, *_ in _GOODS_2000 for c in ("yes", "no", "NE"))


def _vi_coded(col: str, codes: tuple):
    """Each code (or tuple of codes; ``"N+"`` = N to 98) of ``col``, % of the dwellings."""
    def ours(v):
        x = _code(v, col)
        return _of(pd.Series(True, index=v.index), *(_sel(x, c) for c in codes))
    return ours


def _vi05(v):
    """C2KVI05: the rooms as INEGI counts them (``TOTCUART_INEGI``: less an exclusive kitchen
    nobody sleeps in; 7f), 1 … 5, 6 and more, not specified."""
    x = pd.to_numeric(v["TOTCUART_INEGI"], errors="coerce")
    return _of(pd.Series(True, index=v.index), *(x.eq(k) for k in range(1, 6)), x.ge(6), x.isna())


def _vi07(v):
    """C2KVI07: a kitchen (``COCINA`` 1), then as % of those: exclusive (``COCDOR`` 4: nobody
    sleeps there), a bedroom too (3), not specified (9); no kitchen (2), not specified (9)."""
    every, kitchen, sleep = pd.Series(True, index=v.index), _code(v, "COCINA"), _code(v, "COCDOR")
    has = kitchen.eq(1)
    return [(has, every), *_of(has, sleep.eq(4), sleep.eq(3), sleep.eq(9)),
            *_of(every, kitchen.eq(2), kitchen.eq(9))]


def _vi09(v):
    """C2KVI09: an exclusive sanitary service (``SERSAN`` 1 and ``USOEXC`` 1), then as % of
    those its water (``CONAGU``: connected, a bucket, none, not specified); none exclusive
    (``SERSAN`` 2, or 1 and shared), not specified (``SERSAN`` 9, or 1 and ``USOEXC`` 9)."""
    every, kind, use, water = (pd.Series(True, index=v.index), _code(v, "SERSAN"),
                               _code(v, "USOEXC"), _code(v, "CONAGU"))
    own = kind.eq(1) & use.eq(1)
    return [(own, every), *_of(own, *(water.eq(c) for c in (1, 2, 3, 9))),
            (kind.eq(2) | (kind.eq(1) & use.eq(2)), every),
            (kind.eq(9) | (kind.eq(1) & use.eq(9)), every)]


def _vi10d(v):
    """C2KVI10 in detail: drainage (``DRENAJE`` 1–4), then as % of those its outlet (the
    public network, a septic tank, a ravine, a river or the sea); none (5), not specified."""
    every, d = pd.Series(True, index=v.index), _code(v, "DRENAJE")
    has = d.between(1, 4)
    return [(has, every), *_of(has, *(d.eq(c) for c in (1, 2, 3, 4))),
            *_of(every, d.eq(5), d.eq(9))]


def _vi11(v):
    """C2KVI11: piped water in the dwelling's grounds (``DISAGU`` 1–2: inside, outside but
    in the lot), carried (3–4: a public tap, another dwelling), none (5–6: a pipa; a well,
    river or other), each with its parts as % of it; not specified (9)."""
    every, w = pd.Series(True, index=v.index), _code(v, "DISAGU")
    out = []
    for group in ((1, 2), (3, 4), (5, 6)):
        has = w.isin(group)
        out += [(has, every), *_of(has, *(w.eq(c) for c in group))]
    return out + [(w.eq(9), every)]


def _vi12(v):
    """C2KVI12: the dwellings with piped water inside the dwelling or the lot (``DISAGU``
    1–2, asked ``DOTAGUAD``) by its supply: daily (then as % of those: all day, part of the
    day, not specified — ``DOTAGUAR``), every third day, twice a week, once, now and then,
    not specified."""
    piped = _code(v, "DISAGU").isin([1, 2])
    days, hours = _code(v, "DOTAGUAD"), _code(v, "DOTAGUAR")
    daily = piped & days.eq(1)
    return [(daily, piped), *_of(daily, *(hours.eq(c) for c in (1, 2, 9))),
            *_of(piped, *(days.eq(c) for c in (2, 3, 4, 5, 9)))]


def _vi14(v):
    """C2KVI14: owned (``TENVIV`` 1; as % of those ``TENPROP`` being paid 3, paid 4, other 5,
    not specified 9), not owned (2: rented 6, lent or other 7, not specified 9), not
    specified (``TENVIV`` 9)."""
    every, owned, how = pd.Series(True, index=v.index), _code(v, "TENVIV"), _code(v, "TENPROP")
    own, other = owned.eq(1), owned.eq(2)
    return [(own, every), *_of(own, *(how.eq(c) for c in (3, 4, 5, 9))),
            (other, every), *_of(other, *(how.eq(c) for c in (6, 7, 9))), (owned.eq(9), every)]


def _vi18(v):
    """C2KVI18: the dwellings that hand their waste to a service, a container, the street or
    a ravine (``ELIBAS`` 1–4: those asked ``ELIBASPE``) by how often it is collected (daily,
    every third day, twice a week, once, now and then, never, not specified), then each way:
    the collection service (1), a container (2), the street, a vacant lot or a ravine (3, 4)."""
    how, often = _code(v, "ELIBAS"), _code(v, "ELIBASPE")
    return [cell for codes in ((1, 2, 3, 4), 1, 2, (3, 4)) for cell in _of(
        _is(how, codes), *(often.eq(c) for c in (1, 2, 3, 4, 5, 6, 9)))]


def _vi19(v):
    """C2KVI19: the occupants (``NUMPERS``) per dwelling, per household (``NUMHOGS``: their
    number where there are several, blank for one), per room (``TOTCUART_INEGI``) and per
    bedroom (``CUADORM``) of the dwellings that gave them, and the households per dwelling."""
    every = pd.Series(True, index=v.index)
    persons, households = v["NUMPERS"], _code(v, "NUMHOGS").fillna(1)
    rooms = pd.to_numeric(v["TOTCUART_INEGI"], errors="coerce")
    bedrooms = _code(v, "CUADORM").where(lambda x: x.lt(99))
    with_rooms, with_bedrooms = rooms.notna(), bedrooms.notna()
    return [(Weighted(every, persons), every),
            (Weighted(every, persons), Weighted(every, households)),
            (Weighted(with_rooms, persons), Weighted(with_rooms, rooms)),
            (Weighted(with_bedrooms, persons), Weighted(with_bedrooms, bedrooms)),
            (Weighted(every, households), every)]


def _dwelling_checks_2000() -> tuple[Check, ...]:
    """CGPV 2000's dwelling tabulados (C2KVI01–18; VI06 and VI10 since 6i on the derived
    columns, here in detail): every one for the dwellings and, but VI04 and VI12, the
    occupants (``…o``)."""
    specs = (
        ("01", "Floors (`PISOS`)", "CDEF", ("earth", "cement", "tiles, wood or other", "NE"),
         _vi_coded("PISOS", (1, 2, 3, 9))),
        ("02", "Walls (`PAREDES`)", "CDE", ("light, natural or precarious", "solid", "NE"),
         _vi_coded("PAREDES", (tuple(range(1, 8)), 8, 9))),
        ("03", "Roofs (`TECHOS`)", "CDEFGHI",
         ("waste material", "cardboard sheet", "asbestos or metal sheet", "palm, tejamanil or "
          "wood", "tile", "slab, brick or terrado", "NE"), _vi_coded("TECHOS", (1, 2, 3, 4, 5, 6, 9))),
        ("05", "Rooms (`TOTCUART_INEGI`)", "CDEFGHI", ("1", "2", "3", "4", "5", "6+", "NE"), _vi05),
        ("06d", "Bedrooms in detail (`CUADORM`)", "CDEFGHI", ("1", "2", "3", "4", "5", "6+", "NE"),
         _vi_coded("CUADORM", (1, 2, 3, 4, 5, "6+", 99))),
        ("07", "Kitchen (`COCINA`, `COCDOR`)", "CDEFGH",
         ("a kitchen", "exclusive", "a bedroom too", "use NE", "no kitchen", "NE"), _vi07),
        ("08", "Cooking fuel (`COMBUST`)", "CDEF", ("gas", "wood or charcoal", "other", "NE"),
         _vi_coded("COMBUST", (1, (2, 3), (4, 5), 9))),
        ("09", "Exclusive sanitary service and its water (`SERSAN`, `USOEXC`, `CONAGU`)",
         "CDEFGHI", ("exclusive", "connected", "a bucket", "no water", "water NE",
                     "none exclusive", "NE"), _vi09),
        ("10d", "Drainage in detail (`DRENAJE`)", "CDEFGHI",
         ("drainage", "public network", "septic tank", "ravine", "river, lake or sea", "none",
          "NE"), _vi10d),
        ("11", "Water (`DISAGU`)", "CDEFGHIJKL",
         ("piped in the grounds", "inside", "in the lot", "carried", "a public tap",
          "another dwelling", "none", "a pipa", "a well, river or other", "NE"), _vi11),
        ("13", "Electricity (`ELECTRI`)", "CDE", ("has it", "has none", "NE"),
         _vi_coded("ELECTRI", (1, 2, 9))),
        ("14", "Tenure (`TENVIV`, `TENPROP`)", "CDEFGHIJKL",
         ("owned", "being paid", "paid", "other", "owned, NE", "not owned", "rented",
          "lent or other", "not owned, NE", "NE"), _vi14),
        ("15", "Age of the building (`ANTIGUE`)", "CDEFGHIJ",
         ("under 1", "1-5", "6-10", "11-20", "21-30", "31-50", "50+", "NE"),
         _vi_coded("ANTIGUE", (1, 2, 3, 4, 5, 6, 7, 9))),
        ("17", "Waste disposal (`ELIBAS`)", "CDEFGHI",
         ("collection service", "public container", "street or vacant lot", "ravine",
          "river, lake or sea", "burn or bury", "NE"), _vi_coded("ELIBAS", (1, 2, 3, 4, 5, 6, 9))),
    )
    out = []
    for key, title, cols, cells, ours in specs:
        source = f"C2KVI{key[:2]}.xls"
        out.append(Check("2000", f"VI{key}", f"{title}, % of the dwellings", source, "viviendas",
                         cells, _c2k(cols, level="dwellings"), ours))
        out.append(Check("2000", f"VI{key}o", f"{title}, % of the occupants", source,
                         "viviendas", cells, _c2k(cols, level="occupants"), ours,
                         weight=_occupants))
    # Chiapas: shares of a small base (the carried water's tap or dwelling, the container's
    # never collected) sit up to 0.84 / 1.79 points off — its sample's weights, as its other
    # 2000 cells (MI11 0.68, EM04 0.56); the nation's VI18o cell (0.057) inherits it
    loose = {"VI11": {7: 0.9}, "VI11o": {7: 0.9}}
    out = [replace(c, tolerance=loose[c.key],
                   note=c.note or "Chiapas: shares of the small «carried» base, up to 0.84 "
                                  "points off (its weights; 7i).") if c.key in loose else c
           for c in out]
    out[0] = replace(out[0], note="Every private dwelling (its «Otro» classes carry the "
                                  "items, 7f), once (the first household's row); the occupants "
                                  "Σ `FACTOR` × `NUMPERS` (7i).")
    out += [
        Check("2000", "VI04", "Occupants per dwelling (`NUMPERS`), % of the dwellings",
              "C2KVI04.xls", "viviendas", ("1", "2", "3", "4", "5", "6", "7+"),
              _c2k_states("CDEFGHI"), _vi_coded("NUMPERS", (1, 2, 3, 4, 5, 6, "7+"))),
        Check("2000", "VI12", "Water supply of the dwellings with piped water inside the "
              "dwelling or the lot (`DOTAGUAD`, `DOTAGUAR`), %", "C2KVI12.xls", "viviendas",
              ("daily", "all day", "part of the day", "hours NE", "every third day",
               "twice a week", "once a week", "now and then", "NE"),
              _c2k_states("CDEFGHIJK"), _vi12),
        Check("2000", "VI16", "Goods (`RADIO` … `COMPU`), % of the dwellings", "C2KVI16.xls",
              "viviendas", _GOODS_CELLS_2000, _c2k_items("CDE"), _vi_items),
        Check("2000", "VI16o", "Goods (`RADIO` … `COMPU`), % of the occupants", "C2KVI16.xls",
              "viviendas", _GOODS_CELLS_2000, _c2k_items("GHI"), _vi_items, weight=_occupants),
        Check("2000", "VI19", "Averages per dwelling (`NUMPERS`, `NUMHOGS`, `TOTCUART_INEGI`, "
              "`CUADORM`)", "C2KVI19.xls", "viviendas",
              ("occupants per dwelling", "occupants per household", "occupants per room",
               "occupants per bedroom", "households per dwelling"),
              _c2k_states("CDEFG"), _vi19, unit="average",
              note="Rooms as 2000's ITER (`TOTCUART_INEGI`, 7f) and bedrooms of the dwellings "
                   "that gave them; households = `NUMHOGS` (blank = one household; 7i)."),
    ]
    frequency = ("daily", "every third day", "twice a week", "once a week", "now and then",
                 "never", "NE")
    names = tuple(f"{way}: {f}" for way in ("all", "collection service", "container",
                                            "street, vacant lot or ravine") for f in frequency)
    for key, label, weight in (("VI18", "VIVIENDAS", None), ("VI18o", "OCUPANTES", _occupants)):
        out.append(Check("2000", key, "Waste collection frequency by way of disposal "
                         f"(`ELIBAS`, `ELIBASPE`), % of the {'dwellings' if weight is None else 'occupants'}",
                         "C2KVI18.xls", "viviendas", names, _c2k_repeated("CDEFGHI", label),
                         _vi18, weight=weight,
                         tolerance={7: 1.6} if weight is None else {7: 1.8, 0: 0.06},
                         note="The dwellings that hand their waste to a service, a container, "
                              "the street or a ravine (`ELIBAS` 1–4), asked `ELIBASPE` (7i). "
                              "Chiapas: «container: never», a share of a small base, 1.57 "
                              "points off (1.79 for the occupants, whose national cell "
                              "inherits 0.057) — its weights."
                         if weight is None else ""))
    return tuple(out)


# Censo 2010 persons and international migrants (7m) --------------------------------------

_QUIN_2010 = ("Total", *(f"{a:02d}-{a + 4:02d} años" for a in range(0, 65, 5)), "65 años y más",
              "No especificado")
_WOMEN_AGES_2010 = ("Total", "12-14 años", *(f"{a}-{a + 4} años" for a in range(15, 65, 5)),
                    "65 años y más")


def _children_2010(p):
    """02_04A: the women of 12 and more by children born alive (``NUMHIJ`` 0 … 7, 8 and
    more, not specified 98/99), by age group."""
    women = p["SEXO"].astype(str).eq("3") & _age(p).between(12, 130)
    born = _code(p, "NUMHIJ")
    out = []
    for label in _WOMEN_AGES_2010:
        g = women & _age_group(p, label)
        out += _counts_of(g, *(g & born.eq(k) for k in range(8)), g & born.between(8, 97),
                          g & born.isin([98, 99]))
    return out


def _limitation_causes_2010(p):
    """06_02A: limited in an activity (``LIM_ACTIVIDAD``), then as % of them each cause any of
    their limitations has (``CAUSADIS1``–``7``: birth, illness, accident, old age, other, not
    specified); not limited, not specified."""
    every, lim = pd.Series(True, index=p.index), _cat(p, "LIM_ACTIVIDAD")
    limited = lim.eq("Sí")
    causes = pd.DataFrame({i: _code(p, f"CAUSADIS{i}") for i in range(1, 8)})
    return _counts_of(every, limited, *(limited & causes.eq(c).any(axis=1) for c in (1, 2, 3, 4, 5, 9)),
                      lim.eq("No"), lim.eq("No especificado"))


def _service_use_2010(p):
    """09_04A: who use a health service (``SERSALUD`` 01–08), then as % of them each
    institution; who use none (09), not specified (99)."""
    every, use = pd.Series(True, index=p.index), _code(p, "SERSALUD")
    return _counts_of(every, use.between(1, 8), *(use.eq(k) for k in range(1, 9)), use.eq(9),
                      use.eq(99))


_UNIONS_2010 = (("Total", "Total", (1, 5, 6, 7)), ("Casado(a)", "Total", (5, 6, 7)),
                ("Casado(a)", "Civil", (5,)), ("Casado(a)", "Religiosamente", (6,)),
                ("Casado(a)", "Civil y religiosamente", (7,)), ("Unión libre", "Total", (1,)))


def _spouse_2010(p):
    """10_02A: the 12+ in a union (``ESTCON`` 1, 5, 6, 7) by its kind, then by whether the
    spouse lives in the dwelling (``IDENT_PAREJA_CAT``: yes, no, not specified)."""
    twelve, union, spouse = _age(p).between(12, 130), _code(p, "ESTCON"), _cat(p, "IDENT_PAREJA_CAT")
    out = []
    for _, _, codes in _UNIONS_2010:
        u = twelve & union.isin(codes)
        out += _counts_of(u, *(u & spouse.eq(c) for c in ("Sí", "No", "No especificado")))
    return out


def _unions_2010(wb):
    """10_02A: the rows (state, sex, civil status, kind of union) in :data:`_UNIONS_2010`'s
    order, as counts."""
    rows = _estimates(_sheet(wb, None), "Parámetro")
    out = {}
    for (state, sex, civil, kind), v in rows.items():
        out.setdefault((state, sex), {})[civil, kind] = _counts(v[0], v[1:])
    return {k: [x for civil, kind, _ in _UNIONS_2010 for x in v[civil, kind]] for k, v in out.items()}


def _migrants_by_origin(cells: Callable[[pd.DataFrame], list]):
    """The 2010 international migrants counted in the state they left (``MLUGORI_C``; 999 =
    not specified), as counts."""
    def ours(m):
        origin = m["MLUGORI_C"]
        return [(ByOrigin(c, origin), None) for c in cells(m)]
    return ours


def _movement_2010(m) -> list[pd.Series]:
    """04_04A: every migrant, the emigrants (``MPAIRES`` 1–2: the United States, another
    country), the return migrants (3; of them: in the same dwelling, ``MCONRESACT`` 1, in
    another place 3, not specified 9), not specified (9)."""
    res, cur = _code(m, "MPAIRES"), _code(m, "MCONRESACT")
    back = res.eq(3)
    return [pd.Series(True, index=m.index), res.isin([1, 2]), back, back & cur.eq(1),
            back & cur.eq(3), back & cur.eq(9), res.eq(9)]


_MIGRANT_AGES_2010 = ((0, 14), (15, 24), (25, 34), (35, 49), (50, 59), (60, 130))


def _person_checks_2010() -> tuple[Check, ...]:
    """Censo 2010's person and international-migrant tabulados by state read in 7m."""
    est = "Parámetro"
    return (
        Check("2010", "01_02A", "Population by five-year age (`EDAD_QUIN`) and sex",
              "01_02A_ESTATAL.xls", "personas",
              tuple(f"{g}: {s}" for g in _QUIN_2010 for s in ("total", "men", "women")),
              _by_dims(est, None, _QUIN_2010, lambda v: v[:3]), _population(_QUIN_2010),
              unit="persons", note="The sexes are columns: sex T only (7m)."),
        Check("2010", "02_04A", "Women 12+ by children born alive (`NUMHIJ`) and age",
              "02_04A_ESTATAL.xls", "personas",
              tuple(f"{g}: {c}" for g in _WOMEN_AGES_2010 for c in (
                  "women", *(str(k) for k in range(8)), "8+", "NE")),
              _by_dims(est, None, _WOMEN_AGES_2010, lambda v: _counts(v[0], v[1:])),
              _children_2010, unit="persons", note="Not specified = `NUMHIJ` 98 and 99 (7m)."),
        Check("2010", "06_02A", "Limitation in an activity and its causes (`LIM_ACTIVIDAD`, "
              "`CAUSADIS1`–7)", "06_02A_ESTATAL.xls", "personas",
              ("population", "limited", "birth", "illness", "accident", "old age", "other",
               "cause NE", "not limited", "NE"),
              _wide(est, lambda v: _counts(v[0], v[1:], [0, 1, 1, 1, 1, 1, 1, 0, 0])),
              _limitation_causes_2010, unit="persons",
              note="A cause counts the limited with any limitation of that cause (7m)."),
        Check("2010", "09_04A", "Use of health services by institution (`SERSALUD`)",
              "09_04A_ESTATAL.xls", "personas",
              ("population", "users", "IMSS", "ISSSTE", "ISSSTE estatal", "Pemex, Defensa, Marina",
               "SSA", "IMSS Oportunidades", "private", "elsewhere", "no user", "NE"),
              _wide(est, lambda v: _counts(v[0], v[1:], [0, *[1] * 8, 0, 0])),
              _service_use_2010, unit="persons",
              note="The institutions are % of the users (7m)."),
        Check("2010", "10_02A", "The 12+ in a union by its kind and the spouse's residence "
              "(`ESTCON`, `IDENT_PAREJA_CAT`)", "10_02A_ESTATAL.xls", "personas",
              tuple(f"{c} {k}: {x}" for c, k, _ in _UNIONS_2010
                    for x in ("in a union", "spouse here", "spouse elsewhere", "NE")),
              _unions_2010, _spouse_2010, unit="persons"),
        Check("2010", "04_04A", "International migrants by movement, state left (`MPAIRES`, "
              "`MCONRESACT`)", "04_04A_ESTATAL.xls", "migrantes",
              ("migrants", "emigrants", "return migrants", "back in the same dwelling",
               "back elsewhere", "back, NE", "NE"),
              _wide(est, lambda v: _counts(v[0], v[1:], [0, 0, 2, 2, 2, 0])),
              _migrants_by_origin(_movement_2010), unit="persons", by_origin=True,
              note="Counted in the state they left (`MLUGORI_C`; 7m)."),
        Check("2010", "04_05A", "International migrants by sex, state left (`MSEXO`)",
              "04_05A_ESTATAL.xls", "migrantes", ("migrants", "men", "women"),
              _wide(est, lambda v: _counts(v[0], v[1:]), dims=lambda k: (k[0], "T")),
              _migrants_by_origin(lambda m: [pd.Series(True, index=m.index),
                                             m["MSEXO"].astype(str).eq("1"),
                                             m["MSEXO"].astype(str).eq("3")]),
              unit="persons", by_origin=True),
        Check("2010", "04_06A", "International migrants by age at emigrating, state left "
              "(`MEDAD`)", "04_06A_ESTATAL.xls", "migrantes",
              ("migrants", "0-14", "15-24", "25-34", "35-49", "50-59", "60+", "NE"),
              _wide(est, lambda v: _counts(v[0], v[1:]), dims=lambda k: (k[0], "T")),
              _migrants_by_origin(lambda m: [pd.Series(True, index=m.index),
                                             *(_code(m, "MEDAD").between(a, b)
                                               for a, b in _MIGRANT_AGES_2010),
                                             _code(m, "MEDAD").eq(999)]),
              unit="persons", by_origin=True),
    )


# Censo 2020 persons and international migrants (7n) --------------------------------------

_QUIN_2020 = ("Total", *(f"{a:02d}-{a + 4:02d} años" for a in range(0, 75, 5)), "75 años y más")
_REGISTRATION_AGES_2020 = ("Total", "00-04 años", "05-11 años", "12-17 años", "18-29 años",
                           "30-44 años", "45-64 años", "65 años y más")
_BIRTHPLACES_2020 = ("Total", "En los Estados Unidos de América", "En otro país")
_SPEAKERS_2020 = (("Total", None), ("Habla lengua indígena", 1), ("No habla lengua indígena", 3),
                  ("No especificado", 9))
_MIGRANT_AGES_2020 = ((0, 17), (18, 29), (30, 44), (45, 64), (65, 130))


def _registration_2020(p):
    """01-04: by age group, registered (``REGIS_NAC`` 1–2; as % of them in Mexico 1, abroad
    2), not registered (3), not specified (9)."""
    reg = _code(p, "REGIS_NAC")
    out = []
    for label in _REGISTRATION_AGES_2020:
        g = _age_group(p, label)
        r = g & reg.isin([1, 2])
        out += _counts_of(g, r, r & reg.eq(1), r & reg.eq(2), g & reg.eq(3), g & reg.eq(9))
    return out


def _nationality_2020(p):
    """04-02: the born abroad (``ENT_PAIS_NAC_CAT`` «OtroPais») — all, in the United States
    (``ENT_PAIS_NAC`` 221), elsewhere — by Mexican nationality (``NACIONALIDAD`` 1, 3, 9)."""
    abroad = _cat(p, "ENT_PAIS_NAC_CAT").eq("OtroPais")
    usa = _code(p, "ENT_PAIS_NAC").eq(221)
    nat = _code(p, "NACIONALIDAD")
    out = []
    for g in (abroad, abroad & usa, abroad & ~usa):
        out += _counts_of(g, *(g & nat.eq(c) for c in (1, 3, 9)))
    return out


def _by_place_2020(wb):
    """04-02: (state, birthplace, sex) rows → per (state, sex) the birthplaces in order."""
    rows = _estimates(_sheet(wb, "02"), "Valor")
    out = {}
    for (state, place, sex), v in rows.items():
        out.setdefault((state, sex), {})[place] = _counts(v[0], v[1:])
    return {k: [x for place in _BIRTHPLACES_2020 for x in v[place]] for k, v in out.items()}


def _self_identification(item: str):
    """05-02 (2020, ``PERTE_INDIGENA``), 05_01A (2010, ``PERETN``; 7p): the 3+ by
    indigenous language (all, speakers, not, not specified) and self-identification
    (``item`` 1, 3, 9)."""
    def ours(p):
        three = _age(p).between(3, 130)
        speaks, ident = _code(p, "HLENGUA"), _code(p, item)
        out = []
        for _, code in _SPEAKERS_2020:
            g = three if code is None else three & speaks.eq(code)
            out += _counts_of(g, *(g & ident.eq(c) for c in (1, 3, 9)))
        return out
    return ours


def _understands(item: str, codes: tuple[int, int, int]):
    """05-04 (2020: ``ELENGUA`` 5, 7, 9), 05_02A (2010: ``CLENGUA`` 1, 3, 9; 7p): the 3+
    who speak no indigenous language (``HLENGUA`` 3) by whether they understand one."""
    def ours(p):
        g = _age(p).between(3, 130) & _code(p, "HLENGUA").eq(3)
        under = _code(p, item)
        return _counts_of(g, *(g & under.eq(c) for c in codes))
    return ours


def _destination_2020(m) -> list[pd.Series]:
    """04-10: every migrant, the United States (``MPAIDES_C`` 221), another country, not
    specified (999 or blank)."""
    dest = _code(m, "MPAIDES_C")
    unknown = dest.isna() | dest.eq(999)
    return [pd.Series(True, index=m.index), dest.eq(221), ~unknown & dest.ne(221), unknown]


def _person_checks_2020() -> tuple[Check, ...]:
    """Censo 2020's person and international-migrant tabulados by state read in 7n."""
    pop, mig, eth = ("cpv2020_a_eum_01_poblacion.xlsx", "cpv2020_a_eum_04_migracion.xlsx",
                     "cpv2020_a_eum_05_etnicidad.xlsx")
    by_sex = lambda m: [pd.Series(True, index=m.index), m["MSEXO"].astype(str).eq("1"),  # noqa: E731
                        m["MSEXO"].astype(str).eq("3")]
    ages = lambda m: [pd.Series(True, index=m.index),  # noqa: E731
                      *(_code(m, "MEDAD").between(a, b) for a, b in _MIGRANT_AGES_2020),
                      _code(m, "MEDAD").eq(999)]
    state = lambda k: (k[0], "T")  # noqa: E731
    return (
        Check("2020", "01-02", "Population by five-year age (`EDAD_QUIN`) and sex", pop,
              "personas", tuple(f"{g}: {s}" for g in _QUIN_2020 for s in ("total", "men", "women")),
              _by_dims("Valor", "02", _QUIN_2020, lambda v: v[:3]), _population(_QUIN_2020),
              unit="persons", sheet="02", note="The sexes are columns: sex T only (7n)."),
        Check("2020", "01-04", "Birth registration (`REGIS_NAC`) by age", pop, "personas",
              tuple(f"{g}: {c}" for g in _REGISTRATION_AGES_2020 for c in (
                  "population", "registered", "in Mexico", "abroad", "not registered", "NE")),
              _by_dims("Valor", "04", _REGISTRATION_AGES_2020,
                       lambda v: _counts(v[0], v[1:], [0, 1, 1, 0, 0]), sexed=True),
              _registration_2020, unit="persons", sheet="04"),
        Check("2020", "04-02", "The born abroad by Mexican nationality (`NACIONALIDAD`)", mig,
              "personas", tuple(f"{b}: {c}" for b in ("all", "United States", "elsewhere")
                                for c in ("born abroad", "Mexican", "not", "NE")),
              _by_place_2020, _nationality_2020, unit="persons", sheet="02"),
        Check("2020", "05-02", "Indigenous self-identification of the 3+ (`PERTE_INDIGENA`) "
              "by language", eth, "personas",
              tuple(f"{n}: {c}" for n, _ in _SPEAKERS_2020
                    for c in ("population 3+", "indigenous", "not", "NE")),
              _by_dims("Valor", "02", tuple(n for n, _ in _SPEAKERS_2020),
                       lambda v: _counts(v[0], v[1:]), sexed=True),
              _self_identification("PERTE_INDIGENA"), unit="persons", sheet="02"),
        Check("2020", "05-04", "The 3+ speaking no indigenous language by understanding one "
              "(`ELENGUA`)", eth, "personas", ("population", "understand", "do not", "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="04"),
              _understands("ELENGUA", (5, 7, 9)), unit="persons", sheet="04"),
        Check("2020", "04-04", "International migrants by movement, state left (`MPAIRES`, "
              "`MCONRESACT`)", mig, "migrantes",
              ("migrants", "emigrants", "return migrants", "back in the same dwelling",
               "back elsewhere", "back, NE", "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 0, 2, 2, 2, 0]), sheet="04"),
              _migrants_by_origin(_movement_2010), unit="persons", sheet="04", by_origin=True,
              note="Counted in the state they left (`MLUGORI_C`; 7n)."),
        Check("2020", "04-06", "International migrants by sex, state left (`MSEXO`)", mig,
              "migrantes", ("migrants", "men", "women"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="06", dims=state),
              _migrants_by_origin(by_sex), unit="persons", sheet="06", by_origin=True),
        Check("2020", "04-08", "International migrants by age at emigrating, state left "
              "(`MEDAD`)", mig, "migrantes",
              ("migrants", "0-17", "18-29", "30-44", "45-64", "65+", "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="08", dims=state),
              _migrants_by_origin(ages), unit="persons", sheet="08", by_origin=True),
        Check("2020", "04-10", "International migrants by destination, state left "
              "(`MPAIDES_C`)", mig, "migrantes",
              ("migrants", "United States", "another country", "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="10", dims=state),
              _migrants_by_origin(_destination_2020), unit="persons", sheet="10",
              by_origin=True,
              note="The United States = `MPAIDES_C` 221; not specified 999 or blank (7n)."),
    )


# Censo 2020's disability and migration causes; Censo 2010's self-identification, fields of
# study, divisions, parents and kinship lines (7p) ----------------------------------------

_DIS_ITEMS_2020 = ("DIS_VER", "DIS_OIR", "DIS_CAMINAR", "DIS_RECORDAR", "DIS_BANARSE",
                   "DIS_HABLAR")
_DIS_CAUSES = (("birth", (1,)), ("illness", (2,)), ("accident", (3,)), ("old age", (4,)),
               ("other", (5,)), ("NE", (9,)))
# a mental condition's causes: the accident and the old age among the other causes
_MENTAL_CAUSES = (("birth", (1,)), ("illness", (2,)), ("other", (3, 4, 5)), ("NE", (9,)))
_DIS_AGES_2020 = ("Total", "00-14 años", "15-29 años", "30-59 años", "60-84 años",
                  "85 años y más", "No especificado")
_ACTIVITIES_2020 = ("Total", "Ver aun usando lentes", "Oír aun usando aparato auditivo",
                    "Caminar, subir o bajar", "Recordar o concentrarse",
                    "Bañarse, vestirse o comer", "Hablar o comunicarse")
_DIS_KINDS_2020 = ("Total", "Con discapacidad", "Con limitación")
# 06-02/04: the population; of it, who have a disability, limitation or mental condition;
# of them, the disabled (and of these each cause), the limited (each cause), those with a
# mental condition (each cause); of the population, who have none and not specified
_DIS_CELLS = ("population", "any", "disability",
              *(f"disability: {c}" for c, _ in _DIS_CAUSES), "limitation",
              *(f"limitation: {c}" for c, _ in _DIS_CAUSES), "mental condition",
              *(f"mental: {c}" for c, _ in _MENTAL_CAUSES), "none", "NE")
_DIS_BASES = [0, 1, *[2] * 6, 1, *[9] * 6, 1, *[16] * 4, 0, 0]


def _difficulties_2020(p) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    """Per activity, INEGI's disability (much difficulty, cannot, or the degree unknown: 3,
    4, 8) and limitation (some difficulty, 2, counted only for the persons without a
    disability in another activity: ``LIMITACION``) — 6c's and 6y's rules."""
    limited = _cat(p, "LIMITACION").eq("Sí")
    degree = {i: _code(p, i) for i in _DIS_ITEMS_2020}
    return ({i: d.isin([3, 4, 8]) for i, d in degree.items()},
            {i: limited & d.eq(2) for i, d in degree.items()})


def _any_cause(p, flags: dict[str, pd.Series], codes: tuple) -> pd.Series:
    """The persons with a difficulty in ``flags`` whose cause (``CAU_*``) is one of
    ``codes`` (a person with several difficulties counts once per cause they name)."""
    return pd.concat([m & _code(p, i.replace("DIS_", "CAU_")).isin(codes)
                      for i, m in flags.items()], axis=1).any(axis=1)


def _disability_cells_2020(p) -> list[pd.Series]:
    """06-02/04's cells over every person (:data:`_DIS_CELLS`): ``SIN_DISC_LIM``'s «No»
    has one (6g), the disabled ``DISCAPACIDAD``, the limited ``LIMITACION``, a mental
    condition ``DIS_MENTAL`` 5 (its cause ``CAU_MENTAL``)."""
    dis, lim = _difficulties_2020(p)
    disabled, limited = _cat(p, "DISCAPACIDAD").eq("Sí"), _cat(p, "LIMITACION").eq("Sí")
    mental, mental_cause = _code(p, "DIS_MENTAL").eq(5), _code(p, "CAU_MENTAL")
    none = _cat(p, "SIN_DISC_LIM")
    return [pd.Series(True, index=p.index), none.eq("No"), disabled,
            *(_any_cause(p, dis, c) for _, c in _DIS_CAUSES), limited,
            *(_any_cause(p, lim, c) for _, c in _DIS_CAUSES), mental,
            *(mental & mental_cause.isin(c) for _, c in _MENTAL_CAUSES), none.eq("Sí"),
            none.eq("No especificado")]


def _disability_by_age_2020(p):
    """06-04: :func:`_disability_cells_2020` in each age group."""
    cells = _disability_cells_2020(p)
    return [(g & m, None) for label in _DIS_AGES_2020 for g in [_age_group(p, label)]
            for m in cells]


def _disability_by_activity_2020(p):
    """06-06: for every activity and each of them, the disabled or limited in it (either,
    disabled, limited), then each cause of their difficulty in it."""
    dis, lim = _difficulties_2020(p)
    either = {i: dis[i] | lim[i] for i in _DIS_ITEMS_2020}
    out = []
    for a in range(len(_ACTIVITIES_2020)):
        items = _DIS_ITEMS_2020 if a == 0 else _DIS_ITEMS_2020[a - 1:a]
        for flags in (either, dis, lim):
            flags = {i: flags[i] for i in items}
            out += _counts_of(pd.concat(flags.values(), axis=1).any(axis=1),
                              *(_any_cause(p, flags, c) for _, c in _DIS_CAUSES))
    return out


_DURATIONS_2020 = (("under a year", 0, 11), ("6 months or less", 0, 6),
                   ("7 to 11 months", 7, 11), ("1 to under 3 years", 12, 35),
                   ("3 to 5 years", 36, 1000))


def _duration_2020(m) -> pd.Series:
    """The return migrants' months abroad: the return's year and month less the
    emigration's; missing where a date is not specified (9999, 99)."""
    ea, em, ra, rm = (_code(m, c) for c in ("MFECEMIA", "MFECEMIM", "MFECRETA", "MFECRETM"))
    known = ea.lt(9999) & em.lt(99) & ra.lt(9999) & rm.lt(99)
    return ((ra * 12 + rm) - (ea * 12 + em)).where(known)


def _return_duration_2020(m):
    """04-12: the return migrants (``MPAIRES`` 3), in the state they live in (the frame's),
    by the duration of their migration (:func:`_duration_2020`); not specified."""
    back, months = _code(m, "MPAIRES").eq(3), _duration_2020(m)
    return _counts_of(back, *(back & months.between(lo, hi) for _, lo, hi in _DURATIONS_2020),
                      back & months.isna())


def _return_months_2020(m):
    """04-12: the return migrants' average months abroad (a date not specified: left out)."""
    back, months = _code(m, "MPAIRES").eq(3), _duration_2020(m)
    known = back & months.notna()
    return [(Weighted(known, months.fillna(0)), known)]


# The causes: the questionnaire's precoded answers (work: looking for a job, a job change or
# offer; family: joining the family, marriage; study; deportation — return only) by their
# four-digit code (`MCAUSAEMIG_V`, `MCAUSARETO_V`); every other code is «otra causa», 9999
# not specified (INEGI's footnotes)
_CAUSES_2020 = (("work", ("0101", "0102")), ("family", ("0301", "0401")), ("study", ("0501",)))
_DEPORTED_2020 = ("deported", ("0801",))


def _migration_causes_2020(item: str, universe: Callable[[pd.DataFrame], pd.Series],
                           groups: tuple):
    """04-14/15: the migrants of ``universe`` by the cause ``item`` gives (:data:`_CAUSES_2020`
    and ``groups``), another cause, not specified."""
    def cells(m) -> list[pd.Series]:
        g, code = universe(m), m[item].astype(str)
        named = [g & code.isin(codes) for _, codes in groups]
        unspecified = g & code.eq("9999")
        other = g & m[item].notna() & ~pd.concat([*named, unspecified], axis=1).any(axis=1)
        return [g, *named, other, unspecified]
    return cells


_SELECTED_2010 = (4, 7, 8, 9, 12, 13, 15, 16, 20, 21, 23, 24, 30, 31)


def _selected_states_2010(cells: Callable[[pd.DataFrame], list]):
    """05_01A/02A publish 14 states one by one and «the rest of the states» together: the
    records of the others count in :data:`_REST` (:class:`ByOrigin`; all 32 states needed)."""
    def ours(p):
        state = _code(p, "ENT")
        origin = state.where(state.isin(_SELECTED_2010), _REST)
        return [(ByOrigin(m, origin), None) for m, _ in cells(p)]
    return ours


_FIELDS_2010 = ("education", "arts and humanities", "social sciences, administration, law",
                "natural and exact sciences, computing", "engineering, manufacturing, "
                "construction", "agronomy and veterinary", "health", "services", "NE")


def _fields_2010(universe: Callable[[pd.DataFrame], pd.Series]):
    """07_02A/05A: the persons of ``universe`` by the field of their career, the first digit
    of ``NOMCAR_C`` (`TC_CARRERA_2010`: 1–8, 9 not specified). 800 («carreras técnicas
    básicas», técnica after primaria's code) names no field: not specified (one maestría in
    Veracruz, as INEGI's)."""
    def ours(p):
        code = p["NOMCAR_C"].astype(str)
        g, field = universe(p), code.str[:1].where(code.ne("800"), "9")
        return _counts_of(g, *(g & field.eq(str(d)) for d in range(1, 10)))
    return ours


def _superior_2010(p) -> pd.Series:
    """07_02A: the 18+ with a grade of técnica after preparatoria, normal de licenciatura,
    licenciatura, maestría or doctorado (``NIVACAD`` 08–12)."""
    return _age(p).between(18, 130) & _code(p, "NIVACAD").between(8, 12)


def _technical_2010(p) -> pd.Series:
    """07_05A: the 15+ with a grade of técnica after secundaria (``NIVACAD`` 07)."""
    return _age(p).between(15, 130) & _code(p, "NIVACAD").eq(7)


# 08_06A/07A: the divisions as Censo 2010 spells them (_DIVISIONS: 2015's word order)
_DIVISIONS_2010 = ("Total", "Funcionarios, directores y jefes", "Profesionistas y técnicos",
                   "Trabajadores auxiliares en actividades administrativas",
                   "Comerciantes, empleados en ventas y agentes de ventas",
                   "Trabajadores en servicios personales y vigilancia",
                   "Trabajadores en actividades agrícolas, ganaderas, forestales, caza y pesca",
                   "Trabajadores artesanales",
                   "Operadores de maquinaria industrial, ensambladores, choferes y conductores "
                   "de transporte",
                   "Trabajadores en actividades elementales y de apoyo", "No especificado")
_HOURS_2010 = (("up to 16", 1, 16), ("17-24", 17, 24), ("25-32", 25, 32), ("33-40", 33, 40),
               ("41-48", 41, 48), ("49-56", 49, 56), ("more than 56", 57, 168),
               ("did not work", 0, 0), ("NE", 999, 999))


def _by_division_2010(cells: Callable[[pd.DataFrame, pd.Series], list[pd.Series]]):
    """08_06A/07A: the employed, then those of each division (as 08_02A), each with
    ``cells(frame, group)``."""
    def ours(p):
        e, occ = _employed(p), _code_of(p, "OCUPACION_C_COARSE")
        division = (occ // 10).where(occ.ne(99), 10)
        groups = [e, *(e & division.eq(i) for i in range(1, 11))]
        return [(m, None) for g in groups for m in [g, *cells(p, g)]]
    return ours


def _sectors_of(p, g) -> list[pd.Series]:
    code = _code_of(p, "ACTIVIDADES_C_COARSE")
    return [g & code.isin(s) for _, s in _SECTOR_GROUPS]


def _hours_of(p, g) -> list[pd.Series]:
    """«Hasta 16 horas» starts at 1: who did not work last week (0) apart (``HORTRA``)."""
    hours = _code(p, "HORTRA")
    return [g & hours.between(lo, hi) for _, lo, hi in _HOURS_2010]


_PARENT_AGES_2010 = ("Total", "00-04 años", "05-14 años", "15-29 años", "30-44 años",
                     "45-59 años", "60 años y más", "No especificado")
_KIN_AGES_2010 = ("Total", "00-14 años", "15-29 años", "30-59 años", "60 años y más",
                  "No especificado")
_KINSHIP = ("head", "spouse or partner", "ascendants", "descendants", "collaterals",
            "not related", "NE")
# 12_04A's lines for «otro parentesco» (`PARENT` 08), by its detail (`OTROPARE_C`), found on
# the tabulado in every state: ascendants — step-parents, grand-, great- and
# great-great-grandparents, uncles and aunts, godparents; descendants — great- and
# great-great-grandchildren, nephews and nieces, godchildren; «Familiar» (623) not
# specified; every other code (siblings, cousins, in-laws, co-parents…) or none collateral
_ASCENDANTS_2010 = (602, 606, 607, 608, 612, 620)
_DESCENDANTS_2010 = (610, 611, 613, 621)


def _kinship_2010(p) -> list[pd.Series]:
    """12_04A: head (``PARENT`` 01), spouse (02), ascendants (06 parents, 07 parents-in-law
    and :data:`_ASCENDANTS_2010`), descendants (03 children, 04 grandchildren, 05 children-in-
    law and :data:`_DESCENDANTS_2010`), collaterals (the rest of 08), not related (09), not
    specified (99 and «Familiar»)."""
    rel, other = _code(p, "PARENT"), _code(p, "OTROPARE_C")
    unspecified = rel.eq(99) | (rel.eq(8) & other.eq(623))
    up = rel.isin([6, 7]) | (rel.eq(8) & other.isin(_ASCENDANTS_2010))
    down = rel.isin([3, 4, 5]) | (rel.eq(8) & other.isin(_DESCENDANTS_2010))
    return [rel.eq(1), rel.eq(2), up, down, rel.eq(8) & ~up & ~down & ~unspecified, rel.eq(9),
            unspecified]


def _by_age_2010(groups: tuple[str, ...], cells: Callable[[pd.DataFrame], list[pd.Series]]):
    """12_02A/04A: every age group (``EDAD``), its population and ``cells``."""
    def ours(p):
        masks = [pd.Series(True, index=p.index), *cells(p)]
        return [(g & m, None) for label in groups for g in [_age_group(p, label)]
                for m in masks]
    return ours


def _person_checks_2010_p() -> tuple[Check, ...]:
    """Censo 2010's by-state tabulados 7m left: self-identification (selected states),
    fields of study, sector and hours by division, parents and kinship lines by age (7p)."""
    total = lambda v: _counts(v[0], v[1:])  # noqa: E731
    speakers = tuple(n for n, _ in _SPEAKERS_2020)
    return (
        Check("2010", "05_01A", "Ethnic self-identification of the 3+ (`PERETN`) by language, "
              "selected states", "05_01A_ESTATAL.xls", "personas",
              tuple(f"{n}: {c}" for n in speakers
                    for c in ("population 3+", "indigenous", "not", "NE")),
              _by_dims("Parámetro", None, speakers, total, sexed=True),
              _selected_states_2010(_self_identification("PERETN")), unit="persons",
              by_origin=True,
              note="Published for 14 states; state 98 = «the rest of the states» together "
                   "(7p)."),
        Check("2010", "05_02A", "The 3+ speaking no indigenous language by understanding one "
              "(`CLENGUA`), selected states", "05_02A_ESTATAL.xls", "personas",
              ("population", "understand", "do not", "NE"), _wide("Parámetro", total),
              _selected_states_2010(_understands("CLENGUA", (1, 3, 9))), unit="persons",
              by_origin=True),
        Check("2010", "07_02A", "The 18+ with higher education by field (`NOMCAR_C`)",
              "07_02A_ESTATAL.xls", "personas", ("population", *_FIELDS_2010),
              _wide("Parámetro", total), _fields_2010(_superior_2010), unit="persons",
              note="Higher education = `NIVACAD` 08–12 (técnica after preparatoria, normal de "
                   "licenciatura, licenciatura, posgrado); the field = `NOMCAR_C`'s first "
                   "digit, 800 («carreras técnicas básicas»: one maestría) not specified. "
                   "07_03A (the same counts by field and sex) is not compared (7p)."),
        Check("2010", "07_05A", "The 15+ with técnica after secundaria by field (`NOMCAR_C`)",
              "07_05A_ESTATAL.xls", "personas", ("population", *_FIELDS_2010),
              _wide("Parámetro", total, dims=lambda k: (k[0], "T")),
              _fields_2010(_technical_2010), unit="persons"),
        Check("2010", "08_06A", "Employed by division and sector (`OCUPACION_C_COARSE`, "
              "`ACTIVIDADES_C_COARSE`)", "08_06A_ESTATAL.xls", "personas",
              tuple(f"{d}: {c}" for d in _DIVISIONS_2010
                    for c in ("employed", *(n for n, _ in _SECTOR_GROUPS))),
              _by_dims("Parámetro", None, _DIVISIONS_2010, total, sexed=True),
              _by_division_2010(_sectors_of), unit="persons"),
        Check("2010", "08_07A", "Employed by division and hours worked (`HORTRA`)",
              "08_07A_ESTATAL.xls", "personas",
              tuple(f"{d}: {c}" for d in _DIVISIONS_2010
                    for c in ("employed", *(n for n, *_ in _HOURS_2010))),
              _by_dims("Parámetro", None, _DIVISIONS_2010, total, sexed=True),
              _by_division_2010(_hours_of), unit="persons",
              note="«Hasta 16 horas» from 1: 0 hours is «no trabajó la semana pasada» (7p)."),
        Check("2010", "12_02A", "Parents in the dwelling by age (`MADRE_EN_VIVIENDA`, "
              "`PADRE_EN_VIVIENDA`)", "12_02A_ESTATAL.xls", "personas",
              tuple(f"{a}: {c}" for a in _PARENT_AGES_2010
                    for c in ("population", "both", "only the father", "only the mother",
                              "neither", "not specified")),
              _by_dims("Parámetro", None, _PARENT_AGES_2010, total, sexed=True),
              _by_age_2010(_PARENT_AGES_2010, lambda p: [m for m, _ in _parents(p)[1:]]),
              unit="persons"),
        Check("2010", "12_04A", "Kinship lines by age (`PARENT`, `OTROPARE_C`)",
              "12_04A_ESTATAL.xls", "personas",
              tuple(f"{a}: {c}" for a in _KIN_AGES_2010 for c in ("population", *_KINSHIP)),
              _by_dims("Parámetro", None, _KIN_AGES_2010, total, sexed=True),
              _by_age_2010(_KIN_AGES_2010, _kinship_2010), unit="persons",
              note="INEGI's lines for «otro parentesco» (08), found on the tabulado in every "
                   "state: uncles and godparents ascendants, nephews and godchildren "
                   "descendants, «Familiar» (623) not specified (7p)."),
    )


def _person_checks_2020_p() -> tuple[Check, ...]:
    """Censo 2020's disability tabulados by state and the international migrants' duration
    and causes (7p)."""
    dis, mig = "cpv2020_a_eum_06_discapacidad.xlsx", "cpv2020_a_eum_04_migracion.xlsx"
    state = lambda k: (k[0], "T")  # noqa: E731
    pick = lambda v: _counts(v[0], v[1:], _DIS_BASES)  # noqa: E731
    back = lambda m: _code(m, "MPAIRES").eq(3)  # noqa: E731
    every = lambda m: pd.Series(True, index=m.index)  # noqa: E731
    return (
        Check("2020", "06-02", "Disability, limitation, mental condition and their causes "
              "(`DIS_*`, `CAU_*`)", dis, "personas", _DIS_CELLS, _wide("Valor", pick, sheet="02"),
              lambda p: _counts_of(*_disability_cells_2020(p)), unit="persons", sheet="02",
              note="INEGI's flags (`DISCAPACIDAD`, `LIMITACION`, `SIN_DISC_LIM`: 6c, 6g); a "
                   "cause counts every disabled (limited) person who names it for one of "
                   "their difficulties; a mental condition's «other» holds the accident and "
                   "old age (7p)."),
        Check("2020", "06-04", "Disability, limitation, mental condition and their causes by "
              "age", dis, "personas",
              tuple(f"{a}: {c}" for a in _DIS_AGES_2020 for c in _DIS_CELLS),
              _by_dims("Valor", "04", _DIS_AGES_2020, pick), _disability_by_age_2020,
              unit="persons", sheet="04"),
        Check("2020", "06-06", "Disability or limitation by activity and cause", dis,
              "personas",
              tuple(f"{a}: {k}: {c}" for a in _ACTIVITIES_2020 for k in _DIS_KINDS_2020
                    for c in ("persons", *(n for n, _ in _DIS_CAUSES))),
              _by_dims("Valor", "06", _DIS_KINDS_2020, lambda v: _counts(v[0], v[1:]),
                       rows=_ACTIVITIES_2020),
              _disability_by_activity_2020, unit="persons", sheet="06",
              note="A limitation in an activity counts only without a disability in another "
                   "(6y's rule)."),
        Check("2020", "04-12", "Return migrants by the duration of their migration "
              "(`MFECEMIA`/`M`, `MFECRETA`/`M`)", mig, "migrantes",
              ("return migrants", *(n for n, *_ in _DURATIONS_2020), "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:7], [0, 1, 1, 0, 0, 0]), sheet="12",
                    dims=state),
              _return_duration_2020, unit="persons", sheet="12",
              note="In the state they live in (the dwelling's); the months between the "
                   "emigration and the return (7p)."),
        Check("2020", "04-12m", "Return migrants' average months abroad", mig, "migrantes",
              ("months",), _wide("Valor", lambda v: [v[7]], sheet="12", dims=state),
              _return_months_2020, unit="average", sheet="12", tolerance={None: 1e-4}),
        Check("2020", "04-14", "Return migrants by the cause of their return (`MCAUSARETO_V`)",
              mig, "migrantes",
              ("return migrants", *(n for n, _ in _CAUSES_2020), _DEPORTED_2020[0], "other",
               "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="14", dims=state),
              lambda m: _counts_of(*_migration_causes_2020(
                  "MCAUSARETO_V", back, (*_CAUSES_2020, _DEPORTED_2020))(m)),
              unit="persons", sheet="14"),
        Check("2020", "04-15", "International migrants by the cause of their emigration "
              "(`MCAUSAEMIG_V`), state left", mig, "migrantes",
              ("migrants", *(n for n, _ in _CAUSES_2020), "other", "NE"),
              _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="15", dims=state),
              _migrants_by_origin(_migration_causes_2020("MCAUSAEMIG_V", every, _CAUSES_2020)),
              unit="persons", sheet="15", by_origin=True,
              note="Every migrant, counted in the state they left (`MLUGORI_C`); a deportation "
                   "is «otra causa» here (7p)."),
    )


# CGPV 2000 persons: population, disability, fertility, language (7k) ---------------------

_AGES_2000 = (*((a, a + 4) for a in range(0, 65, 5)), (65, 130), None)    # None = 999
_DISABILITY_AGES_2000 = ((0, 14), (15, 29), (30, 59), (60, 130), None)
_MOTHER_AGES_2000 = ((12, 130), (12, 14), *((a, a + 4) for a in range(15, 60, 5)), (60, 130))


def _ages_2000(p: pd.DataFrame, groups: tuple) -> list[pd.Series]:
    age = _age(p)
    return [age.eq(999) if g is None else age.between(*g) for g in groups]


def _po01(p):
    """C2KPO01: the population by five-year age group (999 = not specified), % per sex."""
    every = pd.Series(True, index=p.index)
    return _of(every, *_ages_2000(p, _AGES_2000))


# CGPV 2000's disability types: the items' own codes and its classified «other» limitation
# (DISOTRA_C): the insufficiently specified motor (299) and mental (399) ones join their
# type, «sin especificar el tipo» (960) is the type not specified, the rest «otra» — and so
# is the second limitation that could not be classified (DISOTRA_V 7)
_DISABILITY_TYPES_2000 = (("motor", (("DISMOV", 1), ("DISBRA", 2), ("DISOTRA_C", 299))),
                          ("hearing", (("DISOIR", 3),)), ("speech", (("DISMUDO", 4),)),
                          ("visual", (("DISVER", 5),)),
                          ("mental", (("DISMENT", 6), ("DISOTRA_C", 399))),
                          ("other", (*(("DISOTRA_C", c) for c in (131, 199, 421, 422, 430, 499)),
                                     ("DISOTRA_V", 7))),
                          ("type NE", (("DISOTRA_C", 960),)))


def _disability_2000(p) -> tuple[pd.Series, pd.Series, pd.Series, dict[str, pd.Series]]:
    """Without a disability (``DISNOTIE`` 8), with one (any type), not specified (``DISMOV``
    9), and each type."""
    types = {name: np.logical_or.reduce([_code(p, col).eq(code) for col, code in items])
             for name, items in _DISABILITY_TYPES_2000}
    with_ = np.logical_or.reduce([*types.values(), _code(p, "DISOTRA_C").notna()])
    return (_code(p, "DISNOTIE").eq(8), pd.Series(with_, index=p.index),
            _code(p, "DISMOV").eq(9), {k: pd.Series(v, index=p.index) for k, v in types.items()})


def _di01(p):
    """C2KDI01: the population and each age group by disability (without, with, NE), %."""
    without, with_, unknown, _ = _disability_2000(p)
    every = pd.Series(True, index=p.index)
    return [cell for g in (every, *_ages_2000(p, _DISABILITY_AGES_2000))
            for cell in _of(g, without, with_, unknown)]


def _di02(p):
    """C2KDI02: without, with (then each type as % of them: a person may have several), not
    specified."""
    without, with_, unknown, types = _disability_2000(p)
    every = pd.Series(True, index=p.index)
    return [(without, every), (with_, every), *_of(with_, *types.values()), (unknown, every)]


def _di04(p):
    """C2KDI04: the disabled by cause (``CAUSADIS``: birth, illness, accident, old age, other,
    not specified), %."""
    _, with_, _, _ = _disability_2000(p)
    cause = _code(p, "CAUSADIS")
    return _of(with_, *(cause.eq(c) for c in (1, 2, 3, 4, 5, 9)))


def _mothers_2000(p) -> tuple[pd.Series, pd.Series]:
    """The women of 12 and more who said how many children they had born alive (``NUMHIJ``
    below 98), and the number."""
    born = _code(p, "NUMHIJ")
    return p["SEXO"].astype(str).eq("2") & _age(p).between(12, 130) & born.lt(98), born


def _fe_average(item: str | None):
    """C2KFE03 (``item`` None: the children born alive) and C2KFE04 (``HIJSOB``, the
    surviving: 0 where the woman gave none) per woman, all and by her age group."""
    def ours(p):
        women, born = _mothers_2000(p)
        value = born if item is None else _code(p, item).where(lambda x: x.lt(99), 0).fillna(0)
        return [(Weighted(women & g, value), women & g) for g in _ages_2000(p, _MOTHER_AGES_2000)]
    return ours


def _fe05(p):
    """C2KFE05: the children who died (``HIJFAL``) as % of those born alive, of the women who
    gave both, all and by her age group."""
    women, born = _mothers_2000(p)
    died = _code(p, "HIJFAL")
    women &= died.lt(99)
    return [(Weighted(women & g, died), Weighted(women & g, born))
            for g in _ages_2000(p, _MOTHER_AGES_2000)]


def _li02(p):
    """C2KLI02: the 5+ speaking an indigenous language (``HLENGUA`` 1; as % of them, Spanish
    too, not, not specified — ``HESPANOL``), not speaking one (2), not specified (9)."""
    five = _age(p).between(5, 130)
    speaks, spanish = _code(p, "HLENGUA"), _code(p, "HESPANOL")
    s = five & speaks.eq(1)
    return [(s, five), *_of(s, spanish.eq(3), spanish.eq(4), spanish.eq(9)),
            *_of(five, speaks.eq(2), speaks.eq(9))]


def _person_checks_2000() -> tuple[Check, ...]:
    """CGPV 2000's person tabulados by state read in 7k."""
    ages = tuple(f"{g[0]}-{g[1]}" if g and g[1] < 130 else (f"{g[0]}+" if g else "NE")
                 for g in _AGES_2000)
    mothers = ("12+", *(f"{a}-{b}" if b < 130 else f"{a}+" for a, b in _MOTHER_AGES_2000[1:]))
    return (
        Check("2000", "PO01", "Population by five-year age, % per sex", "C2KPO01.xls",
              "personas", ages, _c2k_age_shares, _po01,
              note="Published as counts with the sexes in columns: compared as each age "
                   "group's share of the state's population of the sex (7k)."),
        Check("2000", "DI01", "Disability by age group (`DISNOTIE`, `DISMOV` …), %",
              "C2KDI01.xls", "personas",
              tuple(f"{a}: {c}" for a in ("all", "0-14", "15-29", "30-59", "60+", "age NE")
                    for c in ("without", "with", "NE")),
              _c2k_rows("CDE"), _di01, note="Sex T only (the age groups are rows; 7k)."),
        Check("2000", "DI02", "Disability and its types, %", "C2KDI02.xls", "personas",
              ("without", "with", *(n for n, _ in _DISABILITY_TYPES_2000), "NE"),
              _c2k("CDEFGHIJKL"), _di02,
              note="Types as % of the disabled (several per person): motor = `DISMOV` 1, "
                   "`DISBRA` 2 or `DISOTRA_C` 299; mental = `DISMENT` 6 or 399; the type not "
                   "specified = 960; other = 131, 199, 421, 422, 430, 499 or `DISOTRA_V` 7 "
                   "(a second limitation not classified; 7k)."),
        Check("2000", "DI04", "The disabled by cause (`CAUSADIS`), %", "C2KDI04.xls",
              "personas", ("birth", "illness", "accident", "old age", "other", "NE"),
              _c2k("CDEFGH"), _di04),
        Check("2000", "FE03", "Children born alive per woman 12+ (`NUMHIJ`), by age",
              "C2KFE03.xls", "personas", mothers, _c2k_states("BCDEFGHIJKLM"),
              _fe_average(None), unit="average",
              note="The women who said how many (`NUMHIJ` below 98); «M.I.» (muestra "
                   "insuficiente) is not compared (7k)."),
        Check("2000", "FE04", "Surviving children per woman 12+ (`HIJSOB`), by age",
              "C2KFE04.xls", "personas", mothers, _c2k_states("BCDEFGHIJKLM"),
              _fe_average("HIJSOB"), unit="average",
              note="0 for the women without an answer (no child born alive; 7k)."),
        Check("2000", "FE05", "Children who died (`HIJFAL`), % of those born alive, by the "
              "mother's age", "C2KFE05.xls", "personas", mothers,
              _c2k_states("BCDEFGHIJKLM"), _fe05),
        Check("2000", "LI02", "Indigenous language and Spanish of the 5+ (`HLENGUA`, "
              "`HESPANOL`), selected states, %", "C2KLI02.xls", "personas",
              ("speaks one", "and Spanish", "not Spanish", "Spanish NE", "speaks none", "NE"),
              _c2k("CDEFGH"), _li02, tolerance={0: 0.1},
              note="INEGI publishes it for its selected states (7k). The nation's Spanish "
                   "split is up to 0.081 points off: Chiapas's 0.34 (its weights) on its "
                   "~15% of the speakers."),
    )


# CGPV 2000 households and education (7l) ------------------------------------------------
# The households are the dwelling file's rows (table «hogares»); their population is
# Σ FACTOR × TOTPERS (the household's members).

def _household_persons(h: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(h["FACTOR"]) * pd.to_numeric(h["TOTPERS"])


def _ho01(h):
    """C2KHO01: the households by size (``TOTPERS`` 1 … 8, 9 and more), %."""
    size, every = _code(h, "TOTPERS"), pd.Series(True, index=h.index)
    return _of(every, *(size.eq(k) for k in range(1, 9)), size.ge(9))


def _ho02(h):
    """C2KHO02: familiar (``TIPOHOG`` 1–4; as % of them nuclear, ampliado, compuesto, not
    specified), no familiar (5–6: unipersonal, corresidente), not specified (9), %."""
    kind, every = _code(h, "TIPOHOG"), pd.Series(True, index=h.index)
    fam, other = kind.isin([1, 2, 3, 4]), kind.isin([5, 6])
    return [(fam, every), *_of(fam, *(kind.eq(k) for k in (1, 2, 3, 4))),
            (other, every), *_of(other, kind.eq(5), kind.eq(6)), (kind.eq(9), every)]


def _household_income(item: str):
    """C2KHO05 (``INGTRHOG``, the household's income from work) and C2KHO07 (``INGTOHOG``,
    its total income) in its municipality's monthly minimum wages (7c's table): none, below
    1, 1 to 2, above 2 to 3 (exactly 3 wages fall here, though the header says «menos de 3»:
    Coahuila's total incomes settle it), above 3 to 5, above 5 to 10, above 10, not specified
    (999999; 999998 is the top code, above 10)."""
    def ours(h):
        from mxcensus.cpv_derived import _salario_minimo

        income, every = _code(h, item), pd.Series(True, index=h.index)
        wage = _salario_minimo("2000", _code(h, "ENT").astype("int64"),
                               _code(h, "MUN").astype("int64")).astype(float)
        ne = income.ge(999999) | income.isna()
        cents = income * 100
        known = ~ne
        return _of(every, known & income.eq(0), known & income.gt(0) & cents.lt(wage),
                   known & cents.ge(wage) & cents.le(2 * wage),
                   known & cents.gt(2 * wage) & cents.le(3 * wage),
                   known & cents.gt(3 * wage) & cents.le(5 * wage),
                   known & cents.gt(5 * wage) & cents.le(10 * wage),
                   known & cents.gt(10 * wage), ne)
    return ours


def _ho08(h):
    """C2KHO08: per household, its members (``TOTPERS``), its head's age (of the heads of a
    specified age), its members under 12, of 12 to 64, of 65 and more, economically active,
    inactive, employed (``_with_members_2000``)."""
    every = pd.Series(True, index=h.index)
    head_age = pd.to_numeric(h["_HEAD_AGE"], errors="coerce")
    known = head_age.lt(999)
    return [(Weighted(every, h["TOTPERS"]), every), (Weighted(known, head_age), known),
            *[(Weighted(every, h[col]), every)
              for col in ("_UNDER12", "_12TO64", "_65PLUS", "_PEA", "_PEI", "_EMPLOYED")]]


_LITERACY_AGES_2000 = ((6, 14), (6, 9), (10, 14))
_LITERACY15_AGES_2000 = ((15, 130), (15, 19), (20, 29), (30, 39), (40, 49), (50, 59),
                         (60, 130))
_ATTENDANCE_AGES_2000 = ((6, 130), (6, 9), (10, 14), (15, 19), (20, 24), (25, 29), (30, 130))
_NOT_ATTENDING_AGES_2000 = ((7, 29), (7, 9), (10, 14), (15, 19), (20, 24), (25, 29))


def _by_age_2000(item: str, groups: tuple, codes: tuple, universe=None):
    """Each age group (the first = all) by ``item``'s codes (or tuples), % of the group."""
    def ours(p):
        x, age = _code(p, item), _age(p)
        u = pd.Series(True, index=p.index) if universe is None else universe(p)
        return [cell for lo, hi in groups
                for cell in _of(u & age.between(lo, hi), *(_is(x, c) for c in codes))]
    return ours


def _c2k_rows_by_sex(columns: dict[str, str]):
    """CGPV 2000 tabulados with a state row and its age-group rows, the sexes in columns
    (C2KED02/04/06: ``{"T": "EHK", "H": "FIL", "M": "GJM"}``; 7l)."""
    def read(wb):
        out = {}
        for sex, cols in columns.items():
            for (state, _), v in _c2k_rows(cols)(wb).items():
                out[state, sex] = v
        return out
    return read


def _person_checks_2000_l() -> tuple[Check, ...]:
    """CGPV 2000's household and education tabulados by state read in 7l."""
    out = []
    specs = (("HO01", "Households by size (`TOTPERS`)", "CDEFGHIJK",
              tuple(str(k) for k in range(1, 9)) + ("9+",), _ho01),
             ("HO02", "Households by type and class (`TIPOHOG`)", "CDEFGHIJK",
              ("familiar", "nuclear", "ampliado", "compuesto", "familiar, type NE",
               "no familiar", "unipersonal", "corresidente", "NE"), _ho02),
             ("HO05", "Households by income from work in minimum wages (`INGTRHOG`)",
              "CDEFGHIJ", ("none", "below 1", "1-2", "2-3", "3-5", "5-10", "above 10", "NE"),
              _household_income("INGTRHOG")),
             ("HO07", "Households by total income in minimum wages (`INGTOHOG`)", "CDEFGHIJ",
              ("none", "below 1", "1-2", "2-3", "3-5", "5-10", "above 10", "NE"),
              _household_income("INGTOHOG")))
    for key, title, cols, cells, ours in specs:
        for suffix, label, weight in (("", "HOGARES", None), ("p", "POBLACIÓN", _household_persons)):
            out.append(Check("2000", key + suffix,
                             f"{title}, % of the {'households' if not suffix else 'population'}",
                             f"C2K{key}.xls", "hogares", cells, _c2k_repeated(cols, label),
                             ours, weight=weight))
    out[0] = replace(out[0], note="The dwelling file's household rows; the population Σ "
                                  "`FACTOR` × `TOTPERS`; the income against the "
                                  "municipality's monthly minimum wage (7c; 7l).")
    out.append(Check("2000", "HO08", "Averages per household (`TOTPERS`; the members' ages and "
                     "activity, the head's age, from the person file)", "C2KHO08.xls",
                     "hogares", ("members", "head's age", "under 12", "12-64", "65+",
                                 "economically active", "inactive", "employed"),
                     _c2k_states("CDEFGHIJ"), _ho08, unit="average",
                     note="The members by age and activity (`CONACT_CAT`) and the head's age "
                          "(`OTROPARE_C` 100) from the person file (`_with_members_2000`; 7l)."))
    sexes = {"T": "EHK", "H": "FIL", "M": "GJM"}
    groups = lambda gs: tuple(f"{a}-{b}" if b < 130 else f"{a}+" for a, b in gs)  # noqa: E731
    out += [
        Check("2000", "ED02", "Literacy of the 6-14 (`ALFABET`), %", "C2KED02.xls",
              "personas", tuple(f"{g}: {c}" for g in groups(_LITERACY_AGES_2000)
                                for c in ("can read and write", "cannot", "NE")),
              _c2k_rows_by_sex(sexes), _by_age_2000("ALFABET", _LITERACY_AGES_2000, (1, 2, 9))),
        Check("2000", "ED04", "Literacy of the 15+ (`ALFABET`) by ten-year age, %",
              "C2KED04.xls", "personas",
              tuple(f"{g}: {c}" for g in groups(_LITERACY15_AGES_2000)
                    for c in ("literate", "illiterate", "NE")),
              _c2k_rows_by_sex(sexes),
              _by_age_2000("ALFABET", _LITERACY15_AGES_2000, (1, 2, 9))),
        Check("2000", "ED06", "School attendance of the 6+ (`ASISTEN`) by age, %",
              "C2KED06.xls", "personas",
              tuple(f"{g}: {c}" for g in groups(_ATTENDANCE_AGES_2000)
                    for c in ("attends", "does not", "NE")),
              _c2k_rows_by_sex(sexes),
              _by_age_2000("ASISTEN", _ATTENDANCE_AGES_2000, (1, 2, 9))),
        Check("2000", "ED12", "The 7-29 not attending school by cause (`ABANESCO`), %",
              "C2KED12.xls", "personas",
              tuple(f"{g}: {c}" for g in groups(_NOT_ATTENDING_AGES_2000)
                    for c in ("never attended", "stopped attending", "NE")),
              _c2k_rows("CDE"),
              _by_age_2000("ABANESCO", _NOT_ATTENDING_AGES_2000, (0, tuple(range(1, 9)), 9),
                           universe=lambda p: _code(p, "ASISTEN").eq(2)),
              tolerance={0: 0.07},
              note="Never attended = `ABANESCO` 0, stopped = 1–8 (its causes), not specified "
                   "9; sex T only (7l). The nation's 7–9 split is 0.06 off: Chiapas's 0.34 (its "
                   "weights) on a small base."),
    ]
    return tuple(out)


# EIC 2015 persons: population, birth registration, fertility, child mortality, unpaid
# work (7j) ------------------------------------------------------------------------------

def _age_group(p: pd.DataFrame, label: str) -> pd.Series:
    """An age group of INEGI's tabulados: «Total», «NN-MM años», «NN años y más», «No
    especificado» (``EDAD`` 999)."""
    age = _age(p)
    if label == "Total":
        return pd.Series(True, index=p.index)
    if label == "No especificado":
        return age.eq(999)
    if m := re.fullmatch(r"(\d+)-(\d+) años", label):
        return age.between(int(m.group(1)), int(m.group(2)))
    if m := re.fullmatch(r"(\d+) años y más", label):
        return age.between(int(m.group(1)), 130)
    raise ValueError(f"age group {label!r}")


_QUIN_2015 = ("Total", *(f"{a:02d}-{a + 4:02d} años" for a in range(0, 75, 5)), "75 años y más",
              "No especificado")
_REGISTRATION_AGES = ("Total", "00-05 años", "06-14 años", "15-64 años", "65 años y más",
                      "No especificado")
_WOMEN_AGES = ("Total", "12-14 años", *(f"{a}-{a + 4} años" for a in range(15, 75, 5)),
               "75 años y más")
_UNPAID_AGES = ("Total", "12-14 años", "15-17 años", "18-24 años", "25-34 años", "35-44 años",
                "45-54 años", "55-64 años", "65 años y más")
_MARITAL_2015 = (("Total", None), ("Soltera", "soltero"), ("Unida o casada", "casado"),
                 ("Separada, divorciada o viuda", "separado"),
                 ("No especificado", "No especificado"))
_UNPAID = ("disabled persons", "sick persons", "healthy children under 6",
           "healthy children 6-14", "persons 60+", "cooking", "cleaning, laundry",
           "shopping, errands")


def _by_dims(estimator: str, sheet: str, groups: tuple[str, ...], pick: Callable[[list], list],
             sexed: bool = False, rows: tuple[str, ...] | None = None):
    """EIC 2015 tabulados with rows (state[, sex][, a category], an age group): per (state,
    sex), ``pick`` of each (category,) age group's values, the categories ``rows`` (their
    names as published) outer, the age ``groups`` inner (7j). A row INEGI leaves out is
    nobody: zeros (7p: Censo 2020's 06-04 has no unspecified age in five states)."""
    def read(wb):
        out, width = {}, 0
        for key, values in _estimates(_sheet(wb, sheet), estimator).items():
            state, rest = key[0], list(key[1:])
            sex = rest.pop(0) if sexed else "T"
            out.setdefault((state, sex), {})[tuple(rest)] = values
            width = len(values)
        return {k: [x for r in (rows or (None,)) for g in groups
                    for x in pick(v.get((g,) if r is None else (r, g), [0.0] * width))]
                for k, v in out.items()}
    return read


def _quin_group(p: pd.DataFrame, label: str) -> pd.Series:
    """An age group of the tabulados as ``EDAD_QUIN`` categories (7a): «NN-MM años» its own,
    «NN años y más» every category from NN on, «No especificado», «Total»."""
    quin = _cat(p, "EDAD_QUIN")
    if label == "Total":
        return pd.Series(True, index=p.index)
    if label == "No especificado":
        return quin.eq("No especificado")
    if m := re.fullmatch(r"(\d+)-(\d+) años", label):
        return quin.eq(f"{int(m.group(1))}-{int(m.group(2))}")
    if m := re.fullmatch(r"(\d+) años y más", label):
        lows = quin.astype(str).str.extract(r"^(\d+)-")[0].astype(float)
        return lows.ge(int(m.group(1)))
    raise ValueError(f"age group {label!r}")


def _population(groups: tuple[str, ...]):
    """EIC 2015 01-02, Censo 2010 01_02A: every age group (``EDAD_QUIN``) by sex in columns:
    total, men, women."""
    def ours(p):
        sex = p["SEXO"].astype(str)
        out = []
        for label in groups:
            g = _quin_group(p, label)
            out += [(g, None), (g & sex.eq("1"), None), (g & sex.eq("3"), None)]
        return out
    return ours


def _registration_2015(p):
    """01-03: by age group, the registration (``ACTA_NAC``): registered or not (1–2), then
    registered (1) and not (2) of those, registered abroad (3), not specified (9)."""
    acta = _code(p, "ACTA_NAC")
    out = []
    for label in _REGISTRATION_AGES:
        g = _age_group(p, label)
        out += _counts_of(g, g & acta.isin([1, 2]), g & acta.eq(1), g & acta.eq(2),
                          g & acta.eq(3), g & acta.eq(9))
    return out


def _women_2015(p) -> tuple[pd.Series, pd.Series]:
    """The women of 12 and more (a specified age) who gave their children born alive
    (``HIJOS_NAC_VIVOS`` below 98: not the topic omitted, not specified), and the number."""
    born = _code(p, "HIJOS_NAC_VIVOS")
    return p["SEXO"].astype(str).eq("3") & _age(p).between(12, 130) & born.lt(98), born


def _fertility_2015(average: bool):
    """02-02: those women by marital status (``SITUA_CONYUGAL_CAT``) and age group: their
    number, or (``average``) their children born alive per woman."""
    def ours(p):
        women, born = _women_2015(p)
        marital = _cat(p, "SITUA_CONYUGAL_CAT")
        out = []
        for _, cat in _MARITAL_2015:
            m = women if cat is None else women & marital.eq(cat)
            for label in _WOMEN_AGES:
                g = m & _age_group(p, label)
                out.append((Weighted(g, born), g) if average else (g, None))
        return out
    return ours


def _child_deaths_2015(p):
    """03-01: the children who died (``HIJOS_FALLECIDOS``) as % of those born alive, of the
    women who gave both, by the mother's age group."""
    women, born = _women_2015(p)
    died = _code(p, "HIJOS_FALLECIDOS")
    women &= died.lt(99)
    return [(Weighted(women & _age_group(p, label), died),
             Weighted(women & _age_group(p, label), born)) for label in _WOMEN_AGES]


def _unpaid_hours(p) -> pd.DataFrame:
    """The weekly hours of each unpaid activity (``ACTI_SIN_PAGO1``–``8``; 0 = none, 999 =
    not specified)."""
    return pd.DataFrame({i: _code(p, f"ACTI_SIN_PAGO{i}") for i in range(1, 9)})


def _unpaid_2015(p):
    """09-02: the 12+ (a specified age) by age group: who do unpaid work (some activity with
    hours), then each activity of those; who do none (no hours given, not every activity
    unspecified), not specified (all eight 999)."""
    hours = _unpaid_hours(p)
    given = hours.gt(0) & hours.lt(999)
    does, unknown = given.any(axis=1), hours.eq(999).all(axis=1)
    out = []
    for label in _UNPAID_AGES:
        g = _age(p).between(12, 130) & _age_group(p, label)
        out += _counts_of(g, g & does, *(g & does & given[i] for i in range(1, 9)),
                          g & ~does & ~unknown, g & unknown)
    return out


def _unpaid_hours_2015(p):
    """09-03: the weekly hours of who do unpaid work — all their activities' given hours —,
    then each activity's of who do it, by age group."""
    hours = _unpaid_hours(p)
    known = hours.where(hours.lt(999))
    does = (known.gt(0)).any(axis=1)
    out = []
    for label in _UNPAID_AGES:
        g = _age(p).between(12, 130) & _age_group(p, label)
        out.append((Weighted(g & does, known.sum(axis=1)), g & does))
        out += [(Weighted(g & known[i].gt(0), known[i]), g & known[i].gt(0)) for i in range(1, 9)]
    return out


def _person_checks_2015() -> tuple[Check, ...]:
    """The EIC 2015 person tabulados by state not read before 7j."""
    exact = {None: 1e-4}                 # averages and shares: INEGI's 13 decimals
    return (
        Check("2015", "01-02", "Population by five-year age (`EDAD_QUIN`) and sex",
              "01_poblacion.xls", "personas",
              tuple(f"{g}: {s}" for g in _QUIN_2015 for s in ("total", "men", "women")),
              _by_dims("Valor", "02", _QUIN_2015, lambda v: v[:3]), _population(_QUIN_2015),
              unit="persons", sheet="02", note="The sexes are columns: sex T only (7j)."),
        Check("2015", "01-03", "Birth registration (`ACTA_NAC`) by age", "01_poblacion.xls",
              "personas",
              tuple(f"{g}: {c}" for g in _REGISTRATION_AGES for c in (
                  "population", "registered or not", "registered", "not registered",
                  "registered abroad", "NE")),
              _by_dims("Valor", "03", _REGISTRATION_AGES,
                       lambda v: _counts(v[0], v[1:], [0, 1, 1, 0, 0]), sexed=True),
              _registration_2015, unit="persons", sheet="03"),
        Check("2015", "02-02a", "Women 12+ who gave their children born alive, by marital "
              "status (`SITUA_CONYUGAL_CAT`) and age", "02_fecundidad.xls", "personas",
              tuple(f"{m}: {g}" for m, _ in _MARITAL_2015 for g in _WOMEN_AGES),
              _by_dims("Valor", "02", _WOMEN_AGES, lambda v: v[:1],
                       rows=tuple(m for m, _ in _MARITAL_2015)),
              _fertility_2015(False), unit="persons", sheet="02",
              note="The women of a specified age whose `HIJOS_NAC_VIVOS` is given (not 98, "
                   "topic omitted, nor 99); the published rows are women (7j)."),
        Check("2015", "02-02b", "Children born alive per woman (`HIJOS_NAC_VIVOS`), by "
              "marital status and age", "02_fecundidad.xls", "personas",
              tuple(f"{m}: {g}" for m, _ in _MARITAL_2015 for g in _WOMEN_AGES),
              _by_dims("Valor", "02", _WOMEN_AGES, lambda v: v[1:2],
                       rows=tuple(m for m, _ in _MARITAL_2015)),
              _fertility_2015(True), unit="average", sheet="02", tolerance=exact),
        Check("2015", "03-01", "Children who died (`HIJOS_FALLECIDOS`), % of those born "
              "alive, by the mother's age", "03_mortalidad.xls", "personas", _WOMEN_AGES,
              _by_dims("Valor", "01", _WOMEN_AGES, lambda v: v[:1]), _child_deaths_2015,
              sheet="01", tolerance=exact,
              note="Of the women of a specified age who gave both counts (7j)."),
        Check("2015", "09-02", "Unpaid work of the 12+ (`ACTI_SIN_PAGO1`–8) by age",
              "09_trabajo_no_remunerado.xls", "personas",
              tuple(f"{g}: {c}" for g in _UNPAID_AGES for c in (
                  "population 12+", "do unpaid work", *_UNPAID, "do none", "NE")),
              _by_dims("Valor", "02", _UNPAID_AGES,
                       lambda v: _counts(v[0], v[1:], [0, *[1] * 8, 0, 0]), sexed=True),
              _unpaid_2015, unit="persons", sheet="02",
              note="Unpaid work = an activity with hours (1–998); none = no hours given and "
                   "not every activity unspecified; not specified = all eight 999 (7j)."),
        Check("2015", "09-03", "Weekly hours of unpaid work by activity and age",
              "09_trabajo_no_remunerado.xls", "personas",
              tuple(f"{g}: {c}" for g in _UNPAID_AGES for c in ("all activities", *_UNPAID)),
              _by_dims("Valor", "03", _UNPAID_AGES, lambda v: v[:9], sexed=True),
              _unpaid_hours_2015, unit="average", sheet="03", tolerance=exact,
              note="All activities: each one's given hours summed, of who do any (7j)."),
    )


# Fertility and infant mortality: the last child born alive (7o) -------------------------

# Each edition's items: children born alive, the last child's birth year, survival, age at
# death in years (blank below one year: days, months, «less than a month/year», unspecified)
_LAST_CHILD = {"2010": ("NUMHIJ", "FECNACA", "SOBREVI", "EDAMORA"),
               "2015": ("HIJOS_NAC_VIVOS", "FECHA_NAC_A", "SOBREVIVENCIA", "EDAD_MORIR_A"),
               "2020": ("HIJOS_NAC_VIVOS", "FECHA_NAC_A", "SOBREVIVENCIA", "EDAD_MORIR_A")}
_FERTILE_AGES = tuple((f"{a}-{a + 4} años", a, a + 4) for a in range(15, 50, 5))
_MOTHER_AGES = (("Total", 12, 49), ("12-19 años", 12, 19), ("20-34 años", 20, 34),
                ("35-49 años", 35, 49))
_NATION_NAME = "Estados Unidos Mexicanos"
_SIZES = {"2010": ("Menos de 2 500 habitantes", "2 500-14 999 habitantes",
                   "15 000-99 999 habitantes", "100 000 y más habitantes"),
          "2015": ("Menos de 2 500 habitantes", "2 500-14 999 habitantes",
                   "15 000-49 999 habitantes", "50 000-99 999 habitantes",
                   "100 000 y más habitantes"),
          "2020": ("1-2 499 habitantes", "2 500-14 999 habitantes", "15 000-49 999 habitantes",
                   "50 000-99 999 habitantes", "100 000 y más habitantes")}
_RATE_CELLS = (*(g.removesuffix(" años") for g, *_ in _FERTILE_AGES), "TGF")


def _size(p: pd.DataFrame) -> pd.Series:
    """The locality size code (2015/2020 ``TAMLOC`` 1–5; 2010 ``TAM_LOC`` 01–04, state 15's
    ``tam_loc``) as numbers."""
    return _code(p, next(c for c in ("TAMLOC", "TAM_LOC", "tam_loc") if c in p))


def _sizes(p: pd.DataFrame, period: str) -> list[pd.Series]:
    """The nation, then each locality size in the order of :data:`_SIZES`."""
    size = _size(p)
    return [pd.Series(True, index=p.index), *(size.eq(i) for i in range(1, len(_SIZES[period]) + 1))]


def _fertility_rates(period: str, by_size: bool = False):
    """02_02A / 02-04 / 02-02 (by state) and 02_01A / 02-03 / 02-01 (``by_size``, the
    nation): births of the year before the census per 1,000 women of each five-year age (at
    the census) — the women whose last child born alive was born that year, over the women
    whose fertility is known: not the topic omitted (children born alive 98) nor the last
    child's year unspecified (9999); an unspecified number of children (99) counts."""
    born, year = _LAST_CHILD[period][:2]

    def ours(p):
        women = p["SEXO"].astype(str).eq("3")
        last, age = _code(p, year), _age(p)
        mothers = women & last.eq(int(period) - 1)
        known = women & ~_code(p, born).eq(98) & ~last.eq(9999)
        groups = [age.between(lo, hi) for _, lo, hi in _FERTILE_AGES]
        out = []
        for s in (_sizes(p, period) if by_size else [pd.Series(True, index=p.index)]):
            out += [(mothers & s & g, known & s & g) for g in groups]
        return out
    return ours


def _with_tgf(values: list[float]) -> list[float]:
    """Each block of seven fertility rates followed by its Tasa Global de Fecundidad, five
    times their sum per woman."""
    n = len(_FERTILE_AGES)
    return [x for i in range(0, len(values), n)
            for x in (*values[i:i + n], 5 * sum(values[i:i + n]) / 1000)]


def _infant_mortality(period: str):
    """03_01A / 03-02 / 03-01: the last children born alive in the year before the census
    who died under one year, per 1,000 of them, by locality size and the mother's age at the
    census («Total» = 12–49). Censo 2020: the age at death in days given (``EDAD_MORIR_TD``
    0–364) — INEGI's own count, exact; 2010/2015: every death not aged in years (the unknown
    ages included) — INEGI's estimate is no ratio of the sample's records (STEP_7o.md)."""
    _, year, alive, years = _LAST_CHILD[period]

    def ours(p):
        born = p["SEXO"].astype(str).eq("3") & _code(p, year).eq(int(period) - 1)
        dead = born & _code(p, alive).eq(3)
        died = (dead & _code(p, "EDAD_MORIR_TD").between(0, 364) if period == "2020"
                else dead & _code(p, years).isna())
        age = _age(p)
        groups = [age.between(lo, hi) for _, lo, hi in _MOTHER_AGES]
        out = []
        for s in _sizes(p, period):
            out += [(died & s & g, born & s & g) for g in groups]
        return out
    return ours


def _rate_checks() -> tuple[Check, ...]:
    """The fertility rates and the infant mortality of Censo 2010, the EIC 2015 and Censo
    2020 (7o)."""
    exact = {None: 1e-4}               # per 1,000; INEGI publishes 6 decimals (2020) or more
    files = {"2010": ("02_02A_ESTATAL.xls", None, "02_01A_ESTATAL.xls", None,
                      "03_01A_ESTATAL.xls", None, "Parámetro"),
             "2015": ("02_fecundidad.xls", "04", "02_fecundidad.xls", "03",
                      "03_mortalidad.xls", "02", "Valor"),
             "2020": ("cpv2020_a_eum_02_fecundidad.xlsx", "02",
                      "cpv2020_a_eum_02_fecundidad.xlsx", "01",
                      "cpv2020_a_eum_03_mortalidad.xlsx", "01", "Valor")}
    keys = {"2010": ("02_02A", "02_01A", "03_01A"), "2015": ("02-04", "02-03", "03-02"),
            "2020": ("02-02", "02-01", "03-01")}
    # 2010/2015's infant mortality: the largest |Δ| over its cells (the nation's is 0.09/0.17)
    loose = {"2010": {None: 1.0}, "2015": {None: 1.8}, "2020": exact}
    out = []
    for period, (state_src, state_sheet, size_src, size_sheet, tmi_src, tmi_sheet,
                 est) in files.items():
        state_key, size_key, tmi_key = keys[period]
        rows = (_NATION_NAME, *_SIZES[period])
        out += [
            Check(period, state_key, "Fertility rates by five-year age and TGF (the last "
                  "child born alive)", state_src, "personas", _RATE_CELLS,
                  _wide(est, lambda v: v[:8], sheet=state_sheet, dims=lambda k: (k[0], "T")),
                  _fertility_rates(period), unit="rate", sheet=state_sheet, tolerance=exact,
                  combine=_with_tgf,
                  note="Women whose last child born alive was born the year before, per 1,000 "
                       "women of the age (at the census) whose fertility is known (not 98, "
                       "topic omitted; the last child's year not 9999); TGF = 5 × Σ rates "
                       "/ 1,000 (7o)."),
            Check(period, size_key, "Fertility rates and TGF by locality size", size_src,
                  "personas", tuple(f"{r}: {c}" for r in rows for c in _RATE_CELLS),
                  _national(est, tuple((r,) for r in rows), sheet=size_sheet),
                  _fertility_rates(period, by_size=True), unit="rate", sheet=size_sheet,
                  tolerance=exact, combine=_with_tgf, note="National (7o)."),
            Check(period, tmi_key, "Infant mortality by locality size and the mother's age",
                  tmi_src, "personas",
                  tuple(f"{r}: {g}" for r in rows for g, *_ in _MOTHER_AGES),
                  _national(est, tuple((r, g) for r in rows for g, *_ in _MOTHER_AGES),
                            sheet=tmi_sheet),
                  _infant_mortality(period), unit="rate", sheet=tmi_sheet,
                  tolerance=loose[period],
                  note=("Deaths aged 0–364 days (`EDAD_MORIR_TD`) of the last children born in "
                        "2019, per 1,000 of them; the mother's age at the census, «Total» = "
                        "12–49 (7o)." if period == "2020" else
                        "Not reproducible from the sample (STEP_7o.md): INEGI's cells are no "
                        "ratio of its records' weights (a «Total» is not the sum of its age "
                        "groups). Ours: every death not aged in years (unknown ages included) "
                        "of the last children born the year before, per 1,000 of them; "
                        "tolerance = the largest gap (7o).")),
        ]
    return tuple(out)


_ECO_2020 = "cpv2020_a_eum_08_caracteristicas_economicas.xlsx"
_MOV_2020 = "cpv2020_a_eum_10_movilidad_cotidiana.xlsx"

CHECKS: tuple[Check, ...] = (
    Check("2000", "MI01", "Birthplace (`ENT_PAIS_NAC_CAT`), % of all", "C2KMI01.xls",
          "personas", ("this entity", "another entity or abroad", "not specified"),
          _c2k("CDE"), _mi01),
    Check("2000", "MI03", "Residence in 1995 (`ENT_PAIS_RES_CAT`), % of the 5+", "C2KMI03.xls",
          "personas", ("this entity", "another entity or abroad", "not specified"),
          _c2k("CDE"), _mi03),
    Check("2000", "RE02", "Religion (`RELIGION_CAT`), % of the 5+", "C2KRE02.xls", "personas",
          ("católica", "protestant, evangelical and other biblical", "other", "none",
           "not specified"),
          _c2k("CDEFGH", lambda v: [v[0], v[1] + v[2], *v[3:]]), _re02),
    Check("2000", "SS04", "Health coverage (`DHSERSAL_*`)", "C2KSS04.xls", "personas",
          ("not covered (% of all)", "covered (% of all)", "IMSS (% of covered)",
           "ISSSTE", "PEMEX, Defensa, Marina", "other institution", "not specified (% of all)"),
          _c2k("CDEFGHI"), _ss04),
    Check("2000", "EC02", "Marital status (`SITUA_CONYUGAL_CAT`), % of the 12+", "C2KEC02.xls",
          "personas", ("single", "married or in a free union", "separated, divorced, widowed",
                       "not specified"),
          _c2k("CDEFG", lambda v: [v[0], v[1] + v[2], v[3], v[4]]), _ec02),
    Check("2000", "EM01", "Activity (`CONACT_CAT`)", "C2KEM01.xls", "personas",
          ("PEA (% of the 12+)", "employed (% of PEA)", "unemployed (% of PEA)",
           "inactive (% of the 12+)", "not specified (% of the 12+)"),
          _c2k("CDEFG"), _em01),
    Check("2000", "EM05", "Sector of the employed (`ACTIVIDADES_C_COARSE`)", "C2KEM05.xls",
          "personas", tuple(n for n, _ in _SECTORS_2000),
          lambda wb: _c2k_sectors(_sheet(wb, None)), _em05),
    Check("2000", "EM07", "Hours worked by the employed (`HORTRA_CAT`)", "C2KEM07.xls",
          "personas", ("none or up to 40", "41-48", "49-56", "more than 56", "not specified"),
          _c2k("CDEFGHIJKLM", lambda v: [sum(v[:6]), v[6], v[7], v[8] + v[9], v[10]]), _em07),
    Check("2000", "ED08", "Education of the 12+ (`EDUC_INEGI`)", "C2KED08.xls", "personas",
          ("sin instrucción", "primaria incompleta or grade not specified", "primaria completa",
           "secundaria", "técnica after primaria", "media superior and superior",
           "not specified"),
          _c2k("CDEFGHIJ", lambda v: [v[0], v[1] + v[3], v[2], v[4], v[5], v[6], v[7]]), _ed08,
          note="Técnica after primaria is its own column here, as `EDUC_INEGI`'s "
               "«Técnica_primaria» (6k)."),
    Check("2000", "ED11", "Education of the 18+ (`EDUC_INEGI_DET`)", "C2KED11.xls",
          "personas", ("without media superior", "media superior", "superior",
                       "not specified"),
          _c2k("CDEFGH", lambda v: [v[0], v[1] + v[2] + v[3], v[4], v[5]]), _ed11,
          note="Media superior = técnica after secundaria, preparatoria and normal básica "
               "(its columns D–F); superior holds the posgrado (6w)."),
    Check("2000", "ED10", "Education of the 15+ (`EDUC_INEGI_DET`)", "C2KED10.xls",
          "personas", ("sin instrucción", "primaria incompleta or grade not specified",
                       "primaria completa", "secundaria and técnica after primaria",
                       "media superior", "superior", "not specified"),
          _c2k("CDEFGHIJKL", lambda v: [v[0], v[1] + v[3], v[2], v[4] + v[5] + v[6],
                                        v[7], v[8], v[9]]), _ed10,
          note="INEGI's 2000 levels put técnica after primaria with secundaria (its footnote "
               "1), so the comparison groups it there."),
    Check("2000", "VI06", "Bedrooms (`CUADORM_CAT`), % of the dwellings", "C2KVI06.xls",
          "viviendas", ("one", "two or more", "not specified"),
          _c2k("CDEFGHI", lambda v: [v[0], sum(v[1:6]), v[6]], level="dwellings"), _vi06),
    Check("2000", "VI10", "Drainage (`DRENAJE_CAT`), % of the dwellings", "C2KVI10.xls",
          "viviendas", ("has drainage", "has none", "not specified"),
          _c2k("CHI", level="dwellings"), _vi10),
    Check("2000", "HO04a", "Households by the head's sex (`JEFE_SEXO`, 6s), %", "C2KHO04.xls",
          "hogares", ("male head", "female head"), _c2k("CD"), _head_sex("JEFE_SEXO")),
    Check("2000", "HO04b", "Population in households by the head's sex (`HOGJEF_SEXO`), %",
          "C2KHO04.xls", "personas", ("male head", "female head"), _c2k("FG"),
          _head_sex("HOGJEF_SEXO"), note="The head's sex is the breakdown: both sexes only."),
    Check("2000", "EM08", "Income of the employed in minimum wages (`INGTRMEN_SM`)",
          "C2KEM08.xls", "personas",
          ("no income", "below 1", "1 to 2", "above 2, below 3", "3 to 5", "above 5 to 10",
           "above 10", "not specified"),
          _c2k("CDEFGHIJ"), _em08,
          note="The monthly minimum wage of the municipality's area in February 2000 (its FD's "
               "annex: A 1,137, B 1,053, C 981 = the daily wage × 30); 7c."),
    Check("2000", "EM10", "Place of work by municipality (`LUGAR_TRAB`)", "C2KEM10.xls",
          "personas", _PLACE_CELLS, _c2k("CDEFGH"), _place_shares("LUGAR_TRAB", _employed_2000),
          tolerance={7: 1.2},
          note="Both sexes only; the municipality's cells are % of the same entity. "
               "`LTRABPAI_C` 999 is «No especificado» (7c). Chiapas' same/another municipality "
               "split is 1.1 points off (its sample's weights)."),
    Check("2000", "MI04", "Residence in 1995 by municipality (`LUGAR_RES_5A`), % of the 5+",
          "C2KMI04.xls", "personas",
          ("same entity", "same municipality", "another municipality",
           "municipality not specified", "another entity", "abroad", "not specified"),
          _c2k("CDEFGHI"), _place_shares("LUGAR_RES_5A", _five, abroad_apart=True),
          tolerance={_NATION: 0.1, 7: 0.85, 11: 0.1, 20: 0.25, 30: 1.05, 32: 0.96},
          note="The person's answer (`MUN95OTR_C` against the current municipality; 7c, "
               "user's choice). INEGI counts more municipal migrants in Guanajuato, Oaxaca, "
               "Veracruz and Zacatecas (0.08–1.04 points of the same entity); in Zacatecas "
               "they are the residents of Trancoso (created after 1995) who answered "
               "Trancoso, the other three have no such rule (Campeche's and Sonora's "
               "1996–98 municipalities show none)."),
    Check("2000", "EM02", "Inactive 12+ by kind (`CONACT` 40–80)", "C2KEM02.xls", "personas",
          ("students", "home duties", "retired or pensioned", "unable to work", "other"),
          _c2k("CDEFG"), _em02, note="Raw `CONACT` (7d)."),
    Check("2000", "EM03", "Participation rates by age (`CONACT_CAT`)", "C2KEM03.xls",
          "personas", ("12+", *(f"{a}-{b}" if b < 130 else f"{a}+" for a, b in _AGES_EM03)),
          lambda wb: _c2k_sectors(_sheet(wb, None), total=True), _em03,
          note="The PEA as % of every person of the age, the unspecified activity included "
               "(7d)."),
    Check("2000", "EM04", "Employed by occupation (`OCUACTIV_C`'s CMO group)", "C2KEM04.xls",
          "personas", tuple(n for n, _ in _CMO_GROUPS),
          lambda wb: _c2k_sectors(_sheet(wb, None)), _em04,
          note="The CMO's 19 principal groups = the first two digits of the raw code (7d); "
               "no SINCO bridge."),
    Check("2000", "EM06", "Employed by position at work (`SITTRA`)", "C2KEM06.xls",
          "personas", ("employee", "day labourer", "employer", "own account",
                       "unpaid family worker", "not specified"),
          _c2k("CDEFGH"), _em06),
    Check("2000", "EM09", "Wage earners by benefit (`VACACION` … `SARAFORE`)", "C2KEM09.xls",
          "personas", ("paid holidays", "Christmas bonus", "profit sharing", "health care",
                       "retirement savings", "none"),
          _c2k("CDEFGH"), _em09,
          note="Wage earners = employees and day labourers (`SITTRA` 1, 2); «none» = every "
               "benefit answered «no» (7d)."),
    Check("2000", "EM11", "Complementary rates (TDA, TOPD2, TIID), % of the PEA", "C2KEM11.xls",
          "personas", ("open unemployment", "part-time and unemployment",
                       "income below the minimum wage and unemployment"),
          _c2k_sex_columns({"T": "BEH", "H": "CFI", "M": "DGJ"}), _em11,
          note="TOPD2: worked 1–34 hours in the reference week (`HORTRA`), not who had a job "
               "but did not work (`CONACT` 20); TIID: `INGTRMEN_SM` below one minimum wage, "
               "those without income left out (7d)."),
    Check("2000", "MI02", "Lifetime immigrants and emigrants by state of birth (`LNACEDO_C`)",
          "C2KMI02.xls", "personas", ("immigrants", "emigrants"), _c2k("BC"),
          _flows("LNACEDO_C", lambda p: pd.Series(True, index=p.index)), by_origin=True,
          note="Both % of the residents born in a specified state (born abroad or not "
               "specified left out); the emigrants count in their birth state (7d)."),
    Check("2000", "MI05", "Immigrants and emigrants since 1995 (`RES95EDO_C`), the 5+",
          "C2KMI05.xls", "personas", ("immigrants", "emigrants"), _c2k("BC"),
          _flows("RES95EDO_C", _five), by_origin=True,
          note="Both % of the 5+ who lived in a specified state in 1995; the emigrants count "
               "in their 1995 state (7d)."),
    Check("2000", "MI06", "Migrants 5+ by cause (`CAUEMI`)", "C2KMI06.xls", "personas",
          ("work search", "join the family", "job transfer", "study", "marriage or union",
           "health, violence or insecurity", "other", "not specified"),
          _c2k("CDEFGHIJ"), _mi06,
          note="Migrants: in 1995 in another state or country (`ENT_PAIS_RES_CAT`; 7d)."),
    Check("2000", "MI07", "International migrants by movement and age at emigrating "
          "(`migrantes`), nation", "C2KMI07.xls", "migrantes",
          tuple(f"{g}: {mv}" for g in ("all", *(f"{a}-{b}" if b < 130 else (
              "50+" if a == 50 else "age not specified") for a, b in _AGES_MI07))
              for mv in _MOVEMENTS),
          _c2k_national("CDE"), _mi07,
          note="Movement by `MPAIRES_C` (700 = Mexico: returned; 999 not specified; else "
               "abroad), age at emigrating `MEDAD` (7d)."),
    Check("2000", "MI08", "International migrants by age at emigrating (`migrantes`), % of "
          "each movement, nation", "C2KMI08.xls", "migrantes",
          tuple(f"{g}: % of {u}" for g in (*(f"{a}-{b}" if b < 130 else (
              "50+" if a == 50 else "age not specified") for a, b in _AGES_MI07),)
              for u in ("all", *_MOVEMENTS)),
          _c2k_national("BCDE", first=False), _mi08, note="7d."),
    Check("2000", "MI09", "International migrants by movement (`migrantes`), state of "
          "residence", "C2KMI09.xls", "migrantes", _MOVEMENTS, _c2k_states("DEF"), _mi09,
          note="Both sexes only; the share of the resident population (column C) needs the "
               "person file and is not compared (7d)."),
    Check("2000", "MI10", "International migrants by sex, state left (`MLUGORI_C`)",
          "C2KMI10.xls", "migrantes", ("men", "women"), _c2k_states("CD"),
          _by_origin(lambda m: [m["MSEXO"].eq("1"), m["MSEXO"].eq("2")]), by_origin=True,
          note="By the state the migrants left; state 99 = not specified (7d)."),
    Check("2000", "MI11", "International migrants by age at emigrating, state left",
          "C2KMI11.xls", "migrantes",
          ("0-14", "15-24", "25-34", "35-49", "50+", "age not specified"), _c2k_states("CDEFGH"),
          _by_origin(lambda m: _ages(m, _AGES_MI11)), by_origin=True, tolerance={7: 0.7},
          note="Chiapas' 15–24 share is 0.68 points under INEGI's: 1,139 emigrant records, its "
               "sample's weights (unweighted 57.42, weighted 53.75, INEGI 54.43; 7d)."),
    Check("2000", "MI12", "International migrants by destination (`MPDESOTR_C`), state left",
          "C2KMI12.xls", "migrantes", ("United States", "rest of the world", "not specified"),
          _c2k_states("CDE"), _by_origin(_destination), by_origin=True,
          note="C2KMI13 (each state's share of each destination) is the same counts over the "
               "national totals: not compared (7d)."),
    Check("2010", "04_02A", "Residence in 2005 by municipality (`LUGAR_RES_5A`), the 5+",
          "04_02A_ESTATAL.xls", "personas", ("population 5+", *_PLACE_CELLS),
          _wide("Parámetro", _place_published), _place("LUGAR_RES_5A", _five), unit="persons",
          note="The entity not specified (`RES05EDO_C` 999) is «No especificado», as INEGI's "
               "(the legacy `ENT_PAIS_RES_CAT`: `OtraEnt`); 7b."),
    Check("2010", "08_15A", "Place of work by municipality (`LUGAR_TRAB`)",
          "08_15A_ESTATAL.xls", "personas", ("employed", *_PLACE_CELLS),
          _wide("Parámetro", _place_published, dims=_total_row), _place("LUGAR_TRAB", _employed),
          unit="persons",
          note="`LTRABPAI_C` holds the entity and country catalogs; its 999 (the entity's «no "
               "especificada») and 900 (topic omitted) are «No especificado» (7b)."),
    Check("2010", "08_10A", "Income of the employed in minimum wages (`INGTRMEN_SM`)",
          "08_10A_ESTATAL.xls", "personas", ("employed", *_SM_CELLS),
          _income_sm_published("Parámetro"), _income_sm, unit="persons",
          tolerance={_NATION: 525.5, 15: 525.5},
          note="INEGI's catalog `TC_TABLA_SALARIOS_MUN_2010` (A 1,723.80, B 1,675.20, "
               "C 1,634.10; 7c). Exact but in the State of México, up to 525 persons (0.012 "
               "points) under INEGI's lower groups, which no change of a municipality's (or "
               "two's) area explains."),
    Check("2010", "08_02A", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          "08_02A_ESTATAL.xls", "personas", _DIVISIONS,
          _long("Parámetro", _DIVISIONS), _occupation, unit="persons"),
    Check("2010", "08_03A", "Employed by sector (`ACTIVIDADES_C_COARSE`)", "08_03A_ESTATAL.xls",
          "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _long("Parámetro", tuple(n for n, _ in _SECTOR_GROUPS)), _sector, unit="persons"),
    Check("2010", "06_01A", "Limitation in activity (`LIM_ACTIVIDAD`), nation only",
          "06_01A_ESTATAL.xls", "personas",
          ("population", "with a limitation", "without", "not specified"),
          _wide("Parámetro", lambda v: _counts(v[0], [v[1], v[8], v[9]])), _limitation,
          unit="persons",
          note="Published by locality size: the national row only (all 32 states needed)."),
    Check("2010", "12_01A", "Parents in the dwelling (`MADRE_EN_VIVIENDA`, "
          "`PADRE_EN_VIVIENDA`), nation only", "12_01A_ESTATAL.xls", "personas",
          ("population", "both", "only the father", "only the mother", "neither",
           "not specified"),
          _wide("Parámetro", lambda v: _counts(v[0], v[1:]), dims=_total_row), _parents,
          unit="persons",
          note="Published by locality size: the national row only (all 32 states needed)."),
    Check("2015", "04-02", "Birthplace (`ENT_PAIS_NAC_INEGI`)", "04_migracion.xls", "personas",
          ("population", "this entity", "another entity", "abroad", "not specified"),
          _wide("Valor", lambda v: (c := _counts(v[0], v[1:]))[:3] + [c[3] + c[4], c[5]],
                sheet="02"),
          _birthplace_2015, unit="persons", sheet="02",
          note="On `ENT_PAIS_NAC_INEGI`: the entity not specified (997) is «No especificado», "
               "as INEGI's (the legacy `ENT_PAIS_NAC_CAT`: `OtraEnt`)."),
    Check("2015", "04-05", "Residence in 2010 by municipality (`LUGAR_RES_5A`), the 5+",
          "04_migracion.xls", "personas", ("population 5+", *_PLACE_CELLS),
          _wide("Valor", _place_published, sheet="05"), _place("LUGAR_RES_5A", _five),
          unit="persons", sheet="05",
          note="The entity not specified (997) is «No especificado» (the legacy "
               "`ENT_PAIS_RES_CAT`: `OtraEnt`); 7b."),
    Check("2015", "10-01", "Place of school by municipality (`LUGAR_ASI`)",
          "10_movilidad_cotidiana.xls", "personas", ("students 3+", *_PLACE_CELLS),
          _wide("Valor", _place_published, sheet="01", dims=_total_row),
          _place("LUGAR_ASI", _students), unit="persons", sheet="01"),
    Check("2015", "10-04", "Place of work by municipality (`LUGAR_TRAB`)",
          "10_movilidad_cotidiana.xls", "personas", ("employed", *_PLACE_CELLS),
          _wide("Valor", _place_published, sheet="04", dims=_total_row),
          _place("LUGAR_TRAB", _employed), unit="persons", sheet="04"),
    Check("2015", "08-02", "Activity of the 12+ (`CONACT_CAT`)",
          "08_caracteristicas_economicas.xls", "personas",
          ("population 12+", "PEA", "employed", "unemployed", "inactive", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:6], [0, 1, 1, 0, 0]), sheet="02",
                dims=lambda k: k[:2] if k[2] == "Total" else None),
          _activity_2015, unit="persons", sheet="02"),
    Check("2015", "08-11", "Income of the employed in minimum wages (`INGTRMEN_SM`)",
          "08_caracteristicas_economicas.xls", "personas", ("employed", *_SM_CELLS),
          _income_sm_published("Valor", "11"), _income_sm, unit="persons", sheet="11",
          note="INEGI's catalog `TC_SALARIO_MUN_2015` as published (A 2,103, B 1,993.5; its "
               "Coacoatzintla in area A, where the DOF has Coatzintla); 7c."),
    Check("2015", "08-06", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          "08_caracteristicas_economicas.xls", "personas", _DIVISIONS,
          _long("Valor", _DIVISIONS, sheet="06"), _occupation, unit="persons", sheet="06"),
    Check("2015", "08-07", "Employed by sector (`ACTIVIDADES_C_COARSE`)",
          "08_caracteristicas_economicas.xls", "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _long("Valor", tuple(n for n, _ in _SECTOR_GROUPS), sheet="07"), _sector,
          unit="persons", sheet="07"),
    Check("2015", "06-11", "Education of the 15+ (`EDUC`)", "06_educacion.xls", "personas",
          ("population 15+", "no schooling (preschool included)", "primaria",
           "secundaria incompleta", "secundaria completa", "media superior",
           "superior (posgrado included)", "not specified"),
          _wide("Valor", _educ_2015_published, sheet="11", dims=_total_row), _educ_2015,
          unit="persons", sheet="11",
          note="Técnica after primaria counts in primaria, in the tabulado as in `EDUC`; "
               "media superior and superior by `EDUC_INEGI_DET` (6w)."),
    Check("2015", "05-04", "Population aged 0–2 in indigenous households (`HOG_IND`)",
          "05_etnicidad.xls", "personas", ("aged 0–2, the head or partner speaks",),
          _indigenous_children_published, _indigenous_children, unit="persons", sheet="04",
          note="Both sexes only; the households whose head or partner speaks an indigenous "
               "language, the EIC 2015's definition (6w)."),
    Check("2015", "07-02", "Health affiliation by institution (`DHSERSAL_*`)",
          "07_servicios_de_salud.xls", "personas",
          ("population", "affiliated", "IMSS", "ISSSTE (federal or state)",
           "PEMEX, Defensa or Marina", "Seguro Popular", "private", "other",
           "not affiliated", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:10], [0, 1, 1, 1, 1, 1, 1, 0, 0]),
                sheet="02", dims=_total_row),
          _affiliation_2015, unit="persons", sheet="02"),
    Check("2015", "10-03", "Commute to school (`MED_TRASLADO_ESC_*`)",
          "10_movilidad_cotidiana.xls", "personas",
          ("students who travel", "bus, taxi", "metro, metrobús", "private vehicle",
           "school bus", "bicycle", "walking", "other", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="03", dims=_total_row),
          _commute_2015("MED_TRASLADO_ESC", "Transporte escolar", 3), unit="persons",
          sheet="03"),
    Check("2015", "10-06", "Commute to work (`MED_TRASLADO_TRAB_*`)",
          "10_movilidad_cotidiana.xls", "personas",
          ("employed who travel", "bus, taxi", "metro, metrobús", "private vehicle",
           "staff transport", "bicycle", "walking", "other", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="06", dims=_total_row),
          _commute_2015("MED_TRASLADO_TRAB", "Transporte de personal", 12), unit="persons",
          sheet="06"),
    Check("2015", "11-02", "Marital status of the 12+ (`SITUA_CONYUGAL_CAT`)",
          "11_situacion_conyugal.xls", "personas",
          ("population 12+", "single", "married or in union", "separated, divorced, widowed",
           "not specified"),
          _wide("Valor", lambda v: (c := _counts(v[0], v[1:]))[:2]
                + [c[2] + c[3], c[4] + c[5] + c[6], c[7]], sheet="02", dims=_total_row),
          _marital, unit="persons", sheet="02"),
    Check("2015", "12-05", "Population in households by the head's sex (`HOGJEF_SEXO`)",
          "12_hogares.xls", "personas", ("population in households", "male head",
                                         "female head"),
          _population_by_head_published, _population_by_head, unit="persons", sheet="05",
          note="The head's sex is the breakdown: both sexes only."),
    Check("2015", "12-05a", "Households by class (`CLASE_HOG`) and type (`TIPOHOG`)",
          "12_hogares.xls", "viviendas",
          ("households", "familiar", "nuclear", "ampliado", "compuesto", "familiar, type not "
           "specified", "no familiar", "unipersonal", "corresidentes", "not specified"),
          _household_class_published("Hogares"), _households_by_class, unit="persons",
          sheet="05", note="One household per dwelling, every dwelling class (7b)."),
    Check("2015", "12-05b", "Population in households by class (`CLASE_HOG`)",
          "12_hogares.xls", "personas",
          ("population in households", "familiar", "no familiar", "not specified"),
          _household_class_published("Población en hogares",
                                     lambda c: [c[0], c[1], c[6], c[9]]),
          _population_by_class, unit="persons", sheet="05",
          note="The household's class is the breakdown: both sexes only (7b)."),
    Check("2015", "14-13", "Dwellings by tenure (`TENENCIA`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "own", "rented", "lent by a relative or another", "other", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="13", dims=lambda k: (k[0], "T")),
          _tenure_2015, unit="persons", sheet="13",
          note="Locales no construidos para habitación, móviles and refugios (`CLAVIVP` 7–9) "
               "left out, as INEGI's dwelling tabulados (7b)."),
    Check("2015", "14-16", "Owned dwellings by deed (`ESCRITURAS_VIV`)", "14_vivienda.xls",
          "viviendas", ("owned dwellings", "in a resident's name", "in a non-resident's name",
                        "no deed", "not known", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="16",
                dims=lambda k: (k[0], "T") if k[1] == "Total" else None),
          _deeds_2015, unit="persons", sheet="16",
          note="The owner's sex is the breakdown: its «Total» rows (7b)."),
    Check("2015", "14-14", "Owned dwellings by their owners' sex and order "
          "(`NUM_DUE_VIV1`/`2` → the person's `SEXO`)", "14_vivienda.xls", "viviendas",
          ("owned dwellings", "only a man", "only a woman", "a man and a woman",
           "a woman and a man", "both of one sex", "not identified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="14", dims=lambda k: (k[0], "T")),
          _owners_2015, unit="persons", sheet="14",
          note="The owner items point at the person rows (`NUMPER`), whose `SEXO` the person "
               "file gives; 99 = the owner not identified (7h)."),
    Check("2015", "14-16s", "Owned dwellings by the owner's sex and deed (`ESCRITURAS_VIV`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(tuple((n, None) for n in ("man", "woman", "not identified")),
                     ("owned", "in a resident's name", "in a non-resident's name", "no deed",
                      "not known", "NE")),
          _stacked(("Hombres", "Mujeres", "Dueño(a) no identificado(a)"),
                   lambda v: _counts(v[0], v[1:]), "16"),
          _deeds_by_owner_2015, unit="persons", sheet="16",
          note="The first owner's sex (7h)."),
    Check("2015", "14-18", "Financing of the owned dwellings bought or built "
          "(`FINANCIAMIENTO_*`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "INFONAVIT, FOVISSSTE or PEMEX", "FONHAPO", "banks",
           "other institution", "a relative or another person", "own resources",
           "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="18",
                dims=lambda k: (k[0], "T")),
          _financing_2015, unit="persons", sheet="18"),
    Check("2015", "14-02a", "Dwellings by class (`CLAVIVP`)", "14_vivienda.xls", "viviendas",
          tuple(n for n, _ in _CLASSES_2015), _stacked(tuple(n for n, _ in _CLASSES_2015),
                                                       lambda v: v[:1], "02"),
          _class_2015, unit="persons", sheet="02",
          note="Every dwelling class: «otro tipo» = cuarto de azotea, local no construido "
               "para habitación, vivienda móvil, refugio (06–09; 7d)."),
    Check("2015", "14-02b", "Occupants by their dwelling's class (`CLAVIVP`, `NUMPERS`)",
          "14_vivienda.xls", "viviendas", tuple(n for n, _ in _CLASSES_2015),
          _stacked(tuple(n for n, _ in _CLASSES_2015), lambda v: v[1:2], "02"),
          _class_2015, unit="persons", sheet="02", weight=_occupants,
          note="The occupants = Σ `FACTOR` × `NUMPERS` of the dwellings (7d)."),
    Check("2015", "14-04", "Dwellings by floor (`PISOS`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "earth", "cement", "tiles, wood or other", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="04", dims=lambda k: (k[0], "T")),
          _item("PISOS", (1, 2, 3, 9)), unit="persons", sheet="04",
          note="Here and below, `CLAVIVP` 7–9 left out, as INEGI's dwelling tabulados (7b)."),
    Check("2015", "14-06", "Dwellings by roof (`TECHOS`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "waste material", "cardboard sheet", "metal sheet", "asbestos sheet",
           "fibre-cement sheet", "palm or straw", "wood or tejamanil", "terrado with beams",
           "tile", "concrete slab", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="06", dims=lambda k: (k[0], "T")),
          _item("TECHOS", (*range(1, 11), 99)), unit="persons", sheet="06"),
    Check("2015", "14-08", "Dwellings by wall (`PAREDES`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "waste material", "cardboard sheet", "asbestos or metal sheet",
           "reed, bamboo or palm", "embarro or bajareque", "wood", "adobe",
           "brick, block, stone or concrete", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="08", dims=lambda k: (k[0], "T")),
          _item("PAREDES", (*range(1, 9), 9)), unit="persons", sheet="08"),
    Check("2015", "14-09", "Dwellings by occupants (`NUMPERS`) and rooms (`TOTCUART`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(_OCCUPANTS_2015, ("dwellings", "1", "2", "3", "4", "5", "6+", "NE")),
          _stacked(tuple(n for n, _ in _OCCUPANTS_2015), lambda v: _counts(v[0], v[1:]), "09"),
          _by_count("TOTCUART", (1, 2, 3, 4, 5, "6+", 99), "NUMPERS", _OCCUPANTS_2015),
          unit="persons", sheet="09"),
    Check("2015", "14-10", "Dwellings by occupants (`NUMPERS`) and bedrooms (`CUADORM`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(_OCCUPANTS_2015, ("dwellings", "1", "2", "3", "4+", "NE")),
          _stacked(tuple(n for n, _ in _OCCUPANTS_2015), lambda v: _counts(v[0], v[1:]), "10"),
          _by_count("CUADORM", (1, 2, 3, "4+", 99), "NUMPERS", _OCCUPANTS_2015),
          unit="persons", sheet="10"),
    Check("2015", "14-11", "Dwellings that cook by fuel and place (`COMBUSTIBLE`, `COCINA`, "
          "`LUGAR_COCINA`)", "14_vivienda.xls", "viviendas",
          _row_cells(_FUELS_2015, ("dwellings", "kitchen", "elsewhere", "corridor", "shed",
                                   "outdoors", "elsewhere, NE", "NE")),
          _stacked(tuple(n for n, _ in _FUELS_2015),
                   lambda v: _counts(v[0], v[1:], [0, 0, 2, 2, 2, 2, 0]), "11"),
          _cooking_2015, unit="persons", sheet="11",
          note="INEGI's dwellings that cook name a place (`LUGAR_COCINA` 1–3) or a fuel "
               "(`COMBUSTIBLE` 1–4): a fuel not specified without a place is left out "
               "(150,929 dwellings); electricity is «otro combustible» (7d)."),
    Check("2015", "14-12", "Dwellings cooking with wood or charcoal by stove (`ESTUFA`), "
          "nation", "14_vivienda.xls", "viviendas",
          ("dwellings", "with a chimney", "without", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="12", dims=lambda k: (k[0], "T")),
          _item("ESTUFA", (1, 3, 9),
                lambda v: _cooks_2015(v) & _code(v, "COMBUSTIBLE").eq(1)),
          unit="persons", sheet="12", note="Published by locality size: the national row."),
    Check("2015", "14-17", "Owned dwellings by rooms and acquisition (`FORMA_ADQUI`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(_ROOMS_2015, ("owned", "bought", "had it built", "built it", "inherited",
                                   "government", "other", "NE")),
          _stacked(tuple(n for n, _ in _ROOMS_2015), lambda v: _counts(v[0], v[1:]), "17"),
          _acquisition_2015, unit="persons", sheet="17"),
    Check("2015", "14-20", "Dwellings by water (`AGUA_ENTUBADA`, `ABA_AGUA_NO_ENTU`)",
          "14_vivienda.xls", "viviendas",
          ("dwellings", "piped", "inside", "in the yard", "carried", "community tap",
           "another dwelling", "pipa", "well", "river, stream or lake", "rain",
           "carried, NE", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 1, 1, 0, 4, 4, 4, 4, 4, 4, 4, 0]),
                sheet="20", dims=lambda k: (k[0], "T")),
          _water_2015, unit="persons", sheet="20"),
    Check("2015", "14-34", "Occupants by water (`AGUA_ENTUBADA`, `ABA_AGUA_NO_ENTU`)",
          "14_vivienda.xls", "viviendas",
          ("occupants", "piped", "inside", "in the yard", "carried", "community tap",
           "another dwelling", "pipa", "well", "river, stream or lake", "rain",
           "carried, NE", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 1, 1, 0, 4, 4, 4, 4, 4, 4, 4, 0]),
                sheet="34", dims=lambda k: (k[0], "T")),
          _water_2015, unit="persons", sheet="34", weight=_occupants),
    Check("2015", "14-36", "Dwellings with piped water by source (`ABA_AGUA_ENTU`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(_PIPED_2015, ("dwellings", "public service", "community well",
                                   "private well", "pipa", "another dwelling", "elsewhere",
                                   "NE")),
          _stacked(tuple(n for n, _ in _PIPED_2015), lambda v: _counts(v[0], v[1:]), "36"),
          _water_source_2015, unit="persons", sheet="36"),
    Check("2015", "14-22", "Occupants with piped water by source (`ABA_AGUA_ENTU`)",
          "14_vivienda.xls", "viviendas",
          _row_cells(_PIPED_2015, ("occupants", "public service", "community well",
                                   "private well", "pipa", "another dwelling", "elsewhere",
                                   "NE")),
          _stacked(tuple(n for n, _ in _PIPED_2015), lambda v: _counts(v[0], v[1:]), "22"),
          _water_source_2015, unit="persons", sheet="22", weight=_occupants),
    Check("2015", "14-38", "Dwellings by drainage (`DRENAJE`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "with drainage", "public network", "septic tank", "ravine or crack",
           "river, lake or sea", "without", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 1, 1, 1, 1, 0, 0]), sheet="38",
                dims=lambda k: (k[0], "T")),
          _item("DRENAJE", ((1, 2, 3, 4), 1, 2, 3, 4, 5, 9)), unit="persons", sheet="38"),
    Check("2015", "14-24", "Occupants by drainage (`DRENAJE`)", "14_vivienda.xls", "viviendas",
          ("occupants", "with drainage", "public network", "septic tank", "ravine or crack",
           "river, lake or sea", "without", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 1, 1, 1, 1, 0, 0]), sheet="24",
                dims=lambda k: (k[0], "T")),
          _item("DRENAJE", ((1, 2, 3, 4), 1, 2, 3, 4, 5, 9)), unit="persons", sheet="24",
          weight=_occupants),
    Check("2015", "14-26", "Dwellings by electricity (`ELECTRICIDAD`)", "14_vivienda.xls",
          "viviendas", ("dwellings", "has it", "has none", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="26", dims=lambda k: (k[0], "T")),
          _item("ELECTRICIDAD", (5, 7, 9)), unit="persons", sheet="26"),
    Check("2015", "14-27", "Dwellings with electricity by light bulbs (`FOCOS`)",
          "14_vivienda.xls", "viviendas",
          ("dwellings", "1-5", "6-10", "11-15", "16-20", "21+", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="27", dims=lambda k: (k[0], "T")),
          _item("FOCOS", (tuple(range(1, 6)), tuple(range(6, 11)), tuple(range(11, 16)),
                          tuple(range(16, 21)), tuple(range(21, 999)), 999),
                lambda v: _dwellings_2015(v) & _code(v, "ELECTRICIDAD").eq(5)),
          unit="persons", sheet="27"),
    Check("2015", "14-28", "Dwellings by sanitary service (`SERSAN`, `CONAGUA`)",
          "14_vivienda.xls", "viviendas",
          ("dwellings", "with a toilet or latrine", "toilet", "toilet: flush", "toilet: bucket",
           "toilet: no water", "toilet: NE", "latrine", "latrine: bucket", "latrine: no water",
           "latrine: NE", "neither", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:], [0, 1, 2, 2, 2, 2, 1, 7, 7, 7, 0, 0]),
                sheet="28", dims=lambda k: (k[0], "T")),
          _sanitary_2015, unit="persons", sheet="28"),
    Check("2015", "14-29", "Dwellings by waste disposal (`DESTINO_BASURA`)", "14_vivienda.xls",
          "viviendas", ("dwellings", "collection service", "container", "burn it", "bury it",
                        "public dump", "elsewhere", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="29", dims=lambda k: (k[0], "T")),
          _item("DESTINO_BASURA", (1, 2, 3, 4, 5, 6, 9)), unit="persons", sheet="29"),
    Check("2015", "14-30", "Dwellings giving their waste to a service or container by "
          "separation (`SEPARA_BASURA`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "separate it", "do not", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="30", dims=lambda k: (k[0], "T")),
          _item("SEPARA_BASURA", (1, 3, 9),
                lambda v: _dwellings_2015(v) & _code(v, "DESTINO_BASURA").isin([1, 2])),
          unit="persons", sheet="30"),
    Check("2015", "14-31", "Dwellings by waste reuse (`SEPARA_ALI`/`_ABO`/`_VEN`)",
          "14_vivienda.xls", "viviendas", _item_cells(_REUSE_2015),
          _stacked(tuple(n for n, *_ in _REUSE_2015), lambda v: _counts(v[0], v[1:]), "31"),
          _items(_REUSE_2015), unit="persons", sheet="31"),
    Check("2015", "14-32", "Dwellings by goods and ICT (`REFRIGERADOR` … `SERV_TV_PAGA`)",
          "14_vivienda.xls", "viviendas", _item_cells(_GOODS_2015),
          _stacked(tuple(n for n, *_ in _GOODS_2015), lambda v: _counts(v[0], v[1:]), "32"),
          _items(_GOODS_2015), unit="persons", sheet="32"),
    Check("2015", "14-33", "Dwellings by equipment (`TINACO` … `PANEL_SOLAR`)",
          "14_vivienda.xls", "viviendas", _item_cells(_EQUIPMENT_2015),
          _stacked(tuple(n for n, *_ in _EQUIPMENT_2015), lambda v: _counts(v[0], v[1:]), "33"),
          _items(_EQUIPMENT_2015), unit="persons", sheet="33"),
    Check("2020", "07-04", "Population 18+ with educación superior (`EDUC_INEGI_DET`)",
          "cpv2020_a_eum_07_educacion.xlsx", "personas", ("18+, superior or posgrado",),
          _wide("Valor", lambda v: v[:1], sheet="04"), _superior, unit="persons", sheet="04",
          note="Técnica after preparatoria, licenciatura, normal superior, especialidad, "
               "maestría, doctorado (6w)."),
    Check("2020", "08-06", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          _ECO_2020, "personas", _DIVISIONS,
          _wide("Valor", lambda v: _counts(v[0], v[1:])[1:], sheet="06"), _occupation,
          unit="persons", sheet="06"),
    Check("2020", "08-08", "Employed by sector (`ACTIVIDADES_C_COARSE`)", _ECO_2020,
          "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _wide("Valor", lambda v: _counts(v[0], v[1:])[1:], sheet="08"), _sector,
          unit="persons", sheet="08"),
    Check("2020", "08-18", "Income of the employed in minimum wages (`INGTRMEN_SM`)",
          _ECO_2020, "personas", ("employed", *_SM_CELLS), _income_sm_published("Valor", "18"),
          _income_sm, unit="persons", sheet="18",
          note="The Zona Libre de la Frontera Norte (5,566.80; San Quintín included) and the "
               "rest of the country (3,696.60), DOF 23/12/2019; 7c."),
    Check("2020", "08-12", "Hours worked (`HORTRA_CAT`)", _ECO_2020, "personas",
          ("employed", "up to 40 (none included)", "41-48", "49-56", "more than 56",
           "not specified"),
          _wide("Valor", lambda v: (c := _counts(v[0], v[1:]))[:1]
                + [c[1] + c[2] + c[6], c[3], c[4], c[5], c[7]], sheet="12", dims=_total_row),
          _hours, unit="persons", sheet="12"),
    Check("2020", "09-04", "Health affiliation by institution (`DHSERSAL_*`)",
          "cpv2020_a_eum_09_servicios_de_salud.xlsx", "personas",
          ("population", "affiliated", "IMSS", "ISSSTE (federal or state)",
           "PEMEX, Defensa or Marina", "INSABI", "IMSS-BIENESTAR", "private", "other",
           "not affiliated", "not specified"),
          _affiliation_published, _affiliation, unit="persons", sheet="04"),
    Check("2020", "10-02", "Place of school by municipality (`LUGAR_ASI`)", _MOV_2020,
          "personas", ("students 3+", *_PLACE_CELLS),
          _wide("Valor", _place_published, sheet="02", dims=_total_row),
          _place("LUGAR_ASI", _students), unit="persons", sheet="02", note="7b."),
    Check("2020", "10-08", "Place of work by municipality (`LUGAR_TRAB`)", _MOV_2020,
          "personas", ("employed", *_PLACE_CELLS),
          _wide("Valor", _place_published, sheet="08", dims=_total_row),
          _place("LUGAR_TRAB", _employed), unit="persons", sheet="08", note="7b."),
    Check("2020", "10-06", "Commute to school (`MED_TRASLADO_ESC_*`)", _MOV_2020, "personas",
          ("students who travel", *(n for n, _ in _MODES_ESC)),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="06", dims=_total_row),
          _commute("MED_TRASLADO_ESC", _MODES_ESC, 3), unit="persons", sheet="06"),
    Check("2020", "10-12", "Commute to work (`MED_TRASLADO_TRAB_*`)", _MOV_2020, "personas",
          ("employed who travel", *(n for n, _ in _MODES_TRAB)),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="12", dims=_total_row),
          _commute("MED_TRASLADO_TRAB", _MODES_TRAB, 12), unit="persons", sheet="12"),
    Check("2020", "11-02", "Partner in the dwelling (`IDENT_PAREJA_CAT`)",
          "cpv2020_a_eum_11_situacion_conyugal.xlsx", "personas",
          ("married or in union, 12+", "partner lives here", "partner lives elsewhere",
           "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="02", dims=_total_row),
          _partner, unit="persons", sheet="02"),
    Check("2020", "16-34", "Financing of the owned dwellings bought or built "
          "(`FINANCIAMIENTO_*`, several sources)", "cpv2020_a_eum_16_vivienda.xlsx",
          "viviendas", ("dwellings", *_FINANCING_2020),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="34",
                dims=lambda k: (k[0], "T")),
          _financing_2020, unit="persons", sheet="34"),
) + (_dwelling_checks_2010() + _dwelling_checks_2020() + _dwelling_checks_2000()  # 7h, 7i
     + _person_checks_2015() + _person_checks_2000() + _person_checks_2000_l()        # 7j–7l
     + _person_checks_2010() + _person_checks_2020()                                 # 7m, 7n
     + _rate_checks()                                                                # 7o
     + _person_checks_2010_p() + _person_checks_2020_p())                            # 7p


# --------------------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------------------

def _frame(period: str, table: str, state: int) -> pd.DataFrame:
    import mxcensus
    if table == "migrantes":                                            # 7d
        return mxcensus.load_cpv_migrantes(period, state=state, labels=False)
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(period, state=state, derived=True, labels=False)
    if table == "viviendas" and isinstance(frame.index, pd.MultiIndex):
        frame = frame[~frame.index.get_level_values(0).duplicated()]  # 2000: one per dwelling
    if table == "viviendas" and period in _OWNERS:
        frame = _with_owners(frame, period, state)
    if table == "hogares" and period == "2000":
        frame = _with_members_2000(frame, state)                           # 7l
    return frame


def _with_members_2000(h: pd.DataFrame, state: int) -> pd.DataFrame:
    """7l: each CGPV 2000 household's members from the person file — the head's age (999 =
    not specified), the members under 12, of 12 to 64 and of 65 and more, the economically
    active and inactive, the employed (``_HEAD_AGE``, ``_UNDER12`` …)."""
    import mxcensus

    p = mxcensus.load_cpv_personas("2000", state=state, derived=True, labels=False)
    age = _age(p)
    activity = _cat(p, "CONACT_CAT")
    twelve = age.between(12, 130)
    counts = pd.DataFrame({
        "_UNDER12": age.between(0, 11), "_12TO64": age.between(12, 64),
        "_65PLUS": age.between(65, 130),
        "_PEA": twelve & activity.isin(["Trabaja", "Buscó trabajo"]),
        "_PEI": twelve & activity.isin(["No trabaja"]),
        "_EMPLOYED": twelve & activity.eq("Trabaja")}, index=p.index).astype(int)
    keys = [p.index.get_level_values(0), p.index.get_level_values(1)]
    sums = counts.groupby(keys).sum()
    head = _code(p, "OTROPARE_C").eq(100)
    head_age = age[head].groupby([k[head.to_numpy()] for k in keys]).first()
    out = h.copy()
    idx = pd.MultiIndex.from_arrays([h.index.get_level_values(0), h.index.get_level_values(1)])
    for col in sums.columns:
        out[col] = sums[col].reindex(idx).fillna(0).to_numpy()
    out["_HEAD_AGE"] = head_age.reindex(idx).to_numpy()
    return out


def _with_owners(v: pd.DataFrame, period: str, state: int) -> pd.DataFrame:
    """7h: the owners' raw ``SEXO`` (``DUE1_SEXO``/``DUE2_SEXO``) from the person file
    (``ID_VIV``, ``NUMPER``, ``SEXO``): the owner items hold person rows; 99 (not identified)
    or a blank gives none. The 2015 codes are unpadded, so both sides compare as numbers."""
    import pyarrow.parquet as pq
    from mxcensus.data._registry import POOCH

    path = POOCH.fetch(f"cpv_personas_{period}_{state:02d}.parquet")
    p = pq.read_table(path, columns=["ID_VIV", "NUMPER", "SEXO"]).to_pandas()
    sex = pd.Series(p["SEXO"].astype(str).to_numpy(), index=pd.MultiIndex.from_arrays(
        [pd.to_numeric(p["ID_VIV"]), pd.to_numeric(p["NUMPER"])]))
    dwelling = pd.to_numeric(pd.Series(v.index.get_level_values("ID_VIV"), index=v.index))
    out = v.copy()
    for name, col in zip(("DUE1_SEXO", "DUE2_SEXO"), _OWNERS[period]):
        row = pd.to_numeric(v[col], errors="coerce")
        key = pd.MultiIndex.from_arrays([dwelling.to_numpy(), row.to_numpy()])
        out[name] = sex.reindex(key).to_numpy()
    return out


# The tables broken down by sex, and their sex item (7d: the emigrants' own)
_SEX_ITEM = {"personas": "SEXO", "migrantes": "MSEXO"}


def _part(part, w: pd.Series, keep: pd.Series, state: int) -> dict[int, float]:
    """Σ weight of a cell part's records: in the frame's ``state``, or by their origin
    (:class:`ByOrigin`)."""
    if isinstance(part, Weighted):                                          # 7i
        mask = part.mask & keep
        return {state: float((w * pd.to_numeric(part.values, errors="coerce"))[mask].sum())}
    if not isinstance(part, ByOrigin):
        return {state: float(w[part & keep].sum())}
    mask = part.mask & keep
    origin = pd.to_numeric(part.origin, errors="coerce")
    origin = origin.where(origin.between(1, 32) | origin.eq(_REST), _UNSPECIFIED).astype(int)
    return {int(k): float(v) for k, v in w[mask].groupby(origin[mask]).sum().items()}


def _sums(check: Check, frame: pd.DataFrame, state: int
          ) -> dict[str, list[tuple[dict, dict | None]]]:
    """Σ weight (``FACTOR``) of each cell's numerator and denominator, by sex (T, and H/M
    for persons and emigrants), each as ``{state: Σ}`` (the frame's state, or the records'
    origins)."""
    w = check.weight(frame) if check.weight else pd.to_numeric(frame["FACTOR"])
    sexes = {"T": pd.Series(True, index=frame.index)}
    if check.table in _SEX_ITEM:
        for code, sex in _SEXES[check.period].items():
            sexes[sex] = frame[_SEX_ITEM[check.table]].eq(code)
    cells = check.ours(frame)
    return {sex: [(_part(num, w, keep, state),
                   _part(den, w, keep, state) if den is not None else None)
                  for num, den in cells]
            for sex, keep in sexes.items()}


def _value(num: float, den: float, unit: str) -> float:
    if unit == "average":              # 7i; 7j: INEGI writes 0 for an average of nobody
        return num / den if den else 0.0
    if unit == "rate":                 # 7o: per 1,000
        return 1000 * num / den if den else np.nan
    return num if unit == "persons" else (100 * num / den if den else np.nan)


def _tolerance(period: str, state: int, check: Check | None = None) -> float:
    if check is not None and check.tolerance:
        if state in check.tolerance:
            return check.tolerance[state]
        if None in check.tolerance:                  # 7j: the check's own, every state
            return check.tolerance[None]
    tol = _TOLERANCE[period]
    return tol.get(state, tol[None])


def run(periods: list[str], states: list[int], tab_dir: Path = _DEFAULT_TAB_DIR,
        mirror: Path = _DEFAULT_MIRROR, log=print) -> list[dict]:
    """Every check of ``periods`` over ``states`` (and the nation when all 32 are given).
    Returns one row per compared cell: period, check, state, sex, cell, published, ours,
    delta, tolerance."""
    from mxcensus.data import _registry

    _registry.POOCH.fetch = lambda name, **kw: str(mirror / name)
    paths = fetch(periods, tab_dir)
    every_state = len(states) == 32
    rows = []
    for period in periods:
        # 7d: a check counting records by origin needs every state
        checks = [c for c in CHECKS if c.period == period and (every_state or not c.by_origin)]
        workbooks, published = {}, {}
        for c in checks:
            if c.source not in workbooks:
                workbooks[c.source] = fd.read_workbook(paths[f"{period}/{c.source}"])
            published[c.key] = c.published(workbooks[c.source])
        del workbooks
        # (check, sex) → per cell, its numerator's and denominator's {state: Σ weight}
        acc: dict[tuple[str, str], list] = {}
        for state in states:
            frames = {}
            for c in checks:
                if c.table not in frames:
                    frames[c.table] = _frame(period, c.table, state)
                for sex, cells in _sums(c, frames[c.table], state).items():
                    slots = acc.setdefault((c.key, sex), [
                        (defaultdict(float), None if den is None else defaultdict(float))
                        for _, den in cells])
                    for (num_acc, den_acc), (num, den) in zip(slots, cells):
                        for s, v in num.items():
                            num_acc[s] += v
                        for s, v in (den or {}).items():
                            den_acc[s] += v
            log(f"  {period} state {state:02d}: {sum(len(f) for f in frames.values()):,} rows")
        sums: dict[tuple[str, int, str], list] = {}
        for (key, sex), slots in acc.items():
            targets = set().union(*(set(n) | set(d or ()) for n, d in slots))
            for s in targets:
                sums[key, s, sex] = [(n.get(s, 0.0), d.get(s, 0.0) if d is not None else np.nan)
                                     for n, d in slots]
            if every_state:                       # the nation: every state (and origin)
                sums[key, _NATION, sex] = [
                    (sum(n.values()), sum(d.values()) if d is not None else np.nan)
                    for n, d in slots]
        for c in checks:
            for (key, state, sex), cells in sums.items():
                if key != c.key or (state, sex) not in published[c.key]:
                    continue
                pub = published[c.key][state, sex]
                values = [_value(num, den, c.unit) for num, den in cells]
                if c.combine:                                                   # 7o
                    values = c.combine(values)
                if len(pub) != len(values) or len(pub) != len(c.cells):
                    raise RuntimeError(f"{period} {c.key}: {len(pub)} published cells, "
                                       f"{len(values)} computed, {len(c.cells)} named")
                for name, p, ours in zip(c.cells, pub, values):
                    if np.isnan(p):
                        continue
                    rows.append({"period": period, "check": c.key, "state": state, "sex": sex,
                                 "cell": name, "published": p, "ours": ours,
                                 # 7d: a share of nothing against a published one fails
                                 "delta": ours - p if not np.isnan(ours) else np.inf,
                                 "tolerance": _tolerance(period, state, c)})
    return rows


def _fmt(x: float, unit: str) -> str:
    if unit == "rate":                                                      # 7o
        return f"{x:.4f}"
    return f"{x:.3f}" if unit in ("points", "average") else f"{x:,.2f}"


def report(rows: list[dict], states: list[int]) -> str:
    """The Markdown report: per check, the cells compared, |Δ| statistics and the cells
    beyond tolerance."""
    df = pd.DataFrame(rows)
    by_key = {(c.period, c.key): c for c in CHECKS}
    lines = ["# CPV derived columns vs INEGI's sample tabulados", "",
             "Generated by `scripts/check_cpv_tabulados.py` (do not edit by hand). Each row "
             "compares the derived columns (`derived=True`) of one edition with the tabulado "
             "INEGI computed from the same sample, for "
             + ("every state, both sexes and the nation" if len(states) == 32
                else f"states {', '.join(f'{s:02d}' for s in states)}")
             + " — the derived columns and, since 7d, the samples' raw items (the EIC 2015 "
             "dwellings', CGPV 2000's employment and migration items and its `migrantes` "
             "file; 7h: the Censo 2010 and 2020 dwellings', the owners' sex from the person "
             "file). 2000: shares "
             "in percentage points (published with two decimals; 7i: its dwelling averages as "
             "they are); 2010, 2015 and 2020: counts "
             "in persons (Σ `FACTOR`; published totals × percentages; the occupants Σ "
             "`FACTOR` × `NUMPERS`; 7o: the fertility rates and infant mortality per 1,000, to "
             "0.0001 unless a note says otherwise).", ""]
    for period in sorted(df["period"].unique()):
        sub = df[df["period"] == period]
        tol = _TOLERANCE[period]
        extra = ", ".join(f"state {s:02d}: {t}" for s, t in tol.items() if s is not None)
        unit = "points" if period == "2000" else "persons"
        lines += [f"## {period}", "",
                  f"Tolerance: {tol[None]} {unit}" + (f" ({extra})" if extra else "") + ".", "",
                  "| check | tabulado | cells | median \\|Δ\\| | 95th pct. \\|Δ\\| | max \\|Δ\\| "
                  "(where) | beyond tolerance |",
                  "|---|---|---|---|---|---|---|"]
        notes = []
        for key in dict.fromkeys(sub["check"]):
            c = by_key[period, key]
            d = sub[sub["check"] == key]
            a = d["delta"].abs()
            worst = d.loc[a.idxmax()]
            bad = d[a > d["tolerance"]]
            where = f"{int(worst['state']):02d} {worst['sex']} «{worst['cell']}»"
            lines.append(f"| {key} {c.title} | `{c.source}`{' ' + c.sheet if c.sheet else ''} "
                         f"| {len(d)} | {_fmt(a.median(), c.unit)} | "
                         f"{_fmt(a.quantile(0.95), c.unit)} | {_fmt(a.max(), c.unit)} "
                         f"({where}) | {len(bad)} |")
            if c.note:
                notes.append(f"- {key}: {c.note}")
        lines += ["", *notes, ""] if notes else [""]
        bad = sub[sub["delta"].abs() > sub["tolerance"]]
        if len(bad):
            lines += ["Cells beyond tolerance:", "",
                      "| check | state | sex | cell | published | ours | Δ |",
                      "|---|---|---|---|---|---|---|"]
            for _, r in bad.iterrows():
                u = by_key[period, r["check"]].unit
                lines.append(f"| {r['check']} | {int(r['state']):02d} | {r['sex']} | {r['cell']} | "
                             f"{_fmt(r['published'], u)} | {_fmt(r['ours'], u)} | "
                             f"{_fmt(r['delta'], u)} |")
            lines.append("")
    lines += ["State 00 is the nation (the sum of the states); state 99 the origin not "
              "specified (the international migrants by the state they left); state 98 the "
              "states a tabulado publishes together («Resto de las entidades»); sex T = both, "
              "H = men, M = women.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--periods", nargs="+", default=sorted(SOURCES), choices=sorted(SOURCES))
    ap.add_argument("--states", nargs="+", type=int, default=list(range(1, 33)))
    ap.add_argument("--tab-dir", type=Path, default=_DEFAULT_TAB_DIR)
    ap.add_argument("--mirror", type=Path, default=_DEFAULT_MIRROR)
    ap.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    ap.add_argument("--report-only", action="store_true",
                    help="print the report instead of writing it")
    args = ap.parse_args(argv)
    rows = run(args.periods, args.states, args.tab_dir, args.mirror)
    text = report(rows, args.states)
    if args.report_only:
        print(text)
    else:
        args.report.write_text(text, encoding="utf-8")
        print(f"wrote {args.report} ({len(rows)} cells)")
    bad = [r for r in rows if abs(r["delta"]) > r["tolerance"]]
    print(f"{len(rows)} cells, {len(bad)} beyond tolerance")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
