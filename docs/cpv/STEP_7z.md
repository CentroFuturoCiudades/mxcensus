# CPV Unit 7z — more tabulado checks: every CGPV 2000 tabulado, every value

Done **2026-10-12** (on the Mac, with the user). HANDOFF candidate 3's «CGPV 2000's
tabulados» item (whether INEGI publishes more, a coverage probe for their layout), the user's
choice over the 0.15.0 release, a 2015 locality edition and the lineage leftovers; widened by
the user on the probe to every value («Everything»). Gate: every published value of the 2000
tabulados enters a compared cell; every cell within its tolerance; tests green. Checks only:
no loader, derivation or dictionary changed.

## What INEGI publishes

INEGI's file-listing API (`idBiinegi` 2, `tipodocto` 5; `STEP_0_probe.md`) lists **95**
cuestionario-ampliado workbooks under `ccpv/2000/tabulados/ampliado/` — `SOURCES` held 66 —
plus 13 national workbooks of the cuestionario básico (`CPyV2000_NAL_*`: the census, not the
sample; out of scope, as Censo 2010's and 2020's básico tabulados) and 8 interactive (OLAP)
tables. The 29 others: 23 by locality size (`C2KDI03/05`, `EC01`, `ED01/03/05/07/09/13/15`,
`FE01/02/06`, `HO03/06`, `LI01/03`, `PO02`, `RE01`, `SS01/02/05/06`) and six by state or
nation (`C2KED14`, `SS03/07/08/09`, `MI13`).

**Every value**: a probe on 2000's layout (below) found 14,700 of the 55,302 published values
of the 66 workbooks unread — mostly the counts, each row's population, dwellings or
households (column B), which the 2000 checks never compared (they compare shares) — and a
few blocks: every age row of EC02/MI01/MI03, the net migration (MI02/05 D), the migrants'
share of the residents (MI09 C), average schooling (ED10 M), the 100% totals of MI07,
MI10–12, VI18 and DI04, LI02's «Resto de las entidades».

## The finding: the counts are exact but in Chiapas

Σ `FACTOR` equals INEGI's published count of every row of every 2000 tabulado — persons,
occupants, dwellings, households, migrants — **in every state but Chiapas**: INEGI computed
its tabulados from the public sample's records and weights, Chiapas's apart. Chiapas's total
population agrees (3,912,081), its sexes do not (−228 men, +228 women), nor its dwellings
(−484) and households (−583); its largest gap is 1,324 persons (SS09n: the users of each
institution among the covered), and the nation inherits it. The 4a explanation of the 2000
gaps (the weights' ratio estimator on preliminary counts) holds for Chiapas only: outside it,
the shares agree within the edition's 0.04 points (median 0.003; MI04's documented municipal
migrants apart).

## What changed

Only `scripts/check_cpv_tabulados.py` (and its tests, the report and the docs).

- **Readers** (`_c2k_every`): CGPV 2000's layout row by row — under each place (a state, the
  nation, «RESTO DE LAS ENTIDADES», a locality size renamed as a state) every row with values,
  its own first, then the blocks under its HOMBRES and MUJERES rows; or the sexes in column
  groups (`{sex: cols}`); a row's cells mapped by `row`. `_num` reads C2KHO03's «M.I» (no
  dot) as missing; `_state_of` «RESTO DE LAS ENTIDADES» (upper case) as `_REST`.
