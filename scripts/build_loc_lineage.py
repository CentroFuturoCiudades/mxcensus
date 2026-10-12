"""Build the cross-edition locality lineage from INEGI's Archivo Histórico de Localidades
(maintainer-only).

Writes ``src/mxcensus/_yaml/cpv_loc_lineage.csv.gz``: every documented link between two
locality codes (9 characters: entity + municipality + locality) that takes effect at a CPV
edition from 1990 on — the same locality under a new code, a locality absorbed by another,
a locality counted with another at one census, a locality separated from another. Read by
``mxcensus.cpv_geo``.

**Source.** INEGI's *Archivo Histórico de Localidades* (AHL,
https://www.inegi.org.mx/app/geo2/ahl/) publishes, per state and nationally, a ZIP of four
CSVs (``AHL{NN}Maestro``/``Habitantes``/``Movimientos``/``Res_hist``). ``Movimientos`` holds
every locality's history, one row per event (a census or count, a geostatistical update, a
decree), under the locality's last code, with what changed in free text (``ORI_MODIF``):
«Pasa al municipio de X (012) con clave de localidad (0034).», «A esta localidad se conurba
la 010012150.», «Hasta este evento estuvo registrada con clave 230060044.». The download is
a POST to ``…/ahl/descarga`` (``clave=00&tipo=N``), cached in ``data/dict/ahl/AHL.zip``.

**Links.** Each statement gives a link ``FROM`` → ``TO`` of one ``KIND``:

- ``code`` — the same locality under another code: a move to another municipality or state
  («Pasa al municipio … con clave …» on the old record, «Viene del municipio … con clave …»
  on the new one; a move stated without the code on both records is paired by the
  locality's name), a renumbering inside a record («Hasta este evento estuvo registrada con
  clave Y» … «A partir de este evento cambia a la clave X»), a duplicate registration («Es
  la misma localidad (LLLL) del municipio (MMM)», «Misma que la localidad …»: the duplicate
  is ``FROM``);
- ``absorption`` — ``FROM`` joins ``TO`` («Se conurba a / Se fusiona a …» on the absorbed
  record, «A esta localidad se conurba(n) / fusiona(n) / integra(n) …» on the other);
- ``counted_with`` — ``FROM`` was counted with ``TO`` at that census only («Se censó con la
  localidad …»);
- ``separation`` — ``FROM`` leaves ``TO`` («Se desconurba / Se desfusiona / Se desagrega de
  …», «De esta localidad se desconurba(n) / desfusiona(n) …»).

A locality number stated with a name but no municipality («Se conurba a Playas de Rosarito
(0001)») is placed by that name (``Resolver``): the stating record's municipality is wrong
when the other locality lies in another. Rival claims on one locality at one edition (two
absorbers, two new codes: INEGI lists some twice) keep the one stated on both records; with
none, a name-verified one, one stated on the locality's own record (``lineage``).

**Editions.** A link is dated by its event: a census or count row by that census's
reference date, an update by its date, a decree by the first date in its text. ``PERIOD``
is the first edition whose **cut** is on or after that date. The cut is the last change an
edition's locality codes reflect, found on the data (``check``; STEP_7t.md): the census day
for 1990, 1995 and 2000, INEGI's geostatistical update of 30 October 2005 for the Conteo
2005, that of 15 October 2010 for the Censo 2010, every change of 2020 for the Censo 2020
(its ITER and MG frame), every change up to 30 November 2025 for the MG 2025 frame. Links in
effect by 1990 are dropped, except those counted with another locality at the 1990 census. A
link stated on both records is ``CONFIRMED``.

Usage::

    .venv/bin/python scripts/build_loc_lineage.py              # download (once) + build
    .venv/bin/python scripts/build_loc_lineage.py --download   # refresh data/dict/ahl/AHL.zip
    .venv/bin/python scripts/build_loc_lineage.py --check      # + the check against the
                                                               #   ITER and MG 2025 → report
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ZIP = _REPO_ROOT / "data" / "dict" / "ahl" / "AHL.zip"
_DEFAULT_OUTPUT = _REPO_ROOT / "src" / "mxcensus" / "_yaml" / "cpv_loc_lineage.csv.gz"
_DEFAULT_MIRROR = _REPO_ROOT / "data" / "parquet"
_DEFAULT_REPORT = _REPO_ROOT / "docs" / "cpv" / "LOC_LINEAGE_REPORT.md"
_AHL_URL = "https://www.inegi.org.mx/app/geo2/ahl/descarga"

# Reference dates of the censuses and counts (a row «Censo de 2010.» is dated so).
CENSUS_DATES: dict[str, date] = {
    "1990": date(1990, 3, 12), "1995": date(1995, 11, 5), "2000": date(2000, 2, 14),
    "2005": date(2005, 10, 17), "2010": date(2010, 6, 12), "2020": date(2020, 3, 15),
}
# Each edition's cut: the last change its locality codes reflect (module doc).
EDITIONS: dict[str, date] = {
    "1990": date(1990, 3, 12), "1995": date(1995, 11, 5), "2000": date(2000, 2, 14),
    "2005": date(2005, 10, 30), "2010": date(2010, 10, 15), "2020": date(2020, 12, 31),
    "2025": date(2025, 12, 31),
}
_MESES = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
    "diciembre".split())}
KINDS = ("code", "absorption", "counted_with", "separation")


# --------------------------------------------------------------------------- reading

def download(path: Path) -> Path:
    """Fetch the national AHL ZIP into ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.parse.urlencode({"clave": "00", "tipo": "N"}).encode()
    with urllib.request.urlopen(urllib.request.Request(_AHL_URL, data=data), timeout=600) as r:
        body = r.read()
    if not body.startswith(b"PK"):
        raise SystemExit(f"{_AHL_URL}: not a ZIP ({len(body)} bytes)")
    path.write_bytes(body)
    return path


