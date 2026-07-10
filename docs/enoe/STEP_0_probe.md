# ENOE Unit 0 — URL + ZIP-layout probe

Empirical verification of INEGI's ENOE bulk-download URLs and in-ZIP table naming,
performed before committing the catalog (`_enoe_catalog.py`, Unit 1). All findings below
were verified live against `inegi.org.mx` on **2026-07-10**.

## ⚠️ Gotcha: INEGI serves soft-404s with HTTP 200

A missing file returns **HTTP 200** with `Content-Type: text/html` and a ~2263-byte HTML
placeholder — *not* a 404. **Status code alone is meaningless.** A URL is only real when
`Content-Type: application/x-zip-compressed` (ZIP) or `application/pdf`. The build's
existing `fetch_zip_verified` → `verify_zip` (`scripts/_build_common.py`) already catches
this downstream (the HTML body fails `zipfile` integrity), but any URL-existence probe
must check Content-Type, not the status line.

## Download tree

Base (target the **15ymas** = 15-and-older directory, not `14ymas`):
```
https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/
```
One ZIP **per quarter** contains **all 5 tables** (VIV, HOG, SDEM, COE1, COE2). There is no
per-table or per-state split — ENOE is national. Format probed: **CSV** (`_csv.zip`).

## Three filename regimes (verified)

| Regime | Quarters | ZIP filename template | Example (real size) |
|--------|----------|-----------------------|---------------------|
| **Old ENOE**  | 2005-Q1 … 2020-Q1 | `{year}trim{q}_csv.zip`         | `2019trim1_csv.zip` (31 MB) |
| **ENOEN**     | 2020-Q3 … 2022-Q4 | `enoe_n_{year}_trim{q}_csv.zip` | `enoe_n_2021_trim3_csv.zip` (32 MB) |
| **New ENOE**  | 2023-Q1 … latest  | `enoe_{year}_trim{q}_csv.zip`   | `enoe_2023_trim1_csv.zip` (37 MB) |

Note the underscore differences: old has **no** underscores around the year; new-ENOE and
ENOEN insert them (`enoe_2023_trim1`, `enoe_n_2021_trim3`). The regime is a pure function of
the period — no per-quarter exceptions were found.

**Boundaries pinned by probe:** `2020trim1` real, `2020trim2/3/4` all soft-404 (old naming);
`enoe_n_2020_trim3/4` real; `enoe_n_2022_trim4` real, `enoe_2022_trim4` soft-404;
`enoe_n_2023_trim1` soft-404, `enoe_2023_trim1` real. So the switchovers are exactly
old→ENOEN at 2020-Q1/Q3 and ENOEN→new at 2022-Q4/2023-Q1.

**Earliest / latest:** `2004trim4` soft-404 (2005-Q1 is the first quarter). `enoe_2026_trim1`
real; `enoe_2026_trim2/3/4` soft-404 → **2026-Q1 is the latest available quarter**.

**2020-Q2 gap:** absent under *both* namings (`2020trim2_csv.zip` and
`enoe_n_2020_trim2_csv.zip` both soft-404). Q2-2020 exists only as **ETOE** — a separate
telephone-survey product at a different endpoint
(`inegi.org.mx/contenidos/investigacion/etoe/`). Document-and-skip (plan Unit 10 covers it).

### Quarter inventory (as of 2026-07-10)

**84 quarters**, 2005-Q1 → 2026-Q1, excluding 2020-Q2:
- Old ENOE: **61** (2005-Q1…2019-Q4 = 60, + 2020-Q1)
- ENOEN: **10** (2020-Q3, 2020-Q4, all of 2021, all of 2022)
- New ENOE: **13** (all of 2023–2025, + 2026-Q1)

Mirror scale: 84 × 5 tables = **420 parquet files**.

## In-ZIP layout (verified by downloading one ZIP per regime)

All members are flat at the ZIP root (no `conjunto_de_datos/` subdir). Comma-delimited CSVs.
Member core is always `{TABLE}T{Q}{YY}` (Q = quarter digit 1–4, YY = 2-digit year); the
**prefix and case differ by regime**:

