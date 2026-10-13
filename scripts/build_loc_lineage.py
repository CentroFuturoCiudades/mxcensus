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
  on the new one; the code also «, localidad NAME (LLLL)», «con nombre y clave NAME
  (LLLL)», «en donde tenía la clave (LLLL)» or after a decree's sentence), a renumbering
  inside a record («Hasta este evento estuvo registrada con clave Y» … «A partir de este
  evento cambia a la clave X», «Anteriormente tenía la clave Y»), a duplicate registration
  («Es la misma localidad (LLLL) del municipio (MMM)», «Misma que la localidad …»: the
  duplicate is ``FROM``);
- ``absorption`` — ``FROM`` joins ``TO`` («Se conurba a / Se fusiona a …» on the absorbed
  record, «A esta localidad se conurba(n) / fusiona(n) / integra(n) …» on the other);
- ``counted_with`` — ``FROM`` was counted with ``TO`` at that census only («Se censó con la
  localidad …»);
- ``separation`` — ``FROM`` leaves ``TO`` («Se desconurba / Se desfusiona / Se desagrega de
  …», «De esta localidad se desconurba(n) / desfusiona(n) …»).

A locality number stated with a name but no municipality («Se conurba a Playas de Rosarito
(0001)») is placed by that name (``Resolver``, ``name_match``: abbreviations, ordinals and
misspellings allowed, placeholders such as «Ninguno» never a match): the stating record's
municipality is wrong when the other locality lies in another. A move stated without the code
(«Pasa al municipio Nadadores (021).») confirms the code link the other record states, is
paired with the other record's statement by the locality's name, or is linked to the only
locality of that name in the other municipality (``pair_unkeyed``). Rival claims on one
locality at one edition (two absorbers, two new codes: INEGI lists some twice) keep the one
stated on both records; with none, the target's own record decides (a new code that states
another origin is not this locality's), then a name-verified one, one stated on the
locality's own record, the closest name (``lineage``).

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
import difflib
import functools
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
_KEY = (r"\.?,?\s*(?:con|y) (?:la )?clave(?: de(?: la)? localidad| geoestad[ií]stica)? "
        r"\(?\s*\b(\d{9}|\d{4})\b\s*\)?")
# the old or new code written another way after the municipality: with the locality's name
# («, localidad El Betel (0119)», «con nombre y clave La Caldera (0412)», «, El Jarillal con
# clave de localidad (0123)»), as the code it had there («en donde tenía la clave (0313)»),
# or after a decree's sentence («Escárcega 009. Decreto No. 66 del … de 1998. con clave de
# localidad 0144.»)
_KEYS = (
    r",?\s*(?:con nombre y clave(?: de localidad)?|(?:de la )?localidad)\s+" + _N
    + r"\s*\(\s*(\d{4})\s*\)",
    r",\s*(?!(?:con|y|de la|localidad)\b)" + _N + r"\s+con clave(?: de localidad)?\s*"
    r"\(?\s*(\d{4})\s*\)?",
    r",?\s*en (?:donde|el que) ten[ií]a (?:la )?clave(?: de localidad)?\s*\(?\s*(\d{4})\s*\)?",
    r"\s*\.?\s*(?=Decreto|Peri[oó]dico)[^()]{0,150}?\.\s*(?:con|y) (?:la )?clave(?: de "
    r"localidad)?\s*\(?\s*(\d{4})\s*\)?",
)
_NO_KEY = r"(?![\s)]*\.?,?\s*(?:con|y) (?:la )?clave)"
# localities listed by code, some only in part («… y parte de las localidades 151060125 …»)
_LIST = (r"((?:(?:parte de (?:la |las )?(?:localidad(?:es)? )?)?\(?\d{9}\)?"
         r"(?:\s*,\s*|\s+y\s+|\s+e\s+)?)+)")
