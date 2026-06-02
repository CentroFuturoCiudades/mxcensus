# DENUE mirror — Step 4: loader + harmonization

Status: **done** (2026-06-02)

## Goal
`load_denue()` that fetches a mirrored release/state and optionally harmonizes it to the
latest schema (g10) so all 24 releases are longitudinally comparable, validated with
Pandera. (Option A — full harmonization of all 11 groups.)

## Delivered (`src/mxcensus/denue.py`)
- **`load_denue(survey_path=None, *, state=None, release=None, harmonize=True)`** — two
  conventions: `state=` fetches `denue_{release|latest}_{NN}.parquet` via Pooch (mirrors
  `load_census`), or an explicit `survey_path`. Returns a GeoDataFrame (points, EPSG:4326).
- **`_harmonize(gdf, gid, latest_cols)`** — maps any group onto g10's 42 columns:
  - explicit raw→mnemonic renames for the descriptive groups g01–g07 (`_RENAME`);
  - case-insensitive auto-match for the mnemonic/UPPERCASE groups (g08–g11) → exact g10 casing;
  - unmapped columns dropped (NIC/NOP, extra phones/fax, status flags, duplicate code cols);
  - latest-only columns added as null (`clee` for pre-2021);
  - reordered to g10 + geometry.
- **`per_ocu` canonicalization** (`_PER_OCU`): the source column and encoding differ by era —
  2010–2011 UPPERCASE labels, 2012/2013-Oct **numeric codes** (read from the reliably-populated
  code column, since the label column is empty for some states e.g. 2012/12,14), 2013-Jul/2015
  label column, 2016+ mnemonic. All map to the canonical 7 strata + `No especificado`.
- **Pandera schema** (`_latest_schema`, applied when `harmonize=True`): 42 columns as nullable
  strings, `per_ocu` constrained to the canonical set, `strict=False` (ignores geometry).
- **`_resources.py`**: added `denue_schema_map()` and `variables_denue(schema_id)` accessors.

## Verified
All 11 groups, one representative file each:
- harmonize=True → identical 42-col g10 schema + geometry, EPSG:4326, Pandera passes;
- `per_ocu` canonical across every era (union = 7 strata + `No especificado`);
- g04 (2012 states 12/14, empty label column) → per_ocu recovered from the **code** column;
- harmonize=False → the release's raw columns (no transformation).

## Notes / decisions
- Harmonization spec lives in `denue.py` as auditable Python dicts (the descriptive→mnemonic
  maps + per_ocu source/value tables) rather than YAML — the maps encode semantic judgments
  (e.g. 2010's `Calle, avenida…`→`nom_vial`, `Tipo de unidad económica`/`Tipo de establecimiento`
  →`tipoUniEco`) better kept with the code that applies them.
- Anomalous 2012 per_ocu code `13` → `No especificado`.
- Some 2010-era latest-only columns (`clee`, `tipo_vial`, `letra_ext`, `cve_*`, `fecha_alta`, …)
  are null after harmonization — expected (the data didn't exist then).

## Next — Step 5
Registry append (`_build_common.update_registry` over the 768 `denue_*` parquet, preserving
census+geo entries) + package wiring (`__init__.py` export `load_denue`/`variables_denue`/
`denue_schema_map`; `_cli.py` `--dataset denue`; refactor `build_data.py`/`build_marco_geo.py`
to import the shared `_build_common` helpers). Upload (~11 GB) to the `data-v0.1.0` release is
the maintainer step (Step 6).
