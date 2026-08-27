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
    _DWELLING_KEY_SPEC,
    _ENT_ALIASES,
    _HOUSEHOLD_KEY_SPEC,
    _PERSON_KEY_SPEC,
    _WEIGHTS,
    _CORE_ADD,
    _RENAME_CORE,
    _core_order,
    _filter_ent,
    _fingerprint,
    _group_of,
    _group_schema,
    _harmonize,
    _latest_schema,
    _level_key,
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
    """2025-T3 renamed ``ent`` → ``cve_ent``; the entity component resolves to the new name."""
    frame = pd.DataFrame(
        {c: ["1"] for c in ("cd_a", "cve_ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")}
    )
    key = _person_key(frame, frame, frame)
    assert "cve_ent" in key and "ent" not in key


def test_person_key_widens_in_panel_era():
    """When ``tipo``/``mes_cal``/``ca`` are present they extend the key (panel/CATI era).

    The panel identifiers sit in the dwelling portion of the key, so they precede
    ``n_hog``/``h_mud``/``n_ren`` — keeping the dwelling/household/person keys clean prefixes.
    """
    cols = ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren", "tipo", "mes_cal", "ca")
    frame = pd.DataFrame({c: ["1"] for c in cols})
    key = _person_key(frame, frame, frame)
    assert key == ["cd_a", "ent", "con", "v_sel", "tipo", "mes_cal", "ca",
                   "n_hog", "h_mud", "n_ren"]


