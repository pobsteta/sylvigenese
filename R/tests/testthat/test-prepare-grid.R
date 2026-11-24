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

test_that("ser.tif : l'alluvion L3 reçoit H10, aucune SER L1 à L5 n'est écrite, le rapport le dit", {
  z <- zone_preparee()
  cats <- utils::read.csv(file.path(z, "ser.csv"), stringsAsFactors = FALSE)
  expect_equal(names(cats), c("value", "name"))
  expect_false(any(cats$name %in% c("L1", "L2", "L3", "L4", "L5")))
  expect_equal(cats$name, "H10")
  # le couloir L3 (y 420-520 en m locaux) porte la valeur de H10
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 470), cats$value[cats$name == "H10"])
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 100), cats$value[cats$name == "H10"])
  expect_equal(valeur_en(file.path(z, "ser.tif"), X0 + 500, Y0 + 900), cats$value[cats$name == "H10"])
  s <- terra::values(terra::rast(file.path(z, "ser.tif")), mat = FALSE)
  expect_false(anyNA(s))
  rapport <- paste(readLines(file.path(z, "rapport_prepare.html"), encoding = "UTF-8", warn = FALSE),
                   collapse = "\n")
  expect_match(rapport, "alluvions L3 .*SER H10")
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
