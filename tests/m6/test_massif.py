"""massif/index.json et massif/<année>/<bloc>.json produits par `assets` (mission 069, plan §4, §5 T5 T6, §6).

Contrats : assets.massif_index et assets.massif_block (version 2). Repère : le piège de la Somalie (x et y inversés) est
attrapé par quatre arbres aux extrémités nord, sud, est, ouest de la zone, aux coordonnées asymétriques. Altitude du pied :
celle du MNT de la grille à 25 m (bilinéaire entre centres), recalculée ici depuis dtm.tif. Mode `trees_init` (sans sim/) :
`seedlings_simulated` faux. Le mode `sim` est dans test_massif_sim.py.
"""
import re

import numpy as np
import pytest
import yaml

import helpers_m4 as H
import helpers_m6 as M

TOL_XY = 0.05      # m
TOL_Z = 0.1        # m (terrain à 25 m ; plan §8 : quelques décimètres entre tronc et sol possibles, mais z de l'arbre = MNT)


@pytest.fixture(scope="module")
def zdir(zone_a):
    return M.exige(zone_a)


def _blocs(zdir):
    idx = M.read_json(zdir / "massif" / "index.json")
    out = {}
    for y in idx["years"]:
        for b in y["blocks"]:
            out[(y["year"], b["block_id"])] = M.read_json(zdir / "massif" / b["file"])
    return idx, out


def test_index_et_blocs_sont_conformes_aux_contrats(zdir):
    r = M.validate("assets.massif_index", zdir / "massif" / "index.json")
    assert r.returncode == 0, r.stdout + r.stderr
    fichiers = sorted((zdir / "massif").glob("*/*.json"))
    assert len(fichiers) == 4, f"{len(fichiers)} blocs pour 4 tuiles de 500 m"
    for f in fichiers:
        r = M.validate("assets.massif_block", f)
        assert r.returncode == 0, f"{f.name} : {r.stdout + r.stderr}"


def test_l_index_dit_la_zone_le_repere_et_les_annees_comme_tiles_index(zdir):
    idx = M.read_json(zdir / "massif" / "index.json")
    til = M.read_json(zdir / "tiles" / "index.json")
    assert idx["zone"] == zdir.name and idx["fictive"] is True and idx["crs"] == "EPSG:2154"
    assert idx["vertical_datum"] == "NGF-IGN69" and idx["source"] == "trees_init" and idx["block_size_m"] == 500
    assert [y["year"] for y in idx["years"]] == [y["year"] for y in til["years"]]
    assert idx["provisoire"] is True
    assert "recruitment" not in idx, "pas de mode de recrutement sans sim/"


def test_somme_des_arbres_des_blocs_egale_instances_de_tiles_index(zdir):
    blocs = _blocs(zdir)
    idx, bl = blocs
    til = M.read_json(zdir / "tiles" / "index.json")
    for y in til["years"]:
        iy = next(v for v in idx["years"] if v["year"] == y["year"])
        assert iy["trees"] == y["instances"] == sum(b["trees"] for b in iy["blocks"])
        assert {b["block_id"]: b["trees"] for b in iy["blocks"]} == {t["tile"]: t["instances"] for t in y["tiles"]}
        for b in iy["blocks"]:
            assert len(bl[(y["year"], b["block_id"])]["trees"]) == b["trees"], b["block_id"]
        assert iy["trees"] == sum(iy["trees_by_kind"].values())


def test_models_couvre_toutes_les_essences_et_pointe_vers_des_fichiers(zdir):
    blocs = _blocs(zdir)
    idx, bl = blocs
    essences = {t["species"] for b in bl.values() for t in b["trees"]}
    assert essences == {m["species"] for m in idx["models"]}
    for m in idx["models"]:
        if m["kind"] == "alias":
            assert M.owner_of(m["species"])[1] == m["alias_of"] == m["model"], m
        elif m["kind"] == "own":
            assert m["model"] == m["species"] == M.owner_of(m["species"])[1], m
        files = [p for p in M.glb_files(zdir) if p == m["model"] or p.startswith(m["model"] + "_")]
        assert files, f"aucun .glb pour le modèle {m['model']}"


