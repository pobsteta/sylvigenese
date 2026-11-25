"""Rasters web en COG (spec §9 : « COG avec aperçus ») : `web/rasters/vegetation_map.tif` et, quand
`sim/` existe, `web/rasters/g_<année>.tif` (surface terrière par cellule, décision de Pascal Q3).

Étape du BRIEF codée : spec §9, rasters web ; BRIEF §10 (raster temporel des indicateurs).
Profil `cog` de `contracts/geotiff_profile.json` : tuiles, Deflate, EPSG:2154, nodata, au moins
un aperçu. Catégories : aperçus au plus proche voisin (jamais de moyenne entre deux codes de
catégorie). Surface terrière (Float32, m2/ha) : aperçus en moyenne, nodata exclu.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as copy_dataset

from sylvigenese.common import ModuleError


G_NODATA = -9999.0


def write_cog(source: Path, output: Path, levels: tuple[int, ...] = (2, 4), resampling: str = "nearest") -> None:
    """Copie `source` en COG avec aperçus internes, déterministe ; `resampling` : `nearest` (catégories) ou
    `average` (valeurs continues)."""
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
            dst.build_overviews([n for n in levels if n < max(src.width, src.height)] or [2], Resampling[resampling])
            dst.update_tags(ns="rio_overview", resampling=resampling)
            dst.update_tags(AREA_OR_POINT="Area")
    # recopie en COG : en-tête en tête de fichier, aperçus après l'image ; GDAL réutilise les aperçus
    with rasterio.open(tmp) as src:
        copy_dataset(src, output, driver="COG", compress="DEFLATE", blocksize=256, overviews="FORCE_USE_EXISTING",
               resampling=resampling.upper())
    tmp.unlink()


def write_basal_area_cog(grid: Path, values: np.ndarray, output: Path) -> None:
    """`g_<année>.tif` : COG Float32 aligné sur grid.tif, m2/ha ; NaN de `values` (hors forêt et sans arbre)
    écrit en nodata G_NODATA (contrat assets.basal_area_raster)."""
    with rasterio.open(grid) as g:
        if values.shape != (g.height, g.width):
            raise ModuleError(f"carte de surface terrière de forme {values.shape}, grid.tif {(g.height, g.width)}")
        profile = {"driver": "GTiff", "width": g.width, "height": g.height, "count": 1, "dtype": "float32",
                   "crs": g.crs, "transform": g.transform, "nodata": G_NODATA}
    output.parent.mkdir(parents=True, exist_ok=True)
    plain = output.with_suffix(".plat.tif")
    data = np.where(np.isnan(values), G_NODATA, values).astype("float32")
    with rasterio.open(plain, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(AREA_OR_POINT="Area")
    write_cog(plain, output, resampling="average")
    plain.unlink()
