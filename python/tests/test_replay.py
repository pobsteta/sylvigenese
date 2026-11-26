"""Rejeu sur un export d'exemplaires (tools/rejouer_exemplaires_reels, mission 070) : exemplaires SYNTHÉTIQUES."""

import csv
import subprocess
import sys

import exemplars_synthetiques as F
from test_assets import ROOT


def run(*args):
    return subprocess.run([str(ROOT / "tools" / "rejouer_exemplaires_reels"), *map(str, args)], capture_output=True,
                          text=True, cwd=ROOT)


def test_rejeu_conforme_identique_et_rapport(tmp_path):
    F.write_set(tmp_path / "ex")
    result = run(tmp_path / "ex", "--sortie", tmp_path / "out")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "identité des deux écritures : oui" in result.stderr
    rows = list(csv.DictReader(open(tmp_path / "out" / "rejouer_exemplaires.csv", encoding="utf-8")))
    own = [r for r in rows if r["kind"] == "own"]
    assert len(own) == 12 and {r["model"] for r in rows} >= {"02_mature", "61_young", "generique_feuillu"}
    assert {r["calage"] for r in own if r["model"].startswith("61_")} == {"non calé"}
    assert all(int(r["triangles_lod0"]) > int(r["triangles_lod1"]) > int(r["triangles_lod2"]) for r in rows)
    assert not (tmp_path / "out" / ".rejeu").exists()


def test_rejeu_refuse_une_sortie_dans_le_depot_et_un_dossier_vide(tmp_path):
    F.write_set(tmp_path / "ex")
    assert run(tmp_path / "ex", "--sortie", ROOT / "essai_rejeu_interdit").returncode == 2
    assert not (ROOT / "essai_rejeu_interdit").exists()
    (tmp_path / "vide").mkdir()
    bad = run(tmp_path / "vide", "--sortie", tmp_path / "o")
    assert bad.returncode == 2 and "aucun fichier .parquet" in bad.stderr
