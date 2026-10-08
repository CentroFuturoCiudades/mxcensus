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


def test_cpv_state_tables_plus_national(fetched):
    _cli.main(["fetch", "9", "--dataset", "cpv"])
    assert fetched == ["cpv_viviendas_2025_09.parquet", "cpv_personas_2025_09.parquet",
                       "cpv_migrantes_2025_09.parquet", "cpv_estimaciones_2025.parquet"]
    fetched.clear()
    _cli.main(["fetch", "1", "--dataset", "cpv", "--edition", "2025"])
    assert fetched[0] == "cpv_viviendas_2025_01.parquet" and len(fetched) == 4
    fetched.clear()
    _cli.main(["fetch", "9", "--dataset", "cpv", "--edition", "2020"])   # + ITER/AGEB, per state
    assert fetched == [f"cpv_{t}_2020_09.parquet"
                       for t in ("viviendas", "personas", "migrantes", "iter", "ageb")]


def test_mg_layers_in_registry(fetched):
    _cli.main(["fetch", "9", "--dataset", "mg"])                  # default: the 2020 frame
    assert len(fetched) == 15 and fetched[:2] == ["mg_ent_09.parquet", "mg_mun_09.parquet"]
    fetched.clear()
    _cli.main(["fetch", "2", "--dataset", "mg", "--edition", "2025"])   # an island state
    assert len(fetched) == 16 and "mg_ti_2025_02.parquet" in fetched
    assert all(f.endswith("_2025_02.parquet") for f in fetched)


@pytest.mark.parametrize("argv", [
    ["fetch", "--dataset", "denue"],                              # missing STATE
    ["fetch", "33"],                                              # out of range
    ["fetch", "9", "--dataset", "denue", "--edition", "2022"],    # wrong selector
    ["fetch", "--dataset", "enigh", "--period", "2023t1"],        # wrong selector
    ["fetch", "--dataset", "enigh", "--edition", "2015"],         # unknown edition
    ["fetch", "--dataset", "cpv"],                                # missing STATE
    ["fetch", "9", "--dataset", "cpv", "--edition", "2016"],      # unknown edition
    ["fetch", "9", "--dataset", "cpv", "--edition", "2015"],      # not mirrored yet
    ["fetch", "9", "--dataset", "mg", "--edition", "2015"],       # unknown MG edition
    ["fetch", "9", "--dataset", "mg", "--edition", "2010"],       # not mirrored yet
    ["fetch", "9", "--dataset", "mg", "--period", "2025"],        # wrong selector
])
def test_argument_errors(argv, fetched):
    with pytest.raises(SystemExit) as exc:
        _cli.main(argv)
    assert exc.value.code == 2
    assert fetched == []
