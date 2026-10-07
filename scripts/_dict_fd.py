"""Maintainer-only: INEGI's census "FD" data dictionaries (xlsx) → variable dictionaries.

Where INEGI publishes no DDI codebook in the RNM (EIC 2025; possibly CPV 2020), the
microdata dictionary is an Excel workbook (``eic2025_micro_fd.xlsx``): one sheet per table
(``VIVIENDAS``/``PERSONAS``/``MIGRANTES``) with the columns ``Cons. | Descripción |
Mnemónico | Pregunta y categoría | Tipo | Rango válido | Longitud``. A variable row carries
the mnemonic; the rows below it list its codes (``Rango válido``) with their labels
(``Pregunta y categoría``). Codes may be ranges (``01..54``, ``0101.. 9030``), ``Nulo`` marks
the blank-by-skip cell, and ``(Según clasificador de …)`` points to a classification
catalog shipped separately (``889463931966_csv.zip``: ``OCUPACION.csv``, ``PARENTESCO.csv``…).

:func:`parse_fd_xlsx` returns ``{stem: {VARNAME: meta}}`` in the shape of
:func:`_dict_ddi.parse_ddi` (``Descripción``, ``Pregunta``, ``Tipo`` numeric/string,
``Longitud``, ``Rango``, ``Categorías``, ``Especiales``) plus ``Catálogo`` (the catalog
stem) and ``Nota``. Unlike a DDI ``valrng``, the FD ``Rango válido`` is the questionnaire's
own bound, so :func:`fd_entry` keeps it on numeric variables.

:func:`parse_indicator_csv` reads the aggregate products' ``diccionario_datos_*.csv``
(``Cons. | Indicador | Descripción | Mnemónico | Rangos | Long.``), whose footnotes define
the non-numeric cell codes (``NA: No aplica.``, ``MI: No disponible por muestra
insuficiente.``) — those become the indicators' ``Especiales``.

The workbook is read with the standard library (:func:`read_xlsx`: ``zipfile`` +
``ElementTree``); no spreadsheet dependency is needed for the build.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import _dict_ddi as ddi

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")

# FD column headers → meta fields (header text compared after accent/case folding).
_FD_HEADERS = {"descripcion": "desc", "mnemonico": "var", "pregunta y categoria": "label",
               "tipo": "tipo", "rango valido": "code", "longitud": "len"}
_CATALOG_RE = re.compile(r"seg[uú]n clasificador de ([^)]+)", re.IGNORECASE)
# A code labelled "No especificado…"/"No sabe" is a non-response sentinel (``Especiales``).
_SENTINEL_RE = re.compile(r"\bno especificad|^no sabe\b", re.IGNORECASE)
# A numeric code above the valid range that is itself a value: a top-code.
_TOPCODE_RE = re.compile(r"\bmayor(es)? a\b|^más de\b|\by más\b", re.IGNORECASE)
_NULL_CODES = {"nulo"}
_MAX_EXPAND = 200  # a code range wider than this is never enumerated
_VARNAME_RE = re.compile(r"^[A-Za-z]\w*$")  # a mnemonic (stem rows may carry '--')


def _fold(text: str) -> str:
    """Lower-case, accent-free, whitespace-collapsed text (for header/catalog matching)."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace(".", " ").split())


# --------------------------------------------------------------------------------------
# xlsx (stdlib)
# --------------------------------------------------------------------------------------