def read_ahl(path: Path, kind: str) -> pd.DataFrame:
    """One AHL table (``Maestro``, ``Habitantes``, ``Movimientos``, ``Res_hist``) of every
    state, all columns strings, from the national ZIP of per-state ZIPs (ISO-8859-1)."""
    frames = []
    with zipfile.ZipFile(path) as outer:
        for name in sorted(n for n in outer.namelist() if re.fullmatch(r"AHL\d\d\.zip", n)):
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                member = f"{name[:5]}{kind}.csv"
                frames.append(pd.read_csv(io.BytesIO(inner.read(member)), dtype=str,
                                          encoding="latin-1", keep_default_na=False))
    if len(frames) != 32:
        raise SystemExit(f"{path}: {len(frames)} state ZIPs, expected 32")
    return pd.concat(frames, ignore_index=True)


def ahl_date(path: Path) -> date:
    """The AHL export's date (its members' newest timestamp): no event is later."""
    with zipfile.ZipFile(path) as z:
        return max(date(*i.date_time[:3]) for i in z.infolist())


# --------------------------------------------------------------------------- events

_CENSUS_RE = re.compile(r"\s*(censo|conteo)(?: de)? (\d{4})\b", re.I)
_UPDATE_RE = re.compile(r"\s*actualizaci[oó]n geo\w*", re.I)
_DATE_RE = re.compile(r"(\d{1,2})(?:o|º)? de (" + "|".join(_MESES) + r") (?:de |del )?(\d{4})",
                      re.I)
_YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-4]\d)\b")


def event(text: str) -> tuple[str, date | None]:
    """A history row's event kind (``census``, ``update``, ``other``) and date: a census or
    count → its reference date (1 January of other years); else the first «D de mes de
    AAAA» in the text, else 1 January of its first year; ``None`` without any year."""
    m = _CENSUS_RE.match(text)
    if m:
        year = m.group(2)
        return "census", CENSUS_DATES.get(year, date(int(year), 1, 1))
    kind = "update" if _UPDATE_RE.match(text) else "other"
    m = _DATE_RE.search(text)
    if m:
        year, month = int(m.group(3)), _MESES[m.group(2).lower()]
        try:
            return kind, date(year, month, int(m.group(1)))
        except ValueError:                       # «31 de junio»: the month's last day
            return kind, date(year, month, 28)
    m = _YEAR_RE.search(text)
    return kind, (date(int(m.group(1)), 1, 1) if m else None)


def edition_of(day: date) -> str | None:
    """The first edition whose cut is on or after ``day`` (``None`` after the last)."""
    for period, cut in EDITIONS.items():
        if day <= cut:
            return period
    return None


# --------------------------------------------------------------------------- statements

# A name: up to 90 characters, parentheses allowed only around words («Acatepec (San
# Antonio)»), so a name never runs past a code in parentheses.
_N = r"(?:[^()]|\([^()]*[^()\d\s][^()]*\)){0,90}?"
_MUN = r"\(?\s*\b(\d{3})\b\s*\)?"
_KEY = (r"\.?,? (?:con|y) (?:la )?clave(?: de(?: la)? localidad| geoestad[ií]stica)? "
        r"\(?\s*\b(\d{9}|\d{4})\b\s*\)?")
_NO_KEY = r"(?![\s)]*\.?,? (?:con|y) (?:la )?clave)"
_LIST = r"((?:\(?\d{9}\)?(?:\s*,\s*|\s+y\s+|\s+e\s+)?)+)"
_ART = r"(?:la |las |los |el )?(?:localidad(?:es)? )?(?:de )?"
_HERE = r"a est[aá] localidad (?:se|de) (?:le )?"          # «A esta localidad se (le) …»
_FROM_HERE = r"de est[aá] localidad (?:se|de) "

