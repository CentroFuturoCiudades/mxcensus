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
    fetch_p.add_argument(
        "state", type=int, metavar="STATE",
        help="State code (ENTIDAD), 1-32. Ignored (N/A) for --dataset enoe (ENOE is national)",
    )
    fetch_p.add_argument(
        "--dataset",
        choices=["iter", "resargebub", "personas", "viviendas", "denue", "enoe", "all"],
        default="all",
        help="Which dataset(s) to fetch (default: all census tabular datasets)",
    )
    fetch_p.add_argument(
        "--release", metavar="YYYYMM",
        help="DENUE release id (e.g. 202011); defaults to the latest. Only for --dataset denue",
    )
    fetch_p.add_argument(
        "--period", metavar="YYYYtQ",
        help="ENOE quarter id (e.g. 2023t1); defaults to the latest. Only for --dataset enoe",
    )

    sub.add_parser("info", help="Show cache directory and mirror info")

    args = parser.parse_args()

    if args.cmd == "fetch":
        from mxcensus.data._registry import POOCH
        from mxcensus.data._catalog import STATE_CODE_FMT

        code = STATE_CODE_FMT(args.state)
        if args.release and args.dataset != "denue":
            parser.error("--release only applies to --dataset denue")
        if args.period and args.dataset != "enoe":
            parser.error("--period only applies to --dataset enoe")
        if args.dataset == "enoe":
            # ENOE is national — one file set per quarter, no per-state split. The `state`
            # positional is ignored; fetch the five tables for the requested (or latest) quarter.
            from mxcensus.data._enoe_catalog import TABLES, latest_quarter
            period = args.period or latest_quarter().period
            fnames = [f"enoe_{table}_{period}.parquet" for table in TABLES]
        elif args.dataset == "denue":
            from mxcensus.data._denue_catalog import latest_release
            rel = args.release or latest_release().yyyymm
            fnames = [f"denue_{rel}_{code}.parquet"]
        else:
            datasets = (
                ["iter", "resargebub", "personas", "viviendas"]
                if args.dataset == "all"
                else [args.dataset]
            )
            fnames = [f"{ds}_{code}.parquet" for ds in datasets]
        for fname in fnames:
            path = POOCH.fetch(fname, progressbar=True)
            print(f"  {fname} → {path}")
        print(f"\nFetched {len(fnames)} file(s).")

    elif args.cmd == "info":
        from mxcensus.data._registry import POOCH, _BASE_URL
        from mxcensus.data._paths import get_pooch_cache_dir

        print(f"Cache directory : {get_pooch_cache_dir()}")
        print(f"Mirror base URL : {_BASE_URL}")
        print("Set $MXCENSUS_CACHE_DIR to override the cache directory.")


if __name__ == "__main__":
    main()
