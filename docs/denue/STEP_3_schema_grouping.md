# DENUE mirror — Step 3: schema grouping + variables YAML

Status: **done** (2026-06-02)

## Goal
Group every mirrored file by its exact schema (per release+state, to capture
within-release disagreements), and generate the bundled metadata the loader/validator
will use: `denue_schema_map.yaml` + one `variables_denue_<gNN>.yaml` per group.

## Artifacts produced (bundled in `src/mxcensus/_yaml/`)
- **`denue_schema_map.yaml`** — `fingerprints` (column-list sha256 → group id),
  `groups` (gNN → columns, n_columns, file count, releases), and `latest` (the
  harmonization target). Built by `build_denue.py --schema-map` (scans parquet on disk).
- **`variables_denue_g01..g11.yaml`** — per group: each column's `Descripción`/`Tipo`/
  `Longitud` (parsed from that release's bundled `denue_diccionario_de_datos.csv`) and
  `Categorías` for the personnel-stratum column (from the actual data values). Built by
  `build_denue.py --variables`.

## 11 schema groups (fingerprint = ordered column names)
Grouping is **per (release, state)**, so within-release variants land in their true group:

| group | cols | files | where |
|---|---|---|---|
| g01 | 24 | 33 | 2010 (+2011 state 32, stuck on 2010 schema) |
| g02 | 30 | 31 | 2011 (majority) |
| g03 | 47 | 30 | 2012 (majority) |
| g04 | 47 | 2 | 2012 states 12,14 — **typo'd headers** |
| g05 | 28 | 32 | 2013-Jul |
| g06 | 44 | 32 | 2013-Oct |
| g07 | 41 | 28 | 2015 descriptive (majority) |
| **g08** | 41 | 323 | 2015's 4 mnemonic states **+ 2016→2020** (early mnemonic adopters merged here) |
| g09 | 41 | 1 | 2018-03 state 15 — UPPERCASE headers |
| **g10** | 42 | 252 | 2021→2025 (mnemonic + `clee`) — **`latest`, harmonization target** |
| g11 | 42 | 4 | UPPERCASE-header states (2022-11 19/20/26, 2024-05 11) |

## Key finding for Step 4 — `per_ocu` value drift
The personnel-stratum field is encoded **four different ways** across eras (captured in
each group's `Categorías`):
- **g01/g02 (2010–2011):** UPPERCASE labels + `NO ESPECIFICADO` (`0 A 5 PERSONAS`,
  `251 Y MAS PERSONAS` — note no accent).
- **g03/g04/g06 (2012, …):** numeric **codes** `1`–`7` — plus an anomalous **`13`** in
  2012 (probable data error; flag, map to NA or nearest).
- **g05/g07/g08/g10 (2013→2025):** lowercase accented labels (`0 a 5 personas` …
  `251 y más personas`).

Harmonization must map all encodings → g10's canonical 7 labels (codes→labels,
UPPERCASE→lowercase, `MAS`→`más`, strip ` PERSONAS`, `NO ESPECIFICADO`/`13` → NA).

## Notes
- `clee` (added 2021) has no dictionary description in its first release — left blank.
- Column-name normalization (case/strip/rename, e.g. g09/g11 UPPERCASE, g04 typos) is
  **not** applied here — it's deferred to the Step 4 harmonization spec. The mirror and
  these per-group YAMLs stay faithful to the raw schemas.

## Next — Step 4
`src/mxcensus/denue.py`: `_build_denue_schema(schema_id)` (per-group Pandera schema from
the variables YAML: nullable strings + geometry + `per_ocu` categorical + `codigo_act`
regex), the `harmonization` spec (group→g10: rename, case/strip, `per_ocu` value_remap,
`add_null`/`drop`), `_harmonize`, and `load_denue(*, state, release=None, harmonize=True)`.
Add `variables_denue` / `denue_schema_map` accessors to `_resources.py`.
