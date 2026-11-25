"""Rasters web en COG (spec §9 : « COG avec aperçus ») : `web/rasters/vegetation_map.tif`.

Étape du BRIEF codée : spec §9, rasters web. Profil `cog` de `contracts/geotiff_profile.json` :
tuiles, Deflate, EPSG:2154, nodata, au moins un aperçu. Catégories : aperçus au plus proche
voisin (jamais de moyenne entre deux codes de catégorie).
"""

from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as copy_dataset

from sylvigenese.common import ModuleError


def write_cog(source: Path, output: Path, levels: tuple[int, ...] = (2, 4)) -> None:
    """Copie `source` (GeoTIFF catégoriel) en COG avec aperçus internes, déterministe."""
    if not Path(source).is_file():
        raise ModuleError(f"raster introuvable : {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp.tif")
    with rasterio.open(source) as src:
        profile = src.profile
        profile.update(driver="GTiff", tiled=True, blockxsize=256, blockysize=256, compress="deflate",
                      predictor=1, interleave="band")
        profile.pop("photometric", None)
        with rasterio.open(tmp, "w", **profile) as dst:
            dst.write(src.read())
            dst.build_overviews([n for n in levels if n < max(src.width, src.height)] or [2], Resampling.nearest)
            dst.update_tags(ns="rio_overview", resampling="nearest")
            dst.update_tags(AREA_OR_POINT="Area")
    # recopie en COG : en-tête en tête de fichier, aperçus après l'image ; GDAL réutilise les aperçus
    with rasterio.open(tmp) as src:
        copy_dataset(src, output, driver="COG", compress="DEFLATE", blocksize=256, overviews="FORCE_USE_EXISTING",
               resampling="NEAREST")
    tmp.unlink()
