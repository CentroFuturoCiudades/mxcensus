# CPV Unit 8g — the locality lineage's last leftovers

Done **2026-10-14** (on the Mac; the check's mirror is a scratch directory of symlinks to
`data/parquet`'s ITERs and MG 2010/2015/2020 layers plus the MG 2025 `l`/`lpr` layers of the
Pooch cache, as in 8d; `wsl` not needed). HANDOFF candidate 2, the user's choice over the
0.15.0 release (recommended), a CPV user guide and a cross-edition ITER panel. The scope was
agreed on the probe: (1) the wrong kinds the check shows (Villa de Pozos, El Caudillo), (2)
the statements without a date, (3) the rest documented as final. The probe then found the
moves between states the parser skipped (311 of 649 statements); the unit took them too (the
user was told). The user's decisions: the 20 absorptions at 2020 → 2025 that the MG 2025 frame
still lists stay at 2025 (the build stays AHL-only); `CONFIRMED` stays per edition (8c's open
question, closed). Gate: every new rule general (no code listed by hand), the lineage rebuilt
and checked against every ITER and frame, `load_ahl_poblacion` unchanged, tests green.

## The probe: what decides the leftovers

- **The 248 moves left unpaired** (8a): no record of that name on the other side, several,
  or the old code filed under the new record. The AHL's coordinates do not decide them: 124
  have no record of the right timing within 1 km of the stating record, 73 have several, 49
  have one. Names rarely agree, and the old records' coordinates are rough (8a's own
  municipality-level one-side links include pairs 20–166 km apart, by the same
  coordinates). The ITERs' names (the mirror) pair 9 of the 248. Left.
