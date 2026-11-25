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

REPO_ROOT = Path(__file__).resolve().parents[2]
TO_COPY = ["R", "biomes", "contracts", "python", "config.yml", "Makefile", "DESCRIPTION", "NAMESPACE", "_targets.R"]
VERSIONED_ZONE = ["inputs", "params", "README.md", "zone.yml"]


@pytest.fixture(scope="session")
def zone_chain(tmp_path_factory) -> Path:
    """Dossier de zone du jeu fictif après `make prepare biomes trees` (racine temporaire)."""
    root = tmp_path_factory.mktemp("chaine")
    for name in TO_COPY:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(source, root / name, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        elif source.is_file():
            shutil.copy2(source, root / name)
    zone_source = REPO_ROOT / "tests" / "fixtures" / "zone_fictive"
    zone = root / "tests" / "fixtures" / "zone_fictive"
    zone.mkdir(parents=True)
    for name in VERSIONED_ZONE:
        source = zone_source / name
        if source.is_dir():
            shutil.copytree(source, zone / name)
        elif source.is_file():
            shutil.copy2(source, zone / name)
    result = subprocess.run(["make", "prepare", "biomes", "trees", "ZONE=zone_fictive"], cwd=root,
                              capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert (zone / "trees_init" / "trees.parquet").is_file()
    return zone


@pytest.fixture(scope="session")
def chain_root(zone_chain) -> Path:
    return zone_chain.parents[2]
