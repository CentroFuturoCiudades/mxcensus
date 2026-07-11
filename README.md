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

Requires **Python 3.13+**. Install the latest release straight from GitHub:

```bash
uv pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git"
# or pin to a released tag:
uv pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
# or add it to a project:
uv add "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
```

Plain `pip` works too:

```bash
pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
```

No data ships with the package — DataFrames are fetched on first use from the
public mirror and cached locally (run `mxcensus info` to see where).

### Development install

```bash
git clone https://github.com/CentroFuturoCiudades/mxcensus.git
cd mxcensus
uv pip install -e ".[dev]"   # editable, with build/test tooling
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

# ENOE labor-force survey — national quarterly microdata (no per-state split)
persons = mxcensus.load_enoe_persons(period="2023t1")     # analysis-ready person frame
persons = mxcensus.load_enoe_persons()                    # defaults to the latest quarter
sdem = mxcensus.load_enoe(table="sdem", period="2023t1")  # one raw table for one quarter
```

Pre-download a state's files (optional; loaders fetch on demand):

```bash
mxcensus fetch 9        # all four census datasets for state 9
mxcensus fetch 9 --dataset denue                  # DENUE (latest release) for state 9
mxcensus fetch 9 --dataset enoe --period 2023t1   # the five ENOE tables (national — 9 is ignored)
mxcensus info           # cache directory and mirror URL
```

## Datasets

| Dataset | Level | Description |
|---------|-------|-------------|
| **ITER** | Locality | Aggregate counts (state → municipality → locality) |
| **RESARGEBUB** | Urban block | AGEB (urban statistical areas) and MZA (city blocks) |
| **Cuestionario Ampliado** | Microdata | Individual person and household records |
| **Marco Geoestadístico** | Geometries | INEGI's 2020 geostatistical boundaries (15 layers/state) as GeoParquet |
| **DENUE** | Establishments | Economic-units directory, 25 releases 2010–2026, as point GeoParquet |
| **ENOE** | Labor force | Quarterly employment-survey microdata, 84 quarters 2005–2026, national (5 tables/quarter) |

### DENUE (multi-temporal)

DENUE (Directorio Estadístico Nacional de Unidades Económicas) is mirrored for all 25
releases (2010–2026) × 32 states as point GeoParquet (`denue_{YYYYMM}_{NN}.parquet`,
EPSG:4326). Its schema drifted substantially over time (column names, encodings, the
`per_ocu` personnel strata), so `load_denue(state=N)` **harmonizes** each release to the
latest schema by default for longitudinal analysis; pass `harmonize=False` for the raw
release schema, or `release="YYYYMM"` for a specific edition. The schema groups and the
documented inconsistencies (drift, duplicates, malformed/missing files) live in
[docs/denue/](docs/denue/).

### ENOE (labor-force survey, multi-temporal)

ENOE (Encuesta Nacional de Ocupación y Empleo) is INEGI's quarterly labor-force survey.
Unlike the other datasets it is **national** — one file set per quarter, not per state — and
each quarter bundles **five tables**: `viv` (dwelling), `hog` (household), `sdem`
(sociodemographic, the main person table), and `coe1`/`coe2` (the two employment-questionnaire
parts). All **84 quarters** from 2005-T1 to 2026-T1 are mirrored (2020-T2 is excluded — field
operations were suspended for COVID and replaced by the telephone survey ETOE), as faithful
`str`-typed parquet named `enoe_{table}_{period}.parquet` (e.g. `enoe_sdem_2023t1.parquet`).

Loaders:

```python
# One raw table for one quarter (period defaults to the latest quarter)
sdem = mxcensus.load_enoe(table="sdem", period="2023t1")
sdem_jal = mxcensus.load_enoe(table="sdem", period="2023t1", ent=14)   # filter to a state

# The analysis-ready person frame: SDEM joined with COE1/COE2, filtered to the canonical
# working-age universe, with a numeric `fac_tri` weight and labour-force flags
persons = mxcensus.load_enoe_persons(period="2023t1")

pop_15plus = persons["fac_tri"].sum()                              # ~99.7 M
pea        = persons.loc[persons["is_pea"], "fac_tri"].sum()       # economically active
participation = pea / pop_15plus                                   # ~0.602
informal   = persons.loc[persons["is_informal"], "fac_tri"].sum()
```

