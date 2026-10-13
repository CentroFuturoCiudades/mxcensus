"""``scripts/check_cpv_tabulados.py`` (unit 6m): the derived columns against INEGI's sample
tabulados (6p: Censo 2020's ampliado tabulados too).

Offline: the readers of the three tabulado layouts (CGPV 2000 blocks and sector rows, the
2010/2015 «Estimador» tables), the count arithmetic and the check list. Real data (skipped
without the local mirror and the cached tabulados in ``data/dict/tabulados``): every check
of state 01 within its tolerance. All 32 states, both sexes and the nation:
``docs/cpv/TABULADOS_REPORT.md``.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_cpv_tabulados as ck  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_MIRROR = _ROOT / "data" / "parquet"
_TABS = _ROOT / "data" / "dict" / "tabulados"
_REAL = all((_MIRROR / f"cpv_personas_{p}_01.parquet").exists() for p in ck.SOURCES) and all(
    (_TABS / period / name).exists() for period, (_, names) in ck.SOURCES.items()
    for name in names)
_REAL_SKIP = pytest.mark.skipif(not _REAL, reason="no local CPV mirror or cached tabulados")


def test_state_of():
    assert ck._state_of("ESTADOS UNIDOS MEXICANOS") == ck._state_of("Estados Unidos Mexicanos") == 0
    assert ck._state_of("01 AGUASCALIENTES") == 1
    assert ck._state_of("32 Zacatecas") == 32
    # 7p: Censo 2010's plain names (code order), «the rest of the states» together
    assert ck._state_of("Aguascalientes") == 1 and ck._state_of("Zacatecas ") == 32
    assert ck._state_of("México") == 15 and ck._state_of("Distrito Federal") == 9
    assert ck._state_of("Resto de las entidades") == ck._REST == 98
    for not_a_state in ("12 - 14  AÑOS", "50 Y MÁS  AÑOS", "15 Y MÁS AÑOS", "HOMBRES", "",
                        "40 Otra cosa", "MÉXICO", "Estados Unidos de América"):
        assert ck._state_of(not_a_state) is None, not_a_state


def test_c2k_blocks_persons_and_dwellings():
    """A state row (both sexes), age-group rows (skipped), then HOMBRES/MUJERES and their
    own age groups (the first HOMBRES/MUJERES row is the sex's total)."""
    rows = [{"A": "INEGI. XII Censo"}, {"A": "ENTIDAD FEDERATIVA", "C": "EN LA"},
            {"A": "ESTADOS UNIDOS MEXICANOS", "B": "100", "C": "80.5", "D": "19.5"},
            {"A": "0 - 14   AÑOS", "B": "30", "C": "90", "D": "10"},
            {"A": "50 Y MÁS  AÑOS", "B": "10", "C": "70", "D": "30"},
            {"A": "HOMBRES", "B": "48", "C": "81", "D": "19"},
            {"A": "50 Y MÁS  AÑOS", "B": "5", "C": "71", "D": "29"},
            {"A": "MUJERES", "B": "52", "C": "80", "D": "20"},
            {"A": "01 AGUASCALIENTES", "B": "9", "C": "79.03", "D": ""},
            {"A": "HOMBRES", "B": "4", "C": "79.87", "D": "20.13"}]
    out = ck._c2k_blocks(rows, "CD")
    assert out[0, "T"] == [80.5, 19.5] and out[0, "H"] == [81, 19] and out[0, "M"] == [80, 20]
    assert out[1, "T"][0] == 79.03 and np.isnan(out[1, "T"][1]) and out[1, "H"] == [79.87, 20.13]
    assert set(out) == {(0, "T"), (0, "H"), (0, "M"), (1, "T"), (1, "H")}
    dwellings = [{"A": "01 AGUASCALIENTES"}, {"A": "VIVIENDAS", "B": "5", "C": "94.31"},
                 {"A": "OCUPANTES", "B": "20", "C": "95"}]
    assert ck._c2k_blocks(dwellings, "C", level="dwellings") == {(1, "T"): [94.31]}


def test_c2k_sectors_wrapped_names():
    rows = [{"A": "SEGÚN SECTOR DE ACTIVIDAD/1", "B": "TOTAL", "C": "HOMBRES", "D": "MUJERES"},
            {"A": "01 AGUASCALIENTES", "B": "336384", "C": "218420", "D": "117964"},
            {"A": "- AGRICULTURA, GANADERÍA, APROVECHAMIENTO"},
            {"A": "FORESTAL, PESCA Y CAZA", "B": "8.91", "C": "12.71", "D": "1.88"},
            {"A": "- MINERÍA", "B": "0.23", "C": "0.28", "D": "0.12"},
            {"A": "/1 Con base en el SCIAN"}]
    assert ck._c2k_sectors(rows) == {(1, "T"): [8.91, 0.23], (1, "H"): [12.71, 0.28],
                                     (1, "M"): [1.88, 0.12]}


def test_estimates_dimensions_and_blanks():
    """The «Estimador» column splits the dimensions (state first; only the «Sexo» column's
    labels become T/H/M) from the values; a blank cell is NaN, not a shifted column."""
    rows = [{"A": "Entidad federativa", "B": "Sexo", "C": "Grupos de edad", "D": "Estimador",
             "E": "Población"},
            {"F": "Ocupada"},
            {"A": "Estados Unidos Mexicanos", "B": "Total", "C": "Total", "D": "Valor",
             "E": "100", "F": "50.5", "G": "49.5"},
            {"A": "Estados Unidos Mexicanos", "B": "Total", "C": "Total", "D": "Error estándar",
             "E": "1", "F": "0.1", "G": "0.1"},
            {"A": "01 Aguascalientes", "B": "Mujeres", "C": "12-14 años", "D": "Valor",
             "E": "10", "G": "40"}]
    out = ck._estimates(rows, "Valor")
    assert out[0, "T", "Total"] == [100, 50.5, 49.5]
    assert out[1, "M", "12-14 años"][::2] == [10, 40] and np.isnan(out[1, "M", "12-14 años"][1])
    assert len(out) == 2


def test_c2k_sectors_total_and_sex_columns():
    """7d: C2KEM03 keeps the state row (the 12+) before its age rows; C2KEM11 has one row
    per state with the sexes in columns."""
    rows = [{"A": "ESTADOS UNIDOS MEXICANOS", "B": "50.54", "C": "71.44", "D": "31.3"},
            {"A": "12 - 14  AÑOS", "B": "8.89", "C": "12.3", "D": "5.43"},
            {"A": "01 AGUASCALIENTES", "B": "51.64", "C": "71.43", "D": "34.09"}]
    out = ck._c2k_sectors(rows, total=True)
    assert out[0, "T"] == [50.54, 8.89] and out[0, "M"] == [31.3, 5.43]
    assert out[1, "H"] == [71.43]
    assert ck._c2k_sectors(rows) == {(0, "T"): [8.89], (0, "H"): [12.3], (0, "M"): [5.43]}
    wide = [{"A": "B=TOTAL", "B": "TOTAL"},
            {"A": "01  AGUASCALIENTES", "B": "1.12", "C": "1.28", "D": "0.84", "E": "19.06",
             "F": "13.23", "G": "29.9"}]
    read = ck._c2k_sex_columns({"T": "BE", "H": "CF", "M": "DG"})
    assert read({"s": wide}) == {(1, "T"): [1.12, 19.06], (1, "H"): [1.28, 13.23],
                                 (1, "M"): [0.84, 29.9]}


def test_c2k_states_and_national_blocks():
    """7d: C2KMI10–12 rows by the state left, its «NO ESPECIFICADO» = 99; C2KMI07/08 the
    nation's, the men's and the women's blocks, row by row (C2KMI08's first row: counts)."""
    rows = [{"A": "ESTADOS UNIDOS MEXICANOS", "B": "100", "C": "74.6", "D": "25.4"},
            {"A": "01  AGUASCALIENTES", "B": "100", "C": "83.63", "D": "16.37"},
            {"A": "NO ESPECIFICADO", "B": "100", "C": "77.04", "D": "22.96"}]
    assert ck._c2k_states("CD")({"s": rows}) == {(0, "T"): [74.6, 25.4], (1, "T"): [83.63, 16.37],
                                                 (99, "T"): [77.04, 22.96]}
    blocks = [{"A": "SEXO Y GRUPOS", "B": "POBLACIÓN"},
              {"A": "ESTADOS UNIDOS MEXICANOS", "B": "1633052", "C": "1235477"},
              {"A": "0 - 4    AÑOS", "B": "1.67", "C": "1.47"},
              {"A": "NO ESPECIFICADO", "B": "2.4", "C": "2.37"},
              {"A": "HOMBRES", "B": "1218000", "C": "930000"},
              {"A": "0 - 4    AÑOS", "B": "1.2", "C": "1.1"},
              {"A": "MUJERES", "B": "415000", "C": "305000"},
              {"A": "0 - 4    AÑOS", "B": "3", "C": "2.9"}]
    assert ck._c2k_national("BC", first=False)({"s": blocks}) == {
        (0, "T"): [1.67, 1.47, 2.4, 2.37], (0, "H"): [1.2, 1.1], (0, "M"): [3, 2.9]}
    assert ck._c2k_national("C")({"s": blocks})[0, "M"] == [305000, 2.9]


def test_tokens_keep_numbers():
    """7d: «2 ocupantes» ≠ «3 ocupantes» (``_words`` drops digits); a footnote glued to a
    word is dropped."""
    assert ck._tokens("2 ocupantes") != ck._tokens("3 ocupantes")
    assert ck._tokens("Otro tipo de vivienda1") == ck._tokens("otro tipo de vivienda")
    assert ck._tokens("6 cuartos y más") == frozenset({"6", "cuartos", "y", "más"})


def test_part_by_origin():
    """7d: a plain mask counts in the frame's state; a :class:`ByOrigin` part in each
    record's origin, outside 1–32 the unspecified 99."""
    import pandas as pd
    w = pd.Series([1.0, 2.0, 4.0, 8.0])
    keep = pd.Series([True, True, True, False])
    every = pd.Series(True, index=w.index)
    assert ck._part(every, w, keep, 5) == {5: 7.0}
    origin = pd.Series(["001", "999", "001", "002"])
    assert ck._part(ck.ByOrigin(every, origin), w, keep, 5) == {1: 5.0, 99: 2.0}
    rest = pd.Series([98, 0, 4, 4])                                  # 7p: kept apart
    assert ck._part(ck.ByOrigin(every, rest), w, keep, 5) == {98: 1.0, 99: 2.0, 4: 4.0}


def test_sums_migrants_by_sex():
    """7d: the emigrants' sex is ``MSEXO``; a check's ``weight`` replaces ``FACTOR``."""
    import pandas as pd
    m = pd.DataFrame({"FACTOR": ["10", "20", "30"], "MSEXO": ["1", "2", "2"],
                      "NUMPERS": ["1", "2", "3"]})
    every = lambda f: [(pd.Series(True, index=f.index), None)]   # noqa: E731
    check = ck.Check("2000", "X", "x", "C2KMI07.xls", "migrantes", ("all",), dict, every,
                     unit="persons")
    assert ck._sums(check, m, 3) == {"T": [({3: 60.0}, None)], "H": [({3: 10.0}, None)],
                                     "M": [({3: 50.0}, None)]}
    weighted = ck.Check("2015", "Y", "y", "14_vivienda.xls", "viviendas", ("all",), dict, every,
                        unit="persons", weight=ck._occupants)
    assert ck._sums(weighted, m, 3) == {"T": [({3: 140.0}, None)]}


def test_counts():
    assert ck._counts(200, [50, 10]) == [200, 100, 20]
    # PEA % of the 12+, employed and unemployed % of the PEA, inactive % of the 12+
    assert ck._counts(200, [50, 90, 10, 50], [0, 1, 1, 0]) == [200, 100, 90, 10, 100]


def test_sel_and_crossed():
    """7h: a category of a coded item (``None`` any, ``"N+"`` N to 98, a tuple, a code) and
    the dwellings by two items (each row's total, then its columns)."""
    x = pd.Series([1, 5, 7, 99, np.nan])
    assert ck._sel(x, None).all() and ck._sel(x, "5+").tolist() == [False, True, True, False,
                                                                     False]
    assert ck._sel(x, (1, 7)).tolist() == [True, False, True, False, False]
    v = pd.DataFrame({"CLAVIVP": ["1", "1", "5", "9"], "COCINA": ["1", "3", "1", "1"],
                      "COMBUST": ["1", "3", "1", "9"]})
    cells = ck._crossed(ck._dwellings_2010, "COCINA", (None, 1), "COMBUST", (1, (3, 4), 9))(v)
    assert [num.tolist() for num, _ in cells] == [
        [True, True, False, True], [True, False, False, False], [False, True, False, False],
        [False, False, False, True],                       # every dwelling but the locale (5)
        [True, False, False, True], [True, False, False, False], [False] * 4,
        [False, False, False, True]]


def test_with_owners_and_their_sex(monkeypatch, tmp_path):
    """7h: the owners' sex from the person rows the owner items point at (2015's unpadded
    codes compare as numbers; 99 = not identified), and 2020's owners by sex and number."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from mxcensus.data import _registry

    persons = pa.table({"ID_VIV": ["010010000001"] * 3 + ["010010000002"] * 2,
                        "NUMPER": ["01", "02", "03", "01", "02"],
                        "SEXO": ["1", "3", "3", "3", "3"]})
    pq.write_table(persons, tmp_path / "cpv_personas_2020_01.parquet")
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda name, **kw: str(tmp_path / name))
    v = pd.DataFrame({"CLAVIVP": ["01"] * 4, "TENENCIA": ["1", "1", "1", "2"],
                      "DUE1_NUM": ["02", "01", "99", None], "DUE2_NUM": [None, "02", None, None]},
                     index=pd.Index(["010010000001", "010010000002", "010010000001",
                                     "010010000002"], name="ID_VIV"))
    out = ck._with_owners(v, "2020", 1)
    assert out["DUE1_SEXO"].tolist()[:2] == ["3", "3"] and out["DUE1_SEXO"].isna().tolist()[2:] == [
        True, True]
    assert out["DUE2_SEXO"].tolist()[1] == "3" and out["DUE2_SEXO"].isna().sum() == 3
    cells = [num.tolist() for num, _ in ck._owners_2020(out)]
    assert cells == [[True, True, True, False], [True, False, False, False], [False] * 4,
                     [False, True, False, False], [False] * 4, [False] * 4,
                     [False, False, True, False]]


def test_saving_bulbs_and_titles():
    """7h: 2020's energy-saving bulbs (none whatever the total; not specified = the saving
    bulbs' 999, or a share of an unknown total) and the occupants' titles."""
    v = pd.DataFrame({"CLAVIVP": ["01"] * 7 + ["07"], "ELECTRICIDAD": ["1"] * 8,
                      "FOCOS": ["10", "999", "10", "8", "4", "10", "999", ""],
                      "FOCOS_AHORRA": ["0", "0", "4", "6", "4", "999", "3", ""]})
    cells = [num.tolist() for num, _ in ck._saving_bulbs_2020(v)]
    assert [sum(c) for c in cells] == [7, 2, 1, 0, 1, 1, 2]               # 75% → 75–100%
    assert cells[1][1] and cells[4][3] and cells[5][4] and cells[6][5] and cells[6][6]
    assert ck._occupants_title("Owned dwellings by deed") == "Occupants of the owned dwellings by deed"
    assert ck._occupants_title("Dwellings by wall") == "Occupants of the dwellings by wall"


def test_c2k_items_and_repeated_blocks():
    """7i: C2KVI16's one row per good under each state's name row, and C2KVI18's several
    VIVIENDAS/OCUPANTES blocks per state (all, then each way of disposal)."""
    goods = [{"A": "ESTADOS UNIDOS MEXICANOS"}, {"A": "RADIO", "B": "10", "C": "80", "D": "20",
                                                 "F": "40", "G": "75", "H": "25"},
             {"A": "TELEVISIÓN", "B": "10", "C": "90", "D": "10", "F": "40", "G": "95", "H": "5"},
             {"A": "01 AGUASCALIENTES"}, {"A": "RADIO", "B": "2", "C": "70", "D": "30"}]
    assert ck._c2k_items("CD")({"x": goods}) == {(0, "T"): [80, 20, 90, 10], (1, "T"): [70, 30]}
    assert ck._c2k_items("GH")({"x": goods})[0, "T"] == [75, 25, 95, 5]
    blocks = [{"A": "01 AGUASCALIENTES"}, {"A": "VIVIENDAS", "B": "100", "C": "60", "D": "40"},
              {"A": "OCUPANTES", "B": "100", "C": "55", "D": "45"},
              {"A": "SERVICIO DE RECOLECCIÓN DOMICILIARIO"},
              {"A": "VIVIENDAS", "B": "100", "C": "70", "D": "30"}]
    assert ck._c2k_repeated("CD", "VIVIENDAS")({"x": blocks}) == {(1, "T"): [60, 40, 70, 30]}
    assert ck._c2k_repeated("CD", "OCUPANTES")({"x": blocks}) == {(1, "T"): [55, 45]}
    occupants = [{"A": "01 AGUASCALIENTES"}, {"A": "VIVIENDAS", "B": "9", "C": "1"},
                 {"A": "OCUPANTES", "B": "40", "C": "2"}]
    assert ck._c2k_blocks(occupants, "C", level="occupants") == {(1, "T"): [2]}


def test_weighted_parts_and_averages():
    """7i: a ``Weighted`` part counts each record's value × its weight (an average's
    numerator or denominator); unit «average» = numerator / denominator."""
    w = pd.Series([2.0, 1.0, 1.0])
    keep = pd.Series([True, True, False])
    part = ck.Weighted(pd.Series([True, False, True]), pd.Series(["4", "3", "5"]))
    assert ck._part(part, w, keep, 1) == {1: 8.0}
    assert ck._value(9.0, 2.0, "average") == 4.5 and ck._value(0.0, 0.0, "average") == 0.0  # 7j
    v = pd.DataFrame({"NUMPERS": ["4", "2"], "NUMHOGS": [None, "2"], "TOTCUART_INEGI": [2, None],
                      "CUADORM": ["01", "99"]})
    cells = ck._vi19(v)
    w = pd.Series([1.0, 1.0])
    sums = [(ck._part(n, w, w.astype(bool), 1)[1],
             ck._part(d, w, w.astype(bool), 1)[1]) for n, d in cells]
    assert sums == [(6.0, 2.0), (6.0, 3.0), (4.0, 2.0), (4.0, 1.0), (3.0, 2.0)]


def test_age_groups_and_dimensions():
    """7j: INEGI's age-group labels as ``EDAD`` ranges (999 = not specified), and the EIC 2015
    tabulados' rows (state[, sex][, category], age group) as one list per (state, sex)."""
    p = pd.DataFrame({"EDAD": ["004", "012", "075", "110", "999"]})
    assert ck._age_group(p, "00-04 años").tolist() == [True, False, False, False, False]
    assert ck._age_group(p, "75 años y más").tolist() == [False, False, True, True, False]
    assert ck._age_group(p, "No especificado").tolist() == [False] * 4 + [True]
    assert ck._age_group(p, "Total").all()
    with pytest.raises(ValueError):
        ck._age_group(p, "Menores")
    rows = [{"A": "Entidad federativa", "B": "Sexo", "C": "Situación", "D": "Grupos",
             "E": "Estimador", "F": "Mujeres"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Total", "D": "Total", "E": "Valor",
             "F": "10", "G": "2.5"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Total", "D": "12-14 años",
             "E": "Valor", "F": "4", "G": "0.1"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Soltera", "D": "Total",
             "E": "Valor", "F": "3", "G": "0.5"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Soltera", "D": "12-14 años",
             "E": "Valor", "F": "2", "G": "0.0"}]
    read = ck._by_dims("Valor", None, ("Total", "12-14 años"), lambda v: v[1:2], sexed=True,
                       rows=("Total", "Soltera"))
    assert read({"x": rows}) == {(1, "T"): [2.5, 0.1, 0.5, 0.0]}
    # 7p: a row INEGI leaves out is nobody
    read = ck._by_dims("Valor", None, ("Total", "No especificado"), lambda v: v, sexed=True,
                       rows=("Total",))
    assert read({"x": rows}) == {(1, "T"): [10.0, 2.5, 0.0, 0.0]}


