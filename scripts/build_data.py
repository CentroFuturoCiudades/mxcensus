"""Build the legacy CPV 2020 census parquet mirror (iter_/resargebub_/personas_/viviendas_).

This script is for maintainers only — it is NOT part of the installed package.

It builds the original, period-less 2020 files read by ``load_census`` /
``load_extended_*`` (natural dtype inference, ``N/D`` → NaN). The multi-year census
family (``cpv_*``, faithful-raw ``dtype=str``, 1990–2025) is built by
``scripts/build_cpv.py`` instead — see docs/cpv/PLAN.md.

Steps
-----
1. Download raw ZIPs from INEGI for each requested state, verifying each
   archive's integrity (truncation + per-member CRC) and re-downloading on
   failure — INEGI's servers interrupt downloads. Disable with --no-verify.
2. Convert each extracted CSV to parquet:
   - na_values=["N/D"] (INEGI's missing-data marker becomes NaN)
   - Natural dtype inference is preserved (numeric columns stay numeric;
     columns with "*" censoring markers remain object/string)
3. Regenerate the bundled ITER/RESARGEBUB variable dictionaries
   (src/mxcensus/_yaml/) from one state's diccionario CSVs. Disable with
   --no-dictionaries.
4. Upsert the SHA256 hashes of the files written into registry.txt
   (``_build_common.update_registry`` — every other family's entries are preserved;
   the old ``pooch.make_registry`` rewrite would have dropped any registry entry whose
   parquet is not present in <output>/).

After running
-------------
- Upload the new files to the Hugging Face bucket: ``python scripts/upload_hf.py upload``.
- Commit the updated src/mxcensus/data/registry.txt and any changes to
  src/mxcensus/_yaml/variables_{iter,resargebub}.yaml.

Quick smoke test (CDMX only)
-----------------------------
    python scripts/build_data.py --states 9

Full build (all 32 states — takes a long time and significant bandwidth)
-------------------------------------------------------------------------
    python scripts/build_data.py
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd

import _build_common as bc
from mxcensus.data._catalog import (
    STATE_CODE_FMT,
    cuestionario_ampliado_entry,
    iter_entry,
    resargebub_entry,
)
from mxcensus.utils import get_vars_from_indicator_csv

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_RAW = _REPO_ROOT / "data" / "raw"
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"
_DEFAULT_YAML = _REPO_ROOT / "src" / "mxcensus" / "_yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _download_raw(
    state: int, raw_dir: Path, cache_dir: Path, verify: bool, retries: int
) -> None:
    """Download, optionally verify, and extract all three ZIPs for one state.

    With ``known_hash=None`` pooch reuses any file already in ``cache_dir``
    without re-checking it, so a once-corrupt download would persist across
    runs. ``_build_common.fetch_zip_verified`` deletes a bad file and re-downloads
    up to ``retries`` times; on persistent failure it raises so the build stops
    loudly instead of converting a truncated archive.
    """
    for entry_fn in (iter_entry, resargebub_entry, cuestionario_ampliado_entry):
        entry = entry_fn(state)
        zip_name = entry.url.rsplit("/", 1)[-1]
        extract_dir = raw_dir / entry.extract_dir
        extract_dir.mkdir(parents=True, exist_ok=True)

        if verify:
            zip_path = bc.fetch_zip_verified(entry.url, cache_dir, zip_name, retries)
            print(f"  ✓ verified {zip_name}")
        else:
            zip_path = bc.fetch_zip(entry.url, cache_dir, zip_name)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)


def _csv_to_parquet(csv_path: Path, parquet_path: Path, encoding: str = "utf-8-sig") -> Path:
    """Convert a CSV to parquet with INEGI's N/D sentinel mapped to NaN.

    low_memory=False forces whole-column dtype inference. With pandas' default
    chunked reading, a column whose codes look numeric in early chunks but turn
    out mixed later (e.g. ITER's ALTITUD — zero-padded "0018" alongside "00-1"
    markers and blank rows) lands as a mixed str/NaN object column that pyarrow
    refuses to write. One-pass inference resolves it to a single string column
    with proper nulls instead.
    """
    df = pd.read_csv(csv_path, encoding=encoding, na_values=["N/D"], low_memory=False)
    df.to_parquet(parquet_path, index=False)
    print(f"  wrote {parquet_path.name}  ({parquet_path.stat().st_size // 1024} KB)")
    return parquet_path


def _build_state(state: int, raw_dir: Path, out_dir: Path) -> list[Path]:
    """Convert one state's extracted CSVs; return the parquet files written."""
    code = STATE_CODE_FMT(state)
    written: list[Path] = []

    # ITER — locality-level. Nested: <root>/iter_NN_cpv2020/conjunto_de_datos/...
    iter_csv = (
        raw_dir / "loc" / f"iter_{code}_cpv2020"
        / "conjunto_de_datos" / f"conjunto_de_datos_iter_{code}CSV20.csv"
    )
    written.append(_csv_to_parquet(iter_csv, out_dir / f"iter_{code}.parquet"))

    # RESARGEBUB — AGEB/block-level; encoding varies, detect with chardet.
    resargebub_csv = (
        raw_dir / "ageb_manz" / f"ageb_mza_urbana_{code}_cpv2020"
        / "conjunto_de_datos" / f"conjunto_de_datos_ageb_urbana_{code}_cpv2020.csv"
    )
    written.append(_csv_to_parquet(
        resargebub_csv,
        out_dir / f"resargebub_{code}.parquet",
        encoding=bc.detect_encoding(resargebub_csv),
    ))

    # Extended questionnaire — flat ZIP, uppercase .CSV, zero-padded state code.
    ca_dir = raw_dir / "cuestionario_ampliado"
    written.append(
        _csv_to_parquet(ca_dir / f"Personas{code}.CSV", out_dir / f"personas_{code}.parquet"))
    written.append(
        _csv_to_parquet(ca_dir / f"Viviendas{code}.CSV", out_dir / f"viviendas_{code}.parquet"))
    return written


