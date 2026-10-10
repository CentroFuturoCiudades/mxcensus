# CPV family — session handoff

**Status (2026-10-10): units 0–6y are done. `main` = v0.10.0 + 6u (merged
locally, **not pushed, no version bump**; v0.10.0 = 6s–6t, tagged and pushed; 0.9.0 =
6k–6r, §Review). `cpv-integration` = `main` + 6v + 6w + 6x + 6y (6v: the `POBHOG` total and
the Conteo 2005's households; 6w: indigenous households and media superior/superior apart;
6x: `HOG_IND` on the household records; 6y: the EIC 2025's percentages as constraints; all
agreed with the user): all four committed (6y with the user's go-ahead, 2026-10-10). None
merged or pushed. No unit is queued. A session starts by
checking `git log`/`git status` against this line.**
- **Released** (registered, uploaded, verified): every edition 1990–2025 (897 `cpv_` files)
  and the Marco Geoestadístico 1995–2025 frames, incl. the EIC 2015's (6h); registry
  **4148** entries (`STEP_6b.md` §Release batch, `STEP_6h.md`).
- **Derived columns** (6b, 6d, 6e, 6f, 6i): `derived=True` on `load_cpv_personas/viviendas/survey`
  for every edition 2000–2025;
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
- **6h** (`STEP_6h.md`): the EIC 2015 frame = INEGI's «Cartografía geoestadística urbana y
  rural amanzanada. Cierre de la Encuesta Intercensal 2015» (a UPC per state), MG period
  2015: 397 files, registry 3751 → 4148, uploaded and verified; the lineage's 2015 step.
- **6i** (`STEP_6i.md`): CGPV 2000 and Conteo 2005 derived columns (2000: 17 + 5, 2005:
  13 + 4) and constraints (2000: 29 + 4, 2005: 38 + 8); 2000 checked against INEGI's sample
  tabulados (within 0.02 points outside Chiapas).
- **6j** (`STEP_6j.md`): CGPV 1990 and Conteo 1995 derived columns (1990: 9 + 4, 1995: 8 + 3)
  and constraints (1990: 12 + 5, 1995: 6 + 3). Their **dwelling frames** are built from the
  person files (user's choice): `load_cpv_viviendas(1990|1995)`, and `load_cpv_survey` no
  longer returns `None` for them. The 1995 `POBFEM`/`POBMAS` cells were fixed (sex is
  `P3_5`). Checked against the 1990/1995 ITER in all 32 states.
- **6k** (`STEP_6k.md`): INEGI's primaria completa leaves técnica after primaria out in
  every ITER that publishes it (1990, 2000, 2010, 2020; the 2010/2020 ITER = the básico
  tabulados' «6 grados» exactly in all 32 states). New derived `EDUC_INEGI` (every edition:
  `EDUC` with «Técnica_primaria» apart; user's choice over a flag) and the 18 education
  constraints on it. The frozen legacy `P15PRI_CO` cell overshoots INEGI's by 2.9% (2020).
- **6l** (`STEP_6l.md`): dictionary fixes. The Conteo 2005 FD's vertical-ellipsis rows no
  longer make a `':'` category (`GRA_APRO`/`NHIJNAVI`/`NUHIJSOB`; `_dict_fd._ELLIPSIS_RE`);
  CGPV 1990's unlabelled «0» (not asked) is «Blanco por pase» in its 20 coded person items
  (`build_cpv._label_blank_zero`). Only those two YAMLs changed.
- **6m** (`STEP_6m.md`): `_dict_fd.read_xls` reads Excel 95 (BIFF5: the CGPV 2000 tabulados);
  `scripts/check_cpv_tabulados.py` runs the 2000/2010/2015 sample-tabulado checks over every
  state, sex and the nation → `TABULADOS_REPORT.md` (10,461 cells; 2010/2015 exact, 2000
  within 0.04 points outside Chiapas; 2000 education on `EDUC_INEGI` = INEGI's levels).
- **6n** (`STEP_6n.md`): the legacy constraints the 2000/2005/2010 samples answer on their
  own items (`_EDITION_CELLS`) and 2010's `CLAVIVP_CAT` (2010 dwellings 0 → 26 constraints;
  2000 4 → 16, 2005 8 → 21; persons 2000 29 → 34, 2005 38 → 43). Crosswalk fix: 2000's ITER
  `VP_CCUART` («con un dormitorio» in its dictionary) is one room without the exclusive
  kitchen, so it no longer becomes `VPH_1DOR` (`_XW_UNPAIR`; 403 indicators).
- **6o** (`STEP_6o.md`): new derived `SECTOR` (1990 CMAP division, 2000–2025 SCIAN sector) and
  the indicators the 1990–2005 ITERs publish under their own names as edition cells (sectors,
  literacy, attendance, ages by sex, basic education, tenure, fuel, goods…; 1990 23 + 9, 1995 10,
  2000 60 + 33, 2005 83 constraints; the 2005/2010 Seguro Popular).
- **6p** (`STEP_6p.md`): Censo 2020 in `check_cpv_tabulados.py` (INEGI's ampliado tabulados,
  `.xlsx`): the 2020 derived columns = INEGI's estimates exactly in every state (5,247 cells).
- **6q** (`STEP_6q.md`): EIC 2015 affiliation, commute, marital status and education, Censo
  2010 limitation and parental co-residence (national) in the tabulado checks, all exact. It
  reversed a 6e rule: 2010's pointer «row 99 + blank code» is «no especificado» (INEGI's
  `12_01A`, to the person), not «lives here».
- **6r** (`STEP_6r.md`): CGPV 2000 hours (EM07) and education of the 12+/18+ (ED08/ED11) in
  the checks; 2000's `HORTRA_CAT` counts «had a job but did not work» (`CONACT` 20) at 0
  hours, as INEGI's tabulado and 2010–2025 (the 2000 sample records their usual hours).
- **6s** (`STEP_6s.md`): `load_cpv_viviendas(2000|2005|2010, derived=True)` takes the
  household head's `SEXO` from the person file (`cpv._attach_heads`, a column-projected read;
  exactly one head per household in every state, else it raises) → derived `JEFE_SEXO`
  (2020's item), so the legacy `HOGJEF_F`/`HOGJEF_M` apply (dwelling constraints 2000 33 → 35,
  2005 21 → 23, 2010 26 → 28). The user chose the loader (not survey-only) and, for 2005's
  dwelling rows, the first household's head. Female-headed share = the ITER's within 0.83
  (2000), 0.94 (2005), 1.51 (2010) points in all 32 states; the method = 2020's `JEFE_SEXO`
  in every dwelling.
- **6t** (`STEP_6t.md`): new derived `HOGJEF_SEXO` on the persons of 1995 and 2000–2025 (the
  user's name — distinct from the dwelling's `JEFE_SEXO` — and editions; 1990 has no
  household number): the `SEXO` of the person's own household head, from the person frame
  (`cpv_derived._HEAD_CODES`, `_household`: exactly one head per household in every state).
  The `PHOGJEF_F`/`PHOGJEF_M` constraints (2000–2025; 2020 = the legacy set + 2): EIC 2025
  exact in all 2,478 municipalities; the ITER within 0.74 (2000), 1.25 (2005, unweighted),
  1.55 (2010), 2.60 points (2020, whose own dwelling item sits as far); CGPV 2000's `C2KHO04`
  and EIC 2015's `12_hogares` 05 tabulados in `check_cpv_tabulados.py`.
- **6u** (`STEP_6u.md`): the relationship items of 1990–2000 labelled from INEGI's own
  documents. CGPV 1990 `CVE_PAR` takes `CATPAREN`'s label where the catalog has the code
  (synonyms joined), else its first digit's group (the FD's rule; the user's choice over
  «eight groups only»): 107 codes, 54 labels, 12,046 persons (0.15%) on undocumented
  detail codes. The Conteo 1995's catalog PDF is now read (`_dict_fd.parse_catalogs_1995_text`):
  `P3_4`/`P9_15` get its eight groups, and the six place items (`P3_7B`, `P4_3`, `P4_6A`,
  `P9_5`/`P9_7`/`P9_9`; the user widened the unit to them) its 41 state/country codes.
  `P7_4`/`P7_8` get its occupation and activity groups through the same link. CGPV 2000
  `OTROPARE_C` gets its FD's seven code groups (`build_cpv._CODE_GROUPS`; «Jefe(a)» = the
  2,312,035 household rows). 2000–2025 FD parses byte-identical; `--validate` 0/897; full
  suite 1802 passed, 1 skipped (Mac).
