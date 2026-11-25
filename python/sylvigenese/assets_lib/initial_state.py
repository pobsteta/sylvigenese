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

from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[3]
COLUMNS = ["tree_id", "x", "y", "species", "d130", "h", "crown_area"]


def zone_dir(config: dict) -> Path:
    """Même règle que `prepare_zone_dir` (R) : jeu fictif versionné, sinon data/<zone>.

    `SYLVIGENESE_ROOT` (comme pour `import_tarif`) désigne une autre racine, pour les essais."""
    zone = config.get("zone")
    if not zone:
        raise ModuleError("config.yml : `zone` manquante")
    root = Path(os.environ["SYLVIGENESE_ROOT"]) if os.environ.get("SYLVIGENESE_ROOT") else ROOT
    return root / "tests" / "fixtures" / "zone_fictive" if zone == "zone_fictive" else root / "data" / zone


def species_groups(path: Path | None = None) -> dict[str, str]:
    """espar -> groupe (`feuillu` ou `resineux`), lu dans contracts/species.csv."""
    path = path or ROOT / "contracts" / "species.csv"
    with open(path, encoding="utf-8", newline="") as f:
        return {row["espar"]: row["groupe"] for row in csv.DictReader(f)}


def read_trees(zone: Path) -> dict[str, np.ndarray]:
    """Lit `trees_init/` : colonnes en tableaux numpy, triées par tree_id (ordre stable)."""
    directory = zone / "trees_init"
    file = directory / "trees.parquet"
    if not file.is_file():
        raise ModuleError(f"état initial : {file} introuvable (lancer prepare, biomes puis trees)")
    table = pq.read_table(file, columns=COLUMNS)
    if table.num_rows == 0:
        raise ModuleError(f"état initial : {file} ne contient aucun arbre")
    ids = table.column("tree_id").to_pylist()
    duplicates = sorted({i for i in ids if ids.count(i) > 1}) if len(set(ids)) != len(ids) else []
    if duplicates:
        raise ModuleError(f"état initial : tree_id en double dans trees_init ({len(duplicates)}, par exemple {duplicates[0]}) ; "
                           "un tree_id doit être unique")
    order = np.argsort(np.array(table.column("tree_id").to_pylist(), dtype=object), kind="stable")
    trees = {}
    for name in COLUMNS:
        values = table.column(name).to_numpy(zero_copy_only=False) if name != "tree_id" and name != "species" \
            else np.array(table.column(name).to_pylist(), dtype=object)
        trees[name] = values[order]
    return trees


def group_of_each_tree(species_codes: np.ndarray, table: dict[str, str]) -> np.ndarray:
    """Groupe de chaque arbre ; essence absente de species.csv ou groupe inconnu : erreur explicite."""
    unknown = sorted({e for e in set(species_codes.tolist()) if e not in table})
    if unknown:
        raise ModuleError(f"essence(s) absente(s) de contracts/species.csv : {', '.join(unknown)}")
    groups = np.array([table[e] for e in species_codes.tolist()], dtype=object)
    outside = sorted({g for g in set(groups.tolist()) if g not in ("feuillu", "resineux")})
    if outside:
        raise ModuleError(f"groupe d'essences sans modèle générique : {', '.join(outside)}")
    return groups


def flight_year(chm_date: Path) -> tuple[int, dict[int, int], str, str]:
    """Année de vol la plus fréquente de chm_date.tif ; rend (année, effectifs, date min, date max)."""
    with rasterio.open(chm_date) as src:
        a = src.read(1)
        nodata = src.nodata
    values = a[a != nodata] if nodata is not None else a.reshape(-1)
    if values.size == 0:
        raise ModuleError(f"{chm_date} : aucune date de vol")
    epoch = datetime.date(1970, 1, 1)
    years = Counter()
    for days, n in zip(*np.unique(values, return_counts=True)):
        years[(epoch + datetime.timedelta(days=int(days))).year] += int(n)
    year = sorted(years.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    date_min = (epoch + datetime.timedelta(days=int(values.min()))).isoformat()
    date_max = (epoch + datetime.timedelta(days=int(values.max()))).isoformat()
    return year, dict(sorted(years.items())), date_min, date_max


def displayed_year(config: dict, zone: Path) -> tuple[int, str]:
    """(année, phrase d'origine) selon la règle du module."""
    t0 = (config.get("simulate") or {}).get("t0")
    chm = zone / "chm_date.tif"
    if t0 is not None:
        return int(t0), f"t0 de config.yml ({t0})"
    if chm.is_file():
        year, year_counts, date_min, date_max = flight_year(chm)
        return year, (f"année de vol LiDAR la plus fréquente de chm_date.tif ({year} ; vols du {date_min} au {date_max}, "
                       f"cellules par année : {year_counts}) ; hauteurs non avancées jusqu'à t0")
    raise ModuleError("année affichée indéterminée : ni `simulate.t0` dans config.yml ni chm_date.tif")
