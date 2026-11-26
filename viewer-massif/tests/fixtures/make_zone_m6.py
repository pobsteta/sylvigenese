#!/usr/bin/env python3
"""Zone d'essai SYNTHÉTIQUE des tests GUT de viewer-massif (mission 069). Écrit, à côté de ce script :

  zone_m6/              un bloc de 500 m (t_700000_6500000, 2022), quatre arbres aux extrémités nord, sud, est, ouest
                        (coordonnées asymétriques x != y), couvert herbacé 0,3 ; assets/trees/ : trois .glb
  zone_m6_sans_herbe/   la même, couvert herbacé et arbustif nuls (l'herbe d'une cellule à couvert nul est vide)

Les .glb sont écrits ici, à la main (struct), INDÉPENDAMMENT de assets : des arbres géométriques (un tronc, une cime
penchée vers l'est et le NORD du générateur, donc vers +x et -z de glTF y-up), trois niveaux de détail par MSFT_lod.
Aucune valeur n'est écologique ; tout est marqué synthétique et provisoire. Le sol est un plan incliné
(z = 340 + 0,04 x + 0,10 y, relatif à l'origine du bloc) : l'interpolation bilinéaire y est exacte.

Usage : python3 make_zone_m6.py
"""
import json
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ORIGIN = {"x": 700000.0, "y": 6500000.0, "z": 340.0}
H_REF = 12.0
STAGE_OF = {"09": ("mature", "old"), "62": ("mature",)}
TREES = [  # tree_id, espèce, stade, x, y (relatifs à l'origine du bloc), h
    ("n01", "09", "mature", 260.0, 470.0, 12.0),
    ("s01", "09", "old", 240.0, 30.0, 12.0),
    ("e01", "62", "mature", 475.0, 230.0, 12.0),
    ("w01", "09", "mature", 25.0, 270.0, 12.0),
]


def sol(x, y):
    return 0.04 * x + 0.10 * y


def ring(y, r, n=6, cx=0.0, cz=0.0):
    return [(cx + r * np.cos(2 * np.pi * k / n), y, cz + r * np.sin(2 * np.pi * k / n)) for k in range(n)]


def mesh_tree(sides, with_crown=True):
    """Tronc (prisme) de y = 0 à 4 m, cime (cône) de 4 à H_REF penchée vers +x et -z (nord du générateur)."""
    pos, idx = [], []

    def tube(rings):
        base = len(pos)
        for r in rings:
            pos.extend(r)
        n = len(rings[0])
        for a in range(len(rings) - 1):
            for k in range(n):
                p, q = base + a * n + k, base + a * n + (k + 1) % n
                pos_next = n
                idx.extend([p, q, p + pos_next, q, q + pos_next, p + pos_next])
    tube([ring(0.0, 0.25, sides), ring(4.0, 0.2, sides)])
    if with_crown:
        top = len(pos)
        pos.append((2.0, H_REF, -2.0))               # sommet décalé : est (+x) et nord (-z)
        tube([ring(4.0, 2.0, sides, 1.0, -1.0), ring(4.001, 2.0, sides, 1.0, -1.0)])
        # fermer vers le sommet
        base = len(pos) - sides
        for k in range(sides):
            idx.extend([base + k, base + (k + 1) % sides, top])
    return np.array(pos, dtype="<f4"), np.array(idx, dtype="<u4")


