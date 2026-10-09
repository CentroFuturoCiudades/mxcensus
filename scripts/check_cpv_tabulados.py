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
              "C2KEM01.xls", "C2KEM05.xls", "C2KED10.xls", "C2KVI06.xls", "C2KVI10.xls")),
    "2010": ("ccpv/2010/tabulados/Ampliado",
             ("04_02A_ESTATAL.xls", "08_02A_ESTATAL.xls", "08_03A_ESTATAL.xls")),
    "2015": ("intercensal/2015/tabulados",
             ("04_migracion.xls", "08_caracteristicas_economicas.xls", "14_vivienda.xls")),
    "2020": ("ccpv/2020/tabulados/ampliado",
             ("cpv2020_a_eum_08_caracteristicas_economicas.xlsx",
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


def _c2k_sectors(rows: list[dict]) -> dict[tuple[int, str], list[float]]:
    """C2KEM05 (sector of the employed): under each state row, one row per sector (its name
    may wrap onto the next row, the values on the last) with the total, men and women in
    columns B, C, D."""
    out, state = {}, None
    for r in rows:
        a = (r.get("A") or "").strip()
        if (s := _state_of(a)) is not None:
            state = s
        elif state is not None and a and r.get("B"):
            for sex, col in (("T", "B"), ("H", "C"), ("M", "D")):
                out.setdefault((state, sex), []).append(_num(r.get(col)))
    return out


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
    table: str                        # personas | viviendas
    cells: tuple[str, ...]            # the compared cells' names
    published: Callable[[dict], dict]  # workbook → {(state, sex): [values]}
    ours: Callable[[pd.DataFrame], list]  # frame → [(numerator, denominator | None)]
    unit: str = "points"              # points (shares) or persons (counts)
    sheet: str | None = None          # the workbook's sheet (default: its first)
    note: str = ""


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


def _moved(frame: pd.DataFrame, col: str, item: str, code: str) -> pd.Series:
    """INEGI's tabulados count a person whose entity is not specified as «No especificado»;
    the derived columns keep the legacy rule (``OtraEnt``, STEP_6e.md)."""
    return _cat(frame, col).mask(frame[item].eq(code), "No especificado")


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


def _em05(p):
    employed = _age(p).between(12, 130) & _cat(p, "CONACT_CAT").eq("Trabaja")
    code = _code_of(p, "ACTIVIDADES_C_COARSE")
    return _shares(employed, *(code.isin(g) for _, g in _SECTORS_2000))


def _ed10(p):
    e = _cat(p, "EDUC_INEGI")
    return _shares(_age(p).between(15, 130), e.eq("Sin Educación"), e.eq("Primaria_incom"),
                   e.eq("Primaria_com"),
                   e.isin(["Técnica_primaria", "Secundaria_incom", "Secundaria_com"]),
                   e.eq("Posbásica"), e.eq("No especificado"))


def _vi06(v):
    cd = _cat(v, "CUADORM_CAT")
    return _shares(pd.Series(True, index=v.index), cd.eq("1"), cd.eq("2+"),
                   cd.eq("No especificado"))


def _vi10(v):
    dr = _cat(v, "DRENAJE_CAT")
    return _shares(pd.Series(True, index=v.index), dr.eq("Sí"), dr.eq("No"),
                   dr.eq("No especificado"))


def _c2k(cols: str, combine: Callable[[list], list] = lambda v: v, level: str = "persons"):
    def read(wb):
        return {k: combine(v) for k, v in _c2k_blocks(_sheet(wb, None), cols, level).items()}
    return read


# 2010 / 2015 --------------------------------------------------------------------------

def _counts_of(*masks: pd.Series) -> list:
    return [(m, None) for m in masks]


def _birthplace_2015(p):
    nac = _moved(p, "ENT_PAIS_NAC_CAT", "ENT_PAIS_NAC", "997")
    return _counts_of(pd.Series(True, index=p.index), nac.eq("EstaEnt"), nac.eq("OtraEnt"),
                      nac.eq("OtroPais"), nac.eq("No especificado"))


def _residence(item: str, code: str):
    def ours(p):
        res = _moved(p, "ENT_PAIS_RES_CAT", item, code)
        five = _age(p).between(5, 130)
        return _counts_of(five, five & res.eq("EstaEnt"), five & res.isin(["OtraEnt", "OtroPais"]),
                          five & res.eq("No especificado"))
    return ours


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
    Check("2000", "ED10", "Education of the 15+ (`EDUC_INEGI`)", "C2KED10.xls", "personas",
          ("sin instrucción", "primaria incompleta or grade not specified",
           "primaria completa", "secundaria and técnica after primaria",
           "media superior and superior", "not specified"),
          _c2k("CDEFGHIJKL", lambda v: [v[0], v[1] + v[3], v[2], v[4] + v[5] + v[6],
                                        v[7] + v[8], v[9]]), _ed10,
          note="INEGI's 2000 levels put técnica after primaria with secundaria (its footnote "
               "1), so the comparison groups it there."),
    Check("2000", "VI06", "Bedrooms (`CUADORM_CAT`), % of the dwellings", "C2KVI06.xls",
          "viviendas", ("one", "two or more", "not specified"),
          _c2k("CDEFGHI", lambda v: [v[0], sum(v[1:6]), v[6]], level="dwellings"), _vi06),
    Check("2000", "VI10", "Drainage (`DRENAJE_CAT`), % of the dwellings", "C2KVI10.xls",
          "viviendas", ("has drainage", "has none", "not specified"),
          _c2k("CHI", level="dwellings"), _vi10),
    Check("2010", "04_02A", "Residence in 2005 (`ENT_PAIS_RES_CAT`), the 5+",
          "04_02A_ESTATAL.xls", "personas",
          ("population 5+", "same entity", "another entity or country", "not specified"),
          _wide("Parámetro", lambda v: [_counts(v[0], v[1:])[i] for i in (0, 1, 5, 6)]),
          _residence("RES05EDO_C", "999"), unit="persons",
          note="Entity not specified (`RES05EDO_C` 999) counted as «No especificado», as "
               "INEGI's tabulado (the derived column: `OtraEnt`)."),
    Check("2010", "08_02A", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          "08_02A_ESTATAL.xls", "personas", _DIVISIONS,
          _long("Parámetro", _DIVISIONS), _occupation, unit="persons"),
    Check("2010", "08_03A", "Employed by sector (`ACTIVIDADES_C_COARSE`)", "08_03A_ESTATAL.xls",
          "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _long("Parámetro", tuple(n for n, _ in _SECTOR_GROUPS)), _sector, unit="persons"),
    Check("2015", "04-02", "Birthplace (`ENT_PAIS_NAC_CAT`)", "04_migracion.xls", "personas",
          ("population", "this entity", "another entity", "abroad", "not specified"),
          _wide("Valor", lambda v: (c := _counts(v[0], v[1:]))[:3] + [c[3] + c[4], c[5]],
                sheet="02"),
          _birthplace_2015, unit="persons", sheet="02",
          note="Entity not specified (`ENT_PAIS_NAC` 997) counted as «No especificado», as "
               "INEGI's tabulado (the derived column: `OtraEnt`)."),
    Check("2015", "04-05", "Residence in 2010 (`ENT_PAIS_RES_CAT`), the 5+", "04_migracion.xls",
          "personas", ("population 5+", "same entity", "another entity or country",
                       "not specified"),
          _wide("Valor", lambda v: [_counts(v[0], v[1:])[i] for i in (0, 1, 5, 6)], sheet="05"),
          _residence("ENT_PAIS_RES10", "997"), unit="persons", sheet="05",
          note="Entity not specified (`ENT_PAIS_RES10` 997) counted as «No especificado»."),
    Check("2015", "08-02", "Activity of the 12+ (`CONACT_CAT`)",
          "08_caracteristicas_economicas.xls", "personas",
          ("population 12+", "PEA", "employed", "unemployed", "inactive", "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:6], [0, 1, 1, 0, 0]), sheet="02",
                dims=lambda k: k[:2] if k[2] == "Total" else None),
          _activity_2015, unit="persons", sheet="02"),
    Check("2015", "08-06", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          "08_caracteristicas_economicas.xls", "personas", _DIVISIONS,
          _long("Valor", _DIVISIONS, sheet="06"), _occupation, unit="persons", sheet="06"),
    Check("2015", "08-07", "Employed by sector (`ACTIVIDADES_C_COARSE`)",
          "08_caracteristicas_economicas.xls", "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _long("Valor", tuple(n for n, _ in _SECTOR_GROUPS), sheet="07"), _sector,
          unit="persons", sheet="07"),
    Check("2015", "14-18", "Financing of the owned dwellings bought or built "
          "(`FINANCIAMIENTO_*`)", "14_vivienda.xls", "viviendas",
          ("dwellings", "INFONAVIT, FOVISSSTE or PEMEX", "FONHAPO", "banks",
           "other institution", "a relative or another person", "own resources",
           "not specified"),
          _wide("Valor", lambda v: _counts(v[0], v[1:]), sheet="18",
                dims=lambda k: (k[0], "T")),
          _financing_2015, unit="persons", sheet="18"),
    Check("2020", "08-06", "Employed by occupational division (`OCUPACION_C_COARSE`)",
          _ECO_2020, "personas", _DIVISIONS,
          _wide("Valor", lambda v: _counts(v[0], v[1:])[1:], sheet="06"), _occupation,
          unit="persons", sheet="06"),
    Check("2020", "08-08", "Employed by sector (`ACTIVIDADES_C_COARSE`)", _ECO_2020,
          "personas", tuple(n for n, _ in _SECTOR_GROUPS),
          _wide("Valor", lambda v: _counts(v[0], v[1:])[1:], sheet="08"), _sector,
          unit="persons", sheet="08"),
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
    loader = mxcensus.load_cpv_personas if table == "personas" else mxcensus.load_cpv_viviendas
    frame = loader(period, state=state, derived=True, labels=False)
    if table == "viviendas" and isinstance(frame.index, pd.MultiIndex):
        frame = frame[~frame.index.get_level_values(0).duplicated()]  # 2000: one per dwelling
    return frame


def _sums(check: Check, frame: pd.DataFrame) -> dict[str, list[tuple[float, float]]]:
    """Σ FACTOR of each cell's numerator and denominator, by sex (T, and H/M for persons)."""
    w = pd.to_numeric(frame["FACTOR"])
    sexes = {"T": pd.Series(True, index=frame.index)}
    if check.table == "personas":
        for code, sex in _SEXES[check.period].items():
            sexes[sex] = frame["SEXO"].eq(code)
    cells = check.ours(frame)
    return {sex: [(float(w[num & keep].sum()),
                   float(w[den & keep].sum()) if den is not None else np.nan)
                  for num, den in cells]
            for sex, keep in sexes.items()}


def _value(num: float, den: float, unit: str) -> float:
    return num if unit == "persons" else (100 * num / den if den else np.nan)


def _tolerance(period: str, state: int) -> float:
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
    rows = []
    for period in periods:
        checks = [c for c in CHECKS if c.period == period]
        published = {}
        for c in checks:
            published[c.key] = c.published(fd.read_workbook(paths[f"{period}/{c.source}"]))
        sums: dict[tuple[str, int, str], list] = {}
        for state in states:
            frames = {}
            for c in checks:
                if c.table not in frames:
                    frames[c.table] = _frame(period, c.table, state)
                for sex, cells in _sums(c, frames[c.table]).items():
                    sums[c.key, state, sex] = cells
            log(f"  {period} state {state:02d}: {sum(len(f) for f in frames.values()):,} rows")
        if len(states) == 32:
            for c in checks:
                for sex in ("T", "H", "M"):
                    parts = [sums.get((c.key, s, sex)) for s in states]
                    if all(parts):
                        sums[c.key, _NATION, sex] = [
                            (sum(p[i][0] for p in parts), sum(p[i][1] for p in parts))
                            for i in range(len(parts[0]))]
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
                                 "delta": ours - p, "tolerance": _tolerance(period, state)})
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
             + ". 2000: shares in percentage points (published with two decimals); 2010 and "
             "2015: counts in persons (Σ `FACTOR`; published totals × percentages).", ""]
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
    lines += ["State 00 is the nation (the sum of the states); sex T = both, H = men, "
              "M = women.", ""]
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
