"""Modèles d'arbres glTF binaires (`assets/trees/*.glb`, BRIEF §4, spec §9, mission 068, ADR 0007 projet).

Le fichier est lu en entier (en-tête, bloc JSON, bloc binaire) et refusé s'il est tronqué.
Règles, dans l'ordre où le message les dit :
- conteneur : version 2, longueur déclarée = longueur du fichier, blocs entiers, bloc JSON
  puis bloc binaire qui couvre `buffers[0].byteLength` ;
- accesseurs : vues et accesseurs dans le tampon, `POSITION` avec `min` et `max` qui bornent les
  sommets, sommets finis, indices dans le maillage ;
- trois niveaux de détail par l'extension `MSFT_lod` (T2) : un seul nœud principal (LOD0), deux
  nœuds `ids` plus grossiers (LOD1 puis LOD2), chacun avec un maillage, triangles strictement
  décroissants, `extras.MSFT_screencoverage` de trois nombres décroissants ; `MSFT_lod` est dans
  `extensionsUsed` ;
- repère y-up (T6) : la base du LOD0 est en y = 0 et son sommet en y = `H_ref_m`, à 1 % près ;
- `extras` : schéma `json/tree_model_extras.schema.json` (`source_commit` obligatoire pour un modèle
  du générateur) ;
- nom `<espar>_<stade>.glb`, ou `generique_<groupe>.glb` (repli signalé, Q3) ; le code espar est
  celui de `contracts/species.csv`, avec un modèle propre (`tarif_nemeton_code` non vide) ; **un
  code qui en partage un autre est un alias** et n'a pas de fichier propre (pas de doublon, M2) ;
  `extras` redit l'essence, le stade et l'essence du générateur du nom.

Le glTF-Validator de Khronos n'est pas appelé ici : il s'ajoute au job `m6` de la CI (plan T4).
"""
import array
import csv
import json
import math
import re
import struct
from pathlib import Path

from . import json_docs
from .report import Findings

CONTRACTS_DIR = Path(__file__).resolve().parent.parent
GLB_MAGIC = 0x46546C67  # « glTF »
CHUNK_JSON = 0x4E4F534A  # « JSON »
CHUNK_BIN = 0x004E4942  # « BIN »
ESPAR = re.compile(r"^[0-9]{2}[A-Z0-9]{0,3}$")
GENERIC_NAME = re.compile(r"^generique_(feuillu|resineux)$")
COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
TRIANGLES = 4  # mode de primitive glTF
H_REF_TOLERANCE = 0.01  # étendue en +Y du LOD0 = H_ref_m, à 1 % (plan T6)


def stages():
    with open(CONTRACTS_DIR / "json" / "enums" / "stage.json", encoding="utf-8") as f:
        return json.load(f)["enum"]


