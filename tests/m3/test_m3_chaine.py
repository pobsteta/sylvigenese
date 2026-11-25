"""M3a, critère « 100 ans sur le massif fictif » (spec §11) : la chaîne `make prepare biomes trees dynamics
simulate`, le validateur, les partitions, les règles d'état (clé, d130, mortalité, recrues), les cellules."""
import math
import re

import numpy as np
import pytest

import helpers_m3 as H

T0 = H.SIM_NOMINAL["t0"]
ANNEES = H.SIM_NOMINAL["years"]
ESPECES_FICTIF = {"03", "09", "61", "62", "64"}


queue = H.queue


# ------------------------------------------------------------------ la chaîne
def test_la_chaine_complete_sort_avec_le_code_0(chaine):
    assert chaine["make"].returncode == 0, queue(chaine["make"])


def test_le_t0_du_depot_est_l_annee_du_dernier_vol():
    """config.yml (t0 = 2022) et le jeu fictif disent la même année : celle de la date de vol la plus récente de
    chm_date.tif ; la hauteur ne se recule pas, donc t0 ne peut être antérieur à un vol."""
    assert H.DEPOT["t0"] == H._annee_du_dernier_vol() == 2022, (H.DEPOT["t0"], H._annee_du_dernier_vol())


def test_la_config_du_depot_tourne_sur_le_jeu_fictif(run_depot):
    """Le bloc simulate de config.yml, tel quel (t0 = 2022), tourne sur le jeu fictif : code 0."""
    assert run_depot["proc"].returncode == 0, queue(run_depot["proc"])


def test_le_validateur_est_vert_sur_toute_la_zone(chaine):
    """Sans --require-outputs : post et assets ne tournent pas en M3a ; les sorties de simulate, elles, sont exigées une à une ci-dessous."""
    r = H.run_validate("--zone", str(chaine["dir"]))
    assert r.returncode == 0, queue(r)


@pytest.mark.parametrize("contrat,chemin", [("sim_trees", "sim/trees"), ("sim_cells", "sim/cells"),
                                              ("run", "sim/run.json"), ("sim_flags", "sim/flags.parquet")])
def test_le_validateur_est_vert_sur_chaque_sortie(chaine, contrat, chemin):
    p = chaine["dir"] / chemin
    assert p.exists(), f"{chemin} absent"
    r = H.run_validate(contrat, str(p))
    assert r.returncode == 0, queue(r)


def test_la_simulation_dure_moins_de_30_minutes(chaine):
    """CLAUDE.md : rejouable sur le massif test en moins de 30 minutes (la durée est celle de run.json)."""
    assert H.read_run_json(chaine["dir"])["duration_s"] < 1800


# ------------------------------------------------------------------ partitions
def test_partitions_de_trees_de_t0_a_t0_plus_100(chaine):
    ann = sorted(H.partitions(chaine["dir"], "trees"))
    assert ann == list(range(T0, T0 + ANNEES + 1)), f"partitions trouvées : {ann[:3]}...{ann[-3:]} ({len(ann)})"


def test_partitions_de_cells_de_t0_a_t0_plus_100(chaine):
    ann = sorted(H.partitions(chaine["dir"], "cells"))
    assert ann == list(range(T0, T0 + ANNEES + 1)), f"partitions trouvées : {ann[:3]}...{ann[-3:]} ({len(ann)})"


def test_aucune_partition_vide(chaine):
    for kind in ("trees", "cells"):
        parts = H.partitions(chaine["dir"], kind)
        assert parts, f"sim/{kind} sans aucune partition year=AAAA"
        for y, files in parts.items():
            assert files, f"sim/{kind}/year={y} sans fichier .parquet"


@pytest.mark.parametrize("kind", ["trees", "cells"])
def test_l_annee_n_est_que_dans_le_nom_du_dossier(chaine, arbres, kind):
    """Convention Hive (contrat et validateur) : aucun fichier de sim/trees ni de sim/cells ne porte de colonne
    `year` ; l'année se lit du dossier year=AAAA, comme un jeu de données partitionné (pyarrow.dataset)."""
    avec = H.fichiers_sans_year(chaine["dir"], kind)
    assert not avec, f"{len(avec)} fichiers portent une colonne year, par exemple {avec[:2]}"
    if kind == "trees":
        assert arbres["year"].min() == T0 and arbres["year"].max() == T0 + ANNEES


