# ENOE Unit 6 — Loaders

Fleshed out `src/mxcensus/enoe.py` with the public loaders on top of Unit 5's schema layer.

## API

- **`load_enoe(survey_path=None, *, table, period=None, harmonize=False, ent=None)`** — one
  raw table for one quarter as a faithful `dtype=str` frame. Fetches
  `enoe_{table}_{period}.parquet` from the mirror via Pooch (`period` defaults to
  `latest_quarter()`), or reads an explicit `survey_path`. Optional `ent` (1–32) row filter.
  Resolves the group by fingerprint (`_group_of`, raises on unknown) and validates against
  `_group_schema(table, gid)` (`_validate` — **warns**, doesn't raise). `harmonize=True`
  raises `NotImplementedError` (deferred to Unit 9).
- **`load_enoe_persons(period=None, *, ent=None, canonical_filter=True)`** — the analytical
  person frame: SDEM left-joined with COE1/COE2 on the era-appropriate person key, filtered
  to the canonical universe, with a canonical numeric `fac_tri` weight and boolean
  `is_pea`/`is_ocupado`/`is_informal` flags.

## Design notes (all grounded in the data)

- **Person key** (`_person_key`, `_KEY_SPEC`): ordered logical components, each resolved to
  the first *alias* present in all three tables. Base seven `cd_a`/`ent`/`con`/`v_sel`/
  `n_hog`/`h_mud`/`n_ren`, plus `tipo`/`mes_cal` (2020-T3+) and `ca` (2020-T3…2021-T2). In the
  panel/CATI era the base seven are **not** unique within a quarter file (a person recurs
  across `tipo`/`mes_cal` — 2023-T1 SDEM has 27 415 base-seven duplicates), so the key must
  be taken as wide as the columns allow.
- **`ent`→`cve_ent` rename** (2026-T1's `cve_*` geographic-key rename): the entity component
  resolves across both names (`_ENT_ALIASES`), and `_filter_ent` numerically coerces so it
  works whether codes are un-padded (`'9'`) or zero-padded (`'09'`).
- **Canonical filter** `R_DEF==0 & C_RES∈{1,3} & EDA∈[15,98]` — padding-robust via
  `pd.to_numeric` (the CSV emits `r_def='0'`, not the FD's nominal `'00'`; `eda` has `' '`
  blanks → NaN → excluded).
- **COE join**: only COE columns absent from SDEM are merged, so the ~10 columns COE shares
  with SDEM (`eda`, `fac_tri`, `r_def`, `upm`, …) come from SDEM once. The join never fans
  out — the key is unique in every table.
- **Canonical `fac_tri`**: coalesces `fac_tri` (2020-T3+) or `fac` (earlier) → a numeric
  column for weighted sums.

## Bug caught during verification — silent 2026-T1 fan-out

Before the `ent`/`cve_ent` alias fix, `load_enoe_persons("2026t1")` dropped the entity from
the key (2026 renamed `ent`→`cve_ent`), producing a **3× fan-out** (687 k rows) and a
**286 M** "population" — and since `latest_quarter()` is 2026-T1, the default
`load_enoe_persons()` was affected. Fixed by alias-resolving the entity component, and added
a **fan-out guard**: if the person key isn't unique in SDEM, the loader `warns` loudly rather
than silently inflating totals (so a future unhandled key rename fails visibly).

## Verification

`load_enoe(table="sdem", period="2023t1")` validates clean (no warnings); `harmonize=True`
raises. `load_enoe_persons("2023t1")` row count (344 205) equals the filtered SDEM count; no
fan-out. Weighted totals across every built era match INEGI's published ENOE trajectory:

| period | rows | pob. 15+ (Σ fac_tri) | tasa participación |
|--------|-----:|---------------------:|:------------------:|
| 2019t1 | 300,514 | 93,369,417 | 0.595 |
| 2020t3 | 224,153 | 96,339,397 | 0.556 (COVID) |
| 2021t3 | 323,604 | 98,118,371 | 0.594 |
| 2023t1 | 344,205 | 99,747,474 | 0.602 |
| 2023t2 | 329,632 | 100,050,783 | 0.602 |
| 2026t1 | 323,299 | 104,074,365 | 0.587 |

2023-T1 detail matches INEGI exactly: unemployment 2.66 %, informality 55.1 %. `ent=9`
(Jalisco) on 2026-T1 (via `cve_ent`): 8.1 M pob 15+. The fan-out guard does not false-fire on
any of the 8 built quarters. All 93 DENUE tests still pass.

## Note — mirror fetch pending Unit 7

The ENOE parquet aren't uploaded to the HF bucket yet (Unit 7), so `POOCH.fetch` 404s for
now; this unit was verified via `survey_path=` and a monkeypatched `POOCH.fetch` pointing at
`data/parquet/`. Once Unit 7 uploads + registers, `load_enoe(period=…)` resolves anonymously.
The subset caveat also persists — a quarter absent from the (partial) schema map raises in
`_group_of` until the full build regenerates it.

## Status: ✅ Unit 6 complete — proceed to Unit 7 (registry + upload).