_PATTERNS: list[tuple[str, re.Pattern]] = [(name, re.compile(rx, re.I)) for name, rx in (
    # the same locality under another code
    ("pasa_estado", r"pasa al estado (?:de )?" + _N + r"\((\d{2})\),? (?:en el|al|del) municipio "
                    r"(?:de )?" + _N + _MUN + _KEY),
    ("viene_estado", r"viene del estado (?:de )?" + _N + r"\((\d{2})\),? (?:del|en el|al) "
                     r"municipio (?:de )?" + _N + _MUN + _KEY),
    ("viene_estado", r"viene del Distrito Federal \((09)\),? delegaci[oó]n " + _N
                     + r"\(\s*(\d{2,3})\s*\)" + _KEY),
    ("pasa", r"pasa (?:al mun[i]?cipio|a la delegaci[oó]n) (?:de )?" + _N + _MUN + _KEY),
    ("viene", r"viene (?:del? mun[i]?cipio|de la delegaci[oó]n) (?:de )?" + _N + _MUN + _KEY),
    ("pasa_sin", r"pasa al municipio (?:de )?(" + _N + r")\s*" + _MUN + _NO_KEY),
    ("viene_sin", r"viene del municipio (?:de )?(" + _N + r")\s*" + _MUN + _NO_KEY),
    ("cambia", r"(?:cambi[aó] (?:a )?la clave|se registra con (?:la )?clave)"
               r"(?: de localidad)? \(?(\d{9}|\d{4})\b\)?"),
    ("hasta", r"hasta este evento (?:la localidad )?estuvo registrada con (?:la )?"
              r"clave(?: de localidad)? \(?(\d{9}|\d{4})\b\)?"),
    ("antes", r"antes era la (?:localidad )?\(?(\d{9})\)?"),
    ("misma", r"es la misma localidad \((\d{4})\) del municipio \((\d{3})\)"),
    ("misma_que", r"misma que la localidad " + _N + r"\(?(\d{9})\)?"),
    # absorptions, counted with, separations
    ("absorbida", r"(?:se (?:conurba|fusiona)|(?:localidad )?(?:conurbada|fusionada)) "
                  r"(?:a|al|con) " + _ART + r"(?:(\d{9})|" + _N + r",? (?:con )?(?:la )?clave "
                  r"\(?(\d{9})\)?|(" + _N + r")\s*\((\d{4})\)(?:,? del municipio (?:de )?"
                  + _N + _MUN + r")?)"),
    ("absorbe", _HERE + r"(?:conurba|fusiona|integra)n? (?:parte de )?" + _ART + _LIST),
    ("censo_con", r"(?:se )?cens[oó] con " + _ART + r"(" + _N + r")\s*\((\d{4})\)"),
    ("separada", r"(?:se des(?:conurba|fusiona)n?|se desagrega|localidad desagregada) de "
                 + _ART + r"(?:(\d{9})|(" + _N + r")\s*\((\d{4})\)(?:,? del municipio "
                 r"(?:de )?" + _N + _MUN + r")?)"),
    ("separa", r"(?:" + _FROM_HERE + r"|" + _HERE + r")de(?:s)?(?:conurba|fusiona)n? "
               + _ART + _LIST),
)]


@dataclass
class Row:
    code: str
    indice: int
    name: str
    text: str
    kind: str
    day: date | None
    found: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)


def statements(text: str) -> dict[str, list[tuple[str, ...]]]:
    """Every pattern's matches in one history text (groups as strings, '' when absent)."""
    out = {}
    for name, rx in _PATTERNS:
        hits = [tuple(g or "" for g in m.groups()) for m in rx.finditer(text)]
        if hits:
            out[name] = hits
    return out


@dataclass(frozen=True)
class Link:
    source: str      # FROM
    target: str      # TO
    kind: str        # one of KINDS
    day: date | None
    event: str
    record: str      # the AHL record that states it
    verified: bool = True    # False: a locality number placed without its name matching


def _expand(x: str, ent: str, mun: str) -> str:
    return x if len(x) == 9 else ent + mun + x


_GENERIC = {"la", "el", "los", "las", "de", "del", "y", "cab", "san", "santa", "rancho",
            "colonia", "ejido", "localidad"}


def _tokens(name: str) -> set[str]:
    return set(_norm_name(name).split()) - _GENERIC


def name_match(a: str, b: str) -> int:
    """How well two locality names match once normalized (accents, case, punctuation): 3
    equal, 2 equal without generic words («El», «Rancho», «(Cab.)»…), 1 one inside the other
    or sharing at least half their distinctive words, 0 not."""
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return 0
    if na == nb:
        return 3
    ta, tb = _tokens(a), _tokens(b)
    if ta and ta == tb:
        return 2
    if f" {na} " in f" {nb} " or f" {nb} " in f" {na} ":
        return 1
    return int(bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.5)


