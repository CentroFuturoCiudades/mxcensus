# ENOE — Remote build & release handoff (Units 7–8, full mirror)

**Audience:** a fresh Claude Code session on a remote headless server, with **no access to
prior conversation/project memory**. Everything you need is in this file and the repo. Read
this top-to-bottom before running anything.

**Goal of the remote session:** perform the **full 84-quarter ENOE build**, regenerate all
metadata from it, register + **upload the mirror to the Hugging Face bucket** (Unit 7), then
land the code/docs/tests (Unit 8), verify end-to-end, and commit. Optional Units 9–10 at the
end.

---

## 0. Context — what ENOE is and what's already done

`mxcensus` is a loader for INEGI Mexican microdata (census, DENUE economic units). We are
adding a **4th data family**: **ENOE** (Encuesta Nacional de Ocupación y Empleo), Mexico's
quarterly labor-force survey — **national** (one file set per quarter, *not* per-state),
**5 tables per quarter** (`viv`/`hog`/`sdem`/`coe1`/`coe2`), **84 quarters** 2005-T1…2026-T1
(2020-T2 is an ETOE gap, excluded). Modelled on the DENUE machinery (per-period, faithful-raw
parquet + fingerprint schema-groups + warn-not-raise validation → HF-bucket mirror →
release-qualified loader), minus geometry.

**Work is on branch `enoe-integration`.** Units 0–6 are **done and committed** (do `git log
--oneline | grep ENOE`). Per-unit design notes live in `docs/enoe/STEP_0..6.md` — **read
STEP_2, STEP_5, STEP_6 before building** (they contain the data gotchas). Summary of what
exists:

| Done | What |
|------|------|
| Unit 0–1 | `src/mxcensus/data/_enoe_catalog.py` — URL/regime catalog, 84 quarters, `latest_quarter()`. |
| Unit 2 | `scripts/build_enoe.py` — download→faithful parquet (`enoe_{table}_{period}.parquet`). |
| Unit 3 | `--schema-map`/`--report-only` → `enoe_schema_map.yaml` (per-table groups) + `INCONSISTENCY_REPORT.md`. |
| Unit 4 | `--variables` → `variables_enoe_{table}_{gNN}.yaml`; hand-curated `variables_enoe_core.yaml`; `_resources.py` accessors. |
| Unit 5 | `--validate` → `VALIDATION_REPORT.md`; `enoe.py` `_group_schema` schema layer. |
| Unit 6 | `enoe.py` loaders `load_enoe` / `load_enoe_persons`. |
| Unit 7 (this) | `--update-registry` mode exists; **the actual full build + registry + upload is what you do.** |

### ⚠️ The single most important fact

**Everything committed so far used only an 8-quarter SUBSET** (`2005t1, 2019t1, 2019t2,
2020t3, 2021t3, 2023t1, 2023t2, 2026t1`) — a full build was impractical interactively. So the
committed `enoe_schema_map.yaml`, the per-group `variables_enoe_{table}_{gNN}.yaml`, and the
two reports are **subset-derived and MUST be regenerated from the full build** (§B). They will
change — expect **more schema groups** (previously-unsampled quarters: Q3/Q4 COE básico
variants, 2006–2018 drift). `variables_enoe_core.yaml` is the exception — it is **hand-curated
and must NOT be overwritten** (see §Gotchas).

---

## 1. Prerequisites & secrets

- **Repo**: on branch `enoe-integration`, `git pull` the latest. All commands assume repo root.
- **Python/env**: 3.13+; `uv sync --extra dev` (or `uv pip install -e ".[dev]"`). **Run
  Python as `uv run python`.**
- **Disk**: budget **~6 GB free** — ZIP cache (`data/cache`, ~2.5 GB, kept for resumability) +
  420 parquet (`data/parquet`, ~2.5 GB) + transient CSV extraction (deleted per-quarter).
- **Network**: `www.inegi.org.mx` reachable. Downloads are **slow/throttled and flaky**;
  the build retries each ZIP and does not abort the sweep on one failure.
