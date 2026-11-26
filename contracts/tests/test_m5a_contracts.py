"""Contrats de M5a, le niveau SER en cohortes et la régénération (mission 060 ; plan m5a §3).

Chaque règle nouvelle a un cas conforme et un cas fautif : mode de recrutement et blocs `regeneration`
et `ser` de config.yml, `params/regeneration` (termes nommés, sans valeur), `cohorts_init`,
`sim.cohorts`, comptes et mentions de `run.json`, colonnes de semis de `sim.cells`, signalements.
Les contrats de M3a restent conformes (rétrocompatibilité). Les valeurs sont celles d'un essai :
aucune n'a de sens écologique.
"""
import copy
import re
from pathlib import Path

import pytest
import yaml

import helpers as h
from validator import catalog, cli

ROOT = Path(__file__).resolve().parents[2]


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def check(capsys, name, path):
    return run(capsys, [name, str(path)])


def mutated(factory, change):
    data = copy.deepcopy(factory())
    change(data)
    return data


def check_dict(capsys, name, data, tmp_path, suffix="json"):
    path = tmp_path / f"doc.{suffix}"
    if suffix == "json":
        h.write_json(path, data)
    else:
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return check(capsys, name, path)


# ------------------------------------------------------------------ config.yml

REGENERATION = {"kernel_truncation_cells": 16, "zero_threshold": 1e-9}
SER = {"diameter_class_width_cm": 5, "diameter_classes": 15, "write_step": 10}


def config_cohorts():
    data = h.config()
    data["simulate"].update(recruitment="cohorts", regeneration=dict(REGENERATION))
    return data


def config_ser():
    data = config_cohorts()
    data["simulate"].update(level="ser", ser=dict(SER))
    return data


@pytest.mark.parametrize("factory", [h.config, config_cohorts, config_ser], ids=["m3a", "cohorts", "ser"])
def test_config_conform(factory, tmp_path, capsys):
    code, out = check_dict(capsys, "config", factory(), tmp_path, "yml")
    assert code == 0, out


def test_config_ifn_direct_is_conform(tmp_path, capsys):
    data = h.config()
    data["simulate"]["recruitment"] = "ifn_direct"
    code, out = check_dict(capsys, "config", data, tmp_path, "yml")
    assert code == 0, out


def test_config_of_the_repo_keeps_ifn_direct_and_stays_conform(capsys):
    content = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    assert content["simulate"]["recruitment"] == "ifn_direct"
    assert content["simulate"]["level"] == "massif"
    code, out = check(capsys, "config", ROOT / "config.yml")
    assert code == 0, out


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d["simulate"].update(recruitment="mixte"), r"recruitment"),
    (lambda d: d["simulate"].update(recruitment=None), r"recruitment"),
    (lambda d: d["simulate"].pop("regeneration"), r"regeneration"),
    (lambda d: d["simulate"]["regeneration"].pop("kernel_truncation_cells"), r"kernel_truncation_cells"),
    (lambda d: d["simulate"]["regeneration"].pop("zero_threshold"), r"zero_threshold"),
    (lambda d: d["simulate"]["regeneration"].update(kernel_truncation_cells=0), r"kernel_truncation_cells"),
    (lambda d: d["simulate"]["regeneration"].update(kernel_truncation_cells=2.5), r"kernel_truncation_cells"),
    (lambda d: d["simulate"]["regeneration"].update(zero_threshold=0), r"zero_threshold"),
    (lambda d: d["simulate"]["regeneration"].update(zero_threshold=1), r"zero_threshold"),
    (lambda d: d["simulate"]["regeneration"].update(inconnue=1), r"inconnue"),
], ids=["mode-inconnu", "mode-vide", "bloc-absent", "troncature-absente", "seuil-absent",
        "troncature-0", "troncature-decimale", "seuil-0", "seuil-1", "cle-inconnue"])
