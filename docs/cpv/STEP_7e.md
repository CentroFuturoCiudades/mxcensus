# CPV Unit 7e — ratio constraints

Done **2026-10-10** (on the Mac). HANDOFF candidate 1, agreed with the user at the
session's start and widened by the user (on a probe of the estimates) to the averages and to
the Censo 2010/2020 ITER. Gate: every ratio constraint equal to its published value, the EIC
2025's at every published geography and the ITER's where the sample is the census; tests
green.

## The idea

A published share whose base is not published, or an average, is no count. But it is
still a **linear** constraint on the weights. If r is the published value of a geography,
N and D are each record's numerator and denominator terms, and `scale` is 100 for a
percentage and 1 for an average, then Σ w·N = r / scale · Σ w·D over its records. This
means Σ w·(N − r / scale · D) = 0, and it needs no count of the base. A term is 0 outside
its side's cells. Inside them it is 1, or the record's value: children, years of
schooling, occupants, rooms.

## The user's choices

- **The unit**: the ratio constraints (HANDOFF candidate 1) over more tabulado checks, the
  locality lineage and the small cleanups.
- **The scope**, after a probe of what the EIC 2025's constraints still left out (35 of its
  349 columns):
  - the EIC 2025's 11 percentages and its averages;
  - the same averages in the census ITERs, for the editions whose sample has the items
    (over «the EIC 2025 only» and «the 11 only»).
- **The API**:
  - a new `cpv_ratio_constraints(table, period)` beside `cpv_constraints`, which is
    unchanged, so `get_tables_dict` keeps working;
  - a consumer `cpv_ratio_terms(frame, ratios)` that gives each record's N and D.
  - Folding the ratios into `cpv_constraints` with a kind marker, or a spec without a
    helper, was turned down.
- **CGPV 2000**: left out (over its two dwelling averages with new machinery, or
  approximately on household rows). Its rules are recorded below for a later unit.

## The spec

`cpv_ratio_constraints(table, period)` maps each indicator to a dict with these keys:

| key | content |
|---|---|
| `numerator` | cells, as `cpv_constraints` writes them; `{}` = every record |
| `numerator_value` | a numeric column, or `None` for 1 |
| `denominator` | cells, as above |
| `denominator_value` | a numeric column, or `None` for 1 |
| `known` | the columns that must be given |
| `scale` | 100 for a percentage, 1 for an average |

- **The cells** are read on the labelled frame with `derived=True`. A value column is a
  numeric column of that frame (`Int64`, with the sentinels missing).
- **`known`**: a record with a `known` column missing counts on neither side (INEGI's
  averages leave out whoever did not say how many). Any other missing value counts 0. That
  is Censo 2010's `PRO_OCUP_C`, below.
- **`cpv_ratio_terms`** returns two `float64` frames on the frame's index, one column per
  indicator. It raises when a cell variable is not categorical or lacks a category the
  cell names, and when a value column is not numeric. Such a frame was loaded with
  `labels=False`, and its sentinel codes would count as values.

## The constraints (each found on the microdata, as 6y found the percentages' bases)

### EIC 2025: 15 person and 2 dwelling constraints

Every one is within the two-decimal rounding of the estimates (≤ 0.005) at every published
geography: the 2,478 municipalities, the 233 localities of 50,000 and more, the 32 state
remainders, the 32 states and the nation, 2,769 in all. `PROM_OCUP` is published at 2,776.

