# CPV Unit 4a — CGPV 2000 + Conteo 2005 microdata

Done **2026-10-08** (overnight, unattended), entirely on the **Mac**. `wsl` was unreachable
(Tailscale SSH asks for an interactive re-login, see `HANDOFF.md`), so the Mac now holds
the whole CPV mirror: 2020/2025 from the HF bucket (sha-verified), 2010/2015 rebuilt from
INEGI, and 2000/2005 built here.

Gate: **`--validate` 0 failures** — ✅ **0/673** (every CPV file of 2000–2025).

## Build

`_ENABLED` += `2000`, `2005`. Both are DBF editions, read by the stdlib `scripts/_dbf.py`
(unit 3b). The CLI guard test now uses 1995.

- **192 files, 0 failed**, in 30 s with the ZIPs already cached. Peak RSS was 1.4 GB.
- Every table is plain ASCII, with no deleted records.

| edition | table | member | rows | columns |
|---|---|---|---|---|
| CGPV 2000 | `viviendas` | `VHO_F{NN}.DBF` (one row per **household**) | 2,312,035 | 52 |
| | `personas` | `PER_F{NN}.DBF` | 10,099,182 | 81 |
| | `migrantes` | `MIN_F{NN}.DBF` | 195,701 | 19 |
| Conteo 2005 | `viviendas` | `trvmue{NN}.DBF` | 2,470,678 | 24 |
| | `hogares` | `trhmue{NN}.DBF` | 2,546,879 | 7 |
| | `personas` | `trpmue{NN}.DBF` | 10,282,760 | 32 |

Size: 171 MB (2000) and 93 MB (2005).

## Dictionaries

`--dictionary --periods 2000 2005` fetches both editions' sources into `data/dict/fd/`.
The DDI codebooks 141 and 140 are fetched for reference only.

**Conteo 2005** has `fd_muestra_2005.xls` and `catalogos_muestra_2005.xls`, both legacy
BIFF8 files read by `_dict_fd.read_xls`.
- **The FD's three sheets** (`FD VIVIENDAS`, `FD HOGAR`, `FD PERSONAS`; `_FD_SHEET_TABLE`)
  use a *split* layout. The variable's name, the mnemonic's definition (→ `Definición`),
  the valid ranges, the code and its label, the data mnemonic and the catalog each have
  their own column (`_FD_HEADERS`). Code rows continue under the variable row.
