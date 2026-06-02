# DENUE mirror — Step 2: full download + fingerprinting + inconsistency report

Status: **done** (2026-06-01)

## Goal
Download all 24 releases × 32 states, convert to GeoParquet, and produce
`INCONSISTENCY_REPORT.md` (schema drift, duplicates, malformed/missing, within-release
disagreements) + actual mirror size.

## Result
- **768 files mirrored, 0 missing, 0 malformed.** Total **~11 GB** GeoParquet (zstd),
  EPSG:4326 points. (Source ZIPs cached: 782.)
- **8 schema groups** (see report §2):

  | group | cols | releases |
  |---|---|---|
  | g01 | 24 | 2010 |
  | g02 | 30 | 2011 |
  | g03 | 47 | 2012 |
  | g04 | 28 | 2013-Jul |
  | g05 | 44 | 2013-Oct |
  | g06 | 41 | 2015 |
  | **g07** | 41 | 2016-01 → 2020-11 (10 releases, descriptive→mnemonic stable era) |
  | **g08** | 42 | 2021-05 → 2025-05 (adds `clee`; **harmonization target**) |

- **Duplicates (§4), genuine:** `201000/32 ≡ 201100/32` (Zacatecas unchanged 2010→2011);
  `201703/{19,20} ≡ 201711/{19,20}` (states unchanged Mar→Nov 2017). Verified genuine
  (distinct source filenames), not cache artifacts.
- **Within-release disagreements (§6), genuine — 6 releases:** some states ship a
  different schema than their peers in the same release:
  - 2011 state 32 → still the 24-col 2010 schema (30-col elsewhere).
  - **2015 states 11,21,22,23 → already the mnemonic schema** while 28 states have the
    old descriptive schema.
  - 2012 states 12,14 → typo'd headers (`Nombre de clase dela actividad`, trailing-space
    `Área geoestadística básica `).
  - 2018-03 state 15, 2022-11 states 19/20/26, 2024-05 state 11 → UPPERCASE headers.
  These are real INEGI inconsistencies; harmonization (Step 4) normalizes case + maps names.

## Bugs found and fixed during Step 2
These were caught by the smoke test and the full run, then fixed (all in
`scripts/build_denue.py` / `scripts/_build_common.py`):

1. **Flat ZIP layout (pre-2016):** 2010–2015 ship `DenueCSV{NN}.csv` at the root (PDF
   dictionary), not `conjunto_de_datos/`. `_locate_data_csv` now picks the largest
   non-dictionary CSV across layouts.
2. **Encoding mis-detection:** chardet guessed cp850/cp1250 → mojibake or `0x90`
   decode errors. Replaced with utf-8→cp1252 fallback (`_read_csv_robust`).
3. **lat/lon renamed/capitalized** (`Latitud`/`Longitud` in old releases): matched
   case-insensitively; absent → all-null geometry.
4. **Mixed str/float columns** (`numero_ext`): read **all columns as `dtype=str`**
   (DENUE fields are categorical text, not arithmetic) — faithful and eliminates the
   dtype drift that pyarrow can't serialize.
5. **Network flakiness:** `fetch_zip_verified` now retries on download exceptions
   (ConnectTimeout/IncompleteRead/Read-timeout), not just bad-ZIP.
6. **Cache-key collision (important):** 2013-Julio and 2013-Octubre both serve a file
   named `denue_{NN}_2013_csv.zip`; pooch's basename cache key made October silently
   reuse July's download → a *spurious* "byte-identical 2013 duplicate". Fixed by caching
   under a release-qualified name (`{folder}_{filename}`). Real Oct-2013 (g05, 44 cols)
   is now distinct from Jul-2013 (g04, 28 cols).
7. **Multipart casing artifact:** 2018-03 state 15's two parts had different header
   casing; naive `pd.concat` produced 82 half-empty columns. Parts are now aligned
   case-insensitively to the first part before concat (→ 41 cols).

## Design notes / decisions
- **Faithful raw mirror:** column names are kept as INEGI ships them (lowercase/UPPERCASE/
  descriptive/typo'd). All normalization (case, strip, rename) is deferred to the Step 4
  harmonization layer; the report documents the raw inconsistencies.
- **Report regenerates from disk** (`--report-only`), decoupled from any single run, so
  targeted recovery doesn't clobber it.
- **Disk hygiene:** extracted CSVs deleted after conversion (`--keep-raw` to retain).

## Open question for the maintainer
- The **2 genuine duplicate pairs** (and any future ones) are mirrored as-is for
  completeness but flagged. Decide whether to drop redundant copies before upload.
- Total upload ≈ 11 GB / 768 assets to the existing `data-v0.1.0` release (Step 5).

## Next — Step 3
Schema grouping → per-group `variables_denue_<gNN>.yaml` (seeded from the bundled
`denue_diccionario_de_datos.csv`, PDF for 2010) + per-group Pandera schemas +
`denue_schema_map.yaml` (release→group, fingerprints, latest=g08). Must account for the
within-release disagreements (group by per-state schema, not just a canonical state).
