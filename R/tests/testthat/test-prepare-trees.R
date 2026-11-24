# Tests de prepare : arbres détectés et peuplements (mission 018, R/prepare_trees.R).
# Coordonnées : EPSG:2154, x vers l'est, y vers le nord, en mètres ; les cellules d'un raster
# se comptent depuis le coin nord-ouest. Le massif fictif va de (700000 ; 6500000) au sud-ouest
# à (701000 ; 6501000) au nord-est (tests/fixtures/zone_fictive/README.md).

racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
zone_fictive <- file.path(racine, "tests", "fixtures", "zone_fictive")

# MNH synthétique : une cône parabolique par arbre, comme le jeu fictif. Le raster fait
# 40 m x 40 m à 0,5 m, coin sud-ouest (700000 ; 6500000), EPSG:2154.
# `arbres` : data.frame (x, y, h, r) en mètres absolus (x est, y nord).
mnh_synthetique <- function(arbres, taille = 40, res = 0.5) {
  r <- terra::rast(xmin = 700000, xmax = 700000 + taille, ymin = 6500000,
                   ymax = 6500000 + taille, resolution = res, crs = "EPSG:2154")
  xy <- terra::xyFromCell(r, seq_len(terra::ncell(r)))
  v <- numeric(terra::ncell(r))
  for (i in seq_len(nrow(arbres))) {
    d2 <- ((xy[, 1] - arbres$x[i])^2 + (xy[, 2] - arbres$y[i])^2) / arbres$r[i]^2
    v <- pmax(v, ifelse(d2 < 1, arbres$h[i] * (1 - d2), 0))
  }
  terra::setValues(r, v)
}

# ------------------------------------------------------------------ détection

test_that("un arbre isolé est détecté à sa place, x vers l'est et y vers le nord", {
  # sommet au centre d'une cellule : (700012,25 ; 6500027,75), 20 m de haut
  chm <- mnh_synthetique(data.frame(x = 700012.25, y = 6500027.75, h = 20, r = 4))
  d <- detect_trees(chm)
  expect_equal(nrow(d), 1L)
  expect_equal(d$x, 700012.25)
  expect_equal(d$y, 6500027.75)
  expect_equal(d$h, 20, tolerance = 1e-6)
  # x et y ne sont pas inversés : x est de l'ordre de 7e5, y de 6,5e6
  expect_lt(d$x, 1e6)
  expect_gt(d$y, 1e6)
  # le rang et la colonne retombent sur la même cellule du raster
  expect_equal(terra::cellFromRowCol(chm, d$row, d$col), terra::cellFromXY(chm, cbind(d$x, d$y)))
})

test_that("deux arbres éloignés donnent deux sommets, deux arbres collés un seul", {
  loin <- mnh_synthetique(data.frame(x = c(700010.25, 700030.25), y = c(6500020.25, 6500020.25),
                                     h = c(20, 22), r = 4))
  expect_equal(nrow(detect_trees(loin)), 2L)
  colles <- mnh_synthetique(data.frame(x = c(700020.25, 700021.25), y = c(6500020.25, 6500020.25),
                                       h = c(20, 19), r = 4))
  expect_equal(nrow(detect_trees(colles)), 1L)
})

test_that("un sol plat et un sous-bois sous la hauteur minimale ne donnent aucun arbre", {
  plat <- terra::rast(xmin = 700000, xmax = 700020, ymin = 6500000, ymax = 6500020,
                      resolution = 0.5, crs = "EPSG:2154", vals = 0)
  expect_equal(nrow(detect_trees(plat)), 0L)
  petit <- mnh_synthetique(data.frame(x = 700020.25, y = 6500020.25, h = TREES_HMIN_M - 1, r = 2))
  expect_equal(nrow(detect_trees(petit)), 0L)
})

test_that("un plateau parfaitement plat ne donne qu'un seul sommet", {
  chm <- mnh_synthetique(data.frame(x = 700020, y = 6500020, h = 15, r = 3))
  chm <- terra::ifel(chm > 0, 15, 0)
  expect_equal(nrow(detect_trees(chm)), 1L)
})

