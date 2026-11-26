"""Contrats de M6a : arbres du générateur et vue massif (mission 068 ; plan m6a §3 ligne B, §4 ; ADR 0007 projet).

Chaque règle nouvelle a un cas conforme et un cas fautif : `.glb` (conteneur, accesseurs, trois
niveaux de détail par MSFT_lod, repère y-up, extras dont `source_commit`, nom, alias, générique),
`massif_block` version 2, `massif/index.json`, exemplaires Parquet (repère z-up dit),
`params/model_dimensions.csv`, seuils des stades, blocs `assets.models` et `viewer` de `config.yml`.
Les valeurs sont celles d'un essai : aucune n'a de sens écologique.
"""
import copy
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

import helpers as h
from validator import catalog, cli

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def refused(capsys, name, path, pattern):
    code, out = run(capsys, [name, str(path)])
    assert code == 3, out
    assert re.search(pattern, out), out


def accepted(capsys, name, path):
    code, out = run(capsys, [name, str(path)])
    assert code == 0, out


# ============================================================================ .glb

def tree(tmp, name="09_mature.glb", **kw):
    return h.glb(tmp / name, **kw)


def test_glb_conform_with_three_levels(tmp_path, capsys):
    accepted(capsys, "tree_model", tree(tmp_path))


def test_glb_truncated_in_the_binary_block_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, truncate=40), r"tronqué")


def test_glb_truncated_by_a_few_bytes_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, truncate=3), r"tronqué|longueur déclarée")


def test_glb_without_binary_block_is_refused(tmp_path, capsys):
    path = h.glb(tmp_path / "09_mature.glb")
    data = path.read_bytes()
    json_end = 20 + int.from_bytes(data[12:16], "little")
    import struct
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, json_end) + data[12:json_end])
    refused(capsys, "tree_model", path, r"bloc binaire|BIN")


def drop_lod2(gltf):
    gltf["nodes"][0]["extensions"]["MSFT_lod"]["ids"] = [1]


def test_glb_without_lod2_node_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, mutate=drop_lod2), r"LOD2")


def test_glb_with_only_two_meshes_is_refused(tmp_path, capsys):
    def two_levels(gltf):
        gltf["nodes"][0]["extensions"]["MSFT_lod"]["ids"] = [1, 7]
    refused(capsys, "tree_model", tree(tmp_path, mutate=two_levels), r"MSFT_lod\.ids")


def test_glb_without_the_extension_declared_is_refused(tmp_path, capsys):
    def undeclared(gltf):
        del gltf["extensionsUsed"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=undeclared), r"extensionsUsed")


def test_glb_without_lod_node_at_all_is_refused(tmp_path, capsys):
    def no_lod(gltf):
        del gltf["nodes"][0]["extensions"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_lod), r"un seul nœud principal")


def test_glb_triangles_must_decrease(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, counts=(6, 12, 2)), r"strictement décroissants")


def test_glb_screencoverage_must_decrease(tmp_path, capsys):
    def wrong(gltf):
        gltf["nodes"][0]["extras"]["MSFT_screencoverage"] = [0.05, 0.3, 0.005]
    refused(capsys, "tree_model", tree(tmp_path, mutate=wrong), r"MSFT_screencoverage")


def test_glb_without_screencoverage_is_refused(tmp_path, capsys):
    def none(gltf):
        del gltf["nodes"][0]["extras"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=none), r"MSFT_screencoverage")


def test_glb_without_source_commit_is_refused(tmp_path, capsys):
    def no_commit(gltf):
        del gltf["extras"]["source_commit"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_commit), r"extras\.source_commit")


def test_glb_without_any_extras_is_refused(tmp_path, capsys):
    def no_extras(gltf):
        del gltf["extras"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_extras), r"extras")


@pytest.mark.parametrize("key, value", [("synthetique", False), ("provisoire", False),
                                        ("source_commit", "pas-un-commit"), ("D_cm", -1),
                                        ("stage", "adulte"), ("graine", 1.5),
                                        ("feuillage", {"type": "photo", "couleur": "#4f7a32"})])
def test_glb_extras_values_are_checked(tmp_path, capsys, key, value):
    def bad(gltf):
        gltf["extras"][key] = value
    refused(capsys, "tree_model", tree(tmp_path, mutate=bad), key)


def test_glb_conifer_not_calibrated_without_b_cible_is_accepted(tmp_path, capsys):
    """Résineux du générateur : « non calé », raisons en liste, sans b_cible (comme exemplars)."""
    def not_calibrated(gltf):
        del gltf["extras"]["b_cible"]
        gltf["extras"]["calage"] = "non calé"
        gltf["extras"]["calage_raisons"] = ["densité des rameaux tirée", "stades jeune et perche extrapolés"]
    accepted(capsys, "tree_model", tree(tmp_path, "61_mature.glb", species="61", mutate=not_calibrated))


