# ENIGH Unit 1 — build script + metadata

`scripts/build_enigh.py` (copied from `build_enoe.py` and retargeted): one ZIP per (edition,
table) → `enigh_{table}_{year}.parquet`, faithful `dtype=str`, zstd. Differences from ENOE:

- `_build_edition` fetches **per table** (`enigh_zip_entry(edition, table)`), skips tables the
  catalog says are absent for the edition (`status="absent"`, not an error), and reports
  download failures per table (`malformed`) without aborting the sweep.
- Mirror filenames are parsed with `_FILE_RE = enigh_(?P<table>.+)_(?P<period>\d{4})` instead
  of `split("_")` (table names could carry underscores).
- Editions sort by `int(year)`.

## Full build (Mac, 2026-08-27)

99 files in ~15 min (INEGI ~1 MB/s); two 2014 expenditure ZIPs failed with transient SSL
errors on the first pass and succeeded on re-run. All CSVs decoded as clean `utf-8`.
Sizes: `gastoshogar_2024` 11.5 M rows is the largest; total ≈ 450 MB parquet.

## Schema groups (61 over 13 tables)

| table | groups | note |
|---|---|---|
| concentradohogar | 6 | 2008, 2010, 2012–2014, 2016, 2018–2022, 2024 (2024: 3 health items renamed) |
| viviendas | 5 | 2012, 2014, 2016, 2018–2022, 2024 (+18 cols: CPV-2020 homologation) |
| hogares | 7 | nearly every edition its own group |
| poblacion | 8 | 2016–2018 share; each other edition its own |
| ingresos | 2 | 2008–2020; 2022–2024 (+`est_dis`/`upm`/`factor`) |
| gastoshogar / gastospersona | 3 / 4 | 2012; 2016–2020; 2022(+design vars); 2024 |
| trabajos | 7 | |
| agro / noagro | 6 / 6 | |
| erogaciones | 2 | 2008–2010; 2012–2024 |
| gastotarjetas / gastos | 2 / 2 | NCV-only |

From 2022 INEGI added `est_dis`/`upm`/`factor` to every table (previously only in
`concentradohogar`/`viviendas`/`hogares`). The 2014→2016 break shows as new groups in every
table; the 2022→2024 update as new groups in 7 of 11 nueva-serie tables.

`--variables`: 61 per-group YAMLs (data-enumerated categories, threshold 64) overlaid with
`variables_enigh_core.yaml` (24 core variables; complete value-sets across all editions —
`educa_jefe` lists both padded and un-padded codes because 2012 is un-padded).
`--validate`: **0/99** failures. `--update-registry`: 1833 → 1932.
