# ENOE Unit 11 — Cross-era harmonization (`harmonize=True`)

`load_enoe(..., harmonize=True)` — and the same flag on `load_enoe_persons` /
`load_enoe_viviendas` / `load_enoe_hogares` / `load_enoe_survey` — now canonicalizes the
**analytical core** of any quarter so frames from different eras stack. Previously it raised
`NotImplementedError`.

## Why ENOE harmonization is narrower than DENUE's

DENUE's `_harmonize` projects every release onto the *latest group's exact column list*
(explicit per-group renames + case-fold; unmapped columns dropped). ENOE cannot do that:

- The COE alternates an **ampliado** (Q1) and a **básico** (Q2–Q4) questionnaire. The básico
  groups carry items the latest ampliado group lacks (coe1 g08 vs g09: `p2i…p2k_mes`,
  `p3j1…p3l`, `p5b_*`). Projecting onto g09 would silently drop every básico-only item.
- SDEM renumbered open-text items in 2025-T3 (`cs_p20_des`/`cs_p22_des` →
  `cs_p20a_*`/`cs_p21_des`/`cs_p23_des`) — a questionnaire change, not a rename.

So ENOE harmonization touches only the drift that is well understood and era-wide, and keeps
**every other column verbatim**. The drift, from the 33-group schema map:

| era | raw | harmonized |
|-----|-----|------------|
| 2019-T3/T4 (viv g02, hog g02, coe1 g03, coe2 g03) | `UPPERCASE` names | lowercased |
| ≤ 2020-T1 | `fac`, `est_d`, `t_loc` | `fac_tri`, `est_d_tri`, `t_loc_tri`; `*_men` added as NA |
| ≤ 2020-T1 | no `tipo` / `mes_cal` | added as NA |
| 2020-T3 … 2021-T2 | `ca` | kept (era-only column) |
| ≤ 2025-T2 | `ent`, `mun` (un-padded) | `cve_ent` (2), `cve_mun` (3) zero-padded; `cvegeo` derived |
| ≤ 2025-T2 | `loc`, `ageb` | `cve_loc`, `cve_ageb` — renamed only (blank / `00000` placeholders in every era) |

`cvegeo` = `cve_ent` + `cve_mun`, with `999` when the municipality is blank — verified equal
to INEGI's own `cvegeo` on 100 % of 2026-T1 SDEM rows (including the blank-`mun` rows).

## Implementation (`src/mxcensus/enoe.py`)

- `_RENAME_CORE` / `_GEO_PAD` / `_CORE_ADD` — **generic**, not per-group (unlike DENUE's
  `_RENAME[gid]`), so a new quarter that only adds a fingerprint harmonizes with no map edit.
- `_harmonize(df, table)`: lowercase → rename (refuses a frame that already has both a legacy
  column and its target — never overwrite) → `_zfill_codes` (digits only; NA/blank untouched;
  idempotent on already-padded 2025-T3+ frames) → derive `cvegeo` if absent → NA-fill
  `_CORE_ADD` → core columns first (`_core_order`, from `variables_enoe_core.yaml`), the rest
  in original order. Stale-map guard mirrors DENUE: no `cve_ent`/`fac_tri` after harmonization
  → `warnings.warn("… _RENAME_CORE may be stale")`.
- `_latest_schema(table)`: "tight where safe" — `isin` on the FD-sourced `Categorías` of the
  core columns, numeric weights, width regex on `cve_ent`/`cve_mun`/`cvegeo` (blank allowed),
  nullable `str` otherwise; only the columns every table carries are `required`;
  `strict=False` (questionnaire items are validated per-era by `_group_schema`).
- `load_enoe`: raw validation as before, then `_harmonize` + `_validate(_latest_schema)`.
  The other loaders pass `harmonize=` through; the alias-based key specs already resolve
  `cve_ent`, so indices/joins work unchanged.

## Verification

`tests/test_enoe.py`: synthetic tests (rename/pad/`cvegeo`, uppercase 2019 files, `999`
municipality, idempotence, mixed-era refusal, stale-source warning, `_latest_schema` for all
five tables incl. negative tests), real-quarter tests (one per era, no warnings, column set
differs from raw only by the core renames), `cvegeo` equality with INEGI, the shared-index
survey with `cve_ent`, and the **continuity check**. Suite: 260 passed.

Weighted totals with `harmonize=True` are identical to the raw loader in every quarter
(same rows, same Σ `fac_tri`, same PEA), across all three rename boundaries:

| period | rows | pob 15+ (Σ fac_tri) | PEA |
|--------|-----:|--------------------:|----:|
| 2005t1 | 283,547 | 71,466,330 | 42,106,336 |
| 2019t1 | 300,514 | 93,369,417 | 55,578,352 |
| 2020t1 | 311,756 | 95,151,641 | 57,014,967 |
| 2020t3 | 224,153 | 96,339,397 | 53,571,791 |
| 2021t2 | 288,243 | 97,662,760 | 57,668,254 |
| 2021t3 | 323,604 | 98,118,371 | 58,307,446 |
| 2023t1 | 344,205 | 99,747,474 | 60,089,308 |
| 2025t2 | 324,613 | 102,615,200 | 61,065,005 |
| 2025t3 | 325,108 | 103,068,355 | 61,303,255 |
| 2026t1 | 323,299 | 104,074,365 | 61,113,357 |

## Status: ✅ Unit 11 complete.
