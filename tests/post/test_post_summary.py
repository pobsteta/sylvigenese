"""sim/summary.parquet sur la zone simulée (5 ans), contre l'oracle recalculé depuis sim/trees et params/tarif.parquet
(contrat post.summary 0.2 ; décisions Q3 à Q5 du 26/11/2026). Une ligne par (cellule, année, essence) vivante, comme
sim/cells ; t0 présent ; sommes des arbres vivants calculés divisées par la surface de la cellule ; hors domaine compté."""
import math

import pytest

import helpers_post as P

T = P.T


@pytest.fixture(scope="module")
def summary(base_dir):
    return P.read_summary(base_dir)


@pytest.fixture(scope="module")
def attendu(oracle):
    return oracle.summary()


def proche(a, b, rel=P.TOL):
    return a is not None and b is not None and math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)


def test_l_oracle_exerce_le_hors_domaine(oracle):
    # garde-fou : la zone simulée contient des recrues (dbh_below) et de gros arbres (dbh_above), sinon le test ment
    c = oracle.counts()
    raisons = {r for v in c["out_of_domain"].values() for r, n in v.items() if n}
    assert {"dbh_below", "dbh_above"} <= raisons, raisons
    assert c["tree_years_computed"] > 0


def test_une_ligne_par_cellule_annee_essence_vivante(summary, attendu):
    en_trop = sorted(set(summary) - set(attendu))
    manque = sorted(set(attendu) - set(summary))
    assert not en_trop, f"{len(en_trop)} lignes sans arbre vivant, ex. {en_trop[:5]}"
    assert not manque, f"{len(manque)} (cellule, année, essence) vivants sans ligne, ex. {manque[:5]}"


def test_memes_cles_que_sim_cells(summary, base_dir):
    cles = {(int(r["cell_id"]), int(r["year"]), str(r["species"])) for r in T.cells_rows(base_dir)}
    assert set(summary) == cles


def test_t0_et_toutes_les_annees_sont_presentes(summary):
    assert sorted({k[1] for k in summary}) == list(range(P.T0, P.T0 + P.YEARS + 1))


def test_volume_biomasse_carbone_des_feuillus_recalcules(summary, attendu, oracle):
    faux, n = [], 0
    for k, e in attendu.items():
        if e["volume_m3_ha"] is None:
            continue
        n += 1
        r = summary.get(k)
        dens, frac, rac = oracle.factors(k[2])
        v = e["volume_m3_ha"]
        if r is None or not (proche(r["volume_m3_ha"], v) and proche(r["biomass_t_ha"], v * dens)
                             and proche(r["carbon_t_ha"], v * dens * frac)):
            faux.append((k, None if r is None else (r["volume_m3_ha"], r["biomass_t_ha"], r["carbon_t_ha"]), v))
    assert n > 1000, f"seulement {n} lignes de feuillus recalculées"
    assert not faux, f"{len(faux)} lignes fausses sur {n}, ex. {faux[:3]}"


def test_racines_a_part_et_provisoires(summary, oracle):
    faux = []
    for k, r in summary.items():
        dens, frac, rac = oracle.factors(k[2])
        assert "carbon_roots_t_ha" in r, "le tarif porte le modèle racines : colonne carbon_roots_t_ha attendue"
        if not proche(r["carbon_roots_t_ha"], r["carbon_t_ha"] * rac) and not (r["carbon_t_ha"] == r["carbon_roots_t_ha"] == 0):
            faux.append((k, r["carbon_roots_t_ha"], r["carbon_t_ha"]))
    assert not faux, f"{len(faux)} lignes : racines ≠ carbone aérien × rapport, ex. {faux[:3]}"
    assert all(r["provisoire"] is True for r in summary.values()), "provisoire doit être vrai sur toutes les lignes (v1)"


def test_resineux_biomasse_et_carbone_deduits_du_volume(summary, attendu, oracle):
    faux, n = [], 0
    for k, e in attendu.items():
        if e["volume_m3_ha"] is not None:
            continue
        n += 1
        r = summary.get(k)
        dens, frac, _ = oracle.factors(k[2])
        ok = (r is not None and r["volume_m3_ha"] > 0 and math.isfinite(r["volume_m3_ha"])
              and proche(r["biomass_t_ha"], r["volume_m3_ha"] * dens)
              and proche(r["carbon_t_ha"], r["volume_m3_ha"] * dens * frac))
        if not ok:
            faux.append((k, r))
    assert n > 100, f"seulement {n} lignes de résineux calculés"
    assert not faux, f"{len(faux)} lignes de résineux incohérentes, ex. {faux[:2]}"