def test_person_key_intersection_only():
    """A component absent from one joined table is dropped from the key."""
    a = pd.DataFrame({c: ["1"] for c in ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren", "tipo")})
    b = pd.DataFrame({c: ["1"] for c in ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")})  # no tipo
    assert "tipo" not in _person_key(a, b)


# --- level-key prefixes (dwelling ⊂ household ⊂ person) ----------------------

def test_level_key_specs_are_nested_prefixes():
    """The spec constants nest: dwelling ⊂ household ⊂ person."""
    assert _HOUSEHOLD_KEY_SPEC[:len(_DWELLING_KEY_SPEC)] == _DWELLING_KEY_SPEC
    assert _PERSON_KEY_SPEC[:len(_HOUSEHOLD_KEY_SPEC)] == _HOUSEHOLD_KEY_SPEC


def test_level_key_resolves_clean_prefixes_panel_era():
    """Resolved keys are clean prefixes in the panel era (tipo/mes_cal present, no ca)."""
    cols = ("cd_a", "ent", "con", "v_sel", "tipo", "mes_cal", "n_hog", "h_mud", "n_ren")
    f = pd.DataFrame({c: ["1"] for c in cols})
    dk, hk, pk = _level_key(_DWELLING_KEY_SPEC, f), _level_key(_HOUSEHOLD_KEY_SPEC, f), _level_key(_PERSON_KEY_SPEC, f)
    assert dk == ["cd_a", "ent", "con", "v_sel", "tipo", "mes_cal"]
    assert hk == dk + ["n_hog", "h_mud"]
    assert pk == hk + ["n_ren"]


def test_level_key_base_era_no_panel_cols():
    """Pre-2020-T3 (no tipo/mes_cal/ca): keys fall back to the base components."""
    cols = ("cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren")
    f = pd.DataFrame({c: ["1"] for c in cols})
    assert _level_key(_DWELLING_KEY_SPEC, f) == ["cd_a", "ent", "con", "v_sel"]
    assert _level_key(_HOUSEHOLD_KEY_SPEC, f) == ["cd_a", "ent", "con", "v_sel", "n_hog", "h_mud"]
    assert _level_key(_PERSON_KEY_SPEC, f) == ["cd_a", "ent", "con", "v_sel", "n_hog", "h_mud", "n_ren"]


def test_level_key_cve_ent_alias():
    """The entity component resolves across the ent→cve_ent rename at every level."""
    cols = ("cd_a", "cve_ent", "con", "v_sel", "tipo", "mes_cal", "n_hog", "h_mud", "n_ren")
    f = pd.DataFrame({c: ["1"] for c in cols})
    assert "cve_ent" in _level_key(_DWELLING_KEY_SPEC, f)
    assert "ent" not in _level_key(_PERSON_KEY_SPEC, f)


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
    for name in ("load_enoe", "load_enoe_persons", "load_enoe_viviendas",
                 "load_enoe_hogares", "load_enoe_survey"):
        assert callable(getattr(mxcensus, name)), name
        assert name in mxcensus.__all__, name


def test_enoe_resources_exported():
    assert callable(mxcensus.enoe_schema_map)
    assert callable(mxcensus.variables_enoe)
    assert callable(mxcensus.variables_enoe_core)


# --- harmonization (synthetic frames; no mirror needed) ---------------------------

def _old_era_frame() -> pd.DataFrame:
    """A pre-2020-T3-style SDEM slice: un-padded codes, ``fac``, no ``tipo``/``mes_cal``."""
    return pd.DataFrame({
        "cd_a": ["01"], "ent": ["9"], "con": ["1"], "v_sel": ["1"], "n_hog": ["1"],
        "h_mud": ["0"], "n_ren": ["1"], "mun": ["7"], "loc": [" "], "ageb": ["0"],
        "fac": ["770"], "est_d": ["1"], "t_loc": ["1"], "clase1": ["1"], "cs_p20_des": ["x"],
    }, dtype=str)


def test_harmonize_renames_core_and_pads_codes():
    h = _harmonize(_old_era_frame(), "sdem")
    for src, tgt in _RENAME_CORE.items():
        assert src not in h.columns and tgt in h.columns
    assert h["cve_ent"].iloc[0] == "09" and h["cve_mun"].iloc[0] == "007"
    assert h["cvegeo"].iloc[0] == "09007"
    assert h["fac_tri"].iloc[0] == "770"
    for col in _CORE_ADD:
        assert col in h.columns
    assert h["fac_men"].isna().all() and h["tipo"].isna().all() and h["mes_cal"].isna().all()
    # non-core, era-only columns survive verbatim (no DENUE-style projection)
    assert h["cs_p20_des"].iloc[0] == "x"
    # core columns lead, in dictionary order
    lead = [c for c in _core_order() if c in h.columns]
    assert list(h.columns[: len(lead)]) == lead


def test_harmonize_lowercases_2019_uppercase_files():
    up = _old_era_frame().rename(columns=str.upper)
    h = _harmonize(up, "coe1")
    assert all(c == c.lower() for c in h.columns)
    assert "cve_ent" in h.columns and "fac_tri" in h.columns


def test_harmonize_cvegeo_unspecified_municipality():
    f = _old_era_frame()
    f["mun"] = [" "]
    assert _harmonize(f, "sdem")["cvegeo"].iloc[0] == "09999"


def test_harmonize_is_idempotent_on_modern_frame():
    modern = _harmonize(_old_era_frame(), "sdem")
    again = _harmonize(modern, "sdem")
    pd.testing.assert_frame_equal(modern, again)


def test_harmonize_refuses_mixed_era_frame():
    f = _old_era_frame()
    f["cve_ent"] = ["09"]
    with pytest.raises(ValueError, match="both a legacy column and its target"):
        _harmonize(f, "sdem")


def test_harmonize_warns_when_core_source_missing():
    f = _old_era_frame().drop(columns=["fac"])
    with pytest.warns(UserWarning, match="_RENAME_CORE may be stale"):
        _harmonize(f, "sdem")


def test_core_order_has_no_duplicates():
    order = _core_order()
    assert len(order) == len(set(order))
    assert "fac" not in order and "ent" not in order


@pytest.mark.parametrize("table", TABLES)
def test_latest_schema_builds_and_accepts_harmonized(table):
    schema = _latest_schema(table)
    h = _harmonize(_old_era_frame(), table)
    schema.validate(h, lazy=True)


def test_latest_schema_rejects_out_of_catalog_core_value():
    f = _old_era_frame()
    f["clase1"] = ["7"]  # not an FD code (0/1/2)
    with pytest.raises(pa.errors.SchemaErrors):
        _latest_schema("sdem").validate(_harmonize(f, "sdem"), lazy=True)


def test_latest_schema_rejects_unpadded_ent():
    h = _harmonize(_old_era_frame(), "sdem")
    h["cve_ent"] = ["9"]
    with pytest.raises(pa.errors.SchemaErrors):
        _latest_schema("sdem").validate(h, lazy=True)


def test_load_enoe_unknown_table():
    with pytest.raises(ValueError):
        mxcensus.load_enoe(table="nope")


def test_load_enoe_survey_bad_persons():
    # An invalid persons= value raises before any file access, so this needs no mirror.
    with pytest.raises(ValueError):
        mxcensus.load_enoe_survey(period="2023t1", persons="bogus")


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


# --- dwelling / household analysis-ready loaders ----------------------------

# 2023t1 = panel era (tipo/mes_cal in the key, fac_tri weight); 2005t1 = base era (no
# tipo/mes_cal, fac→fac_tri coalescing) — both exercised so the era handling is covered.
@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
@pytest.mark.parametrize("period", ["2023t1", "2005t1"])
def test_load_enoe_viviendas_real(local_mirror, period):
    viv = mxcensus.load_enoe_viviendas(period=period)
    assert viv.index.is_unique
    assert list(viv.index.names) == _level_key(_DWELLING_KEY_SPEC, viv.reset_index())
    assert str(viv["fac_tri"].dtype).startswith(("int", "float"))  # coerced numeric
    assert viv["fac_tri"].sum() > 20_000_000                       # ≈ tens of millions of dwellings


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
@pytest.mark.parametrize("period", ["2023t1", "2005t1"])
def test_load_enoe_hogares_real(local_mirror, period):
    hog = mxcensus.load_enoe_hogares(period=period)
    viv = mxcensus.load_enoe_viviendas(period=period)
    assert hog.index.is_unique
    # household index extends the dwelling index by exactly n_hog, h_mud
    assert list(hog.index.names)[: len(viv.index.names)] == list(viv.index.names)
    assert list(hog.index.names)[len(viv.index.names):] == ["n_hog", "h_mud"]
    assert hog["fac_tri"].sum() > 20_000_000


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
@pytest.mark.parametrize("period", ["2023t1", "2005t1"])
def test_load_enoe_survey_prefix_nesting_real(local_mirror, period):
    """The three frames tuple-unpack and share a clean nested index (dwelling ⊂ hog ⊂ person)."""
    viv, hog, per = mxcensus.load_enoe_survey(period=period)  # persons="all"
    for lvl in (viv, hog, per):
        assert lvl.index.is_unique
    assert list(hog.index.names)[: len(viv.index.names)] == list(viv.index.names)
    assert list(per.index.names)[: len(hog.index.names)] == list(hog.index.names)
    assert list(per.index.names)[len(hog.index.names):] == ["n_ren"]


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_load_enoe_survey_persons_all_decomposes(local_mirror):
    """persons='all' = every household member (full SDEM); 'labor' = the 15+ analytical subset."""
    _, _, per_all = mxcensus.load_enoe_survey(period="2023t1", persons="all")
    _, _, per_lab = mxcensus.load_enoe_survey(period="2023t1", persons="labor")
    assert len(per_all) == 450_263                       # full SDEM
    assert len(per_lab) == 344_205                       # canonical working-age subset
    assert set(per_lab.index) <= set(per_all.index)      # labor is a subset of all
    assert "is_pea" in per_lab.columns and "is_pea" not in per_all.columns


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_load_enoe_survey_ent_filter_real(local_mirror):
    """ent= restricts all three frames to one state."""
    viv, hog, per = mxcensus.load_enoe_survey(period="2023t1", ent=9)
    viv_nat, _, _ = mxcensus.load_enoe_survey(period="2023t1")
    assert 0 < len(viv) < len(viv_nat)
    for lvl in (viv, hog, per):
        ent_vals = pd.to_numeric(lvl.index.get_level_values("ent"))
        assert set(ent_vals) == {9}


# --- harmonization against real quarters (one per era) -----------------------------

_ERA_PERIODS = ["2005t1", "2019t1", "2020t3", "2021t3", "2023t1", "2026t1"]


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
@pytest.mark.parametrize("period", _ERA_PERIODS)
@pytest.mark.parametrize("table", ["sdem", "coe1", "viv"])
def test_harmonized_real_validates_clean(local_mirror, table, period):
    if not (_MIRROR / f"enoe_{table}_{period}.parquet").exists():
        pytest.skip(f"{table} {period} not built locally")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        h = mxcensus.load_enoe(table=table, period=period, harmonize=True)
    assert not [x for x in w if "schema violation" in str(x.message) or "stale" in str(x.message)]
    assert {"cve_ent", "fac_tri", *_CORE_ADD} <= set(h.columns)
    assert h["cve_ent"].str.fullmatch(r"\d{2}").all()
    assert h["cvegeo"].dropna().str.fullmatch(r"\d{5}").all()
    raw = mxcensus.load_enoe(table=table, period=period)
    assert len(h) == len(raw)
    # nothing but the core renames/additions changed the column set
    assert set(raw.columns.str.lower()) - set(h.columns) <= set(_RENAME_CORE)


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_harmonized_cvegeo_matches_inegi(local_mirror):
    """Our derived cvegeo equals INEGI's own in an era that ships it."""
    raw = mxcensus.load_enoe(table="sdem", period="2026t1")
    derived = _harmonize(raw.drop(columns=["cvegeo"]), "sdem")["cvegeo"]
    assert derived.equals(raw["cvegeo"])


# Weighted totals must be identical with and without harmonization on both sides of each
# rename boundary (fac→fac_tri in 2020-T3, ca dropped in 2021-T3, ent→cve_ent in 2025-T3).
_BOUNDARIES = [("2020t1", "2020t3"), ("2021t2", "2021t3"), ("2025t2", "2025t3")]


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
@pytest.mark.parametrize("before,after", _BOUNDARIES)
def test_harmonized_persons_continuity(local_mirror, before, after):
    for per in (before, after):
        if not (_MIRROR / f"enoe_coe2_{per}.parquet").exists():
            pytest.skip(f"{per} not built locally")
    totals = {}
    for per in (before, after):
        raw = mxcensus.load_enoe_persons(period=per)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            harm = mxcensus.load_enoe_persons(period=per, harmonize=True)
        assert not [x for x in w if "not unique" in str(x.message)]   # no fan-out
        assert len(harm) == len(raw)
        assert harm["fac_tri"].sum() == raw["fac_tri"].sum()
        assert harm.loc[harm["is_pea"], "fac_tri"].sum() == raw.loc[raw["is_pea"], "fac_tri"].sum()
        assert "cve_ent" in harm.columns and "ent" not in harm.columns
        totals[per] = harm.loc[harm["is_pea"], "fac_tri"].sum()
    # adjacent quarters: PEA moves by well under 10 % (2020-T1→T3 is the COVID trough)
    assert abs(totals[after] / totals[before] - 1) < 0.10


@pytest.mark.skipif(not _REAL, reason="no local ENOE mirror (data/parquet/)")
def test_harmonized_survey_shared_index_names(local_mirror):
    viv, hog, per = mxcensus.load_enoe_survey(period="2005t1", harmonize=True)
    assert viv.index.names[1] == "cve_ent"
    assert list(viv.index.names) == list(hog.index.names[: viv.index.nlevels])
    assert list(hog.index.names) == list(per.index.names[: hog.index.nlevels])
