# Tests du module dynamics (mission 025, R/dynamics.R). Lancés par `make test-r` depuis la racine.
# Données : un petit IFN synthétique écrit ici (aucune valeur écologique), en EPSG:2154, x vers
# l'est et y vers le nord, en mètres.

racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))

# ------------------------------------------------------------------ jeu synthétique

#' IFN synthétique : `n_plots` placettes revues 5 ans après, trois essences (03, 09, 62),
#' accroissement, morts, coupes, recrues et hauteurs tirés d'une loi connue.
fake_ifn <- function(n_plots = 48L, seed = 1L) {
  set.seed(seed)
  ids <- sprintf("%07d", 9100000L + seq_len(n_plots))
  x <- 700000 + stats::runif(n_plots, 0, 8000)
  y <- 6500000 + stats::runif(n_plots, 0, 6000)
  c1 <- 2015L + (seq_len(n_plots) %% 5L)
  d1 <- as.Date(sprintf("%d-09-15", c1))
  d2 <- d1 + round(365.25 * 5 + stats::runif(n_plots, -60, 60))
  trophic <- round(stats::runif(n_plots, 2.5, 6), 1)
  hyd <- stats::runif(n_plots, -1.5, 0)
  bio <- stats::runif(n_plots, -0.8, 0.5)
  ser <- ifelse(x < 704000, "H10", "H11")
  mk_plot <- function(v) {
    data.frame(plot_id = ids, campaign = if (v == 1) c1 else c1 + 5L, x = x, y = y,
               loc_precision_m = 700, source = "ifn", ser_code = ser, trophic = trophic,
               coarse_hydric_700m = hyd, coarse_bioclim_700m = bio, visit = as.integer(v),
               date_point = format(if (v == 1) d1 else d2),
               incident_nature = if (v == 1) 0L else NA_integer_,
               incident_intensity = if (v == 1) 0L else NA_integer_,
               harvest_5y = NA_character_,
               clearing_5y = if (v == 2) 0L else NA_integer_,
               planting_5y = if (v == 2) 0L else NA_integer_, stringsAsFactors = FALSE)
  }
  plots <- rbind(mk_plot(1), mk_plot(2))
  w_of <- function(d) ifelse(d * pi / 100 < 0.705, 88.42, ifelse(d * pi / 100 < 1.175, 39.29, 14.15))
  rows1 <- list(); rows2 <- list()
  for (i in seq_len(n_plots)) {
    n <- 15L
    sp <- sample(c("03", "09", "62"), n, replace = TRUE)
    d <- round(stats::runif(n, 8, 70), 1)
    w <- w_of(d)
    ba <- w * pi * (d / 200)^2
    bal <- vapply(d, function(di) sum(ba[d > di]), numeric(1))
    incr <- exp(-1.0 + 0.35 * log(d) - 0.015 * bal + 0.05 * trophic[i]) / 10 *
      stats::rgamma(n, shape = 8, rate = 8)
    ir5_1 <- ifelse(stats::runif(n) < 0.6, round(incr * 5 / 100, 5), NA)
    h <- round(1.3 + 30 * (1 - exp(-0.04 * d)) * stats::rgamma(n, 30, 30), 1)
    a <- as.character(seq_len(n))
    rows1[[i]] <- data.frame(plot_id = ids[i], campaign = c1[i], tree_id = a, species = sp, d130 = d,
                             h = h, weight_ha = w, veg_state = "0", veg_state_5y = NA_character_,
                             radial_incr_5y_m = ir5_1, stringsAsFactors = FALSE)
    p_dead <- 1 - exp(-exp(-4 + 0.04 * bal) * 5)
    u <- stats::runif(n)
    state <- ifelse(u < p_dead, "M", ifelse(u > 0.97, "6", "0"))
    d_2 <- ifelse(state == "0", round(d + 2 * incr * 5, 1), ifelse(state == "M", d, NA))
    ir5_2 <- ifelse(state == "0" & stats::runif(n) < 0.6, round(incr * 5 / 100, 5), NA)
    nr <- stats::rpois(1, 1.5)
    rec <- if (nr) data.frame(plot_id = ids[i], campaign = c1[i] + 5L, tree_id = as.character(n + seq_len(nr)),
                              species = sample(c("03", "09", "62"), nr, replace = TRUE),
                              d130 = round(stats::runif(nr, 7.6, 9.5), 1), h = NA_real_, weight_ha = 88.42,
                              veg_state = NA_character_, veg_state_5y = "0", radial_incr_5y_m = NA_real_,
                              stringsAsFactors = FALSE)
    rows2[[i]] <- rbind(data.frame(plot_id = ids[i], campaign = c1[i] + 5L, tree_id = a, species = sp,
                                   d130 = d_2, h = NA_real_, weight_ha = ifelse(is.na(d_2), NA, w_of(d_2)),
                                   veg_state = NA_character_, veg_state_5y = state,
                                   radial_incr_5y_m = ir5_2, stringsAsFactors = FALSE), rec)
  }
  trees <- rbind(do.call(rbind, rows1), do.call(rbind, rows2))
  list(trees = trees, plots = plots)
}

