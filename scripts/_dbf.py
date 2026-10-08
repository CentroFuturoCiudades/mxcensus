"""Maintainer-only: a standard-library (+ NumPy/Arrow) reader for dBASE III ``.dbf`` files.

INEGI ships the census microdata of 1990–2010 and the CPV 2010 classification catalogs as
DBF tables. A DBF file is a 32-byte header (record count, header and record lengths, a
language-driver byte at offset 29), one 32-byte descriptor per field (name, type, width)
closed by ``0x0D``, then fixed-width records, each led by a deletion flag (``*`` =
deleted). Character fields are space-padded on the right, numeric fields on the left.

:func:`read_dbf` returns the table **faithful raw**, like the CSV editions' parquet: every
field a ``string`` column, values as written minus their fixed-width padding (spaces and
NULs at either end), an empty field null, deleted records dropped (and counted). The
records are memory-mapped and decoded one field at a time — columns of plain ASCII are cast
directly; columns with accented bytes are decoded once per distinct value — so a
multi-million-row personas file never becomes Python objects row by row.

The text encoding is chosen from the bytes (:func:`sniff_encoding`). INEGI's language-driver
bytes are unreliable (the 2010 viviendas say 0x00 and the personas 0x03 for the same
cp1252 text; the municipality catalog says 0x02 and is cp850), so the high bytes are decoded
both ways and the encoding that yields more Spanish letters wins; the driver byte only
breaks a tie.
"""
from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

# Language-driver byte → code page (dBASE / Visual FoxPro table).
_LANG_CODEPAGE = {0x01: "cp437", 0x02: "cp850", 0x03: "cp1252", 0x57: "cp1252",
                  0x58: "cp1252", 0x59: "cp1252", 0x64: "cp852", 0x7D: "cp1255",
                  0xC8: "cp1250", 0xC9: "cp1251", 0xCA: "cp1254", 0xCB: "cp1253"}
_CANDIDATES = ("cp1252", "cp850")
_SPANISH = frozenset("áéíóúüñÁÉÍÓÚÜÑ¿¡°ºª")
_PAD = " \x00"
_CHUNK_ROWS = 1 << 20


@dataclass(frozen=True)
class DbfField:
    name: str
    type: str      # C (character), N (numeric), F (float), D (date), L (logical), …
    length: int
    decimals: int
    offset: int    # byte offset within the record (the deletion flag is byte 0)


@dataclass(frozen=True)
class DbfHeader:
    version: int
    n_records: int
    header_len: int
    record_len: int
    lang: int
    fields: tuple[DbfField, ...]

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.fields]


def read_header(data: bytes) -> DbfHeader:
    """Parse the header of a DBF file given its leading bytes (at least the header)."""
    if len(data) < 32:
        raise ValueError("not a DBF file: shorter than its 32-byte header")
    version, _, _, _, n_records, header_len, record_len = struct.unpack_from("<4BIHH", data, 0)
    fields, offset = [], 1
    for pos in range(32, header_len, 32):
        if data[pos] == 0x0D:
            break
        desc = data[pos:pos + 32]
        if len(desc) < 32:
            raise ValueError("truncated DBF field descriptor")
        name = desc[:11].split(b"\0", 1)[0].decode("ascii", "replace").strip()
        fields.append(DbfField(name, chr(desc[11]), desc[16], desc[17], offset))
        offset += desc[16]
    if not fields or offset != record_len:
        raise ValueError(f"DBF field widths add up to {offset} bytes, the header says "
                         f"{record_len}")
    return DbfHeader(version, n_records, header_len, record_len, data[29], tuple(fields))


def _records(data, header: DbfHeader) -> np.ndarray:
    """The record block as an ``(n, record_len)`` uint8 array (a view; no copy)."""
    available = (len(data) - header.header_len) // header.record_len
    n = min(header.n_records, available)
    if n < header.n_records:
        raise ValueError(f"DBF truncated: header says {header.n_records} records, the file "
                         f"holds {available}")
    return np.frombuffer(data, dtype=np.uint8, count=n * header.record_len,
                         offset=header.header_len).reshape(n, header.record_len)


def sniff_encoding(records: np.ndarray, lang: int = 0) -> str:
    """``ascii`` when no byte is ≥ 0x80; else the candidate code page (cp1252 or cp850)
    under which the high bytes decode to the most Spanish letters (``_SPANISH``), the
    language-driver byte breaking a tie (default cp1252)."""
    counts = np.zeros(256, dtype=np.int64)
    for start in range(0, len(records), _CHUNK_ROWS):
        block = records[start:start + _CHUNK_ROWS]
        counts += np.bincount(block[block >= 0x80], minlength=256)
    if not counts.any():
        return "ascii"
    score = {enc: sum(int(counts[b]) for b in range(0x80, 0x100)
                      if counts[b] and bytes([b]).decode(enc, "replace") in _SPANISH)
             for enc in _CANDIDATES}
    best = max(score.values())
    winners = [enc for enc in _CANDIDATES if score[enc] == best]
    hint = _LANG_CODEPAGE.get(lang)
    return hint if hint in winners else winners[0]


def _column(records: np.ndarray, field: DbfField, encoding: str) -> pa.Array:
    """One field as a ``string`` array: padding trimmed, empty → null."""
    raw = np.ascontiguousarray(records[:, field.offset:field.offset + field.length])
    n = len(raw)
    if field.length == 0:
        return pa.nulls(n, pa.string())
    if encoding == "ascii" or not (raw >= 0x80).any():
        fixed = pa.FixedSizeBinaryArray.from_buffers(pa.binary(field.length), n,
                                                     [None, pa.py_buffer(raw)])
        text = pc.utf8_trim(fixed.cast(pa.binary()).cast(pa.string()), characters=_PAD)
    else:
        values, inverse = np.unique(raw.view(f"S{field.length}").ravel(), return_inverse=True)
        decoded = pa.array([v.decode(encoding).strip(_PAD) for v in values], pa.string())
        text = decoded.take(pa.array(inverse.ravel()))
    return pc.if_else(pc.equal(text, ""), pa.scalar(None, pa.string()), text)


@dataclass(frozen=True)
class DbfTable:
    table: pa.Table
    encoding: str
    deleted: int
    header: DbfHeader


def read_dbf(source: Path | str | bytes, encoding: str | None = None) -> DbfTable:
    """Read a DBF file (a path, or its bytes) faithfully as an all-``string`` Arrow table.

    ``encoding`` overrides :func:`sniff_encoding`. Raises ``ValueError`` on a malformed
    header, duplicate field names or a file shorter than its declared record count.
    """
    if isinstance(source, bytes):
        return _read(source, encoding)
    with open(source, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        return _read(mm, encoding)


def _read(data, encoding: str | None) -> DbfTable:
    header = read_header(bytes(data[:min(len(data), 65536)]))
    names = header.names
    dupes = sorted({c for c in names if names.count(c) > 1})
    if dupes:
        raise ValueError(f"DBF has duplicate field names {dupes}")
    records = _records(data, header)
    enc = encoding or sniff_encoding(records, header.lang)
    live = records[:, 0] != ord("*")
    deleted = int((~live).sum())
    columns = [_column(records, f, enc) for f in header.fields]
    table = pa.table(columns, names=names)
    if deleted:
        table = table.filter(pa.array(live))
    del records
    return DbfTable(table, enc, deleted, header)
