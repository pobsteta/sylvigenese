# Tests de prepare : grille de 25 m et rasters alignés (mission 017, R/prepare_grid.R).
# Coordonnées : EPSG:2154, x vers l'est, y vers le nord, en mètres ; les cellules d'un raster
# se comptent depuis le coin nord-ouest. Le massif fictif va de (700000 ; 6500000) au sud-ouest
# à (701000 ; 6501000) au nord-est (tests/fixtures/zone_fictive/README.md).

racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
X0 <- 700000
Y0 <- 6500000

# Rectangle sf (xmin, ymin, xmax, ymax) en EPSG:2154.
boite <- function(xmin, ymin, xmax, ymax) {
  sf::st_polygon(list(matrix(c(xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax, xmin, ymin),
                             ncol = 2, byrow = TRUE)))
}

couche_ser <- function(codes, boites) {
  sf::st_sf(ser_code = codes, geometry = sf::st_sfc(boites, crs = 2154))
}

# Valeur d'un raster au point (x, y) de l'EPSG:2154 : x d'abord (est), puis y (nord).
valeur_en <- function(chemin, x, y, couche = 1) {
  r <- terra::rast(chemin)
  terra::extract(r, matrix(c(x, y), ncol = 2))[1, couche]
}

# ------------------------------------------------------------------ la grille

test_that("la grille s'arrondit vers l'extérieur sur des multiples de la maille", {
  g <- grid_template(c(700010, 6500010, 700990, 6500990), 25)
  expect_equal(c(terra::xmin(g), terra::xmax(g), terra::ymin(g), terra::ymax(g)),
               c(700000, 701000, 6500000, 6501000))
  expect_equal(terra::res(g), c(25, 25))
  expect_equal(terra::ncol(g), 40L)
  expect_equal(terra::nrow(g), 40L)
})

test_that("une emprise déjà sur la maille ne s'agrandit pas", {
  g <- grid_template(c(700000, 6500000, 701000, 6501000), 25)
  expect_equal(c(terra::ncol(g), terra::nrow(g)), c(40L, 40L))
})

test_that("un point connu tombe dans la bonne cellule (x est, y nord, coin nord-ouest)", {
  g <- grid_template(c(700000, 6500000, 701000, 6501000), 25)
  # centre de la cellule nord-ouest : cellule 1 (ligne 1, colonne 1)
  expect_equal(terra::cellFromXY(g, cbind(700012.5, 6500987.5)), 1)
  # coin sud-est : dernière cellule
  expect_equal(terra::cellFromXY(g, cbind(700987.5, 6500012.5)), terra::ncell(g))
  # x et y inversés tombent hors de la grille : on ne les confond pas
  expect_true(is.na(terra::cellFromXY(g, cbind(6500012.5, 700987.5))))
})

# ------------------------------------------------------------------ alluvions : SER sous-jacente

test_that("l'alluvion reçoit la SER voisine de plus longue frontière", {
  # A (B10) à gauche de L2 sur 1000 m ; C (C20) au-dessus de L2 sur 500 m
  ser <- couche_ser(c("B10", "C20", "L2"),
                    list(boite(0, 0, 1000, 1000), boite(1000, 1000, 1500, 1300),
                         boite(1000, 0, 1500, 1000)))
  res <- resolve_alluvium_ser(ser)
  expect_equal(res$ser$ser_code, c("B10", "C20", "B10"))
  a <- res$attributions
  expect_equal(nrow(a), 1L)
  expect_equal(a$alluvium_code, "L2")
  expect_equal(a$ser_code, "B10")
  expect_equal(a$frontier_m, 1000, tolerance = 0.1)
  expect_equal(a$runner_up, "C20")
  expect_equal(a$runner_up_m, 500, tolerance = 0.1)
  expect_false(a$tie)
  # le code brut de l'IGN reste lisible
  expect_equal(res$ser$ser_code_igns[3], "L2")
})

test_that("c'est la frontière la plus longue qui gagne, pas la première voisine ni la plus grande", {
  ser <- couche_ser(c("B10", "C20", "L4"),
                    list(boite(0, 0, 1000, 200),          # B10 : 200 m de frontière avec L4
                         boite(1000, 0, 2000, 1000),      # C20 : 1000 m
                         boite(0, 200, 1000, 1000)))      # L4 touche B10 (haut) et C20 (droite)
  # L4 : sous B10 ? B10 est en bas (y 0-200), L4 au-dessus (y 200-1000) : frontière 1000 m ;
  # C20 à droite, x = 1000 sur y 200-1000 : 800 m. Les deux sont connues, B10 l'emporte.
  res <- resolve_alluvium_ser(ser)
  expect_equal(res$attributions$ser_code, "B10")
  expect_equal(res$attributions$frontier_m, 1000, tolerance = 0.1)
  expect_equal(res$attributions$runner_up, "C20")
  expect_equal(res$attributions$runner_up_m, 800, tolerance = 0.1)
})

test_that("les polygones d'une même SER s'additionnent avant la comparaison", {
  # B10 en deux polygones de 500 m chacun contre L1 ; C20 en un polygone de 700 m
  ser <- couche_ser(c("B10", "B10", "C20", "L1"),
                    list(boite(0, 0, 500, 500), boite(500, 0, 1000, 500),
                         boite(0, 1000, 700, 1500), boite(0, 500, 1000, 1000)))
  # L1 (y 500-1000) : B10 en dessous sur 1000 m ; C20 au-dessus sur 700 m
  res <- resolve_alluvium_ser(ser)
  expect_equal(res$attributions$ser_code, "B10")
  expect_equal(res$attributions$frontier_m, 1000, tolerance = 0.1)
})

