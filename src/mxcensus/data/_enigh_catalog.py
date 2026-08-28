"""INEGI ENIGH bulk-download catalog (national, one CSV ZIP per (edition, table)).

ENIGH (Encuesta Nacional de Ingresos y Gastos de los Hogares) is Mexico's biennial
household income/expenditure survey — the source for CONEVAL poverty measurement, income
deciles and household expenditure structure. Like ENOE it is **national** (no per-state
split), but unlike ENOE each **table ships as its own ZIP** holding a single CSV member.

Everything below was verified live against the INEGI tree on ``CATALOG_VERIFIED_DATE``
(see ``docs/enigh/STEP_0_probe.md``). INEGI serves a soft-404 (HTTP 200 + a ~2263-byte HTML
placeholder) for missing files, so existence is judged by Content-Type; the build's
``fetch_zip_verified`` catches this downstream. The server matches ZIP filenames
case-insensitively; the canonical casing is recorded here.

Two regimes, both under ``…/contenidos/programas/enigh/nc/{year}/microdatos/``:

=========  ======================  ========================================  ===================
regime     editions                ZIP filename template                     in-ZIP member
=========  ======================  ========================================  ===================
``ns``     2016 2018 2020 2022 2024  ``enigh{year}_ns_{table}_csv.zip``       ``{table}.csv``
``ncv``    2008 2010 2012 2014     ``NCV_{Stem}_{year}_concil_2010_csv.zip``  ``{stem}.csv`` or the ZIP stem
=========  ======================  ========================================  ===================

**Nueva serie (``ns``, 2016+).** In 2016 INEGI stopped fielding the MCS (Módulo de
Condiciones Socioeconómicas) separately and folded it into ENIGH with a much larger sample
(81.5 k dwellings in 2016, 105.5 k from 2020; state × urban/rural representativeness) and
revised income capture — **a new statistical series**, not comparable to 2014 and earlier
without INEGI's bridging model. Eleven tables per edition (:data:`NS_TABLES`).

**Nueva Construcción de Variables (``ncv``, 2008–2014).** INEGI's own re-expression of the
traditional-series microdata with the variable construction of the MCS-ENIGH, *conciliated*
to the CPV-2010 population frame (``_concil_2010``) — the closest pre-break data comparable
to the nueva serie. Table names differ (``Concentrado``→``concentradohogar``,
``Agropecuario``→``agro``, ``Gastohogar``→``gastoshogar``) and the set varies by year: 2008
and 2010 have no dwelling table and a single combined expenditure table (``Gastos``); the
NCV-only ``Gastotarjetas`` (credit-card expenditure) exists 2008–2014. Canonical (``ns``)
table names are used throughout the package; :data:`_NCV_STEMS` maps them to INEGI's stems.

**2022 → 2024.** ENIGH 2024 (same series) updated the questionnaires — housing items
homologated to the CPV 2020, new sociodemographic items, updated classifiers and CCIF-2018
based expenditure codes — so column sets drift within the nueva serie too. Handled downstream
by the per-table schema-fingerprint groups (``scripts/build_enigh.py``), not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ._catalog import CatalogEntry

_BASE = "https://www.inegi.org.mx/contenidos/programas/enigh/nc/"

# Date this catalog was last verified against the live INEGI tree.
CATALOG_VERIFIED_DATE = "2026-08-27"

# Canonical table names = the nueva-serie names. concentradohogar is the analysis-ready
# household summary (income/expenditure aggregates); viviendas/hogares/poblacion the three
# survey levels; ingresos/trabajos/agro/noagro person-level income and work; gastoshogar/
# gastospersona/erogaciones the expenditure detail.
NS_TABLES: tuple[str, ...] = (
    "concentradohogar", "viviendas", "hogares", "poblacion", "ingresos", "gastoshogar",
    "gastospersona", "trabajos", "agro", "noagro", "erogaciones",
)
# Tables that exist only in the NCV (2008–2014) regime.
NCV_ONLY_TABLES: tuple[str, ...] = ("gastotarjetas", "gastos")
TABLES: tuple[str, ...] = NS_TABLES + NCV_ONLY_TABLES

# Canonical name → INEGI stem in the NCV ZIP filename (``NCV_{stem}_{year}_concil_2010``).
# A callable resolves year-dependent stems; ``None`` means the table is absent that year.
_NCV_STEMS: dict[str, object] = {
    "concentradohogar": "Concentrado",
    "viviendas": lambda y: {2014: "Vivi", 2012: "Viviendas"}.get(y),
    "hogares": "Hogares",
    "poblacion": "Poblacion",
    "ingresos": "Ingresos",
    "gastoshogar": lambda y: "Gastohogar" if y >= 2012 else None,
    "gastospersona": lambda y: "Gastopersona" if y >= 2012 else None,
    "gastos": lambda y: "Gastos" if y <= 2010 else None,   # combined hogar+persona table
    "trabajos": "Trabajos",
    "agro": "Agropecuario",
    "noagro": "Noagropecuario",
    "erogaciones": "Erogaciones",
    "gastotarjetas": "Gastotarjetas",
}

_NS_YEARS = (2016, 2018, 2020, 2022, 2024)
_NCV_YEARS = (2008, 2010, 2012, 2014)


@dataclass(frozen=True)
class EnighEdition:
    """One ENIGH edition: a stable period id (the year, e.g. ``"2022"``) plus its regime."""

    period: str
    year: int
    regime: str

    @property
    def label(self) -> str:
        """Human label, e.g. ``"ENIGH 2022 (nueva serie)"``."""
        kind = "nueva serie" if self.regime == "ns" else "nueva construcción de variables"
        return f"ENIGH {self.year} ({kind})"

    @property
    def tables(self) -> tuple[str, ...]:
        """The tables INEGI publishes for this edition (canonical names)."""
        if self.regime == "ns":
            return NS_TABLES
        return tuple(t for t in TABLES if ncv_stem(self.year, t) is not None)

    def zip_filename(self, table: str) -> str:
        """ZIP filename for ``table`` under ``_BASE/{year}/microdatos/``."""
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}; known: {TABLES}")
        if table not in self.tables:
            raise ValueError(f"table {table!r} is not published for {self.label}")
        if self.regime == "ns":
            return f"enigh{self.year}_ns_{table}_csv.zip"
        return f"NCV_{ncv_stem(self.year, table)}_{self.year}_concil_2010_csv.zip"

    def url(self, table: str) -> str:
        """Full download URL for ``table``'s CSV ZIP."""
        return f"{_BASE}{self.year}/microdatos/{self.zip_filename(table)}"


