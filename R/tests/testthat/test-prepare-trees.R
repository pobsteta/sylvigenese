# Tests de prepare : arbres, houppiers et peuplements (mission 018, R/prepare_trees.R).
# Coordonnées : EPSG:2154, x vers l'est, y vers le nord, en mètres ; les cellules d'un raster
# se comptent depuis le coin nord-ouest. Le massif fictif va de (700000 ; 6500000) au sud-ouest
# à (701000 ; 6501000) au nord-est (tests/fixtures/zone_fictive/README.md).
#
# Ce fichier est autonome : les tests du module lancent eux-mêmes la chaîne prepare -> biomes ->
# trees dans une racine temporaire (comme test-biomes.R) ; aucun ne lit la sortie d'un autre test
# ni les sorties versionnées du jeu fictif (forest_mask.tif, grid.tif, trees_init/...).

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

# MNH de plateaux : `blocs` donne (ligne1, ligne2, col1, col2, h) en cellules (comptées depuis le
# coin nord-ouest) ; le reste vaut 0. Raster de `nl` lignes sur `nc` colonnes, maille de 0,5 m.
mnh_plateaux <- function(blocs, nl = 60, nc = 60) {
  r <- terra::rast(nrows = nl, ncols = nc, xmin = 700000, xmax = 700000 + nc / 2,
                   ymin = 6500000, ymax = 6500000 + nl / 2, crs = "EPSG:2154")
  m <- matrix(0, nl, nc)
  for (k in seq_len(nrow(blocs))) {
    m[blocs$l1[k]:blocs$l2[k], blocs$c1[k]:blocs$c2[k]] <- blocs$h[k]
  }
  terra::setValues(r, as.vector(t(m)))
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

test_that("la fenêtre est celle de tarif-nemeton : 3 m sous 2 m, puis vers 5,6 m", {
  # f_ws(x) = 2,6 (1 - exp(-0,08 (x - 2))) + 3 pour x >= 2, 3 sinon
  # (tarif-nemeton, code/etage_b_arbres_lidar.R, l.13)
  expect_equal(tree_window_m(c(0, 1.9, 2)), c(3, 3, 3))
  expect_equal(tree_window_m(10), 2.6 * (1 - exp(-0.08 * 8)) + 3)
  expect_equal(tree_window_m(20), 2.6 * (1 - exp(-0.08 * 18)) + 3)
  expect_equal(tree_window_m(20), 4.98, tolerance = 1e-3)
  expect_equal(tree_window_m(1000), 5.6, tolerance = 1e-6)
  h <- seq(0, 60, by = 1)
  expect_true(all(diff(tree_window_m(h)) >= 0))
  expect_true(all(tree_window_m(h) >= 3 & tree_window_m(h) < 5.6 + 1e-9))
  # nombre impair de cellules, jamais plus large que la fenêtre demandée
  expect_true(all(window_cells(c(3, 4.5, 5.6), 0.5) %% 2L == 1L))
  expect_equal(window_cells(3, 0.5), 7L)
  expect_equal(window_cells(5.6, 0.5), 11L)
})

test_that("les paramètres de détection sont ceux de tarif-nemeton (hauteur minimale, médiane)", {
  expect_equal(TREES_HMIN_M, 5)          # lmf(hmin = 5), l.18 ; th_tree = 5, l.19
  expect_equal(TREES_SMOOTH_CELLS, 3L)   # focal(chm, w = 3, fun = median), l.17
  expect_equal(c(TREES_CROWN_TH_TREE, TREES_CROWN_TH_SEED, TREES_CROWN_TH_CR, TREES_CROWN_MAX_CR),
               c(5, 0.45, 0.55, 24))     # dalponte2016, l.19
})

# ------------------------------------------------------------------ houppiers

test_that("un plateau de 10 x 10 cellules donne un houppier de 100 cellules, soit 25 m²", {
  chm <- mnh_plateaux(data.frame(l1 = 20, l2 = 29, c1 = 20, c2 = 29, h = 15))
  seeds <- data.frame(row = 25L, col = 25L)
  expect_equal(segment_crowns(chm, seeds), 100L)
})

test_that("la croissance de région est limitée à max_cr / 2 cellules du sommet, ligne et colonne", {
  # bande de 4 lignes (10 à 13) sur 20 colonnes (10 à 29) ; sommet à (ligne 11 ; colonne 10) :
  # colonnes 10 à 21 (écart < 12), soit 4 x 12 = 48 cellules. Une ligne et une colonne
  # permutées donneraient un autre nombre.
  chm <- mnh_plateaux(data.frame(l1 = 10, l2 = 13, c1 = 10, c2 = 29, h = 15))
  expect_equal(segment_crowns(chm, data.frame(row = 11L, col = 10L)), 48L)
  # un seul sommet au bord est, symétrique
  expect_equal(segment_crowns(chm, data.frame(row = 11L, col = 29L)), 48L)
})

test_that("le houppier s'arrête là où le MNH passe sous th_tree, th_seed ou th_cr", {
  # plateau de 15 m au sommet, entouré d'un anneau de 4 m (sous th_tree = 5) : l'anneau est écarté
  chm <- mnh_plateaux(data.frame(l1 = c(15, 20), l2 = c(34, 29), c1 = c(15, 20), c2 = c(34, 29),
                                 h = c(4, 15)))
  expect_equal(segment_crowns(chm, data.frame(row = 25L, col = 25L)), 100L)
  # anneau de 6 m : au-dessus de th_tree mais sous 0,45 x 15 = 6,75 m (th_seed) : écarté aussi
  chm2 <- mnh_plateaux(data.frame(l1 = c(15, 20), l2 = c(34, 29), c1 = c(15, 20), c2 = c(34, 29),
                                  h = c(6, 15)))
  expect_equal(segment_crowns(chm2, data.frame(row = 25L, col = 25L)), 100L)
  # anneau de 12 m : au-dessus de th_seed (6,75) et de th_cr x moyenne (0,55 x 15 = 8,25) : accepté
  chm3 <- mnh_plateaux(data.frame(l1 = c(21, 24), l2 = c(28, 27), c1 = c(21, 24), c2 = c(28, 27),
                                  h = c(12, 15)))
  expect_equal(segment_crowns(chm3, data.frame(row = 25L, col = 25L)), 64L)
  # une cellule plus haute que le sommet de plus de 5 % n'est pas absorbée (elle est un autre sommet)
  chm4 <- mnh_plateaux(data.frame(l1 = c(20, 20), l2 = c(24, 24), c1 = c(20, 25), c2 = c(24, 29),
                                  h = c(15, 17)))
  n <- segment_crowns(chm4, data.frame(row = c(22L, 22L), col = c(22L, 27L)))
  expect_equal(n, c(25L, 25L))
})

test_that("deux arbres voisins se partagent les cellules sans en compter une deux fois", {
  chm <- mnh_synthetique(data.frame(x = c(700015.25, 700022.25), y = c(6500020.25, 6500020.25),
                                    h = c(20, 20), r = 5))
  d <- detect_trees(chm)
  expect_equal(nrow(d), 2L)
  n <- segment_crowns(smooth_chm(chm), d)
  expect_true(all(n > 0L))
  # aucune cellule n'est comptée deux fois : au plus les cellules du MNH lissé au-dessus de th_tree
  expect_lte(sum(n), sum(terra::values(smooth_chm(chm), mat = FALSE) > TREES_CROWN_TH_TREE, na.rm = TRUE))
  # deux arbres symétriques : deux houppiers de même taille, à 10 % près (les cellules de la médiane vont au premier voisin)
  expect_lt(abs(n[1] - n[2]) / mean(n), 0.1)
})

test_that("la surface du houppier croît avec la taille de la cime", {
  petit <- mnh_synthetique(data.frame(x = 700020.25, y = 6500020.25, h = 20, r = 3))
  grand <- mnh_synthetique(data.frame(x = 700020.25, y = 6500020.25, h = 20, r = 6))
  cp <- segment_crowns(smooth_chm(petit), detect_trees(petit))
  cg <- segment_crowns(smooth_chm(grand), detect_trees(grand))
  expect_gt(cg, cp)
  # cône parabolique de rayon 6 m, 20 m de haut : cellules au-dessus de 0,45 x 20 = 9 m,
  # soit d < 0,74 r = 4,4 m, environ 61 m² (244 cellules) ; fenêtre large pour la maille de 0,5 m
  expect_gt(cg * 0.25, 45)
  expect_lt(cg * 0.25, 80)
  # le houppier ne dépasse jamais le carré de max_cr cellules de côté
  expect_lte(cg, TREES_CROWN_MAX_CR^2)
})

test_that("une cellule sans valeur n'entre jamais dans un houppier, et aucun sommet : aucun houppier", {
  chm <- mnh_plateaux(data.frame(l1 = 20, l2 = 29, c1 = 20, c2 = 29, h = 15))
  chm[25, 22:24] <- NA
  expect_equal(segment_crowns(chm, data.frame(row = 25L, col = 25L)), 97L)
  expect_equal(segment_crowns(chm, data.frame(row = integer(), col = integer())), integer())
})

# ------------------------------------------------------------------ d130 : étage B

coef_essai <- data.frame(species = c("09", "62", "64"), a = c(0.10, 0.20, 0.30),
                         b = c(1.12, 1.08, NA), c = c(0.20, NA, 0.10), stringsAsFactors = FALSE)

test_that("avec a, b et c : ln D = a + b ln H + c ln CPA, d130_source tarif_etage_b", {
  d <- d130_etage_b("09", h = 27, crown_area = 40, coef = coef_essai)
  expect_equal(d$d130, exp(0.10 + 1.12 * log(27) + 0.20 * log(40)))
  expect_equal(d$d130_source, "tarif_etage_b")
  # le houppier compte : un houppier plus grand donne un diamètre plus grand (c > 0)
  expect_gt(d130_etage_b("09", 27, 80, coef_essai)$d130, d$d130)
})

test_that("sans coefficient c : ln D = a + b ln H, d130_source tarif_etage_b_ifn, houppier ignoré", {
  d <- d130_etage_b(c("62", "62"), h = c(36, 36), crown_area = c(10, 90), coef = coef_essai)
  expect_equal(d$d130, rep(exp(0.20 + 1.08 * log(36)), 2))
  expect_equal(d$d130_source, c("tarif_etage_b_ifn", "tarif_etage_b_ifn"))
})

test_that("sans a ou sans b, ou essence absente : pas de d130, pas de source (aucune valeur par défaut)", {
  d <- d130_etage_b(c("64", "99"), c(20, 20), c(30, 30), coef_essai)  # 64 : b manque ; 99 : absente
  expect_true(all(is.na(d$d130)))
  expect_true(all(is.na(d$d130_source)))
  expect_equal(species_without_coefficients(c("09", "64", "99", "64"), coef_essai), c("64", "99"))
  expect_equal(species_without_coefficients(c("09", "62"), coef_essai), character())
})

test_that("les coefficients etage_b (a, b, c) sont lus dans allometry.parquet, essence en chaîne", {
  coef <- read_etage_b_coefficients(file.path(zone_fictive, "params", "allometry.parquet"))
  expect_true(is.character(coef$species))
  expect_equal(names(coef), c("species", "a", "b", "c"))
  expect_true(all(c("09", "03", "62") %in% coef$species))  # le zéro de tête est conservé
  expect_equal(coef$a[coef$species == "09"], 0.10)
  expect_equal(coef$b[coef$species == "09"], 1.12)
  # coefficient c fictif (synthétique, provisoire) du jeu fictif, pour chaque essence du jeu
  expect_equal(coef$c[coef$species == "09"], 0.20)
  expect_false(anyNA(coef$c))
})

test_that("un terme c absent d'une essence se lit NA ; un terme en double est refusé", {
  f <- tempfile(fileext = ".parquet")
  ligne <- function(sp, term, v) data.frame(species = sp, model = "etage_b", term = term, value = v,
                                            stringsAsFactors = FALSE)
  arrow::write_parquet(rbind(ligne("09", "a", 0.1), ligne("09", "b", 1.1), ligne("09", "c", 0.2),
                             ligne("62", "a", 0.2), ligne("62", "b", 1.0),
                             ligne("62", "a", 9)), f)   # 62 : a en double
  expect_error(read_etage_b_coefficients(f), "plusieurs coefficients a")
  arrow::write_parquet(rbind(ligne("09", "a", 0.1), ligne("09", "b", 1.1), ligne("09", "c", 0.2),
                             ligne("62", "a", 0.2), ligne("62", "b", 1.0)), f)
  coef <- read_etage_b_coefficients(f)
  expect_equal(coef$c, c(0.2, NA))
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

# Autonome : une racine temporaire reçoit les entrées du jeu fictif, ses paramètres, les biomes et
# le référentiel des essences ; le test y lance lui-même prepare, biomes, puis trees (comme
# test-biomes.R). Rien n'est lu dans les sorties versionnées du jeu fictif, rien n'y est écrit.
# Les variantes copient cette racine et en changent une entrée.

config_depot <- file.path(racine, "config.yml")

# Exécute `code` avec SYLVIGENESE_ROOT = `racine_tmp` et le vrai validateur, puis remet l'état.
avec_racine <- function(racine_tmp, code) {
  ancienne_racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = NA)
  ancien_validateur <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_ROOT = racine_tmp,
             SYLVIGENESE_VALIDATE = file.path(racine, "contracts", "validate"))
  on.exit({
    if (is.na(ancienne_racine)) Sys.unsetenv("SYLVIGENESE_ROOT") else Sys.setenv(SYLVIGENESE_ROOT = ancienne_racine)
    if (is.na(ancien_validateur)) Sys.unsetenv("SYLVIGENESE_VALIDATE") else Sys.setenv(SYLVIGENESE_VALIDATE = ancien_validateur)
  }, add = TRUE)
  force(code)
}

zone_de <- function(racine_tmp) file.path(racine_tmp, "tests", "fixtures", "zone_fictive")

# Racine temporaire : entrées et paramètres du jeu fictif, biomes, référentiel des essences.
nouvelle_racine <- function() {
  r <- tempfile("racine_")
  zone <- zone_de(r)
  dir.create(zone, recursive = TRUE)
  file.copy(file.path(zone_fictive, c("inputs", "params")), zone, recursive = TRUE)
  file.copy(file.path(racine, "biomes"), r, recursive = TRUE)
  dir.create(file.path(r, "contracts"))
  file.copy(file.path(racine, "contracts", "species.csv"), file.path(r, "contracts"))
  r
}

# Lance le module `f` en gardant les messages : rend list(status, messages).
lancer_avec_messages <- function(f, ...) {
  msgs <- character()
  status <- withCallingHandlers(
    f(...),
    message = function(m) { msgs <<- c(msgs, conditionMessage(m)); invokeRestart("muffleMessage") })
  list(status = status, messages = msgs)
}

# La chaîne, une fois : prepare, biomes (jeu fictif entier), puis le MNH est rogné à une fenêtre qui
# touche les cinq polygones et la forêt sans polygone (x 300-700, y 400-600 en mètres locaux) pour
# que trees reste court ; trees tourne par run_trees (code de sortie et validateur compris).
chaine <- local({
  cache <- NULL
  function() {
    if (!is.null(cache)) return(cache)
    r <- nouvelle_racine()
    zone <- zone_de(r)
    res <- avec_racine(r, {
      sp <- lancer_avec_messages(run_prepare, config_depot)
      sb <- lancer_avec_messages(run_biomes, config_depot)
      chm <- terra::rast(file.path(zone, "inputs", "chm.tif"))
      terra::writeRaster(terra::crop(chm, terra::ext(700300, 700700, 6500400, 6500600)),
                         file.path(zone, "inputs", "chm.tif"), overwrite = TRUE,
                         datatype = "FLT4S", NAflag = -9999)
      st <- lancer_avec_messages(run_trees, config_depot)
      list(prepare = sp$status, biomes = sb$status, trees = st$status, messages = st$messages)
    })
    cache <<- c(list(racine = r, zone = zone), res)
    cache
  }
})

# Copie de la racine de la chaîne, modifiée par `modif(zone)` ; rend (racine, zone).
variante <- function(modif = function(zone) NULL) {
  base <- chaine()
  r <- tempfile("variante_")
  dir.create(r)
  file.copy(list.files(base$racine, full.names = TRUE), r, recursive = TRUE)
  zone <- zone_de(r)
  modif(zone)
  list(racine = r, zone = zone)
}

lire_arbres <- function(zone) {
  read_parquet_tbl(file.path(zone, "trees_init", "trees.parquet"))
}

lire_rapport <- function(zone) {
  paste(readLines(file.path(zone, "rapport_arbres.html"), encoding = "UTF-8"), collapse = "\n")
}

# Coefficients etage_b du jeu fictif, modifiés par `modif(df)` (lignes species/model/term/value).
changer_allometrie <- function(zone, modif) {
  f <- file.path(zone, "params", "allometry.parquet")
  rows <- read_parquet_tbl(f)
  arrow::write_parquet(modif(rows), f)
}

test_that("la chaîne prepare, biomes, trees tourne toute seule dans une racine temporaire", {
  c0 <- chaine()
  expect_equal(c0$prepare, 0L)
  expect_equal(c0$biomes, 0L)
  expect_equal(c0$trees, 0L)
  expect_true(file.exists(file.path(c0$zone, "trees_init", "trees.parquet")))
  expect_true(file.exists(file.path(c0$zone, "rapport_arbres.html")))
  # le dépôt n'est pas touché : la racine est temporaire
  expect_false(identical(normalizePath(c0$zone), normalizePath(zone_fictive)))
})

test_that("trees_init/ passe le validateur des contrats, houppier compris", {
  z <- chaine()$zone
  avec_racine(chaine()$racine, {
    expect_silent(validate_file("prepare.trees_init", file.path(z, "trees_init")))
  })
  a <- lire_arbres(z)
  expect_true("crown_area" %in% names(a))
})

test_that("stands.parquet passe le validateur et reprend les cinq polygones aux noms de sylvigenese", {
  z <- chaine()$zone
  avec_racine(chaine()$racine, validate_file("prepare.stands", file.path(z, "stands.parquet")))
  s <- read_parquet_tbl(file.path(z, "stands.parquet"))
  expect_equal(sort(s$stand_id), c("S01", "S02", "S03", "S04", "S05"))
  expect_equal(s$species[s$stand_id == "S01"], "09")
  expect_equal(s$d130[s$stand_id == "S03"], 48)
  expect_equal(s$h[s$stand_id == "S03"], 36)
  expect_equal(s$source[s$stand_id == "S04"], "synthetic_ml")
})

test_that("chaque arbre porte une surface de houppier positive, en m², multiple de la maille", {
  a <- lire_arbres(chaine()$zone)
  expect_gt(nrow(a), 100)
  expect_true(all(is.finite(a$crown_area) & a$crown_area > 0 & a$crown_area < 400))
  # la surface est un nombre entier de cellules de 0,5 m x 0,5 m
  expect_equal(a$crown_area / 0.25, round(a$crown_area / 0.25))
})

test_that("chaque arbre porte ses deux sources, et l'essence suit le polygone ou la végétation", {
  a <- lire_arbres(chaine()$zone)
  expect_true(all(a$species_source %in% c("nemeton", "vegetation_type")))
  # le jeu fictif donne a, b et c à toutes ses essences : tous les d130 suivent le modèle du houppier
  expect_true(all(a$d130_source == "tarif_etage_b"))
  expect_equal(anyDuplicated(a$tree_id), 0L)
  # hors polygone (x 350-650, y 0-500 locaux) : essence dominante du type de végétation
  hors <- a$x >= 700350 & a$x < 700650 & a$y < 6500500
  expect_gt(sum(hors), 10)
  expect_true(all(a$species_source[hors] == "vegetation_type"))
  expect_equal(length(unique(a$species[hors])), 1L)
  # S03 (x 350-650, y 500-1000) : épicéa 62 de nemeton, plus haut que son plafond, non ramené
  s03 <- a$x >= 700350 & a$x < 700650 & a$y >= 6500500
  expect_gt(sum(s03), 10)
  expect_true(all(a$species[s03] == "62" & a$species_source[s03] == "nemeton"))
  expect_gt(median(a$h[s03]), 30)
})

test_that("le d130 écrit suit ln D = a + b ln H + c ln CPA avec les coefficients du fichier", {
  z <- chaine()$zone
  a <- lire_arbres(z)
  rows <- read_parquet_tbl(file.path(z, "params", "allometry.parquet"))
  rows <- rows[rows$model == "etage_b", ]
  terme <- function(t) rows$value[rows$term == t][match(a$species, rows$species[rows$term == t])]
  attendu <- exp(terme("a") + terme("b") * log(a$h) + terme("c") * log(a$crown_area))
  expect_false(anyNA(attendu))
  expect_equal(a$d130, attendu, tolerance = 1e-9)
})

test_that("les arbres sont dans la fenêtre, x est et y nord, sur un maximum du MNH", {
  z <- chaine()$zone
  a <- lire_arbres(z)
  expect_true(all(a$x >= 700300 & a$x <= 700700))
  expect_true(all(a$y >= 6500400 & a$y <= 6500600))
  chm <- terra::rast(file.path(z, "inputs", "chm.tif"))
  ref <- terra::extract(terra::focal(chm, w = 3L, fun = "max", na.rm = TRUE), cbind(a$x, a$y))[, 1]
  expect_equal(a$h, ref, tolerance = 1e-4)
})

test_that("le rapport dit mono-essence, synthetic_ml sans recompter le MNH, et les arbres hors polygone", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "mono-essence")
  expect_match(html, "S04 : source synthetic_ml")
  expect_match(html, "seconde fois")
  expect_match(html, "hors polygone nemeton")
})

