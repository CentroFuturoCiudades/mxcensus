# CPV family — session handoff

**Status (2026-10-07): units 0, 1a–1e and 2a are complete.**
- The Encuesta Intercensal 2025 is released: registered, uploaded and fetchable.
- **CPV 2020 is built and validated but not yet registered or uploaded:** 160
  `cpv_{viviendas,personas,migrantes,iter,ageb}_2020_NN` files on `wsl`, `--validate` 0/257.
- **Next is unit 2b**: 2020↔2025 core harmonization, the legacy-equality tests, then registry
  and upload.

Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at the top). What 2a did:
[`STEP_2a.md`](STEP_2a.md). Earlier units:
[`STEP_1e.md`](STEP_1e.md) (registry, upload, CLI), [`STEP_1d.md`](STEP_1d.md) (MG 2025,
`load_mg`), [`STEP_1c.md`](STEP_1c.md) (loaders), [`STEP_1b.md`](STEP_1b.md) (dictionaries),
[`STEP_1a.md`](STEP_1a.md) (build), [`STEP_0_probe.md`](STEP_0_probe.md) (URLs, members,
editions).

Branch: `cpv-integration`. It is **not merged into `main`** and has no `v0.5.0` tag; see the
open questions. The package version is 0.5.0. The registry has **2535 entries**, none of
them CPV 2020.

**Host state.**
- `wsl:~/mxcensus` holds the full mirror (EIC 2025 + CPV 2020 + everything else) and the
  logs (`build_cpv_2020.log`).
- The Mac has CPV 2020 state 01 only, and EIC 2025 states 01/09/15 plus the estimaciones.
- **wsl's working tree is dirty from 2a**: the code was `scp`'d there and the metadata
  generated there, with no commit. Once the 2a commit is pushed, clean it and pull:

  ```bash
  git checkout -- .
  rm src/mxcensus/_yaml/variables_cpv_{viviendas,personas,migrantes}_g02.yaml \
     src/mxcensus/_yaml/variables_cpv_{iter,ageb}_g01.yaml
  git pull --ff-only
  ```

  Then check `git status` / `git log --oneline -5` on both hosts.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (2b: 2020↔2025 core harmonization — ENT/MUN→CVE_ENT/CVE_MUN
> in the microdata, table-scoped ITER/AGEB geography; raw-vs-harmonized totals and the
> legacy-equality tests; then registry +160 and upload of the CPV 2020 files) following
> the session protocol at the top of PLAN.md. Use .venv/bin/python, not uv run. Run wsl
> tasks without asking; ask me before committing, pushing, installing packages or
> uploading. When the unit's gate is met, write docs/cpv/STEP_2b.md, tick the unit table,
> rewrite HANDOFF.md for unit 3a, update the memory note, ask me before committing, and
> give me the next handoff prompt.

## Next unit — 2b: harmonization, legacy equality, upload

Gate: Σ `FACTOR` and row counts are identical raw vs harmonized (2020 and 2025); the 2020
files equal the legacy ones; the 160 files are registered (additions only), uploaded and
verified.

1. **Read first**:
   - `PLAN.md` §Harmonization and Phase 2;
   - `STEP_2a.md` §Findings for 2b;
   - in `src/mxcensus/cpv.py`: `_harmonize`, `_RENAME_CORE`, `_GEO_PAD`/`_GEO_PARTS`,
     `_required`, `_latest_schema`, `_labels_for`, `_core_for`/`_in_scope`.
2. **Microdata harmonization**:
   - Add `ENT→CVE_ENT` and `MUN→CVE_MUN` to `_RENAME_CORE`. 2020 has no `CVEGEO`, so
     `_harmonize` derives it (5 digits).
   - Today a 2020 frame with `harmonize=True` warns "lacks core column(s) ['CVE_ENT']"; it
     must not after this.
   - `ID_PER`/`ID_MIN`/`TAM_LOC` are 2010 spellings (3b), not needed yet.
   - Check that `load_cpv_personas(state=[...], period=…)` mixing editions is not a thing:
     editions load one at a time; mixing 2020 + 2025 means two calls plus a concat of
     harmonized frames. Decide whether to offer more.
