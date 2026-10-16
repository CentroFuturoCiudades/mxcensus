# CPV Unit 8i — the ITER on stable units; the count constraints' terms

Done **2026-10-15** (on the Mac). HANDOFF candidates 1 (a public `cpv_constraint_terms`)
and 3 (a cross-edition ITER panel on the stable units), the user's choice «both together»
over either alone and the release. Gate: `load_cpv_iter_panel` adding up to every ITER in
all 32 states at both levels, `cpv_constraint_terms` equal to the guide's `design()`
helper, the 1990 → 1995 municipal step bundled and rebuilt from the mirror, the guide's
examples rerun, tests green. No mirror file, dictionary or derivation changed.

## Decisions (user, 2026-10-15)

| question | decision |
|---|---|
| the next unit | **the ITER panel + `cpv_constraint_terms`** (over the panel alone, the helper alone, the 0.16.0 release alone) |
| the averages | **exact + weighted** (recommended): `REL_H_M`/`PROM_OCUP` the ratio of the unit's counts; `GRAPROES`, `PROM_HNV`, `PRO_OCUP_C` the members' values weighted by a published base (over: exact ones only; counts only) |
| 1990, which has no frame | **derive the 1990 → 1995 step** from the localities that moved, bundled in `cpv_mun_lineage.yaml` (recommended; over a municipal panel from 1995) |
| 2025 | **the EIC 2025's published municipal counts** (recommended; over adding the counts behind its percentages, or leaving 2025 out) |
| locality units across states | **complete units**: the other state's members are read (recommended; over summing the requested states only, with a warning) |
| reserved `*` members at the locality level | **the known sum + a bound** (`N_RESERVED`, `RESERVED_POB`; recommended; over missing, or an option) — asked after the probe showed the strict rule blanks about half of the merged units of 2,500+ |

Taken without asking: the panel in `cpv_aggregates.py`; long, indexed `(PERIOD, UNIT)`
(the package's `pd.concat(…, names=["PERIOD"])` convention), balanced (every unit in every
edition, `N_CODES` 0 where none is listed); the names of each unit's most populous member
per edition; `PHOG_IND` left out of the default whenever 2025 is combined with a census
(its definition counts more relatives, 6w); the 1990 shares measured at the Conteo 1995
(see below); the national test trimmed to 1990 → 2020 for the localities (the full run is
below).

## The probe (every ITER, 32 states)

- **Every `Int64` column of every ITER is a count**: the municipalities add up to their
  state in all 32 states of 1990, 1995, 2000, 2005, 2010, 2020 — except CGPV 2000's
  `GRAPROES` (`GRADOESCO`), an average INEGI publishes in whole years, typed `Int64`.
- **The averages** (`Float64`): `REL_H_M` = `POBMAS / POBFEM × 100` and `PROM_OCUP` =
  `OCUPVIVPAR / VIVPAR_HAB` (2020: `/ TVIVPARHAB`, not `VIVPAR_HAB` — 44 off at a state
  otherwise) within the published rounding everywhere (1990/1995 truncate: 0.01).
  `GRAPROES` weighted by `P_15YMAS`, `PROM_HNV` by `P_12YMAS_F`, `PRO_OCUP_C` by the rooms
  `OCUPVIVPAR / PRO_OCUP_C`: the state's value from its municipalities within 0.015, 0.009
  and 0.008 (INEGI's rounding 0.005; their bases — who gave their schooling, the women who
  said how many children, the dwellings with rooms — are not published). The EIC 2025's
  `PROM_OCUP` is of the `VIVPARHAB_C` dwellings, whose occupants are not published:
  weighted by `VIVPARHAB_C`, within 0.0064. The Conteo 1995's percentages (`P_P0A4` …)
  are left out.
- **Localities vs municipalities**: the localities add up to their municipality but
  `POBTOT`, `TVIVHAB` and `VIVTOT` (persons and dwellings INEGI places in no locality), in
  every edition; the Conteo 1995's municipalities also hold their `agregado` rows.
