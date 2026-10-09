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
``ElementTree``; :func:`read_xls`: the OLE2 container and BIFF8 — or Excel 95's BIFF5,
INEGI's CGPV 2000 tabulados — records with ``struct``); no spreadsheet dependency is needed
for the build.
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

import _dbf
import _dict_ddi as ddi

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")

# FD column headers → meta fields (header text compared after accent/case folding).
_FD_HEADERS = {"descripcion": "desc", "mnemonico": "var", "pregunta y categoria": "label",
               "tipo": "tipo", "rango valido": "code", "longitud": "len",
               # Conteo 2005 ("FD Y DESCRIPCIÓN DE LOS MNEMÓNICOS"): the header range, the
               # codes and their labels, the mnemonic and the catalog in columns of their own
               "nombre de la variable": "desc", "descripcion del mnemonico": "defn",
               "rangos validos": "hdr", "rango o codigo a describir": "code",
               "descripcion de los codigos en la base de datos": "label",
               "mnemonico en la base de datos": "var", "catalogo": "cat"}
_FIELDS = tuple(dict.fromkeys(_FD_HEADERS.values()))
# A code row that points at a classification instead of labelling codes (Conteo 2005:
# «Ver clasificación de Entidades»).
_SEE_CATALOG_RE = re.compile(r"^ver clasificaci[oó]n", re.IGNORECASE)
# The note may wrap across lines ("Según Clasificador\nde Parentescos" — CPV 2020).
_CATALOG_RE = re.compile(r"seg[uú]n\s+clasificador\s+de\s+([^)]+)", re.IGNORECASE)
# A code labelled "No especificado…"/"No sabe" is a non-response sentinel (``Especiales``).
_SENTINEL_RE = re.compile(r"\bno especificad|^no sabe\b(?!\s+(leer|escribir|hablar))",
                          re.IGNORECASE)    # «No sabe leer y escribir» is an answer
# A numeric code above the valid range that is itself a value: a top-code.
_TOPCODE_RE = re.compile(r"\bmayor(es)? a\b|^más de\b|\by más\b|^\d+\s+\w+\s+o\s+más\b",
                         re.IGNORECASE)   # the last: Conteo 1995 «98 años o más»
_NULL_CODES = {"nulo", "b"}    # CPV 2010/EIC 2015 write the blank cell "b" («Blanco por pase»)
# A code row labelled «Blanco (por pase)» marks the blank cell whatever its code (``Nulo``;
# EIC 2015 also writes ``b``).
_BLANK_RE = re.compile(r"^blanco\b", re.IGNORECASE)
# EIC 2015 names a classification catalog in a code row of its own: ``TC_OCUPACION_2015``
# labelled «Descripción por catálogo». Any other label makes the reference a note (a name
# column, the minimum-wage table, ESCOACUM's reference table).
_CATALOG_REF_RE = re.compile(r"^TC_\w+$", re.IGNORECASE)
_CATALOG_DESC_RE = re.compile(r"^descripci[oó]n por cat[aá]logo", re.IGNORECASE)
# The vertical ellipsis between the first and last rows of an enumeration (Conteo 2005:
# «1 Un grado aprobado», «: :», «8 Ocho grados aprobados»; its catalog has every code).
_ELLIPSIS_RE = re.compile(r"^[:.…⋮]+$")
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
# xls (legacy BIFF8, or Excel 95's BIFF5, in an OLE2 compound file; stdlib)
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
    raise LookupError(f"OLE2 file has no {name!r} stream")


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


# BIFF5 writes its strings in the workbook's code page (the CODEPAGE record): a Windows code
# page number, except for these.
_CODEPAGES = {367: "ascii", 1200: "utf-16-le", 10000: "mac_roman", 32768: "mac_roman",
              32769: "cp1252"}
_BIFF5, _BIFF8 = 0x0500, 0x0600


