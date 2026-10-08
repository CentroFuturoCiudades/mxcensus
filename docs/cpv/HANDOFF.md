# CPV family — session handoff

**Status (2026-10-07): units 0, 1a–1e, 2a and 2b are complete.**
- The Encuesta Intercensal 2025 and the **Censo 2020** are released: registered, uploaded
  and fetchable (`mxcensus fetch N --dataset cpv --edition 2020`).
- `harmonize=True` maps the 2020 geography onto the 2025/MG names (`STEP_2b.md`).
- The 2020 files equal the legacy `viviendas_`/`personas_`/`iter_`/`resargebub_` files cell
  by cell in all 32 states.
- **Next is unit 3a**: the Encuesta Intercensal 2015 (build, dictionary, validation; no
  upload — 3a–3d upload together in 3d).

Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at the top). What 2b did:
[`STEP_2b.md`](STEP_2b.md). Earlier units: [`STEP_2a.md`](STEP_2a.md) (CPV 2020 build, FD
dictionary), [`STEP_1e.md`](STEP_1e.md) (registry, upload, CLI), [`STEP_1d.md`](STEP_1d.md)
(MG 2025, `load_mg`), [`STEP_1c.md`](STEP_1c.md) (loaders), [`STEP_1b.md`](STEP_1b.md)
(dictionaries), [`STEP_1a.md`](STEP_1a.md) (build), [`STEP_0_probe.md`](STEP_0_probe.md)
(URLs, members, editions).

Branch: `cpv-integration`, version **0.6.0**. At the end of 2b it was **merged into `main`
(fast-forward) and tagged `v0.6.0`** (EIC 2025 + CPV 2020; there is no `v0.5.0` tag).
Keep working on `cpv-integration`; merge again at the next release point. The registry has **2695 entries**: 128 legacy census, 986 MG,
800 DENUE, 425 ENOE, 99 ENIGH and 257 CPV (97 EIC 2025 + 160 CPV 2020).

**Host state.**
- `wsl:~/mxcensus` holds the full mirror and the logs (`build_cpv_2020.log`,
  `variables_2b.log`, `validate_2b.log`, `registry_2b.log`, `upload_2b*.log`,
  `verify_2b.log`, `pytest_2b*.log`).
- The Mac has CPV 2020 state 01 only, EIC 2025 states 01/09/15 plus the estimaciones, and
  all 128 legacy census files.
- 2a and 2b are pushed. At the end of 2b, `wsl`'s tree was cleaned (2b's `scp`'d copies
  discarded) and fast-forwarded to the pushed branch. Check `git status` /
  `git log --oneline -3` on both hosts before starting.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (3a: Encuesta Intercensal 2015 — probe the state-01 ZIP,
> dictionary from RNM DDI 214 (the FD is a legacy .xls), enable the 2015 build, full build
> and metadata on wsl, core verified for 2015, --validate 0, Σ FACTOR vs INEGI's published
> totals) following the session protocol at the top of PLAN.md. Use .venv/bin/python, not
> uv run. Run wsl tasks without asking; ask me before committing, pushing, installing
> packages or uploading. When the unit's gate is met, write docs/cpv/STEP_3a.md, tick the
> unit table, rewrite HANDOFF.md for unit 3b, update the memory note, ask me before
> committing, and give me the next handoff prompt.

## Next unit — 3a: Encuesta Intercensal 2015

Gate: `build_cpv.py --validate` reports 0 failures over every CPV file (2015 + 2020 + 2025),
and Σ `FACTOR` matches INEGI's published EIC 2015 totals. No registry or upload in 3a:
the plan uploads 3a–3d together in 3d.

1. **Read first**:
   - `PLAN.md` Phase 3 (the 2015 bullet) and the edition matrix row;
   - `STEP_0_probe.md` (2015: `intercensal/2015/microdatos/eic2015_{NN}_csv.zip`, members
     `TR_VIVIENDA01.CSV`/`TR_PERSONA01.CSV`, FD `doc/eic2015_fd.xls`, DDI 214,
     `idBiinegi` 1714);
   - `STEP_2a.md`: the pattern for adding an edition (dictionary probe, build, metadata
     order, gid shift, tests);
   - `CpvEdition("2015")` in `_cpv_catalog.py`. Its member regexes are lower-case `\.csv`;
     the probed names are upper-case `.CSV`, so check that `find_member` matches
     case-insensitively.
2. **Probe the data (Mac)**:
   - `build_cpv.py --dry-run --periods 2015 --states 1`.
   - Fetch the state-01 ZIP and read the headers:
     - geography spelling (`ENT`/`MUN`/`LOC50K`? `NOM_*`?), and whether `ENT` is
       zero-padded;
     - key names and widths (`ID_VIV`, `ID_PERSONA`?);
     - `FACTOR`, `ESTRATO`, `UPM`, `COBERTURA` (likely absent), and `TAMLOC` vs `TAM_LOC`;
     - the encoding.
   - Any new spelling of a core column becomes a `_RENAME_CORE` entry once its codes are
     verified.