def write_glb(path, species, stage, generic=None):
    levels = [mesh_tree(6), mesh_tree(4), mesh_tree(3)]
    buf = bytearray()
    views, accs, meshes = [], [], []
    for pos, idx in levels:
        for arr, target, comp, typ in ((pos, 34962, 5126, "VEC3"), (idx, 34963, 5125, "SCALAR")):
            off = len(buf)
            buf.extend(arr.tobytes())
            while len(buf) % 4:
                buf.append(0)
            views.append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, "target": target})
            acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(arr.size // (3 if typ == "VEC3" else 1)),
                   "type": typ}
            if typ == "VEC3":
                acc["min"], acc["max"] = pos.min(axis=0).tolist(), pos.max(axis=0).tolist()
            accs.append(acc)
        meshes.append({"primitives": [{"attributes": {"POSITION": len(accs) - 2}, "indices": len(accs) - 1, "mode": 4}]})
    extras = ({"generique": True, "groupe": "resineux", "provisoire": True, "synthetique": True} if generic else
              {"species": species, "stage": stage, "source_commit": "0000000",
               "essence_generateur": "Fagus_sylvatica", "D_cm": 30.0, "H_m": H_REF, "hbh_m": 6.0, "Rh_m": 3.0,
               "b_cible": 1.0, "graine": 1, "H_ref_m": H_REF, "rayon_houppier_ref_m": 2.0,
               "provisoire": True, "synthetique": True,
               "feuillage": {"type": "cartes_couleur_unie", "couleur": "#4f7a32"}})
    gltf = {
        "asset": {"version": "2.0", "generator": "make_zone_m6.py (fixture synthetique, mission 069)"},
        "extensionsUsed": ["MSFT_lod"], "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "extensions": {"MSFT_lod": {"ids": [1, 2]}}, "extras": {"MSFT_screencoverage": [0.30, 0.05, 0.005]}},
                  {"mesh": 1}, {"mesh": 2}],
        "meshes": meshes, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}],
        "extras": extras,
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    body = bytes(buf) + b"\0" * (-len(buf) % 4)
    total = 12 + 8 + len(js) + 8 + len(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(body), 0x004E4942) + body)


def write_zone(name, herb, shrub):
    zone = HERE / name
    for sp, st, gen in (("09", "mature", None), ("09", "old", None), ("62", "mature", "generique_resineux")):
        write_glb(zone / "assets" / "trees" / ((gen or f"{sp}_{st}") + ".glb"), sp, st, generic=bool(gen))
    n = 20
    ground = [340.0 + sol(12.5 + 25.0 * c, 500.0 - 12.5 - 25.0 * r) for r in range(n) for c in range(n)]   # ligne 0 au nord
    cells = [{"cell_id": r * n + c, "x": 12.5 + 25.0 * c, "y": 500.0 - 12.5 - 25.0 * r, "biome": "type_frais_futaie_fictive_mature",
              "biome_provisoire": True, "herb_cover": herb, "shrub_cover": shrub} for r in range(n) for c in range(n)]
    block = {
        "schema_version": 2, "block_id": "t_700000_6500000", "year": 2022, "crs": "EPSG:2154", "vertical_datum": "NGF-IGN69",
        "origin": ORIGIN,
        "trees": [{"tree_id": i, "species": sp, "stage": st, "x": x, "y": y, "z": sol(x, y), "h": h, "d130": 30.0, "hcb": 5.0, "cw": 4.0}
                  for i, sp, st, x, y, h in TREES],
        "ground": {"resolution_m": 25, "nx": n, "ny": n, "z": ground},
        "cells": cells, "seedlings_simulated": False,
        "mentions": ["trajectoire technique, non validée écologiquement", "jeu fictif : valeurs synthétiques",
                     "modèle générique employé pour l'essence 62 (aucun exemplaire)",
                     "gibier, sous-bois et fructification non simulés"],
        "provisoire": True,
    }
    index = {
        "schema_version": 1, "zone": name, "fictive": True, "crs": "EPSG:2154", "vertical_datum": "NGF-IGN69", "source": "trees_init",
        "block_size_m": 500, "provisoire": True,
        "notes": ["trajectoire technique, non validée écologiquement", "jeu fictif : valeurs synthétiques",
                  "1 arbre dessiné par un modèle générique (aucun exemplaire de l'essence 62)"],
        "models": [{"species": "09", "model": "09", "kind": "own"}, {"species": "62", "model": "generique_resineux", "kind": "generic"}],
        "years": [{"year": 2022, "trees": 4, "trees_by_kind": {"own": 3, "alias": 0, "generic": 1},
                   "blocks": [{"block_id": "t_700000_6500000", "file": "2022/t_700000_6500000.json",
                               "sw": {"x": 700000.0, "y": 6500000.0}, "size_m": 500, "trees": 4}]}],
    }
    (zone / "massif" / "2022").mkdir(parents=True, exist_ok=True)
    (zone / "massif" / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (zone / "massif" / "2022" / "t_700000_6500000.json").write_text(json.dumps(block, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    (zone / "zone.yml").write_text("schema_version: 1\nfictive: true\nreason: zone d'essai synthétique des tests GUT de M6a (mission 069)\n", encoding="utf-8")


if __name__ == "__main__":
    write_zone("zone_m6", 0.3, 0.15)
    write_zone("zone_m6_sans_herbe", 0.0, 0.0)
    print("ok")
