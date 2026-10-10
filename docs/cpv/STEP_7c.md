# CPV Unit 7c — CGPV 2000's places and the income in minimum wages

Done **2026-10-10** (on the Mac; the 32-state sweep on `wsl`). HANDOFF candidate 2's «CGPV
2000's places» and «income in minimum wages for 2000», agreed with the user at the session's
start and widened by the user to 2010–2020. Gate: 2000's places and every edition's income
in minimum wages equal to INEGI's tabulados (2000 within its sample band), the 2000 ITER's
indicators as constraints; tests green.

## The user's choices

- **The unit**: «2000 places + minimum wages» (over the ratio constraints and more EIC 2015
  checks), then, once the 2015/2020 tabulados showed income in minimum wages too, **2000 +
  2010–2020** for the wages (over 2000 only).
- **The column's name**: `INGTRMEN_SM` (beside the legacy `INGTRMEN_CAT`, in pesos).
- **The 1995 residence by municipality**: the person's own answer (`MUN95OTR_C` against the
  current municipality, as 2010–2025), not INEGI's Trancoso rule (below); the check allows
  the four states a documented band.

## The sources

**The place items of CGPV 2000** (its FD: «toda la información se concentra en el campo
`LTRABPAI_C` y sus valores tienen el mismo significado que `LNACEDO_C` y `RES95EDO_C`»):
`RES95EDO_C` / `LTRABPAI_C` hold the entity (001–032) or the country (100–535 as 2020's
catalog, 221 the United States; 600 a country not known), 999 not specified;
`MUN95OTR_C` / `LTRABMUN_C` the municipality of every Mexican answer (the own one too),
999 when not given. Censo 2010's layout without its split. The 999 of the place of work is
simply «no especificado»: Mexico City's employed give 87.86% in the entity (C2KEM10:
87.88), 5.66% elsewhere (5.66) and 6.49% with 999 (6.46), with or without a municipality.

**The minimum wages** (INEGI's monthly wage = the daily general minimum wage × 30; × 30.4
misses the 2000 tabulado by up to 6 points and the 2020 one by 3.6):

| edition | date | areas (daily wage) | INEGI's source | the municipalities |
|---|---|---|---|---|
| CGPV 2000 | February 2000 | A 37.90, B 35.10, C 32.70 | its FD's annex «Salarios mínimos generales por entidad federativa y áreas geográficas vigentes a febrero del 2000» (monthly 1,137 / 1,053 / 981) | = DOF 31/12/1999 |
| Censo 2010 | June 2010 | A 57.46, B 55.84, C 54.47 | catalog `TC_TABLA_SALARIOS_MUN_2010.DBF` (1,723.80 / 1,675.20 / 1,634.10) | = DOF 23/12/2009 = 2000's |
| EIC 2015 | March 2015 | A 70.10, B 66.45 (B rose to 68.28 on 1 April) | catalog `TC_SALARIO_MUN_2015.xls` (2,103 / 1,993.5) | A = 2010's A and B (DOF 29/12/2014), but for one slip |
| Censo 2020 | March 2020 | Zona Libre de la Frontera Norte 185.56, the rest 123.22 | none | DOF 23/12/2019 (43 municipalities) + San Quintín |

- **The EIC 2015 catalog's slip**: it puts Coacoatzintla (30-036) in area A where the DOF
  names Coatzintla (30-040). INEGI's tabulado follows the catalog to the person; the DOF's
  municipality misses Veracruz by 525 persons. `INGTRMEN_SM` follows the catalog.
- **San Quintín** (02-006, split off Ensenada in February 2020) is in the border zone for
  INEGI's 2020 tabulado (exact with it, 15,045 persons off without it).
- The 120 municipalities of 2000's FD annex map to the 2000 ITER's codes by name («Gral.
  Escobedo» = 19-021, «Tuxpan» = 30-189); 2000's and 2010's sets are equal code for code.

## What changed

