# CPV Unit 7f — CGPV 2000 per dwelling; the 1990/1995 averages

Done **2026-10-10** (on the Mac). HANDOFF candidate 1 (7e's leftover), widened by the user
at the session's start to the 1990/1995 ITER averages. Gate: every CGPV 2000 dwelling
constraint and average equal to its ITER where the sample is the census; the 1990/1995
averages within their samples' band; tests green.

## The user's choices

- **The unit**: «2000 per dwelling + 1990/1995 averages», over 2000 alone, the smaller
  items and more tabulado checks.
- **CGPV 2000's 33 dwelling constraints move** onto the first household and count every
  private dwelling class (over «keep them, add the ratios only»): exact in 186/186
  municipalities, against 39–186 before.
- **Names**: `PRIMER_HOGAR`, `TOTCUART_INEGI` (over `CUARTOS_SCE` and `HOG_PRINCIPAL`).
- **`VIVPAR_HAB`** as a dwelling constraint for 2000, 1990 and 1995 (over 2000 only, none).
- **CGPV 1990's dwelling cells widen** to every class too, by 2000's verified rule (its
  «Otro» is 0.1% of a 10% sample, so it cannot be checked there).
- **`OCUPVIVPAR`** as a 1990/1995 person total (over 1995 only, or leaving it out).

The crosswalk renames (1995 `PRO_O_VP`, 2000 `VP_AGUENT`) follow from the probe and are
flagged for the user's review (below, §Crosswalk).

## CGPV 2000 per dwelling

CGPV 2000's dwelling file has one row per household; the dwelling's items repeat in each,
`NUMPERS` is the dwelling's persons and `TOTPERS` the household's. **Every dwelling has
exactly one `NUMHOG` 01 row** in all 32 states (3.1% of the rows share a dwelling).

**The probe.** The municipalities whose every sampled person has `FACTOR` 1 (207) and whose
population in households equals the ITER's `POBHOG` (186, in 14 states, 112 in Oaxaca):
there the sample is the census.

| the dwelling cells | exact (of 186) | max \|Δ\| |
|---|---|---|
| every household row, «Vivienda» only (until 6z) | 39–186 | 47 dwellings |
| the first household's row, «Vivienda» only | 142–186 | 7 |
| **the first household's row, every class** | **186, every indicator** | 0 |

- **One row per dwelling.** `VIVPAR_HAB` and `OCUPVIVPAR` (Σ `NUMPERS`) are exact on the
  first households; on every row they count households.
- **Every class.** CGPV 2000 records the dwelling items of its «Otro» dwellings (locales no
  construidos para habitación, viviendas móviles; no refugio is in the sample), and its ITER
  counts them. The legacy cells' «Vivienda» condition comes from 2010–2025, whose «Otro»
  classes have their items blank.
- **The households' indicators** (`TOTHOG`, `HOGJEF_F`/`HOGJEF_M`) are exact on every row
  and stay there.

**New derived columns** (2000 dwellings):

- **`PRIMER_HOGAR`** («Sí»/«No», `_primer_hogar`): «Sí» on the `NUMHOG` 1 row.
- **`TOTCUART_INEGI`** (`_totcuart_inegi`): the rooms as the 2000 ITER counts them. Its
  `VP2_5CUAR` says «no incluye cocina exclusiva»: `TOTCUART` (which counts the kitchen)
  less 1 when the dwelling has a room for cooking (`COCINA` 1) where nobody sleeps
  (`COCDOR` 4). An unspecified `COCDOR` keeps the kitchen, and `TOTCUART` 99 gives a
  missing value. It is the **first numeric derived column** (`Int64`):
  - `derived_dtypes` may now return a non-categorical dtype;
  - `derived_schema` lets it be missing;
  - `derive` skips its missing-category check;
  - `_categories` leaves it out and `_numeric_columns` adds it.

**The cells** (`cpv_constraints("viviendas", …)` → `_dwelling_cells`, every indicator but
`_HOUSEHOLD_INDICATORS`):
- `_EVERY_CLASS` (1990, 2000): the «Vivienda» condition is dropped;
- `_PER_DWELLING` (2000): `PRIMER_HOGAR` «Sí» is added;
- `VIVPAR_HAB: {}` is a new edition cell, so 2000's counts the first households.

**The averages** (`cpv_ratio_constraints("viviendas", 2000)`, on the first households):

| indicator | rule | exact (of 186) | the alternatives |
|---|---|---|---|
| `PROM_OCUP` (`PRO_OVP`) | Σ `NUMPERS` / dwellings | 186 (rounded; 94 truncated) | — |
| `PRO_OCUP_C` (`PRO_OCVP`) | Σ `NUMPERS` / Σ `TOTCUART_INEGI`, `known` `TOTCUART_INEGI` | 186 (19-035: 1.165 → 1.17, a rounding tie) | `TOTCUART` as is 0 (max 1.58); every kitchen out 1; every occupant over the known rooms (2010's rule) 107; an unspecified `COCDOR` as no one sleeping 44 |

2000 rounds; 1990 and 1995 truncate (below).

**The band** (the sample against the ITER, 32 states):

| indicator | median \|Δ\| | max \|Δ\| |
|---|---|---|
| `PROM_OCUP` | 0.011 | 0.055 (Baja California) |
| `PRO_OCUP_C` | 0.019 | 0.071 (Guerrero) |
| `VIVPAR_HAB` | 0.5% | 7.6% |

2000's weights sit above `POBHOG` by 0.07–8.9% (6v). In state 01 the 31 dwelling edition
cells are within 1.56 points of the ITER (`VP_BOILER`; the test's tolerance went from 3.0
to 2.0).

## The 1990/1995 ITER averages

**What the ITER publishes.** The occupants per dwelling are `OCUPVIVPAR / VIVPAR_HAB`,
truncated to two decimals:
- 1990's `PROM_VIV` at all 99,983 geographies;
- 1995's `PRO_O_VP` at its 32 states and 2,413 municipalities (its localities round to one
  decimal).

The 1995 descriptor's «población total entre el total de viviendas» is not what it
publishes. Both counts are published, but `OCUPVIVPAR` is no dwelling cell (it is a sum
of occupants), so the average is a ratio constraint on the dwellings.

**CGPV 1990** (a 10% extract, unweighted):
- The extract holds exactly 10.00% of the ITER's private dwellings in every state (within
  0.06%), but its occupants run about 0.4% over in every state.
