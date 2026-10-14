# CPV Unit 8f — the kinship lines; the codes the FDs leave out

Done **2026-10-14** (on the Mac). HANDOFF candidate 1's small items, the user's choice over the
lineage leftovers and 8e's leftovers (the 0.15.0 release, planned after it, waits: the user
committed 8f only): CGPV 1990's undocumented
`TIP_HOGAR` 6 (and the two other codes the FDs leave out) and 7p's kinship lines as a derived
column. The third small item, the hand-curated minimum-wage tables as a generated YAML, stays
conditional (no later edition needs one). Gate: every code the FDs leave out explained in the
dictionaries (`--validate` 0/897, 2 min with `--jobs 6`), `LINEA_PARENTESCO` derived in every state of its six editions
with no unmapped code, Censo 2010's and 2020's tabulados read on it and still exact, tests green.

## Decisions (user, 2026-10-14)

| question | decision |
|---|---|
| CGPV 1990's `TIP_HOGAR` 6 | **a sentinel of its own**, «NO ESPECIFICADO (SIN DATOS DEL HOGAR)», apart from 7 «NO ESPECIFICADO» (recommended; over one label for both) |
| the editions of the kinship line | **1990, 2005, 2010, 2015, 2020, 2025**: every edition whose relationship catalog names each relative (recommended; over 2010/2020/2025 only) |
| its categories | **Censo 2020's nine lines in every edition** (recommended; over each edition's own tabulado lines): Censo 2010's seven are sums of them |
| Censo 2010's «otro parentesco» (`PARENT` 08) without a detail code (44,098 records, 0.39% weighted) | **«Otro parentesco»**, as the EIC 2015's «Otro familiar» and Censo 2020's «Otros familiares» (recommended; over INEGI's 2010 placement among the collaterals) |

