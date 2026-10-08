# mxcensus

Data loaders for INEGI's open data: Mexico's **censuses, conteos and intercensal surveys**
(every edition from the 1990 census to the Encuesta Intercensal 2025), the **Marco
Geoestadístico** (1995–2025 frames), the **DENUE** economic-units directory, and
the **ENOE** and **ENIGH** household surveys.

`mxcensus` fetches pre-converted parquet files from a curated mirror, parses them
(handling INEGI's censoring and missing-data conventions), and returns clean,
analysis-ready pandas DataFrames.

> **Unofficial project.** `mxcensus` is an independent, community-maintained tool.
> It is **not** produced, endorsed, sponsored, or supported by INEGI. See
> [Data source and attribution](#data-source-and-attribution) below.

## Installation

Requires **Python 3.13+**. Install the latest release straight from GitHub:

```bash
uv pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git"
# or pin to a released tag:
uv pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
# or add it to a project:
uv add "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
```

Plain `pip` works too:

```bash
pip install "git+https://github.com/CentroFuturoCiudades/mxcensus.git@v0.1.0"
```

No data ships with the package — DataFrames are fetched on first use from the
public mirror and cached locally (run `mxcensus info` to see where).

### Development install

```bash
git clone https://github.com/CentroFuturoCiudades/mxcensus.git
cd mxcensus
uv pip install -e ".[dev]"   # editable, with build/test tooling
```

## Quick start

```python
import mxcensus

# Full pipeline for one state (9 = Ciudad de México)
census = mxcensus.load_census(state=9)

# Extended-questionnaire microdata
personas = mxcensus.load_extended_personas(state=9)
viviendas = mxcensus.load_extended_viviendas(state=9)

# Geometries (Marco Geoestadístico) merged with census counts
mg_aur, mg_loc_ageb = mxcensus.load_mg_census(state=9)

# Encuesta Intercensal 2025 — microdata (labelled, weighted) and the published estimates
viv, per, mig = mxcensus.load_cpv_survey(state=9)
est = mxcensus.load_cpv_estimaciones(nivel="municipal")
# …and the Censo 2020 in the same family (cuestionario ampliado + ITER/AGEB)
viv20, per20, mig20 = mxcensus.load_cpv_survey(2020, state=9, harmonize=True)

# Any Marco Geoestadístico layer, 2020 or 2025 frame
mun = mxcensus.load_mg("mun", state=9, period=2025)

# DENUE economic units — any release, harmonized to the latest schema by default
denue = mxcensus.load_denue(state=9)                      # latest release
denue_2010 = mxcensus.load_denue(state=9, release="201000")   # comparable to latest
raw = mxcensus.load_denue(state=9, release="201000", harmonize=False)  # raw schema

# ENOE labor-force survey — national quarterly microdata (no per-state split)
persons = mxcensus.load_enoe_persons(period="2023t1")     # analysis-ready person frame
persons = mxcensus.load_enoe_persons()                    # defaults to the latest quarter
sdem = mxcensus.load_enoe(table="sdem", period="2023t1")  # one raw table for one quarter
```

Pre-download a state's files (optional; loaders fetch on demand):

```bash
mxcensus fetch 9        # all four census datasets for state 9
mxcensus fetch 9 --dataset denue                  # DENUE (latest release) for state 9
mxcensus fetch 9 --dataset enoe --period 2023t1   # the five ENOE tables (national — 9 is ignored)
mxcensus fetch 9 --dataset cpv                    # EIC 2025 microdata for state 9 + the estimates
mxcensus fetch 9 --dataset cpv --edition 2020     # CPV 2020: microdata + ITER/AGEB for state 9
mxcensus fetch 9 --dataset mg --edition 2025      # every MG 2025 layer for state 9
mxcensus info           # cache directory and mirror URL
```

## Datasets

| Dataset | Level | Description |
|---------|-------|-------------|
| **ITER** | Locality | Aggregate counts (state → municipality → locality) |
| **RESARGEBUB** | Urban block | AGEB (urban statistical areas) and MZA (city blocks) |
| **Cuestionario Ampliado** | Microdata | Individual person and household records |
| **Censuses & intercensal surveys** (`cpv`) | Microdata + aggregates | Multi-year family, 1990–2025: the census, conteo and intercensal samples (dwellings, households, persons, emigrants per state), the ITER locality counts (1990–2020) and AGEB/block counts (2010, 2020), the EIC 2025 national estimates |
| **Marco Geoestadístico** | Geometries | INEGI's geostatistical frames as GeoParquet: 2020 and 2025 (15 layers/state + island polygons), 2010 (5 layers) and the municipal frames 1995–2005 |
| **DENUE** | Establishments | Economic-units directory, 25 releases 2010–2026, as point GeoParquet |
| **ENOE** | Labor force | Quarterly employment-survey microdata, 85 quarters 2005–2026, national (5 tables/quarter) |
| **ENIGH** | Income & expenditure | Biennial household income/expenditure microdata, 9 editions 2008–2024 (nueva serie 2016+ and the conciliated NCV 2008–2014), national (10–12 tables/edition) |

### Censuses and intercensal surveys (multi-year)

The `cpv` family holds every census, conteo and intercensal survey INEGI has published since
1990, the way ENIGH holds its editions. Files are faithful `str`-typed parquet,
`cpv_{table}_{year}_{NN}.parquet` per state (national tables `cpv_{table}_{year}.parquet`):

| edition | microdata (per state) | aggregates (per state) | weight |
|---|---|---|---|
| **Encuesta Intercensal 2025** | `viviendas`, `personas`, `migrantes` | national `estimaciones` | `FACTOR` |
| **Censo 2020** (cuestionario ampliado) | `viviendas`, `personas`, `migrantes` | `iter`, `ageb` | `FACTOR` |
| **Encuesta Intercensal 2015** | `viviendas`, `personas` | — | `FACTOR` |
| **Censo 2010** (cuestionario ampliado) | `viviendas`, `personas`, `migrantes` | `iter`, `ageb` | `FACTOR` |
| **II Conteo 2005** (sample) | `viviendas`, `hogares`, `personas` | `iter` | none |
| **XII Censo General 2000** (sample) | `viviendas`, `personas`, `migrantes` | `iter` | `FACTOR` |
| **Conteo 1995** (sample) | `personas`, `migrantes` | `iter` | `FAC_POB`, `FAC_VIV`, `FAC_PROM`¹ |
| **XI Censo General 1990** (10% sample) | `personas` | `iter` | none |

The EIC 2025 is representative of all 2,478 municipalities and the 233 localities of 50k+
inhabitants; `cpv_estimaciones_2025` is INEGI's national table of estimates. The Censo 2020
files hold the same values as the legacy `viviendas_NN`/`personas_NN`/`iter_NN`/
`resargebub_NN` files (checked cell by cell for all 32 states), but as INEGI's text:
zero-padded codes and the aggregates' `*`/`N/D`/`N/A` markers kept. The legacy loaders
(`load_census`, `load_extended_*`) and their files are unchanged. The 1990 and 1995 samples
are person files (each person carries the dwelling's items), and the 1990–2005 samples have
no key column: `ID_VIV`, `ID_HOG`, `ID_PERSONA` are derived from INEGI's composite parts.

¹ `FAC_POB` weights persons, `FAC_VIV` dwellings, households and emigrants, `FAC_PROM` the
health-coverage and disability items; with `harmonize=True` the persons' `FACTOR` is
`FAC_POB` and the emigrants' `FAC_VIV`.

```python
# Analysis-ready, labelled frames indexed by the record key (ID_VIV ⊂ ID_PERSONA / ID_MII)
viv, per, mig = mxcensus.load_cpv_survey(state=1)          # Aguascalientes
per["FACTOR"].sum()                                         # 1,534,416 = published POBTOT
per.groupby("SEXO", observed=True)["FACTOR"].sum()          # weighted, labelled
per = mxcensus.load_cpv_personas(state=[1, 9])              # several states, concatenated
raw = mxcensus.load_cpv(table="personas", state=1)          # faithful raw codes

# Older editions: the same loaders with period=
viv, per, mig = mxcensus.load_cpv_survey(2020, state=1)
viv15, per15, _ = mxcensus.load_cpv_survey(2015, state=1)    # no emigrants in 2015
hog05 = mxcensus.load_cpv_hogares(2005, state=1)            # the only household table
it = mxcensus.load_cpv(table="iter", period=2020, state=1, labels=True)  # '*'/'N/D' → NA

# ITER/AGEB by level, on string keys (CVE_ENT, CVE_MUN, CVE_LOC[, CVE_AGEB, CVE_MZA])
it = mxcensus.load_cpv_iter(2000, state=1)        # NIVEL estatal/municipal/agregado/localidad
ag = mxcensus.load_cpv_ageb(2010, state=1, nivel="ageb")
st, mun, loc, ageb = mxcensus.load_cpv_census(2020, state=1)   # = load_census(state=1)

# The published estimates: one row per geography, one column per indicator
est = mxcensus.load_cpv_estimaciones(nivel="municipal", state=1)
ee = mxcensus.load_cpv_estimaciones(estimador="ee")          # standard errors (also li/ls/cv)
```

The EIC 2025 expansion factors are calibrated to the estimates: Σ `FACTOR` over the
microdata equals the published population and occupied-dwelling totals **exactly** at every
geographic level, and the 2015 and 2010 Σ `FACTOR` equal INEGI's tabulados exactly. (The
2020 sample expands to the population of inhabited private dwellings, 125.5 M, not the
census total. CGPV 2000's `FACTOR` is a ratio estimator on preliminary counts, so it comes
close to the ITER without matching it.) The files are mirrored per state, so `state=` is
required (an INEGI code or a sequence of them). Variable dictionaries come from INEGI's data
dictionaries (the FD workbooks of 2005–2025, the PDF annexes of 1990–2000, and the ITER/AGEB
indicator dictionaries), overlaid by a hand-curated core. Every file is fingerprinted into a
per-table schema group and validated on load.

Editions keep INEGI's own column names. `harmonize=True` puts the shared **core** on the
latest edition's names, which are also the Marco Geoestadístico's: the 2020 `ENT`/`MUN`
become `CVE_ENT`/`CVE_MUN` and a `CVEGEO` is derived (in the ITER/AGEB also `ENTIDAD`/`LOC`/
`AGEB`/`MZA` → `CVE_ENT`/`CVE_LOC`/`CVE_AGEB`/`CVE_MZA`, with a 9- or 16-character
`CVEGEO`), codes the 2015 CSVs left unpadded are padded, and the 2010 keys (serials within
a state) become national. The ITER indicators an older edition spells differently take the
newest mnemonic (`cpv_iter_crosswalk()` lists them). Rows and Σ `FACTOR` are unchanged and
every other column stays verbatim. Each call loads one edition; stack editions yourself:

```python
import pandas as pd

frames = {p: mxcensus.load_cpv_personas(p, state=1, harmonize=True, labels=False)
          for p in (2020, 2025)}
per = pd.concat(frames, names=["PERIOD"])                   # core columns aligned
```

Only the core (keys, geography, sample design, `FACTOR`, `CLAVIVP`, `SEXO`, `EDAD`,
`TAMLOC`) is comparable across editions; other items keep each edition's codes.

`derived=True` adds the analysis columns of the legacy `load_extended_*` loaders, computed
from the raw codes: `EDAD_CAT`, `EDUC`, `CONACT_CAT`, `SITUA_CONYUGAL_CAT`, the health
coverage (`DHSERSAL_*`), commute (`MED_TRASLADO_*`) and financing (`FINANCIAMIENTO_*`)
dummies, `DIS_CON`/`DIS_LIMI`, the income and room bins… plus `DISCAPACIDAD`/`LIMITACION`,
INEGI's own definitions of disability and limitation (the legacy `DIS_CON`/`DIS_LIMI` count
a difficulty of unknown degree as unspecified, and the disabled as limited too),
`SIN_DISC_LIM`, INEGI's population without disability, limitation or mental condition (only
persons with all seven answers unspecified are left out; it reproduces every EIC 2025
`PSIND_LIM` estimate), and
`MADRE_EN_VIVIENDA`/`PADRE_EN_VIVIENDA` (whether the mother/father lives in the dwelling). For Censo
2020 the columns equal `load_extended_*`'s; the EIC 2025 gets the same columns through a
recode of the items INEGI renumbered (`SITUA_CONYUGAL`, `DHSERSAL`, two country codes).
EIC 2015 and Censo 2010 get the columns whose items map onto the 2020 codes (age, income,
education, activity, occupation and economic sector, marital status, health coverage,
birthplace and residence five years earlier, the partner and parents in the dwelling, and
religion in 2010; `cpv_derivations()` lists them per edition), with these differences. Neither edition has `DHSERSAL_IMSS_BIENESTAR`, because
neither asked about IMSS-PROSPERA/BIENESTAR. The EIC 2015 commute dummies follow its 7
modes, with 2015's wording for the three that 2020 splits, and its financing dummies follow
its one item, whose first code merges INFONAVIT, FOVISSSTE and PEMEX. Censo 2010 measured
disability with another question, so it gets its own `LIM_ACTIVIDAD` («limitación en la
actividad») instead of `DIS_*`/`DISCAPACIDAD`; it asked only whether the mother/father
lives in the dwelling, so it gets the co-residence flags but not `IDENT_MADRE_CAT`/
`IDENT_PADRE_CAT`. The EIC 2015 birthplace and residence columns reproduce INEGI's
tabulados in every state, and Censo 2010's residence reproduces its ampliado tabulado, up to
the few hundred persons whose state is not specified: INEGI counts them as not specified,
the derived columns as another state (the legacy 2020 rule, kept in every edition).
The coarse occupation (`OCUPACION_C_COARSE`) is the SINCO two-digit group in every edition
(Censo 2010 codes four digits, EIC 2015 three, as 2020); SINCO 2019 dropped group 59, so
its few 2010/2015 workers join group 52, where SINCO 2019 put them. The coarse activity is
the SCIAN sector. Both reproduce INEGI's 2010 and 2015 tabulados by occupational division
and sector in every state. Censo 2010's religion follows 2020's grouping, which counts the
neo-Israelite movements as evangelical (the 2010 ITER: other religions).
`cpv_constraints(table, period)` filters the census constraint sets (ITER indicator →
microdata cells) to the indicators an edition publishes and can reproduce, for
`get_tables_dict`. For Censo 2010 it adds the ITER's own limitation indicators (`PCON_LIM`,
`PSIN_LIM`, `PCLIM_*`) and religion groups (`PNCATOLICA`):

