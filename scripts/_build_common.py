"""Shared helpers for the maintainer-only build scripts.

Importable by sibling scripts (``import _build_common``) because Python puts the
running script's directory on ``sys.path``. Centralises the ZIP download +
integrity-verification logic (originally in build_data.py) and the
registry-append logic (originally in build_marco_geo.py) so build_data.py,
build_marco_geo.py and build_denue.py share one implementation.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import chardet
import pooch

# Filename prefixes of mirror entries that must never be dropped when a build
# script rewrites registry.txt. Each dataset's build appends its own prefix.
PRESERVE_PREFIXES = (
    "iter_", "resargebub_", "personas_", "viviendas_",  # census
    "mg_",       # Marco Geoestadístico
    "denue_",    # DENUE
)


def detect_encoding(path: Path) -> str:
    """Best-effort text encoding for an INEGI CSV (ascii is widened to latin-1)."""
    result = chardet.detect(path.read_bytes())
    enc = result.get("encoding") or "latin-1"
    return "latin-1" if enc.lower() == "ascii" else enc


def fetch_zip(url: str, cache_dir: Path, zip_name: str) -> Path:
    """Download one ZIP (no hash check, no extraction) and return its cached path."""
    return Path(
        pooch.retrieve(
            url=url, known_hash=None, path=cache_dir, fname=zip_name, progressbar=True
        )
    )


def verify_zip(zip_path: Path) -> str | None:
    """Full-archive integrity check. Return None if OK, else a reason string.

    Catches an interrupted download's two failure modes: a truncated archive
    (``ZipFile`` raises ``BadZipFile`` because the central directory is at the
    end of the file) and silent byte corruption (``testzip`` recomputes CRCs).
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            bad_member = zf.testzip()
    except zipfile.BadZipFile as exc:
        return f"not a valid/complete ZIP ({exc})"
    if bad_member is not None:
        return f"CRC check failed for member {bad_member!r}"
    return None


def fetch_zip_verified(
    url: str, cache_dir: Path, zip_name: str, retries: int = 2
) -> Path:
    """Download a ZIP and verify it, retrying on both download and integrity failures.

    INEGI's servers drop connections mid-transfer (ConnectTimeout, IncompleteRead)
    and occasionally serve truncated/HTML bodies. We retry up to ``retries`` times on
    *either* a download exception or a failed integrity check, deleting the partial
    file each time (``known_hash=None`` means pooch would otherwise reuse it). Raises
    RuntimeError if still failing after the retries.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            zip_path = fetch_zip(url, cache_dir, zip_name)
        except Exception as exc:  # transient network error during download
            last_err = f"download error: {type(exc).__name__}"
            (cache_dir / zip_name).unlink(missing_ok=True)
            if attempt < retries:
                print(f"  ! {zip_name}: {last_err} — retry {attempt + 1}/{retries}")
            continue
        reason = verify_zip(zip_path)
        if reason is None:
            return zip_path
        last_err = reason
        zip_path.unlink(missing_ok=True)
        if attempt < retries:
            print(f"  ! {zip_name}: {reason} — re-downloading {attempt + 1}/{retries}")
    raise RuntimeError(
        f"{zip_name}: {last_err}. Removed from cache after {retries} "
        f"retr{'y' if retries == 1 else 'ies'}; re-run to try again."
    )


def update_registry(written: list[Path], registry_path: Path) -> None:
    """Upsert ``written`` files' hashes into registry.txt, preserving prior entries.

    Reads the existing registry, recomputes/inserts a SHA256 (via
    ``pooch.file_hash``) for each newly written file, and rewrites the file with
    comment lines preserved and all entries sorted. Asserts that no pre-existing
    mirror entry (matching PRESERVE_PREFIXES) was lost.
    """
    comments: list[str] = []
    entries: dict[str, str] = {}
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                comments.append(line)
                continue
            fname, file_hash = stripped.split()
            entries[fname] = file_hash

    before = {k for k in entries if k.startswith(PRESERVE_PREFIXES)}
    for path in written:
        entries[path.name] = pooch.file_hash(str(path))

    lines = comments + [f"{fname} {entries[fname]}" for fname in sorted(entries)]
    registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    after = {k for k in entries if k.startswith(PRESERVE_PREFIXES)}
    lost = before - after
    assert not lost, f"registry lost protected entries: {sorted(lost)}"
    print(f"\nRegistry updated: {len(written)} entries upserted; {len(entries)} total.")
