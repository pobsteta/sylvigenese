"""Contrats de la suite de M4a, la vue dans le temps (mission 044 ; plan m4a-suite-temps §3).

Fiche de cellule v2, tiles/index.json, raster de surface terrière par année, bloc `assets` de
config.yml et colonne h_dom_m de sim.cells. Un cas conforme et un cas fautif par règle nouvelle ;
la version 1 de la fiche reste conforme (rétrocompatibilité). Les valeurs sont celles d'un essai :
aucune n'a de sens écologique. Coordonnées : EPSG:2154, x est, y nord.
"""
import copy
import fnmatch
import re

import pytest

import helpers as h
from validator import catalog, cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def sheet_path(tmp_path, sheet):
    return h.write_json(tmp_path / "t_0_0.json", sheet)


def index_path(tmp_path, data):
    return h.write_json(tmp_path / "index.json", data)


def mutated(factory, change):
    data = copy.deepcopy(factory())
    change(data)
    return data


def year0(d):
    return d["cells"][0]["years"][0]


# ------------------------------------------------------------------ fiche v1 inchangée

def test_cell_sheet_v1_stays_conform(tmp_path, capsys):
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, h.cell_sheet()))])
    assert code == 0, out


def test_cell_sheet_v1_with_its_optional_keys_stays_conform(tmp_path, capsys):
    sheet = h.cell_sheet()
    year0(sheet).update(h0_m=26.9, density_trees_ha=112.0, notes=["volume et carbone non calculés"])
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 0, out


@pytest.mark.parametrize("key,value", [
    ("source", "sim"), ("notes", ["volume et carbone non calculés"])])
def test_cell_sheet_v1_refuses_the_keys_of_v2(key, value, tmp_path, capsys):
    sheet = h.cell_sheet()
    sheet[key] = value
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 3 and key in out, out


def test_cell_sheet_refuses_an_unknown_version(tmp_path, capsys):
    """La version 3 existe depuis la mission 051 : la première version inconnue est la 4."""
    sheet = h.cell_sheet()
    sheet["schema_version"] = 4
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 3 and "schema_version" in out, out


# ------------------------------------------------------------------ fiche v2

def test_cell_sheet_v2_is_conform(tmp_path, capsys):
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, h.cell_sheet_v2()))])
    assert code == 0, out


def test_cell_sheet_v2_accepts_a_cell_without_stem_and_an_unknown_ceiling(tmp_path, capsys):
    sheet = h.cell_sheet_v2()
    year = year0(sheet)
    year.update(stems_ha=0.0, basal_area_m2_ha=0.0, d130_mean_cm=None, composition=[])
    sheet["cells"][0]["h_ceiling_m"] = None
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 0, out


def test_cell_sheet_v2_accepts_a_null_h_dom_m_with_stems(tmp_path, capsys):
    """I3 (relecture de la PR n° 9) : h_dom_m null est conforme, même avec des tiges (hauteur dominante non finie) ;
    c'est assets qui refuse ce cas à l'écriture, le contrat de la fiche n'a pas à le faire."""
    sheet = h.cell_sheet_v2()
    year0(sheet)["h_dom_m"] = None
    assert year0(sheet)["stems_ha"] > 0
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 0, out