```python
per = mxcensus.load_cpv_personas(2025, state=1, derived=True)
per.groupby(["EDAD_CAT", "CONACT_CAT"], observed=True)["FACTOR"].sum()
tables = mxcensus.get_tables_dict(mxcensus.cpv_constraints("personas", 2025), per.dtypes)
```

The legacy health-coverage dummies `DHSERSAL_Popular_NGenración_SBienestar` and
`DHSERSAL_IMSS_Prospera/Bienestar` are named `DHSERSAL_SALUD_PUBLICA` and
`DHSERSAL_IMSS_BIENESTAR` here: the EIC 2025 swapped the two codes and widened the first
(any public health centre, including INSABI and Seguro Popular).
Municipalities were created between editions (2,428 in 1995, 2,478 in 2025; none retired):
`cpv_mun_lineage()` lists each new code with its parents, and
`cpv_municipal_units(start, end)` maps every municipality to a unit stable between two
frames, for comparing editions on one geography. Schema groups, reports and the
implementation history live in [docs/cpv/](docs/cpv/).

### DENUE (multi-temporal)

DENUE (Directorio Estadístico Nacional de Unidades Económicas) is mirrored for all 25
releases (2010–2026) × 32 states as point GeoParquet (`denue_{YYYYMM}_{NN}.parquet`,
EPSG:4326). Its schema drifted substantially over time (column names, encodings, the
`per_ocu` personnel strata), so `load_denue(state=N)` **harmonizes** each release to the
latest schema by default for longitudinal analysis; pass `harmonize=False` for the raw
release schema, or `release="YYYYMM"` for a specific edition. The schema groups and the
documented inconsistencies (drift, duplicates, malformed/missing files) live in
[docs/denue/](docs/denue/).

