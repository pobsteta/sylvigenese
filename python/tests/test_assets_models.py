"""Modèles du générateur dans les tuiles et dans massif/ (mission 070), état initial du jeu fictif.

Exemplaires SYNTHÉTIQUES (exemplars_synthetiques.py) pour le hêtre (09), le chêne (02, alias 03) et le sapin (61) ;
les essences 62 et 64 de la zone fictive n'ont PAS d'exemplaire : modèle générique résineux, signalé et compté (Q3).
Le dépôt n'est jamais écrit (copie de la zone dans un dossier temporaire)."""

import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter

import numpy as np
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml

import exemplars_synthetiques as F
from sylvigenese import assets
from sylvigenese.assets_lib import altitude, glb, initial_state, models, stages, tiles
from sylvigenese.common import ModuleError

from test_assets import ASSET_OUTPUTS, CONFIG, ROOT, fingerprints

YEAR = "2021"      # année de vol LiDAR la plus fréquente du jeu fictif, sans simulate.t0 (comme test_assets.py)
KINDS = {"09": "own", "61": "own", "03": "alias", "62": "generic", "64": "generic"}


@pytest.fixture(scope="module")
def exemplars_dir(tmp_path_factory):
    return F.write_set(tmp_path_factory.mktemp("exemplaires"))


def config_with(exemplars_dir):
    config = json.loads(json.dumps(CONFIG))
    config["assets"]["models"]["exemplars_dir"] = str(exemplars_dir)
    return config


@pytest.fixture(scope="module")
def zone_models(tmp_path_factory, zone_chain, exemplars_dir):
    directory = tmp_path_factory.mktemp("zm") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    summary = assets.produce_initial_state(config_with(exemplars_dir), directory)
    return {"dir": directory, "summary": summary, "config": config_with(exemplars_dir)}


@pytest.fixture(scope="module")
def zone_generic(tmp_path_factory, zone_chain):
    directory = tmp_path_factory.mktemp("zg") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    assets.produce_initial_state(CONFIG, directory)
    return directory