TREES_TYPES <- c(plot_id = "string", campaign = "int32", tree_id = "string", species = "string",
                 d130 = "float64", h = "float64", weight_ha = "float64", veg_state = "string",
                 veg_state_5y = "string", radial_incr_5y_m = "float64")
PLOTS_TYPES <- c(plot_id = "string", campaign = "int32", x = "float64", y = "float64",
                 loc_precision_m = "float64", source = "string", ser_code = "string",
                 trophic = "float64", coarse_hydric_700m = "float64", coarse_bioclim_700m = "float64",
                 visit = "int32", date_point = "string", incident_nature = "int32",
                 incident_intensity = "int32", harvest_5y = "string", clearing_5y = "int32",
                 planting_5y = "int32")

write_fake_zone <- function(ifn) {
  zone <- tempfile("zone_dyn_")
  dir.create(file.path(zone, "ifn"), recursive = TRUE)
  write_parquet_tbl(ifn$trees, file.path(zone, "ifn", "trees.parquet"), as.list(TREES_TYPES))
  write_parquet_tbl(ifn$plots, file.path(zone, "ifn", "plots.parquet"), as.list(PLOTS_TYPES))
  zone
}

species_ref <- function() dyn_species_ref(racine)

# Un seul lancement complet, partagé (il dure quelques secondes).
run_cache <- new.env()
full_run <- function() {
  if (is.null(run_cache$zone)) {
    zone <- write_fake_zone(fake_ifn())
    old <- setwd(racine); on.exit(setwd(old), add = TRUE)
    run_cache$res <- suppressMessages(dynamics_run(zone, zone = "essai", root = racine))
    run_cache$zone <- zone
  }
  run_cache
}

# ------------------------------------------------------------------ outils numériques

test_that("dyn_ncs est la spline cubique naturelle par les nœuds, bornée hors des nœuds", {
  xk <- c(1, 2.5, 4, 7, 10); yk <- c(0.3, -0.2, 0.5, 1.1, 0.7)
  ref <- stats::splinefun(xk, yk, method = "natural")
  x <- seq(1, 10, length.out = 97)
  expect_equal(dyn_ncs(xk, yk, x), ref(x), tolerance = 1e-12)
  expect_equal(dyn_ncs(xk, yk, c(-5, 0.99, 10.01, 50)), c(0.3, 0.3, 0.7, 0.7))
  expect_equal(dyn_ncs(c(0, 1), c(2, 4), 0.25), 2.5)
})

test_that("les valeurs aux nœuds relues redonnent predict.gam à 1e-10 (accroissement, Tweedie, SER)", {
  ifn <- fake_ifn(n_plots = 30L, seed = 3L)
  prep <- dyn_prepare_data(ifn$trees, ifn$plots)
  fit <- suppressWarnings(dyn_fit("growth", prep$growth))
  expect_true(any(vapply(fit$smooth, function(s) inherits(s, "random.effect"), logical(1))))
  rows <- dyn_export(fit)
  nd <- dyn_model_frame(prep$growth)
  eta <- dyn_eta(rows, nd)
  expect_equal(as.numeric(eta), as.numeric(stats::predict(fit, newdata = nd, type = "link")),
               tolerance = 1e-10)
  expect_true("tweedie_p" %in% rows$term)
  p <- rows$value[rows$term == "tweedie_p"]
  expect_true(p > 1 && p < 2)
})

