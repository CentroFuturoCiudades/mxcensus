"""Tests for the Marco Geoestadístico loader (``mxcensus.load_mg``) and its build script.

Offline tests write synthetic GeoParquet into ``tmp_path`` and point ``POOCH.fetch`` at it.
The ``_REAL`` tests read ``data/parquet`` (sentinel ``mg_mun_2025_01.parquet``): the Mac
holds the 2020 frame for all states and 2025 for state 01; ``wsl`` holds both in full.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from pyproj import CRS
from shapely.geometry import MultiPolygon, box

import mxcensus
from mxcensus.data._catalog import (
    MG_LAYERS,
    MG_OPTIONAL_LAYERS,
    mg_filename,
)
from mxcensus.mg import CANONICAL_CRS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_marco_geo as _bmg  # noqa: E402

# INEGI's two spellings of the one MG projection, verbatim from the 2025 state-01 ZIP
# (``01a.prj`` and ``01ar.prj``).
_PRJ_CUSTOM = (
    'PROJCS["MEXICO_ITRF_2008_LCC",GEOGCS["GCS_ITRF_2008",DATUM["D_ITRF_2008",'
    'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic"],'
    'PARAMETER["False_Easting",2500000.0],PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",-102.0],PARAMETER["Standard_Parallel_1",17.5],'
    'PARAMETER["Standard_Parallel_2",29.5],PARAMETER["Latitude_Of_Origin",12.0],'
    'UNIT["Meter",1.0]]'
)
_PRJ_EPSG = (
    'PROJCS["Mexico ITRF2008 / LCC",GEOGCS["Mexico ITRF2008",DATUM["Mexico_ITRF2008",'
    'SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]],'
    'TOWGS84[0,0,0,0,0,0,0],AUTHORITY["EPSG","1120"]],PRIMEM["Greenwich",0,'
    'AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
    'AUTHORITY["EPSG","6365"]],PROJECTION["Lambert_Conformal_Conic_2SP"],'
    'PARAMETER["standard_parallel_1",17.5],PARAMETER["standard_parallel_2",29.5],'
    'PARAMETER["latitude_of_origin",12],PARAMETER["central_meridian",-102],'
    'PARAMETER["false_easting",2500000],PARAMETER["false_northing",0],'
    'UNIT["metre",1,AUTHORITY["EPSG","9001"]],AUTHORITY["EPSG","6372"]]'
)


def _mun_frame(state: int, crs: str, n: int = 2) -> gpd.GeoDataFrame:
    """A ``mun``-layer frame as the build writes it: string codes, MultiPolygons in LCC
    metres (around Aguascalientes)."""
    ent = f"{state:02d}"
    mun = [f"{i:03d}" for i in range(1, n + 1)]
    geoms = [MultiPolygon([box(2_450_000 + 1000.123456789 * i, 1_100_000.5,
                               2_450_900 + 1000.123456789 * i, 1_100_900.25)])
             for i in range(n)]
    return gpd.GeoDataFrame({"CVEGEO": [ent + m for m in mun], "CVE_ENT": ent, "CVE_MUN": mun,
                             "NOMGEO": [f"M{m}" for m in mun]},
                            geometry=geoms, crs=CRS.from_wkt(crs))


@pytest.fixture
def mg_mirror(tmp_path, monkeypatch):
    """A tiny mirror: ``mun`` for states 1 and 2 in 2020 (custom CRS) and 2025 (state 1
    EPSG-named, state 2 custom — the mixed case). ``POOCH.fetch`` resolves into it and,
    like Pooch, raises ``ValueError`` for a name it does not hold; fetched names are recorded."""
    from mxcensus.data import _registry
    for period, state, prj in [("2020", 1, _PRJ_CUSTOM), ("2020", 2, _PRJ_CUSTOM),
                               ("2025", 1, _PRJ_EPSG), ("2025", 2, _PRJ_CUSTOM)]:
        _mun_frame(state, prj).to_parquet(tmp_path / mg_filename("mun", state, period))
    fetched: list[str] = []

    def _fetch(fname, **_):
        path = tmp_path / fname
        if not path.exists():
            raise ValueError(f"File '{fname}' is not in the registry.")
        fetched.append(fname)
        return str(path)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)
    return fetched


def _coords(gdf: gpd.GeoDataFrame) -> np.ndarray:
    return shapely.get_coordinates(gdf.geometry)


# --- catalog / build script -------------------------------------------------------------

def test_layers_catalog():
    assert len(MG_LAYERS) == 16 and MG_OPTIONAL_LAYERS == {"ti"} <= set(MG_LAYERS)
    assert _bmg._ALL_SUFFIXES == sorted(MG_LAYERS)
    assert mxcensus.load_mg is mxcensus.mg.load_mg and "load_mg" in mxcensus.__all__


def test_build_skips_absent_optional_layer_quietly(tmp_path, capsys):
    frames = {"mun": _mun_frame(1, _PRJ_CUSTOM)}
    written = _bmg._build_marco_geo_state(1, frames.get, tmp_path, ["mun", "ti", "ent"],
                                          "2025")
    assert [p.name for p in written] == ["mg_mun_2025_01.parquet"]
    out = capsys.readouterr().out
    assert "01ent: layer not present" in out and "01ti" not in out


def test_built_files_and_update_registry(tmp_path, capsys):
    out_dir = tmp_path / "parquet"
    out_dir.mkdir()
    for sfx in ("mun", "ti"):
        _mun_frame(2, _PRJ_CUSTOM).to_parquet(out_dir / mg_filename(sfx, 2, "2025"))
    _mun_frame(1, _PRJ_CUSTOM).to_parquet(out_dir / mg_filename("mun", 1, "2025"))
    _mun_frame(1, _PRJ_CUSTOM).to_parquet(out_dir / mg_filename("mun", 1))   # 2020: ignored
    present, missing = _bmg._built_files(out_dir, [1, 2], ["ent", "mun", "ti"], "2025")
    assert sorted(p.name for p in present) == ["mg_mun_2025_01.parquet",
                                              "mg_mun_2025_02.parquet", "mg_ti_2025_02.parquet"]
    assert missing == ["mg_ent_2025_01.parquet", "mg_ent_2025_02.parquet"]   # ti_01: optional

    registry = tmp_path / "registry.txt"
    registry.write_text("# comment\ncpv_x_2025_01.parquet abc\n")
    _bmg.main(["--period", "2025", "--states", "1", "2", "--layers", "ent", "mun", "ti",
               "--update-registry", "--output", str(out_dir), "--registry", str(registry)])
    assert "2 expected file(s) not built" in capsys.readouterr().out
    lines = registry.read_text().splitlines()
    assert lines[0] == "# comment" and "cpv_x_2025_01.parquet abc" in lines
    assert sorted(ln.split()[0] for ln in lines[1:] if ln.startswith("mg_")) == \
        sorted(p.name for p in present)
    with pytest.raises(SystemExit):
        _bmg.main(["--update-registry", "--no-registry", "--output", str(out_dir)])


def test_national_layer_names_and_state_codes():
    assert [_bmg._national_suffix(n) for n in ("Entidades_2010_5", "municipios_2010_5",
                                                "AGEB_urb_2010_5", "Localidades_urbanas_2010_5",
                                                "localidades_rurales_2010_5", "otra_capa")] == \
        ["ent", "mun", "a", "l", "lpr", None]
    f = gpd.GeoDataFrame({"CVEGEO": ["0100100010010", "3200100010010"]}, geometry=[None, None])
    assert list(_bmg._state_codes(f)) == ["01", "32"]               # AGEBs: CVEGEO only
    f = gpd.GeoDataFrame({"cve_ent": [1, 9]}, geometry=[None, None])
    assert list(_bmg._state_codes(f)) == ["01", "09"]
    with pytest.raises(ValueError, match="no entity column"):
        _bmg._state_codes(gpd.GeoDataFrame({"NOM": ["x"]}, geometry=[None]))


def test_build_national_splits_per_state(tmp_path, monkeypatch, capsys):
    """MG 2010 is one national ZIP of per-layer ZIPs; each layer is split per state."""
    import zipfile
    src = tmp_path / "src"
    src.mkdir()
    ent = pd.concat([_mun_frame(1, _PRJ_CUSTOM, 1), _mun_frame(2, _PRJ_CUSTOM, 1)])
    ent = ent.drop(columns="CVE_MUN")
    ageb = ent.drop(columns="CVE_ENT").assign(CVEGEO=["0100100010010", "0200100010021"])
    national = tmp_path / "national.zip"
    with zipfile.ZipFile(national, "w") as outer:
        for stem, frame in (("Entidades_2010_5", ent), ("AGEB_urb_2010_5", ageb),
                            ("otra_capa", ent)):
            frame.to_file(src / f"{stem}.shp")
            inner = src / f"{stem}.zip"
            with zipfile.ZipFile(inner, "w") as z:
                for part in src.glob(f"{stem}.*"):
                    if part.suffix != ".zip":
                        z.write(part, part.name)
            outer.write(inner, inner.name)
    monkeypatch.setattr(_bmg.bc, "fetch_zip_verified", lambda *a, **k: national)
    out = tmp_path / "out"
    out.mkdir()
    written = _bmg._build_national("2010", [1], ["ent", "mun", "a"], out, tmp_path / "cache",
                                   tmp_path / "raw", 0)
    assert sorted(p.name for p in written) == ["mg_a_2010_01.parquet", "mg_ent_2010_01.parquet"]
    a = gpd.read_parquet(out / "mg_a_2010_01.parquet")
    assert list(a["CVEGEO"]) == ["0100100010010"] and a.crs.equals(CRS.from_wkt(_PRJ_CUSTOM))
    assert "otra_capa.shp: no layer suffix" in capsys.readouterr().out
    assert not (tmp_path / "raw" / "mg" / "2010" / "national").exists()    # cleaned up
    assert [p.name for p in _bmg._national_built(out, [1, 2], ["ent", "a"], "2010")] == \
        ["mg_ent_2010_01.parquet", "mg_a_2010_01.parquet"]


# --- load_mg (offline) ------------------------------------------------------------------

def test_load_mg_filenames_by_period(mg_mirror):
    mxcensus.load_mg("mun", state=1)
    mxcensus.load_mg("mun", state=1, period=2025)
    mxcensus.load_mg("mun", state=[2, 1, 2], period="2025")
    assert mg_mirror == ["mg_mun_01.parquet", "mg_mun_2025_01.parquet",
                         "mg_mun_2025_02.parquet", "mg_mun_2025_01.parquet"]


def test_load_mg_default_crs_is_canonical_and_lossless(mg_mirror, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        g20 = mxcensus.load_mg("mun", state=1)
        g25 = mxcensus.load_mg("mun", state=[1, 2], period=2025)   # mixed spellings
    assert g20.crs == g25.crs == CRS.from_user_input(CANONICAL_CRS)
    assert isinstance(g25, gpd.GeoDataFrame) and g25.index.equals(pd.RangeIndex(4))
    assert g25["CVEGEO"].tolist() == ["01001", "01002", "02001", "02002"]
    assert all(str(g25[c].dtype) == "str" for c in ("CVEGEO", "CVE_ENT", "CVE_MUN"))
    for state, name in [(1, "mg_mun_2025_01.parquet"), (2, "mg_mun_2025_02.parquet")]:
        stored = gpd.read_parquet(tmp_path / name)
        assert (_coords(g25[g25["CVE_ENT"] == f"{state:02d}"]) == _coords(stored)).all()
    pd.concat([g20, g25])                                  # one CRS: combines directly


def test_load_mg_crs_none_and_reprojection(mg_mirror):
    raw = mxcensus.load_mg("mun", state=1, period=2025, crs=None)
    assert raw.crs.name == "Mexico ITRF2008 / LCC"
    assert mxcensus.load_mg("mun", state=[1, 2], crs=None).crs.name == "MEXICO_ITRF_2008_LCC"
    with pytest.raises(ValueError, match="stored CRSs differ.*pass crs="):
        mxcensus.load_mg("mun", state=[1, 2], period=2025, crs=None)
    geo = mxcensus.load_mg("mun", state=1, period=2025, crs="EPSG:4326")
    assert geo.crs.to_epsg() == 4326
    lon, lat = _coords(geo).mean(axis=0)
    assert -103 < lon < -101 and 21 < lat < 23            # Aguascalientes


@pytest.mark.parametrize("kwargs, match", [
    (dict(layer="xx", state=1), "unknown Marco Geoestadístico layer"),
    (dict(layer="mun", state=1, period=2015), "unknown Marco Geoestadístico period"),
    (dict(layer="mun", state=None), "mirrored per state"),
    (dict(layer="mun", state=33), "state code 1-32"),
    (dict(layer="mun", state=[]), "empty sequence"),
    (dict(layer="mun", state=True), "state code 1-32"),
    (dict(layer="mun", state=3, period=2025), r"no MG 2025 'mun' layer for state 03"),
    (dict(layer="ti", state=1, period=2025), "island states"),
])
def test_load_mg_errors(mg_mirror, kwargs, match):
    with pytest.raises(ValueError, match=match):
        mxcensus.load_mg(**kwargs)


# --- real mirror ------------------------------------------------------------------------

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REQUIRED = sorted(set(MG_LAYERS) - MG_OPTIONAL_LAYERS)
_REAL = (_MIRROR / "mg_mun_2025_01.parquet").exists()
_REAL_SKIP = pytest.mark.skipif(not _REAL, reason="no local MG 2025 mirror (data/parquet/)")


def _local_states(period: str) -> list[int]:
    """States whose every required layer of ``period`` is on disk."""
    return [s for s in range(1, 33)
            if all((_MIRROR / mg_filename(sfx, s, period)).exists() for sfx in _REQUIRED)]


@pytest.fixture
def local_mirror(monkeypatch):
    """Redirect ``POOCH.fetch`` to ``data/parquet``, so the real-data tests read the local
    mirror (no network, no user cache); a missing file raises like Pooch's not-in-registry."""
    from mxcensus.data import _registry

    def _fetch(fname, **_):
        p = _MIRROR / fname
        if not p.exists():
            raise ValueError(f"File '{fname}' is not in the registry.")
        return str(p)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)
    return _MIRROR


