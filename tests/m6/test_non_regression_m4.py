"""Non-régression de M4 avec les modèles du générateur (mission 069, plan §6) : mêmes arbres, mêmes places.

14 080 instances, la même année, les mêmes tuiles (instances par tuile), chaque arbre de trees_init retrouvé UNE fois à
ses coordonnées (au dixième de mètre). Si un de ces chiffres bouge, D a un défaut (plan §8, « tests de M4 »).
"""
import numpy as np

import helpers_m4 as H
import helpers_m6 as M


def test_14080_instances_une_par_arbre_au_dixieme_de_metre(zone_a):
    zdir = M.exige(zone_a)
    t = H.read_trees_init(H.ZONE)
    inst = M.tile_instances(zdir)
    assert len(inst["world"]) == 14080 == len(t["x"])
    m = H.match_instances(inst["world"], t["x"], t["y"])
    ok = m["tree_of"] >= 0
    assert ok.all(), f"{int((~ok).sum())} instances sans arbre"
    assert len(set(m["tree_of"])) == 14080, "deux instances pour un même arbre, ou un arbre sans instance"
    assert np.nanmax(m["resid"]) <= 0.1, f"écart maximal {np.nanmax(m['resid']):.3f} m"


def test_tiles_index_garde_l_annee_et_les_instances_par_tuile(zone_a):
    zdir = M.exige(zone_a)
    avant = M.read_json(H.ZONE / "tiles" / "index.json")      # jeu versionné : 14 080 en quatre tuiles
    apres = M.read_json(zdir / "tiles" / "index.json")
    assert [y["year"] for y in apres["years"]] == [y["year"] for y in avant["years"]] == [2022]
    assert apres["years"][0]["instances"] == 14080
    assert {t["tile"]: t["instances"] for t in apres["years"][0]["tiles"]} == \
           {t["tile"]: t["instances"] for t in avant["years"][0]["tiles"]}
    assert M.validate("assets.tiles_index", zdir / "tiles" / "index.json").returncode == 0


def test_les_tuiles_restent_en_gltf_avec_bin_et_instanciation(zone_a):
    """T1 : les tuiles iTowns restent des .gltf + .bin en EXT_mesh_gpu_instancing (le gestionnaire n'est enregistré que pour .gltf)."""
    zdir = M.exige(zone_a)
    contenus = sorted((zdir / "tiles" / "2022").glob("t_*.gltf"))
    assert len(contenus) == 4
    for c in contenus:
        assert c.with_suffix(".bin").is_file()
        assert H.EXT in c.read_text(encoding="utf-8")
        g = H.read_gltf(c)
        assert g["asset"]["version"] == "2.0" and H.EXT in g.get("extensionsUsed", [])