- `cpv_derived`:
  - **2000 places**: `LUGAR_RES_5A` (`_ALIASES` `MUN_RES_5A` += `MUN95OTR_C`; the residence
    item was already aliased), `LUGAR_TRAB` and `ENT_PAIS_TRAB_INEGI` (2010's derivations,
    now `("2000", "2010")`; `_RECODE["2000"]["LTRABPAI_C"]` = {600: 998}).
  - **`INGTRMEN_SM`** (2000, 2010, 2015, 2020; `_ingtrmen_sm`): the income over the
    municipality's monthly wage (`_salario_minimo`, `_SALARIOS_MINIMOS`: daily wages in cents,
    areas `_SM_A`/`_SM_B` for 2000 and 2010, `_SM_A_2015`, `_ZLFN`), compared in cents
    (5 × 1,675.20 = 8,376 exactly), INEGI's groups: `_SM_2000` (below 1; from 1 to 2; above
    2 and below 3; from 3 to 5; above 5 to 10; above 10 — C2KEM08's, `_period_dtypes`) and
    `_SM` (up to 1; above 1 to 2; 2 to 3; 3 to 5; 5 to 10; above 10), «No recibe ingresos»,
    «No especificado» (999999; 999998, an income above 999,997, is above 10), «Blanco por
    pase». Ordered categoricals.
  - **Constraints**: CGPV 2000's ITER `P_1SM`, `P1_2SM`, `P2_5SM` (the 2–3 and 3–5 groups),
    `P6_10SM`, `P10_SM` as edition cells (2000 person constraints 65 → 70). No other ITER
    publishes income.
- `scripts/check_cpv_tabulados.py`: C2KEM08 (income), C2KEM10 (place of work; both sexes
  only), C2KMI04 (residence in 1995 by municipality and sex; another entity and abroad
  apart) as shares (`_place_shares`), Censo 2010 `08_10A`, EIC 2015 08-11, Censo 2020 08-18
  (income; the employed by occupational division's «Total» rows); `Check.tolerance`, a
  per-state override for documented differences of INEGI's own.
- Docs: `cpv_derived` docstrings, README, CLAUDE.md.

## The data

**INEGI's tabulados, every state, both sexes and the nation** (`scripts/check_cpv_tabulados.py`,
`TABULADOS_REPORT.md`): 31,116 cells (26,760 before), none beyond tolerance; the earlier
checks unchanged. The 4,356 new cells:

| edition | check | cells | median \|Δ\| | max \|Δ\| (where) |
|---|---|---|---|---|
| CGPV 2000 | C2KEM08 income in minimum wages (`INGTRMEN_SM`), points | 792 | 0.003 | 0.071 (Chiapas; elsewhere ≤ 0.02) |
| CGPV 2000 | C2KEM10 place of work by municipality (`LUGAR_TRAB`), points | 198 | 0.003 | 1.104 (Chiapas' same/another municipality; elsewhere ≤ 0.009) |
| CGPV 2000 | C2KMI04 residence in 1995 by municipality (`LUGAR_RES_5A`), points | 693 | 0.003 | 1.040 (Veracruz; below) |
| Censo 2010 | `08_10A` income in minimum wages, persons | 891 | 0.00 | 525 (State of México; below) |
| EIC 2015 | 08-11 income in minimum wages, persons | 891 | 0.00 | 0.00 |
| Censo 2020 | 08-18 income in minimum wages, persons | 891 | 0.00 | 0.24 (the nation: six-decimal percentages) |

Per-check tolerances (`Check.tolerance`): EM10 Chiapas 1.2; MI04 Chiapas 0.85, Guanajuato
0.1, Oaxaca 0.25, Veracruz 1.05, Zacatecas 0.96, the nation 0.1; `08_10A` the State of
México and the nation 525.5 persons.

**Residence in 1995 by municipality** (C2KMI04): within 0.013 points in 27 states; in
Guanajuato (0.10), Oaxaca (0.23), Veracruz (1.04), Zacatecas (0.95) and Chiapas (0.79) INEGI
counts more municipal migrants than the answers give (the «same municipality» share of the
same entity is that much lower). Zacatecas is the residents of Trancoso (32-057, created after
1995) who answered «Trancoso»: 0.916 / 0.948 / 0.887 points (T/H/M) against gaps of 0.919 /
0.951 / 0.883. No such rule fits the others: Campeche's Calakmul and Candelaria and Sonora's
Benito Juárez and San Ignacio Río Muerto (1996–98) show nothing (7.6% of Campeche answered
their own new municipality, and Campeche is within 0.007), the own-code answers in
Veracruz's three new municipalities (30-208 to 30-210) make 0.62 of its 1.03 points, and
Guanajuato and Oaxaca created none.

**The Censo 2010 income tabulado in the State of México**: up to 525 persons (0.012 points)
fewer in INEGI's three lowest groups and more in ours above; no change of one or two
municipalities' areas explains it (the best pair leaves 70). Every other state is exact.

**Every state of 2000, 2010, 2015 and 2020** (`load_cpv_personas(derived=True)`, raw and
harmonized: 256 loads on `wsl`, the patch applied there): no unmapped code and no own
entity without a municipality; raw = harmonized weighted totals of `INGTRMEN_SM`,
`LUGAR_RES_5A`, `LUGAR_TRAB`, `ENT_PAIS_TRAB_INEGI`; `INGTRMEN_SM`'s «Blanco por pase», «No
especificado» and «No recibe ingresos» = `INGTRMEN_CAT`'s in every row; the place of work is
asked of exactly the employed (2000 too); `LUGAR_TRAB` without the municipality =
`ENT_PAIS_TRAB_INEGI`, and 2000's `LUGAR_RES_5A` = the legacy `ENT_PAIS_RES_CAT` (2000 writes
no unspecified entity), in every row.

