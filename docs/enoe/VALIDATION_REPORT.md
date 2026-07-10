# ENOE validation report

Each mirrored file validated against its (table, group) tight schema (`mxcensus.enoe._group_schema`). Files: 420. Failing: 0.

> Value-level anomalies that are not schema violations (e.g. the mangled Ó/Ñ in SDEM open-text fields, see `STEP_2.md`) are faithful to INEGI's source and do not appear here — free-text columns carry no `isin`/regex check.

All files pass their group schema.
