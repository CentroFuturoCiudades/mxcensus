# CPV Unit 8a — the locality lineage's leftovers

Done **2026-10-12** (on the Mac: `wsl` asked for a Tailscale re-login; the Mac holds every
ITER and the MG 2020 frame, and the MG 2025 locality layers were fetched from the bucket for
the check). HANDOFF candidate 2's «leftovers» of 7t, the user's choice over the 0.15.0
release, a 2015 locality edition and the small derived columns. Gate: 7t's three leftovers
(337 moves stated without a code, 233 unverified locality numbers, 14 rival claims) worked
through on INEGI's own records, the lineage rebuilt and checked against every edition, tests
green.

## What changed (`scripts/build_loc_lineage.py`)

The source is the same AHL export (2026-09-18); only the parser and the rules changed.

### Statements the parser missed

Each found among the leftovers, then counted over all 2,535,190 history rows:

| shape | rows | example |
|---|---|---|
| the code after a decree's sentence | 195 | «Viene del municipio Escárcega 009. Decreto No. 66 del 23 de junio de 1998. con clave de localidad 0144.» (Campeche's 1998 municipalities) |
| «con nombre y clave NAME (LLLL)» | 24 | «Viene del municipio de Rioverde (024) con nombre y clave El Tepetate (0278).» |
| «(MMM),con clave» (no space) | 10 | «Pasa al municipio Hecelchakán (005),con clave de localidad (0064).» |
| «, localidad NAME (LLLL)», «de la localidad (LLLL)» | 6 + | «Pasa al municipio Huichapan (029), localidad El Betel (0119).» |
| «, NAME con clave de localidad (LLLL)» | 1 + | «Pasa al municipio Huichapan (029), El Jarillal con clave de localidad (0123).» |
| «en donde / en el que tenía la clave (LLLL)» | 7 | «Viene del municipio Manuel Doblado (008) en donde tenía la clave (0313).»; «Pasa del municipio de San Luis de la Paz (033) en el que tenía la clave (0169) al …» (a provenance) |
| «Anteriormente tenía la clave Y» | 2 | 4 or 9 digits («… la clave 250170584»: 7t's pattern would have read 4) |
| «y parte de las localidades LIST» | 8 | «A esta localidad se conurban las 151060169, 151060189 y parte de las localidades 151060125, 151060152 y 151060158.» |
| a name after the number | 3 | «Se fusiona a (0321) Los Laureles.», «Se desfusiona de (0322) Nuevo Progreso Dos.» |
| a 4-digit number after «, con clave» | — | «Conurbada a Tenabo, con clave (0001).» (7t read the name «Tenabo, con clave») |
| «se censó con clave de localidad (LLLL)» | 1 | its own number at that census (7t read the name «clave de localidad») |

Patterns sharing a name now pool their matches (`statements`; before, a second `viene_estado`
pattern overwrote the first's). A move stated without the code beside an absorption or a
separation on the same row places that link in the municipality it moves to or comes from
(«Pasa al municipio Tultitlán (109). Se conurba a San Pablo de las Salinas (0025).»).
Stated links: 75,563 → 75,839.

### Names (`name_match`, `Resolver`)

- Abbreviations and ordinals spelled out (`_WORDS`: «Cd.», «Ing.», «Sn.», «Gral.», «No.»;
  «I/Uno/1ro», «II/ll/Dos/2do» …), more generic words («Ciudad», «Cabecera»,
  «Fraccionamiento», «Barrio»).
- A misspelling is level 1 (`difflib` ratio ≥ 0.85 on the distinctive words: «Cuidad
  Obregón», «Ciudad Vicroria», «Tlacopa» for «Tlacoapa», «Hemosillo»); the `Resolver` tries
  it only when no candidate matches otherwise (so a typo never overturns a real match
  elsewhere, and the build stays at ~28 s: matching every candidate fuzzily took 68 s).
- **Placeholders match nothing** (`_UNNAMED`: «Localidad sin nombre», «Ninguno», «S/N»; a
  name of generic words only, «La Ciudad», is no placeholder):
  «Se fusiona a Ninguno (0553)» had been placed by the name «Ninguno» in another
  municipality (two absorptions corrected), and two «Rancho Sin Nombre» are no evidence of
  one locality.

Placed locality numbers (all statements, any date): own municipality 29,347 → 29,413, other
160 → 114, **unverified 233 → 173**. Of the unverified, **35 links of the lineage** rest on one
that no other record states (29 absorptions, 4 separations, 2 counted-with): most name an
absorber that has no record under that code (its history is filed under a later one), so the
stating record's municipality stays the default; the rest are INEGI's typos too far for the
fuzzy test («Tukuch»/«Tikuch») or another name altogether.

### Moves stated without a code (`pair_unkeyed`)

7t paired them only when one statement on each side had the very same name. Now, per record
and move (in scope):

| what became of them | statements |
|---|---|
| confirm the code link the other record states (when it is the only one) | 393 |
| beside an absorption / a separation that places it | 18 / 1 |
| paired with the other side's statement by name (any name in the records' histories, `name_match` ≥ 2, each the other's only best: renamed localities pair) | 44 (22 moves) |
| one side: the only record of that name in the other municipality, there at that edition (a destination that starts by the cut and lasts past the previous one; an origin there at the previous edition and gone by this one), stating no other code link | 31 |
| coded elsewhere | 8 |
| **left: no record of that name** | 186 |
| **left: history here** (a new record whose history goes back before the move: the old code was filed under it, no other record holds it — mostly «Reactivación … Viene del municipio …») | 50 |
| **left: several of that name** (unnamed ranches, duplicate names) | 12 |

7t counted 337 unpaired *statements* (several per record possible); the 248 left here are
one per record and move, and 50 of them have nothing to pair with by construction.

### Rival claims (`lineage`)

7t kept the claim stated on both records, else a name-verified one, one stated on the
locality's own record, a new code with the locality's name — applied together. Now, in this
order, the first rule that tells the claims apart decides (each decision logged):

1. **the target states another origin**: a `code` claim not stated on its target, whose
   target's own record states another origin at that edition, is dropped (26 localities).
   Every one keeps the target with the locality's name — Campeche 1998's old records point
   one or two numbers off (Monterrey → 3413 «La Esperanza», not 3414 «Monterrey»; La Elvira
   I → 3299 «La Elvira Dos»), Echeverría Castellot 0100 → 0099, San José (Q. Roo) 0381 →
   0380, Emiliano Zapata (Santiago Sochiapan) 0032 → 0031 (INEGI wrote the old number; the
   population agrees, 402 → 425 against 16);
2. its number matched its name (17); 3. stated on its own record (59); 4. the closest name
   (19).

| rule | localities |
|---|---|
| stated on both records | 66 |
| stated on its own record | 59 |
| the target states another origin | 26 |
| the closest name | 19 |
| its number matched its name | 17 |
| several stated on both records (kept) | 3 |
| each states it as its origin (kept) | 2 |
| undecided (kept) | 5 |
| undecided, the locality keeps its code (dropped) | 1 |

- **San Antonio (190100027, El Carmen NL)**: «Pasa al municipio de General Escobedo (021) con
  clave (0001)» on its record, «Viene del municipio de China (010) con clave (0027)» on El
  Carmen's seat; its record goes on under 190100027 (Censo 2010, a 2011 move, a 2018
  conurbation), so neither is a renumbering: both dropped. **7t's units joined Ciudad General
  Escobedo (454,967 in 2020) with El Carmen's seat (11,583) for every span over 1995** —
  below 7t's 20,000+ audit.
- **Toluca's partial absorptions** (La Concepción, La Trinidad, El Arenal: «parte de la
  localidad se conurba a Toluca de Lerdo (0001) y la otra parte a …»): the absorbers' «y parte
  de las localidades …» now parse, so all six claims are confirmed and kept; El Arenal's
  second absorber, Cacalomacán (13,796), joins Toluca's 1990 → 2020 unit as San Mateo
  Otzacatipan did in 7t.
