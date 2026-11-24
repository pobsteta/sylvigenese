# prepare : grille de 25 m et rasters alignés (spec §2, §3, §5, §7, §9 ; mission 017).
#
# Lit les entrées de <zone>/inputs/ et écrit directement sous <zone>/ (BRIEF §4) :
#   grid.tif              la grille (spec §7) : UInt16, 1 partout ; elle seule définit l'emprise
#   dtm.tif               MNT sur la grille (Float32)
#   forest_mask.tif       1 = forêt, 0 = hors forêt (UInt16)
#   ser.tif + ser.csv     SER sous-jacente (UInt16) ; L1 à L5 n'y figurent jamais
#   h0.tif                H0 = percentile 95 du MNH à 50 cm par cellule (Float32), PROVISOIRE
#   chm_date.tif          date de vol du MNH, en jours depuis le 1970-01-01 (UInt16)
#   station_gradients.tif trophic, hydric, bioclim (3 bandes Float32)
#   station_type.tif + .csv  type de station (UInt16) et sa légende (valeur, nom)
#   site_potential.tif + .csv  plafond h_pot, une bande par famille d'essences (Float32)
#   rapport_prepare.html  ce que prepare a attribué, comblé ou laissé vide
#
# Règles (spec §7) :
#  - la grille : EPSG:2154, maille de config.yml (25 m, ADR 0001), alignée sur des multiples
#    de la maille ; emprise = celle du masque forestier, arrondie vers l'extérieur ;
#  - bilinéaire pour les entrées continues de maille proche, mode pour les catégorielles ;
#  - le MNH à 50 cm n'est JAMAIS rééchantillonné : il est agrégé en h0.tif (percentile 95).
#    Le percentile 95 est PROVISOIRE (spec §5) : il sera remplacé par l'estimateur h_dom de
#    typopeuplement ;
#  - alluvions : un polygone L1 à L5 de l'entrée brute de l'IGN reçoit la SER voisine qui
#    partage avec lui la plus longue frontière (décision de Pascal du 24/11/2026) ; chaque
#    attribution est une ligne du rapport ;
#  - signaler plutôt que deviner : une cellule sans valeur reste sans valeur (nodata) et
#    figure au rapport ; aucune valeur par défaut.
#
# Non fait ici (à dire) : la zone tampon de la largeur du noyau de dispersion (spec §7), dont
# la largeur n'est pas dans config.yml ; la grille s'arrête à l'emprise du masque forestier.

# Profil GeoTIFF des contrats (contracts/README.md, « Profil GeoTIFF ») : sans ces options,
# GDAL écrit PLANARCONFIG=1 et le validateur refuse le fichier.
GRID_GDAL_OPTIONS <- c("INTERLEAVE=BAND", "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256",
                       "COMPRESS=DEFLATE")
GRID_NODATA_UINT16 <- 65535
GRID_NODATA_FLOAT <- -9999
GRID_CRS <- "EPSG:2154"
# H0 : percentile 95 du MNH (PROVISOIRE, spec §5).
H0_PROBABILITY <- 0.95
# Tolérances (m) pour mesurer une frontière commune entre polygones de la couche IGN : on
# essaie d'abord 1 cm (arêtes confondues) ; si aucune voisine n'est trouvée, 1 m (arêtes
# décalées), et le rapport le dit.
SER_FRONTIER_TOLERANCES_M <- c(0.01, 1)
# Codes des SER d'alluvions de l'IGN (docs/referentiels/surfaces-ser.csv).
ALLUVIUM_CODES <- c("L1", "L2", "L3", "L4", "L5")
# En dessous de ce rapport (maille source / maille de la grille), l'entrée est plus fine que la
# grille : on l'agrège (moyenne) au lieu d'interpoler, qui ne ferait qu'échantillonner.
BILINEAR_MIN_RATIO <- 0.5

# ------------------------------------------------------------------ rapport de prepare

new_report <- function() {
  e <- new.env(parent = emptyenv())
  e$entries <- list()
  e
}