class _Biff5Reader:
    """:class:`_BiffReader`'s interface for BIFF5: a string is a byte count and that many
    bytes in the workbook's code page, without an option byte (no ``CONTINUE`` split)."""

    def __init__(self, body: bytes, codec: str):
        self.body, self.p, self.codec = body, 0, codec

    def string(self, len_size: int = 2) -> str:
        n = int.from_bytes(self.body[self.p:self.p + len_size], "little")
        self.p += len_size + n
        return self.body[self.p - n:self.p].decode(self.codec, errors="replace")


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
    """:func:`read_xlsx` for a legacy Excel 97–2003 ``.xls`` workbook (BIFF8) or an Excel
    5.0/95 one (BIFF5), same output; ``path`` may also be the file's bytes (a ZIP member).

    Reads the ``Workbook`` stream of the OLE2 container (BIFF5: ``Book``), the shared-string
    table (``SST``, split across ``CONTINUE`` records), the worksheets' bounds
    (``BOUNDSHEET``) and their value cells: shared strings (``LABELSST``), inline strings
    (``LABEL``, ``RSTRING``), numbers (``NUMBER``, ``RK``, ``MULRK``) and formulas' cached
    results (``FORMULA`` + ``STRING``). Numbers come back as text (``1``, ``1993.5``).
    Charts and other sheet types are skipped, as are the records of a substream nested in a
    worksheet (an embedded chart). BIFF5 has no shared strings: its strings are 8-bit, in
    the code page of the ``CODEPAGE`` record (:data:`_CODEPAGES`; cp1252 when absent).
    INEGI's dictionaries for the EIC 2015 (and 2010/2005) are BIFF8 ``.xls``; the CGPV
    2000 tabulados are BIFF5.
    """
    data = path if isinstance(path, bytes) else Path(path).read_bytes()
    try:
        wb = _ole_stream(data, "Workbook")
    except LookupError:
        try:
            wb = _ole_stream(data, "Book")
        except LookupError:
            raise LookupError("OLE2 file has no 'Workbook' (BIFF8) or 'Book' (BIFF5) "
                              "stream") from None
    records = []
    pos = 0
    while pos + 4 <= len(wb):
        rid, size = struct.unpack_from("<HH", wb, pos)
        records.append((pos, rid, wb[pos + 4:pos + 4 + size]))
        pos += 4 + size
    index = {pos: k for k, (pos, _, _) in enumerate(records)}
    if not records or records[0][1] != 0x0809 or len(records[0][2]) < 2:
        raise ValueError("not a BIFF5/BIFF8 workbook stream (no BOF record first)")
    version = struct.unpack_from("<H", records[0][2])[0]
    if version not in (_BIFF5, _BIFF8):
        raise ValueError(f"unsupported BIFF version {version:#06x} (BIFF5/BIFF8 only)")
    codec = "cp1252"
    if version == _BIFF5:
        for _, rid, body in records:
            if rid == 0x0042:  # CODEPAGE
                cp = struct.unpack_from("<H", body)[0]
                codec = _CODEPAGES.get(cp, f"cp{cp}")
                break

    def text_reader(body: bytes):
        return _Biff5Reader(body, codec) if version == _BIFF5 else _BiffReader([body])

    sheets, sst = [], []
    for k, (_, rid, body) in enumerate(records):
        if rid == 0x0085 and body[5] == 0:  # BOUNDSHEET of a worksheet
            name = text_reader(body[6:]).string(len_size=1)
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
            elif rid in (0x0204, 0x00D6):  # LABEL; RSTRING (BIFF5: rich runs follow)
                r, c = struct.unpack_from("<HH", b)
                put(r, c, text_reader(b[6:]).string())
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
                put(*pending, text_reader(b).string())
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


def _catalog_from_rows(rows: list[list[str]], lead_keys: bool = False
                       ) -> dict[str, str] | None:
    """One classification table → ``{code: label}``, or ``None`` when it is not one.

    The code is the concatenation of the ``CLAVE``/``CLAVE_*``/``CVE_*`` columns
    (``MUNICIPIO.csv`` → entidad+municipio) and the label the last ``DESC*`` column (else
    the last ``NOM*``); codes keep their spelling. With ``lead_keys`` (Conteo 2005's
    workbook, whose sheets are all catalogs), a table with no such key column keys on the
    columns before its ``DESC*`` column (``NIVANTES | DESC``, ``ENT | MUN | DESC``) when
    those codes are unique — a reference table repeating codes (``TC_ESCOACUM``) is not a
    catalog."""
    if not rows:
        return None
    if lead_keys and rows[0] and rows[0][0].strip().isdigit():
        # CGPV 1990 catalogos_1990.xls: no header row, code | label; a code repeated for
        # its synonyms (CATPAREN: 301 Hijo(a), 301 Hijastro(a)…) keeps its first label
        table: dict[str, str] = {}
        for r in rows:
            if r and r[0].strip():
                table.setdefault(r[0].strip(), next((c.strip() for c in r[1:] if c.strip()), ""))
        return table
    header = [h.strip().upper() for h in rows[0]]
    body = [r for r in rows[1:] if r and any(x.strip() for x in r)]
    keys = [i for i, h in enumerate(header) if h == "CLAVE" or h.startswith(("CVE", "CLAVE_"))]
    desc = ([i for i, h in enumerate(header) if h.startswith("DESC")]
            or [i for i, h in enumerate(header) if h.startswith("NOM")])
    if lead_keys and not keys and desc and desc[-1] > 0 and header[desc[-1]].startswith("DESC"):
        lead = list(range(desc[-1]))          # Conteo 2005: NIVANTES | DESC; ENT | MUN | DESC
        codes = ["".join(r[i].strip() for i in lead) for r in body]
        if all(header[i] for i in lead) and len(codes) == len(set(codes)):
            keys = lead
    if not keys or not desc:
        return None
    table = {"".join(r[i].strip() for i in keys): r[desc[-1]].strip() for r in body}
    table.pop("", None)                       # Conteo 2005: the blank cell's row has no code
    return table