test_that("la fenêtre grandit avec la hauteur et reste dans ses bornes", {
  expect_equal(tree_window_m(c(0, 10, 100)),
               c(TREES_WINDOW_MIN_M, max(TREES_WINDOW_MIN_M, TREES_WINDOW_SLOPE * 10),
                 TREES_WINDOW_MAX_M))
  expect_true(all(window_cells(c(3, 4.5, 8), 0.5) %% 2L == 1L))
  expect_equal(window_cells(4.5, 0.5), 9L)
})

# ------------------------------------------------------------------ d130 : étage B

test_that("d130 = exp(a + b ln H) avec les coefficients donnés ; NA sans coefficients", {
  coef <- data.frame(species = c("09", "62"), a = c(0.10, 0.20), b = c(1.12, 1.08),
                     stringsAsFactors = FALSE)
  d <- d130_etage_b(c("09", "62", "99"), c(27, 36, 20), coef)
  expect_equal(d[1], exp(0.10 + 1.12 * log(27)))
  expect_equal(d[2], exp(0.20 + 1.08 * log(36)))
  expect_true(is.na(d[3]))
})

test_that("les coefficients etage_b sont lus dans allometry.parquet, essence en chaîne", {
  coef <- read_etage_b_coefficients(file.path(zone_fictive, "params", "allometry.parquet"))
  expect_true(is.character(coef$species))
  expect_true(all(c("09", "03") %in% coef$species))  # le zéro de tête est conservé
  expect_equal(coef$a[coef$species == "09"], 0.10)
  expect_equal(coef$b[coef$species == "09"], 1.12)
})

# ------------------------------------------------------------------ Parquet

test_that("l'écriture puis la lecture Parquet gardent le zéro de tête et les types", {
  f <- file.path(tempfile("pq"), "t.parquet")
  df <- data.frame(id = c("a", "b"), species = c("09", "62"), v = c(1.5, NA),
                   n = c(3L, 4L), stringsAsFactors = FALSE)
  write_parquet_tbl(df, f, list(id = "string", species = "string", v = "float64", n = "int32"))
  back <- read_parquet_tbl(f)
  expect_equal(back$species, c("09", "62"))
  expect_equal(back$v, c(1.5, NA))
  expect_equal(back$n, c(3L, 4L))
})

test_that("lire un Parquet absent arrête avec un message en français", {
  expect_error(read_parquet_tbl(file.path(tempdir(), "absent.parquet")), "absent")
})

# ------------------------------------------------------------------ essence du type de végétation

ecrire_biome <- function(dir, id, composition) {
  lignes <- c(sprintf("id: %s", id), "provisoire: true", "strates:", "  arboree:", "    composition:",
              sprintf("      \"%s\": %s", names(composition), composition))
  writeLines(lignes, file.path(dir, paste0(id, ".yml")))
}

test_that("l'essence d'un type de végétation est la plus grande part de la strate arborée", {
  dir <- tempfile("biomes"); dir.create(dir)
  ecrire_biome(dir, "type_a", c("09" = 0.7, "62" = 0.3))
  ecrire_biome(dir, "type_egalite", c("09" = 0.5, "62" = 0.5))
  d <- vegetation_dominant_species(c("type_a", "type_egalite", "type_inconnu"), dir,
                                   known_species = c("09", "62"))
  expect_equal(unname(d["type_a"]), "09")
  expect_true(is.na(d["type_egalite"]))
  expect_true(is.na(d["type_inconnu"]))
  expect_match(attr(d, "motifs")[["type_egalite"]], "galit")
  expect_match(attr(d, "motifs")[["type_inconnu"]], "aucun biome")
})

test_that("un code d'essence hors référentiel est refusé, pas deviné", {
  dir <- tempfile("biomes"); dir.create(dir)
  ecrire_biome(dir, "type_b", c("XX" = 1))
  d <- vegetation_dominant_species("type_b", dir, known_species = c("09"))
  expect_true(is.na(d["type_b"]))
  expect_match(attr(d, "motifs")[["type_b"]], "rentiel")
})

