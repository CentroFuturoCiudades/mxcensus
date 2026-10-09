# CPV Unit 6n — the legacy constraints on the 2000/2005/2010 samples' own items

Done **2026-10-08** (night, on the Mac; chosen unattended, see `STEP_6m.md`). Gate: every
legacy constraint an edition's ITER publishes and its sample can answer is a cell, each new
cell checked against the ITER in all 32 states, tests green.

## The gap

`cpv_constraints(table, period)` keeps a legacy (Censo 2020) constraint only when every
variable and category of its cells exists in the edition's frame. The 1990/1995 samples got
their own cells in 6j (`_EDITION_CELLS`); 2000, 2005 and 2010 still missed the indicators
their ITER publishes but their items spell differently:

| edition | missing (legacy indicators the ITER publishes) | why |
|---|---|---|
| 2000 | `P5_HLI`, `P5_HLI_NHE`, `P5_HLI_HE`, `P15A17A`, `P15YM_AN`; 15 dwelling cells | 2000's labels («Sí habla algún dialecto», «No sabe leer y escribir»…), item names (`ELECTRI`, `DISAGU`, `REFRIG`, `TELEVI`…) |
| 2005 | `P5_HLI*`, `P6A11_NOA`, `P12A14NOA`; 15 dwelling cells | `HABLENIN`/`HATAMESP`/`ASIS_ESC`, `MAT_PISO`, `DIS_ELEC`, `DIS_AGUA`, `DIS_SANI`, `DIS_REFR`… |
| 2010 | every dwelling cell (28) | no `CLAVIVP_CAT` (every legacy dwelling cell requires it) |

## What changed

- **2010 `CLAVIVP_CAT`**: 2010's `CLAVIVP` is 2000's classification (casa independiente,
  departamento, vecindad, azotea, local no construido, móvil, refugio, NE), so the 2000/2005
  recode applies (`_RECODE["2010"]["CLAVIVP"]`); «Vivienda» = classes 1–4 and NE, which is
  exactly the ampliado tabulados' «viviendas particulares habitadas» (3b). This enables
  all the legacy dwelling cells whose items 2010 shares with 2020 (floor, bedrooms, rooms,
  drainage, car, radio, washing machine, landline, mobile, internet).
- **`_EDITION_CELLS`** for 2000, 2005 and 2010, by each ITER's definitions:
  - persons: indigenous language (5+, with or without Spanish), literacy (15+), school
    attendance (2000 15–17; 2005 6–11 and 12–14);
  - dwellings: floor (2005 also earth), electricity (2010 also without), piped water within
    the dwelling or plot (2005/2010 also without), sanitary service (**2000: the exclusive
    one**, `SERSAN` and `USOEXC`, as its `VP_SERSAN`), electricity + water + drainage,
    none of the three (2000/2005), «sin ningún bien» (**2000: its ten goods** — radio, TV,
    video, blender, fridge, washing machine, phone, boiler, car, computer; **2005: its own
    item** `NODISBIE` over four goods; **2010: nine** — radio, TV, fridge, washing machine,
    car, computer, landline, mobile, internet), and each good.
  - The household head's sex (`HOGJEF_F`/`HOGJEF_M`) stays out: 2000–2010 have no such
    dwelling item (it would need the person file).

| edition | personas | viviendas |
|---|---|---|
| 2000 | 29 → **34** | 4 → **16** (`VPH_1DOR` out, below) |
| 2005 | 38 → **43** | 8 → **21** |
| 2010 | 142 | 0 → **26** |

## A crosswalk fix: 2000's `VP_CCUART` is not one bedroom

The sweep put 2000's `VPH_1DOR` (one bedroom, a 6i constraint) 12 points (!) off its ITER in
every state. The ITER column is 2000's `VP_CCUART`, which its dictionary describes «con un
dormitorio», like 2005's `VPH_1DOR`, so 4b's description matching paired and renamed it.
The counts say otherwise: `VP_CCUART` is the dwellings with **one room when an exclusive
kitchen is not counted** — the rule of its sibling `VP2_5CUAR` («2 a 5 cuartos, no incluye
cocina exclusiva») — within 0.2 points in states 01, 09, 15, 20, 30 (bedrooms = 1 is 12–17
points higher, and INEGI's own sample tabulado VI06 agrees with the bedrooms). Fix:
`build_cpv._XW_UNPAIR` gets `("2000", "VP_CCUART")` and a note; the regenerated
`cpv_iter_crosswalk.yaml` (402 → 403 indicators) changes only those two entries, so
`harmonize=True` no longer calls 2000's one-room count `VPH_1DOR`, and 2000 loses the
`VPH_1DOR` constraint (its ITER publishes no bedrooms count).

## Verification: every cell against the ITER, 32 states

Each constraint's share (Σ `FACTOR` over its cells / Σ `FACTOR`; the 2005 sample is
unweighted) against the ITER's (the indicator / `POBTOT` or `VIVPAR_HAB`; an indicator the
crosswalk keeps under the edition's name is read under it), per state:

| edition, table | new cells | median \|Δ\| | 90th pct. | max \|Δ\| | the edition's other cells (median) |
|---|---|---|---|---|---|
| 2000 personas | 5 | 0.13 | 0.56 | 2.79 (Chiapas, language) | 0.33 |
| 2000 viviendas | 13 | 0.42 | 1.15 | 2.67 (water) | 0.70 |
| 2005 personas | 5 | 0.01 | 0.09 | 1.38 (Chiapas) | 0.21 |
| 2005 viviendas | 13 | 1.08 | 3.69 | 11.75 (Quintana Roo) | 0.73 |
| 2010 viviendas | 25 | 0.54 | 1.98 | 5.70 (Nayarit, radio) | — |

The new cells sit in the band of each edition's existing ones; the definitions check out
where they differ (2000's ten goods: «sin ningún bien» median 0.19; 2010's nine: 0.10;
2005's `NODISBIE`: 0.05; 2000's exclusive sanitary service: mean −0.34, the non-exclusive
reading would be ~2 points high). What is left is the samples, not the cells:

- **2000** (persons): the census `POBTOT` includes the population estimated for dwellings
  without occupant information, which has no age; the sample has none, so every age cell of
  states 02, 06, 15, 17 (up to 7 points in Baja California) sits above the ITER's share.
- **2005**: the Conteo's sample is unweighted, and Quintana Roo's is far off (persons aged
  5+ 10.6 points, every dwelling cell ~11); outside it, up to ~6.6 points.
- **2010**: bedrooms are 2–5 points apart (the ampliado's question; `VPH_1DOR` below the
  ITER in every state), as are radio and mobile in a few states.

## Tests (`tests/test_cpv_derived.py`)

- `test_cpv_constraints_per_edition`: the 2010 dwelling set (26, `CLAVIVP_CAT` + own
  cells, nine goods), the 2000/2005 person and dwelling sets (2000 without `VPH_1DOR`,
  exclusive sanitary service, 2005's `NODISBIE`).
- `test_source_codes_match_2020`: 2010 `CLAVIVP` (the same reviewed gap as 2000/2005).
- `test_6n_cells_equal_iter` (real, state 01): the 5 + 13 + 5 + 13 + 26 cells within 0.3
  points (persons) / 2.5 (dwellings) of the ITER.
- `test_crosstab_per_edition`: the dwelling tables of every edition 1990–2020 build, and
  2000/2005/2010's services table (class × electricity × water × drainage).
- **Full suite**: 1769 passed, 1 skipped (31 min, the Mac's full mirror; two tests updated
  during the run — the 2010 listing and dwelling classes — pass on the rerun).
