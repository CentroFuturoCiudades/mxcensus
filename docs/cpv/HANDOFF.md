# CPV family — session handoff

**Status (2026-10-08, overnight): units 0–3c are complete. 3c's 32-state verification ran
on the Mac, which now holds the full CPV mirror (`STEP_3c.md` §Verification).**
- The Encuesta Intercensal 2025 and the **Censo 2020** are released: registered, uploaded
  and fetchable.
- **EIC 2015** (3a), the **Censo 2010 microdata** (3b) and the **2010 ITER/AGEB** (3c) are
  built on `wsl` (64 + 96 + 64 files), **not registered or uploaded**; 3a–3d upload
  together in 3d. Every Σ `FACTOR` equals INEGI's tabulados exactly.
- 3c added `load_cpv_iter`/`load_cpv_ageb`/`load_cpv_census` and `cpv_iter_crosswalk.yaml`.
  `load_cpv_census(2020)` equals the legacy `load_census` in all 32 states.
- **`wsl` became unreachable mid-3c**: Tailscale SSH asks for an interactive re-login
  (`ssh wsl` prints a `login.tailscale.com/a/…` URL). **The user must re-authenticate**:
  run `ssh wsl` in a terminal and open the URL. Uploads need `wsl` (the Mac has no HF
  client or token).

The user asked (2026-10-07, before going to sleep) for all remaining phases to run in that
session without their input, and allowed commits, pushes and HF uploads (not package
installs). A fresh session should confirm with the user before relying on that.

Design: [`PLAN.md`](PLAN.md). Recent units: [`STEP_3c.md`](STEP_3c.md) (aggregates,
crosswalk, what is pending), [`STEP_3b.md`](STEP_3b.md) (CPV 2010 DBF microdata, national
keys, core `Periodos`), [`STEP_3a.md`](STEP_3a.md) (EIC 2015, stdlib `.xls` reader),
[`STEP_2b.md`](STEP_2b.md) … [`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, version **0.6.0** (`main` = `v0.6.0`). The registry still has
**2695 entries**.

**Host state.**
- `wsl:~/mxcensus` holds the full mirror (with the 2015 and 2010 files) at HEAD = 3a, with
  3b's files copied in (`git status` shows exactly 3b's changes). 3c's code and generated
  metadata are in the separate copy **`~/mxcensus3c`** (run there with
  `PYTHONPATH=src ~/mxcensus/.venv/bin/python …` and `--output/--dict-dir` pointing at
  `~/mxcensus/data`); it can be deleted once 3c is verified.
- The Mac has state 01 of every edition, all 2010/2015/2020 dictionaries in `data/dict/fd/`,
  and the commits.

## 3c verification — done on the Mac

`wsl` stayed unreachable, so the Mac got the full mirror (2020/2025 from the bucket, 2010/2015
rebuilt from INEGI) and ran the checks there: metadata byte-identical, `--validate` 0/481,
the 32-state CPV tests (`STEP_3c.md` §Verification). `wsl:~/mxcensus` still needs to be
brought to the branch before its next use (`git checkout -- . && git pull --ff-only`, after
removing the untracked 3b files listed in `git status`), and `~/mxcensus3c` can be deleted.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to.
> Execute unit 3d (MG 2010 v5.0 national ZIP → per-state mg_*_2010_NN; identify the
> EIC 2015 frame; registry for 3a–3d; HF upload + verify; clean-cache fetch; CLI/README/
> CLAUDE.md for 2010/2015; version bump) following the session protocol at the top of
> PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without asking; ask me before
> committing, pushing, installing packages or uploading. When the unit's gate is met,
> write docs/cpv/STEP_3d.md, tick the unit table, rewrite HANDOFF.md for unit 4a, update
> the memory note, ask me before committing, and give me the next handoff prompt.

## Next unit — 3d: MG 2010, the 2015 frame, release of 3a–3d

Gate: the 3a–3d files are registered, uploaded and verified, and a clean-cache fetch plus
the unpatched loaders work for 2010 and 2015.

1. **MG 2010 v5.0** (`STEP_0_probe.md` §MG; `_catalog.MG_EDITIONS["2010"]`, UPC
   702825292812):
   - The national ZIP (`…/geografia/marc_geo/702825292812_s.zip`, ~100 MB) is split per
     state into `mg_{sfx}_2010_NN.parquet`, the same layers as 2020 where they exist.
   - `build_marco_geo.py` handles per-state ZIPs only, so add the national-ZIP path.
   - Check the CRS spellings and the layer list (`contenido`).
2. **EIC 2015 frame**: identify which MG edition frames the EIC 2015 (likely MG 2014 v6.2 —
   probe INEGI). Set `CpvEdition("2015").mg_period`, and build it only if it is a new
   edition.
3. **Registry**:
   - `build_cpv.py --update-registry` adds 64 + 96 + 64 = **224 `cpv_` files**;
     `build_marco_geo.py --period 2010 --update-registry` adds the MG files.
   - The diff must be additions only.
4. **Upload**: `upload_hf.py upload` from `wsl` (dry-run first, never `--delete`), then
   `verify` in the background and a clean-cache `POOCH.fetch` of a few files.
5. **CLI/docs**:
   - `fetch --dataset cpv --edition 2010|2015` and `--dataset mg --edition 2010` (they
     offer registered files only);
   - README (the 2015/2010 prose, the ITER/AGEB loaders), CLAUDE.md counts,
     `docs/hf_bucket_readme.md`;
   - a version bump (0.7.0), then the merge into `main` + tag if the user wants it as in 2b.

## Open questions for the user

- **Re-authenticate Tailscale SSH on `wsl`** (blocking every `wsl` step).
- Decisions taken overnight without the user, for their review:
  - a stdlib DBF reader instead of `dbfread` (3b);
  - national keys for 2010 under `harmonize=True` (3b);
  - the core `Periodos` key (3b);
  - `load_cpv_census` and the one-frame-with-`NIVEL` design of `load_cpv_iter`/`load_cpv_ageb` (3c);
  - the crosswalk review flags (3c).

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
- **Census aggregates**: ITER/AGEB 2010 = `g01`, 2020 = `g02`. 2010 headers are lower case
  (the code rules match case-insensitively), `TAMLOC` is a string class code in both
  editions (`_AGG_CODES`), and the crosswalk renames only `TAM_LOC` → `TAMLOC`.
  `cpv_iter_crosswalk.yaml` is generated (`--crosswalk`), never hand-edited.
- **Tailscale SSH can demand a re-login at any time** (it did at 2026-10-07 ~23:30). A
  hanging `ssh wsl` that prints a login URL means it needs the user.
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
