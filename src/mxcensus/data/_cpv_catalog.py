"""INEGI population & housing census family (CPV) — download catalog, 1990–2025.

One multi-temporal family covers every *censo* (1990, 2000, 2010, 2020), *conteo* (1995,
2005) and *encuesta intercensal* (2015, 2025). An edition is keyed by its year (unique
across the three kinds) and publishes a subset of seven canonical tables:

- microdata (sample/extended questionnaire, one ZIP per state carrying several tables):
  ``viviendas`` (dwelling or dwelling+household record), ``hogares`` (household record,
  2005 sample and the 1995 ``datgen95`` household file), ``personas``, ``migrantes``
  (international emigrants of the household);
- aggregates: ``iter`` (principales resultados por localidad, every censo/conteo),
  ``ageb`` (urban AGEB/block results, 2010 and 2020), ``estimaciones`` (EIC 2025
  estimates for the nation, states, every municipality and the ≥50k localities —
  national, one file).

URLs, ZIP members and file formats were verified against INEGI's servers on
2026-10-07 (``docs/cpv/STEP_0_probe.md``): every product listed here answered a HEAD
with a ZIP ``Content-Type``. INEGI soft-404s (HTTP 200, ``text/html``, 2263 bytes), so the
build judges a download by its ZIP integrity, never the status code.

Mirror files are ``cpv_{table}_{period}_{NN}.parquet`` (per state) or
``cpv_{table}_{period}.parquet`` (national tables), faithful raw (every column ``str``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from mxcensus.data._catalog import STATE_ABBR, STATE_CODE_FMT, CatalogEntry

_BASE = "https://www.inegi.org.mx/contenidos/programas"

# Date this catalog was last verified against the INEGI portal.
CATALOG_VERIFIED_DATE = "2026-10-07"

KINDS = ("censo", "conteo", "intercensal")
MICRO_TABLES = ("viviendas", "hogares", "personas", "migrantes")
AGG_TABLES = ("iter", "ageb", "estimaciones")
TABLES = MICRO_TABLES + AGG_TABLES
# Tables INEGI publishes as one national file (no per-state split).
NATIONAL_TABLES = frozenset({"estimaciones"})

# Table → the INEGI product (ZIP kind) it is extracted from. One microdata ZIP per state
# holds every microdata table of the edition (as ENOE's quarter ZIP holds five tables).
PRODUCT_OF: dict[str, str] = {
    **{t: "microdatos" for t in MICRO_TABLES},
    "iter": "iter",
    "ageb": "ageb",
    "estimaciones": "estimaciones",
}
PRODUCTS = ("microdatos", "iter", "ageb", "estimaciones")

# State slug in the 1990–2010 DBF/XLS file names (`{NN}_{slug}_{year}_iter`,
# `{NN}_{slug}_2010_ageb_manzana_urbana`). Identical in every year (verified 2026-10-07);
# 0 = the national file. Distinct from the MG slugs (``_catalog.STATE_SLUG_MG``).
HIST_SLUG: dict[int, str] = {
    0: "nacional", 1: "aguascalientes", 2: "baja_california", 3: "baja_california_sur",
    4: "campeche", 5: "coahuila", 6: "colima", 7: "chiapas", 8: "chihuahua",
    9: "distrito_federal", 10: "durango", 11: "guanajuato", 12: "guerrero", 13: "hidalgo",
    14: "jalisco", 15: "mexico", 16: "michoacan", 17: "morelos", 18: "nayarit",
    19: "nuevo_leon", 20: "oaxaca", 21: "puebla", 22: "queretaro", 23: "quintana_roo",
    24: "san_luis_potosi", 25: "sinaloa", 26: "sonora", 27: "tabasco", 28: "tamaulipas",
    29: "tlaxcala", 30: "veracruz", 31: "yucatan", 32: "zacatecas",
}

# Mirror filename: per-state ``cpv_{table}_{period}_{NN}``, national ``cpv_{table}_{period}``.
# Table names never contain "_" (asserted below), so the parse is unambiguous.
FILE_RE = re.compile(
    r"^cpv_(?P<table>[a-z]+)_(?P<period>\d{4})(?:_(?P<state>\d{2}))?(?:\.parquet)?$"
)


@dataclass(frozen=True)
class CpvEdition:
    """One census / conteo / intercensal edition and its INEGI download layout.

    ``urls`` maps a product to its path under ``{_BASE}/{program_path}/`` with the
    placeholders ``{nn}`` (zero-padded state), ``{abbr}`` (``STATE_ABBR``) and
    ``{slug}`` (``HIST_SLUG``). ``members`` maps a table to a case-insensitive regex for
    its data file's basename inside the product ZIP (``{nn}`` substituted).
    """

    period: str
    year: int
    kind: str
    title: str
    program_path: str
    urls: dict[str, str] = field(compare=False, hash=False)
    members: dict[str, str] = field(compare=False, hash=False)
    weighted: bool = True       # microdata carry an expansion factor
    fmt: str = "csv"            # microdata format: "csv" | "dbf"
    ddi_id: int | None = None   # INEGI RNM DDI catalog id (None = none located; fetched by
                                # build_cpv.py --dictionary — 2020 builds from its FD xlsx)
    biinegi_id: int | None = None  # INEGI file-listing API id (idBiinegi)
    mg_period: str | None = None   # Marco Geoestadístico edition framing it (_catalog.MG_EDITIONS)
    notes: str = ""

    @property
    def label(self) -> str:
        return f"{self.title} ({self.period})"

    @property
    def tables(self) -> tuple[str, ...]:
        """Canonical tables this edition publishes, in ``TABLES`` order."""
        return tuple(t for t in TABLES if t in self.members)

    @property
    def products(self) -> tuple[str, ...]:
        return tuple(p for p in PRODUCTS if p in self.urls)

    def tables_in(self, product: str) -> tuple[str, ...]:
        """Tables of this edition extracted from ``product``'s ZIP."""
        return tuple(t for t in self.tables if PRODUCT_OF[t] == product)

    def has(self, table: str) -> bool:
        return table in self.members

    def per_state(self, product: str) -> bool:
        """Whether ``product`` ships one ZIP per state (else one national ZIP)."""
        if product not in self.urls:
            raise ValueError(f"{self.label} has no {product!r} product")
        return "{" in self.urls[product]

    def _require(self, table: str) -> None:
        if table not in TABLES:
            raise ValueError(f"unknown CPV table {table!r}; known: {list(TABLES)}")
        if not self.has(table):
            raise ValueError(
                f"{self.label} does not publish {table!r}; it has {list(self.tables)}"
            )

    def zip_url(self, product: str, state: int | None = None) -> str:
        """Download URL of ``product``'s ZIP (``state`` required for per-state products)."""
        if product not in self.urls:
            raise ValueError(f"{self.label} has no {product!r} product")
        tmpl = self.urls[product]
        if "{" in tmpl:
            if state is None:
                raise ValueError(f"{self.label} {product!r} is per state; pass state=")
            _check_state(state)
            tmpl = tmpl.format(nn=STATE_CODE_FMT(state), abbr=STATE_ABBR[state],
                               slug=HIST_SLUG[state])
        return f"{_BASE}/{self.program_path}/{tmpl}"

    def zip_filename(self, product: str, state: int | None = None) -> str:
        """INEGI's own ZIP basename (already edition-qualified — safe as a cache key)."""
        return self.zip_url(product, state).rsplit("/", 1)[-1]

    def member_regex(self, table: str, state: int | None = None) -> re.Pattern:
        self._require(table)
        pat = self.members[table]
        if "{nn}" in pat:
            if state is None:
                raise ValueError(f"{self.label} {table!r} member is per state; pass state=")
            pat = pat.replace("{nn}", STATE_CODE_FMT(state))
        return re.compile(rf"^{pat}$", re.IGNORECASE)

    def filename(self, table: str, state: int | None = None) -> str:
        """Mirror (registry) filename of ``table`` for ``state``."""
        self._require(table)
        return cpv_filename(table, self.period, state)