def ncv_stem(year: int, table: str) -> str | None:
    """INEGI's NCV filename stem for ``table`` in ``year`` (``None`` if not published)."""
    spec = _NCV_STEMS.get(table)
    return spec(year) if callable(spec) else spec


def find_member(names: list[str], edition: EnighEdition, table: str) -> str | None:
    """Find ``table``'s CSV member among a ZIP's ``names``.

    Every ENIGH ZIP holds exactly one data CSV, named either ``{table}.csv`` (``ns``;
    ``ncv`` 2008/2010, lowercase canonical stem) or the ZIP's own stem
    (``ncv_gastotarjetas_2014_concil_2010.csv``, ``NCV_viviendas_2012_concil_2010.csv``).
    Matches case-insensitively on the basename against both spellings; if the ZIP holds a
    single ``.csv`` it is accepted regardless (the name is informational only).
    """
    csvs = [n for n in names if n.lower().endswith(".csv")]
    stem = ncv_stem(edition.year, table) if edition.regime == "ncv" else table
    pat = re.compile(
        rf"^(ncv_)?({re.escape(table)}|{re.escape(stem or table)})(_{edition.year}_concil_2010)?\.csv$",
        re.IGNORECASE,
    )
    for n in csvs:
        if pat.match(n.rsplit("/", 1)[-1]):
            return n
    if len(csvs) == 1:
        return csvs[0]
    return None


def enigh_zip_entry(edition: EnighEdition, table: str) -> CatalogEntry:
    """Return the download entry for one (edition, table) CSV ZIP."""
    return CatalogEntry(
        url=edition.url(table),
        extract_dir=Path("enigh") / edition.period / table,
        description=f"{edition.label} — {table}",
    )


def _generate_editions() -> list[EnighEdition]:
    eds = [EnighEdition(period=str(y), year=y, regime="ncv") for y in _NCV_YEARS]
    eds += [EnighEdition(period=str(y), year=y, regime="ns") for y in _NS_YEARS]
    return eds


# Chronological catalog of editions (2008 … 2024).
EDITIONS: list[EnighEdition] = _generate_editions()

EDITIONS_BY_PERIOD: dict[str, EnighEdition] = {e.period: e for e in EDITIONS}


def latest_edition() -> EnighEdition:
    """Return the most recent ENIGH edition in the catalog."""
    return EDITIONS[-1]
