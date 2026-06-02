# mxcensus

Data loader and preprocessor for Mexico's **2020 Census** (Censo de Población y
Vivienda 2020, CPV 2020), published by INEGI.

`mxcensus` fetches pre-converted parquet files from a curated mirror, parses them
(handling INEGI's censoring and missing-data conventions), and returns clean,
analysis-ready pandas DataFrames.

> **Unofficial project.** `mxcensus` is an independent, community-maintained tool.
> It is **not** produced, endorsed, sponsored, or supported by INEGI. See
> [Data source and attribution](#data-source-and-attribution) below.

## Installation

```bash
uv pip install -e ".[dev]"   # Python 3.13+
```

## Quick start

```python
import mxcensus

# Full pipeline for one state (9 = Ciudad de México)
census = mxcensus.load_census(state=9)

# Extended-questionnaire microdata
personas = mxcensus.load_extended_personas(state=9)
viviendas = mxcensus.load_extended_viviendas(state=9)

# Geometries (Marco Geoestadístico) merged with census counts
mg_aur, mg_loc_ageb = mxcensus.load_mg_census(state=9)

# DENUE economic units — any release, harmonized to the latest schema by default
denue = mxcensus.load_denue(state=9)                      # latest release
denue_2010 = mxcensus.load_denue(state=9, release="201000")   # comparable to latest
raw = mxcensus.load_denue(state=9, release="201000", harmonize=False)  # raw schema
```

Pre-download a state's files (optional; loaders fetch on demand):

```bash
mxcensus fetch 9        # all four datasets for state 9
mxcensus info           # cache directory and mirror URL
```

## Datasets

| Dataset | Level | Description |
|---------|-------|-------------|
| **ITER** | Locality | Aggregate counts (state → municipality → locality) |
| **RESARGEBUB** | Urban block | AGEB (urban statistical areas) and MZA (city blocks) |
| **Cuestionario Ampliado** | Microdata | Individual person and household records |
| **Marco Geoestadístico** | Geometries | INEGI's 2020 geostatistical boundaries (15 layers/state) as GeoParquet |
| **DENUE** | Establishments | Economic-units directory, 24 releases 2010–2025, as point GeoParquet |

### DENUE (multi-temporal)

DENUE (Directorio Estadístico Nacional de Unidades Económicas) is mirrored for all 24
releases (2010–2025) × 32 states as point GeoParquet (`denue_{YYYYMM}_{NN}.parquet`,
EPSG:4326). Its schema drifted substantially over time (column names, encodings, the
`per_ocu` personnel strata), so `load_denue(state=N)` **harmonizes** each release to the
latest schema by default for longitudinal analysis; pass `harmonize=False` for the raw
release schema, or `release="YYYYMM"` for a specific edition. The schema groups and the
documented inconsistencies (drift, duplicates, malformed/missing files) live in
[docs/denue/](docs/denue/).

### Geometries (Marco Geoestadístico)

All 15 INEGI Marco Geoestadístico 2020 layers per state are mirrored as GeoParquet,
named `mg_{suffix}_{NN}.parquet` (suffix ∈ `a, ar, cd, e, ent, fm, l, lpr, m, mun, pe,
pem, sia, sil, sip`; `NN` = state code). Fetch individual layers via
`mxcensus.data.POOCH.fetch("mg_m_09.parquet")`. The convenience wrapper
`load_mg_census(state=N)` consumes four of them (`a` urban AGEB, `l` urban locality,
`lpr` rural locality points, `ar` rural AGEB) and returns census counts joined to
geometry as a GeoDataFrame.

## Variable dictionaries

INEGI's variable dictionaries are bundled with the package and exposed as plain
dicts keyed by variable mnemonic — no download required:

```python
mxcensus.variables_iter()          # ITER indicators (name, description, range)
mxcensus.variables_resargebub()    # RESARGEBUB indicators
mxcensus.variables_personas()      # person microdata variables + category labels
mxcensus.variables_viviendas()     # household microdata variables + category labels
mxcensus.variables_denue("g10")    # DENUE variables for a schema group (g01..g11)
mxcensus.denue_schema_map()        # DENUE schema groups + the latest (harmonization target)
```

The ITER and RESARGEBUB dictionaries are national (identical across states), so a
single copy of each is bundled. Note their schema differs from the microdata
dictionaries: aggregate indicators carry `Indicador` / `Descripción` / `Rangos` /
`Longitud` fields, while the microdata variables include categorical code→label
maps under `Categorías`.

## Data source and attribution

All data originates from INEGI's open-data ("datos abiertos") releases:

- Census tabular data and microdata — Censo de Población y Vivienda 2020:
  <https://www.inegi.org.mx/programas/ccpv/2020/>
- Geometries — Marco Geoestadístico (Censo 2020):
  <https://www.inegi.org.mx/temas/mg/>
- Economic units — Directorio Estadístico Nacional de Unidades Económicas (DENUE):
  <https://www.inegi.org.mx/app/mapa/denue/>

When you publish work that uses data obtained through `mxcensus`, INEGI's terms
require you to credit INEGI as the author of the data. Use the citation(s):

> **Fuente: INEGI, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Marco Geoestadístico, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Directorio Estadístico Nacional de Unidades Económicas (DENUE).**

The data is provided under INEGI's **Términos de Libre Uso de la Información del
INEGI** (Terms of Free Use):

- <https://www.inegi.org.mx/inegi/terminos.html>
- [Full text (PDF)](https://www.inegi.org.mx/contenidos/inegi/doc/terminos_info.pdf)

These terms permit copying, publishing, adapting, extracting, and even commercial
use of the information, **provided that** you (1) credit INEGI as author using the
citation above, (2) inform end users of any analysis or transformation applied to
the data, and (3) do not present your use as an official INEGI position or as
endorsed by INEGI.

### Notice of transformation

In compliance with the terms above (clause 1g), note that `mxcensus` does **not**
distribute INEGI's data unaltered. The original INEGI CSV files are transformed
before and during loading:

- **Format conversion** — the source CSVs are converted to parquet, and the Marco
  Geoestadístico GeoPackage layers to GeoParquet (rural locality points promoted to
  MultiPoint), for the mirror.
- **Censored values** — INEGI's `*` suppression marker (meaning 0, 1, or 2
  persons) is mapped to masked integers, and zeros are imputed where parent-level
  totals confirm a suppressed value must be 0.
- **Missing data** — INEGI's `N/D` marker is converted to `NaN`.
- **Derived columns** — the extended microdata loaders add summary flags (e.g.
  health-insurance, disability, transport, income bins) computed from the raw
  fields.
- **DENUE harmonization** — DENUE CSVs are converted to point GeoParquet (geometry
  from `latitud`/`longitud`); by default `load_denue` further **harmonizes** older
  releases onto the latest release's schema (renaming columns, normalizing the
  `per_ocu` and `tipoUniEco` strata across encodings, the `fecha_alta` date format,
  and adding/dropping columns). Pass `harmonize=False` for the raw release schema.
  A handful of undecodable bytes in one source file are replaced with U+FFFD (`�`)
  during conversion; otherwise text is preserved as INEGI published it — including
  the source data-entry errors the validation reports flag (e.g. non-numeric postal
  codes), which are **not** corrected or imputed. Point geometry is built from the
  coordinates as published and validated against each row's own state boundary: where a
  deterministic transform (a latitude/longitude swap or a dropped minus sign) places an
  offending coordinate back inside its state, the geometry is corrected accordingly
  (this covers the 2012 file where INEGI transposed the columns for all rows); points
  that no transform can place inside the state — or that fall outside Mexico entirely —
  get **null** geometry. In every case the raw `latitud`/`longitud` columns are kept
  verbatim; only the derived geometry is corrected or nulled.

**These transformations are performed by `mxcensus`, not by INEGI.** Any errors,
imputations, or derived values are the responsibility of this package and must not
be attributed to INEGI. INEGI's own variable dictionaries are bundled unmodified
(see [Variable dictionaries](#variable-dictionaries)); for the unaltered source
data files and their complete metadata and catalogs, download directly from the
INEGI links above.

## License

The `mxcensus` **source code** is released under the [MIT License](LICENSE).

This license covers only the software (the Python package, build scripts, and the
bundled YAML configuration). It does **not** apply to the census data, which
remains subject to INEGI's *Términos de Libre Uso de la Información del INEGI* as
described in [Data source and attribution](#data-source-and-attribution) above.
The bundled variable dictionaries are derived from INEGI's published dictionaries
and are likewise attributable to INEGI as their source.