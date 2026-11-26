"""Contrats de post, volume et carbone (mission 051 ; plan post-volume-carbone §4 ; décisions de
Pascal Q1 à Q6 du 26/11/2026).

params/tarif (modèle NEMETON v5 et son domaine), sim/summary 0.2, sim/summary_zone, sim/post.json
et fiche de cellule v3. Un cas conforme et un cas fautif par règle nouvelle ; les fiches v1 et v2
restent conformes à l'identique. Les valeurs sont celles d'un essai : AUCUNE n'a de sens écologique,
aucune ne vient de tarif-nemeton. Coordonnées : EPSG:2154, x est, y nord.
"""
import copy
import json
import re
from pathlib import Path

import pyarrow as pa
import pytest

import helpers as h
from validator import catalog, cli

CONTRACTS = Path(__file__).resolve().parents[1]


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def mutated(factory, change):
    data = copy.deepcopy(factory())
    change(data)
    return data


def check_table(capsys, tmp_path, name, factory, change=None, types=None):
    data = mutated(factory, change) if change else factory()
    path = h.parquet(tmp_path / "t.parquet", data, types)
    return run(capsys, [name, str(path)])


# ------------------------------------------------------------------ params/tarif

def tarif_check(capsys, tmp_path, change=None):
    return check_table(capsys, tmp_path, "import_tarif.tarif", h.tarif, change, h.TARIF_TYPES)


def test_tarif_is_conform(capsys, tmp_path):
    code, out = tarif_check(capsys, tmp_path)
    assert code == 0, out


def test_tarif_has_its_own_contract_and_not_the_generic_one():
    schema = catalog.get("import_tarif.tarif")["schema"]
    assert schema == "tables/params/tarif.schema.json"
    assert catalog.get("import_tarif.allometry")["schema"] == "tables/params/parameters.schema.json"


def test_tarif_columns_are_the_ones_of_the_tarif_nemeton_csv():
    schema = json.loads((CONTRACTS / "tables/params/tarif.schema.json").read_text("utf-8"))
    names = [f["name"] for f in schema["fields"]]
    assert names[:2] == ["essence", "groupe"]
    assert {"modele", "terme", "valeur", "unite", "source_code", "source_biblio"} <= set(names)


def test_tarif_contract_holds_no_value():
    """Aucune valeur écologique dans le contrat : ni enum de valeurs, ni exemple, ni défaut."""
    schema = json.loads((CONTRACTS / "tables/params/tarif.schema.json").read_text("utf-8"))
    for field in schema["fields"]:
        assert "example" not in field and "default" not in field, field["name"]
    valeur = next(f for f in schema["fields"] if f["name"] == "valeur")
    assert set(valeur["constraints"]) == {"required"}


def test_tarif_accepts_a_row_by_group_without_species(capsys, tmp_path):
    def only_groups(d):
        keep = [i for i, e in enumerate(d["essence"]) if e is None]
        for key in d:
            d[key] = [d[key][i] for i in keep]
    code, out = tarif_check(capsys, tmp_path, only_groups)
    assert code == 0, out


TARIF_FAULTS = [
    ("old column species", lambda d: d.update(species=d.pop("essence")), r"species|essence"),
    ("old column value", lambda d: d.update(value=d.pop("valeur")), r"value|valeur"),
    ("model unknown", lambda d: d["modele"].__setitem__(0, "tarif_dbh_h"), r"modele"),
    ("model missing", lambda d: d["modele"].__setitem__(0, None), r"modele"),
    ("term empty", lambda d: d["terme"].__setitem__(0, ""), r"terme"),
    ("value infinite", lambda d: d["valeur"].__setitem__(0, float("inf")), r"valeur"),
    ("value missing", lambda d: d["valeur"].__setitem__(0, None), r"valeur"),
    ("unit missing", lambda d: d["unite"].__setitem__(0, None), r"unite"),
    ("unit empty", lambda d: d["unite"].__setitem__(0, ""), r"unite"),
    ("code source missing", lambda d: d["source_code"].__setitem__(0, None), r"source_code"),
    ("bibliographic source empty", lambda d: d["source_biblio"].__setitem__(0, ""), r"source_biblio"),
    ("commit in capitals", lambda d: d["source_commit"].__setitem__(0, "0F51B96"),
     r"source_commit"),
    ("commit too short", lambda d: d["source_commit"].__setitem__(0, "0f51"), r"source_commit"),
    ("provisoire as integer", lambda d: d.update(provisoire=[1] * len(d["provisoire"])),
     r"provisoire"),
    ("species written 9", lambda d: d["essence"].__setitem__(0, "9"), r"essence"),
    ("group unknown", lambda d: d["groupe"].__setitem__(5, "conifere"), r"groupe"),
    ("neither species nor group",
     lambda d: (d["essence"].__setitem__(5, None), d["groupe"].__setitem__(5, None)),
     r"essence, groupe"),
    ("same term twice",
     lambda d: [d[k].__setitem__(1, d[k][0]) for k in ("terme",)], r"doublon"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in TARIF_FAULTS],
                         ids=[c[0] for c in TARIF_FAULTS])