test_that("le rapport dit que l'essence hors polygone est la plus grande part de la strate arborée, provisoire", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "plus grande part dans la strate arborée du type de végétation")
  expect_match(html, "règle PROVISOIRE")
})

test_that("le rapport dit que la hauteur n'est pas avancée jusqu'à t0, en attente de dynamics (M2)", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "n'est pas avancée jusqu'à t0")
  expect_match(html, "courbe de hauteur de dynamics \\(M2\\)")
  expect_match(html, "spec §4\\.4")
})

test_that("le rapport dit que l'inventaire vidéo est lu et validé mais pas utilisé en M1a", {
  z <- chaine()$zone
  html <- lire_rapport(z)
  expect_match(html, "inventaire vidéo")
  expect_match(html, "lu \\(placettes : 3, arbres : 88\\) et validé à l'entrée")
  expect_match(html, "PAS UTILISÉ en M1a")
  expect_false(any(c("inventaire_video") %in% c(lire_arbres(z)$species_source, lire_arbres(z)$d130_source)))
})

test_that("le rapport donne l'origine des paramètres de détection, avec URL, commit, fichier et lignes", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "https://github.com/pobsteta/tarif-nemeton", fixed = TRUE)
  expect_match(html, "0f51b9606165237b7cae2dda8809081adef869ac", fixed = TRUE)
  expect_match(html, "code/etage_b_arbres_lidar.R", fixed = TRUE)
  expect_match(html, "hauteur minimale 5 m : lmf\\(hmin = 5\\) à la l\\.18")
  expect_match(html, "médiane 3x3 cellules .* à la l\\.17")
  expect_match(html, "fenêtre de maximum local de 3 m .* croissant vers 5,6 m : f_ws à la l\\.13")
  expect_match(html, "PROVISOIRES")
})

