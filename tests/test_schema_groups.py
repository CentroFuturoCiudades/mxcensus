"""Tests for the shared schema-group machinery (``mxcensus._schema_groups``) and for the
family modules' thin wrappers staying bound to it."""
from __future__ import annotations

import warnings

import pandas as pd
import pandera.pandas as pa
import pytest

from mxcensus import _schema_groups as sg
from mxcensus import denue, enigh, enoe


def test_fingerprint_is_order_sensitive_and_shared():
    a = sg.fingerprint(["x", "y"])
    assert a == sg.fingerprint(("x", "y")) and a != sg.fingerprint(["y", "x"])
    assert len(a) == 64
    for mod in (denue, enoe, enigh):
        assert mod._fingerprint(["x", "y"]) == a


def test_group_of_resolves_and_raises():
    section = {"fingerprints": {sg.fingerprint(["a", "b"]): "g02"}}
    assert sg.group_of("X", section, ["a", "b"], map_name="m.yaml") == "g02"
    with pytest.raises(ValueError, match="X file schema not found in m.yaml.*edition"):
        sg.group_of("X", section, ["b", "a"], map_name="m.yaml", unit="edition")
    with pytest.raises(ValueError):
        sg.group_of("X", None, ["a"], map_name="m.yaml")


def test_build_group_schema_rules():
    variables = {"cat": {"Categorías": {"1": "one", "2": "two"}}, "w": {}, "free": {}}
    rule = lambda c: pa.Column(str, pa.Check.str_matches(r"^\d{2}$"), nullable=True, coerce=True) if c == "code" else None
    schema = sg.build_group_schema(["cat", "w", "free", "code"], variables, weights={"w"}, column_rule=rule)
    ok = pd.DataFrame({"cat": ["1"], "w": ["3.5"], "free": ["anything"], "code": ["07"], "extra": ["ignored"]})
    schema.validate(ok, lazy=True)
    for col, bad in (("cat", "9"), ("w", "abc"), ("code", "7")):
        frame = ok.copy()
        frame[col] = [bad]
        with pytest.raises(pa.errors.SchemaErrors):
            schema.validate(frame, lazy=True)
    # a categorical map wins over the column rule; weights win over categories
    schema2 = sg.build_group_schema(["code"], {"code": {"Categorías": {"07": "x"}}}, column_rule=rule)
    with pytest.raises(pa.errors.SchemaErrors):
        schema2.validate(pd.DataFrame({"code": ["08"]}), lazy=True)


def test_validate_warn_warns_not_raises():
    schema = sg.build_group_schema(["c"], {"c": {"Categorías": {"1": "a"}}})
    with pytest.warns(UserWarning, match=r"FAM lbl: 2 schema violation\(s\) \[c/isin"):
        sg.validate_warn("FAM", schema, pd.DataFrame({"c": ["1", "x", "y"]}), "lbl")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sg.validate_warn("FAM", schema, pd.DataFrame({"c": ["1"]}), "lbl")


def test_level_key_and_index_level():
    spec = [("a",), ("ent", "cve_ent"), ("z",)]
    f1 = pd.DataFrame({"a": ["1", "1"], "cve_ent": ["01", "01"], "v": ["x", "y"]})
    f2 = pd.DataFrame({"a": ["1"], "ent": ["1"], "cve_ent": ["01"]})
    assert sg.level_key(spec, f1) == ["a", "cve_ent"]
    assert sg.level_key(spec, f1, f2) == ["a", "cve_ent"]      # first alias common to all
    assert sg.level_key(spec, f2) == ["a", "ent"]
    with pytest.warns(UserWarning, match="FAM level key .* not unique"):
        out = sg.index_level("FAM", f1, spec)
    assert list(out.index.names) == ["a", "cve_ent"]
    f1u = f1.assign(a=["1", "2"])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = sg.index_level("FAM", f1u, spec)
    assert out.index.is_unique


def test_family_wrappers_share_implementation():
    # Same key resolution and same warning family prefix through the wrappers.
    spec = [("folioviv",), ("foliohog",)]
    f = pd.DataFrame({"folioviv": ["1", "1"], "foliohog": ["1", "1"]})
    assert enigh._level_key(spec, f) == enoe._level_key(spec, f) == ["folioviv", "foliohog"]
    with pytest.warns(UserWarning, match="ENIGH level key"):
        enigh._index_level(f, spec)
    with pytest.warns(UserWarning, match="ENOE level key"):
        enoe._index_level(f, spec)
    schema = sg.build_group_schema(["c"], {"c": {"Categorías": {"1": "a"}}})
    bad = pd.DataFrame({"c": ["x"]})
    with pytest.warns(UserWarning, match="^DENUE lbl"):
        denue._validate(schema, bad, "lbl")
    with pytest.warns(UserWarning, match="^ENOE lbl"):
        enoe._validate(schema, bad, "lbl")
    with pytest.warns(UserWarning, match="^ENIGH lbl"):
        enigh._validate(schema, bad, "lbl")