def test_glb_not_calibrated_reason_may_be_a_string(tmp_path, capsys):
    def not_calibrated(gltf):
        gltf["extras"]["calage"] = "non calé"
        gltf["extras"]["calage_raisons"] = "densité des rameaux tirée"
    accepted(capsys, "tree_model", tree(tmp_path, "61_mature.glb", species="61", mutate=not_calibrated))


def test_glb_calage_outside_enumeration_is_refused(tmp_path, capsys):
    def bad(gltf):
        gltf["extras"]["calage"] = "peut-être"
    refused(capsys, "tree_model", tree(tmp_path, mutate=bad), r"calage")


def test_glb_generator_model_without_calage_is_refused(tmp_path, capsys):
    def no_calage(gltf):
        del gltf["extras"]["calage"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_calage), r"calage")


def test_glb_calibrated_without_b_cible_is_refused(tmp_path, capsys):
    def no_b(gltf):
        del gltf["extras"]["b_cible"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_b), r"b_cible")


def test_glb_generic_model_with_calage_is_refused(tmp_path, capsys):
    def with_calage(gltf):
        gltf["extras"]["calage"] = "non calé"
    refused(capsys, "tree_model", h.generic_glb(tmp_path / "generique_resineux.glb", "resineux",
                                                mutate=with_calage), r"calage")


def test_glb_unknown_extras_key_is_refused(tmp_path, capsys):
    def extra(gltf):
        gltf["extras"]["foret"] = "x"
    refused(capsys, "tree_model", tree(tmp_path, mutate=extra), r"clé inconnue.*foret")


def test_glb_height_must_match_h_ref(tmp_path, capsys):
    """Repère y-up (plan T6) : le LOD0 va de 0 à H_ref_m, à 1 % près."""
    def other_height(gltf):
        gltf["extras"]["H_ref_m"] = 30.0
    refused(capsys, "tree_model", tree(tmp_path, mutate=other_height), r"repère y-up")


def test_glb_height_within_one_percent_is_accepted(tmp_path, capsys):
    def near(gltf):
        gltf["extras"]["H_ref_m"] = 25.2   # 0,8 % d'écart
    accepted(capsys, "tree_model", tree(tmp_path, mutate=near))


def test_glb_with_a_non_finite_vertex_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, binary_nan=True), r"non fini")


def test_glb_position_without_min_max_is_refused(tmp_path, capsys):
    def no_bounds(gltf):
        del gltf["accessors"][0]["min"]
    refused(capsys, "tree_model", tree(tmp_path, mutate=no_bounds), r"min et max")


def test_glb_accessor_beyond_its_view_is_refused(tmp_path, capsys):
    def too_many(gltf):
        gltf["accessors"][2]["count"] = 9999
    refused(capsys, "tree_model", tree(tmp_path, mutate=too_many), r"demandent")


def test_glb_with_an_external_uri_buffer_is_refused(tmp_path, capsys):
    def uri(gltf):
        gltf["buffers"][0]["uri"] = "arbre.bin"
    refused(capsys, "tree_model", tree(tmp_path, mutate=uri), r"uri")


# ---------------------------------------------------------------- nom, alias, générique

def test_alias_code_has_no_file_of_its_own(tmp_path, capsys):
    """02 et 03 sont la même essence (Quercus_spec) : le fichier est 02_<stade>.glb, pas 03_."""
    accepted(capsys, "tree_model", tree(tmp_path, "02_mature.glb", species="02"))
    refused(capsys, "tree_model", tree(tmp_path, "03_mature.glb", species="03"),
            r"alias de 02.*pas de doublon")


def test_second_betula_code_is_an_alias_too(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "12V_pole.glb", species="12V", stage="pole"),
            r"alias de 12P")


def test_species_without_generator_model_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "10_mature.glb", species="10"),
            r"pas de modèle propre.*pas d'emprunt")


def test_unknown_espar_code_is_refused(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "99_mature.glb", species="99"),
            r"pas de modèle propre")


def test_extras_must_repeat_the_name(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "09_old.glb", stage="mature"), r"extras\.stage")
    refused(capsys, "tree_model", tree(tmp_path, "61_mature.glb", species="09"), r"extras\.species")


def test_essence_of_the_generator_must_match_species_csv(tmp_path, capsys):
    def borrowed(gltf):
        gltf["extras"]["essence_generateur"] = "Picea_abies"   # un hêtre dessiné avec l'essence d'un épicéa
    refused(capsys, "tree_model", tree(tmp_path, mutate=borrowed), r"extras\.essence_generateur")


def test_stage_must_be_in_the_enumeration(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "09_adulte.glb"), r"stade parmi")


@pytest.mark.parametrize("group", ["feuillu", "resineux"])
def test_generic_model_is_accepted(tmp_path, capsys, group):
    accepted(capsys, "tree_model", h.generic_glb(tmp_path / f"generique_{group}.glb", group))


