# CPV Unit 7w — more tabulado checks: every Censo 2020 tabulado

Done **2026-10-12** (on the Mac, with the user). HANDOFF candidate 3's «Censo 2020» item, the
user's choice over Censo 2010's leftovers, a 2015 locality edition and the small cleanups.
Gate: every new cell exact in every state, sex, locality size and the nation; tests green.
Checks only: no loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Every Censo 2020 tabulado is now read, every row.** The probe listed the 30 sheets of the
  cached workbooks no check read; INEGI's file-listing API (`idBiinegi` 3001, `tipodocto` 5)
  lists 15 ampliado workbooks, three of which `SOURCES` lacked: `13_hogares_censales` and
  `15_alimentacion` (never fetched) and `14_ingresos_mon_dif_trabajo` (cached, never
  listed) — added (15 workbooks).
- **20 checks by state** (`_person_checks_2020_w`):
  - 07-02 the 15+ with a técnica or comercial career of media superior by field (`NIVACAD`,
    `NOMCAR_C`);
  - the employed: 08-02/04 position (`SITTRA`) by division and by sector, 08-10 sector by
    division, 08-14/16 hours worked (`HORTRA`) by sector and by position, 08-20/22 the income
    in minimum wages (`INGTRMEN_SM`, 7c) by sector and by position, 08-24/26 the salaried's
    benefits by division and by sector, 08-28 the 12+ by activity (`CONACT`) and age;
  - 09-02 the use of health services (`SERSALUD`) by sex and age;
  - 10-04 the students' commute time (`TIE_TRASLADO_ESCU`) by age, 10-10 the employed's
    (`TIE_TRASLADO_TRAB`) by position;
  - 13-02 the population in households by kinship line (`PARENTESCO`), 13-04/06 the 0–17 by
    their parents' residence and survival (`IDENT_MADRE`, `IDENT_PADRE`);
  - 14-02 the households by other incomes (`INGR_OTROS`, 6z) and source by household size;
  - 15-02 the households by a lack of food for want of money (`ALIMENTACION`) by the head's
    sex, 15-04 by each of the adults' five food situations.
