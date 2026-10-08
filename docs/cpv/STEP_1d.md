# CPV Unit 1d — Marco Geoestadístico EIC 2025 (geometry) and `load_mg`

Done **2026-10-07**. Gate: the EIC 2025 frame built on `wsl` for all 32 states
(**493 files**: 15 layers × 32 states = 480, plus `ti` for 13 island states), and
`load_mg` tested (offline, and `_REAL` on the Mac's state 01 and on `wsl`'s full mirror).
Every national total INEGI states in the ZIPs' `catalogos/contenido.txt` matches the mirror
exactly, for 2020 and 2025.

## User decisions (this session)

- **Registry → 1e.** The build ran with `--no-registry`; `build_marco_geo.py` gained an
  `--update-registry` mode (hashes the files already built, no download), so 1e upserts
  the `cpv_` and `mg_*_2025` entries together and the `wsl` tree stays clean.
- **CLI `--dataset mg --edition` → 1e**, with the registry, like `cpv`: the CLI never
  offers unregistered files.
- **CRS: keep the mirror faithful; `load_mg(..., crs="EPSG:6372")` by default** (see
  below).
- **Mirror the 16th layer, `ti` (territorio insular), for 2025 and 2020.** The 2020 files
  are new (`mg_ti_NN`, 13 states); no existing legacy file or hash changes.
- **`wsl` runs no longer need the user's permission** (from mid-1d on). Commits, pushes and
  uploads still do.

## The CRS spelling — finding and decision

INEGI's `contenido.txt` gives one projection for every layer (Lambert conformal conic,
ITRF2008, GRS80, lat₀ 12°, lon₀ −102°, parallels 17.5°/29.5°, false easting 2,500,000),
but the `.prj` files spell it two ways:

- a custom ESRI WKT, `MEXICO_ITRF_2008_LCC` (datum `D_ITRF_2008`), on most layers;
- EPSG:6372, "Mexico ITRF2008 / LCC" (datum `Mexico_ITRF2008`, `TOWGS84[0,…]`), on a few.

**The mix is within each year, and in 2020 even across the states of one layer**, not only
across years (the probe in `STEP_0_probe.md` only compared years). Over all 32 states:

| edition | layers carrying EPSG:6372 | custom on all other layers |
|---|---|---|
| 2020 | `fm` in 30 states (02 and 25 are custom) | yes |
| 2025 | `ar`, `ent`, `lpr`, `mun`, `ti`, in every state | yes |

The two CRS objects compare unequal, so geopandas **raises** on `pd.concat([a, ar])`
("Cannot determine common CRS") and **warns** on `sjoin(l, lpr)` in 2025 — the pairs the
legacy AGEB/locality pipeline combines. PROJ resolves the conversion between the two to
`proj=noop` ("Ballpark geographic offset from ITRF2008 to Mexico ITRF2008"): `to_crs`
moves **no coordinate** (max |Δ| = 0.0 on every layer of state 01, both editions), and
costs ~50 ms on the largest layer (`fm`, 119k lines).

**Decision:** the mirror keeps each file's source CRS, as the 2020 files always have
(faithful; normalising at build time would also leave the frozen 2020 files custom, so
cross-year `==` would still fail). `load_mg` returns every layer on
`CANONICAL_CRS = "EPSG:6372"` by default; `crs=None` returns the stored CRS, any other
value reprojects. `test_real_crs_spellings_are_one_projection` pins the per-layer
spellings of state 01 and asserts bit-identical coordinates after the default `to_crs`,
so a PROJ release that started applying a datum shift would fail the suite.

## What was built

### `src/mxcensus/mg.py` — `load_mg(layer, *, state, period="2020", crs="EPSG:6372")`

A new module: `aggregate.py` is the frozen legacy path, and `load_mg` serves every
edition. `load_mg_census` is untouched.

- `layer`: one of `MG_LAYERS` (16 suffixes); unknown → `ValueError`.
- `period`: str or int, any `MG_EDITIONS` key. 2020 reads the legacy `mg_{sfx}_{NN}`,
  other periods `mg_{sfx}_{period}_{NN}` (`_catalog.mg_filename`). The national-layout
  editions (1995–2010) resolve the same names once 3d/4b split them per state; until then
  their fetch fails.
- `state`: required keyword, `int | sequence`, with `cpv._states` semantics (duplicates
  dropped, order kept; bool/float/str/empty/out-of-range raise). A sequence concatenates
  with a fresh `RangeIndex`.