test_that("une égalité de frontière est signalée et tranchée par l'ordre des codes", {
  ser <- couche_ser(c("C20", "B10", "L3"),
                    list(boite(0, 0, 500, 500), boite(500, 0, 1000, 500),
                         boite(0, 500, 1000, 1000)))
  res <- resolve_alluvium_ser(ser)
  expect_true(res$attributions$tie)
  expect_equal(res$attributions$ser_code, "B10")
  rap <- new_report()
  expect_message(report_alluvium_attributions(rap, res$attributions), "GALIT")
})

test_that("une alluvion sans voisine, ou voisine d'une autre alluvion seulement, reste sans SER", {
  ser <- couche_ser(c("B10", "L1", "L2", "L5"),
                    list(boite(0, 0, 1000, 1000),
                         boite(5000, 0, 5500, 500),          # isolée
                         boite(8000, 0, 8500, 500),          # voisine de L5 seulement
                         boite(8500, 0, 9000, 500)))
  res <- resolve_alluvium_ser(ser)
  expect_equal(res$ser$ser_code[1], "B10")
  expect_true(all(is.na(res$ser$ser_code[2:4])))
  expect_equal(nrow(res$attributions), 3L)
  expect_true(all(is.na(res$attributions$ser_code)))
  rap <- new_report()
  expect_message(report_alluvium_attributions(rap, res$attributions), "aucune SER voisine")
})

test_that("chaque attribution est une ligne de rapport, avec le code d'alluvions et la SER", {
  ser <- couche_ser(c("H10", "L3"), list(boite(0, 0, 1000, 1000), boite(1000, 0, 1500, 1000)))
  res <- resolve_alluvium_ser(ser)
  rap <- new_report()
  expect_message(report_alluvium_attributions(rap, res$attributions), "L3.*H10")
  expect_equal(length(rap$entries), 1L)
  expect_equal(rap$entries[[1]]$section, "Alluvions : SER sous-jacente")
})

test_that("sans alluvions, le rapport le dit au lieu de se taire", {
  ser <- couche_ser("H10", list(boite(0, 0, 1000, 1000)))
  res <- resolve_alluvium_ser(ser)
  expect_equal(nrow(res$attributions), 0L)
  rap <- new_report()
  expect_message(report_alluvium_attributions(rap, res$attributions), "aucun polygone d'alluvions")
})

# ------------------------------------------------------------------ H0 : agrégation du MNH

# MNH de 0,5 m couvrant `n` cellules de 25 m par côté (50 pixels par cellule), coin
# sud-ouest en (X0 ; Y0).
mnh_de_test <- function(valeurs, n = 2) {
  r <- terra::rast(xmin = X0, xmax = X0 + 25 * n, ymin = Y0, ymax = Y0 + 25 * n,
                   resolution = 0.5, crs = "EPSG:2154")
  terra::values(r) <- valeurs
  r
}

test_that("H0 est le percentile 95 du MNH de la cellule, pas le maximum ni la moyenne", {
  n <- 2
  v <- rep(10, (50 * n)^2)
  r <- mnh_de_test(v, n)
  # cellule nord-ouest : 100 pixels sur 2 500 (4 %) à 40 m : le percentile 95 reste à 10 m
  rows <- 1:50; cols <- 1:50
  idx <- terra::cellFromRowCol(r, rep(rows, each = 50)[1:100], rep(cols, times = 50)[1:100])
  v[idx] <- 40
  terra::values(r) <- v
  g <- grid_template(c(X0, Y0, X0 + 25 * n, Y0 + 25 * n), 25)
  h0 <- aggregate_h0(r, g)
  expect_equal(dim(h0)[1:2], c(2, 2))
  expect_equal(terra::values(h0, mat = FALSE)[1], 10)
  # 10 % de pixels à 40 m : le percentile 95 monte à 40 m
  v2 <- rep(10, (50 * n)^2)
  idx2 <- terra::cellFromRowCol(r, rep(rows, each = 50)[1:250], rep(cols, times = 50)[1:250])
  v2[idx2] <- 40
  terra::values(r) <- v2
  h0b <- aggregate_h0(r, g)
  expect_equal(terra::values(h0b, mat = FALSE)[1], 40)
})

test_that("H0 d'une cellule uniforme vaut la hauteur uniforme, et chaque cellule garde sa place", {
  n <- 2
  r <- mnh_de_test(0, n)
  # cellule sud-est (ligne 2, colonne 2 de la grille) à 17 m, le reste à 0
  sud_est <- terra::cellFromRowCol(r, rep(51:100, each = 50), rep(51:100, times = 50))
  v <- rep(0, (50 * n)^2); v[sud_est] <- 17
  terra::values(r) <- v
  g <- grid_template(c(X0, Y0, X0 + 50, Y0 + 50), 25)
  h0 <- aggregate_h0(r, g)
  # centre de la cellule sud-est : (X0 + 37,5 ; Y0 + 12,5)
  expect_equal(terra::extract(h0, cbind(X0 + 37.5, Y0 + 12.5))[1, 1], 17)
  expect_equal(terra::extract(h0, cbind(X0 + 12.5, Y0 + 37.5))[1, 1], 0)
})

