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

from mxcensus.utils import expand_cat_map_str

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
        meta = variables.get(col) or {}
        cats = meta.get("Categorías") or {}
        rule = column_rule(col) if column_rule is not None else None
        if col in weights:
            schema[col] = pa.Column(float, nullable=True, coerce=True)
        elif cats:
            # Raw frames may spell a code either way (``Alias``: raw spelling → canonical,
            # e.g. ENIGH 2012's un-padded ``educa_jefe``); ``Especiales`` are valid codes too.
            schema[col] = raw_column(pa.Check.isin(raw_codes(meta)))
        elif norm_tipo(meta) == "numeric" and col not in weights:
            schema[col] = raw_column(_numeric_raw_check(meta))
        elif rule is not None:
            schema[col] = rule
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


# INEGI writes a single space for a not-applicable cell (an absent resident's ``sex``):
# missing information, not an out-of-catalog code — blanked to NA before the checks run.
_BLANK_TO_NA = pa.Parser(lambda s: s.mask(s.astype("string").str.strip() == ""))


def isin_or_blank(codes: Iterable[str]) -> pa.Check:
    """Plain ``isin(codes)``; pair it with :data:`_BLANK_TO_NA` (see :func:`raw_column`)."""
    return pa.Check.isin(list(codes))


def raw_column(check: pa.Check, **kw) -> pa.Column:
    """A nullable raw-string column whose blank cells are NA before ``check`` runs."""
    return pa.Column(str, check, nullable=True, coerce=True, parsers=_BLANK_TO_NA, **kw)


def raw_codes(meta: dict) -> list[str]:
    """Every code a raw frame may carry for a categorical entry: ``Categorías`` ∪
    ``Especiales`` ∪ ``Alias`` keys (range keys expanded)."""
    return (list(expand_cat_map_str(meta.get("Categorías") or {}))
            + list(expand_cat_map_str(meta.get("Especiales") or {}))
            + list(meta.get("Alias") or {}))


def _numeric_raw_check(meta: dict) -> pa.Check:
    """Raw-string check for a ``Tipo: numeric`` variable: every value is a sentinel
    (``Especiales``) or parses as a number within ``Rango`` (when given)."""
    special = set(meta.get("Especiales") or {})
    rng = meta.get("Rango") or []
    lo, hi = (float(rng[0]), float(rng[1])) if len(rng) == 2 else (None, None)

    def _ok(s: pd.Series) -> pd.Series:
        s = s.astype("string").str.strip()
        num = pd.to_numeric(s.where(~s.isin(special)), errors="coerce")
        good = s.isna() | (s == "") | s.isin(special) | num.notna()
        if lo is not None:
            good &= num.isna() | num.between(lo, hi)
        return good

    return pa.Check(_ok, name="numeric_in_range", error=f"numeric{'' if lo is None else f' in [{lo:g}, {hi:g}]'} or sentinel")


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
        warnings.warn(f"{family} {label}: {_summarise(exc)}", stacklevel=stacklevel)


def _summarise(exc: SchemaErrors) -> str:
    """``"N schema violation(s) [col/check×n; …]"`` — the six most frequent (column, check)."""
    fc = exc.failure_cases
    top = fc.groupby(["column", "check"], dropna=False).size().sort_values(ascending=False).head(6)
    detail = "; ".join(f"{col}/{chk}×{n}" for (col, chk), n in top.items())
    return f"{len(fc)} schema violation(s) [{detail}]"


def validate_raise(family: str, schema: pa.DataFrameSchema, frame: pd.DataFrame,
                   label: str) -> pd.DataFrame:
    """Validate lazily and **raise** ``ValueError`` on any violation (labelled frames).

    The analysis-ready loaders return labelled, typed frames whose contract is strict — an
    out-of-dictionary value there is a defect to fix (in the dictionary or the mirror), not
    a wart to warn about — so this mirrors the extended-census loaders. Returns the
    validated (coerced) frame: ``coerce=True`` is what materialises the ``CategoricalDtype``
    / numeric dtypes declared by :func:`build_labelled_schema`.
    """
    try:
        return schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        raise ValueError(f"{family} {label}: {_summarise(exc)}") from exc