_ART = r"(?:la |las |los |el )?(?:localidad(?:es)? )?(?:de )?"
# a locality's name written after its number («(0321) Los Laureles.»), not its municipality
_AFTER = r"(?!del? municipio|de la |,)([^\s.()\d][^.()]{0,89})"
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
    *(("pasa", r"pasa (?:al mun[i]?cipio|a la delegaci[oó]n) (?:de )?" + _N + _MUN + key)
      for key in (_KEY, *_KEYS)),
    *(("viene", r"viene (?:del? mun[i]?cipio|de la delegaci[oó]n) (?:de )?" + _N + _MUN + key)
      for key in (_KEY, *_KEYS)),
    ("viene", r"pasa del municipio (?:de )?" + _N + _MUN + _KEYS[2]),
    ("pasa_sin", r"pasa al municipio (?:de )?(" + _N + r")\s*" + _MUN + _NO_KEY),
    ("viene_sin", r"viene del municipio (?:de )?(" + _N + r")\s*" + _MUN + _NO_KEY),
    ("cambia", r"(?:cambi[aó] (?:a )?la clave|se registra con (?:la )?clave)"
               r"(?: de localidad)? \(?(\d{9}|\d{4})\b\)?"),
    ("hasta", r"hasta este evento (?:la localidad )?estuvo registrada con (?:la )?"
              r"clave(?: de localidad)? \(?(\d{9}|\d{4})\b\)?"),
    ("antes", r"antes era la (?:localidad )?\(?(\d{9})\)?"),
    ("antes", r"anteriormente ten[ií]a (?:la )?clave(?: de localidad)? \(?(\d{9}|\d{4})\b\)?"),
    ("misma", r"es la misma localidad \((\d{4})\) del municipio \((\d{3})\)"),
    ("misma_que", r"misma que la localidad " + _N + r"\(?(\d{9})\)?"),
    # absorptions, counted with, separations; a locality number may come with its name
    # before («Tenabo, con clave (0001)», «Acatepec (San Antonio) (0054)») or after it
    # («(0321) Los Laureles»)
    ("absorbida", r"(?:se (?:conurba|fusiona)|(?:localidad )?(?:conurbada|fusionada)) "
                  r"(?:a|al|con) " + _ART + r"(?:(\d{9})|(" + _N + r"),? (?:con )?(?:la )?clave "
                  r"\(?(\d{9}|\d{4})\)?|\((\d{4})\)\s+" + _AFTER + r"|(" + _N
                  + r")\s*\((\d{4})\)(?:,? del municipio (?:de )?" + _N + _MUN + r")?)"),
    ("absorbe", _HERE + r"(?:conurba|fusiona|integra)n? (?:parte de )?" + _ART + _LIST),
    ("censo_clave", r"cens[oó] con (?:la )?clave(?: de localidad)? \(?(\d{4})\)?"),
    ("censo_con", r"(?:se )?cens[oó] con (?!(?:la )?clave)" + _ART + r"(" + _N
                  + r")\s*\((\d{4})\)"),
    ("separada", r"(?:se des(?:conurba|fusiona)n?|se desagrega|localidad desagregada) de "
                 + _ART + r"(?:(\d{9})|\((\d{4})\)\s+" + _AFTER + r"|(" + _N
                 + r")\s*\((\d{4})\)(?:,? del municipio (?:de )?" + _N + _MUN + r")?)"),
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
    """Every pattern's matches in one history text (groups as strings, '' when absent; the
    patterns sharing a name pooled, each match once)."""
    out: dict[str, list[tuple[str, ...]]] = {}
    for name, rx in _PATTERNS:
        for m in rx.finditer(text):
            hit = tuple(g or "" for g in m.groups())
            if hit not in out.setdefault(name, []):
                out[name].append(hit)
    return {k: v for k, v in out.items() if v}


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


_GENERIC = {"la", "el", "los", "las", "de", "del", "y", "cab", "cabecera", "san", "santa",
            "rancho", "colonia", "ejido", "localidad", "ciudad", "fraccionamiento", "barrio"}
# abbreviations and ordinals as INEGI writes them («Cd. Juárez», «Ing. Eugenio …», «El
# Pardillo 3ro», «Chanyokdzonot II» / «Dos»)
_WORDS = {"cd": "ciudad", "sn": "san", "sta": "santa", "sto": "santo", "col": "colonia",
          "fracc": "fraccionamiento", "frac": "fraccionamiento", "ej": "ejido",
          "gral": "general", "ing": "ingeniero", "lic": "licenciado", "prof": "profesor",
          "dr": "doctor", "no": "numero", "num": "numero", "nte": "norte",
          **{w: str(i) for i, ws in enumerate((
              (), ("i", "uno", "una", "primero", "primera", "1ro", "1ra", "1o", "1a"),
              ("ii", "ll", "dos", "segundo", "segunda", "2do", "2da", "2o", "2a"),
              ("iii", "tres", "tercero", "tercera", "3ro", "3ra", "3o", "3a"),
              ("iv", "cuatro", "cuarto", "cuarta", "4to", "4ta"),
              ("v", "cinco", "quinto", "quinta", "5to", "5ta"))) for w in ws}}