def test_config_cohorts_faulty_is_refused(change, pattern, tmp_path, capsys):
    code, out = check_dict(capsys, "config", mutated(config_cohorts, change), tmp_path, "yml")
    assert code == 3 and re.search(pattern, out), out


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d["simulate"].pop("ser"), r"ser"),
    (lambda d: d["simulate"]["ser"].pop("diameter_class_width_cm"), r"diameter_class_width_cm"),
    (lambda d: d["simulate"]["ser"].pop("diameter_classes"), r"diameter_classes"),
    (lambda d: d["simulate"]["ser"].pop("write_step"), r"write_step"),
    (lambda d: d["simulate"]["ser"].update(diameter_class_width_cm=0), r"diameter_class_width_cm"),
    (lambda d: d["simulate"]["ser"].update(diameter_classes=1), r"diameter_classes"),
    (lambda d: d["simulate"]["ser"].update(write_step=0), r"write_step"),
    (lambda d: d["simulate"]["ser"].update(inconnue=1), r"inconnue"),
], ids=["bloc-absent", "largeur-absente", "classes-absentes", "pas-absent",
        "largeur-0", "une-classe", "pas-0", "cle-inconnue"])
def test_config_ser_faulty_is_refused(change, pattern, tmp_path, capsys):
    code, out = check_dict(capsys, "config", mutated(config_ser, change), tmp_path, "yml")
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ params/regeneration

def regeneration_file(tmp_path, data):
    return h.parquet(tmp_path / "regeneration.parquet", data, h.REGENERATION_TYPES)


def test_regeneration_params_conform(tmp_path, capsys):
    code, out = check(capsys, "regeneration", regeneration_file(tmp_path, h.regeneration_params()))
    assert code == 0, out


def test_regeneration_params_have_a_closed_list_of_eleven_terms():
    schema = catalog.load_schema("tables/params/regeneration.schema.json")
    term = next(f for f in schema["fields"] if f["name"] == "term")
    assert [t for t, _ in h.TERMS] == term["constraints"]["enum"]


def test_regeneration_maturity_is_a_height_and_the_diameter_term_is_gone(tmp_path, capsys):
    """Mission 062 : la maturité est une hauteur (m), comme TreeMig ; maturity_d130_cm (version 0.1) est refusé."""
    schema = catalog.load_schema("tables/params/regeneration.schema.json")
    term = next(f for f in schema["fields"] if f["name"] == "term")
    assert "maturity_height_m" in term["constraints"]["enum"]
    assert "maturity_d130_cm" not in term["constraints"]["enum"]
    assert schema["x-schema-version"] == "0.3"
    data = h.regeneration_params()
    data["term"][data["term"].index("maturity_height_m")] = "maturity_d130_cm"
    code, out = check(capsys, "regeneration", regeneration_file(tmp_path, data))
    assert code == 3 and re.search(r"term", out), out


def test_regeneration_stress_mortality_is_a_term_of_the_contract(tmp_path, capsys):
    """Mission 066 : la mortalité de stress (TreeMig éq. 40) est un terme du contrat, version 0.3, sans valeur dans le
    schéma ; sans lui le contrat reste conforme (c'est simulate qui arrête, code 2, en mode cohorts)."""
    schema = catalog.load_schema("tables/params/regeneration.schema.json")
    term = next(f for f in schema["fields"] if f["name"] == "term")
    assert "stress_mortality" in term["constraints"]["enum"] and schema["x-schema-version"] == "0.3"
    for mot in ("stress_mortality", "éq. 40", "1/an", "code 2"):
        assert mot in schema["description"], mot
    assert "0,184" not in schema["description"] and "0.184" not in schema["description"]
    data = h.regeneration_params()
    assert "stress_mortality" in data["term"]
    code, out = check(capsys, "regeneration", regeneration_file(tmp_path, data))
    assert code == 0, out


def test_regeneration_kernel_is_documented_from_the_two_lososova_distances():
    """Mission 062 : le noyau se paramètre depuis les distances à 50 % et 99 % de la classe de Lososová."""
    desc = catalog.load_schema("tables/params/regeneration.schema.json")["description"]
    for mot in ("Lososová et al. 2023", "d50", "d99", "50 %", "99 %", "P(2 / b, (d50 / a)^b) = 0,5",
                "P(2 / b, (d99 / a)^b) = 0,99", "provisoire"):
        assert mot in desc, mot


