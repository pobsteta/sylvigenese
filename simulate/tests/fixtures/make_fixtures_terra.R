# Fichiers d'essai GeoTIFF écrits par terra (mission 015) : valeurs synthétiques.
# Usage : Rscript simulate/tests/fixtures/make_fixtures_terra.R
# Ordre des axes : x = est, y = nord, EPSG:2154. Coin nord-ouest (700000 ; 6501000).
# Valeur au pixel (ligne l, colonne c), l et c comptés depuis 0 : 0,5 l + 0,25 c (Float32).
library(terra)
dossier <- file.path("simulate", "tests", "fixtures")
nl <- 270; nc <- 300
r <- rast(nrows = nl, ncols = nc, xmin = 700000, xmax = 700000 + 25 * nc,
          ymin = 6501000 - 25 * nl, ymax = 6501000, crs = "EPSG:2154")
ligne <- rep(0:(nl - 1), each = nc); colonne <- rep(0:(nc - 1), times = nl)
values(r) <- 0.5 * ligne + 0.25 * colonne
gdal_ok <- c("TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256", "INTERLEAVE=BAND", "COMPRESS=DEFLATE")
writeRaster(r, file.path(dossier, "terra_float32_deflate.tif"), datatype = "FLT4S",
            NAflag = -9999, gdal = gdal_ok, overwrite = TRUE)
writeRaster(r, file.path(dossier, "terra_float32_predictor2.tif"), datatype = "FLT4S",
            NAflag = -9999, gdal = c(gdal_ok, "PREDICTOR=2"), overwrite = TRUE)
# Refusé : réglages par défaut de GDAL (entrelacement PLANARCONFIG=1, bandes de lignes).
writeRaster(r, file.path(dossier, "refus_terra_defaut.tif"), datatype = "FLT4S",
            NAflag = -9999, overwrite = TRUE)