def test_c2k_rows_age_shares_and_disability():
    """7k: the state's row and its category rows (C2KDI01), the age shares per sex of
    C2KPO01's counts, «M.I.» as missing, and CGPV 2000's disability types (``DISOTRA_C`` 299
    motor, 399 mental, 960 type not specified)."""
    rows = [{"A": "ESTADOS UNIDOS MEXICANOS", "B": "100", "C": "50", "D": "50"},
            {"A": "0 - 4   AÑOS", "B": "10", "C": "6", "D": "4"},
            {"A": "65 Y MÁS AÑOS", "B": "90", "C": "44", "D": "46"},
            {"A": "01 AGUASCALIENTES", "B": "20", "C": "10", "D": "10"},
            {"A": "0 - 4   AÑOS", "B": "5", "C": "2", "D": "3"}]
    assert ck._c2k_rows("BC")({"x": rows}) == {(0, "T"): [100, 50, 10, 6, 90, 44],
                                               (1, "T"): [20, 10, 5, 2]}
    shares = ck._c2k_age_shares({"x": rows})
    assert shares[0, "T"] == [10.0, 90.0] and shares[0, "H"] == [12.0, 88.0]
    assert shares[1, "M"] == [30.0]
    assert np.isnan(ck._num("M.I.")) and ck._num("2.5") == 2.5
    p = pd.DataFrame({"DISMOV": [None, "9", None, None, None, "1"],
                      "DISBRA": [None] * 6, "DISOIR": [None, None, None, "3", None, None],
                      "DISMUDO": [None] * 6, "DISVER": [None] * 6,
                      "DISMENT": [None] * 6,
                      "DISOTRA_C": [None, None, "299", "960", "430", None],
                      "DISOTRA_V": [None] * 6,
                      "DISNOTIE": ["8", None, None, None, None, None]})
    without, with_, unknown, types = ck._disability_2000(p)
    assert without.tolist() == [True] + [False] * 5
    assert unknown.tolist() == [False, True, False, False, False, False]
    assert with_.tolist() == [False, False, True, True, True, True]
    assert types["motor"].tolist() == [False, False, True, False, False, True]
    assert types["type NE"].tolist() == [False, False, False, True, False, False]  # with 3
    assert types["other"].tolist() == [False] * 4 + [True, False]


