"""Derived analysis columns on the CPV microdata (the legacy ``load_extended_*`` set) and
the census constraints per edition.

The legacy loaders (``extended_personas``/``extended_viviendas``: Censo 2020 only, frozen)
add coarse categories (``EDAD_CAT``, ``EDUC``, ``CONACT_CAT``…), indicator dummies
(``DHSERSAL_*``, ``MED_TRASLADO_*``, ``FINANCIAMIENTO_*``) and flags (``DIS_CON``/
``DIS_LIMI``) to the cuestionario ampliado. :func:`derive` adds the same columns to a CPV
frame of any edition whose source items carry the same codes. ``load_cpv_personas``/
``load_cpv_viviendas``/``load_cpv_survey`` call it with ``derived=True``.

**How.** Each derivation (:data:`_DERIVATIONS`) names its source items, the editions it is
verified for, and a function of the source codes. The codes are read from the **raw**
frame (before labelling), translated into the Censo 2020 code space by the edition's
recode table (:data:`_RECODE`; identity unless listed), then mapped with the legacy
dictionaries (``variables_personas.yaml``/``variables_viviendas.yaml``). The 2020 columns
therefore equal the legacy ones (tested state by state). Two differences, both deliberate:

- ``DHSERSAL_SALUD_PUBLICA`` / ``DHSERSAL_IMSS_BIENESTAR`` replace the legacy
  ``DHSERSAL_Popular_NGenración_SBienestar`` / ``DHSERSAL_IMSS_Prospera/Bienestar``: the
  EIC 2025 swapped the two codes and widened one (:data:`_RECODE`), so both editions use
  names that fit both.
- The dummy sets (``MED_TRASLADO_ESC_*``, ``MED_TRASLADO_TRAB_*``, ``FINANCIAMIENTO_*``)
  are fixed: one column per code, also for codes no one in the frame reported (the legacy
  loaders only create the observed ones). As in the legacy loaders, a blank second or
  third item sets the ``…_Blanco por pase`` dummy.

Several columns are new: ``SECTOR`` (below), ``DISCAPACIDAD``/``LIMITACION``, INEGI's
definitions of disability and limitation (code 8, «degree unknown», is a disability; a
limitation excludes the disabled; the legacy ``DIS_CON``/``DIS_LIMI`` count otherwise and
are kept as they are),
``SIN_DISC_LIM``, INEGI's population without either or a mental condition (its
``PSIND_LIM``), and ``MADRE_EN_VIVIENDA``/``PADRE_EN_VIVIENDA`` (whether the mother/father lives in the
dwelling: the one part of ``IDENT_MADRE``/``IDENT_PADRE`` Censo 2010 also asked).
CGPV 2000's, the Conteo 2005's and Censo 2010's dwellings get ``JEFE_SEXO``, the item
Censo 2020 publishes: the household head's ``SEXO``, which the dwelling loader attaches
from the person file (``cpv._attach_heads``), so ``derive`` reads it as a dwelling source.
The persons of every edition from 1995 on get ``HOGJEF_SEXO`` (6t), the sex of their own
household's head, with ``JEFE_SEXO``'s labels: the ``SEXO`` of the person of the same
household (``ID_HOG`` in 1995–2005; the dwelling in 2010–2025, one household each) whose
relationship code is the head's (:data:`_HEAD_CODES`), exactly one per household or
:func:`derive` raises. A person of a Conteo 2005 dwelling's second household gets that
household's head (the dwelling's ``JEFE_SEXO`` is its first household's).
The persons of 2000–2025 get ``HOG_IND`` (6w, «Sí»/«No»): whether their household is
indigenous, by each edition's own definition — someone among the members its publications
count speaks an indigenous language (:data:`_IND_CODES`): the head or the partner up to the
EIC 2015, plus the parents and parents-in-law in Censo 2020, plus the step-parents and
grandparents in the EIC 2025. The households carry it too (6x): the dwellings of 2000 (one
row per household) and 2010–2025 (one household per dwelling) and the Conteo 2005's
households (its dwelling rows are dwellings, so they do not) get their household's
``HOG_IND``, computed by the same rule over the household's members — the person rows the
loader reads from the person file and passes as :func:`derive`'s ``members`` (a derivation
with ``members=True``). Every edition's ``EDUC_INEGI`` comes with ``EDUC_INEGI_DET``
(6w), its «Posbásica» split into INEGI's media superior, superior and posgrado
(:data:`_POSBASICA`).

**Editions.** Censo 2020 and EIC 2025 (same questionnaire family) get every derivation
whose sources exist; 2025 lacks ``RELIGION`` and ``IDENT_HIJO``. EIC 2015 and Censo 2010
get the derivations whose source items map onto the 2020 codes (:data:`_RECODE`; 2010
reads its marital status from ``ESTCON``, 2015 its residence five years earlier from
``ENT_PAIS_RES10``), with these edition-specific sets:

- ``DHSERSAL_*`` without ``DHSERSAL_IMSS_BIENESTAR`` (neither edition offered
  IMSS-PROSPERA/BIENESTAR);
- the EIC 2015 commute dummies, one per 2015 code (7 modes): the 2020 names where the mode
  is the same, 2015's wording for the three modes 2020 splits;
- the EIC 2015 financing dummies, one per code of its one item: the 2020 names where the
  source is the same, 2015's wording for «INFONAVIT, FOVISSSTE o PEMEX»;
- Censo 2010's ``LIM_ACTIVIDAD`` («limitación en la actividad», ``DISCAP1``–``DISCAP8``):
  another question than 2020's difficulty scale, so no ``DIS_*``/``DISCAPACIDAD`` there;
- Censo 2010's birthplace and residence in 2005, each split in an entity and a country
  item (``LNACEDO_C``/``LNACPAIS_C``, ``RES05EDO_C``/``RES05PAI_C``; the municipality
  ``MUN05OTR_C``), its place of work, one item holding both catalogs (``LTRABPAI_C``,
  whose 999 is the entity's «no especificada»; the municipality ``LTRABMUN_C``), and its
  co-residence pointer pairs (row number + code item: ``IDMADRE``/``IDMADREC``…), which give
  ``IDENT_PAREJA_CAT`` and the two co-residence flags but not ``IDENT_MADRE_CAT``/
  ``IDENT_PADRE_CAT`` (its «no vive aquí» merges 2020's other dwelling, dead, unknown);
- Censo 2010's 4-digit occupation (``OCUACTIV_C``) and its religion (``OTRAREL_C``, six
  digits), each with its own catalog: the occupation's first two digits are the SINCO
  group, the religion's group gives ``RELIGION_CAT`` (:data:`_RELIGION_2010`).

The coarse occupation is SINCO's two-digit group, labelled as in SINCO 2019; the 2010/2015
group 59, which SINCO 2019 dropped, joins 52 (:data:`_RECODE`). CGPV 2000 codes occupations
in the CMO: a bundled bridge gives each code its SINCO group (8e, ``cpv_cmo_sinco.csv``,
``_ocup_cmo``) — INEGI's SINCO 2011 comparison table, ENOE's 2012 panel where it splits a
code, 99 «No especificado» for the few codes nothing places (0.55% of the employed). The coarse activity is the
SCIAN sector, the same in the 2010, 2015 and 2020 catalogs (2010's item: ``ACTTRAB_C``).
``SECTOR`` (new, 6o) groups it into INEGI's three sectors (primary, secondary, tertiary,
the 1990/2000 ITER's ``POCUSECP/S/T``) in 1990 (its CMAP division) and 2000–2025.

CGPV 2000 and the Conteo 2005 (unweighted) get the columns their items allow: age,
education (from their level-and-antecedent items), health coverage (one item per
institution: :data:`_DHSERSAL_ITEMS`), residence five years earlier, dwelling class, rooms
and drainage; 2000 also income, hours, activity, sector (SCIAN subsector), occupation
(SINCO group, 8e), marital status, birthplace and religion (asked of the 5+: its ``RELIGION_CAT`` adds «Blanco por pase»).

CGPV 1990 (unweighted) and the Conteo 1995 publish person files only (their dwelling
frames are built from them, ``cpv._DWELLINGS_FROM_PERSONS``): age, education (1990 from
its approved-grade, level and technical/normal items, 1995 from its level, grade and
technical-career items), activity, marital status, birthplace, residence five years
earlier, hours and income (1990's monthly income in new pesos: ÷ 1,000), 1990's religion
(asked of the 5+, as 2000's); dwelling rooms, bedrooms and drainage, and 1990's class.
CGPV 1990 writes 0 for «not asked» (``_NA`` in :data:`_RECODE`); neither asked health
coverage or disability per person (the Conteo counts them per household).

An unspecified entity (2020: 997) counts as ``OtraEnt`` in every edition, the legacy rule;
INEGI's tabulados count it as not specified (a few hundred persons per edition), and so
does ``ENT_PAIS_NAC_INEGI`` (6y), the birthplace beside it (the EIC 2025's ``PNACOE``: 14,882
persons nationally). ``DHSERSAL_ISSSTE_T`` (6y) is the ISSSTE, federal or state, beside
the public (``DHSERSAL_PUB``) and any (``DHSERSAL_AFIL``) affiliation.

Three household columns are new in 6z (the EIC 2025's dwelling and household
percentages): ``OCUP_CUARTO_CAT``, the occupants per room (``NUMPERS`` ÷ ``TOTCUART``, the
rooms counting the kitchen: up to 2.5 or more; 2010–2025, one household per dwelling);
``CLASE_HOG``, the household's class from INEGI's ``TIPOHOG`` («Familiar» = nuclear,
ampliado, compuesto and the unspecified familiar type 4; «No familiar» = unipersonal,
corresidente; 9 «No especificado»), on the dwellings of 2000 (one row per household) and
2010–2025 and on their persons, who read their household's ``TIPOHOG`` from the dwelling
file (``cpv._attach_dwellings``, as the Conteo 2005's households read their dwelling's
class); ``INGR_OTROS`` (2015–2025), whether a member receives money from a source other
than work: any of the four «otros ingresos» items yes, all four no, else not specified.

7a (the EIC 2025's person percentages) adds ``EDAD_QUIN``, five-year age groups up to
75 and over (every edition); for 2020 and 2025, ``LUGAR_RES_5A``, the residence five years
earlier by the person's own municipality and entity, the United States apart
(:func:`_lugar`), ``ENT_PAIS_ASI_INEGI``/``ENT_PAIS_TRAB_INEGI``, the place of school
and work by INEGI's rule (as ``ENT_PAIS_NAC_INEGI``), and the summary dummies
``MED_TRASLADO_{ESC,TRAB}_{METRO,BUS,TAXI}_T`` (metro or metrobús; trolebús or bus,
combi, colectivo; either taxi: :data:`_TRASLADO_T`); for the EIC 2025 only,
``DHSERSAL_AFIL_ACCESO`` (affiliated, or recognising an access to the public health
services, an item asked of the not affiliated) and ``HOG_AFRO`` (persons and dwellings, as
``HOG_IND``): one of the indigenous household's members (:data:`_AFRO_CODES`) considers
themself Afro-Mexican or Afro-descendant. 7b takes the places to the EIC 2015 (its
residence in 2010, school and work) and Censo 2010 (residence in 2005 and work, from its
split items; it asked no place of school), and adds ``LUGAR_ASI``/``LUGAR_TRAB``, the
place of school and of work by municipality with ``LUGAR_RES_5A``'s categories (2015–2025;
work also 2010), INEGI's tabulados' «mismo municipio / otro municipio / no especificado,
otra entidad o país, no especificado». The grouped commute dummies stay 2020/2025: the EIC
2015 answers bus and taxi with one code.

7c takes ``LUGAR_RES_5A`` (residence in 1995), ``LUGAR_TRAB`` and ``ENT_PAIS_TRAB_INEGI`` to
CGPV 2000 (Censo 2010's layout: an entity-or-country item and the municipality of every
Mexican answer; 999 not specified) and adds ``INGTRMEN_SM``, the income from work in
minimum wages of INEGI's tabulados (CGPV 2000 and its ITER's ``P_1SM`` … ``P10_SM``, Censo
2010, EIC 2015, Censo 2020): the monthly wage (daily × 30) of the municipality's CONASAMI
area at the edition's date (:data:`_SALARIOS_MINIMOS`; INEGI's own catalogs for 2010 and
2015, its FD's annex for 2000, the DOF's northern border zone for 2020), with each edition's
groups (2000's bounds differ: below 1, from 1 to 2…; 2010–2020 up to 1, above 1 to 2…).

7f gives CGPV 2000's dwelling frame (one row per household) ``PRIMER_HOGAR``, «Sí» on the
first household's row (``NUMHOG`` 1: one per dwelling), which its dwelling indicators
count, and ``TOTCUART_INEGI``, the first numeric derived column (``Int64``, missing where
the rooms are not specified): its rooms as its ITER counts them, ``TOTCUART`` less an
exclusive kitchen nobody sleeps in, the value of its occupants per room.

8f adds ``LINEA_PARENTESCO``, the person's kinship line to the household head as INEGI
tabulates it (Censo 2020's 13-02: reference person, partner, child, ascendant,
descendant, collateral, another relative, none, not specified; :data:`_LINEAS`), in every
edition whose relationship catalog names each relative (CGPV 1990, Conteo 2005, Censo
2010, EIC 2015, Censo 2020, EIC 2025; the Conteo 1995's has groups only, CGPV 2000's
details no labels). Censo 2020's equals its tabulado, line by line, in every state and
sex; Censo 2010's tabulado (12_04A: seven lines) is read on it with children among the
descendants, the «otro parentesco» without a detail among the collaterals and its
«Familiar» not specified — both «Otro parentesco» here, as the EIC 2015's and Censo 2020's
unspecified relatives (:func:`_linea_2010`).

:func:`cpv_derivations` lists the columns per edition. The check that the source codes
match after the recode is a test (``tests/test_cpv_derived.py``).

**Constraints.** :func:`cpv_constraints` filters the legacy constraint sets (ITER
indicator → microdata cells, ``constraints_*.yaml``) to the indicators an edition can
reproduce, for :func:`mxcensus.crosstabs.get_tables_dict`, plus the indicators an edition
publishes under its own definition (:data:`_EDITION_CELLS`: Censo 2010's limitation; the
legacy cells on the 1990–2010 samples' own items; the 1990–2005 ITERs' own indicators) and
the population by its household head's sex (``PHOGJEF_F``/``PHOGJEF_M`` on
``HOGJEF_SEXO``), the population in households (``POBHOG``) and in indigenous households
(``PHOG_IND`` on ``HOG_IND``) and the indigenous households themselves (``HOG_IND`` on the
dwellings' ``HOG_IND``: the EIC 2025 estimates) (:data:`_CELLS`), which the legacy sets
lack. INEGI's limitation and disability by activity (6y; ``PCLIM_*`` only for the persons
with a limitation, ``PCDISC_*`` with the unknown degree) replace the legacy cells in 2020
and 2025. The EIC 2025 publishes most indicators as percentages; their counts
(``load_cpv_estimaciones(counts=True)``) are indicators too, some on its own definitions
(:data:`_EDITION_CELLS`: born in another state without the unspecified one, the ISSSTE
federal or state, toilet or latrine; 7a: the persons' five-year ages, residence in 2020,
commute, health use…). The Conteo
2005's household indicators are counted on its household frame
(``cpv_constraints("hogares", 2005)``; its dwelling rows are dwellings), whose
``derived=True`` adds the dwelling's class and the household's own head's sex. CGPV 1990's
and 2000's dwelling indicators count every private dwelling, the «Otro» classes too (7f:
theirs carry the items; :data:`_EVERY_CLASS`), CGPV 2000's on the first household's row
(:data:`_PER_DWELLING`), with the dwellings themselves (``VIVPAR_HAB``; 1990 and 1995 too).

**Ratio constraints** (7e). A published share of a base the edition does not publish (the
EIC 2025's employed's commute modes, ``PCN_P3NHLI_CLI``, ``PCN_HF``) or an average (the
children born alive per woman, the years of schooling, the occupants per room and per
dwelling: the EIC 2025 estimates, the Censo 2010/2020 ITER; 7f: the occupants per dwelling
and per room of CGPV 1990 and 2000, per dwelling of the Conteo 1995) is no count: Σ w·N = r
/ scale · Σ w·D over a geography's records. :func:`cpv_ratio_constraints` gives each one's
numerator and denominator cells (and value columns), :func:`cpv_ratio_terms` each record's
N and D.
"""
from __future__ import annotations

import functools
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from mxcensus._resources import (
    constraints_personas,
    constraints_viviendas,
    variables_personas,
    variables_viviendas,
)
from mxcensus.utils import expand_cat_map

TABLES = ("personas", "viviendas", "hogares")   # hogares: the Conteo 2005 (6v)

# Edition → source item → {edition code: Censo 2020 code}. Codes not listed are the same;
# ``_NA`` makes a code blank (CGPV 1990 writes 0 for «not asked»).
_NA = float("nan")
_RECODE: dict[str, dict[str, dict[int, float]]] = {
    "2025": {
        # 01–09/99; «separada(o)» split into 02 (from a free union) and 03 (from a marriage).
        "SITUA_CONYUGAL": {1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 99: 9},
        # 05 = IMSS-BIENESTAR (2020: 06); 06 = a public health centre, hospital or institute,
        # incl. INSABI and Seguro Popular (2020: 05, Seguro Popular / INSABI).
        "DHSERSAL1": {5: 6, 6: 5},
        "DHSERSAL2": {5: 6, 6: 5},
        # The country catalog renumbered two entries: Isla de Man, Palaos.
        "ENT_PAIS_NAC": {454: 241, 536: 356},
        "ENT_PAIS_RES_5A": {454: 241, 536: 356},
        "ENT_PAIS_ASI": {454: 241, 536: 356},
        "ENT_PAIS_TRAB": {454: 241, 536: 356},
    },
    "2015": {
        # 1 = Seguro Popular (2020: 05) first, then IMSS…otra 2–7 (2020: 01–04, 07, 08),
        # 8 = not affiliated, 9 = not specified; no IMSS-PROSPERA/BIENESTAR (2020: 06).
        "DHSERSAL1": {1: 5, 2: 1, 3: 2, 4: 3, 5: 4, 6: 7, 7: 8, 8: 9, 9: 99},
        "DHSERSAL2": {1: 5, 2: 1, 3: 2, 4: 3, 5: 4, 6: 7, 7: 8, 8: 9, 9: 99},
        # 10 worked, 11–15 found working by the activity check (2020: 10, 13–19 by declared
        # status), 16 had a job (20), 20 searched (30), 31–35 student, retired, home duties,
        # limitation, did not work (50, 40, 60, 70, 80).
        "CONACT": {11: 10, 12: 10, 13: 10, 14: 10, 15: 10, 16: 20, 20: 30,
                   31: 50, 32: 40, 33: 60, 34: 70, 35: 80},
        # 5 = casada(o), not split into civil/religious (2020: 05–07, all «casado»);
        # 6 = soltera(o).
        "SITUA_CONYUGAL": {6: 8},
        # «¿Dónde vive la pareja?»: 98 = does not know where, so not in this dwelling (96).
        "IDENT_PAREJA": {98: 96},
        # SINCO 2011's only subgroup of its group 59 («Otras ocupaciones en servicios
        # personales y vigilancia, no clasificadas anteriormente»): SINCO 2019 dropped the
        # group and added 529 «Otros trabajadores en servicios personales no clasificados».
        "OCUPACION_C": {599: 529},
    },
    "2010": {
        # 6 = private, 7 = other, 8 = no entitlement, 9 = not specified (2020: 07, 08, 09, 99);
        # no IMSS-PROSPERA/BIENESTAR (2020: 06).
        "DHSERSAL1": {6: 7, 7: 8, 8: 9, 9: 99},
        "DHSERSAL2": {6: 7, 7: 8, 8: 9, 9: 99},
        # 04 = either bachillerato (2020: 04/05), 05 = normal básica (09), then normal de
        # licenciatura, licenciatura, maestría, doctorado (10, 11, 13, 14); no especialidad.
        "NIVACAD": {5: 9, 9: 10, 10: 11, 11: 13, 12: 14},
        # Birthplace and residence in 2005: an entity item and a country item. Entity 999 =
        # entity not specified (2020: 997), 900 = topic omitted (999); country 600 =
        # insufficiently specified (998), 700 = «México (país)» (997), 999 = country not
        # specified (998).
        "LNACEDO_C": {900: 999, 999: 997},
        "RES05EDO_C": {900: 999, 999: 997},
        "LNACPAIS_C": {600: 998, 700: 997, 999: 998},
        "RES05PAI_C": {600: 998, 700: 997, 999: 998},
        # Place of work (7b): one item for «another state or country» holding both catalogs
        # (entities 001–032, 900 topic omitted; countries, 600, 700); its 999 is the
        # entity's «no especificada» (INEGI's tabulado 08_15A counts it not specified).
        "LTRABPAI_C": {600: 998, 700: 997, 900: 999, 999: 997},
        # The 4-digit SINCO of 2010 (TC_OCUPACION_2010): 5999 is group 59 (as 2015's 599).
        "OCUACTIV_C": {5999: 5299},
        # Dwelling class: 2000's classes (casa independiente, departamento, vecindad,
        # azotea, local no construido, móvil, refugio, not specified); its tabulados'
        # «viviendas particulares habitadas» leave out 5–7, as 2020's «Otro» (STEP_3b.md).
        "CLAVIVP": {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 9: 99},
    },
    "2000": {
        # 14 student, 15 home duties, 16 retired found working by the activity check; 40
        # student, 50 home duties, 60 retired (2020: 15, 16, 14 and 50, 60, 40).
        "CONACT": {14: 15, 15: 16, 16: 14, 40: 50, 50: 60, 60: 40},
        # Level: normal (5; its antecedent is primaria or secundaria) 9, profesional (7) 11,
        # maestría o doctorado (8) 13, not specified (9) 99; técnica (6) by its antecedent
        # (_educ_2000).
        "NIVACAD": {5: 9, 7: 11, 8: 13, 9: 99},
        "ESCOLARI": {9: 99},
        # Birthplace, residence in 1995 and place of work (7c; its FD: the same codes as the
        # birthplace): 600 = «otro país, no se sabe cuál» (2020: 998); 999 not specified.
        "ENT_PAIS_NAC": {600: 998},
        "ENT_PAIS_RES_5A": {600: 998},
        "LTRABPAI_C": {600: 998},
        # Dwelling class (CLAVIV): casa independiente (2020: casa única en el terreno),
        # departamento, vecindad, azotea, local no construido para habitación, vivienda
        # móvil, refugio, not specified.
        "CLAVIVP": {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 9: 99},
        # 26 rooms (2020's code list stops at 25; both «3+»).
        "TOTCUART": {26: 25},
        # Sex: 1 man, 2 woman (2020: 1, 3); read for the household head (6s, JEFE_SEXO).
        "SEXO": {2: 3},
        # Speaks an indigenous language: 1 yes, 2 no (2020: 1, 3), 9 not specified (6w).
        "HLENGUA": {2: 3},
    },
    "2005": {
        # Level and antecedent (NIVANTES), as 2000's; 84 maestría, 94/95 doctorado.
        "NIVANTES": {10: 1, 20: 2, 30: 3, 40: 4, 51: 9, 52: 9, 61: 6, 62: 7, 63: 8, 73: 11,
                     84: 13, 94: 14, 95: 14, 99: 99},
        "GRA_APRO": {9: 99},
        # Residence in October 2000 (LURE2000): 033 entity not sufficiently specified
        # (2020: 997), 201 the United States (221), 600 another country (998).
        "ENT_PAIS_RES_5A": {33: 997, 201: 221, 600: 998},
        # Dwelling class (CLAVIVPA): 2000's classes.
        "CLAVIVP": {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 9: 99},
        "SEXO": {2: 3},                                     # as 2000's
        "HLENGUA": {2: 3},                                  # HABLENIN, as 2000's (6w)
    },
    "1995": {
        "EDAD": {99: 999},                                  # 99 = not specified (98 = 98+)
        "HORTRA": {99: 999},
        # 1 worked, 2 had a job, 3 searched, 4 student, 5 home duties, 6 retired, 7 unable
        # to work, 8 did not work, 9 not specified.
        "CONACT": {1: 10, 2: 20, 3: 30, 4: 50, 5: 60, 6: 40, 7: 70, 8: 80, 9: 99},
        # 1 unión libre, 2 viuda(o), 3 separada(o), 4 divorciada(o), 5 casada(o) (not split
        # by civil/religious), 6 soltera(o), 8 «alguna vez unida y no se sabe el estado
        # civil» (not specified, the user's choice), 9 not specified.
        "SITUA_CONYUGAL": {1: 1, 2: 4, 3: 2, 4: 3, 5: 5, 6: 8, 8: 9, 9: 9},
        # Birthplace and residence in 1990 (its catalog of entities and countries): 01–32
        # entity, 33–38 a continent (35 the United States), 70 «México (país)» = entity not
        # specified (2020: 997), 90 a country insufficiently specified, 99 not specified.
        "ENT_PAIS_NAC": {**dict.fromkeys(range(33, 39), 998), 70: 997, 90: 998, 99: 999},
        "ENT_PAIS_RES_5A": {**dict.fromkeys(range(33, 39), 998), 70: 997, 90: 998, 99: 999},
        # Sex (P3_5): 1 man, 2 woman (2020: 1, 3); read for the household head (6t).
        "SEXO": {2: 3},
    },
    "1990": {
        # 0 = not asked (under 12) in the activity items, 1–9 as 1995's.
        "CONACT": {0: _NA, 1: 10, 2: 20, 3: 30, 4: 50, 5: 60, 6: 40, 7: 70, 8: 80, 9: 99},
        # 1 unión libre, 2 casada(o) civil y religiosamente, 3 sólo por el civil, 4 sólo
        # religiosamente, 5 separada(o), 6 divorciada(o), 7 viuda(o), 8 soltera(o), 9.
        "SITUA_CONYUGAL": {0: _NA, 1: 1, 2: 7, 3: 5, 4: 6, 5: 2, 6: 3, 7: 4, 8: 8, 9: 9},
        # Birthplace and residence in 1985 (CATPAISE): 001–032 entity, 033–099 entity
        # insufficiently specified (2020: 997), 100–998 another country (998), 999 not
        # specified; 0 = not asked (residence: under 5).
        "ENT_PAIS_NAC": {**dict.fromkeys(range(33, 100), 997),
                         **dict.fromkeys(range(100, 999), 998)},
        "ENT_PAIS_RES_5A": {0: _NA, **dict.fromkeys(range(33, 100), 997),
                            **dict.fromkeys(range(100, 999), 998)},
        # 1 ninguna, 2 católica, 3 protestante o evangélica, 4 judaica, 5 otra, 9; 0 = under 5.
        "RELIGION": {0: _NA, 1: 3101, 2: 1101, 3: 1326, 4: 2201, 5: 2901, 9: 9999},
        # Dwelling class (T_VIV): 1 casa sola, 2 departamento o vecindad, 3 cuarto de azotea,
        # 4 vivienda móvil, 5 refugio, 9.
        "CLAVIVP": {1: 1, 2: 4, 3: 6, 4: 8, 5: 9, 9: 99},
        # The refugios have no dwelling characteristics (0); 26 rooms (both «3+»).
        "CUADORM": {0: _NA},
        "TOTCUART": {0: _NA, 26: 25},
        # 3 «con desagüe al suelo, a un río o lago» (2020: 3/4, both drainage), 4 none (5).
        "DRENAJE": {0: _NA, 4: 5},
    },
}

