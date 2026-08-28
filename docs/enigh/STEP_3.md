# ENIGH Unit 3 — wiring, tests, docs

- `_resources.py`: `variables_enigh(table, gid)`, `enigh_schema_map()`, `variables_enigh_core()`.
- `__init__.py`: exports the five loaders + three accessors.
- `_cli.py`: `--dataset enigh --edition YYYY` (state positional ignored; fetches the edition's
  published tables). The per-family selector-flag exclusivity checks are now a small table
  (`release`/`period`/`edition`).
- `scripts/_build_common.py`: `PRESERVE_PREFIXES += "enigh_"`.
- `tests/test_enigh.py` (185 tests): catalog (99 files, regimes, absent tables, member
  spellings), dynamic per-(table, group) fingerprint/schema tests, negative `isin`/numeric
  tests, key nesting, `ent` filter, synthetic harmonization (renames, 5/9-char `ubica_geo`,
  `poblacion` keeps person `sexo`/`edad`, idempotence, mixed-era refusal, uppercase, stale
  warning), `_latest_schema` per table incl. negatives; `_REAL`-guarded real tests over all
  nine editions (no warnings, unique nested indices, factor never null, published household
  totals, raw ≡ harmonized totals, survey nesting, `ent` filter, 2008 dwelling error).
- Docs: README (datasets table, ENIGH section with the 2016 break and 2024 changes, accessors,
  source/citation, transformation notice), CLAUDE.md (module rows, YAML inventory, naming,
  totals 1932, build block, narrative), `docs/hf_bucket_readme.md`.
