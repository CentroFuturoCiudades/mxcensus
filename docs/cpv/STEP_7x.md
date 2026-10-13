# CPV Unit 7x — more tabulado checks: every Censo 2010 tabulado, every cell

Done **2026-10-12** (on the Mac, with the user). HANDOFF candidate 3's «Censo 2010» item and
its «the rows the 2010/2015 checks skip», the user's choice over the small cleanups, the
locality-lineage leftovers and a 2015 locality edition. Gate: every new cell exact in every
state, sex, locality size and the nation; tests green. Checks only: no loader, derivation or
dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Every Censo 2010 tabulado is read, every cell.** INEGI's file-listing API (`idBiinegi`
  487, `tipodocto` 5) lists 80 cuestionario-ampliado workbooks; `SOURCES` held 51. The 29
  others are added — 28 workbooks and **10_01A, which INEGI publishes as a PDF only** (the
  listing gives its `.xls` 0 bytes; the server answers it with an HTML page).
- **21 checks by state** (`_person_checks_2010_x`):
  - 06_04A limitation and its causes by age, 06_06A the limited by type of limitation
    (`DISCAPk`) and its cause (`CAUSADISk`);
  - 07_03A higher education by field with the sexes in columns (07_02A's counts,
    `_by_sex_columns`);
  - the employed: 08_08A/09A hours by sector and by position, 08_11A/12A the income in
    minimum wages by sector and by position, 08_14A/16A the place of work by division and by
    position, 08_17A/18A the salaried's benefits (`PRESLAB1`–6) by division and by sector,
    08_20A the 12+ by activity and five-year age;
  - 08_21A/22A (national, by sex): the employed by SCIAN sector (20 sectors and the
    unspecified) and locality size, in counts and in shares;
  - 09_03A the use of health services by age, 09_05A by affiliation and institution;
  - 12_06A the 12+ by other incomes (`AYUPROGOB` … `AYUOTRFTE`) and household size, 12_07A
    the households by a lack of food (`COMIO1VEZ`, `NOCOMI1D`, `SINCOMER`);
  - the `migrantes`: 04_08A by destination (`MPDESOTR_C`) and the state left, 04_10A/10Am
    the return migrants by the duration of their migration and its average.
- **11 checks by locality size**: 04_07A, 06_03A, 06_05A, 08_19A, 12_05A through
  `_SIZE_TWINS`; and, through twins built for them (`_size_twins_2010_x`), 04_09A/09Am (by sex,
  unlike 04_10A), 08_01A (position), 09_01A (five-year ages), 10_01A/10_01As (the PDF).
- **Every row of the checks that read a «Total» or a category's count**: 08_02A/03A (the
  positions of each division and sector; their divisions' and sectors' employed before),
  08_10A (income by division), 08_15A (place of work by sector), 07_01A (by level of higher
  education; its «Total» level before), 08_04A/05A (the employed too; their shares before).
- **The international migrants whose state left is not specified**: `_estimates` reads the
  «No especificado» row of a «Entidad federativa expulsora» (04_05A misspells it «expusora»:
  `_LEFT`) as state 99 — the `ByOrigin` code of `MLUGORI_C` 999, the only code outside 1–32
  in both editions. 2010's 04_04A–06A and 04_08A and **Censo 2020's 04-04/06/08/10/15**
  compare it now (+41 cells in 2020).
- **The EIC 2015's remaining rows and cells** (the coverage probe below found more than the
  HANDOFF listed): every row of 04-02 (abroad: the United States and another country apart,
  `ENT_PAIS_NAC` 221), 06-11 (by sex and age), 07-02 (by sex and age), 07-06 (the
  institutions under the «Total» affiliation: INEGI repeats the «Afiliada» rows), 08-02 (by
  sex and age), 08-06/07 (each division's and sector's positions), 08-11 (income by
  division), 10-01/03 (place and mode to school by age), 10-04/06 (place of work by sector,
  mode by position), 11-02 (marital status by sex and age), 12-05a/b (every head's sex; the
  population by household type too); their by-size twins follow (04-01, 07-01, 08-01, 11-01,
  12-04a/b; 08-08/09 with the employed). New: **06-11d** and **11-02d** — the cells the
  derived `EDUC` and `SITUA_CONYUGAL_CAT` merge, on the raw items —, **06-11m** (the average
  grades approved, `ESCOACUM`), **14-02s** (the occupants by sex and dwelling class, from the
  persons; 14-01s by size).
- **Readers and helpers**: `_unions_pdf` (10_01A's text via poppler's `pdftotext -layout`,
  `_dict_fd.pdf_text`, recast as 10_02A's layout; `_workbook` dispatches on `.pdf`, `fetch`
  accepts a PDF), `_unions(pick)`, `_scian_published`, `_by_affiliation` (07-06's reader,
  generalized), `_destination_of(item)`, `_activity(groups)`, `_use_2010`, `_benefits(…,
  benefits=)`, `_yes_no_items`, `_with_dwelling` (`_frame` gives the EIC 2015's persons their
  dwelling's `TIPOHOG` and `CLAVIVP`, which the person file lacks; `ID_VIV` as numbers).
  `_long`, `_total_row`, `_income_sm` and `_income_sm_published` went unused and are gone.

## The definitions found

- **Destination** (04_07A/08A): the United States = `MPDESOTR_C` 221 (the return migrants'
  too), not specified 999, every other code another country — Censo 2020's rule (7n) on
  2010's item; exact nationally (994,869 to the United States).
- **Return migrants' duration** (04_09A/10A): Censo 2020's rule (7p) — the months between
  the emigration and the return, dates not specified apart, in the state they live in.
- **Limitation by type** (06_05A/06A): a type's limited = its `DISCAPk` given, the cause its
  `CAUSADISk`; «Total» = `LIM_ACTIVIDAD` with any limitation's cause (06_02A's).
