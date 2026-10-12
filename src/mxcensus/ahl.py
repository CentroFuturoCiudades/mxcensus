"""INEGI's Archivo Histórico de Localidades (AHL): every locality's population 1900–2020.

The AHL is INEGI's history of the localities of its geostatistical catalog (413,339
records), each filed under the locality's **last** code. The mirror keeps its four tables
per state as published (:func:`load_ahl`, a snapshot of INEGI's export:
:mod:`mxcensus.data._ahl_catalog`); two analysis-ready frames are built from them:

- :func:`load_ahl_poblacion` — a historical ITER: the population (total, men, women) of
  every locality at every census and count 1900–2020 (and the 1939 buildings census), with
  the name, municipality and category it had then;
- :func:`load_ahl_localidades` — one row per locality: its current name, urban/rural type,
  coordinates (decimal degrees; ``geometry=True`` for points), altitude.

**One code across time.** A record holds the history of one locality under its last code,
so the population rows of a locality that changed code since are under the new code — the
panel needs no code bridge. The ITER of each census 1990–2020 lists the codes of its own
time; :func:`mxcensus.cpv_locality_units` maps them. Against the ITERs the AHL's
populations differ in 2–11 localities per census 1995–2020 and 26 in 1990 (where both
publish one); the AHL has the population of 1,589 localities the Conteo 1995's ITER
reserves, and none for 1,381 localities of the 1990 ITER (102,276 persons, most of
Escárcega, created after that census): ``docs/cpv/AHL_REPORT.md``.

**Coverage before 1990.** The AHL holds the localities of INEGI's present catalog (those
dropped since included); its sums are 83–89% of the national population for 1900–1960,
95% for 1970 and 99.8% for 1980 — a panel of the catalog's localities, not the old
censuses' full listings.

**INEGI's copies.** When a locality changes code after a census (since the Censo 2010),
INEGI copies that census's row to the new record (444 rows in 2010, 689 in 2020), so it is
counted twice.
:func:`load_ahl_poblacion` finds them with the bundled lineage
(:func:`mxcensus.cpv_loc_lineage`) and drops them unless ``copies=True``; the 2010 and 2020
sums then equal the ITERs' to within 115 and 155 persons.

Example — a municipality's localities over a century::

    pob = mxcensus.load_ahl_poblacion(state=1)
    pob.xs("001", level="CVE_MUN")["POBTOT"].unstack("EVE_CENSAL")
"""
from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from datetime import date

import pandas as pd

from mxcensus.cpv import _states
from mxcensus.data._ahl_catalog import TABLES, ahl_filename

__all__ = ["load_ahl", "load_ahl_localidades", "load_ahl_poblacion"]

_INDEX = ["CVE_ENT", "CVE_MUN", "CVE_LOC"]

# The censuses and counts the AHL records: year → (kind, reference date). The dates
# matter only from 1990 on (the lineage's links start there; an earlier census precedes
# every link); they are build_loc_lineage's.
CENSUSES: dict[int, tuple[str, date]] = {
    1900: ("Censo", date(1900, 10, 28)), 1910: ("Censo", date(1910, 10, 27)),
    1921: ("Censo", date(1921, 11, 30)), 1930: ("Censo", date(1930, 5, 15)),
    1939: ("Censo de edificios", date(1939, 1, 1)), 1940: ("Censo", date(1940, 3, 6)),
    1950: ("Censo", date(1950, 6, 6)), 1960: ("Censo", date(1960, 6, 8)),
    1970: ("Censo", date(1970, 1, 28)), 1980: ("Censo", date(1980, 6, 4)),
    1990: ("Censo", date(1990, 3, 12)), 1995: ("Conteo", date(1995, 11, 5)),
    2000: ("Censo", date(2000, 2, 14)), 2005: ("Conteo", date(2005, 10, 17)),
    2010: ("Censo", date(2010, 6, 12)), 2020: ("Censo", date(2020, 3, 15)),
}
FUENTES = ("Censo", "Conteo", "Censo de edificios")
# INEGI writes the 1921 census «1920» in a few rows (their history says «Censo de 1921»).
_YEAR_ALIASES = {"1920": "1921"}