**The 2000 ITER** (`P_1SM` … `P10_SM`, % of its `POCUPADA`, the census against its sample;
the sample − the census by state): median |Δ| 0.41 (`P_1SM`), 0.76 (`P1_2SM`), 0.55
(`P2_5SM`), 0.24 (`P6_10SM`), 0.24 points (`P10_SM`); outside Chiapas and Oaxaca at most
1.29, 2.32 (Guerrero), 1.38, 0.69, 0.88; Chiapas 5.83 (`P_1SM`), Oaxaca 3.85 (`P1_2SM`).
The existing `POCUNINGR` sits as far (median 1.38, Chiapas 8.27): the 2000 sample's band
(its weights; 6i, 6o).

National totals (Σ `FACTOR`, thousands; CGPV 2000's weights are its ratio estimator):

| `INGTRMEN_SM` | CGPV 2000 | Censo 2010 | EIC 2015 | Censo 2020 |
|---|---|---|---|---|
| no income | 3,542 | 3,276 | 1,344 | 3,661 |
| below 1 (2000) / up to 1 | 4,366 | 3,779 | 3,522 | 10,962 |
| 1–2 | 10,370 | 9,459 | 12,011 | 20,349 |
| 2–3 | 6,082 | 8,867 | 10,142 | 9,058 |
| 3–5 | 4,859 | 7,961 | 8,358 | 4,571 |
| 5–10 | 2,746 | 4,202 | 3,936 | 2,463 |
| above 10 | 1,282 | 1,792 | 1,423 | 864 |
| not specified | 1,898 | 3,387 | 4,378 | 342 |

(Censo 2020's wage, $123.22 a day, was 1.8 times 2015's in pesos — the 2019–2020 rises —, so
its employed crowd the lowest groups.)

| CGPV 2000 | `LUGAR_RES_5A` (5+) | `LUGAR_TRAB` (employed) |
|---|---|---|
| same municipality | 78,863 | 27,190 |
| another municipality | 2,621 | 4,305 |
| municipality not specified | 263 | 302 |
| another entity | 3,795 | 1,776 |
| the United States / another country | 337 / 51 | 140 / 3 |
| not specified | 294 | 1,428 |

## Tests

- `test_derive_places_2000` (offline): every category of the two places, 600, 999, 221, the
  own entity without a municipality raises.
- `test_salario_minimo_7c`, `test_derive_income_sm_7c` (offline): the wage of each area and
  edition (2015's catalog slip, San Quintín), every bound in cents in both group sets, 999998,
  999999, blank, dtypes.
- `test_wage_tables_equal_inegi_catalogs` (the 2010/2015 catalogs, skipped without
  `data/dict/fd`): every municipality's wage.
- `test_derive_persons_2000_recodes`, `test_cpv_derivations_listing`,
  `test_cpv_constraints_per_edition` (2000: 70), `test_source_codes_match_2020` (2000's
  `LTRABPAI_C`, `LTRABMUN_C`, `MUN95OTR_C`), `test_6n_cells_equal_iter` (2000 persons: 38
  cells; `P10_SM` 0.28 points under its ITER in Aguascalientes).
- `test_state_01_within_tolerance` (`tests/test_cpv_tabulados.py`): 132 more state-01 cells.

Full suite on the Mac: **1889 passed, 1 skipped** (31 min; 7b's 1881 + the five new tests and three new source-code cases). The 32-state tabulado run and the `wsl` sweep above ran on the same code.

## Left out

- The EIC 2025's income in minimum wages: its estimates publish no income.
- The 1990/1995 incomes: their ITERs publish no income groups.
- Trancoso's own-code answers as «Otro municipio» (the user's choice above).