def test_generic_model_needs_its_flag_and_group(tmp_path, capsys):
    refused(capsys, "tree_model", tree(tmp_path, "generique_feuillu.glb"), r"générique|generique")
    refused(capsys, "tree_model", h.generic_glb(tmp_path / "generique_resineux.glb", "feuillu"),
            r"extras\.groupe")


def test_generic_model_must_have_three_levels_too(tmp_path, capsys):
    refused(capsys, "tree_model",
            h.generic_glb(tmp_path / "generique_feuillu.glb", mutate=drop_lod2), r"LOD2")


# ======================================================================= massif_block

def block_v2():
    block = h.massif_block()
    block.update(
        schema_version=2, block_id="t_652000_6862000",
        ground={"resolution_m": 25, "nx": 3, "ny": 2, "z": [35.0, 35.5, 36.0, 34.0, 34.5, 35.0]},
        cells=[{"cell_id": 0, "x": 12.5, "y": 12.5, "biome": "type_frais_futaie_fictive_mature",
                "biome_provisoire": True, "herb_cover": 0.3, "shrub_cover": 0.15,
                "seedlings": [{"species": "09", "seedlings_ha": 1200.0, "h_mean_m": 0.4}]},
               {"cell_id": 1, "x": 37.5, "y": 12.5, "biome": None, "biome_provisoire": True,
                "herb_cover": None, "shrub_cover": None, "seedlings": []}],
        seedlings_simulated=True,
        mentions=["trajectoire technique, non validée écologiquement", "jeu fictif"],
        provisoire=True)
    return block


def drop_seedlings(block):
    block["seedlings_simulated"] = False
    for cell in block["cells"]:
        del cell["seedlings"]
    return block


def test_massif_block_v1_stays_conform(tmp_path, capsys):
    accepted(capsys, "massif_block", h.write_json(tmp_path / "b.json", h.massif_block()))


def test_massif_block_v2_conform_with_cohorts(tmp_path, capsys):
    accepted(capsys, "massif_block", h.write_json(tmp_path / "b.json", block_v2()))


def test_massif_block_v2_conform_without_cohorts(tmp_path, capsys):
    accepted(capsys, "massif_block", h.write_json(tmp_path / "b.json", drop_seedlings(block_v2())))


def test_massif_block_v2_fault_cases(tmp_path, capsys):
    def faulty(mutate, pattern, name):
        block = block_v2()
        mutate(block)
        refused(capsys, "massif_block", h.write_json(tmp_path / f"{name}.json", block), pattern)

    faulty(lambda b: b.pop("ground"), r"clé obligatoire absente : ground", "no_ground")
    faulty(lambda b: b.pop("cells"), r"cells", "no_cells")
    faulty(lambda b: b.pop("mentions"), r"mentions", "no_mentions")
    faulty(lambda b: b.pop("provisoire"), r"provisoire", "no_provisoire")
    faulty(lambda b: b.pop("seedlings_simulated"), r"seedlings_simulated", "no_flag")
    faulty(lambda b: b["ground"].update(resolution_m=30), r"resolution_m", "resolution")
    faulty(lambda b: b["ground"].update(nx=1), r"nx", "nx")
    faulty(lambda b: b["cells"][0].update(herb_cover=1.5), r"herb_cover", "cover")
    faulty(lambda b: b["cells"][0].update(shrub_cover=-0.1), r"shrub_cover", "shrub")
    faulty(lambda b: b["cells"][0].update(biome="Biome Inconnu"), r"biome", "biome")
    faulty(lambda b: b["cells"][0]["seedlings"][0].update(h_mean_m=0), r"h_mean_m", "height")
    faulty(lambda b: b["cells"][0].update(composition_herbacee={"a": 1}), r"clé inconnue", "herb")
    faulty(lambda b: b.update(mentions=["jeu fictif"]), r"mentions", "mention_text")
    faulty(lambda b: b["trees"][0].update(stage="adulte"), r"stage", "stage")


def test_massif_block_ground_size_is_checked(tmp_path, capsys):
    block = block_v2()
    block["ground"]["z"].pop()
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block), r"ground\.z : 5 altitudes")


def test_seedlings_are_present_if_and_only_if_simulated(tmp_path, capsys):
    block = block_v2()
    del block["cells"][1]["seedlings"]
    refused(capsys, "massif_block", h.write_json(tmp_path / "a.json", block), r"seedlings")
    block = drop_seedlings(block_v2())
    block["cells"][0]["seedlings"] = []
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block),
            r"cells\.0\.seedlings : clé non admise")


def test_v1_block_refuses_the_keys_of_v2(tmp_path, capsys):
    block = h.massif_block()
    block["ground"] = block_v2()["ground"]
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block), r"clé inconnue.*ground")


def test_unknown_schema_version_is_refused(tmp_path, capsys):
    block = block_v2()
    block["schema_version"] = 3
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block), r"schema_version")


# ======================================================================= massif_index