### ENOE (labor-force survey, multi-temporal)

ENOE (Encuesta Nacional de Ocupación y Empleo) is INEGI's quarterly labor-force survey.
Unlike the other datasets it is **national** — one file set per quarter, not per state — and
each quarter bundles **five tables**: `viv` (dwelling), `hog` (household), `sdem`
(sociodemographic, the main person table), and `coe1`/`coe2` (the two employment-questionnaire
parts). All **85 quarters** from 2005-T1 to 2026-T2 are mirrored (2020-T2 is excluded — field
operations were suspended for COVID and replaced by the telephone survey ETOE), as faithful
`str`-typed parquet named `enoe_{table}_{period}.parquet` (e.g. `enoe_sdem_2023t1.parquet`).

Loaders:

```python
# One raw table for one quarter (period defaults to the latest quarter)
sdem = mxcensus.load_enoe(table="sdem", period="2023t1")
sdem_jal = mxcensus.load_enoe(table="sdem", period="2023t1", ent=14)   # filter to a state

# The analysis-ready person frame: SDEM joined with COE1/COE2, filtered to the canonical
# working-age universe, with a numeric `fac_tri` weight and labour-force flags
persons = mxcensus.load_enoe_persons(period="2023t1")
persons["clase1"].cat.categories     # ['No aplica (…)', 'Población económicamente activa (PEA)', …]
persons["ing7c"].cat.ordered         # True — ordinal scales are ordered categoricals
persons["eda"].dtype                 # Int64 (sentinel codes 98/99 → NA)
raw = mxcensus.load_enoe_persons(period="2023t1", labels=False)   # the faithful raw codes

pop_15plus = persons["fac_tri"].sum()                              # ~99.7 M
pea        = persons.loc[persons["is_pea"], "fac_tri"].sum()       # economically active
participation = pea / pop_15plus                                   # ~0.602
informal   = persons.loc[persons["is_informal"], "fac_tri"].sum()
```

