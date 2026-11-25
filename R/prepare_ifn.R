# prepare : tables IFN (spec §2 « ifn/ », §6 ; mission 019 ; BRIEF §4).
#
# Lit les trois fichiers bruts de l'IFN sous <zone>/inputs/ifn/ (PLACETTE.csv, ARBRE.csv,
# FLORE.csv) et écrit sous <zone>/ifn/ les trois tables que lit `dynamics` :
#   plots.parquet   contrat prepare.ifn_plots
#   trees.parquet   contrat prepare.ifn_trees
#   flora.parquet   contrat prepare.ifn_flora
#
# En deux temps, pour qu'une entrée refusée ne laisse aucune sortie à moitié produite :
#   prepare_ifn_check()  valide les trois entrées (contrats inputs.ifn_*), les lit et construit
#                        les tables en mémoire ; n'écrit rien ; arrête (code 2 du module) au
#                        premier refus. `run_prepare()` l'appelle AVANT la première écriture
#                        de prepare (grid.tif, ...), les signalements allant dans
#                        rapport_prepare.html ;
#   prepare_ifn()        écrit les trois Parquet (writer commun write_parquet_tbl) et les fait
#                        valider (contrats prepare.ifn_*).
#
# Règles (docs/referentiels/ifn-placettes.md, IMOT 2025 p. 61 et 71) :
#  - `C13` est une circonférence en millimètres : d130 (cm) = C13 / (10 pi) ;
#  - les placettes ont des cercles emboîtés, choisis par classe de dimension sur C13 en mm
#    (IMOT 2025 p. 61, tableau DIMESS ; décision du 24/11/2026) :
#      C13 < 235 mm            non recensable : arbre écarté et signalé
#      235 à moins de 705 mm   cercle de 6 m
#      705 à moins de 1175 mm  cercle de 9 m
#      1175 mm et plus         cercle de 15 m
#    le poids d'un arbre (tiges/ha) est 10000 / (pi R^2), soit 88,4 ; 39,3 ; 14,1. La colonne
#    W du fichier brut n'est pas la référence : un désaccord est signalé, le poids du cercle
#    est retenu ;
#  - les coordonnées sont floutées (700 m) : les placettes sont marquées par `mark_ifn()` de
#    la garde (R/ifn_guard.R) et ne sont croisées avec aucun raster fin. Ce module n'ouvre
#    aucun raster.
#
# Signaler plutôt que deviner : arbres écartés, W en désaccord, colonnes laissées vides
# (`ser_code`, `trophic`, `coarse_hydric_700m`, `coarse_bioclim_700m`), CD_REF en TAXREF v13
# non convertis, tree_id fabriqué, HTOT <= 0 mis à NA : chacun est une ligne de
# rapport_prepare.html (section « IFN : ... »), jamais seulement un message sur la sortie d'erreur.

# Seuils sur C13 en mm (IMOT 2025 p. 61, tableau DIMESS).
IFN_C13_MIN_MM <- 235      # sous ce seuil, l'arbre n'est pas recensable
IFN_C13_9M_MM <- 705       # 705 mm et plus : cercle de 9 m
IFN_C13_15M_MM <- 1175     # 1175 mm et plus : cercle de 15 m

#' d130 en cm depuis C13 (circonférence en mm) : C13 / (10 pi).
ifn_d130_cm <- function(c13_mm) c13_mm / (10 * pi)

#' Rayon du cercle de placette (m) selon C13 (mm) : 6 m de 235 à moins de 705 mm, 9 m de 705 à
#' moins de 1175 mm, 15 m à partir de 1175 mm (IMOT 2025 p. 61, tableau DIMESS). NA sous le
#' seuil de 235 mm (arbre non recensable) ou si C13 est NA.
ifn_circle_radius_m <- function(c13_mm) {
  r <- rep(NA_real_, length(c13_mm))
  ok <- !is.na(c13_mm)
  r[ok & c13_mm >= IFN_C13_MIN_MM] <- 6
  r[ok & c13_mm >= IFN_C13_9M_MM] <- 9
  r[ok & c13_mm >= IFN_C13_15M_MM] <- 15
  r
}

#' Poids d'un arbre en tiges par hectare : inverse de la surface de son cercle.
ifn_weight_ha <- function(c13_mm) 10000 / (pi * ifn_circle_radius_m(c13_mm)^2)

