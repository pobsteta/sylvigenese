# biomes : types de végétation, carte et rapport (spec §4, §8, §11 ; mission 020).
#
# Lit les sorties de prepare sous <zone>/ (grille, forest_mask, station_type, h0,
# site_potential, stand_map.tif + .csv, stands.parquet) et le catalogue du dépôt biomes/*.yml ;
# n'ouvre aucune entrée de inputs/. Écrit sous <zone>/ :
#   vegetation_map.tif + vegetation_map.csv   type de végétation par cellule (UInt16) et sa
#                                             légende (valeur, nom) ; le nom est l'`id` du biome
#   rapport_biomes.html                       ce que biomes a attribué, ou laissé vide
#   rapport_biomes_hors_polygone.csv          (seulement s'il y a plus de 50 cellules forestières
#                                             hors polygone) la liste complète : cell_id, x, y
#
# Un type de végétation = une combinaison station × type de peuplement × stade (BRIEF §5),
# celle de `condition` dans le catalogue.
#  - station : le nom du type de station de la cellule (station_type.csv) ;
#  - stade : tiré de la position de la hauteur H0 sous le plafond h_pot (spec §8). Les seuils
#    ci-dessous sont PROVISOIRES : ils ne viennent d'aucune source ;
#  - type de peuplement : PROVISOIRE, une seule valeur. Aucune entrée ne le fournit encore
#    (le module typopeuplement n'est pas branché) ; le rapport le dit.
#
# Règles :
#  - signaler plutôt que deviner : une cellule forestière sans type de végétation reste au
#    nodata et figure au rapport (nombre, puis liste des cell_id) ; aucune valeur par défaut ;
#  - cell_id = ligne × largeur + colonne dans grid.tif, ligne et colonne comptées depuis 0 à
#    partir du coin nord-ouest ;
#  - les cellules non forestières (trouée) n'ont pas de type et ne sont pas signalées comme
#    orphelines (spec §11, M1a) ;
#  - le rapport dit aussi les polygones nemeton mono-essence (spec §4.1), les cellules
#    forestières hors polygone (spec §4.2 : « la cellule est signalée », donc leurs cell_id :
#    la liste complète, ou les 50 premiers et un CSV joint si elles sont plus nombreuses) et
#    les polygones en synthetic_ml (spec §4.5) ;
#  - les polygones nemeton viennent de stand_map.tif (+ .csv, name = stand_id) et de
#    stands.parquet (species, source), écrits par prepare ; biomes ne lit pas inputs/.
#
# Dépend de R/commun.R (outils communs à tous les modules R, spec §2), et d'aucun fichier d'un
# autre module.

# Stades (énumération `stage`, contracts/json/enums/stage.json), du plus jeune au plus âgé.
BIOMES_STAGES <- c("young", "pole", "mature", "old")
# Rapport H0 / h_pot au-dessous duquel une cellule est jeune, puis perchis, puis mature ; au
# delà, vieux. PROVISOIRE : seuils inventés pour le jeu fictif (aucune source citée).
BIOMES_STAGE_BREAKS <- c(0.25, 0.60, 0.90)
# Type de peuplement unique, PROVISOIRE (voir l'en-tête).
BIOMES_TYPOPEUPLEMENT <- "futaie_fictive"
# Source des polygones nemeton dont le MNH est déjà compté (spec §4.5).
BIOMES_SYNTHETIC_ML <- "synthetic_ml"
# Au-delà de ce nombre, les cell_id des cellules hors polygone vont dans un CSV joint.
BIOMES_MAX_LISTED_CELLS <- 50L

# ------------------------------------------------------------------ le catalogue