class Resolver:
    """A locality number (4 digits) stated with a name, without its municipality: among
    the state's localities with that number, the one whose names in the AHL match the name
    best (``name_match``), the stating record's municipality on a tie with it; the record's
    municipality when none matches or several tie (counted as unverified)."""

    def __init__(self, rows: list[Row]):
        self.names: dict[str, set[str]] = {}
        for r in rows:
            self.names.setdefault(r.code, set()).add(r.name)
        self.by_number: dict[tuple[str, str], list[str]] = {}
        for c in self.names:
            self.by_number.setdefault((c[:2], c[5:]), []).append(c)
        self.counts = Counter()

    def __call__(self, ent: str, mun: str, loc: str, name: str,
                 stated_mun: str = "") -> tuple[str, bool]:
        """The code and whether its name matched."""
        if stated_mun:
            return ent + stated_mun + loc, True
        own = ent + mun + loc
        if not name.strip():
            self.counts["unverified"] += 1
            return own, False
        score = {c: max((name_match(name, n) for n in self.names[c]), default=0)
                 for c in self.by_number.get((ent, loc), [])}
        best = max(score.values(), default=0)
        top = [c for c, v in score.items() if v == best]
        if best and score.get(own, 0) == best:
            self.counts["own municipality"] += 1
            return own, True
        if best and len(top) == 1:
            self.counts["other municipality"] += 1
            return top[0], True
        self.counts["unverified"] += 1
        return own, False


def record_links(rows: list[Row], resolve: Resolver | None = None) -> list[Link]:
    """The links one AHL record states (its rows in ``INDICE`` order); ``resolve`` places
    a locality number stated with a name (the record's municipality without one)."""
    links: list[Link] = []
    code = rows[0].code
    ent, mun = code[:2], code[2:5]
    if resolve is None:
        def resolve(e, m, loc, name, stated=""):
            return e + (stated or m) + loc, True

    def add(src, dst, kind, r, verified=True):
        if isinstance(dst, tuple):
            dst, verified = dst
        if src != dst:
            links.append(Link(src, dst, kind, r.day, r.kind, code, verified))

    # renumbering inside the record: "hasta" closes a code, "cambia" opens one
    current, pending, pending_row = None, None, None
    for i, r in enumerate(rows):
        f = r.found
        if pending is not None and "cambia" not in f and i > pending_row:
            # the row after a closed code opens the next one: the next "hasta" code or the
            # record's own; a later "cambia" names it instead (and dates the change)
            nxt, deferred = None, False
            for later in rows[i:]:
                if "cambia" in later.found:
                    deferred = True
                    break
                if "hasta" in later.found:
                    nxt = _expand(later.found["hasta"][0][0], ent, mun)
                    break
            if not deferred:
                nxt = nxt or code
                add(pending, nxt, "code", r)
                current, pending = nxt, None
        for (x,) in f.get("cambia", []):
            new = _expand(x, ent, mun)
            old = pending or current
            if old:
                add(old, new, "code", r)
            current, pending = new, None
        for (y,) in f.get("hasta", []):
            pending, pending_row, current = _expand(y, ent, mun), i, None

    for r in rows:
        f = r.found
        for e, m, loc in f.get("pasa_estado", []):
            add(code, _expand(loc, e, m), "code", r)
        for e, m, loc in f.get("viene_estado", []):
            add(_expand(loc, e, m.zfill(3)), code, "code", r)
        for m, loc in f.get("pasa", []):
            add(code, _expand(loc, ent, m), "code", r)
        for m, loc in f.get("viene", []):
            add(_expand(loc, ent, m), code, "code", r)
        for loc, m in f.get("misma", []):
            add(code, ent + m + loc, "code", r)
        for (x,) in f.get("misma_que", []):
            add(code, x, "code", r)
        for (x,) in f.get("antes", []):
            add(x, code, "code", r)
        for full, full2, name, loc, m in f.get("absorbida", []):
            add(code, full or full2 or resolve(ent, mun, loc, name, m), "absorption", r)
        for (lst,) in f.get("absorbe", []):
            for x in re.findall(r"\d{9}", lst):
                add(x, code, "absorption", r)
        for name, loc in f.get("censo_con", []):
            add(code, resolve(ent, mun, loc, name), "counted_with", r)
        for full, name, loc, m in f.get("separada", []):
            add(code, full or resolve(ent, mun, loc, name, m), "separation", r)
        for (lst,) in f.get("separa", []):
            for x in re.findall(r"\d{9}", lst):
                add(x, code, "separation", r)
    return links


def parse(mov: pd.DataFrame) -> tuple[list[Row], list[Link], Counter]:
    """Every history row (event, statements), every link the records state, and how the
    locality numbers stated with a name were placed (``Resolver``)."""
    mov = mov.assign(I=mov["INDICE"].astype(int)).sort_values(["CVE_GEOEST", "I"])
    rows = []
    for code, i, name, text in zip(mov["CVE_GEOEST"], mov["I"], mov["NOM_LOC"],
                                   mov["ORI_MODIF"]):
        text = re.sub(r"\s+", " ", text).strip()
        kind, day = event(text)
        rows.append(Row(code, i, name, text, kind, day, statements(text)))
    resolve = Resolver(rows)
    links: list[Link] = []
    start = 0
    for end in range(1, len(rows) + 1):
        if end == len(rows) or rows[end].code != rows[start].code:
            links.extend(record_links(rows[start:end], resolve))
            start = end
    return rows, links, resolve.counts


def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _in_scope(day: date | None, kind: str, latest: date) -> bool:
    """A link takes effect after 1990 (counted with another locality: at 1990 or later)
    and by the last cut; a date after the export is a typo (dropped)."""
    if day is None or day > latest or edition_of(day) is None:
        return False
    return day > EDITIONS["1990"] or (kind == "counted_with" and day >= CENSUS_DATES["1990"])