test_that("le rapport dit le statut provisoire du houppier (réserve TLS contre MNH aéroporté)", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "le houppier est PROVISOIRE")
  expect_match(html, "TLS")
  expect_match(html, "surface projetée des houppiers \\(crown_area, m²\\) : minimum")
})

test_that("le rapport dit la règle des recouvrements de polygones, même sans recouvrement", {
  html <- lire_rapport(chaine()$zone)
  expect_match(html, "Recouvrements de polygones")
  expect_match(html, "le plus petit stand_id l'emporte")
})

# ------------------------------------------------------------------ variantes

test_that("sans carte de végétation, trees s'arrête avec une erreur explicite, rien n'est écrit", {
  v <- variante(function(zone) {
    unlink(file.path(zone, c("vegetation_map.tif", "vegetation_map.csv", "trees_init", "rapport_arbres.html")),
           recursive = TRUE)
  })
  r <- avec_racine(v$racine, lancer_avec_messages(run_trees, config_depot))
  expect_equal(r$status, 2L)
  expect_match(paste(r$messages, collapse = "\n"), "make biomes")
  expect_false(dir.exists(file.path(v$zone, "trees_init")))
  expect_false(file.exists(file.path(v$zone, "rapport_arbres.html")))
})

test_that("la carte de végétation est validée à l'entrée : désalignée sur la grille, elle est refusée", {
  v <- variante(function(zone) {
    unlink(file.path(zone, c("trees_init", "rapport_arbres.html")), recursive = TRUE)
    f <- file.path(zone, "vegetation_map.tif")
    decalee <- tempfile(fileext = ".tif")
    write_grid_raster(terra::shift(terra::rast(f), dx = 10), decalee, "INT2U")  # 10 m vers l'est
    file.copy(decalee, f, overwrite = TRUE)
  })
  r <- avec_racine(v$racine, lancer_avec_messages(run_trees, config_depot))
  expect_equal(r$status, 2L)
  expect_match(paste(r$messages, collapse = "\n"), "biomes.vegetation_map")
  expect_match(paste(r$messages, collapse = "\n"), "par le validateur \\(contrat biomes.vegetation_map")
  expect_false(dir.exists(file.path(v$zone, "trees_init")))
})

