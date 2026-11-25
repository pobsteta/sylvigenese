"""Chaîne `make prepare biomes dynamics` et contrats des params (spec §2, §6, §10, §11 : « Ajustement
sur un extrait IFN »). Un test = une phrase, en français."""
import pytest

import helpers_m2 as H


def test_la_chaine_prepare_biomes_dynamics_aboutit_sans_reseau(chaine):
    # L'environnement des tests coupe le réseau (proxys morts) : aucune étape ne doit en dépendre.
    p = chaine["make"]
    assert p.returncode == 0, f"make prepare biomes dynamics : code {p.returncode}\n{p.stderr[-1500:]}"


@pytest.mark.parametrize("nom", H.PARAMS)
def test_dynamics_appelle_le_validateur_en_fin_de_module(chaine, nom):
    # Spec §2 : « chaque module l'appelle en sous-processus, à la fin de son travail ».
    sortie = chaine["make"].stdout
    assert f"contrat dynamics.{nom})" in sortie, \
        f"le module n'a pas contrôlé params/{nom}.parquet (aucune ligne « conforme » dans la sortie)"


def test_les_quatre_tables_et_le_rapport_sont_ecrits(chaine):
    manquants = [r for r in (H.RAPPORT, *[f"params/{p}.parquet" for p in H.PARAMS])
                 if not (H.ZONE / r).is_file()]
    assert not manquants, f"sorties absentes : {manquants}"


@pytest.mark.parametrize("nom", H.PARAMS)
def test_params_conformes_au_contrat(chaine, nom):
    p = H.validate(f"dynamics.{nom}", str(H.ZONE / "params" / f"{nom}.parquet"))
    assert p.returncode == 0, f"params/{nom}.parquet non conforme (code {p.returncode}) :\n{p.stderr[-1200:]}"


@pytest.mark.parametrize("nom", H.PARAMS)
def test_params_non_vides(params, nom):
    assert len(params[nom]) > 0, f"params/{nom}.parquet est vide"


def test_codes_d_essence_des_params_sont_au_referentiel_et_dans_les_donnees(params, ifn):
    # « Tout code produit appartient aux référentiels » ; « ne rien inventer » : pas d'essence que
    # l'extrait IFN ne contient pas. Code espar en chaîne, zéro de tête compris.
    referentiel = H.species_referentiel()
    dans_les_donnees = {t["ESPAR"] for t in ifn.trees}
    for nom, rows in params.items():
        for r in rows:
            sp = r.get("species")
            if sp is None:
                assert r.get("species_group"), f"{nom} : ligne sans essence ni groupe : {r}"
                continue
            assert isinstance(sp, str), (nom, sp)
            assert sp in referentiel, f"{nom} : essence {sp!r} hors de contracts/species.csv"
            assert sp in dans_les_donnees, f"{nom} : essence {sp!r} absente de l'extrait IFN"


@pytest.mark.parametrize("nom", H.PARAMS)
def test_chaque_essence_du_jeu_est_ajustee_seule_ou_en_groupe(params, rapport, ifn, nom):
    # Essence ajustée seule, ou rangée dans un groupe dont le rapport donne les membres.
    rows = params[nom]
    seules = {r["species"] for r in rows if r.get("species")}
    groupes = [r for r in rows if r.get("species_group") and not r.get("species")]
    for code in sorted({t["ESPAR"] for t in ifn.trees}):
        if code in seules:
            continue
        assert groupes, f"{nom} : l'essence {code} n'a ni ligne propre ni groupe"
        assert H.species_blocks(rapport, code), \
            f"{nom} : l'essence {code} est en groupe mais le rapport ne dit pas où"


@pytest.mark.parametrize("nom", H.PARAMS)
def test_params_provisoires_et_sources_comme_issus_du_jeu_fictif(params, nom):
    # Spec §10 : chaque paramètre porte `provisoire` et sa source ; CLAUDE.md : jamais un coefficient
    # ajusté sur le jeu fictif présenté comme écologique.
    for r in params[nom]:
        assert r["provisoire"] is True, f"{nom} : coefficient non provisoire ajusté sur le jeu fictif : {r}"
        src = H.sans_accent(r["source"] or "")
        assert "synthet" in src or "fictif" in src, \
            f"{nom} : la source ne dit pas que le jeu est fictif : {r['source']!r}"


def test_deux_lancements_donnent_des_params_identiques(chaine):
    # Reproductibilité (graine) : rejouer `make dynamics` sur la même zone redonne les mêmes valeurs.
    p1, p2 = chaine["params_1"], chaine["params_2"]
    assert chaine["make_2"].returncode == 0, chaine["make_2"].stderr[-1200:]
    assert p1 is not None and p2 is not None, "params absents après l'un des lancements"
    for nom in H.PARAMS:
        assert p1[nom] == p2[nom], f"params/{nom}.parquet diffère d'un lancement à l'autre"


def test_une_zone_neuve_redonne_les_memes_params(chaine, zone_rejeu):
    # Même entrée, autre dossier, tout recalculé depuis prepare : mêmes params (aucune dépendance au
    # chemin, à l'horloge ni à un état laissé par un lancement précédent).
    assert zone_rejeu["make"].returncode == 0, zone_rejeu["make"].stderr[-1500:]
    autre = H.read_params(zone_rejeu["dir"])
    for nom in H.PARAMS:
        assert chaine["params_1"][nom] == autre[nom], f"params/{nom}.parquet dépend de la zone"


def test_dynamics_ne_lit_que_ifn(zone_rejeu):
    # Spec §2 : entrées de dynamics = `ifn/`. On rejoue sur une zone d'où tout le reste a disparu
    # (entrées, rasters, tables de catégories) : le module doit aboutir, aucun import caché d'un autre module.
    import shutil
    nom = "m2_ifn_seul"
    try:
        d, cfg = H.clone_zone(zone_rejeu["name"], nom)
        shutil.rmtree(d / "inputs")
        for f in list(d.iterdir()):
            if f.name not in ("ifn", "params", cfg.name):
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        shutil.rmtree(d / "params")
        (d / "params").mkdir()
        p = H.run_module_status("dynamics", cfg)
        assert p.returncode == 0, f"dynamics a besoin d'autre chose que ifn/ :\n{p.stderr[-1500:]}"
        assert set(H.dynamics_outputs(d)) == {H.RAPPORT, *[f"params/{x}.parquet" for x in H.PARAMS]}
    finally:
        H.remove_zone_copy(nom)
