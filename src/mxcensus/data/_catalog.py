"""INEGI Census 2020 (CPV 2020) download catalog.

URL patterns were identified from the INEGI open-data portal for the
Censo de Población y Vivienda 2020. Verify against the live portal before
relying on downloads, as INEGI occasionally reorganises file locations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Two-digit state ENTIDAD code → lowercase abbreviation used in CA filenames
STATE_ABBR: dict[int, str] = {
    1: "ags", 2: "bc", 3: "bcs", 4: "camp", 5: "coah",
    6: "col", 7: "chis", 8: "chih", 9: "cdmx", 10: "dgo",
    11: "gto", 12: "gro", 13: "hgo", 14: "jal", 15: "mex",
    16: "mich", 17: "mor", 18: "nay", 19: "nl", 20: "oax",
    21: "pue", 22: "qro", 23: "qroo", 24: "slp", 25: "sin",
    26: "son", 27: "tab", 28: "tamps", 29: "tlax", 30: "ver",
    31: "yuc", 32: "zac",
}


def STATE_CODE_FMT(state: int) -> str:
    """Return the zero-padded two-digit state code string."""
    return f"{state:02d}"


_BASE = "https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos"

# Date this catalog was last verified against the INEGI portal
CATALOG_VERIFIED_DATE = "2025-05-29"


@dataclass
class CatalogEntry:
    url: str
    dest: Path  # relative to data_dir
    description: str


def iter_entry(state: int) -> CatalogEntry:
    code = STATE_CODE_FMT(state)
    return CatalogEntry(
        url=f"{_BASE}/iter/iter_{code}CSV20.zip",
        dest=Path("loc") / f"ITER_{code}CSV20.csv",
        description=f"ITER state {state} — locality-level aggregate counts",
    )


def resargebub_entry(state: int) -> CatalogEntry:
    code = STATE_CODE_FMT(state)
    return CatalogEntry(
        url=f"{_BASE}/ageb_manzana/ageb/RESAGEBURB_{code}CSV20.zip",
        dest=Path("ageb_manz") / f"RESAGEBURB_{code}CSV20.csv",
        description=f"RESARGEBUB state {state} — AGEB/block-level aggregate counts",
    )


def cuestionario_ampliado_entry(state: int) -> CatalogEntry:
    code = STATE_CODE_FMT(state)
    abbr = STATE_ABBR[state]
    folder = f"Censo2020_CA_{abbr}_csv"
    return CatalogEntry(
        url=f"{_BASE}/microdatos/cuestionario_ampliado/Censo2020_CA_{abbr}_csv.zip",
        dest=Path("cuestionario_ampliado") / folder,
        description=f"Extended questionnaire microdata — state {state} ({abbr})",
    )