def massif_index():
    def year(y, own, alias, generic):
        total = own + alias + generic
        return {"year": y, "trees": total,
                "trees_by_kind": {"own": own, "alias": alias, "generic": generic},
                "blocks": [{"block_id": "t_652000_6862000", "file": f"{y}/t_652000_6862000.json",
                            "sw": {"x": h.PARIS_X, "y": h.PARIS_Y}, "size_m": 500, "trees": total}]}
    return {"schema_version": 1, "zone": "zone_fictive", "fictive": True, "crs": "EPSG:2154",
            "vertical_datum": "NGF-IGN69", "source": "sim", "block_size_m": 500,
            "recruitment": "ifn_direct", "provisoire": True,
            "notes": ["trajectoire technique, non validée écologiquement", "semis non simulés"],
            "models": [{"species": "09", "model": "09", "kind": "own"},
                       {"species": "03", "model": "02", "kind": "alias", "alias_of": "02"},
                       {"species": "10", "model": "generique_feuillu", "kind": "generic"}],
            "years": [year(2022, 90, 6, 4), year(2032, 80, 5, 3)]}


def test_massif_index_conform(tmp_path, capsys):
    accepted(capsys, "massif_index", h.write_json(tmp_path / "index.json", massif_index()))


def test_massif_index_trees_init_mode_conform(tmp_path, capsys):
    index = massif_index()
    index.update(source="trees_init")
    del index["recruitment"]
    index["years"] = index["years"][:1]
    accepted(capsys, "massif_index", h.write_json(tmp_path / "index.json", index))


@pytest.mark.parametrize("name, mutate, pattern", [
    ("alias_without_target", lambda i: i["models"][1].pop("alias_of"), r"alias_of"),
    ("own_with_target", lambda i: i["models"][0].update(alias_of="02"), r"alias_of"),
    ("generic_borrowed", lambda i: i["models"][2].update(model="09"), r"model"),
    ("generic_unknown_group", lambda i: i["models"][2].update(model="generique_arbuste"), r"model"),
    ("unknown_kind", lambda i: i["models"][0].update(kind="emprunt"), r"kind"),
    ("sim_without_mode", lambda i: i.pop("recruitment"), r"recruitment"),
    ("bad_mode", lambda i: i.update(recruitment="aleatoire"), r"recruitment"),
    ("no_counts_by_kind", lambda i: i["years"][0].pop("trees_by_kind"), r"trees_by_kind"),
    ("missing_generic_count", lambda i: i["years"][0]["trees_by_kind"].pop("generic"), r"generic"),
    ("bad_file", lambda i: i["years"][0]["blocks"][0].update(file="t_1_2.json"), r"file"),
    ("bad_block_id", lambda i: i["years"][0]["blocks"][0].update(block_id="bloc1"), r"block_id"),
    ("sw_swapped", lambda i: i["years"][0]["blocks"][0].update(sw={"x": h.PARIS_Y, "y": h.PARIS_X}),
     r"inversés"),
    ("no_mention", lambda i: i.update(notes=["jeu fictif"]), r"notes"),
    ("no_blocks", lambda i: i["years"][0].update(blocks=[]), r"blocks"),
    ("unknown_key", lambda i: i.update(composition_herbacee=1), r"clé inconnue"),
])
def test_massif_index_faults(tmp_path, capsys, name, mutate, pattern):
    index = massif_index()
    mutate(index)
    refused(capsys, "massif_index", h.write_json(tmp_path / "index.json", index), pattern)


def test_trees_init_index_refuses_a_recruitment_mode(tmp_path, capsys):
    index = massif_index()
    index["source"] = "trees_init"
    refused(capsys, "massif_index", h.write_json(tmp_path / "index.json", index),
            r"recruitment : clé non admise")


# ========================================================================== exemplaires

def exemplar(tmp, name="Fagus_sylvatica_mature.parquet", metadata=None, columns=None):
    meta = {"frame": "z-up", "units": "m", "essence": "Fagus_sylvatica", "stage": "mature",
            "D_cm": "40.0", "H_m": "28.0", "hbh_m": "12.6", "Rh_m": "5.6", "b_cible": "1.8",
            "seed": "1", "source_commit": "4ee122c", "synthetic": "true"}
    meta.update(metadata or {})
    meta = {k: v for k, v in meta.items() if v is not None}
    # tige verticale (z), une branche vers l'est (x) : cas asymétrique, x != y
    data = columns or {
        "x0": [0.0, 0.0], "y0": [0.0, 0.0], "z0": [0.0, 12.6],
        "x1": [0.0, 3.0], "y1": [0.0, 1.0], "z1": [28.0, 14.0],
        "r0_m": [0.2, 0.04], "r1_m": [0.01, 0.01], "niveau": [0, 1], "axe": [0, 1]}
    table = pa.table(data).replace_schema_metadata(meta)
    path = Path(tmp) / name
    pq.write_table(table, path)
    return path