test_that("une cellule sans MNH reste NA, elle n'est pas remplie", {
  n <- 2
  r <- mnh_de_test(5, n)
  # le MNH ne couvre que la moitié ouest ; la grille couvre les deux cellules en x
  g <- grid_template(c(X0, Y0, X0 + 25 * n + 25, Y0 + 25 * n), 25)
  h0 <- aggregate_h0(r, g)
  expect_equal(terra::ncol(h0), 3L)
  expect_true(is.na(terra::extract(h0, cbind(X0 + 62.5, Y0 + 12.5))[1, 1]))
  expect_equal(terra::extract(h0, cbind(X0 + 12.5, Y0 + 12.5))[1, 1], 5)
})

test_that("un MNH non aligné sur la grille est refusé, jamais rééchantillonné", {
  r <- terra::rast(xmin = X0 + 0.25, xmax = X0 + 50.25, ymin = Y0, ymax = Y0 + 50,
                   resolution = 0.5, crs = "EPSG:2154")
  terra::values(r) <- 1
  g <- grid_template(c(X0, Y0, X0 + 50, Y0 + 50), 25)
  expect_error(aggregate_h0(r, g), "pas align")
})

test_that("un MNH dont la maille ne divise pas la cellule est refusé", {
  r <- terra::rast(xmin = X0, xmax = X0 + 60, ymin = Y0, ymax = Y0 + 60,
                   resolution = 0.6, crs = "EPSG:2154")
  terra::values(r) <- 1
  g <- grid_template(c(X0, Y0, X0 + 50, Y0 + 50), 25)
  expect_error(aggregate_h0(r, g), "jamais r")
})

# ------------------------------------------------------------------ rapport

test_that("le rapport HTML est écrit en UTF-8, échappé et groupé par section", {
  rap <- new_report()
  suppressMessages({
    report_add(rap, "Alluvions", "L3 vers H10 <test> & accents \u00e9")
    report_add(rap, "Grille", "40 x 40")
  })
  f <- tempfile(fileext = ".html")
  write_prepare_report(rap, f)
  octets <- readBin(f, "raw", file.size(f))
  txt <- rawToChar(octets)
  expect_match(txt, "<h2>Alluvions</h2>", fixed = TRUE)
  expect_match(txt, "&lt;test&gt; &amp; accents ", fixed = TRUE)
  expect_match(txt, "charset=\"utf-8\"", fixed = TRUE)
  # le é est écrit en UTF-8 : octets c3 a9
  expect_true(any(octets[-length(octets)] == as.raw(0xc3) & octets[-1] == as.raw(0xa9)))
})

# ------------------------------------------------------------------ le jeu fictif, de bout en bout

# Valide avec le vrai validateur (chemin absolu : les tests changent de dossier courant).
avec_vrai_validateur <- function(code) {
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = file.path(racine, "contracts", "validate"))
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  force(code)
}

# Copie des seules entrées du jeu fictif dans un dossier temporaire : les sorties ne
# touchent pas au dépôt.
copie_zone <- function() {
  zone <- tempfile("zone_")
  dir.create(zone)
  file.copy(file.path(racine, "tests", "fixtures", "zone_fictive", "inputs"), zone,
            recursive = TRUE)
  zone
}

config_fictive <- function() read_config(file.path(racine, "config.yml"))

# prepare_grid est lancé une fois pour tout le fichier.
zone_preparee <- local({
  zone <- NULL
  function() {
    if (is.null(zone)) {
      z <- copie_zone()
      avec_vrai_validateur(suppressMessages(prepare_grid(z, config_fictive())))
      zone <<- z
    }
    zone
  }
})

test_that("prepare_grid écrit tous les fichiers de la mission, validés par le vrai validateur", {
  z <- zone_preparee()
  for (f in c("grid.tif", "dtm.tif", "forest_mask.tif", "ser.tif", "ser.csv", "h0.tif",
              "chm_date.tif", "station_gradients.tif", "station_type.tif", "station_type.csv",
              "site_potential.tif", "site_potential.csv", "rapport_prepare.html")) {
    expect_true(file.exists(file.path(z, f)), info = f)
  }
  # contrôle explicite, hors de prepare_grid : variante grille, alignement sur grid.tif
  avec_vrai_validateur({
    grid <- file.path(z, "grid.tif")
    for (par in list(c("prepare.dtm", "dtm.tif"), c("prepare.forest_mask", "forest_mask.tif"),
                     c("prepare.ser", "ser.tif"), c("prepare.h0", "h0.tif"),
                     c("prepare.chm_date", "chm_date.tif"),
                     c("prepare.station_gradients", "station_gradients.tif"),
                     c("prepare.station_type", "station_type.tif"),
                     c("prepare.site_potential", "site_potential.tif"))) {
      expect_equal(call_validator(c(par[1], "--grid", grid, file.path(z, par[2]))), 0L,
                   info = par[2])
    }
    expect_equal(call_validator(c("prepare.grid", grid)), 0L)
  })
})

test_that("la grille est de 25 m, EPSG:2154, et couvre le massif de (700000 ; 6500000) à (701000 ; 6501000)", {
  z <- zone_preparee()
  g <- terra::rast(file.path(z, "grid.tif"))
  expect_equal(terra::res(g), c(25, 25))
  expect_equal(c(terra::xmin(g), terra::xmax(g), terra::ymin(g), terra::ymax(g)),
               c(X0, X0 + 1000, Y0, Y0 + 1000))
  expect_equal(c(terra::ncol(g), terra::nrow(g)), c(40L, 40L))
  expect_equal(terra::crs(g, describe = TRUE)$code, "2154")
})