- **Kept, each target stating the locality as its origin**: Cerro de Torres (Cosamaloapan →
  Carlos A. Carrillo, 370 → 45 + 288: a split), La Unión (Carmen → Candelaria, two «La Unión»).
- **Undecided (kept)**: 020041186 and 040030194 (no record of the old code; two new codes
  claim it), Los Corrales 030010074 (its record says 0150, 0189's says it), Dos Potrillos
  310130098 (two absorbers list it; it goes on, uninhabited), 260291473 (two absorbers, no
  record).
- An unkeyed statement confirms a code link only when it is the only one into or from that
  municipality: El Carmen (2510) «Pasa al municipio Candelaria 011.» would otherwise have
  confirmed both new codes claiming it (0075 «El Carmen», 0215 «La Granada»).

## Result: 33,210 links (7t 33,161)

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|
| code | 0 | 3,571 | 2,328 | 1,920 | 904 | 2,846 | 840 |
| absorption | 0 | 1,961 | 1,558 | 2,803 | 3,197 | 6,741 | 2,148 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 75 | 158 | 279 | 931 | 321 |

- Against 7t: code +61 / −13, absorption +3 / −2; 588 links newly confirmed (541 of them
  Campeche's 2000 moves). Confirmed: **code 72.7% → 77.2%**, absorption 81.1%, separation
  83.3%.
- Every added and removed link was read against the records' texts and names (the session's
  diff); three of this unit's own bugs were caught that way and fixed before the build (a
  name after the number swallowing «del municipio de San Martín Chalchicuautla»; a 9-digit
  «anteriormente» read as 4; a move with its code after a decree confirming its own link),
  and a fourth reading the code (a name of generic words only, «La Ciudad», taken for a
  placeholder: no link changed, 15 placements verified).