def test_exemplar_conform(tmp_path, capsys):
    accepted(capsys, "exemplars", exemplar(tmp_path))


def test_exemplar_with_optional_column_conform(tmp_path, capsys):
    columns = {"x0": [0.0], "y0": [0.0], "z0": [0.0], "x1": [0.0], "y1": [0.0], "z1": [1.0],
               "r0_m": [0.1], "r1_m": [0.05], "niveau": [-1], "axe": [0], "racine_niveau1": [3]}
    accepted(capsys, "exemplars", exemplar(tmp_path, columns=columns))


@pytest.mark.parametrize("metadata, pattern", [
    ({"frame": "y-up"}, r"frame.*z-up"),
    ({"frame": None}, r"métadonnée Parquet obligatoire absente.*frame"),
    ({"source_commit": None}, r"source_commit"),
    ({"units": "cm"}, r"units"),
    ({"stage": "adulte"}, r"stage"),
    ({"D_cm": "-3"}, r"D_cm"),
    ({"H_m": "grand"}, r"H_m"),
    ({"b_cible": "nan"}, r"b_cible"),
    ({"seed": "1.5"}, r"seed"),
    ({"synthetic": "false"}, r"synthetic"),
])
def test_exemplar_metadata_faults(tmp_path, capsys, metadata, pattern):
    refused(capsys, "exemplars", exemplar(tmp_path, metadata=metadata), pattern)


def test_exemplar_not_calibrated_without_b_cible_conform(tmp_path, capsys):
    """Résineux : aucun b observé, b_cible absent, dit « non calé »."""
    meta = {"b_cible": None, "calage": "non calé", "calage_raisons": "densité des rameaux tirée"}
    accepted(capsys, "exemplars", exemplar(tmp_path, name="Picea_abies_mature.parquet",
                                           metadata=dict(meta, essence="Picea_abies")))


def test_exemplar_calibrated_with_b_cible_conform(tmp_path, capsys):
    accepted(capsys, "exemplars", exemplar(tmp_path, metadata={"calage": "calé"}))


@pytest.mark.parametrize("metadata, pattern", [
    ({"b_cible": None}, r"obligatoire absente.*b_cible"),                       # feuillu sans b_cible
    ({"b_cible": None, "calage": "calé"}, r"obligatoire absente.*b_cible"),    # « calé » sans b_cible
    ({"b_cible": "nan", "calage": "non calé"}, r"b_cible.*fini"),              # jamais NaN
    ({"calage": "peut-être"}, r"calage.*liste fermée"),
])
def test_exemplar_b_cible_rule_faults(tmp_path, capsys, metadata, pattern):
    refused(capsys, "exemplars", exemplar(tmp_path, metadata=metadata), pattern)


def test_exemplar_name_must_follow_its_metadata(tmp_path, capsys):
    refused(capsys, "exemplars", exemplar(tmp_path, name="Fagus_sylvatica_old.parquet"),
            r"Fagus_sylvatica_mature\.parquet attendu")


def test_exemplar_without_metadata_at_all_is_refused(tmp_path, capsys):
    path = tmp_path / "Fagus_sylvatica_mature.parquet"
    pq.write_table(pa.table({"x0": [0.0], "y0": [0.0], "z0": [0.0], "x1": [0.0], "y1": [0.0],
                             "z1": [1.0], "r0_m": [0.1], "r1_m": [0.1], "niveau": [0], "axe": [0]}), path)
    refused(capsys, "exemplars", path, r"frame")


@pytest.mark.parametrize("column, value, pattern", [
    ("r0_m", [-0.1, 0.04], r"r0_m"),
    ("niveau", [-2, 1], r"niveau"),
    ("axe", [0, -1], r"axe"),
    ("z1", [28.0, float("nan")], r"NaN|finie|z1"),
])
def test_exemplar_column_faults(tmp_path, capsys, column, value, pattern):
    columns = {"x0": [0.0, 0.0], "y0": [0.0, 0.0], "z0": [0.0, 12.6], "x1": [0.0, 3.0],
               "y1": [0.0, 1.0], "z1": [28.0, 14.0], "r0_m": [0.2, 0.04], "r1_m": [0.01, 0.01],
               "niveau": [0, 1], "axe": [0, 1]}
    columns[column] = value
    refused(capsys, "exemplars", exemplar(tmp_path, columns=columns), pattern)


def test_exemplar_missing_column_is_refused(tmp_path, capsys):
    columns = {"x0": [0.0], "y0": [0.0], "z0": [0.0], "x1": [0.0], "y1": [0.0], "z1": [1.0],
               "r0_m": [0.1], "r1_m": [0.1], "niveau": [0]}
    refused(capsys, "exemplars", exemplar(tmp_path, columns=columns), r"axe")