def pair_unkeyed(rows: list[Row], links: list[Link], latest: date) -> tuple[list[Link], int]:
    """Moves stated without the new or old code on both records («Pasa al municipio X
    (MMM).» on the old one, «Viene del municipio Y (NNN).» on the new one), where no record
    gives the code: paired when exactly one record on each side has the locality's name
    in that pair of municipalities at that edition. Returns the links and the number of
    such statements left unpaired."""
    coded_src = {l.source for l in links if l.kind == "code"}
    coded_dst = {l.target for l in links if l.kind == "code"}
    out, gone, come = [], {}, {}
    for r in rows:
        if not _in_scope(r.day, "code", latest):
            continue
        period = edition_of(r.day)
        for _, m in r.found.get("pasa_sin", []):
            if r.code not in coded_src:
                key = (r.code[:5], r.code[:2] + m, period, _norm_name(r.name))
                gone.setdefault(key, []).append(r)
        for _, m in r.found.get("viene_sin", []):
            if r.code not in coded_dst:
                key = (r.code[:2] + m, r.code[:5], period, _norm_name(r.name))
                come.setdefault(key, []).append(r)
    paired = set()
    for key, olds in gone.items():
        news = come.get(key, [])
        if len({r.code for r in olds}) == 1 and len({r.code for r in news}) == 1:
            o, n = olds[0], news[0]
            out.append(Link(o.code, n.code, "code", o.day, o.kind, o.code))
            out.append(Link(o.code, n.code, "code", n.day, n.kind, n.code))
            paired.add(key)
    left = sum(len(v) for k, v in gone.items() if k not in paired) + sum(
        len(v) for k, v in come.items() if k not in paired)
    return out, left


def lineage(rows: list[Row], links: list[Link], latest: date) -> pd.DataFrame:
    """The links in scope, one per (``FROM``, ``TO``, ``KIND``, ``PERIOD``): ``DATE`` the
    earliest statement's, ``CONFIRMED`` when both records state it. Rival claims on one
    locality at one edition (two absorbers, two new codes) keep the confirmed one; with none
    confirmed, an absorption, separation or count whose locality number matched its name
    beats one that did not, one stated on the locality's own record beats those stated only
    on others, and a new code with the locality's own name beats others."""
    df = pd.DataFrame([l.__dict__ for l in links])
    df = df[[_in_scope(d, k, latest) for d, k in zip(df["day"], df["kind"])]].copy()
    df["PERIOD"] = df["day"].map(edition_of)
    df["side"] = ["from" if rec == s else "to" if rec == t else "other"
                  for rec, s, t in zip(df["record"], df["source"], df["target"])]
    df = df.sort_values("day")
    out = (df.groupby(["source", "target", "kind", "PERIOD"], sort=False)
             .agg(DATE=("day", "first"), EVENT=("event", "first"),
                  sides=("side", lambda s: frozenset(s)), verified=("verified", "max"))
             .reset_index())
    out["CONFIRMED"] = [{"from", "to"} <= s for s in out["sides"]]
    # a locality that two records claim at one edition (absorbed by both, renumbered to
    # both): when exactly one claim is stated on both records, the others are dropped
    group = out.groupby(["source", "kind", "PERIOD"])["CONFIRMED"]
    n_to, n_conf = group.transform("size"), group.transform("sum")
    out = out[(n_to == 1) | (n_conf != 1) | out["CONFIRMED"]]
    names: dict[str, set[str]] = {}
    for r in rows:
        names.setdefault(r.code, set()).add(r.name)
    out["named"] = [out_kind == "code" and any(name_match(a, b) for a in names.get(src, ())
                                               for b in names.get(dst, ()))
                    for out_kind, src, dst in zip(out["kind"], out["source"], out["target"])]
    group = out.groupby(["source", "kind", "PERIOD"])
    rival = (group["CONFIRMED"].transform("size") > 1) & (group["CONFIRMED"].transform("sum") == 0)
    own = pd.Series(["from" in x for x in out["sides"]], index=out.index) & out["verified"]
    out["own"] = own
    group = out.groupby(["source", "kind", "PERIOD"])
    beats = (out["kind"] != "code") & group["verified"].transform("max") & ~out["verified"]
    beats |= (out["kind"] != "code") & group["own"].transform("max") & ~out["own"]
    beats |= (out["kind"] == "code") & group["named"].transform("max") & ~out["named"]
    out = out[~(rival & beats)]
    out = out.rename(columns={"source": "FROM", "target": "TO", "kind": "KIND"})
    out = out[["PERIOD", "DATE", "EVENT", "KIND", "FROM", "TO", "CONFIRMED"]]
    out["KIND"] = pd.Categorical(out["KIND"], KINDS)
    return out.sort_values(["PERIOD", "KIND", "FROM", "TO"]).reset_index(drop=True)


