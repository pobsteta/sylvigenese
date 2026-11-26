#!/usr/bin/env python3
"""Ordres de grandeur IFN de la surface terrière (G, m²/ha) et des tiges/ha, par placette.

Référentiel : docs/referentiels/ifn-g-tiges.md (décision éclairée : bornes du critère M3b de
docs/spec.md §11, « surface terrière et tiges par hectare entre les quantiles 5 et 95 % de l'IFN »,
et recalage du jeu fictif).

ÉTAT : écrit par l'acquéreur le 2026-11-26, JAMAIS EXÉCUTÉ (pas d'outil d'exécution dans sa
session). À lancer d'abord avec --self-test, puis sur l'export réel.

Données (hors dépôt, sous data/) :
    https://inventaire-forestier.ign.fr/dataifn/data/export_dataifn_2005_2025.zip
    (mise à jour du 07/10/2026, Licence Ouverte Etalab 2.0), à poser par exemple dans
    data/ifn/export_dataifn_2005_2025.zip. Le script lit l'archive sans la décompresser.

Usage :
    python3 -I tools/referentiels/ifn_g_tiges.py --self-test
    python3 -I tools/referentiels/ifn_g_tiges.py --export data/ifn/export_dataifn_2005_2025.zip \
        --csv docs/referentiels/ifn-g-tiges.csv

Calcul (sources : IGN_DB_documentation_generale.pdf v3.0 p. 9 ; IGN_DB_doc_arbre.pdf v2.4 p. 1, 7, 9 ;
metadonnees.csv de l'archive de documentation 2025) :
  - placette retenue : CAMPAGNE dans la période, VISITE = 1, CSA dans {1 boisée fermée,
    3 boisée ouverte} (5 = peupleraie, exclue par défaut), PEUPNR = 0 (peuplement recensable) ;
  - arbre retenu : VEGET = 0 (vivant sur pied), C13 >= 0,235 m (D13 >= 7,5 cm) ;
  - g d'un arbre = C13² / (4 π) (m², C13 en mètres) ; G/ha = Σ W·g ; tiges/ha = Σ W, où W est le
    poids de l'arbre fourni par l'IGN (88,4 / 39,3 / 14,1 pour les cercles de 6, 9, 15 m, corrigé
    en lisière) ;
  - dg_cm = 100 × sqrt(4 G / (π N)) (diamètre quadratique moyen de la placette).
  - Les quantiles portent sur les placettes, SANS poids de point : l'IGN ne les publie pas
    (documentation générale p. 2). Ce ne sont donc pas des estimations d'inventaire.

Types de peuplement : convention de l'acquéreur, PROVISOIRE, à valider par Pascal (elle imite la
règle « pur si une essence fait au moins 75 % » des tableaux IGN, mais sur la part de G et non sur
le couvert libre relatif) ; « taillis » = au moins 75 % des tiges/ha issues de rejet (ORI = 0).
"""
import argparse
import csv
import io
import math
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

PERIOD = (2021, 2025)          # 5 dernières campagnes de l'export du 07/10/2026
C13_MIN_M = 0.235              # seuil de recensabilité (IGN_DB_doc_arbre.pdf p. 1 et 7)
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
N_MIN = 30                     # effectif minimal pour publier des quantiles (convention, provisoire)
PURE_SHARE = 0.75              # convention provisoire (voir l'en-tête)
COPPICE_SHARE = 0.75           # convention provisoire (voir l'en-tête)
SOURCE_TAG = "DataIFN calcul (tools/referentiels/ifn_g_tiges.py)"
SOURCE_URL = "https://inventaire-forestier.ign.fr/dataifn/data/export_dataifn_2005_2025.zip"

# Codes ESPAR1 lus dans metadonnees.csv (lignes 4441-4586) ; regroupement = convention provisoire.
SPECIES_GROUPS = {
    "chenaie": {"02", "03", "04", "05", "07"},                 # chênes caducifoliés
    "chenaie_sempervirente": {"06", "08P", "08S"},            # chêne vert, chênes-lièges
    "hetraie": {"09"},
    "sapiniere_pessiere": {"61", "62"},                        # sapin pectiné, épicéa commun
    "pinede": {"51", "52", "53CO", "53CA", "53S", "54", "55", "56", "57A", "57B", "58",
               "59", "60", "68PM", "68PC", "77"},
    "douglas": {"64"},
}

