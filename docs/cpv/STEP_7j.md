# CPV Unit 7j — more tabulado checks: the EIC 2015's persons

Done **2026-10-11** (on the Mac, overnight, unattended, as 7g–7i). HANDOFF candidate 3's
«the EIC 2015 person tabulados not yet read»: population (01), fertility (02), child
mortality (03) and unpaid work (09). Gate: every new cell exact in every state, sex and the
nation; tests green. Checks only: no loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **EIC 2015** (`intercensal/2015/tabulados/NN_tema.xls`, «Valor»; the tabulados by state):
  - 01-02 the population by five-year age (the derived `EDAD_QUIN`, 7a) and sex;
  - 01-03 birth registration (`ACTA_NAC`) by sex and age;
  - 02-02 the women of 12 and more by marital status (`SITUA_CONYUGAL_CAT`) and age, and
    their children born alive per woman (`HIJOS_NAC_VIVOS`);
  - 03-01 the children who died (`HIJOS_FALLECIDOS`) as % of those born alive, by the
    mother's age;
  - 09-02 unpaid work (`ACTI_SIN_PAGO1`–`8`: weekly hours per activity) by sex and age,
    09-03 its weekly hours.
  Four workbooks added to `SOURCES`.
- `_age_group` (INEGI's age labels → `EDAD` ranges; 999 = not specified) and `_by_dims` (the
  2015 tabulados with state, sex, a category and an age group as rows).
- The averages and shares compare with a check-wide tolerance (`Check.tolerance` may now hold
  `None` = every state: 10⁻⁴, INEGI publishes 13 decimals); an average of nobody is 0, as
  INEGI writes it (`_value`).
- Left unread: the fertility rates and the infant mortality rate of 2014 (02-03/04, 03-02;
  they need the births of a year), the tabulados by locality size.

## The definitions found

- **The women of 02-02** are those of a specified age who gave their number of children born
  alive (`HIJOS_NAC_VIVOS` below 98: not «omisión del tema», 98, nor not specified, 99):
  513,885 in Aguascalientes, against 521,346 women of 12 and more.
- **Child deaths** (03-01): Σ died ÷ Σ born alive, of the women who gave both.
- **Birth registration** (01-03): registered (1) and not (2) as % of both, registered abroad
  (3) and not specified (9) of all.
- **Unpaid work** (09-02): who do it = an activity with hours (1–998); the activities as % of
  them; who do none = no hours given and not every activity unspecified (a mix of 0 and 999
  is «none»); not specified = all eight 999. The 12+ leave out the unspecified ages.
- **The hours** (09-03): of who do any, all the given hours summed; each activity's, of who
  do it.

## The data

**INEGI's tabulados, every state, sex and the nation** (`TABULADOS_REPORT.md`): **111,978
cells** (82,476 before), none beyond tolerance. The 29,502 new EIC 2015 cells, **every one
exact**:

| check | cells | max \|Δ\| |
|---|---|---|
| 01-02 population by `EDAD_QUIN` × sex (sex T: the sexes are columns) | 1,782 | 0.00 persons |
| 01-03 birth registration by age, by sex | 3,564 | 0.00 persons |
| 02-02a women 12+ by marital status × age | 2,475 | 0.00 persons |
| 02-02b children born alive per woman | 2,475 | < 0.0005 |
| 03-01 children who died, % | 495 | < 0.0005 points |
| 09-02 unpaid work by activity, by sex and age | 10,692 | 0.00 persons |
| 09-03 its weekly hours, by sex and age | 8,019 | < 0.0005 hours |

The derived `EDAD_QUIN` (7a) and `SITUA_CONYUGAL_CAT` (6d) hold in every state.

## Tests

- `test_age_groups_and_dimensions` (offline); `test_weighted_parts_and_averages`: an average
  of nobody is 0.
- `test_state_01_within_tolerance`: 894 more state-01 cells (3,361 in all).
- `test_checks_are_consistent`: 2015's averages and shares carry a tolerance.

## Verification

- The report: every edition, 32 states (~47 min).
- `tests/test_cpv_tabulados.py`: 19 passed; 7j touches only the check script and its tests.