- **The catalogs** are one workbook with a sheet per catalog (`TC_ENTID`, `TC_PAREN`, …),
  keyed by the columns before `DESC` (`read_catalogs` on an `.xls`; the `lead_keys`
  fallback is scoped to this workbook, so 2010's reference tables stay excluded).
- **Labels**: the catalogs are in capitals. Where an FD row labels the same code with the
  same words, the FD's spelling wins (`CASA INDEPENDIENTE` → «Casa independiente»).
  2010–2025 are unaffected.
- **One FD misspelling**: `TOPERHOG` for the data's `TOTPEHOG` (`build_cpv._FD_RENAMES`).

**CGPV 2000** has no spreadsheet. Its FD is an annex of `fd_muestra_censal_2000.pdf`
(inside `fd_muestra_censal_2000_pdf.zip`), parsed from `pypdf`'s text by the new
`_dict_fd.parse_fd_pdf` / `parse_fd_text`.
- It finds the sections «Descripción de las variables de explotación del archivo de …
  (VIVHOG | PER | MIN)», each listing variables as `num  description  [question]  MNEMONIC
  {ranges}  length`, then indented code rows.
- The text extraction wraps freely. Handled cases:
  - a mnemonic split over two lines (`DOTAGUA` / `D`);
  - a header over up to 12 lines (`NOMCAR_C`: the question number and the length each on
    their own line);
  - the length column landing inside a wrapped range list (`OTROPARE_C {100,…,430, 3` /
    `440,…,999}`);
  - dash ranges (`001-032`);
  - wrapped labels, and all-capitals section titles that must not join a label.
- **Result**: 52 / 81 / 19 variables, exactly the data's columns, except the FD's `TIPHOG`
  for the data's `TIPOHOG` (`_FD_RENAMES`). The one observed code the FD does not list is
  `ABANESCO` `8`; it is appended from the data with a `Nota`, as usual.
- **Not used**: the sample-design PDF next to it (`diseno_muestra.pdf`) is AES-encrypted.
  `pypdf` would need `cryptography`, and no packages were installed. The FD annex has the
  same estimator description (§Weights).

**Rules for FDs without a `Tipo` column** (`_quantity`; they apply to 2010 too):
- **Code lists**: several labelled ranges, or a header with several ranges, make a code
  list. Examples: `LNACEDO_C` (001-032 entidad / 100-535 país), `OTROPARE_C`, `NOMCAR_C`.
- **Values**: a single code next to the one range is a value (`FECNACA
  {1929,1930..2000,9999}`: 1929 = «1929 y antes» → `Rango [1929, 2000]`, 9999 special).
- **Header-only sentinels**: a sentinel listed only in the header becomes `Especiales`
  (`HIJFAL {00..25,99,b}`).
- **Check**: the 2010/2015/2020/2025 parses are byte-identical before and after every
  parser change (a JSON dump of all four).

## Record keys: derived from composite parts

Neither edition has a key column (probed on states 01, 09, 15 and 20, then checked on all
32 states).
- **CGPV 2000**: a dwelling is `ENT`+`MUN`+`LOC`+`NUMVIV` (`NUMVIV` restarts in every
  locality) and a household adds `NUMHOG`. `VHO_F` has one row per household; the
  dwelling items repeat (`CLAVIV`, `PAREDES`, `FACTOR` and `NUMHOGS` checked constant
  within the dwelling in states 01 and 20). **Persons are not
  numbered**: `PER_F` lists each household's members together, but not in questionnaire
  order (often not the head first). An emigrant is `MPER`, numbered within the household.
- **Conteo 2005**: a dwelling is `ENT`+`MUN`+`CONS_MUN` (a serial within the
  municipality). `CONS_VIV` is the dwelling's number in its listing, not a key. A
  household adds `CONS_HOG`, a person `CONS_PER` (numbered within the household).

`cpv._composite_keys(frame, table)` inserts the derived keys as the first columns. Every
part is zero-padded to its width, so the concatenations are unambiguous:

| key | CGPV 2000 | Conteo 2005 |
|---|---|---|
| `ID_VIV` | ENT+MUN+LOC+NUMVIV (15) | ENT+MUN+CONS_MUN padded to 7 (12) |
| `ID_HOG` | + NUMHOG to 2 (17) | + CONS_HOG to 2 (14) |
| `ID_PERSONA` | + order in the household, in file order (19) | + CONS_PER (18) |
| `ID_MII` | `ID_HOG` + MPER (19) | — (no migrant table) |

2005's dwelling serial is padded to 7 so `ID_VIV` has the 12 digits of 2010–2025. Without
it, `harmonize=True`'s `ID_VIV` padding (`_CODE_PAD`) would change a harmonized frame on
a second pass; with it the step stays idempotent (tested). In all 32 states of both
editions the keys are unique at every level, every person/emigrant/household hangs from a
parent, and every 2005 dwelling has a household.

**Where the keys are derived**:
- the keyed loaders (`_load_level`) derive them with `harmonize=False`;
- `_harmonize` derives them after the padding (from the padded `CVE_ENT`/`CVE_MUN`), so
  raw and harmonized keys are identical;
- `load_cpv` (faithful raw) never adds columns.

**The household level** (`_HOUSEHOLD_KEY_SPEC` = `ID_VIV` + `ID_HOG`):
- persons and emigrants extend it: `(ID_VIV, ID_HOG, ID_PERSONA)`;
- 2010–2025 have no `ID_HOG`, so `level_key` drops it and their indices are unchanged;
- `viviendas` uses the household spec too, so CGPV 2000's dwelling-household rows are
  indexed `(ID_VIV, ID_HOG)` and 2005's dwellings `ID_VIV`;
- `_required` does not demand `ID_HOG` outside `hogares` (`_OPTIONAL_KEYS`);
- the raw key parts (`NUMVIV`, `NUMHOG`, `CONS_*`) stay strings under `labels=True`
  (`_KEY_PARTS` ⊂ `_SKIP`).

**`load_cpv_hogares(period=None, *, state, harmonize, labels)`** is new: Conteo 2005's
household table. `load_cpv_survey` keeps its `(viviendas, personas, migrantes)` tuple:
2005's households are a separate call, and its `migrantes` is `None`. Stack 2005 with
another edition on the columns (`reset_index()`): the household level makes its index
deeper.

## Core

- **`SEXO`**: 2000 and 2005 write mujer as `2` (3 since 2010). A plain `Alias '2': '3'`
  would also let `2` through in 2010–2025, where it is invalid (a rejection test guards
  that). Instead a new core key **`Recodificar`** = `{edition: {raw: canonical}}` scopes
  the recode. `cpv._scoped_entry(meta, periods)` turns it into the entry's `Alias` for
  those editions only. It feeds `_core_for` (labels, `_latest_schema`) and
  `build_cpv --variables` (the generated 2000/2005 `SEXO` entries carry the `Alias`).
  `_harmonize` now applies an in-scope core `Alias`, so harmonized 2000/2005 `SEXO` reads
  `1`/`3`. Labelled frames read «Hombre»/«Mujer» in every edition.
- **New `ID_HOG`** entry. Descriptions extended for `ID_VIV`, `ID_PERSONA`, `ID_MII`,
  `CVE_ENT`, `CVE_MUN`, `ESTRATO` (2000: 10 digits), `UPM` (2000: 4), `FACTOR` (2005 has
  none) and `EDAD`.
- The header documents `Recodificar`; the contract test checks its editions and targets.
- `EDAD`, `FACTOR`, `ESTRATO` and `UPM` have the same codes in 2000 (and `EDAD` in 2005):
  `--validate` passes with the core entries verbatim.

## Weights

- **CGPV 2000**: `FACTOR` (per dwelling, repeated on its rows). Per the FD annex, it is a
  *separate ratio estimator* per municipality whose auxiliary variable is the
  **preliminary** count of residents of inhabited private dwellings. That count includes
  the occupants INEGI estimated for dwellings without information (4 per dwelling, 5 in
  Chiapas). Σ `FACTOR` therefore matches no final table exactly.
  - **The check** (on the final 2000 ITER's state rows): in **every** state, Σ `FACTOR`
    over persons lies strictly between `OCUVIVPAR` (occupants of private dwellings with
    information) and `POBTOT`.
  - **National totals** (pinned as a regression test): 97,014,867 persons, 21,857,601
    dwellings (first household) and 22,639,808 households. The ITER has `POBTOT`
    97,483,412, `OCUVIVPAR` 95,373,479, `VIVPARHAB` 21,513,235, `TOTHOG` 22,268,916.
  - INEGI's own muestra tabulados could not be located online in this session.
- **Conteo 2005**: a sample **without** a weight. The loaders return no `FACTOR`, and the
  docstrings say so.

## Schema map (gids are chronological; `latest` = the newest edition)

| table | 2000 | 2005 | 2010 | 2010 (state 15) | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|
| `viviendas` | g01 | g02 | g03 | g04 | g05 | g06 | g07 |
| `personas` | g01 | g02 | g03 | g04 | g05 | g06 | g07 |
| `migrantes` | g01 | — | g02 | g03 | — | g04 | g05 |
| `hogares` | — | g01 | — | — | — | — | — |

ITER/AGEB/estimaciones are unchanged. All 25 groups were regenerated. Compared with the
3c dictionaries under their new gids, the 2010–2025 groups differ only in the edited core
descriptions and lengths; the crosswalk is unchanged.

## Code

- `scripts/_dict_fd.py`:
  - `parse_fd_pdf` (path or bytes) / `parse_fd_text`, `_pdf_header`, the `_PDF_*` regexes;
  - the 2005 split-layout headers in `_FD_HEADERS`;
  - `read_catalogs` on a multi-sheet `.xls` (`_catalog_from_rows(lead_keys=True)`);
  - dash ranges in `_parse_code`;
  - the `_quantity` and header-sentinel rules;
  - the FD-over-catalog label casing.
- `scripts/build_cpv.py`:
  - `_ENABLED` += 2000/2005;
  - `_FD_SHEET_TABLE` (2005 sheets, 2000 file tags);
  - `_FD_RENAMES`;
  - `_fd_docs` reads a ZIP-wrapped PDF (`_FD_MEMBER_RE`) and the `.xls` catalogs;
  - `--variables` uses `_scoped_entry`.
- `src/mxcensus/cpv.py`:
  - `_HOUSEHOLD_KEY_SPEC`, `_OPTIONAL_KEYS`, `_COMPOSITE_KEYS`, `_KEY_PARTS`;
  - `_composite_keys`, `_scoped_entry`;
  - the core recodes in `_harmonize`;
  - `load_cpv_hogares` (exported);
  - docstrings.
- `src/mxcensus/_yaml/variables_cpv_core.yaml`: see §Core.
- `data/_cpv_catalog.py`: the 2000/2005 key notes corrected (`CONS_VIV` is not a key).

## Tests

`tests/test_cpv.py`, unit-4a section:
- **Offline**:
  - a synthetic CGPV 2000 FD text (`parse_fd_text`: every wrap case, code lists vs
    counts, `FECNACA`);
  - a synthetic 2005 split-layout FD + catalog workbook;
  - `_fd_docs` table mapping and the two renames;
  - the build plan;
  - `_composite_keys` for both editions (file-order persons, `NUMVIV` restarting per
    locality, idempotence, raw = harmonized keys, the `SEXO` recode only for 2000/2005);
  - `_scoped_entry`;
  - the optional household key;
  - the schema-map groups.
- **Real** (state 01 + all 32):
  - `load_cpv_survey(2000)`: shapes, indices, nesting, Σ `FACTOR`, `SEXO` labels, recode;
  - `load_cpv_survey(2005)` + `load_cpv_hogares`: shapes, nesting, no `FACTOR`,
    Σ `TOTPEHOG` = persons, stacking with 2020;
  - the 2000 ITER bounds for states 01/09/15;
  - the national pins.
- **Changed**:
  - the 2010 schema-map test finds its groups by edition (gids moved);
  - the core contract test compares with the *scoped* entries;
  - `test_key_specs_nest_and_skip` checks the household spec and the key parts. 2000's
    `MPER` is the emigrant's own number, not a person-list pointer, so it is exempt from
    the pointer coding check.

**Full suite on the Mac**, with every CPV edition in all 32 states: **1,322 passed, 1
skipped**, 4 pre-existing DENUE/ENOE warnings, in 27 min. The one failure was
`test_key_specs_nest_and_skip` (the exact `_SKIP` set, and 2000's `MPER`); it was fixed and
re-run.

`tests/test_mg.py` (MG 2010 from 3d, until now untested):
- the national-ZIP layer names;
- `_state_codes`;
- `_build_national` on a synthetic nested ZIP;
- `test_real_mg_2010_counts` (counts per layer; municipalities = the 2010 ITER's 2,456).

## Deviations from the plan

- **The 2000 weight check is a bound, not an equality** (§Weights).
- **The 2000 dictionary is the FD PDF**, not DDI 141: the PDF annex is complete and
  matches the data.
- The household spec was added to every microdata key (absent levels drop out) instead of
  a separate per-edition key table.
- Everything ran on the Mac, so `wsl` lacks the 2000/2005 files and the 2010/2015 rebuilds
  are not yet compared with `wsl`'s: §Pending.

## Pending (needs `wsl`)

- Bring `wsl:~/mxcensus` to the branch, then copy or rebuild the 2000/2005 files there
  (`build_cpv.py --periods 2000 2005 --tables viviendas hogares personas migrantes`, about
  a minute).
- Compare the Mac's 2010/2015 rebuilds with `wsl`'s by `sha256sum`. The DBF/CSV
  conversion is deterministic, so they should be equal.
- Upload 2000/2005 with 4b's ITER files (4b's gate).
