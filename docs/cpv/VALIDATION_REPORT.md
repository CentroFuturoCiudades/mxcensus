# CPV validation report

Each mirrored file validated against its (table, group) tight schema (`mxcensus.cpv._group_schema`: `isin` on every dictionary-coded column, numbers within `Rango` or a sentinel, digit codes for keys/geography and width-checked catalog codes). Files: 417. Failing: 0.

| table | group | files | rows | failing |
|---|---|---|---|---|
| viviendas | g01 | 31 | 2,682,985 | 0 |
| viviendas | g02 | 1 | 220,655 | 0 |
| viviendas | g03 | 32 | 5,854,392 | 0 |
| viviendas | g04 | 32 | 4,016,627 | 0 |
| viviendas | g05 | 32 | 7,340,046 | 0 |
| personas | g01 | 31 | 11,011,345 | 0 |
| personas | g02 | 1 | 927,057 | 0 |
| personas | g03 | 32 | 22,692,265 | 0 |
| personas | g04 | 32 | 15,015,683 | 0 |
| personas | g05 | 32 | 25,222,336 | 0 |
| migrantes | g01 | 31 | 150,166 | 0 |
| migrantes | g02 | 1 | 6,274 | 0 |
| migrantes | g03 | 32 | 120,099 | 0 |
| migrantes | g04 | 32 | 362,679 | 0 |
| iter | g01 | 32 | 195,659 | 0 |
| ageb | g01 | 32 | 1,683,504 | 0 |
| estimaciones | g01 | 1 | 13,880 | 0 |

All files pass their group schema.
