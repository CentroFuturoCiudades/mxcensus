# CPV Unit 6c — Review of the pending decisions; follow-ups

Done **2026-10-08** (with the user, on the Mac). The user went over every pending decision
of units 3b–6b. Three changed something and were implemented in this session; the rest
were confirmed. Gate: tests (full suite green, §Tests).

## Decisions

| decision | outcome |
|---|---|
| The legacy `load_census` crashed in states 08/15/16 (`impute_collective`: `if diff == 0` on `pd.NA`) | **fixed** in the frozen `aggregate.py` (one NA guard) |
| CGPV 2000's dwelling table has one row per household | **kept** as published (`(ID_VIV, ID_HOG)`; dwellings = `NUMHOG == "1"`) |
| Conteo 1995 has three weights and no `FACTOR` | **`harmonize=True` adds `FACTOR`** = `FAC_POB` (persons) / `FAC_VIV` (emigrants) |
| `load_cpv_iter`/`load_cpv_ageb`: one frame with `NIVEL` | **kept** |
| The legacy `DIS_CON`/`DIS_LIMI` are not INEGI's definitions (6b finding) | **new `DISCAPACIDAD`/`LIMITACION`** with INEGI's rules; the CPV constraints use them |
| The 17 other overnight decisions (3b–6a; listed in 6b's `HANDOFF.md`) | **confirmed** as implemented |
| Merge `cpv-integration` into `main`, tag v0.7.0 | after this unit (user's choice) |

## The legacy crash (`aggregate.impute_collective`)

- **The bug.** In 08, 15 and 16 a reserved (`*`) coarse total makes the collective
  difference `pd.NA`, and `if diff == 0` raises `TypeError: boolean value of NA is
  ambiguous`. So `load_census(state=8|15|16)` had never loaded under current pandas.
- **The fix.** `if pd.notna(diff) and diff == 0` for `POBCOL` and `TOTCOL`, the rule the
  port `cpv_aggregates._impute_collective` already followed: a missing difference
  imputes nothing.
- **Effect.** No output changes where the function worked. `tests/test_census_legacy.py`
  pins the frozen path, and `test_census_2020_equals_legacy` now compares the unpatched
  legacy chain with `load_cpv_census(2020)`: **equal in all 32 states** (8 min 22 s on the
  Mac). `test_impute_collective_na_safe` checks that the legacy loop equals the port on
  a frame with a reserved total.

## `FACTOR` for the Conteo 1995 (`cpv._harmonize`)

- **The rule.** `_FACTOR_FROM = {"personas": "FAC_POB", "migrantes": "FAC_VIV"}`. When a
  harmonized frame has no `FACTOR` but has its table's estimator, the copy is inserted
  just before that estimator and made numeric.
- **Unchanged:**
  - every other edition (they have their own `FACTOR`);
  - raw loads (`harmonize=False`, `load_cpv`);
  - the three originals.
- The step is idempotent, and the docstrings say to weight 1995's health and disability
  items with `FAC_PROM`.
- **Effect.** Stacked editions share one weight column: Σ `FACTOR` for state 01 is
  858,971 (1995), 940,778 (2000) and 1,421,198 (2020).

## INEGI's disability definitions (`cpv_derived`)

**Two new derived columns**, 2020 and 2025, categories Sí / No / No especificado
(`_dis_inegi`, dtypes in `_DTYPES`):
- `DISCAPACIDAD` = Sí when an activity is done with much difficulty or not at all
  (3, 4), **or with a difficulty of unknown degree (8)**; else No especificado when an
  item is 9; else No.
- `LIMITACION` = Sí when an activity is done with some difficulty (2) **and the person has
  no disability**; No when disabled; else No especificado when an item is 9; else No.

These rules were fitted to the EIC 2025 estimates. The FD labels code 8 «Se desconoce el
grado de la discapacidad/dificultad». The legacy `DIS_CON`/`DIS_LIMI` are unchanged:
- they treat 8 as «No especificado»;
- they count the disabled among the limited.

**Constraints.** The CPV set (`_CELLS`) puts `PCON_DISC` on `DISCAPACIDAD` = Sí and
`PCON_LIMI` on `LIMITACION` = Sí (the legacy YAML keeps `DIS_CON`/`DIS_LIMI`).

**Verification:**
- **EIC 2025.** Both match the published estimate exactly in all 32 states (§Tests).
  `PSIND_LIM` stays on the legacy cells, since INEGI's exact rule is unknown; it is the
  only constraint that differs (−95,116 nationally).
- **Censo 2020**, state 01, against the census ITER. The census counts everyone, so the
  sample can only come close:

  | indicator | ITER | INEGI rule | legacy flag |
  |---|---|---|---|
  | `PCON_DISC` | 71,294 | 71,768 | 71,768 (no code 8 there) |
  | `PCON_LIMI` | 165,482 | 160,082 (−3%) | 193,452 (+17%) |

## Tests

- **`tests/test_cpv_aggregates.py`:**
  - `test_census_2020_equals_legacy` now runs without the monkeypatch, and the
    "legacy raises" branch is gone;
  - `test_impute_collective_na_safe`: legacy = port, with a reserved total.
- **`tests/test_cpv.py`:** `test_harmonize_1995_factor` (offline: copy, position,
  idempotence, migrantes, an edition with its own `FACTOR`) and
  `test_harmonize_1995_factor_real`.
- **`tests/test_cpv_derived.py`** (74):
  - `test_disability_flags_inegi_vs_legacy` (codes 8, 2 + 3, 2 + 9);
  - the 2025 synthetic rows;
  - `PCON_DISC`/`PCON_LIMI` in `cpv_constraints`;
  - the EIC 2025 estimates test now expects 24 exact person indicators (only `PSIND_LIM`
    differs);
  - the legacy-equality test skips the two new flags among the "extra" columns.
- **The 2025 check over all 32 states** (a script): Σ `FACTOR` over the cells equals the
  state estimate for all 24 person and 3 dwelling indicators in every state; only
  `PSIND_LIM` differs (−95,116 nationally).
- **Full suite**: 1586 passed, 1 skipped (29 min, the Mac's full mirror).