def read_catalogs(path: Path) -> dict[str, dict[str, str]]:
    """``{catalog stem: {code: label}}`` from INEGI's classification tables
    (:func:`_catalog_from_rows`).

    ``path`` is a ZIP whose members are CSVs (EIC 2025, CPV 2020), one-sheet ``.xls``
    workbooks (EIC 2015: ``TC_PARENTESCO_2015.xls`` …) or DBF tables (CPV 2010:
    ``TC_PARENTESCO_2010.DBF`` …, :mod:`_dbf`) — the stem is the member's name — or one
    ``.xls`` workbook with a sheet per catalog (Conteo 2005: ``catalogos_muestra_2005.xls``,
    sheets ``TC_ENTID``, ``TC_PAREN`` …) — the stem is the sheet's name. A table that is not
    a catalog (EIC 2015's ``TC_ESCOACUM_2015``, a reference table) is skipped.
    """
    out: dict[str, dict[str, str]] = {}
    path = Path(path)
    if path.suffix.lower() == ".xls":
        for sheet, rows in read_xls(path).items():
            cols = sorted({c for row in rows for c in row}, key=lambda c: (len(c), c))
            table = _catalog_from_rows([[row.get(c, "") for c in cols] for row in rows],
                                       lead_keys=True)
            if table is not None:
                out[sheet.strip().upper()] = table
        return out
    with zipfile.ZipFile(path) as z:
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
            elif name.lower().endswith(".dbf"):
                table = _dbf.read_dbf(raw).table
                rows = [table.column_names] + [[v or "" for v in r.values()]
                                               for r in table.to_pylist()]
            else:
                continue
            table = _catalog_from_rows(rows)
            if table is not None:
                out[Path(name).stem.upper()] = table
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
    elif m := re.fullmatch(r"(\d+)-(\d+)", t):   # Conteo 2005: "201-204", "001-033"
        a, b = m.groups()
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


def _quantity(var: dict, catalog: str | None = None) -> bool:
    """For an FD without a ``Tipo`` column (CPV 2010): whether a variable is a number.

    It is when a code row is a labelled range (``01..25 Número de dormitorios``,
    ``{000001..999997} Ingresos especificados``) or, with no code rows, when its header
    holds a range plus a sentinel (``EDAD {000..130,999}``) or an unpadded range (``MPERA
    {0..99}``). A zero-padded header range alone is a code space (``ENT {01..32}``,
    ``MUN {001..570}``); single labelled codes are categories. A range labelled «Ver
    clasificación de …» (Conteo 2005) is a code space too. A variable with a resolved
    ``catalog`` is a number only through a labelled range row (Conteo 2005 attaches a
    catalog even to counts: ``Cuardom`` → ``TC_NUMCD``). Several labelled ranges, or a
    header with several ranges, make a code list (CGPV 2000: ``LNACEDO_C`` 001-032 Clave de
    entidad / 100-535 Clave de país; ``OTROPARE_C {100,200,300,401-412,…,999}``); a single
    code next to the one range is a value (``FECNACA {1929,1930..2000,9999}``: 1929 = «1929
    y antes»).
    """
    ranged = [c for c, label in var["rows"]
              if isinstance(c, tuple) and label and not _SEE_CATALOG_RE.match(label)
              and "catalogo" not in _fold(label)]
    if ranged:
        return len(ranged) == 1
    codes = _header_codes(var["code"])
    ranges = [c for c in codes if isinstance(c, tuple)]
    if var["rows"] and not catalog and len(ranges) == 1 and all(
            isinstance(c, str) and c.isdigit() and int(c) > ranges[0][1]
            for c, _ in var["rows"]):
        return True            # the rows list only sentinels above the range (1990 EDAD)
    if var["rows"] or catalog:
        return False
    return len(ranges) == 1 and (len(codes) > 1 or not ranges[0][2])


def _finish(var: dict, catalogs: dict | None) -> dict:
    """Turn a variable's raw code rows into ``parse_ddi``-shaped meta."""
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
    if var.get("typed", True):
        numeric = _fold(var["tipo"]).startswith("numer") and not _enumerated(var)
    else:
        numeric = _quantity(var, catalog)
    rows = var["rows"] or [(c, "") for c in _header_codes(header)]
    ranges = [c for c, _ in rows if isinstance(c, tuple)]
    if numeric and not ranges:  # code rows list only labelled values: the header has the range
        ranges = [c for c in _header_codes(header) if isinstance(c, tuple)]
    singles = [(c, lab) for c, lab in rows if isinstance(c, str)]
    if numeric and not var.get("typed", True):
        # FDs without a Tipo column list some sentinels only in the header range
        # (CGPV 2000: HIJFAL {00..25,99,b} has code rows for 00 and 01-25 only)
        listed = {c for c, _ in singles}
        singles += [(c, "") for c in _header_codes(header)
                    if isinstance(c, str) and c not in listed]
    cats: dict[str, str] = {}
    special: dict[str, str] = {}
    meta = {"Descripción": var["desc"], "Pregunta": var["label"],
            "Tipo": "numeric" if numeric else "string", "Longitud": var["len"],
            "Rango": [], "Categorías": cats, "Especiales": special}
    if var.get("defn"):                   # Conteo 2005: the mnemonic's definition
        meta["Definición"] = " ".join(var["defn"].split())

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
            else:  # a catalog code listed singly (``3101`` — CPV 2020) keeps its catalog
                # label, unless the FD spells the same words better (Conteo 2005's catalogs
                # are in capitals: CASA INDEPENDIENTE / Casa independiente)
                same = label and _fold(label) == _fold(codes.get(code) or "")
                cats[code] = label if same else codes.get(code) or label or code
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


