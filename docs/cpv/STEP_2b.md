# CPV Unit 2b — 2020 ↔ 2025 harmonization, legacy equality, the CPV 2020 release

Done **2026-10-07**. Gate met:
- Rows and Σ `FACTOR` are identical raw vs harmonized for every microdata table of both
  editions in every state (`test_raw_vs_harmonized_totals_real`, 32 × 2 on `wsl`).
- The 2020 files equal the legacy ones cell by cell in all 32 states
  (`test_cpv_2020_equals_legacy`, 128 cases on `wsl`).
- The 160 files are registered (2535 → **2695**, additions only), uploaded and verified.

Unit 2a was committed at the start of this session (`e997834`, local, not pushed); `wsl` was
fast-forwarded to it from a `git bundle`, so its tree was clean before 2b.

## User decisions (this session)

- Commit 2a on its own before starting 2b (no push yet).
- Version **0.6.0**.
- The 2020 dictionary stays the FD xlsx; DDI 632 is recorded only (`ddi_id`).
- Release: push 2a + 2b, merge `cpv-integration` into `main` (fast-forward) and tag
  **`v0.6.0`** (EIC 2025 + CPV 2020). Work continues on the branch.

## Harmonization (`src/mxcensus/cpv.py`)

**Renames.** `_renames(table)` = the global `_RENAME_CORE` plus a per-table
`_RENAME_TABLE` (ENIGH's idiom):

| scope | raw (2020) | harmonized |
|---|---|---|
| every table | `ENT`, `MUN` | `CVE_ENT`, `CVE_MUN` |
| `iter`, `ageb` | `ENTIDAD`, `LOC` | `CVE_ENT`, `CVE_LOC` |
| `ageb` | `AGEB`, `MZA` | `CVE_AGEB`, `CVE_MZA` |

`ENTIDAD`/`LOC` are table-scoped because a later microdata table may use those names for
something else (the plan's concern). `AGEB`/`MZA` take the Marco Geoestadístico's names, so a
harmonized frame joins the MG directly. The 2010 spellings (`ID_PER`, `ID_MIN`, `TAM_LOC`)
wait for 3b. A frame with two sources of one target (`ENT` and `ENTIDAD`) now raises, as a
source + target clash already did.

**CVEGEO** is the concatenation of the *leading* geographic parts a frame carries
(`_GEO_PARTS` = `CVE_ENT, CVE_MUN, CVE_LOC, CVE_AGEB, CVE_MZA`, taken while present):

| table | parts | length |
|---|---|---|
| microdata (2020 derived, 2025 checked) | ENT + MUN | 5 |
| estimaciones (checked), ITER (derived) | + LOC | 9 |
| AGEB (derived) | + AGEB + MZA | 16 |

Total rows keep their zero parts (`00/000/0000/0000/000`), as the estimaciones already do.
So `CVEGEO` is **unique per row** in both 2020 aggregates (checked on state 01). A block
row's `CVEGEO` is the MG manzana key, and an AGEB-level row's MG key is its first 13
characters. `_GEO_REGEX` accepts 5/9/13/16 characters; `CVE_AGEB` gets the AGEB shape
`^\d{3}[0-9A-P]$` and `CVE_MZA` 3 digits.

**Decision on the aggregates** (the handoff left it open): harmonize their geography **now**
rather than in 3c. The renames cost a two-line map, and 3c's `load_cpv_iter`/`load_cpv_ageb`
are planned "on harmonized uppercase names", so the level split can rely on `CVE_*` and
`CVEGEO`. A harmonized ITER frame has the estimaciones' layout (`CVEGEO, CVE_ENT, NOM_ENT,
CVE_MUN, NOM_MUN, CVE_LOC, NOM_LOC`). `_required("iter")` no longer warns. The level split,
`*` imputation and `TAMLOC` labels stay in 3c.

**Mixing editions** stays out of a single call, as in ENOE and ENIGH. One call loads one
edition; to stack editions, load each with `harmonize=True` and concatenate with the
period as an index level (`pd.concat(frames, names=["PERIOD"])`; documented in the module
docstring and the README, tested). Reasons:
- `ID_VIV` can repeat across editions, so a multi-edition index would need a period level;
- the non-core items differ in name and code between editions.

A `period=[2020, 2025]` option can come later if wanted.

**`_labels_for`** (several schema groups in one call) now compares only the label-relevant
keys (`_LABEL_KEYS`: `Tipo` normalized, `Categorías`, `Especiales`, `Rango`, `Ordenada`,
`Alias`, `Decimales`). A wording-only difference no longer drops a column's labels, and the
newest group's entry is kept. Between 2020 and 2025 this cuts the conflicting shared
columns from 48/52/12 (viviendas/personas/migrantes) to the 7/22/5 that really label
differently. No CPV call stacks two groups yet: each edition has one fingerprint per table.

**Other code changes:**
- `_GEO_CODES` (kept raw under `labels=True`) gains `CVE_AGEB`/`CVE_MZA`;
- `_DIGIT_CODES` gains `CVE_MZA`, and `_CODE_REGEX` gains `CVE_AGEB`, for a future edition
  that ships them raw;
- `variables_cpv_labels` keys each entry under its table-scoped harmonized name too.

## Core (`variables_cpv_core.yaml`)

- `CVEGEO`, `CVE_ENT`, `CVE_MUN` and `CVE_LOC` describe the 2020 spellings and the
  ITER/AGEB codes (`LOC` 0000 = totals, 9998/9999 = one/two-dwelling localities).
  `CVEGEO` `Longitud: 5 / 9 / 16`.
- New entries `CVE_AGEB` and `CVE_MZA` (string). No raw column carries those names, so they
  only document the harmonized frames.
- The header explains that geography entries use the harmonized names.

`--variables` on `wsl` (2 min 31 s) changed only the core copies' descriptions in
`variables_cpv_{viviendas,personas,migrantes}_g02` and `variables_cpv_estimaciones_g01`.
`--validate --jobs 16`: **0/257** failures.

## Legacy equality

`_legacy_mismatches(legacy, raw)` (in `tests/test_cpv.py`) compares each legacy column with
the faithful-raw rebuild:
- numeric legacy columns against the raw strings parsed with `pd.to_numeric`;
- the others as strings.

The only systematic difference is **`N/A`**. The legacy builder read the CSVs with pandas'
default NA strings, so the `REL_H_M`/`PROM_HNV` cells INEGI writes as `N/A` (zero
denominator) are NaN in `iter_NN`/`resargebub_NN`, while the mirror keeps `N/A`. The
comparator treats pandas' default NA strings as NA; `*` and `N/D` are strings on both sides.
With that, every cell of `cpv_{viviendas,personas,iter,ageb}_2020_NN` equals its legacy
twin, with the same columns in the same order. `migrantes` has no legacy twin.

The Mac covers state 01 only, which has **no `N/D` cell**. The first 32-state run on `wsl`
therefore failed on `iter`/`ageb` of states with undisclosed counts (`iter_02`: 4
localities × 271 columns). The legacy builder (`scripts/build_data.py`) reads with
`na_values=["N/D"]` on top of pandas' defaults. With `N/D` added to the comparator's
`_LEGACY_NA`, all **128 (table, state) pairs pass** on `wsl`, and so do the 64
raw-vs-harmonized cases (194 tests, 16 min 22 s).

## Registry and upload (`wsl`)

- `build_cpv.py --update-registry`: 257 entries upserted, **2535 → 2695**. The diff is
  160 added lines and 0 removed (32 × `viviendas/personas/migrantes/iter/ageb` 2020).
- The five state-01 files built on the Mac hash identically to `wsl`'s.
- `upload_hf.py upload --dry-run`: **160 uploads (649,383,556 B), 0 deletes, 2535 skips**.

- `upload_hf.py upload` (no `--delete`) took 27 s, including the bucket README. A second
  dry run reported **0 uploads, 2695 skips**.
- `upload_hf.py verify`: **2695 ok, 0 missing, 0 size-mismatch** (16 min).
- **Clean-cache fetch (Mac, empty `$MXCENSUS_CACHE_DIR`)**:
  - `POOCH.fetch` downloaded `cpv_personas_2020_01` and `cpv_iter_2020_01` anonymously and
    checked them against the new registry.
  - The unpatched `load_cpv_survey(2020, state=1, harmonize=True)` then pulled the other
    tables and ran with warnings set to raise. Results: 24,349 / 95,983 / 1,563 rows,
    Σ `FACTOR` 387,762 / 1,421,198 / 17,762.
  - The harmonized ITER total row `010000000` has `POBTOT` 1,425,607.
  - `mxcensus fetch 1 --dataset cpv --edition 2020` found all five files cached.

## CLI and docs

- `mxcensus fetch N --dataset cpv --edition 2020` needed no code change. It offers the five
  registered 2020 tables (ITER/AGEB included), and `tests/test_cli.py` pins the list.
- README:
  - the `cpv` section covers CPV 2020, harmonization and the two-call stacking;
  - the datasets row, Quick start and CLI examples cover CPV 2020, plus a `variables_cpv`
    `g01` example;
  - the transformations notice mentions the 2020 markers and `harmonize=True`.
- CLAUDE.md:
  - the `cpv.py` row (renames, CVEGEO lengths, one edition per call, `_labels_for`);
  - file naming (257 CPV files) and registry totals (2695);
  - the family status and the CLI example.
- `docs/hf_bucket_readme.md`: CPV row (257), total 2695, CPV 2020 microdata in the privacy
  note, a 2020 usage line.
- Version 0.6.0 (`pyproject.toml`, `uv.lock`).

## Tests

`tests/test_cpv.py` adds:
- the real rename map and the duplicate-target clash
  (`test_harmonize_rename_and_clash`);
- `test_harmonize_aggregates_table_scoped`: ITER/AGEB renames, 9/16-character `CVEGEO`,
  idempotence, `_latest_schema`, an invalid `CVE_AGEB`, and `ENTIDAD`/`LOC` kept verbatim in
  a microdata table;
- `test_mixed_schema_groups`: a wording-only difference is not a conflict, and the newest
  entry wins;
- `test_raw_vs_harmonized_totals_real`: every local (period, state) with all three
  microdata tables, compared directly through `_harmonize`;
- `test_harmonized_editions_stack_real`: 2020 + 2025 through the loaders, the two-call
  stack, and the harmonized ITER/AGEB (`CVEGEO` unique, state `POBTOT` 1,425,607);
- `test_legacy_mismatches_helper` and `test_cpv_2020_equals_legacy`: every local
  (table, state) pair with both files.

`tests/test_cli.py`: `--edition 2020`.

Results:
- **`wsl`** (`test_cpv`, `test_schema_groups`, `test_cli`, `test_census_legacy`): **432
  passed** in 25 min. That covers all 32 states of both editions: the legacy equality,
  raw vs harmonized, and the 2025 data checks.
- **Mac**: full suite **792 passed, 2 skipped** in 7 min. The 4 warnings are the pre-existing DENUE/ENOE ones.

## Deviations from the plan

- The plan left the aggregates' harmonization open, possibly for 3c. It was done now, and
  only the geography (above).
- New core entries `CVE_AGEB`/`CVE_MZA` (harmonized names only).