def read_tile(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc, path.with_suffix(".bin").read_bytes()


def accessor(doc, binary, index, width):
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    dtype = {5126: "<f4", 5123: "<u2", 5125: "<u4"}[acc["componentType"]]
    return np.frombuffer(binary, dtype=dtype, count=width * acc["count"], offset=view.get("byteOffset", 0)).reshape(-1, width)


def mesh_positions(doc, binary, mesh):
    return np.vstack([accessor(doc, binary, p["attributes"]["POSITION"], 3) for p in doc["meshes"][mesh]["primitives"]])


def test_les_fichiers_glb_un_par_essence_et_stade_sans_alias_et_un_seul_generique(zone_models):
    names = sorted(p.name for p in (zone_models["dir"] / "assets" / "trees").iterdir())
    own = sorted(f"{c}_{s}.glb" for c in ("02", "09", "61") for s in F.STAGES)
    assert names == own + ["generique_resineux.glb"]            # ni 03_*, ni 62_*, ni 64_* ; pas de générique feuillu inutile
    assert zone_models["summary"]["models"] == 13


def test_validateur_sur_toutes_les_sorties(zone_models):
    zone = zone_models["dir"]
    for contract, pattern in (("assets.tree_model", "assets/trees/*.glb"), ("assets.massif_index", "massif/index.json"),
                              ("assets.massif_block", "massif/*/*.json")):
        r = subprocess.run([sys.executable, "contracts/validate", contract, *map(str, sorted(zone.glob(pattern)))],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 0, r.stdout + r.stderr


def test_instances_positions_et_annees_inchangees_par_rapport_aux_modeles_generiques(zone_models, zone_generic):
    """Non-régression de M4 : 14 080 instances, mêmes positions, même index de tuiles, les années ne bougent pas."""
    def translations(directory):
        rows = []
        for file in sorted((directory / "tiles" / YEAR).glob("t_*.gltf")):
            doc, binary = read_tile(file)
            for node in doc["nodes"]:
                rows.append(accessor(doc, binary, node["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]["TRANSLATION"], 3))
        stacked = np.vstack(rows)
        return stacked[np.lexsort(stacked.T)]
    a, b = translations(zone_models["dir"]), translations(zone_generic)
    assert len(a) == len(b) == 14080 and np.array_equal(a, b)
    index_a = json.loads((zone_models["dir"] / "tiles" / "index.json").read_text(encoding="utf-8"))
    index_b = json.loads((zone_generic / "tiles" / "index.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in index_a.items() if k != "notes"} == {k: v for k, v in index_b.items() if k != "notes"}
    differ = [n for n in index_a["notes"] if n not in index_b["notes"]]    # seule la note sur l'origine des modèles change
    assert len(differ) == 1 and "modèles du générateur" in differ[0] and "en générique" in differ[0]
    assert not any("remplacés en M6" in n or "(M6)" in n for n in index_a["notes"] + index_b["notes"])
    assert sorted(p.name for p in (zone_models["dir"] / "tiles").iterdir()) == [YEAR, "index.json"]


def test_les_tuiles_reprennent_les_sommets_du_lod2_du_glb(zone_models):
    """Plan T1 : un seul constructeur de maillage, deux sorties ; les octets des sommets sont identiques."""
    seen = set()
    for file in sorted((zone_models["dir"] / "tiles" / YEAR).glob("t_*.gltf")):
        doc, binary = read_tile(file)
        for node in doc["nodes"]:
            stem = node["name"]
            seen.add(stem)
            g_doc, g_bin = glb.read_container((zone_models["dir"] / "assets" / "trees" / f"{stem}.glb").read_bytes())
            lod2 = g_doc["meshes"][g_doc["nodes"][0]["extensions"]["MSFT_lod"]["ids"][1]]
            for tile_prim, glb_prim in zip(doc["meshes"][node["mesh"]]["primitives"], lod2["primitives"]):
                assert accessor(doc, binary, tile_prim["attributes"]["POSITION"], 3).tobytes() \
                    == accessor(g_doc, g_bin, glb_prim["attributes"]["POSITION"], 3).tobytes(), stem
                assert accessor(doc, binary, tile_prim["indices"], 1).tobytes() \
                    == accessor(g_doc, g_bin, glb_prim["indices"], 1).tobytes(), stem
    assert len(seen) >= 8 and "generique_resineux" in seen and any(s.startswith("09_") for s in seen)
    assert not any(s.startswith("03_") for s in seen)


def test_l_echelle_d_une_instance_est_rayon_sur_r_ref_et_hauteur_sur_h_ref(tmp_path, exemplars_dir):
    reg = models.ModelRegistry.from_config(config_with(exemplars_dir))
    model = reg.model("09_mature")
    trees = {"x": np.array([700100.0, 700200.0]), "y": np.array([6500100.0, 6500300.0]),
             "crown_area": np.array([10.0, 10.0]), "h": np.array([12.0, 30.0])}
    z = np.array([310.0, 312.0])
    tile = tiles.build_tile(700000, 6500000, trees, z, np.array(["09_mature", "generique_resineux"], dtype=object),
                            radius=np.array([3.0, 4.0]))
    path = tiles.write_content(tmp_path, tile, int(YEAR), reg)
    doc, binary = read_tile(path)
    by_name = {n["name"]: accessor(doc, binary, n["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]["SCALE"], 3)
               for n in doc["nodes"]}
    assert by_name["09_mature"][0].tolist() == pytest.approx([3.0 / model.r_ref_m, 12.0 / model.h_ref_m, 3.0 / model.r_ref_m])
    assert by_name["generique_resineux"][0].tolist() == pytest.approx([4.0, 30.0, 4.0])       # (r, h, r) pour un générique
    assert doc["extras"]["modeles"] == ["09_mature", "generique_resineux"] and doc["extras"]["generique"] is True


def test_rejouable_a_l_octet_pres_modeles_tuiles_et_massif(zone_models):
    before = fingerprints(zone_models["dir"])
    assert len(before) == 13 + 9 + 1 + 4 + 1 + 5
    assets.produce_initial_state(zone_models["config"], zone_models["dir"])
    assert fingerprints(zone_models["dir"]) == before


# ------------------------------------------------------------------ massif/
def index_of(zone):
    return json.loads((zone / "massif" / "index.json").read_text(encoding="utf-8"))


def blocks_of(zone, year=int(YEAR)):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((zone / "massif" / str(year)).glob("t_*.json"))}


def test_index_modeles_comptes_et_blocs(zone_models):
    index = index_of(zone_models["dir"])
    assert index["source"] == "trees_init" and index["fictive"] is True and "recruitment" not in index
    assert [(m["species"], m["kind"], m.get("alias_of")) for m in index["models"]] == [
        ("03", "alias", "02"), ("09", "own", None), ("61", "own", None), ("62", "generic", None), ("64", "generic", None)]
    assert {m["species"]: m["model"] for m in index["models"]} == {"03": "02", "09": "09", "61": "61",
                                                                    "62": "generique_resineux", "64": "generique_resineux"}
    trees = pq.read_table(zone_models["dir"] / "trees_init" / "trees.parquet").to_pylist()
    expected = Counter(KINDS[t["species"]] for t in trees)
    year = index["years"][0]
    assert year["year"] == int(YEAR) and year["trees"] == 14080 and year["trees_by_kind"] == dict(expected)
    assert year["trees_by_kind"]["generic"] == 1763 + 2326                       # 62 et 64 : comptés, jamais empruntés
    tile_index = json.loads((zone_models["dir"] / "tiles" / "index.json").read_text(encoding="utf-8"))
    assert [(b["block_id"], b["trees"]) for b in year["blocks"]] == [(t["tile"], t["instances"]) for t in tile_index["years"][0]["tiles"]]
    assert any("générique" in n for n in index["notes"]) and any("non validée écologiquement" in n for n in index["notes"])


def test_blocs_arbres_a_leur_place_avec_quatre_extremites_asymetriques(zone_models):
    zone = zone_models["dir"]
    trees = pq.read_table(zone / "trees_init" / "trees.parquet").to_pydict()
    x, y = np.array(trees["x"]), np.array(trees["y"])
    extremes = {"nord": int(np.argmax(y)), "sud": int(np.argmin(y)), "est": int(np.argmax(x)), "ouest": int(np.argmin(x))}
    assert len({x[i] for i in extremes.values()}) > 1 and len({y[i] for i in extremes.values()}) > 1     # x et y asymétriques
    blocks = blocks_of(zone)
    by_id = {t["tree_id"]: (b, t) for b in blocks.values() for t in b["trees"]}
    z_ngf = altitude.read_ngf_altitude(zone / "dtm.tif", x, y)
    for name, i in extremes.items():
        block, tree = by_id[trees["tree_id"][i]]
        assert block["crs"] == "EPSG:2154" and block["vertical_datum"] == "NGF-IGN69" and block["schema_version"] == 2
        assert block["origin"]["x"] + tree["x"] == pytest.approx(x[i], abs=2e-3), name
        assert block["origin"]["y"] + tree["y"] == pytest.approx(y[i], abs=2e-3), name
        assert block["origin"]["z"] + tree["z"] == pytest.approx(z_ngf[i], abs=2e-3), name       # le pied : altitude.py
        assert 0 <= tree["x"] < 500 and 0 <= tree["y"] < 500 and block["block_id"] == f"t_{int(x[i] // 500 * 500)}_{int(y[i] // 500 * 500)}"
        assert tree["species"] == trees["species"][i] and tree["h"] == pytest.approx(trees["h"][i], abs=1e-3)
    assert sum(len(b["trees"]) for b in blocks.values()) == 14080


def test_stade_de_chaque_arbre_est_h_sur_plafond_de_sa_cellule(zone_models):
    zone = zone_models["dir"]
    with rasterio.open(zone / "site_potential.tif") as src:
        ceiling = src.read(1)
    breaks = stages.load_breaks()
    counts = Counter()
    for block in blocks_of(zone).values():
        for t in block["trees"]:
            gx, gy = block["origin"]["x"] + t["x"], block["origin"]["y"] + t["y"]
            ratio = t["h"] / float(ceiling[int((6_501_000 - gy) // 25), int((gx - 700_000) // 25)])
            if min(abs(ratio - b) for b in breaks) < 2e-3:
                continue                                                          # trop près d'un seuil : arrondi du bloc
            assert t["stage"] == stages.STAGES[sum(ratio >= b for b in breaks)]
            counts[t["stage"]] += 1
    assert sum(counts.values()) > 13000 and len(counts) >= 2


def test_terrain_cellules_et_couverts_du_bloc(zone_models):
    zone = zone_models["dir"]
    block = blocks_of(zone)["t_700000_6500500"]
    ground = block["ground"]
    assert (ground["resolution_m"], ground["nx"], ground["ny"], len(ground["z"])) == (25, 20, 20, 400)
    with rasterio.open(zone / "dtm.tif") as src:
        dtm = src.read(1)
    # nœud (ligne 0 au nord, colonne 0 à l'ouest) = cellule de la grille : le bloc t_700000_6500500 est le nord-ouest
    assert ground["z"][0] == pytest.approx(float(dtm[0, 0]), abs=1e-3)
    assert ground["z"][5 * 20 + 3] == pytest.approx(float(dtm[5, 3]), abs=1e-3)           # ligne 5, colonne 3
    assert block["origin"]["z"] == float(np.floor(min(ground["z"])))
    cells = block["cells"]
    assert len(cells) == 400 and cells[0]["cell_id"] == 0 and (cells[0]["x"], cells[0]["y"]) == (12.5, 487.5)
    last = cells[-1]
    assert last["cell_id"] == 19 * 40 + 19 and (last["x"], last["y"]) == (487.5, 12.5)
    biome = yaml.safe_load((ROOT / "biomes" / f"{cells[0]['biome']}.yml").read_text(encoding="utf-8"))
    assert cells[0]["herb_cover"] == biome["strates"]["herbacee"]["couvert"]
    assert cells[0]["shrub_cover"] == biome["strates"]["arbustive"]["couvert"]
    assert cells[0]["biome_provisoire"] is True and "seedlings" not in cells[0] and block["seedlings_simulated"] is False
    assert any("semis non simulés" in m for m in block["mentions"]) and any("hcb absent" in m for m in block["mentions"])
    assert block["trees"] and all(t["hcb"] is None for t in block["trees"])                     # null, jamais 0
    assert any(f"{len(block['trees'])} arbre(s) sans hauteur de base de houppier" in m for m in block["mentions"])
    assert block["provisoire"] is True and any("non validée écologiquement" in m for m in block["mentions"])


def test_alias_et_generique_dans_les_blocs_sans_emprunt(zone_models):
    blocks = blocks_of(zone_models["dir"])
    for block in blocks.values():
        generic = sum(t["species"] in ("62", "64") for t in block["trees"])
        said = [m for m in block["mentions"] if "par un modèle générique" in m]
        assert len(said) == 1                                                  # dit dans chaque bloc, zéro compris
        assert said[0].startswith(f"{generic} arbre(s)") if generic else said[0].startswith("aucun arbre")
    index = index_of(zone_models["dir"])
    assert {m["species"] for m in index["models"] if m["kind"] == "generic"} == {"62", "64"}      # jamais 09 ou 61


def test_sans_exemplaire_tous_les_arbres_sont_generiques_et_le_disent(zone_generic):
    index = index_of(zone_generic)
    assert {m["kind"] for m in index["models"]} == {"generic"}
    assert index["years"][0]["trees_by_kind"] == {"own": 0, "alias": 0, "generic": 14080}
    assert any("aucun exemplaire" in n for n in index["notes"])
    assert sorted(p.name for p in (zone_generic / "assets" / "trees").iterdir()) == ["generique_feuillu.glb", "generique_resineux.glb"]


def test_exemplaire_corrompu_ou_dossier_absent_refuse_et_ne_publie_rien(tmp_path, zone_chain, exemplars_dir):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    broken = tmp_path / "ex"
    shutil.copytree(exemplars_dir, broken)
    (broken / "Abies_alba_old.parquet").write_bytes(b"PAR1 pas du parquet")
    with pytest.raises(ModuleError, match="Abies_alba_old.parquet refusé"):
        assets.produce_initial_state(config_with(broken), directory)
    with pytest.raises(ModuleError, match="n'est pas un dossier"):
        assets.produce_initial_state(config_with(tmp_path / "absent"), directory)
    assert not (directory / "tiles").exists() and not (directory / "massif").exists() and not (directory / assets.STAGING).exists()


def test_exemplars_dir_relatif_se_lit_depuis_le_dossier_de_config(tmp_path, zone_chain, exemplars_dir):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    config = config_with("exemplaires_relatifs")
    shutil.copytree(exemplars_dir, tmp_path / "exemplaires_relatifs")
    summary = assets.produce_initial_state(config, directory, base_dir=tmp_path)
    assert summary["models"] == 13


def test_config_sans_bloc_models_lit_le_depot_et_le_dit_sans_exemplaire(tmp_path, zone_chain, capsys):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    summary = assets.produce_initial_state({"zone": "zone_fictive", "crs": "EPSG:2154"}, directory)
    assert "assets.models absent de config.yml" in capsys.readouterr().err
    assert summary["models"] == 2 and summary["massif"]["generic"] == 14080          # génériques seulement


def test_stade_indetermine_est_une_erreur_et_rien_n_est_publie(tmp_path, zone_chain):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    with rasterio.open(directory / "site_potential.tif", "r+") as src:
        array = src.read(1)
        array[:] = src.nodata
        src.write(array, 1)
    with pytest.raises(ModuleError, match="stade indéterminé"):
        assets.produce_initial_state(CONFIG, directory)
    assert not (directory / "massif").exists()


def test_tuile_generique_vrai_seulement_si_un_modele_generique_sert(tmp_path, exemplars_dir):
    reg = models.ModelRegistry.from_config(config_with(exemplars_dir))
    trees = {"x": np.array([700100.0, 700200.0]), "y": np.array([6500100.0, 6500300.0]),
             "crown_area": np.array([10.0, 10.0]), "h": np.array([12.0, 30.0])}
    z = np.array([310.0, 312.0])
    for names, expected in ((["09_mature", "09_mature"], False), (["09_mature", "generique_resineux"], True)):
        directory = tmp_path / str(expected)
        directory.mkdir()
        tile = tiles.build_tile(700000, 6500000, trees, z, np.array(names, dtype=object), radius=np.array([3.0, 4.0]))
        doc, _ = read_tile(tiles.write_content(directory, tile, int(YEAR), reg))
        assert doc["extras"]["generique"] is expected and doc["extras"]["modeles"] == sorted(set(names))


def test_note_de_l_index_dit_les_modeles_du_generateur_et_le_nombre_de_generiques(zone_models, zone_generic):
    notes = json.loads((zone_models["dir"] / "tiles" / "index.json").read_text(encoding="utf-8"))["notes"]
    generic = json.loads((zone_models["dir"] / "massif" / "index.json").read_text(encoding="utf-8"))["years"][0]["trees_by_kind"]["generic"]
    said = [n for n in notes if n.startswith("modèles du générateur")]
    assert len(said) == 1 and f"{generic} arbre(s) dessiné(s) en générique" in said[0] and "3 essence(s)" in said[0]
    assert not any("remplacés en M6" in n for n in notes)
    notes = json.loads((zone_generic / "tiles" / "index.json").read_text(encoding="utf-8"))["notes"]
    said = [n for n in notes if n.startswith("aucun exemplaire")]
    assert len(said) == 1 and "14080 arbre(s) dessiné(s) en générique" in said[0]


# ------------------------------------------------------------------ un stade sans exemplaire (mission 075)
@pytest.fixture(scope="module")
def zone_partial(tmp_path_factory, zone_chain):
    """Hêtre (09) avec des exemplaires aux stades mature et old SEULEMENT : ses stades young et pole n'ont pas d'exemplaire
    (cas réel : Picea abies, stade mature, 1 arbre en 2022). Chêne et sapin : les quatre stades."""
    exemplars = F.write_set(tmp_path_factory.mktemp("exemplaires_partiels"), essences=("Quercus_spec", "Abies_alba"))
    for stage in ("mature", "old"):
        F.write(exemplars, "Fagus_sylvatica", stage, seed=11)
    directory = tmp_path_factory.mktemp("zp") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=ASSET_OUTPUTS)
    assets.produce_initial_state(config_with(exemplars), directory)
    return directory


def test_l_index_dit_le_fichier_de_chaque_essence_et_stade_generique_compris(zone_partial):
    index = index_of(zone_partial)
    by_pair = {(m["species"], m["stage"]): m for m in index["stage_models"]}
    pairs = {(t["species"], t["stage"]) for b in blocks_of(zone_partial).values() for t in b["trees"]}
    assert set(by_pair) == pairs and len(by_pair) == len(index["stage_models"])          # un couple une fois, aucun en trop
    beech = {stage: m for (sp, stage), m in by_pair.items() if sp == "09"}
    assert {"young", "pole"} & set(beech), "le jeu fictif doit avoir des hêtres jeunes pour exercer le repli"
    for stage, m in beech.items():
        if stage in ("mature", "old"):
            assert (m["kind"], m["file"]) == ("own", f"09_{stage}.glb")
        else:
            assert (m["kind"], m["file"]) == ("generic", "generique_feuillu.glb"), stage       # jamais 09_<stade> absent
    assert all(m["file"] == "generique_resineux.glb" for (sp, _), m in by_pair.items() if sp in ("62", "64"))
    # `models` dit l'essence (own dès qu'un stade a un exemplaire) : le fichier est celui de stage_models
    assert {m["species"]: m["kind"] for m in index["models"]}["09"] == "own"


def test_chaque_fichier_dit_existe_et_les_comptes_de_generiques_sont_justes(zone_partial):
    index = index_of(zone_partial)
    trees_dir = zone_partial / "assets" / "trees"
    for m in index["stage_models"]:
        assert (trees_dir / m["file"]).is_file(), m
        if m["kind"] == "alias":
            assert m["file"] == f"{m['alias_of']}_{m['stage']}.glb"
    kind_of = {(m["species"], m["stage"]): m["kind"] for m in index["stage_models"]}
    counts = Counter(kind_of[(t["species"], t["stage"])] for b in blocks_of(zone_partial).values() for t in b["trees"])
    year = index["years"][0]
    assert year["trees_by_kind"] == {k: counts.get(k, 0) for k in ("own", "alias", "generic")}
    beech_generic = sum(1 for b in blocks_of(zone_partial).values() for t in b["trees"]
                        if t["species"] == "09" and t["stage"] in ("young", "pole"))
    assert beech_generic > 0 and year["trees_by_kind"]["generic"] == beech_generic + 1763 + 2326       # hêtres jeunes + 62 et 64
    assert any(n.startswith("essence 09 : stade(s) sans exemplaire, modèle générique") for n in index["notes"])
    assert "generique_feuillu.glb" in {p.name for p in trees_dir.iterdir()}


def test_stage_models_est_conforme_au_contrat(zone_partial):
    import jsonschema
    schema = json.loads((ROOT / "contracts" / "json" / "massif_index.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(index_of(zone_partial), schema)


def _glb_json(path):
    import struct
    data = path.read_bytes()
    return json.loads(data[20:20 + struct.unpack_from("<I", data, 12)[0]])


def test_chaque_niveau_de_chaque_glb_porte_ecorce_puis_feuillage_exemplaires_et_generiques(zone_models, zone_generic):
    """Mission 084c, contrat assets.tree_model : deux primitives par niveau, matériaux `<fichier>_ecorce` puis
    `<fichier>_feuillage`, y compris pour les génériques (qui s'appelaient « tronc » et « houppier » : la vue ne lisait pas
    leur rôle)."""
    fichiers = sorted((zone_models["dir"] / "assets" / "trees").glob("*.glb")) + \
        sorted((zone_generic / "assets" / "trees").glob("*.glb"))
    assert len(fichiers) >= 5 and any(f.name.startswith("generique_") for f in fichiers)
    for fichier in fichiers:
        doc = _glb_json(fichier)
        assert [m["name"] for m in doc["materials"]] == [f"{fichier.stem}_ecorce", f"{fichier.stem}_feuillage"], fichier.name
        for mesh in doc["meshes"]:
            assert [doc["materials"][p["material"]]["name"].rsplit("_", 1)[1] for p in mesh["primitives"]] == \
                ["ecorce", "feuillage"], fichier.name
