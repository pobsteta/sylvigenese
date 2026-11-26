"""Chaque arbre est dessiné par SON modèle : un par (essence, stade), générique signalé sans emprunt (mission 069).

Décisions de Pascal du 26/11/2026 : Q3 (essence sans modèle = générique feuillu ou résineux, signalé, compté, aucun
emprunt à une essence voisine, décomptes d'arbres inchangés) ; Q8 (stade de CHAQUE arbre = h / h_pot de l'arbre, seuils de
biomes/stades/stage_breaks.yml). Oracle recalculé ici : species.csv, site_potential.tif (h_pot de la cellule),
trees_init, exemplaires de la fixture. Remplace, avec tests/m4, l'ancienne épingle « feuillu et résineux ».
"""
import numpy as np

import helpers_m4 as H
import helpers_m6 as M
from glb import Glb


def _modele_par_arbre(zdir, oracle_zone):
    """(noms de modèle d'après les tuiles, noms attendus, masque des arbres hors des seuils, rang des arbres)."""
    t = H.read_trees_init(oracle_zone)
    inst = M.tile_instances(zdir)
    m = H.match_instances(inst["world"], t["x"], t["y"])
    ok = m["tree_of"] >= 0
    assert ok.sum() == len(t["x"]), f"{len(t['x']) - ok.sum()} arbres sans instance"
    lod2 = {Glb(p).lod2_hash(): k for k, p in M.glb_files(zdir).items()}
    modele = np.array([lod2.get(h, "?") for h in inst["model_hash"]], dtype=object)
    vu = np.empty(len(t["x"]), dtype=object)
    vu[m["tree_of"]] = modele
    return t, vu


def _attendu(t, zdir, available):
    hp = M.hpot_of_trees(zdir, t)
    ratio = np.array(t["h"], float) / hp
    stade = [M.stage_of(r) for r in ratio]
    noms = [M.expected_model(str(s), st, available)[0] for s, st in zip(t["species"], stade)]
    return np.array(noms, dtype=object), np.array(stade, dtype=object), ~M.near_break(ratio)


def test_chaque_arbre_a_le_modele_de_son_essence_et_de_son_stade(zone_a):
    zdir = M.exige(zone_a)
    t, vu = _modele_par_arbre(zdir, H.ZONE)
    attendu, stade, franc = _attendu(t, H.ZONE, M.exemplars_available())
    faux = np.nonzero((vu != attendu) & franc)[0]
    assert not len(faux), (f"{len(faux)} arbres avec un autre modèle que (essence, stade) ; "
                           f"ex. {[(t['species'][i], stade[i], vu[i], attendu[i]) for i in faux[:4]]}")


def test_il_y_a_un_modele_par_essence_et_par_stade_pas_deux_groupes(zone_a):
    zdir = M.exige(zone_a)
    t, vu = _modele_par_arbre(zdir, H.ZONE)
    attendu, _, franc = _attendu(t, H.ZONE, M.exemplars_available())
    employes = set(vu[franc])
    assert len(employes) > 4, f"modèles employés : {sorted(employes)} (feuillu et résineux seuls ?)"
    assert employes == set(attendu[franc]), f"employés {sorted(employes)} != attendus {sorted(set(attendu[franc]))}"


def test_le_sous_etage_se_voit_des_arbres_de_stades_differents_dans_une_meme_cellule(zone_a):
    """Q8 : le stade est celui de l'arbre (h / h_pot), pas celui de sa cellule."""
    zdir = M.exige(zone_a)
    t, vu = _modele_par_arbre(zdir, H.ZONE)
    o = H.Oracle(H.ZONE)
    stades = {}
    for cell, v, s in zip(o.tree_cell, vu, t["species"]):
        if str(s) in ("09", "03"):
            stades.setdefault(int(cell), set()).add(v)
    assert sum(len(v) > 1 for v in stades.values()) > 100, "aucune cellule n'a deux modèles de stades différents"


def test_les_decomptes_d_arbres_ne_bougent_pas(zone_a):
    zdir = M.exige(zone_a)
    assert len(M.tile_instances(zdir)["world"]) == 14080


