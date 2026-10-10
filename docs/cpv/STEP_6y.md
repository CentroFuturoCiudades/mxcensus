# CPV Unit 6y — the EIC 2025's percentages as constraints

Done **2026-10-10** (on the Mac; agreed with the user from a probe at the session's start —
it widens HANDOFF candidate 2). Gate: every percentage of the EIC 2025 estimates whose cells
the constraint sets hold becomes a count (`load_cpv_estimaciones(counts=True)`) and a
constraint, each equal to the estimates at every published geography; tests green.

## The gap

The EIC 2025 estimates publish 346 columns, **278 of them only as percentages** (`PCN_*`,
two decimals; three spelled `PNC_P6A14AN*` by INEGI). `cpv_constraints` matched the
indicators by their count names, so the EIC 2025 had **33** constraints (29 person, 4
dwelling) against Censo 2020's 207: no dwelling characteristic, no education level, no
activity rate, no health institution. 82 of the percentages are legacy cells under the
`PCN_` prefix (`PCN_VPH_PISOTI` ↔ `VPH_PISOTI`), and 190 are the survey's own (5-year age
groups, walls, roofs, cooking, waste, tenure, deeds, household types, income sources, food
security…).

## The user's choices

- **The unit**: the percentages whose cells exist (the 82, plus the count-like indicators
  a cell answers directly: `P_6A14`, `POB0_14_F/M`, `PNACOP_F/M`, `P6A14AN`); the 190 others
  later (they need new cells).
- **The disability and limitation by activity** (`PCDISC_*`, `PCLIM_*`): INEGI's definitions
  in **2020 and 2025** (not 2025 only), since Censo 2020's ITER agrees with them.
- **Born in another state** (`PNACOE`): a new derived **`ENT_PAIS_NAC_INEGI`** beside
  `ENT_PAIS_NAC_CAT` (as `EDUC_INEGI` beside `EDUC`), not leaving it out of 2025.
- **The counts**: `counts=True` on `load_cpv_estimaciones`, `Float64` and **unrounded**.

## Finding each percentage's base

A percentage is a share of some count — its base. For each `PCN_X`, Σ `FACTOR` over `X`'s
cells divided by Σ `FACTOR` over each candidate base's cells (every legacy cell and a few
more), at all 2,769 geographies with a published value (32 states, 2,478 municipalities,
the 233 localities of 50,000+, the 32 state remainders), against the published value. The
base is the one within the rounding (≤ 0.005) everywhere; there was always exactly one
(apart from synonyms such as `POBTOT`/`POBHOG`). Most bases are the population of the age
group or the dwellings; these are not:

| percentages | base |
|---|---|
| `PCN_PEA_F`/`_M`, `PCN_PE_INAC_F`/`_M` | the PEA / the inactive (the women's share **of the PEA**) |
| `PCN_POCUPADA*`, `PCN_PDESOCUP*` | the PEA of the sex |
| `PCN_PDER_IMSS`, `_ISTE`, `_IMSSB`, `PCN_PAFIL_*` | the affiliated (`PDER_SS`) |
| `PCN_PCDISC_*`, `PCN_PCLIM_*` | the persons with a disability / a limitation |
| `PCN_P3HLINHE*`, `PCN_P3HLI_HE*` | the indigenous-language speakers of the sex (3+) |
| `PCN_VPH_*` | `VIVPARHAB_C`, the dwellings of class «Vivienda» (= the legacy `VIVPARH_CV`) |

`cpv_aggregates._PERCENT_BASES` holds the 85 (the 82 minus `PNACOP`/`POCUPADA`/`PDER_SS`,
whose counts the estimates publish, plus `PNACOP_F`/`_M` and the three `PNC_P6A14AN*`). A
base may itself come from a percentage (`PEA` = `PCN_PEA` × `P_12YMAS`, then `PEA_F` =
`PCN_PEA_F` × `PEA`); `_percent_counts` resolves them in order.

## INEGI's definitions where the legacy cells differ

Eleven legacy cells did not reproduce their percentage. Each has INEGI's definition, found
on the same 2,769 geographies (exact to the rounding):

| indicator | legacy cell | INEGI's (2025) |
|---|---|---|
| `PCLIM_*` (6) | «poca dificultad» in the activity | … and `LIMITACION` (no disability in any activity) |
| `PCDISC_*` (6) | «mucha dificultad», «no puede» | … and «se desconoce el grado» (as `DISCAPACIDAD`) |
| `PNACOE` (+ `_F`/`_M`) | `OtraEnt` (the unspecified state 997 included) | 001–032 other than the own state |
| `PDER_ISTE` | the federal ISSSTE | the ISSSTE, federal or state |
| `VPH_EXCSA` | a toilet | a toilet or a latrine |
| `VPH_AGUADV`, `VPH_C_SERV` | 2020's «sólo en el patio» | 2025's wording «solo» (same codes) |

`VPH_C_SERV` needs no public network despite its description («agua entubada de la red
pública»): requiring `ABA_AGUA_ENTU` = «del servicio público» misses in 2,735 geographies.
The 997 group is 14,882 persons nationally, up to 0.66 points of a municipality.

**Censo 2020 decides whether these are new definitions or the legacy cells' errors.** In the
220 municipalities its sample enumerated completely (`FACTOR` 1 for everyone) the sample is
the census; in the 184 of them whose population in households equals the ITER's, the ITER
is matched to the person (6w):

| indicator | legacy cell exact | INEGI's 2025 definition exact | totals: legacy / INEGI / ITER |
|---|---|---|---|
| `PCLIM_VIS` | 0 / 184 | 168 / 184 | 33,431 / 28,560 / 28,595 |
| `PCLIM_MOT2` | 0 | 181 | 4,085 / 1,760 / 1,765 |
| `PCLIM_*` (all six) | 0–4 | 168–181 | |
| `PCDISC_*` (six) | 175–182 | 179–183 | `_VIS` 10,436 / 10,440 / 10,448 |
| `PNACOE` | 151 | 159 | 15,020 / 14,999 / 15,060 |
| `PDER_ISTE` | **148** | 93 | 6,690 / 7,696 / 6,734 |
| `VPH_EXCSA` (dwellings) | **184** | 3 | 59,553 / 85,764 / 59,553 |

So the limitation and the disability are INEGI's definitions in 2020 too (the legacy
`PCLIM_*` overshoot the ITER by 17–131%), and replace the legacy cells in both editions
(`_CELLS`, `_pcdisc`); the ISSSTE and the sanitary service are 2025 changes (edition
cells); `PNACOE` fits neither rule exactly in 2020, which keeps the legacy cell.

