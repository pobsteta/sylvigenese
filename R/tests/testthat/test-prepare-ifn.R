# Les motifs de recherche évitent les lettres accentuées (un « . » ne vaut qu'un octet) : la suite peut tourner en locale C.
# Tests de prepare_ifn (mission 019, spec §6) : d130, poids par cercle, coordonnées, garde IFN
# et contrats des trois tables. Aucun test n'est sauté : sans Arrow, ils échouent (voulu).

racine_ifn <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
zone_fictive <- file.path(racine_ifn, "tests", "fixtures", "zone_fictive")

brut <- function(nom, cols) {
  .ifn_read_csv(file.path(zone_fictive, "inputs", "ifn", nom), cols)
}

test_that("d130 = C13 / (10 pi), C13 en mm : 1175 mm donne 37,4 cm", {
  expect_equal(ifn_d130_cm(1175), 1175 / (10 * pi))
  expect_equal(round(ifn_d130_cm(1175), 1), 37.4)
  expect_equal(ifn_d130_cm(0), 0)
})

test_that("le cercle se choisit sur C13 en mm (IMOT 2025 p. 61, tableau DIMESS), bornes comprises", {
  # < 235 : non recensable ; 235 à < 705 : 6 m ; 705 à < 1175 : 9 m ; >= 1175 : 15 m
  expect_equal(ifn_circle_radius_m(c(234, 235, 704, 705, 706, 1174, 1175, 1176, 3000)),
               c(NA, 6, 6, 9, 9, 9, 15, 15, 15))
  expect_true(is.na(ifn_circle_radius_m(NA_real_)))
  # poids exacts aux seuils : 705 mm -> 39,30 ; 1175 mm -> 14,15 tiges/ha
  expect_equal(round(ifn_weight_ha(c(705, 1175)), 2), c(39.30, 14.15))
})

test_that("le poids est l'inverse de la surface du cercle : 88,4 ; 39,3 ; 14,1 tiges/ha", {
  expect_equal(ifn_weight_ha(c(400, 800, 1500)),
               c(10000 / (pi * 36), 10000 / (pi * 81), 10000 / (pi * 225)))
  expect_equal(round(ifn_weight_ha(c(400, 800, 1500)), 1), c(88.4, 39.3, 14.1))
})

test_that("jeu fictif : poids calculés = W du fichier (générateur à la règle de l'IMOT), y compris C13 = 705 et 1175 mm", {
  arbre <- brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13"))
  c13 <- as.numeric(arbre$C13)
  expect_true(all(abs(ifn_weight_ha(c13) - as.numeric(arbre$W)) <= 0.005))
  expect_true(all(c(705, 1175) %in% c13))
})

test_that("ifn_tables sur le jeu fictif : colonnes, effectifs, clés", {
  r <- ifn_tables(
    brut("PLACETTE.csv", c("CAMPAGNE", "IDP", "XL", "YL")),
    brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    brut("FLORE.csv", c("CAMPAGNE", "IDP", "CD_REF", "ABOND")))
  expect_named(r$plots, c("plot_id", "campaign", "x", "y", "loc_precision_m", "source",
                          "ser_code", "trophic", "coarse_hydric_700m", "coarse_bioclim_700m"))
  expect_named(r$trees, c("plot_id", "campaign", "tree_id", "species", "d130", "h", "weight_ha"))
  expect_named(r$flora, c("plot_id", "campaign", "cd_ref", "taxref_version", "abundance"))
  expect_equal(nrow(r$plots), 40)
  expect_equal(nrow(r$trees), 386)
  expect_equal(nrow(r$flora), 174)
  expect_false(anyDuplicated(r$trees[, c("plot_id", "campaign", "tree_id")]) > 0)
  expect_true(all(r$trees$d130 > 0))
})

test_that("un point du terrain tombe au bon endroit : placette 9000001, x est, y nord, EPSG:2154", {
  r <- ifn_tables(
    brut("PLACETTE.csv", c("CAMPAGNE", "IDP", "XL", "YL")),
    brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    brut("FLORE.csv", c("CAMPAGNE", "IDP", "CD_REF", "ABOND")))
  p <- r$plots[r$plots$plot_id == "9000001", ]
  expect_equal(p$x, 698757.7)    # est, Lambert-93
  expect_equal(p$y, 6498503.2)   # nord, Lambert-93
  expect_equal(p$campaign, 2015L)
  expect_true(all(r$plots$x > 0 & r$plots$x < 1300000))
  expect_true(all(r$plots$y > 6000000 & r$plots$y < 7200000))
})

