"""Contrats amendés ou nouveaux pour M3a (mission 033) : run.json, sim.cells sans semis,
signalements de la simulation, courbe de Korf et allométries hcb et cw.

Chaque contrat a ici un cas conforme et un cas fautif de plus que ceux de test_cases.py.
"""
import copy
import re

import pyarrow as pa
import pytest

import helpers as h
from validator import cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def check(capsys, name, path):
    return run(capsys, [name, str(path)])


# ------------------------------------------------------------------ run.json

def test_run_json_with_all_counts_is_conform(tmp_path, capsys):
    code, out = check(capsys, "run", h.write_json(tmp_path / "run.json", h.run_json()))
    assert code == 0, out


@pytest.mark.parametrize("key", ["domain_outputs", "cells_at_height_ceiling", "edge_disks",
                                 "mixed_cells", "recruits", "deaths", "memory_estimate_bytes",
                                 "duration_s", "config_sha256"])
def test_run_json_without_a_count_is_refused(key, tmp_path, capsys):
    data = h.run_json()
    del data[key]
    code, out = check(capsys, "run", h.write_json(tmp_path / "run.json", data))
    assert code == 3 and key in out, out


def mutated(change):
    data = copy.deepcopy(h.run_json())
    change(data)
    return data


@pytest.mark.parametrize("change,pattern", [
    (lambda d: d.update(deaths=-1), r"deaths"),
    (lambda d: d.update(recruits=2.5), r"recruits"),
    (lambda d: d.update(config_sha256="ABC"), r"config_sha256"),
    (lambda d: d["domain_outputs"].update(altitude={"below": 0, "above": 0}), r"altitude"),
    (lambda d: d["domain_outputs"].update(bal={"below": 0}), r"above"),
    (lambda d: d["domain_outputs"].update(bal={"below": -1, "above": 0}), r"below"),
    (lambda d: d.update(domain_outputs={}), r"domain_outputs"),
    (lambda d: d.update(inconnu=1), r"inconnu"),
])
def test_run_json_faulty_counts_are_refused(change, pattern, tmp_path, capsys):
    code, out = check(capsys, "run", h.write_json(tmp_path / "run.json", mutated(change)))
    assert code == 3 and re.search(pattern, out), out


# ------------------------------------------------------------------ sim.cells, semis facultatifs

def cells_without_seedlings():
    data = h.sim_cells()
    del data["seedlings_ha"], data["seedling_h_mean"]
    return data


def test_cells_without_seedling_columns_are_conform(tmp_path, capsys):
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", cells_without_seedlings()))
    assert code == 0, out


def test_cells_with_only_the_seedling_density_are_conform(tmp_path, capsys):
    data = cells_without_seedlings()
    data["seedlings_ha"] = [1000.0, 50.0, 0.0]
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", data))
    assert code == 0, out


def test_cells_with_a_negative_seedling_density_are_refused(tmp_path, capsys):
    data = h.sim_cells()
    data["seedlings_ha"][0] = -1.0
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", data))
    assert code == 3 and "seedlings_ha" in out, out


def test_cells_still_require_the_stem_columns(tmp_path, capsys):
    data = cells_without_seedlings()
    del data["stems_ha"]
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", data))
    assert code == 3 and "stems_ha" in out, out


def test_cells_refuse_an_unknown_column(tmp_path, capsys):
    data = cells_without_seedlings()
    data["semis"] = [0.0, 0.0, 0.0]
    code, out = check(capsys, "sim_cells", h.hive(tmp_path / "cells", data))
    assert code == 3 and "semis" in out, out


# ------------------------------------------------------------------ signalements

FLAG_TYPES = {"entity": pa.string(), "value": pa.float64(), "kind": pa.string(),
              "message": pa.string()}


def flags_file(tmp_path, data):
    return h.parquet(tmp_path / "flags.parquet", data, FLAG_TYPES)


def test_flags_table_is_conform(tmp_path, capsys):
    code, out = check(capsys, "sim_flags", flags_file(tmp_path, h.sim_flags()))
    assert code == 0, out


