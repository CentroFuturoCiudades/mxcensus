# CPV Unit 5b — 1990 + 1995 samples, MG 1995

Done **2026-10-08** (overnight, unattended, on the Mac). The files are built and validated;
like 3a–5a they wait for `wsl` to be registered and uploaded.

Gate: `--validate` 0 with the 1990/1995 microdata — ✅ **0/897** (every CPV file,
1990–2025). MG 1995 is built. Uploaded: pending (`HANDOFF.md` §Release batch).

## The tables, after a probe

**Conteo 1995**:
- **`datgen95` is a person file**, not the household record unit 0 assumed. There are
  ~4.8 rows per household, `P3_1` numbers the persons (01, 02…), and the dwelling items
  `P1_*` and household items `P2_*` repeat on each person.
- **Weights**: `FAC_POB` varies by person; `FAC_VIV` is constant per dwelling.
- **Mapping**: `datgen95` → `personas` (catalog member and tests fixed); `migint95` →
  `migrantes`.

**CGPV 1990**: one flat person file (`m_10NN.dbf`) → `personas`, the 10% extract with the
dwelling items on each person, unweighted.

**Build** (`--periods 1990 1995 --tables personas migrantes`): 96 files in a few minutes
(downloads included), all ASCII, 0 failed.

| edition | table | rows | columns | size |
|---|---|---|---|---|
| 1990 | `personas` | 8,118,242 | 53 | 82 MB |
| 1995 | `personas` | 332,061 | 105 | 7 MB |
| 1995 | `migrantes` | 7,272 | 23 | 0.2 MB |

## Keys (`cpv._composite_keys`, two more specs)

- **Conteo 1995**: probed in all 32 states.
  - Dwelling = `ENT`+`MUN`+`ZONA`+`UPM`+`VIV` (VIV padded to 3, so 12 digits); `FAC_VIV`
    is constant within it.
  - Household = `HOGAR` (`ID_HOG`, 14 digits).
  - Person = `P3_1` (`ID_PERSONA`, 16).
  - Emigrant = `P9_1` (`ID_MII`, 16).
  - All are unique, and every emigrant's household is in the person file.
- **CGPV 1990**: dwelling = `ENT` + `FOLIO_VIV`, person = `NUM_PER`, no household level.
  - **Reused folios**: 729 of 8.1 million rows repeat (ENT, FOLIO_VIV, NUM_PER), because
    INEGI reused a few folios within a state and duplicated some rows exactly (177).
    Persons are listed dwelling by dwelling, **but not in `NUM_PER` order**. A first rule
    ("a new dwelling where `NUM_PER` drops") split 61,460 rows of one state wrongly and was
    replaced.
  - **The rule** (`_folio_occurrence`): a dwelling is a run of one folio, split where a
    person number repeats within the run. A folio's dwellings are numbered in file order,
    also when it comes back later in the file. `ID_VIV` = entity + folio padded to 9 + that
    occurrence (12 digits); `ID_PERSONA` = `ID_VIV` + `NUM_PER` (16).
  - **Result**: unique in all 32 states; 643 rows sit in a reused folio's second or later
    dwelling.
  - **Check**: of 1,618,617 derived dwellings, one has inconsistent dwelling items, and
    99.98% list exactly `NUM_PERS` persons.
- `load_cpv_survey(1990|1995)` returns `None` for the dwelling table (neither edition has
  one). Personas are indexed `(ID_VIV, ID_PERSONA)` (1990) or
  `(ID_VIV, ID_HOG, ID_PERSONA)` (1995), emigrants `(ID_VIV, ID_HOG, ID_MII)`.

## Weights

- **1995** has three estimators: `FAC_POB` (persons, except health coverage and
  disability), `FAC_VIV` (dwellings and households) and `FAC_PROM` (coverage and
  disability). All three join `cpv._WEIGHTS` (numeric in raw validation and in the
  loaders); they are not renamed onto `FACTOR`.
- **The sums are close to the 1995 ITER, not equal** (pinned as regression values):

  | sum | value | 1995 ITER |
  |---|---|---|
  | Σ `FAC_POB` | 90,728,652 | `POBTOTAL` 90,638,604 |
  | Σ `FAC_VIV`, dwellings | 19,361,472 | `VIV_PART` 19,272,550 |
  | Σ `FAC_PROM` | 91,052,274 | — |
- **1990** is unweighted (a 10% extract: 8,118,242 rows for 81.2 million).

## Dictionaries (`_dict_fd`, PDFs read with poppler)

Both FDs are encrypted PDFs; `_dict_fd.pdf_text` runs `pdftotext -layout`.
`build_cpv._fd_docs` picks the parser from `_FD_PDF_PARSERS`.
- **`parse_fd_1990_text`** (`fd_cgpv1990.pdf`):
  - **Variable table**: number, mnemonic, description, length, range (`01..05 Y 09` →
    `{01..05,09}`, `1Y2`, `VER CATÁLOGO`; a range wrapped onto the next line is rejoined).
  - **Code sections**: one per variable number; the first code may share the section line
    (`12 TAM_DUERME 0 NO DISPONE DE COCINA`); wrapped labels are rejoined. A section naming
    a catalog (`(CATPAREN)`) points at that sheet of `catalogos_1990.xls`.
  - **The end**: parsing stops at «ESTRUCTURAS DE CATALOGOS». The minimum-wage annex after
    it lists states by number («26 SONORA») and had leaked rows into `SEXO`.
  - **Catalogs**: the sheets of `catalogos_1990.xls` have no header row
    (`_catalog_from_rows` now reads code | label), and parentesco lists synonyms under one
    code (the first label wins). `CATMUN00` has a header without a name column and stays
    out: `MUN` is a code string.
  - **Fix**: the FD's `ACT_PRI` is the data's `ACT_PRIN` (`_FD_RENAMES`).
