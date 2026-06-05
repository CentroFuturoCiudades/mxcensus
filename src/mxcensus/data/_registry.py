"""Global Pooch registry for the mxcensus parquet mirror.

No network traffic occurs at import time — files are only downloaded on the
first ``POOCH.fetch()`` call for each file.
"""
from __future__ import annotations

import os
from importlib import resources

import pooch

from ._paths import get_pooch_cache_dir

# The parquet mirror is hosted in a Hugging Face Storage Bucket. Public bucket objects are
# served anonymously over plain HTTPS at ``<bucket>/resolve/<filename>`` (a 302 redirect to
# the Xet CDN), so Pooch fetches them as base_url + filename — registry keys are bare
# filenames. Override with $MXCENSUS_BASE_URL to point at a fork/mirror (keep trailing "/").
HF_BUCKET = "gperaza/mxcensus"
_BASE_URL = os.environ.get(
    "MXCENSUS_BASE_URL", f"https://huggingface.co/buckets/{HF_BUCKET}/resolve/"
)

POOCH = pooch.create(
    path=get_pooch_cache_dir(),
    base_url=_BASE_URL,
    registry={},
    env="MXCENSUS_CACHE_DIR",
)

# Show a tqdm download progress bar by default on every fetch (mirror files run from a
# few MB up to hundreds of MB). Pooch only draws the bar when actually downloading, so
# cache hits stay silent. Callers can still pass progressbar=False to opt out.
_pooch_fetch = POOCH.fetch


def _fetch_with_progress(fname, *args, progressbar=True, **kwargs):
    return _pooch_fetch(fname, *args, progressbar=progressbar, **kwargs)


POOCH.fetch = _fetch_with_progress

_reg = resources.files("mxcensus.data") / "registry.txt"
with resources.as_file(_reg) as _p:
    POOCH.load_registry(_p)
