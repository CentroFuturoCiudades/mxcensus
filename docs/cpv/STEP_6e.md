# CPV Unit 6e — 2015/2010 migration, co-residence and financing in `cpv_derived`

Done **2026-10-08** (with the user, on the Mac). Gate: tests (full suite green, §Tests), a
32-state `derived=True` sweep of both editions with no unmapped code, and the new columns
checked against INEGI's tabulados (§Verification).

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| next unit | **6e**: the 2015/2010 birthplace, residence five years earlier, parent/partner pointers and 2015 `FINANCIAMIENTO` (HANDOFF candidate 1, first half) |
| merge of 6d | **after 6e**: merge 6d + 6e together at the end of this session, asking first |
| Censo 2010 mother/father (it asked only «does she/he live here? who?») | **new co-residence flags** `MADRE_EN_VIVIENDA`/`PADRE_EN_VIVIENDA` (Sí / No / No especificado) in every edition 2010–2025; 2015 also gets `IDENT_MADRE_CAT`/`IDENT_PADRE_CAT` (2020's codes); 2010 does not |
| EIC 2015 `IDENT_PAREJA` 98 «No sabe» (where the partner lives) | **→ No** (a partner living here would be listed here) |
| Censo 2010 birthplace/residence sentinels | **mirror 2020**: entity 999 «no especificada» → 997 → `OtraEnt`; 900 «Omisión del tema» → `No especificado`; country 600 → `OtroPais` |
| EIC 2015 `FINANCIAMIENTO` (one item, one answer; 1 = INFONAVIT, FOVISSSTE o PEMEX) | **its own dummy set**, as 6d's 2015 commute: 2020 names where the source is the same, 2015's wording for code 1 |
| INEGI's tabulados count an unspecified state as «No especificado» (found while verifying) | **keep the legacy rule (→ `OtraEnt`) in every edition**; document the gap; the tests pin the tabulados up to that group |

## Recodes (`_RECODE`, into the Censo 2020 code space)

| item | edition | edition code → 2020 code |
|---|---|---|
| `IDENT_PAREJA` | 2015 | 98 «No sabe» (dónde vive) → 96 «No» |
| `LNACEDO_C`, `RES05EDO_C` | 2010 | 999 «Entidad federativa no especificada» → 997; 900 «Omisión del tema» → 999 |
| `LNACPAIS_C`, `RES05PAI_C` | 2010 | 600 «Otro país, insuficientemente especificado» → 998; 700 «México (país)» → 997; 999 «País no especificado» → 998 (700 and 999 never occur) |

The 2015 items need no recode: `ENT_PAIS_NAC`/`ENT_PAIS_RES10` use 2020's code layout
(001–032, countries in 100–535, 997/998/999; `TC_ENTIDAD_PAIS_2015` adds six territories, all
inside 100–535), and `IDENT_MADRE`/`IDENT_PADRE` use 2020's codes (rows 01–54, 96 another
dwelling, 97 dead, 98 unknown, 99). The CSVs write the pointers un-padded (`3`); the codes
are read as numbers. `ENT_PAIS_RES10` is read as `ENT_PAIS_RES_5A` (`_ALIASES`).

## Edition-specific derivations

