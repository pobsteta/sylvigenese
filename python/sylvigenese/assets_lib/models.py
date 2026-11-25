"""Modèles d'arbres glTF 2.0 génériques : un par groupe d'essences (feuillu, résineux).

Étape du BRIEF codée : spec §2 (assets) et §9 (glTF 2.0). Mission 028.

GÉNÉRIQUES ET PROVISOIRES (marqués dans `extras`) : tronc + houppier très simples, pas une
essence dessinée. Remplacés en M6 par les arbres du générateur.

Échelle : le modèle mesure 1 m de haut et son houppier a 1 m de rayon (maximum). Le tronc et
le houppier sont étirés ensemble à l'instanciation : échelle (r, h, r) en glTF (x, y, z), avec
r = rayon du houppier déduit de `crown_area` (r = sqrt(crown_area / pi)) et h la hauteur de
l'arbre. Le tronc suit donc le houppier, pas le d130 : c'est un dessin, pas une mesure.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np

GROUPS = ("feuillu", "resineux")
COLORS = {"feuillu": [0.30, 0.52, 0.22, 1.0], "resineux": [0.10, 0.34, 0.22, 1.0]}
TRUNK_COLOR = [0.38, 0.27, 0.17, 1.0]
GENERIC_EXTRAS = {
    "generique": True,
    "provisoire": True,
    "remplace_en": "M6 (arbres du générateur)",
    "echelle": "hauteur 1 m, rayon de houppier 1 m ; instancié en (r, h, r)",
}


def _ring(radius: float, y: float, n: int) -> list[list[float]]:
    return [[radius * math.cos(2 * math.pi * i / n), y, radius * math.sin(2 * math.pi * i / n)] for i in range(n)]


def _vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Normales lissées : somme des normales de faces par sommet."""
    normals = np.zeros_like(positions)
    for a, b, c in indices.reshape(-1, 3):
        n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
        normals[[a, b, c]] += n
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    length[length == 0] = 1.0
    return normals / length


