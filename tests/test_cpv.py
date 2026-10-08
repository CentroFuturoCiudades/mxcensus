"""CPV family (censos / conteos / encuestas intercensales 1990–2025) tests.

Phase 0 covers the download catalog (``mxcensus.data._cpv_catalog``) and the
multi-edition Marco Geoestadístico helpers — all offline. The URLs and ZIP member lists
pinned here were verified live against INEGI on 2026-10-07 (``docs/cpv/STEP_0_probe.md``);
loader/schema tests join this file as the family is built (docs/cpv/PLAN.md).
"""
from __future__ import annotations

import pytest

from mxcensus.data._catalog import (
    MG_EDITIONS,
    marco_geo_national_url,
    marco_geo_zip_url,
    mg_filename,
)
from mxcensus.data._cpv_catalog import (
    DICTIONARY_URLS,
    EDITIONS,
    EDITIONS_BY_PERIOD,
    FILE_RE,
    KINDS,
    MICRO_TABLES,
    NATIONAL_TABLES,
    PRODUCT_OF,
    TABLES,
    cpv_filename,
    cpv_zip_entry,
    dictionary_url,
    find_member,
    get_edition,
    latest_edition,
    parse_filename,
)

_P = "https://www.inegi.org.mx/contenidos/programas"

# State-01 (or national) URLs HEAD-verified on 2026-10-07 (ZIP Content-Type).
_VERIFIED_URLS = {
    ("1990", "microdatos"): "ccpv/1990/microdatos/cgpv90p_01_dbf.zip",
    ("1990", "iter"): "ccpv/1990/microdatos/iter/01_aguascalientes_1990_iter_dbf.zip",
    ("1995", "microdatos"): "ccpv/1995/microdatos/cpv95_01_dbf.zip",
    ("1995", "iter"): "ccpv/1995/microdatos/iter/01_aguascalientes_1995_iter_dbf.zip",
    ("2000", "microdatos"): "ccpv/2000/microdatos/muestra/cgpv2000_01_dbf.zip",
    ("2000", "iter"): "ccpv/2000/datosabiertos/cgpv2000_iter_01_csv.zip",
    ("2005", "microdatos"): "ccpv/2005/microdatos/muestra/cpv2005_01_dbf.zip",
    ("2005", "iter"): "ccpv/2005/datosabiertos/cpv2005_iter_01_csv.zip",
    ("2010", "microdatos"): "ccpv/2010/microdatos/mpv/MC2010_01_dbf.zip",
    ("2010", "iter"): "ccpv/2010/datosabiertos/iter_01_2010_csv.zip",
    ("2010", "ageb"): "ccpv/2010/datosabiertos/ageb_y_manzana/resageburb_01_2010_csv.zip",
    ("2015", "microdatos"): "intercensal/2015/microdatos/eic2015_01_csv.zip",
    ("2020", "microdatos"): "ccpv/2020/microdatos/Censo2020_CA_ags_csv.zip",
    ("2020", "iter"): "ccpv/2020/datosabiertos/iter/iter_01_cpv2020_csv.zip",
    ("2020", "ageb"): "ccpv/2020/datosabiertos/ageb_manzana/ageb_mza_urbana_01_cpv2020_csv.zip",
    ("2025", "microdatos"): "eic/2025/microdatos/eic2025_micro_01_csv.zip",
    ("2025", "estimaciones"): "eic/2025/datosabiertos/conjunto_de_datos_eic2025_105_csv.zip",
}

# Data members of the state-01 / national ZIPs listed on 2026-10-07 (dictionary CSVs kept
# as decoys where the ZIP has them).
_PROBED_MEMBERS = {
    ("1990", "microdatos"): ["m_1001.dbf"],
    ("1990", "iter"): ["ITER_01DBF90.dbf"],
    ("1995", "microdatos"): ["datgen95.dbf", "migint95.dbf"],
    ("1995", "iter"): ["ITER_01DBF95.dbf"],
    ("2000", "microdatos"): ["MIN_F01.DBF", "PER_F01.DBF", "VHO_F01.DBF"],
    ("2000", "iter"): ["cgpv2000_iter_01/conjunto_de_datos/cgpv2000_iter_01.csv",
                       "cgpv2000_iter_01/diccionario_de_datos/fd_cgpv2000_iter.csv"],
    ("2005", "microdatos"): ["cpv2005_01_dbf/trhmue01.DBF", "cpv2005_01_dbf/trpmue01.DBF",
                             "cpv2005_01_dbf/trvmue01.DBF"],
    ("2005", "iter"): ["cpv2005_iter_01/conjunto_de_datos/cpv2005_iter_01.csv",
                       "cpv2005_iter_01/diccionario_de_datos/fd_cpv2005_iter.csv"],
    ("2010", "microdatos"): ["Migrantes_01.dbf", "Personas_01.dbf", "Viviendas_01.dbf"],
    ("2010", "iter"): ["iter_01_cpv2010/catalogos/tam_loc.csv",
                       "iter_01_cpv2010/conjunto_de_datos/iter_01_cpv2010.csv",
                       "iter_01_cpv2010/diccionario_de_datos/fd_iter_cpv2010.csv"],
    ("2010", "ageb"): [
        "resultados_ageb_urbana_01_cpv2010/conjunto_de_datos/resultados_ageb_urbana_01_cpv2010.csv",
        "resultados_ageb_urbana_01_cpv2010/diccionario_de_datos/fd_resultados_ageb_urbana_cpv2010.csv",
    ],
    ("2015", "microdatos"): ["TR_PERSONA01.CSV", "TR_VIVIENDA01.CSV"],
    ("2020", "microdatos"): ["Migrantes01.CSV", "Personas01.CSV", "Viviendas01.CSV"],
    ("2020", "iter"): ["iter_01_cpv2020/catalogos/tam_loc.csv.csv",
                       "iter_01_cpv2020/conjunto_de_datos/conjunto_de_datos_iter_01CSV20.csv",
                       "iter_01_cpv2020/diccionario_datos/diccionario_datos_iter_01CSV20.csv"],
    ("2020", "ageb"): [
        "ageb_mza_urbana_01_cpv2020/conjunto_de_datos/conjunto_de_datos_ageb_urbana_01_cpv2020.csv",
        "ageb_mza_urbana_01_cpv2020/diccionario_de_datos/diccionario_datos_ageb_urbana_01_cpv2020.csv",
    ],
    ("2025", "microdatos"): ["migrantes01.csv", "personas01.csv", "viviendas01.csv"],
    ("2025", "estimaciones"): ["conjunto_de_datos/conjunto_datos_eic2025_105.csv",
                               "diccionario_datos/diccionario_datos_eic2025_105.csv"],
}


# --- editions -----------------------------------------------------------------------

def test_editions_chronological_and_consistent():
    periods = [e.period for e in EDITIONS]
    assert periods == ["1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025"]
    assert list(EDITIONS_BY_PERIOD) == periods
    for e in EDITIONS:
        assert e.period == str(e.year)
        assert e.kind in KINDS
        assert e.tables and set(e.tables) <= set(TABLES)
        for t in e.tables:
            assert PRODUCT_OF[t] in e.urls
        assert set(e.products) == {PRODUCT_OF[t] for t in e.tables}


def test_edition_table_sets():
    has = {e.period: set(e.tables) for e in EDITIONS}
    assert has["2025"] == {"viviendas", "personas", "migrantes", "estimaciones"}
    assert has["2020"] == {"viviendas", "personas", "migrantes", "iter", "ageb"}
    assert has["2015"] == {"viviendas", "personas"}
    assert has["2010"] == {"viviendas", "personas", "migrantes", "iter", "ageb"}
    assert has["2005"] == {"viviendas", "hogares", "personas", "iter"}
    assert has["2000"] == {"viviendas", "personas", "migrantes", "iter"}
    assert has["1995"] == {"hogares", "migrantes", "iter"}
    assert has["1990"] == {"personas", "iter"}
    # ITER exists for every censo/conteo and no encuesta intercensal.
    for e in EDITIONS:
        assert e.has("iter") == (e.kind != "intercensal")
    assert {e.period for e in EDITIONS if not e.weighted} == {"1990", "2005"}


@pytest.mark.parametrize("key", sorted(_VERIFIED_URLS))
def test_verified_urls(key):
    period, product = key
    ed = get_edition(period)
    state = None if product == "estimaciones" else 1
    assert ed.zip_url(product, state) == f"{_P}/{_VERIFIED_URLS[key]}"


@pytest.mark.parametrize("state", [1, 9, 15, 16, 30, 32])
def test_per_state_urls_format_every_state(state):
    code = f"{state:02d}"
    for e in EDITIONS:
        for product in e.products:
            if product == "estimaciones":
                continue
            url = e.zip_url(product, state)
            assert "{" not in url and url.endswith(".zip")
            assert code in url or e.period == "2020" and product == "microdatos"
            assert e.zip_filename(product, state) == url.rsplit("/", 1)[-1]


def test_url_errors():
    e25, e15 = get_edition("2025"), get_edition("2015")
    with pytest.raises(ValueError, match="per state"):
        e25.zip_url("microdatos")
    with pytest.raises(ValueError, match="no 'iter' product"):
        e15.zip_url("iter", 1)
    with pytest.raises(ValueError, match="1-32"):
        e25.zip_url("microdatos", 33)
    with pytest.raises(ValueError, match="does not publish"):
        e15.filename("migrantes", 1)
    with pytest.raises(ValueError, match="unknown CPV edition"):
        get_edition("2016")


def test_latest_edition():
    assert latest_edition().period == "2025"
    assert latest_edition("personas").period == "2025"
    assert latest_edition("estimaciones").period == "2025"
    assert latest_edition("iter").period == "2020"
    assert latest_edition("ageb").period == "2020"
    assert latest_edition("hogares").period == "2005"
    with pytest.raises(ValueError, match="unknown CPV table"):
        latest_edition("nope")


# --- ZIP members --------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(_PROBED_MEMBERS))
def test_find_member_probed(key):
    period, product = key
    ed = get_edition(period)
    state = None if product == "estimaciones" else 1
    names = _PROBED_MEMBERS[key]
    found = {t: find_member(names, ed, t, state) for t in ed.tables_in(product)}
    assert len(set(found.values())) == len(found)            # distinct members
    for member in found.values():
        assert "diccionario" not in member and "fd_" not in member and "catalogos" not in member


def test_find_member_errors():
    ed = get_edition("2025")
    with pytest.raises(LookupError, match="none"):
        find_member(["personas02.csv"], ed, "personas", 1)
    with pytest.raises(ValueError, match="does not publish"):
        find_member(["x.csv"], get_edition("2015"), "migrantes", 1)


# --- mirror filenames ---------------------------------------------------------------

def test_filename_roundtrip():
    for e in EDITIONS:
        for t in e.tables:
            states = [None] if t in NATIONAL_TABLES else [1, 9, 32]
            for s in states:
                name = e.filename(t, s)
                assert FILE_RE.match(name)
                assert parse_filename(name) == (t, e.period, s)
    assert cpv_filename("personas", "2025", 9) == "cpv_personas_2025_09.parquet"
    assert cpv_filename("estimaciones", "2025") == "cpv_estimaciones_2025.parquet"


def test_filename_errors():
    with pytest.raises(ValueError, match="national table"):
        cpv_filename("estimaciones", "2025", 9)
    with pytest.raises(ValueError, match="per state"):
        cpv_filename("personas", "2025")
    for bad in ("cpv_personas_2025.parquet", "cpv_estimaciones_2025_09.parquet",
                "cpv_nope_2025_01.parquet", "enigh_poblacion_2024.parquet",
                "cpv_iter_2020_1.parquet"):
        with pytest.raises(ValueError):
            parse_filename(bad)


def test_microdata_tables_are_per_state():
    assert not (set(MICRO_TABLES) & NATIONAL_TABLES)


def test_zip_entry_and_dictionaries():
    e = get_edition("2025")
    entry = cpv_zip_entry(e, "microdatos", 9)
    assert entry.url.endswith("eic2025_micro_09_csv.zip")
    assert str(entry.extract_dir) == "cpv/2025/microdatos"
    assert cpv_zip_entry(e, "estimaciones").url.endswith("_105_csv.zip")
    assert dictionary_url("2025", "fd") == f"{_P}/eic/2025/microdatos/eic2025_micro_fd.xlsx"
    assert set(DICTIONARY_URLS) == set(EDITIONS_BY_PERIOD)


# --- Marco Geoestadístico editions ----------------------------------------------------

def test_mg_legacy_2020_unchanged():
    url = marco_geo_zip_url(9)
    assert url == ("https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/"
                   "espanol/bvinegi/productos/geografia/marcogeo/889463807469/"
                   "09_ciudaddemexico.zip")
    assert mg_filename("ent", 9) == "mg_ent_09.parquet"


def test_mg_2025_and_national_editions():
    assert marco_geo_zip_url(1, "2025").endswith("/marcogeo/794551196649/01_aguascalientes.zip")
    assert mg_filename("mun", 9, "2025") == "mg_mun_2025_09.parquet"
    assert marco_geo_national_url("2010").endswith("/marc_geo/702825292812_s.zip")
    with pytest.raises(ValueError, match="national ZIP"):
        marco_geo_zip_url(1, "2010")
    with pytest.raises(ValueError, match="per state"):
        marco_geo_national_url("2025")
    with pytest.raises(ValueError, match="unknown Marco"):
        mg_filename("mun", 1, "2015")
    # Every edition that names an MG frame points at a known MG edition.
    for e in EDITIONS:
        assert e.mg_period is None or e.mg_period in MG_EDITIONS


def test_per_state_matches_national_tables():
    for e in EDITIONS:
        for product in e.products:
            national = all(t in NATIONAL_TABLES for t in e.tables_in(product))
            assert e.per_state(product) is not national
    with pytest.raises(ValueError, match="no 'iter' product"):
        get_edition("2025").per_state("iter")


def test_zip_cache_names_unique():
    """The build caches ZIPs flat under INEGI's basenames — they must never collide."""
    names = [e.zip_filename(p, s)
             for e in EDITIONS for p in e.products
             for s in (range(1, 33) if e.per_state(p) else [None])]
    assert len(names) == len(set(names))


# --- build script (scripts/build_cpv.py) — pure helpers, no download -------------------

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_cpv as _bcpv  # noqa: E402
import build_enigh as _benigh  # noqa: E402

_ACCENTS = "CVE_ENT,NOM_LOC\n01,Jesús María\n09,Álvaro Obregón\n"
_MANY = ("CVE_ENT,NOM_LOC\n" + "01,Jesús María\n09,Álvaro Obregón\n" * 50).encode("utf-8")


@pytest.mark.parametrize("raw, expected", [
    (b"a,b\n1,2\n", "utf-8"),                                          # ASCII
    (_ACCENTS.encode("utf-8"), "utf-8"),                               # clean UTF-8
    (_MANY + b"09,x\xe9y\n", "utf-8/replace"),                         # a few bad bytes
    (_ACCENTS.encode("cp1252"), "cp1252"),                             # single-byte
    (_ACCENTS.encode("latin-1") + b"\x81\n", "latin-1"),               # undefined in cp1252
    (_MANY + "ñ".encode("utf-8")[:1], "utf-8/replace"),               # truncated tail
    (_ACCENTS.encode("utf-8") + "ñ".encode("utf-8")[:1], "latin-1"),  # ≥10% bad; 0x81 ∉ cp1252
])
@pytest.mark.parametrize("chunk", [1, 3, 1 << 24])
def test_sniff_encoding_streaming_matches_one_shot(tmp_path, raw, expected, chunk):
    path = tmp_path / "x.csv"
    path.write_bytes(raw)
    assert _bcpv._sniff_encoding(path, chunk_size=chunk) == expected
    assert _benigh._sniff_encoding(path) == expected  # same decision as the ENIGH build


def _read(tmp_path, raw: bytes):
    path = tmp_path / "x.csv"
    path.write_bytes(raw)
    return _bcpv._read_csv_arrow(path)


def test_read_csv_arrow_faithful(tmp_path):
    raw = ('﻿CVE_ENT,CVE_MUN,FACTOR,NOTA,TXT\n'
           '01,001,12,NA," a\nb "\n'
           '09,,0007,N/A,""\n').encode("utf-8")
    table, enc = _read(tmp_path, raw)
    assert enc == "utf-8"
    assert table.column_names == ["CVE_ENT", "CVE_MUN", "FACTOR", "NOTA", "TXT"]  # BOM gone
    assert {str(t) for t in table.schema.types} == {"string"}
    assert table.to_pydict() == {
        "CVE_ENT": ["01", "09"],           # zero-padding kept
        "CVE_MUN": ["001", None],          # empty cell → null
        "FACTOR": ["12", "0007"],          # no numeric inference
        "NOTA": ["NA", "N/A"],             # NA-like strings kept verbatim
        "TXT": [" a\nb ", None],           # quoted newline + whitespace kept; "" → null
    }


def test_read_csv_arrow_encodings(tmp_path):
    table, enc = _read(tmp_path, _ACCENTS.encode("cp1252"))
    assert enc == "cp1252"
    assert table.column("NOM_LOC").to_pylist() == ["Jesús María", "Álvaro Obregón"]
    table, enc = _read(tmp_path, _MANY + b"09,x\xe9y\n")
    assert enc == "utf-8/replace"
    assert table.num_rows == 101 and table.column("NOM_LOC")[-1].as_py() == "x�y"
    assert table.column("NOM_LOC")[0].as_py() == "Jesús María"


def test_arrow_parquet_matches_pandas_path(tmp_path):
    """Same frame as the ENIGH pandas path (``_read_csv_robust`` + ``_df_to_parquet``) on a
    file without pandas' default NA strings (those stay verbatim here — see STEP_1a)."""
    import pandas as pd

    csv = tmp_path / "v.csv"
    csv.write_bytes(("ID_VIV,CVE_MUN,FACTOR,NOM\n"
                     "010010000001,001,12,Jesús\n"
                     "010010000002,,0007, \n").encode("utf-8"))
    df, _ = _benigh._read_csv_robust(csv)
    _benigh._df_to_parquet(df, tmp_path / "pandas.parquet")
    table, _ = _bcpv._read_csv_arrow(csv)
    _bcpv._table_to_parquet(table, tmp_path / "arrow.parquet")
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "pandas.parquet"),
                                  pd.read_parquet(tmp_path / "arrow.parquet"))


def test_read_csv_arrow_rejects_duplicate_header(tmp_path):
    with pytest.raises(ValueError, match="duplicates"):
        _read(tmp_path, b"A,B,A\n1,2,3\n")


def test_build_plan():
    e25 = get_edition("2025")
    jobs = _bcpv._plan([e25], list(TABLES), [1, 9])
    assert [(j[1], j[2], j[3]) for j in jobs] == [
        ("microdatos", 1, ("viviendas", "personas", "migrantes")),
        ("microdatos", 9, ("viviendas", "personas", "migrantes")),
        ("estimaciones", None, ("estimaciones",)),   # national: once, whatever --states
    ]
    jobs = _bcpv._plan([e25], ["personas"], list(range(1, 33)))
    assert len(jobs) == 32 and all(j[3] == ("personas",) for j in jobs)
    assert _bcpv._plan([e25], ["iter"], [1]) == []   # 2025 has no ITER
    full = _bcpv._plan([e25], list(TABLES), list(range(1, 33)))
    assert sum(len(j[3]) for j in full) == 97          # 96 microdata files + estimaciones


@pytest.mark.parametrize("key", [("2025", "microdatos"), ("2025", "estimaciones"),
                                 ("2005", "microdatos"), ("2020", "iter")])
def test_member_plan(key):
    period, product = key
    ed = get_edition(period)
    state = None if product == "estimaciones" else 1
    names = _PROBED_MEMBERS[key]
    tables = ed.tables_in(product)
    plan = _bcpv._member_plan(names, ed, tables, state)
    assert set(plan) == set(tables) and all(plan.values())
    assert len(set(plan.values())) == len(plan)
    # A member missing from the ZIP is reported as None, not raised.
    first = tables[0]
    plan = _bcpv._member_plan([n for n in names if n != plan[first]], ed, tables, state)
    assert plan[first] is None


