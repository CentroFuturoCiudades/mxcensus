"""Build the mxcensus raw parquet mirror.

This script is for maintainers only — it is NOT part of the installed package.

Steps
-----
1. Download raw ZIPs from INEGI for each requested state.
2. Convert each extracted CSV to parquet:
   - na_values=["N/D"] (INEGI's missing-data marker becomes NaN)
   - Natural dtype inference is preserved (numeric columns stay numeric;
     columns with "*" censoring markers remain object/string)
3. Write SHA256 hashes to registry.txt via pooch.make_registry().

After running
-------------
- Upload all files in <output>/ to the GitHub Release tagged with the
  value of _DATA_RELEASE_TAG in src/mxcensus/data/_registry.py.
- Commit the updated src/mxcensus/data/registry.txt.

Quick smoke test (CDMX only)
-----------------------------
    python scripts/build_data.py --states 9

Full build (all 32 states — takes a long time and significant bandwidth)
-------------------------------------------------------------------------
    python scripts/build_data.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import chardet
import pandas as pd
import pooch

from mxcensus.data._catalog import (
    STATE_ABBR,
    STATE_CODE_FMT,
    cuestionario_ampliado_entry,
    iter_entry,
    resargebub_entry,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_encoding(path: Path) -> str:
    result = chardet.detect(path.read_bytes())
    enc = result.get("encoding") or "latin-1"
    return "latin-1" if enc.lower() == "ascii" else enc


def _download_raw(state: int, raw_dir: Path, cache_dir: Path) -> None:
    """Download and extract all three ZIPs for one state."""
    for entry_fn in (iter_entry, resargebub_entry, cuestionario_ampliado_entry):
        entry = entry_fn(state)
        zip_name = entry.url.rsplit("/", 1)[-1]
        extract_dir = raw_dir / entry.dest.parent
        extract_dir.mkdir(parents=True, exist_ok=True)
        pooch.retrieve(
            url=entry.url,
            known_hash=None,
            path=cache_dir,
            fname=zip_name,
            progressbar=True,
            processor=pooch.Unzip(extract_dir=str(extract_dir)),
        )


def _csv_to_parquet(csv_path: Path, parquet_path: Path, encoding: str = "utf-8-sig") -> None:
    """Convert a CSV to parquet with INEGI's N/D sentinel mapped to NaN."""
    df = pd.read_csv(csv_path, encoding=encoding, na_values=["N/D"])
    df.to_parquet(parquet_path, index=False)
    print(f"  wrote {parquet_path.name}  ({parquet_path.stat().st_size // 1024} KB)")


def _build_state(state: int, raw_dir: Path, out_dir: Path) -> None:
    code = STATE_CODE_FMT(state)
    abbr = STATE_ABBR[state]
    folder = f"Censo2020_CA_{abbr}_csv"

    # ITER — always utf-8-sig
    iter_csv = raw_dir / "loc" / f"ITER_{code}CSV20.csv"
    _csv_to_parquet(iter_csv, out_dir / f"iter_{code}.parquet")

    # RESARGEBUB — encoding varies; detect with chardet
    resargebub_csv = raw_dir / "ageb_manz" / f"RESAGEBURB_{code}CSV20.csv"
    _csv_to_parquet(
        resargebub_csv,
        out_dir / f"resargebub_{code}.parquet",
        encoding=_detect_encoding(resargebub_csv),
    )

    # Extended questionnaire (utf-8-sig for 2020 CA files)
    base = raw_dir / "cuestionario_ampliado" / folder
    _csv_to_parquet(base / f"Personas{state}.csv", out_dir / f"personas_{code}.parquet")
    _csv_to_parquet(base / f"Viviendas{state}.csv", out_dir / f"viviendas_{code}.parquet")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--states", nargs="+", type=int, default=list(range(1, 33)),
        metavar="N", help="State codes to process (default: all 32)",
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR",
                        help="Output directory for parquet files")
    parser.add_argument("--raw-dir", type=Path, default=_DEFAULT_RAW, metavar="DIR",
                        help="Directory for extracted CSVs")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE, metavar="DIR",
                        help="Directory for downloaded ZIPs (pooch cache)")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE",
                        help="Output registry.txt path")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip downloading ZIPs (use existing raw CSVs)")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    for state in args.states:
        print(f"\n=== State {state:02d} ===")
        if not args.skip_download:
            _download_raw(state, args.raw_dir, args.cache_dir)
        _build_state(state, args.raw_dir, args.output)

    print(f"\nGenerating registry at {args.registry} ...")
    pooch.make_registry(str(args.output), str(args.registry), recursive=False)
    print("Done.")
    print(
        "\nNext steps:\n"
        f"  1. Upload all files in {args.output}/ to the GitHub Release.\n"
        f"  2. Commit {args.registry}."
    )


if __name__ == "__main__":
    main()
