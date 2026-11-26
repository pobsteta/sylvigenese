"""Tests de `assets` quand `sim/` existe (mission 047, plan m4a-suite-temps T1 à T10).

Le jeu fictif (chaîne prepare, biomes, trees du conftest) est copié dans un dossier temporaire, et un
petit `sim/` SYNTHÉTIQUE y est écrit par le test : 2022 = les arbres de trees_init (cw = diamètre du
disque de crown_area), 2023 = les mêmes, trois morts, et une recrue au point connu (est 700 012,5 ;
nord 6 500 987,5, EPSG:2154), qui doit tomber dans la tuile t_700000_6500500 et la cellule 0 (coin
nord-ouest de grid.tif). Ces valeurs n'ont aucun sens écologique : elles servent à vérifier les comptes.
Le dépôt n'est jamais écrit.
"""

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import yaml
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
from rasterio.warp import transform as warp_transform

from sylvigenese import assets
from sylvigenese.assets_lib import altitude, cell_sheets, frame, sim_state, tiles
from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[2]
KNOWN_POINT = (700_012.5, 6_500_987.5)      # (est, nord), EPSG:2154
CELL_HA = 0.0625
DEAD = ("T0001_0634", "T0001_0663", "T0001_0694")
REPO_CONFIG = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
CONFIG = {"zone": "zone_fictive", "crs": "EPSG:2154",
          "simulate": {"level": "massif", "seed": 42, "t0": 2022, "years": 1},
          "assets": {"year_step": 1, "models": REPO_CONFIG["assets"]["models"]}, "viewer": REPO_CONFIG["viewer"]}


@pytest.fixture(autouse=True)
def from_root(monkeypatch):
    monkeypatch.chdir(ROOT)


def cell_of(x, y):
    """cell_id de grid.tif (40 x 40, coin nord-ouest 700 000 ; 6 501 000, maille 25 m)."""
    return int(np.floor((6_501_000 - y) / 25) * 40 + np.floor((x - 700_000) / 25))


def write_sim(zone: Path) -> dict:
    """Écrit un sim/ synthétique de deux années ; rend les états par année."""
    init = pq.read_table(zone / "trees_init" / "trees.parquet").to_pydict()
    n = len(init["tree_id"])
    base = {"tree_id": list(init["tree_id"]), "species": list(init["species"]), "x": list(init["x"]),
            "y": list(init["y"]), "d130": list(init["d130"]), "h": list(init["h"]),
            "hcb": [0.3 * h for h in init["h"]], "cw": [2 * math.sqrt(a / math.pi) for a in init["crown_area"]],
            "status": ["alive"] * n}
    later = {k: list(v) for k, v in base.items()}
    later["h"] = [h + 0.5 for h in later["h"]]
    for tid in DEAD:
        later["status"][later["tree_id"].index(tid)] = "dead"
    for k, v in {"tree_id": "r2023_000001", "species": "09", "x": KNOWN_POINT[0], "y": KNOWN_POINT[1],
                 "d130": 8.0, "h": 6.0, "hcb": 2.0, "cw": 3.0, "status": "alive"}.items():
        later[k].append(v)
    states = {2022: base, 2023: later}
    sim = zone / "sim"
    for year, st in states.items():
        (sim / "trees" / f"year={year}").mkdir(parents=True)
        pq.write_table(pa.table(st), sim / "trees" / f"year={year}" / "part-00000.parquet")
        acc: dict = {}
        hdom: dict = {}
        for tid, sp, x, y, d, h, s in zip(st["tree_id"], st["species"], st["x"], st["y"], st["d130"], st["h"], st["status"]):
            if s != "alive":
                continue
            c = cell_of(x, y)
            e = acc.setdefault((c, sp), [0, 0.0, 0.0])
            e[0] += 1
            e[1] += math.pi * (d / 200) ** 2
            e[2] += d
            hdom[c] = max(hdom.get(c, 0.0), h)
        keys = sorted(acc)
        (sim / "cells" / f"year={year}").mkdir(parents=True)
        pq.write_table(pa.table({
            "cell_id": pa.array([c for c, _ in keys], pa.int64()), "species": [s for _, s in keys],
            "stems_ha": [acc[k][0] / CELL_HA for k in keys], "basal_area_m2_ha": [acc[k][1] / CELL_HA for k in keys],
            "d130_mean": [acc[k][2] / acc[k][0] for k in keys], "h_dom_m": [hdom[c] for c, _ in keys]}),
            sim / "cells" / f"year={year}" / "part-00000.parquet")
    pq.write_table(pa.table({"year": pa.array([2023, 2023], pa.int64()), "entity": ["0", "zone_fictive"],
                             "kind": ["hdom_au_dessus_du_plafond", "total_recrues_cellule_vide"],
                             "message": ["H_dom au-dessus du plafond", "total"], "value": [31.5, 1.0]}),
                   sim / "flags.parquet")
    run = {"schema_version": 1, "level": "massif", "seed": 42, "t0": 2022, "years": 1, "threads": 1,
           "memory_estimate_bytes": 0, "duration_s": 0.0, "config_sha256": "0" * 64, "zeroed_values": 0,
           "provisional_share": 1.0, "domain_outputs": {"d130": {"below": 0, "above": 0}},
           "cells_at_height_ceiling": 0, "edge_disks": 0, "mixed_cells": 0, "recruits": 1, "deaths": len(DEAD)}
    (sim / "run.json").write_text(json.dumps(run), encoding="utf-8")
    return states


