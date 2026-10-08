"""Maintainer-only: INEGI's census "FD" data dictionaries (xlsx/xls) → variable dictionaries.

Where INEGI publishes no usable DDI codebook in the RNM (EIC 2025 has none; the CPV 2020
and EIC 2015 ones are Nesstar exports with incomplete value labels), the microdata
dictionary is an Excel workbook (``eic2025_micro_fd.xlsx``; EIC 2015's ``eic2015_fd.xls``
is a legacy BIFF8 file): one sheet per table (``VIVIENDAS``/``PERSONAS``/``MIGRANTES``;
2015 ``TR_Vivienda``/``TR_Persona``) with the columns ``Cons. | Descripción | Mnemónico |
Pregunta y categoría | Tipo | Rango válido | Longitud`` (in any order). A variable row
carries the mnemonic; the rows below it list its codes (``Rango válido``) with their labels
(``Pregunta y categoría``). Codes may be ranges (``01..54``, ``0101.. 9030``), ``Nulo`` (or a
row labelled «Blanco por pase») marks the blank-by-skip cell, and ``(Según clasificador de
…)`` — in 2015 a ``TC_…`` code row — points to a classification catalog shipped separately
(``889463931966_csv.zip``: ``OCUPACION.csv``, ``PARENTESCO.csv``…; 2015
``eic2015_catalogos.zip``: ``TC_OCUPACION_2015.xls``…).

:func:`parse_fd` returns ``{stem: {VARNAME: meta}}`` in the shape of
:func:`_dict_ddi.parse_ddi` (``Descripción``, ``Pregunta``, ``Tipo`` numeric/string,
``Longitud``, ``Rango``, ``Categorías``, ``Especiales``) plus ``Catálogo`` (the catalog
stem) and ``Nota``. Unlike a DDI ``valrng``, the FD ``Rango válido`` is the questionnaire's
own bound, so :func:`fd_entry` keeps it on numeric variables.

:func:`parse_indicator_csv` reads the aggregate products' ``diccionario_datos_*.csv``
(``Cons. | Indicador | Descripción | Mnemónico | Rangos | Long.``), whose footnotes define
the non-numeric cell codes (``NA: No aplica.``, ``MI: No disponible por muestra
insuficiente.``) — those become the indicators' ``Especiales``.

Workbooks are read with the standard library (:func:`read_xlsx`: ``zipfile`` +
``ElementTree``; :func:`read_xls`: the OLE2 container and BIFF8 records with ``struct``);
no spreadsheet dependency is needed for the build.
"""
from __future__ import annotations

import csv
import io
import os
import re
import struct
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
# The note may wrap across lines ("Según Clasificador\nde Parentescos" — CPV 2020).
_CATALOG_RE = re.compile(r"seg[uú]n\s+clasificador\s+de\s+([^)]+)", re.IGNORECASE)
# A code labelled "No especificado…"/"No sabe" is a non-response sentinel (``Especiales``).
_SENTINEL_RE = re.compile(r"\bno especificad|^no sabe\b", re.IGNORECASE)
# A numeric code above the valid range that is itself a value: a top-code.
_TOPCODE_RE = re.compile(r"\bmayor(es)? a\b|^más de\b|\by más\b", re.IGNORECASE)
_NULL_CODES = {"nulo"}
# A code row labelled «Blanco (por pase)» marks the blank cell whatever its code (``Nulo``;
# EIC 2015 also writes ``b``).
_BLANK_RE = re.compile(r"^blanco\b", re.IGNORECASE)
# EIC 2015 names a classification catalog in a code row of its own: ``TC_OCUPACION_2015``
# labelled «Descripción por catálogo». Any other label makes the reference a note (a name
# column, the minimum-wage table, ESCOACUM's reference table).
_CATALOG_REF_RE = re.compile(r"^TC_\w+$", re.IGNORECASE)
_CATALOG_DESC_RE = re.compile(r"^descripci[oó]n por cat[aá]logo", re.IGNORECASE)
# Header words that are not codes (folded: ``{Alfanumérico}``, ``Ver catálogo``).
_NOT_CODES = {"alfanumerico", "vercatalogo"}
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
# xls (legacy BIFF8 in an OLE2 compound file; stdlib)
# --------------------------------------------------------------------------------------

_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_END_OF_CHAIN, _FREE_SECT = 0xFFFFFFFE, 0xFFFFFFFF


