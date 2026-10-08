"""Command-line interface for mxcensus."""
from __future__ import annotations

import argparse

# Each multi-temporal family has its own selector flag. A flag maps to the set of
# --dataset values it applies to (one flag may serve several families, e.g. --edition).
SELECTOR_FLAGS: dict[str, frozenset[str]] = {
    "release": frozenset({"denue"}),
    "period": frozenset({"enoe"}),
    "edition": frozenset({"enigh", "cpv", "mg"}),
}

# Datasets mirrored as one national file set: the STATE positional does not apply.
NATIONAL_DATASETS = frozenset({"enoe", "enigh"})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="mxcensus",
        description="mxcensus — INEGI census, survey and geostatistical data tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch_p = sub.add_parser(
        "fetch",
        help="Pre-download parquet files for a state from the mirror",
    )
    fetch_p.add_argument(
        "state", type=int, metavar="STATE", nargs="?",
        help="State code (ENTIDAD), 1-32. Required except for the national surveys "
             "(--dataset enoe/enigh), where it is ignored",
    )
    fetch_p.add_argument(
        "--dataset",
        choices=["iter", "resargebub", "personas", "viviendas", "denue", "enoe", "enigh",
                 "cpv", "mg", "all"],
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
    fetch_p.add_argument(
        "--edition", metavar="YYYY",
        help="Edition year. --dataset enigh (e.g. 2022) and cpv (e.g. 2025): defaults to the "
             "latest; --dataset mg (Marco Geoestadístico, 2020 or 2025): defaults to 2020, "
             "as mxcensus.load_mg",
    )

    sub.add_parser("info", help="Show cache directory and mirror info")

    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        from mxcensus.data._registry import POOCH
        from mxcensus.data._catalog import STATE_CODE_FMT

        # Reject a selector flag used with a family it does not apply to.
        for flag, families in SELECTOR_FLAGS.items():
            if getattr(args, flag) and args.dataset not in families:
                parser.error(f"--{flag} only applies to --dataset {'/'.join(sorted(families))}")
        if args.dataset not in NATIONAL_DATASETS:
            if args.state is None:
                parser.error(f"STATE is required for --dataset {args.dataset}")
            if not 1 <= args.state <= 32:
                parser.error(f"STATE must be 1-32, got {args.state}")
            code = STATE_CODE_FMT(args.state)
        if args.dataset == "enigh":
            # ENIGH is national — one file per (edition, table); `state` is ignored.
            from mxcensus.data._enigh_catalog import EDITIONS_BY_PERIOD, latest_edition
            period = args.edition or latest_edition().period
            if period not in EDITIONS_BY_PERIOD:
                parser.error(f"unknown ENIGH edition {period!r}; known: {list(EDITIONS_BY_PERIOD)}")
            fnames = [f"enigh_{table}_{period}.parquet"
                      for table in EDITIONS_BY_PERIOD[period].tables]
        elif args.dataset == "enoe":
            # ENOE is national — one file set per quarter, no per-state split. The `state`
            # positional is ignored; fetch the five tables for the requested (or latest) quarter.
            from mxcensus.data._enoe_catalog import TABLES, latest_quarter
            period = args.period or latest_quarter().period
            fnames = [f"enoe_{table}_{period}.parquet" for table in TABLES]
        elif args.dataset == "cpv":
            # Censos/conteos/intercensales: the state's microdata tables of the edition plus
            # its national tables (EIC 2025: the estimaciones) — only files in the registry.
            from mxcensus.data._cpv_catalog import (
                EDITIONS_BY_PERIOD, NATIONAL_TABLES, cpv_filename, latest_edition)
            period = args.edition or latest_edition().period
            if period not in EDITIONS_BY_PERIOD:
                parser.error(f"unknown CPV edition {period!r}; known: {list(EDITIONS_BY_PERIOD)}")
            fnames = [cpv_filename(t, period, None if t in NATIONAL_TABLES else args.state)
                      for t in EDITIONS_BY_PERIOD[period].tables]
            fnames = [f for f in fnames if f in POOCH.registry]
            if not fnames:
                parser.error(f"CPV {period} is not in the mirror yet")
        elif args.dataset == "mg":
            # Marco Geoestadístico: every layer of the state in the registry (``ti`` exists
            # only for the island states).
            from mxcensus.data._catalog import MG_EDITIONS, MG_LAYERS, MG_LEGACY_PERIOD, mg_filename
            period = args.edition or MG_LEGACY_PERIOD
            if period not in MG_EDITIONS:
                parser.error(f"unknown Marco Geoestadístico edition {period!r}; "
                             f"known: {sorted(MG_EDITIONS)}")
            fnames = [f for sfx in MG_LAYERS
                      if (f := mg_filename(sfx, args.state, period)) in POOCH.registry]
            if not fnames:
                parser.error(f"Marco Geoestadístico {period} is not in the mirror yet")
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