def test_regeneration_schema_holds_no_value_but_the_nominal_ones_in_its_text():
    """Aucune valeur écologique dans le schéma : ni défaut, ni exemple, ni borne sur `value`."""
    schema = catalog.load_schema("tables/params/regeneration.schema.json")
    value = next(f for f in schema["fields"] if f["name"] == "value")
    assert set(value.get("constraints", {})) == {"required"}
    for field in schema["fields"]:
        assert "default" not in field and "example" not in field


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d["term"].__setitem__(0, "dispersion_par_le_vent"), r"term"),
    (lambda d: d["source"].__setitem__(0, ""), r"source"),
    (lambda d: d["source"].__setitem__(0, None), r"source"),
    (lambda d: d["provisoire"].__setitem__(0, None), r"provisoire"),
    (lambda d: d["unit"].__setitem__(0, ""), r"unit"),
    (lambda d: d["value"].__setitem__(0, float("nan")), r"value"),
    (lambda d: d["value"].__setitem__(0, None), r"value"),
    (lambda d: d["species"].__setitem__(0, "9"), r"species"),
    (lambda d: (d["species"].__setitem__(0, None), d["species_group"].__setitem__(0, None)), r"species"),
    (lambda d: d["species_group"].__setitem__(11, "arbustes"), r"species_group"),
    (lambda d: d["term"].__setitem__(1, "kernel_scale_m"), r"doublon"),
    (lambda d: d.update(model=["x"] * 12), r"model"),
    (lambda d: d.pop("unit"), r"unit"),
], ids=["terme-hors-liste", "source-vide", "source-absente", "provisoire-absent", "unite-vide",
        "valeur-nan", "valeur-absente", "essence-sans-zero", "ni-essence-ni-groupe",
        "groupe-inconnu", "doublon", "colonne-en-trop", "colonne-absente"])
def test_regeneration_params_faulty_is_refused(change, pattern, tmp_path, capsys):
    data = mutated(h.regeneration_params, change)
    code, out = check(capsys, "regeneration", regeneration_file(tmp_path, data))
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ cohorts_init

@pytest.mark.parametrize("name", ["cohorts_init", "prepare.cohorts_init"])
def test_cohorts_init_conform(name, tmp_path, capsys):
    path = h.parquet(tmp_path / "cohorts_init.parquet", h.cohorts_init())
    code, out = check(capsys, name, path)
    assert code == 0, out


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d["d_class"].__setitem__(0, -1), r"d_class"),
    (lambda d: d["stems_ha"].__setitem__(0, -1.0), r"stems_ha"),
    (lambda d: d["stems_ha"].__setitem__(0, float("inf")), r"stems_ha"),
    (lambda d: d["cell_id"].__setitem__(0, -1), r"cell_id"),
    (lambda d: d["species"].__setitem__(0, "9"), r"species"),
    (lambda d: d["source"].__setitem__(0, ""), r"source"),
    (lambda d: d["source"].__setitem__(0, None), r"source"),
    (lambda d: d["d_class"].__setitem__(1, 0), r"doublon"),
    (lambda d: d.update(seedlings_ha=[0.0] * 4), r"seedlings_ha"),
    (lambda d: d.pop("d_class"), r"d_class"),
], ids=["classe-negative", "tiges-negatives", "tiges-infinies", "cellule-negative", "essence-sans-zero",
        "source-vide", "source-absente", "doublon", "semis-non-admis-ici", "classe-absente"])
def test_cohorts_init_faulty_is_refused(change, pattern, tmp_path, capsys):
    path = h.parquet(tmp_path / "cohorts_init.parquet", mutated(h.cohorts_init, change))
    code, out = check(capsys, "cohorts_init", path)
    assert code == 3 and re.search(pattern, out), out


def test_cohorts_init_with_a_float_class_is_refused(tmp_path, capsys):
    data = h.cohorts_init()
    data["d_class"] = [0.0, 1.0, 0.0, 0.0]
    code, out = check(capsys, "cohorts_init", h.parquet(tmp_path / "c.parquet", data))
    assert code == 3 and "d_class" in out, out


# ------------------------------------------------------------------ sim.cohorts

def test_sim_cohorts_partitioned_by_year_are_conform(tmp_path, capsys):
    root = h.hive(tmp_path / "cohorts", h.sim_cohorts())
    for name in ("sim_cohorts", "simulate.cohorts"):
        code, out = check(capsys, name, root)
        assert code == 0, out