#' Ajoute une ligne au rapport et la dit sur la sortie de message.
report_add <- function(report, section, text) {
  report$entries[[length(report$entries) + 1L]] <- list(section = section, text = text)
  message(sprintf("[prepare] %s : %s", section, text))
  invisible(report)
}

html_escape <- function(x) {
  x <- gsub("&", "&amp;", x, fixed = TRUE)
  x <- gsub("<", "&lt;", x, fixed = TRUE)
  gsub(">", "&gt;", x, fixed = TRUE)
}

#' Écrit rapport_prepare.html (UTF-8), les lignes groupées par section.
write_prepare_report <- function(report, path) {
  sections <- unique(vapply(report$entries, function(e) e$section, character(1)))
  body <- character()
  for (s in sections) {
    lines <- vapply(Filter(function(e) identical(e$section, s), report$entries),
                    function(e) sprintf("<li>%s</li>", html_escape(e$text)), character(1))
    body <- c(body, sprintf("<h2>%s</h2>", html_escape(s)), "<ul>", lines, "</ul>")
  }
  html <- c("<!DOCTYPE html>", "<html lang=\"fr\">",
            "<head><meta charset=\"utf-8\"><title>Rapport de prepare</title></head>",
            "<body>", "<h1>Rapport de prepare : grille, SER, rasters</h1>", body,
            "</body>", "</html>")
  con <- file(path, open = "wb")
  on.exit(close(con))
  writeLines(enc2utf8(html), con, useBytes = TRUE)
  invisible(path)
}

# ------------------------------------------------------------------ zone et grille

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