def test_exemplar_stage_list_is_the_enumeration():
    schema = json.loads((CONTRACTS / "tables/assets/exemplars.schema.json").read_text(encoding="utf-8"))
    stages = json.loads((CONTRACTS / "json/enums/stage.json").read_text(encoding="utf-8"))["enum"]
    assert schema["x-metadata"]["enum"]["stage"] == stages
    dims = json.loads((CONTRACTS / "tables/params/model_dimensions.schema.json").read_text(encoding="utf-8"))
    assert [f for f in dims["fields"] if f["name"] == "stage"][0]["constraints"]["enum"] == stages


# ================================================================== model_dimensions.csv

HEADER = ["essence", "stage", "term", "value", "unit", "provisoire", "source"]


def dimensions(tmp, rows):
    return h.csv(Path(tmp) / "model_dimensions.csv", HEADER, rows)


GOOD_ROWS = [["Fagus_sylvatica", "mature", "H_m", 20.0, "m", "true", "valeur d'essai"],
             ["Fagus_sylvatica", "mature", "D_cm", 35.0, "cm", "true", "valeur d'essai"]]


def test_model_dimensions_conform(tmp_path, capsys):
    accepted(capsys, "model_dimensions", dimensions(tmp_path, GOOD_ROWS))


@pytest.mark.parametrize("row, pattern", [
    (["Fagus_sylvatica", "mature", "H_m", 20.0, "m", "true", ""], r"source"),
    (["Fagus_sylvatica", "mature", "age", 20.0, "m", "true", "x"], r"term"),
    (["Fagus_sylvatica", "adulte", "H_m", 20.0, "m", "true", "x"], r"stage"),
    (["hetre", "mature", "H_m", 20.0, "m", "true", "x"], r"essence"),
    (["Fagus_sylvatica", "mature", "H_m", 20.0, "pieds", "true", "x"], r"unit"),
    (["Fagus_sylvatica", "mature", "H_m", 20.0, "m", "", "x"], r"provisoire"),
])
def test_model_dimensions_faults(tmp_path, capsys, row, pattern):
    refused(capsys, "model_dimensions", dimensions(tmp_path, [row]), pattern)


def test_model_dimensions_duplicate_key_is_refused(tmp_path, capsys):
    refused(capsys, "model_dimensions", dimensions(tmp_path, GOOD_ROWS + [GOOD_ROWS[0]]),
            r"doublon|unique")


def test_no_values_file_is_written_by_this_mission():
    """Le contrat n'a aucune valeur : le fichier de repli reste à sourcer (Q6)."""
    assert not (ROOT / "params" / "model_dimensions.csv").exists()


# ========================================================================= seuils des stades

STAGE_BREAKS = CONTRACTS.parent / "biomes" / "stades" / "stage_breaks.yml"


def breaks_document():
    return yaml.safe_load(STAGE_BREAKS.read_text(encoding="utf-8"))


def test_stage_breaks_file_is_conform(capsys):
    accepted(capsys, "stage_breaks", STAGE_BREAKS)


def test_stage_breaks_file_is_not_a_biome():
    """biomes/*.yml est lu tout entier par R (read_biome_catalog) : le fichier est dans un sous-dossier."""
    assert STAGE_BREAKS.parent != ROOT / "biomes"
    assert not list((ROOT / "biomes").glob("*stage*"))


def test_stage_breaks_are_those_of_r_biomes():
    """Mêmes valeurs que BIOMES_STAGE_BREAKS (R/biomes.R) tant que R n'a pas repris le fichier :
    aucun résultat ne change."""
    text = (ROOT / "R" / "biomes.R").read_text(encoding="utf-8")
    found = re.search(r"BIOMES_STAGE_BREAKS\s*<-\s*c\(([^)]*)\)", text)
    assert found, "BIOMES_STAGE_BREAKS introuvable dans R/biomes.R"
    in_r = [float(v) for v in found.group(1).split(",")]
    assert in_r == breaks_document()["breaks"]


def test_stage_breaks_stages_are_the_enumeration():
    stages = json.loads((CONTRACTS / "json/enums/stage.json").read_text(encoding="utf-8"))["enum"]
    assert breaks_document()["stages"] == stages


def write_breaks(tmp, mutate):
    document = breaks_document()
    mutate(document)
    return h.write_yaml(Path(tmp) / "stage_breaks.yml", document)


@pytest.mark.parametrize("mutate, pattern", [
    (lambda d: d.update(breaks=[0.6, 0.25, 0.9]), r"strictement croissants"),
    (lambda d: d.update(breaks=[0.25, 0.25, 0.9]), r"strictement croissants"),
    (lambda d: d.update(breaks=[0.25, 0.9]), r"breaks"),
    (lambda d: d.update(breaks=[0.0, 0.5, 0.9]), r"breaks"),
    (lambda d: d.update(stages=["young", "pole", "mature", "adulte"]), r"stages"),
    (lambda d: d.update(source=""), r"source"),
    (lambda d: d.pop("provisoire"), r"provisoire"),
    (lambda d: d.update(ratio="H0 / h_pot"), r"ratio"),
])
def test_stage_breaks_faults(tmp_path, capsys, mutate, pattern):
    refused(capsys, "stage_breaks", write_breaks(tmp_path, mutate), pattern)


