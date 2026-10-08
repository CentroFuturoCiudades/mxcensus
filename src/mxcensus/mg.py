"""Marco Geoestadístico (INEGI's geostatistical frame) — layer loader for every mirrored edition.

The mirror holds one GeoParquet file per (layer, state, edition), converted faithfully from
INEGI's per-state shapefile ZIPs by ``scripts/build_marco_geo.py``: ``mg_{layer}_{NN}`` is
the 2020 frame (the original, period-less names), ``mg_{layer}_{period}_{NN}`` any other
edition (``mg_mun_2025_09`` — the Encuesta Intercensal 2025 frame). Layers are listed in
:data:`mxcensus.data._catalog.MG_LAYERS` (``ent``, ``mun``, ``a``/``ar`` AGEBs, ``l``/``lpr``
localities, ``m`` blocks, …; ``ti`` — territorio insular — exists only for the island states).
The EIC 2015 frame (period ``"2015"``, INEGI's closure cartography of the survey) has 12 of
them (``mg_layers("2015")``: no ``cd``/``pe``/``pem``/``ti``); the national-ZIP editions
(1995–2010) have two to five.

**CRS.** Every layer is in the same Lambert conformal conic projection (ITRF2008, GRS80),
but INEGI spells it two ways: most layers carry a custom ``MEXICO_ITRF_2008_LCC`` WKT, a few
carry EPSG:6372 ("Mexico ITRF2008 / LCC") — and which ones differs by edition (2020: ``fm``;
2025: ``ar``/``ent``/``lpr``/``mun``). The two compare unequal, so geopandas refuses to
``concat`` them and warns on ``sjoin``. The mirror keeps each file's source CRS;
:func:`load_mg` returns every layer on :data:`CANONICAL_CRS` (EPSG:6372) by default. PROJ
resolves the conversion between the two spellings to a no-op, so the coordinates are
unchanged bit for bit (``docs/cpv/STEP_1d.md``). The 1995–2015 frames are on ITRF92 with
the same projection parameters; PROJ converts them with a null (ballpark) datum shift too.

The legacy :func:`mxcensus.load_mg_census` (2020 layers merged with the census) is unchanged.
"""
from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import pandas as pd

from mxcensus.cpv import _states
from mxcensus.data._catalog import (
    MG_EDITIONS,
    MG_LAYERS,
    MG_LEGACY_PERIOD,
    MG_OPTIONAL_LAYERS,
    mg_filename,
    mg_layers,
)

# The one projection every MG layer is in, under its EPSG name.
CANONICAL_CRS = "EPSG:6372"


def load_mg(
    layer: str,
    *,
    state: int | Sequence[int],
    period: str | int = MG_LEGACY_PERIOD,
    crs: str | None = CANONICAL_CRS,
) -> gpd.GeoDataFrame:
    """Load one Marco Geoestadístico layer for one or more states.

    - ``load_mg("mun", state=9)`` — CDMX municipalities (alcaldías), 2020 frame.
    - ``load_mg("a", state=[1, 9], period=2025)`` — urban AGEBs of two states, EIC 2025 frame.

    Parameters
    ----------
    layer : str
        Layer suffix, one of :data:`mxcensus.data._catalog.MG_LAYERS`.
    state : int or sequence of int
        INEGI state code(s), 1–32 (the mirror is per state). A sequence loads the states one
        by one and concatenates them (fresh ``RangeIndex``).
    period : str or int, default "2020"
        MG edition (:data:`mxcensus.data._catalog.MG_EDITIONS`); ``"2020"`` reads the legacy
        ``mg_{layer}_{NN}`` files, ``"2025"`` the Encuesta Intercensal 2025 frame, ``"2015"``
        the Encuesta Intercensal 2015 one.
    crs : str or None, default "EPSG:6372"
        CRS to return. The default puts INEGI's two spellings of the MG projection on one
        CRS object without moving any coordinate, so layers and editions combine directly;
        any other CRS reprojects (e.g. ``"EPSG:4326"``); ``None`` keeps each file's stored
        CRS (several states must then share one).

    Returns
    -------
    geopandas.GeoDataFrame
        INEGI's attribute columns verbatim (codes such as ``CVEGEO``/``CVE_ENT``/``CVE_MUN``
        stay zero-padded strings, so they join the CPV frames and estimates) and the
        Multi* ``geometry``.
    """
    if layer not in MG_LAYERS:
        raise ValueError(f"unknown Marco Geoestadístico layer {layer!r}; known: {list(MG_LAYERS)}")
    period = str(period)
    if period not in MG_EDITIONS:
        raise ValueError(f"unknown Marco Geoestadístico period {period!r}; "
                         f"known: {sorted(MG_EDITIONS)}")
    if layer not in mg_layers(period):
        raise ValueError(f"MG {period} has no {layer!r} layer; its layers: "
                         f"{list(mg_layers(period))}")
    states = _states(state)
    if states is None:
        raise ValueError("the Marco Geoestadístico is mirrored per state; pass state= (an "
                         "INEGI code 1-32 or a sequence of them)")

    from mxcensus.data._registry import POOCH

    frames = []
    for s in states:
        fname = mg_filename(layer, s, period)
        try:
            path = POOCH.fetch(fname)
        except ValueError as err:                 # Pooch: "File … is not in the registry"
            note = (" — 'ti' (territorio insular) exists only for the island states"
                    if layer in MG_OPTIONAL_LAYERS else "")
            raise ValueError(f"no MG {period} {layer!r} layer for state {s:02d} in the "
                             f"mirror ({fname}){note}") from err
        gdf = gpd.read_parquet(path)
        if crs is not None:
            gdf = gdf.to_crs(crs)
        frames.append(gdf)

    if len(frames) == 1:
        return frames[0]
    if crs is None and len({f.crs for f in frames}) > 1:
        raise ValueError(f"MG {period} {layer!r}: the states' stored CRSs differ "
                         f"({sorted({f.crs.name for f in frames})}); pass crs= to put them "
                         f"on one (the default {CANONICAL_CRS!r} moves no coordinate)")
    return pd.concat(frames, ignore_index=True)