- **Censo 2010 birthplace and residence in 2005**: each split in an entity item and a
  country item. Over all 32 states the country item is set only when the entity item is
  blank (85,696 birthplace / 131,047 residence records), and both residence items are blank
  exactly for the 1,237,891 persons under 5. `_ent_pais_cat(var, name, abroad=)` reads the entity code,
  else the country code, then maps as 2020 (`EstaEnt` = the person's own entity).
- **Censo 2010 pointer pairs** (`_pointer_2010`): `IDMADRE`/`IDPADRE`/`IDCONYUGE` hold the
  row number (or 99, row not given) and `IDMADREC`/`IDPADREC`/`IDCONYUGEC` the answer when
  it is not a row (88 «no vive en la vivienda», 99 not specified). A row, or 99 with a
  blank code, → 1 (lives here); 88 → 96; 99/99 → 99; both blank → blank (partner only: not
  in a union). Any other code → -99, which no category takes, so `derive` raises.
  - The «99 + blank code» rows (228,326 mothers, 164,768 fathers, 51,296 partners) have
    the age profile of the numbered rows (mothers: median age 13 vs 12; «88»: 41), so they
    are «lives here, row not given». **Superseded by 6q** (`STEP_6q.md`): INEGI's ampliado
    tabulado `12_01A` counts them «no especificado» (to the person nationally), and so
    does `_pointer_2010` now.
  - Rows go up to 96 in 2010 (2020: 01–54); the pair reading makes that irrelevant.
  - 2010 gets `IDENT_PAREJA_CAT` (2020's Sí/No/NE/Blanco fit exactly) and the two flags,
    not `IDENT_MADRE_CAT`/`IDENT_PADRE_CAT`: its 88 merges 2020's 96/97/98.
- **`MADRE_EN_VIVIENDA` / `PADRE_EN_VIVIENDA`** (`_en_vivienda`, new, 2010–2025): from the
  2020 pointer codes, a row 01–54 → Sí, 96/97/98 → No, 99 → No especificado (dtype
  `_YES_NO`, as `DISCAPACIDAD`). In 2015–2025 they collapse `IDENT_MADRE_CAT`/
  `IDENT_PADRE_CAT`; in 2010 they read the pointer pair.
- **EIC 2015 financing dummies** (`_financiamiento_2015`), in 2015's own code space:

  | 2015 code | dummy `FINANCIAMIENTO_…` | 2020 |
  |---|---|---|
  | 1 | `INFONAVIT, FOVISSSTE o PEMEX` | INFONAVIT + FOVISSSTE + PEMEX |
  | 2–6 | `FONHAPO`, `Banco`, `Otra institución`, `Le prestó un familiar, amiga(o) o prestamista`, `Usó sus propios recursos` | the same (2020 codes 4–8) |
  | 9, blank | `No especificado`, `Blanco por pase` | the same |

  2015 records one answer, 2020 up to three. In 2015 exactly one dummy is 1 per dwelling,
  and `Blanco por pase` means "not asked" (not an owner who bought or built). In 2020 it is
  also set by a blank second or third answer (legacy rule).

### Columns per edition (after 6e)

| edition | personas | viviendas |
|---|---|---|
| 2025 | **58** (was 56): + `MADRE_EN_VIVIENDA`, `PADRE_EN_VIVIENDA` | 15 |
| 2020 | **60** (was 58): the same two | 15 |
| 2015 | **40** (was 33): + `ENT_PAIS_NAC_CAT`, `ENT_PAIS_RES_CAT`, `IDENT_MADRE_CAT`, `IDENT_PADRE_CAT`, `IDENT_PAREJA_CAT`, the two flags | **13** (was 5): + 8 `FINANCIAMIENTO_*` |
| 2010 | **22** (was 17): + `ENT_PAIS_NAC_CAT`, `ENT_PAIS_RES_CAT`, `IDENT_PAREJA_CAT`, the two flags | 4 |

## Constraints (`cpv_constraints`)

2010 personas **126 → 138**: `PNACENT`, `PNACOE`, `PRES2015` (2010 ITER `PRES2005`),
`PRESOE15` (`PRESOE05`), each with `_F`/`_M`, from the legacy cells on
`ENT_PAIS_NAC_CAT`/`ENT_PAIS_RES_CAT`. Others unchanged (2015: none; 2020: 157 + 46; 2025:
25 + 3).

## Verification

**32-state sweep.** `load_cpv_personas`/`load_cpv_viviendas(period, state=s,
derived=True)` for 2010 and 2015, all 32 states: no unmapped code, no missing value.
(`_pointer_2010`'s −99 guard and the 01–54 bound came after the sweep. They change nothing
on these data: the 2010 code items hold only 88/99/blank nationally, and 2015's rows reach
37/31/52.)

**National Σ `FACTOR`** (all 32 states):

| | 2010 | 2015 |
|---|---|---|
| born in the entity / another / abroad / NE | 80.6% / 18.3% / 0.9% / 0.3% | 82.1% / 16.6% / 0.8% / 0.5% |
| residence 5 years earlier: same / another entity / abroad / NE (all ages; blank = under 5) | 86.0% / 3.1% / 1.0% / 0.5% (blank 9.4%) | 87.2% / 2.7% / 0.6% / 0.7% (blank 8.8%) |
| partner in the dwelling: Sí / No / NE / blank | 40.4% / 1.3% / 0.6% / 57.8% | 41.0% / 1.4% / 0.5% / 57.2% |
| `MADRE_EN_VIVIENDA` Sí / No / NE | 48.6% / 50.8% / 0.6% | 45.2% / 52.6% / 2.2% |
| `PADRE_EN_VIVIENDA` Sí / No / NE | 38.3% / 60.9% / 0.8% | 35.0% / 63.2% / 1.8% |

The co-residence «No especificado» share is lower in 2010 (0.6% vs 2.2%). 2010 records
"lives here, row not given" as a row (above), so those persons are `Sí`. 2015 has one item,
and such answers probably end up in its 99. That is up to about 2 points of `Sí` that 2010
counts and 2015 cannot. State 01 across the four editions (`MADRE_EN_VIVIENDA` = Sí):
50.7%, 48.5%, 46.4%, 44.5%.

**INEGI's tabulados.** Σ `FACTOR` per state and sex (Total, Hombres, Mujeres; 32 states +
nation = 99 rows each) against the published percentages:

| tabulado | rows | result |
|---|---|---|
| EIC 2015 `04_migracion.xls` sheet 02: population by birthplace (entity, another, US + other country, NE) | 99 | exact up to the 997 group: `EstaEnt` and `OtroPais` exact; `OtraEnt`/NE off by the 252 persons nationally (73 records) coded 997 «entidad insuficientemente especificada», which INEGI counts as NE |
| EIC 2015 sheet 05: population 5+ by residence in March 2010 (same entity, another entity or country, NE) | 99 | **exact** (|Δ| < 0.5 persons; 6-decimal percentages). Country 998 (6,320 records) is «otra entidad o país» there too |
| Censo 2010 ampliado `04_02A_ESTATAL.xls`: population 5+ by residence in June 2005 | 99 | exact up to the entity-999 group: same entity exact; the other two off by the 1,690 persons nationally (79 records) coded 999, which INEGI counts as NE |
| EIC 2015 `14_vivienda.xls` sheet 18: owned dwellings bought or built, by financing | 33 | **exact** (|Δ| < 1e-8; national 19,095,472 = 31,949,709 − 12,854,237 `Blanco por pase`) |

With the unspecified-state group counted as NE, all three migration comparisons are exact
in every row (worst |Δ| 0.87 persons, the rounding of 6-decimal percentages). The
population universe is ages 5–130: INEGI leaves out persons of unspecified age. They were
asked the residence question, so `ENT_PAIS_RES_CAT` gives them a category.

The derived columns keep the legacy 2020 rule (an unspecified state → `OtraEnt`) in every
edition (user's choice). The column means the same in 2010–2025, and 2020 must equal the
legacy loader. INEGI's rule would move ≤ 0.002% of the population. Sources: INEGI,
*Encuesta Intercensal 2015, tabulados* (elaborated 24/10/2016),
`intercensal/2015/tabulados/04_migracion.xls`, `14_vivienda.xls`; *Censo de Población y
Vivienda 2010, Tabulados del Cuestionario Ampliado* (24/05/2013),
`ccpv/2010/tabulados/Ampliado/04_02A_ESTATAL.xls`. The ampliado has no birthplace table
(birthplace is a basic-questionnaire item).

**Censo 2010 sample vs the census ITER** (the 12 new constraints, national):

| indicator (2010 ITER) | ITER | sample Σ FACTOR | sample vs ITER |
|---|---|---|---|
| `PNACENT` / `_F` / `_M` | 89,918,571 / 45,898,604 / 44,019,967 | 90,237,477 / 46,130,502 / 44,106,975 | +0.4% / +0.5% / +0.2% |
| `PNACOE` / `_F` / `_M` | 19,747,511 / 10,256,735 / 9,490,776 | 20,458,048 / 10,674,851 / 9,783,197 | +3.6% / +4.1% / +3.1% |
| `PRES2015` (`PRES2005`) / `_F` / `_M` | 95,431,977 / 49,304,545 / 46,127,432 | 96,248,626 / 49,829,351 / 46,419,275 | +0.9% / +1.1% / +0.6% |
| `PRESOE15` (`PRESOE05`) / `_F` / `_M` | 3,292,310 / 1,652,115 / 1,640,195 | 3,502,386 / 1,775,502 / 1,726,884 | +6.4% / +7.5% / +5.3% |

As in 6d, the sample reproduces INEGI's ampliado tabulado, not the census ITER. The
entity-999 group (OtraEnt here) accounts for only ~2k of the residence gap. The rest is
the known census-vs-sample difference (the census has more unspecified answers).

## Tests (`tests/test_cpv_derived.py`)

- **Offline:**
  - `test_source_codes_match_2020`: 2015 `ENT_PAIS_NAC`/`ENT_PAIS_RES10` (gap 997/998:
    catalog rows, not FD sentinels, in 2015) and `IDENT_*` (numeric in 2015, `_NUMERIC_CODES`);
    2010's split items, pointer pairs and 2015 `FINANCIAMIENTO` as own-code items
    (`_OWN_CODES`; a string own-code item must name its catalog);
  - the new recodes (`test_recode_tables`);
  - the listings per edition (personas 2010/2015, viviendas 2015; the flags in 2020/2025);
  - synthetic 2025/2015/2010 persons (birthplace, residence, pointers incl. 99 + blank
    code and a row above 54, 2015's un-padded pointers and 98) and 2015 dwellings (financing);
  - unknown codes raise (a 2010 pointer code 77; a birthplace with neither item);
  - 2010 constraints include `PNACENT_F`, `PNACOE`, `PRES2015`, `PRESOE15_M`.
- **Real data (local mirror):**
  - `test_migration_equals_tabulados`: EIC 2015 state 05 birthplace and residence, Censo
    2010 state 02 residence = the tabulados, with the unspecified-state group (14 and 143
    persons) moved to NE;
  - `test_financing_2015_equals_tabulado`: state 01, exact, one dummy per dwelling;
  - the existing `test_derived_editions_real` (all four editions, state 01) and
    `test_derived_2020_equals_legacy` (the flags are extra columns, `_DTYPES`) cover the
    rest.
- **Full suite**: 1633 passed, 1 skipped (32 min, the Mac's full mirror; started before
  `test_financing_2015_equals_tabulado` was added, which passes on its own).

## Not done (HANDOFF §Next)

- the older SINCO/SCIAN occupation and activity catalogs (`*_COARSE` for 2015/2010);
- 2010 religion (`OTRAREL_C`, a catalog);
- 2015 has no religion item, no `IDENT_HIJO`; 2010 has no financing item (`FADQUI` only);
- 2000/2005 have no derived columns yet.