- **Time**: the full download is **multi-hour** (84 ZIPs × ~30–40 MB over a throttled link).
  It is **resumable** — cached ZIPs are reused, so re-running `build_enoe.py` continues where
  it left off. Consider running the build in the background and polling.
- **🔑 HF write auth (REQUIRED for upload, §C)**: the upload uses `hf buckets sync` to the
  bucket **`gperaza/mxcensus`** (`HF_BUCKET` in `src/mxcensus/data/_registry.py`). Headless:
  `export HF_TOKEN=hf_...` with **write** access to the `gperaza` namespace (the `hf` CLI /
  `huggingface_hub` reads `HF_TOKEN`). **This token must be supplied by the maintainer — you
  cannot proceed past §C without it.** If it's absent, do §A/§B/§D and STOP before §C-upload,
  leaving upload for the maintainer.

---

## 2. Gotchas — read before building (all learned the hard way)

- **Faithful raw**: every column is `dtype=str`. **Never "fix"/impute values.** The mirror
  mirrors INEGI byte-for-byte.
- **Soft-404s**: INEGI serves missing files as **HTTP 200 + HTML**. `fetch_zip_verified`
  catches this (ZIP integrity fails) → the quarter is reported `MALFORMED`, sweep continues.
- **Source encoding defect (do not fix)**: some SDEM files carry an *unrecoverable* INEGI
  encoding defect (bytes `0xCB`/`0xD0` = mangled Ó/Ñ) in the open-text `cs_p21_des`/
  `cs_p23_des` fields only. Preserved losslessly; **not** a build bug. See `STEP_2.md`. It is
  value-level (free text), so it never fails schema validation.
- **Un-padded codes**: the CSV emits `r_def='0'` (not `'00'`), `mes_cal='1'..'12'` + special
  `96..99`, `ent='1'..'32'`. **2026-T1 renamed** `ent`→`cve_ent` (zero-padded `'01'..'32'`)
  and `ageb/loc/mun`→`cve_*` + added `cvegeo`. The loaders already handle all of this; just
  don't be surprised.
- **🚫 Never regenerate `variables_enoe_core.yaml`.** It is **hand-curated** from the FD
  dictionary PDF (labels for `clase1`/`clase2`/`pos_ocu`/…). `--variables` **reads** it (it
  overlays the authoritative labelled categories onto the analytical-core columns) but never
  writes it. If a *new* quarter introduces a category value absent from core (validation will
  flag it), **add** the value to `variables_enoe_core.yaml` by hand — do not delete the check.
- **Catalog is pinned** to latest = **2026-T1** (verified 2026-07-10). If INEGI has since
  published newer quarters, that's a catalog re-probe (Units 0–1) — **out of scope here**;
  build what `_enoe_catalog.QUARTERS` contains.
- `data/parquet` and `data/cache` are **git-ignored** (mirror artifacts) — only code, YAML,
  docs, and `registry.txt` are committed.

---

## A. Full 84-quarter build

```bash
# 1. Smoke-test one quarter (fast sanity check of env + network)
uv run python scripts/build_enoe.py --dry-run --periods 2023t1
uv run python scripts/build_enoe.py --periods 2023t1

# 2. FULL build — all 84 quarters × 5 tables (~420 files). LONG & resumable.
#    Recommend background + tee; re-run the same command to resume after any interruption.
uv run python scripts/build_enoe.py 2>&1 | tee /tmp/enoe_build.log
```

Expect a final line like `Done: 84 quarter(s); N table(s) failed/missing.`
- **N should be 0** ideally. Investigate every `MALFORMED`/`MISSING` line:
  - transient download failure → just **re-run** the build (cached good ZIPs are skipped;
    the failed one retries);
  - a genuinely absent quarter/table on INEGI's tree → note it (rare; the catalog was probed,
    but INEGI occasionally pulls a file). Record any true gaps in a short note appended here.