test_that("une essence sans coefficient c suit ln D = a + b ln H, et d130_source le distingue", {
  # 62 (S03) perd son coefficient c ; les autres essences gardent le houppier
  v <- variante(function(zone) {
    changer_allometrie(zone, function(rows) rows[!(rows$species == "62" & rows$term == "c"), ])
  })
  r <- avec_racine(v$racine, lancer_avec_messages(run_trees, config_depot))
  expect_equal(r$status, 0L)
  a <- lire_arbres(v$zone)
  sans_c <- a$species == "62"
  expect_gt(sum(sans_c), 10)
  expect_gt(sum(!sans_c), 100)
  expect_true(all(a$d130_source[sans_c] == "tarif_etage_b_ifn"))
  expect_true(all(a$d130_source[!sans_c] == "tarif_etage_b"))
  rows <- read_parquet_tbl(file.path(v$zone, "params", "allometry.parquet"))
  ab <- function(t) rows$value[rows$species == "62" & rows$term == t & rows$model == "etage_b"]
  expect_equal(a$d130[sans_c], exp(ab("a") + ab("b") * log(a$h[sans_c])), tolerance = 1e-9)
  expect_match(lire_rapport(v$zone), "d'essence sans coefficient c \\(ln D = a \\+ b ln H, d130_source = tarif_etage_b_ifn\\)")
})

