"""M3a : recalcul Python INDÉPENDANT du pas annuel, depuis le seul texte des contrats et du plan (ADR 0004,
plan M3a §1, §2, §4) : d130 et statut en t0 + 1 pour les arbres de la chaîne nominale (14 080 arbres, voisinage
et disque de 15 m compris), puis sur des arbres fabriqués dont la géométrie est connue (disque de 15 m :
14,9 m compte, 15,1 m non ; relecture bornée aux nœuds ; coins de la grille)."""
import numpy as np
import pytest

import helpers_m3 as H

T0 = H.SIM_NOMINAL["t0"]
SEED = H.SIM_NOMINAL["seed"]


def _initiaux(chaine):
    return H.read_trees_init(chaine["dir"]).sort_values("tree_id", kind="stable").reset_index(drop=True)


def _aire_concordante(obs, pred_fn):
    """Si le d130 observé ne concorde pas avec l'aire du plan (706,858), dit si π × 15² concorde."""
    exact = pred_fn(H.AIRE_DISQUE_EXACTE)
    return float(np.abs(obs - exact).max())


# ------------------------------------------------------------------ d130 en t0 + 1 (chaîne nominale)
def test_d130_de_t0_plus_1_recalcule_a_1e_9(chaine, grid, params, init, arbres):
    """η = intercept + Σ f_v(x_v) + b_ser ; d130 += 2 exp(η), en moyenne, sans bruit (plan M3a §2, Q4). Les
    arbres dont le voisinage est ambigu dans le texte (voisin à 1 µm du rayon, diamètre égal) ne sont pas jugés."""
    p = H.predict_step(grid, params, init)
    a1 = arbres[arbres["year"] == T0 + 1].set_index("tree_id").loc[init["tree_id"]]
    vivants = (a1["status"] == "alive").to_numpy()
    jug = p["ok"] & vivants
    assert jug.sum() > 12_000, f"trop peu d'arbres jugés : {jug.sum()}"
    ecart = np.abs(a1["d130"].to_numpy() - p["d130"])
    pire = float(ecart[jug].max())
    if pire > H.TOL_D130:
        def alt(aire):
            return H.predict_step(grid, params, init, aire=aire)["d130"][jug]
        e_alt = _aire_concordante(a1["d130"].to_numpy()[jug], alt)
        i = int(np.argmax(np.where(jug, ecart, 0)))
        pytest.fail(f"d130 en t0+1 : écart max {pire:.3e} (> {H.TOL_D130}) sur {int((ecart[jug] > H.TOL_D130).sum())} "
                    f"arbres, par exemple {init['tree_id'][i]} observé {a1['d130'].iloc[i]!r} attendu {p['d130'][i]!r} ; "
                    f"avec π × 15² au lieu de {H.AIRE_DISQUE} l'écart max serait {e_alt:.3e}")


def test_le_recalcul_discrimine_les_variables_du_modele(grid, params, init):
    """Garde-fou de l'oracle : sans la concurrence (bal et ba_plot à 0) ou sans la station, la prédiction change
    de plus que la tolérance, donc le test ci-dessus ne passerait pas avec un moteur qui les oublie."""
    p = H.predict_step(grid, params, init)
    x, y, d, sp = (init[c].to_numpy() for c in ("x", "y", "d130", "species"))
    st = grid.station(x, y)
    ser = grid.ser_code(x, y)
    s = sp == "61"
    base = {"d130": d[s], "ba_plot": p["ba_plot"][s], "bal": p["bal"][s], **{k: a[s] for k, a in st.items()}}
    ref = params.eta("growth_gam", "61", base, ser[s])
    for var in ("ba_plot", "bal", "trophic", "coarse_hydric_700m", "coarse_bioclim_700m", "d130"):
        if var not in params.variables("growth_gam", "61"):
            continue
        v = dict(base)
        v[var] = np.zeros_like(v[var])
        diff = np.abs(2 * np.exp(params.eta("growth_gam", "61", v, ser[s])) - 2 * np.exp(ref)).max()
        assert diff > 1e-8, f"le recalcul ne dépend pas de {var} (écart {diff})"


def test_le_statut_de_t0_plus_1_recalcule_avec_ma_fonction_u(chaine, grid, params, init, arbres):
    """Meurt si u(seed, année, numéro d'arbre, essence, MORT) < p, p = 1 − exp(−exp(η)) (plan M3a §4 et « Aléa »).
    Ici la fonction u est celle du plan (SplitMix64 chaîné), écrite dans helpers_m3 ; aucune lecture du moteur."""
    p = H.predict_step(grid, params, init)
    a1 = arbres[arbres["year"] == T0 + 1].set_index("tree_id").loc[init["tree_id"]]
    obs_mort = (a1["status"] == "dead").to_numpy()
    sp = init["species"].to_numpy()

    def attendu(annee, base, big):
        return np.array([H.u_chained(SEED, annee, base + i, H.pack_species(sp[i], big), H.SORTES["MORT"]) < p["p_mort"][i]
                         for i in range(len(sp))])

    exp = attendu(T0 + 1, 0, True)
    jug = p["ok"]
    faux = int((exp != obs_mort)[jug].sum())
    if faux:
        autres = {}
        for annee in (T0, T0 + 1):
            for base in (0, 1):
                for big in (True, False):
                    autres[f"année={annee}, numéro depuis {base}, essence {'gros' if big else 'petit'}-boutiste"] = \
                        int((attendu(annee, base, big) != obs_mort)[jug].sum())
        pytest.fail(f"statut en t0+1 : {faux} arbres sur {int(jug.sum())} ne concordent pas avec la convention déclarée "
                    f"(année simulée, numéro 0.., essence en gros-boutiste) ; autres conventions, écarts : {autres}")
    assert obs_mort.sum() > 100 and exp[jug].sum() > 100, "test non discriminant : trop peu de morts"


