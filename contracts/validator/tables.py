"""Contrôle d'une table Arrow contre un Table Schema v2 (Frictionless), en vectoriel.

Sert au Parquet et aux attributs des GeoPackage (spec §2, ADR 0002). Le CSV passe par
frictionless-py (`csv_files.py`). On ne lit pas le Parquet avec frictionless : il passe par
pandas et ligne par ligne, ce qui ne tient pas les 30 minutes sur `sim/`.

Sous-ensemble pris en charge, et rien d'autre (un contrat qui demande plus est refusé,
code 2, plutôt que d'être contrôlé à moitié) :
- types : string, integer, number, boolean, date ;
- contraintes : required, unique, minLength, pattern, enum, minimum, maximum,
  exclusiveMinimum, exclusiveMaximum ;
- niveau table : fieldsMatch (equal, subset), primaryKey, missingValues ;
- extensions de sylvigenese : x-optional (colonne qui peut manquer), x-extent, x-allow-empty, x-require-one-of,
  x-schema-version, x-geopackage, x-csv.

Règles propres au projet (contracts/README.md) : un nombre NaN ou infini est toujours
refusé ; une table vide est refusée sauf `x-allow-empty: true`.
"""
import pyarrow as pa
import pyarrow.compute as pc

from . import extent
from .report import Refused, show_value

FIELD_KEYS = {"name", "type", "format", "title", "description", "constraints", "example",
              "unit", "x-unit", "x-optional"}
CONSTRAINT_KEYS = {"required", "unique", "minLength", "pattern", "enum", "minimum",
                   "maximum", "exclusiveMinimum", "exclusiveMaximum"}
SCHEMA_KEYS = {"$schema", "fields", "fieldsMatch", "primaryKey", "missingValues", "title",
               "description", "x-schema-version", "x-extent", "x-allow-empty",
               "x-require-one-of", "x-geopackage", "x-csv", "x-names-fixed-by"}
TYPES = {"string", "integer", "number", "boolean", "date"}
TYPE_LABELS = {"string": "chaîne", "integer": "entier", "number": "nombre",
               "boolean": "booléen", "date": "date"}


def check_schema_supported(schema):
    """Refuse (code 2) un contrat qui sort du sous-ensemble pris en charge."""
    unknown = set(schema) - SCHEMA_KEYS
    if unknown:
        raise Refused(f"contrat invalide : propriétés non prises en charge {sorted(unknown)}")
    if schema.get("fieldsMatch", "equal") not in ("equal", "subset"):
        raise Refused("contrat invalide : fieldsMatch doit valoir equal ou subset")
    names = set()
    for field in schema.get("fields", []):
        if set(field) - FIELD_KEYS:
            raise Refused(f"contrat invalide : colonne {field.get('name')} : propriétés "
                          f"non prises en charge {sorted(set(field) - FIELD_KEYS)}")
        if field.get("type") not in TYPES:
            raise Refused(f"contrat invalide : colonne {field.get('name')} : type "
                          f"{field.get('type')} non pris en charge")
        if set(field.get("constraints", {})) - CONSTRAINT_KEYS:
            raise Refused(f"contrat invalide : colonne {field['name']} : contraintes non "
                          f"prises en charge {sorted(set(field['constraints']) - CONSTRAINT_KEYS)}")
        names.add(field["name"])
    for key in schema.get("primaryKey", []):
        if key not in names:
            raise Refused(f"contrat invalide : clé primaire {key} absente des colonnes")


def is_text(arrow_type):
    return (pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type)
            or pa.types.is_string_view(arrow_type))


def arrow_type_matches(ts_type, arrow_type):
    if ts_type == "string":
        if pa.types.is_dictionary(arrow_type):
            return is_text(arrow_type.value_type)
        return is_text(arrow_type)
    if ts_type == "integer":
        return pa.types.is_integer(arrow_type)
    if ts_type == "number":
        return pa.types.is_floating(arrow_type)
    if ts_type == "boolean":
        return pa.types.is_boolean(arrow_type)
    if ts_type == "date":
        return pa.types.is_date(arrow_type)
    return False