- Confirm the count: `ls data/parquet/enoe_*.parquet | wc -l` → should be ~**420**
  (84 × 5, minus any genuine gaps).

---

## B. Regenerate ALL metadata from the full build (ORDER MATTERS)

`--variables` reads the schema map; `--validate` reads both. **Delete the stale subset
per-group files first** — the full build may renumber/add group ids, and `--variables` writes
the current groups but does not remove orphaned files. The glob below removes only the
**per-group** files (`*_g*.yaml`), **not** the hand-curated `variables_enoe_core.yaml`:

```bash
# 0. Drop stale subset-derived per-group dictionaries (KEEPS variables_enoe_core.yaml)
rm src/mxcensus/_yaml/variables_enoe_*_g*.yaml

# 1. Schema map (COMPLETE now; may contain more groups than the subset's 4–6 per table)
uv run python scripts/build_enoe.py --schema-map

# 2. Per-group variable dictionaries (data-derived categories + core overlay)
uv run python scripts/build_enoe.py --variables

# 3. Inconsistency report
uv run python scripts/build_enoe.py --report-only

# 4. Validation sweep — should be 0 hard failures (or only documented anomalies)
uv run python scripts/build_enoe.py --validate
```

**After regenerating, re-run the core-category cross-check** — a previously-unsampled quarter
may carry a precodificado value absent from `variables_enoe_core.yaml`:

```bash
uv run python - <<'PY'
import yaml, glob, pandas as pd
core = yaml.safe_load(open("src/mxcensus/_yaml/variables_enoe_core.yaml"))
catvars = [k for k,v in core.items() if v["Categorías"]]
seen = {v:set() for v in catvars}
for f in glob.glob("data/parquet/enoe_*.parquet"):
    df = pd.read_parquet(f, columns=None)
    for v in catvars:
        if v in df.columns: seen[v].update(df[v].dropna().unique())
gaps = {v: sorted(seen[v]-set(core[v]["Categorías"])) for v in catvars if seen[v]-set(core[v]["Categorías"])}
print("UNCOVERED (add these to variables_enoe_core.yaml by hand):", gaps or "none — all covered")
PY
```

