# STEP 4 — Human-readable dictionaries (INEGI DDI) + labelled loaders

Same design as ENOE `docs/enoe/STEP_12.md` (read that first); ENIGH specifics below.

## DDI source

One RNM codebook per edition (`scripts/_dict_ddi.py::ENIGH_DDI`): 2008 = 7, 2010 = 30,
2012 = 75, 2014 = 165 (Nueva Construcción de Variables), 2016 = 310, 2018 = 511, 2020 = 685,
2022 = 901, 2024 = 1116. Data-file stems match the canonical table names; the 2008/2010
NCV codebooks call `concentradohogar` `concentrado` (`build_enigh._DDI_STEM_ALIASES`).
**Every column of every table in every edition is documented** (checked 2026-08-29); 3,948 /
3,968 categorical columns have every observed code labelled. `&` (INEGI's "no
especificado" glyph) becomes `Especiales`, partial month maps are completed, mixed padding
across the editions of one group is accepted; the residue after regeneration is 7 entries
(`clave` catalog in `erogaciones`, `inst_1/2='08'`, the off-by-one `noatenc_*` codes),
identity-labelled and flagged in `Nota`. Cross-checked against the "Descripción de la base de
datos" PDFs: the 2024 DBD's range for `inst_1/2` explicitly skips `08` yet the data carries it,
and the 2008 `noatenc_N` columns hold code N-1 while the codebook documents N — INEGI
codebook gaps, left as identity codes.

## Regeneration (local mirror is complete, 99 files)

```bash
uv run python scripts/build_enigh.py --dictionary
rm src/mxcensus/_yaml/variables_enigh_*_g*.yaml
uv run python scripts/build_enigh.py --schema-map
uv run python scripts/build_enigh.py --variables      # 61 files; provenance per group printed
uv run python scripts/build_enigh.py --validate       # label-coverage gate
```

After regeneration the per-group files are ~98 % `core`+`ddi` sourced (e.g.
`poblacion/g08`: core=9, ddi=176). `Tipo` distribution over all 61 files: 2,757 categorical,
2,017 numeric, 229 string.

## Core

`variables_enigh_core.yaml` normalised to the shared contract: `tam_loc`, `est_socio`,
`educa_jefe` ordered; `educa_jefe` keeps only the padded codes with an `Alias` for the
un-padded 2012 spellings (replaces the `_latest_schema` special case); `edad`/`edad_jefe`
`Rango: [0, 120]`, `tot_integ [1, 60]`, money columns `Decimales: "2"` (→ `Float64`).

## Loaders

`load_enigh(labels=False)` raw by default; `load_enigh_hogares/viviendas/personas/survey`
labelled by default (`labels=True`): `_attach_factor` joins from the raw household summary
first, then the frame is labelled once, indexed, and validated strictly. Σ `factor` and
Σ `ing_cor` are identical with `labels=False` in every edition tested (2008, 2012, 2016,
2024; `_HOUSEHOLDS` totals unchanged).
