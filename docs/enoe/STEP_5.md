# ENOE Unit 5 — Validation schemas + report

Added the validation layer: the per-group Pandera schema in a new loader module plus a
maintainer `--validate` sweep.

## Files

- **`src/mxcensus/enoe.py`** (new) — the ENOE loader module's **schema layer**:
  `_fingerprint(columns)` and `_group_schema(table, gid)`. The public loaders
  (`load_enoe` / `load_enoe_persons`) and analytical-core harmonization arrive in Unit 6;
  this unit adds only what validation needs, matching how `build_denue.py --validate`
  imports `_group_schema` from `mxcensus.denue`.
- **`scripts/build_enoe.py`** — new `--validate` mode → `docs/enoe/VALIDATION_REPORT.md`.

## `_group_schema(table, gid)` design

Built from the group's bundled `variables_enoe_{table}_{gid}.yaml`, per the plan
("ID keys as string columns, weights numeric/Int64, precodificado vars `isin` their
category keys"):

- **weights** (`fac`/`fac_tri`/`fac_men`) → numeric type check (`pa.Column(float,
  coerce=True)`; the raw frame is `dtype=str`, so numeric-coercibility is the guarantee —
  they are integer expansion factors but `float` avoids false-fails on any decimal era);
- **columns with a non-empty `Categorías`** → strict `isin` on the keys. For the
  analytical-core columns these are the complete FD-sourced value-sets (so a future
  out-of-catalog value fails), for others the data-enumerated values;
- **everything else** → nullable string.

`strict=False` ignores extra columns; `coerce=True` parses the string frame for the checks.
`@functools.cache`d on `(table, gid)`.

## Bug caught during verification — `mes_cal` encoding

The first validation run failed **every** SDEM/VIV row on `mes_cal`. Root cause: the
hand-curated core (Unit 4) assumed zero-padded month codes `01`–`12` (from the FD's
"Longitud 2"), but the **CSV emits them un-padded** (`1`,`2`,`3`), plus per-quarter special
codes (Q1=`96`, Q2=`97`, Q3=`98`, Q4=`99`) for records with no specific calendar month. My
Unit-4 cross-check had omitted `mes_cal`, so it slipped through. Fixed `variables_enoe_core.yaml`
(`1`–`12` + `96`–`99`) and regenerated the 25 per-group files. The cross-check now covers
**all** core categoricals against all built data (100% covered).

## Verification

- **`--validate` over the 8 built quarters (40 files): 0 hard failures.**
- **Non-vacuous** — a negative test (inject `clase1='9'`, `fac_tri='NOTANUMBER'` into an
  SDEM frame) is caught: `clase1 / isin(['0','1','2'])` and `fac_tri / dtype('float64')`.
- The report notes that value-level anomalies which are **not** schema violations — the
  mangled Ó/Ñ in the SDEM open-text `cs_p21_des`/`cs_p23_des` (STEP_2), faithful to INEGI's
  source — do not appear, because free-text columns carry no `isin`/regex check. This is the
  same acceptance bar as `docs/denue/` (schema-based sweep; data-quality lives in the
  narrative).

## Caveats

- Same **subset** caveat as Units 3–4: over the built subset, `isin` on *data-derived*
  (non-core) categories passes by construction; its purpose is to flag drift on future/full
  data. The **core** categories are complete/authoritative, so those checks are meaningful
  even here. Regenerate schema map + variables + validation after the full build.
- `_validate` (the loader's warn-not-raise wrapper) and `_group_of` are **not** here yet —
  they belong with the loaders in Unit 6. The build's `--validate` does its own hard
  pass/fail reporting (like DENUE's), so it needs neither.

## Status: ✅ Unit 5 complete — proceed to Unit 6 (loaders `load_enoe` / `load_enoe_persons`).
