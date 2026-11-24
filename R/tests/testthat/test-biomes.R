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

# Zone d'essai : prepare est remplacé par des rasters écrits à la main.
zone_essai <- function() {
  z <- tempfile("zone_"); dir.create(file.path(z, "inputs"), recursive = TRUE)
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
  box <- function(x0, x1) sf::st_polygon(list(matrix(
    c(x0, BY1 - 100, x1, BY1 - 100, x1, BY1, x0, BY1, x0, BY1 - 100), ncol = 2, byrow = TRUE)))
  stands <- sf::st_sf(stand_id = c("S01", "S02"), species_espar = c("09", "61"),
                      source = c("inventaire", "synthetic_ml"),
                      geometry = sf::st_sfc(box(BX0, BX0 + 75), box(BX0 + 75, BX0 + 125), crs = 2154))
  sf::st_write(stands, file.path(z, "inputs", "nemeton_stands.gpkg"), layer = "stands", quiet = TRUE)
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
})
