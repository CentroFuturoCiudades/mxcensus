# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies (add ,notebook for Jupyter/Quarto)
uv pip install -e ".[dev]"            # or: uv sync --extra dev --extra notebook

# Run tests (NOTE: tests/ currently holds only an empty __init__.py — no test
# suite exists yet, so `pytest` collects nothing. Add tests as tests/test_*.py.)
pytest
pytest tests/test_foo.py          # single file, once tests exist

# CLI — pre-download parquet files for a state, show cache info
mxcensus fetch 9                  # all 4 datasets for state 9
mxcensus fetch 9 --dataset iter   # one dataset: iter|resargebub|personas|viviendas|all
mxcensus info                     # resolved cache dir + mirror base URL
```

The project uses `uv` as the build tool. Python 3.13+ is required (`pyproject.toml`
declares `>=3.13`; the active venv runs 3.14).

## What this project does

`mxcensus` is a data loader and preprocessor for Mexico's 2020 Census (CPV 2020) published by INEGI. It fetches pre-converted parquet files from a curated mirror hosted on GitHub Releases, parses them (handling censored values and missing data conventions), and returns clean pandas DataFrames ready for analysis.

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
GitHub Release (raw parquet mirror)
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
| `denue.py` | `load_denue(state=N, release=…, harmonize=, dedupe=, dedupe_ids=)` — fetches a DENUE release/state geoparquet, optionally **harmonizes** it to the latest schema (g10) via per-group rename + `per_ocu`/`tipoUniEco`/`fecha_alta` canonicalization, then validates: raw frames against the tight per-group schema `_group_schema(gid)`, harmonized frames against `_latest_schema()`. `dedupe=True` (default) drops exact full-row duplicates; `dedupe_ids=True` (default) drops rows sharing an `id`/`clee` (collapses near-duplicates that differ only in coordinate precision/whitespace). Both clean only the loaded frame — the mirror stays faithful (duplicates are reported, not removed, by the build). Validation **warns** on value-level violations (it does not raise — `_validate`); an unknown schema raises. Multi-temporal economic-units directory (catalog: 25 releases 2010–2026; the mirror holds 24 until the latest **2026-05** — undated `denue_{state}_csv.zip` on INEGI's tree — is built and uploaded). |
| `crosstabs.py` | Builds contingency tables from the constraint YAML specs |
| `utils.py` | `expand_cat_map` (expands `"1..5"` range keys into per-int label maps) and `get_cats_from_excel` (generates the `_yaml/` category files from INEGI Excel data dictionaries) |
| `_resources.py` | Lazy, cached loader for the bundled YAML (`variables_*`, `constraints_*`, `denue_schema_map`, `variables_denue_<gNN>`) |
| `_cli.py` | Two subcommands: `fetch` (pre-download a state; `--dataset denue --release` for DENUE) and `info` |
| `data/_registry.py` | Global `POOCH` instance; loads `registry.txt` at import time; no network traffic until `.fetch()` is called |
| `data/_paths.py` | Cache-dir resolution via `platformdirs`; respects `$MXCENSUS_CACHE_DIR` |
| `data/_catalog.py` | `STATE_ABBR`, `STATE_CODE_FMT`, INEGI census URL builders, and the `CatalogEntry` dataclass |
| `data/_denue_catalog.py` | `DenueRelease`, `RELEASES` (24 verified release URL templates incl. state-15 multipart & per-release quirks), `denue_zip_entry`, `latest_release` |
| `scripts/_build_common.py` | **Maintainer-only** — shared build helpers: `fetch_zip_verified` (download+verify+retry), `detect_encoding`, `update_registry` (append/upsert preserving prior entries) |
| `scripts/build_data.py` | **Maintainer-only** — downloads raw census ZIPs from INEGI, converts CSVs to parquet, regenerates `registry.txt` |
| `scripts/build_marco_geo.py` | **Maintainer-only** — converts a local Marco Geoestadístico gpkg copy to geoparquet (15 layers/state, `mg_{suffix}_{NN}.parquet`); appends to `registry.txt` |
| `scripts/build_denue.py` | **Maintainer-only** — downloads/converts DENUE to geoparquet (`denue_{YYYYMM}_{NN}.parquet`), detects inconsistencies (`docs/denue/INCONSISTENCY_REPORT.md`), extracts data dictionaries (CSV 2016+ / PDF 2010–2013 via `pypdf`) to fill `variables_denue_*.yaml` descriptions + categories (categories cross-validated against the data → `docs/denue/CATEGORY_AUDIT.md`), generates `denue_schema_map.yaml`, validates every file against its group schema (`docs/denue/VALIDATION_REPORT.md`), derives/repairs point geometry against state boundaries (`docs/denue/GEOMETRY_REPORT.md`), appends to `registry.txt`. Modes: `--schema-map`, `--variables` (`--cat-threshold`), `--validate`, `--refilter-boundaries` (`--boundary-buffer-m`/`--boundaries-dir`/`--geometry-report`), `--report-only`, `--update-registry`, `--dry-run` |
| `scripts/upload_release.py` | **Maintainer-only** — resumable batch upload of the parquet mirror to the GitHub Release. Source of truth for "already uploaded" is the release itself (queried live via `gh release view`), so it survives multi-day / partial uploads. Batches derived from `registry.txt`: `core_denue` (latest DENUE), `core_census` (iter/resargebub/personas/viviendas), `core_mg` (the 4 MG layers `load_mg_census` fetches), `mg-rest` (other 11 MG layers), one `denue-<id>` per older release. Subcommands: `status` (`--write-doc`), `list <batch>`, `upload <batch…>` or `--next` (`--clobber`/`--chunk N`/`--dry-run`) |

### YAML schemas (`_yaml/`)

- `variables_personas.yaml` / `variables_viviendas.yaml` – microdata variable names, descriptions, and value→label category mappings (generated by `utils.get_cats_from_excel` from INEGI's Excel dictionaries)
- `variables_iter.yaml` / `variables_resargebub.yaml` – aggregate-dataset indicator dictionaries: `Indicador`/`Descripción`/`Rangos`/`Longitud` per mnemonic, no category maps (generated by `utils.get_vars_from_indicator_csv` from the `diccionario_datos_*.csv` inside the INEGI ZIPs; national, one copy per dataset)
- `constraints_personas.yaml` / `constraints_viviendas.yaml` – valid variable combinations for crosstab generation
- `denue_schema_map.yaml` – DENUE column-fingerprint → schema group (g01..g11), group→columns, and `latest` (harmonization target); `variables_denue_<gNN>.yaml` – per-group DENUE variable dictionaries (`Descripción`/`Tipo`/`Longitud` from the release dictionaries; `Categorías` code→label maps for coded fields + data-enumerated categoricals — drives `_group_schema`; generated by `scripts/build_denue.py`)

`_resources.py` loads these once via `@functools.cache` and exposes them as `variables_*()` / `constraints_*()` / `variables_denue(gid)` / `denue_schema_map()`.

### Census data hierarchy

ITER and RESARGEBUB data follow: State → Municipality → Locality → AGEB → Block (MZA). Each level uses a different row in the raw file; `load_iter()` and `load_resargebub()` accept `.parquet` or `.csv` paths and split rows into level-specific DataFrames with appropriate multi-indices.

### Censored values

INEGI encodes suppressed counts as `*` (meaning 0, 1, or 2 persons). The parquet mirror preserves these as string values in object-dtype columns. `aggregate.py` maps them to masked `Int64` values and imputes zeros where parent-level totals confirm the suppressed value must be 0.

### Extended microdata preprocessing

Multi-response fields (health insurance categories, transport modes) are expanded into binary dummy columns then reduced to summary flags. The full preprocessing pipeline always runs at load time (no separate caching step). All output is validated with Pandera `DataFrameModel` schemas.

### Parquet mirror and registry

Raw INEGI data is pre-converted to parquet and hosted on a GitHub Release (`data-v0.1.0` under `CentroFuturoCiudades/mxcensus`, see `data/_registry.py`). The registry file (`src/mxcensus/data/registry.txt`) maps filenames to SHA256 hashes and is committed to the repo after each data release.

> **Pending:** fetches resolve to the release URL, but the assets must actually be uploaded there (`gh release upload data-v0.1.0 …`). Until then `POOCH.fetch` / `load_census(state=…)` return 404.

File naming convention:
```
# Census tabular data (128 files) — scripts/build_data.py
iter_{NN}.parquet          # raw ITER for state NN
resargebub_{NN}.parquet    # raw RESARGEBUB for state NN
personas_{NN}.parquet      # raw Personas for state NN
viviendas_{NN}.parquet     # raw Viviendas for state NN

