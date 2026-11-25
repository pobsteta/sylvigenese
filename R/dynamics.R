# Module dynamics : modèles de la dynamique des arbres ajustés sur l'IFN (mission 025).
#
# Étapes du BRIEF codées ici : §6 « Diamètre, mortalité, recrutement » (trois modèles par essence
# ou groupe d'essences, validation croisée spatiale par blocs, rapport par essence) et §6
# « Hauteur » points 1 et 2 (forme de la courbe de hauteur dominante par essence, hauteur d'un
# arbre d'après la hauteur dominante et son rang en diamètre). Règles d'ajustement : spec §5, §6
# (« Données d'ajustement ») et §11 (M2a). Colonnes IFN : docs/referentiels/ifn-dynamique.md.
#
# Entrées : ifn/trees.parquet, ifn/plots.parquet (prepare), contracts/species.csv (référentiel).
# Sorties : params/{growth,mortality,recruitment,height_curve}.parquet (contrat
# contracts/tables/params/dynamics_params.schema.json) et rapport_dynamics.html.
#
# Modèles (GAM additifs de mgcv, REML avec pénalité de sélection des termes, splines cubiques de
# régression `cr`, sans interaction) :
#   - growth_gam : accroissement radial annuel (cm/an) = IR5 × 100 / 5 ; Tweedie, lien log ;
#   - mortality_gam : mort naturelle entre les deux visites ; binomiale, lien cloglog, décalage
#     log(Δt) : dyn_p(mort en Δt ans) = 1 − exp(−exp(η) × Δt), exp(η) est le risque annuel ;
#   - recruitment_gam : recrues (C13 ≥ 0,235 m) en tiges/ha, par placette revue et essence ;
#     Tweedie, lien log, décalage log(Δt) : exp(η) en tiges/ha/an ;
#   - relative_height_gam : h / H_dom selon d130 / d_dom ; gaussienne, identité ;
#   - chapman_richards : H(t) = A (1 − exp(−k t))^p, paramètres lus dans nemeton (cités) ;
#   - korf (hêtre 09 seul) : hauteur dominante qui avance d'un an, forme de Bontemps et al. 2007,
#     paramètres lus dans nemeton (cités, décision de Pascal du 25/11/2026, mission 034).
#
# Représentation portable (décision du 25/11/2026, représentation A) : une spline `cr` de mgcv est
# une spline cubique naturelle sur ses nœuds. On écrit, pour chaque terme lisse, ses valeurs aux
# nœuds ; `dyn_ncs()` les relit par interpolation cubique naturelle, à l'identique de
# predict.gam (test à 1e-10). Hors des nœuds extrêmes, la variable est bornée au nœud extrême.
#
# Rien d'écologique n'est inventé ici : les seuils, la taille des blocs et la graine sont des
# réglages provisoires, écrits au rapport ; les coefficients viennent de l'ajustement (jeu fictif
# en M2a, donc sans valeur écologique) ou de nemeton (cité ligne à ligne).
# N'appelle que R/commun.R, R/config.R et R/validateur.R.

# ------------------------------------------------------------------ réglages (provisoires)

# Taille des blocs carrés de la validation croisée, en m (EPSG:2154). Provisoire : 2 km font
# environ trois fois la portée du floutage des coordonnées IFN (700 m) et dépassent le diamètre
# (1 400 m) du disque des valeurs `coarse_*_700m`. Ce n'est PAS une garantie d'indépendance : deux
# placettes de blocs voisins peuvent être à moins de 1 400 m et partager des mailles de station ;
# il n'y a pas de zone tampon en M2a (à revoir en M2b, sur la SER pilote).
DYN_BLOCK_SIZE_M <- 2000
# Au-delà de DYN_MAX_FOLDS blocs, ils sont répartis en DYN_GROUPED_FOLDS plis par la graine.
DYN_MAX_FOLDS <- 20L
DYN_GROUPED_FOLDS <- 10L
DYN_SEED <- 20261125L
# Effectif minimal pour ajuster une essence seule (provisoire) : arbres avec IR5 ; morts
# naturelles (10 événements par degré de liberté, Peduzzi et al. 1996, non relu) ; recrues ;
# arbres avec hauteur mesurée.
DYN_THRESHOLDS <- c(growth = 100, mortality = 40, recruitment = 30, height = 100)
DYN_NOMINAL_INTERVAL_Y <- 5
DYN_RECRUIT_C13_M <- 0.235
# Première campagne de 2e visite qui sert au recrutement : en 2010-2014 les revisites ne relèvent
# pas les nouveaux arbres (décision de Pascal du 25/11/2026, spec §6).
DYN_RECRUIT_FIRST_CAMPAIGN <- 2015L
DYN_HDOM_STEMS_HA <- 100
DYN_ALL_SPECIES <- "toutes_essences"
DYN_PARAMS <- c("growth", "mortality", "recruitment", "height_curve")
DYN_STATION_VARS <- c("trophic", "coarse_hydric_700m", "coarse_bioclim_700m")

DYN_MODELS <- list(
  growth = list(model = "growth_gam", label = "Accroissement radial annuel",
                vars = c("d130", "ba_plot", "bal", DYN_STATION_VARS), ser = TRUE,
                offset = FALSE, k = 5L, unit = "cm/an"),
  mortality = list(model = "mortality_gam", label = "Mortalité naturelle",
                   vars = c("d130", "ba_plot", "bal", DYN_STATION_VARS), ser = TRUE,
                   offset = TRUE, k = 4L, unit = "probabilité"),
  recruitment = list(model = "recruitment_gam", label = "Recrutement à 7,5 cm",
                     vars = c("ba_plot", "ba_species", DYN_STATION_VARS), ser = TRUE,
                     offset = TRUE, k = 4L, unit = "tiges/ha/an"),
  height = list(model = "relative_height_gam", label = "Hauteur relative (h / H_dom)",
                vars = c("rel_d"), ser = FALSE, offset = FALSE, k = 5L, unit = "sans unité")
)

dyn_family <- function(kind) {
  # La famille tw() de mgcv appelle ldTweedie() sans préfixe : mgcv doit être attaché.
  if (!"package:mgcv" %in% search()) suppressPackageStartupMessages(library(mgcv))
  switch(kind,
         growth = mgcv::tw(link = "log"),
         mortality = stats::binomial(link = "cloglog"),
         recruitment = mgcv::tw(link = "log"),
         height = stats::gaussian())
}

# Forme de Chapman-Richards de la hauteur dominante, lue dans nemeton (projet de Pascal, GPL-3),
# commit bd6fbe5, data-raw/site_index_curves.R, table `site_index_params` (asymptotes a1 à a5 par
# classe de fertilité, k, p) ; références telles que nemeton les cite. Transcription, pas de copie
# de code. FASY (hêtre) n'y est pas en Chapman-Richards mais en modèle de Korf (Bontemps et al.
# 2007) : voir DYN_KORF_NEMETON plus bas.
DYN_CR_SOURCE <- paste0("nemeton bd6fbe5 (https://github.com/pobsteta/nemeton, GPL-3), ",
                        "data-raw/site_index_curves.R, site_index_params")
DYN_CR_NEMETON <- data.frame(
  nemeton_code = c("QUPE", "QURO", "CASA", "PIAB", "ABAL", "PSME", "PISY", "PIPI", "POSP"),
  a1 = c(38, 36, 34, 42, 44, 50, 30, 30, 36),
  a2 = c(34, 32, 30, 38, 38, 44, 26, 26, 32),
  a3 = c(29, 27, 26, 32, 32, 37, 22, 22, 28),
  a4 = c(24, 22, 22, 26, 26, 30, 18, 18, 24),
  a5 = c(20, 18, 18, 20, 20, 24, 14, 14, 20),
  k = c(0.022, 0.020, 0.028, 0.028, 0.024, 0.032, 0.032, 0.045, 0.080),
  p = c(1.50, 1.50, 1.35, 1.30, 1.30, 1.30, 1.30, 1.20, 1.10),
  reference = c("Duplat et Tran-Ha 1997", "Duplat et Tran-Ha 1997",
                "mise à l'échelle d'après Dhôte (Dhôte et Hervé 2000)", "Seynave et al. 2005",
                "Vallet et Pérot 2011", "DSF/IRSTEA 2010", "Duplat 2001 (suite)",
                "Lemoine 1991 (Landes)", "CNPF 2013"),
  stringsAsFactors = FALSE
)
DYN_CR_NOT_TAKEN <- character()   # aucune essence de nemeton n'est laissée de côté pour sa forme

# Modèle de Korf du hêtre (FASY), forme récursive de Bontemps, Duplat, Hervé et Dhôte (2007),
# « Croissance en hauteur dominante du hêtre dans le Nord de la France », Rendez-Vous Techniques
# ONF, HS2, 39-47, annexe 2 (HAL hal-00823732), telle que nemeton la reprend (commit bd6fbe5,
# data-raw/site_index_curves.R, blocs `fasy_regions` et `build_fasy_block`) ; transcription des
# nombres, pas de copie de code. Deux régions chez nemeton : NO (nord-ouest) et NE (nord-est).
# `p_f_min` et `p_f_max` : fertilité de la classe 5 (la pire) et de la classe 1 (la meilleure),
# classes de nemeton réparties à pas égal entre les deux. t0 et H0 (âge et hauteur de départ de
# nemeton) servent à l'illustration du rapport seulement : le moteur part de h0.tif.
DYN_KORF_SOURCE <- paste0("nemeton bd6fbe5 (https://github.com/pobsteta/nemeton, GPL-3), data-raw/site_index_curves.R, ",
                          "fasy_regions (NO et NE) ; Bontemps et al. 2007, RFF HS2, annexe 2")
DYN_KORF_REGIONS <- data.frame(
  region = c("NO", "NE"),
  a = c(44.2, 68.7), b = c(0.032, 0.028), c = c(1.647, 0.823),
  t0 = c(6, 6), H0 = c(1.40, 1.35), p_f_min = c(0.29, 0.21), p_f_max = c(0.58, 0.53),
  stringsAsFactors = FALSE
)
DYN_KORF_NEMETON_CODES <- c("FASY")   # essences de nemeton à la forme de Korf (contracts/species.csv)
DYN_KORF_REF_AGE <- 100               # âge du point de référence de nemeton pour le hêtre (H(100), classe 3)
DYN_KORF_REF_H_CLASS3 <- 29.2         # m, point cité par nemeton (site_index_reference_points) : moyenne NO et NE

# ------------------------------------------------------------------ outils numériques

