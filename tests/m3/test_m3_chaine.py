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


def test_la_config_du_depot_tourne_sur_le_jeu_fictif(run_depot):
    """Le t0 de config.yml (mission 034 : 2021, « année de vol majoritaire ») doit être celui d'un jeu fictif sur lequel
    le moteur tourne. Si le moteur refuse « une date de vol après la fin de t0 » (le jeu a des dalles de 2022), c'est
    le désaccord entre config.yml et le jeu fictif qu'il faut trancher (t0 ou règle de date), pas ce test."""
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


def test_l_annee_n_est_ecrite_que_dans_le_nom_du_dossier_ou_egale_a_lui(arbres):
    """Le validateur refuse une colonne `year` dans un fichier partitionné (convention Hive) : si elle y est, elle
    égale la partition ; sinon l'année vient du dossier year=AAAA (relue par helpers_m3)."""
    dans = arbres["year_dans_fichier"].dropna()
    assert (dans == arbres.loc[dans.index, "part_year"]).all()
    assert arbres["part_year"].between(T0, T0 + ANNEES).all()


def test_tree_id_et_annee_forment_une_cle_unique(arbres):
    dup = arbres.duplicated(["tree_id", "year"], keep=False)
    assert not dup.any(), f"{dup.sum()} lignes en double, par exemple {arbres[dup].head(3)[['tree_id','year']].to_dict('records')}"


def test_cell_id_year_species_est_une_cle_unique_des_cellules(chaine):
    for y in (T0, T0 + 1, T0 + 50, T0 + ANNEES):
        c = H.read_year(chaine["dir"], "cells", y)
        assert not c.duplicated(["cell_id", "year", "species"]).any(), f"clé en double en {y}"


# ------------------------------------------------------------------ codes des référentiels, piège de la Somalie
def test_essences_et_statuts_appartiennent_aux_referentiels(arbres, params):
    ref = set(H.species_groups())
    inconnues = set(arbres["species"]) - ref
    assert not inconnues, f"essences hors contracts/species.csv : {inconnues}"
    sans_params = set(arbres["species"]) - set(params.df["species"].dropna())
    assert not sans_params, f"essences sans paramètres : {sans_params}"
    assert set(arbres["status"]) <= {"alive", "dead"}, set(arbres["status"])
    assert (arbres["species"].str.fullmatch(r"[0-9]{2}[A-Z0-9]{0,3}")).all()


def test_les_arbres_sont_dans_l_emprise_x_est_y_nord(arbres, grid):
    """Piège de la Somalie : x (est) et y (nord) ne sont pas inversés ; tout est dans l'emprise EPSG:2154."""
    assert arbres["x"].between(grid.x0, grid.x1).all(), (arbres["x"].min(), arbres["x"].max())
    assert arbres["y"].between(grid.y1, grid.y0).all(), (arbres["y"].min(), arbres["y"].max())
    assert (arbres["y"] > arbres["x"]).all()     # Lambert-93 : y vaut ~6,5 millions, x ~0,7 million


def test_les_cellules_sont_dans_la_grille(chaine, grid):
    for y in (T0, T0 + ANNEES):
        c = H.read_year(chaine["dir"], "cells", y)
        assert c["cell_id"].between(0, grid.ncols * grid.nrows - 1).all()
        assert set(c["species"]) <= set(H.species_groups())


# ------------------------------------------------------------------ l'état de départ
def test_la_partition_t0_est_l_etat_initial(arbres, init):
    a0 = arbres[arbres["year"] == T0].sort_values("tree_id", kind="stable").reset_index(drop=True)
    assert len(a0) == len(init), (len(a0), len(init))
    assert list(a0["tree_id"]) == list(init["tree_id"])
    assert (a0["status"] == "alive").all()
    assert np.allclose(a0["x"], init["x"], atol=1e-9, rtol=0) and np.allclose(a0["y"], init["y"], atol=1e-9, rtol=0)
    assert np.abs(a0["d130"].to_numpy() - init["d130"].to_numpy()).max() < 1e-9, "d130 de t0 différent de trees_init"
    assert list(a0["species"]) == list(init["species"])


