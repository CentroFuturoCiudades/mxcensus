# CPV Unit 8e — CGPV 2000's occupation in SINCO groups (the CMO bridge)

Done **2026-10-13** (on the Mac; ENOE's two quarters through the loader, a probe of the panel
on `wsl`). HANDOFF candidate 1's «2000 occupation bridge», the user's choice over the 0.15.0
release (recommended), the small derived columns and the lineage leftovers. Gate: a sourced
bridge for every code CGPV 2000 uses, `derived=True` in all 32 states with no unmapped code,
the bridge checked on ENOE and against Censo 2010, tests green.

## Decisions (user, 2026-10-13)

| question | decision |
|---|---|
| the 37 CMO codes INEGI's table splits across SINCO groups (17.3% of 2000's employed) | **the ENOE panel's modal group** among the table's groups (recommended; over leaving them missing or a position rule for the farm codes) |
| the 13 codes CGPV 2000 uses that the table lacks (0.55%) | **the panel's group on enough evidence, else the CMO subgroup's only group, else missing** (recommended) |

Taken without asking: «missing» is group 99 «No especificado» (rule *not placed*), since
`derive` refuses a missing value in a categorical column by design (an unmapped code must
raise); the panel's evidence threshold for an absent code (10+ linked persons, 50%+ of them
agreeing); a split code takes the panel's group on any linked person (it only chooses among
the groups INEGI's table allows), and with none (4139) is *not placed*.

## The source: INEGI's comparison table

CGPV 2000 codes `OCUACTIV_C` in the Clasificación Mexicana de Ocupaciones (CMO, four digits,
1100–8390; 9999 not specified; its first two digits the 19 groups 7d checked against
C2KEM04). Every later edition codes SINCO (2010's CUO ≈ SINCO 2011, 2015 SINCO 2011, 2020 and
2025 SINCO 2019), whose two-digit group is `OCUPACION_C_COARSE` (6f).

INEGI published, with the SINCO 2011, *Tablas comparativas* between the SINCO and the CIUO,
CMO, CNO, SOC and NOC (SNIEG's 2012 SINCO presentation lists them among its products). The
current site no longer serves them; the Internet Archive keeps the file the old classifier
page linked, `…/clasificadoresycatalogos/doc/sinco_tablas_comparativas.xls` (archived
2014-02-26; «Actualización noviembre de 2012»; sha256 `2fa4813f…`). Its sheet `SINCO-CMO`
lists the SINCO unit groups (four digits) with the CMO codes each takes, a unit taking
several on the rows after it: **531 pairs, 430 SINCO units, 448 CMO codes**. The CMO there is
the one CGPV 2000 uses: **447 of its 460 codes, 99.45% of its employed** (weighted). INEGI's
ENOE note on the switch (2012-T3) warns there is not «una correspondencia uno a uno»: 37 of
the 448 codes take units in several SINCO groups.

## The bridge (`scripts/build_cmo_sinco.py` → `src/mxcensus/_yaml/cpv_cmo_sinco.csv`)

ENOE switched from the CMO to the SINCO in 2012-T3, and its rotating panel interviews the
same persons in consecutive quarters: **109,566 persons employed in 2012-T2 (coded CMO) and
2012-T3 (coded SINCO)**, linked on the person key and the visit (`n_ent` + 1). For each code:

| RULE | codes | 2000's employed |
|---|---|---|
| `table`: one SINCO group | 411 | 82.69% |
| `panel`: split by the table, the group most of its linked persons take among the table's groups (weighted by T3's `fac`) | 36 | 16.76% |
| `siblings`: absent from the table, the one group the table gives its CMO subgroup (1369 → 27, 1419 → 21, 1469 → 25, 5335 → 81) | 4 | 0.01% |
| `not placed` (99): 4139 (split, no linked person) and 9 absent codes — 5190 and 6290, «otros … no clasificados» (0.24%, 0.27%), 6131, 1429, 1439, 1490, 5509, 6109, 6139 | 10 | 0.55% |