#' Grille vide : multiples de `res` en x et en y, emprise arrondie vers l'extérieur.
#' `bbox` : c(xmin, ymin, xmax, ymax), EPSG:2154, x vers l'est, y vers le nord, en mètres.
grid_template <- function(bbox, res, crs = GRID_CRS) {
  bbox <- as.numeric(bbox)
  # petite marge contre les erreurs d'arrondi (700000,0000001 ne doit pas ouvrir une maille)
  eps <- 1e-6
  xmin <- floor((bbox[1] + eps) / res) * res
  ymin <- floor((bbox[2] + eps) / res) * res
  xmax <- ceiling((bbox[3] - eps) / res) * res
  ymax <- ceiling((bbox[4] - eps) / res) * res
  terra::rast(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax,
              resolution = res, crs = crs)
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

# ------------------------------------------------------------------ alluvions : SER sous-jacente

#' Attribue à chaque polygone d'alluvions (L1 à L5) la SER voisine qui partage avec lui la plus
#' longue frontière (spec §7, décision de Pascal du 24/11/2026).
#'
#' `ser` : objet sf avec `ser_code`, forme brute de l'IGN. Rend une liste :
#'   ser          le même objet, `ser_code` remplacé par la SER sous-jacente (NA si aucune
#'                voisine) ; la colonne `ser_code_igns` garde le code brut
#'   attributions une ligne par polygone d'alluvions : row, alluvium_code, ser_code (NA si
#'                aucune), frontier_m, runner_up, runner_up_m, tie (TRUE si égalité),
#'                tolerance_m (tolérance qui a servi à la mesure)
#' Les voisines sont les polygones qui ne sont pas eux-mêmes des alluvions ; les polygones
#' d'une même SER sont réunis avant la mesure, pour ne pas compter deux fois un coin.
resolve_alluvium_ser <- function(ser, tolerances_m = SER_FRONTIER_TOLERANCES_M) {
  ser$ser_code_igns <- as.character(ser$ser_code)
  is_alluvium <- ser$ser_code_igns %in% ALLUVIUM_CODES
  base <- ser[!is_alluvium, ]
  rows <- which(is_alluvium)
  out <- vector("list", length(rows))
  new_codes <- as.character(ser$ser_code)
  for (k in seq_along(rows)) {
    i <- rows[k]
    boundary <- sf::st_boundary(sf::st_geometry(ser)[i])
    lengths_by_code <- numeric()
    used_tolerance <- NA_real_
    for (tol in tolerances_m) {
      used_tolerance <- tol
      lengths_by_code <- numeric()
      for (code in sort(unique(as.character(base$ser_code)))) {
        near <- sf::st_buffer(sf::st_union(sf::st_geometry(base)[base$ser_code == code]), tol)
        shared <- suppressWarnings(sf::st_intersection(boundary, near))
        len <- if (length(shared) == 0L) 0 else sum(as.numeric(sf::st_length(shared)))
        if (is.finite(len) && len > 0) lengths_by_code[code] <- len
      }
      if (length(lengths_by_code) > 0L) break
    }
    if (length(lengths_by_code) == 0L) {
      chosen <- NA_character_; best <- 0; second <- NA_character_; second_len <- NA_real_
      tie <- FALSE
    } else {
      # tri décroissant par frontière, puis par code : un ex æquo se tranche de façon stable
      ord <- order(-round(lengths_by_code, 3), names(lengths_by_code))
      sorted <- lengths_by_code[ord]
      chosen <- names(sorted)[1]; best <- unname(sorted[1])
      second <- if (length(sorted) > 1L) names(sorted)[2] else NA_character_
      second_len <- if (length(sorted) > 1L) unname(sorted[2]) else NA_real_
      tie <- length(sorted) > 1L && abs(sorted[1] - sorted[2]) < 1e-3
    }
    new_codes[i] <- chosen
    out[[k]] <- data.frame(row = i, alluvium_code = ser$ser_code_igns[i], ser_code = chosen,
                           frontier_m = best, runner_up = second, runner_up_m = second_len,
                           tie = tie, tolerance_m = used_tolerance, stringsAsFactors = FALSE)
  }
  ser$ser_code <- new_codes
  attributions <- if (length(out) > 0L) do.call(rbind, out) else
    data.frame(row = integer(), alluvium_code = character(), ser_code = character(),
               frontier_m = numeric(), runner_up = character(), runner_up_m = numeric(),
               tie = logical(), tolerance_m = numeric(), stringsAsFactors = FALSE)
  list(ser = ser, attributions = attributions)
}

#' Une ligne de rapport par attribution d'alluvions.
report_alluvium_attributions <- function(report, attributions) {
  section <- "Alluvions : SER sous-jacente"
  if (nrow(attributions) == 0L) {
    return(report_add(report, section, "aucun polygone d'alluvions (L1 à L5) dans ser.gpkg"))
  }
  for (k in seq_len(nrow(attributions))) {
    a <- attributions[k, ]
    if (is.na(a$ser_code)) {
      report_add(report, section, sprintf(
        "alluvions %s (polygone %d de ser.gpkg) : aucune SER voisine, SER sous-jacente non attribuée ; ses cellules restent sans SER (nodata)",
        a$alluvium_code, a$row))
      next
    }
    txt <- sprintf("alluvions %s (polygone %d de ser.gpkg) rattachées à la SER %s, frontière commune de %.0f m",
                   a$alluvium_code, a$row, a$ser_code, a$frontier_m)
    if (!is.na(a$runner_up)) {
      txt <- paste0(txt, sprintf(" (suivante : %s, %.0f m)", a$runner_up, a$runner_up_m))
    }
    if (!is.na(a$tolerance_m) && a$tolerance_m > 0.01) {
      txt <- paste0(txt, sprintf(" ; arêtes non confondues, mesurée avec une tolérance de %g m", a$tolerance_m))
    }
    if (isTRUE(a$tie)) {
      txt <- paste0(txt, " ; ÉGALITÉ de frontière, SER retenue : première dans l'ordre alphabétique des codes")
    }
    report_add(report, section, txt)
  }
  invisible(report)
}

# ------------------------------------------------------------------ rasterisation et rééchantillonnage

#' Rasterise des polygones sur `tmpl` d'après le centre des cellules (terra, touches = FALSE).
#' `values` : un nombre par polygone ; NA hors polygone. En cas de recouvrement, le dernier
#' polygone du fichier l'emporte.
rasterize_polygons <- function(polys, values, tmpl) {
  v <- terra::vect(sf::st_sf(value = values, geometry = sf::st_geometry(polys)))
  terra::rasterize(v, tmpl, field = "value", touches = FALSE)
}

#' Entrée continue -> grille. Bilinéaire si la maille source est proche de celle de la grille
#' (20 m, 26,6 m, spec §7) ; moyenne si la source est plus fine d'au moins deux fois (MNT de 1
#' ou 5 m), dit au rapport.
resample_continuous <- function(r, tmpl, report, label) {
  ratio <- terra::res(r)[1] / terra::res(tmpl)[1]
  method <- if (ratio >= BILINEAR_MIN_RATIO) "bilinear" else "average"
  report_add(report, "Rééchantillonnage", sprintf(
    "%s : maille %.4g m vers %.4g m, méthode %s", label, terra::res(r)[1],
    terra::res(tmpl)[1], if (method == "bilinear") "bilinéaire" else "moyenne (source plus fine que la grille)"))
  terra::resample(r, tmpl, method = method)
}

#' Entrée catégorielle -> grille : mode (spec §7).
resample_categorical <- function(r, tmpl, report, label) {
  report_add(report, "Rééchantillonnage", sprintf(
    "%s : maille %.4g m vers %.4g m, méthode mode", label, terra::res(r)[1], terra::res(tmpl)[1]))
  terra::resample(r, tmpl, method = "mode")
}

#' H0 par cellule : percentile 95 du MNH à 50 cm sur la cellule (PROVISOIRE, spec §5).
#' Le MNH n'est pas rééchantillonné : il est agrégé par blocs entiers, sur une grille alignée.
#' Arrête si le MNH n'est pas aligné sur la grille ou si sa maille ne la divise pas.
aggregate_h0 <- function(chm, tmpl, probability = H0_PROBABILITY) {
  res_chm <- terra::res(chm)[1]
  res_grid <- terra::res(tmpl)[1]
  k <- res_grid / res_chm
  if (abs(k - round(k)) > 1e-9 || round(k) < 1) {
    stop(sprintf("le MNH (maille %g m) ne s'agrège pas en cellules de %g m : le rapport n'est pas entier ; le MNH n'est jamais rééchantillonné",
                 res_chm, res_grid), call. = FALSE)
  }
  k <- as.integer(round(k))
  # alignement : les bords de la grille doivent tomber sur des bords de cellules du MNH
  shift_x <- (terra::xmin(chm) - terra::xmin(tmpl)) / res_chm
  shift_y <- (terra::ymax(chm) - terra::ymax(tmpl)) / res_chm
  if (abs(shift_x - round(shift_x)) > 1e-6 || abs(shift_y - round(shift_y)) > 1e-6) {
    stop("le MNH n'est pas aligné sur la grille (origine décalée d'une fraction de cellule) ; il n'est jamais rééchantillonné",
         call. = FALSE)
  }
  if (terra::xmax(chm) <= terra::xmin(tmpl) || terra::xmin(chm) >= terra::xmax(tmpl) ||
      terra::ymax(chm) <= terra::ymin(tmpl) || terra::ymin(chm) >= terra::ymax(tmpl)) {
    stop("le MNH ne recouvre pas la grille", call. = FALSE)
  }
  # recadrage sur l'emprise de la grille : les cellules sans MNH deviennent NA (signalées)
  chm <- terra::extend(terra::crop(chm, terra::ext(tmpl)), terra::ext(tmpl))
  q <- function(x, ...) {
    x <- x[!is.na(x)]
    if (length(x) == 0L) NA_real_ else unname(stats::quantile(x, probability, type = 7, names = FALSE))
  }
  h0 <- terra::aggregate(chm, fact = k, fun = q)
  terra::compareGeom(h0, tmpl, stopOnError = TRUE)
  h0
}

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

write_categories <- function(values, names, path) {
  tab <- data.frame(value = as.integer(values), name = as.character(names),
                    stringsAsFactors = FALSE)
  utils::write.csv(tab, path, row.names = FALSE, fileEncoding = "UTF-8", quote = TRUE)
  invisible(tab)
}

#' Nombre de cellules sans valeur parmi les cellules de forêt et au total, au rapport.
report_missing <- function(report, r, forest, label, how) {
  na <- is.na(terra::values(r, mat = FALSE))
  f <- terra::values(forest, mat = FALSE) == 1
  f[is.na(f)] <- FALSE
  n_na <- sum(na); n_forest_na <- sum(na & f)
  if (n_na > 0L) {
    report_add(report, "Cellules sans valeur", sprintf(
      "%s : %d cellule(s) sans valeur (dont %d forestière(s)) ; laissées au nodata, %s",
      label, n_na, n_forest_na, how))
  }
  invisible(c(total = n_na, forest = n_forest_na))
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

# ------------------------------------------------------------------ le module

#' Construit la grille et les rasters alignés d'une zone (mission 017). Rend la liste des
#' fichiers écrits. Arrête avec un message en français à la première entrée refusée.
prepare_grid <- function(zone_dir, cfg, validate = TRUE) {
  res <- cfg$grid$resolution_m
  if (is.null(res) || !is.numeric(res) || res <= 0) {
    stop("config.yml : grid.resolution_m manquante ou invalide", call. = FALSE)
  }
  if (!identical(cfg$crs, GRID_CRS)) {
    stop(sprintf("config.yml : crs %s, seul %s est pris en charge", cfg$crs, GRID_CRS),
         call. = FALSE)
  }
  inp <- function(...) file.path(zone_dir, "inputs", ...)
  out <- function(...) file.path(zone_dir, ...)
  report <- new_report()

  # -- entrées : validées à l'entrée (spec §2), puis lues
  inputs <- list(
    inputs.forest_mask = inp("forest_mask.gpkg"), inputs.ser = inp("ser.gpkg"),
    inputs.dtm = inp("dtm.tif"), inputs.chm = inp("chm.tif"),
    inputs.lidar_tiles = inp("lidar_tiles.gpkg"),
    inputs.station_gradients = inp("station_gradients.tif"),
    inputs.station_type = inp("station_type.tif"), inputs.h_pot = inp("h_pot.tif"),
    inputs.nemeton_stands = inp("nemeton_stands.gpkg"))
  # Toutes les entrées sont contrôlées AVANT la première écriture : une entrée refusée
  # ne laisse aucune sortie à moitié produite. nemeton_stands.gpkg n'est lu que par 018, mais
  # il est contrôlé ici, à l'entrée du module (spec §2). L'inventaire vidéo est facultatif.
  for (k in seq_along(inputs)) check_input_file(inputs[[k]])
  if (file.exists(inp("inventaire_video.gpkg"))) {
    inputs$inputs.inventaire_video <- inp("inventaire_video.gpkg")
  }
  if (validate) {
    for (k in seq_along(inputs)) validate_file(names(inputs)[k], inputs[[k]], what = "entrée")
  }

  # -- grille : emprise du masque forestier, arrondie vers l'extérieur
  mask_sf <- read_layer_2154(inputs$inputs.forest_mask, "forest_mask")
  tmpl <- grid_template(sf::st_bbox(mask_sf), res)
  report_add(report, "Grille", sprintf(
    "%d colonnes x %d lignes de %g m, x de %.1f à %.1f, y de %.1f à %.1f (EPSG:2154, coin nord-ouest %.1f ; %.1f)",
    terra::ncol(tmpl), terra::nrow(tmpl), res, terra::xmin(tmpl), terra::xmax(tmpl),
    terra::ymin(tmpl), terra::ymax(tmpl), terra::xmin(tmpl), terra::ymax(tmpl)))
  report_add(report, "Grille", "zone tampon de dispersion non ajoutée : sa largeur n'est pas fixée dans config.yml (spec §7)")
  written <- character()
  grid_path <- out("grid.tif")
  grid <- terra::rast(tmpl, vals = 1L)
  write_grid_raster(grid, grid_path, "INT2U")
  written <- c(written, grid_path)

  # -- masque forestier : 1 si le centre de la cellule est dans un polygone, 0 sinon
  forest <- rasterize_polygons(mask_sf, rep(1, nrow(mask_sf)), tmpl)
  forest <- terra::ifel(is.na(forest), 0, 1)
  write_grid_raster(forest, out("forest_mask.tif"), "INT2U")
  written <- c(written, out("forest_mask.tif"))
  report_add(report, "Grille", sprintf("%d cellule(s) forestière(s) sur %d",
                                      sum(terra::values(forest) == 1), terra::ncell(forest)))

  # -- MNT
  dtm <- resample_continuous(read_raster_2154(inputs$inputs.dtm), tmpl, report, "dtm.tif")
  report_missing(report, dtm, forest, "dtm.tif", "aucune altitude devinée")
  write_grid_raster(dtm, out("dtm.tif"), "FLT4S")
  written <- c(written, out("dtm.tif"))

  # -- SER (alluvions comprises)
  ser_raw <- read_layer_2154(inputs$inputs.ser, "ser")
  if (!"ser_code" %in% names(ser_raw)) stop("ser.gpkg : colonne ser_code absente", call. = FALSE)
  res_ser <- resolve_alluvium_ser(ser_raw)
  report_alluvium_attributions(report, res_ser$attributions)
  ser <- res_ser$ser
  codes <- sort(unique(stats::na.omit(as.character(ser$ser_code))))
  if (any(codes %in% ALLUVIUM_CODES)) {
    stop("erreur interne : un code d'alluvions L1 à L5 reste dans ser.tif", call. = FALSE)
  }
  ser_value <- match(as.character(ser$ser_code), codes)
  has_code <- !is.na(ser_value)
  ser_r <- rasterize_polygons(ser[has_code, ], ser_value[has_code], tmpl)
  report_missing(report, ser_r, forest, "ser.tif", "aucune SER devinée")
  write_grid_raster(ser_r, out("ser.tif"), "INT2U")
  write_categories(seq_along(codes), codes, out("ser.csv"))
  written <- c(written, out("ser.tif"), out("ser.csv"))

  # -- MNH : H0 (percentile 95, PROVISOIRE) ; le MNH n'est pas rééchantillonné
  chm <- read_raster_2154(inputs$inputs.chm)
  h0 <- aggregate_h0(chm, tmpl)
  report_add(report, "H0", sprintf(
    "h0.tif : percentile %g du MNH de %g m sur chaque cellule de %g m (agrégation, sans rééchantillonnage) ; PROVISOIRE, à remplacer par le h_dom de typopeuplement (spec §5)",
    100 * H0_PROBABILITY, terra::res(chm)[1], res))
  report_missing(report, h0, forest, "h0.tif", "aucune hauteur devinée")
  write_grid_raster(h0, out("h0.tif"), "FLT4S")
  written <- c(written, out("h0.tif"))

  # -- date du vol : jours depuis le 1970-01-01, dalle qui contient le centre de la cellule
  tiles <- read_layer_2154(inputs$inputs.lidar_tiles, "lidar_tiles")
  days <- as.integer(as.Date(as.character(tiles$flight_date)))
  if (anyNA(days) || any(days < 0 | days >= GRID_NODATA_UINT16)) {
    stop("lidar_tiles.gpkg : flight_date illisible ou hors de la plage d'un UInt16 (jours depuis le 1970-01-01)",
         call. = FALSE)
  }
  chm_date <- rasterize_polygons(tiles, days, tmpl)
  report_missing(report, chm_date, forest, "chm_date.tif", "aucune date devinée")
  write_grid_raster(chm_date, out("chm_date.tif"), "INT2U")
  written <- c(written, out("chm_date.tif"))

  # -- gradients de station (continus, 3 bandes)
  sg <- read_raster_2154(inputs$inputs.station_gradients)
  wanted <- c("trophic", "hydric", "bioclim")
  if (terra::nlyr(sg) != 3L || !setequal(names(sg), wanted)) {
    stop(sprintf("station_gradients.tif : bandes %s attendues, trouvées : %s",
                 paste(wanted, collapse = ", "), paste(names(sg), collapse = ", ")), call. = FALSE)
  }
  sg <- sg[[wanted]]
  sg <- resample_continuous(sg, tmpl, report, "station_gradients.tif")
  for (b in wanted) report_missing(report, sg[[b]], forest, paste0("station_gradients.tif (", b, ")"),
                                   "aucune valeur devinée")
  write_grid_raster(sg, out("station_gradients.tif"), "FLT4S", names = wanted)
  written <- c(written, out("station_gradients.tif"))

  # -- type de station (catégoriel, légende de types.csv de sylvostation)
  legend_path <- inp("types.csv")
  check_input_file(legend_path)
  legend <- utils::read.csv2(legend_path, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  if (!all(c("id", "type") %in% names(legend))) {
    stop("types.csv : colonnes id et type attendues", call. = FALSE)
  }
  st <- read_raster_2154(inputs$inputs.station_type)
  st <- resample_categorical(st, tmpl, report, "station_type.tif")
  found <- stats::na.omit(unique(terra::values(st, mat = FALSE)))
  unknown <- setdiff(found, legend$id)
  if (length(unknown) > 0L) {
    stop(sprintf("station_type.tif : code(s) %s absent(s) de types.csv", paste(unknown, collapse = ", ")),
         call. = FALSE)
  }
  report_missing(report, st, forest, "station_type.tif", "aucun type deviné")
  write_grid_raster(st, out("station_type.tif"), "INT2U")
  write_categories(legend$id, legend$type, out("station_type.csv"))
  written <- c(written, out("station_type.tif"), out("station_type.csv"))

  # -- potentialité de station : plafond h_pot, une bande par famille d'essences
  hp <- read_raster_2154(inputs$inputs.h_pot)
  families <- names(hp)
  if (any(!nzchar(families)) || anyDuplicated(families) > 0L || any(grepl("^lyr[.]?[0-9]+$", families))) {
    stop(sprintf("h_pot.tif : chaque bande doit porter le nom de sa famille d'essences, uniques ; trouvé : %s",
                 paste(families, collapse = ", ")), call. = FALSE)
  }
  hp <- resample_continuous(hp, tmpl, report, "h_pot.tif")
  for (b in seq_along(families)) report_missing(report, hp[[b]], forest,
    paste0("site_potential.tif (", families[b], ")"), "aucun plafond deviné")
  write_grid_raster(hp, out("site_potential.tif"), "FLT4S", names = families)
  write_categories(seq_along(families), families, out("site_potential.csv"))
  written <- c(written, out("site_potential.tif"), out("site_potential.csv"))

  # -- rapport, puis validation des sorties (spec §2 : chaque module valide ses sorties)
  report_path <- out("rapport_prepare.html")
  write_prepare_report(report, report_path)
  written <- c(written, report_path)
  if (validate) {
    contracts <- c(grid.tif = "prepare.grid", dtm.tif = "prepare.dtm",
                   forest_mask.tif = "prepare.forest_mask", ser.tif = "prepare.ser",
                   h0.tif = "prepare.h0", chm_date.tif = "prepare.chm_date",
                   station_gradients.tif = "prepare.station_gradients",
                   station_type.tif = "prepare.station_type",
                   site_potential.tif = "prepare.site_potential")
    for (f in names(contracts)) {
      validate_file(contracts[[f]], out(f), grid = if (f == "grid.tif") NULL else grid_path)
    }
    tables <- c(ser.csv = "prepare.ser_categories", station_type.csv = "prepare.station_type_categories",
                site_potential.csv = "prepare.site_potential_bands")
    for (f in names(tables)) validate_file(tables[[f]], out(f))
  }
  invisible(written)
}
