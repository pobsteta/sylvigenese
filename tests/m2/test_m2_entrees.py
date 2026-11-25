"""Entrées de la dynamique : jeu fictif IFN conforme à la documentation (Q3), colonnes préparées par
prepare pour dynamics (Q8), et entrées refusées (code 2, aucune sortie à moitié ; spec §3 et §6).
"""
import math

import pytest

import helpers_m2 as H


def _codes_veget(campagne):
    """VEGET de 1re visite selon la période (metadonnees.csv l. 6067-6074, DOM8M1 puis DOM8M2)."""
    return {"0", "1", "5", "C"} if campagne >= 2019 else {"0", "A", "5", "C"}


def _codes_veget5(campagne):
    """VEGET5 de 2e visite selon la période (metadonnees.csv l. 6075-6099)."""
    if campagne >= 2019:
        return {"0", "6", "7", "1", "2", "M", "N", "T"}
    if campagne >= 2017:
        return {"0", "6", "7", "A", "M", "N", "T"}
    if campagne >= 2015:
        return {"0", "M", "A", "6", "N"}
    return {"0", "6", "A", "5", "C"}


# ------------------------------------------------------------------ le jeu fictif suit la documentation
def test_jeu_fictif_une_2e_visite_est_a_la_campagne_de_la_1re_plus_5(ifn):
    # ifn-dynamique.md §1 : le point revu garde son IDP, sa 2e visite est cinq campagnes après la 1re.
    assert ifn.revisited_plots(), "aucune placette revue dans le jeu fictif"
    for idp in ifn.revisited_plots():
        v = ifn.plot_rows[idp]
        assert int(v[2]["CAMPAGNE"]) == int(v[1]["CAMPAGNE"]) + 5, idp


def test_jeu_fictif_c13_en_metres_et_a_partir_du_seuil_de_recensabilite(ifn):
    # Piège de l'unité : l'export donne des mètres. Seuil 0,235 m (D13 >= 7,5 cm) ; une valeur de 235 ou
    # plus serait en millimètres.
    c13 = [H.mm(t["C13"]) for t in ifn.trees if t["C13"].strip()]
    assert min(c13) >= 235 and max(c13) < 4000, (min(c13), max(c13))


def test_jeu_fictif_codes_de_vegetation_de_la_bonne_periode(ifn):
    # `5` est « mort sur pied » dans VEGET mais `M` dans VEGET5 à partir de 2015 : les codes d'une même
    # colonne changent de nomenclature selon la campagne (piège de codage, ifn-dynamique.md §4).
    for t in ifn.trees:
        visite = ifn.visit[(t["CAMPAGNE"], t["IDP"])]
        c = int(t["CAMPAGNE"])
        if visite == 2:
            assert t["VEGET"] == "", f"VEGET sur une ligne de 2e visite : {t}"
            assert t["VEGET5"] in _codes_veget5(c), f"VEGET5 hors de la nomenclature de {c} : {t}"
        else:
            assert t["VEGET5"] == "", f"VEGET5 sur une ligne de 1re visite : {t}"
            assert t["VEGET"] in _codes_veget(c), f"VEGET hors de la nomenclature de {c} : {t}"


def test_jeu_fictif_exerce_chaque_cas_de_la_mortalite_et_du_recrutement(ifn):
    # Sans arbre coupé, non retrouvé, perdu, mort, recrue ou incident, aucun test de règle ne discrimine.
    etats = {t["VEGET5"] for t in ifn.trees}
    assert {"0", "M", "6", "7", "N", "T"} <= etats, etats
    assert ifn.incident_plots(), "aucune placette à incident"
    assert ifn.recruits(set()), "aucune recrue"
    assert any(not t["IR5"].strip() for t in ifn.trees if t["VEGET"] == "0"), "IR5 toujours renseigné"
    assert any(t["IR5"].strip() for t in ifn.trees), "IR5 jamais renseigné"
    assert any(i not in ifn.revisited_plots() for i in ifn.plot_rows), "toutes les placettes sont revues"


def test_jeu_fictif_flore_seulement_a_la_1re_visite(ifn):
    # FLO p.2 : la flore n'est relevée qu'en 1re visite.
    assert all(ifn.visit[(f["CAMPAGNE"], f["IDP"])] == 1 for f in ifn.flora)


