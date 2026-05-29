"""Extended questionnaire person table: preprocessing, schema, and loader."""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from mxcensus._resources import variables_personas
from mxcensus.utils import expand_cat_map


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def dhsersal_create_dummies(df):
    dhsersal_or_cats = [
        "DHSERSAL_IMSS",
        "DHSERSAL_ISSSTE",
        "DHSERSAL_ISSSTE_E",
        "DHSERSAL_P_D_M",
        "DHSERSAL_Popular_NGenración_SBienestar",
        "DHSERSAL_IMSS_Prospera/Bienestar",
        "DHSERSAL_Privado",
        "DHSERSAL_Otro",
        "DHSERSAL_No afiliado",
    ]
    dhsersal1_dummies = pd.get_dummies(df.DHSERSAL1, prefix="DHSERSAL")
    dhsersal2_dummies = pd.get_dummies(
        df.DHSERSAL2,
        prefix="DHSERSAL",
    )
    dhsersal_df = dhsersal1_dummies.add(dhsersal2_dummies, fill_value=0)[
        dhsersal_or_cats
    ].astype(int)
    dhsersal_df["DHSERSAL_PUB"] = (
        dhsersal_df[dhsersal_or_cats[:6]].T.sum() > 0
    ).astype(int)
    dhsersal_df["DHSERSAL_AFIL"] = (
        dhsersal_df[dhsersal_or_cats[:8]].T.sum() > 0
    ).astype(int)
    dhsersal_df = dhsersal_df.astype("category")

    return dhsersal_df


def med_traslado_esc_create_dummies(df):
    med_traslado_esc1_dummies = pd.get_dummies(
        df.MED_TRASLADO_ESC1, prefix="MED_TRASLADO_ESC"
    )
    med_traslado_esc2_dummies = pd.get_dummies(
        df.MED_TRASLADO_ESC2, prefix="MED_TRASLADO_ESC"
    )
    med_traslado_esc3_dummies = pd.get_dummies(
        df.MED_TRASLADO_ESC3, prefix="MED_TRASLADO_ESC"
    )
    df_agg = (
        med_traslado_esc1_dummies.add(med_traslado_esc2_dummies, fill_value=0)
        .add(med_traslado_esc3_dummies, fill_value=0)
        .astype(int)
        .replace({2: 1, 3: 1})
    )
    return df_agg


def med_traslado_trab_create_dummies(df):
    med_traslado_trab1_dummies = pd.get_dummies(
        df.MED_TRASLADO_TRAB1, prefix="MED_TRASLADO_TRAB"
    )
    med_traslado_trab2_dummies = pd.get_dummies(
        df.MED_TRASLADO_TRAB2, prefix="MED_TRASLADO_TRAB"
    )
    med_traslado_trab3_dummies = pd.get_dummies(
        df.MED_TRASLADO_TRAB3, prefix="MED_TRASLADO_TRAB"
    )
    df_agg = (
        med_traslado_trab1_dummies.add(med_traslado_trab2_dummies, fill_value=0)
        .add(med_traslado_trab3_dummies, fill_value=0)
        .astype(int)
        .replace({2: 1, 3: 1})
    )
    return df_agg


def dis_create_agg_cols(df):
    df_dis = pd.DataFrame(index=df.index)

    dis_agg = (
        df.DIS_VER.astype(str)
        + df.DIS_OIR.astype(str)
        + df.DIS_CAMINAR.astype(str)
        + df.DIS_RECORDAR.astype(str)
        + df.DIS_BANARSE.astype(str)
        + df.DIS_HABLAR.astype(str)
    )

    def has_con(c):
        if ("3" in c) or ("4" in c):
            return "Sí"
        elif ("8" in c) or ("9" in c):
            return "No especificado"
        else:
            return "No"

    def has_limi(c):
        if "2" in c:
            return "Sí"
        elif ("8" in c) or ("9" in c):
            return "No especificado"
        else:
            return "No"

    df_dis["DIS_CON"] = dis_agg.apply(has_con)
    df_dis["DIS_LIMI"] = dis_agg.apply(has_limi)

    return df_dis


def get_educ_col(df):
    variables = variables_personas()
    educ = (df.NIVACAD.astype(str) + "_" + df.ESCOLARI.astype(str)).map(
        variables["EDUC"]["Categorías"]
    )
    return educ


