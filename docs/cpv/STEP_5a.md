# CPV Unit 5a — 1990 + 1995 ITER (DBF) and their crosswalk

Done **2026-10-08** (overnight, unattended, on the Mac). Like 3a–4b, the files are built but
not registered or uploaded (the release batch waits for `wsl`).

Gate: `--validate` 0 with the 1990/1995 ITER — ✅ **0/801**. The crosswalk entries are
reviewed.

## Build

`_ENABLED` now holds every edition (1990–2025). The CLI guard test disables one by
monkeypatching `_ENABLED`. `build_cpv.py --periods 1990 1995 --tables iter` downloaded 64
per-state ZIPs (`ccpv/{1990,1995}/microdatos/iter/{NN}_{slug}_{year}_iter_dbf.zip`, members
`ITER_{NN}DBF90.dbf`/`ITER_{NN}DBF95.dbf`): **64 files, 0 failed**.
- **1990**: 46 columns, 162,193 rows, 7 MB.
- **1995**: 44 columns, 205,765 rows, 10 MB.
- Every DBF is cp1252 with upper-case names; the total rows and 9998/9999 aggregates are
  laid out as in 2000–2010.
- **Marker**: `*` only (1990: 2,114,630 cells, 1995: 3,111,503; `_AGG_SPECIALS`).
- **National totals** (the state rows summed): 1990 **81,249,645**, the XI Censo's published
  total. 1995 **90,638,604**, equal to the «TOTAL NACIONAL» row of INEGI's national 1995
  ITER file (`00_nacional_1995_iter_dbf.zip`, checked). INEGI's headline figure for the
  Conteo 1995, as I recall it (91,158,290), is higher. The ITER descriptor does not explain
  the difference, so the test pins the ITER's own total.
- **1995's aggregates are not duplicates.** In 1995 the localities of one and two dwellings
  appear only in the 9998/9999 rows. A municipality equals its listed localities plus its
  `agregado` rows, in all 2,413 municipalities. In 1990 and 2000–2020 the listed localities
  alone add up (checked for 1990: 2,403 municipalities, and 2000: 2,443).
  `load_cpv_iter`'s docstring says so, and the zero imputation stays safe: it fires only
  where a municipality equals the sum of its listed localities.
- **Broken rows**: seven 1995 locality rows have a name that spilled into `LONGITUD`
  (Chihuahua 3, Oaxaca 3, Querétaro 1; e.g. Urique 1781 «Y» + «GRIEGA», with no comma).
  `_repair_spilled_names` now recognizes a spill as **a `LONGITUD` without a single digit**:
  the coordinate is digits through 2005, and degree-minute-second text with digits in
  2010/2020. It fixes these rows like 2000's. After the shift they are consistent (men +
  women = total).
- Faithful oddities left alone: 1995 `ALTITUD` `54O` (a letter O) and `-3` (below sea
  level, Baja California).

## Dictionaries: the ITER descriptor PDFs

Neither ZIP has a dictionary, and there is no DDI. INEGI's file listing (`idBiinegi` 781,
343) shows an ITER descriptor per edition: `doc/fd_iter_1990.pdf` and `doc/fd_iter_1995.pdf`
(`DICTIONARY_URLS[…]["fd_iter"]`). Each is a table «Estructura de la tabla FD ITER…» with
the columns No. | Categoría o indicador | Descripción | Mnemónico | Rango | Long.
- **Reading them.** They are AES-encrypted with an empty password. `pypdf` needs the
  `cryptography` package for that, and no packages were installed. Homebrew's poppler
  `pdftotext` (already on the Mac) reads them: `_dict_fd.pdf_words` runs `pdftotext -tsv`
  for the word boxes. It raises with an install hint if poppler is missing (`wsl` will need
  `poppler-utils` for `--dictionary` of these two editions).
- **Parsing.** `_dict_fd.parse_iter_fd_tsv(tsv, align)` rebuilds the table from word
  positions:
  - per page, the column edges come from the header words and the left edges most lines
    share;
  - a row is anchored on its number; mnemonic, range and length are the nearest words in
    their columns;
  - the indicator and description lines join a row by its layout:
    - 1990 is **top**-aligned (a line belongs to the last row at or above it, across page
      breaks);
    - 1995 is vertically **centred** (each column splits into contiguous runs, one per row,
      centred on its number: a small dynamic program, `_centred_runs`);
  - the header, the section titles and the footnotes after «Total de caracteres» are left
    out; a word hyphenated at a line end is rejoined.