test_that("une essence sans aucun coefficient arrête trees (code 2), nomme l'essence, n'écrit rien", {
  v <- variante(function(zone) {
    unlink(file.path(zone, c("trees_init", "rapport_arbres.html")), recursive = TRUE)
    changer_allometrie(zone, function(rows) rows[rows$species != "62", ])
  })
  r <- avec_racine(v$racine, lancer_avec_messages(run_trees, config_depot))
  expect_equal(r$status, 2L)
  msg <- paste(r$messages, collapse = "\n")
  expect_match(msg, "essence 62")
  expect_match(msg, "aucun coefficient")
  expect_false(dir.exists(file.path(v$zone, "trees_init")))
  expect_false(file.exists(file.path(v$zone, "trees_init.parquet")))
  expect_false(file.exists(file.path(v$zone, "rapport_arbres.html")))
})

test_that("une essence qui n'a que le coefficient c, sans a ni b, est aussi une erreur explicite", {
  v <- variante(function(zone) {
    unlink(file.path(zone, c("trees_init", "rapport_arbres.html")), recursive = TRUE)
    changer_allometrie(zone, function(rows) rows[!(rows$species == "62" & rows$term == "b"), ])
  })
  r <- avec_racine(v$racine, lancer_avec_messages(run_trees, config_depot))
  expect_equal(r$status, 2L)
  expect_match(paste(r$messages, collapse = "\n"), "essence 62 : aucun coefficient")
  expect_false(dir.exists(file.path(v$zone, "trees_init")))
})

