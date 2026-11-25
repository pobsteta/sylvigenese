"""M3a, hauteur (spec §5, plan M3a §3, décisions de Pascal Q1 et Q2) sur des arbres fabriqués : un arbre seul dans
sa cellule, date de vol de chm_date = 1er janvier de t0 + 1 (l'état initial est la fin de l'année t0, journal du 25/11/2026), donc H_dom(t0) = h0 de la cellule.

Décision de Pascal (Q2) : chaque arbre grandit de sa part f(rel_d) de ΔH_dom, f = relative_height_gam (lien identité)
relue aux nœuds. Un arbre SEUL dans sa cellule a rel_d = 1, mais f(1) n'est pas forcément 1 : le pas attendu est
f(1) × ΔH_dom (H.part_arbre_seul). Ce que le plan fixe sans
ambiguïté (plafond, pas exact de Chapman-Richards, Korf du hêtre, dH >= 0, ancre sans saut) est testé exactement."""
import numpy as np
import pytest

import helpers_m3 as H

T0 = H.SIM_NOMINAL["t0"]


def _h(zu, annee):
    return H.read_year(zu["dir"], "trees", annee)


def _init(zu):
    return H.Tab.from_records(zu["rows"])


def test_l_ancre_la_hauteur_de_t0_est_la_hauteur_mesuree(zone_unitaire):
    """Q2 : « sans saut au départ ». Avec la date de vol au 1er janvier de t0 + 1 (fin de l'année t0), rien à avancer : h(t0) = mesure."""
    zu = zone_unitaire
    assert zu["proc"].returncode == 0, H.queue(zu["proc"])
    ini, h0 = _init(zu), _h(zu, T0)
    ecart = np.abs(h0.align(ini["tree_id"])["h"] - ini["h"])
    assert ecart.max() < 1e-9, f"h(t0) s'écarte de la mesure de {ecart.max():.3e}"


def test_au_plafond_la_hauteur_ne_bouge_pas_et_n_est_jamais_corrigee(zone_unitaire):
    """H_dom >= A (site_potential) : dH = 0, sans fonction min. Une hauteur au-dessus du plafond reste telle quelle
    (CLAUDE.md : signalée, jamais corrigée), de t0 à la fin."""
    zu = zone_unitaire
    ini = _init(zu)
    assert len(zu["meta"]["plafond"]) >= 10
    for annee in range(T0, T0 + 4):
        h = _h(zu, annee)
        for t in zu["meta"]["plafond"]:
            if not h.has(t["tree_id"]):
                continue                                  # mort avant : écrit une fois puis plus
            assert abs(h.at(t["tree_id"], "h") - ini.at(t["tree_id"], "h")) < 1e-9, \
                f"{t['tree_id']} (cellule {t['cell_id']}, h0 {t['h0']:.2f} >= A {t['A']:.2f}) bouge en {annee}"
            assert h.at(t["tree_id"], "h") >= t["A"] - 1e-9
    assert any(_h(zu, T0 + 3).has(t["tree_id"]) for t in zu["meta"]["plafond"])


def test_le_plafond_est_signale_dans_les_signalements_et_dans_run_json(zone_unitaire):
    import pyarrow.parquet as pq
    zu = zone_unitaire
    flags = H.Tab.from_arrow(pq.read_table(zu["dir"] / "sim" / "flags.parquet"))
    cellules = set(flags["entity"].tolist())
    manque = [t["cell_id"] for t in zu["meta"]["plafond"] if str(t["cell_id"]) not in cellules]
    assert not manque, f"cellules au plafond non signalées : {manque[:5]}"
    assert H.read_run_json(zu["dir"])["cells_at_height_ceiling"] >= len(zu["meta"]["plafond"])


def _pas_chapman_richards(zu, params, t):
    k, p = params.scalar("chapman_richards", t["species"], "k"), params.scalar("chapman_richards", t["species"], "p")
    return H.part_arbre_seul(params, t["species"]) * (float(H.chapman_richards_step(t["h0"], t["A"], k, p)) - t["h0"])


@pytest.mark.parametrize("essence", ["61", "62", "03", "64"])
def test_la_hauteur_suit_le_pas_exact_de_chapman_richards(zone_unitaire, essence):
    """H(t+1) − H(t) sur la courbe de l'essence, A = site_potential, depuis H_dom = h0 (plan §3), à 1e-9."""
    zu = zone_unitaire
    params = H.Params(zu["dir"])
    arbres = [t for t in zu["meta"]["isoles"] if t["species"] == essence]
    assert len(arbres) >= 5, f"{len(arbres)} arbres isolés d'essence {essence}"
    h_t0, h_t1 = _h(zu, T0), _h(zu, T0 + 1)
    jug = 0
    for t in arbres:
        if not h_t1.has(t["tree_id"]) or h_t1.at(t["tree_id"], "status") != "alive":
            continue
        att = _pas_chapman_richards(zu, params, t)
        assert att > 1e-4, f"test non discriminant : dH attendu {att}"
        obs = h_t1.at(t["tree_id"], "h") - h_t0.at(t["tree_id"], "h")
        assert abs(obs - att) < 1e-9, (f"{t['tree_id']} (essence {essence}, h0 {t['h0']:.3f}, A {t['A']:.3f}) : "
                                       f"dh observé {obs!r}, attendu {att!r}, rapport {obs / att:.6f}")
        jug += 1
    assert jug >= 4


