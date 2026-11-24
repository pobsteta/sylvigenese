"""GeoPackage : couche, géométrie, système de coordonnées et attributs (spec §3).

Lu avec `sqlite3` de la bibliothèque standard, sans GDAL. La partie vectorielle du contrat
est l'extension `x-geopackage` du Table Schema (décision de l'orchestrateur, mission 009) :

    "x-geopackage": {"layer": "stands", "geometry_types": ["POLYGON", "MULTIPOLYGON"],
                     "srs_epsg": 2154}

Les attributs passent ensuite par le même contrôle que le Parquet (`tables.py`). Chaque
géométrie doit tomber dans l'emprise du Lambert-93 (`extent.py`).
"""
import datetime
import sqlite3
import struct

import pyarrow as pa

from . import extent, tables
from .report import Findings

GPKG_APPLICATION_ID = 0x47504B47  # « GPKG »
DECLARED = {"TEXT": "string", "VARCHAR": "string", "INTEGER": "integer", "INT": "integer",
            "MEDIUMINT": "integer", "SMALLINT": "integer", "TINYINT": "integer",
            "REAL": "number", "DOUBLE": "number", "FLOAT": "number", "BOOLEAN": "boolean",
            "DATE": "date", "DATETIME": "datetime", "BLOB": "blob"}
SQLITE_LABEL = {"string": "TEXT", "integer": "INTEGER", "number": "REAL", "boolean": "BOOLEAN",
                "date": "DATE"}


def declared_type(sql_type):
    base = (sql_type or "").upper().split("(")[0].strip()
    return DECLARED.get(base, base.lower() or "inconnu")


def open_gpkg(path):
    """Connexion en lecture seule ; ValueError si ce n'est pas un GeoPackage lisible."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        app_id = con.execute("PRAGMA application_id").fetchone()[0]
        con.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValueError("fichier GeoPackage illisible : ce n'est pas une base SQLite") from exc
    if app_id != GPKG_APPLICATION_ID:
        con.close()
        raise ValueError("fichier non conforme : base SQLite sans l'identifiant GeoPackage "
                         "(application_id « GPKG »)")
    return con


def check(path, schemas):
    """Écarts d'un GeoPackage à une ou plusieurs couches décrites par `schemas`."""
    findings = Findings()
    try:
        con = open_gpkg(path)
    except ValueError as exc:
        findings.error(str(exc))
        return [(path, findings)]
    try:
        for schema in schemas:
            check_layer(con, schema, findings)
    except sqlite3.DatabaseError as exc:
        findings.error(f"fichier GeoPackage illisible ({exc})")
    finally:
        con.close()
    return [(path, findings)]