- **Gaps**: the Conteo 1995 did not count 15 municipalities of Chiapas (in the 1990 ITER
  and the 1995 frame, not in the 1995 ITER); CGPV 2000's Nicolás Ruíz (07-058) publishes
  only `POBTOT`.

## The 1990 → 1995 municipal step (`build_geo_crosswalk.py`)

1990 has no frame; 25 municipalities of the 1995 frame are not in the 1990 ITER (2,403 →
2,428; the 1990 codes are a subset, checked). Each takes as parents the 1990 municipalities
whose localities the locality lineage moves into it at 1995 (`code` and `absorption`
links of `PERIOD` 1995; the parent = the municipality of the locality's earlier code).
Population shares, measured at the Conteo 1995 — the analogue of the frames' areas on the
later frame:

- each 1995 locality a link brings into the new municipality weighs its 1995 `POBTOT`
  (reserved 0), split among its links' municipalities by their 1990 counts (La Magdalena
  Tlaltelulco, 29048: 8,409 persons in 29010 and 1,159 in 29029 in 1990, one locality of
  12,174 in 1995);
- `parte_del_nuevo` = the parent's share of that population; `parte_del_origen` = its share
  of the parent's population before the split (the parent's 1995 `POBTOT` + everything it
  lost in the step).

Why 1995 and not 1990: some seats were parts of a 1990 locality (Valle de Chalco's Xico
inside Chalco city; San Lorenzo Axocomanitla inside Zacatelco), so they have no 1990 count.
A 1990 measure needed a fallback that gave Chalco a `parte_del_origen` of 1.02. Measured
in 1995, Valle de Chalco took 62% of Chalco's pre-split population. A locality whose
parts come from two municipalities without a 1990 count for each raises (none does).

Result (`cpv_mun_lineage.yaml`: `periodos` + `1990`, `municipios['1990']` 2,403, 25
changes; the frames' changes byte-identical): 21 single-parent municipalities, e.g. 01010/
01011 ← 01001, 15122 ← 15025 (0.999; Tláhuac's six boundary localities below 5%), 02005 ←
02004 (0.98; Ensenada below 5%); two parents: 12076 (12072 0.913, 12063 0.087), 29048
(29010 0.879, 29029 0.121). `cpv_municipal_units(1990, …)` works with no code change (the
units read `periodos`); its error for an unknown edition is now «no municipal lineage».
`test_units_cover_the_iter` from 1990: every 1990 municipality has a unit, one common set
with 2020, 81,249,645 persons.

## `load_cpv_iter_panel(periods, *, state, nivel="municipal", indicators=None, …)`

- **Units**: `cpv_municipal_units(first, last, min_share=, cross_state=)` or
  `cpv_locality_units(first, last, absorptions=, confirmed=)`; a municipality without a
  unit raises; a locality without one is its own.
- **Editions**: the ITERs (1990, 1995, 2000, 2005, 2010, 2020) and, at the municipal level,
  2025 = `load_cpv_estimaciones(nivel="municipal")` (`valor`), matched by name (53 counts
  and averages; 40 shared with the 2020 ITER, 39 in a 2020/2025 panel without `PHOG_IND`).
- **States**: the units with a member in `state`; the other states' members of those units
  are read too (`extra`: the localities moved between states, 248 units for 1990 → 2020).
- **Columns**: `N_CODES`, `N_RESERVED`, `RESERVED_POB` (missing where a reserved member's
  own `POBTOT` is reserved, as in the Conteo 1995), `NOM_ENT`, `NOM_MUN`[, `NOM_LOC`], then
  the indicators — by default those every requested edition publishes (`_panel_indicators`:
  the `Int64` columns and `_AVERAGES`) but the crosswalk's `Comparable: false` (`PHOG_IND`,
  `PCLIM_VIS`, `PCLIM_MOT2`, `PDER_SEGP`) and `_ESTIMATES_NOT_COMPARABLE` with 2025; a list
  keeps those, missing where an edition lacks one, and raises on one no edition publishes.
- **Sums** (`_unit_sum`): over the members' known values, missing where none is known.
  **Averages** (`_unit_values`, `_AVERAGES` by edition): `ratio` over the members that give
  both counts, `mean` over those that give value and weight; a base of 0 is missing.
- Aguascalientes 1990/2000/2020: 11 municipalities → 9 units (01001 with El Llano and San
  Francisco de los Romo), 22 indicators in common; Tlaxcala 1990–2025: 44 → 60
  municipalities, La Magdalena Tlaltelulco's 12% from 29029 joins two families of
  municipalities into one unit of six (`min_share` 0.10 — a larger one splits them);
  Aguascalientes city 2000 → 2020: 26 localities of 2000, 17 with a reserved count, 108
  persons.

**The national run** (all 32 states, the six ITER editions; the sweep, 77 s municipal,
234 s localities): every edition's municipalities and localities exactly once
(`N_CODES` = the ITER's rows: 2,403 … 2,469 municipalities, 156,602 … 199,391
localities), Σ `POBTOT` = the ITER's at both levels in every edition (the Conteo 1995's
localities 90,065,931, without its agregado rows), and the 2,112 rows of the units that
span two states identical in both states' panels. The suite runs the municipalities over
the six editions and the localities 1990 → 2020.

