"""Tuiles 3D Tiles 1.1 de l'état initial : un `tileset.json` par année, un contenu .gltf par tuile.

Étape du BRIEF codée : spec §9 (3D Tiles 1.1 avec instanciation) ; ADR 0002 ; référentiel
`docs/referentiels/itowns-instancing.md` (contenu en `.gltf` et non `.glb`, point A ;
`EXT_mesh_gpu_instancing` lue par three). Mission 028.

- Découpage : carrés de `TUILE_M` mètres alignés sur des multiples de `TUILE_M` en EPSG:2154 ;
  seules les tuiles qui portent des arbres existent. Nom : `t_<x_ouest>_<y_sud>`.
- Chaque tuile a son `transform` (repère est-nord-haut local, voir `repere.py`) et une
  `boundingVolume` en `box` dans ce repère, qui contient les arbres, houppiers compris.
- La racine n'a pas de contenu ; sa `boundingVolume` est une `region` (longitude, latitude,
  hauteur) qui contient toutes les tuiles. Pas de niveaux de détail en v1 : `refine: ADD`,
  erreur géométrique 0 pour les tuiles de contenu.
- Contenu : un nœud glTF par groupe d'essences, avec `EXT_mesh_gpu_instancing` (TRANSLATION,
  SCALE). Une instance par arbre : translation = pied de l'arbre, échelle = (r, h, r).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from sylvigenese.assets_lib import modeles
from sylvigenese.assets_lib.repere import RepereLocal, local_vers_gltf

TUILE_M = 500
COMPOSANT_FLOAT = 5126


def nom_tuile(x_ouest: int, y_sud: int) -> str:
    return f"t_{x_ouest}_{y_sud}"


def coin_tuile(x: np.ndarray, y: np.ndarray, taille: int = TUILE_M) -> tuple[np.ndarray, np.ndarray]:
    """Coin sud-ouest (entiers, EPSG:2154) de la tuile de chaque point."""
    return (np.floor(np.asarray(x) / taille).astype("int64") * taille,
            np.floor(np.asarray(y) / taille).astype("int64") * taille)


def rayon_houppier(crown_area: np.ndarray) -> np.ndarray:
    """Rayon (m) du disque de même surface que le houppier projeté."""
    return np.sqrt(np.asarray(crown_area, dtype="float64") / math.pi)


def construire_tuile(x_ouest: int, y_sud: int, arbres: dict[str, np.ndarray], z_ellips: np.ndarray,
                     groupes: np.ndarray, taille: int = TUILE_M) -> dict:
    """Prépare une tuile : repère local, positions et échelles par groupe, volume englobant.

    `arbres` ne contient que les arbres de la tuile ; `z_ellips` : hauteur ellipsoïdale du pied.
    """
    xc, yc = x_ouest + taille / 2.0, y_sud + taille / 2.0
    zc = round(float(np.mean(z_ellips)), 3)
    repere = RepereLocal(xc, yc, zc)
    enu = repere.lambert_vers_local(arbres["x"], arbres["y"], z_ellips)
    r = rayon_houppier(arbres["crown_area"])
    h = np.asarray(arbres["h"], dtype="float64")
    mini = np.array([(enu[:, 0] - r).min(), (enu[:, 1] - r).min(), enu[:, 2].min()])
    maxi = np.array([(enu[:, 0] + r).max(), (enu[:, 1] + r).max(), (enu[:, 2] + h).max()])
    centre, demi = (mini + maxi) / 2.0, (maxi - mini) / 2.0
    return {"nom": nom_tuile(x_ouest, y_sud), "repere": repere, "enu": enu, "r": r, "h": h,
            "groupes": groupes, "boite": (centre, demi), "n": int(len(h))}


def ecrire_contenu(dossier: Path, tuile: dict, annee: int) -> Path:
    """Écrit `<tuile>.gltf` et `<tuile>.bin` ; rend le chemin du .gltf."""
    nom = tuile["nom"]
    doc, tampon = modeles.document_vide(f"{nom}.bin"), modeles.Tampon()
    gltf = local_vers_gltf(tuile["enu"]).astype("float32")
    echelle = np.column_stack([tuile["r"], tuile["h"], tuile["r"]]).astype("float32")
    for groupe in modeles.GROUPES:
        choix = tuile["groupes"] == groupe
        if not choix.any():
            continue
        maillage = modeles.ajouter_maillage(tampon, doc, groupe, groupe)
        a_t = tampon.ajouter(gltf[choix], None, "VEC3", COMPOSANT_FLOAT)
        a_s = tampon.ajouter(echelle[choix], None, "VEC3", COMPOSANT_FLOAT)
        doc["nodes"].append({"name": f"{groupe}_instances", "mesh": maillage,
                             "extensions": {"EXT_mesh_gpu_instancing": {"attributes": {"TRANSLATION": a_t, "SCALE": a_s}}},
                             "extras": {"instances": int(choix.sum())}})
        doc["scenes"][0]["nodes"].append(len(doc["nodes"]) - 1)
    doc["extensionsUsed"] = doc["extensionsRequired"] = ["EXT_mesh_gpu_instancing"]
    doc["extras"] = dict(modeles.EXTRAS_GENERIQUE, annee=annee, etat="initial", tuile=nom,
                         repere="glTF Y haut ; local est-nord-haut (e, n, u) -> (e, u, -n) ; origine et orientation : transform de la tuile dans tileset.json",
                         instances=tuile["n"])
    chemin = dossier / f"{nom}.gltf"
    modeles.ecrire_gltf(chemin, doc, modeles.finaliser(doc, tampon))
    return chemin


def region_racine(tuiles: list[dict], marge_m: float = 1.0) -> list[float]:
    """`region` 3D Tiles [ouest, sud, est, nord, hauteur min, hauteur max] (radians, mètres) qui contient toutes les tuiles."""
    from sylvigenese.assets_lib.repere import ECEF, WGS84
    from rasterio.warp import transform as warp_transform
    coins = []
    for t in tuiles:
        centre, demi = t["boite"]
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    local = centre + np.array([sx, sy, sz]) * (demi + marge_m)
                    coins.append(t["repere"].origine + t["repere"].axes @ local)
    coins = np.array(coins)
    lon, lat, haut = warp_transform(ECEF, WGS84, coins[:, 0].tolist(), coins[:, 1].tolist(), coins[:, 2].tolist())
    lon, lat, haut = (np.array(v) for v in (lon, lat, haut))
    return [float(np.radians(lon.min())), float(np.radians(lat.min())), float(np.radians(lon.max())),
            float(np.radians(lat.max())), float(haut.min()), float(haut.max())]


def ecrire_tileset(dossier: Path, tuiles: list[dict], annee: int, extras: dict) -> Path:
    """Écrit `tileset.json` (3D Tiles 1.1) ; chaque tuile a déjà son contenu .gltf."""
    etendue = region_racine(tuiles)
    enfants = []
    for t in tuiles:
        centre, demi = t["boite"]
        enfants.append({
            "transform": t["repere"].transform_3dtiles(),
            "boundingVolume": {"box": [float(centre[0]), float(centre[1]), float(centre[2]),
                                       float(demi[0]), 0.0, 0.0, 0.0, float(demi[1]), 0.0, 0.0, 0.0, float(demi[2])]},
            "geometricError": 0.0,
            "refine": "ADD",
            "content": {"uri": f"{t['nom']}.gltf"},
            "extras": {"tile": t["nom"], "instances": t["n"]},
        })
    diag = max(2.0 * float(np.linalg.norm(t["boite"][1])) for t in tuiles)
    doc = {
        "asset": {"version": "1.1", "tilesetVersion": str(annee)},
        "geometricError": round(diag * 2.0, 3),
        "root": {"boundingVolume": {"region": etendue}, "geometricError": round(diag * 2.0, 3),
                 "refine": "ADD", "children": enfants},
        "extras": extras,
    }
    chemin = dossier / "tileset.json"
    chemin.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return chemin
