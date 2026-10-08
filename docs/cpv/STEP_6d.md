# CPV Unit 6d — The 2015/2010 recoded items in `cpv_derived`

Done **2026-10-08** (with the user, on the Mac). Gate: tests (full suite green, §Tests) and
a 32-state `derived=True` sweep of both editions with no unmapped code (§Verification).

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| next unit | **6d**, the 2015/2010 recodes (HANDOFF candidate 1) |
| the recode tables (§Recodes) | **accepted** as proposed |
| 2015 commute items (7 codes vs 2020's 12) | **2015's own dummies**: one per 2015 code; the 2020 names where the mode is the same, 2015's wording for the three merged modes |
| `DHSERSAL_IMSS_BIENESTAR` in 2010/2015 (option not asked) | **left out** (a column of zeros would read as "nobody") |
| 2010 disability (`DISCAP1`–`8`: yes/no per activity, no degree) | **a 2010 flag `LIM_ACTIVIDAD` + 2010-only constraints** (`PCON_LIM`, `PSIN_LIM`, `PCLIM_*`) |
| 2010 marital status `ESTCON` (2020's codes, another name) | **included** (`_ALIASES`) |

## Recodes (`_RECODE`, into the Censo 2020 code space)

| item | edition | edition code → 2020 code |
|---|---|---|
| `DHSERSAL1/2` | 2015 | 1 Seguro Popular → 05; 2 IMSS → 01; 3 ISSSTE → 02; 4 ISSSTE estatal → 03; 5 Pemex/Defensa/Marina → 04; 6 privado → 07; 7 otra → 08; 8 no afiliado → 09; 9 → 99 |
| `DHSERSAL1/2` | 2010 | 1–5 the same; 6 privado → 07; 7 otra → 08; 8 sin derechohabiencia → 09; 9 → 99 |
| `CONACT` | 2015 | 10–15 → 10 (11–15: found working by the activity check); 16 tenía trabajo → 20; 20 buscó → 30; 31 estudiante → 50; 32 jubilado → 40; 33 quehaceres → 60; 34 limitación → 70; 35 no trabajó → 80 |
| `SITUA_CONYUGAL` | 2015 | 6 soltera → 08; 5 casada stays 05 (not split civil/religious; 2020's 05–07 are all `casado`) |
| `SITUA_CONYUGAL` | 2010 | read from `ESTCON`; the 2020 codes |
| `NIVACAD` | 2010 | 05 normal básica → 09; 09 normal de licenciatura → 10; 10 licenciatura → 11; 11 maestría → 13; 12 doctorado → 14; 04 covers both 2020 bachillerato codes |
| `NIVACAD`/`ESCOLARI` | 2015 | the 2020 codes (`ESCOLARI` is numeric there, same values) |

The derived categories (`CONACT_CAT`, `SITUA_CONYUGAL_CAT`, `EDUC`, the `DHSERSAL_*`
dummies) then come from the legacy maps, as in 6b. The 77 (2015) and 69 (2010) observed
`(NIVACAD, ESCOLARI)` pairs of all 32 states (blank and unspecified included) all land in
an `EDUC` category.

## Edition-specific derivations

- **`DHSERSAL_*` for 2010/2015** (`_dhsersal(codes)`): the 2020 dummies minus
  `DHSERSAL_IMSS_BIENESTAR`; `DHSERSAL_PUB` = any public code offered, `DHSERSAL_AFIL` =
  any code 1–8 offered.
- **EIC 2015 commute dummies** (`_traslado_2015(item)`), read in 2015's own code space:

  | 2015 code | dummy (`MED_TRASLADO_ESC_…` / `MED_TRASLADO_TRAB_…`) | 2020 |
  |---|---|---|
  | 1 | `Camión, taxi, combi o colectivo` | camión + both taxis |
  | 2 | `Metro, metrobús o tren ligero` | metro + metrobús |
  | 3 | `Vehículo particular (automóvil, camioneta o motocicleta)` | motocicleta + automóvil |
  | 4 | `Transporte escolar` / `Transporte de personal` (2015: «laboral») | the same |
  | 5, 6, 7, 9 | `Bicicleta`, `Caminando`, `Otro`, `No especificado` | the same |
  | blank | `Blanco por pase` | the same |

  2020's trolebús has no 2015 code. To compare with 2020, sum its dummies into 2015's
  groups (trolebús aside).
- **Censo 2010 `LIM_ACTIVIDAD`** (`_lim_actividad`): Sí when any of `DISCAP1`–`DISCAP7`
  holds its code (one item per activity), No when `DISCAP8` = 17 («no tiene»), No
  especificado when `DISCAP8` = 99. In every state, `DISCAP8` is blank exactly when an
  activity item is set (660,103 rows; none has both, none has neither), so no row is left
  without a value. 2010 gets no `DIS_*` and no
  `DISCAPACIDAD`/`LIMITACION`: its question has no degree of difficulty.

**Mechanics.** A column can now have one `_Derivation` per set of editions;
`cpv_derivations()` lists it once per derivation, and once per edition with `period=`.
`_dummies` takes an optional code → label map. The dummy sets and `DHSERSAL` now mark a
row with an unlisted code as missing (`_as_dummies`), so `derive` raises on it, as it
already did for the other columns. In 6b an unlisted code there gave all-zero dummies
silently.

### Columns per edition (after 6d)

| edition | personas | viviendas |
|---|---|---|
| 2025 | 56 (unchanged) | 15 |
| 2020 | 58 (unchanged) | 15 |
| 2015 | **33** (was 2): `EDAD_CAT`, `INGTRMEN_CAT`, `EDUC`, `CONACT_CAT`, `SITUA_CONYUGAL_CAT`, 10 `DHSERSAL_*`, 9 + 9 `MED_TRASLADO_*` | 5 (unchanged) |
| 2010 | **17** (was 4): `EDAD_CAT`, `INGTRMEN_CAT`, `HORTRA_CAT`, `EDUC`, `CONACT_CAT`, `SITUA_CONYUGAL_CAT`, `LIM_ACTIVIDAD`, 10 `DHSERSAL_*` | 4 (unchanged) |

## Constraints (`cpv_constraints`)

- **`_EDITION_CELLS`**: indicators an edition publishes under its own definition, on its
  own items, added for that edition whatever the crosswalk's `Comparable` says (the
  edition must still publish the column). For 2010:
  - `PCON_LIM` = `LIM_ACTIVIDAD` Sí;
  - `PSIN_LIM` = `LIM_ACTIVIDAD` No;
  - `PCLIM_MOT`, `PCLIM_VIS`, `PCLIM_LENG`, `PCLIM_AUD`, `PCLIM_MOT2`, `PCLIM_MEN`,
    `PCLIM_MEN2` = the labelled `DISCAP1`–`DISCAP7` category.

  `PCLIM_VIS`/`PCLIM_MOT2` share 2020's names with another concept (crosswalk `Comparable:
  false`). They now appear in 2010's constraints with 2010's cells. 2020 never sees the
  2010 cells.
- **2010: 91 → 126 person constraints.** The 35 new ones:
  - 9 limitation indicators;
  - `PDER_SS`, `PDER_IMSS`, `PDER_ISTE`, `PDER_ISTEE`, `PSINDER`. `PDER_SEGP` stays out:
    the crosswalk says 2010's Seguro Popular indicator is not comparable;
  - `P12YM_SOLT`/`CASA`/`SEPA`;
  - the 18 `EDUC` ones (`P15YM_SE*`, `P18YM_PB*`, `P15PRI_CO*`/`IN*`, `P15SEC_CO*`/`IN*`).
- 2015 still has none (no ITER, no estimates). 2010 dwellings still have none (no
  `CLAVIVP_CAT`).

## Verification

**The 32-state sweep** (a script, both editions):
- `load_cpv_personas(period, state=…, derived=True)` loaded every state of 2010 and 2015.
- The loader raises on an unmapped code, and its derived schema refuses missing values.
- No state failed.

**National weighted totals** (Σ `FACTOR`, all 32 states) agree with INEGI's published figures:
- **2010 `LIM_ACTIVIDAD` = Sí: 5,739,270 (5.1%)**. This is exactly INEGI's published count of
  people with a limitation in the 2010 census (cuestionario ampliado).
- **2015 health coverage**:
  - not affiliated: 20.62 M (17.3% of 119.5 M), INEGI's published share;
  - affiliated (`DHSERSAL_AFIL`): 98.22 M;
  - Seguro Popular (`SALUD_PUBLICA`): 49.02 M;
  - IMSS: 38.49 M.
- **Shares across 2010 → 2015 change smoothly**:
  - `Posbásica` 25.5% → 29.2%;
  - `Trabaja` 38.2% → 37.7%;
  - `casado` 41.9% → 42.8%;
  - Seguro Popular 26.6 M → 49.0 M, the program's expansion.

**2010 sample vs the census ITER** (national, Σ over the 32 state rows). The sample is the
cuestionario ampliado, and its `FACTOR` reproduces the ampliado tabulados, not the census
counts, so only closeness is expected:

| indicator | sample | ITER | diff |
|---|---|---|---|
| `POBTOT` | 111,960,139 | 112,336,538 | −0.3% |
| `PEA` / `POCUPADA` | 44,768,254 / 42,699,571 | 44,701,044 / 42,669,675 | +0.2% / +0.1% |
| `P12YM_SOLT` / `CASA` / `SEPA` | 29,929,274 / 46,879,066 / 8,636,452 | 29,853,117 / 46,651,603 / 8,162,339 | +0.3% / +0.5% / +5.8% |
| `P15YM_SE` / `P18YM_PB` | 5,859,510 / 26,575,566 | 5,646,147 / 26,057,800 | +3.8% / +2.0% |
| `PDER_SS` / `PDER_IMSS` / `PSINDER` | 74,321,995 / 35,211,846 / 36,961,419 | 72,514,513 / 35,380,021 / 38,020,372 | +2.5% / −0.5% / −2.8% |
| `PCON_LIM` / `PSIN_LIM` | 5,739,270 / 105,402,663 | 4,527,784 / 105,646,736 | **+26.8%** / −0.2% |
| `PCLIM_MOT` … `PCLIM_MEN2` | | | +9% to +39% |

The limitation gap is the known difference between INEGI's two 2010 counts, not a recode
error: the ampliado's 5,739,270 is INEGI's own published figure. A model calibrated to the
ITER should know that the 2010 limitation cells will be pulled down by about a fifth.

## Tests (`tests/test_cpv_derived.py`)

- `test_source_codes_match_2020` (now 76 cases) compares each edition's codes after the
  recode with 2020's, up to reviewed tables:
  - `_GAPS`: 2020 codes the edition does not distinguish;
  - `_EXTRAS`: codes the edition adds — `DHSERSAL2` 1 (IMSS as the second option),
    2015 `ESCOLARI` 9 (in the FD range, never in the data).

  Own-code items (2015 commute, 2010 `DISCAP`) are checked against their own lists
  (`_OWN_CODES`); later commute options list a subset. Sources are resolved through
  `_ALIASES` (`ESTCON`). `ESCOLARI` compares its numeric range with 2020's codes.
- `test_recode_tables`: the 2015/2010 entries.
- `test_cpv_derivations_listing`: the 2015/2010 column sets; columns unique per edition.
- New: `test_derive_persons_2015_recodes`, `test_derive_persons_2010_recodes` (synthetic
  raw frames), `test_derive_older_editions_unknown_codes` (an unlisted commute or DHSERSAL
  code, a 2010 row with no `DISCAP` answer, an unmapped `EDUC` pair all raise).
- `test_cpv_constraints_per_edition`: the 2010 additions, `_EDITION_CELLS` verbatim,
  `PDER_SEGP` absent, no 2010 cells in 2020.
- `test_crosstab_per_edition` (2010): the `LIM_ACTIVIDAD` and `DISCAP2` tables build.
- Unchanged and green: 2020 = legacy (states 01/09/15), the EIC 2025 cells = its estimates.
- **Full suite**: 1614 passed, 1 skipped (29 min 38 s on the Mac's full mirror; 6c: 1586).
  The 5 warnings are the known data ones (DENUE, ENOE, the 2000 ITER's spilled names).

## Not done (HANDOFF §Next)

The other 2015/2010 items need catalog work, not code-list recodes:
- birthplace and earlier residence;
- parent/partner pointers;
- 2015's single `FINANCIAMIENTO`;
- the older SINCO/SCIAN occupation and activity catalogs;
- 2010 religion.

2000/2005 have no derived columns yet.
