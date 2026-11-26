# Les motifs de recherche évitent les lettres accentuées (un « . » ne vaut qu'un octet) : la suite peut tourner en locale C.
# Tests de prepare_ifn (mission 019, spec §6) : d130, poids par cercle, coordonnées, garde IFN
# et contrats des trois tables. Aucun test n'est sauté : sans Arrow, ils échouent (voulu).

racine_ifn <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))
zone_fictive <- file.path(racine_ifn, "tests", "fixtures", "zone_fictive")

brut <- function(nom, cols) {
  .ifn_read_csv(file.path(zone_fictive, "inputs", "ifn", nom), cols)
}

cols_p <- c("CAMPAGNE", "IDP", "XL", "YL", "VISITE")
cols_a <- c("CAMPAGNE", "IDP", "ESPAR", "C13")
cols_f <- c("CAMPAGNE", "IDP", "CD_REF", "ABOND")
tables_fictives <- function() {
  ifn_tables(brut("PLACETTE.csv", cols_p), brut("ARBRE.csv", cols_a), brut("FLORE.csv", cols_f))
}

test_that("d130 = C13 x 100 / pi, C13 en mètres : 1,175 m donne 37,4 cm", {
  expect_equal(ifn_d130_cm(1.175), 1.175 * 100 / pi)
  expect_equal(round(ifn_d130_cm(1.175), 1), 37.4)
  expect_equal(ifn_d130_cm(0), 0)
  # 0,235 m = D13 de 7,5 cm (seuil de recensabilité, ARBRE p. 1 et GEN p. 3)
  expect_equal(round(ifn_d130_cm(0.235), 1), 7.5)
})

test_that("le cercle se choisit sur C13 en m (IMOT 2025 p. 61, tableau DIMESS), bornes comprises", {
  # < 0,235 : non recensable ; 0,235 à < 0,705 : 6 m ; 0,705 à < 1,175 : 9 m ; >= 1,175 : 15 m
  expect_equal(ifn_circle_radius_m(c(0.234, 0.235, 0.704, 0.705, 0.706, 1.174, 1.175, 1.176, 3)),
               c(NA, 6, 6, 9, 9, 9, 15, 15, 15))
  expect_true(is.na(ifn_circle_radius_m(NA_real_)))
  # poids exacts aux seuils : 0,705 m -> 39,30 ; 1,175 m -> 14,15 tiges/ha
  expect_equal(round(ifn_weight_ha(c(0.705, 1.175)), 2), c(39.30, 14.15))
})

test_that("le poids est l'inverse de la surface du cercle : 88,4 ; 39,3 ; 14,1 tiges/ha", {
  expect_equal(ifn_weight_ha(c(0.400, 0.800, 1.500)),
               c(10000 / (pi * 36), 10000 / (pi * 81), 10000 / (pi * 225)))
  expect_equal(round(ifn_weight_ha(c(0.400, 0.800, 1.500)), 1), c(88.4, 39.3, 14.1))
})

test_that("jeu fictif : poids calculés = W du fichier pour la 1re visite, y compris C13 = 0,705 et 1,175 m", {
  arbre <- brut("ARBRE.csv", c("CAMPAGNE", "IDP", "ESPAR", "C13", "VEGET5"))
  v1 <- arbre$VEGET5 == ""                       # 1re visite : VEGET5 vide
  c13 <- as.numeric(arbre$C13)[v1]
  expect_true(all(abs(ifn_weight_ha(c13) - as.numeric(arbre$W)[v1]) <= 0.005))
  expect_true(all(c(0.705, 1.175) %in% c13))     # arbres exactement aux bornes
})

