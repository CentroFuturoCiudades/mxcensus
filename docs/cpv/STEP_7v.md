# CPV Unit 7v — more tabulado checks: the EIC 2015's remaining tabulados

Done **2026-10-12** (on the Mac, with the user). HANDOFF candidate 3's «EIC 2015» item, the
user's choice over Censo 2010/2020's leftovers, a 2015 locality edition and the small
cleanups. Gate: every new cell exact in every state, sex, locality size and the nation; tests
green. Checks only: no loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Every EIC 2015 tabulado is now read.** The probe listed the 34 sheets of the cached
  workbooks no check read; INEGI's file-listing API (`idBiinegi` 1714, `tipodocto` 5) named two
  workbooks `SOURCES` never had — `13_ingresos_monetarios_diferentes_al_trabajo.xls` (other
  incomes) and `15_suficiencia_alimentaria.xls` (food access) — added (15 workbooks).
- **27 checks by state** (`_person_checks_2015_v`; two of them national):
  - education: 06-02 literacy of the 6–14 (`ALFABET`), 06-04 of the 15+ by age, 06-06 school
    attendance (`ASISTEN`) by one-year age, 06-08 the level (`NIVACAD`) and the grades in
    primaria (`ESCOLARI`) by sex and age, 06-10 the grades in secundaria;
  - health services: 07-05 their use (`SERSALUD`) by sex, 07-06 by affiliation and
    institution (the derived `DHSERSAL_*`);
  - economic characteristics: 08-03 the not economically active by kind (`CONACT` 31–35), sex
    and age, 08-10 the employed by sector × occupational division (the derived
    `ACTIVIDADES_C_COARSE`, `OCUPACION_C_COARSE`), 08-12 the salaried's benefits by sector;
  - commute times: 10-02 the students' (`TIE_TRASLADO_ESCU`) by age, 10-05 the employed's
    (`TIE_TRASLADO_TRAB`) by position (`SITUACION_TRAB`);
  - households: 12-01 the population by relationship (`PARENT`), sex and age; 12-03/12-06 the
    households by size (`NUMPERS`) and by type and class (`TIPOHOG`), by the head's sex and age
    (the dwelling file's `JEFE_SEXO`, `JEFE_EDAD`);
  - migration: 04-03 the born abroad (`ENT_PAIS_NAC_INEGI` «OtroPais»; the United States 221)
    by nationality (`NACIONALIDAD`) and sex, 04-06 internal migration (immigrants, emigrants by
    their 2010 entity — `ByOrigin`, so all 32 states —, net by `Check.combine`), 04-04 the
    residence in 2010 by municipality (`LUGAR_RES_5A`) by age (national);
  - ethnicity: 05-01 indigenous language (`HLENGUA`) and Spanish (`HESPANOL`) by sex and age,
    05-05 understanding one (`ELENGUA`), 05-06/07 indigenous and afrodescendant
    self-identification (`PERTE_INDIGENA`, `AFRODES`) by sex and age, 05-03 the speakers by
    language (`QDIALECT_INALI`) by state, 05-02 by language, sex and age (national);
  - 13-02 the households by other incomes (the derived `INGR_OTROS`, 6z) and source (`INGR_*`),
    15-01/02 by the adults' and the minors' food access (`ALIM_*`, `ING_ALIM_*`).
- **11 checks by locality size**: 06-01, 06-03, 06-05, 06-09, 07-04, 12-02 through `_SIZE_TWINS`
  (their by-state twins' layout); 06-07 (one-year ages), 07-03 (by age, no sex), 08-04 (the
  participation rates, unit «points») and 08-05 (position), which have no by-state twin, and
  13-01 (by household size) through a twin built for them (`_size_twins_2015_v`, never run by
  state).
- **Readers and cells**: `_sex_columns` (the sexes in columns: a category's share of the total,
  then the sexes' shares of it) with `_sexed`/`_sex_cells`; `_age_group` reads one-year ages
  («03 años») and any age column (`JEFE_EDAD`); `_by_dims` takes the sex at another place
  (`sex_at`: 04-03's is last) and compares labels through `_dim` (06-03 writes «45- 54 años»);
  `_language_shares_published` (05-03: a «Total» row and one row per language spoken in the
  state, its percentage in the first value column); `_LANGUAGES_2015` = INEGI's catalog
  `TC_LENGUA_INDIGENA_INALI_2015` transcribed (the check list is built at import, before any
  data: a test compares it with the catalog when `data/dict/fd/2015` holds it).
- **Speed** (the new checks would have tripled a run): `_numeric`/`_cat` convert a column once
  per frame (`_CONVERTED`, cleared after each state; `pd.to_numeric` on the string columns was
  ~60% of a run), and `_part` sums on arrays (a mask on the frame's MultiIndex rebuilt it for
  every cell). The same sums to the bit: every 2015 cell of states 01, 09 and 15 and 04-06's
  origin sums compared equal with the old `_part`, and the full report's other editions are
  byte-identical (below). A missing mask value is False and a missing weight skipped, as
  pandas does (CGPV 2000's masks carry `pd.NA`).

## The definitions found

- **Técnica after primaria** (`NIVACAD` 6) is primaria with six grades in 06-07/08 and primaria
  in 06-09/10 (their footnotes); técnica after secundaria (7) posbásica, with preparatoria,
  bachillerato, normal and higher.
- **Benefits** (08-12): with benefits = some item «yes» (each as % of those); without = all
  seven «no»; not specified = no «yes» and some item 9. The rule «all seven 9» (7j's unpaid
  work) misses by up to 1,296 salaried in Aguascalientes.
- **Internal migration** (04-06): INEGI's «población de 5 años y más residente en la entidad en
  marzo de 2010» is the population that **lives in the entity now** and lived in some entity of
  Mexico in 2010 — stayers plus immigrants —, not the population that lived there in 2010
  (stayers plus emigrants: off by the net migration, e.g. 222,456 in the Ciudad de México).
  Abroad and not specified in 2010 are out; the nation's base is 107,396,355 either way.
- **The born abroad** (04-03): `ENT_PAIS_NAC_INEGI` «OtroPais», the country insufficiently
  specified included; the United States is code 221.
- **Food access** (15-02): the households with minors are those that answered the minors'
  items (`ALIM_MEN1` not blank: 214,423 in Aguascalientes = the tabulado); 15-01 counts every
  household, those without adults too.
- **Languages** (05-02/03): `QDIALECT_INALI` codes → the catalog's names; the tabulados list 72
  of its 73 (no Ku'ahl speaker in the sample) and only the languages spoken in each state.
- **Universes**: the 3+ / 6–14 / 12+ / 15+ leave out the unspecified ages; the population in
  households (12-01), the use of services (07-03/05) and self-identification (05-06/07) count
  every age, «No especificado» as its own row.

## The data

**INEGI's tabulados, every state, sex and the nation** (`TABULADOS_REPORT.md`): **376,570
cells** (209,272 before), none beyond tolerance. The **167,298** new EIC 2015 cells, **every
one exact** (≤ 0.6 of a person: the six-decimal percentages):

| check | cells | max \|Δ\| |
|---|---|---|
| 06-02/04/06 literacy and attendance (sexes in columns: sex T) | 9,900 | 0.00 persons |
| 06-08/10 level and grades in primaria/secundaria, by sex and age | 43,065 | 0.00 |
| 07-05/06 use of health services, by sex / by affiliation | 4,719 | 0.00 |
| 08-03/10/12 the inactive, sector × division, benefits | 24,156 | 0.00 |
| 10-02/05 commute times | 13,068 | 0.00 |
| 12-01 relationship, 12-03/06 households by the head's sex and age | 44,055 | 0.60 |
| 04-03/06 nationality, internal migration; 04-04 residence by age (nation) | 1,647 | 0.51 |
| 05-01/05/06/07 language, understanding, self-identification | 8,844 | 0.59 |
| 05-03/02 speakers by language (by state; nation by sex and age) | 3,330 | 0.04 |
| 13-02 other incomes, 15-01/02 food access | 1,848 | 0.06 |
| 11 checks by locality size (06-01/03/05/07/09, 07-03/04, 08-04/05, 12-02, 13-01) | 12,666 | 0.16 |

The derived columns they read hold in every state: `DHSERSAL_*` (6d), `ACTIVIDADES_C_COARSE`
and `OCUPACION_C_COARSE` (6f), `ENT_PAIS_NAC_INEGI` (6y), `LUGAR_RES_5A` (7b), `INGR_OTROS` (6z).

## Tests

- `test_eic2015_layouts_and_cells_7v` (offline): the sexes in columns, one-year and head ages,
  a sex after another dimension, «45- 54 años», técnica after primaria, the benefits' rule, the
  conversion cache (a copy is another frame), `_part` on a nullable mask.
- `test_eic2015_languages_and_migration_7v`: 05-03's rows, 04-06's base and origins, the
  transcribed catalog = INEGI's (when cached).
- `test_state_01_within_tolerance`: 4,645 more state-01 cells (10,322 in all); its place filter
  now keys on the edition too (2015's 10-02 is commute times, 2020's the place of school).
- `test_checks_are_consistent`: 04-06 is the one 2015 person check by origin.

## Verification

- The EIC 2015 over 32 states through a scratch harness on cached frames (18 min), spliced into
  the report (52 lines added, none changed); then a fresh full run (every edition, 32 states;
  50 min on the Mac): **byte-identical** to the spliced report — the 2000/2010/2020 sections
  untouched by the conversion cache and the array sums.
- `tests/test_cpv_tabulados.py`: 29 passed. 7v touches only the check script and its tests.

## Left out

- Nothing of the EIC 2015: every sheet of its 15 workbooks is read.
- Censo 2010's and Censo 2020's unread tabulados (HANDOFF candidate 3).
