# CPV family — session handoff

**Status (2026-10-08, overnight): units 0–3c and 4a are complete; 3d is half done (its
release waits for `wsl`). Next: unit 4b.**
- **Released** (registered, uploaded, fetchable): the Encuesta Intercensal 2025 and the
  Censo 2020.
- **Built, not registered or uploaded**:

  | unit | files |
  |---|---|
  | 3a | EIC 2015, 64 |
  | 3b | Censo 2010 microdata, 96 |
  | 3c | 2010 ITER/AGEB, 64 |
  | 3d | MG 2010, 160 |
  | 4a | CGPV 2000 + Conteo 2005 microdata, 192 |

  They upload together once `wsl` is back (§Release batch). The 2010/2015 Σ `FACTOR`
  equal INEGI's tabulados exactly. 2000's `FACTOR` is a ratio estimator on preliminary
  counts, bounded by the ITER (`STEP_4a.md` §Weights). 2005 has no weight.
- **`wsl` is unreachable**: Tailscale SSH asks for an interactive re-login (`ssh wsl` prints
  a `login.tailscale.com/a/…` URL). **The user must re-authenticate**: run `ssh wsl` in a
  terminal and open the URL. Only the HF upload needs `wsl` (it holds the HF token; the
  Mac has no HF client).
- **3c's 32-state verification ran on the Mac** and found two census-chain bugs, both
  fixed (`STEP_3c.md` §Verification). One is a pre-existing crash of the frozen legacy
  `load_census` in states 08/15/16.

The user asked (2026-10-07, before going to sleep) for all remaining phases to run in that
session without their input, and allowed commits, pushes and HF uploads (not package
installs). A fresh session should confirm with the user before relying on that.

Design: [`PLAN.md`](PLAN.md). Recent units:
- [`STEP_4a.md`](STEP_4a.md): 2000/2005 microdata, PDF/split-layout FDs, composite keys,
  households, `Recodificar`;