test_that("les valeurs aux nœuds relues redonnent predict.gam à 1e-10 (mortalité, décalage log(dt))", {
  ifn <- fake_ifn(n_plots = 30L, seed = 4L)
  prep <- dyn_prepare_data(ifn$trees, ifn$plots)
  fit <- suppressWarnings(dyn_fit("mortality", prep$mortality))
  rows <- dyn_export(fit)
  nd <- dyn_model_frame(prep$mortality)
  eta <- as.numeric(dyn_eta(rows, nd))
  expect_equal(eta + log(nd$dt), as.numeric(stats::predict(fit, newdata = nd, type = "link")),
               tolerance = 1e-10)
  expect_equal(dyn_response("mortality", eta, nd$dt),
               as.numeric(stats::predict(fit, newdata = nd, type = "response")), tolerance = 1e-10)
})

test_that("un point du terrain tombe dans le bon bloc de 2 km (x est, y nord, EPSG:2154, m)", {
  # (701 999,9 ; 6 500 000,1) : colonne 350 (700 000 à 702 000), ligne 3250 (6 500 000 à 6 502 000)
  expect_equal(dyn_block_id(701999.9, 6500000.1), "350_3250")
  expect_equal(dyn_block_id(702000.0, 6500000.1), "351_3250")
  expect_equal(dyn_block_id(701999.9, 6499999.9), "350_3249")
  expect_identical(DYN_BLOCK_SIZE_M, 2000)
})

test_that("les plis : un bloc par pli jusqu'à 20, puis 10 plis tirés par la graine, sans toucher l'aléa global", {
  b <- sprintf("b%02d", c(3, 1, 2, 1))
  expect_equal(dyn_folds(b), c(3L, 1L, 2L, 1L))
  many <- sprintf("b%02d", 1:35)
  set.seed(99); avant <- stats::runif(1); set.seed(99)
  f1 <- dyn_folds(many); apres <- stats::runif(1)
  expect_equal(avant, apres)
  expect_identical(f1, dyn_folds(many))
  expect_setequal(unique(f1), 1:10)
})

test_that("surface terrière de la placette et des arbres plus gros, pondérées par weight_ha", {
  d <- c(10, 30, 50); w <- c(88.42, 39.29, 14.15)
  ba <- dyn_tree_ba(d, w)
  expect_equal(ba[1], 88.42 * pi * 0.05^2)
  expect_equal(dyn_bal(c("p", "p", "p"), d, ba), c(ba[2] + ba[3], ba[3], 0))
  expect_equal(dyn_bal(c("p", "q", "p"), d, ba), c(ba[3], 0, 0))
})

test_that("H_dom et d_dom : les 100 plus gros arbres par hectare, le dernier en partie", {
  r <- dyn_dominant(d130 = c(50, 40, 20), h = c(30, 26, 15), w = c(14.15, 39.29, 88.42))
  part <- 100 - 14.15 - 39.29
  expect_equal(r$h_dom, (14.15 * 30 + 39.29 * 26 + part * 15) / 100)
  expect_equal(r$d_dom, sqrt((14.15 * 2500 + 39.29 * 1600 + part * 400) / 100))
  expect_true(r$complete)
  expect_false(dyn_dominant(50, 30, 14.15)$complete)
})

test_that("VEGET5 se lit avec la nomenclature de la campagne : coupé, non retrouvé, perdu ne sont pas morts", {
  expect_equal(dyn_fate(c("0", "1", "M", "2", "6", "7", "N", "T", NA, "5"), 2021L),
               c("vivant", "vivant", "mort", "mort", "coupe", "coupe", "non_retrouve", "perdu",
                 "etat_absent", "hors_nomenclature"))
  expect_equal(dyn_fate(c("5", "C", "A", "6", "M"), 2012L),
               c("mort", "mort", "chablis_inconnu", "coupe", "hors_nomenclature"))
  expect_equal(dyn_fate(c("M", "A", "N", "7"), 2016L),
               c("mort", "chablis_inconnu", "non_retrouve", "hors_nomenclature"))
})