def test_sim_cohorts_float32_densities_are_conform(tmp_path, capsys):
    data = h.sim_cohorts()
    data["stems_ha"] = h.pa.array(data["stems_ha"], type=h.pa.float32())
    code, out = check(capsys, "sim_cohorts", h.hive(tmp_path / "cohorts", data))
    assert code == 0, out


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d["stems_ha"].__setitem__(0, -0.5), r"stems_ha"),
    (lambda d: d["d_class"].__setitem__(0, -1), r"d_class"),
    (lambda d: d.pop("d_class"), r"d_class"),
    (lambda d: d["species"].__setitem__(0, "Hêtre"), r"species"),
    (lambda d: d.update(seedlings_ha=[0.0] * 3), r"seedlings_ha"),
    (lambda d: d["d_class"].__setitem__(1, 0), r"doublon"),
], ids=["tiges-negatives", "classe-negative", "classe-absente", "essence-en-clair",
        "colonne-de-semis-non-admise", "doublon"])
def test_sim_cohorts_faulty_is_refused(change, pattern, tmp_path, capsys):
    code, out = check(capsys, "sim_cohorts", h.hive(tmp_path / "cohorts", mutated(h.sim_cohorts, change)))
    assert code == 3 and re.search(pattern, out), out


def test_sim_cohorts_outside_a_year_folder_is_refused(tmp_path, capsys):
    data = h.sim_cohorts()
    del data["year"]
    code, out = check(capsys, "sim_cohorts", h.parquet(tmp_path / "cohorts" / "p.parquet", data))
    assert code == 3 and "year" in out, out


# ------------------------------------------------------------------ run.json

def run_cohorts():
    data = h.run_json()
    data.update(recruitment="cohorts", not_simulated=["gibier", "sous_bois", "fructification"],
                memory_estimate_max_bytes=130_000_000, memory_peak_rss_bytes=125_000_000,
                seedling_stock_limited=12, gaps_recolonised=3, buffer_cells=2000)
    return data


def run_ifn_direct():
    data = h.run_json()
    data.update(recruitment="ifn_direct", not_simulated=["semis", "sous_bois", "gibier", "fructification"],
                memory_estimate_max_bytes=123_456_789, memory_peak_rss_bytes=None)
    return data


def test_run_json_of_m3a_stays_conform(tmp_path, capsys):
    code, out = check_dict(capsys, "run", h.run_json(), tmp_path)
    assert code == 0, out


def test_run_json_of_m3a_built_here_stays_conform_in_a_zone_folder(tmp_path, capsys):
    """Un run.json de M3a (sans recruitment) écrit dans sim/ d'un dossier temporaire, pas d'un jeu généré."""
    path = h.write_json(_sim_dir(tmp_path) / "run.json", h.run_json())
    code, out = check(capsys, "run", path)
    assert code == 0, out


def _sim_dir(tmp_path):
    (tmp_path / "sim").mkdir(exist_ok=True)
    return tmp_path / "sim"


@pytest.mark.parametrize("factory", [run_cohorts, run_ifn_direct], ids=["cohorts", "ifn_direct"])
def test_run_json_of_m5a_is_conform(factory, tmp_path, capsys):
    code, out = check_dict(capsys, "run", factory(), tmp_path)
    assert code == 0, out


def test_run_json_at_level_ser_is_conform(tmp_path, capsys):
    data = run_cohorts()
    data["level"] = "ser"
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 0, out


def test_run_json_with_a_null_peak_is_conform_off_linux(tmp_path, capsys):
    data = run_cohorts()
    data["memory_peak_rss_bytes"] = None
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 0, out


@pytest.mark.parametrize("key", ["not_simulated", "memory_estimate_max_bytes", "memory_peak_rss_bytes"])
@pytest.mark.parametrize("factory", [run_cohorts, run_ifn_direct], ids=["cohorts", "ifn_direct"])
def test_run_json_of_m5a_without_a_key_is_refused(factory, key, tmp_path, capsys):
    data = factory()
    del data[key]
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and key in out, out


@pytest.mark.parametrize("key", ["seedling_stock_limited", "gaps_recolonised", "buffer_cells"])
def test_run_json_cohorts_without_a_count_is_refused(key, tmp_path, capsys):
    data = run_cohorts()
    del data[key]
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and key in out, out