- A file missing from the mirror (Pooch's "not in the registry") becomes
  `ValueError: no MG {period} {layer!r} layer for state NN …`, with a note for `ti`
  (island states only).
- `crs=None` with several states whose stored CRSs differ raises, pointing at `crs=`. Real
  data reaches this: 2020 `fm` for states 01 and 02.
- Attribute columns are returned verbatim: codes stay zero-padded `str` (`CVEGEO`,
  `CVE_ENT`, …), so `mg_mun_2025` joins `load_cpv_estimaciones` and the microdata
  `CVEGEO`. Rows keep INEGI's order (2025 `mun` is not sorted by code). `CVEGEO` is unique
  in every layer except the service layers (`sia`/`sil`/`sip`) and `ti`.
- `period="2020"` is the default, as `PLAN.md` specified (it frames the census with
  ITER/AGEB data; the other families default to the latest edition).
- Exported from `mxcensus` (`load_mg`).

### `src/mxcensus/data/_catalog.py`

- `MG_LAYERS`: suffix → content, from `contenido.txt` (identical suffixes and columns in
  2020 and 2025).
- `MG_OPTIONAL_LAYERS = {"ti"}`: `contenido.txt` says `ti`, `cd`, `pe`, `pem`, `sia`,
  `sil`, `sip` ship only where such features exist, but in both editions only `ti` is
  actually absent from some states.

### `scripts/build_marco_geo.py`

- Layers come from `MG_LAYERS` (now including `ti`). An absent optional layer is skipped
  silently; any other absent layer is still reported.
- `--update-registry`: upsert the hashes of the `--period/--states/--layers` files already
  in `--output` (reports expected files not built; `ti` outside the island states is not
  "missing"). Mutually exclusive with `--no-registry`.
- `main(argv=None)` for testing.

### Tests — `tests/test_mg.py` (new)

- Offline (synthetic GeoParquet in `tmp_path` with INEGI's two verbatim `.prj` strings;
  `POOCH.fetch` redirected and raising like Pooch for missing names): filenames by period,
  default CRS canonical and lossless across mixed spellings, `crs=None` (and its
  mixed-CRS error), reprojection to EPSG:4326, eight error cases, the catalog/build layer
  list, the quiet optional-layer skip, `_built_files` and the `--update-registry` CLI on a
  scratch registry.
- `_REAL` (sentinel `mg_mun_2025_01.parquet`; `local_mirror` fixture as in
  `test_cpv.py`):
  - the CRS spellings and the no-op conversion (state 01, all layers, both editions);
  - layers and editions combine without warnings (`concat(a, ar)`, `sjoin(l, lpr)`, 2020
    vs 2025 `mun`, the state boundary moved < 10 m² between frames);
  - states with different stored spellings (2020 `fm`, states 01 + 02) need the default
    `crs`;
  - every 2025 layer keeps the 2020 columns and geometry types (every state on disk);
  - `mg_mun_2025` CVEGEOs == the estimaciones municipalities (every state on disk; 2,478
    on `wsl`);
  - `ti` loads for the island states present;
  - national totals == `contenido.txt` for every edition on disk for all 32 states.

## Numbers

### Build (`wsl`, `build_marco_geo.py --period 2025 --no-registry`)

- **493 files**, 0 conversion failures: 15 layers × 32 states + `ti` for 13 states (the
  same island states as 2020: 02, 03, 04, 06, 12, 14, 18, 20, 23, 25, 26, 30, 31). Every
  layer has the 2020 attribute columns and geometry types in every state
  (`test_real_layer_columns_match_2020`).
- 2.6 GB of ZIPs (`data/cache/mg_2025_NN.zip`) → **2.3 GB** of GeoParquet. The largest
  layers are `fm` (853 MB), `m` (540 MB) and `e` (326 MB).
- About 2 h 10 min of wall clock (15:39–17:51 CST, including the restart). The first run stopped at state 11 when
  a download failed 3 times (`ChunkedEncodingError`, then `SSLError`; `--retries 2`).
  Rerunning states 11–32 with `--retries 6` recovered it after 4 retries. On the same run,
  states 15 and 17 came back truncated ("not a zip file") 4 and 1 times; the
  `fetch_zip_verified` integrity check re-downloaded them. Nothing was patched by hand.
- `ti` for states 01–10 came from a `--layers ti` rerun on the cached ZIPs: the first run
  used the pre-`ti` code. The 2020 `ti` files (13, 350 polygons, 1.2 MB) were built the same
  way from the cached 2020 ZIPs on both hosts.
- `tests/test_mg.py` on `wsl`: **21 passed** over the full mirror. On the Mac: 21 passed,
  1 skipped (2025 totals need all 32 states).

### National totals vs `contenido.txt` (exact)

| layer(s) | 2020 stated = mirror | 2025 stated = mirror |
|---|---|---|
| `mun` | 2,469 | 2,478 |
| `l` (rural amanzanadas + urban) | 45,397 + 4,911 = 50,308 | 46,894 + 4,904 = 51,798 |
| `lpr` | 295,779 | 291,946 |
| `ti` | 350 (13 states) | 367 (13 states) |
| `ar` | 17,469 | 17,475 |
| `a` | 63,982 | 64,807 |
| `m` + `cd` ("manzanas … incluyendo caserío disperso") | 2,430,116 + 83,737 = 2,513,853 | 2,541,097 + 95,636 = 2,636,733 |
| `ent` | 32 | 32 |

`mg_mun_2025` holds exactly the 2,478 municipalities of the EIC 2025 estimates. The
estimates' 2,478 also match the plan's EIC coverage (750 + 1,721 + 7).

## Deviations from the plan

- **`ti`** was not in the plan ("all 15 layers"): INEGI ships a 16th, optional layer that
  the 2020 mirror had never included. It is now mirrored for both editions (user
  decision).
- **The registry** waits for 1e (as `PLAN.md` already put it) via the new
  `--update-registry` mode, instead of the build's own append.
- **The CLI** (`--dataset mg --edition`) moved to 1e, as for `cpv`.
- The probe's "5 layers differ" was a cross-year comparison; the within-year mix (table
  above) is what makes the default `crs=` necessary.

## Gotchas for later units

- The 2025 ZIPs ship `01lpr.DBF` (upper-case extension); GDAL reads it.
- `upload_release.py` (the superseded GitHub-Release uploader) parses MG names as
  `mg_<suffix>_<NN>`, so it would batch `mg_*_2025_*` as `mg-rest`. It is unused since the
  HF bucket; leave it or fix it if it is ever revived.
- For 3d/4b: the national-ZIP editions must be split per state into
  `mg_{sfx}_{period}_{NN}` to be loadable by `load_mg` unchanged; check their `.prj`
  spellings the same way.
