"""Tables IFN de prepare (spec §6, §8 ; docs/referentiels/ifn-placettes.md pour les cercles,
docs/referentiels/ifn-dynamique.md §3 pour l'unité de C13 : mètres dans l'export, décision Q1 du
25/11/2026)."""
import csv
import math

import pytest

import helpers as H


def _csv(name):
    with open(H.INPUTS / "ifn" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture(scope="module")
def plots(runs):
    return H.read_parquet(H.ZONE / "ifn" / "plots.parquet")


def test_plots_une_ligne_par_placette_et_par_visite_aux_coordonnees_floutees_inchangees(plots):
    # Une ligne par (IDP, campagne) : un point revu a deux lignes, celle de la 2e visite à la
    # campagne de la 1re plus 5 (docs/referentiels/ifn-dynamique.md §1).
    src = _csv("PLACETTE.csv")
    assert len(plots) == len(src) > 40
    par_cle = {(str(r["plot_id"]), r["campaign"]): r for r in plots}
    assert len(par_cle) == len(plots), "clé (plot_id, campaign) en double"
    for s in src:
        p = par_cle[(s["IDP"], int(s["CAMPAGNE"]))]
        # Coordonnées recopiées telles quelles : jamais recalées sur un raster (garde IFN).
        assert p["x"] == pytest.approx(float(s["XL"]), abs=1e-6)
        assert p["y"] == pytest.approx(float(s["YL"]), abs=1e-6)
        assert p["visit"] == int(s["VISITE"])


def test_plots_precision_de_localisation_jamais_fine(plots):
    # Floutage IFN d'environ 700 m ; seuil de la garde : 25 m.
    for p in plots:
        assert p["loc_precision_m"] is not None and p["loc_precision_m"] > 25, p["plot_id"]
        assert p["source"] == "ifn", (p["plot_id"], p["source"])


def test_plots_ser_code_est_null_en_m1a_et_jamais_une_alluvion(plots):
    # Règle attendue en M1a (à relire si elle change) : la placette IFN est floutée (~700 m) et ne
    # se croise pas avec ser.tif, raster fin (garde IFN, CLAUDE.md) : ser_code est donc NULL pour
    # toutes les placettes. S'il était renseigné, il ne serait jamais un code L1-L5 (spec §3).
    # Ce test vérifie la règle NULL ; il n'est pas une preuve de rattachement des alluvions.
    non_null = [(p["plot_id"], p["ser_code"]) for p in plots if p["ser_code"] is not None]
    assert not non_null, f"ser_code renseigné pour des placettes IFN floutées : {non_null[:5]}"


def _mm(texte):
    """C13 de l'export, en mètres (metadonnees.csv l. 35 et 203), ramené à des millimètres entiers :
    les seuils 0,705 et 1,175 m se comparent sans bruit d'arrondi flottant."""
    return round(float(texte.replace(",", ".")) * 1000)


def test_jeu_fictif_contient_des_arbres_exactement_a_0_705_et_1_175_m():
    c13 = {_mm(s["C13"]) for s in _csv("ARBRE.csv") if s["C13"].strip()}
    assert 705 in c13 and 1175 in c13, "le jeu fictif n'a pas d'arbre aux seuils 0,705 et 1,175 m"


def test_jeu_fictif_c13_est_en_metres_comme_l_export():
    # Piège de l'unité (décision du 25/11/2026) : l'export donne des mètres (0,235 à 2,613 sur un
    # extrait réel), la saisie de terrain des millimètres. Un C13 de 235 ou plus serait en mm.
    valeurs = [float(s["C13"].replace(",", ".")) for s in _csv("ARBRE.csv") if s["C13"].strip()]
    assert valeurs and 0.235 <= min(valeurs) and max(valeurs) < 4.0, (min(valeurs), max(valeurs))


def _rayon(c13_m):
    """IMOT 2025 p. 61 (tableau DIMESS), sur C13 de l'export en mètres : < 0,705 -> 6 m ;
    0,705 à < 1,175 -> 9 m ; >= 1,175 -> 15 m. 0,705 et 1,175 passent à la classe supérieure."""
    mm = round(c13_m * 1000)
    return 6 if mm < 705 else 9 if mm < 1175 else 15


def test_rayon_aux_seuils_0_705_et_1_175_m():
    assert [_rayon(x) for x in (0.704, 0.705, 1.174, 1.175)] == [6, 9, 9, 15]


def _visites():
    return {(s["CAMPAGNE"], s["IDP"]): int(s["VISITE"]) for s in _csv("PLACETTE.csv")}


def test_arbres_d130_depuis_c13_en_m_et_poids_par_cercle():
    # d130 = C13 x 100 / pi (cm), C13 en mètres ; 1re visite : weight_ha = 10000 / (pi R^2) avec R
    # le cercle de la classe de C13 (IMOT 2025 p. 61) ; 2e visite : W de l'export, vide s'il manque
    # (rien n'est deviné). Les arbres se retrouvent par (IDP, campagne, A).
    rows = H.read_parquet(H.ZONE / "ifn" / "trees.parquet")
    src = _csv("ARBRE.csv")
    assert len(rows) == len(src) > 386
    par_cle = {(str(r["plot_id"]), r["campaign"], str(r["tree_id"])): r for r in rows}
    assert len(par_cle) == len(rows), "arbre en double dans ifn/trees.parquet"
    visites = _visites()
    for s in src:
        r = par_cle[(s["IDP"], int(s["CAMPAGNE"]), s["A"])]
        assert r["species"] == s["ESPAR"] and isinstance(r["species"], str)
        if not s["C13"].strip():
            assert r["d130"] is None, (s["IDP"], s["A"], r["d130"])
            continue
        c13 = float(s["C13"].replace(",", "."))
        assert r["d130"] == pytest.approx(c13 * 100 / math.pi, abs=0.01), (s["IDP"], s["A"])
        if visites[(s["CAMPAGNE"], s["IDP"])] == 1:
            attendu = round(1e4 / (math.pi * _rayon(c13) ** 2), 2)
            assert r["weight_ha"] == pytest.approx(attendu, rel=0.005), (s["IDP"], s["A"], c13)
        elif s["W"].strip():
            assert r["weight_ha"] == pytest.approx(float(s["W"]), abs=0.01), (s["IDP"], s["A"])
        else:
            assert r["weight_ha"] is None, (s["IDP"], s["A"])


def test_poids_exacts_aux_seuils_0_705_et_1_175_m():
    rows = H.read_parquet(H.ZONE / "ifn" / "trees.parquet")
    par_cle = {(str(r["plot_id"]), r["campaign"], str(r["tree_id"])): r for r in rows}
    visites = _visites()
    for c13_mm, poids in ((705, 39.30), (1175, 14.15)):
        cles = [(s["IDP"], int(s["CAMPAGNE"]), s["A"]) for s in _csv("ARBRE.csv")
                if s["C13"].strip() and _mm(s["C13"]) == c13_mm
                and visites[(s["CAMPAGNE"], s["IDP"])] == 1]
        assert cles, f"aucun arbre de 1re visite à C13 = {c13_mm / 1000} m dans ARBRE.csv"
        for k in cles:
            assert par_cle[k]["weight_ha"] == pytest.approx(poids, abs=0.01), (c13_mm, k)


def test_flore_une_ligne_par_releve():
    rows = H.read_parquet(H.ZONE / "ifn" / "flora.parquet")
    src = _csv("FLORE.csv")
    assert len(rows) == len(src) > 174
    a = sorted((s["IDP"], int(s["CD_REF"]), int(s["ABOND"])) for s in src)
    o = sorted((str(r["plot_id"]), int(r["cd_ref"]), int(r["abundance"])) for r in rows)
    assert a == o
