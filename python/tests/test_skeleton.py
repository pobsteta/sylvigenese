"""Tests du squelette Python (mission 012). Lancés par `make test-python` depuis la racine du dépôt.

Le validateur est remplacé par un faux script pour les cas 0 / 3 / absent. Le test
d'intégration appelle le vrai validateur : rouge tant que `contracts/validate`
(mission 009) est absent de l'arbre, sauf si SYLVIGENESE_VALIDATE le désigne.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sylvigenese import assets, import_tarif, post
from sylvigenese.common import ModuleError, read_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config.yml"
MODULES = [import_tarif, post, assets]  # import_tarif : voir aussi test_import_tarif.py (mission 027)


def fake_validator(directory: Path, code: int) -> Path:
    path = directory / "validate"
    path.write_text(f"import sys\nsys.exit({code})\n", encoding="utf-8")
    return path


def temporary_root(tmp_path: Path, zone_chain: Path) -> Path:
    """Racine d'essai : copie de la zone passée par prepare/biomes/trees (conftest), sans les sorties
    d'assets (le dépôt n'est pas écrit)."""
    target = tmp_path / "racine" / "tests" / "fixtures" / "zone_fictive"
    shutil.copytree(zone_chain, target,
                    ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim"))
    return tmp_path / "racine"


@pytest.fixture(autouse=True)
def from_root(monkeypatch):
    monkeypatch.chdir(ROOT)


def test_lire_config_du_depot():
    config = read_config(CONFIG)
    assert config["crs"] == "EPSG:2154"
    assert config["grid"]["resolution_m"] == 25
    assert config["management"] == "none"


def test_lire_config_absent():
    with pytest.raises(ModuleError, match="introuvable"):
        read_config("/nulle/part/config.yml")


@pytest.mark.parametrize("module", MODULES)
def test_sortie_0_si_le_validateur_dit_0(module, tmp_path, monkeypatch, request):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(fake_validator(tmp_path, 0)))
    if module is assets:  # assets écrit ses sorties : racine temporaire, pas le dépôt
        monkeypatch.setenv("SYLVIGENESE_ROOT", str(temporary_root(tmp_path, request.getfixturevalue("zone_chain"))))
    assert module.main(["--config", str(CONFIG)]) == 0


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_le_validateur_refuse(module, tmp_path, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(fake_validator(tmp_path, 3)))
    assert module.main(["--config", str(CONFIG)]) == 2


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_le_validateur_est_absent(module, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", "/nulle/part/validate")
    assert module.main(["--config", str(CONFIG)]) == 2


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_config_absent(module, tmp_path, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(fake_validator(tmp_path, 0)))
    assert module.main(["--config", "/nulle/part/config.yml"]) == 2


def test_sortie_2_si_argument_inconnu():
    assert post.main(["--inconnu"]) == 2


@pytest.mark.parametrize("name", ["import_tarif", "post", "assets"])
def test_integration_en_ligne_de_commande_avec_le_vrai_validateur(name, tmp_path, request):
    # Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
    env = {**os.environ, "PYTHONPATH": str(ROOT / "python")}
    if name == "assets":  # racine temporaire : le dépôt n'est pas écrit
        env["SYLVIGENESE_ROOT"] = str(temporary_root(tmp_path, request.getfixturevalue("zone_chain")))
    result = subprocess.run(
        [sys.executable, "-m", f"sylvigenese.{name}", "--config", str(CONFIG)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