test_that("tous les rasters ont la géométrie exacte de grid.tif", {
  z <- zone_preparee()
  g <- terra::rast(file.path(z, "grid.tif"))
  for (f in c("dtm", "forest_mask", "ser", "h0", "chm_date", "station_gradients",
              "station_type", "site_potential")) {
    expect_true(terra::compareGeom(g, terra::rast(file.path(z, paste0(f, ".tif"))),
                                   stopOnError = FALSE), info = f)
  }
})

test_that("le profil des contrats est respecté : tuiles de 256, Deflate, nodata déclaré, types", {
  z <- zone_preparee()
  tif <- function(f) terra::describe(file.path(z, f))
  for (f in c("h0.tif", "dtm.tif", "station_gradients.tif", "site_potential.tif")) {
    expect_true(any(grepl("Type=Float32", tif(f))), info = f)
    expect_true(any(grepl("NoData Value=-9999", tif(f), fixed = TRUE)), info = f)
  }
  for (f in c("grid.tif", "forest_mask.tif", "ser.tif", "chm_date.tif", "station_type.tif")) {
    expect_true(any(grepl("Type=UInt16", tif(f))), info = f)
    expect_true(any(grepl("NoData Value=65535", tif(f), fixed = TRUE)), info = f)
  }
  expect_true(any(grepl("Block=256x256", tif("h0.tif"), fixed = TRUE)))
  expect_true(any(grepl("COMPRESSION=DEFLATE", tif("h0.tif"), fixed = TRUE)))
})

test_that("le masque forestier a sa trouée au bon endroit (400-600 ; 100-300 en m locaux)", {
  z <- zone_preparee()
  f <- file.path(z, "forest_mask.tif")
  expect_equal(valeur_en(f, X0 + 500, Y0 + 200), 0)      # au centre de la trouée
  expect_equal(valeur_en(f, X0 + 412.5, Y0 + 112.5), 0)  # cellule de coin de la trouée
  expect_equal(valeur_en(f, X0 + 387.5, Y0 + 112.5), 1)  # juste à l'ouest
  expect_equal(valeur_en(f, X0 + 500, Y0 + 312.5), 1)    # juste au nord
  expect_equal(valeur_en(f, X0 + 200, Y0 + 800), 1)      # peuplement S02
  m <- terra::values(terra::rast(f), mat = FALSE)
  expect_equal(sum(m == 0), 8 * 8)                       # 200 m x 200 m = 64 cellules
})

test_that("ser.tif : l'alluvion L3 reçoit H10 et garde son origine par alluvium_code, le rapport le dit", {
  z <- zone_preparee()
  cats <- utils::read.csv(file.path(z, "ser.csv"), stringsAsFactors = FALSE, na.strings = "")
  expect_equal(names(cats), c("value", "name", "alluvium_code"))
  # name = SER sous-jacente, jamais L1 à L5 ; l'alluvion est dans alluvium_code
  expect_false(any(cats$name %in% c("L1", "L2", "L3", "L4", "L5")))
  expect_equal(cats$name, c("H10", "H10"))
  expect_equal(cats$alluvium_code, c(NA, "L3"))
  # le couloir L3 (y 420-520 en m locaux) porte la valeur du couple (H10, L3), le reste (H10, vide)
  v_alluvion <- cats$value[!is.na(cats$alluvium_code)]
  v_hors <- cats$value[is.na(cats$alluvium_code)]
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 470), v_alluvion)
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 100), v_hors)
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 900), v_hors)
  s <- terra::values(terra::rast(file.path(z, "ser.tif")), mat = FALSE)
  expect_false(anyNA(s))
  # 4 rangées de 25 m dans le couloir de 100 m, sur toute la largeur : 4 x 40 cellules
  expect_equal(sum(s == v_alluvion), 4 * 40)
  rapport <- paste(readLines(file.path(z, "rapport_prepare.html"), encoding = "UTF-8", warn = FALSE),
                   collapse = "\n")
  expect_match(rapport, "alluvions L3 .*SER H10")
})

test_that("ser_value_table : une valeur par couple (SER, alluvions), name jamais L1 à L5", {
  ser <- couche_ser(c("B10", "C20", "L2", "L4", "L1"),
                    list(boite(0, 0, 1000, 1000), boite(5000, 0, 5500, 500),
                         boite(1000, 0, 1500, 1000), boite(0, 1000, 1000, 1500),
                         boite(9000, 0, 9500, 500)))   # L1 isolée : sans SER
  res <- resolve_alluvium_ser(ser)
  t <- ser_value_table(res$ser)
  expect_equal(t$table$name, c("B10", "B10", "B10", "C20"))
  expect_equal(t$table$alluvium_code, c(NA, "L2", "L4", NA))
  expect_equal(t$table$value, 1:4)
  expect_equal(t$value, c(1L, 4L, 2L, 3L, NA))
  expect_false(any(t$table$name %in% ALLUVIUM_CODES))
})

