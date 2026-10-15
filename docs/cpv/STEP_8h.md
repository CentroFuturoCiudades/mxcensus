# CPV Unit 8h — the CPV user guide

Done **2026-10-14** (on the Mac). HANDOFF candidate 4's first idea, the user's choice
(«release, then the guide»): the 0.15.0 release (7v–8g, `STEP_8g.md` §Release) first, then
this unit in the same session. Gate: `docs/cpv/GUIDE.md` written, every example run against
the mirror with its real output quoted, a test that runs them (and rebuilds the guide's
generated tables) green, the README's CPV section cut to an overview that links it, tests
green. No loader, derivation, dictionary or data changed.

## Decisions (user, 2026-10-14)

| question | decision |
|---|---|
| where and in what form | **`docs/cpv/GUIDE.md`**, one Markdown file linked from the README (recommended; over a notebook in `notebooks/` or both) |
| the README's long CPV section | **trimmed to an overview + link** (recommended; over keeping it and adding a link), with its stale bits fixed |
| keeping the examples true | **run once against the mirror, outputs quoted, and a `_REAL` test that runs them** (recommended; over running them once by hand) |

Taken without asking: the examples as doctests (`pycon` blocks, `>>>` with the output under
it) so the test checks the quoted outputs and not only that the code runs; state 1
(Aguascalientes: every edition's files are small and on disk), Quintana Roo for the
municipal units (Tulum, Bacalar, Puerto Morelos between 2000 and 2020); the two tables that
go stale fastest — the derived columns by edition, the constraints by edition — generated
between `<!-- … -->` markers and rebuilt by an offline test; the 0/1 terms of the count
constraints as a seven-line `design()` helper in the guide, not a new public function (the
unit changes docs only; see §Left).

## The guide (`docs/cpv/GUIDE.md`)

Ten sections, written for a user of the package rather than a maintainer:

1. **What is in the family**: editions × tables, weights, frames.
2. **Microdata**: `load_cpv` (raw strings) vs the labelled loaders; keys and the survey
   tuple, the keys of every edition (a table); several states (Censo 2010's state-scoped
   keys refused, then national with `harmonize=True` — the error quoted); harmonizing and
   stacking editions (2010–2025 by sex), what is comparable as is and what only through the
   derived columns; the dictionaries and schema groups.
3. **Derived columns**: the 2000 education by `EDUC_INEGI`, `cpv_derivations`, the
   matrix of the derived columns (62 rows, a set of dummies one row) × 8 editions, the legacy rule
   beside INEGI's (education, disability, places, 2010 religion), the two renamed
   health-coverage dummies, the columns read from another file.
4. **Published aggregates**: the ITER by level (2020; 1990 by municipality on the 2020
   names), reserved cells and imputation, the crosswalk, AGEB and `load_cpv_census`; the
   EIC 2025 estimates, estimators and `counts=True`.
5. **Constraints**: `cpv_constraints`, the table of constraints by edition, a worked
   comparison of the EIC 2025 sample with its municipal estimates (37 published counts
   exact, the counts behind percentages within 0.0001 of the share), which total to fit
   (`POBTOT`, `POBHOG`, `OCUPVIVPAR` by edition), ratio constraints (`GRAPROES`,
   `PROM_HNV`, `PCN_HF` = the estimates), the 2000/2005/2025 specifics.
6. **Geography across editions**: `load_mg` and the join with the estimates; the
   municipal units (Quintana Roo 2000 → 2020); the locality lineage and units
   (Aguascalientes city 2000 → 2020).
7. **Localities 1900–2020**: `load_ahl_poblacion` (the city and the state 1900–2020).
8. **Edition notes**: one paragraph per edition, the pitfalls a user meets.
9. **How the data were checked**: the six reports.
10. **Function index**.

75 examples; they read 18 files (state 1 of every edition, Quintana Roo's 2000/2020 ITER, the
estimates, the MG 2025 municipalities, two AHL tables) and run in ~20 s.

## Found while writing it

- The README said the MG 2025 municipalities join the EIC 2025 estimates «on `CVEGEO`»:
  the estimates' `CVEGEO` has nine characters (entity, municipality, locality), the
  layer's five. The guide joins on `CVE_ENT`/`CVE_MUN`; the README says so.
- The README's dictionary examples named the CPV person groups of unit 3a (`g05` = EIC
  2025); since 5b they are `g09` (2025), `g08` (2020), `g07` (2015) … `g01` (1990). Its
  install pin was `@v0.1.0`; now `@v0.15.0`.
- The Conteo 1995's ITER has no rows for 15 municipalities of Chiapas (`STEP_5b.md`): not
  in the README, now in the guide's edition notes. The 1990 → 1995 municipalities: 25 codes
  the 1995 ITER has and 1990's lacks (16 in Tlaxcala, 2 in Aguascalientes…), outside the
  lineage (1990 has no frame).
- CGPV 2000 has no `DHSERSAL_SALUD_PUBLICA`, `DHSERSAL_Privado` or `DHSERSAL_ISSSTE_E`
  (one question per institution); 2000–2015 no `DHSERSAL_IMSS_BIENESTAR`.

## The README

The CPV section (320 lines: the edition table, then every unit's prose from 1c to 8e) is now
an overview of 48: the edition table, one code block (survey, older editions, raw, ITER,
estimates, constraints, locality units), one paragraph on what the family does and a link
to the guide, which holds the detail. The ¹ footnote on 1995's weights, the derived
columns' prose, the constraints' and the lineage's moved into the guide's sections 3, 5, 6
and 8. Other families untouched.

## Tests (`tests/test_cpv_guide.py`, new, 4 tests)

- `test_derived_matrix_is_current`, `test_constraint_counts_are_current` (offline):
  `derived_matrix()`/`constraint_counts()` rebuild the two tables from
  `cpv_derivations`/`cpv_constraints`/`cpv_ratio_constraints` and compare them with the
  guide's sections; a new derived column or constraint fails until the guide is updated
  (paste the function's output between the markers).
- `test_guide_blocks_parse` (offline): every `pycon` block holds doctest examples and every
  linked report exists.
- `test_guide_examples` (`_REAL`: the 18 files in `data/parquet`): the examples as one
  doctest over the guide with every other line blank (a failure reports the guide's own
  line), `POOCH.fetch` on `data/parquet`, `ELLIPSIS | NORMALIZE_WHITESPACE`, pandas display
  width 88 / 20 columns (`_OPTIONS`, the options the outputs were printed with). A wrong
  output fails (checked by hand: `len(cons)` 215 → «Expected 215, Got 214», line 433).
- Full suite: the Mac's on 8g, **1976 passed, 1 skipped** (`STEP_8g.md` §Release), and the
  4 new tests run apart, **4 passed** (20 s); 8h changes no code the suite runs.

Updating the guide after a change: edit the example, then rerun the examples and paste the
new output (the session's helper ran each `pycon` block and rewrote its outputs; doctest's
report gives the same outputs one by one).

## Left

- **A public `cpv_constraint_terms(frame, constraints)`**, the count constraints' sibling
  of `cpv_ratio_terms` (each record's 0/1 term; the guide's `design()` helper): a candidate
  for a later unit.
- A notebook running the guide's examples with plots (the user chose Markdown only).
- The cross-edition ITER panel on the stable units (HANDOFF candidate 4's second idea): the
  guide's §6 shows the recipe for one state; a loader would do it for every indicator the
  crosswalk pairs.
