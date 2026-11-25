"""Lecture de l'état initial : arbres de `trees_init/`, groupes d'essences, année affichée.

Étape du BRIEF codée : spec §4 (état initial) et §2 (assets). Mission 028 : tant que `sim/`
n'existe pas, `assets` montre l'état initial ; la lecture de `sim/` viendra avec M3.

Année affichée (spec §4.4 : la hauteur est celle du MNH à la date de vol, avancée jusqu'à t0
par la courbe de hauteur ; `prepare` ne l'avance pas encore, voir `R/prepare_trees.R`) :
- si `simulate.t0` est écrit dans config.yml, c'est lui (l'état initial est l'année 0 de la
  simulation) ;
- sinon, l'année de vol LiDAR la plus fréquente dans `chm_date.tif` (jours depuis 1970-01-01) ;
- sinon : erreur. L'écart entre cette année et les dates de vol est écrit dans les extras.
"""

from __future__ import annotations

import csv
import datetime
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import rasterio

from sylvigenese.commun import ErreurModule

RACINE = Path(__file__).resolve().parents[3]
COLONNES = ["tree_id", "x", "y", "species", "d130", "h", "crown_area"]


def dossier_zone(config: dict) -> Path:
    """Même règle que `prepare_zone_dir` (R) : jeu fictif versionné, sinon data/<zone>.

    `SYLVIGENESE_ROOT` (comme pour `import_tarif`) désigne une autre racine, pour les essais."""
    zone = config.get("zone")
    if not zone:
        raise ErreurModule("config.yml : `zone` manquante")
    racine = Path(os.environ["SYLVIGENESE_ROOT"]) if os.environ.get("SYLVIGENESE_ROOT") else RACINE
    return racine / "tests" / "fixtures" / "zone_fictive" if zone == "zone_fictive" else racine / "data" / zone


def groupes_essences(chemin: Path | None = None) -> dict[str, str]:
    """espar -> groupe (`feuillu` ou `resineux`), lu dans contracts/species.csv."""
    chemin = chemin or RACINE / "contracts" / "species.csv"
    with open(chemin, encoding="utf-8", newline="") as f:
        return {ligne["espar"]: ligne["groupe"] for ligne in csv.DictReader(f)}


def lire_arbres(zone: Path) -> dict[str, np.ndarray]:
    """Lit `trees_init/` : colonnes en tableaux numpy, triées par tree_id (ordre stable)."""
    dossier = zone / "trees_init"
    fichier = dossier / "trees.parquet"
    if not fichier.is_file():
        raise ErreurModule(f"état initial : {fichier} introuvable (lancer prepare, biomes puis trees)")
    table = pq.read_table(fichier, columns=COLONNES)
    if table.num_rows == 0:
        raise ErreurModule(f"état initial : {fichier} ne contient aucun arbre")
    ids = table.column("tree_id").to_pylist()
    doubles = sorted({i for i in ids if ids.count(i) > 1}) if len(set(ids)) != len(ids) else []
    if doubles:
        raise ErreurModule(f"état initial : tree_id en double dans trees_init ({len(doubles)}, par exemple {doubles[0]}) ; "
                           "un tree_id doit être unique")
    ordre = np.argsort(np.array(table.column("tree_id").to_pylist(), dtype=object), kind="stable")
    arbres = {}
    for nom in COLONNES:
        valeurs = table.column(nom).to_numpy(zero_copy_only=False) if nom != "tree_id" and nom != "species" \
            else np.array(table.column(nom).to_pylist(), dtype=object)
        arbres[nom] = valeurs[ordre]
    return arbres


def groupe_de_chaque_arbre(especes: np.ndarray, table: dict[str, str]) -> np.ndarray:
    """Groupe de chaque arbre ; essence absente de species.csv ou groupe inconnu : erreur explicite."""
    inconnues = sorted({e for e in set(especes.tolist()) if e not in table})
    if inconnues:
        raise ErreurModule(f"essence(s) absente(s) de contracts/species.csv : {', '.join(inconnues)}")
    groupes = np.array([table[e] for e in especes.tolist()], dtype=object)
    hors = sorted({g for g in set(groupes.tolist()) if g not in ("feuillu", "resineux")})
    if hors:
        raise ErreurModule(f"groupe d'essences sans modèle générique : {', '.join(hors)}")
    return groupes


def annee_vol(chm_date: Path) -> tuple[int, dict[int, int], str, str]:
    """Année de vol la plus fréquente de chm_date.tif ; rend (année, effectifs, date min, date max)."""
    with rasterio.open(chm_date) as src:
        a = src.read(1)
        nodata = src.nodata
    valeurs = a[a != nodata] if nodata is not None else a.reshape(-1)
    if valeurs.size == 0:
        raise ErreurModule(f"{chm_date} : aucune date de vol")
    epoque = datetime.date(1970, 1, 1)
    annees = Counter()
    for jours, n in zip(*np.unique(valeurs, return_counts=True)):
        annees[(epoque + datetime.timedelta(days=int(jours))).year] += int(n)
    annee = sorted(annees.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    dmin = (epoque + datetime.timedelta(days=int(valeurs.min()))).isoformat()
    dmax = (epoque + datetime.timedelta(days=int(valeurs.max()))).isoformat()
    return annee, dict(sorted(annees.items())), dmin, dmax


def annee_affichee(config: dict, zone: Path) -> tuple[int, str]:
    """(année, phrase d'origine) selon la règle du module."""
    t0 = (config.get("simulate") or {}).get("t0")
    chm = zone / "chm_date.tif"
    if t0 is not None:
        return int(t0), f"t0 de config.yml ({t0})"
    if chm.is_file():
        annee, effectifs, dmin, dmax = annee_vol(chm)
        return annee, (f"année de vol LiDAR la plus fréquente de chm_date.tif ({annee} ; vols du {dmin} au {dmax}, "
                       f"cellules par année : {effectifs}) ; hauteurs non avancées jusqu'à t0")
    raise ErreurModule("année affichée indéterminée : ni `simulate.t0` dans config.yml ni chm_date.tif")