test_that("ser.csv sur la variante alluvions : H20 avec et sans L3, un code par couple, contrat respecté", {
  z <- copie_zone()
  loc <- function(x0, x1, y0, y1) boite(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
  ser <- couche_ser(c("H10", "H30", "H20", "H40", "L3"),
                    list(loc(0, 400, 0, 420), loc(400, 1000, 0, 420), loc(0, 1000, 520, 600),
                         loc(0, 1000, 600, 1000), loc(0, 1000, 420, 520)))
  sf::st_write(ser, file.path(z, "inputs", "ser.gpkg"), layer = "ser", delete_dsn = TRUE, quiet = TRUE)
  avec_vrai_validateur(suppressMessages(prepare_grid(z, config_fictive())))
  cats <- utils::read.csv(file.path(z, "ser.csv"), stringsAsFactors = FALSE, na.strings = "")
  expect_equal(cats$name, c("H10", "H20", "H20", "H30", "H40"))
  expect_equal(cats$alluvium_code, c(NA, NA, "L3", NA, NA))
  f <- file.path(z, "ser.tif")
  v <- function(cx, cy) cats[cats$value == valeur_en(f, X0 + cx, Y0 + cy), c("name", "alluvium_code")]
  expect_equal(v(500, 470)$name, "H20")             # couloir : voisine de plus longue frontière
  expect_equal(v(500, 470)$alluvium_code, "L3")     # ... et son origine d'alluvions
  expect_true(is.na(v(500, 560)$alluvium_code))     # H20 propre, sans alluvions
  expect_equal(v(500, 560)$name, "H20")
  expect_equal(v(200, 200)$name, "H10")
  expect_equal(v(700, 200)$name, "H30")
  expect_equal(v(500, 800)$name, "H40")
  # le couloir et H20 propre sont deux valeurs différentes de la même SER
  expect_false(valeur_en(f, X0 + 500, Y0 + 470) == valeur_en(f, X0 + 500, Y0 + 560))
  avec_vrai_validateur({
    expect_equal(call_validator(c("prepare.ser_categories", file.path(z, "ser.csv"))), 0L)
    expect_equal(call_validator(c("prepare.ser", "--grid", file.path(z, "grid.tif"), f)), 0L)
  })
})

# ------------------------------------------------------------------ stand_map : polygone nemeton par cellule

test_that("stand_map.tif : chaque cellule porte son polygone nemeton, hors polygone au nodata", {
  z <- zone_preparee()
  f <- file.path(z, "stand_map.tif")
  cats <- utils::read.csv(file.path(z, "stand_map.csv"), stringsAsFactors = FALSE)
  expect_equal(names(cats), c("value", "name"))
  expect_equal(cats$name, c("S01", "S02", "S03", "S04", "S05"))   # name = stand_id, ordre des stand_id
  nom <- function(cx, cy) cats$name[cats$value == valeur_en(f, X0 + cx, Y0 + cy)]
  # un point du terrain tombe au bon endroit (x est, y nord) : S01 (0-350 ; 0-500), S02 (0-350 ; 500-1000)
  expect_equal(nom(175, 250), "S01")
  expect_equal(nom(175, 750), "S02")
  expect_equal(nom(500, 750), "S03")
  expect_equal(nom(825, 250), "S04")
  expect_equal(nom(825, 750), "S05")
  # forêt sans polygone nemeton (350-650 ; 0-500) : nodata ; x et y ne sont pas intervertis
  expect_true(is.na(valeur_en(f, X0 + 500, Y0 + 100)))
  expect_true(is.na(valeur_en(f, X0 + 500, Y0 + 400)))
  v <- terra::values(terra::rast(f), mat = FALSE)
  expect_equal(sum(is.na(v)), 240)          # 12 x 20 cellules hors de tout polygone
  expect_true(all(v[!is.na(v)] %in% cats$value))
  g <- file.path(z, "grid.tif")
  avec_vrai_validateur({
    expect_equal(call_validator(c("prepare.stand_map", "--grid", g, f)), 0L)
    expect_equal(call_validator(c("prepare.stand_map_categories", file.path(z, "stand_map.csv"))), 0L)
  })
  expect_true(terra::compareGeom(terra::rast(g), terra::rast(f), stopOnError = FALSE))
  expect_true(any(grepl("Type=UInt16", terra::describe(f))))
})

test_that("stand_map_values : valeur par rang du stand_id, doublon ou manque refusé", {
  r <- stand_map_values(c("S05", "S01", "S03"))
  expect_equal(r$names, c("S01", "S03", "S05"))
  expect_equal(r$value, c(3L, 1L, 2L))
  expect_error(stand_map_values(c("S01", "S01")), "en double")
  expect_error(stand_map_values(c("S01", NA)), "manquant")
  # UInt16 : 65 534 polygones au plus (65535 est le nodata), erreur explicite au-delà
  ok <- stand_map_values(sprintf("S%05d", seq_len(65534L)))
  expect_equal(max(ok$value), 65534L)
  expect_error(stand_map_values(sprintf("S%05d", seq_len(65535L))), "65534 que stand_map.tif")
})

test_that("stand_map : plus de 65 534 polygones, prepare rend 2 avant toute écriture, aucune sortie", {
  # Racine temporaire : le dépôt n'est pas touché. 65 535 polygones nemeton (copies du premier,
  # stand_id distincts) : la garde de stand_map_values doit agir avant grid.tif.
  racine_t <- tempfile("racine_65535_")
  zone_t <- file.path(racine_t, "tests", "fixtures", "zone_fictive")
  dir.create(zone_t, recursive = TRUE)
  src <- file.path(racine, "tests", "fixtures", "zone_fictive")
  file.copy(file.path(src, c("inputs", "params")), zone_t, recursive = TRUE)
  dir.create(file.path(racine_t, "contracts"))
  file.copy(file.path(racine, "contracts", "species.csv"), file.path(racine_t, "contracts"))
  gpkg <- file.path(zone_t, "inputs", "nemeton_stands.gpkg")
  st <- sf::st_read(gpkg, layer = "stands", quiet = TRUE)
  st$age_yr <- as.integer(st$age_yr)
  gros <- st[rep(1L, 65535L), ]
  gros$stand_id <- sprintf("S%05d", seq_len(65535L))
  sf::st_write(gros, gpkg, layer = "stands", delete_dsn = TRUE, quiet = TRUE)
  ancien_wd <- setwd(racine)
  ancienne_racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = NA)
  on.exit({
    setwd(ancien_wd)
    if (is.na(ancienne_racine)) Sys.unsetenv("SYLVIGENESE_ROOT") else Sys.setenv(SYLVIGENESE_ROOT = ancienne_racine)
  }, add = TRUE)
  Sys.setenv(SYLVIGENESE_ROOT = racine_t)
  msgs <- character()
  status <- avec_vrai_validateur(withCallingHandlers(
    run_prepare(file.path(racine, "config.yml")),
    message = function(m) { msgs <<- c(msgs, conditionMessage(m)); invokeRestart("muffleMessage") }))
  expect_equal(status, 2L)
  expect_match(paste(msgs, collapse = "\n"), "65534 que stand_map.tif")
  # aucune sortie : seuls inputs/ et params/ (copiés) restent dans la zone
  expect_equal(sort(list.files(zone_t, all.files = TRUE, no.. = TRUE)), c("inputs", "params"))
})

