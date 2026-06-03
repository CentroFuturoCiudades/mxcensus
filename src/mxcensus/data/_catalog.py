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
    1: "ags",
    2: "bc",
    3: "bcs",
    4: "cam",
    5: "coa",
    6: "col",
    7: "chs",
    8: "chh",
    9: "cdmx",
    10: "dgo",
    11: "gto",
    12: "gro",
    13: "hgo",
    14: "jal",
    15: "mex",
    16: "mich",
    17: "mor",
    18: "nay",
    19: "nl",
    20: "oax",
    21: "pue",
    22: "qro",
    23: "qroo",
    24: "slp",
    25: "sin",
    26: "son",
    27: "tab",
    28: "tam",
    29: "tla",
    30: "ver",
    31: "yuc",
    32: "zac",
}


def STATE_CODE_FMT(state: int) -> str:
    """Return the zero-padded two-digit state code string."""
    return f"{state:02d}"


# Two-digit state ENTIDAD code → lowercase name slug used in the Marco Geoestadístico
# per-state download filename ({code}_{slug}.zip). The slug (not just the code) is
# required by the URL; verified against the INEGI bvinegi tree (2026-06-03).
STATE_SLUG_MG: dict[int, str] = {
    1: "aguascalientes",
    2: "bajacalifornia",
    3: "bajacaliforniasur",
    4: "campeche",
    5: "coahuiladezaragoza",
    6: "colima",
    7: "chiapas",
    8: "chihuahua",
    9: "ciudaddemexico",
    10: "durango",
    11: "guanajuato",
    12: "guerrero",
    13: "hidalgo",
    14: "jalisco",
    15: "mexico",
    16: "michoacandeocampo",
    17: "morelos",
    18: "nayarit",
    19: "nuevoleon",
    20: "oaxaca",
    21: "puebla",
    22: "queretaro",
    23: "quintanaroo",
    24: "sanluispotosi",
    25: "sinaloa",
    26: "sonora",
    27: "tabasco",
    28: "tamaulipas",
    29: "tlaxcala",
    30: "veracruzignaciodelallave",
    31: "yucatan",
    32: "zacatecas",
}

# Marco Geoestadístico, Censo de Población y Vivienda 2020 (UPC 889463807469).
# Per-state shapefile ZIPs live directly under this folder as {code}_{slug}.zip.
_MG_BASE = (
    "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/"
    "bvinegi/productos/geografia/marcogeo/889463807469"
)


def marco_geo_zip_url(state: int) -> str:
    """Return the INEGI per-state Marco Geoestadístico 2020 shapefile ZIP URL."""
    return f"{_MG_BASE}/{STATE_CODE_FMT(state)}_{STATE_SLUG_MG[state]}.zip"


_BASE = "https://www.inegi.org.mx/contenidos/programas/ccpv/2020"

# Date this catalog was last verified against the INEGI portal
CATALOG_VERIFIED_DATE = "2026-05-31"


@dataclass
class CatalogEntry:
    """URL, raw-data extraction subdirectory, and description for one INEGI ZIP."""

    url: str
    extract_dir: Path  # subdirectory of raw_dir the ZIP is extracted into
    description: str


def iter_entry(state: int) -> CatalogEntry:
    """Return the INEGI download entry for the ITER (locality-level) file of ``state``."""
    code = STATE_CODE_FMT(state)
    return CatalogEntry(
        url=f"{_BASE}/datosabiertos/iter/iter_{code}_cpv2020_csv.zip",
        extract_dir=Path("loc"),
        description=f"ITER state {state} — locality-level aggregate counts",
    )


def resargebub_entry(state: int) -> CatalogEntry:
    """Return the INEGI download entry for the RESARGEBUB (AGEB/block-level) file of ``state``."""
    code = STATE_CODE_FMT(state)
    return CatalogEntry(
        url=f"{_BASE}/datosabiertos/ageb_manzana/ageb_mza_urbana_{code}_cpv2020_csv.zip",
        extract_dir=Path("ageb_manz"),
        description=f"RESARGEBUB state {state} — AGEB/block-level aggregate counts",
    )


def cuestionario_ampliado_entry(state: int) -> CatalogEntry:
    """Return the INEGI download entry for the extended-questionnaire ZIP of ``state``."""
    abbr = STATE_ABBR[state]
    return CatalogEntry(
        url=f"{_BASE}/microdatos/Censo2020_CA_{abbr}_csv.zip",
        extract_dir=Path("cuestionario_ampliado"),
        description=f"Extended questionnaire microdata — state {state} ({abbr})",
    )
