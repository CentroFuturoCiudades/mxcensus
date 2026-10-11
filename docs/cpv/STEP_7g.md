# CPV Unit 7g — constraint keys = published columns; every constraint against the census

Done **2026-10-10** (on the Mac, overnight, without the user: they asked for the night's
units to run unattended, for review in the morning). HANDOFF candidate 2 («constraint keys
vs ITER names»), widened on the probe's findings to check every 2000/2010/2020 constraint
against its ITER column wherever the sample is the census. Gate: every constraint key a
column of the edition's published aggregate; each changed cell exact where the sample is the
census; tests green.

## Decisions taken unattended (for the user's review)

1. **Keys = the edition's column** (over a helper that maps a constraint to its published
   column): `cpv_constraints` and `cpv_ratio_constraints` now key each indicator by the
   column `load_cpv_iter(period)` publishes it under. 18 keys change name in 2000/2005/2010
   (below); 2020 and 2025 are untouched.
2. **CGPV 2000's own definitions** of the kept pairs: `PNACOENT` (born outside the entity
   *or the country*) and `P5_RESO95` (living in 1995 in another entity *or country*) count
   the born and the residents abroad too; `P5_CATOLIC`, `P5_NCATOLI` and `P5_SINRELI` count
   the 5 and more only (the persons of unspecified age answer the item; INEGI leaves them
   out).
3. **INEGI's rule for the unspecified entity in 2010 and 2020**: `PNACOE` (`_F`, `_M`) on
   `ENT_PAIS_NAC_INEGI` and `PRESOE05`/`PRESOE15` (`_F`, `_M`) on `LUGAR_RES_5A` «Otra
   entidad», as the EIC 2025 already had (6y, 7a). For 2020 this departs from the frozen
   legacy cells, as 6y's `PCLIM_*`/`PCDISC_*` did: the 2020 ITER agrees with INEGI's rule.
4. **New derived `RELIGION_INEGI`** (Censo 2010 only): its religion by its own
   classification, the neo-Israelite movements (220100) among «Otros credos». `PNCATOLICA`
   and `POTRAS_REL` (2010) count on it. `RELIGION_CAT` keeps 2020's grouping (6f, the
   user's choice), so nothing else changes.
5. **Found, not changed** (no rule reproduces INEGI's census): CGPV 2000's no schooling and
   income in minimum wages, Censo 2020's health affiliation and religion (below).

## 1. Constraint keys

`cpv_derived._published_name(ind, period)`: the crosswalk's column of `ind` in `period`
when the crosswalk pairs it with an older edition's column that `harmonize=True` does not
rename (another date or definition: `_XW_PAIRS_KEPT`), else `ind`. Both constraint
functions apply it to their output keys (the cells and the «published» test stay on the
canonical names inside).

| edition | canonical → published |
|---|---|
| 2000 personas | `PNACOE` → `PNACOENT`, `PRES2015` → `P5_RES95`, `PRESOE15` → `P5_RESO95`, `PCATOLICA` → `P5_CATOLIC` |
| 2000 viviendas | `VPH_EXCSA` → `VP_SERSAN` |
| 2005 personas | `PRES2015` → `P_RE2000`, `PRESOE15` (`_F`, `_M`) → `P_OE2000` (`P_F_OE2000`, `P_M_OE2000`), `PDER_SEGP` → `P_SEGPOP` |
| 2005 viviendas | `VPH_AGUADV` → `VPH_AGDV`, `VPH_AGUAFV` → `VPH_NOAG` |
| 2010 personas | `PRES2015` (`_F`, `_M`) → `PRES2005` (…), `PRESOE15` (`_F`, `_M`) → `PRESOE05` (…) |

Every count and ratio key of every edition is now a column of its published aggregate (a
new offline test checks it against the schema map); no two indicators collide. The counts
per edition are unchanged.

## 2. Every constraint against the census

**Where the sample is the census.** As 6w–7f: the municipalities whose every sampled person
has `FACTOR` 1 and whose population in households equals the ITER's `POBHOG` (2000: 186,
2010: 364, 2020: 184). There the sample's ages may still differ from the ITER's (7e found
it in Oaxaca), so **strict** adds: every age/sex-only constraint (`POBFEM`, `P_5YMAS`,
`P_15A49_F`…) equal to the ITER's. Strict: 2000 **51**, 2010 **233**, 2020 **130**
municipalities (Oaxaca: 50, 174, 107).

