# CPV Unit 8d — the locality lineage's leftovers

Done **2026-10-13** (on the Mac; the check's mirror is a scratch directory of symlinks to
`data/parquet`'s ITERs and MG 2010/2015/2020 layers plus the MG 2025 `l`/`lpr` layers of the
Pooch cache; `wsl` not needed). HANDOFF candidate 2's leftovers, the user's choice over the
0.15.0 release (recommended), the small derived columns and the 2000 occupation bridge;
`CONFIRMED` stays per edition (the user's answer to 8c's open question). Gate: every new rule
general (no code listed by hand), the lineage rebuilt and checked against every ITER and
frame, `load_ahl_poblacion` unchanged, tests green.

8c's report put the most weight on the `code` links the editions contradict (197, 95 of them
1990 → 1995); reading them found two rules the parser had wrong, and reading the statements
it skipped found five more.

## «Es la misma localidad»: which record is the duplicate

7t read «Es la misma localidad (LLLL) del municipio (MMM)» (and «Misma que la localidad …»)
as the stating record being the duplicate (`FROM`). Michoacán's Conteo 1995 writes it on
**both** records, and on the new code's first row: Las Cañadas, 160100621, starts at the
Conteo 1995 with «Es la misma localidad (0608)»; 160100608's record ends there with «… (0621)».
7t made two opposite links, one of them contradicted (0621 is in the 1995 ITER).

**Rule** (`record_links`, `duplicate`; `parse` passes every record's last dated event): the
stating record is the duplicate, unless its history goes on past the statement and the other
record's ends by then — then it is the new code (`FROM` = the other). Of the 761 statements,
144 in scope turn: 118 match the editions (the old code gone, the new one there), 26 neither
code is in the edition; one stays contradicted (both records go on). 40 pairs become one
confirmed link (El Potrero, 160150140 → 160150575: the old record's statement is of 1990,
out of scope, so only the reoriented one is left).

## A move and the move back at one edition

Estado de México's decree 34 of 2 October 2001 created Luvianos with localities of
Tejupilco, which «Viene del municipio de Luvianos (123) con clave …» at the Conteo 2005
(the old code again); Oaxaca's updates of 2000–2004 moved localities that the Conteo 2005
moved back; Tlacuilola went to Querétaro in 2007 and back by the Censo 2010. Each left two
`code` links at one edition, A → B and B → A, and the first contradicted.

**Rule** (`lineage`, after «joined and left», *moved and moved back*): a `code` link and its
reverse at one edition whose first statements are on **different days** cancel out — the
locality ends under the code it started with. 28 pairs (56 links: 19 at 2005, 7 at 2010, 2
at 1995, 1 at 2015, 1 at 2020); none against the codes (no pair where the edition has B and
not A). The **same day** (3 pairs) they are two records each stating the other as its origin
(La Esperanza, Carmen ⇄ Candelaria, both «Viene …» at the Censo 2000): kept, as before.

## Statements the parser skipped

| shape | example | statements | reading |
|---|---|---|---|
| another municipality named first | «Se fusiona al municipio de Coatepec (038) Localidad Briones (0031).»; «Se conurba al municipio (011) San Francisco de los Romo localidad (0001).» | 3 in scope (2019) | absorption (`absorbida_mun`) |
| «Forma parte de» | «Baja de localidad. Forma parte de la localidad El Vergel (0051) del municipio de Aquismón (003).» | 6 in scope | absorption (`forma_parte`) |
| a part's move | «Parte de la localidad pasa al municipio de Nextlalpan (059) con clave de localidad (0041).» / «… viene del municipio de Tultepec (108) con clave … (0019).» | 2 in scope | separation (`parte_pasa`/`parte_viene`), no longer a `code` link |
| a year after «de» without a space | «Decreto No. 162 del 01 de marzo de1992.», «del 13 de mayo de2001» | 34 newly dated | dates (`_DATE_RE`, `_YEAR_RE`) |

- Coatepec's three: Briones and Chilacayotes confirm the absorber's statements; Tecojotal
  (301820020 → 300380196, Tres Marías since April 2019) is new.
- «Forma parte»: five of San Luis Potosí's Conteo 1995 (with «Baja de localidad») and El
  Caudillo's 2005 «Forma parte de la localidad 240470089» — the reverse of 0089's 1995
  statement (0089 ends in 1995; 0085 is counted at every census): INEGI's slip, which the
  census rule moves to 2025, where MG 2025 contradicts it (left).
- A part that moves is not the same locality under another code: Ejido Tultepec (151080019)
  keeps its code, so the part is a `separation` 150590041 → 151080019 (confirmed; 150590041
  also separates from Cajiga that census: two separations, both kept). The other part
  statement, San Luis Potosí's «Parte del territorio de la localidad … se integra al
  municipio de Villa de Pozos (059) …», is undated: Villa de Pozos's «Viene del municipio de
  San Luis Potosí (028) con clave (0001)» stays a `code` link 240280001 → 240590001 at 2025
  (contradicted: the city keeps its code; the unit is right either way).
- The dates: undated statements 67 → 33. Aguascalientes's decree 162 of 1 March 1992 (El
  Llano, San Francisco de los Romo; 18 statements) confirms the new records' links at 1995;
  Nuevo Progreso's absorption «del 31 de julio de2024» is new at 2025; a creation «del 13 de
  mayo de2001» (203770154) loses 8c's *record starts later* (the frame lists it in 2015,
  the AHL has no census row before 2020: now unexplained, honestly). The year needs no word
  boundary but no digit around it (`(?<!\d)…(?!\d)`), so a code never dates a row.

