"""Command-line interface for mxcensus."""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mxcensus",
        description="mxcensus — Mexico Census 2020 data tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch_p = sub.add_parser(
        "fetch",
        help="Pre-download parquet files for a state from the mirror",
    )
    fetch_p.add_argument("state", type=int, metavar="STATE", help="State code (ENTIDAD), 1-32")
    fetch_p.add_argument(
        "--dataset",
        choices=["iter", "resargebub", "personas", "viviendas", "all"],
        default="all",
        help="Which dataset(s) to fetch (default: all)",
    )

    sub.add_parser("info", help="Show cache directory and mirror info")

    args = parser.parse_args()

    if args.cmd == "fetch":
        from mxcensus.data._registry import POOCH
        from mxcensus.data._catalog import STATE_CODE_FMT

        code = STATE_CODE_FMT(args.state)
        datasets = (
            ["iter", "resargebub", "personas", "viviendas"]
            if args.dataset == "all"
            else [args.dataset]
        )
        for ds in datasets:
            fname = f"{ds}_{code}.parquet"
            path = POOCH.fetch(fname, progressbar=True)
            print(f"  {fname} → {path}")
        print(f"\nFetched {len(datasets)} file(s).")

    elif args.cmd == "info":
        from mxcensus.data._registry import POOCH, _BASE_URL
        from mxcensus.data._paths import get_pooch_cache_dir

        print(f"Cache directory : {get_pooch_cache_dir()}")
        print(f"Mirror base URL : {_BASE_URL}")
        print("Set $MXCENSUS_CACHE_DIR to override the cache directory.")


if __name__ == "__main__":
    main()
