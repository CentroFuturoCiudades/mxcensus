# CPV Unit 3a — Encuesta Intercensal 2015

Done **2026-10-07**. Gate:
- `build_cpv.py --validate` reports **0 failures over all 321 files** (64 EIC 2015 + 160 CPV
  2020 + 97 EIC 2025) on `wsl` (`VALIDATION_REPORT.md`).
- Σ `FACTOR` equals INEGI's published EIC 2015 totals **exactly**: in every state and
  nationally, for dwellings, population, men and women.

No registry or upload in 3a: the plan uploads 3a–3d together in 3d. Nothing was committed
during the unit. The code was copied to `wsl` with `scp` and the generated metadata copied
back (§Process).

## Probe (state 01)

`intercensal/2015/microdatos/eic2015_01_csv.zip` (6.8 MB) holds `TR_VIVIENDA01.CSV` and
`TR_PERSONA01.CSV`, dated 2015-12-17. `find_member` matches the upper-case `.CSV`, because
the member regexes compile with `re.IGNORECASE`.

- **Encoding**: cp1252 (63 of 64 files). `cpv_viviendas_2015_02` sniffs as UTF-8 because it
  is pure ASCII (Baja California's names have no accents).
- **Columns**: viviendas 88, personas 86. Geography: `ENT` (zero-padded `01`), `NOM_ENT`,
  `MUN` (`001`), `NOM_MUN`, `LOC50K` (`0000`/`0001`), `NOM_LOC`. 2015 has no `CVEGEO`,
  `TIPO_REG` or migrant table. `TAMLOC` is the last column of both tables. The persons table
  has no `CLAVIVP`.
- **Leading zeros dropped.** The CSVs write numbers without their leading zeros, although
  the FD documents zero-padded codes:
  - `ID_VIV` has 11 digits in states 01–09 and 12 elsewhere (the FD documents
    `{010010000001.. 320589999999}`).
  - `ID_PERSONA` = `ID_VIV` + the 2-digit `NUMPER`: 13 or 14 digits (2020/2025: 17).
  - `CLAVIVP` is `1`…`9`, `99` (2020/2025: `01`…`09`, `99`).
  - `ENT`, `MUN` and `LOC50K` keep their padding.
- **Sample design**:
  - `COBERTURA` uses the 2020/2025 codes 1/2/3.
  - `ESTRATO` has 9 characters (`01-001-05`; the FD allows 17).
  - `UPM` has 6 digits (the FD allows 7; 2020/2025 have 5).
  - `FACTOR` ranges 1–467 (core `Rango [1, 99999]`).

## Dictionary: the FD `.xls` through a new stdlib reader (user's choice)

**RNM DDI 214** (`MEX-INEGI…EIC-2015`) documents `TR_Vivienda`/`TR_Persona` with exactly
the data's columns, apart from the typo `MUN__TRAB`. Like 2020's DDI 632, it is a Nesstar
export and falls short:

| variable | DDI 214 | FD `eic2015_fd.xls` |
|---|---|---|
| `EDAD` | one category `0` labelled «109 Años cumplidos» (the range row `0..109` collapsed), `110`, `999` | `0..109`, `110` = 110 y más, `999` No especificado |
| `ESCOLARI`, `HIJOS_*`, `ACTI_SIN_PAGO1-8`, `EDAD_MORIR_*` | the same collapse (`'1': '9 Grado de escolaridad'`, `'1': '140 Horas'`…) | ranges + sentinels |
| `NUMPERS` | `1` Sí / `3` No (another variable's codes) | `1..54` |
| `LOC50K` | `1`/`2` | `0001..9999` / `0000` |
| sentinels | no `missing` flag anywhere: `999` would count as an age | `No especificado` rows |
| types | every variable `numeric` (`NOM_ENT`, `ESTRATO`…) | Numérico / Caracter |

The FD workbook `doc/eic2015_fd.xls` is complete and has the 2020/2025 layout (sheets
`TR_Vivienda`, `TR_Persona`, `Modelo de datos`), with `Rango Válido` before `Tipo`. It is
a **legacy BIFF8 `.xls`**, which the stdlib `read_xlsx` cannot read, and `xlrd` would be a
new dependency. Asked mid-unit, the user chose **a stdlib `.xls` reader**. `CpvEdition("2015")`
keeps `ddi_id=214`, and `--dictionary` fetches the codebook for reference only.

**Catalogs.** The FD names its classification catalogs (`TC_PARENTESCO_2015`,
`TC_OCUPACION_2015`…). The file-listing API (`idBiinegi` 1714) does not list them, but
`intercensal/2015/doc/eic2015_catalogos.zip` exists. It holds 11 one-sheet `.xls` files:
`TC_PARENTESCO_2015` (48), `TC_OCUPACION_2015` (156), `TC_SECTOR_2015` (178),
`TC_ENTIDAD_PAIS_2015` (262), `TC_LENGUA_INDIGENA_2015` (326),
`TC_LENGUA_INDIGENA_INALI_2015` (73), `TC_MUNICIPIO_2015` (2,490), `TC_COBERTURA` (3), the
minimum-wage table `TC_SALARIO_MUN_2015`, the reference table `TC_ESCOACUM_2015` and an
index. It was added to `DICTIONARY_URLS["2015"]`.

### `scripts/_dict_fd.py`

- **`read_xls(path | bytes)`** returns the same `{sheet: [{column letter: text}]}` as
  `read_xlsx`, using only the standard library (`struct`):
  - **container**: the OLE2 compound file (512- or 4096-byte sectors, DIFAT chains, the
    mini stream for streams under the cutoff);
  - **workbook stream**: `BOUNDSHEET`, and `SST` + `CONTINUE` (a string crossing a record
    boundary restarts with an option byte; rich-text runs and extensions are skipped);
  - **cells**: `LABELSST`, `LABEL`, `NUMBER`, `RK`, `MULRK`, and `FORMULA` + `STRING`
    cached results;
  - **skipped**: chart sheets and substreams nested in a worksheet (embedded charts).
  - It reads all 12 INEGI workbooks identically to the scratch prototype that was checked
    by eye.
- **`read_workbook`** dispatches on the file signature (`PK` vs `D0CF11E0`).
- **`parse_fd_xlsx` → `parse_fd`**, which reads either format. It handles 2015's
  conventions generically:
  - **«Numérico» coded items.** 2015 types its coded items «Numérico», where 2020/2025 use
    «Carácter»: `SEXO {1,3}`, `ELECTRICIDAD {5,7,9,Nulo}`, `TAMLOC {1…5}`. `_enumerated`
    makes such a variable categorical when its code rows label every header code one by
    one. A quantity still has a range row (`0..109 Años cumplidos`) or a header range that
    no row enumerates (2025 `EDAD`).
  - **`TC_…` code rows.** A row labelled «Descripción por catálogo» names the catalog
    (`Catálogo`), which enumerates the variable's codes. Any other label (a municipality
    *name* column, the minimum-wage table, `ESCOACUM`'s reference table) becomes a `Nota`.
  - **Blank rows**: a row labelled «Blanco…» marks the blank cell whatever its code
    (`Nulo`; 2015 also writes `b`).
  - **Non-codes**: `Ver catálogo` in a header is not a code.
- **`read_catalogs`** reads `.xls` members too. Its key columns now include `CLAVE_*`
  (`TC_MUNICIPIO_2015`: `CLAVE_ENT` + `CLAVE_MUN`), and a member without key or description
  columns is skipped.
- **2020/2025 parses are byte-identical** before and after: the catalogs, FD workbooks and
  indicator CSVs dumped as JSON on both hosts (md5 `ce76b6e4…` on `wsl`).

`build_cpv._fd_docs` accepts `.xls` and maps the sheet stems `tr_vivienda`/`tr_persona` to
the tables (`_FD_SHEET_TABLE`).

**Result on the 32-state data**: every 2015 column comes from the core or the FD; there are
no `fd+data` or `data` entries.

| group | core | fd | Tipo |
|---|---|---|---|
| viviendas/g01 | 8 | 80 | 69 categorical, 11 numeric, 8 string |
| personas/g01 | 10 | 76 | 38 categorical, 25 numeric, 23 string |

The large catalogs (occupation, activity, country, municipality, language) are width-checked
strings with `Catálogo`; `PARENT_OTRO_C` (47 codes) is labelled.

## Build

`_ENABLED = ("2015", "2020", "2025")`. A smoke build of state 01 on the Mac took 13 s,
including the download.

**Full build on `wsl`** (`--periods 2015 --retries 6`, log `wsl:~/mxcensus/build_cpv_2015.log`):
- **64 files written, 0 failed**;
- 24 min, dominated by INEGI's download rate (853 MB of ZIPs);
- peak RSS 2.7 GB;
- 594 MB of parquet (viviendas 110 MB, personas 485 MB).

| state | viviendas | personas | Σ FACTOR viviendas | Σ FACTOR personas |
|---|---|---|---|---|
| 01 | 43,613 | 177,853 | 334,589 | 1,312,544 |
| 02 | 55,751 | 192,034 | 967,863 | 3,315,766 |
| 03 | 23,642 | 78,983 | 209,834 | 712,029 |
| 04 | 41,504 | 158,693 | 244,471 | 899,931 |
| 05 | 104,631 | 379,692 | 809,275 | 2,954,915 |
| 06 | 32,991 | 115,647 | 205,243 | 711,235 |
| 07 | 406,797 | 1,824,844 | 1,239,007 | 5,217,908 |
| 08 | 170,844 | 601,066 | 1,033,658 | 3,556,574 |
| 09 | 160,006 | 553,032 | 2,601,323 | 8,918,653 |
| 10 | 95,818 | 379,608 | 455,989 | 1,754,754 |
| 11 | 178,100 | 723,696 | 1,443,035 | 5,853,677 |
| 12 | 279,157 | 1,144,440 | 895,157 | 3,533,251 |
| 13 | 214,130 | 815,460 | 757,252 | 2,858,359 |
| 14 | 331,769 | 1,266,418 | 2,059,987 | 7,844,830 |
| 15 | 480,680 | 1,922,025 | 4,168,206 | 16,187,608 |
| 16 | 291,433 | 1,133,370 | 1,191,884 | 4,584,471 |
| 17 | 99,374 | 368,976 | 523,984 | 1,903,811 |
| 18 | 65,042 | 245,239 | 332,553 | 1,181,050 |
| 19 | 144,210 | 518,876 | 1,393,542 | 5,119,504 |
| 20 | 578,240 | 2,221,014 | 1,043,527 | 3,967,889 |
| 21 | 428,362 | 1,748,258 | 1,554,026 | 6,168,883 |
| 22 | 70,016 | 278,508 | 533,596 | 2,038,372 |
| 23 | 47,038 | 167,489 | 441,200 | 1,501,562 |
| 24 | 154,983 | 604,420 | 710,233 | 2,717,820 |
| 25 | 82,072 | 305,488 | 806,237 | 2,966,321 |
| 26 | 125,554 | 440,966 | 814,820 | 2,850,330 |
| 27 | 73,506 | 277,847 | 646,448 | 2,395,272 |
| 28 | 116,613 | 400,776 | 987,184 | 3,441,698 |
| 29 | 118,579 | 491,365 | 310,504 | 1,272,847 |
| 30 | 555,209 | 2,067,015 | 2,251,217 | 8,112,505 |
| 31 | 162,257 | 626,599 | 565,015 | 2,097,175 |
| 32 | 122,471 | 462,568 | 418,850 | 1,579,209 |
| **total** | **5,854,392** | **22,692,265** | **31,949,709** | **119,530,753** |

## Σ FACTOR vs INEGI's published totals

Source: INEGI, *Encuesta Intercensal 2015, tabulados predefinidos* (elaborated 24/10/2016),
`intercensal/2015/tabulados/14_vivienda.xls` sheet `02` (viviendas particulares habitadas
by entidad) and `01_poblacion.xls` sheet `02` (population in viviendas particulares
habitadas by entidad and sex), row «Total», estimator «Valor». Read with the new `read_xls`.

| | published | Σ FACTOR |
|---|---|---|
| viviendas particulares habitadas | 31,949,709 | 31,949,709 |
| población en viviendas particulares habitadas | 119,530,753 | 119,530,753 |
| hombres | 58,056,133 | 58,056,133 |
| mujeres | 61,474,620 | 61,474,620 |

All four are **equal in each of the 32 states** too; the per-state figures are pinned in
`tests/test_cpv.py::_PUBLISHED_2015`. As in 2020, the sample expands to the population of
inhabited private dwellings, not the total population.

## Structural checks (all 32 states, `wsl`)

Every check passes in every state (`tests/test_cpv.py::test_eic2015_data_checks_by_state`):
- `ENT` equals the file's state in both tables.
- `ID_VIV` and `ID_PERSONA` are unique.
- `ID_PERSONA` = `ID_VIV` + the 2-digit `NUMPER`.
- `ID_VIV.zfill(12)[:5]` = `ENT` + `MUN`.
- Every person's dwelling exists, and every dwelling has people.
- `FACTOR` is constant within the dwelling, and a person's `FACTOR` is the dwelling's.
- `NUMPERS` equals the dwelling's person records.
- There is one `COBERTURA` per municipality.

## Metadata (`wsl`, in order)

`--dictionary --periods 2015` (FD, catalogs, DDI 214), then `--schema-map`,
`--report-only`, deleting the stale `variables_cpv_{viviendas,personas}_g0*.yaml`,
`--variables` (3 min 32 s) and `--validate --jobs 16` (82 s).

- **Schema map**: 11 groups.
  - **The gids shift.** For viviendas/personas, 2015 = `g01`, 2020 = `g02` and 2025 =
    `g03` (latest). Migrantes are unchanged: 2020 = `g01`, 2025 = `g02`.
  - The 2020/2025 YAMLs under their new gids differ from the old ones only by this unit's
    core edits.
- **Drift 2015 → 2020** (`INCONSISTENCY_REPORT.md`):
  - viviendas renamed or split several items: `LUGAR_COCINA` → `LUG_COC`,
    `DESTINO_BASURA` → `DESTINO_BAS`, `SEPARA_*` → `SEPARACION1-4`, `NUM_DUE_VIV1/2` →
    `DUE1/2_NUM`, `ALIM_ADU*` → `ALIM_ADL*`. It dropped `NOM_*`, `TERRENO_*` and
    `TELEVISOR_PP`.
  - personas: `PARENT`/`PARENT_OTRO_C` → `PARENTESCO`, `*_RES10` → `*_RES_5A`. 2020 added
    the disability block (`DIS_*`/`CAU_*`), `RELIGION`, `CLAVIVP`…; `ACTI_SIN_PAGO1-8` and
    `QDIALECT_C` were dropped.
  - None of these are core, so they stay verbatim under `harmonize=True`.
- **Validation**: **0/321 failing**.

## Core and package changes

- **`variables_cpv_core.yaml`**, verified for 2015:
  - `ID_VIV`, `ID_PERSONA` (`Longitud 14 / 17`), `CVE_ENT`/`CVE_MUN` (2015 spells them
    `ENT`/`MUN`, like 2020), `LOC50K`, `COBERTURA`, `ESTRATO` (`9 / 14 / 15`), `UPM`
    (`5 / 6`), `FACTOR`, `CLAVIVP`, `SEXO`, `EDAD` (2015's `110` = 110 y más fits
    `Rango [0, 130]`) and `TAMLOC` carry the same codes in 2015.
  - **`CLAVIVP` gains an `Alias`** `1`…`9` → `01`…`09` (ENIGH's `educa_jefe` pattern), so
    the raw validation and the labels accept 2015's spelling. INEGI words class 03 «Casa
    dúplex, triple o cuádruple» and class 06 «Cuarto en la azotea…» in 2015; the codes are
    the same.
  - The header's «verified for» list names EIC 2015.
- **`cpv.py`**:
  - **`_CODE_PAD`** = `ID_VIV` 12, `ID_PERSONA` 14 and `CLAVIVP` 2, zero-padded by
    `harmonize=True` next to `_GEO_PAD`. `zfill` is a no-op on 2020/2025, which are already
    padded (and whose person key has 17 digits).
  - With the padding, a harmonized 2015 frame has `ID_VIV[:2] == CVE_ENT`,
    `ID_VIV[:5] == CVEGEO` and `ID_PERSONA[:12] == ID_VIV`, as in 2025.
  - `_POINTERS` += `NUM_DUE_VIV1`, `NUM_DUE_VIV2`, `NUM_DUE_TERR` (2015's owner pointers),
    so they stay raw strings.
  - Docstrings name 2015.
- **`_cpv_catalog`**: 2015 notes, and `DICTIONARY_URLS["2015"]["catalogos"]`.
- **`build_cpv.py`**: `_ENABLED`, `_fd_docs`/`_FD_SHEET_TABLE`, and docstrings.
- **README**: the `variables_cpv(...)` examples use `g03` = EIC 2025, `g02` = Censo 2020 and
  `g01` = EIC 2015. Prose about 2015 waits for its release (3d), as 2a's did.
- **CLAUDE.md**: CPV status and the module/YAML rows.

`load_cpv(table=…, period=2015, state=N)` and `load_cpv_survey(2015, state=N)` (which
returns `migrantes=None`) work against a local mirror. They cannot fetch 2015 until the
files are registered and uploaded in 3d.

## Tests

`tests/test_cpv.py` adds:
- **an in-test BIFF8/OLE2 writer** (`_xls`, `_ole`), so `read_xls` is tested without
  binary fixtures:
  - mini-stream and regular-sector storage;
  - SST strings split across `CONTINUE` records (option byte switching between latin-1
    and UTF-16, rich-text runs crossing a boundary);
  - `RK` (integer, ×100), `MULRK`, `NUMBER`, `LABEL`, formula number and text results;
  - an embedded chart substream and a chart sheet, both ignored;
  - a large stream, and the errors;
- `read_catalogs` with `.xls` members (composite municipality key, reference table
  skipped);
- a synthetic 2015-layout FD parsed through the `.xls` path, `_enumerated`, and `_fd_docs`
  mapping the 2015 sheets;
- the 2015 build plan (32 ZIPs → 64 files), the schema groups, and planted rejections in
  the 2015 schemas (19 rule types: `SEXO=2`, `EDAD=131`, `CLAVIVP=10`, `PARENT_OTRO_C=102`,
  `ACTIVIDADES_C=111`, `IDENT_MADRE=55`, `NUM_DUE_VIV1=55`…);
- unpadded codes and sentinels accepted, and harmonized padding (idempotent, validated);
- `_REAL` tests:
  - state-01 loads: shapes, `migrantes=None`, raw unpadded keys, labelled `CLAVIVP`
    through the `Alias`, pointers raw, harmonized 12/14-digit keys, and 2015 + 2025
    stacked;
  - the real FD + catalogs;
  - per-state published totals and structural checks;
  - the national total, when all 32 states are present (`wsl`).

Existing tests now find the 2020 gids through `_gid(table, period)`.
`test_raw_vs_harmonized_totals_real` covers 2015, loops over the tables each edition
publishes, and checks the padded columns. The pointer test accepts 2015's numeric
`Rango [1, 54]`.

Results: Mac full suite **835 passed, 3 skipped** in 7 min 13 s (the 4 warnings are the
pre-existing DENUE/ENOE ones). `wsl` CPV/schema/CLI tests (all 32 states of 2015, 2020 and
2025): **536 passed** in 32 min 44 s (`wsl:~/mxcensus/pytest_3a.log`).

## Findings for later units

- **3b (CPV 2010)**:
  - The FD `doc/diccionario_cuestionario_ampliado.xls` is a `.xls`, which `read_xls` should
    read. The catalogs are DBF (`doc/catalogos_2010_dbf.zip`).
  - The microdata are DBF: the plan's `dbfread` (a new build extra) or a stdlib reader?
  - `ID_VIV` has 8 characters and is unique within a state only. Make it national (prefix
    the entity, as the probe suggests) **before** `_CODE_PAD` pads it, or the zfill(12)
    would invent a wrong entity prefix.
  - Add `ID_PER` → `ID_PERSONA`, `ID_MIN` → `ID_MII` and `TAM_LOC` → `TAMLOC` to
    `_RENAME_CORE` once their codes are verified.
- **3d**: register and upload the 64 files with the rest. Write the README's 2015 prose and
  the `fetch --dataset cpv --edition 2015` CLI note then. The MG frame of 2015 is still to
  be identified.
- `TIPOHOG` code 4 «Hogar no especificado (Familiar)» lands in `Especiales` (the sentinel
  regex matches «no especificado»). It is a category either way.

## Deviations from the plan

- **Dictionary**: the FD `.xls` + catalogs, not DDI 214 (user's decision on the evidence
  above). This needed a stdlib BIFF8 reader rather than `xlrd`.
- **`harmonize=True` now pads keys and `CLAVIVP`** (`_CODE_PAD`). The plan listed only
  the geography.
- The catalogs ZIP is not in INEGI's file-listing API; its URL was found by trying
  `doc/eic2015_catalogos.zip`.

## Process

As in 2a: the changed files were `scp`'d to `wsl:~/mxcensus` (working tree dirty there), the
metadata ran there, and the generated files were `scp`'d back (checksums equal). **Before
pulling on `wsl` after the commit**, discard the copies there. The two new `g03` YAMLs are
untracked on `wsl`, so a pull would refuse to overwrite them:

```bash
git checkout -- .
rm src/mxcensus/_yaml/variables_cpv_{viviendas,personas}_g03.yaml
git pull --ff-only
```

Logs on `wsl:~/mxcensus`: `build_cpv_2015.log`, `check_2015.log`, `validate_3a.log`,
`pytest_3a.log`.