test_that("le référentiel des essences se lit par sa première colonne, en chaîne", {
  codes <- read_species_codes(file.path(racine, "contracts", "species.csv"))
  expect_true(all(c("09", "03", "62") %in% codes))
  expect_true(all(is.character(codes)))
})

# ------------------------------------------------------------------ le module, sur le jeu fictif

# Zone d'essai : copie du jeu fictif dont le MNH est rogné à une fenêtre qui touche les cinq
# polygones (x 300-700, y 400-600 en mètres locaux) ; une carte de végétation fictive
# (un seul type) et son biome sont ajoutés si `avec_vegetation`.
zone_essai <- function(avec_vegetation) {
  zone <- tempfile("zone"); dir.create(zone)
  file.copy(file.path(zone_fictive, "inputs"), zone, recursive = TRUE)
  file.copy(file.path(zone_fictive, "params"), zone, recursive = TRUE)
  file.copy(file.path(zone_fictive, "forest_mask.tif"), zone)
  chm <- terra::rast(file.path(zone_fictive, "inputs", "chm.tif"))
  fenetre <- terra::ext(700300, 700700, 6500400, 6500600)
  terra::writeRaster(terra::crop(chm, fenetre), file.path(zone, "inputs", "chm.tif"),
                     overwrite = TRUE, datatype = "FLT4S", NAflag = -9999)
  biomes <- file.path(zone, "biomes"); dir.create(biomes)
  if (avec_vegetation) {
    g <- terra::rast(file.path(zone_fictive, "grid.tif"))
    terra::writeRaster(terra::rast(g, vals = 1L), file.path(zone, "vegetation_map.tif"),
                       datatype = "INT2U", overwrite = TRUE)
    writeLines(c("value,name", "1,type_fictif"), file.path(zone, "vegetation_map.csv"))
    ecrire_biome(biomes, "type_fictif", c("03" = 0.6, "09" = 0.4))
  }
  list(zone = zone, biomes = biomes)
}

lancer_module <- function(avec_vegetation) {
  z <- zone_essai(avec_vegetation)
  suppressMessages(prepare_trees(z$zone, cfg = list(), validate = FALSE, biomes_dir = z$biomes,
                                 species_csv = file.path(racine, "contracts", "species.csv")))
  z$zone
}

zone_avec <- local({ z <- NULL; function() { if (is.null(z)) z <<- lancer_module(TRUE); z } })

lire_arbres <- function(zone) {
  read_parquet_tbl(file.path(zone, "trees_init", "trees.parquet"))
}

test_that("trees_init/ et stands.parquet passent le validateur des contrats", {
  z <- zone_avec()
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = file.path(racine, "contracts", "validate"))
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  expect_silent(validate_file("prepare.trees_init", file.path(z, "trees_init")))
  zs <- tempfile("zs"); dir.create(zs)
  file.copy(file.path(zone_fictive, "inputs"), zs, recursive = TRUE)
  suppressMessages(prepare_stands(zs, cfg = list(), validate = TRUE,
                                  species_csv = file.path(racine, "contracts", "species.csv")))
  expect_true(file.exists(file.path(zs, "stands.parquet")))
})

test_that("chaque arbre porte ses deux sources, et l'essence suit le polygone ou la végétation", {
  a <- lire_arbres(zone_avec())
  expect_gt(nrow(a), 100)
  expect_true(all(a$species_source %in% c("nemeton", "vegetation_type")))
  expect_true(all(a$d130_source == "tarif_etage_b"))
  expect_equal(anyDuplicated(a$tree_id), 0L)
  # hors polygone (x 350-650, y 0-500 locaux) : essence du type de végétation fictif (03)
  hors <- a$x >= 700350 & a$x < 700650 & a$y < 6500500
  expect_gt(sum(hors), 10)
  expect_true(all(a$species_source[hors] == "vegetation_type"))
  expect_true(all(a$species[hors] == "03"))
  # S03 (x 350-650, y 500-1000) : épicéa 62 de nemeton, plus haut que son plafond, non ramené
  s03 <- a$x >= 700350 & a$x < 700650 & a$y >= 6500500
  expect_gt(sum(s03), 10)
  expect_true(all(a$species[s03] == "62" & a$species_source[s03] == "nemeton"))
  expect_gt(median(a$h[s03]), 30)
})