def test_tarif_faults_are_refused(change, pattern, capsys, tmp_path):
    code, out = tarif_check(capsys, tmp_path, change)
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ sim/summary 0.2

def summary_check(capsys, tmp_path, factory=h.summary, change=None):
    return check_table(capsys, tmp_path, "post.summary", factory, change)


def test_summary_is_conform(capsys, tmp_path):
    code, out = summary_check(capsys, tmp_path)
    assert code == 0, out


def test_summary_with_the_optional_provisional_root_carbon_is_conform(capsys, tmp_path):
    code, out = summary_check(capsys, tmp_path, h.summary_with_roots)
    assert code == 0, out


def test_summary_version_is_0_2():
    schema = json.loads((CONTRACTS / "tables/sim/summary.schema.json").read_text("utf-8"))
    assert schema["x-schema-version"] == "0.2"
    text = schema["description"].lower()
    assert "aérien total" in text and "pas de volume bois fort" in text


def test_summary_defines_each_quantity():
    schema = json.loads((CONTRACTS / "tables/sim/summary.schema.json").read_text("utf-8"))
    fields = {f["name"]: f for f in schema["fields"]}
    for name in ("volume_m3_ha", "biomass_t_ha", "carbon_t_ha", "carbon_roots_t_ha",
                 "stems_not_computed_ha", "basal_area_not_computed_share"):
        assert len(fields[name]["description"]) > 30, name
    assert "aérien total" in fields["volume_m3_ha"]["description"]
    assert "aérien" in fields["carbon_t_ha"]["description"]
    assert fields["carbon_roots_t_ha"]["x-optional"] is True
    assert "PROVISOIRE" in fields["carbon_roots_t_ha"]["description"]


SUMMARY_FAULTS = [
    ("stems_not_computed_ha missing", lambda d: d.pop("stems_not_computed_ha"),
     r"stems_not_computed_ha"),
    ("basal_area_not_computed_share missing", lambda d: d.pop("basal_area_not_computed_share"),
     r"basal_area_not_computed_share"),
    ("share above one", lambda d: d["basal_area_not_computed_share"].__setitem__(0, 1.2),
     r"basal_area_not_computed_share"),
    ("share negative", lambda d: d["basal_area_not_computed_share"].__setitem__(0, -0.1),
     r"basal_area_not_computed_share"),
    ("stems not computed negative", lambda d: d["stems_not_computed_ha"].__setitem__(0, -1.0),
     r"stems_not_computed_ha"),
    ("share NaN", lambda d: d["basal_area_not_computed_share"].__setitem__(0, float("nan")),
     r"basal_area_not_computed_share"),
    ("volume negative", lambda d: d["volume_m3_ha"].__setitem__(0, -1.0), r"volume_m3_ha"),
    ("volume missing", lambda d: d.pop("volume_m3_ha"), r"volume_m3_ha"),
    ("carbon missing", lambda d: d.pop("carbon_t_ha"), r"carbon_t_ha"),
    ("volume bois fort column added", lambda d: d.update(volume_sup7_m3_ha=[1.0, 1.0]),
     r"volume_sup7_m3_ha"),
    ("total volume column added (one volume only)",
     lambda d: d.update(volume_total_m3_ha=[1.0, 1.0]), r"volume_total_m3_ha"),
    ("root carbon negative",
     lambda d: d.update(carbon_roots_t_ha=[-1.0, 2.0]), r"carbon_roots_t_ha"),
    ("root carbon with a missing value",
     lambda d: d.update(carbon_roots_t_ha=[1.0, None]), r"carbon_roots_t_ha"),
    ("provisoire missing", lambda d: d.pop("provisoire"), r"provisoire"),
    ("same key twice", lambda d: d["cell_id"].__setitem__(1, 0), r"doublon"),
    ("species written 9", lambda d: d["species"].__setitem__(0, "9"), r"species"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in SUMMARY_FAULTS],
                         ids=[c[0] for c in SUMMARY_FAULTS])