**The sweep** (`load_cpv_personas/viviendas(derived=True)`, every count and ratio
constraint of 2000/2010/2020, 32 states, 5 processes):

| edition | constraints | exact in every strict municipality, before → after |
|---|---|---|
| 2000 | 70 + 0 persons, 36 + 2 dwellings | persons 53 → 58, dwellings 38/38 |
| 2010 | 147 + 4 persons, 28 + 2 dwellings | persons 145 → **151/151**, dwellings 30/30 |
| 2020 | 161 + 4 persons, 46 + 2 dwellings | persons 139 → 145, dwellings 48/48 |

**The changes, exact of the strict municipalities** (legacy cells → 7g's):

| edition | indicator | legacy | 7g |
|---|---|---|---|
| 2000 | `PNACOENT` | 40 | **51** |
| 2000 | `P5_RESO95` | 27 | **51** |
| 2000 | `P5_CATOLIC` | 20 | **51** |
| 2000 | `P5_NCATOLI`, `P5_SINRELI` | 42, 40 | **51**, **51** |
| 2010 | `PNACOE`, `PNACOE_F` (`_M` already 233) | 231 | **233** |
| 2010 | `PRESOE05`, `PRESOE05_F` (`_M` already 233) | 231 | **233** |
| 2010 | `PNCATOLICA`, `POTRAS_REL` | 221 | **233** |
| 2020 | `PNACOE`, `_F`, `_M` | 123, 129, 124 | **130** |
| 2020 | `PRESOE15`, `_F`, `_M` | 120, 124, 124 | **130** |

Over every municipality where the sample is the census (not only strict): 2000 `PNACOENT`
102 → 180 of 186, `P5_RESO95` 78 → 181, `P5_CATOLIC` 45 → 173; 2010 `PNACOE` 347 → 356 of
364, `PRESOE05` 357 → 360; 2020 `PNACOE` 151 → 159 of 184, `PRESOE15` 157 → 169.

- **2000's pairs.** The crosswalk notes said so for `PNACOENT` («incluye a la población
  nacida en otro país»); its dictionary says «residente en otra entidad o país» for
  `P5_RESO95` too, which the note had missed. Both columns work alike (the INEGI-rule
  columns and the legacy ones give the same counts in 2000; the INEGI ones are used, as in
  2010–2025).
- **2000's religions** are asked of the 5+, and the persons of unspecified age (999) answer
  them; INEGI's «de 5 años y más» leaves those out (7a's rule for the age universe).
- **The unspecified entity.** The 2010/2020 ITERs leave it out of «nacida en otra entidad»
  and «residente en otra entidad», as INEGI's tabulados (6e) and the EIC 2025 estimates.
  The Conteo 2005 keeps the legacy cells (`_EDITION_CELLS`): it has no `LUGAR_RES_5A`, and
  its residence item has no unspecified entity (its «no especificado» is the whole answer's,
  already apart).
