"""Smoke tests pinning the legacy CPV 2020 path (``load_census`` / ``load_extended_*``).

The multi-year CPV family (``mxcensus.cpv``, ``cpv_*`` files) is built alongside these
loaders without touching them; these tests guard that the frozen 2020 path keeps
producing the same frames. They run only when the local legacy mirror
(``data/parquet/iter_01.parquet`` …) is present, via a fixture that redirects
``POOCH.fetch`` to it (no network).
"""
from __future__ import annotations

from pathlib import Path

import pytest

import mxcensus

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REAL = all((_MIRROR / f"{ds}_01.parquet").exists()
            for ds in ("iter", "resargebub", "personas", "viviendas"))

pytestmark = pytest.mark.skipif(not _REAL, reason="no local legacy census mirror (data/parquet/)")


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


def test_load_census_state_01(local_mirror):
    state, mun, loc, ageb = mxcensus.load_census(state=1)
    assert [list(df.index.names) for df in (state, mun, loc, ageb)] == [
        ["ENTIDAD"], ["ENTIDAD", "MUN"], ["ENTIDAD", "MUN", "LOC"],
        ["ENTIDAD", "MUN", "LOC", "AGEB"],
    ]
    assert (len(state), len(mun), len(loc), len(ageb)) == (1, 11, 2022, 480)
    # INEGI: Aguascalientes 2020 population 1,425,607 — consistent across levels.
    for df in (state, mun, loc):
        assert int(df["POBTOT"].sum()) == 1_425_607
    assert int(ageb["POBTOT"].sum()) == 1_198_711


def test_load_extended_state_01(local_mirror):
    p = mxcensus.load_extended_personas(state=1)
    v = mxcensus.load_extended_viviendas(state=1)
    assert list(p.index.names) == ["ID_VIV", "ID_PERSONA"]
    assert list(v.index.names) == ["ID_VIV"]
    assert p.shape == (95_983, 139) and v.shape == (24_349, 96)
    assert int(p["FACTOR"].sum()) == 1_421_198
    assert int(v["FACTOR"].sum()) == 387_762
    assert p.index.get_level_values("ID_VIV").isin(v.index).all()
