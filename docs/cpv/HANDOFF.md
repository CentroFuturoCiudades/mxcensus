# CPV family — session handoff

**Status (2026-10-07): units 0, 1a and 1b are done; next is unit 1c (loaders).** Design:
[`PLAN.md`](PLAN.md) (unit table and session protocol at the top). What 1b built and found:
[`STEP_1b.md`](STEP_1b.md); earlier units: [`STEP_1a.md`](STEP_1a.md),
[`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, pushed to `origin` (1b: `5316aad` code, `a69eb25` full-mirror
metadata from `wsl`, then a docs commit). `wsl:~/mxcensus` is checked out on it and holds the
full EIC 2025 mirror: 97 `cpv_*_2025*` files in `data/parquet` and the dictionaries in
`data/dict/fd/2025/`. The Mac has states 01, 09, 15 + estimaciones and the same dictionaries.
Check `git status` / `git log --oneline -5` on both hosts first, and `git pull --ff-only`
wherever you are behind.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (1c: loaders for EIC 2025 — load_cpv*, load_cpv_survey,
> load_cpv_estimaciones, exports, tests, EIC 2025 data checks) following the session
> protocol at the top of PLAN.md. Use .venv/bin/python, not uv run. Ask me before
> pushing, installing packages, or running anything on the wsl host. When the unit's gate
> is met, write docs/cpv/STEP_1c.md, tick the unit table, rewrite HANDOFF.md for unit 1d,
> update the memory note, ask me before committing, and give me the next handoff prompt.

## Next unit — 1c: loaders + tests + EIC 2025 data checks

Gate: `pytest -q` green, and the Σ `FACTOR` checks of `PLAN.md` §Verification recorded in
`STEP_1c.md` (exact or within LI–LS, per check).

1. **Read first**:
   - `PLAN.md` §Architecture → **Loaders** and **Keys**, and §Verification;
   - `src/mxcensus/enigh.py` as the pattern: `_load_enigh_raw`, `load_enigh`,
     `variables_enigh_labels`, `_finish_labelled`, `_index_level`, the `load_enigh_*`
     loaders, `load_enigh_survey`;
   - `src/mxcensus/cpv.py` (1b skeleton: `_WEIGHTS`, `_code_rule`, `_group_schema`,
     `_group_of`, `_validate`);
   - `STEP_1b.md` §"Findings for 1c".
2. **`src/mxcensus/cpv.py`**: add the loaders on the ENIGH pattern.
   - `load_cpv(survey_path=None, *, table, period=None, state=None, harmonize=False,
     labels=False)` returns the raw table.
   - `load_cpv_viviendas`/`load_cpv_personas`/`load_cpv_migrantes(period=None, *, state,
     harmonize=False, labels=True)` are analysis-ready: numeric `FACTOR`, the level index,
     labelled, validated strictly.
   - `load_cpv_survey(period=None, *, state, …)` → `(viviendas, personas, migrantes | None)`
     with the shared nested index.
   - `variables_cpv_labels(table, gid)`: per-group overlaid by core, keyed by raw and
     harmonized names.
   - **`state`**: `int | Sequence[int] | None`.
     - Per-state tables: `None` raises. A sequence concatenates, and must fall in one group
       unless `harmonize=True`.
     - National tables: `state` filters on `CVE_ENT`.
   - **Keys**: `_DWELLING = [("ID_VIV",)]`, `_PERSON = _DWELLING + [("ID_PERSONA", "ID_PER")]`,
     `_MIGRANT = _DWELLING + [("ID_MII", "ID_MIN")]` (a sibling of persons). `skip=` takes the
     keys plus the geography codes (`CVEGEO`, `CVE_ENT`, `CVE_MUN`, `LOC50K`, `CVE_LOC`), so
     they stay joinable strings.
   - **`harmonize`**: for 2025 it is the identity plus the checks (uppercase names, zero-pad
     `CVE_ENT`/`CVE_MUN`/`LOC50K`, check `CVEGEO == CVE_ENT+CVE_MUN`, numeric `FACTOR`).
     Write it generically (`PLAN.md` §Harmonization) so 2a only adds renames.
     `_latest_schema(table)` comes from the core.
3. **Decide (record in `STEP_1c.md`)**:
   - Person-number pointers (`NUMPER`, `IDENT_*`, `DUE*_NUM`, `MPER`, `MPERLS`): label them
     (53–56 identity categories) or put them in `skip=`. Recommended: `skip=`; they are
     intra-dwelling references.
   - Year fields: `FECHA_NAC_A` is numeric, but `MFECEMIA`/`MFECRETA` are 6-code
     categoricals. Either leave them or add numeric core entries for the two migrant years.
   - The optional migrant → person link via (`ID_VIV`, `MPERLS` = `NUMPER`): 652/652 in state
     01. It could be a documented join rather than an index level.
4. **`src/mxcensus/cpv_aggregates.py`**: `load_cpv_estimaciones(period="2025", *,
   estimador="valor", nivel=None, state=None)`.
   - One row per geography and one column per indicator, indexed `(CVE_ENT, CVE_MUN,
     CVE_LOC)`.
   - An ordered `NIVEL` column: `nacional | estatal | municipal | resto_estatal` (`997`/`9997`)
     `| localidad`.
   - `ESTIMADOR` → `valor|ee|li|ls|cv`. A list or `None` keeps it as the last index level.
   - Labelled cells: `NA`/`MI` → NA, `Decimales` → Float64.
5. **Exports**: `__init__.py` gets the loaders, `variables_cpv_labels`, and the `_resources`
   accessors (`cpv_schema_map`, `variables_cpv`, `variables_cpv_core`, already written in 1b).
6. **CLI** (`--dataset cpv --edition YYYY`; `SELECTOR_FLAGS["edition"]` gains `cpv`). The
   registry has **no `cpv_` entries until 1e**, so `mxcensus fetch` of a cpv file fails
   until then. Either add the CLI now with a parse-only test, or move it to 1e; record which.
   `PLAN.md` wants the CLI never to offer unregistered files.
7. **Tests** (`tests/test_cpv.py`):
   - offline: labels via a monkeypatched `read_parquet` (an unmapped code raises), harmonize
     (padding, clash, idempotence, the `CVEGEO` check), key nesting, `state` semantics, and
     the estimaciones reshape/`NIVEL` on a synthetic 2-geography × 5-estimator frame;
   - `_REAL` tests: sentinel `data/parquet/cpv_personas_2025_01.parquet`, with a
     `local_mirror` fixture that monkeypatches `POOCH.fetch` as `tests/test_enigh.py` does
     (needed, since the registry has no cpv entries yet).
8. **EIC 2025 data checks** (`PLAN.md` §Verification; `STEP_1a.md` already found Σ `FACTOR`
   exact per state). As `_REAL` tests on the local states, and once over all 32 on `wsl`
   with the user's OK:
   - personas Σ `FACTOR` = estimaciones `POBTOT` `Valor` for nation, state and each
     municipality;
   - ≥50k localities;
   - viviendas = `VIVPARHAB`;
   - migrantes vs the emigrant total;
   - key nesting;
   - `COBERTURA = 1` for 753 municipalities;
   - LI ≤ valor ≤ LS, and 2,776 × 5 rows.
9. **Memory**: `load_cpv_personas(state=15)` is 2.3 M × 92. Labelling is per column; measure
   peak RSS on the Mac.

## Open questions for the user

- The CLI for `--dataset cpv` in 1c (parse-only until the 1e registry) or in 1e (step 6).
- Commits: ask before committing (the user's standing instruction for this family).

## Gotchas (carry forward)

- **Metadata modes run on `wsl` only.** `--schema-map`/`--variables`/`--report-only` on the
  Mac's 3-state mirror would overwrite the committed 32-state map (`files: 3`) and report.
  `--validate` locally is fine; it only writes the report, which you then should not commit.
- The FD workbook is read by `_dict_fd.read_xlsx` (stdlib). Neither host has `openpyxl`, and
  none is needed.
- `variables_cpv_core.yaml` is hand-curated: never regenerate it. After editing it, rerun
  `--variables` on `wsl`, since the core is copied verbatim into every group file (a test
  checks this).
- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes). Rely on ZIP integrity.
- INEGI downloads run at ~0.3–0.7 MB/s.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (Mac: CPython 3.14.8 with
  `dev` + `notebook`). Both hosts run pyarrow 24.0.0 / pandas 3.0.3.
- With Tailscale SSH, `ssh wsl 'nohup … &'` does not return until the job ends. Launch long
  jobs with the Bash tool's `run_in_background`.
- Faithful raw in `cpv_*`: `null_values=[""]` only, so `NA`/`MI` strings stay verbatim
  (declared `Especiales` since 1b).
- Never `upload_hf.py --delete` from a partial local mirror. Full builds and uploads run on `wsl`.
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen 2020
  path, pinned by `tests/test_census_legacy.py`.
- MG 2025 layers: same projection as 2020, but 5 layers carry an EPSG:6372-named WKT
  (`STEP_0_probe.md` §MG). Decide in 1d.
