"""Documents YAML et JSON contre un JSON Schema 2020-12 (spec §2, §9).

Les schémas sont tous locaux (`contracts/json/`, dont les schémas CesiumGS de 3D Tiles 1.1
dans `json/vendor/`) : aucun accès réseau. Une clé en double est refusée au lieu de garder
la dernière. Mot-clé propre au projet : `x-lambert93: true` sur un objet qui porte `x` et
`y` en EPSG:2154 ; le point doit tomber dans l'emprise (`extent.py`).
"""
import json
from functools import lru_cache
from pathlib import Path

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from . import extent
from .report import Findings, show_value

CONTRACTS_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = CONTRACTS_DIR / "json"


class DuplicateKeyLoader(yaml.SafeLoader):
    """Chargeur YAML qui refuse une clé en double dans un même objet."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"clé en double : {key}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_document(path, fmt):
    """Contenu du fichier ; ValueError avec un message français s'il est illisible."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("fichier illisible : texte UTF-8 attendu") from exc
    if fmt == "yaml":
        try:
            return yaml.load(text, Loader=DuplicateKeyLoader)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
            where = f", ligne {mark.line + 1}" if mark else ""
            problem = getattr(exc, "problem", None) or ""
            if "clé en double" in str(exc):
                problem = str(exc).split("\n")[0]
            raise ValueError(f"fichier YAML illisible{where} : erreur de syntaxe {problem}".rstrip()) from exc

    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            raise ValueError(f"fichier JSON invalide : clé en double {sorted(dup)[0]}")
        return dict(pairs)

    try:
        return json.loads(text, object_pairs_hook=no_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"fichier JSON illisible, ligne {exc.lineno} : erreur de syntaxe") from exc


@lru_cache(maxsize=1)
def registry():
    resources = []
    for file in sorted(JSON_DIR.rglob("*.json")):
        with open(file, encoding="utf-8") as f:
            contents = json.load(f)
        if isinstance(contents, dict) and "$id" in contents:
            resources.append((contents["$id"], Resource(contents, specification=DRAFT202012)))
    return Registry().with_resources(resources)


def lambert93(validator, enabled, instance, schema):
    if not enabled or not isinstance(instance, dict):
        return
    x, y = instance.get("x"), instance.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        problem = extent.point_problem(float(x), float(y))
        if problem:
            yield jsonschema.ValidationError(problem, validator="x-lambert93")


Validator = jsonschema.validators.extend(jsonschema.Draft202012Validator,
                                         {"x-lambert93": lambert93})


def where(error):
    path = ".".join(str(p) for p in error.absolute_path)
    return path or "(racine)"


def translate(error):
    """Message français d'une erreur jsonschema, qui nomme la clé en cause."""
    kw, value, inst = error.validator, error.validator_value, error.instance
    at = where(error)
    prefix = "" if at == "(racine)" else at + "."
    if kw == "required":
        missing = [k for k in value if isinstance(inst, dict) and k not in inst]
        return "clé obligatoire absente : " + ", ".join(prefix + k for k in missing)
    if kw == "additionalProperties":
        known = set(error.schema.get("properties", {}))
        extra = [k for k in inst if k not in known] if isinstance(inst, dict) else []
        return "clé inconnue (absente du contrat) : " + ", ".join(prefix + k for k in extra)
    if kw == "const":
        return f"{at} : valeur {show_value(inst)} refusée, {show_value(value)} attendu"
    if kw == "enum":
        return (f"{at} : valeur {show_value(inst)} hors de la liste fermée "
                f"({', '.join(map(str, value))})")
    if kw == "type":
        return f"{at} : type attendu {value}, trouvé {show_value(inst)}"
    if kw in ("minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"):
        word = {"minimum": "minimum", "exclusiveMinimum": "minimum exclusif",
                "maximum": "maximum", "exclusiveMaximum": "maximum exclusif"}[kw]
        return f"{at} : valeur {show_value(inst)} hors limite ({word} {value})"
    if kw == "pattern":
        return f"{at} : valeur {show_value(inst)} ne respecte pas le motif {value}"
    if kw == "propertyNames":
        return f"{at} : nom de clé {show_value(inst)} invalide"
    if kw in ("minItems", "minLength", "minProperties"):
        return f"{at} : valeur trop courte ou vide (règle {kw} = {value})"
    if kw == "x-lambert93":
        return f"{at} : {error.message}"
    return f"{at} : valeur invalide (règle {kw})"


def check(path, schema_file, fmt):
    findings = Findings()
    try:
        document = load_document(path, fmt)
    except ValueError as exc:
        findings.error(str(exc))
        return [(path, findings)]
    with open(CONTRACTS_DIR / schema_file, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Validator(schema, registry=registry(),
                          format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(map(str, e.absolute_path)))
    for error in errors:
        findings.error(translate(error))
    return [(path, findings)]