_COUNTS = {"TOT_HAB": "POBTOT", "TOT_HOM": "POBMAS", "TOT_MUJ": "POBFEM"}
_RESERVED = {"*", "-"}          # * reserved (one or two dwellings), - not available


def _fetch(fname: str) -> str:
    from mxcensus.data._registry import POOCH
    return POOCH.fetch(fname)


def _read(table: str, states: list[int], snapshot: str | None) -> pd.DataFrame:
    frames = [pd.read_parquet(_fetch(ahl_filename(table, s, snapshot))) for s in states]
    return frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)


def _require_states(state) -> list[int]:
    states = _states(state)
    if states is None:
        raise ValueError("the AHL is mirrored per state; pass state= (an INEGI code 1-32 or "
                         "a sequence of them)")
    return states


def load_ahl(table: str, *, state: int | Sequence[int],
             snapshot: str | None = None) -> pd.DataFrame:
    """One table of INEGI's Archivo Histórico de Localidades as published.

    ``table`` is ``habitantes``, ``maestro``, ``movimientos`` or ``res_hist``
    (:data:`mxcensus.data._ahl_catalog.TABLES`); ``state`` an INEGI code or a sequence of
    them (concatenated, fresh ``RangeIndex``); ``snapshot`` the export (``YYYYMMDD``,
    default the latest mirrored). Every column is a string in INEGI's spelling (the
    population ``1,234`` with its thousands separator, ``*``/``-`` reserved), empty cells
    missing; the rows in INEGI's order.
    """
    if table not in TABLES:
        raise ValueError(f"unknown AHL table {table!r}; known: {list(TABLES)}")
    return _read(table, _require_states(state), snapshot)


# --------------------------------------------------------------------------- population

def _count(s: pd.Series, name: str) -> pd.Series:
    """INEGI's population string (``1,234``; ``*``/``-`` → missing) as ``Int64``."""
    digits = s.str.replace(",", "", regex=False)
    bad = s.notna() & ~s.isin(_RESERVED) & ~digits.str.fullmatch(r"\d+").fillna(False)
    if bad.any():
        raise ValueError(f"AHL {name}: unexpected values {sorted(set(s[bad]))[:10]}")
    return pd.to_numeric(digits.where(~s.isin(_RESERVED)), errors="raise").astype("Int64")


def _rank(s: pd.Series) -> pd.Series:
    """A duplicate row's information: a population > reserved (``*``) > 0 > ``-``."""
    n = pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")
    return (n.gt(0).astype(int) * 3 + s.eq("*").astype(int) * 2 + n.eq(0).astype(int)
            ).fillna(0).astype(int)


# Rows INEGI read one column off from the ITER (a quoted locality name in 1990; in
# 1995/2000 the names that spilled into LONGITUD, ``cpv_aggregates._repair_spilled_names``):
# ``TOT_HAB`` holds the altitude (``*`` in 1990), ``TOT_HOM`` the total, ``TOT_MUJ`` the
# men. Shifted back (the women = total − men): each then equals its ITER.
_SHIFTED = {
    ("020021303", "1990"), ("080070286", "1990"), ("200170008", "1990"),
    ("080070286", "1995"), ("080130220", "1995"), ("200170008", "1995"),
    ("202770101", "1995"), ("204460033", "1995"), ("220120011", "1995"),
    ("202770101", "2000"), ("220120011", "2000"),
}


def _unshift(df: pd.DataFrame) -> pd.DataFrame:
    """The :data:`_SHIFTED` rows shifted back, while still inconsistent (the sexes do not
    add up to the total: a later snapshot may have fixed them)."""
    n = {c: pd.to_numeric(df[c].str.replace(",", "", regex=False), errors="coerce")
         for c in _COUNTS}
    listed = pd.Series([k in _SHIFTED for k in zip(df["CVE_GEOEST"], df["EVE_CENSAL"])],
                       index=df.index)
    fix = listed & n["TOT_HOM"].notna() & n["TOT_MUJ"].notna() & (
        n["TOT_HAB"].fillna(-1) != n["TOT_HOM"] + n["TOT_MUJ"])
    if not fix.any():
        return df
    df = df.copy()
    women = (n["TOT_HOM"] - n["TOT_MUJ"])[fix].astype(int).map("{:,}".format)
    df.loc[fix, "TOT_HAB"] = df.loc[fix, "TOT_HOM"]
    df.loc[fix, "TOT_HOM"] = df.loc[fix, "TOT_MUJ"]
    df.loc[fix, "TOT_MUJ"] = women
    return df


