# CPV family — session handoff

**Status (2026-10-07): units 0, 1a, 1b and 1c are done; next is unit 1d (Marco
Geoestadístico EIC 2025).** Design: [`PLAN.md`](PLAN.md) (unit table and session protocol at
the top). What 1c built and found: [`STEP_1c.md`](STEP_1c.md); earlier units:
[`STEP_1b.md`](STEP_1b.md), [`STEP_1a.md`](STEP_1a.md), [`STEP_0_probe.md`](STEP_0_probe.md).

Branch: `cpv-integration`, pushed to `origin`. 1c is two commits: code + tests, then docs.
`wsl:~/mxcensus` is on the branch and holds the full EIC 2025 mirror (97 `cpv_*_2025*`
files) and the dictionaries. The Mac has states 01, 09, 15 + estimaciones. Check `git status`
/ `git log --oneline -5` on both hosts first, and `git pull --ff-only` wherever you are
behind.

## Kickoff prompt for the next session

> Continue the CPV census-family integration in this repo (branch cpv-integration).
> Read docs/cpv/HANDOFF.md first, then the parts of docs/cpv/PLAN.md it points to,
> and execute the next unit (1d: Marco Geoestadístico EIC 2025 — full
> build_marco_geo.py --period 2025 on wsl, load_mg(layer, *, state, period), tests, the
> CRS-spelling decision) following the session protocol at the top of PLAN.md. Use
> .venv/bin/python, not uv run. Ask me before pushing, installing packages, or running
> anything on the wsl host. When the unit's gate is met, write docs/cpv/STEP_1d.md, tick
> the unit table, rewrite HANDOFF.md for unit 1e, update the memory note, ask me before
> committing, and give me the next handoff prompt.

## Next unit — 1d: MG EIC 2025 (geometry)

Gate: 480 `mg_{sfx}_2025_{NN}.parquet` files built on `wsl` (15 layers × 32 states), and
`load_mg` tested.

1. **Read first**:
   - `PLAN.md` §Architecture → **Files** (MG naming) and the `load_mg` bullet under
     **Loaders**;
   - `STEP_0_probe.md` §"Marco Geoestadístico editions": UPCs, the per-state ZIP layout,
     and the state-01 smoke conversion (same 15 layers and columns as 2020, the CRS WKT
     spelling);
   - `scripts/build_marco_geo.py` (`--period`, `mg_filename`, period-qualified cache/raw
     dirs since unit 0);
   - `data/_catalog.py` (`MgEdition`, `MG_EDITIONS`, `marco_geo_zip_url`, `mg_filename`);
   - `aggregate.load_mg_census`. It is the **frozen** legacy 2020 path, so do not re-point
     it.
2. **Build on `wsl`** (ask first): `python scripts/build_marco_geo.py --period 2025`, all
   32 states.
   - Smoke-test `--states 1` first.
   - The ZIPs are ~38 MB (AGS) to a few hundred MB each, and INEGI serves at ~0.3–0.7 MB/s,
     so expect hours.
   - Launch it with the Bash tool's `run_in_background` (Tailscale SSH does not return on
     `nohup … &`), with a log.
   - It appends the `mg_*_2025_*` hashes to `registry.txt` on `wsl`. Decide whether to
     commit them in 1d or leave all registry work to 1e (PLAN puts it in 1e). Never run
     `upload_hf.py --delete`.
3. **Decide (record in `STEP_1d.md`)**: 5 layers (`ar`, `ent`, `fm`, `lpr`, `mun`) carry
   an EPSG:6372-named WKT, where 2020 has a custom "MEXICO_ITRF_2008_LCC" name. The
   projection is the same LCC, so `crs ==` is False across years although the coordinates
   are comparable. Either normalise the CRS object at build time, against the faithful-raw
   rule, or keep it and document it, perhaps adding a `load_mg(..., crs=)` / comparison
   helper.
4. **`load_mg(layer, *, state, period="2020")`**: probably in `aggregate.py` or a new
   `mg.py`; choose and record.
   - 2020 reads the legacy `mg_{sfx}_{NN}`; other periods read `mg_{sfx}_{period}_{NN}`.
   - `state` can be an int or a sequence (concat), with the same semantics as `load_cpv`
     (`cpv._states`).
   - Returns a GeoDataFrame.
   - `CVEGEO` stays a string, so it joins `load_cpv_estimaciones` and the microdata
     `CVEGEO`/`CVE_*`.
   - Export it; test it offline (synthetic geoparquet in `tmp_path`) and `_REAL` on local
     files, using a `local_mirror` fixture as in `tests/test_cpv.py`.
   - Optional data check: every estimaciones municipality (`NIVEL == municipal`) has an
     `mg_mun_2025` polygon, and the reverse.
5. **CLI**: `--dataset mg --edition` should follow the 1c decision for `cpv` and move to 1e
   with the registry, so the CLI never offers unregistered files. Confirm with the user.

## Open questions for the user

- The `mg` CLI: in 1d or with the registry in 1e (recommended: 1e, as for `cpv`).
- Commit the `mg_*_2025` registry lines from `wsl` in 1d, or leave the whole registry to 1e.
- Commits: ask before committing (the user's standing instruction for this family).

## Gotchas (carry forward)

- **Metadata modes run on `wsl` only.** `build_cpv.py --schema-map`/`--variables`/
  `--report-only` on the Mac's 3-state mirror would overwrite the committed 32-state map and
  report.
- **The registry has no `cpv_` entries until 1e.** `POOCH.fetch("cpv_…")` fails outside the
  tests' `local_mirror` fixture, and the CLI for `cpv` (and `mg` 2025) waits for 1e.
- **`_schema_groups.label_frame` changed in 1c** (all families): categoricals are built
  directly as `Categorical`s, mapping only distinct values. It is identical on
  ENOE/ENIGH/CPV (`STEP_1c.md`) and up to 14× faster on large frames. A missing label is `NaN` in a
  `Categorical`, no longer `None` in an object column.
- **EIC 2025 coverage**: 750 municipalities censados, 1,721 muestreados and 7 with
  insufficient sample. The plan's first guess of 753 was wrong (`STEP_1c.md`). Every Σ
  `FACTOR` equals the published estimates exactly, nationally and per state, municipality
  and ≥50k locality.
- **Memory**: `load_cpv_survey(state=15)` peaks at 6.4 GB RSS on the Mac (read + raw
  validation + index sort + strict validation; the result is 1.1 GB). Loading many big
  states at once multiplies that.
- `variables_cpv_core.yaml` is hand-curated: never regenerate it. After editing it, rerun
  `--variables` on `wsl` (the core is copied verbatim into every group file; a test checks
  this).
- INEGI soft-404s: HTTP 200 + `text/html` (2263 bytes). Rely on ZIP integrity.
- `uv run` may re-sync/recreate `.venv`; use `.venv/bin/python` (Mac: CPython 3.14.8 with
  `dev` + `notebook`). Both hosts run pyarrow 24.0.0 / pandas 3.0.3.
- With Tailscale SSH, `ssh wsl 'nohup … &'` does not return until the job ends. Launch long
  jobs with the Bash tool's `run_in_background`.
- Faithful raw in `cpv_*`: `null_values=[""]` only, so `NA`/`MI` strings stay verbatim
  (declared `Especiales`); `load_cpv_estimaciones` turns them into missing values.
- Never `upload_hf.py --delete` from a partial local mirror. Full builds and uploads run on
  `wsl`.
- `scripts/build_data.py` / `aggregate.py` / `extended_*.py` / legacy files are the frozen
  2020 path, pinned by `tests/test_census_legacy.py`.
