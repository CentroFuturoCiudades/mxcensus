# CPV Unit 6b — Derived columns on the CPV frames; constraints per edition

Done **2026-10-08** (with the user, on the Mac). Gate: tests — ✅ (`tests/test_cpv_derived.py`,
73 tests; full suite: 1583 passed, 1 skipped). The same session first ran the pending **release batch**
(§Release batch).

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| `DHSERSAL` 05/06 in 2025 (codes swapped, one widened) | **new neutral names for both editions**, mapped by meaning: `DHSERSAL_SALUD_PUBLICA` (2020 05, 2025 06) and `DHSERSAL_IMSS_BIENESTAR` (2020 06, 2025 05); the legacy names stay in `load_extended_personas` only |
| editions | **2020 + 2025 in full; 2015/2010 only the items with identical code lists**; their recoded items wait |
| API | **`derived=` flag, off by default**, on `load_cpv_personas`/`load_cpv_viviendas`/`load_cpv_survey`; computed from the raw codes before labelling |
| crosstabs | **filter per edition**: one CPV constraint set, kept per edition when the indicator is published and its cells exist; one table tested per edition |

Stated in the session without objection: 2025 `SITUA_CONYUGAL` keeps the legacy grouping
(01, 06–08 → casado; 02–05 → separado, both new «separada» codes with divorciada and viuda as
in 2020; 09 → soltero; 99 → No especificado). `TENENCIA` (recoded in 2025) feeds no derived
column or constraint, so nothing was needed.

## `mxcensus.cpv_derived` (new)

- **The registry** (`_registry()`): 25 derivations, each a `_Derivation(table, columns,
  sources, periods, func)`.
  - `func` sees the source items as float codes **in the Censo 2020 code space** (blank =
    NaN). It maps them with the legacy dictionaries (`variables_personas.yaml`/
    `variables_viviendas.yaml`, `_legacy_map`) and casts to the legacy schema's dtype
    (`_legacy_dtypes`, read from `extended_*._build_schema()`).
  - So the 2020 columns equal the legacy ones by construction. The label-keyed legacy
    `EDUC` map is turned into a code-pair map (`_educ_map`).
- **Recodes** (`_RECODE`), edition → item → {code: 2020 code}, everything else identity.
  2025:
  - `SITUA_CONYUGAL` 01–09/99 → 1, 2, 2, 3, 4, 5, 6, 7, 8, 9;
  - `DHSERSAL1/2` 05 ↔ 06;
  - `ENT_PAIS_NAC`/`ENT_PAIS_RES_5A` 454 → 241 (Isla de Man) and 536 → 356 (Palaos).
    The 2025 country catalog (`ENTIDAD_PAIS.csv`) renumbered these two. The other 256
    codes are the same, and 18 country names were reworded.
- **`derive(df, table, period)`** reads the raw codes (padded or not; `ENT` or `CVE_ENT`,
  `_ALIASES`) and appends the columns. It raises when:
  - a source code has no derived category (a recode gap);
  - a source is missing;
  - a derived name is already in the frame;
  - the table is not `personas`/`viviendas`.
- **Loaders**: `_load_level(…, derived)` derives after the keys and before labelling, then
  validates the derived columns (`derived_schema`: their categorical dtype, no missing
  value). They pass untouched through `label_frame` and the labelled schema, which ignore
  columns outside the dictionary.
- **`cpv_derivations(table, period)`** lists the columns per edition; `derived_dtypes`.
- **Two deliberate differences from the legacy frames:**
  - the two `DHSERSAL` names (`DHSERSAL_RENAMES`);
  - fixed dummy sets: one column per code of `MED_TRASLADO_ESC_*`, `MED_TRASLADO_TRAB_*`
    and `FINANCIAMIENTO_*`. The legacy loader makes only the observed ones, 50–56 person
    columns depending on the state. As there, a blank second or third item sets
    `…_Blanco por pase`.

### Columns per edition