@functools.cache
def _tokens(name: str) -> frozenset[str]:
    return frozenset({_WORDS.get(w, w) for w in _norm_name(name).split()} - _GENERIC)


# the words of a placeholder («Localidad sin nombre», «Ninguno», «S/N»): it names nothing
_UNNAMED = frozenset({"sin", "nombre", "nombres", "ninguno", "ninguna", "s", "n"})


def name_match(a: str, b: str, fuzzy: bool = True) -> int:
    """How well two locality names match once normalized (accents, case, punctuation; a
    placeholder such as «Localidad sin nombre» matches nothing): 3 equal, 2 equal without
    generic words («El», «Rancho», «(Cab.)», «Ciudad»…) once
    abbreviations and ordinals are spelled out, 1 one inside the other, sharing at least half
    their distinctive words or one a misspelling of the other («Cuidad Obregón», «Tlacopa»
    for «Tlacoapa»: 85% of their letters in common; not tested with ``fuzzy=False``), 0
    not."""
    na, nb = _norm_name(a), _norm_name(b)
    ta, tb = _tokens(a), _tokens(b)
    if not na or not nb or (ta and ta <= _UNNAMED) or (tb and tb <= _UNNAMED):
        return 0
    if na == nb:
        return 3
    if ta and ta == tb:
        return 2
    if f" {na} " in f" {nb} " or f" {nb} " in f" {na} ":
        return 1
    if ta and tb and len(ta & tb) / len(ta | tb) >= 0.5:
        return 1
    if not fuzzy:
        return 0
    sa, sb = " ".join(sorted(ta)), " ".join(sorted(tb))
    return int(min(len(sa), len(sb)) >= 5
               and difflib.SequenceMatcher(None, sa, sb).ratio() >= 0.85)


class Resolver:
    """A locality number (4 digits) stated with a name, without its municipality: among
    the state's localities with that number, the one whose names in the AHL match the name
    best (``name_match``; a misspelling only when no name matches otherwise), the stating
    record's municipality on a tie with it; the record's municipality when none matches or
    several tie (counted as unverified)."""

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
        for fuzzy in (False, True):        # a misspelling only when nothing else matches
            score = {c: max((name_match(name, n, fuzzy) for n in self.names[c]), default=0)
                     for c in self.by_number.get((ent, loc), [])}
            best = max(score.values(), default=0)
            if best:
                break
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
        # a move stated without the code beside an absorption or a separation: the other
        # locality is in the municipality it moves to («Pasa al municipio Tultitlán (109). Se
        # conurba a San Pablo de las Salinas (0025).») or comes from
        to_mun = f["pasa_sin"][0][1] if len(f.get("pasa_sin", [])) == 1 else ""
        from_mun = f["viene_sin"][0][1] if len(f.get("viene_sin", [])) == 1 else ""
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
            add(_expand(x, ent, mun), code, "code", r)
        for full, name2, key, loc3, name3, name, loc, m in f.get("absorbida", []):
            dst = (full or (key if len(key) == 9 else "")
                   or resolve(ent, mun, key or loc3 or loc, name2 or name3 or name,
                              m or to_mun))
            add(code, dst, "absorption", r)
        for (lst,) in f.get("absorbe", []):
            for x in re.findall(r"\d{9}", lst):
                add(x, code, "absorption", r)
        for (loc,) in f.get("censo_clave", []):       # its own number at that census
            add(code, ent + mun + loc, "counted_with", r)
        for name, loc in f.get("censo_con", []):
            add(code, resolve(ent, mun, loc, name), "counted_with", r)
        for full, loc3, name3, name, loc, m in f.get("separada", []):
            add(code, full or resolve(ent, mun, loc3 or loc, name3 or name, m or from_mun),
                "separation", r)
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