test_that("une essence sous le seuil prend son groupe, un groupe sous le seuil toutes les essences", {
  ref <- species_ref()
  d <- data.frame(species = c(rep("03", 120), rep("09", 30), rep("62", 20), rep("61", 10)))
  u <- dyn_units("growth", d, c("03", "09", "61", "62"), ref)
  expect_equal(u$unit, c("03", "feuillu", DYN_ALL_SPECIES, DYN_ALL_SPECIES))
  expect_equal(u$members[2], "03, 09")
  expect_equal(u$unit_count[3], 180)
})

# ------------------------------------------------------------------ règles d'ajustement (spec §6)

test_that("la population à risque retire les coupés et garde les morts ; les recrues sans poids sont signalées", {
  ifn <- fake_ifn(n_plots = 12L, seed = 5L)
  t <- ifn$trees
  i2 <- which(t$campaign > 2019L & t$veg_state_5y == "0" & as.integer(t$tree_id) <= 15L)[1:3]
  t$veg_state_5y[i2] <- c("6", "N", "T")
  t$d130[i2] <- NA; t$weight_ha[i2] <- NA; t$radial_incr_5y_m[i2] <- NA
  rec <- t[t$campaign > 2019L & as.integer(t$tree_id) > 15L, ][1, ]
  rec$tree_id <- "99"; rec$weight_ha <- NA
  t <- rbind(t, rec)
  prep <- dyn_prepare_data(t, ifn$plots)
  base <- dyn_prepare_data(ifn$trees, ifn$plots)
  fk <- prep$counts$fates_kept
  expect_equal(fk[["coupe"]] - base$counts$fates_kept[["coupe"]], 1)
  expect_equal(fk[["non_retrouve"]], 1)
  expect_equal(fk[["perdu"]], 1)
  expect_equal(nrow(prep$mortality), nrow(base$mortality) - 3L)
  expect_equal(sum(prep$mortality$dead), sum(base$mortality$dead))
  expect_equal(prep$counts$recruits_no_w_kept, 1L)
  expect_equal(prep$counts$recruit_cells_no_w, 1L)
  expect_equal(prep$counts$recruits_all, base$counts$recruits_all + 1L)
})

test_that("placettes à incident, défrichées, plantées ou sans station : écartées et comptées", {
  ifn <- fake_ifn(n_plots = 12L, seed = 6L)
  p <- ifn$plots
  p$incident_nature[p$plot_id == p$plot_id[1] & p$visit == 1L] <- 4L
  p$clearing_5y[p$plot_id == p$plot_id[2] & p$visit == 2L] <- 2L
  p$planting_5y[p$plot_id == p$plot_id[3] & p$visit == 2L] <- 1L
  p$coarse_hydric_700m[p$plot_id == p$plot_id[4]] <- NA
  prep <- dyn_prepare_data(ifn$trees, p)
  expect_equal(prep$counts$excl_inc_trav_rev, 3L)
  expect_equal(prep$counts$excl_no_station_rev, 1L)
  expect_equal(prep$counts$fit_rev, 8L)
  expect_false(any(p$plot_id[1:4] %in% c(prep$growth$plot_id, prep$mortality$plot_id,
                                          prep$recruitment$plot_id, prep$height$plot_id)))
})

test_that("intervalle : DATEPOINT des deux visites, sinon 5 ans nominal ; date impossible ou inversée refusée", {
  ifn <- fake_ifn(n_plots = 6L, seed = 7L)
  p <- ifn$plots
  prep <- dyn_prepare_data(ifn$trees, p)
  expect_equal(prep$counts$dt_nominal, 0L)
  expect_true(all(abs(prep$mortality$dt - 5) < 0.2))
  p0 <- p; p0$date_point[p0$visit == 2L][1] <- NA
  expect_equal(dyn_prepare_data(ifn$trees, p0)$counts$dt_nominal, 1L)
  pi_ <- p; pi_$date_point[1] <- "2015-02-31"
  expect_error(dyn_prepare_data(ifn$trees, pi_), "DATEPOINT impossible")
  pn <- p; pn$date_point[pn$visit == 2L][1] <- "2001-01-01"
  expect_error(dyn_prepare_data(ifn$trees, pn), "DATEPOINT incoh")
})

