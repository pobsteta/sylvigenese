"""Fichiers écrits par les vrais outils, et un point du terrain au bon endroit.

- GeoTIFF écrits par rasterio (GDAL) et par terra (R) : conformes au profil s'ils sont
  écrits avec INTERLEAVE=BAND ; refusés avec l'entrelacement par défaut de GDAL ;
- la vraie table `contracts/species.csv` (mission 011) respecte son contrat ;
- un arbre à Paris (x = 652 000, y = 6 862 000, EPSG:2154, x = est) est accepté, et refusé
  si x et y sont inversés.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

import helpers as h
from validator import cli

CONTRACTS = Path(__file__).resolve().parents[1]


def code_of(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_rasterio_band_interleave_is_conform(tmp_path, capsys):
    path = h.tif(tmp_path / "grid.tif", dtype="uint16", interleave="band")
    assert code_of(capsys, ["grid", str(path)])[0] == 0


def test_rasterio_default_pixel_interleave_is_refused(tmp_path, capsys):
    path = h.tif(tmp_path / "grid.tif", dtype="uint16", interleave="pixel")
    code, out = code_of(capsys, ["grid", str(path)])
    assert code == 3 and "PLANARCONFIG" in out


def test_rasterio_cog_with_overviews_is_conform(tmp_path, capsys):
    path = h.tif(tmp_path / "w.tif", driver="COG", dtype="uint16", size=600)
    assert code_of(capsys, ["web_raster", str(path)])[0] == 0


TERRA = """
library(terra)
r <- rast(nrows=300, ncols=300, xmin=900000, xmax=907500, ymin=6492500, ymax=6500000,
          crs="EPSG:2154")
values(r) <- 1
writeRaster(r, commandArgs(TRUE)[1], overwrite=TRUE, datatype="FLT4S", NAflag=-9999,
  gdal=c("TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256", "COMPRESS=DEFLATE",
         "INTERLEAVE=BAND"))
"""


def terra_available():
    if shutil.which("Rscript") is None:
        return False
    r = subprocess.run(["Rscript", "-e", "quit(status = !requireNamespace('terra'))"],
                       capture_output=True, timeout=120)
    return r.returncode == 0


@pytest.mark.skipif(not terra_available(), reason="R ou terra absent de cette machine")
def test_terra_file_is_conform_and_aligned(tmp_path, capsys):
    script = tmp_path / "write.R"
    script.write_text(TERRA, encoding="utf-8")
    path = tmp_path / "dtm.tif"
    subprocess.run(["Rscript", str(script), str(path)], check=True, capture_output=True,
                   timeout=300)
    grid = h.tif(tmp_path / "grid.tif", dtype="uint16")
    code, out = code_of(capsys, ["prepare.dtm", str(path), "--grid", str(grid)])
    assert code == 0, out


def test_real_species_table_is_conform(capsys):
    path = CONTRACTS / "species.csv"
    if not path.exists():
        pytest.fail("contracts/species.csv absent : mission 011 non intégrée")
    code, out = code_of(capsys, ["species", str(path)])
    assert code == 0, out


def test_tree_in_paris_is_accepted_and_swapped_is_refused(tmp_path, capsys):
    data = h.trees_init()
    assert data["x"][0] == 652000.0 and data["y"][0] == 6862000.0
    good = h.parquet(tmp_path / "good.parquet", data)
    assert code_of(capsys, ["trees_init", str(good)])[0] == 0
    data["x"], data["y"] = data["y"], data["x"]
    bad = h.parquet(tmp_path / "bad.parquet", data)
    code, out = code_of(capsys, ["trees_init", str(bad)])
    assert code == 3 and "inversés" in out


def test_raster_placed_in_the_atlantic_is_refused(tmp_path, capsys):
    """Origine à x = 50 000 : à l'ouest de la Bretagne, hors de l'emprise."""
    path = h.tif(tmp_path / "a.tif", origin=(50000.0, 6800000.0))
    code, out = code_of(capsys, ["geotiff_profile", str(path)])
    assert code == 3 and "emprise" in out
