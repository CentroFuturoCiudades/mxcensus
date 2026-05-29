from pathlib import Path

import pandas as pd
import yaml


def expand_cat_map(cat_map: dict) -> dict:
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


def get_cats_from_excel(excel_path: Path, sheet_name: str, opath: Path) -> Path:
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
