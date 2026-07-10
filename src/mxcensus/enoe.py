"""ENOE (Encuesta Nacional de Ocupación y Empleo) — schema/validation layer.

ENOE is INEGI's quarterly labor-force survey, mirrored per (table, quarter) as
``enoe_{table}_{period}.parquet`` (five tables ``viv``/``hog``/``sdem``/``coe1``/``coe2``;
see ``mxcensus.data._enoe_catalog`` and ``scripts/build_enoe.py``). Like DENUE it drifts
across eras, so every mirrored file is fingerprinted into a **per-table** schema group
(``_yaml/enoe_schema_map.yaml``) and validated against a tight per-group Pandera schema
built from that group's ``variables_enoe_{table}_{gid}.yaml``.

This module currently provides the schema layer (``_fingerprint`` / ``_group_schema``);
the public loaders (``load_enoe`` / ``load_enoe_persons``) and analytical-core
harmonization are added in a later work unit. The maintainer ``build_enoe.py --validate``
sweep validates every mirrored file against ``_group_schema`` and is the authoritative
per-file report (``docs/enoe/VALIDATION_REPORT.md``).
"""
from __future__ import annotations

import functools
import json
from hashlib import sha256

import pandera.pandas as pa

from mxcensus._resources import enoe_schema_map, variables_enoe

# Expansion weights — validated as numeric (coercible) rather than by category. ``fac`` is
# the pre-2020-T3 factor; ``fac_tri``/``fac_men`` the quarterly/monthly factors after.
_WEIGHTS = {"fac", "fac_tri", "fac_men"}


def _fingerprint(columns) -> str:
    """sha256 over the ordered column names — identifies a table's schema group.

    Same recipe as ``scripts/build_enoe.py`` uses when writing ``enoe_schema_map.yaml``, so a
    mirrored file's columns hash to the fingerprint recorded there.
    """
    return sha256(json.dumps(list(columns)).encode()).hexdigest()


@functools.cache
def _group_schema(table: str, gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for one ENOE ``(table, schema group)``'s raw frame.

    Built from the group's bundled ``variables_enoe_{table}_{gid}.yaml``:

    - expansion weights (``_WEIGHTS``) → numeric type check (coercible from the raw strings);
    - any column with a non-empty ``Categorías`` map → strict ``isin`` on its keys. For the
      analytical-core columns those keys are the complete, FD-sourced value-set (so a future
      file with an out-of-catalog value fails here); for other categoricals they are the
      data-enumerated values;
    - everything else → nullable string.

    ``strict=False`` so extra columns are ignored; ``coerce=True`` parses the ``dtype=str``
    frame to the declared types for the checks.
    """
    vars_ = variables_enoe(table, gid)
    cols = enoe_schema_map()[table]["groups"][gid]["columns"]
    schema = {}
    for col in cols:
        cats = (vars_.get(col) or {}).get("Categorías") or {}
        if col in _WEIGHTS:
            schema[col] = pa.Column(float, nullable=True, coerce=True)
        elif cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True, coerce=True)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)
