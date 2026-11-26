"""Zone échantillon : 13 arbres choisis (helpers_post.MINI_TREES), deux années, valeurs refaites à la calculette.
Échantillon terrain n° 1 du plan : l'arbre du point (est 700 012,5 ; nord 6 500 987,5, EPSG:2154) est dans la cellule 0,
et son volume se refait à la main depuis params/tarif.parquet. Hors domaine et sans tarif : comptés, jamais extrapolés
ni empruntés (décision Q5). Racines à part, provisoires (Q4)."""
import math

import pytest

import helpers_post as P

AIRE = 0.0625
# volumes à la calculette (formule du contrat volume_feuillus, tarif synthétique ; voir test_post_oracle.py)
V_A = 1.8471724842550155   # 09, D 40 cm, H 20 m
V_I = 3.895028724998727    # 09, D 50 cm, H 26 m
V_K = 0.01336548901755479  # 09, D 10 cm, H 3 m (bornes exactes)
V_L = 0.12334197978193531  # 03, D 12,5 cm, H 14 m
ANNEES = (2022, 2023)


@pytest.fixture(scope="module")
def cellules(ech):
    return P.mini_cells(ech["dir"])


@pytest.fixture(scope="module")
def summary(ech_dir):
    return P.read_summary(ech_dir)


def ligne(summary, cell, year, sp):
    k = (cell, year, sp)
    assert k in summary, f"pas de ligne {k} dans sim/summary.parquet ; lignes : {sorted(summary)}"
    return summary[k]


def proche(a, b, rel=1e-9):
    return a is not None and math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)


@pytest.mark.parametrize("annee", ANNEES)
def test_l_arbre_du_point_connu_volume_biomasse_carbone_a_la_main(summary, annee):
    r = ligne(summary, 0, annee, "09")
    assert proche(r["volume_m3_ha"], V_A / AIRE), f"volume {r['volume_m3_ha']} ; attendu {V_A / AIRE} (29,55476 m³/ha)"
    assert proche(r["biomass_t_ha"], V_A * 0.300 / AIRE), r["biomass_t_ha"]
    assert proche(r["carbon_t_ha"], V_A * 0.300 * 0.30 / AIRE), r["carbon_t_ha"]


@pytest.mark.parametrize("annee", ANNEES)
def test_l_arbre_du_point_connu_racines_a_part_et_provisoires(summary, annee):
    r = ligne(summary, 0, annee, "09")
    assert "carbon_roots_t_ha" in r, "le tarif porte le modèle racines : la colonne carbon_roots_t_ha est attendue"
    assert proche(r["carbon_roots_t_ha"], V_A * 0.3 * 0.3 * 0.10 / AIRE), r["carbon_roots_t_ha"]
    # à part : le carbone aérien n'inclut pas les racines
    assert proche(r["carbon_t_ha"], V_A * 0.09 / AIRE)
    assert r["provisoire"] is True


@pytest.mark.parametrize("annee", ANNEES)
def test_la_recrue_de_7_5_cm_du_point_connu_est_comptee_non_calculee(summary, annee):
    r = ligne(summary, 0, annee, "09")
    assert proche(r["stems_not_computed_ha"], 1 / AIRE), r["stems_not_computed_ha"]
    assert proche(r["basal_area_not_computed_share"], 7.5 ** 2 / (40.0 ** 2 + 7.5 ** 2)), r["basal_area_not_computed_share"]


def test_l_arbre_du_point_connu_n_est_dans_aucune_autre_cellule(summary, cellules):
    # latitude et longitude inversées, ou ligne et colonne échangées : le hêtre de 40 cm tomberait ailleurs
    assert {c for (c, _, sp) in summary if sp == "09"} == {0, cellules[3], cellules[4]}
    assert {c for (c, _, _) in summary} <= set(cellules), "ligne pour une cellule sans arbre"