test_that("sans 2e visite, l'entrée est refusée", {
  ifn <- fake_ifn(n_plots = 6L, seed = 8L)
  p <- ifn$plots[ifn$plots$visit == 1L, ]
  t <- ifn$trees[ifn$trees$campaign %in% p$campaign & paste(ifn$trees$plot_id, ifn$trees$campaign) %in%
                   paste(p$plot_id, p$campaign), ]
  expect_error(dyn_prepare_data(t, p), "revisit")
})

test_that("Chapman-Richards : paramètres de nemeton cités, hêtre (Korf) signalé et non inventé", {
  cr <- dyn_chapman_richards(c("09", "62", "17C"), species_ref())
  r62 <- cr$rows[cr$rows$species == "62", ]
  expect_equal(r62$value[r62$term == "k"], 0.028)
  expect_equal(r62$value[r62$term == "A_class3"], 32)
  expect_true(all(grepl("nemeton bd6fbe5", r62$source)) && all(grepl("Seynave", r62$source)))
  expect_true(all(r62$provisoire))
  expect_false("09" %in% cr$rows$species)
  expect_match(cr$missing[["09"]], "Korf")
  expect_true("17C" %in% names(cr$missing))
})

# ------------------------------------------------------------------ module complet

test_that("dynamics écrit les quatre tables conformes et un rapport par essence", {
  r <- full_run()
  out <- dyn_output_paths(r$zone)
  expect_true(all(file.exists(out)))
  old <- setwd(racine); on.exit(setwd(old), add = TRUE)
  for (n in DYN_PARAMS) {
    expect_equal(call_validator(c(paste0("dynamics.", n), out[[n]])), 0L)
    t <- read_parquet_tbl(out[[n]])
    expect_gt(nrow(t), 0)
    expect_true(all(t$provisoire))
  }
  html <- paste(readLines(out[["report"]], encoding = "UTF-8"), collapse = "\n")
  expect_match(html, "Validation croisée spatiale par blocs")
  expect_match(html, "modèle nul")
  expect_match(html, "Limites connues")
  expect_false(grepl("\\b(NA|NaN|Inf)\\b", html))
  for (sp in c("03", "09", "62")) expect_match(html, sprintf("<td>%s</td>", sp))
})

test_that("sur la loi synthétique, l'accroissement et la hauteur battent le modèle nul en validation croisée", {
  r <- full_run()
  expect_lt(r$res$res$growth$pooled$error, r$res$res$growth$pooled$error_null)
  expect_lt(r$res$res$height$pooled$error, r$res$res$height$pooled$error_null)
})

test_that("deux lancements donnent des params identiques (reproductibilité)", {
  r <- full_run()
  out <- dyn_output_paths(r$zone)
  first <- lapply(DYN_PARAMS, function(n) read_parquet_tbl(out[[n]]))
  old <- setwd(racine); on.exit(setwd(old), add = TRUE)
  suppressMessages(dynamics_run(r$zone, zone = "essai", root = racine))
  second <- lapply(DYN_PARAMS, function(n) read_parquet_tbl(out[[n]]))
  expect_identical(first, second)
})

test_that("une entrée refusée ne laisse aucune sortie, même d'un lancement précédent", {
  r <- full_run()
  zone <- tempfile("zone_dyn_refus_")
  dir.create(zone)
  file.copy(file.path(r$zone, "ifn"), zone, recursive = TRUE)
  file.copy(file.path(r$zone, "params"), zone, recursive = TRUE)
  file.copy(file.path(r$zone, "rapport_dynamics.html"), zone)
  t <- read_parquet_tbl(file.path(zone, "ifn", "trees.parquet"))
  t$species[1] <- "ZZZ99"
  write_parquet_tbl(t, file.path(zone, "ifn", "trees.parquet"), as.list(TREES_TYPES))
  old <- setwd(racine); on.exit(setwd(old), add = TRUE)
  expect_error(dynamics_run(zone, root = racine), "ZZZ99")
  expect_false(any(file.exists(dyn_output_paths(zone))))
  unlink(file.path(zone, "ifn", "plots.parquet"))
  expect_error(dynamics_run(zone, root = racine), "plots")
})
