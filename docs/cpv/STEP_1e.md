# CPV Unit 1e — registry, upload, CLI and docs (the EIC 2025 release)

Done **2026-10-07**. Gate met: on the Mac, with an empty `$MXCENSUS_CACHE_DIR`,
`POOCH.fetch` downloaded `cpv_personas_2025_01`, `cpv_estimaciones_2025`, `mg_mun_2025_01` and
`mg_ti_02` anonymously from the HF bucket, each verified against the committed registry. The
unpatched loaders then ran end to end from that cache: `load_cpv_survey(state=1)`, and
`load_mg("mun", state=1, period=2025)` joined to `load_cpv_estimaciones(nivel="municipal",
state=1)` on `CVEGEO`, with Σ personas `FACTOR` = Σ `POBTOT` = 1,534,416.

## User decisions (this session)

- `mxcensus fetch N --dataset cpv` fetches the state's microdata tables **plus** the national
  `estimaciones` file (9.8 MB). The default edition is the latest (2025).
- `--dataset mg` defaults to **2020**, the same as `load_mg`, so pre-fetching serves the
  loader's defaults. `--edition 2025` fetches the EIC frame.
- Version **0.5.0**.
- The registry was committed on `wsl`, then pushed, uploaded and verified, after the checks
  below.

## Registry (`wsl`, commit `b07a8cb`)

The upserts used the `--update-registry` modes:

| command | entries |
|---|---|
| `build_cpv.py --update-registry` | +97 (`cpv_{viviendas,personas,migrantes}_2025_NN` × 32, `cpv_estimaciones_2025`) |
| `build_marco_geo.py --period 2025 --update-registry` | +493 (`mg_*_2025_NN`: 15 layers × 32 + `ti` × 13) |
| `build_marco_geo.py --period 2020 --layers ti --update-registry` | +13 (`mg_ti_NN`) |

- **1932 → 2535 entries.** The diff has 603 additions and 0 removed lines.
- Reproducibility: 38 of these files had also been built on the Mac (cpv states 01, 09 and
  15 + estimaciones, MG 2025 state 01, MG 2020 `ti`). All 38 hash **identically** on both
  hosts.

## Upload (`wsl`, `scripts/upload_hf.py`)

- The dry run showed **603 uploads (2.88 GB), 0 deletes, 1932 skips (identical)**. The
  real `upload` (no `--delete`) took about a minute; a second dry run then reported
  0 uploads and 2535 skips.
- `upload_hf.py verify` (HEAD of every registry URL against the local size): **2534 ok, 0 size-mismatch, 1 "missing"** of 2535 (~15 min).
  The one miss was `denue_202405_19.parquet`, a pre-existing DENUE file the sync dry run had
  just listed as identical. Re-checked by hand, from the Mac (curl) and from `wsl` (the
  script's own `urllib` HEAD), it answers 200 with the local size (13,970,200 B). It was a
  transient HEAD failure: `_content_length` counts any exception, timeouts included, as
  missing. **All 2535 files are on the bucket with the right size.**
- The bucket README (`docs/hf_bucket_readme.md`) was rewritten in this unit and re-uploaded
  after the docs commit (`upload_hf.py upload`, no parquet changes).

## CLI (`src/mxcensus/_cli.py`)

- `SELECTOR_FLAGS["edition"] = {"enigh", "cpv", "mg"}`, and `--dataset` gains `cpv` and `mg`.
  `STATE` stays required for both (neither is in `NATIONAL_DATASETS`).
- `--dataset cpv [--edition YYYY]`: `cpv_filename(t, period, state)` for every table of the
  edition, with the national tables (EIC 2025: `estimaciones`) fetched without a state.
- `--dataset mg [--edition YYYY]`: every `MG_LAYERS` file of the state.
- Both offer **only files in `POOCH.registry`**. `ti` is therefore fetched only for island
  states, and an edition with nothing registered (`--edition 2015` for cpv, `2010` for mg)
  is a parser error ("not in the mirror yet") rather than a 404. An unknown edition is a
  parser error listing the known ones.
- `tests/test_cli.py`: cpv state + national, mg 2020 (15 layers) and 2025 for island state
  02 (16), and six new argument errors.

## Docs and metadata

- **README:**
  - generalised title and intro;
  - Quick start with `load_cpv_survey`/`load_cpv_estimaciones`/`load_mg`, and the CLI
    examples;
  - a Datasets row for the `cpv` family;
  - a new "Censuses and intercensal surveys (multi-year)" section;
  - the Geometries section rewritten around `load_mg` (both frames, `ti`, the CRS note);
  - the CPV dictionary accessors;
  - EIC 2025 / MG 2025 sources and citations (`https://www.inegi.org.mx/programas/eic/2025/`,
    checked: the program page, not a soft-404);
  - the transformation notice (CPV faithful raw, MG CRS handling).

  Every README snippet was run.
- **CLAUDE.md:**
  - commands;
  - the overview and Public API;
  - new module rows (`cpv.py`, `cpv_aggregates.py`, `mg.py`, `build_cpv.py`, `_dict_fd.py`),
    updated rows (`_cli.py`, `_catalog.py`, `_cpv_catalog.py`, `_resources.py`,
    `build_marco_geo.py`);
  - the CPV YAML trio;
  - file naming (`cpv_*`, `mg_{sfx}_{period}_{NN}`, `ti`);
  - registry totals 2535;
  - the MG rebuild commands;
  - the CPV family status.
- **`docs/hf_bucket_readme.md`:**
  - contents table, with the CPV row and MG 2020 / 2025 rows of 493 each;
  - total 2535;
  - citation;
  - privacy, now covering EIC 2025 and the Cuestionario Ampliado microdata, which the old
    text wrongly called aggregate;
  - transformations (CPV faithful raw, MG CRS);
  - usage.
- **Version 0.5.0** (`pyproject.toml`, `uv.lock` by hand as in the 0.4.0 bump, no
  `uv lock`). The description is generalised, and so is the package docstring.
  `mxcensus.__version__` reads the installed metadata, so a dev venv keeps reporting
  0.4.0 until reinstalled (`uv pip install -e .`).

## Decisions recorded

- **`local_mirror` fixtures kept** in `test_cpv.py`/`test_mg.py`. The `_REAL` tests read
  `data/parquet` directly, so they never touch the network or the user's cache. Their
  docstrings no longer say the files are unregistered.

## Test suite

Mac: **740 passed, 2 skipped**, 4 warnings (the pre-existing DENUE/ENOE value-level
ones). The skips are the MG 2025 national-totals check, which needs all 32 states, and the
existing one from 1c. On `wsl`, `tests/test_mg.py` passes 21 of 21 over the full mirror
(`STEP_1d.md`).

## Left for later

- **Release mechanics**: `cpv-integration` is not merged into `main`, and there is no
  `v0.5.0` tag. Users installing from `main` keep the 1932-entry registry; the bucket's
  extra files are harmless to them. Merge and tag when the user decides (2a and 2b can
  continue on the branch either way).
- `upload_release.py` (superseded) still parses MG names as `mg_<suffix>_<NN>`
  (`STEP_1d.md`).