@pytest.mark.parametrize("annee", ANNEES)
def test_une_cellule_toute_hors_domaine_vaut_0_avec_une_part_de_1(summary, cellules, annee):
    r = ligne(summary, cellules[1], annee, "03")     # chênes de 12 cm et de 105 cm
    assert r["volume_m3_ha"] == 0 and r["biomass_t_ha"] == 0 and r["carbon_t_ha"] == 0
    assert r.get("carbon_roots_t_ha", 0) == 0
    assert r["basal_area_not_computed_share"] == 1.0, "part exactement 1 quand aucune tige n'est calculée"
    assert proche(r["stems_not_computed_ha"], 2 / AIRE)


@pytest.mark.parametrize("annee", ANNEES)
def test_essence_sans_tarif_non_calculee_et_sans_emprunt(summary, cellules, annee):
    # 02 n'a aucune ligne de tarif ; 03 en a une, et species.csv donne aux deux le code Quercus_spec : pas d'emprunt
    r = ligne(summary, cellules[4], annee, "02")
    assert r["volume_m3_ha"] == 0 and r["carbon_t_ha"] == 0 and r["biomass_t_ha"] == 0
    assert r["basal_area_not_computed_share"] == 1.0
    assert proche(r["stems_not_computed_ha"], 1 / AIRE)


@pytest.mark.parametrize("annee", ANNEES)
def test_bornes_fermees_du_domaine(summary, cellules, annee):
    k = ligne(summary, cellules[4], annee, "09")
    assert proche(k["volume_m3_ha"], V_K / AIRE) and k["basal_area_not_computed_share"] == 0
    l_ = ligne(summary, cellules[4], annee, "03")
    assert proche(l_["volume_m3_ha"], V_L / AIRE) and l_["basal_area_not_computed_share"] == 0
    assert proche(l_["carbon_t_ha"], V_L * 0.09 / AIRE)


@pytest.mark.parametrize("annee", ANNEES)
def test_resineux_biomasse_carbone_racines_deduits_du_volume(summary, cellules, annee):
    r = ligne(summary, cellules[2], annee, "61")
    v = r["volume_m3_ha"]
    assert v is not None and v > 0 and math.isfinite(v), f"volume du sapin de 30 cm : {v}"
    assert proche(r["biomass_t_ha"], v * 0.350)
    assert proche(r["carbon_t_ha"], v * 0.350 * 0.35)
    assert proche(r["carbon_roots_t_ha"], v * 0.350 * 0.35 * 0.15)
    assert proche(r["basal_area_not_computed_share"], 10.0 ** 2 / (30.0 ** 2 + 10.0 ** 2))   # le 61 de H/D 210
    assert proche(r["stems_not_computed_ha"], 1 / AIRE)
    for sp in ("64", "62"):                      # h < 3 m ; h > 50 m
        z = ligne(summary, cellules[2], annee, sp)
        assert z["volume_m3_ha"] == 0 and z["basal_area_not_computed_share"] == 1.0


def test_les_morts_de_l_annee_sortent_du_stock(summary, cellules):
    r = ligne(summary, cellules[3], 2022, "09")
    assert proche(r["volume_m3_ha"], V_I / AIRE)
    assert proche(r["basal_area_not_computed_share"], 7.5 ** 2 / (50.0 ** 2 + 7.5 ** 2))
    assert not [k for k in summary if k[0] == cellules[3] and k[1] == 2023], \
        "cellule sans arbre vivant en 2023 : aucune ligne attendue"


def test_nombre_de_lignes_par_annee(summary):
    par_annee = {y: sum(1 for k in summary if k[1] == y) for y in ANNEES}
    assert par_annee == {2022: 9, 2023: 8}, par_annee