# ------------------------------------------------------------------ essence sans modèle : générique, signalé, sans emprunt
def test_hetre_sans_exemplaire_est_generique_feuillu_et_non_un_chene(zone_generique):
    zdir = M.exige(zone_generique)
    noms = M.glb_files(zdir)
    assert not any(k.startswith("09_") for k in noms), "un modèle propre du hêtre sans exemplaire"
    assert "generique_feuillu" in noms
    t, vu = _modele_par_arbre(zdir, zdir)
    attendu, _, franc = _attendu(t, zdir, M.exemplars_available(zone_generique["exemplars_dir"]))
    sp = np.array(t["species"], dtype=str)
    assert (attendu[sp == "09"] == "generique_feuillu").all()
    hetres = (sp == "09") & franc
    assert (vu[hetres] == "generique_feuillu").all(), f"hêtres dessinés par {sorted(set(vu[hetres]))} : emprunt ou erreur"


def test_chataignier_sans_modele_du_generateur_est_generique_feuillu(zone_generique):
    zdir = M.exige(zone_generique)
    t, vu = _modele_par_arbre(zdir, zdir)
    ids = set(zone_generique["castaneas"])
    sel = np.array([str(i) in ids for i in t["tree_id"]])
    assert sel.sum() == 40
    assert (vu[sel] == "generique_feuillu").all(), f"châtaigniers : {sorted(set(vu[sel]))}"


def test_les_hetres_ramenes_a_15_pour_cent_de_h_pot_prennent_le_stade_young_du_chene_voisin_pas_du_hetre(zone_generique):
    """Avec le hêtre sans exemplaire, `young` n'est pas servi par le hêtre : ces 5 arbres restent génériques (jamais
    02_young) ; les chênes (alias 03 -> 02) du même stade, eux, prennent 02_young."""
    zdir = M.exige(zone_generique)
    t, vu = _modele_par_arbre(zdir, zdir)
    ids = set(zone_generique["jeunes"])
    sel = np.array([str(i) in ids for i in t["tree_id"]])
    assert sel.sum() == 5 and (vu[sel] == "generique_feuillu").all(), sorted(set(vu[sel]))
    sp = np.array(t["species"], dtype=str)
    hp = M.hpot_of_trees(zdir, t)
    young_chene = (sp == "03") & (np.array(t["h"], float) / hp < 0.25 - 0.003)
    if young_chene.any():
        assert (vu[young_chene] == "02_young").all()


def test_aucun_glb_n_est_emprunte_a_une_autre_essence(zone_generique):
    zdir = M.exige(zone_generique)
    assert M.glb_files(zdir), "aucun .glb produit"
    for nom, p in M.glb_files(zdir).items():
        e = Glb(p).extras
        if nom.startswith("generique_"):
            assert e["generique"] is True
        else:
            assert e["species"] == nom.split("_")[0], f"{nom} : extras.species = {e['species']}"


def test_l_index_du_massif_dit_alias_propre_et_generique_et_les_compte(zone_generique, zone_a):
    for z, attendu_gen in ((zone_a, {"62": "generique_resineux", "64": "generique_resineux"}),
                           (zone_generique, {"62": "generique_resineux", "64": "generique_resineux",
                                             "09": "generique_feuillu", "10": "generique_feuillu"})):
        zdir = M.exige(z)
        idx = M.read_json(zdir / "massif" / "index.json")
        par = {m["species"]: m for m in idx["models"]}
        for sp, nom in attendu_gen.items():
            assert par[sp]["kind"] == "generic" and par[sp]["model"] == nom, f"{sp} : {par[sp]}"
        assert par["03"]["kind"] == "alias" and par["03"]["alias_of"] == "02" and par["03"]["model"] == "02"
        assert par["61"]["kind"] == "own" and par["61"]["model"] == "61"
        t = H.read_trees_init(zdir)
        sp = np.array(t["species"], dtype=str)
        gen = int(np.isin(sp, list(attendu_gen)).sum())
        # le générique du groupe est signalé et compté ; les décomptes d'arbres sont inchangés
        y0 = idx["years"][0]
        assert y0["trees"] == len(sp) == 14080
        assert y0["trees_by_kind"]["generic"] == gen, f"{y0['trees_by_kind']} (générique attendu : {gen})"
        assert sum(y0["trees_by_kind"].values()) == y0["trees"]


def test_le_generique_est_signale_dans_les_notes_et_les_fiches(zone_generique):
    zdir = M.exige(zone_generique)
    idx = M.read_json(zdir / "massif" / "index.json")
    assert any("générique" in n or "generique" in n for n in idx["notes"]), idx["notes"]
    fiches = "".join(p.read_text(encoding="utf-8") for p in sorted((zdir / "web" / "cells").glob("*.json")))
    assert "générique" in fiches or "generique" in fiches, "la fiche ne signale pas le modèle générique (Q3)"