Every analysis-ready loader (`load_enoe_persons/viviendas/hogares/survey`, and the ENIGH
`load_enigh_hogares/viviendas/personas/survey`) returns **labelled** frames by default:
coded fields become labelled `Categorical` columns (ordered where the scale is ordinal),
numeric fields become numbers with INEGI's non-response codes as NA, the key/index columns
stay raw strings, and the result is validated by a strict schema (an out-of-dictionary value
raises). Pass `labels=False` for the faithful `dtype=str` codes; the low-level `load_enoe` /
`load_enigh` are raw by default (`labels=True` opts in). Weighted totals are identical either
way — flags and filters are computed from the raw codes.

`load_enoe_persons` adds `is_pea` / `is_ocupado` / `is_informal` boolean flags and a canonical
numeric `fac_tri` expansion weight (coalescing the pre-2020 `fac` and later `fac_tri` columns),
and handles the survey's cross-era drift automatically — the `ent`→`cve_ent` geographic-key
rename (2025-T3), the `FAC`→`FAC_TRI` weight rename (2020-T3), and the panel-era person key.
Every column is otherwise the faithful raw value. ENOE's schema drifts across eras, so each
file is fingerprinted into a **per-table schema group** and validated on load. The schema
groups, per-quarter inconsistency report, and validation report live in
[docs/enoe/](docs/enoe/).

