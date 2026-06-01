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

## Variable dictionaries

INEGI's variable dictionaries are bundled with the package and exposed as plain
dicts keyed by variable mnemonic — no download required:

```python
mxcensus.variables_iter()          # ITER indicators (name, description, range)
mxcensus.variables_resargebub()    # RESARGEBUB indicators
mxcensus.variables_personas()      # person microdata variables + category labels
mxcensus.variables_viviendas()     # household microdata variables + category labels
```

The ITER and RESARGEBUB dictionaries are national (identical across states), so a
single copy of each is bundled. Note their schema differs from the microdata
dictionaries: aggregate indicators carry `Indicador` / `Descripción` / `Rangos` /
`Longitud` fields, while the microdata variables include categorical code→label
maps under `Categorías`.

## Data source and attribution

All census data originates from INEGI's open-data ("datos abiertos") release of
the Censo de Población y Vivienda 2020:

- Census program: <https://www.inegi.org.mx/programas/ccpv/2020/>

When you publish work that uses data obtained through `mxcensus`, INEGI's terms
require you to credit INEGI as the author of the data. Use the citation:

> **Fuente: INEGI, Censo de Población y Vivienda 2020.**

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

- **Format conversion** — the source CSVs are converted to parquet for the mirror.
- **Censored values** — INEGI's `*` suppression marker (meaning 0, 1, or 2
  persons) is mapped to masked integers, and zeros are imputed where parent-level
  totals confirm a suppressed value must be 0.
- **Missing data** — INEGI's `N/D` marker is converted to `NaN`.
- **Derived columns** — the extended microdata loaders add summary flags (e.g.
  health-insurance, disability, transport, income bins) computed from the raw
  fields.

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