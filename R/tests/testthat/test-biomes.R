# Tests de biomes : types de végétation, carte et rapport (mission 020, R/biomes.R).
# Coordonnées : EPSG:2154, x vers l'est, y vers le nord, en mètres ; les cellules d'un raster se
# comptent depuis le coin nord-ouest : cell_id = ligne * largeur + colonne, depuis 0.
# Tout est synthétique : la zone d'essai est une grille de 6 colonnes sur 4 lignes, de 25 m.

racine_bio <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
BX0 <- 700000   # x ouest
BY1 <- 6500100  # y nord

# Un biome minimal, conforme au contrat biomes.biome.
ecrire_biome <- function(dossier, station, stade, provisoire = "true", id = NULL) {
  id <- if (is.null(id)) paste(station, "futaie_fictive", stade, sep = "_") else id
  writeLines(c(sprintf("id: %s", id), sprintf("provisoire: %s", provisoire),
               "condition:", sprintf("  station: %s", station),
               "  typopeuplement: futaie_fictive", sprintf("  stade: %s", stade),
               "strates:", "  arboree:", "    composition:", "      \"09\": 1.0",
               "sources:", "  - \"synthetique : essai\""),
             file.path(dossier, paste0(id, ".yml")))
}

catalogue_essai <- function(biomes = list(c("type_sec", "mature"), c("type_frais", "mature"))) {
  d <- tempfile("biomes_"); dir.create(d)
  for (b in biomes) ecrire_biome(d, b[1], b[2])
  d
}

# Raster de la grille d'essai (6 x 4) rempli ligne par ligne depuis le coin nord-ouest.
raster_essai <- function(valeurs) {
  r <- terra::rast(xmin = BX0, xmax = BX0 + 150, ymin = BY1 - 100, ymax = BY1,
                   resolution = 25, crs = "EPSG:2154")
  terra::values(r) <- valeurs
  r
}

STANDS_ESSAI_TYPES <- list(stand_id = "string", species = "string", d130 = "float64", h = "float64",
                           density_ha = "float64", age = "int32", source = "string",
                           stand_id_source = "string")

# Zone d'essai : prepare est remplacé par des fichiers écrits à la main, aux formats de ses
# sorties (rasters, stand_map + .csv, stands.parquet). Il n'y a PAS de dossier inputs/ : biomes
# ne doit rien y lire.
zone_essai <- function() {
  z <- tempfile("zone_"); dir.create(z)
  uint <- function(v, nom) write_grid_raster(raster_essai(v), file.path(z, nom), "INT2U")
  uint(rep(1L, 24), "grid.tif")
  forest <- rep(1L, 24); forest[6] <- 0L                    # (ligne 0, colonne 5) : trouée
  uint(forest, "forest_mask.tif")
  station <- rep(c(1L, 1L, 1L, 2L, 2L, 2L), 4)
  station[1 * 6 + 1 + 1] <- NA                               # (1, 1) : station absente
  uint(station, "station_type.tif")
  write_categories(1:2, c("type_sec", "type_frais"), file.path(z, "station_type.csv"))
  h0 <- rep(25, 24)                                          # 25 / 30 : stade mature
  h0[2 * 6 + 4 + 1] <- 5                                     # (2, 4) : jeune, absent du catalogue
  h0[3 * 6 + 0 + 1] <- NA                                    # (3, 0) : hauteur absente
  write_grid_raster(raster_essai(h0), file.path(z, "h0.tif"), "FLT4S")
  write_grid_raster(raster_essai(rep(30, 24)), file.path(z, "site_potential.tif"), "FLT4S",
                    names = "h_pot_m")
  write_categories(1L, "h_pot_m", file.path(z, "site_potential.csv"))
  # polygones nemeton : S01 = colonnes 0 à 2 (x 0-75), S02 = colonnes 3 et 4 (x 75-125), colonne 5 hors polygone
  uint(rep(c(1L, 1L, 1L, 2L, 2L, NA), 4), "stand_map.tif")
  write_categories(1:2, c("S01", "S02"), file.path(z, "stand_map.csv"))
  write_parquet_tbl(data.frame(stand_id = c("S01", "S02"), species = c("09", "61"),
                               d130 = c(30, 30), h = c(25, 25), density_ha = c(300, 300),
                               age = c(60L, 60L), source = c("inventaire", "synthetic_ml"),
                               stand_id_source = c("a", "b"), stringsAsFactors = FALSE),
                    file.path(z, "stands.parquet"), STANDS_ESSAI_TYPES)
  z
}

