# CPV family — session handoff

**Status (2026-10-07): units 0, 1a–1e, 2a, 2b and 3a are complete.**
- The Encuesta Intercensal 2025 and the **Censo 2020** are released: registered, uploaded
  and fetchable (`mxcensus fetch N --dataset cpv --edition 2020`).
- **The Encuesta Intercensal 2015 is built** (unit 3a, `STEP_3a.md`):
  - 64 `cpv_{viviendas,personas}_2015_NN` files sit on `wsl`, **not registered or
    uploaded** — 3a–3d upload together in 3d;
  - `--validate` reports 0/321 failures;
  - every Σ `FACTOR` equals INEGI's tabulados exactly (32 states + nation; dwellings,
    population, men, women).
- **Next is unit 3b**: the Censo 2010 microdata (DBF).

Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at the top). What 3a did:
[`STEP_3a.md`](STEP_3a.md). Earlier units: [`STEP_2b.md`](STEP_2b.md) (2020↔2025
harmonization, legacy equality, release), [`STEP_2a.md`](STEP_2a.md) (CPV 2020 build, FD
dictionary), [`STEP_1e.md`](STEP_1e.md) (registry, upload, CLI), [`STEP_1d.md`](STEP_1d.md)
(MG 2025, `load_mg`), [`STEP_1c.md`](STEP_1c.md) (loaders), [`STEP_1b.md`](STEP_1b.md)
(dictionaries), [`STEP_1a.md`](STEP_1a.md) (build), [`STEP_0_probe.md`](STEP_0_probe.md)
(URLs, members, editions).

Branch: `cpv-integration`, version **0.6.0** (`main` = `v0.6.0`, EIC 2025 + CPV 2020). The
registry still has **2695 entries**; 3a added none.

**Host state.**
- `wsl:~/mxcensus` holds the full mirror (now with the 64 EIC 2015 files), the 2015 ZIPs
  in `data/cache/`, the dictionaries in `data/dict/fd/2015/` + `data/dict/ddi/214.xml`, and
  the logs (`build_cpv_2015.log`, `check_2015.log`, `validate_3a.log`, `pytest_3a.log`).
- The Mac has EIC 2015 state 01, CPV 2020 state 01, EIC 2025 states 01/09/15 plus the
  estimaciones, all 128 legacy census files, and `data/dict/fd/2015/`.
- **If 3a's commit is pushed, clean `wsl` before pulling.** 3a's `scp`'d copies make its
  tree dirty, and the two new `g03` YAMLs are untracked there:
  ```bash
  git checkout -- .
  rm src/mxcensus/_yaml/variables_cpv_{viviendas,personas}_g03.yaml
  git pull --ff-only
  ```
  Check `git status` / `git log --oneline -3` on both hosts before starting.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (3b: Censo 2010 microdata — DBF reader (ask me: dbfread build
> extra or a stdlib reader), probe the state-01 ZIP and its code pages, dictionary from the
> FD .xls (read_xls) + DBF catalogs, cross-checked against RNM DDI 71, a national ID_VIV,
> FACTOR joined onto personas, ID_PER/ID_MIN/TAM_LOC renames, full build and metadata on
> wsl, --validate 0, Σ FACTOR vs INEGI's published 2010 totals) following the session
> protocol at the top of PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without
> asking; ask me before committing, pushing, installing packages or uploading. When the
> unit's gate is met, write docs/cpv/STEP_3b.md, tick the unit table, rewrite HANDOFF.md for
> unit 3c, update the memory note, ask me before committing, and give me the next handoff
> prompt.

## Next unit — 3b: Censo de Población y Vivienda 2010 (microdata)

Gate: `build_cpv.py --validate` reports 0 failures over every CPV file (2010 + 2015 + 2020
+ 2025), and Σ `FACTOR` matches INEGI's published 2010 totals (inhabited private dwellings
and their population). No registry or upload (3d).

1. **Read first**:
   - `PLAN.md` Phase 3 (the 2010 bullets) and the edition matrix row;
   - `STEP_0_probe.md` §Microdata structure (2010: `Viviendas_01`/`Personas_01`/
     `Migrantes_01.dbf`; `ID_VIV` C8, `ID_PER` C9, `ID_MIN` C7; `FACTOR` N8 in viviendas
     and migrantes only; DBF code-page bytes 0x00/0x03);
   - `STEP_3a.md` (the stdlib `.xls` reader, the 2015 FD conventions, `_CODE_PAD`);
   - `CpvEdition("2010")` in `_cpv_catalog.py`.
