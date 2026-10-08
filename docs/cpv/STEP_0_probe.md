# CPV Unit 0 — probe, catalog and groundwork

Probed live on **2026-10-07**. Every product listed in the catalog answered a HEAD with
`application/x-zip-compressed`; a deliberate miss (`MC2010_99_dbf.zip`) returned INEGI's
soft-404 (`HTTP 200`, `text/html`, 2263 bytes). Judge a download by its ZIP integrity
(`_build_common.fetch_zip_verified`), never by the status code.

## How the file lists were obtained

INEGI's (unofficial) file-listing API, the one the program pages use:

```
https://www.inegi.org.mx/app/api/descarga/componente/descargamasiva/lista/archivoscompaginacion
  ?tema=0&subtema=0&areaGeografica=0&proyecto=0&anio=0&tipodocto={4|12}&agrupacion=VG9kYXM=
  &idBiinegi={ID}&desde=1&hasta=1000&textoBuscar=&ordenar=orden&ingles=0&datosAbiertos=0&orden=
```

`tipodocto` 4 = microdatos, 5 = tabulados, 12 = datos abiertos. Each item's `pathLogico` +
a `formato` suffix (`_csv.zip`, `_dbf.zip`, `.xlsx`…) under `https://www.inegi.org.mx/contenidos`
is the URL. `idBiinegi`: EIC 2025 = 3455, EIC 2015 = 1714, CPV 2020 = 3001, CPV 2010 = 487,
Conteo 2005 = 3, CGPV 2000 = 2, Conteo 1995 = 343, CGPV 1990 = 781 (stored as
`CpvEdition.biinegi_id`). Content trees: `/contenidos/programas/{ccpv/<yr>|intercensal/2015|eic/2025}/`
(EIC 2025 is `eic/2025`, *not* `intercensal/2025`; EIC 2015 is `intercensal/2015`).

## Products per edition (state 01 shown; `{NN}` = 01–32)

| period | product | URL (under `/contenidos/programas/`) | data members (basename) |
|---|---|---|---|
| 2025 | microdatos | `eic/2025/microdatos/eic2025_micro_{NN}_csv.zip` (5.4 MB AGS, 70 MB MEX) | `viviendas01.csv`, `personas01.csv`, `migrantes01.csv` |
| 2025 | estimaciones | `eic/2025/datosabiertos/conjunto_de_datos_eic2025_105_csv.zip` (8.3 MB, national) | `conjunto_de_datos/conjunto_datos_eic2025_105.csv` (+ `diccionario_datos/…`, `metadatos/…`) |
| 2020 | microdatos | `ccpv/2020/microdatos/Censo2020_CA_{abbr}_csv.zip` | `Viviendas01.CSV`, `Personas01.CSV`, `Migrantes01.CSV` |
| 2020 | iter | `ccpv/2020/datosabiertos/iter/iter_{NN}_cpv2020_csv.zip` | `…/conjunto_de_datos/conjunto_de_datos_iter_01CSV20.csv` |
| 2020 | ageb | `ccpv/2020/datosabiertos/ageb_manzana/ageb_mza_urbana_{NN}_cpv2020_csv.zip` | `…/conjunto_de_datos_ageb_urbana_01_cpv2020.csv` |
| 2015 | microdatos | `intercensal/2015/microdatos/eic2015_{NN}_csv.zip` | `TR_VIVIENDA01.CSV`, `TR_PERSONA01.CSV` |
| 2010 | microdatos | `ccpv/2010/microdatos/mpv/MC2010_{NN}_dbf.zip` (no CSV) | `Viviendas_01.dbf`, `Personas_01.dbf`, `Migrantes_01.dbf` |
| 2010 | iter | `ccpv/2010/datosabiertos/iter_{NN}_2010_csv.zip` | `iter_01_cpv2010/conjunto_de_datos/iter_01_cpv2010.csv` |
| 2010 | ageb | `ccpv/2010/datosabiertos/ageb_y_manzana/resageburb_{NN}_2010_csv.zip` | `…/resultados_ageb_urbana_01_cpv2010.csv` |
| 2005 | microdatos | `ccpv/2005/microdatos/muestra/cpv2005_{NN}_dbf.zip` | `cpv2005_01_dbf/trvmue01.DBF`, `trhmue01.DBF`, `trpmue01.DBF` |
| 2005 | iter | `ccpv/2005/datosabiertos/cpv2005_iter_{NN}_csv.zip` | `cpv2005_iter_01/conjunto_de_datos/cpv2005_iter_01.csv` |
| 2000 | microdatos | `ccpv/2000/microdatos/muestra/cgpv2000_{NN}_dbf.zip` | `VHO_F01.DBF`, `PER_F01.DBF`, `MIN_F01.DBF` |
| 2000 | iter | `ccpv/2000/datosabiertos/cgpv2000_iter_{NN}_csv.zip` | `cgpv2000_iter_01/conjunto_de_datos/cgpv2000_iter_01.csv` |
| 1995 | microdatos | `ccpv/1995/microdatos/cpv95_{NN}_dbf.zip` | `datgen95.dbf`, `migint95.dbf` (no state code in the name) |
| 1995 | iter | `ccpv/1995/microdatos/iter/{NN}_{slug}_1995_iter_dbf.zip` | `ITER_01DBF95.dbf` |
| 1990 | microdatos | `ccpv/1990/microdatos/cgpv90p_{NN}_dbf.zip` | `m_1001.dbf` (one flat file) |
| 1990 | iter | `ccpv/1990/microdatos/iter/{NN}_{slug}_1990_iter_dbf.zip` | `ITER_01DBF90.dbf` |