config_essai <- function() list(zone = "essai")

# Le rapport est lu en octets (UTF-8) : les motifs de recherche le sont aussi (useBytes), sinon
# une locale C fausserait la comparaison des accents.
lire_rapport <- function(z) {
  f <- file.path(z, "rapport_biomes.html")
  rawToChar(readBin(f, "raw", file.size(f)))
}
attendu <- function(rapport, motif, fixed = FALSE) {
  octets <- rawToChar(charToRaw(enc2utf8(motif)))   # motif sans marque d'encodage, en octets UTF-8
  expect_true(grepl(octets, rapport, useBytes = TRUE, fixed = fixed), info = motif)
}

# Valide avec le vrai validateur (chemin absolu : les tests changent de dossier courant).
avec_vrai_validateur_biomes <- function(code) {
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = file.path(racine_bio, "contracts", "validate"))
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  force(code)
}

# ------------------------------------------------------------------ le catalogue

test_that("le catalogue du dépôt est lu, provisoire et sans doublon", {
  cat <- read_biome_catalog(file.path(racine_bio, "biomes"))
  expect_gt(nrow(cat), 0L)
  expect_false(anyDuplicated(cat$id) > 0L)
  expect_true(all(cat$stade %in% BIOMES_STAGES))
  expect_equal(cat$id, sort(cat$id))
})

test_that("un biome sans `provisoire: true` est refusé", {
  d <- tempfile("biomes_"); dir.create(d)
  ecrire_biome(d, "type_sec", "mature", provisoire = "false")
  expect_error(read_biome_catalog(d), "provisoire")
})

test_that("une condition en double ou un dossier vide est refusé", {
  d <- catalogue_essai()
  ecrire_biome(d, "type_sec", "mature", id = "autre_nom")
  expect_error(read_biome_catalog(d), "condition en double")
  vide <- tempfile("biomes_"); dir.create(vide)
  expect_error(read_biome_catalog(vide), "absent ou vide")
})

# ------------------------------------------------------------------ stade et attribution

test_that("stade : seuils provisoires, bornes basses incluses, NA sans plafond", {
  expect_equal(stage_from_ratio(c(0, 7.4, 7.5, 17.9, 18, 26.9, 27, 40), 30),
               c("young", "young", "pole", "pole", "mature", "mature", "old", "old"))
  expect_equal(stage_from_ratio(c(10, 10, NA), c(NA, 0, 30)), rep(NA_character_, 3))
})

test_that("attribution : cellule non forestière sans type, orpheline forestière avec sa raison", {
  cat <- data.frame(id = c("a", "b"), station = c("s1", "s2"),
                    typopeuplement = BIOMES_TYPOPEUPLEMENT, stade = c("mature", "old"),
                    stringsAsFactors = FALSE)
  station <- c("s1", "s2", "s1", NA, "s1", "s1")
  stage <- c("mature", "old", "young", "mature", NA, "mature")
  forest <- c(TRUE, TRUE, TRUE, TRUE, TRUE, FALSE)
  a <- assign_biomes(station, stage, forest, cat)
  expect_equal(a$index, c(1L, 2L, NA, NA, NA, NA))
  expect_equal(a$reason[3:4], c("combinaison absente du catalogue", "station absente"))
  expect_true(grepl("stade ind", a$reason[5], fixed = TRUE))
  expect_true(is.na(a$reason[6]))   # trouée : ni type ni orpheline
})

