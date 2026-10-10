# CPV Unit 6w — indigenous households; media superior and superior apart

Done **2026-10-09** (on the Mac; HANDOFF candidates 2 and 1, one unit, agreed with the user
after 6v). Gate: a person column for the population in indigenous households in every
edition with a household and a language item, matching each edition's publication; 2000's
media superior and superior as constraints; every edition's 32 states derive; tests green.

## The gaps

- **Indigenous households.** The 2005, 2010 and 2020 ITER publish the population in
  indigenous households (2005 `P_HOG_IND`, renamed `PHOG_IND`), and the EIC 2025 estimates
  publish both `PHOG_IND` and the households (`HOG_IND`). No person item says whether the
  person's household is indigenous: it depends on the language of other members.
- **Media superior and superior.** CGPV 2000's ITER splits the 18+ beyond básica into
  `P18_CMEDSU` (media superior) and `P18_CSUPER` (superior); `EDUC_INEGI` merges them into
  «Posbásica». The EIC 2015 and Censo 2020 tabulados and the EIC 2025 estimates split them
  too (the 2025 estimates also split off the posgrado).

## Each edition's own definition (verified)

INEGI changed who counts between editions, and its dictionaries' wording does not match
its numbers. A household is indigenous when one of these members speaks an indigenous
language:

| edition | members | evidence |
|---|---|---|
| CGPV 2000 | head, partner | no publication (no ITER indicator, no household tabulado); the definition of its era |
| Conteo 2005 | head, partner | its ITER dictionary; the unweighted sample: median \|Δ\| 0.045 points by state (with the ascendants 0.098) |
| Censo 2010 | head, partner | exact in the **364** municipalities its sample enumerated completely (`FACTOR` 1) whose population in households equals the ITER's; head only: 293 off, + parents 128, + parents-in-law 77, + both 139 |
| EIC 2015 | head, partner | its tabulado 05-04 («hogares cuyo jefe o jefa y/o cónyuge habla lengua indígena»): exact in every state |
| Censo 2020 | head, partner, mother or father (401), parent-in-law (416) | exact in the **184** completely enumerated municipalities with the ITER's `POBHOG`; head and partner only: 76 off; + step-parents 1; + grandparents 23; 2025's set 24 |
| EIC 2025 | head, partner, mother or father, step-parent (402), grandparent (406), great- or great-great-grandparent (407), parent-in-law | exact in all **2,478** municipalities (`PHOG_IND` and `HOG_IND`); 2020's set: 440 off; without 407: 11; spouse 201 without 202 (concubina): 40; + co-parents-in-law (417): 18 |

The 2020 ITER dictionary says «la persona de referencia del hogar o su cónyuge o alguno de
los ascendientes de estos» (grandparents would break it). The EIC 2025 dictionary names
«madre o padre, suegra(o)» only, but the step-parents and grandparents are needed. The
partner codes 203 (2020/2025 «amante») and 202–204 (2005) are kept with the partner: the
data cannot tell, and the head's spouse group is INEGI's «cónyuge». A first, weighted
state-level test of the 2020 definitions was inconclusive, even misleading (the sample's
indigenous-household population runs 4.5% over the ITER's nationally, its speakers 2.1%,
so the head-or-partner rule looked closer); the completely enumerated municipalities
settled it.

## The user's choices

- **Each edition's own definition** in one column (over a second, comparable
  head-or-partner column, or a column graded by the speaking relative), so `PHOG_IND`
  matches every edition's publication.
- **Persons only**: no dwelling column, so the EIC 2025's `HOG_IND` is checked in the tests
  (through the household heads, exact in every municipality) but not offered as a
  constraint.
- **A new full-scale column** (over a small posbásica column or changing `EDUC_INEGI`),
  **posgrado apart** (as the EIC 2025 estimates; 2000's superior = superior + posgrado).
- **Names**: `HOG_IND` and `EDUC_INEGI_DET`.
- Stated by me before implementing (no objection): since 2005/2010's `PHOG_IND` counts
  fewer relatives than 2020's, the crosswalk marks it `Comparable: false` (as 6o did for
  `PDER_SEGP`), and the 2005/2010 cells come in as each edition's own cells.

## What changed

