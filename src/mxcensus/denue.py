"""DENUE loader: fetch a mirrored release/state, optionally harmonize to the latest schema.

DENUE's schema drifted across 24 releases (2010–2025): descriptive Spanish column
names in 2010–2015 became mnemonics (``nom_estab`` …) in 2016+, ``clee`` was added in
2021, casing varies, and the personnel-stratum field is encoded as UPPERCASE labels,
numeric codes, or lowercase labels depending on era. Step 3 grouped every mirrored file
into one of 11 schema groups (``_yaml/denue_schema_map.yaml``); this module maps each
group to the latest schema (``g10``) so releases are longitudinally comparable.

``load_denue(state=N)`` returns the latest release harmonized; pass ``release=`` for a
specific edition and ``harmonize=False`` to get that edition's raw schema.

Maintenance note: the harmonization spec (``_RENAME``, ``_PER_OCU``) is hard-coded here
and targets the *current* latest schema's mnemonic column names (``g10``). If a future
INEGI release introduces a new majority schema that becomes ``latest`` in
``denue_schema_map.yaml``, these dicts must be revisited — the descriptive-name renames
all map onto g10's column names. ``_latest_schema`` itself reads ``latest`` dynamically
from the map, so only the rename/per_ocu spec is era-pinned.
"""
from __future__ import annotations

import functools
import json
import re
import warnings
from hashlib import sha256
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from mxcensus._resources import denue_schema_map, variables_denue