def test_summary_faults_are_refused(change, pattern, capsys, tmp_path):
    types = {"carbon_roots_t_ha": pa.float64()}
    data = mutated(h.summary, change)
    code, out = run(capsys, ["post.summary", str(h.parquet(tmp_path / "s.parquet", data, types))])
    assert code == 3 and re.search(pattern, out), out


def test_summary_of_version_0_1_is_refused(capsys, tmp_path):
    """L'ancien summary (sans les colonnes non calculées) n'est plus conforme."""
    def v01(d):
        d.pop("stems_not_computed_ha")
        d.pop("basal_area_not_computed_share")
    code, out = summary_check(capsys, tmp_path, change=v01)
    assert code == 3 and "stems_not_computed_ha" in out, out


# ------------------------------------------------------------------ sim/summary_zone

def zone_check(capsys, tmp_path, change=None):
    return check_table(capsys, tmp_path, "post.summary_zone", h.summary_zone, change)


def test_summary_zone_is_conform(capsys, tmp_path):
    code, out = zone_check(capsys, tmp_path)
    assert code == 0, out


def test_summary_zone_accepts_the_optional_roots(capsys, tmp_path):
    def roots(d):
        d["carbon_roots_t"] = [30.0, 3.0]
        d["carbon_roots_t_ha"] = [12.0, 1.2]
    code, out = zone_check(capsys, tmp_path, roots)
    assert code == 0, out


def test_summary_zone_accepts_a_species_only_dead_this_year(capsys, tmp_path):
    """Un triplet sans arbre vivant mais avec des morts dans l'année garde sa ligne (flux)."""
    def only_dead(d):
        for key in ("volume_m3", "biomass_t", "carbon_t", "volume_m3_ha", "biomass_t_ha",
                    "carbon_t_ha", "basal_area_not_computed_share"):
            d[key][1] = 0.0
        d["stems_not_computed"][1] = 0
        d["dead_volume_m3"][1] = 2.0
    code, out = zone_check(capsys, tmp_path, only_dead)
    assert code == 0, out


ZONE_FAULTS = [
    ("forest area zero", lambda d: d["forest_area_ha"].__setitem__(0, 0.0), r"forest_area_ha"),
    ("forest area missing", lambda d: d.pop("forest_area_ha"), r"forest_area_ha"),
    ("vegetation type empty", lambda d: d["vegetation_type"].__setitem__(0, ""),
     r"vegetation_type"),
    ("vegetation type missing", lambda d: d.pop("vegetation_type"), r"vegetation_type"),
    ("year as a text", lambda d: d.update(year=["2030", "2030"]), r"year"),
    ("volume negative", lambda d: d["volume_m3"].__setitem__(0, -1.0), r"volume_m3"),
    ("dead volume negative", lambda d: d["dead_volume_m3"].__setitem__(0, -0.5),
     r"dead_volume_m3"),
    ("dead carbon missing", lambda d: d.pop("dead_carbon_t"), r"dead_carbon_t"),
    ("dead stems not computed missing", lambda d: d.pop("dead_stems_not_computed"),
     r"dead_stems_not_computed"),
    ("stems not computed fractional",
     lambda d: d.update(stems_not_computed=[10.5, 40.0]), r"stems_not_computed"),
    ("share above one", lambda d: d["basal_area_not_computed_share"].__setitem__(1, 1.5),
     r"basal_area_not_computed_share"),
    ("mean per hectare missing", lambda d: d.pop("carbon_t_ha"), r"carbon_t_ha"),
    ("carbon in CO2 column", lambda d: d.update(co2_t=[1.0, 1.0]), r"co2_t"),
    ("provisoire missing", lambda d: d.pop("provisoire"), r"provisoire"),
    ("same key twice", lambda d: d["species"].__setitem__(1, "09"), r"doublon"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in ZONE_FAULTS],
                         ids=[c[0] for c in ZONE_FAULTS])