Pass `harmonize=True` to any ENOE loader to canonicalize the **analytical core** across eras
so quarters stack for longitudinal analysis: column names lowercased, `fac`→`fac_tri`
(+ `fac_men`), `ent`/`mun`→zero-padded `cve_ent`/`cve_mun` plus a derived `cvegeo`,
`tipo`/`mes_cal` added (empty) before 2020-T3. Unlike DENUE, every other column is kept
verbatim — the COE alternates an *ampliado* (Q1) and a *básico* (Q2–Q4) questionnaire with
different item sets, so no era is projected onto another's column list:

```python
panel = pd.concat(
    mxcensus.load_enoe_persons(period=p, harmonize=True).assign(period=p)
    for p in ["2019t1", "2020t3", "2023t1", "2026t1"]
)
panel.groupby(["period", "cve_ent"])["fac_tri"].sum()   # same key/weight names in every era
```

#### Dwelling / household / combined loaders

The dwelling (`viv`) and household (`hog`) tables have their own analysis-ready loaders
(numeric weights + a hierarchical index), and `load_enoe_survey` loads all three household-survey
levels at once with a **shared, nested `MultiIndex`** — the way the extended-census microdata
shares `ID_VIV` / `[ID_VIV, ID_PERSONA]`:

```python
viviendas = mxcensus.load_enoe_viviendas(period="2023t1")   # one row per dwelling
hogares   = mxcensus.load_enoe_hogares(period="2023t1")     # one row per household
viviendas["fac_tri"].sum()   # ≈ 37.3 M dwellings

# All three levels together, indices nesting dwelling ⊂ household ⊂ person
viv, hog, per = mxcensus.load_enoe_survey(period="2023t1")
# the person index carries the household levels as a prefix, so persons group by household:
household_size = per.groupby(level=list(hog.index.names)).size()   # persons per household
```

Each frame is indexed by its level's key (`viviendas` by the dwelling key, `hogares` by the
household key = dwelling key + `n_hog`, `h_mud`, `personas` by the person key = household key +
`n_ren`), so the indices are clean prefixes and the levels align/join naturally (the keys adapt
per era — pre-2020-T3 quarters have no `tipo`/`mes_cal`; 2025-T3+ uses `cve_ent`). By default
`load_enoe_survey` returns **all** household members as `personas` (full `sdem`, so households
fully decompose); pass `persons="labor"` for the working-age labor-force analytical frame
instead (`is_pea`/… flags, but only interviewed 15+ members). All take an optional `ent=` state
filter.

### ENIGH (household income and expenditure survey, biennial)

ENIGH (Encuesta Nacional de Ingresos y Gastos de los Hogares) is INEGI's biennial household
income/expenditure survey — the source for poverty measurement, income deciles and household
expenditure structure. It is **national**, and each edition publishes **10–12 tables**
(`concentradohogar` — the per-household summary — plus `viviendas`, `hogares`, `poblacion`,
`ingresos`, `trabajos`, `agro`, `noagro`, `gastoshogar`, `gastospersona`, `erogaciones`, and
the 2008–2014-only `gastotarjetas`/`gastos`). Nine editions are mirrored as faithful
`str`-typed parquet `enigh_{table}_{year}.parquet`:

- **Nueva serie — 2016, 2018, 2020, 2022, 2024.** In 2016 INEGI merged the MCS into ENIGH,
  enlarged the sample (81.5 k → 105.5 k dwellings, state × urban/rural representativeness) and
  revised income capture: **a new statistical series**. ENIGH 2024 also updated questionnaires
  (housing items homologated to the 2020 census, new sociodemographic items, CCIF-2018
  expenditure codes) while keeping series comparability.
- **Nueva Construcción de Variables — 2008, 2010, 2012, 2014.** INEGI's re-expression of the
  traditional series with the MCS variable construction, conciliated to the 2010 census frame:
  the closest pre-break data. Estimates are **not directly comparable** with 2016+.