test_that("stand_map : deux polygones qui se recouvrent, règle déterministe et rapport chiffré", {
  z <- copie_zone()
  st <- sf::st_read(file.path(z, "inputs", "nemeton_stands.gpkg"), layer = "stands", quiet = TRUE)
  st$age_yr <- as.integer(st$age_yr)   # sf réécrit un entier en REAL sans cela : le contrat veut INTEGER
  i2 <- which(st$stand_id == "S02")
  # S02 étendu vers le sud jusqu'à y = 400 : il recouvre S01 (0-350 ; 0-500) sur 350 m x 100 m
  sf::st_geometry(st)[i2] <- sf::st_sfc(boite(X0, Y0 + 400, X0 + 350, Y0 + 1000), crs = 2154)
  sf::st_write(st, file.path(z, "inputs", "nemeton_stands.gpkg"), layer = "stands", delete_dsn = TRUE,
               quiet = TRUE)
  avec_vrai_validateur(suppressMessages(prepare_grid(z, config_fictive())))
  cats <- utils::read.csv(file.path(z, "stand_map.csv"), stringsAsFactors = FALSE)
  f <- file.path(z, "stand_map.tif")
  # dans le recouvrement (x 100, y 450) : le plus petit stand_id, S01, quel que soit l'ordre du fichier
  expect_equal(cats$name[cats$value == valeur_en(f, X0 + 100, Y0 + 450)], "S01")
  expect_equal(cats$name[cats$value == valeur_en(f, X0 + 100, Y0 + 550)], "S02")
  rapport <- paste(readLines(file.path(z, "rapport_prepare.html"), encoding = "UTF-8", warn = FALSE),
                   collapse = "\n")
  expect_match(rapport, "nemeton_stands.gpkg : 56 cellule\\(s\\) re.oivent plusieurs polygones")
  expect_match(rapport, "nemeton_stands.gpkg : S01 et S02 se recouvrent sur 35000,0 m. \\(56 cellule")
  expect_match(rapport, "valeurs diff.rentes, la plus petite l'emporte")
})

test_that("rasterize_polygons : en cas de recouvrement la plus petite valeur l'emporte, quel que soit l'ordre", {
  g <- grid_template(c(X0, Y0, X0 + 100, Y0 + 100), 25)
  p <- sf::st_sf(geometry = sf::st_sfc(boite(X0, Y0, X0 + 75, Y0 + 100),
                                       boite(X0 + 50, Y0, X0 + 100, Y0 + 100), crs = 2154))
  a <- terra::values(rasterize_polygons(p, c(7, 3), g), mat = FALSE)
  b <- terra::values(rasterize_polygons(p[2:1, ], c(3, 7), g), mat = FALSE)
  expect_equal(a, b)
  # colonne 3 (x 50-75) : les deux polygones ; colonnes 1-2 : le premier ; colonne 4 : le second
  expect_equal(a[1:4], c(7, 7, 3, 3))
  expect_false(any(is.nan(a)))
})

test_that("polygon_overlaps : paires, surface et cellules ; aucun recouvrement entre voisins qui se touchent", {
  g <- grid_template(c(X0, Y0, X0 + 200, Y0 + 100), 25)
  p <- sf::st_sf(geometry = sf::st_sfc(boite(X0, Y0, X0 + 100, Y0 + 100),
                                       boite(X0 + 75, Y0, X0 + 200, Y0 + 100), crs = 2154))
  ov <- polygon_overlaps(p, c("A", "B"), c(1, 2), g)
  expect_equal(nrow(ov$pairs), 1L)
  expect_equal(ov$pairs$area_m2, 25 * 100)
  expect_equal(ov$pairs$cells, 4L)         # colonne x 75-100, 4 lignes
  expect_equal(ov$cells, 4L)
  expect_false(ov$pairs$same_value)
  # deux polygones qui se touchent par une arête ne se recouvrent pas
  q <- sf::st_sf(geometry = sf::st_sfc(boite(X0, Y0, X0 + 100, Y0 + 100),
                                       boite(X0 + 100, Y0, X0 + 200, Y0 + 100), crs = 2154))
  expect_equal(nrow(polygon_overlaps(q, c("A", "B"), c(1, 2), g)$pairs), 0L)
  rap <- new_report()
  expect_message(report_polygon_overlaps(rap, q, c("A", "B"), c(1, 2), g, "essai"), "aucun recouvrement")
})

