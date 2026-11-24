"""Ligne de commande, mode --zone, cas limites des lecteurs (mission 009)."""
import os
import shutil
import subprocess
from pathlib import Path

import pyarrow as pa
import pytest

import helpers as h
import test_cases
from validator import catalog, cli, csv_files, tables
from validator.report import Findings

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def run(capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --------------------------------------------------------------------- arguments

@pytest.mark.parametrize("argv", [[], ["trees_init"], ["--zone"], ["--bogus", "x"],
                                  ["--max-errors", "0", "trees_init", "x"],
                                  ["--zone", "a", "trees_init"]])
def test_invalid_arguments_give_code_2_in_french(argv, capsys):
    code, _, err = run(capsys, argv)
    assert code == 2
    assert "argument" in err and "usage" in err


def test_help_and_list(capsys):
    assert run(capsys, ["--aide"])[0] == 0
    code, out, _ = run(capsys, ["--list"])
    assert code == 0
    assert "prepare.trees_init (aussi : trees_init)" in out


def test_contract_option_is_the_same_as_positional(tmp_path, capsys):
    path = h.parquet(tmp_path / "t.parquet", h.trees_init())
    assert run(capsys, ["--contract", "prepare.trees_init", str(path)])[0] == 0
    assert run(capsys, ["trees_init", str(path), str(path)])[0] == 0


def test_max_errors_limits_the_output(tmp_path, capsys):
    data = h.trees_init()
    for key in ("species", "species_source", "d130_source"):
        data[key] = ["?", "?"]
    path = h.parquet(tmp_path / "t.parquet", data)
    code, _, err = run(capsys, ["--max-errors", "1", "trees_init", str(path)])
    assert code == 3
    assert "autre(s) écart(s)" in err


def test_script_runs_as_a_subprocess_without_traceback(tmp_path):
    bad = tmp_path / "x.parquet"
    bad.write_bytes(b"PAR1 pas du parquet")
    r = subprocess.run([str(CONTRACTS / "validate"), "trees_init", str(bad)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 3
    assert "Traceback" not in r.stderr and "illisible" in r.stderr


def test_csv_works_without_network(tmp_path):
    env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9")
    path = test_cases.species(tmp_path, False)
    r = subprocess.run(["python3", str(CONTRACTS / "validate"), "species", str(path)],
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------- mode zone

def write_inputs(zone):
    """Toutes les entrées obligatoires, conformes, sous zone/inputs/."""
    inputs = zone / "inputs"
    (inputs / "ifn").mkdir(parents=True)
    for name in test_cases.CASES:
        if not name.startswith("inputs.") or name == "inputs.inventaire_video":
            continue
        made, _ = test_cases.build(name, inputs, fault=False)
        target = zone / catalog.get(name)["paths"][0]
        if made != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(made), str(target))
    return zone


def test_zone_with_all_inputs_is_conform(tmp_path, capsys):
    zone = write_inputs(tmp_path / "zone_fictive")
    code, out, err = run(capsys, ["--zone", str(zone)])
    assert code == 0, err
    assert "0 non conforme(s), 0 impossible(s) à contrôler, 0 obligatoire(s) absent(s)" in out


def test_zone_without_h_pot_gives_code_2(tmp_path, capsys):
    """Spec §3 : h_pot.tif manquant, erreur, code 2."""
    zone = write_inputs(tmp_path / "zone_fictive")
    (zone / "inputs" / "h_pot.tif").unlink()
    code, _, err = run(capsys, ["--zone", str(zone)])
    assert code == 2
    assert "h_pot.tif" in err and "obligatoire absent" in err


def test_zone_with_a_bad_output_gives_code_3(tmp_path, capsys):
    zone = write_inputs(tmp_path / "zone_fictive")
    h.tif(zone / "grid.tif", dtype="uint16")
    h.tif(zone / "h0.tif", origin=(h.ORIGIN[0] + 25, h.ORIGIN[1]))  # décalé d'une maille
    code, _, err = run(capsys, ["--zone", str(zone)])
    assert code == 3
    assert "h0.tif" in err and "non aligné" in err


def test_absent_zone_gives_code_2(tmp_path, capsys):
    assert run(capsys, ["--zone", str(tmp_path / "rien")])[0] == 2


# ------------------------------------------------------------- cas des lecteurs

def test_empty_parquet_directory_is_not_conform(tmp_path, capsys):
    (tmp_path / "trees_init").mkdir()
    code, _, err = run(capsys, ["trees_init", str(tmp_path / "trees_init")])
    assert code == 3 and "aucun fichier" in err


def test_partition_folder_is_required(tmp_path, capsys):
    h.parquet(tmp_path / "trees" / "2030" / "part.parquet", h.sim_trees())
    code, _, err = run(capsys, ["sim_trees", str(tmp_path / "trees")])
    assert code == 3 and "year=AAAA" in err


def test_directory_given_for_a_file_contract(tmp_path, capsys):
    code, _, err = run(capsys, ["species", str(tmp_path)])
    assert code == 3 and "dossier" in err


def test_json_duplicate_key_is_refused(tmp_path, capsys):
    path = tmp_path / "run.json"
    path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    code, _, err = run(capsys, ["run", str(path)])
    assert code == 3 and "double" in err


def test_table_missing_column_and_empty_table(capsys, tmp_path):
    path = h.parquet(tmp_path / "s.parquet", {k: v[:0] for k, v in h.summary().items()},
                     types={"cell_id": pa.int64(), "year": pa.int64(),
                            "species": pa.string(), "volume_m3_ha": pa.float64(),
                            "biomass_t_ha": pa.float64(), "carbon_t_ha": pa.float64(),
                            "provisoire": pa.bool_()})
    code, _, err = run(capsys, ["summary", str(path)])
    assert code == 3 and "table vide" in err


def test_same_verdict_for_csv_and_parquet(tmp_path):
    """Le contrôle Arrow (Parquet) et frictionless (CSV) disent la même chose."""
    schema = {"$schema": "https://datapackage.org/profiles/2.0/tableschema.json",
              "fieldsMatch": "equal",
              "fields": [{"name": "value", "type": "integer",
                          "constraints": {"required": True, "unique": True, "minimum": 0}},
                         {"name": "name", "type": "string",
                          "constraints": {"required": True, "pattern": "[a-z_]+",
                                          "enum": ["a", "b_c"]}}]}
    cases = {"conforme": ([1, 2], ["a", "b_c"]), "doublon": ([1, 1], ["a", "b_c"]),
             "négatif": ([-1, 2], ["a", "b_c"]), "motif": ([1, 2], ["a", "B"]),
             "liste": ([1, 2], ["a", "zz"])}
    for label, (values, names) in cases.items():
        arrow = Findings()
        tables.check_table(schema, pa.table({"value": values, "name": names}), arrow)
        path = h.csv(tmp_path / f"{label}.csv", ["value", "name"],
                     [[v, n] for v, n in zip(values, names)])
        [(_, csv)] = csv_files.check(path, schema, {})
        assert bool(arrow) == bool(csv), (label, arrow.errors, csv.errors)
        assert bool(arrow) == (label != "conforme"), label