test_that("ifn_tables sur le jeu fictif : colonnes, effectifs, clés", {
  r <- tables_fictives()
  expect_named(r$plots, c("plot_id", "campaign", "x", "y", "loc_precision_m", "source",
                          "ser_code", "trophic", "coarse_hydric_700m", "coarse_bioclim_700m",
                          "visit", "date_point", "incident_nature", "incident_intensity",
                          "harvest_5y", "clearing_5y", "planting_5y"))
  expect_named(r$trees, c("plot_id", "campaign", "tree_id", "species", "d130", "h", "weight_ha",
                          "veg_state", "veg_state_5y", "radial_incr_5y_m", "stem_volume_m3"))
  expect_named(r$flora, c("plot_id", "campaign", "cd_ref", "taxref_version", "abundance"))
  expect_equal(nrow(r$plots), 228)               # 120 placettes de 1re visite + 108 revisites
  expect_equal(sum(r$plots$visit == 1L), 120)
  expect_equal(sum(r$plots$visit == 2L), 108)
  expect_equal(nrow(r$trees), 2286)              # une ligne par arbre et par visite
  expect_equal(nrow(r$flora), 626)               # flore de la 1re visite seule
  expect_false(anyDuplicated(r$trees[, c("plot_id", "campaign", "tree_id")]) > 0)
  expect_true(all(r$trees$d130 > 0, na.rm = TRUE))
})

test_that("la 2e visite d'un point garde son IDP et tombe 5 campagnes plus tard", {
  r <- tables_fictives()
  p1 <- r$plots[r$plots$visit == 1L, ]
  p2 <- r$plots[r$plots$visit == 2L, ]
  expect_true(all(p2$plot_id %in% p1$plot_id))
  expect_equal(p2$campaign, p1$campaign[match(p2$plot_id, p1$plot_id)] + 5L)
  expect_true(all(grepl("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", r$plots$date_point)))
  yrs <- as.numeric(as.Date(p2$date_point) - as.Date(p1$date_point[match(p2$plot_id, p1$plot_id)])) / 365.25
  expect_true(all(yrs > 3.9 & yrs < 6.1))
})

test_that("un point du terrain tombe au bon endroit : placette 9000001, x est, y nord, EPSG:2154", {
  r <- tables_fictives()
  p <- r$plots[r$plots$plot_id == "9000001" & r$plots$visit == 1L, ]
  expect_equal(p$x, 699794.4)    # est, Lambert-93
  expect_equal(p$y, 6500485.4)   # nord, Lambert-93
  expect_equal(p$campaign, 2015L)
  # la 2e visite recopie les mêmes coordonnées floutées
  p2 <- r$plots[r$plots$plot_id == "9000001" & r$plots$visit == 2L, ]
  expect_equal(c(p2$x, p2$y, p2$campaign), c(699794.4, 6500485.4, 2020))
  expect_true(all(r$plots$x > 0 & r$plots$x < 1300000))
  expect_true(all(r$plots$y > 6000000 & r$plots$y < 7200000))
})

test_that("arbre de la placette 9000001 : 0,387 m -> d130 12,3 cm, cercle de 6 m, ESPAR '09' gardé", {
  r <- tables_fictives()
  t1 <- r$trees[r$trees$plot_id == "9000001" & r$trees$campaign == 2015L, ]
  expect_equal(t1$species[1], "09")
  expect_equal(t1$d130[1], 0.387 * 100 / pi)
  expect_equal(round(t1$d130[1], 1), 12.3)
  expect_equal(t1$weight_ha[1], 10000 / (pi * 36))
  expect_equal(t1$tree_id[1:3], c("1", "2", "3"))   # numéro d'arbre A de l'export
})

test_that("dynamique : arbre 1 revu en 2020 (vivant, 0,507 m), arbre 3 coupé (VEGET5 6, sans C13)", {
  r <- tables_fictives()
  a <- r$trees[r$trees$plot_id == "9000001", ]
  v1 <- a[a$campaign == 2015L & a$tree_id == "1", ]
  v2 <- a[a$campaign == 2020L & a$tree_id == "1", ]
  expect_equal(c(v1$veg_state, v1$veg_state_5y), c("0", NA))      # VEGET en 1re visite, VEGET5 vide
  expect_equal(c(v2$veg_state, v2$veg_state_5y), c(NA, "0"))      # l'inverse en 2e visite
  expect_equal(v2$d130, 0.507 * 100 / pi)
  expect_true(is.na(v1$radial_incr_5y_m))
  expect_equal(a$radial_incr_5y_m[a$campaign == 2020L & a$tree_id == "2"], 0.0067)  # IR5 en m
  cut <- a[a$campaign == 2020L & a$tree_id == "3", ]
  expect_equal(cut$veg_state_5y, "6")
  expect_true(is.na(cut$d130) && is.na(cut$weight_ha))
  # le poids d'une 2e visite est le W de l'export (arbre 1 : 0,507 m -> cercle de 6 m)
  expect_equal(v2$weight_ha, 88.42)
})

