# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies (add ,notebook for Jupyter/Quarto)
uv pip install -e ".[dev]"            # or: uv sync --extra dev --extra notebook

# Run tests (DENUE suite tests/test_denue.py ~93 tests; ENOE tests/test_enoe.py; ENIGH tests/test_enigh.py)
pytest
pytest tests/test_denue.py        # single file

# CLI — pre-download parquet files for a state, show cache info
mxcensus fetch 9                  # all 4 datasets for state 9
mxcensus fetch 9 --dataset iter   # one dataset: iter|resargebub|personas|viviendas|all
mxcensus info                     # resolved cache dir + mirror base URL
```

The project uses `uv` as the build tool. Python 3.13+ is required (`pyproject.toml`
declares `>=3.13`; the active venv runs 3.14).

## What this project does

`mxcensus` is a data loader and preprocessor for Mexico's 2020 Census (CPV 2020) published by INEGI. It fetches pre-converted parquet files from a curated mirror hosted in a Hugging Face Storage Bucket, parses them (handling censored values and missing data conventions), and returns clean pandas DataFrames ready for analysis.

Three dataset types are supported:

- **ITER** – Locality-level aggregate counts (state → municipality → locality hierarchy)
- **RESARGEBUB** – Urban block-level data (AGEB = urban statistical areas, MZA = city blocks)
- **Cuestionario Ampliado** – Extended microdata with individual person and household records

## Architecture

### Public API

The package re-exports its surface from `src/mxcensus/__init__.py`. The primary
entry point is **`load_census(state=N)`** in `aggregate.py`, which orchestrates
the full ITER + RESARGEBUB pipeline (fetch → parse → impute → merge → validate).
Extended microdata uses `load_extended_personas` / `load_extended_viviendas`.
Lower-level building blocks (`load_iter`, `load_resargebub`, `merge_*`,
`impute_*`, `add_derived_cols`, `sanity_checks`) are also exported for direct use.

### Data flow

```
Hugging Face Storage Bucket (raw parquet mirror)
  → Pooch fetches & caches locally (data/_registry.py)
  → parse & process (aggregate.py, or extended_personas.py / extended_viviendas.py)
  → validate via Pandera schemas (_yaml/ bundled files)
  → return multi-index DataFrames
