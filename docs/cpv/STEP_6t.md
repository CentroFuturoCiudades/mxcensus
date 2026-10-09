# CPV Unit 6t — persons by their household head's sex

Done **2026-10-09** (on the Mac; HANDOFF candidate 2, agreed with the user after 6s). Gate:
a person column with the sex of the person's own household head in every edition with a
household, the ITER's (and the EIC 2025 estimates') `PHOGJEF_F`/`PHOGJEF_M` as constraints,
each within its sample-vs-census band in all 32 states, tests green.

## The gap

6s gave the dwellings of 2000–2010 the head's sex (`JEFE_SEXO`, 2020's dwelling item), so the
households by the head's sex (`HOGJEF_F`/`HOGJEF_M`) became constraints. The population by
its household head's sex is another indicator: the 2000–2020 ITERs publish it (2000
`PHOGJEFF`/`PHOGJEFM`, 2005 `P_HOG_JF`/`P_HOG_JM`, 2010/2020 `PHOGJEF_F`/`PHOGJEF_M`; the
crosswalk renames them) and so do the EIC 2025 estimates. In every state
`PHOGJEF_F` + `PHOGJEF_M` = the ITER's `POBHOG`. The legacy constraint YAML has no person
cell for it, and no person item carries the head's sex.

## The user's choices

