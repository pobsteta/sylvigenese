# prepare : grille de 25 m et rasters alignés (spec §2, §3, §5, §7, §9 ; mission 017).
#
# Lit les entrées de <zone>/inputs/ et écrit directement sous <zone>/ (BRIEF §4) :
#   grid.tif              la grille (spec §7) : UInt16, 1 partout ; elle seule définit l'emprise
#   dtm.tif               MNT sur la grille (Float32)
#   forest_mask.tif       1 = forêt, 0 = hors forêt (UInt16)
#   ser.tif + ser.csv     SER sous-jacente (UInt16), une valeur par couple distinct
#                         (ser_code, alluvium_code) ; ser.csv : value, name (= ser_code, jamais
#                         L1 à L5), alluvium_code (L1 à L5, ou vide hors alluvions)
#   stand_map.tif + .csv  polygone nemeton de chaque cellule (UInt16, nodata hors polygone) et
#                         sa table (value, name = stand_id) ; c'est ce que lit biomes
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
#  - recouvrements : si deux polygones d'une même couche (SER, peuplements nemeton, dalles
#    LiDAR) se recouvrent, la PLUS PETITE valeur l'emporte (règle indépendante de l'ordre du
#    fichier) et le rapport dit combien de cellules et quels polygones ;
#  - signaler plutôt que deviner : une cellule sans valeur reste sans valeur (nodata) et
#    figure au rapport ; aucune valeur par défaut.
#
# Les outils communs (rapport, lecture en EPSG:2154, écriture des grilles, validation) sont dans
# R/commun.R, commun à tous les modules R (spec §2).
#
# Non fait ici (à dire) : la zone tampon de la largeur du noyau de dispersion (spec §7), dont
# la largeur n'est pas dans config.yml ; la grille s'arrête à l'emprise du masque forestier.

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

#' Écrit rapport_prepare.html (UTF-8), les lignes groupées par section.
write_prepare_report <- function(report, path) {
  write_html_report(report, path, "Rapport de prepare",
                    "Rapport de prepare : grille, SER, rasters")
}

# ------------------------------------------------------------------ grille


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
      txt <- paste0(txt, sprintf(" ; arêtes non confondues, mesurée avec une tolérance de %s m", fr_num(a$tolerance_m)))
    }
    if (isTRUE(a$tie)) {
      txt <- paste0(txt, " ; ÉGALITÉ de frontière, SER retenue : première dans l'ordre alphabétique des codes")
    }
    report_add(report, section, txt)
  }
  invisible(report)
}

# ------------------------------------------------------------------ rasterisation et rééchantillonnage

#' Entrée continue -> grille. Bilinéaire si la maille source est proche de celle de la grille
#' (20 m, 26,6 m, spec §7) ; moyenne si la source est plus fine d'au moins deux fois (MNT de 1
#' ou 5 m), dit au rapport.
resample_continuous <- function(r, tmpl, report, label) {
  ratio <- terra::res(r)[1] / terra::res(tmpl)[1]
  method <- if (ratio >= BILINEAR_MIN_RATIO) "bilinear" else "average"
  report_add(report, "Rééchantillonnage", sprintf(
    "%s : maille %s m vers %s m, méthode %s", label, fr_num(terra::res(r)[1]),
    fr_num(terra::res(tmpl)[1]), if (method == "bilinear") "bilinéaire" else "moyenne (source plus fine que la grille)"))
  terra::resample(r, tmpl, method = method)
}