```

### Module responsibilities

| File | Role |
|------|------|
| `aggregate.py` | `load_iter` / `load_resargebub` — split raw data into level-specific DataFrames, handle `*` censoring, imputation; `load_census(state=N)` — orchestrates the full pipeline; `merge_mg_census` / `mg_agebs_ur` — merge Marco Geoestadístico geometries with census; `load_mg_census(state=N)` — fetches the 4 MGN layers (`mg_a/l/lpr/ar`) and runs the geometry pipeline |
| `extended_personas.py` | Preprocesses person microdata; derives health insurance flags, disability indicators, transport modes; Pandera validation |
| `extended_viviendas.py` | Preprocesses household microdata; derives income bins, financing modes; Pandera validation |
| `denue.py` | `load_denue(state=N, release=…, harmonize=, dedupe=, dedupe_ids=)` — fetches a DENUE release/state geoparquet, optionally **harmonizes** it to the latest schema (g10) via per-group rename + `per_ocu`/`tipoUniEco`/`fecha_alta` canonicalization, then validates: raw frames against the tight per-group schema `_group_schema(gid)`, harmonized frames against `_latest_schema()`. `dedupe=True` (default) drops exact full-row duplicates; `dedupe_ids=True` (default) drops rows sharing an `id`/`clee` (collapses near-duplicates that differ only in coordinate precision/whitespace). Both clean only the loaded frame — the mirror stays faithful (duplicates are reported, not removed, by the build). Validation **warns** on value-level violations (it does not raise — `_validate`); an unknown schema raises. Multi-temporal economic-units directory (25 releases 2010–2026, all built + mirrored; the latest **2026-05** came from the undated `denue_{state}_csv.zip` on INEGI's tree). |
| `enoe.py` | `load_enoe(table=, period=…, harmonize=, ent=)` — fetches one raw ENOE table (`viv`/`hog`/`sdem`/`coe1`/`coe2`) for one quarter as a faithful `dtype=str` frame, resolves its **per-table** schema group by column fingerprint (`_group_of`, raises on unknown), and validates against the tight per-group Pandera schema `_group_schema(table, gid)` (value-level violations **warn**, don't raise — `_validate`); `harmonize=True` applies `_harmonize` (cross-era **analytical-core** canonicalization: lowercase names, `fac`/`est_d`/`t_loc`→`*_tri` + NA `*_men`, `ent`/`mun`/`loc`/`ageb`→zero-padded `cve_*` + derived `cvegeo` (= `cve_ent`+`cve_mun`, `999` for unspecified), NA `tipo`/`mes_cal` before 2020-T3; every non-core column kept verbatim; generic `_RENAME_CORE`, not per-group) and validates against `_latest_schema(table)` (`isin` on the FD-sourced core categories, numeric weights, width regex on the padded codes). `load_enoe_persons(period=…, ent=, canonical_filter=, harmonize=)` — the analytical person frame: SDEM left-joined with COE1/COE2 on the era-appropriate person key (`_person_key`, handling the `ent`→`cve_ent` rename + panel-era `tipo`/`mes_cal`/`ca` widening), filtered to the canonical universe `R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]`, with a numeric canonical `fac_tri` weight and `is_pea`/`is_ocupado`/`is_informal` flags. `load_enoe_viviendas(period=, ent=, harmonize=)` / `load_enoe_hogares(period=, ent=, harmonize=)` — analysis-ready dwelling/household frames (numeric weights via `_coalesce_fac_tri`; era-appropriate hierarchical `MultiIndex` via `_index_level`). `load_enoe_survey(period=, ent=, persons="all"|"labor", harmonize=)` — returns the plain tuple `(viviendas, hogares, personas)` with a **shared nested `MultiIndex`** (dwelling ⊂ household ⊂ person, as the extended census shares `ID_VIV`/`ID_PERSONA`); `persons="all"` (default) = full SDEM so households fully decompose, `persons="labor"` = the `load_enoe_persons` frame. The three level keys come from one source of truth — `_DWELLING_KEY_SPEC` ⊂ `_HOUSEHOLD_KEY_SPEC` ⊂ `_PERSON_KEY_SPEC`, resolved per era by `_level_key` (`_person_key` = the person spec). National (no per-state split); `ent` is a post-load row filter |
| `crosstabs.py` | Builds contingency tables from the constraint YAML specs |
| `utils.py` | `expand_cat_map` (expands `"1..5"` range keys into per-int label maps) and `get_cats_from_excel` (generates the `_yaml/` category files from INEGI Excel data dictionaries) |
| `_schema_groups.py` | Shared machinery for the multi-temporal families (DENUE/ENOE/ENIGH): `fingerprint` (sha256 of ordered column names — the single recipe the build scripts write into the `*_schema_map.yaml` and the loaders resolve against), `group_of` (fingerprint → gid, raises on unknown), `build_group_schema` (weights → numeric, `Categorías` → `isin`, optional per-family `column_rule` e.g. DENUE's coded-field regexes, else str), `validate_warn` (lazy validate + warn summary), and the hierarchical-key helpers `level_key`/`index_level`. Each family module keeps its private `_fingerprint`/`_group_of`/`_group_schema`/`_validate`/`_level_key`/`_index_level` as thin wrappers bound to its own accessors |
| `_resources.py` | Lazy, cached loader for the bundled YAML (`variables_*`, `constraints_*`, `denue_schema_map`, `variables_denue_<gNN>`, `enoe_schema_map`, `variables_enoe_<table>_<gNN>`, `variables_enoe_core`) |
| `_cli.py` | Two subcommands: `fetch` (pre-download a state; `--dataset denue --release` for DENUE; `--dataset enoe --period` for the five national ENOE tables — `state` positional is N/A/ignored) and `info` |
| `data/_registry.py` | Global `POOCH` instance; loads `registry.txt` at import time; no network traffic until `.fetch()` is called |
| `data/_paths.py` | Cache-dir resolution via `platformdirs`; respects `$MXCENSUS_CACHE_DIR` |
| `data/_catalog.py` | `STATE_ABBR`, `STATE_CODE_FMT`, INEGI census URL builders, and the `CatalogEntry` dataclass |
| `data/_denue_catalog.py` | `DenueRelease`, `RELEASES` (25 verified release URL templates incl. state-15 multipart & per-release quirks), `denue_zip_entry`, `latest_release` |
| `enigh.py` | `load_enigh(table=, period=…, harmonize=, ent=)` — one raw ENIGH table (13 canonical names; `gastotarjetas`/`gastos` are 2008–2014-only) for one edition year as a faithful `dtype=str` frame, per-table fingerprint group (`_group_of` raises on unknown) + tight `_group_schema(table, gid)` validation (warns). `harmonize=True` → `_harmonize`: lowercase, `factor_hog`/`factor_viv`→`factor` (all tables), the 2008/2010 `concentradohogar` spellings (`_RENAME_TABLE`: `ingcor`→`ing_cor`, `tam_hog`→`tot_integ`, `n_ocup`/`pering`/`perocu`→`ocupados`/`percep_ing`/`perc_ocupa`, head `sexo`/`edad`/`ed_formal`→`*_jefe` — table-scoped because `poblacion` has person-level `sexo`/`edad`), zero-padded `educa_jefe`, derived `cve_ent`/`cve_mun`/`cve_loc`/`cvegeo` from `ubica_geo` (9 chars 2012–2022, 5 chars 2008/2010/2024; `cve_ent` from `folioviv[:2]` when `ubica_geo` is absent); non-core columns verbatim; validated by `_latest_schema(table)`. Analysis-ready: `load_enigh_hogares` (= `concentradohogar`, numeric `factor`/`ing_cor`/…, household `MultiIndex`), `load_enigh_viviendas` (2012+), `load_enigh_personas` (`poblacion` + `factor` joined from `concentradohogar` via `_attach_factor` when the raw table has no weight), `load_enigh_survey` → `(viviendas, hogares, personas)` with the shared nested index (`_DWELLING_KEY_SPEC` ⊂ `_HOUSEHOLD_KEY_SPEC` ⊂ `_PERSON_KEY_SPEC` = `folioviv` ⊂ `+foliohog` ⊂ `+numren`, unique at each level in every edition). `ent` filters on `folioviv[:2]` |
| `data/_enoe_catalog.py` | ENOE bulk-download catalog: `EnoeQuarter`, `QUARTERS` (85 quarters 2005-T1…2026-T2, 2020-T2 ETOE gap excluded), `QUARTERS_BY_PERIOD`, `latest_quarter`, `TABLES`, three filename regimes (`enoe_old`/`enoen`/`enoe_new`) + `find_member`. National (one ZIP per quarter, five tables) |
| `scripts/_build_common.py` | **Maintainer-only** — shared build helpers: `fetch_zip_verified` (download+verify+retry), `detect_encoding`, `update_registry` (append/upsert preserving prior entries) |
| `scripts/build_data.py` | **Maintainer-only** — downloads raw census ZIPs from INEGI, converts CSVs to parquet, regenerates `registry.txt` |
| `scripts/build_marco_geo.py` | **Maintainer-only** — downloads INEGI's Marco Geoestadístico 2020 per-state shapefile ZIPs (UPC 889463807469, via `marco_geo_zip_url`) and converts the 15 layers/state to geoparquet (`mg_{suffix}_{NN}.parquet`, single→Multi* geometry, int32 codes, source `.prj` CRS); appends to `registry.txt`. `--local-gpkg-dir DIR` uses a local gpkg copy instead of downloading |
| `scripts/build_denue.py` | **Maintainer-only** — downloads/converts DENUE to geoparquet (`denue_{YYYYMM}_{NN}.parquet`), detects inconsistencies (`docs/denue/INCONSISTENCY_REPORT.md`), extracts data dictionaries (CSV 2016+ / PDF 2010–2013 via `pypdf`) to fill `variables_denue_*.yaml` descriptions + categories (categories cross-validated against the data → `docs/denue/CATEGORY_AUDIT.md`), generates `denue_schema_map.yaml`, validates every file against its group schema (`docs/denue/VALIDATION_REPORT.md`), derives/repairs point geometry against state boundaries (`docs/denue/GEOMETRY_REPORT.md`), appends to `registry.txt`. Modes: `--schema-map`, `--variables` (`--cat-threshold`), `--validate`, `--refilter-boundaries` (`--boundary-buffer-m`/`--boundaries-dir`/`--geometry-report`), `--report-only`, `--update-registry`, `--dry-run` |
| `data/_enigh_catalog.py` | ENIGH bulk-download catalog: `EnighEdition`, `EDITIONS` (2008–2024 biennial), `EDITIONS_BY_PERIOD`, `latest_edition`, `TABLES`/`NS_TABLES`, two regimes under one tree (`ns` `enigh{year}_ns_{table}_csv.zip`; `ncv` `NCV_{Stem}_{year}_concil_2010_csv.zip` with per-year stems via `ncv_stem`), `edition.tables` (per-year set), `find_member` (sole-CSV fallback), `enigh_zip_entry(edition, table)` — one ZIP per (edition, table) |
| `scripts/build_enoe.py` | **Maintainer-only** — downloads each ENOE quarter's CSV ZIP from INEGI and converts the five tables to faithful-raw parquet (`enoe_{table}_{period}.parquet`, every column `dtype=str`, no geometry). Fingerprints each file into a **per-table** schema group (`enoe_schema_map.yaml`), extracts per-group variable dictionaries (`variables_enoe_{table}_{gNN}.yaml`; categories data-derived, overlaid with the hand-curated `variables_enoe_core.yaml`), validates each file against its group schema, and appends to `registry.txt`. Modes: (build) `--periods`/`--tables`/`--dry-run`/`--keep-raw`, then `--schema-map`, `--variables` (`--cat-threshold`), `--report-only` (`docs/enoe/INCONSISTENCY_REPORT.md`), `--validate` (`docs/enoe/VALIDATION_REPORT.md`), `--update-registry`. See `docs/enoe/HANDOFF.md` + `STEP_*.md` |
| `scripts/build_enigh.py` | **Maintainer-only** — downloads each ENIGH (edition, table) CSV ZIP and converts it to faithful-raw parquet (`enigh_{table}_{year}.parquet`). Same mode set as `build_enoe.py` (`--periods`/`--tables`/`--dry-run`, `--schema-map`, `--variables`, `--report-only`, `--validate`, `--update-registry`); per-table schema groups in `enigh_schema_map.yaml`, per-group `variables_enigh_{table}_{gNN}.yaml` overlaid with the hand-curated `variables_enigh_core.yaml`; reports in `docs/enigh/`. Filenames are parsed with `_FILE_RE` (not `split("_")`). See `docs/enigh/HANDOFF.md` |
| `scripts/upload_hf.py` | **Maintainer-only** — host the parquet mirror in the Hugging Face Storage Bucket (`mxcensus.data._registry.HF_BUCKET`), the package's **current** data source. Subcommands: `create` (make the bucket), `upload` (`hf buckets sync` of `data/parquet/*.parquet` to the bucket root + the provenance `docs/hf_bucket_readme.md` as `README.md`; `--delete`/`--dry-run`), `verify` (HEAD each `…/resolve/<file>` URL vs local size, no download). Buckets are mutable (overwrite-in-place), so re-uploading after a rebuild just syncs changed files |
| `scripts/upload_release.py` | **Maintainer-only** (legacy GitHub-Release alternative; superseded by `upload_hf.py`) — resumable batch upload of the parquet mirror to a GitHub Release. Source of truth for "already uploaded" is the release itself (queried live via `gh release view`), so it survives multi-day / partial uploads. Batches derived from `registry.txt`: `core_denue` (latest DENUE), `core_census` (iter/resargebub/personas/viviendas), `core_mg` (the 4 MG layers `load_mg_census` fetches), `mg-rest` (other 11 MG layers), one `denue-<id>` per older release. Subcommands: `status` (`--write-doc`), `list <batch>`, `create-release`, `verify <batch…>` (compares each asset's GitHub SHA-256 digest + size to `registry.txt` via `gh api`, no download), `upload <batch…>` or `--next` (`--clobber`/`--chunk N`/`--dry-run`; auto-creates the release if missing) |

### YAML schemas (`_yaml/`)

- `variables_personas.yaml` / `variables_viviendas.yaml` – microdata variable names, descriptions, and value→label category mappings (generated by `utils.get_cats_from_excel` from INEGI's Excel dictionaries)
- `variables_iter.yaml` / `variables_resargebub.yaml` – aggregate-dataset indicator dictionaries: `Indicador`/`Descripción`/`Rangos`/`Longitud` per mnemonic, no category maps (generated by `utils.get_vars_from_indicator_csv` from the `diccionario_datos_*.csv` inside the INEGI ZIPs; national, one copy per dataset)
- `constraints_personas.yaml` / `constraints_viviendas.yaml` – valid variable combinations for crosstab generation
- `denue_schema_map.yaml` – DENUE column-fingerprint → schema group (g01..g11), group→columns, and `latest` (harmonization target); `variables_denue_<gNN>.yaml` – per-group DENUE variable dictionaries (`Descripción`/`Tipo`/`Longitud` from the release dictionaries; `Categorías` code→label maps for coded fields + data-enumerated categoricals — drives `_group_schema`; generated by `scripts/build_denue.py`)
- `enoe_schema_map.yaml` – **per-table** ENOE column-fingerprint → schema group map (one section per table `viv`/`hog`/`sdem`/`coe1`/`coe2`, each with `fingerprints`, `groups` gNN→columns, and `latest`); `variables_enoe_<table>_<gNN>.yaml` – per-(table, group) variable dictionaries (`Categorías` data-enumerated + core overlay — drives `_group_schema(table, gid)`; generated by `scripts/build_enoe.py`); `variables_enoe_core.yaml` – **hand-curated** analytical-core dictionary (FD-sourced labelled categories for `clase1`/`clase2`/`pos_ocu`/… — overlaid by `--variables`, **never** regenerated)
- `enigh_schema_map.yaml` / `variables_enigh_<table>_<gNN>.yaml` / `variables_enigh_core.yaml` – the same trio for ENIGH (13 tables; core = keys, `factor`, `ubica_geo`, `tam_loc`/`est_socio`, `clase_hog`, head variables, `ing_cor`/`ingtrab`/`gasto_mon`, `sexo`/`edad`/`parentesco`; `educa_jefe` lists both padded and un-padded codes because 2012 is un-padded)

`_resources.py` loads these once via `@functools.cache` and exposes them as `variables_*()` / `constraints_*()` / `variables_denue(gid)` / `denue_schema_map()` / `variables_enoe(table, gid)` / `enoe_schema_map()` / `variables_enoe_core()` / `variables_enigh(table, gid)` / `enigh_schema_map()` / `variables_enigh_core()`.

### Census data hierarchy

ITER and RESARGEBUB data follow: State → Municipality → Locality → AGEB → Block (MZA). Each level uses a different row in the raw file; `load_iter()` and `load_resargebub()` accept `.parquet` or `.csv` paths and split rows into level-specific DataFrames with appropriate multi-indices.

### Censored values

INEGI encodes suppressed counts as `*` (meaning 0, 1, or 2 persons). The parquet mirror preserves these as string values in object-dtype columns. `aggregate.py` maps them to masked `Int64` values and imputes zeros where parent-level totals confirm the suppressed value must be 0.

### Extended microdata preprocessing

Multi-response fields (health insurance categories, transport modes) are expanded into binary dummy columns then reduced to summary flags. The full preprocessing pipeline always runs at load time (no separate caching step). All output is validated with Pandera `DataFrameModel` schemas.

### Parquet mirror and registry

Raw INEGI data is pre-converted to parquet and hosted in a **Hugging Face Storage Bucket** (`HF_BUCKET` in `data/_registry.py`, default `gperaza/mxcensus`). Public bucket objects are served anonymously over plain HTTPS at `https://huggingface.co/buckets/<bucket>/resolve/<filename>` (a 302 to the Xet CDN), so Pooch fetches them as `base_url + filename` — no auth, no `hf://` client. `$MXCENSUS_BASE_URL` overrides the base URL (e.g. to a fork or a GitHub-Release mirror). The registry file (`src/mxcensus/data/registry.txt`) maps filenames to SHA256 hashes and is committed after each data build; Pooch verifies every download against it. Upload via `scripts/upload_hf.py upload`.

The bucket is live and holds the full mirror (all registry entries; see the totals below), so `POOCH.fetch` / `load_*(state=…)` resolve anonymously. After a rebuild, re-sync changed files with `python scripts/upload_hf.py upload`; until a newly built file is uploaded, fetching it 404s.

File naming convention:
```
# Census tabular data (128 files) — scripts/build_data.py
iter_{NN}.parquet          # raw ITER for state NN
resargebub_{NN}.parquet    # raw RESARGEBUB for state NN
personas_{NN}.parquet      # raw Personas for state NN
viviendas_{NN}.parquet     # raw Viviendas for state NN

# Marco Geoestadístico geometries (15 layers × 32 states = 480 geoparquet) — scripts/build_marco_geo.py
mg_{suffix}_{NN}.parquet   # suffix ∈ {a,ar,cd,e,ent,fm,l,lpr,m,mun,pe,pem,sia,sil,sip}

# DENUE economic units (25 releases × 32 states = 800 geoparquet, points) — scripts/build_denue.py
denue_{YYYYMM}_{NN}.parquet   # YYYYMM = release id (e.g. 202505); EPSG:4326

# ENOE labor-force survey (85 quarters × 5 tables = 425 parquet, national, no geometry) — scripts/build_enoe.py
enoe_{table}_{period}.parquet   # table ∈ {viv,hog,sdem,coe1,coe2}; period = {year}t{quarter} (e.g. 2023t1)

# ENIGH income/expenditure survey (9 editions × 10–12 tables = 99 parquet, national) — scripts/build_enigh.py
enigh_{table}_{year}.parquet    # table ∈ concentradohogar,viviendas,hogares,poblacion,ingresos,gastoshogar,gastospersona,trabajos,agro,noagro,erogaciones[,gastotarjetas,gastos]; year ∈ 2008…2024 biennial
```
Registry totals: 128 census + 480 geo + 800 DENUE + 425 ENOE + 99 ENIGH = **1932** entries.

To rebuild the **census** mirror after an INEGI data update:
```bash
python scripts/build_data.py --states 9   # smoke test one state first
python scripts/build_data.py              # full build
# Then upload data/parquet/ to the GitHub Release and commit registry.txt
```

To (re)build the **Marco Geoestadístico** geoparquet (downloads from INEGI):
```bash
python scripts/build_marco_geo.py --states 1   # smoke test (downloads 01_aguascalientes.zip)
python scripts/build_marco_geo.py              # all 32 states, all 15 layers
python scripts/build_marco_geo.py --local-gpkg-dir DIR   # use a local gpkg copy instead
# Appends mg_* entries to registry.txt (preserving census entries); then
# python scripts/upload_release.py upload core_mg --clobber   # then mg-rest
```

To (re)build the **DENUE** mirror (downloads from INEGI):
```bash
python scripts/build_denue.py --dry-run --release 202505 --states 9   # smoke test
python scripts/build_denue.py                       # all 25 releases × 32 states (~11 GB)
python scripts/build_denue.py --schema-map          # regenerate denue_schema_map.yaml
python scripts/build_denue.py --variables           # regenerate variables_denue_<gNN>.yaml (+ CATEGORY_AUDIT.md)
python scripts/build_denue.py --validate            # validate all files vs group schemas → VALIDATION_REPORT.md
python scripts/build_denue.py --refilter-boundaries # re-derive geometry vs state boundaries (recover/null) → GEOMETRY_REPORT.md
python scripts/build_denue.py --report-only         # regenerate INCONSISTENCY_REPORT.md
python scripts/build_denue.py --update-registry     # append denue_* hashes to registry.txt
# then: gh release upload data-v0.1.0 data/parquet/denue_*.parquet --clobber
```

`--refilter-boundaries` rewrites the parquet in place (no re-download) — afterward
regenerate hashes (`--update-registry`) and re-upload the changed files. Requires the
Marco Geoestadístico `mg_ent_*.parquet` boundaries to exist first (default in `--output`,
override with `--boundaries-dir`).

To (re)build the **ENOE** mirror (downloads from INEGI; national, no geometry). The full
build + upload procedure is in `docs/enoe/HANDOFF.md`; order matters (metadata is derived
from the built parquet):
```bash
python scripts/build_enoe.py --dry-run --periods 2023t1   # smoke test (prints URLs/members)
python scripts/build_enoe.py --periods 2023t1             # one quarter (5 tables)
python scripts/build_enoe.py                              # all 85 quarters × 5 tables (~2.5 GB); resumable
python scripts/build_enoe.py --schema-map                 # regenerate enoe_schema_map.yaml
python scripts/build_enoe.py --variables                  # regenerate variables_enoe_<table>_<gNN>.yaml (core overlay)
python scripts/build_enoe.py --report-only                # regenerate INCONSISTENCY_REPORT.md
python scripts/build_enoe.py --validate                   # validate all files vs group schemas → VALIDATION_REPORT.md
python scripts/build_enoe.py --update-registry            # append enoe_* hashes to registry.txt
# then upload with scripts/upload_hf.py upload (syncs data/parquet/*.parquet to the HF bucket)
```

### DENUE (multi-temporal economic units)

DENUE drifts across its 25 releases (2010–2026): schemas change, files can be malformed
or byte-duplicates, and `per_ocu` is encoded 4 different ways. `build_denue.py` detects and
reports all of this (`docs/denue/INCONSISTENCY_REPORT.md`); the implementation history is in
`docs/denue/STEP_*.md`. Every file is fingerprinted into one of **11 schema groups**
(`denue_schema_map.yaml`, `latest`=`g10`); `load_denue(..., harmonize=True)` maps any group
onto the latest 42-column schema (rename + `per_ocu`/`tipoUniEco`/`fecha_alta`
canonicalization) so releases are longitudinally comparable. `harmonize=False` returns the
raw schema. Source URL quirks (state-15 multipart from 2018, the 2013-Jul/Oct shared
filename, state-18 2015 date) live in `data/_denue_catalog.py`; the cache key is
release-qualified to avoid collisions.

**Validation.** Each group has a *tight* Pandera schema `_group_schema(gid)` built from its
`variables_denue_<gid>.yaml`: columns with a `Categorías` map get an `isin` check (categories
are sourced from the release dictionary and cross-validated against the data at build time),
coded columns (`codigo_act`/`cod_postal`/`cve_*`, by mnemonic via `_mnemonic_of`) get regex,
lat/lon a numeric check, `fecha_alta` a `YYYY-MM` date check. `load_denue` validates raw
frames against `_group_schema(gid)` and harmonized frames against `_latest_schema()`
("tight where safe" — `isin` on the canonicalized `per_ocu`/`tipoUniEco`, type checks
elsewhere; free-text categoricals stay `str` to avoid cross-era spelling false-fails).
Value-level violations **warn** (via `_validate`), they don't raise; the maintainer
`--validate` sweep (`docs/denue/VALIDATION_REPORT.md`) is the hard per-file report — it
surfaced ~50 files with corrupt `cod_postal` (address text, letter-O-for-zero, `0.00`).

**Build vs source defects.** The sweep distinguishes our bugs from INEGI's. The encoding
heuristic `_sniff_encoding` (in `build_denue.py`) picks utf-8 / utf-8+replace / cp1252 /
latin-1 by comparing U+FFFD count to the high-byte count — a UTF-8 file with a few bad
bytes is read utf-8-with-replace, **not** downgraded to cp1252 (the old bug that mojibake'd
~104k cells of `denue_201811_29`, since fixed and re-converted). The remaining `cod_postal`
garbage and sparse per-cell mojibake are **verbatim in INEGI's source CSVs** — left intact
(the mirror is faithful) and only flagged by the reports, never rewritten/imputed.
**Geometry derivation & repair.** `_df_to_geoparquet` derives the EPSG:4326 point from the
raw latitud/longitud and validates each point against its **own state's `mg_ent` polygon**
(buffered 500 m, in the boundary's native metric CRS). Offending coordinates are
**recovered** by `_recover_geometry`: a small ordered set of deterministic transforms
(`swap`, `neg_lon`, `neg_lat`, `neg_both`, `swap_neg_*`) is tried and the first whose point
lands back **inside the assigned state** wins — strong evidence the raw value was a mangled
form (this subsumes the old national-bbox transposed-coord recovery, e.g. `denue_201200_14`,
all 307k rows → `swap`). Points that no transform places in-state get **null** geometry
(scattered out-of-state geocoding errors — ~62 across the latest release). The raw
latitud/longitud columns are **kept verbatim**; only the derived geometry is corrected or
nulled. Every fix and every null is itemized in `docs/denue/GEOMETRY_REPORT.md` (which also
reports per-file **duplicate rows** / duplicate `id`/`clee` — reported, never removed); a
file with >5% out-of-state points is flagged there for manual review. Requires the `mg_ent_*`
layers to be built first (`scripts/build_marco_geo.py`).

Coordinates are parsed with `_parse_coords` (CPython's correctly-rounded `float()`), **not**
numpy/pandas fast parsers: INEGI's full-precision lat/lon strings sit on double midpoints
where fast parsers can round 1 ULP differently across library versions *and CPU
architectures*, which would make the derived geometry — and the parquet hashes in
`registry.txt` — non-reproducible across build machines. `float()` is deterministic
everywhere, so a build on any architecture yields identical geometry/hashes.

The harmonization spec (`_RENAME`, `_PER_OCU`, `_TIPO_UNI`) is hard-coded in `denue.py`,
**pinned to `g10`'s mnemonic column names** — `_latest_schema`/`_group_schema` read columns
dynamically from the map, but the rename/value targets do not. If a future release introduces
a new majority schema that becomes `latest`, revisit those dicts. Note `tipoUniEco` for
2012–2013 (g03–g06) comes from `Tipo de establecimiento` (codes 1/2/3; code 3 = the
in-dwelling fixed type → `Actividad en vivienda`), **not** the unrelated `Tipo de unidad
económica` (S/U/M) the general rename would pick. The report's §7 lists each group's all-null
columns (e.g. g04's empty `entidad`/`municipio` names in 2012 states 12/14 — faithful to
source, codes-only); an all-null column is data quality, whereas a *stale* rename map emits a
`warnings.warn` at load time.

To (re)build the **ENIGH** mirror (downloads from INEGI; national; ~500 MB, minutes):
```bash
python scripts/build_enigh.py --dry-run --periods 2022        # smoke test (prints URLs)
python scripts/build_enigh.py                                 # all 9 editions (99 files); resumable
python scripts/build_enigh.py --schema-map / --variables / --report-only / --validate / --update-registry
```
Same ordering rules as ENOE (delete stale `variables_enigh_*_g*.yaml` first; never regenerate
`variables_enigh_core.yaml`); runbook in `docs/enigh/HANDOFF.md`.

### ENIGH (biennial household income/expenditure survey)

Fifth data family, built on the ENOE machinery. Two regimes under one INEGI tree
(`data/_enigh_catalog.py`): the **nueva serie** (2016–2024, 11 tables) and INEGI's conciliated
**Nueva Construcción de Variables** (2008–2014; 10–12 tables, per-year filename stems, no
dwelling table and a combined `gastos` table in 2008/2010). One ZIP per (edition, table),
single CSV member, no bundled dictionary. **2014 → 2016 is a methodological break** (MCS
merger, sample redesign, income capture) and **2024 updated the questionnaires/classifiers**
(CCIF-2018 expenditure codes) — both surface as schema groups (`enigh_schema_map.yaml`, 61
groups over 13 tables; `docs/enigh/INCONSISTENCY_REPORT.md` lists the column drift) and are
documented, not modelled: `harmonize=True` is **core-only** (see the `enigh.py` row) and the
expenditure `clave` catalogs are not bridged. Keys `folioviv` ⊂ `foliohog` ⊂ `numren` are
unique per level in every edition; `folioviv[:2]` is the state code. Weights: `factor`
(`factor_hog`/`factor_viv` in 2012–2014) live in `concentradohogar`/`viviendas` and, from 2022,
in every table; the analysis-ready loaders join `factor` from `concentradohogar` otherwise.
Published checks: Σ `factor` = 31,671,002 (2014), 37,560,123 (2022), 38,830,230 (2024)
households; 2024 mean quarterly `ing_cor` ≈ $77,864. `--validate` → 0/99 failures.

### ENOE (multi-temporal labor-force survey)

ENOE is INEGI's quarterly labor-force survey — the fourth data family, modelled on the DENUE
machinery (per-period, faithful-raw `dtype=str` parquet + fingerprint schema-groups +
warn-not-raise validation → HF-bucket mirror → release-qualified loader) **minus geometry**.
Unlike census/DENUE it is **national** (one file set per quarter, no per-state split), with
**five tables** per quarter (`viv`/`hog`/`sdem`/`coe1`/`coe2`) across **85 quarters**
2005-T1…2026-T2 (2020-T2 is the ETOE COVID gap, excluded — see `data/_enoe_catalog.py`).

It drifts across eras — three ZIP-filename regimes (`enoe_old`/`enoen`/`enoe_new`), the
`FAC`→`FAC_TRI` weight rename (2020-T3), the `ENOEN`→`ENOE` member rename (2023), and the
`ent`→`cve_ent` geographic-key rename (2025-T3) — plus the COE ampliado/básico alternation
that changes the COE1/COE2 column sets by quarter. This is captured empirically: every file
is fingerprinted into a **per-table** schema group (`enoe_schema_map.yaml`), and
`load_enoe(table=, period=)` validates it against `_group_schema(table, gid)` (value-level
violations **warn**). Cross-era **harmonization** (`harmonize=True` on every loader) is
deliberately narrower than DENUE's: it canonicalizes only the **analytical core** — casing,
`fac`/`est_d`/`t_loc`→`*_tri` (+ NA `*_men`), `ent`/`mun`→zero-padded `cve_ent`/`cve_mun` +
derived `cvegeo`, `loc`/`ageb`→`cve_loc`/`cve_ageb`, NA `tipo`/`mes_cal` before 2020-T3 — and
keeps every other column verbatim, because the COE **ampliado** (Q1) and **básico** (Q2–Q4)
questionnaires have disjoint item sets (projecting onto the latest group's columns, as DENUE
does, would drop every básico-only item) and SDEM renumbered items in 2025-T3. The maps
(`_RENAME_CORE`, `_GEO_PAD`, `_CORE_ADD`) are generic, not per-group, so a new fingerprint
harmonizes without a map edit; a frame that already has both a legacy column and its target
raises, and a missing core source warns (`_RENAME_CORE may be stale`). Harmonized frames are
validated against `_latest_schema(table)`. Weighted totals (`load_enoe_persons`) are
identical with and without harmonization on both sides of every rename boundary
(tested: 2020-T1→T3, 2021-T2→T3, 2025-T2→T3).

`load_enoe_persons(period=)` builds the analytical person frame — SDEM left-joined with
COE1/COE2 on the era-appropriate person key (`_person_key`: base seven `cd_a`/`ent`/`con`/
`v_sel`/`n_hog`/`h_mud`/`n_ren`, widened by `tipo`/`mes_cal` from 2020-T3 and `ca` for
2020-T3…2021-T2, since the base seven are **not** unique in the panel/CATI era), filtered to
the canonical universe `R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]` (padding-robust — the CSV emits
un-padded codes, e.g. `r_def='0'`), with a numeric canonical `fac_tri` weight coalescing
`fac_tri`/`fac`, and `is_pea`/`is_ocupado`/`is_informal` flags. A **fan-out guard** warns if
the person key isn't unique in SDEM (e.g. an unhandled future key rename) rather than silently
inflating weighted totals. Faithful-raw policy applies: some SDEM files carry an unrecoverable
INEGI encoding defect (bytes `0xCB`/`0xD0`) in the open-text `cs_p21_des`/`cs_p23_des` fields
only — preserved losslessly (value-level, never fails schema validation), not a build bug
(`docs/enoe/STEP_2.md`).

The household survey nests **dwelling ⊂ household ⊂ person**, and the three natural keys are
clean prefixes (dwelling `cd_a`/`ent`/`con`/`v_sel`[`+tipo`/`mes_cal`/`ca`] ⊂ household `+n_hog`/
`h_mud` ⊂ person `+n_ren`) — verified unique at each level for both a modern and a 2005 quarter.
`load_enoe_viviendas` / `load_enoe_hogares` return the `viv`/`hog` tables with numeric weights and
that level's key as a sorted `MultiIndex`; `load_enoe_survey` returns all three with the shared
nested index so they align/join like the extended-census `ID_VIV`/`ID_PERSONA` microdata. The
panel identifiers `tipo`/`mes_cal`/`ca` live in the **dwelling** portion of the key (they
distinguish a dwelling across panel visits) so the prefixes stay clean — note this reorders
`_person_key`'s output relative to the pre-refactor `_KEY_SPEC` (the column *set* is unchanged, so
joins/filters are unaffected; only the `docs/enoe/STEP_9.md` refactor changed the order).
`load_enoe_persons` stays flat (unchanged); only `load_enoe_survey` sets the person `MultiIndex`. `variables_enoe_core.yaml` is **hand-curated** and never regenerated;
`--variables` overlays it onto the data-derived per-group dictionaries. Full build/upload
procedure and gotchas: `docs/enoe/HANDOFF.md` + `STEP_*.md`.

### Cache directory

Resolved by `platformdirs` in priority order:
1. `$MXCENSUS_CACHE_DIR` env var
2. `~/Library/Caches/mxcensus` (macOS)
3. `~/.cache/mxcensus` (Linux/XDG)

`mxcensus info` shows the resolved path. The `POOCH` object in `mxcensus.data` can be used directly for advanced access.