def test_households_and_education_2000():
    """7l: CGPV 2000's household rows by size, type and income in minimum wages (999999 not
    specified, 999998 the top code), the averages from the attached members, the sexes in
    columns of C2KED02/04/06, the age groups by an item's codes."""
    h = pd.DataFrame({"TOTPERS": ["1", "9", "3"], "TIPOHOG": ["5", "2", "9"],
                      "ENT": ["01", "01", "01"], "MUN": ["001", "001", "001"],
                      "INGTRHOG": ["0", "999998", "999999"],
                      "_HEAD_AGE": [40, 999, 60], "_UNDER12": [0, 4, 1], "_12TO64": [1, 5, 1],
                      "_65PLUS": [0, 0, 1], "_PEA": [1, 3, 0], "_PEI": [0, 2, 2],
                      "_EMPLOYED": [1, 3, 0], "FACTOR": ["1", "1", "2"]})
    size = [num.tolist() for num, _ in ck._ho01(h)]
    assert size[0] == [True, False, False] and size[8] == [False, True, False]
    kind = [num.tolist() for num, _ in ck._ho02(h)]
    assert kind[5] == [True, False, False] and kind[8] == [False, False, True]
    income = [num.tolist() for num, _ in ck._household_income("INGTRHOG")(h)]
    assert income[0] == [True, False, False] and income[6] == [False, True, False]
    assert income[7] == [False, False, True]
    w = pd.to_numeric(h["FACTOR"]).astype(float)
    every = pd.Series(True, index=h.index)
    sums = [(ck._part(n, w, every, 1)[1], ck._part(d, w, every, 1)[1]) for n, d in ck._ho08(h)]
    assert sums[0] == (16.0, 4.0) and sums[1] == (160.0, 3.0)        # the head of age 999 out
    assert ck._household_persons(h).tolist() == [1.0, 9.0, 6.0]
    rows = [{"A": "01 AGUASCALIENTES", "B": "10", "E": "90", "F": "88", "G": "92", "H": "10",
             "I": "12", "J": "8"},
            {"A": "6 - 9   AÑOS", "B": "4", "E": "80", "F": "79", "G": "81", "H": "20",
             "I": "21", "J": "19"}]
    read = ck._c2k_rows_by_sex({"T": "EH", "H": "FI", "M": "GJ"})({"x": rows})
    assert read == {(1, "T"): [90, 10, 80, 20], (1, "H"): [88, 12, 79, 21],
                    (1, "M"): [92, 8, 81, 19]}
    p = pd.DataFrame({"EDAD": ["007", "012", "040"], "ASISTEN": ["2", "1", "2"],
                      "ABANESCO": ["0", None, "5"]})
    cells = [num.tolist() for num, _ in ck._by_age_2000(
        "ABANESCO", ((7, 29), (7, 9)), (0, tuple(range(1, 9)), 9),
        universe=lambda q: ck._code(q, "ASISTEN").eq(2))(p)]
    assert cells[0] == [True, False, False] and cells[1] == [False] * 3        # 40: not 7-29
    assert cells[3] == [True, False, False]


def test_rates_tgf_and_national_rows():
    """7o: unit «rate» = per 1,000; ``_with_tgf`` appends each block's Tasa Global de
    Fecundidad (5 × Σ rates / 1,000); ``_national`` reads the rows of a national tabulado by
    locality size (and the mother's age) in the given order, a missing row raises."""
    assert ck._value(3.0, 1500.0, "rate") == 2.0 and np.isnan(ck._value(1.0, 0.0, "rate"))
    assert ck._with_tgf([10.0] * 7 + [20.0] * 7) == [10.0] * 7 + [0.35] + [20.0] * 7 + [0.7]
    rows = [{"A": "Tamaño de localidad", "B": "Grupos de edad de la madre", "C": "Estimador",
             "D": "Tasa"},
            {"A": "Estados Unidos Mexicanos", "B": "Total", "C": "Valor", "D": "6.5"},
            {"A": "Estados Unidos Mexicanos", "B": "Total", "C": "Error estándar", "D": "0.1"},
            {"A": "1-2 499 habitantes ", "B": "12-19 años", "C": "Valor", "D": "7.25"}]
    read = ck._national("Valor", (("1-2 499 habitantes", "12-19 años"),
                                  ("Estados Unidos Mexicanos", "Total")))
    assert read({"x": rows}) == {(0, "T"): [7.25, 6.5]}
    with pytest.raises(KeyError):
        ck._national("Valor", (("100 000 y más habitantes", "Total"),))({"x": rows})


def test_fertility_rates_and_infant_mortality():
    """7o: the women whose last child was born the year before over the women of the age
    whose fertility is known (not 98, the topic omitted, nor the year 9999; 99 counts); the
    infant deaths of those last children — 2020 by ``EDAD_MORIR_TD`` 0–364, 2010/2015 every
    death not aged in years — by locality size and the mother's age («Total» = 12–49)."""
    p = pd.DataFrame({
        "SEXO": ["3", "3", "3", "3", "3", "1", "3", "3"],
        "EDAD": ["017", "016", "018", "019", "015", "017", "050", "025"],
        "HIJOS_NAC_VIVOS": ["01", "98", "99", "02", None, "01", "01", "01"],
        "FECHA_NAC_A": ["2019", None, None, "9999", None, "2019", "2019", "2019"],
        "SOBREVIVENCIA": ["3", None, None, None, None, "3", "3", "1"],
        "EDAD_MORIR_TD": ["010", None, None, None, None, "010", "999", None],
        "EDAD_MORIR_A": [None] * 8, "TAMLOC": ["1", "1", "2", "1", "5", "1", "1", "5"]})
    fifteen = ck._fertility_rates("2020")(p)[0]
    assert fifteen[0].tolist() == [True] + [False] * 7
    assert fifteen[1].tolist() == [True, False, True, False, True, False, False, False]
    by_size = ck._fertility_rates("2020", by_size=True)(p)
    assert len(by_size) == 6 * 7 and by_size[7][1].tolist() == [True] + [False] * 7  # size 1
    cells = ck._infant_mortality("2020")(p)
    assert len(cells) == 6 * 4
    assert cells[0][0].tolist() == [True] + [False] * 7               # nation, mothers 12-49
    assert cells[0][1].tolist() == [True] + [False] * 6 + [True]      # the 50-year-old out
    assert cells[2][1].tolist() == [False] * 7 + [True]                # 20-34
    q = p.assign(EDAD_MORIR_TD=None, EDAD_MORIR_A=[None, None, None, None, None, None, "1",
                                                   None], FECHA_NAC_A=p["FECHA_NAC_A"].replace(
        "2019", "2014"), TAMLOC=["1", "1", "2", "1", "5", "1", "1", "5"])
    q.loc[6, "EDAD"] = "030"
    cells = ck._infant_mortality("2015")(q)
    assert cells[0][0].tolist() == [True] + [False] * 7               # aged in years: out
    assert cells[0][1].tolist() == [True] + [False] * 5 + [True, True]
    r = pd.DataFrame({"SEXO": ["3", "3"], "EDAD": ["020", "020"], "tam_loc": ["04", "01"],
                      "FECNACA": ["2009", "2009"], "SOBREVI": ["3", "3"],
                      "EDAMORA": [None, None]})
    last = ck._infant_mortality("2010")(r)[-4:]                    # 100 000 y más (04)
    assert [n.tolist() for n, _ in last] == [[True, False], [False, False], [True, False],
                                             [False, False]]


def test_disability_causes_2020():
    """7p: a disability is 3, 4 or 8 in an activity; a limitation 2, only without a
    disability elsewhere; a cause counts each person once, for any difficulty of the kind;
    a mental condition's «other» holds the accident and the old age."""
    items = {i: ["1"] * 4 for i in ck._DIS_ITEMS_2020}
    causes = {i.replace("DIS_", "CAU_"): [None] * 4 for i in ck._DIS_ITEMS_2020}
    p = pd.DataFrame({**items, **causes, "DIS_MENTAL": ["6", "5", "6", "9"],
                      "CAU_MENTAL": [None, "4", None, None],
                      "DISCAPACIDAD": ["Sí", "No", "No", "No especificado"],
                      "LIMITACION": ["No", "Sí", "No", "No especificado"],
                      "SIN_DISC_LIM": ["No", "No", "Sí", "No especificado"]})
    # person 0: cannot see (birth) and some difficulty hearing (illness): disabled only;
    # person 1: some difficulty walking and talking, both from an accident: limited once
    p.loc[0, ["DIS_VER", "CAU_VER", "DIS_OIR", "CAU_OIR"]] = ["4", "1", "2", "2"]
    p.loc[1, ["DIS_CAMINAR", "CAU_CAMINAR", "DIS_HABLAR", "CAU_HABLAR"]] = ["2", "3", "2", "3"]
    cells = dict(zip(ck._DIS_CELLS, (m.tolist() for m in ck._disability_cells_2020(p))))
    assert cells["any"] == [True, True, False, False] and cells["NE"] == [False] * 3 + [True]
    assert cells["disability: birth"] == [True, False, False, False]
    assert cells["disability: illness"] == [False] * 4             # its hearing: a limitation
    assert cells["limitation: accident"] == [False, True, False, False]
    assert cells["mental: other"] == [False, True, False, False]
    by_activity = ck._disability_by_activity_2020(p)
    assert len(by_activity) == 7 * 3 * 7
    hearing = by_activity[2 * 21:3 * 21]                              # «Oír»: either, dis, lim
    assert [m.tolist() for m, _ in hearing[::7]] == [[False] * 4] * 3


