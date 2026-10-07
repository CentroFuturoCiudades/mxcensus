"""CLI argument handling (``mxcensus fetch``) — offline: ``POOCH.fetch`` is stubbed."""
from __future__ import annotations

import pytest

from mxcensus import _cli
from mxcensus.data._enigh_catalog import latest_edition


@pytest.fixture
def fetched(monkeypatch):
    from mxcensus.data import _registry

    names: list[str] = []
    monkeypatch.setattr(_registry.POOCH, "fetch",
                        lambda fname, **_: names.append(fname) or f"/cache/{fname}")
    return names


def test_census_default_dataset(fetched):
    _cli.main(["fetch", "9"])
    assert fetched == ["iter_09.parquet", "resargebub_09.parquet",
                       "personas_09.parquet", "viviendas_09.parquet"]


def test_national_survey_needs_no_state(fetched):
    _cli.main(["fetch", "--dataset", "enigh", "--edition", "2022"])
    assert fetched and all(f.endswith("_2022.parquet") for f in fetched)
    fetched.clear()
    _cli.main(["fetch", "--dataset", "enigh"])
    assert all(f.endswith(f"_{latest_edition().period}.parquet") for f in fetched)


@pytest.mark.parametrize("argv", [
    ["fetch", "--dataset", "denue"],                              # missing STATE
    ["fetch", "33"],                                              # out of range
    ["fetch", "9", "--dataset", "denue", "--edition", "2022"],    # wrong selector
    ["fetch", "--dataset", "enigh", "--period", "2023t1"],        # wrong selector
    ["fetch", "--dataset", "enigh", "--edition", "2015"],         # unknown edition
])
def test_argument_errors(argv, fetched):
    with pytest.raises(SystemExit) as exc:
        _cli.main(argv)
    assert exc.value.code == 2
    assert fetched == []