def check_layer(con, schema, findings):
    spec = schema["x-geopackage"]
    layer = spec["layer"]
    layers = [r[0] for r in con.execute("SELECT table_name FROM gpkg_contents")]
    if layer not in layers:
        findings.error(f"couche « {layer} » absente du GeoPackage ; couches trouvées : "
                       f"{', '.join(layers) or 'aucune'}")
        return
    geom = con.execute("SELECT column_name, geometry_type_name, srs_id FROM "
                       "gpkg_geometry_columns WHERE table_name = ?", (layer,)).fetchone()
    if geom is None:
        findings.error(f"couche {layer} : aucune colonne de géométrie déclarée")
        return
    geom_col, geom_type, srs_id = geom
    if geom_type.upper() not in spec["geometry_types"]:
        findings.error(f"couche {layer} : géométrie {geom_type}, attendu "
                       f"{' ou '.join(spec['geometry_types'])}")
    srs = con.execute("SELECT organization, organization_coordsys_id FROM "
                      "gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,)).fetchone()
    want = spec["srs_epsg"]
    crs_ok = srs is not None and srs[0].upper() == "EPSG" and srs[1] == want
    if not crs_ok:
        found = f"{srs[0]}:{srs[1]}" if srs else f"srs_id {srs_id} non décrit"
        findings.error(f"couche {layer} : projection {found}, EPSG:{want} attendu")

    info = con.execute(f'PRAGMA table_info("{layer}")').fetchall()
    pk = {r[1] for r in info if r[5]}
    attributes = {r[1]: r[2] for r in info if r[1] != geom_col and r[1] not in pk}
    fields = {f["name"]: f for f in schema["fields"]}
    columns, skip = {}, set()
    for name, sql_type in attributes.items():
        if name not in fields:
            columns[name] = pa.nulls(0)  # présence seulement (fieldsMatch)
            continue
        want_type = fields[name]["type"]
        found = declared_type(sql_type)
        if found != want_type:
            findings.error(f"colonne {name} : type attendu {tables.TYPE_LABELS[want_type]} "
                           f"({SQLITE_LABEL[want_type]}), trouvé {sql_type or 'sans type'}")
            skip.add(name)
            columns[name] = pa.nulls(0)
            continue
        rows = con.execute(f'SELECT "{name}", typeof("{name}") FROM "{layer}" '
                           f'ORDER BY rowid').fetchall()
        array, problem = to_arrow(rows, want_type)
        if problem:
            findings.error(f"colonne {name} : {problem}")
            skip.add(name)
            columns[name] = pa.nulls(0)
            continue
        columns[name] = array
    n = con.execute(f'SELECT count(*) FROM "{layer}"').fetchone()[0]
    columns = {k: (v if len(v) == n else pa.nulls(n)) for k, v in columns.items()}
    # Le nombre d'entités est compté ici : une couche sans attribut a des lignes.
    tables.check_table({**schema, "x-allow-empty": True}, pa.table(columns), findings,
                       skip=skip)
    if n == 0 and not schema.get("x-allow-empty", False):
        findings.error(f"couche {layer} vide : au moins une entité attendue")
    if crs_ok:
        check_geometries(con, layer, geom_col, findings)


def to_arrow(rows, ts_type):
    """Valeurs SQLite vers un tableau Arrow typé ; (tableau, None) ou (None, problème)."""
    values = []
    for i, (value, storage) in enumerate(rows, start=1):
        if value is None:
            values.append(None)
            continue
        if ts_type == "string" and storage != "text":
            return None, f"valeur stockée en {storage} à la ligne {i}, chaîne attendue"
        if ts_type == "integer" and storage != "integer":
            return None, f"valeur stockée en {storage} à la ligne {i}, entier attendu"
        if ts_type == "number":
            if storage not in ("real", "integer"):
                return None, f"valeur stockée en {storage} à la ligne {i}, nombre attendu"
            value = float(value)
        if ts_type == "boolean":
            if storage != "integer" or value not in (0, 1):
                return None, f"valeur {value!r} à la ligne {i}, booléen 0 ou 1 attendu"
            value = bool(value)
        if ts_type == "date":
            try:
                value = datetime.date.fromisoformat(value)
            except (TypeError, ValueError):
                return None, f"valeur {value!r} à la ligne {i}, date AAAA-MM-JJ attendue"
        values.append(value)
    arrow_type = {"string": pa.string(), "integer": pa.int64(), "number": pa.float64(),
                  "boolean": pa.bool_(), "date": pa.date32()}[ts_type]
    return pa.array(values, type=arrow_type), None


def check_geometries(con, layer, geom_col, findings):
    rows = con.execute(f'SELECT "{geom_col}" FROM "{layer}" ORDER BY rowid').fetchall()
    for i, (blob,) in enumerate(rows, start=1):
        if blob is None:
            findings.error(f"entité {i} : géométrie absente")
            return
        try:
            bounds = gpkg_blob_bounds(bytes(blob))
        except (ValueError, struct.error):
            findings.error(f"entité {i} : géométrie illisible (en-tête GeoPackage ou WKB)")
            return
        if bounds is None:
            findings.error(f"entité {i} : géométrie vide")
            return
        problem = extent.bounds_problem(*bounds)
        if problem:
            findings.error(f"entité {i} : {problem}")
            return


def gpkg_blob_bounds(blob):
    """(x_min, y_min, x_max, y_max) d'une géométrie GeoPackage, None si elle est vide."""
    if blob[:2] != b"GP":
        raise ValueError("en-tête GP absent")
    flags = blob[3]
    if flags & 0b10000:
        return None
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 0b111]
    coords = []
    wkb_coords(blob, 8 + envelope, coords)
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def wkb_coords(buf, pos, out):
    """Lit une géométrie WKB (ISO ou EWKB) à `pos`, ajoute ses (x, y) à `out`."""
    order = "<" if buf[pos] == 1 else ">"
    (code,) = struct.unpack_from(order + "I", buf, pos + 1)
    pos += 5
    dims = 2
    if code & 0x20000000:  # EWKB avec SRID
        pos += 4
    if code & 0x80000000:
        dims += 1
    if code & 0x40000000:
        dims += 1
    code &= 0x0FFFFFFF
    kind, iso = code % 1000, code // 1000
    dims += {0: 0, 1: 1, 2: 1, 3: 2}[iso]
    point = struct.Struct(order + "d" * dims)

    def read_points(p):
        (n,) = struct.unpack_from(order + "I", buf, p)
        p += 4
        for _ in range(n):
            out.append(point.unpack_from(buf, p)[:2])
            p += point.size
        return p

    if kind == 1:
        out.append(point.unpack_from(buf, pos)[:2])
        return pos + point.size
    if kind == 2:
        return read_points(pos)
    if kind == 3:
        (rings,) = struct.unpack_from(order + "I", buf, pos)
        pos += 4
        for _ in range(rings):
            pos = read_points(pos)
        return pos
    if kind in (4, 5, 6, 7):
        (parts,) = struct.unpack_from(order + "I", buf, pos)
        pos += 4
        for _ in range(parts):
            pos = wkb_coords(buf, pos, out)
        return pos
    raise ValueError(f"type WKB {kind} non pris en charge")