def test_migration_duration_and_causes_2020():
    """7p: the months between the emigration and the return (a date not specified: none);
    the causes' precoded answers, 9999 not specified, every other code «other»."""
    m = pd.DataFrame({"MPAIRES": ["3", "3", "3", "1"],
                      "MFECEMIA": ["2018", "2016", "9999", "2019"],
                      "MFECEMIM": ["11", "03", "01", "02"],
                      "MFECRETA": ["2019", "2019", "2019", None],
                      "MFECRETM": ["05", "02", "01", None],
                      "MCAUSARETO_V": ["0102", "0801", "9999", None],
                      "MCAUSAEMIG_V": ["0301", "0103", "0801", "0501"]})
    assert ck._duration_2020(m).tolist()[:2] == [6.0, 35.0]
    assert ck._duration_2020(m).isna().tolist() == [False, False, True, True]
    cells = [x.tolist() for x, _ in ck._return_duration_2020(m)]
    assert cells == [[True, True, True, False], [True, False, False, False],
                     [True, False, False, False], [False] * 4, [False, True, False, False],
                     [False] * 4, [False, False, True, False]]
    back = lambda f: ck._code(f, "MPAIRES").eq(3)  # noqa: E731
    ret = ck._migration_causes_2020("MCAUSARETO_V", back, (*ck._CAUSES_2020, ck._DEPORTED_2020))
    assert [x.tolist() for x in ret(m)][1:] == [
        [True, False, False, False], [False] * 4, [False] * 4, [False, True, False, False],
        [False] * 4, [False, False, True, False]]
    every = lambda f: pd.Series(True, index=f.index)  # noqa: E731
    emi = ck._migration_causes_2020("MCAUSAEMIG_V", every, ck._CAUSES_2020)(m)
    assert [x.tolist() for x in emi][1:] == [[False] * 4, [True, False, False, False],
                                             [False, False, False, True],
                                             [False, True, True, False], [False] * 4]


def test_kinship_fields_and_selected_states_2010():
    """7p: 12_04A's lines on ``PARENT`` and «otro parentesco»'s detail; 07_02A's fields =
    ``NOMCAR_C``'s first digit; 05_01A's unpublished states count together in 98."""
    p = pd.DataFrame({"PARENT": ["01", "08", "08", "08", "08", "08", "06", "04", "99", "09"],
                      "OTROPARE_C": [None, "612", "613", "603", None, "623", None, "609",
                                     "999", "501"]})
    lines = [m.tolist() for m in ck._kinship_2010(p)]
    assert [ck._KINSHIP[[ln[i] for ln in lines].index(True)] for i in range(10)] == [
        "head", "ascendants", "descendants", "collaterals", "collaterals", "NE", "ascendants",
        "descendants", "NE", "not related"]
    assert all(sum(ln[i] for ln in lines) == 1 for i in range(10))
    q = pd.DataFrame({"EDAD": ["030", "017", "040", "050", "040"],
                      "NIVACAD": ["10", "10", "07", "08", "11"],
                      "NOMCAR_C": ["311", "311", "511", "999", "800"]})
    fields = [m.tolist() for m, _ in ck._fields_2010(ck._superior_2010)(q)]
    assert fields[0] == [True, False, False, True, True]
    assert fields[3] == [True, False, False, False, False]
    assert fields[9] == [False, False, False, True, True]          # 800: no field
    assert not fields[8][4]
    r = pd.DataFrame({"ENT": ["20", "01", "15"], "EDAD": ["030"] * 3, "HLENGUA": ["1", "3", "1"],
                      "PERETN": ["1", "3", "9"]})
    parts = ck._selected_states_2010(ck._self_identification("PERETN"))(r)
    assert parts[0][0].origin.tolist() == [20, 98, 15]


