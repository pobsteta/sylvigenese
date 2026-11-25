"""Exécution de prepare et biomes sur le jeu fictif (cas nominal, rejeu, sans réseau)."""
import numpy as np

import helpers as H


def _msg(p):
    return f"code {p.returncode}\n--- stdout ---\n{p.stdout[-1500:]}\n--- stderr ---\n{p.stderr[-1500:]}"


def test_make_prepare_reussit_sans_reseau(runs):
    # Les proxys sont morts (127.0.0.1:9) : prepare ne doit rien télécharger.
    assert runs["prepare"].returncode == 0, _msg(runs["prepare"])


def test_make_biomes_reussit_sans_reseau(runs):
    assert runs["biomes"].returncode == 0, _msg(runs["biomes"])


def test_make_trees_reussit_sans_reseau(runs):
    assert runs["trees"].returncode == 0, _msg(runs["trees"])


def test_toutes_les_sorties_de_m1a_existent(runs):
    absentes = [r for r in H.OUTPUT_FILES if not (H.ZONE / r).is_file()]
    if not (H.ZONE / "trees_init").exists() and not (H.ZONE / "trees_init.parquet").exists():
        absentes.append("trees_init (dossier ou .parquet)")
    assert not absentes, f"sorties absentes de tests/fixtures/zone_fictive/ : {absentes}"


def test_prepare_est_rejouable_a_l_identique(runs):
    # BRIEF/CLAUDE.md : rejouable depuis config.yml ; un second passage redonne les mêmes valeurs.
    for k in ("prepare_2", "biomes_2", "trees_2"):
        assert runs[k].returncode == 0, _msg(runs[k])
    s1, s2 = runs["snapshot1"], runs["snapshot2"]
    assert set(s1) == set(s2) and s1, "aucune sortie rejouable relue"
    for k in s1:
        if isinstance(s1[k], np.ndarray):
            assert np.array_equal(s1[k], s2[k], equal_nan=True), f"{k} diffère au second passage"
        else:
            assert s1[k] == s2[k], f"{k} diffère au second passage"


def test_les_entrees_ne_sont_pas_modifiees(runs):
    # Les entrées du jeu fictif restent valides pour le validateur (code 0, entrées seulement).
    p = H.validate("--zone", str(H.ZONE))
    assert p.returncode == 0, p.stderr[-1500:]


def test_trees_sans_vegetation_map_rend_2_et_n_ecrit_pas_trees_init():
    # Décision de l'orchestrateur : trees lit vegetation_map ; s'il manque, entrée refusée, code 2.
    try:
        d, cfg = H.make_zone_copy("m1_sans_vegetation_map")
        p = H.run_make("prepare", zone="m1_sans_vegetation_map", config=cfg)
        assert p.returncode == 0, _msg(p)
        assert not (d / "vegetation_map.tif").exists()
        q = H.run_module_status("trees", cfg)
        assert q.returncode == 2, _msg(q)
        assert q.stderr.strip(), "aucun message d'erreur"
        assert not (d / "trees_init").exists() and not (d / "trees_init.parquet").exists()
    finally:
        H.remove_zone_copy("m1_sans_vegetation_map")