- **The 55 `code` links the editions contradict** (8d): read again, with the AHL's
  `Habitantes`. 174 `code` links have a `FROM` counted at a census after the link. Most are
  codes INEGI gave to another locality later, or localities that came back (Chiapas's and
  Veracruz's municipal moves of 1995, back by 2005). A unit built from codes cannot separate
  a reused code from the locality that left it (`cpv_locality_units` over a long span joins
  both). Left, documented.
- **What the check flagged at 2020 → 2025**: one wrong kind (Villa de Pozos) and four
  absorptions stated the wrong way round (El Caudillo, El Chaparral, two Ensenada ranches).
  The other 16 contradicted absorptions are 8b's *moved* ones: every census to 2020 still
  counted them and the MG 2025 frame still lists them (the user's decision: kept).

## Villa de Pozos: a part, not the city

Decree 1074 of 22 July 2024 created Villa de Pozos (24059). Its seat's record, 240590001,
says «Viene del municipio de San Luis Potosí (028) con clave de localidad (0001)». So 8f had
`code` 240280001 → 240590001: the city of San Luis Potosí (845,941 inhabitants in 2020)
became the new seat at 2025, a contradiction (the city is in the MG 2025 frame). The city's
own record has an undated last row: «Parte del territorio de la localidad San Luis Potosí
(0001) del municipio de San Luis Potosí (028) se integra al municipio de Villa de Pozos (059)
con clave de localidad (0001).» The parser did not read it.

- **Parse** (`parte_integra`): «Parte del territorio de la localidad X (LLLL) del municipio …
  (MMM) se integra al municipio … (NNN) con clave de localidad (KKKK)» is a separation, the
  new code leaving the locality (the only such statement in the AHL).
- **Rule** (`lineage`, *a part*): a move to a new code that the old locality's own record
  calls a part is that part. The old record states a separation and no move at that edition,
  so the new record's `code` claim becomes the separation (both records state it:
  `CONFIRMED`). Amaque (Hidalgo, 2014–2015) moved and came back with a part: its record
  states the move too, so the rule leaves it alone.
- The city's statement is undated: the dating below gives it the decree's date.

Result: `separation` 240590001 → 240280001 at 2025 (2024-07-22, confirmed), no `code` link.
The unit `cpv_locality_units(2020, 2025)` still joins the two (every kind joins). It should:
the new seat's territory was part of the city in 2020.

## Each absorbed by the other

INEGI states some absorptions both ways. La Zorra (240470089) «Forma parte de la localidad
El Caudillo (La Zorra) (0085)» at the Conteo 1995, and was never counted again. El Caudillo
(0085), counted at every census to 2020, says «Forma parte de la localidad 240470089» at the
Conteo 2005. 8b's census rule then moved that link to 2025 (El Caudillo counted on its own),
where the MG 2025 frame contradicts it. At El Chaparral (San Martín Chalchicuautla 0105 and
Tamazunchale 0114, Conteo 1995), each record says it fuses into the other the same day; 0105
had two dwellings in 1990 and is never counted again.

**Rule** (`lineage`, *the other way round*, before the census rule): two localities each
stated absorbed by the other, with no separation between them. When only one of them has a
population of its own at a census from the first statement's edition on, that one absorbed
the other, and its own absorption is dropped. Four links: El Caudillo, El Chaparral, and two
Ensenada ranches (020024715/4843, 020024716/4845, update of 15 June 2011). Kept where both
are counted afterwards (San Miguel Vindhó and Santa María Ilucán, Tula, 1995 and 2010) or
neither (Ensenada's two salt works, 2024).

## Moves between states the parser skipped

7t's patterns read «Pasa al estado de X (NN) en el municipio … (MMM) con clave …». 311 of
the AHL's 649 statements of a move between states were written otherwise:

- **With the code** (39 statements, 30 in scope): a 3-digit state code «(019)», «(032)»; a
  4-digit municipality «(0027)»; «municipio» without «del» or «en el», «del de municipio»;
  «clave (0890)» without «con», «con la clave»; «con clave de localidad la Morita (0038)»;
  «municipio (027), Ramos Arispe (0154)»; «(29 )»; «Concordia(004)»; the whole code «Viene
  del Estado de Jalisco con clave (140530848)». The patterns `pasa_estado`/`viene_estado`
  gain tolerant forms (`_EDO`, `_EMUN`, `_SKEYS`; every older match kept, each new match
  read one by one), plus `pasa_clave`/`viene_clave`.
- **With only the state** (266 statements, 44 in scope, mostly the Conteo 1995): «Pasa al
  Estado de Durango (10).», «Viene del Estado de Guerrero», «Pasa al Estado de Zacatecas (32)
  municipio (051).» (`pasa_estado_sin`/`viene_estado_sin`). The state's code comes from
  its number, else from its name (`state_code`, `_STATES`), and the municipality when
  given. `pair_unkeyed` pairs them like the moves inside a state: the state, or the
  municipality, takes the municipality's place. With only the state named, the one-side
  match takes the only namesake within 10 km by the AHL's coordinates (`_NEAR_KM`, `xy`):
  a whole state holds namesakes far away. Cuadrilla Vieja (Tejupilco), «Pasa al estado de
  Guerrero», is not Guerrero's Cuadrilla Vieja, 165 km off. The nine linked are 0.05–1.4 km
  apart. Among them is Reforma el Alto: 1,008 inhabitants in 1995 under a Veracruz code,
  back in San Luis Potosí's 240160023 in 2000.
- Left unread: 6 (a state without its number before a municipality and code, Mainero 1995;
  no municipality, Zacatecas «con clave de localidad (0524)»; 1990 and earlier).

Of the 44 in scope: 9 linked by name and place, 3 by name (the municipality given), 2 confirm
a code link, 30 left (18 no record of that name, 10 none of that name nearby, 2 several).

## Statements without a date

36 links come from a history row without a date of its own (8f's 33, + 3 the new patterns
read). **Rule** (`date_statements`, after `parse`; `Link` now carries its row, `row`):

1. *the other record's date*: the same link stated on another record (same pair, kind and
   direction; else the pair stated any way) on or after the record's previous dated row and
   by its next one (`INDICE` order), when that gives one date: 20 rows. They include «Decreto
   No. 162 del 01 de marzo de .» (San Francisco de los Romo, 1992), «Decreto Número 421 del
   11 de febrero de 201.» (Bacalar, 2011) and San Luis Potosí's part (2024-07-22);
2. *its neighbours*: the next dated row's date, when every day after the previous dated row
   and up to it falls in one edition. On a record's first row, the record starts there and
   the next row's edition applies. 7 rows, e.g. Carlos y Abel's three «Se desconurba de la
   localidad 190440001» before the Censo 2010; 8b's rule then moves them to 2015 (counted
   only in 2020).

The rows take the date too, for `pair_unkeyed`. 4 links stay undated (out of scope). Tepeji's
window runs across two editions (its row sits between the Conteo 2005 and the Censo 2010, and
the 2005 cut is 30 October). Three have no later row: «Pasa al estado de Sinaloa» after the
Censo 2020, Cancún after 1980, Chalma after 1930.

## Result: 32,933 links (8f 32,905)

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|---|
| code | 0 | 3,540 | 2,332 | 1,884 | 897 | 452 | 2,391 | 840 |
| absorption | 0 | 1,957 | 1,557 | 2,770 | 3,153 | 1,387 | 5,292 | 2,147 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 71 | 150 | 253 | 312 | 609 | 310 |