def test_chaque_arbre_est_a_sa_place_x_et_y_ne_sont_pas_inverses(zdir):
    blocs = _blocs(zdir)
    """Chaque arbre de trees_init se retrouve (par tree_id) à (origine + position relative) = ses coordonnées Lambert-93."""
    _, bl = blocs
    t = H.read_trees_init(H.ZONE)
    pos = {str(i): (float(x), float(y), float(h), float(d)) for i, x, y, h, d in zip(t["tree_id"], t["x"], t["y"], t["h"], t["d130"])}
    vus = {}
    for (an, _), b in bl.items():
        assert b["crs"] == "EPSG:2154" and b["vertical_datum"] == "NGF-IGN69"
        for a in b["trees"]:
            x, y = b["origin"]["x"] + a["x"], b["origin"]["y"] + a["y"]
            vus[a["tree_id"]] = (x, y)
            ex = pos[a["tree_id"]]
            assert abs(x - ex[0]) <= TOL_XY and abs(y - ex[1]) <= TOL_XY, \
                f"{a['tree_id']} en ({x:.2f}, {y:.2f}), attendu ({ex[0]:.2f}, {ex[1]:.2f})"
            assert a["h"] == pytest.approx(ex[2], abs=1e-3) and a["d130"] == pytest.approx(ex[3], abs=1e-3)
    assert set(vus) == set(pos), "arbres perdus ou inventés"


def test_quatre_arbres_aux_extremites_nord_sud_est_ouest(zdir):
    blocs = _blocs(zdir)
    _, bl = blocs
    t = H.read_trees_init(H.ZONE)
    ids = {"nord": int(np.argmax(t["y"])), "sud": int(np.argmin(t["y"])), "est": int(np.argmax(t["x"])), "ouest": int(np.argmin(t["x"]))}
    allt = {a["tree_id"]: (b, a) for b in bl.values() for a in b["trees"]}
    for nom, i in ids.items():
        b, a = allt[str(t["tree_id"][i])]
        x, y = b["origin"]["x"] + a["x"], b["origin"]["y"] + a["y"]
        assert (abs(x - t["x"][i]) <= TOL_XY and abs(y - t["y"][i]) <= TOL_XY), f"arbre {nom} : ({x}, {y}) != ({t['x'][i]}, {t['y'][i]})"
        assert abs(t["x"][i] - t["y"][i]) > 1e5, "cas symétrique : x et y ne se distinguent pas"
        # un échange x <-> y sortirait de l'emprise de la zone : cela fait de ce test un détecteur
        assert not (abs(x - t["y"][i]) <= TOL_XY)


def test_l_altitude_du_pied_est_celle_du_mnt_de_la_grille(zdir):
    blocs = _blocs(zdir)
    _, bl = blocs
    vus = 0
    for b in bl.values():
        for a in b["trees"][::37]:           # un arbre sur 37 : 380 arbres, tout le massif
            x, y = b["origin"]["x"] + a["x"], b["origin"]["y"] + a["y"]
            if not (H.X0 + 12.5 <= x <= H.X0 + 1000 - 12.5 and H.Y0 - 1000 + 12.5 <= y <= H.Y0 - 12.5):
                continue
            z = b["origin"]["z"] + a["z"]
            assert abs(z - M.dtm_bilinear(zdir, x, y)) <= TOL_Z, f"{a['tree_id']} : z = {z:.2f}, MNT {M.dtm_bilinear(zdir, x, y):.2f}"
            vus += 1
    assert vus > 200