def test_la_hauteur_de_t0_ne_descend_pas_sous_la_mesure(arbres, init):
    """La hauteur mesurée est l'ancre (Q2) et dH >= 0 : avancée de la date de vol à t0, elle ne baisse pas."""
    a0 = arbres[arbres["year"] == T0].sort_values("tree_id", kind="stable").reset_index(drop=True)
    assert (a0["h"].to_numpy() >= init["h"].to_numpy() - 1e-9).all()


# ------------------------------------------------------------------ règles d'état
def test_d130_ne_decroit_jamais(arbres):
    a = arbres.sort_values(["tree_id", "year"], kind="stable")
    d = a.groupby("tree_id", sort=False)["d130"].diff()
    bad = a[d < -1e-12]
    assert bad.empty, f"{len(bad)} baisses de d130, par exemple {bad.head(3)[['tree_id','year','d130']].to_dict('records')}"


def test_la_hauteur_ne_decroit_jamais(arbres):
    """dH >= 0 : une hauteur au-dessus du plafond est signalée, jamais corrigée (CLAUDE.md, spec §5)."""
    a = arbres.sort_values(["tree_id", "year"], kind="stable")
    d = a.groupby("tree_id", sort=False)["h"].diff()
    bad = a[d < -1e-9]
    assert bad.empty, f"{len(bad)} baisses de h, par exemple {bad.head(3)[['tree_id','year','h']].to_dict('records')}"


def test_les_valeurs_sont_finies_et_positives(arbres):
    for c in ("x", "y", "d130", "h", "hcb", "cw"):
        assert np.isfinite(arbres[c]).all(), f"{c} non fini"
    assert (arbres["d130"] > 0).all() and (arbres["h"] > 0).all()
    assert (arbres["hcb"] >= 0).all() and (arbres["cw"] >= 0).all()


def test_un_mort_apparait_une_fois_puis_plus(arbres):
    a = arbres.sort_values(["tree_id", "year"], kind="stable")
    morts = a[a["status"] == "dead"]
    assert len(morts) > 0, "aucun arbre mort en 100 ans : la mortalité n'agit pas"
    assert morts["tree_id"].is_unique, "un arbre est écrit mort plusieurs fois"
    derniere = a.groupby("tree_id", sort=False)["year"].max()
    annee_mort = morts.set_index("tree_id")["year"]
    assert (derniere.loc[annee_mort.index] == annee_mort).all(), "un mort réapparaît après l'année de sa mort"
    # et un arbre qui n'est pas mort est écrit jusqu'à la fin
    vivants_fin = a[(a["year"] == T0 + ANNEES) & (a["status"] == "alive")]
    reste = set(a["tree_id"]) - set(annee_mort.index)
    assert set(vivants_fin["tree_id"]) == reste, "un arbre non mort disparaît avant la fin"


def test_un_mort_est_ecrit_avec_ses_valeurs_du_1er_janvier(arbres):
    """Décision du 25/11/2026 (037) : la mort est écrite avec les valeurs du début de l'année, sans la croissance de
    l'année de sa mort : d130 et h du mort valent ceux de la ligne de l'année précédente."""
    a = arbres.sort_values(["tree_id", "year"], kind="stable")
    prev = a.groupby("tree_id", sort=False)[["d130", "h", "x", "y"]].shift(1)
    morts = a["status"] == "dead"
    assert morts.sum() > 100
    for col in ("d130", "h", "x", "y"):
        ecart = (a.loc[morts, col] - prev.loc[morts, col]).abs()
        assert (ecart < 1e-12).all(), f"{col} d'un mort différent de celui du 1er janvier : écart max {ecart.max():.3e}"


def test_la_vie_d_un_arbre_est_continue(arbres):
    g = arbres.groupby("tree_id", sort=False)["year"].agg(["min", "max", "count"])
    trou = g[(g["max"] - g["min"] + 1) != g["count"]]
    assert trou.empty, f"{len(trou)} arbres avec des années manquantes : {trou.head(3)}"


