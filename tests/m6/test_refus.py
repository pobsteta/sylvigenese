"""Refus et replis de `assets` face à des exemplaires fautifs (mission 069, cas du terrain, signaler plutôt que deviner).

Chaque cas casse UNE chose dans une copie des exemplaires de la fixture ; `assets` s'arrête (code non nul, sans réseau)
en disant laquelle, et n'écrit aucun .glb à moitié. Cas : fichier corrompu, repère non dit z-up, colonne absente, essence
hors référentiel, doublon (essence, stade), exemplaire non synthétique, source_commit absent, dossier d'exemplaires absent.
"""
import helpers_m6 as M


def test_un_exemplaire_fautif_est_refuse_en_disant_pourquoi(refus, zone_a):
    M.exige(zone_a)      # les mêmes exemplaires non cassés sont acceptés : le refus vient bien du défaut
    cas, z, mots = refus
    p = z["proc"]
    assert p.returncode != 0, f"{cas} : assets a accepté l'exemplaire fautif"
    texte = (p.stdout + p.stderr)
    assert any(m.lower() in texte.lower() for m in mots), f"{cas} : le message ne nomme pas la cause ({mots}) :\n{texte[-1200:]}"
    assert "Traceback" not in texte, f"{cas} : trace Python au lieu d'une erreur lisible :\n{texte[-1200:]}"


def test_un_refus_n_ecrit_aucun_glb_a_moitie(refus, zone_a):
    M.exige(zone_a)
    cas, z, _ = refus
    assert z["proc"].returncode != 0
    assert not M.glb_files(z["dir"]), f"{cas} : des .glb existent après un refus : {sorted(M.glb_files(z['dir']))}"


def test_dossier_d_exemplaires_absent_est_un_refus_pas_un_repli_silencieux(zone_exemplars_dir_absent, zone_a):
    M.exige(zone_a)
    p = zone_exemplars_dir_absent["proc"]
    assert p.returncode != 0, "exemplars_dir inexistant : assets ne doit pas se rabattre en silence sur le générique"
    assert "n_existe_pas_m6" in (p.stdout + p.stderr) or "exemplars_dir" in (p.stdout + p.stderr)