If `gaps` is non-empty, **edit `variables_enoe_core.yaml`** to add the missing codes (give
them a sensible label; consult the FD PDF `enoe_<code>_fd_c_bas_amp.pdf` under
`inegi.org.mx/contenidos/programas/enoe/15ymas/doc/` — it is AES-encrypted, decrypt with
`qpdf --decrypt --password= in.pdf out.pdf` before `pypdf`), then **re-run steps 2 & 4**.
`--validate` must end at **0 failures** (or failures you can explain as documented source
anomalies, per STEP_5's bar).

**Reconcile the YAML dir in git**: `git status src/mxcensus/_yaml/` — `git add -A` the
`variables_enoe_*` and `enoe_schema_map.yaml` changes (new group files added, stale ones
removed).

---

## C. Registry + upload (Unit 7)

```bash
# 1. Append enoe_* sha256 hashes to registry.txt (preserves census/mg/denue entries).
uv run python scripts/build_enoe.py --update-registry
# Expect: "~420 entries upserted". registry.txt goes from 1408 → ~1828 lines.
git diff --stat src/mxcensus/data/registry.txt   # sanity: only additions, prior entries intact
```

**🔑 Upload — requires `HF_TOKEN` with write access (see §1). If absent, STOP here.**

```bash
export HF_TOKEN=hf_...            # maintainer-supplied, write scope on gperaza namespace
uv run python scripts/upload_hf.py upload --dry-run   # lists only the new enoe_* files
uv run python scripts/upload_hf.py upload             # hf buckets sync data/parquet/*.parquet
uv run python scripts/upload_hf.py verify             # HEAD each resolve URL vs local size
```

`verify` must report `0 missing, 0 size-mismatch`. Then a **clean-cache fetch** proves the
public path works:

```bash
uv run python - <<'PY'
import tempfile, os
os.environ["MXCENSUS_CACHE_DIR"] = tempfile.mkdtemp()   # force a fresh download
from mxcensus.data._registry import POOCH
print("fetched:", POOCH.fetch("enoe_sdem_2023t1.parquet"))
PY
```

---

## D. Unit 8 — CLI, exports, docs, tests (pure code; do after §B so tests match final groups)

Mirror the existing DENUE plumbing exactly.

1. **`src/mxcensus/__init__.py`** — add an "ENOE" import block + `__all__` entries mirroring
   the DENUE ones (see lines ~25, ~35, ~59, ~70):
   - `from mxcensus.enoe import load_enoe, load_enoe_persons`
   - add to the `_resources` import: `variables_enoe, enoe_schema_map, variables_enoe_core`
   - add all five names to `__all__`.

2. **`src/mxcensus/_cli.py`** — the `fetch` subcommand is **state-centric**, but ENOE is
   **national**. Add `"enoe"` to `--dataset` choices and a `--period YYYYtQ` option (parallel
   to `--release`; validate it only applies to `--dataset enoe`, and that `--release` does
   not). For `--dataset enoe`, **ignore the `state` positional** (document it as N/A for ENOE)
   and fetch the five national tables `enoe_{table}_{period}.parquet` (period defaulting to
   `mxcensus.data._enoe_catalog.latest_quarter().period`). Keep the change minimal and
   symmetric with the existing `denue` branch (lines ~19–51).

3. **`tests/test_enoe.py`** — mirror `tests/test_denue.py`. Key rules:
   - **Read `enoe_schema_map()` / group ids DYNAMICALLY** — do **not** hardcode gids or group
     counts (they depend on the build). Parametrize synthetic-frame tests over the tables and
     whatever groups the map currently has.
   - Cover: `_fingerprint` round-trip; `_group_schema(table, gid)` builds and accepts a
     synthetic in-catalog frame and **rejects** an out-of-catalog value (non-vacuous, like
     STEP_5's negative test); `_person_key` alias/era resolution (`ent` vs `cve_ent`).
   - A `@pytest.mark.skipif(not _REAL)` block over `data/parquet/` (present on this remote box
     after §A): assert `load_enoe(table="sdem", period="2023t1")` validates clean, and
     `load_enoe_persons("2023t1")` reproduces the STEP_6 sanity numbers (pob 15+ ≈ 99.7 M,
     unemployment ≈ 2.66 %, informality ≈ 55 %). Guard with `_REAL = (repo/"data"/"parquet"/
     "enoe_sdem_2023t1.parquet").exists()` so the suite stays green offline.
   - `pytest tests/test_enoe.py -q` must pass; also run `pytest` (full) — 93 DENUE tests must
     still pass.

4. **`CLAUDE.md`** — add ENOE to: the module table (`enoe.py`, `_enoe_catalog.py`,
   `build_enoe.py`), the file-naming convention (`enoe_{table}_{period}.parquet`, 84 × 5 =
   ~420 files), the **registry totals** (`1408 → ~1828`), and a build-commands block (the
   `build_enoe.py` modes + a pointer to this handoff). Mirror the DENUE section's depth.

---

## E. End-to-end verification

```bash
uv run pytest -q                                         # ALL green offline (denue + enoe)
uv run python -c "import mxcensus; mxcensus.load_enoe; mxcensus.load_enoe_persons; print('exports OK')"
uv run mxcensus fetch 9 --dataset enoe --period 2023t1   # fetches the 5 national tables
# clean-cache POOCH fetch already done in §C; load a quarter and re-check weighted totals:
uv run python - <<'PY'
from mxcensus.enoe import load_enoe_persons
p = load_enoe_persons(period="2023t1")   # uses the uploaded mirror
print("rows", len(p), "pob15+", f"{p['fac_tri'].sum():,.0f}")
g = p.groupby("clase1")["fac_tri"].sum()
print("PEA", f"{g.get('1',0):,.0f}", "PNEA", f"{g.get('2',0):,.0f}")
PY
```

Reference expectations (2023-T1): rows ≈ 344,205; pob 15+ ≈ 99,747,474; PEA ≈ 60.1 M;
participation ≈ 0.602; unemployment ≈ 2.66 %; informality ≈ 55 %. Full per-era table in
`STEP_6.md`.

---

## F. Commit plan

Commit in logical units (data/parquet is git-ignored — nothing to commit there). Follow the
existing convention and write a short **`docs/enoe/STEP_7.md`** and **`STEP_8.md`** capturing
what you did + any build anomalies (mirror `STEP_2..6.md`), and note in this HANDOFF whether
the full mirror is now live (append a dated "✅ full build uploaded" line at the top).

```bash
# Unit 7 — metadata regenerated from the full build + registry
git add src/mxcensus/_yaml/enoe_schema_map.yaml src/mxcensus/_yaml/variables_enoe_*.yaml \
        docs/enoe/INCONSISTENCY_REPORT.md docs/enoe/VALIDATION_REPORT.md docs/enoe/STEP_7.md \
        src/mxcensus/data/registry.txt docs/enoe/HANDOFF.md
git commit -m "ENOE Unit 7: full-mirror build — regenerate schema map/variables/reports + registry + upload"

# Unit 8 — code, tests, docs
git add src/mxcensus/__init__.py src/mxcensus/_cli.py tests/test_enoe.py CLAUDE.md docs/enoe/STEP_8.md
git commit -m "ENOE Unit 8: exports, --dataset enoe CLI, tests, docs"
```

Push the branch. (Opening a PR to `main` is the maintainer's call.)

---

## G. Optional units (only if asked)

- **Unit 9 — analytical-core harmonization.** In `enoe.py`, add `_RENAME`/capture maps limited
  to the person key + `FAC`→`FAC_TRI`/`FAC_MEN` + precodificado vars, a `_latest_schema`, and
  a `_harmonize`; flip `load_enoe(harmonize=True)` on (it currently raises
  `NotImplementedError`). Verify weighted PEA totals are continuous across the
  2020-T1→2020-T3 and 2021-T2 rename boundaries. Full spec in the project plan
  (`docs/enoe/STEP_*` reference the plan) and mirrors DENUE's `_harmonize`.
- **Unit 10 — ETOE 2020-T2.** Add a separate `etoe` regime/endpoint
  (`inegi.org.mx/contenidos/investigacion/etoe/`) + a `2020t2` special period + its own schema
  group; document its non-comparability to face-to-face ENOE.

---

## Appendix — quick reference

- **Branch**: `enoe-integration`. **Commits so far**: `git log --oneline | grep ENOE`.
- **Subset already built interactively** (what the committed metadata came from):
  `2005t1, 2019t1, 2019t2, 2020t3, 2021t3, 2023t1, 2023t2, 2026t1`.
- **File naming**: `enoe_{table}_{period}.parquet`, table ∈ {viv,hog,sdem,coe1,coe2},
  period = `{year}t{quarter}` (e.g. `2023t1`). No per-state split.
- **Person key** (`enoe._person_key`): `cd_a, ent|cve_ent, con, v_sel, n_hog, h_mud, n_ren`
  (+ `tipo, mes_cal` from 2020-T3, + `ca` for 2020-T3…2021-T2). Base seven are NOT unique in
  the panel era — `tipo`/`mes_cal` are required.
- **Canonical universe**: `R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]` (padding-robust; codes are
  un-padded in the CSV).
- **Weights**: `fac` (pre-2020-T3), `fac_tri`/`fac_men` (after); `load_enoe_persons` exposes a
  numeric canonical `fac_tri`.
- **`build_enoe.py` modes**: (build) `--periods/--tables/--dry-run`, then `--schema-map`,
  `--report-only`, `--variables` (`--cat-threshold`), `--validate`, `--update-registry`.
- **STEP docs**: `docs/enoe/STEP_0_probe.md` (URLs/regimes), `STEP_2..6.md` (per-unit design +
  gotchas). Read them for anything ambiguous here.
