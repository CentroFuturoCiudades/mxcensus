# CPV Unit 7u — the historical localities (INEGI's Archivo Histórico de Localidades)

Done **2026-10-12** (on the Mac; a byte-identical rebuild on `wsl`). HANDOFF candidate 2's
first item — «the AHL's `Habitantes` as a data product: every locality's population at
every census and count 1900–2020, a historical ITER» —, the user's choice over a 2015
locality edition, the small cleanups and more tabulado checks. Gate: the four AHL tables
in the mirror (faithful raw, registered), loaders, a check against every ITER 1990–2020,
tests green.

## The user's choices

- **The unit**: the historical ITER (over the 2015 locality edition, the small items and the
  tabulado checks).
- **Mirror scope**: all four tables, per state (`habitantes`, `maestro`, `movimientos`,
  `res_hist` × 32 = 128 files), over two tables or national files.
- **Snapshots**: the export's date in the file name (`ahl_{table}_20260918_{NN}`), as DENUE's
  releases — INEGI updates the archive continuously, and the bundled lineage (7t) is built
  from this export.
- **INEGI's copies**: flagged (`COPIA`) and dropped by default (`copies=False`).
- **Coordinates**: decimal `LATITUD`/`LONGITUD` always, `geometry=True` for points.

## Source

INEGI's AHL national ZIP (7t: `data/dict/ahl/AHL.zip`, a POST to `…/geo2/ahl/descarga`,
`clave=00&tipo=N`; 56 MB, the export of **2026-09-18**): 32 state ZIPs of four ISO-8859-1
CSVs and a one-page structure PDF (`Estructura_Archivos_AHL.pdf`).

