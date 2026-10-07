# CPV Unit 1a — `scripts/build_cpv.py` + the EIC 2025 build

Done **2026-10-07**. Gate: the 97 `cpv_*_2025*` files on `wsl`, every source ZIP
CRC-verified, row counts below. Code: commit `a702f3e` (pushed to `origin/cpv-integration`).

## What was built

`scripts/build_cpv.py` (maintainer-only). It reuses `_build_common.fetch_zip_verified`
(download, full CRC check, retry, cache under INEGI's own edition-qualified basename) and the
unit-0 catalog (`EDITIONS_BY_PERIOD`, `find_member`, `cpv_zip_entry`, `CpvEdition.filename`).

- **Jobs** (`_plan`): one per ZIP, `(edition, product, state, tables)`. A per-state product gives
  one job per `--states` entry. The national `estimaciones` product gives one job with
  `state=None`, whatever `--states` is. The full 2025 plan is 33 ZIPs → 97 files.
- **Members** (`_member_plan`): table → member via `find_member`; `None` when no unique match.
  Only those members are extracted, into `raw/cpv/{period}/{product}/{NN|nacional}/`. The
  per-state subdirectory is there because 1995's `datgen95.dbf` carries no state code. Extracts
  are deleted after conversion unless `--keep-raw`.
- **Statuses** per table: `ok` / `absent` / `malformed` (download/ZIP failure, or an unreadable
  CSV) / `missing` (no member). The sweep continues past failures, and the exit code is 1 when
  any table failed. A re-run resumes from the ZIP cache: no re-download, only re-conversion.
- **Enabled editions**: `_ENABLED = ("2025",)`. `--dry-run` previews any edition (URLs, member
  regexes, output names). A real build of a non-enabled edition, e.g. the DBF ones, is a usage
  error until its unit enables it.
- Catalog addition: `CpvEdition.per_state(product)`, plus a module assertion that per-state URLs
  coincide with per-state tables.

### Faithful-raw read with pyarrow (no pandas)

- **Encoding sniff, streamed** (`_sniff_encoding`). It makes the same decision as
  `build_enigh._sniff_encoding` but reads 16 MiB chunks. Pass 1 counts high bytes and runs a
  strict incremental UTF-8 decode; only a file that fails gets pass 2 (U+FFFD count under
  `utf-8/replace`, strict cp1252). Incremental decoders carry split multi-byte sequences
  across chunks, and a test pins the one-shot equality at chunk sizes 1, 3 and 16 MiB.
- **Read** (`_read_csv_arrow`). The header is read first with `csv.reader`, BOM stripped as
  pyarrow strips it, and duplicate names raise. Then `pyarrow.csv.read_csv` runs with every
  column typed `string`, `null_values=[""]` and `newlines_in_values=True`.
  - `utf-8/replace` files are read through `codecs.EncodedFile(…, errors="replace")`, because
    pyarrow's own transcoder is strict.
  - cp1252/latin-1 use `ReadOptions(encoding=…)`.
- **Write**: `pq.write_table(table, path, compression="zstd")`, default 1 Mi-row row groups.
  The Arrow type is `string`, where pandas 3's `to_parquet` writes `large_string`. Both read
  back as pandas `str`, and `fingerprint` hashes column names only.
- **Equivalence with the pandas path** (`build_enigh._read_csv_robust` + `_df_to_parquet`),
  compared with `pd.read_parquet` + `assert_frame_equal` on states 01 and 09:
  - **identical** for all six microdata files;
  - the estimaciones file differs in exactly **5,065 cells holding the literal string `NA`**.
    pandas' default NA list would null them; `null_values=[""]` keeps them verbatim, so they
    are equal once `NA` is masked. Keeping them is the faithful choice; the 1b dictionary
    should declare `NA` (and `MI`, 8,855 cells) as estimaciones `Especiales`.
  - A build-free test pins the equivalence on a synthetic file.
- **Memory**: on the Mac, a run of state 15 alone (Estado de México: personas 2.3 M rows × 92
  cols, 66.7 MiB ZIP) peaked at **1.6 GB** RSS, and states 01 + 09 + estimaciones at 0.7 GB.
  The largest file, Oaxaca personas (2.4 M rows), was built only on `wsl`. The pandas
  `dtype=str` alternative was not measured; the handoff estimated tens of GB for it.

## EIC 2025 build on `wsl`

`nohup .venv/bin/python scripts/build_cpv.py --periods 2025 > build_cpv_2025.log 2>&1 &` on
`wsl:~/mxcensus` (branch `cpv-integration` at `a702f3e`; the checkout there was on `main` at
`5ad37b1` before). INEGI served at ~0.3–0.7 MB/s. The log stays untracked at
`wsl:~/mxcensus/build_cpv_2025.log`.

Run 11:50 → 12:28 (~38 min, download-bound): **97 files written, 0 failed/missing**. All 33 ZIPs
(727 MiB of microdata ZIPs + 8.3 MB estimaciones) pass the full CRC check. 96 files are UTF-8,
1 is cp1252 (estimaciones), and no file needed `utf-8/replace`. The parquet total is 543.6 MiB.
Process peak RSS was 2.27 GB (`ru_maxrss` is cumulative; on the Mac, state 15 alone peaked at
1.6 GB).

| state | ZIP MiB | viviendas rows | personas rows | migrantes rows | parquet MiB (v/p/m) |
|---|---|---|---|---|---|
| 01 | 5.1 | 48,538 | 177,984 | 5,060 | 0.7/3.2/0.07 |
| 02 | 4.7 | 50,317 | 153,906 | 1,182 | 0.8/2.9/0.02 |
| 03 | 2.8 | 29,601 | 90,185 | 350 | 0.5/1.8/0.01 |
| 04 | 5.8 | 55,426 | 192,068 | 1,345 | 0.9/3.6/0.03 |
| 05 | 11.6 | 124,095 | 406,572 | 3,114 | 1.7/6.9/0.05 |
| 06 | 4.1 | 42,039 | 129,603 | 1,724 | 0.7/2.5/0.03 |
| 07 | 51.2 | 512,608 | 2,092,680 | 24,540 | 6.7/31.3/0.33 |
| 08 | 14.7 | 168,337 | 508,496 | 5,370 | 2.3/8.7/0.08 |
| 09 | 13.8 | 144,814 | 442,778 | 2,208 | 1.8/8.1/0.04 |
| 10 | 11.1 | 110,631 | 391,482 | 7,559 | 1.7/6.6/0.11 |
| 11 | 22.7 | 223,876 | 796,597 | 17,670 | 3.1/13.2/0.24 |
| 12 | 32.3 | 317,279 | 1,146,271 | 26,699 | 4.6/18.9/0.35 |
| 13 | 29.9 | 298,475 | 980,308 | 18,342 | 4.1/17.1/0.25 |
| 14 | 39.1 | 407,180 | 1,355,591 | 18,778 | 5.3/22.7/0.26 |
| 15 | 66.7 | 653,934 | 2,295,122 | 15,251 | 8.7/38.9/0.22 |
| 16 | 37.3 | 372,592 | 1,285,076 | 27,655 | 5.3/21.5/0.38 |
| 17 | 14.4 | 140,710 | 463,112 | 5,911 | 2.1/8.3/0.09 |
| 18 | 8.5 | 88,191 | 299,490 | 3,727 | 1.3/5.1/0.06 |
| 19 | 16.8 | 184,155 | 589,658 | 2,511 | 2.3/10.1/0.05 |
| 20 | 70.2 | 705,853 | 2,395,039 | 52,603 | 10.0/41.0/0.67 |
| 21 | 59.4 | 571,396 | 2,086,905 | 32,797 | 7.9/34.9/0.44 |
| 22 | 9.3 | 93,233 | 318,757 | 6,612 | 1.3/5.6/0.10 |
| 23 | 5.4 | 57,139 | 178,706 | 678 | 0.9/3.3/0.02 |
| 24 | 20.2 | 198,608 | 686,573 | 11,968 | 2.9/11.8/0.17 |
| 25 | 10.0 | 102,331 | 342,137 | 3,859 | 1.5/5.9/0.06 |
| 26 | 13.3 | 142,938 | 443,419 | 3,835 | 2.1/7.7/0.06 |
| 27 | 9.7 | 103,617 | 338,515 | 1,280 | 1.5/5.8/0.03 |
| 28 | 12.6 | 137,501 | 421,231 | 3,855 | 1.9/7.3/0.06 |
| 29 | 17.9 | 166,111 | 612,107 | 4,988 | 2.3/10.5/0.08 |
| 30 | 69.6 | 730,541 | 2,368,150 | 34,667 | 10.0/40.0/0.47 |
| 31 | 21.1 | 204,379 | 713,742 | 2,952 | 2.9/12.5/0.05 |
| 32 | 15.2 | 153,601 | 520,076 | 13,589 | 2.1/8.8/0.19 |
| **total** | | **7,340,046** | **25,222,336** | **362,679** | |

`cpv_estimaciones_2025.parquet`: 13,880 rows × 349 cols (9.8 MiB). The expected AGS counts from
the handoff (48,538 / 177,984 / 5,060; 13,880 × 349) match.

## Structural checks (all 32 states)

Run read-only on `wsl` with a scratch script (kept outside the repo). These become `_REAL`
tests in 1c. **Every check passes in every state:**

- `ID_VIV` (always 12 chars), `ID_PERSONA` (always 17) and `ID_MII` are unique within their tables.
- `ID_PERSONA[:12] == ID_VIV` for every person.
- Every person's and every migrant's `ID_VIV` exists in viviendas, and every dwelling has at
  least one person.
- `CVE_ENT` is constant and equals the file's state in all three tables. `ID_VIV[:2]` equals the
  state, and `CVEGEO == CVE_ENT + CVE_MUN` row by row.
- Column counts are 87 / 92 / 27 everywhere.
- `FACTOR` is constant within a dwelling, and each person's `FACTOR` equals their dwelling's.
- **Σ `FACTOR` matches the estimaciones `Valor` exactly in every state**: personas = `POBTOT`,
  viviendas = `VIVPARHAB`. Nationally both are exact: **130,393,389** persons and **39,699,242**
  occupied private dwellings. The expansion factors are calibrated to the published estimates,
  so this is an equality, not a confidence-interval check.

## What the files look like (input for 1b/1c)

- Column sets: viviendas 87, personas 92, migrantes 27, identical in all 32 states, so each
  table should have one schema group. Estimaciones: 349 columns.
- Keys: `ID_VIV` (12 chars), `ID_PERSONA` (17), `ID_MII`. `ID_VIV[:2]` = the state, so
  `ID_VIV` is unique **nationally** (unlike 2010's 8-char state-scoped `ID_VIV`, `STEP_0`).
- Leading columns: `CVEGEO, CVE_ENT, CVE_MUN, LOC50K, ID_VIV, ID_PERSONA, TIPO_REG, COBERTURA,
  ESTRATO, UPM, FACTOR, CLAVIVP, …`; `TAMLOC` is near the end. Migrantes has
  `MPER, MCONRES, MSEXO, MEDAD, …` and no `ID_PERSONA`. It is a sibling of personas under the
  dwelling, as `PLAN.md` §Keys assumed.
- Not-applicable cells are **empty**, so they are null in parquet. There are no whitespace-only
  cells, unlike ENIGH's `' '`. In state 01, the housing-characteristics block (`PAREDES`…
  `SERV_TV_PAGA`) is null in exactly 60 rows. Those are the `CLAVIVP` `07` (53) and `09` (7)
  dwellings; in the 2020 coding these are non-residential premises and shelters, to be confirmed
  against the FD in 1b. In state 01, `TIPO_REG` is `0` for every dwelling but `0`/`1` in
  personas (1,107 × `1`; meaning TBD in 1b).
- `SEXO` is coded `1`/`3`, as in CPV 2020. Codes keep their zero-padding (`NIVACAD` `00`…`11`,
  `CONACT` `10`…`80`).
- Estimaciones: `ESTIMADOR` ∈ {`Valor`, `Error estándar`, `Límite inferior de confianza`,
  `Límite superior de confianza`, `Coeficiente de variación`}, 2,776 rows each. The geography is
  `CVEGEO` (9) + `CVE_ENT`/`CVE_MUN`/`CVE_LOC`, with names `NOM_*`. The nation is `00`/`000`/`0000`,
  with 32 states and 2,743 sub-state geographies (2,776 in all). Cells contain `NA` and `MI` besides numbers.
- **Calibration**: Σ `FACTOR` equals the estimaciones `Valor` exactly (not just inside LI–LS).
  Personas sum to `POBTOT` and viviendas to `VIVPARHAB` (= `TOTHOG`) for every state;
  `FACTOR` is constant within a dwelling and equals the viviendas `FACTOR`. These become the
  `_REAL` data checks in 1c.

## Tests

`tests/test_cpv.py` gained the build-free build-script tests:
- `_sniff_encoding` streamed vs one-shot (7 inputs × 3 chunk sizes);
- the faithful read (padding, `NA` kept, quoted newline, BOM, cp1252, `utf-8/replace`,
  duplicate header);
- arrow ↔ pandas parquet equivalence;
- `_plan` (97 files for the full 2025 plan, national once);
- `_member_plan` on probed member lists (missing → `None`);
- CLI guards;
- catalog: `per_state` ⇔ `NATIONAL_TABLES`, and ZIP cache names unique across every
  edition/product/state.

Full suite (Mac, local mirror present): **661 passed** in 14 min, up from 628 after unit 0.
The 4 warnings are the pre-existing DENUE/ENOE value-level ones.

## Deviations from the plan

- The microdata are read with pyarrow, not `build_enigh._read_csv_robust`/`_df_to_parquet`
  (`PLAN.md` §Critical files listed those as "reused as is"). The handoff had already flagged
  this for memory reasons.
- `null_values=[""]`: unlike the other families' pandas builds, NA-like strings stay verbatim.
  That only matters for estimaciones (`NA`).
- `CpvEdition.per_state` was added to the catalog.
- The commit was split: the code (`a702f3e`) was committed and pushed mid-unit so `wsl` could
  build it; the docs follow in a second commit.