#' Lit biomes/*.yml. Arrête si le dossier est vide, si un fichier n'est pas marqué
#' `provisoire: true` ou si deux fichiers ont la même condition ou le même `id`.
#' Rend une table : id, station, typopeuplement, stade, file (triée par id, donc stable).
read_biome_catalog <- function(biomes_dir) {
  files <- sort(list.files(biomes_dir, pattern = "[.]yml$", full.names = TRUE))
  if (length(files) == 0L) {
    stop(sprintf("catalogue de biomes absent ou vide : %s", biomes_dir), call. = FALSE)
  }
  rows <- lapply(files, function(f) {
    b <- tryCatch(
      yaml::yaml.load(paste(readLines(f, warn = FALSE, encoding = "UTF-8"), collapse = "\n")),
      error = function(e) stop(sprintf("biome illisible (%s) : %s", f, conditionMessage(e)),
                               call. = FALSE))
    if (!isTRUE(b$provisoire)) {
      stop(sprintf("biome %s sans `provisoire: true` : toute valeur écologique vient d'une source citée ou est provisoire",
                   basename(f)), call. = FALSE)
    }
    data.frame(id = as.character(b$id), station = as.character(b$condition$station),
               typopeuplement = as.character(b$condition$typopeuplement),
               stade = as.character(b$condition$stade), file = f, stringsAsFactors = FALSE)
  })
  cat <- do.call(rbind, rows)
  if (anyDuplicated(cat$id)) {
    stop(sprintf("biomes : id en double : %s", paste(unique(cat$id[duplicated(cat$id)]), collapse = ", ")),
         call. = FALSE)
  }
  key <- biome_key(cat$station, cat$typopeuplement, cat$stade)
  if (anyDuplicated(key)) {
    stop(sprintf("biomes : condition en double (station | peuplement | stade) : %s",
                 paste(unique(key[duplicated(key)]), collapse = " ; ")), call. = FALSE)
  }
  cat <- cat[order(cat$id), ]
  rownames(cat) <- NULL
  cat
}

biome_key <- function(station, typopeuplement, stade) paste(station, typopeuplement, stade, sep = "|")

# ------------------------------------------------------------------ stade et attribution

#' Stade d'après le rapport hauteur / plafond (BIOMES_STAGE_BREAKS, provisoire). NA si le
#' rapport est NA ou si le plafond n'est pas strictement positif : jamais de stade deviné.
stage_from_ratio <- function(h, h_pot, breaks = BIOMES_STAGE_BREAKS) {
  h_pot <- rep_len(h_pot, length(h))
  ratio <- ifelse(!is.na(h_pot) & h_pot > 0, h / h_pot, NA_real_)
  idx <- findInterval(ratio, breaks) + 1L   # 1 : < breaks[1] ; ... ; 4 : >= breaks[3]
  BIOMES_STAGES[idx]
}

#' Pour chaque cellule : rang de son biome dans `catalog`, NA si la cellule n'est pas
#' forestière ou si sa combinaison n'est pas au catalogue. `reason` dit pourquoi pour les
#' cellules forestières sans type : "station absente", "stade indéterminé" ou "hors catalogue".
assign_biomes <- function(station, stage, forest, catalog, typopeuplement = BIOMES_TYPOPEUPLEMENT) {
  key <- biome_key(station, typopeuplement, stage)
  idx <- match(key, biome_key(catalog$station, catalog$typopeuplement, catalog$stade))
  idx[is.na(station) | is.na(stage)] <- NA_integer_
  idx[!forest] <- NA_integer_
  reason <- rep(NA_character_, length(idx))
  orphan <- forest & is.na(idx)
  reason[orphan & is.na(station)] <- "station absente"
  reason[orphan & !is.na(station) & is.na(stage)] <- "stade indéterminé (hauteur ou plafond absent)"
  reason[orphan & !is.na(station) & !is.na(stage)] <- "combinaison absente du catalogue"
  list(index = idx, reason = reason)
}

# ------------------------------------------------------------------ rapport

#' Écrit rapport_biomes.html (UTF-8), les lignes groupées par section.
write_biomes_report <- function(report, path) {
  write_html_report(report, path, "Rapport de biomes", "Rapport de biomes : types de végétation")
}

# ------------------------------------------------------------------ le module

biomes_read_grid_raster <- function(zone_dir, name, grid) {
  p <- file.path(zone_dir, name)
  if (!file.exists(p)) {
    stop(sprintf("%s absent : lancer prepare d'abord (%s)", name, p), call. = FALSE)
  }
  r <- terra::rast(p)
  if (!isTRUE(terra::compareGeom(r, grid, stopOnError = FALSE))) {
    stop(sprintf("%s n'est pas aligné sur grid.tif", name), call. = FALSE)
  }
  r
}