- Against 8f: 7 links out:
  - Villa de Pozos's `code` link;
  - the four reversed absorptions;
  - Cuadra el Milagro's absorption by Esperanza: its separation, now dated, cancels it at 2010 (*joined and left*);
  - 050050146's move to Nuevo León in 2007 and back in 2008 (*moved and moved back*, once the return was read).
- 35 links in: 30 `code` (the state moves), 1 absorption, 4 separations. 30 links newly confirmed, none lost.
- Confirmed links: 26,249 → 26,282.
- Units:

  | span | 8f | 8g |
  |---|---|---|
  | `cpv_locality_units(2010, 2020)` | 16,655 codes in 6,250 units | 16,658 in 6,250 |
  | `cpv_locality_units(1990, 2025)` | 50,754 in 18,387 | 50,813 in 18,415 |
  | `cpv_locality_units(2020, 2025)` | 5,517 in 2,220 | 5,511 in 2,217 |
- `ahl._copies` reads the `code` links: `load_ahl_poblacion` is identical with the 8f and 8g
  lineages in the 19 states the changed links touch (05, 08, 10–16, 19–25, 28, 30, 32).
  Only links dated after a census from 2010 on can flag a copy, and the two such links
  have targets without population rows.

## The check (`LOC_LINEAGE_REPORT.md`)

Contradicted links, 8f → 8g: 2020 → 2025 `code` 1 → **0**, absorption 20 → **16**; every
other span unchanged (1990 → 1995: 8 and 7; the `code` links of 1995 → 2000, 2005 → 2010:
13 each). Unexplained codes leaving / entering:

| span | leaving | entering |
|---|---|---|
| 1990 → 1995 | 207 → 201 | 173 → 172 |
| 1995 → 2000 | 86 → 82 | 38 |
| 2000 → 2005 | 48 → 47 | 38 |
| 2005 → 2010 | 111 → 109 | 104 → 103 |
| ITER 2010 → 2020 | 283 | 128 → 125 |
| 2010 → 2015 | 80 | 361 → 358 |
| 2015 → 2020 | 484 | 88 |
| 2020 → 2025 | 167 → 166 | 79 |

The report has a new section, «Statements without a date» (every dated row, the four left).
«Moves stated without a code» now covers the states (*by name and place*, *none of that
name nearby*). The corrections table adds *a part* and *the other way round*.

## Tests (`tests/test_cpv_geo.py`, +2)

- Document: Villa de Pozos's separation (2025, 2024-07-22, confirmed) and no `code` link, El
  Caudillo, a confirmed move from Nuevo León to Tamaulipas (3-digit state code), Reforma el
  Alto at 2000, Cuadrilla Vieja unlinked.
- Parser: the state shapes (six `viene_estado`, Concordia's `pasa_estado`, the whole code),
  the state-only shapes and one refused (a code without a municipality), `state_code`,
  `parte_integra`.
- New `test_loc_lineage_dating` (`date_statements`: both rules, a window across two editions
  left undated; then *a part* in `lineage`) and `test_loc_lineage_unkeyed_states` (a namesake
  near and one far; without coordinates nothing links).
- `test_loc_lineage_own_records`: *the other way round* (El Caudillo dropped, Vindhó's pair
  kept).
- `_REAL` (`test_loc_lineage_rebuilds_and_checks`): byte-identical rebuild, the thresholds
  of 8d hold.
- Full suite on the Mac: **1976 passed, 1 skipped** (34 min; 8f 1974 + the 2 new tests).

## Left (final: nothing in the AHL decides them)

- 248 moves left unpaired inside states + 30 between states (coordinates and the ITERs'
  names do not pair them; see the probe), 31 links on an unverified number, 4 undecided
  rival claims, the 2 «each states it as its origin».
- `code` links on codes INEGI reused or that came back (174 with `FROM` counted later): a
  code-based unit joins the reused code's locality to the one that left it over a long span.
- The 16 absorptions at 2020 → 2025 that the MG 2025 frame still lists (the user's decision:
  kept); Campeche's records that end at the Censo 2010 (the AHL's gap); the 11 pairs either
  side of the 2015 cut; the 4 undated links; the 6 unread state statements.

## Release

With the user's go-ahead (2026-10-14), 7v–8g as **0.15.0** (`pyproject.toml`, `uv.lock`):
the Mac's full suite on 8g, **1976 passed, 1 skipped** (35 min); `main` fast-forwarded to
the release commit, tagged `v0.15.0` and pushed with `cpv-integration`; `wsl` pulled. No
data changed (registry 4276; the lineage, the CMO bridge and the dictionaries are bundled).
