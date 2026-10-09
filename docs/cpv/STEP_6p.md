# CPV Unit 6p — Censo 2020 in the tabulado checks

Done **2026-10-09** (night, on the Mac; unattended, see `STEP_6m.md`). Gate: the Censo 2020
derived columns (the base edition, = the frozen legacy `load_extended_*` ones) checked
against INEGI's cuestionario ampliado tabulados in every state, both sexes and the nation,
tests green.

## Why

2020's derived columns equal the legacy ones by construction (6b), and the EIC 2025 cells
equal its published estimates (6b, 6g), but nothing had checked the 2020 columns against
INEGI's own numbers. INEGI's 2020 ampliado tabulados (`ccpv/2020/tabulados/ampliado/
cpv2020_a_eum_NN_tema.xlsx`, found through the file-listing API, `idBiinegi` 3001,
`tipodocto` 5) are computed from the same sample and weights, so they must match to the
person. (The EIC 2025 publishes its tabulados only as OLAP cubes; its constraints already
equal its downloadable estimates.)

## The checks

`scripts/check_cpv_tabulados.py` reads the `.xlsx` workbooks (`_dict_fd.read_workbook`;
`fetch` accepts an OLE2 or ZIP signature) with the same «Estimador» reader as 2010/2015:

| tabulado | cells | derived columns |
|---|---|---|
| 08-06 | the employed by occupational division | `OCUPACION_C_COARSE` |
| 08-08 | the employed by sector | `ACTIVIDADES_C_COARSE` |
| 08-12 | the employed by hours worked: up to 40 (its «hasta 32», «33 a 40» and «no trabajó» together), 41–48, 49–56, more than 56, NE | `HORTRA_CAT` |
| 09-04 | the population by affiliation and institution: IMSS, ISSSTE (federal or state), PEMEX/Defensa/Marina, INSABI, IMSS-BIENESTAR, private, other, not affiliated, NE | `DHSERSAL_*` |
| 10-06 | students who travel, by mode (several per person) | `MED_TRASLADO_ESC_*` |
| 10-12 | the employed who travel, by mode | `MED_TRASLADO_TRAB_*` |
| 11-02 | the married or in union aged 12+, by whether the partner lives in the dwelling | `IDENT_PAREJA_CAT` |
| 16-34 | the owned dwellings bought or built, by financing source (several) | `FINANCIAMIENTO_*` |

Two readings the tabulados required: the commute tables count the students aged 3+ and the
employed aged 12+ who travel, so a person of unspecified age (999) who answered a mode is
left out (with them, 22 states were 1 to 315 students over and 18 states 2 to 325 workers);
and an institution's footnote digit («ISSSTE4») is dropped before matching.

## Results (all 32 states, both sexes, the nation)

**Every 2020 cell is exact** — 5,247 cells; the largest gap, 0.26 of a person, is the
rounding of the six-decimal percentages at the national total. So the 2020 derived columns
(= the frozen legacy ones) reproduce INEGI's own estimates: the coarse occupation and
activity, the hours bins, the affiliation dummies (ISSSTE federal and state together, the
INSABI under `DHSERSAL_SALUD_PUBLICA`, IMSS-BIENESTAR), the 2020 commute dummies (several
answers per person), `IDENT_PAREJA_CAT` and the financing dummies.

The report now has 15,708 cells (2000 5,148; 2010 1,980; 2015 3,333; 2020 5,247),
none beyond tolerance.

## Tests

- `tests/test_cpv_tabulados.py`: the check list now spans 2020 (`.xlsx` sources); the
  real state-01 test covers it (159 cells, all exact; 476 in all).
- **Full suite**: 1772 passed, 1 skipped (31 min, the Mac's full mirror; with 6o; `test_cpv_tabulados.py` rerun after the commute fix: 8 passed).