def test_summary_zone_faults_are_refused(change, pattern, capsys, tmp_path):
    code, out = zone_check(capsys, tmp_path, change)
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ sim/post.json

def post_check(capsys, tmp_path, change=None):
    data = mutated(h.post_run_json, change) if change else h.post_run_json()
    return run(capsys, ["post.run", str(h.write_json(tmp_path / "post.json", data))])


def test_post_run_is_conform(capsys, tmp_path):
    code, out = post_check(capsys, tmp_path)
    assert code == 0, out


def test_post_run_with_no_tree_out_of_the_domain_is_conform(capsys, tmp_path):
    def none(d):
        d["out_of_domain"] = {}
        d["without_tarif"] = {}
        d["tree_years_not_computed"] = 0
    code, out = post_check(capsys, tmp_path, none)
    assert code == 0, out


def test_post_run_without_untyped_cell_is_conform(capsys, tmp_path):
    """Mission 053 : sans cellule hors type de végétation, le compte s'écrit quand même (liste vide, 0)."""
    code, out = post_check(capsys, tmp_path,
                           lambda d: d.update(without_vegetation_type={"cells": [], "tree_years": 0}))
    assert code == 0, out


def test_untyped_cells_rule_is_written_in_summary_zone_and_post_run():
    """Mission 053 : une cellule sans type de végétation n'entre pas dans summary_zone (aucun type inventé)."""
    zone = json.loads((CONTRACTS / "tables/sim/summary_zone.schema.json").read_text("utf-8"))["description"]
    post = json.loads((CONTRACTS / "json/post.schema.json").read_text("utf-8"))
    assert "SANS TYPE DE VÉGÉTATION" in zone and "without_vegetation_type" in zone
    assert "without_vegetation_type" in post["required"]


def test_tarif_description_names_the_terms_of_each_form():
    """Mission 053 : les termes de chaque forme sont écrits (NEMETON v5 et forme synthétique du jeu fictif)."""
    d = json.loads((CONTRACTS / "tables/params/tarif.schema.json").read_text("utf-8"))["description"]
    for term in ("sigma_log", "facteur_biais_sigma2", "k0", "k1", "beta", "lam", "x0", "sx", "h_ref", "n_points",
                 "marge_sommet", "u_min", "D_plafond", "synth_p1", "synth_p2", "synth_E", "rho_moyenne",
                 "rho_pente_10cm", "pas_D", "facteur_arbre_entier", "fraction", "ratio", "dbh_min", "hd_max"):
        assert re.search(rf"\b{term}\b", d), term
    assert "synth_p1 + synth_p2 / 2" in d


def test_post_run_is_found_by_its_catalog_path():
    spec = catalog.get("post.run")
    assert spec["paths"] == ["sim/post.json"] and spec["kind"] == "json"
    assert catalog.resolve("post_run") == "post.run"


def drop(key):
    return lambda d: d.pop(key)