- **Higher education's levels** (07_01A): técnica after preparatoria `NIVACAD` 08;
  profesional 09–10 (normal de licenciatura, licenciatura); maestría o doctorado 11–12.
- **Benefits** (08_17A/18A): the EIC 2015's rule (7v) on 2010's six items: with = some
  «yes», without = all six «no», not specified = no «yes» and some 9.
- **Activity** (08_19A/20A): Censo 2020's codes (7w) hold for 2010: the PEA `CONACT` 10–30
  (employed 10–20, unemployed 30), not active 40–80, not specified 99.
- **SCIAN sectors** (08_21A/22A): `ACTIVIDADES_C_COARSE`'s two digits (31–33, 48–49 joined);
  08_21A publishes its «Total» row in counts and each sector as a **share of every size's
  employed**, 08_22A each sector's employed and its sizes as shares of it.
- **Other incomes** (12_05A/06A): Censo 2010 asks them of each person 12+ (not of the
  household): some source «yes»; none = all five «no»; else not specified; the household
  size = the persons of the dwelling (= `NUMPERS`).
- **Food access** (12_07A): the census households are **every dwelling**, the locales,
  móviles and refugios (`CLAVIVP` 5–7, which the dwelling tabulados leave out) included —
  they answer the items (213 households in Aguascalientes); «Total»: some situation «yes»,
  all three «no», else not specified.
- **EIC 2015** (06-11d/m, 11-02d): media superior = `NIVACAD` 4, 5, 7, 9, superior 8, 10–14
  (`EDUC_INEGI_DET`'s); secundaria's grades `ESCOLARI` 1–2, 3, 99; the average grades approved
  over the 15+ whose `ESCOACUM` is given (99 out); marital status `SITUA_CONYUGAL` 6, 5, 1, 2,
  3, 4, 9 in the tabulado's order.

## The data

**INEGI's tabulados, every state, sex, locality size and the nation**
(`TABULADOS_REPORT.md`): **758,477 cells** (529,879 before), none beyond tolerance. The
**228,598** new cells are **every one exact** but the State of México's documented income
gap (7c: 525 persons in 08_10A, now also 08_11A/12A — the same records) and 10_01A's shares,
published with two decimals (within 0.005 points):

| edition | checks | cells | max \|Δ\| |
|---|---|---|---|
| 2010: 21 new by state (06, 07_03A, 08_08A … 08_22A, 09, 12, 04_08A/10A) | 21 | 77,496 | 0.63 persons (State of México 525) |
| 2010: 11 new by size (10_01A from the PDF: 90 counts, 270 shares) | 11 | 3,810 | 0.63 (10_01As 0.005 points) |
| 2010: widened (08_02A/03A/10A/15A, 07_01A, 08_04A/05A, the unspecified origin) | 10 | 22,688 | 0.00 (State of México 525) |
| 2015: widened (04-02, 06-11, 07-02, 07-06, 08-02/06/07/11, 10-01/03/04/06, 11-02, 12-05a/b) + twins | 23 | 90,633 | 0.58 |
| 2015: new (06-11d/m, 11-02d, 14-02s) + twins | 6 | 33,930 (the average: 1,386) | 0.25 (the average to 1e-4) |
| 2020: the unspecified state left (04-04/06/08/10/15) | — | 41 | 0.00 |

The report's 2000 section is **byte-identical**; 2010, 2015 and 2020 change only in the rows
above. A coverage probe (every Censo 2010 and EIC 2015 workbook: the published values of the
«Parámetro»/«Valor» rows against the cells the checks read) now finds no unread cell.

## Tests

- `test_census2010_rules_7x` (offline): the unspecified state left (both spellings; a
  state of residence is not one), the destination, the limited by type and cause, the 12+'s
  other incomes by household size, the food access of every dwelling, 08_21A/22A's layouts,
  10_01A's PDF lines (`pdf_text` monkeypatched) and its shares.
- `test_eic2015_rows_7x` (offline): the birthplace abroad split, 06-11's raw levels and
  average, the raw marital status, the households by every head's sex, `_with_dwelling` and
  the occupants by sex.
- `test_long_matches_category_words` is gone with `_long`; `test_checks_are_consistent`
  admits 10_01A's PDF and the 2010 averages and shares.
- `test_state_01_within_tolerance`: **20,752** cells (14,253 before: 2010 +2,316 new, +672
  widened; 2015 +3,511), every one within tolerance.
- `tests/test_cpv_tabulados.py`: **31 passed**. The full suite was not run: 7x touches only the
  check script and its tests (as 7v, 7w).

## Verification

- The new and widened checks over 32 states, the nation and every size through a scratch
  harness on cached frames: every cell exact (08_21A's sector rows first read as counts: they
  are shares of each size; 12_07A first left out the locales: they answer).
- The full report: one run per edition (four processes; 2010/2015 on cached frames, 2000/2020
  through the loaders; ~40 min on the Mac), the sections spliced as `report()` writes them
  (the four headers and footers identical): 758,477 cells, 0 beyond tolerance.

## Left out

- Nothing of Censo 2010's ampliado (80 workbooks, every cell; 10_01A from its PDF, the
  shares to their two decimals) nor of the EIC 2015 (every sheet, every cell).
- **Censo 2020** (the same probe): the unspecified-age rows of 01-02 and 01-04 (and their
  by-size twins), 07-03/04's fields of higher education (07-04 reads its total only), 08-05…08's
  employed (the shares only), 09-03/04's use of services by affiliation (09-04 reads each
  row's population only) — 7w's «every row» read every row of its own checks, not these
  cells.
- The 2010/2015 infant mortality (7o: not reproducible from the sample).
