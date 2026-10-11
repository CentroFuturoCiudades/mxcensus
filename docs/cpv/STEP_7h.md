# CPV Unit 7h — more tabulado checks: the Censo 2010 and 2020 dwellings, the owners' sex

Done **2026-10-11** (on the Mac, overnight, unattended, as 7g). HANDOFF candidate 3's «Censo
2010's and 2020's dwelling tabulados (raw items, as 7d did for 2015)», with 7d's leftover
EIC 2015 owners by sex (14-14, 14-16 by the owner's sex) and Censo 2020's (16-28), which
join the person file. Gate: every new cell exact (within the tolerance, 1 person) in every
state and the nation; tests green. Checks only: no loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Censo 2010** (`ccpv/2010/tabulados/Ampliado/14_NNA_ESTATAL.xls`, «Parámetro»; the
  tabulados by state — the odd-numbered ones by locality size repeat them): 14_02A walls ×
  roofs, 14_03A tenure (dwellings and occupants), 14_05A the owned dwellings by rooms ×
  acquisition, 14_07A the toilets by use × water, 14_09A equipment, 14_10A the water supply
  of the dwellings with piped water, 14_12A kitchen × cooking fuel, 14_14A waste (dwellings
  and occupants). 8 workbooks added to `SOURCES`.
- **Censo 2020** (`cpv2020_a_eum_16_vivienda.xlsx`, the even sheets by state; 6p had read
  34): walls, roofs, the room to cook, the place, the fuel, the chimney of who cooks with
  wood or charcoal, light bulbs and energy-saving bulbs, the toilet's use, equipment, waste
  separation and disposal, tenure, the owners' sex, deeds, acquisition, the credit's
  payment — each for the dwellings and (where published) the occupants.
- **The owners' sex** (EIC 2015 14-14 and 14-16 by sex, Censo 2020 16-28): the owner items
  (`NUM_DUE_VIV1`/`2`, `DUE1_NUM`/`DUE2_NUM`) hold person rows; `_frame` now attaches
  `DUE1_SEXO`/`DUE2_SEXO` to the 2015/2020 dwelling frames from the person file (`ID_VIV`,
  `NUMPER`, `SEXO`, a column-projected read; `_with_owners`). 99 = the owner not identified.
- Helpers: `_dwellings_2010`/`_dwellings_2020` (the tabulados' dwelling universe), `_sel`
  (a category: any, «N or more», a tuple of codes, a code), `_crossed` (two items),
  `_rows_of` (the «Viviendas»/«Ocupantes» rows), `_two_blocks` (2020's items with a dwellings
  and an occupants block), `_occupants_title`; `_stacked` takes the estimator (2010's
  «Parámetro»), `_items` a universe.

## The definitions found

- **The dwelling universe**: Censo 2010 leaves out `CLAVIVP` 5–7 (locales, móviles,
  refugios; the class not specified, 9, counts), Censo 2020 07–09 — their items are blank;
  as the EIC 2015 (7d).
- **2010**: «con agua entubada» (14_10A) = `DISAGU` 1–2, inside the dwelling or the lot (the
  dwellings asked `DOTAGUAD`); «una o dos veces a la semana» = `DOTAGUAD` 3 + 4; the toilet's
  shared use = `USOEXC` 1; the toilet takes water = `CONAGU` 5 (flush) or 6 (bucket), its
  two shares of those, 7 and 9 of all; «leña y carbón» = `COMBUST` 3 + 4, electricity is
  «otro combustible»; waste «barranca, río, lago o mar» = `ELIBAS` 7 + 8; «5 cuartos o más»
  = `TOTCUART` 5–98.
- **2020**: the shared toilet = `USOEXC` 1 (the question asks whether they share it); bulbs
  in groups of five (`FOCOS` 999 = not specified); **energy-saving bulbs**: none =
  `FOCOS_AHORRA` 0 whatever the total (also when `FOCOS` is not specified), not specified =
  `FOCOS_AHORRA` 999, the shares of the rest; the credit's payment (16-36) is asked of the
  owned dwellings bought or built (`FORMA_ADQUI` 1–3) with a credit (a `FINANCIAMIENTO`
  source 1–7, not only their own resources: = the dwellings with `DEUDA`).
- **The owners**: 2020 one owner (`DUE2` blank) by sex, co-owners two women / two men / a
  woman and a man (either order), not identified (`DUE1_NUM` 99); 2015 in their order
  (only a man, only a woman, a man and a woman, a woman and a man, both of one sex, not
  identified); 2015's deeds by «the owner's sex» = the first owner's.

## The data

**INEGI's tabulados, every state and the nation** (`scripts/check_cpv_tabulados.py`,
`TABULADOS_REPORT.md`): **72,015 cells** (53,469 before), none beyond tolerance; the earlier
checks unchanged. The 18,546 new cells, in persons (dwellings or occupants), sex T:

| edition | tabulados | cells | max \|Δ\| |
|---|---|---|---|
| Censo 2010 | 14_02A, 03A (×2), 05A, 07A, 09A, 10A, 12A, 14A (×2) | 8,646 | 0.01 (14_07A, the nation) |
| EIC 2015 | 14-14, 14-16 by the owner's sex | 825 | 0.00 |
| Censo 2020 | 16-02 … 16-36 (16 tabulados; 14 with the occupants) | 9,075 | 0.62 (16-04b, the nation) |

**Every new cell is exact.** 2020's percentages have six decimals: on 125,229,023 occupants
that leaves up to 0.63 of a person nationally (0.17 on the dwellings); 2010's carry full
precision. The codes, the universes and the person join hold in every state.

## Tests

- `test_sel_and_crossed`, `test_with_owners_and_their_sex`, `test_saving_bulbs_and_titles`
  (offline).
- `test_state_01_within_tolerance`: 562 more state-01 cells (2010 262, 2015 25, 2020 275;
  2,150 in all), every new one sex T.
- `test_checks_are_consistent` covers the new checks and sources.

## Verification

- The report: every edition, 32 states (~30 min on the Mac, beside the 7g suite).
- `tests/test_cpv_tabulados.py`: 16 passed. 7h touches only the check script and its tests;
  the rest of the suite is 7g's run (1912 passed, 1 skipped).

## Left out

- Censo 2010's and 2020's tabulados by locality size (the odd-numbered ones) repeat the
  state ones.
- CGPV 2000's dwelling tabulados (`C2KVI01`–`19`, shares in points; VI06/VI10 since 6i):
  the next unit (7i).