#' Spline cubique naturelle passant par (xk, yk), évaluée en x ; x est borné à [xk1, xkn].
#' C'est la relecture des valeurs aux nœuds d'une spline `cr` de mgcv (à reproduire en Rust).
dyn_ncs <- function(xk, yk, x) {
  n <- length(xk)
  if (n < 2L) stop("erreur interne : spline à moins de deux nœuds", call. = FALSE)
  h <- diff(xk)
  m <- numeric(n)
  if (n > 2L) {
    a <- matrix(0, n - 2L, n - 2L)
    r <- numeric(n - 2L)
    for (i in 2:(n - 1L)) {
      j <- i - 1L
      a[j, j] <- 2 * (h[i - 1L] + h[i])
      if (j > 1L) a[j, j - 1L] <- h[i - 1L]
      if (j < n - 2L) a[j, j + 1L] <- h[i]
      r[j] <- 6 * ((yk[i + 1L] - yk[i]) / h[i] - (yk[i] - yk[i - 1L]) / h[i - 1L])
    }
    m[2:(n - 1L)] <- solve(a, r)
  }
  xc <- pmin(pmax(x, xk[1L]), xk[n])
  i <- findInterval(xc, xk, rightmost.closed = TRUE, all.inside = TRUE)
  da <- xk[i + 1L] - xc
  db <- xc - xk[i]
  hi <- h[i]
  (m[i] * da^3 + m[i + 1L] * db^3) / (6 * hi) +
    (yk[i] / hi - m[i] * hi / 6) * da + (yk[i + 1L] / hi - m[i + 1L] * hi / 6) * db
}

#' Bloc de validation croisée d'un point (x est, y nord, EPSG:2154, en m) : « colonne_ligne ».
dyn_block_id <- function(x, y, size = DYN_BLOCK_SIZE_M) {
  sprintf("%d_%d", as.integer(floor(x / size)), as.integer(floor(y / size)))
}

#' Plis de la validation croisée : un bloc par pli jusqu'à `max_folds` blocs, sinon répartition
#' des blocs (triés) en `n_grouped` plis par une permutation tirée avec la graine.
dyn_folds <- function(blocks, max_folds = DYN_MAX_FOLDS, n_grouped = DYN_GROUPED_FOLDS,
                      seed = DYN_SEED) {
  ub <- sort(unique(blocks), method = "radix")
  if (length(ub) <= max_folds) return(match(blocks, ub))
  old <- if (exists(".Random.seed", envir = globalenv())) get(".Random.seed", envir = globalenv()) else NULL
  on.exit(if (!is.null(old)) assign(".Random.seed", old, envir = globalenv()), add = TRUE)
  set.seed(seed, kind = "Mersenne-Twister", normal.kind = "Inversion", sample.kind = "Rejection")
  fold_of_block <- rep_len(seq_len(n_grouped), length(ub))[sample.int(length(ub))]
  fold_of_block[match(blocks, ub)]
}

#' Surface terrière par hectare d'un arbre (m²/ha) : poids × π (d130 / 200)², d130 en cm.
dyn_tree_ba <- function(d130, weight_ha) weight_ha * pi * (d130 / 200)^2

#' Surface terrière des arbres strictement plus gros, dans le même groupe (placette et visite).
#' `ba` vaut NA pour un arbre qui ne compte pas dans la surface terrière.
dyn_bal <- function(group, d130, ba) {
  out <- rep(NA_real_, length(d130))
  for (ii in split(seq_along(d130), group)) {
    ok <- ii[!is.na(ba[ii]) & !is.na(d130[ii])]
    for (i in ii) {
      if (!is.na(d130[i])) out[i] <- sum(ba[ok][d130[ok] > d130[i]])
    }
  }
  out
}

#' Hauteur et diamètre dominants d'une placette : moyenne pondérée de la hauteur, et diamètre
#' quadratique moyen, des `stems` plus gros arbres par hectare (le dernier arbre compte pour la
#' part de son poids qui complète `stems`). Définition provisoire (spec §5 : l'estimateur de
#' typopeuplement reste à lire).
dyn_dominant <- function(d130, h, w, stems = DYN_HDOM_STEMS_HA) {
  o <- order(-d130, method = "radix")
  w <- w[o]
  before <- cumsum(w) - w
  take <- pmin(w, pmax(0, stems - before))
  sel <- take > 0
  list(h_dom = sum(take[sel] * h[o][sel]) / sum(take[sel]),
       d_dom = sqrt(sum(take[sel] * d130[o][sel]^2) / sum(take[sel])),
       complete = sum(w) >= stems)
}

#' Sort d'un arbre vivant à la 1re visite, d'après VEGET5 lu avec la nomenclature de la campagne
#' de la 2e visite (docs/referentiels/ifn-dynamique.md §4 ; metadonnees.csv l. 6075-6099).
#' Rend : vivant, mort, coupe, non_retrouve, perdu, chablis, etat_absent, hors_nomenclature.
#' « chablis » : code A de VEGET5 (campagnes 2010 à 2018), compté comme mort dans la mortalité
#' (décision de Pascal du 25/11/2026, spec §6).
dyn_fate <- function(code, campaign) {
  out <- rep("hors_nomenclature", length(code))
  set <- function(sel, codes, v) out[sel & code %in% codes] <<- v
  p19 <- campaign >= 2019
  p17 <- campaign >= 2017 & campaign <= 2018
  p15 <- campaign >= 2015 & campaign <= 2016
  p10 <- campaign >= 2010 & campaign <= 2014
  set(p19, c("0", "1"), "vivant"); set(p19, c("M", "2"), "mort"); set(p19, c("6", "7"), "coupe")
  set(p19, "N", "non_retrouve"); set(p19, "T", "perdu")
  set(p17, "0", "vivant"); set(p17, "M", "mort"); set(p17, c("6", "7"), "coupe")
  set(p17, "N", "non_retrouve"); set(p17, "T", "perdu"); set(p17, "A", "chablis")
  set(p15, "0", "vivant"); set(p15, "M", "mort"); set(p15, "6", "coupe")
  set(p15, "N", "non_retrouve"); set(p15, "A", "chablis")
  set(p10, "0", "vivant"); set(p10, c("5", "C"), "mort"); set(p10, "6", "coupe")
  set(p10, "A", "chablis")
  out[is.na(code)] <- "etat_absent"
  out
}

# ------------------------------------------------------------------ entrées

dyn_root <- function() Sys.getenv("SYLVIGENESE_ROOT", unset = ".")

dyn_species_ref <- function(root = dyn_root()) {
  path <- file.path(root, "contracts", "species.csv")
  check_input_file(path)
  utils::read.csv(path, colClasses = "character", encoding = "UTF-8", na.strings = "")
}

#' Lit ifn/trees.parquet et ifn/plots.parquet ; refuse (erreur) une entrée absente, une essence
#' hors référentiel, puis fait valider les deux tables par leurs contrats.
dyn_read_inputs <- function(zone_dir, species_ref, validate = TRUE) {
  paths <- c(trees = file.path(zone_dir, "ifn", "trees.parquet"),
             plots = file.path(zone_dir, "ifn", "plots.parquet"))
  for (n in names(paths)) {
    if (!file.exists(paths[[n]])) {
      stop(sprintf("entrée absente : ifn/%s.parquet (%s) ; lancer prepare d'abord", n, paths[[n]]),
           call. = FALSE)
    }
  }
  trees <- read_parquet_tbl(paths[["trees"]])
  plots <- read_parquet_tbl(paths[["plots"]])
  unknown <- setdiff(unique(trees$species), species_ref$espar)
  if (length(unknown)) {
    stop(sprintf("ifn/trees.parquet : essence (species) hors du référentiel contracts/species.csv : %s",
                 paste(sort(unknown), collapse = ", ")), call. = FALSE)
  }
  if (validate) {
    validate_file("prepare.ifn_trees", paths[["trees"]], what = "entrée")
    validate_file("prepare.ifn_plots", paths[["plots"]], what = "entrée")
  }
  list(trees = trees, plots = plots)
}

# ------------------------------------------------------------------ données d'ajustement