def test_flags_table_without_a_row_is_conform(tmp_path, capsys):
    empty = {k: [] for k in h.sim_flags()}
    empty["year"] = pa.array([], pa.int64())
    code, out = check(capsys, "sim_flags", flags_file(tmp_path, empty))
    assert code == 0, out


@pytest.mark.parametrize("column,value,pattern", [
    ("entity", "", r"entity"),
    ("kind", "Plafond", r"kind"),
    ("message", None, r"message"),
    ("year", None, r"year"),
    ("value", float("nan"), r"value"),
])
def test_flags_table_faults_are_refused(column, value, pattern, tmp_path, capsys):
    data = h.sim_flags()
    data[column][0] = value
    code, out = check(capsys, "sim_flags", flags_file(tmp_path, data))
    assert code == 3 and re.search(pattern, out), out


def test_flags_table_refuses_a_missing_column(tmp_path, capsys):
    data = h.sim_flags()
    del data["message"]
    code, out = check(capsys, "sim_flags", flags_file(tmp_path, data))
    assert code == 3 and "message" in out, out


# ------------------------------------------------------------------ Korf et allométries

DYN_TYPES = {"species": pa.string(), "species_group": pa.string(), "variable": pa.string(),
             "x": pa.float64()}
SRC = "synthétique, jeu fictif"


def long_rows(model, terms, species="09"):
    n = len(terms)
    return {"species": [species] * n, "species_group": [None] * n, "model": [model] * n,
            "term": list(terms), "variable": [None] * n, "x": [None] * n,
            "value": [1.0 + i for i in range(n)], "provisoire": [True] * n, "source": [SRC] * n}


KORF_TERMS = ["a", "b", "c"] + [f"p_f_class{i}" for i in range(1, 6)]


def test_korf_curve_is_conform(tmp_path, capsys):
    path = h.parquet(tmp_path / "height_curve.parquet", long_rows("korf", KORF_TERMS), DYN_TYPES)
    code, out = check(capsys, "height_curve", path)
    assert code == 0, out


def test_korf_next_to_chapman_richards_is_conform(tmp_path, capsys):
    rows = long_rows("korf", KORF_TERMS)
    other = long_rows("chapman_richards", ["k", "p"], species="02")
    for key in rows:
        rows[key] += other[key]
    path = h.parquet(tmp_path / "height_curve.parquet", rows, DYN_TYPES)
    code, out = check(capsys, "height_curve", path)
    assert code == 0, out


def test_korf_written_with_a_capital_is_refused(tmp_path, capsys):
    path = h.parquet(tmp_path / "height_curve.parquet", long_rows("Korf", KORF_TERMS), DYN_TYPES)
    code, out = check(capsys, "height_curve", path)
    assert code == 3 and "model" in out, out


def test_korf_with_a_duplicate_term_is_refused(tmp_path, capsys):
    path = h.parquet(tmp_path / "height_curve.parquet",
                     long_rows("korf", KORF_TERMS + ["a"]), DYN_TYPES)
    code, out = check(capsys, "height_curve", path)
    assert code == 3 and "doublon" in out, out


ALLOMETRY_TYPES = {"species": pa.string(), "species_group": pa.string()}


def test_hcb_and_cw_allometries_are_conform(tmp_path, capsys):
    hcb = long_rows("hcb", ["CR_a", "CR_b", "CR_min", "CR_max"])
    cw = long_rows("cw", ["R_a", "R_b"])
    rows = {k: hcb[k] + cw[k] for k in hcb if k not in ("variable", "x")}
    path = h.parquet(tmp_path / "allometry.parquet", rows, ALLOMETRY_TYPES)
    code, out = check(capsys, "allometry", path)
    assert code == 0, out


def test_hcb_allometry_without_a_value_is_refused(tmp_path, capsys):
    rows = long_rows("hcb", ["CR_a", "CR_b"])
    rows = {k: v for k, v in rows.items() if k not in ("variable", "x")}
    rows["value"][1] = None
    path = h.parquet(tmp_path / "allometry.parquet", rows, ALLOMETRY_TYPES)
    code, out = check(capsys, "allometry", path)
    assert code == 3 and "value" in out, out