`{slug}` is one table for 1990–2010 (`HIST_SLUG`: `distrito_federal`, `coahuila`, `michoacan`,
`veracruz`…), identical in every year — it differs from the MG slugs (`STATE_SLUG_MG`).
2010 also publishes DBF/XLS twins of ITER/AGEB (`microdatos/iter/…`); 2000/2005 ITER exist as
DBF/TXT/XLS too — the catalog uses the open-data CSV where one exists.

Not mirrored (out of scope or redundant): national microdata ZIPs (`_00_`, 762 MB CSV for 2025
— the per-state files are the same rows), dta/sas/sav twins, tabulados, the 2020
`ceu`/`cl`/`caas` products (entorno urbano, localidades, alojamientos), 2010 `resloc`/
`MANZANA_EU`, 2005 `vivloc`, electoral-geography estimates (`eceg_2010/2020`, `eiege_eic_2015`).

## Dictionaries (`DICTIONARY_URLS`)

| period | descriptor | catalogs | RNM DDI |
|---|---|---|---|
| 2025 | `microdatos/eic2025_micro_fd.xlsx` (sheets Índice, MODELO LÓGICO, VIVIENDAS, PERSONAS, MIGRANTES) | `microdatos/889463931966_csv.zip` | none (highest RNM id 1151 on 2026-10-07; re-check at unit 1b) |
| 2020 | `microdatos/diccionario_cuestionario_ampliado_cpv2020.xlsx` | `microdatos/Censo2020_clasificaciones_CPV_csv.zip` | not located — probe at 2a |
| 2015 | `doc/eic2015_fd.xls` (legacy BIFF8) | `doc/eic2015_catalogos.zip` (`TC_*.xls`; not in the listing API — found in unit 3a) | 214 (incomplete; unused, `STEP_3a.md`) |
| 2010 | `doc/diccionario_cuestionario_ampliado.xls` | `doc/catalogos_2010_dbf.zip` | 71 |
| 2005 | `doc/fd_muestra_2005.xls` | `doc/catalogos_muestra_2005.xls` | 140 |
| 2000 | `doc/fd_muestra_censal_2000_pdf.zip` | — | 141 |
| 1995 | `doc/fd_encuesta_cpv1995.pdf` | `doc/catalogos_cpv1995.pdf` | — |
| 1990 | `doc/fd_cgpv1990.pdf` | `doc/catalogos_1990.xls` | — |

The aggregate ZIPs (ITER/AGEB 2000–2020, estimaciones 2025) carry their own
`diccionario_datos/…csv` (`utils.get_vars_from_indicator_csv`). The 2025 estimaciones CSV is
**cp1252** (all other 2025 files UTF-8 without BOM).

## Microdata structure seen in the state-01 files (DBF headers read without extraction)

| period | file → table | rows (AGS) | keys | weight | DBF code-page byte |
|---|---|---|---|---|---|
| 2010 | `Viviendas_01` → viviendas | 16,572 | `ENT`, `ID_VIV` (C8) | `FACTOR` N8 | 0x00 |
| 2010 | `Personas_01` → personas | 69,804 | + `ID_PER` (C9) | `FACTOR` N8 (3b: the probe first missed it) | 0x03 |
| 2010 | `Migrantes_01` → migrantes | 1,268 | `ID_VIV`, `ID_MIN` (C7) | `FACTOR` | 0x00 |
| 2005 | `trvmue` / `trhmue` / `trpmue` | 24,562 / 25,217 / 106,171 | `ENT`,`MUN`,`CONS_MUN`,`CONS_VIV` (+`CONS_HOG`, +`CONS_PER`) | **none** | 0x02 (cp850) |
| 2000 | `VHO_F` (viv+hogar) / `PER_F` / `MIN_F` | 19,132 / 87,507 / 2,950 | `ENT`,`MUN`,`LOC`,`NUMVIV`,`NUMHOG` (+ person/migrant no. — find at 4a) | `FACTOR` C5 | 0x00 |
| 1995 | `datgen95` → hogares, `migint95` → migrantes | 11,098 / 439 | `ENT`,`ZONA`,`ESTRATO`,`TAM_LOC`,`MUN`,`UPM`,`VIV`,`HOGAR` | `FAC_POB`,`FAC_VIV`,`FAC_PROM` | 0x03 |
| 1990 | `m_1001` → personas (flat, dwelling items repeated) | 71,734 | `FOLIO_VIV`, `NUM_PER` | **none** | 0x00 |

Consequences for later units:
- **2010 `ID_VIV` is 8 chars — unique only within a state**; stacking states needs `CVE_ENT`
  in the dwelling key (decide the key spec in 1c so 2025/2020 and 2010 share it).
