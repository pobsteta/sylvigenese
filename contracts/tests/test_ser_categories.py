"""Contrat `prepare.ser_categories` (ser.csv) : une valeur de ser.tif par couple distinct
(SER sous-jacente, code d'alluvions), colonnes value, name, alluvium_code.

Les autres tables de catégories restent (value, name) : on le vérifie aussi, pour que le
nouveau contrat ne les ait pas déplacées.
"""
import pytest

import helpers as h
from validator import cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def ser_csv(tmp_path, rows, header=("value", "name", "alluvium_code")):
    return h.csv(tmp_path / "ser.csv", list(header), rows)


def test_la_meme_ser_peut_porter_plusieurs_valeurs(tmp_path, capsys):
    """H10 sans alluvions, puis H10 portant L3 : `name` se répète, c'est voulu."""
    path = ser_csv(tmp_path, [[1, "H10", ""], [2, "H10", "L3"], [3, "B21", "L1"]])
    assert run(capsys, ["prepare.ser_categories", str(path)])[0] == 0


def test_alluvium_code_vide_partout_est_accepte(tmp_path, capsys):
    path = ser_csv(tmp_path, [[1, "H10", ""], [2, "B21", ""]])
    assert run(capsys, ["prepare.ser_categories", str(path)])[0] == 0


@pytest.mark.parametrize("name", ["L1", "L3", "L5"])
def test_une_alluvion_n_est_jamais_une_ser_sous_jacente(name, tmp_path, capsys):
    code, out = run(capsys, ["prepare.ser_categories", str(ser_csv(tmp_path, [[1, name, ""]]))])
    assert code == 3 and "name" in out


@pytest.mark.parametrize("alluvium", ["L6", "L0", "H10", "l3"])
def test_alluvium_code_hors_l1_a_l5_est_refuse(alluvium, tmp_path, capsys):
    code, out = run(capsys, ["prepare.ser_categories",
                             str(ser_csv(tmp_path, [[1, "H10", alluvium]]))])
    assert code == 3 and "alluvium_code" in out


def test_l_ancienne_forme_sans_alluvium_code_est_refusee(tmp_path, capsys):
    path = ser_csv(tmp_path, [[1, "H10"]], header=("value", "name"))
    code, out = run(capsys, ["prepare.ser_categories", str(path)])
    assert code == 3 and "alluvium_code" in out


def test_une_valeur_en_double_est_refusee(tmp_path, capsys):
    code, out = run(capsys, ["prepare.ser_categories",
                             str(ser_csv(tmp_path, [[1, "H10", ""], [1, "H10", "L3"]]))])
    assert code == 3 and "value" in out


def test_les_autres_tables_de_categories_restent_value_name(tmp_path, capsys):
    for contract, name in [("prepare.station_type_categories", "station_type.csv"),
                           ("prepare.stand_map_categories", "stand_map.csv"),
                           ("biomes.vegetation_categories", "vegetation_map.csv")]:
        good = h.csv(tmp_path / name, ["value", "name"], [[1, "S01"], [2, "S02"]])
        assert run(capsys, [contract, str(good)])[0] == 0, contract
        extra = h.csv(tmp_path / name, ["value", "name", "alluvium_code"], [[1, "S01", ""]])
        assert run(capsys, [contract, str(extra)])[0] == 3, contract


@pytest.mark.parametrize("rows", [
    [[1, "H10", "L3"], [2, "B21", ""], [3, "H10", "L3"]],   # même couple avec alluvions
    [[1, "H10", ""], [2, "H10", "L3"], [3, "H10", ""]],      # même couple sans alluvions
])
def test_un_couple_ser_alluvions_en_double_est_refuse(rows, tmp_path, capsys):
    """Une valeur par couple distinct (name, alluvium_code) : deux valeurs pour le même couple
    sont refusées, que le code d'alluvions soit rempli ou vide."""
    code, out = run(capsys, ["prepare.ser_categories", str(ser_csv(tmp_path, rows))])
    assert code == 3 and "doublon" in out and "ligne 4" in out


# --- clé primaire (name, alluvium_code) avec une valeur nulle (dette M1a, mission 027) ---------
# Table Schema compare les clés comme des tuples : (H10, vide) en double est un doublon.

def test_doublon_h10_sans_alluvions_est_refuse(tmp_path, capsys):
    path = ser_csv(tmp_path, [[1, "H10", ""], [2, "H10", ""]])
    code, out = run(capsys, ["prepare.ser_categories", str(path)])
    assert code == 3 and "doublon" in out


def test_doublon_avec_alluvions_reste_refuse(tmp_path, capsys):
    path = ser_csv(tmp_path, [[1, "H10", "L3"], [2, "H10", "L3"]])
    assert run(capsys, ["prepare.ser_categories", str(path)])[0] == 3


def test_un_vide_et_un_code_ne_sont_pas_un_doublon(tmp_path, capsys):
    path = ser_csv(tmp_path, [[1, "H10", ""], [2, "H10", "L3"], [3, "H10", "L4"]])
    assert run(capsys, ["prepare.ser_categories", str(path)])[0] == 0


def _check_arrow(keys_a, keys_b):
    """Chemin Arrow (Parquet) : même schéma que ser.csv, clé primaire (name, alluvium_code)."""
    import json
    from pathlib import Path

    import pyarrow as pa
    from validator import tables
    from validator.report import Findings

    schema = json.loads((Path(__file__).resolve().parents[1]
                         / "tables/prepare/ser_categories.schema.json").read_text(encoding="utf-8"))
    findings = Findings()
    tables.check_table(schema, pa.table({"value": list(range(1, len(keys_a) + 1)),
                                         "name": pa.array(keys_a, pa.string()),
                                         "alluvium_code": pa.array(keys_b, pa.string())}),
                       findings)
    return findings.errors


def test_arrow_doublon_h10_nul_refuse():
    errors = _check_arrow(["H10", "H10"], [None, None])
    assert any("doublon" in e and "(vide)" in e for e in errors), errors


def test_arrow_h10_nul_puis_code_accepte():
    assert _check_arrow(["H10", "H10", "B21"], [None, "L3", None]) == []


def test_arrow_cle_entierement_nulle_refusee():
    import pyarrow as pa
    from validator import tables
    from validator.report import Findings

    schema = {"fields": [{"name": "a", "type": "string"}, {"name": "b", "type": "string"}],
              "primaryKey": ["a", "b"]}
    findings = Findings()
    tables.check_table(schema, pa.table({"a": pa.array(["x", None], pa.string()),
                                         "b": pa.array([None, None], pa.string())}), findings)
    assert any("entièrement nulle" in e for e in findings.errors), findings.errors
