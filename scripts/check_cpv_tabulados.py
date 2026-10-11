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
from dataclasses import dataclass
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
              "C2KMI08.xls", "C2KMI09.xls", "C2KMI10.xls", "C2KMI11.xls", "C2KMI12.xls")),
    "2010": ("ccpv/2010/tabulados/Ampliado",
             ("04_02A_ESTATAL.xls", "06_01A_ESTATAL.xls", "08_02A_ESTATAL.xls",
              "08_03A_ESTATAL.xls", "08_10A_ESTATAL.xls", "08_15A_ESTATAL.xls",
              "12_01A_ESTATAL.xls")),
    "2015": ("intercensal/2015/tabulados",
             ("04_migracion.xls", "05_etnicidad.xls", "06_educacion.xls",
              "07_servicios_de_salud.xls",
              "08_caracteristicas_economicas.xls", "10_movilidad_cotidiana.xls",
              "11_situacion_conyugal.xls", "12_hogares.xls", "14_vivienda.xls")),
    "2020": ("ccpv/2020/tabulados/ampliado",
             ("cpv2020_a_eum_07_educacion.xlsx",
              "cpv2020_a_eum_08_caracteristicas_economicas.xlsx",
              "cpv2020_a_eum_09_servicios_de_salud.xlsx",
              "cpv2020_a_eum_10_movilidad_cotidiana.xlsx",
              "cpv2020_a_eum_11_situacion_conyugal.xlsx", "cpv2020_a_eum_16_vivienda.xlsx")),
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


def _num(text: str | None) -> float:
    return float(text) if text not in (None, "") else np.nan


def _state_of(name: str) -> int | None:
    """0 for the nation, the state code for «NN Name», else ``None`` (an age-group row such
    as «50 Y MÁS AÑOS» is not a state)."""
    name = name.strip()
    if name.upper() == _C2K_NATION:
        return _NATION
    m = _C2K_STATE.match(name)
    if m and 1 <= int(m.group(1)) <= 32 and "AÑOS" not in name.upper():
        return int(m.group(1))
    return None


def _c2k_blocks(rows: list[dict], cols: str, level: str = "persons"
                ) -> dict[tuple[int, str], list[float]]:
    """A CGPV 2000 tabulado by state: ``{(state, sex): [cells of cols]}``. Person
    tabulados: the state's row (both sexes) and its first HOMBRES/MUJERES rows (age-group
    rows in between are skipped); dwelling tabulados: the state's VIVIENDAS row."""
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
        elif level == "dwellings" and a == "VIVIENDAS":
            out[state, "T"] = [_num(r.get(c)) for c in cols]
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


def _estimates(rows: list[dict], estimator: str) -> dict[tuple, list[float]]:
    """A 2010/2015 tabulado: the header row names the ``Estimador`` column; the columns
    before it are the row's dimensions (state first), those after it its values. Returns
    ``{(state, *other dimensions): [values]}`` for the rows of ``estimator``."""
    order = lambda c: (len(c), c)  # noqa: E731 — column letters in sheet order
    header = next(r for r in rows if "Estimador" in r.values())
    est = next(c for c in header if header[c] == "Estimador")
    dims = sorted((c for c in header if order(c) < order(est)), key=order)
    data = [r for r in rows if r.get(est) == estimator]
    values = sorted({c for r in data for c in r if order(c) > order(est)}, key=order)
    out = {}
    for r in data:
        if (state := _state_of(r.get(dims[0], ""))) is None:
            continue
        key = [state]
        for c in dims[1:]:
            text = r.get(c, "").strip()
            key.append(_SEX_LABEL.get(text, text) if header[c] == "Sexo" else text)
        out[tuple(key)] = [_num(r.get(c)) for c in values]
    return out


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
    unit: str = "points"              # points (shares) or persons (counts)
    sheet: str | None = None          # the workbook's sheet (default: its first)
    note: str = ""
    # state (0 = the nation) → its largest |Δ| for this check, over the edition's
    # :data:`_TOLERANCE` (7c: differences of INEGI's own, documented in the note)
    tolerance: dict[int, float] | None = None
    # 7d: each record's weight (default ``FACTOR``; the occupants: × ``NUMPERS``)
    weight: Callable[[pd.DataFrame], pd.Series] | None = None
    # 7d: some cells are :class:`ByOrigin` — compared only when all 32 states are loaded
    by_origin: bool = False


@dataclass(frozen=True)
class ByOrigin:
    """A cell part whose records count in their state of origin, not the frame's (7d: the
    emigrants by their birth state or their state in 1995, the international migrants by
    the state they left). ``origin`` holds state codes; anything outside 1–32 is the
    unspecified origin, :data:`_UNSPECIFIED`."""
    mask: pd.Series
    origin: pd.Series


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


def _stacked(names: tuple[str, ...], pick: Callable[[list], list], sheet: str):
    """EIC 2015 tabulados with one row per (state, category) — the class, the number of
    occupants or rooms, the fuel, the item: per state, ``pick`` of each category's values in
    the order of ``names`` (matched as :func:`_tokens`)."""
    def read(wb):
        out = {}
        for (state, category), values in _estimates(_sheet(wb, sheet), "Valor").items():
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


def _items(items: tuple):
    return _stacked_cells(*(_item(col, (yes, no, 9)) for _, col, yes, no in items))


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
)


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
    return frame


# The tables broken down by sex, and their sex item (7d: the emigrants' own)
_SEX_ITEM = {"personas": "SEXO", "migrantes": "MSEXO"}


def _part(part, w: pd.Series, keep: pd.Series, state: int) -> dict[int, float]:
    """Σ weight of a cell part's records: in the frame's ``state``, or by their origin
    (:class:`ByOrigin`)."""
    if not isinstance(part, ByOrigin):
        return {state: float(w[part & keep].sum())}
    mask = part.mask & keep
    origin = pd.to_numeric(part.origin, errors="coerce")
    origin = origin.where(origin.between(1, 32), _UNSPECIFIED).astype(int)
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
    return num if unit == "persons" else (100 * num / den if den else np.nan)


def _tolerance(period: str, state: int, check: Check | None = None) -> float:
    if check is not None and check.tolerance and state in check.tolerance:
        return check.tolerance[state]
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
                if len(pub) != len(cells) or len(pub) != len(c.cells):
                    raise RuntimeError(f"{period} {c.key}: {len(pub)} published cells, "
                                       f"{len(cells)} computed, {len(c.cells)} named")
                for name, p, (num, den) in zip(c.cells, pub, cells):
                    if np.isnan(p):
                        continue
                    ours = _value(num, den, c.unit)
                    rows.append({"period": period, "check": c.key, "state": state, "sex": sex,
                                 "cell": name, "published": p, "ours": ours,
                                 # 7d: a share of nothing against a published one fails
                                 "delta": ours - p if not np.isnan(ours) else np.inf,
                                 "tolerance": _tolerance(period, state, c)})
    return rows


def _fmt(x: float, unit: str) -> str:
    return f"{x:.3f}" if unit == "points" else f"{x:,.2f}"


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
             "file). 2000: shares "
             "in percentage points (published with two decimals); 2010, 2015 and 2020: counts "
             "in persons (Σ `FACTOR`; published totals × percentages; the occupants Σ "
             "`FACTOR` × `NUMPERS`).", ""]
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
              "specified (the international migrants by the state they left); sex T = both, "
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
