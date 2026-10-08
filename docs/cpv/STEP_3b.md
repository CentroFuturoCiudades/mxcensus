# CPV Unit 3b — Censo de Población y Vivienda 2010 (microdata)

Done **2026-10-07** (overnight, unattended at the user's request; see §Process). Gate:
- `build_cpv.py --validate` reports **0 failures over all 417 files** (96 CPV 2010 + 64
  EIC 2015 + 160 CPV 2020 + 97 EIC 2025) on `wsl`.
- Σ `FACTOR` equals INEGI's published 2010 cuestionario-ampliado totals **exactly**, in
  every state and nationally.

No registry or upload (3d). The 2010 ITER/AGEB (CSV) are left to 3c.

## Probe (state 01)

`ccpv/2010/microdatos/mpv/MC2010_01_dbf.zip` (2.1 MB) holds `Viviendas_01.dbf` (56
fields), `Personas_01.dbf` (95) and `Migrantes_01.dbf` (27), all dBASE III (version byte
0x03).

- **Encoding**: cp1252 text (94 of 96 files; Baja California's viviendas and migrantes are
  pure ASCII). The language-driver byte is unreliable: viviendas/migrantes say 0x00 and
  personas 0x03 for the same text, and the catalog `TC_MUNICIPIO_2010` says 0x02 and really
  is cp850. The reader therefore decides from the bytes.
- **`FACTOR` is in every table**, personas included (N8, right-aligned). `STEP_0_probe.md`
  said otherwise; it is corrected.
- **Keys are serials unique within a state only**: `ID_VIV` (8 digits), `ID_PER` (9, a
  state-wide person serial, *not* `ID_VIV` + a number) and `ID_MIN` (7).
  - `NUMPER` (5 digits) is the person's number in the dwelling and is unique within it.
  - `MPERA` (emigrant number) repeats within a dwelling, so it cannot build a key.
  - 19 dwellings in states 02, 07 and 13 have 6- or 7-character `ID_VIV`s (as written in
    INEGI's DBF; 172 `ID_PER`s and 7 `ID_MIN`s likewise). They are kept verbatim, and they
    stay unique after zero-padding.
- **Geography**: `ENT`/`MUN`/`LOC50K` are zero-padded as in 2015–2025, with names
  `NOM_ENT`/`NOM_MUN`/`NOM_LOC`.
- **Sample design**: `ESTRATO` has 15 characters (`400-01-001-0003`) and `UPM` 4 digits.
  `CERTEZA` (municipality censused with the CA) and `IDH125` (one of the 125 lowest-HDI
  municipalities) are 1/0 flags. There is no `COBERTURA`.
- **`TAM_LOC`** has four classes (01 < 2 500; 02 2 500–14 999; **03 15 000–99 999**;
  04 100 000+), where 2015–2025's `TAMLOC` has five.
- **`CLAVIVP`** is another classification: 1 casa independiente, 2 departamento,
  3 vecindad, 4 cuarto de azotea, 5 local no construido, 6 móvil, 7 refugio, 9 no
  especificado.
- **State 15** spells the field `tam_loc` in lower case in all three DBFs (every other
  state: `TAM_LOC`), so its files form a schema group of their own.

## The DBF reader: `scripts/_dbf.py` (stdlib + NumPy/Arrow)

The plan named `dbfread(raw=True)` as a new build extra. The user had chosen stdlib readers
for `.xlsx` and `.xls`, and asked for this session to run without installs, so dBASE III
is read with a small module instead:
- **`read_header`** parses the 32-byte header and the field descriptors, and checks that
  the widths add up to the record length.
- **`read_dbf(path | bytes)`** returns a `DbfTable(table, encoding, deleted, header)`:
  - the file is memory-mapped, and the record block is a NumPy `(n, record_len)` view;
  - each field becomes a `string` column, its fixed-width padding (spaces/NULs at either
    end) trimmed and an empty field null;
  - an ASCII column is cast through a fixed-size-binary Arrow array; any other column is
    decoded once per distinct value;
  - deleted records (`*`) are dropped and counted (none in 2010);
  - a file shorter than its declared record count raises.
- **`sniff_encoding`**: `ascii` when no byte is ≥ 0x80. Otherwise the high bytes are
  decoded as cp1252 and as cp850, and the one yielding more Spanish letters wins; the
  driver byte only breaks a tie.

Speed: state 01's 69,804 persons in 0.12 s. The full build peaked at 2.0 GB RSS.
`build_cpv._build_zip` dispatches on the member suffix (`.dbf` → `_dbf.read_dbf`) and
reports dropped deleted records.

## Dictionary: the FD `.xls` + DBF catalogs (DDI 71 cross-checked, unused)

- **FD** `doc/diccionario_cuestionario_ampliado.xls` is the legacy BIFF8 format `read_xls`
  reads, with sheets `VIVIENDAS`/`PERSONAS`/`MIGRANTES`. Its layout differs from 2015's:
  - **There is no `Tipo` column.** `_dict_fd._quantity` infers numbers instead:
    - a labelled range row (`01..25 Número de dormitorios`, `{000001..999997} Ingresos
      especificados`) makes a number;
    - so does a header range plus a sentinel (`EDAD {000..130,999}`) or an unpadded header
      range (`MPERA {0..99}`);
    - a zero-padded header range alone is a code space (`ENT {01..32}`, `MUN {001..570}`);
    - single labelled codes are categories;
    - a variable with a resolved catalog is never a number.
  - The blank cell is **`b`** (`{1..7,9,b}`), which joins `Nulo` in `_NULL_CODES`.
  - Catalogs are named **`Tc_Parentesco_2010`** in code rows (2015's `TC_…` convention,
    case-insensitive), sometimes with a suffix («Descripción por catálogo /1»).
  - The FD lists the sample-design fields before the keys; the DBFs put them last.
- **Catalogs** `doc/catalogos_2010_dbf.zip` (12 DBFs): `read_catalogs` reads `.dbf` members
  through `_dbf.read_dbf(bytes)`. `TC_ESCOACUM_2010` is a level/grade reference table with
  duplicate codes, not a code→label catalog, so it is skipped (no key column). 2010's
  `ESCOACUM` is therefore numeric 0–24 + 99, as in 2015.
- **DDI 71** (`Vivienda_Ampliado`/`Poblacion_Ampliado`/`Migracion_Internacional`, plus the
  basic questionnaire) has the right code lists for some items (`ESCOACUM`, `TAM_LOC`). But
  every variable is typed `string`, and quantities have neither ranges nor sentinels
  (`EDAD`, `HORTRA`, `INGTRMEN`). The FD stays the source, as in 2015/2020; `ddi_id=71` is
  fetched for reference.
- **2015/2020/2025 parses are byte-identical** before and after the `_dict_fd` changes
  (JSON dumps on both hosts, md5 `78c1fc03…` on `wsl`).

**Result**: every 2010 column comes from the core or the FD, with no `fd+data`/`data`
entries.

| group | core | fd |
|---|---|---|
| viviendas/g01, g02 | 5 | 51 |
| personas/g01, g02 | 7 | 88 |
| migrantes/g01, g02 | 5 | 22 |

The large catalogs (country, municipality, language, occupation, SCIAN activity, career,
religion) are width-checked strings with `Catálogo`. Entity of birth and residence
(`TC_ENTIDAD_2010`, 34 codes incl. 900/999) and other-kinship (`TC_PARENTESCO_2010`, 61)
are labelled.

## Build

`_ENABLED = ("2010", "2015", "2020", "2025")`. The smoke build of state 01 on the Mac was
instantaneous.

**Full build on `wsl`** (`--periods 2010 --tables viviendas personas migrantes --retries 6`,
log `wsl:~/mxcensus/build_cpv_2010.log`):
- **96 files written, 0 failed**, 0 deleted records;
- 9 min 58 s wall clock (`/usr/bin/time`), including 362 MB of ZIP downloads;
- peak RSS 2.0 GB;
- 230 MB of parquet (viviendas 33, personas 195, migrantes 2.4 MB).

| state | viviendas | personas | migrantes | Σ FACTOR viv (tab.) | Σ FACTOR per (tab.) |
|---|---|---|---|---|---|
| 01 | 16,572 | 69,804 | 1,268 | 293,024 | 1,178,260 |
| 02 | 25,666 | 92,554 | 662 | 869,565 | 3,098,948 |
| 03 | 9,140 | 31,914 | 135 | 185,595 | 631,738 |
| 04 | 15,382 | 61,756 | 183 | 214,072 | 816,867 |
| 05 | 48,483 | 181,343 | 1,182 | 736,427 | 2,738,203 |
| 06 | 18,310 | 66,508 | 867 | 180,866 | 646,855 |
| 07 | 199,231 | 966,027 | 3,471 | 1,084,500 | 4,785,677 |
| 08 | 78,613 | 282,926 | 3,148 | 951,205 | 3,388,957 |
| 09 | 97,838 | 353,030 | 2,035 | 2,440,641 | 8,770,578 |
| 10 | 48,066 | 202,250 | 2,731 | 407,646 | 1,624,630 |
| 11 | 79,704 | 340,991 | 9,295 | 1,287,875 | 5,472,860 |
| 12 | 155,980 | 719,037 | 10,641 | 816,642 | 3,378,137 |
| 13 | 82,021 | 328,266 | 6,468 | 673,159 | 2,672,904 |
| 14 | 158,952 | 637,439 | 11,809 | 1,819,793 | 7,315,955 |
| 15 | 220,655 | 927,057 | 6,274 | 3,717,606 | 15,104,013 |
| 16 | 133,170 | 540,337 | 12,713 | 1,081,827 | 4,342,947 |
| 17 | 39,406 | 152,689 | 2,216 | 475,166 | 1,768,413 |
| 18 | 27,784 | 114,611 | 1,412 | 294,470 | 1,075,664 |
| 19 | 74,310 | 276,098 | 1,278 | 1,215,839 | 4,640,811 |
| 20 | 381,664 | 1,573,719 | 31,436 | 936,359 | 3,783,491 |
| 21 | 224,013 | 963,016 | 13,899 | 1,380,656 | 5,773,760 |
| 22 | 26,240 | 109,080 | 2,842 | 455,026 | 1,825,159 |
| 23 | 19,338 | 71,742 | 246 | 367,569 | 1,319,120 |
| 24 | 65,778 | 272,907 | 4,613 | 640,693 | 2,573,321 |
| 25 | 33,111 | 128,457 | 825 | 722,337 | 2,758,050 |
| 26 | 71,281 | 260,964 | 1,673 | 735,695 | 2,625,590 |
| 27 | 26,183 | 104,214 | 286 | 570,132 | 2,231,743 |
| 28 | 56,990 | 208,089 | 1,841 | 902,548 | 3,252,937 |
| 29 | 59,483 | 259,858 | 3,308 | 276,772 | 1,179,808 |
| 30 | 254,174 | 1,021,875 | 10,310 | 2,027,661 | 7,622,807 |
| 31 | 99,821 | 398,578 | 1,861 | 504,951 | 1,951,699 |
| 32 | 56,281 | 221,266 | 5,512 | 377,174 | 1,493,882 |
| **total** | **2,903,640** | **11,938,402** | **156,440** | **28,643,491** | **111,843,784** |

## Σ FACTOR vs INEGI's published totals

Source: INEGI, *Censo de Población y Vivienda 2010, Tabulados del Cuestionario Ampliado*
(elaborated 11/05/2011), `ccpv/2010/tabulados/Ampliado/14_03A_ESTATAL.xls`, estimator
«Parámetro»: inhabited private dwellings and their occupants per state. The tabulados'
«viviendas particulares habitadas» **leave out `CLAVIVP` 5–7** (non-residential premises,
mobile dwellings, shelters). The state-01 classes show it: Σ over classes 1–4 + 9 is
exactly 293,024 / 1,178,260; adding class 5 gives 293,237 / 1,178,800.

| | published | Σ FACTOR |
|---|---|---|
| viviendas particulares habitadas (CLAVIVP ∉ 5–7) | 28,643,491 | 28,643,491 |
| ocupantes (CLAVIVP ∉ 5–7) | 111,843,784 | 111,843,784 |
| población total (every record; `09_02A_ESTATAL`) | 111,960,139 | 111,960,139 |
| hombres / mujeres (every record; `09_02A`) | 54,527,077 / 57,433,062 | 54,527,077 / 57,433,062 |

All are **equal in each of the 32 states** too (the dwelling/occupant pairs are pinned in
`tests/test_cpv.py::_PUBLISHED_2010`). Σ `FACTOR` over all dwellings is 28,696,180 and over
the emigrants 1,112,273.

## Structural checks (all 32 states, `wsl`)

Every check passes in every state (`tests/test_cpv.py::test_cpv2010_data_checks_by_state`;
the full run is `wsl:~/mxcensus/check_2010.log`):
- `ENT` equals the file's state in all three tables.
- `ID_VIV`, `ID_PER` and `ID_MIN` are unique, and `(ID_VIV, NUMPER)` is unique.
- Every person's and every emigrant's dwelling exists, and every dwelling has people.
- `NUMPERS` equals the dwelling's person records.
- `FACTOR` is constant within the dwelling, for persons and emigrants alike, and so is
  `CLAVIVP` (it is repeated in every table).
- The dwellings with `MCONMIG = 1` are exactly those with emigrant records, and each has
  `MNUMPERS` of them.

## Keys and harmonization (`cpv.py`)

- **Raw keys stay verbatim.** The person index is `(ID_VIV, ID_PER)` and the emigrant index
  `(ID_VIV, ID_MIN)`, both unique within a state. A keyed loader refuses several 2010
  states without `harmonize=True` (`_STATE_SCOPED_KEYS`), because the serials repeat across
  states; `load_cpv(table=…)` (unindexed) still concatenates them.
- **`harmonize=True` builds national, nested keys** (`_national_keys`), the same shape as
  2020's:
  - `ID_VIV` = entity + the serial zero-padded to 10 (12 digits);
  - `ID_PERSONA` = `ID_VIV` + the 5-digit `NUMPER` (17);
  - `ID_MII` = `ID_VIV` + the emigrant's 2-digit rank in the dwelling by `ID_MIN` (14).

  The new keys are inserted after `ID_PER`/`ID_MIN`, which are kept. The step is idempotent
  and runs only for an edition with state-scoped keys; `_harmonize` now takes the frame's
  `periods`, taken from its schema group.
- **Core edition scope `Periodos`** (new optional key):
  - The core `CLAVIVP` covers 2015–2025 only, so 2010's `CLAVIVP` keeps its FD entry, is
    not padded and is not checked against the core.
  - It applies in `_in_scope(meta, table, periods)`, `variables_cpv_labels`,
    `_latest_schema(table, periods)`, `_CODE_PAD` and `--variables`.
  - Every other core entry (`SEXO`, `EDAD` — written `000`…`130` — `FACTOR`, `LOC50K`,
    `ESTRATO`, `UPM`, geography) has the same codes in 2010.
- **No `TAM_LOC` → `TAMLOC` rename**: the scales differ (4 vs 5 classes), contrary to the
  plan. No `ID_PER`/`ID_MIN` renames either: they are rebuilt.
- `_POINTERS` += `IDMADRE`, `IDPADRE`, `IDCONYUGE` (01–98; 88 "lives elsewhere" is a
  separate `…C` column) and `NUMINF` (the informant). `_DIGIT_CODES` += `ID_PER`, `ID_MIN`.

## Metadata (`wsl`, in order)

`--dictionary --periods 2010` (FD, catalogs, DDI 71 and the ITER/AGEB indicator
dictionaries), then `--schema-map`, `--report-only`, deleting the stale
`variables_cpv_{viviendas,personas,migrantes}_g0*.yaml`, `--variables` (4 min 13 s) and
`--validate --jobs 16` (95 s).

- **Indicator dictionaries**: `_INDICATOR_DICT_RE` also matches any CSV under a
  `diccionario_de_datos/` folder (2010's `fd_iter_cpv2010.csv`).
- **The gids shift again** (17 groups):

  | table | 2010 | 2015 | 2020 | 2025 |
  |---|---|---|---|---|
  | viviendas | g01 (31 states), g02 (state 15) | g03 | g04 | g05 (latest) |
  | personas | g01, g02 | g03 | g04 | g05 |
  | migrantes | g01, g02 | — | g03 | g04 |

- **Validation**: **0/417 failing**.

## Tests

`tests/test_cpv.py` adds:
- a synthetic DBF writer (`_dbf_bytes`), covering:
  - padding trimmed both ways, blanks, deleted records, path vs bytes input;
  - cp1252 vs cp850 sniffing against the driver byte, ASCII, and the tie-break;
  - errors: truncated file, duplicate names, widths ≠ record length, a short header;
- `read_catalogs` with DBF members (a cp850 municipality catalog, a skipped reference
  table);
- a synthetic 2010-layout FD with no `Tipo` column (`_quantity` cases, the `b` blank row,
  `Tc_` refs, an unresolved reference table);
- the 2010 build plan and schema groups (the state-15 group), and core `Periodos` scope;
- national keys (values, nesting, idempotence, `CLAVIVP` unpadded) and the multi-state
  guard;
- planted rejections in the 2010 schemas (19 rule types);
- `_REAL` tests:
  - state-01 raw/labelled/harmonized loads (raw `(ID_VIV, ID_PER)` index; harmonized
    12/17/14-digit keys; 2010's own `CLAVIVP`/`TAM_LOC` labels; 2010 + 2020 stacked);
  - the real FD + catalogs;
  - per-state published totals and structural checks;
  - the national totals on `wsl`.

Existing tests no longer hard-code a gid: the pointer test accepts 2010's numeric
(`[1, 98]`, `[0, 99]`) and string (`NUMPER`) pointers, and the core-contract test checks
`Periodos`. `test_build_cli_guards` now uses 2005 as the disabled edition (with 2010
enabled it ran a real build).

Results: Mac full suite **886 passed, 4 skipped** in 7 min 19 s (the skips are the three
32-state national checks and one pre-existing skip; the 4 warnings are the pre-existing
DENUE/ENOE ones). `wsl` CPV/schema/CLI tests over all 32 states of 2010, 2015, 2020 and 2025:
**619 passed** in 32 min 54 s (`wsl:~/mxcensus/pytest_3b.log`).

## Findings for 3c

- **The 2010 ITER/AGEB CSVs fail to convert**: the header is `﻿"entidad",…` (a BOM
  before a quoted name). `_read_header` strips the BOM *after* `csv.reader` has kept the
  quotes, so the parsed names differ from the header. Fix the header read (strip the BOM
  first), then build them: they are lower-case, UTF-8 with a BOM, and their dictionaries are
  cp1252 `fd_*.csv` with odd trailing characters in some mnemonics (`vph_pc\xa0`).
- 2010 ITER has 200 columns and 2020 has 286; 185 names are shared. The rest are changed
  concepts (2010 `PRES2005*`/2020 `PRES2015*`; the disability block `PCON_LIM…` vs
  `PCON_DISC…`; `TAM_LOC` vs `TAMLOC`, both 14 classes).

## Deviations from the plan

- **Stdlib DBF reader instead of `dbfread`** (no new dependency; consistent with the
  xlsx/xls choices; the user was asleep and had asked for no installs).
- **National keys rebuilt, not renamed**: `ID_PER`/`ID_MIN` → derived `ID_PERSONA`/
  `ID_MII`. The plan assumed simple renames, but 2010's keys are state-scoped serials.
- **No `TAM_LOC` → `TAMLOC` rename** (different scale).
- **Core `Periodos`**: a new optional key, needed because `CLAVIVP` means different things
  in 2010.
- **The 2010 ITER/AGEB are not built yet** (3c), although `_ENABLED` includes 2010: build
  2010 with `--tables viviendas personas migrantes` until 3c fixes the CSV header read.

## Process

The user went to sleep mid-session and asked for work to continue through all phases
without their input. They then allowed pushes and HF uploads (not package installs). So 3b
was committed and pushed without a per-unit go-ahead. As in 3a, the files were `scp`'d to
`wsl`, the metadata ran there, and the generated files came back (checksums equal). `wsl`'s
HEAD was moved to the pushed 3a commit with `git reset` (mixed, tree untouched), so its
`git status` shows exactly 3b's changes.

Logs on `wsl:~/mxcensus`: `build_cpv_2010.log`, `check_2010.log`, `validate_3b.log`,
`pytest_3b.log`.
