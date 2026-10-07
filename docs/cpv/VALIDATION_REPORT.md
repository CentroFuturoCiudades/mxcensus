# CPV validation report

Each mirrored file validated against its (table, group) tight schema (`mxcensus.cpv._group_schema`: `isin` on every dictionary-coded column, numbers within `Rango` or a sentinel, digit codes for keys/geography and width-checked catalog codes). Files: 10. Failing: 0.

| table | group | files | rows | failing |
|---|---|---|---|---|
| viviendas | g01 | 3 | 847,286 | 0 |
| personas | g01 | 3 | 2,915,884 | 0 |
| migrantes | g01 | 3 | 22,519 | 0 |
| estimaciones | g01 | 1 | 13,880 | 0 |

All files pass their group schema.
