# CPV validation report

Each mirrored file validated against its (table, group) tight schema (`mxcensus.cpv._group_schema`: `isin` on every dictionary-coded column, numbers within `Rango` or a sentinel, digit codes for keys/geography and width-checked catalog codes). Files: 97. Failing: 0.

| table | group | files | rows | failing |
|---|---|---|---|---|
| viviendas | g01 | 32 | 7,340,046 | 0 |
| personas | g01 | 32 | 25,222,336 | 0 |
| migrantes | g01 | 32 | 362,679 | 0 |
| estimaciones | g01 | 1 | 13,880 | 0 |

All files pass their group schema.