# A source read under another name in some editions or under harmonize=True.
_ALIASES = {"ENT": ("ENT", "CVE_ENT"),
            "MUN": ("MUN", "CVE_MUN"),
            "EDAD": ("EDAD", "ANO_CUMP", "P3_6"),
            "CONACT": ("CONACT", "ACT_PRIN", "P7_1"),
            "SITUA_CONYUGAL": ("SITUA_CONYUGAL", "ESTCON", "EST_CIVIL", "P6_1"),
            "ENT_PAIS_NAC": ("ENT_PAIS_NAC", "LNACEDO_C", "CVE_P_NAC", "P3_7B"),
            "ENT_PAIS_RES_5A": ("ENT_PAIS_RES_5A", "ENT_PAIS_RES10", "RES95EDO_C", "LURE2000",
                                "CVE_P_RES", "P4_6A"),
            "MUN_RES_5A": ("MUN_RES_5A", "MUN_RES10", "MUN95OTR_C"),    # 7b, 7c: 2015, 2000
            "ACTIVIDADES_C": ("ACTIVIDADES_C", "ACTTRAB_C"),
            "INGTRMEN": ("INGTRMEN", "INGRESOS", "INGRESO", "P7_9MP"),
            "HORTRA": ("HORTRA", "HORAS", "P7_6"),
            "CLAVIVP": ("CLAVIVP", "CLAVIV", "CLAVIVPA", "T_VIV"),
            "CUADORM": ("CUADORM", "CUARDOM", "P_DORMIR", "P1_6"),
            "TOTCUART": ("TOTCUART", "NUMCUAR", "T_CUARTOS", "P1_7"),
            "DRENAJE": ("DRENAJE", "DIS_DREN", "P1_13"),
            "SEXO": ("SEXO", "P3_5"),
            "HLENGUA": ("HLENGUA", "HABLENIN"),
            # the relationship to the household head (own codes: _HEAD_CODES, _IND_CODES)
            "PARENTESCO": ("PARENTESCO", "PARENT", "OTROPARE_C", "P3_4")}

# The household head's code in each edition's relationship item (6t; codes as numbers):
# 2020/2025 PARENTESCO 101 «Jefa(e)»; Censo 2010 and EIC 2015 PARENT 01 «Jefe(a)»; the Conteo
# 2005's PARENT 101 «Jefe(a)» and 102 «Persona sola»; CGPV 2000's OTROPARE_C 100 (the head
# group of its catalog); the Conteo 1995's P3_4 1 «Jefe o Jefa» (its catalog's 7 «Persona
# sola» marks a few persons of households that have a 1). One per household in every state.
_HEAD_CODES: dict[str, tuple[int, ...]] = {
    "1995": (1,), "2000": (100,), "2005": (101, 102), "2010": (1,), "2015": (1,),
    "2020": (101,), "2025": (101,)}

# The members whose indigenous language makes their household indigenous (6w, ``HOG_IND``),
# by each edition's own definition, verified on its publications: the head and the partner
# up to the EIC 2015 (2005/2010 ITER ``PHOG_IND``, Censo 2010 exact in the 364 municipalities
# its sample enumerated completely; the EIC 2015 tabulado «hogares cuyo jefe o jefa y/o
# cónyuge habla lengua indígena»); Censo 2020 adds the mother or father and the
# parents-in-law (its ITER, exact in the 184 completely enumerated municipalities;
# grandparents and step-parents would not be); the EIC 2025 also the step-parents,
# grandparents and great-grandparents (its estimates, exact in all 2,478 municipalities).
# CGPV 2000 (no such indicator) takes the head and the partner, the definition of its era.
# Codes: 2020/2025 PARENTESCO 101 head, 201–203 partner, 401 mother or father, 402
# step-parent, 406 grandparent, 407 great- or great-great-grandparent, 416 parent-in-law;
# 2010/2015 PARENT 01 head, 02 partner; 2005 PARENT 101/102 head, 201–204 partner; 2000
# OTROPARE_C 100 head, 200 partner.
_PARTNERS = (201, 202, 203)
_IND_CODES: dict[str, tuple[int, ...]] = {
    "2000": (100, 200), "2005": (101, 102, 201, 202, 203, 204), "2010": (1, 2),
    "2015": (1, 2), "2020": (101, *_PARTNERS, 401, 416),
    "2025": (101, *_PARTNERS, 401, 402, 406, 407, 416)}


def _span(first: int, last: int) -> tuple[int, ...]:
    return tuple(range(first, last + 1))


# 8f: the kinship lines («líneas de parentesco»: the population in households by its
# relationship to the head; Censo 2020's tabulado 13-02, Censo 2010's 12_04A), each found on
# its tabulado in every state and sex (STEP_7w.md, STEP_7p.md). Censo 2020's nine lines in
# every edition whose catalog names each relative, by its labels; the Conteo 1995's
# catalog has groups only and CGPV 2000's detail codes have no labels. Edition → line →
# its relationship codes (2020/2025 PARENTESCO, EIC 2015 PARENT_OTRO_C, Conteo 2005 PARENT,
# CGPV 1990 CVE_PAR; Censo 2010: :func:`_linea_2010`). The domestic workers, their
# relatives, the guests and tutors have none; a «persona sola» heads a household of one.
# CGPV 1990's first digit is the relationship (its FD's groups), the other two CATPAREN's
# word as written: its 702 «huésped» and 703 «abonado» are persons alone (one-person
# dwellings), so heads; its «otro parentesco» (6xx) is read by the word.
_LINEAS: dict[str, dict[str, tuple[int, ...]]] = {
    "2020": {"Persona de referencia": (101,), "Esposa(o) o pareja": (201, 202, 203),
             "Hija(o)": _span(301, 304),
             "Ascendente": (401, 402, 406, 407, 412, 416, 421),
             "Descendente": (408, 409, 410, 411, 413, 414, 418, 422),
             "Colateral": (403, 404, 405, 415, 417, 419, 420, 423),
             "Otro parentesco": (424,),
             "Sin parentesco": (501, 502, 503, 601, 611, 612, 613, 701),
             "No especificado": (999,)},
    "2015": {"Persona de referencia": (101,), "Esposa(o) o pareja": _span(201, 204),
             "Hija(o)": _span(301, 304),
             "Ascendente": (401, 402, 406, 407, 408, 412, 415, 420),
             "Descendente": (409, 410, 411, 413, 417, 421),
             "Colateral": (403, 404, 405, 414, 416, 418, 419, 422),
             "Otro parentesco": (423,),
             "Sin parentesco": (*_span(501, 503), 601, *_span(611, 615), 701, *_span(711, 715)),
             "No especificado": (999,)},
    "2005": {"Persona de referencia": (101, 102), "Esposa(o) o pareja": _span(201, 204),
             "Hija(o)": _span(301, 305),
             "Ascendente": (601, 602, 606, 607, 608, 612, 615, 620),
             "Descendente": (609, 610, 611, 613, 617, 621),
             "Colateral": (603, 604, 605, 614, 616, 618, 619, 622),
             "Otro parentesco": (623,),
             "Sin parentesco": (*_span(401, 413), 421, 431, 441, 451, 461, *_span(501, 503),
                                701, *_span(711, 715)),
             "No especificado": (999,)},
    "1990": {"Persona de referencia": (*_span(100, 199), *_span(700, 799)),
             "Esposa(o) o pareja": _span(200, 299), "Hija(o)": _span(300, 399),
             "Ascendente": (601, 602, 605, 606, 607, 611, 614, 620),
             "Descendente": (608, 609, 610, 612, 615, 621),
             "Colateral": (603, 604, 613, 616, 617, 622),
             "Otro parentesco": (600, 623),
             "Sin parentesco": (*_span(400, 599), 618, 619),
             "No especificado": _span(900, 999)},
}
_LINEAS["2025"] = _LINEAS["2020"]                 # the same catalog
_LINEA_ITEMS = {"1990": "CVE_PAR", "2005": "PARENT", "2015": "PARENT_OTRO_C",
                "2020": "PARENTESCO", "2025": "PARENTESCO"}
# Censo 2010: PARENT's groups (01 head … 07 parent-in-law, 09 none, 99) and, for its «otro
# parentesco» (08), the detail OTROPARE_C, numbered as the Conteo 2005's 6xx. INEGI's 12_04A
# counts the 08 without a detail code (44,098 records) collateral; here they are «Otro
# parentesco», as the EIC 2015's «Otro familiar» and 2020's «Otros familiares» (the user's
# choice), so 12_04A's collaterals = «Colateral» + those, its «No especificado» = the rest
# of «Otro parentesco» (623 «Familiar») + «No especificado», its descendants = «Hija(o)» +
# «Descendente».
_PARENT_2010 = {1: "Persona de referencia", 2: "Esposa(o) o pareja", 3: "Hija(o)",
                4: "Descendente", 5: "Descendente", 6: "Ascendente", 7: "Ascendente",
                9: "Sin parentesco", 99: "No especificado"}
_OTRO_2010 = {code: line for line, codes in _LINEAS["2005"].items() for code in codes
              if 601 <= code <= 623}

_BLANK = -1  # a blank (not asked) code, as the legacy dictionaries spell it
_DUMMY = pd.CategoricalDtype([0, 1])
# Derived columns the legacy loaders do not have (the others take the legacy dtype).
_YES_NO = pd.CategoricalDtype(["Sí", "No", "No especificado"])
# INEGI's levels (its ITER and tabulados, 1990–2020): the legacy EDUC with the técnica or
# commercial studies after primaria apart, so «Primaria_com» is six grades of primaria only;
# INEGI tabulates them between básica and media superior.
_EDUC_INEGI = pd.CategoricalDtype(["Sin Educación", "Primaria_incom", "Primaria_com",
                                   "Secundaria_incom", "Secundaria_com", "Técnica_primaria",
                                   "Posbásica", "No especificado", "Blanco por pase"],
                                  ordered=True)
# EDUC_INEGI with «Posbásica» split into INEGI's levels (6w; the 2000 ITER's P18_CMEDSU/
# P18_CSUPER, the EIC 2025 estimates' EMS/ES/POS), by the 2020 NIVACAD: media superior =
# bachillerato general or tecnológico (4, 5), técnica after secundaria (7), normal básica
# (9); superior = técnica after preparatoria (8), normal de licenciatura (10), licenciatura
# (11); posgrado = especialidad, maestría, doctorado (12–14).
_POSBASICA = {**dict.fromkeys((4, 5, 7, 9), "Media_superior"),
              **dict.fromkeys((8, 10, 11), "Superior"), **dict.fromkeys((12, 13, 14), "Posgrado")}
_EDUC_INEGI_DET = pd.CategoricalDtype(["Sin Educación", "Primaria_incom", "Primaria_com",
                                       "Secundaria_incom", "Secundaria_com", "Técnica_primaria",
                                       "Media_superior", "Superior", "Posgrado",
                                       "No especificado", "Blanco por pase"], ordered=True)
_SI_NO = pd.CategoricalDtype(["Sí", "No"])
# INEGI's three sectors of activity (the 1990/2000 ITER's POCUSECP/S/T): primary =
# agriculture, livestock, forestry, fishing and hunting; secondary = mining, electricity and
# water, construction, manufacturing; tertiary = trade, transport, services, government.
_SECTOR = pd.CategoricalDtype(["Primario", "Secundario", "Terciario", "No especificado",
                               "Blanco por pase"])
# 6z: the occupants per room (the EIC 2025's VPH_2_5OCU: more than 2.5) and the household's
# class (INEGI's familiar / no familiar, from its TIPOHOG).
_OCUP_CUARTO = pd.CategoricalDtype(["Hasta 2.5", "Más de 2.5", "No especificado",
                                    "Blanco por pase"])
_CLASE_HOG = pd.CategoricalDtype(["Familiar", "No familiar", "No especificado"])
# 7a: the five-year age groups (the EIC 2025 estimates' P_0A4 … P_75YMAS) and the place of
# residence five years earlier with the municipality and the United States apart (its
# PRESM20 … PRESOP20; the person's own municipality and entity; «Municipio no especificado»:
# the own entity, municipality 999); 7b: the place of school and of work by the same
# categories (INEGI's 2010–2020 tabulados: same municipality, another, not specified;
# another entity or country; not specified).
_EDAD_QUIN = pd.CategoricalDtype([*(f"{a}-{a + 4}" for a in range(0, 75, 5)), "75-130",
                                  "No especificado"], ordered=True)
_LUGAR_RES = pd.CategoricalDtype(["Mismo municipio", "Otro municipio",
                                  "Municipio no especificado", "Otra entidad", "Estados Unidos",
                                  "Otro país", "No especificado", "Blanco por pase"])
# 7c: the income from work in minimum wages, INEGI's tabulados' groups: CGPV 2000's
# (C2KEM08; its ITER's P_1SM … P10_SM join the 2–3 and 3–5 groups) are bounded otherwise
# than 2010–2020's (:func:`_ingtrmen_sm`).
_SM_2000 = pd.CategoricalDtype(["No recibe ingresos", "Menos de 1 s.m.", "De 1 hasta 2 s.m.",
                                "Más de 2 y menos de 3 s.m.", "De 3 hasta 5 s.m.",
                                "Más de 5 hasta 10 s.m.", "Más de 10 s.m.", "No especificado",
                                "Blanco por pase"], ordered=True)
_SM = pd.CategoricalDtype(["No recibe ingresos", "Hasta 1 s.m.", "Más de 1 a 2 s.m.",
                           "Más de 2 a 3 s.m.", "Más de 3 a 5 s.m.", "Más de 5 a 10 s.m.",
                           "Más de 10 s.m.", "No especificado", "Blanco por pase"], ordered=True)
# 8f: the kinship line, Censo 2020's tabulado 13-02's (:data:`_LINEAS`).
_LINEA_PARENTESCO = pd.CategoricalDtype(["Persona de referencia", "Esposa(o) o pareja",
                                         "Hija(o)", "Ascendente", "Descendente", "Colateral",
                                         "Otro parentesco", "Sin parentesco",
                                         "No especificado"])
_DTYPES = {"DISCAPACIDAD": _YES_NO, "LIMITACION": _YES_NO, "SIN_DISC_LIM": _YES_NO,
           "LIM_ACTIVIDAD": _YES_NO, "MADRE_EN_VIVIENDA": _YES_NO, "PADRE_EN_VIVIENDA": _YES_NO,
           "EDUC_INEGI": _EDUC_INEGI, "EDUC_INEGI_DET": _EDUC_INEGI_DET, "SECTOR": _SECTOR,
           "HOG_IND": _SI_NO, "OCUP_CUARTO_CAT": _OCUP_CUARTO, "CLASE_HOG": _CLASE_HOG,
           "INGR_OTROS": _YES_NO, "EDAD_QUIN": _EDAD_QUIN, "LUGAR_RES_5A": _LUGAR_RES,
           "LUGAR_ASI": _LUGAR_RES, "LUGAR_TRAB": _LUGAR_RES, "HOG_AFRO": _SI_NO,
           "INGTRMEN_SM": _SM, "PRIMER_HOGAR": _SI_NO, "TOTCUART_INEGI": pd.Int64Dtype(),
           "LINEA_PARENTESCO": _LINEA_PARENTESCO}
# Derived columns with another column's legacy dtype: the household head's sex on the
# person (6t) has the dwelling item's; INEGI's birthplace (6y) the legacy one's; the place
# of school and work by INEGI's rule (7a) the residence's (with «Blanco por pase»).
_DTYPE_LIKE = {"HOGJEF_SEXO": ("viviendas", "JEFE_SEXO"),
               "ENT_PAIS_NAC_INEGI": ("personas", "ENT_PAIS_NAC_CAT"),
               "ENT_PAIS_ASI_INEGI": ("personas", "ENT_PAIS_RES_CAT"),
               "ENT_PAIS_TRAB_INEGI": ("personas", "ENT_PAIS_RES_CAT"),
               "RELIGION_INEGI": ("personas", "RELIGION_CAT")}
_DIS_ITEMS = ("DIS_VER", "DIS_OIR", "DIS_CAMINAR", "DIS_RECORDAR", "DIS_BANARSE", "DIS_HABLAR")
# Censo 2010: one item per activity (DISCAP1–7, its code or blank), DISCAP8 = none (17) or
# not specified (99).
_DISCAP_ITEMS = tuple(f"DISCAP{i}" for i in range(1, 9))

# DHSERSAL1/2 code (2020) → dummy; 1–6 are public institutions, 1–8 any affiliation.
_DHSERSAL = {
    1: "DHSERSAL_IMSS",
    2: "DHSERSAL_ISSSTE",
    3: "DHSERSAL_ISSSTE_E",
    4: "DHSERSAL_P_D_M",
    5: "DHSERSAL_SALUD_PUBLICA",       # legacy DHSERSAL_Popular_NGenración_SBienestar
    6: "DHSERSAL_IMSS_BIENESTAR",      # legacy DHSERSAL_IMSS_Prospera/Bienestar
    7: "DHSERSAL_Privado",
    8: "DHSERSAL_Otro",
    9: "DHSERSAL_No afiliado",
}
_DHSERSAL_NO_BIENESTAR = tuple(c for c in _DHSERSAL if c != 6)   # 2010, 2015
#: Legacy dummy name → the neutral name used here (for the legacy constraints and tests).
DHSERSAL_RENAMES = {
    "DHSERSAL_Popular_NGenración_SBienestar": "DHSERSAL_SALUD_PUBLICA",
    "DHSERSAL_IMSS_Prospera/Bienestar": "DHSERSAL_IMSS_BIENESTAR",
}


@functools.cache
def _variables(table: str) -> dict:
    return variables_personas() if table == "personas" else variables_viviendas()


@functools.cache
def _legacy_map(table: str, var: str) -> dict:
    """The legacy code → label map of ``var`` (int codes, ``-1`` = blank)."""
    return expand_cat_map(_variables(table)[var]["Categorías"])


@functools.cache
def _legacy_dtypes(table: str) -> dict:
    """The dtype each derived column has in the legacy loader's schema (``hogares``, whose
    columns are dwelling columns: ``extended_viviendas``'s)."""
    from mxcensus import extended_personas, extended_viviendas

    mod = extended_personas if table == "personas" else extended_viviendas
    return {name: col.dtype.type for name, col in mod._build_schema().columns.items()}


def _legacy_dtype(table: str, name: str) -> pd.CategoricalDtype:
    """The legacy loader's dtype of ``name`` (or of its :data:`_DTYPE_LIKE` column)."""
    table, name = _DTYPE_LIKE.get(name, (table, name))
    return _legacy_dtypes(table)[name]


def _as(values, table: str, name: str) -> pd.Series:
    return pd.Series(values).astype(_DTYPES.get(name) or _legacy_dtype(table, name))


def _mapped(codes: pd.Series, table: str, var: str, name: str) -> pd.Series:
    """``codes`` through the legacy map of ``var`` (the ``Categorías`` of ``name``)."""
    return _as(codes.fillna(_BLANK).map(_legacy_map(table, var)), table, name)


def _cut(values: pd.Series, table: str, name: str, bins, labels, *, right: bool,
         blank: float | None = None) -> pd.Series:
    """The legacy ``pd.cut`` binning (``blank`` fills the not-asked rows first)."""
    if blank is not None:
        values = values.fillna(blank)
    return _as(pd.cut(values, bins, right=right, labels=labels), table, name)


# --- the derivations (src: the source items as float codes in the 2020 code space) --------

_INCOME_BINS = (0, 1, 1000, 5000, 10000, 20000, 40000, 80000, 150000, 999999, 1e6, 3e6)
_INCOME_LABELS = ["No recibe ingresos", "1-999", "1,000-4,999", "5,000-9,999",
                  "10,000-19,999", "20,000-39,999", "40,000-79,999", "80,000-149,999",
                  "150,000yMas", "No especificado", "Blanco por pase"]


def _edad_cat(src):
    labels = ["0-2", "3-4", "5", "6-7", "8-11", "12-14", "15-17", "18-24", "25-49",
              "50-59", "60-64", "65-130", "No especificado"]
    return {"EDAD_CAT": _cut(src["EDAD"], "personas", "EDAD_CAT",
                             (0, 3, 5, 6, 8, 12, 15, 18, 25, 50, 60, 65, 200, 1e6),
                             labels, right=False)}


def _edad_quin(src):
    """Five-year age groups (7a), up to «75-130» (``EDAD_CAT``'s bins: 999 = not specified)."""
    return {"EDAD_QUIN": _cut(src["EDAD"], "personas", "EDAD_QUIN",
                              (*range(0, 80, 5), 200, 1e6), list(_EDAD_QUIN.categories),
                              right=False)}


def _ingtrmen_cat(src):
    return {"INGTRMEN_CAT": _cut(src["INGTRMEN"], "personas", "INGTRMEN_CAT", _INCOME_BINS,
                                 _INCOME_LABELS, right=False, blank=2e6)}


def _hortra_cat(src):
    labels = ["0-5", "6-10", "11-20", "21-40", "41-48", "49-56", "57-60", "61-80", "81YMAS",
              "No especificado", "Blanco por pase"]
    return {"HORTRA_CAT": _cut(src["HORTRA"], "personas", "HORTRA_CAT",
                               [-1, 5, 10, 20, 40, 48, 56, 60, 80, 998, 1e6, 3e6], labels,
                               right=True, blank=2e6)}


_EMPLOYED = (10, 20)          # CONACT (2020 codes): worked, had a job but did not work


def _hortra_2000(src):
    """CGPV 2000's hours: who had a job but did not work (``CONACT`` 20) reported hours,
    likely their usual ones; INEGI's sample tabulado (C2KEM07, «no trabajó»), like every
    later edition's data, gives them none, so they count at 0 hours (6r)."""
    return _hortra_cat(pd.DataFrame({"HORTRA": src["HORTRA"].mask(src["CONACT"].eq(20), 0)}))


def _hortra_1990(src):
    """CGPV 1990's hours (``HORAS``): 0 for everyone not employed, so blank unless the
    activity (``ACT_PRIN``) is «worked» or «had a job» (who had one worked 0 hours, as in
    2020)."""
    return _hortra_cat(pd.DataFrame({"HORTRA": src["HORTRA"].where(
        src["CONACT"].isin(_EMPLOYED))}))


def _ingtrmen_1990(src):
    """CGPV 1990's monthly income (``INGRESO``) is in pesos of before the 1993
    redenomination: in new pesos (÷ 1,000; a positive amount is at least $1, so it is not
    «No recibe ingresos»), 99999997–99999999 (eventual, does not know, not specified) →
    not specified, blank unless employed (0 for everyone else). About 1% of the incomes
    look written in thousands (258 for $258,000, one minimum wage); the bins put most of
    them where the larger amount would go (both under $999)."""
    income = src["INGTRMEN"]
    new = np.maximum(income / 1000, 1).where(income.gt(0), income)
    new = new.mask(income.ge(99_999_997), 999_999).where(src["CONACT"].isin(_EMPLOYED))
    return _ingtrmen_cat(pd.DataFrame({"INGTRMEN": new}))