@functools.cache
def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _in_scope(day: date | None, kind: str, latest: date) -> bool:
    """A link takes effect after 1990 (counted with another locality: at 1990 or later)
    and by the last cut; a date after the export is a typo (dropped)."""
    if day is None or day > latest or edition_of(day) is None:
        return False
    return day > EDITIONS["1990"] or (kind == "counted_with" and day >= CENSUS_DATES["1990"])


def _previous(period: str) -> str:
    eds = list(EDITIONS)
    return eds[max(eds.index(period) - 1, 0)]


def pair_unkeyed(rows: list[Row], links: list[Link], latest: date
                 ) -> tuple[list[Link], Counter, pd.DataFrame]:
    """Moves stated without the code («Pasa al municipio X (MMM).» on the old record,
    «Viene del municipio Y (NNN).» on the new one), in this order:

    - beside an absorption or a separation on the same row: that link places the locality
      (``record_links``), nothing to pair;
    - the other record states the code link (into or from that municipality, at that
      edition): the statement confirms it, when it is the only one;
    - a statement on each side: paired by the localities' names (any name in their
      histories, ``name_match`` ≥ 2, each the other's only best) in that pair of
      municipalities at that edition;
    - left on one side: the only record of that name (``name_match`` ≥ 2) in the other
      municipality that is there at that edition (a move: it starts by the edition's cut
      and is there after the previous one; a provenance: it was there at the previous
      edition and ends by this one), stating no other code link then — a link stated on one
      record.

    Returns the links, what became of the statements (one per record and move) and those
    left (``history here``: a new record whose history goes back before the move — the old
    code was filed under it, so no other record holds it)."""
    recs: dict[str, list[Row]] = {}
    for r in rows:
        recs.setdefault(r.code, []).append(r)
    names = {c: {r.name for r in rs} for c, rs in recs.items()}
    days = {c: sorted(r.day for r in rs if r.day) for c, rs in recs.items()}
    by_mun: dict[str, list[str]] = {}
    for c in recs:
        by_mun.setdefault(c[:5], []).append(c)
    out_of: dict[tuple[str, str], set[str]] = {}
    into: dict[tuple[str, str], set[str]] = {}
    for l in links:
        if l.kind == "code" and _in_scope(l.day, "code", latest):
            out_of.setdefault((l.source, edition_of(l.day)), set()).add(l.target)
            into.setdefault((l.target, edition_of(l.day)), set()).add(l.source)
    coded_src = {l.source for l in links if l.kind == "code"}
    coded_dst = {l.target for l in links if l.kind == "code"}

    def score(a: str, b: str) -> int:              # ≥ 2 is all that counts here
        return max(name_match(x, y, fuzzy=False) for x in names[a] for y in names[b])

    out, counts, left = [], Counter(), []
    gone: dict[tuple[str, str, str], dict[str, Row]] = {}
    come: dict[tuple[str, str, str], dict[str, Row]] = {}
    for r in rows:
        if not _in_scope(r.day, "code", latest):
            continue
        period = edition_of(r.day)
        f = r.found
        # a statement whose row gives the code («…, localidad El Betel (0119).») is no
        # unkeyed one; one beside an absorption or a separation is placed by that link
        for direction, unkeyed, coded, beside, links_of, own in (
                ("gone", "pasa_sin", ("pasa", "pasa_estado"), "absorbida", out_of, coded_src),
                ("come", "viene_sin", ("viene", "viene_estado"), "separada", into, coded_dst)):
            if any(c in f for c in coded):
                continue
            for _, m in f.get(unkeyed, []):
                other = r.code[:2] + m
                hits = {c for c in links_of.get((r.code, period), ()) if c[:5] == other}
                if beside in f:
                    counts["beside an absorption" if beside == "absorbida"
                           else "beside a separation"] += 1
                elif len(hits) == 1:        # (two would be rival claims it cannot tell apart)
                    c = hits.pop()
                    out.append(Link(r.code, c, "code", r.day, r.kind, r.code) if direction
                               == "gone" else Link(c, r.code, "code", r.day, r.kind, r.code))
                    counts["confirms a code link"] += 1
                elif r.code in own:
                    counts["coded elsewhere"] += 1
                elif direction == "gone":
                    gone.setdefault((r.code[:5], other, period), {}).setdefault(r.code, r)
                else:
                    come.setdefault((other, r.code[:5], period), {}).setdefault(r.code, r)
    # a statement on each side, paired by name
    for key in sorted(set(gone) & set(come)):
        olds, news = gone[key], come[key]
        s = {(o, n): score(o, n) for o in olds for n in news}
        o_all, n_all = list(olds), list(news)
        for (o, n), v in sorted(s.items()):
            if v >= 2 and all(s[o, x] < v for x in n_all if x != n) and all(
                    s[y, n] < v for y in o_all if y != o):
                out.append(Link(o, n, "code", olds[o].day, olds[o].kind, o))
                out.append(Link(o, n, "code", news[n].day, news[n].kind, n))
                counts["paired by name"] += 2
                del olds[o], news[n]
    # one side only: the other record states nothing
    for (src_mun, dst_mun, period), olds in sorted(gone.items()):
        cut, prev = EDITIONS[period], EDITIONS[_previous(period)]
        for o, r in sorted(olds.items()):
            cands = [c for c in by_mun.get(dst_mun, []) if score(o, c) >= 2
                     and days[c] and days[c][0] <= cut and days[c][-1] > prev
                     and not into.get((c, period)) and not out_of.get((c, period))]
            if len(cands) == 1:
                out.append(Link(o, cands[0], "code", r.day, r.kind, o))
                counts["one side, by name"] += 1
            else:
                why = "several of that name" if cands else "no record of that name"
                counts["left: " + why] += 1
                left.append((period, "to", o, dst_mun, r.name, why, " ".join(cands), r.text))
    for (src_mun, dst_mun, period), news in sorted(come.items()):
        cut, prev = EDITIONS[period], EDITIONS[_previous(period)]
        for n, r in sorted(news.items()):
            cands = [c for c in by_mun.get(src_mun, []) if score(n, c) >= 2
                     and days[c] and days[c][0] <= prev <= days[c][-1] <= cut
                     and not into.get((c, period)) and not out_of.get((c, period))]
            if len(cands) == 1:
                out.append(Link(cands[0], n, "code", r.day, r.kind, n))
                counts["one side, by name"] += 1
            else:
                why = ("several of that name" if cands else "history here"
                       if days[n] and days[n][0] < r.day else "no record of that name")
                counts["left: " + why] += 1
                left.append((period, "from", n, src_mun, r.name, why, " ".join(cands), r.text))
    return out, counts, pd.DataFrame(left, columns=[
        "PERIOD", "MOVE", "RECORD", "MUNICIPALITY", "NAME", "WHY", "CANDIDATES", "TEXT"])


