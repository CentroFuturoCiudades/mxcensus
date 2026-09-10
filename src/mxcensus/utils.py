"""Shared utilities for category-map expansion and YAML generation from INEGI data dictionaries."""

from pathlib import Path

import pandas as pd
import yaml


def get_vars_from_indicator_csv(csv_path: Path, opath: Path) -> dict:
    """Parse an INEGI ITER/RESARGEBUB "Relación de indicadores" dictionary CSV to YAML.

    These aggregate datasets ship a ``diccionario_datos_*.csv`` whose columns are
    ``Núm., Indicador, Descripción, Mnemónico, Rangos, Longitud`` after a few title
    rows. The dictionary is national (identical for every state), so a single file
    is generated. Unlike the microdata dictionaries (see ``get_cats_from_excel``),
    these aggregate variables carry no categorical code→label maps, so each entry
    keeps the source's ``Indicador``/``Descripción``/``Rangos``/``Longitud`` fields.
    Returns the dict and writes it (keyed by mnemonic) to ``opath``.
    """
    rows = pd.read_csv(csv_path, header=None, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    header_row = rows.index[rows[0].str.strip().str.startswith("Núm")][0]
    df = pd.read_csv(csv_path, skiprows=header_row, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]

    out: dict = {}
    for _, row in df.iterrows():
        mnemonic = str(row.get("Mnemónico", "")).strip()
        if not mnemonic:
            continue
        out[mnemonic] = {
            field: row.get(field, "").strip()
            for field in ("Indicador", "Descripción", "Rangos", "Longitud")
        }

    with open(opath, "w", encoding="utf-8") as file:
        yaml.dump(out, file, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return out


def expand_cat_map(cat_map: dict) -> dict:
    """Expand range-key entries (e.g. ``"1..5": "label"``) into individual int → label pairs."""
    cat_map_new = {}
    for k, v in cat_map.items():
        if isinstance(k, str) and ".." in k:
            # This is a range, expand
            a, b = map(int, k.split(".."))
            k_list = list(range(a, b + 1))
            if isinstance(v, str) and ".." in v:
                # Value is also a range
                c, d = map(int, v.split(".."))
                v_list = list(range(c, d + 1))
                assert len(k_list) == len(v_list)
                for i, j in zip(k_list, v_list):
                    cat_map_new[i] = j
            else:
                # Just repeat v
                for i in range(a, b + 1):
                    cat_map_new[i] = v
        else:
            # propagate map
            cat_map_new[k] = v
    return cat_map_new


def expand_cat_map_str(cat_map: dict) -> dict[str, str]:
    """String-keyed sibling of :func:`expand_cat_map` for the survey dictionaries.

    ENOE/ENIGH codes are quoted, possibly zero-padded strings (``'01'``), so keys are kept
    as text: a range key ``'01..05'`` expands to ``'01'``…``'05'`` preserving the width of its
    left bound; labels are always ``str``. Non-range keys pass through (stringified).
    """
    out: dict[str, str] = {}
    for k, v in cat_map.items():
        k = str(k)
        if ".." in k:
            a, b = k.split("..", 1)
            if a.strip().lstrip("-").isdigit() and b.strip().lstrip("-").isdigit():
                width = len(a.strip()) if a.strip().startswith("0") else 0
                for i in range(int(a), int(b) + 1):
                    out[str(i).zfill(width)] = str(v)
                continue
        out[k] = str(v)
    return out


def get_cats_from_excel(excel_path: Path, sheet_name: str, opath: Path):
    """Parse an INEGI data-dictionary Excel sheet and write a category YAML file to ``opath``."""
    df_dic = (
        pd.read_excel(
            excel_path,
            skiprows=5,
            sheet_name=sheet_name,
            usecols=[
                "Descripción",
                "Mnemónico",
                "Pregunta y categoría",
                "Rango válido",
            ],
        )
        .dropna(subset="Pregunta y categoría")
        .rename(columns={"Descripción": "Desc"})
        .reset_index(drop=True)
    )

    dic_dic = {}
    for i, (_, row) in enumerate(df_dic.iterrows()):
        varname = row["Mnemónico"]
        if isinstance(varname, str):
            key = varname
            dic_dic[key] = {}
            dic_dic[key]["Descripción"] = row["Desc"]
            dic_dic[key]["Pregunta"] = row["Pregunta y categoría"]
            dic_dic[key]["Categorías"] = {}
        else:
            code = row["Rango válido"]
            if isinstance(code, str) and code.isdigit():
                code = int(code)
            dic_dic[key]["Categorías"][code] = row["Pregunta y categoría"]

    with open(opath, "w") as file:
        yaml.dump(
            dic_dic, file, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
