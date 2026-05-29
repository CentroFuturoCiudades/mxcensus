"""On-demand data download and path resolution for INEGI Census 2020."""
from mxcensus.data._paths import get_data_dir
from mxcensus.data._download import download
from mxcensus.data._catalog import (
    STATE_ABBR,
    CATALOG_VERIFIED_DATE,
    iter_entry,
    resargebub_entry,
    cuestionario_ampliado_entry,
)

__all__ = [
    "download",
    "get_data_dir",
    "STATE_ABBR",
    "CATALOG_VERIFIED_DATE",
    "iter_entry",
    "resargebub_entry",
    "cuestionario_ampliado_entry",
]