# 7c: the minimum wage of each municipality, for the income in minimum wages of INEGI's
# tabulados (and CGPV 2000's ITER): the general daily minimum wage of the municipality's
# CONASAMI area at the edition's date, × 30 (INEGI's monthly wage; × 30.4 misses its
# tabulados by points). Daily wages in cents; an area maps an entity to its municipalities
# (_WHOLE: all of them); the rest of the country takes the edition's first wage.
# - CGPV 2000: its FD's annex «Salarios mínimos generales por entidad federativa y áreas
#   geográficas vigentes a febrero del 2000» (= DOF 31/12/1999): A 37.90, B 35.10, C 32.70.
# - Censo 2010: INEGI's catalog TC_TABLA_SALARIOS_MUN_2010 (= DOF 23/12/2009; 2000's
#   municipalities): 57.46, 55.84, 54.47.
# - EIC 2015: INEGI's catalog TC_SALARIO_MUN_2015 — the two areas of 2012 (A = the old A and
#   B), the January–March wages 70.10 and 66.45 —, as published: it puts Coacoatzintla
#   (30-036) in area A where the DOF names Coatzintla (30-040), and INEGI's tabulados follow
#   the catalog (to the person; the DOF's municipality misses Veracruz by 525 persons).
# - Censo 2020: DOF 23/12/2019, the Zona Libre de la Frontera Norte 185.56 (its 43
#   municipalities and San Quintín, 02-006, split off Ensenada in February 2020: INEGI's
#   tabulados count it in the zone) and the rest of the country 123.22.
_WHOLE = None
_SM_A = {2: _WHOLE, 3: _WHOLE, 9: _WHOLE, 8: (28, 37, 53), 12: (1,),
         15: (13, 20, 24, 33, 57, 104, 109, 121), 26: (2, 19, 39, 43, 48, 55, 59, 70),
         28: (7, 14, 15, 22, 24, 25, 27, 32, 33, 35, 40),
         30: (39, 48, 61, 82, 108, 111, 204, 206)}
_SM_B = {14: (39, 70, 97, 98, 101, 120), 19: (6, 19, 21, 26, 39, 46, 48),
         26: (4, 7, 12, 16, 17, 18, 20, 21, 22, 25, 26, 29, 30, 33, 35, 36, 42, 45, 46, 47, 56,
              58, 60, 62, 64, 65, 71, 72),
         28: (2, 3, 4, 9, 11, 12, 21, 28, 29, 38, 43), 30: (40, 131, 189)}
_SM_A_2015 = {**_SM_A, **_SM_B,
              **{e: tuple(sorted(_SM_A[e] + _SM_B[e])) for e in _SM_A.keys() & _SM_B.keys()},
              30: (36, 39, 48, 61, 82, 108, 111, 131, 189, 204, 206)}   # the catalog's 036
_ZLFN = {2: _WHOLE, 5: (2, 12, 13, 14, 22, 23, 25, 38), 8: (5, 15, 28, 35, 37, 42, 52, 53),
         19: (5,), 26: (2, 4, 17, 19, 39, 43, 48, 55, 59, 60, 70),
         28: (7, 14, 15, 22, 24, 25, 27, 32, 33, 40)}
_SALARIOS_MINIMOS: dict[str, tuple[int, tuple[tuple[int, dict], ...]]] = {
    "2000": (3270, ((3790, _SM_A), (3510, _SM_B))),
    "2010": (5447, ((5746, _SM_A), (5584, _SM_B))),
    "2015": (6645, ((7010, _SM_A_2015),)),
    "2020": (12322, ((18556, _ZLFN),)),
}
_INCOME_NE = 999999      # INGTRMEN not specified (999998: an income above 999,997)


def _salario_minimo(period: str, ent: pd.Series, mun: pd.Series) -> pd.Series:
    """The monthly minimum wage (cents) of each row's municipality in ``period``."""
    rest, areas = _SALARIOS_MINIMOS[period]
    key = ent * 1000 + mun
    out = pd.Series(30 * rest, index=ent.index, dtype="int64")
    for daily, area in areas:
        whole = [e for e, muns in area.items() if muns is _WHOLE]
        pairs = [e * 1000 + m for e, muns in area.items() if muns is not _WHOLE for m in muns]
        out[ent.isin(whole) | key.isin(pairs)] = 30 * daily
    return out


def _ingtrmen_sm(period: str):
    """The monthly income from work in minimum wages (7c, ``INGTRMEN_SM``), INEGI's groups:
    2000 below 1, from 1 to 2, above 2 and below 3, from 3 to 5, above 5 to 10, above 10
    (C2KEM08); 2010–2020 up to 1, above 1 to 2, 2 to 3, 3 to 5, 5 to 10, above 10. «No
    recibe ingresos» (0), «No especificado» (999999), «Blanco por pase» (not employed). The
    wage is the municipality's (:func:`_salario_minimo`); compared in cents, exactly."""
    dtype = _SM_2000 if period == "2000" else _SM

    def fn(src):
        income = src["INGTRMEN"]
        wage = _salario_minimo(period, src["ENT"], src["MUN"]).astype(float)
        cents = income * 100
        if period == "2000":
            bounds = [cents.lt(wage), cents.le(2 * wage), cents.lt(3 * wage),
                      cents.le(5 * wage), cents.le(10 * wage)]
        else:
            bounds = [cents.le(k * wage) for k in (1, 2, 3, 5, 10)]
        cats = list(dtype.categories)
        values = np.select([income.isna(), income.eq(0), income.eq(_INCOME_NE), *bounds,
                            income.gt(0)],
                           [cats[8], cats[0], cats[7], *cats[1:6], cats[6]], None)
        return {"INGTRMEN_SM": pd.Series(values, index=src.index).astype(dtype)}
    return fn


@functools.cache
def _educ_map() -> dict[int, str]:
    """(NIVACAD, ESCOLARI) → EDUC, keyed ``(nivacad + 1) * 1000 + escolari + 1`` (blank =
    -1): the legacy map is keyed by the two items' labels, ``"Primaria_6"``."""
    educ = _variables("personas")["EDUC"]["Categorías"]
    out = {}
    for n, n_label in _legacy_map("personas", "NIVACAD").items():
        for e, e_label in _legacy_map("personas", "ESCOLARI").items():
            if (label := educ.get(f"{n_label}_{e_label}")) is not None:
                out[(n + 1) * 1000 + e + 1] = label
    return out


_TECNICA_PRIMARIA = 6   # NIVACAD (2020): estudios técnicos o comerciales con primaria terminada


def _educ(src):
    """``EDUC`` (the legacy map of level and grade), ``EDUC_INEGI`` (the same, with the
    técnica studies after primaria, «Primaria_com» in ``EDUC``, as «Técnica_primaria») and
    ``EDUC_INEGI_DET`` (``EDUC_INEGI`` with «Posbásica» split by the level:
    :data:`_POSBASICA`)."""
    key = (src["NIVACAD"].fillna(_BLANK) + 1) * 1000 + src["ESCOLARI"].fillna(_BLANK) + 1
    educ = _as(key.map(_educ_map()), "personas", "EDUC")
    tecnica = src["NIVACAD"].eq(_TECNICA_PRIMARIA) & educ.notna()
    inegi = educ.astype(object).mask(tecnica, "Técnica_primaria")
    det = inegi.mask(inegi.eq("Posbásica"), src["NIVACAD"].map(_POSBASICA))
    return {"EDUC": educ, "EDUC_INEGI": _as(inegi, "personas", "EDUC_INEGI"),
            "EDUC_INEGI_DET": _as(det, "personas", "EDUC_INEGI_DET")}


def _educ_2000(src):
    """CGPV 2000's ``EDUC``: its level (recoded by :data:`_RECODE`) with the antecedent
    (``ANTESC``) of técnica studies — after primaria (2020: 6, «Primaria_com»), secundaria
    (7) or preparatoria (8); persons aged 5–29 who never attended school have no level but
    ``NIVELACAD`` 00, «sin instrucción» (2020: level and grade 0)."""
    nivacad, escolari = src["NIVACAD"], src["ESCOLARI"]
    tecnica = nivacad.eq(6)
    nivacad = nivacad.mask(tecnica, src["ANTESC"].map({1: 6, 2: 7, 3: 8}))
    none = nivacad.isna() & ~tecnica & src["NIVELACAD"].eq(0)
    nivacad, escolari = nivacad.mask(none, 0), escolari.mask(none, 0)
    # técnica after preparatoria: 2020's list stops at grade 4 (2000 records 5; «Posbásica»)
    escolari = escolari.mask(nivacad.eq(8) & escolari.between(5, 8), 4)
    return _educ(pd.DataFrame({"NIVACAD": nivacad, "ESCOLARI": escolari}))


def _educ_2005(src):
    """Conteo 2005's ``EDUC``: level and antecedent (``NIVANTES``, recoded to 2020's
    ``NIVACAD``) and grade (``GRA_APRO``); «sin escolaridad» has no grade (2020: 0), and a
    grade without a level is «No especificado»."""
    nivacad, escolari = src["NIVANTES"], src["GRA_APRO"]
    escolari = escolari.mask(nivacad.eq(0) & escolari.isna(), 0).mask(nivacad.eq(99), 99)
    return _educ(pd.DataFrame({"NIVACAD": nivacad, "ESCOLARI": escolari}))


def _educ_1995(src):
    """Conteo 1995's ``EDUC``: the level (``P5_4B``: ninguno, preescolar, primaria,
    secundaria, preparatoria, normal básica, profesional, posgrado — 2020: 0–4, 9, 11, 13 —,
    9 not specified) and its grades (``P5_4A``; 9 = not specified, a posgrado's 7th/8th year
    → 2020's last, 6); who never attended school (``P5_3`` 6) has no level (2020: level and
    grade 0), who did not say (9) is «No especificado». A technical career (``P5_5``) after
    secundaria or preparatoria (its requisite ``P5_7`` 2/3) lifts a secundaria to
    «Posbásica» (2020: 7/8), after primaria (1) a primaria to complete (6)."""
    level = src["P5_4B"].map({0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 9, 6: 11, 7: 13, 9: 99})
    grade = src["P5_4A"].mask(src["P5_4A"].eq(9) | level.eq(99), 99)
    grade = grade.mask(level.eq(13) & grade.between(7, 8), 6)
    tecnica, requisite = src["P5_5"].eq(1), src["P5_7"]
    after_sec = tecnica & requisite.isin([2, 3]) & level.eq(3)
    after_pri = tecnica & requisite.eq(1) & level.eq(2)
    level = level.mask(after_sec, requisite.map({2: 7, 3: 8})).mask(after_pri, 6)
    grade = grade.mask(after_sec | after_pri, 1)
    for answer, code in ((6, 0), (9, 99)):        # never attended / not specified: no level
        unasked = level.isna() & src["P5_3"].eq(answer)
        level, grade = level.mask(unasked, code), grade.mask(unasked, code)
    return _educ(pd.DataFrame({"NIVACAD": level, "ESCOLARI": grade}))


def _educ_1990(src):
    """CGPV 1990's ``EDUC``: whether the person approved a grade (``APROBO``; 0 = under 5,
    blank), the preschool years (``PRESCO``) of who did not, the highest level and its
    grades (``NIV_EST``, ``ANO_APRO``: primaria, secundaria, preparatoria, profesional,
    posgrado — 2020: 2, 3, 4, 11, 13; a profesional's 9th–11th year → 2020's last, 8, a
    posgrado's 7th–10th → 6), and the years of technical studies after secundaria
    (``TEC_SEC``) or of normal básica (``NOR_BAS``), which lift a complete secundaria to
    «Posbásica» (2020: 7, 9). Technical studies after a complete primaria (``TEC_PRIM``) are
    2020's 6: «Primaria_com» in ``EDUC``, «Técnica_primaria» in ``EDUC_INEGI`` (the 1990
    ITER's primaria completa leaves them out)."""
    aprobo, presco = src["APROBO"], src["PRESCO"]
    level = src["NIV_EST"].map({1: 2, 2: 3, 3: 4, 4: 11, 5: 13})
    grade = src["ANO_APRO"].mask(level.eq(11) & src["ANO_APRO"].between(9, 98), 8)
    grade = grade.mask(level.eq(13) & grade.between(7, 98), 6)
    tec_sec, normal = src["TEC_SEC"].gt(0), src["NOR_BAS"].gt(0)
    after_sec = level.eq(3) & (tec_sec | normal)
    level = level.mask(after_sec, np.where(tec_sec, 7, 9))
    grade = grade.mask(after_sec, src["TEC_SEC"].where(tec_sec, src["NOR_BAS"]))
    after_pri = level.eq(2) & grade.eq(6) & src["TEC_PRIM"].gt(0)
    level, grade = level.mask(after_pri, _TECNICA_PRIMARIA), grade.mask(after_pri, src["TEC_PRIM"])
    none = aprobo.eq(2)                               # no grade: preschool only, or none
    level, grade = level.mask(none, presco.gt(0).astype(int)), grade.mask(none, presco)
    level, grade = level.mask(aprobo.eq(9), 99), grade.mask(aprobo.eq(9), 99)
    level, grade = level.mask(aprobo.eq(0)), grade.mask(aprobo.eq(0))
    return _educ(pd.DataFrame({"NIVACAD": level, "ESCOLARI": grade}))


def _coarse(var: str, name: str, divisor: int):
    def fn(src):
        return {name: _mapped(np.floor(src[var] / divisor), "personas", name, name)}
    return fn


@functools.cache
def _cmo_sinco() -> dict[float, int]:
    """CGPV 2000's CMO code → its SINCO group (the bundled bridge, ``cpv_cmo_sinco.csv``;
    SINCO 2011's 59 → 52, as SINCO 2019 and the 2010/2015 recodes)."""
    from mxcensus._resources import cpv_cmo_sinco
    table = cpv_cmo_sinco()
    return {float(c): {59: 52}.get(int(g), int(g)) for c, g in zip(table["CMO"], table["GROUP"])}


def _ocup_cmo(src):
    """CGPV 2000's ``OCUPACION_C_COARSE`` (8e): its CMO code (``OCUACTIV_C``) through the
    bridge to SINCO groups — INEGI's SINCO 2011 comparison table, ENOE's 2012 panel where
    the table splits a code, the CMO subgroup's group where it lacks one, 99 «No
    especificado» where none places it (``scripts/build_cmo_sinco.py``); 9999 = not
    specified; blank = not employed. A code the bridge lacks stays missing (``derive``
    raises)."""
    code = src["OCUACTIV_C"]
    group = code.map(_cmo_sinco()).mask(code.isna(), _BLANK)
    name = "OCUPACION_C_COARSE"
    return {name: _as(group.map(_legacy_map("personas", name)), "personas", name)}


_SECONDARY = (21, 22, 23, 31, 32, 33)  # SCIAN: mining, utilities, construction, manufacturing


def _sector(var: str, divisor: int):
    """``SECTOR`` of a SCIAN code: its sector (the first two digits; ``divisor`` drops the
    rest) — 11 primary, 21–23 and 31–33 secondary, 99 not specified, any other sector of
    the classification tertiary; blank = not employed. An unknown sector stays missing."""
    def fn(src):
        sector = np.floor(src[var] / divisor)
        known = sector.isin(list(_legacy_map("personas", "ACTIVIDADES_C_COARSE")))
        values = np.select([sector.isna(), sector.eq(11), sector.isin(_SECONDARY),
                            sector.eq(99), known],
                           ["Blanco por pase", "Primario", "Secundario", "No especificado",
                            "Terciario"], None)
        return {"SECTOR": _as(values, "personas", "SECTOR")}
    return fn


def _sector_1990(src):
    """CGPV 1990's ``SECTOR``: the CMAP division, the first digit of ``C_A_ECO`` — 1
    agriculture (primary); 2 mining, 3 manufacturing, 4 electricity and construction
    (secondary); 5 trade, 6 transport, 7 finance, 8 services (tertiary); 9 not specified;
    0 = not employed (its 00000)."""
    division = np.floor(src["C_A_ECO"] / 10000)
    values = np.select([division.eq(0), division.eq(1), division.isin([2, 3, 4]),
                        division.isin([5, 6, 7, 8]), division.eq(9)],
                       ["Blanco por pase", "Primario", "Secundario", "Terciario",
                        "No especificado"], None)
    return {"SECTOR": _as(values, "personas", "SECTOR")}


def _dis(src):
    items = src[list(_DIS_ITEMS)]
    unspecified = items.isin([8, 9]).any(axis=1)
    out = {}
    for name, has in (("DIS_CON", items.isin([3, 4]).any(axis=1)),
                      ("DIS_LIMI", items.eq(2).any(axis=1))):
        out[name] = _as(np.select([has, unspecified], ["Sí", "No especificado"], "No"),
                        "personas", name)
    return out


def _dis_inegi(src):
    """INEGI's definitions (the EIC 2025 estimates, matched exactly): a disability is much
    difficulty, not being able, or a difficulty of unknown degree (code 8) in at least one
    activity; a limitation is some difficulty (2) in at least one, without a disability."""
    items = src[list(_DIS_ITEMS)]
    disabled = items.isin([3, 4, 8]).any(axis=1)
    limited = items.eq(2).any(axis=1) & ~disabled
    unspecified = items.eq(9).any(axis=1)
    return {"DISCAPACIDAD": _as(np.select([disabled, unspecified], ["Sí", "No especificado"],
                                          "No"), "personas", "DISCAPACIDAD"),
            "LIMITACION": _as(np.select([limited, disabled, unspecified],
                                        ["Sí", "No", "No especificado"], "No"),
                              "personas", "LIMITACION")}


def _sin_disc_lim(src):
    """INEGI's population «sin discapacidad, limitación, problema o condición mental» (the
    EIC 2025 ``PSIND_LIM``, matched exactly in every state and municipality): no difficulty
    of any degree (2, 3, 4, 8) in the six activities and no mental condition (``DIS_MENTAL``
    5). Persons whose seven answers are all unspecified (9) are «No especificado»; one
    unspecified answer among others counts as none (the legacy ``PSIND_LIM`` cells require
    all seven to be answered «no»)."""
    items, mental = src[list(_DIS_ITEMS)], src["DIS_MENTAL"]
    known = items.isin([1, 2, 3, 4, 8, 9]).all(axis=1) & mental.isin([5, 6, 9])
    some = items.isin([2, 3, 4, 8]).any(axis=1) | mental.eq(5)
    unspecified = items.eq(9).all(axis=1) & mental.eq(9)
    values = np.select([~known, some, unspecified], [None, "No", "No especificado"], "Sí")
    return {"SIN_DISC_LIM": _as(values, "personas", "SIN_DISC_LIM")}


def _as_dummies(flags: Mapping[str, pd.Series], unknown: pd.Series) -> dict[str, pd.Series]:
    """Boolean flags → 0/1 dummies, missing on the ``unknown`` rows (a code no dummy names,
    which :func:`derive` reports)."""
    return {k: v.astype(int).astype(_DUMMY).mask(unknown) for k, v in flags.items()}


def _summaries(has: Mapping[int, pd.Series], codes: tuple[int, ...]) -> dict[str, pd.Series]:
    """The summary dummies: the ISSSTE, federal or state (6y: the EIC 2025's ``PDER_ISTE``;
    Censo 2020's counts the federal one only), a public institution (1–6), any (1–8)."""
    def any_of(selected):
        return pd.concat([has[c] for c in codes if c in selected], axis=1).any(axis=1)
    return {"DHSERSAL_ISSSTE_T": any_of((2, 3)), "DHSERSAL_PUB": any_of(range(1, 7)),
            "DHSERSAL_AFIL": any_of(range(1, 9))}


def _dhsersal(codes: tuple[int, ...]):
    """The dummies of the 2020 ``codes`` an edition offers, and the summaries."""
    def fn(src):
        d1, d2 = src["DHSERSAL1"], src["DHSERSAL2"]
        has = {code: d1.eq(code) | d2.eq(code) for code in codes}
        out = {_DHSERSAL[code]: has[code] for code in codes} | _summaries(has, codes)
        known = [*codes, 99]
        unknown = (d1.notna() & ~d1.isin(known)) | (d2.notna() & ~d2.isin(known))
        return _as_dummies(out, unknown)
    return fn


# CGPV 2000 and Conteo 2005 ask one item per institution: item → {its code: the 2020
# DHSERSAL code}. 2000: IMSS 9 = coverage not known at all (2020: 99), OTRINS_V 4 = covered
# by an institution not named (INEGI's 2000 tabulados count it as «otra institución»), no
# Seguro Popular, private or state institutions (in «otra»). 2005: OTRA_INS 1 = the state
# governments' institutions (2020: 03, ISSSTE estatal), 2 another institution (08), 3 private
# institutions with subrogated services (07, private), 9 an institution not named (08).
_DHSERSAL_ITEMS = {
    "2000": {"IMSS": {1: 1, 9: 99}, "ISSSTE": {2: 2}, "PEMEX": {3: 4}, "OTRINS_V": {4: 8},
             "NOTIEDER": {5: 9}},
    "2005": {"IMSS": {1: 1}, "ISSSTE": {1: 2}, "PEMEX": {1: 4}, "SEGU_POP": {1: 5},
             "INST_PRI": {1: 7}, "OTRA_INS": {1: 3, 2: 8, 3: 7, 9: 8},
             "SIN_DERE": {6: 9, 9: 99}},
}


def _dhsersal_codes(period: str) -> tuple[int, ...]:
    return tuple(sorted({c for m in _DHSERSAL_ITEMS[period].values() for c in m.values()
                         if c in _DHSERSAL}))


def _dhsersal_items(period: str):
    """The 2020 dummies from an edition's one-item-per-institution coverage."""
    items, codes = _DHSERSAL_ITEMS[period], _dhsersal_codes(period)

    def fn(src):
        has = {code: pd.Series(False, index=src.index) for code in codes}
        unknown = pd.Series(False, index=src.index)
        for item, mapping in items.items():
            v = src[item]
            unknown |= v.notna() & ~v.isin(list(mapping))
            for raw, code in mapping.items():
                if code in has:
                    has[code] |= v.eq(raw)
        out = {_DHSERSAL[code]: has[code] for code in codes} | _summaries(has, codes)
        return _as_dummies(out, unknown)
    return fn


def _dhsersal_names(codes: tuple[int, ...]) -> tuple[str, ...]:
    return (*(_DHSERSAL[c] for c in codes), "DHSERSAL_ISSSTE_T", "DHSERSAL_PUB",
            "DHSERSAL_AFIL")


def _dummies(table: str, items: tuple[str, ...], prefix: str,
             labels: Mapping[int, str] | None = None):
    """One 0/1 column per code of ``labels`` (default: the legacy map of ``items[0]``; the
    labels name the columns): 1 when any of ``items`` has that code (a blank item sets the
    ``Blanco por pase`` dummy)."""
    def fn(src):
        codes = src[list(items)].fillna(_BLANK)
        names = labels or _legacy_map(table, items[0])
        flags = {f"{prefix}_{label}": codes.eq(code).any(axis=1) for code, label in names.items()}
        return _as_dummies(flags, ~codes.isin(list(names)).all(axis=1))
    return fn


def _dummy_names(table: str, items: tuple[str, ...], prefix: str,
                 labels: Mapping[int, str] | None = None) -> tuple[str, ...]:
    return tuple(f"{prefix}_{label}" for label in (labels or _legacy_map(table, items[0])).values())


# 7a: the commute modes the EIC 2025 estimates group (its PASIS_MET, _TROL, _TAXI and
# POCUP_*): metro or metrobús, trolebús or camión/autobús/combi/colectivo, either taxi
# (2020 codes, the same in 2025); summary dummies beside the one per code.
_TRASLADO_T = {"METRO_T": (3, 5), "BUS_T": (4, 6), "TAXI_T": (8, 9)}


def _traslado_t(items: tuple[str, ...], prefix: str):
    """1 when any of ``items`` has a code of the group (an unknown code is reported by the
    per-code dummies)."""
    def fn(src):
        codes = src[list(items)]
        flags = {f"{prefix}_{name}": codes.isin(group).any(axis=1)
                 for name, group in _TRASLADO_T.items()}
        return _as_dummies(flags, pd.Series(False, index=src.index))
    return fn


def _afil_acceso(src):
    """Affiliated to any institution (``DHSERSAL_AFIL``) or, not affiliated, recognising an
    access to the public health services (``DHSERSAL_ACCESO`` 1): the EIC 2025's
    ``PcSSyRecAc`` (7a). An unknown access code is left missing."""
    afil = src["DHSERSAL1"].between(1, 8) | src["DHSERSAL2"].between(1, 8)
    access = src["DHSERSAL_ACCESO"]
    return _as_dummies({"DHSERSAL_AFIL_ACCESO": afil | access.eq(1)},
                       access.notna() & ~access.isin([1, 3, 9]))


# EIC 2015 commute code → its Censo 2020 code where the mode is the same (4 = transporte
# escolar/laboral, 2020's «de personal»). Codes 1–3 merge 2020 modes (camión + both taxis,
# metro + metrobús, automóvil + motocicleta) and keep 2015's wording; 2020's trolebús has no
# 2015 code.
_TRASLADO_2015_SAME = {4: 7, 5: 2, 6: 1, 7: 12, 9: 99, _BLANK: _BLANK}
_TRASLADO_2015_OWN = {1: "Camión, taxi, combi o colectivo", 2: "Metro, metrobús o tren ligero",
                      3: "Vehículo particular (automóvil, camioneta o motocicleta)"}


@functools.cache
def _traslado_2015(item: str) -> dict[int, str]:
    """EIC 2015 commute code → dummy label (the 2020 ``item``'s label where the mode is
    the same)."""
    legacy = _legacy_map("personas", item)
    same = {code: legacy[ref] for code, ref in _TRASLADO_2015_SAME.items()}
    return {code: _TRASLADO_2015_OWN.get(code) or same[code]
            for code in sorted({*_TRASLADO_2015_OWN, *same}, key=lambda c: (c == _BLANK, c))}


