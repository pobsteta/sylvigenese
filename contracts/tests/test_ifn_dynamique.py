"""Contrats IFN de la dynamique (mission 023) : un fichier conforme et un fautif par nouvelle
colonne, C13 et IR5 en mètres (docs/referentiels/ifn-dynamique-colonnes.csv).

Les entrées sont des CSV `;` aux colonnes exactes de l'export ; les sorties de `prepare` des
Parquet aux colonnes anglaises documentées.
"""
import pyarrow as pa
import pytest

import helpers as h
import test_cases as tc
from validator import cli

PLACETTE = ["IDP", "CAMPAGNE", "XL", "YL", "VISITE", "DATEPOINT", "NINCID", "INCID", "PRELEV5",
            "DEF5", "INSTP5"]
ARBRE = ["IDP", "CAMPAGNE", "A", "ESPAR", "C13", "VEGET", "VEGET5", "IR5", "HTOT", "V"]


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def placette(tmp, **changes):
    row = dict(zip(PLACETTE, ["1001", 2015, h.PARIS_X, h.PARIS_Y, 1, "10/03/2015", 0, 0, "", "", ""]))
    row.update(changes)
    return h.csv(tmp / "PLACETTE.csv", PLACETTE, [[row[c] for c in PLACETTE]], sep=";")


def arbre(tmp, **changes):
    row = dict(zip(ARBRE, ["1001", 2015, 1, "09", 0.950, 0, "", 0.012, 22.5, 0.8]))
    row.update(changes)
    return h.csv(tmp / "ARBRE.csv", ARBRE, [[row[c] for c in ARBRE]], sep=";")


def test_conform_files(tmp_path, capsys):
    assert run(capsys, ["ifn_placette", str(placette(tmp_path))])[0] == 0
    assert run(capsys, ["ifn_arbre", str(arbre(tmp_path))])[0] == 0


# (colonne, valeur fautive, mot attendu dans le message)
FAULTY_PLACETTE = [
    ("VISITE", 3, "VISITE"), ("VISITE", "", "VISITE"), ("DATEPOINT", "2015-03-10", "DATEPOINT"),
    ("NINCID", 6, "NINCID"), ("INCID", 5, "INCID"), ("DEF5", 6, "DEF5"), ("INSTP5", 2, "INSTP5"),
    ("CAMPAGNE", "", "CAMPAGNE"),
]


@pytest.mark.parametrize("column,value,word", FAULTY_PLACETTE)
def test_faulty_placette_column(tmp_path, capsys, column, value, word):
    code, out = run(capsys, ["ifn_placette", str(placette(tmp_path, **{column: value}))])
    assert code == 3 and word in out


FAULTY_ARBRE = [
    ("A", "", "A"), ("A", 0, "A"), ("C13", -0.5, "C13"), ("VEGET", "9", "VEGET"),
    ("VEGET5", "Z", "VEGET5"), ("IR5", -0.01, "IR5"), ("IR5", "abc", "IR5"), ("CAMPAGNE", "", "CAMPAGNE"),
]


@pytest.mark.parametrize("column,value,word", FAULTY_ARBRE)
def test_faulty_arbre_column(tmp_path, capsys, column, value, word):
    code, out = run(capsys, ["ifn_arbre", str(arbre(tmp_path, **{column: value}))])
    assert code == 3 and word in out


def test_empty_optional_cells_are_conform(tmp_path, capsys):
    """Colonne vide = valeur absente de l'export : VEGET sur une 2e visite, IR5 non mesuré."""
    path = arbre(tmp_path, VEGET="", VEGET5="M", IR5="")
    assert run(capsys, ["ifn_arbre", str(path)])[0] == 0


def test_veget5_column_may_be_missing_before_2010(tmp_path, capsys):
    cols = [c for c in ARBRE if c != "VEGET5"]
    path = h.csv(tmp_path / "ARBRE.csv", cols, [["1001", 2005, 1, "09", 0.950, 0, 0.012, 22.5, 0.8]], sep=";")
    assert run(capsys, ["ifn_arbre", str(path)])[0] == 0