```python
# Analysis-ready household frame = INEGI's `concentradohogar` summary, numeric weight/income
hog = mxcensus.load_enigh_hogares(period="2024")          # indexed by (folioviv, foliohog)
hog["educa_jefe"].cat.categories                          # 'Sin instrucción' … 'Posgrado' (ordered)
hog.groupby("tam_loc", observed=True)["ing_cor"].mean()   # labelled, ordered locality size
hog["factor"].sum()                                       # 38,830,230 households
(hog["ing_cor"] * hog["factor"]).sum() / hog["factor"].sum()   # mean quarterly income

per = mxcensus.load_enigh_personas(period="2024")         # poblacion + numeric factor
viv, hog, per = mxcensus.load_enigh_survey(period="2022") # shared nested MultiIndex (2012+)
raw = mxcensus.load_enigh(table="gastoshogar", period="2022")   # any raw table, any edition
```

Each file is fingerprinted into a **per-table schema group** and validated on load. Pass
`harmonize=True` to canonicalize the **analytical core** across editions so they stack
(`factor_hog`/`factor_viv` → `factor`; the 2008/2010 `ingcor`/`tam_hog`/head `sexo`/`edad`/
`ed_formal` → `ing_cor`/`tot_integ`/`sexo_jefe`/`edad_jefe`/`educa_jefe`; derived `cve_ent`/
`cve_mun`/`cve_loc`/`cvegeo` from `ubica_geo`, which is 9 characters in 2012–2022 and 5 in
2008/2010/2024). Every other column — including the expenditure/income `clave` codes, whose
catalog changed in 2024 — is kept verbatim. The 2016 series break is documented, not
modelled. Schema groups and reports live in [docs/enigh/](docs/enigh/).

### Geometries (Marco Geoestadístico)