# ------------------------------------------------------------------ le module sur la zone d'essai

test_that("biomes_run : orphelines comptées et listées par cell_id, trouée non comptée", {
  z <- zone_essai()
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  veg <- terra::rast(file.path(z, "vegetation_map.tif"))
  v <- terra::values(veg, mat = FALSE)
  # cell_id attendus : (1,1) -> 7 ; (2,4) -> 16 ; (3,0) -> 18 ; la trouée (0,5) -> 5 est exclue
  expect_equal(which(is.na(v)) - 1L, c(5L, 7L, 16L, 18L))
  # un point du terrain tombe au bon endroit : le centre de (ligne 2, colonne 4), x puis y
  xy <- matrix(c(BX0 + 4.5 * 25, BY1 - 2.5 * 25), ncol = 2)
  expect_equal(terra::cellFromXY(veg, xy) - 1, 16)
  expect_true(is.na(terra::extract(veg, xy)[1, 1]))
  rapport <- lire_rapport(z)
  attendu(rapport, "3 cellules forestières sans type de végétation", fixed = TRUE)
  attendu(rapport, "cell_id [^:]*: 7, 16, 18")
  expect_false(grepl("7, 16, 18, 5|5, 7", rapport))
  attendu(rapport, "station absente : 1 cellule")
  attendu(rapport, "combinaison absente du catalogue : 1 cellule")
  attendu(rapport, "stade indéterminé")
})

test_that("biomes_run : une cellule typée prend le biome de sa station et de son stade", {
  z <- zone_essai()
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  v <- terra::values(terra::rast(file.path(z, "vegetation_map.tif")), mat = FALSE)
  leg <- utils::read.csv(file.path(z, "vegetation_map.csv"), stringsAsFactors = FALSE)
  nom <- leg$name[match(v, leg$value)]
  expect_equal(nom[1], "type_sec_futaie_fictive_mature")    # (0,0)
  expect_equal(nom[4], "type_frais_futaie_fictive_mature")  # (0,3)
  expect_equal(leg$name, sort(leg$name))
})

test_that("biomes_run : le rapport dit hors polygone, mono-essence et synthetic_ml", {
  z <- zone_essai()
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  rapport <- lire_rapport(z)
  # colonne 5 hors polygone : 3 cellules forestières (lignes 1 à 3 ; (0,5) est la trouée)
  attendu(rapport, "3 cellules forestières hors polygone nemeton", fixed = TRUE)
  # elles sont signalées une à une (spec §4.2) : (1,5), (2,5), (3,5) -> cell_id 11, 17, 23
  attendu(rapport, "cell_id [^:]*des cellules signalées : 11, 17, 23")
  attendu(rapport, "polygone S01 : mono-essence")
  attendu(rapport, "polygone S02 : mono-essence")
  attendu(rapport, "polygone S02 : source synthetic_ml")
  expect_false(grepl("polygone S01 : source synthetic_ml", rapport, fixed = TRUE))
  attendu(rapport, "<meta charset=\"utf-8\">", fixed = TRUE)
  # accents écrits en UTF-8 (octets c3 a9), jamais en texte « <c3><a9> » (locale C)
  octets <- charToRaw(rapport)
  expect_true(any(octets[-length(octets)] == as.raw(0xc3) & octets[-1] == as.raw(0xa9)))
  expect_false(grepl("<c3>", rapport, fixed = TRUE))
  attendu(rapport, "SYNTHÉTIQUES")
})