def test_les_morts_de_t0_plus_1_suivent_la_probabilite_attendue(grid, params, init, arbres):
    """Indépendant de u : le nombre de morts observé est celui de Σ p (écart de 5 écarts-types au plus)."""
    p = H.predict_step(grid, params, init)
    a1 = arbres[arbres["year"] == T0 + 1].set_index("tree_id").loc[init["tree_id"]]
    n = int((a1["status"] == "dead").sum())
    mu = float(p["p_mort"].sum())
    sd = float(np.sqrt((p["p_mort"] * (1 - p["p_mort"])).sum()))
    assert abs(n - mu) < 5 * sd, f"{n} morts observés, {mu:.1f} ± {sd:.1f} attendus"


# ------------------------------------------------------------------ arbres fabriqués (géométrie connue)
def _etat_initial(zu):
    import pandas as pd
    return pd.DataFrame(zu["rows"]).sort_values("tree_id", kind="stable").reset_index(drop=True)


def test_simulate_tourne_sur_les_arbres_fabriques(zone_unitaire):
    assert zone_unitaire["proc"].returncode == 0, H.queue(zone_unitaire["proc"])


def test_d130_des_arbres_fabriques_recalcule_a_1e_9(zone_unitaire):
    zu = zone_unitaire
    ini = _etat_initial(zu)
    params = H.Params(zu["dir"])
    p = H.predict_step(zu["grid"], params, ini)
    a1 = H.read_year(zu["dir"], "trees", T0 + 1).set_index("tree_id").loc[ini["tree_id"]]
    jug = p["ok"] & (a1["status"] == "alive").to_numpy()
    assert jug.sum() >= len(ini) * 0.9
    ecart = np.abs(a1["d130"].to_numpy() - p["d130"])
    assert ecart[jug].max() < H.TOL_D130, \
        f"écart max {ecart[jug].max():.3e} sur {ini['tree_id'][int(np.argmax(np.where(jug, ecart, 0)))]}"


def test_le_disque_de_15_m_compte_14_9_et_pas_15_1(zone_unitaire):
    """Un voisin à 14,9 m (de plus gros diamètre) entre dans ba_plot et bal du focal ; à 15,1 m il n'y entre
    pas. Quatre directions (est, nord, ouest, sud) : un x et un y échangés se verraient."""
    zu = zone_unitaire
    ini = _etat_initial(zu)
    params = H.Params(zu["dir"])
    a1 = H.read_year(zu["dir"], "trees", T0 + 1).set_index("tree_id")
    for g in zu["meta"]["grappes"]:
        seul = ini[ini["tree_id"] == g["focal"]].reset_index(drop=True)
        avec = H.predict_step(zu["grid"], params, ini)
        i = int(ini.index[ini["tree_id"] == g["focal"]][0])
        d_seul = H.predict_step(zu["grid"], params, seul)["d130"][0]
        d_avec = avec["d130"][i]
        dedans = g["nom"].endswith("dedans") and not g["nom"].endswith("dehors")
        if dedans:
            assert abs(d_avec - d_seul) > 1e-8, f"{g['nom']} : test non discriminant (voisin sans effet)"
        else:
            assert abs(d_avec - d_seul) < 1e-12, f"{g['nom']} : le voisin à 15,1 m devrait être hors disque"
        obs = a1.loc[g["focal"], "d130"]
        assert abs(obs - d_avec) < H.TOL_D130, \
            f"{g['nom']} : observé {obs!r}, attendu {d_avec!r} ({'avec' if dedans else 'sans'} le voisin), " \
            f"sans voisin {d_seul!r}"


def test_une_valeur_hors_des_noeuds_est_bornee_et_comptee(zone_unitaire):
    """Un arbre de 400 cm : la relecture tient la valeur du nœud extrême (contrat), et run.json compte la sortie
    de domaine ; le d130 reste celui du recalcul borné."""
    zu = zone_unitaire
    cid = zu["meta"]["hors_domaine"]
    assert cid is not None, "arbre hors domaine non fabriqué"
    ini = _etat_initial(zu)
    row = ini[ini["d130"] > 300].iloc[0]
    params = H.Params(zu["dir"])
    p = H.predict_step(zu["grid"], params, ini)
    i = int(ini.index[ini["tree_id"] == row["tree_id"]][0])
    a1 = H.read_year(zu["dir"], "trees", T0 + 1).set_index("tree_id")
    if a1.loc[row["tree_id"], "status"] == "alive":
        assert abs(a1.loc[row["tree_id"], "d130"] - p["d130"][i]) < H.TOL_D130
    run = H.read_run_json(zu["dir"])
    assert run["domain_outputs"]["d130"]["above"] >= 1, run["domain_outputs"]["d130"]


