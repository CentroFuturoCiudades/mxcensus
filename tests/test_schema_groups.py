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


# --- labelled frames (label_frame / build_labelled_schema / validate_raise) -------------

_VARS = {
    "lvl": {"Tipo": "categorical", "Ordenada": True,
            "Categorías": {"1": "Bajo", "2": "Medio", "3": "Alto"},
            "Especiales": {"9": "No especificado"}},
    "pad": {"Categorías": {"01": "Uno", "02": "Dos"}, "Alias": {"1": "01", "2": "02"}},
    "rng": {"Categorías": {"01..03": "Sí", "04": "No"}},
    "age": {"Tipo": "Numérico", "Rango": [0, 98], "Especiales": {"99": "No especificada"}},
    "amt": {"Tipo": "float", "Decimales": "2", "Rango": ["0", "1e9"]},
    "w": {"Tipo": "numeric"},
    "txt": {"Tipo": "Carácter"},
}


def _raw():
    return pd.DataFrame({
        "lvl": ["1", "3", "9", None], "pad": ["1", "02", " 2 ", ""], "rng": ["02", "04", "01", "03"],
        "age": ["15", "99", "0", "98"], "amt": ["10.5", "0", "3", "1e3"], "w": ["1", "2.5", "3", "4"],
        "txt": ["a", "b", "c", ""], "other": ["x", "y", "z", "w"],
    })


def test_norm_tipo_vocabulary():
    assert sg.norm_tipo({"Categorías": {"1": "a"}, "Tipo": "Numérico"}) == "categorical"
    for t in ("Numérico", "int", "float", "numeric", "N"):
        assert sg.norm_tipo({"Tipo": t}) == "numeric"
    for t in ("Carácter", "str", "string", "", None):
        assert sg.norm_tipo({"Tipo": t}) == "string"


def test_expand_cat_map_str_ranges():
    from mxcensus.utils import expand_cat_map_str
    assert expand_cat_map_str({"01..03": "Sí", "4": 5}) == {"01": "Sí", "02": "Sí", "03": "Sí", "4": "5"}
    assert expand_cat_map_str({"1..2": "x"}) == {"1": "x", "2": "x"}


def test_label_frame_maps_codes_numerics_and_sentinels():
    out = sg.label_frame(_raw(), _VARS, weights={"w"}, family="FAM", skip={"txt"})
    assert list(out["lvl"]) == ["Bajo", "Alto", "No especificado", None]
    assert list(out["pad"]) == ["Uno", "Dos", "Dos", None]          # Alias + strip + blank→NA
    assert list(out["rng"]) == ["Sí", "No", "Sí", "Sí"]
    assert list(out["age"].astype("Float64")) == [15, None, 0, 98] or pd.isna(out["age"][1])
    assert out["age"].dtype.kind in "fi" and pd.isna(out["age"].iloc[1])
    assert out["amt"].iloc[3] == 1000.0 and out["w"].dtype.kind == "f"
    assert list(out["txt"]) == ["a", "b", "c", ""]                  # skipped verbatim
    assert list(out["other"]) == ["x", "y", "z", "w"]               # not in dictionary


def test_label_frame_raises_on_unknown_code_and_non_numeric():
    bad = _raw()
    bad.loc[0, "lvl"] = "7"
    bad.loc[0, "age"] = "abc"
    with pytest.raises(ValueError, match=r"FAM: values without a dictionary label.*'lvl': \['7'\].*'age': \['abc'\]"):
        sg.label_frame(bad, _VARS, family="FAM")


def test_build_labelled_schema_dtypes_and_checks():
    frame = sg.label_frame(_raw(), _VARS, weights={"w"}, family="FAM")
    schema = sg.build_labelled_schema(frame.columns, _VARS, weights={"w"})
    out = sg.validate_raise("FAM", schema, frame, "lbl")
    assert isinstance(out["lvl"].dtype, pd.CategoricalDtype) and out["lvl"].dtype.ordered
    assert list(out["lvl"].cat.categories) == ["Bajo", "Medio", "Alto", "No especificado"]
    assert not out["pad"].dtype.ordered and list(out["pad"].cat.categories) == ["Uno", "Dos"]
    assert list(out["rng"].cat.categories) == ["Sí", "No"]          # duplicate labels folded, in order
    assert str(out["age"].dtype) == "Int64" and str(out["amt"].dtype) == "Float64"
    assert out["w"].dtype.kind == "f"
    # Rango violation and negative weight raise with the family prefix
    bad = frame.copy(); bad.loc[0, "age"] = 150
    with pytest.raises(ValueError, match=r"^FAM lbl: 1 schema violation\(s\) \[age/"):
        sg.validate_raise("FAM", schema, bad, "lbl")
    bad = frame.copy(); bad.loc[0, "w"] = -1
    with pytest.raises(ValueError, match=r"w/"):
        sg.validate_raise("FAM", schema, bad, "lbl")


def test_build_labelled_schema_unique_index():
    frame = sg.label_frame(_raw(), _VARS, family="FAM").assign(k1=["1", "1", "2", "2"], k2=["a", "b", "a", "b"])
    cols = [c for c in frame.columns if c not in ("k1", "k2")]
    schema = sg.build_labelled_schema(cols, _VARS, index_names=["k1", "k2"])
    sg.validate_raise("FAM", schema, frame.set_index(["k1", "k2"]), "lbl")
    dup = frame.assign(k2=["a", "a", "a", "b"]).set_index(["k1", "k2"])
    with pytest.raises(ValueError):
        sg.validate_raise("FAM", schema, dup, "lbl")
    single = sg.build_labelled_schema(cols + ["k2"], _VARS, index_names=["k1"])
    with pytest.raises(ValueError):
        sg.validate_raise("FAM", single, frame.set_index("k1"), "lbl")


def test_build_group_schema_accepts_alias_and_especiales():
    schema = sg.build_group_schema(["c"], {"c": {"Categorías": {"01": "a"}, "Alias": {"1": "01"},
                                                 "Especiales": {"9": "ne"}}})
    schema.validate(pd.DataFrame({"c": ["01", "1", "9"]}), lazy=True)
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(pd.DataFrame({"c": ["2"]}), lazy=True)


def test_build_group_schema_numeric_raw_check():
    variables = {"age": {"Tipo": "numeric", "Rango": [0, 97], "Especiales": {"99": "ne"}},
                 "amt": {"Tipo": "Numérico"}}
    schema = sg.build_group_schema(["age", "amt"], variables)
    schema.validate(pd.DataFrame({"age": ["15", "99", "", None, " 97"], "amt": ["1.5", "0", "", None, "7"]}), lazy=True)
    for col, bad in (("age", "150"), ("age", "abc"), ("amt", "x")):
        frame = pd.DataFrame({"age": ["1"], "amt": ["1"]}); frame[col] = [bad]
        with pytest.raises(pa.errors.SchemaErrors):
            schema.validate(frame, lazy=True)


def test_group_schema_isin_accepts_blank_cells():
    schema = sg.build_group_schema(["c"], {"c": {"Categorías": {"1": "a"}}})
    schema.validate(pd.DataFrame({"c": ["1", " ", "", None]}), lazy=True)
    with pytest.raises(pa.errors.SchemaErrors, match="isin"):
        schema.validate(pd.DataFrame({"c": ["2"]}), lazy=True)
