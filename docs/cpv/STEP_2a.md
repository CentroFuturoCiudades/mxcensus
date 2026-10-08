# CPV Unit 2a — CPV 2020 into the family

Done **2026-10-07**. Gate: `build_cpv.py --validate` reports **0 failures over all 257 files**
(160 CPV 2020 + 97 EIC 2025) on `wsl` (`VALIDATION_REPORT.md`). Nothing was committed during
the unit: the code was copied to `wsl` with `scp` and the generated metadata copied back (see
§Process). Registry and upload are **2b**.

## Dictionary probe: a DDI exists, the FD workbook is used

The RNM listing (`…/rnm/index.php/api/catalog/search?ps=200&page=1..5`, 825 entries, highest
id 1151) has **id 632, `MEX-INEGI.ESD2.01-CPV-2020`**. Its codebook documents eight files:
`Viviendas`/`Personas` (cuestionario básico), `Viviendas_CA` (83 vars), `Personas_CA` (91),
`Migrantes` (26) and three alojamientos files. The three CA files list exactly the data
columns, in the same order. There is still no EIC 2025 DDI.

**The DDI is not used for the 2020 dictionaries.** It is a Nesstar export whose value labels
and types come from observed statistics, and it falls short of the FD workbook
(`diccionario_cuestionario_ampliado_cpv2020.xlsx`) on the state-01 data:

| variable | DDI 632 | FD workbook |
|---|---|---|
| `EDAD` | string; special `9` | numeric 0–130; special `999` |
| `PARENTESCO` | 2-digit `01..08`; data codes are 3-digit (`101`…) | catalog `PARENTESCO` (40 codes) + `999` |
| `IDENT_MADRE`/`IDENT_PADRE` | only `96`/`97` + `98`/`99` | `01..54` + `96`/`97`, `98`/`99` |
| `DUE1_NUM`, `JEFE_EDAD` | only `99` / `999` | full range |
| `ENT` | unpadded `1..32`; numeric | `01..32` |
| `SEXO`, most yes/no items | numeric | categorical |
| `ESCRITURAS` | no code `8` (in the data) | `8` = No sabe |
| `NUMPER`, months, years | no categories | identity spans / numeric ranges |

