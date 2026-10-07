# CPV Unit 1b — dictionaries, schema map, validation (EIC 2025)

Done **2026-10-07**. Gate: `build_cpv.py --validate` reports **0 failures over all 97**
`cpv_*_2025*` files on `wsl` (`VALIDATION_REPORT.md`). Commits: `5316aad` (code, core YAML,
tests, metadata from the 3 local states; pushed) and `a69eb25` (map and reports regenerated
over the full mirror on `wsl`; pushed). The docs follow in a third commit.

## What was built

### `scripts/_dict_fd.py` — INEGI's FD workbook → `parse_ddi`-shaped dictionaries

- **`read_xlsx(path)`**: a stdlib reader (`zipfile` + `ElementTree`). It returns `{sheet:
  [{column letter: text}]}` and handles shared strings (incl. rich-text runs), inline strings
  and literal values. It skips empty and whitespace-only cells. The user chose this over
  adding `openpyxl` (see Decisions).
- **`read_catalogs(zip)`**: reads `{STEM: {code: label}}` from `889463931966_csv.zip`, where
  the code is the concatenation of the `CLAVE`/`CVE_*` columns. `match_catalog(phrase)` maps a
  `(Según clasificador de …)` note to the stem with the largest word overlap. That copes with
  `entidad federativa y país` → `ENTIDAD_PAIS` and with INEGI's own typo
  `ESOLARIDAD_ACUMULADA`. A tie or no shared word returns `None`.
- **`parse_fd_xlsx(path, catalogs)`** → `{stem: {VAR: meta}}` (`viviendas`/`personas`/
  `migrantes`). Its meta has `Descripción`, `Pregunta`, `Tipo`, `Longitud`, `Rango`,
  `Categorías`, `Especiales`, `Catálogo` and `Nota`. Rules, all from the probe of
  `eic2025_micro_fd.xlsx`:
  - A table sheet is one with a `Mnemónico` header row (header text compared accent- and
    case-folded). `Índice` and `MODELO LÓGICO` have none.
  - A row whose mnemonic is an identifier starts a variable. A row with code + label is one
    of its codes; `Nulo` ("Blanco por pase") is skipped, since it is the null cell.
  - A row with a description and a question but no code is a **question stem** (`En su vida
    diaria, ¿(NOMBRE) cuánta dificultad tiene para:`). It prefixes every following item
    question that starts in lower case (`ver, aun usando lentes?`), until the next stem or
    section. The migrantes sheet marks its stem with the placeholder mnemonic `--`, which is
    therefore not a variable.
  - Code ranges: `01..54`, `0101.. 9030` (with a space) and `…` all parse. Zero-padding
    comes from the bounds.
  - **Numeric** (`Numérico`): ranges and in-range single codes are values, giving `Rango`
    `[min, max]`. A single code above the range is an `Especial`, unless its label marks a
    top-code (`Ingresos mayores a 999,997` = 999998 stays a value). Value labels such as `0 =
    Ninguno` go to `Nota`.
  - **Character** (`Carácter`): labels matching `no especificad…`/`No sabe` become
    `Especiales`, everything else `Categorías`, in the sheet's order. A classified range is
    replaced by the catalog's codes. An unclassified span ≤ 200 codes gets identity labels
    (the person-number pointers `01..54`). A wider span is not enumerated: the variable
    becomes `Tipo: string` with a `Nota` (`LOC50K`).
- **`parse_indicator_csv(path)`** reads the aggregates' `diccionario_datos_*.csv` (header
  `Cons.|Indicador|Descripción|Mnemónico|Rangos|Long.`). It generalises
  `utils.get_vars_from_indicator_csv`, whose header test (`Núm…`) does not match 2025.
  - `0 … 100.00` → `Tipo: numeric`, with `Decimales` taken from the upper bound.
  - Zero-padded code ranges (`00…32`) and `Alfanumérico` → string.
  - The table's footnotes `NA: No aplica.` and `MI: No disponible por muestra insuficiente.`
    become every numeric indicator's `Especiales`.
  - The ranges are kept verbatim as `Rangos` but are **not** turned into a `Rango` bound. One
    column holds all five estimators, and the CV rows exceed the 0–100 range of a percentage
    in 64 indicator columns (`PCN_VPH_*`, `PCN_PA*`, …), so only the `Valor` rows obey it.
