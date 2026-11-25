"""Règles d'ajustement de la spec §6 « Données d'ajustement » (décisions Q2 à Q8 du 25/11/2026).

Chaque règle a deux tests : un compte attendu recalculé depuis les entrées brutes (oracle de
helpers_m2.Ifn) sur le jeu fictif, puis une zone variante qui change ce compte d'une valeur connue ;
le rapport doit suivre. Un rapport figé, ou une règle ignorée, ne passe pas la variante.

Le format du rapport n'est pas imposé par la spec : un compte est « au rapport » s'il figure comme
entier dans un bloc (ligne de tableau, item, paragraphe) qui porte les mots de la règle. Les lectures
admises des placettes écartées sont deux (incidents seuls, ou incidents et travaux DEF5/INSTP5) ;
pour les retraits, un troisième (comptés avant d'écarter les placettes). La variante doit suivre la
MÊME lecture que le jeu de base.
"""
import pytest

import helpers_m2 as H


def _lectures(ifn, avec_toutes=False):
    d = dict(ifn.definitions())
    if avec_toutes:
        d["toutes_les_placettes"] = set()
    return d


def _comptes(ifn, fonction, avec_toutes=False):
    return {nom: fonction(ex) for nom, ex in _lectures(ifn, avec_toutes).items()}


def _suit(base_blocs, var_blocs, mots, cand_base, cand_var, quoi):
    """Une lecture qui retrouve le compte du jeu de base doit retrouver celui de la variante."""
    ok_base = H.matching_definitions(base_blocs, mots, cand_base)
    assert ok_base, f"{quoi} : le jeu de base n'a aucun des comptes attendus {cand_base} dans un bloc « {mots} »"
    ok_var = H.matching_definitions(var_blocs, mots, {k: cand_var[k] for k in ok_base})
    assert ok_var, (f"{quoi} : la variante devrait donner {({k: cand_var[k] for k in ok_base})} "
                    f"(base : {({k: cand_base[k] for k in ok_base})}) dans un bloc « {mots} »")


def _bloc_variante(zone):
    assert zone["make"].returncode == 0, f"make prepare dynamics sur {zone['name']} : code " \
        f"{zone['make'].returncode}\n{zone['make'].stderr[-1500:]}"
    return H.html_blocks(zone["rapport"])


# ------------------------------------------------------------------ jeu de base
def test_effectif_a_risque_par_essence_suit_la_population_de_la_spec(rapport, ifn):
    # Population à risque = arbres vivants (VEGET = 0) à la 1re visite, revus, hors placettes écartées ;
    # coupés, non retrouvés et perdus en sont retirés (Q2). Effectif par essence = vivants + morts naturels.
    for code in sorted({t["ESPAR"] for t in ifn.trees}):
        cand = {nom: ifn.mortality_counts(ex).get(code, {}).get("n", 0) for nom, ex in _lectures(ifn).items()}
        assert any(v > 0 for v in cand.values()), f"jeu fictif sans arbre à risque de l'essence {code}"
        ints = H.ints_in_blocks(H.species_blocks(rapport, code))
        assert set(cand.values()) & ints, \
            f"essence {code} : effectif à risque attendu {cand}, entiers de sa ligne {sorted(ints)}"


@pytest.mark.parametrize("cle,mots", [("coupes", ("coupe",)), ("non_retrouves", ("non retrouve",)),
                                      ("perdus", ("perdu",))])
def test_coupes_non_retrouves_et_perdus_sont_retires_et_comptes(rapport, ifn, cle, mots):
    # Spec §6 : « arbres coupés (6, 7), non retrouvés (N) ou perdus (T) : retirés de la population et
    # comptés au rapport ».
    cand = _comptes(ifn, lambda ex: ifn.removed_totals(ex).get(cle, 0), avec_toutes=True)
    assert any(v > 0 for v in cand.values()), f"jeu fictif sans arbre « {cle} »"
    trouves = H.matching_definitions(rapport, mots, cand)
    assert trouves, f"« {cle} » : compte attendu parmi {cand}, absent des blocs « {mots} »"


