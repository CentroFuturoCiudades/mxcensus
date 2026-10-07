# CPV family — session handoff

**Status (2026-10-07): unit 0 done; next is unit 1a.** Design: [`PLAN.md`](PLAN.md) (the
unit table + session protocol live at its top). What unit 0 found and changed:
[`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration` (local only — not pushed). Unit 0 is committed there; check
`git status` / `git log --oneline -5` first.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo: read `docs/cpv/HANDOFF.md`
> and execute the next unit (1a) following the session protocol in `docs/cpv/PLAN.md`.
> Hand off when the unit is done.

## Next unit — 1a: `scripts/build_cpv.py` build mode + EIC 2025 build

Goal: faithful-raw parquet for EIC 2025 — `cpv_{viviendas,personas,migrantes}_2025_{NN}`
(96 files) + `cpv_estimaciones_2025` (1). Metadata modes (`--schema-map`, `--variables`, …)
are unit 1b. **Do not** touch `registry.txt` in 1a beyond an optional local dry check; the
registry update happens in 1e after validation.

1. Create `scripts/build_cpv.py`, cloned from `scripts/build_enigh.py` (read it first), with:
   - catalog from `mxcensus.data._cpv_catalog` (`EDITIONS_BY_PERIOD`, `find_member`,
     `cpv_zip_entry`, `parse_filename`/`FILE_RE` — import them, don't redefine the regex);
   - flags `--periods` (default: editions enabled for build — start with `2025` only),
     `--tables`, `--states`, `--dry-run` (print URLs + member patterns, no download),
     `--output/--raw-dir/--cache-dir/--retries/--keep-raw`;
   - **loop over (edition, product, state)** — one microdata ZIP yields up to 3 tables
     (`edition.tables_in(product)`); the `estimaciones` ZIP is national (state `None`);
   - statuses `ok/absent/malformed/missing` per table like ENIGH; the sweep continues on
     failure; resumable (cached ZIPs are reused by `fetch_zip_verified`).
2. **Memory — do not use `pandas.read_csv(dtype=str)` for microdata.** Mexico state personas is
   ~70 MB zipped (hundreds of MB of CSV, millions of rows); pandas object strings would need
   tens of GB. Read with `pyarrow.csv` instead:
   - header first → `ConvertOptions(column_types={c: pa.string() for c in header},
     strings_can_be_null=True, null_values=[""])` (only empty cells → null; more faithful than
     pandas' default NA list);
   - `ReadOptions(encoding=…)` from the sniffed encoding — but make the sniff **stream**
     (chunked bytes) instead of `read_bytes()` on a 500 MB file; the 2025 microdata are UTF-8
     without BOM, the estimaciones CSV is **cp1252**;
   - write with `pq.write_table(table, path, compression="zstd")`; check the result matches
     what `_df_to_parquet` would produce (all-string columns, empty → null) on a small file.
3. Smoke locally: `--dry-run --periods 2025`, then `--periods 2025 --states 1 9` and the
   estimaciones file. Record rows/cols/encoding/size per file in `STEP_1a.md`.
   Expected AGS rows: 48,538 dwellings, 177,984 persons, 5,060 migrants; estimaciones 13,880
   rows × 349 cols.
4. Quick structural checks to record (cheap now, gate-relevant later): `ID_VIV` unique in
   viviendas; `ID_PERSONA` unique; `ID_PERSONA[:12] == ID_VIV`?; every person's `ID_VIV` in
   viviendas; `CVE_ENT` constant = state; `CVEGEO == CVE_ENT+CVE_MUN`.
5. Full 2025 build on the `wsl` host (see the `remote-build-host-wsl` memory note): the
   branch must reach `wsl` (push/pull or rsync — ask the user), then
   `nohup .venv/bin/python scripts/build_cpv.py --periods 2025 > build_cpv_2025.log 2>&1 &`.
6. Tests: add build-free tests if any helper is pure (e.g. the multi-member extraction
   plan); keep `pytest -q` green. Then the end-of-session protocol (`STEP_1a.md`, tick the
   table in `PLAN.md`, rewrite this file for unit 1b, memory note, commit with the user's
   go-ahead).

## Open questions for the user

- Commits: the user had unit 0 committed at the end of its session; confirm before committing
  later units unless they say otherwise.
- **Push not yet authorized.** The full 2025 build (step 5) needs the branch on `wsl` — ask the
  user whether to push `cpv-integration` to `origin` or sync it another way.

## Gotchas (carry forward)

- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes) — rely on ZIP integrity.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (venv = CPython 3.14.8 with
  `dev` + `notebook` extras since 2026-10-07).
- Never regenerate a hand-curated core YAML; never `upload_hf.py --delete` from a partial
  local mirror; full builds/uploads run on `wsl` (the Mac has a subset).
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen 2020
  path — `tests/test_census_legacy.py` pins them.
- MG 2025 layers: same projection as 2020 but 5 layers carry an EPSG:6372-named WKT
  (`STEP_0_probe.md` §MG) — decide in 1d.
