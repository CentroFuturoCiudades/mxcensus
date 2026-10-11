# CPV Unit 7d — more tabulado checks: the EIC 2015's dwellings, CGPV 2000's employment and migration

Done **2026-10-10** (on the Mac). HANDOFF candidate 2's «more EIC 2015 tabulados» (the
dwelling materials, services and goods 14-04…14-33, the acquisition 14-17: raw items, a check
of the codes and the `CLAVIVP` 7–9 universe) and «more CGPV 2000 tabulados» (C2KMI02/05–13:
migration by state, the international migrants of the `migrantes` file; C2KEM02/03/04/06/09/11:
inactivity, participation rates, occupation, position, benefits), agreed with the user at the
session's start as one unit. Gate: every new cell within its edition's tolerance in every
state, both sexes and the nation; tests green. No loader, derivation or dictionary changed.

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Raw items**: the checks so far read derived columns; 7d's read the samples' own items
  (2015 `PISOS` … `PANEL_SOLAR`; 2000 `CONACT`, `SITTRA`, `OCUACTIV_C`, the five benefits,
  `HORTRA`, `LNACEDO_C`, `RES95EDO_C`, `CAUEMI`; the `migrantes` file's `MPAIRES_C`, `MEDAD`,
  `MLUGORI_C`, `MPDESOTR_C`, `MSEXO`) by their codes — the code meanings and the universes
  are what they check.
- **`ByOrigin`**: a cell part whose records count in their state of origin, not the frame's
  (the emigrants by their birth state or their state in 1995, the international migrants by
  the state they left; outside 1–32 the unspecified origin, state 99). `run` now accumulates
  every cell part as `{state: Σ weight}` over the loaded states and the nation as the sum of
  them all; a `Check(by_origin=True)` runs only with all 32 states.
- **`Check.weight`**: the occupants' tabulados weight each dwelling by `FACTOR` × `NUMPERS`
  (`_occupants`); exact against INEGI's occupants in every state.
- **`migrantes` frames** (`load_cpv_migrantes(labels=False)`), their sex `MSEXO`
  (`_SEX_ITEM`).
- **Readers**: `_c2k_sectors(total=True)` (C2KEM03: the state row, then its age groups),
  `_c2k_sex_columns` (C2KEM11: one row per state, the sexes in columns), `_c2k_states`
  (C2KMI09–12: one row per state, «NO ESPECIFICADO» = 99), `_c2k_national` (C2KMI07/08: the
  nation's, the men's and the women's blocks), `_stacked` (the EIC 2015 tabulados with a
  second row dimension — class, occupants, rooms, fuel, the item — matched by `_tokens`:
  `_words` drops digits, so «2 ocupantes» and «3 ocupantes» would collide).
- `run` reads each workbook once (the 3.3 MB `14_vivienda.xls` served 27 checks); a share of
  nothing against a published value is now a failure (Δ = ∞), not a silent NaN.

## The definitions found

**EIC 2015** (`CLAVIVP` 7–9 left out but in 14-02; each code as its FD):

- 14-02 the classes: every dwelling; «otro tipo» = `CLAVIVP` 06–09 (cuarto de azotea, local,
  móvil, refugio). The occupants = Σ `FACTOR` × `NUMPERS` (119,530,753 = INEGI's).
- 14-11 **the dwellings that cook**: a place (`LUGAR_COCINA` 1–3) or a fuel (`COMBUSTIBLE`
  1–4) given. «No cocinan» (`LUGAR_COCINA` 4, `COMBUSTIBLE` 5) is out, and so are the 150,929
  dwellings whose fuel is not specified and that name no place (a kitchen or an unspecified
  place): INEGI cannot tell whether they cook. Electricity is «otro combustible».
- 14-12 the stove (`ESTUFA`) of the 4,724,814 dwellings cooking with wood or charcoal
  (national only: published by locality size).
- 14-20/34 water: piped inside or in the yard; carried from a community tap, another
  dwelling, a pipa, a well, a river, rain (`ABA_AGUA_NO_ENTU`, the tabulado's order 2, 3, 5,
  1, 4, 6), not specified.
- 14-27 light bulbs of the dwellings with electricity, in groups of five (999 = NE).
- 14-28 a toilet by how it takes water (flush, bucket, none, NE), a latrine (bucket, none, NE).
- 14-30 the separation of the dwellings giving their waste to the service or a container.

**CGPV 2000** (shares in points):

- EM02 the inactive 12+: `CONACT` 40–80 (students, home, retired, unable to work, other).
- EM03 participation rates: the PEA over **every** person of the age (the unspecified
  activity included).
- EM04 occupation: the CMO's 19 principal groups = the first two digits of `OCUACTIV_C` (no
  SINCO bridge needed to check it).
