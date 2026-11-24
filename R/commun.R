# Outils communs à tous les modules R (spec §2, « Règles »), sans logique métier.
#
# Comme R/config.R et R/validateur.R, ce fichier n'appartient à aucun module : prepare
# (R/prepare_grid.R, R/prepare_ifn.R, R/prepare_trees.R), biomes (R/biomes.R) et dynamics s'en
# servent tous, et aucun module n'appelle le code d'un autre. Il contient :
#   - le rapport HTML (new_report, report_add, html_escape, write_html_report, fr_num) ;
#   - la lecture des entrées en EPSG:2154 (check_input_file, read_layer_2154, read_raster_2154) ;
#   - l'écriture des grilles au profil GeoTIFF des contrats et des tables de catégories
#     (write_grid_raster, write_categories) ;
#   - la rasterisation de polygones sur la grille (rasterize_polygons) ;
#   - le dossier d'une zone (prepare_zone_dir) ;
#   - la validation d'un fichier par contracts/validate (validate_file) ;
#   - la lecture et l'écriture du Parquet par le paquet R « arrow » (read_parquet_tbl,
#     write_parquet_tbl).
#
# Aucune valeur écologique ici. Chargé comme les autres fichiers de R/ (Makefile, _targets.R,
# R/tests/testthat.R : tout R/*.R est lu avant l'appel d'un module).

# Profil GeoTIFF des contrats (contracts/README.md, « Profil GeoTIFF ») : sans ces options,
# GDAL écrit PLANARCONFIG=1 et le validateur refuse le fichier.
GRID_GDAL_OPTIONS <- c("INTERLEAVE=BAND", "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256",
                       "COMPRESS=DEFLATE")
GRID_NODATA_UINT16 <- 65535
GRID_NODATA_FLOAT <- -9999
GRID_CRS <- "EPSG:2154"

# ------------------------------------------------------------------ rapport HTML

#' Un rapport : une liste de lignes (section, texte). `module` est le nom que portent les
#' messages envoyés en même temps sur la sortie de message (« [prepare] », « [biomes] »).
new_report <- function(module = "prepare") {
  e <- new.env(parent = emptyenv())
  e$entries <- list()
  e$module <- module
  e
}

#' Ajoute une ligne au rapport et la dit sur la sortie de message.
report_add <- function(report, section, text) {
  report$entries[[length(report$entries) + 1L]] <- list(section = section, text = text)
  message(sprintf("[%s] %s : %s", report$module, section, text))
  invisible(report)
}

html_escape <- function(x) {
  x <- gsub("&", "&amp;", x, fixed = TRUE)
  x <- gsub("<", "&lt;", x, fixed = TRUE)
  gsub(">", "&gt;", x, fixed = TRUE)
}

#' Nombre écrit à la française pour un rapport : virgule décimale (0,6 et non 0.6). Sans
#' `digits`, le nombre garde ses chiffres significatifs ; avec `digits`, ce nombre de décimales.
fr_num <- function(x, digits = NULL) {
  one <- function(v) {
    if (is.na(v)) return("NA")
    # 10 chiffres significatifs : 26,6 et non 26,6000000000012 (bruit de virgule flottante)
    s <- if (is.null(digits)) format(signif(v, 10), trim = TRUE, scientific = FALSE, digits = 10)
         else formatC(v, format = "f", digits = digits)
    sub(".", ",", s, fixed = TRUE)
  }
  vapply(x, one, character(1), USE.NAMES = FALSE)
}

#' Écrit un rapport HTML en UTF-8, les lignes groupées par section. `title` va dans <title>,
#' `heading` dans <h1>.
write_html_report <- function(report, path, title, heading) {
  sections <- unique(vapply(report$entries, function(e) e$section, character(1)))
  body <- character()
  for (s in sections) {
    lines <- vapply(Filter(function(e) identical(e$section, s), report$entries),
                    function(e) sprintf("<li>%s</li>", html_escape(e$text)), character(1))
    body <- c(body, sprintf("<h2>%s</h2>", html_escape(s)), "<ul>", lines, "</ul>")
  }
  html <- c("<!DOCTYPE html>", "<html lang=\"fr\">",
            sprintf("<head><meta charset=\"utf-8\"><title>%s</title></head>", html_escape(title)),
            "<body>", sprintf("<h1>%s</h1>", html_escape(heading)), body,
            "</body>", "</html>")
  # Pas d'enc2utf8 : en locale C il transcrirait les octets UTF-8 en texte « <c3><a9> ».
  # Les chaînes sont déjà de l'UTF-8 ; on les marque et on écrit les octets tels quels.
  Encoding(html) <- "UTF-8"
  con <- file(path, open = "wb")
  on.exit(close(con))
  writeLines(html, con, useBytes = TRUE)
  invisible(path)
}

# ------------------------------------------------------------------ zone

#' Dossier d'une zone : le jeu fictif est versionné sous tests/fixtures, les autres zones
#' sous data/<zone> (comme le Makefile). La racine du dépôt vient de SYLVIGENESE_ROOT, sinon
#' du dossier courant.
prepare_zone_dir <- function(cfg) {
  if (is.null(cfg$zone) || !nzchar(cfg$zone)) {
    stop("config.yml : `zone` manquante", call. = FALSE)
  }
  root <- Sys.getenv("SYLVIGENESE_ROOT", unset = ".")
  if (identical(cfg$zone, "zone_fictive")) {
    file.path(root, "tests", "fixtures", "zone_fictive")
  } else {
    file.path(root, "data", cfg$zone)
  }
}