def check_columns(schema, column_names, findings):
    """Présence des colonnes selon fieldsMatch. Rend les noms des colonnes à contrôler."""
    wanted = [f["name"] for f in schema["fields"]]
    for field in schema["fields"]:
        if field["name"] not in column_names and not field.get("x-optional"):
            findings.error(f"colonne obligatoire absente : {field['name']}")
    if schema.get("fieldsMatch", "equal") == "equal":
        for name in column_names:
            if name not in wanted:
                findings.error(f"colonne inattendue : {name} (absente du contrat)")
    return [n for n in wanted if n in column_names]


def _first_rows(mask):
    """Indices (à partir de 0) des lignes où le masque booléen est vrai."""
    mask = pc.fill_null(mask, False)
    return pc.indices_nonzero(mask).to_pylist()


def _report(findings, name, mask, column, what):
    rows = _first_rows(mask)
    if rows:
        value = column[rows[0]].as_py()
        findings.error(f"colonne {name} : {len(rows)} valeur(s) {what} ; première à la "
                       f"ligne {rows[0] + 1} : {show_value(value)}")


def check_field_values(field, column, findings):
    """Contraintes d'une colonne déjà au bon type."""
    name = field["name"]
    cons = field.get("constraints", {})
    if isinstance(column, pa.ChunkedArray):
        column = column.combine_chunks()
    if field["type"] == "number":
        bad = pc.invert(pc.is_finite(column))
        _report(findings, name, bad, column, "NaN ou infinies, refusées (valeur invalide)")
    if cons.get("required") and column.null_count:
        rows = _first_rows(pc.is_null(column))
        findings.error(f"colonne {name} : {len(rows)} valeur(s) manquante(s) alors qu'elle "
                       f"est obligatoire ; première à la ligne {rows[0] + 1}")
    if "minLength" in cons:
        short = pc.less(pc.utf8_length(column), cons["minLength"])
        what = "vides" if cons["minLength"] == 1 else f"de moins de {cons['minLength']} caractères"
        _report(findings, name, short, column, what)
    if "pattern" in cons:
        matched = pc.match_substring_regex(column, "^(?:" + cons["pattern"] + ")$")
        hint = f" ({field['description']})" if "description" in field else ""
        _report(findings, name, pc.invert(matched), column,
                f"qui ne respectent pas le motif attendu {cons['pattern']}{hint}")
    if "enum" in cons:
        allowed = pa.array(cons["enum"], type=column.type)
        inside = pc.is_in(column, value_set=allowed)
        outside = pc.and_(pc.invert(inside), pc.is_valid(column))  # NULL : vu par required
        _report(findings, name, outside, column,
                "hors de la liste fermée (" + ", ".join(map(str, cons["enum"])) + ")")
    for key, op, word in (("minimum", pc.less, "inférieures au minimum"),
                          ("maximum", pc.greater, "supérieures au maximum"),
                          ("exclusiveMinimum", pc.less_equal, "inférieures ou égales au minimum exclusif"),
                          ("exclusiveMaximum", pc.greater_equal, "supérieures ou égales au maximum exclusif")):
        if key in cons:
            _report(findings, name, op(column, cons[key]), column, f"{word} {cons[key]}")
    if cons.get("unique"):
        check_unique(findings, [name], pa.table({name: column}))