#' Nom du type de station de chaque cellule (NA sans valeur), d'après station_type.csv.
biomes_station_names <- function(zone_dir, station_type) {
  leg_path <- file.path(zone_dir, "station_type.csv")
  if (!file.exists(leg_path)) stop(sprintf("station_type.csv absent : %s", leg_path), call. = FALSE)
  leg <- utils::read.csv(leg_path, stringsAsFactors = FALSE, encoding = "UTF-8")
  v <- terra::values(station_type, mat = FALSE)
  nm <- leg$name[match(v, leg$value)]
  unknown <- unique(v[!is.na(v) & is.na(nm)])
  if (length(unknown) > 0L) {
    stop(sprintf("station_type.tif : valeur(s) %s absente(s) de station_type.csv",
                 paste(unknown, collapse = ", ")), call. = FALSE)
  }
  list(names = nm, legend = leg)
}

#' Plafond h_pot de chaque cellule. Une seule bande est attendue : avec plusieurs familles
#' d'essences, le stade dépendrait d'un choix de famille qui n'est pas fait ; on s'arrête.
biomes_ceiling <- function(zone_dir, grid) {
  hp <- biomes_read_grid_raster(zone_dir, "site_potential.tif", grid)
  if (terra::nlyr(hp) != 1L) {
    stop(sprintf("site_potential.tif a %d bandes (familles d'essences) : le stade d'une cellule ne se définit pas sans choisir une famille ; décision à prendre, rien n'est deviné",
                 terra::nlyr(hp)), call. = FALSE)
  }
  terra::values(hp, mat = FALSE)
}

#' Polygones nemeton, d'après les sorties de prepare : rend, par cellule, le rang du polygone
#' qui la contient dans la table `table` (NA hors polygone), et cette table (stand_id, species,
#' source, lue dans stands.parquet). stand_map.csv donne le stand_id de chaque valeur de
#' stand_map.tif ; un stand_id absent de stands.parquet est une erreur.
biomes_stands <- function(zone_dir, grid) {
  csv <- file.path(zone_dir, "stand_map.csv")
  if (!file.exists(csv)) stop(sprintf("stand_map.csv absent : lancer prepare d'abord (%s)", csv), call. = FALSE)
  pq <- file.path(zone_dir, "stands.parquet")
  if (!file.exists(pq)) stop(sprintf("stands.parquet absent : lancer prepare d'abord (%s)", pq), call. = FALSE)
  value <- terra::values(biomes_read_grid_raster(zone_dir, "stand_map.tif", grid), mat = FALSE)
  cats <- utils::read.csv(csv, stringsAsFactors = FALSE, encoding = "UTF-8", colClasses = c(name = "character"))
  stands <- read_parquet_tbl(pq)
  table <- data.frame(stand_id = as.character(stands$stand_id), species = as.character(stands$species),
                      source = as.character(stands$source), stringsAsFactors = FALSE)
  missing_ids <- setdiff(cats$name, table$stand_id)
  if (length(missing_ids) > 0L) {
    stop(sprintf("stand_map.csv : stand_id absent(s) de stands.parquet : %s",
                 paste(missing_ids, collapse = ", ")), call. = FALSE)
  }
  unknown <- setdiff(unique(value[!is.na(value)]), cats$value)
  if (length(unknown) > 0L) {
    stop(sprintf("stand_map.tif : valeur(s) %s absente(s) de stand_map.csv",
                 paste(unknown, collapse = ", ")), call. = FALSE)
  }
  rank <- match(cats$name[match(value, cats$value)], table$stand_id)
  list(rank = as.integer(rank), table = table)
}

#' Cellules forestières hors polygone nemeton (spec §4.2) : data.frame (cell_id, x, y), x vers
#' l'est et y vers le nord, au centre de la cellule, en EPSG:2154. cell_id = ligne × largeur +
#' colonne depuis 0 au coin nord-ouest, comme ailleurs dans ce module.
outside_polygon_cells <- function(grid, forest, stand_rank) {
  cells <- which(forest & is.na(stand_rank))
  xy <- if (length(cells) > 0L) terra::xyFromCell(grid, cells) else matrix(numeric(), 0L, 2L)
  data.frame(cell_id = cells - 1L, x = xy[, 1], y = xy[, 2])
}

