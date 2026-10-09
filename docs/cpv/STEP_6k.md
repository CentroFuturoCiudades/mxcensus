# CPV Unit 6k — `P15PRI_CO` without técnica after primaria (`EDUC_INEGI`)

Done **2026-10-08** (on the Mac; 6j's open question). Gate: INEGI's rule settled for every
edition that publishes `P15PRI_CO`, a derived column carries it, the CPV constraints use
it, the legacy path unchanged, tests green.

User decisions (this session): 6k = this question, then 6l = the dictionary fixes; the fix
is a **finer `EDUC` column** (not a yes/no flag), so the education crosstabs keep their
shape.

## INEGI's rule, per edition

The legacy `EDUC` counts «estudios técnicos o comerciales con primaria terminada» (2020's
`NIVACAD` 6) as «Primaria_com», so the legacy cell `P15PRI_CO` = `EDUC` «Primaria_com»
includes them. INEGI's primaria completa does not, in all four editions whose ITER publishes
it:

| edition | ITER indicator | evidence |
|---|---|---|
| 1990 | `PRIM_COM` | 6j: the 10% extract overshoots by 10.7% with them, +0.6% without |
| 2000 | `P15_CPRIMA` | its dictionary: técnica «con antecedente de primaria» is `P15_POSPRI` (posprimaria), and `P15_CONSEC` groups it with secundaria |
| 2010 | `P15PRI_CO` | the ITER = the básico tabulado `07_08B` «Primaria, 6 grados» (15+) **exactly in all 32 states**; the tabulado's técnica column (468,752 persons aged 15+) is apart |
| 2020 | `P15PRI_CO` | the ITER = the básico tabulado `cpv2020_b_eum_07_educacion` sheet 12 «Primaria, 6 grados» (15+) **exactly in all 32 states** (12,325,433 nationally); the técnica column (352,797 aged 15+) is apart |

The 2010/2020 dictionaries say only «máxima escolaridad 6 grados aprobados en primaria», and
the samples cannot tell: the cuestionario ampliado sits about 1.5% (relative) below the ITER
without them and about 1.5% above with them, nationally and across states. The básico
tabulados settle it.

**The exception is the EIC 2015**: its tabulados (`06_educacion.xls`, footnote 1 of «6
grados») count técnica after primaria *in* primaria completa, as the legacy `EDUC` does.
The EIC 2015 has no constraints, so this only matters for comparisons with its tabulados.

Where técnica after primaria goes in the ITER: in no education indicator (not in
`P15SEC_*`, not in `P18YM_PB`), only in `P_15YMAS` (2010/2020); 1990/2000 count it as
posprimaria (`INS_PPRIM`, `P15_POSPRI`, which have no legacy cell).

**Consequence for the frozen legacy path**: the legacy 2020 `constraints_personas.yaml` cells
`P15PRI_CO`/`P15PRI_COF`/`P15PRI_COM` overshoot INEGI's counts by técnica after primaria
(2.9% of `P15PRI_CO` nationally, 3.8% in Aguascalientes). The legacy files, loaders and YAML
stay as they are (`tests/test_census_legacy.py`); the CPV constraints are corrected.

## What changed (`cpv_derived.py`)

- **`EDUC_INEGI`** (new derived column, every edition 1990–2025, beside `EDUC`): the legacy
  `EDUC` with 2020's level 6 (técnica after primaria, any grade or unspecified grade) as
  «Técnica_primaria». Ordered categories (`_EDUC_INEGI`): the legacy ones with
  «Técnica_primaria» after «Secundaria_com», INEGI's tabulado order (between básica and
  media superior). `_educ` returns both columns; an unknown code leaves both missing, so
  `derive` raises.
- Each edition's técnica after primaria is 2020's 6 already: 2000 `NIVACAD` 6 + `ANTESC` 1,
  2005 `NIVANTES` 61, 1995 `P5_5` 1 with requisite `P5_7` 1 on a primaria, 2010–2025
  `NIVACAD` 6. **1990** needed a rule: `TEC_PRIM` > 0 on a complete primaria (`NIV_EST` 1,
  `ANO_APRO` 6) → level 6 with grade `TEC_PRIM` (1–3); `EDUC` is unchanged («Primaria_com»).
  In the 1990 extract all 104,884 persons with `TEC_PRIM` at the primaria level have six
  grades; the other 72,047 with `TEC_PRIM` > 0 went further (secundaria or more) and keep
  their level.
