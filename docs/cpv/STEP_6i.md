# CPV Unit 6i — derived columns for CGPV 2000 and Conteo 2005

Done **2026-10-08** (on the Mac, the same session as 6f–6h; developed in a git worktree
while 6h's files uploaded). Gate: a 32-state `derived=True` sweep of both editions with no
unmapped code, the 2000 columns checked against INEGI's sample tabulados, tests green.

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| Conteo 2005 `OTRA_INS` (1 state governments' institutions, 2 other, 3 private with subrogated services, 9 not named) | **1 → `DHSERSAL_ISSSTE_E`** (2020's 03, «ISSSTE estatal»), **2 → `DHSERSAL_Otro`**, **3 → `DHSERSAL_Privado`**; 9 → `Otro` (as 2000's unnamed institution) |
| CGPV 2000 religion (asked of the 5+) | **`RELIGION_CAT` with «Blanco por pase» for the under-5s**, a category only 2000's `RELIGION_CAT` has (`_period_dtypes`) |

Taken without asking (evidence below): 2000's activity is the SCIAN subsector (3 digits). Its
occupation is CMO, not SINCO, so 2000 gets no `OCUPACION_C_COARSE`. Neither edition gets a
disability column: the 2000 ITER publishes no disability indicator the crosswalk pairs, and
the Conteo did not ask.

## Columns per edition (after 6i)

| edition | personas | viviendas |
|---|---|---|
| 2000 | **17**: `EDAD_CAT`, `INGTRMEN_CAT` (`INGRESOS`), `HORTRA_CAT`, `EDUC`, `ACTIVIDADES_C_COARSE`, `CONACT_CAT`, `SITUA_CONYUGAL_CAT` (`ESTCON`), `ENT_PAIS_NAC_CAT` (`LNACEDO_C`), `ENT_PAIS_RES_CAT` (`RES95EDO_C`), `RELIGION_CAT`, 7 `DHSERSAL_*` | **5**: `CLAVIVP_CAT` (`CLAVIV`), `CUADORM_CAT`, `TOTCUART_CAT`, `DRENAJE_CAT`, `INGTRHOG_CAT` |
| 2005 | **13**: `EDAD_CAT`, `EDUC`, `ENT_PAIS_RES_CAT` (`LURE2000`), 10 `DHSERSAL_*` | **4**: `CLAVIVP_CAT` (`CLAVIVPA`), `CUADORM_CAT` (`CUARDOM`), `TOTCUART_CAT` (`NUMCUAR`), `DRENAJE_CAT` (`DIS_DREN`) |

The `DHSERSAL_*` sets are the 2020 dummies each edition can answer:
- **2000**: IMSS, ISSSTE, P_D_M, Otro, No afiliado, PUB, AFIL.
- **2005**: those, plus ISSSTE_E, SALUD_PUBLICA (Seguro Popular) and Privado.

## Recodes and edition rules (into the Censo 2020 code space)

| item | edition | rule |
|---|---|---|
| `CONACT` | 2000 | 14 student, 15 home duties, 16 retired (found working) → 15, 16, 14; 40 student, 50 home duties, 60 retired → 50, 60, 40 |
| `NIVACAD` | 2000 | 5 normal → 9, 7 profesional → 11, 8 maestría o doctorado → 13, 9 → 99; **6 técnica by `ANTESC`**: after primaria → 6 («Primaria_com», as 2020), secundaria → 7, preparatoria → 8 (`_educ_2000`) |
| | 2000 | 141,225 records aged 5–29 who never attended school have no level and `NIVELACAD` 00 «sin instrucción» → level and grade 0. Técnica after preparatoria with grade 5 (6 records) → grade 4 (2020's list stops there; «Posbásica» either way) |
| `NIVANTES` + `GRA_APRO` | 2005 | level and antecedent like 2000's `NIVELACAD`: 51/52 → 9, 61/62/63 → 6/7/8, 73 → 11, 84 → 13, 94/95 → 14, 99 → 99. «Sin escolaridad» (0) has no grade → 0. A grade without a level (99) → «No especificado». Blank = under 5 (`_educ_2005`) |
| `LNACEDO_C`, `RES95EDO_C` | 2000 | 001–032 entity, 100–535 country (2020's layout), 600 «otro país, no se sabe cuál» → 998, 999 NE |
| `LURE2000` | 2005 | 001–032, 033 entity not sufficiently specified → 997 (`OtraEnt`, the legacy rule), 201 the United States → 221, 600 another country → 998, 999 |
| coverage | 2000 | one item per institution (`_DHSERSAL_ITEMS`): `IMSS` 1 (9 = coverage not known at all → 2020's 99, every dummy 0), `ISSSTE` 2, `PEMEX` 3 → P_D_M, `OTRINS_V` 4 (covered, institution not named — INEGI's tabulado counts it as «otra institución»: 1,056,252 = 2.67% of the covered) → Otro, `NOTIEDER` 5 → No afiliado |
| | 2005 | `IMSS`, `ISSSTE`, `PEMEX`, `SEGU_POP`, `INST_PRI` (1 each); `OTRA_INS` (decision above); `SIN_DERE` 6 → No afiliado, 9 → NE |
| `OTRAREL_C` | 2000 | its FD: 0001 católica, 9100 ninguna; the first digit is the 2000 classification's group: 1 protestantes y evangélicas, 2 bíblicas no evangélicas (2020: both «Protestante/cristiano evangélico»), 3–8 and 9001 other, 9999 NE (`_religion_2000`). The national shares match INEGI's tabulado exactly (88.22, 5.22, 2.13, 0.37, 3.49, 0.57%) |
| `CLAVIV`, `CLAVIVPA` | 2000, 2005 | 1 casa independiente (2020's 1–3) → 1, 2 departamento → 4, 3 vecindad → 5, 4 azotea → 6, 5 local → 7, 6 móvil → 8, 7 refugio → 9, 9 → 99 |
| `TOTCUART` | 2000 | 26 → 25 (both «3+»). Like 2020's, it counts the kitchen |
| `ACTTRAB_C` | 2000 | SCIAN subsector (110–939; the tabulado: «con base en el SCIAN»): sector = first two digits |
| `INGRESOS`, `HORTRA` | 2000 | 2020's code space: income 999999 = NE (5.24% of the employed = the tabulado), 0 = no income (10.07%); hours 999 = NE (3.23%) |

`_ALIASES` reads 2000's `INGRESOS`, `LNACEDO_C`, `RES95EDO_C`, `CLAVIV` and 2005's
`LURE2000`, `CLAVIVPA`, `CUARDOM`, `NUMCUAR`, `DIS_DREN` under their 2020 names. 2000's
`SEXO` is 1/2 in the raw data.

## Constraints (`cpv_constraints`)

| edition | personas | viviendas |
|---|---|---|
| 2000 | 0 → **29** (`POBTOT`…, `PDER_SS`, `PDER_IMSS`, `PDER_ISTE`, `PSINDER`, `PEA`, `POCUPADA`, `PE_INAC`, `P12YM_CASA`, `PCATOLICA` (5+), `PNACENT`, `PNACOE`, `PRES2015`/`PRESOE15` (1995), education …) | 0 → **4** (`TOTHOG`, `VPH_1CUART`, `VPH_1DOR`, `VPH_DRENAJ`) |
| 2005 | 0 → **38** | 0 → **8** |

The 2000 ITER's `V_1CUARTO` counts «en el total de cuartos registraron uno solo», kitchen
included, as `TOTCUART_CAT` = 1 does.

## Verification

**32-state sweep** (`load_cpv_personas`/`load_cpv_viviendas(period, state=s,
derived=True)`, 2000 and 2005): no unmapped code, no missing value.

**INEGI's CGPV 2000 ampliado tabulados** (`ccpv/2000/tabulados/ampliado/C2K*.xls`, BIFF5
workbooks read with a scratch reader — `_dict_fd.read_xls` reads BIFF8 only; percentages with
2 decimals; 32 states + nation × total/men/women):

| tabulado | cells | median \|Δ\| | 95th pct. \|Δ\| (without Chiapas) | max \|Δ\| |
|---|---|---|---|---|
| MI01 birthplace (this entity / other or abroad / NE) | 99 | 0.003 | 0.006 | 0.069 (Chiapas) |
| MI03 residence in 1995 (5+) | 99 | 0.003 | 0.006 | 0.026 (Chiapas) |
| RE02 religion (5+) | 495 | 0.003 | 0.009 | 0.133 (Chiapas) |
| SS04 coverage | 693 | 0.003 | 0.005 | 0.053 (Chiapas) |
| EC02 marital status (12+), `SITUA_CONYUGAL_CAT` | 132 | 0.003 | 0.007 | 0.017 |
| EM01 activity (12+), `CONACT_CAT` | 495 | 0.002 | 0.005 | 0.048 (Chiapas) |
| EM05 sector (employed), `ACTIVIDADES_C_COARSE` | 1,683 | 0.003 | 0.005 | 0.508 (Chiapas) |
| VI05 rooms (the tabulado leaves out an exclusive kitchen: `TOTCUART` − (`COCINA` 1 and `COCDOR` 4)) | 231 | 0.003 | 0.008 | 0.126 (Chiapas) |
| VI06 bedrooms, `CUADORM_CAT` | 99 | 0.003 | 0.010 | 0.105 (Chiapas) |
| VI10 drainage, `DRENAJE_CAT` | 99 | 0.002 | 0.006 | 0.019 |

The national population equals the tabulados' exactly (97,014,867); dwellings are 21,857,601
against 21,858,085 (−484).
The shares agree to rounding in most cells. The rest are a few hundredths of a point,
except in Chiapas: the public sample's weights (4a: a ratio estimator on preliminary counts)
do not reproduce INEGI's tabulados cell for cell. The derived columns agree with the same
shares computed from the raw items. **Education** (ED10) is not comparable cell by cell:
INEGI's 2000 levels put técnica after primaria with secundaria and split «media superior» /
«superior». The legacy `EDUC` counts técnica after primaria as «Primaria_com» and merges the
rest into «Posbásica» (up to 3.6 points per cell).

**National** (Σ FACTOR, 2000): `EDUC` Sin Educación 11.1%, primaria incompleta 24.5% /
completa 15.1%, secundaria 6.1% / 12.0%, posbásica 18.2%, NE 2.0%, under 5 11.1%;
`RELIGION_CAT` católica 78.4% (88.2% of the 5+); covered 40.8%.

**Conteo 2005** has no weights (the sample is unweighted), and its tabulados are the full
count, so no exact check. Unweighted, 48.4% of the records are covered, 7.2% by the Seguro
Popular, and 86.6% lived in the same entity in 2000.

## Tests (`tests/test_cpv_derived.py`)

- **Offline:**
  - `test_source_codes_match_2020`: the 2000/2005 items, as own-code items (`_OWN_CODES`:
    the coverage items, `NIVELACAD`, `ANTESC`, `ACTTRAB_C`, `OTRAREL_C`, `NIVANTES`,
    `GRA_APRO`, `LURE2000`, and 2000's text items without a catalog, `_NO_CATALOG`) or
    against 2020 with reviewed gaps (`CONACT` 17, `NIVACAD` 5/7/8/10/12/14, `CLAVIVP` 2/3);
  - the listings (2000, 2005; 1995 has none);
  - synthetic 2000 persons (técnica after primaria, never schooled, under 5, IMSS 9,
    `OTRINS_V`, 2xxx religion, 600 country), 2005 persons (`OTRA_INS` 1/3, 201, 033, a grade
    without a level) and dwellings (`CLAVIV` 05, 26 rooms, refugio);
  - unknown codes raise;
  - 2000/2005 constraints.
- **Real:**
  - `test_2000_equals_tabulados`: state 01 birthplace, coverage, religion, activity within
    0.02 points;
  - `test_derived_editions_real` and `test_crosstab_per_edition` now include 2000 and 2005.
- **Full suite**: 1702 passed, 1 skipped (31 min, the Mac's full mirror).

## Follow-ups (HANDOFF)

- The 2005 FD's ellipsis row («1 : 8») left a `':'` category in `GRA_APRO`'s dictionary
  (`variables_cpv_personas_g04.yaml`). It is harmless (no record has it) but a parser fix
  (`_dict_fd`) plus `--variables` would remove it.
- 2000 occupation (CMO) has no SINCO bridge, and 2000/2005 have no disability or migration
  constraints beyond the above.
