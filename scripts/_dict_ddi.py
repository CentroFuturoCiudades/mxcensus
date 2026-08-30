"""Maintainer-only: INEGI's DDI metadata (Red Nacional de Metadatos) → variable dictionaries.

INEGI publishes structured DDI-Codebook 1.2.2 metadata for its household surveys in the
RNM (a NADA catalog): ``https://www.inegi.org.mx/rnm/index.php/catalog/<id>`` with the
codebook at ``…/catalog/ddi/<id>``. Each codebook lists every data file (``fileDscr``) and
every variable (``var``) with its label, question text, type, value range and the
``catgry`` value labels — including a ``missing="Y"`` flag on the non-response codes.

:func:`parse_ddi` returns ``{file_stem: {VARNAME: meta}}`` where ``file_stem`` is the data
file name without extension (``SDEMT123``, ``poblacion``) and ``meta`` has:

``Descripción`` (label), ``Pregunta`` (question literal), ``Tipo`` (``numeric``/``string``),
``Longitud`` (field width, from ``location``), ``Rango`` (``[min, max]`` from ``valrng``),
``Categorías`` (``{code: label}`` for the valid codes) and ``Especiales`` (``{code: label}``
for the codes flagged missing / invalid-range).

:data:`ENIGH_DDI` / :func:`enoe_ddi_ids` map an edition / quarter to the catalog ids.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

RNM_DDI_URL = "https://www.inegi.org.mx/rnm/index.php/catalog/ddi/{id}"
_NS = "{http://www.icpsr.umich.edu/DDI}"

# ENIGH edition year → RNM catalog id (NCV editions for 2008–2014, Nueva serie 2016+).
ENIGH_DDI: dict[str, int] = {
    "2008": 7, "2010": 30, "2012": 75, "2014": 165, "2016": 310, "2018": 511,
    "2020": 685, "2022": 901, "2024": 1116,
}

# ENOE: one catalog entry per (year, questionnaire) — the ampliado entry carries the T1
# files, the básico entry T2–T4 (2006–2008 alternate differently; the DDI's own file names
# encode the quarter, so the entry is only a container). Listed newest-first per year.
ENOE_DDI: dict[int, tuple[int, ...]] = {
    2005: (1105,), 2006: (1076, 1077), 2007: (1056, 1057), 2008: (1021, 1020),
    2009: (984, 985), 2010: (943, 944), 2011: (925, 926), 2012: (909, 910, 911),
    2013: (864, 863), 2014: (842, 843), 2015: (206, 209), 2016: (205, 792),
    2017: (752, 753), 2018: (448, 410), 2019: (497, 512), 2020: (591, 643),
    2021: (664, 689, 710), 2022: (763, 793), 2023: (866, 907), 2024: (983, 1016),
    2025: (1104, 1121),
}

_FILE_RE = re.compile(r"^(?P<table>VIV|HOG|SDEM|COE1|COE2)T(?P<q>\d)(?P<yy>\d\d)$", re.I)


def _tx(e) -> str:
    return " ".join((e.text or "").split()) if e is not None else ""


def parse_ddi(xml_path: Path) -> dict[str, dict[str, dict]]:
    """Parse one RNM DDI codebook → ``{file_stem: {VARNAME: meta}}`` (see module doc)."""
    root = ET.parse(str(xml_path)).getroot()
    files = {f.get("ID"): _tx(f.find(f".//{_NS}fileName")) for f in root.findall(f".//{_NS}fileDscr")}
    out: dict[str, dict[str, dict]] = {}
    for v in root.findall(f".//{_NS}var"):
        stem = files.get(v.get("files") or "", "").rsplit(".", 1)[0]
        if not stem:
            continue
        fmt = v.find(f"{_NS}varFormat")
        numeric = (fmt is not None and fmt.get("type") == "numeric") or v.get("intrvl") == "contin"
        loc = v.find(f"{_NS}location")
        cats, special = {}, {}
        for c in v.findall(f"{_NS}catgry"):
            code = _tx(c.find(f"{_NS}catValu"))
            if not code or code.lower() == "sysmiss":
                continue
            label = _tx(c.find(f"{_NS}labl")) or code
            (special if c.get("missing") == "Y" else cats)[code] = label
        rng = v.find(f"{_NS}valrng/{_NS}range")
        rango = [rng.get("min"), rng.get("max")] if rng is not None and rng.get("min") is not None and rng.get("max") is not None else []
        for item in v.findall(f"{_NS}invalrng/{_NS}item"):
            code = item.get("VALUE")
            if code and code not in cats:
                special.setdefault(code, "No especificado")
        out.setdefault(stem, {})[v.get("name")] = {
            "Descripción": _tx(v.find(f"{_NS}labl")),
            "Pregunta": _tx(v.find(f".//{_NS}qstnLit")),
            "Tipo": "numeric" if numeric else "string",
            "Longitud": (loc.get("width") or "") if loc is not None else "",
            "Rango": rango,
            "Categorías": cats,
            "Especiales": special,
        }
    return out


def enoe_file_period(stem: str) -> tuple[str, str] | None:
    """``SDEMT123`` → ``("sdem", "2023t1")``; ``None`` for a non-ENOE file name."""
    m = _FILE_RE.match(stem)
    if not m:
        return None
    return m.group("table").lower(), f"20{m.group('yy')}t{m.group('q')}"


def enoe_ddi_ids(period: str) -> tuple[int, ...]:
    """Catalog ids that may document ``period`` (``2023t1``): its year's entries, then the
    previous year's (a quarter not yet catalogued — e.g. 2026 — reuses last year's
    questionnaire metadata; the build accepts a dictionary only if the data's codes fit)."""
    year = int(period[:4])
    return ENOE_DDI.get(year, ()) + ENOE_DDI.get(year - 1, ())


