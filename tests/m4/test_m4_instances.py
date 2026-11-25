"""Une instance par arbre de trees_init, à sa place, à sa taille (fiche 028 ; spec §4.3, §9 ; CLAUDE.md :
piège de la Somalie, x et y inversés, repère juste)."""
import numpy as np
import pytest

import helpers_m4 as H


def test_la_conversion_lambert93_de_l_oracle_est_juste():
    # Garde de l'oracle (pas de pyproj) : origine de la projection et point connu de l'IGN (Paris).
    lon, lat = H.lambert93_inverse(700000.0, 6600000.0)
    assert abs(lon - 3.0) < 1e-9 and abs(lat - 46.5) < 1e-9
    x, y = H.lambert93_forward(2.3522, 48.8566)
    assert abs(x - 652469.0) < 1 and abs(y - 6862035.0) < 1


def test_une_instance_par_arbre_nombre_exact(instances, oracle):
    n = len(instances["inst"]["world"])
    assert n == oracle.n_trees == 14080, f"{n} instances pour {oracle.n_trees} arbres dans trees_init"


def test_chaque_instance_tombe_sur_un_arbre_de_trees_init_et_un_seul(instances, oracle):
    m = instances["match"]
    assert m is not None, "aucune instance"
    assert m["n_ok"] == len(m["tree_of"]), f"{len(m['tree_of']) - m['n_ok']} instances sans arbre à cette place (repère {m['frame']})"
    assert len(set(m["tree_of"].tolist())) == oracle.n_trees, "des arbres ont deux instances, d'autres aucune"


def test_positions_justes_au_dixieme_de_metre(instances):
    m = instances["match"]
    assert m is not None
    assert float(np.max(m["resid"])) <= H.POS_TOL, \
        f"écart horizontal maximal {np.max(m['resid']):.3f} m (repère reconnu : {m['frame']}) > {H.POS_TOL} m"


def test_positions_de_quatre_arbres_aux_extremites_recalculees(instances, oracle):
    # Les extrémités (nord, sud, est, ouest) attrapent un x/y inversé, un miroir ou un décalage d'origine.
    m, inst = instances["match"], instances["inst"]
    t = oracle.trees
    chosen = {"nord": int(np.argmax(t["y"])), "sud": int(np.argmin(t["y"])),
              "est": int(np.argmax(t["x"])), "ouest": int(np.argmin(t["x"]))}
    inst_of_tree = {int(ti): ii for ii, ti in enumerate(m["tree_of"]) if ti >= 0}
    for nom, ti in chosen.items():
        assert ti in inst_of_tree, f"arbre {nom} ({t['tree_id'][ti]}) sans instance"
        xy = m["xy"][inst_of_tree[ti]]
        dx, dy = xy[0] - t["x"][ti], xy[1] - t["y"][ti]
        assert np.hypot(dx, dy) <= H.POS_TOL, \
            f"arbre {nom} {t['tree_id'][ti]} attendu en ({t['x'][ti]:.2f}; {t['y'][ti]:.2f}), instance en ({xy[0]:.2f}; {xy[1]:.2f}), repère {m['frame']}"


def test_le_repere_est_ecef_ou_lambert93(instances):
    # Le test ne choisit pas : il exige que l'un des deux soit juste (voir helpers_m4, en-tête).
    m = instances["match"]
    assert m is not None and m["frame"] in ("ECEF", "EPSG:2154")
    assert m["n_ok"] == len(m["tree_of"])


def test_x_et_y_ne_sont_pas_inverses(instances, oracle):
    # Une inversion de x et y (piège de la Somalie, CLAUDE.md) renverrait chaque arbre à son miroir par rapport
    # à la diagonale du massif carré. Aucune instance ne doit être au miroir de son arbre quand il en est loin.
    m = instances["match"]
    t = oracle.trees
    ok = m["tree_of"] >= 0
    ti = m["tree_of"][ok]
    lx, ly = t["x"][ti] - H.X0, t["y"][ti] - (H.Y0 - 1000.0)       # mètres locaux de l'arbre
    mx, my = m["xy"][ok, 0] - H.X0, m["xy"][ok, 1] - (H.Y0 - 1000.0)
    loin = np.abs(lx - ly) > 5.0                                    # arbres hors de la diagonale
    assert loin.sum() > 1000
    assert (np.hypot(mx - ly, my - lx)[loin] > 1.0).all(), "des instances sont au miroir (x, y) de leur arbre"


def test_aucune_instance_hors_du_massif(instances):
    m = instances["match"]
    xy = m["xy"]
    assert xy[:, 0].min() >= H.X0 - 1 and xy[:, 0].max() <= H.X0 + 1001
    assert xy[:, 1].min() >= H.Y0 - 1001 and xy[:, 1].max() <= H.Y0 + 1


def test_echelle_croit_avec_la_hauteur_dans_chaque_modele(instances, oracle):
    # « Échelle croissante avec h » : dans un même modèle, l'échelle verticale (Y glTF) suit le rang de h.
    inst, m = instances["inst"], instances["match"]
    ok = m["tree_of"] >= 0
    h = oracle.trees["h"][m["tree_of"][ok]]
    sy = inst["scale"][ok, 1]
    models = inst["model"][ok]
    assert (sy > 0).all(), "échelle verticale nulle ou négative"
    for mod in sorted(set(models)):
        sel = models == mod
        o = np.argsort(h[sel], kind="stable")
        s = sy[sel][o]
        assert np.all(np.diff(s) >= -1e-6 * s.max()), f"modèle {mod} : l'échelle décroît quand h croît"
        assert s[-1] > s[0], f"modèle {mod} : l'échelle ne dépend pas de h"


def test_echelle_verticale_proportionnelle_a_h_dans_chaque_modele(instances, oracle):
    # Fiche 028 : « hauteur proportionnelle à h » (valeur provisoire) : scale_y / h constant dans un modèle.
    inst, m = instances["inst"], instances["match"]
    ok = m["tree_of"] >= 0
    h = oracle.trees["h"][m["tree_of"][ok]]
    sy = inst["scale"][ok, 1]
    models = inst["model"][ok]
    for mod in sorted(set(models)):
        r = sy[models == mod] / h[models == mod]
        assert r.max() / r.min() < 1.01, f"modèle {mod} : scale_y/h varie de {r.min():.4f} à {r.max():.4f}"


def test_les_deux_groupes_ont_chacun_leur_modele(instances, oracle):
    # Feuillu (03, 09) et résineux (61, 62, 64) : un modèle par groupe, pas de mélange.
    inst, m = instances["inst"], instances["match"]
    groupe = H.species_group()
    ok = m["tree_of"] >= 0
    g = np.array([groupe[str(s)] for s in oracle.trees["species"][m["tree_of"][ok]]])
    models = inst["model"][ok]
    par_groupe = {gr: set(models[g == gr]) for gr in ("feuillu", "resineux")}
    assert all(len(v) == 1 for v in par_groupe.values()), f"modèles par groupe : {par_groupe}"
    assert par_groupe["feuillu"] != par_groupe["resineux"], "feuillus et résineux ont le même modèle"


def test_les_essences_de_trees_init_ont_un_groupe_au_referentiel(oracle):
    groupe = H.species_group()
    manquantes = sorted({str(s) for s in oracle.trees["species"]} - set(groupe))
    assert not manquantes, f"essences hors de contracts/species.csv : {manquantes}"