def produce(zone: Path, config=CONFIG) -> dict:
    """Comme `assets.run`, sans relire config.yml : écriture, contrôle, publication."""
    with assets.Staging(zone) as staging:
        summary = assets.write_sim_state(config, zone, staging.root)
        assert assets.validate_outputs(staging.root, summary["years"], zone / "grid.tif") == 0
        staging.publish()
    return summary


def fingerprints(zone: Path) -> dict:
    return {str(p.relative_to(zone)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("assets", "tiles", "web", "massif") for p in sorted((zone / d).rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def sim_zone(tmp_path_factory, zone_chain):
    directory = tmp_path_factory.mktemp("sim") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim", "massif"))
    states = write_sim(directory)
    # une année périmée plantée : elle doit disparaître (écriture atomique, plan T6)
    (directory / "tiles" / "2021").mkdir(parents=True)
    (directory / "tiles" / "2021" / "tileset.json").write_text("{}", encoding="utf-8")
    summary = produce(directory)
    return {"dir": directory, "states": states, "summary": summary}


@pytest.fixture
def fresh(tmp_path, zone_chain):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim", "massif"))
    write_sim(directory)
    return directory


def read_instances(zone: Path, year: int) -> dict:
    """Instances d'une année en EPSG:2154 : tuile, (x, y), échelle, nom du nœud."""
    ts = json.loads((zone / "tiles" / str(year) / "tileset.json").read_text(encoding="utf-8"))
    out = {"tile": [], "xy": [], "scale": [], "node": []}
    for child in ts["root"]["children"]:
        path = zone / "tiles" / str(year) / child["content"]["uri"]
        doc = json.loads(path.read_text(encoding="utf-8"))
        binary = path.with_suffix(".bin").read_bytes()
        for node in doc["nodes"]:
            attrs = node["extensions"]["EXT_mesh_gpu_instancing"]["attributes"]
            arrays = []
            for key in ("TRANSLATION", "SCALE"):
                acc = doc["accessors"][attrs[key]]
                view = doc["bufferViews"][acc["bufferView"]]
                arrays.append(np.frombuffer(binary, "<f4", acc["count"] * 3, view["byteOffset"]).reshape(-1, 3))
            ecef = frame.local_to_ecef(child["transform"], frame.gltf_to_local(arrays[0]))
            x, y, _ = warp_transform("EPSG:4978", "EPSG:2154", *(ecef[:, i].tolist() for i in range(3)))
            out["xy"].append(np.column_stack([x, y]))
            out["scale"].append(arrays[1])
            out["tile"] += [Path(child["content"]["uri"]).stem] * len(x)
            out["node"] += [node["name"]] * len(x)
    return {"tile": np.array(out["tile"]), "xy": np.vstack(out["xy"]), "scale": np.vstack(out["scale"]),
            "node": np.array(out["node"])}


# ---------------------------------------------------------------- années retenues (T1)

def test_annees_retenues_t0_puis_une_sur_n_puis_la_derniere():
    assert sim_state.retained_years(2022, 15, 10) == [2022, 2032, 2037]
    assert sim_state.retained_years(2022, 100, 10) == list(range(2022, 2123, 10))
    assert sim_state.retained_years(2022, 15, 5) == [2022, 2027, 2032, 2037]
    assert sim_state.retained_years(2022, 1, 10) == [2022, 2023]
    assert sim_state.retained_years(2022, 0, 1) == [2022]


@pytest.mark.parametrize("config", [{}, {"assets": None}, {"assets": {}}, {"assets": {"year_step": 0}},
                                    {"assets": {"year_step": True}}, {"assets": {"year_step": "10"}}])
def test_year_step_absent_ou_faux_est_refuse(config):
    with pytest.raises(ModuleError, match="year_step"):
        sim_state.year_step(config)


# ---------------------------------------------------------------- fiche v2 : une année

def test_annee_sans_ligne_est_une_cellule_sans_arbre_vivant():
    e = cell_sheets.year_entry_v2([], 2032, 7)
    assert (e["stems_ha"], e["basal_area_m2_ha"], e["d130_mean_cm"], e["h_dom_m"], e["composition"]) == (0.0, 0.0, None, None, [])
    assert e["volume_m3_ha"] is None and e["carbon_t_ha"] is None and e["provisoire"] is True


def test_annee_recalcule_sim_cells_sans_arrondi():
    rows = [{"species": "61", "stems_ha": 48.0, "basal_area_m2_ha": 10.1, "d130_mean": 40.0, "h_dom_m": 27.3},
            {"species": "09", "stems_ha": 16.0, "basal_area_m2_ha": 0.3, "d130_mean": 12.0, "h_dom_m": 27.3}]
    e = cell_sheets.year_entry_v2(rows, 2032, 7)
    assert e["stems_ha"] == 64.0 and e["basal_area_m2_ha"] == pytest.approx(10.4, rel=1e-15)
    assert e["d130_mean_cm"] == pytest.approx((40.0 * 48 + 12.0 * 16) / 64, rel=1e-15)
    assert e["h_dom_m"] == 27.3
    assert [c["species"] for c in e["composition"]] == ["09", "61"]        # ordre stable
    assert [c["share"] for c in e["composition"]] == [0.25, 0.75]         # part des TIGES, pas de G


def test_h_dom_m_differente_entre_essences_est_refusee():
    rows = [{"species": "61", "stems_ha": 16.0, "basal_area_m2_ha": 1.0, "d130_mean": 30.0, "h_dom_m": 20.0},
            {"species": "09", "stems_ha": 16.0, "basal_area_m2_ha": 1.0, "d130_mean": 30.0, "h_dom_m": 21.0}]
    with pytest.raises(ModuleError, match="h_dom_m"):
        cell_sheets.year_entry_v2(rows, 2032, 7)


def test_tiges_vivantes_avec_h_dom_m_null_refusees_jamais_aucun_arbre_vivant():
    rows = [{"species": "61", "stems_ha": 48.0, "basal_area_m2_ha": 10.1, "d130_mean": 40.0, "h_dom_m": None}]
    with pytest.raises(ModuleError, match=r"cellule 7.*48 tiges/ha vivantes.*h_dom_m est null") as err:
        cell_sheets.year_entry_v2(rows, 2032, 7)
    assert "aucun arbre vivant" in str(err.value)   # la cause dit ce qu'elle refuse d'afficher
    # aucune ligne : c'est bien « aucun arbre vivant », et rien n'est refusé
    assert cell_sheets.year_entry_v2([], 2032, 7)["h_dom_m"] is None


# ---------------------------------------------------------------- bout en bout sur un sim/ synthétique

def test_index_annees_instances_et_morts(sim_zone):
    idx = json.loads((sim_zone["dir"] / "tiles" / "index.json").read_text(encoding="utf-8"))
    assert idx["source"] == "sim" and idx["t0"] == 2022 and idx["year_step"] == 1
    assert idx["run_config_sha256"] == "0" * 64
    assert [(e["year"], e["instances"], e["dead"]) for e in idx["years"]] == [(2022, 14080, 0), (2023, 14078, 3)]
    assert any("non validée écologiquement" in n for n in idx["notes"])
    assert "non validée écologiquement" in idx["basal_area_map"]["mention"]


def test_les_annees_perimees_sont_effacees_et_rien_ne_reste_en_cours(sim_zone):
    zone = sim_zone["dir"]
    assert sorted(p.name for p in (zone / "tiles").iterdir()) == ["2022", "2023", "index.json"]
    assert not (zone / assets.STAGING).exists()


def test_le_point_connu_tombe_dans_la_bonne_tuile_et_la_bonne_cellule(sim_zone):
    zone = sim_zone["dir"]
    inst = read_instances(zone, 2023)
    d = np.hypot(inst["xy"][:, 0] - KNOWN_POINT[0], inst["xy"][:, 1] - KNOWN_POINT[1])
    i = int(d.argmin())
    assert d[i] < 0.01                                              # au centimètre
    assert inst["tile"][i] == "t_700000_6500500"
    assert inst["node"][i] == "generique_feuillu"                    # 09, hêtre
    assert inst["scale"][i].tolist() == pytest.approx([1.5, 6.0, 1.5], abs=1e-5)   # (cw / 2, h, cw / 2)
    assert cell_of(*KNOWN_POINT) == 0
    sheet = json.loads((zone / "web" / "cells" / "t_700000_6500500.json").read_text(encoding="utf-8"))
    c0 = next(c for c in sheet["cells"] if c["cell_id"] == 0)
    assert (c0["x"], c0["y"]) == (700012.5, 6500987.5)
    year_2023 = next(e for e in c0["years"] if e["year"] == 2023)
    assert "09" in {c["species"] for c in year_2023["composition"]}
    assert year_2023["flags"] == [{"kind": "hdom_au_dessus_du_plafond", "message": "H_dom au-dessus du plafond", "value": 31.5}]
    # x et y non inversés : le miroir (y, x) du point connu n'est pas une instance
    assert np.hypot(inst["xy"][:, 0] - KNOWN_POINT[1], inst["xy"][:, 1] - KNOWN_POINT[0]).min() > 1000


def test_aucun_mort_n_est_dessine(sim_zone):
    zone, st = sim_zone["dir"], sim_zone["states"][2023]
    inst = read_instances(zone, 2023)
    for tid in DEAD:
        i = st["tree_id"].index(tid)
        assert np.hypot(inst["xy"][:, 0] - st["x"][i], inst["xy"][:, 1] - st["y"][i]).min() > 0.05, tid


def test_fiches_v2_toutes_les_annees_et_mentions(sim_zone):
    zone = sim_zone["dir"]
    for p in sorted((zone / "web" / "cells").glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["schema_version"] == 2 and doc["source"] == "sim"
        assert any("non validée écologiquement" in n for n in doc["notes"])
        assert any("volume et carbone non calculés" in n for n in doc["notes"])
        for c in doc["cells"]:
            assert [e["year"] for e in c["years"]] == [2022, 2023]
            assert all(("h0_m" in e) <= (e["year"] == 2022) for e in c["years"])


def test_carte_de_g_et_extras_du_tileset(sim_zone):
    zone = sim_zone["dir"]
    with rasterio.open(zone / "web" / "rasters" / "g_2023.tif") as r:
        g = r.read(1)
        assert r.dtypes[0] == "float32" and r.overviews(1)
        cells = pq.read_table(zone / "sim" / "cells" / "year=2023" / "part-00000.parquet").to_pylist()
        expected = sum(row["basal_area_m2_ha"] for row in cells if row["cell_id"] == 0)
        assert g[0, 0] == pytest.approx(expected, rel=1e-6)
    extras = json.loads((zone / "tiles" / "2023" / "tileset.json").read_text(encoding="utf-8"))["extras"]
    assert extras["etat"] == "simulé" and extras["annee"] == 2023 and extras["instances"] == 14078
    assert extras["source"] == "sim/trees/year=2023" and "non validée écologiquement" in extras["mention"]


def test_rejeu_identique_a_l_octet_pres(sim_zone):
    zone = sim_zone["dir"]
    before = fingerprints(zone)
    produce(zone)
    assert fingerprints(zone) == before


# ---------------------------------------------------------------- refus : rien n'est écrit, rien n'est perdu

def test_partition_absente_refusee_et_sorties_precedentes_intactes(fresh):
    produce(fresh)
    before = fingerprints(fresh)
    shutil.rmtree(fresh / "sim" / "trees" / "year=2023")
    with pytest.raises(ModuleError, match="2023"):
        produce(fresh)
    assert fingerprints(fresh) == before
    assert not (fresh / assets.STAGING).exists()


@pytest.mark.parametrize("key, value, word", [("seed", 43, "seed"), ("t0", 2021, "t0"), ("years", 2, "years")])
def test_bloc_simulate_different_du_run_refuse(fresh, key, value, word):
    config = {**CONFIG, "simulate": {**CONFIG["simulate"], key: value}}
    with pytest.raises(ModuleError, match=word):
        produce(fresh, config)
    assert not (fresh / "tiles").exists()


def test_run_json_absent_refuse(fresh):
    (fresh / "sim" / "run.json").unlink()
    with pytest.raises(ModuleError, match="run.json"):
        produce(fresh)
    assert not (fresh / "tiles").exists() and not (fresh / assets.STAGING).exists()


def test_tree_id_en_double_refuse(fresh, capfd):
    """Le validateur du contrat simulate.trees (clé tree_id, year) le refuse avant toute écriture, et le nomme."""
    p = fresh / "sim" / "trees" / "year=2023" / "part-00000.parquet"
    t = pq.read_table(p).to_pydict()
    t["tree_id"][1] = t["tree_id"][0]
    pq.write_table(pa.table(t), p)
    with pytest.raises(ModuleError, match="simulate.trees"):
        produce(fresh)
    assert "doublon" in capfd.readouterr().err
    assert not (fresh / "tiles").exists()


def test_tree_id_en_double_refuse_aussi_sans_validateur(fresh):
    """Le contrôle propre de assets (lecture d'une partition), s'il est appelé sans le validateur."""
    p = fresh / "sim" / "trees" / "year=2023" / "part-00000.parquet"
    t = pq.read_table(p).to_pydict()
    t["tree_id"][1] = t["tree_id"][0]
    pq.write_table(pa.table(t), p)
    with pytest.raises(ModuleError, match="tree_id en double"):
        sim_state.read_trees(fresh, 2023)


def test_sans_h_dom_m_refuse(fresh):
    p = fresh / "sim" / "cells" / "year=2022" / "part-00000.parquet"
    pq.write_table(pq.read_table(p).drop_columns(["h_dom_m"]), p)
    with pytest.raises(ModuleError, match="h_dom_m"):
        produce(fresh)


def test_tiges_avec_h_dom_m_null_refusees_en_code_2(fresh):
    p = fresh / "sim" / "cells" / "year=2022" / "part-00000.parquet"
    t = pq.read_table(p)
    nulls = pa.array([None] * t.num_rows, pa.float64())
    pq.write_table(t.set_column(t.schema.get_field_index("h_dom_m"), "h_dom_m", nulls), p)
    with pytest.raises(ModuleError, match="h_dom_m est null"):   # ModuleError = code de sortie 2 (common.py)
        produce(fresh)


def test_tuiles_du_point_connu():
    x, y = tiles.tile_corner(np.array([KNOWN_POINT[0]]), np.array([KNOWN_POINT[1]]))
    assert tiles.tile_name(int(x[0]), int(y[0])) == "t_700000_6500500"


# ---------------------------------------------------------------- massif/ en mode sim (mission 070)

def massif_block(zone: Path, year: int, name: str) -> dict:
    return json.loads((zone / "massif" / str(year) / f"{name}.json").read_text(encoding="utf-8"))


def test_massif_sim_sans_recrutement_dit_ifn_direct_et_compte_les_vivants(sim_zone):
    zone = sim_zone["dir"]
    index = json.loads((zone / "massif" / "index.json").read_text(encoding="utf-8"))
    assert index["source"] == "sim" and index["recruitment"] == "ifn_direct"          # run.json de M3a : sans clé recruitment
    assert [(y["year"], y["trees"]) for y in index["years"]] == [(2022, 14080), (2023, 14078)]
    tiles_index = json.loads((zone / "tiles" / "index.json").read_text(encoding="utf-8"))
    for massif_year, tiles_year in zip(index["years"], tiles_index["years"]):
        assert massif_year["trees"] == tiles_year["instances"]
        assert [(b["block_id"], b["trees"]) for b in massif_year["blocks"]] == \
            [(t["tile"], t["instances"]) for t in tiles_year["tiles"]]
        assert sum(massif_year["trees_by_kind"].values()) == massif_year["trees"]
    assert index["years"][0]["trees_by_kind"] == {"own": 0, "alias": 0, "generic": 14080}   # aucun exemplaire configuré
    block = massif_block(zone, 2023, "t_700000_6500500")
    assert block["seedlings_simulated"] is False and all("seedlings" not in c for c in block["cells"])
    assert any("semis non simulés" in m for m in block["mentions"])
    assert not any("hcb absent" in m for m in block["mentions"])                         # sim/trees porte hcb


def test_massif_sim_le_point_connu_est_a_sa_place_relative_et_les_morts_sont_absents(sim_zone):
    zone, state = sim_zone["dir"], sim_zone["states"][2023]
    block = massif_block(zone, 2023, "t_700000_6500500")
    recruit = next(t for t in block["trees"] if t["tree_id"] == "r2023_000001")
    assert (block["origin"]["x"], block["origin"]["y"]) == (700_000.0, 6_500_500.0)
    assert (recruit["x"], recruit["y"]) == (12.5, 487.5)                                  # (est, nord) relatifs, x != y
    assert (recruit["h"], recruit["d130"], recruit["hcb"], recruit["cw"]) == (6.0, 8.0, 2.0, 3.0)
    assert recruit["z"] + block["origin"]["z"] == pytest.approx(
        float(altitude.read_ngf_altitude(zone / "dtm.tif", np.array([KNOWN_POINT[0]]), np.array([KNOWN_POINT[1]]))[0]), abs=2e-3)
    ids = {t["tree_id"] for b in (massif_block(zone, 2023, n) for n in ("t_700000_6500000", "t_700000_6500500",
                                                                      "t_700500_6500000", "t_700500_6500500")) for t in b["trees"]}
    assert not set(DEAD) & ids and len(ids) == 14078
    older = {t["tree_id"] for n in ("t_700000_6500000", "t_700000_6500500", "t_700500_6500000", "t_700500_6500500")
             for t in massif_block(zone, 2022, n)["trees"]}
    assert set(DEAD) <= older and "r2023_000001" not in older                           # vivants en 2022, morts en 2023


@pytest.fixture(scope="module")
def cohort_zone(tmp_path_factory, zone_chain):
    """Même sim/ synthétique, déclaré en mode cohorts : colonnes de semis dans sim/cells, run.json de M5a."""
    directory = tmp_path_factory.mktemp("cohorts") / "zone_fictive"
    shutil.copytree(zone_chain, directory, ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim", "massif"))
    write_sim(directory)
    seedlings = {}
    for year in (2022, 2023):
        path = directory / "sim" / "cells" / f"year={year}" / "part-00000.parquet"
        table = pq.read_table(path)
        count, height = [], []
        for cell, species in zip(table.column("cell_id").to_pylist(), table.column("species").to_pylist()):
            n = 40.0 * (1 + cell % 3) if cell % 7 == 0 else 0.0           # semis dans une cellule sur sept (valeurs d'essai)
            count.append(n)
            height.append(0.4 + 0.1 * (cell % 5))
            if n:
                seedlings.setdefault((year, cell), []).append({"species": species, "seedlings_ha": n, "h_mean_m": height[-1]})
        table = table.append_column("seedlings_ha", pa.array(count, pa.float64())).append_column(
            "seedling_h_mean", pa.array(height, pa.float64()))
        pq.write_table(table, path)
    run_path = directory / "sim" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run.update({"recruitment": "cohorts", "not_simulated": ["sous_bois", "gibier", "fructification"],
                "memory_estimate_max_bytes": 0, "memory_peak_rss_bytes": None, "seedling_stock_limited": 0,
                "gaps_recolonised": 0, "buffer_cells": 0})
    run_path.write_text(json.dumps(run), encoding="utf-8")
    summary = produce(directory)
    return {"dir": directory, "seedlings": seedlings, "summary": summary}


def test_massif_cohorts_les_semis_sont_ceux_de_sim_cells(cohort_zone):
    zone = cohort_zone["dir"]
    index = json.loads((zone / "massif" / "index.json").read_text(encoding="utf-8"))
    assert index["recruitment"] == "cohorts"
    assert any("semis simulés par cohortes" in n for n in index["notes"]) and any("Q2 de M5a" in n for n in index["notes"])
    found = {}
    for year in (2022, 2023):
        for name in ("t_700000_6500000", "t_700000_6500500", "t_700500_6500000", "t_700500_6500500"):
            block = massif_block(zone, year, name)
            assert block["seedlings_simulated"] is True
            for cell in block["cells"]:
                assert "seedlings" in cell                                          # [] pour une cellule sans semis
                if cell["seedlings"]:
                    found[(year, cell["cell_id"])] = cell["seedlings"]
    assert found == {k: sorted(v, key=lambda r: r["species"]) for k, v in cohort_zone["seedlings"].items()}
    assert len(found) > 20


def test_massif_cohorts_semis_sans_hauteur_est_un_refus(tmp_path, zone_chain):
    directory = tmp_path / "z"
    shutil.copytree(zone_chain, directory, ignore=shutil.ignore_patterns("tiles", "web", "assets", "sim", "massif"))
    write_sim(directory)
    path = directory / "sim" / "cells" / "year=2022" / "part-00000.parquet"
    table = pq.read_table(path)
    n = table.num_rows
    table = table.append_column("seedlings_ha", pa.array([10.0] * n, pa.float64())).append_column(
        "seedling_h_mean", pa.array([None] * n, pa.float64()))
    pq.write_table(table, path)
    with pytest.raises(ModuleError, match="seedling_h_mean|hauteur"):
        sim_state.read_seedlings(directory, 2022)
    pq.write_table(table.drop_columns(["seedling_h_mean"]), path)
    with pytest.raises(ModuleError, match="seedling_h_mean"):
        sim_state.read_seedlings(directory, 2022)


def test_demande_de_dimensions_quantiles_de_sim_trees_au_contrat(sim_zone, tmp_path):
    """Q6 : D et H en quantiles de sim/trees par essence et stade, écrits au format params.model_dimensions."""
    import csv
    import subprocess
    import sys
    from sylvigenese.assets_lib import exemplars, stages
    zone = sim_zone["dir"]
    rows, notes = exemplars.dimensions_request(zone, CONFIG, 0.5, 30)
    path = exemplars.write_request(tmp_path / "demande.csv", rows)
    r = subprocess.run([sys.executable, "contracts/validate", "params.model_dimensions", str(path)], capture_output=True,
                       text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    with open(path, encoding="utf-8", newline="") as f:
        written = list(csv.DictReader(f))
    assert [r["term"] for r in written][:2] == ["D_cm", "H_m"] and {r["provisoire"] for r in written} == {"true"}
    assert all("quantile 0,5" in r["source"] or "quantile 0.5" in r["source"] for r in written)
    # calcul indépendant : les arbres vivants des deux années, stade = h / h_pot de leur cellule
    with rasterio.open(zone / "site_potential.tif") as src:
        ceiling = src.read(1)
    species = {"09": "Fagus_sylvatica", "03": "Quercus_spec", "61": "Abies_alba", "62": "Picea_abies", "64": "Pseudotsuga_menziesii"}
    breaks = stages.load_breaks()
    pools = {}
    for year, state in sim_zone["states"].items():
        for sp, x, y, d, h, s in zip(state["species"], state["x"], state["y"], state["d130"], state["h"], state["status"]):
            if s != "alive":
                continue
            ratio = h / float(ceiling[int((6_501_000 - y) // 25), int((x - 700_000) // 25)])
            stage = stages.STAGES[sum(ratio >= b for b in breaks)]
            pools.setdefault((species[sp], stage), []).append((d, h))
    expected = {}
    for (essence, stage), values in pools.items():
        if len(values) >= 30:
            arr = np.array(values)
            expected[(essence, stage, "D_cm")] = float(np.quantile(arr[:, 0], 0.5))
            expected[(essence, stage, "H_m")] = float(np.quantile(arr[:, 1], 0.5))
    got = {(r["essence"], r["stage"], r["term"]): float(r["value"]) for r in written}
    assert got.keys() == expected.keys() and len(got) >= 8
    for key, value in expected.items():
        assert got[key] == pytest.approx(value, abs=6e-4), key                            # arrondi à 3 décimales
    # un couple trop peu peuplé est signalé, pas complété ; aucun couple assez peuplé : rien à demander
    with pytest.raises(ModuleError, match="rien à demander"):
        exemplars.dimensions_request(zone, CONFIG, 0.5, 10 ** 6)
    for key in {(n["essence"], n["stage"]) for n in notes if n["stage"]}:
        assert (key[0], key[1], "D_cm") not in got


def test_demande_de_dimensions_par_la_ligne_de_commande(sim_zone, tmp_path, monkeypatch):
    out = tmp_path / "demande.csv"
    cfg = tmp_path / "config.yml"
    cfg.write_text(yaml.safe_dump({**CONFIG, "zone": "zone_fictive"}, allow_unicode=True), encoding="utf-8")
    # zone_dir() désigne <racine>/tests/fixtures/zone_fictive : une racine d'essai le reconstitue autour de la copie
    root = tmp_path / "racine"
    (root / "tests" / "fixtures").mkdir(parents=True)
    (root / "tests" / "fixtures" / "zone_fictive").symlink_to(sim_zone["dir"])
    monkeypatch.setenv("SYLVIGENESE_ROOT", str(root))
    assert assets.main(["--config", str(cfg), "--demande-dimensions", str(out)]) == 0
    assert out.is_file() and out.read_text(encoding="utf-8").startswith("essence,stage,term,value,unit,provisoire,source")
    assert assets.main(["--config", str(cfg), "--demande-dimensions", str(out), "--quantile", "1.5"]) == 2
