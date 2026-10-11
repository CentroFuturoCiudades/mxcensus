# CPV Unit 7p — more tabulado checks: Censo 2020's disability and migration causes, Censo 2010's leftovers

Done **2026-10-11** (on the Mac, with the user). HANDOFF candidate 3's first item, the user's
choice over the 0.12.0 release, the tabulados by locality size and the small cleanups:
Censo 2020's 06_discapacidad and 04-12/14/15, with Censo 2010's by-state tabulados 7m left.
Gate: every new cell exact (1 person) in every state, sex and the nation; tests green.
Checks only: no loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Censo 2020** (`cpv2020_a_eum_06_discapacidad.xlsx`, added to `SOURCES`; «Valor»):
  - 06-02 (by state and sex) and 06-04 (by state and age group): the population; who have a
    disability, limitation or mental condition; of them the disabled, the limited and those
    with a mental condition, each by cause; who have none; not specified (23 cells);
  - 06-06: the disabled or limited by activity (all, each of the six) and kind (either,
    disability, limitation), each by cause;
  - 04-12 (`cpv2020_a_eum_04_migracion.xlsx`): the return migrants by the duration of their
    migration and its average in months (04-12m, unit «average»); 04-14 by the cause of the
    return; 04-15 every international migrant by the cause of the emigration, counted in the
    state they left.
- **Censo 2010** (eight `NN_NNA_ESTATAL.xls` added to `SOURCES`; «Parámetro»):
  - 05_01A/02A: the 3+ by self-identification (`PERETN`) and language, the non-speakers by
    understanding one (`CLENGUA`) — published for 14 states one by one and «Resto de las
    entidades»;
  - 07_02A/05A: the 18+ with higher education and the 15+ with técnica after secundaria by
    field of study (`NOMCAR_C`);
  - 08_06A/07A: the employed by occupational division × sector and × hours worked;
  - 12_02A: the population by the parents' residence in the dwelling, by age; 12_04A by
    kinship line, by age.
- **Readers**: `_state_of` reads Censo 2010's plain state names (07_02A has no codes;
  `_STATE_NAMES_2010`, code order; no other workbook in `SOURCES` holds such a name) and «Resto de las entidades» as the pseudo-state
  `_REST` = 98, which `ByOrigin` keeps apart (05_01A/02A count the other 18 states' records
  there: `_selected_states_2010`; such checks need all 32 states). `_by_dims` reads a row
  INEGI leaves out as nobody (zeros): Censo 2020's 06-04 has no «No especificado» age in
  five states.
- 7n's `_self_identification_2020`/`_understands_2020` became `_self_identification(item)`
  and `_understands(item, codes)` (2010's `PERETN`/`CLENGUA` too).

## INEGI's rules, found on the data

- **Disability** (06-02/04/06; exact on the first try): 6c's `DISCAPACIDAD` (much difficulty,
  cannot, or the degree unknown — 8 — in an activity), `LIMITACION` (some difficulty, only
  without a disability: 6y's rule, also per activity), `SIN_DISC_LIM` (6g) for «none» and
  «not specified», a mental condition `DIS_MENTAL` 5. A cause counts every disabled (limited)
  person who names it for any of their difficulties of the kind (the shares sum to more than
  100); a mental condition's «otra causa» holds the accident and old age (INEGI's footnote).
- **Return migrants** (04-12): `MPAIRES` 3, whether in the dwelling or not, counted in the
  dwelling's state; the duration = the return's year × 12 + month − the emigration's; under a
  year 0–11 months (≤ 6, 7–11), 1 to under 3 years 12–35, 3 to 5 years 36+; any date
  unspecified (9999, 99) = not specified and left out of the average.
- **Causes** (04-14/15): the questionnaire's precoded answers by their four-digit code —
  work 0101/0102 (looking for a job, a change or offer of job), family 0301/0401 (joining the
  family, marriage), study 0501, deported 0801 (the return; the emigration's is «otra
  causa»); 9999 not specified; every other code «otra causa» (INEGI's footnotes). 04-15
  counts every international migrant (emigrant or return) in the state they left.
- **Fields of study** (07_02A/05A): `NOMCAR_C`'s first digit (`TC_CARRERA_2010`: 1–8 the
  fields, 9 not specified); higher education = `NIVACAD` 08–12 (técnica after preparatoria,
  normal de licenciatura, licenciatura, maestría, doctorado), 18+; técnica after secundaria =
  `NIVACAD` 07, 15+.
