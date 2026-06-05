"""mxcensus — Mexico Census 2020 (CPV 2020) data loader and preprocessor."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mxcensus")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"

from mxcensus.aggregate import (
    load_census,
    load_iter,
    load_resargebub,
    load_mg_census,
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
from mxcensus.denue import load_denue
from mxcensus.crosstabs import create_cont_table, get_tables_dict
from mxcensus.utils import expand_cat_map, get_cats_from_excel, get_vars_from_indicator_csv
from mxcensus._resources import (
    constraints_personas,
    constraints_viviendas,
    variables_personas,
    variables_viviendas,
    variables_iter,
    variables_resargebub,
    variables_denue,
    denue_schema_map,
)
from mxcensus import data

__all__ = [
    "__version__",
    # Aggregate census
    "load_census",
    "load_iter",
    "load_resargebub",
    "load_mg_census",
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
    # DENUE (economic units, multi-temporal)
    "load_denue",
    # Crosstabs / constraints
    "create_cont_table",
    "get_tables_dict",
    "constraints_personas",
    "constraints_viviendas",
    # Variable dictionaries (metadata)
    "variables_personas",
    "variables_viviendas",
    "variables_iter",
    "variables_resargebub",
    "variables_denue",
    "denue_schema_map",
    # Utilities
    "expand_cat_map",
    "get_cats_from_excel",
    "get_vars_from_indicator_csv",
    # Data download subpackage
    "data",
]
