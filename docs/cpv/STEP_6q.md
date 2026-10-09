# CPV Unit 6q — more EIC 2015 and Censo 2010 tabulado checks

Done **2026-10-09** (night, on the Mac; unattended, see `STEP_6m.md`). Gate: the 2015/2010
derived columns 6d–6f recoded (coverage, commute, marital status, education, limitation,
co-residence) checked against INEGI's tabulados in every state (2010: the nation), tests
green.

## Why

6d recoded the EIC 2015 and Censo 2010 items into the 2020 code space and gave 2015 its own
commute dummies, but only migration, occupation, sector and financing had been checked
against INEGI's tabulados (6e, 6f; `TABULADOS_REPORT.md` since 6m). The EIC 2015 publishes
state tabulados for the rest; the Censo 2010 ampliado publishes limitation and parental
co-residence by locality size, so only their national rows apply.

## The checks (`scripts/check_cpv_tabulados.py`)

| edition | tabulado | cells | derived columns |
|---|---|---|---|
| 2015 | `06_educacion` 11 | the 15+ by level: no schooling (preschool with it), primaria, secundaria incomplete (and of unspecified grade) / complete, media superior and superior, NE | `EDUC` (the legacy one: the EIC 2015 tabulados, like it, count técnica after primaria in primaria — 6k) |
| 2015 | `07_servicios_de_salud` 02 | the population by affiliation and institution: IMSS, ISSSTE (federal or state), PEMEX/Defensa/Marina, Seguro Popular, private, other, not affiliated, NE | `DHSERSAL_*` (6d's recode: 2015's 1 = Seguro Popular → `SALUD_PUBLICA`) |
| 2015 | `10_movilidad_cotidiana` 03 / 06 | students aged 3+ and employed aged 12+ who travel, by mode (several per person) | 2015's own `MED_TRASLADO_ESC_*`/`_TRAB_*` (seven modes) |
| 2015 | `11_situacion_conyugal` 02 | the 12+: single, married or in union, separated/divorced/widowed, NE | `SITUA_CONYUGAL_CAT` |
| 2010 | `06_01A` (nation) | the population with / without a limitation in activity, NE | `LIM_ACTIVIDAD` |
| 2010 | `12_01A` (nation) | the population by parents in the dwelling: both, only the father, only the mother, neither, NE | `MADRE_EN_VIVIENDA`, `PADRE_EN_VIVIENDA` |

## A fix: Censo 2010's «row not given» is not specified

The first full run put 2010's parental co-residence 3.1 million persons off nationally:
INEGI's «no especificado» held 4,126,899 persons, the derived flags 1,011,272, and «both»,
«only the father», «only the mother» were over by exactly the difference. 6e had read a
pointer row given as 99 («row not given») with a blank code as «lives here, row not given»
(its age profile is that of the numbered rows: `STEP_6e.md`). INEGI's tabulado counts it
**not specified**: with that reading all five national cells (both, only the father, only
the mother, neither, NE) equal the tabulado to the person, men and women too. So
`_pointer_2010` now maps «99 + blank code» to 99 (not specified) for the mother, the father
and — the same questionnaire design, no tabulado to check — the partner
(`IDENT_PAREJA_CAT`); 2010's co-residence NE share goes from 0.9% to 3.7% (2015: 2.2%). No
constraint uses these columns.

## Results (all 32 states, both sexes, the nation)

**Every new cell is exact.** EIC 2015 (3,960 new cells, 32 states × 3 sexes + the nation):
education (`EDUC`), affiliation by institution, both commute tables and marital status,
|Δ| ≤ 0.51 of a person (the national rounding of six-decimal percentages). Censo 2010
(national, both sexes): limitation and — after the fix — parental co-residence, exact.

The report now has **19,698 cells** (2000 5,148; 2010 2,010; 2015 7,293; 2020 5,247), none
beyond tolerance. With 6m–6q, every derived column of the 2010–2020 samples that INEGI
tabulates by state is checked against its tabulados.

## Tests

- `tests/test_cpv_tabulados.py`: the real state-01 test covers the 2015 checks (120 more
  cells, all exact; the 2010 ones are national).
- `tests/test_cpv_derived.py`: the 2010 synthetic pointers — a row given as 99 with a blank
  code is «No especificado» for the father and the partner.
- **Full suite**: 1772 passed, 1 skipped (30 min, the Mac's full mirror).