- **Seven checks read every row**: 08-12 (hours) and 08-18 (income) by division, 10-02 (place
  of school) and 10-06 (commute mode to school) by age, 10-08 (place of work) by sector, 10-12
  (commute mode to work) by position and 11-02 (the partner's residence) by union read only
  their breakdown's «Total» row; they now read every row (`_place`, `_commute` take `rows`;
  `_partner` its unions). 08-12 is on the raw `HORTRA` (`HORTRA_CAT` cannot split the
  tabulado's 32 hours, so it read «up to 40» as one cell).
- **By locality size**: the 20 new checks join `_SIZE_TWINS` (their by-size sheets — 07-01,
  08-01 … 08-27, 09-01, 10-03, 10-09, 13-01/03/05, 14-01, 15-01/03 — have the twins' layout);
  the seven widened twins (08-11, 08-17, 10-01, 10-05, 10-07, 10-11, 11-01) read every row too.
- **Shared cell builders** (the EIC 2015's and Censo 2020's tabulados have the same layouts and,
  for these items, the same codes): `_cross(universe, rows, cells)` (rows × cells, each a
  function of a frame and a group), the row/cell functions `_division_rows`, `_sectors`,
  `_position_rows` (`_positions(p, item)`: 2015 `SITUACION_TRAB`, 2020 `SITTRA`), `_age_rows`,
  `_hours_2020`, `_incomes`, `_school_times`, `_work_times`, and `_benefits(rows, item)`;
  7v's `_benefits_2015`, `_school_time_2015`, `_work_time_2015`, `_occupation` and
  `_income_sm` are now written with them (the same masks). `_hours` (`HORTRA_CAT`, the old
  08-12's only reader) is gone.

## The definitions found

- **Técnica of media superior** (07-01/02; footnote: «al menos un grado aprobado en carrera
  técnica o comercial de educación media superior»): the 15+ with `NIVACAD` 05 (bachillerato
  tecnológico), 07 (técnica after secundaria) or 09 (normal with primaria or secundaria
  terminada — 1,942 of Aguascalientes's 1,979 in Educación); without 09 the total is short by
  1,979 there. The field is `NOMCAR_C`'s first two digits (catalog CARRERA: the CMPE's ten
  campos amplios 01–10), 9999 not specified.
- **Hours** (08-11–16): «hasta 32» = 1–32, then 33–40, 41–48, 49–56, more than 56 (`HORTRA`
  57–140), «no trabajó la semana pasada» = 0 hours (= `CONACT` 20, had a job but did not
  work), 999 not specified.
- **Activity** (08-27/28): the 12+ (unspecified ages out); the PEA `CONACT` 10–30 (as % of the
  12+), the employed 10–20 and the unemployed 30 (as % of the PEA), the not active 40–80,
  not specified 99.
- **Benefits** (08-23–26): the EIC 2015's rule (7v) and codes: with = some item «yes», without
  = all seven «no», not specified = no «yes» and some 9; the salaried `SITTRA` 1–3.
- **Health services** (09-01/02): every person, «Total» holding the unspecified ages; users
  `SERSALUD` 01–09 (ISSSTE = 02 + 03, IMSS-BIENESTAR 06, pharmacy 08, other 09), non-users
  10, not specified 99.
- **Kinship lines** (13-01/02), found on the tabulado in every state and sex (≤ 0.04 of a
  person): ascendants — parents, step-parents, grand- and great-grandparents, uncles and
  aunts, parents-in-law, godparents (401, 402, 406, 407, 412, 416, 421); descendants —
  grandchildren, step-grandchildren, the grandchildren's spouses, great-grandchildren,
  nephews and nieces and theirs, children-in-law, godchildren (408–411, 413, 414, 418, 422);
  collaterals — siblings, half- and step-siblings, cousins, the children's parents-in-law,
  siblings-in-law, concuños, compadres (403–405, 415, 417, 419, 420, 423); «otro parentesco»
  = «otros familiares» (424); the unrelated, tutors, domestic workers and their families and
  guests none (5xx, 6xx, 701).
- **The parents of the 0–17** (13-03–06): not specified when either pointer is 99, «no
  sabe» when either is 98 and neither 99 (the other order moves 223 children in
  Aguascalientes); else a row 01–54 lives here, 96 elsewhere, 97 died (survival: alive = a
  row or 96).
- **Households** (13–15): every dwelling row is a household, the classes 07–09 (787 of
  Aguascalientes's 387,762, weighted) included; the food items are asked of all (none blank), so each situation's
  base is every household.

### INEGI's one inconsistent row

10-02, Tabasco, women aged 6–11: INEGI publishes «en la misma entidad» as **100.0%** beside 2
«no especificado» (0.001573%), so its row sums to 100.0016%; the men's and both sexes' rows,
and the nation's, agree with ours exactly. «Same entity» and «same municipality» (a share of
it) are 2.0 and 1.97 persons above ours: the check's tolerance for state 27 is 2 persons
(7c's precedent of a per-state tolerance with its note).

## The data

**INEGI's tabulados, every state, sex and the nation** (`TABULADOS_REPORT.md`): **529,879
cells** (376,570 before), none beyond tolerance. The 7w checks hold **159,510 cells**
(6,201 before: the seven widened checks' «Total» rows), **every one exact** (≤ 0.62 of a
person, the nation's six-decimal percentages) but Tabasco's cell above:

| check | cells | max \|Δ\| |
|---|---|---|
| 07-02 técnica of media superior by field | 1,188 | 0.01 persons |
| 08-02/04/10 position by division and sector, sector by division | 18,315 | 0.25 |
| 08-12/14/16 hours by division, sector, position | 19,008 | 0.25 |
| 08-18/20/22 income in minimum wages by division, sector, position | 21,384 | 0.24 |
| 08-24/26 benefits by division and sector | 19,602 | 0.20 |
| 08-28 activity by age | 4,158 | 0.23 |
| 09-02 use of health services by age | 8,316 | 0.62 |
| 10-02/08 place of school by age, of work by sector | 10,395 | 0.21 (Tabasco 2.0) |
| 10-04/10 commute times by age and position | 13,068 | 0.23 |
| 10-06/12 commute modes by age and position | 13,860 | 0.22 |
| 11-02 the partner's residence by union | 1,188 | 0.19 |
| 13-02 kinship lines; 13-04/06 the parents of the 0–17 | 2,376 | 0.56 |
| 14-02 other incomes by household size; 15-02/04 food access | 2,112 | 0.16 |
| 27 checks by locality size (07-01 … 15-03) | 24,540 | 0.62 |

The derived columns they read hold in every state: `OCUPACION_C_COARSE`,
`ACTIVIDADES_C_COARSE` (6f), `INGTRMEN_SM` (7c), `LUGAR_ASI`/`LUGAR_TRAB` (7b), the commute
dummies, `SITUA_CONYUGAL_CAT`/`IDENT_PAREJA_CAT`, `INGR_OTROS` (6z), `JEFE_SEXO`.

## Tests

- `test_census2020_rules_7w` (offline): the kinship lines, the parents' precedence (99 over 98
  over the rest; 96 alive), the hours' bins (0, 32 | 33, 999), the técnica universe and fields,
  `_cross`'s order, `_position_names`, the partner by union, the food access by the head's sex.
- `test_state_01_within_tolerance`: 3,931 more state-01 cells (2,758 new; the widened checks
  159 → 1,332), its income and place filters on the 2020 rows by division, age and sector.

## Verification

- The new and widened checks over 32 states, the nation and every size through a scratch
  harness on cached frames (9 min): every cell exact but Tabasco's.
- The full report: one run per edition (four processes, every state; 26 min on the Mac, the
  EIC 2015 the longest), the sections spliced as `report()` writes them (the header and
  footer of the four runs identical): 529,879 cells, 0 beyond tolerance. The 2000, 2010 and
  2015 sections are **byte-identical** to the committed report, and so is every 2020 row but
  the 7w checks' (the shared cell builders and the generalized `_place`/`_income_sm`/
  `_occupation` change no other cell).
- `tests/test_cpv_tabulados.py`: 30 passed. The full suite was not run: 7w touches only the
  check script and its tests (as 7v).

## Left out

- Nothing of Censo 2020's ampliado: every sheet of its 15 workbooks, every row (its
  cuestionario básico tabulados `cpv2020_b_*` count the census, not the sample).
- The 2010 and 2015 checks that still read only their breakdown's «Total» row: 2010
  `08_10A`, `08_15A`; 2015 06-11, 07-02, 08-11, 10-01, 10-03, 10-04, 10-06, 11-02 (7v's
  «every sheet» read these sheets' totals only).
- Censo 2010's unread tabulados (HANDOFF candidate 3).
