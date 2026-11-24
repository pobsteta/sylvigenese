"""Catalogue des contrats (`contracts/catalog.yml`) : nom, couche, schéma, chemins.

Un contrat se désigne par son nom complet (`prepare.trees_init`) ou par son nom court
(`trees_init`), comme dans les tests d'acceptation de la mission 010.
"""
import json
from functools import lru_cache
from pathlib import Path

import yaml

from .report import Refused

CONTRACTS_DIR = Path(__file__).resolve().parent.parent
KINDS = {"parquet", "csv", "geopackage", "yaml", "json", "geotiff", "glb"}


@lru_cache(maxsize=1)
def load():
    with open(CONTRACTS_DIR / "catalog.yml", encoding="utf-8") as f:
        catalog = yaml.safe_load(f)
    return catalog["contracts"]


def names():
    """Nom complet -> liste des noms courts."""
    return {name: spec.get("aliases", []) for name, spec in load().items()}


def resolve(name):
    """Nom complet d'un contrat donné par son nom complet ou court ; Refused sinon."""
    contracts = load()
    if name in contracts:
        return name
    matches = [full for full, spec in contracts.items() if name in spec.get("aliases", [])]
    if len(matches) == 1:
        return matches[0]
    suffix = [full for full in contracts if full.split(".")[-1] == name]
    if suffix:
        raise Refused(f"contrat ambigu : {name} ; préciser {' ou '.join(sorted(suffix))}")
    raise Refused(f"contrat inconnu : {name} (liste : contracts/validate --list)")


def get(name):
    return load()[name]


def load_schema(relative):
    """Contenu d'un fichier de schéma ; Refused si le contrat lui-même est illisible."""
    path = CONTRACTS_DIR / relative
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise Refused(f"contrat invalide : schéma {relative} illisible ({exc})") from exc