# Marco Geoestadístico geometries (15 layers × 32 states = 480 geoparquet) — scripts/build_marco_geo.py
mg_{suffix}_{NN}.parquet   # suffix ∈ {a,ar,cd,e,ent,fm,l,lpr,m,mun,pe,pem,sia,sil,sip}

# DENUE economic units (24 releases × 32 states = 768 geoparquet, points) — scripts/build_denue.py
denue_{YYYYMM}_{NN}.parquet   # YYYYMM = release id (e.g. 202505); EPSG:4326
```
Registry totals: 128 census + 480 geo + 768 DENUE = **1376** entries.

To rebuild the **census** mirror after an INEGI data update:
```bash
python scripts/build_data.py --states 9   # smoke test one state first
python scripts/build_data.py              # full build
# Then upload data/parquet/ to the GitHub Release and commit registry.txt
```

To (re)build the **Marco Geoestadístico** geoparquet from a local gpkg copy:
```bash
python scripts/build_marco_geo.py --states 1   # smoke test
python scripts/build_marco_geo.py              # all 32 states, all 15 layers
# Appends mg_* entries to registry.txt (preserving census entries); then
# gh release upload data-v0.1.0 data/parquet/mg_*.parquet --clobber
```

To (re)build the **DENUE** mirror (downloads from INEGI):
```bash
python scripts/build_denue.py --dry-run --release 202505 --states 9   # smoke test
python scripts/build_denue.py                       # all 24 releases × 32 states (~11 GB)
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

### DENUE (multi-temporal economic units)

DENUE drifts across its 24 releases (2010–2025): schemas change, files can be malformed
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

### Cache directory

Resolved by `platformdirs` in priority order:
1. `$MXCENSUS_CACHE_DIR` env var
2. `~/Library/Caches/mxcensus` (macOS)
3. `~/.cache/mxcensus` (Linux/XDG)

`mxcensus info` shows the resolved path. The `POOCH` object in `mxcensus.data` can be used directly for advanced access.
