"""Rasters web en COG (spec §9 : « COG avec aperçus ») : `web/rasters/vegetation_map.tif`.

Étape du BRIEF codée : spec §9, rasters web. Profil `cog` de `contracts/geotiff_profile.json` :
tuiles, Deflate, EPSG:2154, nodata, au moins un aperçu. Catégories : aperçus au plus proche
voisin (jamais de moyenne entre deux codes de catégorie).
"""

from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as copier

from sylvigenese.commun import ErreurModule


def ecrire_cog(source: Path, sortie: Path, niveaux: tuple[int, ...] = (2, 4)) -> None:
    """Copie `source` (GeoTIFF catégoriel) en COG avec aperçus internes, déterministe."""
    if not Path(source).is_file():
        raise ErreurModule(f"raster introuvable : {source}")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = sortie.with_suffix(".tmp.tif")
    with rasterio.open(source) as src:
        profil = src.profile
        profil.update(driver="GTiff", tiled=True, blockxsize=256, blockysize=256, compress="deflate",
                      predictor=1, interleave="band")
        profil.pop("photometric", None)
        with rasterio.open(tmp, "w", **profil) as dst:
            dst.write(src.read())
            dst.build_overviews([n for n in niveaux if n < max(src.width, src.height)] or [2], Resampling.nearest)
            dst.update_tags(ns="rio_overview", resampling="nearest")
            dst.update_tags(AREA_OR_POINT="Area")
    # recopie en COG : en-tête en tête de fichier, aperçus après l'image ; GDAL réutilise les aperçus
    with rasterio.open(tmp) as src:
        copier(src, sortie, driver="COG", compress="DEFLATE", blocksize=256, overviews="FORCE_USE_EXISTING",
               resampling="NEAREST")
    tmp.unlink()