# EIC 2015's one financing item (one answer) → the 2020 code where the source is the same;
# its 1 merges INFONAVIT, FOVISSSTE and PEMEX (2020: 1–3) and keeps 2015's wording.
_FINANCIAMIENTO_2015_SAME = {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 9: 9, _BLANK: _BLANK}


@functools.cache
def _financiamiento_2015() -> dict[int, str]:
    """EIC 2015 financing code → dummy label (the 2020 label where the source is the same)."""
    legacy = _legacy_map("viviendas", "FINANCIAMIENTO1")
    return {1: "INFONAVIT, FOVISSSTE o PEMEX",
            **{code: legacy[ref] for code, ref in _FINANCIAMIENTO_2015_SAME.items()}}


def _lim_actividad(src):
    """Censo 2010's «limitación en la actividad» (its ITER's ``PCON_LIM``/``PSIN_LIM``): a
    difficulty in at least one activity (``DISCAP1``–``DISCAP7``), none (``DISCAP8`` = 17)
    or not specified (99). A row with neither is left missing (:func:`derive` reports it)."""
    limited = src[list(_DISCAP_ITEMS[:7])].notna().any(axis=1)
    none = src["DISCAP8"]
    values = np.select([limited, none.eq(17), none.eq(99)], ["Sí", "No", "No especificado"],
                       None)
    return {"LIM_ACTIVIDAD": _as(values, "personas", "LIM_ACTIVIDAD")}


def _cat(table: str, var: str, name: str):
    def fn(src):
        return {name: _mapped(src[var], table, name, name)}
    return fn


_ENT_NE = 997            # an entity not specified (2020 code; each edition's via _RECODE)


def _ent_pais_cat(var: str, name: str, abroad: str | None = None, inegi: str | None = None):
    """Entity or country → ``OtraEnt``/``OtroPais``/…, ``EstaEnt`` for the person's entity
    (Censo 2010 splits the answer: the entity item ``var``, else the country item
    ``abroad``). ``inegi`` names INEGI's version too (6y), with the unspecified entity
    (``OtraEnt`` by the legacy rule) «No especificado»: its tabulados' and the EIC 2025
    estimates' ``PNACOE`` (exact in every municipality)."""
    def fn(src):
        code = src[var] if abroad is None else src[var].fillna(src[abroad])
        cat = _mapped(code, "personas", name, name).mask(code.eq(src["ENT"]), "EstaEnt")
        out = {name: cat}
        if inegi:
            out[inegi] = _as(cat.mask(code.eq(_ENT_NE), "No especificado"), "personas", inegi)
        return out
    return fn


def _ent_pais_inegi(var: str, name: str):
    """A place item (entity or country) by INEGI's rule (7a; the EIC 2025's ``PASIS_ENT``/
    ``_OENT``, ``POCUP_ENT``/``_OENT``): ``EstaEnt`` for the person's entity, ``OtraEnt``
    for another, ``OtroPais`` for a country or the country not specified (998), «No
    especificado» for the entity not specified (997) or 999; the residence's labels."""
    def fn(src):
        code = src[var]
        cat = _mapped(code, "personas", "ENT_PAIS_RES_CAT", name).mask(code.eq(src["ENT"]),
                                                                      "EstaEnt")
        return {name: cat.mask(code.eq(_ENT_NE), "No especificado")}
    return fn


_USA = 221               # Estados Unidos de América (the 2020 country catalog)


def _lugar(var: str, mun: str, name: str, abroad: str | None = None):
    """A place by the person's own municipality and entity: the residence five years
    earlier (7a, ``LUGAR_RES_5A``; the EIC 2025's ``PRESM20`` … ``PRESOP20``), the place of
    school and of work (7b, ``LUGAR_ASI``/``LUGAR_TRAB``; INEGI's 2010–2020 tabulados, 7c:
    CGPV 2000's). The own entity by the municipality (``mun`` against the person's; 999
    «Municipio no especificado»), another entity, the United States, another country or the
    country not specified (998), not specified (the entity not specified, 997, or 999),
    blank (not asked). Censo 2010 splits the residence's answer: the entity item ``var``, else the
    country item ``abroad``. A code the residence's labels lack, or the own entity without
    a municipality, is left missing (:func:`derive` reports it)."""
    def fn(src):
        code = src[var] if abroad is None else src[var].fillna(src[abroad])
        cat = _mapped(code, "personas", "ENT_PAIS_RES_CAT", "ENT_PAIS_RES_CAT").astype(object)
        own, where = code.eq(src["ENT"]), src[mun]
        values = np.select(
            [own & where.eq(src["MUN"]), own & where.eq(999), own & where.notna(), own,
             code.eq(_ENT_NE), code.eq(_USA), cat.eq("OtraEnt"), cat.eq("OtroPais"),
             cat.eq("No especificado"), cat.eq("Blanco por pase")],
            ["Mismo municipio", "Municipio no especificado", "Otro municipio", None,
             "No especificado", "Estados Unidos", "Otra entidad", "Otro país",
             "No especificado", "Blanco por pase"], None)
        return {name: _as(values, "personas", name)}
    return fn


def _pointer_2010(number: pd.Series, code: pd.Series) -> pd.Series:
    """Censo 2010's pointer pair («en esta vivienda, ¿vive…? ¿Quién es?»: the row number,
    99 when the row was not given, and the code item: 88 not here, 99 not specified) → a
    2020 pointer code: 1 (a row of this dwelling), 96 (not here), 99 (not specified: a 99
    code, or a row given as 99 — INEGI's ampliado tabulado ``12_01A`` counts those not
    specified, to the person nationally; 6q); blank when both are blank (not asked). Any
    other code becomes -99, which no category takes."""
    out = code.replace({88: 96}).mask(code.isna() & number.notna(), 1)
    out = out.mask(code.isna() & number.eq(99), 99)
    return out.where(code.isna() | code.isin([88, 99]), -99)


def _pareja_2010(src):
    code = _pointer_2010(src["IDCONYUGE"], src["IDCONYUGEC"])
    return {"IDENT_PAREJA_CAT": _mapped(code, "personas", "IDENT_PAREJA_CAT",
                                        "IDENT_PAREJA_CAT")}


def _en_vivienda(name: str, item: str, code_item: str | None = None):
    """Whether the mother or father lives in the dwelling, from the 2020 pointer codes: a
    row number 01–54 (Sí), 96–98 another dwelling, dead or unknown (No), 99 (No
    especificado). Censo 2010 (``code_item``) reads its pair through :func:`_pointer_2010`."""
    def fn(src):
        codes = src[item] if code_item is None else _pointer_2010(src[item], src[code_item])
        values = np.select([codes.between(1, 54), codes.isin([96, 97, 98]), codes.eq(99)],
                           ["Sí", "No", "No especificado"], None)
        return {name: _as(values, "personas", name)}
    return fn


# Censo 2010 religion (``OTRAREL_C``; catalog TC_RELIGION_2010, six digits, the first two
# the group) → a Censo 2020 code of the same ``RELIGION_CAT`` group: 11 católica, 12 ortodoxa
# (and 1207xx «cristianos tradicionalistas»), 13 protestantes históricas, 14 pentecostales y
# evangélicas, 15 bíblicas diferentes de evangélicas, 21–29 the other credos (origen
# oriental, judaico, islámico, New Age, esotéricas, raíces étnicas, espiritualistas, otros
# movimientos, cultos populares), 31 sin religión, 99 no especificada.
_RELIGION_2010 = {11: 1101, 12: 1201, 13: 1307, 14: 1326, 15: 1331, 21: 2303, 22: 2101,
                  23: 2201, 24: 2401, 25: 2401, 26: 2501, 27: 2701, 28: 2901, 29: 2801,
                  31: 3101, 99: 9999}
# Codes whose 2020 counterpart is not their group's: the neo-Israelite movements (2010 a
# judaic credo, its ITER's POTRAS_REL; 2020's 1325, an evangelical church — 2020's grouping
# is kept) and «sin adscripción religiosa» (2020's 3104).
_RELIGION_2010_CODES = {220100: 1325, 310100: 3104}


def _religion_2010(src, column: str = "RELIGION_CAT", codes: dict = _RELIGION_2010_CODES):
    """Censo 2010's religion → ``RELIGION_CAT`` (:data:`_RELIGION_2010`); a code of another
    group is left missing (:func:`derive` reports it)."""
    code = src["OTRAREL_C"]
    group = code.where(code.between(100000, 999999)) // 10000
    code2020 = code.map(codes).fillna(group.map(_RELIGION_2010))
    return {column: _mapped(code2020, "personas", "RELIGION_CAT", "RELIGION_CAT")}


def _religion_inegi_2010(src):
    """7g: Censo 2010's religion by its own classification (``RELIGION_INEGI``,
    ``RELIGION_CAT``'s labels): the neo-Israelite movements (220100) are a judaic credo,
    «Otros credos» — its ITER's ``POTRAS_REL``, not ``PNCATOLICA`` —, exact in the 233
    municipalities its sample enumerated completely where every age and sex count is the
    ITER's (``RELIGION_CAT`` keeps 2020's grouping, an evangelical church: 6f)."""
    return _religion_2010(src, "RELIGION_INEGI",
                          {c: v for c, v in _RELIGION_2010_CODES.items() if c != 220100})


# CGPV 2000 religion (OTRAREL_C, 4 digits, asked of persons aged 5+): its FD makes 0001
# católica and 9100 ninguna; the first digit is the group of INEGI's 2000 classification,
# whose tabulados' groups these reproduce: 1 protestantes y evangélicas, 2 bíblicas no
# evangélicas (2020: both «Protestante/cristiano evangélico»), 3–8 and 9001 otras
# religiones, 9999 not specified. Under 5: «Blanco por pase», a category of 2000 only.
def _religion_5plus(code2020: pd.Series, blank: pd.Series, period: str) -> dict:
    """``RELIGION_CAT`` of an edition that asked the 5+ only: the 2020 code's group,
    «Blanco por pase» on the ``blank`` rows (an unknown code stays missing)."""
    labels = code2020.map(_legacy_map("personas", "RELIGION_CAT")).mask(blank, "Blanco por pase")
    return {"RELIGION_CAT": labels.astype(_period_dtypes("personas", period)["RELIGION_CAT"])}


def _religion_2000(src):
    code = src["OTRAREL_C"]
    code2020 = pd.Series(np.select(
        [code.eq(1), code.eq(9100), code.eq(9999), code.eq(9001), code.between(1101, 1999),
         code.between(2000, 2999), code.between(3000, 8999)],
        [1101, 3101, 9999, 2901, 1326, 1331, 2901], np.nan), index=code.index)
    return _religion_5plus(code2020, code.isna(), "2000")


def _religion_1990(src):
    """CGPV 1990's religion (recoded to a 2020 code of its group: ninguna, católica,
    protestante o evangélica, judaica and otra — both «Otros credos» —, not specified);
    0 = under 5 (blank)."""
    return _religion_5plus(src["RELIGION"], src["RELIGION"].isna(), "1990")


@functools.cache
def _period_dtypes(table: str, period: str) -> dict[str, pd.CategoricalDtype]:
    """Derived columns whose categories differ in an edition: CGPV 1990 and 2000 asked
    religion of persons aged 5+ only, so their ``RELIGION_CAT`` adds «Blanco por pase»;
    CGPV 2000's income groups in minimum wages are bounded otherwise (7c, ``_SM_2000``)."""
    out = {}
    if table == "personas" and period in ("1990", "2000"):
        cats = list(_legacy_dtypes("personas")["RELIGION_CAT"].categories)
        out["RELIGION_CAT"] = pd.CategoricalDtype([*cats, "Blanco por pase"])
    if table == "personas" and period == "2000":
        out["INGTRMEN_SM"] = _SM_2000
    return out


def _ingtrhog_cat(src):
    return {"INGTRHOG_CAT": _cut(src["INGTRHOG"], "viviendas", "INGTRHOG_CAT", _INCOME_BINS,
                                 _INCOME_LABELS, right=False, blank=2e6)}


_ROOMS_NE = 99           # TOTCUART (2010–2025): rooms not specified


def _ocup_cuarto(src):
    """Occupants per room (6z): ``NUMPERS`` ÷ ``TOTCUART`` (the rooms counting the kitchen)
    up to 2.5 or more — the EIC 2025's ``VPH_2_5OCU``, exact at every published geography.
    Rooms not specified (99) → «No especificado», blank (a dwelling class without
    characteristics) → «Blanco por pase»; any other room code is left missing."""
    rooms, persons = src["TOTCUART"], src["NUMPERS"]
    valid = rooms.between(1, 25) & persons.ge(1)
    values = pd.Series(None, index=src.index, dtype=object)
    values[valid] = np.where((persons / rooms)[valid].gt(2.5), "Más de 2.5", "Hasta 2.5")
    values[rooms.eq(_ROOMS_NE)] = "No especificado"
    values[rooms.isna()] = "Blanco por pase"
    return {"OCUP_CUARTO_CAT": _as(values, "viviendas", "OCUP_CUARTO_CAT")}


# TIPOHOG (2000–2025, the same codes): nuclear, ampliado, compuesto and «no especificado»
# (all familiar), unipersonal and corresidente (no familiar), 9 «no se sabe la composición».
# The EIC 2025 counts 4 as familiar and 9 as neither (its PCN_HOG_FAM/_NFAM).
_CLASES = {**dict.fromkeys((1, 2, 3, 4), "Familiar"), 5: "No familiar", 6: "No familiar",
           9: "No especificado"}


def _primer_hogar(src):
    """CGPV 2000's dwelling rows are households (``NUMHOG``): the first household's row
    stands for the dwelling (every dwelling has exactly one), so the dwelling indicators
    count it (7f: ``_PER_DWELLING``)."""
    numhog = src["NUMHOG"]
    first = pd.Series(np.where(numhog.eq(1), "Sí", "No"), index=numhog.index)
    return {"PRIMER_HOGAR": first.where(numhog.notna()).astype(_SI_NO)}


def _totcuart_inegi(src):
    """CGPV 2000's rooms as its ITER counts them («no incluye cocina exclusiva»: its
    ``PRO_OCVP``, ``VP2_5CUAR``): ``TOTCUART``, which counts the kitchen, less an exclusive
    kitchen nobody sleeps in (``COCINA`` 1 «sí cuenta con un cuarto» and ``COCDOR`` 4 «no
    duermen en la cocina»; an unspecified ``COCDOR`` keeps it); missing where ``TOTCUART``
    is not specified (99). A number, not a category: the value of its occupants per room
    (7f, :func:`cpv_ratio_constraints`)."""
    rooms = src["TOTCUART"].where(src["TOTCUART"].ne(99))
    kitchen = (src["COCINA"].eq(1) & src["COCDOR"].eq(4)).astype(int)
    return {"TOTCUART_INEGI": (rooms - kitchen).astype("Int64")}


def _clase_hog(src):
    """The household's class (6z): familiar or not, from INEGI's household type ``TIPOHOG``
    (on the dwelling; the persons take their household's from the dwelling file:
    ``cpv._attach_dwellings``)."""
    return {"CLASE_HOG": _as(src["TIPOHOG"].map(_CLASES), "viviendas", "CLASE_HOG")}


# The household's non-labour income items (2015–2025, «Otros ingresos»; codes yes/no: 1/2,
# 3/4, 5/6, 7/8; 9 not specified).
_INGR_OTROS = {"INGR_PEROTROPAIS": (1, 2), "INGR_PERDENTPAIS": (3, 4), "INGR_AYUGOB": (5, 6),
               "INGR_JUBPEN": (7, 8)}


def _ingr_otros(src):
    """Whether a member receives money from a source other than work (6z; the EIC 2025's
    ``HOG_PERC``/``HOG_NPERC``): «Sí» when any of the four items is yes, «No» when all four
    are no, else «No especificado»; a code other than the item's yes, no or 9 is left
    missing."""
    def every(codes_of) -> pd.DataFrame:
        return pd.concat([src[item].isin(codes_of(codes)) for item, codes in
                          _INGR_OTROS.items()], axis=1)

    values = pd.Series("No especificado", index=src.index, dtype=object)
    values[every(lambda c: c[:1]).any(axis=1)] = "Sí"
    values[every(lambda c: c[1:]).all(axis=1)] = "No"
    values[~every(lambda c: (*c, 9)).all(axis=1)] = None
    return {"INGR_OTROS": _as(values, "viviendas", "INGR_OTROS")}


def _jefe_sexo(src):
    """The household head's sex (2020's dwelling item ``JEFE_SEXO``, its labels) from the
    head's ``SEXO``, which the dwelling loader brings from the person file for the editions
    without the item (``cpv._attach_heads``: CGPV 2000, Conteo 2005, Censo 2010; 6s)."""
    return {"JEFE_SEXO": _mapped(src["SEXO"], "viviendas", "JEFE_SEXO", "JEFE_SEXO")}


def _hogjef_sexo(heads: tuple[int, ...]):
    """The sex of each person's household head (6t; ``JEFE_SEXO``'s labels): the ``SEXO``
    of the one person of the household (``src[_HOUSEHOLD]``) whose ``PARENTESCO`` is in
    ``heads``. A household without exactly one head raises."""
    def func(src):
        household = src[_HOUSEHOLD]
        is_head = src["PARENTESCO"].isin(heads)
        n = is_head.groupby(household).transform("sum")
        if (n != 1).any():
            bad = household[n != 1].nunique()
            raise ValueError(f"HOGJEF_SEXO: {bad} households without exactly one head "
                             f"(PARENTESCO code {' or '.join(map(str, heads))})")
        sexo = src["SEXO"].where(is_head).groupby(household).transform("max")
        return {"HOGJEF_SEXO": _mapped(sexo, "viviendas", "JEFE_SEXO", "HOGJEF_SEXO")}
    return func


def _hog_flag(name: str, item: str, members: tuple[int, ...]):
    """Whether each person's household has one of its ``members`` (relationship codes)
    answering 1 to ``item`` (codes 1, 3, 9; 2020 codes): «Sí»/«No» (not specified or not
    asked is not). A household with another code is left missing (:func:`derive` reports
    it)."""
    def func(src):
        household, answer = src[_HOUSEHOLD], src[item]
        yes = answer.eq(1) & src["PARENTESCO"].isin(members)
        unknown = (answer.notna() & ~answer.isin([1, 3, 9])).groupby(household).transform("any")
        values = np.where(yes.groupby(household).transform("any"), "Sí", "No")
        return {name: _as(values, "personas", name).mask(unknown.to_numpy())}
    return func


def _hog_ind(members: tuple[int, ...]):
    """Whether each person's household is indigenous (6w), by the edition's own definition:
    one of its ``members`` (relationship codes, :data:`_IND_CODES`) speaks an indigenous
    language (``HLENGUA`` 1); not speaking, not specified or not asked (the youngest) is
    not."""
    return _hog_flag("HOG_IND", "HLENGUA", members)


# 7a: the Afro-descendant households (the EIC 2025's HOG_AFRO/PHOG_AFRO, exact in every
# geography): one of the indigenous households' members (_IND_CODES: head, partner,
# parents, step-parents, grandparents, parents-in-law) considers themself Afro-Mexican or
# Afro-descendant (AFRODES 1). The other editions publish no such count.
_AFRO_CODES: dict[str, tuple[int, ...]] = {"2025": _IND_CODES["2025"]}


def _hog_afro(members: tuple[int, ...]):
    return _hog_flag("HOG_AFRO", "AFRODES", members)


def _linea(item: str, lines: Mapping[str, tuple[int, ...]]):
    """The kinship line of each person (8f) from the edition's relationship ``item`` and its
    ``lines`` (:data:`_LINEAS`); a code of no line is left missing (:func:`derive` reports
    it)."""
    lookup = {code: line for line, codes in lines.items() for code in codes}

    def func(src):
        return {"LINEA_PARENTESCO": _as(src[item].map(lookup), "personas", "LINEA_PARENTESCO")}
    return func


def _linea_2010(src):
    """Censo 2010's kinship line (8f): ``PARENT``'s, and for its «otro parentesco» (08) the
    detail ``OTROPARE_C``'s (:data:`_OTRO_2010`); an 08 without a detail code is «Otro
    parentesco», an unknown detail is left missing."""
    rel, other = src["PARENT"], src["OTROPARE_C"]
    detail = other.map(_OTRO_2010).where(other.notna(), "Otro parentesco")
    values = rel.map(_PARENT_2010).where(rel.ne(8), detail)
    return {"LINEA_PARENTESCO": _as(values, "personas", "LINEA_PARENTESCO")}


def _periods_by(codes: Mapping[str, tuple]) -> dict[tuple, tuple[str, ...]]:
    """Edition → codes, inverted: codes → the editions that share them."""
    out: dict[tuple, tuple[str, ...]] = {}
    for period, value in codes.items():
        out[value] = (*out.get(value, ()), period)
    return out


# The editions whose household records are a household table: the Conteo 2005, whose
# dwelling file has one row per dwelling (6v). Elsewhere a dwelling row is a household
# (CGPV 2000's dwelling file has one row per household; one household per dwelling from
# 2010 on).
_HOUSEHOLD_TABLE = ("2005",)


