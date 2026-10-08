"""mxcensus — loaders for INEGI open data: censuses and intercensal surveys, Marco
Geoestadístico, DENUE, ENOE and ENIGH."""
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
    variables_enoe_labels,
)
from mxcensus.enigh import (
    load_enigh,
    load_enigh_hogares,
    load_enigh_viviendas,
    load_enigh_personas,
    load_enigh_survey,
    variables_enigh_labels,
)
from mxcensus.cpv import (
    load_cpv,
    load_cpv_viviendas,
    load_cpv_personas,
    load_cpv_migrantes,
    load_cpv_survey,
    variables_cpv_labels,
)
from mxcensus.cpv_aggregates import (
    load_cpv_estimaciones,
    load_cpv_iter,
    load_cpv_ageb,
    load_cpv_census,
)
from mxcensus.mg import load_mg
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
    variables_cpv,
    variables_cpv_core,
    cpv_schema_map,
    cpv_iter_crosswalk,
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
    "variables_enoe_labels",
    # ENIGH (household income/expenditure survey, biennial, national)
    "load_enigh",
    "load_enigh_hogares",
    "load_enigh_viviendas",
    "load_enigh_personas",
    "load_enigh_survey",
    "variables_enigh_labels",
    # CPV family (censos, conteos y encuestas intercensales; EIC 2025 so far)
    "load_cpv",
    "load_cpv_viviendas",
    "load_cpv_personas",
    "load_cpv_migrantes",
    "load_cpv_survey",
    "load_cpv_estimaciones",
    "load_cpv_iter",
    "load_cpv_ageb",
    "load_cpv_census",
    "variables_cpv_labels",
    # Marco Geoestadístico (geometry, per state; 2020 and EIC 2025 frames)
    "load_mg",
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
    "variables_cpv",
    "variables_cpv_core",
    "cpv_schema_map",
    "cpv_iter_crosswalk",
    # Utilities
    "expand_cat_map",
    "get_cats_from_excel",
    "get_vars_from_indicator_csv",
    # Data download subpackage
    "data",
]
