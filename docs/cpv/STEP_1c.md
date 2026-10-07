# CPV Unit 1c — loaders, tests and EIC 2025 data checks

Done **2026-10-07**. Gate: `pytest -q` green (Mac: 711 passed, 1 skipped; `wsl`: the
CPV tests over all 32 states), and the Σ `FACTOR` checks of `PLAN.md` §Verification
recorded below. Every check is an **exact equality**: the expansion factors
are calibrated to the published estimates.

## What was built

### `src/mxcensus/cpv.py` — microdata loaders (ENIGH pattern)

- **`load_cpv(survey_path=None, *, table, period=None, state=None, harmonize=False,
  labels=False)`** returns the raw table: faithful `str` columns, validated against its
  group schema (violations warn).
  - `period` defaults to the latest edition publishing `table`; `get_edition` accepts a
    str or int.
  - An unknown table or edition, or a table the edition does not publish, raises before
    anything is fetched.
- **`state`** is `int | iterable of int | None`:
  - Per-state tables: `None` raises (`mirrored per state; pass state=`). A sequence loads
    the states one by one (duplicates dropped, order kept) and concatenates them.
  - National tables, and any table read via `survey_path`: a row filter on `CVE_ENT`
    (`ENT` is accepted too).
  - Accepts numpy ints, arrays, Series and ranges. Rejects `bool`, `float`, `str`, an empty
    sequence and codes outside 1–32.
  - States from different schema groups raise unless `harmonize=True`. Then each state is
    harmonized before the concat, and labelling uses the union of the groups' dictionaries.
    A column documented differently across groups stays raw, with a warning
    (`_labels_for`).
- **`load_cpv_viviendas` / `load_cpv_personas` / `load_cpv_migrantes(period=None, *,
  state, harmonize=False, labels=True)`** are analysis-ready: numeric `FACTOR`, labelled,
  strictly validated (`_finish_labelled` → `validate_raise`), and indexed by the level key.
  `state` is a required keyword. With `labels=False` they return raw strings plus a numeric
  `FACTOR` and the index.
- **`load_cpv_survey(period=None, *, state, …)`** → `(viviendas, personas, migrantes |
  None)`. `None` is for an edition without a migrant table (2015).
- **Keys** (`_KEY_SPEC`):
  - `_DWELLING_KEY_SPEC = [("ID_VIV",)]`
  - `_PERSON_KEY_SPEC = + [("ID_PERSONA", "ID_PER")]`
  - `_MIGRANT_KEY_SPEC = + [("ID_MII", "ID_MIN")]`

  Persons and migrants are siblings under the dwelling.
- **`variables_cpv_labels(table, gid)`**: the per-group dictionary overlaid by the core. It
  is keyed by the raw name and by the harmonized one (upper case, then `_RENAME_CORE`).
