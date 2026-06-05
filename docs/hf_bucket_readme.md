# Mexico Census 2020 / Marco Geoestadístico / DENUE — parquet mirror (mxcensus)

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
| Marco Geoestadístico (`mg_*`, 15 layers × 32 states) | 480 | Marco Geoestadístico, Censo de Población y Vivienda 2020 (UPC 889463807469) |
| DENUE economic units (`denue_{YYYYMM}_*`, 25 releases 2010–2026) | 800 | Directorio Estadístico Nacional de Unidades Económicas (DENUE) |

Files are stored flat at the bucket root as `<name>.parquet`; the full naming scheme and
schema are documented in the package repository.

## Source & attribution

All data originates from INEGI and is redistributed under the
**[Términos de Libre Uso de la Información del INEGI](https://www.inegi.org.mx/inegi/terminos.html)**,
which permit free use and redistribution with attribution and without implying INEGI's
endorsement. Please cite the original source:

> Fuente: INEGI. Censo de Población y Vivienda 2020; Marco Geoestadístico 2020; Directorio
> Estadístico Nacional de Unidades Económicas (DENUE). https://www.inegi.org.mx

## License

The underlying data is governed by INEGI's *Términos de Libre Uso de la Información del
INEGI* (linked above). The **transformations** in this mirror (CSV/shapefile → parquet
conversion, DENUE schema harmonization, geometry recovery against state boundaries, etc.)
are released by the `mxcensus` maintainers under the package's own license; see the
[repository](https://github.com/CentroFuturoCiudades/mxcensus). Users must comply with
INEGI's terms when using the data.

## Personal data & privacy

The census and Marco Geoestadístico data are **aggregate or geometric** and contain no
personal data.

**DENUE** is a directory of economic units and may contain **personal data of natural
persons** — e.g. establishment names that are individuals' names (sole proprietors) and,
in some editions, contact fields (telephone, email, website). This data is **published
openly by INEGI** as a public statistical product; it is mirrored here unmodified. Users
are responsible for using it in compliance with applicable law, including Mexico's *Ley
Federal de Protección de Datos Personales en Posesión de los Particulares* (LFPDPPP), and
with the [Hugging Face Content Policy](https://huggingface.co/content-policy). To report a
concern or request removal, open an issue in the
[package repository](https://github.com/CentroFuturoCiudades/mxcensus/issues).

## Transformations applied

This mirror is faithful to the source: values are not imputed or corrected. Processing
includes parquet conversion, DENUE longitudinal **harmonization** to a common schema,
point-geometry derivation with **state-boundary validation/recovery** (offending
coordinates corrected or nulled; raw lat/lon retained), and **reporting** (not removal) of
duplicate rows. Coordinates are parsed with a correctly-rounded float conversion so builds
are reproducible across machines. Full details and per-file reports are in the package
repository (`docs/denue/`).

## How to use

```bash
pip install mxcensus
```
```python
import mxcensus as m
df_state, df_mun, df_loc, df_ageb = m.load_census(state=9)   # CDMX
denue = m.load_denue(state=9)                                # latest DENUE, harmonized
mg_aur, mg_loc_ageb = m.load_mg_census(state=9)
```
`mxcensus` downloads only the files it needs from this bucket and caches them locally.

## Citation

If you use this data, please cite **INEGI** (as above) and the package:

```bibtex
@software{mxcensus,
  title  = {mxcensus: Mexico Census 2020 data loader and preprocessor},
  author = {Peraza, Gonzalo and {Centro para el Futuro de las Ciudades}},
  url    = {https://github.com/CentroFuturoCiudades/mxcensus}
}
```

## Disclaimer

Not affiliated with, produced by, or endorsed by INEGI. Provided "as is" for research use.