# ------------------------------------------------------------------ types.csv validé avant usage

test_that("types.csv non conforme au contrat inputs.station_types : prepare s'arrête avant toute sortie", {
  z <- copie_zone()
  f <- file.path(z, "inputs", "types.csv")
  txt <- readLines(f, encoding = "UTF-8")
  txt[1] <- sub("type;", "nom_du_type;", txt[1], fixed = TRUE)
  writeLines(txt, f)
  avec_vrai_validateur(
    expect_error(suppressMessages(prepare_grid(z, config_fictive())), "inputs.station_types")
  )
  expect_equal(setdiff(list.files(z), "inputs"), character(0))
})

test_that("types.csv conforme : il est validé comme les autres entrées, puis lu", {
  journal <- tempfile(fileext = ".log")
  faux <- tempfile(fileext = ".py")
  writeLines(c("import sys",
               sprintf("open(%s, 'a').write(sys.argv[1] + chr(10))", deparse(journal))), faux)
  z <- copie_zone()
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = faux)
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  suppressMessages(prepare_grid(z, config_fictive()))
  sortie <- readLines(journal)
  expect_true("inputs.station_types" %in% sortie)
  # validé avant la première sortie : avant prepare.grid
  expect_lt(match("inputs.station_types", sortie), match("prepare.grid", sortie))
})

# ------------------------------------------------------------------ nombres à la française

test_that("fr_num : virgule décimale, sans bruit de virgule flottante", {
  expect_equal(fr_num(0.6), "0,6")
  expect_equal(fr_num(c(0.25, 0.6, 0.9)), c("0,25", "0,6", "0,9"))
  expect_equal(fr_num(26.6000000000012), "26,6")
  expect_equal(fr_num(25), "25")
  expect_equal(fr_num(700000, 1), "700000,0")
  expect_false(any(grepl(".", fr_num(c(0.5, 4.5)), fixed = TRUE)))
})

test_that("h0.tif : percentile 95 du MNH à 50 cm, recalculé ici sur une cellule de chaque peuplement", {
  z <- zone_preparee()
  chm <- terra::rast(file.path(z, "inputs", "chm.tif"))
  # centres de cellules : S01 (essence 09), S03 (au-dessus de h_pot), S04, hors polygone nemeton
  for (xy in list(c(175, 250), c(500, 750), c(825, 250), c(500, 400), c(500, 800))) {
    cx <- X0 + 25 * floor(xy[1] / 25) + 12.5
    cy <- Y0 + 25 * floor(xy[2] / 25) + 12.5
    bloc <- terra::crop(chm, terra::ext(cx - 12.5, cx + 12.5, cy - 12.5, cy + 12.5))
    attendu <- unname(stats::quantile(terra::values(bloc, mat = FALSE), 0.95, type = 7))
    expect_equal(terra::ncell(bloc), 2500L)
    expect_equal(valeur_en(file.path(z, "h0.tif"), cx, cy), attendu, tolerance = 1e-4,
                 info = sprintf("cellule (%g ; %g)", cx, cy))
  }
  # la trouée n'a pas de MNH : H0 = 0 (la cellule est dans le raster, pas sans valeur)
  expect_equal(valeur_en(file.path(z, "h0.tif"), X0 + 500, Y0 + 200), 0)
  # S03 dépasse h_pot (36 m contre un plafond d'environ 31 m) : H0 le reflète, sans correction
  expect_gt(valeur_en(file.path(z, "h0.tif"), X0 + 500, Y0 + 750), 28)
})

test_that("chm_date.tif : jours depuis le 1970-01-01, vol de 2021 à l'ouest, de 2022 à l'est", {
  z <- zone_preparee()
  f <- file.path(z, "chm_date.tif")
  expect_equal(valeur_en(f, X0 + 100, Y0 + 500), as.integer(as.Date("2021-08-03")))
  expect_equal(valeur_en(f, X0 + 900, Y0 + 500), as.integer(as.Date("2022-06-21")))
  expect_equal(as.integer(as.Date("2021-08-03")), 18842L)
})

test_that("station_gradients.tif : trois bandes dans l'ordre trophic, hydric, bioclim", {
  z <- zone_preparee()
  sg <- terra::rast(file.path(z, "station_gradients.tif"))
  expect_equal(names(sg), c("trophic", "hydric", "bioclim"))
  src <- terra::rast(file.path(z, "inputs", "station_gradients.tif"))
  # l'interpolation reste dans l'étendue des valeurs sources, bande par bande
  for (b in 1:3) {
    v <- terra::values(sg[[b]], mat = FALSE)
    s <- terra::values(src[[b]], mat = FALSE)
    expect_false(anyNA(v))
    expect_gte(min(v), min(s) - 1e-4)
    expect_lte(max(v), max(s) + 1e-4)
  }
})