- EM06 `SITTRA`; EM09 the wage earners (`SITTRA` 1, 2) by benefit, «none» = all five «no».
- EM11 TDA = unemployed / PEA; **TOPD2** = (employed who worked 1–34 hours **in the reference
  week** + unemployed) / PEA — who had a job but did not work (`CONACT` 20) is out, though the
  sample records their usual hours (with them: 20.15 nationally against INEGI's 19.84);
  **TIID** = (employed below one minimum wage, `INGTRMEN_SM` «Menos de 1 s.m.», those without
  income left out + unemployed) / PEA.
- MI02/05 the immigrants and emigrants as % of the residents born (living in 1995) in a
  specified Mexican state, its footnote's universe; the emigrants by `ByOrigin`.
- MI06 the migrants 5+ (in 1995 in another state or country) by `CAUEMI`; «salud, violencia e
  inseguridad» = codes 6 + 7.
- MI07–12 the international migrants: **movement** by `MPAIRES_C` (700 «México» = returned,
  999 not specified, any country or 600 = still abroad), age at emigrating `MEDAD` (999 NE),
  destination `MPDESOTR_C` (221 the United States, 999 NE, the rest of the world), the state
  left `MLUGORI_C` (999 → 99). C2KMI13 (each state's share of each destination) is MI12's
  counts over national totals: not compared. MI09's share of the resident population needs
  the person file: not compared.

## The data

**INEGI's tabulados, every state, both sexes and the nation** (`scripts/check_cpv_tabulados.py`,
`TABULADOS_REPORT.md`): **53,469 cells** (31,116 before), none beyond tolerance; the earlier
checks unchanged. The 22,353 new cells:

**EIC 2015, 15,283 cells in persons (dwellings or occupants): every one exact** — the largest
|Δ| is 1.3·10⁻⁷ of a person (floating point), in every state and the nation: 14-02 (classes
and their occupants), 14-04/06/08 (floors, roofs, walls), 14-09/10 (rooms and bedrooms by
occupants), 14-11 (cooking place by fuel), 14-12 (the stove, national), 14-17 (acquisition by
rooms), 14-20/34 (water: dwellings, occupants), 14-36/22 (the piped water's source by where:
dwellings, occupants), 14-38/24 (drainage: dwellings, occupants), 14-26/27 (electricity,
bulbs), 14-28 (sanitary), 14-29/30/31 (waste, separation, reuse), 14-32/33 (12 goods, 8
equipment items). The 2015 FD's codes and the `CLAVIVP` 7–9 universe hold for all of them.

**CGPV 2000, 7,070 cells in points** (tolerance 0.04, Chiapas 0.6):

| check | cells | median \|Δ\| | max \|Δ\| outside Chiapas (where) | Chiapas |
|---|---|---|---|---|
| EM02 inactive by kind | 495 | 0.003 | 0.013 (Guanajuato, home duties) | 0.163 |
| EM03 participation rates by age | 1,287 | 0.002 | 0.007 (nation, women 60–64) | 0.109 |
| EM04 occupation (CMO groups) | 1,881 | 0.003 | 0.037 (Oaxaca, women agricultural workers) | 0.556 |
| EM06 position at work | 594 | 0.003 | 0.014 (Hidalgo, employees) | 0.135 |
| EM09 benefits of the wage earners | 594 | 0.003 | 0.006 | 0.055 |
| EM11 TDA, TOPD2, TIID | 297 | 0.003 | 0.009 | 0.139 |
| MI02 lifetime immigrants and emigrants | 198 | 0.003 | 0.024 (Tabasco, men's emigrants) | 0.044 |
| MI05 immigrants and emigrants since 1995 | 198 | 0.003 | 0.011 | 0.019 |
| MI06 migrants by cause | 792 | 0.003 | 0.019 (Mexico City, not specified) | 0.209 |
| MI07 international migrants: movement by age (nation) | 117 | 0.002 | 0.021 | — |
| MI08 international migrants: age by movement (nation) | 144 | 0.003 | 0.027 | — |
| MI09 international migrants by movement (state of residence) | 99 | 0.003 | 0.009 | 0.091 |
| MI10 international migrants by sex (state left) | 68 | 0.002 | 0.013 | 0.312 |
| MI11 international migrants by age (state left) | 204 | 0.003 | 0.015 (nation) | **0.683** |
| MI12 international migrants by destination (state left) | 102 | 0.003 | 0.009 | 0.169 |

- **MI11's Chiapas** (15–24, 0.683 > its 0.6): 1,139 emigrant records left Chiapas (9,928
  weighted); the unweighted share is 57.42, the weighted 53.75, INEGI's 54.43 — the weights,
  as in Chiapas's other 2000 cells (EM04 0.556, EM05 0.508). `Check.tolerance` {7: 0.7},
  documented in the report.
- The unspecified origin (state 99: «NO ESPECIFICADO» in C2KMI10–12) is compared too.
- The migrants file's Σ `FACTOR` = 1,632,790 (INEGI's 1,633,052): emigrants 1,235,267
  (1,235,477), returned 284,806 (284,834), not specified 112,717 (112,741).

The report takes 24 min for every edition and state on the Mac (each workbook read once).

## Tests

- `test_c2k_sectors_total_and_sex_columns`, `test_c2k_states_and_national_blocks`,
  `test_tokens_keep_numbers`, `test_part_by_origin`, `test_sums_migrants_by_sex` (offline).
- `test_checks_are_consistent`: `migrantes` and `by_origin` are 2000's only.
- `test_state_01_within_tolerance`: 646 more state-01 cells (2000 183, 2015 463; 1,588 in all).

Full suite on the Mac: **1894 passed, 1 skipped** (32 min; 7c's 1889 + the five new tests). The 32-state report ran on the same code.

## Left out

- EIC 2015 14-14 (the owners by sex and order) and 14-15/16 by the owner's sex: the owner is
  a person row (`NUM_DUE_VIV1`/`2`), so the check needs the person file joined to the
  dwelling; the tabulados by locality size (14-01, 03, 05…) repeat the state ones.
- C2KMI13 and MI09's share of the resident population (above).
