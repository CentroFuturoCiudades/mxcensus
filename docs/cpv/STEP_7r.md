# CPV Unit 7r — codes their FDs make numbers, and the sentinels labelled with their own code

Done **2026-10-11** (on the Mac, with the user). HANDOFF candidate 2's «7q's leftovers»
(the user's choice over the 0.12.0 release, the tabulados by locality size and the other
small items), widened on the probe to every code typed as a number and to one broken FD
parse.
Gate: only the dictionary entries listed here change; `--validate` 0/897; the labelled
frames carry them as decided in every state; tests green.

## The problem

7q left two kinds of dictionary entries (`STEP_7q.md` §Left out), and the probe found more
of each:

- **Codes typed as numbers.** A code space the FD writes as one labelled range («001-570
  Clave de municipio») or as a bare range list («{001-032,999}») is read as a count
  (`_dict_fd._quantity`), so the labelled frames made it `Int64` and lost its zero padding.
  7q named CGPV 2000's `OTRAREL_C`, `MLUGORI_C`, `MPDESOTR_C` and the Conteo 1995's
  `P7_11D`/`F`. A survey of every numeric entry found six more in CGPV 2000 (`QDIALECT_C`,
  `OCUACTIV_C`, `ACTTRAB_C`, `MUN95OTR_C`, `LTRABMUN_C`, the emigrants' `MPAIRES_C`) and the
  Conteo 2005's `NIVANTES`, its level and antecedent, a 15-code list (`TC_ANTES`).
- **Sentinels labelled with their own code** (`'99': '99'`): an FD that lists a sentinel only
  in the header range (`{01..25,99}`) gives it no label, and `_reconcile_ranges` adds the
  all-nines codes the data show. CGPV 2000's rooms, schooling, children, birth dates, the
  emigrants' age and dates; the Conteo 1995's monthly incomes and its second and third other
  incomes; CGPV 1990's `N_F_GPOS`; Censo 2010's `ESCOACUM`. Cosmetic: a numeric sentinel is
  missing in labelled frames whatever its label.
- **A broken parse: CGPV 2000's `MFECRETA`** (the return year), numeric with no range and no
  sentinel. The migration file's layout is the FD annex's last, and the parser kept adding
  indented lines to its last field after «Total de caracteres» (the glossary, the
  minimum-wage annex): one annex row («1 053 Yucatán 981 …») became its only category, so the
  data reconciliation left it a number without its FD range `{1995..2000,9999,b}`. Its 9999
  (4,201 emigrants who returned) would have been read as a year.

## Decisions (the user's)

1. **Sentinels: all «No especificado»**: INEGI's words where its documents give them (the
   2000 FD's text for `ESCOACUM`, `HIJFAL`/`HIJSOB`; Censo 2010's reference table
   `TC_ESCOACUM_2010`; the 1995 FD's «Igual que en INGRESO (1)»), else the FD's convention
   for its other sentinels, with `Nota` saying which. The one exception: 2000's `MPDESOTR_C`
   600 is «País no especificado», as the 2000 FD labels 600 in its birthplace items.
2. **Codes: «string», or «categorical» where INEGI lists every code.** The 2000 code spaces
   become `string` like the edition's own birthplace and residence items (`LNACEDO_C`,
   `RES95EDO_C`, `LTRABPAI_C`) and 2010–2025's catalog codes: the FD's ranges and labelled
   codes go into `Nota`, the sentinels into `Especiales`. `NIVANTES` takes its catalog's
   labels; `P7_11D`/`F` take `P7_11B`'s (the FD: «Igual que en PERIODO (1)»). Labels are not
   borrowed from another edition's catalog (2000's state names, 2010's languages).

## What changed

