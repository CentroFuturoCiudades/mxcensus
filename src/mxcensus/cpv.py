"""CPV family (censos, conteos y encuestas intercensales 1990–2025) — schema layer.

The family is mirrored as ``cpv_{table}_{period}_{NN}.parquet`` (per-state microdata) and
``cpv_{table}_{period}.parquet`` (national aggregates), faithful raw: every column a
string, only empty cells null (see ``mxcensus.data._cpv_catalog``, ``scripts/build_cpv.py``
and ``docs/cpv/PLAN.md``). Like ENOE/ENIGH, every mirrored file is fingerprinted into a
**per-table** schema group (``_yaml/cpv_schema_map.yaml``) and validated against a tight
Pandera schema built from that group's ``variables_cpv_{table}_{gid}.yaml``.

So far this module holds only the private schema helpers the maintainer ``--validate``
sweep needs (unit 1b); the loaders (``load_cpv``, ``load_cpv_viviendas``/``personas``/
``migrantes``, ``load_cpv_survey``) arrive in unit 1c.
"""
from __future__ import annotations

import functools

import pandas as pd
import pandera.pandas as pa

from mxcensus import _schema_groups as _sg
from mxcensus._resources import cpv_schema_map, variables_cpv

# Expansion weight — validated as numeric.
_WEIGHTS = {"FACTOR"}

# Keys and geographic codes: digit strings (their width is edition-specific, so only the
# all-digits shape is checked here; key widths are checked by the data tests).
_DIGIT_CODES = frozenset({"ID_VIV", "ID_PERSONA", "ID_MII", "CVEGEO", "CVE_ENT", "CVE_MUN",
                          "LOC50K", "CVE_LOC"})


def _fingerprint(columns) -> str:
    """Schema-group fingerprint (shared recipe, see :mod:`mxcensus._schema_groups`)."""
    return _sg.fingerprint(columns)


def _code_rule(col: str, meta: dict) -> pa.Column | None:
    """Raw-string rule for a coded string column: a key/geographic code → digits; a code
    from a classification catalog too large to enumerate (``Catálogo`` + string ``Tipo``:
    occupation, activity, country, municipality, language) → exactly ``Longitud`` digits.
    ``None`` for any other column."""
    if col in _DIGIT_CODES:
        return _sg.raw_column(pa.Check.str_matches(r"^\d+$"))
    width = str(meta.get("Longitud") or "").strip()
    if meta.get("Catálogo") and _sg.norm_tipo(meta) == "string" and width.isdigit():
        return _sg.raw_column(pa.Check.str_matches(rf"^\d{{{width}}}$"))
    return None


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one CPV ``(table, schema group)``'s raw frame (weights →
    numeric, ``Categorías`` → strict ``isin``, numerics → number in ``Rango`` or sentinel,
    coded strings → :func:`_code_rule`, else nullable string)."""
    cols = cpv_schema_map()[table]["groups"][gid]["columns"]
    variables = variables_cpv(table, gid)
    return _sg.build_group_schema(cols, variables, weights=_WEIGHTS,
                                  column_rule=lambda c: _code_rule(c, variables.get(c) or {}))


def _group_of(table: str, df: pd.DataFrame) -> str:
    """Resolve a loaded frame to its per-table schema group id (raises if unknown)."""
    return _sg.group_of("CPV", cpv_schema_map().get(table), df.columns,
                        map_name="cpv_schema_map.yaml", unit="edition")


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise."""
    _sg.validate_warn("CPV", schema, frame, label)
