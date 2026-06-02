# DENUE validation report

Each mirrored file validated against its group's tight schema (`_group_schema`). Files: 800. Failing: 50.

## denue_201100_08.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `A.P.`

## denue_201100_09.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 3 row(s), e.g. `C.P.`

## denue_201100_11.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `|`

## denue_201100_14.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `CP 44`

## denue_201100_15.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `|`

## denue_201100_17.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P.`

## denue_201100_19.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 2 row(s), e.g. `Â¦`

## denue_201100_22.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `. 771`

## denue_201100_26.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P.`

## denue_201100_28.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P.`

## denue_201100_30.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P.`

## denue_201100_31.parquet (g02) — FAIL
- `Código postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P.`

## denue_201200_14.parquet (g04) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `CP 44`

## denue_201200_31.parquet (g03) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `C.P. `

## denue_201502_02.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `2253O`

## denue_201502_07.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 4 row(s), e.g. `305O3`

## denue_201502_08.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 3 row(s), e.g. `3'000`

## denue_201502_09.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 4 row(s), e.g. `O6020`

## denue_201502_11.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `IT SU`

## denue_201502_12.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `4177O`

## denue_201502_13.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `0.00`

## denue_201502_14.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 5 row(s), e.g. `JUAN`

## denue_201502_15.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 15 row(s), e.g. `FALTA`

## denue_201502_20.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `SN`

## denue_201502_21.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `20 DE`

## denue_201502_25.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 2 row(s), e.g. `JOSÉ`

## denue_201502_28.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 5 row(s), e.g. `INDUS`

## denue_201502_29.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 3 row(s), e.g. `905O7`

## denue_201502_31.parquet (g07) — FAIL
- `Código Postal` / str_matches('^\s*\d{1,5}\s*$'): 2 row(s), e.g. `PARAI`

## denue_201601_02.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `2253O`

## denue_201601_07.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 4 row(s), e.g. `305O3`

## denue_201601_08.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `3'000`

## denue_201601_09.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 3 row(s), e.g. `O6020`

## denue_201601_11.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `IT SU`

## denue_201601_12.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `4177O`

## denue_201601_14.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `4425O`

## denue_201601_15.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 15 row(s), e.g. `FALTA`

## denue_201601_18.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 213 row(s), e.g. `     `

## denue_201601_21.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `20 DE`

## denue_201601_27.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `866O`

## denue_201601_28.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 5 row(s), e.g. `INDUS`

## denue_201601_29.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 3 row(s), e.g. `905O7`

## denue_201601_31.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 2 row(s), e.g. `PARAI`

## denue_201803_09.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 13 row(s), e.g. `0.00`

## denue_201803_15.parquet (g09) — FAIL
- `COD_POSTAL` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `0.00`

## denue_201811_09.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 13 row(s), e.g. `0.00`

## denue_201811_15.parquet (g08) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `0.00`

## denue_202505_09.parquet (g10) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `FORES`

## denue_202505_11.parquet (g10) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `E14A `

## denue_202505_20.parquet (g10) — FAIL
- `cod_postal` / str_matches('^\s*\d{1,5}\s*$'): 1 row(s), e.g. `SANTO`

