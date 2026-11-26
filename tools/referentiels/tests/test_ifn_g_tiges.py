"""Tests du calcul IFN de G (m²/ha) et des tiges/ha par placette (mission 058).

Référentiel : docs/referentiels/ifn-g-tiges.md. Jeu construit à la main, aucune donnée réelle :
les placettes et les arbres ci-dessous sont fictifs ; seuls les codes (CSA, PEUPNR, VEGET, ORI,
ESPAR) sont ceux de metadonnees.csv de l'export DataIFN du 07/10/2026.

Pas de coordonnées : le script ne lit ni XL ni YL, il ne fait que des statistiques par placette
(aucun croisement avec un raster fin, garde IFN).

Lancer : python3 -m pytest tools/referentiels/tests
"""
import csv
import io
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "ifn_g_tiges.py"
sys.path.insert(0, str(HERE.parent))

import ifn_g_tiges as ifn  # noqa: E402

# Placettes : A (sapinière, 3 arbres), B (arbre sans W : placette écartée), C (2e visite),
# D (PEUPNR vide), E (aucun arbre : G = 0), F (taillis de châtaignier, boisée ouverte),
# G (peupleraie, CSA = 5), H (campagne 2019, hors période).
PLACETTE = (
    "﻿CAMPAGNE;IDP;XL;VISITE;GRECO;SER;CSA;PEUPNR;\n"
    "2022;10;0;1;G;G11;1;0;\n"
    "2022;11;0;1;G;G11;1;0;\n"
    "2024;12;0;2;G;G11;1;0;\n"
    "2023;13;0;1;G;G11;1;;\n"
    "2023;14;0;1;G;G12;1;0;\n"
    "2023;15;0;1;G;G12;3;0;\n"
    "2023;16;0;1;G;G12;5;0;\n"
    "2019;17;0;1;G;G12;1;0;\n"
)
ARBRE = (
    "﻿CAMPAGNE;IDP;A;ESPAR;VEGET;ORI;C13;V;W;\n"
    # A : sapin pectiné (61) C13 = 1,0 m sur le cercle de 15 m, sapin C13 = 0,5 m sur 9 m,
    # hêtre (9, sans zéro initial) C13 = 0,3 m sur 6 m, issu de rejet.
    "2022;10;1;61;0;1;1.000;1.2;14.15;\n"
    "2022;10;2;61;0;1;0.500;0.3;39.29;\n"
    "2022;10;3;9;0;0;0.300;0.1;88.42;\n"
    "2022;10;4;61;5;1;0.900;0.9;14.15;\n"      # mort sur pied : exclu
    "2022;10;5;61;0;1;0.200;0.0;88.42;\n"      # sous le seuil de 0,235 m : exclu
    # B : arbre vivant sans W (cas réel en lisière) : toute la placette est écartée.
    "2022;11;1;09;0;1;0.400;0.2;;\n"
    "2022;11;2;09;0;1;0.400;0.2;88.42;\n"
    # C : 2e visite, W vide comme dans l'export réel.
    "2024;12;1;09;0;1;0.400;;;\n"
    # D : PEUPNR vide.
    "2023;13;1;09;0;1;0.400;0.2;88.42;\n"
    # F : deux châtaigniers (10) de rejet, C13 = 0,4 m sur le cercle de 6 m.
    "2023;15;1;10;0;0;0.400;0.2;88.42;\n"
    "2023;15;2;10;0;0;0.400;0.2;88.42;\n"
    # G : peupleraie.
    "2023;16;1;09;0;1;0.400;0.2;88.42;\n"
    # H : hors période.
    "2019;17;1;09;0;1;0.400;0.2;88.42;\n"
)