def _check_state(state: int) -> None:
    if state not in STATE_ABBR:
        raise ValueError(f"state must be an INEGI state code 1-32, got {state!r}")


def cpv_filename(table: str, period: str, state: int | None = None) -> str:
    """``cpv_{table}_{period}_{NN}.parquet`` (per-state) / ``cpv_{table}_{period}.parquet``."""
    if table in NATIONAL_TABLES:
        if state is not None:
            raise ValueError(f"{table!r} is a national table; it has no per-state file")
        return f"cpv_{table}_{period}.parquet"
    if state is None:
        raise ValueError(f"{table!r} is mirrored per state; pass state=")
    _check_state(state)
    return f"cpv_{table}_{period}_{STATE_CODE_FMT(state)}.parquet"


def parse_filename(name: str) -> tuple[str, str, int | None]:
    """Inverse of :func:`cpv_filename` → ``(table, period, state | None)``."""
    m = FILE_RE.match(Path(name).name)
    if m is None or m["table"] not in TABLES:
        raise ValueError(f"not a CPV mirror filename: {name!r}")
    state = int(m["state"]) if m["state"] else None
    if (state is None) != (m["table"] in NATIONAL_TABLES):
        raise ValueError(f"state suffix inconsistent with table in {name!r}")
    return m["table"], m["period"], state


