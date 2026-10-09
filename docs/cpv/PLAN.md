# Plan — multi-year census family (`cpv`): EIC 2025 first, then CPV 2020 → 1990

Approved 2026-10-07. This file is the **design**; the live status and the instructions for
the next session are in [`HANDOFF.md`](HANDOFF.md); each finished unit has a `STEP_<unit>.md`.

## Execution: one unit per session

The work runs over many Claude Code sessions. **Each session executes exactly one unit
below, then hands off.** Units are sized to fit one session; if one overruns, stop at a
clean checkpoint, record the split in `HANDOFF.md`, and leave the remainder as the next
unit.

| unit | scope | depends on | gate (must hold before handing off) |
|---|---|---|---|
| **0** | Groundwork: build-script hazards, MG editions, `_cpv_catalog.py` (all 8 editions), CLI selector map, probe doc, catalog/CLI/legacy tests | — | ✅ done 2026-10-07 (`STEP_0_probe.md`) |
| **1a** | `scripts/build_cpv.py`: build mode, `--dry-run`, multi-member ZIPs, faithful-raw parquet; EIC 2025 smoke build locally (states 01, 09 + estimaciones); full 2025 build on `wsl` | 0 | ✅ done 2026-10-07 (`STEP_1a.md`): 97 files on `wsl`, 0 failures, Σ `FACTOR` = published totals |
| **1b** | Dictionaries: `scripts/_dict_fd.py` (FD xlsx → `parse_ddi` shape), classification catalogs, hand-curated `variables_cpv_core.yaml`, `--dictionary --schema-map --variables --report-only --validate` | 1a | ✅ done 2026-10-07 (`STEP_1b.md`): 0/97 failures on `wsl`; every observed code documented by the FD (stdlib xlsx reader, no `openpyxl`) |
| **1c** | Loaders: `cpv.py` (`load_cpv`, `load_cpv_viviendas/personas/migrantes`, `load_cpv_survey`, `variables_cpv_labels`), `cpv_aggregates.load_cpv_estimaciones`; `_resources`/`__init__`; `tests/test_cpv.py` (offline + `_REAL`), `test_schema_groups.py` family loops; EIC 2025 data checks (§Verification) | 1b | ✅ done 2026-10-07 (`STEP_1c.md`): pytest green; every Σ `FACTOR` check exact (state, municipality, ≥50k locality, nation on `wsl`); CLI moved to 1e |
| **1d** | MG EIC 2025: full `build_marco_geo.py --period 2025` on `wsl` (480 files); `load_mg(layer, *, state, period)`; decide on the CRS-spelling difference (`STEP_0_probe.md` §MG) | 0 | ✅ done 2026-10-07 (`STEP_1d.md`): 493 files (480 + `ti` for 13 island states; 2020 `ti` added too); `load_mg` (default CRS EPSG:6372, a PROJ no-op) tested; national totals = `contenido.txt` exactly; CLI and registry moved to 1e |
| **1e** | Registry + `upload_hf.py upload`/`verify` + clean-cache fetch; CLI `--dataset cpv --edition` and `--dataset mg --edition` (moved from 1c/1d: the CLI never offers unregistered files); README/CLAUDE.md/`hf_bucket_readme.md`/pyproject; version bump | 1a–1d | ✅ done 2026-10-07 (`STEP_1e.md`): registry 1932 → 2535 (additions only), 603 files uploaded + verified, clean-cache fetch + unpatched loaders OK; CLI `cpv`/`mg`; docs; v0.5.0 |
| **2a** | CPV 2020 into the family (`viviendas`/`personas`/**`migrantes`**, `iter`, `ageb` as `cpv_*_2020_NN`); 2020 dictionary (RNM DDI probe, else FD xlsx) | 1 | ✅ done 2026-10-07 (`STEP_2a.md`): 160 files on `wsl`, `--validate` 0/257; dictionary = FD xlsx (DDI 632 found but incomplete); 2020 gids `g01`, 2025 → `g02`; core `Tablas` scope |
| **2b** | 2020↔2025 core harmonization; raw-vs-harmonized and legacy-equality tests; upload | 2a | ✅ done 2026-10-07 (`STEP_2b.md`): rows/Σ `FACTOR` identical raw vs harmonized (2020 + 2025, 32 states); 2020 files = legacy cell by cell (32 states); ITER/AGEB geography harmonized too; registry 2535 → 2695, uploaded + verified; v0.6.0 |
| **3a** | EIC 2015 (`TR_VIVIENDA`/`TR_PERSONA`, DDI 214) | 2 | ✅ done 2026-10-07 (`STEP_3a.md`): 64 files on `wsl`, `--validate` 0/321; Σ `FACTOR` = INEGI's tabulados exactly (32 states + nation, dwellings, population, men, women); dictionary = the FD `.xls` + `TC_*` catalogs via a stdlib BIFF8 reader (DDI 214 incomplete — user's choice); 2015 = `g01` |
| **3b** | CPV 2010 microdata (DBF via `dbfread(raw=True)`, code pages, DDI 71, `ID_PER`/`ID_MIN`, state-scoped `ID_VIV`) | 3a | ✅ done 2026-10-07 (`STEP_3b.md`): 96 files on `wsl`, `--validate` 0/417; Σ `FACTOR` = the CA tabulados exactly (outside `CLAVIVP` 5–7); stdlib DBF reader `scripts/_dbf.py` (no `dbfread`); FD `.xls` (no Tipo column) + DBF catalogs; national keys under `harmonize=True`; core `Periodos` |
| **3c** | Aggregates `load_cpv_iter`/`load_cpv_ageb` (2020 + 2010), `cpv_iter_crosswalk.yaml`, equality with legacy `load_census` | 3b | ✅ done 2026-10-07, verified 2026-10-08 on the Mac (`STEP_3c.md`): 2010 ITER/AGEB built (64 files); `load_cpv_census(2020)` = legacy `load_census` in all 32 states (two census-chain bugs found and fixed: the legacy collective imputation's NA crash in states 08/15/16, 2010's AGEB `TVIVHAB` shortfall); `--validate` 0/481; crosswalk 296 indicators |
| **3d** | MG 2010 v5.0 (national ZIP → per-state split); identify the 2015 frame; upload 3a–3d | 3c | ✅ done 2026-10-08 (`STEP_3d.md`): national-ZIP MG builder, MG 2010 built (160 files; municipalities = the 2010 ITER's); registered + uploaded in the release batch (`STEP_6b.md`); the 2015 frame is still unidentified |
| **4a** | 2000 + 2005 microdata (composite keys, `hogares` level, unweighted 2005) | 3 | ✅ done 2026-10-08 on the Mac (`STEP_4a.md`): 192 files; `--validate` 0/673; dictionaries = 2005 FD `.xls` + catalog workbook, 2000 FD PDF (`parse_fd_pdf`); derived keys + `ID_HOG` level, `load_cpv_hogares`; core `Recodificar` (SEXO 2 → 3); 2000 Σ `FACTOR` bounded by the ITER (ratio estimator on preliminary counts) |
| **4b** | 2000 + 2005 ITER (+ crosswalk), municipal MGs 2000/2005; upload | 4a | ✅ done 2026-10-08 on the Mac (`STEP_4b.md`): ITER 2000/2005 (64 files; national POBTOT = INEGI's), `--validate` 0/737; crosswalk 388 indicators (description auto-pairs + reviewed pairs, `Renombrar` per edition); MG 2000/2005 (192 files; municipalities = ITER); uploaded in the release batch |
| **5a** | 1990 + 1995 ITER (DBF) + crosswalk | 4 | ✅ done 2026-10-08 on the Mac (`STEP_5a.md`): 64 files; `--validate` 0/801; dictionaries = INEGI's ITER descriptor PDFs (AES; read via poppler `pdftotext -tsv`, `parse_iter_fd_tsv`); crosswalk 402 indicators; 1995's one/two-dwelling localities exist only as aggregates; 1995 spilled-name rows repaired |
| **5b** | 1990 + 1995 samples, MG 1995; upload | 5a | ✅ done 2026-10-08 on the Mac (`STEP_5b.md`): 96 files (1995 `datgen95` is a person file → `personas`); `--validate` 0/897; FDs from encrypted PDFs (poppler; `parse_fd_1990_text`/`parse_fd_1995_text`), ranges reconciled with the data; 1990 keys via folio occurrences; 1995's three weights; MG 1995 (64 files); uploaded in the release batch |
| **6a** | Cross-year geographic crosswalk (AGEEML / Archivo Histórico de Localidades) | 5 | ✅ done 2026-10-08 (`STEP_6a.md`): municipal lineage from the MG polygons 1995–2025 (50 new codes, none retired; `cpv_mun_lineage.yaml`, `scripts/build_geo_crosswalk.py`); `cpv_mun_lineage()`, `cpv_municipal_units(start, end)`; localities not covered |
| **6b** | Port `load_extended_*` derived columns onto labelled frames; `crosstabs` per edition | 6a | ✅ done 2026-10-08 (`STEP_6b.md`): `cpv_derived` (`derived=True`; 2020 = legacy in 32 states; 2025 via `_RECODE`; 2015/2010 identical items), `cpv_constraints` per edition (2025 cells = estimates); the release batch went first: registry 2695 → 3751, 1,056 files uploaded, v0.7.0 |
| **6c** | Review of the pending decisions (3b–6b) with the user; follow-ups | 6b | ✅ done 2026-10-08 (`STEP_6c.md`): legacy `impute_collective` NA guard (`load_census` loads all 32 states), `FACTOR` for harmonized 1995 frames, INEGI's `DISCAPACIDAD`/`LIMITACION` (+ the CPV constraints); 17 overnight decisions confirmed; then `main` = v0.7.0 |
| **6d** | The 2015/2010 recoded items in `cpv_derived` (`DHSERSAL`, `CONACT`, `SITUA_CONYUGAL`, `EDUC`, 2015 commute, 2010 `DISCAP`) | 6c | ✅ done 2026-10-08 (`STEP_6d.md`): reviewed recodes (+ 2010 `ESTCON`), no `DHSERSAL_IMSS_BIENESTAR` before 2020, 2015's own commute dummies, 2010 `LIM_ACTIVIDAD` + the 2010 ITER's limitation constraints (`_EDITION_CELLS`); 2015 personas 2 → 33 derived columns, 2010 4 → 17; 2010 constraints 91 → 126; 32-state sweep clean |
| **6e** | The 2015/2010 birthplace, residence five years earlier, parent/partner pointers; 2015 `FINANCIAMIENTO` | 6d | ✅ done 2026-10-08 (`STEP_6e.md`): 2010's split entity/country items and pointer pairs, new `MADRE_EN_VIVIENDA`/`PADRE_EN_VIVIENDA` (2010–2025), 2015's own financing dummies; 2015 personas 33 → 40, viviendas 5 → 13, 2010 personas 17 → 22; 2010 constraints 126 → 138; 2015 migration/financing and 2010 residence = INEGI's tabulados in all 32 states (up to the unspecified-state group, legacy rule kept); 32-state sweep clean |
| **6f** | The 2015/2010 coarse occupation/activity (SINCO/SCIAN bridges) and 2010 religion | 6e | ✅ done 2026-10-08 (`STEP_6f.md`): SINCO two-digit group (2010: 4 digits; group 59 → 52, as SINCO 2019), SCIAN sector, 2010 `RELIGION_CAT` by its catalog's groups (neo-Israelites → evangelical, 2020's grouping, user's choice); 2015 personas 40 → 42, 2010 22 → 25; 2010 constraints 138 → 142 (`PNCATOLICA` own cell); occupation/activity = INEGI's 2015 and 2010 tabulados in all 32 states, exactly |
| **6g** | `PSIND_LIM`'s exact rule | 6f | ✅ done 2026-10-08 (`STEP_6g.md`): not disabled, not limited, no mental condition, leaving out only the persons with all seven answers unspecified; exact in all 32 states, the nation and 2,471 municipalities of the EIC 2025; new `SIN_DISC_LIM` (2020/2025) and the CPV `PSIND_LIM` cell on it (25/25 person estimates exact) |
| **6h** | The EIC 2015 geographic frame (3d leftover) | 6g | ✅ done 2026-10-08 (`STEP_6h.md`): the survey's own «Cartografía geoestadística urbana y rural amanzanada. Cierre de la Encuesta Intercensal 2015» (a UPC per state; 2,457 municipalities = the EIC 2015's) as MG period 2015: 397 files (12 layers + `ti`), registry 3751 → 4148, uploaded + verified; lineage 2015 step; `MgEdition.products`/`layers`, `mg_layers` |
| **6i** | Derived columns for 2000/2005 | 6h | ✅ done 2026-10-08 (`STEP_6i.md`): 2000 personas 17 / viviendas 5, 2005 13 / 4 (age, income, hours, education with the 2000/2005 level-and-antecedent items, activity, marital status, birthplace/residence, 2000 religion with «Blanco por pase» under 5, one-item-per-institution coverage, 2000 SCIAN sector, dwelling class/rooms/drainage); constraints 2000 29 + 4, 2005 38 + 8; 2000 = INEGI's sample tabulados within 0.02 points outside Chiapas; 32-state sweep clean |
| **6j** | Derived columns for 1990/1995 | 6i | ✅ done 2026-10-08 (`STEP_6j.md`): the dwelling frames of 1990/1995 built from their person files (`load_cpv_viviendas`; user's choice), 1990 personas 9 / viviendas 4, 1995 8 / 3 (age, education from their own items, activity, marital status, birthplace, residence five years earlier, hours, income — 1990's in new pesos —, 1990 religion; rooms, bedrooms, drainage, 1990 class); constraints 1990 12 + 5, 1995 6 + 3 (and the 1995 `SEXO` cell fixed: its sex is `P3_5`); = the 1990/1995 ITER shares within tenths of a point for persons, except 1990's `P15PRI_CO` (INEGI leaves out técnica after primaria; open question); 32-state sweep clean |
| **6k** | `P15PRI_CO` and técnica after primaria (6j's open question) | 6j | ✅ done 2026-10-08 (`STEP_6k.md`): INEGI's primaria completa leaves técnica after primaria out in every ITER that publishes it (1990, 2000 by its dictionary, 2010 and 2020 = the básico tabulados' «6 grados» exactly in all 32 states; the EIC 2015 tabulados fold it in); new `EDUC_INEGI` (every edition; «Técnica_primaria» apart, 1990 via `TEC_PRIM`) and the 18 education constraints on it (user's choice: a finer column, not a flag); `P15PRI_CO` now within 0.29/0.48/0.44 points of the 1990/2000/2010 ITER in every state (was 3.03/1.36/1.29); legacy YAML frozen |
| **6l** | Dictionary fixes: the 2005 FD's `':'` category, 1990's «0» label | 6k | ✅ done 2026-10-08 (`STEP_6l.md`): `_dict_fd` skips the 2005 FD's vertical-ellipsis rows (`GRA_APRO`/`NHIJNAVI`/`NUHIJSOB` lose `':'`; every other parse byte-identical); `--variables` labels 1990's unlabelled 0 «Blanco por pase» in its 20 coded person items (`_label_blank_zero`); dictionaries regenerated |
| **6m** | A BIFF5 reader; the tabulado checks as a maintainer script | 6l | ✅ done 2026-10-08 (`STEP_6m.md`): `_dict_fd.read_xls` reads Excel 95 (the CGPV 2000 tabulados; every BIFF8 parse byte-identical); `scripts/check_cpv_tabulados.py` runs the 6e/6f/6i checks (+ EIC 2015 activity, 2000 education on `EDUC_INEGI`) over every state, sex and the nation → `TABULADOS_REPORT.md`: 10,461 cells, 2010/2015 exact, 2000 within 0.04 points outside Chiapas |
| **6n** | The legacy constraints on the 2000/2005/2010 samples' own items | 6m | ✅ done 2026-10-08 (`STEP_6n.md`): 2010 `CLAVIVP_CAT` (2000's recode; 2010 dwellings 0 → 26 constraints), `_EDITION_CELLS` for 2000/2005/2010 (language, literacy, attendance; floor, electricity, water, sanitary service, goods, services; 2000 4 → 16 + 29 → 34, 2005 8 → 21 + 38 → 43); crosswalk fix: 2000's `VP_CCUART` is one room without the exclusive kitchen, not `VPH_1DOR`; every new cell within its edition's sample-vs-census band in all 32 states |

The user asked (2026-10-08, afternoon) for all four post-6e candidates in one session, one
unit each (6f–6i), with a local commit per unit; push, merge, version and upload wait for
the user. 6j (evening) was agreed from the candidates; merge into `main` as 0.8.0 follows it.
6k and 6l (night) were agreed from the HANDOFF candidates, one session, a commit each.
6m onwards (the same night): the user asked for the next units to proceed unattended,
committing and pushing each, for review in the morning.

### Session protocol

1. **Start**: read `docs/cpv/HANDOFF.md` (status, next unit, gotchas) and the parts of this plan
   it points to; `git status` / `git log --oneline -5` on branch `cpv-integration`.
2. **Work** only on the next unit. Use `.venv/bin/python` (not `uv run`, which may re-sync the
   venv); full builds and uploads run on the `wsl` host.
3. **End** (always, even when stopping early):
   - test suite green (`.venv/bin/python -m pytest -q`);
   - write `docs/cpv/STEP_<unit>.md` (what was built, decisions, numbers, deviations from this plan);
   - tick the unit in the table above and update this plan if the design changed;
   - rewrite `HANDOFF.md` (status line, next unit with concrete first steps, open questions, gotchas);
   - update the auto-memory note `cpv-integration-handoff`;
   - commit on `cpv-integration` (with the user's go-ahead), then give the user the kickoff
     prompt for the next session (in `HANDOFF.md`).

## Context

Census support today is **CPV 2020 only, with no year concept anywhere**: `aggregate.py`
(`load_census(state=)`), `extended_personas.py`/`extended_viviendas.py`, `data/_catalog.py`
(2020 URLs), `scripts/build_data.py` (inferred dtypes), and the mirror files
`iter_NN`/`resargebub_NN`/`personas_NN`/`viviendas_NN` (128) plus MG 2020 `mg_{sfx}_NN` (480).
DENUE, ENOE and ENIGH are multi-year families. Each uses faithful-raw `dtype=str` parquet,
fingerprint schema groups, warn-not-raise validation, dictionaries in the order core > DDI > data,
core-only `harmonize=`, and labelled analysis-ready loaders with a shared nested index.

INEGI published the **Encuesta Intercensal 2025 on 22 Sep 2026**. Its microdata are per state
(CSV: `viviendas`, `personas`, `migrantes`, with `FACTOR`) and are representative for all 2,478
municipalities and the 233 localities of 50k+. It has **no ITER and no AGEB data**. Its only open
aggregate is a national estimates file (5 estimator rows per geography). There is **no DDI on the
RNM** yet; the dictionary is `eic2025_micro_fd.xlsx`. The goal is to ship EIC 2025 now as the
first edition of a new `cpv` family. That family is designed from the start to take every census,
conteo and intercensal edition back to 1990 the same way ENIGH takes editions.

**User decisions (2026-10-07):**
- Rebuild 2020 into the family under new names. The legacy files and loaders stay untouched.
- Use the `cpv_` prefix and `load_cpv*` loaders.
- Mirror **all MG layers** for EIC 2025: the 15 every state has plus the optional `ti`
  (territorio insular), which 1d also added for 2020 (13 new `mg_ti_NN` files).
- Plan every edition **back to 1990** in detail.

## Edition matrix (verified 2026-10-07; details go into `docs/cpv/STEP_0_probe.md`)

| period | kind | microdata (tables · format · weight · dictionary) | iter | ageb | other | MG |
|---|---|---|---|---|---|---|
| 1990 | censo | `cgpv90p_{NN}_dbf` 10% sample, one flat person file (`m_10NN.dbf`) · DBF · **no weight** · none | DBF/TXT | — | — | none known |
| 1995 | conteo | `cpv95_{NN}_dbf` (`datgen95` = household record → `hogares`, `migint95`) · `FAC_POB/FAC_VIV/FAC_PROM` · none | DBF/TXT | — | — | municipal 1995 `702825292836` (national ZIP) |
| 2000 | censo | `cgpv2000_{NN}_dbf` (`VHO_F`/`PER_F`/`MIN_F`) · `FACTOR` · DDI 141 | CSV `cgpv2000_iter_{NN}` | — | — | municipal 2000 `702825292843` (national ZIP) |
| 2005 | conteo | `cpv2005_{NN}_dbf` (`trvmue`/`trhmue`/`trpmue`) · **no weight** · DDI 140 | CSV `cpv2005_iter_{NN}` | — | — | municipal 2005 `702825292850` (national ZIP) |
| 2010 | censo | `mpv/MC2010_{NN}_dbf` (Viviendas/Personas/Migrantes; cp1252; state-scoped keys) · `FACTOR` · FD `.xls` + DBF catalogs (DDI 71 exists, incomplete — unused) | CSV `iter_{NN}_2010` (lowercase) | CSV `resageburb_{NN}_2010` | — | v5.0 `702825292812` (national ZIP) |
| 2015 | intercensal | `eic2015_{NN}_csv` (`TR_VIVIENDA`/`TR_PERSONA`, no migrantes; cp1252; unpadded keys) · `FACTOR` · FD `.xls` + `eic2015_catalogos.zip` (DDI 214 exists, incomplete — unused) | — | — | — | probe (MG 2014 v6.2?) |
| 2020 | censo | `Censo2020_CA_{abbr}_csv` (+ `Migrantes`) · `FACTOR` · FD xlsx (DDI 632 exists, incomplete — unused) | CSV | CSV | — | legacy `mg_{sfx}_NN` |
| 2025 | intercensal | `eic2025_micro_{NN}_csv` · `FACTOR` · FD xlsx | — | — | `estimaciones` (`conjunto_de_datos_eic2025_105`, cp1252) | EIC 2025 `794551196649` |

**URL and server quirks:**
- Content trees: `/contenidos/programas/{ccpv/<yr>|intercensal/2015|eic/2025}/`.
- Soft-404s come back as 200 + `text/html` (2263 bytes), so judge a file by Content-Type.
- File-listing API: `…/app/api/descarga/componente/descargamasiva/lista/archivoscompaginacion?…&idBiinegi=` with ids EIC2025 = 3455, EIC2015 = 1714, CPV2020 = 3001, CPV2010 = 487, Conteo2005 = 3, CGPV2000 = 2, Conteo1995 = 343, CGPV1990 = 781.

## Architecture

**One family, two loader modules.** The catalog, build script, schema map, YAMLs and file
prefix are shared.
- `src/mxcensus/cpv.py` holds the microdata loaders, on the ENIGH pattern, plus the shared private
  helpers (`_group_of`, `_group_schema`, `_validate`, `_harmonize`, `_resolve_period`, `_fetch`).
- `src/mxcensus/cpv_aggregates.py` holds the aggregate products (estimaciones now, ITER/AGEB
  later). It does its own level splitting on **string** codes.
- `aggregate.py`, `extended_*.py`, the legacy files and `load_mg_census` are **frozen as the
  legacy 2020 path**. They depend on inferred dtypes and 2020 names, so they are not re-pointed
  to the new files.

**Files** (registry keys; faithful raw, every column `str`, zstd):
- Per state: `cpv_{table}_{year}_{NN}.parquet`. National: `cpv_estimaciones_2025.parquet`.
- Canonical tables: `viviendas`, `hogares` (2005 only), `personas`, `migrantes`, `iter`, `ageb`,
  `estimaciones`. Table names never contain `_`.
- Parse with `^cpv_(?P<table>[a-z]+)_(?P<period>\d{4})(?:_(?P<state>\d{2}))?$`.
- MG: `mg_{sfx}_{year}_{NN}.parquet` (e.g. `mg_mun_2025_09`). This keeps the preserved `mg_`
  prefix; the legacy `mg_{sfx}_{NN}` permanently means 2020.

**Catalog: `src/mxcensus/data/_cpv_catalog.py`.**
- Frozen `CpvEdition(period, year, kind, program_path, tables, per_state, ddi_id, biinegi_id, mg_upc)`.
- Per-product URL builders (microdata, iter, ageb, estimaciones).
- `members(table)`: one microdata ZIP holds several tables, as in ENOE.
- `EDITIONS`, `EDITIONS_BY_PERIOD`, `latest_edition(table=None)`: microdata → 2025, iter → 2020.
- `find_member(names, edition, table, state)` with a sole-file fallback, `mg_zip_url(period, state)`
  and `mg_filename(period, sfx, state)`.
- Reuse `STATE_ABBR`, `STATE_CODE_FMT`, `STATE_SLUG_MG` and `CatalogEntry` from `data/_catalog.py`.
- **All eight editions are declared in Phase 0**; each later phase only enables a build.

**Schema and dictionaries** (reuse `_schema_groups.py` unchanged):
- `cpv_schema_map.yaml` has one section per table: `latest`, `fingerprints`, and `groups` holding
  `{n_columns, files: <count>, periods, states (only when a group covers part of a year), columns}`.
  There are no filename lists, and gids are chronological.
- `variables_cpv_{table}_{gNN}.yaml` = core > dictionary > data. `variables_cpv_core.yaml` is
  hand-curated and never regenerated, under the contract header of `variables_enoe_core.yaml`.
- **Dictionary sources:**
  - RNM DDI through `scripts/_dict_ddi.py`, with the ids taken from `CpvEdition.ddi_id` (2000 = 141,
    2005 = 140, 2010 = 71; 2015 = 214 and 2020 = 632 are recorded but unused — Nesstar
    exports with incomplete value labels, so 2015/2020 use their FD workbooks, `STEP_2a.md`,
    `STEP_3a.md`). `build_cpv.py --dictionary` fetches them.
  - `scripts/_dict_fd.py::parse_fd_xlsx(path, catalogs) -> {stem: {VAR: meta}}` in the same shape
    as `parse_ddi`, generalising `utils.get_cats_from_excel`. It reads the workbook with stdlib
    readers (`read_xlsx`; since 3a also `read_xls` for the legacy BIFF8 workbooks of 2015 and,
    later, 2010/2005; no `openpyxl`/`xlrd`). It covers EIC 2025, CPV 2020 and EIC 2015 (renamed
    `parse_fd` in 3a). `fd_entry` builds the entries (1b, `STEP_1b.md`).
  - Aggregates use INEGI's `diccionario_datos_*.csv` (`_dict_fd.parse_indicator_csv`):
    `Tipo: numeric`, `Especiales` from the dictionary's own footnotes (2025: `NA`, `MI`), no
    `Rango` (a column mixes the five estimators), and `--cat-threshold 0` (`_TABLE_THRESHOLD`).
  - 1990/1995 have no DDI: use DBF field metadata, then data enumeration, and flag it.
    (5a: their ITER has descriptor PDFs, `doc/fd_iter_{1990,1995}.pdf`, read via poppler.)
- Large classification codes (SINCO, SCIAN, country, language from `889463931966_csv.zip`) get
  `Tipo: string` plus a `Catálogo:` note, not huge `Categorías`.
- `_dict_ddi.observed_values` must read **per column** (`pq.read_table(columns=[c])` +
  `pyarrow.compute.unique`). Whole frames over 32 personas files would exhaust memory.

**Keys** (alias KeySpecs; `level_key` drops components absent everywhere):
- `_DWELLING = [("ID_VIV",)]`
- `_HOUSEHOLD = _DWELLING + [("ID_HOG",)]` (4a: 2000 and 2005; `ID_HOG` derived, absent
  elsewhere so `level_key` drops it)
- `_PERSON = _DWELLING + [("ID_PERSONA", "ID_PER")]`
- `_MIGRANT = _DWELLING + [("ID_MII", "ID_MIN")]`, a sibling of persons, not nested under them
- 2000/1990/1995 keys are composite and probed in their phases. (4a) 2000 and 2005 have no
  key column: `cpv._composite_keys` derives `ID_VIV`/`ID_HOG`/`ID_PERSONA`/`ID_MII` from the
  parts (2000's persons by file order); see `STEP_4a.md`.
- Keys and geography codes are passed as `skip=` so they stay joinable strings.

**Harmonization (core-only; the canonical spelling is the latest edition's uppercase)**:
- Uppercase all names.
- Rename `ENT→CVE_ENT`, `MUN→CVE_MUN` (2b; the aggregates' `ENTIDAD`/`LOC`/`AGEB`/`MZA` renames
  are table-scoped). (3b) `ID_PER`/`ID_MIN` are **not** renamed: 2010's keys are serials unique
  within a state, so `harmonize=True` builds national, nested keys instead
  (`ID_VIV` = entity + serial, `ID_PERSONA` = `ID_VIV` + `NUMPER`, `ID_MII` = `ID_VIV` +
  rank); `TAM_LOC` is **not** renamed onto `TAMLOC` (4 classes vs 5).
- (3b) A core entry may carry `Periodos`, the editions its codes were verified for (2010's
  `CLAVIVP` is another classification): outside them the column keeps its own dictionary,
  is not padded and is not checked against the core.
- Zero-pad `CVE_ENT` (2), `CVE_MUN` (3), `LOC50K`/`CVE_LOC` (4) and `CVE_MZA` (3). Derive
  `CVEGEO` from the leading geographic parts (5/9/16 characters), or check it when present.
- (3a) Zero-pad `ID_VIV` (12), `ID_PERSONA` (≥ 14) and `CLAVIVP` (2): the EIC 2015 CSVs
  drop leading zeros (`_CODE_PAD`; `zfill` is a no-op on the padded editions). The 2010
  `ID_VIV` (8 characters, unique within a state only) must be made national before this pad
  applies to it (3b).
- `FACTOR` becomes numeric.
- A frame holding both a legacy column and its target raises; a missing core source warns.
- Non-core columns pass through verbatim.
- Validated by `_latest_schema(table)` built from the core YAML.
- The core grows only after a variable's codes are verified in every edition it covers. Geography is
  **not** reconciled across municipal splits (Phase 6).

**Loaders:**
- `load_cpv(survey_path=None, *, table, period=None, state=None, harmonize=False, labels=False)` returns the raw table.
- `load_cpv_viviendas/personas/migrantes(period=None, *, state, harmonize=False, labels=True)` are
  analysis-ready: numeric `FACTOR`, indexed, labelled and strictly validated (`_finish_labelled`).
- `load_cpv_survey(period=None, *, state, …)` returns `(viviendas, personas, migrantes | None)` with
  a shared nested index.
- `variables_cpv_labels(table, gid)`.
- `state: int | Sequence[int] | None`:
  - Per-state tables: `None` raises (no accidental multi-GB fetch). A sequence concatenates and
    must fall in one group unless `harmonize=True`.
  - National tables: `state` filters rows on `CVE_ENT`.
- `cpv_aggregates.load_cpv_estimaciones(period=None, *, estimador="valor", nivel=None, state=None,
  survey_path=None)` returns one row per geography and one column per indicator, indexed
  `(CVE_ENT, CVE_MUN, CVE_LOC)`.
  - An ordered `NIVEL` column takes `nacional | estatal | municipal | resto_estatal (997/9997) | localidad`.
  - `ESTIMADOR` maps to `valor|ee|li|ls|cv`. A list or `None` keeps `ESTIMADOR` as the last index level.
- Geometry: new `mg.load_mg(layer, *, state, period="2020", crs="EPSG:6372")`. It reads legacy
  names for 2020 and `mg_{sfx}_{year}_{NN}` otherwise. INEGI spells the one MG projection two
  ways within each edition; the mirror keeps the source CRS and `crs=` (default EPSG:6372, a
  PROJ no-op) puts every layer on one CRS object (`STEP_1d.md`).

## Phases

### Phase 0 — groundwork (no data)
- **Fix `scripts/build_data.py`.** It ends with `pooch.make_registry(output_dir)`, which would
  **wipe the 373 ENOE entries** that are not present locally. Switch it to
  `_build_common.update_registry` and drop its duplicate fetch/verify helpers.
- **Fix the `scripts/build_marco_geo.py` cache collision.** It caches `mg_{code}.zip` and extracts
  to `raw/mg/{code}` with no year, so an MG 2025 build would silently reuse the 2020 ZIP.
  - Parameterise it with `--period` (UPC from the catalog) and put the year in the cache and raw names.
  - Write `mg_{sfx}_{year}_{NN}`, discover layers from the ZIP, and record any deviation from the 15.
- `scripts/_build_common.PRESERVE_PREFIXES += ("cpv_",)`. `mg_` already covers the new MG names.
- `_dict_ddi.observed_values` reads per column (see Schema and dictionaries).
- **`_cli.py`:**
  - Turn the flag→family check into a map from each flag to a set of families
    (`SELECTOR_FLAGS`); make `STATE` optional for the national surveys (`NATIONAL_DATASETS`).
  - `--dataset cpv --edition YYYY` and `--dataset mg --edition YYYY` are added together
    with their registry entries (unit 1e), so the CLI never offers files that are not in
    the registry.
  - The `state` positional stays meaningful for per-state files.
- `data/_cpv_catalog.py` with all eight editions, plus `docs/cpv/STEP_0_probe.md` (the matrix, URLs, quirks).
- `tests/test_cpv.py` skeleton with catalog/URL/`_FILE_RE` round-trip tests.
- A `_REAL`-gated legacy smoke test of `load_census(state=1)` and `load_extended_*`, to guard the frozen path.

### Phase 1 — EIC 2025 (priority)
1. **Build `scripts/build_cpv.py`**, cloned from `build_enigh.py` with the same mode set (`--periods
   --tables --states --dry-run --dictionary --schema-map --variables --report-only --validate
   --update-registry`).
   - Loop over (edition, product ZIP) and extract several members per ZIP.
   - Read CSVs with `pyarrow.csv` (all `string`, `null_values=[""]`) after a streamed
     `_sniff_encoding`; pandas `dtype=str` does not fit the large personas files in memory
     (`STEP_1a.md`). The estimaciones file is cp1252.
   - Output: 96 microdata files + 1 estimaciones file. The national `_00_` ZIP is not mirrored.
2. **Metadata:**
   - `--dictionary` fetches the FD xlsx and classification catalogs into `data/dict/fd/`.
   - Hand-write `variables_cpv_core.yaml`: keys, geography, `FACTOR`, `ESTRATO`, `UPM`, `COBERTURA`,
     `TIPO_REG`, `TAMLOC`, plus `SEXO`/`EDAD` with `Rango`.
   - Then run `--schema-map`, `--variables`, `--report-only`, and `--validate`, which must report 0
     failures and doubles as the label-coverage gate.
3. **Loaders:** `cpv.py`, `cpv_aggregates.load_cpv_estimaciones`, `load_mg`. Add `_resources`
   accessors (`cpv_schema_map`, `variables_cpv(table, gid)`, `variables_cpv_core`) and `__init__`
   exports. The CLI comes with the registry (1e).
4. **MG EIC 2025:** all 15 layers × 32 states (≈2–3 GB) + `ti` via the parameterised
   `build_marco_geo.py --period 2025` (1d: built with `--no-registry`).
5. **Registry and upload on the `wsl` build host.** Registry +97 cpv, +493 mg 2025 and +13 mg
   `ti` 2020 → 2535 entries (`build_cpv.py --update-registry`,
   `build_marco_geo.py --period 2025 --update-registry`, and `--period 2020 --layers ti`).
   Run `upload_hf.py upload` (no `--delete`), `verify`, then a clean-cache `POOCH.fetch`.
6. **Docs:**
   - `docs/cpv/STEP_1.md` and `HANDOFF.md` (runbook modelled on `docs/enigh/HANDOFF.md`).
   - README: a new `### Census & intercensal (multi-year)` section, and generalise the "2020 Census"
     title.
   - Counts in CLAUDE.md and `docs/hf_bucket_readme.md`; generalise the pyproject description.
   - No `build` extra: the FD workbooks are read with the stdlib (1b, 3a), and so are the DBFs
     (3b: `scripts/_dbf.py` instead of the planned `dbfread`).

### Phase 2 — CPV 2020 into the family
- Rebuild the 2020 CA tables (`viviendas`/`personas`/**`migrantes`**), `iter` and `ageb` as
  `cpv_*_2020_NN` (≈+1 GB).
- Dictionaries: RNM DDI if one exists, else the FD xlsx. (2a: DDI 632 exists but the FD xlsx
  is complete and parses like 2025's, so it is used; the ITER/AGEB sentinels `*`/`N/D`/`N/A`
  come from `build_cpv._AGG_SPECIALS` since their dictionaries have no footnotes.)
- First cross-edition harmonization (`ENT`/`MUN`→`CVE_*`; ITER/AGEB `ENTIDAD`/`LOC` → table-scoped).
  (2b: `_RENAME_CORE` + per-table `_RENAME_TABLE`; AGEB `AGEB`/`MZA` → the MG's
  `CVE_AGEB`/`CVE_MZA`; `CVEGEO` = the leading geographic parts, 5/9/16 characters with zero
  parts on total rows. One edition per call; stacking is two calls + `pd.concat`.)
- A core entry may carry `Tablas` (the tables it applies to): the microdata `TAMLOC` (5
  classes) is not the ITER's (14 classes).
- Tests:
  - Σ `FACTOR` and row counts identical raw vs harmonized.
  - Values match the legacy `personas_NN` after casting keys to int. (2b: every cell of
    viviendas/personas/iter/ageb in all 32 states, treating the legacy reader's NA strings —
    pandas defaults + `N/D` — as NA.)

### Phase 3 — EIC 2015 + CPV 2010 (+ aggregates)
- 2015: CSV `TR_VIVIENDA`/`TR_PERSONA`, DDI 214. (3a: the dictionary is the FD `.xls` and
  the `TC_*.xls` catalogs, read by a stdlib BIFF8 reader; DDI 214 recorded only.)
- 2010:
  - Microdata DBF read with `dbfread(raw=True)`, decoded by code page, fixed-width padding stripped only.
    (3b: a stdlib reader, `scripts/_dbf.py`, with the same contract.)
  - DDI 71; `ID_PER`/`ID_MIN` aliases.
- **Aggregates:**
  - `cpv_aggregates.load_cpv_iter(period=None, *, state, nivel=None)` and `load_cpv_ageb(...)`.
    These port `aggregate.py`'s level split, the `LOC>=9998` aggregates, `*`→masked `Int64`, and
    the zero imputation onto string codes and harmonized uppercase names.
  - Add `cpv_iter_crosswalk.yaml` (canonical 2020 mnemonic → per-edition source column). The draft
    is generated by matching dictionary descriptions, then hand-reviewed.
  - Test: 2020 output equals legacy `load_census(state)` after dtype alignment. That equality is the
    gate for later deprecating or delegating `load_census`.
- MG 2010 v5.0, all layers, as `mg_*_2010_NN`.
- MG for 2015: probe (likely MG 2014 v6.2).

### Phase 4 — Censo 2000 + Conteo 2005
- ITER CSV for both; crosswalk entries for renamed mnemonics.
- 2000 muestra: `VHO_F` → `viviendas`, `PER_F`, `MIN_F`; DDI 141; probe the composite keys.
- 2005 sample: `trvmue`/`trhmue`/`trpmue` → `viviendas`/`hogares`/`personas`, so the household level
  enters the key spec. **There is no weight**: the analysis-ready loaders return no `FACTOR` and say
  so. DDI 140.
- No AGEB data exists for either year.
- Municipal MGs 2000/2005 (`mun`, `ent`).

### Phase 5 — 1990 + 1995
- ITER from DBF/TXT, using the crosswalk.
- Samples: 1995 `datgen95`/`migint95` with `FAC_POB`/`FAC_VIV`/`FAC_PROM` mapped onto `FACTOR`
  semantics in core; 1990 `cgpv90p` has no weight.
- Dictionaries come from DBF metadata plus data enumeration (no DDI), with `Nota`s.
- Municipal MG 1995. No MG known for 1990.

### Phase 6 — cross-year integration
- Geographic crosswalk from AGEEML and the Archivo Histórico de Localidades, for municipal splits
  (2,443 in 2000 → 2,478 in 2025) and locality code changes. Expose it as a `cvegeo` mapping table
  and a helper.
- Port the `load_extended_*` derived columns (`EDAD_CAT`, dummies, `EDUC`, …) onto harmonized
  labelled frames so they work for 2025 and later 2015/2010.
- Revisit `crosstabs` constraints per edition.

## Critical files

- **New:**
  - `src/mxcensus/cpv.py`, `src/mxcensus/cpv_aggregates.py`, `src/mxcensus/data/_cpv_catalog.py`
  - `scripts/build_cpv.py`, `scripts/_dict_fd.py`
  - `src/mxcensus/_yaml/{cpv_schema_map,variables_cpv_core,variables_cpv_*_gNN}.yaml`
  - `tests/test_cpv.py`, `docs/cpv/*`
- **Modified:**
  - `scripts/build_data.py` (registry fix), `scripts/build_marco_geo.py` (period param, cache names)
  - `scripts/_build_common.py`, `scripts/_dict_ddi.py` (per-column observed values; `group_entries(entry_fn=)`)
  - `src/mxcensus/_resources.py`, `__init__.py`, `_cli.py`
  - `tests/test_schema_groups.py` (add `cpv` to the family loops)
  - README, CLAUDE.md, `docs/hf_bucket_readme.md`, pyproject
- **Reused as is:** `_schema_groups.py` (all of it), `_build_common.fetch_zip_verified`/`update_registry`,
  `_dict_ddi.dictionary_entry`/`group_entries`/`dump_yaml`, and
  `utils.get_cats_from_excel`/`get_vars_from_indicator_csv` (logic generalised into `_dict_fd.py`;
  the utils themselves are untouched).
  The CSV reader is the exception: `build_cpv.py` has its own streamed sniff and pyarrow reader
  instead of `build_enigh._read_csv_robust`/`_df_to_parquet` (1a).

## Verification

**Offline** (`pytest tests/test_cpv.py tests/test_schema_groups.py`):
- catalog and URLs for all eight editions
- `_FILE_RE` round trip
- dynamic schema-map parametrization with synthetic valid frames
- labels via monkeypatched `read_parquet`, including an unmapped code raising
- harmonize: padding, clash, idempotence, `CVEGEO` check
- key nesting
- `state` semantics
- estimaciones reshape and `NIVEL` on a synthetic 2-geography × 5-estimator frame
- core-YAML contract
- CLI parsing

**Build gates:**
- `build_cpv.py --dry-run --periods 2025 --states 1`, then the full build.
- `--validate` reports 0 failures.
- `upload_hf.py verify`, plus a clean-cache `POOCH.fetch('cpv_personas_2025_01.parquet')`.

**EIC 2025 data checks** (`_REAL`-gated, sentinel `cpv_personas_2025_01.parquet`):
- **Population totals:** personas Σ `FACTOR` by nation, state and each of the 2,478 municipalities
  equals estimaciones `POBTOT` `valor`. Record whether the match is exact (calibrated) or only
  inside LI–LS.
- **Localities:** each ≥50k locality equals Σ over `LOC50K ≠ 0000`. Σ over `LOC50K = 0000` equals
  the state's 997 row.
- **Dwellings and migrants:** viviendas Σ `FACTOR` equals occupied private dwellings, and migrantes
  equals the emigrant total. Both are pinned from Comunicado 54/26 and the tabulados.
- **Keys:** IDs are unique per level, `ID_PERSONA[:12] == ID_VIV`, and every person's dwelling
  exists. Check (don't assume) that `FACTOR` is constant within a dwelling.
- **Geography:** `CVEGEO == CVE_ENT+CVE_MUN`, and each state file holds only its own `CVE_ENT`.
- **Coverage:** `COBERTURA` 1 / 2 / 3 = 750 / 1,721 / 7 municipalities, matching the
  estimaciones name marks `*` / none / `**` (1c found 750 censados, not the 753 first assumed).
- **Estimates:** LI ≤ valor ≤ LS, cv ≈ 100·ee/valor (within the 2-decimal rounding), and 2,776 × 5 rows.
- **Legacy path:** `load_census(state=1)` and `load_extended_*` are unchanged.

## Risks

- **FD xlsx layout** is unprobed; data enumeration is the fallback.
- **DBF code pages** (cp850 vs latin-1).
- **Memory** when loading many states or running `--variables`.
- **2020 CA re-download size.**
- **Code meanings that drift across eras**, which is why the core stays small.
- **`upload_hf --delete`** against a partial local directory: never use it.
- **Full builds must run on the `wsl` host**, which holds the complete mirror.