POST_FAULTS = [
    ("run_config_sha256 missing", drop("run_config_sha256"), r"run_config_sha256"),
    ("run_config_sha256 in capitals", lambda d: d.update(run_config_sha256="AB" * 32),
     r"run_config_sha256"),
    ("run_config_sha256 too short", lambda d: d.update(run_config_sha256="abc"),
     r"run_config_sha256"),
    ("inputs_sha256 missing", drop("inputs_sha256"), r"inputs_sha256"),
    ("input hash missing", lambda d: d["inputs_sha256"].pop("params_tarif"), r"params_tarif"),
    ("input hash not hexadecimal", lambda d: d["inputs_sha256"].update(sim_trees="z" * 64),
     r"sim_trees"),
    ("unknown input", lambda d: d["inputs_sha256"].update(ifn="0" * 64), r"ifn"),
    ("tarif_commit missing", drop("tarif_commit"), r"tarif_commit"),
    ("tarif_commit in capitals", lambda d: d.update(tarif_commit="0F51B96"), r"tarif_commit"),
    ("tarif_commit too short", lambda d: d.update(tarif_commit="0f51"), r"tarif_commit"),
    ("models empty", lambda d: d.update(models=[]), r"models"),
    ("model unknown", lambda d: d["models"][0].update(model="tarif_dbh_h"), r"model"),
    ("model without source", lambda d: d["models"][0].pop("source"), r"source"),
    ("model without commit", lambda d: d["models"][0].pop("commit"), r"commit"),
    ("model commit not hexadecimal", lambda d: d["models"][0].update(commit="main"), r"commit"),
    ("tree_years_computed negative", lambda d: d.update(tree_years_computed=-1),
     r"tree_years_computed"),
    ("tree_years_not_computed missing", drop("tree_years_not_computed"),
     r"tree_years_not_computed"),
    ("count fractional", lambda d: d.update(tree_years_computed=1.5), r"tree_years_computed"),
    ("out_of_domain missing", drop("out_of_domain"), r"out_of_domain"),
    ("out_of_domain species written 9",
     lambda d: d["out_of_domain"].update({"9": d["out_of_domain"]["09"]}), r"nom de clé|9"),
    ("out_of_domain reason missing",
     lambda d: d["out_of_domain"]["09"].pop("hd_above"), r"hd_above"),
    ("out_of_domain reason unknown",
     lambda d: d["out_of_domain"]["09"].update(age_above=1), r"age_above"),
    ("out_of_domain negative", lambda d: d["out_of_domain"]["09"].update(dbh_below=-1),
     r"dbh_below"),
    ("without_tarif missing", drop("without_tarif"), r"without_tarif"),
    ("without_tarif zero", lambda d: d["without_tarif"].update({"02": 0}), r"02"),
    ("without_tarif species written 2", lambda d: d["without_tarif"].update({"2": 5}),
     r"nom de clé|2"),
    ("without_vegetation_type missing", drop("without_vegetation_type"), r"without_vegetation_type"),
    ("without_vegetation_type cell negative",
     lambda d: d["without_vegetation_type"].update(cells=[-1]), r"cells|-1"),
    ("without_vegetation_type cell repeated",
     lambda d: d["without_vegetation_type"].update(cells=[1423, 1423]), r"cells|1423"),
    ("without_vegetation_type count missing",
     lambda d: d["without_vegetation_type"].pop("tree_years"), r"tree_years"),
    ("without_vegetation_type count negative",
     lambda d: d["without_vegetation_type"].update(tree_years=-1), r"tree_years"),
    ("without_vegetation_type unknown key",
     lambda d: d["without_vegetation_type"].update(vegetation_type="inventé"), r"vegetation_type"),
    ("provisional_share above one", lambda d: d.update(provisional_share=1.5),
     r"provisional_share"),
    ("provisional_share missing", drop("provisional_share"), r"provisional_share"),
    ("duration negative", lambda d: d.update(duration_s=-1), r"duration_s"),
    ("schema_version other", lambda d: d.update(schema_version=2), r"schema_version"),
    ("unknown key", lambda d: d.update(inconnu=1), r"inconnu"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in POST_FAULTS],
                         ids=[c[0] for c in POST_FAULTS])
def test_post_run_faults_are_refused(change, pattern, capsys, tmp_path):
    code, out = post_check(capsys, tmp_path, change)
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ fiche de cellule v3

def sheet_check(capsys, tmp_path, change=None):
    data = mutated(h.cell_sheet_v3, change) if change else h.cell_sheet_v3()
    return run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "t_0_0.json", data))])


def year(d, i=0):
    return d["cells"][0]["years"][i]


def test_cell_sheet_v3_is_conform(capsys, tmp_path):
    code, out = sheet_check(capsys, tmp_path)
    assert code == 0, out