def test_le_compte_des_morts_est_plausible(arbres):
    """Avec un risque annuel de quelques %, l'année t0+1 compte des centaines de morts, jamais tous les arbres."""
    a1 = arbres[arbres["year"] == T0 + 1]
    n_morts = int((a1["status"] == "dead").sum())
    assert 20 < n_morts < 0.5 * len(a1), n_morts


# ------------------------------------------------------------------ recrues
@pytest.fixture(scope="module")
def recrues(arbres):
    r = arbres[arbres["tree_id"].str.startswith("r")]
    return r


def test_il_y_a_des_recrues(recrues):
    assert recrues["tree_id"].nunique() > 100, recrues["tree_id"].nunique()


def test_aucune_recrue_a_t0(arbres):
    assert not arbres[(arbres["year"] == T0)]["tree_id"].str.startswith("r").any()


def test_tree_id_des_recrues_au_motif_cellule_annee_rang(recrues):
    mauvais = [t for t in recrues["tree_id"].unique() if not H.RE_RECRUE.match(t)]
    assert not mauvais, f"identifiants hors motif r<cell_id>_<année>_<rang> : {mauvais[:5]}"


def test_l_annee_d_un_tree_id_de_recrue_est_celle_de_sa_premiere_ligne(recrues):
    prem = recrues.groupby("tree_id")["year"].min()
    ann = prem.index.map(lambda t: int(H.RE_RECRUE.match(t).group(2)))
    assert (prem.to_numpy() == np.asarray(ann)).all()


def test_les_rangs_des_recrues_sont_consecutifs_par_cellule_et_annee(recrues):
    ids = recrues["tree_id"].unique()
    par = {}
    for t in ids:
        c, a, r = map(int, H.RE_RECRUE.match(t).groups())
        par.setdefault((c, a), []).append(r)
    debuts = set()
    for (c, a), rangs in par.items():
        rangs = sorted(rangs)
        debuts.add(rangs[0])
        assert rangs == list(range(rangs[0], rangs[0] + len(rangs))), f"rangs non consécutifs en ({c},{a}) : {rangs}"
    assert len(debuts) == 1 and debuts <= {0, 1}, f"les rangs commencent à des valeurs différentes : {debuts}"


def test_les_recrues_entrent_a_7_48_cm_dans_leur_cellule(recrues, grid, params):
    prem = recrues.sort_values("year", kind="stable").drop_duplicates("tree_id", keep="first")
    assert np.abs(prem["d130"] - H.D130_RECRUE).max() < 1e-9, \
        f"d130 d'entrée : {sorted(set(np.round(prem['d130'], 6)))[:5]}"
    cid = prem["tree_id"].map(lambda t: int(H.RE_RECRUE.match(t).group(1)))
    assert (grid.cell_id(prem["x"], prem["y"]) == cid.to_numpy()).all(), "une recrue n'est pas dans sa cellule"
    assert grid.inside(prem["x"], prem["y"]).all()
    assert (prem["status"] == "alive").all()
    assert (prem["h"] > 0).all()
    assert set(prem["species"]) <= ESPECES_FICTIF, set(prem["species"])


def test_les_recrues_ont_les_quatre_jeux_de_parametres(recrues, params):
    """T6 : essences candidates = celles qui ont les quatre jeux de paramètres."""
    for s in set(recrues["species"]):
        for m in ("growth_gam", "mortality_gam", "recruitment_gam", "relative_height_gam"):
            assert params.rows(m, s) is not None, f"recrue d'essence {s} sans {m}"


def test_les_positions_de_recrues_ne_sont_pas_toutes_au_meme_point(recrues, grid):
    prem = recrues.sort_values("year", kind="stable").drop_duplicates("tree_id", keep="first")
    ox = (prem["x"] - grid.x0) % grid.res
    oy = (prem["y"] - grid.y1) % grid.res
    assert ox.nunique() > 50 and oy.nunique() > 50, "positions de recrues non tirées dans la cellule"
    assert ox.std() > 3.0 and oy.std() > 3.0, (ox.std(), oy.std())