| edition | personas | viviendas |
|---|---|---|
| 2020 | 56: `EDAD_CAT`, `INGTRMEN_CAT`, `HORTRA_CAT`, `EDUC`, `OCUPACION_C_COARSE`, `ACTIVIDADES_C_COARSE`, `DIS_CON`, `DIS_LIMI`, 11 `DHSERSAL_*`, 14 + 14 `MED_TRASLADO_*`, `CONACT_CAT`, `SITUA_CONYUGAL_CAT`, `ENT_PAIS_NAC_CAT`, `ENT_PAIS_RES_CAT`, `IDENT_MADRE/PADRE/PAREJA/HIJO_CAT`, `RELIGION_CAT` | 15: `CLAVIVP_CAT`, `CUADORM_CAT`, `TOTCUART_CAT`, `DRENAJE_CAT`, `INGTRHOG_CAT`, 10 `FINANCIAMIENTO_*` |
| 2025 | 54: the same minus `RELIGION_CAT` and `IDENT_HIJO_CAT` (no `RELIGION`/`IDENT_HIJO` items) | 15 |
| 2015 | `EDAD_CAT`, `INGTRMEN_CAT` | `CLAVIVP_CAT`, `CUADORM_CAT`, `TOTCUART_CAT`, `DRENAJE_CAT`, `INGTRHOG_CAT` |
| 2010 | `EDAD_CAT`, `INGTRMEN_CAT`, `HORTRA_CAT`, `CONACT_CAT` | `CUADORM_CAT`, `TOTCUART_CAT`, `DRENAJE_CAT`, `INGTRHOG_CAT` |

- 2010's `CONACT` has the 2020 codes (10, 13–19, 20, 30, 40–80, 99) with other wording, so
  it qualifies under "identical code lists".
- 2010's `HORTRA` range is 0–168 (2020: 0–140), which still falls in the `81YMAS` bin.
- 2015's `CLAVIVP` is 2020's classification, unlike 2010's.
- Not covered for 2015/2010, because their code lists differ:
  - `DHSERSAL` (2015 reorders the codes; 2010 has no 99);
  - `NIVACAD`/`ESCOLARI` (2010: other levels; numeric `ESCOLARI`);
  - the commute items (2015: 7 codes);
  - `SITUA_CONYUGAL` (2015: 6 codes), `CONACT` 2015, `ENT_PAIS_NAC` 2015;
  - `IDENT_*` (2015: numeric pointers, other sentinels);
  - disability (2015 has none, 2010 its own `DISCAP1–8`);
  - `FINANCIAMIENTO` (absent).

## Constraints per edition (`cpv_constraints(table, period)`)