| table | rows | content |
|---|---|---|
| `Habitantes` | 2,152,598 | `CVE_GEOEST`, `EVE_CENSAL` (the year), `INDICE_HAB`, `FUENTE` (Censo/Conteo), `TOT_HAB`/`TOT_HOM`/`TOT_MUJ` («1,234»; `*` reserved, `-` not available): 410,803 records |
| `Maestro` | 413,339 | one per record: DMS coordinates, altitude, 1:50,000 sheet, `TIPO` R/U, state and municipality names (the PDF's `NOMBRE_LOC` is missing) |
| `Movimientos` | 2,535,190 | the history: one row per event, its name, municipality, political and administrative categories then, what changed (free text) — a row per census and count |
| `Res_hist` | 18,842 | historical accounts of municipal seats and localities with indigenous names |

Every record is under the locality's **last** code. The censuses: 1900, 1910, 1921, 1930,
**1939** (INEGI's «Censo de Edificios», 179 rows, almost all `-`), 1940 … 1980, 1990, the
Conteo 1995, 2000, the Conteo 2005, 2010, 2020.

## The mirror (`scripts/build_ahl.py`, maintainer-only, ~8 s)

- `ahl_{table}_{snapshot}_{NN}.parquet`: every column a string, only empty cells null,
  INEGI's row order (`read_member`: pandas' parse checked against `csv`'s, same header and
  rows). Latin-1 as 7t: three `Res_hist` texts carry UTF-8 quotation marks (12 bytes)
  inside the Latin-1 text — kept byte for byte. 128 files, 42 MB.
- The snapshot is the members' timestamp (`build_loc_lineage.ahl_date`); a new export must be
  added to `_ahl_catalog.SNAPSHOTS` first.
- `--update-registry` upserted the 128 hashes: registry **4148 → 4276**. The files built on
  `wsl` (pyarrow 24.0.0, from its copy of the same ZIP) have the registry's hashes, all 128.
- `_build_common.PRESERVE_PREFIXES` += `ahl_`.

## `mxcensus.ahl`

- **`load_ahl(table, *, state, snapshot=None)`** — one table as published.
- **`load_ahl_poblacion(*, state, snapshot=None, copies=False)`** — the historical ITER:
  indexed `(CVE_ENT, CVE_MUN, CVE_LOC, EVE_CENSAL)`; `FUENTE` (`Censo`/`Conteo`/`Censo de
  edificios`, by the year), `POBTOT`/`POBMAS`/`POBFEM` (`Int64`, `*`/`-` missing), and the
  name, municipality, political and administrative category at that census (`NOM_LOC`,
  `NOM_MUN`, `CAT_POLI`, `CAT_ADMIVA`) from the record's census row in `Movimientos`
  (`_census_events`: «Censo de 2010.», «Censo 2010.», «Conteo de1995.», «censo de 2010.»,
  «Censo de Edificios de 1939.»; not «Censo Económico 2014.»; of two rows of one census the
  later `INDICE`). 1,065 rows have no census row in their history (no name).
- **`load_ahl_localidades(*, state, snapshot=None, geometry=False)`** — one row per record:
  `NOM_ENT`, `NOM_MUN` (Maestro's), `NOM_LOC`, `CAT_POLI`, `CAT_ADMIVA` (the last event's),
  `AMBITO` (`Rural`/`Urbana`: the MG's names for R/U; 118 `0`/blank missing),
  `LATITUD`/`LONGITUD` (decimal degrees, `Float64`), `ALTITUD` (`Int64`, as published: one
  8,800 m and 1,820 below 0 kept), `CARTA_TOPO` (normalized `F13D19`; `null`, `0`, six
  digits missing). The DMS parser (`_degrees`) takes «O» for west, «¨»/«´» for the marks, a
  missing hemisphere as N/W; minutes or seconds of 60 or more and values outside 14–33° N,
  86–119° W are missing (49 of 355,680: swapped latitude/longitude in Huitiupán and Cozumel,
  `991°`, a Tecate locality at 33.5° N…). `geometry=True`: a `GeoDataFrame` of EPSG:4326
  points, missing where the coordinates are.
- Exported from `mxcensus`; CLI `mxcensus fetch STATE --dataset ahl [--snapshot YYYYMMDD]`
  (`SELECTOR_FLAGS["snapshot"]`).

### INEGI's defects the analysis frame repairs

| defect | rows | repair |
|---|---|---|
| rows copied to a locality's new code after a census | 2010: 444 (49,027 persons), 2020: 689 (162,896) | `COPIA`, dropped unless `copies=True` |
| «1920» | 1 | the 1921 census (its history says «Censo de 1921») |
| years `2` (8), `2013` (1) | 9, all zero | dropped (a warning if one ever has population) |
| two rows of one locality and year | 31 pairs | the one with more information (population > `*` > 0 > `-`): the ITER agrees in all 4 pairs it can tell |
| read one column off from the ITER | 11 (1990 3, 1995 6, 2000 2) | shifted back (`_SHIFTED`): each equals its ITER |
| `FUENTE` contradicting the year | 238 | `FUENTE` set by the year |

- **The copies** (`_copies`): a row of `TO` (a `code` link of the bundled lineage) at a
  census **from 2010 on** before the link's date, equal in its three counts to `FROM`'s row
  at that census (`FROM`'s state is read when not loaded; 5 links cross states, none with a
  copy in this snapshot). In 2010 and 2020 every flagged row with population has its new code
  missing from that ITER and the old one in it. Before 2010 two codes of one locality with
  equal rows are mostly **both** in that census's ITER (double registrations merged later,
  «Es la misma localidad»): 1990's 13 such rows with population — 9 with both codes in the
  1990 ITER — are kept, hence `_COPIES_SINCE = 2010`.
- **The shifted rows**: the ITER rows whose locality name was quoted (1990: `" T " DEL
  NAYARIT`, `"Y", LA`) or spilled into `LONGITUD` (1995/2000, the rows
  `cpv_aggregates._repair_spilled_names` repairs) reached the AHL one column off: `TOT_HAB`
  = the altitude (`*` in 1990), `TOT_HOM` = the total, `TOT_MUJ` = the men. Shifted back
  (women = total − men) only while still inconsistent (a later snapshot may be fixed).

## The check (`--check` → `docs/cpv/AHL_REPORT.md`, ~70 s)

| census | ITER localities | in the AHL | equal | different (both known) | ITER only (moved) | ITER persons | AHL persons |
|---|---|---|---|---|---|---|---|
| 1990 | 156,602 | 155,221 | 155,184 | 26 | 1,381 (246) | 81,249,645 | 81,148,169 |
| 1995 | 198,430 | 198,089 | 196,496 | 4 | 341 (20) | 90,065,931 | 90,044,870 |
| 2000 | 199,391 | 199,372 | 199,369 | 2 | 19 (1) | 97,483,412 | 97,483,228 |
| 2005 | 187,938 | 187,928 | 187,924 | 3 | 10 (1) | 103,263,388 | 103,263,403 |
| 2010 | 192,247 | 192,242 | 192,240 | 2 | 5 (0) | 112,336,538 | 112,336,423 |
| 2020 | 189,432 | 189,423 | 189,410 | 11 | 9 (1) | 126,014,024 | 126,013,869 |

- **Sexes**: equal wherever both publish them (1995: 9 of 104,040 differ, 2010: 1).
- **`equal`** counts both reserved too; the rest of `in the AHL` is reserved on one side:
  1990's 11 the AHL has none for (`*`/`-`), 2000/2005/2020's 1–2.
- **1995's reserved localities**: the Conteo 1995's ITER reserves the count of the
  localities of one or two dwellings; the AHL has it for **1,589** of them (`reserved in the
  ITER only`) — beyond the ITER.
- **The differences** left (both known; the shifted rows now equal): 1990's 26 (most in
  Durango and Sonora: the AHL has 0 where the ITER has a few persons), 1995's 4 and 2000's 2
  (the AHL 0), 2005's 3 and 2010's 2 (a few persons), 2020's 11 in Nuevo León (19038–19040:
  other small values in the AHL — INEGI's later corrections, presumably).