def species_rows():
    """Lignes de contracts/species.csv, dans l'ordre du fichier."""
    with open(CONTRACTS_DIR / "species.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def model_owner(espar):
    """(essence du générateur, code espar qui porte le fichier) d'un code ; (None, None) sans modèle.

    Deux codes de même `tarif_nemeton_code` sont la même essence : le fichier porte le nom du
    premier code dans l'ordre de species.csv, les autres sont des alias."""
    rows = species_rows()
    mine = next((r for r in rows if r["espar"] == espar), None)
    if mine is None or not mine["tarif_nemeton_code"]:
        return None, None
    essence = mine["tarif_nemeton_code"]
    owner = next(r["espar"] for r in rows if r["tarif_nemeton_code"] == essence)
    return essence, owner


def check(path, options):
    findings = Findings()
    data = Path(path).read_bytes()
    gltf, binary = read_container(data, findings)
    if gltf is None:
        return [(path, findings)]
    check_buffers(gltf, binary, findings)
    positions = check_accessors(gltf, binary, findings)
    check_levels(gltf, positions, findings)
    check_extras(gltf, findings)
    if options.get("name_rule") == "species_stage":
        check_name(Path(path).stem, gltf, findings)
    return [(path, findings)]


# ----------------------------------------------------------------------- conteneur

def read_container(data, findings):
    """(JSON, octets du bloc binaire) ; (None, None) si le fichier est illisible."""
    if len(data) < 20:
        findings.error("fichier GLB illisible : trop court pour un en-tête glTF")
        return None, None
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        findings.error("fichier GLB illisible : nombre magique « glTF » absent")
        return None, None
    if version != 2:
        findings.error(f"conteneur GLB version {version}, version 2 attendue")
    if length != len(data):
        findings.error(f"longueur déclarée {length} octets, fichier de {len(data)} octets "
                       f"(fichier tronqué ou rallongé)")
    chunks, offset = [], 12
    while offset + 8 <= len(data):
        size, kind = struct.unpack_from("<II", data, offset)
        if offset + 8 + size > len(data):
            findings.error(f"bloc {kind:#x} tronqué : {size} octets déclarés, "
                           f"{len(data) - offset - 8} présents")
            return None, None
        chunks.append((kind, data[offset + 8: offset + 8 + size]))
        offset += 8 + size
    if not chunks or chunks[0][0] != CHUNK_JSON:
        findings.error("premier bloc du GLB : bloc JSON attendu")
        return None, None
    try:
        gltf = json.loads(chunks[0][1].decode("utf-8"))
        asset_version = gltf["asset"]["version"]
    except (ValueError, KeyError, TypeError):
        findings.error("bloc JSON du GLB illisible ou sans asset.version")
        return None, None
    if asset_version != "2.0":
        findings.error(f"asset.version = {asset_version!r}, glTF 2.0 attendu")
    binary = next((body for kind, body in chunks[1:] if kind == CHUNK_BIN), None)
    if binary is None:
        findings.error("bloc binaire (BIN) absent : les sommets et les indices y sont écrits")
        return None, None
    return gltf, binary


def check_buffers(gltf, binary, findings):
    buffers = gltf.get("buffers")
    if not isinstance(buffers, list) or not buffers:
        findings.error("clé obligatoire absente : buffers")
        return
    first = buffers[0]
    if "uri" in first:
        findings.error("buffers[0].uri : un GLB range son tampon dans le bloc BIN, sans uri")
    size = first.get("byteLength")
    if not isinstance(size, int) or size < 1:
        findings.error("buffers[0].byteLength : entier positif attendu")
    elif size > len(binary):
        findings.error(f"buffers[0].byteLength = {size} dépasse le bloc BIN ({len(binary)} octets) : "
                       f"fichier tronqué")


# ---------------------------------------------------------------------- accesseurs

def check_accessors(gltf, binary, findings):
    """Contrôle les accesseurs ; rend {indice d'accesseur POSITION: (min, max) réels}."""
    views, accessors = gltf.get("bufferViews"), gltf.get("accessors")
    if not isinstance(views, list) or not views or not isinstance(accessors, list) or not accessors:
        findings.error("clé obligatoire absente ou vide : bufferViews, accessors")
        return {}
    declared = (gltf.get("buffers") or [{}])[0].get("byteLength")
    limit = min(len(binary), declared) if isinstance(declared, int) else len(binary)
    for i, view in enumerate(views):
        start, size = view.get("byteOffset", 0), view.get("byteLength")
        if view.get("buffer") != 0 or not isinstance(size, int) or size < 1 \
                or not isinstance(start, int) or start < 0 or start + size > limit:
            findings.error(f"bufferViews[{i}] sort du tampon (octets {start} à {start}+{size}, "
                           f"tampon de {limit})")
    position_ids = {p["attributes"]["POSITION"]
                    for m in gltf.get("meshes", []) for p in m.get("primitives", [])
                    if isinstance(p.get("attributes"), dict) and "POSITION" in p["attributes"]}
    bounds = {}
    for i, acc in enumerate(accessors):
        size = accessor_size(i, acc, views, limit, findings)
        if size is None:
            continue
        if i in position_ids:
            bounds[i] = check_positions(i, acc, views, binary, findings)
    check_indices(gltf, accessors, views, binary, findings)
    return bounds


def accessor_size(i, acc, views, limit, findings):
    comp, kind = acc.get("componentType"), acc.get("type")
    count, view_id = acc.get("count"), acc.get("bufferView")
    if comp not in COMPONENT_SIZE or kind not in TYPE_COUNT or not isinstance(count, int) or count < 1:
        findings.error(f"accessors[{i}] : componentType, type ou count invalide")
        return None
    if not isinstance(view_id, int) or not 0 <= view_id < len(views):
        findings.error(f"accessors[{i}].bufferView : vue absente")
        return None
    view = views[view_id]
    stride = view.get("byteStride") or COMPONENT_SIZE[comp] * TYPE_COUNT[kind]
    need = acc.get("byteOffset", 0) + (count - 1) * stride + COMPONENT_SIZE[comp] * TYPE_COUNT[kind]
    if need > view.get("byteLength", 0):
        findings.error(f"accessors[{i}] : {count} éléments demandent {need} octets, la vue "
                       f"bufferViews[{view_id}] en a {view.get('byteLength', 0)}")
        return None
    return need


def read_floats(acc, views, binary, width):
    view = views[acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or 4 * width
    if stride == 4 * width:
        values = array.array("f")
        values.frombytes(binary[start: start + 4 * width * acc["count"]])
        return values
    return [struct.unpack_from("<f", binary, start + k * stride + 4 * j)[0]
            for k in range(acc["count"]) for j in range(width)]


def check_positions(i, acc, views, binary, findings):
    if acc.get("componentType") != 5126 or acc.get("type") != "VEC3":
        findings.error(f"accessors[{i}] (POSITION) : float32 VEC3 attendu")
        return None
    low, high = acc.get("min"), acc.get("max")
    if not (isinstance(low, list) and isinstance(high, list) and len(low) == len(high) == 3):
        findings.error(f"accessors[{i}] (POSITION) : min et max obligatoires (3 nombres)")
        return None
    values = read_floats(acc, views, binary, 3)
    if any(not math.isfinite(v) for v in values):
        findings.error(f"accessors[{i}] (POSITION) : sommet non fini (NaN ou infini)")
        return None
    real_low = [min(values[k::3]) for k in range(3)]
    real_high = [max(values[k::3]) for k in range(3)]
    if any(real_low[k] < low[k] - 1e-4 or real_high[k] > high[k] + 1e-4 for k in range(3)):
        findings.error(f"accessors[{i}] (POSITION) : des sommets sortent de min et max déclarés")
    return real_low, real_high


def check_indices(gltf, accessors, views, binary, findings):
    """Les indices d'une primitive existent dans son maillage."""
    for m, mesh in enumerate(gltf.get("meshes", [])):
        for p, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes") or {}
            if "POSITION" not in attrs:
                findings.error(f"meshes[{m}].primitives[{p}] : attribut POSITION absent")
                continue
            idx = prim.get("indices")
            pos = accessors[attrs["POSITION"]] if attrs["POSITION"] < len(accessors) else None
            if idx is None or pos is None or not 0 <= idx < len(accessors):
                continue
            acc = accessors[idx]
            if acc.get("componentType") not in (5121, 5123, 5125) or acc.get("type") != "SCALAR":
                findings.error(f"accessors[{idx}] (indices) : entiers non signés SCALAR attendus")
                continue
            if acc["count"] % 3 and prim.get("mode", TRIANGLES) == TRIANGLES:
                findings.error(f"accessors[{idx}] (indices) : {acc['count']} indices, "
                               f"multiple de 3 attendu (triangles)")
            view = views[acc["bufferView"]] if acc.get("bufferView", -1) < len(views) else None
            if view is None or acc["count"] * COMPONENT_SIZE[acc["componentType"]] > view.get("byteLength", 0):
                continue
            code = {5121: "B", 5123: "H", 5125: "I"}[acc["componentType"]]
            start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
            values = struct.unpack_from(f"<{acc['count']}{code}", binary, start)
            if values and max(values) >= pos["count"]:
                findings.error(f"accessors[{idx}] (indices) : l'indice {max(values)} dépasse les "
                               f"{pos['count']} sommets du maillage")


# ------------------------------------------------------------ niveaux de détail

def triangle_count(gltf, node):
    mesh = node.get("mesh")
    meshes = gltf.get("meshes", [])
    if not isinstance(mesh, int) or not 0 <= mesh < len(meshes):
        return None
    total = 0
    for prim in meshes[mesh].get("primitives", []):
        idx = prim.get("indices")
        accessors = gltf.get("accessors", [])
        if idx is None or not 0 <= idx < len(accessors):
            return None
        total += accessors[idx]["count"] // 3
    return total


def mesh_bounds(gltf, node, positions):
    """(min, max) des sommets du maillage d'un nœud, ou None."""
    mesh = node.get("mesh")
    if not isinstance(mesh, int) or not 0 <= mesh < len(gltf.get("meshes", [])):
        return None
    lows, highs = [], []
    for prim in gltf["meshes"][mesh].get("primitives", []):
        found = positions.get((prim.get("attributes") or {}).get("POSITION"))
        if found:
            lows.append(found[0])
            highs.append(found[1])
    if not lows:
        return None
    return [min(v[k] for v in lows) for k in range(3)], [max(v[k] for v in highs) for k in range(3)]


def check_levels(gltf, positions, findings):
    nodes = gltf.get("nodes")
    if not isinstance(nodes, list) or not nodes or not gltf.get("scenes"):
        findings.error("clé obligatoire absente ou vide : nodes, scenes")
        return
    if "MSFT_lod" not in (gltf.get("extensionsUsed") or []):
        findings.error("extension MSFT_lod absente de extensionsUsed : trois niveaux de détail "
                       "attendus par MSFT_lod (plan T2)")
    leaders = [i for i, n in enumerate(nodes)
               if isinstance((n.get("extensions") or {}).get("MSFT_lod"), dict)]
    if len(leaders) != 1:
        findings.error(f"MSFT_lod : un seul nœud principal (LOD0) attendu, {len(leaders)} trouvés")
        return
    top = nodes[leaders[0]]
    ids = top["extensions"]["MSFT_lod"].get("ids")
    if not (isinstance(ids, list) and len(ids) == 2 and all(isinstance(k, int) for k in ids)):
        findings.error("MSFT_lod.ids : deux nœuds (LOD1 puis LOD2) attendus ; il manque un niveau de détail "
                       "(nœud LOD2 absent ou ids incomplets)")
        return
    if len(set(ids) | {leaders[0]}) != 3 or any(not 0 <= k < len(nodes) for k in ids):
        findings.error("MSFT_lod.ids : deux nœuds distincts du nœud principal, présents dans nodes")
        return
    levels = [top] + [nodes[k] for k in ids]
    counts = [triangle_count(gltf, n) for n in levels]
    for name, n, c in zip(("LOD0", "LOD1", "LOD2"), levels, counts):
        if c is None or c < 1:
            findings.error(f"niveau {name} : un maillage indexé avec au moins un triangle est attendu")
    if all(c for c in counts) and not counts[0] > counts[1] > counts[2]:
        findings.error(f"triangles par niveau {counts[0]}, {counts[1]}, {counts[2]} : "
                       f"strictement décroissants attendus (LOD0 > LOD1 > LOD2)")
    cover = (top.get("extras") or {}).get("MSFT_screencoverage")
    ok = (isinstance(cover, list) and len(cover) == 3
          and all(isinstance(c, (int, float)) and not isinstance(c, bool) and 0 < c <= 1 for c in cover)
          and cover[0] > cover[1] > cover[2])
    if not ok:
        findings.error("extras.MSFT_screencoverage du nœud principal : trois nombres de ]0 ; 1] "
                       "strictement décroissants attendus (un par niveau)")
    check_up_axis(gltf, top, positions, findings)


def check_up_axis(gltf, top, positions, findings):
    """Repère y-up : base du LOD0 en y = 0, sommet en y = H_ref_m, à 1 % près (plan T6)."""
    h_ref = (gltf.get("extras") or {}).get("H_ref_m")
    box = mesh_bounds(gltf, top, positions)
    if box is None or not isinstance(h_ref, (int, float)) or isinstance(h_ref, bool) or h_ref <= 0:
        return
    if any(k in top for k in ("matrix", "translation", "rotation", "scale")):
        findings.error("nœud LOD0 : aucune transformation attendue (repère y-up écrit dans les sommets)")
        return
    low, high = box[0][1], box[1][1]
    tol = H_REF_TOLERANCE * h_ref
    if abs(low) > tol or abs(high - h_ref) > tol:
        findings.error(f"repère y-up : le LOD0 va de y = {low:.3f} à y = {high:.3f} m, attendu de 0 à "
                       f"H_ref_m = {h_ref} m (à 1 % près) ; repère du générateur z-up converti ? (T6)")


# ------------------------------------------------------------------------ extras

def extras_validator():
    with open(CONTRACTS_DIR / "json" / "tree_model_extras.schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    return json_docs.Validator(schema, registry=json_docs.registry())


def check_extras(gltf, findings):
    probe = {"extras": gltf.get("extras")}
    if probe["extras"] is None:
        findings.error("clé obligatoire absente : extras (source_commit, essence, stade, dimensions…)")
        return
    for error in sorted(extras_validator().iter_errors(probe),
                        key=lambda e: list(map(str, e.absolute_path))):
        findings.error(json_docs.translate(error))


def check_name(stem, gltf, findings):
    extras = gltf.get("extras") if isinstance(gltf.get("extras"), dict) else {}
    if GENERIC_NAME.match(stem):
        if extras.get("generique") is not True:
            findings.error(f"{stem}.glb : un modèle générique porte extras.generique = true")
        elif extras.get("groupe") != stem.split("_", 1)[1]:
            findings.error(f"{stem}.glb : extras.groupe = {extras.get('groupe')!r}, "
                           f"{stem.split('_', 1)[1]!r} attendu d'après le nom")
        return
    species, _, stage = stem.rpartition("_")
    allowed = stages()
    if not ESPAR.match(species) or stage not in allowed:
        findings.error(f"nom de fichier {stem}.glb : <species>_<stage>.glb attendu, avec un "
                       f"code espar et un stade parmi {', '.join(allowed)}, ou generique_feuillu / "
                       f"generique_resineux")
        return
    essence, owner = model_owner(species)
    if essence is None:
        findings.error(f"{stem}.glb : le code espar {species} n'a pas de modèle propre (absent de "
                       f"species.csv ou sans tarif_nemeton_code) : pas d'emprunt, utiliser "
                       f"generique_<groupe>.glb")
        return
    if owner != species:
        findings.error(f"{stem}.glb : le code {species} est un alias de {owner} (même essence "
                       f"{essence}) : pas de doublon, le modèle est {owner}_{stage}.glb")
    for key, expected in (("species", species), ("stage", stage), ("essence_generateur", essence)):
        if extras.get(key) != expected:
            findings.error(f"extras.{key} = {extras.get(key)!r}, {expected!r} attendu d'après le nom "
                           f"{stem}.glb et species.csv")
