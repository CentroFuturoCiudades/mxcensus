"""Tests for the cross-edition municipal geography (``mxcensus.cpv_geo``, unit 6a).

Offline tests read the bundled ``cpv_mun_lineage.yaml``; the ``_REAL`` tests rebuild it from
the Marco Geoestadístico municipal layers in ``data/parquet`` and join it to the ITER.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

import mxcensus
from mxcensus._resources import cpv_mun_lineage as lineage_doc
from mxcensus.cpv_geo import cpv_mun_lineage, cpv_municipal_units
from mxcensus.data._catalog import mg_filename

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_PERIODS = ("1995", "2000", "2005", "2010", "2015", "2020", "2025")


def test_lineage_document():
    doc = lineage_doc()
    assert doc["periodos"] == list(_PERIODS)
    assert doc["municipios"] == {"1995": 2_428, "2000": 2_443, "2005": 2_454, "2010": 2_456,
                                 "2015": 2_457, "2020": 2_469, "2025": 2_478}
    assert len(doc["claves"]) == len(set(doc["claves"])) == doc["municipios"]["2025"]
    lin = cpv_mun_lineage()
    created = lin.groupby(["PERIOD_FROM", "PERIOD_TO"])["CVEGEO"].nunique()
    for old, new in zip(_PERIODS[:-1], _PERIODS[1:]):   # codes are never retired
        assert created[(old, new)] == doc["municipios"][new] - doc["municipios"][old]
    assert ((lin["SHARE_NEW"] >= 0.05) & (lin["SHARE_NEW"] <= 1)).all()
    assert ((lin["SHARE_PARENT"] > 0) & (lin["SHARE_PARENT"] <= 1)).all()
    assert set(lin["CVEGEO"]) <= set(doc["claves"]) and set(lin["PARENT"]) <= set(doc["claves"])
    main = lin.sort_values("SHARE_NEW").groupby("CVEGEO").tail(1)
    assert (main["CVEGEO"].str[:2] == main["PARENT"].str[:2]).all()    # its main parent's state
    assert lin.loc[lin["CVEGEO"] == "02007", "PARENT"].tolist() == ["02001", "02002"]
    # 6h: the EIC 2015 frame dates Bacalar (2011) to 2010 → 2015, the other 12 to 2015 → 2020
    assert lin.loc[lin["PERIOD_TO"] == "2015", "CVEGEO"].unique().tolist() == ["23010"]


def test_municipal_units():
    u = cpv_municipal_units(2020, 2025)
    assert len(u) == 2_478 and u["CVEGEO"].is_unique
    bc = u.set_index("CVEGEO").loc[["02001", "02002", "02007"]]
    assert set(bc["UNIT"]) == {"02001"} and bc.loc["02007", "FIRST"] == "2025"
    assert (u.loc[u["CVEGEO"] == "01001", ["UNIT", "FIRST"]].values == [["01001", "2020"]]).all()
    assert cpv_municipal_units(2015, 2020).set_index("CVEGEO").loc["23011", "FIRST"] == "2020"
    assert len(cpv_municipal_units(2015, 2015)) == 2_457
    same = cpv_municipal_units("2000", "2000")
    assert len(same) == 2_443 and (same["UNIT"] == same["CVEGEO"]).all()
    wide = cpv_municipal_units(1995, 2025)
    assert len(wide) == 2_478 and wide["UNIT"].nunique() < cpv_municipal_units(2010, 2025)["UNIT"].nunique()
    # Bacalar (23009, 2010) took 5% from Yucatán's 31019 (a boundary dispute): ignored by
    # default, joined only across states and below the default share
    assert wide.set_index("CVEGEO").loc["31019", "UNIT"] == "31019"
    loose = cpv_municipal_units(2005, 2010, min_share=0.05, cross_state=True).set_index("CVEGEO")
    assert loose.loc["31019", "UNIT"] == loose.loc["23009", "UNIT"]
    with pytest.raises(ValueError, match="1990 has none"):
        cpv_municipal_units(1990, 2020)
    with pytest.raises(ValueError, match="after end"):
        cpv_municipal_units(2020, 2000)
    assert mxcensus.cpv_municipal_units is cpv_municipal_units


_REAL = all((_MIRROR / mg_filename("mun", s, p)).exists() for p in _PERIODS for s in range(1, 33))


@pytest.mark.skipif(not _REAL, reason="needs the municipal layers of every MG frame")
def test_lineage_rebuilds_from_the_frames():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_geo_crosswalk as b
    assert b.build(_MIRROR) == {k: v for k, v in lineage_doc().items()}


_ITER = all((_MIRROR / f"cpv_iter_{p}_{s:02d}.parquet").exists() for p in ("2000", "2020")
            for s in range(1, 33))


@pytest.mark.skipif(not _ITER, reason="needs the 2000 and 2020 ITER of every state")
def test_units_cover_the_iter(monkeypatch):
    from mxcensus.data import _registry
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda f, **_: str(_MIRROR / f))
    units = cpv_municipal_units(2000, 2020)
    sums = {}
    for p in ("2000", "2020"):
        it = mxcensus.load_cpv_iter(p, state=list(range(1, 33)), nivel="municipal").reset_index()
        it["CVEGEO"] = it["CVE_ENT"] + it["CVE_MUN"]
        merged = it.merge(units, on="CVEGEO", how="left")
        assert merged["UNIT"].notna().all(), p
        sums[p] = merged.groupby("UNIT")["POBTOT"].sum()
    assert sums["2000"].index.equals(sums["2020"].index)      # one common set of units
    assert int(sums["2000"].sum()) == 97_483_412