3. **Dictionary**:
   - The FD is a **legacy BIFF `.xls`**. The stdlib `_dict_fd.read_xlsx` reads only `.xlsx`,
     and `xlrd` would be a new dependency (ask first).
   - So the plan's source is **RNM DDI 214** through `scripts/_dict_ddi.py` (`fetch_ddi`,
     `parse_ddi`, `dictionary_entry`, as `build_enigh.py` uses them). `build_cpv._doc_for`
     knows only FD workbooks and indicator CSVs, so add a DDI branch keyed by
     `CpvEdition.ddi_id`, mapping each table to its DDI file stem.
   - **Check DDI 214's value labels against the data, as 2a did for DDI 632** (`EDAD`,
     `PARENTESCO`, `IDENT_*`, `ENT` padding, yes/no items, numeric ranges). 632 was a
     Nesstar export with observed-statistics labels. If 214 is as thin, decide with the
     user: `xlrd`, a one-off conversion of the `.xls`, or DDI + data enumeration with
     `Nota`s.
4. **Build**:
   - `_ENABLED += ("2015",)`, then a smoke build of state 01 on the Mac.
   - The full build on `wsl`: `--periods 2015 --retries 6`, run with `run_in_background`
     and a log.
   - The EIC 2015 sample is larger than the 2020 cuestionario ampliado; watch the personas
     sizes and memory.
5. **Metadata on `wsl`, in order**: `--dictionary --periods 2015`, `--schema-map`,
   `--report-only`, `--variables`, `--validate --jobs 16`.
   - **Gids shift again.** 2015 slots in first, so viviendas/personas become 2015 = `g01`,
     2020 = `g02`, 2025 = `g03`. Migrantes are unchanged (2015 has none: 2020 `g01`, 2025
     `g02`).
   - Delete the stale `variables_cpv_{viviendas,personas}_g0*.yaml` before `--variables`.
   - Update the README examples (`g02` = EIC 2025 becomes `g03`; `g01` = CPV 2020 becomes
     `g02`). Tests take gids from the map.
6. **Core**:
   - Verify every core entry a 2015 table carries (`SEXO`, `EDAD`, `CLAVIVP`, `TAMLOC`,
     `ESTRATO` width, `UPM`, `FACTOR` range, key widths) against the 2015 FD/DDI and data.
   - Scope or split any entry that differs (`Tablas`, or a rename once verified).
   - Update the core header's "verified for" list.
7. **Data checks and tests**:
   - Σ `FACTOR` (personas, viviendas) per state and nationally vs INEGI's published EIC
     2015 totals. Pin the exact figures and their source (tabulados / principales
     resultados) in `STEP_3a.md`.
   - Keys unique and nested, `FACTOR` constant within a dwelling, `ENT` = file state.
   - `tests/test_cpv.py`:
     - the 2015 build plan, schema groups, planted rejections, and `_REAL` state-01 2015
       loads (`load_cpv_survey(2015, …)` returns `migrantes=None`);
     - `_HARM_STATES`/`test_raw_vs_harmonized_totals_real` assume all three microdata
       tables exist, so loop over the tables the edition publishes.

## Open questions for the user

- **2015 dictionary**: if DDI 214's value labels fall short (step 3), choose `xlrd` (a new
  build dependency), a one-off `.xls` conversion, or DDI + data enumeration.
- Commits, pushes and uploads: ask before each (the user's standing instruction for this
  family). wsl runs need no permission.

## Gotchas (carry forward)

- **CPV gids are chronological** and shift when an older edition joins: 2015 will push 2020
  to `g02` and 2025 to `g03` (viviendas/personas). Code and tests take gids from
  `cpv_schema_map()`; never hard-code one.
- **Harmonization is table-scoped** (`_renames(table)` = `_RENAME_CORE` +
  `_RENAME_TABLE`):
  - the 2020 `ENT`/`MUN` → `CVE_*` everywhere;
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
  `wsl` (2.5 min) or `test_core_yaml_contract` fails.
- **Aggregate sentinels**: `build_cpv._AGG_SPECIALS["2020"]` = `*`/`N/D`/`N/A`.
- **`_dict_fd`** handles the 2020 FD quirks; re-check the 2025 parse is byte-identical
  whenever it changes. It cannot read `.xls`.
- **`ageb_14` (2020) is cp1252**; the sniff handles it.
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
  Soft-404s come back as HTTP 200 + `text/html`.
- **`uv run`** may re-sync `.venv`; use `.venv/bin/python`. Both hosts run pyarrow 24.0.0 /
  pandas 3.0.3, and builds are byte-identical across them.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac for EIC 2025.
- **Frozen legacy path**: `scripts/build_data.py`, `aggregate.py`, `extended_*.py` and the
  legacy files are pinned by `tests/test_census_legacy.py`.