`load_enoe_persons` adds `is_pea` / `is_ocupado` / `is_informal` boolean flags and a canonical
numeric `fac_tri` expansion weight (coalescing the pre-2020 `fac` and later `fac_tri` columns),
and handles the survey's cross-era drift automatically — the `ent`→`cve_ent` geographic-key
rename (2026), the `FAC`→`FAC_TRI` weight rename (2020-T3), and the panel-era person key. Every
column is otherwise the faithful raw value. ENOE's schema drifts across eras, so each file is
fingerprinted into a **per-table schema group** and validated on load; cross-era
harmonization of the raw tables is not yet implemented (`harmonize=True` raises). The schema
groups, per-quarter inconsistency report, and validation report live in
[docs/enoe/](docs/enoe/).

#### Dwelling / household / combined loaders

The dwelling (`viv`) and household (`hog`) tables have their own analysis-ready loaders
(numeric weights + a hierarchical index), and `load_enoe_survey` loads all three household-survey
levels at once with a **shared, nested `MultiIndex`** — the way the extended-census microdata
shares `ID_VIV` / `[ID_VIV, ID_PERSONA]`:

```python
viviendas = mxcensus.load_enoe_viviendas(period="2023t1")   # one row per dwelling
hogares   = mxcensus.load_enoe_hogares(period="2023t1")     # one row per household
viviendas["fac_tri"].sum()   # ≈ 37.3 M dwellings

# All three levels together, indices nesting dwelling ⊂ household ⊂ person
viv, hog, per = mxcensus.load_enoe_survey(period="2023t1")
# the person index carries the household levels as a prefix, so persons group by household:
household_size = per.groupby(level=list(hog.index.names)).size()   # persons per household
```

Each frame is indexed by its level's key (`viviendas` by the dwelling key, `hogares` by the
household key = dwelling key + `n_hog`, `h_mud`, `personas` by the person key = household key +
`n_ren`), so the indices are clean prefixes and the levels align/join naturally (the keys adapt
per era — pre-2020-T3 quarters have no `tipo`/`mes_cal`; 2026-T1 uses `cve_ent`). By default
`load_enoe_survey` returns **all** household members as `personas` (full `sdem`, so households
fully decompose); pass `persons="labor"` for the working-age labor-force analytical frame
instead (`is_pea`/… flags, but only interviewed 15+ members). All take an optional `ent=` state
filter.

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
mxcensus.enoe_schema_map()         # ENOE per-table schema groups (viv/hog/sdem/coe1/coe2)
mxcensus.variables_enoe("sdem", "g04")   # ENOE variables for a (table, schema group)
mxcensus.variables_enoe_core()     # ENOE analytical-core labels (clase1, pos_ocu, …)
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
- Labor-force survey — Encuesta Nacional de Ocupación y Empleo (ENOE):
  <https://www.inegi.org.mx/programas/enoe/15ymas/>

When you publish work that uses data obtained through `mxcensus`, INEGI's terms
require you to credit INEGI as the author of the data. Use the citation(s):

> **Fuente: INEGI, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Marco Geoestadístico, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Directorio Estadístico Nacional de Unidades Económicas (DENUE).**
>
> **Fuente: INEGI, Encuesta Nacional de Ocupación y Empleo (ENOE).**

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
- **ENOE** — the quarterly CSVs are converted to parquet as **faithful raw**: every column
  is kept as the text INEGI published, with no harmonization, imputation, or correction of
  values. The convenience loader `load_enoe_persons` **derives** an analysis frame from these
  raw tables (joining SDEM with the employment questionnaire, filtering to the canonical
  working-age universe, and adding a numeric `fac_tri` weight and `is_pea`/`is_ocupado`/
  `is_informal` flags), but leaves the underlying values untouched. One source-side encoding
  defect — a few mangled accented characters in two open-text SDEM fields
  (`cs_p21_des`/`cs_p23_des`) — is preserved as published, **not** corrected.

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