test_that("deux polygones qui se recouvrent : le plus petit stand_id l'emporte, et le rapport le dit", {
  # S03b recouvre S03 exactement, avec une autre essence (61) : S03 (62) l'emporte, quel que soit
  # l'ordre dans le fichier (S03b écrit AVANT S03)
  v <- variante(function(zone) {
    unlink(file.path(zone, c("trees_init", "rapport_arbres.html")), recursive = TRUE)
    f <- file.path(zone, "inputs", "nemeton_stands.gpkg")
    s <- sf::st_read(f, layer = "stands", quiet = TRUE)
    doublon <- s[s$stand_id == "S03", ]
    doublon$stand_id <- "S03b"
    doublon$species_espar <- "61"
    sf::st_write(rbind(doublon, s), f, layer = "stands", delete_layer = TRUE, quiet = TRUE)
  })
  # le validateur de l'entrée ne voit pas ce fichier retouché : validate = FALSE, tout le reste est vrai
  avec_racine(v$racine, suppressMessages(prepare_trees(
    v$zone, cfg = list(), validate = FALSE, biomes_dir = file.path(v$racine, "biomes"),
    species_csv = file.path(v$racine, "contracts", "species.csv"))))
  a <- lire_arbres(v$zone)
  s03 <- a$x >= 700350 & a$x < 700650 & a$y >= 6500500
  expect_gt(sum(s03), 10)
  expect_true(all(a$species[s03] == "62"))
  html <- lire_rapport(v$zone)
  expect_match(html, "tombent dans plusieurs polygones nemeton qui se recouvrent")
  expect_match(html, "S03 et S03b : [0-9]+ arbre\\(s\\) ; essences différentes")
})