def check_unique(findings, keys, table, *, primary_key=False):
    """Doublons sur une colonne ou une clé composée.

    Contrainte `unique` d'une colonne : les valeurs nulles sont ignorées.
    Clé primaire (`primary_key=True`) : une valeur nulle est une valeur comme une autre dans le
    couple, donc (H10, nul) en double est refusé ; une ligne dont toutes les colonnes de la clé
    sont nulles est refusée, car elle n'identifie rien (comportement de Frictionless, qui
    sert de référence à Table Schema).
    """
    label = keys[0] if len(keys) == 1 else "(" + ", ".join(keys) + ")"
    if primary_key:
        empty = None
        for k in keys:
            col = pc.is_null(table[k])
            empty = col if empty is None else pc.and_(empty, col)
        rows = _first_rows(empty)
        if rows:
            findings.error(f"clé primaire {label} : {len(rows)} ligne(s) dont la clé est entièrement "
                           f"nulle ; première à la ligne {rows[0] + 1}")
        sub = table.select(keys).filter(pc.invert(empty))
    else:
        sub = table.select(keys).drop_null()
    if sub.num_rows == 0:
        return
    counts = sub.group_by(keys).aggregate([([], "count_all")])
    dup = counts.filter(pc.greater(counts["count_all"], 1))
    if dup.num_rows:
        example = ", ".join("(vide)" if dup[k][0].as_py() is None else str(dup[k][0].as_py())
                            for k in keys)
        findings.error(f"colonne {label} : {dup.num_rows} doublon(s) ; par exemple "
                       f"{show_value(example)}")


def check_table(schema, table, findings, *, skip=()):
    """Contrôle complet d'une table Arrow. `skip` : colonnes déjà signalées au type."""
    check_schema_supported(schema)
    present = check_columns(schema, table.column_names, findings)
    fields = {f["name"]: f for f in schema["fields"]}
    good = []
    for name in present:
        if name in skip:
            continue
        field = fields[name]
        column = table[name]
        if not arrow_type_matches(field["type"], column.type):
            findings.error(f"colonne {name} : type attendu {TYPE_LABELS[field['type']]} "
                           f"({field['type']}), trouvé {column.type}")
            continue
        if field["type"] == "string" and not pa.types.is_string(column.type):
            # dictionnaire de chaînes, string_view, large_string : décodés en chaînes
            column = pc.cast(column, pa.string())
            table = table.set_column(table.column_names.index(name), name, column)
        good.append(name)
        check_field_values(field, column, findings)
    if table.num_rows == 0 and not schema.get("x-allow-empty", False):
        findings.error("table vide : au moins une ligne attendue")
    keys = schema.get("primaryKey", [])
    kc = fields[keys[0]].get("constraints", {}) if len(keys) == 1 else {}
    already_unique = bool(kc.get("unique") and kc.get("required"))
    if keys and all(k in good for k in keys) and not already_unique:
        check_unique(findings, keys, table, primary_key=True)
    one_of = schema.get("x-require-one-of")
    if one_of and all(k in good for k in one_of):
        none = None
        for k in one_of:
            col = pc.is_null(table[k])
            none = col if none is None else pc.and_(none, col)
        rows = _first_rows(none)
        if rows:
            findings.error(f"colonnes {', '.join(one_of)} : {len(rows)} ligne(s) sans aucune "
                           f"valeur alors qu'au moins une est obligatoire ; première à la "
                           f"ligne {rows[0] + 1}")
    xy = schema.get("x-extent")
    if xy and xy["x"] in good and xy["y"] in good:
        check_extent(table[xy["x"]], table[xy["y"]], findings)
    return good


def check_extent(xs, ys, findings):
    """Toutes les coordonnées (x, y) dans l'emprise du Lambert-93."""
    e = extent.load_extent()
    xs = pc.cast(xs, pa.float64())
    ys = pc.cast(ys, pa.float64())
    outside = pc.or_(
        pc.or_(pc.less(xs, e["x_min"]), pc.greater(xs, e["x_max"])),
        pc.or_(pc.less(ys, e["y_min"]), pc.greater(ys, e["y_max"])))
    rows = _first_rows(outside)
    if rows:
        i = rows[0]
        problem = extent.point_problem(xs[i].as_py(), ys[i].as_py())
        findings.error(f"{len(rows)} ligne(s) {problem.replace('coordonnées ', 'aux coordonnées ', 1)} ; "
                       f"première à la ligne {i + 1}")