- `cpv_derived`:
  - `_IND_CODES`: the relationship codes per edition (2000 `OTROPARE_C` 100/200; 2005
    `PARENT` 101/102/201–204; 2010/2015 `PARENT` 1/2; 2020 `PARENTESCO` 101/201–203/401/416;
    2025 + 402/406/407). `_hog_ind(members)`: «Sí» when a member listed speaks (`HLENGUA` 1),
    else «No» (no, not specified or not asked); a household with a language code other than
    1/3/9 is left missing, so `derive` raises. One derivation per set of codes,
    `household=True` (6t's grouping: `ID_HOG` in 2000/2005, the dwelling from 2010).
  - `HLENGUA` sources: `_ALIASES` `HABLENIN` (2005); `_RECODE` 2000/2005 2 → 3 (no).
  - `_SI_NO` (Sí/No) for `HOG_IND`; `_EDUC_INEGI_DET` (ordered: `EDUC_INEGI`'s categories with
    «Posbásica» replaced by «Media_superior», «Superior», «Posgrado»).
  - `_educ` adds `EDUC_INEGI_DET` from the 2020 level (`_POSBASICA`): media superior =
    bachillerato general or tecnológico (4, 5), técnica after secundaria (7), normal básica
    (9); superior = técnica after preparatoria (8), normal de licenciatura (10),
    licenciatura (11); posgrado = 12–14. Every edition's own education function ends in
    `_educ`, so 1990–2025 all get it (`_EDUC` = three columns).
  - `_CELLS["personas"]["PHOG_IND"]` = `{HOG_IND: [Sí]}`; `_EDITION_CELLS` 2005/2010 carry the
    same cell (their indicator is not comparable); 2000 `P18_CMEDSU` = 18+ ×
    `Media_superior`, `P18_CSUPER` = 18+ × `Superior` + `Posgrado`.
- `build_cpv._XW_NOT_COMPARABLE` += `PHOG_IND` and its `_XW_NOTES` entry states the
  definitions; `cpv_iter_crosswalk.yaml` regenerated (only `PHOG_IND` changed).
- Person constraints: 2000 63 → **65**, 2005 86 → **87**, 2010 146 → **147**, 2020 160 →
  **161** (the legacy 157 + 4), 2025 28 → **29**. 1990, 1995, 2015 unchanged.
- `scripts/check_cpv_tabulados.py`: CGPV 2000 ED10/ED11 and EIC 2015 06-11 compare media
  superior and superior apart (on `EDUC_INEGI_DET`; ED11's media superior = its columns
  D–F, técnica after secundaria, preparatoria, normal básica); new EIC 2015 **05-04** (the
  population aged 0–2 in households whose head or partner speaks, `HOG_IND`; its
  estimators in columns, `_indigenous_children_published`) and Censo 2020 **07-04** (the
  18+ with educación superior, posgrado included). Sources += `05_etnicidad.xls`,
  `cpv2020_a_eum_07_educacion.xlsx`.
- Docs: the `cpv_derived` and `load_cpv_personas` docstrings, README, CLAUDE.md.

## The data (all 32 states, `load_cpv_personas(derived=True)`)

Every edition's 32 states derive without an unmapped code; `EDUC_INEGI_DET` collapses onto
`EDUC_INEGI` exactly in every row.

**Indigenous households.**

- EIC 2025: `PHOG_IND` and `HOG_IND` (Σ `FACTOR` of the heads) exact in all 32 states and
  the 2,422 municipalities with a published value (the other 56 publish «No aplica»; the
  sample has no indigenous household there).
- Censo 2010 and 2020, completely enumerated municipalities (767 and 220): exact wherever
  the population in households is (364 and 184); elsewhere off by no more than the
  population in households is (residents counted without characteristics).
- Against the ITER by state (share of the household population, sample − ITER, points):

| edition | median \|Δ\| | 90th pct. | max \|Δ\| | nation (sample / ITER) |
|---|---|---|---|---|
| Conteo 2005 (unweighted) | 0.045 | 0.34 | 1.34 (Quintana Roo) | 9.49 / 9.51 |
| Censo 2010 | 0.22 | 0.75 | 2.08 (Quintana Roo) | 9.97 / 9.75 |
| Censo 2020 | 0.36 | 0.89 | 3.06 (Quintana Roo) | 9.83 / 9.40 |

  The 2010/2020 gaps are the samples', not the definition's (which is exact wherever the
  sample is the census, above): nationally the 2020 sample counts 2.1% more speakers aged
  3+ than the ITER and 4.5% more persons in indigenous households (Quintana Roo 11% and
  13%); the 2010 sample 1.1% and 3.4%. The weights are calibrated on population totals,
  not on language, so the larger indigenous households sit further off than the speakers.
- EIC 2015: the tabulado 05-04 — see below.

**Media superior and superior.**

- EIC 2025: the five levels of the estimates (`PCN_P15YM_SE` sin instrucción, `_EB`
  básica — técnica after primaria included —, `_EMS`, `_ES`, `_POS`) equal ours within
  their 2-decimal rounding (≤ 0.005) in all 32 states and 2,471 municipalities.
- CGPV 2000 against its ITER, the share of the 18+: `P18_CMEDSU` median |Δ| 0.16 points,
  90th percentile 0.43, max 1.62 (Campeche); `P18_CSUPER` 0.22 / 0.56 / 0.61 (Quintana Roo).
  The nation's counts run 1.6% and 1.8% above the ITER's: the 2000 weights add up above
  the population in households (6v). The sample tabulados ED10/ED11 agree within the 2000
  tolerance (below), so the gap to the ITER is the sample's.
- Upper levels, % of each edition's persons: media superior 8.8 (1990) → 20.3 (2025),
  superior 4.7 → 17.3, posgrado 0.4 → 1.9.

**Against INEGI's sample tabulados** (`TABULADOS_REPORT.md`, now 21,843 cells, none beyond
tolerance):

