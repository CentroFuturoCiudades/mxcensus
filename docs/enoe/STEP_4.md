# ENOE Unit 4 — Variable dictionaries

Added the variable-dictionary layer: a hand-curated analytical core, a data-derived
per-group generator, and the `_resources.py` accessors.

## Files

- **`src/mxcensus/_yaml/variables_enoe_core.yaml`** (hand-curated) — the ~24 variables that
  matter for labor-force analysis, with authoritative labels/categories: the person key
  (`cd_a`/`ent`/`con`/`v_sel`/`n_hog`/`h_mud`/`n_ren` + `tipo`/`mes_cal`), the
  canonical-universe filter columns (`r_def`/`c_res`/`eda`), the expansion weights
  (`fac`/`fac_tri`/`fac_men`), and the precodificado analytical variables
  (`clase1`/`clase2`/`pos_ocu`/`rama_est1`/`rama_est2`/`emp_ppal`/`ing7c`/`seg_soc`/`c_ocu11c`).
- **`src/mxcensus/_yaml/variables_enoe_{table}_{gNN}.yaml`** (generated, 25 files) — one per
  (table, schema group) from the schema map; column category value-sets for validation.
- **`src/mxcensus/_resources.py`** — `variables_enoe(table, gid)`, `enoe_schema_map()`,
  `variables_enoe_core()` (lazy `@functools.cache`, mirroring `variables_denue` /
  `denue_schema_map`).
- **`scripts/build_enoe.py`** — new `--variables` mode (`--cat-threshold`, default 64).

## Sourcing the core labels (FD PDF)

Labels/categories were transcribed from INEGI's ENOE **FD dictionary**
(`enoe_123_fd_c_bas_amp.pdf`, 2023-T1 / 2024 edition, "Estructura de la tabla de datos del
sociodemográfico", fields on pp. 15–28). INEGI ships the PDF **AES-encrypted** (empty
password); `pypdf` couldn't open it until `qpdf --decrypt` produced a readable copy. The FD
was read directly (not programmatically parsed — the plan defers FD parsing), giving:

- `clase1` 1=PEA/2=PNEA · `clase2` 1=ocupada/2=desocupada/3=disponible/4=no disponible ·
  `pos_ocu` 1–5 · `rama_est1` 1=Primario/…/4=No especificado · `rama_est2` 1–11 ·
  `emp_ppal` 1=informal/2=formal · `ing7c` 1–7 · `seg_soc` 1–3 · `c_ocu11c` 1–11 ·
  `tipo` 1=ENOE/2=ENOE-CATI · `mes_cal` months 01–12 · `c_res` 1–3.

**Universe & the `0` fill.** The FD's "Variables precodificadas" note pins the canonical
filter — `R_DEF == '00' AND C_RES in {1,3} AND EDA in [15,98]`. The FD's "Códigos válidos"
does **not** list `0`, but every precodificado column carries `0` in the data for records
outside that universe; the core file includes it as *"No aplica (fuera del universo
analítico)"* so `isin` checks accept it. Cross-checked: the core categories cover **every**
value observed across the 8 built quarters (all 11 checked vars, 100% covered).

## `--variables` design

`_build_categories` enumerates distinct values per column across a group's files and drops
any column exceeding `--cat-threshold` (high-cardinality / continuous / free-text — weights,
control numbers, the `*_des` open-text fields including the STEP_2 mojibake columns are all
dropped). `_write_variables_yaml` then writes each column as
`{Descripción, Tipo, Longitud, Categorías}`:

- **analytical-core columns** take their entry **verbatim from `variables_enoe_core.yaml`** —
  the complete, FD-sourced, labelled value-set. This keeps the `isin` value-set robust
  despite a partial build and lets validation *flag* out-of-catalog anomalies (mirrors DENUE
  labelling its coded fields from a catalog rather than from the data).
- **all other columns** get a blank description + the data-derived identity category map.

## ⚠️ Subset-derived (same caveat as Unit 3)

The 25 generated `variables_enoe_{table}_{gNN}.yaml` were produced from the 8-quarter subset,
so **non-core** category value-sets are only as complete as the built data. The **core**
categories are complete and authoritative (FD-sourced), so the analytically important `isin`
checks are unaffected. The maintainer regenerates all 25 with `--variables` after the full
build (which may add groups and widen non-core value-sets).

## Verification

- `--variables` wrote 25 files (viv 4, hog 5, sdem 4, coe1 6, coe2 6).
- Spot-check `variables_enoe_sdem_g03.yaml`: `clase1`/`pos_ocu` carry the labelled core
  categories (`pos_ocu` includes valid code `5` unobserved in the subset); non-core
  `cs_p20a_1` keeps its data-derived values; `cs_p21_des` (open text) correctly has no
  categories.
- Accessors: `enoe_schema_map()` → 5 tables; `variables_enoe("sdem","g03")` → 114 cols,
  `clase1` keys `{0,1,2}`; `variables_enoe_core()` → 24 vars; second call returns the **same
  cached object**; `clase1` keys ⊇ `{1,2}`.

## Status: ✅ Unit 4 complete — proceed to Unit 5 (validation schemas + report).