#' Applique les règles de spec §6 (« Données d'ajustement ») : jointure des visites, placettes
#' écartées, intervalle, population à risque, recrues, concurrence. Rend les quatre jeux
#' d'ajustement et les comptes du rapport. Refuse (erreur) : aucune 2e visite, DATEPOINT
#' impossible ou 2e visite non postérieure à la 1re.
dyn_prepare_data <- function(trees, plots) {
  cnt <- list()
  if (any(duplicated(plots[, c("plot_id", "visit")]))) {
    d <- plots$plot_id[duplicated(plots[, c("plot_id", "visit")])]
    stop(sprintf("ifn/plots.parquet : placette en double pour une même visite : %s",
                 paste(utils::head(unique(d), 5), collapse = ", ")), call. = FALSE)
  }
  p1 <- plots[plots$visit == 1L, , drop = FALSE]
  p2 <- plots[plots$visit == 2L, , drop = FALSE]
  p1 <- p1[order(p1$plot_id, method = "radix"), , drop = FALSE]
  revisited <- sort(intersect(p1$plot_id, p2$plot_id), method = "radix")
  cnt$plots_v1 <- nrow(p1)
  cnt$plots_v2_orphan <- length(setdiff(p2$plot_id, p1$plot_id))
  cnt$revisited <- length(revisited)
  if (!length(revisited)) {
    stop(paste0("ifn/plots.parquet : aucune placette revisitée (aucune 2e visite) ; la mortalité ",
                "et le recrutement ne peuvent pas être ajustés : entrée refusée"), call. = FALSE)
  }

  # DATEPOINT : une date impossible ou une 2e visite non postérieure à la 1re est refusée.
  dates <- as.Date(plots$date_point, format = "%Y-%m-%d")
  bad <- !is.na(plots$date_point) & is.na(dates)
  if (any(bad)) {
    stop(sprintf("ifn/plots.parquet : DATEPOINT impossible (%s, placette %s) : entrée refusée",
                 plots$date_point[bad][1], plots$plot_id[bad][1]), call. = FALSE)
  }
  d1 <- dates[plots$visit == 1L][match(revisited, p1$plot_id)]
  d2 <- dates[plots$visit == 2L][match(revisited, p2$plot_id)]
  dt <- as.numeric(d2 - d1) / 365.25
  neg <- which(!is.na(dt) & dt <= 0)
  if (length(neg)) {
    i <- neg[1]
    stop(sprintf(paste0("ifn/plots.parquet : DATEPOINT incohérente, la 2e visite de la placette %s ",
                        "(%s) n'est pas postérieure à la 1re (%s) : intervalle négatif ou nul, ",
                        "entrée refusée"), revisited[i], format(d2[i]), format(d1[i])), call. = FALSE)
  }
  cnt$dt_from_datepoint <- sum(!is.na(dt))
  cnt$dt_nominal <- sum(is.na(dt))
  cnt$dt_range <- if (any(!is.na(dt))) range(dt, na.rm = TRUE) else c(NA_real_, NA_real_)
  dt[is.na(dt)] <- DYN_NOMINAL_INTERVAL_Y
  dt_of <- stats::setNames(dt, revisited)
  camp2 <- p2$campaign[match(revisited, p2$plot_id)]
  camp1 <- p1$campaign[match(revisited, p1$plot_id)]
  cnt$campaign_gap_not5 <- sum(camp2 - camp1 != 5L)
  camp2_of <- stats::setNames(camp2, revisited)

  # Placettes écartées (spec §6, décision du 25/11/2026) et placettes sans station.
  ids <- p1$plot_id
  by_plot <- function(col, pred) {
    v <- tapply(pred(plots[[col]]), plots$plot_id, any)
    out <- as.logical(v[ids]); out[is.na(out)] <- FALSE; out
  }
  incident <- by_plot("incident_nature", function(v) !is.na(v) & v != 0L)
  travaux <- by_plot("clearing_5y", function(v) !is.na(v) & v >= 1L) |
    by_plot("planting_5y", function(v) !is.na(v) & v == 1L)
  harvest <- by_plot("harvest_5y", function(v) !is.na(v) & nzchar(v))
  station_ok <- stats::complete.cases(p1[, DYN_STATION_VARS])
  names(incident) <- names(travaux) <- names(harvest) <- names(station_ok) <- ids
  rev <- ids %in% revisited
  cnt$excl_incident_rev <- sum(incident & rev)
  cnt$excl_travaux_rev <- sum(travaux & rev)
  cnt$excl_inc_trav_rev <- sum((incident | travaux) & rev)
  cnt$excl_no_station_rev <- sum(!station_ok & !(incident | travaux) & rev)
  cnt$excl_all_rev <- sum((incident | travaux | !station_ok) & rev)
  cnt$excl_inc_trav_all <- sum(incident | travaux)
  cnt$excl_no_station_all <- sum(!station_ok)
  cnt$harvest_rev <- sum(harvest & rev)
  fit_plots <- ids[!(incident | travaux | !station_ok)]
  fit_rev <- intersect(fit_plots, revisited)
  cnt$fit_plots <- length(fit_plots)
  cnt$fit_rev <- length(fit_rev)
  # Plage de campagnes de 2e visite de chaque modèle (décision de Pascal du 25/11/2026, spec §6) :
  # la mortalité sert toutes les revisites ; le recrutement seulement celles de 2015 et après.
  fit_rec <- fit_rev[camp2_of[fit_rev] >= DYN_RECRUIT_FIRST_CAMPAIGN]
  cnt$fit_rec <- length(fit_rec)
  cnt$rec_excluded_plots <- length(fit_rev) - length(fit_rec)
  rng <- function(ids) if (length(ids)) range(camp2_of[ids]) else c(NA_integer_, NA_integer_)
  cnt$camp2_range_mortality <- rng(fit_rev)
  cnt$camp2_range_recruitment <- rng(fit_rec)
  if (!length(fit_rec)) {
    stop(sprintf(paste0("ifn/plots.parquet : aucune placette retenue revue en %d ou après ; le ",
                        "recrutement ne peut pas être ajusté (les revisites de 2010 à 2014 ne servent ",
                        "qu'à la mortalité, spec §6) : entrée refusée"), DYN_RECRUIT_FIRST_CAMPAIGN),
         call. = FALSE)
  }
  ser_values <- p1$ser_code[match(fit_plots, p1$plot_id)]
  cnt$ser_levels <- sort(unique(ser_values[!is.na(ser_values)]), method = "radix")
  cnt$ser_missing <- sum(is.na(ser_values))

  station <- p1[, c("plot_id", "x", "y", "ser_code", DYN_STATION_VARS)]
  station$block <- dyn_block_id(station$x, station$y)

  # Arbres : visite, concurrence par placette et visite.
  pk <- paste(plots$plot_id, plots$campaign)
  tk <- paste(trees$plot_id, trees$campaign)
  vis <- plots$visit[match(tk, pk)]
  if (anyNA(vis)) {
    stop(sprintf(paste0("ifn/trees.parquet : %d ligne(s) sans placette (plot_id, campaign) dans ",
                        "ifn/plots.parquet ; première : placette %s, campagne %s"),
                 sum(is.na(vis)), trees$plot_id[is.na(vis)][1], trees$campaign[is.na(vis)][1]),
         call. = FALSE)
  }
  trees$visit <- vis
  trees <- trees[order(trees$plot_id, trees$visit, trees$tree_id, method = "radix"), , drop = FALSE]
  state <- ifelse(trees$visit == 1L, trees$veg_state, trees$veg_state_5y)
  trees$alive <- !is.na(state) & state == "0"
  trees$ba_tree <- ifelse(trees$alive, dyn_tree_ba(trees$d130, trees$weight_ha), NA_real_)
  cnt$alive_no_weight <- sum(trees$alive & is.na(trees$weight_ha))
  grp <- paste(trees$plot_id, trees$visit)
  ba_plot <- tapply(ifelse(is.na(trees$ba_tree), 0, trees$ba_tree), grp, sum)
  trees$ba_plot <- as.numeric(ba_plot[grp])
  trees$bal <- dyn_bal(grp, trees$d130, trees$ba_tree)
  trees$key <- paste(trees$plot_id, trees$tree_id, sep = "|")
  st <- station[match(trees$plot_id, station$plot_id), c("ser_code", DYN_STATION_VARS, "block")]
  for (n in names(st)) trees[[n]] <- st[[n]]
  t1 <- trees[trees$visit == 1L, , drop = FALSE]
  t2 <- trees[trees$visit == 2L, , drop = FALSE]

  # Accroissement : IR5 sur toute ligne vivante qui l'a, placettes retenues (les deux visites).
  g <- trees[trees$alive & !is.na(trees$radial_incr_5y_m) & !is.na(trees$d130) &
               trees$plot_id %in% fit_plots, , drop = FALSE]
  g$y <- g$radial_incr_5y_m * 100 / 5
  growth <- g[, c("plot_id", "block", "species", "y", "d130", "ba_plot", "bal", "ser_code",
                  DYN_STATION_VARS)]
  cnt$ir5_lines <- sum(!is.na(trees$radial_incr_5y_m))

  # Contrôle IR5 / différence de C13 : arbres vivants aux deux visites, IR5 de la 2e visite.
  m12 <- match(t1$key, t2$key)
  both <- t1$alive & !is.na(m12)
  t2m <- t2[m12[both], , drop = FALSE]
  t1b <- t1[both, , drop = FALSE]
  ctl <- t2m$alive & !is.na(t2m$radial_incr_5y_m) & !is.na(t2m$d130) & !is.na(t1b$d130)
  ctl_dt <- dt_of[t1b$plot_id[ctl]]
  cnt$ctl <- list(n = sum(ctl), ir5 = t2m$radial_incr_5y_m[ctl] * 100 / 5,
                  c13 = (t2m$d130[ctl] - t1b$d130[ctl]) / 2 / ctl_dt)

  # Mortalité : vivants (VEGET = 0) à la 1re visite sur placette revue.
  risk <- t1[t1$alive & t1$plot_id %in% revisited, , drop = FALSE]
  j <- match(risk$key, t2$key)
  code5 <- t2$veg_state_5y[j]
  camp5 <- t2$campaign[j]
  fate <- dyn_fate(code5, ifelse(is.na(camp5), 0L, camp5))
  fate[is.na(j)] <- "sans_ligne_2e_visite"
  risk$fate <- fate
  kept <- risk$plot_id %in% fit_plots
  cnt$fates_all <- table(factor(fate, levels = dyn_fate_levels()))
  cnt$fates_kept <- table(factor(fate[kept], levels = dyn_fate_levels()))
  # Les chablis (code A) comptent comme morts (décision de Pascal du 25/11/2026).
  at_risk <- fate %in% c("vivant", "mort", "chablis")
  m <- risk[kept & at_risk & !is.na(risk$d130), , drop = FALSE]
  cnt$risk_no_d130 <- sum(kept & at_risk & is.na(risk$d130))
  m$dead <- as.integer(m$fate %in% c("mort", "chablis"))
  m$dt <- as.numeric(dt_of[m$plot_id])
  mortality <- m[, c("plot_id", "block", "species", "dead", "dt", "d130", "ba_plot", "bal",
                     "ser_code", DYN_STATION_VARS)]

  # Recrutement : lignes de 2e visite sans 1re visite, recensables (C13 >= 0,235 m).
  rc <- t2[t2$plot_id %in% revisited & !(t2$key %in% t1$key), , drop = FALSE]
  c13 <- rc$d130 * pi / 100
  rec_ok <- !is.na(c13) & c13 >= DYN_RECRUIT_C13_M - 1e-9
  rc_kept <- rc$plot_id %in% fit_rec
  cnt$recruits_old_campaign <- sum(rec_ok & rc$plot_id %in% fit_rev & !(rc$plot_id %in% fit_rec))
  cnt$recruits_all <- sum(rec_ok)
  cnt$recruits_kept <- sum(rec_ok & rc_kept)
  cnt$recruits_below <- sum(!rec_ok & !is.na(c13))
  cnt$recruits_no_c13 <- sum(is.na(c13))
  cnt$recruits_no_w_all <- sum(rec_ok & is.na(rc$weight_ha))
  cnt$recruits_no_w_kept <- sum(rec_ok & rc_kept & is.na(rc$weight_ha))
  rr <- rc[rec_ok & rc_kept, , drop = FALSE]
  all_species <- sort(unique(trees$species), method = "radix")
  cells <- expand.grid(species = all_species, plot_id = fit_rec, stringsAsFactors = FALSE)
  cells <- cells[, c("plot_id", "species")]
  ck <- paste(cells$plot_id, cells$species)
  rk <- paste(rr$plot_id, rr$species)
  cells$y <- as.numeric(tapply(rr$weight_ha, factor(rk, levels = ck), function(v) sum(v)))
  cells$y[is.na(cells$y) & !(ck %in% rk)] <- 0
  cells$n_recruits <- as.integer(table(factor(rk, levels = ck)))
  no_w <- is.na(cells$y)
  cnt$recruit_cells_no_w <- sum(no_w)
  cells <- cells[!no_w, , drop = FALSE]
  v1 <- t1[t1$plot_id %in% fit_rec, , drop = FALSE]
  cells$ba_plot <- as.numeric(tapply(ifelse(is.na(v1$ba_tree), 0, v1$ba_tree), v1$plot_id, sum)[cells$plot_id])
  ba_sp <- tapply(ifelse(is.na(v1$ba_tree), 0, v1$ba_tree), paste(v1$plot_id, v1$species), sum)
  cells$ba_species <- as.numeric(ba_sp[paste(cells$plot_id, cells$species)])
  cells$ba_species[is.na(cells$ba_species)] <- 0
  cells$ba_plot[is.na(cells$ba_plot)] <- 0
  cells$dt <- as.numeric(dt_of[cells$plot_id])
  st <- station[match(cells$plot_id, station$plot_id), c("ser_code", DYN_STATION_VARS, "block")]
  for (n in names(st)) cells[[n]] <- st[[n]]
  recruitment <- cells[, c("plot_id", "block", "species", "y", "n_recruits", "dt", "ba_plot",
                           "ba_species", "ser_code", DYN_STATION_VARS)]

  # Hauteur relative : vivants de 1re visite à hauteur mesurée, placettes retenues.
  hh <- t1[t1$alive & !is.na(t1$h) & !is.na(t1$d130) & !is.na(t1$weight_ha) &
             t1$plot_id %in% fit_plots, , drop = FALSE]
  dom <- lapply(split(seq_len(nrow(hh)), hh$plot_id), function(ii) {
    r <- dyn_dominant(hh$d130[ii], hh$h[ii], hh$weight_ha[ii])
    data.frame(plot_id = hh$plot_id[ii[1]], h_dom = r$h_dom, d_dom = r$d_dom, complete = r$complete)
  })
  dom <- do.call(rbind, c(list(data.frame(plot_id = character(), h_dom = numeric(),
                                          d_dom = numeric(), complete = logical())), dom))
  cnt$hdom_incomplete <- sum(!dom$complete)
  di <- match(hh$plot_id, dom$plot_id)
  hh$y <- hh$h / dom$h_dom[di]
  hh$rel_d <- hh$d130 / dom$d_dom[di]
  height <- hh[, c("plot_id", "block", "species", "y", "rel_d", "d130", "h")]

  list(growth = growth, mortality = mortality, recruitment = recruitment, height = height,
       counts = cnt, species = all_species, trees = trees)
}

