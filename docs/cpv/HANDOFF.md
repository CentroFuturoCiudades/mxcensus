# CPV family — session handoff

**Status (2026-10-07): Phase 1 is done. Units 0 and 1a–1e are complete, and the Encuesta
Intercensal 2025 is released (registered, uploaded, fetchable). Next is unit 2a: CPV 2020
into the family.** Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at the
top). What 1e did: [`STEP_1e.md`](STEP_1e.md). Earlier units:
[`STEP_1d.md`](STEP_1d.md) (MG 2025, `load_mg`), [`STEP_1c.md`](STEP_1c.md) (loaders),
[`STEP_1b.md`](STEP_1b.md) (dictionaries), [`STEP_1a.md`](STEP_1a.md) (build),
[`STEP_0_probe.md`](STEP_0_probe.md) (URLs, members, editions).

Branch: `cpv-integration`, pushed to `origin`. It is **not merged into `main`** and has no
`v0.5.0` tag; see the open questions. The package version is 0.5.0.

The registry has **2535 entries**: 97 `cpv_*_2025*`, 493 `mg_*_2025_*` and 13 new 2020
`mg_ti_NN`, all uploaded to the HF bucket and verified. `wsl:~/mxcensus` holds the full mirror
and the build logs. The Mac has `cpv` states 01, 09 and 15 plus estimaciones, MG 2025 state
01, and the 2020 `mg_ti_NN`. Check `git status` / `git log --oneline -5` on both hosts first,
and `git pull --ff-only` wherever you are behind.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (2a: CPV 2020 into the family — viviendas/personas/migrantes,
> iter and ageb as cpv_*_2020_NN; the 2020 dictionary, RNM DDI if one exists else the FD
> xlsx; --validate 0 failures) following the session protocol at the top of PLAN.md. Use
> .venv/bin/python, not uv run. Run wsl tasks without asking; ask me before committing,
> pushing, installing packages or uploading. When the unit's gate is met, write
> docs/cpv/STEP_2a.md, tick the unit table, rewrite HANDOFF.md for unit 2b, update the
> memory note, ask me before committing, and give me the next handoff prompt.

## Next unit — 2a: CPV 2020 into the family

Gate: `build_cpv.py --validate` reports **0 failures** over the full 2020 + 2025 mirror on
`wsl`.

1. **Read first**:
   - `PLAN.md` Phase 2 and the 2a/2b rows;
   - `STEP_0_probe.md`: the 2020 rows of the microdata/aggregate tables and the
     dictionaries table (`diccionario_cuestionario_ampliado_cpv2020.xlsx`,
     `Censo2020_clasificaciones_CPV_csv.zip`, "RNM DDI not located — probe at 2a");
   - `STEP_1a.md` (build pipeline, pyarrow reader, memory) and `STEP_1b.md` (FD
     dictionaries, `_dict_fd`, core YAML, `--cat-threshold`);
   - the 2020 `CpvEdition` in `data/_cpv_catalog.py` (URLs, member regexes, the
     `Censo2020_CA_{abbr}_csv.zip` naming), and `_ENABLED` in `scripts/build_cpv.py`.
2. **Dictionary probe.** Search the RNM for a CPV 2020 DDI (`…/rnm/index.php/api/catalog/
   search?ps=200&page=N`, filter idno locally; see the memory note on the RNM). If one
   exists, set `CpvEdition.ddi_id` and use `_dict_ddi`. If not, use the FD xlsx through
   `_dict_fd.parse_fd_xlsx`; its layout may differ from 2025's, so check the sheets and
   columns first. ITER/AGEB use their bundled `diccionario_datos_*.csv`
   (`parse_indicator_csv`). Their non-numeric codes are `*` (censored 0–2) and `N/D`; check
   the footnotes and declare them as `Especiales`.
3. **Build.**
   - Add `"2020"` to `_ENABLED`, then `--dry-run --periods 2020 --states 1`.
   - Smoke-test state 01 on the Mac (`--periods 2020 --states 1`), then the full build on
     `wsl` (all 32 states × microdatos/iter/ageb), in the background with a log and
     `--retries` raised (INEGI dropped connections and truncated ZIPs in 1d).
   - Expect 32 × 5 = 160 files.
   - Raw names stay as INEGI spells them (e.g. `ENT`/`MUN` in 2020); the `ENT→CVE_ENT`
     harmonization is **2b**.
   - The legacy `iter_NN`/`personas_NN`/… files are not touched. The new files are separate
     `cpv_*_2020_NN`, faithful raw `str` (the legacy ones have inferred dtypes).
