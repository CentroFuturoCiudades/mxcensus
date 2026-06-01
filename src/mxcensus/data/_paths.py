"""Platform-appropriate directory resolution via platformdirs."""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

_APP = "mxcensus"


def get_data_dir() -> Path:
    """Return the mxcensus user-data directory.

    Override with ``$MXCENSUS_DATA_DIR``.
    """
    if env := os.environ.get("MXCENSUS_DATA_DIR"):
        return Path(env).expanduser().resolve()
    return Path(user_data_dir(_APP))


def get_pooch_cache_dir() -> Path:
    """Return the directory where Pooch caches downloaded parquet files.

    Override with ``$MXCENSUS_CACHE_DIR``.
    """
    if env := os.environ.get("MXCENSUS_CACHE_DIR"):
        return Path(env).expanduser().resolve()
    return Path(user_cache_dir(_APP))