test_that("le jeu fictif porte les cinq événements, des recrues et un IR5 partiel, par essence", {
  r <- tables_fictives()
  tr <- r$trees
  v1 <- tr[is.na(tr$veg_state_5y) & !is.na(tr$veg_state), ]
  v2 <- tr[!is.na(tr$veg_state_5y), ]
  expect_setequal(unique(v2$veg_state_5y), c("0", "M", "2", "6", "7", "N", "T"))
  # recrues : 2e visite dont (plot_id, tree_id) n'a pas de 1re visite
  rec <- v2[!paste(v2$plot_id, v2$tree_id) %in% paste(v1$plot_id, v1$tree_id), ]
  expect_gt(nrow(rec), 100)
  expect_true(all(rec$d130 >= ifn_d130_cm(0.235)))
  # chaque essence a de quoi ajuster : arbres à risque, morts, recrues, IR5
  vivants1 <- v1[v1$veg_state == "0", ]
  revu <- merge(vivants1[, c("plot_id", "tree_id", "species")],
                v2[, c("plot_id", "tree_id", "veg_state_5y")], by = c("plot_id", "tree_id"))
  for (sp in c("09", "61", "62", "03", "64")) {
    expect_gte(sum(revu$species == sp), 100)
    expect_gte(sum(revu$species == sp & revu$veg_state_5y %in% c("M", "2")), 8)
    expect_gte(sum(rec$species == sp), 20)
    expect_gte(sum(tr$species == sp & !is.na(tr$radial_incr_5y_m)), 150)
  }
  expect_true(any(is.na(tr$radial_incr_5y_m)) && any(!is.na(tr$radial_incr_5y_m)))
  expect_true(all(tr$radial_incr_5y_m[!is.na(tr$radial_incr_5y_m)] > 0))
})

test_that("quelques placettes à incident, défrichées, et une sur dix non revisitée", {
  r <- tables_fictives()
  p1 <- r$plots[r$plots$visit == 1L, ]
  p2 <- r$plots[r$plots$visit == 2L, ]
  expect_equal(sum(p1$incident_nature == 4L), 12)
  expect_true(all(p1$incident_intensity[p1$incident_nature == 4L] == 2L))
  expect_equal(sum(p2$clearing_5y == 2L), 12)
  expect_equal(sum(!p1$plot_id %in% p2$plot_id), 12)
  # NINCID relevé en 1re visite seulement, DEF5 en 2e seulement
  expect_true(all(is.na(p2$incident_nature)) && all(is.na(p1$clearing_5y)))
  expect_true(all(is.na(r$plots$harvest_5y)))     # PRELEV5 : 2010-2014 seulement, vide ici
})

