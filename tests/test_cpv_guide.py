"""The CPV user guide (``docs/cpv/GUIDE.md``, unit 8h) stays true.

Its two generated tables (the derived columns by edition, the constraints by edition) are
rebuilt offline from ``cpv_derivations``/``cpv_constraints``/``cpv_ratio_constraints``;
its ```pycon examples run as doctests against the local mirror (``data/parquet``), the
outputs it quotes included (skipped without the files they read).
"""
from __future__ import annotations

import doctest
import re
from pathlib import Path

import pandas as pd
import pytest

import mxcensus

_ROOT = Path(__file__).resolve().parent.parent
_GUIDE = _ROOT / "docs" / "cpv" / "GUIDE.md"
_MIRROR = _ROOT / "data" / "parquet"

_PERIODS = ("1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025")
_TABLES = ("personas", "viviendas", "hogares")
# A set of dummies is one row of the matrix.
_DUMMY_SETS = ("DHSERSAL_", "MED_TRASLADO_ESC_", "MED_TRASLADO_TRAB_", "FINANCIAMIENTO_")
_FENCE = re.compile(r"^```pycon\n(.*?)^```\n", re.S | re.M)
# The display options the quoted outputs were printed with.
_OPTIONS = {"display.width": 88, "display.max_columns": 20, "display.max_colwidth": 50}


def _column_row(column: str) -> str:
    for prefix in _DUMMY_SETS:
        if column.startswith(prefix):
            star = "*_T" if prefix.startswith("MED_") and column.endswith("_T") else "*"
            return prefix + star
    return column


def derived_matrix() -> str:
    """The guide's table of derived columns by edition (Markdown)."""
    rows: dict[tuple[str, str], set[str]] = {}
    for _, r in mxcensus.cpv_derivations().iterrows():
        key = (r["TABLE"], _column_row(r["COLUMN"]))
        rows.setdefault(key, set()).update(p.strip() for p in r["PERIODS"].split(","))
    lines = ["| table | column | " + " | ".join(_PERIODS) + " |",
             "|---|---|" + "---|" * len(_PERIODS)]
    for table in _TABLES:
        for (t, column), periods in rows.items():
            if t == table:
                marks = " | ".join("✓" if p in periods else "" for p in _PERIODS)
                lines.append(f"| {table} | `{column}` | {marks} |")
    return "\n".join(lines)


def constraint_counts() -> str:
    """The guide's table of constraints by edition (count + ratio constraints)."""
    lines = ["| edition | " + " | ".join(_TABLES) + " |", "|---|" + "---|" * len(_TABLES)]
    for period in reversed(_PERIODS):
        cells = []
        for table in _TABLES:
            try:
                counts = mxcensus.cpv_constraints(table, period)
                ratios = mxcensus.cpv_ratio_constraints(table, period)
            except ValueError:
                cells.append("—")
                continue
            cells.append(f"{len(counts)} + {len(ratios)}" if ratios else f"{len(counts)}")
        lines.append(f"| {period} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _example_lines(text: str) -> set[int]:
    """The 0-based numbers of the lines inside the ```pycon blocks."""
    lines = set()
    for m in _FENCE.finditer(text):
        first = text.count("\n", 0, m.start(1))
        lines.update(range(first, first + m.group(1).count("\n")))
    return lines


def _section(text: str, marker: str) -> str:
    m = re.search(rf"<!-- {marker}:[^\n]*-->\n(.*?)<!-- /{marker} -->", text, re.S)
    assert m, f"GUIDE.md has no {marker} section"
    return m.group(1).strip()


def test_derived_matrix_is_current():
    assert _section(_GUIDE.read_text(), "derived-matrix") == derived_matrix()


def test_constraint_counts_are_current():
    assert _section(_GUIDE.read_text(), "constraint-counts") == constraint_counts()


def test_guide_blocks_parse():
    """Every example block is a doctest and the guide links only to files that exist."""
    text = _GUIDE.read_text()
    blocks = _FENCE.findall(text)
    assert len(blocks) >= 20
    parser = doctest.DocTestParser()
    for block in blocks:
        assert parser.get_examples(block), block[:80]
    for link in re.findall(r"\]\(([A-Za-z_]+\.md)\)", text):
        assert (_GUIDE.parent / link).exists(), link


# --- the examples, against the local mirror -------------------------------------------------

# The files the examples read: state 1 of every edition, Quintana Roo's 2000/2020 ITER, the
# EIC 2025 estimates and municipal frame, Aguascalientes's AHL.
_NEEDED = (
    [f"cpv_{t}_{p}_01.parquet" for p, ts in {
        "2025": ("viviendas", "personas", "migrantes"),
        "2020": ("personas", "iter"),
        "2015": ("personas",),
        "2010": ("personas",),
        "2000": ("viviendas", "personas", "iter"),
        "1990": ("iter",)}.items() for t in ts]
    + ["cpv_personas_2010_02.parquet", "cpv_iter_2000_23.parquet", "cpv_iter_2020_23.parquet",
       "cpv_estimaciones_2025.parquet", "mg_mun_2025_01.parquet",
       "ahl_habitantes_20260918_01.parquet", "ahl_movimientos_20260918_01.parquet"])
_REAL = all((_MIRROR / f).exists() for f in _NEEDED)


@pytest.fixture
def local_mirror(monkeypatch):
    from mxcensus.data import _registry

    def _fetch(fname, **_):
        p = _MIRROR / fname
        if not p.exists():
            raise FileNotFoundError(p)
        return str(p)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)


@pytest.mark.skipif(not _REAL, reason="no local CPV mirror (data/parquet/)")
@pytest.mark.filterwarnings("ignore")
def test_guide_examples(local_mirror):
    text = _GUIDE.read_text()
    # The examples alone, every other line blank: a failure reports the guide's line.
    keep = _example_lines(text)
    source = "\n".join(line if i in keep else "" for i, line in enumerate(text.split("\n")))
    test = doctest.DocTestParser().get_doctest(source, {}, "GUIDE.md", str(_GUIDE), 0)
    runner = doctest.DocTestRunner(
        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
    report: list[str] = []
    with pd.option_context(*[x for kv in _OPTIONS.items() for x in kv]):
        result = runner.run(test, out=report.append)
    assert result.failed == 0, "".join(report)
