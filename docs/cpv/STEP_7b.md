# CPV Unit 7b — the older editions catch up: the places by municipality

Done **2026-10-10** (on the Mac; HANDOFF candidate 3, «the older editions catch up», agreed
with the user at the session's start, together with the 0.11.0 release preparation). Gate:
7a's place columns for the EIC 2015 and Censo 2010, each equal to INEGI's tabulados in every
state; the EIC 2015 tabulado checks for the household class, tenure and deeds; tests green.

## The user's choices

- **The unit**: «older editions catch up» (HANDOFF candidate 3's first items) over the
  ratio constraints (candidate 2) and 2000's income in minimum wages; the release
  preparation alongside (`wsl` suite in the background, merge/tag/push on the user's word).
- **The places by municipality** (asked once the 2015 and 2010 items were probed): new
  `LUGAR_ASI` and `LUGAR_TRAB` beside `LUGAR_RES_5A`, not only the entity-level
  `ENT_PAIS_ASI_INEGI`/`ENT_PAIS_TRAB_INEGI` (7a parity). INEGI's 2010, 2015 and 2020
  tabulados publish the school and work places by municipality (the EIC 2025 estimates only
  by entity).

## The items

| edition | residence five years earlier | school | work |
|---|---|---|---|
| Censo 2010 | `RES05EDO_C` (entity: 001–032, 900 topic omitted, 999 entity not specified) or `RES05PAI_C` (country: 600, 700 «México (país)», 999) + `MUN05OTR_C` | not asked | `LTRABPAI_C` (one item, **both catalogs**: entities 001–032, 900, 999; countries, 600, 700) + `LTRABMUN_C` |
| EIC 2015 | `ENT_PAIS_RES10` + `MUN_RES10` | `ENT_PAIS_ASI` + `MUN_ASI` | `ENT_PAIS_TRAB` + `MUN_TRAB` |
| Censo 2020 / EIC 2025 | `ENT_PAIS_RES_5A` + `MUN_RES_5A` | `ENT_PAIS_ASI` + `MUN_ASI` | `ENT_PAIS_TRAB` + `MUN_TRAB` |

- The EIC 2015 uses 2020's codes (997 entity not specified, 998 country not specified,
  999, 221 the United States; municipalities zero-padded; its FD declares only 999, the
  others are rows of `TC_ENTIDAD_PAIS_2015`, as for its birthplace).
- Censo 2010's municipality item holds the municipality for every person with a Mexican
  residence (the own municipality too, despite the FD's «(otro)»), 999 when not given.
- **Censo 2010's place of work, `LTRABPAI_C`**: its FD names the country catalog, but the
  data hold the entity codes too, with the entity catalog's 900 and 999. Its 999 is ambiguous
  in the catalogs (entity or country not specified). INEGI's tabulado `08_15A` settles it:
  Mexico City's employed match to the person in every cell only with 999 = the entity's «no
  especificada» (with 900, «No especificado»; as «another entity or country» the share is
  off by 0.46 points). `_RECODE["2010"]["LTRABPAI_C"]` = {600: 998, 700: 997, 900: 999,
  999: 997}.
- Each place is asked of exactly the students and the employed (every state of 2010–2025),
  persons of unspecified age (999) included; INEGI's tabulados leave those out, so the cells
  keep the age condition (5+, students 3+, employed 12+).

## What changed

- `cpv_derived`:
  - `_lugar(var, mun, name, abroad=None)` generalizes 7a's `_lugar_res` (the categories of
    `LUGAR_RES_5A`: «Mismo municipio», «Otro municipio», «Municipio no especificado», «Otra
    entidad», «Estados Unidos», «Otro país», «No especificado», «Blanco por pase»; Censo
    2010's split answer via `abroad`).
  - new derived **`LUGAR_ASI`** (2015, 2020, 2025) and **`LUGAR_TRAB`** (2010–2025), dtype
    `_LUGAR_RES`;
  - `LUGAR_RES_5A` now 2010–2025 (2015: `_ALIASES` `MUN_RES_5A` = `MUN_RES10`; 2010 its own
    derivation from the split items);
  - `ENT_PAIS_ASI_INEGI` 2015–2025, `ENT_PAIS_TRAB_INEGI` 2010–2025 (2010 from
    `LTRABPAI_C`);
  - `_RECODE["2010"]["LTRABPAI_C"]` (above).
  - Not ported: the grouped commute dummies (`MED_TRASLADO_*_{METRO,BUS,TAXI}_T`): the EIC
    2015 answers bus and taxi with one code (its own dummies, 6d, keep it).
- Constraints: none change (no edition but the EIC 2025 publishes these places as
  aggregates; its cells were 7a's).
- `scripts/check_cpv_tabulados.py`:
  - the places by municipality (`_place`, `_place_published`): Censo 2010 `04_02A`
    (residence, replacing the entity-level check) and `08_15A` (work; new source), EIC 2015
    `04-05` (residence, replacing), `10-01` (school), `10-04` (work), Censo 2020 `10-02`
    (school), `10-08` (work) — the universe, the same entity, the same municipality, another,
    not specified (each as % of the same entity in the tabulados), another entity or country,
    not specified;
  - EIC 2015 `04-02` reads `ENT_PAIS_NAC_INEGI` (6y) instead of moving the unspecified group
    (`_moved` is gone);
  - EIC 2015 `12-05a` (households by `CLASE_HOG` and by the raw `TIPOHOG` within each class),
    `12-05b` (the population in households by `CLASE_HOG`), `14-13` (tenure, `TENENCIA`),
    `14-16` (owned dwellings by deed, `ESCRITURAS_VIV`). The dwelling tabulados leave out the
    locales no construidos para habitación, móviles and refugios (`CLAVIVP` 7–9, their
    footnote 1); the households count every dwelling (31,949,709 households against
    31,924,863 dwellings nationally).
- Docs: `cpv_derived` docstring, README, CLAUDE.md.

## The data

**INEGI's tabulados, every state, both sexes and the nation**
(`scripts/check_cpv_tabulados.py`, `TABULADOS_REPORT.md`): 26,760 cells (21,843 before), none
beyond tolerance. The 4,917 new cells:

| edition | check | cells | max \|Δ\| (persons) |
|---|---|---|---|
| Censo 2010 | `04_02A` residence in 2005 by municipality (`LUGAR_RES_5A`) | 693 | 0.00 |
| Censo 2010 | `08_15A` place of work by municipality (`LUGAR_TRAB`) | 693 | 0.00 |
| EIC 2015 | `04-05` residence in 2010 by municipality | 693 | 0.51 (nation) |
| EIC 2015 | `10-01` place of school by municipality (`LUGAR_ASI`) | 693 | 0.00 |
| EIC 2015 | `10-04` place of work by municipality | 693 | 0.00 |
| EIC 2015 | `12-05a` households by class and type | 330 | 0.16 (nation) |
| EIC 2015 | `12-05b` population in households by class | 132 | 0.47 (nation) |
| EIC 2015 | `14-13` dwellings by tenure | 198 | 0.00 |
| EIC 2015 | `14-16` owned dwellings by deed | 198 | 0.00 |
| Censo 2020 | `10-02` place of school by municipality | 693 | 0.15 (nation) |
| Censo 2020 | `10-08` place of work by municipality | 693 | 0.21 (nation) |

(2010: full precision; 2015/2020: six-decimal percentages, so a national cell may be off by
up to ~0.9 of a person.) The 2015 birthplace on `ENT_PAIS_NAC_INEGI` is as exact as before
on the moved group (max 0.87, the nation).

**Every state of 2010, 2015, 2020 and 2025** (`load_cpv_personas(derived=True)`, raw and
harmonized: 256 loads): no unmapped code and no own entity without a municipality;
`LUGAR_ASI`/`LUGAR_TRAB` without the municipality = `ENT_PAIS_ASI_INEGI`/`ENT_PAIS_TRAB_INEGI`
in every row; raw = harmonized weighted totals of every new column; `LUGAR_RES_5A` = the legacy
`ENT_PAIS_RES_CAT` (own entity, another, abroad, not specified, blank) in every row but the
entity not specified (997; 2010 `RES05EDO_C` 999 or `RES05PAI_C` 700), «No especificado»
here and `OtraEnt` there (sample rows: 79 in 2010, none in 2015 — its residence writes
999 —, 2,125 in 2020, 2,982 in 2025).

National totals (Σ `FACTOR`, thousands):

| column | category | Censo 2010 | EIC 2015 | Censo 2020 | EIC 2025 |
|---|---|---|---|---|---|
| `LUGAR_RES_5A` | same municipality | 92,942 | 101,000 | 107,849 | 116,061 |
| | another municipality | 3,077 | 3,216 | 2,724 | 2,434 |
| | municipality not specified | 274 | 36 | 155 | 28 |
| | another entity | 3,502 | 3,199 | 3,937 | 3,580 |
| | the US / another country | 985 / 91 | 559 / 129 | 381 / 186 | 333 / 219 |
| | not specified | 513 | 865 | 166 | 169 |
| `LUGAR_ASI` | same municipality | — | 29,569 | 29,314 | 29,728 |
| | another municipality | — | 2,605 | 2,745 | 2,554 |
| | another entity / abroad | — | 607 / 50 | 684 / 54 | 611 / 60 |
| | not specified (+ municipality) | — | 1,547 (+ 33) | 202 (+ 26) | 7 (+ 4) |
| `LUGAR_TRAB` | same municipality | 33,663 | 35,537 | 42,435 | 48,487 |
| | another municipality | 5,725 | 6,582 | 7,120 | 6,998 |
| | another entity / abroad | 2,169 / 133 | 2,266 / 133 | 2,434 / 160 | 2,453 / 229 |
| | not specified (+ municipality) | 882 (+ 152) | 499 (+ 98) | 74 (+ 44) | 47 (+ 33) |

The EIC 2015's students with the place not specified (4.5%, its tabulado's too) and Censo
2010's employed (2.1%) stand out; both are INEGI's.

## Tests

- `test_derive_places_7b` (offline): every category of the three places in 2015 and 2010
  (2010: the entity or the country item, 900, 999, 700, 600), INEGI's entity-level columns
  = the places without the municipality, dtypes, the own entity without a municipality
  raises.
- `test_derive_persons_7a` (2025's `LUGAR_ASI`), `test_derive_persons_2015_recodes`,
  `test_derive_persons_2010_recodes` (their builders carry the new items),
  `test_cpv_derivations_listing`, `test_source_codes_match_2020` (2010's three own-code
  items; 2015's `ENT_PAIS_ASI`/`_TRAB` gaps 997/998; 2020's FD names no catalog for
  `MUN_TRAB`: `_REF_WITHOUT_CATALOG`), `test_recode_tables` (2010's work item).
- `test_places_equal_tabulados` (real data, state 01): the 2010, 2015 and 2020 places equal
  INEGI's tabulados (7 cases).

- `test_state_01_within_tolerance` (`tests/test_cpv_tabulados.py`): 149 more state-01 cells
  (the seven place checks, 7 cells × 3 sexes; the four EIC 2015 household and dwelling
  checks, sex T).

Full suite on the Mac: **1881 passed, 1 skipped** (32 min, beside the tabulado run and the
sweep; the first run's one failure was that cell count, then fixed and re-run). `wsl` (the
same code: 7a + this unit's patch, for the 0.11.0 release): **1882 passed** (1 h 54 min, none
skipped).

## Left out

- The EIC 2015's grouped commute dummies (above).
- The 2020 residence by municipality has no ampliado tabulado (Censo 2020 asked the residence
  in 2015 of everyone: its básico tabulados, not the sample's).
