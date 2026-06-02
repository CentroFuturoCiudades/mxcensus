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
import warnings
from hashlib import sha256
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa

from mxcensus._resources import denue_schema_map

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


@functools.cache
def _latest_schema() -> pa.DataFrameSchema:
    """Pandera schema for the harmonized (latest-group) DENUE frame.

    All attribute columns are nullable strings (DENUE fields are categorical text);
    ``per_ocu`` is constrained to the canonical strata. ``strict=False`` ignores the
    geometry column. Required-column presence is the main guarantee.
    """
    cols = denue_schema_map()["groups"][denue_schema_map()["latest"]]["columns"]
    schema = {}
    for c in cols:
        if c == "per_ocu":
            schema[c] = pa.Column(str, pa.Check.isin(_OCU_ALLOWED), nullable=True, coerce=True)
        elif c == "codigo_act":  # SCIAN class code: 4–6 digits (nulls tolerated)
            schema[c] = pa.Column(
                str, pa.Check.str_matches(r"^\d{4,6}$"), nullable=True, coerce=True
            )
        else:
            schema[c] = pa.Column(str, nullable=True, coerce=True)
    return pa.DataFrameSchema(schema, strict=False, coerce=True)


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


def _harmonize(gdf: gpd.GeoDataFrame, gid: str, latest_cols: list) -> gpd.GeoDataFrame:
    """Map a group's GeoDataFrame onto the latest schema's columns + geometry."""
    # per_ocu: pull from its designated raw source column (which the general rename may
    # drop) and canonicalize, before the rename/drop pass.
    src, vmap = _PER_OCU.get(gid, ("per_ocu", None))
    per_ocu = gdf[src] if src in gdf.columns else None
    if per_ocu is not None and vmap is not None:
        per_ocu = per_ocu.map(lambda v: vmap.get(v, v))

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

    for col in latest_cols:  # add latest-only columns absent here (e.g. clee)
        if col not in gdf.columns:
            gdf[col] = pd.NA
    return gdf[latest_cols + ["geometry"]]


def load_denue(
    survey_path: Path | None = None,
    *,
    state: int | None = None,
    release: str | None = None,
    harmonize: bool = True,
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
    if harmonize:
        gid = _group_of(gdf, schema_map)
        latest_cols = schema_map["groups"][schema_map["latest"]]["columns"]
        gdf = _harmonize(gdf, gid, latest_cols)
        _latest_schema().validate(gdf.drop(columns="geometry"))  # raises on violation
    return gdf
