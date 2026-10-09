# CPV Unit 6j — derived columns for CGPV 1990 and the Conteo 1995

Done **2026-10-08** on the Mac. Gate: a 32-state `derived=True` sweep of both editions with no
unmapped code, the constraint cells checked against the 1990 and 1995 ITER in all 32 states,
tests green.

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| 1990/1995 have no dwelling file (the dwelling items repeat on every person) | **Build a dwelling frame from the person file**: `load_cpv_viviendas(1990\|1995)` = one row per `ID_VIV` with its first person's dwelling columns; `load_cpv_survey` returns it (5b returned `None`) |
| 1990 income (`INGRESO`, monthly, pesos before the 1993 redenomination) | **Convert to new pesos** (÷ 1,000) before the legacy bins; 99999997–9 (eventual, does not know, not specified) → «No especificado» |
| 1995 marital status 8, «alguna vez unida y no se sabe el estado civil» (22 records) | **«No especificado»** |

Taken without asking (precedent or evidence below):
- The legacy `EDUC` rule stays: technical studies after primaria are «Primaria_com», as in
  2000–2025 (`P15PRI_CO` keeps its cell in 1990, as in 2000/2010/2020; §Verification).
- Countries go to 998 (`OtroPais`) in both editions: their catalogs number countries their
  own way, and the derived category needs no country.
- 1995's ages and hours use 99 for «not specified» (2020: 999).
- 1990's drainage 3, «con desagüe al suelo, a un río o lago», counts as drainage (2020: 3/4).
- The Conteo 1995 has no dwelling class, so its dwelling cells take every sampled dwelling.

## Dwelling frames (`cpv.py`)

- `_DWELLINGS_FROM_PERSONS`: the dwelling columns of each person file.
  - **1990**: 22 columns, `TAM_LOC` … `N_F_GPOS`.
  - **1995**: 25 columns: the geography, `FAC_VIV`, `P1_*`, and `P2_2`/`P2_3` (shared
    expenses and number of households).
- `_dwellings_from_persons`:
  1. loads the raw person file(s) and derives the composite keys;
  2. keeps the first row of each `ID_VIV`;
  3. under `harmonize=True`, harmonizes the result as a `viviendas` frame (`_FACTOR_FROM`
     gains `"viviendas": "FAC_VIV"`).
- The frame is labelled with the person group's dictionary and indexed by `ID_VIV`.
- `load_cpv(table="viviendas", period=1990)` still raises: no raw file exists.
- **Constancy**: every dwelling column is constant within its dwelling in all 32 states of
  both editions, except the single 1990 dwelling 5b found.
- **Counts**:

  | edition | dwellings | expanded total | ITER `VIVPAR_HAB` |
  |---|---|---|---|
  | 1990 | 1,618,617 | × 10 = 16,186,170 | 16,183,310 |
  | 1995 | 70,672 | Σ `FAC_VIV` = 19,361,472 | 19,272,550 |

## Columns per edition (after 6j)

| edition | personas | viviendas |
|---|---|---|
| 1990 | **9**: `EDAD_CAT` (`ANO_CUMP`), `EDUC`, `CONACT_CAT` (`ACT_PRIN`), `SITUA_CONYUGAL_CAT` (`EST_CIVIL`), `ENT_PAIS_NAC_CAT` (`CVE_P_NAC`), `ENT_PAIS_RES_CAT` (`CVE_P_RES`, residence in 1985), `HORTRA_CAT` (`HORAS`), `INGTRMEN_CAT` (`INGRESO`), `RELIGION_CAT` | **4**: `CLAVIVP_CAT` (`T_VIV`), `CUADORM_CAT` (`P_DORMIR`), `TOTCUART_CAT` (`T_CUARTOS`), `DRENAJE_CAT` |
| 1995 | **8**: those but religion (not asked): `P3_6`, `P5_*`, `P7_1`, `P6_1`, `P3_7B`, `P4_6A` (residence in 1990), `P7_6`, `P7_9MP` | **3**: `CUADORM_CAT` (`P1_6`), `TOTCUART_CAT` (`P1_7`), `DRENAJE_CAT` (`P1_13`) |

