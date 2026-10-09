# CPV Unit 6u — relationship labels (1990–2000) and the Conteo 1995's catalogs

Done **2026-10-09** (on the Mac; HANDOFF candidate 4, agreed with the user, who widened it
to CGPV 2000's relationship item and the 1995 place items). Gate: the relationship items of
1990, 1995 and 2000 labelled from INEGI's own documents, every other edition's FD parse
byte-identical, `--variables` rerun, `--validate` 0/897, labelled frames in all 32 states,
tests green.

## The gap

Three editions shipped their relationship-to-the-head item unlabelled:

- **CGPV 1990 `CVE_PAR`** (3 digits): a `string` entry with «catálogo de 59 códigos (no
  enumerado)». The data hold 107 codes, more than the 64-value threshold, so `--variables`
  never enumerated them. The FD defines only the **first digit** («CATALOGO DE PARENTESCO
  (CATPAREN) PRIMER DIGITO IGUAL A: 1 JEFE(A) … 7 PERSONA SOLA, 9 PARENTESCO NO
  ESPECIFICADO»). `CATPAREN` (`catalogos_1990.xls`) labels the one-digit groups and the
  detail codes 101, 201–204, 301–305, 401–412, 501–503, 601–623, 701–703 and 999, each with
  its synonyms on rows of their own (601 PADRE, PAPA, MADRE, MAMA).
- **Conteo 1995 `P3_4`** (and the emigrants' `P9_15`): a `string` entry. The FD says «Ver
  catálogo de parentesco», and that catalog is a PDF (`catalogos_cpv1995.pdf`) the build
  did not read. It lists eight groups only («los tamaños de muestra no aseguran información
  confiable para cada una de las ochenta descripciones»), and the data hold exactly those
  eight codes.
- **CGPV 2000 `OTROPARE_C`**: 46 identity labels (`'100': '100'`). Its FD has no catalog.
  It documents the item in its «Parentesco» section (PARENT merged into OTROPARE_C): 100
  Jefe(a), 200 Esposo(a), 300 Hijo(a), 401–440 Trabajador(es) doméstico(s), 501–503 No tiene
  parentesco, 601–624 Otro parentesco, 999 No especificado. The same ranges define its
  `TIPOHOG`.

The 1995 catalog PDF also labels the items that point to its other sections. These are the
places (`P3_7B` birthplace, `P4_3` previous residence, `P4_6A` residence in 1990; emigrants
`P9_5`/`P9_7`/`P9_9`: 32 states, six continent codes, 70 Mexico, 90/99 unspecified), the
occupation `P7_4` (19 CMO groups) and the activity `P7_8` (15 CAE sectors; «31 y 32»). Every
observed code is in its section.

## How 1990's codes read (the data)

The FD's group rule holds, and the catalog's one-digit group codes appear in the data as
**G00**: 100 = 1,545,772 heads, 200 = 1,240,389 spouses, 300 = 4,238,914 children, 700 =
79,550 persons alone (~5% of households; `TIP_HOGAR` 5 «unipersonal»), 900 = 278,603. The
group codes cover 7,468,680 of 8,118,242 persons. The catalog's detail codes cover 637,516.
The remaining 49 codes cover 12,046 persons (0.15%): 1YY, 7YY beyond 703 and 9YY.
Their YY follows group 6's detail list by age (9YY: 908 median 5 years = 608 «nieto», 905/77
= 605/78 «abuelo»). The FD documents none of them, so they are labelled by their group. The
whole-dwelling 9xx records are the undocumented `TIP_HOGAR` 6 (96,370 persons, all with
`N_F_GPOS` 99), left as found (see §Left out).

## The user's choices

- **1990: detail where documented** (over «eight groups only»). Each observed code takes
  `CATPAREN`'s label where the catalog has it, with its synonyms joined. Otherwise it takes
  its first digit's group, labelled as `CATPAREN` labels the one-digit group code. G00 thus
  shares the label of the catalog's G01 where both name the same group (100 + 101 «JEFE O
  JEFA», 300 + 301 «HIJO(A)», 500 + 501, 999 + 9xx «NO ESPECIFICADO», a sentinel). The labelled
  column has 54 categories. The raw codes keep everything (`labels=False`).