def _ole_stream(data: bytes, name: str) -> bytes:
    """One stream of an OLE2 compound file ([MS-CFB]), found by name in the directory.

    Handles 512- and 4096-byte sectors, a DIFAT longer than the header's 109 entries and
    streams below the mini-stream cutoff (kept in the root entry's mini stream).
    """
    if data[:8] != _OLE_MAGIC:
        raise ValueError("not an OLE2 compound file (legacy .xls)")
    ssz = 1 << struct.unpack_from("<H", data, 30)[0]
    mssz = 1 << struct.unpack_from("<H", data, 32)[0]
    (n_fat, dir_start, _, cutoff, mfat_start, _, difat_start,
     n_difat) = struct.unpack_from("<8I", data, 44)

    def sector(i: int) -> bytes:  # sector 0 follows the header, which fills one sector
        return data[(i + 1) * ssz:(i + 2) * ssz]

    def chain(start: int, table: list[int], read) -> bytes:
        parts, i, seen = [], start, set()
        while i not in (_END_OF_CHAIN, _FREE_SECT):
            if i in seen or i >= len(table):
                raise ValueError("corrupt OLE2 sector chain")
            seen.add(i)
            parts.append(read(i))
            i = table[i]
        return b"".join(parts)

    difat = list(struct.unpack_from("<109I", data, 76))
    i = difat_start
    for _ in range(n_difat):  # DIFAT sectors: ssz/4 - 1 entries, then the next sector
        s = sector(i)
        difat += struct.unpack_from(f"<{ssz // 4 - 1}I", s)
        i = struct.unpack_from("<I", s, ssz - 4)[0]
    fat: list[int] = []
    for i in difat[:n_fat]:
        fat += struct.unpack_from(f"<{ssz // 4}I", sector(i))

    directory = chain(dir_start, fat, sector)
    entries = []
    for off in range(0, len(directory) - 127, 128):
        e = directory[off:off + 128]
        name_len = struct.unpack_from("<H", e, 64)[0]
        start, size = struct.unpack_from("<IQ", e, 116)
        if ssz == 512:
            size &= 0xFFFFFFFF  # version 3: the high half is undefined
        entries.append((e[:max(name_len - 2, 0)].decode("utf-16-le"), e[66], start, size))
    root_start = entries[0][2]
    for ename, etype, start, size in entries:
        if etype != 2 or ename.lower() != name.lower():
            continue
        if size >= cutoff:
            return chain(start, fat, sector)[:size]
        mini = chain(root_start, fat, sector)
        mfat_bytes = chain(mfat_start, fat, sector)
        mfat = list(struct.unpack_from(f"<{len(mfat_bytes) // 4}I", mfat_bytes))
        return chain(start, mfat, lambda j: mini[j * mssz:(j + 1) * mssz])[:size]
    raise LookupError(f"OLE2 file has no {name!r} stream (only BIFF8 workbooks are read)")