def read_xlsx(path: Path) -> dict[str, list[dict[str, str]]]:
    """``{sheet name: [row, …]}`` with each row ``{column letter: cell text}``.

    Cell text is stripped; empty and whitespace-only cells are omitted, and so are rows
    left empty. Shared strings (incl. rich-text runs), inline strings and literal values
    (numbers as written in the file) are supported — enough for INEGI's dictionaries,
    which hold no formulas the reader would need to evaluate.
    """
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{_M}t"))
                      for si in root.findall(f"{_M}si")]
        rels = {r.get("Id"): r.get("Target")
                for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        book = ET.fromstring(z.read("xl/workbook.xml"))
        out: dict[str, list[dict[str, str]]] = {}
        for sheet in book.iter(f"{_M}sheet"):
            target = rels[sheet.get(f"{_R}id")].lstrip("/")
            target = target if target.startswith("xl/") else f"xl/{target}"
            rows = []
            for row in ET.fromstring(z.read(target)).iter(f"{_M}row"):
                cells = {}
                for c in row.findall(f"{_M}c"):
                    kind, v = c.get("t"), c.find(f"{_M}v")
                    if kind == "inlineStr":
                        text = "".join(t.text or "" for t in c.iter(f"{_M}t"))
                    elif v is None or v.text is None:
                        continue
                    elif kind == "s":
                        text = shared[int(v.text)]
                    else:
                        text = v.text
                    text = text.strip()
                    if text:
                        cells[_CELL_RE.match(c.get("r")).group(1)] = text
                if cells:
                    rows.append(cells)
            out[sheet.get("name")] = rows
    return out


# --------------------------------------------------------------------------------------
# classification catalogs (889463931966_csv.zip: CLAVE,DESCRIPCION[,…])
# --------------------------------------------------------------------------------------

def read_catalogs(zip_path: Path) -> dict[str, dict[str, str]]:
    """``{catalog stem: {code: label}}`` from a ZIP of INEGI classification CSVs.

    The code is the concatenation of the ``CLAVE``/``CVE_*`` columns (``MUNICIPIO.csv`` →
    entidad+municipio) and the label the last ``DESC*`` column; codes keep their spelling.
    """
    out: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith(".csv"):
                continue
            text = z.read(name).decode("utf-8-sig")
            rows = list(csv.reader(io.StringIO(text)))
            header = [h.strip().upper() for h in rows[0]]
            keys = [i for i, h in enumerate(header) if h == "CLAVE" or h.startswith("CVE")]
            desc = [i for i, h in enumerate(header) if h.startswith("DESC")][-1]
            stem = Path(name).stem.upper()
            out[stem] = {"".join(r[i].strip() for i in keys): r[desc].strip()
                         for r in rows[1:] if r and any(x.strip() for x in r)}
    return out


def match_catalog(phrase: str, catalogs) -> str | None:
    """The catalog a ``(Según clasificador de <phrase>)`` note refers to: the stem sharing
    the most words with the phrase (``entidad federativa y país`` → ``ENTIDAD_PAIS``;
    INEGI's own stems have typos — ``ESOLARIDAD_ACUMULADA`` — so a partial overlap counts).
    ``None`` when no stem shares a word or two stems tie."""
    words = set(_fold(phrase).split())
    scored = sorted(((len(words & set(_fold(s.replace("_", " ")).split())), s) for s in catalogs),
                    reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return None
    return scored[0][1]


# --------------------------------------------------------------------------------------
# FD workbook → {stem: {VAR: meta}}
# --------------------------------------------------------------------------------------

def _parse_code(text: str):
    """``'7'`` → ``'7'``; ``'01..54'`` / ``'0101.. 9030'`` → ``(lo, hi, width)``;
    ``'Nulo'`` → ``None``. ``width`` is the zero-padding (both bounds equally long and the
    lower one padded), else 0."""
    t = text.replace(" ", "").replace("…", "..")
    if t.lower() in _NULL_CODES:
        return None
    if ".." in t:
        a, b = t.split("..", 1)
        if a.lstrip("-").isdigit() and b.lstrip("-").isdigit():
            width = len(a) if len(a) == len(b) and a.startswith("0") else 0
            return int(a), int(b), width
    return t


def _header_codes(text: str) -> list:
    """Codes of a ``Rango válido`` header such as ``{1..8, 9, Nulo}`` (catalog note and
    ``Alfanumérico`` dropped)."""
    text = _CATALOG_RE.sub("", text).replace("(", "").replace(")", "")
    inner = text.strip().strip("{}").strip()
    return [c for c in (_parse_code(x) for x in inner.split(",") if x.strip())
            if c is not None and c != "Alfanumérico"]


def _num(x: str):
    return int(x) if x.lstrip("-").isdigit() else float(x)


def _finish(var: dict, catalogs: dict | None) -> dict:
    """Turn a variable's raw code rows into ``parse_ddi``-shaped meta."""
    numeric = _fold(var["tipo"]).startswith("numer")
    header = var["code"]
    phrase = _CATALOG_RE.search(header)
    catalog = match_catalog(phrase.group(1), catalogs or {}) if phrase else None
    rows = var["rows"] or [(c, "") for c in _header_codes(header)]
    ranges = [c for c, _ in rows if isinstance(c, tuple)]
    singles = [(c, lab) for c, lab in rows if isinstance(c, str)]
    cats: dict[str, str] = {}
    special: dict[str, str] = {}
    nota = []
    meta = {"Descripción": var["desc"], "Pregunta": var["label"],
            "Tipo": "numeric" if numeric else "string", "Longitud": var["len"],
            "Rango": [], "Categorías": cats, "Especiales": special}

    if numeric:
        lo = min((r[0] for r in ranges), default=None)
        hi = max((r[1] for r in ranges), default=None)
        for code, label in singles:
            value = _num(code) if code.lstrip("-").replace(".", "", 1).isdigit() else None
            if value is None or (hi is not None and value > hi and not _TOPCODE_RE.search(label)):
                special[code] = label or code
                continue
            lo = value if lo is None else min(lo, value)
            hi = value if hi is None else max(hi, value)
            if label:
                nota.append(f"{code} = {label}")
        if lo is not None:
            meta["Rango"] = [lo, hi]
    else:
        codes = dict(catalogs.get(catalog, {})) if catalog else {}
        wide = [r for r in ranges if not codes and r[1] - r[0] + 1 > _MAX_EXPAND]
        for code, label in rows:  # in the dictionary's order
            if isinstance(code, tuple):
                lo, hi, width = code
                if wide:
                    nota.append(f"{str(lo).zfill(width)}..{str(hi).zfill(width)} = "
                                f"{label or 'códigos'} (no enumerados)")
                elif codes:  # the catalog enumerates the range
                    for c, lab in codes.items():
                        cats.setdefault(c, lab)
                else:  # a span of codes ("Número de persona"): identity labels
                    for i in range(lo, hi + 1):
                        cats.setdefault(str(i).zfill(width), str(i).zfill(width))
            elif _SENTINEL_RE.search(label):
                special[code] = label
            elif wide:
                nota.append(f"{code} = {label}")
            else:
                cats[code] = label or code
        for code in special:
            cats.pop(code, None)
        if ranges:  # used only if the entry turns out numeric (a year: 1925..2025)
            meta["Rango"] = [min(r[0] for r in ranges), max(r[1] for r in ranges)]
    if catalog:
        meta["Catálogo"] = catalog
    elif phrase:
        nota.append(f"clasificador «{phrase.group(1).strip()}» no disponible")
    if nota:
        meta["Nota"] = "; ".join(nota)
    return meta


def parse_fd_xlsx(path: Path, catalogs: dict[str, dict[str, str]] | None = None
                  ) -> dict[str, dict[str, dict]]:
    """Parse an INEGI FD workbook → ``{sheet stem: {VARNAME: meta}}`` (see module doc).

    Only sheets with a ``Mnemónico`` header are tables; the stem is the lower-cased sheet
    name (``VIVIENDAS`` → ``viviendas``). A row with a description and a question but no
    mnemonic is a question stem shared by the following items (``En su vida diaria,
    ¿(NOMBRE) cuánta dificultad tiene para:`` → ``ver, aun usando lentes?``); it prefixes
    every item question that starts in lower case, until the next stem or section.
    ``catalogs`` (:func:`read_catalogs`) enumerate the ``Según clasificador`` variables.
    """
    out: dict[str, dict[str, dict]] = {}
    for sheet, rows in read_xlsx(path).items():
        cols = None
        for i, row in enumerate(rows):
            folded = {_FD_HEADERS.get(_fold(v)): k for k, v in row.items()}
            if "var" in folded and "code" in folded:
                cols = {field: col for field, col in folded.items() if field}
                break
        if cols is None:
            continue
        vars_: dict[str, dict] = {}
        current, stem = None, None
        for row in rows[i + 1:]:
            get = {field: row.get(col, "") for field, col in cols.items()}
            if _VARNAME_RE.match(get["var"]):
                label = get["label"]
                if stem and label[:1].islower():
                    label = f"{stem} {label}"
                current = {**get, "label": label, "rows": []}
                vars_[get["var"]] = current
            elif get["code"] and get["label"] and current is not None:
                code = _parse_code(get["code"])
                if code is not None:
                    current["rows"].append((code, get["label"]))
            elif get["desc"] and get["label"] and not get["code"]:
                stem, current = get["label"], None
            elif not any(get.values()):  # a section title (outside the table columns)
                stem, current = None, None
        out[sheet.strip().lower()] = {v: _finish(m, catalogs) for v, m in vars_.items()}
    return out


# --------------------------------------------------------------------------------------
# Aggregate-product indicator dictionaries (diccionario_datos_*.csv)
# --------------------------------------------------------------------------------------

_NOTE_RE = re.compile(r"^(?P<code>[A-Z]{1,3}): (?P<label>.+?)\.?$")


def parse_indicator_csv(path: Path) -> dict[str, dict]:
    """Parse a ``diccionario_datos_*.csv`` → ``{MNEMONIC: meta}``.

    ``Rangos`` such as ``0 … 100.00`` make a numeric indicator (``Decimales`` from the
    upper bound); zero-padded code ranges (``00…32``) and ``Alfanumérico`` make a string.
    The table's footnotes ``XX: label.`` are the non-numeric cell codes → ``Especiales`` of
    every numeric indicator. The indicator ranges are kept verbatim (``Rangos``) but not
    turned into a ``Rango`` bound: a column holds the five estimators (value, standard
    error, CI limits, CV) and only the value obeys the indicator's range.
    """
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text)))
    head = next(i for i, r in enumerate(rows) if any(_fold(c) == "mnemonico" for c in r))
    idx = {_fold(c): j for j, c in enumerate(rows[head])}
    col = {k: idx[k] for k in ("indicador", "descripcion", "mnemonico", "rangos")}
    col["len"] = next(j for k, j in idx.items() if k.startswith("long"))
    special = {}
    for r in rows[head + 1:]:
        m = _NOTE_RE.match((r[0] if r else "").strip())
        if m:
            special[m["code"]] = m["label"]
    out: dict[str, dict] = {}
    for r in rows[head + 1:]:
        if len(r) <= col["mnemonico"] or not r[col["mnemonico"]].strip():
            continue
        rng = " ".join(r[col["rangos"]].split())
        bounds = [b for b in re.split(r"\s*(?:…|\.\.\.?)\s*", rng) if b]
        numeric = (len(bounds) == 2 and all(re.fullmatch(r"-?\d+(\.\d+)?", b) for b in bounds)
                   and not (len(bounds[0]) > 1 and bounds[0].startswith("0")))
        meta = {"Descripción": r[col["indicador"]].strip(),
                "Definición": " ".join(r[col["descripcion"]].split()),
                "Tipo": "numeric" if numeric else "string",
                "Longitud": r[col["len"]].strip(), "Rangos": rng,
                "Rango": [], "Categorías": {}, "Especiales": dict(special) if numeric else {}}
        if numeric and "." in bounds[1]:
            meta["Decimales"] = str(len(bounds[1].split(".")[1]))
        out[r[col["mnemonico"]].strip()] = meta
    return out


