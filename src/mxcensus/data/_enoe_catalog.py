"""INEGI ENOE bulk-download catalog (national, per-quarter CSV ZIPs).

ENOE (Encuesta Nacional de Ocupación y Empleo) is Mexico's quarterly labor-force
survey, published as microdata since 2005-Q1. Unlike the census/DENUE mirrors it is
**national** — one ZIP per quarter (no per-state split) — and each ZIP bundles the
**five tables** ``viv``/``hog``/``sdem``/``coe1``/``coe2`` (dwelling, household,
sociodemographic, and the two employment-questionnaire parts).

Everything below was verified live against the INEGI tree on ``CATALOG_VERIFIED_DATE``
(see ``docs/enoe/STEP_0_probe.md``). INEGI serves a soft-404 (HTTP 200 + a ~2263-byte
HTML placeholder) for missing files, so URL existence must be judged by Content-Type,
not the status code; the build's ``fetch_zip_verified`` catches this downstream.

Three filename regimes, a pure function of the period (no per-quarter exceptions):

===========  ==================  ==============================  ===========================
regime       quarters            ZIP filename template            in-ZIP member example
===========  ==================  ==============================  ===========================
``enoe_old`` 2005-Q1 … 2020-Q1   ``{year}trim{q}_csv.zip``        ``sdemt119.csv`` (lowercase)
``enoen``    2020-Q3 … 2022-Q4   ``enoe_n_{year}_trim{q}_csv.zip````ENOEN_SDEMT321.csv``
``enoe_new`` 2023-Q1 … latest    ``enoe_{year}_trim{q}_csv.zip``  ``ENOE_SDEMT123.csv``
===========  ==================  ==============================  ===========================

The in-ZIP member core is always ``{TABLE}T{Q}{YY}`` (Q = quarter 1-4, YY = 2-digit
year); only the prefix and case differ by regime (see ``_MEMBER_STYLE``).

**2020-Q2 gap.** Field operations were suspended for COVID; Q2-2020 exists only as the
telephone survey **ETOE**, a separate product at a different endpoint
(``inegi.org.mx/contenidos/investigacion/etoe/``). It is **excluded** from ``QUARTERS``
(a later work unit may add it as its own regime).

**COE ampliado vs. básico.** ENOE alternates an expanded (ampliado) and basic (básico)
employment questionnaire — historically Q1 = ampliado, Q2-Q4 = básico from 2009 on, with
messier 2005-2008 patterns — which changes the COE1/COE2 column sets. This is **not**
hard-coded here; the schema-fingerprint groups (``build_enoe.py``) capture it empirically.

The ``ENOEN``→``ENOE`` rename (2023) and ``FAC``→``FAC_TRI`` weight rename (2020-Q3) are
schema-drift facts handled downstream (fingerprint groups + optional harmonization), not
in the catalog.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ._catalog import CatalogEntry

_BASE = "https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/"

# Date this catalog was last verified against the live INEGI tree.
CATALOG_VERIFIED_DATE = "2026-07-10"

# The five data tables in every quarter's ZIP (dwelling, household, sociodemographic,
# and the two employment-questionnaire parts). SDEM is the main person-level table.
TABLES: tuple[str, ...] = ("viv", "hog", "sdem", "coe1", "coe2")

# First and latest available quarters, and the face-to-face gap (see module docstring).
_EARLIEST = (2005, 1)
_LATEST = (2026, 1)
_GAPS: set[tuple[int, int]] = {(2020, 2)}

# regime → (member-name prefix, uppercase?) for the in-ZIP CSV member name.
_MEMBER_STYLE: dict[str, tuple[str, bool]] = {
    "enoe_old": ("", False),
    "enoen": ("ENOEN_", True),
    "enoe_new": ("ENOE_", True),
}


def _regime_for(year: int, quarter: int) -> str:
    """Return the filename regime for a (year, quarter) — see the regime table above."""
    if (year, quarter) <= (2020, 1):
        return "enoe_old"
    if (year, quarter) <= (2022, 4):
        return "enoen"
    return "enoe_new"


@dataclass(frozen=True)
class EnoeQuarter:
    """One ENOE quarter: a stable period id plus its filename regime.

    ``period`` is ``"{year}t{quarter}"`` (e.g. ``"2023t1"``) — lowercase and naturally
    sortable, mirroring the ``T123`` member core. ``regime`` is one of the keys of
    ``_MEMBER_STYLE`` and drives both the ZIP filename and the in-ZIP member naming.
    """

    period: str
    year: int
    quarter: int
    regime: str

    @property
    def label(self) -> str:
        """Human label, e.g. ``"trimestre 1 de 2023"``."""
        return f"trimestre {self.quarter} de {self.year}"

    @property
    def zip_filename(self) -> str:
        """The ZIP filename for this quarter under ``_BASE`` (regime-dependent)."""
        if self.regime == "enoe_old":
            return f"{self.year}trim{self.quarter}_csv.zip"
        if self.regime == "enoen":
            return f"enoe_n_{self.year}_trim{self.quarter}_csv.zip"
        return f"enoe_{self.year}_trim{self.quarter}_csv.zip"

    @property
    def url(self) -> str:
        """Full download URL for this quarter's CSV ZIP."""
        return _BASE + self.zip_filename


