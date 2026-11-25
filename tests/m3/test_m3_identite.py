"""M3a, critère « identité entre 1 et N fils » (spec §6 « Aléa », §11) : mêmes graine, mêmes octets, quel que
soit le nombre de fils ; autre graine, autres morts ; accroissement sans bruit (Pascal, Q4)."""
import numpy as np
import pytest

import helpers_m3 as H

queue = H.queue
T0 = H.SIM_NOMINAL["t0"]


# ------------------------------------------------------------------ 1 fil contre N fils
def test_n_fils_s_executent_avec_le_code_0(run_fils):
    assert run_fils["proc"].returncode == 0, queue(run_fils["proc"])


def test_run_json_dit_le_nombre_de_fils_demande(run_fils):
    assert H.read_run_json(run_fils["dir"])["threads"] == run_fils["threads"]


def test_sim_est_identique_au_bit_pres_entre_1_et_n_fils(chaine, run_fils):
    """SHA-256 de chaque fichier de sim/ (Parquet, flags) ; run.json comparé champ à champ, sans les seuls
    champs qui disent le calcul (fils, durée, mémoire estimée, empreinte de la config)."""
    ref = H.sim_digest(chaine["dir"])
    autre = H.sim_digest(run_fils["dir"])
    assert ref, "sim/ de la chaîne vide"
    assert set(ref) == set(autre), f"fichiers différents : {set(ref) ^ set(autre)}"
    diff = [f for f in ref if ref[f] != autre[f]]
    assert not diff, f"{len(diff)} fichiers différents entre 1 et {run_fils['threads']} fils, dont {diff[:3]}"


# ------------------------------------------------------------------ même graine, mêmes octets
def test_rejouer_la_meme_config_donne_les_memes_octets(chaine, run_t1_bis):
    assert run_t1_bis["proc"].returncode == 0, queue(run_t1_bis["proc"])
    ref = H.sim_digest(chaine["dir"], ignore_run_keys=("duration_s", "config_sha256"))
    bis = H.sim_digest(run_t1_bis["dir"], ignore_run_keys=("duration_s", "config_sha256"))
    assert ref and any(f.endswith(".parquet") for f in ref), "sim/ de la chaîne vide : rien à comparer"
    assert ref == bis, [f for f in ref if ref.get(f) != bis.get(f)][:3]


def test_l_horizon_n_influence_pas_les_annees_communes(chaine, run_graine42_court):
    """Le résultat d'une année ne dépend que de la graine, de la config et des entrées : 3 ans ou 100 ans, les
    trois premières années sont les mêmes."""
    assert run_graine42_court["proc"].returncode == 0, queue(run_graine42_court["proc"])
    for y in range(T0, T0 + 4):
        a = H.read_year(chaine["dir"], "trees", y).order("tree_id")
        b = H.read_year(run_graine42_court["dir"], "trees", y).order("tree_id")
        assert a.equals(b), f"année {y} différente entre 100 ans et 3 ans"


# ------------------------------------------------------------------ autre graine, autres morts
def test_une_autre_graine_donne_d_autres_morts(run_graine, run_graine42_court):
    assert run_graine["proc"].returncode == 0, queue(run_graine["proc"])
    for y in range(T0 + 1, T0 + 4):
        t42, t43 = (H.read_year(r["dir"], "trees", y) for r in (run_graine42_court, run_graine))
        m42 = set(t42["tree_id"][t42["status"] == "dead"].tolist())
        m43 = set(t43["tree_id"][t43["status"] == "dead"].tolist())
        assert len(m42) > 20 and len(m43) > 20, (len(m42), len(m43))
        assert m42 != m43, f"mêmes morts avec deux graines en {y}"
        inter = len(m42 & m43)
        # deux tirages indépendants à ~2 % : le recouvrement est faible devant l'effectif
        assert inter < 0.5 * min(len(m42), len(m43)), f"recouvrement suspect en {y} : {inter} sur {len(m42)} et {len(m43)}"


def test_une_autre_graine_donne_d_autres_recrues(run_graine, run_graine42_court):
    r42 = H.read_year(run_graine42_court["dir"], "trees", T0 + 1)
    r43 = H.read_year(run_graine["dir"], "trees", T0 + 1)
    def positions(t):
        r = t.where(H.commence_par(t["tree_id"], "r"))
        return set(zip(np.round(r["x"], 6).tolist(), np.round(r["y"], 6).tolist()))
    p42, p43 = positions(r42), positions(r43)
    assert len(p42) > 100 and len(p43) > 100
    commun = len(p42 & p43)
    assert commun < 0.05 * len(p42), f"{commun} recrues aux mêmes positions avec deux graines"


def test_l_accroissement_est_sans_bruit_donc_independant_de_la_graine(run_graine, run_graine42_court):
    """Q4 : accroissement en moyenne, sans bruit. En t0+1, tout arbre vivant dans les deux runs a le même d130
    (la concurrence de début d'année est la même) ; seules la mort et les recrues dépendent de la graine."""
    a = H.read_year(run_graine42_court["dir"], "trees", T0 + 1)
    b = H.read_year(run_graine["dir"], "trees", T0 + 1)
    communs = [t for t in a["tree_id"].tolist() if not t.startswith("r") and b.has(t)]
    ac, bc = a.align(communs), b.align(communs)
    # un arbre mort dans l'un des deux est écrit avec ses valeurs du 1er janvier, sans croissance : on ne compare
    # que les arbres vivants dans les deux
    vivants = (ac["status"] == "alive") & (bc["status"] == "alive")
    assert vivants.sum() > 10_000
    ac, bc = ac.where(vivants), bc.where(vivants)
    assert np.abs(ac["d130"] - bc["d130"]).max() < 1e-12
    assert np.abs(ac["h"] - bc["h"]).max() < 1e-12
    assert H.read_run_json(run_graine["dir"])["seed"] == H.SIM_NOMINAL["seed"] + 1
