# prepare : tables IFN (spec §2 « ifn/ », §6 ; mission 019 ; BRIEF §4).
#
# Lit les trois fichiers bruts de l'IFN sous <zone>/inputs/ifn/ (PLACETTE.csv, ARBRE.csv,
# FLORE.csv) et écrit sous <zone>/ifn/ les trois tables que lit `dynamics` :
#   plots.parquet   contrat prepare.ifn_plots
#   trees.parquet   contrat prepare.ifn_trees
#   flora.parquet   contrat prepare.ifn_flora
#
# Règles (docs/referentiels/ifn-placettes.md, IMOT 2025 p. 61 et 71) :
#  - `C13` est une circonférence en millimètres : d130 (cm) = C13 / (10 pi) ;
#  - les placettes ont des cercles emboîtés, choisis par classe de dimension :
#      d130 de 7,5 (C13 235 mm) à moins de 22,5 cm  -> cercle de 6 m
#      d130 de 22,5 à moins de 37,5 cm               -> cercle de 9 m
#      d130 de 37,5 cm et plus                       -> cercle de 15 m
#    les seuils portent sur le d130 calculé (22,5 pi = 706,86 mm ; 37,5 pi = 1178,1 mm)
#    le poids d'un arbre (tiges/ha) est 10000 / (pi R^2), soit 88,4 ; 39,3 ; 14,1 ;
#  - les coordonnées sont floutées (700 m) : les placettes sont marquées par `mark_ifn()` de
#    la garde (R/ifn_guard.R) et ne sont croisées avec aucun raster fin. Ce module n'ouvre
#    aucun raster.
#
# Signaler plutôt que deviner : `ser_code`, `trophic`, `coarse_hydric_700m` et
# `coarse_bioclim_700m` sont laissés vides (NA) tant que leur source n'est pas branchée ;
# le message de sortie le dit. Voir `prepare_ifn()` pour le détail.

IFN_CIRCLES <- data.frame(
  radius_m = c(6, 9, 15),
  c13_min_mm = c(235, 705, 1175),
  stringsAsFactors = FALSE
)

#' d130 en cm depuis C13 (circonférence en mm) : C13 / (10 pi).
ifn_d130_cm <- function(c13_mm) c13_mm / (10 * pi)

#' Rayon du cercle de placette (m) selon C13 (mm) ; NA sous le seuil de 235 mm
#' (arbre non recensable) ou si C13 est NA.
ifn_circle_radius_m <- function(c13_mm) {
  d <- ifn_d130_cm(c13_mm)          # seuils pris sur le d130 calcule (22,5 et 37,5 cm)
  r <- rep(NA_real_, length(c13_mm))
  r[!is.na(c13_mm) & c13_mm >= 235] <- 6
  r[!is.na(c13_mm) & d >= 22.5] <- 9
  r[!is.na(c13_mm) & d >= 37.5] <- 15
  r
}

#' Poids d'un arbre en tiges par hectare : inverse de la surface de son cercle.
ifn_weight_ha <- function(c13_mm) 10000 / (pi * ifn_circle_radius_m(c13_mm)^2)

.ifn_read_csv <- function(path, required) {
  if (!file.exists(path)) stop(sprintf("fichier IFN introuvable : %s", path), call. = FALSE)
  d <- utils::read.table(path, sep = ";", header = TRUE, colClasses = "character",
                         quote = "\"", comment.char = "", check.names = FALSE,
                         encoding = "UTF-8", stringsAsFactors = FALSE)
  manque <- setdiff(required, names(d))
  if (length(manque)) {
    stop(sprintf("%s : colonne(s) absente(s) : %s", basename(path),
                 paste(manque, collapse = ", ")), call. = FALSE)
  }
  d
}

.ifn_num <- function(v, what) {
  n <- suppressWarnings(as.numeric(v))
  mal <- !is.na(v) & v != "" & is.na(n)
  if (any(mal)) {
    stop(sprintf("%s : valeur non numérique (ex. « %s »)", what, v[mal][1]), call. = FALSE)
  }
  n
}

.ifn_campaign <- function(v, what) {
  n <- .ifn_num(v, what)
  if (anyNA(n) || any(n != round(n))) {
    stop(sprintf("%s : année de campagne manquante ou non entière", what), call. = FALSE)
  }
  as.integer(n)
}