@pytest.mark.parametrize("missing", ["gibier", "sous_bois", "fructification"])
def test_run_json_cohorts_must_say_what_is_not_simulated(missing, tmp_path, capsys):
    data = run_cohorts()
    data["not_simulated"].remove(missing)
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and "not_simulated" in out, out


def test_run_json_cohorts_cannot_say_seedlings_are_not_simulated(tmp_path, capsys):
    data = run_cohorts()
    data["not_simulated"].append("semis")
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and "not_simulated" in out, out


def test_run_json_ifn_direct_must_say_seedlings_are_not_simulated(tmp_path, capsys):
    data = run_ifn_direct()
    data["not_simulated"].remove("semis")
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and "not_simulated" in out, out


@pytest.mark.parametrize("key", ["seedling_stock_limited", "gaps_recolonised", "buffer_cells"])
def test_run_json_ifn_direct_refuses_the_cohort_counts(key, tmp_path, capsys):
    data = run_ifn_direct()
    data[key] = 0
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3, out


def test_run_json_cohort_counts_without_recruitment_are_refused(tmp_path, capsys):
    data = h.run_json()
    data["buffer_cells"] = 10
    code, out = check_dict(capsys, "run", data, tmp_path)
    assert code == 3 and "recruitment" in out, out


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d.update(recruitment="mixte"), r"recruitment"),
    (lambda d: d.update(not_simulated=["gibier", "sous_bois", "fructification", "mildiou"]), r"not_simulated"),
    (lambda d: d.update(not_simulated=["gibier", "gibier", "sous_bois", "fructification"]), r"not_simulated"),
    (lambda d: d.update(seedling_stock_limited=-1), r"seedling_stock_limited"),
    (lambda d: d.update(gaps_recolonised=1.5), r"gaps_recolonised"),
    (lambda d: d.update(buffer_cells=-3), r"buffer_cells"),
    (lambda d: d.update(memory_estimate_max_bytes=-1), r"memory_estimate_max_bytes"),
    (lambda d: d.update(memory_peak_rss_bytes=-1), r"memory_peak_rss_bytes"),
    (lambda d: d.update(memory_peak_rss_bytes="inconnue"), r"memory_peak_rss_bytes"),
    (lambda d: d.update(zeroed_values=None), r"zeroed_values"),
], ids=["mode-inconnu", "mention-inconnue", "mention-en-double", "stock-negatif", "trouees-decimales",
        "tampon-negatif", "estimation-negative", "pic-negatif", "pic-devine", "zeroed-null"])
def test_run_json_m5a_faulty_values_are_refused(change, pattern, tmp_path, capsys):
    code, out = check_dict(capsys, "run", mutated(run_cohorts, change), tmp_path)
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ sim.cells : semis et mode

def cells_without_seedlings():
    data = h.sim_cells()
    del data["seedlings_ha"], data["seedling_h_mean"]
    return data


def cells_seedlings_only_rows():
    """Au niveau SER en mode cohorts : un couple (cellule, essence) peut n'avoir que des semis."""
    data = h.sim_cells()
    data["stems_ha"] = [300.0, 0.0, 0.0]
    data["basal_area_m2_ha"] = [25.0, 0.0, 0.0]
    data["d130_mean"] = [32.0, None, None]
    data["seedlings_ha"] = [1000.0, 50.0, 400.0]
    data["seedling_h_mean"] = [0.6, 0.3, 0.2]
    return data


def seedling_columns_follow_the_mode(run_doc, cells_columns):
    """La règle entre deux fichiers (plan m5a §3), que le validateur ne lit pas : en mode cohorts,
    sim/cells porte seedlings_ha et seedling_h_mean ; en ifn_direct, il n'en porte aucune."""
    has = {"seedlings_ha", "seedling_h_mean"} <= set(cells_columns)
    none = not ({"seedlings_ha", "seedling_h_mean"} & set(cells_columns))
    mode = run_doc.get("recruitment")
    if mode == "cohorts":
        return has
    if mode == "ifn_direct":
        return none
    return True  # run.json de M3a : les colonnes restent facultatives


def test_cells_with_seedlings_follow_a_cohorts_run():
    assert seedling_columns_follow_the_mode(run_cohorts(), h.sim_cells())