- **The ITER's localities without a 1990 row** (1,381, 102,276 persons; 1995: 341, 33,409):
  246 moved (their history is under the new code), most of the rest in **Escárcega (04009,
  317 localities, 44,496 persons)** — created three months after the 1990 census and already
  in its ITER: the history has the 1990 census under the old Carmen code, but no population
  row under either code — and Sonora's 26026 (46, 18,502; 1995: 26, 20,257). INEGI's gaps;
  the loader cannot bridge them.
- **Coverage before 1990** (INEGI's national totals, series históricas, rounded to tens
  before 1980): 1900 82.7%, 1910 82.9%, 1921 87.0%, 1930 88.0%, 1940 86.6%, 1950 87.4%, 1960
  89.3%, 1970 94.6%, 1980 99.8%. The AHL holds the catalog's localities (including those
  dropped since), not the old censuses' full listings; the 1950–1960 rows lack the
  population of 6,500–12,700 localities (`-`).
- **Per state**: Querétaro equals the ITER in every locality and total 1995–2020; Campeche
  in every locality 1990–2020 that both list (its 1990 total is 45k short: Escárcega).

## Tests

- New `tests/test_ahl.py` (10): the catalog, the registry's 128 names, the builder's reader
  (faithful strings, Latin-1, newlines in values), `load_ahl`, the population rules on
  synthetic tables (copies — also across states —, «1920», stray years and the warning,
  duplicates, `*`/`-`, names from the census rows, the shift repair and its guard,
  unexpected values raise), the localities (DMS variants, bounds, `CARTA_TOPO`, `AMBITO`,
  the geometry), and two `_REAL`: Campeche and Querétaro against their ITERs, a rebuild of
  states 01/04 = the registry's hashes.
- `tests/test_cli.py` +4 (`--dataset ahl`, the snapshot, three argument errors).
- Full suite on the Mac: **1950 passed, 1 skipped** (34 min; 7t's 1936 + 14).

## Release

With the user's go-ahead: the 128 files uploaded from `wsl` (`hf` is logged in there only;
its checkout fast-forwarded to 7u by a `git bundle`, its `data/parquet/` given the 128 files
of its own rebuild — the registry's hashes): `upload_hf.py upload --dry-run` = 128 new,
4,148 identical; `upload` (and the bucket README: 4276 files, the AHL row and citation);
`verify` = every registered file served at its size. A fresh cache on the Mac downloads
and hash-checks them anonymously. Merged into `main` as **0.14.0**, tagged and pushed.

## Left out

- **A bridge to the ITER codes**: the AHL panel is under the last codes; to compare with an
  ITER of its own time, map the ITER through `cpv_locality_units` (7t). The 1990/1995 gaps
  above stay INEGI's.
- **Recovering swapped coordinates** (4 records): missing, as every malformed one.
- **`Res_hist`** is mirrored but has no analysis frame (prose and bibliography).
- **The pre-1990 links** (renumberings before 1990): the lineage starts in 1990; a locality's
  older rows are already under its last code.