No absent code reaches the panel's threshold: 5190 has 75 linked persons spread over 81, 82
and 16 (26% the largest), 6290 has 7. The large split codes: 8200 domestic workers → 96
(97% of 3,436 persons), 8303 → 53 (98%), 6270 → 31 (95%), 5230 → 73 (91%), 4109/4119 «otros
trabajadores agrícolas» → 91 (62%, 87%); the close calls: 7201 street vendors → 95 (46%;
42 44%), 5400 → 92 (55%), 8150 → 97 (50%). Every row records its evidence (`SHARE`,
`PERSONS`) and the table's SINCO units (`UNITS`); `docs/cpv/CMO_SINCO_REPORT.md` lists them.

`cpv_derived._ocup_cmo` (`derived=True`, CGPV 2000): `OCUACTIV_C` through the bridge, SINCO
2011's 59 → 52 (9 «otros … servicios personales» codes, as 2010's 5999), labelled as every
other edition; blank → «Blanco por pase»; a code the bridge lacks raises.

## Why not a position rule for the farm codes

INEGI's table sends most CMO farm codes (4100 «trabajadores en actividades agrícolas», the
crops 4101–4108) to SINCO 61 (farmers) only. On the panel 10–50% of those workers (4100:
36%) are coded 91 (agricultural support workers) once SINCO applies: SINCO separates laborers from farmers
by their role. CGPV 2000 has `SITTRA` «Jornalero o peón», but Censo 2010 — SINCO-coded,
same item — puts its jornaleros 55% in 61 and 43% in 91: position does not draw INEGI's
census boundary. The census coders also draw it unlike ENOE's: 91 is 6.05% of ENOE 2012-T3's
employed but 2.49% of Censo 2010's. The bridge keeps INEGI's table there; 2000's 91 (3.65%)
comes from the split codes 4109/4119/4134/4140.

## Checks (`CMO_SINCO_REPORT.md`)

- **On ENOE** (every employed person of 2012-T2 through the bridge against 2012-T3's SINCO
  groups, one quarter apart): within ±0.4 points in every group but the farm split (61
  +5.5, 91 −5.9), street vendors (95 +1.2, 42 −1.2) and 94 (−0.9, a group the CMO codes do
  not reach); dissimilarity 10.0 points. On the panel the linked persons' T3 group is the
  bridge's for 60.4% (people change jobs between quarters; coders differ).
- **Against Censo 2010** (ten years apart, plausibility): dissimilarity 10.7 points; 61 + 91
  15.1% → 12.2%, 99 2.44% → 0.98% (the not-placed and 2000's 9999), 42 7.3% → 8.6%.
- **All 32 states** `derived=True`: no missing value, 35,144,618 employed (Σ `FACTOR`), the
  report's shares. The 2000 constraints are unchanged (70; none on occupation).

## Tests (`tests/test_cpv_derived.py`)

- `test_derive_persons_2000_recodes`: 8200 → domestic workers, 9999 → «No especificado»,
  8190 → group 52, 6290 → 99, 4100 → 61, an unknown code raises.
- `test_cmo_sinco_bridge`: the file's contract (each rule's evidence, `UNITS`, 461 codes,
  13 absent, none placed by the panel among them).
- `test_cmo_sinco_rebuilds`: the script writes the bundled CSV byte for byte (skipped without
  `data/dict/sinco/` and the CPV 2000 mirror; ENOE through the loader).
- `test_source_codes_match_2020`: 2000's `OCUACTIV_C` as an own-code item (9999).
- Full suite on the Mac: **1966 passed, 1 skipped** (34 min; 8d + the bridge contract, the rebuild and 2000's `OCUACTIV_C` code list).

## Left

- The farm laborer boundary (61/91) differs between coders (ENOE vs the census); the bridge
  keeps INEGI's table. A user comparing farm work across 2000 → 2010+ should sum 61 + 91.
- 5190 and 6290 (0.51% of 2000's employed) stay «No especificado»: their CMO labels («otros
  …») place them in no single SINCO group, and the panel is diffuse.
- `OCUPACION_C_COARSE` only: no SINCO subgroup or unit for 2000 (the table maps units, but
  the splits multiply below the group).
