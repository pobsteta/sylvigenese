"""Bloc `simulate` de config.yml (mission 034) : level, seed, t0 et years sont exigés ; threads est facultatif.

Aucune valeur par défaut silencieuse : le schéma refuse un bloc incomplet, et simulate refuse (code 2)
l'absence du bloc. Le config.yml du dépôt porte le bloc actif (jeu fictif : t0 = 2022, année du vol
le plus récent de chm_date.tif : la hauteur ne se recule pas, décision de l'orchestrateur du 25/11/2026).
"""
import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import helpers as h

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "contracts" / "validate"


def run(tmp_path, content):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return subprocess.run([sys.executable, str(VALIDATE), "config", str(path)], capture_output=True, text=True)


def test_config_du_depot_porte_le_bloc_simulate_actif():
    content = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    assert content["simulate"]["level"] == "massif"
    assert content["simulate"]["t0"] == 2022          # année du vol le plus récent du jeu fictif
    assert set(content["simulate"]) >= {"level", "seed", "t0", "years"}
    done = subprocess.run([sys.executable, str(VALIDATE), "config", str(ROOT / "config.yml")], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize("key", ["level", "seed", "t0", "years"])
def test_cle_de_simulate_absente_est_refusee(tmp_path, key):
    content = copy.deepcopy(h.config())
    del content["simulate"][key]
    result = run(tmp_path, content)
    assert result.returncode == 3, result.stdout + result.stderr
    assert key in result.stdout + result.stderr


def test_threads_est_facultatif(tmp_path):
    content = copy.deepcopy(h.config())
    del content["simulate"]["threads"]
    assert run(tmp_path, content).returncode == 0


@pytest.mark.parametrize("change", [("seed", -1), ("years", 0), ("t0", "2021"), ("level", "zone"), ("threads", 0)])
def test_valeur_hors_contrat_refusee(tmp_path, change):
    content = copy.deepcopy(h.config())
    content["simulate"][change[0]] = change[1]
    assert run(tmp_path, content).returncode == 3


def test_config_sans_bloc_simulate_reste_valide_pour_les_autres_modules(tmp_path):
    """Le schéma n'impose pas le bloc aux modules qui n'en ont pas besoin ; c'est simulate qui refuse (code 2)."""
    content = copy.deepcopy(h.config())
    del content["simulate"]
    assert run(tmp_path, content).returncode == 0