- **`fd_entry`** wraps `_dict_ddi.dictionary_entry`: same priority core > dictionary > data,
  same re-spelling and undocumented-code handling. It differs in four ways:
  - A string variable without categories, or whose catalog has more codes than the
    threshold, stays `Tipo: string` with `Catálogo` + `Especiales`, instead of a huge
    `Categorías` map.
  - Numerics keep the FD `Rango`, which is the questionnaire bound (a DDI `valrng` is only
    the observed range).
  - `Catálogo`/`Decimales`/`Definición`/`Rangos` are carried over.
  - Sources report as `fd`/`fd+data`.
- `_dict_ddi.group_entries` gained an `entry_fn=` hook (default `dictionary_entry`, so
  ENOE/ENIGH are unchanged).

### `scripts/build_cpv.py` — the metadata modes (same set as ENIGH)

- `--dictionary` (default `--periods` = the enabled editions) downloads into
  `data/dict/fd/{period}/`:
  - the edition's `DICTIONARY_URLS`: xlsx/zip are CRC-verified; anything else is rejected
    if it is an HTML soft-404;
  - the RNM DDI when `CpvEdition.ddi_id` is set (none for 2025);
  - each aggregate table's `diccionario_datos_*.csv`, copied out of its (cached) product ZIP
    as `diccionario_datos_{table}.csv`.
- `--schema-map` → `cpv_schema_map.yaml` in the `PLAN.md` format. Gids go in
  (edition, state) order. `states: {period: [NN…]}` appears only for an edition a group
  covers partially. `latest` is the group holding the most files of the newest edition.
- `--report-only` → `INCONSISTENCY_REPORT.md`: inventory, groups, drift between consecutive
  editions, and missing files of the editions on disk or enabled.
- `--variables` → `variables_cpv_{table}_{gNN}.yaml`, core > FD/indicator CSV > data.
  - Observed values are read per column with `_dict_ddi.observed_values`.
  - `_TABLE_THRESHOLD = {"estimaciones": 0}` overrides `--cat-threshold`, so the numeric
    cells are never enumerated.
  - Columns sourced from `data`/`+data` are printed.
- `--validate [--jobs N]` → `VALIDATION_REPORT.md`.
  - Each file is validated in 1 Mi-row batches (`iter_batches` → `to_pandas`; checked
    identical to `read_parquet`), so memory stays bounded for the 2.4 M-row personas files.
  - Files run in parallel with `--jobs`, and the exit code is 1 on any failure.
- `--update-registry` upserts `cpv_*` hashes. The code is written but **not run**; that is
  for 1e.

### Package side

- **`src/mxcensus/cpv.py`** (skeleton; the loaders are 1c): `_WEIGHTS = {"FACTOR"}`,
  `_fingerprint`, `_group_of` (family `CPV`, raises on unknown), `_validate` (warns) and
  `_group_schema(table, gid)`. The schema is `_schema_groups.build_group_schema` plus
  `_code_rule`:
  - keys/geography (`ID_*`, `CVEGEO`, `CVE_ENT`, `CVE_MUN`, `LOC50K`, `CVE_LOC`) must be
    digits (widths are edition-specific, so they are left to the data tests);
  - a `Catálogo` string column must be exactly `Longitud` digits.
- **`_resources`**: `cpv_schema_map()`, `variables_cpv(table, gid)`, `variables_cpv_core()`.
- **`variables_cpv_core.yaml`** is hand-curated, never regenerated, and uses the ENOE contract
  header plus the informative keys `Catálogo`/`Definición`/`Rangos`/`Nota`. It covers:
  - keys `ID_VIV`/`ID_PERSONA`/`ID_MII`;
  - geography `CVEGEO` (5 digits in the microdata, 9 in estimaciones), `CVE_ENT`, `CVE_MUN`,
    `LOC50K`, `CVE_LOC`, and `TAMLOC` (ordered);
  - `COBERTURA`, `ESTRATO`, `UPM`, `FACTOR`, `TIPO_REG`, `CLAVIVP`, `SEXO` (`1`/`3`), and
    `EDAD` (`Rango [0, 130]`, `999` = No especificado);
  - `ESTIMADOR` (the 5 literal estimator names). Every code was checked against the FD and
    the data.

## Numbers

