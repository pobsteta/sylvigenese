"""Tests de `assets`, état initial (mission 028).

Le jeu fictif est copié dans un dossier temporaire : le dépôt n'est jamais écrit. Le validateur
appelé est le vrai (`contracts/validate`). Repère : un point de coordonnées connues (l'origine
du Lambert-93 : x = 700 000, y = 6 600 000, EPSG:2154, soit 3° E et 46,5° N) ancre les tests.
"""

import hashlib
import json
import math
import shutil
import struct
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as warp_transform

from sylvigenese import assets
from sylvigenese.assets_lib import altitude, etat_initial, modeles, repere, tuiles
from sylvigenese.commun import ErreurModule

RACINE = Path(__file__).resolve().parents[2]
FICTIF = RACINE / "tests" / "fixtures" / "zone_fictive"
CONFIG = {"zone": "zone_fictive", "crs": "EPSG:2154"}
RESUME: dict = {}  # résumé rendu par produire_etat_initial (rempli par la fixture `zone`)


@pytest.fixture(autouse=True)
def depuis_la_racine(monkeypatch):
    monkeypatch.chdir(RACINE)


SORTIES_ASSETS = shutil.ignore_patterns("tiles", "web", "assets", "sim")


@pytest.fixture(scope="module")
def zone(tmp_path_factory, zone_chaine):
    """Copie du jeu fictif passé par prepare, biomes et trees (conftest), + état initial produit."""
    dossier = tmp_path_factory.mktemp("zone") / "zone_fictive"
    shutil.copytree(zone_chaine, dossier, ignore=SORTIES_ASSETS)
    RESUME.update(assets.produire_etat_initial(CONFIG, dossier))
    return dossier