dyn_fate_levels <- function() {
  c("vivant", "mort", "coupe", "non_retrouve", "perdu", "chablis", "etat_absent",
    "hors_nomenclature", "sans_ligne_2e_visite")
}

# ------------------------------------------------------------------ essences et groupes

#' Effectif d'une essence dans un jeu d'ajustement, au sens du seuil du modèle.
dyn_species_count <- function(kind, data) {
  v <- switch(kind,
              growth = rep(1, nrow(data)),
              mortality = data$dead,
              recruitment = data$n_recruits,
              height = rep(1, nrow(data)))
  tapply(v, factor(data$species), sum)
}

#' Unités d'ajustement : l'essence seule si elle atteint le seuil ; sinon le groupe de
#' contracts/species.csv (feuillu, resineux), ajusté sur toutes les essences du groupe s'il
#' l'atteint ; sinon toutes les essences. Rend un data.frame (species, unit, unit_type, members,
#' count, unit_count).
dyn_units <- function(kind, data, species, species_ref, threshold = DYN_THRESHOLDS[[kind]]) {
  cs <- dyn_species_count(kind, data)
  count <- as.numeric(cs[species]); count[is.na(count)] <- 0
  group <- species_ref$groupe[match(species, species_ref$espar)]
  gcount <- tapply(count, group, sum)
  out <- data.frame(species = species, count = count, group = group, stringsAsFactors = FALSE)
  out$unit <- ifelse(count >= threshold, species,
                     ifelse(gcount[group] >= threshold, group, DYN_ALL_SPECIES))
  out$unit_type <- ifelse(out$unit == species, "essence", "groupe")
  out$unit_count <- ifelse(out$unit_type == "essence", count,
                           ifelse(out$unit == DYN_ALL_SPECIES, sum(count), gcount[group]))
  out$members <- vapply(seq_len(nrow(out)), function(i) {
    u <- out$unit[i]
    m <- if (out$unit_type[i] == "essence") u else if (u == DYN_ALL_SPECIES) species else species[group == u]
    paste(m, collapse = ", ")
  }, character(1))
  out
}

dyn_unit_rows <- function(data, units, unit) {
  members <- strsplit(units$members[units$unit == unit][1], ", ", fixed = TRUE)[[1]]
  data[data$species %in% members, , drop = FALSE]
}

# ------------------------------------------------------------------ ajustement et export

#' Formule d'un modèle sur ses données : un terme `cr` par variable continue qui a au moins quatre
#' valeurs distinctes (k borné par leur nombre moins un), un effet aléatoire de SER s'il y en a au
#' moins deux et qu'aucune n'est vide, et le décalage log(dt). Rend la formule et les variables
#' laissées de côté.
dyn_formula <- function(kind, data) {
  spec <- DYN_MODELS[[kind]]
  terms <- character()
  dropped <- character()
  for (v in spec$vars) {
    nu <- length(unique(data[[v]][!is.na(data[[v]])]))
    if (nu >= 4L) {
      terms <- c(terms, sprintf("s(%s, bs = \"cr\", k = %d)", v, min(spec$k, nu - 1L)))
    } else {
      dropped <- c(dropped, v)
    }
  }
  if (spec$ser) {
    lv <- unique(data$ser_code)
    if (!anyNA(lv) && length(lv) >= 2L) terms <- c(terms, "s(ser_code, bs = \"re\")")
    else dropped <- c(dropped, "ser_code")
  }
  if (spec$offset) terms <- c(terms, "offset(log(dt))")
  resp <- if (kind == "mortality") "dead" else "y"
  rhs <- if (length(terms)) paste(terms, collapse = " + ") else "1"
  list(formula = stats::as.formula(paste(resp, "~", rhs), env = globalenv()), dropped = dropped)
}

dyn_model_frame <- function(data) {
  if ("ser_code" %in% names(data)) {
    data$ser_code <- factor(data$ser_code, levels = sort(unique(data$ser_code), method = "radix"))
  }
  data
}

#' Ajuste un modèle (mgcv, REML) ; rend l'objet gam et les variables laissées de côté.
dyn_fit <- function(kind, data) {
  f <- dyn_formula(kind, data)
  data <- dyn_model_frame(data)
  fit <- mgcv::gam(f$formula, family = dyn_family(kind), data = data, method = "REML", select = TRUE)
  attr(fit, "dropped") <- f$dropped
  attr(fit, "data") <- data
  fit
}

#' Ajuste un modèle sans taire mgcv : rend l'ajustement (ou l'erreur), le nombre d'avertissements,
#' leurs textes, et si l'ajustement a convergé (gam$converged et outer.info$conv).
dyn_fit_logged <- function(kind, data) {
  warns <- character()
  fit <- tryCatch(withCallingHandlers(dyn_fit(kind, data), warning = function(w) {
    warns <<- c(warns, conditionMessage(w))
    invokeRestart("muffleWarning")
  }), error = function(e) e)
  ok <- !inherits(fit, "error")
  conv <- ok && isTRUE(fit$converged) &&
    (is.null(fit$outer.info$conv) || identical(fit$outer.info$conv, "full convergence"))
  list(fit = fit, ok = ok, converged = conv, warnings = warns)
}

#' Lignes de paramètres d'un ajustement (représentation A) : intercept, valeurs de chaque terme
#' lisse à ses nœuds, valeur de chaque niveau de SER, dispersion et puissance Tweedie.
#' Colonnes : term, variable, x, value.
dyn_export <- function(fit) {
  data <- attr(fit, "data")
  base <- data[1L, , drop = FALSE]
  rows <- list(data.frame(term = "intercept", variable = NA_character_, x = NA_real_,
                          value = unname(stats::coef(fit)[["(Intercept)"]]), stringsAsFactors = FALSE))
  for (sm in fit$smooth) {
    v <- sm$term
    if (inherits(sm, "cr.smooth")) {
      xk <- sm$xp
      nd <- base[rep(1L, length(xk)), , drop = FALSE]
      nd[[v]] <- xk
      tv <- stats::predict(fit, newdata = nd, type = "terms")[, sm$label]
      rows[[length(rows) + 1L]] <- data.frame(
        term = sprintf("s(%s)[%02d]", v, seq_along(xk)), variable = v, x = xk,
        value = unname(tv), stringsAsFactors = FALSE)
    } else if (inherits(sm, "random.effect")) {
      lv <- levels(data[[v]])
      nd <- base[rep(1L, length(lv)), , drop = FALSE]
      nd[[v]] <- factor(lv, levels = lv)
      tv <- stats::predict(fit, newdata = nd, type = "terms")[, sm$label]
      rows[[length(rows) + 1L]] <- data.frame(
        term = paste0(v, "=", lv), variable = v, x = NA_real_, value = unname(tv),
        stringsAsFactors = FALSE)
    } else {
      stop(sprintf("erreur interne : terme %s non exportable", sm$label), call. = FALSE)
    }
  }
  rows[[length(rows) + 1L]] <- data.frame(term = "scale", variable = NA_character_, x = NA_real_,
                                          value = fit$sig2, stringsAsFactors = FALSE)
  if (grepl("^Tweedie", fit$family$family)) {
    rows[[length(rows) + 1L]] <- data.frame(term = "tweedie_p", variable = NA_character_,
                                            x = NA_real_, value = fit$family$getTheta(TRUE),
                                            stringsAsFactors = FALSE)
  }
  do.call(rbind, rows)
}

#' Prédicteur linéaire η relu depuis les lignes de paramètres (sans décalage). Un niveau de SER
#' absent des paramètres compte pour 0 et est compté dans l'attribut « unseen_ser ».
dyn_eta <- function(rows, newdata) {
  eta <- rep(rows$value[rows$term == "intercept"], nrow(newdata))
  sm <- rows[!is.na(rows$variable) & !is.na(rows$x), , drop = FALSE]
  for (v in unique(sm$variable)) {
    r <- sm[sm$variable == v, , drop = FALSE]
    r <- r[order(r$x), , drop = FALSE]
    eta <- eta + dyn_ncs(r$x, r$value, newdata[[v]])
  }
  lv <- rows[!is.na(rows$variable) & is.na(rows$x), , drop = FALSE]
  unseen <- 0L
  if (nrow(lv)) {
    val <- lv$value[match(paste0("ser_code=", as.character(newdata$ser_code)), lv$term)]
    unseen <- sum(is.na(val))
    val[is.na(val)] <- 0
    eta <- eta + val
  }
  attr(eta, "unseen_ser") <- unseen
  eta
}

#' Réponse du modèle : accroissement (cm/an), probabilité de mort sur dt, recrues (tiges/ha/an),
#' hauteur relative.
dyn_response <- function(kind, eta, dt = NULL) {
  switch(kind,
         growth = exp(eta),
         mortality = 1 - exp(-exp(eta) * dt),
         recruitment = exp(eta),
         height = eta)
}

#' Valeur observée comparée à la prédiction.
dyn_observed <- function(kind, data) {
  switch(kind,
         growth = data$y,
         mortality = data$dead,
         recruitment = data$y / data$dt,
         height = data$y)
}

#' Modèle nul ajusté sur `train`, prédit sur `test` : moyenne (accroissement, hauteur), taux
#' constant (recrutement : somme des tiges sur somme des années), risque annuel constant
#' (mortalité : binomiale cloglog avec le même décalage).
dyn_null <- function(kind, train, test) {
  switch(kind,
         growth = rep(mean(train$y), nrow(test)),
         height = rep(mean(train$y), nrow(test)),
         recruitment = rep(sum(train$y) / sum(train$dt), nrow(test)),
         mortality = {
           if (sum(train$dead) == 0) rep(0, nrow(test)) else {
             g <- stats::glm(dead ~ 1, offset = log(dt), family = stats::binomial(link = "cloglog"),
                             data = train)
             1 - exp(-exp(unname(stats::coef(g)[1])) * test$dt)
           }
         })
}

