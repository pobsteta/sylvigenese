"""Stade d'un arbre : une seule fonction, les seuils d'un seul fichier.

Étape du BRIEF codée : §6 (les quatre stades `young`, `pole`, `mature`, `old`, d'après la position de la
hauteur sur la courbe de hauteur) et, pour l'arbre et non plus le peuplement, l'extension décidée par
Pascal le 26/11/2026 (Q8, ADR 0007 choix 9) : stade d'un arbre = h / h_pot de l'arbre, avec les seuils de
`biomes/stades/stage_breaks.yml` (contrat `biomes.stage_breaks`, provisoire). Mission 070.

- Une seule copie des seuils : ce fichier. Aucune valeur n'est écrite dans ce module.
- Borne basse incluse, comme `findInterval` de `R/biomes.R` : un rapport égal à un seuil est dans le stade
  du dessus. Un rapport au-dessus de 1 (hauteur au-dessus du plafond) est le stade le plus âgé : la hauteur
  n'est jamais corrigée (BRIEF §6, décision du 24/11/2026).
- Plafond h_pot : `site_potential.tif` (grille de 25 m, une bande) à la cellule de l'arbre. Un plafond
  absent, nul ou hors de la grille est une erreur nommée : aucun stade n'est deviné.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import yaml

from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[3]
BREAKS_FILE = ROOT / "biomes" / "stades" / "stage_breaks.yml"
STAGES = ("young", "pole", "mature", "old")


def load_breaks(path: Path | None = None) -> tuple[float, float, float]:
    """Les trois seuils de `biomes/stades/stage_breaks.yml` ; fichier absent ou mal formé : erreur."""
    path = Path(path) if path else BREAKS_FILE
    if not path.is_file():
        raise ModuleError(f"seuils des stades introuvables : {path} (contrat biomes.stage_breaks)")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ModuleError(f"{path} illisible : {error}") from error
    if not isinstance(doc, dict) or doc.get("stages") != list(STAGES):
        raise ModuleError(f"{path} : `stages` doit être {list(STAGES)}")
    breaks = doc.get("breaks")
    ok = (isinstance(breaks, list) and len(breaks) == 3
          and all(isinstance(b, (int, float)) and not isinstance(b, bool) for b in breaks)
          and breaks[0] < breaks[1] < breaks[2])
    if not ok:
        raise ModuleError(f"{path} : `breaks` doit être trois nombres strictement croissants")
    return float(breaks[0]), float(breaks[1]), float(breaks[2])


def stage_of(h, h_pot, breaks: tuple[float, float, float] | None = None) -> np.ndarray:
    """Stade de chaque arbre (tableau de chaînes) d'après h / h_pot. Fonction unique du stade d'un arbre.

    `h` et `h_pot` en mètres, scalaires ou tableaux de même longueur. Un plafond absent (NaN), nul ou négatif,
    ou une hauteur absente : erreur (jamais de stade deviné)."""
    breaks = breaks or load_breaks()
    h = np.atleast_1d(np.asarray(h, dtype="float64"))
    h_pot = np.broadcast_to(np.atleast_1d(np.asarray(h_pot, dtype="float64")), h.shape)
    bad = ~np.isfinite(h) | ~np.isfinite(h_pot) | (h_pot <= 0)
    if bad.any():
        raise ModuleError(f"stade indéterminé pour {int(bad.sum())} arbre(s) : hauteur ou plafond de la station "
                          "(site_potential.tif) absent ou nul ; aucun stade n'est deviné")
    rank = np.searchsorted(np.asarray(breaks), h / h_pot, side="right")   # borne basse incluse
    return np.array(STAGES, dtype=object)[rank]


def ceiling_at(zone: Path, x, y) -> np.ndarray:
    """Plafond de hauteur (h_pot, m) de `site_potential.tif` à la cellule de chaque point (EPSG:2154)."""
    path = Path(zone) / "site_potential.tif"
    if not path.is_file():
        raise ModuleError(f"{path} introuvable : le stade d'un arbre vient de h / h_pot (sortie de prepare)")
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ModuleError(f"{path} a {src.count} bandes : le plafond d'une cellule ne se choisit pas seul")
        array = src.read(1).astype("float64")
        nodata = src.nodata
        column, row = (~src.transform) @ (np.asarray(x, dtype="float64"), np.asarray(y, dtype="float64"))
    column, row = np.floor(column).astype(int), np.floor(row).astype(int)
    outside = (column < 0) | (column >= array.shape[1]) | (row < 0) | (row >= array.shape[0])
    if outside.any():
        raise ModuleError(f"{int(outside.sum())} arbre(s) hors de la grille de {path.name} : plafond inconnu")
    values = array[np.clip(row, 0, array.shape[0] - 1), np.clip(column, 0, array.shape[1] - 1)]
    if nodata is not None:
        values = np.where(values == nodata, np.nan, values)
    return values


def tree_stages(zone: Path, x, y, h, breaks: tuple[float, float, float] | None = None) -> np.ndarray:
    """Stade de chaque arbre d'une zone : h de l'arbre, h_pot de sa cellule, seuils du fichier unique."""
    return stage_of(h, ceiling_at(zone, x, y), breaks)