def test_build_cli_guards(capsys):
    assert _bcpv.main(["--dry-run", "--periods", "2010", "--states", "1"]) == 0
    out = capsys.readouterr().out
    assert "MC2010_01_dbf.zip" in out and "cpv_personas_2010_01.parquet" in out
    with pytest.raises(SystemExit):
        _bcpv.main(["--periods", "2005", "--states", "1"])   # edition not enabled yet
    with pytest.raises(SystemExit):
        _bcpv.main(["--dry-run", "--states", "33"])


# --- unit 1b: dictionaries (scripts/_dict_fd.py), schema map, group schemas ------------

import zipfile  # noqa: E402

import pandas as pd  # noqa: E402
import pandera.pandas as pa  # noqa: E402

import _dict_fd as _fd  # noqa: E402
import mxcensus  # noqa: E402
from mxcensus import _schema_groups as sg  # noqa: E402
from mxcensus._resources import cpv_schema_map, variables_cpv, variables_cpv_core  # noqa: E402
from mxcensus.cpv import (  # noqa: E402
    _CODE_REGEX, _WEIGHTS, _code_rule, _core_for, _fingerprint, _group_of, _group_schema,
)

_SM = cpv_schema_map()
_TABLE_GROUPS = [(t, g) for t in TABLES if t in _SM for g in _SM[t]["groups"]]


def _xlsx(path, sheets: dict) -> None:
    """A minimal workbook (the parts ``read_xlsx`` reads): text as shared strings, ints as
    literal values, a ``("inline", text)`` tuple as an inline string, ``None`` as no cell."""
    shared, sheet_xml = [], []
    for rows in sheets.values():
        out = []
        for i, row in enumerate(rows, 1):
            cells = []
            for j, v in enumerate(row):
                ref = f"{chr(65 + j)}{i}"
                if v is None:
                    continue
                if isinstance(v, tuple):
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{v[1]}</t></is></c>')
                elif isinstance(v, int):
                    cells.append(f'<c r="{ref}"><v>{v}</v></c>')
                else:
                    shared.append(v)
                    cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
            out.append(f'<row r="{i}">{"".join(cells)}</row>')
        sheet_xml.append("".join(out))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rns}><sheets>' + "".join(
            f'<sheet name="{n}" sheetId="{k}" r:id="rId{k}"/>' for k, n in enumerate(sheets, 1))
            + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{k}" Target="worksheets/sheet{k}.xml"/>'
                             for k in range(1, len(sheets) + 1)) + "</Relationships>")
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(
            f"<si><r><t>{s[:2]}</t></r><r><t>{s[2:]}</t></r></si>" for s in shared) + "</sst>")
        for k, body in enumerate(sheet_xml, 1):
            z.writestr(f"xl/worksheets/sheet{k}.xml", f"<worksheet {ns}><sheetData>{body}"
                       "</sheetData></worksheet>")


_HDR = [None, "Cons.", "Descripción", "Mnemónico", "Pregunta y categoría", "Tipo",
        "Rango válido", "Longitud"]
_FD_SHEETS = {
    "Índice": [[None, "ENCUESTA"], [None, "Cons.", "Nombre de la tabla/Hoja"]],
    "PERSONAS": [
        [None, None, "ENCUESTA INTERCENSAL 2025"],
        _HDR,
        [None, "LISTA DE PERSONAS"],                                         # section
        [None, 1, "Sexo", "SEXO", "(NOMBRE) es:", "Carácter", "{1, 3}", 1],
        [None, None, None, None, "Hombre", None, 1],
        [None, None, None, None, "Mujer", None, 3],
        [None, 2, "Edad", "EDAD", "¿Cuántos años?", "Numérico", "{0..130, 999}", 3],
        [None, None, None, None, "Menos de un año", None, "0"],
        [None, None, None, None, "Años", None, "1..130"],
        [None, None, None, None, "No especificado", None, "999"],
        [None, None, "Dificultad", "--", "¿Cuánta dificultad tiene para:"],  # stem ('--')
        [None, 3, "Ver", "DIS_VER", "ver?", "Carácter", "{1, 2, 9, Nulo}", 1],
        [None, None, " ", None, "Sí", None, "1"],                            # stray blank C
        [None, None, None, None, "No", None, "2"],
        [None, None, None, None, "No especificado", None, "9"],
        [None, None, None, None, "Blanco por pase", None, "Nulo"],
        [None, None, None, None, None, None, None, 4],                       # subtotal
        [None, 4, "Madre", "IDENT_MADRE", "¿La madre:", "Carácter", "{01..03, 97, 99}", 2],
        [None, None, None, None, "¿Quién es?", None, "01..03"],
        [None, None, None, None, "ya falleció?", None, "97"],
        [None, None, None, None, "No especificado", None, "99"],
        [None, 5, "Parentesco", "PARENTESCO", "¿Qué es?", "Carácter",
         "{101..201, 999}\n(Según clasificador de parentesco)", 3],
        [None, None, None, None, "Clave de parentesco", None, "101..201"],
        [None, None, None, None, "No especificado", None, "999"],
        [None, 6, "Ocupación", "OCUPACION_C", "¿Ocupación?", "Carácter",
         "{111..989, 999} (Según clasificador de ocupación)", 3],
        [None, None, None, None, "Clave", None, "111.. 989"],
        [None, None, None, None, "No especificado", None, "999"],
        [None, 7, "Ingreso", "INGTRMEN", ("inline", "¿Cuánto gana?"), "Numérico",
         "{0..999998, 999999, Nulo}", 6],
        [None, None, None, None, "No recibe", None, "0"],
        [None, None, None, None, "Ingresos especificados", None, "1..999997"],
        [None, None, None, None, "Ingresos mayores a 999,997", None, "999998"],
        [None, None, None, None, "No especificado", None, "999999"],
        [None, 8, "Año", "FECHA_NAC_A", "¿Año?", "Carácter", "{1925..2025, 9999}", 4],
        [None, None, None, None, "Año", None, "1925..2025"],
        [None, None, None, None, "No especificado", None, "9999"],
        [None, 9, "Factor", "FACTOR", "Factor", "Numérico", "{1..99999}", 5],
        [None, 10, "Localidad", "LOC50K", "Clave", "Carácter", "{0000..9999}", 4],
        [None, None, None, None, "Menor de 50 000", None, "0000"],
        [None, None, None, None, "Mayor", None, "0001..9999"],
        [None, None, None, None, None, None, "TOTAL DE CARACTERES: ", 42],
    ],
}


def _catalog_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("PARENTESCO.csv", "﻿CLAVE,DESCRIPCION\n101,Jefa(e)\n201,Esposa(o)\n999,NE\n")
        z.writestr("OCUPACION.csv", "﻿CLAVE,DESCRIPCION\n111,Funcionarios\n112,Directores\n")
        z.writestr("MUNICIPIO.csv", "﻿CVE_ENT,DESC_ENT,CVE_MUN,DESC_MUN\n001,Ags,001,Ags\n")
        z.writestr("ENTIDAD_PAIS.csv", "﻿CLAVE,DESCRIPCION\n001,Aguascalientes\n")
        z.writestr("ENTIDAD.csv", "﻿CLAVE,DESCRIPCION\n01,Aguascalientes\n")


def test_read_xlsx_and_catalogs(tmp_path):
    _xlsx(tmp_path / "fd.xlsx", _FD_SHEETS)
    book = _fd.read_xlsx(tmp_path / "fd.xlsx")
    assert list(book) == ["Índice", "PERSONAS"]
    rows = book["PERSONAS"]
    assert rows[1] == dict(zip("BCDEFGH", _HDR[1:]))        # shared strings (rich-text runs)
    assert rows[3]["B"] == "1" and rows[3]["H"] == "1"       # literal values
    assert rows[12] == {"E": "Sí", "G": "1"}                 # whitespace-only cell dropped
    _catalog_zip(tmp_path / "cat.zip")
    cats = _fd.read_catalogs(tmp_path / "cat.zip")
    assert cats["PARENTESCO"] == {"101": "Jefa(e)", "201": "Esposa(o)", "999": "NE"}
    assert cats["MUNICIPIO"] == {"001001": "Ags"}             # entity + municipality key
    assert _fd.match_catalog("entidad federativa y país", cats) == "ENTIDAD_PAIS"
    assert _fd.match_catalog("ocupación", cats) == "OCUPACION"
    assert _fd.match_catalog("religión", cats) is None


def test_parse_fd_xlsx(tmp_path):
    _xlsx(tmp_path / "fd.xlsx", _FD_SHEETS)
    _catalog_zip(tmp_path / "cat.zip")
    doc = _fd.parse_fd(tmp_path / "fd.xlsx", _fd.read_catalogs(tmp_path / "cat.zip"))
    assert list(doc) == ["personas"]                          # Índice has no Mnemónico
    p = doc["personas"]
    assert "--" not in p and list(p)[:3] == ["SEXO", "EDAD", "DIS_VER"]
    assert p["SEXO"]["Categorías"] == {"1": "Hombre", "3": "Mujer"}
    assert p["EDAD"]["Tipo"] == "numeric" and p["EDAD"]["Rango"] == [0, 130]
    assert p["EDAD"]["Especiales"] == {"999": "No especificado"}
    assert p["DIS_VER"]["Pregunta"] == "¿Cuánta dificultad tiene para: ver?"   # stem prefixed
    assert p["DIS_VER"]["Categorías"] == {"1": "Sí", "2": "No"}               # Nulo skipped
    assert p["DIS_VER"]["Especiales"] == {"9": "No especificado"}
    assert list(p["IDENT_MADRE"]["Categorías"]) == ["01", "02", "03", "97"]   # identity, in order
    assert p["PARENTESCO"]["Catálogo"] == "PARENTESCO"
    assert p["PARENTESCO"]["Categorías"] == {"101": "Jefa(e)", "201": "Esposa(o)"}
    assert p["OCUPACION_C"]["Categorías"] == {"111": "Funcionarios", "112": "Directores"}
    ing = p["INGTRMEN"]                                       # 0 and the top-code are values
    assert ing["Pregunta"] == "¿Cuánto gana?" and ing["Rango"] == [0, 999998]
    assert ing["Especiales"] == {"999999": "No especificado"}
    assert p["FECHA_NAC_A"]["Rango"] == [1925, 2025] and len(p["FECHA_NAC_A"]["Categorías"]) == 101
    assert p["FACTOR"]["Rango"] == [1, 99999]                 # header-only numeric
    loc = p["LOC50K"]                                         # a range too wide to enumerate
    assert loc["Tipo"] == "string" and not loc["Categorías"] and "0000 = Menor" in loc["Nota"]
    # without the catalogs, a classified range is left unenumerated, with a note
    bare = _fd.parse_fd(tmp_path / "fd.xlsx")["personas"]
    assert bare["OCUPACION_C"]["Tipo"] == "string" and "no disponible" in bare["OCUPACION_C"]["Nota"]


def test_fd_entry_rules(tmp_path):
    _xlsx(tmp_path / "fd.xlsx", _FD_SHEETS)
    _catalog_zip(tmp_path / "cat.zip")
    p = _fd.parse_fd(tmp_path / "fd.xlsx", _fd.read_catalogs(tmp_path / "cat.zip"))["personas"]
    e, src = _fd.fd_entry("PARENTESCO", {"101", "999"}, None, p["PARENTESCO"], 64)
    assert src == "fd" and e["Tipo"] == "categorical" and e["Catálogo"] == "PARENTESCO"
    e, src = _fd.fd_entry("OCUPACION_C", None, None, p["OCUPACION_C"], 1)   # catalog > threshold
    assert src == "fd" and e["Tipo"] == "string" and "Categorías" not in e
    assert e["Especiales"] == {"999": "No especificado"} and "OCUPACION" in e["Nota"]
    e, src = _fd.fd_entry("EDAD", None, None, p["EDAD"], 64)
    assert e["Tipo"] == "numeric" and e["Rango"] == [0, 130]                 # FD range kept
    e, src = _fd.fd_entry("FECHA_NAC_A", None, None, p["FECHA_NAC_A"], 64)  # 101 years → number
    assert e["Tipo"] == "numeric" and e["Rango"] == [1925, 2025] and e["Especiales"] == {"9999": "No especificado"}
    e, src = _fd.fd_entry("SEXO", {"1", "3", "5"}, None, p["SEXO"], 64)      # undocumented code
    assert src == "fd+data" and e["Categorías"]["5"] == "5" and "el FD" in e["Nota"]
    e, src = _fd.fd_entry("SEXO", {"1"}, {"Tipo": "string"}, p["SEXO"], 64)  # core wins
    assert (e, src) == ({"Tipo": "string"}, "core")
    e, src = _fd.fd_entry("NEW", {"a"}, None, None, 64)
    assert src == "data" and e["Categorías"] == {"a": "a"}


def test_parse_indicator_csv(tmp_path):
    path = tmp_path / "dicc.csv"
    path.write_text(
        "DESCRIPTOR DE LA BASE DE DATOS,,,,,\n,,,,,\n"
        "Cons.,Indicador,Descripción,Mnemónico,Rangos,Long.\n"
        "IDENTIFICACIÓN GEOGRÁFICA,,,,,\n"
        "1,Clave estatal,Código de la entidad,CVE_ENT,00…32,2\n"
        "2,Tipo de estimador,\"Valor, error…\",ESTIMADOR,Alfanumérico,50\n"
        "3,Población,Total de personas,POBTOT,0 … 999999999,9\n"
        "4,Porcentaje,Por cada cien,PCN_X,0 … 100.00,6\n"
        ",,,,,\nNota: Incluye todas las localidades.,,,,,\nNA: No aplica.,,,,,\n"
        "MI: No disponible por muestra insuficiente.,,,,,\n* Municipio censado.,,,,,\n",
        encoding="utf-8")
    d = _fd.parse_indicator_csv(path)
    assert list(d) == ["CVE_ENT", "ESTIMADOR", "POBTOT", "PCN_X"]
    assert d["CVE_ENT"]["Tipo"] == "string" and d["ESTIMADOR"]["Tipo"] == "string"
    assert d["POBTOT"]["Tipo"] == "numeric" and "Decimales" not in d["POBTOT"]
    assert d["PCN_X"]["Decimales"] == "2" and d["PCN_X"]["Rango"] == []
    assert d["PCN_X"]["Especiales"] == {"NA": "No aplica",
                                        "MI": "No disponible por muestra insuficiente"}
    assert d["PCN_X"]["Descripción"] == "Porcentaje" and d["PCN_X"]["Definición"] == "Por cada cien"
    e, src = _fd.fd_entry("PCN_X", None, None, d["PCN_X"], 0)
    assert e["Tipo"] == "numeric" and e["Decimales"] == "2" and e["Rangos"] == "0 … 100.00"
    assert "Rango" not in e                         # the column mixes the five estimators


def test_group_schemas_partial_states_and_latest():
    def rec(period, state, cols):
        return {"table": "personas", "period": period, "state": state, "columns": cols,
                "fingerprint": _fingerprint(cols), "rows": 1}
    a, b = ["X", "Y"], ["X", "Y", "Z"]
    doc = _bcpv._group_schemas([rec("2025", 9, b), rec("2025", 1, a), rec("2020", 1, b),
                                rec("2025", 2, b)])["personas"]
    assert doc["fingerprints"] == {_fingerprint(b): "g01", _fingerprint(a): "g02"}
    g1, g2 = doc["groups"]["g01"], doc["groups"]["g02"]
    assert g1["periods"] == ["2020", "2025"] and g1["files"] == 3
    assert g1["states"] == {"2025": [2, 9]} and g2["states"] == {"2025": [1]}
    assert doc["latest"] == "g01"                   # majority of the newest edition
    whole = _bcpv._group_schemas([rec("2025", 1, a), rec("2025", 2, a)])["personas"]
    assert "states" not in whole["groups"]["g01"]


def test_mirror_files_and_thresholds(tmp_path):
    for n in ("cpv_personas_2025_01.parquet", "cpv_estimaciones_2025.parquet",
              "cpv_x.parquet", "enigh_poblacion_2024.parquet"):
        (tmp_path / n).touch()
    assert [p.name for p in _bcpv._mirror_files(tmp_path)] == [
        "cpv_estimaciones_2025.parquet", "cpv_personas_2025_01.parquet"]
    assert _bcpv._TABLE_THRESHOLD == {"estimaciones": 0, "iter": 0, "ageb": 0}


# --- the bundled schema map / dictionaries --------------------------------------------

def _cols(table, gid):
    return _SM[table]["groups"][gid]["columns"]


_CODE_SAMPLE = {"AGEB": "011A", "CVE_AGEB": "011A"}   # a value of each _CODE_REGEX shape


def _valid_value(table: str, gid: str, col: str) -> str:
    """A value that should pass ``_group_schema(table, gid)`` for ``col``."""
    if col in _WEIGHTS:
        return "1"
    meta = variables_cpv(table, gid).get(col) or {}
    cats = meta.get("Categorías") or {}
    if cats:
        return next(iter(cats))
    if sg.norm_tipo(meta) == "numeric":
        rng = meta.get("Rango") or []
        return str(rng[0]) if rng else "1"
    if col.upper() in _CODE_REGEX:                       # 2010 aggregates: lower case
        return _CODE_SAMPLE[col.upper()]
    if _code_rule(col, meta) is not None:
        width = str(meta.get("Longitud") or "")
        return "0" * int(width) if meta.get("Catálogo") and width.isdigit() else "01"
    return "x"


def _valid_frame(table, gid, rows=3):
    return pd.DataFrame({c: [_valid_value(table, gid, c)] * rows for c in _cols(table, gid)},
                        dtype=str)


def test_schema_map_per_table():
    assert _SM and set(_SM) <= set(TABLES)
    for t in _SM:
        assert set(_SM[t]) == {"latest", "fingerprints", "groups"}
        assert _SM[t]["latest"] in _SM[t]["groups"]
        for gid, g in _SM[t]["groups"].items():
            assert g["n_columns"] == len(g["columns"]) and g["files"] >= 1
            assert set(g) <= {"n_columns", "files", "periods", "states", "columns"}
            assert set(g.get("states", {})) <= set(g["periods"])


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_fingerprint_round_trips(table, gid):
    fp = _fingerprint(_cols(table, gid))
    assert _SM[table]["fingerprints"][fp] == gid
    assert _group_of(table, _valid_frame(table, gid)) == gid


def test_group_of_unknown_raises():
    with pytest.raises(ValueError, match="CPV file schema not found in cpv_schema_map.yaml"):
        _group_of("personas", pd.DataFrame({"zzz": ["1"]}))


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_group_schema_accepts_valid_frame(table, gid):
    _group_schema(table, gid).validate(_valid_frame(table, gid), lazy=True)


@pytest.mark.parametrize("col,bad", [("SEXO", "2"), ("EDAD", "131"), ("FACTOR", "abc"),
                                     ("CVE_ENT", "x1"), ("OCUPACION_C", "12")])
def test_group_schema_rejects(col, bad):
    gid = _SM["personas"]["latest"]
    f = _valid_frame("personas", gid)
    f[col] = [bad] * len(f)
    with pytest.raises(pa.errors.SchemaErrors, match=col):
        _group_schema("personas", gid).validate(f, lazy=True)


def test_estimaciones_sentinels():
    gid = _SM["estimaciones"]["latest"]
    f = _valid_frame("estimaciones", gid, rows=2)
    f["POBTOT"] = ["NA", "1234"]
    f["PCN_P_0A4"] = ["MI", "12.50"]
    _group_schema("estimaciones", gid).validate(f, lazy=True)
    f["POBTOT"] = ["ZZ", "1"]
    with pytest.raises(pa.errors.SchemaErrors, match="POBTOT"):
        _group_schema("estimaciones", gid).validate(f, lazy=True)


