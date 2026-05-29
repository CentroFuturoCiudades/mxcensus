"""mxcensus — Mexico Census 2020 (CPV 2020) data loader and preprocessor."""
from mxcensus.aggregate import (
    load_census,
    load_iter,
    load_resargebub,
    merge_loc_agebs,
    merge_mg_census,
    mg_agebs_ur,
    add_collective_cols,
    add_derived_cols,
    impute_collective,
    impute_zeros_univariate,
    sanity_checks,
)
from mxcensus.extended_personas import load_extended_personas
from mxcensus.extended_viviendas import load_extended_viviendas
from mxcensus.crosstabs import create_cont_table, get_tables_dict
from mxcensus.utils import expand_cat_map, get_cats_from_excel
from mxcensus._resources import constraints_personas, constraints_viviendas
from mxcensus import data

__all__ = [
    # Aggregate census
    "load_census",
    "load_iter",
    "load_resargebub",
    "merge_loc_agebs",
    "merge_mg_census",
    "mg_agebs_ur",
    "add_collective_cols",
    "add_derived_cols",
    "impute_collective",
    "impute_zeros_univariate",
    "sanity_checks",
    # Extended questionnaire
    "load_extended_personas",
    "load_extended_viviendas",
    # Crosstabs / constraints
    "create_cont_table",
    "get_tables_dict",
    "constraints_personas",
    "constraints_viviendas",
    # Utilities
    "expand_cat_map",
    "get_cats_from_excel",
    # Data download subpackage
    "data",
]
