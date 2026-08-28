# ENIGH — build & release runbook

**Status: ✅ 2026-08-27 — full mirror built (99 files, 0/99 validation failures), registry
1833 → 1932, uploaded to the `gperaza/mxcensus` bucket.** This file is the runbook for
rebuilding or extending the ENIGH mirror (next edition: ENIGH 2026, expected mid-2027).

## What ENIGH is here

Fifth data family (after census, MGN, DENUE, ENOE), modelled on ENOE: per-edition faithful-raw
`dtype=str` parquet → per-table fingerprint schema groups → warn-not-raise validation →
HF bucket → edition-qualified loaders with a shared nested index + core-only `harmonize=True`.
Design notes: `STEP_0_probe.md` (URLs, regimes, breaks), `STEP_1.md` (build + metadata),
`STEP_2.md` (loaders + harmonization), `STEP_3.md` (wiring/tests/docs).

## Prerequisites

- Repo on the target branch, `uv sync --extra dev`; run Python as `uv run python`.
- Disk: ~1 GB (ZIP cache ~500 MB + parquet ~450 MB). Network to `www.inegi.org.mx`
  (throttled ~1 MB/s; transient SSL/chunked errors happen — the build retries and reports,
  re-run to resume; cached good ZIPs are skipped).
- Upload needs the `hf` CLI authenticated with write access to `gperaza/mxcensus` (the
  maintainer's `wsl` box has it; a Mac build can be `rsync`ed there).

## Gotchas

- **Faithful raw**: every column `str`; never fix/impute values.
- **Soft-404s**: INEGI serves missing files as HTTP 200 + HTML; `fetch_zip_verified` catches
  this as a ZIP-integrity failure → `MALFORMED`, sweep continues.
- **Per-year NCV filenames** (`Vivi` vs `Viviendas`, `Gastos` in 2008/2010, no dwelling table
  in 2008/2010) are encoded in `_enigh_catalog._NCV_STEMS`; INEGI's server is
  case-insensitive on ZIP names. A new INEGI stem → extend `_NCV_STEMS`, not the build.
- **Never regenerate `variables_enigh_core.yaml`** (hand-curated). If a new edition brings a
  new code for a core categorical (`--validate` will flag it), add it by hand.
- `ubica_geo` width varies (5 chars in 2008/2010/**2024**, 9 in 2012–2022); harmonization
  slices, never assumes.

## A. Build

```bash
uv run python scripts/build_enigh.py --dry-run --periods 2024
uv run python scripts/build_enigh.py                    # all 9 editions → data/parquet/enigh_*.parquet
# expect "Done: 9 edition(s); 0 table(s) failed/missing." and 99 files
```

## B. Metadata (ORDER MATTERS)

```bash
rm src/mxcensus/_yaml/variables_enigh_*_g*.yaml          # keeps variables_enigh_core.yaml
uv run python scripts/build_enigh.py --schema-map
uv run python scripts/build_enigh.py --variables
uv run python scripts/build_enigh.py --report-only
uv run python scripts/build_enigh.py --validate           # must be 0 failures
uv run python scripts/build_enigh.py --update-registry    # +99 entries
```

## C. Upload + verify

```bash
uv run python scripts/upload_hf.py upload --dry-run       # only new/changed files listed
uv run python scripts/upload_hf.py upload                 # NO --delete
nohup uv run python scripts/upload_hf.py verify > /tmp/verify.log 2>&1 &   # HEADs ~1.9k URLs, >10 min
MXCENSUS_CACHE_DIR=$(mktemp -d) uv run python -c "from mxcensus.data._registry import POOCH; print(POOCH.fetch('enigh_concentradohogar_2024.parquet'))"
```

## D. Adding a new edition (e.g. 2026)

1. Probe `…/nc/2026/microdatos/enigh2026_ns_{table}_csv.zip` (HEAD; Content-Type must be zip).
2. `_enigh_catalog.py`: add the year to `_NS_YEARS`, bump `CATALOG_VERIFIED_DATE`.
3. §A with `--periods 2026`, then §B in full (group ids are chronological — adding the newest
   edition can only append/join groups), core-category check, §C, docs counts
   (`CLAUDE.md`, `README.md`, `docs/hf_bucket_readme.md`), tests' `_HOUSEHOLDS` table.

## Verification numbers

| edition | households (Σ factor) | persons (Σ factor, poblacion) | mean quarterly `ing_cor` |
|---|---:|---:|---:|
| 2008 | 27,874,625 | 111,760,640 | 36,523 |
| 2010 | 29,556,772 | 114,700,757 | 34,969 |
| 2012 | 31,559,379 | 117,449,649 | 38,000 |
| 2014 | 31,671,002 | 120,089,882 | 39,742 |
| 2016 | 32,974,661 | 120,919,430 | 46,765 |
| 2018 | 34,400,515 | 123,934,029 | 49,851 |
| 2020 | 35,749,659 | 126,838,467 | 50,309 |
| 2022 | 37,560,123 | 128,999,038 | 63,695 |
| 2024 | 38,830,230 | 130,325,969 | 77,864 |

Identical with and without `harmonize=True` in every edition (tested).
