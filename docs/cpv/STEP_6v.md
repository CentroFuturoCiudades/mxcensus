# CPV Unit 6v — the samples' universe: `POBHOG` and the Conteo 2005's households

Done **2026-10-09** (on the Mac; HANDOFF candidates 1 and 2, taken together as one unit at
the user's choice). Gate: a `POBHOG` person total wherever an edition publishes it, and the
Conteo 2005's household indicators counted on its household frame, both checked against
the ITER (the EIC 2025: its estimates) in all 32 states, tests green.

## The gaps

- **The person total.** The legacy person set has one total, `POBTOT: {}` (every person),
  matched to the ITER's `POBTOT`. The samples cover the residents of private dwellings,
  whereas `POBTOT` also counts the population of collective dwellings and people without a
  dwelling. The ITER publishes the samples' universe as `POBHOG` («población en hogares
  censales», 2000–2020; 2005 `P_HOGAR`, renamed by the crosswalk) and the EIC 2025's
  estimates have it too.
- **The Conteo 2005's households.** Its dwelling file has one row per dwelling, but its
  ITER counts households (`TOT_HOG`, `HOGAR_JF`/`HOGAR_JM`). After 6s the dwelling cells
  `TOTHOG`/`HOGJEF_*` counted dwellings, each with its first household's head. The
  household table (`load_cpv_hogares`, `TOTPEHOG`/`TICLAHOG`) had no dwelling class and no
  head.

## The user's choices

- **`POBHOG` beside `POBTOT`** (not instead): a new CPV cell `POBHOG: {}`. The legacy set
  stays frozen, so Censo 2020's CPV set is still the legacy set plus additions.