@_REAL_SKIP
def test_real_crs_spellings_are_one_projection(local_mirror):
    """State 01: which layers INEGI ships under the EPSG name, and that the default
    ``crs`` moves no coordinate of any layer in either edition (PROJ resolves the
    conversion to a no-op — a PROJ update adding a datum shift would fail here)."""
    epsg_named = {}
    for period in ("2020", "2025"):
        epsg_named[period] = set()
        for sfx in _REQUIRED:
            stored = gpd.read_parquet(_MIRROR / mg_filename(sfx, 1, period))
            if stored.crs.to_epsg() == 6372:
                epsg_named[period].add(sfx)
            else:
                assert stored.crs.name == "MEXICO_ITRF_2008_LCC"
            loaded = mxcensus.load_mg(sfx, state=1, period=period)
            assert loaded.crs.to_epsg() == 6372
            assert np.array_equal(_coords(loaded), _coords(stored))
    assert epsg_named == {"2020": {"fm"}, "2025": {"ar", "ent", "lpr", "mun"}}


@_REAL_SKIP
def test_real_layers_and_editions_combine(local_mirror):
    a = mxcensus.load_mg("a", state=1, period=2025)
    ar = mxcensus.load_mg("ar", state=1, period=2025)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        both = pd.concat([a, ar], ignore_index=True)
        gpd.sjoin(mxcensus.load_mg("l", state=1, period=2025),
                  mxcensus.load_mg("lpr", state=1, period=2025), predicate="intersects")
    # urban AGEB = ENT+MUN+LOC+AGEB (13), rural AGEB = ENT+MUN+AGEB (9)
    assert both["CVEGEO"].str.len().value_counts().to_dict() == {13: len(a), 9: len(ar)}
    assert both["CVEGEO"].is_unique
    m20, m25 = (mxcensus.load_mg("mun", state=1, period=p) for p in (2020, 2025))
    assert m20.crs == m25.crs and set(m20["CVEGEO"]) == set(m25["CVEGEO"])
    # the state boundary did not move between frames (≈1 m² of 5,559 km²)
    e20, e25 = (mxcensus.load_mg("ent", state=1, period=p) for p in (2020, 2025))
    assert e20.geometry.iloc[0].symmetric_difference(e25.geometry.iloc[0]).area < 10


