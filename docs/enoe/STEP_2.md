# ENOE Unit 2 — Build/convert to parquet

Created `scripts/build_enoe.py` (maintainer-only), which downloads each ENOE quarter's
CSV ZIP from INEGI and converts each of the five tables to a faithful-raw parquet:
`enoe_{table}_{period}.parquet` (e.g. `enoe_sdem_2023t1.parquet`). No geometry — ENOE has
no coordinates — so conversion is a plain zstd `to_parquet`. Also modified
`scripts/_build_common.py` to add `"enoe_"` to `PRESERVE_PREFIXES` (so a registry rewrite
never drops ENOE entries).

## Design (mirrors `build_denue.py`, minus geometry/state)

- **CSV reading** — `_sniff_encoding` / `_read_csv_robust` are copied **verbatim** from
  `build_denue.py` (ENOE shares DENUE's encoding zoo). Kept local rather than imported so
  this build stays independent of the DENUE loader's module-level imports (geopandas,
  shapely, `mxcensus.denue`). `dtype=str, low_memory=False` — every field read as text
  (faithful, and avoids mixed str/float object columns pyarrow can't serialise).
- **`_df_to_parquet`** — normalises object-column NaN → None (an empty cell under
  `dtype=str` reads as float NaN, so a column can mix str + NaN, which pyarrow may refuse),
  then `to_parquet(..., compression="zstd")`. No values otherwise altered.
- **`_build_quarter`** — fetches the quarter's ZIP **once** (via
  `bc.fetch_zip_verified`; ZIP basenames are globally unique across regimes, so the
  basename is a safe cache key), extracts it, and for each requested table locates the CSV
  member with `_enoe_catalog.find_member` (regime-agnostic prefix/case regex), reads it,
  and writes one parquet. A table absent from the ZIP is reported `missing` (no file), not
  fatal. Extract dir is deleted after conversion (`--keep-raw` to retain); the cache ZIP is
  retained for re-runs.
- **CLI** (`main`): `--periods` (default all quarters), `--tables` (default all 5),
  `--output`/`--raw-dir`/`--cache-dir`, `--retries`, `--keep-raw`, `--report-only` (on-disk
  parquet inventory), `--dry-run` (print the planned (quarter, table) → file plan + URLs +
  member names, **no download**). Unknown periods/tables error out. Per-quarter build is
  wrapped in try/except so one malformed/unavailable quarter doesn't abort a full sweep.

Schema fingerprinting, the inconsistency report, variable dictionaries, validation and the
registry append are **not** in this unit — they arrive in Units 3–7 (mirroring the DENUE
machinery). This unit is download → convert only.

## Verification (2026-07-10, live against INEGI)

`--dry-run` over `2023t1 2021t3 2019t1` printed the correct ZIP URL, regime, and in-ZIP
member name for all three regimes (`ENOE_SDEMT123.csv`, `ENOEN_SDEMT321.csv`,
`sdemt119.csv`), matching STEP_0.

Real build `--periods 2023t1` produced **5** parquet files; row counts match the source
CSVs exactly and column counts match STEP_0's SDEM=114:

| table | rows | cols | source encoding |
|-------|-----:|-----:|-----------------|
| viv   | 150,566 | 25  | utf-8 |
| hog   | 151,368 | 37  | utf-8 |
| sdem  | 450,263 | 114 | cp1252 |
| coe1  | 366,771 | 189 | utf-8 |
| coe2  | 366,771 | 137 | utf-8 |

Re-opened with `pd.read_parquet`: all columns `str` dtype; the person key
(`cd_a,ent,con,v_sel,n_hog,h_mud,n_ren,tipo,mes_cal`), weights (`fac_tri,fac_men`),
canonical-filter columns (`r_def,c_res,eda`), and all precodificado analytical vars
(`clase1,clase2,pos_ocu,rama_est1,rama_est2,emp_ppal,ing7c,seg_soc,c_ocu11c`) are present.

## Source-data anomaly (INEGI defect, not a build bug)

SDEM 2023-Q1 contains exactly **two** distinct high bytes: `0xCB` and `0xD0`, only in the
open-text "reason for change of residence" fields `cs_p21_des` / `cs_p23_des`. In context
they clearly stand for **Ó** (`REMODELACI?N`, `CAMBI?`, `INDEPENDIZ?`) and **Ñ**
(`A?OS`, `COMPA?IA`, `ACOMPA?AR`) — but **no** encoding (cp1252, latin-1, cp850, cp437,
cp858, cp860, mac_roman, iso-8859-15, and every Python-aliased codec) maps `0xCB→Ó` and
`0xD0→Ñ`. The accents were mangled by some export step in INEGI's own pipeline; the intended
letters are **unrecoverable** from these bytes, so any "fix" would be fabrication.

The faithful choice — and what the build does — is to preserve the bytes **losslessly**:
`_sniff_encoding` picks cp1252 (utf-8 strict fails; only these two single-byte high bytes,
both defined in cp1252, so it decodes cleanly), and cp1252 round-trips `0xCB↔Ë`, `0xD0↔Ð`
bijectively, so the original source bytes remain recoverable from the parquet. This mirrors
DENUE's policy: source mojibake is preserved verbatim and flagged, never rewritten/imputed.
The affected columns are open-text and non-analytical; every analytical/precodificado column
is clean ASCII. Unit 3's inconsistency report should surface such per-file anomalies
systematically across quarters.

## Status: ✅ Unit 2 complete — proceed to Unit 3 (schema map + inconsistency report).