test_that("arbre de la placette 9000001 : 387 mm -> d130 12,3 cm, cercle de 6 m, ESPAR '09' gardé", {
  r <- ifn_tables(
    brut("PLACETTE.csv", c("CAMPAGNE", "IDP", "XL", "YL")),
    brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    brut("FLORE.csv", c("CAMPAGNE", "IDP", "CD_REF", "ABOND")))
  t1 <- r$trees[r$trees$plot_id == "9000001", ]
  expect_equal(t1$species[1], "09")
  expect_equal(t1$d130[1], 387 / (10 * pi))
  expect_equal(t1$weight_ha[1], 10000 / (pi * 36))
  expect_equal(t1$tree_id[1:3], c("1", "2", "3"))
})

test_that("les placettes sont marquées IFN à 700 m, et la garde refuse un raster fin", {
  r <- ifn_tables(
    brut("PLACETTE.csv", c("CAMPAGNE", "IDP", "XL", "YL")),
    brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    brut("FLORE.csv", c("CAMPAGNE", "IDP", "CD_REF", "ABOND")))
  expect_true(all(r$plots$source == "ifn"))
  expect_true(all(r$plots$loc_precision_m == 700))
  # spec §6 : la garde refuse station_gradients.tif aux placettes
  expect_error(assert_no_fine_extract_on_ifn(r$plots, "station_gradients"),
               "interdite")
  expect_error(assert_no_fine_extract_on_ifn(r$plots, c("station_gradients.tif")),
               "interdite")
  # idem pour les variables fines connues, même sans le marquage (précision 700 > 25 m)
  expect_error(assert_no_fine_extract_on_ifn(r$plots, c("pente", "mnt", "lidar_h95")),
               "interdite")
  expect_error(assert_no_fine_extract_on_ifn(
    data.frame(x = 1, y = 2, loc_precision_m = 700), "station_gradients"), "interdite")
  # les colonnes à maille large restent permises
  expect_true(assert_no_fine_extract_on_ifn(r$plots, c("coarse_hydric_700m", "coarse_bioclim_700m")))
  # un point précis (<= 25 m) non IFN n'est pas bloqué
  expect_true(assert_no_fine_extract_on_ifn(
    data.frame(x = 1, y = 2, loc_precision_m = 1), "pente"))
})

test_that("signaler plutôt que deviner : entrées incohérentes refusées", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = "09", C13 = "800", HTOT = "10")
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  expect_silent(ifn_tables(p, a, f))
  # x et y inversés
  expect_error(ifn_tables(transform(p, XL = "6500000", YL = "700000"), a, f), "hors de la France")
  # arbre d'une placette absente
  expect_error(ifn_tables(p, transform(a, IDP = "2"), f), "absente de PLACETTE")
  expect_error(ifn_tables(p, a, transform(f, IDP = "2")), "absente de PLACETTE")
  # placette en double
  expect_error(ifn_tables(rbind(p, p), a, f), "en double")
  # C13 non numérique, ESPAR invalide
  expect_error(ifn_tables(p, transform(a, C13 = "abc"), f), "valeur non num")
  expect_error(ifn_tables(p, transform(a, ESPAR = "x"), f), "ESPAR invalide")
})

test_that("arbres sous le seuil de 235 mm écartés et dits ; W en désaccord signalé", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = c("09", "09", "09"),
                  C13 = c("200", "NA", "800"), HTOT = c("5", "5", "0"), W = c("88.42", "88.42", "88.42"),
                  stringsAsFactors = FALSE)
  a$C13[2] <- ""
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  r <- ifn_tables(p, a, f)
  expect_equal(nrow(r$trees), 1)
  expect_true(any(grepl("1 arbre.*C13 manquant", r$report$text)))
  expect_true(any(grepl("1 arbre.*C13 sous le seuil de recensabilit.*235 mm", r$report$text)))
  expect_true(any(grepl("colonne W du fichier", r$report$text)))   # 88,42 contre 39,3 au cercle de 9 m (800 mm)
  expect_true(any(grepl("HTOT inf.*0 : h mis", r$report$text)))
  expect_true(is.na(r$trees$h))                               # HTOT = 0 : pas de hauteur mesurée
})