- **6v** (`STEP_6v.md`): the samples' universe (HANDOFF candidates 1 and 2, one unit).
  - **`POBHOG`**: a new CPV person cell `POBHOG: {}` beside `POBTOT` (user's choice, not a
    replacement), 2000–2025. The weights add up to `POBHOG` in Censo 2020 in every state.
    The EIC 2025 has `POBHOG` = `POBTOT`, exact in all 2,478 municipalities. CGPV 2000's and
    Censo 2010's weights match neither total: above `POBHOG` in every state (0.07–8.9%,
    0.06–3.0%), within 1.2% of `POBTOT` (three 2010 states above it).
  - **The Conteo 2005's households**: `load_cpv_hogares(2005, derived=True)` adds
    `CLAVIVP_CAT` (from the dwelling file, `cpv._attach_dwellings`) and `JEFE_SEXO` (its own
    head, `_attach_heads`). `cpv_constraints("hogares", 2005)` = `TOTHOG`/`HOGJEF_F`/
    `HOGJEF_M`, which leave the 2005 dwellings (user's choice; 23 → 20).
  - The female-headed share is within 0.087 points of the ITER at the median, 0.285 at the
    90th percentile, 1.07 at most (Colima); 6s's dwelling version had 0.118/0.348/0.935.

- **6w** (`STEP_6w.md`): HANDOFF candidates 2 and 1 as one unit (the user's choice).
  - **`HOG_IND`** (persons, 2000–2025, «Sí»/«No»): whether the household is indigenous, by
    **each edition's own definition** (user's choice). The household counts if one of these
    speaks an indigenous language:
    - 2000–2015: the head or the partner;
    - 2020: also the mother or father and the parents-in-law;
    - 2025: also the step-parents, grandparents and great-grandparents.
    - The sets were found on INEGI's numbers, not its dictionaries' wording
      (`cpv_derived._IND_CODES`): exact in the municipalities the 2010/2020 samples
      enumerated completely (364/184) and in every EIC 2025 municipality (`PHOG_IND`,
      `HOG_IND`); EIC 2015 tabulado 05-04.
    - The `PHOG_IND` constraint is on 2005/2010/2020/2025; the crosswalk marks 2005/2010's
      `Comparable: false`, so their cells are edition cells. Persons only (user's choice).
  - **`EDUC_INEGI_DET`** (every edition 1990–2025): `EDUC_INEGI` with «Posbásica» split into
    «Media_superior», «Superior» and «Posgrado» (user's choices: a new full-scale column,
    posgrado apart).
    - 2000's `P18_CMEDSU`/`P18_CSUPER` constraints.
    - Equal to the EIC 2025 estimates' five levels within rounding in every municipality.
    - Exact against the EIC 2015/Censo 2020 tabulados; 2000's within tolerance.

- **6x** (`STEP_6x.md`): HANDOFF candidate 2 after 6w.
  - **`HOG_IND` on the household records**: the dwellings of 2000 (one row per household) and
    2010–2025, and the Conteo 2005's households (user's choices: those frames — not the 2005
    dwellings —, the same name as the person column).
  - A derivation may declare `members=True`: `derive(…, members=)` runs the person rule
    (`_hog_ind`) over the household's person rows and gives each record its household's value;
    `_load_level` reads them from the person file (`cpv._household_members`, a
    column-projected read shared with 6s's `_attach_heads`: `_person_columns`).
  - Equal to the persons' `HOG_IND` in every household of every state and edition (raw and
    harmonized); the EIC 2025's `HOG_IND` estimate is a dwelling constraint (3 → 4), exact in
    every municipality with a published value.

- **6y** (`STEP_6y.md`): the EIC 2025's percentages as constraints (a probe at the session's
  start: 278 of its 346 indicators are published only as `PCN_*` percentages, so 2025 had
  33 constraints against 2020's 207).
  - `load_cpv_estimaciones(counts=True)` (`valor` only): 85 percentages → counts on their
    bases (`cpv_aggregates._PERCENT_BASES`, each found on the microdata), `Float64`,
    unrounded (user's choice).
  - EIC 2025 constraints 29 + 4 → **94 + 31**, each equal to the estimates at all 2,769
    published geographies (counts exactly, percentages to their rounding), all 32 states.
  - INEGI's definitions where the legacy cells differ: `PCLIM_*` only for the persons with a
    limitation, `PCDISC_*` with the unknown degree — in 2020 and 2025 (user's choice: in the
    184 completely enumerated municipalities the 2020 ITER matches them in 168–183, the
    legacy limitation cells in 0–4); 2025's own `PDER_ISTE` (federal or state ISSSTE, new
    dummy `DHSERSAL_ISSSTE_T`), `VPH_EXCSA` (toilet or latrine), water wording; `PNACOE`
    without the unspecified state on the new **`ENT_PAIS_NAC_INEGI`** (user's choice; every
    edition with a birthplace).

Design: [`PLAN.md`](PLAN.md). Recent units: [`STEP_6y.md`](STEP_6y.md), [`STEP_6x.md`](STEP_6x.md), [`STEP_6w.md`](STEP_6w.md), [`STEP_6v.md`](STEP_6v.md), [`STEP_6u.md`](STEP_6u.md), [`STEP_6t.md`](STEP_6t.md), [`STEP_6s.md`](STEP_6s.md), [`STEP_6r.md`](STEP_6r.md), [`STEP_6q.md`](STEP_6q.md), [`STEP_6p.md`](STEP_6p.md), [`STEP_6o.md`](STEP_6o.md), [`STEP_6n.md`](STEP_6n.md), [`STEP_6m.md`](STEP_6m.md), [`STEP_6l.md`](STEP_6l.md), [`STEP_6k.md`](STEP_6k.md), [`STEP_6j.md`](STEP_6j.md), [`STEP_6i.md`](STEP_6i.md), [`STEP_6h.md`](STEP_6h.md), [`STEP_6g.md`](STEP_6g.md), [`STEP_6f.md`](STEP_6f.md), [`STEP_6e.md`](STEP_6e.md),
[`STEP_6d.md`](STEP_6d.md),
[`STEP_6c.md`](STEP_6c.md), [`STEP_6b.md`](STEP_6b.md), … [`STEP_0_probe.md`](STEP_0_probe.md).

**Host state.** The Mac and `wsl:~/mxcensus` both hold the full mirror (4148 registered
files; the MG 2015 files were built on the Mac and copied to `wsl` for the upload);
`wsl:~/mxcensus` was pulled to 6r on 2026-10-09 (the full suite ran there before the
merge: 1773 passed, 1 h 50 min) and holds a copy of the Mac's tabulados cache
(`data/dict/tabulados/`, without 6t's `2000/C2KHO04.xls` and `2015/12_hogares.xls` and 6w's
`2015/05_etnicidad.xls` and `2020/cpv2020_a_eum_07_educacion.xlsx`: the script fetches
them). 6s–6y ran on the Mac only.
`wsl:~/mxcensus3c` (3c's code copy) can be deleted.

## Kickoff prompt for the next session

> Continue the CPV census-family work in this repo (branch cpv-integration = main + 6v–6y;
> main = v0.10.0 + 6u, merged). Read docs/cpv/HANDOFF.md first, then agree with me which next unit to
> take (candidates in HANDOFF §Next) before implementing it, following the session protocol
> in docs/cpv/PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without asking; ask
> me before committing, pushing, installing packages or uploading.

## Review: decisions taken unattended (night of 2026-10-08/09) — kept

The user asked for the night's units (6m–6r) to run without them, and on 2026-10-09 reviewed
and **kept all seven** (merged as 0.9.0):

1. **6n, a crosswalk change with user-visible effect**: 2000's ITER `VP_CCUART` is no longer
   renamed to `VPH_1DOR` under `harmonize=True` (it counts one room without the exclusive
   kitchen, not one bedroom: `STEP_6n.md`). `load_cpv_iter(2000, harmonize=True)` loses
   `VPH_1DOR` and keeps `VP_CCUART`; 2000 loses the `VPH_1DOR` constraint.
2. **6o, a new derived column**: `SECTOR` is added by `derived=True` in 1990 and 2000–2025
   (so 2010–2025 frames gain a column too).
3. **6n/6o, the constraint sets grew** (1990 17 → 32, 1995 9 → 13, 2000 33 → 93, 2005 46 →
   104, 2010 142 → 169): crosstabs built from `cpv_constraints` for these editions now have
   more tables. Each new cell sits within its edition's sample-vs-census band, which for
   the dwelling goods and the 2005 sample is up to a few points (`STEP_6n.md`, `STEP_6o.md`).
4. **6m, the 2000 tolerance** of the tabulado checks is 0.04 points (7 of 1,683 sector cells
   are 0.02–0.039 off outside Chiapas).
5. **Left out on purpose**: 2000's disability indicators (`PCONDISC`…; the sample's shares
   are 30–60% above the census's), income in minimum wages, the household head's sex for
   2000–2010 (`HOGJEF_*`: needs the person file — done in 6s).
6. **6q, a 6e rule reversed on INEGI's evidence**: Censo 2010's pointer «row 99 + blank
   code» is now «no especificado» (was «lives here»): INEGI's tabulado `12_01A` counts it so,
   to the person nationally. `MADRE_EN_VIVIENDA`/`PADRE_EN_VIVIENDA`/`IDENT_PAREJA_CAT`
   (2010) change for ~3.1M persons (weighted); the partner follows by analogy (no tabulado).
7. **6r, 2000's hours**: `HORTRA_CAT` 2000 sets `CONACT` 20 («had a job but did not work»)
   to 0 hours (INEGI's C2KEM07 «no trabajó»; 2010–2025 record 0 for them).
8. **Merge and version**: 6k–6r merged into `main` as **0.9.0** (2026-10-09); 6s–6t as
   **0.10.0** the same day.

## Next: candidates (none decided)

1. Merge 6v–6y into `main`, push `main`/`cpv-integration` (6u–6y) and a version
   bump, when the user wants them (`wsl` pull + full suite there first, as for 0.9.0).
2. The EIC 2025's other 190 percentages (6y left them: their cells are new), with 6y's
   method (`STEP_6y.md`: the base search, then `_PERCENT_BASES` + cells, verified at every
   geography). Probably two units:
   - **persons**: the 5-year age groups by sex (48), the residence in October 2020
     (`PCN_PRES*20`; an `ENT_PAIS_RES_INEGI` beside `ENT_PAIS_RES_CAT`, as 6y's
     birthplace), nationality of the born abroad, Afro-descendant households
     (`HOG_AFRO`/`PHOG_AFRO`, counts), the disability by age and sex, school attendance…;
   - **dwellings and households**: walls, roofs, cooking place and fuel, waste, water
     storage and heaters, tenure and deeds, the household types (`PCN_HOG_FAM`/`_NFAM`),
     income sources (`PCN_HOG_PERC`, `_GOB`, `_JUB`, `_OVIV`, `_OPAIS`), food security
     (`PCN_*_ADL*`, `PCN_*_MEN*`, `HOG_MEN_ALIM`) and displacement — their bases are
     households.
3. Smaller: `check_cpv_tabulados.py`'s EIC 2015 migration check could read
   `ENT_PAIS_NAC_INEGI` instead of moving the unspecified group (`_moved`); a 2000 occupation bridge (CMO → SINCO, no published table); income in minimum
   wages for 2000 (`P_1SM`…: three wage zones by municipality); a locality-level lineage
   (6a covered municipalities only); CGPV 1990's undocumented `TIP_HOGAR` 6 (96,370
   persons, all `N_F_GPOS` 99 and a 9xx relationship: a dwelling without its household
   composition; identity-labelled, `STEP_6u.md` §Left out).

## Open questions for the user

None.

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
- **1990/1995 microdata** (5b): person files only (`viviendas`/`hogares` not published;
  since 6j the dwellings are built from the person file). 1990's `ID_VIV` ends in the folio's
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
- **MG 2015** (6h): one INEGI product per state (`MgEdition.products`, UPCs in INEGI's
  alphabetical order), 12 layers + `ti` (`mg_layers`), island layer named
  `NNterritorioinsular`, columns differ from 2020's, LCC on ITRF92; Empalme (26025) has a
  second, empty polygon. INEGI serves ~0.5 MB/s per connection: prefetch in parallel.
- **MG national editions** (3d/4b): each frame names its codes its own way
  (`_ENTITY_COLUMNS`/`_ENTITY_PREFIX_COLUMNS`); a layer without `.prj` takes the
  edition's declared CRS (`_edition_crs`). Attribute names stay INEGI's.
- **`ageb_14` (2020) is cp1252**; the 2015 CSVs are cp1252 too (one ASCII file sniffs
  UTF-8). The sniff handles both.
- **On the Mac, `rm` and `cp` are aliased to ask for confirmation**, which hangs
  non-interactive commands; use `/bin/rm -f` and `/bin/cp -f`.
- **Registry**: `--update-registry` upserts. The diff must be additions only (`git diff
  --numstat`).
- **Upload**: `upload_hf.py upload` from `wsl` only, never with `--delete`. Dry-run first,
  and count the actions: the dry run must list exactly the new files.
- **Mac → `wsl` copies** (6h): macOS `tar` adds AppleDouble `._*` sidecars (397 junk
  `._mg_*.parquet` would have been uploaded). Use `COPYFILE_DISABLE=1 tar …`, or delete
  `._*` on `wsl` before the dry run. Tailscale carries ~0.6 MB/s; check SHA-256 against the
  registry on `wsl` after copying.
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
- **Both hosts hold the full mirror** (4148 registered files) since 6h;
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
- **2000/2005 derived columns** (6i): education from the level-and-antecedent items
  (2000 `NIVACAD` + `ANTESC`, never-schooled 5–29 via `NIVELACAD` 00; 2005 `NIVANTES` +
  `GRA_APRO`), coverage from one item per institution (`_DHSERSAL_ITEMS`), 2000 religion
  with its own «Blanco por pase» dtype (`_period_dtypes`), 2000 `TOTCUART` counts the
  kitchen (its rooms tabulado does not). The 2000 sample does not reproduce its tabulados
  cell for cell (weights): compare within ~0.02 points, Chiapas worse. The 2000 tabulados
  are BIFF5 (`_dict_fd.read_xls` reads BIFF8 only).
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
  code» is **not specified** (6q: INEGI's `12_01A` counts it so, to the person nationally;
  6e had read it «lives here»), so 2010's co-residence NE share is 3.7%.
- **INEGI's tabulados as checks** (6e): EIC 2015 `intercensal/2015/tabulados/NN_tema.xls`
  (`04_migracion`, `14_vivienda`, `01_poblacion`…; estimator «Valor», percentages with 6
  decimals) and Censo 2010 ampliado `ccpv/2010/tabulados/Ampliado/NN_NNA_ESTATAL.xls`
  («Parámetro», full precision). Read with `scripts/_dict_fd.read_xls`; a wrong name comes
  back as HTTP 200 + `text/html`. Their «5 años y más» leaves out unspecified ages.
- **1990/1995 dwellings** (6j) are built from the person file (`cpv._DWELLINGS_FROM_PERSONS`,
  `_dwellings_from_persons`): there is no raw `viviendas` file, so `load_cpv(table=
  "viviendas", period=1990)` raises, and `cpv_derived._frame_group` labels them with the
  person group. 1990 writes **0 for «not asked»** (`_NA` in `_RECODE`). Its income is in old
  pesos (÷ 1,000; ~1% look written in thousands). 1995's 1,151 employed with a blank
  monthly income have `FAC_POB` = 0.
- **Core overlays label columns a frame lacks** (6j): `variables_cpv_labels` includes every
  in-scope core entry (`SEXO`, `EDAD`…), whatever the edition calls the item (1995: `P3_5`,
  `P3_6`). Constraint categories (`_categories`) and the code-list test take only the
  group's own columns.
- **Dictionary artefacts** (6l): an FD row whose code is only dots/colons is an ellipsis
  (`_dict_fd._ELLIPSIS_RE`); an edition that writes an unlabelled 0 for «not asked» goes in
  `build_cpv._BLANK_ZERO` (1990 only). `test_dictionary_fixes_6l` pins both in the YAML.
- **Education constraints read `EDUC_INEGI`** (6k, `cpv_derived._CELL_VARS`): its
  «Primaria_com» is six grades only, «Técnica_primaria» (2020's `NIVACAD` 6) apart, as the
  ITER 1990–2020. The legacy `EDUC` and `constraints_personas.yaml` (frozen) count técnica
  as «Primaria_com». INEGI's own products disagree: the EIC 2015 tabulados put it in «6
  grados», 1990/2000 ITER in «posprimaria», 2010/2020 apart. The 2010/2020 básico tabulados
  (`ccpv/2010/tabulados/Basico/07_08B_ESTATAL.xls`, `ccpv/2020/tabulados/
  cpv2020_b_eum_07_educacion.xlsx`) equal the ITER; the ampliado samples cannot tell.
- **2010 limitation ≠ 2020 disability.** 2010 asked yes/no per activity (`DISCAP1`–`8`);
  its ITER `PCLIM_VIS`/`PCLIM_MOT2` share 2020's names with another concept (crosswalk
  `Comparable: false`). `_EDITION_CELLS` adds them for 2010 on 2010's own items, whatever
  `Comparable` says. The 2010 sample (cuestionario ampliado) does not reproduce the census
  ITER exactly (`STEP_6d.md` §Verification).
- **`scripts/check_cpv_tabulados.py`** (6m–6q) takes ~25 min for all editions and 32 states
  (peaks ~8 GB); `--periods`/`--states` for a quick look (the nation and the 2010
  national-only checks need all 32). Tabulados cache in `data/dict/tabulados/{period}/`
  (2000 `C2K*.xls` BIFF5, 2010/2015 `.xls`, 2020 `.xlsx`). INEGI's tabulados leave out
  unspecified ages (999) from age-defined universes (the commute tables: students 3+,
  employed 12+); the 2015 percentages have six decimals (≤ ~0.9 of a person nationally).
- **A crosswalk pair by description can be wrong** (6n): 2000's `VP_CCUART` «con un
  dormitorio» is one room without the exclusive kitchen. Check a paired indicator's level
  against the sample before trusting it (`_XW_UNPAIR`).
- **Sample vs census** (6n/6o): edition cells reproduce their ITER within the edition's band
  — 2000's census `POBTOT` includes the population without characteristics (age cells
  3–7 points off in states 02, 06, 15); the 2005 sample is unweighted (Quintana Roo ~11
  points off); 2010's ampliado bedrooms 2–5 points; 2000's employed share +0.7–1.3.
- **Sweeps over 2000/2005**: their person frames carry `ID_HOG` in the index; drop
  duplicate `ID_VIV`s only on dwelling frames. 1995's weights exist only under
  `harmonize=True` (raw frames have `FAC_POB`, no `FACTOR`).
- **The head's sex** (6s): `derive` on the 2000/2005/2010 dwellings needs the head's `SEXO`
  column, which `cpv._load_level` attaches (`_attach_heads`, from the person parquet) and
  drops after `derive`; a synthetic dwelling frame in a test must carry it.
  `cpv_derivations` lists `JEFE_SEXO ← SEXO` (the person item). 2005's `TOTHOG`/`HOGJEF_*`
  count dwellings, not households. The 2010 sample's female-headed share sits up to 1.5
  points from the census (2020's own sample: 1.7).
- **Household derivations** (6t): a `_Derivation(household=True)` gets each record's
  household in `src[_HOUSEHOLD]` (`_household`: entity + `ID_HOG` in 1995–2005, entity +
  `ID_VIV` from 2010; a frame without keys gets the composite keys). Synthetic person frames
  must carry the relationship item (`PARENTESCO`/`PARENT`/`OTROPARE_C`/`P3_4`), `SEXO`
  (1995 `P3_5`) and the key or its parts; rows replicated from one person need a household
  each (`tests/test_cpv_derived._each_a_household`), or the household has several heads and
  `derive` raises. The relationship item is own-code per edition (`_HEAD_CODES`), so the
  code-list test checks only that the head codes are documented.
- **Head's sex vs the ITER** (6s/6t): the 2020 sample's female-headed share sits up to 2.6
  points under its ITER (Querétaro) — INEGI's own dwelling item `JEFE_SEXO` as far, so it is
  the sample's, not a bug; 2010's 1.6. Tabulados by the head's sex publish both sexes of the
  persons only (`check_cpv_tabulados.py` compares sex T); table `hogares` there = CGPV
  2000's household rows (`viviendas` keeps one row per dwelling).
- **`cpv_derived` module names are shared**: `_EMPLOYED` (1990's employed CONACT codes) vs
  the constraint dict `_EMPLOYED_CELLS` (6o) — a shadowed constant silently blanked 1990's
  hours until a test caught it.
- **Code groups** (6u): an item whose FD documents groups of codes, not each code (1990
  `CVE_PAR` by its first digit, 2000 `OTROPARE_C` by ranges), is listed in
  `build_cpv._CODE_GROUPS` (transcribed from the FD). `--variables` labels every observed
  code there (`_label_code_groups`: own catalog label, else the group's; a code outside the
  groups raises). Since 6u, CGPV 1990's catalog workbook joins a code's synonyms
  (`_catalog_from_rows`).
- **Two person totals** (6v): `POBTOT: {}` (legacy) and `POBHOG: {}` (`_CELLS`), both
  every sampled person. Censo 2020's weights = `POBHOG`, the EIC 2025's = both; 2000/2010's
  match neither (above `POBHOG`, about `POBTOT`). A fit should use one of them, not both.
- **The Conteo 2005's household indicators live on `hogares`** (6v):
  `cpv_constraints("viviendas", 2005)` has no `TOTHOG`/`HOGJEF_*`
  (`_HOUSEHOLD_INDICATORS`); `cpv_constraints("hogares", …)` raises outside 2005.
  `load_cpv_hogares(2005, derived=True)` reads the dwelling file (`CLAVIVPA`,
  `_DWELLING_FOR_HOUSEHOLDS`) and the person file (the head's `SEXO`). Both are
  column-projected, and the helper columns are dropped after `derive`. The source-code test
  maps borrowed sources to their files (`tests/test_cpv_derived._BORROWED`).
- **The Conteo 1995 catalogs are a PDF** (6u, `_dict_fd.parse_catalogs_1995_text`, poppler):
  one stem per «CATÁLOGO DE …» section. The municipal and metropolitan-area sections are
  per-state tables, skipped (`_CAT95_SKIP`). An FD field without codes but with «Ver
  catálogo de X» takes the section `match_catalog(X)` names; `ENT` keeps its own `{01..32}`.
- **Indigenous households** (6w): each edition counts other relatives (`cpv_derived._IND_CODES`;
  `STEP_6w.md` has the table), and INEGI's dictionary wording is wrong both ways (the 2020
  ITER says «ascendientes» but counts only parents and parents-in-law; the EIC 2025 says
  «madre o padre, suegra(o)» but counts step-parents and grandparents too). `PHOG_IND` is
  `Comparable: false` in the crosswalk (2005/2010 head or partner only).
- **Completely enumerated municipalities** (6w): Censo 2010 (767) and 2020 (220) have
  municipalities whose every sampled person has `FACTOR` 1 — the ampliado went to every
  dwelling there, so the sample *is* the census and the ITER is matched to the person
  wherever `POBHOG` matches (364/184). Use them to settle a definition; a weighted
  state-level fit can mislead (the 2020 sample's indigenous-household population runs
  4.5% over the ITER).
- **EIC 2025 estimates write «No aplica» (NA) for a zero** (6w: the 56 municipalities
  without an indigenous household); compare only the published values.
- **Household columns on household records** (6x): a `_Derivation(members=True)` reads person
  items from `derive`'s `members` (the person rows of the frame's households), so `derive` on
  a 2000/2010–2025 dwelling frame or the 2005 household frame raises without `members=`, and
  a record whose household has no member raises. The loaders read them
  (`cpv._household_members` → `_person_columns`: the first alias the file has — Censo 2010
  has both `PARENT` and `OTROPARE_C` —, keyed as the frame). Synthetic dwelling frames in the
  tests go through `tests/test_cpv_derived._derive_dwellings` (keys + one non-speaking head
  each). The match ignores zero padding (`_per_record`), so raw 2015 members fit a harmonized
  dwelling frame; Censo 2010's raw serials need the same `harmonize` on both sides
  (`_person_columns` builds the national keys).
- **`HOG_IND` is on both frames** (6x): a person ↔ dwelling join needs a suffix.
- **EIC 2025 percentages** (6y): most estimates are `PCN_*` percentages (two decimals).
  `load_cpv_estimaciones(counts=True)` (`valor` only) adds `X` = `PCN_X` × base / 100 for
  the 85 in `cpv_aggregates._PERCENT_BASES`. Each 2025 constraint is a column of that frame.
  A derived count is off Σ `FACTOR` by the rounding (base × 0.00005: ≤ 5,268 persons
  nationally, ≤ 88 in a municipality), so a test compares the **share** (our cells ÷ the
  base's cells) with the percentage, within 0.005. Bases are not always the age group
  (`PEA_F` is a share of the PEA, `PDER_IMSS` of the affiliated, `VPH_*` of
  `VIVPARHAB_C`): find them on the data, never from the description alone.
- **The base search** (6y, `STEP_6y.md`): Σ `FACTOR` per geography (municipality, ≥50k
  locality = `LOC50K`, the state remainder 997/9997 = `LOC50K` 0000, state) over every
  candidate cell, then for each percentage the base whose share is within 0.005 at all 2,769
  published geographies. Seven municipalities have persons without characteristics: every
  percentage there is «No aplica».
- **Legacy vs CPV cells in 2020** (6y): `PCLIM_*` (on `LIMITACION`) and `PCDISC_*` (with the
  unknown degree) differ from the frozen `constraints_personas.yaml`, as `PCON_DISC`/
  `PCON_LIMI`/`PSIND_LIM` and the education cells already did; the Censo 2020 ITER agrees
  with INEGI's. The unknown degree's label differs by edition (2020 «… de la discapacidad»,
  2025 «… de la dificultad»: `_pcdisc`).
- **Two birthplace columns** (6y): `ENT_PAIS_NAC_CAT` (legacy: the unspecified state is
  `OtraEnt`) and `ENT_PAIS_NAC_INEGI` (it is «No especificado»). Only the EIC 2025's
  `PNACOE` reads the INEGI one; 2020's ITER fits neither exactly.