V2_FAULTS = [
    # (nom du cas, changement, motif attendu dans le message)
    ("source not sim", lambda d: d.update(source="trees_init"), r"source"),
    ("source missing", lambda d: d.pop("source"), r"source"),
    ("document notes missing", lambda d: d.pop("notes"), r"notes"),
    ("notes without the ecological mention",
     lambda d: d.update(notes=["volume et carbone non calculés (post)"]), r"notes"),
    ("notes without the volume mention",
     lambda d: d.update(notes=["non validée écologiquement"]), r"notes"),
    ("note per year", lambda d: year0(d).update(notes=["provisoire"]), r"notes"),
    ("v1 density kept in v2", lambda d: year0(d).update(density_trees_ha=112.0), r"density_trees_ha"),
    ("h_dom_m missing", lambda d: year0(d).pop("h_dom_m"), r"h_dom_m"),
    ("h_dom_m negative", lambda d: year0(d).update(h_dom_m=-1.0), r"h_dom_m"),
    ("h_ceiling_m missing", lambda d: d["cells"][0].pop("h_ceiling_m"), r"h_ceiling_m"),
    ("h_ceiling_m negative", lambda d: d["cells"][0].update(h_ceiling_m=-2.0), r"h_ceiling_m"),
    ("stems_ha missing", lambda d: year0(d).pop("stems_ha"), r"stems_ha"),
    ("basal area negative", lambda d: year0(d).update(basal_area_m2_ha=-0.1), r"basal_area_m2_ha"),
    ("d130 mean zero", lambda d: year0(d).update(d130_mean_cm=0), r"d130_mean_cm"),
    ("d130 mean missing", lambda d: year0(d).pop("d130_mean_cm"), r"d130_mean_cm"),
    ("composition without stems",
     lambda d: year0(d)["composition"][0].pop("stems_ha"), r"stems_ha"),
    ("composition without basal area",
     lambda d: year0(d)["composition"][0].pop("basal_area_m2_ha"), r"basal_area_m2_ha"),
    ("share above one", lambda d: year0(d)["composition"][0].update(share=1.2), r"share"),
    ("species written 9", lambda d: year0(d)["composition"][0].update(species="9"), r"species"),
    ("flags missing", lambda d: year0(d).pop("flags"), r"flags"),
    ("flag kind in capitals",
     lambda d: d["cells"][0]["years"][1]["flags"][0].update(kind="Plafond"), r"kind"),
    ("flag without message", lambda d: d["cells"][0]["years"][1]["flags"][0].pop("message"),
     r"message"),
    ("flag with an unknown key",
     lambda d: d["cells"][0]["years"][1]["flags"][0].update(entity="12"), r"entity"),
    ("volume computed", lambda d: year0(d).update(volume_m3_ha=300.0), r"volume_m3_ha"),
    ("carbon computed", lambda d: year0(d).update(carbon_t_ha=100.0), r"carbon_t_ha"),
    ("volume missing", lambda d: year0(d).pop("volume_m3_ha"), r"volume_m3_ha"),
    ("provisoire missing", lambda d: year0(d).pop("provisoire"), r"provisoire"),
    ("cell without years", lambda d: d["cells"][0].update(years=[]), r"years"),
    ("x and y inverted",
     lambda d: d["cells"][0].update(x=h.PARIS_Y, y=h.PARIS_X), r"inversés"),
    ("unknown key at the root", lambda d: d.update(inconnu=1), r"inconnu"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in V2_FAULTS], ids=[c[0] for c in V2_FAULTS])
def test_cell_sheet_v2_faults_are_refused(change, pattern, tmp_path, capsys):
    sheet = mutated(h.cell_sheet_v2, change)
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 3 and re.search(pattern, out), out


def test_cell_sheet_v2_flag_value_may_be_absent_or_null(tmp_path, capsys):
    sheet = h.cell_sheet_v2()
    del sheet["cells"][0]["years"][1]["flags"][1]["value"]
    code, out = run(capsys, ["cell_sheet", str(sheet_path(tmp_path, sheet))])
    assert code == 0, out


# ------------------------------------------------------------------ tiles/index.json

def test_tiles_index_sim_is_conform(tmp_path, capsys):
    code, out = run(capsys, ["tiles_index", str(index_path(tmp_path, h.tiles_index()))])
    assert code == 0, out


def test_tiles_index_initial_state_is_conform(tmp_path, capsys):
    code, out = run(capsys, ["tiles_index", str(index_path(tmp_path, h.tiles_index_initial()))])
    assert code == 0, out


def drop(key):
    return lambda d: d.pop(key)