def _household_records(periods: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """The table whose rows are the households of each of ``periods`` → those editions."""
    out: dict[str, tuple[str, ...]] = {}
    for period in periods:
        table = "hogares" if period in _HOUSEHOLD_TABLE else "viviendas"
        out[table] = (*out.get(table, ()), period)
    return out


@dataclass(frozen=True)
class _Derivation:
    table: str
    columns: tuple[str, ...]
    sources: tuple[str, ...]
    periods: tuple[str, ...]          # editions whose source codes were verified
    func: Callable[[pd.DataFrame], Mapping[str, pd.Series]]
    household: bool = False           # func also reads each record's household (_HOUSEHOLD)
    # A household's column on its dwelling or household record (6x): ``sources`` are person
    # items, read from the household's members (``derive(members=)``), and ``func`` is the
    # person derivation's; each record takes its household's value.
    members: bool = False


_NEW = ("2020", "2025")
_OLD = ("2010", "2015")
_SINCE_2015 = ("2015", "2020", "2025")
_ALL = ("2010", "2015", "2020", "2025")
_SINCE_2000 = ("2000", *_ALL)                  # the editions with a sample's full person record
_EVERY = ("2000", "2005", *_ALL)
_OLDEST = ("1990", "1995")                     # person files only (cpv: dwellings built from them)
_ESC = ("MED_TRASLADO_ESC1", "MED_TRASLADO_ESC2", "MED_TRASLADO_ESC3")
_TRAB = ("MED_TRASLADO_TRAB1", "MED_TRASLADO_TRAB2", "MED_TRASLADO_TRAB3")
_FIN = ("FINANCIAMIENTO1", "FINANCIAMIENTO2", "FINANCIAMIENTO3")
_EDUC = ("EDUC", "EDUC_INEGI", "EDUC_INEGI_DET")
_NAC = ("ENT_PAIS_NAC_CAT", "ENT_PAIS_NAC_INEGI")      # the legacy rule and INEGI's (6y)


@functools.cache
def _registry() -> tuple[_Derivation, ...]:
    D = _Derivation
    per, viv, hog = "personas", "viviendas", "hogares"
    esc15, trab15 = _traslado_2015(_ESC[0]), _traslado_2015(_TRAB[0])
    fin15 = _financiamiento_2015()
    return (
        D(per, ("EDAD_CAT",), ("EDAD",), (*_OLDEST, *_EVERY), _edad_cat),
        D(per, ("EDAD_QUIN",), ("EDAD",), (*_OLDEST, *_EVERY), _edad_quin),          # 7a
        D(per, ("INGTRMEN_CAT",), ("INGTRMEN",), ("1995", *_SINCE_2000), _ingtrmen_cat),
        D(per, ("INGTRMEN_CAT",), ("INGTRMEN", "CONACT"), ("1990",), _ingtrmen_1990),
        *(D(per, ("INGTRMEN_SM",), ("INGTRMEN", "ENT", "MUN"), (p,), _ingtrmen_sm(p))  # 7c
          for p in _SALARIOS_MINIMOS),
        D(per, ("HORTRA_CAT",), ("HORTRA",), ("1995", "2010", "2020", "2025"), _hortra_cat),
        D(per, ("HORTRA_CAT",), ("HORTRA", "CONACT"), ("2000",), _hortra_2000),
        D(per, ("HORTRA_CAT",), ("HORTRA", "CONACT"), ("1990",), _hortra_1990),
        D(per, _EDUC, ("NIVACAD", "ESCOLARI"), _ALL, _educ),
        D(per, _EDUC, ("NIVACAD", "ANTESC", "ESCOLARI", "NIVELACAD"), ("2000",), _educ_2000),
        D(per, _EDUC, ("NIVANTES", "GRA_APRO"), ("2005",), _educ_2005),
        D(per, _EDUC, ("P5_3", "P5_4B", "P5_4A", "P5_5", "P5_7"), ("1995",), _educ_1995),
        D(per, _EDUC, ("APROBO", "PRESCO", "NIV_EST", "ANO_APRO", "TEC_PRIM", "TEC_SEC",
                       "NOR_BAS"), ("1990",), _educ_1990),
        D(per, ("OCUPACION_C_COARSE",), ("OCUPACION_C",), _SINCE_2015,
          _coarse("OCUPACION_C", "OCUPACION_C_COARSE", 10)),
        D(per, ("OCUPACION_C_COARSE",), ("OCUACTIV_C",), ("2010",),
          _coarse("OCUACTIV_C", "OCUPACION_C_COARSE", 100)),
        D(per, ("OCUPACION_C_COARSE",), ("OCUACTIV_C",), ("2000",), _ocup_cmo),     # 8e: CMO
        D(per, ("ACTIVIDADES_C_COARSE",), ("ACTIVIDADES_C",), _ALL,
          _coarse("ACTIVIDADES_C", "ACTIVIDADES_C_COARSE", 100)),
        D(per, ("ACTIVIDADES_C_COARSE",), ("ACTTRAB_C",), ("2000",),      # SCIAN subsector
          _coarse("ACTTRAB_C", "ACTIVIDADES_C_COARSE", 10)),
        D(per, ("SECTOR",), ("ACTIVIDADES_C",), _ALL, _sector("ACTIVIDADES_C", 100)),
        D(per, ("SECTOR",), ("ACTTRAB_C",), ("2000",), _sector("ACTTRAB_C", 10)),
        D(per, ("SECTOR",), ("C_A_ECO",), ("1990",), _sector_1990),
        D(per, ("DIS_CON", "DIS_LIMI"), _DIS_ITEMS, _NEW, _dis),
        D(per, ("DISCAPACIDAD", "LIMITACION"), _DIS_ITEMS, _NEW, _dis_inegi),
        D(per, ("SIN_DISC_LIM",), (*_DIS_ITEMS, "DIS_MENTAL"), _NEW, _sin_disc_lim),
        D(per, ("LIM_ACTIVIDAD",), _DISCAP_ITEMS, ("2010",), _lim_actividad),
        D(per, _dhsersal_names(tuple(_DHSERSAL)), ("DHSERSAL1", "DHSERSAL2"), _NEW,
          _dhsersal(tuple(_DHSERSAL))),
        D(per, _dhsersal_names(_DHSERSAL_NO_BIENESTAR), ("DHSERSAL1", "DHSERSAL2"), _OLD,
          _dhsersal(_DHSERSAL_NO_BIENESTAR)),
        *(D(per, _dhsersal_names(_dhsersal_codes(p)), tuple(_DHSERSAL_ITEMS[p]), (p,),
            _dhsersal_items(p)) for p in ("2000", "2005")),
        D(per, _dummy_names(per, _ESC, "MED_TRASLADO_ESC"), _ESC, _NEW,
          _dummies(per, _ESC, "MED_TRASLADO_ESC")),
        D(per, _dummy_names(per, _ESC, "MED_TRASLADO_ESC", esc15), _ESC, ("2015",),
          _dummies(per, _ESC, "MED_TRASLADO_ESC", esc15)),
        D(per, _dummy_names(per, _TRAB, "MED_TRASLADO_TRAB"), _TRAB, _NEW,
          _dummies(per, _TRAB, "MED_TRASLADO_TRAB")),
        D(per, _dummy_names(per, _TRAB, "MED_TRASLADO_TRAB", trab15), _TRAB, ("2015",),
          _dummies(per, _TRAB, "MED_TRASLADO_TRAB", trab15)),
        # 7a: the EIC 2025 estimates' groups of commute modes, its affiliated or recognising
        # an access to the public health services, the place of school and of work by
        # INEGI's rule, the residence five years earlier by municipality
        *(D(per, tuple(f"{prefix}_{name}" for name in _TRASLADO_T), items, _NEW,
            _traslado_t(items, prefix))
          for items, prefix in ((_ESC, "MED_TRASLADO_ESC"), (_TRAB, "MED_TRASLADO_TRAB"))),
        D(per, ("DHSERSAL_AFIL_ACCESO",), ("DHSERSAL1", "DHSERSAL2", "DHSERSAL_ACCESO"),
          ("2025",), _afil_acceso),
        # (7b: the EIC 2015's and Censo 2010's places too, and the place of school and of
        # work by municipality; Censo 2010 asked no place of school; 7c: CGPV 2000's
        # residence in 1995 and place of work, Censo 2010's layout without its split)
        *(D(per, (f"{item}_INEGI",), (item, "ENT"), _SINCE_2015,
            _ent_pais_inegi(item, f"{item}_INEGI")) for item in ("ENT_PAIS_ASI", "ENT_PAIS_TRAB")),
        D(per, ("ENT_PAIS_TRAB_INEGI",), ("LTRABPAI_C", "ENT"), ("2000", "2010"),
          _ent_pais_inegi("LTRABPAI_C", "ENT_PAIS_TRAB_INEGI")),
        *(D(per, (name,), (item, mun, "ENT", "MUN"), periods, _lugar(item, mun, name))
          for name, item, mun, periods in (
              ("LUGAR_RES_5A", "ENT_PAIS_RES_5A", "MUN_RES_5A", ("2000", *_SINCE_2015)),
              ("LUGAR_ASI", "ENT_PAIS_ASI", "MUN_ASI", _SINCE_2015),
              ("LUGAR_TRAB", "ENT_PAIS_TRAB", "MUN_TRAB", _SINCE_2015))),
        D(per, ("LUGAR_RES_5A",), ("RES05EDO_C", "RES05PAI_C", "MUN05OTR_C", "ENT", "MUN"),
          ("2010",), _lugar("RES05EDO_C", "MUN05OTR_C", "LUGAR_RES_5A", abroad="RES05PAI_C")),
        D(per, ("LUGAR_TRAB",), ("LTRABPAI_C", "LTRABMUN_C", "ENT", "MUN"), ("2000", "2010"),
          _lugar("LTRABPAI_C", "LTRABMUN_C", "LUGAR_TRAB")),
        D(per, ("CONACT_CAT",), ("CONACT",), (*_OLDEST, *_SINCE_2000),
          _cat(per, "CONACT", "CONACT_CAT")),
        D(per, ("SITUA_CONYUGAL_CAT",), ("SITUA_CONYUGAL",), (*_OLDEST, *_SINCE_2000),
          _cat(per, "SITUA_CONYUGAL", "SITUA_CONYUGAL_CAT")),
        D(per, _NAC, ("ENT_PAIS_NAC", "ENT"), (*_OLDEST, "2000", *_SINCE_2015),
          _ent_pais_cat("ENT_PAIS_NAC", _NAC[0], inegi=_NAC[1])),
        D(per, _NAC, ("LNACEDO_C", "LNACPAIS_C", "ENT"), ("2010",),
          _ent_pais_cat("LNACEDO_C", _NAC[0], abroad="LNACPAIS_C", inegi=_NAC[1])),
        D(per, ("ENT_PAIS_RES_CAT",), ("ENT_PAIS_RES_5A", "ENT"),
          (*_OLDEST, "2000", "2005", *_SINCE_2015),
          _ent_pais_cat("ENT_PAIS_RES_5A", "ENT_PAIS_RES_CAT")),
        D(per, ("ENT_PAIS_RES_CAT",), ("RES05EDO_C", "RES05PAI_C", "ENT"), ("2010",),
          _ent_pais_cat("RES05EDO_C", "ENT_PAIS_RES_CAT", abroad="RES05PAI_C")),
        D(per, ("IDENT_MADRE_CAT",), ("IDENT_MADRE",), _SINCE_2015,
          _cat(per, "IDENT_MADRE", "IDENT_MADRE_CAT")),
        D(per, ("IDENT_PADRE_CAT",), ("IDENT_PADRE",), _SINCE_2015,
          _cat(per, "IDENT_PADRE", "IDENT_PADRE_CAT")),
        D(per, ("IDENT_PAREJA_CAT",), ("IDENT_PAREJA",), _SINCE_2015,
          _cat(per, "IDENT_PAREJA", "IDENT_PAREJA_CAT")),
        D(per, ("IDENT_PAREJA_CAT",), ("IDCONYUGE", "IDCONYUGEC"), ("2010",), _pareja_2010),
        D(per, ("MADRE_EN_VIVIENDA",), ("IDENT_MADRE",), _SINCE_2015,
          _en_vivienda("MADRE_EN_VIVIENDA", "IDENT_MADRE")),
        D(per, ("MADRE_EN_VIVIENDA",), ("IDMADRE", "IDMADREC"), ("2010",),
          _en_vivienda("MADRE_EN_VIVIENDA", "IDMADRE", "IDMADREC")),
        D(per, ("PADRE_EN_VIVIENDA",), ("IDENT_PADRE",), _SINCE_2015,
          _en_vivienda("PADRE_EN_VIVIENDA", "IDENT_PADRE")),
        D(per, ("PADRE_EN_VIVIENDA",), ("IDPADRE", "IDPADREC"), ("2010",),
          _en_vivienda("PADRE_EN_VIVIENDA", "IDPADRE", "IDPADREC")),
        D(per, ("IDENT_HIJO_CAT",), ("IDENT_HIJO",), ("2020",),
          _cat(per, "IDENT_HIJO", "IDENT_HIJO_CAT")),
        D(per, ("RELIGION_CAT",), ("RELIGION",), ("2020",),
          _cat(per, "RELIGION", "RELIGION_CAT")),
        D(per, ("RELIGION_CAT",), ("OTRAREL_C",), ("2010",), _religion_2010),
        D(per, ("RELIGION_INEGI",), ("OTRAREL_C",), ("2010",), _religion_inegi_2010),
        D(per, ("RELIGION_CAT",), ("OTRAREL_C",), ("2000",), _religion_2000),
        D(per, ("RELIGION_CAT",), ("RELIGION",), ("1990",), _religion_1990),
        *(D(per, ("HOGJEF_SEXO",), ("PARENTESCO", "SEXO"), periods, _hogjef_sexo(heads),
            household=True) for heads, periods in _periods_by(_HEAD_CODES).items()),
        *(D(per, ("HOG_IND",), ("PARENTESCO", "HLENGUA"), periods, _hog_ind(members),
            household=True) for members, periods in _periods_by(_IND_CODES).items()),
        # 6x: the household's HOG_IND on its record — the dwelling (2000's dwelling rows are
        # households; one household per dwelling from 2010) or, in the Conteo 2005, the
        # household (its dwelling rows are dwellings) — over the person file's members
        *(D(table, ("HOG_IND",), ("PARENTESCO", "HLENGUA"), editions, _hog_ind(members),
            household=True, members=True)
          for members, periods in _periods_by(_IND_CODES).items()
          for table, editions in _household_records(periods).items()),
        # 7a: the Afro-descendant households, on the persons and on the household records
        *(D(per, ("HOG_AFRO",), ("PARENTESCO", "AFRODES"), periods, _hog_afro(members),
            household=True) for members, periods in _periods_by(_AFRO_CODES).items()),
        *(D(table, ("HOG_AFRO",), ("PARENTESCO", "AFRODES"), editions, _hog_afro(members),
            household=True, members=True)
          for members, periods in _periods_by(_AFRO_CODES).items()
          for table, editions in _household_records(periods).items()),
        # 8f: the kinship line of INEGI's tabulados, by each edition's relationship catalog
        *(D(per, ("LINEA_PARENTESCO",), (item,), (p,), _linea(item, _LINEAS[p]))
          for p, item in _LINEA_ITEMS.items()),
        D(per, ("LINEA_PARENTESCO",), ("PARENT", "OTROPARE_C"), ("2010",), _linea_2010),
        D(viv, ("CLAVIVP_CAT",), ("CLAVIVP",), ("1990", "2000", "2005", "2010", *_SINCE_2015),
          _cat(viv, "CLAVIVP", "CLAVIVP_CAT")),
        D(viv, ("JEFE_SEXO",), ("SEXO",), ("2000", "2005", "2010"), _jefe_sexo),  # the head's
        # 6v: the Conteo 2005's households, their dwelling's class and their own head's sex
        # (cpv._attach_dwellings, cpv._attach_heads), with the dwelling columns' labels
        D(hog, ("CLAVIVP_CAT",), ("CLAVIVP",), ("2005",), _cat(viv, "CLAVIVP", "CLAVIVP_CAT")),
        D(hog, ("JEFE_SEXO",), ("SEXO",), ("2005",), _jefe_sexo),
        D(viv, ("CUADORM_CAT",), ("CUADORM",), (*_OLDEST, *_EVERY),
          _cat(viv, "CUADORM", "CUADORM_CAT")),
        D(viv, ("TOTCUART_CAT",), ("TOTCUART",), (*_OLDEST, *_EVERY),
          _cat(viv, "TOTCUART", "TOTCUART_CAT")),
        D(viv, ("DRENAJE_CAT",), ("DRENAJE",), (*_OLDEST, *_EVERY),
          _cat(viv, "DRENAJE", "DRENAJE_CAT")),
        D(viv, ("INGTRHOG_CAT",), ("INGTRHOG",), _SINCE_2000, _ingtrhog_cat),
        # 7f: CGPV 2000's first household (its dwelling rows are households) and its rooms
        # without an exclusive kitchen nobody sleeps in (its ITER's), a number
        D(viv, ("PRIMER_HOGAR",), ("NUMHOG",), ("2000",), _primer_hogar),
        D(viv, ("TOTCUART_INEGI",), ("TOTCUART", "COCINA", "COCDOR"), ("2000",),
          _totcuart_inegi),
        # 6z: the occupants per room (one household per dwelling from 2010 on), the
        # household's class (the persons read their household's TIPOHOG, which the person
        # loader attaches from the dwelling file: cpv._attach_dwellings) and its income
        # from other sources than work
        D(viv, ("OCUP_CUARTO_CAT",), ("NUMPERS", "TOTCUART"), _ALL, _ocup_cuarto),
        D(viv, ("CLASE_HOG",), ("TIPOHOG",), _SINCE_2000, _clase_hog),
        D(per, ("CLASE_HOG",), ("TIPOHOG",), _SINCE_2000, _clase_hog),
        D(viv, ("INGR_OTROS",), tuple(_INGR_OTROS), _SINCE_2015, _ingr_otros),
        D(viv, _dummy_names(viv, _FIN, "FINANCIAMIENTO"), _FIN, _NEW,
          _dummies(viv, _FIN, "FINANCIAMIENTO")),
        D(viv, _dummy_names(viv, ("FINANCIAMIENTO",), "FINANCIAMIENTO", fin15),
          ("FINANCIAMIENTO",), ("2015",),
          _dummies(viv, ("FINANCIAMIENTO",), "FINANCIAMIENTO", fin15)),
    )


@functools.cache
def _derivations(table: str, period: str) -> tuple[_Derivation, ...]:
    if table not in TABLES:
        raise ValueError(f"CPV derived columns exist for {list(TABLES)}, not {table!r}")
    return tuple(d for d in _registry() if d.table == table and period in d.periods)


def cpv_derivations(table: str | None = None, period: str | int | None = None) -> pd.DataFrame:
    """The derived columns and the editions each one is verified for.

    One row per derived column and derivation: ``TABLE``, ``COLUMN``, ``SOURCES`` (the raw
    items it reads) and ``PERIODS`` (a column computed differently in some editions, such
    as the 2015 commute dummies, has one row per way). ``table``/``period`` filter the rows
    (``period``: the columns ``derived=True`` adds to that edition's frame, each once).
    """
    rows = [(d.table, col, ", ".join(d.sources), ", ".join(d.periods))
            for d in _registry() for col in d.columns
            if (table is None or d.table == table)
            and (period is None or str(period) in d.periods)]
    return pd.DataFrame(rows, columns=["TABLE", "COLUMN", "SOURCES", "PERIODS"])


@functools.cache
def derived_dtypes(table: str, period: str | int) -> dict[str, pd.api.extensions.ExtensionDtype]:
    """The dtype of each derived column of ``table`` in ``period``: categorical, but for
    the numbers (7f: CGPV 2000's ``TOTCUART_INEGI``, ``Int64``)."""
    out = {}
    own = _period_dtypes(table, str(period))
    for d in _derivations(table, str(period)):
        for col in d.columns:
            if col.startswith(("DHSERSAL_", "MED_TRASLADO_", "FINANCIAMIENTO_")):
                out[col] = _DUMMY
            else:
                out[col] = own.get(col) or _DTYPES.get(col) or _legacy_dtype(table, col)
    return out


def derived_schema(table: str, period: str | int) -> pa.DataFrameSchema:
    """Pandera schema of the derived columns: their dtype; no missing category (a number
    is missing where its source is not specified)."""
    return pa.DataFrameSchema(
        {col: pa.Column(dtype, nullable=not isinstance(dtype, pd.CategoricalDtype))
         for col, dtype in derived_dtypes(table, period).items()}, strict=False)


def _source(df: pd.DataFrame, name: str) -> str:
    for alias in _ALIASES.get(name, (name,)):
        if alias in df.columns:
            return alias
    raise KeyError(name)


_HOUSEHOLD = "_HOGAR"      # the household's number, in a derivation's ``src`` (household=True)


def _household_keys(df: pd.DataFrame) -> list[pd.Series]:
    """Each record's household: the entity and ``ID_HOG`` in the editions with a household
    level (1995–2005), else the entity and ``ID_VIV`` (one household per dwelling; the
    entity makes Censo 2010's state-scoped serials unique). A frame without keys gets the
    1995–2005 composite keys (``cpv._composite_keys``)."""
    from mxcensus.cpv import _composite_keys

    keyed = _composite_keys(df, "personas")
    key = next((k for k in ("ID_HOG", "ID_VIV") if k in keyed.columns), None)
    if key is None:
        raise ValueError("CPV: HOGJEF_SEXO and HOG_IND need the household key "
                         "(ID_HOG or ID_VIV, or the parts they are derived from)")
    return [keyed[_source(keyed, "ENT")], keyed[key]]


def _household(df: pd.DataFrame) -> pd.Series:
    """Each record's household, numbered (:func:`_household_keys`)."""
    ent, key = _household_keys(df)
    return pd.DataFrame({"ent": ent, "key": key}).groupby(["ent", "key"], sort=False) \
        .ngroup().set_axis(df.index)


def _per_record(values: pd.Series, members: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
    """A household's value on each of its ``members`` (``values``, on their rows) → on each
    record of ``df`` (a dwelling or household frame): its household's, matched on the entity
    and the household key without their zero padding (the 2015 CSVs drop it, harmonized
    frames restore it). Missing for a record whose household has no member."""
    def households(frame: pd.DataFrame) -> pd.MultiIndex:
        return pd.MultiIndex.from_arrays([k.astype("string").str.lstrip("0")
                                          for k in _household_keys(frame)])

    by_household = pd.Series(values.array, index=households(members))
    by_household = by_household[~by_household.index.duplicated()]
    return pd.Series(by_household.reindex(households(df)).array, index=df.index)


def _member_sources(table: str, period: str | int) -> tuple[str, ...]:
    """The person items (2020 names) a ``table`` frame's household columns read from the
    household's members (``derive(members=)``; 6x); empty when it has none."""
    return tuple(dict.fromkeys(s for d in _derivations(table, str(period)) if d.members
                               for s in d.sources))


def _codes(raw: pd.Series, recode: Mapping[int, int] | None) -> pd.Series:
    """A raw code column as float codes (blank → NaN), recoded into the 2020 code space."""
    s = raw if pd.api.types.is_numeric_dtype(raw) else \
        pd.to_numeric(raw.astype("string").str.strip().replace("", pd.NA), errors="raise")
    s = s.astype(float)
    if recode:
        s = s.where(~s.isin(list(recode)), s.map(recode))
    return s


def derive(df: pd.DataFrame, table: str, period: str | int,
           members: pd.DataFrame | None = None) -> pd.DataFrame:
    """``df`` (a raw CPV ``table`` frame of edition ``period``) plus its derived columns.

    Reads the source items' raw codes (zero-padded or not), so call it before labelling;
    the derived columns are ``Categorical`` (0/1 for the dummies), or ``Int64`` numbers
    (:func:`derived_dtypes`). A source code with no derived category raises ``ValueError``
    (a code the recode table does not know); a number may be missing.

    A household's column on a dwelling or household frame (6x: ``HOG_IND``) is computed
    over ``members``, the raw person rows of the frame's households (the person items it
    reads and the household key or its parts; ``load_cpv_viviendas``/``load_cpv_hogares``
    read them from the person file), as on the persons; each record takes its household's
    value. A frame with such a column and no ``members``, or a record whose household has no
    member, raises.
    """
    period = str(period)
    derivations = _derivations(table, period)
    if not derivations:
        warnings.warn(f"CPV {table} {period}: no derived columns are verified for this "
                      f"edition (see cpv_derivations()).", stacklevel=2)
    recode = _RECODE.get(period, {})
    dtypes = derived_dtypes(table, period)
    clash = [c for d in derivations for c in d.columns if c in df.columns]
    if clash:
        raise ValueError(f"CPV {table} {period}: derived columns already present: {clash}")
    new: dict[str, pd.Series] = {}
    problems: dict[str, list] = {}
    orphans: dict[str, int] = {}
    caches: dict[bool, dict[str, pd.Series]] = {False: {}, True: {}}    # the frame, members
    for d in derivations:
        frame, cache = (members if d.members else df), caches[d.members]
        if frame is None:
            raise ValueError(f"CPV {table} {period}: {d.columns[0]} is computed over each "
                             f"household's members: pass members= (the person rows; "
                             f"load_cpv_{table}(derived=True) reads them)")
        try:
            cols = {s: _source(frame, s) for s in d.sources}
        except KeyError as exc:
            raise ValueError(f"CPV {table} {period}: {d.columns[0]} needs {exc.args[0]!r}, "
                             f"absent from the {'members' if d.members else 'frame'}") from None
        for s, col in cols.items():
            if s not in cache:
                cache[s] = _codes(frame[col], recode.get(s))
        src = pd.DataFrame({s: cache[s] for s in cols}, index=frame.index)
        if d.household:
            if _HOUSEHOLD not in cache:
                cache[_HOUSEHOLD] = _household(frame)
            src[_HOUSEHOLD] = cache[_HOUSEHOLD]
        for name, values in d.func(src).items():
            values = pd.Series(values, index=frame.index) if not isinstance(values, pd.Series) \
                else values.set_axis(frame.index)
            if values.isna().any() and isinstance(dtypes[name], pd.CategoricalDtype):
                bad = src.loc[values.isna().to_numpy()].drop_duplicates().head(12)
                problems[name] = bad.to_dict("records")
            if d.members:
                values = _per_record(values, frame, df)
                if name not in problems and values.isna().any():
                    orphans[name] = int(values.isna().sum())
            new[name] = values
    if problems:
        raise ValueError(f"CPV {table} {period}: source codes without a derived category "
                         f"(add them to cpv_derived._RECODE): {problems}")
    if orphans:
        raise ValueError(f"CPV {table} {period}: records without members in the person rows "
                         f"(their household's columns): {orphans}")
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# --- constraints per edition ---------------------------------------------------------------

def _period_gid(table: str, period: str) -> str:
    from mxcensus._resources import cpv_schema_map

    for gid, group in cpv_schema_map()[table]["groups"].items():
        if period in [str(p) for p in group["periods"]]:
            return gid
    raise ValueError(f"no CPV {table} schema group for {period}")


@functools.cache
def _relabels(table: str) -> dict[str, dict[str, str]]:
    """Legacy label → the Censo 2020 FD label, for the constrained items whose legacy
    dictionary words them differently (matched through their shared codes)."""
    from mxcensus.cpv import variables_cpv_labels

    fd = variables_cpv_labels(table, _period_gid(table, "2020"))
    out: dict[str, dict[str, str]] = {}
    for var in {v for c in _base_constraints(table).values() for v in (c or {})}:
        meta = fd.get(var)
        if not meta or var not in _variables(table):
            continue
        fd_labels = {int(k): v for k, v in {**(meta.get("Categorías") or {}),
                                            **(meta.get("Especiales") or {})}.items()
                     if str(k).lstrip("-").isdigit()}
        pairs = {old: fd_labels[code] for code, old in _legacy_map(table, var).items()
                 if code in fd_labels and fd_labels[code] != old}
        if pairs:
            out[var] = pairs
    return out


def _base_constraints(table: str) -> dict:
    if table not in TABLES:
        raise ValueError(f"CPV constraints exist for {list(TABLES)}, not {table!r}")
    return constraints_personas() if table == "personas" else constraints_viviendas()


# Variables the CPV cells read under another name: the neutral DHSERSAL names, and INEGI's
# levels for the education indicators (its primaria completa leaves out the técnica studies
# after primaria, which the legacy EDUC counts as «Primaria_com»; STEP_6k.md).
_CELL_VARS = {**DHSERSAL_RENAMES, "EDUC": "EDUC_INEGI"}

# Indicators whose CPV cells replace the legacy ones (INEGI's disability definitions) or that
# the legacy sets lack: the population by its household head's sex (6t; the 2000–2020 ITER,
# the EIC 2025 estimates) and the population in households (6v, ``POBHOG``: every person of
# the sample, as ``POBTOT``; the samples cover the residents of private dwellings, which the
# ITER's ``POBTOT`` exceeds by the population of collective dwellings and without a dwelling,
# and in 2000 by the population counted without characteristics; see cpv_constraints).
_PHOG_IND = {"HOG_IND": ["Sí"]}      # each edition's own definition (_IND_CODES; 6w)
# The limitation and the disability by activity (6y): INEGI counts a limitation in an
# activity (some difficulty) only for the persons with a limitation, i.e. without a
# disability in another activity (``LIMITACION``), and a disability (much difficulty, cannot)
# with the persons whose degree is unknown (the edition's label: _pcdisc). The EIC 2025
# estimates match to their rounding everywhere; the Censo 2020 ITER, in the 184
# municipalities its sample enumerated completely, matches the limitation in 168–181 (the
# legacy cells, some difficulty whatever the rest: 0–4) and the disability in 179–183
# (legacy 175–182).
_LIMITATIONS = {"PCLIM_VIS": "DIS_VER", "PCLIM_OAUD": "DIS_OIR", "PCLIM_CSB": "DIS_CAMINAR",
                "PCLIM_RE_CO": "DIS_RECORDAR", "PCLIM_MOT2": "DIS_BANARSE",
                "PCLIM_HACO": "DIS_HABLAR"}
_DISABILITIES = {"PCDISC_VIS": "DIS_VER", "PCDISC_AUD": "DIS_OIR", "PCDISC_MOT": "DIS_CAMINAR",
                 "PCDISC_MEN": "DIS_RECORDAR", "PCDISC_MOT2": "DIS_BANARSE",
                 "PCDISC_LENG": "DIS_HABLAR"}


def _pcdisc(unknown: str) -> dict:
    """INEGI's disability by activity, with the edition's label for an unknown degree."""
    return {ind: {item: ["Lo hace con mucha dificultad", "No puede hacerlo", unknown]}
            for ind, item in _DISABILITIES.items()}


_CELLS = {"personas": {"POBHOG": {},
                       "PCON_DISC": {"DISCAPACIDAD": ["Sí"]},
                       "PCON_LIMI": {"LIMITACION": ["Sí"]},
                       "PSIND_LIM": {"SIN_DISC_LIM": ["Sí"]},
                       **{ind: {item: ["Lo hace con poca dificultad"], "LIMITACION": ["Sí"]}
                          for ind, item in _LIMITATIONS.items()},
                       "PHOGJEF_F": {"HOGJEF_SEXO": ["Mujer"]},
                       "PHOGJEF_M": {"HOGJEF_SEXO": ["Hombre"]},
                       "PHOG_IND": _PHOG_IND},
          # 6x: the indigenous households (the EIC 2025 estimates' HOG_IND), on the
          # household's HOG_IND of each dwelling
          "viviendas": {"HOG_IND": _PHOG_IND}}

_AGES_5PLUS = ["5", "6-7", "8-11", "12-14", "15-17", "18-24", "25-49", "50-59", "60-64",
               "65-130"]
_AGES_15PLUS = _AGES_5PLUS[4:]
_AGES_12PLUS, _AGES_18PLUS = _AGES_5PLUS[3:], _AGES_5PLUS[5:]
_AGES_6_14, _AGES_15_24 = ["6-7", "8-11", "12-14"], ["15-17", "18-24"]
_AGES_0_14 = ["0-2", "3-4", "5", *_AGES_6_14]
_VIVIENDA = {"CLAVIVP_CAT": ["Vivienda"]}
# The employed by sector (CGPV 1990 and 2000's ITER; 6o).
_EMPLOYED_CELLS = {"EDAD_CAT": _AGES_12PLUS, "CONACT_CAT": ["Trabaja"]}
_SECTOR_CELLS = {ind: {**_EMPLOYED_CELLS, "SECTOR": [sector]} for ind, sector in (
    ("POCUSECP", "Primario"), ("POCUSECS", "Secundario"), ("POCUSECT", "Terciario"))}
# INEGI's posprimaria (1990/2000): any level above primaria, técnica after primaria included.
_POSPRIMARIA = ["Técnica_primaria", "Secundaria_incom", "Secundaria_com", "Posbásica"]
_SIN_POSPRIMARIA = ["Sin Educación", "Primaria_incom", "Primaria_com"]


def _by_sex(cells: dict, names: tuple[str, str, str], sex: str = "SEXO") -> dict:
    """An indicator and its men's and women's (``names`` = total, men, women)."""
    total, men, women = names
    return {total: cells, men: {**cells, sex: ["Hombre"]}, women: {**cells, sex: ["Mujer"]}}


# 7g: the born and the residents five years earlier in another entity leave out the
# unspecified entity (INEGI's rule: ENT_PAIS_NAC_INEGI, LUGAR_RES_5A; the legacy cells count
# it in OtraEnt), as the EIC 2025 estimates (6y, 7a) and the Censo 2010 and 2020 ITER: exact
# in the 233/130 municipalities their samples enumerated completely where every age and sex
# count is the ITER's (the legacy cells: 231/123 and 231/120). The Conteo 2005, without
# LUGAR_RES_5A, keeps the legacy cells (its residence item has no unspecified entity).
_CELLS["personas"].update({
    **_by_sex({"ENT_PAIS_NAC_INEGI": ["OtraEnt"]}, ("PNACOE", "PNACOE_M", "PNACOE_F")),
    **_by_sex({"EDAD_CAT": _AGES_5PLUS, "LUGAR_RES_5A": ["Otra entidad"]},
              ("PRESOE15", "PRESOE15_M", "PRESOE15_F")),
})

# Indicators an edition publishes under its own definition, on its own items: Censo 2010's
# limitation in activity (its PCLIM_VIS/PCLIM_MOT2 share 2020's names, not their concept)
# and its protestant, evangelical and other biblical religions (7g: by its own
# classification, RELIGION_INEGI — 2020's protestant/evangelical group also holds the
# neo-Israelite movements its ITER counts in POTRAS_REL). CGPV
# 1990 and the Conteo 1995: the legacy cells on their own items (literacy, indigenous
# language, sex, floor, electricity, water), with their dictionaries' labels; the Conteo
# 1995 has no dwelling class, so its dwelling cells take every (private) dwelling. CGPV
# 2000, the Conteo 2005 and Censo 2010 (6n): the legacy cells their items answer under
# other names or labels, by their ITER's definitions (2000's sanitary service is the
# exclusive one; «sin ningún bien» lists 2000's ten goods, 2005's four, 2010's nine).
_SIN_BIENES_2000 = ("RADIO", "TELEVI", "VIDEO", "LICUAD", "REFRIG", "LAVADORA", "TELEFONO",
                    "BOILER", "AUTOPROP", "COMPU")
_SIN_BIENES_2010 = ("RADIO", "TELEVI", "REFRIG", "LAVADORA", "AUTOPROP", "COMPU", "TELEFONO",
                    "CELULAR", "INTERNET")
_AGUA_DV_2000 = ["Agua entubada dentro de la vivienda",
                 "Agua entubada fuera de la vivienda, pero dentro del terreno"]
_AGUA_FV_2000 = ["Agua entubada de llave pública (o hidrante)",
                 "Agua entubada que acarrean de otra vivienda", "Agua de pipa",
                 "Agua de un pozo, río lago, arroyo u otra"]
_AGUA_FV_2010 = [*_AGUA_FV_2000[:3], "Agua de un pozo, río, lago, arroyo u otra"]
_AGUA_DV_2005 = ["Disponen de agua de la red pública dentro de la vivienda",
                 "Disponen de agua de la red pública fuera de la vivienda pero dentro del "
                 "terreno"]
_AGUA_FV_2005 = ["Se abastecen de una llave pública o hidrante", "Se abastecen de otra vivienda",
                 "Se abastecen de agua de pipa", "Se abastecen de agua de pozo",
                 "Se abastecen de agua de río, arroyo, lago u otro"]
_AGUA_DV_2025 = ["dentro de la vivienda?", "solo en el patio o terreno?"]
# 6z: the EIC 2025's other dwelling characteristics (their percentages' base: VIVPARHAB_C;
# the deeds' the owned dwellings, VPH_PROPIA, which counts those being paid for) and its
# household items (base: TOTHOG; the minors' food items: HOG_MEN_ALIM, «hogares con
# menores de edad», which no cell reproduces: the questionnaire's filter of minors is not
# in the microdata). Each = the estimates to their rounding at every published geography.
_TECHO_LAMINA = ["Lámina metálica", "Lámina de asbesto", "Lámina de fibrocemento"]
_DWELLINGS_2025 = {ind: {**_VIVIENDA, **cells} for ind, cells in {
    "VPH_2_5OCU": {"OCUP_CUARTO_CAT": ["Más de 2.5"]},
    "VPH_PDESH": {"PAREDES": ["Material de desecho", "Lámina de cartón"]},
    "VPH_PASB": {"PAREDES": ["Lámina de asbesto o metálica", "Carrizo, bambú o palma",
                             "Embarro o bajareque"]},
    "VPH_PMAD": {"PAREDES": ["Madera", "Adobe"]},
    "VPH_PTAB": {"PAREDES": ["Tabique, ladrillo, block, piedra, cantera, cemento o concreto"]},
    "VPH_TDESH": {"TECHOS": ["Material de desecho", "Lámina de cartón"]},
    "VPH_TASB": {"TECHOS": _TECHO_LAMINA},
    "VPH_TLOSA": {"TECHOS": ["Losa de concreto o viguetas con bovedilla"]},
    "VPH_TOTRO": {"TECHOS": ["Palma o paja", "Madera o tejamanil", "Terrado con viguería",
                             "Teja"]},
    "VPH_PISOCEM": {"PISOS": ["Cemento o firme"]},
    "VPH_PISOMAD": {"PISOS": ["Madera, mosaico u otro recubrimiento"]},
    "VPH_CINT": {"LUG_COC": ["al interior de la vivienda?"]},
    "VPH_CSEP": {"LUG_COC": ["en un cuarto separado de la vivienda?"]},
    "VPH_COTRO": {"LUG_COC": ["en un pasillo o corredor fuera de la vivienda?",
                              "en un tejabán o techito?", "al aire libre?",
                              "¿No tiene un espacio para cocinar?"]},
    "VPH_COMGAS": {"COMBUSTIBLE": ["gas?"]},
    "VPH_COMELE": {"COMBUSTIBLE": ["electricidad?"]},
    "VPH_BOMBA": {"BOMBA_AGUA": ["Sí"]},
    "VPH_REGA": {"REGADERA": ["Sí"]},
    "VPH_BOILER": {"BOILER": ["Sí"]},
    "VPH_SOLAR": {"CALENTADOR_SOLAR": ["Sí"]},
    "VPH_AIRE": {"AIRE_ACON": ["Sí"]},
    "VPH_PANEL": {"PANEL_SOLAR": ["Sí"]},
    "VPH_ORGANI": {"SEPARACION1": ["Sí"]},
    "VPH_ANIMAL": {"SEPARACION2": ["Sí"]},
    "VPH_PLANTA": {"SEPARACION3": ["Sí"]},
    "VPH_VENDER": {"SEPARACION4": ["Sí"]},
    "VPH_CAMBASU": {"DESTINO_BAS": ["se la dan a un camión o carrito recolector de basura?"]},
    "VPH_CNTBASU": {"DESTINO_BAS": ["la dejan en un contenedor o depósito?"]},
    "VPH_ELIMBAS": {"DESTINO_BAS": ["la queman?", "la entierran?",
                                    "la llevan al basurero público?",
                                    "la tiran en otro lugar? (Calle, baldío, barranca, río)"]},
    "VPH_TVP": {"SERV_TV_PAGA": ["Sí"]},
    "VPH_PROPIA": {"TENENCIA": ["vive la persona que es dueña o propietaria?",
                                "vive la persona que es dueña pero la están pagando?"]},
    "VPH_ALQUI": {"TENENCIA": ["se paga renta?"]},
    "VPH_PREST": {"TENENCIA": ["¿Es de un familiar o les prestan la vivienda?"]},
    "VPH_OTRASIT": {"TENENCIA": ["¿Está intestada o en litigio?",
                                 "¿La ocupan en otra situación?"]},
    "VPH_PROPRESI": {"ESCRITURAS": ["a nombre de la persona dueña o propietaria?"]},
    "VPH_PERNORES": {"ESCRITURAS": ["a nombre de otra persona?"]},
    "VPH_NOESCRI": {"ESCRITURAS": ["¿No tiene escrituras?"]},
    "VPH_ESCRIDES": {"ESCRITURAS": ["No sabe"]},
}.items()}
_HOUSEHOLDS_2025 = {
    "HOG_FAM": {"CLASE_HOG": ["Familiar"]},
    "HOG_NFAM": {"CLASE_HOG": ["No familiar"]},
    "HOG_PERC": {"INGR_OTROS": ["Sí"]},
    "HOG_NPERC": {"INGR_OTROS": ["No"]},
    "HOG_GOB": {"INGR_AYUGOB": ["Sí"]},
    "HOG_JUB": {"INGR_JUBPEN": ["Sí"]},
    "HOG_OVIV": {"INGR_PERDENTPAIS": ["Sí"]},
    "HOG_OPAIS": {"INGR_PEROTROPAIS": ["Sí"]},
    # ALIMENTACION: «se quedaron sin comida?» (yes = no access to food)
    "HOG_ALIM_N": {"ALIMENTACION": ["Sí"]},
    "HOG_ALIM": {"ALIMENTACION": ["No"]},
    **{ind: {item: ["Sí"]} for ind, item in (
        ("ALIM_ADL1", "ALIM_ADL1"), ("ALIM_ADL2", "ALIM_ADL2"), ("ALIM_ADL3", "ALIM_ADL3"),
        ("ING_ADL1", "ING_ALIM_ADL1"), ("ING_ADL2", "ING_ALIM_ADL2"),
        ("ALIM_MEN1", "ALIM_MEN1"), ("ALIM_MEN2", "ALIM_MEN2"), ("ALIM_MEN3", "ALIM_MEN3"),
        ("ING_MEN1", "ING_ALIM_MEN1"), ("ING_MEN2", "ING_ALIM_MEN2"),
        ("ING_MEN3", "ING_ALIM_MEN3"),
        ("DESP_INSEG", "DESP_INSEGURIDAD"), ("DESP_CATAS", "DESP_CATASTROFES"))},
}
# 7a: the EIC 2025's person percentages (the counts behind them: cpv_aggregates.
# _PERCENT_BASES), each cell within its indicator's universe (the ages, the students, the
# employed). The five-year age groups by sex; birthplace abroad by nationality; residence
# five years earlier; self-identification as indigenous; disability by sex and by age;
# attendance; education levels; position at work; health affiliation, access and use; the
# students' and the employed's place and time of commute, the students' modes (the
# employed's are not: their base, who commute, is not published); marital status by sex.
# Left out: PCN_HF (a share of children, not persons), PCN_P3NHLI_CLI (its base, the 3+
# who do not speak an indigenous language, leaves out the unspecified, which nothing
# published gives) and the employed's modes.
_AGES_3PLUS = ["3-4", *_AGES_5PLUS]
_QUIN = [*(f"{a}-{a + 4}" for a in range(0, 75, 5)), "75-130"]


def _quin_name(group: str) -> str:
    """«0-4» → ``P_0A4``, «75-130» → ``P_75YMAS`` (the estimates' age-group names)."""
    lo, hi = group.split("-")
    return f"P_{lo}YMAS" if hi == "130" else f"P_{lo}A{hi}"


_STUDENTS = {"EDAD_CAT": _AGES_3PLUS, "ASISTEN": ["Sí"]}
_TIEMPOS = {"15MIN": ["Hasta 15 minutos"], "30MIN": ["16 a 30 minutos"],
            "1HOR": ["31 minutos a 1 hora"]}
_SERSALUD_2025 = {"IMSS": ["Seguro Social (IMSS)"], "ISTE": ["ISSSTE", "ISSSTE estatal"],
                  "PDOM": ["PEMEX, la Defensa o la Marina"],
                  "IMSSB": ["IMSS-BIENESTAR (IMSS-PROSPERA)"],
                  "IPUB": ["Centro de salud, hospital o instituto público de salud (federal o "
                           "estatal. Incluye INSABI y Seguro Popular)"],
                  "IPRIV": ["Consultorio, clínica u hospital privado"],
                  "CFARM": ["Consultorio de farmacia"], "OTRAI": ["Otro lugar"]}
_MODES_ESC = {"CAM": "Caminando", "BICI": "Bicicleta", "MET": "METRO_T", "TROL": "BUS_T",
              "TESC": "Transporte escolar", "TAXI": "TAXI_T", "MOTO": "Motocicleta o motoneta",
              "AUTO": "Automóvil o camioneta", "OMED": "Otro"}
_PERSONS_2025 = {
    **{ind: cells for group in _QUIN
       for ind, cells in _by_sex({"EDAD_QUIN": [group]},
                                 (_quin_name(group), f"{_quin_name(group)}_M",
                                  f"{_quin_name(group)}_F")).items()},
    "PNACOP_NAC": {"ENT_PAIS_NAC_CAT": ["OtroPais"], "NACIONALIDAD": ["Sí"]},
    "PNACOP_NONAC": {"ENT_PAIS_NAC_CAT": ["OtroPais"], "NACIONALIDAD": ["No"]},
    **{ind: {"EDAD_CAT": _AGES_5PLUS, "LUGAR_RES_5A": places} for ind, places in (
        ("PRESM20", ["Mismo municipio"]), ("PRESOM20", ["Otro municipio"]),
        ("PRESE20", ["Mismo municipio", "Otro municipio", "Municipio no especificado"]),
        ("PRESOE20", ["Otra entidad"]), ("PRESEUA20", ["Estados Unidos"]),
        ("PRESOP20", ["Otro país"]))},
    **_by_sex({"PERTE_INDIGENA": ["Sí"]}, ("POB_IND", "POB_IND_M", "POB_IND_F")),
    "PCON_DISC_M": {"DISCAPACIDAD": ["Sí"], "SEXO": ["Hombre"]},
    "PCON_DISC_F": {"DISCAPACIDAD": ["Sí"], "SEXO": ["Mujer"]},
    **{ind: {"DISCAPACIDAD": ["Sí"], "EDAD_QUIN": _QUIN[lo:hi]} for ind, lo, hi in (
        ("PCON_DISC0A14", 0, 3), ("PCON_DISC15A29", 3, 6), ("PCON_DISC30A59", 6, 12),
        ("PCON_DISC60YM", 12, 16))},
    "P3YM_ASIS": _STUDENTS,
    **_by_sex({"EDAD_CAT": _AGES_6_14, "ASISTEN": ["No"]},
              ("P6A14_NOA", "P6A14_NOA_M", "P6A14_NOA_F")),
    **{ind: {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI_DET": levels} for ind, levels in (
        ("P15YM_EB", ["Primaria_incom", "Primaria_com", "Técnica_primaria",
                      "Secundaria_incom", "Secundaria_com"]),
        ("P15YM_EMS", ["Media_superior"]), ("P15YM_ES", ["Superior"]),
        ("P15YM_POS", ["Posgrado"]))},
    **{ind: {**_EMPLOYED_CELLS, "SITTRA": positions} for ind, positions in (
        ("POCUP_ASA", ["empleada(o) u obrera(o)?", "jornalera(o) o peón(a)?",
                       "ayudante con pago?"]),
        ("POCUP_EMP", ["patrón(a) o empleador(a)? (Tiene trabajadores por un sueldo)"]),
        ("POCUP_CPRO", ["trabajador(a) por cuenta propia? (No tiene trabajadores por un "
                        "sueldo)"]),
        ("POCUP_SPAG", ["trabajador(a) sin pago?"]))},
    "PcSSyRecAc": {"DHSERSAL_AFIL_ACCESO": [1]},
    "PAFIL_IPUB": {"DHSERSAL_SALUD_PUBLICA": [1]},
    "PUSU_SS": {"SERSALUD": [c for v in _SERSALUD_2025.values() for c in v]},
    **{f"PUSU_{ind}": {"SERSALUD": places} for ind, places in _SERSALUD_2025.items()},
    "PASIS_ENT": {**_STUDENTS, "ENT_PAIS_ASI_INEGI": ["EstaEnt"]},
    "PASIS_OENT": {**_STUDENTS, "ENT_PAIS_ASI_INEGI": ["OtraEnt", "OtroPais"]},
    **{f"PASIS_{ind}": {**_STUDENTS, "TIE_TRASLADO_ESCU": times} for ind, times in (
        *_TIEMPOS.items(), ("1HYM", ["Más de 1 hora y hasta 2 horas", "Más de 2 horas"]))},
    **{f"PASIS_{ind}": {**_STUDENTS, f"MED_TRASLADO_ESC_{mode}": [1]}
       for ind, mode in _MODES_ESC.items()},
    "POCUP_ENT": {**_EMPLOYED_CELLS, "ENT_PAIS_TRAB_INEGI": ["EstaEnt"]},
    "POCUP_OENT": {**_EMPLOYED_CELLS, "ENT_PAIS_TRAB_INEGI": ["OtraEnt", "OtroPais"]},
    **{f"POCUP_{ind}": {**_EMPLOYED_CELLS, "TIE_TRASLADO_TRAB": times} for ind, times in (
        *_TIEMPOS.items(), ("2HOR", ["Más de 1 hora y hasta 2 horas"]),
        ("2HYM", ["Más de 2 horas"]))},
    # «casada(o) o en unión libre» = the legacy «casado»; the totals of the single and the
    # separated are the legacy P12YM_SOLT/_SEPA
    **{ind: cells for status, name in (("soltero", "SOLT"), ("casado", "CUL"),
                                       ("separado", "SEPA"))
       for ind, cells in _by_sex({"EDAD_CAT": _AGES_12PLUS, "SITUA_CONYUGAL_CAT": [status]},
                                 (f"P12YM_{name}", f"P12YM_{name}_M",
                                  f"P12YM_{name}_F")).items()
       if ind not in ("P12YM_SOLT", "P12YM_SEPA")},
    "PHOG_AFRO": {"HOG_AFRO": ["Sí"]},
}
_EDITION_CELLS = {
    ("personas", "1990"): {
        # 7f: the population in private dwellings, the sample's universe (its POBHOG; the
        # ITER's POBTOT adds the collective dwellings')
        "OCUPVIVPAR": {},
        "P15YM_AN": {"EDAD_CAT": _AGES_15PLUS,
                     "ALFABETA": ["NO SABE LEER NI ESCRIBIR ALGUN RECADO"]},
        # 6o: its own indicators (literacy, attendance, posprimaria, sector)
        "P6_14SLEE": {"EDAD_CAT": _AGES_6_14, "ALFABETA": ["SABE LEER Y ESCRIBIR ALGUN RECADO"]},
        "P6_14NLEE": {"EDAD_CAT": _AGES_6_14,
                      "ALFABETA": ["NO SABE LEER NI ESCRIBIR ALGUN RECADO"]},
        "P15_ALFAB": {"EDAD_CAT": _AGES_15PLUS, "ALFABETA": ["SABE LEER Y ESCRIBIR ALGUN RECADO"]},
        "P5_ASIESC": {"EDAD_CAT": ["5"], "ASISTE": ["ASISTE A LA ESCUELA ACTUALMENTE"]},
        "P_5_NOAE": {"EDAD_CAT": ["5"], "ASISTE": ["NO ASISTE A LA ESCUELA ACTUALMENTE"]},
        "P6_14AESC": {"EDAD_CAT": _AGES_6_14, "ASISTE": ["ASISTE A LA ESCUELA ACTUALMENTE"]},
        "P6A14NOA": {"EDAD_CAT": _AGES_6_14, "ASISTE": ["NO ASISTE A LA ESCUELA ACTUALMENTE"]},
        "P15_POSPRI": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _POSPRIMARIA},
        **_SECTOR_CELLS,
        "P5_HLI_HE": {"EDAD_CAT": _AGES_5PLUS, "HAB_IND": ["SI"], "HAB_ESP": ["SI"]},
        "P5_HLI_NHE": {"EDAD_CAT": _AGES_5PLUS, "HAB_IND": ["SI"], "HAB_ESP": ["NO"]},
    },
    ("viviendas", "1990"): {
        "VIVPAR_HAB": {},                     # 7f: every dwelling (the extract holds 10%)
        "VPH_PISODT": {**_VIVIENDA, "PISOS": ["CEMENTO O FIRME",
                                              "MADERA, MOSAICO U OTROS RECUBRIMIENTOS"]},
        "VPH_C_ELEC": {**_VIVIENDA, "ELECTRI": ["DISPONE"]},
        "VPH_AGUADV": {**_VIVIENDA, "AGUA_ENTU": ["DENTRO DE LA VIVIENDA",
                                                  "FUERA DE VIVIENDA, PERO DENTRO DEL TERRENO"]},
        # 6o: waste material is «otros materiales» in 1990's lists; two rooms, the kitchen
        # one they do not sleep in
        "VP_PARDES": {**_VIVIENDA, "PAREDES": ["LAMINA DE CARTON", "OTROS MATERIALES"]},
        "VP_TECDES": {**_VIVIENDA, "TECHOS": ["LAMINA DE CARTON", "OTROS MATERIALES"]},
        "VP_2CUAR": {**_VIVIENDA, "TOTCUART_CAT": ["2"], "TAM_DUERME": ["NO"]},
        "VP_PROPIA": {**_VIVIENDA, "TENENCIA": ["PROPIA"]},
    },
    ("personas", "1995"): {
        "OCUPVIVPAR": {},       # 7f: FAC_POB adds up to it in every state but Chiapas
        "POBFEM": {"P3_5": ["Mujer"]},
        "POBMAS": {"P3_5": ["Hombre"]},
        "P15YM_AN": {"EDAD_CAT": _AGES_15PLUS, "P5_1": ["No"]},
        "P_6A14_AN": {"EDAD_CAT": _AGES_6_14},                                    # 6o
        "P6_14SLEE": {"EDAD_CAT": _AGES_6_14, "P5_1": ["Sí"]},
        "P6_14NLEE": {"EDAD_CAT": _AGES_6_14, "P5_1": ["No"]},
        "P15_ALFAB": {"EDAD_CAT": _AGES_15PLUS, "P5_1": ["Sí"]},
    },
    ("viviendas", "1995"): {
        "VIVPAR_HAB": {},                                                         # 7f
        "VPH_C_ELEC": {"P1_16": ["Sí"]},
        "VPH_AGUADV": {"P1_8": ["Dentro de la vivienda",
                                "Fuera de la vivienda, pero dentro del terreno"]},
        "VPH_DRENAJ": {"DRENAJE_CAT": ["Sí"]},
    },
    ("personas", "2000"): {
        "P5_HLI": {"EDAD_CAT": _AGES_5PLUS, "HLENGUA": ["Sí habla algún dialecto"]},
        "P5_HLI_NHE": {"EDAD_CAT": _AGES_5PLUS, "HLENGUA": ["Sí habla algún dialecto"],
                       "HESPANOL": ["No habla español"]},
        "P5_HLI_HE": {"EDAD_CAT": _AGES_5PLUS, "HLENGUA": ["Sí habla algún dialecto"],
                      "HESPANOL": ["Sí habla español"]},
        "P15A17A": {"EDAD_CAT": ["15-17"], "ASISTEN": ["Sí va a la escuela"]},
        "P15YM_AN": {"EDAD_CAT": _AGES_15PLUS, "ALFABET": ["No sabe leer y escribir"]},
        # 6o: its own indicators
        "P_0A4": {"EDAD_CAT": ["0-2", "3-4"]},
        "P_6A14_AN": {"EDAD_CAT": _AGES_6_14},
        "P_15A24": {"EDAD_CAT": _AGES_15_24},
        "P5_ASIESC": {"EDAD_CAT": ["5"], "ASISTEN": ["Sí va a la escuela"]},
        "P_5_NOAE": {"EDAD_CAT": ["5"], "ASISTEN": ["No va a la escuela"]},
        "P6_14AESC": {"EDAD_CAT": _AGES_6_14, "ASISTEN": ["Sí va a la escuela"]},
        "P6A14NOA": {"EDAD_CAT": _AGES_6_14, "ASISTEN": ["No va a la escuela"]},
        "P_15A24A": {"EDAD_CAT": _AGES_15_24, "ASISTEN": ["Sí va a la escuela"]},
        "P15_24NESC": {"EDAD_CAT": _AGES_15_24, "ASISTEN": ["No va a la escuela"]},
        "P6_14SLEE": {"EDAD_CAT": _AGES_6_14, "ALFABET": ["Sí sabe leer y escribir"]},
        "P6_14NLEE": {"EDAD_CAT": _AGES_6_14, "ALFABET": ["No sabe leer y escribir"]},
        "P15_ALFAB": {"EDAD_CAT": _AGES_15PLUS, "ALFABET": ["Sí sabe leer y escribir"]},
        "PSOLTER12_": {"EDAD_CAT": _AGES_12PLUS, "SITUA_CONYUGAL_CAT": ["soltero"]},
        # 7g: its own definitions of the pairs the crosswalk keeps apart (published as
        # PNACOENT, P5_RESO95, P5_CATOLIC): born or living in 1995 outside the entity *or
        # the country*, and the religions of the 5 and more (the persons of unspecified age
        # answer the item; INEGI leaves them out) — exact in the 51 municipalities its
        # sample enumerated completely where every age and sex count is the ITER's (the
        # legacy cells: 0, 0, 20; P5_NCATOLI/P5_SINRELI without the age: 42, 40)
        "PNACOE": {"ENT_PAIS_NAC_INEGI": ["OtraEnt", "OtroPais"]},
        "PRESOE15": {"EDAD_CAT": _AGES_5PLUS,
                     "LUGAR_RES_5A": ["Otra entidad", "Estados Unidos", "Otro país"]},
        "PCATOLICA": {"EDAD_CAT": _AGES_5PLUS, "RELIGION_CAT": ["Católica"]},
        "P5_NCATOLI": {"EDAD_CAT": _AGES_5PLUS,
                       "RELIGION_CAT": ["Protestante/cristiano evangélico", "Otros credos"]},
        "P5_SINRELI": {"EDAD_CAT": _AGES_5PLUS,
                       "RELIGION_CAT": ["Protestante/cristiano evangélico", "Otros credos",
                                        "Sin religión / Sin adscripción religiosa"]},
        "P15_POSPRI": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _POSPRIMARIA},
        "P15_SINSEC": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _SIN_POSPRIMARIA},
        "P15_CONSEC": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _POSPRIMARIA[:3]},
        "P15_CMEDSS": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": ["Posbásica"]},
        "P18_SMEDSU": {"EDAD_CAT": _AGES_18PLUS,
                       "EDUC_INEGI": [*_SIN_POSPRIMARIA, *_POSPRIMARIA[:3]]},
        # 6w: media superior and superior apart (its superior includes the posgrado)
        "P18_CMEDSU": {"EDAD_CAT": _AGES_18PLUS, "EDUC_INEGI_DET": ["Media_superior"]},
        "P18_CSUPER": {"EDAD_CAT": _AGES_18PLUS, "EDUC_INEGI_DET": ["Superior", "Posgrado"]},
        **_SECTOR_CELLS,
        "POCUNINGR": {**_EMPLOYED_CELLS, "INGTRMEN_CAT": ["No recibe ingresos"]},
        # 7c: the income in minimum wages (the municipality's area, February 2000)
        **{ind: {**_EMPLOYED_CELLS, "INGTRMEN_SM": groups} for ind, groups in (
            ("P_1SM", ["Menos de 1 s.m."]), ("P1_2SM", ["De 1 hasta 2 s.m."]),
            ("P2_5SM", ["Más de 2 y menos de 3 s.m.", "De 3 hasta 5 s.m."]),
            ("P6_10SM", ["Más de 5 hasta 10 s.m."]), ("P10_SM", ["Más de 10 s.m."]))},
        "P41_48HTR": {**_EMPLOYED_CELLS, "HORTRA_CAT": ["41-48"]},
        "P48_HTR": {**_EMPLOYED_CELLS, "HORTRA_CAT": ["49-56", "57-60", "61-80", "81YMAS"]},
    },
    ("viviendas", "2000"): {
        "VIVPAR_HAB": {},                     # 7f: the first households (_PER_DWELLING)
        "VPH_PISODT": {**_VIVIENDA, "PISOS": ["Cemento o firme",
                                              "Madera, mosaico u otros recubrimientos"]},
        "VPH_C_ELEC": {**_VIVIENDA, "ELECTRI": ["Sí tiene"]},
        "VPH_AGUADV": {**_VIVIENDA, "DISAGU": _AGUA_DV_2000},
        "VPH_EXCSA": {**_VIVIENDA, "SERSAN": ["Sí tiene"], "USOEXC": ["Sí es exclusivo"]},
        "VPH_C_SERV": {**_VIVIENDA, "ELECTRI": ["Sí tiene"], "DISAGU": _AGUA_DV_2000,
                       "DRENAJE_CAT": ["Sí"]},
        "VPH_NDEAED": {**_VIVIENDA, "ELECTRI": ["No tiene"], "DISAGU": _AGUA_FV_2000,
                       "DRENAJE_CAT": ["No"]},
        "VPH_SNBIEN": {**_VIVIENDA, **{item: ["No tienen en la vivienda"]
                                       for item in _SIN_BIENES_2000}},
        **{ind: {**_VIVIENDA, item: ["Sí tienen en la vivienda"]} for ind, item in (
            ("VPH_REFRI", "REFRIG"), ("VPH_LAVAD", "LAVADORA"), ("VPH_AUTOM", "AUTOPROP"),
            ("VPH_RADIO", "RADIO"), ("VPH_TV", "TELEVI"), ("VPH_TELEF", "TELEFONO"),
            ("VP_VIDEO", "VIDEO"), ("VP_BOILER", "BOILER"))},
        # 6o: its own indicators (two services «y» — not «only» —, tenure by TENVIV, the
        # kitchen counted among the rooms)
        "VP_PARDES": {**_VIVIENDA, "PAREDES": ["Material de deshecho", "Lámina de cartón"]},
        "VP_TECDES": {**_VIVIENDA, "TECHOS": ["Material de deshecho", "Lámina de cartón"]},
        "VP_2CUAR": {**_VIVIENDA, "TOTCUART_CAT": ["2"]},
        **{ind: {**_VIVIENDA, "COMBUST": [fuel]} for ind, fuel in (
            ("VP_COCGAS", "Gas"), ("VP_COCLEN", "Leña"), ("VP_COCCAR", "Carbón"),
            ("VP_COCPET", "Petróleo"))},
        "VP_DREAGU": {**_VIVIENDA, "DRENAJE_CAT": ["Sí"], "DISAGU": _AGUA_DV_2000},
        "VP_DREELE": {**_VIVIENDA, "DRENAJE_CAT": ["Sí"], "ELECTRI": ["Sí tiene"]},
        "VP_AGUELE": {**_VIVIENDA, "ELECTRI": ["Sí tiene"], "DISAGU": _AGUA_DV_2000},
        "VP_PROPIA": {**_VIVIENDA, "TENVIV": ["Sí"]},
        "VP_PPAGAD": {**_VIVIENDA, "TENPROP": ["Está totalmente pagada"]},
        "VP_PPAGAN": {**_VIVIENDA, "TENPROP": ["Está pagándose"]},
        "VP_RENTAD": {**_VIVIENDA, "TENPROP": ["Está rentada"]},
        "VP_CBIENE": {**_VIVIENDA, **{item: ["Sí tienen en la vivienda"]
                                      for item in _SIN_BIENES_2000}},
    },
    ("personas", "2005"): {
        # 7g: the residents in another entity in 2000 on the legacy cells (no LUGAR_RES_5A;
        # its residence item has no unspecified entity, so OtraEnt is INEGI's)
        **_by_sex({"EDAD_CAT": _AGES_5PLUS, "ENT_PAIS_RES_CAT": ["OtraEnt"]},
                  ("PRESOE15", "PRESOE15_M", "PRESOE15_F")),
        "P5_HLI": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"]},
        "P5_HLI_NHE": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"],
                       "HATAMESP": ["No habla español"]},
        "P5_HLI_HE": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"], "HATAMESP": ["Habla español"]},
        "P6A11_NOA": {"EDAD_CAT": ["6-7", "8-11"], "ASIS_ESC": ["No"]},
        "P12A14NOA": {"EDAD_CAT": ["12-14"], "ASIS_ESC": ["No"]},
        # 6o: its own indicators (ages, attendance, basic education, by sex)
        **_by_sex({"EDAD_CAT": ["0-2", "3-4"]}, ("P_0A4", "P_0A4_M", "P_0A4_F")),
        "P_0A14_MA": {"EDAD_CAT": ["0-2", "3-4", "5", *_AGES_6_14], "SEXO": ["Hombre"]},
        "P_0A14_FE": {"EDAD_CAT": ["0-2", "3-4", "5", *_AGES_6_14], "SEXO": ["Mujer"]},
        "P_5_AN": {"EDAD_CAT": ["5"]},
        **_by_sex({"EDAD_CAT": _AGES_6_14}, ("P_6A14_AN", "P_6A14_M", "P_6A14_F")),
        "P_15A24": {"EDAD_CAT": _AGES_15_24},
        **_by_sex({"EDAD_CAT": ["15-17", "18-24", "25-49", "50-59"]},
                  ("P_15A59", "P_15A59_M", "P_15A59_F")),
        "P_65YMAS_M": {"EDAD_CAT": ["65-130"], "SEXO": ["Hombre"]},
        "P_65YMAS_F": {"EDAD_CAT": ["65-130"], "SEXO": ["Mujer"]},
        **_by_sex({"EDAD_CAT": ["5"], "ASIS_ESC": ["No"]},
                  ("P_5_NOAE", "P_M_5_NOAE", "P_F_5_NOAE")),
        **_by_sex({"EDAD_CAT": _AGES_6_14, "ASIS_ESC": ["No"]},
                  ("P6A14NOA", "PM_6A14NOA", "PF_6A14NOA")),
        **_by_sex({"EDAD_CAT": _AGES_15_24, "ASIS_ESC": ["Si"]},
                  ("P_15A24A", "P_M_15A24A", "P_F_15A24A")),
        # basic education incomplete (primaria, técnica after primaria, secundaria 1–2),
        # complete (secundaria 3), posbásica
        **_by_sex({"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": ["Primaria_incom", "Primaria_com",
                                                            "Técnica_primaria",
                                                            "Secundaria_incom"]},
                  ("P15YM_EBIN", "PM15YMEBIN", "PF15YMEBIN")),
        **_by_sex({"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": ["Secundaria_com"]},
                  ("P15YM_EBC", "PM15YM_EBC", "PF15YM_EBC")),
        **_by_sex({"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": ["Posbásica"]},
                  ("P15YMAPB", "PM_15YMAPB", "PF_15YMAPB")),
        "P5YMAHLI_M": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"], "SEXO": ["Hombre"]},
        "P5YMAHLI_F": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"], "SEXO": ["Mujer"]},
        "PM5YMALINE": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"],
                       "HATAMESP": ["No habla español"], "SEXO": ["Hombre"]},
        "PF5YMALINE": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"],
                       "HATAMESP": ["No habla español"], "SEXO": ["Mujer"]},
        "PMYMALIES": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"],
                      "HATAMESP": ["Habla español"], "SEXO": ["Hombre"]},
        "PFYMALIES": {"EDAD_CAT": _AGES_5PLUS, "HABLENIN": ["Si"],
                      "HATAMESP": ["Habla español"], "SEXO": ["Mujer"]},
        # the Seguro Popular (2005/2010; not 2020's INSABI: crosswalk Comparable: false)
        "PDER_SEGP": {"DHSERSAL_SALUD_PUBLICA": [1]},
        # 6w: indigenous households by the head or the partner only (2005/2010; 2020's adds
        # parents and parents-in-law: crosswalk Comparable: false)
        "PHOG_IND": _PHOG_IND,
    },
    ("viviendas", "2005"): {
        "VPH_PISODT": {**_VIVIENDA, "MAT_PISO": ["Cemento o firme",
                                                 "Madera, mosaico u otro material"]},
        "VPH_PISOTI": {**_VIVIENDA, "MAT_PISO": ["Tierra"]},
        "VPH_C_ELEC": {**_VIVIENDA, "DIS_ELEC": ["Si"]},
        "VPH_AGUADV": {**_VIVIENDA, "DIS_AGUA": _AGUA_DV_2005},
        "VPH_AGUAFV": {**_VIVIENDA, "DIS_AGUA": _AGUA_FV_2005},
        "VPH_EXCSA": {**_VIVIENDA, "DIS_SANI": ["Si"]},
        "VPH_C_SERV": {**_VIVIENDA, "DIS_ELEC": ["Si"], "DIS_AGUA": _AGUA_DV_2005,
                       "DRENAJE_CAT": ["Sí"]},
        "VPH_NDEAED": {**_VIVIENDA, "DIS_ELEC": ["No"], "DIS_AGUA": _AGUA_FV_2005,
                       "DRENAJE_CAT": ["No"]},
        "VPH_SNBIEN": {**_VIVIENDA, "NODISBIE": ["No dispone de ninguno de los bienes captados."]},
        "VPH_REFRI": {**_VIVIENDA, "DIS_REFR": ["Si"]},
        "VPH_LAVAD": {**_VIVIENDA, "DIS_LAVA": ["Disponen de lavadora"]},
        "VPH_TV": {**_VIVIENDA, "DIS_TELE": ["Si"]},
        "VPH_PC": {**_VIVIENDA, "DIS_COMP": ["Disponen de computadora"]},
    },
    ("viviendas", "2010"): {
        "VPH_C_ELEC": {**_VIVIENDA, "ELECTRI": ["Sí"]},
        "VPH_S_ELEC": {**_VIVIENDA, "ELECTRI": ["No"]},
        "VPH_AGUADV": {**_VIVIENDA, "DISAGU": _AGUA_DV_2000},
        "VPH_AGUAFV": {**_VIVIENDA, "DISAGU": _AGUA_FV_2010},
        "VPH_EXCSA": {**_VIVIENDA, "SERSAN": ["Sí"]},
        "VPH_C_SERV": {**_VIVIENDA, "ELECTRI": ["Sí"], "DISAGU": _AGUA_DV_2000,
                       "DRENAJE_CAT": ["Sí"]},
        "VPH_SNBIEN": {**_VIVIENDA, **{item: ["No"] for item in _SIN_BIENES_2010}},
        "VPH_REFRI": {**_VIVIENDA, "REFRIG": ["Sí"]},
        "VPH_TV": {**_VIVIENDA, "TELEVI": ["Sí"]},
        "VPH_PC": {**_VIVIENDA, "COMPU": ["Sí"]},
    },
    ("personas", "2010"): {
        "PDER_SEGP": {"DHSERSAL_SALUD_PUBLICA": [1]},                     # 6o: Seguro Popular
        "PHOG_IND": _PHOG_IND,                                  # 6w: head or partner only
        # 7g: its religion groups by its own classification (the neo-Israelites among the
        # other credos; RELIGION_CAT keeps 2020's grouping)
        "PNCATOLICA": {"RELIGION_INEGI": ["Protestante/cristiano evangélico"]},
        "POTRAS_REL": {"RELIGION_INEGI": ["Otros credos"]},
        "PCON_LIM": {"LIM_ACTIVIDAD": ["Sí"]},
        "PSIN_LIM": {"LIM_ACTIVIDAD": ["No"]},
        "PCLIM_MOT": {"DISCAP1": ["Caminar, moverse, subir o bajar"]},
        "PCLIM_VIS": {"DISCAP2": ["Ver, aun usando lentes"]},
        "PCLIM_LENG": {"DISCAP3": ["Hablar, comunicarse o conversar"]},
        "PCLIM_AUD": {"DISCAP4": ["Oír, aun usando aparato auditivo"]},
        "PCLIM_MOT2": {"DISCAP5": ["Vestirse, bañarse o comer"]},
        "PCLIM_MEN": {"DISCAP6": ["Poner atención o aprender cosas sencillas"]},
        "PCLIM_MEN2": {"DISCAP7": ["Limitación mental"]},
    },
    # 6y: INEGI's disability by activity, each edition's «degree unknown» label (_CELLS)
    ("personas", "2020"): _pcdisc("Se desconoce el grado de la discapacidad"),
    # 6y: the EIC 2025 estimates' own definitions (their percentages, as counts:
    # cpv_aggregates._PERCENT_BASES) — the disability by activity; born in another state
    # without the unspecified state (ENT_PAIS_NAC_INEGI); the ISSSTE federal or state; the
    # age groups, birthplace abroad and literacy of the 6–14 the legacy sets lack
    ("personas", "2025"): {
        **_pcdisc("Se desconoce el grado de la dificultad"),
        **_by_sex({"ENT_PAIS_NAC_INEGI": ["OtraEnt"]}, ("PNACOE", "PNACOE_M", "PNACOE_F")),
        **_by_sex({"ENT_PAIS_NAC_CAT": ["OtroPais"]}, ("PNACOP", "PNACOP_M", "PNACOP_F")),
        "PDER_ISTE": {"DHSERSAL_ISSSTE_T": [1]},
        **_by_sex({"EDAD_CAT": _AGES_0_14}, ("POB0_14", "POB0_14_M", "POB0_14_F")),
        **_by_sex({"EDAD_CAT": _AGES_6_14}, ("P_6A14", "P_6A14_M", "P_6A14_F")),
        **_by_sex({"EDAD_CAT": _AGES_6_14, "ALFABET": ["No"]},
                  ("P6A14AN", "P6A14AN_M", "P6A14AN_F")),
        # 6z: the population in familiar and not familiar households
        "POBHOG_FAM": {"CLASE_HOG": ["Familiar"]},
        "POBHOG_NFAM": {"CLASE_HOG": ["No familiar"]},
        **_PERSONS_2025,                                                     # 7a
    },
    # 6y: the EIC 2025's dwelling universe (its percentages' base: the class «Vivienda», the
    # legacy VIVPARH_CV), its water item's wording («solo», 2020 «sólo»), and its sanitary
    # service, which counts a latrine too (Censo 2020's VPH_EXCSA: the toilet only)
    ("viviendas", "2025"): {
        "VIVPARHAB_C": _VIVIENDA,
        "VPH_AGUADV": {**_VIVIENDA, "AGUA_ENTUBADA": _AGUA_DV_2025},
        "VPH_C_SERV": {**_VIVIENDA, "ELECTRICIDAD": ["Sí"], "AGUA_ENTUBADA": _AGUA_DV_2025,
                       "DRENAJE_CAT": ["Sí"]},
        "VPH_EXCSA": {**_VIVIENDA, "SERSAN": ["taza de baño (excusado o sanitario)?",
                                              "letrina (pozo u hoyo)?"]},
        **_DWELLINGS_2025,
        **_HOUSEHOLDS_2025,
        "HOG_AFRO": {"HOG_AFRO": ["Sí"]},              # 7a: on the household's HOG_AFRO
    },
}