def test_les_coins_de_la_grille_tombent_dans_les_bonnes_cellules(zone_unitaire):
    """Piège de la Somalie : x (est) et y (nord) pas échangés, ligne comptée depuis le nord. L'arbre en
    (700 012,5 ; 6 500 987,5) est dans cell_id 0 ; les trois autres coins valent 39, 1560 et 1599."""
    zu = zone_unitaire
    attendus = {0: (700_012.5, 6_500_987.5), 39: (700_987.5, 6_500_987.5),
                1560: (700_012.5, 6_500_012.5), 1599: (700_987.5, 6_500_012.5)}
    coins = {c["cell_id"]: c for c in zu["meta"]["coins"]}
    assert set(coins) == set(attendus)
    for cid, (x, y) in attendus.items():
        assert (coins[cid]["x"], coins[cid]["y"]) == (x, y)
    c0 = H.read_year(zu["dir"], "cells", T0)
    for cid, (x, y) in attendus.items():
        lignes = c0[(c0["cell_id"] == cid) & (c0["species"] == "61")]
        assert len(lignes) == 1, f"cell_id {cid} : {len(lignes)} lignes pour l'essence 61 en t0"
        assert abs(lignes["stems_ha"].iloc[0] - 1 / H.AIRE_CELLULE_HA) < 1e-9, lignes.to_dict("records")
        g = np.pi * (45.0 / 200.0) ** 2 / H.AIRE_CELLULE_HA
        assert abs(lignes["basal_area_m2_ha"].iloc[0] - g) < 1e-9
        assert abs(lignes["d130_mean"].iloc[0] - 45.0) < 1e-9


def test_toutes_les_cellules_de_t0_sont_celles_des_arbres_fabriques(zone_unitaire):
    zu = zone_unitaire
    ini = _etat_initial(zu)
    ini["cell_id"] = zu["grid"].cell_id(ini["x"], ini["y"])
    attendu = ini.groupby(["cell_id", "species"]).size() / H.AIRE_CELLULE_HA
    c0 = H.read_year(zu["dir"], "cells", T0)
    c0 = c0[c0["stems_ha"] > 0].set_index(["cell_id", "species"])["stems_ha"]
    assert set(c0.index) == set(attendu.index), (len(c0), len(attendu))
    assert np.abs(c0.loc[attendu.index].to_numpy() - attendu.to_numpy()).max() < 1e-9


def test_un_arbre_de_la_chaine_tombe_dans_la_cellule_de_la_formule(chaine, grid, arbres):
    """Sur la zone réelle de la chaîne, chaque arbre de t0 est compté dans le cell_id de la formule
    (ligne × largeur + colonne, ligne depuis le nord) : somme des tiges par cellule = celle des arbres."""
    a0 = arbres[arbres["year"] == T0]
    attendu = a0.groupby(grid.cell_id(a0["x"], a0["y"]).tolist()).size() / H.AIRE_CELLULE_HA
    c0 = H.read_year(chaine["dir"], "cells", T0).groupby("cell_id")["stems_ha"].sum()
    c0 = c0[c0 > 0]
    assert set(c0.index) == set(attendu.index)
    assert np.abs(c0.loc[attendu.index].to_numpy() - attendu.to_numpy()).max() < 1e-9


def test_le_niveau_de_ser_est_relu_par_le_code_de_ser_pas_par_l_alluvion(zone_unitaire):
    """Le jeu fictif n'a aucun terme ser_code= : la zone fabriquée en ajoute un pour H10 (croissance +0,15,
    mortalité +0,4). Les deux valeurs de ser.tif (1 : H10 ; 2 : H10 sous alluvions L3) lisent ce même niveau. Le
    recalcul du test 'd130 des arbres fabriqués' le contient ; ici on prouve qu'il pèse, donc qu'il discrimine."""
    zu = zone_unitaire
    ini = _etat_initial(zu)
    params = H.Params(zu["dir"])
    assert (params.df["term"] == "ser_code=H10").sum() >= 5
    ser = zu["grid"].ser_code(ini["x"].to_numpy(), ini["y"].to_numpy())
    assert set(ser) == {"H10"}, set(ser)
    s = ini["species"].to_numpy() == "61"
    st = zu["grid"].station(ini["x"].to_numpy(), ini["y"].to_numpy())
    v = {"d130": ini["d130"].to_numpy()[s], "ba_plot": np.full(s.sum(), 20.0), "bal": np.full(s.sum(), 5.0),
         **{k: a[s] for k, a in st.items()}}
    avec = params.eta("growth_gam", "61", v, ser[s])
    sans = params.eta("growth_gam", "61", v, np.array([""] * s.sum(), dtype=object))
    assert np.abs(np.exp(avec) - np.exp(sans)).min() > 1e-3