Every layer of INEGI's Marco Geoestadístico is mirrored per state as GeoParquet for two
frames: the **2020** census frame (`mg_{layer}_{NN}.parquet`) and the **Encuesta Intercensal
2025** frame (`mg_{layer}_2025_{NN}.parquet`). There are 15 layers in every state, `ent`,
`mun`, `a`/`ar` (urban/rural AGEBs), `l`/`lpr` (locality polygons/rural locality points),
`m` (blocks), `fm`, `e`, `cd`, `pe`, `pem`, `sia`, `sil`, `sip`, plus `ti` (island
territory) in the 13 states with islands (`mxcensus.data._catalog.MG_LAYERS` describes each).
Older frames, published by INEGI as one national ZIP, are split per state into the same
names (`mg_{layer}_{period}_{NN}.parquet`, INEGI's attribute names kept): **2010** v5.0
(`ent`, `mun`, `a`, `l`, `lpr`), the municipal frames **2005** and **2000** (`ent`, `mun`,
`a`) and **1995** (`ent`, `mun`).

```python
mun = mxcensus.load_mg("mun", state=9)                       # 2020 frame (the default)
agebs = mxcensus.load_mg("a", state=[1, 9], period=2025)     # several states, concatenated
mun95 = mxcensus.load_mg("mun", state=9, period=1995)        # municipal frame 1995
pts = mxcensus.load_mg("lpr", state=9, crs="EPSG:4326")      # reprojected
```

Codes (`CVEGEO`, `CVE_ENT`, `CVE_MUN`, …) stay zero-padded strings, so the 2025
municipalities join the EIC 2025 estimates and microdata on `CVEGEO`. INEGI ships its one
Lambert conformal conic projection under two spellings (a custom `MEXICO_ITRF_2008_LCC` WKT
on most layers, EPSG:6372 on a few), which geopandas treats as different CRSs.
`load_mg` therefore returns every layer on EPSG:6372 by default, without moving any
coordinate; pass `crs=None` for the stored CRS.

The convenience wrapper `load_mg_census(state=N)` consumes four 2020 layers (`a` urban
AGEB, `l` urban locality, `lpr` rural locality points, `ar` rural AGEB) and returns census
counts joined to geometry as a GeoDataFrame.

## Variable dictionaries

INEGI's variable dictionaries are bundled with the package and exposed as plain
dicts keyed by variable mnemonic — no download required:

```python
mxcensus.variables_iter()          # ITER indicators (name, description, range)
mxcensus.variables_resargebub()    # RESARGEBUB indicators
mxcensus.variables_personas()      # person microdata variables + category labels
mxcensus.variables_viviendas()     # household microdata variables + category labels
mxcensus.variables_denue("g10")    # DENUE variables for a schema group (g01..g11)
mxcensus.denue_schema_map()        # DENUE schema groups + the latest (harmonization target)
mxcensus.enoe_schema_map()         # ENOE per-table schema groups (viv/hog/sdem/coe1/coe2)
mxcensus.variables_enoe("sdem", "g04")   # ENOE variables for a (table, schema group)
mxcensus.variables_enoe_core()     # ENOE analytical-core labels (clase1, pos_ocu, …)
mxcensus.variables_enoe_labels("sdem", "g04")   # the merged dictionary the labelled loaders apply
mxcensus.enigh_schema_map()        # ENIGH per-table schema groups (concentradohogar/poblacion/…)
mxcensus.variables_enigh("concentradohogar", "g06")   # ENIGH variables for a (table, schema group)
mxcensus.variables_enigh_core()    # ENIGH analytical-core labels (clase_hog, educa_jefe, …)
mxcensus.variables_enigh_labels("poblacion", "g08")   # merged dictionary (core over DDI)
mxcensus.cpv_schema_map()          # CPV-family per-table schema groups (viviendas/personas/…)
mxcensus.variables_cpv("personas", "g05")   # CPV variables for a (table, schema group): g05 = EIC 2025
mxcensus.variables_cpv("personas", "g04")   # g04 = Censo 2020, g03 = EIC 2015, g01/g02 = Censo 2010
mxcensus.variables_cpv_core()      # CPV analytical-core labels (keys, geography, SEXO, EDAD, …)
mxcensus.variables_cpv_labels("personas", "g05")   # merged dictionary (core over the FD)
```

The ENOE and ENIGH per-group dictionaries carry a human-readable `Descripción`, the
question text (`Pregunta`) and code→label `Categorías` for every documented variable,
sourced from INEGI's DDI codebooks in the Red Nacional de Metadatos and overlaid by the
hand-curated core (ordinal order, numeric ranges, sentinel codes). Every entry follows
one contract: `Tipo` (`categorical` / `numeric` / `string`), `Categorías`, `Especiales`
(non-response codes), `Ordenada`, `Rango`, `Alias`.

The ITER and RESARGEBUB dictionaries are national (identical across states), so a
single copy of each is bundled. Note their schema differs from the microdata
dictionaries: aggregate indicators carry `Indicador` / `Descripción` / `Rangos` /
`Longitud` fields, while the microdata variables include categorical code→label
maps under `Categorías`.

## Data source and attribution

All data originates from INEGI's open-data ("datos abiertos") releases:

- Census tabular data and microdata — Censo de Población y Vivienda 2020:
  <https://www.inegi.org.mx/programas/ccpv/2020/>
- Earlier censuses and conteos (1990, 1995, 2000, 2005, 2010):
  <https://www.inegi.org.mx/programas/ccpv/>
- Intercensal survey microdata and estimates — Encuestas Intercensales 2015 and 2025:
  <https://www.inegi.org.mx/programas/intercensal/2015/>,
  <https://www.inegi.org.mx/programas/eic/2025/>
- Geometries — Marco Geoestadístico (1995–2025 frames):
  <https://www.inegi.org.mx/temas/mg/>
- Economic units — Directorio Estadístico Nacional de Unidades Económicas (DENUE):
  <https://www.inegi.org.mx/app/mapa/denue/>
- Labor-force survey — Encuesta Nacional de Ocupación y Empleo (ENOE):
  <https://www.inegi.org.mx/programas/enoe/15ymas/>
- Household income/expenditure survey — Encuesta Nacional de Ingresos y Gastos de los Hogares (ENIGH):
  <https://www.inegi.org.mx/programas/enigh/nc/2024/>

When you publish work that uses data obtained through `mxcensus`, INEGI's terms
require you to credit INEGI as the author of the data. Use the citation(s):

> **Fuente: INEGI, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Encuesta Intercensal 2025.**
>
> For the earlier editions, cite each by its name, e.g. **Fuente: INEGI, XII Censo General
> de Población y Vivienda 2000.**, **Fuente: INEGI, Encuesta Intercensal 2015.**,
> **Fuente: INEGI, Marco Geoestadístico 2010 v5.0.**
>
> **Fuente: INEGI, Marco Geoestadístico, Censo de Población y Vivienda 2020.**
>
> **Fuente: INEGI, Marco Geoestadístico, Encuesta Intercensal 2025.**
>
> **Fuente: INEGI, Directorio Estadístico Nacional de Unidades Económicas (DENUE).**
>
> **Fuente: INEGI, Encuesta Nacional de Ocupación y Empleo (ENOE).**
>
> **Fuente: INEGI, Encuesta Nacional de Ingresos y Gastos de los Hogares (ENIGH).**

The data is provided under INEGI's **Términos de Libre Uso de la Información del
INEGI** (Terms of Free Use):

- <https://www.inegi.org.mx/inegi/terminos.html>
- [Full text (PDF)](https://www.inegi.org.mx/contenidos/inegi/doc/terminos_info.pdf)

These terms permit copying, publishing, adapting, extracting, and even commercial
use of the information, **provided that** you (1) credit INEGI as author using the
citation above, (2) inform end users of any analysis or transformation applied to
the data, and (3) do not present your use as an official INEGI position or as
endorsed by INEGI.

### Notice of transformation

In compliance with the terms above (clause 1g), note that `mxcensus` does **not**
distribute INEGI's data unaltered. The original INEGI CSV files are transformed
before and during loading:

- **Format conversion** — the source CSVs are converted to parquet, and the Marco
  Geoestadístico shapefile/GeoPackage layers to GeoParquet (single-part geometries promoted
  to their Multi* form, integer attributes to int32), for the mirror. Each layer keeps its
  source CRS; `load_mg` relabels INEGI's two spellings of the one projection as EPSG:6372
  by default (no coordinate changes).
- **Censored values** — INEGI's `*` suppression marker (meaning 0, 1, or 2
  persons) is mapped to masked integers, and zeros are imputed where parent-level
  totals confirm a suppressed value must be 0.
- **Missing data** — INEGI's `N/D` marker is converted to `NaN`.
- **Derived columns** — the extended microdata loaders add summary flags (e.g.
  health-insurance, disability, transport, income bins) computed from the raw
  fields.
- **DENUE harmonization** — DENUE CSVs are converted to point GeoParquet (geometry
  from `latitud`/`longitud`); by default `load_denue` further **harmonizes** older
  releases onto the latest release's schema (renaming columns, normalizing the
  `per_ocu` and `tipoUniEco` strata across encodings, the `fecha_alta` date format,
  and adding/dropping columns). Pass `harmonize=False` for the raw release schema.
  A handful of undecodable bytes in one source file are replaced with U+FFFD (`�`)
  during conversion; otherwise text is preserved as INEGI published it — including
  the source data-entry errors the validation reports flag (e.g. non-numeric postal
  codes), which are **not** corrected or imputed. Point geometry is built from the
  coordinates as published and validated against each row's own state boundary: where a
  deterministic transform (a latitude/longitude swap or a dropped minus sign) places an
  offending coordinate back inside its state, the geometry is corrected accordingly
  (this covers the 2012 file where INEGI transposed the columns for all rows); points
  that no transform can place inside the state — or that fall outside Mexico entirely —
  get **null** geometry. In every case the raw `latitud`/`longitud` columns are kept
  verbatim; only the derived geometry is corrected or nulled.
