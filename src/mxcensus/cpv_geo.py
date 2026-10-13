"""Cross-edition municipal and locality geography for the CPV family (1990–2025).

Municipalities split between censuses: Mexico had 2,428 in the 1995 frame and 2,478 in
2025. A split keeps the parent's code and gives the seceding part a new one; codes are
never retired. The lineage of every new code comes from the Marco Geoestadístico polygons
(``_yaml/cpv_mun_lineage.yaml``, built by ``scripts/build_geo_crosswalk.py``): which
municipalities of the previous frame its territory came from, and in what shares.

- :func:`cpv_mun_lineage` — that lineage as a table.
- :func:`cpv_municipal_units` — stable municipal units between two editions: every
  municipality of the later one (a superset of the earlier one's) mapped to a unit that
  joins each municipality created in between with its parents. Aggregating both editions
  to these units makes them comparable.

Example — municipal population 2000 vs 2020 on common units::

    units = mxcensus.cpv_municipal_units(2000, 2020)
    it = {p: mxcensus.load_cpv_iter(p, state=7, nivel="municipal") for p in (2000, 2020)}
    pob = {p: f.reset_index().assign(CVEGEO=lambda d: d.CVE_ENT + d.CVE_MUN)
               .merge(units, on="CVEGEO").groupby("UNIT")["POBTOT"].sum()
           for p, f in it.items()}

The 1990 census has no frame, so its municipalities have no lineage here (its codes are a
subset of 1995's).

Localities change far more: between two censuses tens of thousands are dropped, created,
renumbered, moved to a new municipality, absorbed by a growing town or split off again.
INEGI's Archivo Histórico de Localidades records each locality's history; the links it
documents between two codes from 1990 on are bundled (``_yaml/cpv_loc_lineage.csv.gz``,
built by ``scripts/build_loc_lineage.py``).

- :func:`cpv_loc_lineage` — those links as a table.
- :func:`cpv_locality_units` — the localities two editions' codes must be joined into to
  compare them: a renumbered or moved locality with its old code, an absorbed one with the
  locality that absorbed it.

Example — locality population 2000 vs 2020 on common units::

    units = mxcensus.cpv_locality_units(2000, 2020).set_index("CVEGEO")["UNIT"]
    it = {p: mxcensus.load_cpv_iter(p, state=7, nivel="localidad") for p in (2000, 2020)}
    pob = {p: f.assign(UNIT=lambda d: d.CVEGEO.map(units).fillna(d.CVEGEO))
               .groupby("UNIT")["POBTOT"].sum()
           for p, f in it.items()}
"""
from __future__ import annotations

import functools

import pandas as pd

from mxcensus._resources import cpv_loc_lineage as _loc_doc
from mxcensus._resources import cpv_mun_lineage as _lineage_doc

__all__ = ["cpv_loc_lineage", "cpv_locality_units", "cpv_mun_lineage", "cpv_municipal_units"]


@functools.cache
def _lineage() -> pd.DataFrame:
    rows = [(c["desde"], c["hasta"], c["CVEGEO"], o["CVEGEO"], o["parte_del_nuevo"],
             o["parte_del_origen"])
            for c in _lineage_doc()["cambios"] for o in c["origen"]]
    return pd.DataFrame(rows, columns=["PERIOD_FROM", "PERIOD_TO", "CVEGEO", "PARENT",
                                       "SHARE_NEW", "SHARE_PARENT"])


def cpv_mun_lineage() -> pd.DataFrame:
    """Every municipality created between two consecutive Marco Geoestadístico frames
    (1995, 2000, 2005, 2010, 2020, 2025), one row per parent: ``PERIOD_FROM`` /
    ``PERIOD_TO`` (the frames it falls between), ``CVEGEO`` (the new municipality, entity +
    municipality), ``PARENT`` (a municipality of ``PERIOD_FROM`` covering at least 5% of
    it), ``SHARE_NEW`` (that share of the new municipality's area) and ``SHARE_PARENT``
    (the share of the parent's area that went to it)."""
    return _lineage().copy()


def _period(value) -> str:
    periods = _lineage_doc()["periodos"]
    p = str(value)
    if p not in periods:
        raise ValueError(f"no municipal frame for {value!r}; frames: {periods} (1990 has none)")
    return p


def cpv_municipal_units(start, end, *, min_share: float = 0.10,
                        cross_state: bool = False) -> pd.DataFrame:
    """Stable municipal units between editions ``start`` and ``end`` (frames 1995–2025).

    Returns one row per municipality of ``end`` (``CVEGEO``, 5 characters): ``UNIT``, the
    smallest code of its unit, and ``FIRST``, the frame where the code first appears
    (``start`` for the municipalities that already existed). A unit joins every
    municipality created after ``start`` (up to ``end``) with the parents that gave it at
    least ``min_share`` of its area, transitively; unchanged municipalities are units of
    their own. A parent in another state (a boundary dispute: Quintana Roo's 23009
    Bacalar and Yucatán's 31019, 5%) is ignored unless ``cross_state``. Merge an edition's
    municipal rows on ``CVEGEO`` and aggregate by ``UNIT``; the editions' municipalities
    are then comparable.
    """
    a, b = _period(start), _period(end)
    periods = _lineage_doc()["periodos"]
    if periods.index(a) > periods.index(b):
        raise ValueError(f"start {a} is after end {b}")
    lin = _lineage()
    later = set(lin.loc[lin["PERIOD_TO"].map(periods.index) > periods.index(b), "CVEGEO"])
    codes = [c for c in _lineage_doc()["claves"] if c not in later]
    first = {c: a for c in codes}
    span = lin[(lin["PERIOD_FROM"].map(periods.index) >= periods.index(a))
               & (lin["PERIOD_TO"].map(periods.index) <= periods.index(b))]
    for code, to in zip(span["CVEGEO"], span["PERIOD_TO"]):
        first[code] = to
    parent = {c: c for c in codes}

    def find(c: str) -> str:
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    links = span[span["SHARE_NEW"] >= min_share]
    if not cross_state:
        links = links[links["CVEGEO"].str[:2] == links["PARENT"].str[:2]]
    for new, old in zip(links["CVEGEO"], links["PARENT"]):
        ra, rb = find(new), find(old)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return pd.DataFrame({"CVEGEO": codes, "UNIT": [find(c) for c in codes],
                         "FIRST": [first[c] for c in codes]})