def _habitantes(raw: pd.DataFrame) -> pd.DataFrame:
    """The population rows on census years, one per (locality, year): INEGI's «1920»
    (the 1921 census) moved, rows on no census year dropped (warning if one has
    population), of two rows of one year the one with more information (the ITER agrees
    where it can tell), the rows read one column off shifted back (:data:`_SHIFTED`)."""
    year = raw["EVE_CENSAL"].replace(_YEAR_ALIASES)
    known = year.isin([str(y) for y in CENSUSES])
    stray = raw[~known]
    if (_rank(stray["TOT_HAB"]) >= 2).any():
        warnings.warn(f"AHL: {int((_rank(stray['TOT_HAB']) >= 2).sum())} population rows on "
                      f"no census year ({sorted(set(stray['EVE_CENSAL']))}) dropped",
                      stacklevel=3)
    df = raw.assign(EVE_CENSAL=year)[known]
    df = (df.assign(_rank=_rank(df["TOT_HAB"]), _order=range(len(df)))
          .sort_values(["CVE_GEOEST", "EVE_CENSAL", "_rank", "_order"],
                       ascending=[True, True, False, True])
          .drop_duplicates(["CVE_GEOEST", "EVE_CENSAL"]))
    return _unshift(df.drop(columns=["_rank", "_order"]))


_EVENT_RE = re.compile(r"^\s*(?:censo|conteo)(?:\s*del?)?\s*(?:edif\w*\s+(?:de\s+)?)?(\d{4})\b",
                       re.I)


def _census_events(mv: pd.DataFrame) -> pd.DataFrame:
    """Each record's census and count rows of ``Movimientos`` («Censo de 2010.», «Conteo
    de 1995.», «Censo de Edificios de 1939.»…): one per (locality, year), the last listed
    (``INDICE``) where INEGI has two, with the name, municipality and categories then."""
    year = mv["ORI_MODIF"].str.extract(_EVENT_RE, expand=False).replace(_YEAR_ALIASES)
    ev = mv.assign(EVE_CENSAL=year, _i=pd.to_numeric(mv["INDICE"]))
    ev = ev[ev["EVE_CENSAL"].isin([str(y) for y in CENSUSES])]
    ev = ev.sort_values("_i").drop_duplicates(["CVE_GEOEST", "EVE_CENSAL"], keep="last")
    return ev[["CVE_GEOEST", "EVE_CENSAL", "NOM_LOC", "NOM_MUN", "CAT_POLI", "CAT_ADMIVA"]]