def test_stage_of_ratio_follows_the_file_like_r():
    """Règle de lecture écrite dans le contrat : borne basse incluse, comme findInterval de R."""
    import bisect
    document = breaks_document()
    stage = lambda ratio: document["stages"][bisect.bisect_right(document["breaks"], ratio)]
    assert [stage(r) for r in (0.0, 0.24, 0.25, 0.59, 0.60, 0.89, 0.90, 1.2)] == \
        ["young", "young", "pole", "pole", "mature", "mature", "old", "old"]


# ===================================================================== config.yml : M6a

def real_config():
    return yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))


def config_file(tmp, mutate=None):
    config = real_config()
    if mutate:
        mutate(config)
    return h.write_yaml(Path(tmp) / "config.yml", config)


def test_real_config_has_the_display_blocks_marked_provisional(capsys):
    config = real_config()
    assert config["viewer"]["provisoire"] is True
    assert "illustration, non mesurée" in config["viewer"]["mention"]
    assert config["assets"]["models"]["provisoire"] is True
    accepted(capsys, "config", ROOT / "config.yml")


def test_no_dendrometric_value_in_the_display_blocks():
    """Q6 : D, H, hbh, Rh, b_cible ne sont pas des réglages d'affichage."""
    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from keys(v)
    found = set(keys([real_config()["viewer"], real_config()["assets"]["models"]]))
    assert not found & {"D_cm", "H_m", "hbh_m", "Rh_m", "b_cible", "D", "H"}


@pytest.mark.parametrize("name, mutate, pattern", [
    ("no_lod2_budget", lambda c: c["assets"]["models"]["triangle_budgets"].pop("lod2"), r"lod2"),
    ("zero_budget", lambda c: c["assets"]["models"]["triangle_budgets"].update(lod0=0), r"lod0"),
    ("two_coverages", lambda c: c["assets"]["models"].update(screencoverage=[0.3, 0.05]), r"screencoverage"),
    ("coverage_above_one", lambda c: c["assets"]["models"].update(screencoverage=[2.0, 0.05, 0.005]),
     r"screencoverage"),
    ("no_provisoire_models", lambda c: c["assets"]["models"].pop("provisoire"), r"provisoire"),
    ("unknown_models_key", lambda c: c["assets"]["models"].update(hauteur_m=25), r"clé inconnue"),
    ("viewer_without_mention", lambda c: c["viewer"].pop("mention"), r"mention"),
    ("viewer_mention_not_marked", lambda c: c["viewer"].update(mention="herbe verte"), r"mention"),
    ("viewer_without_provisoire", lambda c: c["viewer"].pop("provisoire"), r"provisoire"),
    ("negative_radius", lambda c: c["viewer"]["grass"].update(radius_m=-1), r"radius_m"),
    ("bad_color", lambda c: c["viewer"]["grass"].update(color="vert"), r"color"),
    ("no_group_color", lambda c: c["viewer"]["foliage"]["color_by_group"].pop("resineux"), r"resineux"),
    ("bad_essence_key", lambda c: c["viewer"]["foliage"].update(color_by_essence={"hetre": "#00ff00"}),
     r"color_by_essence"),
    ("unknown_viewer_key", lambda c: c["viewer"].update(herbes={"a": 1}), r"clé inconnue"),
])
def test_config_m6a_faults(tmp_path, capsys, name, mutate, pattern):
    refused(capsys, "config", config_file(tmp_path, mutate), pattern)


def test_config_accepts_an_exemplars_dir_and_a_colour_per_essence(tmp_path, capsys):
    def more(c):
        c["assets"]["models"]["exemplars_dir"] = "/chemin/vers/exemplaires"
        c["viewer"]["foliage"]["color_by_essence"] = {"Fagus_sylvatica": "#6a8f3a"}
    accepted(capsys, "config", config_file(tmp_path, more))


def test_config_without_the_new_blocks_stays_conform(tmp_path, capsys):
    """Rétrocompatibilité : une config de M5a (sans models ni viewer) reste conforme."""
    def old(c):
        del c["viewer"]
        del c["assets"]["models"]
    accepted(capsys, "config", config_file(tmp_path, old))


# ================================================================== catalogue et zone

def test_new_contracts_are_in_the_catalog():
    names = catalog.names()
    for name in ("assets.exemplars", "assets.massif_index", "params.model_dimensions",
                 "biomes.stage_breaks"):
        assert name in names
    assert catalog.get("assets.massif_block")["paths"] == ["massif/*/*.json"]
    assert catalog.get("assets.massif_index")["paths"] == ["massif/index.json"]


