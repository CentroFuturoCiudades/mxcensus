"""Extended questionnaire household table: preprocessing, schema, and loader."""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from mxcensus._resources import variables_viviendas
from mxcensus.utils import expand_cat_map

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def financiamiento_create_dummies(df):
    """Combine up to three financing-source fields into binary dummy columns (capped at 1)."""
    df1 = pd.get_dummies(df.FINANCIAMIENTO1, prefix="FINANCIAMIENTO")
    df2 = pd.get_dummies(df.FINANCIAMIENTO2, prefix="FINANCIAMIENTO")
    df3 = pd.get_dummies(df.FINANCIAMIENTO3, prefix="FINANCIAMIENTO")
    df_agg = (
        df1.add(df2, fill_value=0)
        .add(df3, fill_value=0)
        .astype(int)
        .replace({2: 1, 3: 1})
    )
    return df_agg


def preprocessor(df):
    """Apply all derived-column and category-mapping transformations to the raw viviendas DataFrame."""
    variables = variables_viviendas()
    df = df.copy()

    # Derive new columns
    new_cols = ["CLAVIVP_CAT", "CUADORM_CAT", "TOTCUART_CAT", "DRENAJE_CAT"]
    for col in new_cols:
        parent = variables[col]["Original"]
        cat_map = expand_cat_map(variables[col]["Categorías"])
        df[col] = df[parent].fillna(-1).map(cat_map)
    df["INGTRHOG_CAT"] = pd.cut(
        df.INGTRHOG.fillna(2e6),
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

    # Category mappings
    cols = [
        "COBERTURA",
        "CLAVIVP",
        "PAREDES",
        "TECHOS",
        "PISOS",
        "COCINA",
        "CUADORM",
        "TOTCUART",
        "LUG_COC",
        "COMBUSTIBLE",
        "ESTUFA",
        "ELECTRICIDAD",
        "AGUA_ENTUBADA",
        "ABA_AGUA_ENTU",
        "ABA_AGUA_NO_ENTU",
        "TINACO",
        "CISTERNA",
        "BOMBA_AGUA",
        "REGADERA",
        "BOILER",
        "CALENTADOR_SOLAR",
        "AIRE_ACON",
        "PANEL_SOLAR",
        "SERSAN",
        "CONAGUA",
        "USOEXC",
        "DRENAJE",
        "SEPARACION1",
        "SEPARACION2",
        "SEPARACION3",
        "SEPARACION4",
        "DESTINO_BAS",
        "REFRIGERADOR",
        "LAVADORA",
        "HORNO",
        "AUTOPROP",
        "MOTOCICLETA",
        "BICICLETA",
        "RADIO",
        "TELEVISOR",
        "COMPUTADORA",
        "TELEFONO",
        "CELULAR",
        "INTERNET",
        "SERV_TV_PAGA",
        "SERV_PEL_PAGA",
        "CON_VJUEGOS",
        "TENENCIA",
        "ESCRITURAS",
        "FORMA_ADQUI",
        "FINANCIAMIENTO1",
        "FINANCIAMIENTO2",
        "FINANCIAMIENTO3",
        "DEUDA",
        "DUE1_NUM",
        "DUE2_NUM",
        "MCONMIG",
        "MNUMPERS",
        "INGR_PEROTROPAIS",
        "INGR_PERDENTPAIS",
        "INGR_AYUGOB",
        "INGR_JUBPEN",
        "ALIMENTACION",
        "ALIM_ADL1",
        "ALIM_ADL2",
        "ING_ALIM_ADL1",
        "ING_ALIM_ADL2",
        "ING_ALIM_ADL3",
        "TIPOHOG",
        "JEFE_SEXO",
        "TAMLOC",
    ]
    for col in cols:
        cat_map = expand_cat_map(variables[col]["Categorías"])
        df[col] = df[col].fillna(-1).map(cat_map)

    df = pd.concat([df, financiamiento_create_dummies(df)], axis=1)

    return df


# ---------------------------------------------------------------------------
# Schema (lazy — only built on first load)
# ---------------------------------------------------------------------------

_col_si_no_bpp = pa.Column(
    pd.CategoricalDtype(["Sí", "No", "No especificado", "Blanco por pase"])
)
_col_si_no = pa.Column(pd.CategoricalDtype(["Sí", "No", "No especificado"]))


@functools.cache
def _build_schema() -> pa.DataFrameSchema:
    variables = variables_viviendas()
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
            "CLAVIVP_CAT": pa.Column(
                pd.CategoricalDtype(["Vivienda", "Otro"]),
            ),
            # Características de la vivienda
            "PAREDES": pa.Column(
                pd.CategoricalDtype(variables["PAREDES"]["Categorías"].values()),
            ),
            "TECHOS": pa.Column(
                pd.CategoricalDtype(variables["TECHOS"]["Categorías"].values()),
            ),
            "PISOS": pa.Column(
                pd.CategoricalDtype(variables["PISOS"]["Categorías"].values()),
            ),
            "COCINA": pa.Column(
                pd.CategoricalDtype(variables["COCINA"]["Categorías"].values()),
            ),
            "CUADORM": pa.Column(
                pd.CategoricalDtype(
                    list(expand_cat_map(variables["CUADORM"]["Categorías"]).values())
                ),
            ),
            "CUADORM_CAT": pa.Column(
                pd.CategoricalDtype(variables["CUADORM_CAT"]["Categorías"].values()),
            ),
            "TOTCUART": pa.Column(
                pd.CategoricalDtype(
                    list(expand_cat_map(variables["TOTCUART"]["Categorías"]).values())
                ),
            ),
            "TOTCUART_CAT": pa.Column(
                pd.CategoricalDtype(variables["TOTCUART_CAT"]["Categorías"].values()),
            ),
            "LUG_COC": pa.Column(
                pd.CategoricalDtype(variables["LUG_COC"]["Categorías"].values()),
            ),
            "COMBUSTIBLE": pa.Column(
                pd.CategoricalDtype(variables["COMBUSTIBLE"]["Categorías"].values()),
            ),
            "ESTUFA": pa.Column(
                pd.CategoricalDtype(variables["ESTUFA"]["Categorías"].values()),
            ),
            "ELECTRICIDAD": pa.Column(
                pd.CategoricalDtype(variables["ELECTRICIDAD"]["Categorías"].values()),
            ),
            "FOCOS": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 998),
                parsers=pa.Parser(lambda s: s.replace(999, pd.NA)),
                nullable=True,
            ),
            "FOCOS_AHORRA": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 998),
                parsers=pa.Parser(lambda s: s.replace(999, pd.NA)),
                nullable=True,
            ),
            "AGUA_ENTUBADA": pa.Column(
                pd.CategoricalDtype(variables["AGUA_ENTUBADA"]["Categorías"].values()),
            ),
            "ABA_AGUA_ENTU": pa.Column(
                pd.CategoricalDtype(variables["ABA_AGUA_ENTU"]["Categorías"].values()),
            ),
            "ABA_AGUA_NO_ENTU": pa.Column(
                pd.CategoricalDtype(
                    variables["ABA_AGUA_NO_ENTU"]["Categorías"].values()
                ),
            ),
            "TINACO": _col_si_no_bpp,
            "CISTERNA": _col_si_no_bpp,
            "BOMBA_AGUA": _col_si_no_bpp,
            "REGADERA": _col_si_no_bpp,
            "BOILER": _col_si_no_bpp,
            "CALENTADOR_SOLAR": _col_si_no_bpp,
            "AIRE_ACON": _col_si_no_bpp,
            "PANEL_SOLAR": _col_si_no_bpp,
            "SERSAN": pa.Column(
                pd.CategoricalDtype(variables["SERSAN"]["Categorías"].values()),
            ),
            "CONAGUA": pa.Column(
                pd.CategoricalDtype(variables["CONAGUA"]["Categorías"].values()),
            ),
            "USOEXC": pa.Column(
                pd.CategoricalDtype(variables["USOEXC"]["Categorías"].values()),
            ),
            "DRENAJE": pa.Column(
                pd.CategoricalDtype(variables["DRENAJE"]["Categorías"].values()),
            ),
            "DRENAJE_CAT": _col_si_no_bpp,
            "SEPARACION1": _col_si_no_bpp,
            "SEPARACION2": _col_si_no_bpp,
            "SEPARACION3": _col_si_no_bpp,
            "SEPARACION4": _col_si_no_bpp,
            "DESTINO_BAS": pa.Column(
                pd.CategoricalDtype(variables["DESTINO_BAS"]["Categorías"].values()),
            ),
            "REFRIGERADOR": _col_si_no_bpp,
            "LAVADORA": _col_si_no_bpp,
            "HORNO": _col_si_no_bpp,
            "AUTOPROP": _col_si_no_bpp,
            "MOTOCICLETA": _col_si_no_bpp,
            "BICICLETA": _col_si_no_bpp,
            "RADIO": _col_si_no_bpp,
            "TELEVISOR": _col_si_no_bpp,
            "COMPUTADORA": _col_si_no_bpp,
            "TELEFONO": _col_si_no_bpp,
            "CELULAR": _col_si_no_bpp,
            "INTERNET": _col_si_no_bpp,
            "SERV_TV_PAGA": _col_si_no_bpp,
            "SERV_PEL_PAGA": _col_si_no_bpp,
            "CON_VJUEGOS": _col_si_no_bpp,
            "TENENCIA": pa.Column(
                pd.CategoricalDtype(variables["TENENCIA"]["Categorías"].values()),
            ),
            "ESCRITURAS": pa.Column(
                pd.CategoricalDtype(variables["ESCRITURAS"]["Categorías"].values()),
            ),
            "FORMA_ADQUI": pa.Column(
                pd.CategoricalDtype(variables["FORMA_ADQUI"]["Categorías"].values()),
            ),
            "FINANCIAMIENTO1": pa.Column(
                pd.CategoricalDtype(
                    variables["FINANCIAMIENTO1"]["Categorías"].values()
                ),
            ),
            "FINANCIAMIENTO2": pa.Column(
                pd.CategoricalDtype(
                    variables["FINANCIAMIENTO1"]["Categorías"].values()
                ),
            ),
            "FINANCIAMIENTO3": pa.Column(
                pd.CategoricalDtype(
                    variables["FINANCIAMIENTO1"]["Categorías"].values()
                ),
            ),
            "FINANCIAMIENTO_.+": pa.Column(pd.CategoricalDtype([0, 1]), regex=True),
            "DEUDA": pa.Column(
                pd.CategoricalDtype(variables["DEUDA"]["Categorías"].values()),
            ),
            "NUMPERS": pa.Column(int, pa.Check.between(1, 999)),
            "DUE1_NUM": pa.Column(
                pd.CategoricalDtype(
                    list(expand_cat_map(variables["DUE1_NUM"]["Categorías"]).values())
                ),
            ),
            "DUE2_NUM": pa.Column(
                pd.CategoricalDtype(
                    list(expand_cat_map(variables["DUE2_NUM"]["Categorías"]).values())
                ),
            ),
            "MCONMIG": pa.Column(
                pd.CategoricalDtype(variables["MCONMIG"]["Categorías"].values()),
            ),
            "MNUMPERS": pa.Column(
                pd.CategoricalDtype(
                    list(expand_cat_map(variables["MNUMPERS"]["Categorías"]).values())
                ),
            ),
            "INGR_PEROTROPAIS": _col_si_no,
            "INGR_PERDENTPAIS": _col_si_no,
            "INGR_AYUGOB": _col_si_no,
            "INGR_JUBPEN": _col_si_no,
            "ALIMENTACION": _col_si_no,
            "ALIM_ADL1": _col_si_no,
            "ALIM_ADL2": _col_si_no,
            "ING_ALIM_ADL1": _col_si_no,
            "ING_ALIM_ADL2": _col_si_no,
            "ING_ALIM_ADL3": _col_si_no,
            "TIPOHOG": pa.Column(
                pd.CategoricalDtype(variables["TIPOHOG"]["Categorías"].values()),
            ),
            "INGTRHOG": pa.Column(
                "Int64",
                checks=pa.Check.between(0, 999998),
                parsers=pa.Parser(lambda s: s.replace(999999, pd.NA)),
                nullable=True,
            ),
            "INGTRHOG_CAT": pa.Column(
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
            "JEFE_SEXO": pa.Column(
                pd.CategoricalDtype(variables["JEFE_SEXO"]["Categorías"].values())
            ),
            "JEFE_EDAD": pa.Column(
                "Int64",
                parsers=pa.Parser(lambda s: s.replace(999, pd.NA)),
                nullable=True,
            ),
            "TAMLOC": pa.Column(
                pd.CategoricalDtype(variables["TAMLOC"]["Categorías"].values())
            ),
        },
        strict=False,
        coerce=True,
        index=pa.Index(int, name="ID_VIV", unique=True, coerce=True),
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_extended_viviendas(
    survey_path: Path | None = None,
    *,
    state: int | None = None,
) -> pd.DataFrame:
    """Load and validate the extended questionnaire household table.

    Two calling conventions:

    Explicit path (parquet from the mirror or your own file)::

        load_extended_viviendas(Path("viviendas_14.parquet"))

    State code — fetches the raw parquet from the mxcensus mirror via Pooch::

        load_extended_viviendas(state=14)
    """
    if state is not None:
        from mxcensus.data._catalog import STATE_CODE_FMT
        from mxcensus.data._registry import POOCH

        code = STATE_CODE_FMT(state)
        survey_path = Path(POOCH.fetch(f"viviendas_{code}.parquet"))

    if survey_path is None:
        raise ValueError("Provide either survey_path or state=")

    return (
        pd.read_parquet(survey_path)
        .set_index("ID_VIV")
        .sort_index()
        .pipe(preprocessor)
        .pipe(_build_schema())
    )
