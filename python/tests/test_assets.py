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
from sylvigenese.assets_lib import altitude, initial_state, models, frame, tiles
from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[2]
FICTITIOUS_ZONE = ROOT / "tests" / "fixtures" / "zone_fictive"
CONFIG = {"zone": "zone_fictive", "crs": "EPSG:2154"}
SUMMARY: dict = {}  # résumé rendu par produce_initial_state (rempli par la fixture `zone`)


@pytest.fixture(autouse=True)
def from_root(monkeypatch):
    monkeypatch.chdir(ROOT)


ASSET_OUTPUTS = shutil.ignore_patterns("tiles", "web", "assets", "sim")


@pytest.fixture(scope="module")
def zone(tmp_path_factory, zone_chain):
    """Copie du jeu fictif passé par prepare, biomes et trees (conftest), + état initial produit."""
    directory = tmp_path_factory.mktemp("zone") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    SUMMARY.update(assets.produce_initial_state(CONFIG, directory))
    return directory


def fingerprints(directory: Path) -> dict:
    outputs = [p for subset in ("assets", "tiles", "web") for p in sorted((directory / subset).rglob("*")) if p.is_file()]
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}


def read_gltf(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    binary = path.with_suffix(".bin").read_bytes()
    return doc, binary


def read_accessor(doc, binary, index):
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    assert acc["componentType"] == 5126 and acc["type"] == "VEC3"
    start = view["byteOffset"] + acc.get("byteOffset", 0)
    return np.frombuffer(binary, dtype="<f4", count=acc["count"] * 3, offset=start).reshape(-1, 3)


# ---------------------------------------------------------------- repère (point connu)

def test_origine_du_lambert93_est_a_3_est_46_5_nord():
    lon_lat = frame.lambert_to_lonlat(700000.0, 6600000.0)[0]
    assert lon_lat[0] == pytest.approx(3.0, abs=1e-9)
    assert lon_lat[1] == pytest.approx(46.5, abs=1e-9)


def test_ecef_de_l_origine_du_lambert93_contre_la_formule_wgs84():
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    lon, lat = math.radians(3.0), math.radians(46.5)
    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    expected = [n * math.cos(lat) * math.cos(lon), n * math.cos(lat) * math.sin(lon), n * (1 - e2) * math.sin(lat)]
    obtained = frame.lambert_to_ecef(700000.0, 6600000.0, 0.0)[0]
    assert np.abs(obtained - expected).max() < 1.0  # RGF93 et WGS84 : moins d'un mètre


def test_repere_local_x_est_y_nord_haut():
    r = frame.LocalFrame(700000.0, 6600000.0, 100.0)
    origin = r.lambert_to_local(700000.0, 6600000.0, 100.0)[0]
    assert np.abs(origin).max() < 1e-6
    east = r.lambert_to_local(701000.0, 6600000.0, 100.0)[0]
    north = r.lambert_to_local(700000.0, 6601000.0, 100.0)[0]
    up = r.lambert_to_local(700000.0, 6600000.0, 150.0)[0]
    assert east[0] == pytest.approx(1000.0, abs=2.0) and abs(east[1]) < 1e-3  # x Lambert -> est
    assert north[1] == pytest.approx(1000.0, abs=2.0) and abs(north[0]) < 1e-3  # y Lambert -> nord
    assert up[2] == pytest.approx(50.0, abs=1e-6) and abs(up[0]) < 1e-6 and abs(up[1]) < 1e-6


def test_aller_retour_glTF_local_ecef_lambert():
    r = frame.LocalFrame(700250.0, 6500750.0, 340.0)
    ecef = frame.lambert_to_ecef(700153.25, 6500999.75, 331.5)
    enu = r.ecef_to_local(ecef)
    gltf = frame.local_to_gltf(enu)
    assert gltf[0, 0] == pytest.approx(enu[0, 0]) and gltf[0, 1] == pytest.approx(enu[0, 2])
    assert gltf[0, 2] == pytest.approx(-enu[0, 1])
    round_trip = frame.local_to_ecef(r.transform_3dtiles(), frame.gltf_to_local(gltf))
    assert np.abs(round_trip - ecef).max() < 1e-6
    x, y, z = warp_transform("EPSG:4978", "EPSG:2154", [round_trip[0, 0]], [round_trip[0, 1]], [round_trip[0, 2]])
    assert (x[0], y[0], z[0]) == pytest.approx((700153.25, 6500999.75, 331.5), abs=1e-3)


# ---------------------------------------------------------------- état initial complet

def test_instances_egales_aux_arbres_de_trees_init(zone):
    trees = pq.read_table(zone / "trees_init" / "trees.parquet")
    assert SUMMARY["trees"] == trees.num_rows == 14080
    total = 0
    for file in sorted((zone / "tiles" / str(SUMMARY["year"])).glob("t_*.gltf")):
        doc, _ = read_gltf(file)
        for node in doc["nodes"]:
            attrs = node["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
            n = doc["accessors"][attrs["TRANSLATION"]]["count"]
            assert doc["accessors"][attrs["SCALE"]]["count"] == n
            total += n
    assert total == trees.num_rows


def test_annee_affichee_est_l_annee_de_vol_sans_t0(zone):
    assert SUMMARY["year"] == 2021
    assert (zone / "tiles" / "2021" / "tileset.json").is_file()
    assert initial_state.displayed_year({"simulate": {"t0": 2026}}, zone)[0] == 2026


def test_un_arbre_connu_tombe_au_bon_endroit(zone):
    """T0001_0307 : x = 700153,25 (est), y = 6500999,75 (nord), h = 25,24 m, crown_area = 15,75 m²."""
    year = SUMMARY["year"]
    tileset = json.loads((zone / "tiles" / str(year) / "tileset.json").read_text(encoding="utf-8"))
    child = next(e for e in tileset["root"]["children"] if e["content"]["uri"] == "t_700000_6500500.gltf")
    doc, binary = read_gltf(zone / "tiles" / str(year) / "t_700000_6500500.gltf")
    ngf = altitude.read_ngf_altitude(zone / "dtm.tif", np.array([700153.25]), np.array([6500999.75]))[0]
    expected = frame.lambert_to_ecef(700153.25, 6500999.75, ngf)[0]  # jeu fictif : ondulation 0
    best = (1e9, None)
    for node in doc["nodes"]:
        attrs = node["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
        translation = read_accessor(doc, binary, attrs["TRANSLATION"])
        scale = read_accessor(doc, binary, attrs["SCALE"])
        ecef = frame.local_to_ecef(child["transform"], frame.gltf_to_local(translation))
        distances = np.linalg.norm(ecef - expected, axis=1)
        i = int(distances.argmin())
        if distances[i] < best[0]:
            best = (distances[i], (node["name"], scale[i]))
    assert best[0] < 0.01  # à moins d'un centimètre
    name, scale = best[1]
    assert name == "resineux_instances"  # espèce 61 (Abies alba), groupe résineux de species.csv
    assert scale == pytest.approx([math.sqrt(15.75 / math.pi), 25.24, math.sqrt(15.75 / math.pi)], abs=1e-3)


def test_tuiles_et_volumes_englobants(zone):
    year = SUMMARY["year"]
    tileset = json.loads((zone / "tiles" / str(year) / "tileset.json").read_text(encoding="utf-8"))
    assert tileset["asset"]["version"] == "1.1"
    assert len(tileset["root"]["children"]) == SUMMARY["tiles"] == 4
    west, south, east, north, hmin, hmax = tileset["root"]["boundingVolume"]["region"]
    for child in tileset["root"]["children"]:
        assert len(child["transform"]) == 16
        assert child["content"]["uri"].endswith(".gltf")  # pas .glb (référentiel iTowns, point A)
        doc, binary = read_gltf(zone / "tiles" / str(year) / child["content"]["uri"])
        box = child["boundingVolume"]["box"]
        center, half = np.array(box[:3]), np.array([box[3], box[7], box[11]])
        for node in doc["nodes"]:
            attrs = node["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
            enu = frame.gltf_to_local(read_accessor(doc, binary, attrs["TRANSLATION"]))
            scale = read_accessor(doc, binary, attrs["SCALE"])
            tree_base, tree_top = enu, enu + np.column_stack([0 * scale[:, 0], 0 * scale[:, 0], scale[:, 1]])
            assert (np.abs(tree_base - center) <= half + 1e-3).all() and (np.abs(tree_top - center) <= half + 1e-3).all()
            # la région de la racine contient la base des arbres
            ecef = frame.local_to_ecef(child["transform"], enu)
            lon, lat, h = warp_transform("EPSG:4978", "EPSG:4326", ecef[:, 0].tolist(), ecef[:, 1].tolist(), ecef[:, 2].tolist())
            assert np.radians(min(lon)) >= west and np.radians(max(lon)) <= east
            assert np.radians(min(lat)) >= south and np.radians(max(lat)) <= north
            assert min(h) >= hmin and max(h) <= hmax


def test_contenu_porte_l_extension_et_les_marques_generiques(zone):
    for file in sorted((zone / "tiles" / "2021").glob("t_*.gltf")) + sorted((zone / "assets" / "trees").glob("*.gltf")):
        doc, binary = read_gltf(file)
        assert doc["asset"]["version"] == "2.0"
        assert doc["extras"]["generique"] is True and doc["extras"]["provisoire"] is True
        assert doc["buffers"][0]["byteLength"] == len(binary) and len(binary) % 4 == 0
    doc, _ = read_gltf(zone / "tiles" / "2021" / "t_700000_6500000.gltf")
    assert doc["extensionsUsed"] == ["EXT_mesh_gpu_instancing"]


def test_deux_modeles_generiques(zone):
    assert sorted(p.name for p in (zone / "assets" / "trees").glob("*.gltf")) == ["feuillu.gltf", "resineux.gltf"]
    for group in models.GROUPS:
        doc, binary = read_gltf(zone / "assets" / "trees" / f"{group}.gltf")
        positions = doc["meshes"][0]["primitives"][1]["attributes"]["POSITION"]
        max_corner = doc["accessors"][positions]["max"]
        assert max(max_corner[0], max_corner[2]) <= 1.0 + 1e-6 and max_corner[1] == pytest.approx(1.0)  # 1 m de haut, 1 m de rayon


def test_fiches_de_cellule(zone):
    year = SUMMARY["year"]
    trees = pq.read_table(zone / "trees_init" / "trees.parquet").to_pylist()
    cell_sheets = {}
    for file in sorted((zone / "web" / "cells").glob("t_*.json")):
        doc = json.loads(file.read_text(encoding="utf-8"))
        assert doc["tile"] == file.stem and doc["schema_version"] == 1
        for cell in doc["cells"]:
            cell_sheets[cell["cell_id"]] = cell
    assert len(cell_sheets) == SUMMARY["cells"]["cells"] == 1536
    # cellule 6 (ligne 0, colonne 6) : x de 700 150 à 700 175, y de 6 500 975 à 6 501 000
    inside = [a for a in trees if 700150 <= a["x"] < 700175 and 6500975 < a["y"] <= 6501000]
    cell = cell_sheets[6]
    assert (cell["x"], cell["y"]) == (700162.5, 6500987.5)
    year_entry = cell["years"][0]
    assert year_entry["year"] == year and year_entry["provisoire"] is True
    assert year_entry["volume_m3_ha"] is None and year_entry["carbon_t_ha"] is None
    assert any("volume et carbone non calculés" in n for n in year_entry["notes"])
    assert year_entry["density_trees_ha"] == pytest.approx(len(inside) / 0.0625)
    assert sum(c["share"] for c in year_entry["composition"]) == pytest.approx(1.0, abs=1e-5)
    assert {c["species"] for c in year_entry["composition"]} == {a["species"] for a in inside}
    assert cell["station_type"] != initial_state and cell["vegetation_type"].startswith("type_")


def test_cog_avec_apercus_et_memes_valeurs(zone):
    output = zone / "web" / "rasters" / "vegetation_map.tif"
    with rasterio.open(output) as cog, rasterio.open(zone / "vegetation_map.tif") as source:
        assert cog.overviews(1) and cog.crs.to_epsg() == 2154 and cog.nodata == source.nodata
        assert cog.profile["tiled"] and cog.profile["compress"] == "deflate"
        assert (cog.read(1) == source.read(1)).all() and cog.transform == source.transform


def test_validateur_conforme_sur_toutes_les_sorties(zone):
    assert assets.validate_outputs(zone, SUMMARY["year"]) == 0


def test_rejouable_a_l_identique(zone, tmp_path):
    before = fingerprints(zone)
    assert len(before) == 19  # 4 modèles, 9 fichiers de tuiles, tiles/index.json (mission 047), 4 fiches, 1 COG
    assets.produce_initial_state(CONFIG, zone)
    assert fingerprints(zone) == before


# ---------------------------------------------------------------- erreurs, jamais de valeur devinée

@pytest.fixture
def copy_without_outputs(tmp_path, zone_chain):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    return directory


def test_sim_present_est_une_erreur_explicite(tmp_path, copy_without_outputs):
    directory = copy_without_outputs
    (directory / "sim").mkdir()
    with pytest.raises(ModuleError, match="sim/|sim"):
        assets.produce_initial_state(CONFIG, directory)


def test_zone_sans_marqueur_et_sans_raf20_est_une_erreur(tmp_path, copy_without_outputs):
    directory = copy_without_outputs
    (directory / "zone.yml").unlink()
    assert not assets.is_fictitious_zone(directory)
    with pytest.raises(ModuleError, match="raf20_grid"):
        assets.produce_initial_state({"zone": "massif_reel"}, directory)


def test_marqueur_false_ne_dispense_pas_de_raf20(tmp_path, copy_without_outputs):
    directory = copy_without_outputs
    (directory / "zone.yml").write_text("schema_version: 1\nfictive: false\nreason: zone réelle\n", encoding="utf-8")
    with pytest.raises(ModuleError, match="raf20_grid"):
        assets.produce_initial_state({"zone": "massif_reel"}, directory)


def test_copie_de_zone_sous_un_autre_nom_herite_du_marqueur(tmp_path, copy_without_outputs):
    """Variante copiée (autre nom de zone) : le marqueur fait foi, pas le nom ; l'état initial réussit."""
    directory = copy_without_outputs
    assert assets.is_fictitious_zone(directory)
    summary = assets.produce_initial_state({"zone": "m4_variante"}, directory)
    assert summary["trees"] == 14080
    tileset = json.loads((directory / "tiles" / str(summary["year"]) / "tileset.json").read_text(encoding="utf-8"))
    assert tileset["extras"]["raf20"] is None and "fictive" in tileset["extras"]["altitude"]


def test_marqueur_du_depot_est_conforme_au_contrat():
    import subprocess, sys
    r = subprocess.run([sys.executable, "contracts/validate", "zone_marker", str(FICTITIOUS_ZONE / "zone.yml")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_raf20_ajoute_l_ondulation(tmp_path, copy_without_outputs):
    directory = copy_without_outputs
    grid = tmp_path / "raf20_essai.tif"  # grille géographique d'essai : ondulation constante de 50 m
    with rasterio.open(grid, "w", driver="GTiff", width=40, height=40, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(2.0, 47.0, 0.05, 0.05)) as dst:
        dst.write(np.full((1, 40, 40), 50.0, dtype="float32"))
    trees = initial_state.read_trees(directory)
    z0, _ = assets.ellipsoidal_height(CONFIG, directory, trees)
    z1, info = assets.ellipsoidal_height({**CONFIG, "external": {"raf20_grid": str(grid)}}, directory, trees)
    assert np.allclose(z1 - z0, 50.0) and info["raf20"] == str(grid)


def test_essence_inconnue_est_une_erreur():
    with pytest.raises(ModuleError, match="99Z"):
        initial_state.group_of_each_tree(np.array(["09", "99Z"], dtype=object), initial_state.species_groups())


def test_nodata_sous_un_arbre_est_une_erreur(tmp_path, copy_without_outputs):
    directory = copy_without_outputs
    with rasterio.open(directory / "dtm.tif", "r+") as dtm:
        a = dtm.read(1)
        a[:] = dtm.nodata
        dtm.write(a, 1)
    with pytest.raises(ModuleError, match="nodata"):
        assets.produce_initial_state(CONFIG, directory)


def test_decoupage_en_tuiles_aligne_sur_500_m():
    tile_x, tile_y = tiles.tile_corner(np.array([700153.25, 700500.0, 700999.75]), np.array([6500999.75, 6500000.0, 6500499.99]))
    assert tile_x.tolist() == [700000, 700500, 700500] and tile_y.tolist() == [6500500, 6500000, 6500000]


def test_index_de_l_etat_initial(zone):
    """Mission 047 : sans sim/, tiles/index.json en mode trees_init, une seule année (contrat tiles_index)."""
    index = json.loads((zone / "tiles" / "index.json").read_text(encoding="utf-8"))
    assert index["source"] == "trees_init" and index["t0"] == SUMMARY["year"]
    assert [(e["year"], e["instances"], e["tileset"]) for e in index["years"]] == \
        [(SUMMARY["year"], 14080, f"{SUMMARY['year']}/tileset.json")]
    assert sum(t["instances"] for t in index["years"][0]["tiles"]) == 14080


def test_etat_initial_efface_les_annees_perimees(tmp_path, copy_without_outputs):
    """Écriture atomique (mission 047) : une année et une carte g_ d'un ancien run disparaissent."""
    directory = copy_without_outputs
    (directory / "tiles" / "1999").mkdir(parents=True)
    (directory / "web" / "rasters").mkdir(parents=True)
    (directory / "web" / "rasters" / "g_1999.tif").write_bytes(b"")
    summary = assets.produce_initial_state(CONFIG, directory)
    assert sorted(p.name for p in (directory / "tiles").iterdir()) == [str(summary["year"]), "index.json"]
    assert sorted(p.name for p in (directory / "web" / "rasters").iterdir()) == ["vegetation_map.tif"]
    assert not (directory / assets.STAGING).exists()