- **The name**: `HOGJEF_SEXO`, distinct from the dwelling's `JEFE_SEXO`, so a person ↔
  dwelling join never holds two columns of one name that disagree (they can in the Conteo
  2005: a person of a dwelling's second household gets that household's head, the
  dwelling row its first household's). Labels and dtype are `JEFE_SEXO`'s (Hombre/Mujer).
- **The editions**: 1995 and 2000–2025, every edition with a household key and one head
  per household. CGPV 1990 is left out: it has no household number, and 6–8% of its
  dwellings have no person coded 100 (jefe) while 1–2% have several. 1995 and 2015 get the
  column without an ITER indicator (no constraint); 2015 is checked against its tabulado.
- **Merge and version**: 6s and 6t go to `main` together as **0.10.0**.

## What changed

- `cpv_derived`:
  - `_HEAD_CODES`: the head's code in each edition's relationship item, read under one
    source name `PARENTESCO` (`_ALIASES`: `PARENT`, `OTROPARE_C`, `P3_4`). 2020/2025 101
    «Jefa(e)»; 2010/2015 01 «Jefe(a)»; 2005 101 «Jefe(a)» and 102 «Persona sola»; 2000 100
    (the head group of its catalog); 1995 1 «Jefe o Jefa» (its FD says «Ver catálogo de
    parentesco»: the catalog PDF, `catalogos_cpv1995.pdf`, not parsed into the YAML; its 7
    «Persona sola» marks 21 persons nationally, all in households that have a 1).
  - `_hogjef_sexo(heads)`: the `SEXO` of the household's one head, broadcast to its members;
    a household without exactly one head raises. One derivation per set of head codes.
  - `_Derivation.household`: a derivation that also reads each record's household, which
    `derive` puts in `src[_HOUSEHOLD]` (`_household`: the entity and `ID_HOG` in 1995–2005,
    else the entity and `ID_VIV` — one household per dwelling in 2010–2025; the entity
    keeps Censo 2010's state-scoped serials apart). A frame without keys gets the
    1995–2005 composite keys (`cpv._composite_keys`); without either it raises.
  - `_ALIASES["SEXO"]` = `SEXO`/`P3_5` and `_RECODE["1995"]["SEXO"]` 2 → 3 (1995's sex).
  - `_DTYPE_LIKE` / `_legacy_dtype`: `HOGJEF_SEXO` takes the legacy dwelling `JEFE_SEXO`
    dtype.
  - `_CELLS`: `PHOGJEF_F` = `{HOGJEF_SEXO: [Mujer]}`, `PHOGJEF_M` = `[Hombre]`.
- Person constraints: 2000 60 → **62**, 2005 83 → **85**, 2010 143 → **145**, 2020 157 →
  **159** (the legacy YAML's 157 + 2), 2025 25 → **27** (both equal the estimates). 1990,
  1995 and 2015 unchanged (no indicator).
- `scripts/check_cpv_tabulados.py`: CGPV 2000's `C2KHO04` (households and their population
  by the head's sex, % by state — `HO04a` on 6s's `JEFE_SEXO` over the household rows,
  table `hogares`; `HO04b` on `HOGJEF_SEXO`) and the EIC 2015's `12_hogares.xls` sheet 05
  (`12-05`: the population in households by the head's sex). Censo 2010's and 2020's
  ampliado tabulados have no breakdown by the head's sex (2010 `12_0nA`, 2020
  `cpv2020_a_eum_13_hogares_censales.xlsx`: relationship, parents only).
- Docs: `cpv.load_cpv_personas`, the `cpv_derived` docstrings, README, CLAUDE.md.

## The data (all 32 states, `load_cpv_personas(derived=True)` through the constraints)

**One head per household** in every state of 1995–2025 (`derive` would raise). Each
edition's 32 states load in 10 s (1995) to 5 min (2025).

**EIC 2025: exact.** Σ `FACTOR` by `HOGJEF_SEXO` = the estimates' `PHOGJEF_F`/`PHOGJEF_M`
in all 32 states and all **2,478 municipalities** (nation: 42,935,971 / 87,457,418).

**The censuses against their ITER**: the female-headed share of the household population,
sample − ITER, in points:

| edition | median \|Δ\| | 90th pct. | max \|Δ\| | nation (sample / ITER) |
|---|---|---|---|---|
| CGPV 2000 | 0.22 | 0.56 | 0.74 (Morelos) | 17.22 / 17.27 |
| Conteo 2005 (unweighted) | 0.10 | 0.26 | 1.25 (Colima) | 19.47 / 19.44 |
| Censo 2010 | 0.43 | 1.00 | 1.55 (Aguascalientes) | 20.90 / 21.00 |
| Censo 2020 | 0.59 | 2.04 | 2.60 (Querétaro) | 29.02 / 29.81 |

The 2020 gap is the sample's, not the derivation's: INEGI's own dwelling item `JEFE_SEXO`
gives the same share (Querétaro: 27.50% by the dwelling item on the person weights, 27.50%
by `HOGJEF_SEXO`; the ITER 30.09), and its households sit as far under the ITER (30.66 vs
32.83%). The 2020 sample's weights add up to `POBHOG` (ratio 1.00000–1.00004) but are not
calibrated on the head's sex; 6s saw the same for the households (up to 1.7 points in the
states it checked, 2.2 in Querétaro).

**Against INEGI's sample tabulados** (`TABULADOS_REPORT.md`, now 21,414 cells, none beyond
tolerance): CGPV 2000 `C2KHO04` — the population by the head's sex within 0.005 points and
the households (6s's `JEFE_SEXO`) within 0.009 (Chiapas) in every state and the nation; EIC
2015 `12-05` exact to the person in every state and the nation. The rest of the report is
unchanged.

## Tests

- `test_derive_hogjef_sexo` (offline): each edition's synthetic persons (1995/2000 two
  households in one dwelling, 2005 a second household headed by a 102 «persona sola»,
  2010 two states sharing serials, 2015 un-padded keys), the dtype (= `JEFE_SEXO`'s),
  1990 without it; two heads, no head, an unknown sex code and a frame without a
  household key raise.
- `test_source_codes_match_2020`: the relationship item is own-code — the head codes must
  be in each edition's dictionary, labelled as the head where it has labels (2000: the
  catalog's unlabelled group codes; 1995: a string item pointing at its catalog).
- `test_cpv_derivations_listing`, `test_cpv_constraints_per_edition` (2020 = the legacy
  count + 2; `PHOGJEF_*` in 2000–2025, not 1995), `test_eic2025_constraints_equal_estimates`
  (25 → 27 cells).
- Real (state 01): `test_hogjef_sexo_equals_published` (2000/2005 within 0.3 points of the
  ITER, 2010 2.0, 2020 0.5; 2025 every municipality exact).
- The synthetic person frames of every edition test carry the head (`derive` needs it):
  `_persons_2025` (+ `_each_a_household` for the replicated-row tests), `_persons_2015`,
  `_persons_2010`, `_persons_2000`, and the new `_persons_2005`/`_persons_1995` helpers.
- `tests/test_cpv_tabulados.py`: the check table admits `hogares` (2000 only); state 01
  compares 648 cells (+ 7: `HO04a`/`HO04b`/`12-05`, sex T only).
- **Full suite**: 1799 passed, 1 skipped (30 min on the Mac's full mirror; the first run
  failed only the two `test_cpv_tabulados.py` expectations above, fixed and rerun: 8
  passed).
