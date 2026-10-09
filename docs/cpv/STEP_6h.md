# CPV Unit 6h — the EIC 2015 geographic frame (MG period 2015)

Done **2026-10-08** (on the Mac; upload from `wsl`), the 3d leftover (`STEP_3d.md` §«The EIC
2015 frame: not identified»). Gate: the frame identified and mirrored (built, registered,
uploaded, verified), `load_mg(period=2015)`, the CLI, the lineage's 2015 step, tests green.

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| which frame | first offered MG 2013 v6.0 (municipalities = the EIC 2015's); the user asked to **keep looking for v6.2** (Aug 2014). The search found the survey's own product instead (below), used as the frame |
| lineage | **add the 2015 step** (1995 → … → 2010 → 2015 → 2020 → 2025) |
| release | **register and upload** the files (no push, merge or version bump) |

## Finding the frame

INEGI publishes no «Marco Geoestadístico 2015». The candidates, by municipality set (the EIC
2015 microdata have 2,457 municipalities):

| product (UPC) | municipalities | |
|---|---|---|
| MG 2010 v5.0 (702825292812) | 2,456 | lacks Bacalar (23010, 2011) |
| MG 2013 v6.0, Inventario Nacional de Viviendas 2012 (702825292829, national ZIP, 97 MB) | **2,457** | = the EIC 2015's |
| MG 2014 v6.2 (Aug 2014; the OSM wiki records 2,457 municipalities) | 2,457 | not in INEGI's download catalog (no UPC found by the product API, the UPC series of the other MG products, or the web) |
| MG junio 2016 (702825217341) | 2,458 | adds Puerto Morelos (23011, 2015) |
| **Cartografía geoestadística urbana y rural amanzanada. Cierre de la Encuesta Intercensal 2015** (one product per state, UPC 702825209025–702825209339) | **2,457** | the survey's own frame, cut 30 April 2015: **chosen** |

The last was found through a 2016 blog post that mirrors its shapefiles. Its 32 UPCs were
then read from INEGI's product API
(`…/app/api/productos/interna_v2/ficha/datos?upc=`). They are consecutive in INEGI's
alphabetical order of the state names (Chiapas and Chihuahua before Coahuila), at
`…/geografia/Cinter_2015/{State_Name}/{UPC}_s.zip` (2.2 GB in all). Each ZIP has the
2020/2025 per-state layout (`conjunto_de_datos/{NN}{sfx}.shp`, `catalogos/`, `metadatos/`).

## The edition in the package

- **`_catalog.MG_EDITIONS["2015"]`**: `MgEdition(products=_CINTER_2015, layers=…)`. Two new
  fields: `products` (per-state (path, UPC), for an edition published as one product per
  state) and `layers` (the edition's layers, when fewer than `MG_LAYERS`). New
  `mg_layers(period)`.
- **13 layers**: `ent`, `mun`, `a`, `ar`, `l`, `lpr`, `m`, `fm`, `e`, `sia`, `sil`, `sip`
  in every state, plus `ti` in the 13 island states (the same as 2020). There is no `cd`,
  `pe` or `pem`. The island layer is spelled `NNterritorioinsular.shp`
  (`build_marco_geo._SUFFIX_ALIASES` → `ti`).
- **Attribute columns are the product's.** They differ from 2020's for `a`, `lpr` (no
  `CVE_MZA`/`PLANO`), `ti` (`NOMBRE`), `m`, `fm` (no reference streets), `e` (no
  `TIPOSEN`) and `sia`/`sil`/`sip` (`NOMBRE` vs `NOMSERV`, fewer codes). Column order also
  differs. Codes stay zero-padded strings.
- **CRS**: `ccl_itrf92`, the MG's LCC on ITRF92 (as MG 1995–2010). `load_mg`'s default
  EPSG:6372 is a ballpark (null) datum shift: coordinates are bit-identical.
- `CpvEdition("2015").mg_period = "2015"`. `load_mg(layer, state=, period=2015)` raises
  for a layer outside `mg_layers("2015")`. `build_marco_geo.py --period 2015` builds only
  the edition's layers, and `--update-registry` does not report the absent ones.
- CLI: `mxcensus fetch N --dataset mg --edition 2015` (12 files; 13 in an island state).

## Build and numbers

`build_marco_geo.py --period 2015 --no-registry` on the Mac (ZIPs prefetched 8 at a time:
INEGI served ~0.3–0.7 MB/s per connection), then `--layers ti` for the 13 island states:
**397 files**, 1.8 GB.

| layer | features (32 states) | check |
|---|---|---|
| `ent` | 32 | |
| `mun` | 2,458 | 2,457 codes = the EIC 2015 microdata's exactly. Empalme (26025, Sonora) ships a second polygon of zero area, kept |
| `l` | 55,262 distinct codes | 4,546 urban = the product's `leeme` exactly. 50,716 rural (the `leeme` counts 44,833 «rurales amanzanadas»; the layer has more rural polygons) |
| `ti` | 350 | = 2020's 350 island polygons (also MG 2014 v6.2's) |
| `a` / `ar` | 61,424 / 17,463 | |
| `lpr` | 249,246 | |
| `m` / `fm` / `e` | 2,311,569 / 10,974,660 / 6,532,482 | |
| `sia` / `sil` / `sip` | 142,530 / 522,873 / 489,665 | |

## Lineage (`cpv_mun_lineage.yaml`, rebuilt)

`periodos` 1995 … 2010, **2015**, 2020, 2025, with `municipios` 2015 = 2,457. Bacalar
(23010) now dates to 2010 → 2015 (parent Othón P. Blanco, 23004: 97.6% of Bacalar, 36.9% of
its parent). The other 12 municipalities created after the EIC 2015 date to 2015 → 2020.
Still 50 new codes in all. `cpv_municipal_units` accepts 2015 as a start or an end.

## Release

- Registry: `--update-registry` → **3751 → 4148** (+397, additions only, `git diff
  --numstat`).
- Upload: the 397 files copied to `wsl:~/mxcensus/data/parquet` (Tailscale, ~0.6 MB/s), then
  `upload_hf.py upload` (dry run first, never `--delete`), a check of the new URLs and a
  clean-cache fetch through `load_mg`. Recorded in the follow-up commit (§Upload).
- `docs/hf_bucket_readme.md` (provenance row, total 4148), README, CLAUDE.md.

## Upload (follow-up commit)

- Copied to `wsl` with `tar` over ssh (1h15, ~0.6 MB/s); all 397 SHA-256 equal the
  registry's on `wsl`.
- The first dry run listed 794 uploads: macOS `tar` had added an AppleDouble
  `._mg_*_2015_*.parquet` beside every file. They were deleted on `wsl`, and the second dry
  run listed exactly the 397 files (3,751 skipped as identical).
- `upload_hf.py upload` (no `--delete`) uploaded them and the bucket README (total 4148).
- From the Mac, a HEAD of every new URL: 397/397 present with the local size.
- Clean cache (`MXCENSUS_CACHE_DIR` empty, unpatched `POOCH`): `load_mg("mun", state=[2, 23],
  period=2015)` gives 15 municipalities (Quintana Roo with Bacalar, without Puerto Morelos),
  `load_mg("ti", state=2, period=2015)` gives 63 polygons, and `mxcensus fetch 9 --dataset mg
  --edition 2015` fetches 12 files.

## Tests

- `test_mg_2015_products` (`test_cpv.py`): URLs per state, 32 distinct UPCs with valid
  UPC-A check digits, 13 layers, `mg_period`.
- `test_edition_layers_2015` (`test_mg.py`): `--update-registry` upserts the 12 layers of a
  non-island state and reports nothing missing; the `territorioinsular` alias.
- `test_real_mg_2015` (`test_mg.py`, real): the counts above, the municipality set = the
  EIC 2015's, the one duplicate (Empalme), the stored CRS and the lossless EPSG:6372.
- `test_mg_2015_frame` (`test_cli.py`); `test_load_mg_errors` (2015 has no `cd`);
  `test_lineage_document`/`test_municipal_units` (`test_cpv_geo.py`); the lineage rebuild
  test.
- **Full suite**: 1656 passed, 1 skipped (34 min, the Mac's full mirror).