test_that("les placettes sont marquées IFN à 700 m, et la garde refuse un raster fin", {
  r <- tables_fictives()
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

# Jeu minimal : une placette en 1re visite (2015) et sa revisite (2020), deux arbres.
mini <- function() {
  list(
    p = data.frame(CAMPAGNE = c("2015", "2020"), IDP = "1", XL = "700000", YL = "6500000",
                   VISITE = c("1", "2"), DATEPOINT = c("10/03/2015", "20/06/2020"),
                   NINCID = c("0", ""), INCID = c("0", ""), PRELEV5 = "", DEF5 = c("", "0"),
                   INSTP5 = c("", "0"), stringsAsFactors = FALSE),
    a = data.frame(CAMPAGNE = c("2015", "2015", "2020", "2020", "2020"), IDP = "1",
                   ESPAR = "09", C13 = c("0.800", "0.900", "0.850", "", "0.240"),
                   A = c("1", "2", "1", "2", "3"), VEGET = c("0", "0", "", "", ""),
                   VEGET5 = c("", "", "0", "6", "0"), IR5 = c("0.0120", "", "0.0110", "", ""),
                   W = c("39.30", "39.30", "39.30", "", ""), stringsAsFactors = FALSE),
    f = data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  )
}

test_that("V (volume bois fort tige, m3) est gardé tel quel ; absent il reste NA et est dit", {
  # jeu fictif : V du fichier repris sans conversion (arbre 1 de 9000001 : 0,0682 m3, 2015)
  r <- tables_fictives()
  t1 <- r$trees[r$trees$plot_id == "9000001" & r$trees$campaign == 2015L & r$trees$tree_id == "1", ]
  expect_equal(t1$stem_volume_m3, 0.0682)
  expect_true(any(!is.na(r$trees$stem_volume_m3)) && any(is.na(r$trees$stem_volume_m3)))
  expect_true(all(r$trees$stem_volume_m3[!is.na(r$trees$stem_volume_m3)] >= 0))
  expect_true(any(grepl("stem_volume_m3 \\(m3.*sans conversion.*renseign", r$report$text)))
  # jeu minimal : V du fichier ; vide -> NA, jamais calculé
  m <- mini()
  a <- transform(m$a, V = c("0.9500", "", "1.0100", "", ""))
  r2 <- ifn_tables(m$p, a, m$f)
  expect_equal(r2$trees$stem_volume_m3, c(0.95, NA, 1.01, NA, NA))
  expect_true(any(grepl("renseign.*sur 2 ligne.*sur 5", r2$report$text[grepl("^stem_volume_m3 ", r2$report$text)])))
  expect_error(ifn_tables(m$p, transform(m$a, V = c("-1", "", "", "", "")), m$f), "V n.*gatif")
  expect_error(ifn_tables(m$p, transform(m$a, V = c("abc", "", "", "", "")), m$f), "valeur non num")
  # colonne V absente : NA partout et ligne de rapport
  r3 <- ifn_tables(m$p, m$a, m$f)
  expect_true(all(is.na(r3$trees$stem_volume_m3)))
  expect_true(any(grepl("colonne V absente.*stem_volume_m3", r3$report$text)))
  # V ne change ni d130, ni le poids, ni les placettes (aucun raster ouvert)
  expect_equal(r2$trees$d130, r3$trees$d130)
  expect_equal(r2$trees$weight_ha, r3$trees$weight_ha)
})

test_that("signaler plutôt que deviner : entrées incohérentes refusées", {
  m <- mini()
  expect_silent(ifn_tables(m$p, m$a, m$f))
  # x et y inversés
  expect_error(ifn_tables(transform(m$p, XL = "6500000", YL = "700000"), m$a, m$f), "hors de la France")
  # arbre d'une placette absente
  expect_error(ifn_tables(m$p, transform(m$a, IDP = "2"), m$f), "absente de PLACETTE")
  expect_error(ifn_tables(m$p, m$a, transform(m$f, IDP = "2")), "absente de PLACETTE")
  # placette en double
  expect_error(ifn_tables(rbind(m$p, m$p), m$a, m$f), "en double")
  # C13 non numérique, ESPAR invalide
  expect_error(ifn_tables(m$p, transform(m$a, C13 = "abc"), m$f), "valeur non num")
  expect_error(ifn_tables(m$p, transform(m$a, ESPAR = "x"), m$f), "ESPAR invalide")
  # VISITE absente ou hors de 1 et 2 : les deux visites ne se distinguent plus
  expect_error(ifn_tables(m$p[, names(m$p) != "VISITE"], m$a, m$f), "VISITE absente")
  expect_error(ifn_tables(transform(m$p, VISITE = c("1", "3")), m$a, m$f), "VISITE")
  # C13 en millimètres (ancienne hypothèse de M1a) : refusé, jamais converti en silence
  expect_error(ifn_tables(m$p, transform(m$a, C13 = c("800", "900", "850", "", "240")), m$f),
               "en m.*tres")
  # numéro d'arbre en double dans une visite
  expect_error(ifn_tables(m$p, transform(m$a, A = c("1", "1", "1", "2", "3")), m$f), "en double")
  # 2e visite sans colonne A : les deux visites ne se joignent pas
  expect_error(ifn_tables(m$p, m$a[, names(m$a) != "A"], m$f), "colonne A absente")
})

test_that("arbres sous le seuil de 0,235 m écartés et dits en 1re visite ; W en désaccord signalé", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000", VISITE = "1")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = c("09", "09", "09"),
                  C13 = c("0.200", "NA", "0.800"), HTOT = c("5", "5", "0"),
                  W = c("88.42", "88.42", "88.42"), A = c("1", "2", "3"),
                  stringsAsFactors = FALSE)
  a$C13[2] <- ""
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  r <- ifn_tables(p, a, f)
  expect_equal(nrow(r$trees), 1)
  expect_true(any(grepl("1 arbre.*C13 manquant", r$report$text)))
  expect_true(any(grepl("1 arbre.*C13 sous le seuil de recensabilit.*0,235 m", r$report$text)))
  expect_true(any(grepl("colonne W du fichier", r$report$text)))   # 88,42 contre 39,3 au cercle de 9 m (0,800 m)
  expect_true(any(grepl("HTOT inf.*0 : h mis", r$report$text)))
  expect_true(is.na(r$trees$h))                               # HTOT = 0 : pas de hauteur mesurée
})