def test_tiges_et_part_de_surface_terriere_non_calculees(summary, attendu):
    faux = []
    for k, e in attendu.items():
        r = summary.get(k)
        if r is None or not (proche(r["stems_not_computed_ha"], e["stems_not_computed_ha"]) or
                             r["stems_not_computed_ha"] == e["stems_not_computed_ha"] == 0):
            faux.append((k, "tiges", None if r is None else r["stems_not_computed_ha"], e["stems_not_computed_ha"]))
        elif not (abs(r["basal_area_not_computed_share"] - e["share"]) <= 1e-9):
            faux.append((k, "part", r["basal_area_not_computed_share"], e["share"]))
    assert not faux, f"{len(faux)} écarts, ex. {faux[:3]}"


def test_part_exactement_1_et_valeurs_nulles_quand_rien_n_est_calcule(summary, attendu):
    tous_hors = [k for k, e in attendu.items() if e["n_c"] == 0]
    assert tous_hors, "garde-fou : la zone simulée doit avoir des lignes entièrement hors domaine (recrues)"
    faux = [k for k in tous_hors if not (summary[k]["basal_area_not_computed_share"] == 1.0 and summary[k]["volume_m3_ha"] == 0
                                         and summary[k]["carbon_t_ha"] == 0 and summary[k]["biomass_t_ha"] == 0)]
    assert not faux, f"{len(faux)} lignes sans arbre calculé : part ≠ 1 ou valeur non nulle (extrapolation ?), ex. {faux[:3]}"


def test_aucune_extrapolation_hors_domaine(summary, attendu):
    # une ligne dont des arbres sont hors domaine a exactement le volume de ses seuls arbres calculés (feuillus)
    partielles = [k for k, e in attendu.items() if 0 < e["n_nc"] and e["n_c"] > 0 and e["volume_m3_ha"] is not None]
    assert partielles, "garde-fou : il faut des lignes partielles de feuillus"
    faux = [k for k in partielles if not proche(summary[k]["volume_m3_ha"], attendu[k]["volume_m3_ha"])]
    assert not faux, f"{len(faux)} lignes partielles dont le volume n'est pas celui des seuls arbres calculés, ex. {faux[:3]}"


def test_aucune_valeur_manquante_ni_negative(summary):
    for k, r in summary.items():
        for c, v in r.items():
            assert v is not None, f"{k} : {c} vide"
            if isinstance(v, float):
                assert math.isfinite(v) and v >= 0, f"{k} : {c} = {v}"


@pytest.mark.parametrize("annee", list(range(P.T0, P.T0 + P.YEARS + 1)))
def test_la_cellule_du_point_connu_chaque_annee(summary, attendu, oracle, annee):
    # échantillon terrain n° 1 : la cellule 0 ; sur le jeu fictif ce sont des sapins (61), dont plusieurs > 100 cm
    lignes = {k: e for k, e in attendu.items() if k[0] == 0 and k[1] == annee}
    assert lignes, f"l'oracle ne trouve aucun arbre vivant en cellule 0 en {annee}"
    for k, e in lignes.items():
        r = summary.get(k)
        assert r is not None, f"pas de ligne {k}"
        assert proche(r["stems_not_computed_ha"], e["stems_not_computed_ha"]) or r["stems_not_computed_ha"] == e["stems_not_computed_ha"] == 0
        assert abs(r["basal_area_not_computed_share"] - e["share"]) <= 1e-9, (k, r["basal_area_not_computed_share"], e["share"])
        dens, frac, rac = oracle.factors(k[2])
        assert proche(r["biomass_t_ha"], r["volume_m3_ha"] * dens) or r["volume_m3_ha"] == r["biomass_t_ha"] == 0
        assert proche(r["carbon_t_ha"], r["biomass_t_ha"] * frac) or r["biomass_t_ha"] == r["carbon_t_ha"] == 0