def test_dynamics_columns_other_than_veget5_are_required(tmp_path, capsys):
    for missing in ("A", "CAMPAGNE", "VEGET", "IR5"):
        cols = [c for c in ARBRE if c not in (missing, "VEGET5")]
        row = {"IDP": "1001", "CAMPAGNE": 2015, "A": 1, "ESPAR": "09", "C13": 0.95, "VEGET": 0, "IR5": 0.01, "HTOT": 22.5, "V": 0.8}
        path = h.csv(tmp_path / "ARBRE.csv", cols, [[row[c] for c in cols]], sep=";")
        code, out = run(capsys, ["ifn_arbre", str(path)])
        assert code == 3 and missing in out, missing


def test_placette_optional_columns_may_be_missing(tmp_path, capsys):
    cols = ["IDP", "CAMPAGNE", "XL", "YL", "VISITE"]
    path = h.csv(tmp_path / "PLACETTE.csv", cols, [["1001", 2015, h.PARIS_X, h.PARIS_Y, 1]], sep=";")
    assert run(capsys, ["ifn_placette", str(path)])[0] == 0


def test_c13_in_millimetres_is_not_caught_by_the_contract_but_by_prepare():
    """Le contrat n'a pas de maximum : l'erreur d'unité (C13 en mm) est refusée par prepare
    (R/prepare_ifn.R, garde-fou « C13 en mètres »), vérifiée par testthat."""
    import json
    from pathlib import Path
    racine = Path(__file__).resolve().parents[2]
    schema = json.load(open(racine / "contracts/tables/inputs/ifn_arbre.schema.json", encoding="utf-8"))
    c13 = next(f for f in schema["fields"] if f["name"] == "C13")
    assert c13["x-unit"] == "m" and "maximum" not in c13.get("constraints", {})


# ----------------------------------------------------------------- sorties de prepare

def plots_data():
    d = tc.ifn_plots()
    return d


def write_plots(tmp, mutate=None):
    d = tc.ifn_plots()
    if mutate:
        mutate(d)
    return h.parquet(tmp / "plots.parquet", d, tc.IFN_PLOTS_TYPES)


def write_trees(tmp, mutate=None):
    d = tc.ifn_trees()
    if mutate:
        mutate(d)
    return h.parquet(tmp / "trees.parquet", d, tc.IFN_TREES_TYPES)


def test_prepare_outputs_conform(tmp_path, capsys):
    assert run(capsys, ["prepare.ifn_plots", str(write_plots(tmp_path))])[0] == 0
    assert run(capsys, ["prepare.ifn_trees", str(write_trees(tmp_path))])[0] == 0


@pytest.mark.parametrize("column,index,value", [
    ("visit", 0, 3), ("visit", 0, None), ("date_point", 0, "10/03/2015"),
    ("incident_nature", 0, 6), ("incident_intensity", 0, 5), ("clearing_5y", 1, 6),
    ("planting_5y", 1, 2)])
def test_faulty_prepare_plots_column(tmp_path, capsys, column, index, value):
    path = write_plots(tmp_path, lambda d: d[column].__setitem__(index, value))
    code, out = run(capsys, ["prepare.ifn_plots", str(path)])
    assert code == 3 and column in out


@pytest.mark.parametrize("column,index,value", [
    ("veg_state", 0, "9"), ("veg_state_5y", 1, "Z"), ("radial_incr_5y_m", 0, -0.01),
    ("d130", 0, 0.0)])
def test_faulty_prepare_trees_column(tmp_path, capsys, column, index, value):
    path = write_trees(tmp_path, lambda d: d[column].__setitem__(index, value))
    code, out = run(capsys, ["prepare.ifn_trees", str(path)])
    assert code == 3 and column in out


def test_prepare_trees_without_dynamics_column_is_refused(tmp_path, capsys):
    path = write_trees(tmp_path, lambda d: d.pop("veg_state_5y"))
    code, out = run(capsys, ["prepare.ifn_trees", str(path)])
    assert code == 3 and "veg_state_5y" in out


def test_prepare_trees_empty_d130_is_allowed_for_cut_trees(tmp_path, capsys):
    """Un arbre coupé ou non retrouvé n'a plus de C13 : d130 vide, rien n'est deviné."""
    path = write_trees(tmp_path, lambda d: d["d130"].__setitem__(2, None))
    assert run(capsys, ["prepare.ifn_trees", str(path)])[0] == 0
