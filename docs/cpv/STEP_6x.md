# CPV Unit 6x — the indigenous households on their dwellings

Done **2026-10-10** (on the Mac; HANDOFF candidate 2 after 6w, agreed with the user). Gate:
each edition's household records carry their household's `HOG_IND` (6w's definition),
equal to their persons' in every state; the EIC 2025's `HOG_IND` estimate is a dwelling
constraint, equal to the estimates in every municipality; tests green.

## The gap

6w put `HOG_IND` («Sí»/«No»: the household is indigenous by the edition's own definition) on
the persons only, at the user's choice. The EIC 2025 estimates also publish the households
(`HOG_IND`), which 6w checked through the household heads (Σ `FACTOR` of the heads in
indigenous households, exact in every municipality) but did not offer as a constraint: the
dwelling frame had no such column. It depends on the language of the household's members,
which only the person file has.

## The user's choices

- **Which frames**: every edition's household records with a person `HOG_IND`. These are
  the dwellings of CGPV 2000 (one row per household) and 2010–2025 (one household per
  dwelling), and the Conteo 2005's households (`load_cpv_hogares`). The 2005 dwelling
  frame does not get it: its rows are dwellings, some with several households (6v moved
  that edition's household indicators to its household table for the same reason).
- **The name**: `HOG_IND` on both frames (the same attribute; the EIC 2025's indicator for
  households), not a distinct dwelling name as in 6t's `JEFE_SEXO`/`HOGJEF_SEXO`. A person
  ↔ dwelling join needs a suffix for it.

## Design: a derivation over the household's members

6s brought the head's raw `SEXO` onto the dwelling as a helper column, read by an ordinary
dwelling derivation. `HOG_IND` depends on several members, so it does not fit one helper
column per dwelling. Instead a derivation may declare **`members=True`**:

- its sources are **person** items (`PARENTESCO`, `HLENGUA`), read from `derive`'s new
  `members` argument (the person rows of the frame's households) with the same aliases
  and `_RECODE` as on the persons;
- its function is the person derivation's own (`_hog_ind(_IND_CODES[period])`, with
  `household=True`), so the dwelling and the person columns follow one rule;
- each record then takes its household's value (`_per_record`): matched on the entity and
  `ID_HOG` (2000, 2005) or `ID_VIV` (2010–2025) through `_household_keys`, with zero
  padding ignored (the 2015 CSVs drop it, harmonized frames restore it);
- a frame with such a column and no `members`, or a record whose household has no
  member, raises; an unknown language code among the members raises as on the persons.

The registry holds one such derivation per set of codes (`_periods_by(_IND_CODES)`), on
`viviendas` or, for the Conteo 2005, on `hogares` (`_household_records`, `_HOUSEHOLD_TABLE`).
`cpv_derivations` lists them with the person items as sources; `_member_sources(table,
period)` names the items a frame's members must carry.

## What changed

- `cpv_derived`:
  - `_Derivation.members`; the `HOG_IND` derivations on `viviendas` (2000, 2010, 2015,
    2020, 2025) and `hogares` (2005).
  - `_household_keys` (split out of `_household`), `_per_record`, `_member_sources`.
  - `derive(df, table, period, members=None)`: a cache per frame (the frame, the members).
  - `_CELLS["viviendas"]["HOG_IND"] = {HOG_IND: [Sí]}`: kept where an edition publishes
    `HOG_IND`, the EIC 2025 only (the ITERs publish `PHOG_IND`, the population, not the
    households). `_HOUSEHOLD_INDICATORS` += `HOG_IND` (the 2005 ITER has none, so no
    household cell appears).
- `cpv`:
  - `_person_columns(period, state, harmonize, items)`: the column-projected person read
    that 6s's `_attach_heads` did inline, now shared. Each item takes the first alias the
    file has (Censo 2010's file has both `PARENT` and `OTROPARE_C`; `derive` reads `PARENT`
    there too), the key parts come from `_HOUSEHOLD_PARTS` (2000/2005 composite parts, else
    the entity — `ENT`, or the EIC 2025's `CVE_ENT` — and `ID_VIV`), and the keys are built
    as before (composite keys, Censo 2010's national `ID_VIV` under `harmonize`).
  - `_HEAD_FROM_PERSONS` = (relationship item, head codes); its key parts moved to
    `_HOUSEHOLD_PARTS`.
  - `_household_members(period, state, harmonize, sources)`; `_load_level` reads the
    members when the frame has a `members=True` derivation and passes them to `derive`.
- Derived columns: `HOG_IND` on the dwellings of 2000, 2010, 2015, 2020, 2025 and the
  households of 2005. Constraints: EIC 2025 dwellings 3 → **4** (`HOG_IND`); no other
  edition changes.
- Docs: the `cpv_derived`, `cpv_constraints`, `load_cpv_viviendas`/`load_cpv_hogares`/
  `load_cpv_survey` docstrings, README, CLAUDE.md.

## The data (all 32 states)

`load_cpv_viviendas(derived=True)` (2005: `load_cpv_hogares`) for every edition, all 32
states, raw and `harmonize=True` (384 loads, on the local mirror): no unmapped code, no
record without members, and every record's `HOG_IND` equals its persons' (the person frame's
`HOG_IND` is constant within each household and there is one per record).

| edition | household records | indigenous (unweighted) | weighted share by state: min / median / max |
|---|---|---|---|
| CGPV 2000 (household rows) | 2,312,035 | 327,819 | 0.25 / 4.76 / 54.47 % (Yucatán) |
| Conteo 2005 (households, unweighted) | 2,546,879 | 208,492 | 0.39 / 3.88 / 47.94 % (Yucatán) |
| Censo 2010 | 2,903,640 | 682,486 | 0.37 / 3.95 / 46.07 % (Yucatán) |
| EIC 2015 | 5,854,392 | 1,110,452 | 0.40 / 4.21 / 44.57 % (Yucatán) |
| Censo 2020 | 4,016,627 | 903,006 | 0.36 / 3.93 / 41.43 % (Oaxaca) |
| EIC 2025 | 7,340,046 | 1,316,466 | 0.35 / 3.81 / 38.38 % (Oaxaca) |

**EIC 2025 against its estimates**: Σ `FACTOR` of the indigenous dwellings equals the
published `HOG_IND` in all **2,422** municipalities with a value (and in every state, through
the constraint test). The other 56 publish «No aplica», and the sample has no indigenous
dwelling there (6w's note: the estimates write NA for a zero). Multi-state loads (states 1
and 2: 2000, 2025 raw; 2010, 2015 harmonized) equal the single-state ones.

The other editions have no published household count to check against (§Left out); their
persons' `HOG_IND` is 6w's, checked there against each edition's publication.

## Tests

- `test_derive_hog_ind_households` (offline): a speaking grandparent makes a 2025 dwelling
  indigenous, not a 2020 one; a parent-in-law a 2020 one; the 2015 members' unpadded keys
  match a padded dwelling; Censo 2010's serials repeat across entities; 2000's household
  rows; the 2005 households; no `HOG_IND` on the 2005, 1990 and 1995 dwellings; the errors
  (no members, a record without members, an unknown language code, a missing item).
- `test_household_members` (offline, synthetic files): the edition's item names (2010
  `PARENT` beside `OTROPARE_C`, 2005 `HABLENIN`), the EIC 2025's `CVE_ENT`, 2010's national
  keys under `harmonize`, the 2005 composite keys.
- `test_load_hogares_derived`: the Conteo 2005's households get `HOG_IND` over their own
  members (raw and harmonized).
- `_derive_dwellings` (a test helper): the synthetic dwelling frames of 6n/6s now carry
  keys and one non-speaking head each as members.
- `test_source_codes_match_2020`: the members' items are checked against 2020's person
  items (`_BORROWED` now names the reference table too).
- `test_cpv_derivations_listing`, `test_cpv_constraints_per_edition` (the EIC 2025's
  `HOG_IND`; none in 2000/2010/2020), `test_eic2025_constraints_equal_estimates` (dwellings
  3 → 4 cells), `test_hog_ind_equals_published` (EIC 2025 state 01: the dwellings' own
  `HOG_IND` by municipality).
- **Full suite**: 1830 passed, 1 skipped (31 min on the Mac's full mirror; 6w's 1817 + 13).

## Left out

- The Conteo 2005's dwelling frame (its rows are dwellings; the household frame has it).
- A dwelling-level check outside the EIC 2025: no other edition publishes the number of
  indigenous households (the ITERs publish `PHOG_IND`, the population; the EIC 2015
  tabulados the population aged 0–2), so the other editions are checked against their
  persons' `HOG_IND`, which 6w checked against the publications.
