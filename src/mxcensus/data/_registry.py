"""Global Pooch registry for the mxcensus parquet mirror.

No network traffic occurs at import time — files are only downloaded on the
first ``POOCH.fetch()`` call for each file.
"""
from __future__ import annotations

from importlib import resources

import pooch

from ._paths import get_pooch_cache_dir

_DATA_RELEASE_TAG = "data-v0.1.0"
_BASE_URL = f"https://github.com/OWNER/mxcensus/releases/download/{_DATA_RELEASE_TAG}/"

POOCH = pooch.create(
    path=get_pooch_cache_dir(),
    base_url=_BASE_URL,
    registry={},
    env="MXCENSUS_CACHE_DIR",
)

_reg = resources.files("mxcensus.data") / "registry.txt"
with resources.as_file(_reg) as _p:
    POOCH.load_registry(_p)