- [`STEP_3d.md`](STEP_3d.md): the national-ZIP MG builder, MG 2010;
- [`STEP_3c.md`](STEP_3c.md): aggregates, crosswalk, the Mac verification;
- [`STEP_3b.md`](STEP_3b.md) … [`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, version **0.6.0** (`main` = `v0.6.0`). The registry still has
**2695 entries**.

**Host state.**
- **The Mac** holds the whole CPV mirror:
  - every CPV file of 2000–2025 (673: 2020/2025 from the bucket, 2010/2015 rebuilt from
    INEGI, 2000/2005 built here);
  - MG 2010 (160) and the legacy census files;
  - every dictionary in `data/dict/fd/` (2000–2025);
  - the cached INEGI ZIPs, including the 2000/2005 ITER and the 1995/2000/2005 MG ZIPs
    (the latter in the session scratchpad, re-downloadable).

  Metadata modes and 32-state tests now run on the Mac.
- **`wsl:~/mxcensus`** is at 3a's HEAD with 3b's files copied in, and still holds the
  2010/2015 files it built. **`~/mxcensus3c`** (3c's code copy) can be deleted.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to, and
> execute unit 4b (CGPV 2000 + Conteo 2005 ITER and their crosswalk entries, the 2000/2005
> municipal Marco Geoestadístico; their release joins the pending batch) following the
> session protocol at the top of PLAN.md. If wsl is reachable, do the pending release batch
> first (HANDOFF §Release batch). Use .venv/bin/python, not uv run. Run wsl tasks without
> asking; ask me before committing, pushing, installing packages or uploading. When the
> unit's gate is met, write docs/cpv/STEP_4b.md, tick the unit table, rewrite HANDOFF.md for
> unit 5a, update the memory note, ask me before committing, and give me the next handoff
> prompt.

## Next unit — 4b: 2000 + 2005 ITER, crosswalk, municipal MGs

Gate: `--validate` 0 with the 2000/2005 ITER, a reviewed crosswalk, and the MG files built.
"Uploaded" waits for `wsl` (§Release batch).

1. **ITER build**: `build_cpv.py --periods 2000 2005 --tables iter` (ZIPs cached on the
   Mac).
   - The CSVs look like 2010's: lower-case names, a BOM before a quoted header, total rows
     `mun=000`/`loc=0000`, the 9998/9999 aggregates.
   - 2000 has 132 columns and the markers `*`/`N/D`; 2005 has 130 and `*` (state 01).
     Enumerate the markers over all 32 states, then add `_AGG_SPECIALS["2000"/"2005"]`.
   - The indicator dictionaries are fetched (`data/dict/fd/{2000,2005}/diccionario_datos_iter.csv`).
2. **Crosswalk** (`build_cpv.py --crosswalk`, generated; the review is code: `_XW_PAIRS`,
   `_XW_RENAME`, `_XW_NOTES`, `_XW_NOT_COMPARABLE`):
   - add 2005/2000 to `_XW_PERIODS`;
   - 2005 renames most mnemonics (`p_total`, `p_mas`, `p_fem`, `o_vivpar`…), 2000 fewer
     (`pmascul`, `pfemeni`, `ocuvivpar`…). Only 15 (2000) / 28 (2005) names equal a
     canonical indicator, and 30/49 more match a 2010/2020 description exactly;
   - draft the pairs by normalized description, then review them by hand (the age groups,
     education and income bands differ).
3. **Loaders**: `load_cpv_iter(2000|2005)` (no AGEB file in either year, so no
   `load_cpv_census`). Check `NIVEL`, the 9998/9999 rows, the zero imputation and the
   counts types (`_AGG_CODES` for `TAM_LOC` if present).
4. **Municipal MGs** (`build_marco_geo.py --period 2000|2005|1995`, national ZIPs):
   - 2000 = `mge2000`/`mgm2000`/`mgau2000`; its AGEB shapefile is `agebs_urb_2000`, so
     `_NATIONAL_LAYERS`' `^ageb_urb` must become `^agebs?_urb`. Its `bitacora` CSV is a
     change log.
   - 2005 = `mge`/`mgm`/`mgau` 2005v_1_0, but **its `Entidades`/`Municipios` shapefiles have
     no `.prj`**: take the CRS of the edition's AGEB layer (it has one) after checking the
     extents agree, or set it explicitly with a note.
   - 1995 = `mge1995`/`mgm1995` only (unit 5b builds it).
   - Check counts against the ITER municipalities (2,443 in 2000; 2,454 in 2005).
5. Metadata (Mac): `--schema-map --report-only --variables --validate --crosswalk`; tests;
   STEP_4b; HANDOFF.

## Release batch (needs `wsl`; 3d's gate, then 4b/5b's)

1. Bring `wsl:~/mxcensus` to the branch: `git status`; remove the untracked 3b leftovers
   (`scripts/_dbf.py`, the old `variables_cpv_*_g0*.yaml` it lists); `git checkout -- .`;
   `git pull --ff-only`.
2. Put the Mac-built files on `wsl`: rebuild them there (`build_cpv.py --periods 2000 2005
   --tables viviendas hogares personas migrantes` takes ~1 min; `build_marco_geo.py
   --period 2010 --no-registry`), or `scp` them. Compare `sha256sum` of every 2010/2015
   file on both hosts: the builds are deterministic, so any difference is a finding.
3. Registry:
   - `build_cpv.py --update-registry` adds the 64 + 160 + 192 `cpv_` files, plus 4b's ITER
     if done;
   - `build_marco_geo.py --period 2010 --update-registry` adds 160 more;
   - the diff must be additions only.
4. `upload_hf.py upload --dry-run`, then `upload` (never `--delete`); then `verify` in the
   background and a clean-cache `POOCH.fetch` with the unpatched loaders.
5. CLI/docs:
   - `fetch --dataset cpv --edition 2000|2005|2010|2015`, `--dataset mg --edition 2010`;
   - README (the 2015/2010/2005/2000 prose, the ITER/AGEB loaders, `load_cpv_hogares`),
     CLAUDE.md counts, `docs/hf_bucket_readme.md`;
   - version 0.7.0, then the merge into `main` + tag if the user wants it as in 2b.
6. The EIC 2015 frame is still unidentified (`STEP_3d.md`).

## Open questions for the user

- **Re-authenticate Tailscale SSH on `wsl`** (blocks the release).
- Decisions taken overnight without the user, for their review:
  - (3b) a stdlib DBF reader instead of `dbfread`; national keys for 2010 under
    `harmonize=True`; the core `Periodos` key;
  - (3c) `load_cpv_census`; the one-frame-with-`NIVEL` design of `load_cpv_iter`/
    `load_cpv_ageb`; the crosswalk review flags;
  - (3c verification) the NA-safe port of the collective imputation, which leaves the
    legacy `load_census` broken in states 08/15/16; the 2010 `TVIVHAB` allowance;
  - (4a) the derived 2000/2005 keys. 2000's persons are numbered **in file order** (it has
    no person number), and 2005's `ID_VIV` is padded to 12 digits.
  - (4a) the household level (`ID_HOG`) in the 2000/2005 indices; CGPV 2000's `viviendas`
    has one row per household; `load_cpv_survey` stays a 3-tuple and `load_cpv_hogares` is
    separate.
  - (4a) the core `Recodificar` key (2000/2005 `SEXO` 2 → 3, applied by `harmonize=True`).
  - (4a) the 2000 weight check is a bound against the ITER, not an equality.

## Gotchas (carry forward)

- **CPV gids are chronological** and shift whenever an older edition joins. Since 4a, for
  `viviendas`/`personas`: 2000 = `g01`, 2005 = `g02`, 2010 = `g03` + `g04` (state 15's
  lower-case `tam_loc`), 2015 = `g05`, 2020 = `g06`, 2025 = `g07`; for `migrantes`:
  2000/2010/2010-15/2020/2025 = `g01`…`g05`; `hogares` 2005 = `g01`. Code and tests take
  gids from `cpv_schema_map()` / `_gid(table, period)`; never hard-code one. **Delete the
  `variables_cpv_*_g*.yaml` before `--variables`** when the gids shift.
- **2000/2005 keys are derived** (`cpv._composite_keys`; `load_cpv` never adds them). 2000's
  `ID_PERSONA` is the person's order within the household **in file order**, so it depends
  on the mirror's row order: never re-sort a 2000 personas file before deriving keys.
- **The 2000 FD is a PDF** (`_dict_fd.parse_fd_text` on `pypdf` text); 2005's is a
  split-layout `.xls`. FD misspellings of data columns go in `build_cpv._FD_RENAMES`.
  `_quantity` (FDs without `Tipo`): one labelled range row, or one header range plus
  sentinels, is a count; several ranges make a code list.
- **The FD workbooks beat the RNM DDIs** so far: 632 (2020) and 214 (2015) are Nesstar
  exports with collapsed ranges, wrong code lists and no missing flags. `ddi_id` is
  recorded and fetched for reference only.
- **`_dict_fd`** reads `.xlsx` and legacy `.xls` (`read_workbook`). 2015's quirks:
  - «Numérico» coded items (`_enumerated`);
  - `TC_…` catalog rows (`Catálogo` only under «Descripción por catálogo»);
  - `b` for the blank row;
  - `Ver catálogo` headers.

  Any change must keep the 2010/2015/2020/2025 parses byte-identical: dump them as JSON
  before and after (4a did, after every parser change).
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
  (`_LEGACY_NA`) knows. State 01 has no `N/D`, so only a 32-state run covers it.
- **The legacy `load_census` crashes in states 08/15/16** (`impute_collective`'s
  `if pd.NA == 0`). `load_cpv_census` uses the NA-safe port; the equality test swaps it into
  the legacy chain for those states.
- **`_labels_for`** compares only `_LABEL_KEYS`. Between 2020 and 2025, 7/22/5
  (viviendas/personas/migrantes) shared columns label differently.
- **Core scope**: a core entry with `Tablas` applies only to those tables (`_in_scope`;
  `TAMLOC` is microdata-only). `CVE_AGEB`/`CVE_MZA` exist only as harmonized names.
- **Core edits** change the verbatim copies in the generated YAMLs. Rerun `--variables`
  or `test_core_yaml_contract` fails. Core entries are copied **as scoped**
  (`cpv._scoped_entry`: `Recodificar` → `Alias` for its editions).
- **Aggregate sentinels**: `build_cpv._AGG_SPECIALS` per edition (2020 `*`/`N/D`/`N/A`,
  2010 `*`/`N/D`). 2000/2005 need theirs (4b).
- **`ageb_14` (2020) is cp1252**; the 2015 CSVs are cp1252 too (one ASCII file sniffs
  UTF-8). The sniff handles both.
- **Metadata modes need the full mirror** (`--schema-map`, `--variables`, `--report-only`
  rewrite the 32-state outputs). The Mac has it now (`data/parquet`), and so does `wsl`
  once the Mac-built files are copied.
- **On the Mac, `rm` and `cp` are aliased to ask for confirmation**, which hangs
  non-interactive commands; use `/bin/rm -f` and `/bin/cp -f`.
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
