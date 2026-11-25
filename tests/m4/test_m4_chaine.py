"""Chaîne `make prepare biomes trees assets` et contrats des sorties (spec §2, §9, §11 : M4a, état initial)."""
import json

import pytest

import helpers_m4 as H


def test_le_jeu_fictif_a_14080_arbres(oracle):
    # Garde-fou de l'oracle : la fiche 028 annonce 14 080 instances ; si trees_init change, les tests le disent.
    assert oracle.n_trees == 14080


def test_la_chaine_prepare_biomes_trees_assets_aboutit_sans_reseau(chaine):
    p = chaine["make"]
    assert p.returncode == 0, f"make prepare biomes trees assets : code {p.returncode}\n{p.stderr[-1500:]}"


def test_assets_appelle_le_validateur_en_fin_de_module(chaine):
    # Spec §2 : « chaque module l'appelle en sous-processus, à la fin de son travail ».
    sortie = chaine["make"].stdout
    for contrat in ("assets.tileset", "assets.cell_sheet", "assets.web_raster"):
        assert f"contrat {contrat})" in sortie, f"le module n'a pas contrôlé ses sorties contre {contrat}"


def test_les_sorties_sont_aux_chemins_du_catalogue(chaine):
    assert len(H.find_tilesets(H.ZONE)) == 1, "attendu : exactement un tiles/<année>/tileset.json (une seule année)"
    assert list((H.ZONE / "web" / "cells").glob("*.json")), "aucune fiche web/cells/<tuile>.json"
    assert list((H.ZONE / "web" / "rasters").glob("*.tif")), "aucun raster web/rasters/*.tif"


def test_l_annee_du_dossier_de_tuiles_est_une_annee(chaine):
    ts = H.find_tilesets(H.ZONE)
    assert ts, "aucun tileset"
    d = ts[0].parent.name
    assert d.isdigit() and len(d) == 4 and 1900 < int(d) < 2300, f"tiles/{d}/ : année attendue"


def test_assets_n_ecrit_que_sous_ses_dossiers(chaine):
    # Les entrées et les sorties de prepare/biomes/trees ne sont pas modifiées par assets (rejeu).
    avant, apres = chaine["hors_assets_1"], chaine["hors_assets_2"]
    assert avant == apres, f"fichiers hors assets modifiés par `make assets` : {sorted(k for k in avant if avant[k] != apres.get(k))}"


def test_le_rejeu_de_assets_rend_les_memes_sorties(chaine):
    assert chaine["make_2"].returncode == 0, chaine["make_2"].stderr[-1500:]
    a, b = chaine["sorties_1"], chaine["sorties_2"]
    assert a, "aucune sortie de assets"
    assert a.keys() == b.keys(), f"fichiers différents : {sorted(set(a) ^ set(b))}"
    assert [k for k in a if a[k] != b[k]] == [], f"sorties différentes au rejeu : {[k for k in a if a[k] != b[k]]}"


def test_tileset_conforme_au_validateur(chaine):
    ts = H.find_tilesets(H.ZONE)
    assert ts, "aucun tileset"
    p = H.validate("assets.tileset", str(ts[0]))
    assert p.returncode == 0, f"tileset.json non conforme (code {p.returncode}) :\n{p.stderr[-1500:]}"


def test_fiches_conformes_au_validateur(chaine):
    fiches = sorted((H.ZONE / "web" / "cells").glob("*.json"))
    assert fiches, "aucune fiche"
    p = H.validate("assets.cell_sheet", *map(str, fiches))
    assert p.returncode == 0, f"fiche non conforme (code {p.returncode}) :\n{p.stderr[-1500:]}"


def test_rasters_web_conformes_au_profil_cog(chaine):
    tifs = sorted((H.ZONE / "web" / "rasters").glob("*.tif"))
    assert tifs, "aucun raster"
    p = H.validate("assets.web_raster", *map(str, tifs))
    assert p.returncode == 0, f"raster non conforme au profil cog (code {p.returncode}) :\n{p.stderr[-1500:]}"


def test_aucun_glb_et_des_gltf_dans_les_tuiles(chaine):
    # docs/referentiels/itowns-instancing.md, point A : iTowns ne déclare son gestionnaire que pour /\.gltf$/.
    assert (H.ZONE / "tiles").is_dir(), "tiles/ absent"
    assert not list((H.ZONE / "tiles").rglob("*.glb")), "contenu .glb : le gestionnaire d'iTowns attend .gltf"
    assert list((H.ZONE / "tiles").rglob("*.gltf")), "aucun contenu .gltf"


def test_le_validateur_refuse_un_tileset_en_version_1_0(tmp_path):
    # Témoin du contrat : un tileset en 1.0 est refusé (spec §9 : 3D Tiles 1.1) ; garde le test de conformité honnête.
    ts = {"asset": {"version": "1.0"}, "geometricError": 10,
          "root": {"boundingVolume": {"box": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]}, "geometricError": 0, "refine": "ADD"}}
    f = tmp_path / "tileset.json"
    f.write_text(json.dumps(ts), encoding="utf-8")
    assert H.validate("assets.tileset", str(f)).returncode == 3


@pytest.mark.parametrize("rel", ["rapport_arbres.html", "vegetation_map.tif", "stand_map.tif", "h0.tif"])
def test_la_chaine_a_ecrit_les_sorties_amont(chaine, rel):
    assert (H.ZONE / rel).is_file(), f"{rel} absent après make prepare biomes trees"
