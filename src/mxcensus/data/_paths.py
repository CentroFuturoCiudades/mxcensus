"""XDG-compliant data directory resolution."""
from __future__ import annotations

import os
import platform
from pathlib import Path

_APP_NAME = "mxcensus"
_ENV_VAR = "MXCENSUS_DATA_DIR"


def get_data_dir() -> Path:
    """Return the mxcensus data directory.

    Resolution order:

    1. ``$MXCENSUS_DATA_DIR`` — explicit override
    2. ``~/Library/Application Support/mxcensus`` — macOS conventional
    3. ``$XDG_DATA_HOME/mxcensus`` — XDG standard
    4. ``~/.local/share/mxcensus`` — Linux/other fallback
    """
    if env := os.environ.get(_ENV_VAR):
        return Path(env).expanduser().resolve()

    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME

    if xdg := os.environ.get("XDG_DATA_HOME"):
        return Path(xdg) / _APP_NAME

    return Path.home() / ".local" / "share" / _APP_NAME