def test_tree_id_et_annee_forment_une_cle_unique(arbres):
    n = H.cles_en_double(arbres["tree_id"], arbres["year"])
    assert n == 0, f"{n} lignes dont la clé (tree_id, year) est en double"


def test_cell_id_year_species_est_une_cle_unique_des_cellules(chaine):
    for y in (T0, T0 + 1, T0 + 50, T0 + ANNEES):
        c = H.read_year(chaine["dir"], "cells", y)
        assert H.cles_en_double(c["cell_id"], c["year"], c["species"]) == 0, f"clé en double en {y}"


# ------------------------------------------------------------------ codes des référentiels, piège de la Somalie
def test_essences_et_statuts_appartiennent_aux_referentiels(arbres, params):
    ref = set(H.species_groups())
    vues = set(np.unique(arbres["species"]).tolist())
    assert not vues - ref, f"essences hors contracts/species.csv : {vues - ref}"
    assert not vues - params.species_set(), f"essences sans paramètres : {vues - params.species_set()}"
    assert set(np.unique(arbres["status"]).tolist()) <= {"alive", "dead"}, set(np.unique(arbres["status"]).tolist())
    assert all(re.fullmatch(r"[0-9]{2}[A-Z0-9]{0,3}", s) for s in vues)


def test_les_arbres_sont_dans_l_emprise_x_est_y_nord(arbres, grid):
    """Piège de la Somalie : x (est) et y (nord) ne sont pas inversés ; tout est dans l'emprise EPSG:2154."""
    x, y = arbres["x"], arbres["y"]
    assert x.min() >= grid.x0 and x.max() <= grid.x1, (x.min(), x.max())
    assert y.min() >= grid.y1 and y.max() <= grid.y0, (y.min(), y.max())
    assert (y > x).all()     # Lambert-93 : y vaut ~6,5 millions, x ~0,7 million


def test_les_cellules_sont_dans_la_grille(chaine, grid):
    for y in (T0, T0 + ANNEES):
        c = H.read_year(chaine["dir"], "cells", y)
        assert c["cell_id"].min() >= 0 and c["cell_id"].max() <= grid.ncols * grid.nrows - 1
        assert set(np.unique(c["species"]).tolist()) <= set(H.species_groups())


# ------------------------------------------------------------------ l'état de départ
def test_la_partition_t0_est_l_etat_initial(arbres, init):
    a0 = arbres.where(arbres["year"] == T0).order("tree_id")
    assert len(a0) == len(init), (len(a0), len(init))
    assert a0["tree_id"].tolist() == init["tree_id"].tolist()
    assert (a0["status"] == "alive").all()
    assert np.allclose(a0["x"], init["x"], atol=1e-9, rtol=0) and np.allclose(a0["y"], init["y"], atol=1e-9, rtol=0)
    assert np.abs(a0["d130"] - init["d130"]).max() < 1e-9, "d130 de t0 différent de trees_init"
    assert a0["species"].tolist() == init["species"].tolist()


def test_la_hauteur_de_t0_ne_descend_pas_sous_la_mesure(arbres, init):
    """La hauteur mesurée est l'ancre (Q2) et dH >= 0 : avancée de la date de vol à t0, elle ne baisse pas."""
    a0 = arbres.where(arbres["year"] == T0).order("tree_id")
    assert (a0["h"] >= init["h"] - 1e-9).all()


# ------------------------------------------------------------------ règles d'état
@pytest.fixture(scope="module")
def par_arbre(arbres):
    """sim/trees triée par (tree_id, year) et le drapeau « même arbre que la ligne précédente »."""
    a = arbres.order("tree_id", "year")
    meme = np.zeros(len(a), dtype=bool)
    meme[1:] = a["tree_id"][1:] == a["tree_id"][:-1]
    return a, meme


def _baisses(par_arbre, col, tol):
    a, meme = par_arbre
    d = np.zeros(len(a))
    d[1:] = a[col][1:] - a[col][:-1]
    mauvais = np.flatnonzero(meme & (d < -tol))
    return [(a["tree_id"][i], int(a["year"][i]), float(a[col][i])) for i in mauvais]