#' Remplit rapport_biomes.html : catalogue, cellules sans type, hors polygone, mono-essence,
#' synthetic_ml, répartition.
report_biomes <- function(report, catalog, assign, forest, stand_rank, stands, ncol_grid,
                          station_legend, outside = NULL, outside_csv = NULL) {
  # -- catalogue
  report_add(report, "Catalogue", sprintf(
    "%d types de végétation au catalogue, tous marqués provisoire : valeurs SYNTHÉTIQUES du jeu fictif, aucune n'est écologique",
    nrow(catalog)))
  report_add(report, "Catalogue", sprintf(
    "type de peuplement : une seule valeur provisoire (%s), faute d'entrée typopeuplement ; stades tirés du rapport H0 / h_pot avec des seuils provisoires (%s), sans source",
    BIOMES_TYPOPEUPLEMENT, paste(fr_num(BIOMES_STAGE_BREAKS), collapse = " ; ")))
  report_add(report, "Catalogue", sprintf(
    "H0 (h0.tif) est PROVISOIRE : percentile %s du MNH sur la cellule, à remplacer par le h_dom de typopeuplement (spec §5) ; les stades, donc les types de végétation, en dépendent",
    fr_num(100 * H0_PROBABILITY)))
  unknown <- setdiff(unique(catalog$station), station_legend$name)
  if (length(unknown) > 0L) {
    report_add(report, "Catalogue", sprintf(
      "station(s) du catalogue absente(s) de station_type.csv : %s", paste(unknown, collapse = ", ")))
  }
  no_biome <- setdiff(station_legend$name, catalog$station)
  if (length(no_biome) > 0L) {
    report_add(report, "Catalogue", sprintf(
      "type(s) de station sans aucun biome au catalogue : %s", paste(no_biome, collapse = ", ")))
  }

  # -- cellules forestières sans type de végétation
  section <- "Cellules forestières sans type de végétation"
  orphan <- forest & is.na(assign$index)
  n_orphan <- sum(orphan)
  plural <- function(n, one, many) sprintf("%d %s", n, if (n > 1L) many else one)
  if (n_orphan == 0L) {
    report_add(report, section, sprintf(
      "0 cellule forestière sans type de végétation (sur %s)", plural(sum(forest), "cellule forestière", "cellules forestières")))
  } else {
    report_add(report, section, sprintf(
      "%s sans type de végétation, laissée(s) au nodata ; aucune valeur par défaut",
      plural(n_orphan, "cellule forestière", "cellules forestières")))
    for (why in sort(unique(assign$reason[orphan]))) {
      report_add(report, section, sprintf("%s : %s", why,
                        plural(sum(orphan & assign$reason == why, na.rm = TRUE), "cellule", "cellules")))
    }
    ids <- which(orphan) - 1L   # cell_id = ligne * largeur + colonne, depuis 0 : rang - 1 en ordre ligne par ligne
    report_add(report, section, sprintf(
      "cell_id (ligne × %d + colonne, depuis le coin nord-ouest de grid.tif) : %s", ncol_grid,
      paste(ids, collapse = ", ")))
  }

  # -- hors polygone nemeton (spec §4.2)
  section <- "Hors polygone nemeton"
  out <- forest & is.na(stand_rank)
  report_add(report, section, sprintf(
    "%s hors polygone nemeton : l'essence vient du type de végétation (species_source = vegetation_type) et ces cellules sont signalées ; %d d'entre elles ont un type de végétation, %d n'en ont pas",
    plural(sum(out), "cellule forestière", "cellules forestières"),
    sum(out & !is.na(assign$index)), sum(out & is.na(assign$index))))
  if (sum(out) > 0L && !is.null(outside)) {
    coord <- "cell_id (ligne × %d + colonne, depuis 0 au coin nord-ouest de grid.tif)"
    if (nrow(outside) <= BIOMES_MAX_LISTED_CELLS) {
      report_add(report, section, sprintf(paste0(coord, " des cellules signalées : %s"), ncol_grid,
                                          paste(outside$cell_id, collapse = ", ")))
    } else {
      report_add(report, section, sprintf(
        paste0(coord, " des %d premières des %d cellules signalées : %s ; liste complète (cell_id, x est, y nord, EPSG:2154) dans %s"),
        ncol_grid, BIOMES_MAX_LISTED_CELLS, nrow(outside),
        paste(utils::head(outside$cell_id, BIOMES_MAX_LISTED_CELLS), collapse = ", "), outside_csv))
    }
  }

  # -- mono-essence (spec §4.1) et synthetic_ml (spec §4.5)
  for (k in seq_len(nrow(stands))) {
    s <- stands[k, ]
    n_in <- sum(forest & !is.na(stand_rank) & stand_rank == k)
    report_add(report, "Polygones nemeton : mono-essence", sprintf(
      "polygone %s : mono-essence, une seule essence (espar %s), %s dans la forêt ; essence et densité celles du polygone",
      s$stand_id, s$species, plural(n_in, "cellule", "cellules")))
    if (identical(s$source, BIOMES_SYNTHETIC_ML)) {
      report_add(report, "Polygones nemeton : synthetic_ml", sprintf(
        "polygone %s : source %s, sa hauteur vient déjà du MNH ; le MNH n'est pas compté une seconde fois",
        s$stand_id, BIOMES_SYNTHETIC_ML))
    }
  }

  # -- répartition
  counts <- table(factor(assign$index[!is.na(assign$index)], levels = seq_len(nrow(catalog))))
  for (k in seq_len(nrow(catalog))) {
    if (counts[[k]] > 0L) {
      report_add(report, "Répartition des types de végétation", sprintf(
        "%s : %s", catalog$id[k], plural(counts[[k]], "cellule", "cellules")))
    }
  }
  invisible(report)
}