def test_la_chaine_compte_les_memes_recrues_et_morts_que_run_json(chaine, arbres):
    j = H.read_run_json(chaine["dir"])
    nr = arbres[arbres["tree_id"].str.startswith("r")]["tree_id"].nunique()
    nm = int((arbres["status"] == "dead").sum())
    assert j["recruits"] == nr, (j["recruits"], nr)
    assert j["deaths"] == nm, (j["deaths"], nm)


# ------------------------------------------------------------------ cellules, recalculées depuis les arbres
def _cellules_attendues(arbres_annee, grid, seuil):
    a = arbres_annee[(arbres_annee["status"] == "alive") & (arbres_annee["d130"] >= seuil)].copy()
    a["cell_id"] = grid.cell_id(a["x"], a["y"])
    a["g"] = np.pi * (a["d130"] / 200.0) ** 2
    g = a.groupby(["cell_id", "species"]).agg(n=("g", "size"), g=("g", "sum"), dm=("d130", "mean")).reset_index()
    g["stems_ha"] = g["n"] / H.AIRE_CELLULE_HA
    g["basal_area_m2_ha"] = g["g"] / H.AIRE_CELLULE_HA
    return g.set_index(["cell_id", "species"])


@pytest.mark.parametrize("annee", [T0, T0 + 1, T0 + 50, T0 + ANNEES])
def test_les_cellules_sont_celles_des_arbres(chaine, arbres, grid, annee):
    """Tiges/ha, surface terrière et d130 moyen (arithmétique, T8) recalculés depuis sim/trees. Un arbre mort
    ne compte pas. Une recrue de 7,48 cm est sous le seuil écrit au contrat (7,5 cm) : les deux lectures
    (avec ou sans elle) sont admises, une seule doit concorder partout."""
    c = H.read_year(chaine["dir"], "cells", annee).set_index(["cell_id", "species"])
    a = arbres[arbres["year"] == annee]
    ecarts = {}
    for nom, seuil in (("seuil 7,5 cm", H.SEUIL_TIGE), ("toutes les tiges vivantes", 0.0)):
        e = _cellules_attendues(a, grid, seuil)
        manque = e.index.difference(c.index)
        j = e.join(c, how="inner", rsuffix="_sim")
        pb = ((j["stems_ha"] - j["stems_ha_sim"]).abs() > 1e-9 * j["stems_ha"].clip(lower=1)) \
            | ((j["basal_area_m2_ha"] - j["basal_area_m2_ha_sim"]).abs() > 1e-9 * j["basal_area_m2_ha"].clip(lower=1)) \
            | ((j["dm"] - j["d130_mean"]).abs() > 1e-9)
        extra = c.index.difference(e.index)
        extra_non_nul = c.loc[extra][(c.loc[extra]["stems_ha"] > 0) | (c.loc[extra]["basal_area_m2_ha"] > 0)]
        ecarts[nom] = (len(manque), int(pb.sum()), len(extra_non_nul))
    assert any(v == (0, 0, 0) for v in ecarts.values()), f"année {annee}, écarts (manquantes, fausses, en trop) : {ecarts}"


def test_une_cellule_sans_tige_n_a_pas_de_d130_moyen(chaine):
    c = H.read_year(chaine["dir"], "cells", T0 + 10)
    vide = c[c["stems_ha"] == 0]
    assert vide["d130_mean"].isna().all(), "d130_mean non vide pour une cellule sans tige (contrat : « vide sans tige »)"


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
    t = pq.read_table(chaine["dir"] / "sim" / "flags.parquet").to_pandas()
    assert set(t.columns) == {"year", "entity", "kind", "message", "value"}
    assert len(t) > 0, "aucun signalement : au moins « semis non simulés » et les cellules au plafond sont attendus"
    assert t["kind"].str.fullmatch(r"[a-z][a-z0-9_]*").all()
    assert (t["message"].str.len() > 10).all()
