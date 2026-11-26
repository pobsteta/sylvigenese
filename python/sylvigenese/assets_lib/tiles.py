"""Tuiles 3D Tiles 1.1 : un `tileset.json` par année (état initial ou année simulée retenue), un
contenu .gltf par tuile.

Étape du BRIEF codée : spec §9 (3D Tiles 1.1 avec instanciation ; une tuile par année retenue) ;
ADR 0002 ; référentiel `docs/referentiels/itowns-instancing.md` (contenu en `.gltf` et non `.glb`,
point A ; `EXT_mesh_gpu_instancing` lue par three). Missions 028 (état initial) et 047 (sim/).

- Découpage : carrés de `TUILE_M` mètres alignés sur des multiples de `TUILE_M` en EPSG:2154 ;
  seules les tuiles qui portent des arbres existent. Nom : `t_<x_ouest>_<y_sud>`.
- Chaque tuile a son `transform` (repère est-nord-haut local, voir `frame.py`) et une
  `boundingVolume` en `box` dans ce repère, qui contient les arbres, houppiers compris.
- La racine n'a pas de contenu ; sa `boundingVolume` est une `region` (longitude, latitude,
  hauteur) qui contient toutes les tuiles. Pas de niveaux de détail en v1 : `refine: ADD`,
  erreur géométrique 0 pour les tuiles de contenu.
- Contenu : un nœud glTF par modèle employé (un modèle par essence et stade du générateur, ou le modèle générique
  du groupe, Q3), avec `EXT_mesh_gpu_instancing` (TRANSLATION, SCALE). Une instance par arbre : translation = pied
  de l'arbre, échelle = (r / r_ref, h / h_ref, r / r_ref) du modèle (mission 070 ; (r, h, r) pour un générique,
  qui mesure 1 m sur 1 m). Le maillage de chaque nœud est le niveau LOD2 du `.glb` du même modèle : les MÊMES
  sommets (plan T1), écrits par la même fonction (`models.add_level_mesh`). Les niveaux LOD0 et LOD1 ne servent
  qu'à la vue Godot : iTowns lit LOD2.
- Rayon r : état initial, disque de même surface que `crown_area` ; années simulées (mission 047,
  plan T4), r = cw / 2 de `sim/trees`, t0 compris. `etat` des extras : `initial` ou `simulé`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from sylvigenese.assets_lib import models
from sylvigenese.assets_lib.frame import LocalFrame, local_to_gltf

TILE_M = 500
FLOAT_COMPONENT = 5126


def tile_name(x_west: int, y_south: int) -> str:
    return f"t_{x_west}_{y_south}"


def tile_corner(x: np.ndarray, y: np.ndarray, size: int = TILE_M) -> tuple[np.ndarray, np.ndarray]:
    """Coin sud-ouest (entiers, EPSG:2154) de la tuile de chaque point."""
    return (np.floor(np.asarray(x) / size).astype("int64") * size,
            np.floor(np.asarray(y) / size).astype("int64") * size)


def crown_radius(crown_area: np.ndarray) -> np.ndarray:
    """Rayon (m) du disque de même surface que le houppier projeté."""
    return np.sqrt(np.asarray(crown_area, dtype="float64") / math.pi)


def build_tile(x_west: int, y_south: int, trees: dict[str, np.ndarray], z_ellipsoid: np.ndarray,
                     groups: np.ndarray, size: int = TILE_M, radius: np.ndarray | None = None) -> dict:
    """Prépare une tuile : repère local, positions et échelles par groupe, volume englobant.

    `trees` ne contient que les arbres de la tuile ; `z_ellipsoid` : hauteur ellipsoïdale du pied ;
    `groups` : nom du modèle de chaque arbre (`<espar>_<stade>` ou `generique_<groupe>`, sans .glb) ;
    `radius` : rayon du houppier (m) ; sans lui, celui du disque de surface `crown_area`.
    """
    xc, yc = x_west + size / 2.0, y_south + size / 2.0
    zc = round(float(np.mean(z_ellipsoid)), 3)
    frame = LocalFrame(xc, yc, zc)
    enu = frame.lambert_to_local(trees["x"], trees["y"], z_ellipsoid)
    r = crown_radius(trees["crown_area"]) if radius is None else np.asarray(radius, dtype="float64")
    h = np.asarray(trees["h"], dtype="float64")
    min_corner = np.array([(enu[:, 0] - r).min(), (enu[:, 1] - r).min(), enu[:, 2].min()])
    max_corner = np.array([(enu[:, 0] + r).max(), (enu[:, 1] + r).max(), (enu[:, 2] + h).max()])
    center, half = (min_corner + max_corner) / 2.0, (max_corner - min_corner) / 2.0
    return {"name": tile_name(x_west, y_south), "frame": frame, "enu": enu, "r": r, "h": h,
            "groups": groups, "box": (center, half), "n": int(len(h))}


def write_content(directory: Path, tile: dict, year: int, registry: models.ModelRegistry, state: str = "initial") -> Path:
    """Écrit `<tuile>.gltf` et `<tuile>.bin` ; rend le chemin du .gltf.

    Un nœud par modèle employé, dans l'ordre des noms ; son maillage est le LOD2 du `.glb` du modèle."""
    name = tile["name"]
    doc, buffer = models.empty_document(f"{name}.bin"), models.Buffer()
    gltf = local_to_gltf(tile["enu"]).astype("float32")
    stems = np.asarray(tile["groups"])
    h_ref, r_ref = registry.scale(stems)
    scale = np.column_stack([tile["r"] / r_ref, tile["h"] / h_ref, tile["r"] / r_ref]).astype("float32")
    used = sorted(set(stems.tolist()))
    for stem in used:
        selected = stems == stem
        model = registry.model(stem)
        mesh = models.add_level_mesh(buffer, doc, model.levels[2], models.add_materials(doc, model), stem)
        a_t = buffer.add(gltf[selected], None, "VEC3", FLOAT_COMPONENT)
        a_s = buffer.add(scale[selected], None, "VEC3", FLOAT_COMPONENT)
        doc["nodes"].append({"name": stem, "mesh": mesh,
                             "extensions": {"EXT_mesh_gpu_instancing": {"attributes": {"TRANSLATION": a_t, "SCALE": a_s}}},
                             "extras": {"instances": int(selected.sum()), "modele": stem, "niveau_de_detail": "LOD2"}})
        doc["scenes"][0]["nodes"].append(len(doc["nodes"]) - 1)
    doc["extensionsUsed"] = doc["extensionsRequired"] = ["EXT_mesh_gpu_instancing"]
    # `generique` et `provisoire` sont exigés par le contrat assets.gltf (illustration provisoire) ; les modèles
    # réellement employés sont dits dans `modeles`.
    doc["extras"] = {"generique": True, "provisoire": True, "annee": year, "etat": state, "tuile": name,
                     "modeles": used,
                     "echelle": "instance mise à l'échelle (rayon du houppier / r_ref, hauteur / h_ref, rayon / r_ref) "
                                "du modèle ; générique : (r, h, r)",
                     "repere": "glTF Y haut ; local est-nord-haut (e, n, u) -> (e, u, -n) ; origine et orientation : transform de la tuile dans tileset.json",
                     "instances": tile["n"]}
    path = directory / f"{name}.gltf"
    models.write_gltf(path, doc, models.finalize(doc, buffer))
    return path