# The editions with locality codes, oldest first: the ITERs 1990–2020 and the EIC 2025's
# frame (MG 2025). A link takes effect at the first one whose codes reflect it.
_LOC_PERIODS = ("1990", "1995", "2000", "2005", "2010", "2020", "2025")
_LOC_KINDS = ("code", "absorption", "counted_with", "separation")


@functools.cache
def _loc_lineage() -> pd.DataFrame:
    df = _loc_doc().copy()
    df["DATE"] = pd.to_datetime(df["DATE"])
    df["KIND"] = pd.Categorical(df["KIND"], _LOC_KINDS)
    df["CONFIRMED"] = df["CONFIRMED"] == "1"
    return df


def cpv_loc_lineage() -> pd.DataFrame:
    """Every documented link between two locality codes (``FROM``, ``TO``: entity +
    municipality + locality, 9 characters) that takes effect at a CPV edition from 1990 on,
    from INEGI's Archivo Histórico de Localidades:

    - ``PERIOD`` — the first edition whose locality codes reflect it (``1990``, ``1995``,
      ``2000``, ``2005``, ``2010``, ``2020``: the ITER; ``2025``: the EIC 2025's frame, MG
      2025): its date's, or a later one when that edition's census still counts the
      absorbed locality on its own, or does not yet count the separated one (44 links);
    - ``DATE``, ``EVENT`` — the event that records it (``census``: a census or count, dated
      by its reference date; ``update``: a geostatistical update; ``other``: a decree…);
    - ``KIND`` — ``code`` (the same locality under another code: a move to another
      municipality or state, a renumbering, a duplicate registration), ``absorption``
      (``FROM`` joins ``TO``: conurbation, fusion), ``counted_with`` (``FROM`` counted with
      ``TO`` at that census only), ``separation`` (``FROM`` leaves ``TO``);
    - ``CONFIRMED`` — stated on both localities' records (otherwise on one).
    """
    return _loc_lineage().copy()


def _loc_period(value) -> str:
    p = str(value)
    if p not in _LOC_PERIODS:
        raise ValueError(f"no locality codes for {value!r}; editions: {_LOC_PERIODS}")
    return p


def cpv_locality_units(start, end, *, absorptions: bool = True,
                       confirmed: bool = False) -> pd.DataFrame:
    """The locality units that make editions ``start`` and ``end`` comparable (``1990``,
    ``1995``, ``2000``, ``2005``, ``2010``, ``2020``, ``2025``).

    Returns one row per locality code that a link joins to another between the two
    editions: ``CVEGEO`` (9 characters) and ``UNIT``, the smallest code of its unit. A
    unit joins, transitively, the codes of every link that takes effect after ``start``
    up to ``end`` — the same locality under a new code, a locality absorbed by another or
    separated from it — and the localities counted with another at either edition's census
    or in between. Every other code is a unit of its own: map an edition's ``CVEGEO`` through
    the result, keep the code where it is missing, aggregate by ``UNIT``.

    ``absorptions=False`` joins only the same locality under another code (no absorptions,
    separations or localities counted with another). ``confirmed=True`` uses only the links
    stated on both localities' records. A locality may move to another state: its unit
    then spans two states. Localities created or dropped in between (uninhabited, new
    settlements) are units of their own in the edition that lists them.
    """
    a, b = _loc_period(start), _loc_period(end)
    if _LOC_PERIODS.index(a) > _LOC_PERIODS.index(b):
        raise ValueError(f"start {a} is after end {b}")
    lin = _loc_lineage()
    pos = lin["PERIOD"].map(_LOC_PERIODS.index)
    ia, ib = _LOC_PERIODS.index(a), _LOC_PERIODS.index(b)
    counted = lin["KIND"] == "counted_with"
    keep = (~counted & (pos > ia) & (pos <= ib)) | (counted & (pos >= ia) & (pos <= ib) & (ia < ib))
    if not absorptions:
        keep &= lin["KIND"] == "code"
    if confirmed:
        keep &= lin["CONFIRMED"]
    links = lin[keep]
    parent: dict[str, str] = {}

    def find(c: str) -> str:
        parent.setdefault(c, c)
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for x, y in zip(links["FROM"], links["TO"]):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)
    codes = sorted(parent)
    out = pd.DataFrame({"CVEGEO": codes, "UNIT": [find(c) for c in codes]})
    return out.sort_values(["UNIT", "CVEGEO"], ignore_index=True)