test_that("biomes_run : aucune orpheline, le rapport le dit", {
  z <- zone_essai()
  # station et hauteur complétées : plus d'orpheline sauf le stade jeune absent du catalogue
  cat <- catalogue_essai(list(c("type_sec", "mature"), c("type_frais", "mature"),
                              c("type_frais", "young")))
  terra::writeRaster(raster_essai(rep(c(1L, 1L, 1L, 2L, 2L, 2L), 4)), file.path(z, "station_type.tif"),
                     overwrite = TRUE, datatype = "INT2U", NAflag = 65535)
  h0 <- rep(25, 24); h0[2 * 6 + 4 + 1] <- 5
  terra::writeRaster(raster_essai(h0), file.path(z, "h0.tif"), overwrite = TRUE, datatype = "FLT4S",
                     NAflag = -9999)
  suppressMessages(biomes_run(z, config_essai(), cat, validate = FALSE))
  attendu(lire_rapport(z), "0 cellule forestière sans type de végétation", fixed = TRUE)
})

test_that("biomes_run : plusieurs familles d'essences, on s'arrête sans deviner", {
  z <- zone_essai()
  r <- raster_essai(rep(30, 24)); r2 <- raster_essai(rep(28, 24))
  write_grid_raster(c(r, r2), file.path(z, "site_potential.tif"), "FLT4S", names = c("a", "b"))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)),
               "2 bandes")
})

test_that("biomes_run : une sortie de prepare absente est une erreur claire", {
  z <- zone_essai()
  unlink(file.path(z, "h0.tif"))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)),
               "h0.tif absent")
})

test_that("biomes_run : sorties validées par le vrai validateur", {
  z <- zone_essai()
  avec_vrai_validateur_biomes(suppressMessages(capture.output(
    biomes_run(z, config_essai(), file.path(racine_bio, "biomes"), validate = TRUE))))
  expect_true(all(file.exists(file.path(z, c("vegetation_map.tif", "vegetation_map.csv",
                                             "rapport_biomes.html")))))
})

# ------------------------------------------------------------------ stand_map, stands.parquet, rapport

test_that("biomes ne lit rien sous inputs/ : la zone d'essai n'en a pas, et tout passe", {
  z <- zone_essai()
  expect_false(dir.exists(file.path(z, "inputs")))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)), NA)
  expect_false(dir.exists(file.path(z, "inputs")))
})

test_that("biomes : sans stand_map ou sans stands.parquet, erreur claire ; stand_id inconnu refusé", {
  z <- zone_essai(); unlink(file.path(z, "stand_map.csv"))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)),
               "stand_map.csv absent")
  z <- zone_essai(); unlink(file.path(z, "stands.parquet"))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)),
               "stands.parquet absent")
  z <- zone_essai()
  write_categories(1:2, c("S01", "S99"), file.path(z, "stand_map.csv"))
  expect_error(suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE)),
               "S99")
})

test_that("biomes_stands : le polygone de chaque cellule vient de stand_map, essence et source de stands.parquet", {
  z <- zone_essai()
  grid <- terra::rast(file.path(z, "grid.tif"))
  st <- biomes_stands(z, grid)
  expect_equal(st$table$stand_id, c("S01", "S02"))
  expect_equal(st$table$species, c("09", "61"))                 # zéro de tête gardé
  expect_equal(st$rank, rep(c(1L, 1L, 1L, 2L, 2L, NA), 4))
  # le centre de (ligne 0, colonne 3) est dans S02 : x vers l'est d'abord, y vers le nord
  cell <- terra::cellFromXY(grid, cbind(BX0 + 3.5 * 25, BY1 - 0.5 * 25))
  expect_equal(st$table$stand_id[st$rank[cell]], "S02")
})

