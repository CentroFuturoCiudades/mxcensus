"""Lazy YAML loader for bundled config files.

All YAML access goes through this module. First call parses and caches;
subsequent calls return the same dict object (no re-parsing).
"""
from __future__ import annotations

import functools
from importlib import resources
from typing import Any

import yaml


@functools.cache
def _load_yaml(name: str) -> Any:
    pkg = resources.files("mxcensus._yaml")
    return yaml.safe_load((pkg / name).read_text(encoding="utf-8"))


def variables_personas() -> dict:
    return _load_yaml("variables_personas.yaml")


def variables_viviendas() -> dict:
    return _load_yaml("variables_viviendas.yaml")


def variables_iter() -> dict:
    return _load_yaml("variables_iter.yaml")


def variables_resargebub() -> dict:
    return _load_yaml("variables_resargebub.yaml")


def variables_denue(schema_id: str) -> dict:
    """Variable dictionary for one DENUE schema group, e.g. ``variables_denue("g10")``."""
    return _load_yaml(f"variables_denue_{schema_id}.yaml")


def denue_schema_map() -> dict:
    """DENUE schema map: fingerprints→group, group→columns, and the ``latest`` group."""
    return _load_yaml("denue_schema_map.yaml")


def constraints_personas() -> dict:
    return _load_yaml("constraints_personas.yaml")


def constraints_viviendas() -> dict:
    return _load_yaml("constraints_viviendas.yaml")