- EIC 2015 05-04 (the population aged 0–2 in households whose head or partner speaks):
  exact to the person in every state and the nation (33 cells).
- EIC 2015 06-11, with media superior and superior apart: exact (792 cells).
- Censo 2020 07-04 (the 18+ with educación superior, posgrado included): exact in every
  state, sex and the nation (99 cells).
- CGPV 2000 ED10/ED11, with the split: median |Δ| 0.003 points, the worst 0.094 (Chiapas,
  within its 0.6), every other state within 0.04. The rest of the report is unchanged.

## Tests

- `test_derive_hog_ind` (offline): each edition's definition — a speaking grandparent makes
  a 2025 household indigenous, not a 2020 one; a parent-in-law a 2020 one; a 2015 mother
  or a 2005 parent does not; a 2005 «querido(a)» partner does; a child never does —, the
  dtype, 1990/1995 without it, an unknown language code raises.
- `test_educ_inegi_det` (offline): the level map, the collapse onto `EDUC_INEGI`, and the
  2000/1990/1995 items (técnica after preparatoria, normal básica, posgrado).
- `test_source_codes_match_2020`: the `HLENGUA`/`HABLENIN` codes after the recode = 2020's;
  the relationship codes of `_IND_CODES` are in each dictionary and labelled as partners,
  parents, step-parents, grandparents or parents-in-law.
- `test_cpv_derivations_listing`, `test_cpv_constraints_per_edition` (the new cells, the
  crosswalk flag, the counts), `test_eic2025_constraints_equal_estimates` (28 → 29 cells),
  `test_6n_cells_equal_iter` (2000 33 cells, 2005 46, 2010 12).
- Real: `test_hog_ind_equals_published` — EIC 2025 state 01 every municipality, Censo 2010
  and 2020 Sonora's completely enumerated municipalities (34 and 5) exactly.
- `tests/test_cpv_tabulados.py`: state 01 compares 661 cells (+13).
- `tests/test_cpv_aggregates.py::test_crosswalk_covers_every_column_once`: the crosswalk's
  not-comparable set gains `PHOG_IND`.
- **Full suite**: 1817 passed, 1 skipped, 1 failed (30 min on the Mac's full mirror; the
  failure was the crosswalk test above, which pinned the old set — fixed and rerun: passed).

## Left out

- A dwelling-level `HOG_IND` (the EIC 2025's `HOG_IND` as a dwelling constraint; the user
  chose persons only). It would come from the person file, as 6s's `JEFE_SEXO`.
- CGPV 1990's `HAB_IND` (no household number, 6t) and the Conteo 1995 (no language item).
- CGPV 2000's `HOG_IND` follows the head-or-partner rule of 2005–2015 without a
  publication to check it against.