## Lists with a digit dropped or doubled

58 list statements («A esta localidad se conurban las …») carry a code of 8, 10 or 11 digits
(«05190133», «0200013922», «05050210100»), one carries two codes without a comma
(«160530359160530378»), two a period between codes («161020350.1610200357»). The `\d{9}`
list pattern stopped at an 8-digit code (every code after it lost) and cut a 10-digit one to
a wrong 9-digit code: 13 links in 8c's table to codes nobody stated, and three that 8c's
census rule dropped as *counted on its own* — Veracruz's 301260014 and 301600046 (the
truncations of 301260144 and 301600465) and Jacala's 130310005 (its list's slip for
130310055, a twin `repair_lists` could single out only once «13031006» read as 130310006).

**Rule**: the list takes 8+ digit runs and «.» between codes (`_LIST`); `_listed` splits a run
whose length is a multiple of 9; `repair_lists(links, records)` reads a code of another length
as the AHL record a digit dropped or doubled away (`_digit_off`) that states the event into
the listing record at that edition, else the only one in the listing record's municipality
(*a digit off*: 65, 1960–2026), else drops it (*unread*: 4 — 04002081, 20342009, 21209205,
2200603015).
The codes after them are read again: **140 links newly confirmed**.

## The check: codes the AHL marks «*»

The Conteo 1995's ITER lists its one- and two-dwelling localities only in its 9998/9999
aggregates; the AHL's `Habitantes` marks them «*» (any census: a locality that ITER does not
list). `check(…, stars)` (`unlisted(Habitantes)`) explains a code missing from an ITER that
the AHL marks «*» at that census (*not listed*): 1990 → 1995 leaving 229, entering 552. The
report only; no link changes.

## Result: 32,905 links (8c 33,005)

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|---|
| code | 0 | 3,526 | 2,327 | 1,883 | 889 | 452 | 2,391 | 840 |
| absorption | 0 | 1,957 | 1,557 | 2,769 | 3,154 | 1,387 | 5,292 | 2,151 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 71 | 150 | 253 | 309 | 609 | 309 |

- Against 8c: 214 links out (201 `code`: the reoriented duplicates, the cancelled moves,
  Ejido Tultepec's; 13 absorptions on truncated codes), 114 in (104 `code`, the duplicates'
  right direction; 9 absorptions; 1 separation); **199 newly confirmed, none lost**.
  Confirmed: code 77.3% → 78.0%, absorption 82.0% → 82.7%, separation 84.9% → 85.3%.