@_REAL_SKIP
def test_real_states_mix_spellings(local_mirror):
    """2020 ``fm`` is EPSG-named in 30 states but custom in 02 and 25, so a multi-state
    load needs ``crs`` (the default) — ``crs=None`` refuses rather than failing in concat."""
    with pytest.raises(ValueError, match="stored CRSs differ"):
        mxcensus.load_mg("fm", state=[1, 2], crs=None)
    fm = mxcensus.load_mg("fm", state=[1, 2])
    assert fm.crs.to_epsg() == 6372 and set(fm["CVE_ENT"]) == {"01", "02"}


@_REAL_SKIP
def test_real_layer_columns_match_2020(local_mirror):
    """Every 2025 layer keeps the 2020 attribute columns and geometry type."""
    for s in _local_states("2025"):
        for sfx in _REQUIRED:
            g25 = gpd.read_parquet(_MIRROR / mg_filename(sfx, s, "2025"))
            g20 = gpd.read_parquet(_MIRROR / mg_filename(sfx, s, "2020"))
            assert list(g25.columns) == list(g20.columns), (s, sfx)
            assert set(g25.geom_type.dropna()) == set(g20.geom_type.dropna()), (s, sfx)


@_REAL_SKIP
def test_real_municipalities_match_estimates(local_mirror):
    """Every EIC 2025 municipality with an estimate has an ``mg_mun_2025`` polygon, and
    the reverse — for every state on disk (all 32 on wsl)."""
    est_path = _MIRROR / "cpv_estimaciones_2025.parquet"
    if not est_path.exists():
        pytest.skip("no cpv_estimaciones_2025.parquet")
    states = _local_states("2025")
    est = mxcensus.load_cpv_estimaciones(survey_path=est_path, nivel="municipal")
    est_mun = {e + m for e, m, _ in est.index if int(e) in states}
    mg = mxcensus.load_mg("mun", state=states, period=2025)
    assert mg["CVEGEO"].is_unique and set(mg["CVEGEO"]) == est_mun
    if len(states) == 32:
        assert len(mg) == 2478


