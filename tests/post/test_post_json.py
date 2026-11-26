"""sim/post.json : provenance (empreinte de config.yml copiée de run.json, empreintes des entrées, commit du tarif et
source de chaque modèle) et comptes de ce qui n'est pas calculé, par essence et par première raison (contrat post.run ;
décisions Q1 et Q5 du 26/11/2026)."""
import json

import pytest

import helpers_post as P


@pytest.fixture(scope="module")
def pj(base_dir):
    return P.read_post_json(base_dir)


def test_empreinte_de_config_copiee_de_run_json(pj, base, base_dir):
    run = json.loads((base_dir / "sim" / "run.json").read_text(encoding="utf-8"))
    assert pj["run_config_sha256"] == run["config_sha256"] == P.sha256_file(base["config"])


def test_empreintes_des_entrees(pj, base_dir):
    e = pj["inputs_sha256"]
    assert e["sim_run"] == P.sha256_file(base_dir / "sim" / "run.json")
    assert e["params_tarif"] == P.sha256_file(base_dir / "params" / "tarif.parquet")
    assert len(e["sim_trees"]) == 64 and e["sim_trees"] not in (e["sim_run"], e["params_tarif"])


def test_l_empreinte_de_sim_trees_suit_les_arbres_et_pas_le_tarif(ech_dir, ech_metamorphe, base_dir):
    a = P.read_post_json(ech_dir)["inputs_sha256"]
    assert ech_metamorphe["post"].returncode == 0, P.queue(ech_metamorphe["post"])
    b = P.read_post_json(ech_metamorphe["dir"])["inputs_sha256"]
    c = P.read_post_json(base_dir)["inputs_sha256"]
    assert a["sim_trees"] == b["sim_trees"], "mêmes partitions de sim/trees : même empreinte"
    assert a["params_tarif"] != b["params_tarif"], "tarif changé : empreinte changée"
    assert a["sim_trees"] != c["sim_trees"], "autres arbres : autre empreinte"


def test_commit_du_tarif(pj, base_dir):
    t = P.Tarif(base_dir / "params" / "tarif.parquet")
    assert pj["tarif_commit"] == "0000000" and t.commits == {pj["tarif_commit"]}


def test_un_element_par_modele_utilise_avec_sa_source(pj, base_dir):
    t = P.Tarif(base_dir / "params" / "tarif.parquet")
    models = [m["model"] for m in pj["models"]]
    assert len(models) == len(set(models)), f"modèle en double : {models}"
    assert set(models) == t.models, f"modèles {sorted(models)} ; ceux du tarif : {sorted(t.models)}"
    for m in pj["models"]:
        assert m["commit"] == "0000000" and m["provisoire"] is True, m
        assert "synthetique_jeu_fictif" in m["source"], f"source du modèle {m['model']} : {m['source']!r}"


def test_comptes_egaux_a_l_oracle(pj, oracle):
    att = oracle.counts()
    assert pj["tree_years_computed"] == att["tree_years_computed"]
    assert pj["tree_years_not_computed"] == att["tree_years_not_computed"]
    lu = {sp: v for sp, v in pj["out_of_domain"].items() if any(v.values())}
    assert lu == att["out_of_domain"], {"lu": lu, "attendu": att["out_of_domain"]}
    assert pj["without_tarif"] == att["without_tarif"] == {}


def test_le_compte_non_calcule_est_la_somme_des_raisons(pj, oracle):
    s = sum(sum(v.values()) for v in pj["out_of_domain"].values()) + sum(pj["without_tarif"].values())
    assert pj["tree_years_not_computed"] == s
    assert pj["tree_years_computed"] + pj["tree_years_not_computed"] == len(oracle.trees["year"])


def test_part_provisoire_et_duree(pj):
    assert pj["provisional_share"] == 1.0, "tous les paramètres du tarif synthétique sont provisoires"
    assert pj["duration_s"] >= 0
    assert pj["schema_version"] == 1