- **The CPV constraints** read `EDUC_INEGI` wherever the legacy cells read `EDUC`
  (`_CELL_VARS = {**DHSERSAL_RENAMES, "EDUC": "EDUC_INEGI"}`): 18 indicators (`P15YM_SE`,
  `P15PRI_IN`, `P15PRI_CO`, `P15SEC_IN`, `P15SEC_CO`, `P18YM_PB`, each with `_F`/`_M`). Only
  «Primaria_com» changes meaning; the others have the same members. The crosstab tables keep
  their shape (`EDAD_CAT` × `EDUC_INEGI`, × `SEXO`), and «Técnica_primaria» is a category no
  cell constrains. Constraint counts per edition are unchanged.

Derived person columns: 1990 9 → **10**, 1995 8 → 9, 2000 17 → 18, 2005 13 → 14, 2010 25 →
26, 2015 42 → 43, 2020 61 → 62, 2025 59 → 60.

## Verification

**32-state sweep** (`load_cpv_personas(period, state=s, derived=True, harmonize=True)`; each
education constraint's share of the population against the ITER's share of `POBTOT`, in
points; «legacy» = the old `P15PRI_CO` cell with técnica):

| edition | `P15PRI_CO` max \|Δ\| | mean Δ | legacy max \|Δ\| | legacy mean Δ |
|---|---|---|---|---|
| 1990 (10% extract) | **0.29** | **0.08** | 3.03 | 1.22 |
| 2000 (sample, `FACTOR`) | **0.48** | **−0.03** | 1.36 | 0.45 |
| 2010 (ampliado) | **0.44** | **−0.10** | 1.29 | 0.30 |
| 2020 (ampliado) | 0.89 | −0.15 | 0.89 | 0.09 |

The other 1990 education cells: `P15YM_SE` 0.25 / 0.00, `P15PRI_IN` 0.51 / 0.06 (max / mean).
2000: `P15YM_SE` 2.31 / −0.88 (Chiapas, as 6i), `P15PRI_IN` 1.11 / 0.43, `P15SEC_IN` 0.67 /
0.16, `P15SEC_CO` 0.59 / −0.16. 2010: every education cell within 0.80 points (mean
≤ 0.20) except `P18YM_PB` (2.50 / 0.59, unchanged by 6k); `P15PRI_COF`/`P15PRI_COM` 0.33 /
0.00 and 0.33 / −0.09. 2020: the sample cannot tell the two rules apart (−0.15 against
+0.09 on average, 0.89 at worst either way); the básico tabulado's exact identity is what
decides 2020. Its other education cells
are within 1.31 points (mean ≤ 0.15). No unmapped code in any state (the sweep derives every
column).

Técnica after primaria (aged 15+, weighted sample): 2000 468,282, 2010 448,849, 2020
311,671 (the básico tabulados: 468,752 in 2010, 352,797 in 2020).

## Tests (`tests/test_cpv_derived.py`)

- `test_educ_inegi` (offline): the categories (legacy + «Técnica_primaria», ordered); 2020
  codes: primaria 6 → «Primaria_com» in both, level 6 with grades 1/4/NE → «Técnica_primaria»
  in `EDUC_INEGI` only, the other levels equal; an unknown pair is missing in both; the
  Conteo 1995's technical career after primaria.
- The synthetic 1990, 2000 and 2005 persons assert `EDUC_INEGI` (técnica after primaria →
  «Técnica_primaria»); the listing has `EDUC_INEGI` in every edition; `TEC_PRIM` joins the
  1990 own-code items of `test_source_codes_match_2020`.
- `test_cpv_constraints_per_edition`: the 18 education cells = the legacy ones with
  `EDUC_INEGI` for `EDUC`; no cell reads `EDUC` in any edition.
- `test_1990_1995_constraints_equal_iter` (real): 1990's `P15PRI_CO` now agrees without the
  test's own técnica correction.
- **Full suite**: 1748 passed, 1 skipped (29.5 min, the Mac's full mirror).

## Follow-ups

- The frozen legacy `constraints_personas.yaml` still counts técnica in `P15PRI_CO`
  (documented in the README); a user who wants INEGI's count uses `cpv_constraints(…, 2020)`.
