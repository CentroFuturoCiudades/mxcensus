# Censuses and intercensal surveys 1990–2025: a user guide

`mxcensus` holds every census, conteo and intercensal survey INEGI has published since
1990 as one family, the `cpv` family. That covers the samples (dwellings, households,
persons, emigrants), the census counts by locality (ITER) and block (AGEB), the EIC 2025
estimates, the geographic frames, and the history of every locality. This guide shows how
to use them.

1. [What is in the family](#1-what-is-in-the-family)
2. [Microdata](#2-microdata)
3. [Derived columns](#3-derived-columns)
4. [Published aggregates](#4-published-aggregates)
5. [Constraints: the sample against the published counts](#5-constraints-the-sample-against-the-published-counts)
6. [Geography across editions](#6-geography-across-editions)
7. [Localities 1900–2020](#7-localities-19002020)
8. [Edition notes](#8-edition-notes)
9. [How the data were checked](#9-how-the-data-were-checked)
10. [Function index](#10-function-index)

Every example runs against the mirror; the outputs shown are the real ones (a test runs
this file, `tests/test_cpv_guide.py`). They use state 1, Aguascalientes, whose files are
small. Files download on first use and are cached (`mxcensus info` shows where).

```pycon
>>> import mxcensus
>>> import pandas as pd
```

## 1. What is in the family

| edition | kind | microdata (per state) | aggregates | weight | frame (`load_mg`) |
|---|---|---|---|---|---|
| **2025** Encuesta Intercensal | sample | `viviendas`, `personas`, `migrantes` | national `estimaciones` | `FACTOR` | MG 2025 |
| **2020** Censo, cuestionario ampliado | sample | `viviendas`, `personas`, `migrantes` | `iter`, `ageb` | `FACTOR` | MG 2020 |
| **2015** Encuesta Intercensal | sample | `viviendas`, `personas` | — | `FACTOR` | MG 2015 |
| **2010** Censo, cuestionario ampliado | sample | `viviendas`, `personas`, `migrantes` | `iter`, `ageb` | `FACTOR` | MG 2010 |
| **2005** II Conteo | sample | `viviendas`, `hogares`, `personas` | `iter` | none | MG 2005 (municipal) |
| **2000** XII Censo General | sample | `viviendas`, `personas`, `migrantes` | `iter` | `FACTOR` | MG 2000 (municipal) |
| **1995** Conteo | sample | `personas`, `migrantes` | `iter` | `FAC_POB`, `FAC_VIV`, `FAC_PROM` | MG 1995 (municipal) |
| **1990** XI Censo General | 10% extract | `personas` | `iter` | none | — |

The samples come from the census's extended questionnaire (2000, 2010, 2020), from a
sample of the count (1995, 2005) or from the intercensal survey itself (2015, 2025).
The ITER and AGEB files are the full census. The EIC 2025 publishes no ITER, only a
national table of estimates (five estimator rows per geography).

The mirror keeps INEGI's files as published: every column is a string, as written.
The loaders turn them into analysis-ready frames. They use **one edition per call**, the
edition's year as `period` (default: the latest edition with that table), and
**`state=`**, an INEGI state code or a list of them. `state` is required for the
per-state files, so a call never downloads the whole country by accident.

## 2. Microdata

### Raw tables

`load_cpv` returns one table as INEGI wrote it, every column a string:

```pycon
>>> raw = mxcensus.load_cpv(table="personas", period=2025, state=1)
>>> raw.shape
(177984, 92)
>>> raw[["ID_VIV", "ID_PERSONA", "SEXO", "EDAD", "FACTOR"]].head(3)
         ID_VIV         ID_PERSONA SEXO EDAD FACTOR
0  010010000001  01001000000100001    3   27      7
1  010010000001  01001000000100002    3   54      7
2  010010000001  01001000000100003    3   31      7
>>> raw["SEXO"].value_counts()
SEXO
3    92564
1    85420
Name: count, dtype: int64
```

It is validated against the dictionary of its schema group (one per edition and table;
see [Dictionaries](#dictionaries)). A value outside the dictionary only warns, and the
frame keeps it.

### Analysis-ready frames

`load_cpv_viviendas`, `load_cpv_personas`, `load_cpv_migrantes` and (2005 only)
`load_cpv_hogares` return labelled frames: coded items become `Categorical` columns with
INEGI's labels, quantities become nullable numbers with their sentinel codes («No
especificado») missing, `FACTOR` is a float, and the frame is indexed by its record key.
Keys and geographic codes stay zero-padded strings. Validation is strict: a code the
dictionary does not know raises.

```pycon
>>> per = mxcensus.load_cpv_personas(2025, state=1)
>>> per[["SEXO", "EDAD", "FACTOR"]].head(3)
                                 SEXO  EDAD  FACTOR
ID_VIV       ID_PERSONA
010010000001 01001000000100001  Mujer    27     7.0
             01001000000100002  Mujer    54     7.0
             01001000000100003  Mujer    31     7.0
>>> per.groupby("SEXO", observed=True)["FACTOR"].sum()
SEXO
Hombre    736415.0
Mujer     798001.0
Name: FACTOR, dtype: float64
```

Σ `FACTOR` is the expanded population: 1,534,416 is the EIC 2025's population of
Aguascalientes. Pass `labels=False` for the raw codes with the key index and a numeric
`FACTOR`.

### Keys and the survey tuple

`load_cpv_survey` loads an edition's tables at once, `(viviendas, personas, migrantes)`,
on indices that nest: a person's index starts with its dwelling's.

```pycon
>>> viv, per, mig = mxcensus.load_cpv_survey(2025, state=1)
>>> [list(frame.index.names) for frame in (viv, per, mig)]
[['ID_VIV'], ['ID_VIV', 'ID_PERSONA'], ['ID_VIV', 'ID_MII']]
>>> round(viv["FACTOR"].sum()), round(per["FACTOR"].sum()), round(mig["FACTOR"].sum())
(449177, 1534416, 26542)
>>> per.join(viv[["NUMPERS", "JEFE_SEXO"]], on="ID_VIV")[["SEXO", "EDAD", "NUMPERS", "JEFE_SEXO"]].head(3)
                                 SEXO  EDAD  NUMPERS JEFE_SEXO
ID_VIV       ID_PERSONA
010010000001 01001000000100001  Mujer    27        4     Mujer
             01001000000100002  Mujer    54        4     Mujer
             01001000000100003  Mujer    31        4     Mujer
```

The emigrants hang from the dwelling, not from a person; a returned emigrant who lives in
the dwelling again carries their person number in `MPERLS` (join it to `NUMPER`). The
keys by edition:

| edition | dwelling | household | person | emigrant |
|---|---|---|---|---|
| 2025, 2020, 2010 | `ID_VIV` | — | `ID_VIV, ID_PERSONA` | `ID_VIV, ID_MII` |
| 2015 | `ID_VIV` | — | `ID_VIV, ID_PERSONA` | — |
| 2005 | `ID_VIV` | `ID_VIV, ID_HOG` (`load_cpv_hogares`) | `ID_VIV, ID_HOG, ID_PERSONA` | — |
| 2000 | `ID_VIV, ID_HOG` (one row per household) | — | `ID_VIV, ID_HOG, ID_PERSONA` | `ID_VIV, ID_HOG, ID_MII` |
| 1995 | `ID_VIV` (built from the persons) | — | `ID_VIV, ID_HOG, ID_PERSONA` | `ID_VIV, ID_HOG, ID_MII` |
| 1990 | `ID_VIV` (built from the persons) | — | `ID_VIV, ID_PERSONA` | — |

The 1990–2005 files have no key column: the loaders derive the keys from INEGI's
composite parts (entity, municipality, locality, dwelling and household numbers; 2000's
persons are unnumbered, so their key is their order in the household). 1990 and 1995
publish person files only, each person carrying the dwelling's items:
`load_cpv_viviendas` builds their dwellings from them, one row per dwelling. 2010's keys
are serials unique within a state only (see [Several states](#several-states-and-editions)).

### Several states and editions

A list of states concatenates them. Censo 2010's keys repeat across states, so its keyed
loaders refuse several states unless `harmonize=True`, which makes the keys national:

```pycon
>>> mxcensus.load_cpv_personas(2010, state=[1, 2])
Traceback (most recent call last):
...
ValueError: CPV personas Censo de Población y Vivienda 2010 (2010): the record keys are unique within a state only, ...
>>> mxcensus.load_cpv_personas(2010, state=[1, 2], harmonize=True).index[0]
('010000019178', '01000001917800001')
```

Each edition keeps INEGI's own column names. `harmonize=True` puts the **core** on the
latest edition's names, which are also the Marco Geoestadístico's: `ENT`/`MUN` become
`CVE_ENT`/`CVE_MUN` (in the ITER also `ENTIDAD`/`LOC` → `CVE_ENT`/`CVE_LOC`, in the AGEB
file `AGEB`/`MZA` → `CVE_AGEB`/`CVE_MZA`) and a `CVEGEO` is derived; codes the 2015 CSVs
wrote without their leading zero are padded; 2010's keys become national; 2000/2005 write
a woman's `SEXO` as 2, which becomes 3, as in the other editions; and 1995 gets a
`FACTOR`. Rows, Σ `FACTOR` and every other column stay as they were. Stack editions
yourself:

```pycon
>>> frames = {p: mxcensus.load_cpv_personas(p, state=1, harmonize=True)
...           for p in (2010, 2015, 2020, 2025)}
>>> per = pd.concat(frames, names=["PERIOD"])
>>> per.groupby(["PERIOD", "SEXO"], observed=True)["FACTOR"].sum().unstack()
SEXO      Hombre     Mujer
PERIOD
2010    573064.0  605736.0
2015    640091.0  672453.0
2020    690425.0  730773.0
2025    736415.0  798001.0
```

Only the core is comparable as is: the keys, the geography, the sample design
(`ESTRATO`, `UPM`, `COBERTURA`), `FACTOR`, `SEXO`, `EDAD`, `TAMLOC` and (2015–2025)
`CLAVIVP`. A column with the same name in two editions may still have other codes: the
EIC 2025 renumbered `SITUA_CONYUGAL` and swapped two `DHSERSAL` codes, and Censo 2010
numbered its education levels (`NIVACAD`) otherwise. Where categories differ, `pd.concat` turns a `Categorical`
into strings. Compare editions on the [derived columns](#3-derived-columns), which
recode each edition's items onto one set of categories.

### Dictionaries

The labels come from INEGI's data dictionaries (the FD workbooks of 2005–2025, the PDF
annexes of 1990–2000) under a hand-curated core. Each edition and table is a schema
group:

```pycon
>>> groups = mxcensus.cpv_schema_map()["personas"]["groups"]
>>> pd.Series({gid: ", ".join(g["periods"]) for gid, g in groups.items()})
g01    1990
g02    1995
g03    2000
g04    2005
g05    2010
g06    2010
g07    2015
g08    2020
g09    2025
dtype: str
>>> mxcensus.variables_cpv_labels("personas", "g09")["SEXO"]["Categorías"]
{'1': 'Hombre', '3': 'Mujer'}
```

(2010 has two groups because state 15's files spell one column in lower case.) An entry
holds `Descripción`, `Pregunta`, `Tipo` (`categorical`, `numeric`, `string`),
`Categorías`, `Especiales` (the sentinel codes), `Rango` and, for codes in a
classification (occupation, activity, places, languages), its `Catálogo`.

## 3. Derived columns

`derived=True` adds analysis columns computed from the raw codes: those of the legacy
`load_extended_*` loaders (age groups, education level, activity, the health-coverage and
commute dummies…) and more. Each edition gets the columns its items support, recoded
onto Censo 2020's categories, so the columns line up across editions:

```pycon
>>> per = mxcensus.load_cpv_personas(2000, state=1, derived=True)
>>> per.groupby("EDUC_INEGI", observed=True)["FACTOR"].sum().round()
EDUC_INEGI
Sin Educación        81623.0
Primaria_incom      235960.0
Primaria_com        147198.0
Secundaria_incom     56908.0
Secundaria_com      114085.0
Técnica_primaria      7884.0
Posbásica           168641.0
No especificado      11427.0
Blanco por pase     117052.0
Name: FACTOR, dtype: float64
>>> mxcensus.cpv_derivations("personas", 2000)[["COLUMN", "SOURCES"]].head(4)
         COLUMN             SOURCES
0      EDAD_CAT                EDAD
1     EDAD_QUIN                EDAD
2  INGTRMEN_CAT            INGTRMEN
3   INGTRMEN_SM  INGTRMEN, ENT, MUN
```

`cpv_derivations(table, period)` lists an edition's columns and the raw items each one
reads. For Censo 2020, the columns the legacy loaders also make are identical to theirs.
What each edition gets (a `*` groups a set of dummies):

<!-- derived-matrix: generated from cpv_derivations(), checked by tests/test_cpv_guide.py -->
| table | column | 1990 | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|---|---|
| personas | `EDAD_CAT` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `EDAD_QUIN` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `INGTRMEN_CAT` | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `INGTRMEN_SM` |  |  | ✓ |  | ✓ | ✓ | ✓ |  |
| personas | `HORTRA_CAT` | ✓ | ✓ | ✓ |  | ✓ |  | ✓ | ✓ |
| personas | `EDUC` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `EDUC_INEGI` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `EDUC_INEGI_DET` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `OCUPACION_C_COARSE` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `ACTIVIDADES_C_COARSE` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `SECTOR` | ✓ |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `DIS_CON` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `DIS_LIMI` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `DISCAPACIDAD` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `LIMITACION` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `SIN_DISC_LIM` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `LIM_ACTIVIDAD` |  |  |  |  | ✓ |  |  |  |
| personas | `DHSERSAL_*` |  |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `MED_TRASLADO_ESC_*` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `MED_TRASLADO_TRAB_*` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `MED_TRASLADO_ESC_*_T` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `MED_TRASLADO_TRAB_*_T` |  |  |  |  |  |  | ✓ | ✓ |
| personas | `ENT_PAIS_ASI_INEGI` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `ENT_PAIS_TRAB_INEGI` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `LUGAR_RES_5A` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `LUGAR_ASI` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `LUGAR_TRAB` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `CONACT_CAT` | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `SITUA_CONYUGAL_CAT` | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `ENT_PAIS_NAC_CAT` | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `ENT_PAIS_NAC_INEGI` | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| personas | `ENT_PAIS_RES_CAT` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `IDENT_MADRE_CAT` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `IDENT_PADRE_CAT` |  |  |  |  |  | ✓ | ✓ | ✓ |
| personas | `IDENT_PAREJA_CAT` |  |  |  |  | ✓ | ✓ | ✓ | ✓ |
| personas | `MADRE_EN_VIVIENDA` |  |  |  |  | ✓ | ✓ | ✓ | ✓ |
| personas | `PADRE_EN_VIVIENDA` |  |  |  |  | ✓ | ✓ | ✓ | ✓ |
| personas | `IDENT_HIJO_CAT` |  |  |  |  |  |  | ✓ |  |
| personas | `RELIGION_CAT` | ✓ |  | ✓ |  | ✓ |  | ✓ |  |
| personas | `RELIGION_INEGI` |  |  |  |  | ✓ |  |  |  |
| personas | `HOGJEF_SEXO` |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `HOG_IND` |  |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `HOG_AFRO` |  |  |  |  |  |  |  | ✓ |
| personas | `LINEA_PARENTESCO` | ✓ |  |  | ✓ | ✓ | ✓ | ✓ | ✓ |
| personas | `CLASE_HOG` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| viviendas | `HOG_IND` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| viviendas | `HOG_AFRO` |  |  |  |  |  |  |  | ✓ |
| viviendas | `CLAVIVP_CAT` | ✓ |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| viviendas | `JEFE_SEXO` |  |  | ✓ | ✓ | ✓ |  |  |  |
| viviendas | `CUADORM_CAT` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| viviendas | `TOTCUART_CAT` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| viviendas | `DRENAJE_CAT` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| viviendas | `INGTRHOG_CAT` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| viviendas | `PRIMER_HOGAR` |  |  | ✓ |  |  |  |  |  |
| viviendas | `TOTCUART_INEGI` |  |  | ✓ |  |  |  |  |  |
| viviendas | `OCUP_CUARTO_CAT` |  |  |  |  | ✓ | ✓ | ✓ | ✓ |
| viviendas | `CLASE_HOG` |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| viviendas | `INGR_OTROS` |  |  |  |  |  | ✓ | ✓ | ✓ |
| viviendas | `FINANCIAMIENTO_*` |  |  |  |  |  | ✓ | ✓ | ✓ |
| hogares | `HOG_IND` |  |  |  | ✓ |  |  |  |  |
| hogares | `CLAVIVP_CAT` |  |  |  | ✓ |  |  |  |  |
| hogares | `JEFE_SEXO` |  |  |  | ✓ |  |  |  |  |
<!-- /derived-matrix -->

Some columns come in pairs, the legacy rule beside INEGI's own. Use INEGI's to reproduce
its published numbers:

| topic | legacy rule (Censo 2020 extended loaders) | INEGI's rule |
|---|---|---|
| education | `EDUC`: technical studies after primaria count as primaria completa | `EDUC_INEGI`: apart, as every ITER 1990–2020; `EDUC_INEGI_DET` also splits «Posbásica» into media superior, superior and posgrado |
| disability | `DIS_CON`, `DIS_LIMI`: a difficulty of unknown degree is unspecified; the disabled count as limited too | `DISCAPACIDAD`, `LIMITACION` (limitation without disability), `SIN_DISC_LIM` |
| places | `ENT_PAIS_NAC_CAT`, `ENT_PAIS_RES_CAT`: an unspecified entity counts as another entity | `ENT_PAIS_NAC_INEGI`, `LUGAR_RES_5A`, `LUGAR_ASI`, `LUGAR_TRAB`, `ENT_PAIS_*_INEGI`: «No especificado» apart; the `LUGAR_*` by municipality |
| religion (2010) | `RELIGION_CAT`: Censo 2020's grouping (neo-Israelites evangelical) | `RELIGION_INEGI`: the 2010 ITER's (neo-Israelites among other credos) |

Two legacy health-coverage dummies are renamed: `DHSERSAL_Popular_NGenración_SBienestar`
is `DHSERSAL_SALUD_PUBLICA` and `DHSERSAL_IMSS_Prospera/Bienestar` is
`DHSERSAL_IMSS_BIENESTAR`, because the EIC 2025 swapped the two codes and widened the
first (any public health centre, INSABI and Seguro Popular included). 2000–2015 have no
`DHSERSAL_IMSS_BIENESTAR` (not asked), and CGPV 2000, which asked one question per
institution, no `DHSERSAL_SALUD_PUBLICA`, `DHSERSAL_Privado` or `DHSERSAL_ISSSTE_E`.

A few columns read another file of the edition. The household head's sex on the
2000/2005/2010 dwellings (`JEFE_SEXO`, a raw item from 2020 on) and the indigenous
household (`HOG_IND`) on the dwellings are read from the person file. The persons'
household class (`CLASE_HOG`) is read from the dwelling file. The loader reads only the
columns it needs. `HOG_IND` is on both frames, so a person ↔ dwelling join needs a
suffix.

Some derived columns are worth knowing by name. `OCUPACION_C_COARSE` is the SINCO
two-digit occupation group; CGPV 2000 coded occupations in the older CMO, bridged to
SINCO groups through INEGI's comparison table (see
[CMO_SINCO_REPORT.md](CMO_SINCO_REPORT.md)). `SECTOR` gives INEGI's three economic
sectors. `HOGJEF_SEXO` is the sex of each person's household head. `LINEA_PARENTESCO`
gives Censo 2020's nine kinship lines. `INGTRMEN_SM` is income from work in minimum wages
(each municipality's wage at the edition's date). `TOTCUART_INEGI` is CGPV 2000's rooms
less an exclusive kitchen, as its ITER counts them.

## 4. Published aggregates

### ITER and AGEB

`load_cpv_iter` returns an edition's ITER: one row per state, municipality and
locality, with an ordered `NIVEL`. The 1990–2010 indicators that the crosswalk pairs with
Censo 2020's take its name:

```pycon
>>> it = mxcensus.load_cpv_iter(2020, state=1)
>>> it["NIVEL"].value_counts()
NIVEL
localidad    2022
agregado       24
municipal      11
estatal         1
Name: count, dtype: int64
>>> it90 = mxcensus.load_cpv_iter(1990, state=1, nivel="municipal")
>>> it90[["NOM_MUN", "POBTOT"]].head(3)
                                NOM_MUN  POBTOT
CVE_ENT CVE_MUN CVE_LOC
01      001     0000     Aguascalientes  506274
        002     0000           Asientos   32225
        003     0000           Calvillo   48440
>>> {k: v for k, v in mxcensus.cpv_iter_crosswalk()["P15PRI_CO"].items() if k.isdigit()}
{'2020': 'P15PRI_CO', '2010': 'P15PRI_CO', '2000': 'P15_CPRIMA', '1990': 'PRIM_COM'}
```

INEGI reserves the counts of localities of one or two dwellings (`*`). These cells are
missing in the frame. The `agregado` rows (`CVE_LOC` 9998/9999) are the reserved
localities summed. `impute=True` (the default) fills a reserved count with 0 when the
municipality's total equals the sum of its localities' known values. In the Conteo 1995
the small localities exist only as the `agregado` rows. The crosswalk marks
`Comparable: false` where an older definition differs (2005/2010's indigenous households
count the head or partner only), and keeps an older column under its own name where it
is another date or definition (CGPV 2000's `PNACOENT` includes the born abroad).

`load_cpv_ageb(period, state=…)` (2010, 2020) does the same for urban AGEBs and blocks.
`load_cpv_census(period, state=…)` (2010, 2020) is the legacy `load_census` on the
`cpv_` files: state, municipality, locality and AGEB counts with the collective
population added and imputed. For 2020 it equals `load_census` in all 32 states.

### The EIC 2025 estimates

`load_cpv_estimaciones` reshapes INEGI's national table of estimates to one row per
geography and one column per indicator. Geographies are the nation, the states, the
municipalities, the localities of 50,000+ and each state's remainder. `estimador=`
selects the estimate (`valor`), its standard error (`ee`), the 90% limits (`li`, `ls`)
or the coefficient of variation (`cv`):

```pycon
>>> est = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1)
>>> est[["NOM_MUN", "POBTOT", "PCN_PEA"]].head(3)
                                NOM_MUN   POBTOT  PCN_PEA
CVE_ENT CVE_MUN CVE_LOC
01      001     0000     Aguascalientes  1025505    57.82
        002     0000           Asientos    53631    50.28
        003     0000           Calvillo    55794    51.17
>>> cv = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1, estimador="cv")
>>> float(cv["POBTOT"].max())
5.89
```

Most indicators are published as percentages (`PCN_*`). `counts=True` adds the count
behind each one whose base is known, named without the prefix (`PCN_VPH_PISOTI` →
`VPH_PISOTI` = percentage × base / 100). The bases were found on the microdata, not
read from the descriptions. The percentages are rounded to two decimals, so a count can
be off by base × 0.00005.

```pycon
>>> cnt = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1, counts=True)
>>> cnt[["PCN_PEA", "P_12YMAS", "PEA"]].round({"PEA": 0}).head(3)
                         PCN_PEA  P_12YMAS       PEA
CVE_ENT CVE_MUN CVE_LOC
01      001     0000       57.82    853890  493719.0
        002     0000       50.28     41626   20930.0
        003     0000       51.17     44893   22972.0
```

## 5. Constraints: the sample against the published counts

The samples' weights do not reproduce every published count of their edition. For
small-area estimation, calibration or synthetic populations you need, for each published
indicator, the sample records it counts. `cpv_constraints(table, period)` gives them:
indicator → cells, a cell being `{variable: [categories]}` on the labelled frame with
`derived=True` (every variable at once; `{}` = every record).

```pycon
>>> cons = mxcensus.cpv_constraints("personas", 2025)
>>> len(cons)
214
>>> cons["P_15A49_F"]
{'EDAD_CAT': ['15-17', '18-24', '25-49'], 'SEXO': ['Mujer']}
>>> cons["PNACOE_F"]
{'ENT_PAIS_NAC_INEGI': ['OtraEnt'], 'SEXO': ['Mujer']}
```

The constraints by edition (count constraints + [ratio constraints](#ratios-and-averages)):

<!-- constraint-counts: generated from cpv_constraints() and cpv_ratio_constraints(), checked by tests/test_cpv_guide.py -->
| edition | personas | viviendas | hogares |
|---|---|---|---|
| 2025 | 214 + 15 | 93 + 2 | — |
| 2020 | 161 + 4 | 46 + 2 | — |
| 2015 | 0 | 0 | — |
| 2010 | 147 + 4 | 28 + 2 | — |
| 2005 | 87 | 20 | 3 |
| 2000 | 70 | 36 + 2 | — |
| 1995 | 11 | 4 + 1 | — |
| 1990 | 24 | 10 + 2 | — |
<!-- /constraint-counts -->

Each key is the column the edition publishes the indicator under: a column of
`load_cpv_iter(period)`, or of `load_cpv_estimaciones(counts=True)` for 2025. The EIC 2015
has no published aggregate in the mirror, hence no constraints. A constraint exists
where the edition publishes the indicator and its microdata hold every variable and
category the cells name. Where the edition's definition differs, the cells follow it
(e.g. 2000's religions count the population of 5 and over, as its ITER).

`get_tables_dict(cons, frame.dtypes)` groups them into contingency tables by variable set.
To count them on the sample, turn each indicator into a 0/1 column:

```pycon
>>> def design(df, constraints):
...     """Each record's 0/1 term of each count constraint."""
...     cols = {}
...     for ind, cells in constraints.items():
...         m = pd.Series(True, index=df.index)
...         for var, cats in cells.items():
...             m &= df[var].isin(cats)
...         cols[ind] = m.astype(float)
...     return pd.DataFrame(cols)
>>> per = mxcensus.load_cpv_personas(2025, state=1, derived=True)
>>> X = design(per, cons)
>>> sample = X.mul(per["FACTOR"], axis=0).groupby(per["CVE_MUN"]).sum()
>>> est = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1, counts=True)
>>> published = est.droplevel(["CVE_ENT", "CVE_LOC"])[list(cons)].astype(float)
>>> sample.loc["002", ["POBTOT", "POBFEM", "P_3YMAS_F"]]
POBTOT       53631.0
POBFEM       27940.0
P_3YMAS_F    26818.0
Name: 002, dtype: float64
>>> published.loc["002", ["POBTOT", "POBFEM", "P_3YMAS_F"]]
POBTOT       53631.0
POBFEM       27940.0
P_3YMAS_F    26818.0
Name: 002, dtype: float64
```

The EIC 2025's weights are calibrated to its estimates, so the published counts are
reproduced exactly. The counts derived from percentages match to the percentages'
rounding:

```pycon
>>> printed = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1).columns
>>> exact = [c for c in cons if c in printed]
>>> len(exact), float((sample[exact] - published[exact]).abs().max().max())
(37, 0.0)
>>> share = lambda f: f.div(f["POBTOT"], axis=0)
>>> float((share(sample) - share(published)).abs().max().max()) < 0.0001
True
```

For 1990–2020 the published side is the ITER: the full census or count, to which the
samples' weights are not calibrated, so each sample sits within its band of it. Where a
census sample is the census (the municipalities it enumerated completely, `FACTOR` 1 for
everyone), every Censo 2010 constraint and every CGPV 2000 dwelling constraint equals the
ITER exactly. What still differs there (2000's imputed schooling and income, 2020's
health affiliation and religion) is INEGI's processing of the census.

### Which total

Each person set holds two totals, both counting every sampled person: `POBTOT`, the
ITER's, which also counts the population of collective dwellings and without a dwelling,
and the samples' own universe — `POBHOG`, the population in households (2000–2025), or
`OCUPVIVPAR`, the occupants of private dwellings (1990, 1995). A fit uses one of them:

| edition | Σ `FACTOR` (persons) adds up to |
|---|---|
| 2025 | `POBTOT` = `POBHOG`, in every municipality |
| 2020 | `POBHOG`, in every state |
| 2010, 2000 | neither: above `POBHOG`, within about 1% of `POBTOT` |
| 1995 | `OCUPVIVPAR`, in every state but Chiapas |
| 2005, 1990 | unweighted |

### Ratios and averages

A published share of a base that is not published, or an average, is no count. It still
constrains the weights: `r = scale × Σ w·N / Σ w·D` over a geography's records, i.e.
Σ w·(N − r / scale · D) = 0. `cpv_ratio_constraints(table, period)` gives each one's
numerator and denominator cells, the value a record counts instead of 1 (children,
years of schooling, occupants, rooms), the columns that must be known (who did not say
is left out of both sides) and the scale. `cpv_ratio_terms(frame, ratios)` gives each
record's N and D:

```pycon
>>> ratios = mxcensus.cpv_ratio_constraints("personas", 2025)
>>> num, den = mxcensus.cpv_ratio_terms(per, ratios)
>>> w, mun = per["FACTOR"], per["CVE_MUN"]
>>> scale = pd.Series({ind: r["scale"] for ind, r in ratios.items()})
>>> ours = scale * num.mul(w, axis=0).groupby(mun).sum() / den.mul(w, axis=0).groupby(mun).sum()
>>> ours[["GRAPROES", "PROM_HNV", "PCN_HF"]].round(2).head(3)
         GRAPROES  PROM_HNV  PCN_HF
CVE_MUN
001         11.43      1.87    4.31
002          9.08      2.40    6.14
003          8.57      2.51    5.58
>>> est = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1).droplevel(["CVE_ENT", "CVE_LOC"])
>>> est[["GRAPROES", "PROM_HNV", "PCN_HF"]].head(3)
         GRAPROES  PROM_HNV  PCN_HF
CVE_MUN
001         11.43      1.87    4.31
002          9.08       2.4    6.14
003          8.57      2.51    5.58
```

### Edition specifics

- **CGPV 2000**'s dwelling file has one row per household. Its dwelling constraints count
  the first household's row (`PRIMER_HOGAR` «Sí»), its household constraints (`TOTHOG`,
  `HOGJEF_*`) every row. CGPV 1990's and 2000's dwelling constraints count every private
  dwelling: their «Otro» classes carry the items, and their ITERs count them.
- **Conteo 2005**: its dwelling rows are dwellings while its ITER counts households, so
  its household constraints are `cpv_constraints("hogares", 2005)`, counted on
  `load_cpv_hogares(2005, derived=True)`.
- **EIC 2025**: `HOG_MEN_ALIM` (households with minors, the base of the minors' food
  items) has no cell: the questionnaire's filter of minors is not in the microdata.

## 6. Geography across editions

### The Marco Geoestadístico

`load_mg(layer, state=…, period=…)` returns one layer of a frame as a GeoDataFrame:
2020 and 2025 (15 layers + islands), the EIC 2015's (12 layers), 2010 (`ent`, `mun`, `a`,
`l`, `lpr`) and the municipal frames 2005, 2000 (+ urban AGEBs) and 1995. Each edition's
microdata, ITER and estimates use its own frame's codes (table in
[§1](#1-what-is-in-the-family)). Every layer comes on EPSG:6372 by default, without
moving a coordinate (INEGI spells its projection two ways). The codes are strings, and
the estimates' and ITER's `CVEGEO` has 9 characters, so join a municipal layer on
`CVE_ENT`/`CVE_MUN`:

```pycon
>>> mun = mxcensus.load_mg("mun", state=1, period=2025)
>>> est = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1).reset_index()
>>> geo = mun.merge(est[["CVE_ENT", "CVE_MUN", "POBTOT"]], on=["CVE_ENT", "CVE_MUN"])
>>> geo[["CVEGEO", "NOMGEO", "POBTOT"]].sort_values("CVEGEO").head(3)
   CVEGEO          NOMGEO   POBTOT
0   01001  Aguascalientes  1025505
10  01002        Asientos    53631
9   01003        Calvillo    55794
```

### Municipalities

Municipalities are created between editions (2,428 in 1995, 2,457 in 2015, 2,478 in
2025; none was retired). `cpv_mun_lineage()` lists each new code with the parents that
gave it at least 5% of its area. `cpv_municipal_units(start, end)` maps every
municipality of `end` to a unit stable between two frames: aggregate both editions by
`UNIT`. Quintana Roo created Tulum, Bacalar and Puerto Morelos between 2000 and 2020:

```pycon
>>> units = mxcensus.cpv_municipal_units(2000, 2020).set_index("CVEGEO")["UNIT"]
>>> pob = {p: mxcensus.load_cpv_iter(p, state=23, nivel="municipal")
...           .assign(CVE=lambda d: d["CVEGEO"].str[:5]).set_index("CVE")["POBTOT"]
...           .groupby(units).sum()
...        for p in (2000, 2020)}
>>> pd.DataFrame(pob)
         2000    2020
UNIT
23001   60091   88626
23002  124117  464511
23003   11313   22686
23004  208164  275402
23005  419815  938424
23006   31052   39165
23007   20411   29171
```

Each new municipality joins its parents: 23002 is Felipe Carrillo Puerto with
Solidaridad and Tulum, 23004 Othón P. Blanco with Bacalar, 23005 Benito Juárez with
Puerto Morelos. 1990 has no frame, so the lineage starts in 1995: the 25 municipality
codes the 1995 ITER has and the 1990 ITER lacks (Aguascalientes's El Llano and San
Francisco de los Romo, 16 in Tlaxcala…) need their parents by hand.

### Localities

Localities change far more: tens of thousands are dropped, created, renumbered, moved or
absorbed between two censuses. `cpv_loc_lineage()` lists every link between two locality
codes that INEGI's Archivo Histórico de Localidades documents from 1990 on, dated to the
first edition whose codes reflect it:

```pycon
>>> lin = mxcensus.cpv_loc_lineage()
>>> lin["KIND"].value_counts()
KIND
absorption      18263
code            12336
separation       1799
counted_with      535
Name: count, dtype: int64
```

`code` is the same locality under another code (a move to another municipality, a
renumbering, a duplicate registration). `absorption` means `FROM` joined `TO`
(conurbation, fusion). `separation` means `FROM` left `TO`. `counted_with` means `FROM`
was counted with `TO` at that census only. `CONFIRMED` means both localities' records
state the link. `cpv_locality_units(start, end)` gives the codes a link joins between
two editions (the ITERs 1990–2020, MG 2015 and MG 2025); every other code is a unit of
its own:

```pycon
>>> units = mxcensus.cpv_locality_units(2000, 2020).set_index("CVEGEO")["UNIT"]
>>> pob = {p: mxcensus.load_cpv_iter(p, state=1, nivel="localidad")
...           .assign(UNIT=lambda d: d["CVEGEO"].map(units).fillna(d["CVEGEO"]))
...           .groupby("UNIT")["POBTOT"].sum()
...        for p in (2000, 2020)}
>>> pd.DataFrame(pob).loc[["010010001", "010050001"]]
             2000    2020
UNIT
010010001  594934  863893
010050001   29437   63805
```

`absorptions=False` joins only the same locality under another code. `confirmed=True`
uses only the links both records state. In the example, Aguascalientes city's unit holds
the city (594,092 inhabitants in 2000) and the 25 localities of 2000 that are part of it
by 2020. The lineage leaves out what the archive cannot
decide (moves stated without a code it cannot pair, codes INEGI reused); see
[LOC_LINEAGE_REPORT.md](LOC_LINEAGE_REPORT.md).

## 7. Localities 1900–2020

INEGI's Archivo Histórico de Localidades files every locality's history under its
**last** code, so its population at every census and count since 1900 is one panel with
no code bridge. `load_ahl_poblacion` is that historical ITER:

```pycon
>>> pob = mxcensus.load_ahl_poblacion(state=1)
>>> pob.loc[("01", "001", "0001"), ["NOM_LOC", "POBTOT"]].tail(4)
                          NOM_LOC  POBTOT
EVE_CENSAL
2000        Aguascalientes (Cab.)  594092
2005        Aguascalientes (Cab.)  663671
2010        Aguascalientes (Cab.)  722250
2020        Aguascalientes (Cab.)  863893
>>> pob["POBTOT"].unstack("EVE_CENSAL").sum()[[1900, 1950, 2000, 2020]]
EVE_CENSAL
1900      90753
1950     179935
2000     944285
2020    1425607
dtype: Int64
```

The populations agree with the ITERs in all but 2–11 localities per census 1995–2020.
INEGI copies a locality's rows to its new code when the code changes (since 2010); those
copies are dropped (`copies=True` keeps them, flagged). Before 1990 the archive holds the
present catalog's localities, not the old censuses' full listings: 83–89% of the
national population 1900–1960 ([AHL_REPORT.md](AHL_REPORT.md)).
`load_ahl_localidades(state=…, geometry=True)` gives one row per locality with its
coordinates. `load_ahl(table, state=…)` gives the four tables as published.

## 8. Edition notes

**EIC 2025.** It is representative of all 2,478 municipalities and of the 233 localities
of 50,000+ (`LOC50K`; `0000` = the rest). `COBERTURA` says whether a municipality was
enumerated completely, sampled, or had too small a sample. The weights are calibrated to
the estimates: Σ `FACTOR` equals the published population and dwellings at every
geography. Some codes were renumbered against 2020 (`SITUA_CONYUGAL` 01–09, two
`DHSERSAL` codes swapped, two country codes); the derived columns recode them.

**Censo 2020** (cuestionario ampliado). The weights add up to `POBHOG`, the population in
households (125.5 M nationally), not the census total. The files hold the same values as
the legacy `personas_NN`/`viviendas_NN`/`iter_NN`/`resargebub_NN`, as INEGI's text, and
the derived columns equal the legacy `load_extended_*` ones.

**EIC 2015.** It has no emigrant table and no ITER. Its CSVs write codes without their
leading zero (`ID_VIV`, `ID_PERSONA` in states 01–09; `CLAVIVP`): compare them as
numbers, or use `harmonize=True`, which pads them. Its frame is INEGI's closure
cartography of the survey (MG 2015, 2,457 municipalities).

**Censo 2010** (cuestionario ampliado). Its keys are serials within a state. It measured
disability as limitation in activity (`LIM_ACTIVIDAD`, `DISCAP1`–`8`), another question
than 2020's. Its `TAM_LOC` has four classes and is not `TAMLOC`. Its place of work holds
both the entity and the country catalogs in one item.

**Conteo 2005.** The sample has no weight: counts are sample counts. It is the only
edition with a household table; a dwelling can hold several households.

**CGPV 2000.** The dwelling file has one row per household (3.1% of the rows share a
dwelling): count dwellings on `PRIMER_HOGAR` («Sí»). `FACTOR` is a ratio estimator on
preliminary counts, so it comes close to the ITER without matching it. Chiapas's public
sample is not the one INEGI tabulated (its counts differ). Religion was asked of persons
of 5 and over. Occupations are CMO codes (bridged to SINCO groups).

**Conteo 1995.** It publishes person files only. There are three weights: `FAC_POB`
(persons), `FAC_VIV` (dwellings, households, emigrants) and `FAC_PROM` (health coverage
and disability). `harmonize=True` sets `FACTOR` to `FAC_POB` (`FAC_VIV` for emigrants).
Its ITER publishes the localities of one or two dwellings only as sums and has no rows for
15 municipalities of Chiapas (Ocosingo, Las Margaritas, Altamirano…); Chiapas's person
weights carry the state's official total, 17% above its ITER.

**CGPV 1990.** It is a 10% extract with no weight, published as person files only. 0
means «not asked». Income is in old pesos (the derived columns divide by 1,000). There
is no geographic frame.

**Memory.** One state of one edition fits easily; the largest (the EIC 2025's State of
México with `load_cpv_survey`) peaks at about 6.4 GB. Load states one at a time and
aggregate.

## 9. How the data were checked

| report | what it checks |
|---|---|
| [VALIDATION_REPORT.md](VALIDATION_REPORT.md) | every mirrored file against its schema group's dictionary: 0 failures in 897 files |
| [INCONSISTENCY_REPORT.md](INCONSISTENCY_REPORT.md) | the columns each edition and table adds or drops |
| [TABULADOS_REPORT.md](TABULADOS_REPORT.md) | the derived columns and raw items against every value of INEGI's sample tabulados (Censo 2010, EIC 2015 and Censo 2020 exact to the person in every state; CGPV 2000 within its band): 797,781 cells |
| [LOC_LINEAGE_REPORT.md](LOC_LINEAGE_REPORT.md) | the locality lineage against every ITER's and frame's codes |
| [AHL_REPORT.md](AHL_REPORT.md) | the historical populations against every ITER 1990–2020 |
| [CMO_SINCO_REPORT.md](CMO_SINCO_REPORT.md) | CGPV 2000's occupation bridge |

The implementation history, one note per unit, is in `STEP_*.md` (the unit table in
[PLAN.md](PLAN.md)).

## 10. Function index

| function | returns |
|---|---|
| `load_cpv(table=, period=, state=)` | one table as published, every column a string |
| `load_cpv_viviendas` / `_personas` / `_migrantes` / `_hogares` | labelled frames indexed by their key (`harmonize=`, `labels=`, `derived=`) |
| `load_cpv_survey(period, state=)` | `(viviendas, personas, migrantes)` on nested indices |
| `variables_cpv_labels(table, gid)`, `cpv_schema_map()`, `variables_cpv_core()` | dictionaries and schema groups |
| `cpv_derivations(table, period)` | the derived columns of an edition |
| `load_cpv_iter` / `load_cpv_ageb` / `load_cpv_census` | the census aggregates, harmonized and labelled |
| `cpv_iter_crosswalk()` | the ITER/AGEB indicators across editions |
| `load_cpv_estimaciones(estimador=, nivel=, counts=)` | the EIC 2025 estimates |
| `cpv_constraints(table, period)`, `get_tables_dict` | count constraints: indicator → cells |
| `cpv_ratio_constraints(table, period)`, `cpv_ratio_terms` | ratio and average constraints |
| `load_mg(layer, state=, period=)` | Marco Geoestadístico layers |
| `cpv_mun_lineage()`, `cpv_municipal_units(start, end)` | municipalities across frames |
| `cpv_loc_lineage()`, `cpv_locality_units(start, end)` | localities across editions |
| `load_ahl`, `load_ahl_poblacion`, `load_ahl_localidades` | the Archivo Histórico de Localidades |