def test_placettes_a_incident_ecartees_et_comptees(rapport, ifn):
    cand = {nom: len(pl & ifn.revisited_plots()) for nom, pl in _lectures(ifn).items()}
    assert cand["incidents"] > 0, "jeu fictif sans placette à incident"
    assert H.matching_definitions(rapport, ("placette", "ecart"), cand), \
        f"placettes écartées : compte attendu parmi {cand}, absent des blocs « placette » + « écart »"


def test_recrues_sont_les_arbres_de_2e_visite_sans_1re_visite(rapport, ifn):
    cand = _comptes(ifn, lambda ex: len(ifn.recruits(ex)), avec_toutes=True)
    assert all(v > 0 for v in cand.values()), "jeu fictif sans recrue"
    assert H.matching_definitions(rapport, ("recrue",), cand), \
        f"recrues : compte attendu parmi {cand}, absent des blocs « recrue »"


def test_intervalle_entre_visites_vient_de_datepoint_et_le_rapport_le_dit(rapport, ifn):
    # Q6 : DATEPOINT des deux visites quand il existe (le jeu fictif l'a pour toutes les placettes).
    assert all(p["DATEPOINT"] for p in ifn.plots), "jeu fictif sans DATEPOINT"
    assert H.blocks_with(rapport, "intervalle", "datepoint"), \
        "le rapport ne dit pas d'où vient l'intervalle entre visites (DATEPOINT)"


def test_accroissement_ir5_avec_la_difference_de_c13_en_controle_au_rapport(rapport):
    # Spec §6 : accroissement = IR5 (cumul de 5 cernes, en m) quand il existe ; « la différence de C13
    # entre visites sert de contrôle, écrit au rapport ».
    blocs = H.blocks_with(rapport, "ir5", "c13")
    assert blocs, "le rapport ne confronte pas IR5 à la différence de C13 entre visites"
    assert any(H.decimals_in(b) for b in blocs), "le contrôle IR5 / C13 est cité sans aucun chiffre"


# ------------------------------------------------------------------ retirés, pas morts
def test_variante_retraits_le_rapport_suit_les_comptes(zone_retraits, rapport, ifn):
    blocs = _bloc_variante(zone_retraits)
    var = H.ifn_de(zone_retraits["dir"])
    for cle, mots in (("coupes", ("coupe",)), ("non_retrouves", ("non retrouve",)), ("perdus", ("perdu",))):
        cb = _comptes(ifn, lambda ex: ifn.removed_totals(ex).get(cle, 0), avec_toutes=True)
        cv = _comptes(var, lambda ex: var.removed_totals(ex).get(cle, 0), avec_toutes=True)
        assert cv != cb, f"la variante ne change pas le compte « {cle} » : test vide"
        _suit(rapport, blocs, mots, cb, cv, cle)


def test_variante_retraits_l_effectif_de_l_essence_diminue_d_autant(zone_retraits, rapport, ifn):
    blocs = _bloc_variante(zone_retraits)
    var = H.ifn_de(zone_retraits["dir"])
    code = H.ESSENCE_CIBLE
    cb = _comptes(ifn, lambda ex: ifn.mortality_counts(ex).get(code, {}).get("n", 0))
    cv = _comptes(var, lambda ex: var.mortality_counts(ex).get(code, {}).get("n", 0))
    assert all(cv[k] < cb[k] for k in cb), "la variante ne réduit pas l'effectif à risque : test vide"
    _suit(H.species_blocks(rapport, code), H.species_blocks(blocs, code), (), cb, cv,
          f"effectif à risque de l'essence {code}")


def _distance(a, b):
    va, vb = H.param_vector(a), H.param_vector(b)
    cles = set(va) & set(vb)
    assert cles, "aucun coefficient commun entre les deux ajustements"
    return sum(abs(va[k] - vb[k]) for k in cles)