def test_zone_mode_finds_the_massif_files(tmp_path, capsys):
    """Un bloc v2 sous massif/<année>/ et l'index sous massif/ sont contrôlés en mode --zone."""
    zone = tmp_path / "zone"
    (zone / "massif" / "2022").mkdir(parents=True)
    h.write_json(zone / "massif" / "2022" / "t_652000_6862000.json", block_v2())
    h.write_json(zone / "massif" / "index.json", massif_index())
    (zone / "assets" / "trees").mkdir(parents=True)
    h.glb(zone / "assets" / "trees" / "09_mature.glb")
    code, out = run(capsys, ["--zone", str(zone)])
    assert "conforme : " in out and "contrat assets.massif_index" in out
    assert "contrat assets.massif_block" in out and "contrat assets.tree_model" in out
    assert "3 fichier(s) contrôlé(s), 0 non conforme(s)" in out
    assert code == 2, out   # les entrées obligatoires manquent : seul le contrôle des 3 fichiers compte


def test_zone_mode_refuses_a_bad_block(tmp_path, capsys):
    zone = tmp_path / "zone"
    (zone / "massif" / "2022").mkdir(parents=True)
    block = block_v2()
    block["cells"][0]["herb_cover"] = 7
    h.write_json(zone / "massif" / "2022" / "t_652000_6862000.json", block)
    code, out = run(capsys, ["--zone", str(zone)])
    assert code == 3 and "herb_cover" in out, out


def test_schemas_carry_no_default_value():
    """Aucune valeur écologique dans un schéma : pas de `default` dans ceux de M6a."""
    for name in ("json/massif_block.schema.json", "json/massif_index.schema.json",
                 "json/stage_breaks.schema.json", "json/tree_model_extras.schema.json",
                 "tables/assets/exemplars.schema.json", "tables/params/model_dimensions.schema.json"):
        text = (CONTRACTS / name).read_text(encoding="utf-8")
        assert '"default"' not in text, name


# ======================================================================= reprises de 070 : hcb null, assets.gltf (tuiles)

def test_massif_block_v2_hcb_null_is_conform_when_the_block_says_it(tmp_path, capsys):
    block = block_v2()
    block["trees"][0]["hcb"] = None
    block["mentions"].append("hcb absent de trees_init : 1 arbre(s) sans hauteur de base de houppier, hcb écrit null")
    accepted(capsys, "massif_block", h.write_json(tmp_path / "b.json", block))


def test_massif_block_v2_hcb_null_without_a_mention_is_refused(tmp_path, capsys):
    block = block_v2()
    block["trees"][0]["hcb"] = None
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block), r"mentions")


def test_massif_block_v2_hcb_negative_or_text_is_still_refused(tmp_path, capsys):
    for k, value in enumerate((-1.0, "0")):
        block = block_v2()
        block["trees"][0]["hcb"] = value
        refused(capsys, "massif_block", h.write_json(tmp_path / f"{k}.json", block), r"hcb")


def test_massif_block_v1_refuses_a_null_hcb(tmp_path, capsys):
    block = h.massif_block()
    block["trees"][0]["hcb"] = None
    refused(capsys, "massif_block", h.write_json(tmp_path / "b.json", block), r"hcb")


def gltf_tile(models):
    doc = h.gltf_json()
    doc["extras"] = {"generique": any(m.startswith("generique_") for m in models), "provisoire": True,
                     "modeles": models}
    return doc


@pytest.mark.parametrize("models", [["09_mature"], ["09_mature", "61_old"], ["09_mature", "generique_resineux"],
                                    ["generique_feuillu"]])
def test_gltf_tile_conform_cases(tmp_path, capsys, models):
    accepted(capsys, "gltf", h.write_json(tmp_path / "t.gltf", gltf_tile(models)))


def test_gltf_tile_generique_true_without_a_generic_model_is_refused(tmp_path, capsys):
    doc = gltf_tile(["09_mature"])
    doc["extras"]["generique"] = True
    refused(capsys, "gltf", h.write_json(tmp_path / "t.gltf", doc), r"generique")


def test_gltf_tile_generique_false_with_a_generic_model_is_refused(tmp_path, capsys):
    doc = gltf_tile(["09_mature", "generique_resineux"])
    doc["extras"]["generique"] = False
    refused(capsys, "gltf", h.write_json(tmp_path / "t.gltf", doc), r"generique")


def test_gltf_tile_without_the_list_of_models_or_with_a_bad_name_is_refused(tmp_path, capsys):
    doc = gltf_tile(["09_mature"])
    del doc["extras"]["modeles"]
    refused(capsys, "gltf", h.write_json(tmp_path / "a.gltf", doc), r"modeles")
    for k, bad in enumerate(([], ["feuillu"], ["09_adulte"], ["09_mature", "09_mature"])):
        doc = gltf_tile(["09_mature"])
        doc["extras"]["modeles"] = bad
        refused(capsys, "gltf", h.write_json(tmp_path / f"b{k}.gltf", doc), r"modeles")