# --- Harmonization: explicit raw→latest column renames for the descriptive-name
# groups (2010–2015). Mnemonic groups g08/g10 (identity) and the UPPERCASE groups
# g09/g11 are handled automatically by case-insensitive matching in _harmonize, so
# they need no entry here. Any raw column neither renamed nor case-insensitively
# matching a latest-schema column is dropped (e.g. NIC/NOP, extra phones, status flags).
_RENAME: dict[str, dict[str, str]] = {
    "g01": {  # 2010 (and 2011 state 32)
        "Nombre de la unidad económica": "nom_estab",
        "Razón social": "raz_social",
        "Código de la clase de actividad": "codigo_act",
        "Nombre de la clase de actividad": "nombre_act",
        "Personal ocupado (estrato)": "per_ocu",
        "Calle, avenida, andador, carretera, manzana u otro": "nom_vial",
        "Número exterior o km": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Colonia, fraccionamiento, unidad habitacional o barrio": "nomb_asent",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Código postal": "cod_postal",
        "Entidad federativa": "entidad",
        "Municipio": "municipio",
        "Localidad": "localidad",
        "Área geoestadística básica": "ageb",
        "Manzana": "manzana",
        "Número de teléfono": "telefono",
        "Correo electrónico": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de unidad económica": "tipoUniEco",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g02": {  # 2011
        "Nombre de la unidad económica": "nom_estab",
        "Razón social": "raz_social",
        "Código de la clase de actividad": "codigo_act",
        "Nombre de la clase de actividad": "nombre_act",
        "Personal ocupado (estrato)": "per_ocu",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Número exterior o km": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Tipo y nombre del asentamiento humano": "nomb_asent",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Código postal": "cod_postal",
        "Clave entidad federativa": "cve_ent",
        "Entidad federativa": "entidad",
        "Clave municipio": "cve_mun",
        "Municipio": "municipio",
        "Clave localidad": "cve_loc",
        "Localidad": "localidad",
        "Área geoestadística básica": "ageb",
        "Manzana": "manzana",
        "Número de teléfono": "telefono",
        "Correo electrónico": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de unidad económica": "tipoUniEco",
        "Fecha de incorporación al DENUE": "fecha_alta",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g03": {  # 2012 (majority)
        "Llave DENUE": "id",
        "Clave entidad": "cve_ent",
        "Entidad federativa": "entidad",
        "Clave municipio": "cve_mun",
        "Municipio": "municipio",
        "Clave localidad": "cve_loc",
        "Localidad": "localidad",
        "Área geoestadística básica ": "ageb",
        "Manzana": "manzana",
        "Nombre de la Unidad Económica": "nom_estab",
        "Razón social": "raz_social",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Tipo entre vialidad 1": "tipo_v_e_1",
        "Nombre entre vialidad 1": "nom_v_e_1",
        "Tipo entre vialidad 2": "tipo_v_e_2",
        "Nombre entre vialidad 2": "nom_v_e_2",
        "Tipo vialidad posterior": "tipo_v_e_3",
        "Nombre vialidad posterior": "nom_v_e_3",
        "Número exterior o kilómetro": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Tipo de asentamiento humano": "tipo_asent",
        "Nombre de asentamiento humano": "nomb_asent",
        "Código Postal": "cod_postal",
        "Número de teléfono 1": "telefono",
        "Código de la clase de actividad SCIAN": "codigo_act",
        "Nombre de clase de la actividad": "nombre_act",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Correo electrónico 1": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de unidad económica": "tipoUniEco",
        "Descripcion estrato personal ocupado": "per_ocu",
        "Fecha de incorporación al DENUE": "fecha_alta",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g04": {  # 2012 typo variant (states 12, 14)
        "Llave DENUE": "id",
        "Clave entidad": "cve_ent",
        "Entidad federativa": "entidad",
        "Clave municipio": "cve_mun",
        "Municipio": "municipio",
        "Clave localidad": "cve_loc",
        "Localidad": "localidad",
        "Área geoestadística básica": "ageb",
        "Manzana": "manzana",
        "Nombre de la Unidad Económica": "nom_estab",
        "Razón social": "raz_social",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Tipo entre vialidad 1": "tipo_v_e_1",
        "Nombre entre vialidad 1": "nom_v_e_1",
        "Tipo entre vialidad 2": "tipo_v_e_2",
        "Nombre entre vialidad 2": "nom_v_e_2",
        "Tipo vialidad posterior": "tipo_v_e_3",
        "Nombre vialidad posterior": "nom_v_e_3",
        "Número exterior o kilómetro": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Tipo de asentamiento humano": "tipo_asent",
        "Nombre de asentamiento humano": "nomb_asent",
        "Código Postal": "cod_postal",
        "Número de teléfono 1": "telefono",
        "Código de la clase de actividad SCIAN": "codigo_act",
        "Nombre de clase dela actividad": "nombre_act",  # sic (INEGI typo)
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Correo electrónico 1": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de unidad económica": "tipoUniEco",
        "Descripción de estrato de personal ocupado": "per_ocu",  # sic (variant)
        "Fecha de incorporación al DENUE": "fecha_alta",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g05": {  # 2013-Jul
        "Llave DENUE": "id",
        "Entidad federativa": "entidad",
        "Municipio": "municipio",
        "Localidad": "localidad",
        "Área geoestadística básica ": "ageb",
        "Manzana": "manzana",
        "Nombre de la Unidad Económica": "nom_estab",
        "Razón social": "raz_social",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Número exterior o kilómetro": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Tipo de asentamiento humano": "tipo_asent",
        "Nombre de asentamiento humano": "nomb_asent",
        "Código Postal": "cod_postal",
        "Número de teléfono 1": "telefono",
        "Código de la clase de actividad SCIAN": "codigo_act",
        "Nombre de clase de la actividad": "nombre_act",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Correo electrónico 1": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de establecimiento": "tipoUniEco",
        "Descripcion estrato personal ocupado": "per_ocu",
        "Fecha de incorporación al DENUE": "fecha_alta",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g06": {  # 2013-Oct
        "Llave DENUE": "id",
        "Clave entidad": "cve_ent",
        "Entidad federativa": "entidad",
        "Clave municipio": "cve_mun",
        "Municipio": "municipio",
        "Clave localidad": "cve_loc",
        "Localidad": "localidad",
        "Área geoestadística básica ": "ageb",
        "Manzana": "manzana",
        "Nombre de la Unidad Económica": "nom_estab",
        "Razón social": "raz_social",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Tipo entre vialidad 1": "tipo_v_e_1",
        "Nombre entre vialidad 1": "nom_v_e_1",
        "Tipo entre vialidad 2": "tipo_v_e_2",
        "Nombre entre vialidad 2": "nom_v_e_2",
        "Tipo vialidad posterior": "tipo_v_e_3",
        "Nombre vialidad posterior": "nom_v_e_3",
        "Número exterior o kilómetro": "numero_ext",
        "Edificio, piso o nivel": "edificio",
        "Número o letra interior": "numero_int",
        "Tipo de asentamiento humano": "tipo_asent",
        "Nombre de asentamiento humano": "nomb_asent",
        "Código Postal": "cod_postal",
        "Número de teléfono 1": "telefono",
        "Código de la clase de actividad SCIAN": "codigo_act",
        "Nombre de clase de la actividad": "nombre_act",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Correo electrónico 1": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de establecimiento": "tipoUniEco",
        "Descripcion estrato personal ocupado": "per_ocu",
        "Fecha de incorporación al DENUE": "fecha_alta",
        "Latitud": "latitud",
        "Longitud": "longitud",
    },
    "g07": {  # 2015 descriptive
        "ID": "id",
        "Nombre de la Unidad Económica": "nom_estab",
        "Razón social": "raz_social",
        "Código de la clase de actividad SCIAN": "codigo_act",
        "Nombre de clase de la actividad": "nombre_act",
        "Descripcion estrato personal ocupado": "per_ocu",
        "Tipo de vialidad": "tipo_vial",
        "Nombre de la vialidad": "nom_vial",
        "Tipo de entre vialidad 1": "tipo_v_e_1",
        "Nombre de entre vialidad 1": "nom_v_e_1",
        "Tipo de entre vialidad 2": "tipo_v_e_2",
        "Nombre de entre vialidad 2": "nom_v_e_2",
        "Tipo de entre vialidad 3": "tipo_v_e_3",
        "Nombre de entre vialidad 3": "nom_v_e_3",
        "Número exterior o kilómetro": "numero_ext",
        "Letra exterior": "letra_ext",
        "Edificio": "edificio",
        "Edificio Piso": "edificio_e",
        "Número interior": "numero_int",
        "Letra interior": "letra_int",
        "Tipo de asentamiento humano": "tipo_asent",
        "Nombre de asentamiento humano": "nomb_asent",
        "Tipo centro comercial": "tipoCenCom",
        "Corredor industrial, centro comercial o mercado público": "nom_CenCom",
        "Número de local": "num_local",
        "Código Postal": "cod_postal",
        "Clave entidad": "cve_ent",
        "Entidad federativa": "entidad",
        "Clave municipio": "cve_mun",
        "Municipio": "municipio",
        "Clave localidad": "cve_loc",
        "Localidad": "localidad",
        "Área geoestadística básica ": "ageb",
        "Manzana": "manzana",
        "Número de teléfono": "telefono",
        "Correo electrónico": "correoelec",
        "Sitio en Internet": "www",
        "Tipo de establecimiento": "tipoUniEco",
        "Latitud": "latitud",
        "Longitud": "longitud",
        "Fecha de incorporación al DENUE": "fecha_alta",
    },
}

# Canonical personnel strata (the latest schema's per_ocu labels).
_OCU = ["0 a 5 personas", "6 a 10 personas", "11 a 30 personas", "31 a 50 personas",
        "51 a 100 personas", "101 a 250 personas", "251 y más personas"]

# per_ocu is encoded differently per era, and the *source column* differs too: 2010–2011
# store UPPERCASE labels; 2012 & 2013-Oct have both a numeric-code column (reliably
# populated) and a label column (empty for some states, e.g. 2012 states 12/14), so we
# read the code column; 2013-Jul/2015 have only a label column; 2016+ use mnemonic
# per_ocu. `_PER_OCU[gid]` = (raw source column, value map → canonical or None).
_UPPER_OCU = {
    "0 A 5 PERSONAS": "0 a 5 personas", "6 A 10 PERSONAS": "6 a 10 personas",
    "11 A 30 PERSONAS": "11 a 30 personas", "31 A 50 PERSONAS": "31 a 50 personas",
    "51 A 100 PERSONAS": "51 a 100 personas", "101 A 250 PERSONAS": "101 a 250 personas",
    "251 Y MAS PERSONAS": "251 y más personas", "NO ESPECIFICADO": "No especificado",
}
_CODE_OCU = {
    "1": "0 a 5 personas", "2": "6 a 10 personas", "3": "11 a 30 personas",
    "4": "31 a 50 personas", "5": "51 a 100 personas", "6": "101 a 250 personas",
    "7": "251 y más personas", "13": "No especificado",  # 13 is an anomalous 2012 code
}
_PER_OCU: dict[str, tuple] = {
    "g01": ("Personal ocupado (estrato)", _UPPER_OCU),
    "g02": ("Personal ocupado (estrato)", _UPPER_OCU),
    "g03": ("Personal ocupado (estrato)", _CODE_OCU),
    "g04": ("Personal ocupado (estrato)", _CODE_OCU),
    "g05": ("Descripcion estrato personal ocupado", None),
    "g06": ("Personal ocupado (estrato)", _CODE_OCU),
    "g07": ("Descripcion estrato personal ocupado", None),
    "g08": ("per_ocu", None), "g09": ("PER_OCU", None),
    "g10": ("per_ocu", None), "g11": ("PER_OCU", None),
}

# Allowed per_ocu values after harmonization: the 7 strata + the unspecified category.
_OCU_ALLOWED = _OCU + ["No especificado"]

# tipoUniEco (establishment type) drifts like per_ocu: 2010–2011 store UPPERCASE labels
# (FIJO/SEMIFIJO); 2012–2013 store numeric codes in the *separate* "Tipo de
# establecimiento" column (1/2/3 — the dict says "1 y 3 = fijo, 2 = semifijo"; code 3 is
# the in-dwelling fixed subtype, labelled "Actividad en vivienda"); 2015+ store Fijo/
# Semifijo. The 2012 "Tipo de unidad económica" column is unrelated (S/U/M), so the
# general rename mapping it to tipoUniEco is wrong — `_TIPO_UNI` overrides the source.
_TIPO_UNI_LABEL = {
    "1": "Fijo", "2": "Semifijo", "3": "Actividad en vivienda",
    "FIJO": "Fijo", "SEMIFIJO": "Semifijo",
}
_TIPO_UNI: dict[str, tuple] = {
    "g01": ("Tipo de unidad económica", _TIPO_UNI_LABEL),
    "g02": ("Tipo de unidad económica", _TIPO_UNI_LABEL),
    "g03": ("Tipo de establecimiento", _TIPO_UNI_LABEL),
    "g04": ("Tipo de establecimiento", _TIPO_UNI_LABEL),
    "g05": ("Tipo de establecimiento", _TIPO_UNI_LABEL),
    "g06": ("Tipo de establecimiento", _TIPO_UNI_LABEL),
    "g07": ("Tipo de establecimiento", None),  # already Fijo/Semifijo
    "g08": ("tipoUniEco", None), "g09": ("TIPOUNIECO", None),
    "g10": ("tipoUniEco", None), "g11": ("TIPOUNIECO", None),
}
_TIPO_UNI_ALLOWED = ["Fijo", "Semifijo", "Actividad en vivienda"]

# Coded columns validated by regex rather than enumeration (keyed by latest-schema
# mnemonic; the raw per-group schema maps each raw column to its mnemonic via _mnemonic_of).
# Patterns tolerate INEGI's surrounding whitespace and dropped leading zeros (codes are
# stored as integer-like strings — "02000" → "2000", missing → "0") while still flagging
# non-numeric / over-long garbage. codigo_act (SCIAN) is genuinely 4–6 digits, no padding.
_CODED_REGEX = {
    "codigo_act": r"^\s*\d{4,6}\s*$",   # SCIAN class code
    "cod_postal": r"^\s*\d{1,5}\s*$",
    "cve_ent": r"^\s*\d{1,2}\s*$",
    "cve_mun": r"^\s*\d{1,3}\s*$",
    "cve_loc": r"^\s*\d{1,4}\s*$",
}
# Numeric (type-only) columns. No bbox range check: out-of-bbox coordinates legitimately
# occur in the source (their geometry is nulled at build time), so a range check would
# false-fail on load; numeric-coercibility is the meaningful guarantee.
_NUMERIC = {"latitud", "longitud"}
_FECHA_RE = r"^\d{4}-\d{2}$"  # canonical fecha_alta after _normalize_fecha

# Spanish month → MM, for normalizing fecha_alta across its many era formats.
_MES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05",
        "junio": "06", "julio": "07", "agosto": "08", "septiembre": "09",
        "setiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
_MES_ABBR = {"ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06",
             "jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12"}


def _latest_cols() -> list:
    """Column list of the latest (harmonization-target) schema group."""
    m = denue_schema_map()
    return m["groups"][m["latest"]]["columns"]


def _mnemonic_of(gid: str, raw_col: str) -> str:
    """Resolve a group's raw column name to its canonical latest-schema mnemonic.

    Descriptive groups (g01–g07) use the explicit ``_RENAME`` map; mnemonic (g08/g10)
    and UPPERCASE (g09/g11) groups match case-insensitively against the latest columns;
    anything unmapped (e.g. NIC/NOP, extra phones) returns itself. Importable by the
    build script so descriptions and coded-regex checks key off one mnemonic per column.
    """
    explicit = _RENAME.get(gid, {})
    if raw_col in explicit:
        return explicit[raw_col]
    by_lower = {c.lower(): c for c in _latest_cols()}
    return by_lower.get(raw_col.lower(), raw_col)


def _normalize_fecha(s: pd.Series) -> pd.Series:
    """Normalize fecha_alta to ``YYYY-MM`` across eras; unparseable → NA.

    Handles ``2010-07`` / ``2013 07`` (separator drift), Spanish full-month ``JULIO 2010``,
    and abbreviated ``mar-11``. Unrecognized values become NA rather than raising, so a
    normal load never fails on a stray date — the date-format check surfaces gaps instead.
    """
    def one(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return pd.NA
        t = str(v).strip()
        if not t or t.lower() == "nan":
            return pd.NA
        m = re.fullmatch(r"(\d{4})[-\s](\d{1,2})", t)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}"
        m = re.fullmatch(r"([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+(\d{4})", t)
        if m and m.group(1).lower() in _MES:
            return f"{m.group(2)}-{_MES[m.group(1).lower()]}"
        m = re.fullmatch(r"([A-Za-z]{3})[-/](\d{2})", t)
        if m and m.group(1).lower() in _MES_ABBR:
            return f"20{m.group(2)}-{_MES_ABBR[m.group(1).lower()]}"
        return pd.NA
    return s.map(one)


@functools.cache
def _latest_schema() -> pa.DataFrameSchema:
    """Tight Pandera schema for the harmonized (latest-group) DENUE frame.

    "Tight where safe": ``per_ocu`` and ``tipoUniEco`` are canonicalized by ``_harmonize``
    across eras, so they get strict ``isin`` checks; ``fecha_alta`` is normalized to
    ``YYYY-MM`` and date-checked; coded columns get regex and lat/lon a numeric type check.
    Other categoricals (``tipo_asent``, ``tipo_vial``, ``tipoCenCom``, …) stay plain
    strings here because harmonization renames columns but does NOT translate their label
    spellings across eras — a strict ``isin`` would false-fail. Strict per-era ``isin`` on
    those lives in ``_group_schema`` (the raw, single-era schema). ``strict=False`` ignores
    the geometry column.
    """
    schema = {}
    for c in _latest_cols():
        if c == "per_ocu":
            schema[c] = pa.Column(str, pa.Check.isin(_OCU_ALLOWED), nullable=True, coerce=True)
        elif c == "tipoUniEco":
            schema[c] = pa.Column(str, pa.Check.isin(_TIPO_UNI_ALLOWED), nullable=True, coerce=True)
        elif c == "fecha_alta":
            schema[c] = pa.Column(str, pa.Check.str_matches(_FECHA_RE), nullable=True, coerce=True)
        elif c in _CODED_REGEX:
            schema[c] = pa.Column(str, pa.Check.str_matches(_CODED_REGEX[c]), nullable=True, coerce=True)
        elif c in _NUMERIC:
            schema[c] = pa.Column(float, nullable=True, coerce=True)
        else:
            schema[c] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


@functools.cache
def _group_schema(gid: str) -> pa.DataFrameSchema:
    """Tight Pandera schema for a group's RAW (un-harmonized) frame.

    Built from the group's bundled ``variables_denue_<gid>.yaml``: any column with a
    non-empty ``Categorías`` map is constrained to those keys (``isin``) — the categories
    are sourced from the release's data dictionary and cross-validated against the data at
    build time, so a future file with a new/garbled value fails here. Coded columns
    (by mnemonic) get regex; lat/lon a numeric type check; everything else a nullable
    string. ``strict=False`` ignores geometry and any extra per_ocu source columns.
    """
    vars_ = variables_denue(gid)
    cols = denue_schema_map()["groups"][gid]["columns"]
    schema = {}
    for col in cols:
        cats = (vars_.get(col) or {}).get("Categorías") or {}
        mn = _mnemonic_of(gid, col)
        if cats:
            schema[col] = pa.Column(str, pa.Check.isin(list(cats)), nullable=True, coerce=True)
        elif mn in _CODED_REGEX:
            schema[col] = pa.Column(str, pa.Check.str_matches(_CODED_REGEX[mn]), nullable=True, coerce=True)
        elif mn in _NUMERIC:
            schema[col] = pa.Column(float, nullable=True, coerce=True)
        else:
            schema[col] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


def _validate(schema: pa.DataFrameSchema, frame: pd.DataFrame, label: str) -> None:
    """Validate (lazy) and **warn** on value-level violations rather than raise.

    A single malformed cell (DENUE has e.g. ``cod_postal="IT SU"`` from a misaligned row)
    should surface a problem, not make a whole state unloadable — structural problems
    (unknown schema) already raise earlier in ``load_denue`` via ``_group_of``. The
    maintainer ``--validate`` sweep is the authoritative hard pass/fail report.
    """
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        fc = exc.failure_cases
        top = fc.groupby(["column", "check"]).size().sort_values(ascending=False).head(6)
        detail = "; ".join(f"{col}/{chk}×{n}" for (col, chk), n in top.items())
        warnings.warn(
            f"DENUE {label}: {len(fc)} schema violation(s) [{detail}]", stacklevel=3
        )


def _fingerprint(columns) -> str:
    return sha256(json.dumps(list(columns)).encode()).hexdigest()


def _group_of(gdf: gpd.GeoDataFrame, schema_map: dict) -> str:
    cols = [c for c in gdf.columns if c != "geometry"]
    fp = _fingerprint(cols)
    gid = schema_map["fingerprints"].get(fp)
    if gid is None:
        raise ValueError("DENUE file schema not found in denue_schema_map.yaml "
                         "(stale mirror or map?)")
    return gid


def _capture(gdf: gpd.GeoDataFrame, spec: dict, gid: str):
    """Capture a coded column from its era-specific source and canonicalize its values.

    The general rename can pick the wrong column (tipoUniEco) or drop the populated one
    (per_ocu), so these fields are captured from their designated source *before* the
    rename and re-assigned after. Returns None if the source column is absent.
    """
    src, vmap = spec.get(gid, (None, None))
    if not src or src not in gdf.columns:
        return None
    s = gdf[src]
    return s.map(lambda v: vmap.get(v, v)) if vmap is not None else s


def _harmonize(gdf: gpd.GeoDataFrame, gid: str, latest_cols: list) -> gpd.GeoDataFrame:
    """Map a group's GeoDataFrame onto the latest schema's columns + geometry."""
    # per_ocu and tipoUniEco: capture+canonicalize from their designated raw source
    # columns (which the general rename may drop or mis-source) before the rename/drop.
    per_ocu = _capture(gdf, _PER_OCU, gid)
    tipo_uni = _capture(gdf, _TIPO_UNI, gid)

    by_lower = {c.lower(): c for c in latest_cols}
    explicit = _RENAME.get(gid, {})
    rename = {}
    for col in gdf.columns:
        if col == "geometry":
            continue
        if col in explicit:
            rename[col] = explicit[col]
        elif col.lower() in by_lower:  # mnemonic/UPPERCASE groups → exact latest casing
            rename[col] = by_lower[col.lower()]
        # else: unmapped → dropped below

    # Guard against a stale rename map: an explicit target that never materialized
    # means its source column name (a key in _RENAME[gid]) no longer matches the
    # data, which would otherwise be masked as an all-null column by the add_null
    # pass below. (A genuinely empty source column still materializes — it's present
    # but null — so this fires only on an actual key mismatch.)
    produced = {tgt for src_col, tgt in rename.items() if src_col in explicit}
    missing_targets = set(explicit.values()) - produced
    if missing_targets:
        warnings.warn(
            f"DENUE {gid}: rename target(s) {sorted(missing_targets)} not produced — "
            f"source column(s) absent; _RENAME may be stale for this schema.",
            stacklevel=2,
        )
    gdf = gdf.rename(columns=rename)
    gdf = gdf[[c for c in gdf.columns if c in latest_cols or c == "geometry"]]

    gdf["per_ocu"] = per_ocu.to_numpy() if per_ocu is not None else pd.NA
    gdf["tipoUniEco"] = tipo_uni.to_numpy() if tipo_uni is not None else pd.NA

    for col in latest_cols:  # add latest-only columns absent here (e.g. clee)
        if col not in gdf.columns:
            gdf[col] = pd.NA
    if "fecha_alta" in gdf.columns:  # unify the many era date formats → YYYY-MM
        gdf["fecha_alta"] = _normalize_fecha(gdf["fecha_alta"])
    return gdf[latest_cols + ["geometry"]]


def load_denue(
    survey_path: Path | None = None,
    *,
    state: int | None = None,
    release: str | None = None,
    harmonize: bool = True,
    dedupe: bool = True,
    dedupe_ids: bool = True,
) -> gpd.GeoDataFrame:
    """Load one DENUE release/state as a GeoDataFrame (points, EPSG:4326).

    Two calling conventions:

    - ``load_denue(state=9)`` — fetch from the mxcensus mirror via Pooch (latest release).
    - ``load_denue(survey_path=Path("denue_202505_09.parquet"))`` — explicit local file.

    Parameters
    ----------
    state : int, optional
        INEGI state code (ENTIDAD) 1–32.
    release : str, optional
        Release id ``YYYYMM`` (e.g. ``"202011"``); defaults to the latest release.
    harmonize : bool, default True
        Map the file onto the latest release's 42-column schema for longitudinal
        comparability. If False, return the release's raw columns.
    dedupe : bool, default True
        Drop **exact full-row duplicates** (identical in every column), keeping the
        first occurrence. These are byte-identical source rows that carry no extra
        information — chiefly the 2010/2011 editions (tens of thousands of rows).
    dedupe_ids : bool, default True
        Drop rows sharing the same establishment ``id`` (or ``clee``), keeping the
        first occurrence. Unlike ``dedupe`` this also collapses near-duplicates that
        differ only in trivial cells (coordinate precision, whitespace) — e.g. the
        2023 state-15 file's repeated ids. No-op for early editions that lack an id
        column. Implies ``dedupe`` for same-id rows.

    Both flags only clean the in-memory frame; the mirror itself stays faithful
    (duplicates are reported, not removed, by ``build_denue.py``).

    The frame is validated against the tight Pandera schema for its group (raw) or the
    latest schema (harmonized); value-level violations emit a ``warnings.warn`` summary
    (they do not raise — see ``_validate``). An unrecognized schema raises ``ValueError``.

    Returns
    -------
    geopandas.GeoDataFrame
    """
    schema_map = denue_schema_map()
    if state is not None:
        from mxcensus.data._catalog import STATE_CODE_FMT
        from mxcensus.data._denue_catalog import latest_release
        from mxcensus.data._registry import POOCH

        rel = release or latest_release().yyyymm
        code = STATE_CODE_FMT(state)
        survey_path = Path(POOCH.fetch(f"denue_{rel}_{code}.parquet"))
    if survey_path is None:
        raise ValueError("Provide either state= or survey_path=")

    gdf = gpd.read_parquet(survey_path)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError(
            f"DENUE file {survey_path} is not EPSG:4326 (got {gdf.crs}); stale mirror?"
        )
    if dedupe:
        # Exact full-row duplicates only (geometry is derived from lat/lon, so identical
        # data rows have identical geometry); the duplicated() check ignores it for speed.
        dups = gdf.drop(columns="geometry").duplicated()
        if dups.any():
            gdf = gdf.loc[~dups].reset_index(drop=True)
    if dedupe_ids:
        colmap = {c.lower(): c for c in gdf.columns}
        id_col = next((colmap[k] for k in ("id", "clee") if k in colmap), None)
        if id_col is not None:
            dups = gdf[id_col].duplicated()
            if dups.any():
                gdf = gdf.loc[~dups].reset_index(drop=True)
    gid = _group_of(gdf, schema_map)
    if harmonize:
        latest_cols = schema_map["groups"][schema_map["latest"]]["columns"]
        gdf = _harmonize(gdf, gid, latest_cols)
        _validate(_latest_schema(), gdf.drop(columns="geometry"), f"{gid} (harmonized)")
    else:
        # validate the raw frame against its own group's tight schema
        _validate(_group_schema(gid), gdf.drop(columns="geometry"), f"{gid} (raw)")
    return gdf