def test_variante_un_arbre_coupe_ne_compte_pas_comme_un_arbre_mort(zone_retraits, zone_morts, params):
    # Mêmes arbres, deux sorts : retirés (coupés, non retrouvés, perdus) ou morts sur pied (M). Si les
    # retirés étaient comptés morts, les deux ajustements de la mortalité seraient les mêmes ; retirés, ils
    # ne bougent pas la mortalité de la même façon que des morts.
    _bloc_variante(zone_retraits), _bloc_variante(zone_morts)
    base = params["mortality"]
    retires = H.read_parquet(zone_retraits["dir"] / "params" / "mortality.parquet")
    morts = H.read_parquet(zone_morts["dir"] / "params" / "mortality.parquet")
    d_morts, d_retires = _distance(morts, base), _distance(retires, base)
    assert d_morts > 0, "la mortalité n'a pas bougé quand 40 % des arbres de l'essence sont morts : test vide"
    assert d_retires < d_morts, (f"des arbres retirés pèsent autant que des morts sur la mortalité "
                                 f"(écart au jeu de base : retirés {d_retires:.4g}, morts {d_morts:.4g})")


# ------------------------------------------------------------------ placettes à incident
def test_variante_incidents_placettes_ecartees_et_effectifs_suivent(zone_incidents, rapport, ifn):
    blocs = _bloc_variante(zone_incidents)
    var = H.ifn_de(zone_incidents["dir"])
    cb = {n: len(pl & ifn.revisited_plots()) for n, pl in _lectures(ifn).items()}
    cv = {n: len(pl & var.revisited_plots()) for n, pl in _lectures(var).items()}
    assert all(cv[k] > cb[k] for k in cb), (cb, cv)
    _suit(rapport, blocs, ("placette", "ecart"), cb, cv, "placettes écartées")
    for code in sorted({t["ESPAR"] for t in ifn.trees}):
        eb = _comptes(ifn, lambda ex: ifn.mortality_counts(ex).get(code, {}).get("n", 0))
        ev = _comptes(var, lambda ex: var.mortality_counts(ex).get(code, {}).get("n", 0))
        assert all(ev[k] <= eb[k] for k in eb)
        _suit(H.species_blocks(rapport, code), H.species_blocks(blocs, code), (), eb, ev,
              f"effectif à risque de l'essence {code} après écart des placettes à incident")


# ------------------------------------------------------------------ recrues
def test_variante_recrues_seuil_de_recensabilite_et_poids_non_devine(zone_recrues, rapport, ifn):
    blocs = _bloc_variante(zone_recrues)
    var = H.ifn_de(zone_recrues["dir"])
    cb = _comptes(ifn, lambda ex: len(ifn.recruits(ex)), avec_toutes=True)
    cv = _comptes(var, lambda ex: len(var.recruits(ex)), avec_toutes=True)
    assert all(cv[k] == cb[k] + H.NOUVELLES_RECRUES for k in cb), "variante mal construite"
    # +6 recrues de C13 = 0,236 m ; +3 de C13 = 0,234 m, sous le seuil de 0,235 m : elles ne comptent pas.
    _suit(rapport, blocs, ("recrue",), cb, cv, "recrues")
    # Poids : « leur poids suit W de l'export, sinon il est signalé, jamais deviné ».
    sb = _comptes(ifn, ifn.recruits_sans_poids, avec_toutes=True)
    sv = _comptes(var, var.recruits_sans_poids, avec_toutes=True)
    assert all(sv[k] == sb[k] + H.RECRUES_SANS_POIDS for k in sb)
    poids = H.blocks_with(blocs, "recrue", "poids")
    assert poids, "le rapport ne dit rien du poids des recrues"
    ok = H.matching_definitions(blocs, ("recrue", "poids"), sv)
    assert ok, f"recrues sans poids : attendu {sv}, entiers des blocs « recrue » + « poids » : {sorted(H.ints_in_blocks(poids))}"