- **FD vs data**: the FD documents exactly the data columns, in the same order: 87 / 92 / 27.
  Migrantes has one extra row, the `--` stem.
- **Catalogs** (`889463931966_csv.zip`, 10 CSVs):

  | catalog | codes | treatment |
  |---|---|---|
  | `ACTIVIDAD_ECONOMICA` | 181 | string + width check |
  | `CAUSA_MIGRACION` | 35 | `Categorías` |
  | `CONDICION_MENTAL` | 21 | `Categorías` |
  | `ENTIDAD` | 32 | unused |
  | `ENTIDAD_PAIS` | 261 | string + width check |
  | `ESOLARIDAD_ACUMULADA` | 26 | `ESCOACUM` is numeric 0–24, catalog named |
  | `LENGUA_INDIGENA` | 74 | string + width check |
  | `MUNICIPIO` | 2,511 entity+municipality rows | string + width check |
  | `OCUPACION` | 163 | string + width check |
  | `PARENTESCO` | 41 | `Categorías` |

  The threshold (64) reproduces exactly the split `HANDOFF.md` asked for (SINCO, SCIAN,
  country, municipality, language → string).
- **Sources per group** (identical on the 3-state Mac run and the 32-state `wsl` run, so the
  generated YAML did not change between them):

  | table | core | fd | data / +data |
  |---|---|---|---|
  | viviendas | 12 | 75 | 0 |
  | personas | 15 | 77 | 0 |
  | migrantes | 12 | 15 | 0 |
  | estimaciones | 5 | 344 | 0 |

  Every code observed in 25 M person rows is documented by the FD.
- **Validation** (`wsl`, `--jobs 8`): **0 / 97 failing**, 45 s wall.

  | table | files | rows |
  |---|---|---|
  | viviendas | 32 | 7,340,046 |
  | personas | 32 | 25,222,336 |
  | migrantes | 32 | 362,679 |
  | estimaciones | 1 | 13,880 |

  The largest personas file took 22 s. On the Mac, the 10 local files took 7 s.
- **The schema is not vacuous**: one planted bad value per rule type was rejected:

  | rule | rejected value |
  |---|---|
  | `isin` | `SEXO=2`, `NIVACAD=15`, `PARENTESCO=102`, `IDENT_MADRE=55`, `ESTIMADOR=valor` |
  | `Rango` | `EDAD=131`, `HORTRA=141`, `FECHA_NAC_A=1900` |
  | digit codes | `CVE_ENT=x1`, `CVE_LOC=00A1` |
  | catalog width | `OCUPACION_C=12`, `ENT_PAIS_NAC=1234` |
  | weight | `FACTOR=abc` |
  | indicator | `POBTOT=ZZ` |

  The sentinels (`INGTRMEN=999999`, `MI`) pass. These checks are pinned in `tests/test_cpv.py`.
- The RNM was re-checked: still **no EIC 2025 DDI**. No intercensal entry is among the newest
  catalog entries, and ids 1152–1155 and 1160 return 404.

## Findings for 1c

- **`TIPO_REG`**: `0` = Encuestado, `1` = Imputado (FD). It appears in viviendas too (state 15
  has `1`s), not only in personas.
- **`CLAVIVP` 07/09** are "Local no construido para habitación" and "Refugio" (FD). This
  confirms the 1a observation that their housing block is empty.
- **`MPERLS`** (migrantes) is a returned migrant's number in the dwelling's person list
  (`MODELO LÓGICO`: FK). In state 01 it is filled for the 652 migrants with `MCONRESACT = 1`
  (vive aquí), and **all 652 match a person on (`ID_VIV`, `NUMPER`)**. This is an optional
  migrant → person link for `load_cpv_survey`; migrants stay siblings of persons.
- **Person-number pointers** are `NUMPER`, `IDENT_MADRE`/`IDENT_PADRE`/`IDENT_PAREJA`,
  `DUE1_NUM`/`DUE2_NUM`, `MPER` and `MPERLS`. They are categoricals of 53–56 identity codes
  `01..54` plus labelled specials (96 "vive en otra vivienda", 98 "No sabe", …), so they
  validate tightly. With `labels=True` they would become wide Categoricals. 1c should decide
  whether to put them in `skip=` (keep them as joinable strings) or label them.