| Regime | SDEM member example | Prefix | Case | Extra members |
|--------|---------------------|--------|------|---------------|
| Old   | `sdemt119.csv`        | none      | lower | `nota_bases_datos_enoe_2019_1t.txt` |
| ENOEN | `ENOEN_SDEMT321.csv`  | `ENOEN_`  | UPPER | `nota_bases_datos_enoen_2021_3t.txt` |
| New   | `ENOE_SDEMT123.csv`   | `ENOE_`   | UPPER | (none) |

**Robust member matcher for the build** (regime-agnostic): case-insensitive regex
`^(?:enoe_|enoen_)?{table}t{q}{yy}\.csv$` against each member's basename. The 5 table
tokens (`viv`, `hog`, `sdem`, `coe1`, `coe2`) are mutually unambiguous.

**No bundled dictionary.** The CSV ZIPs carry only a small `nota_*.txt` (old/ENOEN) or
nothing (new) — so `_extract_dictionary`'s "read the diccionario from the ZIP" path (DENUE)
does **not** apply. Dictionaries are separate FD PDFs (see below); Unit 4 sources categories
data-derived + hand-curated, exactly as the plan assumes.

## Column structure (SDEM header, verified per regime)

Column **names are lowercase** in every regime (even when the member *filename* is
uppercase). Delimiter is comma. Schema drift confirmed:

| | Old 2019-Q1 | ENOEN 2021-Q3 | New 2023-Q1 |
|---|---|---|---|
| SDEM columns | 104 | 114 | 114 |
| Keys present | `cd_a,ent,con,v_sel,n_hog,h_mud,n_ren` | + `tipo,mes_cal` | + `tipo,mes_cal` |
| Weights | `fac` | `fac_tri,fac_men` | `fac_tri,fac_men` |
| Design strata | `est_d,t_loc` | `est_d_tri,est_d_men,t_loc_tri,t_loc_men` | (same as ENOEN) |

- `ca` was **not** present in 2021-Q3 (consistent with the documented "CA only 2020-Q3…2021-Q2" rule).
- All precodificado analytical vars present in every regime: `clase1, clase2, pos_ocu,
  rama_est1, rama_est2, emp_ppal, ing7c, seg_soc, c_ocu11c`.
- Canonical-filter columns present in every regime: `r_def, c_res, eda`.

This is exactly the era-drift the fingerprint schema-groups (Unit 3) will capture; the
`fac`→`fac_tri` rename and the key additions are the analytical-core harmonization targets
(Unit 9).

## FD dictionary PDFs (partial — Unit 4 follow-up)

Separate from the microdata ZIPs, under `enoe/15ymas/doc/`. Era-dependent naming; probed:
- `enoe_123_fd_c_bas_amp.pdf` (2023-Q1) — **real** (2.1 MB PDF)
- `enoe_n_fd_c_bas_amp.pdf` (ENOEN, generic) — **real** (1.6 MB PDF)
- `enoe_119_fd_c_bas_amp.pdf` (old 2019-Q1) — soft-404 (old-era doc uses a different name/path)
- `enoe_126_fd_c_bas_amp.pdf` (2026-Q1) — soft-404 (latest quarter's FD not at this exact name)

So the FD-PDF URL scheme is only partly pinned. Unit 4 must run its own doc-URL probe before
relying on FD parsing; the plan already defers full FD parsing (hand-curated core +
data-derived categories), so this does **not** block Units 1–3.

## Implications for Unit 1 (catalog)

- `_BASE = "https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/"`.
- `EnoeQuarter(period, year, quarter, regime, zip_template)` with the 3 templates above;
  `regime ∈ {"enoe_old","enoen","enoe_new"}` (or derive template from `(year, quarter)`).
- Period id: `"{year}t{q}"` e.g. `2023t1` — lowercase, sortable, mirrors the `T123` core.
- `QUARTERS`: 2005t1 … 2026t1, **excluding 2020t2**; `latest_quarter()` → `2026t1`.
- `table_member_name` / a member-matcher must be regime-aware (prefix + case) or use the
  regex above; the build extracts one member per (quarter, table).
- `CATALOG_VERIFIED_DATE = "2026-07-10"`.

## Status: ✅ Unit 0 complete — proceed to Unit 1.
