# Les motifs de recherche évitent les lettres accentuées (un « . » ne vaut qu'un octet) : la suite peut tourner en locale C.
# Tests de R/ifn_station.R (mission 024, spec §6) : trophic recalculé à la main, coarse_*_700m
# recalculées indépendamment sur une grille simple, ser_code majoritaire et ex aequo, garde IFN.
# Coordonnées : EPSG:2154, (x, y) = (est, nord), en m.

racine_st <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
zone_st <- file.path(racine_st, "tests", "fixtures", "zone_fictive")
avec_racine_st <- function(code) {
  old <- setwd(racine_st); on.exit(setwd(old)); force(code)
}

# Grille simple : 10 x 10 mailles de 100 m, coin nord-ouest (700 000 ; 6 501 000) ; valeur = numéro
# de colonne (1 à 10, d'ouest en est).
grille_simple <- function(valeurs = NULL) {
  r <- terra::rast(nrows = 10, ncols = 10, xmin = 700000, xmax = 701000, ymin = 6500000,
                   ymax = 6501000, crs = "EPSG:2154")
  terra::values(r) <- if (is.null(valeurs)) rep(1:10, times = 10) else valeurs
  r
}
pts_ifn <- function(x, y) mark_ifn(data.frame(x = x, y = y), 700)

test_that("disque : mailles dont le centre est à R ou moins, recalculées par force brute", {
  r <- grille_simple()
  p <- pts_ifn(700500, 6500500)          # centre de la grille, sur un coin de maille
  d <- ifn_disc_values(p, r, "coarse_essai", radius_m = 250)[[1]]
  # force brute : tous les centres de la grille, distance euclidienne
  xy <- terra::xyFromCell(r, seq_len(terra::ncell(r)))
  dans <- (xy[, 1] - 700500)^2 + (xy[, 2] - 6500500)^2 <= 250^2
  expect_equal(sort(d$values), sort(terra::values(r)[dans]))
  # à la main : centres à (+-50, +-50), (+-150, +-50), (+-50, +-150) : 4 + 4 + 4 = 12 mailles,
  # (+-150, +-150) à 212 m comprises : 16 ; colonnes 4 à 7, moyenne 5,5
  expect_equal(length(d$values), 16)
  expect_equal(mean(d$values), 5.5)
  expect_equal(d$n_out, 0)
  expect_equal(d$n_na, 0)
})

test_that("disque tronqué au coin : mailles hors emprise comptées, moyenne sur les seules présentes", {
  r <- grille_simple()
  p <- pts_ifn(700000, 6501000)          # coin nord-ouest
  d <- ifn_disc_values(p, r, "coarse_essai", radius_m = 250)[[1]]
  # quart de disque dans la grille : centres (50 ou 150 m, 50 ou 150 m) -> 4 mailles, colonnes 1 et 2
  expect_equal(length(d$values), 4)
  expect_equal(mean(d$values), 1.5)
  expect_equal(d$n_out, 12)              # les trois autres quarts
  # maille sans valeur : comptée, pas dans la moyenne
  v <- rep(1:10, times = 10); v[1] <- NA
  d2 <- ifn_disc_values(p, grille_simple(v), "coarse_essai", radius_m = 250)[[1]]
  expect_equal(d2$n_na, 1)
  expect_equal(mean(d2$values), mean(c(2, 1, 2)))
  # disque entièrement hors de la grille : aucune valeur
  d3 <- ifn_disc_values(pts_ifn(690000, 6490000), r, "coarse_essai", radius_m = 250)[[1]]
  expect_length(d3$values, 0)
  expect_equal(d3$n_out, 16)
})

test_that("garde IFN : une extraction de station_gradients à la placette est refusée", {
  sg <- terra::rast(file.path(zone_st, "inputs", "station_gradients.tif"))
  p <- pts_ifn(700500, 6500500)
  expect_error(ifn_disc_values(p, sg[["hydric"]], "station_gradients"), "Extraction interdite")
  expect_error(ifn_disc_values(p, sg[["hydric"]], "hydric"), "Extraction interdite")
  expect_error(ifn_disc_values(p, sg[["hydric"]], "pente"), "Extraction interdite")
  # même sans marquage IFN : précision absente -> refusé
  expect_error(ifn_disc_values(data.frame(x = 700500, y = 6500500), sg[["hydric"]], "station_gradients"),
               "Extraction interdite")
  expect_silent(ifn_disc_values(p, sg[["hydric"]], "coarse_hydric_700m"))
})

