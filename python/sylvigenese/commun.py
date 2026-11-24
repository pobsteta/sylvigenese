"""Briques communes aux modules Python (spec §2, ADR 0002).

- lire `config.yml` (le contrôle des clés est fait par le validateur, pas ici) ;
- appeler le validateur des contrats **en sous-processus** : aucun import de son code ;
- fournir le point d'entrée en ligne de commande : code de sortie 0 ou 2.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

SORTIE_OK = 0
SORTIE_IMPOSSIBLE = 2


class ErreurModule(Exception):
    """Exécution impossible : le message (en français) est affiché, le code de sortie est 2."""


def lire_config(chemin: str | os.PathLike) -> dict:
    """Lit config.yml et rend son contenu."""
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurModule(f"config.yml introuvable : {chemin}")
    try:
        contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as erreur:
        raise ErreurModule(f"config.yml illisible ({chemin}) : {erreur}") from erreur
    if not isinstance(contenu, dict):
        raise ErreurModule(f"config.yml vide ou mal formé : {chemin}")
    return contenu


def chemin_validateur() -> Path:
    """`SYLVIGENESE_VALIDATE` si elle existe, sinon `contracts/validate` depuis le dossier courant."""
    env = os.environ.get("SYLVIGENESE_VALIDATE", "")
    return Path(env) if env else Path("contracts") / "validate"


def appeler_validateur(arguments: list[str]) -> int:
    """Lance `python3 <validateur> <arguments>` et rend son code (0 conforme, 2 impossible, 3 non conforme)."""
    validateur = chemin_validateur()
    if not validateur.is_file():
        raise ErreurModule(f"validateur introuvable : {validateur} (mission 009)")
    return subprocess.run([sys.executable, str(validateur), *arguments], check=False).returncode


def executer(nom: str, chemin_config: str | os.PathLike = "config.yml") -> int:
    """Squelette d'un module : lit la config, la fait valider, rend 0 ou 2."""
    try:
        lire_config(chemin_config)
        code = appeler_validateur(["config", str(chemin_config)])
        if code != 0:
            raise ErreurModule(f"config.yml non conforme (validateur, code {code})")
    except ErreurModule as erreur:
        print(f"[{nom}] erreur : {erreur}", file=sys.stderr)
        return SORTIE_IMPOSSIBLE
    print(f"[{nom}] config.yml lu et conforme ; rien d'autre à faire (squelette).", file=sys.stderr)
    return SORTIE_OK


def main_module(nom: str, argv: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande d'un module : `--config <chemin>` (défaut config.yml)."""
    analyseur = argparse.ArgumentParser(prog=nom, exit_on_error=False)
    analyseur.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = analyseur.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return SORTIE_IMPOSSIBLE
    return executer(nom, options.config)