def preprocessor(df):
    variables = variables_personas()
    df = df.copy()

    # Derive new columns
    new_cols = [
        "ENT_PAIS_NAC_CAT",
        "RELIGION_CAT",
        "ENT_PAIS_RES_CAT",
        "SITUA_CONYUGAL_CAT",
        "CONACT_CAT",
        "IDENT_MADRE_CAT",
        "IDENT_PADRE_CAT",
        "IDENT_HIJO_CAT",
        "IDENT_PAREJA_CAT",
    ]
    for col in new_cols:
        parent = variables[col]["Original"]
        cat_map = expand_cat_map(variables[col]["Categorías"])
        df[col] = df[parent].fillna(-1).map(cat_map)
    df["OCUPACION_C_COARSE"] = (
        np.floor(df["OCUPACION_C"] / 10)
        .fillna(-1)
        .map(expand_cat_map(variables["OCUPACION_C_COARSE"]["Categorías"]))
    )
    df["EDAD_CAT"] = pd.cut(
        df.EDAD,
        (0, 3, 5, 6, 8, 12, 15, 18, 25, 50, 60, 65, 200, 1e6),
        right=False,
        labels=[
            "0-2",
            "3-4",
            "5",
            "6-7",
            "8-11",
            "12-14",
            "15-17",
            "18-24",
            "25-49",
            "50-59",
            "60-64",
            "65-130",
            "No especificado",
        ],
    )
    df["INGTRMEN_CAT"] = pd.cut(
        df.INGTRMEN.fillna(2e6),
        (0, 1, 1000, 5000, 10000, 20000, 40000, 80000, 150000, 999999, 1e6, 3e6),
        right=False,
        labels=[
            "No recibe ingresos",
            "1-999",
            "1,000-4,999",
            "5,000-9,999",
            "10,000-19,999",
            "20,000-39,999",
            "40,000-79,999",
            "80,000-149,999",
            "150,000yMas",
            "No especificado",
            "Blanco por pase",
        ],
    )
    df["HORTRA_CAT"] = pd.cut(
        df.HORTRA.fillna(2e6),
        [-1, 5, 10, 20, 40, 48, 56, 60, 80, 998, 1e6, 3e6],
        right=True,
        labels=[
            "0-5",
            "6-10",
            "11-20",
            "21-40",
            "41-48",
            "49-56",
            "57-60",
            "61-80",
            "81YMAS",
            "No especificado",
            "Blanco por pase",
        ],
    )
    df["ACTIVIDADES_C_COARSE"] = (
        np.floor(df["ACTIVIDADES_C"] / 100)
        .fillna(-1)
        .map(expand_cat_map(variables["ACTIVIDADES_C_COARSE"]["Categorías"]))
    )

    # Some special new columns requier some additional processing
    df["ENT_PAIS_NAC_CAT"] = df["ENT_PAIS_NAC_CAT"].mask(
        df["ENT_PAIS_NAC"] == df["ENT"], "EstaEnt"
    )
    df["ENT_PAIS_RES_CAT"] = df["ENT_PAIS_RES_CAT"].mask(
        df["ENT_PAIS_RES_5A"] == df["ENT"], "EstaEnt"
    )

    # Disability needs aggregation
    df = pd.concat([df, dis_create_agg_cols(df)], axis=1)

    # Category mappings
    cols = [
        "COBERTURA",
        "CLAVIVP",
        "SEXO",
        "PARENTESCO",
        "IDENT_MADRE",
        "IDENT_PADRE",
        "NACIONALIDAD",
        "SERSALUD",
        "AFRODES",
        "REGIS_NAC",
        "DHSERSAL1",
        "DHSERSAL2",
        "RELIGION",
        "DIS_VER",
        "DIS_OIR",
        "DIS_CAMINAR",
        "DIS_RECORDAR",
        "DIS_BANARSE",
        "DIS_HABLAR",
        "DIS_MENTAL",
        "CAU_VER",
        "CAU_OIR",
        "CAU_CAMINAR",
        "CAU_RECORDAR",
        "CAU_BANARSE",
        "CAU_HABLAR",
        "CAU_MENTAL",
        "HLENGUA",
        "QDIALECT_INALI",
        "HESPANOL",
        "ELENGUA",
        "PERTE_INDIGENA",
        "ASISTEN",
        "MUN_ASI",
        "ENT_PAIS_ASI",
        "TIE_TRASLADO_ESCU",
        "MED_TRASLADO_ESC1",
        "MED_TRASLADO_ESC2",
        "MED_TRASLADO_ESC3",
        "NIVACAD",
        "ESCOLARI",
        "NOMCAR_C",
        "ALFABET",
        "ESCOACUM",
        "ENT_PAIS_RES_5A",
        "MUN_RES_5A",
        "CAUSA_MIG_V",
        "SITUA_CONYUGAL",
        "IDENT_PAREJA",
        "CONACT",
        "OCUPACION_C",
        "SITTRA",
        "AGUINALDO",
        "VACACIONES",
        "SERVICIO_MEDICO",
        "UTILIDADES",
        "INCAP_SUELDO",
        "SAR_AFORE",
        "CREDITO_VIVIENDA",
        "ACTIVIDADES_C",
        "MUN_TRAB",
        "ENT_PAIS_TRAB",
        "TIE_TRASLADO_TRAB",
        "MED_TRASLADO_TRAB1",
        "MED_TRASLADO_TRAB2",
        "MED_TRASLADO_TRAB3",
        "HIJOS_NAC_VIVOS",
        "HIJOS_FALLECIDOS",
        "HIJOS_SOBREVIV",
        "FECHA_NAC_M",
        "FECHA_NAC_A",
        "SOBREVIVENCIA",
        "IDENT_HIJO",
        "EDAD_MORIR_D",
        "EDAD_MORIR_M",
        "EDAD_MORIR_A",
        "EDAD_MORIR_TD",
        "TAMLOC",
    ]
    for col in cols:
        cat_map = expand_cat_map(variables[col]["Categorías"])
        df[col] = df[col].fillna(-1).map(cat_map)

    # Health services are dummied, given they are not mutually exclusive
    df = pd.concat([df, dhsersal_create_dummies(df)], axis=1)
    # Med traslado are dummied as well
    df = pd.concat([df, med_traslado_esc_create_dummies(df)], axis=1)
    df = pd.concat([df, med_traslado_trab_create_dummies(df)], axis=1)
    # Education level needs aggregation
    df["EDUC"] = get_educ_col(df)

    return df