def test_cells_without_seedlings_follow_an_ifn_direct_run():
    assert seedling_columns_follow_the_mode(run_ifn_direct(), cells_without_seedlings())


def test_cells_without_seedlings_contradict_a_cohorts_run():
    assert not seedling_columns_follow_the_mode(run_cohorts(), cells_without_seedlings())


def test_cells_with_one_seedling_column_contradict_a_cohorts_run():
    data = h.sim_cells()
    del data["seedling_h_mean"]
    assert not seedling_columns_follow_the_mode(run_cohorts(), data)


def test_cells_with_seedlings_contradict_an_ifn_direct_run():
    assert not seedling_columns_follow_the_mode(run_ifn_direct(), h.sim_cells())


def test_cells_of_m3a_stay_free_of_the_rule():
    assert seedling_columns_follow_the_mode(h.run_json(), cells_without_seedlings())
    assert seedling_columns_follow_the_mode(h.run_json(), h.sim_cells())


def test_cells_and_run_json_of_m3a_written_here_follow_the_rule(tmp_path, capsys):
    """sim/ d'un run de M3a construit par les fabriques : sim/cells partitionné, sans colonne de semis."""
    import json

    import pyarrow.dataset as ds
    sim = _sim_dir(tmp_path)
    h.write_json(sim / "run.json", h.run_json())
    h.hive(sim / "cells", cells_without_seedlings())
    code, out = check(capsys, "sim_cells", sim / "cells")
    assert code == 0, out
    run_doc = json.loads((sim / "run.json").read_text(encoding="utf-8"))
    columns = ds.dataset(sim / "cells", format="parquet", partitioning="hive").schema.names
    assert "seedlings_ha" not in columns
    assert seedling_columns_follow_the_mode(run_doc, columns)


def test_cells_with_seedling_only_rows_are_conform(tmp_path, capsys):
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", cells_seedlings_only_rows()))
    assert code == 0, out


@pytest.mark.parametrize("column,value", [("seedlings_ha", -1.0), ("seedling_h_mean", 0.0)])
def test_cells_with_a_faulty_seedling_value_are_refused(column, value, tmp_path, capsys):
    data = h.sim_cells()
    data[column][0] = value
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", data))
    assert code == 3 and column in out, out


# ------------------------------------------------------------------ signalements de M5a

def flags_m5a():
    return {"year": [2022, 2023, 2023], "entity": ["12", "12", "zone_fictive"],
            "kind": ["trouee_hors_de_portee", "trouee_hors_de_portee", "total_trouees_hors_de_portee"],
            "message": ["trouée hors de portée du noyau : elle reste vide"] * 2
                       + ["2 couples (cellule, année) hors de portée"],
            "value": [None, None, 2.0]}


def test_flags_of_m5a_are_conform(tmp_path, capsys):
    path = h.parquet(tmp_path / "flags.parquet", flags_m5a(), {"value": h.pa.float64()})
    code, out = check(capsys, "flags", path)
    assert code == 0, out


def test_flags_with_a_malformed_kind_are_refused(tmp_path, capsys):
    data = flags_m5a()
    data["kind"][0] = "Trouée hors de portée"
    path = h.parquet(tmp_path / "flags.parquet", data, {"value": h.pa.float64()})
    code, out = check(capsys, "flags", path)
    assert code == 3 and "kind" in out, out


def test_flags_without_a_message_are_refused(tmp_path, capsys):
    data = flags_m5a()
    data["message"][0] = ""
    path = h.parquet(tmp_path / "flags.parquet", data, {"value": h.pa.float64()})
    code, out = check(capsys, "flags", path)
    assert code == 3 and "message" in out, out


# ------------------------------------------------------------------ catalogue

@pytest.mark.parametrize("alias,name", [("regeneration", "dynamics.regeneration"),
                                        ("cohorts_init", "prepare.cohorts_init"),
                                        ("sim_cohorts", "simulate.cohorts"),
                                        ("cohorts", "simulate.cohorts")])
def test_catalog_resolves_the_new_contracts(alias, name):
    assert catalog.resolve(alias) == name


def test_new_outputs_are_not_required_in_a_zone_of_m3a():
    specs = catalog.load()
    for name in ("dynamics.regeneration", "prepare.cohorts_init", "simulate.cohorts"):
        assert specs[name]["required"] is False
