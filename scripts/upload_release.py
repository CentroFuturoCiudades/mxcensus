#!/usr/bin/env python3
"""Maintainer-only: organized, resumable batch upload of the parquet mirror.

The mirror is ~1400 geoparquet files (~11 GB). GitHub release uploads are done in
small batches over several days, so this tool must be **resumable**: the source of
truth for "already uploaded" is the GitHub release itself, queried live each run via
``gh release view``. There is no local state file to drift or corrupt — re-running
after a crashed or partial upload simply skips the assets already present.

Batches (derived from the registry so they always match what exists on disk):

  core_denue   denue_202605 (latest release).                            [32 files]
  core_census  census (iter/resargebub/personas/viviendas).             [128 files]
  core_mg      the 4 Marco Geoestadístico layers load_mg_census fetches
               (mg_a / mg_l / mg_lpr / mg_ar).                          [128 files]
  mg-rest      the other 11 MG layers (cd/e/ent/fm/m/mun/pe/pem/sia/sil/sip). [352]
  denue-<id>   one older DENUE release per batch, newest→oldest.    [32 files each]

Usage (run from the repo root, where `gh` is on PATH and authenticated):

  python scripts/upload_release.py status               # live progress table
  python scripts/upload_release.py status --write-doc   # also write docs/UPLOAD_PROGRESS.md
  python scripts/upload_release.py create-release       # create the Release (done once)
  python scripts/upload_release.py list core_denue      # files in a batch
  python scripts/upload_release.py upload core_denue    # upload remaining files in the batch
  python scripts/upload_release.py upload --next        # upload the next incomplete batch
  python scripts/upload_release.py upload denue-201811 --clobber   # re-upload (overwrite)
  python scripts/upload_release.py upload core_mg --dry-run        # show, don't upload
  python scripts/upload_release.py verify               # check SHA-256/size vs registry
  python scripts/upload_release.py verify core_denue    # verify one batch

Notes
- `verify` compares each uploaded asset's GitHub-computed SHA-256 digest to registry.txt
  WITHOUT downloading (via `gh api`). GitHub computes digests asynchronously, so a just-
  uploaded asset may show `digest-pending` — it then falls back to a size check against
  the local file, or re-run later once the digest is available.
- The GitHub Release must exist before assets can be uploaded; `upload` creates it
  automatically on first run (or run `create-release`). `gh release upload` errors with
  "release not found" if it is missing.
- ``--clobber`` overwrites assets already on the release (use for the two corrected
  files denue_201811_29 / denue_201200_14); without it, present assets are skipped.
- Uploads are chunked (``--chunk``, default 25) so each `gh` call is a commit point;
  a failure only loses the in-flight chunk and the next run resumes from there.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = "CentroFuturoCiudades/mxcensus"
TAG = "data-v0.1.0"

_ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = _ROOT / "data" / "parquet"
REGISTRY = _ROOT / "src" / "mxcensus" / "data" / "registry.txt"
DOC = _ROOT / "docs" / "UPLOAD_PROGRESS.md"

# MG layers load_mg_census() actually fetches (aggregate.py) — these go in `core`.
USED_MG = ("a", "l", "lpr", "ar")
CENSUS = ("iter", "resargebub", "personas", "viviendas")
LATEST_DENUE = "202605"


# --------------------------------------------------------------------------- #
# Batch construction (derived from the registry — always matches what exists)
# --------------------------------------------------------------------------- #
def _registry_names() -> list[str]:
    if not REGISTRY.exists():
        sys.exit(f"registry not found: {REGISTRY}")
    names = []
    for line in REGISTRY.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line.split()[0])
    return names


def _classify(name: str) -> str:
    """Map a registry filename to its batch key."""
    if name.startswith("denue_"):
        release = name.split("_")[1]              # denue_<YYYYMM>_<NN>.parquet
        return "core_denue" if release == LATEST_DENUE else f"denue-{release}"
    if name.startswith("mg_"):
        suffix = name[len("mg_"):].rsplit("_", 1)[0]   # mg_<suffix>_<NN>.parquet
        return "core_mg" if suffix in USED_MG else "mg-rest"
    if name.split("_")[0] in CENSUS:              # iter/resargebub/personas/viviendas
        return "core_census"
    return "other"


# The three small first-upload batches (was the single `core`), in upload order.
_CORE_BATCHES = ("core_denue", "core_census", "core_mg")


def build_batches() -> "OrderedDict[str, list[str]]":
    """Return ordered {batch_key: [filenames]} — core_*, mg-rest, then denue newest→oldest."""
    groups: dict[str, list[str]] = {}
    for name in _registry_names():
        groups.setdefault(_classify(name), []).append(name)

    ordered: "OrderedDict[str, list[str]]" = OrderedDict()
    for k in _CORE_BATCHES:
        if k in groups:
            ordered[k] = sorted(groups.pop(k))
    if "mg-rest" in groups:
        ordered["mg-rest"] = sorted(groups.pop("mg-rest"))
    # remaining denue releases, newest first
    denue_keys = sorted((k for k in groups if k.startswith("denue-")), reverse=True)
    for k in denue_keys:
        ordered[k] = sorted(groups.pop(k))
    for k in sorted(groups):                      # anything unexpected, surfaced last
        ordered[k] = sorted(groups[k])
    return ordered


# --------------------------------------------------------------------------- #
# GitHub release state (live source of truth)
# --------------------------------------------------------------------------- #
def _require_gh() -> None:
    if shutil.which("gh") is None:
        sys.exit("`gh` CLI not found on PATH. Install it and run `gh auth login`.")


def uploaded_assets() -> set[str]:
    """Set of asset filenames currently on the release (empty if release has none)."""
    _require_gh()
    res = subprocess.run(
        ["gh", "release", "view", TAG, "--repo", REPO, "--json", "assets"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        err = res.stderr.strip()
        if "release not found" in err.lower() or "not found" in err.lower():
            return set()
        sys.exit(f"`gh release view` failed: {err}")
    data = json.loads(res.stdout or "{}")
    return {a["name"] for a in data.get("assets", [])}


def asset_details() -> dict[str, dict]:
    """{asset_name: {'sha256': hex|None, 'size': int}} from the release (no download).

    Uses the raw API (not `gh release view --json`, which omits the digest). GitHub
    computes a SHA-256 ``digest`` per asset asynchronously, so it can be null right
    after upload or for assets predating the feature — callers fall back to size then.
    """
    _require_gh()
    res = subprocess.run(
        ["gh", "api", f"repos/{REPO}/releases/tags/{TAG}"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        err = res.stderr.strip()
        if "not found" in err.lower() or "404" in err:
            return {}
        sys.exit(f"`gh api` failed: {err}")
    out: dict[str, dict] = {}
    for a in json.loads(res.stdout or "{}").get("assets", []):
        digest = a.get("digest") or ""
        out[a["name"]] = {
            "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None,
            "size": a.get("size"),
        }
    return out


def _registry_hashes() -> dict[str, str]:
    """{filename: sha256hex} from registry.txt."""
    out: dict[str, str] = {}
    for line in REGISTRY.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
    return out


def release_exists() -> bool:
    """True if the GitHub Release (and its tag) already exists."""
    _require_gh()
    res = subprocess.run(
        ["gh", "release", "view", TAG, "--repo", REPO, "--json", "tagName"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def ensure_release(*, dry_run: bool = False) -> None:
    """Create the data Release (and tag) if it does not exist — uploads need it first."""
    if release_exists():
        return
    if dry_run:
        print(f"[dry-run] release {TAG} does not exist; would create it on {REPO}.")
        return
    print(f"Release {TAG} not found — creating it on {REPO} …")
    res = subprocess.run(
        ["gh", "release", "create", TAG, "--repo", REPO, "--latest=false",
         "--title", "Data mirror (parquet)",
         "--notes", "Pre-converted INEGI parquet mirror for `mxcensus` "
                    "(census, Marco Geoestadístico, DENUE). Assets are uploaded in "
                    "batches by scripts/upload_release.py."],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.exit(f"failed to create release {TAG}: {res.stderr.strip()}\n"
                 f"Create it manually, e.g.:\n"
                 f"  gh release create {TAG} --repo {REPO} --latest=false "
                 f'--title "Data mirror (parquet)" --notes "mxcensus data mirror"')
    print(f"Created release {TAG}.")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_status(args) -> None:
    batches = build_batches()
    present = uploaded_assets()
    rows, tot, tot_up = [], 0, 0
    for key, files in batches.items():
        up = sum(1 for f in files if f in present)
        tot += len(files); tot_up += up
        mark = "✓" if up == len(files) else ("·" if up == 0 else "◐")
        rows.append((mark, key, up, len(files)))

    width = max(len(k) for _, k, _, _ in rows)
    exists = release_exists()
    print(f"\nRelease {REPO} @ {TAG}  —  {tot_up}/{tot} files uploaded "
          f"({100 * tot_up // tot if tot else 0}%)\n")
    if not exists:
        print("  ⚠ release does not exist yet — `upload` will create it "
              "(or run `create-release`).\n")
    for mark, key, up, n in rows:
        bar_done = up * 20 // n if n else 0
        bar = "█" * bar_done + "░" * (20 - bar_done)
        print(f"  {mark} {key:<{width}}  {bar}  {up:>3}/{n}")
    # next incomplete batch
    nxt = next((k for k, fs in batches.items()
                if sum(f in present for f in fs) < len(fs)), None)
    print(f"\n  next incomplete batch: {nxt or '— all uploaded —'}\n")

    if getattr(args, "write_doc", False):
        _write_doc(batches, present, tot, tot_up, nxt)
        print(f"  wrote {DOC.relative_to(_ROOT)}\n")


def _write_doc(batches, present, tot, tot_up, nxt) -> None:
    lines = [
        "# Mirror upload progress",
        "",
        f"Release: `{REPO}` @ `{TAG}`  ",
        f"Progress: **{tot_up}/{tot}** files "
        f"({100 * tot_up // tot if tot else 0}%)  ",
        f"Next incomplete batch: `{nxt or '— all uploaded —'}`",
        "",
        "> Live state queried from the GitHub release; regenerate with "
        "`python scripts/upload_release.py status --write-doc`.",
        "",
        "| status | batch | uploaded |",
        "|--------|-------|----------|",
    ]
    for key, files in batches.items():
        up = sum(1 for f in files if f in present)
        mark = "✅" if up == len(files) else ("⬜" if up == 0 else "🟡")
        lines.append(f"| {mark} | `{key}` | {up}/{len(files)} |")
    lines.append("")
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines))


def cmd_list(args) -> None:
    batches = build_batches()
    if args.batch not in batches:
        sys.exit(f"unknown batch '{args.batch}'. Known: {', '.join(batches)}")
    for f in batches[args.batch]:
        print(f)


def _resolve_batches(args, batches) -> list[str]:
    if args.next:
        present = uploaded_assets()
        nxt = next((k for k, fs in batches.items()
                    if sum(f in present for f in fs) < len(fs)), None)
        if nxt is None:
            print("All batches already uploaded — nothing to do.")
            return []
        print(f"Next incomplete batch: {nxt}")
        return [nxt]
    unknown = [b for b in args.batches if b not in batches]
    if unknown:
        sys.exit(f"unknown batch(es): {', '.join(unknown)}. Known: {', '.join(batches)}")
    return args.batches


def cmd_verify(args) -> None:
    """Compare release assets' SHA-256 digests (and size) to registry.txt — no download."""
    batches = build_batches()
    unknown = [b for b in args.batches if b not in batches]
    if unknown:
        sys.exit(f"unknown batch(es): {', '.join(unknown)}. Known: {', '.join(batches)}")
    keys = args.batches or list(batches)
    remote = asset_details()
    reg = _registry_hashes()
    if not remote:
        print(f"Release {TAG} has no assets (or does not exist) — nothing to verify.")
        return

    totals: dict[str, int] = {}
    any_bad = False
    for key in keys:
        counts: dict[str, int] = {}
        bad: list[tuple[str, str]] = []
        for f in batches[key]:
            info = remote.get(f)
            if info is None:
                st = "missing"
            elif info["sha256"] is not None:
                st = "ok" if info["sha256"] == reg.get(f) else "MISMATCH"
            else:  # digest not yet computed by GitHub — fall back to size vs local file
                local = PARQUET_DIR / f
                if not local.exists():
                    st = "digest-pending"
                else:
                    st = "size-ok" if local.stat().st_size == info["size"] else "size-MISMATCH"
            counts[st] = counts.get(st, 0) + 1
            totals[st] = totals.get(st, 0) + 1
            if st not in ("ok", "size-ok"):
                bad.append((f, st))
                if st in ("MISMATCH", "size-MISMATCH", "missing"):
                    any_bad = True
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        mark = "✓" if all(s in ("ok", "size-ok") for s in counts) else "✗"
        print(f"  {mark} {key:<13} {len(batches[key]):>4} files — {summary}")
        for f, st in bad[:20]:
            print(f"        {st:<14} {f}")
        if len(bad) > 20:
            print(f"        … and {len(bad) - 20} more")

    print(f"\n  totals: " + ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
    pending = totals.get("digest-pending", 0)
    if pending:
        print(f"  note: {pending} asset(s) have no digest yet (GitHub computes it "
              f"asynchronously) and no local file to size-check; re-run later.")
    if any_bad:
        sys.exit("  verification found mismatches/missing assets.")


def cmd_create_release(args) -> None:
    if release_exists():
        print(f"Release {TAG} already exists on {REPO}.")
        return
    ensure_release()


def cmd_upload(args) -> None:
    batches = build_batches()
    keys = _resolve_batches(args, batches)
    if not keys:
        return
    ensure_release(dry_run=args.dry_run)   # the release must exist before uploading
    present = uploaded_assets()

    for key in keys:
        files = batches[key]
        missing_local = [f for f in files if not (PARQUET_DIR / f).exists()]
        if missing_local:
            sys.exit(f"[{key}] {len(missing_local)} file(s) missing locally, "
                     f"e.g. {missing_local[0]} — aborting.")
        todo = files if args.clobber else [f for f in files if f not in present]
        skipped = len(files) - len(todo)
        print(f"\n[{key}] {len(files)} files — {skipped} already present, "
              f"{len(todo)} to upload"
              + (" (clobber)" if args.clobber else "") + ".")
        if not todo:
            continue

        for i in range(0, len(todo), args.chunk):
            chunk = todo[i:i + args.chunk]
            paths = [str(PARQUET_DIR / f) for f in chunk]
            cmd = ["gh", "release", "upload", TAG, "--repo", REPO, *paths]
            if args.clobber:
                cmd.append("--clobber")
            n0, n1 = i + 1, i + len(chunk)
            print(f"  uploading {n0}-{n1}/{len(todo)}: {chunk[0]} … {chunk[-1]}")
            if args.dry_run:
                continue
            res = subprocess.run(cmd)
            if res.returncode != 0:
                sys.exit(f"  upload failed on chunk {n0}-{n1}; "
                         f"re-run to resume (uploaded assets are skipped).")
        print(f"[{key}] done.")


def main() -> None:
    _require = False  # gh checked lazily per command
    p = argparse.ArgumentParser(description="Resumable batch upload of the parquet mirror.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("status", help="show live upload progress")
    ps.add_argument("--write-doc", action="store_true",
                    help="also write docs/UPLOAD_PROGRESS.md")
    ps.set_defaults(func=cmd_status)

    pl = sub.add_parser("list", help="list the files in a batch")
    pl.add_argument("batch")
    pl.set_defaults(func=cmd_list)

    pc = sub.add_parser("create-release", help="create the data Release if it doesn't exist")
    pc.set_defaults(func=cmd_create_release)

    pv = sub.add_parser("verify", help="check release asset SHA-256/size vs registry (no download)")
    pv.add_argument("batches", nargs="*", help="batch key(s) to verify (default: all)")
    pv.set_defaults(func=cmd_verify)

    pu = sub.add_parser("upload", help="upload a batch (skips already-present assets)")
    pu.add_argument("batches", nargs="*", help="batch key(s); omit with --next")
    pu.add_argument("--next", action="store_true",
                    help="upload the next incomplete batch")
    pu.add_argument("--clobber", action="store_true",
                    help="overwrite assets already on the release")
    pu.add_argument("--chunk", type=int, default=25,
                    help="files per gh call (commit granularity; default 25)")
    pu.add_argument("--dry-run", action="store_true",
                    help="print what would be uploaded, do nothing")
    pu.set_defaults(func=cmd_upload)

    args = p.parse_args()
    if args.cmd == "upload" and not args.next and not args.batches:
        p.error("upload: give a batch key or --next")
    args.func(args)


if __name__ == "__main__":
    main()
