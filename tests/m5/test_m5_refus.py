"""Refus de M5a (codes de sortie de la spec §6 ; plan m5a, mission C ; décision de l'orchestrateur du 26/11/2026 :
`recruitment` facultatif au schéma, simulate refuse sans lui, code 2).

Code 2 : `recruitment` absent (aux deux niveaux), bloc `regeneration` absent en mode cohorts, params/regeneration
absent, terme de semis manquant pour une essence (aucune valeur d'emprunt), bloc `ser` absent au niveau SER,
cohorts_init absent ou faux (classe hors de K, doublon, cellule hors grille, essence hors référentiel, tiges
négatives). Code 3 : valeur non finie injectée au niveau SER. Code 4 : mémoire disponible trop faible au niveau SER.
Chaque refus dit sa cause en clair, sans plantage, et ne laisse aucun sim/ partiel. Tous les lancements sont sans
réseau (proxys morts, cas terrain « absence de réseau »)."""
import pytest

import helpers_m5 as H


FRANCAIS = (" absent", " manquant", " exig", " refus", " inconnu", " hors", " doublon", " double", " négati",
            " negati", " invalide", " attendu", "non conforme")


def _sans_chemins(r):
    """Sortie en minuscules, chemin de la zone retiré (il ne doit pas fournir les mots cherchés)."""
    return H.sortie(r["proc"]).replace(str(r["dir"]).lower(), "<zone>").replace(r["name"], "<zone>")


def _refus_code_2(r):
    p = r["proc"]
    assert p.returncode == 2, f"[{r['cas']}] attendu le code 2 : {H.queue(p)}"
    out = _sans_chemins(r)
    assert "panicked" not in out and "traceback" not in out, f"[{r['cas']}] plantage au lieu d'un refus : {H.queue(p)}"
    assert p.stderr.strip(), f"[{r['cas']}] aucun message sur stderr"
    assert any(m.lower() in out for m in r["mots"]), f"[{r['cas']}] le message ne nomme pas la cause {r['mots']} : {H.queue(p)}"
    assert any(m in out for m in FRANCAIS), f"[{r['cas']}] message sans mot français de refus : {H.queue(p)}"
    assert not (r["dir"] / "sim").exists(), f"[{r['cas']}] sim/ existe après un refus"


def test_ser_refus_en_code_2_qui_dit_sa_cause_sans_sim_partiel(refus_ser):
    _refus_code_2(refus_ser)


def test_massif_refus_en_code_2_qui_dit_sa_cause_sans_sim_partiel(refus_massif):
    _refus_code_2(refus_massif)


@pytest.mark.parametrize("refus_ser", ["terme_de_semis_manquant", "terme_de_passage_manquant"], indirect=True)
def test_le_refus_d_un_terme_manquant_nomme_l_essence(refus_ser):
    """Une essence sans valeur pour un terme lu : code 2, et le message dit laquelle (61 ou 03), jamais un emprunt."""
    essence = "61" if refus_ser["cas"] == "terme_de_semis_manquant" else "03"
    out = _sans_chemins(refus_ser)
    assert refus_ser["proc"].returncode == 2, H.queue(refus_ser["proc"])
    assert essence in out, f"le message ne nomme pas l'essence {essence} : {H.queue(refus_ser['proc'])}"


def test_ser_un_k_trop_court_nomme_l_essence_son_d99_et_le_k_demande(ser_k_court):
    """Mission 080 : K ne couvre pas la distance à 99 % de dispersion (d99, calculé de kernel_scale_m et kernel_shape,
    ici 11 m et forme 1 : 73,0 m ; K = 2 couvre 50 m). Code 2, message nommé, rien écrit, essence dite."""
    _verifier_k_trop_court(ser_k_court, d99="73.0", k="2")


def test_massif_un_k_trop_court_nomme_l_essence_son_d99_et_le_k_demande(massif_k_court):
    """Idem au niveau massif (a = 30 m, forme 1 : d99 = 199,2 m ; K = 1 couvre 25 m)."""
    _verifier_k_trop_court(massif_k_court, d99="199.2", k="1")


def _verifier_k_trop_court(r, d99, k):
    p = r["proc"]
    out = _sans_chemins(r)
    assert p.returncode == 2, H.queue(p)
    assert f"d99 = {d99} m" in out, H.queue(p)
    assert f"kernel_truncation_cells = {k}" in out, H.queue(p)
    assert any(f"essence {e}" in out for e in H.ESSENCES_MASSIF), f"essence non nommée : {H.queue(p)}"
    assert not (r["dir"] / "sim").exists()


def test_ser_un_nan_injecte_arrete_avec_le_code_3(ser_nan):
    p = ser_nan["proc"]
    assert p.returncode == 3, H.queue(p)
    out = H.sortie(p)
    assert "panicked" not in out and ("nan" in out or "non fini" in out), H.queue(p)
    assert not (ser_nan["dir"] / "sim").exists(), "sim/ existe après un contrôle échoué"


def test_ser_une_memoire_trop_faible_sort_avec_le_code_4_avant_toute_ecriture(ser_memoire):
    p = ser_memoire["proc"]
    assert p.returncode == 4, H.queue(p)
    out = H.sortie(p)
    assert ("mémoire" in out or "memoire" in out) and "panicked" not in out, H.queue(p)
    assert not (ser_memoire["dir"] / "sim").exists(), "sim/ écrit malgré une mémoire insuffisante"