- **The wider scope**: 2000's `OTROPARE_C` by its FD's groups (no catalog exists, so
  every code takes its group's label: 7 categories), and the 1995 place items. The
  occupation and activity items come from the same PDF through the same «Ver catálogo de»
  link, so they were labelled too (all their observed codes are in the sections).

## What changed

- `scripts/_dict_fd.py`:
  - `_catalog_from_rows` (CGPV 1990's header-less workbook) **joins a code's synonyms**
    («HIJASTRO(A), ENTENADO(A)», «NUERA, YERNO») instead of keeping the first. That changes
    eight `CVE_PAR` codes and one code each of `CVE_P_NAC`/`CVE_P_RES` (700 «OTRO PAIS, EN
    EL EXTRANJERO»), `CVE_LENG` and `CVE_CAR`. Those four stay unenumerated strings, so
    their YAMLs are unchanged.
  - `parse_catalogs_1995_text`: the 1995 catalog PDF (poppler text) →
    `{stem: {code: label}}`, one stem per «CATÁLOGO DE …» section (`PARENTESCO`,
    `ENTIDADES_FEDERATIVAS_Y_PAISES`, `OCUPACION`, `ACTIVIDAD_ECONOMICA`). Wrapped labels
    are rejoined, «31 y 32» gives two codes and a final period is dropped. The groups'
    «Comprende …» definitions are left out, as are the per-state municipal and
    metropolitan-area sections (`_CAT95_SKIP`).
  - `parse_fd_1995_text`: a field the FD gives no codes for, but «Ver catálogo de X», takes
    every code of the section `match_catalog(X)` names. It goes through EIC 2015's «Descripción
    por catálogo» path; P7_8's «rama de actividad» → `ACTIVIDAD_ECONOMICA`. `ENT` keeps its
    own `{01..32}`, and «municipios» matches no section.
- `scripts/build_cpv.py`:
  - `_fd_docs` reads a PDF catalog through `_CATALOG_PDF_PARSERS` (1995).
  - `_CODE_GROUPS` holds the reviewed code groups transcribed from the FDs (2000
    `OTROPARE_C`, 1990 `CVE_PAR`). `_label_code_groups` (run by `--variables`) labels every
    code observed in the group's files: by its own dictionary label (not an identity one),
    else by its group's. A «No especificado» label is a sentinel (`Especiales`). `Nota` lists
    the groups and the codes labelled by theirs. A code outside every group raises, and so
    does a schema group spanning other editions.
- Dictionaries (`--variables`, gids unchanged): only `variables_cpv_personas_g01` (1990),
  `_g02` (1995), `_g03` (2000) and `variables_cpv_migrantes_g01` (1995) changed.

**Byte-identity check**: every edition's FD parse (`build_cpv._fd_docs`) dumped as JSON
before and after. 2000–2025 are identical. 1990 differs only in the five catalog items above
and 1995 only in its ten «Ver catálogo» items.

Nothing downstream reads these items' labels. The derived columns (`HOGJEF_SEXO`'s head
codes, 1995's birthplace and residence) read the raw codes, and raw validation's `isin`
sets now hold exactly the observed codes.

## The data (all 32 states, labelled loaders)

- 1990 `CVE_PAR`: HIJO(A) 4,268,290, JEFE O JEFA 1,553,787, ESPOSA(O) O COMPAÑERA(O)
  1,240,389, NO ESPECIFICADO 292,448, NIETO(A) 219,527, HERMANO(A) 80,139, PERSONA SOLA
  79,804…
- 1995 `P3_4`: Hijo (a) 165,202, Jefe o Jefa 72,277, Esposa (o) o Compañera (o) 55,204, Otro
  parentesco 37,006 … Persona sola 21 (6t: all in households that have a 1).
- 2000 `OTROPARE_C`: Hijo(a) 4,895,946, **Jefe(a) 2,312,035 = the dwelling file's
  household rows**, Esposo(a) 1,738,279, Otro parentesco 1,078,522, No tiene parentesco
  33,025, Trabajador(es) doméstico(s) 23,983, No especificado 17,392.
- 1995 emigrants' destination `P9_7`: ESTADOS UNIDOS DE AMERICA 7,144 of 7,272.

`--validate`: 0/897 (`VALIDATION_REPORT.md`, unchanged).

## Left out

- CGPV 1990's `TIP_HOGAR` 6 (96,370 persons; every one has `N_F_GPOS` 99 and a 9xx
  relationship, so a dwelling without its household composition) is not in its FD («1..5 Y
  7»). It keeps its identity label and the note «códigos observados sin etiqueta en el FD».
- The 1995 groups' definitions («Comprende hijastro (a), entenado (a)…») stay in the PDF.
  INEGI's 1995 «Hijo (a)» includes stepchildren and adopted children, as 1990's group 3 does.
- 2000's detail codes (401–412, 420/430/440, 601–624) look like 1990's `CATPAREN` extended,
  but no 2000 document labels them, so they keep their group's label.

## Tests

- `test_parse_fd_1990_text`: `CATPAREN`'s synonyms joined, a repeated one once.
- `test_parse_catalogs_1995_text` (offline): a synthetic catalog text (a form feed before a
  title, «Comprende» lines, a wrapped label, «31 y 32», the skipped municipal and
  metropolitan sections) and a synthetic FD whose «Ver catálogo de» items take their
  sections. `ENT` keeps its range, and «municipios» gets no catalog.
- `test_label_code_groups` (offline): own labels over group labels, identity labels
  ignored, a sentinel, the note, the key order, core and other editions untouched, and the
  two errors.
- `test_dictionary_fixes_6u` (the bundled YAML): 1990's 107 codes (G00 = G01 labels,
  synonyms, sentinels), 1995's eight groups in both tables, its six place items (41 codes),
  occupation and activity, and 2000's 46 codes in seven groups.
- `test_source_codes_match_2020`: the 1995 and 2000 head codes are now labelled as the head.
  1995's birthplace and 1990 residence carry their catalog's 41 codes (`_OWN_CODES`; out
  of `_NO_CATALOG`).
- **Full suite**: 1802 passed, 1 skipped (30 min, the Mac's full mirror; 6t + 4 new tests).
