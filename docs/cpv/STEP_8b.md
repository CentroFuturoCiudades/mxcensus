# CPV Unit 8b — the audit of the large locality units

Done **2026-10-13** (on the Mac, which holds every ITER, the MG 2020 frame and the MG 2025
locality layers since 8a; `wsl` was reachable again but not needed). HANDOFF candidate 2's
«wider audit of the units joining localities of 2,500+», the user's choice over the 0.15.0
release, a 2015 locality edition and the small derived columns. Gate: every unit of
`cpv_locality_units` that joins two or more localities of 2,500+ read against INEGI's texts,
each wrong join traced to the rule that made it and fixed by a general rule (counted and
checked over the whole lineage, not only the large units), the lineage rebuilt and checked,
tests green.

## The audit

8a counted the units joining localities of 2,500+ at the span's ends (1990 → 2020: 138). 8b
widened it to **any ITER 1990–2020 and the span 1990 → 2025: 185 units** on 8a's lineage.
For each unit a scratch listing gave its large members (names and populations at every ITER,
the AHL's coordinates), the shortest path of links joining each to the unit's largest, and
four flags: more than 10 km apart on a path that is not code changes only, a path through a
smaller locality, a link stated on one record only, code changes only with both codes counted
at one ITER. Every unit was read, flagged or not.

**180 are right.** A city's conurbations: Tijuana's 17 large members up to 22.6 km from the
AHL's point for the city (the 2019–2024 updates), Mexicali, León's four of 1995, Morelia,
Zapopan, Juárez, Nogales, Ensenada, Mérida, Cuernavaca, Cabo San Lucas. Splits of one
locality into several: Toluca, Metepec, Los Reyes Acaquilpan, Texcoco, Tlaxcala, Tezontepec,
Chalco's Xico, the part of Pachuca in Mineral de la Reforma (2010). Moves into new
municipalities: San Quintín's (2020), Seybaplaya, Bacalar, Puerto Morelos, Tlaxcala's of 1995,
Xoxocotla, Coatetelco. Rosarito's remnant of the old code, Poza Rica's part in Tihuatlán, the
two Juan José Ríos joined into the new municipality's seat (2025).

**5 were wrong**, each through a different slip of INEGI's:

| unit | joined by | what happened |
|---|---|---|
| Telchac (3,496) + Mayapán (3,956), 82 km apart | 310490052 (Mayapán's «Mayapán», 7 inhabitants in 2000), absorbed by Mayapán in 2009 and listed by Telchac Pueblo in 2014 | Telchac's list «se conurba la 310490052 y 310490061» means its own 0052 and 0061, which state «Se conurba a Telchac Pueblo (0001)» that day |
| Córdoba + La Luz Francisco I. Madero (10,907) | «Acuerdo del 23 de febrero de 2001. Se conurba a Córdoba (0001).» | «Conteo de 2005. Se desconurba de Córdoba (0001).»: joined and left between 2000 and 2005, its own locality at both |
| Hermosillo + San Pedro el Saucito (3,366) | Hermosillo's 2019 list «260300535 y 260303510» | San Pedro el Saucito never states it, absorbs a locality itself that day, is counted in 2020 and is in MG 2025 |
| Pesquería (48,069) + Colinas del Aeropuerto (33,108) | «Se conurba a Colinas del Areopuerto (0001)» on Colinas' own record | it names itself (misspelled); 0001 is Pesquería's number (placed as unverified) |
| Túxpam + Santiago de la Peña (8,178), through Roberto Rocha (4 inhabitants) | «2019. Se conurba a Túxpam (0001)» | counted in 2020 on its own, then «2023. Se conurba a Santiago de la Peña (0083)» |

The same slips sat in smaller units: Ensenada's held an Aguascalientes code (010014958
listed for 020014958), Irapuato's and Zamora's a code one digit off (110170371 for 110170571,
161080030 for 161080034).

## The rules (`scripts/build_loc_lineage.py`)

Each rule was counted over the whole lineage and its links compared with every edition's
codes before it was kept.

### Parse

«A esta localidad se conurba a 220140470» (an «a» too many) and «A esta localidad se
conurban a las 190060218 y 190060379» list the absorbed (`absorbe`); `absorbida` no longer
matches right after «A esta localidad». Three texts: La Solana (Querétaro) had been read as
absorbed by its own Sección Noroeste.

### INEGI's slips in the lists (`repair_lists`)

A code in a list («A esta localidad se conurban las …», «De esta localidad se desconurba
…») that its own record never states, when exactly one locality a slip apart — its number in
another municipality or state, or one digit off — states the event into the listing record at
that edition without being listed, and no other listed code claims that one, is that
locality. **93 codes (81 absorptions, 12 separations)**: 66 with the number in another
municipality (6 in another state: 200270453 for 280270453, 600650090 for 300650090), 27 one
digit off; many listed codes have no AHL record at all. At the same edition, not only the
same day (5 of the 93 stated by the locality itself on another day of that edition).
One-to-one only (two list codes claiming 280331369 are left).

### The record's own name (`Resolver`, `parse`)

A locality number stated with the stating record's own name (`name_match` 2–3, or a
misspelling of it) and another existing locality's number, no locality of that number bearing
the name: the record names itself. `parse` keeps it only when the other record states the link
(«San Juan: Se fusiona a San Juan (0009)», which Xaltetipa 0009 lists: kept, confirmed);
otherwise no link. 3 statements: Colinas del Aeropuerto and a 1990 one dropped, San Juan kept.
A number no record has stays an unverified link (Rancho López «Se fusiona a López (4713)»:
it explains why its code leaves).