def build(path: Path) -> tuple[pd.DataFrame, list[Row], dict]:
    """The lineage table, the history rows and the build's counts."""
    latest = ahl_date(path)
    rows, links, placed = parse(read_ahl(path, "Movimientos"))
    extra, unpaired = pair_unkeyed(rows, links, latest)
    table = lineage(rows, links + extra, latest)
    stats = {"rows": len(rows), "records": len({r.code for r in rows}),
             "statements": len(links), "paired_unkeyed": len(extra) // 2,
             "unpaired_unkeyed": unpaired, "latest": latest,
             "undated": sum(1 for l in links if l.day is None),
             "after_export": sum(1 for l in links if l.day and l.day > latest),
             "placed": dict(placed)}
    return table, rows, stats


_HEADER = """\
# Locality lineage across the CPV editions (1990-2025). Generated by
# scripts/build_loc_lineage.py from INEGI's Archivo Histórico de Localidades; do not edit by
# hand. One row per link between two locality codes (entity + municipality + locality) that
# takes effect at PERIOD (the first edition whose locality codes reflect it): KIND code = the
# same locality under another code, absorption = FROM joins TO, counted_with = FROM counted
# with TO at that census only, separation = FROM leaves TO. DATE = the event's date,
# CONFIRMED = stated on both localities' records. Read by mxcensus.cpv_geo.
"""


def write(table: pd.DataFrame, path: Path) -> None:
    """The bundled table: a gzipped CSV with a commented header, reproducible bytes."""
    import gzip
    body = table.assign(DATE=table["DATE"].map(date.isoformat),
                        CONFIRMED=table["CONFIRMED"].map({True: "1", False: "0"})
                        ).to_csv(index=False, lineterminator="\n")
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0,
                                              filename="") as gz:
        gz.write((_HEADER + body).encode("utf-8"))


# --------------------------------------------------------------------------- check

_ITER_EDITIONS = ("1990", "1995", "2000", "2005", "2010", "2020")


def edition_codes(mirror: Path) -> dict[str, set[str]]:
    """The locality codes of each ITER (its locality rows) and of the MG 2025 frame (its
    ``l`` and ``lpr`` layers), from the mirror; an edition with a file missing is left out."""
    import pyarrow.parquet as pq
    out: dict[str, set[str]] = {}
    for period in _ITER_EDITIONS:
        files = [mirror / f"cpv_iter_{period}_{s:02d}.parquet" for s in range(1, 33)]
        if not all(f.exists() for f in files):
            print(f"  ITER {period}: files missing in {mirror}, left out", flush=True)
            continue
        codes = set()
        for f in files:
            cols = {c.upper(): c for c in pq.read_schema(f).names}
            t = pq.read_table(f, columns=[cols["ENTIDAD"], cols["MUN"], cols["LOC"]]
                              ).to_pandas()
            t.columns = ["E", "M", "L"]
            t = t[(t.M.str.zfill(3) != "000") & ~t.L.str.zfill(4).isin(["0000", "9998", "9999"])]
            codes |= set(t.E.str.zfill(2) + t.M.str.zfill(3) + t.L.str.zfill(4))
        out[period] = codes
    files = [mirror / f"mg_{sfx}_2025_{s:02d}.parquet" for sfx in ("l", "lpr")
             for s in range(1, 33)]
    if all(f.exists() for f in files):
        out["2025"] = set()
        for f in files:
            t = pq.read_table(f, columns=["CVEGEO"]).to_pandas()
            out["2025"] |= set(t.CVEGEO.str[:9])
    else:
        print(f"  MG 2025: files missing in {mirror}, left out", flush=True)
    files = [mirror / f"mg_{sfx}_{s:02d}.parquet" for sfx in ("l", "lpr") for s in range(1, 33)]
    if all(f.exists() for f in files):          # MG 2020: 9 characters (lpr: + a point id)
        out["2020mg"] = set()
        for f in files:
            t = pq.read_table(f, columns=["CVEGEO"]).to_pandas()
            out["2020mg"] |= set(t.CVEGEO.str[:9])
    return out


def _status(rows: list[Row]) -> tuple[dict[tuple[str, str], set[str]], dict[str, str]]:
    """Per (record, edition) the AHL's words for its rows in that edition's span, and each
    record's first edition."""
    flags: dict[tuple[str, str], set[str]] = {}
    first: dict[str, str] = {}
    for r in rows:
        if r.day is None:
            continue
        period = edition_of(r.day)
        if period is None:
            continue
        first.setdefault(r.code, period if r.day > date(1985, 1, 1) else "before")
        t = r.text.lower()
        f = flags.setdefault((r.code, period), set())
        if "baja" in t:
            f.add("removed")
        if "deshabitada" in t:
            f.add("uninhabited")
        if "reactiva" in t:
            f.add("reactivated")
        if re.search(r"creaci[oó]n de localidad|alta de localidad", t):
            f.add("created")
        if re.search(r"(una|dos) viviendas?", t):
            f.add("1-2 dwellings")
        if "sin informaci" in t or "no hubo acceso" in t:
            f.add("no information")
    return flags, first