# ---------------------------------------------------------------------------------------
# Editions (chronological). Member regexes are matched against the ZIP member basename.
# ---------------------------------------------------------------------------------------

EDITIONS: list[CpvEdition] = [
    CpvEdition(
        period="1990", year=1990, kind="censo",
        title="XI Censo General de Población y Vivienda 1990",
        program_path="ccpv/1990",
        urls={
            "microdatos": "microdatos/cgpv90p_{nn}_dbf.zip",
            "iter": "microdatos/iter/{nn}_{slug}_1990_iter_dbf.zip",
        },
        # 10% sample: one flat person-level file carrying the dwelling items (FOLIO_VIV);
        # the member is m_10{nn}.dbf for state 01 — pattern kept loose (sole data file).
        members={"personas": r"m_\d+\.dbf", "iter": r"ITER_{nn}DBF90\.dbf"},
        weighted=False, fmt="dbf", biinegi_id=781, mg_period=None,
        notes="10% sample, unweighted; no DDI; ITER mnemonics differ (P_TOTAL, HOMBRES…)",
    ),
    CpvEdition(
        period="1995", year=1995, kind="conteo",
        title="Conteo de Población y Vivienda 1995",
        program_path="ccpv/1995",
        urls={
            "microdatos": "microdatos/cpv95_{nn}_dbf.zip",
            "iter": "microdatos/iter/{nn}_{slug}_1995_iter_dbf.zip",
        },
        # Encuesta del Conteo: datgen95 = household record (ENT…VIV, HOGAR; FAC_POB/
        # FAC_VIV/FAC_PROM), migint95 = international migrants.
        members={"hogares": r"datgen95\.dbf", "migrantes": r"migint95\.dbf",
                 "iter": r"ITER_{nn}DBF95\.dbf"},
        fmt="dbf", biinegi_id=343, mg_period="1995",
        notes="weights FAC_POB/FAC_VIV/FAC_PROM (not FACTOR); no DDI",
    ),
    CpvEdition(
        period="2000", year=2000, kind="censo",
        title="XII Censo General de Población y Vivienda 2000",
        program_path="ccpv/2000",
        urls={
            "microdatos": "microdatos/muestra/cgpv2000_{nn}_dbf.zip",
            "iter": "datosabiertos/cgpv2000_iter_{nn}_csv.zip",
        },
        # Muestra censal: VHO_F = dwelling+household (NUMVIV, NUMHOG), PER_F, MIN_F.
        members={"viviendas": r"VHO_F{nn}\.dbf", "personas": r"PER_F{nn}\.dbf",
                 "migrantes": r"MIN_F{nn}\.dbf", "iter": r"cgpv2000_iter_{nn}\.csv"},
        fmt="dbf", ddi_id=141, biinegi_id=2, mg_period="2000",
        notes="composite keys ENT/MUN/LOC/NUMVIV/NUMHOG; no downloadable AGEB",
    ),
    CpvEdition(
        period="2005", year=2005, kind="conteo",
        title="II Conteo de Población y Vivienda 2005",
        program_path="ccpv/2005",
        urls={
            "microdatos": "microdatos/muestra/cpv2005_{nn}_dbf.zip",
            "iter": "datosabiertos/cpv2005_iter_{nn}_csv.zip",
        },
        members={"viviendas": r"trvmue{nn}\.dbf", "hogares": r"trhmue{nn}\.dbf",
                 "personas": r"trpmue{nn}\.dbf", "iter": r"cpv2005_iter_{nn}\.csv"},
        weighted=False, fmt="dbf", ddi_id=140, biinegi_id=3, mg_period="2005",
        notes="10% sample, no weight (state-level reliability); keys CONS_MUN/CONS_VIV/"
              "CONS_HOG/CONS_PER; no downloadable AGEB",
    ),
    CpvEdition(
        period="2010", year=2010, kind="censo",
        title="Censo de Población y Vivienda 2010",
        program_path="ccpv/2010",
        urls={
            "microdatos": "microdatos/mpv/MC2010_{nn}_dbf.zip",
            "iter": "datosabiertos/iter_{nn}_2010_csv.zip",
            "ageb": "datosabiertos/ageb_y_manzana/resageburb_{nn}_2010_csv.zip",
        },
        members={"viviendas": r"Viviendas_{nn}\.dbf", "personas": r"Personas_{nn}\.dbf",
                 "migrantes": r"Migrantes_{nn}\.dbf", "iter": r"iter_{nn}_cpv2010\.csv",
                 "ageb": r"resultados_ageb_urbana_{nn}_cpv2010\.csv"},
        fmt="dbf", ddi_id=71, biinegi_id=487, mg_period="2010",
        notes="microdata DBF only (ID_VIV 8 chars — unique within a state only; ID_PER, "
              "ID_MIN); ITER/AGEB CSV headers lowercase",
    ),
    CpvEdition(
        period="2015", year=2015, kind="intercensal",
        title="Encuesta Intercensal 2015",
        program_path="intercensal/2015",
        urls={"microdatos": "microdatos/eic2015_{nn}_csv.zip"},
        members={"viviendas": r"TR_VIVIENDA{nn}\.csv", "personas": r"TR_PERSONA{nn}\.csv"},
        ddi_id=214, biinegi_id=1714, mg_period=None,
        notes="no migrantes table, no ITER/AGEB; MG frame not yet identified",
    ),
    CpvEdition(
        period="2020", year=2020, kind="censo",
        title="Censo de Población y Vivienda 2020",
        program_path="ccpv/2020",
        urls={
            "microdatos": "microdatos/Censo2020_CA_{abbr}_csv.zip",
            "iter": "datosabiertos/iter/iter_{nn}_cpv2020_csv.zip",
            "ageb": "datosabiertos/ageb_manzana/ageb_mza_urbana_{nn}_cpv2020_csv.zip",
        },
        members={"viviendas": r"Viviendas{nn}\.csv", "personas": r"Personas{nn}\.csv",
                 "migrantes": r"Migrantes{nn}\.csv",
                 "iter": r"conjunto_de_datos_iter_{nn}CSV20\.csv",
                 "ageb": r"conjunto_de_datos_ageb_urbana_{nn}_cpv2020\.csv"},
        ddi_id=632, biinegi_id=3001, mg_period="2020",
        notes="also mirrored in the legacy period-less files (iter_NN, personas_NN, …); "
              "dictionary = the FD xlsx (RNM DDI 632 is a Nesstar export with incomplete "
              "value labels — kept for reference, not used)",
    ),
    CpvEdition(
        period="2025", year=2025, kind="intercensal",
        title="Encuesta Intercensal 2025",
        program_path="eic/2025",
        urls={
            "microdatos": "microdatos/eic2025_micro_{nn}_csv.zip",
            "estimaciones": "datosabiertos/conjunto_de_datos_eic2025_105_csv.zip",
        },
        members={"viviendas": r"viviendas{nn}\.csv", "personas": r"personas{nn}\.csv",
                 "migrantes": r"migrantes{nn}\.csv",
                 "estimaciones": r"conjunto_datos_eic2025_105\.csv"},
        biinegi_id=3455, mg_period="2025",
        notes="published 2026-09-22; representative for every municipality and the 233 "
              "localities ≥50k; dictionary = microdatos/eic2025_micro_fd.xlsx (no DDI)",
    ),
]