def test_d130_ne_decroit_jamais(par_arbre):
    bad = _baisses(par_arbre, "d130", 1e-12)
    assert not bad, f"{len(bad)} baisses de d130, par exemple {bad[:3]}"


def test_la_hauteur_ne_decroit_jamais(par_arbre):
    """dH >= 0 : une hauteur au-dessus du plafond est signalée, jamais corrigée (CLAUDE.md, spec §5)."""
    bad = _baisses(par_arbre, "h", 1e-9)
    assert not bad, f"{len(bad)} baisses de h, par exemple {bad[:3]}"


def test_les_valeurs_sont_finies_et_positives(arbres):
    for c in ("x", "y", "d130", "h", "hcb", "cw"):
        assert np.isfinite(arbres[c]).all(), f"{c} non fini"
    assert (arbres["d130"] > 0).all() and (arbres["h"] > 0).all()
    assert (arbres["hcb"] >= 0).all() and (arbres["cw"] >= 0).all()


def test_un_mort_apparait_une_fois_puis_plus(par_arbre):
    a, meme = par_arbre
    morts = a["status"] == "dead"
    assert morts.sum() > 0, "aucun arbre mort en 100 ans : la mortalité n'agit pas"
    assert len(np.unique(a["tree_id"][morts])) == int(morts.sum()), "un arbre est écrit mort plusieurs fois"
    derniere = np.ones(len(a), dtype=bool)
    derniere[:-1] = ~meme[1:]                      # dernière ligne de chaque arbre
    assert derniere[morts].all(), "un mort réapparaît après l'année de sa mort"
    # et un arbre qui n'est pas mort est écrit, vivant, jusqu'à la fin
    reste = derniere & ~morts
    assert (a["year"][reste] == T0 + ANNEES).all(), "un arbre non mort disparaît avant la fin"


def test_un_mort_est_ecrit_avec_ses_valeurs_du_1er_janvier(par_arbre):
    """Décision du 25/11/2026 (037) : la mort est écrite avec les valeurs du début de l'année, sans la croissance de
    l'année de sa mort : d130 et h du mort valent ceux de la ligne de l'année précédente."""
    a, meme = par_arbre
    morts = np.flatnonzero(a["status"] == "dead")
    assert len(morts) > 100
    assert meme[morts].all(), "un arbre est écrit mort dès sa première ligne"
    for col in ("d130", "h", "x", "y"):
        ecart = np.abs(a[col][morts] - a[col][morts - 1])
        assert (ecart < 1e-12).all(), f"{col} d'un mort différent de celui du 1er janvier : écart max {ecart.max():.3e}"


def test_la_vie_d_un_arbre_est_continue(par_arbre):
    a, meme = par_arbre
    deb = np.flatnonzero(~meme)
    fin = np.r_[deb[1:] - 1, len(a) - 1]
    nb = fin - deb + 1
    trou = (a["year"][fin] - a["year"][deb] + 1) != nb
    assert not trou.any(), f"{int(trou.sum())} arbres avec des années manquantes, par exemple {a['tree_id'][deb[trou][:3]].tolist()}"


def test_le_compte_des_morts_est_plausible(arbres):
    """Avec un risque annuel de quelques %, l'année t0+1 compte des centaines de morts, jamais tous les arbres."""
    a1 = arbres.where(arbres["year"] == T0 + 1)
    n_morts = int((a1["status"] == "dead").sum())
    assert 20 < n_morts < 0.5 * len(a1), n_morts


# ------------------------------------------------------------------ recrues
@pytest.fixture(scope="module")
def recrues(arbres):
    return arbres.where(H.commence_par(arbres["tree_id"], "r"))


def _premieres(recrues):
    """Première ligne (année la plus ancienne) de chaque recrue."""
    r = recrues.order("tree_id", "year")
    return r.where(H.debuts_de_groupe(r["tree_id"]))


def test_il_y_a_des_recrues(recrues):
    assert len(np.unique(recrues["tree_id"])) > 100, len(np.unique(recrues["tree_id"]))


def test_aucune_recrue_a_t0(arbres):
    assert not H.commence_par(arbres["tree_id"][arbres["year"] == T0], "r").any()