def test_eic2015_layouts_and_cells_7v():
    """7v: the sexes in columns (a category's share of the total, then the sexes' shares of
    it), one-year ages and the head's age, a sex after another dimension, «45- 54 años»;
    técnica after primaria = primaria with six grades; the benefits' «without» (all seven
    «no») and «not specified» (no «yes», some 9)."""
    assert ck._sex_columns((3, 1))([100, 40, 60, 50, 30, 70, 10]) == [100, 40, 60, 50, 15, 35, 10]
    p = pd.DataFrame({"SEXO": ["1", "3", "3"], "EDAD": ["3", "14", "999"],
                      "JEFE_EDAD": ["20", "75", "999"]})
    cells = [m.tolist() for m, _ in ck._sexed(p, pd.Series([True, True, False]),
                                              ((pd.Series([True, False, True]), 3),))]
    assert cells == [[True, True, False], [True, False, False], [False, True, False],
                     [True, False, False], [True, False, False], [False, False, False]]
    assert ck._age_group(p, "03 años").tolist() == [True, False, False]
    assert ck._age_group(p, "75 años y más", "JEFE_EDAD").tolist() == [False, True, False]
    assert ck._dim(" 45- 54 años ") == "45-54 años"
    # the numeric columns are converted once per frame (a copy is another frame)
    assert ck._numeric(p, "EDAD") is ck._numeric(p, "EDAD")
    other = p.assign(EDAD=["4", "14", "999"])
    assert ck._numeric(other, "EDAD").tolist() == [4, 14, 999]
    assert ck._numeric(p, "EDAD").tolist() == [3, 14, 999]
    assert ck._cat(p, "SEXO") is ck._cat(p, "SEXO") and ck._cat(p, "SEXO").dtype == object
    # the sums on arrays: a missing mask value is False, a missing weight skipped (as pandas)
    w = pd.Series([1.0, 2.0, np.nan, 8.0])
    mask = pd.Series([True, pd.NA, True, True], dtype="boolean")
    keep = pd.Series(True, index=w.index)
    assert ck._part(mask, w, keep, 1) == {1: float(w[mask].sum())} == {1: 9.0}
    ck._CONVERTED.clear()
    rows = [{"A": "Entidad federativa", "B": "Lugar de nacimiento", "C": "Sexo", "D": "Estimador",
             "E": "Población"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Hombres", "D": "Valor", "E": "7"},
            {"A": "01 Aguascalientes", "B": "En otro país", "C": "Hombres", "D": "Valor", "E": "2"}]
    read = ck._by_dims("Valor", None, ("Total", "En otro país", "En Marte"), lambda v: v,
                       sexed=True, sex_at=1)
    assert read({"x": rows}) == {(1, "H"): [7.0, 2.0, 0.0]}
    q = pd.DataFrame({"EDAD": ["20"] * 6, "NIVACAD": ["2", "2", "6", "7", "0", "99"],
                      "ESCOLARI": ["5", "6", "2", "1", "0", "99"]})
    cells = dict(zip(ck._PRIMARY_CELLS, (m.tolist() for m, _ in
                                          ck._schooling_2015(3, ("Total",))(q))))
    assert cells["primaria: 6 grades"] == [False, True, True, False, False, False]
    assert cells["primaria"] == [True, True, True, False, False, False]
    assert cells["posbásica"] == [False, False, False, True, False, False]
    assert cells["no schooling"] == [False] * 4 + [True, False]
    benefits = {col: ["2", "2", "9", "9"] for _, col, _ in ck._BENEFITS_2015}
    benefits["AGUINALDO"] = ["1", "2", "2", "9"]
    r = pd.DataFrame({**benefits, "EDAD": ["30"] * 4, "SITUACION_TRAB": ["1"] * 4,
                      "OCUPACION_C_COARSE": ["11"] * 4, "ACTIVIDADES_C_COARSE": ["43"] * 4})
    r["OCUPACION_C_COARSE"] = r["OCUPACION_C_COARSE"].astype("category")
    totals = [m.tolist() for m, _ in ck._benefits_2015(r)[:11]]
    assert totals[1] == [True, False, False, False] and totals[3] == [True, False, False, False]
    assert totals[9] == [False, True, False, False] and totals[10] == [False, False, True, True]


def test_eic2015_languages_and_migration_7v():
    """7v: 05-03's rows (a state's «Total» count, its languages' percentages; a language not
    listed is nobody); 04-06's base (here now, in an entity of Mexico in 2010), immigrants
    here, emigrants in their 2010 entity; the transcribed catalog = INEGI's, when cached."""
    rows = [{"A": "01 Aguascalientes", "B": "Total", "C": "200"},
            {"A": "01 Aguascalientes", "B": "Náhuatl", "C": "25"},
            {"A": "01 Aguascalientes", "B": "", "C": ""}]
    pub = ck._language_shares_published({"03": rows})[1, "T"]
    names = list(ck._LANGUAGES_2015.values())
    assert pub[0] == 200 and pub[1 + names.index("Náhuatl")] == 50 and sum(pub[1:]) == 50
    p = pd.DataFrame({"ENT": ["09", "09", "09", "09"], "EDAD": ["30", "30", "3", "30"],
                      "LUGAR_RES_5A": ["Mismo municipio", "Otra entidad", "Blanco por pase",
                                       "Estados Unidos"],
                      "ENT_PAIS_RES10": ["009", "015", None, "221"]})
    lived, immigrants, emigrants = (c for c, _ in ck._internal_migration_2015(p))
    assert lived.tolist() == [True, True, False, False]           # counted where they live
    assert immigrants.tolist() == [False, True, False, False]
    assert emigrants.origin[emigrants.mask].tolist() == [15]
    catalog = _ROOT / "data" / "dict" / "fd" / "2015" / "eic2015_catalogos.zip"
    if catalog.exists():
        import zipfile
        import _dict_fd as fd
        with zipfile.ZipFile(catalog) as z:
            wb = fd.read_xls(z.read("TC_LENGUA_INDIGENA_INALI_2015.xls"))
        assert {r["A"]: r["B"] for r in next(iter(wb.values()))[1:]} == ck._LANGUAGES_2015


def test_census2020_rules_7w():
    """7w: Censo 2020's kinship lines, the parents of the 0–17 (99 over 98 over the rest; a row
    lives here, 96 elsewhere, 97 died), the hours (0 = did not work, 32 | 33, 999), the técnica
    of media superior (``NIVACAD`` 05/07/09, 15+) by field, the cross tables' order, the
    partner by union and the food access by the head's sex."""
    p = pd.DataFrame({"PARENTESCO": ["101", "203", "304", "416", "421", "410", "418", "417",
                                     "423", "424", "601", "701", "999"]})
    lines = [m.tolist() for m, _ in ck._lines_2020(p)]
    assert lines[0] == [True] * 13
    assert [sum(m) for m in lines[1:]] == [1, 1, 1, 2, 2, 2, 1, 2, 1]
    assert lines[4][3:5] == [True, True] and lines[5][5:7] == [True, True]   # 416/421, 410/418
    assert lines[6][7:9] == [True, True] and lines[8][10:12] == [True, True]  # 417/423, 601/701
    q = pd.DataFrame({"EDAD": ["5", "5", "5", "5", "5", "5", "5", "18"],
                      "IDENT_MADRE": ["02", "02", "96", "97", "98", "99", "98", "02"],
                      "IDENT_PADRE": ["03", "97", "01", "96", "02", "98", "99", "03"]})
    res = [m.tolist() for m, _ in ck._parents_2020(survival=False)(q)]
    viv = [m.tolist() for m, _ in ck._parents_2020(survival=True)(q)]
    assert res[0] == [True] * 7 + [False]                                   # 0–17 only
    assert [r.index(True) if True in r else None for r in zip(*res[1:])][:7] == [
        0, 1, 2, 3, 4, 5, 5]                         # both, mother, father, neither, 98, 99, 99
    assert [r.index(True) for r in list(zip(*viv[1:]))[:4]] == [0, 1, 0, 2]  # 96 is alive
    e = pd.DataFrame({"HORTRA": ["0", "32", "33", "57", "999"], "EDAD": ["30"] * 5})
    hours = [m.tolist() for m in ck._hours_2020(e, pd.Series(True, index=e.index))]
    assert [h.index(True) for h in zip(*hours[1:])] == [5, 0, 1, 4, 6]
    t = pd.DataFrame({"EDAD": ["15", "15", "15", "15", "14"],
                      "NIVACAD": ["05", "07", "09", "08", "07"],
                      "NOMCAR_C": ["0111", "1011", "9999", "0411", "0411"]})
    tech = [m.tolist() for m, _ in ck._technical_2020(t)]
    assert tech[0] == [True, True, True, False, False]
    assert tech[1][0] and tech[10][1] and tech[11][2] and not any(tech[4])  # 01, 10, 9999
    r = pd.DataFrame({"x": [1, 2]})
    crossed = ck._cross(lambda f: pd.Series(True, index=f.index),
                        lambda f, u: [u, u & f["x"].eq(1)],
                        lambda f, g: [g, g & f["x"].eq(2)])(r)
    assert [m.tolist() for m, _ in crossed] == [[True, True], [False, True], [True, False],
                                                [False, False]]
    assert ck._position_names(3)[:2] == ("Total", "Trabajadores asalariados3")
    s = pd.DataFrame({"EDAD": ["30"] * 3, "SITUA_CONYUGAL_CAT": ["casado"] * 3,
                      "SITUA_CONYUGAL": ["7", "1", "5"], "IDENT_PAREJA_CAT": ["Sí", "No", "Sí"]})
    partner = [m.tolist() for m, _ in ck._partner(s)]
    assert partner[4] == [True, False, True] and partner[8] == [False, True, False]
    assert partner[10] == [False, True, False]                      # free union, elsewhere
    v = pd.DataFrame({"JEFE_SEXO": ["1", "3", "3"], "ALIMENTACION": ["1", "3", "9"]})
    food = [m.tolist() for m, _ in ck._food_access_2020(v)]
    assert food[:4] == [[True] * 3, [True, False, False], [False, True, False],
                        [False, False, True]]
    assert food[8:] == [[False, True, True], [False, False, False], [False, True, False],
                        [False, False, True]]
    ck._CONVERTED.clear()


def test_census2010_rules_7x(monkeypatch):
    """7x: the international migrants' unspecified state left (99), their destination, the
    limited by type and cause, the 12+'s other incomes by household size, the food access of
    every dwelling, the SCIAN sectors' two layouts and 10_01A's PDF."""
    rows = [{"A": "Entidad federativa expulsora", "B": "Estimador", "C": "Total"},
            {"A": "No especificado", "B": "Parámetro", "C": "5"},
            {"A": "01 Aguascalientes", "B": "Parámetro", "C": "7"}]
    assert ck._estimates(rows, "Parámetro") == {(99,): [5.0], (1,): [7.0]}
    rows[0] = {**rows[0], "A": "Entidad federativa expusora"}      # 04_05A's spelling
    assert ck._estimates(rows, "Parámetro") == {(99,): [5.0], (1,): [7.0]}
    rows[0] = {**rows[0], "A": "Entidad federativa"}
    assert ck._estimates(rows, "Parámetro") == {(1,): [7.0]}        # a state of residence
    m = pd.DataFrame({"MPDESOTR_C": ["221", "213", "999", None, "600"]})
    dest = [x.tolist() for x in ck._destination_of("MPDESOTR_C")(m)]
    assert dest[1:] == [[True, False, False, False, False], [False, True, False, False, True],
                        [False, False, True, True, False]]
    p = pd.DataFrame({"LIM_ACTIVIDAD": ["Sí", "Sí", "No"],
                      **{f"DISCAP{k}": [None] * 3 for k in range(1, 8)},
                      **{f"CAUSADIS{k}": [None] * 3 for k in range(1, 8)}})
    p.loc[0, ["DISCAP1", "CAUSADIS1", "DISCAP2", "CAUSADIS2"]] = ["10", "2", "11", "4"]
    p.loc[1, ["DISCAP4", "CAUSADIS4"]] = ["13", "9"]
    lim = [x.tolist() for x, _ in ck._limitation_by_type_2010(p)]
    assert lim[0] == [True, True, False] and lim[2] == lim[4] == [True, False, False]
    assert lim[6] == [False, True, False]                           # any limitation's cause
    assert lim[9] == lim[14] == lim[18] == [True, False, False]     # walking's illness,
    #                                                                 seeing and its old age
    assert lim[21] == lim[27] == [False, True, False]               # hearing (4), cause NE
    q = pd.DataFrame({"EDAD": ["30", "12", "5", "70"], "AYUPROGOB": ["1", "2", "2", "2"],
                      "AYUJUBPEN": ["4", "4", None, "9"], "AYUPEDP": ["4", "4", None, "4"],
                      "AYUPEOP": ["2", "2", None, "2"], "AYUOTRFTE": ["2", "2", None, "2"]},
                     index=pd.MultiIndex.from_tuples([(1, 1), (1, 2), (1, 3), (2, 1)],
                                                     names=["ID_VIV", "ID_PER"]))
    inc = [x.tolist() for x, _ in ck._other_incomes_2010(q)]
    assert inc[0] == [True, True, False, True] and inc[2] == [True, False, False, False]
    assert inc[7] == [False, True, False, False] and inc[8] == [False, False, False, True]
    assert inc[9] == [False, False, False, True] and inc[18] == [True, True, False, False]
    v = pd.DataFrame({"CLAVIVP": ["1", "5", "7"], "COMIO1VEZ": ["1", "2", None],
                      "NOCOMI1D": ["4", "4", None], "SINCOMER": ["2", "2", None]})
    food = [x.tolist() for x, _ in ck._food_2010(v)]
    assert food[:4] == [[True] * 3, [True, False, False], [False, True, False],
                        [False, False, True]]                       # the locale (5) counts
    names = [n for n, _ in ck._SCIAN_2010]
    head = {"A": "Sexo", "B": "Sector de actividad económica", "C": "Estimador", "D": "Total"}
    sheet = [head, *({"A": "Total", "B": n, "C": "Parámetro",
                      **dict(zip("DEFGH", ("100", "20", "20", "20", "40") if n == "Total"
                                 else ("10",) * 5))} for n in names)]
    by_size = ck._scian_published(of_size=True)({"s": sheet})[0, "T"]
    assert by_size[:10] == [100, 20, 20, 20, 40, 10, 2, 2, 2, 4] and len(by_size) == 110
    assert ck._scian_published(of_size=False)({"s": sheet})[0, "T"][5:10] == [10, 1, 1, 1, 1]
    text = ("  Población de 12 años y más actualmente unida   Situación conyugal 1\n"
            "   Estados Unidos Mexicanos        46 879 066      95.37      2.94     1.69\n"
            "      Casado(a)                    34 620 467      95.98      2.69     1.33\n"
            "       Civil y religiosamente      22 090 166      96.66      2.25     1.08\n"
            "   Hombres                         23 173 962      96.46      1.94     1.60\n"
            "www.inegi.org.mx\n"
            "  2 500-14 999 habitantes           6 778 592      95.42      2.82     1.76\n")
    monkeypatch.setattr(ck.fd, "pdf_text", lambda path: text)
    pdf = ck._unions_pdf(Path("10_01A_ESTATAL.pdf"))
    rows = pdf["10_01A_ESTATAL"]
    assert [(r["A"], r["B"], r["C"], r["D"], r["F"]) for r in rows[1:]] == [
        ("Estados Unidos Mexicanos", "Total", "Total", "Total", "46879066"),
        ("Estados Unidos Mexicanos", "Total", "Casado(a)", "Total", "34620467"),
        ("Estados Unidos Mexicanos", "Total", "Casado(a)", "Civil y religiosamente", "22090166"),
        ("Estados Unidos Mexicanos", "Hombres", "Total", "Total", "23173962"),
        ("2 500-14 999 habitantes", "Total", "Total", "Total", "6778592")]
    assert ck._estimates(rows, "Parámetro")[0, "H", "Total", "Total"] == [23173962, 96.46, 1.94,
                                                                         1.6]
    s = pd.DataFrame({"EDAD": ["30"] * 3, "ESTCON": ["5", "1", "8"],
                      "IDENT_PAREJA_CAT": ["Sí", "No", "Blanco por pase"]})
    shares = ck._spouse_shares_2010(s)
    assert len(shares) == 18 and shares[0][1].tolist() == [True, True, False]
    assert shares[0][0].tolist() == [True, False, False] and shares[1][0].tolist() == [
        False, True, False]
    ck._CONVERTED.clear()


def test_eic2015_rows_7x(monkeypatch, tmp_path):
    """7x: the EIC 2015's birthplace abroad split, 06-11's raw levels and average schooling,
    the raw marital status, the households by class per the head's sex and the dwelling's
    items on the persons."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from mxcensus.data import _registry

    p = pd.DataFrame({"ENT_PAIS_NAC_INEGI": ["EstaEnt", "OtroPais", "OtroPais",
                                             "No especificado"],
                      "ENT_PAIS_NAC": ["1", "221", "213", "997"]})
    born = [m.tolist() for m, _ in ck._birthplace_2015(p)]
    assert born[3:5] == [[False, True, False, False], [False, False, True, False]]
    e = pd.DataFrame({"EDAD": ["20", "30", "40", "16", "18", "25", "50", "60", "14"],
                      "NIVACAD": ["0", "1", "6", "3", "3", "9", "12", "99", "2"],
                      "ESCOLARI": [None, None, "6", "2", "99", "3", "4", "99", "6"],
                      "ESCOACUM": ["0", "0", "12", "8", "99", "12", "20", "99", "6"]})
    detail = [m.tolist() for m, _ in ck._schooling_detail_2015(("Total",))(e)]
    assert [sum(m) for m in detail] == [8, 1, 4, 1, 1, 2, 1, 0, 1, 1, 1, 1]
    assert detail[4][2] and detail[6][3] and detail[8][4]           # técnica after primaria
    num, den = ck._schooling_years_2015(("Total",))(e)[0]
    assert den.tolist() == [True, True, True, True, False, True, True, False, False]
    w = pd.Series(1.0, index=e.index)
    assert ck._part(num, w, w.astype(bool), 1)[1] / den.sum() == pytest.approx(52 / 6)
    m = pd.DataFrame({"EDAD": ["30"] * 7, "SITUA_CONYUGAL": ["6", "5", "1", "2", "3", "4", "9"]})
    marital = [x.tolist() for x, _ in ck._marital_2015(("Total",))(m)]
    assert [r.index(True) for r in zip(*marital[1:])] == list(range(7))
    rows = [{"A": "Entidad federativa", "B": "Sexo del jefe o la jefa",
             "C": "Hogares/Población en hogares", "D": "Estimador", "E": "Total"},
            *({"A": "01 Aguascalientes", "B": head, "C": kind, "D": "Valor",
               **dict(zip("EFGHIJKLMN", [str(n)] + ["10"] * 9))}
              for head, n in (("Mujeres", 30), ("Total", 100), ("Hombres", 70))
              for kind in ("Hogares", "Población en hogares"))]
    out = ck._household_class_published("Hogares")({"05": rows})[1, "T"]
    assert len(out) == 30 and out[::10] == [100, 70, 30]
    dwellings = pa.table({"ID_VIV": ["10010000001", "10010000002"], "TIPOHOG": ["1", "5"],
                          "CLAVIVP": ["1", "4"]})
    pq.write_table(dwellings, tmp_path / "cpv_viviendas_2015_01.parquet")
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda name, **kw: str(tmp_path / name))
    q = pd.DataFrame({"SEXO": ["1", "3", "3"]}, index=pd.MultiIndex.from_tuples(
        [("010010000001", "1"), ("010010000001", "2"), ("010010000002", "1")],
        names=["ID_VIV", "ID_PERSONA"]))
    out = ck._with_dwelling(q, "2015", 1, ("TIPOHOG", "CLAVIVP"))
    assert out["TIPOHOG"].tolist() == ["1", "1", "5"] and out["CLAVIVP"].tolist()[2] == "4"
    occupants = [x.tolist() for x, _ in ck._occupants_by_sex_2015(out)]
    assert occupants[:3] == [[True] * 3, [True, False, False], [False, True, True]]
    assert occupants[3:6] == [[True, True, False], [True, False, False], [False, True, False]]
    ck._CONVERTED.clear()


def test_census2020_last_cells_7y():
    """7y: Censo 2020's last cells — the unspecified age (a state without one publishes no
    row: zeros), the superior's fields, the employed before their divisions and sectors, the
    use of health services per affiliation and institution."""
    assert ck._QUIN_2020[-1] == ck._REGISTRATION_AGES_2020[-1] == "No especificado"
    head = {"A": "Entidad federativa", "B": "Grupos de edad", "C": "Estimador", "D": "Total"}
    rows = [head, {"A": "01 Aguascalientes", "B": "Total", "C": "Valor", "D": "9"},
            {"A": "01 Aguascalientes", "B": "No especificado", "C": "Valor", "D": "2"},
            {"A": "02 Baja California", "B": "Total", "C": "Valor", "D": "5"}]
    read = ck._by_dims("Valor", "02", ("Total", "No especificado"), lambda v: v)
    assert read({"02": rows}) == {(1, "T"): [9, 2], (2, "T"): [5, 0.0]}
    p = pd.DataFrame({"EDAD": ["25", "40", "17", "30", "30"],
                      "EDUC_INEGI_DET": ["Superior", "Posgrado", "Superior", "Superior",
                                         "Media_superior"],
                      "NOMCAR_C": ["0411", "1021", "0411", "9999", "0411"]})
    sup = [m.tolist() for m, _ in ck._superior(p)]
    assert len(sup) == 12 and sup[0] == [True, True, False, True, False]
    assert sup[4][0] and sup[10][1] and sup[11][3] and sum(map(sum, sup[1:])) == 3
    p = pd.DataFrame({"EDAD": ["30"] * 4, "SERSALUD": ["01", "08", "10", "99"],
                      "DHSERSAL_AFIL": [1, 1, 0, 0], "DHSERSAL_No afiliado": [0, 0, 1, 0],
                      "DHSERSAL_IMSS": [1, 1, 0, 0], "DHSERSAL_ISSSTE": [0] * 4,
                      "DHSERSAL_ISSSTE_E": [0, 1, 0, 0],
                      **{f"DHSERSAL_{c}": [0] * 4 for c in (
                          "P_D_M", "SALUD_PUBLICA", "IMSS_BIENESTAR", "Otro")},
                      "DHSERSAL_Privado": [0, 1, 0, 0]})
    use = [m.tolist() for m, _ in ck._use_by_affiliation_2020(p)]
    assert len(use) == len(ck._AFFILIATION_NAMES_2020) * len(ck._USE_CELLS_2020) == 132
    block = lambda i: use[12 * i:12 * (i + 1)]  # noqa: E731
    assert block(0)[0] == [True] * 4 and block(0)[1] == [True, True, False, False]
    assert block(0)[2] == [True, False, False, False] and block(0)[8] == [False, True, False,
                                                                          False]  # pharmacy
    assert block(0)[10:] == [[False, False, True, False], [False, False, False, True]]
    assert block(2)[0] == [True, True, False, False]                 # IMSS: both
    assert block(3)[0] == [False, True, False, False]                # ISSSTE estatal too
    assert block(7)[0] == [False, True, False, False] and block(9)[0] == [False, False, True,
                                                                          False]
    assert block(10)[0] == [False, False, False, True]               # not specified
    head = {"A": "Entidad federativa", "B": "Condición de afiliación", "C": "Institución",
            "D": "Estimador", "E": "Población", **{c: c for c in "FGHIJKLMNOP"}}
    sheet = [head, *({"A": "01 Aguascalientes", "B": a, "C": i + ("4" if i == "ISSSTE" else ""),
                      "D": "Valor", "E": "200", "F": "90", **dict.fromkeys("GHIJKLMN", "12.5"),
                      "O": "5", "P": "5"} for a, i in ck._AFFILIATION_ROWS)]
    pub = ck._by_affiliation("Valor", "04", ck._AFFILIATION_ROWS,
                             lambda v: ck._counts(v[0], v[1:], [0, *[1] * 8, 0, 0]))
    got = pub({"04": sheet})[1, "T"]
    assert len(got) == 132 and got[:12] == [200, 180, *[22.5] * 8, 10, 10]
    assert [c.cells[0] for c in ck.CHECKS if c.period == "2020" and c.key in (
        "08-06", "08-08")] == ["employed", "employed"]
    ck._CONVERTED.clear()


def test_coverage_traces_values(monkeypatch):
    """7y: :func:`coverage` traces each published value through a check's reader — a total
    read only into counts from its percentages is read, a value no compared cell comes from
    (or only a missing one) is not; the reader's ``_num`` is restored."""
    head = {"A": "Entidad federativa", "B": "Estimador", "C": "Total", "D": "Sí", "E": "No"}
    sheet = [{"A": "Título"}, head,
             {"A": "01 Aguascalientes", "B": "Valor", "C": "200", "D": "60", "E": "40"},
             {"A": "01 Aguascalientes", "B": "Error estándar", "C": "9", "D": "1", "E": "1"},
             {"A": "02 Baja California", "B": "Valor", "C": "50", "D": "", "E": "M.I."}]
    monkeypatch.setattr(ck, "_workbook", lambda path: {"04": sheet})
    check = ck.Check("2020", "x", "x", "x.xlsx", "personas", ("yes",),
                     ck._wide("Valor", lambda v: ck._counts(v[0], v[1:])[1:2], sheet="04",
                              dims=lambda k: (k[0], "T")),
                     None, unit="persons", sheet="04")
    plain = ck._num
    found = ck.coverage("2020", {"2020/x.xlsx": Path("x.xlsx")}, (check,))
    assert ck._num is plain
    assert found == {("x.xlsx", "04"): [(("01 Aguascalientes",), "No"),   # 200, 60 read
                                        (("02 Baja California",), "Total")]}  # into NaN only
    every = replace(check, published=ck._wide("Valor", lambda v: ck._counts(v[0], v[1:]),
                                              sheet="04", dims=lambda k: (k[0], "T")))
    assert ck.coverage("2020", {"2020/x.xlsx": Path("x.xlsx")}, (every,)) == {}
    t = ck._Traced(3.0, frozenset({1})) * 2 + ck._Traced(1.0, frozenset({2}))
    assert t == 7.0 and t.cells == {1, 2} and (100 - t).cells == {1, 2}


