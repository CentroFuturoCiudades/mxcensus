# CPV family — session handoff

**Status (2026-10-08): units 0–6g are done. `main` = v0.7.1 (through 6e); `cpv-integration`
is ahead by the units of this session (6f onward), committed locally, not pushed. The user
asked for the four post-6e candidates in one session, one unit each: 6f and 6g (done), 6h
the EIC 2015 frame, 6i the 2000/2005 derived columns.**
- **Released** (registered, uploaded, verified): every edition 1990–2025 (897 `cpv_` files)
  and the Marco Geoestadístico 1995–2025 frames; registry **3751** entries
  (`STEP_6b.md` §Release batch).
- **Derived columns** (6b, 6d, 6e, 6f): `derived=True` on `load_cpv_personas/viviendas/survey`;
  `cpv_constraints(table, period)` gives the constraints per edition (`STEP_6b.md`).
- **6c** (review of every pending decision with the user, `STEP_6c.md`): legacy NA guard,
  1995 `FACTOR`, INEGI's `DISCAPACIDAD`/`LIMITACION`.
- **6d** (`STEP_6d.md`): the 2015/2010 derived columns. Recodes for `DHSERSAL`, `CONACT`,
  `SITUA_CONYUGAL` (2010 from `ESTCON`) and `NIVACAD`; no `DHSERSAL_IMSS_BIENESTAR` in
  2010/2015; 2015's own commute dummies; 2010's `LIM_ACTIVIDAD`; 2010 constraints 91 → 126,
  with the 2010 ITER's own limitation indicators (`_EDITION_CELLS`).
- **6e** (`STEP_6e.md`): 2015/2010 birthplace and residence five years earlier (2010 from
  its split entity/country items), the partner pointer (2010 from its pointer pairs), 2015
  `IDENT_MADRE/PADRE_CAT`, new `MADRE_EN_VIVIENDA`/`PADRE_EN_VIVIENDA` (2010–2025), 2015's
  own `FINANCIAMIENTO_*` dummies; 2010 constraints 126 → 138. Checked against INEGI's
  tabulados in all 32 states.
- **6f** (`STEP_6f.md`): 2015/2010 `OCUPACION_C_COARSE` (SINCO group; 59 → 52, as SINCO
  2019) and `ACTIVIDADES_C_COARSE` (SCIAN sector), both = INEGI's 2015/2010 tabulados by
  division and sector in all 32 states; 2010 `RELIGION_CAT` (2020's grouping: the
  neo-Israelites are evangelical); 2010 constraints 138 → 142.
- **6g** (`STEP_6g.md`): INEGI's `PSIND_LIM` rule (no difficulty of any degree, no mental
  condition; NE only when all seven answers are unspecified) as `SIN_DISC_LIM` (2020/2025)
  and the CPV `PSIND_LIM` cell; exact in every EIC 2025 state and municipality.

Design: [`PLAN.md`](PLAN.md). Recent units: [`STEP_6g.md`](STEP_6g.md), [`STEP_6f.md`](STEP_6f.md), [`STEP_6e.md`](STEP_6e.md),
[`STEP_6d.md`](STEP_6d.md),
[`STEP_6c.md`](STEP_6c.md), [`STEP_6b.md`](STEP_6b.md), … [`STEP_0_probe.md`](STEP_0_probe.md).

