# CPV Unit 3d — MG 2010, the EIC 2015 frame, release of 3a–3d

**Part 1 (local) done 2026-10-08** (overnight, unattended, on the Mac). **The release —
registry, upload, verify, clean-cache fetch — waits for `wsl`**: it holds the only HF
token, and Tailscale SSH there asks for an interactive re-login. Nothing else depends on the
release, so units 4a onward continue locally. Their files join the same upload batch.

Gate (unchanged): the 3a–3d files are registered, uploaded and verified, and a clean-cache
fetch plus the unpatched loaders work for 2010 and 2015. **Not met yet** (§Pending).

## MG 2010 v5.0: a national ZIP split per state

`scripts/build_marco_geo.py --period` now accepts every `MG_EDITIONS` period. A
`layout="national"` edition (2010 and the 1995–2005 municipal frames) goes through
`_build_national`:
- `_national_layer_paths` downloads the one national ZIP (`marco_geo_national_url`; cached
  as `mg_{period}_national.zip`) and extracts its nested per-layer ZIPs.
- Each shapefile maps to a layer suffix by its name (`_NATIONAL_LAYERS`):
  - `Entidades` → `ent`, `Municipios` → `mun`, `AGEB_urb` → `a`;
  - `Localidades_urbanas` → `l`, `Localidades_rurales` → `lpr`;
  - an unknown shapefile is reported and skipped.
- Each layer is read whole, normalized like the per-state editions (single → Multi*
  geometries, codes as strings, source CRS kept), and split on its entity code
  (`_state_codes`: `CVE_ENT`, else `CVEGEO[:2]` — 2010's AGEB layer has only `CVEGEO`).
  An entity code outside 01–32 raises.
- The output uses the same `mg_{suffix}_{period}_{NN}.parquet` names. `--update-registry`
  hashes what is built (`_national_built`).

**Build** (`--period 2010 --no-registry`, Mac):
- The ZIP is `702825292812_s.zip`, 100 MB: `mge`, `mgm`, `mgau`, `mglu`, `mglr` 2010v5_0.
- It produced **160 files** (5 layers × 32 states), 113 MB.
- **CRS**: an LCC on ITRF92 (GRS 1980; the same parameters as EPSG:6372). The mirror keeps
  it; `load_mg(…, period="2010")` returns EPSG:6372 by default.

| layer | features | geometry | columns |
|---|---|---|---|
| `ent` | 32 | MultiPolygon | `CVE_ENT`, `NOM_ENT`, `OID` |
| `mun` | 2,456 | MultiPolygon | `CVE_ENT`, `CVE_MUN`, `NOM_MUN`, `OID` (no `CVEGEO`) |
| `a` (urban AGEBs) | 56,195 | MultiPolygon | `CVEGEO` (13), `CODIGO`, `GEOGRAFICO`, `FECHAACT`, `GEOMETRIA`, `INSTITUCIO`, `OID` |
| `l` (urban localities) | 4,525 | MultiPolygon | `CVE_ENT`, `CVE_MUN`, `CVE_LOC`, `NOM_LOC`, `OID` |
| `lpr` (rural localities) | 187,719 | MultiPoint | + `CVE_AGEB` (rural, e.g. `106-8`) |

**Checks.** There is no `contenido.txt`, so the counts were checked against the Censo 2010
ITER:
- the same **2,456** municipalities;
- **4,525** urban localities, as many as the urban localities of the 2010 AGEB file;
- **192,244** localities in all, against the ITER's 192,247 locality rows.

## The EIC 2015 frame: not identified

*Resolved in 6h (`STEP_6h.md`): INEGI's «Cartografía geoestadística urbana y rural
amanzanada. Cierre de la Encuesta Intercensal 2015», mirrored as MG period 2015.*

INEGI publishes no frame "for" the Encuesta Intercensal 2015. Its microdata stop at the
municipality (`ENT`/`MUN`), so only a municipal layer matters. Candidates are the national
MG of 2014–2016 (versions 6.x; an IDEGEO layer names `mglu2013v6_2`). Two web searches did
not settle which INEGI product the survey used.

Left open for the session with the user. Simplest option: pick the MG edition whose
municipality set equals the EIC 2015 one (2,457 municipalities) and record the choice.

## Tests (`tests/test_mg.py`)

- `test_national_layer_names_and_state_codes`.
- `test_build_national_splits_per_state`: a synthetic national ZIP with nested shapefile
  ZIPs and an unknown layer. It checks the state filter, the `CVEGEO` split, the kept CRS,
  the cleanup and `_national_built`.
- `test_real_mg_2010_counts` (`_REAL`): the per-layer counts, and that `load_mg("mun",
  state=1, period="2010")` is EPSG:6372.

## Pending (needs `wsl`)

1. Bring `wsl:~/mxcensus` to the branch (see `HANDOFF.md`), then copy the Mac-built files
   there or rebuild them:
   - `build_cpv.py --periods 2000 2005 --tables viviendas hogares personas migrantes`;
   - `build_marco_geo.py --period 2010 --no-registry`.

   Compare `sha256sum` with the Mac for the 2010/2015 CPV files (rebuilt on both hosts).
2. Registry: `build_cpv.py --update-registry` (2010, 2015 and, once 4b is in, 2000/2005) and
   `build_marco_geo.py --period 2010 --update-registry`. Then `upload_hf.py upload` and
   `verify`, and a clean-cache fetch with the unpatched loaders.
3. CLI: `fetch --dataset cpv --edition 2010|2015` and `--dataset mg --edition 2010` (they
   offer only registered files); README, `hf_bucket_readme.md`, CLAUDE.md totals; version
   0.7.0.