def root_region(tiles: list[dict], margin_m: float = 1.0) -> list[float]:
    """`region` 3D Tiles [ouest, sud, est, nord, hauteur min, hauteur max] (radians, mètres) qui contient toutes les tuiles."""
    from sylvigenese.assets_lib.frame import ECEF, WGS84
    from rasterio.warp import transform as warp_transform
    coins = []
    for t in tiles:
        center, half = t["box"]
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    local = center + np.array([sx, sy, sz]) * (half + margin_m)
                    coins.append(t["frame"].origin + t["frame"].axes @ local)
    coins = np.array(coins)
    lon, lat, height = warp_transform(ECEF, WGS84, coins[:, 0].tolist(), coins[:, 1].tolist(), coins[:, 2].tolist())
    lon, lat, height = (np.array(v) for v in (lon, lat, height))
    return [float(np.radians(lon.min())), float(np.radians(lat.min())), float(np.radians(lon.max())),
            float(np.radians(lat.max())), float(height.min()), float(height.max())]


def write_tileset(directory: Path, tiles: list[dict], year: int, extras: dict) -> Path:
    """Écrit `tileset.json` (3D Tiles 1.1) ; chaque tuile a déjà son contenu .gltf."""
    extent = root_region(tiles)
    children = []
    for t in tiles:
        center, half = t["box"]
        children.append({
            "transform": t["frame"].transform_3dtiles(),
            "boundingVolume": {"box": [float(center[0]), float(center[1]), float(center[2]),
                                       float(half[0]), 0.0, 0.0, 0.0, float(half[1]), 0.0, 0.0, 0.0, float(half[2])]},
            "geometricError": 0.0,
            "refine": "ADD",
            "content": {"uri": f"{t['name']}.gltf"},
            "extras": {"tile": t["name"], "instances": t["n"]},
        })
    diag = max(2.0 * float(np.linalg.norm(t["box"][1])) for t in tiles)
    doc = {
        "asset": {"version": "1.1", "tilesetVersion": str(year)},
        "geometricError": round(diag * 2.0, 3),
        "root": {"boundingVolume": {"region": extent}, "geometricError": round(diag * 2.0, 3),
                 "refine": "ADD", "children": children},
        "extras": extras,
    }
    path = directory / "tileset.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path
