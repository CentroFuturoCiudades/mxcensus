# ENOE Unit 10 — 2026-T2 increment (catalog bump + mirror update)

INEGI published `enoe_2026_trim2_csv.zip` after the 2026-07-10 full build. This unit extends
the catalog by one quarter and rolls the mirror forward with the incremental recipe from
`HANDOFF.md` (§A–§C restricted to the new period) — the same steps apply to every future
quarter.

## What was done (2026-08-27, on the maintainer box)

1. `_enoe_catalog.py`: `_LATEST = (2026, 2)`, `CATALOG_VERIFIED_DATE = "2026-08-27"` →
   **85 quarters**; `latest_quarter()` = `2026t2`. Doc counts updated (425 files, registry 1833).
2. `build_enoe.py --periods 2026t2` → 5 parquet, 0 failures (`ENOE_*T226.csv`, utf-8;
   sdem 417 k rows / 115 cols, coe1 344,709 rows / 174 cols = the **básico** layout).
3. Metadata regenerated from the full 425-file dir (`--schema-map`, `--variables`,
   `--report-only`, `--validate`): **still 33 groups** — 2026-T2 joined the existing groups
   (viv g05, hog g06, sdem g04, coe1 g08, coe2 g08); the per-group YAML diffs are category
   reorderings only. **0/425** validation failures; the core-category cross-check found no
   uncovered code.
4. `--update-registry` → 425 `enoe_*` entries, **1833 total**.
5. `upload_hf.py upload` (sync without `--delete`) → the 5 new files + README;
   `resolve/enoe_*_2026t2.parquet` all return 200 with matching sizes; `verify` re-run.

## Note on group stability

Group ids are assigned chronologically, so appending the newest quarter can only add a group
or join one — existing ids never renumber. A future quarter with a new fingerprint would add
`gNN+1` and needs no code change (the loaders read gids from the map; harmonization maps are
generic — see `STEP_11.md`).