# ------------------------------------------------------------------ lecture des entrées

check_input_file <- function(path) {
  if (!file.exists(path)) {
    stop(sprintf("entrée absente : %s", path), call. = FALSE)
  }
  invisible(path)
}

#' Lit une couche vectorielle, exige EPSG:2154 et corrige les géométries invalides.
read_layer_2154 <- function(path, layer) {
  check_input_file(path)
  x <- sf::st_read(path, layer = layer, quiet = TRUE)
  if (is.na(sf::st_crs(x)$epsg) || sf::st_crs(x)$epsg != 2154) {
    stop(sprintf("%s (couche %s) n'est pas en EPSG:2154", path, layer), call. = FALSE)
  }
  if (nrow(x) == 0L) {
    stop(sprintf("%s (couche %s) est vide", path, layer), call. = FALSE)
  }
  sf::st_make_valid(x)
}

read_raster_2154 <- function(path) {
  check_input_file(path)
  r <- terra::rast(path)
  epsg <- terra::crs(r, describe = TRUE)$code
  if (is.na(epsg) || epsg != "2154") {
    stop(sprintf("%s n'est pas en EPSG:2154", path), call. = FALSE)
  }
  r
}

#' Rasterise des polygones sur `tmpl` d'après le centre des cellules (terra, touches = FALSE).
#' `values` : un nombre par polygone ; NA hors polygone. En cas de recouvrement, la PLUS PETITE
#' valeur l'emporte : la règle ne dépend pas de l'ordre des polygones dans le fichier.
rasterize_polygons <- function(polys, values, tmpl) {
  v <- terra::vect(sf::st_sf(value = values, geometry = sf::st_geometry(polys)))
  r <- terra::rasterize(v, tmpl, field = "value", fun = "min", touches = FALSE)
  # fun = "min" laisse NaN là où aucun polygone ne passe : on revient à NA
  terra::ifel(is.nan(r), NA, r)
}

# ------------------------------------------------------------------ écriture des grilles

#' Écrit un raster au profil des contrats : tuiles de 256, Deflate, entrelacement par bande,
#' nodata déclaré.
write_grid_raster <- function(r, path, datatype = c("INT2U", "FLT4S"), names = NULL) {
  datatype <- match.arg(datatype)
  nodata <- if (datatype == "INT2U") GRID_NODATA_UINT16 else GRID_NODATA_FLOAT
  if (!is.null(names)) names(r) <- names
  terra::writeRaster(r, path, overwrite = TRUE, datatype = datatype, NAflag = nodata,
                     gdal = GRID_GDAL_OPTIONS)
  invisible(path)
}

#' Table de catégories (value, name) d'un raster catégoriel, en UTF-8. Colonnes en plus :
#' `extra`, liste nommée de vecteurs de même longueur (valeurs absentes : NA, écrites vides).
write_categories <- function(values, names, path, extra = list()) {
  tab <- data.frame(value = as.integer(values), name = as.character(names),
                    stringsAsFactors = FALSE)
  for (n in names(extra)) tab[[n]] <- as.character(extra[[n]])
  utils::write.csv(tab, path, row.names = FALSE, fileEncoding = "UTF-8", quote = TRUE, na = "")
  invisible(tab)
}

# ------------------------------------------------------------------ validation par fichier

#' Fait valider un fichier par contracts/validate (sous-processus) ; arrête avec le motif
#' sinon. `grid` : chemin de grid.tif pour la variante grille.
validate_file <- function(contract, path, grid = NULL, what = "sortie") {
  args <- c(contract, if (!is.null(grid)) c("--grid", grid), path)
  status <- call_validator(args)
  if (!identical(status, 0L)) {
    stop(sprintf("%s refusée par le validateur (contrat %s, code %s) : %s",
                 what, contract, status, path), call. = FALSE)
  }
  invisible(TRUE)
}

# ------------------------------------------------------------------ Parquet (paquet arrow)
# Voie commune du projet : le paquet R « arrow » (décision de l'orchestrateur, 24/11/2026).

.require_arrow <- function() {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("le paquet R « arrow » est absent : impossible de lire ou d'écrire du Parquet", call. = FALSE)
  }
}

#' Lit un fichier Parquet en data.frame. Les colonnes de texte restent des chaînes (le zéro de
#' tête des codes espar : « 09 », jamais 9).
read_parquet_tbl <- function(path) {
  if (!file.exists(path)) stop(sprintf("fichier Parquet absent : %s", path), call. = FALSE)
  .require_arrow()
  as.data.frame(arrow::read_parquet(path), stringsAsFactors = FALSE)
}

#' Écrit un data.frame en Parquet avec un schéma explicite : `types` nomme le type de chaque
#' colonne (« string », « float64 » ou « int32 »), pour qu'une colonne vide ne devienne pas
#' « null ». Pas de partition.
write_parquet_tbl <- function(df, path, types) {
  .require_arrow()
  if (!setequal(names(df), names(types))) {
    stop("erreur interne : colonnes et types du Parquet ne correspondent pas", call. = FALSE)
  }
  arrow_types <- list(string = arrow::string(), float64 = arrow::float64(), int32 = arrow::int32())
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  sch <- do.call(arrow::schema, lapply(names(types), function(n) arrow::field(n, arrow_types[[types[[n]]]])))
  arrow::write_parquet(arrow::arrow_table(df[, names(types), drop = FALSE], schema = sch), path)
  invisible(path)
}