#' Construit les trois tables à partir des trois data.frames bruts (tout en chaîne).
#'
#' @return liste `plots`, `trees`, `flora`, `report` (vecteur de lignes en français).
ifn_tables <- function(placette, arbre, flore, precision_m = 700, taxref_version = "13") {
  report <- character(0)

  # ---- placettes
  cle_p <- paste(placette$IDP, placette$CAMPAGNE)
  if (anyDuplicated(cle_p)) {
    stop(sprintf("PLACETTE.csv : couple (IDP, CAMPAGNE) en double, ex. %s",
                 cle_p[duplicated(cle_p)][1]), call. = FALSE)
  }
  plots <- data.frame(
    plot_id = placette$IDP,
    campaign = .ifn_campaign(placette$CAMPAGNE, "PLACETTE.csv CAMPAGNE"),
    x = .ifn_num(placette$XL, "PLACETTE.csv XL"),
    y = .ifn_num(placette$YL, "PLACETTE.csv YL"),
    stringsAsFactors = FALSE
  )
  if (anyNA(plots$x) || anyNA(plots$y) || any(plots$plot_id == "")) {
    stop("PLACETTE.csv : IDP, XL ou YL manquant", call. = FALSE)
  }
  # Mêmes bornes approximatives que sylvostation : détecte x/y inversés ou degrés.
  if (any(plots$x < 0 | plots$x > 1300000 | plots$y < 6000000 | plots$y > 7200000)) {
    stop("PLACETTE.csv : coordonnées hors de la France métropolitaine en Lambert-93 ",
         "(x/y inversés ou autre système ?)", call. = FALSE)
  }
  plots <- mark_ifn(plots, precision_m)
  plots$ser_code <- NA_character_
  plots$trophic <- NA_real_
  plots$coarse_hydric_700m <- NA_real_
  plots$coarse_bioclim_700m <- NA_real_
  plots <- plots[, c("plot_id", "campaign", "x", "y", "loc_precision_m", "source",
                     "ser_code", "trophic", "coarse_hydric_700m", "coarse_bioclim_700m")]
  report <- c(report, sprintf(
    "ifn/plots : %d placettes ; ser_code, trophic, coarse_hydric_700m et coarse_bioclim_700m vides (source non branchée)",
    nrow(plots)))

  # ---- arbres
  t_camp <- .ifn_campaign(arbre$CAMPAGNE, "ARBRE.csv CAMPAGNE")
  inconnues <- setdiff(paste(arbre$IDP, t_camp), paste(plots$plot_id, plots$campaign))
  if (length(inconnues)) {
    stop(sprintf("ARBRE.csv : placette absente de PLACETTE.csv (IDP CAMPAGNE) : %s",
                 inconnues[1]), call. = FALSE)
  }
  c13 <- .ifn_num(arbre$C13, "ARBRE.csv C13")
  h <- if ("HTOT" %in% names(arbre)) .ifn_num(arbre$HTOT, "ARBRE.csv HTOT") else rep(NA_real_, nrow(arbre))
  if (any(c13[!is.na(c13)] > 0 & c13[!is.na(c13)] < 100)) {
    # Garde-fou sur l'unité (référentiel §2) : un c13 courant est de 300 à 2000, pas de 30 à 200.
    n_bas <- sum(!is.na(c13) & c13 > 0 & c13 < 100)
    report <- c(report, sprintf(
      "ifn/trees : %d arbre(s) avec C13 < 100 : vérifier que C13 est bien en mm", n_bas))
  }
  rayon <- ifn_circle_radius_m(c13)
  garde <- !is.na(rayon)
  if (any(!garde)) {
    report <- c(report, sprintf(
      "ifn/trees : %d arbre(s) écartés (C13 manquant ou sous le seuil de recensabilité de 235 mm)",
      sum(!garde)))
  }
  w <- 10000 / (pi * rayon^2)
  id_arbre <- if ("ARBRE" %in% names(arbre)) arbre$ARBRE else {
    stats::ave(seq_along(arbre$IDP), arbre$IDP, t_camp, FUN = seq_along)
  }
  trees <- data.frame(
    plot_id = arbre$IDP,
    campaign = t_camp,
    tree_id = as.character(id_arbre),
    species = arbre$ESPAR,
    d130 = ifn_d130_cm(c13),
    h = ifelse(!is.na(h) & h > 0, h, NA_real_),
    weight_ha = w,
    stringsAsFactors = FALSE
  )[garde, , drop = FALSE]
  if (any(!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees$species))) {
    stop(sprintf("ARBRE.csv : code ESPAR invalide (ex. « %s »)",
                 trees$species[!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees$species)][1]),
         call. = FALSE)
  }
  if ("W" %in% names(arbre)) {
    w_brut <- .ifn_num(arbre$W, "ARBRE.csv W")[garde]
    ecart <- !is.na(w_brut) & abs(w_brut - trees$weight_ha) > 0.01 * trees$weight_ha
    if (any(ecart)) {
      report <- c(report, sprintf(
        "ifn/trees : %d arbre(s) dont W du fichier diffère de plus de 1 %% du poids du cercle ; le poids du cercle est retenu",
        sum(ecart)))
    }
  }
  rownames(trees) <- NULL
  report <- c(report, sprintf("ifn/trees : %d arbres ; d130 = C13 / (10 pi) ; poids par cercle de 6, 9 ou 15 m",
                              nrow(trees)))

  # ---- flore
  f_camp <- .ifn_campaign(flore$CAMPAGNE, "FLORE.csv CAMPAGNE")
  inconnues <- setdiff(paste(flore$IDP, f_camp), paste(plots$plot_id, plots$campaign))
  if (length(inconnues)) {
    stop(sprintf("FLORE.csv : placette absente de PLACETTE.csv (IDP CAMPAGNE) : %s",
                 inconnues[1]), call. = FALSE)
  }
  cd <- .ifn_num(flore$CD_REF, "FLORE.csv CD_REF")
  if (anyNA(cd) || any(cd != round(cd)) || any(cd < 1)) {
    stop("FLORE.csv : CD_REF manquant ou non entier positif", call. = FALSE)
  }
  ab <- .ifn_num(flore$ABOND, "FLORE.csv ABOND")
  flora <- data.frame(
    plot_id = flore$IDP,
    campaign = f_camp,
    cd_ref = as.integer(cd),
    taxref_version = taxref_version,
    abundance = ab,
    stringsAsFactors = FALSE
  )
  report <- c(report, sprintf(
    "ifn/flora : %d lignes ; taxref_version = « %s » (CD_REF de l'IFN, sans conversion en v18)",
    nrow(flora), taxref_version))

  list(plots = plots, trees = trees, flora = flora, report = report)
}