def test_cgpv2000_every_value_7z(monkeypatch):
    """7z: CGPV 2000's layout row by row (a place's rows, its HOMBRES and MUJERES blocks, or
    the sexes in columns; rows without values skipped; «RESTO DE LAS ENTIDADES»), its
    locality sizes (``TAM_LOC`` 1, 2, 3–5, 6–7; the rows' spellings), the counts' checks, a
    state's share of the nation's (``of_nation``), the migrants on the dwelling's first
    person and the coverage probe on its layout (every number from the nation's row down)."""
    rows = [{"A": "INEGI. TABULADOS", "B": "POBLACIÓN"}, {"C": "0", "D": "1"},   # a header
            {"A": "ESTADOS UNIDOS MEXICANOS", "B": "100", "C": "60"},
            {"A": "12 - 14  AÑOS", "B": "40", "C": "M.I"},
            {"A": "HOMBRES", "B": "50", "C": "55"}, {"A": "12 - 14  AÑOS", "B": "20", "C": "50"},
            {"A": "MUJERES", "B": "50", "C": "65"},
            {"A": "01 AGUASCALIENTES"},                     # a place without values: no row
            {"A": "SERVICIO", "B": "7", "C": "1"},
            {"A": "RESTO DE LAS ENTIDADES", "B": "9", "C": "2"}, {"A": "/1 NOTA AL PIE."}]
    read = ck._c2k_every("BC")({"x": rows})
    assert read[0, "T"][:3] == [100, 60, 40] and np.isnan(read[0, "T"][3])
    assert read[0, "H"] == [50, 55, 20, 50] and read[0, "M"] == [50, 65]
    assert read[1, "T"] == [7, 1] and read[98, "T"] == [9, 2] and len(read) == 5
    assert ck._c2k_every({"T": "B", "H": "C"}, row=lambda v: [2 * v[0]])({"x": rows[2:3]}) == {
        (0, "T"): [200], (0, "H"): [120]}
    sized = ck._sized_rows_2000([{"A": " MENOS DE 2 500  HABITANTES "},
                                 {"A": "DE 2 500 A 14 999 HABITANTES"},
                                 {"A": "15 000 A 99 999 HABITANTES"},
                                 {"A": "100 000 Y MÁS   HABITANTES"}, {"A": "12 - 14  AÑOS"}])
    assert [ck._state_of(r["A"]) for r in sized] == [1, 2, 3, 4, None]
    assert ck._size_2000(pd.DataFrame({"TAM_LOC": list("1234567")})).tolist() == [
        1, 2, 3, 3, 3, 4, 4]
    by = {c.key: c for c in ck.CHECKS if c.period == "2000"}
    n = by["SS04n"]
    assert (n.unit, n.tolerance, n.cells) == ("persons", ck._COUNTS_2000, ("all",))
    assert n.title == "Health coverage (`DHSERSAL_*`): population (counts)"
    assert (by["SS02n"].tolerance, by["SS02n"].source, by["SS02n"].by_size) == (
        {None: ck._SIZED_COUNTS}, "C2KSS02.xls", True)
    assert by["SS02"].title.endswith("(as SS04)") and by["SS02"].tolerance is None
    with pytest.raises(RuntimeError, match="sizes"):
        by["SS02"].published({"x": rows})
    # the migrants of each dwelling on its first person
    p = pd.DataFrame({"x": range(4)}, index=pd.MultiIndex.from_tuples(
        [("A", 1, 1), ("A", 1, 2), ("B", 1, 1), ("C", 2, 1)]))
    m = pd.DataFrame({"y": range(3)}, index=pd.MultiIndex.from_tuples(
        [("A", 1, 1), ("A", 1, 2), ("C", 2, 1)]))
    import mxcensus
    monkeypatch.setattr(mxcensus, "load_cpv_migrantes", lambda *a, **k: m)
    assert ck._with_migrants_2000(p, 1)["_MIGRANTS"].tolist() == [2, 0, 0, 1]
    monkeypatch.setattr(mxcensus, "load_cpv_migrantes", lambda *a, **k: pd.concat(
        [m, pd.DataFrame({"y": [9]}, index=pd.MultiIndex.from_tuples([("D", 1, 1)]))]))
    with pytest.raises(RuntimeError, match="without persons"):
        ck._with_migrants_2000(p, 1)
    # MI13: each state left's share of the nation's migrants to a destination
    states = [f"{s:02d}  ESTADO" for s in range(1, 33)]
    sheet = [{"A": "ESTADOS UNIDOS MEXICANOS", "B": "64", "C": "32", "D": "31", "E": "1"},
             *({"A": a, "B": "3.125", "C": "3.125", "D": "0" if s == 1 else "3.2258",
                "E": "100" if s == 1 else "0"} for s, a in enumerate(states, 1))]
    frames = {s: pd.DataFrame({"FACTOR": ["1", "1"], "MSEXO": ["1", "2"],
                               "MLUGORI_C": [f"{s:02d}"] * 2,
                               "MPDESOTR_C": ["221", "999" if s == 1 else "300"]})
              for s in range(1, 33)}
    from mxcensus.data import _registry
    monkeypatch.setattr(_registry.POOCH, "fetch", _registry.POOCH.fetch)
    monkeypatch.setattr(ck, "CHECKS", (by["MI13"], by["MI13n"]))
    monkeypatch.setattr(ck, "fetch", lambda periods, tab_dir: {"2000/C2KMI13.xls": "x"})
    monkeypatch.setattr(ck, "_workbook", lambda path: {"Sheet1": sheet})
    monkeypatch.setattr(ck, "_frame", lambda period, table, state: frames[state])
    out = ck.run(["2000"], list(range(1, 33)), log=lambda *a: None)
    assert {r["check"] for r in out} == {"MI13", "MI13n"}
    assert max(abs(r["delta"]) for r in out) < 1e-3 and len(out) == 4 + 32 * 4
    # the coverage probe: column C and none of the header's numbers unread
    monkeypatch.setattr(ck, "_workbook", lambda path: {"Sheet1": rows})
    check = ck.Check("2000", "x", "x", "x.xls", "personas", ("all",), ck._c2k_every("B"), None)
    found = ck.coverage("2000", {"2000/x.xls": Path("x.xls")}, (check,))
    assert found == {("x.xls", "Sheet1"): [((a,), "C") for a in (
        "ESTADOS UNIDOS MEXICANOS", "HOMBRES", "12 - 14  AÑOS", "MUJERES", "SERVICIO",
        "RESTO DE LAS ENTIDADES")]}