def test_post_json_comptes_a_la_main(ech_dir):
    j = P.read_post_json(ech_dir)
    assert j["tree_years_computed"] == 10
    assert j["tree_years_not_computed"] == 16
    zero = dict.fromkeys(P.REASONS, 0)
    attendu = {"09": {**zero, "dbh_below": 4}, "03": {**zero, "dbh_below": 2, "dbh_above": 2},
               "61": {**zero, "hd_above": 2}, "64": {**zero, "h_below": 2}, "62": {**zero, "h_above": 2}}
    lu = {sp: v for sp, v in j["out_of_domain"].items() if any(v.values())}
    assert lu == attendu, lu
    assert j["without_tarif"] == {"02": 2}, j["without_tarif"]


def test_flux_de_mortalite_a_la_main(ech_dir, ech_oracle, cellules):
    z = P.read_summary_zone(ech_dir)
    veg = ech_oracle.veg_of_cell[cellules[3]]
    r = z.get((2023, veg, "09"))
    assert r is not None, f"pas de ligne (2023, {veg}, 09) dans summary_zone"
    assert proche(r["dead_volume_m3"], V_I), r["dead_volume_m3"]
    assert proche(r["dead_carbon_t"], V_I * 0.3 * 0.3), r["dead_carbon_t"]
    assert r["dead_stems_not_computed"] == 1
    for k, row in z.items():
        if k[0] == 2022:
            assert row["dead_volume_m3"] == 0 and row["dead_carbon_t"] == 0 and row["dead_stems_not_computed"] == 0, k


def test_summary_zone_de_l_echantillon_egal_a_l_oracle(ech_dir, ech_oracle):
    lu = P.read_summary_zone(ech_dir)
    att = ech_oracle.zone()
    assert set(lu) == set(att), f"clés : en trop {sorted(set(lu) - set(att))}, manquantes {sorted(set(att) - set(lu))}"


# ------------------------------------------------------------------ variantes (une seule chose changée)
def test_sans_modele_racines_post_aboutit_sans_colonne_racines(ech_sans_racines, summary):
    v = ech_sans_racines
    assert v["post"].returncode == 0, "racines absentes : post doit aboutir (colonne facultative)\n" + P.queue(v["post"])
    import pyarrow.parquet as pq
    names = pq.read_schema(v["dir"] / "sim" / "summary.parquet").names
    assert "carbon_roots_t_ha" not in names, "aucun rapport racines/aérien : pas de colonne inventée"
    zn = pq.read_schema(v["dir"] / "sim" / "summary_zone.parquet").names
    assert "carbon_roots_t" not in zn and "carbon_roots_t_ha" not in zn
    lu = P.read_summary(v["dir"])
    assert set(lu) == set(summary)
    for k, r in lu.items():
        for c in ("volume_m3_ha", "biomass_t_ha", "carbon_t_ha", "basal_area_not_computed_share"):
            assert proche(r[c], summary[k][c]) or r[c] == summary[k][c] == 0, (k, c)
    models = {m["model"] for m in P.read_post_json(v["dir"])["models"]}
    assert "racines" not in models


def test_e_d_double_double_le_volume_du_sapin_seul(ech_metamorphe, summary, cellules):
    # contrat : V aérien = V tige × E ; E(D) du 61 doublé ; infradensité des feuillus doublée
    v = ech_metamorphe
    assert v["post"].returncode == 0, P.queue(v["post"])
    lu = P.read_summary(v["dir"])
    for annee in ANNEES:
        a, b = summary[(cellules[2], annee, "61")], lu[(cellules[2], annee, "61")]
        assert proche(b["volume_m3_ha"], 2 * a["volume_m3_ha"]), (a["volume_m3_ha"], b["volume_m3_ha"])
        assert proche(b["carbon_t_ha"], 2 * a["carbon_t_ha"])
        a, b = summary[(0, annee, "09")], lu[(0, annee, "09")]
        assert proche(b["volume_m3_ha"], a["volume_m3_ha"]), "le volume d'un feuillu ne dépend pas de l'infradensité"
        assert proche(b["biomass_t_ha"], 2 * a["biomass_t_ha"]) and proche(b["carbon_t_ha"], 2 * a["carbon_t_ha"])
