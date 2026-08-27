# ENOE Unit 8 — Exports, CLI, tests, docs

Landed the public plumbing so ENOE is a first-class `mxcensus` data family alongside census /
DENUE. Pure code + docs; mirrors the existing DENUE surface.

## Files

- **`src/mxcensus/__init__.py`** — re-export `load_enoe`, `load_enoe_persons` (from
  `mxcensus.enoe`) and the three resource accessors `variables_enoe`, `variables_enoe_core`,
  `enoe_schema_map` (from `_resources`); all five added to `__all__`.
- **`src/mxcensus/_cli.py`** — `fetch` grew a `--dataset enoe` choice and a `--period YYYYtQ`
  option (parallel to DENUE's `--release`). ENOE is national, so the `state` positional is
  documented as N/A and ignored for `--dataset enoe`; the branch fetches the five national
  tables `enoe_{table}_{period}.parquet` (period defaulting to `latest_quarter().period`).
  Mutual-exclusion guards: `--release` only with `denue`, `--period` only with `enoe`.
- **`tests/test_enoe.py`** (new) — mirrors `tests/test_denue.py`; **118 tests**. Everything is
  read **dynamically** from `enoe_schema_map()` (tables, gids, columns), so nothing hardcodes
  a group id or count — the suite adapts to whatever the build produced (currently 33 groups).
  Coverage:
  - schema-map shape (all five tables, `latest` in `groups`);
  - `_fingerprint` round-trip (`_group_of` resolves each group's columns back to its gid;
    fingerprints match the stored map keys; unknown columns raise);
  - `_group_schema(table, gid)` builds and **accepts** a synthetic in-catalog frame and
    **rejects** an out-of-catalog categorical value (non-vacuous negative test) and a
    non-numeric weight (coercion failure → `SchemaErrors`); `coerce=True` keeps nulls;
  - `_person_key` alias/era resolution — `ent` vs `cve_ent`, panel-era `tipo`/`mes_cal`/`ca`
    widening, intersection-only across tables; `_filter_ent` padding-robustness;
  - exports are callable and in `__all__`; `harmonize=True` raises `NotImplementedError`;
  - a `@skipif(not _REAL)` block (guarded on `data/parquet/enoe_sdem_2023t1.parquet`) that
    loads real quarters and asserts the STEP_6 2023-T1 numbers (rows 344,205; pob 15+
    ≈ 99.7 M; participación ≈ 0.602; unemployment ≈ 2.66 %; informality ≈ 55 %). Because the
    mirror isn't uploaded yet, a `local_mirror` fixture monkeypatches `POOCH.fetch` to resolve
    from `data/parquet/`, so the suite is green offline and hits no network.
- **`CLAUDE.md`** — ENOE added to the module table (`enoe.py`, `data/_enoe_catalog.py`,
  `scripts/build_enoe.py`), the `_resources`/`_cli` rows, the YAML-schemas section, the
  file-naming convention (`enoe_{table}_{period}.parquet`, 84×5 = 420), the registry totals
  (corrected to **128 census + 480 geo + 800 DENUE + 420 ENOE = 1828**; the DENUE line was
  also refreshed 24→25 releases / 768→800 to match the current `registry.txt`), an ENOE
  build-commands block, and a full "ENOE (multi-temporal labor-force survey)" narrative
  section mirroring the DENUE one's depth.

## Verification

- `pytest tests/test_enoe.py -q` → **118 passed**.
- `pytest -q` (full) → **211 passed** (93 DENUE + 118 ENOE), 2 pre-existing DENUE warn-only
  notices unrelated to ENOE.
- `import mxcensus; mxcensus.load_enoe; …` → `exports OK`.
- `mxcensus fetch --help` shows the `enoe` choice + `--period`; the resolution builds the five
  correct filenames. (`mxcensus fetch 9 --dataset enoe --period 2023t1` end-to-end against the
  mirror needs the §C upload first — see STEP_7.)

## Note — one test-suite adjustment vs. the handoff sketch

The handoff's `_REAL` sketch called `load_enoe(period=…)` directly, which fetches from the HF
mirror. Since the ENOE parquet aren't uploaded yet (token-gated), that would 404. The tests
instead use a `local_mirror` monkeypatch (same approach Unit 6 used for its verification), so
they exercise the real loaders against the local build output and stay green offline. Once the
mirror is uploaded the same loaders resolve anonymously with no test change required.

## Status: ✅ Unit 8 complete. Full mirror built + registered; HF upload pending maintainer token.