EDITIONS_BY_PERIOD: dict[str, CpvEdition] = {e.period: e for e in EDITIONS}

# Documentation / dictionary sources outside the data ZIPs (relative to the program path).
DICTIONARY_URLS: dict[str, dict[str, str]] = {
    "2025": {"fd": "microdatos/eic2025_micro_fd.xlsx",
             "catalogos": "microdatos/889463931966_csv.zip"},
    "2020": {"fd": "microdatos/diccionario_cuestionario_ampliado_cpv2020.xlsx",
             "catalogos": "microdatos/Censo2020_clasificaciones_CPV_csv.zip"},
    "2015": {"fd": "doc/eic2015_fd.xls"},
    "2010": {"fd": "doc/diccionario_cuestionario_ampliado.xls",
             "catalogos": "doc/catalogos_2010_dbf.zip"},
    "2005": {"fd": "doc/fd_muestra_2005.xls", "catalogos": "doc/catalogos_muestra_2005.xls"},
    "2000": {"fd": "doc/fd_muestra_censal_2000_pdf.zip"},
    "1995": {"fd": "doc/fd_encuesta_cpv1995.pdf", "catalogos": "doc/catalogos_cpv1995.pdf"},
    "1990": {"fd": "doc/fd_cgpv1990.pdf", "catalogos": "doc/catalogos_1990.xls"},
}