INDEX_FAULTS = [
    ("source unknown", lambda d: d.update(source="post"), r"source"),
    ("t0 missing", drop("t0"), r"t0"),
    ("provisoire missing", drop("provisoire"), r"provisoire"),
    ("notes empty", lambda d: d.update(notes=[]), r"notes"),
    ("sim without the ecological mention",
     lambda d: d.update(notes=["trajectoire technique"]), r"notes"),
    ("sim without year_step", drop("year_step"), r"year_step"),
    ("year_step zero", lambda d: d.update(year_step=0), r"year_step"),
    ("year_step fractional", lambda d: d.update(year_step=2.5), r"year_step"),
    ("sim without run_config_sha256", drop("run_config_sha256"), r"run_config_sha256"),
    ("run_config_sha256 in capitals",
     lambda d: d.update(run_config_sha256="ABC" * 21 + "A"), r"run_config_sha256"),
    ("sim without basal_area_map", drop("basal_area_map"), r"basal_area_map"),
    ("scale max zero", lambda d: d["basal_area_map"].update(scale_max_m2_ha=0), r"scale_max_m2_ha"),
    ("scale min negative",
     lambda d: d["basal_area_map"].update(scale_min_m2_ha=-1), r"scale_min_m2_ha"),
    ("scale without the mention",
     lambda d: d["basal_area_map"].update(mention="surface terrière"), r"mention"),
    ("scale unit other",
     lambda d: d["basal_area_map"].update(unit="m2"), r"unit"),
    ("scale missing a bound", lambda d: d["basal_area_map"].pop("scale_max_m2_ha"),
     r"scale_max_m2_ha"),
    ("sim year without dead", lambda d: d["years"][1].pop("dead"), r"dead"),
    ("dead negative", lambda d: d["years"][1].update(dead=-1), r"dead"),
    ("instances negative", lambda d: d["years"][0].update(instances=-1), r"instances"),
    ("tileset path without the year", lambda d: d["years"][0].update(tileset="tileset.json"),
     r"tileset"),
    ("tileset path from the root", lambda d: d["years"][0].update(tileset="tiles/2022/tileset.json"),
     r"tileset"),
    ("year without tiles", lambda d: d["years"][0].update(tiles=[]), r"tiles"),
    ("tile name unknown", lambda d: d["years"][0]["tiles"][0].update(tile="tuile_1"), r"tile"),
    ("tile without instances", lambda d: d["years"][0]["tiles"][0].pop("instances"), r"instances"),
    ("no year", lambda d: d.update(years=[]), r"years"),
    ("unknown key", lambda d: d.update(inconnu=1), r"inconnu"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in INDEX_FAULTS],
                         ids=[c[0] for c in INDEX_FAULTS])
def test_tiles_index_faults_are_refused(change, pattern, tmp_path, capsys):
    data = mutated(h.tiles_index, change)
    code, out = run(capsys, ["tiles_index", str(index_path(tmp_path, data))])
    assert code == 3 and re.search(pattern, out), out


INITIAL_FAULTS = [
    ("year_step in the initial state", lambda d: d.update(year_step=10), r"year_step"),
    ("run hash in the initial state",
     lambda d: d.update(run_config_sha256="0" * 64), r"run_config_sha256"),
    ("map in the initial state",
     lambda d: d.update(basal_area_map={"unit": "m2/ha", "scale_min_m2_ha": 0,
                                        "scale_max_m2_ha": 1,
                                        "mention": "non validée écologiquement"}),
     r"basal_area_map"),
    ("dead in the initial state", lambda d: d["years"][0].update(dead=0), r"dead"),
    ("two years in the initial state",
     lambda d: d["years"].append(copy.deepcopy(d["years"][0])), r"years"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in INITIAL_FAULTS],
                         ids=[c[0] for c in INITIAL_FAULTS])
def test_tiles_index_initial_state_faults_are_refused(change, pattern, tmp_path, capsys):
    data = mutated(h.tiles_index_initial, change)
    code, out = run(capsys, ["tiles_index", str(index_path(tmp_path, data))])
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ raster g_<année>.tif

def g_raster(tmp_path, name="g_2032.tif", **kwargs):
    options = dict(driver="COG", dtype="float32", size=600, pixel=25.0)
    options.update(kwargs)
    return h.tif(tmp_path / name, **options)


def test_basal_area_raster_is_conform(tmp_path, capsys):
    code, out = run(capsys, ["basal_area_raster", str(g_raster(tmp_path))])
    assert code == 0, out


@pytest.mark.parametrize("kwargs,pattern", [
    ({"dtype": "uint16"}, r"Float32|échantillon"),
    ({"bands": 2}, r"bande"),
    ({"pixel": 12.5}, r"12,5|12\.5|25"),
    ({"size": 100}, r"aperçu"),
    ({"crs": "EPSG:4326", "origin": (6.0, 46.0), "pixel": 0.0002}, r"2154|EPSG"),
], ids=["uint16", "two bands", "pixel 12.5 m", "no overview", "other crs"])
def test_basal_area_raster_faults_are_refused(kwargs, pattern, tmp_path, capsys):
    code, out = run(capsys, ["basal_area_raster", str(g_raster(tmp_path, **kwargs))])
    assert code == 3 and re.search(pattern, out), out


