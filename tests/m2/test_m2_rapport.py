"""rapport_dynamics.html (spec §6 ; spec §11 M2a : « Validation croisée spatiale par blocs. Rapport par
essence. » ; fiche 025 : un tableau par essence, n, biais, erreur, domaine, et les limites connues)."""
import re

import pytest

import helpers_m2 as H


def test_rapport_en_utf8_sans_accent_casse(chaine):
    H.decode_report(H.ZONE / H.RAPPORT)


def test_un_tableau_par_essence_a_les_quatre_colonnes_demandees(rapport):
    # Effectif (ou n), biais, erreur, domaine de validité : un en-tête qui les porte tous.
    for b in rapport:
        s = H.sans_accent(b)
        if "biais" in s and "erreur" in s and "domaine" in s and ("effectif" in s or re.search(r"\bn\b", s)):
            return
    pytest.fail("aucun en-tête de tableau ne porte effectif (n), biais, erreur et domaine de validité")


def test_chaque_essence_du_jeu_a_sa_ligne_chiffree(rapport, ifn):
    # Une ligne par essence : au moins l'effectif (entier), puis le biais et l'erreur (décimaux).
    for code in sorted({t["ESPAR"] for t in ifn.trees}):
        blocs = H.species_blocks(rapport, code)
        assert blocs, f"l'essence {code} n'est pas au rapport"
        assert any(H.ints_in(b) - {int(code) if code.isdigit() else -1} and len(H.decimals_in(b)) >= 2
                   for b in blocs), f"l'essence {code} : ligne sans effectif ni biais ni erreur chiffrés : {blocs}"


def test_aucune_valeur_manquante_ecrite_comme_un_nombre(rapport):
    # Signaler plutôt que deviner : ni NaN, ni NA, ni Inf glissés dans un tableau.
    mauvais = [b for b in rapport if re.search(r"(?<![\w])(NaN|NA|Inf|-Inf)(?![\w])", b)]
    assert not mauvais, f"valeurs non numériques au rapport : {mauvais[:3]}"


def test_le_rapport_dit_que_le_resultat_est_provisoire_et_issu_du_jeu_fictif(rapport):
    # Spec §10 : « résultat provisoire » ; CLAUDE.md : rien d'écologique sans source.
    assert H.blocks_with(rapport, "provisoire"), "le rapport ne dit pas « provisoire »"
    assert H.blocks_with(rapport, "synthet") or H.blocks_with(rapport, "fictif"), \
        "le rapport ne dit pas que les données sont fictives"


# ------------------------------------------------------------------ limites connues (spec §6)
def test_limites_une_section_dediee(rapport):
    assert H.blocks_with(rapport, "limites connues") or H.blocks_with(rapport, "limite"), \
        "aucune section de limites connues"


def test_limite_concurrence_non_spatialisee_a_l_ajustement(rapport):
    # Spec §6 : concurrence à la placette (surface terrière pondérée) contre disque de 15 m en simulation.
    b = H.blocks_with(rapport, "concurrence", "spatialis")
    assert b, "la limite « concurrence non spatialisée » n'est pas écrite"
    assert any("placette" in H.sans_accent(x) for x in b), \
        "la limite ne dit pas que la concurrence est calculée à la placette"


def test_limite_flore_de_premiere_visite_pour_un_arbre_revu(rapport):
    # Spec §6, Q7 : flore et écologie relevées en 1re visite seulement, 5 ans avant la 2e.
    b = H.blocks_with(rapport, "flore")
    assert any(re.search(r"(1re|1ere|premiere|1 re)\s*visite", H.sans_accent(x)) and "decalage" in H.sans_accent(x)
               for x in b), f"la limite « décalage de la flore de 1re visite » n'est pas écrite : {b[:3]}"


# ------------------------------------------------------------------ validation croisée spatiale par blocs
def test_validation_croisee_par_blocs_est_decrite(rapport):
    b = H.blocks_with(rapport, "validation croisee", "bloc")
    assert b, "le rapport ne décrit pas la validation croisée par blocs"
    assert any("spatial" in H.sans_accent(x) for x in H.blocks_with(rapport, "bloc")), \
        "les blocs ne sont pas dits spatiaux"


def test_taille_des_blocs_est_donnee_avec_son_unite_et_marquee_provisoire(rapport):
    # Fiche 025 : « taille des blocs de validation croisée : provisoire, justifiée dans le rapport ».
    b = H.blocks_with(rapport, "bloc", "taille")
    assert any(re.search(r"\d+(?:[.,]\d+)?\s*(km|m)\b", x) for x in b), f"taille des blocs sans nombre ni unité : {b[:3]}"
    assert any("provisoire" in H.sans_accent(x) for x in b), "la taille des blocs n'est pas dite provisoire"


def test_le_modele_est_compare_au_modele_nul_dans_la_validation_croisee(rapport, ifn):
    # Spec §11, critère de M2b rendu possible dès M2a : l'erreur du modèle ET celle du modèle nul, par
    # essence, sur les mêmes blocs mis de côté.
    nuls = H.blocks_with(rapport, "modele nul")
    assert nuls, "aucune mention du modèle nul"
    assert any(len(H.decimals_in(b)) >= 2 for b in nuls), \
        "le modèle nul est cité sans les deux erreurs (modèle et nul) à comparer"
    for code in sorted({t["ESPAR"] for t in ifn.trees}):
        assert any(len(H.decimals_in(b)) >= 3 for b in H.species_blocks(rapport, code)), \
            f"essence {code} : pas de biais, d'erreur et d'erreur du modèle nul sur sa ligne"
