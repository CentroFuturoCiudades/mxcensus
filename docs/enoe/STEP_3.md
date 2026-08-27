# ENOE Unit 3 — Schema map + inconsistency report

Added two "no-download, scan parquet on disk" modes to `scripts/build_enoe.py` and the two
artifacts they produce:

- `--schema-map` → `src/mxcensus/_yaml/enoe_schema_map.yaml`
- `--report-only` → `docs/enoe/INCONSISTENCY_REPORT.md`

## Design — per-table schema groups

The five ENOE tables (`viv`/`hog`/`sdem`/`coe1`/`coe2`) have **independent** schema
histories, so — unlike the flat `g01..` namespace of `denue_schema_map.yaml` — the map is
**namespaced per table**: top-level keys are the table names, and each carries its own
`latest` / `fingerprints` / `groups`, with group ids restarting at `g01` within each table.

- `_fingerprint_cols(cols)` = `sha256(json.dumps(list(cols)))` — **identical recipe** to the
  loader's future `mxcensus.enoe._fingerprint`, so a mirrored file matches its map entry.
  Column *names* (not dtypes) define the schema (dtypes are uniform under `dtype=str`).
- `_scan_enoe_parquet` reads only schema/metadata (no full load); `_group_schemas` assigns
  groups in **period order** (so `g01` = earliest schema seen) and sets `latest` to the group
  of each table's most recent period.
- `_write_schema_map` writes the YAML; `_write_report` writes the markdown: per table an
  inventory (period → group, cols, rows), the distinct groups (columns), consecutive-period
  schema drift (added/removed columns), and the catalog quarters still missing from the
  mirror.

Both generated files are **regenerable** and carry no provenance comments (matching the
DENUE convention) — the maintainer reruns these modes after any (re)build.

## ⚠️ Subset-derived — regenerate from a full build before release

A full 84-quarter build (~2.5 GB over INEGI's throttled link) is impractical in one
session, so the committed `enoe_schema_map.yaml` / `INCONSISTENCY_REPORT.md` were generated
from a **representative 8-quarter subset** chosen to hit every documented era boundary and
the COE ampliado/básico split:

`2005t1, 2019t1, 2019t2, 2020t3, 2021t3, 2023t1, 2023t2, 2026t1`

They are a correct, reproducible snapshot **of that subset** — the report's "Missing
quarters" section lists the 76 absent quarters, so its partial nature is self-documenting.
The map degrades gracefully for the loader (an unbuilt quarter whose fingerprint is absent
→ the loader warns, doesn't crash). **Before release, the maintainer must run the full build
then `--schema-map` / `--report-only` to produce the complete map** (which may reveal
additional groups in the un-sampled quarters — e.g. Q3/Q4 COE básico variants, intra-old-era
drift 2006–2018). `latest` is already correct (2026t1 is the true latest quarter).

## Verification (8-quarter subset, all 40 files built, 0 failures)

Group counts per table (small, matching the ~4 eras + COE ampliado/básico):

| table | groups | periods → group |
|-------|:------:|-----------------|
| viv   | 4 | 104-era `g01`(05/19) · `g02`(20t3) · `g03`(21t3,23) · `g04`(26t1) |
| hog   | 5 | one per era + 26t1 |
| sdem  | 4 | `g01`=104 (05/19) · `g02`=110 (20t3) · `g03`=114 (21t3,23) · `g04`=115 (26t1) |
| coe1  | 6 | ampliado/básico × era |
| coe2  | 6 | ampliado/básico × era |

Plan verification points — all confirmed:

1. **2019 vs 2023 SDEM in different groups** — SDEM `g01` (104 cols, incl. 2019t1/t2) vs
   `g03` (114 cols, incl. 2023t1/t2). ✓
2. **2021-Q3 SDEM shows the migration-var group** — SDEM 2021t3 is `g03`, distinct from
   2020t3's `g02`. The `g02→g03` delta is exactly: **removed** `ca` (confirming the "CA only
   2020t3–2021t2" rule) + `cs_p20_des`/`cs_p22_des`; **added** the migration/place-of-work
   vars `cs_p20a_1, cs_p20a_c, cs_p20b_1, cs_p20b_c, cs_p20c_1, cs_p21_des, cs_p23_des`. ✓
3. **COE ampliado/básico split** — COE1 2023t1 (189, Q1 ampliado) vs 2023t2 (172, Q2 básico)
   swap ~80/63 question columns (`p3l*`/`p3m*` vs `p2i`/`p2j`/`p2k*`); COE2 2023t1 (137) vs
   2023t2 (82) likewise. The same split appears in the old era (2019t1 vs 2019t2). ✓

Bonus drift captured: SDEM `g01→g02` added precisely the ENOEN weight/strata split
(`fac_tri`/`fac_men`, `est_d_tri`/`est_d_men`, `t_loc_tri`/`t_loc_men`, `tipo`, `mes_cal`),
matching STEP_0; and 2026t1 renamed the geographic keys `ageb/ent/loc/mun` →
`cve_ageb/cve_ent/cve_loc/cve_mun` + new `cvegeo` across all tables (its own `g04`/`g05`).

The data-level encoding anomaly noted in STEP_2 (mangled Ó/Ñ in two open-text SDEM fields)
is a *value*-level issue, not a schema one, so it belongs to Unit 5's validation report — it
does not affect the fingerprint groups here.

## Status: ✅ Unit 3 complete (subset-derived artifacts; full regenerate deferred to release)
— proceed to Unit 4 (variable dictionaries).