test_that("station_type.tif : valeurs de la légende, noms de types.csv, mode et non moyenne", {
  z <- zone_preparee()
  cats <- utils::read.csv(file.path(z, "station_type.csv"), stringsAsFactors = FALSE)
  legende <- utils::read.csv2(file.path(z, "inputs", "types.csv"), stringsAsFactors = FALSE)
  expect_equal(cats$value, legende$id)
  expect_equal(cats$name, legende$type)
  v <- terra::values(terra::rast(file.path(z, "station_type.tif")), mat = FALSE)
  expect_true(all(v %in% legende$id))
  # cellule de 25 m dont le centre est dans un pixel de 20 m : la valeur est celle d'un
  # code source (une moyenne donnerait des codes décimaux arrondis hors de la légende)
  src <- terra::rast(file.path(z, "inputs", "station_type.tif"))
  expect_true(all(unique(v) %in% unique(terra::values(src, mat = FALSE))))
})

test_that("site_potential.tif : une bande par famille, table valeur/nom, plafond dans l'étendue de h_pot", {
  z <- zone_preparee()
  sp <- terra::rast(file.path(z, "site_potential.tif"))
  cats <- utils::read.csv(file.path(z, "site_potential.csv"), stringsAsFactors = FALSE)
  expect_equal(cats$value, seq_len(terra::nlyr(sp)))
  expect_equal(cats$name, names(sp))
  src <- terra::values(terra::rast(file.path(z, "inputs", "h_pot.tif")), mat = FALSE)
  v <- terra::values(sp, mat = FALSE)
  expect_false(anyNA(v))
  expect_gte(min(v), min(src) - 1e-4)
  expect_lte(max(v), max(src) + 1e-4)
})

test_that("dtm.tif : le MNT de 25 m déjà sur la grille est repris tel quel", {
  z <- zone_preparee()
  a <- terra::values(terra::rast(file.path(z, "dtm.tif")), mat = FALSE)
  b <- terra::values(terra::rast(file.path(z, "inputs", "dtm.tif")), mat = FALSE)
  expect_equal(a, b, tolerance = 1e-4)
})

# ------------------------------------------------------------------ refus

test_that("une entrée absente arrête prepare avec un message, rien n'est inventé", {
  z <- copie_zone()
  file.remove(file.path(z, "inputs", "h_pot.tif"))
  avec_vrai_validateur(
    expect_error(suppressMessages(prepare_grid(z, config_fictive())), "h_pot.tif")
  )
})

test_that("une entrée refusée par le validateur arrête prepare", {
  z <- copie_zone()
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  faux <- tempfile(fileext = ".py")
  writeLines(c("import sys", "sys.exit(3)"), faux)
  Sys.setenv(SYLVIGENESE_VALIDATE = faux)
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  expect_error(suppressMessages(prepare_grid(z, config_fictive())), "par le validateur")
})

test_that("des bandes de gradients mal nommées sont refusées, pas devinées par l'ordre", {
  z <- copie_zone()
  f <- file.path(z, "inputs", "station_gradients.tif")
  r <- terra::rast(f)
  names(r) <- c("a", "b", "c")
  nouveau <- tempfile(fileext = ".tif")
  terra::writeRaster(r, nouveau, NAflag = -9999)
  file.copy(nouveau, f, overwrite = TRUE)
  expect_error(suppressMessages(prepare_grid(z, config_fictive(), validate = FALSE)),
               "bandes trophic, hydric, bioclim attendues")
})

test_that("une grille sur une autre zone que le jeu fictif se lit sous data/<zone>", {
  expect_equal(prepare_zone_dir(list(zone = "zone_fictive")),
               file.path(Sys.getenv("SYLVIGENESE_ROOT", "."), "tests", "fixtures", "zone_fictive"))
  expect_equal(prepare_zone_dir(list(zone = "massif_test")),
               file.path(Sys.getenv("SYLVIGENESE_ROOT", "."), "data", "massif_test"))
  expect_error(prepare_zone_dir(list()), "zone")
})

test_that("une entrée refusée, même non lue par la grille (nemeton_stands), n'écrit aucune sortie", {
  z <- copie_zone()
  # faux validateur : refuse seulement le contrat inputs.nemeton_stands
  faux <- tempfile(fileext = ".py")
  writeLines(c("import sys", "sys.exit(3 if 'inputs.nemeton_stands' in sys.argv else 0)"), faux)
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = faux)
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  expect_error(suppressMessages(prepare_grid(z, config_fictive())), "inputs.nemeton_stands")
  expect_equal(setdiff(list.files(z), "inputs"), character(0))
})

test_that("sous LC_ALL=C, un é du rapport sort en octets C3 A9, pas en texte <c3><a9>", {
  sortie <- tempfile(fileext = ".html")
  script <- tempfile(fileext = ".R")
  writeLines(c(
    sprintf("source(%s)", deparse(file.path(racine, "R", "commun.R"))),
    "e <- rawToChar(as.raw(c(0xc3, 0xa9)))  # un é en UTF-8, chaîne non marquée comme en locale C",
    "rap <- new_report()",
    "suppressMessages(report_add(rap, 'Grille', paste0('cellule ', e)))",
    sprintf("write_html_report(rap, %s, 'Rapport', 'Rapport')", deparse(sortie))), script)
  status <- system2(file.path(R.home("bin"), "Rscript"), script, env = "LC_ALL=C",
                    stdout = FALSE, stderr = FALSE)
  expect_equal(status, 0L)
  octets <- readBin(sortie, "raw", file.size(sortie))
  expect_true(any(octets[-length(octets)] == as.raw(0xc3) & octets[-1] == as.raw(0xa9)))
  expect_false(grepl("<c3>", rawToChar(octets), fixed = TRUE))
})
