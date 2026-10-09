# CPV Unit 6l — dictionary fixes: the Conteo 2005's ellipsis rows, CGPV 1990's «0»

Done **2026-10-08** (on the Mac, the same session as 6k). Gate: the two artefacts gone from
the generated dictionaries, every other edition's FD parse byte-identical, `--variables`
rerun, tests green.

## The Conteo 2005's `':'` category

The 2005 FD (`fd_muestra_2005.xls`, split layout) enumerates long code lists by their first
and last rows with a vertical ellipsis between them: «1 Un grado aprobado», «: :», «8 Ocho
grados aprobados». `_dict_fd._code_row` took the `':'` row for a code, so three dictionaries
(`variables_cpv_personas_g04.yaml`) had a `':'` category: `GRA_APRO`, `NHIJNAVI` and
`NUHIJSOB`. No record has it (harmless, but wrong); the catalogs (`TC_GAPRO`, `TC_NUMH`,
`TC_NHISO`) enumerate the codes in between.

Fix: `_code_row` skips a row whose code is only dots, colons or ellipses (`_ELLIPSIS_RE`).
**Byte-identity check**: every edition's parsed FD (`build_cpv._fd_docs`, 1990–2025) dumped as
JSON before and after: the only difference is the three `':'` entries of 2005.

## CGPV 1990's «0»

1990 writes 0 for «not asked» (the schooling and religion of the under-5s, the activity and
marital status of the under-12s, the refugios' dwelling items; 6j reads it as blank). Its FD
labels no 0, so `--variables` appended the observed code with an identity label (`'0': '0'`,
`Nota: códigos observados sin etiqueta en el FD: ['0']`) in 20 coded person items: `ACT_PRIN`,
`AGUA_ENTU`, `ALFABETA`, `APROBO`, `ASISTE`, `COMBUS`, `CUA_EXCLU`, `DRENAJE`, `ELECTRI`,
`EST_CIVIL`, `HAB_ESP`, `HAB_IND`, `NIV_EST`, `PAREDES`, `PISOS`, `RELIGION`, `SIT_TRAB`,
`TECHOS`, `TENENCIA`, `TIE_EXCU`.

Fix: `build_cpv._label_blank_zero`, run by `--variables` for the editions in `_BLANK_ZERO`
(1990), labels a non-core categorical entry's identity-labelled 0 «Blanco por pase» (the
blank's label in the other editions' FDs and in the legacy dictionaries) and rewrites the
note («0 = no aplica (sin etiqueta en el FD): «Blanco por pase»», other unlabelled codes kept).
Numeric items (years, rooms, income: 0 = none) are untouched; the derived columns read the
raw codes, so they do not change.

## Regeneration

`build_cpv.py --variables` on the Mac (full mirror; gids unchanged, so no YAML deleted
first): only two files changed.
- `variables_cpv_personas_g04.yaml` (Conteo 2005): the three `':'` rows removed (−3 lines);
  `GRA_APRO` = 1–8, `NHIJNAVI`/`NUHIJSOB` = 0–25.
- `variables_cpv_personas_g01.yaml` (CGPV 1990): 20 labels `'0'` → «Blanco por pase» and their
  notes (40 lines).

The labelled frames follow: state 01, 1990, «Blanco por pase» = 19,260 persons in `NIV_EST`
(no grade approved or under 5), 23,452 in `ACT_PRIN` (under 12), 9,894 in `RELIGION` (under
5), 12 dwellings in `PISOS` (refugios); 2005 `GRA_APRO`'s categories are the eight grades and
«No especificado». No raw validation changes (the codes were already in the `isin` sets).

## Tests

- `test_parse_fd_2005_ellipsis_rows` (offline): an FD with «1», «: :», «3» and a catalog
  with 1–3 → categories 1–3, no `':'`; `_ELLIPSIS_RE` matches `:`/`...`/`…`/`⋮`, not `1..8`.
- `test_label_blank_zero` (offline): the 0 relabelled and the note rewritten; another
  unlabelled code kept; numeric, core and FD-labelled entries untouched.
- `test_dictionary_fixes_6l` (the bundled YAML): no `':'` in the three 2005 items (`GRA_APRO`
  = 1–8); 1990's 20 items label 0 «Blanco por pase», none `'0'`.
- **Full suite**: 1751 passed, 1 skipped (29.5 min, the Mac's full mirror; 6k + 3).