.ifn_read_csv <- function(path, required) {
  if (!file.exists(path)) stop(sprintf("fichier IFN introuvable : %s", path), call. = FALSE)
  d <- utils::read.table(path, sep = ";", header = TRUE, colClasses = "character",
                         quote = "\"", comment.char = "", check.names = FALSE,
                         encoding = "UTF-8", stringsAsFactors = FALSE)
  missing_cols <- setdiff(required, names(d))
  if (length(missing_cols)) {
    stop(sprintf("%s : colonne(s) absente(s) : %s", basename(path),
                 paste(missing_cols, collapse = ", ")), call. = FALSE)
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

#' Construit les trois tables à partir des trois data.frames bruts (tout en chaîne). Pure : rien
#' n'est écrit, aucun message.
#'
#' @return liste `plots`, `trees`, `flora`, `report` (data.frame `section`, `text` : les
#'   signalements, en français).
ifn_tables <- function(plots_raw, trees_raw, flora_raw, precision_m = 700, taxref_version = "13") {
  report <- data.frame(section = character(0), text = character(0), stringsAsFactors = FALSE)
  add <- function(section, text) {
    report[nrow(report) + 1L, ] <<- list(section, text)
  }

  # ---- placettes
  plot_key <- paste(plots_raw$IDP, plots_raw$CAMPAGNE)
  if (anyDuplicated(plot_key)) {
    stop(sprintf("PLACETTE.csv : couple (IDP, CAMPAGNE) en double, ex. %s",
                 plot_key[duplicated(plot_key)][1]), call. = FALSE)
  }
  plots <- data.frame(
    plot_id = plots_raw$IDP,
    campaign = .ifn_campaign(plots_raw$CAMPAGNE, "PLACETTE.csv CAMPAGNE"),
    x = .ifn_num(plots_raw$XL, "PLACETTE.csv XL"),
    y = .ifn_num(plots_raw$YL, "PLACETTE.csv YL"),
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
  add("IFN : placettes", sprintf(
    "%d placette(s), coordonnées floutées (précision %s m), jamais croisées avec un raster fin",
    nrow(plots), fr_num(precision_m)))
  add("IFN : placettes", paste(
    "colonnes laissées vides (NA), source non branchée : ser_code, trophic (gradient trophique",
    "à la placette), coarse_hydric_700m et coarse_bioclim_700m ; dynamics ne peut pas s'en servir",
    "tant qu'elles ne sont pas remplies"))

  # ---- arbres
  t_camp <- .ifn_campaign(trees_raw$CAMPAGNE, "ARBRE.csv CAMPAGNE")
  unknown_keys <- setdiff(paste(trees_raw$IDP, t_camp), paste(plots$plot_id, plots$campaign))
  if (length(unknown_keys)) {
    stop(sprintf("ARBRE.csv : placette absente de PLACETTE.csv (IDP CAMPAGNE) : %s",
                 unknown_keys[1]), call. = FALSE)
  }
  c13 <- .ifn_num(trees_raw$C13, "ARBRE.csv C13")
  if (any(!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees_raw$ESPAR))) {
    stop(sprintf("ARBRE.csv : code ESPAR invalide (ex. « %s »)",
                 trees_raw$ESPAR[!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees_raw$ESPAR)][1]), call. = FALSE)
  }
  h_present <- "HTOT" %in% names(trees_raw)
  h <- if (h_present) .ifn_num(trees_raw$HTOT, "ARBRE.csv HTOT") else rep(NA_real_, nrow(trees_raw))
  n_low <- sum(!is.na(c13) & c13 > 0 & c13 < 100)
  if (n_low > 0L) {
    # Garde-fou sur l'unité (référentiel §2) : un c13 courant est de 300 à 2000, pas de 30 à 200.
    add("IFN : arbres", sprintf(
      "%d arbre(s) avec C13 entre 0 et 100 : vérifier que C13 est bien en mm", n_low))
  }
  radius <- ifn_circle_radius_m(c13)
  kept <- !is.na(radius)
  n_na <- sum(is.na(c13))
  n_below <- sum(!is.na(c13) & c13 < IFN_C13_MIN_MM)
  if (n_na > 0L) {
    add("IFN : arbres", sprintf("%d arbre(s) écarté(s) : C13 manquant", n_na))
  }
  if (n_below > 0L) {
    add("IFN : arbres", sprintf(
      "%d arbre(s) écarté(s) : C13 sous le seuil de recensabilité de %d mm (IMOT 2025 p. 61)",
      n_below, IFN_C13_MIN_MM))
  }
  w <- 10000 / (pi * radius^2)
  made_up_id <- !"ARBRE" %in% names(trees_raw)
  tree_ids <- if (!made_up_id) trees_raw$ARBRE else {
    stats::ave(seq_along(trees_raw$IDP), trees_raw$IDP, t_camp, FUN = seq_along)
  }
  if (made_up_id) {
    add("IFN : arbres", paste(
      "colonne ARBRE absente de ARBRE.csv : tree_id fabriqué (numéro d'ordre de la ligne dans sa",
      "placette et sa campagne), valable pour ce fichier seulement"))
  }
  h_null <- !is.na(h) & h <= 0
  if (!h_present) {
    add("IFN : arbres", "colonne HTOT absente de ARBRE.csv : h vide (NA) pour tous les arbres")
  } else if (any(h_null[kept])) {
    add("IFN : arbres", sprintf(
      "%d arbre(s) avec HTOT inférieure ou égale à 0 : h mis à NA (pas de hauteur mesurée)",
      sum(h_null[kept])))
  }
  trees <- data.frame(
    plot_id = trees_raw$IDP,
    campaign = t_camp,
    tree_id = as.character(tree_ids),
    species = trees_raw$ESPAR,
    d130 = ifn_d130_cm(c13),
    h = ifelse(!is.na(h) & h > 0, h, NA_real_),
    weight_ha = w,
    stringsAsFactors = FALSE
  )[kept, , drop = FALSE]
  if (anyDuplicated(trees[, c("plot_id", "campaign", "tree_id")])) {
    stop("ARBRE.csv : (IDP, CAMPAGNE, ARBRE) en double", call. = FALSE)
  }
  if ("W" %in% names(trees_raw)) {
    w_raw <- .ifn_num(trees_raw$W, "ARBRE.csv W")[kept]
    disagree <- !is.na(w_raw) & abs(w_raw - trees$weight_ha) > 0.01 * trees$weight_ha
    if (any(disagree)) {
      add("IFN : arbres", sprintf(
        "%d arbre(s) dont la colonne W du fichier diffère de plus de 1 %% du poids du cercle (ex. W = %s contre %s) ; le poids du cercle (IMOT 2025 p. 61) est retenu",
        sum(disagree), fr_num(w_raw[disagree][1], 2), fr_num(trees$weight_ha[disagree][1], 2)))
    }
  }
  rownames(trees) <- NULL
  add("IFN : arbres", sprintf(
    "%d arbre(s) retenus sur %d ; d130 = C13 / (10 pi) ; poids par cercle de 6, 9 ou 15 m",
    nrow(trees), nrow(trees_raw)))

  # ---- flore
  f_camp <- .ifn_campaign(flora_raw$CAMPAGNE, "FLORE.csv CAMPAGNE")
  unknown_keys <- setdiff(paste(flora_raw$IDP, f_camp), paste(plots$plot_id, plots$campaign))
  if (length(unknown_keys)) {
    stop(sprintf("FLORE.csv : placette absente de PLACETTE.csv (IDP CAMPAGNE) : %s",
                 unknown_keys[1]), call. = FALSE)
  }
  cd <- .ifn_num(flora_raw$CD_REF, "FLORE.csv CD_REF")
  if (anyNA(cd) || any(cd != round(cd)) || any(cd < 1)) {
    stop("FLORE.csv : CD_REF manquant ou non entier positif", call. = FALSE)
  }
  ab <- .ifn_num(flora_raw$ABOND, "FLORE.csv ABOND")
  flora <- data.frame(
    plot_id = flora_raw$IDP,
    campaign = f_camp,
    cd_ref = as.integer(cd),
    taxref_version = taxref_version,
    abundance = ab,
    stringsAsFactors = FALSE
  )
  add("IFN : flore", sprintf("%d ligne(s) de relevé floristique", nrow(flora)))
  add("IFN : flore", sprintf(
    "CD_REF en TAXREF v%s (version de l'IFN) NON convertis en v18 : taxref_version = « %s » ; à convertir avant toute jointure avec contracts/species.csv (v18)",
    taxref_version, taxref_version))

  list(plots = plots, trees = trees, flora = flora, report = report)
}

#' Contrôle et lit les entrées IFN d'une zone, sans rien écrire (à appeler AVANT la première
#' écriture de prepare). Chaque fichier doit exister et passer son contrat `inputs.ifn_*`
#' (`validate = TRUE`) ; les tables sont ensuite construites en mémoire. Au premier refus, arrête
#' avec un message en français (code 2 du module).
#'
#' @param zone_dir dossier de la zone (`tests/fixtures/zone_fictive` ou `data/<zone>`).
#' @param report rapport de prepare (`new_report()`) où ajouter les signalements ; absent,
#'   un rapport est créé (les lignes sont dites par `message()`, rien n'est écrit).
#' @param precision_m précision de localisation écrite dans `loc_precision_m` (700 m, IGN :
#'   centre de la maille de 1 km, écart maximal 700 m).
#' @param taxref_version version TAXREF des CD_REF lus (« 13 » : version de l'IFN).
#' @return liste invisible `plots`, `trees`, `flora`, `report` (data.frame des signalements).
prepare_ifn_check <- function(zone_dir, report = NULL, precision_m = 700, taxref_version = "13",
                              validate = TRUE) {
  if (is.null(report)) report <- new_report()
  dir_in <- file.path(zone_dir, "inputs", "ifn")
  paths <- c(inputs.ifn_placette = file.path(dir_in, "PLACETTE.csv"),
             inputs.ifn_arbre = file.path(dir_in, "ARBRE.csv"),
             inputs.ifn_flore = file.path(dir_in, "FLORE.csv"))
  for (k in seq_along(paths)) check_input_file(paths[[k]])
  if (validate) {
    for (k in seq_along(paths)) validate_file(names(paths)[k], paths[[k]], what = "entrée")
  }
  res <- ifn_tables(
    .ifn_read_csv(paths[["inputs.ifn_placette"]], c("CAMPAGNE", "IDP", "XL", "YL")),
    .ifn_read_csv(paths[["inputs.ifn_arbre"]], c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    .ifn_read_csv(paths[["inputs.ifn_flore"]], c("CAMPAGNE", "IDP", "CD_REF", "ABOND")),
    precision_m = precision_m, taxref_version = taxref_version
  )
  for (i in seq_len(nrow(res$report))) report_add(report, res$report$section[i], res$report$text[i])
  invisible(res)
}

IFN_PLOTS_TYPES <- c(plot_id = "string", campaign = "int32", x = "float64", y = "float64",
                     loc_precision_m = "float64", source = "string", ser_code = "string",
                     trophic = "float64", coarse_hydric_700m = "float64",
                     coarse_bioclim_700m = "float64")
IFN_TREES_TYPES <- c(plot_id = "string", campaign = "int32", tree_id = "string",
                     species = "string", d130 = "float64", h = "float64", weight_ha = "float64")
IFN_FLORA_TYPES <- c(plot_id = "string", campaign = "int32", cd_ref = "int32",
                     taxref_version = "string", abundance = "float64")

#' Écrit les tables IFN d'une zone (`ifn/plots.parquet`, `trees.parquet`, `flora.parquet`) et les
#' fait valider par les contrats `prepare.ifn_*`. `checked` : résultat de `prepare_ifn_check()`
#' déjà fait par `run_prepare()` ; absent, le contrôle est fait ici d'abord (rien n'est écrit
#' avant qu'il soit passé).
#'
#' @return liste invisible `plots`, `trees`, `flora`, `report`, `files`.
prepare_ifn <- function(zone_dir, checked = NULL, report = NULL, precision_m = 700,
                        taxref_version = "13", validate = TRUE) {
  res <- if (is.null(checked)) {
    prepare_ifn_check(zone_dir, report, precision_m, taxref_version, validate)
  } else checked
  out <- file.path(zone_dir, "ifn")
  files <- c(
    plots = write_parquet_tbl(res$plots, file.path(out, "plots.parquet"), IFN_PLOTS_TYPES),
    trees = write_parquet_tbl(res$trees, file.path(out, "trees.parquet"), IFN_TREES_TYPES),
    flora = write_parquet_tbl(res$flora, file.path(out, "flora.parquet"), IFN_FLORA_TYPES)
  )
  if (validate) {
    contracts_by_table <- c(plots = "prepare.ifn_plots", trees = "prepare.ifn_trees",
                  flora = "prepare.ifn_flora")
    for (k in names(contracts_by_table)) validate_file(contracts_by_table[[k]], files[[k]])
  }
  invisible(c(res, list(files = files)))
}
