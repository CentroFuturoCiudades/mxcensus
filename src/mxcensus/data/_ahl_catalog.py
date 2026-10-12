"""INEGI's Archivo Histórico de Localidades (AHL) — mirror catalog.

The AHL (https://www.inegi.org.mx/app/geo2/ahl/) is INEGI's history of every locality of
its geostatistical catalog: one ZIP per state of four ISO-8859-1 CSVs, filed under each
locality's **last** code (9 characters: entity + municipality + locality):

- ``Habitantes`` — its population (total, men, women) at every census and count 1900–2020;
- ``Maestro`` — one row per locality: coordinates, altitude, 1:50,000 sheet, urban/rural
  type, the names of its state and municipality;
- ``Movimientos`` — its history, one row per event (a census or count, a geostatistical
  update, a decree) with its name, municipality, political and administrative category
  then and what changed (free text);
- ``Res_hist`` — historical accounts of municipal seats and localities with indigenous
  names.

INEGI updates the archive continuously, so the mirror keeps **snapshots**, named by the
export's date (the members' timestamp): ``ahl_{table}_{snapshot}_{NN}.parquet``. The
bundled locality lineage (``cpv_loc_lineage.csv.gz``) is built from the latest one.
Built by ``scripts/build_ahl.py``; read by :mod:`mxcensus.ahl`.
"""
from __future__ import annotations

import re

# The national download: a POST with ``clave=00&tipo=N`` returns a ZIP of the 32 state ZIPs.
AHL_URL = "https://www.inegi.org.mx/app/geo2/ahl/descarga"

# Mirrored snapshots (the export's date, YYYYMMDD), oldest first.
SNAPSHOTS: tuple[str, ...] = ("20260918",)

# Mirror table name → the CSV member's stem (``AHL{NN}{stem}.csv``).
TABLES: dict[str, str] = {
    "habitantes": "Habitantes",
    "maestro": "Maestro",
    "movimientos": "Movimientos",
    "res_hist": "Res_hist",
}

FILE_RE = re.compile(r"ahl_(?P<table>habitantes|maestro|movimientos|res_hist)"
                     r"_(?P<snapshot>\d{8})_(?P<state>\d{2})\.parquet")


def latest_snapshot() -> str:
    """The newest mirrored snapshot."""
    return SNAPSHOTS[-1]


def ahl_filename(table: str, state: int, snapshot: str | None = None) -> str:
    """The mirror file of one AHL table of one state: ``ahl_{table}_{snapshot}_{NN}.parquet``."""
    if table not in TABLES:
        raise ValueError(f"unknown AHL table {table!r}; known: {list(TABLES)}")
    snapshot = latest_snapshot() if snapshot is None else str(snapshot)
    if snapshot not in SNAPSHOTS:
        raise ValueError(f"unknown AHL snapshot {snapshot!r}; mirrored: {list(SNAPSHOTS)}")
    if not 1 <= int(state) <= 32:
        raise ValueError(f"state must be 1-32, got {state!r}")
    return f"ahl_{table}_{snapshot}_{int(state):02d}.parquet"


def ahl_member(table: str, state: int) -> str:
    """The CSV member of one table inside a state's ZIP (``AHL01Habitantes.csv``)."""
    return f"AHL{int(state):02d}{TABLES[table]}.csv"