**Host state.** The Mac and `wsl:~/mxcensus` both hold the full mirror (3751 registered
files); `wsl:~/mxcensus` is at v0.7.0 (pull v0.7.1 before running 6d/6e code there).
`wsl:~/mxcensus3c` (3c's code copy) can be deleted.

## Kickoff prompt for the next session

> Continue the CPV census-family work in this repo (branch cpv-integration; main = v0.7.1).
> Read docs/cpv/HANDOFF.md first. Every planned unit is done; agree the next unit with me
> (candidates in HANDOFF §Next) before implementing it, following the session protocol in
> docs/cpv/PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without asking; ask me
> before committing, pushing, installing packages or uploading.

## Next: this session's remaining units

1. **6h — the EIC 2015 frame** (3d leftover, `STEP_3d.md`): MG 2014 v6.2 (Aug 2014, 2,457
   municipalities = the EIC 2015's) is the likely frame; its UPC is unknown. Candidates
   downloadable: MG 2013 v6.0 (702825292829), MG junio 2016 (702825217341).
2. **6i — derived columns for 2000/2005** (their items differ the most).

## Open questions for the user

None pending: 6e's decisions were taken with the user (`STEP_6e.md` §Decisions).

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
- **Harmonization is table-scoped** (`_renames(table)` = `_RENAME_CORE` + `_RENAME_TABLE`):
  - the 2015/2020 `ENT`/`MUN` → `CVE_*` everywhere;
  - `ENTIDAD`/`LOC` only in ITER/AGEB, and `AGEB`/`MZA` → `CVE_AGEB`/`CVE_MZA` only in AGEB.
  - `CVEGEO` concatenates the *leading* `_GEO_PARTS`: 5, 9 or 16 characters, total rows
    with zero parts.
  - Editions load one per call; stack with `pd.concat(..., names=["PERIOD"])`.
- **Legacy files** were built with pandas' default NA strings **plus `na_values=["N/D"]`**.
  `N/D` and `N/A` are NaN there and kept verbatim in `cpv_*`; the comparator
  (`_LEGACY_NA`) knows. State 01 has no `N/D`, so only a 32-state run covers it.
- **The legacy `load_census` crashed in states 08/15/16** (a reserved coarse total made
  `impute_collective`'s difference `pd.NA`). 6c added the NA guard to `aggregate.py`;
  the legacy chain now equals `load_cpv_census(2020)` in all 32 states, unpatched.
- **`_labels_for`** compares only `_LABEL_KEYS`. Between 2020 and 2025, 7/22/5
  (viviendas/personas/migrantes) shared columns label differently.
- **Core scope**: a core entry with `Tablas` applies only to those tables (`_in_scope`;
  `TAMLOC` is microdata-only). `CVE_AGEB`/`CVE_MZA` exist only as harmonized names.
- **Core edits** change the verbatim copies in the generated YAMLs. Rerun `--variables`
  or `test_core_yaml_contract` fails. Core entries are copied **as scoped**
  (`cpv._scoped_entry`: `Recodificar` → `Alias` for its editions).
- **Aggregate sentinels**: `build_cpv._AGG_SPECIALS` per edition (2020 `*`/`N/D`/`N/A`;
  2010 and 2000 `*`/`N/D`; 2005, 1995 and 1990 `*`).
- **ITER gids** (5a): 1990 = `g01`, 1995 = `g02`, 2000 = `g03`, 2005 = `g04`, 2010 =
  `g05`, 2020 = `g06`; AGEB 2010 = `g01`, 2020 = `g02`.
- **1995's ITER aggregates** (9998/9999) are the only record of its one- and two-dwelling
  localities: a municipality = listed localities + aggregates. In every other edition the
  listed localities add up alone.
- **Spilled names** (`cpv_aggregates._repair_spilled_names`): a `LONGITUD` without any digit
  marks a row whose name spilled one field (2000: 2 rows, 1995: 7); the loader shifts it
  back.
- **Review dicts** in `build_cpv.py`: a duplicate key in a dict literal silently drops a
  pair. A test now refuses duplicates.
- **1990/1995 microdata** (5b): person files only (`viviendas`/`hogares` not published,
  `load_cpv_survey` returns `None` for them). 1990's `ID_VIV` ends in the folio's
  occurrence (`cpv._folio_occurrence`; persons are not in `NUM_PER` order, so never
  re-sort before deriving keys). 1995 weights `FAC_POB`/`FAC_VIV`/`FAC_PROM` are in
  `cpv._WEIGHTS`. Gids: `personas` 1990 = `g01` … 2025 = `g09`; `migrantes` 1995 = `g01` …
  2025 = `g06`.
- **Municipal lineage** (6a): `cpv_mun_lineage.yaml` is generated by
  `scripts/build_geo_crosswalk.py` from `mg_mun_*` of 1995–2025 (all must be on disk;
  MG 2025's 32 files came from the bucket). Rebuild it after any MG rebuild; a test
  compares it with a rebuild.
- **Old FDs from PDFs** (5a/5b): `_dict_fd.pdf_text`/`pdf_words` need poppler's
  `pdftotext`. The parsers: `parse_fd_1990_text`, `parse_fd_1995_text`, `parse_fd_text`
  (2000), `parse_iter_fd_tsv` (1990/1995 ITER).
- **Crosswalk** (4b): `_XW_PERIODS` newest first; older editions auto-pair by normalized
  description (`_XW_DESC_PERIODS`, rejected pairs in `_XW_UNPAIR`); `_XW_PAIRS_RENAMED`
  vs `_XW_PAIRS_KEPT` (+ `_XW_NOTES`). `Renombrar` lists editions, and
  `cpv._renames(table, periods)` renames only the frame's own edition.
- **Indicator ranges** (4b): `parse_indicator_csv` reads `00..9999999999` (all zeros to
  all nines) as a count, other zero-padded ranges as codes. The averages' decimals come
  from the values (`label_frame` makes non-integral columns `Float64`).
- **MG national editions** (3d/4b): each frame names its codes its own way
  (`_ENTITY_COLUMNS`/`_ENTITY_PREFIX_COLUMNS`); a layer without `.prj` takes the
  edition's declared CRS (`_edition_crs`). Attribute names stay INEGI's.
- **`ageb_14` (2020) is cp1252**; the 2015 CSVs are cp1252 too (one ASCII file sniffs
  UTF-8). The sniff handles both.
- **On the Mac, `rm` and `cp` are aliased to ask for confirmation**, which hangs
  non-interactive commands; use `/bin/rm -f` and `/bin/cp -f`.
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
- **Derived columns** (6b, `cpv_derived.py`): computed from the **raw** codes before
  labelling, in the **2020 code space** (`_RECODE[period][item]`), mapped with the frozen
  legacy YAML maps and dtypes, so 2020 = legacy by construction. A new edition or item:
  add the edition to the derivation's `periods`, add `_RECODE` entries for renumbered
  codes, and `test_source_codes_match_2020` checks the dictionaries; then load every state
  with `derived=True` (an unmapped code raises).
- **`cpv_constraints`**: `Comparable: false` in the crosswalk flags the *older* editions'
  columns, never the newest edition's own (2020 keeps all 157 + 46 indicators).
- **INEGI throttles `wsl`** at times (~50 kB/s on 2026-10-08). The Mac's `data/cache`
  ZIPs can be copied over (`scp` into `wsl:mxcensus/data/cache/`); the builds read them
  as cached, and the outputs are byte-identical.
- **Both hosts hold the full mirror** (3751 registered files) since the release batch;
  metadata modes and 32-state tests run on either. The CLI still offers only registered
  files.
- **Tailscale SSH can demand a re-login at any time.** A hanging `ssh wsl` that prints a
  login URL needs the user.
- **1995's `FACTOR`** exists only under `harmonize=True` (`cpv._FACTOR_FROM`: persons
  `FAC_POB`, emigrants `FAC_VIV`); raw 1995 frames keep only the three estimators.
- **Disability flags**: `DISCAPACIDAD`/`LIMITACION`/`SIN_DISC_LIM` are INEGI's definitions
  (the CPV constraints `PCON_DISC`/`PCON_LIMI`/`PSIND_LIM` use them; `SIN_DISC_LIM` is NE
  only when all seven answers are 9); `DIS_CON`/`DIS_LIMI` and the legacy YAML's
  `PSIND_LIM` cells are the legacy ones, kept for 2020 = legacy.
- **Occupation codes** (6f): 2010 `OCUACTIV_C` is 4-digit (CUO 2010 ≈ SINCO 2011), 2015
  3-digit SINCO 2011, 2020/2025 3-digit SINCO 2019; the coarse group is the first two
  digits, group 59 (dropped by SINCO 2019) → 52. INEGI's tabulados leave out persons of
  unspecified age (28,710 employed in 2015).
- **Edition-specific derivations** (6d): a derived column may have several `_Derivation`s,
  one per set of editions (2010/2015 `DHSERSAL_*` without IMSS-BIENESTAR, 2015's commute
  dummies on its own codes). `cpv_derivations()` then lists a column once per derivation;
  per edition it is unique. Derivations in an edition's own code space (2015 commute, 2010
  `DISCAP`) skip `_RECODE`.
- **The code-list test** (`test_source_codes_match_2020`) compares each edition's codes,
  after the recode, with 2020's up to the reviewed `_GAPS`/`_EXTRAS` (own-code items:
  `_OWN_CODES`). A new edition or recode needs its rows there.
- **Unknown codes raise everywhere** (6d): the dummy sets and `DHSERSAL` mark a row with an
  unlisted code missing (`_as_dummies`), so `derive` reports it like the other columns.
- **Unspecified state** (6e): the derived `ENT_PAIS_*_CAT` send it to `OtraEnt` in every
  edition (the legacy 2020 rule for 997; 2010's entity 999 recodes to 997). INEGI's
  tabulados count it as «No especificado» (2015 birthplace: 252 persons, 2010 residence:
  1,690), so a tabulado comparison must move that group first
  (`test_migration_equals_tabulados`). Country «insufficiently specified» is `OtroPais`
  in both.
- **2010 pointer pairs** (6e): `IDMADRE`/`IDPADRE`/`IDCONYUGE` = row (up to 96) or 99 «row
  not given»; `…C` = 88 «not here», 99 NE, blank when the person lives here. «99 + blank
  code» means lives here (`_pointer_2010`); that is why 2010's co-residence NE share
  (0.6%) is below 2015's (2.2%).
- **INEGI's tabulados as checks** (6e): EIC 2015 `intercensal/2015/tabulados/NN_tema.xls`
  (`04_migracion`, `14_vivienda`, `01_poblacion`…; estimator «Valor», percentages with 6
  decimals) and Censo 2010 ampliado `ccpv/2010/tabulados/Ampliado/NN_NNA_ESTATAL.xls`
  («Parámetro», full precision). Read with `scripts/_dict_fd.read_xls`; a wrong name comes
  back as HTTP 200 + `text/html`. Their «5 años y más» leaves out unspecified ages.
- **2010 limitation ≠ 2020 disability.** 2010 asked yes/no per activity (`DISCAP1`–`8`);
  its ITER `PCLIM_VIS`/`PCLIM_MOT2` share 2020's names with another concept (crosswalk
  `Comparable: false`). `_EDITION_CELLS` adds them for 2010 on 2010's own items, whatever
  `Comparable` says. The 2010 sample (cuestionario ampliado) does not reproduce the census
  ITER exactly (`STEP_6d.md` §Verification).