| indicator | numerator | denominator | the alternative it beat |
|---|---|---|---|
| `PCN_POCUP_{CAM,BICI,MET,TROL,TPER,TAXI,MOTO,AUTO,OMED}` | the employed 12+ (`_EMPLOYED_CELLS`) with the mode's dummy (`MED_TRASLADO_TRAB_*`, any of the three options; MET/TROL/TAXI = 7a's `METRO_T`/`BUS_T`/`TAXI_T`, TPER = «Transporte de personal») | the employed who commute: `TIE_TRASLADO_TRAB` a time or «No es posible determinarlo» (`_COMMUTERS`) = those who name a mode (`MED_TRASLADO_TRAB1` given, «No especificado» included) | the base without the unspecified mode: up to 3.46 points off, at 2,085 geographies |
| `PCN_P3NHLI_CLI` | 3+ with `HLENGUA` «No» and `ELENGUA` «Sí» | 3+ with `HLENGUA` «No» | the unspecified speakers in the base: up to 13.84 points off, at 778 |
| `PCN_HF` | Σ `HIJOS_FALLECIDOS`, women 12+ | Σ `HIJOS_NAC_VIVOS`, women 12+; `known` both | keeping the women whose deaths are unspecified in the denominator: ≤ 0.0075 at 6 |
| `PROM_HNV` | Σ `HIJOS_NAC_VIVOS`, women 12+ | women 12+; `known` `HIJOS_NAC_VIVOS` (98 and 99 out) | every woman: ≤ 0.045 at 242; leaving out only 98: ≤ 0.020 at 16 |
| `GRAPROES`, `_F`, `_M` | Σ `ESCOACUM`, 15+ (by sex) | 15+; `known` `ESCOACUM` | the unspecified in the base: ≤ 0.60 at ~2,100 |
| `PRO_OCUP_C` (dwellings) | Σ `NUMPERS`, «Vivienda» (`_VIVIENDA`) | Σ `TOTCUART`; `known` `TOTCUART` | the occupants of the dwellings without rooms counted (Censo 2010's rule): ≤ 0.20 at 34 |
| `PROM_OCUP` (dwellings) | Σ `NUMPERS`, «Vivienda» | the dwellings «Vivienda» (= `VIVPARHAB_C`) | every class: ≤ 0.038 at 367 |

`PROM_OCUP` is not implied by the counts. The occupants of «Vivienda» dwellings are no
published count: `POBTOT` = `OCUPVIVPAR` also holds the «Otro» classes' households.

### Censo 2010 and 2020 (the ITER, `load_cpv_iter`): 4 person and 2 dwelling constraints each

The ITER is the full census and the constraints apply to the sample. Where the sample *is*
the census, the definition shows exactly: these are the municipalities whose sampled persons
all have `FACTOR` 1 (2010: 767, 2020: 220) and whose population in households equals the
ITER's `POBHOG` (364, 184).

| indicator | definition | exact in (2010 / 2020) |
|---|---|---|
| `PROM_HNV` | as the EIC 2025's (2010's item `NUMHIJ`, 98/99 out) | 346 / 135 municipalities with the women 12+ equal too |
| `GRAPROES`, `_F`, `_M` | as the EIC 2025's | 343–348 / 139–144 with the age group equal too |
| `PRO_OCUP_C` | 2020: Σ `NUMPERS` / Σ `TOTCUART`, `known` `TOTCUART`. 2010: the occupants of **every** dwelling over the rooms of those that gave them (no `known`) | 364 / 184 |
| `PROM_OCUP` | Σ `NUMPERS` over every dwelling (cells `{}`) / the dwellings | 364 / 184 |

- **The age condition.** Without it, `GRAPROES` and `PROM_HNV` miss in up to 44
  municipalities, mostly in Oaxaca. There the sample's ages differ from the census's even
  where the population is the same: in 20-228, 510 persons aged 15+ against the ITER's 534.
  These misses come from the data, not from the definition.
- **The «Otro» classes** (locales, móviles, refugios) have no rooms recorded in 2010, 2020
  and 2025. So for 2020/2025, «every dwelling with rooms» is the same as «"Vivienda" with
  rooms».
- **Censo 2010's `PRO_OCUP_C`**: requiring known rooms on both sides misses in 204 of the
  364 (by ≤ 0.08). Taking the «Vivienda» occupants only misses in 13.
- **2020/2025**: counting the occupants without rooms misses in 34 of 2020's 184
  municipalities and at 34 EIC 2025 geographies.

**The samples' band** is the sample against the ITER, state by state:

| indicator | 2010 median / max | 2020 median / max |
|---|---|---|
| `GRAPROES` | 0.047 / 0.264 years | 0.053 / 0.179 |
| `GRAPROES_M` | 0.039 / 0.343 (Baja California Sur) | 0.056 / 0.186 |
| `PROM_HNV` | 0.038 / 0.091 | 0.013 / 0.051 |
| `PRO_OCUP_C` | 0.013 / 0.061 | 0.008 / 0.041 |
| `PROM_OCUP` | 0.034 / 0.154 | 0.018 / 0.071 |

## Left out

- **The medians** (`MEDIANA_*`) and **`TGF`**: not linear in the weights.
- **Ratios of published counts** (`REL_H_M`, `INDICE_ENV*`, `RAZON_DEP_*`): implied by the
  count constraints. The ITERs' `REL_H_M` too.