# The household indicators of the dwelling set (the legacy ones and 6x's HOG_IND). A
# dwelling is a household from 2010 on, and CGPV 2000's dwelling rows are its households,
# but the Conteo 2005's dwelling file has one row per dwelling (its ITER counts households:
# +1.3% in Aguascalientes), so in an edition with a household table they are counted on it
# (6v; the 2005 ITER publishes no HOG_IND).
_HOUSEHOLD_INDICATORS = ("TOTHOG", "HOGJEF_F", "HOGJEF_M", "HOG_IND")
# 7f: the editions whose «Otro» dwelling classes carry the dwelling items, which their ITER
# counts: CGPV 2000's locales no construidos para habitación and viviendas móviles, CGPV
# 1990's móviles (its refugios are blank, as every «Otro» class from 2010 on — the legacy
# cells' «Vivienda» condition). Their dwelling indicators count every private dwelling: CGPV
# 2000's, so, equal its ITER in all 186 municipalities its sample enumerated completely.
_EVERY_CLASS = frozenset({"1990", "2000"})
# 7f: CGPV 2000's dwelling rows are households: its dwelling indicators (not the household
# ones, _HOUSEHOLD_INDICATORS) count the first household's row, one per dwelling.
_PER_DWELLING = {"2000": {"PRIMER_HOGAR": ["Sí"]}}