#' Attribue un type de végétation à chaque cellule forestière d'une zone et écrit
#' vegetation_map.tif, vegetation_map.csv et rapport_biomes.html. Rend la liste des fichiers
#' écrits. Arrête avec un message en français à la première entrée absente ou refusée.
biomes_run <- function(zone_dir, cfg, biomes_dir = NULL, validate = TRUE) {
  out <- function(f) file.path(zone_dir, f)
  if (is.null(biomes_dir)) {
    biomes_dir <- file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."), "biomes")
  }
  catalog <- read_biome_catalog(biomes_dir)
  if (validate) {
    status <- call_validator(c("biomes.biome", catalog$file))
    if (!identical(status, 0L)) {
      stop(sprintf("catalogue de biomes refusé par le validateur (code %s) : %s", status, biomes_dir),
           call. = FALSE)
    }
  }
  grid_path <- out("grid.tif")
  if (!file.exists(grid_path)) {
    stop(sprintf("grid.tif absent : lancer prepare d'abord (%s)", grid_path), call. = FALSE)
  }
  grid <- terra::rast(grid_path)
  forest_r <- biomes_read_grid_raster(zone_dir, "forest_mask.tif", grid)
  forest <- terra::values(forest_r, mat = FALSE)
  forest <- !is.na(forest) & forest == 1
  station <- biomes_station_names(zone_dir, biomes_read_grid_raster(zone_dir, "station_type.tif", grid))
  h0 <- terra::values(biomes_read_grid_raster(zone_dir, "h0.tif", grid), mat = FALSE)
  stage <- stage_from_ratio(h0, biomes_ceiling(zone_dir, grid))
  assign <- assign_biomes(station$names, stage, forest, catalog)

  report <- new_report("biomes")
  stands <- biomes_stands(zone_dir, grid)
  outside <- outside_polygon_cells(grid, forest, stands$rank)

  # carte : valeur = rang du biome (catalogue trié par id), nodata ailleurs
  vegetation <- terra::rast(grid)
  terra::values(vegetation) <- assign$index
  write_grid_raster(vegetation, out("vegetation_map.tif"), "INT2U")
  write_categories(seq_len(nrow(catalog)), catalog$id, out("vegetation_map.csv"))
  written <- c(out("vegetation_map.tif"), out("vegetation_map.csv"))

  # cell_id des cellules forestières hors polygone : dans le rapport s'il y en a peu, sinon un CSV joint
  outside_csv <- "rapport_biomes_hors_polygone.csv"
  if (nrow(outside) > BIOMES_MAX_LISTED_CELLS) {
    utils::write.csv(outside, out(outside_csv), row.names = FALSE, fileEncoding = "UTF-8")
    written <- c(written, out(outside_csv))
  } else {
    unlink(out(outside_csv))   # pas de liste périmée d'une exécution précédente
  }
  report_biomes(report, catalog, assign, forest, stands$rank, stands$table, terra::ncol(grid),
                station$legend, outside, outside_csv)
  report_path <- out("rapport_biomes.html")
  write_biomes_report(report, report_path)
  written <- c(written, report_path)

  if (validate) {
    validate_file("biomes.vegetation_map", out("vegetation_map.tif"), grid = grid_path)
    validate_file("biomes.vegetation_categories", out("vegetation_map.csv"))
  }
  invisible(written)
}
