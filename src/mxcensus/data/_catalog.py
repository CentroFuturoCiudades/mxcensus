"""INEGI Census 2020 (CPV 2020) download catalog + shared state tables / MG editions.

URL patterns were identified from the INEGI open-data portal for the
Censo de Población y Vivienda 2020. Verify against the live portal before
relying on downloads, as INEGI occasionally reorganises file locations.

The multi-year census family (1990–2025) lives in ``_cpv_catalog.py``; this module
keeps the legacy 2020 builders plus the pieces every family shares (``STATE_ABBR``,
``STATE_CODE_FMT``, ``CatalogEntry``) and the Marco Geoestadístico editions.
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

_MG_ROOT = (
    "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/"
    "bvinegi/productos/geografia"
)


@dataclass(frozen=True)
class MgEdition:
    """One Marco Geoestadístico edition, keyed by the census period it frames.

    ``layout="state"`` editions ship one ``{code}_{slug}.zip`` per state under
    ``marcogeo/{upc}/`` (15 layers each); ``layout="national"`` editions ship a single
    ``marc_geo/{upc}_s.zip`` that the build splits per state. URLs and slugs verified
    against INEGI's product API (``…/app/api/productos/interna_v2/ficha/datos?upc=``)
    on 2026-10-07.
    """

    period: str
    upc: str
    title: str
    layout: str  # "state" | "national"


MG_EDITIONS: dict[str, MgEdition] = {
    e.period: e
    for e in (
        MgEdition("1995", "702825292836", "Marco Geoestadístico municipal 1995", "national"),
        MgEdition("2000", "702825292843", "Marco Geoestadístico municipal 2000", "national"),
        MgEdition("2005", "702825292850", "Marco Geoestadístico municipal 2005 v1.0", "national"),
        MgEdition("2010", "702825292812", "Marco Geoestadístico 2010 v5.0", "national"),
        MgEdition("2020", "889463807469",
                  "Marco Geoestadístico, Censo de Población y Vivienda 2020", "state"),
        MgEdition("2025", "794551196649",
                  "Marco Geoestadístico, Encuesta Intercensal 2025", "state"),
    )
}

# The mirror's original MG files carry no period: ``mg_{suffix}_{NN}`` *is* 2020.
MG_LEGACY_PERIOD = "2020"


def _mg_edition(period: str) -> MgEdition:
    try:
        return MG_EDITIONS[period]
    except KeyError:
        raise ValueError(
            f"unknown Marco Geoestadístico period {period!r}; known: {sorted(MG_EDITIONS)}"
        ) from None


def marco_geo_zip_url(state: int, period: str = MG_LEGACY_PERIOD) -> str:
    """Return the INEGI per-state Marco Geoestadístico shapefile ZIP URL for ``period``."""
    ed = _mg_edition(period)
    if ed.layout != "state":
        raise ValueError(
            f"MG {period} is published as one national ZIP; use marco_geo_national_url()"
        )
    return f"{_MG_ROOT}/marcogeo/{ed.upc}/{STATE_CODE_FMT(state)}_{STATE_SLUG_MG[state]}.zip"


def marco_geo_national_url(period: str) -> str:
    """Return the single national ZIP URL of a ``layout="national"`` MG edition."""
    ed = _mg_edition(period)
    if ed.layout != "national":
        raise ValueError(f"MG {period} is published per state; use marco_geo_zip_url()")
    return f"{_MG_ROOT}/marc_geo/{ed.upc}_s.zip"


def mg_filename(suffix: str, state: int, period: str = MG_LEGACY_PERIOD) -> str:
    """Mirror filename of one MG layer: ``mg_{suffix}_{NN}`` for 2020, else
    ``mg_{suffix}_{period}_{NN}`` (the ``mg_`` prefix keeps registry protection)."""
    _mg_edition(period)
    code = STATE_CODE_FMT(state)
    if period == MG_LEGACY_PERIOD:
        return f"mg_{suffix}_{code}.parquet"
    return f"mg_{suffix}_{period}_{code}.parquet"


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
