"""Altitude du pied des arbres : MNT (NGF-IGN69) + ondulation RAF20 = hauteur ellipsoïdale.

Étape du BRIEF codée : spec §9 (« conversion de l'altitude NGF-IGN69 en hauteur ellipsoïdale
avec la grille RAF20, dont le chemin est donné dans `config.yml`. Si elle manque : erreur »).

Le MNT est `dtm.tif` (grille de 25 m, sortie de `prepare`) ; les arbres de `trees_init` sont
issus du MNH, pas de l'IFN : les lire sur le MNT n'est pas un croisement IFN / raster fin.
L'altitude est interpolée en bilinéaire entre centres de cellule ; un nodata sous un arbre est
une erreur (jamais une altitude devinée).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib.frame import LAMBERT93


def _bilinear(array: np.ndarray, nodata, column: np.ndarray, row: np.ndarray, name: str) -> np.ndarray:
    """Interpolation bilinéaire ; colonne et ligne en pixels, centres de pixel aux demi-entiers.

    Au bord (moins d'un demi-pixel), on prolonge la valeur du bord (pas d'extrapolation).
    """
    height, width = array.shape
    c = np.clip(column - 0.5, 0, width - 1)
    r = np.clip(row - 0.5, 0, height - 1)
    c0 = np.minimum(np.floor(c).astype(int), width - 2) if width > 1 else np.zeros_like(c, int)
    r0 = np.minimum(np.floor(r).astype(int), height - 2) if height > 1 else np.zeros_like(r, int)
    c1 = np.minimum(c0 + 1, width - 1)
    r1 = np.minimum(r0 + 1, height - 1)
    fc, fr = c - c0, r - r0
    coins = [array[r0, c0], array[r0, c1], array[r1, c0], array[r1, c1]]
    weights = [(1 - fc) * (1 - fr), fc * (1 - fr), (1 - fc) * fr, fc * fr]
    invalid = np.zeros(c.shape, dtype=bool)
    for value, weight_i in zip(coins, weights):
        missing = ~np.isfinite(value) | ((value == nodata) if nodata is not None else False)
        invalid |= missing & (weight_i > 0)
    if invalid.any():
        raise ModuleError(f"{name} : {int(invalid.sum())} arbre(s) sur une cellule sans valeur (nodata) ; "
                           "altitude non devinée, à corriger dans prepare")
    return sum(value.astype("float64") * weight_i for value, weight_i in zip(coins, weights))


def read_ngf_altitude(dtm_path: Path, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Altitude NGF-IGN69 (m) du MNT en chaque point (x est, y nord, EPSG:2154)."""
    if not Path(dtm_path).is_file():
        raise ModuleError(f"MNT introuvable : {dtm_path} (sortie de prepare)")
    with rasterio.open(dtm_path) as src:
        if src.crs is None or src.crs.to_epsg() != 2154:
            raise ModuleError(f"{dtm_path} : EPSG:2154 attendu")
        array = src.read(1, masked=False).astype("float64")
        inv = ~src.transform
        column, row = inv @ (np.asarray(x), np.asarray(y))
        outside = (column < 0) | (column > src.width) | (row < 0) | (row > src.height)
        if outside.any():
            raise ModuleError(f"{int(outside.sum())} arbre(s) hors de l'emprise du MNT {dtm_path}")
        return _bilinear(array, src.nodata, np.asarray(column), np.asarray(row), "dtm.tif")


def raf20_undulation(raf20_path: Path, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ondulation N (m) de la grille RAF20 en chaque point : h_ellipsoïdale = H_NGF + N."""
    if not Path(raf20_path).is_file():
        raise ModuleError(f"grille RAF20 introuvable : {raf20_path} (external.raf20_grid de config.yml)")
    lon, lat = warp_transform(LAMBERT93, "EPSG:4326", np.asarray(x).tolist(), np.asarray(y).tolist())
    with rasterio.open(raf20_path) as src:
        array = src.read(1).astype("float64")
        column, row = (~src.transform) @ (np.asarray(lon), np.asarray(lat))
        outside = (column < 0) | (column > src.width) | (row < 0) | (row > src.height)
        if outside.any():
            raise ModuleError(f"{int(outside.sum())} arbre(s) hors de la grille RAF20 {raf20_path}")
        return _bilinear(array, src.nodata, np.asarray(column), np.asarray(row), "RAF20")
