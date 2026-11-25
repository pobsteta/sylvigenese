"""Repère des tuiles 3D : de l'EPSG:2154 (x est, y nord, altitude) vers l'ECEF, par un repère local.

Étape du BRIEF codée : §9 de la spec (3D Tiles 1.1, altitude NGF-IGN69 convertie en hauteur
ellipsoïdale avec la grille RAF20).

Choix du repère (mission 028, à relire par Pascal)
--------------------------------------------------
- Chaque tuile 3D Tiles porte un `transform` (matrice 4 x 4, colonnes) qui passe de son repère
  local à l'ECEF (EPSG:4978, WGS84 géocentrique, le repère de 3D Tiles et d'iTowns).
- Le repère local d'une tuile est un repère « est, nord, haut » (ENU) tangent à l'ellipsoïde
  au centre de la tuile : x local = est, y local = nord, z local = haut (3D Tiles est Z haut).
- Les positions des arbres sont donc de petits nombres (quelques centaines de mètres) : un
  accesseur glTF en Float32 les garde au centimètre, ce qu'une écriture directe en ECEF
  (nombres de 6 000 km) ne ferait pas.
- Le passage EPSG:2154 -> ECEF est celui de PROJ (via GDAL, par rasterio), point par point :
  la courbure de la Terre est donc exacte, pas une approximation plane.
- Le contenu glTF est en Y haut (glTF 2.0) ; 3D Tiles 1.1 demande que le client passe de Y haut
  à Z haut (rotation de +90° autour de x). Un point local (est e, nord n, haut u) s'écrit donc
  en glTF (x, y, z) = (e, u, -n).
- WGS84 (EPSG:4978) et RGF93 diffèrent d'au plus quelques décimètres : écart négligé et dit.
"""

from __future__ import annotations

import numpy as np
from rasterio.warp import transform as warp_transform

LAMBERT93 = "EPSG:2154"
ECEF = "EPSG:4978"
WGS84 = "EPSG:4326"


def lambert_vers_ecef(x, y, z_ellipsoide) -> np.ndarray:
    """EPSG:2154 (x est, y nord) et hauteur ellipsoïdale (m) -> ECEF, tableau (n, 3) en mètres."""
    x, y, z = (np.atleast_1d(np.asarray(v, dtype="float64")) for v in (x, y, z_ellipsoide))
    xs, ys, zs = warp_transform(LAMBERT93, ECEF, x.tolist(), y.tolist(), z.tolist())
    return np.column_stack([xs, ys, zs])


def lambert_vers_lonlat(x, y) -> np.ndarray:
    """EPSG:2154 -> (longitude, latitude) en degrés, tableau (n, 2)."""
    x, y = (np.atleast_1d(np.asarray(v, dtype="float64")) for v in (x, y))
    lon, lat = warp_transform(LAMBERT93, WGS84, x.tolist(), y.tolist())
    return np.column_stack([lon, lat])


def axes_enu(lon_deg: float, lat_deg: float) -> np.ndarray:
    """Matrice 3 x 3 dont les colonnes sont l'est, le nord et le haut (en ECEF) en ce point."""
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    est = np.array([-np.sin(lon), np.cos(lon), 0.0])
    nord = np.array([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)])
    haut = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    return np.column_stack([est, nord, haut])


class RepereLocal:
    """Repère est-nord-haut tangent en un point donné par (x, y) Lambert-93 et une hauteur ellipsoïdale."""

    def __init__(self, x: float, y: float, z_ellipsoide: float):
        self.origine = lambert_vers_ecef(x, y, z_ellipsoide)[0]
        lon, lat = lambert_vers_lonlat(x, y)[0]
        self.axes = axes_enu(lon, lat)

    def transform_3dtiles(self) -> list[float]:
        """Matrice 4 x 4 du `transform` d'une tuile 3D Tiles : 16 nombres, colonne après colonne."""
        m = np.eye(4)
        m[:3, :3] = self.axes
        m[:3, 3] = self.origine
        return [float(v) for v in m.T.reshape(-1)]

    def ecef_vers_local(self, ecef: np.ndarray) -> np.ndarray:
        """ECEF (n, 3) -> (est, nord, haut) (n, 3), en mètres, dans ce repère."""
        return (np.asarray(ecef, dtype="float64") - self.origine) @ self.axes

    def lambert_vers_local(self, x, y, z_ellipsoide) -> np.ndarray:
        """EPSG:2154 + hauteur ellipsoïdale -> (est, nord, haut) local, tableau (n, 3)."""
        return self.ecef_vers_local(lambert_vers_ecef(x, y, z_ellipsoide))


def local_vers_gltf(enu: np.ndarray) -> np.ndarray:
    """(est, nord, haut) -> (x, y, z) glTF Y haut : (e, u, -n)."""
    enu = np.asarray(enu, dtype="float64")
    return np.column_stack([enu[:, 0], enu[:, 2], -enu[:, 1]])


def gltf_vers_local(xyz: np.ndarray) -> np.ndarray:
    """Inverse de `local_vers_gltf` : (x, y, z) glTF -> (est, nord, haut)."""
    xyz = np.asarray(xyz, dtype="float64")
    return np.column_stack([xyz[:, 0], -xyz[:, 2], xyz[:, 1]])


def local_vers_ecef(transform_3dtiles: list[float], enu: np.ndarray) -> np.ndarray:
    """Applique un `transform` de tuile (16 nombres, colonnes) à des points locaux (n, 3)."""
    m = np.array(transform_3dtiles, dtype="float64").reshape(4, 4).T
    enu = np.asarray(enu, dtype="float64")
    return enu @ m[:3, :3].T + m[:3, 3]
