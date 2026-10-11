# CPV family — session handoff

**Status (2026-10-11): units 0–6z and 7a–7p are done. `main` = v0.11.0 = 6u–7b, tagged and
pushed. After it, on `cpv-integration` (not pushed): 7c (CGPV 2000's places, the income in
minimum wages 2000–2020), 7d (tabulado checks: the EIC 2015's dwellings, CGPV 2000's
employment and migration), 7e (ratio constraints), 7f (CGPV 2000 per dwelling, the 1990/1995
averages), the unattended night's 7g (constraint keys = the published columns; every
constraint against the census: fixes to 2000/2010/2020 cells, new 2010 `RELIGION_INEGI`) and
7h–7n (tabulado checks only) — all reviewed and **kept** by the user on 2026-10-11 (§Review)
— and 7o (tabulado checks: the fertility rates and the infant mortality of 2010/2015/2020)
and 7p (tabulado checks: Censo 2020's disability and migration causes, Censo 2010's by-state
leftovers).
Before 0.11.0: v0.10.0 = 6s–6t, 0.9.0 = 6k–6r. A session starts by checking `git log`/`git
status` against this line.**
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

- **6z** (`STEP_6z.md`): the EIC 2025's dwelling and household percentages (HANDOFF
  candidate 2's second half; the user chose it over the persons).
  - 63 more counts behind percentages (`_PERCENT_BASES` 85 → 148): the dwellings' on
    `VIVPARHAB_C`, the deeds' on the owned dwellings (`VPH_PROPIA`, which counts those being
    paid for), the households' on `TOTHOG`, the minors' food items on the published
    `HOG_MEN_ALIM`, `POBHOG_FAM`/`_NFAM` on `POBHOG`. EIC 2025 constraints 94 + 31 →
    **96 + 92**, each = the estimates at every published geography.
  - New derived `OCUP_CUARTO_CAT` (occupants per room, 2010–2025; user's editions),
    `CLASE_HOG` (familiar or not from `TIPOHOG`, 2000 and 2010–2025, dwellings **and persons**:
    the persons read their household's `TIPOHOG` from the dwelling file,
    `cpv._attach_dwellings`; user's editions) and `INGR_OTROS` (income from any other source
    than work, 2015–2025: a cell cannot say «any of four items»).
  - `HOG_MEN_ALIM` («hogares con menores de edad») is not a constraint (user's choice): the
    questionnaire's filter of minors is not in the microdata (a person under 18: never
    below, 0.05% over nationally, exact in half the municipalities).

- **7a** (`STEP_7a.md`): the EIC 2025's person percentages (HANDOFF candidate 2: all 127 in
  one session, the user's choice).
  - 116 more counts behind percentages (`_PERCENT_BASES` 148 → 264), plus the published
    `PUSU_SS`, `PHOG_AFRO` and `HOG_AFRO`: EIC 2025 constraints 96 + 92 → **214 + 93**, each
    = the estimates at every published geography.
  - A base may be a **sum** of counts (`_base_parts`): the five-year ages are shares of the
    population of specified age (`POB0_14` + `POB15_64` + `POB65_MAS`; the women's and men's
    groups too), the students' modes of the students who commute (their four times).
  - New derived columns (names and editions the user's): `EDAD_QUIN` (every edition);
    `LUGAR_RES_5A` (residence in 2020 by the own municipality and entity, the US apart),
    `ENT_PAIS_ASI_INEGI`/`ENT_PAIS_TRAB_INEGI` (997 → NE), `MED_TRASLADO_{ESC,TRAB}_{METRO,
    BUS,TAXI}_T` (2020, 2025); `DHSERSAL_AFIL_ACCESO` (affiliated or recognised access) and
    `HOG_AFRO` (persons and dwellings, 2025's indigenous-household members with `AFRODES` 1).
  - Left out (11): the employed's 9 commute modes (their base, who commutes, includes «no
    es posible determinarlo», unpublished: user's choice), `PCN_HF` (a ratio of children),
    `PCN_P3NHLI_CLI` (its base leaves out the unspecified speakers, unpublished; by the
    same rule). The disability by age takes `PCON_DISC` (user's choice): ≤ 28 persons over
    its unpublished specified-age base (51 persons nationally).

- **7b** (`STEP_7b.md`): the older editions catch up (HANDOFF candidate 3's first items; the
  user widened it to the places by municipality).
  - New derived **`LUGAR_ASI`** (2015, 2020, 2025) and **`LUGAR_TRAB`** (2010–2025), the
    place of school and of work with `LUGAR_RES_5A`'s categories (same municipality, another,
    municipality not specified, another entity, the US, another country, not specified,
    blank); `LUGAR_RES_5A` now 2010–2025; `ENT_PAIS_ASI_INEGI` 2015–2025,
    `ENT_PAIS_TRAB_INEGI` 2010–2025 (`cpv_derived._lugar`).
  - Censo 2010's work item `LTRABPAI_C` holds the entity and the country catalogs; its 999
    is the entity's «no especificada» (INEGI's `08_15A`, to the person in every cell).
  - `check_cpv_tabulados.py`: the places by municipality against the 2010/2015/2020
    tabulados (exact in every state), the EIC 2015's household class and type, tenure and
    deeds; its birthplace check reads `ENT_PAIS_NAC_INEGI` (`_moved` is gone).
  - No constraint changes; the EIC 2015's grouped commute dummies are not derivable (one
    code for bus and taxi).

- **7c** (`STEP_7c.md`): HANDOFF candidate 2's CGPV 2000 places and income in minimum wages
  (the user's choice), the wages widened by the user to 2010–2020.
  - **2000's places**: `LUGAR_RES_5A` (its residence in 1995, `RES95EDO_C` + `MUN95OTR_C`),
    `LUGAR_TRAB` and `ENT_PAIS_TRAB_INEGI` (`LTRABPAI_C` + `LTRABMUN_C`; its 999 is simply «no
    especificado»). = C2KEM10 within 0.009 points outside Chiapas; C2KMI04 within 0.013 in 27
    states, but INEGI counts 0.08–1.04 points more municipal migrants in Guanajuato, Oaxaca,
    Veracruz, Zacatecas (and Chiapas). Zacatecas = Trancoso's own-code answers; the others
    have no rule. The person's answer is kept (user's choice).
  - **`INGTRMEN_SM`** (2000, 2010, 2015, 2020; the user's name): the monthly income from work
    over the municipality's CONASAMI minimum wage × 30, in INEGI's groups (2000's bounds
    differ). Wage tables from INEGI's own sources: the 2000 FD's annex, the 2010/2015
    catalogs `TC_TABLA_SALARIOS_MUN_2010`/`TC_SALARIO_MUN_2015` (2015's slip — Coacoatzintla
    for Coatzintla — kept: the tabulado follows it), 2020 the DOF's northern border zone +
    San Quintín. The 2010/2015/2020 tabulados to the person (2010's State of México ≤ 525
    persons, unexplained), 2000 within 0.02 points.
  - The 2000 ITER's `P_1SM` … `P10_SM` are 2000 person constraints (65 → 70).

- **7d** (`STEP_7d.md`): HANDOFF candidate 2's «more EIC 2015 tabulados» and «more CGPV
  2000 tabulados» (the user's choice), checks only — no loader, derivation or dictionary
  changed.
  - `check_cpv_tabulados.py` reads the samples' **raw items** too: every EIC 2015 dwelling
    tabulado by state (14-02…14-38) is exact to the dwelling and the occupant in every state;
    CGPV 2000's C2KEM02/03/04/06/09/11 (inactivity, participation, the CMO groups,
    position, benefits, TDA/TOPD2/TIID) and C2KMI02/05–12 (lifetime and recent migrants by
    state, causes, the `migrantes` file's international migrants) sit in the 2000 band.
  - INEGI's rules found: the 2015 dwellings that cook name a place or a fuel (150,929 with
    neither specified are out); 2000's TOPD2 leaves out who had a job but did not work
    (`CONACT` 20), TIID those without income; the migration shares' base is the residents
    of a specified state; `MPAIRES_C` 700 = returned.
  - New machinery: `ByOrigin` cells (records counted in their state of origin; such checks
    need all 32 states), `Check.weight` (the occupants: `FACTOR` × `NUMPERS`), `migrantes`
    frames.

- **7e** (`STEP_7e.md`): HANDOFF candidate 1, the ratio constraints (the user's choice),
  widened by the user to the averages and the census ITERs.
  - A published share of a base nobody publishes, or an average, is the linear constraint
    Σ w·N = r / scale · Σ w·D. New **`cpv_ratio_constraints(table, period)`** (numerator and
    denominator cells as `cpv_constraints`'s, value columns, `known` columns — a record with
    one missing counts on neither side —, scale) beside the unchanged `cpv_constraints`, and
    **`cpv_ratio_terms(frame, ratios)`**, each record's N and D (user's API choice).
  - **EIC 2025** 15 + 2: the 11 percentages 7a left without a count (the employed's nine
    modes over the employed who commute, «no es posible determinarlo» included;
    `PCN_P3NHLI_CLI` over the 3+ answering «no»; `PCN_HF` dead over born alive), `PROM_HNV`,
    `GRAPROES`/`_F`/`_M` (`ESCOACUM`), `PRO_OCUP_C`, `PROM_OCUP` — each = the estimates at
    every published geography (2,769; 2,776).
  - **Censo 2010/2020** 4 + 2: the ITER's `PROM_HNV`, `GRAPROES`/`_F`/`_M`, `PRO_OCUP_C`,
    `PROM_OCUP`, exact in the municipalities the samples enumerated completely where the
    population and the age group equal the ITER's (2010: 343–364, 2020: 135–184). Censo 2010's
    `PRO_OCUP_C` divides the occupants of every dwelling by the rooms of those that gave
    them.
  - **CGPV 2000 left out** (user's choice): its `GRADOESCO` misses by 0.28 at the median even
    where the sample is the census; `PRO_OVP`/`PRO_OCVP` are exact only once per dwelling (its
    dwelling rows are households) and with 2000's rooms (less an exclusive kitchen nobody
    sleeps in).
  - Full suite on the Mac: 1900 passed, 1 skipped.

- **7f** (`STEP_7f.md`): HANDOFF candidate 1, CGPV 2000 per dwelling, widened by the user to
  the 1990/1995 ITER averages.
  - **CGPV 2000** (one row per household; exactly one `NUMHOG` 01 per dwelling): new derived
    **`PRIMER_HOGAR`** and **`TOTCUART_INEGI`** (its rooms less an exclusive kitchen nobody
    sleeps in — `COCINA` 1, `COCDOR` 4; the first numeric derived column, `Int64`).
  - The 2000 dwelling constraints move onto the first household and every private dwelling
    class, and `VIVPAR_HAB` is added (user's choices). Its «Otro» dwellings carry the items
    and its ITER counts them. All 36 equal the ITER in the 186 municipalities its sample
    enumerated completely; before, 39–186 per indicator.
  - **Ratio constraints**: 2000 `PROM_OCUP`/`PRO_OCUP_C`, exact there. 1990 `PROM_OCUP`/
    `PRO_OCUP_C` and 1995 `PROM_OCUP` are `OCUPVIVPAR / VIVPAR_HAB` truncated (1990's rooms
    by Censo 2010's rule); their samples sit within 0.07 (1990) and 0.21 (1995, whose
    dwelling and person weights are calibrated apart).
  - The 1995 dwellings count their persons (`NUMPERS`); 1990's cells widen to every class
    too (user's choice); `VIVPAR_HAB` 1990/1995 and **`OCUPVIVPAR`** as the 1990/1995 person
    total (user's choice: the Conteo's `FAC_POB` adds up to it but in Chiapas).
  - 1990 `NUM_PERS`/2000 `NUMPERS` become numeric (`build_cpv._QUANTITIES`). Crosswalk (on
    the data; for the user's review): 1995 `PRO_O_VP` → `PROM_OCUP`, 2000 `VP_AGUENT` →
    `VPH_AGUADV`.
  - Full suite on the Mac: 1907 passed, 1 skipped (`--validate` 0/897).

- **7g** (`STEP_7g.md`): HANDOFF candidate 2, unattended, widened on the probe to every
  2000/2010/2020 constraint against its ITER.
  - **Keys = the published columns**: `cpv_constraints`/`cpv_ratio_constraints` key each
    indicator by the column the edition publishes it under (`_published_name`): 18 kept-pair
    keys change (2000 `PNACOENT`, `P5_RES95`, `P5_RESO95`, `P5_CATOLIC`, `VP_SERSAN`; 2005
    `P_RE2000`, `P_OE2000` …, `P_SEGPOP`, `VPH_AGDV`, `VPH_NOAG`; 2010 `PRES2005` …,
    `PRESOE05` …). Every key of every edition is now a column of `load_cpv_iter(period)` (or
    of the EIC 2025's estimates); a test checks it.
  - **Where the sample is the census, strictly**: `FACTOR` 1 for everyone, `POBHOG` and
    every age/sex count equal to the ITER's (2000: 51 municipalities, 2010: 233, 2020: 130).
    Fixes, each now exact there: CGPV 2000's `PNACOENT`/`P5_RESO95` count the born/living
    abroad and its religions the 5+; Censo 2010/2020's `PNACOE` and `PRESOE*` (`_F`, `_M`)
    leave the unspecified entity out (INEGI's rule, as the EIC 2025: `ENT_PAIS_NAC_INEGI`,
    `LUGAR_RES_5A`); new 2010 **`RELIGION_INEGI`** (its own classification: the
    neo-Israelites among the other credos) for `PNCATOLICA`/`POTRAS_REL`. **Every 2010
    constraint is now exact in all 233 municipalities.**
  - Left (INEGI's census processing, no rule): CGPV 2000's no schooling (its census imputed
    the unspecified level) and income in minimum wages; Censo 2020's health affiliation and
    religion (small swaps between categories).
  - Full suite on the Mac: 1912 passed, 1 skipped.

- **7h** (`STEP_7h.md`): HANDOFF candidate 3's Censo 2010/2020 dwelling tabulados and 7d's
  leftover owners by sex, unattended; checks only (no loader, derivation or dictionary
  changed).
  - `check_cpv_tabulados.py` on the raw items of Censo 2010's 8 dwelling tabulados by state
    (`14_NNA_ESTATAL.xls`: walls × roofs, tenure, rooms × acquisition, toilets, equipment,
    water supply, kitchen × fuel, waste) and Censo 2020's 16 (`16_vivienda.xlsx`: walls,
    roofs, cooking, fuel, chimney, bulbs and energy-saving bulbs, toilet use, equipment,
    waste separation and disposal, tenure, owners, deeds, acquisition, credit), dwellings
    and occupants.
  - The owners' sex (EIC 2015 14-14/14-16, Censo 2020 16-28): the owner items hold person
    rows (`NUMPER`), joined from the person file (`_with_owners`; 99 = not identified).
  - **18,546 cells, every one exact** in every state and the nation (the report: 72,015
    cells). Universes: 2010 without `CLAVIVP` 5–7, 2020 without 07–09; 2020's «sin focos
    ahorradores» = `FOCOS_AHORRA` 0 whatever the total.

- **7i** (`STEP_7i.md`): HANDOFF candidate 3's CGPV 2000 dwelling tabulados, unattended;
  checks only.
  - `check_cpv_tabulados.py` on the raw items of `C2KVI01`–`19` (floors, walls, roofs,
    occupants, rooms on `TOTCUART_INEGI`, bedrooms, kitchen, fuel, the exclusive sanitary
    service, drainage, water and its supply, electricity, tenure, age, goods, waste and its
    collection, the averages), dwellings and occupants: **10,461 cells**, every state but
    Chiapas within 0.021 points; Chiapas's small bases up to 1.79 (documented tolerances);
    the report 82,476 cells.
  - New `Weighted(mask, values)` cell parts and the «average» unit (VI19).

- **7j** (`STEP_7j.md`): HANDOFF candidate 3's EIC 2015 person tabulados, unattended; checks
  only. Population by `EDAD_QUIN` × sex (01-02), birth registration (01-03), the women 12+
  by marital status and their children born alive per woman (02-02), the children who died
  (03-01), unpaid work and its hours (09-02/03): **29,502 cells, every one exact** (the report:
  111,978 cells). The women of 02-02 gave their number of children (`HIJOS_NAC_VIVOS` < 98);
  unpaid work = an activity with hours, a mix of 0 and 999 = none.

- **7k** (`STEP_7k.md`): HANDOFF candidate 3's CGPV 2000 person tabulados, unattended; checks
  only. PO01 (age shares per sex), DI01/02/04 (disability by age, type, cause), FE03–05
  (children born alive and surviving per woman, the share who died), LI02 (language):
  **4,987 cells** within the 2000 band (Chiapas up to 0.34; LI02's nation 0.08, documented);
  the report 116,965 cells. Disability types: `DISOTRA_C` 299 → motor, 399 → mental, 960 →
  type not specified, 131/199/4xx and `DISOTRA_V` 7 → other.

- **7l** (`STEP_7l.md`): HANDOFF candidate 3's CGPV 2000 household and education tabulados,
  unattended; checks only. HO01/02/05/07 (households and their population by size, type,
  income from work and total income in minimum wages — exactly 3 wages fall in «2 to 3»),
  HO08 (averages per household, the members from the person file), ED02/04/06 (literacy and
  attendance by age and sex), ED12 (causes of non-attendance): **8,151 cells** within the 2000
  band (Chiapas up to 0.34; ED12's nation 0.06, documented); the report 125,116 cells.

- **7m** (`STEP_7m.md`): HANDOFF candidate 3's Censo 2010 ampliado topics, unattended; checks
  only. 01_02A (`EDAD_QUIN` × sex), 02_04A (children born alive), 06_02A (limitation causes),
  09_04A (health service use: institutions % of users), 10_02A (spouse's residence by union)
  and the `migrantes` file's 04_04A–06A by the state left: **11,913 cells, every one exact**;
  the report 137,029 cells.

- **7n** (`STEP_7n.md`): HANDOFF candidate 3's Censo 2020 ampliado workbooks 01/04/05,
  unattended; checks only. 01-02 (`EDAD_QUIN` × sex), 01-04 (birth registration), 04-02 (the
  born abroad by nationality), 05-02/04 (self-identification, understanding an indigenous
  language), 04-04–10 (the `migrantes` file by the state left): **10,758 cells, every one
  exact**; the report 147,787 cells. Full suite on the Mac on 7l's head: 1920 passed, 1 skipped
  (7m and 7n touched only the check script and its tests).

- **7o** (`STEP_7o.md`): HANDOFF candidate 3's rates, with the user («rates across
  editions»); checks only — no loader, derivation or dictionary changed.
  - `check_cpv_tabulados.py`: unit «rate» (per 1,000), `Check.combine` (the TGF = 5 × Σ
    rates / 1,000 after each block's seven rates), `_national` (national tabulados by
    locality size and the mother's age); nine checks (`_rate_checks`).
  - **Fertility rates** (Censo 2010 `02_01A`/`02_02A`, EIC 2015 02-03/04, Censo 2020 02-01/02;
    by state and nationally by locality size): **exact** in every state, the nation and every
    size. INEGI's rule, found on the data: the women of the age (at the census) whose last
    child born alive was born the year before, per 1,000 women of the age without children
    born alive 98 (topic omitted) or the last child's year 9999 — 99 (unspecified number)
    counts.
  - **Infant mortality, Censo 2020** (03-01, by size × the mother's age): **exact**, the last
    children born in 2019 dead with `EDAD_MORIR_TD` 0–364 per 1,000 of them, mothers 12–49.
  - **Infant mortality, Censo 2010/EIC 2015** (`03_01A`, 03-02): **not reproducible** from
    the sample (the user had it dug further first): INEGI's «Total» is not the sum of its
    age groups as counts under any denominator or grouping tried, so its estimate is no ratio
    of the records' weights. Checked anyway (user's choice) on the cohort rule with the
    largest gap as tolerance: 1.0 (2010), 1.8 per 1,000 (2015); the nation within 0.09/0.17.
  - The report (a fresh full run, every edition, 32 states, 1 h 05 min): 996 new cells, every
    one within its tolerance; **148,783 cells, 0 beyond tolerance**. `tests/test_cpv_tabulados.py`
    23 passed (7o touched only the check script, its tests and the docs).

- **7p** (`STEP_7p.md`): HANDOFF candidate 3's first item, with the user (Censo 2020's
  disability and migration causes, Censo 2010's by-state leftovers); checks only — no loader,
  derivation or dictionary changed.
  - Censo 2020 `06_discapacidad` 06-02/04/06 (disability, limitation, mental condition and
    their causes by sex, age, activity: 6c/6g/6y's flags, exact on the first try), 04-12
    (return migrants by duration, 04-12m its average), 04-14/15 (return and emigration causes
    by the precoded four-digit codes; 04-15 by the state left).
  - Censo 2010 05_01A/02A (self-identification, understanding; 14 states and «Resto de las
    entidades» = pseudo-state 98, `_REST`, via `ByOrigin`), 07_02A/05A (fields of study =
    `NOMCAR_C`'s first digit; 800 «carreras técnicas básicas» not specified — one record),
    08_06A/07A (division × sector, × hours), 12_02A (parents by age), 12_04A (kinship lines:
    INEGI's lines for «otro parentesco» found on the tabulado — uncles and godparents
    ascendants, nephews and godchildren descendants, «Familiar» not specified).
  - Readers: Censo 2010's plain state names (07_02A), a row INEGI leaves out reads as zeros
    (`_by_dims`); 7n's ethnicity helpers generalized.
  - **43,431 new cells, every one exact** (1 person; the nation's six-decimal shares ≤ 0.47);
    the report 192,214 cells, 0 beyond tolerance (the 2010/2020 sections spliced from one
    2010 + 2020 run, every earlier row unchanged). `tests/test_cpv_tabulados.py` 26 passed.

Design: [`PLAN.md`](PLAN.md). Recent units: [`STEP_7p.md`](STEP_7p.md), [`STEP_7o.md`](STEP_7o.md), [`STEP_7n.md`](STEP_7n.md), [`STEP_7m.md`](STEP_7m.md), [`STEP_7l.md`](STEP_7l.md), [`STEP_7k.md`](STEP_7k.md), [`STEP_7j.md`](STEP_7j.md), [`STEP_7i.md`](STEP_7i.md), [`STEP_7h.md`](STEP_7h.md), [`STEP_7g.md`](STEP_7g.md), [`STEP_7f.md`](STEP_7f.md), [`STEP_7e.md`](STEP_7e.md), [`STEP_7d.md`](STEP_7d.md), [`STEP_7c.md`](STEP_7c.md), [`STEP_7b.md`](STEP_7b.md), [`STEP_7a.md`](STEP_7a.md), [`STEP_6z.md`](STEP_6z.md), [`STEP_6y.md`](STEP_6y.md), [`STEP_6x.md`](STEP_6x.md), [`STEP_6w.md`](STEP_6w.md), [`STEP_6v.md`](STEP_6v.md), [`STEP_6u.md`](STEP_6u.md), [`STEP_6t.md`](STEP_6t.md), [`STEP_6s.md`](STEP_6s.md), [`STEP_6r.md`](STEP_6r.md), [`STEP_6q.md`](STEP_6q.md), [`STEP_6p.md`](STEP_6p.md), [`STEP_6o.md`](STEP_6o.md), [`STEP_6n.md`](STEP_6n.md), [`STEP_6m.md`](STEP_6m.md), [`STEP_6l.md`](STEP_6l.md), [`STEP_6k.md`](STEP_6k.md), [`STEP_6j.md`](STEP_6j.md), [`STEP_6i.md`](STEP_6i.md), [`STEP_6h.md`](STEP_6h.md), [`STEP_6g.md`](STEP_6g.md), [`STEP_6f.md`](STEP_6f.md), [`STEP_6e.md`](STEP_6e.md),
[`STEP_6d.md`](STEP_6d.md),
[`STEP_6c.md`](STEP_6c.md), [`STEP_6b.md`](STEP_6b.md), … [`STEP_0_probe.md`](STEP_0_probe.md).

**Host state.** The Mac and `wsl:~/mxcensus` both hold the full mirror (4148 registered
files; the MG 2015 files were built on the Mac and copied to `wsl` for the upload);
`wsl:~/mxcensus` was pulled to 6r on 2026-10-09 (the full suite ran there before the
merge: 1773 passed, 1 h 50 min) and holds a copy of the Mac's tabulados cache
(`data/dict/tabulados/`, without 6t's `2000/C2KHO04.xls` and `2015/12_hogares.xls` and 6w's
`2015/05_etnicidad.xls` and `2020/cpv2020_a_eum_07_educacion.xlsx`: the script fetches
them). 6s–7b were built on the Mac; on 2026-10-10 `wsl` (after a Tailscale re-login: the
user opens the printed URL) ran the 0.11.0 full suite on 7a + 7b's patch (moved by a `git
bundle` and a `git diff` over `scp`, byte-identical to the commit; 1882 passed) and was then
pulled to v0.11.0.
On 2026-10-10 (7c) `wsl:~/mxcensus` ran the 32-state sweep with 7c's patch applied, then was reverted to v0.11.0 (clean; `~/sweep_7c.py`/`.json` beside it). Its tabulados cache lacks 7c's `2000/C2KEM08.xls`, `C2KEM10.xls`, `C2KMI04.xls` and `2010/08_10A_ESTATAL.xls` (the script fetches them).
7d ran on the Mac only; `wsl`'s tabulados cache also lacks its 15 CGPV 2000 workbooks
(`C2KEM02/03/04/06/09/11`, `C2KMI02/05–12`; the script fetches them).
7e ran on the Mac only (a 32-state sweep, 6 processes, ~15 min).
7f ran on the Mac only (`--variables`, `--crosswalk`, `--validate` there; a 32-state sweep,
~1 min). On the night of 2026-10-10 `wsl:~/mxcensus` was fast-forwarded to 7f (b6c8aff, a `git
bundle` of 7c–7f over `scp`; not pushed) and ran the full suite there for the 0.12.0 release
(`~/pytest_7f.log`: **1907 passed, 1 skipped**, 1 h 56 min — the Mac's 7f count). 7g ran on the Mac (32-state sweeps, 5 processes, ~15 min each); 7h too
(the report, ~30 min; the Mac's tabulados cache now holds the eight 2010 `14_NNA` workbooks,
which `wsl`'s lacks — the script fetches them). 7i–7n ran on the Mac too; the Mac's tabulados
cache now holds every workbook in `SOURCES` (the full report takes ~60 min). `wsl` is at 7f
(its 7f suite: 1907 passed); moving 7g–7n there (`git bundle b6c8aff..cpv-integration`, as
for 7f) and its full suite wait for a Tailscale re-login.
7p ran on the Mac only (its tabulados cache now also holds 7p's eight 2010 workbooks; `wsl`'s
lacks them and 2020's `06_discapacidad` — the script fetches them).
`wsl:~/mxcensus3c` (3c's code copy) can be deleted.

## Kickoff prompt for the next session

> Continue the CPV census-family work in this repo (branch cpv-integration = main = v0.11.0
> + units 7c–7p). Read docs/cpv/HANDOFF.md first, then agree with me which next unit to
> take (candidates in HANDOFF §Next) before implementing it, following the session protocol
> in docs/cpv/PLAN.md. Use .venv/bin/python, not uv run. Run wsl tasks without asking; ask
> me before committing, pushing, installing packages or uploading.

## Review: decisions taken unattended (night of 2026-10-10/11) — kept

The user asked for the night's units to run without them (commit each locally; no push,
merge, version or upload), and on 2026-10-11 (7o's session) reviewed and **kept all of
them**, with 7f's two crosswalk renames:

1. **7g, constraint keys** (`cpv_constraints`, `cpv_ratio_constraints`): an older edition's
   kept pair is keyed by its own ITER column (2000 `PNACOENT`, 2005 `P_OE2000`, 2010
   `PRES2005`…; 18 keys), not the canonical name — so every key is a `load_cpv_iter` column.
   The alternative was a helper mapping canonical keys to columns.
2. **7g, CGPV 2000's own definitions**: `PNACOENT`/`P5_RESO95` count the born/living abroad
   (its dictionary: «fuera de la entidad o país», «en otra entidad o país»); `P5_CATOLIC`,
   `P5_NCATOLI`, `P5_SINRELI` count the 5+ only (the unspecified ages answer the item).
3. **7g, INEGI's unspecified entity in 2010 and 2020**: `PNACOE`/`_F`/`_M` on
   `ENT_PAIS_NAC_INEGI`, `PRESOE05`/`PRESOE15` (`_F`, `_M`) on `LUGAR_RES_5A` — for 2020 a
   departure from the frozen legacy cells (as 6y's `PCLIM_*`/`PCDISC_*`), exact in the
   strict municipalities where the legacy cells miss in 1–10.
4. **7g, new derived `RELIGION_INEGI`** (Censo 2010 only; the name is the session's): the
   2010 classification beside `RELIGION_CAT` (2020's grouping, the user's 6f choice), for the
   2010 `PNCATOLICA`/`POTRAS_REL`.
5. **7h–7n** changed only the maintainer check script (no decision with user-visible
   effect); their scope (the Censo 2010/2020 dwelling tabulados and the owners' sex; CGPV
   2000's dwelling tabulados; the EIC 2015's person tabulados; CGPV 2000's persons and
   households; Censo 2010's and 2020's persons and migrants) was the session's choice among
   the candidates. Their documented tolerances follow 7d's MI11 precedent: Chiapas's small
   bases (VI11 0.9, VI18 1.6/1.8 points) and three national cells that inherit Chiapas's
   error (VI18o 0.06, LI02 0.1, ED12 0.07).
6. **The report's 2000/2010/2020 sections** were regenerated by single-edition runs and
   spliced into `TABULADOS_REPORT.md` (7k–7n), to save the 50-minute full run per unit; a
   fresh full run at the end (every edition, 32 states, ~60 min) is **byte-identical** to the
   committed report (147,787 cells, none beyond tolerance).
7. **The `wsl` full-suite run on 7g–7n**, blocked that night by a Tailscale re-login, ran in
   7o's session (`wsl` reachable again; a `git bundle` b6c8aff..87cebf6): **1920 passed, 1 skipped** at 87cebf6 in 1 h 59 min — the Mac's 7l-head
   count, as 7m/7n touched only the check script and its tests.

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

1. **Release 7c–7p** as 0.12.0: the night's decisions are kept and the `wsl` full suite ran
   on 7n (§Review 7); move 7o–7p there (`git bundle 87cebf6..cpv-integration`; they touch
   only the check script and its tests), run `tests/test_cpv_tabulados.py` there, then merge
   into `main`, tag and push — the user's call.
2. Smaller:
   - a 2000 occupation bridge (CMO → SINCO; no published table; 7d checked the CMO groups,
     the first two digits of `OCUACTIV_C`, against C2KEM04);
   - a locality-level lineage (6a covered municipalities only);
   - CGPV 1990's undocumented `TIP_HOGAR` 6 (96,370 persons, all `N_F_GPOS` 99 and a 9xx
     relationship: a dwelling without its household composition; identity-labelled,
     `STEP_6u.md` §Left out);
   - the hand-curated wage tables as a generated YAML (`build_cpv.py` from INEGI's catalogs)
     if a later edition needs one;
   - CGPV 2000's other quantities typed as code ranges (`HORTRA`, `INGRESOS`, `INGTRHOG`…:
     `_QUANTITIES` could take them; the derivations read the raw codes, so only the
     labelled dtype changes);
   - 7p's kinship lines as a derived column (INEGI's 2010 lines for «otro parentesco» are
     now known: `STEP_7p.md`), if a constraint or a user needs them.
3. More tabulado checks (what 7d–7p left):
   - every edition's tabulados by locality size (they repeat the state ones on `TAMLOC`;
     7o's `_national` reads that layout): Censo 2010's 07_01A/04A, 08_04A/05A, 12_03A/05A
     (dated 2013, in the same `ESTATAL` file names), Censo 2020's 06-01/03/05 and 04-11/13,
     and the earlier units' by-size sheets;
   - a reproduction of the 2010/2015 infant mortality would need INEGI's procedure
     (`STEP_7o.md`): its rule is not in the sample.

## Open questions for the user

- None pending (7f's crosswalk renames were kept on 2026-10-11).

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
  7p: a Censo 2010 workbook may name its states without codes (07_02A: `_STATE_NAMES_2010`)
  or publish some states and «Resto de las entidades» (05_01A/02A: pseudo-state `_REST` = 98
  through `ByOrigin`, so all 32 states are needed); INEGI leaves out empty rows (Censo
  2020's 06-04 has no unspecified age in five states: `_by_dims` reads them as zeros). Every
  workbook dated 2013 in Censo 2010's `ESTATAL` names is by locality size, not by state.
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
  `_FROM_DWELLINGS` since 6z) and the person file (the head's `SEXO`). Both are
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
- **Household type on the persons** (6z): `derive` on a person frame of 2000 or 2010–2025
  needs `TIPOHOG`, the dwelling's item, which `cpv._load_level` attaches
  (`_attach_dwellings`, `_FROM_DWELLINGS`, which replaced 6v's `_DWELLING_FOR_HOUSEHOLDS`)
  and drops after `derive`. The test person builders carry it; the dwelling builders get
  `_HOUSEHOLD_ITEMS` (`TIPOHOG`, `NUMPERS`, the four `INGR_*`) through `_derive_dwellings`.
- **A cell is an AND of per-item category lists** (6z): «any of several items» needs a
  derived summary column (`INGR_OTROS` for `HOG_PERC`). Some indicator names equal item
  names (`ALIM_ADL1` = {`ALIM_ADL1`: «Sí»}); `get_tables_dict` does not mind.
- **A percentage's base may be a published count without a cell** (6z: `HOG_MEN_ALIM`):
  the tests take it from the estimates (`test_eic2025_constraints_equal_estimates`).
- **Sum bases** (7a): a `_PERCENT_BASES` value may be a tuple of counts, summed
  (`_base_parts`); tests and scripts must go through `_base_parts`, never use the value as
  a column name. The five-year ages are shares of the population of **specified** age, the
  women's and men's too (not of `POBTOT`/`POBFEM`).
- **The age universe in cells** (7a): persons of unspecified age (999) answer the marital,
  residence and commute items, and INEGI's numerators leave them out. A cell must carry its
  indicator's age condition (`EDAD_CAT`), even when the item is asked of that age only.
- **Unpublished bases** (7a): the disability by age is a share of the disabled of specified
  age; its counts take `PCON_DISC` (51 more persons nationally), so the test reads their
  shares on the specified-age cells (`test_eic2025_constraints_equal_estimates`). The
  employed's modes, `PCN_P3NHLI_CLI` and `PCN_HF` have no count at all (7e: they are
  ratio constraints).
- **`HOG_AFRO` on the dwellings** (7a): `_member_sources("viviendas", "2025")` now reads
  `AFRODES` too, so synthetic 2025 members carry it (`_HEAD_ALONE`).
- **Sweeps through `POOCH`** fetch any file missing from the user cache from the bucket
  (7a: the 2015 dwellings, which the person loader reads for `TIPOHOG`); the tests'
  `local_mirror` fixture reads `data/parquet` instead.
- **Censo 2010's place of work** (7b): `LTRABPAI_C` («en otro estado o país») holds the
  entity catalog (001–032, 900 topic omitted, 999) and the country catalog (600, 700,
  countries) in one column, though its FD names only `Tc_Pais_2010`. Its 999 is the
  entity's «no especificada» (`_RECODE` → 997, «No especificado»): INEGI's `08_15A` matches to
  the person only so. Its municipality items (`LTRABMUN_C`, `MUN05OTR_C`) hold the
  municipality of every Mexican answer, the own one too, despite the FD's «(otro)».
- **Places by municipality** (7b): `_lugar` compares the place's municipality with the
  person's own (`MUN`/`CVE_MUN`); the own entity without a municipality raises. The school
  and work items are asked of exactly the students and the employed (2010–2025), persons of
  unspecified age included; INEGI's tabulados leave those out, so cells and checks keep the
  age condition.
- **EIC 2015 dwelling tabulados** (7b) leave out `CLAVIVP` 7–9 (locales, móviles,
  refugios: 31,924,863 dwellings); its households count every dwelling (31,949,709).
  2015's `CLAVIVP` is un-padded (`pd.to_numeric` before comparing).
- **2020's FD names no catalog for `MUN_TRAB`** (its `MUN_ASI`/`MUN_RES_5A` name «MUN»):
  `test_source_codes_match_2020` excuses it (`_REF_WITHOUT_CATALOG`).
- **Minimum wages** (7c, `cpv_derived._SALARIOS_MINIMOS`): hand-transcribed daily wages (cents)
  and area tables; INEGI's monthly wage is daily × 30 (× 30.4 misses its tabulados by points).
  2010/2015 = INEGI's own catalogs (`data/dict/fd/{2010,2015}`; a test compares every
  municipality and skips without them); 2015's catalog has Coacoatzintla (30-036) where the
  DOF has Coatzintla (30-040), and the tabulado follows the catalog, so the slip is kept on
  purpose. 2020's border zone includes San Quintín (02-006). Compare incomes in cents: 5 ×
  1,675.20 = 8,376 must land in «3 a 5».
- **2000's groups differ** (7c): C2KEM08 and the 2000 ITER bound «menos de 1 / de 1 hasta 2 /
  más de 2 y menos de 3 / de 3 hasta 5»; 2010–2020 «hasta 1 / más de 1 a 2 / …». So
  `INGTRMEN_SM` has two dtypes (`_SM_2000` via `_period_dtypes`, `_SM`); a cross-edition
  stack of it needs a mapping.
- **CGPV 2000's residence in 1995 by municipality** (7c): INEGI's C2KMI04 counts more
  municipal migrants than the answers in Guanajuato, Oaxaca, Veracruz, Zacatecas and Chiapas
  (`Check.tolerance` documents it); Zacatecas = Trancoso's own-code answers. Its place of
  work (C2KEM10) has no such gap.
- **`Check.tolerance`** (7c) overrides the edition's tolerance per state (0 = the nation) for
  one check: use it only for a documented difference of INEGI's own.
- **Sweeps on `wsl`** (7c): its user cache is not filled, so a sweep through the loaders
  downloads every file from the bucket; patch `mxcensus.data._registry.POOCH.fetch` to read
  `data/parquet` (as `check_cpv_tabulados.run` does).
- **Origin cells** (7d, `check_cpv_tabulados.ByOrigin`): a cell part counted in the records'
  state of origin (outside 1–32 → 99) — `run` accumulates every part as `{state: Σ}`, the
  nation is the sum over all of them; a `Check(by_origin=True)` is dropped from partial runs
  (`--states` below 32), so `test_state_01_within_tolerance` never sees MI02/05/10–12.
- **Category keys** (7d): `_words` drops digits («2 ocupantes» = «3 ocupantes»); readers of
  numbered categories use `_tokens` (numbers kept, a footnote glued to a word dropped).
- **The occupants** (7d): the EIC 2015's occupant tabulados = Σ `FACTOR` × `NUMPERS` of the
  dwellings (`Check.weight`), exact; no person file needed.
- **The 2015 dwellings that cook** (7d, `_cooks_2015`): a place (`LUGAR_COCINA` 1–3) or a fuel
  (`COMBUSTIBLE` 1–4) given; a kitchen with the fuel not specified is not counted.
- **CGPV 2000's migrants file** (7d): movement by `MPAIRES_C` (700 «México» = returned, 999
  NE, else abroad), age at emigrating `MEDAD`, sex `MSEXO` (1/2), the state left
  `MLUGORI_C` (999 NE); Σ `FACTOR` = 1,632,790 (INEGI 1,633,052).
- **`run` reads each workbook once** (7d); the full report (every edition, 32 states) takes
  24 min on the Mac (~8 GB).
- **Ratio constraints** (7e, `cpv_ratio_constraints`/`cpv_ratio_terms`): separate from
  `cpv_constraints` (whose dicts feed `get_tables_dict`; a ratio is no cell). Each entry's
  `known` columns decide who leaves both sides; any other missing value counts 0 (Censo
  2010's `PRO_OCUP_C` relies on it). `cpv_ratio_terms` reads the **labelled** frame
  (`derived=True`): raw codes would count the sentinels (98/99) as children or years, so it
  raises on a non-categorical cell variable or a non-numeric value column. The value items
  are each edition's own (2010 `NUMHIJ`, 2020/2025 `HIJOS_NAC_VIVOS`).
- **Census averages vs the sample** (7e): even where the sample is the census (`FACTOR` 1
  for everyone, `POBHOG` equal), the sample's ages may differ from the ITER's (Oaxaca:
  20-228 has 510 persons of 15+ against 534), so a check of an average must also match its
  age group's count (`P_15YMAS`, `P_12YMAS_F`…). CGPV 2000's `FACTOR`-1 municipalities
  (207) do not reproduce its education at all.
- **The «Otro» dwelling classes** (locales, móviles, refugios; 2010 5–7, 2020/2025 07–09)
  have no rooms recorded (`TOTCUART` blank), so «every dwelling with rooms» = «"Vivienda"
  with rooms».
- **CGPV 2000's dwelling indicators count the first household** (7f, `cpv_derived._PER_DWELLING`,
  `_dwelling_cells`): any dwelling count on its frame must filter `PRIMER_HOGAR` «Sí» (its
  rows are households); the household indicators (`_HOUSEHOLD_INDICATORS`) count every row.
  A test comparing shares of `VIVPAR_HAB` must take the first households as the base
  (`test_6n_cells_equal_iter`).
- **Every class in 1990/2000** (7f, `_EVERY_CLASS`): their «Otro» dwellings carry the items,
  so their cells have no «Vivienda» condition; 2010–2025 keep it (their «Otro» items are
  blank). A new edition's cells: check whether its «Otro» rows are blank first.
- **Numeric derived columns** (7f): `derived_dtypes` may return `Int64` (`TOTCUART_INEGI`),
  which may be missing (`derived_schema`); code that iterates the derived dtypes must not
  assume `.categories` (`_categories` skips them, `_numeric_columns` takes them).
- **2000's rooms**: `TOTCUART` counts the kitchen; its ITER's rooms (`PRO_OCVP`, `VP2_5CUAR`)
  leave out an exclusive kitchen nobody sleeps in (`COCINA` 1 and `COCDOR` 4 — «No
  especificado» also starts with «No»: match the full label). 2010–2025's `PRO_OCUP_C`
  counts the kitchen.
- **The ITER rounds or truncates**: 1990/1995 truncate their averages and percentages (two
  decimals; 1995's localities round to one), 2000–2020 round (19-035 2000: 1.165 → 1.17).
  Compare within 0.005 + ε, or truncate.
- **The Conteo 1995's weights** (7f): `FAC_VIV` adds up to `VIVPAR_HAB` and `FAC_POB` to
  `OCUPVIVPAR` exactly in 31 states (state level only), calibrated apart, so dwelling-weighted
  occupants run short (PROM_OCUP 0.06 off at the median). Chiapas's weights carry its
  official total (+15–17% over its ITER, which lacks 15 municipalities). Its dwelling frame
  counts its persons into `NUMPERS` (`cpv._OCCUPANTS_FROM_PERSONS`): a column the person
  dictionary does not declare.
- **FD quantities written as code ranges** (7f, `build_cpv._QUANTITIES`): a zero-padded FD
  range (`0001..9999`) parses as codes; a count must be listed there to be numeric.
- **Constraint keys = the published columns** (7g, `cpv_derived._published_name`): every key
  of `cpv_constraints`/`cpv_ratio_constraints` is a column of the edition's aggregate. The
  cells and `_aggregate_indicators` stay on the canonical names inside (`_EDITION_CELLS` keys
  are canonical); only the output is renamed. A test that iterates `_EDITION_CELLS` must map
  each key through `_published_name` (`test_6n_cells_equal_iter`).
- **Strict «sample = census» municipalities** (7g): `FACTOR` 1, `POBHOG` and every age/sex-only
  constraint equal to the ITER's (2000: 51, 2010: 233, 2020: 130; Oaxaca 50/174/107). Use
  them to settle a definition: there every 2010 constraint is exact. What still misses there
  is INEGI's census processing: CGPV 2000 imputed the unspecified answers in its census (no
  schooling: the illiterate non-attenders mostly → «sin instrucción»), Censo 2020 swaps a few
  persons between affiliation and religion categories.
- **`RELIGION_INEGI`** (7g) exists for Censo 2010 only (its classification: neo-Israelites
  220100 «Otros credos»); `RELIGION_CAT` keeps 2020's grouping in every edition.
- **INEGI's unspecified entity in the constraints** (7g): the born and the residents five
  years earlier in another entity leave it out in 2010/2020/2025 (`_CELLS`); CGPV 2000's
  pairs include the abroad; the Conteo 2005 keeps the legacy cells (no unspecified entity).
- **Dwelling tabulado universes** (7h): Censo 2010's leave out `CLAVIVP` 5–7, Censo 2020's
  07–09, the EIC 2015's 7–9 (their items are blank); the class not specified counts.
- **The owners** (7h, `check_cpv_tabulados._with_owners`): the 2015/2020 owner items
  (`NUM_DUE_VIV1`/`2`, `DUE1_NUM`/`DUE2_NUM`) hold the owner's person row (`NUMPER`); 99 = not
  identified. The script's 2015/2020 dwelling frames carry `DUE1_SEXO`/`DUE2_SEXO` (raw codes)
  from a column-projected person read; 2015's codes are unpadded, so both sides compare as
  numbers.
- **CGPV 2000's dwelling tabulados** (7i) count every private dwelling once (the script's
  frame keeps the first household's row), the occupants with `NUMPERS`; `NUMHOGS` is blank for
  one household (fill 1). Chiapas's small bases miss by up to 1.8 points (its weights).
- **Averages in the tabulado checks** (7i): `Weighted(mask, values)` cell parts and
  `unit="average"` (num ÷ den); 2000's are compared within its band.
- **EIC 2015 person tabulados** (7j): 02-02's women are those who gave `HIJOS_NAC_VIVOS`
  (< 98); unpaid work (`ACTI_SIN_PAGO1`–8) = weekly hours per activity, 0 = none, 999 = not
  specified (a mix of 0 and 999 is «none», all 999 «not specified»); their 12+ leave out the
  unspecified ages. INEGI writes 0 for an average of nobody.
- **CGPV 2000's disability types** (7k, `check_cpv_tabulados._DISABILITY_TYPES_2000`): the
  items' own codes plus the classified `DISOTRA_C` (299 → motor, 399 → mental, 960 → type not
  specified, 131/199/421/422/430/499 → other) and `DISOTRA_V` 7 → other. «M.I.» in its
  tabulados = muestra insuficiente (missing).
- **CGPV 2000's household tabulados** (7l): table «hogares» = the dwelling file's household
  rows (the script's `_frame` keeps them all and, for 2000, attaches the members' counts and
  the head's age from the person file); income 999999 = not specified, 999998 top-coded;
  exactly 3 wages fall in «más de 2 hasta menos de 3».
- **Fertility rates** (7o): the women's age at the census; the denominator leaves out the
  topic omitted (children born alive 98) and the last child's year unspecified (9999), not
  the unspecified number (99). The by-size sheets (`_national`) hold the nation's cells only,
  so a partial run (`--states` below 32) compares only the fertility by state.
- **Infant mortality** (7o): «menos de un año» (`EDAD_MORIR_M`/`EDAMORM` 98) is INEGI's
  processing code for a death of unknown age among the children born less than a year before
  the census (it never occurs earlier); `EDAD_MORIR_D` 99 is the age unknown. Censo 2020
  counts `EDAD_MORIR_TD` 0–364 (both out); 2010/2015 are not reproducible (the additivity
  test: a ratio of weighted sums makes every «Total» the sum of its age groups as counts).