- **Year/month fields**:
  - `FECHA_NAC_A` (1925..2025, 101 codes > 64) becomes numeric with `Rango` + `9999` →
    Int64 under `labels`.
  - `MFECEMIA`/`MFECRETA` (2020..2025, 6 codes) and the months `FECHA_NAC_M`/`MFECEMIM`/
    `MFECRETM` stay identity-labelled categoricals.

  This is consistent with the threshold but not with itself. 1c may move the years to
  numeric in the core if that reads better.
- **`label_frame` coverage**: `labels=True` maps exactly the `Categorías ∪ Especiales` that
  `--validate` checked, so no mirror file can raise an unmapped code. The catalog strings
  (`OCUPACION_C`, `ACTIVIDADES_C`, `ENT_PAIS_*`, `MUN_*`, `QDIALECT_INALI`, `MLUGORI_C`,
  `MPAIDES_C`) stay raw codes; a loader option could join the catalog CSV later.
- **Estimaciones** under `labels`: `NA`/`MI` → NA. Percentages (`Decimales: '2'`) become
  Float64 and counts Int64. `ESTIMADOR` is a 5-label categorical, which
  `load_cpv_estimaciones` maps to `valor|ee|li|ls|cv`.

## Decisions (user, this session)

- **xlsx reader**: stdlib (`_dict_fd.read_xlsx`), not `openpyxl`. Nothing was installed on
  either host and no `build` extra was added. A `build` extra is still needed for `dbfread`
  (unit 3b).
- **`wsl` run**: commit and push the code, run the modes on `wsl`, commit the regenerated
  metadata there, push, and pull on the Mac (same as 1a).

## Deviations from the plan

- No `openpyxl` and no `build` extra (above). The `PLAN.md` Phase 1 docs bullet is updated.
- `utils.get_cats_from_excel` and `get_vars_from_indicator_csv` were not reused or edited. Their
  logic was generalised into `_dict_fd`, as `PLAN.md` §Critical files allowed. The util's
  `Núm` header test does not match the 2025 CSV's `Cons.`.
- `CPV_DDI` was not added to `_dict_ddi.py`; `--dictionary` reads `CpvEdition.ddi_id` from the
  catalog instead (one source of truth).
- Aggregate `Especiales` are **not** a fixed `{'*', 'N/D'}`. They come from each
  dictionary's own footnotes (2025: `NA`, `MI`; there are no `*`/`N/D` cells). The `*`/`**`
  footnotes mark municipality *names* (`Abasolo*` = censado), not cell values.
- The core grew beyond the handoff list: `CLAVIVP` (present in all three microdata tables),
  `CVE_LOC` and `ESTIMADOR` (estimaciones).

## Tests

`tests/test_cpv.py` gained:
- `read_xlsx`/`read_catalogs`/`match_catalog` and `parse_fd_xlsx` on a synthetic workbook
  built in the test. It covers shared and inline strings, a `--` stem, a stray blank cell,
  `Nulo`, identity spans, a classified range with and without catalogs, the top-code, a
  header-only numeric and a too-wide range.
- the `fd_entry` rules and `parse_indicator_csv` (footnote sentinels, `Decimales`, no
  `Rango`);
- `_group_schemas` (partial states, `latest`) and `_mirror_files`;
- over the bundled map: fingerprint round-trips, valid frames, rejections, estimaciones
  sentinels, the core contract (and core copied verbatim into every group), and every
  generated column documented.

`tests/test_schema_groups.py` adds `cpv` to the family-wrapper loops.

Full suite (Mac, before the `wsl` commit): **685 passed** in 13 min 49 s, up from 661. The 4
warnings are the pre-existing DENUE/ENOE ones. The CPV tests are green on `wsl` and again on
the Mac after the pull (123 passed).

## Gotchas

- **Never run `--schema-map`, `--variables` or `--report-only` on the Mac's partial mirror.**
  They would rewrite `files: 3` and a missing-files list over the committed 32-state
  metadata. Metadata comes from `wsl`.
- `pooch` prints a `SHA256 … known_hash` hint when it downloads a dictionary. That is harmless,
  and the bytes are identical on both hosts (FD `679922eb…`, catalogs `f0b3f32a…`).
- The `/usr/bin/time` peak-RSS figure from the parallel `--validate` (160 MB) covers the parent
  process, not the workers, so it is not a memory measurement.