# --------------------------------------------------------------------------------------
# One variables-YAML entry from an FD (or indicator) dictionary entry
# --------------------------------------------------------------------------------------

_EXTRA_KEYS = ("Definición", "Rangos", "Decimales", "Catálogo")
_ORDER = ("Descripción", "Pregunta", "Definición", "Tipo", "Longitud", "Rango", "Decimales",
          "Rangos", "Categorías", "Especiales", "Catálogo", "Nota")


def fd_entry(col: str, observed: set[str] | None, core: dict | None, doc: dict | None,
             threshold: int) -> tuple[dict, str]:
    """:func:`_dict_ddi.dictionary_entry` for an FD-documented variable (same priority:
    core > dictionary > data), with the FD's differences:

    - a string variable without categories (keys, free codes) or whose classification
      catalog has more than ``threshold`` codes (occupation, activity, country,
      municipality, language) stays ``Tipo: string`` with its ``Catálogo`` named — not a
      huge ``Categorías`` map; its sentinel codes are listed as ``Especiales``;
    - a numeric variable keeps the FD's ``Rango`` (the questionnaire's valid range);
    - ``Catálogo``/``Decimales``/``Definición``/``Rangos`` are carried over, the source is
      reported as ``fd``/``fd+data`` and notes say "FD", not "DDI".
    """
    if core is not None or doc is None:
        return ddi.dictionary_entry(col, observed, core, doc, threshold)
    cats = doc.get("Categorías") or {}
    if doc.get("Tipo") == "string" and (not cats or (doc.get("Catálogo") and len(cats) > threshold)):
        entry = {"Descripción": doc.get("Descripción", ""), "Pregunta": doc.get("Pregunta", ""),
                 "Tipo": "string", "Longitud": doc.get("Longitud", "")}
        if doc.get("Especiales"):
            entry["Especiales"] = dict(doc["Especiales"])
        if doc.get("Catálogo") and cats:
            entry["Nota"] = (f"códigos del catálogo {doc['Catálogo']} ({len(cats)} renglones; "
                             "no enumerados)")
        elif doc.get("Nota"):
            entry["Nota"] = doc["Nota"]
        source = "fd"
    else:
        entry, source = ddi.dictionary_entry(col, observed, None, doc, threshold)
        source = source.replace("ddi", "fd")
        if "Nota" in entry:
            entry["Nota"] = entry["Nota"].replace("el DDI", "el FD")
        elif doc.get("Nota"):
            entry["Nota"] = doc["Nota"]
        if entry.get("Tipo") == "numeric" and doc.get("Rango"):
            entry["Rango"] = list(doc["Rango"])
    for key in _EXTRA_KEYS:
        if doc.get(key):
            entry[key] = doc[key]
    if not entry.get("Pregunta"):
        entry.pop("Pregunta", None)
    return {k: entry[k] for k in _ORDER if k in entry} | {
        k: v for k, v in entry.items() if k not in _ORDER}, source