## What changed

- `cpv_aggregates`: `_PERCENT_BASES`, `_count_name`, `_percent_count_names`,
  `_percent_counts`; `load_cpv_estimaciones(counts=False)`: `counts=True` (only with
  `estimador="valor"`: a percentage's standard error or limits are not its count's — the
  bases are not calibration totals below the state, their own standard errors are not 0)
  appends one `Float64` column per percentage, = percentage × base / 100, missing where
  the percentage is (`NA`, `MI`) except 0 where the base is 0.
- `cpv_derived`:
  - new derived **`ENT_PAIS_NAC_INEGI`** (every edition with a birthplace: 1990, 1995, 2000,
    2010–2025; `_ent_pais_cat(…, inegi=)`, the legacy dtype via `_DTYPE_LIKE`): 997 →
    «No especificado»;
  - new summary dummy **`DHSERSAL_ISSSTE_T`** (every edition with health coverage,
    2000–2025; `_summaries`, shared by `_dhsersal`/`_dhsersal_items`);
  - `_CELLS["personas"]`: `PCLIM_*` = «poca» and `LIMITACION` (`_LIMITATIONS`);
  - `_EDITION_CELLS`: `("personas", "2020")` = `_pcdisc` with 2020's «Se desconoce el grado
    de la discapacidad»; `("personas", "2025")` = `_pcdisc` with «… de la dificultad»,
    `PNACOE*` on `ENT_PAIS_NAC_INEGI`, `PNACOP*`, `PDER_ISTE` on `DHSERSAL_ISSSTE_T`,
    `POB0_14*`, `P_6A14*`, `P6A14AN*`; `("viviendas", "2025")` = `VIVPARHAB_C`,
    `VPH_AGUADV`/`VPH_C_SERV` on «solo», `VPH_EXCSA` with the latrine;
  - `_aggregate_indicators("2025")` adds the counts behind the percentages.
- Constraints: EIC 2025 persons 29 → **94**, dwellings 4 → **31**; Censo 2020 keeps 161 +
  46, twelve of them on INEGI's definitions. The new 2025 cells are edition cells, not
  `_CELLS`: the 2005 ITER publishes `P_6A14_F/_M` too, unverified there.
- Docs: `cpv_derived`/`cpv_constraints`/`load_cpv_estimaciones` docstrings, README,
  CLAUDE.md.

## The data

**EIC 2025, all 32 states** (`load_cpv_personas`/`load_cpv_viviendas(2025, derived=True)`,
the actual `cpv_constraints` cells), at all 2,776 geographies of the estimates (the nation
from the 32 states):

- the 40 constraints the estimates publish as counts: Σ `FACTOR` = the count, exactly,
  wherever it is published;
- the 85 counts behind percentages: the share of the base's cells = the percentage within
  0.005 wherever it is published (2,769 geographies; the 7 municipalities whose persons
  have no characteristics publish none).