- **Output.** 46 and 44 rows, each checked by eye against the PDF, every indicator name
  right. `--dictionary` writes them as `diccionario_datos_iter.csv`, INEGI's later format,
  so `parse_indicator_csv`, `--variables` and the crosswalk read them unchanged.
- **One misspelling**: the 1995 descriptor's `P_P5HLIYE` is the DBF's `P_PP5HLIYE`
  (`build_cpv._INDICATOR_RENAMES`, applied by `_indicator_doc`, which the crosswalk now uses
  too).

**Schema map**: ITER 1990 = `g01`, 1995 = `g02`, 2000 = `g03`, 2005 = `g04`, 2010 = `g05`,
2020 = `g06` (29 groups in all). Every 1990/1995 column is documented by its descriptor.

## Crosswalk (388 → 402 indicators)

`_XW_PERIODS` gains 1995 and 1990, and both join `_XW_DESC_PERIODS` (description
auto-pairs). Reviewed:

| edition | columns | same name | auto-paired | hand-paired |
|---|---|---|---|---|
| 1995 | 44 | 23 (9 geography + 14 percentage indicators only 1995 has) | 14 | 7 |
| 1990 | 46 | 9 (geography) | 24 | 13 |

- **Renamed by hand**:
  - sex: `POBTMAS`/`POBTFEM` (1995), `HOMBRES`/`MUJERES` (1990);
  - `IM` → `REL_H_M` (men per 100 women);
  - `PROM_VIV` → `PROM_OCUP` (1990);
  - electricity, drainage and piped water (`VIVP_*` 1995, `C_*` 1990 → `VPH_C_ELEC`,
    `VPH_DRENAJ`, `VPH_AGUADV`): 1990/1995 define piped water as "inside the dwelling or
    its lot", 2010/2020's «ámbito de la vivienda»;
  - `PISO_TIE`, `VIV_1_C`;
  - five 1990 housing/education indicators onto 2000-only ones (`INS_PPRIM` →
    `P15_POSPRI`, `PARED_LA` → `VP_PARDES`, `TECHO_LA` → `VP_TECDES`, `VIV_2_C` →
    `VP_2CUAR`, `VIV_PPROP` → `VP_PROPIA`).
- **Kept name**: 1995 `PRO_O_VP` → `PROM_OCUP`. Its descriptor divides total population
  by all dwellings, not occupants of private dwellings by those dwellings.
- **Auto-pairs reviewed**:
  - `POBTOTAL`/`P_TOTAL` → `POBTOT`;
  - education (`SIN_INS`, `PRIM_INC`…), activity (`P_E_ACT` → `PEA`…);
  - dwelling totals;
  - 1990 ↔ 1995/2000 indicators no later census has (`POB_LEE` → `P6_14SLEE`…).
- **A review dict had a duplicate key**: the new `PROM_OCUP` entry silently dropped
  2000's pair. Fixed, and a test now parses `build_cpv.py` and refuses duplicate keys in any
  dict literal. It also checks every reviewed pair lands under its canonical name.
- The 2000–2020 entries are unchanged, except three notes (`VPH_AGUADV`, `PROM_OCUP`,
  `REL_H_M`).

## Tests

`tests/test_cpv_aggregates.py`:
- the descriptor parser on synthetic word boxes (top-aligned with a page break, a title and
  a footnote; centred, then written as CSV and read back);
- `_centred_runs`;
- the 1990/1995 crosswalk pairs and the duplicate-key guard;
- the digitless spill (`Y GRIEGA`) next to an untouched 2020-style coordinate;
- `test_iter_1990_1995_real` over 64 files: state = Σ municipalities = Σ localities (1995:
  + agregados), men + women = total, renamed indicators present; the repair warning in
  1995's states 8/20/22;
- the national totals.

The schema-map and coverage tests span six ITER editions.

Results: `tests/test_cpv.py`, `test_cpv_aggregates.py`, `test_cli.py`, `test_schema_groups.py` and `test_mg.py` over all 32 states of every edition: **923 passed, 1 skipped** (22 min).

## Deviations from the plan

- The plan said "1990/1995 have no DDI: use DBF field metadata, then data enumeration, and
  flag it". INEGI's ITER descriptor PDFs were found instead, a complete dictionary, read
  through poppler.
- `pdftotext` is a new build-time requirement, for `--dictionary` of 1990/1995 only.