test_that("trophic recalculé à la main sur deux placettes (méthode de sylvostation)", {
  plots <- data.frame(plot_id = c("A", "B", "A", "C"), campaign = c(2015L, 2016L, 2020L, 2017L),
                      visit = c(1L, 1L, 2L, 1L))
  flora <- data.frame(plot_id = c("A", "A", "A", "B", "B", "B"), campaign = c(2015L, 2015L, 2015L, 2016L, 2016L, 2016L),
                      cd_ref = c(1L, 2L, 9L, 2L, 3L, 4L))
  ind <- data.frame(cd_ref = 1:4, reaction = c(2, 6, NA, 8), nutrients = c(4, 5, 7, NA))
  tr <- ifn_trophic(plots, flora, ind)
  # A : réaction (2 + 6) / 2 = 4 ; nutriments (4 + 5) / 2 = 4,5 ; taxon 9 sans valeur -> 4,25
  # B : réaction (6 + 8) / 2 = 7 ; nutriments (5 + 7) / 2 = 6 -> 6,5
  expect_equal(tr$trophic, c(4.25, 6.5, 4.25, NA))
  expect_equal(tr$n_taxa, c(2L, 3L, 2L, 0L))
  expect_equal(tr$unmatched$cd_ref, 9L)
  expect_equal(tr$copied, 1L)
  # réaction seule : trophic = moyenne de réaction
  tr1 <- ifn_trophic(plots[1, ], flora[1:2, ], data.frame(cd_ref = 1:2, reaction = c(2, 6), nutrients = NA_real_))
  expect_equal(tr1$trophic, 4)
  # exclusion des essences : le taxon 2 retiré, A = (2 + 4) / 2 = 3
  tr2 <- ifn_trophic(plots, flora, ind, exclude_cd_ref = 2L)
  expect_equal(tr2$trophic[1], 3)
  expect_equal(tr2$excluded_rows, 2L)
})

test_that("ser_code : SER majoritaire du disque ; ex aequo laissé vide et signalé", {
  ser_tab <- data.frame(value = 1:3, name = c("H10", "H10", "G11"), alluvium_code = c(NA, "L3", NA))
  disc <- list(list(values = c(1, 1, 2, 3, 3)),       # H10 : 3 (dont une maille d'alluvions), G11 : 2
               list(values = c(1, 3)),                 # 1 contre 1
               list(values = numeric(0)))
  m <- ifn_ser_majority(disc, ser_tab)
  expect_equal(m$ser_code, c("H10", NA, NA))
  expect_equal(m$tie, c(FALSE, TRUE, FALSE))
  expect_match(m$tie_codes[2], "G11 1 / H10 1")
  # sur une grille : moitié ouest H10 (1), moitié est G11 (3), point au milieu -> égalité
  r <- grille_simple(rep(rep(c(1, 3), each = 5), times = 10))
  d <- ifn_disc_values(pts_ifn(700500, 6500500), r, "coarse_ser_700m", radius_m = 250)
  expect_true(ifn_ser_majority(d, ser_tab)$tie)
  d <- ifn_disc_values(pts_ifn(700300, 6500500), r, "coarse_ser_700m", radius_m = 250)
  expect_equal(ifn_ser_majority(d, ser_tab)$ser_code, "H10")
})

test_that("essences arborées : CD_REF v18 et v13 du référentiel contracts/species.csv", {
  cd <- ifn_tree_cd_ref(file.path(racine_st, "contracts", "species.csv"))
  expect_true(all(c(116759L, 139596L, 97947L, 113432L, 138781L) %in% cd))
})

copie_zone_station <- function(avec_table = TRUE, avec_grille = TRUE) {
  zone <- tempfile("zone_station_")
  dir.create(file.path(zone, "inputs"), recursive = TRUE)
  file.copy(file.path(zone_st, "inputs", "ifn"), file.path(zone, "inputs"), recursive = TRUE)
  file.copy(file.path(zone_st, "inputs", "station_gradients.tif"), file.path(zone, "inputs"))
  if (avec_table) {
    dir.create(file.path(zone, "params"))
    file.copy(file.path(zone_st, "params", "indicator_values.csv"), file.path(zone, "params"))
  }
  if (avec_grille) file.copy(file.path(zone_st, c("ser.tif", "ser.csv")), zone)
  zone
}

