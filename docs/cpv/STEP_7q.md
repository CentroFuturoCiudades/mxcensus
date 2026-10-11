# CPV Unit 7q — quantities the FDs write as codes: CGPV 2000's hours and incomes, 1990/1995's incomes

Done **2026-10-11** (on the Mac, with the user). HANDOFF candidate 2's «CGPV 2000's other
quantities typed as code ranges» (the user's choice over the 0.12.0 release, the kinship
lines and the tabulados by locality size), widened by the user, after a survey of every
edition's dictionaries, to the other editions' quantities typed as text: CGPV 1990's income
and the Conteo 1995's incomes by period.
Gate: only those dictionary entries change; `--validate` 0/897; the labelled frames carry
them as `Int64` in every state; tests green.

## The problem

Three FD shapes make the parsers read an amount as codes, so its entry was `Tipo: string`
and the labelled frames returned it as text (sentinels and all):

- **A zero-padded range** (7f's case): `{000000..999999,b}`, the shape of a locality's code,
  is read as a code list (`_dict_fd`). CGPV 2000's hours and 11 incomes.
- **A range whose only rows are its special values**: CGPV 1990's `INGRESO` (the FD lists
  `99999997 EVENTUAL`, `99999998 NO SABE`, `99999999 NO ESPECIFICADO`) and the Conteo 1995's
  `P7_9A` (`00000`, `98000`, `99999`) and `P7_11A` (`98000`, `99999`) were read as catalogs of
  1–2 codes, too many distinct values to enumerate, so even their sentinels were dropped
  (`catálogo de N códigos (no enumerado)`).

A survey of every edition's dictionaries found no other quantity typed as text: the other
code ranges are geography and keys (`MUN`, `LOC`, `NUMVIV`, 2010's `ID_PER`/`NUMPER`).

## What changed

- **`scripts/build_cpv.py`**: `_QUANTITIES` is now a dict (period, column) → `_Quantity(rango,
  especiales, nota)`, each transcribed from its FD with the passage quoted in the comment:
  - 7f's `NUM_PERS` (1990) and `NUMPERS` (2000): unchanged (the FD's zero-padded range);
  - CGPV 2000 **`HORTRA`**: `[0, 168]`, `999` «No especificado»;
  - CGPV 2000's monthly incomes **`INGRESOS`, `JUBPENC`, `AYUFAOPC`, `AYUFADPC`, `PROCAMPC`,
    `OTROTIPC`, `OTINGPER`, `INGTOPER`** (persons) and **`INGTRHOG`, `OTINGHOG`, `INGTOHOG`**
    (households): `[0, 999998]`, `999999` «No especificado» — as Censo 2010/2020 type theirs
    (the top code inside the range, explained in `Nota`);
  - CGPV 1990 **`INGRESO`**: `[0, 99999996]`, `99999997`/`8`/`9` with the FD's labels;
  - the Conteo 1995 **`P7_9A`** `[0, 98000]` and **`P7_11A`** `[1, 98000]`, `99999` «No
    especificado»; the codes the FD labels inside the range (`00000 = No recibe ingresos`,
    `98000 = $98,000 o más`) go into `Nota`.
- `_label_quantities(entries, periods, skip, doc)` now takes the FD document (as
  `_label_code_groups`): an entry must still be text (a zero-padded range or a catalog of
  a few codes), and the codes the FD documents out of the range must be exactly the
  sentinels given — else it raises (the FD changed). A sentinel takes the FD's label where
  its layout has one.
- `--variables`: **14 entries in 4 YAMLs changed** (`variables_cpv_personas_g01` 1990,
  `_g02` 1995, `_g03` 2000, `variables_cpv_viviendas_g01` 2000); the other 28 YAMLs are
  byte-identical, 7f's entries too.

Nothing else: the derivations read the raw codes (`INGTRMEN_CAT`, `INGTRMEN_SM`,
`HORTRA_CAT`, `INGTRHOG_CAT` unchanged), `check_cpv_tabulados.py` reads raw frames
(`labels=False`), and `harmonize=True` validates the core only.

## What the FDs say

- **CGPV 2000** (`fd_muestra_censal_2000.pdf`): the record layout gives only `{000..999,b}`
  and `{000000..999999,b}`; the methodology text documents the incomes — «Ingresos por
  trabajo»: the income is made monthly by its period, «si el valor rebasa a 999 999 se asigna
  el valor 999 998 para distinguirlo de los ingresos no especificados (999 999)»; «Otros
  ingresos por persona»: the sum of the five sources, 999 998 when it exceeds it, «el valor
  000 000 … significa que la persona no percibe este tipo de ingreso»; the household
  incomes sum the members', not specified when every member's is. It says nothing of the
  hours' 999: the data hold 0–168 and 999 (116,755 persons), Censo 2010's «No especificado»
  as its FD writes it.
- **CGPV 1990** (`fd_cgpv1990.pdf`, «53 INGRESOS»): `00000000..99999996` the monthly wage;
  «los siguientes tres rubros se consideran como ingreso no especificado»: `99999997`
  eventual, `99999998` no sabe, `99999999` no especificado. In pesos of before the 1993
  redenomination. 1990 writes 0 for everyone not employed (5.9M persons, «not asked»), as
  for the 168,677 employed without income; a quantity cannot tell them apart (`Nota` says
  so; `INGTRMEN_CAT` uses `ACT_PRIN`).
