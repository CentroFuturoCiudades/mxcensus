# CPV family — session handoff

This file holds the **current state only**: status, hosts, next candidates, open questions
and the gotchas to carry forward. The history is elsewhere: [`PLAN.md`](PLAN.md)'s unit
table (one row per unit, with its gate and result, and the narrative of the user's choices
under it) and one `STEP_<unit>.md` per unit (what was built, decisions, numbers, what was
left). A session starts by checking `git log`/`git status` against the status below.

## Status (2026-10-14)

- **Units 0–6z, 7a–7z and 8a–8g are done.** `cpv-integration` = **8g** (the locality
  lineage's last leftovers: Villa de Pozos a part, absorptions stated the wrong way round, the
  moves between states, the undated statements: `STEP_8g.md`), committed locally, not pushed;
  `main` = **v0.14.0** (7u). 7v–8g wait for the 0.15.0 release (candidate 1).
- **Mirror**: every CPV edition 1990–2025 (897 `cpv_` files), the Marco Geoestadístico frames
  1995–2025 and the Archivo Histórico de Localidades (128 `ahl_` files, snapshot 20260918):
  registry **4276** entries, all uploaded and verified. No unit since 7u changed the mirror
  (the lineage, the CMO bridge and the dictionaries are bundled).
- **Tests**: the Mac's full suite at 8g: **1976 passed, 1 skipped** (34 min).
- **Releases**:

  | version | units | content |
  |---|---|---|
  | 0.5.0 | 0–1e | EIC 2025 (untagged) |
  | 0.6.0 | 2a–2b | CPV 2020 into the family |
  | 0.7.0 | 3a–6c | every edition 1990–2015, MG 1995–2010, the municipal lineage, derived columns, constraints |
  | 0.7.1 | 6d–6e | the 2015/2010 derived columns |
  | 0.8.0 | 6f–6j | derived columns for every edition 1990–2025, MG 2015 |
  | 0.9.0 | 6k–6r | `EDUC_INEGI`, `SECTOR`, tabulado checks, older editions' constraints |
  | 0.10.0 | 6s–6t | the household head's sex |
  | 0.11.0 | 6u–7b | relationship labels, the samples' universe, indigenous households, the EIC 2025's percentages as constraints, places by municipality |
  | 0.12.0 | 7c–7s | 2000's places and minimum wages, ratio constraints, 2000 per dwelling, constraint keys, FD quantities and codes, tabulado checks |
  | 0.13.0 | 7t | the locality lineage |
  | 0.14.0 | 7u | the Archivo Histórico de Localidades |
  | *0.15.0* | 7v–8g | *pending*: every tabulado checked (7v–7z), the lineage's leftovers and the EIC 2015 edition (8a–8d, 8g), CGPV 2000's SINCO groups (8e), the kinship lines and undocumented codes (8f) |

## Hosts

- **The Mac** (`/Users/gperaza/Research/mxcensus`): the full mirror in `data/parquet` (4276;
  the MG 2025 locality layers also in the user cache `~/Library/Caches/mxcensus`), every
  tabulado workbook in `data/dict/tabulados/`, the FDs and catalogs in `data/dict/fd/`, the
  AHL export `data/dict/ahl/AHL.zip`, the SINCO comparison workbook `data/dict/sinco/`;
  poppler installed. Units since 7v ran here only.