#' Validation croisée spatiale par blocs d'une unité : chaque pli est mis de côté, le modèle et le
#' modèle nul sont ajustés sur le reste, puis prédits sur le pli par la relecture des paramètres
#' (celle de simulate). Rend les prédictions, les plis échoués et les niveaux de SER inconnus.
dyn_cv <- function(kind, data, fold_of_block) {
  pred <- rep(NA_real_, nrow(data))
  null <- rep(NA_real_, nrow(data))
  fold <- fold_of_block[data$block]
  failed <- 0L
  unseen <- 0L
  not_conv <- 0L
  warns <- character()
  for (f in sort(unique(fold))) {
    test <- fold == f
    train <- data[!test, , drop = FALSE]
    if (!nrow(train)) { failed <- failed + 1L; next }
    lf <- dyn_fit_logged(kind, train)
    warns <- c(warns, lf$warnings)
    if (!lf$ok) { failed <- failed + 1L; next }
    if (!lf$converged) not_conv <- not_conv + 1L
    fit <- lf$fit
    rows <- dyn_export(fit)
    eta <- dyn_eta(rows, data[test, , drop = FALSE])
    unseen <- unseen + attr(eta, "unseen_ser")
    pred[test] <- dyn_response(kind, eta, data$dt[test])
    null[test] <- dyn_null(kind, train, data[test, , drop = FALSE])
  }
  list(pred = pred, null = null, failed = failed, unseen = unseen, not_converged = not_conv,
       warnings = warns, n_folds = length(unique(fold)))
}

#' Biais (prédit − observé), erreur et erreur du modèle nul. Erreur : RMSE ; pour la mortalité,
#' log-perte moyenne (et score de Brier).
dyn_metrics <- function(kind, obs, pred, null) {
  ok <- !is.na(pred) & !is.na(null) & !is.na(obs)
  o <- obs[ok]; p <- pred[ok]; q <- null[ok]
  if (!length(o)) return(list(n_pred = 0L, bias = NA_real_, error = NA_real_, error_null = NA_real_,
                              brier = NA_real_, brier_null = NA_real_))
  if (kind == "mortality") {
    eps <- 1e-12
    ll <- function(pp) { pp <- pmin(pmax(pp, eps), 1 - eps); -mean(o * log(pp) + (1 - o) * log(1 - pp)) }
    list(n_pred = length(o), bias = mean(p - o), error = ll(p), error_null = ll(q),
         brier = mean((p - o)^2), brier_null = mean((q - o)^2))
  } else {
    list(n_pred = length(o), bias = mean(p - o), error = sqrt(mean((p - o)^2)),
         error_null = sqrt(mean((q - o)^2)), brier = NA_real_, brier_null = NA_real_)
  }
}

#' Ajuste un modèle pour toutes ses unités, avec validation croisée. Rend les lignes de params,
#' le tableau par essence et le résumé.
dyn_run_model <- function(kind, data, species, species_ref, fold_of_block, source) {
  units <- dyn_units(kind, data, species, species_ref)
  spec <- DYN_MODELS[[kind]]
  params <- list()
  per_species <- list()
  unit_info <- list()
  pooled <- list(obs = numeric(), pred = numeric(), null = numeric(), block = character())
  for (u in sort(unique(units$unit), method = "radix")) {
    ud <- dyn_unit_rows(data, units, u)
    lf <- dyn_fit_logged(kind, ud)
    if (!lf$ok) {
      stop(sprintf("%s : ajustement impossible pour %s (%d lignes) : %s", spec$label, u, nrow(ud),
                   conditionMessage(lf$fit)), call. = FALSE)
    }
    fit <- lf$fit
    rows <- dyn_export(fit)
    is_sp <- units$unit_type[units$unit == u][1] == "essence"
    rows$species <- if (is_sp) u else NA_character_
    rows$species_group <- if (is_sp) NA_character_ else u
    rows$model <- spec$model
    params[[u]] <- rows
    cv <- dyn_cv(kind, ud, fold_of_block)
    obs <- dyn_observed(kind, ud)
    unit_info[[u]] <- list(n = nrow(ud), dropped = attr(fit, "dropped"), failed = cv$failed,
                           n_folds = cv$n_folds, unseen = cv$unseen,
                           final_converged = lf$converged, final_warnings = lf$warnings,
                           fold_not_converged = cv$not_converged, fold_warnings = cv$warnings,
                           count = units$unit_count[units$unit == u][1],
                           members = units$members[units$unit == u][1])
    # Résumé global : seulement les lignes des essences affectées à cette unité. Les unités se
    # recouvrent (toutes_essences contient aussi les essences d'un groupe) : sans ce filtre, une
    # même observation compterait deux fois.
    assigned <- ud$species %in% units$species[units$unit == u]
    pooled$obs <- c(pooled$obs, obs[assigned]); pooled$pred <- c(pooled$pred, cv$pred[assigned])
    pooled$null <- c(pooled$null, cv$null[assigned]); pooled$block <- c(pooled$block, ud$block[assigned])
    for (sp in units$species[units$unit == u]) {
      sel <- ud$species == sp
      met <- dyn_metrics(kind, obs[sel], cv$pred[sel], cv$null[sel])
      per_species[[sp]] <- c(list(species = sp, unit = u, unit_type = if (is_sp) "essence" else "groupe",
                                  n = sum(sel), events = if (kind == "mortality") sum(ud$dead[sel])
                                  else if (kind == "recruitment") sum(ud$n_recruits[sel]) else NA,
                                  domain = dyn_domain(kind, ud[sel, , drop = FALSE])), met)
    }
  }
  p <- do.call(rbind, params)
  p$provisoire <- TRUE
  p$source <- source
  list(params = p, per_species = per_species[sort(names(per_species), method = "radix")],
       units = units, unit_info = unit_info,
       pooled = dyn_metrics(kind, pooled$obs, pooled$pred, pooled$null),
       block_counts = table(factor(pooled$block, levels = sort(unique(pooled$block), method = "radix"))))
}

#' Domaine de validité d'une essence pour un modèle : étendue des données d'ajustement.
dyn_domain <- function(kind, d) {
  rng <- function(v, digits, unit) {
    v <- v[!is.na(v)]
    if (!length(v)) return("aucune donnée")
    sprintf("de %s à %s %s", dyn_fmt(min(v), digits), dyn_fmt(max(v), digits), unit)
  }
  switch(kind,
         growth = , mortality = paste0("d130 ", rng(d$d130, 1, "cm"), " ; surface terrière ",
                                       rng(d$ba_plot, 1, "m²/ha")),
         recruitment = paste0("surface terrière de la placette ", rng(d$ba_plot, 1, "m²/ha"),
                              " ; de l'essence ", rng(d$ba_species, 1, "m²/ha")),
         height = paste0("d130 / d_dom ", rng(d$rel_d, 2, ""), " ; d130 ", rng(d$d130, 1, "cm")))
}

#' Lignes de la forme de Chapman-Richards pour les essences des données, par la correspondance
#' nemeton_code de contracts/species.csv. Rend les lignes et les essences sans courbe (motif).
dyn_chapman_richards <- function(species, species_ref) {
  rows <- list()
  missing <- character()
  info <- list()
  for (sp in species) {
    code <- species_ref$nemeton_code[match(sp, species_ref$espar)]
    i <- match(code, DYN_CR_NEMETON$nemeton_code)
    if (is.na(code)) {
      missing[sp] <- "aucun code nemeton dans contracts/species.csv"
    } else if (!is.na(DYN_CR_NOT_TAKEN[code])) {
      missing[sp] <- sprintf("%s : %s", code, DYN_CR_NOT_TAKEN[[code]])
    } else if (is.na(i)) {
      missing[sp] <- sprintf("%s : aucune courbe dans nemeton (site_index_params)", code)
    } else {
      r <- DYN_CR_NEMETON[i, ]
      src <- sprintf(paste0("%s, ligne %s : %s, tel que cité par nemeton ; paramètres recalés par ",
                            "nemeton sur un point de référence publié ; non ajusté sur le jeu fictif ; ",
                            "provisoire, à vérifier sur la source"), DYN_CR_SOURCE, code, r$reference)
      rows[[sp]] <- data.frame(
        species = sp, species_group = NA_character_, model = "chapman_richards",
        term = c(paste0("A_class", 1:5), "k", "p"), variable = NA_character_, x = NA_real_,
        value = c(r$a1, r$a2, r$a3, r$a4, r$a5, r$k, r$p), provisoire = TRUE, source = src,
        stringsAsFactors = FALSE)
      info[[sp]] <- list(code = code, A = c(r$a1, r$a2, r$a3, r$a4, r$a5), k = r$k, p = r$p,
                         reference = r$reference)
    }
  }
  list(rows = if (length(rows)) do.call(rbind, rows) else NULL, missing = missing, info = info)
}

#' Un an de la courbe de Korf du contrat dynamics_params (modèle `korf`) :
#' H = a · exp(−(p_f · b + [ln(a / H_prec)]^(−1/c))^(−c)), H_prec dans ]0 ; a[ (sinon erreur).
dyn_korf_step <- function(h_prev, a, b, c, p_f) {
  if (anyNA(h_prev) || any(h_prev <= 0) || any(h_prev >= a)) {
    stop("Korf : la hauteur de l'année précédente doit être strictement entre 0 et l'asymptote a", call. = FALSE)
  }
  a * exp(-(p_f * b + log(a / h_prev)^(-1 / c))^(-c))
}

#' Hauteur de Korf à l'âge `age` pour une classe, en partant de (t0, H0) par `dyn_korf_step` :
#' sert à l'illustration du rapport et aux tests, jamais au moteur (qui part de h0.tif).
dyn_korf_height <- function(age, a, b, c, t0, H0, p_f) {
  if (age < t0) stop("Korf : l'âge demandé est inférieur à l'âge de départ", call. = FALSE)
  h <- H0
  for (i in seq_len(age - t0)) h <- dyn_korf_step(h, a, b, c, p_f)
  h
}

#' Paramètres de Korf du hêtre : la moyenne des deux régions de nemeton, terme à terme (a, b, c,
#' p_f_min, p_f_max), décision de l'orchestrateur du 25/11/2026 (moyenne NO et NE citée par
#' nemeton). Une moyenne des paramètres n'est pas la moyenne des hauteurs de nemeton : l'écart est
#' mesuré et écrit au rapport.
dyn_korf_params <- function(regions = DYN_KORF_REGIONS) {
  m <- colMeans(regions[, c("a", "b", "c", "t0", "H0", "p_f_min", "p_f_max")])
  list(a = m[["a"]], b = m[["b"]], c = m[["c"]], t0 = m[["t0"]], H0 = m[["H0"]],
       p_f = seq(m[["p_f_max"]], m[["p_f_min"]], length.out = 5L))   # classe 1 = la meilleure
}

#' Lignes `korf` (contrat dynamics_params) pour les essences des données qui en ont une dans
#' nemeton (FASY), par la correspondance nemeton_code de contracts/species.csv.
dyn_korf <- function(species, species_ref) {
  rows <- list()
  info <- list()
  kp <- dyn_korf_params()
  for (sp in species) {
    code <- species_ref$nemeton_code[match(sp, species_ref$espar)]
    if (is.na(code) || !code %in% DYN_KORF_NEMETON_CODES) next
    src <- sprintf(paste0("%s : moyenne terme à terme des régions NO et NE, telle que nemeton la cite ; ",
                          "p_f de la classe 1 (meilleure) à 5 à pas égal entre la moyenne des p_f_max et celle des ",
                          "p_f_min ; chprod = 1 ; non ajusté sur le jeu fictif ; provisoire, à vérifier sur la source"),
                   DYN_KORF_SOURCE)
    rows[[sp]] <- data.frame(
      species = sp, species_group = NA_character_, model = "korf",
      term = c("a", "b", "c", paste0("p_f_class", 1:5)), variable = NA_character_, x = NA_real_,
      value = c(kp$a, kp$b, kp$c, kp$p_f), provisoire = TRUE, source = src, stringsAsFactors = FALSE)
    info[[sp]] <- list(code = code, a = kp$a, b = kp$b, c = kp$c, p_f = kp$p_f, t0 = kp$t0, H0 = kp$H0)
  }
  list(rows = if (length(rows)) do.call(rbind, rows) else NULL, info = info)
}

