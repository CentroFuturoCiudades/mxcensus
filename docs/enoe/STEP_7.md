# ENOE Unit 7 — Full-mirror build + metadata regeneration + registry

Executed the full 84-quarter build on the maintainer box and regenerated every derived
artifact from it (the Units 3–6 metadata had been built from an 8-quarter subset). This is
the step the remote handoff (`docs/enoe/HANDOFF.md`) calls §A/§B/§C.

## A. Full build — 84 quarters × 5 tables

`scripts/build_enoe.py` (no args) downloaded and converted every quarter. Result:
**420 parquet** (`ls data/parquet/enoe_*.parquet | wc -l` → 420), `Done: 84 quarter(s);
0 table(s) failed/missing` after the fix below. Row/column counts match the source CSVs;
faithful-raw `dtype=str` throughout.

### Source anomaly fixed — 2013-T2 SDEM member misnaming (INEGI defect)

The first full sweep reported exactly one gap: `2013t2/sdem: MISSING member sdemt213.csv in
ZIP`. Inspecting the cached ZIP (`2013trim2_csv.zip`) showed the SDEM member is shipped as
**`sdemtT213.csv`** — a stray extra `T` — instead of the canonical `sdemt213.csv`. Every
other quarter/table follows the canonical `{table}t{q}{yy}` core; this is a one-off INEGI
naming typo in that single file.

Handled the way DENUE handles per-release source quirks: a small `_MEMBER_ANOMALIES`
`(period, table) → basename` map in `data/_enoe_catalog.py`, consulted as a fallback in
`find_member` only when the canonical regex misses (so it can never mis-match another file).
Re-running `--periods 2013t2 --tables sdem` (cached ZIP reused) produced
`enoe_sdem_2013t2.parquet` (393,107 rows, 104 cols) → **420/420**. The fix is covered
indirectly by the era-sanity check below (2013-T2 loads and joins cleanly).

## B. Metadata regenerated from the full build (order matters)

Deleted the stale subset per-group dictionaries (`rm variables_enoe_*_g*.yaml`, keeping the
hand-curated `variables_enoe_core.yaml`), then:

1. `--schema-map` → `enoe_schema_map.yaml`. The full build surfaced **33 schema groups**
   (subset had 25): **viv 5, hog 6, sdem 4, coe1 9, coe2 9** — the extra groups are the
   previously-unsampled COE ampliado/básico variants and 2006–2018 drift, exactly as the
   handoff predicted. 8 new per-group files (coe1 g07–g09, coe2 g07–g09, hog g06, viv g05);
   the other 25 were rewritten.
2. `--variables` → 33 `variables_enoe_<table>_<gNN>.yaml` (data-derived categories + core
   overlay).
3. `--report-only` → `INCONSISTENCY_REPORT.md` (per-table group tables over all 84 periods).
4. `--validate` → `VALIDATION_REPORT.md`: **0/420 files failed** their group schema.

**Core-category cross-check** (all 12 core categoricals — `tipo`, `mes_cal`, `c_res`,
`clase1`, `clase2`, `pos_ocu`, `rama_est1`, `rama_est2`, `emp_ppal`, `ing7c`, `seg_soc`,
`c_ocu11c` — against every built file): **none uncovered**. No hand-edit of
`variables_enoe_core.yaml` was needed; the FD-sourced value-sets already cover the full mirror.

## C. Registry

`--update-registry` upserted **420 `enoe_*` entries**; `registry.txt` went **1408 → 1828**
(git diff: 420 insertions only, all prior census/mg/denue entries intact).

## Verification

`load_enoe_persons` weighted totals across eras (via local build output) reproduce INEGI's
published ENOE trajectory and match STEP_6 exactly:

| period | rows | pob. 15+ (Σ fac_tri) | participación |
|--------|-----:|---------------------:|:-------------:|
| 2005t1 | 283,547 | 71,466,330 | 0.589 |
| 2013t2 | 282,771 | 84,300,696 | 0.605 |
| 2019t1 | 300,514 | 93,369,417 | 0.595 |
| 2020t3 | 224,153 | 96,339,397 | 0.556 (COVID) |
| 2023t1 | 344,205 | 99,747,474 | 0.602 |
| 2026t1 | 323,299 | 104,074,365 | 0.587 |

2013-T2 (the anomaly-fixed quarter) loads, joins, and weights cleanly — confirming the
`sdemtT213.csv` fix yielded a valid, analysis-ready SDEM table.

## Upload — pending maintainer `HF_TOKEN`

The HF-bucket upload (`scripts/upload_hf.py upload`) requires an `HF_TOKEN` with write scope
on the `gperaza` namespace, which was **not present** in this session. Per the handoff, all of
§A/§B/§C-registry and the Unit-8 code landed; the actual `hf buckets sync` + `verify` +
clean-cache fetch are left for the maintainer (`export HF_TOKEN=… && python
scripts/upload_hf.py upload && python scripts/upload_hf.py verify`). Until then
`POOCH.fetch("enoe_*")` 404s and the real-data tests resolve from `data/parquet/` via a
`local_mirror` monkeypatch fixture.

## Status: ✅ Unit 7 complete (build + metadata + registry). Upload pending maintainer token.