The FD has the same layout as EIC 2025's (`Cons. | Descripción | Mnemónico | Pregunta y
categoría | Tipo | Rango válido | Longitud`, sheets `VIVIENDAS`/`PERSONAS`/`MIGRANTES` +
`Modelo de datos`), so 2020 goes through the same `_dict_fd` path as 2025. That keeps the
two editions' entries comparable for the 2b harmonization. `CpvEdition("2020").ddi_id = 632`
is recorded and `--dictionary` fetches the codebook (`data/dict/ddi/632.xml`) for reference;
nothing reads it.

## `scripts/_dict_fd.py` — what 2020 needed

All changes are generic. The 2025 parse (catalogs, FD workbook, indicator CSV) was dumped
before and after and is **byte-identical**.

- **`read_catalogs`**: the 2020 catalog ZIP (`Censo2020_clasificaciones_CPV_csv.zip`, 12
  CSVs) is **cp1252**, so decoding falls back from UTF-8. `ENT.csv`/`MUN.csv` have
  `CVE_*,NOM_*` headers and no `DESC*` column, so the label is the last `NOM*` column when
  there is no `DESC*`. (`MUN.csv` spells the entity with 3 digits: `001001`.)
- **`match_catalog`**: the 2020 stems abbreviate (`MUN`, `ENT_PAIS`, `CAUSA_MIG`, `INALI`,
  `RELIGION` for «Religiones», `ESCOACUM` for «Escolaridad»), so no word matched exactly.
  A phrase word now matches a stem word when they are equal, when one is a ≥3-letter
  abbreviation of the other, or when they share a ≥4-letter prefix (`_word_match`).
  Punctuation separates words (`(INALI`).
- **`_CATALOG_RE`** allows line breaks (`Según Clasificador\nde Parentescos`).
- **`_parse_code`** strips braces in code rows (`{0001..9999}`, `{000001..999997}`) and
  reads `...`/`…` as a range (`01001000000100001 ... 32058999999999954`).
  **`_split_codes`** splits a cell listing several codes (`1101..2901,3101,\n3102`).
- A **catalog note in a code row** (`ESCOACUM`: `(Según Clasificador de Escolaridad)`) names
  the catalog. A numeric variable whose code rows hold no range takes its range from the
  header (`{0…24, 99}` → `Rango [0, 24]`).
- A **single code that a catalog enumerates** keeps the catalog's label (`3101`), not the
  row's generic «Clave de religión».
- **`parse_indicator_csv(path, specials=None)`**: `specials` are the cell codes an edition
  uses without footnoting them; a footnote's label wins. The range split accepts INEGI's
  typo `0.,.999999999` (`P_0A2_F`), so that column is numeric like its siblings.

Result: every 2020 FD variable matches the state-01 codes. The only mismatches left are
core-owned keys and the `MUN_*` columns, whose 2,502-row catalog makes them string codes
with a 3-digit width check.

## Build

`_ENABLED = ("2020", "2025")`. Dry run and smoke build of state 01 on the Mac: 5 files in
under a second from the cached ZIPs, all UTF-8.

**Full build on `wsl`** (`--periods 2020 --retries 6`, log `wsl:~/mxcensus/build_cpv_2020.log`):
- all 96 ZIPs (738 MB) were already cached by the legacy builder under the same INEGI
  basenames, so nothing was downloaded;
- **160 files written, 0 failed**, in 2 min 20 s, peak RSS 1.8 GB;
- 620 MB of parquet (viviendas 57, personas 252, migrantes 1.4, iter 50, ageb 259 MB);
- 159 files are UTF-8. `cpv_ageb_2020_14` is **cp1252**; its names equal the legacy
  `resargebub_14` and hold no U+FFFD.
- The state-01 files are byte-identical on both hosts.

| state | viviendas | personas | migrantes | iter | ageb |
|---|---|---|---|---|---|
| 01 | 24,349 | 95,983 | 1,563 | 2,058 | 16,376 |
| 02 | 24,017 | 79,047 | 598 | 5,566 | 57,152 |
| 03 | 14,056 | 46,248 | 136 | 2,561 | 18,105 |
| 04 | 23,443 | 85,111 | 262 | 2,800 | 11,840 |
| 05 | 63,817 | 221,346 | 1,259 | 4,149 | 61,056 |
| 06 | 18,407 | 61,125 | 686 | 1,259 | 14,742 |
| 07 | 288,495 | 1,270,527 | 3,764 | 21,487 | 55,369 |
| 08 | 95,725 | 312,925 | 2,547 | 12,389 | 82,131 |
| 09 | 81,527 | 276,007 | 1,318 | 666 | 68,941 |
| 10 | 66,337 | 255,524 | 2,673 | 6,006 | 35,728 |
| 11 | 108,625 | 419,018 | 5,346 | 8,945 | 70,123 |
| 12 | 185,533 | 738,095 | 8,822 | 7,001 | 58,932 |
| 13 | 137,974 | 503,228 | 5,542 | 4,916 | 42,088 |
| 14 | 216,458 | 786,354 | 8,883 | 10,715 | 108,041 |
| 15 | 316,843 | 1,228,485 | 4,305 | 5,136 | 142,214 |
| 16 | 189,761 | 710,181 | 9,534 | 8,956 | 72,355 |
| 17 | 67,035 | 240,423 | 1,693 | 1,678 | 28,824 |
| 18 | 48,560 | 183,780 | 1,764 | 2,913 | 20,821 |
| 19 | 98,315 | 336,666 | 1,575 | 4,974 | 79,916 |
| 20 | 524,900 | 1,938,379 | 23,759 | 11,856 | 72,465 |
| 21 | 322,547 | 1,280,682 | 7,312 | 7,059 | 76,085 |
| 22 | 39,379 | 148,019 | 2,104 | 2,249 | 29,818 |
| 23 | 22,912 | 77,922 | 200 | 2,243 | 26,915 |
| 24 | 96,920 | 361,548 | 4,671 | 6,729 | 39,186 |
| 25 | 46,845 | 165,993 | 1,152 | 5,552 | 48,443 |
| 26 | 79,835 | 263,386 | 2,093 | 7,500 | 71,015 |
| 27 | 44,149 | 156,236 | 371 | 2,517 | 17,786 |
| 28 | 77,616 | 249,967 | 1,832 | 6,695 | 67,254 |
| 29 | 86,142 | 346,580 | 1,465 | 1,323 | 17,842 |
| 30 | 396,260 | 1,406,223 | 7,022 | 20,401 | 97,957 |
| 31 | 128,971 | 475,312 | 904 | 2,691 | 40,140 |
| 32 | 80,874 | 295,363 | 4,944 | 4,669 | 33,844 |
| **total** | **4,016,627** | **15,015,683** | **120,099** | **195,659** | **1,683,504** |

National Σ `FACTOR`: personas **125,515,554**, viviendas **34,987,915**, migrantes
**802,807**. The CA sample expands to the population of inhabited private dwellings, not
the census total (`POBTOT` 126,014,024), as the legacy state-01 pins show (1,421,198 vs
1,425,607).

## Structural checks (all 32 states, read-only scan on `wsl`)

Every check passes in every state:

- `ENT` equals the file's state in all three microdata tables, and so does `ID_VIV[:2]`.
- Widths are `ID_VIV` 12, `ID_PERSONA` 17 and `ID_MII` 14, the same as 2025.
- Keys are unique per table. `ID_PERSONA[:12] == ID_VIV` and `ID_MII[:12] == ID_VIV`.
- Every person's and every migrant's dwelling exists, and every dwelling has people.
- `FACTOR` is constant within a dwelling, for persons and migrants alike. Its maximum is
  1,407, well inside the core `Rango [1, 99999]`.
- There is one `COBERTURA` per municipality.
- Migrants match the declarations: the dwellings with `MCONMIG = 1` are exactly those
  declaring `MNUMPERS`, and each has that many migrant records.
- **Legacy files**: per state, the row counts and Σ `FACTOR` of `cpv_{viviendas,personas}_2020_NN`
  equal the legacy `viviendas_NN`/`personas_NN`, and the ITER/AGEB row counts equal
  `iter_NN`/`resargebub_NN`. On state 01, every value of the viviendas and personas files
  equals the legacy file after numeric casting. The full legacy-equality test is 2b.

## Aggregates: sentinel codes

The 2020 ITER/AGEB indicator dictionaries (`diccionario_datos_iter_01CSV20.csv`,
`…ageb_urbana_01_cpv2020.csv`) are **identical in all 32 state ZIPs** (md5) and have **no
footnotes**. The non-numeric cells, counted over all 32 states:

| code | ITER cells | AGEB cells | meaning |
|---|---|---|---|
| `*` | 22,391,823 | 78,654,323 | counts reserved for a locality/block with one or two inhabited dwellings; also the `TAMLOC` of ITER total rows |
| `N/D` | 41,192 | 134,757 | every indicator but the population/dwelling totals of 152 localities / 621 blocks |
| `N/A` | 425 | 1,102 | `REL_H_M`/`PROM_HNV` with a zero denominator |

These are declared in `build_cpv._AGG_SPECIALS["2020"]` and passed as `specials=`. Some ITER
counts are left-padded with spaces (`'        986'`, `POB_AFRO*`); they stay verbatim, and
the numeric checks and labelling strip them. `LONGITUD`/`LATITUD`/`ALTITUD` are `Caracter`
(degree strings), null on total rows.

## Metadata (`wsl`, in order)

`--dictionary --periods 2020` (FD, catalogs, DDI 632, the two indicator CSVs), then
`--schema-map`, `--report-only`, `--variables` (153 s) and `--validate --jobs 16` (63 s).

- **Schema map**: 9 groups. One fingerprint per table in 2020. Gids are chronological, so
  **2020 = `g01` and 2025 = `g02`** for viviendas/personas/migrantes, with `latest` = `g02`.
  ITER/AGEB have `g01` (2020) and estimaciones `g01` (2025). The 2025 fingerprints and
  columns are unchanged.
- **Dictionaries**: every column is sourced from the core or INEGI's dictionary; there are
  no `data`-only entries.

  | group | core | fd |
  |---|---|---|
  | viviendas/g01 | 8 | 75 |
  | personas/g01 | 11 | 80 |
  | migrantes/g01 | 9 | 17 |
  | iter/g01 | 0 | 286 |
  | ageb/g01 | 0 | 230 |

  The 2025 groups' YAML (now `g02`) differs from the old `g01` only by the core
  description edits and the `Tablas` key.
- **Drift 2020 → 2025** (`INCONSISTENCY_REPORT.md`):
  - viviendas: +`CVEGEO`/`CVE_ENT`/`CVE_MUN`/`TIPO_REG` and the 2025 food-security/
    displacement items; −`ENT`/`MUN`, `FOCOS`, `FOCOS_AHORRA`, `DEUDA`, `USOEXC`,
    `CON_VJUEGOS`, `SERV_PEL_PAGA`, `ING_ALIM_ADL3`.
  - personas: +`CVEGEO`/`CVE_ENT`/`CVE_MUN`/`TIPO_REG`, `CAUSA_MIG_C`, `COND_MENTAL_*`,
    `DHSERSAL_ACCESO`, `SM`; −`ENT`/`MUN`, `RELIGION`, `NOMCAR_C`, `REGIS_NAC`,
    `CAUSA_MIG_V`, `IDENT_HIJO`, `EDAD_MORIR_TD`.
  - migrantes: only `ENT`/`MUN` → `CVEGEO`/`CVE_ENT`/`CVE_MUN`.
- **Validation**: **0/257 failing**.

  | table | g01 (2020) rows | g02 (2025) rows |
  |---|---|---|
  | viviendas | 4,016,627 | 7,340,046 |
  | personas | 15,015,683 | 25,222,336 |
  | migrantes | 120,099 | 362,679 |
  | iter | 195,659 | — |
  | ageb | 1,683,504 | — |

## Core and package changes

- **`variables_cpv_core.yaml`**:
  - Verified for 2020: every core entry a 2020 table carries (`LOC50K`, `ID_*`, `COBERTURA`,
    `ESTRATO`, `UPM`, `FACTOR`, `CLAVIVP`, `SEXO`, `EDAD`, `TAMLOC`) has the same codes, and
    `--validate` confirms it.
  - Descriptions now name both editions; `ESTRATO` is 14 characters in 2020 and 15 in 2025.
  - **New optional key `Tablas`** (documented in the header): the tables an entry applies
    to. `TAMLOC` is scoped to the microdata, because the ITER's `TAMLOC` is a different
    14-class scale (`01..14`, written unpadded, `*` on total rows) and keeps its indicator
    entry.
- **`cpv.py`**:
  - `_in_scope`/`_core_for` apply `Tablas` in `variables_cpv_labels` and `_latest_schema`;
    the build uses the same `_in_scope`.
  - Digit-code checks cover the 2020 raw geography `ENT`, `MUN`, `ENTIDAD`, `LOC` and `MZA`.
  - `_CODE_REGEX` gives `AGEB` the shape `^\d{3}[0-9A-P]$`.
  - The 2020 geography joins `_GEO_CODES`, so it is `_SKIP`ped and stays a raw string under
    `labels=True`.
  - `_filter_states` also reads `ENTIDAD`.
- **`_cpv_catalog`**: 2020 `ddi_id=632` and a note about the dictionary source.
- **README**: the `variables_cpv(...)` examples use `g02` (EIC 2025). **CLAUDE.md**: CPV
  status and the module/YAML rows.

`load_cpv(table="iter"|"ageb", state=N)` now works (`latest_edition` → 2020), raw or
labelled. Labelled, the counts are `Int64` with `*`/`N/D`/`N/A` → NA, the ratios Float64,
and `TAMLOC` and the names stay strings. The ITER/AGEB level splitting and imputation are
3c.

## Tests

`tests/test_cpv.py` adds:
- the 2020 FD code cells, abbreviated catalog stems (and the 2025 ones still resolving),
  cp1252/`NOM_*` catalogs, and a synthetic 2020-layout workbook (wrapped note, multi-code
  cell, catalog-note row, braces);
- `parse_indicator_csv(specials=)` with the range typo and footnote precedence;
- the 2020 build plan (96 ZIPs → 160 files), the gid order, and the core scope;
- planted rejections in the 2020 schemas (15 rule types, incl. `PARENTESCO=102`,
  `ESCOACUM=25`, `MUN_ASI=1`, `AGEB=01Z1`, `REL_H_M=N/E`) and the sentinels accepted;
- `_REAL` 2020 state-01 loads:
  - microdata: raw shape; labelled survey lengths, key nesting, `FACTOR` constant in the
    dwelling, Σ `FACTOR` = legacy pins, the labels;
  - ITER/AGEB: shapes, state `POBTOT` 1,425,607, `*` → NA.

Existing tests now take gids from the map or loop over every group, instead of hard-coding
`g01`.

Results: Mac full suite **781 passed, 2 skipped** in 6 min 54 s (the 4 warnings are the
pre-existing DENUE/ENOE ones). `wsl` CPV/schema/CLI tests: **235 passed** in 8 min,
including all 32 states of 2025 and the national check.

## Findings for 2b

- **Harmonize**: microdata `ENT`→`CVE_ENT` and `MUN`→`CVE_MUN`, deriving `CVEGEO`; 2020 has
  no `CVEGEO`. The aggregates spell `ENTIDAD`/`MUN`/`LOC`, so the rename needs a table scope:
  `ENTIDAD`→`CVE_ENT` in ITER/AGEB, and `MUN` means `CVE_MUN` in every table. Today a 2020
  frame with `harmonize=True` warns `lacks core column(s) ['CVE_ENT']`; that is expected
  until 2b.
- **Cross-edition labels**: `_labels_for` drops a column documented differently in two
  groups and compares whole entries. Between 2020 and 2025, 48/74 viviendas, 52/83 personas
  and 12/24 migrantes shared columns differ somewhere (mostly `Descripción`/`Pregunta`
  wording). Only 7/22/5 differ in the label-relevant keys (`Tipo`, `Categorías`,
  `Especiales`, `Rango`, …). 2b should compare only those keys, or accept fewer labelled
  columns in mixed frames.
- **Legacy equality**: already true value-for-value on state 01 microdata after casting.
- **ITER `TAMLOC`** could be labelled from the ZIP's `catalogos/tam_loc.csv.csv` (14
  classes); left as a string for 3c.

## Deviations from the plan

- **The DDI exists but is not used** (above). The plan and handoff said "RNM DDI if one
  exists". The FD workbook was chosen on the evidence; the decision is the user's to revisit.
- **Core `Tablas`**: a new optional entry key, needed because a core variable name
  (`TAMLOC`) means different things in two tables.
- **Aggregate specials** come from `_AGG_SPECIALS` (observed codes) rather than dictionary
  footnotes, because the 2020 dictionaries have none.

## Process

Commits and pushes wait for the user. So instead of committing mid-unit (as 1a/1b did), the
changed files were `scp`'d to `wsl:~/mxcensus` (working tree now dirty). The metadata ran
there and the generated files were `scp`'d back. **Before pulling on `wsl` after the
commit**, discard the copies there. The five new YAMLs are untracked on `wsl`, so a pull
would refuse to overwrite them:

```bash
git checkout -- .
rm src/mxcensus/_yaml/variables_cpv_{viviendas,personas,migrantes}_g02.yaml \
   src/mxcensus/_yaml/variables_cpv_{iter,ageb}_g01.yaml
git pull --ff-only
```

They are identical to the committed ones.