def test_basal_area_rasters_are_found_by_the_catalog_path():
    spec = catalog.get("assets.basal_area_raster")
    assert spec["paths"] == ["web/rasters/g_*.tif"]
    assert fnmatch.fnmatch("web/rasters/g_2032.tif", spec["paths"][0])
    assert not fnmatch.fnmatch("web/rasters/vegetation_map.tif", spec["paths"][0])


# ------------------------------------------------------------------ config.yml, bloc assets

def config_with(assets):
    data = h.config()
    data["assets"] = assets
    return data


def test_config_with_assets_is_conform(tmp_path, capsys):
    path = h.write_yaml(tmp_path / "config.yml", config_with({"year_step": 10}))
    code, out = run(capsys, ["config", str(path)])
    assert code == 0, out


def test_config_without_assets_stays_conform(tmp_path, capsys):
    """Le bloc est exigé par assets quand sim/ existe, pas par le schéma (rétrocompatibilité)."""
    path = h.write_yaml(tmp_path / "config.yml", h.config())
    code, out = run(capsys, ["config", str(path)])
    assert code == 0, out


@pytest.mark.parametrize("assets,pattern", [
    ({"year_step": 0}, r"year_step"),
    ({"year_step": -5}, r"year_step"),
    ({"year_step": 2.5}, r"year_step"),
    ({"year_step": "10"}, r"year_step"),
    ({}, r"year_step"),
    ({"year_step": 10, "annees": 5}, r"annees"),
], ids=["zero", "negative", "fractional", "string", "empty block", "unknown key"])
def test_config_assets_faults_are_refused(assets, pattern, tmp_path, capsys):
    path = h.write_yaml(tmp_path / "config.yml", config_with(assets))
    code, out = run(capsys, ["config", str(path)])
    assert code == 3 and re.search(pattern, out), out


def test_repository_config_stays_conform(capsys):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    code, out = run(capsys, ["config", str(root / "config.yml")])
    assert code == 0, out


# ------------------------------------------------------------------ sim.cells, h_dom_m

def cells_with_hdom(values):
    data = h.sim_cells()
    data["h_dom_m"] = values
    return data


def test_cells_with_h_dom_m_are_conform(tmp_path, capsys):
    path = h.hive(tmp_path / "cells", cells_with_hdom([25.0, 25.0, 0.0]))
    code, out = run(capsys, ["sim_cells", str(path)])
    assert code == 0, out


def test_cells_without_h_dom_m_stay_conform(tmp_path, capsys):
    """Colonne facultative tant que simulate ne l'écrit pas (mission 046)."""
    code, out = run(capsys, ["sim_cells", str(h.hive(tmp_path / "cells", h.sim_cells()))])
    assert code == 0, out


def test_cells_with_a_negative_h_dom_m_are_refused(tmp_path, capsys):
    path = h.hive(tmp_path / "cells", cells_with_hdom([25.0, -1.0, 3.0]))
    code, out = run(capsys, ["sim_cells", str(path)])
    assert code == 3 and "h_dom_m" in out, out


def test_cells_with_an_infinite_h_dom_m_are_refused(tmp_path, capsys):
    path = h.hive(tmp_path / "cells", cells_with_hdom([25.0, float("inf"), 3.0]))
    code, out = run(capsys, ["sim_cells", str(path)])
    assert code == 3 and re.search(r"h_dom_m|infini|NaN", out), out


# ------------------------------------------------------------------ tree_id : jamais des chiffres seuls (I4)

def sim_trees_with_ids(tmp_path, ids):
    data = h.sim_trees()
    data["tree_id"] = ids
    return h.hive(tmp_path / "trees", data)


@pytest.mark.parametrize("ids", [["T0001_0307", "r12_2030_3"], ["T1", "a"], ["1a", "12_3"]])
def test_sim_trees_tree_id_with_a_non_digit_is_conform(ids, tmp_path, capsys):
    code, out = run(capsys, ["simulate.trees", str(sim_trees_with_ids(tmp_path, ids))])
    assert code == 0, out


@pytest.mark.parametrize("ids", [["T1", "12345"], ["0307", "T2"]])
def test_sim_trees_tree_id_of_digits_only_is_refused(ids, tmp_path, capsys):
    code, out = run(capsys, ["simulate.trees", str(sim_trees_with_ids(tmp_path, ids))])
    assert code == 3, out
    assert re.search(r"tree_id.*motif", out), out
