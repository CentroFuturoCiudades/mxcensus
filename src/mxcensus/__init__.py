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
from mxcensus.enoe import (
    load_enoe,
    load_enoe_persons,
    load_enoe_viviendas,
    load_enoe_hogares,
    load_enoe_survey,
)
from mxcensus.enigh import (
    load_enigh,
    load_enigh_hogares,
    load_enigh_viviendas,
    load_enigh_personas,
    load_enigh_survey,
)
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
    variables_enoe,
    variables_enoe_core,
    enoe_schema_map,
    variables_enigh,
    variables_enigh_core,
    enigh_schema_map,
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
    # ENOE (labor-force survey, multi-temporal, national)
    "load_enoe",
    "load_enoe_persons",
    "load_enoe_viviendas",
    "load_enoe_hogares",
    "load_enoe_survey",
    # ENIGH (household income/expenditure survey, biennial, national)
    "load_enigh",
    "load_enigh_hogares",
    "load_enigh_viviendas",
    "load_enigh_personas",
    "load_enigh_survey",
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
    "variables_enoe",
    "variables_enoe_core",
    "enoe_schema_map",
    "variables_enigh",
    "variables_enigh_core",
    "enigh_schema_map",
    # Utilities
    "expand_cat_map",
    "get_cats_from_excel",
    "get_vars_from_indicator_csv",
    # Data download subpackage
    "data",
]