# ---------------------------------------------------------------------------
# Schema (lazy — only built on first load)
# ---------------------------------------------------------------------------

_col_ident_cat = pa.Column(
    pd.CategoricalDtype(
        [
            "Vive en esta vivienda",
            "Vive en otra vivienda",
            "Ya falleció",
            "No sabe",
            "No especificado",
        ]
    )
)


@functools.cache
def _build_schema() -> pa.DataFrameSchema:
    variables = variables_personas()
    return pa.DataFrameSchema(
        {
            # Identificación geográfica
            "ENT": pa.Column(int, pa.Check.between(1, 32)),
            "MUN": pa.Column(int, pa.Check.between(1, 570)),
            "LOC50K": pa.Column(int, pa.Check.between(0, 9999)),
            # Diseño Muestral
            "COBERTURA": pa.Column(
                pd.CategoricalDtype(variables["COBERTURA"]["Categorías"].values()),
            ),
            "ESTRATO": pa.Column(str),
            "UPM": pa.Column(int),
            "FACTOR": pa.Column(int),
            # Clase de vivienda particular
            "CLAVIVP": pa.Column(
                pd.CategoricalDtype(variables["CLAVIVP"]["Categorías"].values()),
            ),
            # Lista de personas y datos generales
            "NUMPER": pa.Column(int, pa.Check.between(1, 54)),
            "SEXO": pa.Column(
                pd.CategoricalDtype(variables["SEXO"]["Categorías"].values())
            ),
            "EDAD": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 130),
                parsers=pa.Parser(lambda s: s.replace(999, pd.NA)),
                nullable=True,
            ),
            "EDAD_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "0-2",
                        "3-4",
                        "5",
                        "6-7",
                        "8-11",
                        "12-14",
                        "15-17",
                        "18-24",
                        "25-49",
                        "50-59",
                        "60-64",
                        "65-130",
                        "No especificado",
                    ],
                    ordered=True,
                )
            ),
            "PARENTESCO": pa.Column(
                pd.CategoricalDtype(variables["PARENTESCO"]["Categorías"].values()),
            ),
            # Características de las personas
            "IDENT_MADRE": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["IDENT_MADRE"]["Categorías"]).values()
                ),
            ),
            "IDENT_MADRE_CAT": _col_ident_cat,
            "IDENT_PADRE": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["IDENT_PADRE"]["Categorías"]).values()
                ),
            ),
            "IDENT_PADRE_CAT": _col_ident_cat,
            "ENT_PAIS_NAC": pa.Column(
                int,
                pa.Check(
                    lambda s: (
                        ((s > 0) & (s < 33))
                        | ((s > 99) & (s < 536))
                        | ((s > 996) & (s < 1000))
                    )
                ),
            ),
            "ENT_PAIS_NAC_CAT": pa.Column(
                pd.CategoricalDtype(["EstaEnt", "OtraEnt", "OtroPais", "No especificado"]),
            ),
            "NACIONALIDAD": pa.Column(
                pd.CategoricalDtype(variables["NACIONALIDAD"]["Categorías"].values()),
            ),
            "SERSALUD": pa.Column(
                pd.CategoricalDtype(variables["SERSALUD"]["Categorías"].values()),
            ),
            "AFRODES": pa.Column(
                pd.CategoricalDtype(variables["AFRODES"]["Categorías"].values()),
            ),
            "REGIS_NAC": pa.Column(
                pd.CategoricalDtype(variables["REGIS_NAC"]["Categorías"].values()),
            ),
            "DHSERSAL1": pa.Column(
                pd.CategoricalDtype(variables["DHSERSAL1"]["Categorías"].values()),
            ),
            "DHSERSAL2": pa.Column(
                pd.CategoricalDtype(variables["DHSERSAL1"]["Categorías"].values()),
            ),
            "DHSERSAL_IMSS": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_ISSSTE": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_ISSSTE_E": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_P_D_M": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_Popular_NGenración_SBienestar": pa.Column(
                pd.CategoricalDtype([0, 1])
            ),
            "DHSERSAL_IMSS_Prospera/Bienestar": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_Privado": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_Otro": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_No afiliado": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_PUB": pa.Column(pd.CategoricalDtype([0, 1])),
            "DHSERSAL_AFIL": pa.Column(pd.CategoricalDtype([0, 1])),
            "RELIGION": pa.Column(
                pd.CategoricalDtype(variables["RELIGION"]["Categorías"].values()),
            ),
            "RELIGION_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "Católica",
                        "Protestante/cristiano evangélico",
                        "Otros credos",
                        "Sin religión / Sin adscripción religiosa",
                        "No especificado",
                    ]
                ),
            ),
            "DIS_VER": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_OIR": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_CAMINAR": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_RECORDAR": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_BANARSE": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_HABLAR": pa.Column(
                pd.CategoricalDtype(variables["DIS_VER"]["Categorías"].values()),
            ),
            "DIS_MENTAL": pa.Column(
                pd.CategoricalDtype(variables["DIS_MENTAL"]["Categorías"].values()),
            ),
            "DIS_CON": pa.Column(pd.CategoricalDtype(["Sí", "No", "No especificado"])),
            "DIS_LIMI": pa.Column(pd.CategoricalDtype(["Sí", "No", "No especificado"])),
            "CAU_VER": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_OIR": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_CAMINAR": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_RECORDAR": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_BANARSE": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_HABLAR": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "CAU_MENTAL": pa.Column(
                pd.CategoricalDtype(variables["CAU_VER"]["Categorías"].values()),
            ),
            "HLENGUA": pa.Column(
                pd.CategoricalDtype(variables["HLENGUA"]["Categorías"].values()),
            ),
            "QDIALECT_INALI": pa.Column(
                pd.CategoricalDtype(
                    set(variables["QDIALECT_INALI"]["Categorías"].values())
                ),
            ),
            "HESPANOL": pa.Column(
                pd.CategoricalDtype(variables["HESPANOL"]["Categorías"].values()),
            ),
            "ELENGUA": pa.Column(
                pd.CategoricalDtype(variables["ELENGUA"]["Categorías"].values()),
            ),
            "PERTE_INDIGENA": pa.Column(
                pd.CategoricalDtype(variables["PERTE_INDIGENA"]["Categorías"].values()),
            ),
            "ASISTEN": pa.Column(
                pd.CategoricalDtype(variables["ASISTEN"]["Categorías"].values()),
            ),
            "MUN_ASI": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["MUN_ASI"]["Categorías"]).values()
                ),
            ),
            "ENT_PAIS_ASI": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["ENT_PAIS_ASI"]["Categorías"]).values()
                ),
            ),
            "TIE_TRASLADO_ESCU": pa.Column(
                pd.CategoricalDtype(
                    variables["TIE_TRASLADO_ESCU"]["Categorías"].values(), ordered=True
                ),
            ),
            "MED_TRASLADO_ESC1": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_ESC1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_ESC2": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_ESC1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_ESC3": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_ESC1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_ESC_.+": pa.Column(pd.CategoricalDtype([0, 1]), regex=True),
            "NIVACAD": pa.Column(
                pd.CategoricalDtype(
                    variables["NIVACAD"]["Categorías"].values(),
                    ordered=True,
                )
            ),
            "ESCOLARI": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["ESCOLARI"]["Categorías"]).values(),
                    ordered=True,
                ),
            ),
            "EDUC": pa.Column(
                pd.CategoricalDtype(
                    [
                        "Sin Educación",
                        "Primaria_incom",
                        "Primaria_com",
                        "Secundaria_incom",
                        "Secundaria_com",
                        "Posbásica",
                        "No especificado",
                        "Blanco por pase",
                    ],
                    ordered=True,
                )
            ),
            "NOMCAR_C": pa.Column(
                pd.CategoricalDtype(variables["NOMCAR_C"]["Categorías"].values())
            ),
            "ALFABET": pa.Column(
                pd.CategoricalDtype(variables["ALFABET"]["Categorías"].values())
            ),
            "ESCOACUM": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["ESCOACUM"]["Categorías"]).values()
                )
            ),
            "ENT_PAIS_RES_5A": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["ENT_PAIS_RES_5A"]["Categorías"]).values()
                )
            ),
            "ENT_PAIS_RES_CAT": pa.Column(
                pd.CategoricalDtype(
                    ["EstaEnt", "OtraEnt", "OtroPais", "No especificado", "Blanco por pase"]
                )
            ),
            "MUN_RES_5A": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["MUN_RES_5A"]["Categorías"]).values()
                )
            ),
            "CAUSA_MIG_V": pa.Column(
                pd.CategoricalDtype(variables["CAUSA_MIG_V"]["Categorías"].values())
            ),
            "SITUA_CONYUGAL": pa.Column(
                pd.CategoricalDtype(variables["SITUA_CONYUGAL"]["Categorías"].values())
            ),
            "SITUA_CONYUGAL_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "casado",
                        "separado",
                        "soltero",
                        "No especificado",
                        "Blanco por pase",
                    ]
                )
            ),
            "IDENT_PAREJA": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["IDENT_PAREJA"]["Categorías"]).values()
                )
            ),
            "IDENT_PAREJA_CAT": pa.Column(
                pd.CategoricalDtype(["Sí", "No", "No especificado", "Blanco por pase"])
            ),
            "CONACT": pa.Column(
                pd.CategoricalDtype(variables["CONACT"]["Categorías"].values())
            ),
            "CONACT_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "Trabaja",
                        "Buscó trabajo",
                        "No trabaja",
                        "No especificado",
                        "Blanco por pase",
                    ]
                )
            ),
            "OCUPACION_C": pa.Column(
                pd.CategoricalDtype(variables["OCUPACION_C"]["Categorías"].values())
            ),
            "OCUPACION_C_COARSE": pa.Column(
                pd.CategoricalDtype(variables["OCUPACION_C_COARSE"]["Categorías"].values())
            ),
            "SITTRA": pa.Column(
                pd.CategoricalDtype(variables["SITTRA"]["Categorías"].values())
            ),
            "AGUINALDO": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "VACACIONES": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "SERVICIO_MEDICO": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "UTILIDADES": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "INCAP_SUELDO": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "SAR_AFORE": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "CREDITO_VIVIENDA": pa.Column(
                pd.CategoricalDtype(variables["AGUINALDO"]["Categorías"].values())
            ),
            "INGTRMEN": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 999998),
                parsers=pa.Parser(lambda s: s.replace(999999, pd.NA)),
                nullable=True,
            ),
            "INGTRMEN_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "No recibe ingresos",
                        "1-999",
                        "1,000-4,999",
                        "5,000-9,999",
                        "10,000-19,999",
                        "20,000-39,999",
                        "40,000-79,999",
                        "80,000-149,999",
                        "150,000yMas",
                        "No especificado",
                        "Blanco por pase",
                    ],
                    ordered=True,
                )
            ),
            "HORTRA": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 140),
                parsers=pa.Parser(lambda s: s.replace(999, pd.NA)),
                nullable=True,
            ),
            "HORTRA_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "0-5",
                        "6-10",
                        "11-20",
                        "21-40",
                        "41-48",
                        "49-56",
                        "57-60",
                        "61-80",
                        "81YMAS",
                        "No especificado",
                        "Blanco por pase",
                    ],
                    ordered=True,
                )
            ),
            "ACTIVIDADES_C": pa.Column(
                pd.CategoricalDtype(variables["ACTIVIDADES_C"]["Categorías"].values())
            ),
            "ACTIVIDADES_C_COARSE": pa.Column(
                pd.CategoricalDtype(
                    sorted(
                        list(set(variables["ACTIVIDADES_C_COARSE"]["Categorías"].values()))
                    )
                )
            ),
            "MUN_TRAB": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["MUN_TRAB"]["Categorías"]).values()
                ),
            ),
            "ENT_PAIS_TRAB": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["ENT_PAIS_TRAB"]["Categorías"]).values()
                ),
            ),
            "TIE_TRASLADO_TRAB": pa.Column(
                pd.CategoricalDtype(
                    variables["TIE_TRASLADO_TRAB"]["Categorías"].values(), ordered=True
                ),
            ),
            "MED_TRASLADO_TRAB1": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_TRAB1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_TRAB2": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_TRAB1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_TRAB3": pa.Column(
                pd.CategoricalDtype(variables["MED_TRASLADO_TRAB1"]["Categorías"].values()),
            ),
            "MED_TRASLADO_TRAB_.+": pa.Column(pd.CategoricalDtype([0, 1]), regex=True),
            "HIJOS_NAC_VIVOS": pa.Column(
                pd.CategoricalDtype(
                    set(expand_cat_map(variables["HIJOS_NAC_VIVOS"]["Categorías"]).values())
                ),
            ),
            "HIJOS_FALLECIDOS": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["HIJOS_FALLECIDOS"]["Categorías"]).values()
                ),
            ),
            "HIJOS_SOBREVIV": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["HIJOS_SOBREVIV"]["Categorías"]).values()
                ),
            ),
            "FECHA_NAC_M": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["FECHA_NAC_M"]["Categorías"]).values()
                ),
            ),
            "FECHA_NAC_A": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["FECHA_NAC_A"]["Categorías"]).values()
                ),
            ),
            "SOBREVIVENCIA": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["SOBREVIVENCIA"]["Categorías"]).values()
                ),
            ),
            "IDENT_HIJO": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["IDENT_HIJO"]["Categorías"]).values()
                ),
            ),
            "IDENT_HIJO_CAT": pa.Column(
                pd.CategoricalDtype(
                    [
                        "Esta vivienda",
                        "En otra vivienda",
                        "No especificado",
                        "Blanco por pase",
                    ]
                ),
            ),
            "EDAD_MORIR_D": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["EDAD_MORIR_D"]["Categorías"]).values()
                ),
            ),
            "EDAD_MORIR_M": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["EDAD_MORIR_M"]["Categorías"]).values()
                ),
            ),
            "EDAD_MORIR_A": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["EDAD_MORIR_A"]["Categorías"]).values()
                ),
            ),
            "EDAD_MORIR_TD": pa.Column(
                pd.CategoricalDtype(
                    expand_cat_map(variables["EDAD_MORIR_TD"]["Categorías"]).values()
                ),
            ),
            "TAMLOC": pa.Column(
                pd.CategoricalDtype(variables["TAMLOC"]["Categorías"].values()),
            ),
        },
        strict=True,
        coerce=True,
        index=pa.MultiIndex(
            [
                pa.Index(int, name="ID_VIV", unique=True, coerce=True),
                pa.Index(int, name="ID_PERSONA", unique=True, coerce=True),
            ],
            unique=True,
            ordered=True,
            coerce=True,
            strict=True,
        ),
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_extended_personas(
    survey_path: Path | None = None,
    *,
    state: int | None = None,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Load and validate the extended questionnaire person table.

    Two calling conventions:

    Explicit path::

        load_extended_personas(Path("Personas14.parquet"))

    State code (resolves from the XDG data directory)::

        load_extended_personas(state=14)
        load_extended_personas(state=14, data_dir=Path("~/my-data"))
    """
    if state is not None:
        from mxcensus.data._paths import get_data_dir
        from mxcensus.data._catalog import STATE_ABBR

        base = data_dir or get_data_dir()
        abbr = STATE_ABBR[state]
        folder = f"Censo2020_CA_{abbr}_csv"
        survey_path = base / "cuestionario_ampliado" / folder / f"Personas{state}.parquet"
    if survey_path is None:
        raise ValueError("Provide either survey_path or state=")

    return (
        pd.read_parquet(survey_path)
        .set_index(["ID_VIV", "ID_PERSONA"])
        .sort_index()
        .pipe(preprocessor)
        .pipe(_build_schema())
    )
