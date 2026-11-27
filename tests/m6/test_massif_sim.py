"""Vue massif d'une zone avec sim/ (recrutement ifn_direct) : plusieurs années, comptes recoupés (mission 069, plan §6).

`make dynamics simulate` (R et Rust requis, comme tests/m4) puis `assets` avec les exemplaires de la fixture.
Couvre : somme des arbres des blocs = instances de tiles/index.json = arbres vivants de sim/trees ; `ifn_direct` =>
`seedlings_simulated` faux et aucune clé seedlings ; recrutement dit à l'index ; stade par arbre (h / h_pot).
Non couvert : `cohorts` (params/regeneration absents du jeu fictif ; seedlings[] égaux à sim/cells).
"""
import numpy as np

import helpers_m4_temps as T
import helpers_m6 as M


def _zdir(zone_sim):
    assert zone_sim["make"].returncode == 0, "make dynamics simulate en échec :\n" + T.queue(zone_sim["make"])
    return M.exige(zone_sim)


def test_l_index_a_les_annees_de_tiles_index_et_dit_ifn_direct(zone_sim):
    zdir = _zdir(zone_sim)
    idx = M.read_json(zdir / "massif" / "index.json")
    til = M.read_json(zdir / "tiles" / "index.json")
    attendu = T.retained_years(T.T0, T.YEARS, T.STEP)
    assert [y["year"] for y in idx["years"]] == [y["year"] for y in til["years"]] == attendu
    assert idx["source"] == "sim" and idx["recruitment"] == "ifn_direct"
    assert M.validate("assets.massif_index", zdir / "massif" / "index.json").returncode == 0


def test_somme_des_blocs_egale_instances_et_arbres_vivants_de_sim(zone_sim):
    zdir = _zdir(zone_sim)
    idx = M.read_json(zdir / "massif" / "index.json")
    til = M.read_json(zdir / "tiles" / "index.json")
    for y in idx["years"]:
        ty = next(v for v in til["years"] if v["year"] == y["year"])
        vivants = int((T.trees_of_year(zdir, y["year"])["status"] == "alive").sum())
        assert y["trees"] == ty["instances"] == vivants == sum(b["trees"] for b in y["blocks"]), y["year"]
        assert sum(y["trees_by_kind"].values()) == y["trees"]


def test_ifn_direct_sans_semis_et_blocs_conformes(zone_sim):
    zdir = _zdir(zone_sim)
    fichiers = sorted((zdir / "massif").glob("*/*.json"))
    assert len(fichiers) == 4 * 3, f"{len(fichiers)} blocs (4 tuiles x 3 années)"
    for f in fichiers:
        assert M.validate("assets.massif_block", f).returncode == 0, f
        b = M.read_json(f)
        assert b["seedlings_simulated"] is False and all("seedlings" not in c for c in b["cells"])


def test_les_arbres_du_bloc_sont_ceux_de_sim_a_leur_place_et_leur_stade(zone_sim):
    zdir = _zdir(zone_sim)
    idx = M.read_json(zdir / "massif" / "index.json")
    for y in idx["years"]:
        s = T.trees_of_year(zdir, y["year"])
        vivant = s["status"] == "alive"
        pos = {str(i): (float(a), float(b), float(h)) for i, a, b, h, v in zip(s["tree_id"], s["x"], s["y"], s["h"], vivant) if v}
        hp = M.hpot_of_trees(zdir, {"x": s["x"], "y": s["y"]})
        ratio = {str(i): float(h) / p for i, h, p in zip(s["tree_id"], s["h"], hp)}
        vus = 0
        for b in y["blocks"]:
            blk = M.read_json(zdir / "massif" / b["file"])
            for a in blk["trees"]:
                ex = pos[a["tree_id"]]
                assert abs(blk["origin"]["x"] + a["x"] - ex[0]) <= 0.05 and abs(blk["origin"]["y"] + a["y"] - ex[1]) <= 0.05
                r = ratio[a["tree_id"]]
                if not M.near_break(np.array([r]))[0]:
                    assert a["stage"] == M.stage_of(r), f"{y['year']} {a['tree_id']} : {a['stage']} pour h/h_pot = {r:.3f}"
                vus += 1
        assert vus == len(pos)


def test_les_modeles_des_tuiles_de_chaque_annee_sont_des_glb(zone_sim):
    zdir = _zdir(zone_sim)
    from glb import Glb
    lod2 = {Glb(p).lod2_hash() for p in M.glb_files(zdir).values()}
    for y in (2022, 2032, 2037):
        inst = M.tile_instances(zdir, y)
        assert len(inst["world"]) > 0 and inst["mesh_hashes"] <= lod2, f"{y} : maillage de tuile sans .glb"


def test_la_derniere_annee_est_retenue_et_l_annee_voisine_n_existe_pas(zone_sim):
    """Une année absente de l'index n'a pas de bloc : la vue la refuse, jamais l'année voisine (T7)."""
    zdir = _zdir(zone_sim)
    idx = M.read_json(zdir / "massif" / "index.json")
    annees = [y["year"] for y in idx["years"]]
    assert 2033 not in annees and 2027 not in annees
    assert not (zdir / "massif" / "2033").exists() and not (zdir / "massif" / "2027").exists()