@_REAL_SKIP
def test_real_islands(local_mirror):
    """``ti`` is on disk only for island states and loads like any layer."""
    for period in ("2020", "2025"):
        have = [s for s in range(1, 33) if (_MIRROR / mg_filename("ti", s, period)).exists()]
        if not have:
            continue
        ti = mxcensus.load_mg("ti", state=have, period=period)
        assert ti.crs.to_epsg() == 6372 and len(ti) > 0
        assert set(ti["CVE_ENT"].astype(int)) <= set(have)


# National totals stated in each edition's ``catalogos/contenido.txt``: municipalities,
# locality polygons (rural amanzanadas + urban), rural locality points, island polygons,
# rural and urban AGEBs, and blocks "incluyendo caserío disperso" (= m + cd).
_CONTENIDO = {
    "2020": {"mun": 2_469, "l": 45_397 + 4_911, "lpr": 295_779, "ti": 350, "ar": 17_469,
             "a": 63_982, ("m", "cd"): 2_513_853},
    "2025": {"mun": 2_478, "l": 46_894 + 4_904, "lpr": 291_946, "ti": 367, "ar": 17_475,
             "a": 64_807, ("m", "cd"): 2_636_733},
}


@pytest.mark.parametrize("period", sorted(_CONTENIDO))
def test_real_national_counts_match_contenido(period):
    if len(_local_states(period)) < 32:
        pytest.skip(f"MG {period} not on disk for all 32 states")
    import pyarrow.parquet as pq

    def rows(sfx: str) -> int:
        return sum(pq.read_metadata(p).num_rows
                   for s in range(1, 33) if (p := _MIRROR / mg_filename(sfx, s, period)).exists())

    for layers, expected in _CONTENIDO[period].items():
        layers = layers if isinstance(layers, tuple) else (layers,)
        if layers == ("ti",) and rows("ti") == 0:
            continue                                  # ti not built on this host
        assert sum(rows(sfx) for sfx in layers) == expected, (period, layers)
    assert rows("ent") == 32


# MG 2010 v5.0 is one national ZIP with five layers and no contenido.txt; its counts are
# checked against the Censo 2010 ITER instead: the same 2,456 municipalities, and 192,244
# localities (urban polygons + rural points) for the ITER's 192,247 locality rows.
_MG_2010 = {"ent": 32, "mun": 2_456, "a": 56_195, "l": 4_525, "lpr": 187_719}


def test_real_mg_2010_counts(local_mirror):
    if not all((_MIRROR / mg_filename(sfx, s, "2010")).exists()
               for sfx in _MG_2010 for s in range(1, 33)):
        pytest.skip("MG 2010 not on disk for all 32 states")
    import pyarrow.parquet as pq
    for sfx, expected in _MG_2010.items():
        assert sum(pq.read_metadata(_MIRROR / mg_filename(sfx, s, "2010")).num_rows
                   for s in range(1, 33)) == expected, sfx
    mun = mxcensus.load_mg("mun", state=1, period="2010")
    assert len(mun) == 11 and mun.crs.equals(CRS.from_epsg(6372))
    assert set(mun["CVE_ENT"]) == {"01"} and "CVEGEO" not in mun      # 2010: no CVEGEO here
