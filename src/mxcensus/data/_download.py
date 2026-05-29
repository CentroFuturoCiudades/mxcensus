"""INEGI data downloader — stdlib only, no extra dependencies."""
from __future__ import annotations

import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Literal, Sequence

from ._catalog import (
    CatalogEntry,
    cuestionario_ampliado_entry,
    iter_entry,
    resargebub_entry,
)
from ._paths import get_data_dir

DatasetKind = Literal["iter", "resargebub", "cuestionario_ampliado", "all"]

_BUILDERS = {
    "iter": iter_entry,
    "resargebub": resargebub_entry,
    "cuestionario_ampliado": cuestionario_ampliado_entry,
}


def download(
    state: int,
    datasets: DatasetKind | Sequence[DatasetKind] = "all",
    *,
    data_dir: Path | None = None,
    force: bool = False,
    verbose: bool = True,
) -> list[Path]:
    """Download INEGI Census 2020 data for a given state.

    Parameters
    ----------
    state:
        INEGI state code (ENTIDAD), 1–32.
    datasets:
        Which datasets to fetch. One of ``"iter"``, ``"resargebub"``,
        ``"cuestionario_ampliado"``, or ``"all"`` (default).
    data_dir:
        Override the default XDG data directory.
    force:
        Re-download even if the destination already exists.
    verbose:
        Print progress messages to stdout.

    Returns
    -------
    list[Path]
        Absolute paths of the downloaded / extracted destinations.
    """
    base = data_dir or get_data_dir()
    base.mkdir(parents=True, exist_ok=True)

    if isinstance(datasets, str):
        kinds: list[str] = list(_BUILDERS) if datasets == "all" else [datasets]
    else:
        kinds = list(datasets)

    results: list[Path] = []
    for kind in kinds:
        entry = _BUILDERS[kind](state)
        dest = base / entry.dest
        if dest.exists() and not force:
            if verbose:
                print(f"[skip] {entry.description} — already at {dest}")
            results.append(dest)
            continue
        _fetch_and_extract(entry, base, verbose=verbose)
        results.append(dest)
    return results


def _fetch_and_extract(entry: CatalogEntry, base: Path, verbose: bool) -> None:
    if verbose:
        print(f"[download] {entry.description}")
        print(f"  from: {entry.url}")
    tmp_path = Path(tempfile.mktemp(suffix=".zip"))
    try:
        urllib.request.urlretrieve(entry.url, tmp_path)
        dest_dir = base / entry.dest.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_path) as zf:
            zf.extractall(dest_dir)
        if verbose:
            print(f"  extracted to: {dest_dir}")
    finally:
        tmp_path.unlink(missing_ok=True)