def test_cell_sheet_v3_without_roots_and_complete_needs_no_partial_note(capsys, tmp_path):
    """Aucune part non calculée, aucun carbone des racines : ni « volume partiel » ni « racines »."""
    def complete(d):
        for y in d["cells"][0]["years"]:
            y.pop("root_carbon_t_ha", None)
            y["basal_area_not_computed_share"] = 0.0
            y["stems_not_computed_ha"] = 0.0
            y["volume_partiel"] = False
            for c in y["composition"]:
                c["basal_area_not_computed_share"] = 0.0
        d["notes"] = [n for n in d["notes"] if not n.startswith("volume partiel")
                      and "racines" not in n]
        d["notes"].append("carbone aérien (biomasse aérienne × fraction de carbone)")
    code, out = sheet_check(capsys, tmp_path, complete)
    assert code == 0, out


def test_cell_sheet_v3_accepts_a_cell_without_live_tree(capsys, tmp_path):
    """Cellule sans arbre vivant : 0 est un fait arithmétique, la part est 0 (T7 du plan)."""
    def empty(d):
        y = year(d, 0)
        y.update(stems_ha=0.0, basal_area_m2_ha=0.0, d130_mean_cm=None, h_dom_m=None,
                 composition=[], volume_m3_ha=0.0, carbon_t_ha=0.0, root_carbon_t_ha=0.0,
                 stems_not_computed_ha=0.0, basal_area_not_computed_share=0.0,
                 volume_partiel=False)
    code, out = sheet_check(capsys, tmp_path, empty)
    assert code == 0, out


def test_cell_sheet_v3_accepts_null_when_nothing_is_computed(capsys, tmp_path):
    """Part = 1 : rien n'est calculé, volume et carbone valent null, avec leur raison."""
    def nothing(d):
        y = year(d, 1)
        y.update(basal_area_not_computed_share=1.0, volume_partiel=True, volume_m3_ha=None,
                 carbon_t_ha=None, root_carbon_t_ha=None,
                 not_computed_reason="toutes les tiges sont hors du domaine du tarif")
        for c in y["composition"]:
            c.update(basal_area_not_computed_share=1.0, volume_m3_ha=None, carbon_t_ha=None)
    code, out = sheet_check(capsys, tmp_path, nothing)
    assert code == 0, out


def test_cell_sheet_v3_accepts_a_sheet_without_the_root_key(capsys, tmp_path):
    def no_roots(d):
        for y in d["cells"][0]["years"]:
            y.pop("root_carbon_t_ha")
        d["notes"] = [n.replace("(racines)", "") for n in d["notes"]]
    code, out = sheet_check(capsys, tmp_path, no_roots)
    assert code == 0, out


def with_year(change):
    return lambda d: change(year(d, 1))