def test_variante_domaine_de_validite_suit_l_arbre_le_plus_gros(zone_recrues, rapport):
    # Un arbre de l'essence 62 passe à C13 = 2,90 m (d130 92,3 cm) : le jeu fictif n'allait que jusqu'à
    # 81,7 cm. Le domaine de validité de l'essence doit le montrer (d130 en cm ou C13 en m).
    blocs = _bloc_variante(zone_recrues)

    def dans_domaine(bl):
        for b in H.species_blocks(bl, "62"):
            for x in H.numbers_in(b):
                if 91.7 <= x <= 93.5 or 2.88 <= x <= 2.94:
                    return True
        return False

    assert not dans_domaine(rapport), "le jeu de base atteint déjà 92 cm : variante sans effet"
    assert dans_domaine(blocs), "le domaine de l'essence 62 ignore l'arbre de 92,3 cm de d130 (C13 2,90 m)"


# ------------------------------------------------------------------ intervalle
def test_variante_sans_datepoint_l_intervalle_nominal_de_5_ans_est_dit(zone_sans_datepoint, rapport, ifn):
    blocs = _bloc_variante(zone_sans_datepoint)
    dit = [b for b in H.blocks_with(blocs, "intervalle", "datepoint")
           if "nominal" in H.sans_accent(b) or "5 ans" in H.sans_accent(b)]
    assert dit, "sans DATEPOINT, le rapport ne dit pas que l'intervalle est nominal (5 ans)"
    revues = len(ifn.revisited_plots())
    cand = {"placettes revues": revues, "placettes": len({p["IDP"] for p in ifn.plots}),
            "lignes": len(ifn.plots)}
    assert H.ints_in_blocks(H.blocks_with(blocs, "datepoint")) & set(cand.values()), \
        f"le rapport ne compte pas les placettes sans DATEPOINT (attendu l'un de {cand})"
    assert H.blocks_with(rapport, "intervalle", "datepoint") != H.blocks_with(blocs, "intervalle", "datepoint"), \
        "l'intervalle est dit de la même façon avec et sans DATEPOINT"


def test_date_incoherente_est_refusee_ou_signalee_jamais_utilisee_en_silence(zone_date_incoherente):
    # DATEPOINT de la 2e visite (01/01/2010) antérieure à celle de la 1re : l'intervalle serait négatif.
    z = zone_date_incoherente
    idp = z["idp"]
    if z["prepare"].returncode != 0:
        assert z["prepare"].returncode == 2, z["prepare"].stderr[-800:]
        assert "DATEPOINT" in z["prepare"].stderr, "refus sans nommer DATEPOINT"
        return
    d = z["dynamics"]
    assert d is not None
    if d.returncode != 0:
        assert d.returncode == 2 and "DATEPOINT" in d.stderr, d.stderr[-800:]
        assert not H.dynamics_outputs(z["dir"]), "sorties à moitié écrites malgré le refus"
        return
    blocs = H.html_blocks(z["dir"] / H.RAPPORT)
    ok = [b for b in H.blocks_with(blocs, "datepoint") if idp in b or "incoher" in H.sans_accent(b)
          or "anterieur" in H.sans_accent(b) or "negatif" in H.sans_accent(b)]
    assert ok, f"date incohérente (placette {idp}) ni refusée ni signalée au rapport"


# ------------------------------------------------------------------ pas de 2e visite
def test_sans_revisite_dynamics_refuse_avec_le_code_2_et_ne_laisse_rien(zone_sans_revisite):
    z = zone_sans_revisite
    assert z["prepare"].returncode == 0, f"prepare refuse un jeu à 1re visite seule :\n{z['prepare'].stderr[-1200:]}"
    d = z["dynamics"]
    assert d.returncode == 2, f"code {d.returncode} (attendu 2, entrée refusée)\n{d.stderr[-1000:]}"
    msg = H.sans_accent(d.stderr)
    assert "revisit" in msg or "2e visite" in msg or "deuxieme visite" in msg, \
        f"le message ne dit pas qu'il manque des 2e visites :\n{d.stderr[-800:]}"
    assert not H.dynamics_outputs(z["dir"]), f"sorties à moitié : {H.dynamics_outputs(z['dir'])}"
