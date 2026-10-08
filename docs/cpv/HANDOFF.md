# CPV family — session handoff

**Status (2026-10-07, overnight): units 0, 1a–1e, 2a, 2b, 3a and 3b are complete.**
- The Encuesta Intercensal 2025 and the **Censo 2020** are released: registered, uploaded
  and fetchable (`mxcensus fetch N --dataset cpv --edition 2020`).
- **EIC 2015** (3a, `STEP_3a.md`) and the **Censo 2010 microdata** (3b, `STEP_3b.md`) are
  built on `wsl`: 64 + 96 files, **not registered or uploaded** (3a–3d upload together in
  3d). `--validate` reports 0/417 failures, and every Σ `FACTOR` equals INEGI's tabulados
  exactly.
- **Next is unit 3c**: the ITER/AGEB aggregates of 2020 + 2010.

The user asked (2026-10-07, before going to sleep) for **all remaining phases** to run in
that session without their input, and allowed commits, pushes and HF uploads (not package
installs). If a fresh session resumes, it keeps that authorization for this overnight run
only. Check with the user if in doubt.

Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at the top). Recent units:
[`STEP_3b.md`](STEP_3b.md) (CPV 2010 DBF microdata, national keys, core `Periodos`),
[`STEP_3a.md`](STEP_3a.md) (EIC 2015, stdlib `.xls` reader), [`STEP_2b.md`](STEP_2b.md),
[`STEP_2a.md`](STEP_2a.md), [`STEP_1e.md`](STEP_1e.md) … [`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, version **0.6.0** (`main` = `v0.6.0`, EIC 2025 + CPV 2020). The
registry still has **2695 entries**; 3a and 3b added none.

**Host state.**
- `wsl:~/mxcensus` holds the full mirror, now with the EIC 2015 and CPV 2010 microdata
  files. Its dictionaries are in `data/dict/fd/{2010,2015}/` and `data/dict/ddi/{71,214}.xml`;
  logs are `build_cpv_{2015,2010}.log`, `check_{2015,2010}.log`, `validate_3{a,b}.log` and
  `pytest_3{a,b}.log`.
- The Mac has state 01 of every edition built, the legacy census files, and
  `data/dict/fd/{2010,2015}/`.
- 3a is pushed. 3b's files were `scp`'d to `wsl` (working tree dirty there; HEAD = 3a). After
  3b's commit is pushed, clean `wsl` before pulling:
  ```bash
  git checkout -- .
  rm scripts/_dbf.py src/mxcensus/_yaml/variables_cpv_{viviendas,personas}_g0{4,5}.yaml \
     src/mxcensus/_yaml/variables_cpv_migrantes_g0{3,4}.yaml
  git pull --ff-only
  ```

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (3c: the ITER/AGEB aggregates of CPV 2020 + 2010 — fix the
> CSV header read for 2010's BOM-quoted headers, build the 2010 ITER/AGEB, their indicator
> dictionaries and sentinels, load_cpv_iter/load_cpv_ageb with the level split, censoring
> and zero imputation on string codes, a load_cpv_census that reproduces the legacy
> load_census for 2020 (equality over 32 states on wsl), and cpv_iter_crosswalk.yaml
> 2010 ↔ 2020) following the session protocol at the top of PLAN.md. Use .venv/bin/python,
> not uv run. Run wsl tasks without asking; ask me before committing, pushing, installing
> packages or uploading. When the unit's gate is met, write docs/cpv/STEP_3c.md, tick the
> unit table, rewrite HANDOFF.md for unit 3d, update the memory note, ask me before
> committing, and give me the next handoff prompt.

## Next unit — 3c: ITER/AGEB aggregates (2020 + 2010)

Gate: the 2020 output of the new aggregate loaders equals the legacy `load_census(state)`
after dtype alignment (all 32 states on `wsl`), and `--validate` reports 0 failures with the
2010 ITER/AGEB included.

1. **2010 ITER/AGEB build** (`STEP_3b.md` §Findings for 3c):
   - `build_cpv._read_header` must strip the BOM **before** `csv.reader` parses, since
     2010's header is `\ufeff"entidad",…`.
   - Then `--periods 2010 --tables iter ageb` on `wsl`.
   - The indicator dictionaries are already fetched (`data/dict/fd/2010/diccionario_datos_
     {iter,ageb}.csv`, from `fd_*.csv`, cp1252, some mnemonics with trailing junk such as
     `vph_pc\xa0`). Check that `parse_indicator_csv` reads them.
   - Enumerate the non-numeric cells (`*`, `N/D`…) over 32 states for
     `_AGG_SPECIALS["2010"]`.
   - Gids for `iter`/`ageb` become 2010 = `g01`, 2020 = `g02`.
2. **Loaders** (`cpv_aggregates.py`):
   - `load_cpv_iter(period=None, *, state, nivel=None, impute=True)`: harmonized names,
     labelled counts (`*` → NA), index `(CVE_ENT, CVE_MUN, CVE_LOC)`, an ordered `NIVEL`
     (`estatal`/`municipal`/`agregado` = `CVE_LOC` 9998/9999/`localidad`).
   - `load_cpv_ageb(...)`: the same with `(…, CVE_AGEB, CVE_MZA)`, `NIVEL` up to `manzana`.
   - The zero imputation ports `aggregate.impute_zeros_univariate` (municipality →
     localities).
   - A draft of the `NIVEL` helpers is in the session scratchpad and has to be rewritten.
3. **`load_cpv_census(period=None, *, state)`**:
   - It reproduces `aggregate.load_census` on the `cpv_` files and string codes: the level
     split, the block quick-imputation, `add_collective_cols`, the zero imputations and
     the sanity checks (ported: the legacy `sanity_checks` hard-codes `ENTIDAD`/`MUN`).
   - The generic legacy helpers (`add_collective_cols`, `impute_zeros_univariate`) can be
     imported, since they are index-name agnostic. `aggregate.py` itself stays frozen.
   - Test: equal to `load_census(state)` after casting the index codes to int (state 01 on
     the Mac; all 32 on `wsl`).
4. **`cpv_iter_crosswalk.yaml`** (canonical 2020 mnemonic → 2010 source):
   - 185 names are shared; check their descriptions (generated draft + hand review).
   - Leave out the changed concepts (`PRES2005`/`PRES2015`, the disability block).
   - Use it when stacking 2010 + 2020 aggregates (`harmonize=True`).
5. Tests, docs (`STEP_3c.md`, PLAN tick, HANDOFF for 3d), commit + push.

## Open questions for the user

- None blocking. Decisions taken overnight without the user, for their review:
  - a stdlib DBF reader instead of `dbfread` (3b);
  - national keys for 2010 under `harmonize=True` (3b);
  - the core `Periodos` key (3b).

## Gotchas (carry forward)

- **CPV gids are chronological** and shift whenever an older edition joins (3a: 2015 =
  `g01`; 3b: 2010 = `g01`/`g02`, state 15's lower-case `tam_loc` making its own group). Code and tests take gids from `cpv_schema_map()` /
  `_gid(table, period)`; never hard-code one.
- **The FD workbooks beat the RNM DDIs** so far: 632 (2020) and 214 (2015) are Nesstar
  exports with collapsed ranges, wrong code lists and no missing flags. `ddi_id` is
  recorded and fetched for reference only.
- **`_dict_fd`** reads `.xlsx` and legacy `.xls` (`read_workbook`). 2015's quirks:
  - «Numérico» coded items (`_enumerated`);
  - `TC_…` catalog rows (`Catálogo` only under «Descripción por catálogo»);
  - `b` for the blank row;
  - `Ver catálogo` headers.

  Any change must keep the 2015/2020/2025 parses byte-identical: dump them as JSON on both
  hosts before and after.
- **Unpadded 2015 codes**: `ID_VIV` (11 digits in states 01–09), `ID_PERSONA`, `CLAVIVP`.
  The core `CLAVIVP` `Alias` covers raw validation and labels; `harmonize=True` pads all
  three (`cpv._CODE_PAD`).
- **CPV 2010 keys are state-scoped serials.** Keyed loaders refuse several states unless
  `harmonize=True`, which builds national keys (`cpv._national_keys`). The core `CLAVIVP`
  carries `Periodos` (2015–2025), and `TAM_LOC` (4 classes) is not `TAMLOC`.
- **`scripts/_dbf.py`** sniffs cp1252/cp850 from the bytes; INEGI's driver byte lies.
- **Harmonization is table-scoped** (`_renames(table)` = `_RENAME_CORE` + `_RENAME_TABLE`):
  - the 2015/2020 `ENT`/`MUN` → `CVE_*` everywhere;
  - `ENTIDAD`/`LOC` only in ITER/AGEB, and `AGEB`/`MZA` → `CVE_AGEB`/`CVE_MZA` only in AGEB.
  - `CVEGEO` concatenates the *leading* `_GEO_PARTS`: 5, 9 or 16 characters, total rows
    with zero parts.
  - Editions load one per call; stack with `pd.concat(..., names=["PERIOD"])`.
- **Legacy files** were built with pandas' default NA strings **plus `na_values=["N/D"]`**.
  `N/D` and `N/A` are NaN there and kept verbatim in `cpv_*`; the comparator
  (`_LEGACY_NA`) knows. State 01 has no `N/D`, so only the 32-state run (`wsl`) covers it.
- **`_labels_for`** compares only `_LABEL_KEYS`. Between 2020 and 2025, 7/22/5
  (viviendas/personas/migrantes) shared columns label differently.
- **Core scope**: a core entry with `Tablas` applies only to those tables (`_in_scope`;
  `TAMLOC` is microdata-only). `CVE_AGEB`/`CVE_MZA` exist only as harmonized names.
- **Core edits** change the verbatim copies in the generated YAMLs. Rerun `--variables` on
  `wsl` (3.5 min) or `test_core_yaml_contract` fails.
- **Aggregate sentinels**: `build_cpv._AGG_SPECIALS["2020"]` = `*`/`N/D`/`N/A`. 2010's ITER
  will need its own entry (3c).
- **`ageb_14` (2020) is cp1252**; the 2015 CSVs are cp1252 too (one ASCII file sniffs
  UTF-8). The sniff handles both.
- **Metadata modes run on `wsl` only** (`--schema-map`, `--variables`, `--report-only`); the
  Mac's partial mirror would overwrite the 32-state outputs.
- **The CLI offers only registered files** (`POOCH.registry`). Unregistered files are
  readable through the tests' `local_mirror` fixture.
- **Registry**: `--update-registry` upserts. The diff must be additions only (`git diff
  --numstat`).
- **Upload**: `upload_hf.py upload` from `wsl` only, never with `--delete`. Dry-run first.
  `verify` HEADs every registry URL (~2.7k, ~15 min), so run it in the background; a
  timeout counts as "missing", so re-check misses by hand.
- **`pkill -f` over ssh**: the pattern also matches the ssh command line that runs it, so it
  kills its own session (exit 255). Use `pgrep`, then kill by PID.
- **Long jobs on `wsl`**: with Tailscale SSH, `ssh wsl 'nohup … &'` does not return until
  the job ends. Use `run_in_background`. The 32-state CPV tests take well over 10 minutes.
- **INEGI downloads** drop connections and truncate ZIPs; `fetch_zip_verified` retries.
  Soft-404s come back as HTTP 200 + `text/html`. Some files exist but are not in the
  file-listing API (2015's `doc/eic2015_catalogos.zip`), so try the obvious URL.
- **`uv run`** may re-sync `.venv`; use `.venv/bin/python`. Both hosts run pyarrow 24.0.0 /
  pandas 3.0.3, and builds are byte-identical across them.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac for EIC 2025. The
  2015 build peaked at 2.7 GB on `wsl`.
- **Frozen legacy path**: `scripts/build_data.py`, `aggregate.py`, `extended_*.py` and the
  legacy files are pinned by `tests/test_census_legacy.py`.
