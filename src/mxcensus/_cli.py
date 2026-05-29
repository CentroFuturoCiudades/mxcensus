"""Command-line interface for mxcensus."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mxcensus",
        description="mxcensus — Mexico Census 2020 data tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    dl = sub.add_parser("download", help="Download INEGI Census 2020 data for a state")
    dl.add_argument("state", type=int, metavar="STATE", help="State code (ENTIDAD), 1-32")
    dl.add_argument(
        "--dataset",
        choices=["iter", "resargebub", "cuestionario_ampliado", "all"],
        default="all",
        dest="datasets",
        help="Which dataset(s) to download (default: all)",
    )
    dl.add_argument("--data-dir", type=str, default=None, metavar="DIR")
    dl.add_argument("--force", action="store_true", help="Re-download existing files")

    sub.add_parser("info", help="Show resolved data directory and catalog info")

    args = parser.parse_args()

    if args.cmd == "download":
        from pathlib import Path
        from mxcensus.data import download, get_data_dir

        data_dir = Path(args.data_dir).expanduser() if args.data_dir else None
        paths = download(args.state, datasets=args.datasets, data_dir=data_dir, force=args.force)
        print(f"\nDownloaded {len(paths)} dataset(s).")

    elif args.cmd == "info":
        from mxcensus.data import get_data_dir, CATALOG_VERIFIED_DATE
        print(f"Data directory : {get_data_dir()}")
        print(f"Catalog verified: {CATALOG_VERIFIED_DATE}")
        print("Set $MXCENSUS_DATA_DIR to override the data directory.")


if __name__ == "__main__":
    main()