test_that("jeu fictif : coarse_* égales au calcul indépendant, 2e visite = 1re, garde passée", {
  zone <- copie_zone_station()
  rapport <- new_report()
  avec_racine_st(suppressMessages({
    res <- prepare_ifn_check(zone, rapport)
    res <- ifn_station_coarse(res, zone, rapport)
  }))
  p <- res$plots
  sg <- terra::rast(file.path(zone, "inputs", "station_gradients.tif"))
  xy <- terra::xyFromCell(sg, seq_len(terra::ncell(sg)))
  # placettes dont le disque touche le raster (les autres restent vides, et sont comptées)
  avec <- which(!is.na(p$coarse_hydric_700m))
  expect_gt(length(avec), 0)
  for (k in c(utils::head(avec, 3), utils::tail(avec, 1))) {
    d2 <- (xy[, 1] - p$x[k])^2 + (xy[, 2] - p$y[k])^2 <= 700^2
    for (b in c("hydric", "bioclim")) {
      v <- terra::values(sg[[b]])[d2]
      expect_equal(p[[paste0("coarse_", b, "_700m")]][k], mean(v[!is.na(v)]), tolerance = 1e-6,
                   info = paste(p$plot_id[k], b))
    }
  }
  # une placette sans aucune maille dans son disque : vide, jamais complétée
  for (k in which(is.na(p$coarse_hydric_700m))[1:3]) {
    d2 <- (xy[, 1] - p$x[k])^2 + (xy[, 2] - p$y[k])^2 <= 700^2
    expect_false(any(d2), info = p$plot_id[k])
  }
  expect_equal(is.na(p$coarse_bioclim_700m), is.na(p$coarse_hydric_700m))
  expect_true(all(p$ser_code[!is.na(p$ser_code)] == "H10"))
  expect_true(any(!is.na(p$ser_code)))
  v1 <- p$visit == 1L
  i2 <- which(!v1)
  i1 <- match(p$plot_id[i2], p$plot_id[v1])
  expect_equal(p$trophic[i2], p$trophic[v1][i1])
  expect_equal(p$coarse_hydric_700m[i2], p$coarse_hydric_700m[v1][i1])
  expect_equal(p$ser_code[i2], p$ser_code[v1][i1])
  # trophic : synthétique, dans l'échelle 1 à 9, non constant
  expect_true(all(p$trophic[!is.na(p$trophic)] >= 1 & p$trophic[!is.na(p$trophic)] <= 9))
  expect_gt(stats::sd(p$trophic, na.rm = TRUE), 0)
  textes <- vapply(Filter(function(e) e$section == "IFN : station", rapport$entries), `[[`, "", "text")
  expect_true(any(grepl("SYNTH", textes)))
  expect_true(any(grepl("assert_no_fine_extract_on_ifn", textes)))
  expect_true(any(grepl("PROVISOIRE", textes)))
  expect_true(any(grepl("sans valeur indicatrice", textes)))   # 125816 absent de la table fictive
  expect_true(any(grepl("NON convertis", textes)))
})

test_that("zone sans table de valeurs indicatrices ni grille : colonnes vides, et dit", {
  zone <- copie_zone_station(avec_table = FALSE, avec_grille = FALSE)
  rapport <- new_report()
  avec_racine_st(suppressMessages({
    res <- prepare_ifn_check(zone, rapport)
    res <- ifn_station_coarse(res, zone, rapport)
  }))
  expect_true(all(is.na(res$plots$trophic)))
  expect_true(all(is.na(res$plots$ser_code)))
  expect_true(any(!is.na(res$plots$coarse_hydric_700m)))
  textes <- vapply(rapport$entries, `[[`, "", "text")
  expect_true(any(grepl("indicator_values.csv absent", textes)))
  expect_true(any(grepl("ser.tif ou ser.csv absent", textes)))
})

test_that("table de valeurs indicatrices hors contrat : refusée avant toute écriture", {
  zone <- copie_zone_station()
  f <- file.path(zone, "params", "indicator_values.csv")
  l <- readLines(f); l[2] <- sub(";3;4;", ";12;4;", l[2]); writeLines(l, f)
  avec_racine_st(expect_error(suppressMessages(prepare_ifn_check(zone)), "indicator_values"))
  expect_false(dir.exists(file.path(zone, "ifn")))
})

test_that("plus aucune ligne « colonnes laissées vides » pour la station", {
  zone <- copie_zone_station()
  avec_racine_st(suppressMessages(res <- prepare_ifn_check(zone)))
  expect_false(any(grepl("source non branch", res$report$text)))
})
