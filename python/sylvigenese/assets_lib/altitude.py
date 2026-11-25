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

from sylvigenese.commun import ErreurModule
from sylvigenese.assets_lib.repere import LAMBERT93


def _bilineaire(tableau: np.ndarray, nodata, colonne: np.ndarray, ligne: np.ndarray, nom: str) -> np.ndarray:
    """Interpolation bilinéaire ; colonne et ligne en pixels, centres de pixel aux demi-entiers.

    Au bord (moins d'un demi-pixel), on prolonge la valeur du bord (pas d'extrapolation).
    """
    hauteur, largeur = tableau.shape
    c = np.clip(colonne - 0.5, 0, largeur - 1)
    r = np.clip(ligne - 0.5, 0, hauteur - 1)
    c0 = np.minimum(np.floor(c).astype(int), largeur - 2) if largeur > 1 else np.zeros_like(c, int)
    r0 = np.minimum(np.floor(r).astype(int), hauteur - 2) if hauteur > 1 else np.zeros_like(r, int)
    c1 = np.minimum(c0 + 1, largeur - 1)
    r1 = np.minimum(r0 + 1, hauteur - 1)
    fc, fr = c - c0, r - r0
    coins = [tableau[r0, c0], tableau[r0, c1], tableau[r1, c0], tableau[r1, c1]]
    poids = [(1 - fc) * (1 - fr), fc * (1 - fr), (1 - fc) * fr, fc * fr]
    invalide = np.zeros(c.shape, dtype=bool)
    for valeur, poids_i in zip(coins, poids):
        manque = ~np.isfinite(valeur) | ((valeur == nodata) if nodata is not None else False)
        invalide |= manque & (poids_i > 0)
    if invalide.any():
        raise ErreurModule(f"{nom} : {int(invalide.sum())} arbre(s) sur une cellule sans valeur (nodata) ; "
                           "altitude non devinée, à corriger dans prepare")
    return sum(valeur.astype("float64") * poids_i for valeur, poids_i in zip(coins, poids))


def lire_altitude_ngf(chemin_mnt: Path, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Altitude NGF-IGN69 (m) du MNT en chaque point (x est, y nord, EPSG:2154)."""
    if not Path(chemin_mnt).is_file():
        raise ErreurModule(f"MNT introuvable : {chemin_mnt} (sortie de prepare)")
    with rasterio.open(chemin_mnt) as src:
        if src.crs is None or src.crs.to_epsg() != 2154:
            raise ErreurModule(f"{chemin_mnt} : EPSG:2154 attendu")
        tableau = src.read(1, masked=False).astype("float64")
        inv = ~src.transform
        colonne, ligne = inv @ (np.asarray(x), np.asarray(y))
        hors = (colonne < 0) | (colonne > src.width) | (ligne < 0) | (ligne > src.height)
        if hors.any():
            raise ErreurModule(f"{int(hors.sum())} arbre(s) hors de l'emprise du MNT {chemin_mnt}")
        return _bilineaire(tableau, src.nodata, np.asarray(colonne), np.asarray(ligne), "dtm.tif")


def ondulation_raf20(chemin_raf20: Path, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ondulation N (m) de la grille RAF20 en chaque point : h_ellipsoïdale = H_NGF + N."""
    if not Path(chemin_raf20).is_file():
        raise ErreurModule(f"grille RAF20 introuvable : {chemin_raf20} (external.raf20_grid de config.yml)")
    lon, lat = warp_transform(LAMBERT93, "EPSG:4326", np.asarray(x).tolist(), np.asarray(y).tolist())
    with rasterio.open(chemin_raf20) as src:
        tableau = src.read(1).astype("float64")
        colonne, ligne = (~src.transform) @ (np.asarray(lon), np.asarray(lat))
        hors = (colonne < 0) | (colonne > src.width) | (ligne < 0) | (ligne > src.height)
        if hors.any():
            raise ErreurModule(f"{int(hors.sum())} arbre(s) hors de la grille RAF20 {chemin_raf20}")
        return _bilineaire(tableau, src.nodata, np.asarray(colonne), np.asarray(ligne), "RAF20")