def test_core_yaml_contract():
    core = variables_cpv_core()
    for name, meta in core.items():
        assert name == name.upper(), name
        assert meta.get("Tipo") in ("categorical", "numeric", "string"), name
        if meta.get("Ordenada"):
            assert meta.get("Categorías"), name
        if "Rango" in meta:
            assert len(meta["Rango"]) == 2 and meta["Rango"][0] <= meta["Rango"][1], name
        cats, special = meta.get("Categorías") or {}, meta.get("Especiales") or {}
        assert not set(cats) & set(special), name
        labels = list(cats.values()) + list(special.values())
        assert len(labels) == len(set(labels)), f"{name}: duplicate labels"
        assert all(isinstance(k, str) for k in [*cats, *special]), name
    assert core["SEXO"]["Categorías"] == {"1": "Hombre", "3": "Mujer"}
    assert core["TAMLOC"]["Ordenada"] and core["EDAD"]["Especiales"] == {"999": "No especificado"}
    # the core is copied verbatim into every generated group that has the column, when the
    # entry is in scope for the table (``Tablas``: the ITER's TAMLOC is its own 14-class scale)
    for table, gid in _TABLE_GROUPS:
        v = variables_cpv(table, gid)
        for col in set(core) & set(v):
            if col in _core_for(table, _cpv._group_periods(table, gid)):
                assert v[col] == core[col], (table, gid, col)
            else:
                assert v[col] != core[col], (table, gid, col)
    assert all(set(m.get("Tablas") or TABLES) <= set(TABLES) for m in core.values())
    assert all(set(m.get("Periodos") or EDITIONS_BY_PERIOD) <= set(EDITIONS_BY_PERIOD)
               for m in core.values())


def test_generated_dictionaries_cover_every_column():
    for table, gid in _TABLE_GROUPS:
        v = variables_cpv(table, gid)
        assert list(v) == _cols(table, gid), (table, gid)
        for col, meta in v.items():
            assert sg.norm_tipo(meta) in ("categorical", "numeric", "string")
            assert meta.get("Descripción"), (table, gid, col)   # nothing left undocumented


# --- unit 1c: loaders (mxcensus.cpv, mxcensus.cpv_aggregates) --------------------------

import functools  # noqa: E402
import warnings  # noqa: E402

import numpy as np  # noqa: E402

from mxcensus import cpv as _cpv  # noqa: E402
from mxcensus.cpv_aggregates import ESTIMADORES, NIVELES  # noqa: E402

_MIRROR = Path(__file__).resolve().parent.parent / "data" / "parquet"
_REAL = (_MIRROR / "cpv_personas_2025_01.parquet").exists()
_REAL_SKIP = pytest.mark.skipif(not _REAL, reason="no local CPV mirror (data/parquet/)")
# States whose three 2025 microdata tables are on disk (the Mac: 01, 09, 15; wsl: all 32).
_LOCAL_STATES = [s for s in range(1, 33) if all(
    (_MIRROR / cpv_filename(t, "2025", s)).exists() for t in ("viviendas", "personas", "migrantes"))]
_ALL32 = len(_LOCAL_STATES) == 32 and (_MIRROR / "cpv_estimaciones_2025.parquet").exists()

_GEOS = [("00", "000", "0000"), ("01", "000", "0000"), ("01", "001", "0000"),
         ("01", "001", "0001"), ("01", "997", "9997")]
_EST_NIVEL = ["nacional", "estatal", "municipal", "localidad", "resto_estatal"]
_EST_RAW = dict(zip(["Valor", "Error estándar", "Límite inferior de confianza",
                     "Límite superior de confianza", "Coeficiente de variación"],
                    ["10", "1.25", "8", "12", "12.5"]))


def _keyed_frame(table: str, state: int, rows: int = 3) -> pd.DataFrame:
    """A valid frame of ``table``'s latest group with unique keys and the geography of
    ``state`` (municipality 001), as a mirror file would hold."""
    f = _valid_frame(table, _SM[table]["latest"], rows)
    ent = f"{state:02d}"
    viv = [f"{ent}001{i:07d}" for i in range(rows)]
    f["CVE_ENT"], f["CVE_MUN"], f["CVEGEO"], f["LOC50K"] = ent, "001", ent + "001", "0000"
    f["ID_VIV"] = viv
    if "ID_PERSONA" in f:
        f["ID_PERSONA"] = [v + "00001" for v in viv]
    if "ID_MII" in f:
        f["ID_MII"] = [v + "01" for v in viv]
    return f


def _est_frame() -> pd.DataFrame:
    """Synthetic estimaciones: the 5 geographic levels × the 5 estimator rows."""
    gid = _SM["estimaciones"]["latest"]
    rows = []
    for ent, mun, loc in _GEOS:
        for est, val in _EST_RAW.items():
            r = {c: val for c in _cols("estimaciones", gid)}
            r.update(CVEGEO=ent + mun + loc, CVE_ENT=ent, CVE_MUN=mun, CVE_LOC=loc,
                     NOM_ENT="E", NOM_MUN="M", NOM_LOC="L", ESTIMADOR=est,
                     PCN_P_0A4="MI" if loc == "0001" else val)
            r["POBFEM"] = "NA" if mun == "997" else val
            rows.append(r)
    return pd.DataFrame(rows, columns=_cols("estimaciones", gid), dtype=str)


@pytest.fixture
def fake_mirror(monkeypatch):
    """``POOCH.fetch`` echoes the requested name (recorded); ``read_parquet`` returns a
    valid synthetic frame for the mirror file it is given."""
    from mxcensus.data import _registry
    fetched: list[str] = []
    monkeypatch.setattr(_registry.POOCH, "fetch", lambda f, **_: fetched.append(f) or f)

    def _fake_read(path, *_, **__):
        table, _period, state = parse_filename(Path(path).name)
        return _est_frame() if table == "estimaciones" else _keyed_frame(table, state)

    monkeypatch.setattr(pd, "read_parquet", _fake_read)
    return fetched


def _no_warnings():
    ctx = warnings.catch_warnings()
    ctx.__enter__()
    warnings.simplefilter("error")
    return ctx


def test_key_specs_nest_and_skip():
    assert _cpv._PERSON_KEY_SPEC[:1] == _cpv._DWELLING_KEY_SPEC == _cpv._MIGRANT_KEY_SPEC[:1]
    f2010 = pd.DataFrame({"ID_VIV": ["1"], "ID_PER": ["1"], "ID_MIN": ["1"]})
    assert _cpv._level_key(_cpv._PERSON_KEY_SPEC, f2010) == ["ID_VIV", "ID_PER"]
    assert _cpv._level_key(_cpv._MIGRANT_KEY_SPEC, f2010) == ["ID_VIV", "ID_MIN"]
    assert {"ID_VIV", "ID_PERSONA", "ID_PER", "ID_MII", "ID_MIN"} <= _cpv._KEY_COLUMNS
    assert set(_cpv._GEO_CODES) | set(_cpv._POINTERS) | _cpv._KEY_COLUMNS == _cpv._SKIP
    columns = {c for t in _SM for g in _SM[t]["groups"].values() for c in g["columns"]}
    assert set(_cpv._POINTERS) <= columns           # every pointer exists in 2025
    for ptr in _cpv._POINTERS:     # …and codes person numbers 01-54 as themselves (≥ 96: other)
        for table, gid in _TABLE_GROUPS:              # in every edition that has it
            if ptr not in _cols(table, gid):
                continue
            meta = variables_cpv(table, gid)[ptr]
            if sg.norm_tipo(meta) == "numeric":       # EIC 2015 / CPV 2010: the number itself
                lo, hi = meta["Rango"]
                assert lo in (0, 1) and hi in (54, 98, 99), (ptr, gid)
                assert all(int(k) > hi for k in meta.get("Especiales") or {}), (ptr, gid)
                continue
            if sg.norm_tipo(meta) == "string":        # CPV 2010 NUMPER: a 5-digit code
                assert not meta.get("Categorías"), (ptr, gid)
                continue
            cats = meta["Categorías"]
            assert all((k == v) == (int(k) <= 54) for k, v in cats.items()), (ptr, gid)
            assert sum(int(k) <= 54 for k in cats) >= 50, (ptr, gid)


def test_variables_cpv_labels_merges_core_and_renames(monkeypatch):
    labels = mxcensus.variables_cpv_labels("personas", _SM["personas"]["latest"])
    assert labels["SEXO"]["Categorías"] == {"1": "Hombre", "3": "Mujer"}
    assert labels["TAMLOC"]["Ordenada"] and "ESTIMADOR" in labels     # core overlay
    # a legacy lower-case raw name is keyed under its harmonized name too
    monkeypatch.setattr(_cpv, "_RENAME_CORE", {"ENT": "CVE_ENT"})
    monkeypatch.setattr(_cpv, "variables_cpv",
                        lambda t, g: {"ent": {"Descripción": "x"}, "otra": {"Descripción": "y"}})
    merged = _cpv.variables_cpv_labels.__wrapped__("personas", "gXX")
    assert merged["ent"]["Descripción"] == "x" and merged["OTRA"] == merged["otra"]
    assert merged["CVE_ENT"] == variables_cpv_core()["CVE_ENT"]          # core wins


@pytest.mark.parametrize("table,gid", _TABLE_GROUPS)
def test_load_cpv_labels_offline(monkeypatch, table, gid):
    frame = _valid_frame(table, gid)
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: frame.copy())
    raw = mxcensus.load_cpv(survey_path=Path("x.parquet"), table=table)
    assert raw.equals(frame)
    lab = mxcensus.load_cpv(survey_path=Path("x.parquet"), table=table, labels=True)
    variables = mxcensus.variables_cpv_labels(table, gid)
    for col in lab.columns:
        meta = variables.get(col)
        if meta is None or col in _cpv._SKIP:
            assert lab[col].dtype == frame[col].dtype, col
        elif col in _WEIGHTS or sg.norm_tipo(meta) == "numeric":
            assert lab[col].dtype.kind in "fiu", (col, lab[col].dtype)
        elif sg.norm_tipo(meta) == "categorical":
            assert isinstance(lab[col].dtype, pd.CategoricalDtype), col
            assert lab[col].dtype.ordered == bool(meta.get("Ordenada")), col


def test_load_cpv_unmapped_code_raises(monkeypatch):
    frame = _valid_frame("personas", _SM["personas"]["latest"])
    frame["SEXO"] = ["1", "2", "3"]
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: frame.copy())
    with pytest.warns(UserWarning, match="SEXO/isin"):               # raw: warns
        mxcensus.load_cpv(survey_path=Path("x.parquet"), table="personas")
    with pytest.warns(UserWarning), pytest.raises(ValueError, match=r"'SEXO': \['2'\]"):
        mxcensus.load_cpv(survey_path=Path("x.parquet"), table="personas", labels=True)


# --- harmonize ---------------------------------------------------------------------------

def test_harmonize_2025_is_identity_up_to_factor_dtype():
    for table in ("viviendas", "personas", "migrantes"):
        f = _keyed_frame(table, 9)
        ctx = _no_warnings()
        h = _cpv._harmonize(f, table)
        ctx.__exit__(None, None, None)
        assert list(h.columns) == list(f.columns)
        assert h.drop(columns="FACTOR").equals(f.drop(columns="FACTOR"))
        assert h["FACTOR"].dtype.kind in "fi"
        assert _cpv._harmonize(h, table).equals(h)                       # idempotent
        _cpv._latest_schema(table).validate(h, lazy=True)