# ------------------------------------------------------------------ écriture

DYN_PARAM_COLUMNS <- c("species", "species_group", "model", "term", "variable", "x", "value",
                       "provisoire", "source")

#' Écrit une table de params au schéma explicite (provisoire en booléen), triée.
dyn_write_params <- function(df, path) {
  .require_arrow()
  df <- df[, DYN_PARAM_COLUMNS]
  o <- order(is.na(df$species), df$species, is.na(df$species_group), df$species_group, df$model,
             df$term, method = "radix")
  df <- df[o, , drop = FALSE]
  rownames(df) <- NULL
  sch <- arrow::schema(species = arrow::string(), species_group = arrow::string(),
                       model = arrow::string(), term = arrow::string(),
                       variable = arrow::string(), x = arrow::float64(),
                       value = arrow::float64(), provisoire = arrow::boolean(),
                       source = arrow::string())
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  arrow::write_parquet(arrow::arrow_table(df, schema = sch), path)
  invisible(path)
}

dyn_output_paths <- function(zone_dir) {
  c(stats::setNames(file.path(zone_dir, "params", paste0(DYN_PARAMS, ".parquet")), DYN_PARAMS),
    report = file.path(zone_dir, "rapport_dynamics.html"))
}

# ------------------------------------------------------------------ rapport

#' Nombre au format français, ou « — » s'il manque (jamais NA ni Inf au rapport).
dyn_fmt <- function(x, digits = 3) {
  vapply(x, function(v) {
    if (is.null(v) || length(v) != 1L || is.na(v) || !is.finite(v)) return("—")
    sub(".", ",", formatC(v, format = "f", digits = digits), fixed = TRUE)
  }, character(1), USE.NAMES = FALSE)
}

dyn_int <- function(x) ifelse(is.na(x), "—", as.character(as.integer(round(x))))

dyn_html_table <- function(header, rows) {
  cell <- function(v, tag) paste0("<", tag, ">", html_escape(v), "</", tag, ">")
  c("<table>", paste0("<tr>", paste(cell(header, "th"), collapse = ""), "</tr>"),
    vapply(rows, function(r) paste0("<tr>", paste(cell(r, "td"), collapse = ""), "</tr>"), character(1)),
    "</table>")
}

dyn_html <- function(sections) {
  body <- character()
  for (s in sections) {
    body <- c(body, sprintf("<h2>%s</h2>", html_escape(s$title)))
    for (el in s$items) {
      body <- c(body, switch(el$type,
                             p = sprintf("<p>%s</p>", html_escape(el$text)),
                             ul = c("<ul>", sprintf("<li>%s</li>", html_escape(el$items)), "</ul>"),
                             h3 = sprintf("<h3>%s</h3>", html_escape(el$text)),
                             table = dyn_html_table(el$header, el$rows)))
    }
  }
  c("<!DOCTYPE html>", "<html lang=\"fr\">",
    "<head><meta charset=\"utf-8\"><title>rapport_dynamics</title></head>", "<body>",
    "<h1>dynamics : accroissement, mortalité, recrutement et hauteur (IFN)</h1>", body,
    "</body>", "</html>")
}

dyn_write_html <- function(lines, path) {
  Encoding(lines) <- "UTF-8"
  con <- file(path, open = "wb")
  on.exit(close(con))
  writeLines(lines, con, useBytes = TRUE)
  invisible(path)
}

dyn_p <- function(...) list(type = "p", text = paste0(...))
dyn_ul <- function(items) list(type = "ul", items = items)
dyn_h3 <- function(text) list(type = "h3", text = text)
dyn_table <- function(header, rows) list(type = "table", header = header, rows = rows)

#' Éléments du rapport pour la courbe de Korf (tableau des paramètres, hauteurs à l'âge de référence,
#' écart à la moyenne des hauteurs de nemeton). Vide s'il n'y a aucune essence à Korf.
dyn_korf_report_items <- function(korf) {
  if (!length(korf$info)) return(list())
  items <- list()
  rows <- lapply(names(korf$info), function(sp) {
    i <- korf$info[[sp]]
    c(sp, i$code, dyn_fmt(i$a, 2), dyn_fmt(i$b, 4), dyn_fmt(i$c, 3), paste(dyn_fmt(i$p_f, 3), collapse = " ; "))
  })
  items[[1L]] <- dyn_p("Hêtre, forme de Korf (Bontemps et al. 2007, annexe 2) : H = a · exp(−(p_f · b + [ln(a / H_prec)]^(−1/c))^(−c)), ",
                       "paramètres lus dans ", DYN_KORF_SOURCE, " ; provisoire (décision de Pascal du 25/11/2026). Moyenne terme à terme ",
                       "des régions NO et NE de nemeton.")
  items[[2L]] <- dyn_table(c("Essence", "Code nemeton", "a (m)", "b (1/an)", "c", "p_f, classes 1 à 5"), rows)
  sp <- names(korf$info)[1L]
  i <- korf$info[[sp]]
  reg <- DYN_KORF_REGIONS
  at_ref <- function(a, b, c, t0, H0, pf) dyn_korf_height(DYN_KORF_REF_AGE, a, b, c, t0, H0, pf)
  h_param <- vapply(1:5, function(k) at_ref(i$a, i$b, i$c, i$t0, i$H0, i$p_f[k]), numeric(1))
  h_reg <- sapply(seq_len(nrow(reg)), function(r) {
    pf <- seq(reg$p_f_max[r], reg$p_f_min[r], length.out = 5L)
    vapply(1:5, function(k) at_ref(reg$a[r], reg$b[r], reg$c[r], reg$t0[r], reg$H0[r], pf[k]), numeric(1))
  })
  h_mean <- rowMeans(h_reg)
  hrows <- lapply(1:5, function(k) c(as.character(k), dyn_fmt(h_reg[k, 1L], 1), dyn_fmt(h_reg[k, 2L], 1),
                                    dyn_fmt(h_mean[k], 1), dyn_fmt(h_param[k], 1), dyn_fmt(h_param[k] - h_mean[k], 1)))
  items[[3L]] <- dyn_p("Hauteur à ", DYN_KORF_REF_AGE, " ans, en partant de l'âge ", dyn_fmt(reg$t0[1L], 0), " et des hauteurs H0 de nemeton ",
                       "(illustration : le moteur part de h0.tif). Le point de référence de nemeton pour le hêtre est ",
                       dyn_fmt(DYN_KORF_REF_H_CLASS3, 1), " m en classe 3 (moyenne des hauteurs NO et NE). La courbe retenue ici, à un seul jeu ",
                       "de paramètres, s'en écarte de ", dyn_fmt(h_param[3L] - h_mean[3L], 1), " m en classe 3 : écart connu, à trancher ",
                       "avant tout usage hors du jeu fictif.")
  items[[4L]] <- dyn_table(c("Classe de fertilité", "NO (m)", "NE (m)", "Moyenne des hauteurs NO et NE (m)",
                             "Courbe retenue (m)", "Écart (m)"), hrows)
  items
}