- Units: 2000 → 2020 29,784 → 29,787 codes in 10,297 → 10,300 units; 1990 → 2025 50,819 →
  50,919 in 18,349 → 18,402. The module doc's Chiapas example is unchanged.
- **Audit at 2,500+**: units joining two or more localities of 2,500+ (either census): 1990 →
  2020 139 → 138 (Escobedo + El Carmen gone; Toluca's gains Cacalomacán), 2000 → 2020 116,
  the same units.

## The check (`--check`, on the Mac; `LOC_LINEAGE_REPORT.md`)

- Contradicted links: **unchanged in every span** (the new links contradict no edition's
  codes).
- Unexplained codes: 1990 → 1995 leaving 447 → 437, entering 811 → 809; 1995 → 2000 leaving
  100 → 91; the rest unchanged.
- The report gains the moves stated without a code, the rival claims by rule and every
  locality left with several claims or none.

## The Archivo Histórico de Localidades (7u)

`ahl._copies` reads the bundled lineage's `code` links (rows INEGI copied to a new code since
2010). The only changed link dated after the 2010 census (San José, Q. Roo) has unequal 2010
counts: `load_ahl_poblacion(copies=True)` flags the same 490 rows in states 04, 23 and 30
with either lineage; `tests/test_ahl.py` passes.

## Tests (`tests/test_cpv_geo.py`)

- Parser: the new shapes, the absorption/separation tuples (8/6 groups),
  names (abbreviations, ordinals, misspellings, placeholders), the fuzzy fallback, a move
  beside an absorption.
- `test_loc_lineage_unkeyed_moves` (new): a confirmation, a renamed pair, a one-side link to
  the only «San Carlos» there in 1995 (not the one gone by 1960).
- `test_loc_lineage_rival_claims` (new): the target states another origin (Las Delicias),
  San Antonio dropped, Cerro de Torres kept.
- `test_locality_units`: Escobedo apart from El Carmen 1990 → 1995 and 1990 → 2020.
- `_REAL`: the bundled file equals a rebuild byte for byte; the check's thresholds hold.
- Full suite on the Mac: **1960 passed, 1 skipped** (34 min).

## Left

- The 248 moves left unpaired (186 without a record of that name in the other municipality,
  50 whose old code has no record, 12 among namesakes) and the 35 links on an unverified
  number: nothing more in the AHL decides them.
- 5 undecided rival claims (kept: a unit only gets coarser) and the 2 «each states it as its
  origin».
- A wider audit of the 138 units joining localities of 2,500+ (1990 → 2020): 7t reviewed the
  20,000+ ones.
- A 2015 locality edition (the user's choice in 7t).