def test_harmonize_pads_derives_and_uppercases():
    f = pd.DataFrame({"cve_ent": ["1", "15"], "cve_mun": ["7", "121"], "loc50k": ["1", None],
                      "id_viv": ["a", "b"], "factor": ["3", "4"], "otra": ["x", "y"]}, dtype=str)
    h = _cpv._harmonize(f, "viviendas")
    assert list(h.columns) == ["CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "ID_VIV", "FACTOR", "OTRA"]
    assert list(h["CVE_ENT"]) == ["01", "15"] and list(h["CVE_MUN"]) == ["007", "121"]
    assert list(h["CVEGEO"]) == ["01007", "15121"]
    assert h["LOC50K"].iloc[0] == "0001" and pd.isna(h["LOC50K"].iloc[1])
    assert list(h["FACTOR"]) == [3, 4] and list(h["OTRA"]) == ["x", "y"]
    assert _cpv._harmonize(h, "viviendas").equals(h)


def test_harmonize_checks_cvegeo_and_warns_on_missing_core():
    f = _keyed_frame("personas", 1)
    f.loc[0, "CVEGEO"] = "01999"
    with pytest.warns(UserWarning, match=r"CVEGEO differs from CVE_ENT\+CVE_MUN in 1 row"):
        _cpv._harmonize(f, "personas")
    with pytest.warns(UserWarning, match=r"lacks core column\(s\) \['CVE_ENT', 'ID_PERSONA'\]"):
        _cpv._harmonize(pd.DataFrame({"ID_VIV": ["1"]}), "personas")
    est = _est_frame()                                       # 9-digit CVEGEO = ENT+MUN+LOC
    ctx = _no_warnings()
    _cpv._harmonize(est, "estimaciones")
    ctx.__exit__(None, None, None)


def test_harmonize_rename_and_clash():
    h = _cpv._harmonize(pd.DataFrame({"ent": ["9"], "MUN": ["2"], "ID_VIV": ["x"]}), "viviendas")
    assert list(h.columns) == ["CVEGEO", "CVE_ENT", "CVE_MUN", "ID_VIV"]
    assert h.iloc[0].tolist() == ["09002", "09", "002", "x"]
    with pytest.raises(ValueError, match=r"both a legacy column and its target.*\['CVE_ENT'\]"):
        _cpv._harmonize(pd.DataFrame({"ENT": ["9"], "CVE_ENT": ["09"]}), "viviendas")
    with pytest.raises(ValueError, match=r"\['CVE_ENT'\]"):          # two sources, one target
        _cpv._harmonize(pd.DataFrame({"ENT": ["9"], "ENTIDAD": ["09"]}), "iter")


def test_harmonize_aggregates_table_scoped():
    """The ITER/AGEB spell the entity ENTIDAD and the locality LOC: renamed there only, and
    CVEGEO is the concatenation of every geographic part (9 / 16 characters)."""
    geo = {"ENTIDAD": ["01", "01", "01"], "NOM_ENT": ["A"] * 3, "MUN": ["000", "001", "001"],
           "LOC": ["0000", "0000", "0001"], "POBTOT": ["9", "5", "*"]}
    ctx = _no_warnings()
    it = _cpv._harmonize(pd.DataFrame(geo, dtype=str), "iter")
    ag = _cpv._harmonize(pd.DataFrame({**geo, "AGEB": ["0000", "0000", "045A"],
                                       "MZA": ["000", "000", "012"]}, dtype=str), "ageb")
    ctx.__exit__(None, None, None)
    assert list(it.columns) == ["CVEGEO", "CVE_ENT", "NOM_ENT", "CVE_MUN", "CVE_LOC", "POBTOT"]
    assert list(it["CVEGEO"]) == ["010000000", "010010000", "010010001"]
    assert list(ag.columns[-3:]) == ["POBTOT", "CVE_AGEB", "CVE_MZA"]
    assert list(ag["CVEGEO"]) == ["0100000000000000", "0100100000000000", "010010001045A012"]
    assert it["POBTOT"].tolist() == ["9", "5", "*"]                  # non-core: verbatim
    for t, h in (("iter", it), ("ageb", ag)):
        _cpv._latest_schema(t).validate(h, lazy=True)
        assert _cpv._harmonize(h, t).equals(h)                       # idempotent
    bad = ag.copy()
    bad["CVE_AGEB"] = "45AZ"
    with pytest.raises(pa.errors.SchemaErrors, match="CVE_AGEB"):
        _cpv._latest_schema("ageb").validate(bad, lazy=True)
    # elsewhere ENTIDAD/LOC/AGEB/MZA are not core: kept verbatim (and CVEGEO = ENT+MUN)
    with pytest.warns(UserWarning, match=r"lacks core column\(s\) \['CVE_ENT'"):
        v = _cpv._harmonize(pd.DataFrame({"ENTIDAD": ["1"], "MUN": ["2"], "LOC": ["3"],
                                          "ID_VIV": ["x"]}), "viviendas")
    assert list(v.columns) == ["ENTIDAD", "CVE_MUN", "LOC", "ID_VIV"]
    labels = mxcensus.variables_cpv_labels("ageb", _SM["ageb"]["latest"])
    core = variables_cpv_core()
    assert labels["CVE_AGEB"] == core["CVE_AGEB"] and labels["CVE_LOC"] == core["CVE_LOC"]
    assert labels["AGEB"]["Descripción"] == "Clave del AGEB"          # the raw name: FD entry
    assert "CVE_LOC" not in {_cpv._renames("personas").get(c) for c in ("LOC", "ENTIDAD")}


def test_latest_schema_rejects_unpadded_and_bad_core():
    h = _cpv._harmonize(_keyed_frame("personas", 1), "personas")
    for col, bad in (("CVE_ENT", "1"), ("CVEGEO", "0100"), ("SEXO", "2"), ("FACTOR", "x")):
        f = h.copy()
        f[col] = [bad] * len(f)
        with pytest.raises(pa.errors.SchemaErrors, match=col):
            _cpv._latest_schema("personas").validate(f, lazy=True)
    with pytest.raises(pa.errors.SchemaErrors, match="ID_PERSONA"):
        _cpv._latest_schema("personas").validate(h.drop(columns="ID_PERSONA"), lazy=True)


# --- state / period semantics (synthetic mirror) ----------------------------------------

def test_state_semantics(fake_mirror):
    with pytest.raises(ValueError, match="mirrored per state; pass state="):
        mxcensus.load_cpv(table="personas")
    for bad in (0, 33, True, "9", [], [1, 40], 1.0):
        with pytest.raises(ValueError, match="state"):
            mxcensus.load_cpv(table="personas", state=bad)
    df = mxcensus.load_cpv(table="personas", state=[9, np.int64(1), 9])
    assert fake_mirror == ["cpv_personas_2025_09.parquet", "cpv_personas_2025_01.parquet"]
    assert list(df["CVE_ENT"]) == ["09"] * 3 + ["01"] * 3 and df.index.is_unique
    fake_mirror.clear()
    est = mxcensus.load_cpv(table="estimaciones", state=1)            # national: a row filter
    assert fake_mirror == ["cpv_estimaciones_2025.parquet"]
    assert set(est["CVE_ENT"]) == {"01"} and len(est) == 20


def test_period_and_table_errors(fake_mirror):
    with pytest.raises(ValueError, match="unknown CPV table"):
        mxcensus.load_cpv(table="nope", state=1)
    with pytest.raises(ValueError, match="unknown CPV edition"):
        mxcensus.load_cpv(table="personas", period="1999", state=1)
    with pytest.raises(ValueError, match="'migrantes' is not published.*2015"):
        mxcensus.load_cpv_migrantes("2015", state=1)
    with pytest.raises(ValueError, match="'estimaciones' is not published"):
        mxcensus.load_cpv(table="estimaciones", period=2020)
    assert fake_mirror == []                                          # nothing fetched


def test_mixed_schema_groups(fake_mirror, monkeypatch):
    gid = _SM["personas"]["latest"]
    monkeypatch.setattr(_cpv, "_group_of", lambda t, df: "gA" if df["CVE_ENT"].iloc[0] == "01" else "gB")
    monkeypatch.setattr(_cpv, "_group_schema", lambda t, g: pa.DataFrameSchema())
    with pytest.raises(ValueError, match=r"different schema groups \['gA', 'gB'\]"):
        mxcensus.load_cpv(table="personas", state=[1, 2])
    df = mxcensus.load_cpv(table="personas", state=[1, 2], harmonize=True)
    assert len(df) == 6
    base = mxcensus.variables_cpv_labels("personas", gid)
    other = {**base, "NIVACAD": {**base["NIVACAD"], "Categorías": {"00": "Otro"}},
             "SEXO": {**base["SEXO"], "Descripción": "otra redacción", "Pregunta": "¿?"}}
    monkeypatch.setattr(_cpv, "variables_cpv_labels", lambda t, g: base if g == "gA" else other)
    with pytest.warns(UserWarning, match=r"\['NIVACAD'\] are labelled differently"):
        lab = mxcensus.load_cpv_personas(state=[1, 2], harmonize=True)
    assert lab["NIVACAD"].dtype == frame_dtype("NIVACAD") and isinstance(lab["SEXO"].dtype, pd.CategoricalDtype)
    # wording is not a conflict; the newest group's entry is kept
    with pytest.warns(UserWarning, match="NIVACAD"):
        merged = _cpv._labels_for("personas", ["gA", "gB"])
    assert merged["SEXO"]["Descripción"] == "otra redacción" and "NIVACAD" not in merged
    assert _cpv._label_spec({"Tipo": "Numérico", "Ordenada": False}) == _cpv._label_spec(
        {"Tipo": "numeric", "Rango": None, "Descripción": "x"})


def frame_dtype(col):
    return _keyed_frame("personas", 1)[col].dtype


def test_level_loaders_offline(fake_mirror):
    v, p, m = mxcensus.load_cpv_survey(state=9)
    assert list(v.index.names) == ["ID_VIV"]
    assert list(p.index.names) == ["ID_VIV", "ID_PERSONA"]
    assert list(m.index.names) == ["ID_VIV", "ID_MII"]
    assert p.index.get_level_values("ID_VIV").isin(v.index).all()
    assert m.index.get_level_values("ID_VIV").isin(v.index).all()
    for f in (v, p, m):
        assert f.index.is_unique and f["FACTOR"].dtype.kind in "fi"
        assert f["CVE_ENT"].dtype == frame_dtype("CVE_ENT")              # skip: raw string
    assert isinstance(p["SEXO"].dtype, pd.CategoricalDtype) and p["NUMPER"].dtype == frame_dtype("NUMPER")
    raw = mxcensus.load_cpv_personas(state=9, labels=False)
    assert raw["FACTOR"].dtype.kind in "fi" and raw["SEXO"].dtype == frame_dtype("SEXO")
    assert list(raw.index.names) == ["ID_VIV", "ID_PERSONA"]
    harm = mxcensus.load_cpv_personas(state=9, harmonize=True)
    assert harm.equals(p)                                             # 2025: identity
    *_, none = mxcensus.load_cpv_survey("2015", state=9)              # no migrant table
    assert none is None
    with pytest.raises(TypeError):
        mxcensus.load_cpv_personas()                                  # state is required


# --- estimaciones (synthetic) -------------------------------------------------------------

def test_estimaciones_reshape_and_nivel(fake_mirror):
    e = mxcensus.load_cpv_estimaciones()
    assert list(e.index.names) == ["CVE_ENT", "CVE_MUN", "CVE_LOC"] and len(e) == 5
    assert e.index.is_unique and e.index.is_monotonic_increasing
    nivel = dict(zip(_GEOS, _EST_NIVEL))
    assert all(e.loc[g, "NIVEL"] == n for g, n in nivel.items())
    assert e["NIVEL"].dtype == pd.CategoricalDtype(NIVELES, ordered=True)
    assert list(e.columns[:5]) == ["NIVEL", "CVEGEO", "NOM_ENT", "NOM_MUN", "NOM_LOC"]
    assert "ESTIMADOR" not in e.columns and len(e.columns) == 341 + 5
    assert str(e["POBTOT"].dtype) == "Int64" and (e["POBTOT"] == 10).all()
    assert str(e["PCN_P_0A4"].dtype) == "Float64"
    assert pd.isna(e.loc[("01", "001", "0001"), "PCN_P_0A4"])           # MI → NA
    assert pd.isna(e.loc[("01", "997", "9997"), "POBFEM"])              # NA → NA
    ee = mxcensus.load_cpv_estimaciones(estimador="ee")
    assert str(ee["POBTOT"].dtype) == "Float64" and (ee["POBTOT"] == 1.25).all()


def test_estimaciones_estimador_levels_and_filters(fake_mirror):
    a = mxcensus.load_cpv_estimaciones(estimador=None)
    assert list(a.index.names) == ["CVE_ENT", "CVE_MUN", "CVE_LOC", "ESTIMADOR"] and len(a) == 25
    lvl = a.index.get_level_values("ESTIMADOR")
    assert list(lvl[:5]) == list(ESTIMADORES) and lvl.dtype.ordered
    two = mxcensus.load_cpv_estimaciones(estimador=["ls", "valor"])
    assert list(two.index.get_level_values("ESTIMADOR")[:2]) == ["valor", "ls"]
    assert list(two.xs("ls", level="ESTIMADOR")["POBTOT"]) == [12] * 5
    sub = mxcensus.load_cpv_estimaciones(nivel=["estatal", "localidad"], state=[1])
    assert list(sub["NIVEL"]) == ["estatal", "localidad"]
    assert len(mxcensus.load_cpv_estimaciones(nivel="nacional")) == 1
    for kw in ({"estimador": "valor_x"}, {"estimador": []}, {"nivel": "pais"}):
        with pytest.raises(ValueError, match="must be one of"):
            mxcensus.load_cpv_estimaciones(**kw)


def test_cpv_exports():
    for name in ("load_cpv", "load_cpv_viviendas", "load_cpv_personas", "load_cpv_migrantes",
                 "load_cpv_survey", "load_cpv_estimaciones", "variables_cpv_labels",
                 "variables_cpv", "variables_cpv_core", "cpv_schema_map"):
        assert name in mxcensus.__all__ and callable(getattr(mxcensus, name))


# --- real data: EIC 2025 (skipped without the local mirror) --------------------------------

@pytest.fixture
def local_mirror(monkeypatch):
    """Redirect ``POOCH.fetch`` to ``data/parquet``, so the real-data tests read the local
    mirror (no network, no user cache) even though the files are registered (unit 1e)."""
    from mxcensus.data import _registry

    def _fetch(fname, **_):
        p = _MIRROR / fname
        if not p.exists():
            raise FileNotFoundError(p)
        return str(p)

    monkeypatch.setattr(_registry.POOCH, "fetch", _fetch)
    return _MIRROR


@functools.cache
def _estimates(estimador="valor") -> pd.DataFrame:
    return mxcensus.load_cpv_estimaciones(survey_path=_MIRROR / "cpv_estimaciones_2025.parquet",
                                          estimador=estimador)


def _read_mirror(table: str, state: int, columns: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(_MIRROR / cpv_filename(table, "2025", state), columns=columns)
    if "FACTOR" in df:
        df["FACTOR"] = pd.to_numeric(df["FACTOR"])
    return df


@_REAL_SKIP
def test_load_cpv_raw_real(local_mirror):
    ctx = _no_warnings()
    raw = mxcensus.load_cpv(table="personas", state=1)
    harm = mxcensus.load_cpv(table="personas", state=1, harmonize=True)
    ctx.__exit__(None, None, None)
    assert raw.shape == (177_984, 92) and all(str(t) == "str" for t in raw.dtypes)
    assert harm.drop(columns="FACTOR").equals(raw.drop(columns="FACTOR"))


@_REAL_SKIP
def test_survey_labelled_real(local_mirror):
    ctx = _no_warnings()
    v, p, m = mxcensus.load_cpv_survey(state=1)
    ctx.__exit__(None, None, None)
    assert (len(v), len(p), len(m)) == (48_538, 177_984, 5_060)
    for f in (v, p, m):
        assert f.index.is_unique
        assert all(str(f.index.get_level_values(i).dtype) == "str" for i in range(f.index.nlevels))
    pv = p.index.get_level_values("ID_VIV")
    assert pv.isin(v.index).all() and m.index.get_level_values("ID_VIV").isin(v.index).all()
    assert (p.index.get_level_values("ID_PERSONA").str[:12] == pv).all()
    # FACTOR is constant within a dwelling and equals the dwelling's
    assert (p["FACTOR"].to_numpy() == v["FACTOR"].reindex(pv).to_numpy()).all()
    st = _estimates().loc[("01", "000", "0000")]
    assert p["FACTOR"].sum() == st["POBTOT"] and v["FACTOR"].sum() == st["VIVPARHAB"]
    assert p["SEXO"].cat.categories.tolist() == ["Hombre", "Mujer"]
    assert p["TAMLOC"].cat.ordered and str(p["EDAD"].dtype) == "Int64"
    assert p["EDAD"].between(0, 130).all() and str(v["TOTCUART"].dtype) == "Int64"
    assert str(p["NUMPER"].dtype) == "str" and str(p["CVEGEO"].dtype) == "str"
    # the optional emigrant → person link: (ID_VIV, MPERLS) = (ID_VIV, NUMPER)
    ret = m[m["MCONRESACT"] == "Sí"].reset_index()
    people = p.reset_index()[["ID_VIV", "NUMPER"]]
    linked = ret.merge(people, left_on=["ID_VIV", "MPERLS"], right_on=["ID_VIV", "NUMPER"])
    assert len(ret) == len(linked) == 652


@_REAL_SKIP
def test_state_sequence_real(local_mirror):
    both = mxcensus.load_cpv_viviendas(state=[9, 1])
    one = pd.concat([mxcensus.load_cpv_viviendas(state=1), mxcensus.load_cpv_viviendas(state=9)])
    pd.testing.assert_frame_equal(both, one)
    assert both.index.is_monotonic_increasing


@_REAL_SKIP
@pytest.mark.parametrize("state", _LOCAL_STATES)
def test_eic2025_data_checks_by_state(state):
    """The PLAN.md §Verification checks of one state, read column-pruned from the mirror."""
    ent = f"{state:02d}"
    geo = ["CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "ID_VIV"]
    p = _read_mirror("personas", state, geo + ["ID_PERSONA", "FACTOR", "COBERTURA"])
    v = _read_mirror("viviendas", state, geo + ["FACTOR", "MCONMIG", "MNUMPERS"])
    m = _read_mirror("migrantes", state, ["CVE_ENT", "ID_VIV", "ID_MII", "FACTOR"])
    e = _estimates().xs(ent, level="CVE_ENT")
    # geography: only this state; CVEGEO = CVE_ENT + CVE_MUN
    for f in (p, v, m):
        assert (f["CVE_ENT"] == ent).all() and (f["ID_VIV"].str[:2] == ent).all()
    for f in (p, v):
        assert (f["CVEGEO"] == f["CVE_ENT"] + f["CVE_MUN"]).all()
    # keys: unique per level, nested, FACTOR constant within the dwelling
    assert v["ID_VIV"].is_unique and p["ID_PERSONA"].is_unique and m["ID_MII"].is_unique
    assert (p["ID_PERSONA"].str[:12] == p["ID_VIV"]).all()
    assert p["ID_VIV"].isin(v["ID_VIV"]).all() and m["ID_VIV"].isin(v["ID_VIV"]).all()
    assert v["ID_VIV"].isin(p["ID_VIV"]).all()
    vf = v.set_index("ID_VIV")["FACTOR"]
    assert (p["FACTOR"].to_numpy() == vf.reindex(p["ID_VIV"]).to_numpy()).all()
    assert (m["FACTOR"].to_numpy() == vf.reindex(m["ID_VIV"]).to_numpy()).all()
    # emigrants: one record per emigrant the dwelling declared
    declared = pd.to_numeric(v.set_index("ID_VIV")["MNUMPERS"]).dropna().astype(int)
    assert (v["MCONMIG"] == "1").sum() == len(declared)
    assert m.groupby("ID_VIV").size().reindex(declared.index, fill_value=0).equals(declared)
    # Σ FACTOR = the estimates' Valor: state, every municipality, each ≥50k locality,
    # and the state's remainder of smaller localities
    st, mun = e.loc[("000", "0000")], e[e["NIVEL"] == "municipal"]
    assert p["FACTOR"].sum() == st["POBTOT"] and v["FACTOR"].sum() == st["VIVPARHAB"]
    mun = mun.reset_index().set_index("CVE_MUN")
    for f, ind in ((p, "POBTOT"), (v, "VIVPARHAB")):
        got = f.groupby("CVE_MUN")["FACTOR"].sum()
        assert got.index.tolist() == mun.index.tolist()
        assert (got.to_numpy() == mun[ind].to_numpy()).all(), ind
    loc = e[e["NIVEL"] == "localidad"]
    big = p[p["LOC50K"] != "0000"].groupby(["CVE_MUN", "LOC50K"])["FACTOR"].sum()
    assert big.index.tolist() == loc.index.tolist()
    assert (big.to_numpy() == loc["POBTOT"].to_numpy()).all()
    resto = e[e["NIVEL"] == "resto_estatal"]["POBTOT"]
    assert len(resto) == 1 and p.loc[p["LOC50K"] == "0000", "FACTOR"].sum() == resto.iloc[0]
    # coverage: one COBERTURA per municipality, as the estimates mark the municipality's
    # name (``*`` censado = 1, unmarked muestreado = 2, ``**`` muestra insuficiente = 3)
    cov = p.groupby("CVE_MUN")["COBERTURA"].agg(["first", "nunique"])
    assert (cov["nunique"] == 1).all()
    mark = mun["NOM_MUN"].str.extract(r"(\**)$")[0].map({"*": "1", "": "2", "**": "3"})
    assert cov["first"].tolist() == mark.tolist()


@_REAL_SKIP
def test_eic2025_estimates_real():
    a = _estimates(None)
    assert len(a) == 2_776 * 5 and a.index.is_unique
    counts = a.xs("valor", level="ESTIMADOR")["NIVEL"].value_counts()
    assert counts.to_dict() == {"nacional": 1, "estatal": 32, "municipal": 2_478,
                                "resto_estatal": 32, "localidad": 233}
    ind = [c for c in a.columns if c not in ("NIVEL", "CVEGEO", "NOM_ENT", "NOM_MUN", "NOM_LOC")]
    x = {k: a.xs(k, level="ESTIMADOR")[ind].astype("Float64") for k in ESTIMADORES}
    v, ee, li, ls, cv = (x[k] for k in ESTIMADORES)
    assert all((x[k].isna() == v.isna()).all().all() for k in ESTIMADORES)  # NA/MI aligned
    both = v.notna()
    assert ((li <= v) & (v <= ls))[both].all().all()
    # cv = 100·ee/valor, up to the 2-decimal rounding of the three published figures
    d = 0.005
    ok = v > d
    lo = 100 * (ee - d).clip(lower=0) / (v + d) - d - 1e-9
    hi = 100 * (ee + d) / (v - d) + d + 1e-9
    assert ((cv >= lo) & (cv <= hi))[ok].all().all()
    assert (_estimates().loc[("00", "000", "0000"), ["POBTOT", "VIVPARHAB"]].tolist()
            == [130_393_389, 39_699_242])


# Published national figures (INEGI, Comunicado de prensa 54/26, 22 Sep 2026).
_PUBLISHED = {"personas": 130_393_389, "viviendas": 39_699_242,
              "emigrantes": 1_259_978, "retornados": 150_752}


@pytest.mark.skipif(not _ALL32, reason="needs all 32 states of EIC 2025 (the wsl mirror)")
def test_eic2025_national_real():
    tot = dict.fromkeys(("personas", "viviendas", "emigrantes", "retornados"), 0)
    mun_cov, n_loc = {}, 0
    for s in _LOCAL_STATES:
        p = _read_mirror("personas", s, ["CVEGEO", "LOC50K", "FACTOR", "COBERTURA"])
        tot["personas"] += p["FACTOR"].sum()
        tot["viviendas"] += _read_mirror("viviendas", s, ["FACTOR"])["FACTOR"].sum()
        m = _read_mirror("migrantes", s, ["FACTOR", "MPAIRES"])
        tot["emigrantes"] += m["FACTOR"].sum()
        tot["retornados"] += m.loc[m["MPAIRES"] == "3", "FACTOR"].sum()
        mun_cov.update(p.groupby("CVEGEO")["COBERTURA"].first().to_dict())
        n_loc += p.loc[p["LOC50K"] != "0000", ["CVEGEO", "LOC50K"]].drop_duplicates().shape[0]
    assert tot == _PUBLISHED
    assert len(mun_cov) == 2_478 and n_loc == 233
    # 750 censados, 1,721 muestreados, 7 con muestra insuficiente (the estimates' * / **)
    assert pd.Series(mun_cov).value_counts().to_dict() == {"2": 1_721, "1": 750, "3": 7}


# --- unit 2a: CPV 2020 into the family -----------------------------------------------------

def test_fd_2020_code_cells():
    """CPV 2020 writes code cells the EIC 2025 workbook does not: braces around a code row,
    a spaced ellipsis, several codes in one cell."""
    assert _fd._parse_code("{0001..9999}") == (1, 9999, 4)
    assert _fd._parse_code("{000001..999997}") == (1, 999997, 6)
    assert _fd._parse_code("{01001000000100001 ... 32058999999999954}")[1] == 32058999999999954
    assert _fd._parse_code("0…24") == (0, 24, 0) and _fd._parse_code("{Nulo}") is None
    assert _fd._split_codes("1101..2901,3101,\n3102") == [(1101, 2901, 0), "3101", "3102"]
    assert _fd._split_codes("{001..570,999,Nulo}") == [(1, 570, 3), "999"]


def test_match_catalog_abbreviated_stems():
    """The 2020 catalog stems abbreviate their «Según Clasificador de …» names."""
    cats = dict.fromkeys(["ACTIVIDAD", "CARRERA", "CAUSA_MIG", "CLASE_VIV", "ENT", "ENT_PAIS",
                          "ESCOACUM", "INALI", "MUN", "OCUPACION", "PARENTESCO", "RELIGION"], {})
    expected = {"Parentescos": "PARENTESCO", "Religiones": "RELIGION",
                "Lenguas Indígenas (INALI": "INALI", "Carreras": "CARRERA",
                "Municipios y demarcaciones territoriales": "MUN",
                "Entidades federativas y Países": "ENT_PAIS", "Escolaridad": "ESCOACUM",
                "Causas \nde migración": "CAUSA_MIG", "Actividades económicas": "ACTIVIDAD",
                "Ocupaciones": "OCUPACION"}
    for phrase, stem in expected.items():
        assert _fd.match_catalog(phrase, cats) == stem, phrase
    assert _fd.match_catalog("Lugares sagrados", cats) is None
    # and the EIC 2025 stems keep resolving (incl. INEGI's ESOLARIDAD typo)
    c25 = dict.fromkeys(["ENTIDAD", "ENTIDAD_PAIS", "ESOLARIDAD_ACUMULADA", "MUNICIPIO"], {})
    assert _fd.match_catalog("entidad federativa y país", c25) == "ENTIDAD_PAIS"
    assert _fd.match_catalog("escolaridad acumulada", c25) == "ESOLARIDAD_ACUMULADA"


def test_read_catalogs_cp1252_and_nom_columns(tmp_path):
    with zipfile.ZipFile(tmp_path / "c.zip", "w") as z:
        z.writestr("MUN.csv", "CVE_ENT,NOM_ENT,CVE_MUN,NOM_MUN\n001,Ags,011,San Francisco de los Romo\n"
                   "009,CDMX,014,Benito Juárez\n".encode("cp1252"))
        z.writestr("ENT.csv", "CVE_ENT,NOM_ENT\n01,Aguascalientes\n".encode("cp1252"))
    cats = _fd.read_catalogs(tmp_path / "c.zip")
    assert cats["MUN"] == {"001011": "San Francisco de los Romo", "009014": "Benito Juárez"}
    assert cats["ENT"] == {"01": "Aguascalientes"}


_FD_2020 = {"PERSONAS": [
    [None, None, "CENSO DE POBLACIÓN Y VIVIENDA 2020"],
    _HDR,
    [None, 1, "Parentesco", "PARENTESCO", "¿Qué es?", "Caracter",
     "{101..713,999,Nulo}\n(Según Clasificador\nde Parentescos)", 3],
    [None, None, None, None, "Clave de parentesco", None, "101..713"],
    [None, None, None, None, "No especificado", None, "999"],
    [None, 2, "Religión", "RELIGION", "¿Cuál es?", "Caracter",
     "{1101..2901,3101,\n9999}\n(Según Clasificador de Religiones)", 4],
    [None, None, None, None, "Clave de religión", None, "1101..2901,3101"],
    [None, None, None, None, "No especificado", None, "9999"],
    [None, 3, "Escolaridad acumulada", "ESCOACUM", "Escolaridad acumulada", "Numérico",
     "{0…24, 99}", 2],
    [None, None, None, None, "Descripción por tabla de referencia", None,
     "(Según Clasificador de Escolaridad)"],
    [None, None, None, None, "No especificado", None, "99"],
    [None, None, None, None, "Blanco por pase", None, "Nulo"],
    [None, 4, "Localidad", "LOC50K", "Clave", "Caracter", "{0000..9999}", 4],
    [None, None, None, None, "Localidad de 50 000 y más habitantes", None, "{0001..9999}"],
    [None, None, None, None, "Localidad menor de 50 000 habitantes", None, "0000"],
]}


def test_parse_fd_xlsx_2020_layout(tmp_path):
    _xlsx(tmp_path / "fd.xlsx", _FD_2020)
    with zipfile.ZipFile(tmp_path / "c.zip", "w") as z:
        z.writestr("PARENTESCO.csv", "CLAVE,DESCRIPCION\n101,Jefa(e)\n201,Esposa(o)\n")
        z.writestr("RELIGION.csv", "CLAVE,DESCRIPCION\n1101,Católica\n3101,Sin religión\n")
        z.writestr("ESCOACUM.csv", "CLAVE,DESCRIPCION\n0,0 grados\n24,24 grados\n")
    p = _fd.parse_fd(tmp_path / "fd.xlsx", _fd.read_catalogs(tmp_path / "c.zip"))["personas"]
    assert p["PARENTESCO"]["Catálogo"] == "PARENTESCO"       # note wrapped over two lines
    assert p["PARENTESCO"]["Categorías"] == {"101": "Jefa(e)", "201": "Esposa(o)"}
    rel = p["RELIGION"]                                       # a single code keeps its label
    assert rel["Categorías"] == {"1101": "Católica", "3101": "Sin religión"}
    assert rel["Especiales"] == {"9999": "No especificado"}
    esc = p["ESCOACUM"]                     # catalog named in a code row; range from the header
    assert esc["Tipo"] == "numeric" and esc["Rango"] == [0, 24] and esc["Catálogo"] == "ESCOACUM"
    assert esc["Especiales"] == {"99": "No especificado"}
    loc = p["LOC50K"]                                         # braces in the code row
    assert loc["Tipo"] == "string" and not loc["Categorías"] and "0001..9999" in loc["Nota"]


def test_parse_indicator_csv_specials_and_range_typo(tmp_path):
    path = tmp_path / "dicc.csv"
    path.write_text(
        "CENSO 2020,,,,,\nNúm.,Indicador,Descripción,Mnemónico,Rangos,Longitud\n"
        "1,Clave de entidad,Código,ENTIDAD,00…32,2\n"
        "2,Población 0 a 2 femenina,Mujeres,P_0A2_F ,\"0.,.999999999\",9\n"
        "3,Tamaño de localidad,Clases,TAMLOC,01..14,2\n", encoding="utf-8-sig")
    sp = {"*": "Dato reservado por confidencialidad", "NA": "otro"}
    d = _fd.parse_indicator_csv(path, sp)
    assert d["P_0A2_F"]["Tipo"] == "numeric" and d["P_0A2_F"]["Especiales"] == sp
    assert d["ENTIDAD"]["Tipo"] == d["TAMLOC"]["Tipo"] == "string"
    assert not d["ENTIDAD"]["Especiales"]
    footnoted = tmp_path / "f.csv"                            # a footnote's label wins
    footnoted.write_text(path.read_text(encoding="utf-8-sig") + "NA: No aplica.,,,,,\n",
                         encoding="utf-8")
    assert _fd.parse_indicator_csv(footnoted, sp)["P_0A2_F"]["Especiales"]["NA"] == "No aplica"
    assert _bcpv._AGG_SPECIALS["2020"] == {"*": "Dato reservado por confidencialidad",
                                           "N/D": "No disponible", "N/A": "No aplica"}


def test_build_plan_2020():
    assert "2020" in _bcpv._ENABLED
    e20 = get_edition("2020")
    full = _bcpv._plan([e20], list(TABLES), list(range(1, 33)))
    assert len(full) == 96 and sum(len(j[3]) for j in full) == 160    # 32 × (3 + iter + ageb)
    assert {j[1] for j in full} == {"microdatos", "iter", "ageb"}
    assert e20.ddi_id == 632 and e20.zip_filename("microdatos", 1) == "Censo2020_CA_ags_csv.zip"


def _gid(table: str, period: str) -> str:
    """The schema group holding ``table`` for ``period`` (gids shift as editions join)."""
    return next(g for g, m in _SM[table]["groups"].items() if period in m["periods"])


def test_schema_map_2020_groups():
    """Gids are chronological: an older edition's groups come first (2015 joined in unit 3a),
    the newest edition stays latest."""
    for table in ("viviendas", "personas", "migrantes"):
        groups = _SM[table]["groups"]
        g20, g25 = _gid(table, "2020"), _gid(table, "2025")
        assert groups[g20]["periods"] == ["2020"] and groups[g20]["files"] == 32
        assert _SM[table]["latest"] == g25 and groups[g25]["periods"] == ["2025"]
        assert list(groups).index(g20) == list(groups).index(g25) - 1
    for table, n in (("iter", 286), ("ageb", 230)):
        g = _SM[table]["groups"][_gid(table, "2020")]
        assert g["periods"] == ["2020"] and g["n_columns"] == n and g["files"] == 32


def test_core_scope():
    core = variables_cpv_core()
    assert core["TAMLOC"]["Tablas"] == ["viviendas", "personas", "migrantes"]
    assert "TAMLOC" in _core_for("personas") and "TAMLOC" not in _core_for("iter")
    assert "ID_VIV" in _core_for("iter")                       # unscoped: every table
    lab = mxcensus.variables_cpv_labels("iter", _gid("iter", "2020"))
    assert lab["TAMLOC"]["Tipo"] == "string" and lab["TAMLOC"]["Rangos"] == "01..14"
    assert "TAMLOC" not in _cpv._latest_schema("iter").columns
    assert "TAMLOC" in _cpv._latest_schema("personas").columns


@pytest.mark.parametrize("table,col,bad", [
    ("personas", "SEXO", "2"), ("personas", "EDAD", "131"), ("personas", "PARENTESCO", "102"),
    ("personas", "ESCOACUM", "25"), ("personas", "OCUPACION_C", "12"),
    ("personas", "MUN_ASI", "1"), ("personas", "ENT", "33"), ("personas", "MUN", "0a1"),
    ("viviendas", "CLAVIVP", "10"), ("migrantes", "MCAUSAEMIG_V", "0100"),
    ("iter", "POBTOT", "ZZ"), ("iter", "ENTIDAD", "x1"), ("ageb", "AGEB", "01Z1"),
    ("ageb", "MZA", "0a1"), ("ageb", "REL_H_M", "N/E"),
])
def test_group_schema_2020_rejects(table, col, bad):
    gid = _gid(table, "2020")
    f = _valid_frame(table, gid)
    f[col] = [bad] * len(f)
    with pytest.raises(pa.errors.SchemaErrors, match=col):
        _group_schema(table, gid).validate(f, lazy=True)


def test_group_schema_2020_sentinels():
    gi, ga = _gid("iter", "2020"), _gid("ageb", "2020")
    f = _valid_frame("iter", gi, rows=4)
    f["POBTOT"] = ["*", "N/D", "N/A", "        986"]        # INEGI left-pads some counts
    f["TAMLOC"] = ["*", "1", "10", "14"]
    f["LONGITUD"] = ["102°17'45.768\" W", None, None, None]
    _group_schema("iter", gi).validate(f, lazy=True)
    a = _valid_frame("ageb", ga, rows=2)
    a["AGEB"], a["MZA"] = ["0000", "045A"], ["000", "001"]
    _group_schema("ageb", ga).validate(a, lazy=True)


_REAL_2020 = (_MIRROR / "cpv_personas_2020_01.parquet").exists()
_REAL_2020_SKIP = pytest.mark.skipif(not _REAL_2020, reason="no local CPV 2020 mirror")


@_REAL_2020_SKIP
def test_load_cpv_2020_real(local_mirror):
    ctx = _no_warnings()
    raw = mxcensus.load_cpv(table="personas", period=2020, state=1)
    v, p, m = mxcensus.load_cpv_survey(2020, state=1)
    ctx.__exit__(None, None, None)
    assert raw.shape == (95_983, 91) and all(str(t) == "str" for t in raw.dtypes)
    assert (len(v), len(p), len(m)) == (24_349, 95_983, 1_563)
    for f in (v, p, m):
        assert f.index.is_unique
    pv = p.index.get_level_values("ID_VIV")
    assert pv.isin(v.index).all() and m.index.get_level_values("ID_VIV").isin(v.index).all()
    assert (p.index.get_level_values("ID_PERSONA").str[:12] == pv).all()
    assert (p["FACTOR"].to_numpy() == v["FACTOR"].reindex(pv).to_numpy()).all()
    # the legacy files' totals (tests/test_census_legacy.py); full equality is unit 2b
    assert p["FACTOR"].sum() == 1_421_198 and v["FACTOR"].sum() == 387_762
    assert p["SEXO"].cat.categories.tolist() == ["Hombre", "Mujer"]
    assert "Jefa(e)" in p["PARENTESCO"].cat.categories and str(p["EDAD"].dtype) == "Int64"
    assert p["TAMLOC"].cat.ordered and str(p["ESCOACUM"].dtype) == "Int64"
    assert str(p["ENT"].dtype) == "str" and set(p["ENT"]) == {"01"}
    assert str(p["OCUPACION_C"].dtype) == "str" and str(p["NUMPER"].dtype) == "str"


@_REAL_2020_SKIP
def test_load_cpv_2020_aggregates_real(local_mirror):
    ctx = _no_warnings()
    it = mxcensus.load_cpv(table="iter", state=1)           # latest edition with ITER: 2020
    lab = mxcensus.load_cpv(table="iter", state=1, labels=True)
    ag = mxcensus.load_cpv(table="ageb", state=1, labels=True)
    ctx.__exit__(None, None, None)
    assert it.shape == (2_058, 286) and ag.shape == (16_376, 230)
    st = lab[(lab["MUN"] == "000") & (lab["LOC"] == "0000")]
    assert st["POBTOT"].tolist() == [1_425_607]                # test_census_legacy.py
    assert str(lab["POBTOT"].dtype) == "Int64" and lab["P_0A2_F"].isna().any()   # '*' → NA
    assert (it["P_0A2_F"] == "*").sum() == lab["P_0A2_F"].isna().sum()
    assert lab["REL_H_M"].dtype.kind == "f" and str(lab["TAMLOC"].dtype) == "str"
    assert str(ag["AGEB"].dtype) == "str" and str(ag["POBTOT"].dtype) == "Int64"


# --- unit 2b: 2020 ↔ 2025 harmonization; equality with the legacy 2020 files --------------

_SURVEY = ("viviendas", "personas", "migrantes")     # the microdata tables (2015: no migrantes)

_HARM_STATES = [(p, s) for p in ("2015", "2020", "2025") for s in range(1, 33)
                if all((_MIRROR / cpv_filename(t, p, s)).exists()
                       for t in _SURVEY if get_edition(p).has(t))]


@pytest.mark.parametrize("period,state", _HARM_STATES)
def test_raw_vs_harmonized_totals_real(period, state):
    """Harmonizing renames and pads the core only: same rows and Σ FACTOR, raw ENT/MUN =
    harmonized CVE_ENT/CVE_MUN, CVEGEO = CVE_ENT + CVE_MUN, the keys and CLAVIVP zero-padded
    (a change in 2015 only), every other column verbatim."""
    for table in (t for t in _SURVEY if get_edition(period).has(t)):
        raw = pd.read_parquet(_MIRROR / cpv_filename(table, period, state))
        ctx = _no_warnings()
        harm = _cpv._harmonize(raw, table)
        ctx.__exit__(None, None, None)
        assert len(harm) == len(raw) and harm["FACTOR"].dtype.kind in "iu"
        assert harm["FACTOR"].sum() == pd.to_numeric(raw["FACTOR"]).sum()
        assert set(harm["CVE_ENT"]) == {f"{state:02d}"}
        assert (harm["CVEGEO"] == harm["CVE_ENT"] + harm["CVE_MUN"]).all()
        assert harm["ID_VIV"].str.fullmatch(r"\d{12}").all()
        assert (harm["ID_VIV"].str[:2] == harm["CVE_ENT"]).all()
        if "ID_PERSONA" in harm:
            assert (harm["ID_PERSONA"].str[:12] == harm["ID_VIV"]).all()
        padded = [c for c in _cpv._CODE_PAD if c in raw]
        for col in padded:                    # same numbers, now at least the canonical width
            a, b = raw[col].dropna(), harm[col].dropna()
            assert a.index.equals(b.index) and (a.astype(int) == b.astype(int)).all()
            assert b.str.len().min() >= _cpv._CODE_PAD[col]
            if period != "2015":
                assert harm[col].equals(raw[col])               # already canonical
        renamed = {"ENT": "CVE_ENT", "MUN": "CVE_MUN"} if period != "2025" else {}
        drop = ["CVEGEO", "FACTOR", *padded] if renamed else ["FACTOR", *padded]
        assert harm.drop(columns=drop).equals(
            raw.rename(columns=renamed).drop(columns=["FACTOR", *padded]))


@_REAL_2020_SKIP
def test_harmonized_editions_stack_real(local_mirror):
    """2020 and 2025 through the loaders with harmonize=True: same totals as raw, the core
    columns aligned, and the documented two-call stacking works."""
    ctx = _no_warnings()
    frames = {}
    for period in ("2020", "2025"):
        v, p, m = mxcensus.load_cpv_survey(period, state=1, harmonize=True)
        raw = {t: mxcensus.load_cpv(table=t, period=period, state=1) for t in _SURVEY}
        for t, f in zip(_SURVEY, (v, p, m)):
            assert len(f) == len(raw[t])
            assert f["FACTOR"].sum() == pd.to_numeric(raw[t]["FACTOR"]).sum()
            assert list(f.columns[:3]) == ["CVEGEO", "CVE_ENT", "CVE_MUN"]
        frames[period] = mxcensus.load_cpv_personas(period, state=1, harmonize=True, labels=False)
    it = mxcensus.load_cpv(table="iter", state=1, harmonize=True, labels=True)
    ag = mxcensus.load_cpv(table="ageb", state=1, harmonize=True, labels=True)
    ctx.__exit__(None, None, None)
    both = pd.concat(frames, names=["PERIOD"])
    assert both.index.names == ["PERIOD", "ID_VIV", "ID_PERSONA"] and both.index.is_unique
    assert both.groupby(level="PERIOD")["FACTOR"].sum().to_dict() == {"2020": 1_421_198,
                                                                      "2025": 1_534_416}
    core = ["CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "COBERTURA", "ESTRATO", "UPM", "FACTOR",
            "CLAVIVP", "SEXO", "EDAD", "TAMLOC"]
    assert both[core].notna().all().all()
    _cpv._latest_schema("personas").validate(both.reset_index(), lazy=True)
    # the aggregates: the MG's names, CVEGEO 9 (ITER) / 16 (AGEB) characters, unique per row
    assert list(it.columns[:7]) == ["CVEGEO", "CVE_ENT", "NOM_ENT", "CVE_MUN", "NOM_MUN",
                                    "CVE_LOC", "NOM_LOC"]
    assert it["CVEGEO"].str.len().eq(9).all() and it["CVEGEO"].is_unique
    assert ag["CVEGEO"].str.len().eq(16).all() and ag["CVEGEO"].is_unique
    assert it.loc[it["CVEGEO"] == "010000000", "POBTOT"].tolist() == [1_425_607]
    assert ag.loc[ag["CVEGEO"] == "0100000000000000", "POBTOT"].tolist() == [1_425_607]


# The legacy CPV 2020 files (scripts/build_data.py, frozen) were read with pandas' inferred
# dtypes, its default NA strings and ``na_values=["N/D"]``, so a faithful ``N/D`` (an
# undisclosed locality/block count) or ``N/A`` (REL_H_M/PROM_HNV with a zero denominator) is
# NaN there; ``*`` was kept as a string.
_LEGACY_NA = frozenset({"N/D", "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN",
                        "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None",
                        "n/a", "nan", "null"})
_LEGACY_NAME = {"viviendas": "viviendas", "personas": "personas", "iter": "iter",
                "ageb": "resargebub"}
_LEGACY_2020 = [(t, s) for s in range(1, 33) for t in _LEGACY_NAME
                if (_MIRROR / cpv_filename(t, "2020", s)).exists()
                and (_MIRROR / f"{_LEGACY_NAME[t]}_{s:02d}.parquet").exists()]


def _legacy_mismatches(legacy: pd.DataFrame, raw: pd.DataFrame) -> dict[str, int]:
    """Columns (→ cell count) where a legacy file and its faithful-raw ``cpv_`` rebuild
    disagree. Numeric legacy columns are compared with the raw strings parsed as numbers,
    the others as strings; raw cells the legacy reader took as NA (:data:`_LEGACY_NA`)
    count as NA."""
    raw = raw.mask(raw.isin(_LEGACY_NA))
    bad = {}
    for col in legacy.columns:
        a, b = legacy[col], raw[col]
        if a.dtype.kind in "iuf":
            b = pd.to_numeric(b)
        same = (a.to_numpy(dtype=object) == b.to_numpy(dtype=object)) | (a.isna() & b.isna()).to_numpy()
        if not same.all():
            bad[col] = int((~same).sum())
    return bad


def test_legacy_mismatches_helper():
    legacy = pd.DataFrame({"N": [1, 2], "F": [1.5, np.nan], "S": ["*", np.nan]})
    raw = pd.DataFrame({"N": ["01", "2"], "F": ["1.5", "N/A"], "S": ["*", "N/A"]}, dtype=str)
    assert _legacy_mismatches(legacy, raw) == {}
    raw.loc[1, "S"] = "N/D"                                   # the legacy na_values
    assert _legacy_mismatches(legacy, raw) == {}
    raw.loc[0, "S"], raw.loc[0, "N"] = "x", "3"
    assert _legacy_mismatches(legacy, raw) == {"N": 1, "S": 1}


@pytest.mark.parametrize("table,state", _LEGACY_2020)
def test_cpv_2020_equals_legacy(table, state):
    """``cpv_{viviendas,personas,iter,ageb}_2020_NN`` hold the legacy ``viviendas_NN`` /
    ``personas_NN`` / ``iter_NN`` / ``resargebub_NN`` values: same columns in the same order,
    same rows, every cell equal after casting (the Mac: state 01; ``wsl``: all 32)."""
    raw = pd.read_parquet(_MIRROR / cpv_filename(table, "2020", state))
    legacy = pd.read_parquet(_MIRROR / f"{_LEGACY_NAME[table]}_{state:02d}.parquet")
    assert list(raw.columns) == list(legacy.columns) and len(raw) == len(legacy)
    assert all(str(t) == "str" for t in raw.dtypes)
    assert _legacy_mismatches(legacy, raw) == {}


# --- unit 3a: EIC 2015 (legacy .xls dictionary, unpadded codes) -----------------------------

import struct  # noqa: E402

_OLE_FREE, _OLE_END, _OLE_FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD


def _ole(stream: bytes, name: str = "Workbook", cutoff: int = 4096) -> bytes:
    """A minimal OLE2 compound file (version 3, 512-byte sectors) holding one stream; a
    stream below ``cutoff`` goes into the mini stream, as Excel stores a small workbook."""
    ssz, mssz = 512, 64
    sectors: list[bytes] = []
    fat: list[int] = []

    def alloc(data: bytes) -> int:
        start, n = len(sectors), -(-len(data) // ssz)
        for k in range(n):
            sectors.append(data[k * ssz:(k + 1) * ssz].ljust(ssz, b"\0"))
            fat.append(start + k + 1 if k < n - 1 else _OLE_END)
        return start

    mini_start, mfat_start, n_mfat, root_size = _OLE_END, _OLE_END, 0, 0
    if len(stream) < cutoff:
        n = -(-len(stream) // mssz)
        mfat = struct.pack(f"<{n}I", *(k + 1 if k < n - 1 else _OLE_END for k in range(n)))
        mini_start, root_size = alloc(stream.ljust(n * mssz, b"\0")), n * mssz
        n_mfat = -(-len(mfat) // ssz)
        mfat_start = alloc(mfat.ljust(n_mfat * ssz, b"\xff"))
        stream_start = 0
    else:
        stream_start = alloc(stream)

    def entry(ename, etype, start, size, child=_OLE_FREE):
        raw = ename.encode("utf-16-le") + b"\0\0"
        return (raw.ljust(64, b"\0") + struct.pack("<HBB", len(raw), etype, 1)
                + struct.pack("<III", _OLE_FREE, _OLE_FREE, child) + b"\0" * 36
                + struct.pack("<IQ", start, size))

    dir_start = alloc(entry("Root Entry", 5, mini_start, root_size, child=1)
                      + entry(name, 2, stream_start, len(stream)) + b"\0" * 256)
    n_fat = 1
    while -(-(len(fat) + n_fat) // (ssz // 4)) > n_fat:
        n_fat += 1
    fat_start = len(sectors)
    fat += [_OLE_FATSECT] * n_fat
    fat += [_OLE_FREE] * (n_fat * ssz // 4 - len(fat))
    for k in range(n_fat):
        sectors.append(struct.pack(f"<{ssz // 4}I", *fat[k * ssz // 4:(k + 1) * ssz // 4]))
    difat = [fat_start + k for k in range(n_fat)] + [_OLE_FREE] * (109 - n_fat)
    header = (bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 16
              + struct.pack("<5H", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
              + struct.pack("<9I", 0, n_fat, dir_start, 0, cutoff, mfat_start, n_mfat,
                            _OLE_END, 0)
              + struct.pack("<109I", *difat))
    return header + b"".join(sectors)


def _biff(rid: int, body: bytes) -> bytes:
    return struct.pack("<HH", rid, len(body)) + body


def _biff_str(text: str, len_size: int = 2) -> bytes:
    wide = any(ord(c) > 255 for c in text)
    return (len(text).to_bytes(len_size, "little") + bytes([wide])
            + text.encode("utf-16-le" if wide else "latin-1"))


def _biff_sst(strings: list[str], limit: int) -> bytes:
    """SST + CONTINUE records of at most ``limit`` bytes; a string whose characters cross a
    record boundary resumes with an option byte for its next segment (compressed when the
    segment fits latin-1, so the encoding can switch mid-string). The first string carries
    two rich-text runs, which may themselves cross a boundary (no option byte there)."""
    records, buf = [], bytearray(struct.pack("<II", len(strings), len(strings)))

    def flush():
        records.append(bytes(buf))
        buf.clear()

    for k, text in enumerate(strings):
        wide = any(ord(c) > 255 for c in text)
        head = len(text).to_bytes(2, "little") + bytes([wide | (0x08 if k == 0 else 0)])
        head += struct.pack("<H", 2) if k == 0 else b""
        if len(buf) + len(head) + 2 > limit:
            flush()
        buf += head
        i = 0
        while i < len(text):
            room = (limit - len(buf)) // (2 if wide else 1)
            if room <= 0:
                flush()
                wide = any(ord(c) > 255 for c in text[i:i + limit - 1])
                buf.append(wide)
                continue
            part = text[i:i + room]
            buf += part.encode("utf-16-le" if wide else "latin-1")
            i += len(part)
        if k == 0:
            for byte in struct.pack("<4H", 0, 1, 1, 2):
                if len(buf) >= limit:
                    flush()
                buf.append(byte)
    flush()
    return _biff(0x00FC, records[0]) + b"".join(_biff(0x003C, r) for r in records[1:])


def _rk(n: int, div100: bool = False) -> int:
    return ((n & 0x3FFFFFFF) << 2) | 0x02 | div100


def _xls(sheets: dict, cutoff: int = 4096, sst_limit: int = 8224) -> bytes:
    """A BIFF8 ``.xls`` (the records ``_dict_fd.read_xls`` reads). A cell is ``None`` (no
    cell), a ``str`` (LABELSST), an ``int`` (RK; a run of ints on a row is one MULRK), a
    ``float`` (RK ×100 when it has at most two decimals, else NUMBER), ``("label", text)``
    (LABEL), ``("formula", value)`` (FORMULA with that cached result; a STRING record
    follows a text result) or ``("chart",)`` (an embedded chart substream whose cell must be
    ignored). A chart sheet is appended to the workbook (skipped by the reader)."""
    strings = sorted({c for rows in sheets.values() for r in rows for c in r
                      if isinstance(c, str)})
    index = {s: k for k, s in enumerate(strings)}
    bof = lambda dt: _biff(0x0809, struct.pack("<4H2I", 0x0600, dt, 0, 0, 0, 0))  # noqa: E731
    eof = _biff(0x000A, b"")
    bodies = []
    for rows in sheets.values():
        out = bof(0x0010)
        for r, row in enumerate(rows):
            c = 0
            while c < len(row):
                v = row[c]
                if isinstance(v, int):
                    end = c
                    while end < len(row) and isinstance(row[end], int):
                        end += 1
                    if end - c > 1:
                        cells = b"".join(struct.pack("<HI", 0, _rk(x)) for x in row[c:end])
                        out += _biff(0x00BD, struct.pack("<HH", r, c) + cells
                                     + struct.pack("<H", end - 1))
                        c = end
                        continue
                    out += _biff(0x027E, struct.pack("<3HI", r, c, 0, _rk(v)))
                elif isinstance(v, float) and round(v * 100) == v * 100:
                    out += _biff(0x027E, struct.pack("<3HI", r, c, 0, _rk(round(v * 100), True)))
                elif isinstance(v, float):
                    out += _biff(0x0203, struct.pack("<3Hd", r, c, 0, v))
                elif isinstance(v, str):
                    out += _biff(0x00FD, struct.pack("<3HI", r, c, 0, index[v]))
                elif v and v[0] == "label":
                    out += _biff(0x0204, struct.pack("<3H", r, c, 0) + _biff_str(v[1]))
                elif v and v[0] == "formula":
                    text = isinstance(v[1], str)
                    res = bytes([0, 0, 0, 0, 0, 0, 0xFF, 0xFF]) if text else struct.pack("<d", v[1])
                    out += _biff(0x0006, struct.pack("<3H", r, c, 0) + res + struct.pack("<HIH", 0, 0, 0))
                    out += _biff(0x0207, _biff_str(v[1])) if text else b""
                elif v and v[0] == "chart":
                    out += bof(0x0020) + _biff(0x00FD, struct.pack("<3HI", r, c, 0, 0)) + eof
                c += 1
        bodies.append(out + eof)
    bodies.append(bof(0x0020) + eof)                                     # a chart sheet
    kinds = [0] * len(sheets) + [2]
    sst = _biff_sst(strings, sst_limit)

    def globals_(offsets):
        return (bof(0x0005) + b"".join(
            _biff(0x0085, struct.pack("<IBB", off, 0, kind) + _biff_str(name, len_size=1))
            for name, kind, off in zip([*sheets, "Gráfico1"], kinds, offsets)) + sst + eof)

    pos = len(globals_([0] * len(kinds)))
    offsets = []
    for body in bodies:
        offsets.append(pos)
        pos += len(body)
    return _ole(globals_(offsets) + b"".join(bodies), cutoff=cutoff)


_LONG = "Descripción por catálogo ‘larga’ " * 3        # latin-1 and wider characters
_XLS_SHEETS = {
    "TR_Persona": [
        ["Cons.", "Mnemónico", None, "Rango Válido"],
        [1, 2, 3, 4.25, 1993.5, 0.1],                    # MULRK, RK ×100, NUMBER
        ["  ", ("label", "Inline ñ"), ("formula", "texto"), ("formula", 7.0), ("chart",)],
        [_LONG, "Ver catálogo", None, "{01..32}"],
    ],
    "Índice": [["Tabla", -5]],
}
_XLS_EXPECTED = {
    "TR_Persona": [
        {"A": "Cons.", "B": "Mnemónico", "D": "Rango Válido"},
        {"A": "1", "B": "2", "C": "3", "D": "4.25", "E": "1993.5", "F": "0.1"},
        {"B": "Inline ñ", "C": "texto", "D": "7"},          # blank text and the chart dropped
        {"A": _LONG.strip(), "B": "Ver catálogo", "D": "{01..32}"},
    ],
    "Índice": [{"A": "Tabla", "B": "-5"}],
}


@pytest.mark.parametrize("cutoff,sst_limit", [(4096, 8224), (4096, 23), (64, 23), (64, 31)])
def test_read_xls_cells_strings_and_containers(tmp_path, cutoff, sst_limit):
    """Mini-stream and regular-sector storage; SST strings split across CONTINUE records
    (option byte switching encodings, rich-text runs crossing a boundary)."""
    data = _xls(_XLS_SHEETS, cutoff=cutoff, sst_limit=sst_limit)
    assert _fd.read_xls(data) == _XLS_EXPECTED
    (tmp_path / "fd.xls").write_bytes(data)
    assert _fd.read_xls(tmp_path / "fd.xls") == _fd.read_workbook(tmp_path / "fd.xls") == _XLS_EXPECTED


def test_read_xls_large_stream_and_errors(tmp_path):
    big = {"S": [[i, f"r{i}", i + 0.5] for i in range(400)]}          # > the 4 KiB cutoff
    rows = _fd.read_xls(_xls(big))["S"]
    assert len(rows) == 400 and rows[-1] == {"A": "399", "B": "r399", "C": "399.5"}
    with pytest.raises(ValueError, match="not an OLE2"):
        _fd.read_xls(b"PK\x03\x04 not a workbook")
    with pytest.raises(LookupError, match="no 'Workbook' stream"):
        _fd.read_xls(_ole(b"x" * 100, name="Book"))
    _xlsx(tmp_path / "a.xlsx", {"H": [["x", 1]]})
    assert _fd.read_workbook(tmp_path / "a.xlsx") == {"H": [{"A": "x", "B": "1"}]}
    (tmp_path / "bad.xls").write_bytes(b"<!DOCTYPE html>")
    with pytest.raises(ValueError, match="neither an .xlsx"):
        _fd.read_workbook(tmp_path / "bad.xls")


def test_read_catalogs_xls_members(tmp_path):
    """EIC 2015 ships its catalogs as one-sheet .xls workbooks (``eic2015_catalogos.zip``)."""
    with zipfile.ZipFile(tmp_path / "cat.zip", "w") as z:
        z.writestr("TC_PARENTESCO_2015.xls", _xls({"TC_PARENTESCO_2015": [
            ["CLAVE", "DESCRIPCION"], ["101", "Jefa o jefe"], ["201", "Esposa o esposo"]]}))
        z.writestr("TC_MUNICIPIO_2015.xls", _xls({"TC_MUNICIPIO_2015": [
            ["CLAVE_ENT", "DESCRIPCION_ENT", "CLAVE_MUN", "DESCRIPCION_MUN"],
            ["001", "Aguascalientes", "002", "Asientos"]]}))
        z.writestr("TC_ESCOACUM_2015.xls", _xls({"TC_ESCOACUM_2015": [   # reference table
            ["NIVEL_ESCOLARIDAD", "GRADO_ESCOLARIDAD", "ESCOLARIDAD_ACUMULADA"],
            ["Primaria", 1, 1]]}))
        z.writestr("Indice y estructura de catalogos.xls", _xls({"x": [["Catálogo"]]}))
        z.writestr("OCUPACION.csv", "CLAVE,DESCRIPCION\n111,Funcionarios\n")
    cats = _fd.read_catalogs(tmp_path / "cat.zip")
    assert cats == {"TC_PARENTESCO_2015": {"101": "Jefa o jefe", "201": "Esposa o esposo"},
                    "TC_MUNICIPIO_2015": {"001002": "Asientos"},
                    "OCUPACION": {"111": "Funcionarios"}}


_HDR15 = [None, "Cons.", "Descripción", "Mnemónico", "Pregunta y categoría", "Rango Válido",
          "Tipo", "Longitud"]                            # 2015: the range before the type
_FD_2015 = {
    "TR_Persona": [
        [None, "ENCUESTA INTERCENSAL 2015"],
        [None, "TABLA: TR_PERSONA"],
        _HDR15,
        [None, None, "LLAVE ÚNICA"],                                       # section (col C)
        [None, 1, "Identificador", "ID_PERSONA", "Identificador", "{01001000000101 ... "
         "32058999999954}", "Numérico", 14],
        [None, 2, "1. Sexo", "SEXO", "Sexo", "{1,3}", "Numérico", 1],          # coded, «Numérico»
        [None, None, None, None, "Hombre", "1"],
        [None, None, None, None, "Mujer", "3"],
        [None, 3, "2. Edad", "EDAD", "¿Cuántos años?", "{0..110,999}", "Numérico", 3],
        [None, None, None, None, "Años cumplidos", "0..109"],
        [None, None, None, None, "110 y más años cumplidos", "110"],
        [None, None, None, None, "No especificado", "999"],
        [None, 4, "Tamaño", "TAMLOC", "Tamaño de localidad", "{1…3}", "Numérico", 1],
        [None, None, None, None, "Menos de 2 500", "1"],
        [None, None, None, None, "2 500 a 14 999", "2"],
        [None, None, None, None, "15 000 y más", "3"],
        [None, 5, "Parentesco", "PARENT_OTRO_C", "Otro parentesco", "Ver catálogo", "Caracter", 3],
        [None, None, None, None, "Descripción por catálogo", "TC_PARENTESCO_2015"],
        [None, None, None, None, "No especificado", "999"],
        [None, None, None, None, "Blanco", "Nulo"],
        [None, 6, "Municipio", "NOM_MUN_ASI", "Nombre", "{Alfanumérico}", "Caracter", 80],
        [None, None, None, None, "Nombre del municipio", "TC_MUNICIPIO_2015"],
        [None, None, None, None, "Blanco por pase", "Nulo"],
        [None, 7, "Ocupación", "OCUPACION_C", "¿Ocupación?", "Ver catálogo", "Caracter", 3],
        [None, None, None, None, "Descripción por catálogo", "TC_OCUPACION_2015"],
        [None, None, None, None, "No especificado", "999"],
        [None, 8, "Escolaridad", "ESCOACUM", "Escolaridad", "{0…25, 99}", "Numérico", 2],
        [None, None, None, None, "Descripción por tabla de referencia", "TC_ESCOACUM_2015"],
        [None, None, None, None, "No especificado", "99"],
        [None, None, None, None, "Blanco por pase", "b"],                 # INEGI's typo
        [None, 9, "Electricidad", "ELECTRICIDAD", "¿Luz?", "{5,7,9,Nulo}", "Numérico", 1],
        [None, None, None, None, "Sí", "5"],
        [None, None, None, None, "No", "7"],
        [None, None, None, None, "No especificado", "9"],
        [None, None, None, None, "Blanco por pase", "Nulo"],
        [None, None, None, None, None, None, None, 380],                  # subtotal
    ],
    "Modelo de datos": [["ENCUESTA INTERCENSAL 2015"], [None, "TR_PERSONA"]],
}


def _catalogs_2015():
    return {"TC_PARENTESCO_2015": {"101": "Jefa o jefe", "201": "Esposa o esposo"},
            "TC_OCUPACION_2015": {"111": "Funcionarios", "112": "Presidentes"}}


def test_parse_fd_2015_layout(tmp_path):
    (tmp_path / "fd.xls").write_bytes(_xls(_FD_2015))
    doc = _fd.parse_fd(tmp_path / "fd.xls", _catalogs_2015())
    assert list(doc) == ["tr_persona"]                    # «Modelo de datos» has no header
    p = doc["tr_persona"]
    assert p["SEXO"]["Tipo"] == "string" and p["SEXO"]["Categorías"] == {"1": "Hombre", "3": "Mujer"}
    assert p["TAMLOC"]["Categorías"] == {"1": "Menos de 2 500", "2": "2 500 a 14 999",
                                         "3": "15 000 y más"}
    assert p["ELECTRICIDAD"]["Categorías"] == {"5": "Sí", "7": "No"}
    assert p["ELECTRICIDAD"]["Especiales"] == {"9": "No especificado"}
    assert p["EDAD"]["Tipo"] == "numeric" and p["EDAD"]["Rango"] == [0, 110]
    assert p["EDAD"]["Especiales"] == {"999": "No especificado"}
    par = p["PARENT_OTRO_C"]                              # the TC_ row names the catalog
    assert par["Catálogo"] == "TC_PARENTESCO_2015"
    assert par["Categorías"] == {"101": "Jefa o jefe", "201": "Esposa o esposo"}
    assert par["Especiales"] == {"999": "No especificado"}
    nom = p["NOM_MUN_ASI"]                                # a name column: a note, no catalog
    assert nom["Tipo"] == "string" and not nom["Categorías"] and "Catálogo" not in nom
    assert nom["Nota"] == "Nombre del municipio: TC_MUNICIPIO_2015"
    esc = p["ESCOACUM"]                                   # 'b' (Blanco por pase) is no code
    assert esc["Tipo"] == "numeric" and esc["Rango"] == [0, 25]
    assert esc["Especiales"] == {"99": "No especificado"} and "TC_ESCOACUM_2015" in esc["Nota"]
    e, src = _fd.fd_entry("SEXO", {"1", "3"}, None, p["SEXO"], 64)
    assert src == "fd" and e["Tipo"] == "categorical"
    e, src = _fd.fd_entry("OCUPACION_C", None, None, p["OCUPACION_C"], 1)
    assert e["Tipo"] == "string" and e["Catálogo"] == "TC_OCUPACION_2015"
    bare = _fd.parse_fd(tmp_path / "fd.xls")["tr_persona"]       # catalogs not fetched
    assert "Catálogo" not in bare["OCUPACION_C"]
    assert "«TC_OCUPACION_2015» no disponible" in bare["OCUPACION_C"]["Nota"]


def test_enumerated_rule():
    """A «Numérico» variable is categorical when its rows label every header code singly."""
    row = lambda code, rows: {"code": code, "rows": rows}            # noqa: E731
    assert _fd._enumerated(row("{1,3}", [("1", "Hombre"), ("3", "Mujer")]))
    assert _fd._enumerated(row("{1…2, 9, Nulo}", [("1", "a"), ("2", "b"), ("9", "NE")]))
    assert not _fd._enumerated(row("{0..130, 999}", [("0", "Menos de un año")]))  # EIC 2025 EDAD
    assert not _fd._enumerated(row("{0..109}", [((0, 109, 0), "Años")]))          # a range row
    assert not _fd._enumerated(row("{1,3}", [("1", "Hombre"), ("3", "")]))         # unlabelled
    assert not _fd._enumerated(row("{1..999}", [("1", "a")]))                       # too wide
    assert not _fd._enumerated(row("Ver catálogo", [("999", "No especificado")]))


def test_fd_docs_2015_sheets_map_to_tables(tmp_path):
    d = tmp_path / "2015"
    d.mkdir()
    (d / "eic2015_fd.xls").write_bytes(_xls(_FD_2015))
    with zipfile.ZipFile(d / "eic2015_catalogos.zip", "w") as z:
        z.writestr("TC_PARENTESCO_2015.xls", _xls({"T": [["CLAVE", "DESCRIPCION"],
                                                         ["101", "Jefa o jefe"]]}))
    docs = _bcpv._fd_docs(tmp_path, "2015")
    assert list(docs) == ["personas"]
    assert docs["personas"]["PARENT_OTRO_C"]["Categorías"] == {"101": "Jefa o jefe"}
    doc, prov = _bcpv._doc_for(tmp_path, "personas", ["2015"])
    assert prov == "FD 2015/personas" and "SEXO" in doc


def test_build_plan_2015():
    assert "2015" in _bcpv._ENABLED
    e15 = get_edition("2015")
    full = _bcpv._plan([e15], list(TABLES), list(range(1, 33)))
    assert len(full) == 32 and sum(len(j[3]) for j in full) == 64     # viviendas + personas
    assert {j[1] for j in full} == {"microdatos"} and e15.zip_filename("microdatos", 1) == "eic2015_01_csv.zip"
    assert e15.ddi_id == 214 and not e15.has("migrantes")
    assert DICTIONARY_URLS["2015"] == {"fd": "doc/eic2015_fd.xls",
                                       "catalogos": "doc/eic2015_catalogos.zip"}
    assert dictionary_url("2015", "catalogos").endswith("intercensal/2015/doc/eic2015_catalogos.zip")


def test_schema_map_2015_groups():
    """2015 slots in before 2020 (gids are chronological); the migrant table has no 2015
    group."""
    for table, n in (("viviendas", 88), ("personas", 86)):
        g = _SM[table]["groups"]
        g15 = _gid(table, "2015")
        assert g[g15]["periods"] == ["2015"]
        assert g[g15]["n_columns"] == n and g[g15]["files"] == 32
        assert list(g).index(g15) + 1 == list(g).index(_gid(table, "2020"))
    assert all(m["periods"] != ["2015"] for m in _SM["migrantes"]["groups"].values())


@pytest.mark.parametrize("table,col,bad", [
    ("personas", "SEXO", "2"), ("personas", "EDAD", "131"), ("personas", "PARENT", "10"),
    ("personas", "PARENT_OTRO_C", "102"), ("personas", "OCUPACION_C", "12"),
    ("personas", "ACTIVIDADES_C", "111"), ("personas", "MUN_ASI", "1"), ("personas", "ENT", "33"),
    ("personas", "ESCOACUM", "26"), ("personas", "TAMLOC", "6"), ("personas", "IDENT_MADRE", "55"),
    ("personas", "NIVACAD", "15"), ("personas", "ID_PERSONA", "x1"),
    ("viviendas", "CLAVIVP", "10"), ("viviendas", "ELECTRICIDAD", "6"),
    ("viviendas", "NUM_DUE_VIV1", "55"), ("viviendas", "INGTRHOG", "abc"),
    ("viviendas", "COBERTURA", "4"), ("viviendas", "MUN", "0a1"),
])
def test_group_schema_2015_rejects(table, col, bad):
    gid = _gid(table, "2015")
    f = _valid_frame(table, gid)
    f[col] = [bad] * len(f)
    with pytest.raises(pa.errors.SchemaErrors, match=col):
        _group_schema(table, gid).validate(f, lazy=True)


def test_group_schema_2015_accepts_unpadded_codes_and_sentinels():
    v = _valid_frame("viviendas", _gid("viviendas", "2015"), rows=4)
    v["CLAVIVP"] = ["1", "01", "9", "99"]                 # 2015 spelling, canonical, sentinel
    v["ID_VIV"] = ["10010000001", "320010000001", "1", "2"]
    v["NUM_DUE_VIV1"] = ["1", "54", "99", None]
    v["INGTRHOG"] = ["0", "999998", "999999", None]
    _group_schema("viviendas", _gid("viviendas", "2015")).validate(v, lazy=True)
    p = _valid_frame("personas", _gid("personas", "2015"), rows=4)
    p["EDAD"], p["IDENT_MADRE"] = ["0", "110", "999", "45"], ["1", "96", "97", "99"]
    p["QDIALECT_INALI"], p["OCUPACION_C"] = ["0205", "9000", None, None], ["813", "999", None, None]
    _group_schema("personas", _gid("personas", "2015")).validate(p, lazy=True)


def test_harmonize_2015_pads_keys_and_clavivp():
    v = _valid_frame("viviendas", _gid("viviendas", "2015"), rows=3)
    v["ENT"], v["MUN"] = ["01", "01", "01"], ["001", "011", "011"]
    v["ID_VIV"] = ["10010000001", "10110000002", "10110000003"]
    v["CLAVIVP"] = ["1", "9", "99"]
    p = _valid_frame("personas", _gid("personas", "2015"), rows=3)
    p["ENT"], p["MUN"] = v["ENT"], v["MUN"]
    p["ID_VIV"] = v["ID_VIV"]
    p["ID_PERSONA"] = [i + "01" for i in v["ID_VIV"]]
    ctx = _no_warnings()
    hv, hp = _cpv._harmonize(v, "viviendas"), _cpv._harmonize(p, "personas")
    ctx.__exit__(None, None, None)
    assert list(hv["ID_VIV"]) == ["010010000001", "010110000002", "010110000003"]
    assert list(hp["ID_PERSONA"]) == ["01001000000101", "01011000000201", "01011000000301"]
    assert list(hv["CLAVIVP"]) == ["01", "09", "99"] and list(hv["CVEGEO"]) == ["01001", "01011", "01011"]
    assert (hv["ID_VIV"].str[:5] == hv["CVEGEO"]).all()
    assert list(hv.columns[:3]) == ["CVEGEO", "ID_VIV", "CVE_ENT"]
    for t, h in (("viviendas", hv), ("personas", hp)):
        _cpv._latest_schema(t).validate(h, lazy=True)
        assert _cpv._harmonize(h, t).equals(h)                           # idempotent


_REAL_2015 = (_MIRROR / "cpv_personas_2015_01.parquet").exists()
_REAL_2015_SKIP = pytest.mark.skipif(not _REAL_2015, reason="no local EIC 2015 mirror")

# INEGI, Encuesta Intercensal 2015, tabulados predefinidos (dated 24/10/2016;
# intercensal/2015/tabulados/14_vivienda.xls sheet 02 and 01_poblacion.xls sheet 02, row
# «Total», estimator «Valor»): inhabited private dwellings, their population, men, women.
_PUBLISHED_2015 = {
    1: (334_589, 1_312_544, 640_091, 672_453), 2: (967_863, 3_315_766, 1_650_341, 1_665_425),
    3: (209_834, 712_029, 359_137, 352_892), 4: (244_471, 899_931, 441_276, 458_655),
    5: (809_275, 2_954_915, 1_462_612, 1_492_303), 6: (205_243, 711_235, 350_791, 360_444),
    7: (1_239_007, 5_217_908, 2_536_721, 2_681_187),
    8: (1_033_658, 3_556_574, 1_752_275, 1_804_299),
    9: (2_601_323, 8_918_653, 4_231_650, 4_687_003),
    10: (455_989, 1_754_754, 860_382, 894_372),
    11: (1_443_035, 5_853_677, 2_826_369, 3_027_308),
    12: (895_157, 3_533_251, 1_699_059, 1_834_192),
    13: (757_252, 2_858_359, 1_369_025, 1_489_334),
    14: (2_059_987, 7_844_830, 3_835_069, 4_009_761),
    15: (4_168_206, 16_187_608, 7_834_068, 8_353_540),
    16: (1_191_884, 4_584_471, 2_209_747, 2_374_724),
    17: (523_984, 1_903_811, 914_906, 988_905), 18: (332_553, 1_181_050, 586_000, 595_050),
    19: (1_393_542, 5_119_504, 2_541_857, 2_577_647),
    20: (1_043_527, 3_967_889, 1_888_678, 2_079_211),
    21: (1_554_026, 6_168_883, 2_943_677, 3_225_206),
    22: (533_596, 2_038_372, 993_436, 1_044_936), 23: (441_200, 1_501_562, 751_538, 750_024),
    24: (710_233, 2_717_820, 1_317_525, 1_400_295),
    25: (806_237, 2_966_321, 1_464_085, 1_502_236),
    26: (814_820, 2_850_330, 1_410_419, 1_439_911),
    27: (646_448, 2_395_272, 1_171_592, 1_223_680),
    28: (987_184, 3_441_698, 1_692_186, 1_749_512), 29: (310_504, 1_272_847, 614_565, 658_282),
    30: (2_251_217, 8_112_505, 3_909_140, 4_203_365),
    31: (565_015, 2_097_175, 1_027_548, 1_069_627), 32: (418_850, 1_579_209, 770_368, 808_841),
}
_NATIONAL_2015 = (31_949_709, 119_530_753, 58_056_133, 61_474_620)
_STATES_2015 = [s for s in range(1, 33) if all(
    (_MIRROR / cpv_filename(t, "2015", s)).exists() for t in ("viviendas", "personas"))]


def test_published_2015_add_up():
    totals = tuple(sum(v[k] for v in _PUBLISHED_2015.values()) for k in range(4))
    assert totals == _NATIONAL_2015 and totals[1] == totals[2] + totals[3]


@pytest.mark.parametrize("state", _STATES_2015)
def test_eic2015_data_checks_by_state(state):
    """Σ FACTOR = INEGI's published totals exactly (dwellings, population, men, women); keys
    unique and nested (ID_PERSONA = ID_VIV + the 2-digit NUMPER); FACTOR constant within the
    dwelling; ENT = the file's state; NUMPERS = the dwelling's person records."""
    v = _read_mirror_2015("viviendas", state, ["ID_VIV", "ENT", "MUN", "FACTOR", "NUMPERS",
                                               "COBERTURA"])
    p = _read_mirror_2015("personas", state, ["ID_VIV", "ID_PERSONA", "ENT", "FACTOR", "SEXO",
                                              "NUMPER"])
    vf, pf = v["FACTOR"].astype(int), p["FACTOR"].astype(int)
    published = (int(vf.sum()), int(pf.sum()), int(pf[p["SEXO"] == "1"].sum()),
                 int(pf[p["SEXO"] == "3"].sum()))
    assert published == _PUBLISHED_2015[state]
    ent = f"{state:02d}"
    assert (v["ENT"] == ent).all() and (p["ENT"] == ent).all()
    assert v["ID_VIV"].is_unique and p["ID_PERSONA"].is_unique
    assert (p["ID_PERSONA"].str[:-2] == p["ID_VIV"]).all()
    assert (p["ID_PERSONA"].str[-2:].astype(int) == p["NUMPER"].astype(int)).all()
    assert (v["ID_VIV"].str.zfill(12).str[:5] == v["ENT"] + v["MUN"]).all()
    assert p["ID_VIV"].isin(v["ID_VIV"]).all() and v["ID_VIV"].isin(p["ID_VIV"]).all()
    assert (p["FACTOR"].to_numpy() == p["ID_VIV"].map(v.set_index("ID_VIV")["FACTOR"]).to_numpy()).all()
    counts = p.groupby("ID_VIV").size()
    assert (v.set_index("ID_VIV")["NUMPERS"].astype(int) == counts.reindex(v["ID_VIV"]).to_numpy()).all()
    assert (v.groupby("MUN")["COBERTURA"].nunique() == 1).all()


def _read_mirror_2015(table: str, state: int, columns: list[str]) -> pd.DataFrame:
    return pd.read_parquet(_MIRROR / cpv_filename(table, "2015", state), columns=columns)


@pytest.mark.skipif(len(_STATES_2015) < 32, reason="needs all 32 states of EIC 2015 (the wsl mirror)")
def test_eic2015_national_real():
    tot = [0, 0, 0, 0]
    for s in range(1, 33):
        v = _read_mirror_2015("viviendas", s, ["FACTOR"])
        p = _read_mirror_2015("personas", s, ["FACTOR", "SEXO"])
        f = p["FACTOR"].astype(int)
        for k, x in enumerate((v["FACTOR"].astype(int).sum(), f.sum(),
                               f[p["SEXO"] == "1"].sum(), f[p["SEXO"] == "3"].sum())):
            tot[k] += int(x)
    assert tuple(tot) == _NATIONAL_2015


@_REAL_2015_SKIP
def test_load_cpv_2015_real(local_mirror):
    ctx = _no_warnings()
    raw = mxcensus.load_cpv(table="personas", period=2015, state=1)
    v, p, m = mxcensus.load_cpv_survey(2015, state=1)
    hv, hp, hm = mxcensus.load_cpv_survey(2015, state=1, harmonize=True)
    ctx.__exit__(None, None, None)
    assert raw.shape == (177_853, 86) and all(str(t) == "str" for t in raw.dtypes)
    assert m is None and hm is None                                    # no migrant table
    assert (len(v), len(p)) == (43_613, 177_853) and v.index.is_unique and p.index.is_unique
    pv = p.index.get_level_values("ID_VIV")
    assert pv.isin(v.index).all() and set(pv.str.len()) == {11}       # raw: unpadded state 01
    assert (p["FACTOR"].to_numpy() == v["FACTOR"].reindex(pv).to_numpy()).all()
    assert (v["FACTOR"].sum(), p["FACTOR"].sum()) == _PUBLISHED_2015[1][:2]
    assert p["SEXO"].cat.categories.tolist() == ["Hombre", "Mujer"]
    assert "Casa única en el terreno" in v["CLAVIVP"].cat.categories   # '1' via the Alias
    assert v["CLAVIVP"].notna().all() and v["TAMLOC"].cat.ordered
    assert str(p["EDAD"].dtype) == "Int64" and p["EDAD"].max() <= 110
    assert "Esposa(o) o pareja" in p["PARENT"].cat.categories and str(p["ESCOACUM"].dtype) == "Int64"
    assert str(p["OCUPACION_C"].dtype) == "str" and str(p["NUMPER"].dtype) == "str"
    assert str(v["NUM_DUE_VIV1"].dtype) == "str" and str(p["NOM_MUN"].dtype) == "str"
    # harmonized: the 2025 names, keys padded to 12/14 digits, CLAVIVP to 2
    assert set(hv.index.str.len()) == {12} and (hv.index.str[:2] == "01").all()
    assert set(hp.index.get_level_values("ID_PERSONA").str.len()) == {14}
    assert list(hv.columns[:3]) == ["CVEGEO", "CVE_ENT", "NOM_ENT"]
    assert (hv["CLAVIVP"].astype(str) == v["CLAVIVP"].astype(str).to_numpy()).all()
    assert (hv["FACTOR"].sum(), hp["FACTOR"].sum()) == _PUBLISHED_2015[1][:2]
    both = pd.concat({"2015": mxcensus.load_cpv_personas(2015, state=1, harmonize=True, labels=False),
                      "2025": mxcensus.load_cpv_personas(2025, state=1, harmonize=True, labels=False)},
                     names=["PERIOD"])
    assert both.index.names == ["PERIOD", "ID_VIV", "ID_PERSONA"] and both.index.is_unique
    core = ["CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "COBERTURA", "ESTRATO", "UPM", "FACTOR",
            "SEXO", "EDAD", "TAMLOC"]
    assert both[core].notna().all().all()
    _cpv._latest_schema("personas").validate(both.reset_index(), lazy=True)


_FD_2015_REAL = Path(__file__).resolve().parent.parent / "data" / "dict" / "fd" / "2015"


@pytest.mark.skipif(not (_FD_2015_REAL / "eic2015_fd.xls").exists(),
                    reason="EIC 2015 FD not fetched (build_cpv.py --dictionary --periods 2015)")
def test_fd_2015_real():
    """INEGI's own workbook and catalogs (legacy .xls) parse into every 2015 column."""
    cats = _fd.read_catalogs(_FD_2015_REAL / "eic2015_catalogos.zip")
    assert {"TC_PARENTESCO_2015", "TC_OCUPACION_2015", "TC_MUNICIPIO_2015"} <= set(cats)
    assert len(cats["TC_MUNICIPIO_2015"]) == 2_490
    doc = _bcpv._fd_docs(_FD_2015_REAL.parent, "2015")
    for table in ("viviendas", "personas"):
        assert list(doc[table]) == _cols(table, _gid(table, "2015"))
    p = doc["personas"]
    assert p["EDAD"]["Rango"] == [0, 110] and p["EDAD"]["Especiales"] == {"999": "No especificado"}
    assert p["CONACT"]["Tipo"] == "string" and len(p["CONACT"]["Categorías"]) == 13
    assert p["PARENT_OTRO_C"]["Catálogo"] == "TC_PARENTESCO_2015"
    assert len(p["PARENT_OTRO_C"]["Categorías"]) == 47


# --- unit 3b: CPV 2010 (DBF microdata, untyped FD, state-scoped keys) ------------------------

import pyarrow as pa_  # noqa: E402

import _dbf  # noqa: E402


def _dbf_bytes(fields: list[tuple[str, str, int]], rows: list[list], lang: int = 0x03,
               encoding: str = "cp1252", deleted: tuple[int, ...] = (),
               n_records: int | None = None) -> bytes:
    """A dBASE III file: ``fields`` = ``(name, type, width)``; character values left-aligned
    and space-padded, numeric ones right-aligned; ``None`` = blank; ``deleted`` row numbers
    flagged ``*``; ``n_records`` overrides the header's record count."""
    record_len = 1 + sum(w for _, _, w in fields)
    header_len = 32 + 32 * len(fields) + 1
    head = struct.pack("<4BIHH", 0x03, 111, 3, 30, len(rows) if n_records is None else n_records,
                       header_len, record_len) + b"\0" * 17 + bytes([lang]) + b"\0\0"
    desc = b"".join(name.encode("ascii").ljust(11, b"\0") + ftype.encode("ascii") + b"\0" * 4
                    + bytes([width, 0]) + b"\0" * 14 for name, ftype, width in fields)
    body = b""
    for i, row in enumerate(rows):
        body += b"*" if i in deleted else b" "
        for (_, ftype, width), value in zip(fields, row):
            raw = ("" if value is None else str(value)).encode(encoding)
            body += raw.rjust(width) if ftype in "NF" else raw.ljust(width)
    return head + desc + b"\r" + body + b"\x1a"


_DBF_FIELDS = [("ENT", "C", 2), ("NOM_LOC", "C", 20), ("ID_VIV", "C", 8), ("FACTOR", "N", 8),
               ("VACIO", "C", 3)]
_DBF_ROWS = [["01", "Jesús María", "00068033", 17, None],
             ["01", "Asientos", "00068039", 3, "x"],
             ["01", "San José de Gracia", "00068042", 120, None]]


def test_read_dbf_faithful_strings(tmp_path):
    (tmp_path / "v.dbf").write_bytes(_dbf_bytes(_DBF_FIELDS, _DBF_ROWS, deleted=(1,)))
    for source in (tmp_path / "v.dbf", (tmp_path / "v.dbf").read_bytes()):   # mmap / bytes
        r = _dbf.read_dbf(source)
        assert r.encoding == "cp1252" and r.deleted == 1
        assert r.table.column_names == ["ENT", "NOM_LOC", "ID_VIV", "FACTOR", "VACIO"]
        assert all(t == pa_.string() for t in r.table.schema.types)
        assert r.table.to_pylist() == [
            {"ENT": "01", "NOM_LOC": "Jesús María", "ID_VIV": "00068033", "FACTOR": "17",
             "VACIO": None},
            {"ENT": "01", "NOM_LOC": "San José de Gracia", "ID_VIV": "00068042",
             "FACTOR": "120", "VACIO": None}]
    h = _dbf.read_header((tmp_path / "v.dbf").read_bytes())
    assert h.n_records == 3 and h.record_len == 42 and [f.offset for f in h.fields] == [1, 3, 23, 31, 39]


def test_dbf_encoding_sniff():
    rows = [["01", "Álvaro Obregón", "1", 1, None], ["01", "Peñón", "2", 1, None]]
    assert _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, rows)).encoding == "cp1252"
    cp850 = _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, rows, lang=0x00, encoding="cp850"))
    assert cp850.encoding == "cp850"                       # the bytes win over the driver byte
    assert cp850.table.column("NOM_LOC").to_pylist() == ["Álvaro Obregón", "Peñón"]
    ascii_ = _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, _DBF_ROWS[1:2]))
    assert ascii_.encoding == "ascii"
    tie = [["01", "¤", "1", 1, None]]                      # no Spanish letter either way
    assert _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, tie, lang=0x02, encoding="cp850")).encoding == "cp850"
    assert _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, rows), encoding="latin-1").encoding == "latin-1"


def test_dbf_errors():
    with pytest.raises(ValueError, match="truncated"):
        _dbf.read_dbf(_dbf_bytes(_DBF_FIELDS, _DBF_ROWS, n_records=9))
    with pytest.raises(ValueError, match="duplicate field names"):
        _dbf.read_dbf(_dbf_bytes([("A", "C", 1), ("A", "C", 1)], [["x", "y"]]))
    bad = bytearray(_dbf_bytes(_DBF_FIELDS, _DBF_ROWS))
    bad[10] += 1                                            # record length ≠ the field widths
    with pytest.raises(ValueError, match="field widths"):
        _dbf.read_header(bytes(bad))
    with pytest.raises(ValueError, match="32-byte header"):
        _dbf.read_header(b"\x03")


def test_read_catalogs_dbf_members(tmp_path):
    with zipfile.ZipFile(tmp_path / "cat.zip", "w") as z:
        z.writestr("TC_PARENTESCO_2010.DBF", _dbf_bytes(
            [("CLAVE", "C", 3), ("DESCRIP", "C", 20)], [["101", "Jefe(a)"], ["201", "Esposo(a)"]]))
        z.writestr("TC_MUNICIPIO_2010.dbf", _dbf_bytes(
            [("CVE_ENT", "C", 2), ("NOM_ENT", "C", 10), ("CVE_MUN", "C", 3), ("NOM_MUN", "C", 10)],
            [["01", "Ags", "002", "Asientos"]], lang=0x02, encoding="cp850"))
        z.writestr("TC_ESCOACUM_2010.DBF", _dbf_bytes(        # a reference table: skipped
            [("ESCOACUM", "C", 2), ("DESCRIP", "C", 20)], [["00", "Sin escolaridad"]]))
    assert _fd.read_catalogs(tmp_path / "cat.zip") == {
        "TC_PARENTESCO_2010": {"101": "Jefe(a)", "201": "Esposo(a)"},
        "TC_MUNICIPIO_2010": {"01002": "Asientos"}}


_HDR10 = [None, "Cons.", "Descripción", "Mnemónico", "Pregunta y categoría", "Rango Válido",
          "Longitud"]                                         # 2010: no Tipo column
_FD_2010 = {"PERSONAS": [
    [None, "CENSO DE POBLACIÓN Y VIVIENDA 2010"],
    [None, None, None, None, None, "PERSONAS_EE"],
    _HDR10,
    [None, 1, "Entidad Federativa", "ENT", None, "{01..32}", 2],             # a code space
    [None, 2, "Clase", "CLAVIVP", "Clase", "{1..7,9,b}", 1],
    [None, None, None, None, "Casa independiente", "1"],
    [None, None, None, None, "Refugio", "7"],
    [None, None, None, None, "No especificado", "9"],
    [None, None, None, None, "Blanco por pase", "b"],
    [None, 3, "Edad", "EDAD", "¿Años?", "{000..130,999}", 3],                # range + sentinel
    [None, 4, "Migrante", "MPERA", None, "{0..99}", 2],                      # unpadded range
    [None, 5, "Dormitorios", "CUADORM", "¿Cuántos?", "{01..25,99,b}", 2],
    [None, None, None, None, "Número de dormitorios", "01..25"],
    [None, None, None, None, "No especificado", "99"],
    [None, 6, "Parentesco", "OTROPARE_C", "¿Qué es?", "Ver catálogo", 3],
    [None, None, None, None, "Descripción por catálogo", "Tc_Parentesco_2010"],
    [None, None, None, None, "Blanco por pase", "b"],
    [None, 7, "Escolaridad", "ESCOACUM", "Años", "{00..24,99,b}", 2],
    [None, None, None, None, "Descripción por catálogo", "Tc_escoacum_2010"],  # not a catalog
    [None, 8, "Ingresos", "INGTRMEN", "¿Cuánto?", "{000000..999999,b}", 6],
    [None, None, None, None, "No recibe Ingresos", "000000"],
    [None, None, None, None, "Ingresos especificados", "{000001..999997}"],
    [None, None, None, None, "Más de 999,999 ingresos", "999998"],
    [None, None, None, None, "No especificado", "999999"],
]}


def test_parse_fd_2010_untyped(tmp_path):
    """CPV 2010's FD has no Tipo column: numbers are inferred (``_quantity``)."""
    (tmp_path / "fd.xls").write_bytes(_xls(_FD_2010))
    p = _fd.parse_fd(tmp_path / "fd.xls", {"TC_PARENTESCO_2010": {"101": "Jefe(a)"}})["personas"]
    assert p["ENT"]["Tipo"] == "string" and len(p["ENT"]["Categorías"]) == 32
    assert p["CLAVIVP"]["Categorías"] == {"1": "Casa independiente", "7": "Refugio"}
    assert p["CLAVIVP"]["Especiales"] == {"9": "No especificado"}      # 'b' is the blank cell
    assert p["EDAD"]["Tipo"] == "numeric" and p["EDAD"]["Rango"] == [0, 130]
    assert p["EDAD"]["Especiales"] == {"999": "999"}
    assert p["MPERA"]["Tipo"] == "numeric" and p["MPERA"]["Rango"] == [0, 99]
    assert p["CUADORM"]["Rango"] == [1, 25] and p["CUADORM"]["Especiales"] == {"99": "No especificado"}
    assert p["OTROPARE_C"]["Catálogo"] == "TC_PARENTESCO_2010"           # 'Tc_' case-insensitive
    assert p["ESCOACUM"]["Tipo"] == "numeric" and p["ESCOACUM"]["Rango"] == [0, 24]
    assert p["ESCOACUM"]["Especiales"] == {"99": "99"} and "no disponible" in p["ESCOACUM"]["Nota"]
    ing = p["INGTRMEN"]                                                  # the top-code is a value
    assert ing["Rango"] == [0, 999998] and ing["Especiales"] == {"999999": "No especificado"}
    assert all(set(m) >= {"Tipo", "Rango"} for m in p.values())
    assert not _fd._quantity({"code": "{001..570}", "rows": []})        # MUN: a code space


def test_build_plan_2010():
    assert "2010" in _bcpv._ENABLED
    e10 = get_edition("2010")
    micro = _bcpv._plan([e10], ["viviendas", "personas", "migrantes"], list(range(1, 33)))
    assert len(micro) == 32 and sum(len(j[3]) for j in micro) == 96
    assert e10.zip_filename("microdatos", 1) == "MC2010_01_dbf.zip" and e10.fmt == "dbf"
    assert e10.member_regex("personas", 1).match("Personas_01.dbf")


def test_schema_map_2010_groups():
    """2010 is the oldest edition built so far (g01). State 15's DBFs spell the field
    ``tam_loc`` in lower case, so its files form a second 2010 group (g02)."""
    for table, n in (("viviendas", 56), ("personas", 95), ("migrantes", 27)):
        g = _SM[table]["groups"]
        assert _gid(table, "2010") == "g01" and g["g01"]["periods"] == g["g02"]["periods"] == ["2010"]
        assert (g["g01"]["files"], g["g02"]["files"]) == (31, 1)
        assert g["g02"]["states"] == {"2010": [15]} and g["g01"]["n_columns"] == g["g02"]["n_columns"] == n
        assert [c.upper() for c in g["g02"]["columns"]] == g["g01"]["columns"]
        assert _SM[table]["latest"] == _gid(table, "2025")


def test_core_edition_scope():
    """``Periodos``: CPV 2010's CLAVIVP is another classification, so the core entry (and its
    Alias and padding) applies to 2015-2025 only."""
    clavivp = variables_cpv_core()["CLAVIVP"]
    assert clavivp["Periodos"] == ["2015", "2020", "2025"]
    assert not _cpv._in_scope(clavivp, "viviendas", ["2010"])
    assert _cpv._in_scope(clavivp, "viviendas", ["2015"]) and _cpv._in_scope(clavivp, "viviendas")
    g10 = _gid("viviendas", "2010")
    lab = mxcensus.variables_cpv_labels("viviendas", g10)
    assert lab["CLAVIVP"]["Categorías"]["1"] == "Casa independiente" and "Alias" not in lab["CLAVIVP"]
    assert "CLAVIVP" not in _cpv._latest_schema("viviendas", ("2010",)).columns
    assert "CLAVIVP" in _cpv._latest_schema("viviendas", ("2020",)).columns
    assert "SEXO" in _core_for("personas", ["2010"])


def _frame_2010(table: str, rows: int = 3) -> pd.DataFrame:
    f = _valid_frame(table, _gid(table, "2010"), rows)
    f["ENT"], f["MUN"] = "09", "002"
    f["ID_VIV"] = ["00068033", "00068033", "00068039"][:rows]
    if table == "personas":
        f["ID_PER"], f["NUMPER"] = ["000284687", "000284692", "000284695"][:rows], ["00001", "00002", "00001"][:rows]
    if table == "migrantes":
        f["ID_MIN"] = ["0007803", "0007785", "0010681"][:rows]
    f["CLAVIVP"] = "5"
    return f


def test_harmonize_2010_national_keys():
    ctx = _no_warnings()
    hp = _cpv._harmonize(_frame_2010("personas"), "personas", periods=("2010",))
    hm = _cpv._harmonize(_frame_2010("migrantes"), "migrantes", periods=("2010",))
    hv = _cpv._harmonize(_frame_2010("viviendas", 1), "viviendas", periods=("2010",))
    ctx.__exit__(None, None, None)
    assert list(hv["ID_VIV"]) == ["090000068033"] and list(hv["CVEGEO"]) == ["09002"]
    assert list(hp["ID_PERSONA"]) == ["09000006803300001", "09000006803300002",
                                      "09000006803900001"]
    assert hp.columns.get_loc("ID_PERSONA") == hp.columns.get_loc("ID_PER") + 1
    assert list(hp["ID_PER"]) == ["000284687", "000284692", "000284695"]     # kept verbatim
    assert list(hm["ID_MII"]) == ["09000006803302", "09000006803301", "09000006803901"]
    assert set(hv["CLAVIVP"]) == {"5"}                  # 2010's own code: not padded to 05
    for t, h in (("personas", hp), ("migrantes", hm), ("viviendas", hv)):
        assert _cpv._harmonize(h, t, periods=("2010",)).equals(h)          # idempotent
        _cpv._latest_schema(t, ("2010",)).validate(h, lazy=True)
    unknown = _cpv._harmonize(_frame_2010("viviendas", 1), "viviendas")    # edition unknown
    assert list(unknown["ID_VIV"]) == ["000000068033"]    # only padded: no national key


def test_state_scoped_keys_guard(fake_mirror):
    with pytest.raises(ValueError, match="unique within a state only"):
        mxcensus.load_cpv_personas(2010, state=[1, 2])
    with pytest.raises(ValueError, match="unique within a state only"):
        mxcensus.load_cpv_survey(2010, state=[1, 2], labels=False)
    assert fake_mirror == []


@pytest.mark.parametrize("table,col,bad", [
    ("personas", "SEXO", "2"), ("personas", "EDAD", "131"), ("personas", "PARENT", "10"),
    ("personas", "OTROPARE_C", "102"), ("personas", "OCUACTIV_C", "123"),
    ("personas", "LNACEDO_C", "033"), ("personas", "ESCOACUM", "25"),
    ("personas", "IDMADRE", "00"), ("personas", "NIVACAD", "15"), ("personas", "ID_PER", "x1"),
    ("viviendas", "CLAVIVP", "8"), ("viviendas", "TAM_LOC", "05"), ("viviendas", "ELECTRI", "2"),
    ("viviendas", "INGTRHOG", "abc"), ("viviendas", "CERTEZA", "2"), ("viviendas", "ID_VIV", "0006803a"),
    ("migrantes", "MPAIRES", "4"), ("migrantes", "MFECEMIA", "2011"), ("migrantes", "ID_MIN", "x"),
])
def test_group_schema_2010_rejects(table, col, bad):
    gid = _gid(table, "2010")
    f = _valid_frame(table, gid)
    f[col] = [bad] * len(f)
    with pytest.raises(pa.errors.SchemaErrors, match=col):
        _group_schema(table, gid).validate(f, lazy=True)


_REAL_2010 = (_MIRROR / "cpv_personas_2010_01.parquet").exists()
_REAL_2010_SKIP = pytest.mark.skipif(not _REAL_2010, reason="no local CPV 2010 mirror")

# INEGI, Censo de Población y Vivienda 2010, Tabulados del Cuestionario Ampliado (elaborated
# 11/05/2011), ccpv/2010/tabulados/Ampliado/14_03A_ESTATAL.xls, estimator «Parámetro»:
# viviendas particulares habitadas and their occupants per state. The tabulados leave out
# CLAVIVP 5-7 (locales no construidos para habitación, viviendas móviles, refugios).
_PUBLISHED_2010 = {
    1: (293_024, 1_178_260), 2: (869_565, 3_098_948), 3: (185_595, 631_738),
    4: (214_072, 816_867), 5: (736_427, 2_738_203), 6: (180_866, 646_855),
    7: (1_084_500, 4_785_677), 8: (951_205, 3_388_957), 9: (2_440_641, 8_770_578),
    10: (407_646, 1_624_630), 11: (1_287_875, 5_472_860), 12: (816_642, 3_378_137),
    13: (673_159, 2_672_904), 14: (1_819_793, 7_315_955), 15: (3_717_606, 15_104_013),
    16: (1_081_827, 4_342_947), 17: (475_166, 1_768_413), 18: (294_470, 1_075_664),
    19: (1_215_839, 4_640_811), 20: (936_359, 3_783_491), 21: (1_380_656, 5_773_760),
    22: (455_026, 1_825_159), 23: (367_569, 1_319_120), 24: (640_693, 2_573_321),
    25: (722_337, 2_758_050), 26: (735_695, 2_625_590), 27: (570_132, 2_231_743),
    28: (902_548, 3_252_937), 29: (276_772, 1_179_808), 30: (2_027_661, 7_622_807),
    31: (504_951, 1_951_699), 32: (377_174, 1_493_882),
}
_NATIONAL_2010 = (28_643_491, 111_843_784)
_EXCLUDED_2010 = ("5", "6", "7")
_STATES_2010 = [s for s in range(1, 33) if all(
    (_MIRROR / cpv_filename(t, "2010", s)).exists() for t in ("viviendas", "personas", "migrantes"))]


def test_published_2010_add_up():
    assert tuple(sum(v[k] for v in _PUBLISHED_2010.values()) for k in range(2)) == _NATIONAL_2010


def _read_2010(table: str, state: int, columns: list[str]) -> pd.DataFrame:
    return pd.read_parquet(_MIRROR / cpv_filename(table, "2010", state), columns=columns)


@pytest.mark.parametrize("state", _STATES_2010)
def test_cpv2010_data_checks_by_state(state):
    """Σ FACTOR outside CLAVIVP 5-7 = the published dwellings and occupants exactly; keys
    unique (state serials) and nested through NUMPER; FACTOR constant in the dwelling; the
    emigrants' dwellings declare them."""
    v = _read_2010("viviendas", state, ["ENT", "ID_VIV", "CLAVIVP", "FACTOR", "NUMPERS",
                                        "MCONMIG", "MNUMPERS"])
    p = _read_2010("personas", state, ["ENT", "ID_VIV", "ID_PER", "NUMPER", "CLAVIVP", "FACTOR"])
    m = _read_2010("migrantes", state, ["ENT", "ID_VIV", "ID_MIN", "FACTOR"])
    keep_v, keep_p = ~v["CLAVIVP"].isin(_EXCLUDED_2010), ~p["CLAVIVP"].isin(_EXCLUDED_2010)
    assert (int(v["FACTOR"][keep_v].astype(int).sum()),
            int(p["FACTOR"][keep_p].astype(int).sum())) == _PUBLISHED_2010[state]
    ent = f"{state:02d}"
    assert all((f["ENT"] == ent).all() for f in (v, p, m))
    assert v["ID_VIV"].is_unique and p["ID_PER"].is_unique and m["ID_MIN"].is_unique
    assert not p.duplicated(["ID_VIV", "NUMPER"]).any()
    assert p["ID_VIV"].isin(v["ID_VIV"]).all() and m["ID_VIV"].isin(v["ID_VIV"]).all()
    factor = v.set_index("ID_VIV")["FACTOR"]
    assert (p["FACTOR"].to_numpy() == p["ID_VIV"].map(factor).to_numpy()).all()
    assert (m["FACTOR"].to_numpy() == m["ID_VIV"].map(factor).to_numpy()).all()
    counts = p.groupby("ID_VIV").size()
    assert (v.set_index("ID_VIV")["NUMPERS"].astype(int) == counts.reindex(v["ID_VIV"]).to_numpy()).all()
    assert set(v["ID_VIV"][v["MCONMIG"] == "1"]) == set(m["ID_VIV"])


@pytest.mark.skipif(len(_STATES_2010) < 32, reason="needs all 32 states of CPV 2010 (the wsl mirror)")
def test_cpv2010_national_real():
    tot = [0, 0]
    for s in range(1, 33):
        for k, table in enumerate(("viviendas", "personas")):
            f = _read_2010(table, s, ["CLAVIVP", "FACTOR"])
            tot[k] += int(f["FACTOR"][~f["CLAVIVP"].isin(_EXCLUDED_2010)].astype(int).sum())
    assert tuple(tot) == _NATIONAL_2010


@_REAL_2010_SKIP
def test_load_cpv_2010_real(local_mirror):
    ctx = _no_warnings()
    raw = mxcensus.load_cpv(table="personas", period=2010, state=1)
    v, p, m = mxcensus.load_cpv_survey(2010, state=1)
    hv, hp, hm = mxcensus.load_cpv_survey(2010, state=1, harmonize=True)
    ctx.__exit__(None, None, None)
    assert raw.shape == (69_804, 95) and all(str(t) == "str" for t in raw.dtypes)
    assert (len(v), len(p), len(m)) == (16_572, 69_804, 1_268)
    assert list(p.index.names) == ["ID_VIV", "ID_PER"] and list(m.index.names) == ["ID_VIV", "ID_MIN"]
    assert p.index.is_unique and set(v.index.str.len()) == {8}
    assert list(hp.index.names) == ["ID_VIV", "ID_PERSONA"] and list(hm.index.names) == ["ID_VIV", "ID_MII"]
    assert set(hv.index.str.len()) == {12} and (hv.index.str[:2] == "01").all()
    assert (hp.index.get_level_values("ID_PERSONA").str[:12]
            == hp.index.get_level_values("ID_VIV")).all()
    assert hm.index.get_level_values("ID_VIV").isin(hv.index).all()
    assert v["FACTOR"].sum() == hv["FACTOR"].sum() == 293_237              # all classes
    assert p["SEXO"].cat.categories.tolist() == ["Hombre", "Mujer"]
    assert "Casa independiente" in v["CLAVIVP"].cat.categories             # 2010's own classes
    assert str(p["EDAD"].dtype) == "Int64" and p["EDAD"].max() <= 130
    assert str(p["IDMADRE"].dtype) == "str" and str(p["NUMPER"].dtype) == "str"
    assert list(v["TAM_LOC"].cat.categories) == ["Menos de 2 500 habitantes",
                                                "2 500 a 14 999 habitantes",
                                                "15 000 a 99 999 habitantes",
                                                "100 000 y más habitantes"]
    both = pd.concat({"2010": mxcensus.load_cpv_personas(2010, state=1, harmonize=True, labels=False),
                      "2020": mxcensus.load_cpv_personas(2020, state=1, harmonize=True, labels=False)},
                     names=["PERIOD"])
    assert both.index.is_unique and both.index.names == ["PERIOD", "ID_VIV", "ID_PERSONA"]
    assert both[["CVEGEO", "CVE_ENT", "CVE_MUN", "LOC50K", "ESTRATO", "UPM", "FACTOR", "SEXO",
                 "EDAD"]].notna().all().all()


_FD_2010_REAL = Path(__file__).resolve().parent.parent / "data" / "dict" / "fd" / "2010"


@pytest.mark.skipif(not (_FD_2010_REAL / "diccionario_cuestionario_ampliado.xls").exists(),
                    reason="CPV 2010 FD not fetched (build_cpv.py --dictionary --periods 2010)")
def test_fd_2010_real():
    cats = _fd.read_catalogs(_FD_2010_REAL / "catalogos_2010_dbf.zip")
    assert len(cats["TC_MUNICIPIO_2010"]) == 2_456 and cats["TC_PARENTESCO_2010"]["101"] == "Jefe(a)"
    doc = _bcpv._fd_docs(_FD_2010_REAL.parent, "2010")
    for table in ("viviendas", "personas", "migrantes"):    # the FD lists the design last
        assert set(doc[table]) == set(_cols(table, _gid(table, "2010")))
    p = doc["personas"]
    assert p["HORTRA"]["Tipo"] == "numeric" and p["HORTRA"]["Rango"] == [0, 168]
    assert p["OTROPARE_C"]["Catálogo"] == "TC_PARENTESCO_2010" and p["ESCOACUM"]["Rango"] == [0, 24]
