"""Suite de M4a (mission 045) : une instance par arbre VIVANT de l'année, à sa position, aucun mort dessiné ; t0
vient lui aussi de sim/ (T4 : h de sim, rayon = cw / 2) ; piège de la Somalie (plan §2 mission B, T4, T5)."""
import numpy as np
import pytest

import helpers_m4 as H
import helpers_m4_temps as T

ANNEES = T.retained_years(T.T0, T.YEARS, T.STEP)


@pytest.mark.parametrize("annee", ANNEES)
def test_une_instance_par_arbre_vivant_a_sa_position(temps_instances, annee):
    e = temps_instances[annee]
    tr, m = e["trees"], e["match"]
    vivants = np.nonzero(tr["status"] == "alive")[0]
    n = len(e["inst"]["world"])
    assert n == len(vivants), f"{annee} : {n} instances pour {len(vivants)} arbres vivants"
    assert m["n_ok"] == n, f"{annee} : {n - m['n_ok']} instances à plus de {H.POS_TOL} m de tout arbre (repère {m['frame']})"
    assert sorted(m["tree_of"].tolist()) == sorted(vivants.tolist()), \
        f"{annee} : les instances ne sont pas les arbres vivants, un pour un"
    assert float(m["resid"].max()) <= H.POS_TOL


@pytest.mark.parametrize("annee", ANNEES)
def test_aucun_mort_n_est_dessine(temps_instances, annee):
    e = temps_instances[annee]
    tr, m = e["trees"], e["match"]
    sur_mort = [int(i) for i in m["tree_of"] if i >= 0 and tr["status"][i] == "dead"]
    assert not sur_mort, f"{annee} : {len(sur_mort)} instances dessinent un arbre mort ({tr['tree_id'][sur_mort[0]]})"


def test_il_y_a_des_morts_et_des_recrues_sur_les_annees_retenues(temps_instances):
    # Garde du pouvoir des tests ci-dessus : sans mort ni recrue, ils ne discrimineraient rien.
    last = temps_instances[ANNEES[-1]]["trees"]
    assert (last["status"] == "dead").sum() > 0
    t0_ids = set(temps_instances[ANNEES[0]]["trees"]["tree_id"].tolist())
    assert len(set(last["tree_id"].tolist()) - t0_ids) > 0, "aucune recrue en 2037"


@pytest.mark.parametrize("annee", ANNEES)
def test_chaque_instance_est_dans_la_tuile_de_son_arbre(temps_instances, annee):
    e = temps_instances[annee]
    ok = e["match"]["tree_of"] >= 0
    tr = e["trees"]
    attendu = T.tile_name(tr["x"][e["match"]["tree_of"][ok]], tr["y"][e["match"]["tree_of"][ok]])
    faux = int((e["inst"]["tile"][ok] != attendu).sum())
    assert faux == 0, f"{annee} : {faux} instances dans une autre tuile que celle de leur arbre"


def test_x_et_y_ne_sont_pas_inverses(temps_instances):
    # Piège de la Somalie (CLAUDE.md) : aucune instance au miroir (y, x) de son arbre quand il est loin de la diagonale.
    e = temps_instances[ANNEES[-1]]
    m, tr = e["match"], e["trees"]
    ok = m["tree_of"] >= 0
    ti = m["tree_of"][ok]
    lx, ly = tr["x"][ti] - H.X0, tr["y"][ti] - (H.Y0 - 1000.0)
    mx, my = m["xy"][ok, 0] - H.X0, m["xy"][ok, 1] - (H.Y0 - 1000.0)
    loin = np.abs(lx - ly) > 5.0
    assert loin.sum() > 1000
    assert (np.hypot(mx - ly, my - lx)[loin] > 1.0).all()


def _rapports(temps_instances):
    """Par modèle : scale_y / h et scale_x / (cw / 2) de toutes les instances de toutes les années retenues."""
    out = {}
    for y, e in temps_instances.items():
        ok = e["match"]["tree_of"] >= 0
        ti = e["match"]["tree_of"][ok]
        sc, mo = e["inst"]["scale"][ok], e["inst"]["model"][ok]
        for mod in set(mo.tolist()):
            s = mo == mod
            d = out.setdefault(mod, {"h": [], "r": [], "z": []})
            d["h"].append(sc[s, 1] / e["trees"]["h"][ti][s])
            d["r"].append(sc[s, 0] / (e["trees"]["cw"][ti][s] / 2.0))
            d["z"].append(sc[s, 2] / sc[s, 0])
    return {k: {n: np.concatenate(v) for n, v in d.items()} for k, d in out.items()}


def test_t0_et_les_annees_simulees_ont_la_meme_echelle_hauteur_de_sim(temps_instances):
    # T4 : la hauteur dessinée, t0 compris, est h de sim/trees (le rapport scale_y / h ne change pas d'une année à l'autre).
    for mod, d in _rapports(temps_instances).items():
        r = d["h"]
        assert np.isfinite(r).all() and r.min() > 0
        assert r.max() / r.min() < 1.01, f"modèle {mod} : scale_y / h varie de {r.min():.4f} à {r.max():.4f}"


def test_t0_et_les_annees_simulees_ont_le_rayon_cw_sur_2(temps_instances):
    # T4 : rayon de houppier = cw / 2 pour toutes les années, t0 compris (et non crown_area de trees_init) ; SCALE = (r, h, r).
    for mod, d in _rapports(temps_instances).items():
        r = d["r"][np.isfinite(d["r"])]
        assert len(r) and r.min() > 0
        assert r.max() / r.min() < 1.01, f"modèle {mod} : scale_x / (cw / 2) varie de {r.min():.4f} à {r.max():.4f}"
        assert np.allclose(d["z"], 1.0, rtol=1e-5), f"modèle {mod} : SCALE n'est pas (r, h, r)"


def test_chaque_classe_essence_stade_a_son_modele_apres_simulation(temps_instances, temps):
    # M6a (mission 069) : comme test_m4_instances, sur la dernière année simulée ; stade de l'arbre = h / h_pot (Q8).
    e = temps_instances[ANNEES[-1]]
    ok = e["match"]["tree_of"] >= 0
    t = e["trees"]
    idx = e["match"]["tree_of"][ok]
    cl, franc = H.model_classes(temps["dir"], t["species"][idx], t["x"][idx], t["y"][idx], t["h"][idx])
    mo = e["inst"]["model"][ok]
    par = {}
    for c, f, k in zip(cl, franc, mo):
        if f:
            par.setdefault(c, set()).add(k)
    assert all(len(v) == 1 for v in par.values()), {c: len(v) for c, v in par.items() if len(v) > 1}
    modeles = [next(iter(v)) for v in par.values()]
    assert len(set(modeles)) == len(modeles), "deux classes différentes partagent un modèle"


def test_les_essences_de_sim_sont_au_referentiel(temps_instances):
    groupe = H.species_group()
    for y, e in temps_instances.items():
        hors = sorted(set(map(str, e["trees"]["species"].tolist())) - set(groupe))
        assert not hors, f"{y} : essences hors de contracts/species.csv : {hors}"
        assert set(e["trees"]["status"].tolist()) <= {"alive", "dead"}
