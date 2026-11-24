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


def test_toutes_les_sorties_de_m1a_existent(runs):
    absentes = [r for r in H.OUTPUT_FILES if not (H.ZONE / r).is_file()]
    if not (H.ZONE / "trees_init").exists() and not (H.ZONE / "trees_init.parquet").exists():
        absentes.append("trees_init (dossier ou .parquet)")
    assert not absentes, f"sorties absentes de tests/fixtures/zone_fictive/ : {absentes}"


def test_prepare_est_rejouable_a_l_identique(runs):
    # BRIEF/CLAUDE.md : rejouable depuis config.yml ; un second passage redonne les mêmes valeurs.
    assert runs["prepare_2"].returncode == 0, _msg(runs["prepare_2"])
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