def _code_row(var: dict, code: str, label: str) -> None:
    """Add one code row to ``var``: a catalog note (CPV 2020), a ``TC_…`` catalog reference
    (EIC 2015), the blank row or an ellipsis (both skipped) or codes with their label."""
    if _CATALOG_RE.search(code):          # "(Según Clasificador de …)" as a row
        var["note"] = code
    elif _CATALOG_REF_RE.match(code):     # EIC 2015: "TC_OCUPACION_2015"
        var["refs"].append((code, label))
    elif not _BLANK_RE.match(label) and not _ELLIPSIS_RE.match(code.strip()):
        var["rows"] += [(c, label) for c in _split_codes(code)]


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
        typed = "tipo" in cols                # CPV 2010's FD has no Tipo column
        split = "hdr" in cols                 # Conteo 2005: header range and codes apart
        for row in rows[i + 1:]:
            get = {field: row.get(cols[field], "") if field in cols else ""
                   for field in _FIELDS}
            if _VARNAME_RE.match(get["var"]):
                if split:   # the variable row carries its first code and label
                    current = {**get, "code": get["hdr"], "label": "", "rows": [],
                               "refs": [], "typed": typed}
                    if get["cat"]:
                        current["refs"].append((get["cat"], "Descripción por catálogo"))
                    vars_[get["var"]] = current
                    if get["code"] and get["label"]:
                        _code_row(current, get["code"], get["label"])
                    continue
                label = get["label"]
                if stem and label[:1].islower():
                    label = f"{stem} {label}"
                current = {**get, "label": label, "rows": [], "refs": [], "typed": typed}
                vars_[get["var"]] = current
            elif get["code"] and get["label"] and current is not None:
                _code_row(current, get["code"], get["label"])
            elif get["desc"] and get["label"] and not get["code"]:
                stem, current = get["label"], None
            elif not any(get.values()):  # a section title (outside the table columns)
                stem, current = None, None
        out[sheet.strip().lower()] = {v: _finish(m, catalogs) for v, m in vars_.items()}
    return out


# --------------------------------------------------------------------------------------
# CGPV 2000: the FD is a PDF whose annex lists each file's variables as text
# --------------------------------------------------------------------------------------

# «Descripción de las variables de explotación del archivo de vivienda y hogares (VIVHOG)»
_PDF_SECTION_RE = re.compile(r"Descripci[oó]n de las variables de explotaci[oó]n del "
                             r"archivo de[^()]*\(\s*([A-Z]+)\s*\)")
# A variable header once its lines are joined: «16 Número de cuartos dormitorio 5A CUADORM
# {01..25,99} 2» (the question number is optional; the mnemonic precedes the range list).
_PDF_VAR_RE = re.compile(r"^(?P<num>\d+)\s+(?P<desc>.*?)\s+(?:(?P<preg>\d+[A-Z]?)\s+)?"
                         r"(?P<var>[A-Z][A-Z0-9_]*)\s*\{(?P<codes>[^}]*)\}\s*(?:\d+/\s*)?"
                         r"(?P<len>\d+)?\s*$", re.DOTALL)
# A range list that wraps puts the length column's value on its first line, inside the
# list: «{100,200,300,401 -412,420,430, 3» / «440,501-503, 601-624,999}» (OTROPARE_C).
_PDF_INNER_LEN_RE = re.compile(r",\s*(\d{1,2})\s+(?=\d)")
_PDF_CODE_RE = re.compile(r"^\s+(?P<code>\d+(?:\s*-\s*\d+)?|b)\s+(?P<label>\S.*)$")


def _pdf_header(lines: list[str]) -> dict | None:
    """Parse a variable header spread over ``lines`` (a wrapped mnemonic such as
    ``DOTAGUA`` / ``D`` is rejoined)."""
    text = " ".join(x.strip() for x in lines)
    text = re.sub(r"\b([A-Z][A-Z0-9_]{3,}) ([A-Z0-9_]{1,2}) \{", r"\1\2 {", text)
    m = _PDF_VAR_RE.match(text)
    if not m:
        return None
    codes, length = m["codes"], m["len"]
    if length is None:
        inner = _PDF_INNER_LEN_RE.search(codes)
        if inner is None:
            return None
        length, codes = inner.group(1), codes[:inner.start()] + "," + codes[inner.end():]
    return {"var": m["var"], "desc": " ".join(m["desc"].split()), "label": "",
            "code": "{" + " ".join(codes.split()) + "}", "len": length, "tipo": "",
            "rows": [], "refs": [], "typed": False}


def parse_fd_pdf(path: Path | bytes,
                 catalogs: dict | None = None) -> dict[str, dict[str, dict]]:
    """Parse the CGPV 2000 FD (``fd_muestra_censal_2000.pdf``, a path or its bytes, read
    with ``pypdf``) into ``{file tag (vivhog/per/min): {VAR: meta}}`` — the shape of
    :func:`parse_fd`.

    The annex describes each file in a section «Descripción de las variables de explotación
    del archivo de … (VIVHOG|PER|MIN)»; a file described twice keeps its last section. A
    variable header starts at the line's first column with its number and may wrap (the
    range list too); indented lines are code rows (``1 Hombre``, ``001-032 Clave de
    entidad``, ``b Blanco por pase``) whose labels may wrap; an all-capitals line is a
    section title. The variables then go through :func:`_finish` as an FD without a
    ``Tipo`` column (:func:`_quantity` decides the numbers).
    """
    from pypdf import PdfReader

    source = io.BytesIO(path) if isinstance(path, bytes) else str(path)
    text = "\n".join(page.extract_text() for page in PdfReader(source).pages)
    return parse_fd_text(text, catalogs)