def _spans(codes: dict[str, set[str]]) -> list[tuple[str, str, set[str], set[str]]]:
    """Consecutive editions to compare: the ITERs, then the MG 2020 frame against the MG 2025
    frame (both list the uninhabited localities too)."""
    eds = [p for p in _ITER_EDITIONS if p in codes]
    out = [(a, b, codes[a], codes[b]) for a, b in zip(eds[:-1], eds[1:])]
    if "2020mg" in codes and "2025" in codes:
        out.append(("2020", "2025", codes["2020mg"], codes["2025"]))
    return out


_GONE = ("link", "removed", "uninhabited", "was uninhabited", "1-2 dwellings",
         "no information", "not in the AHL", "unexplained")
_NEW = ("link", "new record", "created", "reactivated", "was empty", "no information",
        "not in the AHL", "unexplained")


def check(table: pd.DataFrame, rows: list[Row], codes: dict[str, set[str]]) -> dict:
    """The lineage against each edition's codes: (a) a ``code`` or ``absorption`` link whose
    ``FROM`` is still there at its edition, or a ``separation`` whose ``FROM`` was there
    before but not at its edition, is contradicted; (b) every code that leaves or enters
    between two consecutive editions, by what explains it (``unexplained`` lists the rest)."""
    flags, first = _status(rows)
    contra, explained, unexplained = [], [], {}
    for a, b, A, B in _spans(codes):
        span = table[table.PERIOD.map(lambda p: a < p <= b)]
        for kind in ("code", "absorption", "separation"):
            s = span[span.KIND == kind]
            bad = (s[~s.FROM.isin(B) & s.FROM.isin(A)] if kind == "separation"
                   else s[s.FROM.isin(B)])
            contra.append({"span": f"{a}→{b}", "kind": kind, "links": len(s),
                           "contradicted": len(bad),
                           "of them confirmed": int(bad.CONFIRMED.sum()),
                           "examples": " ".join((bad.FROM + "→" + bad.TO).head(4))})
        moved = (set(span[span.KIND.isin(["code", "absorption"])].FROM)
                 | set(table[(table.KIND == "counted_with") & (table.PERIOD == b)].FROM))
        arrived = (set(span[span.KIND == "code"].TO) | set(span[span.KIND == "separation"].FROM)
                   | set(table[(table.KIND == "counted_with") & (table.PERIOD == a)].FROM))
        why_gone, why_new = Counter(), Counter()
        for c in sorted(A - B):
            fa, fb = flags.get((c, a), set()), flags.get((c, b), set())
            why = ("link" if c in moved else "removed" if "removed" in fa | fb else
                   "uninhabited" if "uninhabited" in fb else
                   "was uninhabited" if "uninhabited" in fa else
                   "1-2 dwellings" if "1-2 dwellings" in fb else
                   "no information" if "no information" in fb else
                   "not in the AHL" if c not in first else "unexplained")
            why_gone[why] += 1
            if why == "unexplained":
                unexplained.setdefault(f"{a}→{b} gone", []).append(c)
        for c in sorted(B - A):
            fa, fb = flags.get((c, a), set()), flags.get((c, b), set())
            why = ("link" if c in arrived else
                   "new record" if first.get(c) == b else
                   "created" if "created" in fa | fb else
                   "reactivated" if "reactivated" in fa | fb else
                   "was empty" if fa & {"uninhabited", "removed"} else
                   "no information" if "no information" in fa else
                   "not in the AHL" if c not in first else "unexplained")
            why_new[why] += 1
            if why == "unexplained":
                unexplained.setdefault(f"{a}→{b} new", []).append(c)
        explained.append(("gone", {"span": f"{a}→{b}", "codes": len(A - B),
                                   **{k: why_gone[k] for k in _GONE}}))
        explained.append(("new", {"span": f"{a}→{b}", "codes": len(B - A),
                                  **{k: why_new[k] for k in _NEW}}))
    return {"contradictions": pd.DataFrame(contra),
            "gone": pd.DataFrame([r for k, r in explained if k == "gone"]),
            "new": pd.DataFrame([r for k, r in explained if k == "new"]),
            "unexplained": unexplained, "municipalities": municipal_moves(table)}


def municipal_moves(table: pd.DataFrame) -> pd.DataFrame:
    """The ``code`` links that move a locality to another municipality, against the
    municipal lineage (``cpv_mun_lineage``, frames 1995–2025): into a municipality created in
    that span with the old municipality among its parents, into one created from others,
    into another state, or into an existing municipality (a boundary change)."""
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from mxcensus._resources import cpv_mun_lineage
    created = {c["CVEGEO"]: (c["hasta"], {o["CVEGEO"] for o in c["origen"]})
               for c in cpv_mun_lineage()["cambios"]}
    eds = list(EDITIONS)
    rows = []
    moves = table[(table.KIND == "code") & (table.FROM.str[:5] != table.TO.str[:5])]
    for period, g in moves.groupby("PERIOD", sort=True):
        prev = eds[eds.index(period) - 1]
        n = Counter()
        for src, dst in zip(g.FROM.str[:5], g.TO.str[:5]):
            when, parents = created.get(dst, (None, set()))
            in_span = when is not None and prev < when <= period
            n["new municipality, from its parent" if in_span and src in parents else
              "new municipality, other parent" if in_span else
              "other state" if src[:2] != dst[:2] else
              "existing municipality"] += 1
        rows.append({"span": f"{prev}→{period}", "moves": len(g), **n})
    return pd.DataFrame(rows).fillna(0)