PLOT_COLUMNS = ("CAMPAGNE", "IDP", "VISITE", "CSA", "PEUPNR", "GRECO", "SER")
TREE_COLUMNS = ("CAMPAGNE", "IDP", "C13", "W", "VEGET", "ESPAR", "ORI")


class InputError(Exception):
    """Entrée refusée : message en français, jamais de valeur par défaut silencieuse."""


def parse_number(text):
    text = (text or "").strip()
    if not text:
        return None
    return float(text.replace(",", "."))


def normalise_code(text):
    """ESPAR '2' et '02' désignent la même essence (espar-cdref13.csv écrit '9' pour '09')."""
    text = (text or "").strip()
    return text.zfill(2) if text.isdigit() else text


def open_table(export, name, encoding):
    """Ouvre <name>.csv dans une archive zip ou un dossier ; erreur explicite sinon."""
    export = Path(export)
    if export.is_dir():
        hits = [p for p in export.rglob("*") if p.name.upper() == f"{name}.CSV"]
        if len(hits) != 1:
            raise InputError(f"{name}.csv : {len(hits)} fichier(s) trouvé(s) sous {export}, 1 attendu")
        return open(hits[0], encoding=encoding, newline="")
    archive = zipfile.ZipFile(export)
    hits = [m for m in archive.namelist() if Path(m).name.upper() == f"{name}.CSV"]
    if len(hits) != 1:
        raise InputError(f"{name}.csv : {len(hits)} membre(s) dans {export}, 1 attendu")
    return io.TextIOWrapper(archive.open(hits[0]), encoding=encoding, newline="")


def check_columns(reader, needed, name):
    missing = [c for c in needed if c not in (reader.fieldnames or [])]
    if missing:
        raise InputError(f"{name}.csv : colonnes absentes {missing}")


def read_plots(handle, period, visits, cover_codes):
    reader = csv.DictReader(handle, delimiter=";")
    check_columns(reader, PLOT_COLUMNS, "PLACETTE")
    plots, report = {}, defaultdict(int)
    for row in reader:
        year = int(row["CAMPAGNE"])
        if not period[0] <= year <= period[1]:
            continue
        report["placettes_periode"] += 1
        if row["VISITE"].strip() not in visits:
            report["exclues_visite"] += 1
            continue
        if row["CSA"].strip() not in cover_codes:
            report["exclues_csa"] += 1
            continue
        if row["PEUPNR"].strip() != "0":
            report["exclues_peupnr"] += 1
            continue
        key = (year, row["IDP"].strip())
        if key in plots:
            raise InputError(f"PLACETTE.csv : doublon (CAMPAGNE, IDP) = {key}")
        plots[key] = {"greco": row["GRECO"].strip(), "ser": row["SER"].strip(),
                      "n": 0.0, "g": 0.0, "n_coppice": 0.0, "g_group": defaultdict(float),
                      "trees": 0}
    report["placettes_retenues"] = len(plots)
    return plots, report


def read_trees(handle, plots, live_codes, report):
    reader = csv.DictReader(handle, delimiter=";")
    check_columns(reader, TREE_COLUMNS, "ARBRE")
    for row in reader:
        key = (int(row["CAMPAGNE"]), row["IDP"].strip())
        plot = plots.get(key)
        if plot is None:
            continue
        if row["VEGET"].strip() not in live_codes:
            report["arbres_non_vivants"] += 1
            continue
        c13, w = parse_number(row["C13"]), parse_number(row["W"])
        if c13 is None or w is None:
            report["arbres_sans_c13_ou_w (signalés, exclus)"] += 1
            continue
        if c13 > 20:
            raise InputError(f"ARBRE.csv : C13 = {c13} pour {key} ; l'export est en mètres "
                             "(metadonnees.csv l. 35) : unité à vérifier")
        if c13 < C13_MIN_M:
            report["arbres_sous_seuil (signalés, exclus)"] += 1
            continue
        g = w * c13 * c13 / (4.0 * math.pi)
        plot["n"] += w
        plot["g"] += g
        plot["trees"] += 1
        if row["ORI"].strip() == "0":
            plot["n_coppice"] += w
        species = normalise_code(row["ESPAR"])
        group = next((name for name, codes in SPECIES_GROUPS.items() if species in codes), "autre")
        plot["g_group"][group] += g
        report["arbres_retenus"] += 1