- **CGPV 2000** (the user's choice). In its 207 municipalities with `FACTOR` 1 for everyone,
  172 have the population and the 15+ equal to the ITER's. There:
  - **`PRO_OVP` (`PROM_OCUP`)** is exact **once per dwelling**: the first household's row
    (`NUMHOG` 1, with the dwelling's `NUMPERS`) over the dwellings. 3.1% of the dwelling
    rows belong to a dwelling with several households. On household rows it is off by up
    to 0.43, at 127 municipalities.
  - **`PRO_OCVP` (`PRO_OCUP_C`)** is exact once per dwelling with 2000's own rooms:
    `TOTCUART` − 1 for an exclusive kitchen nobody sleeps in (`COCINA` 1 and `COCDOR` 4).
    `TOTCUART` as it is misses by up to 1.6, without every kitchen by up to 1.25, and on
    household rows by up to 0.18.
  - **`GRADOESCO` (`GRAPROES`)** reproduces nowhere. The mean of `ESCOACUM` over the 15+
    who gave it is off by 0.28 at the median (up to 1.24), at every one of the 172, in
    both directions (mean +0.05).
    - Leaving out the persons without `NIVACAD`, or counting normal and técnica after
      primaria as 6 + grade, changes nothing.
    - So the ITER's education answers are processed otherwise than the sample's, not
      defined otherwise.
    - Across states the sample sits 0.27 years off at the median (0.55 at most).
  - Both dwelling averages need a «first household» cell on the 2000 dwelling frame (and
    a rooms value without the kitchen). That cell would also make 2000's dwelling *counts*
    count dwellings, not households. This is a HANDOFF candidate.
- **The Conteo 2005** (`PROM_HNV`, `GRAPROES`, `PRO_C_VP`, `PRO_VIPA` in its ITER): its
  sample has no schooling in years and no rooms or occupants on the dwellings. Its
  children born alive are a categorical item (`NHIJNAVI`).
- **CGPV 1990/1995** (`PROM_CUA`, `PROM_VIV`, `PRO_O_VP`): not probed.

## What changed

- **`cpv_derived`**:
  - `_ratio`, `_RATIOS` (per table and edition: `_prom_hnv(item)`, `_graproes()`,
    `_WOMEN_12PLUS`, `_COMMUTERS`, `_MODES_TRAB`), `_numeric_columns`;
  - **`cpv_ratio_constraints(table, period)`** keeps the ratios the edition publishes
    (`_aggregate_indicators`) whose cells and value columns exist in the labelled frame,
    and raises on `hogares` outside 2005, as `cpv_constraints` does;
  - **`cpv_ratio_terms(df, ratios)`**;
  - the module and `cpv_constraints` docstrings.
- **`cpv_aggregates.load_cpv_estimaciones`**: the docstring points the 11 percentages
  without a count to the ratio constraints.
- **`__init__`**: exports `cpv_ratio_constraints` and `cpv_ratio_terms`.
- **Tests** (`tests/test_cpv_derived.py`, `tests/test_cpv.py`):
  - `test_cpv_ratio_constraints_per_edition`: the sizes per edition, the spec, the
    published names, cells and values that exist;
  - `test_cpv_ratio_terms`: the terms, `known` against another missing value, raw frames
    raise;
  - `test_eic2025_ratio_constraints_equal_estimates`: state 01 and its municipalities,
    both tables;
  - `test_census_ratio_constraints_equal_iter`: Sonora, 2010's 31 and 2020's 5 exact
    municipalities;
  - `test_percent_bases_contract`: the 11 without a count are ratio constraints;
  - `test_cpv_exports`.
- **Docs**: README (constraints), CLAUDE.md, PLAN, HANDOFF.

## Verification

- A 32-state sweep through the API: `load_cpv_personas`/`load_cpv_viviendas(derived=True)`
  → `cpv_ratio_terms` → Σ `FACTOR` × term per geography.
  - EIC 2025: all 17 at every published geography (max 0.005).
  - Censo 2010/2020: all six exact in the municipalities above. The state band is in the
    table.
  - It ran in 6 parallel processes on the Mac, about 15 minutes.
- Full suite on the Mac: **1900 passed, 1 skipped** (31 min).