2. **DBF reader — ask the user first.**
   - The plan says `dbfread(raw=True)` as a maintainer-only `build` extra (the user
     anticipated it in 1b).
   - Since then the user chose stdlib readers for `.xlsx` and `.xls`. A dBASE III reader
     is small (32-byte header, 32-byte field descriptors, fixed-width records, deletion
     flag) and fits that line.
   - Either way, decode by code page (cp850 vs latin-1/cp1252: the header byte is
     0x00/0x03, so check the bytes), strip only the fixed-width padding, keep every value
     a string, and skip deleted records (count them).
   - **Memory**: build Arrow columns per field, not row dicts. Personas for state 15 have
     millions of rows.
3. **Probe (Mac)**: `build_cpv.py --dry-run --periods 2010 --states 1`, then fetch
   `MC2010_01_dbf.zip`:
   - field names, types and widths; the code page;
   - `ID_VIV` uniqueness within the state and across two states;
   - geography (`ENT`/`MUN`/`LOC`? widths), `TAM_LOC`, `COBERTURA`/`ESTRATO`/`UPM`;
   - whether personas really carry no `FACTOR`.
4. **Dictionary**:
   - The FD `doc/diccionario_cuestionario_ampliado.xls` should parse with `_dict_fd.parse_fd`
     (`read_xls`). Check its layout against 2015's conventions.
   - The catalogs `doc/catalogos_2010_dbf.zip` are DBF, so `read_catalogs` needs a DBF
     branch (same reader).
   - DDI 71: probe it as 2a/3a did and compare `EDAD`, `PARENTESCO`, ranges and sentinels.
     So far the FDs have won.
   - Re-check that the 2015/2020/2025 parses stay byte-identical: dump them before
     changing `_dict_fd` (`STEP_3a.md` §`_dict_fd`).
5. **Keys and harmonization** (`cpv.py`):
   - **`ID_VIV` is 8 characters and unique only within a state.** Raw loads of several
     states must not collide: the dwelling key spec needs the entity, or `harmonize=True`
     must build a national `ID_VIV` (e.g. `ENT` + something) **before** `_CODE_PAD` pads
     it. Otherwise `zfill(12)` invents a wrong entity prefix. Decide and document it.
   - `_RENAME_CORE` += `ID_PER` → `ID_PERSONA`, `ID_MIN` → `ID_MII`, `TAM_LOC` → `TAMLOC`,
     once the codes are verified. The key specs already alias `ID_PER`/`ID_MIN`.
   - **Personas have no `FACTOR`.** The analysis-ready personas loader must join the
     dwelling's `FACTOR`, like ENIGH's `_attach_factor`. Σ `FACTOR` over persons then
     checks the population total.
6. **Build**:
   - `_ENABLED += ("2010",)` once the DBF path exists; the DBF tables go through a new
     reader branch in `_build_zip`.
   - The 2010 `iter`/`ageb` are CSV (lower-case headers). Building them in 3b is cheap and
     lets 3c start from data. Decide whether to include them (`--tables`) or leave them to
     3c; the plan puts their *loaders* in 3c.
   - Smoke-build state 01 on the Mac, then the full build on `wsl` (`run_in_background` +
     a log).
7. **Metadata on `wsl`, in order**: `--dictionary --periods 2010`, `--schema-map`,
   `--report-only`, delete the stale `variables_cpv_{viviendas,personas,migrantes}_g0*.yaml`,
   `--variables`, `--validate --jobs 16`.
   - **Gids shift again**: 2010 joins first, so viviendas/personas become 2010 = `g01`
     … 2025 = `g04`, and migrantes 2010 = `g01`, 2020 = `g02`, 2025 = `g03`.
   - Update the README `variables_cpv` examples and the tests' expectations. Tests take
     gids from `_gid(table, period)`; `test_schema_map_2015_groups` lists the period
     sequence and needs the new first group.
8. **Data checks and tests**:
   - Σ `FACTOR` per state and nationally vs INEGI's published 2010 cuestionario ampliado
     totals: find the tabulados (`idBiinegi` 487, `tipodocto=5`; `read_xls` reads them).
   - Keys unique and nested, `ENT` = file state, `FACTOR` constant within the dwelling.
   - `tests/test_cpv.py`: the 2010 build plan, the groups, planted rejections, the DBF
     reader (synthetic DBF bytes, as 3a's `_xls` writer), and `_REAL` state-01 loads.

## Open questions for the user

- **DBF reader**: the `dbfread` build extra (plan) or a stdlib reader (step 2).
- Commits, pushes and uploads: ask before each (the user's standing instruction for this
  family). wsl runs need no permission.

## Gotchas (carry forward)

- **CPV gids are chronological** and shift whenever an older edition joins (3a: 2015 =
  `g01`; 3b: 2010 = `g01`). Code and tests take gids from `cpv_schema_map()` /
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
