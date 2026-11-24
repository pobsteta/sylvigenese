"""Écritures lues différemment en YAML 1.1 (PyYAML, R) et en YAML 1.2 (TypeScript).

Décision de l'orchestrateur (relecture 2/3 de la mission 009) : tout scalaire non quoté
ambigu est refusé, code 3, avec ce qu'il faut écrire à la place. JSON n'a pas cette
ambiguïté : `010` ou `yes` y sont déjà des erreurs de syntaxe.
"""
import pytest

import helpers as h
from validator import cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def config_with(tmp_path, old, new):
    path = h.write_yaml(tmp_path / "config.yml", h.config())
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


def biome_with(tmp_path, old, new):
    path = h.write_yaml(tmp_path / "b.yml", h.biome())
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


@pytest.mark.parametrize("new,hint", [
    ("seed: 010", "zéro de tête"),
    ("seed: 0o10", "zéro de tête"),
    ("seed: 1:30", "sexagésimal"),
    ("seed: yes", "true ou false"),
])
def test_config_ambiguous_values_are_refused(new, hint, tmp_path, capsys):
    code, out = run(capsys, ["config", str(config_with(tmp_path, "seed: 42", new))])
    assert code == 3, out
    assert "ambiguë" in out and hint in out and "guillemets" in out


@pytest.mark.parametrize("new", ["provisoire: yes", "provisoire: On", "provisoire: NO",
                                 "provisoire: y", "provisoire: N", "provisoire: off"])
def test_biome_yaml11_booleans_are_refused(new, tmp_path, capsys):
    code, out = run(capsys, ["biome", str(biome_with(tmp_path, "provisoire: true", new))])
    assert code == 3, out
    assert "true ou false" in out


def test_biome_leading_zero_value_is_refused(tmp_path, capsys):
    path = biome_with(tmp_path, "tiges_ha: 320", "tiges_ha: 0320")
    code, out = run(capsys, ["biome", str(path)])
    assert code == 3 and "zéro de tête" in out


def test_biome_ambiguous_key_is_refused(tmp_path, capsys):
    path = biome_with(tmp_path, "      myrtille: 0.5", "      no: 0.5")
    code, out = run(capsys, ["biome", str(path)])
    assert code == 3 and "ambiguë" in out


def test_quoted_and_plain_values_stay_accepted(tmp_path, capsys):
    path = config_with(tmp_path, "zone: zone_fictive", 'zone: "010"')
    assert run(capsys, ["config", str(path)])[0] == 0
    path = biome_with(tmp_path, "tiges_ha: 320", "tiges_ha: 320.0")
    assert run(capsys, ["biome", str(path)])[0] == 0
    path = biome_with(tmp_path, "tiges_ha: 320", "tiges_ha: 0")
    assert run(capsys, ["biome", str(path)])[0] == 0
    path = biome_with(tmp_path, "provisoire: true", "provisoire: false")
    assert run(capsys, ["biome", str(path)])[0] == 0


def test_exponent_without_sign_is_caught_by_the_type_only(tmp_path, capsys):
    """Écart signalé, non tranché : `0.5e3` est une chaîne en YAML 1.1 et un nombre en
    YAML 1.2. Hors des trois familles décidées ; ici le type number du schéma le refuse."""
    path = biome_with(tmp_path, "tiges_ha: 320", "tiges_ha: 0.5e3")
    code, out = run(capsys, ["biome", str(path)])
    assert code == 3 and "tiges_ha" in out


@pytest.mark.parametrize("old,new", [('"year": 2030', '"year": 02030'),
                                     ('"provisoire": true', '"provisoire": yes')])
def test_cell_sheet_json_has_no_ambiguous_writing(old, new, tmp_path, capsys):
    path = h.write_json(tmp_path / "t.json", h.cell_sheet())
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    code, out = run(capsys, ["cell_sheet", str(path)])
    assert code == 3 and "syntaxe" in out


def test_cell_sheet_yaml11_strings_in_json_are_plain_strings(tmp_path, capsys):
    """En JSON, "yes" est une chaîne sans ambiguïté : refusé par le type booléen."""
    sheet = h.cell_sheet()
    sheet["cells"][0]["years"][0]["provisoire"] = "yes"
    code, out = run(capsys, ["cell_sheet", str(h.write_json(tmp_path / "t.json", sheet))])
    assert code == 3 and "provisoire" in out


@pytest.mark.parametrize("value", ["NaN", "inf", "-Infinity"])
def test_csv_nan_says_nan_not_minimum(value, tmp_path, capsys):
    header = ["species", "type", "n_plots", "fertilite_moy", "fertilite_med",
              "fertilite_sd", "age_ref"]
    rows = [["09", "fraiche_acide", 12, value, 24.0, 2.1, 50]]
    path = h.csv(tmp_path / "fertilite.csv", header, rows, sep=";")
    code, out = run(capsys, ["fertilite", str(path)])
    assert code == 3, out
    assert "valeur NaN ou infinie refusée" in out and "minimum" not in out
