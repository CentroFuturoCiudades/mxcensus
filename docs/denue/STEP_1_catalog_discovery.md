# DENUE mirror — Step 1: catalog discovery + dry run

Status: **done** (2026-06-01)

## Goal
Discover DENUE's bulk-download URL pattern, enumerate available releases, and prove
the download→verify→convert→geoparquet pipeline on one release/state.

## URL pattern (verified against the live INEGI "masiva" tree)
```
https://www.inegi.org.mx/contenidos/masiva/denue/{YYYY_MM}/denue_{NN}_{MMYY}_csv.zip
```
- `{YYYY_MM}` = folder, e.g. `2020_11`; `{NN}` = zero-padded state (01..32);
  `{MMYY}` = month+2-digit-year, e.g. `1120` (Nov 2020).
- Each per-state ZIP contains **all SCIAN sectors** for that state (no sector split at
  the per-state level — sector splitting only applies to the national `00` files).

## Releases enumerated
Probing `{year}_{mm}/denue_09_{mm}{yy}_csv.zip` found **18** releases (2016-01 …
2025-05). The pre-2016 editions use **different filename templates** (annual year
tokens / full dates), so that probe missed them. Cross-checking a known-good batch
downloader (`jobs_model/scripts/denue_batch_downloader.py`) and **re-verifying every
template against the live tree** added 6 more, for **24 releases total (2010 … 2025-05)**:

```
201000 201100 201200 201307 201310 201502           # pre-2016 (custom templates)
201601 201610 201703 201711 201803 201811 201904 201911
202004 202011 202105 202111 202205 202211 202311 202405 202411 202505
```
Each release carries an explicit `path_template` in `_denue_catalog.py::RELEASES`
(the path/filename is not uniform across releases). Release ids use the data month
where known; the 2010–2012 annual editions have no published month → `"00"` (e.g.
`201000`). Cadence is irregular (2016 has Jan+Oct; 2023 only Nov; no 2014 edition).

### Per-release / per-state quirks (verified live)
- **State 15 (México) is multipart** (`_1`/`_2`) from 2018 onward; the single-file URL
  404s. `denue_zip_entry` returns one `CatalogEntry` per part and the build
  concatenates them into one per-state parquet. Verified: `denue_202011_15.parquet`
  = 700,741 rows from 2 parts, same schema fingerprint as single-part states.
- **State 18, 2015 release** uses date `04062015` (not `25022015`).
- Pre-2016 templates: `2010/denue_{NN}_2010_csv.zip`, `2013_JULIO/denue_{NN}_2013_csv.zip`,
  `2015/denue_{NN}_25022015_csv.zip`, etc.

## ZIP internal structure
```
denue_{NN}_csv/conjunto_de_datos/denue_inegi_{NN}_.csv   # establishments (the data)
denue_{NN}_csv/diccionario_de_datos/denue_diccionario_de_datos.csv   # data dictionary
denue_{NN}_csv/metadatos/metadatos_denue.txt
```
- Inner folder is `denue_{NN}_csv` (no date) → extraction is isolated per state in a
  `{raw}/denue/{YYYYMM}/{NN}/` subdir and the data CSV located by
  `**/conjunto_de_datos/*.csv`.
- The bundled **data dictionary** will seed the variables YAML in Step 3.

## Schema observed (release 202011, state 09)
- **41 columns**, encoding latin-family (chardet: Windows-1252 on a sample, ISO-8859-15
  on the full file — both decode cleanly; `detect_encoding` handles it).
- Columns: `id, nom_estab, raz_social, codigo_act, nombre_act, per_ocu, tipo_vial,
  nom_vial, tipo_v_e_1..3, nom_v_e_1..3, numero_ext, letra_ext, edificio, edificio_e,
  numero_int, letra_int, tipo_asent, nomb_asent, tipoCenCom, nom_CenCom, num_local,
  cod_postal, cve_ent, entidad, cve_mun, municipio, cve_loc, localidad, ageb, manzana,
  telefono, correoelec, www, tipoUniEco, latitud, longitud, fecha_alta`.
- `per_ocu` = personnel strata ("0 a 5 personas", "6 a 10 personas", …, "251 y más
  personas"). `codigo_act` = 6-digit SCIAN. `id` = unique establishment id.

## Artifacts created
- `scripts/_build_common.py` — shared helpers lifted from build_data.py/build_marco_geo.py:
  `detect_encoding`, `fetch_zip`, `verify_zip`, `fetch_zip_verified` (download+verify+retry),
  `update_registry` (append/upsert preserving prior entries; `PRESERVE_PREFIXES` now
  includes `denue_`). build_data.py / build_marco_geo.py will be refactored to import these
  in Step 5.
- `src/mxcensus/data/_denue_catalog.py` — `DenueRelease`, `RELEASES`, `RELEASES_BY_YYYYMM`,
  `latest_release()`, `denue_zip_entry(release, state)`, `CATALOG_VERIFIED_DATE`.
- `scripts/build_denue.py` — `--dry-run --release YYYYMM --states N`: download→verify→
  extract→`_csv_to_geoparquet`→diagnostics (schema fingerprint, rows, cols, encoding,
  geometry-null fraction). No registry update yet.

## Dry-run result (verified)
```
denue_202011_09.parquet  29.7 MB, 474,328 rows, 41 cols, enc=iso8859-15
geometry null fraction: 0.0012
```
GeoParquet round-trip: CRS = **EPSG:4326 (WGS 84)**, all features `Point`, sample point
`(-99.181, 19.367)` (CDMX). `per_ocu`/`codigo_act` values as expected.

## Resolved during Step 1
- **Null geometry:** invalid/out-of-bbox coords are now set to `None` (true null
  geometry), not empty points. Mexico bbox: `(-118.5, 14.3, -86.6, 32.8)`.

## Known issues for Step 2
- **Encoding fuzziness:** chardet's per-file guess varies (Windows-1252, ISO-8859-15,
  cp1250 seen across files); all decoded without error because the byte ranges overlap,
  but Step 2 should consider forcing a latin-family fallback (try utf-8 → latin-1) and
  recording the chosen encoding per file rather than trusting chardet's exact label.
- **Schema fingerprint** is identical across states of a release (confirmed 09 vs 15 for
  202011) — Step 2 can fingerprint one canonical state per release and assert agreement.

## Next — Step 2
Full download of all 18 releases × 32 states (576 ZIPs, multi-GB, long-running);
per-release schema fingerprinting; build `docs/denue/INCONSISTENCY_REPORT.md`
(schema drift, malformed files, within/cross-release duplicates) and report actual
total mirror size.