test_that("cellules forestières hors polygone : cell_id, x et y des centres (x est, y nord)", {
  z <- zone_essai()
  grid <- terra::rast(file.path(z, "grid.tif"))
  forest <- rep(TRUE, 24); forest[6] <- FALSE
  out <- outside_polygon_cells(grid, forest, biomes_stands(z, grid)$rank)
  expect_equal(out$cell_id, c(11, 17, 23))
  # cell_id 11 = ligne 1, colonne 5 : centre à 5,5 mailles de l'ouest et 1,5 maille du nord
  expect_equal(c(out$x[1], out$y[1]), c(BX0 + 5.5 * 25, BY1 - 1.5 * 25))
  expect_equal(terra::cellFromXY(grid, cbind(out$x, out$y)) - 1, out$cell_id)
})

test_that("au-delà du seuil, les cell_id hors polygone vont dans un CSV joint, sinon dans le rapport", {
  expect_equal(BIOMES_MAX_LISTED_CELLS, 50L)
  assign("BIOMES_MAX_LISTED_CELLS", 2L, envir = globalenv())
  on.exit(assign("BIOMES_MAX_LISTED_CELLS", 50L, envir = globalenv()), add = TRUE)
  z <- zone_essai()
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  csv <- file.path(z, "rapport_biomes_hors_polygone.csv")
  expect_true(file.exists(csv))
  tab <- utils::read.csv(csv)
  expect_equal(names(tab), c("cell_id", "x", "y"))
  expect_equal(tab$cell_id, c(11, 17, 23))
  expect_equal(c(tab$x[1], tab$y[1]), c(BX0 + 5.5 * 25, BY1 - 1.5 * 25))
  rapport <- lire_rapport(z)
  attendu(rapport, "des 2 premières des 3 cellules signalées : 11, 17 ;")
  attendu(rapport, "rapport_biomes_hors_polygone.csv", fixed = TRUE)
  expect_false(grepl("11, 17, 23", rapport, fixed = TRUE))
  # le seuil relevé : plus de CSV, et celui d'une exécution précédente disparaît
  assign("BIOMES_MAX_LISTED_CELLS", 50L, envir = globalenv())
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  expect_false(file.exists(csv))
  attendu(lire_rapport(z), "des cellules signalées : 11, 17, 23")
})

test_that("le rapport écrit les décimales à la française et rappelle que H0 est provisoire", {
  z <- zone_essai()
  suppressMessages(biomes_run(z, config_essai(), catalogue_essai(), validate = FALSE))
  rapport <- lire_rapport(z)
  attendu(rapport, "seuils provisoires \\(0,25 ; 0,6 ; 0,9\\)")
  expect_false(grepl("0.25", rapport, fixed = TRUE))
  expect_false(grepl("0.6", rapport, fixed = TRUE))
  attendu(rapport, "H0 \\(h0.tif\\) est PROVISOIRE : percentile 95 du MNH")
  attendu(rapport, "h_dom de typopeuplement")
})

# ------------------------------------------------------------------ outils communs

# Fonctions définies au premier niveau d'un fichier R : noms des `nom <- function`.
fonctions_definies <- function(fichier) {
  exprs <- parse(fichier, keep.source = FALSE)
  noms <- vapply(exprs, function(e) {
    if (is.call(e) && identical(e[[1]], as.name("<-")) && is.call(e[[3]]) &&
        identical(e[[3]][[1]], as.name("function"))) as.character(e[[2]]) else NA_character_
  }, character(1))
  noms[!is.na(noms)]
}

# Noms utilisés dans un fichier R (appelés ou passés en argument).
symboles_utilises <- function(fichier) {
  pd <- utils::getParseData(parse(fichier, keep.source = TRUE))
  unique(pd$text[pd$token %in% c("SYMBOL_FUNCTION_CALL", "SYMBOL", "SYMBOL_FUNCTION")])
}

test_that("biomes.R et prepare_trees.R n'appellent aucune fonction définie dans prepare_grid.R", {
  definies <- fonctions_definies(file.path(racine_bio, "R", "prepare_grid.R"))
  expect_gt(length(definies), 5L)
  for (f in c("biomes.R", "prepare_trees.R", "prepare_ifn.R")) {
    pris <- intersect(definies, symboles_utilises(file.path(racine_bio, "R", f)))
    expect_equal(pris, character(0), info = sprintf("%s appelle %s", f, paste(pris, collapse = ", ")))
  }
})