- Units: `cpv_locality_units(2010, 2020)` 16,662 codes in 6,251 units → 16,655 in 6,250;
  1990 → 2025 50,800 in 18,402 → 50,754 in 18,387.
- `ahl._copies` reads the `code` links: `load_ahl_poblacion` is identical with the 8c and 8d
  lineages in the 16 states whose `code` links changed (04, 05, 07, 13, 14, 15, 16, 18, 19,
  20, 21, 22, 24, 29, 30, 32).

## The check (`LOC_LINEAGE_REPORT.md`)

Contradicted links, 8c → 8d:

| span | code | absorption | separation |
|---|---|---|---|
| 1990 → 1995 | 95 → **8** | 7 | 0 |
| 1995 → 2000 | 28 → **13** | 0 | 0 |
| 2000 → 2005 | 28 → **5** | 3 | 0 |
| 2005 → 2010 | 24 → **13** | 0 | 0 |
| 2010 → 2015 | 7 → 5 | 9 | 0 |
| ITER 2010 → 2020 | 9 → 6 | 0 | 1 |
| 2015 → 2020 | 5 → 4 | 1 | 0 |
| 2020 → 2025 | 1 | 19 → 20 (El Caudillo) | 0 |

Unexplained codes, 8c → 8d (leaving / entering): 1990 → 1995 438 → **207** / 725 → **173**
(*not listed* 229 / 552), 1995 → 2000 91 → 86 / 52 → 38, 2000 → 2005 52 → 48 / 42 → 38,
2005 → 2010 114 → 111 / 108 → 104, ITER 2010 → 2020 284 → 283 / 131 → 128, 2010 → 2015
80 / 368 → 361, 2015 → 2020 485 → 484 / 88, 2020 → 2025 168 → 167 / 79.

## Tests (`tests/test_cpv_geo.py`)

- Document: Las Cañadas one confirmed link, El Potrero 1995, no Luvianos link, Ejido
  Tultepec's separation, Tecojotal, El Vergel, the 1992 decree confirmed, 050190133 and
  Morelia's 160530378.
- Parser: the four shapes, «de1992»/«de2001», a code never dating a row, `_listed`, «.» in a
  list; `record_links` orients a duplicate with and without the other record's history.
- `repair_lists`: a digit off (the stating record; the only one in the municipality),
  unread when two fit; `lineage`: Luvianos cancelled, La Esperanza's same-day pair kept.
- `_REAL` (`test_loc_lineage_rebuilds_and_checks`): byte-identical rebuild; contradicted ≤
  1.5% of a span's links (was 3%); unexplained ≤ 1% outside the frames, 1990 → 1995 included
  (was 1.5%), the *not listed* codes there more than the unexplained.
- Full suite on the Mac: **1963 passed, 1 skipped** (35 min; 8c's count: the tests were extended, none added).

## Left

- The 8 `code` links 1990 → 1995 still contradicted: Rosarito's remnant (020040223, counted
  to 2000), Campeche's Conteo 1995 rows repeating Escárcega's 1990 decree on records that
  stay in Escárcega, Chihuahua's «Hasta este evento … 0522» / «cambia a la clave 0912» whose
  old code INEGI gave another locality, a reactivation that reuses the code (La Escondida):
  INEGI's records. The 13 at 1995 → 2000 not read one by one; at 2005 → 2010 Jalisco's San
  Ignacio Cerro Gordo moves (both codes in the ITER 2010 and 2020) and four others.
- The three same-day pairs (both records «Viene …»), El Caudillo's reversed «Forma parte»,
  San Luis Potosí → Villa de Pozos (a part, its statement undated).
- 8a's/8b's/8c's leftovers stand: 248 moves left unpaired (unchanged: looser names pair a few
  — «Sra.»/«Señora», «Block»/«Bloque» — and wrong ones too — Kilómetro Cuatro/Tres —), 31
  links on an unverified number, 4 undecided rival claims, the 11 pairs either side of the
  2015 cut, Campeche's records that end at the Censo 2010, 33 undated statements (mostly before
  1990; «11 de febrero de 201.»).
