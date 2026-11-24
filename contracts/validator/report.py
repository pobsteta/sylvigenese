"""Écarts et refus : ce que le validateur dit, et avec quel code de sortie.

- `Refused` : le contrôle n'a pas pu se faire (code 2) : arguments, contrat inconnu,
  fichier absent, contrat lui-même invalide.
- `Findings` : liste des écarts d'un fichier lu (code 3 s'il y en a au moins un).
"""

OK = 0
REFUSED = 2
NONCONFORM = 3


class Refused(Exception):
    """Le contrôle ne peut pas se faire : code de sortie 2."""


class Unreadable(Exception):
    """Le fichier existe mais ne peut pas être lu au format attendu : écart (code 3)."""


class Findings:
    """Écarts relevés sur un fichier, et avertissements (qui ne changent pas le code)."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def extend(self, other):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def __bool__(self):
        return bool(self.errors)


def show_value(value, limit=60):
    """Une valeur lisible dans un message, entre guillemets français."""
    text = repr(value) if not isinstance(value, str) else value
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return f"« {text} »"
