# CPV Unit 3c — Census aggregates (ITER, AGEB) for 2020 + 2010

Done **2026-10-07** (overnight, unattended) — **code complete, verification on `wsl`
pending.** Midway through the unit, Tailscale SSH on `wsl` started demanding an interactive
re-login (`# Tailscale SSH requires an additional check. To authenticate, visit
https://login.tailscale.com/a/…`). That needs the user in a browser, so the last `wsl` steps
could not run. §Pending lists exactly what is left; nothing else depends on them.

Gate status:
- **2020 output equals the legacy `load_census`** — ✅ on state 01 (Mac): all four levels,
  values, columns, index and missing pattern. The 32-state run on `wsl` is pending.
- **`--validate` 0 failures with the 2010 ITER/AGEB included** — ✅ 0/481 on `wsl`, but run
  before two late fixes (the `TAMLOC` type and the case-insensitive code rules, below). It
  must run once more on `wsl`; the four state-01 aggregate files pass locally.

## 2010 ITER/AGEB build

- **The CSV header read** (`build_cpv._read_header`): 2010's files start with a BOM
  followed by a quoted name (`\\ufeff"entidad",…`). The old code stripped the BOM *after*
  `csv.reader` had kept the quotes, so the parsed names differed from the header and the
  conversion failed. UTF-8 is now decoded as `utf-8-sig`, so the BOM goes first. The other
  editions are unaffected (no BOM, or a BOM before an unquoted name).
- **Build on `wsl`** (`--periods 2010 --tables iter ageb`, log `build_cpv_2010_agg.log`):
  64 files, 0 failed, 3 min 44 s, peak RSS 0.8 GB; all UTF-8 with lower-case headers.
  - ITER: 200 columns, 198,485 rows.
  - AGEB: 198 columns, 1,440,175 rows.
- **Sentinels** over all 32 states (`_AGG_SPECIALS["2010"]`):

  | code | ITER cells | AGEB cells |
  |---|---|---|
  | `*` | 15,820,270 | 62,687,059 |
  | `N/D` | 42,550 | 127,985 |

  There is no `N/A`.
- **Indicator dictionaries**: `fd_iter_cpv2010.csv` / `fd_resultados_ageb_urbana_cpv2010.csv`
  (cp1252) live in a `diccionario_de_datos/` folder, so `_INDICATOR_DICT_RE` accepts any CSV
  there. The 2010 AGEB dictionary leaves `nom_ent`/`nom_mun`/`nom_loc` out (and lists a
  `tipo` the data lack), so for AGEB the build falls back to the same edition's ITER
  dictionary for missing names (`_doc_for`).
- **`TAMLOC` is a class code** (`_AGG_CODES`): 2010's dictionary gives `tam_loc` `1..14`,
  which `parse_indicator_csv` reads as a number; 2020's `01..14` is a string. Both are now
  strings. Otherwise the 2010 `TAMLOC` was an `Int64` "count", null on total rows, and
  tripped the census checks.
- **Geography checks in lower case**: `cpv._code_rule` now matches names case-
  insensitively. Before, 2010's `entidad`/`mun`/`loc`/`ageb`/`mza` got no digit/AGEB-shape
  check.
- **Schema map**:
  - `iter`: 2010 = `g01` (200 columns), 2020 = `g02` (286), each 32 files.
  - `ageb`: 2010 = `g01` (198), 2020 = `g02` (230).
  - The 2020 dictionaries came out byte-identical under their new gid.

## Loaders (`cpv_aggregates.py`)

All frames are harmonized (`CVE_*` names, string codes, `CVEGEO`) and labelled: counts
`Int64`, ratios `Float64`, the reserved cells missing.

- **`load_cpv_iter(period=None, *, state, nivel=None, impute=True)`**: one row per state,
  municipality and locality, indexed `(CVE_ENT, CVE_MUN, CVE_LOC)`. An ordered `NIVEL`
  takes `estatal` / `municipal` / `agregado` / `localidad`, where `agregado` is the
  9998/9999 rows: the localities of one and two dwellings, which are *also* listed one by
  one, so the localities alone add up to the municipality. `impute=True` fills a missing
  locality count with 0 when the municipality's total already equals the sum of its
  localities' known values (`_impute_zeros`, the vectorized port of
  `aggregate.impute_zeros_univariate`; a test checks both agree).
- **`load_cpv_ageb(...)`**: indexed `(…, CVE_AGEB, CVE_MZA)`, with `NIVEL` up to `manzana`.
  `impute=True` applies the legacy empty-row fix (dwelling counts of a row with
  `POBTOT = 0` are 0) and the locality → AGEB zero imputation. Blocks are left as
  published, since INEGI's block counts do not add up to their AGEB's (the legacy loader
  notes the same).
- **`load_cpv_census(period=None, *, state)`** is the legacy `load_census` chain on the
  `cpv_` files and string keys:
  - the count columns only;
  - the empty-block fix;
  - `aggregate.add_collective_cols` (`POBCOL`, `TOTCOL` + collective imputation);
  - `impute_zeros_univariate` municipality → locality and locality → AGEB;
  - `aggregate.sanity_checks` ported to `CVE_*` names (`_census_checks`; the legacy one
    hard-codes `ENTIDAD`/`MUN`);
  - every level restricted to the AGEB columns.

  `aggregate.py` is imported, not changed (frozen).

**Results on state 01**:
- 2020: `load_cpv_census(2020, state=1)` **equals** `load_census(state=1)` once the legacy
  integer codes are written as padded strings: `(1, 11, 2022, 480)` rows × 217 columns.
