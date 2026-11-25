"""Fixture commune des tests de `assets` : la chaîne prepare -> biomes -> trees, une fois par session.

Les sorties de ces modules (trees_init/, vegetation_map.tif, h0.tif, ...) sont ignorées par git :
sur un clone propre, elles n'existent pas. La fixture fabrique donc une racine temporaire (R, biomes,
contracts, config.yml, Makefile et les entrées versionnées du jeu fictif), y lance
`make prepare biomes trees ZONE=zone_fictive`, et rend le dossier de zone obtenu. Le dépôt n'est
jamais écrit. Rscript est nécessaire : s'il manque, le test échoue (pas de saut silencieux).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
A_COPIER = ["R", "biomes", "contracts", "python", "config.yml", "Makefile", "DESCRIPTION", "NAMESPACE", "_targets.R"]
ZONE_VERSIONNEE = ["inputs", "params", "README.md", "zone.yml"]


@pytest.fixture(scope="session")
def zone_chaine(tmp_path_factory) -> Path:
    """Dossier de zone du jeu fictif après `make prepare biomes trees` (racine temporaire)."""
    racine = tmp_path_factory.mktemp("chaine")
    for nom in A_COPIER:
        source = RACINE_DEPOT / nom
        if source.is_dir():
            shutil.copytree(source, racine / nom, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        elif source.is_file():
            shutil.copy2(source, racine / nom)
    zone_source = RACINE_DEPOT / "tests" / "fixtures" / "zone_fictive"
    zone = racine / "tests" / "fixtures" / "zone_fictive"
    zone.mkdir(parents=True)
    for nom in ZONE_VERSIONNEE:
        source = zone_source / nom
        if source.is_dir():
            shutil.copytree(source, zone / nom)
        elif source.is_file():
            shutil.copy2(source, zone / nom)
    resultat = subprocess.run(["make", "prepare", "biomes", "trees", "ZONE=zone_fictive"], cwd=racine,
                              capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stdout[-2000:] + resultat.stderr[-2000:]
    assert (zone / "trees_init" / "trees.parquet").is_file()
    return zone


@pytest.fixture(scope="session")
def racine_chaine(zone_chaine) -> Path:
    return zone_chaine.parents[2]
