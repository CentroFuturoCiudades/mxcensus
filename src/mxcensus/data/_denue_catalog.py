"""INEGI DENUE bulk-download catalog (per-release, per-state CSV ZIPs).

DENUE (Directorio Estadístico Nacional de Unidades Económicas) is published
periodically. Each release is downloadable per state from INEGI's "masiva" tree
under ``https://www.inegi.org.mx/contenidos/masiva/denue/``. The relative path
and filename **vary per release** (annual year tokens, full dates, or YYYY_MM
folders), so each release carries an explicit ``path_template``.

Two release-specific quirks (verified against the live tree, see
``docs/denue/STEP_1*``):
- **State 15 (México)** is split into two parts (``_1``/``_2``) from 2018 onward;
  the single-file URL 404s. ``denue_zip_entry`` returns one entry per part and the
  build concatenates them into one per-state parquet.
- **State 18 in the 2015 release** uses date ``04062015`` instead of ``25022015``.

Release ids (``yyyymm``): months are used where known; the 2010–2012 annual editions
have no published month and use ``"00"`` (e.g. ``"201000"``).

Templates were cross-checked with a known-good batch downloader and re-verified
against the live tree on ``CATALOG_VERIFIED_DATE``. Releases run **2010 .. 2025-05**.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._catalog import STATE_CODE_FMT, CatalogEntry

_BASE = "https://www.inegi.org.mx/contenidos/masiva/denue/"

# Date this catalog was last verified against the live INEGI masiva tree.
CATALOG_VERIFIED_DATE = "2026-06-01"


@dataclass(frozen=True)
class DenueRelease:
    """One DENUE edition: a stable id, a human label, and its URL path template.

    ``path_template`` is relative to ``_BASE`` and contains ``{state}`` (2-digit
    code) and ``{part}`` (``""`` normally, ``"_1"``/``"_2"`` for multipart states).
    """

    yyyymm: str
    label: str
    path_template: str


# Verified release catalog (24 releases). Each template carries {state} and {part}.
RELEASES: list[DenueRelease] = [
    DenueRelease("201000", "datos de 2010", "2010/denue_{state}{part}_2010_csv.zip"),
    DenueRelease("201100", "datos de 2011", "2011/denue_{state}{part}_2011_csv.zip"),
    DenueRelease("201200", "datos de 2012", "2012/denue_{state}{part}_2012_csv.zip"),
    DenueRelease("201307", "datos a julio de 2013", "2013_JULIO/denue_{state}{part}_2013_csv.zip"),
    DenueRelease("201310", "datos a octubre de 2013", "2013_OCTUBRE/denue_{state}{part}_2013_csv.zip"),
    DenueRelease("201502", "datos a febrero de 2015", "2015/denue_{state}{part}_25022015_csv.zip"),
    DenueRelease("201601", "datos a enero de 2016", "2016_01/denue_{state}{part}_0116_csv.zip"),
    DenueRelease("201610", "datos a octubre de 2016", "2016_10/denue_{state}{part}_1016_csv.zip"),
    DenueRelease("201703", "datos a marzo de 2017", "2017_03/denue_{state}{part}_0317_csv.zip"),
    DenueRelease("201711", "datos a noviembre de 2017", "2017_11/denue_{state}{part}_1117_csv.zip"),
    DenueRelease("201803", "datos a marzo de 2018", "2018_03/denue_{state}{part}_0318_csv.zip"),
    DenueRelease("201811", "datos a noviembre de 2018", "2018_11/denue_{state}{part}_1118_csv.zip"),
    DenueRelease("201904", "datos a abril de 2019", "2019_04/denue_{state}{part}_0419_csv.zip"),
    DenueRelease("201911", "datos a noviembre de 2019", "2019_11/denue_{state}{part}_1119_csv.zip"),
    DenueRelease("202004", "datos a abril de 2020", "2020_04/denue_{state}{part}_0420_csv.zip"),
    DenueRelease("202011", "datos a noviembre de 2020", "2020_11/denue_{state}{part}_1120_csv.zip"),
    DenueRelease("202105", "datos a mayo de 2021", "2021_05/denue_{state}{part}_0521_csv.zip"),
    DenueRelease("202111", "datos a noviembre de 2021", "2021_11/denue_{state}{part}_1121_csv.zip"),
    DenueRelease("202205", "datos a mayo de 2022", "2022_05/denue_{state}{part}_0522_csv.zip"),
    DenueRelease("202211", "datos a noviembre de 2022", "2022_11/denue_{state}{part}_1122_csv.zip"),
    DenueRelease("202311", "datos a noviembre de 2023", "2023_11/denue_{state}{part}_1123_csv.zip"),
    DenueRelease("202405", "datos a mayo de 2024", "2024_05/denue_{state}{part}_0524_csv.zip"),
    DenueRelease("202411", "datos a noviembre de 2024", "2024_11/denue_{state}{part}_1124_csv.zip"),
    DenueRelease("202505", "datos a mayo de 2025", "2025_05/denue_{state}{part}_0525_csv.zip"),
]

RELEASES_BY_YYYYMM: dict[str, DenueRelease] = {r.yyyymm: r for r in RELEASES}


def latest_release() -> DenueRelease:
    """Return the most recent DENUE release in the catalog."""
    return RELEASES[-1]


def _parts_for(release: DenueRelease, state: int) -> list[str]:
    """Return the part suffixes for a (release, state) — state 15 is split from 2018."""
    if state == 15 and int(release.yyyymm[:4]) >= 2018:
        return ["_1", "_2"]
    return [""]


def denue_zip_entry(release: DenueRelease, state: int) -> list[CatalogEntry]:
    """Return the download entries (one per part) for a state's ZIP(s) of ``release``."""
    code = STATE_CODE_FMT(state)
    entries: list[CatalogEntry] = []
    for part in _parts_for(release, state):
        rel = release.path_template.format(state=code, part=part)
        if release.yyyymm == "201502" and state == 18:  # state-18 2015 date quirk
            rel = rel.replace("25022015", "04062015")
        entries.append(
            CatalogEntry(
                url=_BASE + rel,
                extract_dir=Path("denue") / release.yyyymm / f"{code}{part}",
                description=f"DENUE {release.label} — state {state}{part}",
            )
        )
    return entries