#' Entrée catégorielle -> grille : mode (spec §7).
resample_categorical <- function(r, tmpl, report, label) {
  report_add(report, "Rééchantillonnage", sprintf(
    "%s : maille %s m vers %s m, méthode mode", label, fr_num(terra::res(r)[1]),
    fr_num(terra::res(tmpl)[1])))
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

# ------------------------------------------------------------------ SER : un code par couple

#' Valeur de ser.tif de chaque polygone : une valeur par couple distinct (ser_code,
#' alluvium_code), de sorte que chaque cellule garde son origine d'alluvions (spec §3, §7).
#' `ser` : objet sf passé par resolve_alluvium_ser (`ser_code` = SER sous-jacente, NA sans
#' voisine ; `ser_code_igns` = code brut de l'IGN). Rend une liste :
#'   table  data.frame (value, name, alluvium_code) trié par SER puis par alluvions ; `name` est
#'          le ser_code, jamais L1 à L5 ; alluvium_code NA hors alluvions
#'   value  la valeur de chaque polygone (NA si la SER sous-jacente n'est pas attribuée)
ser_value_table <- function(ser) {
  code <- as.character(ser$ser_code)
  raw <- as.character(ser$ser_code_igns)
  alluvium <- ifelse(raw %in% ALLUVIUM_CODES, raw, NA_character_)
  keep <- !is.na(code)
  couples <- unique(data.frame(name = code[keep], alluvium_code = alluvium[keep],
                               stringsAsFactors = FALSE))
  couples <- couples[order(couples$name, couples$alluvium_code, na.last = FALSE,
                           method = "radix"), , drop = FALSE]
  rownames(couples) <- NULL
  if (any(couples$name %in% ALLUVIUM_CODES)) {
    stop("erreur interne : un code d'alluvions L1 à L5 reste comme SER dans ser.tif", call. = FALSE)
  }
  couples <- data.frame(value = seq_len(nrow(couples)), couples, stringsAsFactors = FALSE)
  sep <- "\r"
  key_table <- paste(couples$name, couples$alluvium_code, sep = sep)
  key_poly <- paste(code, alluvium, sep = sep)
  value <- couples$value[match(key_poly, key_table)]
  value[!keep] <- NA_integer_
  list(table = couples, value = value)
}

# ------------------------------------------------------------------ recouvrements de polygones

#' Recouvrements entre les polygones d'une couche : une ligne par paire dont l'intersection a
#' une surface. `labels` : nom de chaque polygone pour le rapport ; `values` : leur valeur dans
#' le raster ; `tmpl` : la grille. Rend une liste : pairs (a, b, area_m2, cells, same_value) et
#' `cells`, le nombre de cellules (centre dans le polygone) qui reçoivent plusieurs polygones.
polygon_overlaps <- function(polys, labels, values, tmpl) {
  n <- nrow(polys)
  pairs <- data.frame(a = character(), b = character(), area_m2 = numeric(),
                      cells = integer(), same_value = logical(), stringsAsFactors = FALSE)
  if (n < 2L) return(list(pairs = pairs, cells = 0L))
  geom <- sf::st_geometry(polys)
  rel <- sf::st_relate(geom, geom, pattern = "2********", sparse = TRUE)
  rows <- list()
  for (i in seq_len(n)) {
    for (j in rel[[i]]) {
      if (j <= i) next
      inter <- suppressWarnings(sf::st_collection_extract(
        suppressWarnings(sf::st_intersection(geom[i], geom[j])), "POLYGON"))
      area <- sum(as.numeric(sf::st_area(inter)))
      if (length(inter) == 0L || !is.finite(area) || area <= 0) next
      cells <- terra::rasterize(terra::vect(sf::st_sf(value = 1, geometry = inter)), tmpl,
                                field = "value", fun = "sum", touches = FALSE)
      rows[[length(rows) + 1L]] <- data.frame(
        a = labels[i], b = labels[j], area_m2 = area,
        cells = sum(!is.na(terra::values(cells, mat = FALSE))),
        same_value = identical(values[i], values[j]), stringsAsFactors = FALSE)
    }
  }
  if (length(rows) == 0L) return(list(pairs = pairs, cells = 0L))
  pairs <- do.call(rbind, rows)
  count <- terra::rasterize(terra::vect(sf::st_sf(value = 1, geometry = geom)), tmpl,
                            field = "value", fun = "sum", touches = FALSE)
  list(pairs = pairs, cells = sum(terra::values(count, mat = FALSE) > 1, na.rm = TRUE))
}

#' Dit au rapport les recouvrements d'une couche : combien de cellules, quels polygones, et
#' quelle valeur l'emporte. Sans recouvrement, le dit aussi.
report_polygon_overlaps <- function(report, polys, labels, values, tmpl, what) {
  section <- "Recouvrements de polygones"
  ov <- polygon_overlaps(polys, labels, values, tmpl)
  if (nrow(ov$pairs) == 0L) {
    return(report_add(report, section, sprintf("%s : aucun recouvrement entre polygones", what)))
  }
  report_add(report, section, sprintf(
    "%s : %d cellule(s) reçoivent plusieurs polygones ; en cas de recouvrement la plus petite valeur du raster l'emporte (règle indépendante de l'ordre du fichier)",
    what, ov$cells))
  for (k in seq_len(nrow(ov$pairs))) {
    p <- ov$pairs[k, ]
    report_add(report, section, sprintf(
      "%s : %s et %s se recouvrent sur %s m² (%d cellule(s)) ; %s",
      what, p$a, p$b, fr_num(round(p$area_m2, 1), 1), p$cells,
      if (p$same_value) "même valeur, sans effet sur le raster" else "valeurs différentes, la plus petite l'emporte"))
  }
  invisible(report)
}

# ------------------------------------------------------------------ stand_map : polygone nemeton par cellule

# Plus grande valeur de stand_map.tif (UInt16, contrat prepare.stand_map : maximum 65534 ; 65535 = nodata).
STAND_MAP_MAX_POLYGONS <- 65534L

#' Valeur de stand_map.tif de chaque polygone nemeton : le rang de son `stand_id` dans l'ordre
#' des identifiants (tri par octets, indépendant de la locale et de l'ordre du fichier). Arrête
#' si un `stand_id` manque ou se répète : la table de correspondance serait ambiguë, ou s'il y a
#' plus de STAND_MAP_MAX_POLYGONS polygones (UInt16 : la valeur 65535 est le nodata).
stand_map_values <- function(stand_id) {
  ids <- as.character(stand_id)
  if (length(ids) > STAND_MAP_MAX_POLYGONS) {
    stop(sprintf("nemeton_stands.gpkg : %d polygones, au-delà des %d que stand_map.tif (UInt16) peut numéroter ; réduire le fichier ou découper la zone",
                 length(ids), STAND_MAP_MAX_POLYGONS), call. = FALSE)
  }
  if (anyNA(ids) || any(!nzchar(ids))) {
    stop("nemeton_stands.gpkg : stand_id manquant", call. = FALSE)
  }
  if (anyDuplicated(ids) > 0L) {
    stop(sprintf("nemeton_stands.gpkg : stand_id en double (%s) : stand_map.csv serait ambigu",
                 paste(unique(ids[duplicated(ids)]), collapse = ", ")), call. = FALSE)
  }
  sorted <- ids[order(ids, method = "radix")]
  list(value = match(ids, sorted), names = sorted)
}

# ------------------------------------------------------------------ le module

#' Construit la grille et les rasters alignés d'une zone (mission 017). Rend la liste des
#' fichiers écrits. Arrête avec un message en français à la première entrée refusée. `report` :
#' rapport de prepare, déjà porteur des signalements de l'IFN quand `run_prepare()` l'a rempli.
prepare_grid <- function(zone_dir, cfg, validate = TRUE, report = new_report()) {
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

  # -- entrées : validées à l'entrée (spec §2), puis lues
  inputs <- list(
    inputs.forest_mask = inp("forest_mask.gpkg"), inputs.ser = inp("ser.gpkg"),
    inputs.dtm = inp("dtm.tif"), inputs.chm = inp("chm.tif"),
    inputs.lidar_tiles = inp("lidar_tiles.gpkg"),
    inputs.station_gradients = inp("station_gradients.tif"),
    inputs.station_type = inp("station_type.tif"), inputs.h_pot = inp("h_pot.tif"),
    inputs.station_types = inp("types.csv"),
    inputs.nemeton_stands = inp("nemeton_stands.gpkg"))
  # Toutes les entrées sont contrôlées AVANT la première écriture : une entrée refusée
  # ne laisse aucune sortie à moitié produite. types.csv (légende de station_type.tif) est
  # validé ici avant tout usage. L'inventaire vidéo est facultatif.
  for (k in seq_along(inputs)) check_input_file(inputs[[k]])
  if (file.exists(inp("inventaire_video.gpkg"))) {
    inputs$inputs.inventaire_video <- inp("inventaire_video.gpkg")
  }
  if (validate) {
    for (k in seq_along(inputs)) validate_file(names(inputs)[k], inputs[[k]], what = "entrée")
  }

  # -- polygones nemeton : lus et contrôlés ICI, avant la première écriture (dette M1a) : au-delà
  # de 65 534 polygones, stand_id manquant ou en double, prepare s'arrête (code 2) sans laisser
  # de sortie à moitié produite. stand_map.tif n'est écrit que plus bas.
  stands_sf <- read_layer_2154(inputs$inputs.nemeton_stands, "stands")
  if (!"stand_id" %in% names(stands_sf)) stop("nemeton_stands.gpkg : colonne stand_id absente", call. = FALSE)
  sm <- stand_map_values(stands_sf$stand_id)

  # -- grille : emprise du masque forestier, arrondie vers l'extérieur
  mask_sf <- read_layer_2154(inputs$inputs.forest_mask, "forest_mask")
  tmpl <- grid_template(sf::st_bbox(mask_sf), res)
  report_add(report, "Grille", sprintf(
    "%d colonnes x %d lignes de %s m, x de %s à %s, y de %s à %s (EPSG:2154, coin nord-ouest %s ; %s)",
    terra::ncol(tmpl), terra::nrow(tmpl), fr_num(res), fr_num(terra::xmin(tmpl), 1),
    fr_num(terra::xmax(tmpl), 1), fr_num(terra::ymin(tmpl), 1), fr_num(terra::ymax(tmpl), 1),
    fr_num(terra::xmin(tmpl), 1), fr_num(terra::ymax(tmpl), 1)))
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
  ser_values <- ser_value_table(ser)
  has_code <- !is.na(ser_values$value)
  report_polygon_overlaps(report, ser, sprintf("polygone %d (%s)", seq_len(nrow(ser)), ser$ser_code_igns),
                          ser_values$value, tmpl, "ser.gpkg")
  ser_r <- rasterize_polygons(ser[has_code, ], ser_values$value[has_code], tmpl)
  report_missing(report, ser_r, forest, "ser.tif", "aucune SER devinée")
  write_grid_raster(ser_r, out("ser.tif"), "INT2U")
  write_categories(ser_values$table$value, ser_values$table$name, out("ser.csv"),
                   extra = list(alluvium_code = ser_values$table$alluvium_code))
  report_add(report, "SER", sprintf(
    "ser.tif : %d valeur(s), une par couple distinct (SER, alluvions) ; %d d'entre elles portent un code d'alluvions (ser.csv, colonne alluvium_code)",
    nrow(ser_values$table), sum(!is.na(ser_values$table$alluvium_code))))
  written <- c(written, out("ser.tif"), out("ser.csv"))

  # -- MNH : H0 (percentile 95, PROVISOIRE) ; le MNH n'est pas rééchantillonné
  chm <- read_raster_2154(inputs$inputs.chm)
  h0 <- aggregate_h0(chm, tmpl)
  report_add(report, "H0", sprintf(
    "h0.tif : percentile %s du MNH de %s m sur chaque cellule de %s m (agrégation, sans rééchantillonnage) ; PROVISOIRE, à remplacer par le h_dom de typopeuplement (spec §5)",
    fr_num(100 * H0_PROBABILITY), fr_num(terra::res(chm)[1]), fr_num(res)))
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
  report_polygon_overlaps(report, tiles, sprintf("dalle %d", seq_len(nrow(tiles))), days, tmpl,
                          "lidar_tiles.gpkg")
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
  legend <- utils::read.csv(legend_path, sep = ";", stringsAsFactors = FALSE, fileEncoding = "UTF-8")
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

  # -- polygones nemeton : stand_map (ce que lit biomes, spec §4.1, §4.2)
  report_polygon_overlaps(report, stands_sf, as.character(stands_sf$stand_id), sm$value, tmpl,
                          "nemeton_stands.gpkg")
  stand_r <- rasterize_polygons(stands_sf, sm$value, tmpl)
  report_missing(report, stand_r, forest, "stand_map.tif", "hors de tout polygone nemeton (spec §4.2, traité par biomes)")
  write_grid_raster(stand_r, out("stand_map.tif"), "INT2U")
  write_categories(seq_along(sm$names), sm$names, out("stand_map.csv"))
  written <- c(written, out("stand_map.tif"), out("stand_map.csv"))

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
                   site_potential.tif = "prepare.site_potential", stand_map.tif = "prepare.stand_map")
    for (f in names(contracts)) {
      validate_file(contracts[[f]], out(f), grid = if (f == "grid.tif") NULL else grid_path)
    }
    tables <- c(ser.csv = "prepare.ser_categories", station_type.csv = "prepare.station_type_categories",
                site_potential.csv = "prepare.site_potential_bands",
                stand_map.csv = "prepare.stand_map_categories")
    for (f in names(tables)) validate_file(tables[[f]], out(f))
  }
  invisible(written)
}