def stand_type(plot):
    if plot["g"] <= 0.0:
        return "sans_arbre_recensable"
    group, g_max = max(plot["g_group"].items(), key=lambda kv: kv[1])
    if g_max / plot["g"] >= PURE_SHARE and group != "autre":
        return group
    return "melange_ou_autre"


def quantile(sorted_values, q):
    """Quantile de type 7 (interpolation linéaire, défaut de R et de numpy)."""
    pos = (len(sorted_values) - 1) * q
    low = math.floor(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def summarise(plots):
    """Rend {(perimetre, code, peuplement): [placettes]}."""
    groups = defaultdict(list)
    for plot in plots.values():
        kind = stand_type(plot)
        coppice = plot["g"] > 0 and plot["n_coppice"] / plot["n"] >= COPPICE_SHARE
        groups[("france", "FR", "toutes_placettes")].append(plot)
        if plot["g"] <= 0:
            continue
        for perimeter, code in (("france", "FR"), ("greco", plot["greco"])):
            groups[(perimeter, code, "tous_types")].append(plot)
            groups[(perimeter, code, kind)].append(plot)
            if coppice:
                groups[(perimeter, code, "taillis")].append(plot)
        groups[("ser", plot["ser"], "tous_types")].append(plot)
    return groups


def rows_for(groups, period, filters):
    rows = []
    for (perimeter, code, kind), members in sorted(groups.items()):
        n = len(members)
        series = {
            "g_m2_ha": sorted(p["g"] for p in members),
            "tiges_ha": sorted(p["n"] for p in members),
            "dg_cm": sorted(100 * math.sqrt(4 * p["g"] / (math.pi * p["n"]))
                            for p in members if p["n"] > 0),
        }
        for quantity, values in series.items():
            stats = [("moyenne", sum(values) / len(values) if values else None)]
            stats += [(f"q{round(q * 100):02d}", quantile(values, q) if values else None)
                      for q in QUANTILES]
            for stat, value in stats:
                too_few = len(values) < N_MIN
                rows.append({
                    "perimetre": perimeter, "code": code, "peuplement": kind,
                    "grandeur": quantity, "statistique": stat,
                    "valeur": "" if (value is None or too_few) else f"{value:.1f}",
                    "n_placettes": len(values), "periode": f"{period[0]}-{period[1]}",
                    "source": SOURCE_TAG, "url_ou_page": SOURCE_URL, "filtre": filters,
                    "note": f"effectif < {N_MIN} : non publié" if too_few else "",
                })
    return rows


FIELDS = ("perimetre", "code", "peuplement", "grandeur", "statistique", "valeur", "n_placettes",
          "periode", "source", "url_ou_page", "filtre", "note")


def merge_into(csv_path, new_rows):
    """Remplace les lignes de ce script dans le référentiel ; garde les autres sources."""
    kept = []
    if csv_path.exists():
        with open(csv_path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise InputError(f"{csv_path} : en-tête inattendu {reader.fieldnames}")
            kept = [r for r in reader if r["source"] != SOURCE_TAG]
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept + new_rows)


def run(export, csv_path, period, visits, cover_codes, live_codes, encoding):
    with open_table(export, "PLACETTE", encoding) as handle:
        plots, report = read_plots(handle, period, visits, cover_codes)
    with open_table(export, "ARBRE", encoding) as handle:
        read_trees(handle, plots, live_codes, report)
    filters = (f"VISITE in {sorted(visits)} ; CSA in {sorted(cover_codes)} ; PEUPNR = 0 ; "
               f"VEGET in {sorted(live_codes)} ; C13 >= {C13_MIN_M} m")
    rows = rows_for(summarise(plots), period, filters)
    if csv_path is not None:
        merge_into(Path(csv_path), rows)
    for name, count in sorted(report.items()):
        print(f"{name} : {count}", file=sys.stderr)
    return rows, report


def self_test():
    """Contrôle à la main : 1 placette, 2 arbres. Lève AssertionError en cas d'écart."""
    plac = ("CAMPAGNE;IDP;VISITE;CSA;PEUPNR;GRECO;SER\n"
            "2023;1;1;1;0;B;B41\n2023;2;1;5;0;B;B41\n2019;3;1;1;0;B;B41\n")
    arbre = ("CAMPAGNE;IDP;C13;W;VEGET;ESPAR;ORI\n"
             f"2023;1;{math.pi * 0.30:.6f};39.29;0;09;1\n"     # hêtre, d = 30 cm, cercle de 9 m
             f"2023;1;{math.pi * 0.10:.6f};88.42;0;9;0\n"      # hêtre, d = 10 cm, cercle de 6 m
             "2023;1;0.200;88.42;0;09;1\n"                     # sous le seuil : exclu
             "2023;1;1.000;14.15;5;09;1\n")                    # mort : exclu
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("export/PLACETTE.csv", plac)
        archive.writestr("export/ARBRE.csv", arbre)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "export.zip"
        path.write_bytes(buffer.getvalue())
        rows, report = run(path, None, PERIOD, {"1"}, {"1", "3"}, {"0"}, "utf-8")
    expected_g = 39.29 * math.pi / 4 * 0.30 ** 2 + 88.42 * math.pi / 4 * 0.10 ** 2  # 3,472 m²/ha
    expected_n = 39.29 + 88.42
    assert report["placettes_retenues"] == 1, report
    assert report["exclues_csa"] == 1, report
    assert report["arbres_sous_seuil (signalés, exclus)"] == 1, report
    assert report["arbres_non_vivants"] == 1, report
    # n = 1 < N_MIN : la valeur n'est pas publiée, mais la ligne existe avec son effectif.
    hetraie = [r for r in rows if r["peuplement"] == "hetraie" and r["perimetre"] == "france"]
    assert hetraie and all(r["valeur"] == "" and r["n_placettes"] == 1 for r in hetraie), hetraie
    plots, _ = read_plots(io.StringIO(plac), PERIOD, {"1"}, {"1", "3"})
    read_trees(io.StringIO(arbre), plots, {"0"}, defaultdict(int))
    plot = plots[(2023, "1")]
    assert abs(plot["g"] - expected_g) < 1e-3, (plot["g"], expected_g)
    assert abs(plot["n"] - expected_n) < 1e-9, (plot["n"], expected_n)
    assert stand_type(plot) == "hetraie"
    assert abs(quantile([0.0, 10.0], 0.95) - 9.5) < 1e-12
    print(f"self-test : OK (G = {plot['g']:.3f} m²/ha, N = {plot['n']:.2f} tiges/ha)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", help="archive export_dataifn_2005_2025.zip ou dossier décompressé")
    parser.add_argument("--csv", help="référentiel à mettre à jour (docs/referentiels/ifn-g-tiges.csv)")
    parser.add_argument("--first", type=int, default=PERIOD[0])
    parser.add_argument("--last", type=int, default=PERIOD[1])
    parser.add_argument("--with-second-visits", action="store_true",
                        help="ajoute VISITE = 2 (contenu d'une ligne 2e visite non vérifié)")
    parser.add_argument("--with-poplars", action="store_true", help="ajoute CSA = 5 (peupleraies)")
    parser.add_argument("--with-windthrow", action="store_true", help="ajoute VEGET = 1 (chablis vivant)")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not args.export:
        parser.error("--export est requis (ou --self-test)")
    try:
        run(args.export, args.csv, (args.first, args.last),
            {"1", "2"} if args.with_second_visits else {"1"},
            {"1", "3", "5"} if args.with_poplars else {"1", "3"},
            {"0", "1"} if args.with_windthrow else {"0"}, args.encoding)
    except (InputError, UnicodeDecodeError) as error:
        print(f"Entrée refusée : {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