Taken without asking: the column's name `LINEA_PARENTESCO` and its labels (13-02's own:
«Persona de referencia», «Esposa(o) o pareja», «Hija(o)», «Ascendente», «Descendente»,
«Colateral», «Otro parentesco», «Sin parentesco», «No especificado»); 2000's `ABANESCO` 8
labelled «Causa no especificada» (its 9 is «No especificado»); 1995's `ZONA` 06/07 keep their
numbers with a note; tutors and the tutored «Sin parentesco» (2020's 502/503) in 1990 too, whose
catalog files them under «otro parentesco» (618/619).

## The codes the FDs leave out (`build_cpv._UNDOCUMENTED`)

`--variables` labels an observed code its FD does not document with itself and notes
«códigos observados sin etiqueta en el FD». Three categorical items carried that note; each is
now explained by `_UNDOCUMENTED` ((period, column) → the codes' labels and a note that replaces
the FD's; `_label_undocumented`, after `_label_blank_zero`). A note the table does not explain
raises, so a new edition or re-parse that leaves a code out stops `--variables` (numeric
sentinels are `_SENTINELS`'s, 7r).

- **CGPV 1990 `TIP_HOGAR` 6** (FD: «1..5 Y 7»): every person of the dwellings whose household
  items went unanswered — `F_G_COC` 9, `N_F_GPOS` 99 and a 9xx relationship, in those 96,370
  records only, and in all of a dwelling's records (no folio mixes 6 with another type) —; 7 is
  a household with its members whose type is not specified (25,905 records, `N_F_GPOS` known).
  Now `Especiales` `6: NO ESPECIFICADO (SIN DATOS DEL HOGAR)`, `7: NO ESPECIFICADO`.
- **CGPV 2000 `ABANESCO` 8**: the cause not specified of who stopped attending school
  (`ASISTEN` 2; 222,541 records), the «No especificado» column of C2KED13–15 (7z: ED14 exact
  outside Chiapas on 1–8); 9 «No especificado» is not among them. Now `Especiales`
  `8: Causa no especificada`.
- **Conteo 1995 `ZONA` 06/07** (personas and migrantes; FD «01..05», «Ver Catálogo»): the
  zones are numbered per state in its «Catálogo de áreas metropolitanas»
  (`catalogos_cpv1995.pdf`), and Veracruz has seven (06 A.M. de Poza Rica, 07 A.M. de Veracruz).
  The codes keep their identity labels (a zone's number names no zone without its state); only
  the note changes.

The regenerated dictionaries differ in those four entries only (`variables_cpv_personas_g01`,
`g02`, `g03`, `variables_cpv_migrantes_g01`); `--validate` 0/897.

## The kinship line (`cpv_derived.LINEA_PARENTESCO`)

INEGI tabulates the population in households by «líneas de parentesco» twice: Censo 2010's
`12_04A` (seven lines) and Censo 2020's `13-02` (nine). 7p and 7w found each rule on its
tabulado in every state and sex, but in the check script only. 8f makes it a derived person
column with 2020's nine lines in every edition whose catalog names each relative
(`_LINEAS`: edition → line → its codes, assigned by the catalog's labels):

| edition | item | notes |
|---|---|---|
| CGPV 1990 | `CVE_PAR` | the first digit is the relationship (the FD's groups), the other two CATPAREN's word as written: 7xx «persona sola» heads a household of one (its 702 «huésped» and 703 «abonado» live alone, `NUM_PERS` 1), the «otro parentesco» (6xx) read by the word, tutor/tutelado (618/619) none |
| Conteo 2005 | `PARENT` | 102 «persona sola» a head; 715 «otro pariente del huésped» none |
| Censo 2010 | `PARENT` + `OTROPARE_C` | `_linea_2010`: the groups 01–07, 09, 99, and for 08 the detail, numbered as 2005's 6xx; no detail → «Otro parentesco» (the user's choice), an unknown detail missing (so `derive` raises) |
| EIC 2015 | `PARENT_OTRO_C` | the detail of every record (it agrees with `PARENT`'s group in every record) |
| Censo 2020, EIC 2025 | `PARENTESCO` | 13-02's rule (the same catalog) |

The Conteo 1995's `P3_4` has groups only and CGPV 2000's `OTROPARE_C` detail codes have no
labels (6u), so neither gets the column.

Censo 2010's seven lines are sums of the nine: its descendants = «Hija(o)» + «Descendente», its
collaterals = «Colateral» + the 08 without a detail, its «No especificado» = «No especificado» +
«Familiar» (623) — the last two «Otro parentesco» in the column.

**National shares** (Σ `FACTOR`; 1990's extract and 2005 unweighted):

| line | 1990 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|
| Persona de referencia | 20.13 | 24.77 | 25.63 | 26.73 | 27.88 | 30.45 |
| Esposa(o) o pareja | 15.37 | 17.88 | 17.85 | 17.76 | 18.03 | 17.99 |
| Hija(o) | 52.76 | 45.35 | 42.47 | 40.36 | 38.88 | 36.68 |
| Ascendente | 1.06 | 1.28 | 1.17 | 1.26 | 1.29 | 1.37 |
| Descendente | 4.35 | 8.05 | 9.97 | 10.53 | 11.37 | 10.67 |
| Colateral | 1.51 | 1.58 | 1.49 | 1.59 | 1.65 | 1.79 |
| Otro parentesco | 0.04 | 0.25 | 0.41 | 0.60 | 0.31 | 0.22 |
| Sin parentesco | 1.18 | 0.55 | 0.49 | 0.62 | 0.56 | 0.51 |
| No especificado | 3.60 | 0.28 | 0.51 | 0.55 | 0.04 | 0.32 |

Censo 2020 = 13-02's national row to every published decimal (27.875361 … 0.039206); Censo
2010 = 12_04A's (25.6307, 17.8526, 1.1717, 42.470 + 9.970 = 52.4404, 1.492 + 0.390 = 1.8820,
0.4919, 0.508 + 0.023 = 0.5306). 1990's not specified (3.6%) includes `TIP_HOGAR` 6's 96,370
records (1.2%).

## Checks (`scripts/check_cpv_tabulados.py`)

`_kinship_2010` (12_04A and its by-size twin 12_03A) and `_lines_2020` (13-02, 13-01) read the
derived column now (2010 with `OTROPARE_C`'s blank to split «Otro parentesco» back), so the
column itself is checked against INEGI in every state, sex and size: 2010 5,472 cells exact,
2020 1,170 cells within the persons' tolerance (max 0.56 of a person, as before). Titles and
notes are unchanged, so `TABULADOS_REPORT.md` is byte-identical.

## Tests

- `tests/test_cpv.py::test_label_undocumented_8f`: no categorical CPV entry keeps the FD's
  note, the three items' labels, `_label_undocumented` on synthetic entries (a numeric entry
  left to `_label_sentinels`; an unexplained or another code raises).
- `tests/test_cpv_derived.py::test_derive_linea_parentesco`: every edition's fixture (1990, 2005,
  2010, 2015 and 2025 fixtures carry their relationship detail now), Censo 2010's lines through
  its detail, no column in 1995/2000, an unknown 2010 detail raises.
- `test_linea_parentesco_labels`: every line's codes agree with their labels in the edition's
  dictionary (words at the start of a word, accents dropped: «compadre» is no «padre»), and only
  «Sin parentesco» names a domestic worker, guest or tutor — it caught 1990's 702/703.
- `test_source_codes_match_2020`: the relationship items (`_KIN_ITEMS`) — every catalog code has
  a line (Censo 2010: `PARENT`'s groups but 08, `OTROPARE_C`'s 6xx).
- `tests/test_cpv_tabulados.py`: the 2010/2020 kinship tests derive the column first
  (`_with_lines`).
- `test_cpv_derivations_listing`: `LINEA_PARENTESCO` in 1990 and 2005–2025.
- Full suite on the Mac: **1974 passed, 1 skipped** (34 min; the listing test, the run's one
  failure, fixed and rerun on its own).

## Left

- No constraint: no ITER or estimate publishes the lines (the tabulados are sample estimates).
- 1995 and 2000: no line (groups only; undocumented details).
- The minimum-wage tables as a generated YAML (HANDOFF candidate 1): only if a later edition
  needs one.