- **ENOE** — the quarterly CSVs are converted to parquet as **faithful raw**: every column
  is kept as the text INEGI published, with no harmonization, imputation, or correction of
  values. The convenience loader `load_enoe_persons` **derives** an analysis frame from these
  raw tables (joining SDEM with the employment questionnaire, filtering to the canonical
  working-age universe, and adding a numeric `fac_tri` weight and `is_pea`/`is_ocupado`/
  `is_informal` flags), but leaves the underlying values untouched. One source-side encoding
  defect — a few mangled accented characters in two open-text SDEM fields
  (`cs_p21_des`/`cs_p23_des`) — is preserved as published, **not** corrected.
- **Censuses and intercensal surveys (`cpv`)** — every edition's CSV and DBF files are
  converted to parquet as **faithful raw** text: every value as INEGI published it
  (fixed-width DBF padding trimmed), including the estimates' `NA`/`MI` and the ITER/AGEB
  `*`/`N/D`/`N/A` markers. The
  `load_cpv_*` loaders only **derive** analysis frames (numeric `FACTOR`, a record-key
  index, labels from INEGI's dictionaries, and — with `harmonize=True` — the latest
  edition's names for the core geography plus a derived `CVEGEO`), and
  `load_cpv_estimaciones` reshapes the estimates to one row per geography with `NA`/`MI` as
  missing values. No value is imputed or corrected.
- **ENIGH** — every edition's CSV tables are converted to parquet as **faithful raw** text. The `load_enigh_*` loaders only **derive** analysis frames (numeric weights joined from `concentradohogar` where a table carries none, a hierarchical index, and — with `harmonize=True` — canonical names for the analytical core plus geography derived from `ubica_geo`); no value is imputed or corrected.
- **Labelled survey frames** — with `labels=True` (the default of the ENOE/ENIGH/CPV analysis-ready loaders) coded values are replaced by the labels of INEGI's own dictionaries (DDI codebooks or data dictionaries + the bundled core), numeric fields are parsed and INEGI's non-response codes (`99`, `&`, …) become missing values. The mirror and `labels=False` keep the codes verbatim.

**These transformations are performed by `mxcensus`, not by INEGI.** Any errors,
imputations, or derived values are the responsibility of this package and must not
be attributed to INEGI. INEGI's own variable dictionaries are bundled unmodified
(see [Variable dictionaries](#variable-dictionaries)); for the unaltered source
data files and their complete metadata and catalogs, download directly from the
INEGI links above.

## License

The `mxcensus` **source code** is released under the [MIT License](LICENSE).

This license covers only the software (the Python package, build scripts, and the
bundled YAML configuration). It does **not** apply to the census data, which
remains subject to INEGI's *Términos de Libre Uso de la Información del INEGI* as
described in [Data source and attribution](#data-source-and-attribution) above.
The bundled variable dictionaries are derived from INEGI's published dictionaries
and are likewise attributable to INEGI as their source.