V3_FAULTS = [
    # version et document
    ("source not sim", lambda d: d.update(source="trees_init"), r"source"),
    ("tarif missing", drop("tarif"), r"tarif"),
    ("tarif not provisional", lambda d: d["tarif"].update(provisoire=False), r"provisoire"),
    ("tarif commit in capitals", lambda d: d["tarif"].update(commit="0F51B96"), r"commit"),
    ("tarif without name", lambda d: d["tarif"].pop("name"), r"name"),
    ("unknown key at the root", lambda d: d.update(inconnu=1), r"inconnu"),
    # notes du document
    ("notes missing", drop("notes"), r"notes"),
    ("notes without the ecological mention",
     lambda d: d.update(notes=[n for n in d["notes"] if "écologiquement" not in n]), r"notes"),
    ("notes without the volume definition",
     lambda d: d.update(notes=[n for n in d["notes"] if "volume aérien total" not in n]), r"notes"),
    ("notes without the carbon definition",
     lambda d: d.update(notes=[n for n in d["notes"] if "carbone aérien" not in n]), r"notes"),
    ("notes without soil and dead wood",
     lambda d: d.update(notes=[n for n in d["notes"] if "sol et bois mort" not in n]), r"notes"),
    ("notes still saying volume and carbon are not computed",
     lambda d: d["notes"].append("volume et carbone non calculés"), r"notes"),
    ("partial year without the partial mention",
     lambda d: d.update(notes=[n for n in d["notes"] if "volume partiel" not in n]), r"notes"),
    ("roots without the roots mention",
     lambda d: d.update(notes=[n for n in d["notes"] if "racines" not in n]), r"notes"),
    ("note per year", lambda d: year(d).update(notes=["provisoire"]), r"notes"),
    # volume et carbone
    ("volume missing", lambda d: year(d).pop("volume_m3_ha"), r"volume_m3_ha"),
    ("volume negative", lambda d: year(d).update(volume_m3_ha=-1.0), r"volume_m3_ha"),
    ("volume null although something is computed",
     lambda d: year(d).update(volume_m3_ha=None), r"volume_m3_ha"),
    ("carbon null although something is computed",
     lambda d: year(d).update(carbon_t_ha=None), r"carbon_t_ha"),
    ("carbon missing", lambda d: year(d).pop("carbon_t_ha"), r"carbon_t_ha"),
    ("volume above 7 cm added", lambda d: year(d).update(volume_sup7_m3_ha=100.0),
     r"volume_sup7_m3_ha"),
    ("total volume added next to the volume", lambda d: year(d).update(volume_total_m3_ha=100.0),
     r"volume_total_m3_ha"),
    ("co2 added", lambda d: year(d).update(co2_t_ha=300.0), r"co2_t_ha"),
    ("soil carbon added", lambda d: year(d).update(soil_carbon_t_ha=10.0), r"soil_carbon_t_ha"),
    # racines
    ("roots negative", lambda d: year(d).update(root_carbon_t_ha=-1.0), r"root_carbon_t_ha"),
    ("roots on a non provisional year", lambda d: year(d).update(provisoire=False),
     r"provisoire"),
    ("roots null although something is computed",
     lambda d: year(d).update(root_carbon_t_ha=None), r"root_carbon_t_ha"),
    # part non calculée et volume partiel
    ("partial share missing", lambda d: year(d).pop("basal_area_not_computed_share"),
     r"basal_area_not_computed_share"),
    ("partial share above one",
     lambda d: year(d).update(basal_area_not_computed_share=1.5),
     r"basal_area_not_computed_share"),
    ("partial share negative",
     lambda d: year(d).update(basal_area_not_computed_share=-0.1),
     r"basal_area_not_computed_share"),
    ("stems not computed missing", lambda d: year(d).pop("stems_not_computed_ha"),
     r"stems_not_computed_ha"),
    ("stems not computed negative", lambda d: year(d).update(stems_not_computed_ha=-1.0),
     r"stems_not_computed_ha"),
    ("volume_partiel missing", lambda d: year(d).pop("volume_partiel"), r"volume_partiel"),
    ("volume_partiel false with a share above 0",
     lambda d: year(d, 1).update(volume_partiel=False), r"volume_partiel"),
    ("volume_partiel true with a share of 0",
     lambda d: year(d, 0).update(volume_partiel=True), r"volume_partiel"),
    ("nothing computed but a volume written",
     lambda d: year(d, 1).update(basal_area_not_computed_share=1.0, volume_partiel=True,
                                 not_computed_reason="rien", carbon_t_ha=None,
                                 root_carbon_t_ha=None),
     r"volume_m3_ha"),
    ("nothing computed but a zero instead of null",
     lambda d: year(d, 1).update(basal_area_not_computed_share=1.0, volume_partiel=True,
                                 not_computed_reason="rien", volume_m3_ha=0.0,
                                 carbon_t_ha=0.0, root_carbon_t_ha=0.0), r"volume_m3_ha"),
    ("nothing computed without its reason",
     lambda d: year(d, 1).update(basal_area_not_computed_share=1.0, volume_partiel=True,
                                 volume_m3_ha=None, carbon_t_ha=None, root_carbon_t_ha=None),
     r"not_computed_reason"),
    ("reason empty",
     lambda d: year(d, 1).update(basal_area_not_computed_share=1.0, volume_partiel=True,
                                 volume_m3_ha=None, carbon_t_ha=None, root_carbon_t_ha=None,
                                 not_computed_reason=""), r"not_computed_reason"),
    # composition
    ("composition without volume", lambda d: year(d)["composition"][0].pop("volume_m3_ha"),
     r"volume_m3_ha"),
    ("composition without carbon", lambda d: year(d)["composition"][0].pop("carbon_t_ha"),
     r"carbon_t_ha"),
    ("composition without its share",
     lambda d: year(d)["composition"][0].pop("basal_area_not_computed_share"),
     r"basal_area_not_computed_share"),
    ("composition volume negative",
     lambda d: year(d)["composition"][0].update(volume_m3_ha=-2.0), r"volume_m3_ha"),
    ("composition share above one",
     lambda d: year(d)["composition"][0].update(basal_area_not_computed_share=2.0),
     r"basal_area_not_computed_share"),
    # ce que la v2 exigeait reste exigé
    ("h_dom_m missing", lambda d: year(d).pop("h_dom_m"), r"h_dom_m"),
    ("flags missing", lambda d: year(d).pop("flags"), r"flags"),
    ("provisoire missing", lambda d: year(d).pop("provisoire"), r"provisoire"),
    ("h_ceiling_m missing", lambda d: d["cells"][0].pop("h_ceiling_m"), r"h_ceiling_m"),
    ("x and y inverted", lambda d: d["cells"][0].update(x=h.PARIS_Y, y=h.PARIS_X), r"inversés"),
]