# Écriture Parquet par Arrow, avec un schéma explicite : une colonne entièrement vide reste
# de type chaîne ou double (et non « null », que le contrat refuse).
.ifn_write_parquet <- function(df, path, types) {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("le paquet R « arrow » est absent : impossible d'écrire du Parquet ",
         "(voie à décider, voir le rendu de la mission 019)", call. = FALSE)
  }
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  sch <- do.call(arrow::schema, lapply(names(df), function(n) arrow::field(n, types[[n]])))
  arrow::write_parquet(arrow::arrow_table(df, schema = sch), path)
  invisible(path)
}

#' Prépare les tables IFN d'une zone.
#'
#' À brancher dans `run_prepare()` (mission 017) : `prepare_ifn(zone_dir)`.
#'
#' @param zone_dir dossier de la zone (`tests/fixtures/zone_fictive` ou `data/<zone>`).
#' @param precision_m précision de localisation écrite dans `loc_precision_m` (700 m, IGN :
#'   centre de la maille de 1 km, écart maximal 700 m).
#' @param taxref_version version TAXREF des CD_REF lus (« 13 » : version de l'IFN).
#' @return liste invisible `plots`, `trees`, `flora`, `report`, `files`. Les lignes du
#'   rapport sont aussi écrites par `message()`.
prepare_ifn <- function(zone_dir, precision_m = 700, taxref_version = "13") {
  dir_in <- file.path(zone_dir, "inputs", "ifn")
  res <- ifn_tables(
    .ifn_read_csv(file.path(dir_in, "PLACETTE.csv"), c("CAMPAGNE", "IDP", "XL", "YL")),
    .ifn_read_csv(file.path(dir_in, "ARBRE.csv"), c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    .ifn_read_csv(file.path(dir_in, "FLORE.csv"), c("CAMPAGNE", "IDP", "CD_REF", "ABOND")),
    precision_m = precision_m, taxref_version = taxref_version
  )
  out <- file.path(zone_dir, "ifn")
  files <- c(
    plots = .ifn_write_parquet(res$plots, file.path(out, "plots.parquet"), list(
      plot_id = arrow::string(), campaign = arrow::int32(), x = arrow::float64(),
      y = arrow::float64(), loc_precision_m = arrow::float64(), source = arrow::string(),
      ser_code = arrow::string(), trophic = arrow::float64(),
      coarse_hydric_700m = arrow::float64(), coarse_bioclim_700m = arrow::float64())),
    trees = .ifn_write_parquet(res$trees, file.path(out, "trees.parquet"), list(
      plot_id = arrow::string(), campaign = arrow::int32(), tree_id = arrow::string(),
      species = arrow::string(), d130 = arrow::float64(), h = arrow::float64(),
      weight_ha = arrow::float64())),
    flora = .ifn_write_parquet(res$flora, file.path(out, "flora.parquet"), list(
      plot_id = arrow::string(), campaign = arrow::int32(), cd_ref = arrow::int32(),
      taxref_version = arrow::string(), abundance = arrow::float64()))
  )
  for (l in res$report) message("[prepare/ifn] ", l)
  invisible(c(res, list(files = files)))
}
