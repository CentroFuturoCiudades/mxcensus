# ENIGH Unit 2 — loaders + core-only harmonization (`src/mxcensus/enigh.py`)

## Keys and weights (verified on every edition)

- `folioviv` ⊂ `(folioviv, foliohog)` ⊂ `(folioviv, foliohog, numren)` are unique in
  `viviendas` / `hogares`+`concentradohogar` / `poblacion` respectively and nest (every
  household's dwelling exists). No aliases or panel widening needed (unlike ENOE).
- `folioviv[:2]` is the state code in every edition and table (= `ubica_geo[:2]` where
  present) → `ent=` filter works on any table (`_filter_ent`).
- Weights: `factor` (2008–2010, 2016+), `factor_hog`/`factor_viv` (2012–2014). Present in
  `concentradohogar` always, in `viviendas` always, in `hogares` 2008–2014 and 2022+, and in
  every table from 2022. `_attach_factor` joins `factor` (+ `ubica_geo`/`tam_loc`) from
  `concentradohogar` on the household key when a table lacks it — exact, never fans out
  (the factor is constant within a dwelling).

## API

- `load_enigh(table=, period=, harmonize=, ent=)` — raw table; refuses a table the edition
  does not publish (`viviendas` 2008/2010, `gastos` outside 2008/2010, …).
- `load_enigh_hogares` = `concentradohogar` (INEGI's per-household summary) with numeric
  `factor`, `ing_cor`, `ingtrab`, `gasto_mon`, `tot_integ`, `edad_jefe`; household index.
- `load_enigh_viviendas` (2012+), `load_enigh_personas` (`poblacion` + factor, numeric `edad`).
- `load_enigh_survey` → `(viviendas, hogares, personas)`, shared nested index.

## Harmonization (core-only, like ENOE's)

`_RENAME_ALL = {factor_hog, factor_viv → factor}`; `_RENAME_TABLE["concentradohogar"]` folds
the 2008/2010 spellings (`ingcor→ing_cor`, `tam_hog→tot_integ`, `n_ocup→ocupados`,
`pering→percep_ing`, `perocu→perc_ocupa`, head `sexo/edad/ed_formal → sexo_jefe/edad_jefe/
educa_jefe`) — **table-scoped** because `poblacion` legitimately has person-level `sexo`/`edad`.
`educa_jefe` zero-padded to 2. Geography derived from `ubica_geo` (`cve_ent`=[:2],
`cve_mun`=[2:5], `cve_loc`=[5:9] when 9 chars, `cvegeo`=[:5]); without `ubica_geo`, `cve_ent`
from `folioviv`. Mixed-era frames (source + target both present) raise; a frame with neither
`ubica_geo` nor `folioviv` warns (stale map). Core columns lead, everything else verbatim.
`_latest_schema(table)`: `isin` on the padded core codes, numeric amounts/weights, width
regex on `cve_*`; only `folioviv`/`cve_ent` required.

**Not harmonized (by design):** expenditure/income `clave` catalogs (CCIF-2018 re-basing in
2024), questionnaire items renamed in 2024 (`atenc_ambu→ambul_serv`, `hospital→aten_hosp`,
`medicinas→medic_prod`), and — above all — the 2014→2016 series break: the loaders align
names, not estimates.

## Verification

Every edition loads raw and harmonized with zero warnings; row counts, Σ `factor` and
Σ `factor·ing_cor` are identical raw vs harmonized (table in `HANDOFF.md`); 2024 Σ `factor`
= 38,830,230 households exactly matches INEGI's published figure; mean quarterly `ing_cor`
2024 = $77,864 (INEGI: $77,864).
