"""ENOE schema, grouping, person-key, and loader tests.

The synthetic-frame tests exercise the fingerprint / per-group-schema / person-key logic
against the bundled YAMLs only — no network, no mirrored parquet — so they run in CI. The
``@skipif(not _REAL)`` block additionally loads real quarters when a local mirror
(``data/parquet/``) is present (maintainer machine, after ``build_enoe.py``).

Everything is read **dynamically** from ``enoe_schema_map()``: the tables, the group ids,
and each group's columns depend on the build, so nothing here hardcodes a gid or a count.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

import mxcensus
from mxcensus._resources import enoe_schema_map, variables_enoe
from mxcensus.data._enoe_catalog import TABLES
from mxcensus.enoe import (
    _ENT_ALIASES,
    _WEIGHTS,
    _filter_ent,
    _fingerprint,
    _group_of,
    _group_schema,
    _person_key,
)

_SM = enoe_schema_map()

# (table, gid) pairs across the whole map — the unit of parametrization.
_TABLE_GROUPS = [(t, g) for t in TABLES for g in _SM[t]["groups"]]

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REAL = (_MIRROR / "enoe_sdem_2023t1.parquet").exists()


def _cols(table: str, gid: str) -> list[str]:
    return _SM[table]["groups"][gid]["columns"]


def _valid_value(table: str, gid: str, col: str) -> str:
    """A value that should pass ``_group_schema(table, gid)`` for ``col``."""
    if col in _WEIGHTS:
        return "1"  # numeric-coercible
    cats = (variables_enoe(table, gid).get(col) or {}).get("Categorías") or {}
    if cats:
        return next(iter(cats))
    return "x"


def _valid_frame(table: str, gid: str, rows: int = 3) -> pd.DataFrame:
    cols = _cols(table, gid)
    return pd.DataFrame({c: [_valid_value(table, gid, c)] * rows for c in cols}, dtype=str)


# --- schema map shape --------------------------------------------------------

def test_schema_map_has_all_tables():
    assert set(_SM) == set(TABLES)
    for t in TABLES:
        assert _SM[t]["groups"], f"{t} has no groups"
        assert _SM[t]["latest"] in _SM[t]["groups"]


# --- fingerprint round-trip --------------------------------------------------

@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_fingerprint_round_trips(table, gid):
    """A group's columns fingerprint back to that group via _group_of."""
    frame = pd.DataFrame({c: ["x"] for c in _cols(table, gid)}, dtype=str)
    assert _group_of(table, frame) == gid


def test_fingerprint_matches_map():
    """_fingerprint reproduces the fingerprint keys stored in the map."""
    for table in TABLES:
        for gid in _SM[table]["groups"]:
            fp = _fingerprint(_cols(table, gid))
            assert _SM[table]["fingerprints"][fp] == gid


def test_group_of_unknown_raises():
    frame = pd.DataFrame({"not_a_real_enoe_column": ["x"]}, dtype=str)
    with pytest.raises(ValueError):
        _group_of("sdem", frame)


# --- per-group schemas -------------------------------------------------------

@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_group_schema_builds(table, gid):
    schema = _group_schema(table, gid)
    assert set(schema.columns) == set(_cols(table, gid))


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_group_schema_accepts_valid_frame(table, gid):
    """A synthetic in-catalog frame validates clean against its group schema."""
    _group_schema(table, gid).validate(_valid_frame(table, gid))


def _first_categorical(table: str, gid: str) -> str | None:
    """A column in this group carrying an isin check (non-empty Categorías), or None."""
    for col in _cols(table, gid):
        if col in _WEIGHTS:
            continue
        if (variables_enoe(table, gid).get(col) or {}).get("Categorías"):
            return col
    return None


def test_group_schema_rejects_out_of_catalog_value():
    """Non-vacuous negative test: an out-of-catalog categorical value is rejected."""
    hit = None
    for table, gid in _TABLE_GROUPS:
        col = _first_categorical(table, gid)
        if col is not None:
            hit = (table, gid, col)
            break
    assert hit is not None, "no categorical column found in any group"
    table, gid, col = hit
    schema = _group_schema(table, gid)
    schema.validate(_valid_frame(table, gid))  # clean → passes
    bad = _valid_frame(table, gid)
    bad[col] = "__NOT_A_VALID_CODE__"
    with pytest.raises(pa.errors.SchemaError):
        schema.validate(bad)


def test_group_schema_weights_reject_non_numeric():
    """A weight column that can't coerce to float fails the numeric check."""
    hit = next(((t, g) for t, g in _TABLE_GROUPS
                if _WEIGHTS & set(_cols(t, g))), None)
    if hit is None:
        pytest.skip("no weight column in any group (unexpected)")
    table, gid = hit
    wcol = next(c for c in _cols(table, gid) if c in _WEIGHTS)
    bad = _valid_frame(table, gid)
    bad[wcol] = "NOTANUMBER"
    # A failed float coercion raises SchemaErrors (from the coerce step); an isin/type
    # violation raises SchemaError — accept either.
    with pytest.raises((pa.errors.SchemaError, pa.errors.SchemaErrors)):
        _group_schema(table, gid).validate(bad)


def test_group_schema_coerce_keeps_nulls():
    """coerce=True must not turn None into the string 'None' and break isin."""
    hit = None
    for table, gid in _TABLE_GROUPS:
        col = _first_categorical(table, gid)
        if col is not None:
            hit = (table, gid, col)
            break
    assert hit is not None
    table, gid, col = hit
    frame = _valid_frame(table, gid)
    frame[col] = [None] + [_valid_value(table, gid, col)] * (len(frame) - 1)
    _group_schema(table, gid).validate(frame)  # nulls pass isin