4. **Metadata on `wsl` only** (the Mac's partial mirror would overwrite the 32-state map),
   in order: `--dictionary`, `--schema-map`, `--report-only`, `--variables`, `--validate`.
   - The core (`variables_cpv_core.yaml`) is hand-curated. Extend it only for variables
     whose 2020 codes you have verified, then rerun `--variables`.
   - 2025's groups must stay unchanged (the gids are chronological, so expect the 2020
     groups to come **before** 2025's, and 2025's gids to shift). Check every
     consumer/test that hard-codes `g01`, e.g. `tests/test_cpv.py`, the README's
     `variables_cpv("personas", "g01")` and `STEP_1c` examples.
5. **Tests** (`tests/test_cpv.py`):
   - the catalog/build plan for 2020;
   - the schema-map parametrization picks up the 2020 groups automatically;
   - a `_REAL` 2020 state-01 load, raw and labelled.
   - Optional sanity check: row counts and Σ `FACTOR` of `cpv_personas_2020_01` equal the
     legacy `personas_01` (1,421,198 per `tests/test_census_legacy.py`). The full
     legacy-equality test is 2b.
6. **Registry/upload: not in 2a** (2b uploads). The CLI then offers `--dataset cpv --edition
   2020` automatically once the files are registered.

## Open questions for the user

- **Release mechanics**: merge `cpv-integration` into `main` and tag `v0.5.0` now (EIC 2025
  is complete), or keep the branch until CPV 2020 (2b)?
- Commits, pushes and uploads: ask before each (the user's standing instruction for this
  family). wsl runs need no permission.

## Gotchas (carry forward)

- **Metadata modes run on `wsl` only.** `build_cpv.py --schema-map`/`--variables`/
  `--report-only` on the Mac's partial mirror would overwrite the committed 32-state map and
  report.
- **The CLI offers only registered files** (`POOCH.registry`). Files built but not yet
  registered are invisible to it, but `load_*` can still read them through the tests'
  `local_mirror` fixtures.
- **`--update-registry` modes**: `build_cpv.py --update-registry`,
  `build_marco_geo.py --period P --update-registry` (pass `--layers` to limit it). The
  registry diff must be additions only (`STEP_1e.md`).
- **Upload**: `upload_hf.py upload` from `wsl` only, never with `--delete`. Dry-run first
  with `hf buckets sync … --dry-run` (`export PATH=$HOME/.local/bin:$PATH`). `verify` HEADs
  every registry URL (~2.5k, >10 min), so run it in the background. `upload` also pushes
  `docs/hf_bucket_readme.md` as the bucket README.
- **INEGI downloads** drop connections (`ChunkedEncodingError`/`SSLError`) and return
  truncated ZIPs. `fetch_zip_verified` retries; pass a higher `--retries` on long builds and
  rerun the remaining states if one gives up.
- **MG CRS**: INEGI mixes two spellings of one LCC projection, within each edition and even
  across states (2020 `fm`). The mirror keeps them; `load_mg` returns EPSG:6372 by default,
  losslessly (`STEP_1d.md`).
- **`ti`** exists only for the 13 island states (both frames).
- **`mxcensus.__version__`** reads the installed metadata: the Mac's dev venv reports 0.4.0
  until `uv pip install -e .` (ask before installing).
- **`_schema_groups.label_frame` changed in 1c** (all families): a missing label is `NaN`
  in a `Categorical`, no longer `None` in an object column.
- **EIC 2025 coverage**: 750 municipalities censados, 1,721 muestreados and 7 with
  insufficient sample; `mg_mun_2025` has exactly those 2,478.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac (EIC 2025). The
  2020 Cuestionario Ampliado sample is larger; check memory before loading big states.
- `variables_cpv_core.yaml` is hand-curated: never regenerate it. After editing it, rerun
  `--variables` on `wsl`.
- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes, or a "Página no encontrada" title).
  Rely on ZIP integrity.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (Mac: CPython 3.14.8 with
  `dev` + `notebook`). Both hosts run pyarrow 24.0.0 / pandas 3.0.3 / geopandas 1.1.3 /
  pyproj 3.7.2 (PROJ 9.5.1), and the builds reproduce byte for byte across them.
- With Tailscale SSH, `ssh wsl 'nohup … &'` does not return until the job ends. Launch long
  jobs with the Bash tool's `run_in_background`.
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen
  2020 path, pinned by `tests/test_census_legacy.py`.
