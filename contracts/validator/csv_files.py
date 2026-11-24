"""Tables CSV : contrôle par frictionless-py, messages traduits en français (spec §2).

Le dialecte se règle par l'extension `x-csv` du contrat (`{"delimiter": ";"}` pour les
fichiers de sylvostation et de l'IFN) ; par défaut : virgule, UTF-8, une ligne d'en-tête.
Les règles propres au projet (NaN refusé, table vide refusée, emprise du Lambert-93)
s'ajoutent après frictionless, sur les lignes déjà typées.
"""
import csv
import math
import re

from . import extent
from .tables import TYPE_LABELS
from .report import Findings, show_value

LIMIT_ERRORS = 1000
DATARESOURCE_V2 = "https://datapackage.org/profiles/2.0/dataresource.json"

# Type d'erreur frictionless -> message français. {field}, {row}, {cell}, {note}.
MESSAGES = {
    "missing-label": "colonne obligatoire absente : {field}",
    "extra-label": "colonne inattendue : {cell} (absente du contrat)",
    "incorrect-label": "en-tête inattendu {cell} pour la colonne {field}",
    "duplicate-label": "colonne en doublon dans l'en-tête : {cell}",
    "blank-label": "nom de colonne vide dans l'en-tête",
    "type-error": "colonne {field} : valeur {cell} à la ligne {row} du fichier n'est pas du type attendu "
                  "({note})",
    "constraint-error": "colonne {field} : valeur {cell} à la ligne {row} du fichier ne respecte pas la "
                        "contrainte ({note})",
    "unique-error": "colonne {field} : doublon {cell} à la ligne {row} du fichier",
    "primary-key": "clé primaire en doublon à la ligne {row} du fichier",
    "missing-cell": "colonne {field} : valeur manquante à la ligne {row} du fichier",
    "extra-cell": "ligne {row} : cellule en trop",
    "blank-row": "ligne {row} vide",
    "encoding-error": "fichier CSV illisible : encodage invalide, UTF-8 attendu",
    "format-error": "fichier CSV illisible : format non reconnu",
    "source-error": "fichier CSV illisible",
    "scheme-error": "fichier CSV illisible",
}
CONSTRAINT_NOTE = re.compile(r'constraint "(\w+)" is "(.*)"')
CONSTRAINTS_FR = {"required": "obligatoire", "unique": "unique", "minLength": "longueur minimale",
                  "pattern": "motif", "enum": "liste fermée", "minimum": "minimum",
                  "maximum": "maximum", "exclusiveMinimum": "minimum exclusif",
                  "exclusiveMaximum": "maximum exclusif"}


def strip_extensions(schema, header):
    """Schéma pour frictionless : sans extensions x-, sans les colonnes facultatives
    (x-optional) absentes de l'en-tête."""
    plain = {k: v for k, v in schema.items() if not k.startswith("x-")}
    plain["fields"] = [{k: v for k, v in f.items() if not k.startswith("x-")}
                       for f in schema["fields"]
                       if not (f.get("x-optional") and f["name"] not in header)]
    return plain


def read_header(path, delimiter):
    with open(path, encoding="utf-8", newline="") as f:
        return next(csv.reader(f, delimiter=delimiter), [])


def looks_like_text(path):
    with open(path, "rb") as f:
        data = f.read(65536)
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return exc.start > len(data) - 4  # coupure d'un caractère en fin de bloc
    return True


NON_FINITE = {"nan", "inf", "infinity"}


def is_non_finite(cell):
    """Vrai pour une cellule NaN ou infinie, écrite en texte ou déjà lue en nombre."""
    if isinstance(cell, float):
        return not math.isfinite(cell)
    return isinstance(cell, str) and cell.strip().lstrip("+-").lower() in NON_FINITE


def translate(error, field_types):
    """Message français d'une erreur frictionless."""
    template = MESSAGES.get(error.type)
    note = getattr(error, "note", "") or ""
    if error.type == "type-error":
        note = TYPE_LABELS.get(field_types.get(getattr(error, "field_name", None)), "?") + " attendu"
    match = CONSTRAINT_NOTE.match(note)
    if match:
        note = f"{CONSTRAINTS_FR.get(match.group(1), match.group(1))} {match.group(2)}"
    if template is None:
        return f"erreur de table ({error.type}) : {note}"
    cell = getattr(error, "cell", None)
    labels = getattr(error, "label", None)
    if error.type in ("type-error", "constraint-error") and is_non_finite(cell):
        return (f"colonne {getattr(error, 'field_name', '?')} : valeur NaN ou infinie refusée "
                f"({show_value(cell)} à la ligne {getattr(error, 'row_number', '?')} du "
                f"fichier ; nombre fini attendu)")
    return template.format(field=getattr(error, "field_name", "?"),
                           row=getattr(error, "row_number", "?"),
                           cell=show_value(cell if cell is not None else labels),
                           note=note)


def check(path, schema, options):
    findings = Findings()
    if not looks_like_text(path):
        findings.error("fichier CSV illisible : ce n'est pas du texte UTF-8")
        return [(path, findings)]
    from frictionless import Resource  # import tardif : ~0,5 s

    dialect = schema.get("x-csv", {})
    delimiter = dialect.get("delimiter", ",")
    # Ressource déclarée en Data Package v2 : sans cela, frictionless impose la v1 au
    # schéma qu'elle contient (fieldsMatch et exclusiveMinimum seraient refusés).
    plain = strip_extensions(schema, read_header(path, delimiter))
    resource = Resource({"$schema": DATARESOURCE_V2, "name": "table", "path": path.name,
                         "format": "csv", "schema": plain,
                         "dialect": {"csv": {"delimiter": delimiter}}},
                        basepath=str(path.parent))
    report = resource.validate(limit_errors=LIMIT_ERRORS)
    field_types = {f["name"]: f["type"] for f in schema["fields"]}
    for task in report.tasks:
        for error in task.errors:
            findings.error(translate(error, field_types))
    if findings:
        return [(path, findings)]
    check_rows(resource, schema, findings)
    return [(path, findings)]


def check_rows(resource, schema, findings):
    """Règles du projet en plus de frictionless : NaN, table vide, emprise."""
    numbers = [f["name"] for f in schema["fields"] if f["type"] == "number"]
    xy = schema.get("x-extent")
    n = 0
    with resource:
        for row in resource.row_stream:
            n += 1
            line = row.row_number
            for name in numbers:
                value = row.get(name)
                if value is not None and not math.isfinite(float(value)):
                    findings.error(f"colonne {name} : valeur {show_value(str(value))} à la ligne "
                                   f"{line} du fichier : valeur NaN ou infinie refusée")
                    return
            if xy:
                x, y = row.get(xy["x"]), row.get(xy["y"])
                problem = extent.point_problem(None if x is None else float(x),
                                               None if y is None else float(y))
                if problem:
                    findings.error(f"ligne {line} du fichier : {problem}")
                    return
    if n == 0 and not schema.get("x-allow-empty", False):
        findings.error("table vide : aucune ligne de données, au moins une attendue")