# Calcul à la main : g = C13² / (4 π), G = Σ W·g, N = Σ W, 4 π = 12,566371.
# A : G = (14,15 × 1,0² + 39,29 × 0,5² + 88,42 × 0,3²) / 12,566371
#       = (14,15 + 9,8225 + 7,9578) / 12,566371 = 31,9303 / 12,566371 = 2,54093 m²/ha
#     N = 14,15 + 39,29 + 88,42 = 141,86 tiges/ha
#     part de G des sapins = (14,15 + 9,8225) / 31,9303 = 0,7508 >= 0,75 : sapinière pure
#     Dg = 100 × sqrt(4 × 2,54093 / (π × 141,86)) = 100 × sqrt(0,022806) = 15,10 cm
G_A, N_A, DG_A = 2.54093, 141.86, 15.10
# F : G = 2 × 88,42 × 0,4² / 12,566371 = 28,2944 / 12,566371 = 2,25160 m²/ha ; N = 176,84
#     tiges de rejet : 100 % >= 75 % : taillis ; essence 10 hors des groupes : mélange ou autre
G_F, N_F = 2.25160, 176.84


@pytest.fixture()
def export(tmp_path):
    path = tmp_path / "export_dataifn.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("PLACETTE.csv", PLACETTE.encode("utf-8"))
        archive.writestr("ARBRE.csv", ARBRE.encode("utf-8"))
    return path


def run_default(export, csv_path=None):
    return ifn.run(export, csv_path, ifn.PERIOD, {"1"}, {"1", "3"}, {"0"}, "utf-8-sig")


def plots_of(export):
    with ifn.open_table(export, "PLACETTE", "utf-8-sig") as handle:
        plots, report = ifn.read_plots(handle, ifn.PERIOD, {"1"}, {"1", "3"})
    with ifn.open_table(export, "ARBRE", "utf-8-sig") as handle:
        ifn.read_trees(handle, plots, {"0"}, report)
    ifn.exclude_incomplete(plots, report)
    return plots, report


def test_g_and_stems_match_hand_computation(export):
    plots, _ = plots_of(export)
    a, f = plots[(2022, "10")], plots[(2023, "15")]
    assert a["g"] == pytest.approx(G_A, abs=1e-4)
    assert a["n"] == pytest.approx(N_A, abs=1e-9)
    assert f["g"] == pytest.approx(G_F, abs=1e-4)
    assert f["n"] == pytest.approx(N_F, abs=1e-9)
    assert ifn.stand_type(a) == "sapiniere_pessiere"
    assert ifn.stand_type(f) == "melange_ou_autre"
    assert plots[(2023, "14")]["g"] == 0.0
    assert ifn.stand_type(plots[(2023, "14")]) == "sans_arbre_recensable"


def test_filters_are_counted_not_silent(export):
    plots, report = plots_of(export)
    assert sorted(plots) == [(2022, "10"), (2023, "14"), (2023, "15")]
    assert report["placettes_periode"] == 7          # H (2019) hors période
    assert report["exclues_visite"] == 1             # C
    assert report["exclues_peupnr"] == 1             # D (PEUPNR vide)
    assert report["exclues_csa"] == 1                # G (peupleraie)
    assert report["placettes_retenues"] == 4         # A, B, E, F
    assert report["placettes_exclues_c13_ou_w_absent (signalées)"] == 1   # B
    assert report["placettes_calculees"] == 3
    assert report["arbres_non_vivants"] == 1
    assert report["arbres_sous_seuil (signalés, exclus)"] == 1
    assert report["arbres_sans_c13_ou_w (signalés, exclus)"] == 1
    assert report["arbres_retenus"] == 6              # 3 de A, 1 de B (écartée ensuite), 2 de F


def test_plot_without_w_is_not_a_false_zero(export):
    """La placette B ne doit pas peser comme une placette à G = 0."""
    plots, _ = plots_of(export)
    assert (2022, "11") not in plots
    groups = ifn.summarise(plots)
    zeros = [p for p in groups[("france", "FR", "toutes_placettes")] if p["g"] == 0.0]
    assert len(zeros) == 1                            # E seulement


