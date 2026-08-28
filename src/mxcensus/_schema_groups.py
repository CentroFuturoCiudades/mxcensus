"""Shared "schema group" machinery for the multi-temporal families (DENUE, ENOE, ENIGH).

Each of these mirrors drifts across releases/editions, so every mirrored file is
**fingerprinted** by its ordered column names into a *schema group* recorded in a bundled
``*_schema_map.yaml`` (written by the maintainer build scripts with the same recipe), and a
loaded frame is validated against a tight Pandera schema built from that group's variable
dictionary. The pieces below are family-agnostic; each family module binds them to its own
resource accessors and weight/column rules (``denue.py``, ``enoe.py``, ``enigh.py``) and
keeps its private ``_fingerprint``/``_group_of``/``_group_schema``/``_validate`` names as thin
wrappers so nothing user-visible changes.

Also hosts the alias-based hierarchical **key** helpers the household surveys share
(:func:`level_key`, :func:`index_level`).
"""
from __future__ import annotations

import json
import warnings
from collections.abc import Callable, Iterable
from hashlib import sha256

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

KeySpec = list[tuple[str, ...]]


def fingerprint(columns: Iterable[str]) -> str:
    """sha256 over the ordered column names — the group identity of a file's schema.

    The build scripts write this exact value into the schema map, so a mirrored file's
    columns resolve to the group recorded there (see :func:`group_of`).
    """
    return sha256(json.dumps(list(columns)).encode()).hexdigest()


def group_of(family: str, section: dict, columns: Iterable[str], *, map_name: str,
             unit: str = "release") -> str:
    """Resolve a frame's columns to its schema group id via ``section["fingerprints"]``.

    ``section`` is the (per-table, for ENOE/ENIGH; whole map, for DENUE) dict holding
    ``fingerprints`` → gid. Raises ``ValueError`` on an unknown schema — a structural
    problem (stale mirror or map, or a ``unit`` absent from the build) that must fail
    loudly, unlike the value-level violations :func:`validate_warn` only warns about.
    """
    gid = (section or {}).get("fingerprints", {}).get(fingerprint(columns))
    if gid is None:
        raise ValueError(
            f"{family} file schema not found in {map_name} (stale mirror or map, or a "
            f"{unit} not covered by the current build?)."
        )
    return gid


def build_group_schema(
    columns: Iterable[str],
    variables: dict,
    *,
    weights: Iterable[str] = (),
    column_rule: Callable[[str], pa.Column | None] | None = None,
) -> pa.DataFrameSchema:
    """Tight Pandera schema for one schema group's **raw** frame.

    Per column, in order: an expansion weight (``weights``) → numeric (coercible from the raw
    strings); a non-empty ``Categorías`` map in ``variables`` → strict ``isin`` on its keys
    (complete, dictionary-sourced value-sets for the analytical core; data-enumerated values
    otherwise); a family-specific ``column_rule(col)`` returning a ``pa.Column`` (e.g. DENUE's
    coded-field regexes) → that; else a nullable string. ``strict=False`` ignores extra
    columns (geometry, …); ``coerce=True`` parses the ``dtype=str`` frame for the checks.
    """
    weights = set(weights)
    schema: dict[str, pa.Column] = {}
    for col in columns:
        cats = (variables.get(col) or {}).get("Categorías") or {}
        rule = column_rule(col) if column_rule is not None else None
        if col in weights:
            schema[col] = pa.Column(float, nullable=True, coerce=True)
        elif cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True, coerce=True)
        elif rule is not None:
            schema[col] = rule
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


def validate_warn(family: str, schema: pa.DataFrameSchema, frame: pd.DataFrame,
                  label: str, *, stacklevel: int = 4) -> None:
    """Validate lazily and **warn** (never raise) on value-level violations.

    A stray malformed cell should surface a problem, not make a whole file unloadable —
    structural problems already raise in :func:`group_of`. The warning summarises the six
    most frequent ``(column, check)`` pairs; the maintainer ``--validate`` sweeps are the
    authoritative per-file hard pass/fail reports.
    """
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        fc = exc.failure_cases
        top = fc.groupby(["column", "check"]).size().sort_values(ascending=False).head(6)
        detail = "; ".join(f"{col}/{chk}×{n}" for (col, chk), n in top.items())
        warnings.warn(f"{family} {label}: {len(fc)} schema violation(s) [{detail}]",
                      stacklevel=stacklevel)


def level_key(spec: KeySpec, *frames: pd.DataFrame) -> list[str]:
    """Resolve a hierarchical key ``spec`` to the columns present in **every** frame.

    ``spec`` is an ordered list of alias tuples; each component resolves to its first alias
    present in all frames (so an era rename such as ENOE's ``ent``→``cve_ent`` is handled),
    and components absent everywhere are dropped (era-specific panel identifiers). When the
    specs of a family nest (dwelling ⊂ household ⊂ person), the resolved keys are clean
    prefixes of one another.
    """
    common = set.intersection(*(set(f.columns) for f in frames))
    key: list[str] = []
    for aliases in spec:
        col = next((c for c in aliases if c in common), None)
        if col is not None:
            key.append(col)
    return key


def index_level(family: str, df: pd.DataFrame, spec: KeySpec) -> pd.DataFrame:
    """Set the era-appropriate hierarchical key as a sorted ``MultiIndex``.

    Warns if the key is not unique in this frame (it should be — the level keys are verified
    unique at build time), so a future era that renames/drops a key column surfaces instead
    of silently producing a non-unique index.
    """
    key = level_key(spec, df)
    if df.duplicated(subset=key).any():
        warnings.warn(
            f"{family} level key {key} is not unique in this frame; the index will be "
            f"non-unique (a key column may be renamed/missing in this era).", stacklevel=4,
        )
    return df.set_index(key).sort_index()
