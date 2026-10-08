# CPV family — session handoff

**Status (2026-10-07): units 0, 1a, 1b, 1c and 1d are done; next is unit 1e (registry,
upload, CLI, docs — the release of EIC 2025).** Design: [`PLAN.md`](PLAN.md) (unit table and
session protocol at the top). What 1d built and found: [`STEP_1d.md`](STEP_1d.md); earlier
units: [`STEP_1c.md`](STEP_1c.md), [`STEP_1b.md`](STEP_1b.md), [`STEP_1a.md`](STEP_1a.md),
[`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, pushed to `origin`. `wsl:~/mxcensus` is on the branch and holds
the full EIC 2025 mirror: 97 `cpv_*_2025*` files, 493 `mg_*_2025_*` files (480 + `ti` for
13 island states) and the 13 new 2020 `mg_ti_NN` files. **None of them is in
`registry.txt` yet.** The Mac has `cpv` states 01, 09, 15 + estimaciones, MG 2025 state 01
and the 2020 `mg_ti_NN`. Check `git status` / `git log --oneline -5` on both hosts first,
and `git pull --ff-only` wherever you are behind.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (1e: registry + HF upload + clean-cache fetch, the
> `--dataset cpv/mg --edition` CLI, README/CLAUDE.md/hf_bucket_readme/pyproject, version
> bump) following the session protocol at the top of PLAN.md. Use .venv/bin/python, not
> uv run. Run wsl tasks without asking; ask me before committing, pushing, installing
> packages or uploading. When the unit's gate is met, write docs/cpv/STEP_1e.md, tick the unit
> table, rewrite HANDOFF.md for unit 2a, update the memory note, ask me before
> committing, and give me the next handoff prompt.

## Next unit — 1e: registry, upload, CLI, docs (EIC 2025 release)

Gate: a clean-cache `POOCH.fetch` of a `cpv_` file and an `mg_*_2025_` file from the HF
bucket, with the registry committed.

1. **Read first**: `PLAN.md` Phase 1 steps 5–6 and the 1e row; `STEP_1d.md` §User
   decisions; `src/mxcensus/_cli.py` (`SELECTOR_FLAGS`, `NATIONAL_DATASETS`);
   `scripts/upload_hf.py`; `docs/hf_bucket_readme.md`; `tests/test_cli.py`.
2. **Registry on `wsl`**. After `git pull --ff-only`:
   ```bash
   .venv/bin/python scripts/build_cpv.py --update-registry                             # +97
   .venv/bin/python scripts/build_marco_geo.py --period 2025 --update-registry         # +493
   .venv/bin/python scripts/build_marco_geo.py --period 2020 --layers ti --update-registry  # +13
   ```
   - Pass `--layers ti` for 2020: without it, the mode rehashes all 480 legacy files.
     Their hashes should be identical, but nothing needs rehashing.
   - Expected total: 1932 + 97 + 493 + 13 = **2535** entries.
   - `git diff src/mxcensus/data/registry.txt` must show additions only. Commit it on
     `wsl` (ask the user first), push, and pull on the Mac.
3. **Upload on `wsl`** (ask the user first):
   - `python scripts/upload_hf.py upload`. Never pass `--delete`.
   - Update `docs/hf_bucket_readme.md` first: it is uploaded as the bucket README.
   - Run `upload_hf.py verify` in the background; it HEADs ~2.5k URLs, >10 min.
4. **Gate, on the Mac** (the env var must be set before `mxcensus` is imported):
   ```bash
   MXCENSUS_CACHE_DIR=$(mktemp -d) .venv/bin/python -c "from mxcensus.data import POOCH; \
     print(POOCH.fetch('cpv_personas_2025_01.parquet'), POOCH.fetch('mg_mun_2025_01.parquet'))"
   ```
   Also run `load_cpv_survey(state=1)` and `load_mg('mun', state=1, period=2025)`
   unpatched in that clean cache.
5. **CLI** (`_cli.py` + `tests/test_cli.py`):
   - `SELECTOR_FLAGS["edition"]` gains `cpv` and `mg`.
   - `--dataset cpv --edition YYYY` fetches the state's microdata tables of that edition
     (`cpv_filename`); decide whether it also fetches the national `estimaciones`.
   - `--dataset mg --edition YYYY` fetches every `MG_LAYERS` file of the state that is in
     `POOCH.registry`, so `ti` is fetched only for island states. Default edition: decide
     between 2020 (as `load_mg`) and the latest.
   - Neither dataset is in `NATIONAL_DATASETS`, so `STATE` stays required.
6. **Docs**:
   - README: a `### Census & intercensal (multi-year)` section, plus `load_mg`; generalise
     the "2020 Census" title.
   - CLAUDE.md:
     - registry totals and file-naming block (`cpv_*`, `mg_{sfx}_{period}_{NN}`, `ti`);
     - module rows for `cpv.py`, `cpv_aggregates.py`, `mg.py` and `_cpv_catalog.py`
       (`_catalog.MG_LAYERS`);
     - the MG section (16 layers, the CRS note);
     - the CLI row.
   - `pyproject.toml`: generalise the description and bump the version (0.4.0 → 0.5.0?
     ask).
7. Optional: once the registry has them, drop the `local_mirror` monkeypatch from the
   `_REAL` tests in `test_cpv.py`/`test_mg.py`, or keep it so the tests stay offline.
   Decide and record.

## Open questions for the user

- The version number for the release (0.5.0?).
- `--dataset cpv` and the national `estimaciones` file; the default `--edition` for `mg`.
- Commits, pushes and uploads: ask before each (the user's standing instruction for this
  family). Since 1d, wsl runs need no permission.

## Gotchas (carry forward)

- **Metadata modes run on `wsl` only.** `build_cpv.py --schema-map`/`--variables`/
  `--report-only` on the Mac's 3-state mirror would overwrite the committed 32-state map and
  report.
- **Until 1e, the registry has no `cpv_` or `mg_*_2025_` entries**, and no 2020 `mg_ti_`
  entries either. `POOCH.fetch` of them fails outside the tests' `local_mirror` fixtures.
- **MG CRS**: INEGI mixes two spellings of one LCC projection within each edition. The
  mirror keeps them, and `load_mg` returns EPSG:6372 by default, losslessly
  (`STEP_1d.md`). `aggregate.load_mg_census` (2020) is unaffected: its four layers share
  one spelling.
- **`ti`** exists only for island states. `load_mg("ti", state=1)` raises a clear
  `ValueError`.
- **`_schema_groups.label_frame` changed in 1c** (all families): a missing label is `NaN`
  in a `Categorical`, no longer `None` in an object column.
- **EIC 2025 coverage**: 750 municipalities censados, 1,721 muestreados and 7 with
  insufficient sample; `mg_mun_2025` has exactly those 2,478.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac.
- `variables_cpv_core.yaml` is hand-curated: never regenerate it. After editing it, rerun
  `--variables` on `wsl`.
- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes). Rely on ZIP integrity.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (Mac: CPython 3.14.8 with
  `dev` + `notebook`). Both hosts run pyarrow 24.0.0 / pandas 3.0.3 / geopandas 1.1.3 /
  pyproj 3.7.2 (PROJ 9.5.1).
- With Tailscale SSH, `ssh wsl 'nohup … &'` does not return until the job ends. Launch long
  jobs with the Bash tool's `run_in_background`.
- Never `upload_hf.py --delete` from a partial local mirror. Full builds and uploads run on
  `wsl`.
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen
  2020 path, pinned by `tests/test_census_legacy.py`.