test_that("les outils communs sont dans commun.R, et aucune fonction n'est définie dans deux fichiers", {
  commun <- fonctions_definies(file.path(racine_bio, "R", "commun.R"))
  for (nom in c("new_report", "report_add", "html_escape", "write_html_report", "read_layer_2154",
                "read_raster_2154", "rasterize_polygons", "write_grid_raster", "write_categories",
                "validate_file", "prepare_zone_dir", "check_input_file")) {
    expect_true(nom %in% commun, info = nom)
  }
  grille <- fonctions_definies(file.path(racine_bio, "R", "prepare_grid.R"))
  expect_equal(intersect(commun, grille), character(0))
  tous <- unlist(lapply(list.files(file.path(racine_bio, "R"), pattern = "[.]R$", full.names = TRUE),
                        fonctions_definies))
  expect_equal(unique(tous[duplicated(tous)]), character(0))
})

test_that("commun.R se charge seul : il ne dépend d'aucun module", {
  pris <- character()
  for (f in c("prepare_grid.R", "biomes.R", "prepare_trees.R", "prepare_ifn.R")) {
    pris <- c(pris, intersect(fonctions_definies(file.path(racine_bio, "R", f)),
                              symboles_utilises(file.path(racine_bio, "R", "commun.R"))))
  }
  expect_equal(pris, character(0))
})

test_that("run_biomes : le jeu fictif ne laisse aucune cellule forestière sans type non signalée", {
  # Autonome : une racine temporaire reçoit les entrées du jeu fictif et le catalogue ; prepare
  # y tourne d'abord (vrai validateur), puis biomes. Le dépôt n'est pas touché.
  racine_tmp <- tempfile("racine_"); zone <- file.path(racine_tmp, "tests", "fixtures", "zone_fictive")
  dir.create(zone, recursive = TRUE)
  src <- file.path(racine_bio, "tests", "fixtures", "zone_fictive")
  file.copy(file.path(src, c("inputs", "params")), zone, recursive = TRUE)
  file.copy(file.path(racine_bio, "biomes"), racine_tmp, recursive = TRUE)
  dir.create(file.path(racine_tmp, "contracts"))
  file.copy(file.path(racine_bio, "contracts", "species.csv"), file.path(racine_tmp, "contracts"))
  ancien_wd <- setwd(racine_bio)
  ancienne_racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = NA)
  Sys.setenv(SYLVIGENESE_ROOT = racine_tmp)
  on.exit({
    setwd(ancien_wd)
    if (is.na(ancienne_racine)) Sys.unsetenv("SYLVIGENESE_ROOT") else Sys.setenv(SYLVIGENESE_ROOT = ancienne_racine)
  }, add = TRUE)
  config <- file.path(racine_bio, "config.yml")
  invisible(capture.output(suppressMessages(avec_vrai_validateur_biomes({
    sp <- run_prepare(config)
    s <- run_biomes(config)
  }))))
  expect_equal(sp, 0L)
  expect_equal(s, 0L)
  attendu(lire_rapport(zone), "0 cellule forestière sans type de végétation", fixed = TRUE)
  # 176 cellules forestières hors polygone nemeton : 50 dans le rapport, toutes dans le CSV joint
  attendu(lire_rapport(zone), "des 50 premières des 176 cellules signalées")
  tab <- utils::read.csv(file.path(zone, "rapport_biomes_hors_polygone.csv"))
  expect_equal(nrow(tab), 176L)
  expect_equal(tab$cell_id[1], 814)   # ligne 20, colonne 14 : x 700362,5 ; y 6500487,5 (forêt sans polygone)
  expect_equal(c(tab$x[1], tab$y[1]), c(700362.5, 6500487.5))
})