def test_jeu_fictif_les_placettes_sont_a_moins_de_700_m_de_la_zone_de_station(ifn):
    # Le README du jeu fictif floute les placettes de 700 m au plus ; le point réel est dans le massif, donc
    # le point flouté est à moins de 700 m du raster de station et son disque de 700 m le recouvre (sinon
    # coarse_*_700m est vide et dynamics n'a presque aucune station à l'ajustement).
    sans = H.plots_sans_station(H.ZONE)
    assert not sans, f"{len(sans)} placettes sur {len(ifn.plot_rows)} n'ont aucune maille de station dans leur disque de 700 m"


# ------------------------------------------------------------------ ce que prepare donne à dynamics (Q8)
def test_prepare_garde_une_ligne_par_visite_avec_les_colonnes_de_la_dynamique(chaine, ifn):
    plots = {(p["plot_id"], p["campaign"]): p for p in H.read_parquet(H.ZONE / "ifn" / "plots.parquet")}
    trees = {(t["plot_id"], t["campaign"], t["tree_id"]): t for t in H.read_parquet(H.ZONE / "ifn" / "trees.parquet")}
    assert len(plots) == len(ifn.plots) and len(trees) == len(ifn.trees)
    for s in ifn.plots:
        p = plots[(s["IDP"], int(s["CAMPAGNE"]))]
        assert p["visit"] == int(s["VISITE"])
        if s["DATEPOINT"]:
            j, m, a = s["DATEPOINT"].split("/")
            assert p["date_point"] == f"{a}-{m}-{j}", (s["IDP"], p["date_point"], s["DATEPOINT"])
        for src, col in (("NINCID", "incident_nature"), ("INCID", "incident_intensity"),
                         ("DEF5", "clearing_5y"), ("INSTP5", "planting_5y")):
            assert (p[col] is None) == (s[src] == ""), (s["IDP"], src, p[col], s[src])
            if s[src] != "":
                assert p[col] == int(s[src])
    for s in ifn.trees:
        t = trees[(s["IDP"], int(s["CAMPAGNE"]), s["A"])]
        c = int(s["CAMPAGNE"])
        assert t["veg_state"] == (s["VEGET"] if s["VEGET"] in _codes_veget(c) else None), (s["IDP"], s["A"])
        assert t["veg_state_5y"] == (s["VEGET5"] if s["VEGET5"] in _codes_veget5(c) else None), (s["IDP"], s["A"])
        if s["IR5"]:
            assert t["radial_incr_5y_m"] == pytest.approx(float(s["IR5"]), abs=1e-9)
        else:
            assert t["radial_incr_5y_m"] is None
        if s["C13"]:
            assert t["d130"] == pytest.approx(float(s["C13"]) * 100 / math.pi, abs=0.01)


# ------------------------------------------------------------------ entrées refusées : prepare
def test_prepare_refuse_l_entree_ifn_fautive_avec_le_code_2_et_nomme_le_fichier(refus_prepare):
    nom, d, p, mots = refus_prepare
    assert p.returncode == 2, f"{nom} : code {p.returncode} (attendu 2)\n{p.stderr[-1200:]}"
    assert p.stderr.strip(), f"{nom} : aucun message d'erreur"
    assert any(m in p.stderr for m in mots), f"{nom} : le message ne nomme aucun de {mots}\n{p.stderr[-800:]}"


def test_prepare_refusee_ne_laisse_aucune_sortie_a_moitie(refus_prepare):
    nom, d, p, _ = refus_prepare
    produits = [f for f in ("grid.tif", "stands.parquet", "ifn", "trees_init") if (d / f).exists()]
    assert not produits, f"{nom} : sorties écrites malgré le refus : {produits}"
    assert not H.dynamics_outputs(d), f"{nom} : sorties de dynamics présentes"


# ------------------------------------------------------------------ entrées refusées : dynamics
def test_dynamics_refuse_son_entree_avec_le_code_2_et_un_message_en_francais(refus_dynamics):
    nom, d, p, mots = refus_dynamics
    assert p.returncode == 2, f"{nom} : code {p.returncode} (attendu 2)\n{p.stderr[-1200:]}"
    assert p.stderr.strip(), f"{nom} : aucun message d'erreur"
    assert any(m in p.stderr for m in mots), f"{nom} : le message ne nomme aucun de {mots}\n{p.stderr[-800:]}"


def test_dynamics_refusee_ne_laisse_aucune_sortie_a_moitie(refus_dynamics):
    nom, d, p, _ = refus_dynamics
    assert not H.dynamics_outputs(d), f"{nom} : sorties écrites malgré le refus : {H.dynamics_outputs(d)}"