# ---------------------------------------------------------------------------------------
# Labelled (human-readable) frames — the dictionary-driven analogue of the extended-census
# preprocessors: codes → labels, sentinels → NA, numerics → numbers, then a strict schema.
# ---------------------------------------------------------------------------------------
# A variable entry may carry, besides ``Descripción``/``Categorías``:
#   Tipo        categorical | numeric | string   (legacy spellings accepted, see norm_tipo)
#   Ordenada    true → ordered CategoricalDtype in YAML insertion order
#   Rango       [min, max] inclusive bounds checked on the numeric column
#   Especiales  {code: label} sentinel codes — for a categorical they are extra categories
#               (``No especificado`` is information); for a numeric they become NA
#   Alias       {raw spelling: canonical code} applied before the label map
#   Decimales   non-empty → Float64, else Int64 (numeric columns)

_TIPO_ALIASES = {
    "numeric": "numeric", "numérico": "numeric", "numerico": "numeric", "int": "numeric",
    "float": "numeric", "n": "numeric",
    "categorical": "categorical", "categórica": "categorical",
    "string": "string", "str": "string", "carácter": "string", "caracter": "string", "c": "string",
}


def norm_tipo(meta: dict) -> str:
    """Normalise a variable's ``Tipo`` to ``categorical`` / ``numeric`` / ``string``.

    A non-empty ``Categorías`` map wins (a coded field is categorical whatever the storage
    type says); otherwise the legacy spellings (``Numérico``/``Carácter``, ``int``/``float``/
    ``str``) map onto the normalised vocabulary; unknown/blank → ``string``.
    """
    if meta.get("Categorías"):
        return "categorical"
    return _TIPO_ALIASES.get(str(meta.get("Tipo") or "").strip().lower(), "string")


def _labels_of(meta: dict) -> dict[str, str]:
    """code → label map for a categorical entry: ``Categorías`` then ``Especiales``."""
    m = expand_cat_map_str(meta.get("Categorías") or {})
    m.update(expand_cat_map_str(meta.get("Especiales") or {}))
    return m


def _numeric_dtype(meta: dict) -> str:
    return "Float64" if str(meta.get("Decimales") or "").strip() else "Int64"


def label_frame(df: pd.DataFrame, variables: dict, *, weights: Iterable[str] = (),
                family: str, skip: Iterable[str] = ()) -> pd.DataFrame:
    """Map a raw ``dtype=str`` frame onto labels/numbers per ``variables`` (a copy).

    Per column present in ``variables``: weights → numeric; categorical → ``Alias`` then the
    code→label map (``Categorías`` ∪ ``Especiales``); numeric → ``Especiales`` codes to NA,
    then ``to_numeric``; string → untouched. Columns in ``skip`` (index keys) and columns
    absent from the dictionary are left verbatim. Blank strings become NA.

    Raises ``ValueError`` listing every code without a label / non-numeric value — an
    unmapped code would otherwise silently become NA, so it fails loudly here (the maintainer
    ``--validate`` gate guarantees the mirror never trips this).
    """
    weights, skip = set(weights), set(skip)
    out = df.copy()
    problems: dict[str, list] = {}
    for col in out.columns:
        if col in skip:
            continue
        meta = variables.get(col)
        if meta is None:
            continue
        raw = out[col]
        if col in weights:
            out[col] = pd.to_numeric(raw, errors="coerce")
            continue
        if not (raw.dtype == object or pd.api.types.is_string_dtype(raw)):
            continue  # already typed (a derived numeric/flag column) — nothing to map
        s = raw.astype("string").str.strip()
        s = s.mask(s == "")
        tipo = norm_tipo(meta)
        if tipo == "categorical":
            alias = meta.get("Alias") or {}
            if alias:
                s = s.replace(alias)
            mapped = s.map(_labels_of(meta))
            missing = s[mapped.isna() & s.notna()]
            if len(missing):
                problems[col] = sorted(missing.unique())[:12]
            out[col] = mapped.astype(object).where(mapped.notna(), None)
        elif tipo == "numeric":
            out[col] = _to_numeric(s, meta, col, problems)
    if problems:
        raise ValueError(
            f"{family}: values without a dictionary label (add them to the variables YAML, "
            f"or load with labels=False): {problems}"
        )
    return out