@_REAL_SKIP
def test_every_published_value_is_read():
    """7x, 7y: every published value of the Censo 2010, EIC 2015 and Censo 2020 tabulados
    enters a compared cell (no frames needed: the readers only); 7z: CGPV 2000's too."""
    paths = {f"{p}/{n}": _TABS / p / n for p in ck._ESTIMATOR for n in ck.SOURCES[p][1]}
    for period in ck._ESTIMATOR:
        assert ck.coverage(period, paths) == {}, period
    less = tuple(c for c in ck.CHECKS if (c.period, c.key) != ("2020", "09-04"))
    found = ck.coverage("2020", paths, less)
    assert set(found) == {("cpv2020_a_eum_09_servicios_de_salud.xlsx", "04")}
    assert len(found["cpv2020_a_eum_09_servicios_de_salud.xlsx", "04"]) == 33 * 11 * 12
    less = tuple(c for c in ck.CHECKS if (c.period, c.key) != ("2000", "VI16n"))   # 7z
    found = ck.coverage("2000", paths, less)
    assert set(found) == {("C2KVI16.xls", "Sheet1")}
    assert len(found["C2KVI16.xls", "Sheet1"]) == 33 * 10          # the dwellings per good


def test_checks_are_consistent():
    """Every check names a fetched source, unique keys per edition, and a tolerance."""
    keys = [(c.period, c.key) for c in ck.CHECKS]
    assert len(keys) == len(set(keys))
    for c in ck.CHECKS:
        assert c.source in ck.SOURCES[c.period][1], c.key
        assert c.table in ("personas", "viviendas", "hogares", "migrantes")       # 7d
        assert c.unit in ("points", "persons", "average", "rate")           # 7i, 7o
        assert c.period == "2000" or c.unit == "persons" or c.tolerance      # 7j: exact
        assert c.table != "migrantes" or c.period in ("2000", "2010", "2020")  # 7m, 7n
        assert not c.by_origin or c.table == "migrantes" or c.period == "2000" or c.key in (
            "05_01A", "05_02A", "04-06") or c.by_size  # 7d, 7m; 7p: the rest, 98; 7s; 7v: 2010
        assert not c.by_size or c.by_origin                                 # 7s; 7z: 2000
        assert c.table != "hogares" or c.period == "2000"          # 6t: 2000's household rows
        assert c.unit != "persons" or c.period != "2000" or c.tolerance in (  # 7z: counts
            ck._COUNTS_2000, {None: ck._SIZED_COUNTS})
        assert c.unit in ("persons", "rate") or c.period in ("2000", "2015") or (
            c.key in ("04-12m", "04-11m", "04_10Am", "04_09Am", "10_01As"))
        #                                      7j, 7o; 7p: months abroad; 7s: by size; 7x: 2010
        assert c.source.endswith(".xlsx" if c.period == "2020" else ".xls") or (
            c.source == "10_01A_ESTATAL.pdf")                              # 6p; 7x: a PDF
        assert None in ck._TOLERANCE[c.period]
    assert {c.period for c in ck.CHECKS} == set(ck.SOURCES)
    assert {n for _, (_, names) in ck.SOURCES.items() for n in names} == {
        c.source for c in ck.CHECKS}


def test_by_size_checks():
    """7s: a by-size sheet read by its by-state twin's reader (each size row a pseudo-state,
    the nation kept, a missing size raises), the twin's cells counted in each record's
    ``TAMLOC`` (a :class:`Weighted` part too), INEGI's keys."""
    rows = [{"A": "Tamaño de localidad", "B": "Sexo", "C": "Estimador", "D": "Total"},
            {"A": "Estados Unidos Mexicanos", "B": "Total", "C": "Parámetro", "D": "30"},
            *({"A": f" {n} ", "B": "Total", "C": "Parámetro", "D": str(10 * i)}
              for i, n in enumerate(ck._SIZES["2010"], 1)),
            {"A": "1-2 499 habitantes", "B": "Total", "C": "Parámetro", "D": "5"}]   # 2020's size 1
    renamed = ck._sized_rows(rows, "2010")
    assert [r["A"] for r in renamed[1:]] == [
        "Estados Unidos Mexicanos", "01 Localidades de Menos de 2 500 habitantes",
        "02 Localidades de 2 500-14 999 habitantes", "03 Localidades de 15 000-99 999 habitantes",
        "04 Localidades de 100 000 y más habitantes", "1-2 499 habitantes"]
    assert [ck._state_of(r["A"]) for r in renamed[1:]] == [0, 1, 2, 3, 4, None]
    every = lambda f: [(pd.Series(True, index=f.index), None),             # noqa: E731
                       (ck.Weighted(pd.Series(True, index=f.index), f["NUMPERS"]), None)]
    twin = ck.Check("2010", "14_14Aa", "Dwellings, nation", "14_14A_ESTATAL.xls", "viviendas",
                    ("all", "occupants"), ck._wide("Parámetro", lambda v: v * 2,
                                                    dims=lambda k: (k[0], "T")),
                    every, unit="persons", tolerance={None: 0.5, 9: 3.0})
    sized = ck._by_size(twin, source="14_13A_ESTATAL.xls")
    assert (sized.key, sized.sheet, sized.by_size, sized.by_origin) == ("14_13Aa", None, True, True)
    assert sized.title == "Dwellings, by locality size (as 14_14Aa)" and not sized.note
    assert sized.tolerance == {None: 0.5}
    assert sized.published({"x": rows}) == {(s, "T"): [10.0 * s] * 2 if s else [30.0] * 2
                                            for s in range(5)}
    with pytest.raises(RuntimeError, match="sizes"):
        ck._by_size(twin, source="14_13A_ESTATAL.xls").published({"x": rows[:3]})
    v = pd.DataFrame({"tam_loc": ["01", "04", "04", None], "NUMPERS": ["3", "2", "5", "1"],
                      "FACTOR": ["1", "1", "2", "4"]})
    sums = ck._sums(sized, v, 15)
    assert sums == {"T": [({1: 1.0, 4: 3.0, 99: 4.0}, None), ({1: 3.0, 4: 12.0, 99: 4.0}, None)]}
    # 2015/2020: the sheet's number and the twin's suffix; a nation-only by-size check keeps its key
    c2020 = replace(twin, period="2020", key="16-02b", source="x.xlsx", sheet="02")
    assert ck._by_size(c2020, "01").key == "16-01b"
    assert ck._by_size(replace(c2020, key="14-12", sheet="12")).key == "14-12"
    assert ck._place_label(sized, 0) == "00" and ck._place_label(sized, 3) == "size 3"
    assert ck._place_label(twin, 3) == "03"