class _BiffReader:
    """Sequential reader over a record's body and its ``CONTINUE`` records, applying the
    BIFF8 rule that a string whose characters cross into a ``CONTINUE`` restarts there
    with a fresh option byte (compressed latin-1 or UTF-16LE characters)."""

    def __init__(self, chunks: list[bytes]):
        self.chunks, self.k, self.p = chunks, 0, 0

    def take(self, n: int) -> bytes:
        out = bytearray()
        while n:
            if self.p >= len(self.chunks[self.k]):
                self.k, self.p = self.k + 1, 0
            got = self.chunks[self.k][self.p:self.p + n]
            out += got
            self.p += len(got)
            n -= len(got)
        return bytes(out)

    def _chars(self, cch: int, wide: bool) -> str:
        out = []
        while cch:
            if self.p >= len(self.chunks[self.k]):  # continued: a new option byte
                self.k, self.p = self.k + 1, 1
                wide = bool(self.chunks[self.k][0] & 1)
            width = 2 if wide else 1
            n = min(cch, (len(self.chunks[self.k]) - self.p) // width)
            raw = self.chunks[self.k][self.p:self.p + n * width]
            out.append(raw.decode("utf-16-le" if wide else "latin-1"))
            self.p += n * width
            cch -= n
        return "".join(out)

    def string(self, len_size: int = 2) -> str:
        """An ``XLUnicodeRichExtendedString`` (``len_size`` 2) or a short string (1):
        length, option byte, optional rich-run count and extension size, characters, then
        the rich runs and extension, which are skipped."""
        cch = int.from_bytes(self.take(len_size), "little")
        flags = self.take(1)[0]
        runs = struct.unpack("<H", self.take(2))[0] if flags & 0x08 else 0
        ext = struct.unpack("<I", self.take(4))[0] if flags & 0x04 else 0
        text = self._chars(cch, bool(flags & 0x01))
        self.take(4 * runs + ext)
        return text


def _rk(v: int) -> float:
    """Decode an ``RK`` number: a 30-bit integer or the high 30 bits of a double,
    optionally divided by 100."""
    if v & 0x02:
        x = v >> 2
        if x & 0x20000000:
            x -= 0x40000000
    else:
        x = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return x / 100 if v & 0x01 else x


def _num_text(x: float) -> str:
    """A cell number as text: integers without a decimal point, else the shortest repr."""
    return str(int(x)) if float(x).is_integer() else repr(x)


def _col_letter(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xls(path: Path | bytes) -> dict[str, list[dict[str, str]]]:
    """:func:`read_xlsx` for a legacy Excel 97–2003 ``.xls`` workbook (BIFF8), same output;
    ``path`` may also be the file's bytes (a ZIP member).

    Reads the ``Workbook`` stream of the OLE2 container, the shared-string table (``SST``,
    split across ``CONTINUE`` records), the worksheets' bounds (``BOUNDSHEET``) and their
    value cells: shared strings (``LABELSST``), inline strings (``LABEL``), numbers
    (``NUMBER``, ``RK``, ``MULRK``) and formulas' cached results (``FORMULA`` + ``STRING``).
    Numbers come back as text (``1``, ``1993.5``). Charts and other sheet types are
    skipped, as are the records of a substream nested in a worksheet (an embedded chart).
    INEGI's dictionaries for the EIC 2015 (and 2010/2005) are ``.xls``.
    """
    data = path if isinstance(path, bytes) else Path(path).read_bytes()
    wb = _ole_stream(data, "Workbook")
    records = []
    pos = 0
    while pos + 4 <= len(wb):
        rid, size = struct.unpack_from("<HH", wb, pos)
        records.append((pos, rid, wb[pos + 4:pos + 4 + size]))
        pos += 4 + size
    index = {pos: k for k, (pos, _, _) in enumerate(records)}

    sheets, sst = [], []
    for k, (_, rid, body) in enumerate(records):
        if rid == 0x0085 and body[5] == 0:  # BOUNDSHEET of a worksheet
            name = _BiffReader([body[6:]]).string(len_size=1)
            sheets.append((struct.unpack_from("<I", body)[0], name))
        elif rid == 0x00FC:  # SST, continued by CONTINUE (0x003C) records
            chunks = [body]
            j = k + 1
            while j < len(records) and records[j][1] == 0x003C:
                chunks.append(records[j][2])
                j += 1
            reader = _BiffReader(chunks)
            n_unique = struct.unpack("<II", reader.take(8))[1]
            sst = [reader.string() for _ in range(n_unique)]

    out: dict[str, list[dict[str, str]]] = {}
    for offset, name in sheets:
        cells: dict[int, dict[str, str]] = {}

        def put(row: int, col: int, text: str) -> None:
            text = text.strip()
            if text:
                cells.setdefault(row, {})[_col_letter(col)] = text

        depth, pending = 0, None
        for _, rid, b in records[index[offset]:]:
            if rid == 0x0809:  # BOF: the sheet's own, or a nested substream
                depth += 1
                continue
            if rid == 0x000A:  # EOF
                depth -= 1
                if depth == 0:
                    break
                continue
            if depth != 1:
                continue
            if rid == 0x00FD:  # LABELSST
                r, c, _, isst = struct.unpack_from("<HHHI", b)
                put(r, c, sst[isst])
            elif rid == 0x0204:  # LABEL
                r, c = struct.unpack_from("<HH", b)
                put(r, c, _BiffReader([b[6:]]).string())
            elif rid == 0x0203:  # NUMBER
                r, c, _, x = struct.unpack_from("<HHHd", b)
                put(r, c, _num_text(x))
            elif rid == 0x027E:  # RK
                r, c, _, v = struct.unpack_from("<HHHI", b)
                put(r, c, _num_text(_rk(v)))
            elif rid == 0x00BD:  # MULRK: row, first col, (xf, rk)*, last col
                r, c0 = struct.unpack_from("<HH", b)
                for t in range((len(b) - 6) // 6):
                    put(r, c0 + t, _num_text(_rk(struct.unpack_from("<I", b, 6 + 6 * t)[0])))
            elif rid == 0x0006:  # FORMULA: the cached result
                r, c = struct.unpack_from("<HH", b)
                res = b[6:14]
                if res[6:8] != b"\xff\xff":
                    put(r, c, _num_text(struct.unpack("<d", res)[0]))
                elif res[0] == 0:  # a string result follows in a STRING record
                    pending = (r, c)
                elif res[0] == 1:
                    put(r, c, "TRUE" if res[2] else "FALSE")
            elif rid == 0x0207 and pending is not None:  # STRING
                put(*pending, _BiffReader([b]).string())
                pending = None
        out[name] = [cells[r] for r in sorted(cells)]
    return out


def read_workbook(path: Path) -> dict[str, list[dict[str, str]]]:
    """:func:`read_xlsx` or :func:`read_xls`, chosen by the file's signature (INEGI's
    ``.xls`` links sometimes serve an ``.xlsx`` and vice versa)."""
    head = Path(path).read_bytes()[:8]
    if head == _OLE_MAGIC:
        return read_xls(path)
    if head[:4] == b"PK\x03\x04":
        return read_xlsx(path)
    raise ValueError(f"{Path(path).name}: neither an .xlsx (ZIP) nor an .xls (OLE2) workbook")


# --------------------------------------------------------------------------------------
# classification catalogs (889463931966_csv.zip: CLAVE,DESCRIPCION[,…])
# --------------------------------------------------------------------------------------

def _xls_rows(raw: bytes) -> list[list[str]]:
    """The first worksheet of an ``.xls`` catalog as rows of cells in column order (a
    missing cell is ``""``)."""
    sheet = next(iter(read_xls(raw).values()), [])
    cols = sorted({c for row in sheet for c in row}, key=lambda c: (len(c), c))
    return [[row.get(c, "") for c in cols] for row in sheet]


def read_catalogs(zip_path: Path) -> dict[str, dict[str, str]]:
    """``{catalog stem: {code: label}}`` from a ZIP of INEGI classification tables.

    The members are CSVs (EIC 2025, CPV 2020) or one-sheet ``.xls`` workbooks (EIC 2015:
    ``TC_PARENTESCO_2015.xls`` …). The code is the concatenation of the ``CLAVE``/
    ``CLAVE_*``/``CVE_*`` columns (``MUNICIPIO.csv`` → entidad+municipio) and the label the
    last ``DESC*`` column (else the last ``NOM*``); codes keep their spelling. A member
    without such columns (EIC 2015's ``TC_ESCOACUM_2015``, a reference table) is skipped.
    """
    out: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            raw = z.read(name)
            if name.lower().endswith(".csv"):
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:  # CPV 2020's catalogs are cp1252
                    text = raw.decode("cp1252")
                rows = list(csv.reader(io.StringIO(text)))
            elif name.lower().endswith(".xls"):
                rows = _xls_rows(raw)
            else:
                continue
            if not rows:
                continue
            header = [h.strip().upper() for h in rows[0]]
            keys = [i for i, h in enumerate(header)
                    if h == "CLAVE" or h.startswith(("CVE", "CLAVE_"))]
            desc = ([i for i, h in enumerate(header) if h.startswith("DESC")]
                    or [i for i, h in enumerate(header) if h.startswith("NOM")])
            if not keys or not desc:
                continue
            stem = Path(name).stem.upper()
            out[stem] = {"".join(r[i].strip() for i in keys): r[desc[-1]].strip()
                         for r in rows[1:] if r and any(x.strip() for x in r)}
    return out


def _words(text: str) -> list[str]:
    """Accent-free lower-case alphanumeric words (``_`` and punctuation separate words)."""
    return re.findall(r"[a-z0-9]+", _fold(text.replace("_", " ")))


def _word_match(w: str, s: str) -> bool:
    """A phrase word names a stem word: equal, or (both ≥ 3 letters) one abbreviates the
    other (``mun``/``municipios``, ``religion``/``religiones``) or they share a ≥ 4-letter
    prefix (``escoacum``/``escolaridad``)."""
    if w == s:
        return True
    if min(len(w), len(s)) < 3:
        return False
    return w.startswith(s) or s.startswith(w) or len(os.path.commonprefix([w, s])) >= 4


def match_catalog(phrase: str, catalogs) -> str | None:
    """The catalog a ``(Según clasificador de <phrase>)`` note refers to: the stem naming
    the most words of the phrase (``entidad federativa y país`` → ``ENTIDAD_PAIS``). Stems
    may abbreviate (CPV 2020: ``MUN``, ``CAUSA_MIG``, ``RELIGION`` for «Religiones») or
    misspell (EIC 2025: ``ESOLARIDAD_ACUMULADA``), so a word counts when it matches by
    :func:`_word_match`. ``None`` when no stem matches a word or two stems tie."""
    words = set(_words(phrase))
    scored = sorted(((sum(any(_word_match(w, x) for x in _words(s)) for w in words), s)
                     for s in catalogs), reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return None
    return scored[0][1]


# --------------------------------------------------------------------------------------
# FD workbook → {stem: {VAR: meta}}
# --------------------------------------------------------------------------------------

def _parse_code(text: str):
    """``'7'`` → ``'7'``; ``'01..54'`` / ``'0101.. 9030'`` / ``'{0001..9999}'`` / ``'0 … 24'``
    → ``(lo, hi, width)``; ``'Nulo'`` → ``None``. ``width`` is the zero-padding (both
    bounds equally long and the lower one padded), else 0."""
    t = re.sub(r"\.{2,}|…", "..", text.replace(" ", "").strip("{}"))
    if t.lower() in _NULL_CODES:
        return None
    if ".." in t:
        a, b = t.split("..", 1)
        if a.lstrip("-").isdigit() and b.lstrip("-").isdigit():
            width = len(a) if len(a) == len(b) and a.startswith("0") else 0
            return int(a), int(b), width
    return t


def _split_codes(text: str) -> list:
    """The codes of one ``Rango válido`` cell, which may list several separated by commas
    and line breaks (``1101..2901,3101,\n3102`` — CPV 2020); ``Nulo`` dropped."""
    parts = text.strip().strip("{}").split(",")
    return [c for c in (_parse_code(x.strip()) for x in parts if x.strip()) if c is not None]


def _header_codes(text: str) -> list:
    """Codes of a ``Rango válido`` header such as ``{1..8, 9, Nulo}`` (catalog note,
    ``Alfanumérico`` and ``Ver catálogo`` dropped)."""
    text = _CATALOG_RE.sub("", text).replace("(", "").replace(")", "")
    inner = text.strip().strip("{}").strip()
    return [c for c in (_parse_code(x) for x in inner.split(",") if x.strip())
            if c is not None and not (isinstance(c, str) and _fold(c) in _NOT_CODES)]


def _num(x: str):
    return int(x) if x.lstrip("-").isdigit() else float(x)


def _code_key(code: str):
    return int(code) if code.isdigit() else code


def _enumerated(var: dict) -> bool:
    """Whether a variable's code rows label, one by one, every code of its header.

    EIC 2015 types its coded items «Numérico» (``SEXO {1,3}``: 1 Hombre, 3 Mujer;
    ``TAMLOC {1…5}``); such a variable is categorical. A quantity has a range row
    (``0..109 Años cumplidos``) or a header range that no row enumerates (EIC 2025 ``EDAD
    {0..130, 999}`` lists only ``0 Menos de un año``).
    """
    rows = var["rows"]
    if not rows or any(isinstance(c, tuple) or not label for c, label in rows):
        return False
    header: set = set()
    for c in _header_codes(var["code"]):
        if isinstance(c, tuple):
            if c[1] - c[0] + 1 > _MAX_EXPAND:
                return False
            header.update(range(c[0], c[1] + 1))
        else:
            header.add(_code_key(c))
    return bool(header) and header <= {_code_key(c) for c, _ in rows}


def _finish(var: dict, catalogs: dict | None) -> dict:
    """Turn a variable's raw code rows into ``parse_ddi``-shaped meta."""
    numeric = _fold(var["tipo"]).startswith("numer") and not _enumerated(var)
    header = var["code"]
    nota = []
    # The catalog note sits in the header, or in a code row of its own (CPV 2020 ESCOACUM).
    phrase = _CATALOG_RE.search(header) or _CATALOG_RE.search(var.get("note", ""))
    catalog = match_catalog(phrase.group(1), catalogs or {}) if phrase else None
    # EIC 2015: the catalog is named (TC_…) in a «Descripción por catálogo» row and
    # enumerates every code of the variable.
    from_ref = False
    for ref, label in var.get("refs", ()):
        stem = next((s for s in (catalogs or {}) if s.upper() == ref.upper()), None)
        if not _CATALOG_DESC_RE.match(label):
            nota.append(f"{label.rstrip('.: ')}: {ref}")
        elif stem and catalog is None:
            catalog, from_ref = stem, True
        elif not stem:
            nota.append(f"clasificador «{ref}» no disponible")
    rows = var["rows"] or [(c, "") for c in _header_codes(header)]
    ranges = [c for c, _ in rows if isinstance(c, tuple)]
    if numeric and not ranges:  # code rows list only labelled values: the header has the range
        ranges = [c for c in _header_codes(header) if isinstance(c, tuple)]
    singles = [(c, lab) for c, lab in rows if isinstance(c, str)]
    cats: dict[str, str] = {}
    special: dict[str, str] = {}
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
        if from_ref:
            cats.update(codes)
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
            else:  # a catalog code listed singly (``3101`` — CPV 2020) keeps its catalog label
                cats[code] = codes.get(code) or label or code
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


def parse_fd(path: Path, catalogs: dict[str, dict[str, str]] | None = None
             ) -> dict[str, dict[str, dict]]:
    """Parse an INEGI FD workbook (``.xlsx`` or legacy ``.xls``, :func:`read_workbook`) →
    ``{sheet stem: {VARNAME: meta}}`` (see module doc).

    Only sheets with a ``Mnemónico`` header are tables; the stem is the lower-cased sheet
    name (``VIVIENDAS`` → ``viviendas``; EIC 2015 ``TR_Vivienda`` → ``tr_vivienda``). A row with a description and a question but no
    mnemonic is a question stem shared by the following items (``En su vida diaria,
    ¿(NOMBRE) cuánta dificultad tiene para:`` → ``ver, aun usando lentes?``); it prefixes
    every item question that starts in lower case, until the next stem or section.
    ``catalogs`` (:func:`read_catalogs`) enumerate the ``Según clasificador`` variables
    (EIC 2015: the ``TC_…`` catalog named in a code row). Rows labelled «Blanco» mark the
    blank cell, whatever their code.
    """
    out: dict[str, dict[str, dict]] = {}
    for sheet, rows in read_workbook(path).items():
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
                current = {**get, "label": label, "rows": [], "refs": []}
                vars_[get["var"]] = current
            elif get["code"] and get["label"] and current is not None:
                if _CATALOG_RE.search(get["code"]):  # "(Según Clasificador de …)" as a row
                    current["note"] = get["code"]
                    continue
                if _CATALOG_REF_RE.match(get["code"]):  # EIC 2015: "TC_OCUPACION_2015"
                    current["refs"].append((get["code"], get["label"]))
                    continue
                if _BLANK_RE.match(get["label"]):
                    continue
                current["rows"] += [(code, get["label"]) for code in _split_codes(get["code"])]
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


def parse_indicator_csv(path: Path, specials: dict[str, str] | None = None
                        ) -> dict[str, dict]:
    """Parse a ``diccionario_datos_*.csv`` → ``{MNEMONIC: meta}``.

    ``Rangos`` such as ``0 … 100.00`` make a numeric indicator (``Decimales`` from the
    upper bound); zero-padded code ranges (``00…32``) and ``Alfanumérico`` make a string.
    The table's footnotes ``XX: label.`` are the non-numeric cell codes → ``Especiales`` of
    every numeric indicator, together with ``specials`` — the codes an edition uses without
    declaring them (CPV 2020's ITER/AGEB dictionaries have no footnotes for their ``*``
    cells); a footnote's label wins. The indicator ranges are kept verbatim (``Rangos``) but not
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
    special = dict(specials or {})
    for r in rows[head + 1:]:
        m = _NOTE_RE.match((r[0] if r else "").strip())
        if m:
            special[m["code"]] = m["label"]
    out: dict[str, dict] = {}
    for r in rows[head + 1:]:
        if len(r) <= col["mnemonico"] or not r[col["mnemonico"]].strip():
            continue
        rng = " ".join(r[col["rangos"]].split())
        # "0 … 100.00", "00...32"; CPV 2020 also has the typo "0.,.999999999"
        bounds = [b for b in re.split(r"\s*(?:…|[.,]{2,})\s*", rng) if b]
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