def test_le_sol_du_bloc_suit_le_mnt_ligne_0_au_nord(zdir):
    blocs = _blocs(zdir)
    """ground.z : nx x ny altitudes ; nx = 20 (centres des cellules de 25 m) ou 21 (coins) ; ligne 0 au nord."""
    _, bl = blocs
    for (an, bid), b in bl.items():
        g = b["ground"]
        assert g["resolution_m"] == 25 and len(g["z"]) == g["nx"] * g["ny"] and g["nx"] == g["ny"]
        n = g["nx"]
        assert n in (20, 21), f"{bid} : {n} nœuds sur 500 m à 25 m"
        decal = 12.5 if n == 20 else 0.0
        x0 = int(re.match(r"t_(\d+)_(\d+)", bid).group(1))
        y0 = int(re.match(r"t_(\d+)_(\d+)", bid).group(2))
        z = np.array(g["z"], float).reshape(g["ny"], g["nx"])
        for (r, c) in ((3, 3), (6, 14), (10, 8), (16, 5), (16, 16)):      # nœuds intérieurs, jamais au bord de la zone
            x = x0 + decal + 25.0 * c
            y = y0 + 500.0 - decal - 25.0 * r      # ligne 0 au nord
            attendu = M.dtm_bilinear(zdir, x, y)
            assert abs(b["origin"]["z"] + z[r, c] - attendu) <= TOL_Z or abs(z[r, c] - attendu) <= TOL_Z, \
                f"{bid} nœud ({r}, {c}) : {z[r, c]}, MNT {attendu}"


def test_les_cellules_portent_le_couvert_du_biome_sans_valeur_par_defaut(zdir):
    blocs = _blocs(zdir)
    _, bl = blocs
    cellules = 0
    for b in bl.values():
        assert len(b["cells"]) == 400, f"{len(b['cells'])} cellules de 25 m dans un bloc de 500 m"
        for c in b["cells"]:
            cellules += 1
            if c["biome"] is None:
                assert c["herb_cover"] is None and c["shrub_cover"] is None, "couvert inventé pour une cellule sans biome"
                continue
            f = M.ROOT / "biomes" / f"{c['biome']}.yml"
            assert f.is_file(), f"biome {c['biome']} absent de biomes/"
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
            assert c["herb_cover"] == pytest.approx(d["strates"]["herbacee"]["couvert"])
            assert c["shrub_cover"] == pytest.approx(d["strates"]["arbustive"]["couvert"])
            assert c["biome_provisoire"] is bool(d["provisoire"])
    assert cellules == 1600


def test_trees_init_sans_semis_simules_et_sans_cle_seedlings(zdir):
    blocs = _blocs(zdir)
    _, bl = blocs
    for b in bl.values():
        assert b["seedlings_simulated"] is False
        assert all("seedlings" not in c for c in b["cells"])


def test_mentions_provisoire_et_non_validee_ecologiquement(zdir):
    blocs = _blocs(zdir)
    idx, bl = blocs
    for b in bl.values():
        assert b["provisoire"] is True
        txt = " ".join(b["mentions"])
        assert "non validée écologiquement" in txt and ("synthétique" in txt.lower() or "fictif" in txt.lower()), b["mentions"]
        assert "générique" in txt, f"le modèle générique de 62 et 64 n'est pas dit au bloc : {b['mentions']}"
    assert any("non validée écologiquement" in n for n in idx["notes"])


def test_le_stade_de_chaque_arbre_est_h_sur_h_pot_de_l_arbre(zdir):
    blocs = _blocs(zdir)
    """Q8 : stade de l'arbre, seuils de biomes/stades/stage_breaks.yml, borne basse incluse."""
    _, bl = blocs
    t = H.read_trees_init(H.ZONE)
    hp = M.hpot_of_trees(H.ZONE, t)
    ratio = {str(i): float(h) / p for i, h, p in zip(t["tree_id"], t["h"], hp)}
    faux, vus, stades = 0, 0, set()
    for b in bl.values():
        for a in b["trees"]:
            r = ratio[a["tree_id"]]
            if M.near_break(np.array([r]))[0]:
                continue
            vus += 1
            stades.add(a["stage"])
            faux += a["stage"] != M.stage_of(r)
    assert vus > 13000 and faux == 0, f"{faux} arbres au stade faux sur {vus}"
    assert {"pole", "mature", "old"} <= stades, f"stades vus : {stades}"