def lineage(rows: list[Row], links: list[Link], latest: date
            ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The links in scope, one per (``FROM``, ``TO``, ``KIND``, ``PERIOD``): ``DATE`` the
    earliest statement's, ``CONFIRMED`` when both records state it.

    Rival claims on one locality at one edition (two absorbers, two new codes) keep the one
    stated on both records. With none (or several) confirmed, the first of these that tells
    them apart decides:

    1. a ``code`` claim not stated on its target, whose target states another origin then
       («Pasa … con clave (0100)» where 0100 says «Viene … con clave (0183)»), is dropped;
    2. an absorption, separation or count whose locality number matched its name beats one
       that did not;
    3. one stated on the locality's own record beats those stated only on others;
    4. a ``code`` claim whose target's name is closest to the locality's (``name_match``).

    Undecided ``code`` claims on a locality whose record goes on under its own code at a later
    census (none of them a renumbering) are all dropped; any other undecided claims are all
    kept (a unit only gets coarser) — among them a locality split in two, each part stating
    it as its origin. Returns the table and the rival claims (every claim of a locality with
    several, the rule that decided them, ``KEPT``)."""
    df = pd.DataFrame([l.__dict__ for l in links])
    df = df[[_in_scope(d, k, latest) for d, k in zip(df["day"], df["kind"])]].copy()
    df["PERIOD"] = df["day"].map(edition_of)
    df["side"] = ["from" if rec == s else "to" if rec == t else "other"
                  for rec, s, t in zip(df["record"], df["source"], df["target"])]
    df = df.sort_values("day", kind="stable")
    out = (df.groupby(["source", "target", "kind", "PERIOD"], sort=False)
             .agg(DATE=("day", "first"), EVENT=("event", "first"),
                  sides=("side", lambda s: frozenset(s)), verified=("verified", "max"))
             .reset_index())
    out["CONFIRMED"] = [{"from", "to"} <= s for s in out["sides"]]
    names: dict[str, set[str]] = {}
    censuses: dict[str, list[date]] = {}
    for r in rows:
        names.setdefault(r.code, set()).add(r.name)
        if r.kind == "census" and r.day:
            censuses.setdefault(r.code, []).append(r.day)
    # the origin each new code's record states, per edition
    origin: dict[tuple[str, str], set[str]] = {}
    for s, t, k, p, sides in zip(out["source"], out["target"], out["kind"], out["PERIOD"],
                                 out["sides"]):
        if k == "code" and "to" in sides:
            origin.setdefault((t, p), set()).add(s)

    def score(a: str, b: str) -> int:
        return max((name_match(x, y) for x in names.get(a, ()) for y in names.get(b, ())),
                   default=0)

    def closest(g: pd.DataFrame) -> pd.Series:
        sc = pd.Series([score(s, t) for s, t in zip(g["source"], g["target"])], index=g.index)
        return (g["kind"] == "code") & (sc == sc.max()) & (sc > 0)

    rules = (
        ("the target states another origin", lambda g: [
            k != "code" or "to" in sd or not (origin.get((t, p), set()) - {s})
            for s, t, k, p, sd in zip(g["source"], g["target"], g["kind"], g["PERIOD"],
                                      g["sides"])]),
        ("its number matched its name", lambda g: (g["kind"] != "code") & g["verified"]),
        ("stated on its own record", lambda g: (g["kind"] != "code") & g["verified"]
         & g["sides"].map(lambda sd: "from" in sd)),
        ("the closest name", closest),
    )
    key = ["source", "kind", "PERIOD"]
    claims = out.groupby(key)["target"].transform("size")
    keep, log = [out[claims == 1]], []
    for (src, kind, period), g in out[claims > 1].groupby(key, sort=True):
        kept = g["CONFIRMED"]
        rule = ("stated on both records" if kept.sum() == 1
                else "several stated on both records" if kept.any() else None)
        for name, test in rules if rule is None else ():
            mask = pd.Series(test(g), index=g.index).astype(bool)
            if mask.any() and not mask.all():
                kept, rule = mask, name
                break
        if rule is None:
            kept = pd.Series(True, index=g.index)
            if kind == "code" and any(d > EDITIONS[period] for d in censuses.get(src, ())):
                kept[:], rule = False, "undecided, the locality keeps its code (all dropped)"
            elif kind == "code" and all("to" in sd for sd in g["sides"]) and all(
                    score(src, t) for t in g["target"]):
                rule = "each states it as its origin (all kept)"
            else:
                rule = "undecided (all kept)"
        keep.append(g[kept])
        log.append(g.assign(RULE=rule, KEPT=kept))
    out = pd.concat(keep)
    rivals = (pd.concat(log) if log else out.head(0).assign(RULE="", KEPT=False)).rename(
        columns={"source": "FROM", "target": "TO", "kind": "KIND"})
    rivals["SIDES"] = rivals["sides"].map(lambda sd: "+".join(sorted(sd)))
    rivals = rivals[["PERIOD", "KIND", "FROM", "TO", "CONFIRMED", "SIDES", "RULE", "KEPT"]]
    out = out.rename(columns={"source": "FROM", "target": "TO", "kind": "KIND"})
    out = out[["PERIOD", "DATE", "EVENT", "KIND", "FROM", "TO", "CONFIRMED"]]
    out["KIND"] = pd.Categorical(out["KIND"], KINDS)
    return (out.sort_values(["PERIOD", "KIND", "FROM", "TO"]).reset_index(drop=True),
            rivals.reset_index(drop=True))


def build(path: Path) -> tuple[pd.DataFrame, list[Row], dict]:
    """The lineage table, the history rows and the build's counts."""
    latest = ahl_date(path)
    rows, links, placed = parse(read_ahl(path, "Movimientos"))
    extra, unkeyed, left = pair_unkeyed(rows, links, latest)
    table, rivals = lineage(rows, links + extra, latest)
    # the links that rest on a locality number placed without its name matching, stated
    # on no other record
    verified: dict[tuple, bool] = {}
    for l in links + extra:
        if _in_scope(l.day, l.kind, latest):
            k = (l.source, l.target, l.kind, edition_of(l.day))
            verified[k] = verified.get(k, False) or l.verified
    shaky = sum(not verified.get(k, True) and not c for k, c in zip(
        zip(table["FROM"], table["TO"], table["KIND"].astype(str), table["PERIOD"]),
        table["CONFIRMED"]))
    stats = {"rows": len(rows), "records": len({r.code for r in rows}),
             "statements": len(links), "unkeyed": dict(unkeyed), "unpaired": left,
             "rivals": rivals,
             "latest": latest,
             "undated": sum(1 for l in links if l.day is None),
             "after_export": sum(1 for l in links if l.day and l.day > latest),
             "placed": dict(placed), "unverified_links": shaky}
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
    left = stats["unpaired"]
    left_by = (left.pivot_table(index="WHY", columns="PERIOD", values="RECORD",
                                aggfunc="size", fill_value=0) if len(left) else pd.DataFrame())
    rivals = stats["rivals"]
    kept = rivals.groupby(["PERIOD", "KIND", "FROM"])["KEPT"].transform("sum")
    open_claims = (rivals[kept != 1].groupby(["PERIOD", "KIND", "FROM", "RULE"], sort=True)
                   .apply(lambda g: " ".join(f"{t} ({sd})" for t, sd in zip(g["TO"], g["SIDES"])),
                          include_groups=False).rename("TO (stated on)").reset_index())
    lines = [
        "# CPV locality lineage — build report",
        "",
        "Generated by `scripts/build_loc_lineage.py --check` (do not edit). Source: INEGI's",
        f"Archivo Histórico de Localidades, export of {stats['latest'].isoformat()}"
        f" ({stats['records']:,} localities, {stats['rows']:,} history rows,"
        f" {stats['statements']:,} stated links; {len(table):,} in scope). Statements"
        f" without a date: {stats['undated']}; dated after the export (typos):"
        f" {stats['after_export']}. Locality numbers stated with a name, without their"
        " municipality («Se conurba a Playas de Rosarito (0001)»), placed by that name: "
        + ", ".join(f"{k} {v:,}" for k, v in sorted(stats["placed"].items()))
        + f" (in the record's municipality; {stats['unverified_links']} links of the lineage"
        " rest on one and no other record states them).",
        "",
        "## Links by kind and edition",
        "",
        _md(by.astype(int), index=True),
        "",
        "Share confirmed (stated on both records): "
        + ", ".join(f"{k} {v:.1%}" for k, v in conf.items()) + ".",
        "",
        "## Moves stated without a code",
        "",
        "«Pasa al municipio X (MMM).» or «Viene del municipio X (MMM).» without the other"
        " code, in scope (one per record and move; `pair_unkeyed`): beside an absorption or"
        " a separation that places it; confirming the code link the other record states;"
        " paired with a statement on the other side by the locality's name; linked on one"
        " side to the only record of that name in the other municipality there at that"
        " edition; or left — no record of that name, several, or the old code filed under"
        " the new record (*history here*).",
        "",
        _md(pd.DataFrame(sorted(stats["unkeyed"].items(), key=lambda kv: -kv[1]),
                         columns=["statements", "count"])),
        "",
        "Left, by edition:",
        "",
        _md(left_by.reset_index().astype({c: int for c in left_by.columns})),
        "",
        "## Rival claims",
        "",
        "Localities with two or more claims of one kind at one edition (two absorbers, two"
        " new codes), by the rule that decided them (`lineage`):",
        "",
        _md(rivals.drop_duplicates(["PERIOD", "KIND", "FROM"])["RULE"].value_counts()
            .rename_axis("rule").reset_index(name="localities")),
        "",
        "Left with several claims (all kept: a unit only gets coarser) or with none:",
        "",
        _md(open_claims) if len(open_claims) else "None.",
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