dyn_report <- function(zone, prep, res, cr, units_all, korf = list(rows = NULL, info = list())) {
  cnt <- prep$counts
  fa <- cnt$fates_all; fk <- cnt$fates_kept
  sections <- list()
  sections[[length(sections) + 1L]] <- list(title = "Statut", items = list(
    dyn_p("Résultat provisoire. Tous les coefficients de params/ sont marqués provisoire. En M2a, ils ",
      "sont ajustés sur le jeu fictif (données synthétiques) de la zone « ", zone, " » : ils n'ont ",
      "aucune valeur écologique et ne doivent pas être lus comme tels. La forme de Chapman-Richards ",
      "vient de nemeton (cité), pas du jeu fictif."),
    dyn_p("Graine : ", DYN_SEED, " (répartition des blocs en plis, seulement au-delà de ", DYN_MAX_FOLDS,
      " blocs) ; ajustement REML de mgcv ", as.character(utils::packageVersion("mgcv")),
      ", déterministe.")))

  sections[[length(sections) + 1L]] <- list(title = "Données d'ajustement (spec §6)", items = list(dyn_ul(c(
    sprintf("Placettes de 1re visite : %s ; placettes revues (2e visite) : %s ; lignes de 2e visite sans 1re visite de la placette, ignorées : %s.",
            dyn_int(cnt$plots_v1), dyn_int(cnt$revisited), dyn_int(cnt$plots_v2_orphan)),
    sprintf("Placettes revues écartées pour incident (NINCID ≠ 0), défrichement (DEF5 ≥ 1) ou plantation (INSTP5 = 1) : %s (incident : %s ; défrichement ou plantation : %s).",
            dyn_int(cnt$excl_inc_trav_rev), dyn_int(cnt$excl_incident_rev), dyn_int(cnt$excl_travaux_rev)),
    sprintf("Placettes revues sans valeur de station (trophic ou coarse_*_700m vide), exclues de l'ajustement et comptées : %s.",
            dyn_int(cnt$excl_no_station_rev)),
    sprintf("Placettes revues exclues au total (incident, travaux, sans station) : %s ; placettes revues retenues : %s.",
            dyn_int(cnt$excl_all_rev), dyn_int(cnt$fit_rev)),
    sprintf("Toutes visites : placettes de 1re visite écartées pour incident ou travaux : %s ; sans station : %s ; retenues pour l'accroissement et la hauteur : %s.",
            dyn_int(cnt$excl_inc_trav_all), dyn_int(cnt$excl_no_station_all), dyn_int(cnt$fit_plots)),
    sprintf("PRELEV5 renseigné (sans modalités documentées), placettes gardées et signalées : %s.",
            dyn_int(cnt$harvest_rev)),
    sprintf("Population à risque : arbres vivants (VEGET = 0) à la 1re visite sur placette revue. Arbres coupés (6, 7), retirés de la population : %s sur les placettes retenues (%s sur toutes les placettes revues).",
            dyn_int(fk[["coupe"]]), dyn_int(fa[["coupe"]])),
    sprintf("Arbres non retrouvés (N), retirés de la population : %s sur les placettes retenues (%s sur toutes les placettes revues).",
            dyn_int(fk[["non_retrouve"]]), dyn_int(fa[["non_retrouve"]])),
    sprintf("Chablis comptés comme morts (code A de VEGET5, campagnes de 2e visite 2010 à 2018 ; décision de Pascal du 25/11/2026) : %s sur les placettes retenues (%s sur toutes les placettes revues), dans la mortalité avec les morts naturelles.",
            dyn_int(fk[["chablis"]]), dyn_int(fa[["chablis"]])),
    sprintf("Arbres perdus (T, cassés sous C13 ou perdus après incident), retirés de la population : %s sur les placettes retenues (%s sur toutes les placettes revues).",
            dyn_int(fk[["perdu"]]), dyn_int(fa[["perdu"]])),
    sprintf("Autres arbres retirés sur les placettes retenues : VEGET5 vide %s ; code hors nomenclature de la campagne %s ; sans ligne de 2e visite %s ; sans d130 %s.",
            dyn_int(fk[["etat_absent"]]), dyn_int(fk[["hors_nomenclature"]]),
            dyn_int(fk[["sans_ligne_2e_visite"]]), dyn_int(cnt$risk_no_d130)),
    sprintf("Morts (morts naturelles de VEGET5 selon la campagne, plus chablis) sur les placettes retenues : %s, sur %s arbres à risque.",
            dyn_int(fk[["mort"]] + fk[["chablis"]]),
            dyn_int(fk[["vivant"]] + fk[["mort"]] + fk[["chablis"]])),
    sprintf("Plage de campagnes de 2e visite de la mortalité : %s à %s (toutes les revisites des placettes retenues, %s placettes).",
            cnt$camp2_range_mortality[1], cnt$camp2_range_mortality[2], dyn_int(cnt$fit_rev)),
    sprintf("Plage de campagnes de 2e visite du recrutement : %s à %s (%s placettes) ; écartées du recrutement : %s placettes revues retenues dont la 2e visite date d'avant %d (revisites de 2010 à 2014, qui ne relèvent pas les nouveaux arbres) et leurs %s recrues, qui ne servent qu'à la mortalité.",
            cnt$camp2_range_recruitment[1], cnt$camp2_range_recruitment[2], dyn_int(cnt$fit_rec),
            dyn_int(cnt$rec_excluded_plots), DYN_RECRUIT_FIRST_CAMPAIGN, dyn_int(cnt$recruits_old_campaign)),
    sprintf("Recrues (arbres de 2e visite sans 1re visite, C13 ≥ 0,235 m) : %s sur toutes les placettes revues, dont %s sur les placettes retenues ; lignes sous le seuil, non comptées : %s.",
            dyn_int(cnt$recruits_all), dyn_int(cnt$recruits_kept), dyn_int(cnt$recruits_below)),
    sprintf("Recrues sans poids (W absent de l'export) : %s sur toutes les placettes revues, dont %s sur les placettes retenues ; le poids n'est jamais deviné : les couples placette × essence concernés (%s) sont exclus du recrutement.",
            dyn_int(cnt$recruits_no_w_all), dyn_int(cnt$recruits_no_w_kept), dyn_int(cnt$recruit_cells_no_w)),
    sprintf("Arbres vivants sans poids, absents de la surface terrière : %s ; lignes avec IR5 : %s.",
            dyn_int(cnt$alive_no_weight), dyn_int(cnt$ir5_lines)),
    sprintf("Hauteur dominante H_dom : placettes où les arbres mesurés font moins de %s tiges/ha (H_dom prise sur tous) : %s.",
            dyn_int(DYN_HDOM_STEMS_HA), dyn_int(cnt$hdom_incomplete)),
    sprintf("SER des placettes retenues : %s ; placettes sans SER : %s.",
            if (length(cnt$ser_levels)) paste(cnt$ser_levels, collapse = ", ") else "aucune",
            dyn_int(cnt$ser_missing))
  ))))

  interval <- if (cnt$dt_nominal == 0) {
    sprintf("Intervalle entre visites : différence des DATEPOINT des deux visites pour les %s placettes revues (de %s à %s ans).",
            dyn_int(cnt$dt_from_datepoint), dyn_fmt(cnt$dt_range[1], 2), dyn_fmt(cnt$dt_range[2], 2))
  } else {
    sprintf("Intervalle entre visites : DATEPOINT des deux visites pour %s placettes revues ; intervalle nominal de 5 ans pour %s placettes revues sans DATEPOINT à l'une des visites.",
            dyn_int(cnt$dt_from_datepoint), dyn_int(cnt$dt_nominal))
  }
  ctl <- cnt$ctl
  ctl_txt <- if (ctl$n > 0) {
    sprintf("Contrôle IR5 / différence de C13 entre visites (arbres vivants aux deux visites, IR5 de la 2e visite) : %s arbres ; accroissement radial annuel moyen d'après IR5 %s cm/an, d'après la différence de C13 %s cm/an ; écart moyen (C13 − IR5) %s cm/an. L'accroissement ajusté vient d'IR5.",
            dyn_int(ctl$n), dyn_fmt(mean(ctl$ir5), 4), dyn_fmt(mean(ctl$c13), 4), dyn_fmt(mean(ctl$c13 - ctl$ir5), 4))
  } else {
    "Contrôle IR5 / différence de C13 entre visites : aucun arbre vivant aux deux visites avec IR5 et C13 (0,000 cm/an d'écart non calculable)."
  }
  sections[[length(sections) + 1L]] <- list(title = "Intervalle et accroissement", items = list(
    dyn_p(interval, " Le risque de mort et le recrutement sont ramenés à l'année par cet intervalle ; IR5 est par définition l'épaisseur de 5 cernes, il est divisé par 5."),
    dyn_p(sprintf("Campagnes de 2e visite qui ne valent pas celle de la 1re plus 5 : %s.", dyn_int(cnt$campaign_gap_not5))),
    dyn_p(ctl_txt)))

  sections[[length(sections) + 1L]] <- list(title = "Essences et groupes", items = list(
    dyn_p(sprintf(paste0("Seuils provisoires pour ajuster une essence seule : %s arbres avec IR5 (accroissement), %s morts ",
                     "naturelles (mortalité, 10 événements par degré de liberté d'après Peduzzi et al. 1996, référence ",
                     "non relue), %s recrues (recrutement), %s arbres à hauteur mesurée (hauteur relative). Sous le seuil, ",
                     "l'essence prend le modèle de son groupe (colonne groupe de contracts/species.csv : feuillu, resineux), ",
                     "ajusté sur toutes les essences du groupe ; si le groupe est lui-même sous le seuil, le modèle de toutes ",
                     "les essences (%s)."),
              dyn_int(DYN_THRESHOLDS[["growth"]]), dyn_int(DYN_THRESHOLDS[["mortality"]]),
              dyn_int(DYN_THRESHOLDS[["recruitment"]]), dyn_int(DYN_THRESHOLDS[["height"]]), DYN_ALL_SPECIES)),
    dyn_ul(unlist(lapply(names(units_all), function(k) {
      u <- units_all[[k]]
      vapply(seq_len(nrow(u)), function(i) {
        sprintf("%s, essence %s : %s (%s), membres : %s.", DYN_MODELS[[k]]$label, u$species[i],
                if (u$unit_type[i] == "essence") "ajustée seule" else paste("groupe", u$unit[i]),
                if (u$unit_type[i] == "essence") "seuil atteint" else
                  sprintf("effectif du groupe %s%s", dyn_int(u$unit_count[i]),
                          if (u$unit_count[i] < DYN_THRESHOLDS[[k]]) ", encore sous le seuil : à lire avec prudence" else ""),
                u$members[i])
      }, character(1))
    }), use.names = FALSE))))

  nblocks <- length(unique(prep$blocks))
  cv_items <- list(
    dyn_p(sprintf(paste0("Validation croisée spatiale par blocs : blocs carrés de %s m de côté (taille des blocs ",
                     "provisoire : 2 km font environ trois fois la portée du floutage des coordonnées IFN, 700 m, et ",
                     "dépassent le diamètre, 1 400 m, du disque des valeurs coarse_*_700m ; mais deux placettes de ",
                     "blocs voisins peuvent être à moins de 1 400 m et partager des mailles de station : pas de zone ",
                     "tampon en M2a, à revoir sur la SER pilote en M2b). Blocs tirés des coordonnées floutées de 1re ",
                     "visite (EPSG:2154) ; %s blocs spatiaux ; %s."),
              dyn_int(DYN_BLOCK_SIZE_M), dyn_int(nblocks),
              if (nblocks <= DYN_MAX_FOLDS) "un bloc mis de côté à chaque tour" else
                sprintf("blocs répartis en %s plis par la graine %s", dyn_int(DYN_GROUPED_FOLDS), DYN_SEED))),
    dyn_p(paste0("Sur chaque bloc mis de côté, le modèle et le modèle nul sont ajustés sur les autres blocs et prédits ",
             "par la relecture des paramètres écrits (celle de simulate). Modèle nul : moyenne de l'unité ",
             "(accroissement, hauteur relative), taux constant (recrutement), risque annuel constant (mortalité). ",
             "Biais = prédit − observé. Erreur : RMSE, sauf la mortalité (log-perte moyenne ; score de Brier à côté).")))
  summ <- vapply(names(res), function(k) {
    r <- res[[k]]$pooled
    failed <- sum(vapply(res[[k]]$unit_info, function(u) u$failed, integer(1)))
    unseen <- sum(vapply(res[[k]]$unit_info, function(u) u$unseen, integer(1)))
    ui <- res[[k]]$unit_info
    final_nc <- sum(!vapply(ui, function(u) u$final_converged, logical(1)))
    fold_nc <- sum(vapply(ui, function(u) u$fold_not_converged, integer(1)))
    w_final <- sum(vapply(ui, function(u) length(u$final_warnings), integer(1)))
    w_fold <- sum(vapply(ui, function(u) length(u$fold_warnings), integer(1)))
    sprintf("%s : erreur du modèle %s contre %s pour le modèle nul (%s), biais %s, sur %s prédictions des mêmes blocs mis de côté (chaque observation une seule fois, par l'unité de son essence) ; plis non ajustés : %s ; niveaux de SER inconnus du pli : %s ; ajustements finals non convergés : %s sur %s, plis non convergés : %s ; avertissements de mgcv : %s à l'ajustement final, %s dans les plis.",
            DYN_MODELS[[k]]$label, dyn_fmt(r$error, 4), dyn_fmt(r$error_null, 4),
            if (k == "mortality") "log-perte" else paste("RMSE,", DYN_MODELS[[k]]$unit),
            dyn_fmt(r$bias, 4), dyn_int(r$n_pred), dyn_int(failed), dyn_int(unseen),
            dyn_int(final_nc), dyn_int(length(ui)), dyn_int(fold_nc), dyn_int(w_final), dyn_int(w_fold))
  }, character(1))
  cv_items[[length(cv_items) + 1L]] <- dyn_ul(unname(summ))
  bc <- vapply(names(res), function(k) {
    t <- res[[k]]$block_counts
    sprintf("%s, effectif par bloc mis de côté (bloc colonne_ligne de %s m : lignes) : %s ; le plus gros bloc porte %s %% des lignes.",
            DYN_MODELS[[k]]$label, dyn_int(DYN_BLOCK_SIZE_M),
            paste(sprintf("%s : %s", names(t), as.integer(t)), collapse = " ; "),
            dyn_fmt(100 * max(t) / sum(t), 1))
  }, character(1))
  cv_items[[length(cv_items) + 1L]] <- dyn_ul(unname(bc))
  wtxt <- unique(unlist(lapply(res, function(r) unlist(lapply(r$unit_info, function(u) c(u$final_warnings, u$fold_warnings))))))
  if (length(wtxt)) {
    cv_items[[length(cv_items) + 1L]] <- dyn_ul(sprintf("Avertissement de mgcv rencontré : %s", utils::head(wtxt, 10)))
  }
  sections[[length(sections) + 1L]] <- list(title = "Validation croisée spatiale par blocs", items = cv_items)

  # Un tableau par modèle, une ligne par essence.
  tab_items <- list()
  for (k in names(res)) {
    r <- res[[k]]
    unit <- DYN_MODELS[[k]]$unit
    tab_items[[length(tab_items) + 1L]] <- dyn_h3(sprintf("%s (%s, params/%s.parquet)", DYN_MODELS[[k]]$label,
                                                      DYN_MODELS[[k]]$model, if (k == "height") "height_curve" else k))
    if (k == "mortality") {
      header <- c("Essence", "Ajustée comme", "Effectif à risque (n)", "Morts", "Biais (probabilité)",
                  "Erreur (log-perte)", "Erreur du modèle nul (log-perte)", "Brier (modèle / nul)",
                  "Domaine de validité")
    } else {
      header <- c("Essence", "Ajustée comme", if (k == "recruitment") "Effectif (n placettes ; recrues)" else "Effectif (n)",
                  sprintf("Biais (%s)", unit), sprintf("Erreur RMSE (%s)", unit),
                  sprintf("Erreur du modèle nul (%s)", unit), "Domaine de validité")
    }
    rows <- lapply(r$per_species, function(s) {
      how <- if (s$unit_type == "essence") "seule" else paste("groupe", s$unit)
      if (k == "mortality") {
        c(s$species, how, dyn_int(s$n), dyn_int(s$events), dyn_fmt(s$bias, 4), dyn_fmt(s$error, 4),
          dyn_fmt(s$error_null, 4), paste(dyn_fmt(s$brier, 4), "/", dyn_fmt(s$brier_null, 4)), s$domain)
      } else {
        c(s$species, how, if (k == "recruitment") paste0(dyn_int(s$n), " ; ", dyn_int(s$events)) else dyn_int(s$n),
          dyn_fmt(s$bias, 4), dyn_fmt(s$error, 4), dyn_fmt(s$error_null, 4), s$domain)
      }
    })
    tab_items[[length(tab_items) + 1L]] <- dyn_table(header, rows)
    dropped <- unlist(lapply(names(r$unit_info), function(u) {
      d <- r$unit_info[[u]]$dropped
      if (length(d)) sprintf("%s, unité %s : variables laissées de côté (moins de quatre valeurs distinctes, ou SER unique ou vide) : %s.",
                             DYN_MODELS[[k]]$label, u, paste(d, collapse = ", "))
    }))
    if (length(dropped)) tab_items[[length(tab_items) + 1L]] <- dyn_ul(dropped)
  }
  sections[[length(sections) + 1L]] <- list(title = "Résultats par essence", items = tab_items)

  cr_rows <- lapply(names(cr$info), function(sp) {
    i <- cr$info[[sp]]
    c(sp, i$code, paste(dyn_fmt(i$A, 0), collapse = " ; "), dyn_fmt(i$k, 3), dyn_fmt(i$p, 2), i$reference)
  })
  cr_items <- list(
    dyn_p("Hauteur d'un arbre (spec §5) : h / H_dom selon d130 / d_dom, ajustée par essence ou groupe (tableau ",
      "ci-dessus). H_dom et d_dom d'une placette : moyenne pondérée des hauteurs et diamètre quadratique moyen des ",
      dyn_int(DYN_HDOM_STEMS_HA), " plus gros arbres par hectare (définition provisoire)."),
    dyn_p("Forme de la courbe de hauteur dominante (BRIEF §6, hauteur, point 1) : Chapman-Richards H(t) = A (1 − exp(−k t))^p, ",
      "paramètres lus dans ", DYN_CR_SOURCE, ", références telles que nemeton les cite ; provisoire. simulate prend ",
      "le plafond dans site_potential.tif ; A par classe de fertilité est donné pour mémoire."))
  if (length(cr_rows)) {
    cr_items[[length(cr_items) + 1L]] <- dyn_table(c("Essence", "Code nemeton", "A, classes 1 à 5 (m)", "k (1/an)", "p", "Référence citée par nemeton"),
                                               cr_rows)
  }
  if (length(cr$missing)) {
    cr_items[[length(cr_items) + 1L]] <- dyn_ul(sprintf("Essence %s sans courbe de Chapman-Richards, signalée et non inventée : %s.",
                                                    names(cr$missing), cr$missing))
  }
  cr_items <- c(cr_items, dyn_korf_report_items(korf))
  sections[[length(sections) + 1L]] <- list(title = "Courbe de hauteur", items = cr_items)

  sections[[length(sections) + 1L]] <- list(title = "Limites connues", items = list(dyn_ul(c(
    "Concurrence non spatialisée : à l'ajustement, la surface terrière est calculée à la placette (chaque arbre pondéré par l'inverse de la surface de son cercle de 6, 9 ou 15 m) ; en simulation, dans un disque de 15 m autour de chaque arbre simulé. Le décalage entre les deux est une limite connue (spec §6).",
    "Climat : l'accroissement (IR5) et la mortalité reflètent le climat des cinq années précédant la mesure.",
    "Flore de 1re visite : pour un arbre revu, la station (flore, trophic) est celle de la 1re visite, seule relevée ; décalage d'environ 5 ans avec la 2e visite.",
    "Cohérence H/D : le diamètre simulé (modèles IFN) et la hauteur simulée (courbe de station) viennent de deux sources ; le rapport H/D est à contrôler en simulation.",
    "Mortalité sous-estimée : un arbre mort puis coupé avant la 2e visite apparaît coupé, donc retiré de la population (IGN, méthodologie 2023, p. 21).",
    "Accroissement passé, état présent : IR5 couvre les 5 cernes avant la visite, alors que d130 et la concurrence sont ceux de la visite.",
    "Ajustement non pondéré par W : le tirage dépend de d130, qui est une variable du modèle ; W sert au recrutement (tiges/ha) et à la surface terrière.",
    "Hors du domaine : chaque variable est bornée à ses nœuds extrêmes (la valeur au bord est tenue) ; une SER absente de l'ajustement compte pour 0 (moyenne de l'effet aléatoire).",
    sprintf("Blocs déséquilibrés : un bloc qui porte l'essentiel des données (ici, pour la mortalité, %s %% des arbres à risque dans un seul bloc) rend la comparaison au modèle nul peu informative : quand ce bloc est mis de côté, les deux modèles sont ajustés sur peu de données, et les autres plis ne testent presque rien.",
            dyn_fmt(100 * max(res$mortality$block_counts) / sum(res$mortality$block_counts), 1)),
    "Chablis comptés comme morts : les arbres en chablis (code A de VEGET5, campagnes 2010 à 2018) restent dans la population à risque et comptent comme morts, qu'ils aient été vivants ou morts au sol (règle de Pascal du 25/11/2026) ; à partir de 2019, les chablis vivants (code 1) restent vivants.",
    "Chapman-Richards : paramètres reconstitués par nemeton et recalés sur un point de référence publié, pas les paramètres publiés eux-mêmes ; à vérifier sur les sources.",
    "Korf du hêtre : moyenne des paramètres des régions NO et NE de nemeton, pas la moyenne de leurs hauteurs (celle que nemeton cite) ; l'écart de hauteur est donné dans la section « Courbe de hauteur » ; à vérifier sur la source (Bontemps et al. 2007) avant tout usage hors du jeu fictif.",
    "Jeu fictif : en M2a, aucune erreur ni comparaison au modèle nul ne dit quoi que ce soit de la forêt réelle ; le critère de M2b (RMSE sous celle du modèle nul sur la SER pilote) reste à passer avec Pascal."
  ))))
  dyn_html(sections)
}