test_that("signalements : colonnes vides, TAXREF v13 non converti, tree_id fabriqu, section IFN", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000", VISITE = "1")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = c("09", "09"), C13 = c("0.800", "0.900"))
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  r <- ifn_tables(p, a, f)
  txt <- r$report$text
  expect_true(all(grepl("^IFN : ", r$report$section)))
  expect_true(any(grepl("ser_code, trophic.*coarse_hydric_700m.*coarse_bioclim_700m", txt)))
  expect_true(any(grepl("TAXREF v13.*NON convertis en v18", txt)))
  expect_true(any(grepl("tree_id fabriqu", txt)))
  expect_true(any(grepl("colonne HTOT absente", txt)))
  expect_equal(r$trees$tree_id, c("1", "2"))
  # avec A, plus de tree_id fabriqu ; doublon refusé
  a2 <- transform(a, A = c("7", "8"))
  expect_false(any(grepl("tree_id fabriqu", ifn_tables(p, a2, f)$report$text)))
  expect_error(ifn_tables(p, transform(a, A = c("7", "7")), f), "en double")
})

test_that("colonnes de la dynamique absentes : chacune est dite au rapport et reste vide", {
  p <- data.frame(CAMPAGNE = "2015", IDP = "1", XL = "700000", YL = "6500000", VISITE = "1")
  a <- data.frame(CAMPAGNE = "2015", IDP = "1", ESPAR = "09", C13 = "0.800", A = "1")
  f <- data.frame(CAMPAGNE = "2015", IDP = "1", CD_REF = "125816", ABOND = "2")
  r <- ifn_tables(p, a, f)
  txt <- r$report$text
  for (col in c("NINCID", "INCID", "DEF5", "INSTP5", "PRELEV5", "DATEPOINT", "VEGET", "VEGET5", "IR5")) {
    expect_true(any(grepl(paste0("colonne ", col, " absente"), txt)), info = col)
  }
  expect_true(is.na(r$trees$veg_state) && is.na(r$trees$veg_state_5y) && is.na(r$trees$radial_incr_5y_m))
  expect_true(is.na(r$plots$date_point) && is.na(r$plots$incident_nature))
})

test_that("jeu minimal : codes de VEGET5 comptés, recrues, 2e visite sans C13, W manquant, intervalle", {
  m <- mini()
  r <- ifn_tables(m$p, m$a, m$f)
  txt <- r$report$text
  expect_equal(nrow(r$trees), 5)
  expect_true(any(grepl("VEGET5 des lignes de 2e visite : coup.* 1 ; vivant 2", txt)))
  expect_true(any(grepl("1 recrue.*0 sous le seuil", txt)))                     # arbre 3 : 0,240 m
  expect_true(any(grepl("1 ligne.*2e visite sans C13.*d130 et weight_ha vides", txt)))
  expect_true(any(grepl("1 arbre.*2e visite avec C13 mais sans W", txt)))      # la recrue sans W
  expect_true(any(grepl("intervalle entre visites.*de 5,28 .* 5,28 ans sur 1 placette", txt)))
  expect_true(any(grepl("IR5 .*renseign.* sur 2 ligne", txt)))
  expect_true(any(grepl("PRELEV5 renseign.* sur 0 placette", txt)))
  # d130 et poids : 2e visite = W de l'export, vide s'il manque ; arbre coupé sans C13
  t2 <- r$trees[r$trees$campaign == 2020L, ]
  expect_equal(t2$weight_ha, c(39.30, NA, NA))
  expect_true(is.na(t2$d130[2]))
  expect_equal(t2$d130[3], 0.240 * 100 / pi)
  expect_equal(r$plots$date_point, c("2015-03-10", "2020-06-20"))
})