## `cpv_constraint_terms(frame, constraints)`

Each record's 0/1 term of each count constraint, a `float64` frame on the frame's index;
the cell masks are shared with `cpv_ratio_terms` (`_cell_mask`, which now also names a
variable the frame lacks: «load it with derived=True»). Equal to the guide's `design()` on
the EIC 2025's persons (214) and dwellings (93) of state 01 (0.3 s for 177,984 × 214);
`test_eic2025_constraints_equal_estimates` counts through it.

## Docs

- `GUIDE.md`: §5 uses `cpv_constraint_terms` (the `design()` helper is gone); §6 the 1990
  step (an example) and a new subsection «The ITER on stable units» (four examples:
  Aguascalientes 1990/2000/2020, 2020/2025, the city's locality unit); the function index.
  `test_cpv_guide.py` green (its 18 files cover the examples).
- README: `cpv_constraint_terms` and `load_cpv_iter_panel` in the CPV overview.
- `cpv_geo`'s docstrings (1990), `build_geo_crosswalk.py`'s module doc and the YAML header.

## Tests

The Mac's full suite: **1989 passed, 1 skipped** (8g's 1976 + 8h's 4 + 9 new; pytest's
clock 1 h 11 min, 35 min at 8g — the panel tests take ~5 min, the machine was asleep or
throttled part of the run: 2 h 26 min wall at 51% CPU). New and changed:

- `test_cpv_aggregates.py`: `test_panel_unit_values` (synthetic: known sums, the three
  average rules, an indicator the edition lacks), `test_panel_arguments`,
  `test_iter_panel_municipal_real`, `test_iter_panel_1990_2025_real` (Tlaxcala),
  `test_iter_panel_localities_real`, `test_iter_panel_national` (municipal, localidad).
- `test_cpv_derived.py`: `test_cpv_constraint_terms`; the EIC 2025 constraints test through
  it.
- `test_cpv_geo.py`: the document with 1990, the 1990 → 1995 shares (Valle de Chalco, La
  Magdalena Tlaltelulco), `cpv_municipal_units(1990, 2020)`, the rebuild test now also
  needs the 1990/1995 ITER, the coverage test from 1990.

## Left

- The EIC 2025's counts behind its percentages in the panel (`counts=True`: exact only to
  the rounding; the user chose the published counts).
- A 2015 edition for the panel: the EIC 2015 publishes no aggregate in the mirror.
- The 1995 locality panel cannot see the localities of one and two dwellings (INEGI lists
  them only as each municipality's sums).

## Release

With the user's go-ahead (2026-10-15, the user's choice over the AGEB on stable units, a
panel notebook and the small leftovers), 8h–8i as **0.16.0** (`pyproject.toml`, `uv.lock`,
the README's install pins): the Mac's full suite on 8i, **1989 passed, 1 skipped** (1 h 7
min); `main` fast-forwarded to the release commit, tagged `v0.16.0` and pushed with
`cpv-integration`; `wsl`'s pull waits for a Tailscale re-login (HANDOFF). No data changed
(registry 4276; the lineages are bundled).