def _md(df: pd.DataFrame, index: bool = False) -> str:
    """A markdown table (numbers with thousands separators)."""
    if index:
        df = df.reset_index()
    cells = [[f"{v:,}" if isinstance(v, int) else str(v) for v in row]
             for row in df.itertuples(index=False)]
    head = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in cells])


def report(table: pd.DataFrame, stats: dict, result: dict, path: Path) -> None:
    by = table.pivot_table(index="KIND", columns="PERIOD", values="FROM", aggfunc="size",
                           fill_value=0, observed=False)
    conf = table.groupby("KIND", observed=False)["CONFIRMED"].mean().round(3)
    lines = [
        "# CPV locality lineage — build report",
        "",
        "Generated by `scripts/build_loc_lineage.py --check` (do not edit). Source: INEGI's",
        f"Archivo Histórico de Localidades, export of {stats['latest'].isoformat()}"
        f" ({stats['records']:,} localities, {stats['rows']:,} history rows,"
        f" {stats['statements']:,} stated links; {len(table):,} in scope).",
        "",
        f"Moves stated without a code on both records: {stats['paired_unkeyed']} paired by"
        f" name, {stats['unpaired_unkeyed']} statements left unpaired. Statements without a"
        f" date: {stats['undated']}; dated after the export (typos): {stats['after_export']}."
        " Locality numbers stated with a name (4 digits, no municipality): "
        + ", ".join(f"{k} {v:,}" for k, v in sorted(stats["placed"].items())) + ".",
        "",
        "## Links by kind and edition",
        "",
        _md(by.astype(int), index=True),
        "",
        "Share confirmed (stated on both records): "
        + ", ".join(f"{k} {v:.1%}" for k, v in conf.items()) + ".",
        "",
        "## Links against each edition's codes",
        "",
        "A `code` or `absorption` link whose `FROM` is still in the later edition, or a"
        " `separation` whose `FROM` was in the earlier edition but not the later one, is"
        " contradicted.",
        "",
        _md(result["contradictions"]),
        "",
        "## Codes that leave or enter between editions",
        "",
        "The ITERs' locality codes 1990–2020; 2020 → 2025 compares the MG 2020 frame with the"
        " MG 2025 frame (`l` + `lpr`; both list uninhabited localities too). What explains a"
        " code, in this order: a link of the span; the AHL's «baja» (*removed*) or"
        " «deshabitada» (*uninhabited*) at either edition; one or two dwellings (the Conteo"
        " 1995's ITER lists them only in aggregates); «Sin información» / «No hubo acceso»"
        " (*no information*: the Conteo 1995 did not reach part of Chiapas); a code the AHL"
        " does not hold (the frames' industrial parks and service sites); for a code that"
        " enters, an AHL record that starts there (*new record*), a creation or reactivation,"
        " or a locality uninhabited or removed before (*was empty*).",
        "",
        "Codes that leave:",
        "",
        _md(result["gone"]),
        "",
        "Codes that enter:",
        "",
        _md(result["new"]),
        "",
        "## Moves to another municipality against the municipal lineage",
        "",
        "`code` links whose `TO` is in another municipality: into a municipality the MG frames"
        " show created in that span with `FROM`'s municipality among its parents"
        " (`cpv_mun_lineage`), created from others, into another state, or into an existing"
        " municipality (a boundary change). 1990 → 1995 has no 1990 frame: municipalities"
        " created then count as existing.",
        "",
        _md(result["municipalities"].astype(
            {c: int for c in result["municipalities"].columns if c != "span"})),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ahl", type=Path, default=_DEFAULT_ZIP, metavar="ZIP")
    parser.add_argument("--download", action="store_true", help="refresh the AHL ZIP")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, metavar="FILE")
    parser.add_argument("--check", action="store_true",
                        help="check against the mirror's ITER and MG 2025 → --report")
    parser.add_argument("--mirror", type=Path, default=_DEFAULT_MIRROR, metavar="DIR")
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT, metavar="FILE")
    args = parser.parse_args(argv)
    if args.download or not args.ahl.exists():
        download(args.ahl)
    table, rows, stats = build(args.ahl)
    write(table, args.output)
    print(f"{stats['statements']:,} stated links → {len(table):,} in scope → {args.output}")
    print(table.pivot_table(index="KIND", columns="PERIOD", values="FROM", aggfunc="size",
                            fill_value=0, observed=False))
    if args.check:
        result = check(table, rows, edition_codes(args.mirror))
        print(result["contradictions"].to_string())
        print(result["gone"].to_string())
        print(result["new"].to_string())
        report(table, stats, result, args.report)
        print(f"report → {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
