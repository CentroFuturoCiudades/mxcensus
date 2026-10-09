# CPV Unit 6r — CGPV 2000 hours and education tabulados; 2000's «had a job» at 0 hours

Done **2026-10-09** (early morning, on the Mac; unattended, see `STEP_6m.md`). Gate: three
more CGPV 2000 sample tabulados in the checks (hours of the employed, education of the 12+
and 18+), every state within tolerance, tests green.

## The checks (`scripts/check_cpv_tabulados.py`)

| tabulado | cells | derived column |
|---|---|---|
| `C2KEM07` | the employed by hours worked: none or up to 40 (its «no trabajó», ≤8, 9–16, 17–24, 25–32, 33–40), 41–48, 49–56, more than 56 (57–64, more than 64), NE | `HORTRA_CAT` |
| `C2KED08` | the 12+ by level: sin instrucción, primaria incompleta (or grade NE), completa, secundaria, **técnica after primaria** (its own column), media superior and superior, NE | `EDUC_INEGI` (6k's «Técnica_primaria») |
| `C2KED11` | the 18+ without media superior, with media superior or superior, NE | `EDUC_INEGI` |

ED08 is the most direct check of 6k: INEGI's 2000 sample tabulado keeps técnica after
primaria apart, and `EDUC_INEGI`'s «Técnica_primaria» reproduces it (states 01, 07, 09:
median 0.004 points, Chiapas at most 0.09).

## A fix: 2000's «had a job but did not work» worked 0 hours

EM07 first put «up to 40» 0.4–0.8 points under the tabulado in states 01, 07 and 09, and the longer
bins over. INEGI's «no trabajó» column is 1.38% of the employed in Aguascalientes; `HORTRA`
0 is 0.33%. The difference is the persons who had a job but did not work in the reference
week (`CONACT` 20): in the 2000 sample they carry hours (48, 40, 60…: likely their usual
ones), while in 2010, 2020 and 2025 every such person has `HORTRA` 0 (and 6j counts
1990's at 0). `HORTRA_CAT` 2000 now reads `CONACT` too (`_hortra_2000`: `CONACT` 20 → 0
hours), and EM07 matches like the other 2000 tabulados (state 01, 07, 09: median 0.004,
max 0.08 points). The 2000 hours constraints (6o) move closer to the ITER: `P48_HTR`
median gap 0.71 → 0.56 points, `P41_48HTR` 0.26 → 0.23.

## Results

All 32 states, both sexes and the nation (percentage points):

| tabulado | cells | median \|Δ\| | 95th pct. | max \|Δ\| |
|---|---|---|---|---|
| EM07 hours | 495 | 0.003 | 0.015 | 0.080 (Chiapas) |
| ED08 education of the 12+ | 693 | 0.003 | 0.009 | 0.091 (Chiapas) |
| ED11 education of the 18+ | 297 | 0.004 | 0.012 | 0.083 (Chiapas) |

The report now has **21,183 cells** (2000 6,633; 2010 2,010; 2015 7,293; 2020 5,247), none
beyond tolerance.

## Tests

- `tests/test_cpv_derived.py`: a synthetic 2000 person with `CONACT` 20 and 48 reported
  hours → `HORTRA_CAT` «0-5».
- `tests/test_cpv_tabulados.py`: the state-01 test covers the three checks (45 more cells).
- **Full suite**: 1772 passed, 1 skipped (31 min, the Mac's full mirror).
