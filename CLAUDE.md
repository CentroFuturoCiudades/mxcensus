# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies (add ,notebook for Jupyter/Quarto)
uv pip install -e ".[dev]"            # or: uv sync --extra dev --extra notebook

# Run tests (DENUE suite tests/test_denue.py ~93 tests; ENOE tests/test_enoe.py; ENIGH tests/test_enigh.py;
# CPV tests/test_cpv.py (+ tests/test_cpv_derived.py); MG tests/test_mg.py; CLI tests/test_cli.py; frozen 2020 path tests/test_census_legacy.py)
pytest
pytest tests/test_denue.py        # single file

# CLI — pre-download parquet files for a state, show cache info
mxcensus fetch 9                  # all 4 datasets for state 9
mxcensus fetch 9 --dataset iter   # one dataset: iter|resargebub|personas|viviendas|denue|enoe|enigh|cpv|mg|all
mxcensus fetch 9 --dataset cpv    # EIC 2025 microdata for state 9 + the national estimaciones (--edition YYYY)
mxcensus fetch 9 --dataset cpv --edition 2020   # CPV 2020 microdata + ITER/AGEB for state 9
mxcensus fetch 9 --dataset mg --edition 2025   # every MG layer of the state in the registry (default 2020)
mxcensus info                     # resolved cache dir + mirror base URL
```

The project uses `uv` as the build tool. Python 3.13+ is required (`pyproject.toml`
declares `>=3.13`; the active venv runs 3.14).

## What this project does

`mxcensus` is a data loader and preprocessor for INEGI open data: Mexico's censuses and intercensal surveys (the legacy CPV 2020 path plus the multi-year `cpv` family, every census, conteo and intercensal survey 1990–2025), the Marco Geoestadístico (1995–2025), DENUE, ENOE and ENIGH. It fetches pre-converted parquet files from a curated mirror hosted in a Hugging Face Storage Bucket, parses them (handling censored values and missing data conventions), and returns clean pandas DataFrames ready for analysis.

The original (legacy, frozen) census path supports three dataset types; the other
families are described in their own sections below:

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
The multi-year families export their own loaders: `load_cpv*` / `load_cpv_survey` /
`load_cpv_estimaciones` (censuses and intercensal surveys), `load_mg` (any Marco
Geoestadístico layer and edition), `load_denue`, `load_enoe*` and `load_enigh*`.

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
| `enoe.py` | `load_enoe(table=, period=…, harmonize=, ent=)` — fetches one raw ENOE table (`viv`/`hog`/`sdem`/`coe1`/`coe2`) for one quarter as a faithful `dtype=str` frame, resolves its **per-table** schema group by column fingerprint (`_group_of`, raises on unknown), and validates against the tight per-group Pandera schema `_group_schema(table, gid)` (value-level violations **warn**, don't raise — `_validate`); `harmonize=True` applies `_harmonize` (cross-era **analytical-core** canonicalization: lowercase names, `fac`/`est_d`/`t_loc`→`*_tri` + NA `*_men`, `ent`/`mun`/`loc`/`ageb`→zero-padded `cve_*` + derived `cvegeo` (= `cve_ent`+`cve_mun`, `999` for unspecified), NA `tipo`/`mes_cal` before 2020-T3; every non-core column kept verbatim; generic `_RENAME_CORE`, not per-group) and validates against `_latest_schema(table)` (`isin` on the FD-sourced core categories, numeric weights, width regex on the padded codes). `load_enoe_persons(period=…, ent=, canonical_filter=, harmonize=)` — the analytical person frame: SDEM left-joined with COE1/COE2 on the era-appropriate person key (`_person_key`, handling the `ent`→`cve_ent` rename + panel-era `tipo`/`mes_cal`/`ca` widening), filtered to the canonical universe `R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]`, with a numeric canonical `fac_tri` weight and `is_pea`/`is_ocupado`/`is_informal` flags. `load_enoe_viviendas(period=, ent=, harmonize=)` / `load_enoe_hogares(period=, ent=, harmonize=)` — analysis-ready dwelling/household frames (numeric weights via `_coalesce_fac_tri`; era-appropriate hierarchical `MultiIndex` via `_index_level`). `load_enoe_survey(period=, ent=, persons="all"|"labor", harmonize=)` — returns the plain tuple `(viviendas, hogares, personas)` with a **shared nested `MultiIndex`** (dwelling ⊂ household ⊂ person, as the extended census shares `ID_VIV`/`ID_PERSONA`); `persons="all"` (default) = full SDEM so households fully decompose, `persons="labor"` = the `load_enoe_persons` frame. The three level keys come from one source of truth — `_DWELLING_KEY_SPEC` ⊂ `_HOUSEHOLD_KEY_SPEC` ⊂ `_PERSON_KEY_SPEC`, resolved per era by `_level_key` (`_person_key` = the person spec). National (no per-state split); `ent` is a post-load row filter. **Labels**: `load_enoe(labels=False)` is faithful-raw; `labels=True` — the **default of every analysis-ready loader** — maps coded fields to labelled `Categorical` columns (ordered per `Ordenada`), numeric fields to `Int64`/`Float64` with sentinel codes as NA, computes flags/filters from the raw codes *first* (weighted totals identical either way), never labels the key columns (`_KEY_COLUMNS`, the shared index), and validates strictly (`_finish_labelled` → `validate_raise`; an unmapped code raises). `variables_enoe_labels(table, gid)` is the merged dictionary |
| `crosstabs.py` | Builds contingency tables from the constraint YAML specs |
| `utils.py` | `expand_cat_map` (expands `"1..5"` range keys into per-int label maps), `expand_cat_map_str` (its string-keyed sibling for the survey dictionaries — keeps zero-padding) and `get_cats_from_excel` (generates the `_yaml/` category files from INEGI Excel data dictionaries) |
| `_schema_groups.py` | Shared machinery for the multi-temporal families (DENUE/ENOE/ENIGH): `fingerprint` (sha256 of ordered column names — the single recipe the build scripts write into the `*_schema_map.yaml` and the loaders resolve against), `group_of` (fingerprint → gid, raises on unknown), `build_group_schema` (**raw** frames: weights → numeric, `Categorías` → `isin` on `Categorías ∪ Especiales ∪ Alias` keys with whitespace-only cells blanked to NA first (`raw_column`/`_BLANK_TO_NA` — INEGI writes `' '` for not-applicable), `Tipo: numeric` → parse + `Rango`/sentinel check, optional per-family `column_rule` e.g. DENUE's coded-field regexes, else str), `validate_warn` (lazy validate + warn summary), and the hierarchical-key helpers `level_key`/`index_level`. **Labelled** frames: `norm_tipo` (`Tipo` vocabulary `categorical|numeric|string`, legacy spellings tolerated), `label_frame` (Alias → code→label map incl. `Especiales`; numeric: sentinels → NA + `to_numeric`; weights numeric; `skip` keys; **raises** listing unmapped codes), `build_labelled_schema` (`CategoricalDtype` of the labels, `ordered` per `Ordenada`, `Int64`/`Float64` (`Decimales`) + `Rango`, unique nullable key index, undeclared columns pass through), `validate_raise` (lazy validate, raise `ValueError` with the same summary as `validate_warn`). Each family module keeps its private `_fingerprint`/`_group_of`/`_group_schema`/`_validate`/`_level_key`/`_index_level` as thin wrappers bound to its own accessors |
| `_resources.py` | Lazy, cached loader for the bundled YAML (`variables_*`, `constraints_*`, `denue_schema_map`, `variables_denue_<gNN>`, `enoe_schema_map`, `variables_enoe_<table>_<gNN>`, `variables_enoe_core`, the ENIGH trio, the CPV trio `cpv_schema_map`/`variables_cpv(table, gid)`/`variables_cpv_core`). The merged *labelling* dictionaries live in the family modules (`enoe.variables_enoe_labels(table, gid)`, `enigh.variables_enigh_labels(table, gid)` — per-group overlaid by core, keyed by raw **and** harmonized names) |
| `_cli.py` | Two subcommands: `fetch` (pre-download a state; `--dataset denue --release` for DENUE; `--dataset enoe --period` / `--dataset enigh --edition` for the national surveys — `STATE` is optional there and required/range-checked otherwise; `--dataset cpv --edition` (state microdata + the national tables, default latest) and `--dataset mg --edition` (every `MG_LAYERS` file of the state, default 2020) offer only files in `POOCH.registry`; selector flags are validated through `SELECTOR_FLAGS` (flag → datasets), national datasets listed in `NATIONAL_DATASETS`; `main(argv=None)`) and `info` |
| `data/_registry.py` | Global `POOCH` instance; loads `registry.txt` at import time; no network traffic until `.fetch()` is called |
| `data/_paths.py` | Cache-dir resolution via `platformdirs`; respects `$MXCENSUS_CACHE_DIR` |
| `data/_catalog.py` | `STATE_ABBR`, `STATE_CODE_FMT`, legacy CPV 2020 URL builders, the `CatalogEntry` dataclass, and the Marco Geoestadístico editions (`MgEdition`/`MG_EDITIONS` 1995–2025, `marco_geo_zip_url(state, period="2020")`, `marco_geo_national_url`, `mg_filename(suffix, state, period)` — 2020 keeps the period-less `mg_{sfx}_{NN}`, other periods `mg_{sfx}_{period}_{NN}`), `MG_LAYERS` (16 suffixes → content, from the ZIPs' `contenido.txt`) and `MG_OPTIONAL_LAYERS` (`ti`, island states only) |
| `data/_cpv_catalog.py` | **CPV family** (status and next unit: `docs/cpv/HANDOFF.md`): censos/conteos/encuestas intercensales 1990–2025. `CpvEdition` (8 editions keyed by year; `kind`, per-product URL templates, per-table ZIP-member regexes, `weighted`, `ddi_id`, `biinegi_id`, `mg_period`), `TABLES` (`viviendas`/`hogares`/`personas`/`migrantes` microdata; `iter`/`ageb`/`estimaciones` aggregates), `PRODUCT_OF`, `HIST_SLUG`, `FILE_RE`/`cpv_filename`/`parse_filename` (`cpv_{table}_{period}_{NN}.parquet`, national `cpv_{table}_{period}.parquet`), `find_member`, `latest_edition(table)`, `cpv_zip_entry`, `DICTIONARY_URLS` |
| `data/_denue_catalog.py` | `DenueRelease`, `RELEASES` (25 verified release URL templates incl. state-15 multipart & per-release quirks), `denue_zip_entry`, `latest_release` |
| `cpv.py` | **CPV family** (censos/conteos/encuestas intercensales; released: every edition 1990–2025 — EIC 2025, CPV 2020, EIC 2015, CPV 2010, Conteo 2005, CGPV 2000, Conteo 1995 and CGPV 1990) microdata loaders on the ENIGH pattern. `load_cpv(survey_path=None, *, table, period=None, state=None, harmonize=False, labels=False)` — one raw table as a faithful `dtype=str` frame, per-table fingerprint group + `_group_schema(table, gid)` validation (warns). `state`: INEGI code or sequence (`_states`); required for the per-state microdata (a sequence concatenates; states in different groups raise unless `harmonize=True`), a `CVE_ENT` row filter on national tables. `harmonize=True` → core-only `_harmonize` (upper-case names, `_renames(table)` = global `_RENAME_CORE` (2015/2020 `ENT`/`MUN`→`CVE_ENT`/`CVE_MUN`) + per-table `_RENAME_TABLE` (ITER/AGEB `ENTIDAD`/`LOC`→`CVE_ENT`/`CVE_LOC`, AGEB `AGEB`/`MZA`→`CVE_AGEB`/`CVE_MZA` — the MG's names), national keys for the state-scoped 2010 serials (`_national_keys`: `ID_VIV` = entity + serial, `ID_PERSONA` = `ID_VIV` + `NUMPER`, `ID_MII` = `ID_VIV` + rank), zero-padded geography, keys and `CLAVIVP` (`_GEO_PAD`, `_CODE_PAD`: the 2015 CSVs drop leading zeros; a code only in the editions its core entry covers), the in-scope core `Alias` recodes (`_scoped_entry`: a core `Recodificar` = per-edition alias, 2000/2005 `SEXO` 2 → 3), the derived 2000/2005 keys (`_composite_keys`), `CVEGEO` = the leading `_GEO_PARTS` concatenated (5 microdata, 9 estimaciones/ITER, 16 AGEB; totals keep zero parts) or checked, numeric `FACTOR`; identity for 2025 up to the `FACTOR` dtype) validated by `_latest_schema(table)`. One edition per call: stack editions with two `harmonize=True` calls + `pd.concat(..., names=["PERIOD"])`. Analysis-ready `load_cpv_viviendas`/`load_cpv_hogares` (Conteo 2005 only)/`load_cpv_personas`/`load_cpv_migrantes(period=None, *, state, harmonize=False, labels=True)` (numeric `FACTOR`, labelled, strict `_finish_labelled`, indexed by the level key) and `load_cpv_survey` → `(viviendas, personas, migrantes \| None)` with a shared index: `_DWELLING_KEY_SPEC` = `ID_VIV`, `_HOUSEHOLD_KEY_SPEC` = `+ID_HOG` (2000/2005 only; absent elsewhere, so `level_key` drops it — `_OPTIONAL_KEYS`), persons `+ID_PERSONA` (`ID_PER`) and emigrants `+ID_MII` (`ID_MIN`) are **siblings** under the household/dwelling; `viviendas` uses the household spec, so CGPV 2000's dwelling file (one row per household) is indexed `(ID_VIV, ID_HOG)`. 1990–2005 have no key column (1990/1995 publish person files only — `load_cpv_survey` gives `None` for their dwellings; 1995's `datgen95` is `personas`, weights `FAC_POB`/`FAC_VIV`/`FAC_PROM` in `_WEIGHTS`; `harmonize=True` adds `FACTOR` = `FAC_POB` (persons) / `FAC_VIV` (emigrants), `_FACTOR_FROM`; 1990's `ID_VIV` = ENT + FOLIO_VIV + the folio's occurrence in file order, `_folio_occurrence`): `_composite_keys(frame, table)` derives `ID_VIV` (2000: ENT+MUN+LOC+NUMVIV, 15 digits; 2005: ENT+MUN+CONS_MUN padded to 7, 12 digits — idempotent under `_CODE_PAD`), `ID_HOG` (+2-digit NUMHOG/CONS_HOG), `ID_PERSONA` (2005 +CONS_PER; 2000's persons are unnumbered → their order in the household in file order) and `ID_MII` (2000 +MPER) in the keyed loaders (`harmonize=False` too) and in `_harmonize` (after the padding: raw = harmonized keys); `load_cpv` never adds them. The key parts (`_KEY_PARTS`: NUMVIV/NUMHOG/CONS_*) stay strings. Keys, geography (incl. the 2020 raw `ENT`/`MUN`/`ENTIDAD`/`LOC`/`AGEB`/`MZA`) and person-number pointers (`_SKIP`) stay raw strings. `variables_cpv_labels(table, gid)` overlays the core entries in scope for the table and the group's editions (`_in_scope`: a core entry's `Tablas` and `Periodos`); keyed loaders refuse several states of an edition with state-scoped keys (`_STATE_SCOPED_KEYS` = 2010) unless `harmonize=True`; `_labels_for` (several groups in one call) leaves out only columns whose label-relevant keys (`_LABEL_KEYS`) differ, not wording |
| `cpv_aggregates.py` | `load_cpv_estimaciones(period=None, *, estimador="valor", nivel=None, state=None, survey_path=None)` — the EIC 2025 national estimates (5 estimator rows per geography) reshaped to one row per geography × one column per indicator, indexed `(CVE_ENT, CVE_MUN, CVE_LOC)` on **string** codes, an ordered `NIVEL` (`nacional\|estatal\|municipal\|resto_estatal\|localidad`), `ESTIMADOR` `valor\|ee\|li\|ls\|cv` (a list/`None` keeps it as the last index level), `NA`/`MI` → missing. Census aggregates (3c/4b/5a): `load_cpv_iter` (1990, 1995, 2000, 2005, 2010, 2020; in 1995 the one/two-dwelling localities exist only as the 9998/9999 aggregates) / `load_cpv_ageb` (2010, 2020) `(period=None, *, state, nivel=None, impute=True)` — harmonized (the crosswalk's renamed indicators under the canonical name), labelled, one frame with an ordered `NIVEL` (ITER `estatal/municipal/agregado/localidad`, AGEB `…/ageb/manzana`), reserved cells NA, `impute=True` = the forced-zero imputation (`_impute_zeros`, port of `aggregate.impute_zeros_univariate`); ITER rows whose locality name spilled into `LONGITUD` (a `LONGITUD` without digits: 2 in 2000, 7 in 1995) are shifted back with a warning (`_repair_spilled_names`; the mirror keeps them); `load_cpv_census(period, *, state)` (2010, 2020) = the legacy `load_census` chain on the `cpv_` files and string keys (equal to it for 2020 in all 32 states; NA-safe collective imputation `_add_collective_cols` — the legacy one crashed in states 08/15/16 until 6c added the same NA guard to `aggregate.impute_collective` — and its own `_census_checks`, which allows 2010's AGEB `TVIVHAB` shortfall, `_AGEB_TVIVHAB_SHORT`) |
| `cpv_derived.py` | **CPV derived columns** (6b): the legacy `load_extended_*` derived set on any CPV edition, from the raw codes (before labelling). `_registry()` = `_Derivation(table, columns, sources, periods, func)`: each derivation's source items, the editions verified (2020 + 2025 all; 2015/2010 only the items with identical code lists), and a function of the source codes **in the 2020 code space** (`_RECODE[period][item]`: 2025 `SITUA_CONYUGAL` 01–09/99 → 1–9, `DHSERSAL1/2` 05↔06, countries 454/536 → 241/356) mapped with the legacy YAML maps (`_legacy_map`) and legacy schema dtypes (`_legacy_dtypes`), so 2020 = legacy exactly. `DHSERSAL_SALUD_PUBLICA`/`DHSERSAL_IMSS_BIENESTAR` replace two legacy names (`DHSERSAL_RENAMES`); dummy sets are fixed (one per code). `derive(df, table, period)` raises on a source code without a category; `derived_dtypes`/`derived_schema`; `cpv_derivations(table, period)` lists them. New columns (6c): `DISCAPACIDAD`/`LIMITACION`, INEGI's definitions (code 8 = disability; limitation excludes the disabled; `_DTYPES`), beside the legacy `DIS_CON`/`DIS_LIMI`. `cpv_constraints(table, period)` = the legacy constraint YAMLs in the CPV vocabulary (neutral DHSERSAL names, the 2020 FD's labels via `_relabels`, `PCON_DISC`/`PCON_LIMI` on the INEGI flags via `_CELLS`) filtered to the indicators the edition publishes (`_aggregate_indicators`: ITER via the crosswalk — older editions only where `Comparable`; EIC 2025 estimaciones) whose variables/categories exist (`_categories`). Loaders: `load_cpv_personas/viviendas/survey(derived=False)` |
| `cpv_geo.py` | Cross-edition municipal geography (6a): `cpv_mun_lineage()` — every municipality code created between consecutive MG frames 1995→2000→2005→2010→2020→2025 (50; none retired) with its parents covering ≥5% of its area and the area shares, from `_yaml/cpv_mun_lineage.yaml` (built by `scripts/build_geo_crosswalk.py` from the `mg_mun_*` polygons); `cpv_municipal_units(start, end, *, min_share=0.10, cross_state=False)` — stable units (`CVEGEO` → `UNIT`, `FIRST`) joining each municipality created in between with its parents, for comparing editions (1990: no frame) |
| `mg.py` | `load_mg(layer, *, state, period="2020", crs="EPSG:6372")` — one Marco Geoestadístico layer (`_catalog.MG_LAYERS`) for one or more states of any MG edition (2020 = legacy `mg_{sfx}_{NN}`, else `mg_{sfx}_{period}_{NN}`), concatenated with a fresh `RangeIndex`; attribute codes stay zero-padded strings. INEGI spells its one LCC projection two ways (custom `MEXICO_ITRF_2008_LCC` vs EPSG:6372) **within** each edition (2020: `fm`, in 30 states; 2025: `ar`/`ent`/`lpr`/`mun`/`ti`), so the mirror keeps the source CRS and `crs=` (default `CANONICAL_CRS` EPSG:6372 — a PROJ no-op, coordinates bit-identical) puts every layer on one CRS; `crs=None` keeps it (mixed states then raise). A file missing from the registry → `ValueError` (`ti` exists only for island states). `load_mg_census` is untouched |
| `enigh.py` | `load_enigh(table=, period=…, harmonize=, ent=)` — one raw ENIGH table (13 canonical names; `gastotarjetas`/`gastos` are 2008–2014-only) for one edition year as a faithful `dtype=str` frame, per-table fingerprint group (`_group_of` raises on unknown) + tight `_group_schema(table, gid)` validation (warns). `harmonize=True` → `_harmonize`: lowercase, `factor_hog`/`factor_viv`→`factor` (all tables), the 2008/2010 `concentradohogar` spellings (`_RENAME_TABLE`: `ingcor`→`ing_cor`, `tam_hog`→`tot_integ`, `n_ocup`/`pering`/`perocu`→`ocupados`/`percep_ing`/`perc_ocupa`, head `sexo`/`edad`/`ed_formal`→`*_jefe` — table-scoped because `poblacion` has person-level `sexo`/`edad`), zero-padded `educa_jefe`, derived `cve_ent`/`cve_mun`/`cve_loc`/`cvegeo` from `ubica_geo` (9 chars 2012–2022, 5 chars 2008/2010/2024; `cve_ent` from `folioviv[:2]` when `ubica_geo` is absent); non-core columns verbatim; validated by `_latest_schema(table)`. Analysis-ready: `load_enigh_hogares` (= `concentradohogar`, numeric `factor`/`ing_cor`/…, household `MultiIndex`), `load_enigh_viviendas` (2012+), `load_enigh_personas` (`poblacion` + `factor` joined from `concentradohogar` via `_attach_factor` when the raw table has no weight), `load_enigh_survey` → `(viviendas, hogares, personas)` with the shared nested index (`_DWELLING_KEY_SPEC` ⊂ `_HOUSEHOLD_KEY_SPEC` ⊂ `_PERSON_KEY_SPEC` = `folioviv` ⊂ `+foliohog` ⊂ `+numren`, unique at each level in every edition). `ent` filters on `folioviv[:2]`. `labels=` as in ENOE: raw default on `load_enigh`, labelled default on the analysis-ready loaders (`_attach_factor` joins the raw household summary first, then the frame is labelled once); `variables_enigh_labels(table, gid)` |
| `data/_enoe_catalog.py` | ENOE bulk-download catalog: `EnoeQuarter`, `QUARTERS` (85 quarters 2005-T1…2026-T2, 2020-T2 ETOE gap excluded), `QUARTERS_BY_PERIOD`, `latest_quarter`, `TABLES`, three filename regimes (`enoe_old`/`enoen`/`enoe_new`) + `find_member`. National (one ZIP per quarter, five tables) |
| `scripts/_build_common.py` | **Maintainer-only** — shared build helpers: `fetch_zip_verified` (download+verify+retry), `detect_encoding`, `update_registry` (append/upsert preserving prior entries) |
| `scripts/build_data.py` | **Maintainer-only** — the frozen **legacy CPV 2020** builder: downloads the 2020 census ZIPs, converts CSVs to parquet (inferred dtypes), upserts their hashes into `registry.txt` via `_build_common.update_registry` (never rewrites other families' entries) |
| `scripts/build_marco_geo.py` | **Maintainer-only** — downloads INEGI's per-state Marco Geoestadístico shapefile ZIPs for `--period` (default 2020, UPC 889463807469; 2025 = EIC 2025 frame, UPC 794551196649 — `_catalog.MG_EDITIONS`, via `marco_geo_zip_url`) and converts every `MG_LAYERS` layer (15/state + `ti` in the 13 island states; an absent optional layer is skipped quietly) to geoparquet (`mg_filename`: `mg_{suffix}_{NN}.parquet` for 2020, `mg_{suffix}_{period}_{NN}.parquet` otherwise; period-qualified ZIP cache/raw dirs, single→Multi* geometry, int32 codes, source `.prj` CRS kept); appends to `registry.txt` (`--no-registry` skips; `--update-registry` upserts the hashes of files already built, no download). `--local-gpkg-dir DIR` uses a local gpkg copy instead of downloading. **National-ZIP editions** (`layout="national"`: 2010 v5.0 and the 1995/2000/2005 municipal frames; `_build_national`): one ZIP of per-layer ZIPs, each shapefile mapped to a suffix by name (`_NATIONAL_LAYERS`: Entidades→`ent`, Municipios→`mun`, AGEB(s)_urb→`a`, Localidades urbanas/rurales→`l`/`lpr`), split per state on the edition's entity column (`_ENTITY_COLUMNS` `CVE_ENT`/`CVE_EDO`, else the first two characters of `CVEGEO`/`CVE_CONCA`/`CVEMUNI`/`CLVAGB`/`CLAVE`); a layer without `.prj` (MG 2005 `ent`/`mun`) takes the CRS the edition's other layers declare (`_edition_crs`); INEGI's attribute names kept |
| `scripts/build_cpv.py` | **Maintainer-only** — builds the CPV family: loops over (edition, product ZIP, state), one microdata ZIP per state holding several tables, and writes faithful-raw parquet `cpv_{table}_{period}_{NN}.parquet` / national `cpv_{table}_{period}.parquet` (every column `string`, only empty cells null; CSVs read with `pyarrow.csv` after a streamed encoding sniff — pandas `dtype=str` does not fit the large personas files). Only editions in `_ENABLED` build (all eight: 1990–2010 are DBF, `scripts/_dbf.py`); `--dry-run` previews any. 1990/1995 have no indicator CSV: `--dictionary` converts INEGI's ITER descriptor PDFs (`DICTIONARY_URLS[…]["fd_iter"]`, AES-encrypted → poppler `pdftotext -tsv`, `_dict_fd.pdf_words`/`parse_iter_fd_tsv`, `_ITER_FD_ALIGN` top/center) into `diccionario_datos_iter.csv`; indicator misspellings in `_INDICATOR_RENAMES`. `_fd_docs` maps FD sheets / PDF file tags to tables (`_FD_SHEET_TABLE`) and fixes FD misspellings of data columns (`_FD_RENAMES`: 2000 `TIPHOG`→`TIPOHOG`, 2005 `TOPERHOG`→`TOTPEHOG`); the 2000 FD is a PDF inside a ZIP (`_FD_MEMBER_RE`); `--variables` applies the core per edition (`cpv._scoped_entry`). `--crosswalk` writes `cpv_iter_crosswalk.yaml`. Same mode set as `build_enigh.py`: `--dictionary` (FD xlsx/xls + classification catalogs + indicator dictionaries → `data/dict/fd/`; DDI codebooks → `data/dict/ddi/` for reference), `--schema-map`, `--report-only`, `--variables` (core > FD > data), `--validate` (`--jobs`), `--update-registry`. Metadata modes run on `wsl` only (the full mirror) |
| `scripts/_dbf.py` | **Maintainer-only** — stdlib (+ NumPy/Arrow) dBASE III reader for the 1990–2010 census DBFs and the 2010 catalogs: `read_dbf(path or bytes)` → `DbfTable(table, encoding, deleted, header)`, every field a `string` column (fixed-width padding trimmed, empty → null, deleted records dropped and counted), memory-mapped and decoded per field (ASCII cast, else per distinct value); `sniff_encoding` picks cp1252/cp850 from the high bytes (INEGI's language-driver byte is unreliable), the driver byte breaking ties |
| `scripts/_dict_fd.py` | **Maintainer-only** — INEGI's census "FD" data dictionaries (xlsx; legacy BIFF8 xls for EIC 2015, CPV 2010 and the Conteo 2005 — its split layout: description, definition, ranges, code/label, data mnemonic and catalog in separate columns, `_FD_HEADERS`; the CGPV 2000 FD is a PDF annex → `parse_fd_pdf`/`parse_fd_text` on `pypdf` text, handling wrapped headers/mnemonics/range lists) → the `_dict_ddi.parse_ddi` shape (`parse_fd`, `fd_entry`; code ranges, `Nulo`/«Blanco» rows, classification-catalog pointers as `Catálogo` — 2020/2025 «Según clasificador de…», 2015 `TC_…` rows; 2015's «Numérico» coded items whose rows enumerate the header → categorical, `_enumerated`; 2010/2005/2000 FDs have no Tipo column → `_quantity` infers numbers: one labelled range row or one header range (+ sentinels) = a count, several = a code list; `b` = blank), read with stdlib readers (`read_xlsx`, `read_xls` = OLE2 + BIFF8, `read_workbook` dispatches; no openpyxl/xlrd); `read_catalogs` (CSV, `.xls` or `.dbf` members, or one multi-sheet `.xls` — 2005, keys = the columns before `DESC`); a code row's FD label wins over the catalog's when they are the same words (2005's catalogs are in capitals); `parse_indicator_csv` for the aggregates' `diccionario_datos_*.csv` (footnoted `NA`/`MI` → `Especiales`) |
| `scripts/build_denue.py` | **Maintainer-only** — downloads/converts DENUE to geoparquet (`denue_{YYYYMM}_{NN}.parquet`), detects inconsistencies (`docs/denue/INCONSISTENCY_REPORT.md`), extracts data dictionaries (CSV 2016+ / PDF 2010–2013 via `pypdf`) to fill `variables_denue_*.yaml` descriptions + categories (categories cross-validated against the data → `docs/denue/CATEGORY_AUDIT.md`), generates `denue_schema_map.yaml`, validates every file against its group schema (`docs/denue/VALIDATION_REPORT.md`), derives/repairs point geometry against state boundaries (`docs/denue/GEOMETRY_REPORT.md`), appends to `registry.txt`. Modes: `--schema-map`, `--variables` (`--cat-threshold`), `--validate`, `--refilter-boundaries` (`--boundary-buffer-m`/`--boundaries-dir`/`--geometry-report`), `--report-only`, `--update-registry`, `--dry-run` |
| `data/_enigh_catalog.py` | ENIGH bulk-download catalog: `EnighEdition`, `EDITIONS` (2008–2024 biennial), `EDITIONS_BY_PERIOD`, `latest_edition`, `TABLES`/`NS_TABLES`, two regimes under one tree (`ns` `enigh{year}_ns_{table}_csv.zip`; `ncv` `NCV_{Stem}_{year}_concil_2010_csv.zip` with per-year stems via `ncv_stem`), `edition.tables` (per-year set), `find_member` (sole-CSV fallback), `enigh_zip_entry(edition, table)` — one ZIP per (edition, table) |
| `scripts/build_enoe.py` | **Maintainer-only** — downloads each ENOE quarter's CSV ZIP from INEGI and converts the five tables to faithful-raw parquet (`enoe_{table}_{period}.parquet`, every column `dtype=str`, no geometry). Fingerprints each file into a **per-table** schema group (`enoe_schema_map.yaml`), writes per-group variable dictionaries (`variables_enoe_{table}_{gNN}.yaml`: hand-curated core > INEGI DDI codebook (`--dictionary` fetches them from the RNM into `data/dict/ddi/`; `_ddi_doc_for` picks the exact `(table, period)` file or the best-overlapping same-table file of the same/previous year) > data-enumerated), validates each file against its group schema (the **label-coverage gate** — its `isin` keys are exactly what `labels=True` maps), and appends to `registry.txt`. Modes: (build) `--periods`/`--tables`/`--dry-run`/`--keep-raw`, then `--dictionary` (`--ddi-dir`), `--schema-map`, `--variables` (`--cat-threshold`), `--report-only` (`docs/enoe/INCONSISTENCY_REPORT.md`), `--validate` (`docs/enoe/VALIDATION_REPORT.md`), `--update-registry`. See `docs/enoe/HANDOFF.md` + `STEP_*.md` |
| `scripts/build_enigh.py` | **Maintainer-only** — downloads each ENIGH (edition, table) CSV ZIP and converts it to faithful-raw parquet (`enigh_{table}_{year}.parquet`). Same mode set as `build_enoe.py` (`--periods`/`--tables`/`--dry-run`, `--dictionary`, `--schema-map`, `--variables`, `--report-only`, `--validate`, `--update-registry`); per-table schema groups in `enigh_schema_map.yaml`, per-group `variables_enigh_{table}_{gNN}.yaml` = core > DDI (one codebook per edition, `ENIGH_DDI`; 2008/2010 stems via `_DDI_STEM_ALIASES`) > data; reports in `docs/enigh/`. Filenames are parsed with `_FILE_RE` (not `split("_")`). See `docs/enigh/HANDOFF.md` |
| `scripts/upload_hf.py` | **Maintainer-only** — host the parquet mirror in the Hugging Face Storage Bucket (`mxcensus.data._registry.HF_BUCKET`), the package's **current** data source. Subcommands: `create` (make the bucket), `upload` (`hf buckets sync` of `data/parquet/*.parquet` to the bucket root + the provenance `docs/hf_bucket_readme.md` as `README.md`; `--delete`/`--dry-run`), `verify` (HEAD each `…/resolve/<file>` URL vs local size, no download). Buckets are mutable (overwrite-in-place), so re-uploading after a rebuild just syncs changed files |
| `scripts/upload_release.py` | **Maintainer-only** (legacy GitHub-Release alternative; superseded by `upload_hf.py`) — resumable batch upload of the parquet mirror to a GitHub Release. Source of truth for "already uploaded" is the release itself (queried live via `gh release view`), so it survives multi-day / partial uploads. Batches derived from `registry.txt`: `core_denue` (latest DENUE), `core_census` (iter/resargebub/personas/viviendas), `core_mg` (the 4 MG layers `load_mg_census` fetches), `mg-rest` (other 11 MG layers), one `denue-<id>` per older release. Subcommands: `status` (`--write-doc`), `list <batch>`, `create-release`, `verify <batch…>` (compares each asset's GitHub SHA-256 digest + size to `registry.txt` via `gh api`, no download), `upload <batch…>` or `--next` (`--clobber`/`--chunk N`/`--dry-run`; auto-creates the release if missing) |

### YAML schemas (`_yaml/`)

- `variables_personas.yaml` / `variables_viviendas.yaml` – microdata variable names, descriptions, and value→label category mappings (generated by `utils.get_cats_from_excel` from INEGI's Excel dictionaries)
- `variables_iter.yaml` / `variables_resargebub.yaml` – aggregate-dataset indicator dictionaries: `Indicador`/`Descripción`/`Rangos`/`Longitud` per mnemonic, no category maps (generated by `utils.get_vars_from_indicator_csv` from the `diccionario_datos_*.csv` inside the INEGI ZIPs; national, one copy per dataset)
- `constraints_personas.yaml` / `constraints_viviendas.yaml` – valid variable combinations for crosstab generation
- `denue_schema_map.yaml` – DENUE column-fingerprint → schema group (g01..g11), group→columns, and `latest` (harmonization target); `variables_denue_<gNN>.yaml` – per-group DENUE variable dictionaries (`Descripción`/`Tipo`/`Longitud` from the release dictionaries; `Categorías` code→label maps for coded fields + data-enumerated categoricals — drives `_group_schema`; generated by `scripts/build_denue.py`)
- `enoe_schema_map.yaml` – **per-table** ENOE column-fingerprint → schema group map (one section per table `viv`/`hog`/`sdem`/`coe1`/`coe2`, each with `fingerprints`, `groups` gNN→columns, and `latest`); `variables_enoe_<table>_<gNN>.yaml` – per-(table, group) variable dictionaries generated by `scripts/build_enoe.py --variables` from, in priority, the hand-curated core, **INEGI's DDI codebooks** (RNM; label, `Pregunta`, type, code→label `Categorías` re-spelled to the data's zero-padding, `missing` codes as `Especiales`; undocumented observed codes appended with an identity label + `Nota`), else the data-enumerated identity map — drives `_group_schema(table, gid)` and the `labels=True` path; `variables_enoe_core.yaml` – **hand-curated** analytical-core dictionary (labels + `Ordenada`/`Rango`/`Especiales` for `clase1`/`pos_ocu`/`ing7c`/`eda`/… — overlaid by `--variables`, **never** regenerated). **Entry contract** (documented in the core header, read by `_schema_groups`): `Descripción`, `Pregunta`, `Tipo` (`categorical|numeric|string`), `Longitud`, `Categorías` {code: label}, `Especiales` {sentinel: label} (extra categories for a categorical, NA for a numeric), `Ordenada`, `Rango` [min, max], `Alias` {raw spelling: canonical code}, `Decimales`
- `cpv_iter_crosswalk.yaml` – the census ITER/AGEB indicators across editions (1990–2020, six censuses; 402 indicators; canonical = newest mnemonic → each edition's column, `Tablas`, `Renombrar` = the editions whose spelling harmonize renames onto the key (2010 `TAM_LOC` → `TAMLOC`; 2005 `P_TOTAL` → `POBTOT`…), `Comparable: false`, review `Nota`); generated by `build_cpv.py --crosswalk`: older editions auto-pair by normalized description (`_XW_DESC_PERIODS`, rejects in `_XW_UNPAIR`), plus reviewed `_XW_PAIRS_RENAMED`/`_XW_PAIRS_KEPT`/`_XW_NOTES`; read by `cpv._crosswalk_renames(table, periods)` (only the frame's edition) and `cpv_iter_crosswalk()`
- `cpv_schema_map.yaml` / `variables_cpv_<table>_<gNN>.yaml` / `variables_cpv_core.yaml` – the same trio for the CPV family (per-table; gids chronological — `g01` = CGPV 2000, `g02` = Conteo 2005, `g03`/`g04` = CPV 2010 (`g04` = state 15's lower-case `tam_loc`), `g05` = EIC 2015, `g06` = CPV 2020 and `g07` = EIC 2025 for `viviendas`/`personas`; `g01` = 2000, `g02`/`g03` = CPV 2010, `g04` = CPV 2020 and `g05` = EIC 2025 for `migrantes`; `g01` = Conteo 2005 for `hogares`; `g01` = CPV 2010 and `g02` = CPV 2020 for `iter`/`ageb`, `g01` for `estimaciones` (2025); core entries may scope themselves with `Tablas`/`Periodos` and recode an edition's spelling with `Recodificar`; dictionaries = core > INEGI's FD xlsx/xls / indicator CSV > data; the core — keys, geography, `FACTOR`, `ESTRATO`, `UPM`, `COBERTURA`, `TAMLOC`, `SEXO`/`EDAD` … — is hand-curated and never regenerated)
- `enigh_schema_map.yaml` / `variables_enigh_<table>_<gNN>.yaml` / `variables_enigh_core.yaml` – the same trio for ENIGH (13 tables; core = keys, `factor`, `ubica_geo`, `tam_loc`/`est_socio` (ordered), `clase_hog`, head variables (`educa_jefe` ordered, with an `Alias` folding the un-padded 2012 codes onto the padded ones), `ing_cor`/`ingtrab`/`gasto_mon` (`Decimales` → `Float64`), `sexo`/`edad`/`parentesco`)

`_resources.py` loads these once via `@functools.cache` and exposes them as `variables_*()` / `constraints_*()` / `variables_denue(gid)` / `denue_schema_map()` / `variables_enoe(table, gid)` / `enoe_schema_map()` / `variables_enoe_core()` / `variables_enigh(table, gid)` / `enigh_schema_map()` / `variables_enigh_core()` / `variables_cpv(table, gid)` / `cpv_schema_map()` / `variables_cpv_core()`. The DDI codebooks themselves are **not** bundled: `scripts/_dict_ddi.py` (`ENIGH_DDI`/`ENOE_DDI` catalog ids, `fetch_ddi`, `parse_ddi`, `dictionary_entry`) downloads them into the git-ignored `data/dict/ddi/` at build time (`--dictionary`).

### Census data hierarchy

ITER and RESARGEBUB data follow: State → Municipality → Locality → AGEB → Block (MZA). Each level uses a different row in the raw file; `load_iter()` and `load_resargebub()` accept `.parquet` or `.csv` paths and split rows into level-specific DataFrames with appropriate multi-indices.

### Censored values

INEGI encodes suppressed counts as `*` (meaning 0, 1, or 2 persons). The parquet mirror preserves these as string values in object-dtype columns. `aggregate.py` maps them to masked `Int64` values and imputes zeros where parent-level totals confirm the suppressed value must be 0.

### Extended microdata preprocessing

Multi-response fields (health insurance categories, transport modes) are expanded into binary dummy columns then reduced to summary flags. The full preprocessing pipeline always runs at load time (no separate caching step). All output is validated with Pandera `DataFrameSchema` objects (built lazily in a cached `_build_schema()`; `coerce=True` is what materializes the `CategoricalDtype` columns). The ENOE/ENIGH `labels=True` path reproduces this design from YAML dictionaries (see below).

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

# Marco Geoestadístico geometries — scripts/build_marco_geo.py; 2020/2025: 15 layers × 32 states + ti × 13 island states per frame
mg_{suffix}_{NN}.parquet          # 2020 frame (493); suffix ∈ {a,ar,cd,e,ent,fm,l,lpr,m,mun,pe,pem,sia,sil,sip,ti}
mg_{suffix}_{period}_{NN}.parquet # other frames: 2025 = Encuesta Intercensal 2025 (493); national-ZIP frames split per
                                  # state: 2010 ent,mun,a,l,lpr (160); 2005/2000 ent,mun,a (96 each); 1995 ent,mun (64)

# CPV family (censos/conteos/intercensales 1990–2025; 897 parquet, no geometry) — scripts/build_cpv.py
cpv_{table}_{period}_{NN}.parquet # per state: EIC 2025 viviendas,personas,migrantes (96); CPV 2020 + iter,ageb (160);
                                  # EIC 2015 viviendas,personas (64); CPV 2010 viviendas,personas,migrantes,iter,ageb (160);
                                  # 2005 viviendas,hogares,personas,iter (128); 2000 viviendas,personas,migrantes,iter (128);
                                  # 1995 personas,migrantes,iter (96); 1990 personas,iter (64)
cpv_{table}_{period}.parquet      # national, e.g. cpv_estimaciones_2025

# DENUE economic units (25 releases × 32 states = 800 geoparquet, points) — scripts/build_denue.py
denue_{YYYYMM}_{NN}.parquet   # YYYYMM = release id (e.g. 202505); EPSG:4326

# ENOE labor-force survey (85 quarters × 5 tables = 425 parquet, national, no geometry) — scripts/build_enoe.py
enoe_{table}_{period}.parquet   # table ∈ {viv,hog,sdem,coe1,coe2}; period = {year}t{quarter} (e.g. 2023t1)

# ENIGH income/expenditure survey (9 editions × 10–12 tables = 99 parquet, national) — scripts/build_enigh.py
enigh_{table}_{year}.parquet    # table ∈ concentradohogar,viviendas,hogares,poblacion,ingresos,gastoshogar,gastospersona,trabajos,agro,noagro,erogaciones[,gastotarjetas,gastos]; year ∈ 2008…2024 biennial
```
Registry totals: 128 census + 1402 geo (493 MG 2020 + 493 MG 2025 + 160 MG 2010 + 96 MG 2005 + 96 MG 2000 + 64 MG 1995) + 800 DENUE + 425 ENOE + 99 ENIGH + 897 CPV (97 EIC 2025 + 160 CPV 2020 + 64 EIC 2015 + 160 CPV 2010 + 128 Conteo 2005 + 128 CGPV 2000 + 96 Conteo 1995 + 64 CGPV 1990) = **3751** entries.

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
python scripts/build_marco_geo.py --period 2025 --no-registry   # the EIC 2025 frame (~2.6 GB of ZIPs, ~2 h)
python scripts/build_marco_geo.py --period 2025 --update-registry   # upsert hashes of the built files only
# Appends mg_* entries to registry.txt (preserving other entries); then
# python scripts/upload_hf.py upload
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
python scripts/build_enoe.py --dictionary                 # fetch INEGI's DDI codebooks (RNM) → data/dict/ddi/
python scripts/build_enoe.py --schema-map                 # regenerate enoe_schema_map.yaml
python scripts/build_enoe.py --variables                  # regenerate variables_enoe_<table>_<gNN>.yaml (core > DDI > data)
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
python scripts/build_enigh.py --dictionary                    # fetch the 9 DDI codebooks → data/dict/ddi/
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

### CPV family (multi-year census)

The `cpv` family is built on branch `cpv-integration`, one unit per session. **The Encuesta
Intercensal 2025 is released** (units 1a–1e: 97 `cpv_*_2025*` files + the 493-file MG 2025
frame, registered and uploaded; every Σ `FACTOR` equals the published estimates exactly,
and every MG total equals the ZIPs' `contenido.txt`). **CPV 2020 is released** (units 2a–2b:
160 `cpv_{viviendas,personas,migrantes,iter,ageb}_2020_NN` files, faithful raw under
INEGI's names — `ENT`/`MUN`, ITER `ENTIDAD`/`LOC` — `--validate` 0/257, registered and
uploaded; cell-for-cell equal to the legacy `viviendas_`/`personas_`/`iter_`/`resargebub_`
files in all 32 states, `tests/test_cpv.py::test_cpv_2020_equals_legacy`). `harmonize=True`
maps the 2020 geography onto the 2025/MG names. The 2020 dictionary is the FD
xlsx: RNM DDI 632 exists but is a Nesstar export with incomplete value labels (kept as
`ddi_id`, unused). **EIC 2015 is built** (unit 3a: 64 `cpv_{viviendas,personas}_2015_NN`
files; every Σ `FACTOR` equals
INEGI's tabulados exactly, per state and nationally). **CPV 2010 microdata are built** (unit
3b: 96 `cpv_{viviendas,personas,migrantes}_2010_NN` from DBF via the stdlib `scripts/_dbf.py`;
`--validate` 0/417; Σ `FACTOR` outside `CLAVIVP` 5–7 = the cuestionario-ampliado tabulados
exactly). 2010's keys are state-scoped serials: raw multi-state keyed loads raise, and
`harmonize=True` builds national, nested keys (`cpv._national_keys`). Core entries may carry
`Periodos` (the editions they were verified for): 2010's `CLAVIVP` is another
classification, so the core `CLAVIVP` covers 2015–2025 only. Its dictionary is the
legacy BIFF8 `eic2015_fd.xls` + `eic2015_catalogos.zip` (`TC_*.xls`), read by the stdlib
`_dict_fd.read_xls` (DDI 214 is another incomplete Nesstar export); the 2015 CSVs drop
leading zeros (`ID_VIV`/`ID_PERSONA` in states 01–09, `CLAVIVP`), so the core `CLAVIVP` has an
`Alias` and `harmonize=True` pads all three (`cpv._CODE_PAD`). Gids are chronological: for
`viviendas`/`personas` 2015 = `g01`, 2020 = `g02`, 2025 = `g03`; `migrantes` 2020 = `g01`,
2025 = `g02` — 3b pushed them again: `viviendas`/`personas` 2010 = `g01` (+ `g02`, state 15,
whose DBFs spell `tam_loc` in lower case), 2015 = `g03`, 2020 = `g04`, 2025 = `g05`;
`migrantes` 2010 = `g01`/`g02`, 2020 = `g03`, 2025 = `g04`. Core entries may carry `Tablas` (scope; `TAMLOC` = microdata only, the
ITER's is a 14-class scale) and the ITER/AGEB sentinels `*`/`N/D`/`N/A` are declared in
`build_cpv._AGG_SPECIALS` (their dictionaries have no footnotes). The legacy
`iter_`/`resargebub_`/`personas_`/`viviendas_` files and `load_census`/`load_extended_*` stay
frozen, pinned by `tests/test_census_legacy.py`. **3c** added the 2010 ITER/AGEB (64 files),
`load_cpv_iter`/`load_cpv_ageb`/`load_cpv_census` (`cpv_aggregates.py`; `load_cpv_census(2020)`
equals the legacy `load_census`) and `cpv_iter_crosswalk.yaml`; with `wsl` unreachable, its
32-state verification ran on the Mac (`--validate` 0/481, metadata byte-identical, 32-state
tests). **4a** built the CGPV 2000 and Conteo
2005 microdata (192 files, `--validate` 0/673; dictionaries = the 2005 FD `.xls` + catalog
workbook and the 2000 FD PDF; derived composite keys and a household level; `load_cpv_hogares`;
2000's `FACTOR` is a ratio estimator on preliminary counts — bounded by the ITER, not equal to
it; 2005 is unweighted). **4b** added the 2000/2005 ITER (64 files; `--validate` 0/737), the
crosswalk over four censuses and the municipal MG 2000/2005 (192 files, plus MG 2010's 160
from 3d). **5a** added the 1990/1995 ITER (64 files; `--validate` 0/801; dictionaries from
INEGI's descriptor PDFs via poppler). **5b** added the 1990/1995 samples (96 files, person
files only; FDs from encrypted PDFs via `_dict_fd.parse_fd_1990_text`/`parse_fd_1995_text`,
numeric ranges reconciled with the data for these two editions, `build_cpv._reconcile_ranges`;
`--validate` 0/897) and MG 1995 (64 files). **6a** added the municipal lineage and stable
units (`cpv_geo.py`). **The release batch** (2026-10-08) registered and uploaded everything
built in 3a–5b: 1,056 files (640 `cpv_`, 416 `mg_`), rebuilt on `wsl` byte-identical to the
Mac's; registry 2695 → 3751, v0.7.0. **6b** added `cpv_derived.py` (`derived=True`: the
legacy `load_extended_*` columns on any edition — 2020 = legacy in 32 states, 2025 via
`_RECODE`, 2015/2010 identical-code items — and `cpv_constraints(table, period)`; the
EIC 2025 constraint cells equal its estimates in every state). **6c** (the review of the
pending decisions, 2026-10-08): the legacy `impute_collective` NA guard, `FACTOR` for
harmonized 1995 frames, INEGI's `DISCAPACIDAD`/`LIMITACION`; `main` = v0.7.0.
Next: per HANDOFF.
**Before working on it read `docs/cpv/HANDOFF.md`** (status, next unit, kickoff prompt) and
`docs/cpv/PLAN.md` (design, unit table, session protocol); `docs/cpv/STEP_0_probe.md` records
the verified INEGI URLs/members per edition.

### Cache directory

Resolved by `platformdirs` in priority order:
1. `$MXCENSUS_CACHE_DIR` env var
2. `~/Library/Caches/mxcensus` (macOS)
3. `~/.cache/mxcensus` (Linux/XDG)

`mxcensus info` shows the resolved path. The `POOCH` object in `mxcensus.data` can be used directly for advanced access.