def _member_core(quarter: EnoeQuarter, table: str) -> str:
    """In-ZIP member core ``{table}t{q}{yy}`` (e.g. ``sdemt119``), lowercase."""
    return f"{table}t{quarter.quarter}{quarter.year % 100:02d}"


def table_member_name(quarter: EnoeQuarter, table: str) -> str:
    """Canonical in-ZIP CSV member filename for ``table`` in ``quarter``.

    Examples: ``sdemt119.csv`` (old), ``ENOEN_SDEMT321.csv`` (ENOEN),
    ``ENOE_SDEMT123.csv`` (new).
    """
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}; known: {TABLES}")
    core = _member_core(quarter, table)
    prefix, upper = _MEMBER_STYLE[quarter.regime]
    return f"{prefix}{core.upper() if upper else core}.csv"


def find_member(names: list[str], quarter: EnoeQuarter, table: str) -> str | None:
    """Find ``table``'s CSV member among a ZIP's ``names``, tolerant of prefix/case.

    Matches ``(?:enoe_|enoen_)?{core}.csv`` case-insensitively on each basename, so the
    build locates the right member without trusting the exact regime prefix. Returns the
    original member name, or ``None`` if absent.
    """
    core = _member_core(quarter, table)
    pat = re.compile(rf"^(?:enoe_|enoen_)?{re.escape(core)}\.csv$", re.IGNORECASE)
    for n in names:
        if pat.match(n.rsplit("/", 1)[-1]):
            return n
    return None


def enoe_zip_entry(quarter: EnoeQuarter) -> CatalogEntry:
    """Return the download entry for a quarter's CSV ZIP (all five tables)."""
    return CatalogEntry(
        url=quarter.url,
        extract_dir=Path("enoe") / quarter.period,
        description=f"ENOE {quarter.label} — {quarter.regime}",
    )


def _generate_quarters() -> list[EnoeQuarter]:
    """Build the chronological quarter list (2005-Q1 … latest, excluding gaps)."""
    quarters: list[EnoeQuarter] = []
    for year in range(_EARLIEST[0], _LATEST[0] + 1):
        for quarter in range(1, 5):
            yq = (year, quarter)
            if yq < _EARLIEST or yq > _LATEST or yq in _GAPS:
                continue
            quarters.append(
                EnoeQuarter(
                    period=f"{year}t{quarter}",
                    year=year,
                    quarter=quarter,
                    regime=_regime_for(year, quarter),
                )
            )
    return quarters


# Chronological catalog of available quarters (2005-Q1 … 2026-Q1, excluding 2020-Q2).
QUARTERS: list[EnoeQuarter] = _generate_quarters()

QUARTERS_BY_PERIOD: dict[str, EnoeQuarter] = {q.period: q for q in QUARTERS}


def latest_quarter() -> EnoeQuarter:
    """Return the most recent ENOE quarter in the catalog."""
    return QUARTERS[-1]
