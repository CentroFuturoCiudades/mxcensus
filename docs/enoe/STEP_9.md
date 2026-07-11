# ENOE Unit 9 — Dwelling/household loaders + shared-multi-index survey loader

Added analysis-ready loaders for the two non-person household-survey tables, and a combined
loader that returns all three levels with a shared, nested `MultiIndex` — the way the extended
census microdata shares `ID_VIV` / `[ID_VIV, ID_PERSONA]`. Pure code + docs; the mirror and
schema layer are untouched.

## Motivation

Before this, ENOE exposed only `load_enoe` (raw `dtype=str`) and `load_enoe_persons` (the
analysis-ready person frame). `viv` (dwelling) and `hog` (household) had no analysis-ready
loader — users had to coerce weights by hand — and there was no way to load the three levels
together with an aligned index.

## Key hierarchy (single source of truth)

ENOE's survey nests **dwelling ⊂ household ⊂ person**, and the three natural keys are clean
*prefixes*, verified **unique at each level** against real data for both a modern and an old
quarter (2023-T1 and 2005-T1):

| level | key | unique in |
|-------|-----|-----------|
| dwelling | `cd_a, ent(\|cve_ent), con, v_sel` + `tipo, mes_cal[, ca]` (2020-T3+) | `viv` |
| household | dwelling key + `n_hog, h_mud` | `hog` |
| person | household key + `n_ren` | `sdem` |

`enoe.py` now defines these as nested constants and one resolver:

```python
_DWELLING_KEY_SPEC  = [("cd_a",), _ENT_ALIASES, ("con",), ("v_sel",), ("tipo",), ("mes_cal",), ("ca",)]
_HOUSEHOLD_KEY_SPEC = _DWELLING_KEY_SPEC + [("n_hog",), ("h_mud",)]
_PERSON_KEY_SPEC    = _HOUSEHOLD_KEY_SPEC + [("n_ren",)]
_level_key(spec, *frames)   # first alias present in all frames → clean per-era prefix
_person_key(*frames) = _level_key(_PERSON_KEY_SPEC, *frames)
```

The panel identifiers `tipo`/`mes_cal`/`ca` sit in the **dwelling** portion (they distinguish a
dwelling across panel visits), so the prefixes stay clean. This **reorders** `_person_key`'s
output vs the old `_KEY_SPEC` (`tipo`/`mes_cal`/`ca` now precede `n_hog`/`h_mud`/`n_ren`), but the
column **set** is unchanged — `load_enoe_persons`'s joins, fan-out guard, and canonical filter are
all order-insensitive, so behavior is identical. One ordering assertion in
`tests/test_enoe.py::test_person_key_widens_in_panel_era` was updated to the new order.

## New public API

- `load_enoe_viviendas(period=None, *, ent=None)` — `viv` with numeric `fac_tri`/`fac_men`
  (`_coalesce_fac_tri`, coalescing the pre-2020-T3 `fac`) and the dwelling-key `MultiIndex`
  (`_index_level`, sorted; warns if non-unique).
- `load_enoe_hogares(period=None, *, ent=None)` — `hog` with numeric weights and the
  household-key `MultiIndex`.
- `load_enoe_survey(period=None, *, ent=None, persons="all")` — returns the plain tuple
  `(viviendas, hogares, personas)` with the shared nested index. `persons="all"` (default) =
  full `sdem` (every household member → households fully decompose); `persons="labor"` = the
  `load_enoe_persons` working-age analytical frame (COE-joined, canonical filter, flags — only
  interviewed 15+ members, so per-household person sums don't reconstruct full household size).

The keys live in the index only (as the census loaders do). `load_enoe_persons` is unchanged
(stays flat); only `load_enoe_survey` sets the person `MultiIndex`. Validation is inherited from
`load_enoe` (structural raise / value-level warn); the new loaders only reshape.

## Verification

- `pytest tests/test_enoe.py -q` → **131 passed** (was 118); full `pytest -q` → **224 passed**
  (93 DENUE untouched).
- Real-mirror checks (2023-T1 and 2005-T1): unique `MultiIndex` at every level; `fac`→`fac_tri`
  coalescing on 2005-T1; clean prefix nesting (`viv` ⊂ `hog` ⊂ `per`); plausible weighted totals
  (2023-T1: ≈37.3 M dwellings, ≈37.5 M households); `persons="all"` = 450,263 rows ⊇
  `persons="labor"` = 344,205; `ent=` restricts all three frames. A worked example
  (persons-per-household via `per.groupby(level=hog.index.names)`, mean ≈ 3.44) is in the README.

## Status: ✅ Unit 9 complete — dwelling/household + combined shared-index loaders.
