# CPV Unit 7o — more tabulado checks: fertility rates and infant mortality

Done **2026-10-11** (on the Mac, with the user). HANDOFF candidate 3, the rates: the user
chose «rates across editions» — the fertility rates and the infant mortality of Censo 2010,
the EIC 2015 and Censo 2020 — over finishing Censo 2020's ampliado set, Censo 2010's
leftovers and the tabulados by locality size. Checks only: no loader, derivation or
dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Unit «rate»**: per 1,000 (`_value`); a `Check` may `combine` its computed values into the
  published cells (`_with_tgf`: each block's seven fertility rates, then its Tasa Global de
  Fecundidad = 5 × Σ rates / 1,000).
- **`_national(estimator, names, sheet)`**: a national tabulado by locality size (and the
  mother's age), its named rows in order as the nation's cells; `_estimator_rows` (the
  «Estimador» layout without the state filter) now underlies `_estimates`.
- **Nine checks** (`_rate_checks`), each edition's own items (`_LAST_CHILD`: 2010 `NUMHIJ`,
  `FECNACA`, `SOBREVI`, `EDAMORA`; 2015/2020 `HIJOS_NAC_VIVOS`, `FECHA_NAC_A`,
  `SOBREVIVENCIA`, `EDAD_MORIR_A`, 2020 also `EDAD_MORIR_TD`), the locality size from
  `TAMLOC` (2015/2020 1–5) or `TAM_LOC` (2010 01–04; state 15's `tam_loc`):

  | edition | fertility by state | fertility by size (national) | infant mortality (national) |
  |---|---|---|---|
  | Censo 2010 | `02_02A_ESTATAL.xls` | `02_01A_ESTATAL.xls` | `03_01A_ESTATAL.xls` |
  | EIC 2015 | `02_fecundidad.xls` 04 | 02-03 | `03_mortalidad.xls` 02 |
  | Censo 2020 | `cpv2020_a_eum_02_fecundidad.xlsx` 02 | 01 | `cpv2020_a_eum_03_mortalidad.xlsx` 01 |

  Five workbooks added to `SOURCES` (2010's three, 2020's two; 2015's were read already).

## INEGI's rules, found on the data

**Fertility rates** (every edition, exact): the rate of the age group *g* (the woman's age at
the census, five-year groups 15–49) of the year before the census (2009, 2014, 2019) is

    1,000 × Σ FACTOR (women of g whose last child born alive was born that year)
          / Σ FACTOR (women of g, without children born alive 98 — the topic omitted —
                      and without the last child's year 9999)

An unspecified number of children (99) stays in the denominator: Baja California 2020's
20–24 missed by exactly the weight of those women (172) until it did. The first try (both
98 and 99 out) was exact in 12 of the 33 geographies of 2020.

**Infant mortality, Censo 2020** (exact, all 24 cells): the last children born in 2019 whose
mother was 12–49 at the census (the «Total»; 12–19, 20–34, 35–49), dead with
`EDAD_MORIR_TD` 0–364, per 1,000 of them. `EDAD_MORIR_TD` is INEGI's own: one death with its
days given but its birth month unspecified has none (and is not counted); «menos de un año»
(`EDAD_MORIR_M` 98, `EDAD_MORIR_TD` 999 — INEGI's processing code for a death of unknown age
among the children born less than a year before the census) and the unknown age
(`EDAD_MORIR_D` 99) are out.

**Infant mortality, Censo 2010 and EIC 2015: not reproducible from the sample.** Every
variant tried misses:

- the cohort count (the deaths under one of the last children born in the year, with or
  without the unknown ages, the unknown survival out or in): the nation within 0.09 (2010)
  and 0.17 per 1,000 (2015) at best, INEGI higher; cells up to 1.0 and 1.8 off, both ways;
- the mother's age at the birth (age − 1, or minus the completed years since the birth):
  worse;
- other birth windows (the 12 months before the census, 12–24 months before, two years) and
  censored life tables (Kaplan–Meier by month of age, exposure up to the census month):
  worse;
- deaths *occurring* in the year (INEGI's definition of the rate: deaths under one in the
  year / births of the year; children born the year before included), with the death month
  spread over the possible ones (the public files give no day of birth): about the cohort
  count's distance;
- a least-squares fit over the parts (deaths in the year, in the next, of the year before's
  births, the unknown ages) leaves 1–2 records per cell with coefficients that are no clean
  0/1.

The decisive test needs no numerator: if a cell were Σ deaths / Σ births over the sample's
records, each «Total» would equal the sum of its three age groups once turned into counts
(rate × births). In Censo 2020 it does, exactly; in 2010/2015 it fails under every
denominator and age grouping tried — in one size block the «Total» is even below the sum of
its parts, which no wider universe can give. So INEGI's 2010/2015 estimate is no ratio of the
public sample's weighted records: an estimator or data (exact dates) we do not have.

The user chose to check them anyway, on the cohort rule (every death not aged in years — the
unknown ages included — of the last children born the year before, per 1,000 of them), with
a tolerance of the largest gap: 1.0 (2010) and 1.8 per 1,000 (2015).

## The data

**INEGI's tabulados, every state, sex and the nation** (`TABULADOS_REPORT.md`, regenerated
over the full mirror in 1 h 05 min): 996 new cells, every one within its tolerance; the
report 147,787 → **148,783 cells, 0 beyond tolerance**.

| check | cells | max \|Δ\| per 1,000 (where) |
|---|---|---|
| 2010 `02_02A` fertility by state | 264 | 0.0000 |
| 2010 `02_01A` fertility by size | 40 | 0.0000 |
| 2010 `03_01A` infant mortality | 20 | 0.9917 (15,000–99,999, mothers 12–19); median 0.24 |
| 2015 02-04 fertility by state | 264 | 0.0000 |
| 2015 02-03 fertility by size | 48 | 0.0000 |
| 2015 03-02 infant mortality | 24 | 1.7902 (15,000–49,999, mothers 12–19); median 0.18 |
| 2020 02-02 fertility by state | 264 | 0.0000 (5 × 10⁻⁷) |
| 2020 02-01 fertility by size | 48 | 0.0000 |
| 2020 03-01 infant mortality | 24 | 0.0000 |

The national infant mortality («Total», every size): ours 0.09 (2010) and 0.17 (2015) per
1,000 below INEGI's.

The report's intro now names the rates (per 1,000, to 0.0001 unless a note says otherwise);
the line was edited in place to the script's new wording (checked equal to `report()`'s).

**Verification.** `tests/test_cpv_tabulados.py` 23 passed (Mac); 7o touched only the check
script, its tests and the docs, so the rest of the suite is 7n's (`wsl`: HANDOFF §Review).

## Tests

- `test_rates_tgf_and_national_rows`: unit «rate», `_with_tgf`, `_national` (a missing row
  raises).
- `test_fertility_rates_and_infant_mortality`: the masks on synthetic frames (98/99/9999,
  the 50-year-old mother, 2020's `EDAD_MORIR_TD`, 2015's deaths aged in years, 2010's
  `tam_loc`).
- `test_state_01_within_tolerance`: the three fertility checks by state (8 cells each, sex
  T); the national checks need all 32 states (the report).
- `test_checks_are_consistent`: unit «rate» (2010, 2015, 2020).
