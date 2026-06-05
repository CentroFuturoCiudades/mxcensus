#!/usr/bin/env python3
"""Maintainer-only: host the parquet mirror in a Hugging Face Storage Bucket.

The package fetches data from a public HF bucket (see
``mxcensus.data._registry.HF_BUCKET``): objects are served anonymously over plain HTTPS at
``https://huggingface.co/buckets/<bucket>/resolve/<filename>`` (a 302 to the Xet CDN), which
is what Pooch downloads. Buckets are **mutable** (overwrite-in-place, no version history), so
re-running ``upload`` after a rebuild just syncs the changed files — well suited to the
periodic DENUE/MG re-converts (no Git/LFS history to accumulate).

Usage (where the `hf` CLI is installed and authenticated — `hf auth login`):

  python scripts/upload_hf.py create               # create the bucket (once)
  python scripts/upload_hf.py upload               # sync data/parquet/*.parquet + README
  python scripts/upload_hf.py upload --dry-run     # show what would sync, do nothing
  python scripts/upload_hf.py upload --delete      # also remove bucket files absent locally
  python scripts/upload_hf.py verify               # HEAD each resolve URL vs local size (no download)

`upload` is resumable by nature: `hf buckets sync` compares source/destination and transfers
only what changed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from mxcensus.data._registry import HF_BUCKET

_ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = _ROOT / "data" / "parquet"
REGISTRY = _ROOT / "src" / "mxcensus" / "data" / "registry.txt"
README = _ROOT / "docs" / "hf_bucket_readme.md"
BUCKET_URI = f"hf://buckets/{HF_BUCKET}"
RESOLVE = f"https://huggingface.co/buckets/{HF_BUCKET}/resolve/"


def _require_hf() -> None:
    if shutil.which("hf") is None:
        sys.exit("`hf` CLI not found. Install `huggingface_hub` and run `hf auth login`.")


def _registry_names() -> list[str]:
    if not REGISTRY.exists():
        sys.exit(f"registry not found: {REGISTRY}")
    out = []
    for line in REGISTRY.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def cmd_create(args) -> None:
    _require_hf()
    print(f"Creating bucket {HF_BUCKET} (public)…")
    subprocess.run(["hf", "buckets", "create", HF_BUCKET], check=False)


def cmd_upload(args) -> None:
    _require_hf()
    if not PARQUET_DIR.exists():
        sys.exit(f"no parquet directory: {PARQUET_DIR}")
    # Sync the flat parquet files to the bucket ROOT, so resolve/<filename> matches the
    # bare filenames in registry.txt.
    cmd = ["hf", "buckets", "sync", str(PARQUET_DIR), BUCKET_URI, "--include", "*.parquet"]
    if args.delete:
        cmd.append("--delete")
    if args.dry_run:
        cmd.append("--dry-run")
    print("$", " ".join(cmd))
    if subprocess.run(cmd).returncode != 0:
        sys.exit("`hf buckets sync` failed.")
    # Provenance/attribution/PII README rendered on the bucket page.
    if README.exists() and not args.dry_run:
        print(f"Uploading README → {BUCKET_URI}/README.md")
        subprocess.run(
            ["hf", "buckets", "cp", str(README), f"{BUCKET_URI}/README.md"], check=False
        )


def _content_length(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD")  # follows the 302 to the CDN
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cl = r.headers.get("Content-Length")
            return int(cl) if cl is not None else None
    except Exception:
        return None


def cmd_verify(args) -> None:
    """Confirm each registry file is present on the bucket with the right size (no download)."""
    names = _registry_names()
    ok = missing = size_mismatch = no_local = 0
    for name in names:
        url = RESOLVE + name
        remote = _content_length(url)
        if remote is None:
            print(f"  MISSING       {name}")
            missing += 1
            continue
        local = PARQUET_DIR / name
        if not local.exists():
            no_local += 1
            continue
        if local.stat().st_size == remote:
            ok += 1
        else:
            print(f"  SIZE-MISMATCH {name} (local {local.stat().st_size} vs remote {remote})")
            size_mismatch += 1
    print(f"\n  {ok} ok, {missing} missing, {size_mismatch} size-mismatch, "
          f"{no_local} present-remotely-but-no-local-file (of {len(names)}).")
    if missing or size_mismatch:
        sys.exit("verification found problems.")


def main() -> None:
    p = argparse.ArgumentParser(description="Upload the parquet mirror to a HF Storage Bucket.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("create", help="create the bucket (once)").set_defaults(func=cmd_create)

    pu = sub.add_parser("upload", help="sync parquet files + README to the bucket")
    pu.add_argument("--delete", action="store_true",
                    help="remove bucket files no longer present locally")
    pu.add_argument("--dry-run", action="store_true", help="show what would sync, do nothing")
    pu.set_defaults(func=cmd_upload)

    sub.add_parser("verify", help="HEAD each resolve URL and check size vs local (no download)"
                   ).set_defaults(func=cmd_verify)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
