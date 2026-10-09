# CPV Unit 6o — the older ITERs' own indicators as constraints; `SECTOR`

Done **2026-10-09** (night, on the Mac; unattended, see `STEP_6m.md`). Gate: the indicators
the 1990–2005 ITER publish under their own names (no 2020 counterpart) and their samples can
answer are constraint cells, each checked against the ITER in all 32 states; a derived
sector of activity for every edition; tests green.

## `SECTOR` (new derived column, 1990, 2000–2025)

INEGI's three sectors (the 1990/2000 ITER's `POCUSECP`/`POCUSECS`/`POCUSECT`):
«Primario» (agriculture, livestock, forestry, fishing, hunting), «Secundario» (mining,
electricity and water, construction, manufacturing), «Terciario» (trade, transport,
services, government), «No especificado», «Blanco por pase» (not employed):

- 2000–2025 from the SCIAN code (`_sector`): sector 11 primary; 21, 22, 23, 31–33
  secondary; 99 not specified; any other sector of the classification tertiary (an unknown
  sector raises, as `ACTIVIDADES_C_COARSE` does). 2000 reads its 3-digit subsector
  (`ACTTRAB_C`), 2010 its 4-digit `ACTTRAB_C`, 2015–2025 `ACTIVIDADES_C`.
- 1990 from its CMAP code (`C_A_ECO`, 5 digits; `_sector_1990`): the first digit is the
  division — 1 agriculture; 2 mining, 3 manufacturing, 4 electricity and construction; 5
  trade, 6 transport, 7 finance, 8 services; 9 not specified; 00000 not employed.
- 1995 and 2005 have no activity item (the Conteos).

## The cells (`_EDITION_CELLS`)

Each ITER publishes indicators of its own (the crosswalk keeps them under their names: no
2020 counterpart, or not comparable); those the sample can answer are edition cells, by each
ITER's definitions:

| edition | personas | viviendas |
|---|---|---|
| 1990 | 12 → **23**: literacy (6–14, 15+), attendance (5, 6–14), posprimaria, the three sectors | 5 → **9**: walls and roofs of waste material or cardboard, two rooms with a kitchen nobody sleeps in, owned |
| 1995 | 6 → **10**: aged 6–14, literacy (6–14, 15+) | 3 |
| 2000 | 34 → **60**: aged 0–4, 6–14, 15–24; attendance (5, 6–14, 15–24); literacy; single (12+); non-Catholic (with or without «sin religión»); posprimaria, secundaria, media superior or superior, 18+ without media superior; the three sectors; employed without income; hours 41–48 and 49+ | 16 → **33**: walls, roofs, two rooms, cooking fuel (gas, firewood, charcoal, kerosene), drainage + water, drainage + electricity, water + electricity, owned, paid off, being paid, rented, all ten goods, video, boiler |
| 2005 | 43 → **83**: ages 0–4, 0–14, 5, 6–14, 15–24, 15–59, 65+ (by sex where published), attendance (5, 6–14, 15–24, by sex), basic education incomplete / complete / posbásica (by sex), indigenous language by sex, the Seguro Popular | 21 |
| 2010 | 142 → **143**: the Seguro Popular (`PDER_SEGP`, not comparable with 2020's INSABI) | 26 |

What the data decided (each against the ITER in five states first, then all 32):

- **2000's «sólo disponen de drenaje y agua entubada»** (`VP_DREAGU`, `VP_DREELE`,
  `VP_AGUELE`) count the dwellings with **both** services, whatever the third: the «only»
  reading gives under 3%, the ITER ~93%.
- **«Dos cuartos incluyendo la cocina»**: in 2000 any two rooms (`TOTCUART` 2 counts the
  kitchen; adding the exclusive-kitchen condition of its dictionary puts it 3 points under);
  in 1990 two rooms with a kitchen nobody sleeps in (`TAM_DUERME` 4; two rooms alone are
  5–10 points over). Each matches its ITER within about 0.1.
- **2000's owned dwellings** are `TENVIV` «Sí» (a resident owns it): `TENPROP` 3–5 (being
  paid, paid off, other) is 0.9 points under, the owners whose situation is unspecified.
- **1990's waste material** is «otros materiales» (its list has no «material de desecho»):
  cardboard alone is 0.3–1.2 points under, with it within 0.1.
- 2000's posprimaria includes técnica after primaria (6k), so it is `EDUC_INEGI` above
  primaria; media superior and superior together are «Posbásica».

Left out: 2000's disability (`PCONDISC`…: the sample's shares are 30–60% above the census's,
too far for a cell), income in minimum wages (`P_1SM`…: 2000's minimum wage had three
zones), hours up to 32 and 33–40 (`HORTRA_CAT` bins 21–40), 18+ with media superior or with
superior apart (`EDUC_INEGI` merges them), 2000's 2–5 rooms without the exclusive kitchen,
the household head's sex (`HOGJEF_*`, no dwelling item), 2005's residence in the US in 2000
(no country category), averages and 1995's percentages (`P_P*`).

## Verification: every cell against the ITER, 32 states

Each cell's share against the ITER's (the 1995 sample weighted by `FACTOR` = `FAC_POB`,
`harmonize=True`; the 1990 extract and the 2005 sample unweighted):

| edition, table | new cells | median \|Δ\| | 90th pct. | max \|Δ\| | the edition's earlier cells (median) |
|---|---|---|---|---|---|
| 1990 personas | 11 | 0.06 | 0.31 | 1.33 (Baja California, literacy) | 0.08 |
| 1990 viviendas | 4 | 0.12 | 0.72 | 2.00 (Campeche, owned) | 0.45 |
| 1995 personas | 4 | 0.40 | — | 1.62 | 0.06 |
| 2000 personas | 26 | 0.23 | 1.02 | 5.02 (Baja California, literacy) | 0.30 |
| 2000 viviendas | 17 | 0.32 | 1.18 | 2.82 (Nayarit, drainage + electricity) | 0.42 (6n) |
| 2005 personas | 40 | 0.10 | 0.65 | 7.58 (Quintana Roo, 15–59) | 0.13 |
| 2010 personas | 1 (Seguro Popular) | 0.70 | — | 2.81 (Campeche) | 1.2–2.2 (other affiliation cells) |

The new cells sit in their edition's band; the outliers are the samples' known ones
(STEP_6n.md: 2000's population without characteristics in Baja California, Colima, México;
2005's Quintana Roo). The sectors: 1990 within 0.4 points everywhere (median 0.05–0.1),
2000 within 2.6 (its employed share is 0.7–1.3 points above the census's, the ampliado's
activity check).

## Tests (`tests/test_cpv_derived.py`)

- `test_derive_sector` (offline): 1990's CMAP divisions, 2000's subsectors, the 4-digit
  SCIAN (primary, secondary, tertiary, not specified, blank), an unknown sector raises; the
  synthetic 1990 persons carry `C_A_ECO`.
- `test_source_codes_match_2020`: 1990 `C_A_ECO` (catalog CATACTEC, own codes);
  `test_cpv_derivations_listing`: `SECTOR` in 1990 and 2000–2025.
- `test_cpv_constraints_per_edition`: the new counts and cells.
- `test_6o_cells_equal_iter` (real, state 01): every new cell of 1990, 1995, 2000 and 2005
  within 1 point of the ITER (persons; dwellings 1.5).
- **Full suite**: 1772 passed, 1 skipped (31 min, the Mac's full mirror; with 6p in the tree).