test_that("choose_polygon retient le plus petit stand_id, quel que soit l'ordre du fichier", {
  ids <- c("S10", "S02", "S03")
  hit <- list(integer(), c(1L, 2L, 3L), 3L, c(1L, 3L))
  p <- choose_polygon(hit, ids)
  # « S02 » < « S03 » < « S10 » par octets ; le dernier point est dans S10 et S03 : S03 l'emporte
  expect_equal(p$poly, c(NA, 2L, 3L, 3L))
  expect_equal(p$n_hits, c(0L, 3L, 1L, 2L))
})

test_that("le module sans validation écrit les mêmes arbres que la chaîne validée (déterministe)", {
  base <- chaine()
  v <- variante(function(zone) unlink(file.path(zone, c("trees_init", "rapport_arbres.html")), recursive = TRUE))
  avec_racine(v$racine, suppressMessages(prepare_trees(
    v$zone, cfg = list(), validate = FALSE, biomes_dir = file.path(v$racine, "biomes"),
    species_csv = file.path(v$racine, "contracts", "species.csv"))))
  expect_equal(lire_arbres(v$zone), lire_arbres(base$zone))
})

test_that("run_prepare : une essence nemeton de forme valide mais hors référentiel arrête le module avant toute écriture", {
  # « 99 » respecte le motif des codes espar (contrat inputs.nemeton_stands) mais n'est pas dans
  # contracts/species.csv : code 2, et ni grille, ni rasters, ni stand_map, ni ifn/, ni stands.parquet.
  r <- nouvelle_racine()
  zone <- zone_de(r)
  f <- file.path(zone, "inputs", "nemeton_stands.gpkg")
  s <- sf::st_read(f, layer = "stands", quiet = TRUE)
  expect_false("99" %in% read_species_codes(file.path(r, "contracts", "species.csv")))
  s$species_espar[1] <- "99"
  s$age_yr <- as.integer(s$age_yr)   # le contrat veut un entier ; seule l'essence change
  sf::st_write(s, f, layer = "stands", delete_layer = TRUE, quiet = TRUE)
  avant <- list.files(zone, recursive = TRUE, include.dirs = TRUE)
  res <- avec_racine(r, lancer_avec_messages(run_prepare, config_depot))
  expect_equal(res$status, 2L)
  expect_match(paste(res$messages, collapse = "\n"), "essence\\(s\\) hors de contracts/species.csv : 99")
  expect_equal(list.files(zone, recursive = TRUE, include.dirs = TRUE), avant)
  expect_false(any(file.exists(file.path(zone, c("grid.tif", "dtm.tif", "ser.tif", "h0.tif", "stand_map.tif",
                                                 "stands.parquet", "rapport_prepare.html", "ifn")))))
})