- `PROM_OCUP` = Σ `NUM_PERS` / dwellings: within 0.021 at the median, 0.073 at most
  (Colima), mean +0.028.
- `PROM_CUA` (`PRO_OCUP_C`) = every occupant over the rooms of the dwellings that gave them
  (`T_CUARTOS`, the kitchen counted: Censo 2010's rule). It is within 0.006 at the median
  and 0.037 at most (Guerrero). The candidates, in the state band:

  | rooms | median \|Δ\| | mean Δ (truncation-corrected; also bias-corrected) |
  |---|---|---|
  | `T_CUARTOS`, every occupant / the known rooms | 0.006 | +0.002; −0.005 |
  | `T_CUARTOS`, known rooms on both sides | 0.005 | −0.006; −0.013 |
  | less a kitchen nobody sleeps in (2000's rule) | 0.42 | — |
  | less any kitchen | 0.56 | — |
  | bedrooms | 1.11 | — |

  The sample cannot settle the `known` rule firmly. The chosen one sits closer either way,
  and it shares its numerator with `PROM_VIV` (`OCUPVIVPAR`).
- `NUM_PERS` equals the dwelling's person rows in every dwelling.

**The Conteo 1995**:
- It has no occupant item, so its dwelling frame (built from the person file) counts each
  dwelling's persons into **`NUMPERS`** (`Int64`, `cpv._OCCUPANTS_FROM_PERSONS`). Then
  `PROM_OCUP` = Σ `NUMPERS` / dwellings.
- Its weights are calibrated apart. Σ `FAC_VIV` = `VIVPAR_HAB` and Σ `FAC_POB` =
  `OCUPVIVPAR` exactly in 31 states, at the state level only (none of the 664
  municipalities the sample covers is exact).
- So Σ `FAC_VIV`·`NUMPERS` runs short of the occupants: the sample's average sits 0.060 off
  at the median, 0.213 at most (Zacatecas), mean −0.030 (Aguascalientes −0.187).
- **Chiapas** is the exception. Its weights add up to 14.8% more dwellings and 17.1% more
  persons than its ITER. It has the 15 municipalities the ITER lacks (STEP_5b.md) under
  none of the sample's codes, so the weights carry the state's official total, with its
  estimate for the municipalities not counted.

**Left out**: the Conteo 1995's percentages (`P_P0A4`, `P_P15ALFA`, `P_VIVP_EL`…). Each is
a truncated share of published counts, mostly of `POBTOT` whatever its description says
(`P_P15ALFA` = `P15_ALFAB` / `POBTOT`), so the count constraints imply them.

## The person total of 1990/1995

1990 and 1995 publish no `POBHOG` (6v's universe cell). Their samples hold the occupants of
private dwellings, `OCUPVIVPAR`; the ITER's `POBTOT` adds the collective dwellings'.
- The Conteo's `FAC_POB` adds up to `OCUPVIVPAR` exactly in 31 states (not Chiapas), while
  `POBTOT` is 0.3–1.1% higher.
- 1990's extract × 10 sits within 1.4% of either.
- New person cell **`OCUPVIVPAR: {}`** (1990, 1995; `_EDITION_CELLS`) beside `POBTOT`.
- From 2000 on `OCUPVIVPAR` = `POBHOG` (2010/2020 exactly, 2000 within 0.03%; the Conteo 2005
  differs), so it is not added there.

## Dictionaries

The 1990 and 2000 FDs write the number of persons in the dwelling with leading zeros
(`0001..9999`), like a locality code, so `_dict_fd` reads it as a code list (`Tipo:
string`). New in `build_cpv.py`: `_QUANTITIES` (1990 `NUM_PERS`, 2000 `NUMPERS`) and
`_label_quantities`, which makes such an entry numeric with the FD's range. An entry that is
no longer a code range raises.
- `--variables`: only those two entries changed, the other 30 YAMLs are byte-identical;
- `--validate`: 0/897, the report unchanged.

Labelled 1990 person and dwelling frames and 2000 dwelling frames now carry them as
`Int64`.

## Crosswalk (decided on the data; for the user's review)

- **1995 `PRO_O_VP` → `PROM_OCUP`** (`Renombrar` 1995): the same indicator as 1990's
  `PROM_VIV` (above). The note said it divided the total population by the total dwellings.
- **2000 `VP_AGUENT` → `VPH_AGUADV`** (`Renombrar` 2000): the cells on `DISAGU` 1–2 (water
  inside the dwelling or the lot) are exact in all 186 municipalities, 2010/2020's definition.
  The note's «dentro o fuera de la vivienda» meant the same thing.
- `load_cpv_iter(1995)` now shows `PROM_OCUP` and `load_cpv_iter(2000)` shows `VPH_AGUADV`.
  2005's `VPH_AGDV` (the public network) stays.

## Constraint counts

| edition | personas | viviendas | ratio (viviendas) |
|---|---|---|---|
| 1990 | 23 → 24 (`OCUPVIVPAR`) | 9 → 10 (`VIVPAR_HAB`) | 0 → 2 |
| 1995 | 10 → 11 (`OCUPVIVPAR`) | 3 → 4 (`VIVPAR_HAB`) | 0 → 1 |
| 2000 | 70 | 35 → 36 (`VIVPAR_HAB`) | 0 → 2 |

## Found, not changed

Some older editions' constraint keys are not the ITER frame's column names. The crosswalk
pairs them but does not rename them (another date or definition, `_XW_PAIRS_KEPT`):
- 2000: `PNACOE`, `PRES2015`, `PRESOE15`, `PCATOLICA`, `VPH_EXCSA` (`VP_SERSAN`);
- 2005: `PRES2015`/`PRESOE15*`, `PDER_SEGP`, `VPH_AGUADV`/`VPH_AGUAFV`;
- 2010: `PRES2015*`/`PRESOE15*`.

A consumer that compares them with `load_cpv_iter` must map them through
`cpv_iter_crosswalk()` (the tests do). This is a HANDOFF candidate.

## What changed

- **`cpv_derived`**:
  - `_primer_hogar`, `_totcuart_inegi` and their derivations;
  - numeric derived columns (`derived_dtypes`, `derived_schema`, `derive`, `_categories`,
    `_numeric_columns`);
  - `_EVERY_CLASS`, `_PER_DWELLING`, `_dwelling_cells`;
  - `VIVPAR_HAB`/`OCUPVIVPAR` edition cells;
  - `_RATIOS` for 1990/1995/2000;
  - the docstrings.
- **`cpv`**: `_OCCUPANTS_FROM_PERSONS`, `_dwellings_from_persons`, the
  `load_cpv_viviendas` docstring.
- **`scripts/build_cpv.py`**: `_QUANTITIES`, `_label_quantities`; the crosswalk review
  (`_XW_PAIRS_RENAMED`, `_XW_PAIRS_KEPT`, `_XW_NOTES`).
- **YAML**: `variables_cpv_personas_g01.yaml`, `variables_cpv_viviendas_g01.yaml`,
  `cpv_iter_crosswalk.yaml`.
- **Tests**:
  - `test_derive_primer_hogar_totcuart_inegi`;
  - `test_2000_dwellings_equal_iter` (Sonora's 22 municipalities);
  - `test_1990_1995_occupants`;
  - `test_dictionary_quantities_7f`;
  - the per-edition sizes and cells; `test_crosswalk_1990_1995_pairs`;
  - `test_6n_cells_equal_iter` (2000's base: the first households);
  - `_OWN_CODES` (`NUMHOG`, `COCINA`, `COCDOR`) and `_HOUSEHOLD_ITEMS`.
- **Docs**: README, CLAUDE.md, PLAN, HANDOFF.

## Verification

- A 32-state sweep through the API (`load_cpv_viviendas(derived=True)`, `cpv_constraints`,
  `cpv_ratio_terms`; 6 processes, ~1 min):
  - 2000's 36 dwelling constraints exact in all 186 municipalities, the two averages within
    0.005;
  - the 1990/1995 bands as above.
- `--validate` 0/897.
- Full suite on the Mac: 1905 passed, 2 failed, 1 skipped (31 min). The two failures pinned
  the 1995 dwelling frame's columns, which now include `NUMPERS`; once updated they pass,
  so 1907 passed, 1 skipped.
