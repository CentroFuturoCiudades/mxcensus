"""Build the Archivo Histórico de Localidades mirror (maintainer-only).

Converts INEGI's *Archivo Histórico de Localidades* (AHL, https://www.inegi.org.mx/app/geo2/
ahl/) to the mirror: each state's four CSVs (``Habitantes``, ``Maestro``, ``Movimientos``,
``Res_hist``; ISO-8859-1) as faithful-raw parquet, ``ahl_{table}_{snapshot}_{NN}.parquet``
(every column a string, only empty cells null, INEGI's row order; ``snapshot`` = the
export's date, which must be listed in ``mxcensus.data._ahl_catalog.SNAPSHOTS``). The
national ZIP is the one ``scripts/build_loc_lineage.py`` reads (``data/dict/ahl/AHL.zip``,
fetched by a POST, ``--download``). Three cells of ``Res_hist`` hold UTF-8 quotation marks
inside the Latin-1 text: kept byte for byte (Latin-1 decodes every byte).

``--check`` compares :func:`mxcensus.load_ahl_poblacion` with every ITER 1990–2020 of the
mirror (``--mirror``), locality by locality, and writes ``docs/cpv/AHL_REPORT.md`` with the
coverage of the older censuses and INEGI's defects the loaders repair.

Usage::

    .venv/bin/python scripts/build_ahl.py                      # build the 128 files
    .venv/bin/python scripts/build_ahl.py --states 1 9         # some states
    .venv/bin/python scripts/build_ahl.py --update-registry    # + their hashes
    .venv/bin/python scripts/build_ahl.py --check              # → AHL_REPORT.md (no build)
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import warnings
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import _build_common
from build_loc_lineage import ahl_date, download

from mxcensus.data._ahl_catalog import SNAPSHOTS, TABLES, ahl_filename, ahl_member

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ZIP = _REPO_ROOT / "data" / "dict" / "ahl" / "AHL.zip"
_DEFAULT_OUT = _REPO_ROOT / "data" / "parquet"
_DEFAULT_REGISTRY = _REPO_ROOT / "src" / "mxcensus" / "data" / "registry.txt"
_DEFAULT_REPORT = _REPO_ROOT / "docs" / "cpv" / "AHL_REPORT.md"
_ENCODING = "latin-1"

# INEGI's national totals (Censos y Conteos de Población y Vivienda, series históricas;
# 1900–1970 rounded to tens as published there).
NATIONAL_TOTALS = {
    1900: 13_607_260, 1910: 15_160_370, 1921: 14_334_780, 1930: 16_552_720,
    1940: 19_653_550, 1950: 25_791_020, 1960: 34_923_130, 1970: 48_225_240,
    1980: 66_846_833, 1990: 81_249_645, 1995: 91_158_290, 2000: 97_483_412,
    2005: 103_263_388, 2010: 112_336_538, 2020: 126_014_024,
}
_ITER_EDITIONS = (1990, 1995, 2000, 2005, 2010, 2020)


def snapshot_of(zip_path: Path) -> str:
    """The export's date as ``YYYYMMDD`` (its members' newest timestamp)."""
    return ahl_date(zip_path).strftime("%Y%m%d")


def read_member(raw: bytes, member: str) -> pa.Table:
    """One AHL CSV as an Arrow table of strings (empty cells null), checked against a
    plain ``csv`` parse (same rows, same header)."""
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding=_ENCODING, keep_default_na=False)
    rows = list(csv.reader(io.StringIO(raw.decode(_ENCODING), newline="")))
    if rows[0] != list(df.columns) or len(rows) - 1 != len(df):
        raise SystemExit(f"{member}: pandas and csv disagree ({len(df)} vs {len(rows) - 1} rows)")
    return pa.table({c: pa.array([v if v != "" else None for v in df[c].tolist()],
                                 type=pa.string()) for c in df.columns})


def build(zip_path: Path, out_dir: Path, states: list[int]) -> list[Path]:
    """Write the four tables of each state; return the files written."""
    snapshot = snapshot_of(zip_path)
    if snapshot not in SNAPSHOTS:
        raise SystemExit(f"{zip_path}: export {snapshot} is not in _ahl_catalog.SNAPSHOTS "
                         f"{SNAPSHOTS}; add it there first")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(zip_path) as outer:
        for state in states:
            with zipfile.ZipFile(io.BytesIO(outer.read(f"AHL{state:02d}.zip"))) as inner:
                for table in TABLES:
                    member = ahl_member(table, state)
                    arrow = read_member(inner.read(member), member)
                    path = out_dir / ahl_filename(table, state, snapshot)
                    pq.write_table(arrow, path, compression="zstd")
                    written.append(path)
                    print(f"  {member} → {path.name}: {arrow.num_rows:,} rows, "
                          f"{path.stat().st_size // 1024:,} KB", flush=True)
    return written


# --------------------------------------------------------------------------- check

def _md(df: pd.DataFrame) -> str:
    cells = [[f"{v:,}" if isinstance(v, int) else str(v) for v in row]
             for row in df.itertuples(index=False)]
    head = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in cells])


def check(mirror: Path, snapshot: str | None = None) -> dict:
    """The AHL against every ITER 1990–2020 and the national totals (module doc)."""
    import mxcensus
    from mxcensus import ahl
    from mxcensus.data import _registry

    _registry.POOCH.fetch = lambda name, **kw: str(mirror / name)
    states = list(range(1, 33))
    raw = mxcensus.load_ahl("habitantes", state=states, snapshot=snapshot)
    with warnings.catch_warnings():
        warnings.simplefilter("error")                  # no row with population is dropped
        pop = mxcensus.load_ahl_poblacion(state=states, snapshot=snapshot, copies=True)
    flat = pop.reset_index()
    flat["CVEGEO"] = flat["CVE_ENT"] + flat["CVE_MUN"] + flat["CVE_LOC"]
    kept = flat[~flat["COPIA"]]

    # defects INEGI's file has and the loader repairs
    years = raw["EVE_CENSAL"]
    fuente = years.map(lambda y: ahl.CENSUSES.get(int(y), ("?",))[0]
                       if y in {str(k) for k in ahl.CENSUSES} else "?")
    defects = {
        "rows": len(raw), "records": raw["CVE_GEOEST"].nunique(),
        "year_1920": int((years == "1920").sum()),
        "stray_years": years[~years.isin([str(y) for y in ahl.CENSUSES] + ["1920"])]
                       .value_counts().to_dict(),
        "duplicate_pairs": int(raw.duplicated(["CVE_GEOEST", "EVE_CENSAL"]).sum()),
        "fuente_contradicts": int(((fuente != raw["FUENTE"]) & (fuente != "?")
                                   & (fuente != "Censo de edificios")).sum()),
        "copies": flat.loc[flat["COPIA"]].groupby("EVE_CENSAL").agg(
            rows=("POBTOT", "size"), persons=("POBTOT", "sum")),
        "no_name": int(kept["NOM_LOC"].isna().sum()),
    }

    # coverage by census
    by_year = kept.groupby("EVE_CENSAL").agg(
        localities=("POBTOT", "size"), inhabited=("POBTOT", lambda s: int((s > 0).sum())),
        reserved=("POBTOT", lambda s: int(s.isna().sum())), persons=("POBTOT", "sum"))
    by_year["national"] = by_year.index.map(NATIONAL_TOTALS)
    by_year["share"] = (by_year["persons"] / by_year["national"]).round(4)

    # the ITERs, locality by locality
    lin = mxcensus.cpv_loc_lineage()
    moved = set(lin.loc[lin["KIND"] == "code", "FROM"])
    rows, diffs, missing = [], [], []
    for period in _ITER_EDITIONS:
        it = mxcensus.load_cpv_iter(period, state=states, nivel="localidad", impute=False)
        it = it.reset_index()
        it["CVEGEO"] = it["CVE_ENT"] + it["CVE_MUN"] + it["CVE_LOC"]
        a = kept[kept["EVE_CENSAL"] == period]
        m = it.merge(a, on="CVEGEO", how="outer", suffixes=("_iter", "_ahl"), indicator=True)
        both = m[m["_merge"] == "both"]
        eq = both["POBTOT_iter"].fillna(-1) == both["POBTOT_ahl"].fillna(-1)
        known = both["POBTOT_iter"].notna() & both["POBTOT_ahl"].notna()
        sex = both[eq & both["POBMAS_iter"].notna()]
        sex_eq = (sex["POBMAS_iter"] == sex["POBMAS_ahl"].fillna(-1)) & (
            sex["POBFEM_iter"] == sex["POBFEM_ahl"].fillna(-1))
        only_iter = m[m["_merge"] == "left_only"]
        only_ahl = m[m["_merge"] == "right_only"]
        rows.append({
            "census": period, "ITER localities": len(it), "in the AHL": len(both),
            "equal POBTOT": int(eq.sum()), "different": int((~eq & known).sum()),
            "reserved in the ITER only": int((both["POBTOT_iter"].isna()
                                              & both["POBTOT_ahl"].notna()).sum()),
            "reserved in the AHL only": int((both["POBTOT_iter"].notna()
                                             & both["POBTOT_ahl"].isna()).sum()),
            "sexes equal": f"{int(sex_eq.sum()):,} / {len(sex):,}",
            "ITER only": len(only_iter),
            "of them moved": int(only_iter["CVEGEO"].isin(moved).sum()),
            "AHL only, inhabited": int((only_ahl["POBTOT_ahl"] > 0).sum()),
            "ITER persons": int(it["POBTOT"].sum()),
            "AHL persons": int(a["POBTOT"].sum()),
            "AHL with copies": int(flat.loc[flat["EVE_CENSAL"] == period, "POBTOT"].sum()),
        })
        gaps = (only_iter.assign(MUN=only_iter["CVEGEO"].str[:5])
                .groupby("MUN").agg(localities=("CVEGEO", "size"),
                                    persons=("POBTOT_iter", "sum"))
                .sort_values("persons", ascending=False).head(5).reset_index())
        missing.append(gaps.assign(census=period, persons=gaps["persons"].astype(int)))
        d = both.loc[~eq & known, ["CVEGEO", "NOM_LOC_iter", "POBTOT_iter", "POBTOT_ahl"]]
        diffs.append(d.assign(census=period))
    return {"defects": defects, "by_year": by_year, "iter": pd.DataFrame(rows),
            "diffs": pd.concat(diffs, ignore_index=True),
            "missing": pd.concat(missing, ignore_index=True)}


def _localities(mirror: Path, snapshot: str | None) -> dict:
    import mxcensus
    loc = mxcensus.load_ahl_localidades(state=list(range(1, 33)), snapshot=snapshot)
    raw = mxcensus.load_ahl("maestro", state=list(range(1, 33)), snapshot=snapshot)
    stated = raw["LATITUD"].notna() & raw["LONGITUD"].notna()
    both = loc["LATITUD"].notna() & loc["LONGITUD"].notna()
    return {"records": len(loc), "coords": int(both.sum()),
            "stated": int(stated.sum()),
            "rejected": int(stated.sum() - both.sum()),
            "ambito": loc["AMBITO"].value_counts(dropna=False).to_dict(),
            "carta": int(loc["CARTA_TOPO"].notna().sum()),
            "carta_stated": int(raw["CARTA_TOPO"].notna().sum())}


def report(result: dict, locs: dict, snapshot: str, path: Path) -> None:
    from mxcensus import ahl
    d = result["defects"]
    by = result["by_year"].reset_index()
    by = by.assign(**{c: by[c].astype(int) for c in ("EVE_CENSAL", "localities", "inhabited",
                                                     "reserved", "persons")},
                   national=by["national"].map(lambda v: "—" if pd.isna(v) else int(v)),
                   share=by["share"].map(lambda v: "—" if pd.isna(v) else f"{v * 100:.1f}%"))
    by["EVE_CENSAL"] = by["EVE_CENSAL"].astype(str)
    copies = d["copies"].reset_index().astype(int)
    copies["EVE_CENSAL"] = copies["EVE_CENSAL"].astype(str)
    diffs = result["diffs"].astype({"POBTOT_iter": "object", "POBTOT_ahl": "object"})
    diffs["census"] = diffs["census"].astype(str)
    lines = [
        "# Archivo Histórico de Localidades — check against the ITERs",
        "",
        f"Generated by `scripts/build_ahl.py --check` (snapshot {snapshot}). The AHL's",
        "population (`load_ahl_poblacion`, INEGI's copies dropped) against every ITER of the",
        "mirror, locality by locality on the 9-character code; INEGI's national totals for",
        "the coverage of the older censuses (series históricas; 1900–1970 rounded to tens).",
        "",
        "## By census",
        "",
        "`localities`: rows (the uninhabited ones too); `reserved`: population missing (`*`,",
        "`-`); `share`: the AHL's persons over the national total.",
        "",
        _md(by),
        "",
        "## Against the ITER",
        "",
        "`ITER only`: localities of the ITER without a row of that census in the AHL — `of them",
        "moved`: a code the lineage moves to another (the AHL files their history under the new",
        "code). `AHL only, inhabited`: rows with population on a code the ITER does not list.",
        "",
        _md(result["iter"].astype({"census": str})),
        "",
        "`reserved in the ITER only`: the ITER reserves the count (`*`, one or two dwellings)",
        "and the AHL has it — in 1995 the AHL adds the population of those localities;",
        "`reserved in the AHL only`: INEGI's AHL lost the counts of the 1990 localities whose",
        "name is quoted (`\"Y\", LA`) and has none for a few others.",
        "",
        "### The ITER's localities without a row in the AHL: the five municipalities with",
        "### the most persons",
        "",
        "In 1990 most are the localities of Escárcega (04009), created three months after the",
        "census and already in its ITER: their history has the 1990 census under the old",
        "code, but no population row under either code.",
        "",
        _md(result["missing"].astype({"census": str})[["census", "MUN", "localities",
                                                        "persons"]]),
        "",
        "### Localities whose population differs (both known)",
        "",
        _md(diffs[["census", "CVEGEO", "NOM_LOC_iter", "POBTOT_iter", "POBTOT_ahl"]]),
        "",
        "## INEGI's defects the loader repairs",
        "",
        f"- `Habitantes`: {d['rows']:,} rows, {d['records']:,} records.",
        f"- {d['year_1920']} row(s) on «1920» (the 1921 census, as its history says) moved to "
        "1921.",
        f"- Rows on no census year dropped: {d['stray_years']} (none with population).",
        f"- {d['duplicate_pairs']} second rows of one locality and year: the one with more "
        "information kept.",
        f"- {len(ahl._SHIFTED)} rows INEGI read one column off from the 1990–2000 ITERs (the "
        "total holds the altitude or `*`, the men the total, the women the men) shifted back: "
        "each equals its ITER (above).",
        f"- `FUENTE` contradicts the year in {d['fuente_contradicts']} rows: `FUENTE` is set by "
        "the year.",
        f"- {d['no_name']:,} rows without a census row in their history (no name then).",
        "- Rows copied to a new code (dropped unless `copies=True`):",
        "",
        _md(copies),
        "",
        "## `load_ahl_localidades`",
        "",
        f"- {locs['records']:,} records; coordinates stated in {locs['stated']:,}, of which "
        f"{locs['rejected']} malformed (minutes or seconds of 60 or more, latitude and "
        "longitude swapped, digits mistyped) or outside Mexico: missing; "
        f"{locs['coords']:,} kept.",
        f"- `AMBITO`: {locs['ambito']}.",
        f"- `CARTA_TOPO`: {locs['carta']:,} sheets of {locs['carta_stated']:,} stated.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ahl", type=Path, default=_DEFAULT_ZIP, metavar="ZIP")
    parser.add_argument("--download", action="store_true", help="refresh the AHL ZIP")
    parser.add_argument("--states", nargs="+", type=int, default=list(range(1, 33)),
                        metavar="N")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--update-registry", action="store_true",
                        help="upsert the built files' hashes into --registry")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY, metavar="FILE")
    parser.add_argument("--check", action="store_true",
                        help="check the mirror's AHL against its ITERs → --report (no build)")
    parser.add_argument("--mirror", type=Path, default=_DEFAULT_OUT, metavar="DIR")
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT, metavar="FILE")
    args = parser.parse_args(argv)
    if args.check:
        snapshot = SNAPSHOTS[-1]
        result = check(args.mirror, snapshot)
        print(result["by_year"].to_string())
        print(result["iter"].to_string())
        report(result, _localities(args.mirror, snapshot), snapshot, args.report)
        print(f"report → {args.report}")
        return 0
    if args.download or not args.ahl.exists():
        download(args.ahl)
    written = build(args.ahl, args.output, args.states)
    print(f"{len(written)} files → {args.output}")
    if args.update_registry:
        _build_common.update_registry(written, args.registry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
