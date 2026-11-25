"""M3a, codes de sortie (spec §6) : 2 entrée refusée, 3 contrôle échoué, 4 mémoire insuffisante, et jamais de
sim/ partiel. Cas du terrain : configuration incomplète ou hors référentiel, raster absent, arbre hors grille,
essence sans paramètres, doublon, colonne absente, date incohérente, absence de réseau (tous les runs sont sans
réseau : proxys morts)."""
from pathlib import Path

import pytest

import helpers_m3 as H
from conftest import CHAINE

queue = H.queue


def sortie(p):
    return (p.stdout + "\n" + p.stderr).lower()


# ------------------------------------------------------------------ code 2
def test_une_entree_refusee_sort_avec_le_code_2(refus):
    p = refus["proc"]
    assert p.returncode == 2, f"[{refus['cas']}] attendu le code 2 : {queue(p)}"


def test_le_refus_dit_pourquoi_en_clair(refus):
    p = refus["proc"]
    assert p.returncode == 2, f"[{refus['cas']}] attendu le code 2 : {queue(p)}"
    out = sortie(p)
    assert "panicked" not in out and "traceback" not in out, f"[{refus['cas']}] plantage au lieu d'un refus : {queue(p)}"
    assert p.stderr.strip(), f"[{refus['cas']}] aucun message sur stderr"
    assert any(m.lower() in out for m in refus["mots"]), \
        f"[{refus['cas']}] le message ne nomme pas la cause {refus['mots']} : {queue(p)}"


def test_un_refus_ne_laisse_aucun_sim_partiel(refus):
    assert refus["proc"].returncode == 2, f"[{refus['cas']}] attendu le code 2 : {queue(refus['proc'])}"
    assert not (refus["dir"] / "sim").exists(), f"[{refus['cas']}] sim/ existe après un refus : " \
        f"{[str(p.relative_to(refus['dir'])) for p in (refus['dir'] / 'sim').rglob('*')][:5]}"


def test_une_config_introuvable_est_refusee_avec_le_code_2(chaine):
    absent = chaine["dir"] / "pas_de_config.yml"
    p = H.run_simulate(CHAINE, absent)
    assert p.returncode == 2, queue(p)
    assert "config" in sortie(p)


# ------------------------------------------------------------------ code 3
def test_un_nan_injecte_arrete_avec_le_code_3(run_nan):
    p = run_nan["proc"]
    assert p.returncode == 3, queue(p)


def test_le_code_3_dit_le_nan_en_francais_et_sans_plantage(run_nan):
    out = sortie(run_nan["proc"])
    assert "panicked" not in out
    assert "nan" in out or "non fini" in out, queue(run_nan["proc"])
    assert any(m in out for m in ("valeur", "arbre", "année", "annee", "contrôle", "controle")), queue(run_nan["proc"])


def test_le_code_3_ne_laisse_aucun_sim_partiel(run_nan):
    assert run_nan["proc"].returncode == 3, queue(run_nan["proc"])
    assert not (run_nan["dir"] / "sim").exists(), "sim/ existe après un contrôle échoué"


# ------------------------------------------------------------------ code 4
def test_une_memoire_trop_faible_sort_avec_le_code_4(run_memoire):
    assert run_memoire["proc"].returncode == 4, queue(run_memoire["proc"])


def test_le_code_4_refuse_avant_toute_ecriture(run_memoire):
    """Le noyau tue un programme qui sur-alloue (137) : le moteur doit refuser AVANT, sans rien écrire."""
    assert run_memoire["proc"].returncode == 4, queue(run_memoire["proc"])
    assert not (run_memoire["dir"] / "sim").exists(), "sim/ écrit malgré une mémoire insuffisante"
    out = sortie(run_memoire["proc"])
    assert "mémoire" in out or "memoire" in out, queue(run_memoire["proc"])
    assert "panicked" not in out


def test_l_estimation_de_memoire_de_la_chaine_tient_dans_memavailable(chaine):
    """T3 : estimation comparée à MemAvailable × 0,9 ; la chaîne nominale a tourné, donc l'estimation y tient."""
    j = H.read_run_json(chaine["dir"])
    dispo = next(int(l.split()[1]) * 1024 for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemAvailable"))
    assert 0 < j["memory_estimate_bytes"] <= 0.9 * dispo, (j["memory_estimate_bytes"], dispo)


# ------------------------------------------------------------------ date incohérente (t0 avant la date de vol)
def test_un_t0_avant_la_date_de_vol_est_refuse_ou_signale(run_date_incoherente):
    """Les dalles du jeu fictif datent de 2021 et 2022 ; t0 = 2015 demande de reculer la hauteur dans le temps.
    Règle du projet : signaler plutôt que deviner. Admis : le code 2 avec un message sur la date, ou une
    simulation qui la signale dans flags.parquet ; refusé : un résultat muet."""
    r = run_date_incoherente
    p = r["proc"]
    out = sortie(p)
    if p.returncode == 2:
        assert any(m in out for m in ("date", "vol", "t0")), queue(p)
        assert not (r["dir"] / "sim").exists()
        return
    assert p.returncode == 0, queue(p)
    corpus = H.sim_text_corpus(r["dir"]).lower()
    assert any(m in corpus for m in ("date de vol", "vol ", "antérieur", "anterieur", "avant la date")), \
        "t0 antérieur à la date de vol, accepté sans le dire"