- **Conteo 1995** (`fd_encuesta_cpv1995.pdf`): `P7_9A` `{00000..98000,99999,b}` (00000 no
  income, 98000 «$98,000 o más», 99999 not specified), `P7_11A` `{00001..98000,99999,b}`;
  each an amount per the period in `P7_9B`/`P7_11B`.

## The data (every state)

Records of the samples (unweighted), from the 32-state sweep:

| item | records | missing | of which the sentinel |
|---|---|---|---|
| 2000 `INGRESOS` | 10,099,182 | 6,823,080 | 180,688 (999998: 829) |
| 2000 `JUBPENC` | 10,099,182 | 9,927,125 | 24,852 |
| 2000 `AYUFAOPC` | 10,099,182 | 9,969,688 | 20,493 |
| 2000 `AYUFADPC` | 10,099,182 | 9,910,510 | 26,778 |
| 2000 `PROCAMPC` | 10,099,182 | 9,474,249 | 48,083 |
| 2000 `OTROTIPC` | 10,099,182 | 9,996,053 | 19,775 |
| 2000 `OTINGPER` | 10,099,182 | 95,205 | 95,205 |
| 2000 `INGTOPER` | 10,099,182 | 228,537 | 228,537 (999998: 913) |
| 2000 `HORTRA` | 10,099,182 | 6,759,147 | 116,755 |
| 2000 `INGTRHOG` (households) | 2,312,035 | 67,235 | 67,235 (999998: 714) |
| 2000 `OTINGHOG` | 2,312,035 | 52,729 | 52,729 |
| 2000 `INGTOHOG` | 2,312,035 | 61,171 | 61,171 (999998: 814) |
| 1990 `INGRESO` | 8,118,242 | 100,804 | 100,804 (289 / 1,383 / 99,132) |
| 1995 `P7_9A` | 332,061 | 213,998 | 5,618 (98000: 13) |
| 1995 `P7_11A` | 332,061 | 311,232 | 919 (98000: 5) |

Every other value lies in its range: 2000's hours 0–168, `INGRESOS` up to 999,600 below
the top code; 1990's up to 99,999,989; 1995's `P7_9A` 0–82,000, `P7_11A` 5–75,000.

## Tests

- New `test_dictionary_quantities_7q`: the 15 entries' type, range and sentinels (labels, not
  codes); 1995's in-range codes in `Nota`; `_label_quantities` raises when the FD documents a
  sentinel more or one fewer.
- New `test_quantities_7q_real` (state 01, the local mirror): each labelled column `Int64`,
  missing exactly where the raw code is blank or a sentinel, the raw numbers elsewhere.
- `tests/test_cpv_derived.py::test_source_codes_match_2020`: 2000's `INGTRMEN` (`INGRESOS`),
  `HORTRA` and `INGTRHOG` leave `_OWN_CODES`/`_NO_CATALOG` — they are now compared with
  2020's code lists (`999999`, `999`) and match; 1990's income lists its three sentinels.
- `test_dictionary_quantities_7f` unchanged (passes).

## Verification

- `--variables` (Mac, full mirror): the 14 entries, nothing else.
- `--validate --jobs 6`: **0/897**, `VALIDATION_REPORT.md` byte-identical.
- A 32-state sweep (`load_cpv_personas`/`load_cpv_viviendas`, labelled with `derived=True`,
  against `labels=False`): every item of every state `Int64`, missing exactly at the blanks
  and sentinels, within its range, equal to the raw number elsewhere (1 min 44 s, 4
  processes).
- Full suite on the Mac: **1927 passed, 1 skipped** (33 min).

## Left out (for the user's review)

- **Self-labelled sentinels** (the survey's (c); the user's choice to leave them): numeric
  items whose sentinel is labelled with its own code, from FDs that give it no label or
  from `_reconcile_ranges` — 2000 `CUADORM`, `TOTCUART`, `ESCOACUM`, `HIJFAL`, `HIJSOB`,
  `FECNACM`, `FECNACA`, the emigrants' `MEDAD`, `MFECEMIM`/`A`, `MFECRETM`; 1995 `P7_9MP`/`MH`,
  `P7_11C`/`E`/`MP`/`MH` (`P7_11C`/`E` «Igual que en INGRESO (1)»), `INGMENTP`/`H`; 1990
  `N_F_GPOS`, 2010 `ESCOACUM`. Cosmetic: a numeric sentinel is missing whatever its label.
- **Codes typed as numbers** (the survey's (d)): CGPV 2000's religion `OTRAREL_C` (`Rango
  [1, 9001]`), the emigrants' state of origin `MLUGORI_C` and destination country
  `MPDESOTR_C`, and the Conteo 1995's periods of the second and third other incomes
  `P7_11D`/`F` («Igual que en PERIODO (1)», whose `P7_11B` is categorical) become `Int64` in
  labelled frames (zero padding lost; the derivations read the raw codes).