def test_tree_id_des_recrues_au_motif_cellule_annee_rang(recrues):
    mauvais = [t for t in np.unique(recrues["tree_id"]).tolist() if not H.RE_RECRUE.match(t)]
    assert not mauvais, f"identifiants hors motif r<cell_id>_<année>_<rang> : {mauvais[:5]}"


def test_l_annee_d_un_tree_id_de_recrue_est_celle_de_sa_premiere_ligne(recrues):
    prem = _premieres(recrues)
    ann = np.array([int(H.RE_RECRUE.match(t).group(2)) for t in prem["tree_id"].tolist()])
    assert (prem["year"] == ann).all()


def test_les_rangs_des_recrues_sont_consecutifs_par_cellule_et_annee(recrues):
    par = {}
    for t in np.unique(recrues["tree_id"]).tolist():
        c, a, r = map(int, H.RE_RECRUE.match(t).groups())
        par.setdefault((c, a), []).append(r)
    debuts = set()
    for (c, a), rangs in par.items():
        rangs = sorted(rangs)
        debuts.add(rangs[0])
        assert rangs == list(range(rangs[0], rangs[0] + len(rangs))), f"rangs non consécutifs en ({c},{a}) : {rangs}"
    assert len(debuts) == 1 and debuts <= {0, 1}, f"les rangs commencent à des valeurs différentes : {debuts}"


def test_les_recrues_entrent_a_7_48_cm_dans_leur_cellule(recrues, grid, params):
    prem = _premieres(recrues)
    assert np.abs(prem["d130"] - H.D130_RECRUE).max() < H.TOL_D130_RECRUE, \
        f"d130 d'entrée : {sorted(set(np.round(prem['d130'], 6).tolist()))[:5]}"
    cid = np.array([int(H.RE_RECRUE.match(t).group(1)) for t in prem["tree_id"].tolist()])
    assert (grid.cell_id(prem["x"], prem["y"]) == cid).all(), "une recrue n'est pas dans sa cellule"
    assert grid.inside(prem["x"], prem["y"]).all()
    assert (prem["status"] == "alive").all()
    assert (prem["h"] > 0).all()
    assert set(np.unique(prem["species"]).tolist()) <= ESPECES_FICTIF, set(np.unique(prem["species"]).tolist())


def test_les_recrues_ont_les_quatre_jeux_de_parametres(recrues, params):
    """T6 : essences candidates = celles qui ont les quatre jeux de paramètres."""
    for s in set(np.unique(recrues["species"]).tolist()):
        for m in ("growth_gam", "mortality_gam", "recruitment_gam", "relative_height_gam"):
            assert params.rows(m, s) is not None, f"recrue d'essence {s} sans {m}"


def test_les_positions_de_recrues_ne_sont_pas_toutes_au_meme_point(recrues, grid):
    prem = _premieres(recrues)
    ox = (prem["x"] - grid.x0) % grid.res
    oy = (prem["y"] - grid.y1) % grid.res
    assert len(np.unique(ox)) > 50 and len(np.unique(oy)) > 50, "positions de recrues non tirées dans la cellule"
    assert ox.std() > 3.0 and oy.std() > 3.0, (ox.std(), oy.std())


def test_la_chaine_compte_les_memes_recrues_et_morts_que_run_json(chaine, arbres):
    j = H.read_run_json(chaine["dir"])
    nr = len(np.unique(arbres["tree_id"][H.commence_par(arbres["tree_id"], "r")]))
    nm = int((arbres["status"] == "dead").sum())
    assert j["recruits"] == nr, (j["recruits"], nr)
    assert j["deaths"] == nm, (j["deaths"], nm)