- **Hours by division** (08_07A): `HORTRA` 1–16, 17–24 … 49–56, 57+; 0 = «no trabajó la
  semana pasada»; 999 not specified; the divisions and sectors as 08_02A/03A (6f).
- **Kinship lines** (12_04A; found on the tabulado, every state then exact): head `PARENT`
  01, spouse 02, ascendants 06 (parents), 07 (parents-in-law) and of «otro parentesco» (08)
  `OTROPARE_C` 602 step-parents, 606–608 grand-, great- and great-great-grandparents, **612
  uncles and aunts, 620 godparents**; descendants 03–05 (children, grandchildren,
  children-in-law) and 610/611 great-(great-)grandchildren, **613 nephews and nieces, 621
  godchildren**; **«Familiar» (623) not specified** with 99; every other code of 08 — or
  none — collateral (siblings, half- and step-siblings, cousins, co-parents-in-law,
  siblings-in-law, compadres); not related 09.

## The data

**INEGI's tabulados, every state, sex and the nation** (`TABULADOS_REPORT.md`): **192,214
cells** (148,783 before), none beyond tolerance. The 43,431 new cells, **every one exact**
(counts; the largest |Δ| 0.47 of a person, the nation's six-decimal percentages of 125
million; the average months abroad within 5 × 10⁻⁷):

| check | cells | sexes |
|---|---|---|
| 2010 05_01A self-identification by language (14 states, the rest, the nation) | 768 | T, H, M |
| 2010 05_02A understanding an indigenous language | 192 | T, H, M |
| 2010 07_02A the 18+ with higher education by field | 990 | T, H, M |
| 2010 07_05A the 15+ with técnica after secundaria by field | 330 | T |
| 2010 08_06A the employed by division × sector | 7,623 | T, H, M |
| 2010 08_07A the employed by division × hours worked | 10,890 | T, H, M |
| 2010 12_02A parents in the dwelling by age | 4,752 | T, H, M |
| 2010 12_04A kinship lines by age | 4,752 | T, H, M |
| 2020 06-02 disability, limitation, mental condition, causes | 2,277 | T, H, M |
| 2020 06-04 the same by age | 5,313 | T |
| 2020 06-06 disability or limitation by activity and cause | 4,851 | T |
| 2020 04-12 return migrants by duration | 231 | T |
| 2020 04-12m their average months abroad | 33 | T |
| 2020 04-14 return migrants by cause | 231 | T |
| 2020 04-15 international migrants by the cause of emigrating, state left | 198 | T |

The first 32-state run missed one record (07_02A, Veracruz: a woman with a maestría whose
career is 800, «carreras técnicas básicas», weight 16 — INEGI's «not specified»; every other
800 is a técnica after primaria, `NIVACAD` 06); with 800 as not specified every cell is
exact. The 2010 and 2020 sections of the report were regenerated by one 2010 + 2020 run
(95,997 cells) and spliced in: every row of the earlier sections unchanged, only 7p's added.
The 2000 and 2015 sections are untouched (no workbook of theirs holds a plain state name or
«Resto de las entidades», so the reader change cannot reach them).

## Tests

- `test_state_of`: the plain names, «Resto de las entidades».
- `test_part_by_origin`: 98 kept apart.
- `test_age_groups_and_dimensions`: a missing row reads as zeros.
- New `test_disability_causes_2020`, `test_migration_duration_and_causes_2020`,
  `test_kinship_fields_and_selected_states_2010`.
- `test_checks_are_consistent`: the by-origin person checks 05_01A/02A, 2020's average.
- `test_state_01_within_tolerance`: 1,281 more state-01 cells (2010 889, 2020 392); the
  by-origin set holds 05_01A, 05_02A and 04-15.

## Verification

- The 7p checks alone over the 32 states (43,431 cells, 13 min), then one 2010 + 2020 run of
  every check of the two editions (95,997 cells, 0 beyond tolerance) spliced into the report.
- `tests/test_cpv_tabulados.py`: 26 passed (state 01's real-data check included); 7p touches
  only the check script and its tests (the last full suite: `wsl` at 87cebf6, 1920 passed,
  1 skipped).

## Left out

- Censo 2010's 07_03A (07_02A's counts by field and sex, transposed: not compared, as
  CGPV 2000's MI13) and its tabulados by locality size (07_01A/04A, 08_04A/05A, 12_03A/05A).
- Censo 2020's 06-01/03/05 and 04-11/13 (the same by locality size).