- 2010: the chain passes every cross-file check. Aguascalientes has 1,184,996 inhabitants
  (INEGI's 2010 count). The zero imputation fills 12,629 of the 195,480 reserved locality
  cells.

## Crosswalk: `cpv_iter_crosswalk.yaml` (`build_cpv.py --crosswalk`)

The crosswalk is generated, not hand-edited: the columns come from the schema map, the
descriptions from the indicator dictionaries, and the hand review is code in
`build_cpv.py` (`_XW_PAIRS`, `_XW_RENAME`, `_XW_NOTES`, `_XW_NOT_COMPARABLE`). Accessor:
`mxcensus.cpv_iter_crosswalk()`.

- **296 indicators**: 194 in both editions, 8 only in 2010, 94 only in 2020 (the 5-year age
  groups, the 2020 disability module, `POB_AFRO`, new dwelling items…). Every column of
  every ITER/AGEB group appears exactly once as a source (tested).
- **Renamed by `harmonize=True`**: only `TAM_LOC` → `TAMLOC` (the same 14-class scale,
  checked against both editions' `catalogos/tam_loc.csv`). The rename is table-scoped to
  the ITER (`cpv._crosswalk_renames`), because 2010's microdata `TAM_LOC` is a 4-class
  scale.
- **Paired but not renamed**: `PRES2005*`/`PRESOE05*` ↔ `PRES2015*`/`PRESOE15*` (residence
  five years earlier, another reference date).
- **`Comparable: false`** (same name, different measure):
  - `PCLIM_VIS` and `PCLIM_MOT2`: 2010 counts any difficulty, 2020 only «poca» — much
    difficulty is disability, `PCDISC_*`;
  - `PDER_SEGP`: Seguro Popular in 2010, INSABI in 2020.
- **Notes**:
  - the health items (`PDER_*`, `PSINDER`): «derechohabiencia» became «afiliación»;
  - `HOGJEF_*`/`PHOGJEF_*`: «jefatura» became «persona de referencia»;
  - `VPH_PC`: 2020 adds laptop/tablet;
  - `PSIN_RELIG`: 2020 adds «sin adscripción»;
  - the religion regrouping: `PNCATOLICA` 2010 vs `PRO_CRIEVA` 2020, which affects
    `POTRAS_REL`;
  - 2010's activity-limitation block has no 2020 equivalent.

## Tests (`tests/test_cpv_aggregates.py`, new)

- `NIVEL` classification, `_impute_zeros` (only forced zeros; equal to the legacy function)
  and the empty-block fix.
- The BOM-quoted header read; the indicator-dictionary pattern; the 2010 sentinels;
  `_indicator_doc` (`TAMLOC` a string) and the AGEB name fallback.
- The schema groups; both editions' dictionaries; the crosswalk (every column once, the
  flags, the pairs); table-scoped renames; planted rejections in the 2010 aggregate schemas.
- `_REAL` tests:
  - the loaders for 2010 and 2020 (index, `NIVEL`, totals, imputation fills only zeros
    and keeps every known cell);
  - **`test_census_2020_equals_legacy`**, parametrized over every state with both legacy
    and `cpv_` files (01 on the Mac, 32 on `wsl`);
  - the 2010 census checks per state;
  - 2010 + 2020 stacking.

Existing tests take the ITER/AGEB gids from the map (`_gid`).

Results: Mac full suite **914 passed, 4 skipped** in 7 min 34 s (the 4 warnings are the
pre-existing DENUE/ENOE ones). The `wsl` 32-state run is pending (§Pending).

## Pending (needs `wsl`, i.e. the Tailscale re-login)

1. Sync 3c's code to `wsl` and regenerate `--variables` (the `TAMLOC` type changed the
   2010 ITER dictionary) and `--report-only`, then `--validate --jobs 16` (expect 0/481).
2. Copy the generated `cpv_schema_map.yaml`, the `variables_cpv_{iter,ageb}_g0*.yaml`, the
   two reports and the crosswalk back. They should equal the locally generated copies
   committed here (§Process); diff them.
3. Run the CPV tests over all 32 states on `wsl`, in particular
   `test_census_2020_equals_legacy` (the 32-state gate) and `test_census_2010_checks`.

## Deviations from the plan

- `load_cpv_census` is new. The plan named only `load_cpv_iter`/`load_cpv_ageb` and an
  "equality with legacy `load_census`" test; the census builder is the natural place for
  that equality.
- `load_cpv_iter`/`load_cpv_ageb` return one frame with a `NIVEL` column (like
  `load_cpv_estimaciones`), not one frame per level.

## Process

The 3c metadata ran on `wsl` from a separate code copy (`~/mxcensus3c`, `PYTHONPATH=src`,
reading `~/mxcensus/data`), because the 32-state 3b tests were still reading
`~/mxcensus`'s YAMLs.
- When the re-login blocked copying the results back, the **schema map and the ITER/AGEB
  dictionaries were regenerated on the Mac**. The new map sections came from the files'
  columns, with one fingerprint per edition across the 32 states, as `wsl` reported. The
  dictionaries came from a temp mirror of the state-01 files.
- That is exact for these tables: their enumeration threshold is 0, so the data never
  shape the entries. As a check, the two 2020 dictionaries came out byte-identical to the
  committed ones.
- The microdata sections of the schema map are untouched.
- The reports (`INCONSISTENCY_REPORT.md`, `VALIDATION_REPORT.md`) are still 3b's until
  `wsl` regenerates them.
