# CPV Unit 7t — the locality lineage

Done **2026-10-11** (on the Mac; the check against every edition on `wsl`). HANDOFF
candidate 1's «locality-level lineage» (6a covered municipalities only), the user's choice
over more tabulado checks and the small cleanups. Gate: the lineage built from an INEGI
source, checked against every ITER 1990–2020 and the MG 2025 frame, units helper, tests
green.

## The user's choices

- **The unit**: the locality lineage (over Censo 2020's / EIC 2015's / Censo 2010's
  leftover tabulados and the small cleanups).
- **Storage**: a bundled gzipped CSV (`_yaml/cpv_loc_lineage.csv.gz`, 205 KB; over a ~3 MB
  YAML or a mirror parquet that needs an upload).
- **Editions**: the six ITERs 1990–2020 **and 2025** (the EIC 2025's frame, MG 2025).

## Source: INEGI's Archivo Histórico de Localidades

6a found no download of AGEEML's history. The **AHL** (https://www.inegi.org.mx/app/geo2/ahl/)
has one: its «Catálogos» tab lists a ZIP per state and a national one
(`cargaCatalogos.do?cat=cat`), served by a POST to `…/ahl/descarga` (`clave=00&tipo=N` for
the nation: 56 MB, the export of **2026-09-18**). Each state ZIP holds four ISO-8859-1 CSVs
and a one-page structure PDF:

| table | rows | content |
|---|---|---|
| `Maestro` | 413,339 | one per locality (its **last** code): coordinates, type U/R, names of state and municipality (the PDF's `NOMBRE_LOC` is not there) |
| `Habitantes` | 2,152,598 | population (total, men, women) at every census and count **1900–2020** |
| `Movimientos` | 2,535,190 | the history: one row per event (census, count, geostatistical update, decree) with the name, municipality, political category and **what changed in free text** (`ORI_MODIF`) |
| `Res_hist` | 18,842 | historical accounts of municipal seats |

**It is the ITERs' catalog.** `Habitantes` has every ITER locality code of 2000 (199,372 of
199,391), 2005 (187,928/187,938), 2010 (192,242/192,247) and 2020 (189,423/189,432) with
the same population in all but a handful; 1990 and 1995 differ by the codes changed since
(an AHL record is filed under its last code), which its history explains.

## The links (`scripts/build_loc_lineage.py`, maintainer-only, ~20 s)

The history text is semi-structured: 2,826 phrasings of the code-bearing sentences from
1990 on. Regexes (`_PATTERNS`) read each statement, on both records where INEGI writes it:

| kind | statements |
|---|---|
| `code` (the same locality, another code) | «Pasa al municipio X (MMM) con clave de localidad (LLLL)» on the old record / «Viene del municipio …» on the new (also «y clave», codes without parentheses, «Pasa al estado …», the Distrito Federal's «delegación»); «Hasta este evento estuvo registrada con clave Y» … «A partir de este evento cambia a la clave X» inside one record; «Es la misma localidad (LLLL) del municipio (MMM)», «Misma que la localidad …» (duplicates) |
| `absorption` | «Se conurba a / Se fusiona a NAME (LLLL)» on the absorbed record (also «Localidad conurbada a …», «…, clave (9 digits)»), «A esta localidad se conurba(n) / fusiona(n) / integra(n) la(s) …» on the other |
| `counted_with` | «Se censó con la localidad NAME (LLLL)» (1990: 526, 1995: 9) |
| `separation` | «Se desconurba / desfusiona / desagrega de NAME (LLLL)», «De esta localidad se desconurba(n) / desfusiona(n) …» |

- **Moves stated without a code on both records** («Pasa al municipio Nadadores (021).»)
  are paired by the locality's name within the pair of municipalities and the edition: 26
  paired, 337 statements left (most from the 1990s, 82 of the old ones ever in an ITER).
- **A locality number without its municipality** (4 digits, «Se conurba a Playas de
  Rosarito (0001)»): the stating record's municipality was wrong where the absorber lies in
  another — the Rosarito remnant (Tijuana, 004) went to 020050001 (Playas de Rosarito, 005),
  not to Tijuana's 020040001. `Resolver` places the number by its name among the state's
  localities with that number (`name_match`: equal, equal without «El»/«(Cab.)»…, one
  inside the other or half their words): 29,347 in the record's municipality, 160 in
  another, 233 unverified (kept in the record's municipality).
- **Rival claims** (a locality absorbed by two, renumbered to two at one edition; INEGI
  lists some twice): the claim stated on both records wins; with none confirmed, an
  absorption whose number matched its name, one stated on the locality's own record, a new
  code with the locality's own name. Left: 4 absorptions, 10 codes (both kept: a unit only
  gets coarser).

## Dating: each edition's cut

A link is dated by its event (a census row by the census's reference date, an update by its
date, a decree by its text's first date) and takes effect at the first edition whose **cut**
is on or after it. The cut was found on the data, comparing every link's codes with each
ITER and frame by date:

| edition | cut | evidence |
|---|---|---|
| 1990 | 1990-03-12 | the census day (no earlier ITER) |
| 1995 | 1995-11-05 | changes up to the count applied; the next (1996-11-30) not |
| 2000 | 2000-02-14 | the 16 changes of the census day applied; from 2000-02-18 not |
| 2005 | **2005-10-30** | INEGI's update of 30 October 2005 applied (120 links), the one of the 31st not |
| 2010 | **2010-10-15** | the updates of June–October 2010 applied; the decree of 2010-12-11 not |
| 2020 | **2020-12-31** | every change of 2020 applied (to 2020-11-17), none of 2021: the ITER uses the MG 2020 frame of December |
| 2025 | **2025-12-31** | MG 2025 has every change to 2025-11-30, none from 2026-01-01 |

A census row's change shows in that census's ITER (the new code in 97–100% of the listed
cases), so «Censo de 1990. Pasa al municipio …» is in effect by 1990 and dropped (out of
scope), except the localities counted with another at the 1990 census. 67 statements have
no date; one is dated 2214 (a typo: dropped).

## Result: 33,161 links

| KIND | 1990 | 1995 | 2000 | 2005 | 2010 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|
| code | 0 | 3,537 | 2,314 | 1,919 | 904 | 2,847 | 840 |
| absorption | 0 | 1,961 | 1,557 | 2,803 | 3,197 | 6,741 | 2,148 |
| counted_with | 526 | 9 | 0 | 0 | 0 | 0 | 0 |
| separation | 0 | 94 | 75 | 158 | 279 | 931 | 321 |

Confirmed (stated on both records): code 72.7%, absorption 81.1%, separation 83.3%. Columns
`PERIOD, DATE, EVENT, KIND, FROM, TO, CONFIRMED`; the file's bytes are the same built on the
Mac and on `wsl`.

## The check (`--check` → `LOC_LINEAGE_REPORT.md`; needs the full mirror: `wsl`)

- **Links against the codes**: a `code`/`absorption` link whose `FROM` is still listed at
  its edition, or a `separation` whose `FROM` is not, is contradicted: ≤ 2.7% of a span's
  links (1990 → 1995 codes: 97 of 3,537), ≤ 1.2% elsewhere. **Confirmed links 0.3%,
  one-sided ones 2–5%** — kept (95–98% of them agree with the codes; a wrong link only
  makes a unit coarser). The contradictions are INEGI's: Rosarito's remnant kept the old
  code until 2004, Techachales goes on after Tulancingo's record absorbs it, «Familia
  Torres» moved in 2018 and still has a 2020 row.
- **Every code that leaves or enters** between two editions (the ITERs; 2020 → 2025 the
  MG 2020 against the MG 2025 frame) is explained by a link, the AHL's «baja» /
  «deshabitada» / creation / reactivation, a record that starts there, the Conteo 1995's
  one- and two-dwelling localities, «Sin información» (2,463 localities the Conteo 1995 did
  not reach, most in Chiapas) — or not: **unexplained ≤ 1.3% (1990 → 1995: 447 of 33,858
  leaving, 811 of 75,686 entering), ≤ 0.9% elsewhere**. The MG frames since 2015 also list
  22–30 thousand localities the AHL does not hold (industrial parks, plants, service
  sites).
- **Moves to another municipality** against the municipal lineage (6a): 1995 → 2000 1,545 of
  2,275, 2010 → 2020 2,340 of 2,846, 2020 → 2025 727 of 840 go into a municipality the MG
  frames show created then from the old one; the rest are boundary changes (and 171 moves
  between states in 2005 → 2010).
- **Large units**: no unit joins two towns of 20,000+ but by a real conurbation or split
  (Toluca, Metepec, Zinacantepe and Los Reyes split into many localities in 2020; Chalco
  gave Xico to Valle de Chalco; Tijuana, Mexicali, León and Zapopan absorbed theirs). Before
  the rival-claim rules, Monterrey + Escobedo and Poza Rica + Papantla were joined through a
  locality both claimed.

## `mxcensus.cpv_geo`

- **`cpv_loc_lineage()`**: the links (`DATE` datetime, `KIND` categorical, `CONFIRMED`
  bool); `_resources.cpv_loc_lineage()` reads the CSV.
- **`cpv_locality_units(start, end, *, absorptions=True, confirmed=False)`**: one row per
  code a link joins between the editions (`CVEGEO`, `UNIT` = its unit's smallest code),
  transitively: the links that take effect after `start` up to `end`, and the localities
  counted with another at either census. Every other code is its own unit (map, keep the
  code where missing, aggregate). `absorptions=False`: codes only; `confirmed=True`: links
  stated on both records. Sizes: 2000 → 2020 29,784 codes in 10,297 units, 1990 → 2025
  50,819 in 18,349. A unit may span two states (a locality moved between states).
- Example (Chiapas, 2000 vs 2020): 19,455 and 21,157 localities → 19,206 and 20,923 units,
  15,077 in common (the module doc's snippet).
- Exported from `mxcensus`; 1990–2025 editions, 2015 raises (no locality edition).

## Tests (`tests/test_cpv_geo.py`, +4)

- **The document**: columns and types, every link dated within its edition, only 1990's
  counted-with in effect by 1990, confirmed shares, Rosarito (move and conurbation, both
  confirmed), Loreto (codes without parentheses), Real Cumbres (Monterrey, not Escobedo),
  a 2018 move and a 2025 conurbation.
- **Units**: Rosarito joined 1990 → 1995 and 2000 → 2020 but not with Tijuana, Monterrey
  apart from Escobedo, a counted-with of 1990, nothing for one edition, `absorptions`,
  `confirmed`, errors.
- **The parser** (offline): event dating, the cuts, 16 statement shapes, a renumbering
  inside a record, the name resolver.
- **`_REAL`** (needs `data/dict/ahl/AHL.zip` and every ITER): the bundled file equals a
  rebuild byte for byte; the check's contradictions ≤ 3% and unexplained codes ≤ 1% (1.5%
  in 1990 → 1995).
- Full suite on the Mac: **1936 passed, 1 skipped** (34 min); merged into `main` as 0.13.0.

## Left out

- **Locality polygons**: the units are by code, not by territory; an absorbed locality's
  dwellings are counted in its absorber's (that is what the census does).
- **`Habitantes`** (every locality's population 1900–2020) and `Maestro`'s coordinates are
  not bundled: a «historical ITER» back to 1900 would be a data product of its own (it
  needs the mirror).
- **The EIC 2015**: no ITER, and its microdata name only the localities of 50,000+
  (`LOC50K`, as 2010–2025's); the locality editions skip it (the user's choice). A 2015
  cut would have to be found on its frame (MG 2015, cut 30 April 2015).
- The 337 unpaired moves without a code, the 233 unverified locality numbers and the 14
  rival claims left; INEGI's own contradictions stay as they are (the report lists
  examples).
