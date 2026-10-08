# CPV Unit 6g — `PSIND_LIM`'s exact rule

Done **2026-10-08** (on the Mac, the same session as 6f). Gate: the rule reproduces every
published EIC 2025 estimate of `PSIND_LIM`, a derived flag carries it, the CPV constraint
uses it, tests green.

## The rule

`PSIND_LIM` is «Población sin discapacidad, limitación, problema o condición mental». The
legacy cells (6b) require all six difficulty items to be «No tiene dificultad» (1) and
`DIS_MENTAL` = «No» (6). That leaves out everyone with one unspecified answer, and gives
1,262,355 for state 01 against the published 1,263,545. 6b's closest rule gave 1,263,337.

INEGI's rule, found by fitting on state 01 and confirmed everywhere:

> no difficulty of any degree (2, 3, 4, 8) in the six activities, and no mental condition
> (`DIS_MENTAL` ≠ 5), **leaving out the persons whose seven answers are all unspecified**
> (six items and `DIS_MENTAL` = 9).

One unspecified answer among «no» answers counts as none. Equivalently:

```
POBTOT = PCON_DISC + PCON_LIMI + (mental condition only) + PSIND_LIM + (all seven unspecified)
```

State 01: 1,534,416 = 74,620 + 180,240 + 8,912 + 1,263,545 + 7,099.

| rule tried (state 01) | Σ FACTOR | vs published |
|---|---|---|
| legacy: all six = 1 and `DIS_MENTAL` = 6 | 1,262,355 | −1,190 |
| all six = 1 and `DIS_MENTAL` ≠ 5 | 1,262,557 | −988 |
| not disabled, not limited, `DIS_MENTAL` = 6 (6b's closest) | 1,263,337 | −208 |
| not disabled, not limited, `DIS_MENTAL` ≠ 5 | 1,270,644 | +7,099 |
| **not disabled, not limited, `DIS_MENTAL` ≠ 5, not all seven = 9** | **1,263,545** | **0** |

## Verification (EIC 2025)

- **32 states**: exact in every state (Σ `FACTOR` rounded = the estimate). The legacy cells
  are 367–9,521 lower per state.
- **Nation**: 108,214,451 = the national estimate (legacy cells: 108,119,335, −95,116).
- **Municipalities**: exact in all 2,471 municipalities with a published estimate (the
  others are suppressed, `NA`).
- Through the loader (`load_cpv_personas(2025, state=s, derived=True)`, 32 states):
  `SIN_DISC_LIM` = Sí sums to the estimate in every state; no missing value.

**Censo 2020** (no exact check: its ITER is the full count, the microdata the sample):
the sample gives 105,500,366 under this rule and 105,358,104 under the legacy cells. The
ITER has 104,815,785. The sample is in private dwellings only, and the census has more
unspecified answers. `SIN_DISC_LIM` nationally, 2020: Sí 105,500,366, No 19,876,105, No
especificado 139,083. 2025: 108,214,451 / 21,583,387 / 595,551.

## What changed

- **`SIN_DISC_LIM`** (new derived column, 2020 + 2025, `_sin_disc_lim`, dtype `_YES_NO`):
  - **Sí**: no difficulty of any degree and no mental condition;
  - **No**: a difficulty (2/3/4/8) or a mental condition (5);
  - **No especificado**: all seven answers unspecified.

  A code outside these lists leaves the row missing, so `derive` raises. Its sources are
  the six `DIS_*` items and `DIS_MENTAL` (2020 = 2025 codes: 5 Sí, 6 No, 9 NE).
- **The CPV constraint** `PSIND_LIM` → `{SIN_DISC_LIM: [Sí]}` (`_CELLS`, as 6c did for
  `PCON_DISC`/`PCON_LIMI`). It applies in 2020 and 2025; 2010 has no `PSIND_LIM`. The legacy
  `constraints_personas.yaml` is unchanged (frozen path).
- The EIC 2025 constraint test now pins **all 25** person indicators exactly (was 24 plus
  `PSIND_LIM` asserted to differ).

Columns per edition: 2025 personas 58 → **59**, 2020 60 → **61**; 2015/2010 unchanged (no
`DIS_*` items).

## Tests (`tests/test_cpv_derived.py`)

- `test_sin_disc_lim_inegi_rule` (offline): all «no» → Sí; one 9 among «no» with
  `DIS_MENTAL` 9 → Sí; all six 9 with `DIS_MENTAL` 6 → Sí; all seven 9 → NE; `DIS_MENTAL`
  5 → No; any difficulty → No (also with 9s); an unknown `DIS_MENTAL` code raises.
- The synthetic 2025 persons carry `DIS_MENTAL`. The listing has `SIN_DISC_LIM` in 2020 and
  2025. `cpv_constraints` gives `PSIND_LIM` on it in 2020 and 2025.
- `test_eic2025_constraints_equal_estimates` (real): 25 person indicators exact (state 01).
- **Full suite**: 1651 passed, 1 skipped (29 min, the Mac's full mirror).
