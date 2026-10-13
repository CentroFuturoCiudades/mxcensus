# CPV Unit 8c — the EIC 2015's locality edition

Done **2026-10-13** (on the Mac, which holds every ITER and the MG 2010, 2015, 2020 and 2025
locality layers; `wsl` not needed). HANDOFF candidate 2's «a 2015 locality edition», the
user's choice over the 0.15.0 release (recommended), the lineage leftovers and the small
derived columns. Gate: the EIC 2015's cut found on its frame, the lineage rebuilt with a 2015
edition and checked against the MG 2015 frame, `cpv_locality_units` taking 2015, tests green.

## The edition: the MG 2015 frame

The EIC 2015 publishes no ITER, and its microdata name only the localities of 50,000+
(`LOC50K`: 215, all in the frame, the ITER 2010 and the ITER 2020). Its locality codes are its
frame's — INEGI's closure cartography of the survey (6h, `mg_{l,lpr}_2015_NN`): **304,494
codes** (`l` + `lpr`, `CVEGEO[:9]`), like MG 2020 (300,690) and MG 2025 (296,850) listing the
uninhabited localities too; the ITER 2010 has 192,247 and the MG 2010 frame 192,244 (the
ITER's, ±6 and 9). 7t had left 2015 out (`cpv_locality_units(…, 2015)` raised).

## The cut: 30 April 2015

On the data, as 7t's cuts: every link dated around 2015 against the MG 2015 frame (a `code`
or `absorption` reflected when `FROM` is gone, a `separation` when `FROM` is there):

| month | reflected | not |
|---|---|---|
| 2014-10 … 2015-02 | 274 | 4 |
| 2015-03 | 85 | 5 |
| 2015-04 | 358 | 4 |
| 2015-05 | 0 | 12 |
| 2015-06 … 2015-09 | 1 | 77 |
| 2015-10 … 2015-11 | 2 | 724 |