def _trunk(n: int = 6, radius: float = 0.05, trunk_height: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    bottom_ring, top_ring = _ring(radius, 0.0, n), _ring(radius, trunk_height, n)
    positions = np.array(bottom_ring + top_ring, dtype="float32")
    indices = []
    for i in range(n):
        j = (i + 1) % n
        indices += [i, n + i, j, j, n + i, n + j]  # côté, vers l'extérieur
    return positions, np.array(indices, dtype="uint16")


def _broadleaf_crown(n: int = 8, levels: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Ellipsoïde bas : de y = 0,3 à y = 1, rayon 1 à l'équateur."""
    center, half = 0.65, 0.35
    pts = [[0.0, center - half, 0.0]]
    for k in range(1, levels):
        phi = -math.pi / 2 + math.pi * k / levels
        pts += [[math.cos(phi) * math.cos(2 * math.pi * i / n), center + half * math.sin(phi),
                 math.cos(phi) * math.sin(2 * math.pi * i / n)] for i in range(n)]
    pts.append([0.0, center + half, 0.0])
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):  # calotte basse
        idx += [0, 1 + (i + 1) % n, 1 + i]
    for k in range(levels - 2):
        a, b = 1 + k * n, 1 + (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            idx += [a + i, a + j, b + i, a + j, b + j, b + i]
    last = 1 + (levels - 2) * n
    top = len(pts) - 1
    for i in range(n):
        idx += [top, last + i, last + (i + 1) % n]
    return positions, np.array(idx, dtype="uint16")


def _conifer_crown(n: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Cône : de y = 0,15 (rayon 1) à y = 1 (pointe)."""
    pts = _ring(1.0, 0.15, n) + [[0.0, 0.15, 0.0], [0.0, 1.0, 0.0]]
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [i, n + 1, j]  # côté
        idx += [i, j, n]  # dessous
    return positions, np.array(idx, dtype="uint16")


def geometry(group: str) -> list[tuple[np.ndarray, np.ndarray, list[float], str]]:
    """Primitives du modèle : (positions, indices, couleur, nom)."""
    if group not in GROUPS:
        raise ValueError(f"groupe d'essences inconnu : {group!r} (attendu : {', '.join(GROUPS)})")
    crown = _broadleaf_crown() if group == "feuillu" else _conifer_crown()
    return [(*_trunk(), TRUNK_COLOR, "tronc"), (*crown, COLORS[group], "houppier")]


class Buffer:
    """Construit un .bin : ajoute des blocs alignés sur 4 octets, rend les bufferViews."""

    def __init__(self):
        self.data = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def add(self, array: np.ndarray, target: int | None, type_: str, component_type: int, with_min_max: bool = False) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        raw = np.ascontiguousarray(array).tobytes()
        view = {"buffer": 0, "byteOffset": len(self.data), "byteLength": len(raw)}
        if target:
            view["target"] = target
        self.data += raw
        self.views.append(view)
        acc = {"bufferView": len(self.views) - 1, "componentType": component_type, "count": int(array.shape[0]), "type": type_}
        if with_min_max:
            acc["min"] = [float(v) for v in array.min(axis=0)]
            acc["max"] = [float(v) for v in array.max(axis=0)]
        self.accessors.append(acc)
        return len(self.accessors) - 1


def add_mesh(buffer: Buffer, doc: dict, group: str, name: str) -> int:
    """Ajoute le maillage du groupe (matériaux, accesseurs) à `doc` et rend son indice."""
    primitives = []
    for positions, indices, color, primitive_name in geometry(group):
        normals = _vertex_normals(positions.astype("float64"), indices).astype("float32")
        a_pos = buffer.add(positions, 34962, "VEC3", 5126, with_min_max=True)
        a_nor = buffer.add(normals, 34962, "VEC3", 5126)
        a_idx = buffer.add(indices.astype("uint16"), 34963, "SCALAR", 5123)
        doc["materials"].append({"name": f"{group}_{primitive_name}", "doubleSided": True,
                                 "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0.0, "roughnessFactor": 1.0}})
        primitives.append({"attributes": {"POSITION": a_pos, "NORMAL": a_nor}, "indices": a_idx,
                           "material": len(doc["materials"]) - 1, "mode": 4})
    doc["meshes"].append({"name": name, "primitives": primitives, "extras": {**GENERIC_EXTRAS, "groupe": group}})
    return len(doc["meshes"]) - 1


def empty_document(bin_name: str) -> dict:
    return {"asset": {"version": "2.0", "generator": "sylvigenese assets (mission 028)"},
            "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [],
            "buffers": [{"uri": bin_name, "byteLength": 0}], "bufferViews": [], "accessors": []}


def finalize(doc: dict, buffer: Buffer) -> bytes:
    """Complète le document avec le tampon ; rend le contenu du .bin (multiple de 4 octets)."""
    while len(buffer.data) % 4:
        buffer.data.append(0)
    doc["bufferViews"], doc["accessors"] = buffer.views, buffer.accessors
    doc["buffers"][0]["byteLength"] = len(buffer.data)
    return bytes(buffer.data)


def write_gltf(path: Path, doc: dict, binary: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".bin").write_bytes(binary)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_models(directory: Path) -> list[Path]:
    """Écrit `assets/trees/{feuillu,resineux}.gltf` (+ .bin) ; rend les chemins des .gltf."""
    outputs = []
    for group in GROUPS:
        path = directory / f"{group}.gltf"
        doc, buffer = empty_document(f"{group}.bin"), Buffer()
        index = add_mesh(buffer, doc, group, group)
        doc["nodes"].append({"name": group, "mesh": index})
        doc["scenes"][0]["nodes"].append(0)
        doc["extras"] = {**GENERIC_EXTRAS, "groupe": group}
        write_gltf(path, doc, finalize(doc, buffer))
        outputs.append(path)
    return outputs