- **`_harmonize`** (generic; 2a only fills the rename map):
  1. upper-case all names;
  2. apply `_RENAME_CORE`; a frame holding a legacy column and its target raises;
  3. zero-pad `CVE_ENT`(2), `CVE_MUN`(3), `LOC50K`(4) and `CVE_LOC`(4);
  4. derive `CVEGEO` from the parts present (`CVE_ENT+CVE_MUN`, `+CVE_LOC` in
     estimaciones), inserted first; when it already exists, check it instead (a mismatch
     warns);
  5. make `FACTOR` numeric.

  A missing required core column (`CVE_ENT` plus the table's key) warns. Column order is
  kept, so for 2025 the result is the identity up to the `FACTOR` dtype, and it is
  idempotent.
- **`_latest_schema(table)`** is built from the core: categoricals `isin`, numerics and
  the weight numeric, and width regexes on the padded geography. Only `CVE_ENT` and the
  table's key are required.

### `src/mxcensus/cpv_aggregates.py` — `load_cpv_estimaciones`

`load_cpv_estimaciones(period=None, *, estimador="valor", nivel=None, state=None,
survey_path=None)`:
- One row per geography, indexed `(CVE_ENT, CVE_MUN, CVE_LOC)` (sorted).
- Columns: `NIVEL`, `CVEGEO`, `NOM_ENT`/`NOM_MUN`/`NOM_LOC`, then the 341 indicators.
- `NIVEL` is an ordered categorical `nacional < estatal < municipal < resto_estatal <
  localidad`, computed from the string codes. `resto_estatal` is `997`/`9997`.
- `estimador`: one of `valor|ee|li|ls|cv`. A list or `None` adds `ESTIMADOR` (an ordered
  categorical) as the last index level.
- `nivel` and `state` filter rows.
- Cells are labelled: `NA`/`MI` → missing, and percentages (`Decimales`) are `Float64`.
  Counts are `Int64` when the selected rows are integral (valor), else `Float64` (ee, li,
  ls).
- Strict validation, and the index must be unique.

### Shared: `_schema_groups.label_frame` (all families)

Profiling `load_cpv_personas(state=15)` (2.3 M × 92) showed `label_frame` was the
bottleneck. It mapped every cell to a Python label string in an object column, which the
strict schema then coerced to `Categorical`. Two changes fix that:
- **Categoricals are built directly**, as `Categorical.from_codes` of the same dtype
  `build_labelled_schema` declares. The new helpers are `_categorical_dtype` and
  `_to_categorical`.
- **Each column is mapped through its distinct values.** `pd.factorize` gives the
  uniques; strip, alias, label or parse only those; then expand them back through the codes.
  A shallow copy replaces the deep one.

**Equivalence**: on 22 real frames the old and new implementations give identical
validated labelled frames (`assert_frame_equal(check_exact=True)`). The frames are ENIGH
`concentradohogar`/`poblacion` 2008/2012/2024 (raw and harmonized), ENOE `sdem`
2005t1/2020t3/2026t1 (raw and harmonized), CPV state 09 ×3 and estimaciones.

| frame | labelling, old → new |
|---|---|
| ENIGH `poblacion` 2024 | 9.8 s → 0.7 s |
| ENOE `sdem` 2026t1 | 7.6 s → 0.7 s |
| CPV personas 09 | 6.8 s → 0.8 s |
| CPV personas 15, `label_frame` only | 16.7 s → 1.5 s |

One test changed: `test_label_frame_maps_codes_numerics_and_sentinels`. A missing label is
now `NaN` in a `Categorical`, where it used to be `None` in an object column. The test now
also asserts the dtype.

### Exports, tests

- **`__init__`**: `load_cpv`, `load_cpv_viviendas`/`personas`/`migrantes`,
  `load_cpv_survey`, `load_cpv_estimaciones`, `variables_cpv_labels`, `variables_cpv`,
  `variables_cpv_core`, `cpv_schema_map`.
- **`tests/test_cpv.py` §unit 1c, offline** (synthetic mirror: `POOCH.fetch` echoes the
  name, `read_parquet` returns a valid keyed frame):
  - key nesting and skip set;
  - labels over every group, and an unmapped code (raw warns, labelled raises);
  - harmonize: identity, idempotence, padding, `CVEGEO` derive/check, uppercase, rename,
    clash, missing core;
  - `_latest_schema` rejections;
  - `state`/period/table semantics;
  - mixed schema groups;
  - the level loaders and the survey;
  - the estimaciones reshape over 5 geographies × 5 estimators (every `NIVEL`, `NA`/`MI`,
    dtypes, estimator levels and order, filters, errors);
  - exports.
- **`tests/test_cpv.py` §unit 1c, `_REAL`** (sentinel `cpv_personas_2025_01.parquet`;
  `local_mirror` redirects `POOCH.fetch`):
  - the raw/harmonized loads and the labelled survey for state 01;
  - state sequences;
  - `test_eic2025_data_checks_by_state`, parametrized over every state on disk;
  - `test_eic2025_estimates_real`;
  - `test_eic2025_national_real`, which runs only with all 32 states, i.e. on `wsl`.
- **`tests/test_schema_groups.py`**: `cpv` was added to the `_level_key`/`_index_level`
  wrapper loop.

Full suite (Mac): **711 passed, 1 skipped** (the 32-state national test) in 6 min 54 s, with
the 4 pre-existing DENUE/ENOE warnings. 1b ran 685 tests in 13 min 49 s; the time halved
because of the `label_frame` change.

## Decisions

- **Person-number pointers are left raw.** `NUMPER`, `IDENT_MADRE`/`IDENT_PADRE`/
  `IDENT_PAREJA`, `DUE1_NUM`/`DUE2_NUM`, `MPER` and `MPERLS` go in `skip=` with the keys
  and geography (`_SKIP`).
  - Person numbers `01`–`54` are their own labels in the FD, so labelling would add nothing
    but a wide categorical.
  - As raw strings they join directly: `(ID_VIV, IDENT_MADRE)` → `(ID_VIV, NUMPER)`.
  - The codes from 96 up (another dwelling, deceased, no partner, not a resident, don't
    know, not specified) stay documented in `variables_cpv_labels`. A test pins that every
    pointer is identity-coded up to 54.
- **Year fields stay as generated.** `FECHA_NAC_A` is numeric (`Int64`, `9999` → NA).
  `MFECEMIA`/`MFECRETA` (2020–2025) stay 6-label categoricals plus `No especificado`. A
  core entry would need cross-edition verification and a `--variables` rerun on `wsl`, for
  a cosmetic gain. Revisit when 2020 joins (2a).
- **Migrant → person link**: a documented join, not an index level. Returned emigrants who
  live in the dwelling (`MCONRESACT` = Sí) carry `MPERLS` = their `NUMPER`. The join is in
  the docstrings of `load_cpv_migrantes`/`load_cpv_survey` and pinned on state 01: 652 of
  652 link.
- **CLI `--dataset cpv --edition` moves to 1e** (user, this session). The registry has no
  `cpv_` entries until 1e, and the CLI must never offer unregistered files.
- **Wsl run**: commit and push the code, `git pull --ff-only` on `wsl`, and run the
  `_REAL` tests there (user, this session).

## EIC 2025 data checks

### Local states (Mac: 01, 09, 15)

All of the following pass in `test_eic2025_data_checks_by_state`:
- **Geography**: each file holds only its own `CVE_ENT`, and `ID_VIV[:2]` is the state.
  `CVEGEO == CVE_ENT+CVE_MUN` in every row.
- **Keys**:
  - `ID_VIV`/`ID_PERSONA`/`ID_MII` are unique and `ID_PERSONA[:12] == ID_VIV`;
  - every person's and migrant's dwelling exists, and every dwelling has a person;
  - `FACTOR` is constant within the dwelling and equals the dwelling's.
- **Emigrants**: the dwellings with `MCONMIG = 1` are exactly those with `MNUMPERS`, and
  each holds exactly `MNUMPERS` migrant records.
- **Σ `FACTOR` = estimaciones `Valor`, exactly**:
  - persons = `POBTOT` and dwellings = `VIVPARHAB` for the state and for **every
    municipality**;
  - persons = `POBTOT` for each ≥50k locality (`LOC50K ≠ 0000`);
  - persons with `LOC50K = 0000` = the state's `997/9997` row.
- **Coverage**: `COBERTURA` is constant within each municipality.

| state | municipalities | ≥50k localities | Σ persons | `LOC50K=0000` | `COBERTURA` | Σ emigrants | returned (`MPAIRES=3`) |
|---|---|---|---|---|---|---|---|
| 01 | 11 | 2 | 1,534,416 | 540,696 | 2 ×11 | 26,542 | 5,753 |
| 09 | 16 | 15 | 9,165,819 | 390,541 | 2 ×16 | 47,196 | 9,147 |
| 15 | 125 | 29 | 17,561,797 | 7,929,013 | 2 ×123, 1 ×2 | 82,996 | 11,164 |

### Estimates (whole file)

`test_eic2025_estimates_real`:
- 13,880 rows = 2,776 geographies × 5 estimators, and `NIVEL` counts 1 / 32 / 2,478 / 32 /
  233.
- `NA`/`MI` fall in the same cells for all five estimators.
- **LI ≤ valor ≤ LS** in all 943,832 non-missing cells.
- **cv = 100·ee/valor** holds in all 926,036 cells with valor > 0.005, within the rounding
  of the three published 2-decimal figures (interval bounds ±0.005 on each). A naive
  tolerance fails for small percentages, e.g. valor 0.05 and ee 0.06 give cv 100.19 against
  120 from the rounded inputs.
- LI/LS are **not** valor ± z·ee, so only their ordering is checked:
  - the percentage limits are asymmetric (valor 0.05 has LI 0.01 and LS 0.29);
  - LI is clipped at 0 on counts (`PHOG_AFRO` of 23-005-0001: valor 111,281, ee 84,284.83,
    LI 0, LS 252,128.8).
- The nation's `POBTOT` is 130,393,389 and `VIVPARHAB` is 39,699,242.

### National (`wsl`, all 32 states)

Code commit `89164b1`, pulled on `wsl` (fast-forward from `a69eb25`), then
`pytest tests/test_cpv.py tests/test_schema_groups.py`: **178 passed, 1 failed** in 7 min
30 s, peak RSS 2.9 GB. The run covers `test_eic2025_data_checks_by_state` for **all 32
states**, so every check of the local-states section holds for every municipality, ≥50k
locality and state remainder in the country. `test_eic2025_national_real` gives:

| check | microdata | reference |
|---|---|---|
| Σ `FACTOR` persons | 130,393,389 | estimaciones `POBTOT`; Comunicado 54/26 |
| Σ `FACTOR` dwellings | 39,699,242 | estimaciones `VIVPARHAB`; Comunicado 54/26 |
| Σ `FACTOR` emigrants 2020–2025 | 1,259,978 | Comunicado 54/26 |
| returned (`MPAIRES = 3`, "vive en México") | 150,752 | Comunicado 54/26 |
| municipalities / ≥50k localities | 2,478 / 233 | estimaciones `NIVEL` |
| `COBERTURA` 1 / 2 / 3 | 750 / 1,721 / 7 | estimaciones `*` / unmarked / `**` names |

All equalities are exact. The one failure was the plan's expected **753** censado
municipalities: the data have **750**. Two independent INEGI artifacts agree on 750:
- the microdata `COBERTURA = 1`, constant within each municipality, the same in personas
  and viviendas;
- the estimaciones footnote marks, 750 names ending in `*` ("Municipio censado") and 7 in
  `**` ("Municipio con muestra insuficiente").

Where 753 came from could not be traced:
- The methodology note (`889463931133.pdf`) and SNIEG's design presentation are
  AES-encrypted PDFs, and reading them needs `cryptography`, which was not installed.
- Plausibly 753 is the design count, and 3 small planned-census municipalities ended as
  "muestra insuficiente". The 7 `**` ones include Coyame del Sotol, Moris and Huajicori.
  This is unverified.
- Sonora's published plan, 37 municipalities censados, matches the data's 37.

The test now pins 750 / 1,721 / 7. The per-state test cross-checks every municipality's
`COBERTURA` against its estimaciones name mark: green on the Mac's three states, and to be
re-run on `wsl` with the docs commit.

Published references (INEGI, Comunicado de prensa 54/26, 22 Sep 2026):
- 130,393,389 residents of private dwellings and 39,699,242 inhabited private dwellings;
- "1 259 978 personas que vivían en México cambiaron su residencia a otro país" between 2020
  and 2025, "de ellas, 150 752 regresaron y residían en México" (return migrants).

## Memory and time (Mac, CPython 3.14.8, pandas 3.0.3)

| call | wall | peak RSS | result |
|---|---|---|---|
| `load_cpv(table="personas", state=15)` (raw, validated) | 5.7 s | 3.8 GB | 1.9 GB |
| `load_cpv_personas(state=15)` | 10.3 s | 6.1 GB | 0.93 GB |
| `load_cpv_survey(state=15)` | 13.1 s | 6.4 GB | 1.1 GB |
| `load_cpv_survey(state=1)` | 4.4 s | 1.8 GB | — |

The labelled result is half the size of the raw `str` frame: one byte per categorical cell.
The peak comes from four steps:
1. reading the raw frame: 1.9 GB of `str` columns, 3.0 GB RSS during the Arrow → pandas
   conversion;
2. raw validation: +0.8 GB, 5.7 s;
3. the index sort: +1.0 GB, because the files are not ordered by `(ID_VIV, ID_PERSONA)`;
4. the strict validation: +0.7 GB.

These four steps are the same as in ENOE/ENIGH, and were left alone. Before the
`label_frame` change, state 09 personas peaked at 2.8 GB; extrapolating linearly, state 15 would have needed
about 15 GB.

## Deviations from the plan

- The CLI moves to 1e (above). Phase 0's "added with their loaders (1c/1d)" is updated in
  `PLAN.md`. 1d should decide the same for `--dataset mg` (`HANDOFF.md`).
- `load_cpv_estimaciones(period=None, …)` defaults to the latest edition with estimates,
  like every other loader, instead of a literal `"2025"`. It also gained a keyword-only
  `survey_path`, for offline use and tests.
- The ENIGH `_load_*_raw` pattern returns one gid. CPV's `_load_cpv_raw` returns the list
  of groups, for the multi-state case.
- `_schema_groups.label_frame` was optimized (above). This is shared code, verified
  identical on ENOE/ENIGH/CPV.
- §Verification's "`COBERTURA = 1` for 753 municipalities" was wrong: the data say 750, and
  `PLAN.md` is updated.
- Beyond the plan: the emigrant total and the returned migrants are pinned to Comunicado
  54/26; `MNUMPERS` is checked against the migrant records; `COBERTURA` is checked against
  the estimaciones name marks; and cv is checked against ee/valor with rounding bounds.

## Gotchas

- The registry still has no `cpv_` entries, so `POOCH.fetch("cpv_…")` fails outside the
  tests' `local_mirror` until 1e.
- `test_eic2025_national_real` only runs where all 32 states are on disk (`wsl`). It reads
  column-pruned files, so it needs little memory.
- The `fake_mirror` fixture monkeypatches `pd.read_parquet` globally for a test. Tests that
  need real files use `local_mirror`, or read with `survey_path`/`_read_mirror` outside it.