- **The 2005 household indicators move** to `cpv_constraints("hogares", 2005)`. They leave
  `cpv_constraints("viviendas", 2005)` (23 → 20), since the dwelling frame counts dwellings.
  The dwellings keep their `JEFE_SEXO` column (the first household's head, 6s).

## What changed

- `cpv_derived`:
  - `_CELLS["personas"]["POBHOG"] = {}`. It applies wherever `_aggregate_indicators`
    lists `POBHOG`: the 2000/2005/2010/2020 ITER and the EIC 2025 estimates, not 1990/1995.
  - `TABLES` += `hogares`. Two derivations for 2005 use the dwelling columns' legacy maps
    and dtypes:
    - `CLAVIVP_CAT` from `CLAVIVP` (aliases: 2005 `CLAVIVPA`; `_RECODE` 2005 as for the
      dwellings);
    - `JEFE_SEXO` from the head's `SEXO`.
  - `_HOUSEHOLD_INDICATORS` = `TOTHOG`, `HOGJEF_F`, `HOGJEF_M`.
  - `_cpv_constraints("hogares")` = the dwelling set's cells for those three indicators.
  - `cpv_constraints`:
    - drops the three from `viviendas` in an edition with a household table (2005);
    - raises for `hogares` in any other edition.
- `cpv`:
  - `_DWELLING_FOR_HOUSEHOLDS` (2005: the key parts `ENT`/`MUN`/`CONS_MUN` and `CLAVIVPA`).
  - `_attach_dwellings`: a column-projected read of the dwelling file, keys by
    `_composite_keys`, many-to-one merge; a household without its dwelling raises.
  - `_attach_heads(…, table)` now also serves the household frame. Its keys `(ID_VIV,
    ID_HOG)` give each household its own head: 101 «jefe(a)» or 102 «persona sola».
  - `_load_level` attaches both for `hogares` with `derived=True`, derives, and drops the
    helper columns (`CLAVIVPA`, `SEXO`).
  - `load_cpv_hogares(…, derived=False)`.
- Constraint counts:

  | table | 2000 | 2005 | 2010 | 2020 | 2025 |
  |---|---|---|---|---|---|
  | personas | 62 → 63 | 85 → 86 | 145 → 146 | 159 → 160 | 27 → 28 |
  | viviendas | | 23 → 20 | | | |
  | hogares (new) | | 3 | | | |

  1990/1995 are unchanged (no `POBHOG` in their ITER).

## The data

### `POBHOG`: Σ `FACTOR` of the persons against the ITER, per state

| edition | Σ`FACTOR` / `POBHOG` | Σ`FACTOR` / `POBTOT` | `POBHOG` / `POBTOT` | nation (÷`POBHOG`, ÷`POBTOT`) |
|---|---|---|---|---|
| CGPV 2000 | 1.0007–1.0892 (median 1.0059) | 0.9880–0.9978 (0.9953) | 0.914–0.994 | 1.0171, 0.9952 |
| Censo 2010 | 1.0006–1.0304 (1.0121) | 0.9889–1.0092 (0.9964) | 0.966–0.995 | 1.0122, 0.9966 |
| Censo 2020 | 0.99999–1.00004 (1.000004) | 0.9868–0.9985 (0.9967) | 0.987–0.998 | 1.0000, 0.9960 |
| EIC 2025 | 1 (exact) | 1 (exact) | 1 | 1, 1 |

- **Censo 2020**: the weights add up to `POBHOG` in every state, to a few persons. 2020 is
  the edition where `POBHOG` is the right total and `POBTOT` is not.
- **EIC 2025**: `POBHOG` = `POBTOT` in all 2,776 rows of the estimates, and Σ `FACTOR` =
  `POBHOG` in all **2,478 municipalities**. `test_eic2025_constraints_equal_estimates` now
  checks 28 person cells.
- **CGPV 2000** and **Censo 2010** add up to neither total. They are above `POBHOG` in
  every state and closer to `POBTOT` in most (2000: 19 states, 2010: 27).
  - 2000 sits furthest above `POBHOG` where `POBTOT` exceeds `POBHOG` most: Baja California
    1.089 (`POBHOG`/`POBTOT` 0.914), Colima 1.055 (0.937), México 1.047 (0.952). That fits
    6n's finding that 2000's census `POBTOT` includes a population counted without
    characteristics.
  - 2010's weights exceed `POBTOT` in three states: Hidalgo +0.35%, Tlaxcala +0.92%,
    Zacatecas +0.23%. In state 01 the dwelling weights (293,237) exceed even `TVIVPARHAB`
    (290,777, which includes the dwellings without information). So 2010's weights
    reproduce no ITER total. They equal INEGI's cuestionario ampliado tabulados (3b).
- **Conteo 2005**: unweighted, so a level comparison does not apply.
- `PHOGJEF_F` + `PHOGJEF_M` = `POBHOG` in every ITER state row (2000–2020) and in the EIC
  2025. The 6t cells already added up to the sample's total, and `POBHOG` makes that total
  explicit.

### The Conteo 2005's households (all 32 states)

- The joins:
  - 2,546,879 households in 2,470,678 dwellings (+3.1%);
  - every household has its dwelling and every dwelling at least one household;
  - exactly one head (101/102) per household.
- The dwelling class of the households' dwellings: `CLAVIVPA` 9 «no especificado» = 31,953
  households. The legacy `CLAVIVP_CAT` maps it to «Vivienda», so `TOTHOG` (Vivienda + Otro)
  counts every household. `HOGJEF_F` + `HOGJEF_M` = `TOTHOG` in every state.
- Households per dwelling: the sample has 1.010–1.067. The ITER's `TOT_HOG`/`VIVPARHA` is
  0.901–1.054, under 1 in 11 states because `VIVPARHA` counts dwellings without
  information, which have no household. So the sample's household count is its own, and the
  constraints compare shares.
- The female-headed share of the households against the ITER's `HOGAR_JF`/`TOT_HOG`, in
  points (state 01: 21.19% vs 21.03%):

  | frame | median \|Δ\| | 90th pct. | max \|Δ\| |
  |---|---|---|---|
  | households, each its own head (6v) | 0.087 | 0.285 | 1.072 (Colima) |
  | dwellings, first household's head (6s) | 0.118 | 0.348 | 0.935 (Colima) |

  Counting households brings the share closer in most states. Colima moves 0.14 points
  further: its sample has 2.0% more households than dwellings, the ITER 1.4% fewer.
- The 32-state run took 41 s in all: households and dwellings with `derived=True`, the
  ITER, and the EIC 2025 municipal check.

## Tests

- `tests/test_cpv_derived.py`:
  - `test_cpv_constraints_per_edition`:
    - `POBHOG` = `POBTOT` = `{}` in 2000–2025, absent in 1990/1995 and in the legacy YAML;
    - 2020 = the legacy set + 3;
    - 2000 63, 2005 86;
    - the 2005 dwellings 20 without the household indicators;
    - `cpv_constraints("hogares", 2005)` = the dwelling set's three cells, and every other
      edition raises;
    - the categories check covers `hogares`.
  - `test_cpv_derivations_listing`: `hogares` = `CLAVIVP_CAT`, `JEFE_SEXO` (2005), with the
    dwellings' dtypes.
  - `test_source_codes_match_2020`: the household sources come from the files they are
    borrowed from (`_BORROWED`: the head's `SEXO` from the persons, `CLAVIVP` from the
    dwellings) and are compared with 2020's dwelling items.
  - `test_load_hogares_derived` (offline, a synthetic 2005 mirror through a patched
    `POOCH`):
    - a dwelling's second household gets its own «persona sola» head;
    - a refugio is «Otro»;
    - labels and dtypes; the helper columns dropped;
    - `harmonize=True` gives the same index and values;
    - the crosstab tables build;
    - a household without its dwelling raises.
  - Real (state 01):
    - `test_jefe_sexo_equals_iter[2005]` now on the household frame (`TOTHOG` = every
      household);
    - `test_pobhog_equals_iter` (2020 within 1e-5; 2000/2010 above `POBHOG`, below
      `POBTOT`);
    - `test_crosstab_per_edition[2005]` builds the class × head's-sex table;
    - `test_eic2025_constraints_equal_estimates` checks 28 person cells.
- **Full suite**: 1808 passed, 1 skipped (31 min, the Mac's full mirror; 6u: 1802 + 6 new test cases).

## Left out

- `PHOG_IND`/`HOG_IND` (the population in indigenous households: the head's or partner's
  language). It is a household-level classification the samples could derive, but it is
  another unit.
- 2005's `P_HOG_IND` likewise.
- The household class (`TICLAHOG`) has no ITER indicator in 2005.