- **Locality size**: `_SIZES["2000"]` (INEGI's four), `_size_2000` (`TAM_LOC` 1, 2, 3–5,
  6–7), `_sized_rows_2000` (the size rows' spacing and a leading «DE » vary),
  `_sized_2000(check, key, source)` (the 7s machinery on CGPV 2000's layout; `_sized_cells`
  takes the size function).
- **Counts** (`_counted`, keys ending in «n»; 72 checks on the 66 workbooks): each row's
  universe in persons, occupants, dwellings or households (the check's weight). Tolerance
  `_COUNTS_2000`: 1, but Chiapas and the nation 1,500 (`_CHIAPAS_COUNTS`; the largest seen
  1,324), every locality size 7,000 (`_SIZED_COUNTS`: all four hold Chiapas's records; the
  largest seen 6,533, LI03n's speakers).
- **Widened** (`_reworked_2000`): EC02, MI01, MI03 every age row (`_per_row`, `_universes`:
  `_ALL` = every age, 999 too); MI02/MI05 the net migration (`combine`); MI07, MI10–12, VI18,
  DI04 their «100» totals; LI02 «the rest of the states» (`_selected`: the 20 others counted
  in `_REST`, by origin).
- **New on the 66**: ED10m (grado promedio de escolaridad: the mean `ESCOACUM` of the 15+ who
  gave it), MI09r (the `migrantes` file's records as % of the residents: `_frame` puts each
  dwelling's migrants on its first person, `_with_migrants_2000`), MI09n.
- **New by state**: SS03 (coverage by age group), SS07 (use of health services by age
  group), SS08 (by sex), SS09 (by coverage condition and institution), ED14 (causes of leaving
  school by sex), MI13 (each state left's share of the nation's international migrants per
  destination: `Check.of_nation`, every cell's denominator the nation's), MI13n.
- **New by locality size** (44 checks): SS02/06, EC01, ED03/05/09 through their by-state
  twins (SS04, SS08, EC02, ED04/06/10 and their counts); SS01/05 (coverage, use by five-year
  age), DI03/05 (the disabled by age and by type, by cause), LI01 (language and Spanish by
  sex and age), LI03 (self-ascription, `PERETN`, by speaking), FE01 (women by children born
  alive and age), ED13/15 (causes of leaving school by age, by sex and level), ED07 (level
  with primaria's grades by age), ED01 (literacy of the 6–14 by single age), PO02 (counts by
  five-year age and sex), RE01 (religion in INEGI's 2000 groups), HO03 (households and their
  population by the head's age and sex), HO06 (other incomes in minimum wages), FE02
  (children born alive per woman by age and size, national), FE06 (infant mortality).
- **The coverage probe** reads 2000 (`_ESTIMATOR["2000"]` = `None`): every number but
  column A's from the nation's row («ESTADOS UNIDOS MEXICANOS», where every 2000 tabulado's
  data start; `_c2k_traced`) down; `--coverage` covers all four editions.
- **The report**: the 2000 header names the counts' tolerances.

## The definitions found

- **Use of health services** (SS05–09, `SERSALUD`): users = 1–7; «otra institución pública»
  (state social security) = 7, «privada» = 6 — exact outside Chiapas.
- **Leaving school** (ED13–15): those who stopped = `ASISTEN` 2 and `ABANESCO` 1–8 (8: the
  cause not specified; 0 never attended, 9 not specified are not); INEGI's groups personal 1,
  economic 2, school 4, family 5, marriage 3, finished 6, other 7 — ED14 exact outside
  Chiapas.
- **Sin instrucción** (ED07): `NIVACAD` 0, preescolar 1 **or blank** (4.55% of the
  6-year-olds: never attended) — the 6-year-olds' 79.28% exactly.
- **Religion** (RE01): INEGI's 2000 catalog is in the RNM DDI codebook (`ddi_id` 141, not in
  any download): históricas 1101–1114, pentecostales 1201–1299 **but** «Cristiana» (1217) and
  «Evangélica» (1219), counted with the other evangelical (1401–1499) — their sum matches
  INEGI's split to 0.03% —, La Luz del Mundo 1301, the biblical 2001–2003, judaica 5001,
  other religions 3001–4999 and 6001–9001 (9001 espiritualista), none 9100, NE 9999.
- **Average schooling** (ED10/ED09 M): the mean `ESCOACUM` (≤ 24) of the 15+ — exact.
- **Other incomes** (HO06): none = `OTINGHOG` 0; the perceivers' amount by 7c's minimum
  wages, not specified (999999) among them.
- **Infant mortality** (FE06): **not reproducible**, as 2010's and 2015's (7o). INEGI's rates
  of «the deaths that occurred in 1999» (nation 17.51, by the mother's age 16.8 / 15.94 /
  28.16) match no ratio of the sample: the last children born in 1999 who died before their
  first birthday give 16.62 (ours), deaths dated in 1999 by birth month and age at death
  14.29, the children of a known birth month 16.45. Tolerance = the largest gap (1.9 per
  1,000).

## The data

| | cells | max \|Δ\| outside Chiapas |
|---|---|---|
| 2000 before 7z (89 checks) | 39,315 | |
| counts of the 66 (72 checks) | 7,710 | 0 (exact) |
| the 66 widened (EC02/MI01/MI03 ages, net migration, totals, LI02's rest) | +6,165 | 0.024 |
| ED10m, MI09r | 132 | 0.005 |
| new by state (SS03/07/08/09, ED14, MI13 and counts) | 8,778 | 0.030 (MI13) |
| new by locality size (44 checks) | 9,460 | — (every size holds Chiapas) |
| **2000 now (219 checks)** | **71,560** | |

**Every cell within its tolerance.** By locality size every size holds Chiapas's records, so
a share of a base Chiapas weighs on is off by up to 0.34 points (RE01's Adventists: Chiapas
holds 15% of the biblical group, 67.6% of them Adventists); `_SIZED_POINTS` documents eleven
checks' tolerances (LI01 0.18, LI03 0.15, RE01 0.34, ED13/15 and HO03/03p 0.09, DI03/05,
ED01, SS05 0.06). **Each such gap is a fraction of Chiapas's whole contribution to the cell**
(a run with Chiapas's records removed: LI01 ≤ 4%, RE01 ≤ 6%, LI03 ≤ 93%; ED13/15 up to 1.7
on small bases), so no definition explains it; the median by-size gap is 0.003 points.

The report: **797,781 cells** (765,536 before), 0 beyond tolerance; only its header and 2000
section changed. The coverage probe: CGPV 2000's **73,705 published values** (the 66 workbooks
55,302, the 29 new 18,403), **none unread**; 2010, 2015 and 2020 none unread as before.

Nationally (Σ `FACTOR`, INEGI's in brackets): 2,241,193 disabled (2,241,148); 1,632,790
international migrants 1995–2000 (1,633,052), 1.68% of the residents; the grado promedio of
the 15+ 7.56 years (men 7.82, women 7.33; each state's within 0.011).

## Tests

- `test_cgpv2000_every_value_7z` (offline): `_c2k_every` (sex blocks, a place without values,
  «M.I», «RESTO DE LAS ENTIDADES», the sexes in columns), the size rows' spellings,
  `_size_2000`, the counts' check (title, unit, tolerances; by size `_SIZED_COUNTS`), a
  by-size reader missing a size raises, `_with_migrants_2000` (and its raise), MI13's
  `of_nation` through `run` on 32 synthetic states, the probe on 2000's layout (the header's
  numbers are no published value).
- `test_every_published_value_is_read` (real tabulados): 2000 too; without VI16n its 330
  dwelling counts unread.
- `test_checks_are_consistent`: 2000's counts carry `_COUNTS_2000` or `_SIZED_COUNTS`; by
  size any edition.
- `test_state_01_within_tolerance`: **21,606** cells (+673: the counts +258, EC02/MI01/MI03
  rows +165, totals +11, ED10m, MI09r, SS03/07/08/09, ED14), every one within tolerance;
  LI02, LI02n and MI13 count by origin.
- `tests/test_cpv_tabulados.py`: **35 passed**. The full suite was not run: 7z touches only
  the check script and its tests (as 7v–7y).

## Verification

- The probe, then the checks over 32 states through a scratch harness (`run` on a subset of
  `CHECKS`, ~8 min per run, two in parallel), the national raw items for the definitions, a
  run with Chiapas's frames emptied for the by-size gaps.
- The full 2000 report run (one process, ~13 min), its section and the header spliced into
  `TABULADOS_REPORT.md` as `report()` writes them (2010/2015/2020 untouched).

## Left out

- The 13 cuestionario-básico workbooks (`CPyV2000_NAL_*`): the census, not the sample.
- FE06's infant mortality: INEGI's procedure is not in the sample (as 2010/2015's, 7o).
- Chiapas: its records are not those of INEGI's tabulados; nothing in the mirror can close
  the gap (the public sample is what INEGI publishes).