# --- person key alias / era resolution --------------------------------------

def test_person_key_uses_ent_alias():
    """Base seven with the pre-2026 ``ent`` name."""
    frame = pd.DataFrame(
        {c: ["1"] for c in ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")}
    )
    key = _person_key(frame, frame, frame)
    assert "ent" in key and "cve_ent" not in key
    assert key == ["cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren"]


def test_person_key_uses_cve_ent_alias():
    """2026-T1 renamed ``ent`` → ``cve_ent``; the entity component resolves to the new name."""
    frame = pd.DataFrame(
        {c: ["1"] for c in ("cd_a", "cve_ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")}
    )
    key = _person_key(frame, frame, frame)
    assert "cve_ent" in key and "ent" not in key


def test_person_key_widens_in_panel_era():
    """When ``tipo``/``mes_cal``/``ca`` are present they extend the key (panel/CATI era)."""
    cols = ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren", "tipo", "mes_cal", "ca")
    frame = pd.DataFrame({c: ["1"] for c in cols})
    key = _person_key(frame, frame, frame)
    assert key[-3:] == ["tipo", "mes_cal", "ca"]


def test_person_key_intersection_only():
    """A component absent from one joined table is dropped from the key."""
    a = pd.DataFrame({c: ["1"] for c in ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren", "tipo")})
    b = pd.DataFrame({c: ["1"] for c in ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")})  # no tipo
    assert "tipo" not in _person_key(a, b)


def test_filter_ent_padding_robust():
    """_filter_ent coerces numerically, so it matches un-padded and zero-padded codes."""
    df = pd.DataFrame({"ent": ["9", "09", "10", " "], "x": list("abcd")})
    out = _filter_ent(df, 9)
    assert list(out["x"]) == ["a", "b"]
    df2 = pd.DataFrame({"cve_ent": ["09", "9", "10"], "x": list("abc")})
    assert list(_filter_ent(df2, 9)["x"]) == ["a", "b"]


def test_ent_aliases_exported():
    assert _ENT_ALIASES == ("ent", "cve_ent")


# --- exports -----------------------------------------------------------------

def test_load_enoe_exported():
    assert callable(mxcensus.load_enoe)
    assert callable(mxcensus.load_enoe_persons)
    assert "load_enoe" in mxcensus.__all__
    assert "load_enoe_persons" in mxcensus.__all__


def test_enoe_resources_exported():
    assert callable(mxcensus.enoe_schema_map)
    assert callable(mxcensus.variables_enoe)
    assert callable(mxcensus.variables_enoe_core)


def test_harmonize_not_implemented():
    # harmonize=True short-circuits (raises) before any file access, so this needs no mirror.
    with pytest.raises(NotImplementedError):
        mxcensus.load_enoe(table="sdem", harmonize=True)


def test_load_enoe_unknown_table():
    with pytest.raises(ValueError):
        mxcensus.load_enoe(table="nope")


# --- End-to-end against the local build output (skipped when no data/parquet/) ---
#
# The parquet live in ``data/parquet/`` (the build output) but aren't necessarily on the HF
# mirror yet, and we don't want the suite to hit the network. This fixture redirects
# ``POOCH.fetch`` to the local file, so ``load_enoe(period=)`` / ``load_enoe_persons(period=)``
# resolve from the build output exactly as they would from the mirror once uploaded.

@pytest.fixture
def local_mirror(monkeypatch):
    from mxcensus.data import _registry

    def _fetch(fname, **_):
        p = _MIRROR / fname
        if not p.exists():
            raise FileNotFoundError(p)
        return str(p)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)
    return _MIRROR


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_load_enoe_real_validates_clean(local_mirror):
    """A real SDEM quarter loads and validates without warnings."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        df = mxcensus.load_enoe(table="sdem", period="2023t1")
    assert len(df) == 450_263
    assert not any("schema violation" in str(x.message) for x in w)


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_load_enoe_persons_real_sanity(local_mirror):
    """load_enoe_persons reproduces the STEP_6 published 2023-T1 sanity numbers."""
    p = mxcensus.load_enoe_persons(period="2023t1")
    assert len(p) == 344_205                                  # filtered SDEM count
    pob15 = p["fac_tri"].sum()
    assert abs(pob15 - 99_747_474) < 50_000                  # pob 15+ ≈ 99.7 M
    pea = p.loc[p["is_pea"], "fac_tri"].sum()
    assert abs(pea / pob15 - 0.602) < 0.005                  # participation ≈ 0.602
    ocup = p.loc[p["is_ocupado"], "fac_tri"].sum()
    unemployment = 1 - ocup / pea
    assert abs(unemployment - 0.0266) < 0.003                # unemployment ≈ 2.66 %
    informal = p.loc[p["is_informal"], "fac_tri"].sum() / ocup
    assert abs(informal - 0.55) < 0.02                       # informality ≈ 55 %


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_load_enoe_ent_filter_real(local_mirror):
    """ent= restricts to one state (national survey, post-load row filter)."""
    full = mxcensus.load_enoe(table="sdem", period="2023t1")
    jal = mxcensus.load_enoe(table="sdem", period="2023t1", ent=9)
    assert 0 < len(jal) < len(full)
    assert set(pd.to_numeric(jal[next(c for c in _ENT_ALIASES if c in jal.columns)])) == {9}