### The localities' own records (`lineage`, before the rival claims; `corrections`)

| rule | links | what |
|---|---|---|
| contradicted the same day | 2 absorptions, 5 separations | one record states an absorption, the other a separation of the same two localities the same day: the locality's own record decides (Zamora «Se conurba a Ciudad Melchor Múzquiz», Múzquiz «De esta localidad se desconurban las … 050200772», 15 June 2009; Zamora leaves the 2010 ITER) |
| joined and left | 57 pairs | an absorption and a separation of two localities at one edition cancel out (it joined and left, or left and joined again, between two editions) |
| counted on its own | 11 absorptions | the absorbed locality has a population of its own at that edition's census and only others state the absorption: dropped |
| moved | 31 absorptions | the same, its own record stating it: it takes effect at the first edition after whose census it has none (2025 after 2020) |
| moved | 14 separations | the separated locality has no population of its own at that edition's census (2000–2020) but one later: it takes effect at the first edition that counts it (San Miguel Contla and San Lucas Tlacochcalco, stated apart from Santa Cruz Tlaxcala at the Censo 2000, first counted at the Conteo 2005 — now confirmed there) |

**«A population of its own»** is the AHL's `Habitantes` (now read by the build, for this
only), and only a number of inhabitants. Against the ITER codes, by census:

| `TOT_HAB` | 1990 | 1995 | 2000 | 2005 | 2010 | 2020 |
|---|---|---|---|---|---|---|
| a number, in the ITER | 155,185 | 105,574 | 199,369 | 187,924 | 192,241 | 189,421 |
| a number, not in the ITER | 12 | 8 | 2 | 31 | 329 | 480 |
| «*», in the ITER | 13 | 92,449 | 1 | 1 | 0 | 2 |
| «*», not in the ITER | 3,679 | 4,250 | 42 | 5 | 43 | 1 |
| «0», not in the ITER | 15,202 | 53,876 | 60,130 | 81,484 | 87,515 | 87,051 |

A number is the ITER's locality (but INEGI's copies at code changes, 7u); «*» is a locality
the ITER does not list — in 1995 mostly a count the Conteo's ITER reserves, and also the
localities absorbed at that Conteo (Guerrero's «Conteo de 1995. Se conurba a Copalillo
(0001).», `TOT_HAB` «*»): so the separations of 1995 are not moved. The rule is the edition's,
not the statement's date: `Habitantes` is the ITER, which reflects every change up to the
cut (Quinta Isabel, «Se fusiona a La Cañada» in 2008 with a bare «Censo de 2010» row, has no
2010 population: its absorption holds at 2010). The census rows' own text was tried first and
disagreed with the ITER (Colonia Progreso: «Conteo de 2005.» but no 2005 population).

Against the codes: the 11 dropped are in every later edition (Dos Potrillos stays,
uninhabited: 8a's undecided rival claim is gone); the moves are right at their new edition
for 30 of 45; the other 15 stay contradicted, now only at the later edition — 13 at 2025, the
2020 absorptions INEGI's census counted and MG 2025 still lists (the AHL has no census after
2020 to tell).

## Result: 32,978 links (8a 33,210)

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|
| code | 0 | 3,571 | 2,328 | 1,920 | 904 | 2,846 | 840 |
| absorption | 0 | 1,952 | 1,557 | 2,772 | 3,156 | 6,666 | 2,150 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 71 | 150 | 252 | 905 | 309 |

