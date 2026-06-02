# DENUE mirror — Steps 5 & 6: wiring, registry, docs, tests

Status: **done** (2026-06-02). Remaining: maintainer upload (~11 GB) to the release.

## Step 5 — registry + package wiring
- **`registry.txt` append:** `build_denue.py --update-registry` upserted **768 `denue_*`**
  entries via the shared `_build_common.update_registry`, preserving the 128 census + 480
  geo entries → **1376 total**. (The guard asserts no prior-prefix entry is lost.)
- **`__init__.py`:** exports `load_denue`, `variables_denue`, `denue_schema_map`.
- **`_cli.py`:** `fetch --dataset denue [--release YYYYMM]` (defaults to latest release).
- **Shared helpers:** `build_marco_geo.py` now imports `_build_common` (dropped its local
  `_update_registry`/`_CENSUS_PREFIXES`). `build_data.py` left as-is (works, pre-dates the
  shared module; refactor optional). `_build_common.PRESERVE_PREFIXES` covers
  iter/resargebub/personas/viviendas/mg/denue.

## Step 6 — docs + tests
- **`tests/test_denue.py`** — 28 tests, all pass (`uv run --with pytest pytest`). CI-safe:
  exercises harmonization/grouping/`per_ocu` remaps + Pandera against the bundled
  `denue_schema_map.yaml` only (no network, no mirrored parquet). Covers all 11 groups
  (harmonize→g10, fingerprint round-trip), uppercase + numeric-code `per_ocu` remaps,
  schema validation, and the exports.
- **Docs:** CLAUDE.md (module table, mirror/registry, a DENUE section, `_yaml` list) and
  README (datasets row, usage, attribution `Fuente: INEGI, DENUE`, transformation notice).

## Maintainer step still pending (Step 6 tail)
Upload the assets to the `data-v0.1.0` release (everything 404s until then — census, geo,
and DENUE all need uploading):
```bash
gh release upload data-v0.1.0 data/parquet/denue_*.parquet --clobber   # ~11 GB, 768 files
```
Then commit: `registry.txt` (now 1376 entries), `denue_schema_map.yaml`,
`variables_denue_g01..g11.yaml`, `src/mxcensus/denue.py`, `scripts/_build_common.py`,
`scripts/build_denue.py`, `src/mxcensus/data/_denue_catalog.py`, the wiring edits, the
`docs/denue/` records, and `tests/test_denue.py`.

## Post-review hardening (2026-06-02)

A full code review of the DENUE paths (logic verified against the on-disk 768-file
mirror: every schema group loads → harmonizes → validates) produced these changes:

- **Stale-rename guard** (`denue.py` `_harmonize`): warns if an explicit `_RENAME`
  target never materializes (its source column is absent) — previously masked as an
  all-null column by the `add_null` pass. Promoted to an error in the real-data tests.
- **`codigo_act` validated** as `^\d{4,6}$` (SCIAN) in `_latest_schema`; **CRS asserted**
  EPSG:4326 in `load_denue` (both raw and harmonized paths).
- **Real-data tests**: `tests/test_denue.py` now loads one real file per group when a
  local mirror exists (skipped in CI) — covers `per_ocu` value drift and the rename
  guard, which the synthetic-frame tests can't.
- **Report §7** (`build_denue.py`): per-group all-null columns. Surfaces g04 (2012 typo
  variant, states 12/14) shipping empty `Entidad federativa`/`Municipio`/`Localidad`/
  name fields with only codes populated — faithful to source, not a defect. Also fixed
  the report's group map to be **per-file** (was per-release-canonical, which hid
  minority within-release schemas like g04) so §2 now matches the 11 yaml groups.
- **Docs/CLI**: CLAUDE.md notes the harmonization spec is g10-pinned; `mxcensus fetch`
  rejects `--release` for non-DENUE datasets; encoding/dedup-determinism caveats commented.

## DENUE implementation: complete
All six steps done. `load_denue(state=N)` returns any of the 24 releases harmonized to the
latest 42-column schema (or raw via `harmonize=False`); inconsistencies are detected and
reported; per-group schemas + variable dictionaries are bundled. Only the binary upload
(maintainer) remains before end users can fetch over the network.