def _build_dictionaries(state: int, raw_dir: Path, yaml_dir: Path) -> bool:
    """Regenerate the bundled ITER/RESARGEBUB variable dictionaries from one state.

    These dictionaries are national (identical across states), so they are built
    once from a single state's extracted ``diccionario`` CSVs. Returns False (with
    a warning) if those CSVs aren't on disk — e.g. a --skip-download run whose raw
    extraction was cleaned — so a missing optional artifact never aborts the build.
    Note the two datasets use different dictionary folder names (``diccionario_datos``
    vs ``diccionario_de_datos``).
    """
    code = STATE_CODE_FMT(state)
    iter_dict = (
        raw_dir / "loc" / f"iter_{code}_cpv2020"
        / "diccionario_datos" / f"diccionario_datos_iter_{code}CSV20.csv"
    )
    resargebub_dict = (
        raw_dir / "ageb_manz" / f"ageb_mza_urbana_{code}_cpv2020"
        / "diccionario_de_datos" / f"diccionario_datos_ageb_urbana_{code}_cpv2020.csv"
    )
    missing = [p for p in (iter_dict, resargebub_dict) if not p.exists()]
    if missing:
        print(f"  ! dictionaries skipped — not found: {', '.join(p.name for p in missing)}")
        return False

    n_iter = len(get_vars_from_indicator_csv(iter_dict, yaml_dir / "variables_iter.yaml"))
    n_res = len(get_vars_from_indicator_csv(resargebub_dict, yaml_dir / "variables_resargebub.yaml"))
    print(f"  wrote variables_iter.yaml ({n_iter} vars), variables_resargebub.yaml ({n_res} vars)")
    return True


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
                        help="registry.txt to upsert the written files into")
    parser.add_argument("--no-registry", dest="registry_update", action="store_false",
                        help="Skip updating registry.txt")
    parser.add_argument("--yaml-dir", type=Path, default=_DEFAULT_YAML, metavar="DIR",
                        help="Bundled _yaml/ directory for regenerated variable dictionaries")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip downloading ZIPs (use existing raw CSVs)")
    parser.add_argument("--no-verify", dest="verify", action="store_false",
                        help="Skip the ZIP integrity check after each download")
    parser.add_argument("--no-dictionaries", dest="dictionaries", action="store_false",
                        help="Skip regenerating the bundled ITER/RESARGEBUB variable dictionaries")
    parser.add_argument("--retries", type=int, default=2, metavar="N",
                        help="Re-download attempts when a ZIP fails verification (default: 2)")
    parser.set_defaults(verify=True, dictionaries=True, registry_update=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for state in args.states:
        print(f"\n=== State {state:02d} ===")
        if not args.skip_download:
            _download_raw(state, args.raw_dir, args.cache_dir, args.verify, args.retries)
        written += _build_state(state, args.raw_dir, args.output)

    if args.dictionaries:
        print("\nRegenerating bundled variable dictionaries ...")
        _build_dictionaries(args.states[0], args.raw_dir, args.yaml_dir)

    if args.registry_update:
        bc.update_registry(written, args.registry)
    print("Done.")
    print(
        "\nNext steps:\n"
        "  1. python scripts/upload_hf.py upload\n"
        f"  2. Commit {args.registry}."
    )


if __name__ == "__main__":
    main()
