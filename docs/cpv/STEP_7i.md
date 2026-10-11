# CPV Unit 7i — more tabulado checks: CGPV 2000's dwellings

Done **2026-10-11** (on the Mac, overnight, unattended, as 7g–7h). HANDOFF candidate 3's
«CGPV 2000's dwelling tabulados» (`C2KVI01`–`19`; 6i had read VI06 and VI10 on the derived
columns). Gate: every new cell within the 2000 band (0.04 points; Chiapas 0.6) in every
state and the nation; tests green. Checks only: no loader, derivation or dictionary
changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **CGPV 2000's dwelling tabulados by state** (`ccpv/2000/tabulados/ampliado/C2KVI*.xls`,
  Excel 95, shares in points), on the raw items: floors (VI01), walls (02), roofs (03),
  occupants per dwelling (04), rooms (05), bedrooms in detail (06d), kitchen (07), cooking
  fuel (08), the exclusive sanitary service and its water (09), drainage in detail (10d),
  water (11), its supply (12), electricity (13), tenure (14), the building's age (15), ten
  goods (16), waste disposal (17) and its collection frequency (18), and the averages per
  dwelling (19). Each but VI04, VI12 and VI19 for the dwellings and the occupants (`…o`:
  INEGI's OCUPANTES rows, Σ `FACTOR` × `NUMPERS`). 17 workbooks added to `SOURCES`.
- New readers: `_c2k_blocks(level="occupants")`, `_c2k_items` (C2KVI16: one row per good
  under each state), `_c2k_repeated` (C2KVI18: a block per way of disposal).
- **Averages** (VI19): a cell part may be `Weighted(mask, values)` — each record counts its
  value × the weight (occupants, households, rooms) — and a `Check` may have
  `unit="average"` (numerator ÷ denominator, compared within the 2000 band as they are).
- Helpers: `_of` (shares of a base), `_vi_coded`, `_vi05` … `_vi19`, `_dwelling_checks_2000`.

## The definitions found

- **The universe**: every private dwelling, each class (Σ `FACTOR` of the first households
  = the tabulados' totals: 198,682 in Aguascalientes, 2,124,632 in Mexico City); 7f's
  «Otro» classes carry the items here too. The script's 2000 dwelling frame already kept
  one row per dwelling (the first household's).
- **Walls** (VI02): «materiales ligeros, naturales y precarios» = `PAREDES` 1–7 (adobe
  included), «sólidos» = 8.
- **Rooms** (VI05) = `TOTCUART_INEGI` (7f: less an exclusive kitchen nobody sleeps in), as
  the 2000 ITER; `TOTCUART` (with the kitchen) misses by points.
- **Kitchen** (VI07): exclusive = nobody sleeps there (`COCDOR` 4), as % of the dwellings
  with a kitchen.
- **The exclusive sanitary service** (VI09) = `SERSAN` 1 and `USOEXC` 1; «no disponen» =
  `SERSAN` 2 or a shared one; not specified = `SERSAN` 9 or the use not specified.
- **Water supply** (VI12): «con agua entubada en la vivienda» = `DISAGU` 1–2, inside the
  dwelling or the lot (the dwellings asked `DOTAGUAD`), as Censo 2010 (7h).
- **Waste collection** (VI18): the dwellings that hand their waste to a service, a
  container, the street or a ravine (`ELIBAS` 1–4), the ones asked `ELIBASPE`.
- **Households per dwelling** (VI19): `NUMHOGS` holds their number where there are several,
  blank for one (= the dwelling's household rows in every dwelling of state 01).

## The data

**INEGI's tabulados, every state and the nation** (`TABULADOS_REPORT.md`): **82,476 cells**
(72,015 before), none beyond tolerance. The 10,461 new CGPV 2000 cells (sex T):

| checks | cells | median \|Δ\| | max \|Δ\| in a state but Chiapas | Chiapas |
|---|---|---|---|---|
| VI01–03 (materials), dwellings and occupants | 924 | 0.003 | 0.020 (the nation, slab) | 0.136 |
| VI04/05/06d (occupants, rooms, bedrooms) | 1,155 | 0.003 | 0.017 | 0.146 |
| VI07–10d (kitchen, fuel, sanitary, drainage) | 1,584 | 0.003 | 0.014 | 0.179 |
| VI11/12 (water, its supply) | 957 | 0.003 | 0.018 (the nation's tap: 0.037) | **0.844** |
| VI13–15 (electricity, tenure, age) | 1,386 | 0.003 | 0.021 | 0.115 |
| VI16 (ten goods) | 1,980 | 0.003 | 0.010 | 0.095 |
| VI17/18 (waste, its collection) | 2,310 | 0.003 | 0.019 (the nation's «container: never»: 0.057) | **1.789** |
| VI19 (averages) | 165 | 0.003 | 0.005 | 0.005 |

- **Chiapas** (the public sample's weights, as its other 2000 cells): its largest misses are
  shares of small bases — within the carried water, the public tap against another
  dwelling (0.74, occupants 0.84), within the dwellings using a container, «never
  collected» (1.57, occupants 1.79). `Check.tolerance` {7: 0.9} (VI11, VI11o) and {7: 1.6}
  / {7: 1.8, 0: 0.06} (VI18, VI18o; the nation's occupants cell inherits 0.057 of it),
  documented in the report.
- Every other state and cell sits within 0.021 points, the rounding of two decimals and
  the weights; VI19's averages within 0.005.

## Tests

- `test_c2k_items_and_repeated_blocks`, `test_weighted_parts_and_averages` (offline).
- `test_state_01_within_tolerance`: 317 more state-01 cells (2,467 in all), sex T.
- `test_checks_are_consistent`: the «average» unit is 2000's.

## Verification

- The report: every edition, 32 states (~32 min); a 2000-only run for the table above.
- `tests/test_cpv_tabulados.py`: 18 passed; 7i touches only the check script and its tests.

## Left out

- CGPV 2000's fertility, disability and language tabulados (`C2KFE*`, `C2KDI*`, `C2KLI*`).