# ------------------------------------------------------------------ cellules, recalculées depuis les arbres
def _cellules_attendues(arbres_annee, grid, seuil):
    """{(cell_id, essence): (tiges, surface terrière m2, d130 moyen)} des arbres vivants de d130 >= seuil."""
    a = arbres_annee.where((arbres_annee["status"] == "alive") & (arbres_annee["d130"] >= seuil))
    cid = grid.cell_id(a["x"], a["y"])
    sp_val, sp_i = np.unique(a["species"], return_inverse=True)
    cle, inv = np.unique(cid * 1000 + sp_i, return_inverse=True)
    n = np.bincount(inv)
    g = np.bincount(inv, weights=np.pi * (a["d130"] / 200.0) ** 2)
    dm = np.bincount(inv, weights=a["d130"]) / n
    return {(int(k // 1000), str(sp_val[int(k % 1000)])): (int(n[i]), float(g[i]), float(dm[i])) for i, k in enumerate(cle)}


@pytest.mark.parametrize("annee", [T0, T0 + 1, T0 + 50, T0 + ANNEES])
def test_les_cellules_sont_celles_des_arbres(chaine, arbres, grid, annee):
    """Tiges/ha, surface terrière et d130 moyen (arithmétique, T8) recalculés depuis sim/trees. Un arbre mort
    ne compte pas. Une recrue de 7,48 cm est sous le seuil écrit au contrat (7,5 cm) : les deux lectures
    (avec ou sans elle) sont admises, une seule doit concorder partout."""
    c = H.read_year(chaine["dir"], "cells", annee)
    lu = {(int(i), str(s)): (float(a), float(b), float(d)) for i, s, a, b, d in
          zip(c["cell_id"], c["species"], c["stems_ha"], c["basal_area_m2_ha"], c["d130_mean"])}
    a = arbres.where(arbres["year"] == annee)
    ecarts = {}
    for nom, seuil in (("seuil 7,5 cm", H.SEUIL_TIGE), ("toutes les tiges vivantes", 0.0)):
        e = _cellules_attendues(a, grid, seuil)
        manque = [k for k in e if k not in lu]
        fausses = 0
        for k, (n, g, dm) in e.items():
            if k not in lu:
                continue
            st, ba, d = lu[k]
            tiges, surf = n / H.AIRE_CELLULE_HA, g / H.AIRE_CELLULE_HA
            if abs(tiges - st) > 1e-9 * max(tiges, 1) or abs(surf - ba) > 1e-9 * max(surf, 1) or not abs(dm - d) <= 1e-9:
                fausses += 1
        en_trop = sum(1 for k, (st, ba, _d) in lu.items() if k not in e and (st > 0 or ba > 0))
        ecarts[nom] = (len(manque), fausses, en_trop)
    assert any(v == (0, 0, 0) for v in ecarts.values()), f"année {annee}, écarts (manquantes, fausses, en trop) : {ecarts}"


def test_une_cellule_sans_tige_n_a_pas_de_d130_moyen(chaine):
    c = H.read_year(chaine["dir"], "cells", T0 + 10)
    vide = c["stems_ha"] == 0
    assert np.isnan(c["d130_mean"][vide].astype("float64")).all(), \
        "d130_mean non vide pour une cellule sans tige (contrat : « vide sans tige »)"


def test_les_semis_ne_sont_pas_simules(chaine):
    """Pascal, Q3 : colonnes de semis facultatives jusqu'à M5 ; sans valeur inventée, et la mention dite."""
    import pyarrow.parquet as pq
    for y in (T0, T0 + 1, T0 + ANNEES):
        for f in H.partitions(chaine["dir"], "cells")[y]:
            t = pq.read_table(f)
            for col in ("seedlings_ha", "seedling_h_mean"):
                if col in t.schema.names:
                    v = [x for x in t.column(col).to_pylist() if x is not None and not (isinstance(x, float) and math.isnan(x))]
                    assert not v, f"{col} porte {len(v)} valeurs alors que les semis ne sont pas simulés (M3a)"
    corpus = H.sim_text_corpus(chaine["dir"]).lower()
    assert "semis non simulés" in corpus, "la mention « semis non simulés » est absente de sim/ (flags.parquet)"


def test_la_table_de_signalements_est_lisible_et_en_francais(chaine):
    import pyarrow.parquet as pq
    t = H.Tab.from_arrow(pq.read_table(chaine["dir"] / "sim" / "flags.parquet"))
    assert set(t.names) == {"year", "entity", "kind", "message", "value"}
    assert len(t) > 0, "aucun signalement : au moins « semis non simulés » et les cellules au plafond sont attendus"
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in np.unique(t["kind"]).tolist())
    assert all(len(m) > 10 for m in t["message"].tolist())
