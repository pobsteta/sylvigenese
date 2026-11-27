#!/usr/bin/env python3
"""Correspondance monotone Niinemets -> klighs (mission 083, M5b, 27/11/2026).

Lit hors dépôt (data/sources/regeneration/) : l'annexe A de Niinemets et
Valladares 2006, TreePars2.txt (TreeMig). Vérifie leurs sha256 (INDEX.md) et
refuse de tourner s'ils manquent ou diffèrent. Apparie par code de
contracts/species.csv (correspondance T02-ESP de docs/referentiels/regeneration.md),
ajuste klighs = f(Niinemets) et dit l'erreur.

Aucune valeur par essence n'est écrite dans le dépôt : le détail par essence va
dans un fichier hors dépôt (data/sources/regeneration/derive/), les codes seuls
sont imprimés. Usage : python3 -I bench/m5b/correspondance_klighs.py [--racine .]
Dépendances : numpy, scipy.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

# Nom TreePars2 -> code species.csv (T02-ESP, regeneration.csv, lignes 2 à 31 du fichier).
NOM_VERS_CODE = {
    "Abies_alba": "61", "Larix_decidua": "63", "Picea_abies": "62", "Pinus_cembra": "59",
    "Pinus_montana": "60", "Pinus_silvestris": "52", "Taxus_baccata": "67",
    "Acer_campestre": "21C", "Acer_platanoides": "15P", "Acer_pseudoplatanus": "15S",
    "Alnus_glutinosa": "13G", "Alnus_incana": "13B", "Alnus_viridis": "37",
    "Betula_pendula": "12V", "Carpinus_betulus": "11", "Castanea_sativa": "10",
    "Corylus_avellana": "31", "Fagus_silvatica": "09", "Fraxinus_excelsior": "17C",
    "Populus_nigra": "33N", "Populus_tremula": "24", "Quercus_petraea": "03",
    "Quercus_pubescens": "05", "Quercus_robur": "02", "Salix_alba": "25B",
    "Sorbus_aria": "23AB", "Sorbus_aucuparia": "23SO", "Tilia_cordata": "20P",
    "Tilia_platyphyllos": "20G", "Ulmus_scabra": "18M",
}
SYNONYMES_A_VALIDER = {"60", "37", "18M"}      # exclus de l'ajustement principal
INFRASPECIFIQUES = {"63", "13B", "33N", "03", "23SO"}  # code de sous-espèce, nom d'espèce
# Nom Niinemets quand il diffère du nom TreePars (synonymie, T01-<espar>)
NOM_NIINEMETS = {"Pinus_montana": "Pinus mugo", "Alnus_viridis": "Alnus viridis",
                 "Ulmus_scabra": "Ulmus glabra", "Fagus_silvatica": "Fagus sylvatica",
                 "Pinus_silvestris": "Pinus sylvestris"}
FICHIERS = ["niinemets_appendixA.htm", "TreePars2.txt", "TreeMigDocu_251218_Model.pdf"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verifier(src):
    index = (src / "INDEX.md").read_text(encoding="utf-8")
    for nom in FICHIERS:
        p = src / nom
        if not p.exists():
            sys.exit(f"ERREUR : fichier manquant hors dépôt : {p}")
        attendu = [m for m in re.findall(r"\b[0-9a-f]{64}\b",
                   "\n".join(l for l in index.splitlines()
                             if l.startswith("|") and nom in l.split("|")[1]))]
        if not attendu:
            sys.exit(f"ERREUR : aucun sha256 pour {nom} dans INDEX.md")
        if sha256(p) not in attendu:
            sys.exit(f"ERREUR : sha256 différent de INDEX.md pour {nom}")


def lire_niinemets(p):
    t = p.read_text(encoding="latin-1")
    out = {}
    for r in re.findall(r"<tr>(.*?)</tr>", t, re.S)[1:]:
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip()
             for x in re.findall(r"<td.*?>(.*?)</td>", r, re.S)]
        if len(c) == 9:
            out.setdefault(c[0], float(c[6].split("±")[0]))
    return out


def lire_klighs(p):
    lignes = p.read_text(encoding="utf-8").splitlines()
    en = lignes[0].split("\t")
    i = en.index("klighs")
    return {l.split("\t")[0]: float(l.split("\t")[i]) for l in lignes[1:] if l.strip()}


def apparier(src, racine):
    codes = {r["espar"] for r in csv.DictReader(open(racine / "contracts/species.csv", encoding="utf-8"))}
    nii, kl = lire_niinemets(src / "niinemets_appendixA.htm"), lire_klighs(src / "TreePars2.txt")
    lignes, manque = [], []
    for nom, code in NOM_VERS_CODE.items():
        if code not in codes:
            sys.exit(f"ERREUR : code {code} absent de contracts/species.csv")
        n = nii.get(NOM_NIINEMETS.get(nom, nom.replace("_", " ")))
        if nom not in kl or n is None:
            manque.append(code)
            continue
        lignes.append((code, n, kl[nom]))
    return lignes, manque


def pav_decroissant(x, y):
    """Régression isotone non croissante (PAV), tirée par x croissant."""
    o = np.argsort(x, kind="stable")
    xs, ys = x[o], y[o]
    blocs = []  # [somme, poids]
    for v in -ys:  # non décroissant sur -y
        blocs.append([v, 1.0])
        while len(blocs) > 1 and blocs[-2][0] / blocs[-2][1] > blocs[-1][0] / blocs[-1][1]:
            b = blocs.pop()
            blocs[-1][0] += b[0]
            blocs[-1][1] += b[1]
    fit = np.concatenate([[-b[0] / b[1]] * int(b[1]) for b in blocs])
    return xs, fit


def iso_pred(xs, fit, xnew):
    # interpolation linéaire entre paliers (moyenne des fit aux x égaux)
    ux = np.unique(xs)
    uy = np.array([fit[xs == u].mean() for u in ux])
    return np.interp(xnew, ux, uy)


def logi(x, a, b):
    return 1 + 8 / (1 + np.exp(-(a + b * x)))


def m_lin(x, y):
    c = np.polyfit(x, y, 1)
    return lambda z: np.polyval(c, z), {"pente": c[0], "ordonnee": c[1]}


def m_iso(x, y):
    xs, f = pav_decroissant(x, y)
    return lambda z: iso_pred(xs, f, z), {"paliers": int(len(np.unique(np.round(f, 9))))}


def m_log(x, y):
    p, _ = curve_fit(logi, x, y, p0=[1.0, -0.8], maxfev=20000)
    return lambda z: logi(z, *p), {"a": p[0], "b": p[1]}


def evaluer(nom, ajuster, codes, x, y):
    f, coef = ajuster(x, y)
    res = y - f(x)
    loo = np.empty(len(y))
    for i in range(len(y)):
        m = np.arange(len(y)) != i
        loo[i] = y[i] - ajuster(x[m], y[m])[0](x[i:i + 1])[0]
    pire = [codes[i] for i in np.argsort(-np.abs(loo))[:5]]
    return {"modele": nom, "n": len(y), "coef": {k: round(float(v), 4) for k, v in coef.items()},
            "rmse": round(float(np.sqrt(np.mean(res ** 2))), 3),
            "residu_max": round(float(np.abs(res).max()), 3),
            "rmse_loo": round(float(np.sqrt(np.mean(loo ** 2))), 3),
            "residu_loo_max": round(float(np.abs(loo).max()), 3),
            "plus_mal_predites_loo": pire}, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args()
    racine = Path(a.racine)
    src = racine / "data/sources/regeneration"
    verifier(src)
    lignes, manque = apparier(src, racine)
    print(f"Apparié : {len(lignes)} essences sur 30 ; sans paire : {manque}")
    princ = [l for l in lignes if l[0] not in SYNONYMES_A_VALIDER]
    sens = lignes
    sortie = {}
    for etiquette, jeu in (("principal (hors 3 synonymes à valider)", princ),
                           ("sensibilité (avec 60, 37, 18M)", sens)):
        codes = [l[0] for l in jeu]
        x = np.array([l[1] for l in jeu])
        y = np.array([l[2] for l in jeu])
        print(f"\n== {etiquette} : n = {len(jeu)} ; corrélation de Spearman = "
              f"{np.corrcoef(np.argsort(np.argsort(x)), np.argsort(np.argsort(y)))[0, 1]:.3f}")
        res = []
        for nom, aj in (("lineaire", m_lin), ("isotone", m_iso), ("logistique_bornee_1_9", m_log)):
            r, _ = evaluer(nom, aj, codes, x, y)
            res.append(r)
            print(json.dumps(r, ensure_ascii=False))
        sortie[etiquette] = res
    # fichier détaillé hors dépôt (valeurs par essence : jamais dans le dépôt)
    d = src / "derive"
    d.mkdir(exist_ok=True)
    with open(d / "correspondance_klighs_detail.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["espar", "niinemets", "klighs", "synonyme_a_valider", "infraspecifique"])
        for c, n, k in lignes:
            w.writerow([c, n, k, c in SYNONYMES_A_VALIDER, c in INFRASPECIFIQUES])
    (d / "correspondance_klighs_resultats.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDétail par essence écrit hors dépôt : {d}")


if __name__ == "__main__":
    main()