- **`scripts/_dict_fd.py`**: `parse_fd_text` ends a file's layout at «Total de caracteres»
  (`_PDF_END_RE`). Every FD parse of every edition is byte-identical before and after (a JSON
  dump of the eight editions' `_fd_docs`), except CGPV 2000's `MFECRETA`, now numeric
  `[1995, 2000]` with 9999.
- **`scripts/build_cpv.py`**:
  - `_CODES` (period, column) → `_Code(tipo, rangos, codigos, especiales, nota, catalog,
    like)`, transcribed from the FDs with the passages quoted; `_label_codes(entries,
    periods, skip, doc, dict_dir)` retypes them. It raises when an entry is no longer read as
    a number, when the FD lists a code the spec does not give, or when the FD's range is not
    the spec's (the FD changed).
  - `_SENTINELS` (period, column) → `_Sentinel(especiales, nota)`; `_label_sentinels(entries,
    periods, skip)` labels them. It raises on any self-labelled sentinel not listed, so a new
    one is noticed at the next `--variables`.
  - `_edition_catalogs(dict_dir, period)`: the catalog read `_fd_docs` did inline, cached, so
    `_label_codes` can take `TC_ANTES`.
  - `--variables` runs them after `_label_quantities`: **34 entries in 8 YAMLs changed**
    (`variables_cpv_migrantes_g02`, `personas_g01`–`g06`, `viviendas_g01`); the other 24
    YAMLs are byte-identical.

The derivations read raw codes (`_religion_2000`, `_educ_2005`, `_sector`, `_lugar`…
unchanged), `check_cpv_tabulados.py` reads raw frames, and `harmonize=True` validates the
core only.

### The codes (CGPV 2000 `fd_muestra_censal_2000.pdf`; Conteo 2005 `fd_muestra_2005.xls` + `catalogos_muestra_2005.xls`; Conteo 1995 `fd_encuesta_cpv1995.pdf`)

| item | FD | now | `Especiales` | `Nota` (codes) |
|---|---|---|---|---|
| 2000 `MUN95OTR_C` | `{001-570,999,b}`, «Clave de municipio» | string | 999 | `001..570`, in `RES95EDO_C`'s entity |
| 2000 `LTRABMUN_C` | `{001-570,999,b}` | string | 999 | `001..570`, in `LTRABPAI_C`'s entity |
| 2000 `QDIALECT_C` | `{0111-1311,5010,5020,9999,b}` | string | 9999 | `0111..1311`; 5010/5020 other languages of Mexico/America |
| 2000 `OTRAREL_C` | `{0001,1101-9001,9100,9999,b}` | string | 9999 | `1101..9001`; 0001 Católica, 9100 Ninguna (the FD's text) |
| 2000 `OCUACTIV_C` | `{1100-8390,9999,b}` | string | 9999 | `1100..8390` |
| 2000 `ACTTRAB_C` | `{110-939,999,b}` | string | 999 | `110..939` |
| 2000 `MLUGORI_C` | `{001-032,999}` (no rows) | string | 999 | `001..032`, `LNACEDO_C`'s |
| 2000 `MPDESOTR_C` | `{100-535,600,999}` (no rows) | string | 600 País no especificado, 999 | `100..535`; 221 = the US (the FD's text) |
| 2000 `MPAIRES_C` | `{100-535,600,700,999}` | string | 999 | `100..535`; 600 Extranjero, otro país; 700 México |
| 2005 `NIVANTES` | `TC_ANTES` | categorical (14) | 99 | — (0 unpadded, as the data and the FD's rows) |
| 1995 `P7_11D`/`F` | «Igual que en PERIODO (1)» | categorical (4) | 9 | — |

## The data (every state)

Records of the samples (unweighted), from the 32-state sweep:

| item | answered | sentinels |
|---|---|---|
| 2000 `OTRAREL_C` | 8,929,760 | 0001: 7,861,261; 9100: 321,997; 9999: 54,042 |
| 2000 `MUN95OTR_C` / `LTRABMUN_C` | 8,855,635 / 3,320,654 | 999: 79,779 / 102,600 |
| 2000 `OCUACTIV_C` / `ACTTRAB_C` | 3,456,790 | 9999: 65,984 / 999: 79,554 |
| 2000 `QDIALECT_C` | 1,044,550 | 5010: 21, 5020: 33, 9999: 12,904 |
| 2000 emigrants (`MLUGORI_C`, `MPDESOTR_C`, `MPAIRES_C`) | 195,701 | 999: 2,610; 600/999: 43/1,774 (221: 189,929); 600/700/999: 4/32,672/12,839 |
| 2000 `MFECEMIM`/`A`, `MFECRETM`/`A`, `MEDAD` | 195,701 (return: 32,672) | 15,626 / 9,060 / 4,884 / 4,201 / 4,802 |
| 2000 `ESCOACUM` | 8,896,070 | 99: 253,759 |
| 2000 `HIJFAL` / `HIJSOB` / `FECNACM` / `FECNACA` | 2,390,405 | 2,204 / 2,125 / 189,485 / 139,149 |
| 2000 `CUADORM` / `TOTCUART` (households) | 2,312,035 | 11,613 / 17,280 |
| 2005 `NIVANTES` | 9,241,910 | 99: 177,200 (94: 2,305, 95: 5,607) |
| 1995 `P7_11D` / `P7_11F` | 1,100 / 42 | 9: 67 / 4 |
| 1995 `P7_9MP`/`MH`, `P7_11MP`/`MH`, `INGMENTP`/`H` | 122,530 … 321,392 | 999999: 5,519 / 9,583 / 1,102 / 4,327 / 5,430 / 7,293 |
| 1995 `P7_11C` / `P7_11E` | 1,100 / 42 | 99999: 62 / 4 |
| 1990 `N_F_GPOS` | 8,118,242 | 99: 96,370 (all `TIP_HOGAR` 6, a 9xx relationship) |
| 2010 `ESCOACUM` | 11,210,262 | 99: 123,779 |

## Tests

- New `test_parse_fd_text_2000_layout_end`: a synthetic annex tail (the wrapped `MFECRETA`
  header, «Total de caracteres», an indented wage row) parses to `[1995, 2000]` + 9999 (it
  fails without the fix).
- New `test_dictionary_codes_7r`: the 13 entries' type, sentinels and `Nota`; `NIVANTES`'s 14
  labels, `P7_11D`/`F` = `P7_11B`; `_label_codes` raises on an FD code more, another range,
  an entry no longer numeric.
- New `test_dictionary_sentinels_7r`: no `variables_cpv_*` YAML (microdata or aggregate)
  labels a sentinel with its own code; each `_SENTINELS` entry as listed; `MFECRETA`'s range;
  `_label_sentinels` raises on an unlisted sentinel and on another one.
- New `test_codes_7r_real` (state 01, the local mirror): the string codes equal the raw ones
  (zero padding and sentinels kept), the categorical ones labelled, `MFECRETA` an `Int64`
  year with 9999 missing.
- `tests/test_cpv_derived.py::test_source_codes_match_2020`: 2000's `ACTTRAB_C`, `OTRAREL_C`
  (own codes now {9999}: 9100 is «Ninguna», no sentinel), `LTRABMUN_C`, `MUN95OTR_C` join
  `_NO_CATALOG` (text without a catalog, as `LTRABPAI_C`); 2005's `NIVANTES` lists its
  catalog's codes.

## Verification

- FD parses: the eight editions' `_fd_docs` dumped as JSON before and after: only
  `MFECRETA` differs (and the `_edition_catalogs` refactor changes nothing).
- `--variables` (Mac, full mirror): the 34 entries, nothing else.
- `--validate --jobs 6`: **0/897**, `VALIDATION_REPORT.md` byte-identical (2 min).
- A 32-state sweep (`load_cpv_personas`/`viviendas` with `derived=True`, `load_cpv_migrantes`,
  labelled, against `labels=False`; 2000, 2005, 1995, 1990, 2010): 1,088 checks, none
  failed — every string code equal to the raw one and of one width, every categorical labelled
  by its dictionary, every sentinel item `Int64` missing exactly at the blanks and sentinels,
  equal to the raw number elsewhere and within its range (3 min, 4 processes).
- Full suite on the Mac: **1931 passed, 1 skipped** (33 min; 7q's 1927 + the 4 new tests).

## Left out

- 2000's codes keep no labels beyond the FD's: its state names (`MLUGORI_C`), languages,
  religions, occupations and activities could come from other editions' catalogs, but those
  catalogs are not 2000's (the user's choice: no borrowing).
- 2000's `MPDESOTR_C` 221 «Estados Unidos» (189,929 of its 195,701 emigrants) is in `Nota`
  only: a string entry lists no categories.
