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
    for not_a_state in ("12 - 14  AÑOS", "50 Y MÁS  AÑOS", "15 Y MÁS AÑOS", "HOMBRES", "",
                        "40 Otra cosa"):
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


def test_long_matches_category_words():
    """2010 spells a division «forestales, caza y pesca», 2015 «forestales, pesca y caza»;
    footnote digits are dropped; a missing category raises."""
    rows = [{"A": "Entidad federativa", "B": "Sexo", "C": "División ocupacional1",
             "D": "Estimador", "E": "Población ocupada"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Total", "D": "Parámetro", "E": "30"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "Trabajadores agrícolas, caza y pesca2",
             "D": "Parámetro", "E": "10"},
            {"A": "01 Aguascalientes", "B": "Total", "C": "No especificado", "D": "Parámetro",
             "E": "20"}]
    read = ck._long("Parámetro", ("No especificado", "Trabajadores agrícolas, pesca y caza"))
    assert read({"s": rows}) == {(1, "T"): [20.0, 10.0]}
    with pytest.raises(KeyError):
        ck._long("Parámetro", ("Comercio",))({"s": rows})


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


def test_checks_are_consistent():
    """Every check names a fetched source, unique keys per edition, and a tolerance."""
    keys = [(c.period, c.key) for c in ck.CHECKS]
    assert len(keys) == len(set(keys))
    for c in ck.CHECKS:
        assert c.source in ck.SOURCES[c.period][1], c.key
        assert c.table in ("personas", "viviendas", "hogares", "migrantes")       # 7d
        assert c.unit in ("points", "persons", "average")                   # 7i
        assert c.period == "2000" or c.unit == "persons" or c.tolerance      # 7j: exact
        assert c.table != "migrantes" or c.period in ("2000", "2010")       # 7m: 2010's
        assert not c.by_origin or c.table == "migrantes" or c.period == "2000"  # 7d, 7m
        assert c.table != "hogares" or c.period == "2000"          # 6t: 2000's household rows
        assert c.unit != "persons" or c.period != "2000"          # 2000: shares, averages
        assert c.unit == "persons" or c.period in ("2000", "2015")    # 7j: 2015's averages
        assert c.source.endswith(".xlsx" if c.period == "2020" else ".xls")        # 6p
        assert None in ck._TOLERANCE[c.period]
    assert {c.period for c in ck.CHECKS} == set(ck.SOURCES)
    assert {n for _, (_, names) in ck.SOURCES.items() for n in names} == {
        c.source for c in ck.CHECKS}


@_REAL_SKIP
def test_state_01_within_tolerance(monkeypatch):
    """Every check of state 01 (2000, 2010, 2015, 2020) agrees with INEGI's tabulado (the
    national-only 2010 checks need all 32 states: the report)."""
    monkeypatch.setattr(ck, "fetch", lambda periods, tab_dir, retries=2: {
        f"{p}/{n}": tab_dir / p / n for p in periods for n in ck.SOURCES[p][1]})
    rows = ck.run(sorted(ck.SOURCES), [1], _TABS, _MIRROR, log=lambda *a: None)
    assert len(rows) == (317 + 159 + 120 + 45 + 7 + 13 + 149 + 132 + 183 + 463 + 562  # 6p: 2020;
                         + 317 + 894 + 144 + 247 + 329)
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
    #                                                 all 32 states)
    by_origin = {c.key for c in ck.CHECKS if c.by_origin}               # 7d: all 32 only
    assert by_origin == {"MI02", "MI05", "MI10", "MI11", "MI12",
                         "04_04A", "04_05A", "04_06A"}                     # 7m: 2010's migrants
    assert not by_origin & {r["check"] for r in rows}
    income = [r for r in rows if r["check"] in ("EM08", "08_10A", "08-11", "08-18")]
    assert len(income) == 8 * 3 + 3 * 9 * 3
    head = [r for r in rows if r["check"] in ("HO04a", "HO04b", "12-05")]
    assert len(head) == 7 and {r["sex"] for r in head} == {"T"}
    places = [r for r in rows if r["check"] in ("04_02A", "08_15A", "04-05", "10-01", "10-04",
                                                "10-02", "10-08")]
    assert len(places) == 7 * 7 * 3                                       # 7b
    dwellings = [r for r in rows if r["check"] in ("12-05a", "12-05b", "14-13", "14-16")]
    assert len(dwellings) == 10 + 4 + 6 + 6 and {r["sex"] for r in dwellings} == {"T"}
    raw = [r for r in rows if r["check"].startswith(("14_", "16-")) or r["check"] in (
        "14-14", "14-16s")]                                                # 7h
    assert len(raw) == 262 + 25 + 275 + 10 and {r["sex"] for r in raw} == {"T"}  # + 16-34
    vi = [r for r in rows if r["check"].startswith("VI") and r["check"] not in ("VI06", "VI10")]
    assert len(vi) == 317 and {r["sex"] for r in vi} == {"T"}                # 7i
    bad = [r for r in rows if abs(r["delta"]) > r["tolerance"]]
    assert not bad, bad[:5]
    exact = [r for r in rows if r["period"] != "2000"]
    assert max(abs(r["delta"]) for r in exact) < 0.05            # persons