The geostatistical update of **15 April 2015** is in the frame (356 of 360), one dated 30
April too; none from May on (7 May: 0 of 1; 15 May: 0 of 11). `EDITIONS["2015"] =
2015-04-30` (7t's guess from the product). The AHL also writes the survey's own rows
(«Intercensal 2015. Actualización Geoestadística del 16 de febrero de 2015.», «Encuesta
Intercensal 2015.»; about two dozen): dated by their text, inside the cut.

## Why a link's date is not enough: new municipalities

Half the links dated 2011 were not in the frame: Chiapas's **decree of 23 November 2011**
moved 428 localities into El Parral (131), Emiliano Zapata (108) and Mezcalapa (189), which
INEGI's frame has only from 2020 (the municipal lineage, 6a: 07120–07125 created 2015 → 2020);
the MG 2015 frame keeps their old codes. A 2015 dated by the decree would have made
`cpv_locality_units(2015, 2020)` lose them (old code in 2015, new code in 2020, no link
between).

**Rule** (`lineage`, after the rival claims — which compete at the edition of their date —,
`created` = `mun_frames()`, the bundled municipal lineage's `hasta`): a link with a code in a
municipality that no frame has yet at its edition takes effect at the first frame that has it,
merged with the link stated there if any (that statement's date; *its municipality is new*):

| from | to | kind | links |
|---|---|---|---|
| 2015 | 2020 | code | 430 (Chiapas 428, Puerto Morelos 2) |
| 1995 | 2000 | code | 4 (Calakmul, Candelaria: created 1996/1998; merged with their 2000 links, now confirmed) |
| 2010 | 2015 | code | 1 (Bacalar's 0257: «Censo de 2010» on its record, the decree of 2011) |
| 2005 | 2015 | absorption | 1 (two Bacalar codes, an update of 2000 filed under the last codes) |

The rule first ran before the rival claims and moved one claim of a pair out of its rivalry
(230041373 → Puerto Morelos 0093, whose target states another origin: kept twice); after
them, nothing changes there. A merged link keeps the later statement's date: with the earliest
(2010-06-12) Bacalar's 0257 lost its copy of 2010 in `load_ahl_poblacion(state=23)`.

## The census rule over a frame without a census

8b judges an absorption by the census of its edition (a population of its own there: moved
past it, or dropped when only others state it) and moves a separation to the first census
counting the locality. 2015 has no census (the AHL's `Habitantes` stops at 2020):

- an absorption at 2015 is judged by the **next census** (2020: `_census_from`) — as 8b
  judged it at 2020 —, unless the pair separates by then (Camino Real a San Pedro, «Se fusiona
  a Ixotitla» 15 April 2015, «Se desfusiona» 15 June 2019: absorbed at 2015, apart at 2020;
  8b had cancelled the pair);
- an absorption moved past the 2010 census goes to the first edition after the censuses that
  go on counting it — **2015** —, or to the edition **another record states it** up to the
  next census: of the 7 that 8b moved 2010 → 2020, 5 are stated again in 2019–2020 by the
  other record and are still in the MG 2015 frame (Rancho Fátima, Ensenada: listed by Las
  Lomas on 15 March 2010, counted in 2010, «Se fusiona a Las Lomas» on its own record in
  2019) → 2020, merged and confirmed as in 8b; the other 2 are gone from the frame → 2015;
- a separation goes to the edition after the last census without it: 10 that 8b moved to
  2020 go to **2015**, all ten in the MG 2015 frame.

## Result: 33,005 links (8b 32,978)

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|---|
| code | 0 | 3,567 | 2,328 | 1,920 | 903 | 454 | 2,393 | 840 |
| absorption | 0 | 1,952 | 1,557 | 2,771 | 3,156 | 1,389 | 5,295 | 2,151 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 71 | 150 | 252 | 309 | 609 | 309 |

- 8b's 2020 links split into 2,152 at 2015 and 8,297 at 2020. Against 8b otherwise: 6 links
  merged by the new-municipality rule; 11 pairs that 8b cancelled as «joined and left» at 2020
  now straddle the cut (one link at each edition, 22); 11 links that their two records date
  on either side of the cut become two one-record links (10 lose `CONFIRMED`; 5 gain it in
  the merges). Confirmed: code 77.3%, absorption 82.0%, separation 84.9% (8b 77.2%, 82.0%,
  85.2%).
- `cpv_loc_lineage()`: 475 links take effect after their date's edition — 430 for a new
  municipality, 45 by the census rule (8b 44).
- Units: `cpv_locality_units(2010, 2015)` 3,506 codes in 1,356 units, `(2015, 2020)` 13,428 in
  5,138; joined, they give `(2010, 2020)` exactly (16,662 in 6,251; 8b 16,644 in 6,244: the
  11 pairs). 1990 → 2025 50,800 in 18,402 (8b 50,787 in 18,398); Chiapas 2000 vs 2020 (the
  module's example) 19,206 and 20,924 units, 15,077 in common (8b 19,207 / 20,925 / 15,078).
- `ahl._copies` reads the `code` links' dates: no 2010 or 2020 census falls between an old and
  a new date, so `load_ahl_poblacion` is unchanged (compared in states 02, 04, 07, 23).

## The check (`--check`, on the Mac; `LOC_LINEAGE_REPORT.md`)

`edition_codes` reads the MG 2015 frame; `_spans` adds the frames after the ITERs: **ITER 2010
→ MG 2015 → MG 2020 → MG 2025** (the ITER 2010 → 2020 span stays):

| span | code contradicted | absorption | separation | leaving unexplained | entering unexplained |
|---|---|---|---|---|---|
| 2010 → 2015 | 7 of 454 | 9 of 1,389 | 0 of 309 | 80 of 1,773 | 368 of 114,020 |
| 2015 → 2020 | 5 of 2,393 | 1 of 5,295 | 0 of 609 | 485 of 22,469 | 88 of 18,665 |

The 9 absorptions at 2010 → 2015 are mostly pairs dated by their two records either side of
the cut (Prolongación Sinaloa Norte, 090090307: listed by Villa Milpa Alta on 15 March 2015,
«Se conurba a Villa Milpa Alta» on its own record on 15 May 2019; the frame sides with the
later). The leaving codes left unexplained are Campeche's (51 of 80, 436 of 485): records
whose history ends at the Censo 2010 without a word, gone from every later edition (also 248
of the ITER 2010 → 2020's 284). The entering ones at 2010 → 2015 are the frame's localities the AHL has
no record for (22,405 explained as *not in the AHL*) or records from a later census (*record
starts later*, 471).

The check itself (it changes no link):

- a pair's last link in a span decides (absorbed at 2015, separated again at 2020: not
  contradicted in the ITER 2010 → 2020 span);
- the AHL's flags are read over every edition in the span (the ITER 2010 → 2020 span would
  otherwise lose the rows up to 2015's cut);
- the earlier edition's flags from the census before it on (2020: since 2010, the rows up to
  the 2015 cut too — as 8b read them);
- «Localidad Inexistente» (16,986 rows) and «en tapias o ruinas» without «baja» (42) count as
  *removed*;
- *record starts later*: a frame lists a locality the AHL records only from a later census.

Unexplained codes against 8b's report: leaving 2000 → 2005 54 → 52, 2005 → 2010 120 → 114,
ITER 2010 → 2020 357 → 284, 2020 → 2025 169 → 168, 1990 → 1995 437 → 438 (a Campeche code
whose move into Calakmul now takes effect at 2000); entering 1990 → 1995 809 → 725 (84 records
start later), 1995 → 2000 58 → 52, 2000 → 2005 44 → 42, 2005 → 2010 110 → 108, ITER 2010 →
2020 134 → 131, 2020 → 2025 79. Contradicted links: 1990 → 1995 code 97 → 95, 2005 → 2010
code 25 → 24 (the moves into Calakmul, Candelaria and Bacalar now at their frames), 2020 →
2025 absorption 19 (7 → 6 confirmed); the rest unchanged.

## Tests (`tests/test_cpv_geo.py`)

- Document: 2015 among the editions; its links dated by its cut (15 April in, May out);
  Chiapas's 070020003 → 071230029 at 2020 (dated 2011-11-23), Calakmul's 040031040 at 2000,
  Rancho Fátima at 2020; links dated before their edition only for a new municipality (≥ 430)
  or by the census rule (≤ 50).
- Units: `(2010, 2015)` and `(2015, 2020)` together = `(2010, 2020)`; Chiapas's move only in
  the second; `cpv_locality_units(2014, 2020)` raises.
- Parser: the 2015 cut. Own records: Rancho Fátima (2020, confirmed), Camino Real a San Pedro
  (2015 and 2020), a made-up absorption at 2015 counted on its own in 2020 (dropped), Familia
  Alfaro's move into Emiliano Zapata (`created`, 2020); Morelia's 0417 now 2015.
- `_REAL`: the ITER periods spelled out (with 2015 in `_LOC_PERIODS` the test would have looked
  for a 2015 ITER and skipped); the frames in `data/parquet` (MG 2015, MG 2020) checked, their
  unexplained codes ≤ 5% (Campeche).
- Full suite on the Mac: **1963 passed, 1 skipped** (35 min; 8b's count: the tests were extended, none added).

## Left

- **`CONFIRMED` per edition** (open question): a link both records state but date on either
  side of a cut is two one-record links: 10 of the 5,223 units of `cpv_locality_units(2010,
  2020, confirmed=True)` lose a locality against 8b (Ciudad Constitución's 030012867, Villa
  Milpa Alta's three). Counting such a pair confirmed at both editions would restore them but
  flip 186 links, most at 1995–2010 (not 2015's); left for the user.
- The 11 pairs dated either side of the 2015 cut: no rule tells which date is right (the MG
  2015 frame sides with the later in 9 of 11; at older editions the earlier is usually right).
- Campeche's records that end at the Censo 2010 (the AHL's gap, not the lineage's).
- «Se fusiona al municipio de Coatepec (038) Localidad Briones (0031).» (3 statements, 2019,
  Veracruz) is not read; 8a's and 8b's leftovers stand.