test_that("hors modalités ou vide : mis à vide et compté, jamais remplacé", {
  m <- mini()
  # VEGET5 : « M » n'existe pas en 2010-2014 ; VEGET « 1 » n'existe pas avant 2019 (A)
  p <- transform(m$p, CAMPAGNE = c("2010", "2015"))
  a <- transform(m$a, CAMPAGNE = c("2010", "2010", "2015", "2015", "2015"),
                 VEGET = c("1", "0", "", "", ""), VEGET5 = c("", "", "M", "6", "Z"))
  r <- ifn_tables(p, a, m$f)
  txt <- r$report$text
  expect_true(any(grepl("1 valeur.*VEGET hors modalit.*2010", txt)))
  expect_true(any(grepl("1 valeur.*VEGET5 hors modalit.*2015", txt)))   # M et 6 valent en 2015 : seul Z est faux
  expect_true(is.na(r$trees$veg_state[1]))
  expect_equal(r$trees$veg_state[2], "0")
  # hors modalités de placette
  p2 <- transform(m$p, NINCID = c("9", ""), DEF5 = c("", "7"))
  r2 <- ifn_tables(p2, m$a, m$f)
  expect_true(any(grepl("1 valeur.*NINCID hors modalit.*0 .* 5", r2$report$text)))
  expect_true(any(grepl("1 valeur.*DEF5 hors modalit.*0 .* 5", r2$report$text)))
  expect_true(is.na(r2$plots$incident_nature[1]) && is.na(r2$plots$clearing_5y[2]))
  # DATEPOINT impossible (31/02) ou illisible : entrée refusée, jamais devinée
  for (d in c("31/02/2015", "hier")) {
    expect_error(ifn_tables(transform(m$p, DATEPOINT = c(d, "20/06/2020")), m$a, m$f),
                 "DATEPOINT impossible")
  }
  # arbre de 1re visite sans VEGET, ligne de 2e visite sans VEGET5
  a3 <- transform(m$a, VEGET = c("", "0", "", "", ""), VEGET5 = c("", "", "", "6", "0"))
  r3 <- ifn_tables(m$p, a3, m$f)
  expect_true(any(grepl("1 arbre.*1re visite sans VEGET", r3$report$text)))
  expect_true(any(grepl("1 ligne.*2e visite sans VEGET5", r3$report$text)))
  # IR5 négatif : refusé
  expect_error(ifn_tables(m$p, transform(m$a, IR5 = c("-0.01", "", "", "", "")), m$f), "IR5 n.*gatif")
})

test_that("codes de VEGET5 par période : VEGET5 2010-14, VEGET56 2015-16, VEGET57 2017-18, VEGET59 2019-", {
  expect_equal(IFN_VEGET5_CODES(2012), c("0", "6", "A", "5", "C"))
  expect_equal(IFN_VEGET5_CODES(2016), c("0", "M", "A", "6", "N"))
  expect_equal(IFN_VEGET5_CODES(2018), c("0", "6", "7", "A", "M", "N", "T"))
  expect_equal(IFN_VEGET5_CODES(2022), c("0", "6", "7", "1", "2", "M", "N", "T"))
  expect_length(IFN_VEGET5_CODES(2009), 0)
  expect_equal(IFN_VEGET_CODES(2018), c("0", "A", "5", "C"))
  expect_equal(IFN_VEGET_CODES(2019), c("0", "1", "5", "C"))
  expect_null(IFN_VEGET_CODES(2007))
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

test_that("V écrit en Parquet (float64, facultative au contrat) et relu", {
  zone <- copie_zone_ifn()
  avec_racine(suppressMessages(res <- prepare_ifn(zone)))
  t <- arrow::read_parquet(file.path(zone, "ifn", "trees.parquet"))
  expect_true("stem_volume_m3" %in% names(t))
  expect_equal(sum(!is.na(t$stem_volume_m3)), sum(!is.na(res$trees$stem_volume_m3)))
  expect_false(any(grepl("[.]tif$", list.files(zone, recursive = TRUE))))
})
