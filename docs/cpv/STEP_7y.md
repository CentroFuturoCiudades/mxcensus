# CPV Unit 7y — more tabulado checks: Censo 2020's last cells; the coverage probe

Done **2026-10-12** (on the Mac, with the user). HANDOFF candidate 3's «Censo 2020's last
cells», the user's choice over a 2015 locality edition, the locality-lineage leftovers and the
small cleanups. Gate: every new cell exact in every state, sex, locality size and the nation;
every published value of the Censo 2010, EIC 2015 and Censo 2020 tabulados read; tests green.
Checks only: no loader, derivation or dictionary changed.

Before starting, the session found 7x **uncommitted** (its HANDOFF said committed): after
`tests/test_cpv_tabulados.py` passed (31), it was committed with the user's go-ahead
(a79d336).

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **The unspecified age** (01-02 population by five-year age and sex, 01-04 birth
  registration by age; their by-size twins 01-01, 01-03): `_QUIN_2020` and
  `_REGISTRATION_AGES_2020` end with «No especificado» (`EDAD` 999; `EDAD_QUIN` «No
  especificado»). A place without persons of unspecified age publishes no row; `_by_dims`
  reads it as zeros, and ours are zeros too (01-02: 5 places; 01-04: by sex, 5–8).
- **The fields of higher education** (07-04 and its twin 07-03): the 18+ with educación
  superior (`EDUC_INEGI_DET` «Superior» or «Posgrado», 6w) by the CMPE field — `NOMCAR_C`'s
  first two digits 01–10, 9999 not specified —, by sex. 07-04 read its total only.
  `_fields_2020` now serves 07-02's técnica (7w) and 07-04.
- **The employed** (08-06 by division, 08-08 by sector; twins 08-05, 08-07): the employed
  are a cell before their divisions and sectors (their counts were read through the
  percentages only), as 7x did for 2010's 08_04A/05A. `_occupation`, `_sector` and
  `_divisions` build on `_division_rows`/`_sectors`.
- **The use of health services by affiliation and institution** (09-04 and its twin 09-03):
  each of the eleven affiliation rows (all; affiliated and each institution — a person counts
  once per institution, ISSSTE federal or state —; not affiliated; not specified) by
  `SERSALUD` (users and their institution, non-users, not specified: 09-02's cells, now
  `_users_2020`). 09-04 read each row's population only; it now reads through
  `_by_affiliation` (7v/7x's reader). `_affiliation_published` is gone.
- **The coverage probe** (`coverage`, `--coverage`): 7x's probe was a scratch script, lost
  with its session; it is now in the script. Each published value of an edition's estimator
  rows (`_ESTIMATOR`: 2010 «Parámetro», 2015/2020 «Valor») is read as a float that remembers
  its cell (`_Traced`, `_CellText`), through every check's own reader (`_num` swapped for
  the call, restored after): a value is read when a compared, non-missing cell is computed
  from it — so a total read only into the counts of its percentages is read (a wrong total
  puts every such count off). `--coverage` prints the unread values per workbook and sheet
  (exit 1 if any); it needs the tabulados only, not the mirror (~10 s for the three
  editions).

## The data

| check (by state; by size) | cells before | cells now | max \|Δ\| (persons) |
|---|---|---|---|
| 01-02; 01-01 (age × sex, the unspecified age) | 1,683; 306 | 1,782; 324 | 0.000 |
| 01-04; 01-03 (registration × age) | 4,752; 864 | 5,346; 972 | 0.61 |
| 07-04; 07-03 (superior × field) | 99; 18 | 1,188; 216 | 0.08 |
| 08-06; 08-05 (employed × division) | 990; 180 | 1,089; 198 | 0.17 |
| 08-08; 08-07 (employed × sector) | 594; 108 | 693; 126 | 0.21 |
| 09-04; 09-03 (use × affiliation) | 363; 66 | 4,356; 792 | 0.62 |
| **total** | **10,023** | **17,082** | |

**7,059 new cells, every one exact** (the |Δ| is the rounding of six-decimal percentages);
135 of them are the zeros of a place without an unspecified-age row. Nationally 5,533
persons are of unspecified age (2,177 men, 3,356 women; 1,310 with registration not
specified), 19,510,014 persons 18+ have educación superior (2,422,486 in education, 4,516,245
in administration and business…), and 122,652,974 use health services. The report:
**765,536 cells** (758,477 before), 0 beyond tolerance; only its 2020 section changed.

**The coverage probe**: 163,845 published values (2010), 330,333 (2015) and 207,951 (2020)
— before 7y 6,690 of 2020's unread (exactly the HANDOFF's list) —, now **none unread** in any
of the three editions. CGPV 2000's tabulados (no estimator rows) are outside the probe.

## The definitions found

None new: 09-02's use of services holds per affiliation row (the users 01–09, ISSSTE 02/03,
non-users 10, not specified 99), 07-02's fields hold for the superior (the field of the
person's highest level, the posgrado's career included), and the unspecified age is `EDAD`
999 in every 2020 tabulado that publishes it.

## Tests

- `test_census2020_last_cells_7y` (offline): the unspecified age last, a missing row read as
  zeros, the superior's fields, the use per affiliation (a person in two institutions counts
  in both; 132 cells), 09-04's reader on the 2020 layout, the employed first.
- `test_coverage_traces_values` (offline): a total read only into counts is read, a value no
  compared cell comes from (or only a missing one) is not, `_num` restored; `_Traced`'s
  arithmetic.
- `test_every_published_value_is_read` (real tabulados): none unread in 2010, 2015 and 2020;
  without 09-04, its 4,356 values unread.
- `test_state_01_within_tolerance`: **20,933** cells (+181: 01-02 +3, 01-04 +18, 07-04 +33,
  08-06/08 +3 each, 09-04 +121), every one within tolerance.
- `tests/test_cpv_tabulados.py`: **34 passed**. The full suite was not run: 7y touches only the
  check script and its tests (as 7v–7x).

## Verification

- The twelve widened checks over 32 states, the nation and every size through a scratch
  harness (`run` on a subset of `CHECKS`, ~4 min): 17,082 cells, every one exact.
- The full 2020 report run (one process), its section spliced into `TABULADOS_REPORT.md` as
  `report()` writes it (the header and footer identical; 2000/2010/2015 untouched).

## Left out

- Nothing of the Censo 2010, EIC 2015 and Censo 2020 tabulados: every published value enters
  a compared cell (`--coverage`).
- The 2010/2015 infant mortality (7o: not reproducible from the sample).
- CGPV 2000's tabulados are checked as before (shares and blocks; the probe does not read
  their layout).