def test_la_hauteur_ne_decroit_jamais_sur_les_arbres_fabriques(zone_unitaire):
    zu = zone_unitaire
    prev = _h(zu, T0)
    for annee in (T0 + 1, T0 + 2, T0 + 3):
        cur = _h(zu, annee)
        communs = [t for t in prev["tree_id"].tolist() if cur.has(t)]
        assert communs
        assert (cur.align(communs)["h"] >= prev.align(communs)["h"] - 1e-12).all(), f"h baisse en {annee}"
        prev = cur


# ------------------------------------------------------------------ le hêtre et sa courbe de Korf (Pascal, Q1)
def _korf(params, essence="09"):
    r = params.rows("korf", essence)
    assert r is not None, ("aucune ligne `korf` pour le hêtre 09 dans params/height_curve.parquet : la courbe de Korf "
                           "de la mission 034 manque (contrat dynamics_params, modèle korf)")
    a, b, c = (params.scalar("korf", essence, k) for k in "abc")
    pf = [params.scalar("korf", essence, f"p_f_class{i}") for i in range(1, 6)]
    for k in ("t_ref0", "h_ref0", "age_ref"):
        params.scalar("korf", essence, k)               # point de départ du choix de classe (mission 040)
    return a, b, c, pf


def test_la_courbe_de_korf_du_hetre_est_dans_les_parametres(zone_unitaire):
    params = H.Params(zone_unitaire["dir"])
    a, b, c, pf = _korf(params)
    assert a > 20 and b > 0 and c > 0
    assert all(pf[i] >= pf[i + 1] for i in range(4)), f"p_f doit décroître de la classe 1 à la classe 5 : {pf}"
    assert params.rows("korf", "09")["provisoire"].all(), "les termes de Korf sont provisoires (contrat)"


def test_le_hetre_suit_la_courbe_de_korf_de_sa_classe_et_pas_chapman_richards(zone_unitaire):
    """Classe de fertilité = celle dont la hauteur à age_ref (formule avancée d'un an depuis h_ref0 à t_ref0) est la
    plus proche de site_potential (contrat, mission 040) ; le pas observé égale le pas de Korf de cette classe (1e-9),
    et jamais celui de Chapman-Richards. Les cinq classes donnent des pas distincts : le test est discriminant."""
    zu = zone_unitaire
    params = H.Params(zu["dir"])
    a, b, c, pf = _korf(params)
    h_t0, h_t1 = _h(zu, T0), _h(zu, T0 + 1)
    classes, jug = set(), 0
    for t in zu["meta"]["isoles"]:
        if t["species"] != "09" or not h_t1.has(t["tree_id"]) or h_t1.at(t["tree_id"], "status") != "alive" \
                or not 0 < t["h0"] < a:
            continue
        cl = H.korf_class_for(params, t["A"])
        obs = h_t1.at(t["tree_id"], "h") - h_t0.at(t["tree_id"], "h")
        f = H.part_arbre_seul(params, "09")
        pas = [f * (float(H.korf_step(t["h0"], a, b, c, p)) - t["h0"]) for p in pf]
        assert len({round(p, 6) for p in pas}) == 5, f"classes de Korf indiscernables à h0 {t['h0']} : {pas}"
        assert abs(obs - pas[cl - 1]) < 1e-9, \
            (f"{t['tree_id']} (h0 {t['h0']:.3f}, site_potential {t['A']:.3f}) : classe attendue {cl} (pas {pas[cl - 1]!r}), "
             f"dh observé {obs!r}, concorde avec les classes {[i + 1 for i, d in enumerate(pas) if abs(obs - d) < 1e-9]}")
        if params.rows("chapman_richards", "09") is not None:
            k, p = params.scalar("chapman_richards", "09", "k"), params.scalar("chapman_richards", "09", "p")
            cr = f * (float(H.chapman_richards_step(t["h0"], t["A"], k, p)) - t["h0"])
            assert abs(obs - cr) > 1e-6, f"{t['tree_id']} : le hêtre suit Chapman-Richards au lieu de Korf"
        classes.add(cl)
        jug += 1
    assert jug >= 4, f"seulement {jug} hêtres jugés"


def test_les_autres_essences_ne_suivent_pas_korf(zone_unitaire):
    """Korf est celui du hêtre seul : le chêne (03) garde Chapman-Richards (déjà exigé à 1e-9 ci-dessus) ; ici on
    s'assure que Korf ne le décrit PAS, donc que le test du hêtre sépare bien les deux courbes."""
    zu = zone_unitaire
    params = H.Params(zu["dir"])
    a, b, c, pf = _korf(params)
    h_t0, h_t1 = _h(zu, T0), _h(zu, T0 + 1)
    for t in (t for t in zu["meta"]["isoles"] if t["species"] == "03" and 0 < t["h0"] < a):
        if not h_t1.has(t["tree_id"]):
            continue
        obs = h_t1.at(t["tree_id"], "h") - h_t0.at(t["tree_id"], "h")
        f = H.part_arbre_seul(params, "03")
        assert all(abs(obs - f * (float(H.korf_step(t["h0"], a, b, c, p)) - t["h0"])) > 1e-9 for p in pf), \
            f"{t['tree_id']} (chêne) suit une classe de Korf"
