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
  item (``LNACEDO_C``/``LNACPAIS_C``, ``RES05EDO_C``/``RES05PAI_C``), and its co-residence
  pointer pairs (row number + code item: ``IDMADRE``/``IDMADREC``…), which give
  ``IDENT_PAREJA_CAT`` and the two co-residence flags but not ``IDENT_MADRE_CAT``/
  ``IDENT_PADRE_CAT`` (its «no vive aquí» merges 2020's other dwelling, dead, unknown);
- Censo 2010's 4-digit occupation (``OCUACTIV_C``) and its religion (``OTRAREL_C``, six
  digits), each with its own catalog: the occupation's first two digits are the SINCO
  group, the religion's group gives ``RELIGION_CAT`` (:data:`_RELIGION_2010`).

The coarse occupation is SINCO's two-digit group, labelled as in SINCO 2019; the 2010/2015
group 59, which SINCO 2019 dropped, joins 52 (:data:`_RECODE`). The coarse activity is the
SCIAN sector, the same in the 2010, 2015 and 2020 catalogs (2010's item: ``ACTTRAB_C``).
``SECTOR`` (new, 6o) groups it into INEGI's three sectors (primary, secondary, tertiary,
the 1990/2000 ITER's ``POCUSECP/S/T``) in 1990 (its CMAP division) and 2000–2025.

CGPV 2000 and the Conteo 2005 (unweighted) get the columns their items allow: age,
education (from their level-and-antecedent items), health coverage (one item per
institution: :data:`_DHSERSAL_ITEMS`), residence five years earlier, dwelling class, rooms
and drainage; 2000 also income, hours, activity, sector (SCIAN subsector), marital status,
birthplace and religion (asked of the 5+: its ``RELIGION_CAT`` adds «Blanco por pase»).

CGPV 1990 (unweighted) and the Conteo 1995 publish person files only (their dwelling
frames are built from them, ``cpv._DWELLINGS_FROM_PERSONS``): age, education (1990 from
its approved-grade, level and technical/normal items, 1995 from its level, grade and
technical-career items), activity, marital status, birthplace, residence five years
earlier, hours and income (1990's monthly income in new pesos: ÷ 1,000), 1990's religion
(asked of the 5+, as 2000's); dwelling rooms, bedrooms and drainage, and 1990's class.
CGPV 1990 writes 0 for «not asked» (``_NA`` in :data:`_RECODE`); neither asked health
coverage or disability per person (the Conteo counts them per household).

An unspecified entity (2020: 997) counts as ``OtraEnt`` in every edition, the legacy rule;
INEGI's tabulados count it as not specified (a few hundred persons per edition).

:func:`cpv_derivations` lists the columns per edition. The check that the source codes
match after the recode is a test (``tests/test_cpv_derived.py``).

**Constraints.** :func:`cpv_constraints` filters the legacy constraint sets (ITER
indicator → microdata cells, ``constraints_*.yaml``) to the indicators an edition can
reproduce, for :func:`mxcensus.crosstabs.get_tables_dict`, plus the indicators an edition
publishes under its own definition (:data:`_EDITION_CELLS`: Censo 2010's limitation; the
legacy cells on the 1990–2010 samples' own items; the 1990–2005 ITERs' own indicators) and
the population by its household head's sex (``PHOGJEF_F``/``PHOGJEF_M`` on
``HOGJEF_SEXO``, :data:`_CELLS`), which the legacy sets lack.
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

TABLES = ("personas", "viviendas")

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
        # Birthplace and residence in 1995: 600 = «otro país, no se sabe cuál» (2020: 998).
        "ENT_PAIS_NAC": {600: 998},
        "ENT_PAIS_RES_5A": {600: 998},
        # Dwelling class (CLAVIV): casa independiente (2020: casa única en el terreno),
        # departamento, vecindad, azotea, local no construido para habitación, vivienda
        # móvil, refugio, not specified.
        "CLAVIVP": {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 9: 99},
        # 26 rooms (2020's code list stops at 25; both «3+»).
        "TOTCUART": {26: 25},
        # Sex: 1 man, 2 woman (2020: 1, 3); read for the household head (6s, JEFE_SEXO).
        "SEXO": {2: 3},
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
            "EDAD": ("EDAD", "ANO_CUMP", "P3_6"),
            "CONACT": ("CONACT", "ACT_PRIN", "P7_1"),
            "SITUA_CONYUGAL": ("SITUA_CONYUGAL", "ESTCON", "EST_CIVIL", "P6_1"),
            "ENT_PAIS_NAC": ("ENT_PAIS_NAC", "LNACEDO_C", "CVE_P_NAC", "P3_7B"),
            "ENT_PAIS_RES_5A": ("ENT_PAIS_RES_5A", "ENT_PAIS_RES10", "RES95EDO_C", "LURE2000",
                                "CVE_P_RES", "P4_6A"),
            "ACTIVIDADES_C": ("ACTIVIDADES_C", "ACTTRAB_C"),
            "INGTRMEN": ("INGTRMEN", "INGRESOS", "INGRESO", "P7_9MP"),
            "HORTRA": ("HORTRA", "HORAS", "P7_6"),
            "CLAVIVP": ("CLAVIVP", "CLAVIV", "CLAVIVPA", "T_VIV"),
            "CUADORM": ("CUADORM", "CUARDOM", "P_DORMIR", "P1_6"),
            "TOTCUART": ("TOTCUART", "NUMCUAR", "T_CUARTOS", "P1_7"),
            "DRENAJE": ("DRENAJE", "DIS_DREN", "P1_13"),
            "SEXO": ("SEXO", "P3_5"),
            # the relationship to the household head (own codes: _HEAD_CODES)
            "PARENTESCO": ("PARENTESCO", "PARENT", "OTROPARE_C", "P3_4")}

# The household head's code in each edition's relationship item (6t; codes as numbers):
# 2020/2025 PARENTESCO 101 «Jefa(e)»; Censo 2010 and EIC 2015 PARENT 01 «Jefe(a)»; the Conteo
# 2005's PARENT 101 «Jefe(a)» and 102 «Persona sola»; CGPV 2000's OTROPARE_C 100 (the head
# group of its catalog); the Conteo 1995's P3_4 1 «Jefe o Jefa» (its catalog's 7 «Persona
# sola» marks a few persons of households that have a 1). One per household in every state.
_HEAD_CODES: dict[str, tuple[int, ...]] = {
    "1995": (1,), "2000": (100,), "2005": (101, 102), "2010": (1,), "2015": (1,),
    "2020": (101,), "2025": (101,)}

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
# INEGI's three sectors of activity (the 1990/2000 ITER's POCUSECP/S/T): primary =
# agriculture, livestock, forestry, fishing and hunting; secondary = mining, electricity and
# water, construction, manufacturing; tertiary = trade, transport, services, government.
_SECTOR = pd.CategoricalDtype(["Primario", "Secundario", "Terciario", "No especificado",
                               "Blanco por pase"])
_DTYPES = {"DISCAPACIDAD": _YES_NO, "LIMITACION": _YES_NO, "SIN_DISC_LIM": _YES_NO,
           "LIM_ACTIVIDAD": _YES_NO, "MADRE_EN_VIVIENDA": _YES_NO, "PADRE_EN_VIVIENDA": _YES_NO,
           "EDUC_INEGI": _EDUC_INEGI, "SECTOR": _SECTOR}
# Derived columns with another table's legacy dtype: the household head's sex on the
# person (6t) has the dwelling item's.
_DTYPE_LIKE = {"HOGJEF_SEXO": ("viviendas", "JEFE_SEXO")}
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
    """The dtype each derived column has in the legacy loader's schema."""
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
    """``EDUC`` (the legacy map of level and grade) and ``EDUC_INEGI`` (the same, with the
    técnica studies after primaria, «Primaria_com» in ``EDUC``, as «Técnica_primaria»)."""
    key = (src["NIVACAD"].fillna(_BLANK) + 1) * 1000 + src["ESCOLARI"].fillna(_BLANK) + 1
    educ = _as(key.map(_educ_map()), "personas", "EDUC")
    tecnica = src["NIVACAD"].eq(_TECNICA_PRIMARIA) & educ.notna()
    return {"EDUC": educ,
            "EDUC_INEGI": _as(educ.astype(object).mask(tecnica, "Técnica_primaria"),
                              "personas", "EDUC_INEGI")}


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


def _dhsersal(codes: tuple[int, ...]):
    """The dummies of the 2020 ``codes`` an edition offers (1–6 public, 1–8 any)."""
    def fn(src):
        d1, d2 = src["DHSERSAL1"], src["DHSERSAL2"]
        has = {code: d1.eq(code) | d2.eq(code) for code in codes}
        out = {_DHSERSAL[code]: has[code] for code in codes}
        out["DHSERSAL_PUB"] = pd.concat([has[c] for c in codes if c <= 6], axis=1).any(axis=1)
        out["DHSERSAL_AFIL"] = pd.concat([has[c] for c in codes if c <= 8], axis=1).any(axis=1)
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
        out = {_DHSERSAL[code]: has[code] for code in codes}
        out["DHSERSAL_PUB"] = pd.concat([has[c] for c in codes if c <= 6], axis=1).any(axis=1)
        out["DHSERSAL_AFIL"] = pd.concat([has[c] for c in codes if c <= 8], axis=1).any(axis=1)
        return _as_dummies(out, unknown)
    return fn


def _dhsersal_names(codes: tuple[int, ...]) -> tuple[str, ...]:
    return (*(_DHSERSAL[c] for c in codes), "DHSERSAL_PUB", "DHSERSAL_AFIL")


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


def _ent_pais_cat(var: str, name: str, abroad: str | None = None):
    """Entity or country → ``OtraEnt``/``OtroPais``/…, ``EstaEnt`` for the person's entity
    (Censo 2010 splits the answer: the entity item ``var``, else the country item
    ``abroad``)."""
    def fn(src):
        code = src[var] if abroad is None else src[var].fillna(src[abroad])
        cat = _mapped(code, "personas", name, name)
        return {name: cat.mask(code.eq(src["ENT"]), "EstaEnt")}
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


def _religion_2010(src):
    """Censo 2010's religion → ``RELIGION_CAT`` (:data:`_RELIGION_2010`); a code of another
    group is left missing (:func:`derive` reports it)."""
    code = src["OTRAREL_C"]
    group = code.where(code.between(100000, 999999)) // 10000
    code2020 = code.map(_RELIGION_2010_CODES).fillna(group.map(_RELIGION_2010))
    return {"RELIGION_CAT": _mapped(code2020, "personas", "RELIGION_CAT", "RELIGION_CAT")}


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
    religion of persons aged 5+ only, so their ``RELIGION_CAT`` adds «Blanco por pase»."""
    if table == "personas" and period in ("1990", "2000"):
        cats = list(_legacy_dtypes("personas")["RELIGION_CAT"].categories)
        return {"RELIGION_CAT": pd.CategoricalDtype([*cats, "Blanco por pase"])}
    return {}


def _ingtrhog_cat(src):
    return {"INGTRHOG_CAT": _cut(src["INGTRHOG"], "viviendas", "INGTRHOG_CAT", _INCOME_BINS,
                                 _INCOME_LABELS, right=False, blank=2e6)}


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


def _periods_by(codes: Mapping[str, tuple]) -> dict[tuple, tuple[str, ...]]:
    """Edition → codes, inverted: codes → the editions that share them."""
    out: dict[tuple, tuple[str, ...]] = {}
    for period, value in codes.items():
        out[value] = (*out.get(value, ()), period)
    return out


@dataclass(frozen=True)
class _Derivation:
    table: str
    columns: tuple[str, ...]
    sources: tuple[str, ...]
    periods: tuple[str, ...]          # editions whose source codes were verified
    func: Callable[[pd.DataFrame], Mapping[str, pd.Series]]
    household: bool = False           # func also reads each record's household (_HOUSEHOLD)


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
_EDUC = ("EDUC", "EDUC_INEGI")


@functools.cache
def _registry() -> tuple[_Derivation, ...]:
    D = _Derivation
    per, viv = "personas", "viviendas"
    esc15, trab15 = _traslado_2015(_ESC[0]), _traslado_2015(_TRAB[0])
    fin15 = _financiamiento_2015()
    return (
        D(per, ("EDAD_CAT",), ("EDAD",), (*_OLDEST, *_EVERY), _edad_cat),
        D(per, ("INGTRMEN_CAT",), ("INGTRMEN",), ("1995", *_SINCE_2000), _ingtrmen_cat),
        D(per, ("INGTRMEN_CAT",), ("INGTRMEN", "CONACT"), ("1990",), _ingtrmen_1990),
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
        D(per, ("CONACT_CAT",), ("CONACT",), (*_OLDEST, *_SINCE_2000),
          _cat(per, "CONACT", "CONACT_CAT")),
        D(per, ("SITUA_CONYUGAL_CAT",), ("SITUA_CONYUGAL",), (*_OLDEST, *_SINCE_2000),
          _cat(per, "SITUA_CONYUGAL", "SITUA_CONYUGAL_CAT")),
        D(per, ("ENT_PAIS_NAC_CAT",), ("ENT_PAIS_NAC", "ENT"), (*_OLDEST, "2000", *_SINCE_2015),
          _ent_pais_cat("ENT_PAIS_NAC", "ENT_PAIS_NAC_CAT")),
        D(per, ("ENT_PAIS_NAC_CAT",), ("LNACEDO_C", "LNACPAIS_C", "ENT"), ("2010",),
          _ent_pais_cat("LNACEDO_C", "ENT_PAIS_NAC_CAT", abroad="LNACPAIS_C")),
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
        D(per, ("RELIGION_CAT",), ("OTRAREL_C",), ("2000",), _religion_2000),
        D(per, ("RELIGION_CAT",), ("RELIGION",), ("1990",), _religion_1990),
        *(D(per, ("HOGJEF_SEXO",), ("PARENTESCO", "SEXO"), periods, _hogjef_sexo(heads),
            household=True) for heads, periods in _periods_by(_HEAD_CODES).items()),
        D(viv, ("CLAVIVP_CAT",), ("CLAVIVP",), ("1990", "2000", "2005", "2010", *_SINCE_2015),
          _cat(viv, "CLAVIVP", "CLAVIVP_CAT")),
        D(viv, ("JEFE_SEXO",), ("SEXO",), ("2000", "2005", "2010"), _jefe_sexo),  # the head's
        D(viv, ("CUADORM_CAT",), ("CUADORM",), (*_OLDEST, *_EVERY),
          _cat(viv, "CUADORM", "CUADORM_CAT")),
        D(viv, ("TOTCUART_CAT",), ("TOTCUART",), (*_OLDEST, *_EVERY),
          _cat(viv, "TOTCUART", "TOTCUART_CAT")),
        D(viv, ("DRENAJE_CAT",), ("DRENAJE",), (*_OLDEST, *_EVERY),
          _cat(viv, "DRENAJE", "DRENAJE_CAT")),
        D(viv, ("INGTRHOG_CAT",), ("INGTRHOG",), _SINCE_2000, _ingtrhog_cat),
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
def derived_dtypes(table: str, period: str | int) -> dict[str, pd.CategoricalDtype]:
    """The dtype of each derived column of ``table`` in ``period`` (all categorical)."""
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
    """Pandera schema of the derived columns: their categorical dtype, no missing value."""
    return pa.DataFrameSchema({col: pa.Column(dtype, nullable=False)
                               for col, dtype in derived_dtypes(table, period).items()},
                              strict=False)


def _source(df: pd.DataFrame, name: str) -> str:
    for alias in _ALIASES.get(name, (name,)):
        if alias in df.columns:
            return alias
    raise KeyError(name)


_HOUSEHOLD = "_HOGAR"      # the household's number, in a derivation's ``src`` (household=True)


def _household(df: pd.DataFrame) -> pd.Series:
    """Each record's household, numbered: the entity and ``ID_HOG`` in the editions with a
    household level (1995–2005), else the entity and ``ID_VIV`` (one household per dwelling;
    the entity makes Censo 2010's state-scoped serials unique). A frame without keys gets the
    1995–2005 composite keys (``cpv._composite_keys``)."""
    from mxcensus.cpv import _composite_keys

    keyed = _composite_keys(df, "personas")
    key = next((k for k in ("ID_HOG", "ID_VIV") if k in keyed.columns), None)
    if key is None:
        raise ValueError("CPV personas: HOGJEF_SEXO needs the household key (ID_HOG or "
                         "ID_VIV, or the parts they are derived from)")
    return keyed.groupby([keyed[_source(keyed, "ENT")], keyed[key]], sort=False).ngroup() \
        .set_axis(df.index)


def _codes(raw: pd.Series, recode: Mapping[int, int] | None) -> pd.Series:
    """A raw code column as float codes (blank → NaN), recoded into the 2020 code space."""
    s = raw if pd.api.types.is_numeric_dtype(raw) else \
        pd.to_numeric(raw.astype("string").str.strip().replace("", pd.NA), errors="raise")
    s = s.astype(float)
    if recode:
        s = s.where(~s.isin(list(recode)), s.map(recode))
    return s


def derive(df: pd.DataFrame, table: str, period: str | int) -> pd.DataFrame:
    """``df`` (a raw CPV ``table`` frame of edition ``period``) plus its derived columns.

    Reads the source items' raw codes (zero-padded or not), so call it before labelling;
    the derived columns are ``Categorical`` (0/1 for the dummies). A source code with no
    derived category raises ``ValueError`` (a code the recode table does not know).
    """
    period = str(period)
    derivations = _derivations(table, period)
    if not derivations:
        warnings.warn(f"CPV {table} {period}: no derived columns are verified for this "
                      f"edition (see cpv_derivations()).", stacklevel=2)
    recode = _RECODE.get(period, {})
    clash = [c for d in derivations for c in d.columns if c in df.columns]
    if clash:
        raise ValueError(f"CPV {table} {period}: derived columns already present: {clash}")
    new: dict[str, pd.Series] = {}
    problems: dict[str, list] = {}
    cache: dict[str, pd.Series] = {}
    for d in derivations:
        try:
            cols = {s: _source(df, s) for s in d.sources}
        except KeyError as exc:
            raise ValueError(f"CPV {table} {period}: {d.columns[0]} needs {exc.args[0]!r}, "
                             f"absent from the frame") from None
        for s, col in cols.items():
            if s not in cache:
                cache[s] = _codes(df[col], recode.get(s))
        src = pd.DataFrame({s: cache[s] for s in cols}, index=df.index)
        if d.household:
            if _HOUSEHOLD not in cache:
                cache[_HOUSEHOLD] = _household(df)
            src[_HOUSEHOLD] = cache[_HOUSEHOLD]
        for name, values in d.func(src).items():
            values = pd.Series(values, index=df.index) if not isinstance(values, pd.Series) \
                else values.set_axis(df.index)
            if values.isna().any():
                bad = src.loc[values.isna().to_numpy()].drop_duplicates().head(12)
                problems[name] = bad.to_dict("records")
            new[name] = values
    if problems:
        raise ValueError(f"CPV {table} {period}: source codes without a derived category "
                         f"(add them to cpv_derived._RECODE): {problems}")
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
# the EIC 2025 estimates).
_CELLS = {"personas": {"PCON_DISC": {"DISCAPACIDAD": ["Sí"]},
                       "PCON_LIMI": {"LIMITACION": ["Sí"]},
                       "PSIND_LIM": {"SIN_DISC_LIM": ["Sí"]},
                       "PHOGJEF_F": {"HOGJEF_SEXO": ["Mujer"]},
                       "PHOGJEF_M": {"HOGJEF_SEXO": ["Hombre"]}}}

_AGES_5PLUS = ["5", "6-7", "8-11", "12-14", "15-17", "18-24", "25-49", "50-59", "60-64",
               "65-130"]
_AGES_15PLUS = _AGES_5PLUS[4:]
_AGES_12PLUS, _AGES_18PLUS = _AGES_5PLUS[3:], _AGES_5PLUS[5:]
_AGES_6_14, _AGES_15_24 = ["6-7", "8-11", "12-14"], ["15-17", "18-24"]
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

# Indicators an edition publishes under its own definition, on its own items: Censo 2010's
# limitation in activity (its PCLIM_VIS/PCLIM_MOT2 share 2020's names, not their concept)
# and its protestant, evangelical and other biblical religions (2020's protestant/evangelical
# group, which also holds the neo-Israelite movements its ITER counts in POTRAS_REL). CGPV
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
_EDITION_CELLS = {
    ("personas", "1990"): {
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
        "POBFEM": {"P3_5": ["Mujer"]},
        "POBMAS": {"P3_5": ["Hombre"]},
        "P15YM_AN": {"EDAD_CAT": _AGES_15PLUS, "P5_1": ["No"]},
        "P_6A14_AN": {"EDAD_CAT": _AGES_6_14},                                    # 6o
        "P6_14SLEE": {"EDAD_CAT": _AGES_6_14, "P5_1": ["Sí"]},
        "P6_14NLEE": {"EDAD_CAT": _AGES_6_14, "P5_1": ["No"]},
        "P15_ALFAB": {"EDAD_CAT": _AGES_15PLUS, "P5_1": ["Sí"]},
    },
    ("viviendas", "1995"): {
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
        "P5_NCATOLI": {"RELIGION_CAT": ["Protestante/cristiano evangélico", "Otros credos"]},
        "P5_SINRELI": {"RELIGION_CAT": ["Protestante/cristiano evangélico", "Otros credos",
                                        "Sin religión / Sin adscripción religiosa"]},
        "P15_POSPRI": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _POSPRIMARIA},
        "P15_SINSEC": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _SIN_POSPRIMARIA},
        "P15_CONSEC": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": _POSPRIMARIA[:3]},
        "P15_CMEDSS": {"EDAD_CAT": _AGES_15PLUS, "EDUC_INEGI": ["Posbásica"]},
        "P18_SMEDSU": {"EDAD_CAT": _AGES_18PLUS,
                       "EDUC_INEGI": [*_SIN_POSPRIMARIA, *_POSPRIMARIA[:3]]},
        **_SECTOR_CELLS,
        "POCUNINGR": {**_EMPLOYED_CELLS, "INGTRMEN_CAT": ["No recibe ingresos"]},
        "P41_48HTR": {**_EMPLOYED_CELLS, "HORTRA_CAT": ["41-48"]},
        "P48_HTR": {**_EMPLOYED_CELLS, "HORTRA_CAT": ["49-56", "57-60", "61-80", "81YMAS"]},
    },
    ("viviendas", "2000"): {
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
        "PNCATOLICA": {"RELIGION_CAT": ["Protestante/cristiano evangélico"]},
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
}


@functools.cache
def _cpv_constraints(table: str) -> dict:
    """The legacy constraints in the CPV vocabulary: neutral DHSERSAL names, ``EDUC_INEGI``
    for ``EDUC`` (:data:`_CELL_VARS`), FD labels, INEGI's disability flags (:data:`_CELLS`)."""
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
    its national estimates'."""
    from mxcensus._resources import cpv_iter_crosswalk
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
        return frozenset(c for g in groups.values() if period in [str(p) for p in g["periods"]]
                         for c in g["columns"])
    return frozenset()


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
    out.update({col: tuple(dt.categories) for col, dt in derived_dtypes(table, period).items()})
    return out


def cpv_constraints(table: str, period: str | int) -> dict:
    """The census constraints an edition can reproduce from its microdata.

    The legacy sets (``constraints_personas``/``constraints_viviendas``: Censo 2020 ITER
    indicator → the microdata cells it counts) in the CPV vocabulary — the neutral
    ``DHSERSAL_*`` names, the Censo 2020 dictionary's labels, ``PCON_DISC``/``PCON_LIMI``/
    ``PSIND_LIM`` on INEGI's ``DISCAPACIDAD``/``LIMITACION``/``SIN_DISC_LIM`` flags, the
    education indicators on ``EDUC_INEGI`` (INEGI's primaria completa leaves out the técnica
    studies after primaria), and the population by its household head's sex
    (``PHOGJEF_F``/``PHOGJEF_M`` on ``HOGJEF_SEXO``) — keeping the indicators that
    (1) the edition publishes (its ITER, through ``cpv_iter_crosswalk`` — for 2010 only
    the indicators comparable with 2020's —; the EIC 2025's national estimates) and (2)
    whose variables and
    categories all exist in the edition's labelled frame with ``derived=True``. EIC 2015
    publishes neither, so it has none. An edition's own definitions (Censo 2010's
    limitation in activity: ``PCON_LIM``, ``PSIN_LIM``, ``PCLIM_*`` on ``LIM_ACTIVIDAD``
    and ``DISCAP1``–``DISCAP7``; its religion groups: ``PNCATOLICA``; the legacy cells on
    the 1990–2010 samples' own items — literacy, language, attendance, floor, electricity,
    water, sanitary service, goods, with each dictionary's labels) are added when it
    publishes the indicator. Feed the
    result and the frame's dtypes to :func:`mxcensus.get_tables_dict`.
    """
    period = str(period)
    own = _EDITION_CELLS.get((table, period), {})
    published = _aggregate_indicators(period) | (
        own.keys() & _aggregate_indicators(period, comparable=False))
    cats = _categories(table, period)
    return {ind: cells for ind, cells in {**_cpv_constraints(table), **own}.items()
            if ind in published
            and all(var in cats and set(c) <= set(cats[var]) for var, c in cells.items())}
