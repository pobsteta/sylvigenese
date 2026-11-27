"""Identité à l'octet près des .glb, et mêmes sommets dans les deux vues (mission 069, plan §6 ; décisions T1, T12).

- deux exécutions (deux dossiers) et un rejeu : mêmes octets ;
- un exemplaire modifié d'un segment : le .glb de cet exemplaire change, aucun autre ;
- les sommets du modèle de chaque tuile (vue iTowns) égalent ceux du LOD2 d'un .glb (vue Godot).
"""

import helpers_m6 as M
from glb import Glb


def test_deux_executions_donnent_les_memes_octets(zone_a, zone_b):
    a, b = M.glb_files(M.exige(zone_a)), M.glb_files(M.exige(zone_b))
    assert a and set(a) == set(b), f"jeux de .glb différents : {sorted(set(a) ^ set(b))}"
    diff = [k for k in a if M.sha(a[k]) != M.sha(b[k])]
    assert not diff, f"octets différents entre deux exécutions : {diff}"


def test_le_rejeu_sur_place_ne_change_pas_un_octet(zone_a_rerun, zone_a):
    M.exige(zone_a)
    assert zone_a_rerun["proc"].returncode == 0, zone_a_rerun["proc"].stderr[-1500:]
    assert zone_a_rerun["avant"] and zone_a_rerun["avant"] == zone_a_rerun["apres"]


def test_un_segment_modifie_change_le_glb_de_cet_exemplaire_et_aucun_autre(zone_a, zone_exemplaire_modifie):
    a, m = M.glb_files(M.exige(zone_a)), M.glb_files(M.exige(zone_exemplaire_modifie))
    assert set(a) == set(m)
    diff = sorted(k for k in a if M.sha(a[k]) != M.sha(m[k]))
    assert diff == ["09_mature"], f"fichiers changés : {diff} (09_mature seul attendu)"


def test_les_sommets_de_chaque_tuile_sont_ceux_du_lod2_d_un_glb(zone_a):
    zdir = M.exige(zone_a)
    lod2 = {k: Glb(p).lod2_hash() for k, p in M.glb_files(zdir).items()}
    inst = M.tile_instances(zdir)
    assert len(inst["world"]) == 14080
    inconnus = inst["mesh_hashes"] - set(lod2.values())
    assert not inconnus, f"{len(inconnus)} maillage(s) de tuile qui ne sont le LOD2 d'aucun .glb (deux vues, deux arbres)"


def test_aucune_tuile_n_emploie_un_modele_hors_des_glb_et_chaque_modele_employe_est_un_glb(zone_a):
    zdir = M.exige(zone_a)
    lod2 = {Glb(p).lod2_hash(): k for k, p in M.glb_files(zdir).items()}
    employes = {lod2[h] for h in set(M.tile_instances(zdir)["model_hash"]) if h in lod2}
    # 09, 02 (03 en alias), 61 en modèles propres, 62 et 64 en générique résineux : au moins un modèle par stade présent
    assert "generique_resineux" in employes
    assert any(k.startswith("09_") for k in employes) and any(k.startswith("02_") for k in employes)
    assert any(k.startswith("61_") for k in employes)