3. **Aggregate geography is table-scoped**:
   - ITER/AGEB spell `ENTIDAD`/`MUN`/`LOC` (+ `AGEB`/`MZA`); `ENTIDAD→CVE_ENT` and
     `LOC→CVE_LOC` apply only there.
   - `_RENAME_CORE` is flat today; add a per-table map or a `Tablas`-style scope (mirroring
     the core's `Tablas`).
   - Decide the ITER/AGEB `CVEGEO`: ENT+MUN+LOC (9 digits, as the estimaciones) and, for
     AGEB, whether to add `AGEB`/`MZA` (13/16). It may be simpler to leave the aggregates'
     harmonization to 3c (`load_cpv_iter`/`load_cpv_ageb`) and only make `_required` not
     warn for them. Record the choice.
4. **Cross-edition labels**:
   - `_labels_for` drops any column whose entries differ between the stacked groups, and it
     compares whole entries. Between 2020 and 2025, 48/74 viviendas, 52/83 personas and
     12/24 migrantes shared columns differ somewhere, mostly in `Descripción`/`Pregunta`.
     Only 7/22/5 differ in label-relevant keys (`Tipo`, `Categorías`, `Especiales`,
     `Rango`, `Ordenada`, `Alias`, `Decimales`).
   - Comparing only those keys is the likely fix; it matters only when one call stacks
     several groups (`harmonize=True`).
5. **Tests** (`tests/test_cpv.py`):
   - raw vs harmonized: same rows and Σ `FACTOR`, 2020 and 2025, `_REAL` state 01;
   - **legacy equality**: `cpv_{viviendas,personas}_2020_NN` equal the legacy
     `viviendas_NN`/`personas_NN` (inferred dtypes) after numeric casting. 2a found this
     true on state 01. `_REAL` on the local states; all 32 on `wsl`.
   - ITER/AGEB vs `iter_NN`/`resargebub_NN` (the legacy keeps `*` as strings in object
     columns);
   - `test_census_legacy.py` must stay green (frozen path).
6. **Registry and upload (`wsl`, ask before uploading)**:
   - `build_cpv.py --update-registry`: 2535 → **2695**. The diff must be additions only
     (`git diff --stat`; `STEP_1e.md` has the check).
   - Dry-run with `hf buckets sync … --dry-run` (`export PATH=$HOME/.local/bin:$PATH`), then
     `upload_hf.py upload` (never `--delete`), then `upload_hf.py verify` in the background
     (>10 min).
   - Clean-cache `POOCH.fetch("cpv_personas_2020_01.parquet")`, then
     `mxcensus fetch 1 --dataset cpv --edition 2020`. The CLI offers every registered 2020
     table, ITER/AGEB included, with no code change.
7. **Docs**:
   - README: the `cpv` section and the table row (CPV 2020 now in the family, a fetch
     example).
   - CLAUDE.md counts: registry 2695; the CPV family has 257 files.
   - `docs/hf_bucket_readme.md`.
   - Ask about a version bump (0.5.0 → 0.6.0?).

## Open questions for the user

- **Dictionary source for 2020**: the handoff said "RNM DDI if one exists". DDI 632 exists,
  but its value labels are incomplete (see the table in `STEP_2a.md`), so 2a built from the
  FD xlsx and only records `ddi_id=632`. Confirm or overrule.
- **Release mechanics**: merge `cpv-integration` into `main` and tag now, or after 2b's
  upload?
- **Version bump** with 2b (CPV 2020 becomes fetchable)?
- Commits, pushes and uploads: ask before each (the user's standing instruction for this
  family). wsl runs need no permission.

## Gotchas (carry forward)

- **CPV gids are chronological**: 2020 = `g01` and 2025 = `g02` for viviendas/personas/
  migrantes. Code and tests take gids from `cpv_schema_map()` (`latest` is the newest
  edition's group); never hard-code `g01`. The README examples use `g02`. A new edition
  (2015, 2010) slots in by year and shifts later gids again.
- **Core scope**: a core entry with `Tablas` applies only to those tables (`_in_scope`). It
  is used by `--variables`, `variables_cpv_labels` and `_latest_schema`. `TAMLOC` is
  microdata-only: the ITER's is 14 classes, unpadded, with `*` on total rows.
- **Aggregate sentinels**: `build_cpv._AGG_SPECIALS["2020"]` = `*`/`N/D`/`N/A`, because the
  2020 indicator dictionaries have no footnotes. A later edition with footnoteless
  dictionaries needs its own entry.
- **`_dict_fd`** now handles the 2020 FD quirks: brace-wrapped and multi-code cells,
  wrapped catalog notes, catalog-note rows, abbreviated stems, cp1252 catalogs with `NOM_*`
  label columns, and the `0.,.999999999` range typo. The 2025 parse was proven
  byte-identical; re-check that whenever `_dict_fd` changes.
- **`ageb_14` (2020) is cp1252**; the other 159 files are UTF-8. The sniff handles it.
- **Metadata modes run on `wsl` only.** `--schema-map`, `--variables` and `--report-only`
  on the Mac's partial mirror would overwrite the committed 32-state map and report.
- **The CLI offers only registered files** (`POOCH.registry`). Unregistered files are
  readable through the tests' `local_mirror` fixtures.
- **`--update-registry` modes**: `build_cpv.py --update-registry`,
  `build_marco_geo.py --period P --update-registry` (pass `--layers` to limit it). The
  registry diff must be additions only.
- **Upload**: `upload_hf.py upload` from `wsl` only, never with `--delete`. Dry-run first;
  `verify` HEADs every registry URL (~2.7k), so run it in the background. `upload` also
  pushes `docs/hf_bucket_readme.md` as the bucket README.
- **INEGI downloads** drop connections and truncate ZIPs; `fetch_zip_verified` retries
  (raise `--retries`). The 2020 ZIPs are all cached on `wsl` (738 MB).
- **MG CRS**: two spellings of one LCC projection; `load_mg` returns EPSG:6372 losslessly.
  `ti` exists only for the 13 island states.
- **`mxcensus.__version__`** reads installed metadata (the Mac's dev venv may lag).
- **`_schema_groups.label_frame`** (since 1c): a missing label is `NaN` in a
  `Categorical`.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac for EIC 2025. The
  2020 CA sample is smaller per state (15: 1.23 M persons vs 2.30 M).
- **`variables_cpv_core.yaml` is hand-curated**: never regenerate it. After editing it,
  rerun `--variables` on `wsl`.
- **INEGI soft-404s** come back as HTTP 200 + `text/html`; rely on ZIP integrity.
- **`uv run`** may re-sync `.venv`; use `.venv/bin/python`. Both hosts run pyarrow 24.0.0 /
  pandas 3.0.3, and the builds are byte-identical across them (re-checked on the 2020
  state-01 files).
- **Long jobs on `wsl`**: with Tailscale SSH, `ssh wsl 'nohup … &'` does not return until
  the job ends. Use the Bash tool's `run_in_background`.
- **Frozen legacy path**: `scripts/build_data.py`, `aggregate.py`, `extended_*.py` and the
  legacy files are pinned by `tests/test_census_legacy.py`.
