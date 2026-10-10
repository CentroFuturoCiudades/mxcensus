# CPV Unit 7a — the EIC 2025's person percentages

Done **2026-10-10** (on the Mac; HANDOFF candidate 2, the persons' 127 percentages that 6z
left, all in one session at the user's choice; the first unit after 6z). Gate: every
person percentage of the EIC 2025 estimates whose base the estimates give becomes a count
(`load_cpv_estimaciones(counts=True)`) and a constraint, each equal to the estimates at
every published geography; tests green.

## The gap

After 6z the estimates had 127 person percentages without a cell, and three published
counts without one (`HOG_AFRO`, `PHOG_AFRO`, `PUSU_SS`):

- 5-year age groups by sex (48);
- birthplace abroad by nationality (2), residence in October 2020 (6);
- indigenous self-identification (3) and understanding a language (1);
- disability by sex (2) and by age (4);
- attendance (4), education levels (4), position at work (4);
- health: affiliated or with recognised access, affiliated to a public centre, users of
  each service (10);
- the students' commute: place, time, mode (15); the employed's: place, time, mode (16);
- marital status by sex (7);
- `PCN_HF`, the share of the children born alive who died.

## The user's choices

- **The unit**: all 127 in one session (not split into two).
- **The new columns, as proposed**: `EDAD_QUIN` (every edition), `LUGAR_RES_5A`,
  `ENT_PAIS_ASI_INEGI`/`ENT_PAIS_TRAB_INEGI`, the summary dummies
  `MED_TRASLADO_{ESC,TRAB}_{METRO,BUS,TAXI}_T` (2020 and 2025, which share the codes),
  `DHSERSAL_AFIL_ACCESO` (2025).
- **The employed's nine commute modes are left out**: their base, the employed who
  commute, includes «no es posible determinarlo» (5.9% of them), which nothing published
  gives. The grouped work-mode dummies are still derived.
- **The disability by age takes `PCON_DISC` as its base** (an approximation: below).
- **`HOG_AFRO` for the EIC 2025 only** (no other edition publishes such a count).
- Not asked, by the same rule as the work modes (a base the estimates do not give, and
  not negligible): `PCN_P3NHLI_CLI` is left out (below).

## Finding each percentage's base

As in 6y/6z: Σ `FACTOR` over the indicator's cells ÷ Σ `FACTOR` over each candidate base's,
at all 2,769 geographies with a published value, against the published percentage. Every
one matched within its rounding (≤ 0.005) with these bases and rules:

| percentages | base | rule |
|---|---|---|
| `PCN_P_0A4` … `PCN_P_75YMAS`, `_F`, `_M` (48) | the population of **specified** age = `POB0_14` + `POB15_64` + `POB65_MAS` (published) | the women's and men's groups too (a population pyramid, not shares of each sex) |
| `PCN_PNACOP_NAC`, `_NONAC` | `PNACOP` | `NACIONALIDAD` 1 / 3 |
| `PCN_PRESM20`, `PRESOM20`, `PRESE20`, `PRESOE20`, `PRESEUA20`, `PRESOP20` | `P_5YMAS` | same municipality = the own entity and `MUN_RES_5A` = the person's; «same entity» also holds municipality 999, which neither municipality indicator does; another entity without 997; the United States = 221; another country with 998 |
| `PCN_POB_IND`, `_F`, `_M` | `POBTOT`, `POBFEM`, `POBMAS` | `PERTE_INDIGENA` 1 |
| `PCN_PCON_DISC_F`, `_M` | `PCON_DISC` | |
| `PCN_PCON_DISC0A14`, `15A29`, `30A59`, `60YM` | the disabled of specified age (**not published**: `PCON_DISC` taken) | |
| `PCN_P3YM_ASIS` | `P_3YMAS` | |
| `PCN_P6A14_NOA`, `_F`, `_M` | `P_6A14`, `_F`, `_M` | `ASISTEN` 3 |
| `PCN_P15YM_EB`, `EMS`, `ES`, `POS` | `P_15YMAS` | `EDUC_INEGI_DET`: básica = primaria (incomplete, complete, técnica after it) and secundaria |
| `PCN_POCUP_ASA`, `EMP`, `CPRO`, `SPAG` | `POCUPADA` | `SITTRA` 1–3 (employee, day labourer, paid helper) / 4 / 5 / 6 |
| `PCN_PcSSyRecAc` | `POBTOT` | affiliated to any institution (private too) **or** `DHSERSAL_ACCESO` 1 (asked of the not affiliated) |
| `PCN_PAFIL_IPUB` | `PDER_SS` | `DHSERSAL` 06 (2025's code: a public centre, hospital or institute) |
| `PCN_PUSU_*` (8) | `PUSU_SS` (published) = `SERSALUD` 01–09 | `ISTE` = 02 and 03 (federal or state); not 10 «no se atiende», 99 |
| `PCN_PASIS_ENT`, `OENT`, `15MIN`, `30MIN`, `1HOR`, `1HYM` | `P3YM_ASIS` (derived) | `OENT` = another entity, a country or 998; 997/999 in neither; `1HYM` = 4 and 5 |
| `PCN_PASIS_CAM` … `OMED` (9) | the students who commute = `PASIS_15MIN` + `30MIN` + `1HOR` + `1HYM` | any of the three mode items; `MET` = 03 or 05, `TROL` = 04 or 06, `TAXI` = 08 or 09; every student asked a mode says how long (no blank time) |
| `PCN_POCUP_ENT`, `OENT`, `15MIN` … `2HYM` | `POCUPADA` | `2HOR` = 4, `2HYM` = 5 |
| `PCN_P12YM_SOLT`, `CUL`, `SEPA` by sex | `P_12YMAS`, `_F`, `_M` | the legacy `SITUA_CONYUGAL_CAT`; `CUL` («casada o en unión libre») = «casado» |
| `HOG_AFRO`, `PHOG_AFRO` (published counts) | — | one of the 2025 indigenous household's members (head, partner, parents, step-parents, grandparents, parents-in-law: `_IND_CODES`) with `AFRODES` 1. Exact everywhere; head only (164 of 2,710 geographies), head or partner (1,707), 2020's set (2,610) and any member (186) miss |

**The probe's pitfall**: a person of unspecified age (999) can answer the marital status,
residence and commute items. INEGI's numerators keep the age universe, so a cell without
the age condition misses by a person here and there (the first probe did: 23 geographies
for the single women). Every cell keeps it.

`P_0A4` … are the only sum of **published** counts; the students' modes add four derived
counts. `_PERCENT_BASES` may now map a percentage to a tuple of counts (`_base_parts`), and
`_percent_counts` sums them.

## Left out (11)

- `PCN_HF`: dead children over the children born alive (a ratio of children, not of
  persons).
- `PCN_P3NHLI_CLI` (the 3+ who understand a language without speaking one): its base is
  the 3+ who answered «no» to speaking one (`HLENGUA` 3). `P_3YMAS` − `P3YM_HLI` also holds
  those who did not say: 303,176 persons nationally, 0.24% of the 3+ (0.08–0.58% by state),
  enough to move a small municipality's share by up to 13.8 points.
- The employed's nine modes (above).

## Disability by age

The disabled of unspecified age are 51 persons nationally (Σ `FACTOR`), in 21 of the 2,776
geographies. The four counts taken on `PCON_DISC` therefore run over by ≤ 28 persons (60+,
nationally, where INEGI's rounding alone allows 317). Their shares stray beyond the
rounding in 6, 10, 13 and 12 geographies (≤ 0.23 points, small municipalities). The test
reads the shares on the specified-age base, where they are exact.

## What changed

- `cpv_derived`:
  - new derived **`EDAD_QUIN`** (every edition, `_edad_quin`: `EDAD_CAT`'s binning,
    0-4 … 70-74, 75-130, «No especificado»; ordered);
  - new derived **`LUGAR_RES_5A`** (2020, 2025; `_lugar_res`: «Mismo municipio», «Otro
    municipio», «Municipio no especificado», «Otra entidad», «Estados Unidos», «Otro país»,
    «No especificado», «Blanco por pase»; the person's municipality through the new alias
    `MUN` = `MUN`/`CVE_MUN`; the own entity without a municipality raises);
  - new derived **`ENT_PAIS_ASI_INEGI`**, **`ENT_PAIS_TRAB_INEGI`** (2020, 2025;
    `_ent_pais_inegi`: the residence's labels, 997 «No especificado» as
    `ENT_PAIS_NAC_INEGI`; `_RECODE` 2025: the two renumbered countries);
  - new summary dummies **`MED_TRASLADO_{ESC,TRAB}_{METRO,BUS,TAXI}_T`** (2020, 2025;
    `_traslado_t`, `_TRASLADO_T`);
  - new dummy **`DHSERSAL_AFIL_ACCESO`** (2025, `_afil_acceso`);
  - new derived **`HOG_AFRO`** (2025; persons `household=True`, dwellings `members=True`,
    as `HOG_IND`: `_hog_flag` generalizes `_hog_ind`; `_AFRO_CODES`);
  - `_EDITION_CELLS`: `("personas", "2025")` += `_PERSONS_2025` (116 counts behind
    percentages, `PUSU_SS`, `PHOG_AFRO`; the totals `P12YM_SOLT`/`_SEPA` stay the legacy
    cells, identical), `("viviendas", "2025")` += `HOG_AFRO`.
- `cpv_aggregates._PERCENT_BASES`: 148 → **264**; a base may be a tuple (summed).
- Constraints: EIC 2025 persons 96 → **214**, dwellings 92 → **93**; no other edition
  changes.
- Docs: `cpv_derived`/`cpv_constraints`/`load_cpv_estimaciones` docstrings, README,
  CLAUDE.md.

## The data

**EIC 2025, all 32 states** (`load_cpv_personas`/`load_cpv_viviendas(2025, derived=True)`,
the actual `cpv_constraints` cells), at all 2,776 geographies of the estimates (the nation
from the 32 states): **all 307 constraints** reproduce the estimates — the 43 published
counts exactly, each of the 264 counts behind a percentage by its share of the base within
0.005 wherever the percentage is published (2,644–2,776 geographies for the new ones; the
disability by age on the specified-age base). The reconstruction (percentage × base / 100)
is off our Σ `FACTOR` by INEGI's rounding: by municipality 0.15 at the median and 98 at
most, by state 41 and 848, nationally ≤ 6,748 (`PASIS_ENT`; the age groups' base, 133 M of
specified age, allows 6,650).

Some national totals (Σ `FACTOR`):

| indicator | count | indicator | count |
|---|---|---|---|
| `P_0A4` (0–4) | 7,569,573 | `P15YM_POS` (posgrado) | 2,447,653 |
| `P_75YMAS` | 4,964,838 | `POCUP_ASA` (employees) | 41,075,996 |
| `PRESM20` (same municipality) | 116,060,639 | `PcSSyRecAc` | 112,887,166 |
| `PRESEUA20` (in the US in 2020) | 332,776 | `PUSU_SS` / `PUSU_IMSS` | 127,822,515 / 43,269,750 |
| `POB_IND` (self-identified indigenous) | 24,227,973 | `PASIS_MET` (metro or metrobús) | 683,231 |
| `PNACOP_NONAC` (born abroad, not Mexican) | 523,361 | `POCUP_OENT` (works in another entity) | 2,682,816 |
| `PCON_DISC60YM` | 3,505,785 | `POCUP_2HYM` (over 2 hours) | 1,420,909 |
| `P3YM_ASIS` (students 3+) | 32,962,938 | `HOG_AFRO` / `PHOG_AFRO` | 930,370 / 3,067,981 |
| `P12YM_CUL` (married or in union) | 54,680,983 | | |

**The new derived columns, every edition × 32 states** (`load_cpv_personas(derived=True)`,
352 loads: 1990–2025 raw, 2010/2015/2020 also harmonized; and the 32 EIC 2025 dwelling
frames): no unmapped code; `EDAD_QUIN` nests in `EDAD_CAT` (0–4 = «0-2» + «3-4», 65+, not
specified) in every row; the 2020/2025 `LUGAR_RES_5A` agrees with the legacy
`ENT_PAIS_RES_CAT` (own entity, abroad, blank) in every row; raw = harmonized for every new
column (46 weighted totals per edition); every dwelling's `HOG_AFRO` = its persons'.

| edition | 0–4 | 75+ | age not specified (% of persons; 1990/1995 unweighted) |
|---|---|---|---|
| CGPV 1990 | 12.63 | 1.69 | 0.10 |
| Conteo 1995 | 12.10 | 1.86 | 0.16 |
| CGPV 2000 | 11.12 | 1.93 | 0.30 |
| Conteo 2005 | 10.12 | 2.24 | 0.18 |
| Censo 2010 | 9.45 | 2.58 | 0.06 |
| EIC 2015 | 8.81 | 2.80 | 0.07 |
| Censo 2020 | 8.06 | 3.24 | 0.00 |
| EIC 2025 | 5.81 | 3.81 | 0.01 |

| column, national (Σ `FACTOR`) | Censo 2020 | EIC 2025 |
|---|---|---|
| `LUGAR_RES_5A` same / other municipality | 107,848,653 / 2,723,886 | 116,061,260 / 2,433,922 |
| … municipality not specified | 155,428 | 27,713 |
| … other entity / the US / other country | 3,936,960 / 381,464 / 185,841 | 3,579,751 / 332,776 / 218,954 |
| `ENT_PAIS_ASI_INEGI` other entity / abroad / NE | 683,942 / 54,301 / 202,484 | 610,613 / 59,789 / 6,677 |
| `ENT_PAIS_TRAB_INEGI` other entity / abroad / NE | 2,434,483 / 160,397 / 74,274 | 2,453,469 / 229,347 / 46,747 |
| students by metro or metrobús / bus / taxi | 572,912 / 7,333,678 / 700,460 | 683,231 / 7,121,334 / 935,593 |
| employed by metro or metrobús / bus / taxi | 1,767,602 / 13,954,311 / 1,373,882 | 1,923,227 / 13,176,735 / 1,773,301 |
| `DHSERSAL_AFIL_ACCESO` | — | 112,887,166 |
| `HOG_AFRO` «Sí» (persons) | — | 3,067,981 |

## Tests

- `test_derive_persons_7a` (offline): the seven new columns' rules and dtypes on synthetic
  2025 rows (ages, residence by municipality, place of school by INEGI's rule — 2025's
  renumbered Palaos —, the grouped modes counting a person once, the access item, the
  Afro-descendant household by its members), unknown codes raise, Censo 2020's
  `LUGAR_RES_5A` = 2025's on the same codes.
- `test_cpv_derivations_listing`, `test_source_codes_match_2020` (`DHSERSAL_ACCESO`: own
  codes; the own `MUN` skipped as `ENT`; the dwellings' `AFRODES` from the person file),
  `test_household_members` (2025's members read `AFRODES`).
- `test_derived_2020_equals_legacy`: the grouped modes = the OR of the legacy dummies.
- `test_cpv_constraints_per_edition`: 2025 sizes 214/93, the 7a cells, none elsewhere.
- `test_eic2025_constraints_equal_estimates` (real data, state 01 and its municipalities):
  all 307, a sum base, the disability by age on the specified-age base.
- `test_percent_bases_contract`: 264 mapped, the 11 left out by name; base parts each a
  published or derived count. `test_estimaciones_counts`: the two kinds of sum base.

Full suite on the Mac: **1863 passed, 1 skipped** (32 min, beside the 32-state sweep).

## Left out

- The 11 percentages above.
- Censo 2020 and the EIC 2015 ask most of these items too, but publish no ITER/estimates
  for them, so they get the derived columns (2020), not the constraints.
- `EDAD_QUIN` for the other editions' ITER age groups (`P_0A4` in 2000/2005 already has
  its own `EDAD_CAT` cell; nothing changes there).