def _to_numeric(s: pd.Series, meta: dict, col: str, problems: dict) -> pd.Series:
    """Parse a raw string column: sentinels → NA, then ``Int64`` when every value is
    integral (and no ``Decimales`` declared), else ``Float64`` — never truncating."""
    special = meta.get("Especiales") or {}
    if special:
        s = s.mask(s.isin(list(special)))
    num = pd.to_numeric(s, errors="coerce")
    bad = s[num.isna() & s.notna()]
    if len(bad):
        problems[col] = sorted(bad.unique())[:12]
    num = num.astype("Float64")
    if _numeric_dtype(meta) == "Int64" and (num.dropna() % 1 == 0).all():
        return num.astype("Int64")
    return num


def build_labelled_schema(columns: Iterable[str], variables: dict, *,
                          weights: Iterable[str] = (), skip: Iterable[str] = (),
                          index_names: Iterable[str] | None = None) -> pa.DataFrameSchema:
    """Strict Pandera schema for a frame produced by :func:`label_frame`.

    Weights → non-negative float; categorical → ``CategoricalDtype`` of the label values
    (``Ordenada`` → ordered, YAML order; duplicates folded deterministically); numeric →
    ``Int64``/``Float64`` with ``Rango`` bounds; string → nullable str. Columns absent from
    ``variables`` are left out (``strict=False`` passes them through untouched: derived
    flags, era-only items); the ``skip`` columns :func:`label_frame` left verbatim (the keys)
    are nullable strings. ``index_names`` (the hierarchical key) → a unique
    ``MultiIndex``/``Index`` of strings. ``strict=False`` so derived columns (flags, a
    coalesced weight) pass; ``coerce=True`` materialises the dtypes on validation.
    """
    weights, skip = set(weights), set(skip)
    schema: dict[str, pa.Column] = {}
    for col in columns:
        if col not in variables and col not in weights:
            continue  # derived/undocumented column (a flag, an era-only item): untouched
        meta = {} if col in skip else (variables.get(col) or {})
        tipo = norm_tipo(meta)
        if col in weights:
            schema[col] = pa.Column(float, pa.Check.ge(0), nullable=True, coerce=True)
        elif tipo == "categorical":
            labels = list(dict.fromkeys(_labels_of(meta).values()))
            dtype = pd.CategoricalDtype(labels, ordered=bool(meta.get("Ordenada")))
            schema[col] = pa.Column(dtype, nullable=True, coerce=True)
        elif tipo == "numeric":
            rng = meta.get("Rango") or []
            checks = [pa.Check(lambda s: pd.api.types.is_numeric_dtype(s), name="numeric_dtype",
                               element_wise=False)]
            if len(rng) == 2:
                checks.append(pa.Check.between(float(rng[0]), float(rng[1])))
            # dtype left to label_frame (Int64 when integral, else Float64) — declaring one
            # here would let coercion truncate decimals silently.
            schema[col] = pa.Column(checks=checks, nullable=True)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    index = None
    if index_names:
        names = list(index_names)
        # Levels are nullable: harmonization adds the panel identifiers ``tipo``/``mes_cal``
        # as NA to pre-2020-T3 ENOE quarters, and they are part of the key.
        if len(names) == 1:
            index = pa.Index(str, name=names[0], unique=True, nullable=True, coerce=True)
        else:
            index = pa.MultiIndex([pa.Index(str, name=n, nullable=True, coerce=True) for n in names],
                                  unique=names, coerce=True)
    return pa.DataFrameSchema(schema, index=index, strict=False, coerce=True)


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