test_that("signalements : colonnes vides, TAXREF v13 non converti, tree_id fabriqu, section IFN", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = c("09", "09"), C13 = c("800", "900"))
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  r <- ifn_tables(p, a, f)
  txt <- r$report$text
  expect_true(all(grepl("^IFN : ", r$report$section)))
  expect_true(any(grepl("ser_code, trophic.*coarse_hydric_700m.*coarse_bioclim_700m", txt)))
  expect_true(any(grepl("TAXREF v13.*NON convertis en v18", txt)))
  expect_true(any(grepl("tree_id fabriqu", txt)))
  expect_true(any(grepl("colonne HTOT absente", txt)))
  expect_equal(r$trees$tree_id, c("1", "2"))
  # avec ARBRE, plus de tree_id fabriqu ; doublon refusé
  a2 <- transform(a, ARBRE = c("7", "8"))
  expect_false(any(grepl("tree_id fabriqu", ifn_tables(p, a2, f)$report$text)))
  expect_error(ifn_tables(p, transform(a, ARBRE = c("7", "7")), f), "en double")
})

copie_zone_ifn <- function() {
  zone <- tempfile("zone_ifn_")
  dir.create(file.path(zone, "inputs"), recursive = TRUE)
  file.copy(file.path(zone_fictive, "inputs", "ifn"), file.path(zone, "inputs"), recursive = TRUE)
  zone
}

# Le validateur se lance depuis la racine du dépôt (validator_path : contracts/validate).
avec_racine <- function(code) {
  old <- setwd(racine_ifn); on.exit(setwd(old)); force(code)
}

test_that("prepare_ifn écrit trois Parquet conformes aux contrats, validés par le module", {
  zone <- copie_zone_ifn()
  avec_racine(expect_message(res <- prepare_ifn(zone), "IFN : placettes"))
  for (f in c("plots", "trees", "flora")) {
    expect_true(file.exists(file.path(zone, "ifn", paste0(f, ".parquet"))))
  }
  for (c in c("prepare.ifn_plots", "prepare.ifn_trees", "prepare.ifn_flora")) {
    chemin <- file.path(zone, "ifn", paste0(sub("prepare.ifn_", "", c), ".parquet"))
    st <- system2("python3", c(file.path(racine_ifn, "contracts", "validate"), c, chemin),
                  stdout = FALSE, stderr = FALSE)
    expect_equal(st, 0L, info = c)
  }
  # relu : mêmes effectifs que les tables en mémoire
  expect_equal(nrow(arrow::read_parquet(file.path(zone, "ifn", "trees.parquet"))), nrow(res$trees))
  # prepare_ifn n'ouvre aucun raster : aucune source fine n'est lue
  expect_false(any(grepl("[.]tif$", list.files(zone, recursive = TRUE))))
})

test_that("prepare_ifn_check n'écrit rien et ajoute ses signalements au rapport de prepare", {
  zone <- copie_zone_ifn()
  rapport <- new_report()
  avec_racine(suppressMessages(res <- prepare_ifn_check(zone, rapport)))
  expect_false(dir.exists(file.path(zone, "ifn")))
  expect_setequal(list.files(zone), "inputs")
  sections <- vapply(rapport$entries, function(e) e$section, character(1))
  expect_true(all(c("IFN : placettes", "IFN : arbres", "IFN : flore") %in% sections))
  expect_equal(length(rapport$entries), nrow(res$report))
})

test_that("entrée IFN refusée : erreur en français avant toute écriture, aucune sortie", {
  # fichier absent
  zone <- copie_zone_ifn()
  unlink(file.path(zone, "inputs", "ifn", "ARBRE.csv"))
  avec_racine(expect_error(prepare_ifn(zone), "absente.*ARBRE"))
  expect_false(dir.exists(file.path(zone, "ifn")))
  # C13 non numérique : refusé par le contrat inputs.ifn_arbre
  zone <- copie_zone_ifn()
  f <- file.path(zone, "inputs", "ifn", "ARBRE.csv")
  l <- readLines(f, encoding = "UTF-8"); v <- strsplit(l[2], ";")[[1]]; v[4] <- "grosse"
  l[2] <- paste(v, collapse = ";"); writeLines(l, f)
  avec_racine(expect_error(prepare_ifn(zone), "ARBRE"))
  expect_false(dir.exists(file.path(zone, "ifn")))
})

test_that("prepare_ifn : dossier sans IFN signalé", {
  expect_error(prepare_ifn(tempfile("vide_")), "absente")
})

test_that("le module prepare contrôle l'IFN avant la première écriture (ordre dans run_prepare)", {
  src <- paste(deparse(run_prepare), collapse = "\n")
  expect_true(regexpr("prepare_ifn_check", src, fixed = TRUE) < regexpr("prepare_grid", src, fixed = TRUE))
})

test_that("un seul écrivain Parquet : write_parquet_tbl de commun.R", {
  expect_false(exists(".ifn_write_parquet"))
})
