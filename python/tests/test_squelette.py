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
from sylvigenese.commun import ErreurModule, lire_config

RACINE = Path(__file__).resolve().parents[2]
CONFIG = RACINE / "config.yml"
MODULES = [import_tarif, post, assets]  # import_tarif : voir aussi test_import_tarif.py (mission 027)


def faux_validateur(dossier: Path, code: int) -> Path:
    chemin = dossier / "validate"
    chemin.write_text(f"import sys\nsys.exit({code})\n", encoding="utf-8")
    return chemin


def racine_temporaire(tmp_path: Path, zone_chaine: Path) -> Path:
    """Racine d'essai : copie de la zone passée par prepare/biomes/trees (conftest), sans les sorties
    d'assets (le dépôt n'est pas écrit)."""
    cible = tmp_path / "racine" / "tests" / "fixtures" / "zone_fictive"
    shutil.copytree(zone_chaine, cible,
                    ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim"))
    return tmp_path / "racine"


@pytest.fixture(autouse=True)
def depuis_la_racine(monkeypatch):
    monkeypatch.chdir(RACINE)


def test_lire_config_du_depot():
    config = lire_config(CONFIG)
    assert config["crs"] == "EPSG:2154"
    assert config["grid"]["resolution_m"] == 25
    assert config["management"] == "none"


def test_lire_config_absent():
    with pytest.raises(ErreurModule, match="introuvable"):
        lire_config("/nulle/part/config.yml")


@pytest.mark.parametrize("module", MODULES)
def test_sortie_0_si_le_validateur_dit_0(module, tmp_path, monkeypatch, request):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(faux_validateur(tmp_path, 0)))
    if module is assets:  # assets écrit ses sorties : racine temporaire, pas le dépôt
        monkeypatch.setenv("SYLVIGENESE_ROOT", str(racine_temporaire(tmp_path, request.getfixturevalue("zone_chaine"))))
    assert module.main(["--config", str(CONFIG)]) == 0


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_le_validateur_refuse(module, tmp_path, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(faux_validateur(tmp_path, 3)))
    assert module.main(["--config", str(CONFIG)]) == 2


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_le_validateur_est_absent(module, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", "/nulle/part/validate")
    assert module.main(["--config", str(CONFIG)]) == 2


@pytest.mark.parametrize("module", MODULES)
def test_sortie_2_si_config_absent(module, tmp_path, monkeypatch):
    monkeypatch.setenv("SYLVIGENESE_VALIDATE", str(faux_validateur(tmp_path, 0)))
    assert module.main(["--config", "/nulle/part/config.yml"]) == 2


def test_sortie_2_si_argument_inconnu():
    assert post.main(["--inconnu"]) == 2


@pytest.mark.parametrize("nom", ["import_tarif", "post", "assets"])
def test_integration_en_ligne_de_commande_avec_le_vrai_validateur(nom, tmp_path, request):
    # Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
    env = {**os.environ, "PYTHONPATH": str(RACINE / "python")}
    if nom == "assets":  # racine temporaire : le dépôt n'est pas écrit
        env["SYLVIGENESE_ROOT"] = str(racine_temporaire(tmp_path, request.getfixturevalue("zone_chaine")))
    resultat = subprocess.run(
        [sys.executable, "-m", f"sylvigenese.{nom}", "--config", str(CONFIG)],
        cwd=RACINE, env=env, capture_output=True, text=True,
    )
    assert resultat.returncode == 0, resultat.stderr