def parse_fd_text(text: str, catalogs: dict | None = None) -> dict[str, dict[str, dict]]:
    """:func:`parse_fd_pdf` on the PDF's extracted text."""
    starts = list(_PDF_SECTION_RE.finditer(text))
    out: dict[str, dict[str, dict]] = {}
    for k, start in enumerate(starts):
        end = starts[k + 1].start() if k + 1 < len(starts) else len(text)
        vars_: dict[str, dict] = {}
        header: list[str] = []
        current = None
        last_label: list | None = None
        for line in text[start.end():end].splitlines():
            if not line.strip():
                continue
            if header:                                   # finishing a wrapped header
                header.append(line)
                if (var := _pdf_header(header)) is not None:
                    vars_[var["var"]], current, last_label, header = var, var, None, []
                elif len(header) > 12:
                    header = []
                continue
            if re.match(r"^\d+\s", line):                # a new variable
                header = [line]
                if (var := _pdf_header(header)) is not None:
                    vars_[var["var"]], current, last_label, header = var, var, None, []
                continue
            m = _PDF_CODE_RE.match(line)
            if m and current is not None:
                code = m["code"].replace(" ", "")
                last_label = [code, m["label"].strip()]
                current["rows"].append(last_label)
            elif current is not None and last_label is not None:
                words = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", line)
                if words and words == words.upper():       # a section title
                    last_label = None
                else:
                    last_label[1] = f"{last_label[1]} {line.strip()}"
        for var in vars_.values():
            raw, var["rows"] = var["rows"], []
            for code, label in raw:
                _code_row(var, code.replace("-", ".."), " ".join(label.split()))
        out[start.group(1).lower()] = {v: _finish(m, catalogs) for v, m in vars_.items()}
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
        # a zero-padded lower bound is a code space (00…32, 001..570), except an all-zeros
        # one up to all nines: Conteo 2005 writes every count as 00..9999999999
        numeric = (len(bounds) == 2 and all(re.fullmatch(r"-?\d+(\.\d+)?", b) for b in bounds)
                   and (not (len(bounds[0]) > 1 and bounds[0].startswith("0"))
                        or (re.fullmatch(r"0+", bounds[0]) is not None
                            and re.fullmatch(r"9{5,}", bounds[1]) is not None)))
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
# The 1990/1995 ITER descriptors: a table in a PDF («Estructura de la tabla FD ITER…»)
# --------------------------------------------------------------------------------------

# The columns of the descriptor table, by their header words.
_ITER_FD_HEADER = ("No.", "Categoría", "Descripción", "Mnemónico", "Rango", "Long.")
# Section titles printed across the table (not part of any row).
_ITER_FD_TITLES = {"identificacion geografica", "relacion de indicadores"}