- **2010's religion.** In each of the 12 strict municipalities where `PNCATOLICA` missed,
  ours minus the ITER's = the neo-Israelites = the ITER's `POTRAS_REL` minus ours (176 in
  20-104, 96 in 20-504…). Censo 2010's catalog puts them among the judaic credos; 2020's
  among the evangelical churches (6f kept 2020's grouping for `RELIGION_CAT`).

## 3. Found, not changed

- **CGPV 2000's no schooling** (`P15YM_SE`, and `P15_SINSEC`/`P18_SMEDSU`, which hold it;
  25 of 51 strict): the ITER counts more. Where it does, the extra persons are those whose
  level is not specified (`NIVACAD` 9) — most of them in some municipalities (20-228: 128
  of 132; 20-322: 124 of 128), none in others (20-001: 0 of 33). They are mostly illiterate
  and not attending, but no item decides it: INEGI imputed the unspecified answers in the
  census (a donor's), and the sample keeps them unspecified. `EDUC_INEGI`'s «Sin
  Educación» (levels 0 and 1 and the never-schooled 5–29) is right where nothing is
  unspecified.
- **CGPV 2000's income** (`POCUNINGR`, `P_1SM`, `P1_2SM`, `P2_5SM`; 13–45 of 51): the employed
  match, but the ITER has fewer without income and more at 1–2 minimum wages. No item
  (`SITTRA`, `CONACT`, the income code) explains it. The sample tabulado (C2KEM08) matches
  the sample within 0.02 points (7c), so the difference is the census's processing.
- **Censo 2020's health affiliation and religion** (10 affiliation indicators 66–128 of 130,
  `PCATOLICA`/`PRO_CRIEVA`/`PSIN_RELIG` 68–100): small swaps between categories, a few
  persons each way (20-040: 41), with the same unspecified count for affiliation (80 and 80
  in the strict set). The 2020 derived columns equal INEGI's ampliado tabulados exactly (6p),
  so the sample is processed as INEGI's sample; its census is processed otherwise there.
  Censo 2010 has no such difference (every constraint exact).
- Censo 2020's economic activity (`PEA`, `PE_INAC`, `POCUPADA`, each `_F` too) misses
  in one strict municipality, `POTRAS_REL` in another (129 of 130).
- A few 2000 cells sit at 49–50 of 51 (`P15PRI_IN`, `P15SEC_IN`, `P15A17A`, `P6_14AESC`,
  `P_15A24A`): one or two municipalities each, the same imputation of unspecified answers.

## Constraint counts

Unchanged in every edition (2000 70 + 36, 2005 87 + 20 + 3, 2010 147 + 28, 2020 161 + 46,
2025 214 + 93; ratios as 7f). 18 keys renamed (§1); 2000 changes 5 cells, 2010 8, 2020 6.

## What changed

- **`cpv_derived`**:
  - `_published_name`, applied by `cpv_constraints` and `cpv_ratio_constraints`;
  - `_CELLS["personas"]` += `PNACOE`/`_F`/`_M` (`ENT_PAIS_NAC_INEGI`) and `PRESOE15`/`_F`/
    `_M` (`LUGAR_RES_5A`, 5+);
  - `_EDITION_CELLS`: 2000 `PNACOE`, `PRESOE15`, `PCATOLICA` and the age on `P5_NCATOLI`/
    `P5_SINRELI`; 2005 the legacy `PRESOE15`/`_F`/`_M`; 2010 `PNCATOLICA`/`POTRAS_REL` on
    `RELIGION_INEGI`;
  - `_religion_inegi_2010` (and `_religion_2010`'s column and code-map arguments), its
    derivation, `_DTYPE_LIKE["RELIGION_INEGI"]`;
  - the docstrings.
- **Tests** (`tests/test_cpv_derived.py`):
  - `test_published_name`, `test_constraint_keys_are_published_columns` (offline);
  - `test_7g_cells_equal_iter` (Oaxaca's strict municipalities, 2000/2010/2020: 50/174/107);
  - the per-edition cells and names (`test_cpv_constraints_per_edition`), the 2010
    derivations (`RELIGION_INEGI` in `_persons_2010` and the catalog test);
  - `test_6n_cells_equal_iter` and `test_2000_dwellings_equal_iter` read the keys as
    columns.
- **Docs**: README, CLAUDE.md, PLAN, HANDOFF.

## Verification

- The 32-state sweep above (2000, 2010, 2020; ~15 min).
- `test_7g_cells_equal_iter`: 3 passed (102 s).
- Full suite on the Mac: 1907 passed, 5 failed, 1 skipped (33 min). The five pinned the old
  expectations (the 2010 derivation list, the catalog test's one derivation per item, the
  6n own-cell counts); once updated they pass (`test_cpv_derived.py` 367 passed), so 1912
  passed, 1 skipped.