def _dwelling_cells(ind: str, cells: dict, period: str) -> dict:
    """A dwelling indicator's cells in ``period``: without the «Vivienda» condition where
    the «Otro» classes have the items (:data:`_EVERY_CLASS`), on one row per dwelling
    (:data:`_PER_DWELLING`); the household indicators as they are."""
    if ind in _HOUSEHOLD_INDICATORS:
        return cells
    if period in _EVERY_CLASS and cells.get("CLAVIVP_CAT") == _VIVIENDA["CLAVIVP_CAT"]:
        cells = {var: cats for var, cats in cells.items() if var != "CLAVIVP_CAT"}
    return {**cells, **_PER_DWELLING.get(period, {})}


@functools.cache
def _cpv_constraints(table: str) -> dict:
    """The legacy constraints in the CPV vocabulary: neutral DHSERSAL names, ``EDUC_INEGI``
    for ``EDUC`` (:data:`_CELL_VARS`), FD labels, INEGI's disability flags (:data:`_CELLS`);
    ``hogares``: the dwelling set's :data:`_HOUSEHOLD_INDICATORS`."""
    if table == "hogares":
        dwellings = _cpv_constraints("viviendas")
        return {ind: dwellings[ind] for ind in _HOUSEHOLD_INDICATORS}
    relabel = _relabels(table)
    out = {}
    for ind, cells in _base_constraints(table).items():
        out[ind] = {_CELL_VARS.get(var, var): [relabel.get(var, {}).get(c, c) for c in cats]
                    for var, cats in (cells or {}).items()}
    out.update(_CELLS.get(table, {}))
    return out


@functools.cache
def _aggregate_indicators(period: str, comparable: bool = True) -> frozenset[str]:
    """The indicators an edition publishes: its ITER's (through the crosswalk; an older
    edition's only where comparable, unless ``comparable=False``) or, for the EIC 2025,
    its national estimates' — the counts and the counts behind the percentages
    (``load_cpv_estimaciones(counts=True)``; 6y)."""
    from mxcensus._resources import cpv_iter_crosswalk
    from mxcensus.cpv_aggregates import _percent_count_names
    from mxcensus.data._cpv_catalog import get_edition

    edition = get_edition(period)
    if edition.has("iter"):
        # ``Comparable: false`` flags the older editions' columns of that name, never the
        # newest edition's own (the canonical definition).
        return frozenset(ind for ind, e in cpv_iter_crosswalk().items()
                         if e.get(period) and (not comparable
                                               or e.get("Comparable", True) is not False
                                               or period == max(k for k in e if k.isdigit())))
    if edition.has("estimaciones"):
        from mxcensus._resources import cpv_schema_map

        groups = cpv_schema_map()["estimaciones"]["groups"]
        columns = frozenset(c for g in groups.values()
                            if period in [str(p) for p in g["periods"]] for c in g["columns"])
        return columns | _percent_count_names(columns)
    return frozenset()