- DBF code pages vary (0x00 unknown, 0x02 cp850, 0x03 cp1252): decode per file and check accents
  in `NOM_*` columns (3b/4a/5b).
- Old ITER mnemonics differ (1990 `P_TOTAL`/`HOMBRES`, 1995 `POBTOTAL`/`POBTMAS`, 2010 lowercase
  `pobtot`) → `cpv_iter_crosswalk.yaml` (3c/4b/5a).

## Marco Geoestadístico editions (`_catalog.MG_EDITIONS`)

From INEGI's product API (`…/app/api/productos/interna_v2/ficha/datos?upc={UPC}&lang=false`):

| period | UPC | layout | download |
|---|---|---|---|
| 2025 | 794551196649 | per state, same slugs as 2020 | `…/geografia/marcogeo/794551196649/{NN}_{slug}.zip` (AGS 38 MB) |
| 2020 | 889463807469 | per state | `…/geografia/marcogeo/889463807469/{NN}_{slug}.zip` |
| 2010 | 702825292812 (v5.0) | **one national ZIP** | `…/geografia/marc_geo/702825292812_s.zip` (100 MB) |
| 2005 | 702825292850 (municipal) | national | `…/marc_geo/702825292850_s.zip` (66 MB) |
| 2000 | 702825292843 (municipal) | national | `…/marc_geo/702825292843_s.zip` (37 MB) |
| 1995 | 702825292836 (municipal) | national | `…/marc_geo/702825292836_s.zip` (37 MB) |

EIC 2015's frame is not identified (likely MG 2014 v6.2 — unit 3d). No frame for 1990.

**MG 2025 smoke conversion** (state 01, `build_marco_geo.py --period 2025` into scratch): the
same **15 layers** with identical attribute columns and geometry types as 2020; feature counts
grew (e.g. AGEB urbanas 479 → 519, manzanas 22,312 → 24,429). The projection is the same LCC
(`+proj=lcc +lat_0=12 +lon_0=-102 +lat_1=17.5 +lat_2=29.5 +x_0=2500000 +ellps=GRS80`), but
5 layers (`ar`, `ent`, `fm`, `lpr`, `mun`) ship the WKT named "Mexico ITRF2008 / LCC"
(EPSG:6372) instead of 2020's custom "MEXICO_ITRF_2008_LCC", so `crs ==` is False across years
although coordinates are directly comparable. Decide in unit 1d whether to normalise the CRS
object at build time (faithful-raw argues against) or document it.

## Groundwork changes (this unit)

- `scripts/build_data.py` — the legacy 2020 builder now upserts via
  `_build_common.update_registry` (the old `pooch.make_registry(output_dir)` would have dropped
  every registry entry not present locally — 373 ENOE entries on the Mac) and uses the shared
  `fetch_zip_verified`/`detect_encoding`; `--no-registry` added.
- `src/mxcensus/data/_catalog.py` — `MgEdition`, `MG_EDITIONS`, `marco_geo_zip_url(state, period="2020")`,
  `marco_geo_national_url(period)`, `mg_filename(suffix, state, period="2020")` (legacy names kept for 2020).
- `scripts/build_marco_geo.py` — `--period` (state-layout editions); period-qualified cache ZIP /
  raw dir / output names (2020 keeps its names so the existing cache stays valid); unexpected layer
  suffixes are reported.
- `scripts/_build_common.py` — `PRESERVE_PREFIXES += "cpv_"` (`mg_*_2025_*` is covered by `mg_`).
- `scripts/_dict_ddi.observed_values` — reads one column at a time and de-duplicates in Arrow;
  output verified identical to the old implementation on all 61 ENIGH groups and 27 ENOE groups.
- `src/mxcensus/_cli.py` — `SELECTOR_FLAGS` (flag → set of datasets), `NATIONAL_DATASETS`;
  `STATE` is optional for `enoe`/`enigh` and range-checked otherwise (closes review finding 7);
  `main(argv=None)` for testing.
- `src/mxcensus/data/_cpv_catalog.py` — the family catalog: `CpvEdition` (8 editions), `TABLES`,
  `PRODUCT_OF`, `HIST_SLUG`, `FILE_RE`/`cpv_filename`/`parse_filename`, `find_member`,
  `latest_edition(table)`, `cpv_zip_entry`, `DICTIONARY_URLS`/`dictionary_url`.
- Tests: `tests/test_cpv.py` (catalog, verified URLs, probed members, filenames, MG editions),
  `tests/test_cli.py`, `tests/test_census_legacy.py` (pins `load_census`/`load_extended_*` on
  state 01: POBTOT 1,425,607; personas Σ FACTOR 1,421,198; viviendas Σ FACTOR 387,762).

Full suite after unit 0: **628 passed** (14 min, local mirror present; the 4 warnings are
pre-existing DENUE/ENOE value-level ones).

## Environment note

`uv run` recreated `.venv` on CPython 3.13 with only base dependencies (the old venv's Homebrew
3.14 interpreter had been upgraded away). Restored with
`uv sync --python 3.14 --extra dev --extra notebook`; use `.venv/bin/python` directly.
