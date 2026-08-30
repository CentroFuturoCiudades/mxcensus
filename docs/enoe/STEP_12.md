# STEP 12 — Human-readable dictionaries (INEGI DDI) + labelled loaders

**Goal.** Make the ENOE output resemble the extended-census loaders: labelled categorical
columns, human-readable variable dictionaries, and a strict Pandera schema on the
analysis-ready frames. Shared with ENIGH (`docs/enigh/STEP_4.md`).

## 1. Dictionary source: INEGI's DDI codebooks (RNM), not the FD PDFs

INEGI publishes **DDI-Codebook 1.2.2** metadata for every ENOE year in the Red Nacional de
Metadatos (a NADA catalog): `https://www.inegi.org.mx/rnm/index.php/catalog/<id>`, codebook
at `…/catalog/ddi/<id>` (XML namespace `http://www.icpsr.umich.edu/DDI`). One catalog entry
per (year, questionnaire): the *ampliado* entry holds the T1 files, the *básico* entry T2–T4;
the data-file names encode the quarter (`SDEMT123` = sdem 2023-T1). Each `var` carries
`labl` (description), `qstnLit` (question), `varFormat type`, `valrng`, and `catgry`
code→label pairs with `missing="Y"` on non-response codes. The id table is
`scripts/_dict_ddi.py::ENOE_DDI` (2005–2025; 2026 quarters reuse 2025's questionnaire
metadata by best column overlap — 98 % for the 2026-T1 ampliado).

Coverage check (2026-08-29, local subset of 12 quarters): every parquet column of every
matched quarter is documented; 3,933 / 3,937 categorical columns have every observed code
labelled once zero-padding is reconciled (the DDI pads `'01'` where the CSV emits `'1'`);
the rest are free-text `*_des` fields. The FD PDFs (`enoe_123_fd_c_bas_amp.pdf`, AES-encrypted,
column-table layout) were parsed as a first attempt and dropped — the DDI is complete and
structured.

## 2. Build: `--dictionary` + DDI-aware `--variables`

- `build_enoe.py --dictionary` downloads (once) the codebooks that may document
  `--periods` into `data/dict/ddi/` (git-ignored).
- `--variables` now writes, per column and in priority order: the **core** entry
  (`variables_enoe_core.yaml`, verbatim), the **DDI** entry (label, question, type, code
  labels re-spelled to the data's padding; observed codes the DDI lacks are appended with an
  identity label and flagged in `Nota`), else the **data**-enumerated identity map. Rules in
  `_dict_ddi.dictionary_entry`: a DDI enumeration wider than `--cat-threshold` whose codes are
  all integers (the DDI lists every age) → `Tipo: numeric` with the `missing` codes as
  `Especiales`; an all-numeric observed set the DDI covers < 50 % (hours, years, amounts
  documented by a few special codes) → numeric; only sentinel codes documented → numeric.
  **No `Rango` is taken from the DDI** — its `valrng` is the edition's observed min/max, not
  the questionnaire's bounds (a group spans editions). Bounds live in the core.
- Provenance is printed per group (`core=…, ddi=…, ddi+data=…, data=…`).

## 3. Dictionary contract (`variables_*_core.yaml` header)

`Descripción` / `Pregunta` / `Tipo` (`categorical|numeric|string`, legacy spellings tolerated
by `_schema_groups.norm_tipo`) / `Longitud` / `Categorías` / `Especiales` (sentinels: extra
categories for a categorical, NA for a numeric) / `Ordenada` / `Rango` / `Alias` (raw
spelling → canonical code) / `Decimales` (→ `Float64`, else `Int64`). The core was
normalised to it and widened (`sex`, `e_con`, `niv_ins`, `anios_esc`, `hrsocup`, `ingocup`;
`ing7c`/`niv_ins` ordered; `eda` numeric with 98/99 as NA).

## 4. Loaders

- `load_enoe(..., labels=False)` (raw default) — `labels=True` applies
  `_schema_groups.label_frame` (Alias → code→label map / sentinel→NA + `to_numeric`; an
  unmapped code **raises** listing the codes) and validates with `build_labelled_schema`
  (`CategoricalDtype` of the labels, ordered per `Ordenada`; `Int64`/`Float64` + `Rango`;
  unique key index; undeclared columns pass through) via `validate_raise`.
- `load_enoe_persons/viviendas/hogares/survey(..., labels=True)` — labelled **by default**;
  flags and the canonical filter are computed from the raw codes first, so weighted totals
  are identical either way (tested 2023-T1, 2005-T1). Key/identifier columns
  (`enoe._KEY_COLUMNS`, incl. `tipo`/`mes_cal`) are never labelled — they are the shared
  nested index and stay raw strings.
- Raw schemas: `build_group_schema` accepts `Especiales`/`Alias` codes, checks `Tipo:
  numeric` columns (parse + `Rango` or sentinel), and blanks a whitespace-only cell to NA
  before the checks (INEGI writes `' '` for not-applicable). `_latest_schema` likewise.
- `variables_enoe_labels(table, gid)` — the merged dictionary keyed by raw and harmonized
  names.

## 5. Regeneration order (full mirror, on the build host)

```bash
uv run python scripts/build_enoe.py --dictionary          # DDI codebooks → data/dict/ddi/
rm src/mxcensus/_yaml/variables_enoe_*_g*.yaml
uv run python scripts/build_enoe.py --schema-map
uv run python scripts/build_enoe.py --variables           # core > DDI > data
uv run python scripts/build_enoe.py --validate            # 0 failures = every code labelled
```

`--validate` is the **label-coverage gate**: the raw group schema's `isin` is built from the
same `Categorías ∪ Especiales ∪ Alias` keys the labelled path maps, so a file that passes it
can never trip `labels=True` at runtime.