@functools.cache
def _published_name(ind: str, period: str) -> str:
    """The column under which ``period``'s aggregate publishes indicator ``ind`` (7g): the
    canonical name, unless the crosswalk pairs it with an older edition's column that
    ``harmonize=True`` does not rename — another date or definition, kept apart
    (``cpv_iter_crosswalk``: CGPV 2000 ``PNACOENT``, the residence five years earlier
    ``P5_RES95``/``P_RE2000``/``PRES2005``…, CGPV 2000 ``P5_CATOLIC`` and ``VP_SERSAN``, the
    Conteo 2005 ``P_SEGPOP``/``VPH_AGDV``/``VPH_NOAG``) — the name ``load_cpv_iter`` keeps.
    """
    from mxcensus._resources import cpv_iter_crosswalk
    from mxcensus.cpv import _crosswalk_renames

    source = (cpv_iter_crosswalk().get(ind) or {}).get(period)
    if not source or source == ind or source in _crosswalk_renames("iter", (period,)):
        return ind
    return source


def _frame_group(table: str, period: str) -> tuple[str, str, frozenset[str]]:
    """The schema group whose dictionary labels ``table``'s frame of ``period`` (table,
    gid) and the raw columns of the frame (upper case). CGPV 1990's and the Conteo 1995's
    dwelling frames come from their person files (``cpv._DWELLINGS_FROM_PERSONS``)."""
    from mxcensus._resources import cpv_schema_map
    from mxcensus.cpv import _DWELLINGS_FROM_PERSONS

    if table == "viviendas" and period in _DWELLINGS_FROM_PERSONS:
        return ("personas", _period_gid("personas", period),
                frozenset(_DWELLINGS_FROM_PERSONS[period]))
    gid = _period_gid(table, period)
    columns = cpv_schema_map()[table]["groups"][gid]["columns"]
    return table, gid, frozenset(c.upper() for c in columns)


def _categories(table: str, period: str) -> dict[str, tuple]:
    """Each categorical column of the labelled (``derived=True``) frame → its categories
    (the frame's own columns: a core entry such as ``SEXO`` labels only the editions that
    have the column — the Conteo 1995 names it ``P3_5``)."""
    from mxcensus import _schema_groups as _sg
    from mxcensus.cpv import variables_cpv_labels

    source, gid, columns = _frame_group(table, period)
    out = {}
    for col, meta in variables_cpv_labels(source, gid).items():
        if col.upper() in columns and _sg.norm_tipo(meta) == "categorical":
            out[col] = tuple(_sg._categorical_dtype(meta).categories)
    out.update({col: tuple(dt.categories) for col, dt in derived_dtypes(table, period).items()
                if isinstance(dt, pd.CategoricalDtype)})
    return out


def cpv_constraints(table: str, period: str | int) -> dict:
    """The census constraints an edition can reproduce from its microdata.

    The legacy sets (``constraints_personas``/``constraints_viviendas``: Censo 2020 ITER
    indicator → the microdata cells it counts) in the CPV vocabulary — the neutral
    ``DHSERSAL_*`` names, the Censo 2020 dictionary's labels, ``PCON_DISC``/``PCON_LIMI``/
    ``PSIND_LIM`` on INEGI's ``DISCAPACIDAD``/``LIMITACION``/``SIN_DISC_LIM`` flags, the
    education indicators on ``EDUC_INEGI`` (INEGI's primaria completa leaves out the técnica
    studies after primaria), the population by its household head's sex
    (``PHOGJEF_F``/``PHOGJEF_M`` on ``HOGJEF_SEXO``), the population in households
    (``POBHOG``: every person, as ``POBTOT``) and in indigenous households (``PHOG_IND`` on
    ``HOG_IND``, each edition's definition), the indigenous households (``HOG_IND`` on the
    dwellings' ``HOG_IND``; published by the EIC 2025 only), INEGI's limitation and
    disability by activity (``PCLIM_*`` on ``LIMITACION``, ``PCDISC_*`` with the unknown
    degree; 2020 and 2025) — keeping the indicators that
    (1) the edition publishes (its ITER, through ``cpv_iter_crosswalk`` — for 2010 only
    the indicators comparable with 2020's —; the EIC 2025's national estimates: its counts
    and the counts behind its percentages, ``load_cpv_estimaciones(counts=True)``) and (2)
    whose variables and
    categories all exist in the edition's labelled frame with ``derived=True``. EIC 2015
    publishes neither, so it has none. An edition's own definitions (Censo 2010's
    limitation in activity: ``PCON_LIM``, ``PSIN_LIM``, ``PCLIM_*`` on ``LIM_ACTIVIDAD``
    and ``DISCAP1``–``DISCAP7``; its religion groups: ``PNCATOLICA``; the legacy cells on
    the 1990–2010 samples' own items — literacy, language, attendance, floor, electricity,
    water, sanitary service, goods, with each dictionary's labels; CGPV 2000's media
    superior and superior, ``P18_CMEDSU``/``P18_CSUPER`` on ``EDUC_INEGI_DET``, and its
    income in minimum wages, ``P_1SM`` … ``P10_SM`` on ``INGTRMEN_SM`` (7c); the 2005/2010
    ``PHOG_IND``, the head or the partner only; the EIC 2025's born in another state without
    the unspecified one, ``PNACOE`` on ``ENT_PAIS_NAC_INEGI``, its ISSSTE federal or state,
    its toilet or latrine, its water item's wording, its dwelling universe ``VIVPARHAB_C``,
    the age groups ``P_6A14``/``POB0_14_F``…, ``PNACOP_F``/``_M`` and ``P6A14AN``; 6z: its
    other dwelling characteristics — crowding on ``OCUP_CUARTO_CAT``, walls, roofs, floors,
    cooking place and fuel, water and energy equipment, waste, pay TV, tenure and deeds —,
    its household items — the class on ``CLASE_HOG``, income from other sources on
    ``INGR_OTROS`` and each source, food access and insecurity, forced displacement — and
    the population by its household's class, ``POBHOG_FAM``/``POBHOG_NFAM``; 7a: its
    persons' — the five-year age groups by sex on ``EDAD_QUIN``, birthplace abroad by
    nationality, residence in 2020 on ``LUGAR_RES_5A``, self-identification as
    indigenous, disability by sex and age, attendance, education levels, position at
    work, the affiliated or recognising an access (``DHSERSAL_AFIL_ACCESO``), the users of
    each health service (``SERSALUD``; ``PUSU_SS``), the students' and the employed's
    place (``ENT_PAIS_ASI_INEGI``/``ENT_PAIS_TRAB_INEGI``) and time of commute, the
    students' modes (metro or metrobús, bus, taxi: ``MED_TRASLADO_ESC_METRO_T`` …), marital
    status by sex, the Afro-descendant households and their population on ``HOG_AFRO``)
    are added when it publishes the indicator. Each key is the column the edition publishes
    the indicator under (7g): a column of ``load_cpv_iter(period)``, of
    ``load_cpv_estimaciones(counts=True)`` for the EIC 2025. That is the canonical (newest)
    name, except where the crosswalk keeps an older edition's indicator apart — another date
    or definition, which ``harmonize=True`` does not rename (CGPV 2000 ``PNACOENT``, born
    outside the entity or the country; the residence five years earlier, ``P5_RES95``/
    ``P5_RESO95`` 2000, ``P_RE2000``/``P_OE2000`` 2005, ``PRES2005``/``PRESOE05`` 2010;
    CGPV 2000 ``P5_CATOLIC``, the Catholics of 5 and more, and ``VP_SERSAN``; the Conteo
    2005 ``P_SEGPOP``, ``VPH_AGDV``, ``VPH_NOAG``): the cells then count the edition's
    definition, and ``cpv_iter_crosswalk()`` gives the canonical name.
    Its ``HOG_MEN_ALIM`` («hogares con menores de edad»,
    the base of the minors' food items) has no cell: the questionnaire's filter of minors
    is not in the microdata (the households with someone under 18 run 0.05% over). Feed
    the result and the frame's dtypes to :func:`mxcensus.get_tables_dict`. For the EIC
    2025, each indicator is a column of ``load_cpv_estimaciones(counts=True)``. The
    published shares of a base the edition does not give and the averages are
    :func:`cpv_ratio_constraints` (7e).

    ``table`` is ``personas``, ``viviendas`` or, for the Conteo 2005, ``hogares``: its
    dwelling file has one row per dwelling, so the household indicators (``TOTHOG``,
    ``HOGJEF_F``/``HOGJEF_M``; ``HOG_IND``, which the 2005 ITER does not publish) are
    counted on ``load_cpv_hogares(2005, derived=True)`` instead of the dwellings. CGPV
    2000's dwelling file has one row per household: its dwelling indicators count the
    first household's row (``PRIMER_HOGAR`` «Sí»), its household indicators every row
    (7f). CGPV 1990's and 2000's dwelling indicators count every private dwelling, the
    «Otro» classes too, which their ITERs count (their items are recorded: 2000's locales
    and móviles, 1990's móviles; 2010–2025 leave them blank, hence the legacy cells'
    «Vivienda» condition); with the dwellings themselves (``VIVPAR_HAB``, 1990–2000), CGPV
    2000's equal its ITER in the 186 municipalities its sample enumerated completely.

    The person sets hold two totals, both every person of the sample: ``POBTOT`` (the
    ITER's, which adds the population of collective dwellings and without a dwelling) and
    ``POBHOG`` (the population in households, the samples' universe; CGPV 1990 and the
    Conteo 1995, which do not publish it, have ``OCUPVIVPAR``, the occupants of private
    dwellings, instead — 7f: the Conteo's person weights add up to it in every state but
    Chiapas, whose weights carry its official total, 17% above its ITER). The weights add
    up to ``POBHOG`` in Censo 2020 in every state (the EIC 2025 publishes ``POBHOG`` = ``POBTOT``,
    and its weights equal both in every municipality). CGPV 2000's and Censo 2010's add up
    to neither: they are above ``POBHOG`` in every state (2000 by 0.07–8.9%, most where the
    census counted a population without characteristics, which its ``POBTOT`` includes and
    its ``POBHOG`` leaves out; 2010 by 0.06–3.0%) and within 1.2% of ``POBTOT`` (below it,
    except three 2010 states, up to 0.9% above).
    """
    from mxcensus.data._cpv_catalog import get_edition

    period = str(period)
    households = get_edition(period).has("hogares")
    if table == "hogares" and not households:
        raise ValueError(f"CPV hogares: only the Conteo 2005 has a household table, not "
                         f"{period}")
    own = _EDITION_CELLS.get((table, period), {})
    published = _aggregate_indicators(period) | (
        own.keys() & _aggregate_indicators(period, comparable=False))
    if table == "viviendas" and households:           # counted on the households (6v)
        published -= set(_HOUSEHOLD_INDICATORS)
    cats = _categories(table, period)
    cells_of = {ind: _dwelling_cells(ind, cells, period) if table == "viviendas" else cells
                for ind, cells in {**_cpv_constraints(table), **own}.items()}
    return {_published_name(ind, period): cells for ind, cells in cells_of.items()
            if ind in published
            and all(var in cats and set(c) <= set(cats[var]) for var, c in cells.items())}


# ---------------------------------------------------------------------------------------
# Ratio constraints (7e): the published shares and averages whose base is not a count
# ---------------------------------------------------------------------------------------
# A published ratio r (a percentage of a base the estimates do not give, or an average)
# is the linear constraint Σ w·N = r / scale · Σ w·D: N and D are each record's numerator
# and denominator terms — 1, or a value (children, years of schooling, occupants, rooms),
# where the record is in the side's cells, else 0 — and a record with a ``known`` value
# missing counts on neither side (cpv_ratio_terms). Each was found on the microdata, as the
# percentages' bases (6y): the EIC 2025's, Σ FACTOR × term at all 2,769 published
# geographies within the rounding (0.005); Censo 2010's and 2020's ITER averages, exact in
# the municipalities their samples enumerated completely (FACTOR 1 for every person) where
# the population in households and of the age group equals the ITER's (STEP_7e.md); 7f:
# CGPV 2000's occupants per dwelling and per room, the same way, on its first households;
# CGPV 1990's and the Conteo 1995's, ratios of their published counts truncated, within
# their samples' band (STEP_7f.md).
# Left out: the medians and the total fertility rate (not linear in the weights), the
# ratios of published counts (REL_H_M, INDICE_ENV*, RAZON_DEP_*, the Conteo 1995's
# percentages: implied by the count constraints), CGPV 2000's GRADOESCO (it differs from
# the sample's schooling even where the sample is the census) and the Conteo 2005's
# averages (no schooling or rooms item).
def _ratio(numerator: dict, denominator: dict | None = None, *, value: str | None = None,
           base_value: str | None = None, known: tuple[str, ...] = (),
           scale: int = 1) -> dict:
    return {"numerator": numerator, "numerator_value": value,
            "denominator": numerator if denominator is None else denominator,
            "denominator_value": base_value, "known": known, "scale": scale}


_WOMEN_12PLUS = {"SEXO": ["Mujer"], "EDAD_CAT": _AGES_12PLUS}
# The employed who commute: a time, or «no es posible determinarlo» (5.9% of them in the
# EIC 2025), i.e. every employed person who names a mode — the base of the modes' shares.
_COMMUTERS = {**_EMPLOYED_CELLS, "TIE_TRASLADO_TRAB": [
    "Hasta 15 minutos", "16 a 30 minutos", "31 minutos a 1 hora",
    "Más de 1 hora y hasta 2 horas", "Más de 2 horas", "No es posible determinarlo"]}
# The employed's modes: the students' (_MODES_ESC) with the staff transport for the school's.
_MODES_TRAB = {("TPER" if k == "TESC" else k): ("Transporte de personal" if k == "TESC" else v)
               for k, v in _MODES_ESC.items()}


def _prom_hnv(item: str) -> dict:
    """The children born alive per woman of 12 and more who said how many."""
    return {"PROM_HNV": _ratio(_WOMEN_12PLUS, value=item, known=(item,))}


def _graproes(item: str = "ESCOACUM") -> dict:
    """The years of schooling (INEGI's accumulated ``ESCOACUM``) per person of 15 and more
    who gave them, and per woman and man."""
    return {ind: _ratio(cells, value=item, known=(item,)) for ind, cells in
            _by_sex({"EDAD_CAT": _AGES_15PLUS}, ("GRAPROES", "GRAPROES_M", "GRAPROES_F")).items()}


_RATIOS = {
    # The EIC 2025 estimates: the children born alive per woman and the share who died, the
    # 3+ who understand an indigenous language they do not speak (of those who do not speak
    # one: the unspecified speakers are out), the years of schooling, the employed's modes
    # (of the employed who commute; a person may name three).
    ("personas", "2025"): {
        **_prom_hnv("HIJOS_NAC_VIVOS"),
        "PCN_HF": _ratio(_WOMEN_12PLUS, value="HIJOS_FALLECIDOS", base_value="HIJOS_NAC_VIVOS",
                         known=("HIJOS_NAC_VIVOS", "HIJOS_FALLECIDOS"), scale=100),
        "PCN_P3NHLI_CLI": _ratio({"EDAD_CAT": _AGES_3PLUS, "HLENGUA": ["No"], "ELENGUA": ["Sí"]},
                                 {"EDAD_CAT": _AGES_3PLUS, "HLENGUA": ["No"]}, scale=100),
        **_graproes(),
        **{f"PCN_POCUP_{ind}": _ratio({**_EMPLOYED_CELLS, f"MED_TRASLADO_TRAB_{mode}": [1]},
                                      _COMMUTERS, scale=100)
           for ind, mode in _MODES_TRAB.items()},
    },
    # the occupants per room and per dwelling, of its dwelling universe (VIVPARHAB_C)
    ("viviendas", "2025"): {
        "PRO_OCUP_C": _ratio(_VIVIENDA, value="NUMPERS", base_value="TOTCUART",
                             known=("TOTCUART",)),
        "PROM_OCUP": _ratio(_VIVIENDA, value="NUMPERS"),
    },
    # Censo 2010/2020 ITER: every inhabited private dwelling (the «Otro» classes — locales,
    # móviles, refugios — have no rooms recorded); Censo 2010 divides the occupants of every
    # dwelling by the rooms of those that gave them (its PRO_OCUP_C counts the occupants of
    # the dwellings without rooms too).
    ("personas", "2020"): {**_prom_hnv("HIJOS_NAC_VIVOS"), **_graproes()},
    ("viviendas", "2020"): {
        "PRO_OCUP_C": _ratio({}, value="NUMPERS", base_value="TOTCUART", known=("TOTCUART",)),
        "PROM_OCUP": _ratio({}, value="NUMPERS"),
    },
    ("personas", "2010"): {**_prom_hnv("NUMHIJ"), **_graproes()},
    ("viviendas", "2010"): {
        "PRO_OCUP_C": _ratio({}, value="NUMPERS", base_value="TOTCUART"),
        "PROM_OCUP": _ratio({}, value="NUMPERS"),
    },
    # 7f: CGPV 2000's, once per dwelling (its first household's row, with the dwelling's
    # NUMPERS) and with its rooms less an exclusive kitchen nobody sleeps in, of the
    # dwellings that gave them; exact (rounded) in the 186 municipalities its sample
    # enumerated completely
    ("viviendas", "2000"): {
        "PRO_OCUP_C": _ratio(_PER_DWELLING["2000"], value="NUMPERS",
                             base_value="TOTCUART_INEGI", known=("TOTCUART_INEGI",)),
        "PROM_OCUP": _ratio(_PER_DWELLING["2000"], value="NUMPERS"),
    },
    # 7f: CGPV 1990's and the Conteo 1995's: OCUPVIVPAR over VIVPAR_HAB, truncated (both
    # published, every geography), and 1990's occupants over the rooms of the dwellings that
    # gave them (T_CUARTOS, the kitchen counted; Censo 2010's rule): their samples within
    # 0.07 (1990, a 10% extract) and 0.21 (1995: its dwelling and person weights are
    # calibrated apart)
    ("viviendas", "1990"): {
        "PRO_OCUP_C": _ratio({}, value="NUM_PERS", base_value="T_CUARTOS"),
        "PROM_OCUP": _ratio({}, value="NUM_PERS"),
    },
    ("viviendas", "1995"): {"PROM_OCUP": _ratio({}, value="NUMPERS")},
}


def _numeric_columns(table: str, period: str) -> frozenset[str]:
    """The numeric columns of the labelled frame with ``derived=True`` (``Int64``/
    ``Float64``, sentinels missing): the dictionary's, the derived numbers and the Conteo
    1995 dwellings' person count (7f, ``cpv._OCCUPANTS_FROM_PERSONS``)."""
    from mxcensus import _schema_groups as _sg
    from mxcensus.cpv import _OCCUPANTS_FROM_PERSONS, variables_cpv_labels

    source, gid, columns = _frame_group(table, period)
    own = {col for col, meta in variables_cpv_labels(source, gid).items()
           if col.upper() in columns and _sg.norm_tipo(meta) == "numeric"}
    derived = {col for col, dt in derived_dtypes(table, period).items()
               if not isinstance(dt, pd.CategoricalDtype)}
    counted = {_OCCUPANTS_FROM_PERSONS[period]} if (
        table == "viviendas" and period in _OCCUPANTS_FROM_PERSONS) else set()
    return frozenset(own | derived | counted)


def cpv_ratio_constraints(table: str, period: str | int) -> dict:
    """The published ratios an edition's microdata reproduce: shares of a base the edition
    does not publish, and averages.

    Each indicator → ``{"numerator": cells, "numerator_value": column | None,
    "denominator": cells, "denominator_value": column | None, "known": (columns…),
    "scale": 100 | 1}``. The cells are those of :func:`cpv_constraints` (variable → the
    categories counted, every variable at once; ``{}`` = every record), on the labelled
    frame with ``derived=True``; a value column makes each record count its value (number
    of children, years, occupants, rooms) instead of 1. The published value ``r`` of a
    geography then satisfies Σ w·N = r / scale · Σ w·D over its records, i.e. the linear
    constraint Σ w·(N − r / scale · D) = 0, which needs no count of the base:
    :func:`cpv_ratio_terms` gives each record's N and D. A record whose ``known`` columns
    are not all given counts on neither side (INEGI's averages leave out who did not say
    how many); any other missing value counts 0.

    - **EIC 2025** (the national estimates, ``load_cpv_estimaciones``; 15 person, 2
      dwelling): the employed's nine commute modes (``PCN_POCUP_CAM`` …, a share of the
      employed who commute, «no es posible determinarlo» included), the 3+ who understand an
      indigenous language they do not speak (``PCN_P3NHLI_CLI``, of those who answered
      «no»), the children who died (``PCN_HF``, of those born alive), the children born
      alive per woman (``PROM_HNV``), the years of schooling (``GRAPROES``, ``_F``,
      ``_M``), the occupants per room and per dwelling (``PRO_OCUP_C``, ``PROM_OCUP``):
      each equal to the estimates at every published geography within their rounding.
    - **Censo 2010 and 2020** (the ITER, ``load_cpv_iter``; 4 person, 2 dwelling):
      ``PROM_HNV``, ``GRAPROES`` (``_F``, ``_M``), ``PRO_OCUP_C``, ``PROM_OCUP``, exact in
      the municipalities their samples enumerated completely; elsewhere the samples'
      ratios sit within their sample band (the ITER is the full census).
    - **CGPV 2000** (2 dwelling, 7f): ``PROM_OCUP`` and ``PRO_OCUP_C`` once per dwelling
      (the first household's row, ``PRIMER_HOGAR``), the rooms less an exclusive kitchen
      nobody sleeps in (``TOTCUART_INEGI``), exact in the 186 municipalities its sample
      enumerated completely. Its ``GRADOESCO`` does not reproduce on the sample.
    - **CGPV 1990** (2 dwelling) and the **Conteo 1995** (1 dwelling; 7f): ``PROM_OCUP``
      (``OCUPVIVPAR`` / ``VIVPAR_HAB``, truncated) and 1990's ``PRO_OCUP_C`` (the occupants
      over the rooms of the dwellings that gave them, the kitchen counted): their samples
      within 0.07 (1990, a 10% extract) and 0.21 (1995, whose dwelling weights are
      calibrated apart from its person weights). The 1995 dwellings count their persons
      (``NUMPERS``, ``cpv._OCCUPANTS_FROM_PERSONS``).

    The Conteo 2005's sample has neither schooling nor rooms, so it has none.
    ``cpv_constraints`` holds the counts. As there, each key is the column the edition
    publishes the indicator under (7g).
    """
    from mxcensus.data._cpv_catalog import get_edition

    period = str(period)
    if table not in TABLES:
        raise ValueError(f"CPV ratio constraints exist for {list(TABLES)}, not {table!r}")
    if table == "hogares" and not get_edition(period).has("hogares"):
        raise ValueError(f"CPV hogares: only the Conteo 2005 has a household table, not "
                         f"{period}")
    ratios = _RATIOS.get((table, period), {})
    if not ratios:
        return {}
    published = _aggregate_indicators(period)
    cats, numeric = _categories(table, period), _numeric_columns(table, period)

    def available(spec: dict) -> bool:
        values = {spec["numerator_value"], spec["denominator_value"], *spec["known"]} - {None}
        return values <= numeric and all(var in cats and set(c) <= set(cats[var])
                                         for side in ("numerator", "denominator")
                                         for var, c in spec[side].items())

    return {_published_name(ind, period): spec for ind, spec in ratios.items()
            if ind in published and available(spec)}


def cpv_ratio_terms(df: pd.DataFrame, constraints: Mapping[str, dict]
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each record's numerator and denominator term of each ratio constraint
    (:func:`cpv_ratio_constraints`): two ``float64`` frames on ``df``'s index, one column
    per indicator. ``df`` is the labelled frame with ``derived=True`` (categories as cells
    name them, numeric values with the sentinels missing); a cell variable that is not
    categorical, or lacks a category the cell names, raises.

    The published ratio ``r`` of a geography is ``scale`` × Σ w·N / Σ w·D over its records
    (``w`` = ``FACTOR``): ``N.mul(w, axis=0).groupby(geo).sum()`` and the same for ``D``
    give both sums, and Σ w·(N − r / scale · D) = 0 is the constraint a fit imposes.
    """
    columns: dict[str, np.ndarray] = {}

    def cells(spec: dict, ind: str) -> np.ndarray:
        mask = np.ones(len(df), dtype=bool)
        for var, cats in spec.items():
            col = df[var]
            if not isinstance(col.dtype, pd.CategoricalDtype) or not (
                    set(cats) <= set(col.cat.categories)):
                raise ValueError(f"cpv_ratio_terms: {ind} counts {var} {cats}, which the "
                                 f"frame does not label (load it with labels=True, "
                                 f"derived=True)")
            mask &= col.isin(cats).to_numpy()
        return mask

    def value(name: str | None, ind: str) -> np.ndarray:
        if name is None:
            return np.ones(len(df))
        col = df[name]
        if not pd.api.types.is_numeric_dtype(col):
            raise ValueError(f"cpv_ratio_terms: {ind}'s value {name} is not numeric (load "
                             f"the frame with labels=True: sentinel codes become missing)")
        return col.astype("Float64").fillna(0).to_numpy(dtype=float)

    numerators, denominators = {}, {}
    for ind, spec in constraints.items():
        known = np.ones(len(df), dtype=bool)
        for name in spec["known"]:
            known &= df[name].notna().to_numpy()
        numerators[ind] = np.where(known & cells(spec["numerator"], ind),
                                   value(spec["numerator_value"], ind), 0.0)
        denominators[ind] = np.where(known & cells(spec["denominator"], ind),
                                     value(spec["denominator_value"], ind), 0.0)
    return (pd.DataFrame(numerators, index=df.index, columns=list(constraints)),
            pd.DataFrame(denominators, index=df.index, columns=list(constraints)))