def test_groups_and_published_values(export, monkeypatch):
    monkeypatch.setattr(ifn, "N_MIN", 1)
    rows, _ = run_default(export)

    def value(perimeter, code, kind, quantity, stat):
        hits = [r for r in rows if (r["perimetre"], r["code"], r["peuplement"], r["grandeur"],
                                    r["statistique"]) == (perimeter, code, kind, quantity, stat)]
        assert len(hits) == 1, (perimeter, code, kind, quantity, stat)
        return hits[0]

    # France, toutes placettes : E (0), F (2,2516), A (2,5409) ; médiane = F, moyenne à la main
    # (0 + 2,25160 + 2,54093) / 3 = 1,59751 -> « 1.6 ».
    assert value("france", "FR", "toutes_placettes", "g_m2_ha", "q50")["valeur"] == "2.3"
    assert value("france", "FR", "toutes_placettes", "g_m2_ha", "moyenne")["valeur"] == "1.6"
    assert value("france", "FR", "toutes_placettes", "g_m2_ha", "q50")["n_placettes"] == 3
    # tous_types : sans E. q05 = 2,25160 + 0,05 × (2,54093 - 2,25160) = 2,26607 -> « 2.3 » ;
    # tiges : q95 = 141,86 + 0,95 × (176,84 - 141,86) = 175,091 -> « 175.1 ».
    assert value("france", "FR", "tous_types", "g_m2_ha", "q05")["n_placettes"] == 2
    assert value("france", "FR", "tous_types", "tiges_ha", "q95")["valeur"] == "175.1"
    assert value("france", "FR", "tous_types", "tiges_ha", "q05")["valeur"] == "143.6"
    assert value("greco", "G", "sapiniere_pessiere", "dg_cm", "q50")["valeur"] == "15.1"
    assert value("greco", "G", "taillis", "tiges_ha", "q50")["valeur"] == "176.8"
    assert value("ser", "G11", "tous_types", "g_m2_ha", "q50")["valeur"] == "2.5"
    assert value("ser", "G12", "tous_types", "g_m2_ha", "q50")["valeur"] == "2.3"
    assert not [r for r in rows if r["code"] == "G11" and r["peuplement"] != "tous_types"]


def test_small_groups_are_not_published(export):
    rows, _ = run_default(export)                     # N_MIN = 30
    assert rows and all(r["valeur"] == "" for r in rows)
    assert all(r["note"] == "effectif < 30 : non publié" for r in rows)
    assert {r["n_placettes"] for r in rows} <= {1, 2, 3}


def test_quantile_type_7():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    # (n - 1) q = 4 q : q05 -> 0,2 -> 1,2 ; q25 -> 1 -> 2 ; q95 -> 3,8 -> 4,8
    assert ifn.quantile(values, 0.05) == pytest.approx(1.2)
    assert ifn.quantile(values, 0.25) == pytest.approx(2.0)
    assert ifn.quantile(values, 0.50) == pytest.approx(3.0)
    assert ifn.quantile(values, 0.95) == pytest.approx(4.8)
    assert ifn.quantile([7.0], 0.95) == pytest.approx(7.0)


def test_merge_keeps_other_sources(export, tmp_path, monkeypatch):
    monkeypatch.setattr(ifn, "N_MIN", 1)
    path = tmp_path / "ref.csv"
    other = {f: "" for f in ifn.FIELDS}
    other.update(perimetre="france", code="FR", source="IGN, tome 2009-2013", valeur="22.0")
    stale = dict(other, source=ifn.SOURCE_TAG, valeur="999")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ifn.FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows([other, stale])
    rows, _ = run_default(export, path)
    with open(path, encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["source"] == "IGN, tome 2009-2013" and written[0]["valeur"] == "22.0"
    assert "999" not in [r["valeur"] for r in written]
    assert len(written) == 1 + len(rows)


def test_missing_column_is_refused(tmp_path):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("PLACETTE.csv", PLACETTE.replace("PEUPNR", "PEUP"))
        archive.writestr("ARBRE.csv", ARBRE)
    assert ifn.main(["--export", str(path)]) == 2


def test_c13_in_centimetres_is_refused():
    plots = {(2022, "1"): {"greco": "G", "ser": "G11", "n": 0.0, "g": 0.0, "n_coppice": 0.0,
                           "g_group": defaultdict(float), "trees": 0}}
    tree = "CAMPAGNE;IDP;C13;W;VEGET;ESPAR;ORI\n2022;1;94.2;14.15;0;09;1\n"
    with pytest.raises(ifn.InputError, match="unité"):
        ifn.read_trees(io.StringIO(tree), plots, {"0"}, defaultdict(int))


def test_self_test_command_line():
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--self-test"],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "G = 3.472 m²/ha, N = 127.71 tiges/ha" in done.stdout