- Against 8a: absorption −171 / +16, separation −87 / +10; code and counted-with unchanged.
  100 links newly confirmed (the list slips), none lost. Confirmed: absorption 81.1% →
  82.0%, separation 83.3% → 85.2%, code 77.2%.
- `cpv_loc_lineage()`: a link's `PERIOD` may now be later than its `DATE`'s edition (44
  links; the docstring says so).
- Units: 2000 → 2020 29,787 → 29,654 codes in 10,300 → 10,286 units; 1990 → 2025 50,919 →
  50,787 in 18,402 → 18,398. Chiapas 2000 vs 2020 (the module's example): 19,207 and 20,925
  units, 15,078 in common (19,206 / 20,923 / 15,077).
- **Audit: 185 → 180 units** joining two or more localities of 2,500+ (1990 → 2025, any
  ITER); 8a's count 138 → 134 (2000 → 2020: 116 → 112).
- `ahl._copies` reads the `code` links only, which did not change: the same rows.

## The check (`--check`, on the Mac; `LOC_LINEAGE_REPORT.md`)

Contradicted links (absorption / separation; code unchanged):

| span | absorption 8a | 8b | separation 8a | 8b |
|---|---|---|---|---|
| 1990→1995 | 14 | 7 | 0 | 0 |
| 1995→2000 | 1 | 0 | 0 | 0 |
| 2000→2005 | 19 | 3 | 1 | 0 |
| 2005→2010 | 31 | 0 | 3 | 0 |
| 2010→2020 | 38 | 0 | 7 | 1 |
| 2020→2025 | 13 | 19 | 0 | 0 |

Unexplained codes: 2005 → 2010 leaving 121 → 120, 2020 → 2025 leaving 170 → 169, the rest
unchanged (three codes the first trial left unexplained — Zamora, Casa Blanca, Bernabé Arana
— led to the same-day rule and to the census rule by edition).

The report gains **«Corrections»** (the list slips, the own-record rules, every moved and
dropped link) and **«Units joining localities of 2,500+»** (`large_units`, regenerated by
every `--check`: the count and each large member whose path deserves a look — 67 rows: far
28, one record 40, through a smaller locality 9, a remnant of the old code 3; all read in this
unit). `--check` reads the ITERs' names and populations (`edition_localities`) and the AHL's
coordinates (`points`, `mxcensus.ahl._degrees`).

## Tests (`tests/test_cpv_geo.py`)

- Parser: «A esta localidad se conurba a …» / «se conurban a las …» list the absorbed,
  «Esta localidad se conurba a Galeana (0001)» is its own; the record's own name (Colinas: no
  link; San Juan through `parse`: kept, both records; a number without a record: unverified).
- `test_loc_lineage_list_slips` (new): Telchac's list read as its own 0052 and 0061,
  confirmed; no Telchac link for Mayapán's code.
- `test_loc_lineage_own_records` (new): Zamora's same day, La Luz joined and left,
  Hermosillo's list dropped and Maccsa kept, Morelia's 0417 moved to 2020, San Miguel Contla's
  separation moved to 2005, San Lucas (never counted) left at 2000.
- `test_loc_lineage_large_units` (new): a town joined through a ranch, far and on one record,
  listed; a renumbered village not.
- `test_locality_lineage_document`: at most 50 links dated before their edition (44),
  absorptions and separations only. `lineage` returns three frames.
- `_REAL`: the bundled file equals a rebuild byte for byte; the check's thresholds hold.
- Full suite on the Mac: **1963 passed, 1 skipped** (34 min).

## Left

- The 15 moved links still contradicted at their new edition (13 at 2025): MG 2025 keeps
  those localities; nothing in the AHL tells after 2020.
- `code` links contradicted by the codes (1990 → 1995 97, then 28, 28, 25, 9, 1) are
  untouched: `Habitantes` is filed under a locality's last code, so it cannot say whether an
  old code was counted.
- The Conteo 1995's «*»: its separations are not moved, its absorptions not judged.
- 8a's leftovers: 248 moves without a code unpaired, 31 links on an unverified number (35),
  4 undecided rival claims (5: Dos Potrillos dropped) and the 2 «each states it as its
  origin».
- Lists with a wrong number of digits: «3000440059» in Córdoba's 1990 list (read as
  300044005, out of scope), «16053379 y 16053398» in Morelia's 2009 list (8 digits, not
  read).
- A 2015 locality edition (the user's choice in 7t).