@pytest.mark.parametrize("change,pattern", [c[1:] for c in V3_FAULTS], ids=[c[0] for c in V3_FAULTS])
def test_cell_sheet_v3_faults_are_refused(change, pattern, capsys, tmp_path):
    code, out = sheet_check(capsys, tmp_path, change)
    assert code == 3 and re.search(pattern, out), out


def test_cell_sheet_v3_key_of_the_old_density_is_refused(capsys, tmp_path):
    code, out = sheet_check(capsys, tmp_path, lambda d: year(d).update(density_trees_ha=1.0))
    assert code == 3 and "density_trees_ha" in out, out


# ------------------------------------------------------------------ v1 et v2 restent conformes

def test_v1_and_v2_sheets_stay_conform(capsys, tmp_path):
    for name, factory in (("v1", h.cell_sheet), ("v2", h.cell_sheet_v2)):
        path = h.write_json(tmp_path / f"{name}.json", factory())
        code, out = run(capsys, ["cell_sheet", str(path)])
        assert code == 0, (name, out)


def test_v2_still_requires_its_own_mention_and_null_volume(capsys, tmp_path):
    """La v3 n'a pas affaibli la v2 : « volume et carbone non calculés » reste exigé, volume null."""
    sheet = h.cell_sheet_v2()
    sheet["notes"] = ["non validée écologiquement", "volume aérien total", "carbone aérien",
                      "sol et bois mort"]
    code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "a.json", sheet))])
    assert code == 3 and "notes" in out, out
    sheet = h.cell_sheet_v2()
    sheet["cells"][0]["years"][0]["volume_m3_ha"] = 300.0
    code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "b.json", sheet))])
    assert code == 3 and "volume_m3_ha" in out, out


@pytest.mark.parametrize("key,value", [
    ("tarif", {"name": "x", "commit": "0000000", "provisoire": True})])
def test_v2_and_v1_refuse_the_keys_of_v3(key, value, capsys, tmp_path):
    for factory in (h.cell_sheet, h.cell_sheet_v2):
        sheet = factory()
        sheet[key] = value
        code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "t.json", sheet))])
        assert code == 3 and key in out, out


@pytest.mark.parametrize("key,value", [
    ("stems_not_computed_ha", 1.0), ("basal_area_not_computed_share", 0.0),
    ("volume_partiel", False), ("root_carbon_t_ha", 1.0)])
def test_v2_refuses_the_year_keys_of_v3(key, value, capsys, tmp_path):
    sheet = h.cell_sheet_v2()
    sheet["cells"][0]["years"][0][key] = value
    code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "t.json", sheet))])
    assert code == 3 and key in out, out


def test_version_3_is_the_last_known(capsys, tmp_path):
    sheet = h.cell_sheet_v3()
    sheet["schema_version"] = 4
    code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "t.json", sheet))])
    assert code == 3 and "schema_version" in out, out