- The reconstruction `percentage × base / 100` is off our Σ `FACTOR` by INEGI's rounding:
  nationally ≤ 5,268 persons (`P3YM_HLI`, of 126 M aged 3+), by state ≤ 771, by
  municipality 0.08 at the median and 88 at most.
- Unchanged from 6t: `PHOGJEF_F/_M` and `HOGJEF_F/_M` are «No aplica» in those 7
  municipalities, where the sample has persons and heads.

**The new derived columns, every edition × 32 states** (`load_cpv_personas(derived=True)`,
256 loads): no unmapped code. `ENT_PAIS_NAC_INEGI` differs from `ENT_PAIS_NAC_CAT` only
where the legacy rule puts the unspecified state in `OtraEnt`; `DHSERSAL_ISSSTE_T` is
`DHSERSAL_ISSSTE` or `DHSERSAL_ISSSTE_E` in every row.

| edition | unspecified state (`OtraEnt` → «No especificado») | ISSSTE federal / state / either |
|---|---|---|
| CGPV 1990 (unweighted) | 1,325 | — |
| Conteo 1995 (raw: unweighted) | 0 | — |
| CGPV 2000 | 0 | 5,812,626 / — / 5,812,626 |
| Conteo 2005 (unweighted; no birthplace) | — | 599,110 / 93,061 / 690,981 |
| Censo 2010 | 7,053 | 6,366,321 / 994,293 / 7,347,008 |
| EIC 2015 | 252 (= its tabulados' «no especificado», 6e) | 6,461,565 / 1,123,769 / 7,568,987 |
| Censo 2020 | 31,847 | 6,948,054 / 1,390,379 / 8,316,564 |
| EIC 2025 | 14,882 | 6,896,469 / 1,138,856 / 8,011,294 |

## Tests

- `test_estimaciones_counts` (offline, synthetic estimates): the count columns after the
  published ones, `Float64`, a chained base (`PEA` → `PEA_F` → `POCUPADA_F`), the
  `PNC_` spelling, a missing base; `counts=True` with another estimator raises.
- `test_percent_counts_rules` (offline): a missing percentage of a zero base is 0,
  otherwise missing; a percentage without its base raises.
- `test_percent_bases_contract` (offline, the bundled dictionary): every key a percentage
  whose count is not published, every base a published count or a derived one; 85 mapped,
  193 not (3 with a published count, 190 without a cell).
- `test_inegi_birthplace_and_issste` (offline): 997 → «No especificado», same dtype;
  `DHSERSAL_ISSSTE_T` from either item. `test_derive_persons_2010_recodes`: 2010's entity
  999 too.
- `test_cpv_constraints_per_edition`: the 2025 sizes (94/31), every 2025 indicator a
  column of the estimates (published or derived), the 2025 edition cells, INEGI's
  `PCLIM_*`/`PCDISC_*` in 2020 and 2025 (the legacy YAML unchanged), 2020's legacy
  `PNACOE`, `PDER_ISTE`, `VPH_EXCSA`.
- `test_eic2025_constraints_equal_estimates` (real data): now state 01 **and its 11
  municipalities**, all 125 constraints — counts exact, percentages to the rounding.
- `test_disability_by_activity_2020_iter` (real data): Sonora's 5 completely enumerated
  municipalities: the twelve 2020 cells = the ITER to the person; the legacy limitation
  cells count more (29 of 30 cells).
- `test_cpv_derivations_listing`: `ENT_PAIS_NAC_INEGI`, `DHSERSAL_ISSSTE_T`.
- `test_derived_2020_equals_legacy`: `DHSERSAL_ISSSTE_T` = the legacy ISSSTE or state
  ISSSTE (not an unobserved code's all-zero dummy).

Full suite on the Mac: **1835 passed, 1 skipped** (30 min).

## Left out

- **The other 190 percentages** (HANDOFF candidate): their cells are new — 5-year age groups
  (48, by sex), the residence in October 2020 (`PCN_PRES*20`: an `ENT_PAIS_RES_INEGI`
  would follow this unit's birthplace), walls, roofs, cooking place and fuel, waste,
  tenure and deeds, household types, income sources, food security, displacement — and so
  are their bases (households for the `PCN_HOG_*`). Averages and ratios (`PROM_*`, `TGF`,
  `REL_H_M`, `MEDIANA_*`) are not counts.
- `VIVPARHAB` and `OCUPVIVPAR` (the estimates' counts): equal to `TOTHOG` and `POBTOT` in
  the EIC 2025, so they would only repeat a constraint.
- The 2020 `PNACOE`: neither rule reproduces its ITER exactly (151 vs 159 of 184).
- `check_cpv_tabulados.py`'s EIC 2015 migration check still moves the unspecified group
  by hand (`_moved`); `ENT_PAIS_NAC_INEGI` would do it.
