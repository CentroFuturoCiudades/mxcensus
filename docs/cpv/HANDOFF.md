# CPV family — session handoff

**Status (2026-10-07): units 0 and 1a are done; next is unit 1b.** Design:
[`PLAN.md`](PLAN.md) (unit table and session protocol at the top). What 1a built and found:
[`STEP_1a.md`](STEP_1a.md); unit 0: [`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, **pushed to `origin`** since 1a. `wsl:~/mxcensus` is checked out on
it and holds the full EIC 2025 mirror (97 `cpv_*_2025*` files in `data/parquet`). The Mac has
only states 01, 09, 15 + estimaciones. Check `git status` / `git log --oneline -5` on both
hosts first, and `git pull --ff-only` wherever you are behind.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (1b: dictionaries, schema map, validation for EIC 2025)
> following the session protocol at the top of PLAN.md. Use .venv/bin/python, not
> `uv run`. Ask me before pushing, installing packages, or running anything on the wsl
> host. When the unit's gate is met, write docs/cpv/STEP_1b.md, tick the unit table,
> rewrite HANDOFF.md for unit 1c, update the memory note, ask me before committing,
> and give me the next handoff prompt.

## Next unit — 1b: dictionaries + `--schema-map --variables --report-only --validate`

Gate: `build_cpv.py --validate` reports **0 failures** over the 97 EIC 2025 files. It doubles
as the label-coverage gate, because its `isin` keys are exactly what `labels=True` will map in 1c.

1. **Read first**:
   - the metadata modes of `scripts/build_enigh.py`: `_scan_parquet`, `_group_schemas`,
     `_write_schema_map`, `_write_report`, `_write_variables_yaml`, `_write_validation_report`;
   - `scripts/_dict_ddi.py`: the `parse_ddi` output shape, `dictionary_entry`, `group_entries`,
     `observed_values` (already per column) and `dump_yaml`;
   - the contract header of `src/mxcensus/_yaml/variables_enoe_core.yaml`;
   - `STEP_1a.md` §"What the files look like".
2. **Dependency**: `openpyxl` is installed on **neither** host. Build-only deps live in the
   `dev` extra (`pypdf`, `matplotlib`), so add `openpyxl` there; `PLAN.md` said a `build` extra
   in 1e, so record whichever you choose. Install it with the user's OK, e.g.
   `uv pip install --python .venv/bin/python openpyxl`. Not `uv run`/`uv sync` without the
   extras, since it rebuilds the venv.
3. **`--dictionary`**:
   - Download `dictionary_url("2025", "fd")` (`eic2025_micro_fd.xlsx`) and `"catalogos"`
     (`889463931966_csv.zip`) into the git-ignored `data/dict/fd/`.
   - Re-check the RNM for an EIC 2025 DDI. On 2026-10-07 none existed; the highest id was 1151.
   - **Probe the xlsx layout before writing a parser** (sheets Índice, MODELO LÓGICO, VIVIENDAS,
     PERSONAS, MIGRANTES). Then write `scripts/_dict_fd.py::parse_fd_xlsx(path) ->
     {stem: {VAR: meta}}` in `parse_ddi`'s shape (stems `viviendas`/`personas`/`migrantes`),
     generalising `utils.get_cats_from_excel`.
   - Large classification codes (SINCO `OCUPACION_C`, SCIAN `ACTIVIDADES_C`,
     countries/municipalities `ENT_PAIS_*`/`MUN_*`, language `QDIALECT_INALI`) get
     `Tipo: string` + a `Catálogo:` note, not huge `Categorías`.
4. **Estimaciones dictionary**: `diccionario_datos/diccionario_datos_eic2025_105.csv` inside the
   estimaciones ZIP, via `utils.get_vars_from_indicator_csv`.
   - Indicators get `Tipo: numeric`, with `Especiales` for the literal **`NA`** and **`MI`** cells
     (5,065 and 8,855; 1a keeps them verbatim). Also look for `*`/`N/D`.
   - The geography columns and `ESTIMADOR` stay categorical/string.
   - Use `--cat-threshold 0` for this table.
5. **`variables_cpv_core.yaml`** (hand-curated, never regenerated; ENOE contract header):
   - keys `ID_VIV`/`ID_PERSONA`/`ID_MII`;
   - geography `CVEGEO`, `CVE_ENT`, `CVE_MUN`, `LOC50K`;
   - `FACTOR`, `ESTRATO`, `UPM`, `COBERTURA`, `TIPO_REG` (0/1 in personas — find the meaning),
     `TAMLOC`, `CLAVIVP`;
   - `SEXO` (codes `1`/`3`!) and `EDAD` (`Rango` + its sentinel).
   - Verify every code against the FD.
6. **Modes in `scripts/build_cpv.py`** (same mode set as ENIGH):
   - `--schema-map` → `src/mxcensus/_yaml/cpv_schema_map.yaml`, in the `PLAN.md` format:
     `latest`, `fingerprints`, and `groups` with `{n_columns, files, periods, states (only when
     a group covers part of an edition), columns}`. Gids are chronological. Scan names with
     `_cpv_catalog.parse_filename`, never `split("_")`.
   - `--report-only` → `docs/cpv/INCONSISTENCY_REPORT.md`.
   - `--variables` → `variables_cpv_{table}_{gNN}.yaml`, core > FD > data.
   - `--validate` → `docs/cpv/VALIDATION_REPORT.md`.
   - `--update-registry`: write the code, but run it only in 1e.
   - Expect one group per table: all 32 states share 87/92/27 columns.
7. **`--validate` needs `_group_schema`.** The ENIGH sweep imports it from `mxcensus.enigh`.
   Create a **skeleton `src/mxcensus/cpv.py`** with only the private schema helpers
   (`_fingerprint`, `_group_of`, `_group_schema`, `_validate`), bound to new `_resources`
   accessors `cpv_schema_map()`, `variables_cpv(table, gid)` and `variables_cpv_core()`. The
   loaders are 1c.
8. **Where to run**: iterate on the Mac with the 3 local states. Then run the modes over all
   32 states on `wsl` with the user's OK. Commit the generated YAML/reports there, push, and
   `git pull --ff-only` on the Mac (the established workflow, memory `remote-build-host-wsl`).
   `--validate` reads each file whole with pandas; Estado de México personas is 2.3 M × 92
   strings, fine on `wsl` (125 GB RAM).
9. Tests: core-YAML contract, a schema-map parametrization over `cpv`, `parse_fd_xlsx` on a
   tiny fixture. Keep `pytest -q` green. Then the end-of-session protocol.

## Open questions for the user

- Install `openpyxl` on both hosts, and put it in the `dev` extra or a new `build` extra?
- Commits: ask before committing (the user's standing instruction for this family).

## Gotchas (carry forward)

- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes). Rely on ZIP integrity.
- INEGI download speed is ~0.3–0.7 MB/s; the full 2025 build (33 ZIPs, 735 MiB) took ~38 min on `wsl`.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (Mac: CPython 3.14.8 with
  `dev` + `notebook`). Both hosts run pyarrow 24.0.0 / pandas 3.0.3.
- `ssh wsl 'nohup … &'` (Tailscale SSH) did **not** return until the job ended. Launch it with
  the Bash tool's `run_in_background` and leave that session alone (killing it may take the
  job down).
- Faithful raw in `cpv_*`: `null_values=[""]` only, so `NA`/`N/A` strings stay verbatim. That
  differs from the pandas-built families; see `STEP_1a.md`.
- Never regenerate a hand-curated core YAML. Never `upload_hf.py --delete` from a partial
  local mirror. Full builds/uploads run on `wsl`.
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen 2020
  path, pinned by `tests/test_census_legacy.py`.
- MG 2025 layers: same projection as 2020, but 5 layers carry an EPSG:6372-named WKT
  (`STEP_0_probe.md` §MG). Decide in 1d.