**Not derivable:**
- **Health coverage and disability**: 1990 did not ask. The Conteo 1995 counts them per
  household (`P8_2*`, `P8_3*`: the number of members covered by each institution or with
  each impairment), not per person.
- **Occupation and sector**: CMO and CAE/CMAP codes, with no SINCO/SCIAN bridge (as 2000's
  occupation).

## Recodes and edition rules (into the Censo 2020 code space)

| item | edition | rule |
|---|---|---|
| «not asked» | 1990 | the items write 0 (under 5: residence, religion, schooling; under 12: activity, marital status; refugios: dwelling items) → blank (`_NA` in `_RECODE`) |
| `ACT_PRIN`, `P7_1` | 1990, 1995 | 1 worked → 10, 2 had a job → 20, 3 searched → 30, 4 student → 50, 5 home duties → 60, 6 retired → 40, 7 unable → 70, 8 did not work → 80, 9 → 99 |
| `EST_CIVIL` | 1990 | 1 → 1, 2 civil y religioso → 7, 3 civil → 5, 4 religioso → 6, 5 separada → 2, 6 divorciada → 3, 7 viuda → 4, 8 → 8, 9 → 9 |
| `P6_1` | 1995 | 1 → 1, 2 viuda → 4, 3 separada → 2, 4 divorciada → 3, 5 casada (not split) → 5, 6 soltera → 8, 8 → 9 (decision), 9 → 9 |
| `CVE_P_NAC`, `CVE_P_RES` | 1990 | CATPAISE: 001–032 entity, 033–099 entity not sufficiently specified → 997 (`OtraEnt`), 100–998 country → 998, 999 |
| `P3_7B`, `P4_6A` | 1995 | 01–32 entity, 33–38 a continent (35 the US) → 998, 70 «México (país)» → 997, 90 → 998, 99 → 999 |
| `ANO_CUMP`; `P3_6`, `P7_6` | 1990; 1995 | 1990's 999 is 2020's; 1995's 99 → 999 (98 = 98 or more) |
| `RELIGION` | 1990 | 1 ninguna → 3101, 2 católica → 1101, 3 protestante o evangélica → 1326, 4 judaica and 5 otra → «Otros credos», 9 → 9999; the under-5s «Blanco por pase» (2000's own dtype, `_period_dtypes`) |
| `HORAS`, `INGRESO` | 1990 | 0 for everyone not employed: blank unless `ACT_PRIN` 1/2 (who had a job worked 0 hours, as in 2020); income ÷ 1,000, a positive amount at least $1 (`_hortra_1990`, `_ingtrmen_1990`) |
| `APROBO` … `NOR_BAS` | 1990 | no grade (`APROBO` 2): preescolar (`PRESCO` years) or ninguno; `NIV_EST` 1–5 → 2, 3, 4, 11, 13 with `ANO_APRO` (a profesional's 9th–11th year → 8, a posgrado's 7th–10th → 6, 2020's last); a complete secundaria with technical studies (`TEC_SEC`) or normal básica (`NOR_BAS`) → 7/9, «Posbásica»; `APROBO` 9 → «No especificado», 0 → blank (`_educ_1990`) |
| `P5_3` … `P5_7` | 1995 | level `P5_4B` 0–7 → 0, 1, 2, 3, 4, 9, 11, 13 with grade `P5_4A` (9 → not specified); never attended (`P5_3` 6) → ninguno, not said (9) → «No especificado»; a technical career after secundaria/preparatoria (`P5_7` 2/3) lifts a secundaria to «Posbásica», after primaria (1) a primaria to complete (`_educ_1995`) |
| `T_VIV` | 1990 | 1 casa sola → 1, 2 departamento o vecindad → 4, 3 azotea → 6, 4 móvil → 8, 5 refugio → 9 (`Otro`), 9 → 99 |
| `T_CUARTOS`, `P_DORMIR`, `DRENAJE` | 1990 | 0 (refugios) → blank; 26 rooms → 25; drainage 4 none → 5 |

`_ALIASES` reads the 1990/1995 items under their 2020 names.

**1990's income quirk.** About 1% of the incomes look written in thousands of pesos (29,093
records: 258, 645, 516…, the round amounts 258,000, 645,000… of one, 2.5, 2 minimum wages).
With ÷ 1,000 and the $1 floor they land in «1-999» (new pesos), where their thousand-fold
amount would also go, unless that amount is $1,000 or more. A few hundred incomes reach tens
of millions of old pesos. Both are verbatim in INEGI's file.

**1995's zero weights.** 1,151 employed persons have no monthly income (`P7_9MP` blank) and
`FAC_POB` = 0. Their `INGTRMEN_CAT` is «Blanco por pase»; they weigh nothing.

## Constraints (`cpv_constraints`)

| edition | personas | viviendas |
|---|---|---|
| 1990 | 3 → **12**: `POBTOT`, `POBFEM`/`POBMAS`, `P5_HLI_HE`/`P5_HLI_NHE` (own), `P15YM_AN` (own), `P15YM_SE`, `P15PRI_IN`, `P15PRI_CO`, `PEA`, `PE_INAC`, `POCUPADA` | 0 → **5**: `VPH_1CUART`, `VPH_DRENAJ`, `VPH_PISODT`, `VPH_C_ELEC`, `VPH_AGUADV` (the last three own) |
| 1995 | 3 → **6**: `POBTOT`, `POBFEM`/`POBMAS` (own, on `P3_5`), `P_5YMAS`, `P_15YMAS`, `P15YM_AN` (own) | 0 → **3**: `VPH_C_ELEC`, `VPH_AGUADV`, `VPH_DRENAJ` (own, without the dwelling class) |

**Own cells** (`_EDITION_CELLS`) are the legacy cells on the editions' own items, with their
dictionaries' labels:
- 1990: `ALFABETA`, `HAB_IND`/`HAB_ESP`, `PISOS`, `ELECTRI`, `AGUA_ENTU`;
- 1995: `P3_5`, `P5_1`, `P1_16`, `P1_8`.

**Bug fixed.** The 1995 constraints listed `POBFEM`/`POBMAS` on `SEXO`, a column the 1995
frame does not have: the core `SEXO` entry labels every group, and the Conteo names sex
`P3_5`. `_categories` now takes only the frame's own columns (`_frame_group`). The
2000–2025 sets are unchanged (compared as JSON before and after).

## Verification

**32-state sweep** (`load_cpv_survey(period, state=s, derived=True)`, 1990 and 1995): no
unmapped code, no missing value, unique indices. That is 8,118,242 persons and 1,618,617
dwellings (1990), and 332,061 persons and 70,672 dwellings (1995).

**Against the ITER.** The table compares each constraint's share of the population, or of
the private dwellings, with the ITER's share of `POBTOT` or `VIVPAR_HAB`, in points. 1990
is the 10% extract, unweighted; 1995 is the sample, weighted (`FAC_POB`/`FAC_VIV`).

| indicator | 1990 nation | 1990 max \|Δ\| (state) | 1995 nation | 1995 max \|Δ\| (state) |
|---|---|---|---|---|
| `POBFEM`/`POBMAS` | ±0.10 | 0.47 (23) | ±0.07 | 0.25 (18) |
| `P_5YMAS` / `P_15YMAS` | — | — | 0.02 / −0.06 | 0.34 / 1.09 (07) |
| `P15YM_AN` (illiterate) | 0.01 | 0.24 | 0.39 | 1.64 (14) |
| `P15YM_SE` / `P15PRI_IN` | 0.02 / 0.05 | 0.25 / 0.51 | — | — |
| `P15PRI_CO` | **1.27** | 3.03 (08) | — | — |
| `P15PRI_CO`, without technical after primaria | 0.08 | 0.29 | — | — |
| `P5_HLI_HE` / `P5_HLI_NHE` | −0.01 / 0.00 | 0.35 / 0.05 | — | — |
| `PEA` / `POCUPADA` / `PE_INAC` | 0.12 / 0.11 / 0.20 | 0.62 / 0.59 / 0.80 (02) | — | — |
| `VPH_1CUART` | 0.05 | 0.77 (23) | — | — |
| `VPH_C_ELEC` / `VPH_AGUADV` / `VPH_DRENAJ` / `VPH_PISODT` | 0.86 / 0.82 / 0.72 / 0.81 | 2.7 (02) | −0.20 / 1.19 / 1.39 | 3.9 / 6.4 / 7.0 (23, 04) |

- **1990 persons agree** to sampling noise: the extract reproduces `POBTOT` to 0.08%.
- **Except `P15PRI_CO`**: INEGI's 1990 «primaria completa» leaves out persons with technical
  studies after primaria (its «instrucción posprimaria» includes them). Without them, the
  sample gives 9,605,750 against 9,553,163 (+0.6%, like the other indicators). The legacy
  `EDUC` counts them as «Primaria_com», as it does in every edition. The 2020 check is
  inconclusive: four states of the cuestionario ampliado sit closer to primaria without
  técnica in three, and the sample does not reproduce the count closely enough to tell.
  INEGI's 2020 definition says «máxima escolaridad 6 grados aprobados en primaria».
  This is open for the user (HANDOFF).
- **1990 dwelling characteristics** run about 0.8 points above the ITER, alike for each
  characteristic and in each state (2.5–2.8 in Baja California), while the dwelling total
  matches. The ITER seems to tally characteristics over fewer dwellings than its
  `VIVPAR_HAB`. Leaving out the dwellings of unspecified type overshoots the other way.
  This is unexplained and not a derived-column effect.
- **1995** is a survey compared with a count. The persons agree within tenths nationally,
  literacy (0.4) and the dwelling services (1.2–1.4) less. Small states differ by several
  points: a clustered sample of about 2,000 dwellings per state.

**National** shares:
- 1990: `EDUC` (15+) Sin Educación 13.4%, primaria incompleta 22.7%, completa 21.2%,
  secundaria 5.4% / 12.6%, posbásica 22.6%. `RELIGION_CAT` among the 5+: católica 89.7%,
  protestante/evangélica 4.9%, sin religión 3.2% (INEGI's published 1990 shares).
- 1995 (Σ `FAC_POB`): `EDUC` posbásica 27.3%, Sin Educación 10.4%.

## Tests

- **`tests/test_cpv_derived.py`**:
  - `test_source_codes_match_2020` now reads the frame's own item, not a core overlay of
    another name (it had compared the core `EDAD` with 2020's for 1990/1995), and drops
    blank (NaN) codes. It also has the reviewed 1990/1995 rows: `_GAPS` (no activity check,
    1995's unsplit casada, 1990's dwelling classes and drainage) and `_OWN_CODES`/
    `_NO_CATALOG` (education items, income, birthplace/residence, 1990 religion).
  - `test_recode_tables` covers the 1990/1995 recodes.
  - The listings cover 1990/1995.
  - Synthetic 1990 persons: técnica after secundaria, preschool only, under 5, técnica after
    primaria, a «no sabe» income, an income in thousands. Also synthetic 1995 persons and
    1990/1995 dwellings.
  - Unknown codes raise.
  - The 1990/1995 constraints, including the categories of the `viviendas` frames.
  - Real data: `test_derived_editions_real` and `test_crosstab_per_edition` with 1990/1995;
    `test_1990_1995_constraints_equal_iter` (state 01: within 0.7 points in 1990, the
    primaria cell after the technical-studies correction, and 0.5 in 1995).
- **`tests/test_cpv.py`**:
  - `test_load_cpv_1990_1995_real`: the dwelling frames (shapes, `ID_VIV` = the persons',
    Σ `FAC_VIV`).
  - `test_dwellings_from_persons_offline`: first person's items, harmonized `FACTOR`,
    labels, no raw file.
- **Full suite**: 1746 passed, 1 skipped (30 min, the Mac's full mirror).

## Follow-ups (HANDOFF)

- **`P15PRI_CO` across editions**: the legacy cell counts technical studies after primaria
  (`EDUC` «Primaria_com»), and INEGI's 1990 count does not. A user decision: a finer `EDUC`
  category, or an edition-specific cell.
- **1990's «0»**: the 1990 dictionary labels the «not asked» code as `'0'` (its FD gives no
  label). A dictionary note («Blanco por pase») plus `--variables` would label it.
- The 1990 dwelling-characteristic offset (+0.8 points) is unexplained.
- The 1990 ITER's sector indicators (`POCUSECP/S/T`) could get own cells on the CMAP
  division's first digit.