def _clean(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    return s.where(s != "")


def _census_date(year: pd.Series) -> pd.Series:
    return pd.to_datetime(year.astype(int).map(lambda y: CENSUSES[y][1]))


# INEGI copies a census's row to a locality's new code since the Censo 2010. Before it,
# two codes of one locality with equal rows are mostly both in that census's ITER (a double
# registration INEGI merged later), so they are kept.
_COPIES_SINCE = 2010


def _copies(hab: pd.DataFrame, states: list[int], snapshot: str | None) -> pd.Series:
    """The rows INEGI copied to a locality's new code: a row of ``TO`` (a ``code`` link of
    the lineage) at a census from 2010 on before the link's date, equal in its three counts
    to the row of ``FROM`` at that census (``FROM``'s state is read when it is not
    loaded)."""
    from mxcensus.cpv_geo import _loc_lineage
    lin = _loc_lineage()
    links = lin.loc[(lin["KIND"] == "code") & lin["TO"].isin(hab["CVE_GEOEST"]),
                    ["FROM", "TO", "DATE"]]
    flag = pd.Series(False, index=hab.index)
    if links.empty:
        return flag
    cand = (hab.reset_index().rename(columns={"index": "_row"})
            .merge(links, left_on="CVE_GEOEST", right_on="TO"))
    cand = cand[(cand["EVE_CENSAL"].astype(int) >= _COPIES_SINCE)
                & (_census_date(cand["EVE_CENSAL"]) < cand["DATE"])]
    others = sorted({int(c[:2]) for c in cand["FROM"]} - set(states))
    source = hab if not others else pd.concat(
        [hab, _habitantes(_read("habitantes", others, snapshot))], ignore_index=True)
    source = source.loc[source["CVE_GEOEST"].isin(cand["FROM"]),
                        ["CVE_GEOEST", "EVE_CENSAL", *_COUNTS]]
    same = cand.merge(source, left_on=["FROM", "EVE_CENSAL"],
                      right_on=["CVE_GEOEST", "EVE_CENSAL"], suffixes=("", "_from"))
    equal = pd.Series(True, index=same.index)
    for c in _COUNTS:
        equal &= same[c].fillna("") == same[f"{c}_from"].fillna("")
    flag.loc[same.loc[equal, "_row"].unique()] = True
    return flag


def _split_code(code: pd.Series) -> dict[str, pd.Series]:
    return {"CVE_ENT": code.str[:2], "CVE_MUN": code.str[2:5], "CVE_LOC": code.str[5:9]}


def load_ahl_poblacion(*, state: int | Sequence[int], snapshot: str | None = None,
                       copies: bool = False) -> pd.DataFrame:
    """The population of every locality at every census and count 1900–2020 (a historical
    ITER), from INEGI's Archivo Histórico de Localidades.

    One row per locality (its **last** code) and census, indexed ``(CVE_ENT, CVE_MUN,
    CVE_LOC, EVE_CENSAL)`` (the census year: 1900, 1910, 1921, 1930, 1939 — the buildings
    census —, 1940 … 1990, 1995, 2000, 2005, 2010, 2020):

    - ``FUENTE`` — ``Censo``, ``Conteo`` (1995, 2005) or ``Censo de edificios`` (1939), by
      the year (INEGI's column contradicts it in 237 rows);
    - ``POBTOT``, ``POBMAS``, ``POBFEM`` — ``Int64``; missing where INEGI reserves the count
      (``*``: the localities of one or two dwellings — every count in the Conteo 1995, the
      sexes since 1990) or has none (``-``: mostly the sexes in 1970 and 1980). A locality
      listed uninhabited has 0;
    - ``NOM_LOC``, ``NOM_MUN``, ``CAT_POLI`` (political category), ``CAT_ADMIVA``
      (administrative category) — as its history records them at that census (missing for
      the ~1,000 rows whose history has no row for it).

    INEGI's defects are repaired: its «1920» rows are the 1921 census; 9 rows on no census
    year (all zero) are dropped; of two rows of one locality and year (31 pairs, mostly
    zeros) the one with more information is kept; 11 rows INEGI read one column off from
    the 1990–2000 ITERs are shifted back. Rows INEGI copied to a new code (module doc) are
    dropped; ``copies=True`` keeps them with a ``COPIA`` flag.
    """
    states = _require_states(state)
    hab = _habitantes(_read("habitantes", states, snapshot))
    flag = _copies(hab, states, snapshot)
    if not copies:
        hab, flag = hab[~flag], flag[~flag]
    ev = _census_events(_read("movimientos", states, snapshot))
    df = hab.assign(COPIA=flag).merge(ev, on=["CVE_GEOEST", "EVE_CENSAL"], how="left")
    year = df["EVE_CENSAL"].astype(int)
    out = pd.DataFrame({
        **_split_code(df["CVE_GEOEST"]),
        "EVE_CENSAL": year,
        "FUENTE": pd.Categorical(year.map(lambda y: CENSUSES[y][0]), categories=FUENTES),
        **{new: _count(df[old], old) for old, new in _COUNTS.items()},
        **{c: _clean(df[c]) for c in ("NOM_LOC", "NOM_MUN", "CAT_POLI", "CAT_ADMIVA")},
    })
    if copies:
        out["COPIA"] = df["COPIA"].to_numpy(bool)
    return out.set_index([*_INDEX, "EVE_CENSAL"]).sort_index()


# --------------------------------------------------------------------------- localities

_DMS_RE = re.compile(
    r"^\s*(\d{1,3})\s*°\s*(\d{1,2})[^\d]+(\d+(?:\.\d+)?)[^\dNSEWO]*([NSEWO])?\s*$")
# Mexico lies in 14–33° N, 86–119° W: a coordinate outside is missing.
_BOUNDS = {"LATITUD": (14.0, 33.0), "LONGITUD": (-119.0, -86.0)}


def _degrees(s: pd.Series, name: str) -> pd.Series:
    """INEGI's ``21°52'47.362"N`` as decimal degrees (``Float64``): west and south
    negative (``O`` = oeste), a missing hemisphere taken as N/W, minutes or seconds of 60
    or more and values outside Mexico missing."""
    parts = s.str.extract(_DMS_RE)
    d, m, sec = (pd.to_numeric(parts[i]) for i in range(3))
    value = d + m / 60 + sec / 3600
    hemi = parts[3].fillna("N" if name == "LATITUD" else "W")
    value = value.where(~hemi.isin(["S", "W", "O"]), -value)
    lo, hi = _BOUNDS[name]
    ok = (m < 60) & (sec < 60) & value.between(lo, hi)
    return value.where(ok).astype("Float64")


def _carta(s: pd.Series) -> pd.Series:
    """The 1:50,000 sheet (``F13D19``): spaces, tabs, hyphens and stray marks dropped,
    upper case; anything else (``null``, ``0``, six digits) missing."""
    c = s.str.upper().str.replace(r"[\s\-|]", "", regex=True)
    return c.where(c.str.fullmatch(r"[A-Z]\d{2}[A-Z]\d{2}").fillna(False))


def load_ahl_localidades(*, state: int | Sequence[int], snapshot: str | None = None,
                         geometry: bool = False):
    """Every locality of INEGI's Archivo Histórico de Localidades, one row per record (its
    last code), indexed ``(CVE_ENT, CVE_MUN, CVE_LOC)``: ``NOM_ENT``, ``NOM_MUN`` (its
    present state and municipality), ``NOM_LOC``, ``CAT_POLI``, ``CAT_ADMIVA`` (its last
    name and categories in its history), ``AMBITO`` (``Rural``/``Urbana``, the Marco
    Geoestadístico's labels of INEGI's R/U), ``LATITUD``/``LONGITUD`` (decimal degrees,
    ``Float64``; 14% of the records have none, 49 malformed ones are missing),
    ``ALTITUD`` (metres, ``Int64``, as published) and ``CARTA_TOPO`` (the 1:50,000 sheet).

    The records include the localities dropped since (uninhabited, absorbed): their
    population history is in :func:`load_ahl_poblacion`. ``geometry=True`` returns a
    ``GeoDataFrame`` of points in EPSG:4326 (missing where the coordinates are).
    """
    states = _require_states(state)
    m = _read("maestro", states, snapshot)
    mv = _read("movimientos", states, snapshot)
    last = (mv.assign(_i=pd.to_numeric(mv["INDICE"])).sort_values("_i")
            .drop_duplicates("CVE_GEOEST", keep="last").set_index("CVE_GEOEST"))
    code = m["CVE_GEOEST"]
    out = pd.DataFrame({
        **_split_code(code),
        "NOM_ENT": _clean(m["NOMBRE_EDO"]),
        "NOM_MUN": _clean(m["NOMBRE_MUN"]),
        **{c: _clean(code.map(last[c])) for c in ("NOM_LOC", "CAT_POLI", "CAT_ADMIVA")},
        "AMBITO": pd.Categorical(m["TIPO"].map({"R": "Rural", "U": "Urbana"}),
                                 categories=["Rural", "Urbana"]),
        "LATITUD": _degrees(m["LATITUD"], "LATITUD"),
        "LONGITUD": _degrees(m["LONGITUD"], "LONGITUD"),
        "ALTITUD": pd.to_numeric(_clean(m["ALTITUD"])).astype("Int64"),
        "CARTA_TOPO": _carta(m["CARTA_TOPO"]),
    }).set_index(_INDEX).sort_index()
    if not geometry:
        return out
    import geopandas as gpd
    points = gpd.GeoSeries.from_xy(out["LONGITUD"].astype(float), out["LATITUD"].astype(float),
                                   index=out.index, crs="EPSG:4326")
    known = out["LATITUD"].notna() & out["LONGITUD"].notna()
    return gpd.GeoDataFrame(out, geometry=points.where(known, None), crs="EPSG:4326")
