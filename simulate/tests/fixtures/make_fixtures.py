"""Régénère les fichiers d'essai GeoTIFF de la mission 015 (valeurs synthétiques, sans sens écologique).

Usage : python3 simulate/tests/fixtures/make_fixtures.py   (rasterio) ;
        Rscript simulate/tests/fixtures/make_fixtures_terra.R   (terra)

Ordre des axes : x = est, y = nord, EPSG:2154. Coin nord-ouest (700000 ; 6501000).
Valeur au pixel (ligne l, colonne c) de la bande b : 1000 b + 0,5 l + 0,25 c  (Float32)
ou (7 l + 3 c + 100 b) mod 60000 (UInt16). Nodata : -9999 (Float32), 65535 (UInt16).
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

DOSSIER = Path(__file__).resolve().parent
LARGEUR, HAUTEUR = 300, 270  # deux colonnes et deux lignes de tuiles de 256 : bords coupés
TRANSFORM = from_origin(700000.0, 6501000.0, 25.0, 25.0)

PROFIL_OK = dict(driver="GTiff", tiled=True, blockxsize=256, blockysize=256, interleave="band",
                 compress="deflate")


def valeurs(bandes, flottant):
    ligne, colonne = np.mgrid[0:HAUTEUR, 0:LARGEUR]
    piles = []
    for b in range(bandes):
        if flottant:
            piles.append((1000 * b + 0.5 * ligne + 0.25 * colonne).astype("float32"))
        else:
            piles.append(((7 * ligne + 3 * colonne + 100 * b) % 60000).astype("uint16"))
    return np.stack(piles)


def ecrire(nom, bandes=1, flottant=True, crs="EPSG:2154", **options):
    donnees = valeurs(bandes, flottant)
    profil = dict(PROFIL_OK)
    profil.update(options)
    profil.update(width=LARGEUR, height=HAUTEUR, count=bandes, crs=crs, transform=TRANSFORM,
                  dtype=donnees.dtype, nodata=-9999.0 if flottant else 65535)
    if crs != "EPSG:2154":
        profil["transform"] = from_origin(5.0, 48.0, 0.001, 0.001)
    with rasterio.open(DOSSIER / nom, "w", **profil) as f:
        f.write(donnees)


if __name__ == "__main__":
    # Fichiers acceptés.
    ecrire("rasterio_float32_deflate.tif", bandes=2)
    ecrire("rasterio_uint16_predictor2.tif", flottant=False, predictor=2)
    ecrire("rasterio_float32_sans_compression.tif", compress="none")
    # Fichiers refusés (code 2).
    ecrire("refus_planar1_gdal_defaut.tif", bandes=2, interleave="pixel")
    ecrire("refus_predictor3.tif", predictor=3)
    ecrire("refus_bigtiff.tif", bigtiff="YES")
    ecrire("refus_epsg4326.tif", crs="EPSG:4326")
    ecrire("refus_zstd.tif", compress="zstd")
    ecrire("refus_lzw.tif", compress="lzw")
    ecrire("refus_bandes_de_lignes.tif", tiled=False, blockxsize=None, blockysize=None)
    ecrire("refus_tuiles_128.tif", blockxsize=128, blockysize=128)
    donnees = valeurs(1, True).astype("float64")
    with rasterio.open(DOSSIER / "refus_float64.tif", "w", **{**PROFIL_OK, "width": LARGEUR,
            "height": HAUTEUR, "count": 1, "crs": "EPSG:2154", "transform": TRANSFORM,
            "dtype": "float64", "nodata": -9999.0}) as f:
        f.write(donnees)
    sys.exit(0)