def empreintes(dossier: Path) -> dict:
    sorties = [p for sous in ("assets", "tiles", "web") for p in sorted((dossier / sous).rglob("*")) if p.is_file()]
    return {str(p.relative_to(dossier)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorties}


def lire_gltf(chemin: Path):
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    binaire = chemin.with_suffix(".bin").read_bytes()
    return doc, binaire


def lire_accesseur(doc, binaire, indice):
    acc = doc["accessors"][indice]
    vue = doc["bufferViews"][acc["bufferView"]]
    assert acc["componentType"] == 5126 and acc["type"] == "VEC3"
    debut = vue["byteOffset"] + acc.get("byteOffset", 0)
    return np.frombuffer(binaire, dtype="<f4", count=acc["count"] * 3, offset=debut).reshape(-1, 3)


# ---------------------------------------------------------------- repère (point connu)

def test_origine_du_lambert93_est_a_3_est_46_5_nord():
    lon_lat = repere.lambert_vers_lonlat(700000.0, 6600000.0)[0]
    assert lon_lat[0] == pytest.approx(3.0, abs=1e-9)
    assert lon_lat[1] == pytest.approx(46.5, abs=1e-9)


def test_ecef_de_l_origine_du_lambert93_contre_la_formule_wgs84():
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    lon, lat = math.radians(3.0), math.radians(46.5)
    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    attendu = [n * math.cos(lat) * math.cos(lon), n * math.cos(lat) * math.sin(lon), n * (1 - e2) * math.sin(lat)]
    obtenu = repere.lambert_vers_ecef(700000.0, 6600000.0, 0.0)[0]
    assert np.abs(obtenu - attendu).max() < 1.0  # RGF93 et WGS84 : moins d'un mètre


def test_repere_local_x_est_y_nord_haut():
    r = repere.RepereLocal(700000.0, 6600000.0, 100.0)
    origine = r.lambert_vers_local(700000.0, 6600000.0, 100.0)[0]
    assert np.abs(origine).max() < 1e-6
    est = r.lambert_vers_local(701000.0, 6600000.0, 100.0)[0]
    nord = r.lambert_vers_local(700000.0, 6601000.0, 100.0)[0]
    haut = r.lambert_vers_local(700000.0, 6600000.0, 150.0)[0]
    assert est[0] == pytest.approx(1000.0, abs=2.0) and abs(est[1]) < 1e-3  # x Lambert -> est
    assert nord[1] == pytest.approx(1000.0, abs=2.0) and abs(nord[0]) < 1e-3  # y Lambert -> nord
    assert haut[2] == pytest.approx(50.0, abs=1e-6) and abs(haut[0]) < 1e-6 and abs(haut[1]) < 1e-6


def test_aller_retour_glTF_local_ecef_lambert():
    r = repere.RepereLocal(700250.0, 6500750.0, 340.0)
    ecef = repere.lambert_vers_ecef(700153.25, 6500999.75, 331.5)
    enu = r.ecef_vers_local(ecef)
    gltf = repere.local_vers_gltf(enu)
    assert gltf[0, 0] == pytest.approx(enu[0, 0]) and gltf[0, 1] == pytest.approx(enu[0, 2])
    assert gltf[0, 2] == pytest.approx(-enu[0, 1])
    retour = repere.local_vers_ecef(r.transform_3dtiles(), repere.gltf_vers_local(gltf))
    assert np.abs(retour - ecef).max() < 1e-6
    x, y, z = warp_transform("EPSG:4978", "EPSG:2154", [retour[0, 0]], [retour[0, 1]], [retour[0, 2]])
    assert (x[0], y[0], z[0]) == pytest.approx((700153.25, 6500999.75, 331.5), abs=1e-3)


# ---------------------------------------------------------------- état initial complet

def test_instances_egales_aux_arbres_de_trees_init(zone):
    arbres = pq.read_table(zone / "trees_init" / "trees.parquet")
    assert RESUME["arbres"] == arbres.num_rows == 14080
    total = 0
    for fichier in sorted((zone / "tiles" / str(RESUME["annee"])).glob("t_*.gltf")):
        doc, _ = lire_gltf(fichier)
        for noeud in doc["nodes"]:
            attrs = noeud["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
            n = doc["accessors"][attrs["TRANSLATION"]]["count"]
            assert doc["accessors"][attrs["SCALE"]]["count"] == n
            total += n
    assert total == arbres.num_rows


def test_annee_affichee_est_l_annee_de_vol_sans_t0(zone):
    assert RESUME["annee"] == 2021
    assert (zone / "tiles" / "2021" / "tileset.json").is_file()
    assert etat_initial.annee_affichee({"simulate": {"t0": 2026}}, zone)[0] == 2026


def test_un_arbre_connu_tombe_au_bon_endroit(zone):
    """T0001_0307 : x = 700153,25 (est), y = 6500999,75 (nord), h = 25,24 m, crown_area = 15,75 m²."""
    annee = RESUME["annee"]
    tileset = json.loads((zone / "tiles" / str(annee) / "tileset.json").read_text(encoding="utf-8"))
    enfant = next(e for e in tileset["root"]["children"] if e["content"]["uri"] == "t_700000_6500500.gltf")
    doc, binaire = lire_gltf(zone / "tiles" / str(annee) / "t_700000_6500500.gltf")
    ngf = altitude.lire_altitude_ngf(zone / "dtm.tif", np.array([700153.25]), np.array([6500999.75]))[0]
    attendu = repere.lambert_vers_ecef(700153.25, 6500999.75, ngf)[0]  # jeu fictif : ondulation 0
    meilleur = (1e9, None)
    for noeud in doc["nodes"]:
        attrs = noeud["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
        translation = lire_accesseur(doc, binaire, attrs["TRANSLATION"])
        echelle = lire_accesseur(doc, binaire, attrs["SCALE"])
        ecef = repere.local_vers_ecef(enfant["transform"], repere.gltf_vers_local(translation))
        distances = np.linalg.norm(ecef - attendu, axis=1)
        i = int(distances.argmin())
        if distances[i] < meilleur[0]:
            meilleur = (distances[i], (noeud["name"], echelle[i]))
    assert meilleur[0] < 0.01  # à moins d'un centimètre
    nom, echelle = meilleur[1]
    assert nom == "resineux_instances"  # espèce 61 (Abies alba), groupe résineux de species.csv
    assert echelle == pytest.approx([math.sqrt(15.75 / math.pi), 25.24, math.sqrt(15.75 / math.pi)], abs=1e-3)


def test_tuiles_et_volumes_englobants(zone):
    annee = RESUME["annee"]
    tileset = json.loads((zone / "tiles" / str(annee) / "tileset.json").read_text(encoding="utf-8"))
    assert tileset["asset"]["version"] == "1.1"
    assert len(tileset["root"]["children"]) == RESUME["tuiles"] == 4
    ouest, sud, est, nord, bas, haut = tileset["root"]["boundingVolume"]["region"]
    for enfant in tileset["root"]["children"]:
        assert len(enfant["transform"]) == 16
        assert enfant["content"]["uri"].endswith(".gltf")  # pas .glb (référentiel iTowns, point A)
        doc, binaire = lire_gltf(zone / "tiles" / str(annee) / enfant["content"]["uri"])
        boite = enfant["boundingVolume"]["box"]
        centre, demi = np.array(boite[:3]), np.array([boite[3], boite[7], boite[11]])
        for noeud in doc["nodes"]:
            attrs = noeud["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
            enu = repere.gltf_vers_local(lire_accesseur(doc, binaire, attrs["TRANSLATION"]))
            echelle = lire_accesseur(doc, binaire, attrs["SCALE"])
            bas_arbre, haut_arbre = enu, enu + np.column_stack([0 * echelle[:, 0], 0 * echelle[:, 0], echelle[:, 1]])
            assert (np.abs(bas_arbre - centre) <= demi + 1e-3).all() and (np.abs(haut_arbre - centre) <= demi + 1e-3).all()
            # la région de la racine contient la base des arbres
            ecef = repere.local_vers_ecef(enfant["transform"], enu)
            lon, lat, h = warp_transform("EPSG:4978", "EPSG:4326", ecef[:, 0].tolist(), ecef[:, 1].tolist(), ecef[:, 2].tolist())
            assert np.radians(min(lon)) >= ouest and np.radians(max(lon)) <= est
            assert np.radians(min(lat)) >= sud and np.radians(max(lat)) <= nord
            assert min(h) >= bas and max(h) <= haut


def test_contenu_porte_l_extension_et_les_marques_generiques(zone):
    for fichier in sorted((zone / "tiles" / "2021").glob("t_*.gltf")) + sorted((zone / "assets" / "trees").glob("*.gltf")):
        doc, binaire = lire_gltf(fichier)
        assert doc["asset"]["version"] == "2.0"
        assert doc["extras"]["generique"] is True and doc["extras"]["provisoire"] is True
        assert doc["buffers"][0]["byteLength"] == len(binaire) and len(binaire) % 4 == 0
    doc, _ = lire_gltf(zone / "tiles" / "2021" / "t_700000_6500000.gltf")
    assert doc["extensionsUsed"] == ["EXT_mesh_gpu_instancing"]


def test_deux_modeles_generiques(zone):
    assert sorted(p.name for p in (zone / "assets" / "trees").glob("*.gltf")) == ["feuillu.gltf", "resineux.gltf"]
    for groupe in modeles.GROUPES:
        doc, binaire = lire_gltf(zone / "assets" / "trees" / f"{groupe}.gltf")
        positions = doc["meshes"][0]["primitives"][1]["attributes"]["POSITION"]
        maxi = doc["accessors"][positions]["max"]
        assert max(maxi[0], maxi[2]) <= 1.0 + 1e-6 and maxi[1] == pytest.approx(1.0)  # 1 m de haut, 1 m de rayon


def test_fiches_de_cellule(zone):
    annee = RESUME["annee"]
    arbres = pq.read_table(zone / "trees_init" / "trees.parquet").to_pylist()
    fiches = {}
    for fichier in sorted((zone / "web" / "cells").glob("t_*.json")):
        doc = json.loads(fichier.read_text(encoding="utf-8"))
        assert doc["tile"] == fichier.stem and doc["schema_version"] == 1
        for cellule in doc["cells"]:
            fiches[cellule["cell_id"]] = cellule
    assert len(fiches) == RESUME["cellules"]["cellules"] == 1536
    # cellule 6 (ligne 0, colonne 6) : x de 700 150 à 700 175, y de 6 500 975 à 6 501 000
    dedans = [a for a in arbres if 700150 <= a["x"] < 700175 and 6500975 < a["y"] <= 6501000]
    cellule = fiches[6]
    assert (cellule["x"], cellule["y"]) == (700162.5, 6500987.5)
    an = cellule["years"][0]
    assert an["year"] == annee and an["provisoire"] is True
    assert an["volume_m3_ha"] is None and an["carbon_t_ha"] is None
    assert any("volume et carbone non calculés" in n for n in an["notes"])
    assert an["density_trees_ha"] == pytest.approx(len(dedans) / 0.0625)
    assert sum(c["share"] for c in an["composition"]) == pytest.approx(1.0, abs=1e-5)
    assert {c["species"] for c in an["composition"]} == {a["species"] for a in dedans}
    assert cellule["station_type"] != etat_initial and cellule["vegetation_type"].startswith("type_")


def test_cog_avec_apercus_et_memes_valeurs(zone):
    sortie = zone / "web" / "rasters" / "vegetation_map.tif"
    with rasterio.open(sortie) as cog, rasterio.open(zone / "vegetation_map.tif") as source:
        assert cog.overviews(1) and cog.crs.to_epsg() == 2154 and cog.nodata == source.nodata
        assert cog.profile["tiled"] and cog.profile["compress"] == "deflate"
        assert (cog.read(1) == source.read(1)).all() and cog.transform == source.transform


def test_validateur_conforme_sur_toutes_les_sorties(zone):
    assert assets.valider_sorties(zone, RESUME["annee"]) == 0


def test_rejouable_a_l_identique(zone, tmp_path):
    avant = empreintes(zone)
    assert len(avant) == 18  # 4 modèles, 9 fichiers de tuiles, 4 fiches, 1 COG
    assets.produire_etat_initial(CONFIG, zone)
    assert empreintes(zone) == avant


# ---------------------------------------------------------------- erreurs, jamais de valeur devinée

@pytest.fixture
def copie_sans_sorties(tmp_path, zone_chaine):
    dossier = tmp_path / "z"
    shutil.copytree(zone_chaine, dossier, ignore=SORTIES_ASSETS)
    return dossier


def test_sim_present_est_une_erreur_explicite(tmp_path, copie_sans_sorties):
    dossier = copie_sans_sorties
    (dossier / "sim").mkdir()
    with pytest.raises(ErreurModule, match="sim/|sim"):
        assets.produire_etat_initial(CONFIG, dossier)


def test_zone_sans_marqueur_et_sans_raf20_est_une_erreur(tmp_path, copie_sans_sorties):
    dossier = copie_sans_sorties
    (dossier / "zone.yml").unlink()
    assert not assets.zone_fictive(dossier)
    with pytest.raises(ErreurModule, match="raf20_grid"):
        assets.produire_etat_initial({"zone": "massif_reel"}, dossier)


def test_marqueur_false_ne_dispense_pas_de_raf20(tmp_path, copie_sans_sorties):
    dossier = copie_sans_sorties
    (dossier / "zone.yml").write_text("schema_version: 1\nfictive: false\nreason: zone réelle\n", encoding="utf-8")
    with pytest.raises(ErreurModule, match="raf20_grid"):
        assets.produire_etat_initial({"zone": "massif_reel"}, dossier)


def test_copie_de_zone_sous_un_autre_nom_herite_du_marqueur(tmp_path, copie_sans_sorties):
    """Variante copiée (autre nom de zone) : le marqueur fait foi, pas le nom ; l'état initial réussit."""
    dossier = copie_sans_sorties
    assert assets.zone_fictive(dossier)
    resume = assets.produire_etat_initial({"zone": "m4_variante"}, dossier)
    assert resume["arbres"] == 14080
    tileset = json.loads((dossier / "tiles" / str(resume["annee"]) / "tileset.json").read_text(encoding="utf-8"))
    assert tileset["extras"]["raf20"] is None and "fictive" in tileset["extras"]["altitude"]


def test_marqueur_du_depot_est_conforme_au_contrat():
    import subprocess, sys
    r = subprocess.run([sys.executable, "contracts/validate", "zone_marker", str(FICTIF / "zone.yml")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_raf20_ajoute_l_ondulation(tmp_path, copie_sans_sorties):
    dossier = copie_sans_sorties
    grille = tmp_path / "raf20_essai.tif"  # grille géographique d'essai : ondulation constante de 50 m
    with rasterio.open(grille, "w", driver="GTiff", width=40, height=40, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(2.0, 47.0, 0.05, 0.05)) as dst:
        dst.write(np.full((1, 40, 40), 50.0, dtype="float32"))
    arbres = etat_initial.lire_arbres(dossier)
    z0, _ = assets.hauteur_ellipsoidale(CONFIG, dossier, arbres)
    z1, info = assets.hauteur_ellipsoidale({**CONFIG, "external": {"raf20_grid": str(grille)}}, dossier, arbres)
    assert np.allclose(z1 - z0, 50.0) and info["raf20"] == str(grille)


def test_essence_inconnue_est_une_erreur():
    with pytest.raises(ErreurModule, match="99Z"):
        etat_initial.groupe_de_chaque_arbre(np.array(["09", "99Z"], dtype=object), etat_initial.groupes_essences())


def test_nodata_sous_un_arbre_est_une_erreur(tmp_path, copie_sans_sorties):
    dossier = copie_sans_sorties
    with rasterio.open(dossier / "dtm.tif", "r+") as dtm:
        a = dtm.read(1)
        a[:] = dtm.nodata
        dtm.write(a, 1)
    with pytest.raises(ErreurModule, match="nodata"):
        assets.produire_etat_initial(CONFIG, dossier)


def test_decoupage_en_tuiles_aligne_sur_500_m():
    xo, ys = tuiles.coin_tuile(np.array([700153.25, 700500.0, 700999.75]), np.array([6500999.75, 6500000.0, 6500499.99]))
    assert xo.tolist() == [700000, 700500, 700500] and ys.tolist() == [6500500, 6500000, 6500000]