- **`parse_fd_1995_text`** (`fd_encuesta_cpv1995.pdf`):
  - **Variable lines**: field, `{range}`, length and two file positions.
  - **Descriptions** may begin on the line(s) above; an indented one takes the group title
    above it («TIEMPO RESIDENCIA ANTERIOR — MESES»); a missing one repeats the previous
    («FACTORES DE EXPANSION»).
  - **Sections**: one per DBF (`DATGEN95` → `personas`, `MIGINT95` → `migrantes`).
  - **Catalogs**: 1995's are a PDF and are not read.
- **Rules for FDs without `Tipo`** (`_quantity`; they apply to 2010 too):
  - rows that list only sentinels above the one header range make a count (1990
    `ANO_CUMP` `{000..120,999}`);
  - a range row labelled «Ver catálogo» is a code space (1995 `ZONA` 01..05 + 40/50/60);
  - «98 años o más» is a top-code value (`_TOPCODE_RE`, only for a label that starts with
    its number: 2020's `EDAD_MORIR_TD` «De un año o más» stays a category).
- **Range reconciliation** (`build_cpv._reconcile_ranges`, editions in
  `_RANGES_FROM_DATA` = 1990, 1995): the old FDs leave values out of their ranges. In
  `--variables`, a numeric entry's range is extended down to an observed value below it
  (0 = none: years of technical studies, rooms, income); an observed all-nines value above
  it becomes an undocumented sentinel (`N_F_GPOS` 99); anything else above extends the
  range up. Each change is noted. The first `--validate` had failed all 64 files on
  exactly these values.
- **Byte-identity**: 2010–2025 parse the same (JSON dump). The 2000/2005 dictionaries are
  unchanged.
- **Known limit**: 1990 `INGRESO` stays a code string. Its single zero-padded range
  `00000000..99999999` reads as a code space, with the sentinels inside it.

**Core**: `SEXO` `Recodificar` += 1990 (2 → 3); 1995's sex is `P3_5` (its own FD entry,
Hombre/Mujer).

**Schema map** (32 groups):
- `personas`: 1990 `g01`, 1995 `g02`, 2000 `g03`, 2005 `g04`, 2010 `g05`/`g06`, 2015
  `g07`, 2020 `g08`, 2025 `g09`;
- `migrantes`: 1995 `g01`, 2000 `g02`, 2010 `g03`/`g04`, 2020 `g05`, 2025 `g06`.

All other dictionaries are unchanged under their gids, apart from `SEXO`'s description.

## MG 1995

`build_marco_geo.py --period 1995 --no-registry`: `Entidades_1995`/`Municipios_1995` (with
`.prj`, LCC) → 64 files, 43 MB.
- **Municipalities**: 2,428, **15 more than the 1995 ITER (2,413), all in Chiapas (07)**;
  every ITER municipality is in the MG.
- 1990 has no frame (`mg_period=None`).

## Tests

`tests/test_cpv.py` (unit-5b section):
- the 1990 FD text (variable table, inline first code, catalog pointers, the annex cut-off,
  the range header);
- the 1995 FD text (wrapped and grouped descriptions, the factors, `ZONA` as codes, the
  `98 años o más` top-code, the migrant section);
- the headerless synonym catalogs;
- `_reconcile_ranges`;
- `_folio_occurrence` (unsorted persons, a folio reused in one run and later in the file)
  and the 1990 keys, raw = harmonized, with `SEXO` recoded;
- the 1995 keys and weights;
- the schema groups (the 2000/2005 test's gids moved);
- real data: `load_cpv_survey(1990|1995, state=1)` (shapes, indices, emigrants under their
  households, labels, weights);
- the 32-state check: unique keys, the 1990 row count, the 1995 weight sums.

`tests/test_mg.py`: MG 1995 in the municipal-frames test (renamed
`test_real_mg_municipal_frames`).

Results: `test_cpv.py`, `test_cpv_aggregates.py`, `test_cli.py`, `test_schema_groups.py`, `test_mg.py` and `test_census_legacy.py` over all 32 states of every edition: **942 passed, 1 skipped** (22 min). The one failure, 4a's `test_scoped_entry_recodificar` (`SEXO`'s `Recodificar` now includes 1990), was updated and re-run.

## Deviations from the plan

- 1995's `datgen95` is `personas`, not `hogares`; neither 1990 nor 1995 has a dwelling or
  household table.
- 1995's weights stay three named columns (no `FACTOR`).
- The FD ranges are reconciled with the data for 1990/1995 (`_RANGES_FROM_DATA`).