- **`wsl`** (`ssh wsl`, `~/mxcensus`): at **v0.14.0** (pull to `main` after the next push), the full
  mirror (4276), `hf` installed and logged in — **uploads run from here only**. Its tabulados
  cache is partial (`check_cpv_tabulados.py` fetches what is missing) and it has **no
  poppler** (`pdftotext`: Censo 2010's 10_01A and the 1990/1995 FD parsers need it). Stale
  leftovers that can be deleted (ask first): `~/mxcensus3c`, `~/sweep_7c.py`/`.json`,
  `~/pytest_7f.log`, `~/pytest_7r.log`, `/tmp/enoe_panel_2012.pkl`, and the untracked
  `build_cpv_*.log` in `~/mxcensus`.
- The user's standing rules: run `wsl` tasks without asking; ask before committing, pushing,
  installing packages or uploading.

## Kickoff prompt for the next session

> Continue the CPV census-family work in this repo (branch cpv-integration = 8g; main =
> v0.14.0). Read docs/cpv/HANDOFF.md first, then agree with me which next unit to
> take (candidates in HANDOFF §Next) before implementing it, following the session protocol
> in docs/cpv/PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without asking; ask
> me before committing, pushing, installing packages or uploading.

## Next: candidates (none decided)

Every edition is in the mirror, derived and constrained, every published sample tabulado
value of 2000, 2010, 2015 and 2020 enters a compared cell, and the locality lineage reads
everything the AHL decides (8g). What is left is the release, small items or INEGI's own:

1. **The 0.15.0 release** (recommended): 7v–8g are on the branch. 7v–7z changed only the
   check script; 8a–8d and 8g the bundled locality lineage (`cpv_loc_lineage()` and
   `cpv_locality_units()`: 8a 49 more links, 8b 232 fewer — five wrong joins of large
   localities gone —, 8c a 2015 edition, 8d 100 fewer with 199 newly confirmed, 8g 28 more
   with 30 newly confirmed — Villa de Pozos a part, the moves between states); 8e 2000's
   `OCUPACION_C_COARSE`; 8f `LINEA_PARENTESCO` and four dictionary entries. Steps: the version
   bump (`pyproject.toml`, `uv.lock`, PLAN/STEP_8g/HANDOFF), the suite (the Mac's at 8g:
   1976 passed), fast-forward `main`, tag `v0.15.0`, push `main`, `cpv-integration` and
   the tag (ask first), pull `wsl`. No data upload.
2. **Conditional small items**: the hand-curated minimum-wage tables
   (`cpv_derived._SALARIOS_MINIMOS`) as a generated YAML, only if a later edition needs one
   (none does: the EIC 2025 publishes no income, the 1990/1995 ITERs no income groups); 8e's
   leftovers (`STEP_8e.md` §Left: the farm laborer boundary 61/91 differs between INEGI's
   coders — documented, kept as INEGI's table; 5190/6290, 0.51%, not placed; no SINCO
   subgroup for 2000).
3. **Not reproducible / nothing to do in the mirror** (documented): the infant mortality of
   2000, 2010 and 2015 (`STEP_7o.md`, `STEP_7z.md`: INEGI's rule is not in the sample); CGPV
   2000's Chiapas (its records are not those of INEGI's tabulados); the 2000/2010/2020
   cuestionario-básico tabulados (the census, not the sample: the ITER covers them, 7g); the
   locality lineage's leftovers (`STEP_8g.md` §Left: the AHL cannot decide them — 278 moves
   unpaired, 31 links on an unverified number, 4 rival claims, codes INEGI reused, the 16
   absorptions MG 2025 still lists, kept by the user's choice; `CONFIRMED` stays per edition,
   8c's question closed by the user).
4. **Ideas not yet scoped** (the session's, not the user's): a user guide for the CPV family
   (loaders, `derived=True`, constraints, the lineage) in `docs/`; a cross-edition ITER panel
   on the stable units (`cpv_municipal_units`, `cpv_locality_units`).

## Open questions for the user

None.

## Gotchas (carry forward)

### Hosts and operations

- **On the Mac, `rm` and `cp` are aliased to ask for confirmation**, which hangs
  non-interactive commands; use `/bin/rm -f` and `/bin/cp -f`.
- **`uv run`** may re-sync `.venv`; use `.venv/bin/python`. Both hosts run pyarrow 24.0.0 /
  pandas 3.0.3, and builds are byte-identical across them.
- **Tailscale SSH can demand a re-login at any time**: a hanging `ssh wsl` that prints a login
  URL needs the user. With Tailscale SSH, `ssh wsl 'nohup … &'` does not return until the job
  ends: use `run_in_background`.
- **Killing and waiting**: `pkill -f` over ssh matches the ssh command line too and kills its
  own session (exit 255) — `pgrep`, then kill by PID; `until ! pgrep -f 'pattern'` matches its
  own shell and never ends — wait with `while kill -0 PID`.
- **INEGI downloads** drop connections and truncate ZIPs (`fetch_zip_verified` retries);
  soft-404s come back as HTTP 200 + `text/html`; some files exist but are not in the
  file-listing API (2015's `doc/eic2015_catalogs.zip`): try the obvious URL. INEGI serves
  ~0.5 MB/s per connection (prefetch in parallel) and at times throttles `wsl` (~50 kB/s): copy
  the Mac's `data/cache` ZIPs over (`scp` into `wsl:mxcensus/data/cache/`); the builds read
  them as cached, byte-identical. Files INEGI removed: the Internet Archive (CDX API).
- **Mac → `wsl` copies**: macOS `tar` adds AppleDouble `._*` sidecars (397 junk
  `._mg_*.parquet` nearly got uploaded in 6h): use `COPYFILE_DISABLE=1 tar …`, or delete `._*`
  on `wsl` before the dry run. Tailscale carries ~0.6 MB/s; check SHA-256 against the
  registry on `wsl` after copying. Code moves by `git bundle` over `scp` when not pushed.
- **Registry**: `--update-registry` upserts; the diff must be additions only (`git diff
  --numstat`).
- **Upload**: `upload_hf.py upload` from `wsl` only, never with `--delete`; dry-run first and
  count the actions (exactly the new files). `verify` HEADs every registry URL (~15 min): run
  it in the background; a timeout counts as "missing", so re-check misses by hand.
- **Sweeps through `POOCH`** fetch any file missing from the user cache from the bucket (the
  `wsl` user cache is empty: patch `mxcensus.data._registry.POOCH.fetch` to read
  `data/parquet`, as `check_cpv_tabulados.run` does); the tests' `local_mirror` fixture reads
  `data/parquet`. The CLI offers only registered files.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB on the Mac for the EIC 2025; the
  tabulado report ~8 GB; the 2015 build 2.7 GB on `wsl`.
- **Frozen legacy path**: `scripts/build_data.py`, `aggregate.py`, `extended_*.py` and the
  legacy `iter_`/`resargebub_`/`personas_`/`viviendas_` files are pinned by
  `tests/test_census_legacy.py`. They were built with pandas' default NA strings plus
  `na_values=["N/D"]` (`N/D`/`N/A` are NaN there, verbatim in `cpv_*`; the comparator's
  `_LEGACY_NA`; state 01 has no `N/D`, so only a 32-state run covers it). 6c's NA guard in
  `aggregate.impute_collective` made `load_census` equal `load_cpv_census(2020)` in all 32
  states.

### Builds and dictionaries (`build_cpv.py`, `_dict_fd.py`, `_dbf.py`)

- **CPV gids are chronological** and shift whenever an older edition joins (never hard-code
  one; code and tests read `cpv_schema_map()` / `_gid(table, period)`). Now: `personas` 1990
  `g01`, 1995 `g02`, 2000 `g03`, 2005 `g04`, 2010 `g05` + `g06` (state 15's lower-case
  `tam_loc`), 2015 `g07`, 2020 `g08`, 2025 `g09`; `viviendas` 2000 `g01` … 2010 `g03`/`g04`,
  2015 `g05`, 2020 `g06`, 2025 `g07`; `migrantes` 1995 `g01`, 2000 `g02`, 2010 `g03`/`g04`,
  2020 `g05`, 2025 `g06`; `hogares` 2005 `g01`; `iter` 1990 `g01` … 2005 `g04`, 2010 `g05`,
  2020 `g06`; `ageb` 2010 `g01`, 2020 `g02`; `estimaciones` 2025 `g01`. **Delete the
  `variables_cpv_*_g*.yaml` before `--variables`** when the gids shift.
- **Order of the metadata modes**: `--dictionary` → `--schema-map` → `--variables` →
  `--validate` (2 min with `--jobs 6`, 0/897). Metadata modes need the full mirror (either
  host).
- **The core** (`variables_cpv_core.yaml`) is hand-curated, never regenerated: a core edit
  changes the verbatim copies in the generated YAMLs, so rerun `--variables` or
  `test_core_yaml_contract` fails. Entries are copied **as scoped** (`cpv._scoped_entry`:
  `Recodificar` → `Alias` for its editions); `Tablas`/`Periodos` scope an entry (`_in_scope`;
  `TAMLOC` is microdata-only; `CLAVIVP` 2015–2025); `CVE_AGEB`/`CVE_MZA` exist only as
  harmonized names.
- **Dictionary sources**: INEGI's FD workbooks beat the RNM DDIs (632 for 2020 and 214 for
  2015 are Nesstar exports with collapsed ranges and no missing flags; `ddi_id` is kept for
  reference). The 2000 FD is a PDF (`_dict_fd.parse_fd_text` on `pypdf` text; a layout ends
  at «Total de caracteres», `_PDF_END_RE`); 2005's a split-layout `.xls`; 1990/1995's FDs, the
  1990/1995 ITER descriptors and the Conteo 1995's catalogs are (encrypted) PDFs read with
  poppler (`pdf_text`/`pdf_words`; `parse_fd_1990_text`, `parse_fd_1995_text`,
  `parse_iter_fd_tsv`, `parse_catalogs_1995_text` — its per-state municipal and
  metropolitan-area sections skipped, `_CAT95_SKIP`; an FD field «Ver catálogo de X» takes
  `match_catalog(X)`). FD misspellings of data columns go in `_FD_RENAMES`.
- **`_dict_fd`** reads `.xlsx` and legacy `.xls` (BIFF8 and Excel 95's BIFF5, `read_workbook`).
  2015's quirks: «Numérico» coded items (`_enumerated`), `TC_…` catalog rows, `b` for the
  blank row, `Ver catálogo` headers. Any parser change must keep the 2010/2015/2020/2025
  parses byte-identical: dump them as JSON before and after.
- **How an FD item gets its type** (FDs without a `Tipo` column: 2000, 2005, 2010):
  `_dict_fd._quantity` — one labelled range row, or a header range plus sentinels, is a count;
  several ranges a code list. Then the reviewed tables in `build_cpv.py`, each raising on what
  it does not expect: `_QUANTITIES` (zero-padded or catalog-like FD ranges that are counts or
  amounts: 1990 `NUM_PERS`/`INGRESO`, 2000 `NUMPERS`/`HORTRA`/incomes, 1995 incomes),
  `_CODES` (code spaces the FD makes numbers: 2000's municipalities, languages, religion,
  occupation…), `_SENTINELS` (a numeric sentinel labelled with its own code), `_UNDOCUMENTED`
  (8f: a categorical code the FD leaves out — 1990 `TIP_HOGAR` 6, 2000 `ABANESCO` 8, 1995
  `ZONA` 06/07; a new one stops `--variables` until explained), `_CODE_GROUPS` (items the FD
  documents by groups of codes: 1990 `CVE_PAR`, 2000 `OTROPARE_C`), `_BLANK_ZERO` (1990's
  unlabelled 0 «not asked» → «Blanco por pase») and `_ELLIPSIS_RE` (the 2005 FD's «: :» rows).
  1990/1995 numeric ranges are reconciled with the data (`_reconcile_ranges`).
- **Review dicts** in `build_cpv.py`: a duplicate key in a dict literal silently drops a pair;
  a test refuses duplicates.
- **Aggregates' dictionaries**: `parse_indicator_csv` reads `00..9999999999` as a count, other
  zero-padded ranges as codes; averages' decimals come from the values (`label_frame` makes
  non-integral columns `Float64`). Sentinels per edition in `_AGG_SPECIALS` (2020 `*`/`N/D`/
  `N/A`; 2010 and 2000 `*`/`N/D`; 2005, 1995, 1990 `*`).
- **The ITER crosswalk** (`cpv_iter_crosswalk.yaml`) is generated (`--crosswalk`), never
  hand-edited: `_XW_PERIODS` newest first, older editions auto-pair by normalized description
  (`_XW_DESC_PERIODS`; rejects in `_XW_UNPAIR`), reviewed `_XW_PAIRS_RENAMED`/`_XW_PAIRS_KEPT`/
  `_XW_NOTES`; `cpv._renames(table, periods)` renames only the frame's own edition. A pair by
  description can be wrong (2000's `VP_CCUART` «con un dormitorio» is one room without the
  exclusive kitchen): check a paired indicator's level against the sample before trusting it.
- **Encodings**: `scripts/_dbf.py` sniffs cp1252/cp850 from the bytes (INEGI's driver byte
  lies); `ageb_14` (2020) and the 2015 CSVs are cp1252 (one ASCII file sniffs UTF-8).
- **Generated, never hand-edited**: `cpv_loc_lineage.csv.gz` (`build_loc_lineage.py`),
  `cpv_mun_lineage.yaml` (`build_geo_crosswalk.py` from the `mg_mun_*` of 1995–2025, all on
  disk; rebuild after any MG rebuild; a test compares it with a rebuild), `cpv_cmo_sinco.csv`
  (`build_cmo_sinco.py`: the Internet Archive's copy of INEGI's comparison workbook, sha256
  pinned — the URL must keep the `id_` suffix — and ENOE's 2012-T2/T3 COE1;
  `test_cmo_sinco_rebuilds` checks it byte for byte where `data/dict/sinco/` exists).

### Loaders, keys and geography (`cpv.py`, `cpv_aggregates.py`, `mg.py`)

- **Derived keys depend on file order**: 2000/2005's keys are derived (`cpv._composite_keys`;
  `load_cpv` never adds them) and 2000's `ID_PERSONA` is the person's order in the household;
  1990's `ID_VIV` ends in the folio's occurrence (`_folio_occurrence`; persons are not in
  `NUM_PER` order). Never re-sort a 2000 or 1990 person file before deriving keys.
- **Unpadded 2015 codes**: `ID_VIV` (11 digits in states 01–09), `ID_PERSONA`, `CLAVIVP`; the
  core `CLAVIVP` `Alias` covers raw validation and labels; `harmonize=True` pads all three
  (`cpv._CODE_PAD`). Compare 2015 codes as numbers.
- **Censo 2010's keys are state-scoped serials**: keyed loaders refuse several states unless
  `harmonize=True`, which builds national keys (`cpv._national_keys`). Its `TAM_LOC` (4
  classes) is not `TAMLOC`; its aggregate headers are lower case (matched case-insensitively);
  the aggregates' `TAMLOC` is a string class code (`_AGG_CODES`), the ITER's a 14-class scale.
- **Harmonization is table-scoped** (`_renames(table)` = `_RENAME_CORE` + `_RENAME_TABLE`): the
  2015/2020 `ENT`/`MUN` → `CVE_*` everywhere; `ENTIDAD`/`LOC` only in ITER/AGEB; `AGEB`/`MZA`
  → `CVE_AGEB`/`CVE_MZA` only in AGEB. `CVEGEO` concatenates the leading `_GEO_PARTS` (5, 9
  or 16 characters; totals keep zero parts). One edition per call: stack with
  `pd.concat(..., names=["PERIOD"])`.
- **1990/1995** publish person files only: their dwellings are built from them
  (`_DWELLINGS_FROM_PERSONS`), so `load_cpv(table="viviendas", period=1990)` raises and
  `cpv_derived._frame_group` labels them with the person group; 1995's dwelling frame counts
  its persons into `NUMPERS` (`_OCCUPANTS_FROM_PERSONS`). 1995's `FACTOR` exists only under
  `harmonize=True` (`_FACTOR_FROM`: persons `FAC_POB`, emigrants `FAC_VIV`). The Conteo's
  `FAC_VIV` adds up to `VIVPAR_HAB` and `FAC_POB` to `OCUPVIVPAR` in 31 states (not Chiapas,
  whose weights carry its official total), calibrated apart; its 1,151 employed with a blank
  monthly income have `FAC_POB` 0. 1990 writes 0 for «not asked»; its income is in old pesos
  (÷ 1,000; ~1% look written in thousands).
- **Frames with a household level** (2000/2005): their person frames carry `ID_HOG` in the
  index; drop duplicate `ID_VIV`s only on dwelling frames. CGPV 2000's dwelling file has one
  row per household (the first household's row stands for the dwelling: `PRIMER_HOGAR`); the
  Conteo 2005's dwelling rows are dwellings and its households a table of their own.
- **Labels**: `_labels_for` compares only `_LABEL_KEYS` (between 2020 and 2025, 7/22/5
  shared columns of viviendas/personas/migrantes label differently); `variables_cpv_labels`
  includes every in-scope core entry whatever the edition calls the item (1995's sex is
  `P3_5`), so constraint categories and the code-list test take only the group's own columns.
- **ITER quirks**: 1995's one- and two-dwelling localities exist only as its 9998/9999
  aggregates; a `LONGITUD` without digits marks a spilled name (2000: 2 rows, 1995: 7), which
  `_repair_spilled_names` shifts back; 1990/1995 truncate their averages and percentages,
  2000–2020 round (compare within 0.005 + ε).
- **MG**: national-ZIP editions name their codes their own way (`_ENTITY_COLUMNS`/
  `_ENTITY_PREFIX_COLUMNS`); a layer without `.prj` takes the edition's CRS (`_edition_crs`);
  attribute names stay INEGI's. MG 2015 is one product per state (`MgEdition.products`), 12
  layers + `ti` (named `NNterritorioinsular`), LCC on ITRF92; Empalme (26025) has a second,
  empty polygon.

### Derived columns (`cpv_derived.py`)

- **How a derivation works**: from the **raw** codes before labelling, in the **2020 code
  space** (`_RECODE[period][item]`), mapped with the frozen legacy YAML maps and dtypes (2020
  = legacy by construction). A new edition or item: add the edition to the derivation's
  `periods`, `_RECODE` entries for renumbered codes, the reviewed `_GAPS`/`_EXTRAS`/
  `_OWN_CODES` rows for `test_source_codes_match_2020`, then load every state with
  `derived=True`: an unknown code raises everywhere (dummy sets mark it missing, and a
  bridge must map codes, not go through `_mapped`, whose `fillna` would make an unknown code
  a blank — 8e's `_ocup_cmo`).
- **A column may have several derivations**, one per set of editions (2010/2015
  `DHSERSAL_*` without IMSS-BIENESTAR, 2015's commute dummies, `LINEA_PARENTESCO`'s six);
  `cpv_derivations()` lists it once per derivation. Derivations in an edition's own code space
  skip `_RECODE`. Module names are shared: a shadowed constant (`_EMPLOYED` vs
  `_EMPLOYED_CELLS`, 6o) silently blanked 1990's hours once.
- **A numeric derived column** (`TOTCUART_INEGI`, `Int64`) may be missing; code iterating
  `derived_dtypes` must not assume `.categories`.
- **Columns from other files**: the loaders attach and then drop what `derive` needs — the
  household head's `SEXO` on the 2000/2005/2010 dwellings and the 2005 households
  (`_attach_heads`), the dwelling's `TIPOHOG` on the persons of 2000 and 2010–2025 and its
  `CLAVIVPA` on the 2005 households (`_attach_dwellings`), each household's members for
  `HOG_IND`/`HOG_AFRO` on the dwelling records (`_household_members`, column-projected reads;
  `derive(members=)`; `_per_record` matches ignoring zero padding; Censo 2010's raw serials
  need the same `harmonize` on both sides). Synthetic frames in the tests must carry them
  (`tests/test_cpv_derived._derive_dwellings`, `_HEAD_ALONE`, `_HOUSEHOLD_ITEMS`).
  `HOG_IND` is on both frames: a person ↔ dwelling join needs a suffix.
- **Household derivations** (`household=True`) get each record's household in
  `src[_HOUSEHOLD]` (entity + `ID_HOG` 1995–2005, entity + `ID_VIV` from 2010); a synthetic
  person frame needs the relationship item, `SEXO` and the key or its parts, and exactly one
  head per household (`_each_a_household`), or `derive` raises.
- **Relationship items** are own-code per edition: the `PARENTESCO` alias resolves to the
  first of `PARENTESCO`/`PARENT`/`OTROPARE_C`/`P3_4` a frame has (heads, `_HEAD_CODES`;
  indigenous households, `_IND_CODES`, each edition's own definition — INEGI's dictionary
  wording is wrong both ways, `STEP_6w.md`). `LINEA_PARENTESCO` (8f) names its items
  instead: 1990 `CVE_PAR` (the first digit is the relationship, CATPAREN's word what was
  written: 702 «huésped» lives alone), 2005 `PARENT`, 2010 `PARENT` + `OTROPARE_C`, 2015
  `PARENT_OTRO_C`, 2020/2025 `PARENTESCO`; synthetic person frames of those editions must carry
  them. Its 2010 «Otro parentesco» holds what INEGI's 12_04A counts collateral (08 without a
  detail) and not specified (623): the check splits them back on `OTROPARE_C`'s blank.
- **INEGI's rule vs the legacy one**, side by side where they differ: the unspecified entity
  (legacy `ENT_PAIS_*_CAT` → `OtraEnt`; `ENT_PAIS_NAC_INEGI`, `LUGAR_*` and the
  `*_INEGI` places → «No especificado», as INEGI's tabulados); disability (`DISCAPACIDAD`/
  `LIMITACION`/`SIN_DISC_LIM` INEGI's, `DIS_CON`/`DIS_LIMI` legacy); education (`EDUC_INEGI`:
  técnica after primaria apart, as the ITER 1990–2020; the frozen `EDUC` and legacy cells
  count it «Primaria_com»; INEGI's own products disagree, `STEP_6k.md`); religion
  (`RELIGION_INEGI`, Censo 2010 only, beside `RELIGION_CAT`'s 2020 grouping).
- **Censo 2010's items**: limitation (`DISCAP1`–`8`, yes/no per activity) is not 2020's
  disability (its ITER's `PCLIM_*` share 2020's names); the pointer pairs `IDMADRE`/`IDPADRE`/
  `IDCONYUGE` + `…C` (88 not here, 99 NE; «99 + blank code» is **not specified**, INEGI's
  12_01A, 6q); the place of work `LTRABPAI_C` holds both the entity and the country catalogs
  (its 999 the entity's «no especificada»), and the municipality items hold every Mexican
  answer, the own one too.
- **Places by municipality** (`_lugar`): the own entity without a municipality raises; the
  school and work items are asked of the students and the employed, unspecified ages
  included (INEGI's tabulados leave those out: cells and checks keep the age condition).
  2020's FD names no catalog for `MUN_TRAB` (`_REF_WITHOUT_CATALOG`).
- **Minimum wages** (`_SALARIOS_MINIMOS`): hand-transcribed daily wages in cents and area
  tables; the monthly wage is daily × 30; 2015's catalog has Coacoatzintla (30-036) where the
  DOF has Coatzintla, kept (the tabulado follows the catalog); 2020's border zone includes San
  Quintín (02-006); compare in cents (5 × 1,675.20 = 8,376 lands in «3 a 5»). 2000's groups
  are bounded otherwise (`_SM_2000` via `_period_dtypes`): a cross-edition stack needs a map.
- **Occupation codes**: 2010 `OCUACTIV_C` 4-digit (CUO ≈ SINCO 2011), 2015 3-digit SINCO 2011,
  2020/2025 SINCO 2019; the group is the first two digits, 59 → 52; 2000 through the CMO
  bridge (8e).
- **Rooms**: 2000's `TOTCUART` counts the kitchen, its ITER's rooms do not
  (`TOTCUART_INEGI`; «No especificado» also starts with «No»: match full labels); the «Otro»
  dwelling classes (2010 5–7, 2020/2025 07–09) have no rooms recorded.

### Constraints (`cpv_constraints`, `cpv_ratio_constraints`, `load_cpv_estimaciones`)

- **Keys are the published columns** (`_published_name`): an older edition's kept pair is
  keyed by its own ITER column; `_EDITION_CELLS` keys stay canonical inside (a test that
  iterates them maps each through `_published_name`). `Comparable: false` in the crosswalk
  flags the older editions' columns, never the newest's.
- **A cell is an AND of per-item category lists**: «any of several items» needs a derived
  summary column (`INGR_OTROS`, `DHSERSAL_ISSSTE_T`). A cell carries its indicator's age
  condition even when the item is asked of that age only (unspecified ages answer).
- **Two person totals**: `POBTOT` (legacy) and `POBHOG` (every sampled person in both); a fit
  uses one. Censo 2020's weights add up to `POBHOG`, the EIC 2025's to both, 2000/2010's to
  neither; 1990/1995 use `OCUPVIVPAR`.
- **Dwellings**: CGPV 2000's dwelling indicators count the first household's row
  (`_PER_DWELLING`), its household indicators every row; 1990/2000's «Otro» classes carry the
  items, so their cells have no «Vivienda» condition (`_EVERY_CLASS`); the Conteo 2005's
  household indicators live on `cpv_constraints("hogares", 2005)`.
- **The EIC 2025's percentages** become counts (`load_cpv_estimaciones(counts=True)`,
  `_PERCENT_BASES`; a base may be a tuple summed — always go through `_base_parts`). A derived
  count is off Σ `FACTOR` by the rounding, so tests compare the **share** within 0.005. Bases
  are found on the data, never from the description (`PEA_F` of the PEA, `VPH_*` of
  `VIVPARHAB_C`, five-year ages of the specified-age population); a base may be a published
  count without a cell (`HOG_MEN_ALIM`); «No aplica» stands for a zero (compare published
  values only). The 11 without a count and the averages are ratio constraints. The base
  search (`STEP_6y.md`): Σ `FACTOR` per published geography over every candidate cell, the base
  whose share is within 0.005 at all of them; the disability by age is a share of the
  disabled of specified age (an unpublished base).
- **Ratio constraints** (Σ w·N = r / scale · Σ w·D) are separate from `cpv_constraints` (no
  cell): `known` columns decide who leaves both sides, any other missing value counts 0;
  `cpv_ratio_terms` reads the **labelled** frame (raw codes would count sentinels).
- **Settling a definition**: weighted state fits mislead; use the municipalities where the
  sample is the census — `FACTOR` 1 for everyone (Censo 2010: 767, 2020: 220), with `POBHOG`
  and every age/sex constraint equal to the ITER («strict»: 2000 51, 2010 233, 2020 130).
  There every 2010 constraint is exact; what still misses is INEGI's census processing (2000's
  imputed schooling, 2020's swaps in affiliation and religion). Elsewhere each edition has its
  sample-vs-census band (2000's census `POBTOT` includes the population without
  characteristics; the 2005 sample is unweighted; head's sex up to 1.5–2.6 points, `STEP_6s.md`).
  Even there a sample's ages may differ from the ITER's (Oaxaca 20-228: 510 persons of 15+
  against 534), so a check of an average must also match its age group's count.
- **2020 departs from the frozen legacy cells** where INEGI's ITER does (`PCLIM_*` on
  `LIMITACION`, `PCDISC_*` with the unknown degree, `PCON_DISC`/`PCON_LIMI`/`PSIND_LIM`,
  `PNACOE`/`PRESOE*` without the unspecified entity, education on `EDUC_INEGI`). CGPV 2000's
  own `PNACOENT`/`P5_RESO95` count the born and the residents abroad, its religions the 5+;
  the Conteo 2005 keeps the legacy cells (no unspecified entity).

### Tabulado checks (`scripts/check_cpv_tabulados.py`)

- **Running it**: the full report (every edition, 32 states) takes ~60 min (~8 GB); a unit
  changing one edition runs that edition alone and splices its section into
  `TABULADOS_REPORT.md`, and a scratch harness can filter `ck.CHECKS` to the checks at stake
  before `ck.run([period], list(range(1, 33)))` (8f). `--periods`/`--states` for a quick look;
  the nation, `ByOrigin` and by-size checks need all 32 states (a partial run drops
  `by_origin` checks). The script reads each workbook once; the tabulados cache is
  `data/dict/tabulados/{period}/` (2000 `C2K*.xls` BIFF5, 2010/2015 `.xls`, 2020 `.xlsx`,
  2010's 10_01A a PDF read with poppler). A check's title and note are in the report: change
  them only with a regenerated report.
- **The coverage probe** (`--coverage`, `test_every_published_value_is_read`): it swaps `_num`
  for a tracing one, so a reader must parse published values through `_num` and keep them in
  plain Python arithmetic (`_Traced`; NumPy or `float(x)` drop the trace). CGPV 2000's layout:
  every number from the nation's row down counts as published.
- **The conversion cache** (`_CONVERTED`): `_numeric`, `_code`, `_age` and `_cat` return one
  converted column per frame (cleared per state); never modify a frame or a converted column
  in place. `_part` sums on arrays (a missing mask value is False; CGPV 2000's masks carry
  `pd.NA`).
- **Keys repeat across editions** (2015's 10-02 is commute times, 2020's the place of school):
  key tests on (period, check). `Check.tolerance` (per state, 0 = the nation) only for a
  documented difference of INEGI's own (2000 MI04's four states, 2010 08_10A's State of México,
  2020 10-02's Tabasco).
- **Category readers**: `_words` drops digits («2 ocupantes» = «3 ocupantes»): numbered
  categories use `_tokens`. INEGI's tabulados leave out unspecified ages (999) from
  age-defined universes and leave out empty rows (`_by_dims` reads them as zeros); a Censo
  2010 workbook may name its states without codes (`_STATE_NAMES_2010`) or publish some states
  and «Resto de las entidades» (`_REST` 98, `ByOrigin`); every 2010 `ESTATAL` workbook dated
  2013 is by locality size.
- **Universes**: the dwelling tabulados leave out `CLAVIVP` 5–7 (2010), 07–09 (2020), 7–9
  (2015); occupants = Σ `FACTOR` × `NUMPERS` (`Check.weight`); the EIC 2015's dwellings that
  cook name a place or a fuel; the owners' sex joins the person file (`_with_owners`: 99 = not
  identified); CGPV 2000 counts every private dwelling once (`NUMHOGS` blank = 1), its
  «hogares» table = the household rows with the members' counts (income 999999 NE, 999998 the
  top code); fertility = the women's age at the census, the denominator without children born
  alive 98 or the last child's year 9999; the EIC 2015's women with children are those who gave
  `HIJOS_NAC_VIVOS` < 98, its unpaid work hours per activity 0 none and 999 not specified (a
  mix of both is none); INEGI writes 0 for an average of nobody. Averages are
  `Weighted(mask, values)` parts with `unit="average"`.
- **CGPV 2000**: counts exact in every state but Chiapas (`_COUNTS_2000`, by size
  `_SIZED_COUNTS`; its records are not those of INEGI's tabulados), shares within 0.04 points;
  «M.I.» = muestra insuficiente (missing); a row of every age is `_ALL`, never (0, 130);
  disability types classify `DISOTRA_C` (`_DISABILITY_TYPES_2000`); the migrants file:
  `MPAIRES_C` 700 returned, `MLUGORI_C` the state left.
- **Infant mortality**: Censo 2020 counts `EDAD_MORIR_TD` 0–364 (98 «menos de un año» is
  INEGI's code for an unknown age under one); 2000/2010/2015 are not reproducible from the
  sample (checked within 1.9/1.0/1.8 per 1,000).

### Locality lineage and AHL (`build_loc_lineage.py`, `cpv_geo.py`, `ahl.py`)

- **The lineage is generated** from INEGI's AHL (`data/dict/ahl/AHL.zip`): an AHL record is
  filed under the locality's **last** code; a census row's change already shows in that
  census's ITER. `EDITIONS`' cuts were found on the data (`STEP_7t.md` §Dating; 2015 = the MG
  2015 frame's 30 April 2015, 8c): a new edition needs its cut found the same way before the
  links are re-dated. The edition lists live in `cpv_geo._LOC_PERIODS`, the build's
  `EDITIONS` and the tests' `_LOC_PERIODS`/`_CUTS`/`_ITER_PERIODS` (the `_REAL` test spells
  the ITER periods out).
- **`--check`** needs every ITER and the MG 2015/2020/2025 `l`/`lpr` layers: on the Mac, pass
  `--mirror` a scratch directory of symlinks to `data/parquet`'s `cpv_iter_*`, `mg_l_*`,
  `mg_lpr_*` and the user cache's `mg_l(pr)_2025_NN` → `LOC_LINEAGE_REPORT.md`.
- **The parser** (8a/8d): `name_match` levels 3/2 exact (abbreviations, ordinals, generic
  words), level 1 a misspelling unless `fuzzy=False`, a placeholder matches nothing; the
  `Resolver` is two-pass (exact first). A new statement shape: a pattern in `_PATTERNS` (same
  name to pool) and a case in `test_loc_lineage_parser`; a whole-locality move keeps `_WHOLE`
  in front, or a part's move reads as a `code` link. Then read the table's diff against the
  bundled file link by link (8a caught three of its own bugs that way).
- **The corrections, in order** (8b–8d): `repair_lists` after `parse` (a slip-apart twin; a
  code of the wrong length only with `records`), a self-named statement no other record
  states dropped, then in `lineage` the same-day rule, the joined-and-left cancellation, the
  census rule (by **edition**: `Habitantes` is the ITER up to the cut; «*» is also the Conteo
  1995's reserved count; 2015 reads the next census, `_census_from`), the rival claims, then
  the new-municipality rule (after the rivals). A moved or merged link keeps its statement's
  `DATE` (`ahl._copies` reads it). The check's flags read every edition of a span (`within`)
  and the earlier edition's from the census before it (`upto`): a new edition between two
  censuses must keep both. `record_links(…, ends)` orients a duplicate only with
  `ends`; `check(…, stars)` explains *not listed* only with `stars`. Judge a rule against every
  edition's codes and the unexplained codes it creates, not only the units it was meant for.
- **8g's additions**: `Link.row` (the stating row's `INDICE`) lets `date_statements` date an
  undated row (after `parse`, before `repair_lists`; it sets the rows' `day` too) — a window
  that crosses a cut stays undated (the 2005 cut is 30 October, after the Conteo's day).
  Moves between states: the tolerant `_EDO`/`_EMUN`/`_SKEYS` forms of `pasa_estado`/
  `viene_estado` (a new shape: add a key form and diff the old matches, none may be lost),
  `pasa_clave`/`viene_clave`, the state-only `*_estado_sin` (`state_code`, `_STATES`).
  `pair_unkeyed(…, xy)` keys the unkeyed statements by a municipality **or a state** prefix;
  a state-wide one-side match needs the AHL's coordinates (`build` passes `points(path)`;
  without `xy` it links nothing). `lineage`'s order: *a part* first, then the same-day,
  joined-and-left, moved-and-back rules, *the other way round*, the census rule, the rival
  claims, the new municipalities. The AHL's coordinates are rough for old records (8a's
  municipality-level one-side pairs lie up to 166 km apart, and the 248 unpaired moves have
  candidates within 1 km of each other): they serve the state-wide match only (the only
  namesake within 10 km), not the pairing inside a state.
- **The AHL mirror is a snapshot** (`ahl_{table}_{YYYYMMDD}_{NN}`, `_ahl_catalog.SNAPSHOTS`):
  a new INEGI export is a new snapshot (`build_ahl.py` refuses one not listed), and the
  bundled lineage should be rebuilt from it in the same unit (`ahl._copies` reads the bundled
  lineage whatever the snapshot); `_SHIFTED` (11 rows) is snapshot-specific but guarded.