- **The CPV vocabulary** of the legacy constraint YAMLs (`_cpv_constraints`):
  - the neutral `DHSERSAL` names (`PDER_SEGP` → `DHSERSAL_SALUD_PUBLICA`, `PDER_IMSSB` →
    `DHSERSAL_IMSS_BIENESTAR`);
  - the 2020 FD's labels for the four dwelling items whose legacy dictionary words them
    differently (`AGUA_ENTUBADA`, `ABA_AGUA_ENTU`, `CONAGUA`, `SERSAN`: "Dentro de la
    vivienda" → "dentro de la vivienda?"; `_relabels`, matched through the codes).
- **Kept per edition** when:
  1. the edition publishes the indicator: its ITER through `cpv_iter_crosswalk` (an older
     edition only where it is `Comparable`; the flag never excludes the newest edition's
     own column), or the EIC 2025's national estimates;
  2. every variable and category exists in the edition's labelled `derived=True` frame
     (`_categories`: the dictionary's categorical dtypes plus `derived_dtypes`).

| edition | personas (of 157) | viviendas (of 46) |
|---|---|---|
| 2020 | 157 | 46 |
| 2025 | 25 (estimaciones) | 3 (`TOTHOG`, `HOGJEF_F`, `HOGJEF_M`) |
| 2015 | 0 (no ITER, no estimates) | 0 |
| 2010 | 91 | 0 (every dwelling constraint uses `CLAVIVP_CAT`) |

**One table per edition** (tests):
- `get_tables_dict(cpv_constraints(…), frame.dtypes)` and the age × sex
  `create_cont_table` run for 2010, 2020 and 2025.
- For 2025 the cells are checked against the published estimates. Σ `FACTOR` over each
  constraint's cells equals the state estimate **exactly** for 22 person and 3 dwelling
  indicators (state 01 in the test; all 32 states in §Verification).

## Finding: the legacy disability flags are not INEGI's definitions

The three remaining 2025 indicators differ (state 01):

| indicator | microdata | published | INEGI's rule, found by fitting |
|---|---|---|---|
| `PCON_DISC` (`DIS_CON` = Sí) | 74,608 | 74,620 | any item 3/4 **or 8** ("degree unknown"): 74,620 ✓ |
| `PCON_LIMI` (`DIS_LIMI` = Sí) | 213,084 | 180,240 | any item 2 and **not** disabled (incl. 8): 180,240 ✓ |
| `PSIND_LIM` (all six "No tiene dificultad", `DIS_MENTAL` = No) | 1,262,355 | 1,263,545 | not pinned (closest: 1,263,337) |

- The legacy `DIS_CON`/`DIS_LIMI` are kept as they are, because 2020 must equal the
  legacy loader.
- Whether to add INEGI-definition flags is an open question for the user (HANDOFF).
- The test asserts that these three differ and the other 25 match.

## Verification

- **2020 = legacy, all 32 states, both tables.** Every legacy derived column equals the
  CPV one in values and dtype. That is 50–56 person columns and 13–15 dwelling columns per
  state, under the legacy names, on the legacy integer index. Every extra fixed dummy is
  all zeros. The test runs states 01, 09 and 15.
- **No unmapped code.** `derived=True` loads every state of 2025, 2015 and 2010 (persons
  and dwellings) without a missing derived value. The largest, state 15 of 2025, has
  2,295,122 persons and takes 25 s.
- **2025 estimates, all 32 states**: Σ `FACTOR` over the cells equals the state estimate
  exactly for all 22 person and 3 dwelling indicators in every state. The three
  disability indicators differ nationally by −4,483 (`PCON_DISC`), +2,963,073
  (`PCON_LIMI`) and −95,116 (`PSIND_LIM`).
- Labels and harmonization do not change the derived columns (per-column value counts
  are equal). Multi-state `harmonize=True` loads derive too (2010 states 01–02, national
  keys); a raw multi-state 2010 load still raises.

## Tests (`tests/test_cpv_derived.py`, new — 73)

- **Offline:**
  - the source codes of every (derivation, edition ≠ 2020, item) equal 2020's after the
    recode, from the bundled dictionaries (catalog items: their sentinels; the 2020/2025
    occupation and activity catalogs were compared by hand, identical);
  - the recode tables;
  - `cpv_derivations`;
  - `derive` on synthetic 2025/2020/2015/2010 rows: every recode, the blanks, `EstaEnt`,
    the dummies;
  - the errors;
  - `cpv_constraints` per edition.
- **Real** (local mirror):
  - 2020 = legacy (states 01/09/15 × both tables);
  - `derived=True` on each edition (dtypes, no NA, labels and harmonization invariance);
  - one crosstab per edition;
  - the EIC 2025 cells = estimates.

## Release batch (the same session)

- **Registered and uploaded** all 1,056 files built in units 3a–5b. Registry 2695 →
  **3751**, additions only.
  - 640 `cpv_`: EIC 2015 (64), Censo 2010 microdata (96) and ITER/AGEB (64), 2000/2005
    microdata (192) and ITER (64), 1990/1995 ITER (64) and microdata (96);
  - 416 `mg_`: MG 2010 (160), MG 2000/2005 (192), MG 1995 (64).
- **Rebuilt on `wsl`, byte-identical to the Mac build**, compared by `sha256`:
  - 2010/2015 were already there (224 files);
  - 1990/1995 came from fresh INEGI downloads (160);
  - 2000/2005 were built from ZIPs copied from the Mac, because INEGI throttled `wsl` to
    ~50 kB/s (256);
  - the MG frames came from the copied national ZIPs (416).
- **Upload**: `upload_hf.py upload` synced exactly the 1,056 new files (1.82 GB, 0 deletes,
  2,695 skipped as identical) and the bucket README.
- **Checks**:
  - a clean-cache fetch with the unpatched loaders read every new edition (2015 … 1990,
    the ITER/AGEB files, MG 1995–2010) and passed Pooch's hash checks;
  - `verify`: **3751 ok, 0 missing, 0 size mismatches** (every registry URL HEADed).
- **CLI and docs**:
  - `fetch --dataset cpv/mg --edition` offers the older editions (tests);
  - README, CLAUDE.md and the bucket README updated; version 0.7.0;
  - commit `915c6fa`. `main` stays at v0.6.0 (user's choice: merge after review).

## Deviations from the plan

- The plan said derived columns "on harmonized labelled frames". They are computed from
  the raw codes (as ENOE's flags are) and carried through labelling. The recode into the
  2020 code space does per-item what harmonization would do.
- 2015/2010 recoded items are not mapped (user's choice); the registry takes them later by
  adding editions and `_RECODE` entries.
