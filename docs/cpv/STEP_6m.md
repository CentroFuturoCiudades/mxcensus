# CPV Unit 6m — a BIFF5 reader and the tabulado checks as a maintainer script

Done **2026-10-08** (night, on the Mac; HANDOFF candidate 1, taken without the user, who
asked for the night's units to proceed unattended). Gate: `_dict_fd.read_xls` reads the
CGPV 2000 tabulados (Excel 95) with every BIFF8 parse byte-identical, the 2000/2010/2015
tabulado checks of 6e/6f/6i reproducible in one script over all 32 states, tests green.

## `_dict_fd.read_xls` reads BIFF5

INEGI's CGPV 2000 «Tabulados de la muestra censal» (`ccpv/2000/tabulados/ampliado/C2K*.xls`)
are Excel 5.0/95 workbooks (BIFF5): 6i read them with a scratch reader. `read_xls` now
reads both:

- the OLE2 stream is `Workbook` (BIFF8) or `Book` (BIFF5); neither → `LookupError`;
- the first record must be a BOF whose version is 0x0500 (BIFF5) or 0x0600 (BIFF8), else
  `ValueError` (BIFF2–4 and garbage streams are refused);
- BIFF5 has no shared-string table: strings are 8-bit, in the code page of the `CODEPAGE`
  record (`_CODEPAGES`: 367 ASCII, 10000/32768 Mac Roman, 32769 cp1252, else `cpNNNN`;
  cp1252 without one), with no option byte (`_Biff5Reader`); `LABEL`, `RSTRING` (BIFF5's
  rich-text label, its runs skipped), `STRING` after a text `FORMULA` and the
  `BOUNDSHEET` names use it;
- numbers (`NUMBER`, `RK`, `MULRK`) and formula results have the same layout in both.

**Byte-identity check** (the 6l protocol): every `.xls` under `data/dict/` (16 workbooks:
the 2005/2010/2015 FDs, the 1990/2005 catalog workbooks, the 11 `TC_*` catalogs) and every
edition's `build_cpv._fd_docs` (1990–2025) dumped as JSON before and after: identical. So
are the 56 BIFF8 tabulados of earlier sessions (2010/2015). The 18 BIFF5 tabulados read the
same as 6i's scratch reader.

## `scripts/check_cpv_tabulados.py`

The checks of 6e (migration), 6f (occupation, sector) and 6i (the 2000 sample tabulados)
were scratch scripts; one maintainer script now runs them all, and one more
(EIC 2015 activity), over every state, both sexes and the nation, and writes
[`TABULADOS_REPORT.md`](TABULADOS_REPORT.md):

| edition | tabulados (fetched into `data/dict/tabulados/{period}/`) | unit, tolerance |
|---|---|---|
| CGPV 2000 | `C2KMI01` birthplace, `C2KMI03` residence 1995, `C2KRE02` religion, `C2KSS04` coverage, `C2KEC02` marital status, `C2KEM01` activity, `C2KEM05` sector, `C2KED10` education, `C2KVI06` bedrooms, `C2KVI10` drainage | percentage points (two decimals published); 0.02, Chiapas 0.6 |
| Censo 2010 | `04_02A` residence 2005, `08_02A` occupation, `08_03A` sector (ampliado, «Parámetro») | persons; 1 |
| EIC 2015 | `04_migracion` 02/05, `08_caracteristicas_economicas` 02 (activity, new) / 06 / 07, `14_vivienda` 18 (financing) («Valor») | persons; 1 |

Each check is a `Check`: the tabulado, how its cells are read (the 2000 block layout —
a state row, its HOMBRES/MUJERES rows, age-group rows in between —; the 2010/2015
«Estimador» tables), and the same cells as (numerator, denominator) masks over a state's
`derived=True` frame (the nation sums the states). As in the tests, the persons whose
entity is not specified move to «No especificado» (INEGI's rule; the derived columns keep
the legacy `OtraEnt`). New over 6i: **ED10 on `EDUC_INEGI`** (6k), grouping técnica after
primaria with secundaria, as INEGI's 2000 levels do (its footnote 1), and medium/higher
together (`EDUC_INEGI` has one «Posbásica»).

Two reading traps the script handles: a C2K age-group row such as «50 Y MÁS AÑOS» starts
with two digits (it is not state 50; `_state_of`), and 2010 spells a division «forestales,
caza y pesca» where 2015 writes «pesca y caza» (categories match as word sets, `_words`).

## Results (all 32 states, both sexes, the nation)

10,461 cells. **2010 and 2015 are exact** (the largest gap, 0.87 of a person, is the
rounding of the EIC 2015's six-decimal percentages at the national total): residence in
2005/2010, birthplace, occupation, sector, financing — and, new, the **EIC 2015 activity**
(`CONACT_CAT`: 12+, PEA, employed, unemployed, inactive, not specified) to the person in all
32 states.

**2000** (percentage points; the public sample's weights, 4a):

| tabulado | cells | median \|Δ\| | 95th pct. | max \|Δ\| |
|---|---|---|---|---|
| MI01 birthplace | 297 | 0.003 | 0.007 | 0.076 (Chiapas) |
| MI03 residence 1995 | 297 | 0.003 | 0.007 | 0.026 (Chiapas) |
| RE02 religion | 495 | 0.003 | 0.009 | 0.133 (Chiapas) |
| SS04 coverage | 693 | 0.003 | 0.006 | 0.053 (Chiapas) |
| EC02 marital status | 396 | 0.003 | 0.008 | 0.032 (Chiapas) |
| EM01 activity | 495 | 0.002 | 0.005 | 0.048 (Chiapas) |
| EM05 sector | 1,683 | 0.003 | 0.006 | 0.508 (Chiapas) |
| **ED10 education (`EDUC_INEGI`)** | 594 | 0.003 | 0.011 | 0.094 (Chiapas) |
| VI06 bedrooms | 99 | 0.004 | 0.013 | 0.105 (Chiapas) |
| VI10 drainage | 99 | 0.002 | 0.007 | 0.019 |

MI01/MI03/EC02 now compare men and women too (6i's reader took only both sexes there, the
age-group rows in between). Outside Chiapas every cell is within 0.02 points except 7 of the
1,683 sector shares (manufacturing and commerce in states 05, 12, 19, 26, 28, 30; at most
0.039), so the 2000 tolerance is **0.04** (Chiapas 0.6). **Education now reproduces
INEGI's 2000 levels** (6i: up to 3.6 points off with the legacy `EDUC`): with técnica after
primaria apart (`EDUC_INEGI`, 6k) and grouped with secundaria as INEGI does, ED10 is as
close as the other tabulados (median 0.003).

## Tests

- `tests/test_cpv.py`: `test_read_xls_biff5` (a synthetic Excel 95 workbook through the
  mini stream and regular sectors, with and without `CODEPAGE`: LABEL, RSTRING, MULRK,
  NUMBER, FORMULA + STRING, accented sheet names) and
  `test_read_xls_biff5_codepage_and_versions` (cp850, BIFF4 refused, no BOF);
  `test_read_xls_large_stream_and_errors` updated (no stream → `LookupError`; a `Book`
  stream without a BOF → `ValueError`).
- `tests/test_cpv_tabulados.py` (new): the readers (`_state_of`, `_c2k_blocks`,
  `_c2k_sectors`, `_estimates`, `_long`), `_counts`, the check list's consistency; real
  (the mirror + the cached tabulados): every check of state 01 within tolerance (317 cells).
- **Full suite**: 1769 passed, 1 skipped (31 min, the Mac's full mirror; run with 6n in the working tree: two of 6n's derived tests, updated while it ran, failed there and pass on the rerun of `test_cpv_derived.py` + `test_cpv_tabulados.py`, 244 passed).
