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

EXIT_OK = 0
EXIT_IMPOSSIBLE = 2


class ModuleError(Exception):
    """Exécution impossible : le message (en français) est affiché, le code de sortie est 2."""


def read_config(path: str | os.PathLike) -> dict:
    """Lit config.yml et rend son contenu."""
    path = Path(path)
    if not path.is_file():
        raise ModuleError(f"config.yml introuvable : {path}")
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ModuleError(f"config.yml illisible ({path}) : {error}") from error
    if not isinstance(content, dict):
        raise ModuleError(f"config.yml vide ou mal formé : {path}")
    return content


def validator_path() -> Path:
    """`SYLVIGENESE_VALIDATE` si elle existe, sinon `contracts/validate` depuis le dossier courant."""
    env = os.environ.get("SYLVIGENESE_VALIDATE", "")
    return Path(env) if env else Path("contracts") / "validate"


def call_validator(arguments: list[str]) -> int:
    """Lance `python3 <validateur> <arguments>` et rend son code (0 conforme, 2 impossible, 3 non conforme)."""
    validator = validator_path()
    if not validator.is_file():
        raise ModuleError(f"validateur introuvable : {validator} (mission 009)")
    return subprocess.run([sys.executable, str(validator), *arguments], check=False).returncode


def run(name: str, config_path: str | os.PathLike = "config.yml") -> int:
    """Squelette d'un module : lit la config, la fait valider, rend 0 ou 2."""
    try:
        read_config(config_path)
        code = call_validator(["config", str(config_path)])
        if code != 0:
            raise ModuleError(f"config.yml non conforme (validateur, code {code})")
    except ModuleError as error:
        print(f"[{name}] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    print(f"[{name}] config.yml lu et conforme ; rien d'autre à faire (squelette).", file=sys.stderr)
    return EXIT_OK


def module_main(name: str, argv: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande d'un module : `--config <chemin>` (défaut config.yml)."""
    parser = argparse.ArgumentParser(prog=name, exit_on_error=False)
    parser.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return EXIT_IMPOSSIBLE
    return run(name, options.config)
