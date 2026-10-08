# INEGI censuses / Marco Geoestadístico / DENUE / ENOE / ENIGH — parquet mirror (mxcensus)

A pre-converted **parquet/geoparquet mirror of public [INEGI](https://www.inegi.org.mx)
open data**, hosted as the data backend for the
[`mxcensus`](https://github.com/CentroFuturoCiudades/mxcensus) Python package. Files are
fetched on demand by `mxcensus` (via Pooch) over plain HTTPS and verified against SHA-256
hashes shipped in the package. **This is an unofficial mirror — not produced, endorsed, or
maintained by INEGI.**

## Contents

| Family | Files | Source product |
|---|---|---|
| Census tabular (`iter_*`, `resargebub_*`, `personas_*`, `viviendas_*`) | 128 | Censo de Población y Vivienda 2020 (ITER, RESAGEBURB, Cuestionario Ampliado) |
| Censuses, conteos & intercensal surveys (`cpv_{table}_{year}_*`, 1990–2025: microdata `viviendas`/`hogares`/`personas`/`migrantes` and locality/AGEB aggregates `iter`/`ageb` per state, plus the national EIC 2025 `estimaciones`) | 897 | XI Censo General de Población y Vivienda 1990; Conteo de Población y Vivienda 1995; XII Censo General de Población y Vivienda 2000; II Conteo de Población y Vivienda 2005; Censos de Población y Vivienda 2010 and 2020; Encuestas Intercensales 2015 and 2025 (muestras/cuestionario ampliado, ITER, AGEB y manzana urbana, estimaciones) |
| Marco Geoestadístico 2020 (`mg_{layer}_{NN}`, 15 layers × 32 states + `ti` for 13 island states) | 493 | Marco Geoestadístico, Censo de Población y Vivienda 2020 (UPC 889463807469) |
| Marco Geoestadístico 2025 (`mg_{layer}_2025_{NN}`, same layers) | 493 | Marco Geoestadístico, Encuesta Intercensal 2025 (UPC 794551196649) |
| Marco Geoestadístico 2010 (`mg_{ent,mun,a,l,lpr}_2010_{NN}`) | 160 | Marco Geoestadístico 2010 v5.0 (UPC 702825292812) |
| Municipal Marcos Geoestadísticos 1995–2005 (`mg_{ent,mun}_{1995,2000,2005}_{NN}`, `mg_a_{2000,2005}_{NN}`) | 256 | Marco Geoestadístico municipal 1995, 2000 and 2005 v1.0 (UPC 702825292836, 702825292843, 702825292850) |
| DENUE economic units (`denue_{YYYYMM}_*`, 25 releases 2010–2026) | 800 | Directorio Estadístico Nacional de Unidades Económicas (DENUE) |
| ENOE labor-force survey (`enoe_{table}_{period}`, 85 quarters 2005–2026 × 5 tables) | 425 | Encuesta Nacional de Ocupación y Empleo (ENOE) |
| ENIGH income/expenditure survey (`enigh_{table}_{year}`, 9 editions 2008–2024 × 10–12 tables) | 99 | Encuesta Nacional de Ingresos y Gastos de los Hogares (ENIGH) |

Files are stored flat at the bucket root as `<name>.parquet`; the full naming scheme and
schema are documented in the package repository. **Total: 3751 files.**

## Source & attribution

All data originates from INEGI and is redistributed under the
**[Términos de Libre Uso de la Información del INEGI](https://www.inegi.org.mx/inegi/terminos.html)**,
which permit free use and redistribution with attribution and without implying INEGI's
endorsement. Please cite the original source:

> Fuente: INEGI. Censos Generales de Población y Vivienda 1990 and 2000; Conteos de
> Población y Vivienda 1995 and 2005; Censos de Población y Vivienda 2010 and 2020;
> Encuestas Intercensales 2015 and 2025; Marcos Geoestadísticos 1995, 2000, 2005, 2010,
> 2020 and 2025; Directorio
> Estadístico Nacional de Unidades Económicas (DENUE); Encuesta Nacional de Ocupación y
> Empleo (ENOE); Encuesta Nacional de Ingresos y Gastos de los Hogares (ENIGH).
> https://www.inegi.org.mx

## License

The underlying data is governed by INEGI's *Términos de Libre Uso de la Información del
INEGI* (linked above). The **transformations** in this mirror (CSV/shapefile → parquet
conversion, DENUE schema harmonization, geometry recovery against state boundaries, etc.)
are released by the `mxcensus` maintainers under the package's own license; see the
[repository](https://github.com/CentroFuturoCiudades/mxcensus). Users must comply with
INEGI's terms when using the data.

## Personal data & privacy

The census aggregates (ITER, RESAGEBURB, the `cpv_iter`/`cpv_ageb` files, the EIC 2025 estimaciones) and the Marco
Geoestadístico are **aggregate or geometric** and contain no personal data.

**DENUE** is a directory of economic units and may contain **personal data of natural
persons** — e.g. establishment names that are individuals' names (sole proprietors) and,
in some editions, contact fields (telephone, email, website). This data is **published
openly by INEGI** as a public statistical product; it is mirrored here unmodified. Users
are responsible for using it in compliance with applicable law, including Mexico's *Ley
Federal de Protección de Datos Personales en Posesión de los Particulares* (LFPDPPP), and
with the [Hugging Face Content Policy](https://huggingface.co/content-policy). To report a
concern or request removal, open an issue in the
[package repository](https://github.com/CentroFuturoCiudades/mxcensus/issues).

**ENOE**, **ENIGH**, the census **Cuestionario Ampliado** (`personas_*`/`viviendas_*`) and the
census, conteo and intercensal-survey samples 1990–2025 (`cpv_*`) are **de-identified public microdata** — individual person and household records with no direct identifiers (no
names, addresses, or contact details); geography is published only down to the AGEB level
(ENOE/ENIGH) or the municipality and locality (census samples). INEGI releases it openly as a public statistical
product; it is mirrored here unmodified.

## Transformations applied

This mirror is faithful to the source: values are not imputed or corrected. Processing
includes parquet conversion, DENUE longitudinal **harmonization** to a common schema,
point-geometry derivation with **state-boundary validation/recovery** (offending
coordinates corrected or nulled; raw lat/lon retained), and **reporting** (not removal) of
duplicate rows. Coordinates are parsed with a correctly-rounded float conversion so builds
are reproducible across machines. **ENOE**/**ENIGH**/**CPV** (`cpv_*`) parquet are faithful-raw
text (no harmonization or imputation); their per-table schema groups and reports are
documented alongside DENUE's. **Marco Geoestadístico** shapefiles are converted to GeoParquet
(single-part geometries promoted to Multi*, integer attributes to int32) keeping each
layer's source CRS: INEGI spells its one Lambert conformal conic projection two ways
(a custom `MEXICO_ITRF_2008_LCC` WKT and EPSG:6372), which `mxcensus.load_mg` normalises to
EPSG:6372 without moving any coordinate. Full details and per-file reports are in the
package repository (`docs/denue/`, `docs/enoe/`, `docs/enigh/`, `docs/cpv/`).

## How to use

```bash
pip install mxcensus
```
```python
import mxcensus as m
df_state, df_mun, df_loc, df_ageb = m.load_census(state=9)   # CDMX
denue = m.load_denue(state=9)                                # latest DENUE, harmonized
mg_aur, mg_loc_ageb = m.load_mg_census(state=9)
persons = m.load_enoe_persons(period="2023t1")              # ENOE labor-force person frame (national)
hog = m.load_enigh_hogares(period="2024")                    # ENIGH household summary (national)
viv, per, mig = m.load_cpv_survey(state=9)                   # Encuesta Intercensal 2025 microdata
viv, per, mig = m.load_cpv_survey(2020, state=9)             # Censo 2020 Cuestionario Ampliado
iter = m.load_cpv_iter(2000, state=9)                       # CGPV 2000 locality aggregates
mun = m.load_mg("mun", state=9, period=2025)                 # MG EIC 2025 municipalities
```
`mxcensus` downloads only the files it needs from this bucket and caches them locally.

## Citation

If you use this data, please cite **INEGI** (as above) and the package:

```bibtex
@software{mxcensus,
  title  = {mxcensus: loaders for INEGI census, survey and geostatistical open data},
  author = {Peraza, Gonzalo and {Centro para el Futuro de las Ciudades}},
  url    = {https://github.com/CentroFuturoCiudades/mxcensus}
}
```

## Disclaimer

Not affiliated with, produced by, or endorsed by INEGI. Provided "as is" for research use.
