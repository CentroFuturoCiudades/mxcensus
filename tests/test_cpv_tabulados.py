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


def test_counts():
    assert ck._counts(200, [50, 10]) == [200, 100, 20]
    # PEA % of the 12+, employed and unemployed % of the PEA, inactive % of the 12+
    assert ck._counts(200, [50, 90, 10, 50], [0, 1, 1, 0]) == [200, 100, 90, 10, 100]


def test_checks_are_consistent():
    """Every check names a fetched source, unique keys per edition, and a tolerance."""
    keys = [(c.period, c.key) for c in ck.CHECKS]
    assert len(keys) == len(set(keys))
    for c in ck.CHECKS:
        assert c.source in ck.SOURCES[c.period][1], c.key
        assert c.table in ("personas", "viviendas") and c.unit in ("points", "persons")
        assert (c.unit == "points") == (c.period == "2000")
        assert c.source.endswith(".xlsx" if c.period == "2020" else ".xls")        # 6p
        assert None in ck._TOLERANCE[c.period]
    assert {c.period for c in ck.CHECKS} == set(ck.SOURCES)
    assert {n for _, (_, names) in ck.SOURCES.items() for n in names} == {
        c.source for c in ck.CHECKS}


@_REAL_SKIP
def test_state_01_within_tolerance(monkeypatch):
    """Every check of state 01 (2000, 2010, 2015, 2020) agrees with INEGI's tabulado."""
    monkeypatch.setattr(ck, "fetch", lambda periods, tab_dir, retries=2: {
        f"{p}/{n}": tab_dir / p / n for p in periods for n in ck.SOURCES[p][1]})
    rows = ck.run(sorted(ck.SOURCES), [1], _TABS, _MIRROR, log=lambda *a: None)
    assert len(rows) == 317 + 159                                        # 6p: 2020
    bad = [r for r in rows if abs(r["delta"]) > r["tolerance"]]
    assert not bad, bad[:5]
    exact = [r for r in rows if r["period"] != "2000"]
    assert max(abs(r["delta"]) for r in exact) < 0.05            # persons