def fetch_ddi(catalog_id: int, cache_dir: Path) -> Path:
    """Download (once) the DDI codebook for ``catalog_id`` into ``cache_dir``."""
    import urllib.request

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{catalog_id}.xml"
    if not path.exists() or path.stat().st_size < 1000:
        req = urllib.request.Request(RNM_DDI_URL.format(id=catalog_id),
                                     headers={"User-Agent": "mxcensus-build"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        if b"codeBook" not in data[:2000]:
            raise RuntimeError(f"RNM catalog {catalog_id}: response is not a DDI codebook")
        path.write_bytes(data)
    return path


# --------------------------------------------------------------------------------------
# Reconciling a documented variable with the data it must describe
# --------------------------------------------------------------------------------------

def _respell(codes: dict[str, str], observed: set[str]) -> dict[str, str] | None:
    """Re-key ``codes`` to the spelling the data uses (zero-padding differs between the
    DDI and the CSV: ``'01'`` vs ``'1'``). Returns the re-spelled map if every observed
    value then has an entry, else ``None``."""
    if observed <= set(codes):
        return dict(codes)
    stripped = {}
    for k, v in codes.items():
        key = k.lstrip("0") or "0" if k.isdigit() else k
        stripped.setdefault(key, v)
    if observed <= set(stripped):
        return stripped
    width = max((len(k) for k in codes), default=0)
    padded = {(k.zfill(width) if k.isdigit() else k): v for k, v in codes.items()}
    if observed <= set(padded):
        return padded
    both = {**padded, **stripped}  # editions of one group may mix both spellings
    if observed <= set(both):
        return {k: v for k, v in both.items() if k in observed or k in padded}
    return None


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def _fmt_num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


_MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
           "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _complete_months(cats: dict[str, str]) -> dict[str, str] | None:
    """A code→month-name map the DDI lists only partially (the months a table happened to
    cover) → the full 1–12 map in the DDI's padding; ``None`` if not a month variable."""
    if not cats or not all(v.strip().capitalize() in _MONTHS for v in cats.values()):
        return None
    width = max(len(k) for k in cats)
    return {str(i).zfill(width): m for i, m in enumerate(_MONTHS, 1)}


def _labels_are_numeric(cats: dict[str, str]) -> bool:
    """True when every label repeats its code (``'01': '1 Años cumplidos'``, ``'5': '5'``):
    an enumeration that documents a quantity, not categories."""
    if not cats:
        return False
    for code, label in cats.items():
        head = (label or "").strip().split(" ")[0].lstrip("0") or "0"
        if head != (code.lstrip("0") or "0"):
            return False
    return True


def dictionary_entry(col: str, observed: set[str] | None, core: dict | None,
                     doc: dict | None, threshold: int) -> tuple[dict, str]:
    """Build one variables-YAML entry for ``col`` from, in priority order, the hand-curated
    ``core`` entry, the DDI ``doc`` entry, and the data-derived ``observed`` value set.

    Returns ``(entry, source)`` with ``source`` ∈ ``core`` / ``ddi`` / ``ddi+data`` /
    ``data`` / ``none``. ``observed`` is ``None`` for a high-cardinality column (more than
    ``threshold`` distinct values — never enumerated as categories).

    DDI rules: a documented code→label map is accepted as ``Categorías`` when every
    observed value has a label after re-spelling (:func:`_respell`); observed codes the DDI
    lacks are appended with an identity label and flagged in ``Nota`` (``ddi+data``). A
    ``numeric`` variable — or a documented enumeration wider than ``threshold`` whose codes
    are all integers (the DDI lists every age) — becomes ``Tipo: numeric`` with ``Rango``
    from the DDI range (or the enumerated bounds) and the ``missing``-flagged codes as
    ``Especiales``.
    """
    if core is not None:
        return dict(core), "core"
    if doc is None:
        if observed:
            return {"Descripción": "", "Tipo": "", "Longitud": "",
                    "Categorías": {v: v for v in observed}}, "data"
        return {"Descripción": "", "Tipo": "", "Longitud": "", "Categorías": {}}, "none"
    cats, special = dict(doc.get("Categorías") or {}), dict(doc.get("Especiales") or {})
    entry = {"Descripción": doc.get("Descripción", ""), "Pregunta": doc.get("Pregunta", ""),
             "Tipo": doc.get("Tipo") or "string", "Longitud": doc.get("Longitud", ""),
             "Categorías": {}}
    numeric_enum = (cats and len(cats) > threshold
                    and all(k.lstrip("-").isdigit() for k in cats))
    if doc.get("Tipo") == "numeric" and not cats or numeric_enum:
        # No ``Rango`` from the DDI: its ``valrng`` is the edition's *observed* min/max,
        # not the questionnaire's bounds, and a group spans several editions. Bounds are
        # hand-set in the core dictionaries.
        entry["Tipo"] = "numeric"
        if special:
            entry["Especiales"] = special
        return entry, "ddi"
    if not cats and special:
        # Only sentinel codes are documented (a day-of-month, an hour count): a number
        # whose non-response codes become NA.
        entry["Tipo"] = "numeric"
        entry["Especiales"] = special
        return entry, "ddi"
    if observed is None:  # high-cardinality: keep the description, no categories
        if cats:
            entry["Nota"] = f"catálogo de {len(cats)} códigos (no enumerado)"
        return entry, "ddi"
    allowed = {**cats, **special}
    respelled = _respell(allowed, observed) if allowed else None
    if respelled is None and observed and (months := _complete_months(cats)):
        cats, allowed = months, {**months, **special}
        respelled = _respell(allowed, observed)
    if respelled is None and observed and "&" in observed - set(allowed):
        # INEGI's "no especificado" glyph (ENIGH): a sentinel, whichever variable carries it.
        special = {**special, "&": "No especificado"}
        allowed = {**cats, **special}
        respelled = _respell(allowed, observed)
    if respelled is None and observed and all(_is_number(v) for v in observed - set(special)
                                              - {k.lstrip("0") or "0" for k in special}):
        # An all-numeric observed set the DDI only partially enumerates (hours, years,
        # amounts, counts documented by a few labelled codes) is a number, not a category.
        covered = len(observed & set(allowed)) / len(observed)
        if covered < 0.5 or _labels_are_numeric(cats):
            nums = sorted(float(v) for v in observed
                          if v not in special and (v.lstrip("0") or "0") not in special)
            entry["Tipo"] = "numeric"
            if special:
                entry["Especiales"] = special
            entry["Nota"] = "numérica: el DDI sólo enumera códigos especiales"
            return entry, "ddi"
    if respelled is None and allowed:
        # partial: document what we can, append undocumented observed codes verbatim
        base = _respell(allowed, observed & set(allowed)) or dict(allowed)
        extra = sorted(observed - set(base))
        respelled = {**base, **{v: v for v in extra}}
        entry["Nota"] = f"códigos observados sin etiqueta en el DDI: {extra}"
        source = "ddi+data"
    elif respelled is None:
        respelled = {v: v for v in sorted(observed)}
        source = "data"
    else:
        source = "ddi"
    spec_keys = {k for k in respelled if k in special or k.lstrip("0") in {s.lstrip("0") for s in special}}
    entry["Categorías"] = {k: v for k, v in respelled.items() if k not in spec_keys}
    if spec_keys:
        entry["Especiales"] = {k: respelled[k] for k in respelled if k in spec_keys}
    if entry["Categorías"] or entry.get("Especiales"):
        entry["Tipo"] = "categorical"
    return entry, source


# --------------------------------------------------------------------------------------
# Writing the per-group variables YAML (shared by build_enoe.py / build_enigh.py)
# --------------------------------------------------------------------------------------

def observed_values(paths, columns, threshold: int) -> dict[str, set[str] | None]:
    """``{column: set of distinct stripped values}`` across ``paths`` (``None`` once a column
    exceeds ``threshold`` distinct values — high-cardinality, never enumerated)."""
    import pandas as pd
    import pyarrow.parquet as pq

    seen: dict[str, set[str] | None] = {c: set() for c in columns}
    alive = set(columns)
    for p in paths:
        present = [c for c in alive if c in pq.ParquetFile(p).schema_arrow.names]
        if not present:
            continue
        df = pd.read_parquet(p, columns=present)
        for c in present:
            vals = {str(v).strip() for v in df[c].dropna().unique()} - {""}
            seen[c].update(vals)
            if len(seen[c]) > threshold:
                alive.discard(c)
                seen[c] = None
    return seen


def group_entries(columns, observed: dict, core: dict, doc: dict | None,
                  threshold: int) -> tuple[dict, dict]:
    """Entries for one schema group: ``({col: entry}, {col: source})``.

    ``doc`` is the DDI dictionary chosen for the group (``{VARNAME: meta}``; names matched
    case-insensitively, the data's spelling is kept), or ``None`` when no codebook
    documents it.
    """
    docl = {k.lower(): v for k, v in (doc or {}).items()}
    entries, sources = {}, {}
    for col in columns:
        entry, src = dictionary_entry(col, observed.get(col), core.get(col),
                                      docl.get(col.lower()), threshold)
        entries[col], sources[col] = entry, src
    return entries, sources


def dump_yaml(doc: dict, path: Path) -> None:
    import yaml

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False,
                       width=100)