@_REAL_SKIP
def test_state_01_within_tolerance(monkeypatch):
    """Every check of state 01 (2000, 2010, 2015, 2020) agrees with INEGI's tabulado (the
    national-only 2010 checks need all 32 states: the report)."""
    monkeypatch.setattr(ck, "fetch", lambda periods, tab_dir, retries=2: {
        f"{p}/{n}": tab_dir / p / n for p in periods for n in ck.SOURCES[p][1]})
    rows = ck.run(sorted(ck.SOURCES), [1], _TABS, _MIRROR, log=lambda *a: None)
    assert len(rows) == (317 + 159 + 120 + 45 + 7 + 13 + 149 + 132 + 183 + 463 + 562  # 6p: 2020;
                         + 317 + 894 + 144 + 247 + 329 + 291 + 3 * 8 + 889 + 392
                         + 4645                                               # 7v: 2015
                         + 3931                                               # 7w: 2020
                         + 2316 + 672 + 3511                                  # 7x: 2010, 2015
                         + 181                                                # 7y: 2020
                         + 673)                                               # 7z: 2000
    #                                                 6q: 2015 affiliation, commute, marital status,
    #                                                 education (2010's are national); 6r: 2000
    #                                                 hours, education of the 12+/18+; 6t: 2000/2015
    #                                                 by the head's sex (sex T only); 6w: media
    #                                                 superior and superior apart (2000 ED10/ED11,
    #                                                 2015 06-11), 2015 05-04 (sex T), 2020 07-04;
    #                                                 7b: the places by municipality (2010 04_02A
    #                                                 +9, 08_15A; 2015 04-05 +9, 10-01, 10-04; 2020
    #                                                 10-02, 10-08: 7 cells × 3 sexes), 2015
    #                                                 household class, tenure, deeds (sex T);
    #                                                 7c: the income in minimum wages (2000
    #                                                 EM08 8 × 3; 2010/2015/2020 9 × 3), 2000's
    #                                                 places (EM10 6, sex T; MI04 7 × 3); 7d:
    #                                                 2000 EM02/03/04/06/09/11, MI06, MI09 (sex T;
    #                                                 MI02/05/10–12 need all 32 states, MI07/08 are
    #                                                 national), 2015 the dwellings (sex T; 14-12
    #                                                 national); 7h: the Censo 2010/2020
    #                                                 dwellings and the 2015/2020 owners' sex
    #                                                 (2010 262, 2015 25, 2020 275; sex T);
    #                                                 7i: CGPV 2000's dwellings (sex T); 7j:
    #                                                 the EIC 2015 persons (01-02, 02-02, 03-01
    #                                                 sex T; 01-03, 09-02, 09-03 by sex); 7k:
    #                                                 CGPV 2000's persons (PO01, DI02, DI04 by
    #                                                 sex; LI02 not for state 01; FE «M.I.» out);
    #                                                 7l: its households (sex T) and education;
    #                                                 7m: Censo 2010's persons (its migrants need
    #                                                 all 32 states); 7n: Censo 2020's;
    #                                                 7o: the fertility rates by state (8 cells,
    #                                                 sex T; by size and the infant mortality are
    #                                                 national); 7p: Censo 2010's fields, divisions,
    #                                                 parents, kinship (05_01A/02A need all 32),
    #                                                 Censo 2020's disability, return migrants;
    #                                                 7v: the EIC 2015's education, health
    #                                                 services, economy, commute times,
    #                                                 households, migration, ethnicity, other
    #                                                 incomes and food (04-06 needs all 32
    #                                                 states; 05-02, 04-04 and by size are
    #                                                 national); 7w: Censo 2020's (2,758 new
    #                                                 cells; 08-12, 08-18, 10-02, 10-06, 10-08,
    #                                                 10-12, 11-02 read every row: 159 → 1,332);
    #                                                 7x: Censo 2010's last tabulados (2,316;
    #                                                 04_08A needs all 32, 08_21A/22A and the
    #                                                 sizes are national), 08_02A/03A/10A/15A
    #                                                 every row (+672); the EIC 2015's 04-02,
    #                                                 06-11, 07-02, 07-06, 08-02/06/07/11,
    #                                                 10-01/03/04/06, 11-02, 12-05a/b every row,
    #                                                 06-11d/m, 11-02d, 14-02s (+3,511);
    #                                                 7y: Censo 2020's unspecified age (01-02,
    #                                                 01-04), the superior's fields (07-04),
    #                                                 the employed (08-06/08), the use of
    #                                                 services by affiliation (09-04);
    #                                                 7z: CGPV 2000's counts (+258), every age
    #                                                 row (EC02 +84, MI01 +45, MI03 +36), totals
    #                                                 (VI18/VI18o +8, DI04 +3), ED10m, MI09r,
    #                                                 SS03/07/08/09, ED14 (the by-size ones are
    #                                                 national, MI13 needs all 32 states)
    by_origin = {c.key for c in ck.CHECKS if c.by_origin and not c.by_size}  # 7d: all 32
    assert by_origin == {"MI02", "MI05", "MI10", "MI11", "MI12",
                         "04_04A", "04_05A", "04_06A",                     # 7m: 2010's migrants
                         "04-04", "04-06", "04-08", "04-10",               # 7n: 2020's
                         "05_01A", "05_02A", "04-15",                      # 7p
                         "04-06",                                          # 7v: the 2015 internal
                         "04_08A",                                         # 7x
                         "LI02", "LI02n", "MI13"}                          # 7z
    assert not {(c.period, c.key) for c in ck.CHECKS if c.by_origin} & {
        (r["period"], r["check"]) for r in rows}                          # 7s: by size too
    income = [r for r in rows if r["check"] in ("EM08", "08_10A", "08-11", "08-18")]
    assert len(income) == 8 * 3 + 3 * 11 * 9 * 3      # 7w: 2020 by division; 7x: 2010, 2015
    head = [r for r in rows if r["check"] in ("HO04a", "HO04b", "12-05")]
    assert len(head) == 7 and {r["sex"] for r in head} == {"T"}
    places = [r for r in rows if (r["period"], r["check"]) in (
        ("2010", "04_02A"), ("2010", "08_15A"), ("2015", "04-05"), ("2015", "10-01"),
        ("2015", "10-04"), ("2020", "10-02"), ("2020", "10-08"))]       # 7v: 2015's 10-02 too
    assert len(places) == (1 + 7 + 1 + 8 + 7 + 8 + 7) * 7 * 3  # 7b; 7w, 7x: by age, sector
    dwellings = [r for r in rows if r["check"] in ("12-05a", "12-05b", "14-13", "14-16")]
    assert len(dwellings) == 30 + 30 + 6 + 6 and {r["sex"] for r in dwellings} == {"T"}  # 7x
    raw = [r for r in rows if r["check"].startswith(("14_", "16-")) or r["check"] in (
        "14-14", "14-16s")]                                                # 7h
    assert len(raw) == 262 + 25 + 275 + 10 and {r["sex"] for r in raw} == {"T"}  # + 16-34
    vi = [r for r in rows if r["check"].startswith("VI") and r["check"] not in ("VI06", "VI10")]
    counts = [r for r in vi if r["check"].endswith("n")]                     # 7z: the counts
    assert len(vi) == 317 + 8 + 51 and len(counts) == 51 and {r["sex"] for r in vi} == {"T"}
    #                                                          7i; 7z: VI18's totals, the counts
    new = {c.key for c in ck._person_checks_2015_v()}
    v = [r for r in rows if r["period"] == "2015" and r["check"] in new]
    assert len(v) == 4645 + 66                                       # 7v; 7x: 07-06's «Total»
    assert {r["sex"] for r in v if r["check"] in ("06-02", "05-05", "05-03", "07-06", "12-03",
                                                   "12-06", "13-02", "15-01", "15-02")} == {"T"}
    new = {c.key for c in ck._person_checks_2020_w()}
    w = [r for r in rows if r["period"] == "2020" and r["check"] in new]
    assert len(w) == 2758                                                             # 7w
    assert {r["sex"] for r in w if r["check"] in ("14-02", "15-02", "15-04")} == {"T"}
    new = {c.key for c in ck._person_checks_2010_x()}
    x = [r for r in rows if r["period"] == "2010" and r["check"] in new]
    assert len(x) == 2316                                                             # 7x
    assert {r["sex"] for r in x if r["check"] in ("06_04A", "06_06A", "07_03A", "09_03A",
                                                   "09_05A", "12_06A", "12_07A",
                                                   "04_10A")} == {"T"}
    assert {r["sex"] for r in rows if r["period"] == "2015" and r["check"] in (
        "12-05a", "12-05b", "14-02s")} == {"T"}
    bad = [r for r in rows if abs(r["delta"]) > r["tolerance"]]
    assert not bad, bad[:5]
    exact = [r for r in rows if r["period"] != "2000"]
    assert max(abs(r["delta"]) for r in exact) < 0.05            # persons
