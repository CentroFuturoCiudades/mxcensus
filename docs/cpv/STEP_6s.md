# CPV Unit 6s — the household head's sex for 2000–2010

Done **2026-10-09** (on the Mac; HANDOFF candidate 1, agreed with the user after the review
of 6m–6r). Gate: the legacy `HOGJEF_F`/`HOGJEF_M` constraints (households by the head's sex)
for CGPV 2000, the Conteo 2005 and Censo 2010, each within its sample-vs-census band of the
ITER in all 32 states, tests green.

## The gap

Censo 2020 and the EIC 2025 publish the head's sex as a dwelling item (`JEFE_SEXO`); the
legacy dwelling constraints `HOGJEF_F`/`HOGJEF_M` count on it. The 2000, 2005 and 2010
dwelling files have no head item, but their ITERs publish both indicators (2000 `HOGJEFF`/
`HOGJEFM`, 2005 `HOGAR_JF`/`HOGAR_JM`, 2010 `HOGJEF_F`/`HOGJEF_M`; the crosswalk renames
them), so the head has to come from the person file. 1990 and 1995 publish no household
indicator.

## The user's choices

- **Where**: `load_cpv_viviendas(derived=True)` reads the person file (as 6j's 1990/1995
  dwellings do), so `cpv_constraints("viviendas", …)` describes the dwelling frame whatever
  the loader — not a column only `load_cpv_survey` adds.
- **The Conteo 2005**: its dwelling file has one row per dwelling, but its ITER counts
  households (248,905 against 245,625 dwellings in Aguascalientes, +1.3%). A dwelling takes
  **its first household's head**; `HOGJEF_F`/`HOGJEF_M` then count dwellings, as 2005's
  existing `TOTHOG` cell already did. The share is the same within 0.1 point (the first
  household's head vs every household's: 21.18 vs 21.19% in state 01, 18.58 vs 18.70 in
  07, 29.00 vs 28.98 in 09).

## What changed

- `cpv._HEAD_FROM_PERSONS`: per edition, the relationship item, the head's codes and the key
  parts — 2000 `OTROPARE_C` 100; 2005 `PARENT` 101 (jefe) and 102 (persona sola); 2010
  `PARENT` 01.
- `cpv._attach_heads(df, period, state, harmonize)`: reads only those columns and `SEXO`
  from the person parquet (column projection), derives the keys as the dwelling frame has
  them (`_composite_keys`; 2010 with `harmonize=True`: `_national_keys`), checks **exactly
  one head per household** (else `ValueError`), and puts the head's raw `SEXO` on each record
  — 2000's rows are households, a 2005 dwelling takes the head of its lowest-numbered
  household, 2010's household is the dwelling. A record without a head raises.
- `_load_level`: with `derived=True` on those three editions' dwellings it attaches the head
  before `derive` and drops the helper `SEXO` afterwards.
- `cpv_derived`: `JEFE_SEXO` (`_jefe_sexo`) for 2000/2005/2010, mapped with the legacy
  `JEFE_SEXO` map and dtype (Hombre/Mujer, 2020's item); `_RECODE` 2000/2005 `SEXO` 2 → 3
  (their women; the core `SEXO` `Alias` does the same for the labels).
- Constraints: `HOGJEF_F`/`HOGJEF_M` now apply (2000 viviendas 33 → **35**, 2005 21 → **23**,
  2010 26 → **28**).

## The data (all 32 states)

- **One head per household** in every state of the three editions: no household without a
  head, none with two; the heads' `SEXO` codes are 1/2 (2000/2005) and 1/3 (2010); every 2005
  dwelling has a household 01.
- **The method on Censo 2020**, which publishes both: the person whose `PARENTESCO` is 101 is
  unique per dwelling and has the dwelling item `JEFE_SEXO`'s sex in **every** dwelling
  (states 01, 07, 09, 15, 19).
- **Raw = harmonized**: with `harmonize=True` (2010: national keys) every record gets the same
  head as the raw load (state 02, each edition).

## Verification: `HOGJEF_F` against the ITER

The female-headed share of `TOTHOG` (Σ `FACTOR`; the 2005 sample unweighted) through
`load_cpv_viviendas(derived=True)` and `cpv_constraints`, against the ITER's
`HOGJEF_F` / `TOTHOG`, per state, in points (`HOGJEF_F` + `HOGJEF_M` = `TOTHOG` in every
state):

| edition | states | median \|Δ\| | 90th pct. | max \|Δ\| |
|---|---|---|---|---|
| CGPV 2000 (households) | 32 | 0.23 | 0.58 | 0.83 (Tlaxcala) |
| Conteo 2005 (dwellings, first household's head) | 32 | 0.12 | 0.35 | 0.94 (Colima) |
| Censo 2010 (dwellings) | 32 | 0.36 | 0.97 | 1.51 (Aguascalientes) |

The 2000 frame's Σ `FACTOR` is 0.996–1.080 of the ITER's households, 2010's 1.002–1.066 of
its dwellings; each state's loader run takes 1–4 s (2000: 62 s for all 32 states, 2005: 53,
2010: 66).

2010's sample is the ampliado questionnaire's: it sits as far from the census as 2020's own
sample does from its ITER (`JEFE_SEXO` female share, states 01/07/09/15/19: −0.27, −0.63,
+0.48, −0.69, −1.68 points). 2000 and 2005 are closer.

## Tests (`tests/test_cpv_derived.py`)

- `test_derive_jefe_sexo` (offline): the three editions' codes, the dtype, an unknown code and
  a missing `SEXO` raise.
- `test_attach_heads` (offline, synthetic person parquet through a patched `POOCH`): 2000 per
  household, 2005 the first household (a 102 «persona sola» head), 2010 raw and national
  keys; a household with two heads and a record without one raise.
- `test_source_codes_match_2020`: the head's `SEXO` is read from the person dictionary and
  compared with 2020's `JEFE_SEXO` (`_FROM_PERSONS`).
- `test_cpv_derivations_listing`, `test_cpv_constraints_per_edition`: `JEFE_SEXO` in
  2000/2005/2010 only; the new counts and cells.
- Real (state 01): `test_jefe_sexo_equals_iter` (2000/2005 within 0.3 points, 2010 2.0;
  `HOGJEF_F` + `HOGJEF_M` = `TOTHOG`), `test_head_from_persons_2020` (the 2020 method check),
  `test_6n_cells_equal_iter` (2010's dwelling cells 26 → 28).
- `test_derive_dwellings_and_older_editions`, `test_derive_dwellings_2000_2005`: their
  synthetic 2000/2005/2010 dwellings carry the head's `SEXO` (`derive` needs it now).
- **Full suite**: 1781 passed, 1 skipped (30 min, the Mac's full mirror; the first run
  failed only the two synthetic tests above, fixed and rerun with `test_cpv_derived.py`:
  248 passed).