def dictionary_url(period: str, kind: str) -> str:
    """URL of an edition's documentation file (``kind`` ∈ ``DICTIONARY_URLS[period]``)."""
    ed = get_edition(period)
    return f"{_BASE}/{ed.program_path}/{DICTIONARY_URLS[period][kind]}"


def get_edition(period: str | int) -> CpvEdition:
    try:
        return EDITIONS_BY_PERIOD[str(period)]
    except KeyError:
        raise ValueError(
            f"unknown CPV edition {period!r}; known: {list(EDITIONS_BY_PERIOD)}"
        ) from None


def latest_edition(table: str | None = None) -> CpvEdition:
    """Most recent edition overall, or the most recent one that publishes ``table``
    (microdata → 2025, ``iter``/``ageb`` → 2020)."""
    if table is not None and table not in TABLES:
        raise ValueError(f"unknown CPV table {table!r}; known: {list(TABLES)}")
    for ed in reversed(EDITIONS):
        if table is None or ed.has(table):
            return ed
    raise ValueError(f"no edition publishes {table!r}")  # pragma: no cover


def find_member(names: list[str], edition: CpvEdition, table: str,
                state: int | None = None) -> str:
    """The ZIP member holding ``table`` — matched on the basename, case-insensitively
    (INEGI mixes ``.CSV``/``.csv``, ``.DBF``/``.dbf`` and nests some members in folders).
    Raises ``LookupError`` listing the members when nothing (or more than one) matches."""
    rx = edition.member_regex(table, state)
    hits = [n for n in names if not n.endswith("/") and rx.match(n.rsplit("/", 1)[-1])]
    if len(hits) == 1:
        return hits[0]
    raise LookupError(
        f"{edition.label} {table!r}: expected one member matching {rx.pattern!r}, "
        f"found {hits or 'none'} in {names}"
    )


def cpv_zip_entry(edition: CpvEdition, product: str, state: int | None = None) -> CatalogEntry:
    """``CatalogEntry`` for one product ZIP (extracted under ``cpv/{period}/{product}``)."""
    where = f"state {STATE_CODE_FMT(state)}" if state is not None else "national"
    return CatalogEntry(
        url=edition.zip_url(product, state),
        extract_dir=Path("cpv") / edition.period / product,
        description=f"{edition.label} — {product}, {where}",
    )


assert all("_" not in t for t in TABLES), "table names must not contain '_' (FILE_RE)"
assert all(e.kind in KINDS for e in EDITIONS)
assert all(PRODUCT_OF[t] in e.urls for e in EDITIONS for t in e.members), \
    "every table needs its product's URL"
assert all(e.per_state(PRODUCT_OF[t]) == (t not in NATIONAL_TABLES)
           for e in EDITIONS for t in e.members), "per-state URL ⇔ per-state table"
