# ENIGH Unit 0 — download-URL probe + catalog

Probed live on 2026-08-27 with `curl -I` (INEGI soft-404s are HTTP 200 + `text/html`, 2263
bytes; a real file is `application/x-zip-compressed`). Filenames match case-insensitively on
INEGI's server.

## Layout

All editions live under one tree, `https://www.inegi.org.mx/contenidos/programas/enigh/nc/{year}/microdatos/`,
**one ZIP per (edition, table)**, each holding a single CSV.

### Nueva serie (`ns`) — 2016, 2018, 2020, 2022, 2024

`enigh{year}_ns_{table}_csv.zip` — **all 55 verified** (5 editions × 11 tables). Member is
`{table}.csv`. No dictionary inside the ZIP (INEGI's *Descripción de la base de datos* PDF per
edition is the dictionary; e.g. `889463910626.pdf` for 2022).

| table | 2016 | 2018 | 2020 | 2022 | 2024 (bytes) |
|---|---|---|---|---|---|
| concentradohogar | 10.3 M | 10.8 M | 12.1 M | 12.5 M | 13,171,058 |
| viviendas | 1.5 M | 1.6 M | 1.7 M | 1.7 M | 1,848,886 |
| hogares | 3.2 M | 3.0 M | 3.5 M | 3.6 M | 3,330,147 |
| poblacion | 9.2 M | 8.1 M | 10.0 M | 9.9 M | 9,055,376 |
| ingresos | 3.8 M | 3.7 M | 4.2 M | 4.4 M | 4,292,608 |
| gastoshogar | 38.6 M | 36.3 M | 41.1 M | 49.2 M | 54,393,736 |
| gastospersona | 2.2 M | 2.0 M | 1.6 M | 2.3 M | 2,090,789 |
| trabajos | 1.8 M | 1.7 M | 1.9 M | 2.1 M | 1,928,668 |
| agro | 431 k | 444 k | 565 k | 529 k | 513,315 |
| noagro | 1.1 M | 1.1 M | 1.4 M | 1.4 M | 1,347,538 |
| erogaciones | 509 k | 522 k | 746 k | 722 k | 749,406 |

### Nueva Construcción de Variables (`ncv`) — 2008, 2010, 2012, 2014

`NCV_{Stem}_{year}_concil_2010_csv.zip` (DBF twins `_dbf.zip` also exist). Verified stems:

| canonical | 2008 | 2010 | 2012 | 2014 |
|---|---|---|---|---|
| concentradohogar | Concentrado | Concentrado | Concentrado | Concentrado |
| viviendas | — | — | Viviendas | Vivi |
| hogares | Hogares | Hogares | Hogares | Hogares |
| poblacion | Poblacion | Poblacion | Poblacion | Poblacion |
| ingresos | Ingresos | Ingresos | Ingresos | Ingresos |
| gastoshogar | — | — | Gastohogar | Gastohogar |
| gastospersona | — | — | Gastopersona | Gastopersona |
| gastos (combined, NCV-only) | Gastos | Gastos | — | — |
| trabajos | Trabajos | Trabajos | Trabajos | Trabajos |
| agro | Agropecuario | Agropecuario | Agropecuario | Agropecuario |
| noagro | Noagropecuario | Noagropecuario | Noagropecuario | Noagropecuario |
| erogaciones | Erogaciones | Erogaciones | Erogaciones | Erogaciones |
| gastotarjetas (NCV-only) | Gastotarjetas | Gastotarjetas | Gastotarjetas | Gastotarjetas |

Tried and absent for 2008/2010: `Vivi`, `Viviendas`, `Vivienda`, `Gastohogar`, `Gastoshogar`,
`Gasto_hogar`, `Gastopersona`, `Gastospersona` (csv and dbf). Dwelling characteristics for
those years are carried in `Hogares`.

Member naming inside NCV ZIPs varies: `erogaciones.csv` / `gastotarjetas.csv` (2008/2010),
`ncv_gastotarjetas_2014_concil_2010.csv`, `NCV_viviendas_2012_concil_2010.csv` — every ZIP
holds exactly one CSV, so `find_member` matches either spelling and falls back to the sole
CSV. Column headers are lowercase (`folioviv,foliohog,clave,…`); `folioviv` is 6 chars in
2008 vs 10 in 2014+ (harmonization note).

Totals: 55 (`ns`) + 10+10+12+12 = **44** (`ncv`) → **99 files**.

## Catalog (`src/mxcensus/data/_enigh_catalog.py`)

`EnighEdition(period, year, regime)`, `EDITIONS` (2008…2024), `EDITIONS_BY_PERIOD`,
`latest_edition()` = 2024, `TABLES` = 11 canonical `ns` names + NCV-only `gastotarjetas`/
`gastos`, `edition.tables` (per-year set), `edition.zip_filename(table)` / `.url(table)`,
`ncv_stem`, `find_member`, `enigh_zip_entry(edition, table)` → `CatalogEntry`.

## Methodological breaks to document in the loader/README

- **2014 → 2016 (nueva serie)**: MCS merged into ENIGH; sample ~20 k → 81.5 k dwellings
  (105.5 k from 2020); state × urban/rural representativeness; revised income capture.
  INEGI published a statistical bridging model (MCS-ENIGH 2016 / ENIGH 2018) — we do not
  apply it; the NCV files are the pre-break data conciliated to the CPV-2010 frame.
- **2022 → 2024** (INEGI, *Nota técnica de la consulta pública*, 2025): housing items
  homologated to CPV 2020; new items (birthplace, afrodescendencia, early education,
  fertility for men); updated health-services and time-use questions; classifiers updated
  (lenguas indígenas 2018, SCIAN 2018, SINCO 2019); expenditure `clave` codes re-based on
  CCIF 2018. Comparability with 2016+ kept where a change would break it.