def pdf_words(path: Path) -> str:
    """The word boxes of a PDF as ``pdftotext -tsv`` writes them (poppler). INEGI's
    1990/1995 descriptors are AES-encrypted with an empty password, which ``pypdf`` reads
    only with the ``cryptography`` package; poppler reads them as they are."""
    import shutil
    import subprocess

    exe = shutil.which("pdftotext")
    if exe is None:
        raise RuntimeError("pdftotext (poppler-utils) is required to read the 1990/1995 ITER "
                           "descriptors: install poppler (brew install poppler / apt install "
                           "poppler-utils)")
    return subprocess.run([exe, "-tsv", str(path), "-"], check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout


def parse_iter_fd_tsv(tsv: str, align: str = "top") -> list[dict[str, str]]:
    """The rows of an ITER descriptor table from its word boxes (:func:`pdf_words`):
    ``[{Núm., Indicador, Descripción, Mnemónico, Rangos, Longitud}]`` in table order — the
    columns of INEGI's later ``diccionario_datos_*.csv``.

    Per page, the column edges come from the header words (``No.``, ``Categoría``,
    ``Mnemónico``, ``Rango``, ``Long.``) and the left edges most lines share (the indicator
    and description cells are left-aligned). A row is anchored on its number in the ``No.``
    column. Its mnemonic, range and length are the words of those columns nearest to it.
    Its indicator and description lines join it by ``align``:
    - ``"top"`` (CGPV 1990): the number sits on a cell's first line, so a line belongs to
      the last row at or above it, also across a page break;
    - ``"center"`` (Conteo 1995): cells are centred on the number, so each column of a page
      splits into contiguous runs of lines, one per row, the split that best centres every
      run on its number (:func:`_centred_runs`).

    The header row, the section titles (:data:`_ITER_FD_TITLES`) and everything from the
    closing «Total de caracteres» line down (footnotes) are left out.
    """
    from collections import Counter, defaultdict

    words = []
    for line in tsv.splitlines()[1:]:
        f = line.split("\t")
        if len(f) >= 12 and f[0] == "5" and f[11].strip():
            words.append({"page": int(f[1]), "key": (int(f[1]), int(f[3]), int(f[2]), int(f[4])),
                          "x": float(f[6]), "y": float(f[7]), "h": float(f[9]),
                          "c": float(f[7]) + float(f[9]) / 2,      # vertical centre
                          "text": f[11]})
    by_page = defaultdict(list)
    for w in words:
        by_page[w["page"]].append(w)
    anchors: list[dict] = []                 # in reading order
    fragments: list[tuple] = []              # (page, y, x, column, text)
    for page in sorted(by_page):
        ws = by_page[page]
        hdr = {w["text"]: w for w in ws if w["text"] in _ITER_FD_HEADER}
        if not {"No.", "Categoría", "Mnemónico", "Rango", "Long."} <= set(hdr):
            continue
        top = max(w["y"] + w["h"] for w in hdr.values()) + 1
        end = min((w["y"] for i, w in enumerate(ws) if w["text"] == "Total"
                   and [x["text"] for x in ws[i + 1:i + 3]] == ["de", "caracteres"]),
                  default=float("inf"))
        ws = [w for w in ws if top < w["y"] < end - 1]
        lefts = Counter(round(w["x"]) for w in ws)
        x_mnem, x_rango, x_long = hdr["Mnemónico"]["x"], hdr["Rango"]["x"], hdr["Long."]["x"]
        x_desc = max((x for x in lefts if hdr["Categoría"]["x"] + 40 < x < x_mnem - 40),
                     key=lambda x: (lefts[x], -x))
        x_name = max((x for x in lefts if hdr["No."]["x"] + 5 < x < x_desc - 40),
                     key=lambda x: (lefts[x], -x))
        cells = {"mnem": [], "rango": [], "long": []}
        lines = defaultdict(list)
        for w in ws:
            if w["x"] < x_name - 3:
                if w["text"].isdigit():
                    anchors.append({"page": page, "y": w["c"], "num": w["text"]})
            elif w["x"] < x_desc - 3:
                lines[w["key"]].append(("name", w))
            elif w["x"] < x_mnem - 30:
                lines[w["key"]].append(("desc", w))
            elif w["x"] < x_rango - 30:
                cells["mnem"].append(w)
            elif w["x"] < x_long - 10:
                cells["rango"].append(w)
            else:
                cells["long"].append(w)
        for parts in lines.values():
            text = " ".join(w["text"] for _, w in parts)
            if _fold(text) in _ITER_FD_TITLES:
                continue
            for col in ("name", "desc"):
                col_words = [w for c, w in parts if c == col]
                if col_words:
                    fragments.append((page, col_words[0]["c"], col_words[0]["x"], col,
                                      " ".join(w["text"] for w in col_words)))
        for a in (a for a in anchors if a["page"] == page):
            for col, cands in cells.items():
                near = min(cands, key=lambda w: abs(w["c"] - a["y"]), default=None)
                a[col] = near["text"] if near is not None and abs(near["c"] - a["y"]) < 40 else ""
    rows = {id(a): {"name": [], "desc": []} for a in anchors}
    if align == "top":
        for page, y, x, col, text in sorted(fragments):
            above = [a for a in anchors if (a["page"], a["y"] - 3) <= (page, y)]
            if above:
                rows[id(above[-1])][col].append(text)
    else:
        for page in sorted({a["page"] for a in anchors}):
            same = sorted((a for a in anchors if a["page"] == page), key=lambda a: a["y"])
            for col in ("name", "desc"):
                frags = sorted((y, x, text) for p, y, x, c, text in fragments
                               if p == page and c == col)
                runs = _centred_runs([y for y, _, _ in frags], [a["y"] for a in same])
                for a, (i, j) in zip(same, runs):
                    rows[id(a)][col] += [text for _, _, text in frags[i:j]]
    def join(parts: list[str]) -> str:
        # a word hyphenated at a line end joins without a space («político-» «administrativa»)
        text = re.sub(r"(?<=\w)- (?=[a-záéíóúñ])", "-", " ".join(parts))
        return " ".join(text.split())

    out = []
    for a in sorted(anchors, key=lambda a: int(a["num"])):
        out.append({"Núm.": a["num"], "Indicador": join(rows[id(a)]["name"]),
                    "Descripción": join(rows[id(a)]["desc"]),
                    "Mnemónico": a.get("mnem", ""), "Rangos": a.get("rango", ""),
                    "Longitud": a.get("long", "")})
    return out


def _centred_runs(ys: list[float], anchors: list[float]) -> list[tuple[int, int]]:
    """Split lines at heights ``ys`` (sorted) into one contiguous run per anchor (sorted),
    minimizing Σ |mean height of the run − its anchor's height| (an empty run costs 50 pt):
    the cells of a vertically centred table. Returns ``[(start, end)]`` slices."""
    n, m, empty = len(ys), len(anchors), 50.0
    prefix = [0.0]
    for y in ys:
        prefix.append(prefix[-1] + y)

    def cost(i: int, j: int, k: int) -> float:
        return empty if i == j else abs((prefix[j] - prefix[i]) / (j - i) - anchors[k])

    inf = float("inf")
    best = [[inf] * (n + 1) for _ in range(m + 1)]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    for k in range(1, m + 1):
        for j in range(n + 1):
            for i in range(j + 1):
                c = best[k - 1][i] + cost(i, j, k - 1)
                if c < best[k][j]:
                    best[k][j], back[k][j] = c, i
    runs, j = [], n
    for k in range(m, 0, -1):
        i = back[k][j]
        runs.append((i, j))
        j = i
    return runs[::-1]


def write_indicator_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Write :func:`parse_iter_fd_tsv` rows as a ``diccionario_datos_*.csv`` (UTF-8), the
    format :func:`parse_indicator_csv` reads."""
    cols = ["Núm.", "Indicador", "Descripción", "Mnemónico", "Rangos", "Longitud"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])


# --------------------------------------------------------------------------------------
# The 1990 and 1995 microdata FDs: text tables in (encrypted) PDFs
# --------------------------------------------------------------------------------------

def pdf_text(path: Path) -> str:
    """A PDF's text with its layout (``pdftotext -layout``, poppler; see :func:`pdf_words`)."""
    import shutil
    import subprocess

    exe = shutil.which("pdftotext")
    if exe is None:
        raise RuntimeError("pdftotext (poppler-utils) is required to read the 1990/1995 FDs")
    return subprocess.run([exe, "-layout", str(path), "-"], check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout


def _fd_var(name: str, desc: str, code: str, length: str) -> dict:
    return {"var": name, "desc": " ".join(desc.split()), "label": "", "code": code,
            "len": length, "tipo": "", "rows": [], "refs": [], "typed": False}


def _range_header(text: str) -> str:
    """A 1990 «RANGO VALIDO» cell → the ``{…}`` header of the other FDs: ``01..05 Y 09`` →
    ``{01..05,09}``, ``1Y2`` → ``{1,2}``; ``VER CATÁLOGO`` or nothing → ``{}``."""
    text = " ".join(text.split())
    if not text or _fold(text).startswith("ver catalogo"):
        return "{}"
    parts = re.split(r"\s*,\s*|\s*\bY\b\s*|(?<=\d)Y(?=\d)", text)
    return "{" + ",".join(p for p in parts if p) + "}"


# CGPV 1990: the variable table «No MNEMONICO DESCRIPCION LONGITUD RANGO VALIDO»…
_FD90_VAR_RE = re.compile(r"^(?P<num>\d{2})\s+(?P<var>[A-Z][A-Z0-9_]*)\s+(?P<desc>\S.*?)\s{2,}"
                          r"(?P<len>\d+)(?:\s{2,}(?P<range>\S.*?))?\s*$")
# … then a section per variable: «12 TAM_DUERME 0 NO DISPONE DE COCINA», code rows «  3 SI»
_FD90_SECTION_RE = re.compile(r"^(?P<num>\d{2})\s+(?P<title>\S.*?)\s*$")
_FD90_INLINE_RE = re.compile(r"^(?P<title>[A-Z][A-Z0-9_]*)\s+(?P<code>\d+)\s+(?P<label>\S.*)$")
_FD90_CODE_RE = re.compile(r"^\s+(?P<code>\d+)\s+(?P<label>\S.*)$")
_FD_CATALOG_NOTE_RE = re.compile(r"\((CAT[A-Z0-9]+)(?:\.\w+)?\)")


def parse_fd_1990_text(text: str, catalogs: dict | None = None) -> dict[str, dict[str, dict]]:
    """Parse the CGPV 1990 sample FD (``fd_cgpv1990.pdf`` as :func:`pdf_text` lays it out)
    → ``{"personas": {VAR: meta}}``.

    The document lists the variables in a table (number, mnemonic, description, length,
    valid range such as ``01..05 Y 09``, ``1,2 Y 9``, ``VER CATÁLOGO``), then one section per
    variable number with its codes (``1 LAMINA DE CARTON``; the first code may share the
    section's line). A section naming a catalog (``CLAVE DE MUNICIPIO (CATMUN00)``) points
    the variable at that sheet of ``catalogos_1990.xls`` (``catalogs``). Labels that wrap
    are rejoined. The variables go through :func:`_finish` as an FD without ``Tipo``.
    """
    lines = text.splitlines()
    split = next((i for i, l in enumerate(lines) if "SE DESCRIBEN A CONTINUACION" in l),
                 len(lines))
    by_num: dict[str, dict] = {}
    last = None
    for line in lines[:split]:
        m = _FD90_VAR_RE.match(line)
        if m:
            last = by_num[m["num"]] = _fd_var(m["var"], m["desc"],
                                              _range_header(m["range"] or ""), m["len"])
            last["range_text"] = m["range"] or ""
        elif last is not None and line.strip().isdigit() and last["range_text"]:
            last["range_text"] += line.strip()          # «00000000..99999» + «999»
            last["code"] = _range_header(last["range_text"])
    current, row = None, None
    for line in lines[split + 1:]:
        if "ESTRUCTURAS DE CATALOGOS" in line:     # the catalog list and annexes follow
            break
        if not line.strip():
            continue
        m = _FD90_SECTION_RE.match(line)
        if m and m["num"] in by_num:
            current, row = by_num[m["num"]], None
            inline = _FD90_INLINE_RE.match(m["title"])
            if inline:
                row = [inline["code"], inline["label"].strip()]
                current["rows"].append(row)
            continue
        if current is None:
            continue
        cat = _FD_CATALOG_NOTE_RE.search(line)
        if cat:
            current["refs"].append((cat.group(1), "Descripción por catálogo"))
            row = None
            continue
        m = _FD90_CODE_RE.match(line)
        if m:
            row = [m["code"], m["label"].strip()]
            current["rows"].append(row)
        elif row is not None and not re.match(r"^\s*[A-ZÁÉÍÓÚÑ ]+:\s*$", line):
            row[1] = f"{row[1]} {line.strip()}"        # a wrapped label
    out = {}
    for var in by_num.values():
        raw, var["rows"] = var["rows"], []
        for code, label in raw:
            _code_row(var, code, " ".join(label.split()))
        out[var["var"]] = _finish(var, catalogs)
    return {"personas": out}


# Conteo 1995: «DESCRIPCION  CAMPO  {RANGO}  LONGITUD  POSICION INICIAL FINAL», code rows
# indented under the field, one section per DBF («ARCHIVO: … (DATGEN95.DBF)»).
_FD95_VAR_RE = re.compile(r"^(?P<desc>.*?)\s*(?<!\S)(?P<var>[A-Z][A-Z0-9_]*)\s+"
                          r"(?:\{(?P<codes>[^}]*)\}\s+)?(?P<len>\d+)\s+\d+\s+\d+\s*$")
_FD95_FILE_RE = re.compile(r"\((\w+)\.DBF\)", re.IGNORECASE)
_FD95_CODE_RE = re.compile(r"^\s{20,}(?P<code>\d+(?:\.\.\d+)?|b)\s{2,}(?P<label>\S.*)$")
_FD95_SECTION_RE = re.compile(r"^[IVX]+\s+[A-ZÁÉÍÓÚÑ ,]+$")


def parse_fd_1995_text(text: str, catalogs: dict | None = None) -> dict[str, dict[str, dict]]:
    """Parse the Conteo 1995 sample FD (``fd_encuesta_cpv1995.pdf`` as :func:`pdf_text`
    lays it out) → ``{DBF stem (datgen95/migint95): {VAR: meta}}``.

    A variable line ends with its field, ``{range}``, length and file positions. Its
    description may begin on the line(s) just above (``NUMERO DE REGISTRO`` / ``DE LA
    PERSONA  P3_1``). An indented description (``MESES  P4_4A``) is prefixed with the group
    title above it (``TIEMPO RESIDENCIA ANTERIOR``), and a missing one repeats the previous
    variable's (``FACTORES DE EXPANSION``: ``FAC_POB``, ``FAC_VIV``, ``FAC_PROM``). Indented
    code rows (``1  Hombre``, ``01..25  Número…``, ``b  Por pase``) follow; deeper lines
    continue a label. The variables go through :func:`_finish` as an FD without ``Tipo``.
    """
    out: dict[str, dict[str, dict]] = {}
    table = None
    pending: list[str] = []          # column-0 text lines right above a variable line
    group, last_desc = "", ""
    current, row = None, None
    for line in text.splitlines():
        f = _FD95_FILE_RE.search(line)
        if f and line.lstrip().upper().startswith("ARCHIVO"):
            table = out.setdefault(f.group(1).lower(), {})
            pending, group, current, row = [], "", None, None
            continue
        if table is None:
            continue
        if not line.strip():
            if pending:
                group, pending = " ".join(pending), []
            continue
        m = _FD95_VAR_RE.match(line)
        if m and len(m["var"]) > 1:
            desc = m["desc"].strip()
            if pending:
                desc = " ".join(pending + [desc])
            elif desc and line[:1] == " " and group:
                desc = f"{group} — {desc}"
            elif not desc:
                desc = last_desc
            desc = desc.rstrip(" -")
            last_desc = desc
            current = table[m["var"]] = _fd_var(m["var"], desc, "{" + (m["codes"] or "") + "}",
                                                m["len"])
            pending, row = [], None
            continue
        if _FD95_SECTION_RE.match(line.strip()) and not line.startswith(" "):
            pending, group, current, row = [], "", None, None
            continue
        if not line.startswith(" "):             # a description line of the next variable
            pending.append(line.strip())
            continue
        if current is None:
            continue
        m = _FD95_CODE_RE.match(line)
        if m:
            row = [m["code"], m["label"].strip()]
            current["rows"].append(row)
        elif row is not None:
            row[1] = f"{row[1]} {line.strip()}"
        elif _fold(line).strip().startswith("ver catalogo"):
            current["note_ref"] = line.strip()
    result = {}
    for stem, vars_ in out.items():
        for var in vars_.values():
            raw, var["rows"] = var["rows"], []
            for code, label in raw:
                _code_row(var, code, " ".join(label.split()))
        result[stem] = {v: _finish(m, catalogs) for v, m in vars_.items()}
    return result


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
