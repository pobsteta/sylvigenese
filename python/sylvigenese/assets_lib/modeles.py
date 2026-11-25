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

GROUPES = ("feuillu", "resineux")
COULEURS = {"feuillu": [0.30, 0.52, 0.22, 1.0], "resineux": [0.10, 0.34, 0.22, 1.0]}
COULEUR_TRONC = [0.38, 0.27, 0.17, 1.0]
EXTRAS_GENERIQUE = {
    "generique": True,
    "provisoire": True,
    "remplace_en": "M6 (arbres du générateur)",
    "echelle": "hauteur 1 m, rayon de houppier 1 m ; instancié en (r, h, r)",
}


def _anneau(rayon: float, y: float, n: int) -> list[list[float]]:
    return [[rayon * math.cos(2 * math.pi * i / n), y, rayon * math.sin(2 * math.pi * i / n)] for i in range(n)]


def _normales_plates(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Normales lissées : somme des normales de faces par sommet."""
    normales = np.zeros_like(positions)
    for a, b, c in indices.reshape(-1, 3):
        n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
        normales[[a, b, c]] += n
    longueur = np.linalg.norm(normales, axis=1, keepdims=True)
    longueur[longueur == 0] = 1.0
    return normales / longueur


def _tronc(n: int = 6, rayon: float = 0.05, haut: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    bas, sommet = _anneau(rayon, 0.0, n), _anneau(rayon, haut, n)
    positions = np.array(bas + sommet, dtype="float32")
    indices = []
    for i in range(n):
        j = (i + 1) % n
        indices += [i, n + i, j, j, n + i, n + j]  # côté, vers l'extérieur
    return positions, np.array(indices, dtype="uint16")


def _houppier_feuillu(n: int = 8, niveaux: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Ellipsoïde bas : de y = 0,3 à y = 1, rayon 1 à l'équateur."""
    centre, demi = 0.65, 0.35
    pts = [[0.0, centre - demi, 0.0]]
    for k in range(1, niveaux):
        phi = -math.pi / 2 + math.pi * k / niveaux
        pts += [[math.cos(phi) * math.cos(2 * math.pi * i / n), centre + demi * math.sin(phi),
                 math.cos(phi) * math.sin(2 * math.pi * i / n)] for i in range(n)]
    pts.append([0.0, centre + demi, 0.0])
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):  # calotte basse
        idx += [0, 1 + (i + 1) % n, 1 + i]
    for k in range(niveaux - 2):
        a, b = 1 + k * n, 1 + (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            idx += [a + i, a + j, b + i, a + j, b + j, b + i]
    dernier = 1 + (niveaux - 2) * n
    haut = len(pts) - 1
    for i in range(n):
        idx += [haut, dernier + i, dernier + (i + 1) % n]
    return positions, np.array(idx, dtype="uint16")


def _houppier_resineux(n: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Cône : de y = 0,15 (rayon 1) à y = 1 (pointe)."""
    pts = _anneau(1.0, 0.15, n) + [[0.0, 0.15, 0.0], [0.0, 1.0, 0.0]]
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [i, n + 1, j]  # côté
        idx += [i, j, n]  # dessous
    return positions, np.array(idx, dtype="uint16")


def geometrie(groupe: str) -> list[tuple[np.ndarray, np.ndarray, list[float], str]]:
    """Primitives du modèle : (positions, indices, couleur, nom)."""
    if groupe not in GROUPES:
        raise ValueError(f"groupe d'essences inconnu : {groupe!r} (attendu : {', '.join(GROUPES)})")
    houppier = _houppier_feuillu() if groupe == "feuillu" else _houppier_resineux()
    return [(*_tronc(), COULEUR_TRONC, "tronc"), (*houppier, COULEURS[groupe], "houppier")]


class Tampon:
    """Construit un .bin : ajoute des blocs alignés sur 4 octets, rend les bufferViews."""

    def __init__(self):
        self.donnees = bytearray()
        self.vues: list[dict] = []
        self.accesseurs: list[dict] = []

    def ajouter(self, tableau: np.ndarray, cible: int | None, type_: str, type_composant: int, avec_min_max: bool = False) -> int:
        while len(self.donnees) % 4:
            self.donnees.append(0)
        brut = np.ascontiguousarray(tableau).tobytes()
        vue = {"buffer": 0, "byteOffset": len(self.donnees), "byteLength": len(brut)}
        if cible:
            vue["target"] = cible
        self.donnees += brut
        self.vues.append(vue)
        acc = {"bufferView": len(self.vues) - 1, "componentType": type_composant, "count": int(tableau.shape[0]), "type": type_}
        if avec_min_max:
            acc["min"] = [float(v) for v in tableau.min(axis=0)]
            acc["max"] = [float(v) for v in tableau.max(axis=0)]
        self.accesseurs.append(acc)
        return len(self.accesseurs) - 1


def ajouter_maillage(tampon: Tampon, doc: dict, groupe: str, nom: str) -> int:
    """Ajoute le maillage du groupe (matériaux, accesseurs) à `doc` et rend son indice."""
    primitives = []
    for positions, indices, couleur, nom_prim in geometrie(groupe):
        normales = _normales_plates(positions.astype("float64"), indices).astype("float32")
        a_pos = tampon.ajouter(positions, 34962, "VEC3", 5126, avec_min_max=True)
        a_nor = tampon.ajouter(normales, 34962, "VEC3", 5126)
        a_idx = tampon.ajouter(indices.astype("uint16"), 34963, "SCALAR", 5123)
        doc["materials"].append({"name": f"{groupe}_{nom_prim}", "doubleSided": True,
                                 "pbrMetallicRoughness": {"baseColorFactor": couleur, "metallicFactor": 0.0, "roughnessFactor": 1.0}})
        primitives.append({"attributes": {"POSITION": a_pos, "NORMAL": a_nor}, "indices": a_idx,
                           "material": len(doc["materials"]) - 1, "mode": 4})
    doc["meshes"].append({"name": nom, "primitives": primitives, "extras": dict(EXTRAS_GENERIQUE, groupe=groupe)})
    return len(doc["meshes"]) - 1


def document_vide(nom_bin: str) -> dict:
    return {"asset": {"version": "2.0", "generator": "sylvigenese assets (mission 028)"},
            "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [],
            "buffers": [{"uri": nom_bin, "byteLength": 0}], "bufferViews": [], "accessors": []}


def finaliser(doc: dict, tampon: Tampon) -> bytes:
    """Complète le document avec le tampon ; rend le contenu du .bin (multiple de 4 octets)."""
    while len(tampon.donnees) % 4:
        tampon.donnees.append(0)
    doc["bufferViews"], doc["accessors"] = tampon.vues, tampon.accesseurs
    doc["buffers"][0]["byteLength"] = len(tampon.donnees)
    return bytes(tampon.donnees)


def ecrire_gltf(chemin: Path, doc: dict, binaire: bytes) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.with_suffix(".bin").write_bytes(binaire)
    chemin.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def ecrire_modeles(dossier: Path) -> list[Path]:
    """Écrit `assets/trees/{feuillu,resineux}.gltf` (+ .bin) ; rend les chemins des .gltf."""
    sorties = []
    for groupe in GROUPES:
        chemin = dossier / f"{groupe}.gltf"
        doc, tampon = document_vide(f"{groupe}.bin"), Tampon()
        indice = ajouter_maillage(tampon, doc, groupe, groupe)
        doc["nodes"].append({"name": groupe, "mesh": indice})
        doc["scenes"][0]["nodes"].append(0)
        doc["extras"] = dict(EXTRAS_GENERIQUE, groupe=groupe)
        ecrire_gltf(chemin, doc, finaliser(doc, tampon))
        sorties.append(chemin)
    return sorties