# ------------------------------------------------------------------ module

#' Module dynamics sur une zone : lit ifn/, ajuste, valide, écrit params/ et le rapport.
#' Une entrée refusée arrête avant toute écriture ; les sorties d'un lancement précédent sont
#' effacées d'abord (jamais de sortie périmée ou à moitié écrite).
dynamics_run <- function(zone_dir, zone = basename(zone_dir), root = dyn_root(), validate = TRUE) {
  out <- dyn_output_paths(zone_dir)
  unlink(out[file.exists(out)])
  species_ref <- dyn_species_ref(root)
  inp <- dyn_read_inputs(zone_dir, species_ref, validate = validate)
  prep <- dyn_prepare_data(inp$trees, inp$plots)

  blocks <- unique(rbind(prep$growth[, c("plot_id", "block")], prep$mortality[, c("plot_id", "block")],
                         prep$recruitment[, c("plot_id", "block")], prep$height[, c("plot_id", "block")]))
  prep$blocks <- blocks$block
  ub <- sort(unique(blocks$block), method = "radix")
  fold_of_block <- stats::setNames(dyn_folds(ub), ub)

  # La source ne nomme ni la zone ni le chemin : mêmes entrées, mêmes params (rejeu).
  source <- sprintf(paste0("ajusté par dynamics (mgcv %s, REML) sur ifn/ ; M2a : jeu fictif, ",
                           "données synthétiques, aucune valeur écologique ; à refaire sur un export ",
                           "réel (M2b)"), as.character(utils::packageVersion("mgcv")))
  res <- list()
  for (k in names(DYN_MODELS)) {
    data <- prep[[k]]
    if (!nrow(data)) stop(sprintf("%s : aucune donnée d'ajustement après les règles de spec §6", DYN_MODELS[[k]]$label),
                          call. = FALSE)
    res[[k]] <- dyn_run_model(k, data, prep$species, species_ref, fold_of_block, source)
  }
  cr <- dyn_chapman_richards(prep$species, species_ref)
  korf <- dyn_korf(prep$species, species_ref)
  tables <- list(growth = res$growth$params, mortality = res$mortality$params,
                 recruitment = res$recruitment$params,
                 height_curve = rbind(res$height$params[, DYN_PARAM_COLUMNS], cr$rows, korf$rows))
  html <- dyn_report(zone, prep, res, cr, lapply(res, function(r) r$units), korf)

  # Écriture dans un dossier temporaire, validation, puis déplacement : tout ou rien.
  tmp <- file.path(zone_dir, "params", ".dynamics_tmp")
  unlink(tmp, recursive = TRUE)
  dir.create(tmp, recursive = TRUE, showWarnings = FALSE)
  on.exit(unlink(tmp, recursive = TRUE), add = TRUE)
  for (n in DYN_PARAMS) {
    p <- file.path(tmp, paste0(n, ".parquet"))
    dyn_write_params(tables[[n]], p)
    if (validate) validate_file(paste0("dynamics.", n), p)
  }
  for (n in DYN_PARAMS) file.rename(file.path(tmp, paste0(n, ".parquet")), out[[n]])
  dyn_write_html(html, out[["report"]])
  message(sprintf("[dynamics] params/{%s}.parquet et rapport_dynamics.html écrits (%s)",
                  paste(DYN_PARAMS, collapse = ","), zone_dir))
  invisible(list(prep = prep, res = res, cr = cr, korf = korf, tables = tables))
}
