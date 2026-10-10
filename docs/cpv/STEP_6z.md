# CPV Unit 6z — the EIC 2025's dwelling and household percentages

Done **2026-10-10** (on the Mac; HANDOFF candidate 2's second half, chosen by the user over
the persons half). Gate: every dwelling and household percentage of the EIC 2025 estimates
becomes a count (`load_cpv_estimaciones(counts=True)`) and a constraint, each equal to the
estimates at every published geography; tests green.

## The gap

6y left 190 of the estimates' 278 percentages: their cells did not exist. 63 of them are
dwellings and households (the persons' 127 — age groups, commute, health use… — are the
next unit):

- 38 dwelling characteristics: crowding, walls (4), roofs (4), floors (2), cooking place
  (3) and fuel (2), water and energy equipment (6), waste separation (4) and disposal (3),
  pay TV, tenure (4) and deeds (4);
- 23 household items: the class (familiar or not), income from other sources than work
  (any, none, and each of the four), food access (2) and insecurity (5 adults', 6
  minors'), forced displacement (2);
- 2 person counts: the population in familiar and not familiar households.

## The user's choices

- **The unit**: the dwellings and households (not the persons first).
- **`HOG_MEN_ALIM`** («hogares con menores de edad», a published count) is left out as a
  constraint: no rule reproduces it (below). It stays the base of the minors' food items.
- **`OCUP_CUARTO_CAT`** (crowding) on the dwellings of 2010–2025 (one household per
  dwelling; CGPV 2000's dwelling rows are households, so it is left out there).
- **`CLASE_HOG`** on the dwellings and persons of every edition with `TIPOHOG` (2000,
  2010–2025: the same codes in all five).

## Finding each percentage's base

As in 6y: Σ `FACTOR` over the indicator's cells ÷ Σ `FACTOR` over each candidate base's, at
all 2,769 geographies with a published value, against the published percentage. Every one
of the 63 matched within its rounding (≤ 0.005) on the first reading of its description,
with these bases and rules:

| percentages | base | rule the description does not spell out |
|---|---|---|
| `PCN_VPH_*` (34) | `VIVPARHAB_C` | |
| `PCN_VPH_PROPIA` | `VIVPARHAB_C` | «propia» = `TENENCIA` 1 or 2 (owned, or being paid for) |
| `PCN_VPH_OTRASIT` | `VIVPARHAB_C` | 5 (intestate or in litigation) and 6 (other) |
| `PCN_VPH_PROPRESI`, `_PERNORES`, `_NOESCRI`, `_ESCRIDES` | `VPH_PROPIA` (derived) | the deeds are shares of the owned dwellings; «se desconoce» = `ESCRITURAS` 8 «No sabe» |
| `PCN_VPH_2_5OCU` | `VIVPARHAB_C` | `NUMPERS` ÷ `TOTCUART` (rooms counting the kitchen) > 2.5 |
| `PCN_HOG_FAM`, `_NFAM` | `TOTHOG` | `TIPOHOG` 4 (unspecified familiar type) is familiar; 9 is neither |
| `PCN_HOG_PERC`, `_NPERC` | `TOTHOG` | any of the four items yes; all four no |
| `PCN_HOG_ALIM_N`, `_ALIM` | `TOTHOG` | `ALIMENTACION` «Sí» = they ran out of food |
| `PCN_ALIM_ADL*`, `PCN_ING_ADL*`, `PCN_DESP_*` | `TOTHOG` | `ING_ALIM_ADL*` is asked only after an adult item yes; the base is still every household |
| `PCN_ALIM_MEN*`, `PCN_ING_MEN*` | `HOG_MEN_ALIM` (published) | |
| `PCN_POBHOG_FAM`, `_NFAM` | `POBHOG` | the person's household's `TIPOHOG` |

`VPH_PROPIA` is itself a count behind a percentage, so `_percent_counts` derives it first
(as 6y's `PEA` before `PEA_F`).

## `HOG_MEN_ALIM` has no cell

The minors' food items are asked exactly when the household has a minor **and** reported
some adult food insecurity (no household without a person under 18 answered them), except
572 households with a minor and insecurity that were not asked: the questionnaire's filter
of minors is not the final ages. `HOG_MEN_ALIM` follows that filter:

| candidate | exact (of 2,503 states and municipalities) | nationally (published 19,071,553) |
|---|---|---|
| a person under 18 | 1,264 (never below) | 19,081,595 |
| … without the 572 not asked | 1,382 (never below) | 19,079,546 |
| a person under 18 other than the head | 1,541 | 19,068,833 |
| under 18, not head or partner / in a union / domestic workers / imputed records | ≤ 1,227 | |

None is exact, so it is not a constraint (the user's choice). The six minors' percentages
are: their numerators are exact, and their counts come from the published base.

## What changed

- `cpv_derived`:
  - new derived **`OCUP_CUARTO_CAT`** (dwellings 2010–2025, `_ocup_cuarto`): «Hasta 2.5»,
    «Más de 2.5», «No especificado» (rooms 99), «Blanco por pase» (no rooms: classes
    without characteristics); any other room code raises;
  - new derived **`CLASE_HOG`** (dwellings 2000 and 2010–2025, and their persons;
    `_clase_hog`): «Familiar» (`TIPOHOG` 1–4), «No familiar» (5, 6), «No especificado» (9);
  - new derived **`INGR_OTROS`** (dwellings 2015–2025, `_ingr_otros`, `_YES_NO`): «Sí» when
    any of `INGR_PEROTROPAIS`/`INGR_PERDENTPAIS`/`INGR_AYUGOB`/`INGR_JUBPEN` is yes, «No»
    when all four are no, else «No especificado» (same codes 2015–2025);
  - `_EDITION_CELLS`: `("viviendas", "2025")` += `_DWELLINGS_2025` (38, each with the class
    «Vivienda») and `_HOUSEHOLDS_2025` (23); `("personas", "2025")` += `POBHOG_FAM`/`_NFAM`.
- `cpv`: the persons of 2000 and 2010–2025 read their household's raw `TIPOHOG` from the
  dwelling file for `derived=True` (`_FROM_DWELLINGS`, which replaces 6v's
  `_DWELLING_FOR_HOUSEHOLDS`; `_attach_dwellings(df, table, period, state, harmonize)`:
  a column-projected read through the new `_file_columns`, which `_person_columns` now
  calls; matched on the entity and `ID_HOG` in 2000, `ID_VIV` elsewhere, without zero
  padding; 2010 national keys under `harmonize`), dropped after `derive`.
- `cpv_aggregates._PERCENT_BASES`: 85 → **148**.
- Constraints: EIC 2025 persons 94 → **96**, dwellings 31 → **92**; no other edition
  changes (none publishes these indicators).
- Docs: `cpv_derived`/`cpv_constraints` docstrings, README, CLAUDE.md.

## The data

**EIC 2025, all 32 states** (`load_cpv_personas`/`load_cpv_viviendas(2025, derived=True)`,
the actual `cpv_constraints` cells), at all 2,776 geographies of the estimates (the nation
from the 32 states): **all 188 constraints** reproduce the estimates — the published counts
exactly, every count behind a percentage by its share of the base within 0.005 wherever the
percentage is published (2,769 geographies). The 63 new counts' reconstruction
(percentage × base / 100) is off our Σ `FACTOR` by INEGI's rounding: by municipality 0.07
at the median and 87 at most, by state 20 and 605, nationally ≤ 5,246 (`POBHOG_FAM`, of
130 M).

Some national totals (Σ `FACTOR`; 39.7 M households):

| indicator | count | indicator | count |
|---|---|---|---|
| `VPH_2_5OCU` (more than 2.5 per room) | 1,431,234 | `HOG_FAM` / `HOG_NFAM` | 33,413,007 / 6,244,207 |
| `VPH_PTAB` (brick, block… walls) | 36,995,100 | `POBHOG_FAM` / `_NFAM` | 123,607,687 / 6,667,414 |
| `VPH_TLOSA` (concrete roof) | 32,162,253 | `HOG_PERC` / `HOG_NPERC` | 19,899,585 / 19,741,049 |
| `VPH_COMGAS` (cook with gas) | 34,576,655 | `HOG_GOB` (government programmes) | 16,423,616 |
| `VPH_PANEL` (solar panel) | 607,108 | `HOG_ALIM_N` (ran out of food) | 2,595,085 |
| `VPH_PROPIA` (owned) | 26,224,831 | `ALIM_MEN1` (minors, little variety) | 2,068,476 |
| `VPH_PROPRESI` (deeds, the owner's name) | 20,737,234 | `DESP_INSEG` (displaced by violence) | 509,917 |

**The new derived columns, every edition × 32 states** (`load_cpv_personas`/
`load_cpv_viviendas(derived=True)`, 224 loads: 2000, 2010–2025 raw, 2010/2015 also
harmonized): no unmapped code; **every person's `CLASE_HOG` = its household record's**
(85.0 M person records, 119.6 M with the harmonized loads; none unmatched, none
different); raw = harmonized.

| edition | households familiar / not / unknown (persons in them) | more than 2.5 per room | income from other sources: yes / no / NE |
|---|---|---|---|
| CGPV 2000 | 21.07 M / 1.55 M / 17 k (95.3 M / 1.70 M / 50 k) | — | — |
| Censo 2010 | 25.78 M / 2.84 M / 70 k (108.7 M / 3.04 M / 187 k) | 2,207,510 | — |
| EIC 2015 | 28.39 M / 3.46 M / 106 k (115.4 M / 3.83 M / 319 k) | 2,023,549 | 13.13 M / 18.52 M / 305 k |
| Censo 2020 | 30.46 M / 4.51 M / 15 k (120.6 M / 4.90 M / 58 k) | 1,843,273 | 13.48 M / 21.41 M / 98 k |
| EIC 2025 | 33.41 M / 6.24 M / 42 k (123.6 M / 6.67 M / 118 k) | 1,431,234 | 19.90 M / 19.74 M / 59 k |

(CGPV 2000's households are its dwelling rows; its weights are the sample's, 6v.)

## Tests

- `test_derive_household_items_6z` (offline): the three columns' rules, dtypes and
  editions (2015 = 2025's codes), the persons' class from their builders' `TIPOHOG`, an
  unknown room/type/income code raises, a person frame without `TIPOHOG` raises.
- `test_attach_dwellings` (offline, fake files): 2000 on `ID_HOG`, 2010 raw and national
  keys, 2015 un-padded dwellings under `harmonize`, a missing dwelling raises, the 2005
  households' `CLAVIVPA` (6v) unchanged.
- `test_cpv_constraints_per_edition`: 2025 sizes 96/92 and the 6z cells (`VPH_2_5OCU`,
  `VPH_PROPIA` with both owned codes, `VPH_ESCRIDES` «No sabe», `HOG_PERC`/`NPERC` on
  `INGR_OTROS`, `HOG_ALIM_N`, no `HOG_MEN_ALIM`), none in 2000/2010/2020.
- `test_eic2025_constraints_equal_estimates` (real data, state 01 and its municipalities):
  all 188, a published base (`HOG_MEN_ALIM`) taken from the estimates.
- `test_percent_bases_contract`: 148 mapped, 130 not (3 published + 127 persons'), no
  dwelling or household percentage left; `test_estimaciones_counts`: the deeds over the
  derived `VPH_PROPIA`.
- `test_cpv_derivations_listing`, `test_derive_hog_ind_households` and the person builders:
  the new columns and the `TIPOHOG` the loader attaches (`_HOUSEHOLD_ITEMS` fills the
  dwelling builders).

Full suite on the Mac: **1856 passed, 1 skipped** (32 min, beside the 32-state sweep).

## Left out

- **The persons' 127 percentages** (the next unit): 5-year age groups by sex (48), the
  commute to school and work (31), health use (10), marital status, education levels,
  position at work, residence in October 2020, nationality of the born abroad, indigenous
  self-identification and understanding, disability by sex and age, attendance; with
  `HOG_AFRO`/`PHOG_AFRO` (published counts).
- `HOG_MEN_ALIM` (above). Averages and ratios (`PROM_OCUP`, `PRO_OCUP_C`, …) are not counts.
- Censo 2020 and the EIC 2015 ask most of these items too, but publish no ITER for them, so
  they get the derived columns, not the constraints.