test_that("le d130 écrit suit ln D = a + b ln H avec les coefficients du fichier", {
  a <- lire_arbres(zone_avec())
  coef <- read_etage_b_coefficients(file.path(zone_fictive, "params", "allometry.parquet"))
  attendu <- d130_etage_b(a$species, a$h, coef)
  expect_equal(a$d130, attendu, tolerance = 1e-9)
})

test_that("les arbres sont dans le massif, x est et y nord, sur un maximum du MNH", {
  z <- zone_avec()
  a <- lire_arbres(z)
  expect_true(all(a$x >= 700300 & a$x <= 700700))
  expect_true(all(a$y >= 6500400 & a$y <= 6500600))
  chm <- terra::rast(file.path(z, "inputs", "chm.tif"))
  ref <- terra::extract(terra::focal(chm, w = 3L, fun = "max", na.rm = TRUE), cbind(a$x, a$y))[, 1]
  expect_equal(a$h, ref, tolerance = 1e-4)
})

test_that("stands.parquet reprend les cinq polygones nemeton aux noms de sylvigenese", {
  z <- tempfile("zs"); dir.create(z)
  file.copy(file.path(zone_fictive, "inputs"), z, recursive = TRUE)
  suppressMessages(prepare_stands(z, cfg = list(), validate = FALSE,
                                  species_csv = file.path(racine, "contracts", "species.csv")))
  s <- read_parquet_tbl(file.path(z, "stands.parquet"))
  expect_equal(sort(s$stand_id), c("S01", "S02", "S03", "S04", "S05"))
  expect_equal(s$species[s$stand_id == "S01"], "09")
  expect_equal(s$d130[s$stand_id == "S03"], 48)
  expect_equal(s$h[s$stand_id == "S03"], 36)
  expect_equal(s$source[s$stand_id == "S04"], "synthetic_ml")
})

test_that("le rapport dit mono-essence, synthetic_ml sans recompter le MNH, et les arbres hors polygone", {
  html <- paste(readLines(file.path(zone_avec(), "rapport_arbres.html"), encoding = "UTF-8"),
                collapse = "\n")
  expect_match(html, "mono-essence")
  expect_match(html, "S04 : source synthetic_ml")
  expect_match(html, "seconde fois")
  expect_match(html, "hors polygone nemeton")
})

test_that("sans carte de végétation, trees s'arrête avec une erreur explicite, rien n'est écrit", {
  z <- zone_essai(FALSE)
  expect_error(prepare_trees(z$zone, cfg = list(), validate = FALSE, biomes_dir = z$biomes,
                             species_csv = file.path(racine, "contracts", "species.csv")),
               "make biomes")
  expect_false(dir.exists(file.path(z$zone, "trees_init")))
})

test_that("une essence sans coefficients etage_b n'est pas écrite et le rapport le dit", {
  z <- zone_essai(TRUE)
  # le polygone hors-massif reçoit une essence du référentiel sans coefficients : 04
  ecrire_biome(z$biomes, "type_fictif", c("04" = 1))
  suppressMessages(prepare_trees(z$zone, cfg = list(), validate = FALSE, biomes_dir = z$biomes,
                                 species_csv = file.path(racine, "contracts", "species.csv")))
  a <- lire_arbres(z$zone)
  expect_false(any(a$species == "04"))
  html <- paste(readLines(file.path(z$zone, "rapport_arbres.html"), encoding = "UTF-8"), collapse = "\n")
  expect_match(html, "sans coefficients etage_b")
})
