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
# Règles (docs/referentiels/ifn-placettes.md, ifn-dynamique.md ; décisions du 25/11/2026) :
#  - `C13` est une circonférence en MÈTRES, comme dans l'export des données brutes
#    (metadonnees.csv l. 35 et 203) : d130 (cm) = C13 x 100 / pi ;
#  - les placettes ont des cercles emboîtés, choisis par classe de dimension sur C13 en m
#    (IMOT 2025 p. 61, tableau DIMESS ; ARBRE p. 1 ; le seuil et les bornes sont ceux de l'IMOT,
#    saisis en mm, et valent 0,235 / 0,705 / 1,175 m dans l'export) :
#      C13 < 0,235 m           non recensable : arbre écarté et signalé (1re visite)
#      0,235 à moins de 0,705  cercle de 6 m
#      0,705 à moins de 1,175  cercle de 9 m
#      1,175 m et plus         cercle de 15 m
#    le poids d'un arbre de 1re visite (tiges/ha) est 10000 / (pi R^2), soit 88,4 ; 39,3 ; 14,1.
#    La colonne W du fichier brut n'est pas la référence : un désaccord est signalé, le poids du
#    cercle est retenu. Un arbre de 2e visite (y compris une recrue, cherchée sur un cercle
#    qui n'est pas documenté) garde le W de l'export, vide s'il manque : jamais deviné ;
#  - une ligne par arbre et par visite : la 2e visite d'un point garde son IDP et sa campagne
#    vaut celle de la 1re plus 5 ; `VISITE` vient de PLACETTE.csv ; la jointure par (IDP, A)
#    est faite par `dynamics`, pas ici (spec §6, « Données d'ajustement ») ;
#  - nouvelles colonnes (ifn-dynamique-colonnes.csv) : VEGET (1re visite), VEGET5 (2e visite,
#    codes selon la campagne), IR5 (m, cumul de 5 cernes, une partie des arbres seulement) ;
#    VISITE, DATEPOINT, NINCID, INCID, PRELEV5, DEF5, INSTP5 aux placettes ;
#  - les coordonnées sont floutées (700 m) : les placettes sont marquées par `mark_ifn()` de
#    la garde (R/ifn_guard.R) et ne sont croisées avec aucun raster fin. Ce fichier n'ouvre
#    aucun raster ; R/ifn_station.R ne lit station_gradients.tif et ser.tif qu'en disque de 700 m,
#    par la garde.
#
# V (volume bois fort tige, m3, repris sans conversion) : colonne `V` de ARBRE.csv gardée telle
# quelle dans `stem_volume_m3` de trees.parquet (mission 055 ; docs/plans/post-volume-carbone.md, mission F).
# Définition : IGN_DB_doc_arbre.pdf p. 9 « tige principale jusqu'à la découpe bois fort (7 cm fin
# bout) », volume « réfacté » ; metadonnees.csv l. 174 « volume du tronc [...] du sol jusqu'à une
# découpe de 7 cm, incluant l'écorce et une branche maîtresse » (les deux libellés diffèrent, voir
# docs/referentiels/volume-carbone.md §4.3). Colonne absente ou vide : NA et dit, jamais calculée
# ni complétée. V n'est lu que sur l'arbre ; il ne passe par aucun raster.
#
# Station à la placette (`ser_code`, `trophic`, `coarse_hydric_700m`, `coarse_bioclim_700m`) :
# R/ifn_station.R (mission 024), appelé ci-dessous dans prepare_ifn_check() et prepare_ifn().
#
# Signaler plutôt que deviner : arbres écartés, W en désaccord, CD_REF en TAXREF v13
# non convertis, tree_id fabriqué, HTOT <= 0 mis à NA, colonnes de la dynamique absentes, vides
# ou hors modalités de leur campagne : chacun est une ligne de rapport_prepare.html (section
# « IFN : ... »), jamais seulement un message sur la sortie d'erreur. Une valeur hors modalités
# est mise à vide (NA) et comptée ; elle n'est jamais remplacée.

# Seuils sur C13 en m (IMOT 2025 p. 61, tableau DIMESS ; ARBRE p. 1 et 7).
IFN_C13_MIN_M <- 0.235     # sous ce seuil, l'arbre n'est pas recensable (D13 de 7,5 cm)
IFN_C13_9M_M <- 0.705      # 0,705 m et plus : cercle de 9 m
IFN_C13_15M_M <- 1.175     # 1,175 m et plus : cercle de 15 m
# Garde-fou d'unité : un C13 de plus de 10 m (3,2 m de diamètre) est une erreur d'unité, pas un
# arbre ; l'export réel va de 0,235 à 2,6 m (ifn-dynamique.md §3).
IFN_C13_MAX_M <- 10

# Modalités de VEGET selon la campagne (metadonnees.csv l. 372-375, 6067-6074) : DOM8M1 de 2008 à
# 2018, DOM8M2 depuis 2019 ; avant 2008 l'unité n'est pas documentée (aucun contrôle de période).
IFN_VEGET_CODES <- function(campaign) {
  if (campaign >= 2019) c("0", "1", "5", "C") else if (campaign >= 2008) c("0", "A", "5", "C") else NULL
}
# Modalités de VEGET5 selon la campagne de la ligne de 2e visite (metadonnees.csv l. 6075-6099) :
# VEGET5 (2010-14), VEGET56 (2015-16), VEGET57 (2017-18), VEGET59 (2019-). Avant 2010 : aucune.
IFN_VEGET5_CODES <- function(campaign) {
  if (campaign >= 2019) c("0", "6", "7", "1", "2", "M", "N", "T")
  else if (campaign >= 2017) c("0", "6", "7", "A", "M", "N", "T")
  else if (campaign >= 2015) c("0", "M", "A", "6", "N")
  else if (campaign >= 2010) c("0", "6", "A", "5", "C")
  else character(0)
}
# Rangement des codes de VEGET5 pour le rapport (libellés des modalités de l'export ; aucune
# décision de modèle ici : dynamics tranche).
IFN_VEGET5_CLASSES <- c("0" = "vivant", "1" = "chablis vivant", "A" = "chablis", "2" = "chablis mort",
                        "5" = "mort sur pied", "M" = "mort sur pied", "C" = "mort cassé",
                        "6" = "coupé", "7" = "coupé", "N" = "non retrouvé",
                        "T" = "cassé sous C13 ou perdu après incident")

#' d130 en cm depuis C13 (circonférence en m) : C13 x 100 / pi.
ifn_d130_cm <- function(c13_m) c13_m * 100 / pi

#' Rayon du cercle de placette (m) selon C13 (m) : 6 m de 0,235 à moins de 0,705 m, 9 m de 0,705 à
#' moins de 1,175 m, 15 m à partir de 1,175 m (IMOT 2025 p. 61, tableau DIMESS). NA sous le
#' seuil de 0,235 m (arbre non recensable) ou si C13 est NA.
ifn_circle_radius_m <- function(c13_m) {
  r <- rep(NA_real_, length(c13_m))
  ok <- !is.na(c13_m)
  r[ok & c13_m >= IFN_C13_MIN_M] <- 6
  r[ok & c13_m >= IFN_C13_9M_M] <- 9
  r[ok & c13_m >= IFN_C13_15M_M] <- 15
  r
}

#' Poids d'un arbre en tiges par hectare : inverse de la surface de son cercle.
ifn_weight_ha <- function(c13_m) 10000 / (pi * ifn_circle_radius_m(c13_m)^2)

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
  if (!"VISITE" %in% names(plots_raw)) {
    stop("PLACETTE.csv : colonne VISITE absente (1re ou 2e visite : sans elle, les deux visites d'un point ne se distinguent pas)",
         call. = FALSE)
  }
  visit <- .ifn_num(plots_raw$VISITE, "PLACETTE.csv VISITE")
  if (anyNA(visit) || !all(visit %in% c(1, 2))) {
    stop("PLACETTE.csv : VISITE manquante ou différente de 1 et 2", call. = FALSE)
  }
  n_plots <- nrow(plots_raw)
  # Colonne entière facultative : absente -> vide et dit ; hors modalités -> vide et compté.
  opt_int <- function(col, lo, hi, what) {
    if (!col %in% names(plots_raw)) {
      add("IFN : placettes", sprintf(
        "colonne %s absente de PLACETTE.csv (%s) : vide (NA) pour toutes les placettes", col, what))
      return(rep(NA_integer_, n_plots))
    }
    v <- .ifn_num(plots_raw[[col]], paste("PLACETTE.csv", col))
    bad <- !is.na(v) & (v != round(v) | v < lo | v > hi)
    if (any(bad)) {
      add("IFN : placettes", sprintf(
        "%d valeur(s) de %s hors modalités (%d à %d), mises à vide (NA), ex. %s",
        sum(bad), col, lo, hi, fr_num(v[bad][1])))
      v[bad] <- NA_real_
    }
    as.integer(v)
  }
  incident_nature <- opt_int("NINCID", 0L, 5L, "incident des 5 ans avant la 1re visite, depuis 2015")
  incident_intensity <- opt_int("INCID", 0L, 4L, "intensité de l'incident, depuis 2009")
  clearing_5y <- opt_int("DEF5", 0L, 5L, "défrichement entre les deux visites, depuis 2017")
  planting_5y <- opt_int("INSTP5", 0L, 1L, "installation de peuplement entre les deux visites, depuis 2015")
  if ("PRELEV5" %in% names(plots_raw)) {
    harvest_5y <- trimws(plots_raw$PRELEV5)
    harvest_5y[harvest_5y == ""] <- NA_character_
    n_h <- sum(!is.na(harvest_5y))
    camp_p <- .ifn_campaign(plots_raw$CAMPAGNE, "PLACETTE.csv CAMPAGNE")
    out_years <- !is.na(harvest_5y) & (camp_p < 2010 | camp_p > 2014)
    add("IFN : placettes", sprintf(
      "PRELEV5 renseignée sur %d placette(s), recopiée telle quelle : l'export ne documente ni unité ni modalités (valable de 2010 à 2014 seulement)",
      n_h))
    if (any(out_years)) {
      add("IFN : placettes", sprintf(
        "%d valeur(s) de PRELEV5 hors de ses années de validité (2010-2014), conservées telles quelles",
        sum(out_years)))
    }
  } else {
    harvest_5y <- rep(NA_character_, n_plots)
    add("IFN : placettes", paste(
      "colonne PRELEV5 absente de PLACETTE.csv : harvest_5y vide (NA) ; un prélèvement entre les",
      "deux visites ne peut pas être détecté par cette colonne"))
  }
  # DATEPOINT : JJ/MM/AAAA -> AAAA-MM-JJ ; absente ou vide : vide et dit, jamais complétée ;
  # impossible (31/02) ou illisible : entrée refusée (code 2).
  date_point <- rep(NA_character_, n_plots)
  if ("DATEPOINT" %in% names(plots_raw)) {
    raw_d <- trimws(plots_raw$DATEPOINT)
    parsed <- as.Date(ifelse(raw_d == "", NA_character_, raw_d), format = "%d/%m/%Y")
    bad_d <- raw_d != "" & is.na(parsed)
    if (any(bad_d)) {
      stop(sprintf(
        "PLACETTE.csv : %d DATEPOINT impossible(s) ou illisible(s) (attendu une date réelle JJ/MM/AAAA), ex. « %s » : entrée refusée, aucune date n'est devinée",
        sum(bad_d), raw_d[bad_d][1]), call. = FALSE)
    }
    date_point <- format(parsed, "%Y-%m-%d")
  } else {
    add("IFN : placettes", paste(
      "colonne DATEPOINT absente de PLACETTE.csv : date_point vide (NA) ; dynamics comptera",
      "5 ans entre les deux visites et le dira"))
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
  plots$visit <- as.integer(visit)
  plots$date_point <- date_point
  plots$incident_nature <- incident_nature
  plots$incident_intensity <- incident_intensity
  plots$harvest_5y <- harvest_5y
  plots$clearing_5y <- clearing_5y
  plots$planting_5y <- planting_5y
  plots <- plots[, c("plot_id", "campaign", "x", "y", "loc_precision_m", "source",
                     "ser_code", "trophic", "coarse_hydric_700m", "coarse_bioclim_700m",
                     "visit", "date_point", "incident_nature", "incident_intensity",
                     "harvest_5y", "clearing_5y", "planting_5y")]
  add("IFN : placettes", sprintf(
    "%d placette(s), coordonnées floutées (précision %s m), jamais croisées avec un raster fin",
    nrow(plots), fr_num(precision_m)))
  add("IFN : placettes", paste(
    "colonnes de station ser_code, trophic, coarse_hydric_700m et coarse_bioclim_700m : remplies",
    "par R/ifn_station.R, voir la section « IFN : station »"))
  v1 <- plots$visit == 1L
  v2 <- plots$visit == 2L
  add("IFN : placettes", sprintf("%d ligne(s) de 1re visite, %d de 2e visite (une ligne par visite)",
                                 sum(v1), sum(v2)))
  # Les deux visites d'un point : même IDP, campagne de la 2e = campagne de la 1re + 5.
  first_camp <- plots$campaign[v1][match(plots$plot_id[v2], plots$plot_id[v1])]
  no_first <- is.na(first_camp)
  bad_gap <- !no_first & plots$campaign[v2] != first_camp + 5L
  if (any(no_first)) {
    add("IFN : placettes", sprintf(
      "%d placette(s) de 2e visite sans ligne de 1re visite de même IDP (ex. %s) : jointure impossible",
      sum(no_first), plots$plot_id[v2][no_first][1]))
  }
  if (any(bad_gap)) {
    add("IFN : placettes", sprintf(
      "%d placette(s) dont la 2e visite n'est pas 5 campagnes après la 1re (ex. %s : %d puis %d)",
      sum(bad_gap), plots$plot_id[v2][bad_gap][1], first_camp[bad_gap][1],
      plots$campaign[v2][bad_gap][1]))
  }
  # Intervalle réel entre les deux visites (DATEPOINT), sinon 5 ans à la charge de dynamics.
  d1 <- as.Date(plots$date_point[v1][match(plots$plot_id[v2], plots$plot_id[v1])])
  d2 <- as.Date(plots$date_point[v2])
  both <- !is.na(d1) & !is.na(d2)
  if (any(v2)) {
    if (any(both)) {
      yrs <- as.numeric(d2[both] - d1[both]) / 365.25
      add("IFN : placettes", sprintf(
        "intervalle entre visites d'après DATEPOINT : de %s à %s ans sur %d placette(s) ; %d placette(s) sans les deux dates : 5 ans supposés par dynamics",
        fr_num(min(yrs), 2), fr_num(max(yrs), 2), sum(both), sum(!both)))
    } else {
      add("IFN : placettes", "aucune placette de 2e visite avec les deux DATEPOINT : intervalle de 5 ans supposé par dynamics")
    }
  }
  if ("NINCID" %in% names(plots_raw) || "INCID" %in% names(plots_raw)) {
    n_inc <- sum(v1 & ((!is.na(plots$incident_nature) & plots$incident_nature >= 1L) |
                         (!is.na(plots$incident_intensity) & plots$incident_intensity >= 1L)))
    n_miss <- sum(v1 & is.na(plots$incident_nature) & is.na(plots$incident_intensity))
    add("IFN : placettes", sprintf(
      "%d placette(s) de 1re visite avec un incident (NINCID 1 à 5 ou INCID 1 à 4), écartées par dynamics ; %d de 1re visite sans NINCID ni INCID (vides)",
      n_inc, n_miss))
  }
  n_def <- sum(v2 & ((!is.na(plots$clearing_5y) & plots$clearing_5y >= 1L) |
                       (!is.na(plots$planting_5y) & plots$planting_5y >= 1L)))
  if (any(v2)) {
    add("IFN : placettes", sprintf(
      "%d placette(s) de 2e visite avec défrichement (DEF5 1 à 5) ou installation de peuplement (INSTP5 = 1) entre les visites, écartées par dynamics",
      n_def))
  }

  # ---- arbres
  t_camp <- .ifn_campaign(trees_raw$CAMPAGNE, "ARBRE.csv CAMPAGNE")
  plot_keys <- paste(plots$plot_id, plots$campaign)
  unknown_keys <- setdiff(paste(trees_raw$IDP, t_camp), plot_keys)
  if (length(unknown_keys)) {
    stop(sprintf("ARBRE.csv : placette absente de PLACETTE.csv (IDP CAMPAGNE) : %s",
                 unknown_keys[1]), call. = FALSE)
  }
  t_visit <- plots$visit[match(paste(trees_raw$IDP, t_camp), plot_keys)]
  is_v2 <- t_visit == 2L
  c13 <- .ifn_num(trees_raw$C13, "ARBRE.csv C13")
  if (any(!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees_raw$ESPAR))) {
    stop(sprintf("ARBRE.csv : code ESPAR invalide (ex. « %s »)",
                 trees_raw$ESPAR[!grepl("^[0-9]{2}[A-Z0-9]{0,3}$", trees_raw$ESPAR)][1]), call. = FALSE)
  }
  h_present <- "HTOT" %in% names(trees_raw)
  h <- if (h_present) .ifn_num(trees_raw$HTOT, "ARBRE.csv HTOT") else rep(NA_real_, nrow(trees_raw))
  if (any(!is.na(c13) & c13 > IFN_C13_MAX_M)) {
    # Garde-fou sur l'unité (référentiel ifn-dynamique §3) : l'export donne C13 en mètres.
    stop(sprintf(
      "ARBRE.csv : C13 de %s ou plus (ex. %s) : C13 est attendu en mètres (0,235 à 2,6 m dans l'export), pas en millimètres",
      fr_num(IFN_C13_MAX_M), fr_num(max(c13, na.rm = TRUE))), call. = FALSE)
  }
  radius <- ifn_circle_radius_m(c13)
  # 1re visite : arbre non recensable ou sans C13 écarté et dit. 2e visite : toute ligne est gardée
  # (arbre coupé ou non retrouvé sans C13, arbre remesuré sous le seuil) ; d130 et weight_ha vides.
  kept <- is_v2 | !is.na(radius)
  n_na <- sum(!is_v2 & is.na(c13))
  n_below <- sum(!is_v2 & !is.na(c13) & c13 < IFN_C13_MIN_M)
  if (n_na > 0L) {
    add("IFN : arbres", sprintf("%d arbre(s) de 1re visite écarté(s) : C13 manquant", n_na))
  }
  if (n_below > 0L) {
    add("IFN : arbres", sprintf(
      "%d arbre(s) de 1re visite écarté(s) : C13 sous le seuil de recensabilité de %s m (IMOT 2025 p. 61)",
      n_below, fr_num(IFN_C13_MIN_M)))
  }
  made_up_id <- !"A" %in% names(trees_raw)
  if (made_up_id) {
    if (any(is_v2)) {
      stop("ARBRE.csv : colonne A absente alors que des placettes sont en 2e visite : les deux visites d'un arbre ne se joignent que par (IDP, A)",
           call. = FALSE)
    }
    tree_ids <- stats::ave(seq_along(trees_raw$IDP), trees_raw$IDP, t_camp, FUN = seq_along)
    add("IFN : arbres", paste(
      "colonne A absente de ARBRE.csv : tree_id fabriqué (numéro d'ordre de la ligne dans sa",
      "placette et sa campagne), valable pour ce fichier seulement"))
  } else {
    a_num <- .ifn_num(trees_raw$A, "ARBRE.csv A")
    if (anyNA(a_num) || any(a_num != round(a_num)) || any(a_num < 1)) {
      stop("ARBRE.csv : numéro d'arbre A manquant ou non entier positif", call. = FALSE)
    }
    tree_ids <- as.character(as.integer(a_num))
  }
  h_null <- !is.na(h) & h <= 0
  if (!h_present) {
    add("IFN : arbres", "colonne HTOT absente de ARBRE.csv : h vide (NA) pour tous les arbres")
  } else if (any(h_null[kept])) {
    add("IFN : arbres", sprintf(
      "%d arbre(s) avec HTOT inférieure ou égale à 0 : h mis à NA (pas de hauteur mesurée)",
      sum(h_null[kept])))
  }

  # Colonnes de la dynamique : chaîne facultative, vide -> NA.
  txt_col <- function(col) {
    if (!col %in% names(trees_raw)) return(NULL)
    v <- trimws(trees_raw[[col]])
    v[v == ""] <- NA_character_
    v
  }
  # VEGET : état à la 1re visite ; modalités selon la campagne.
  veg <- txt_col("VEGET")
  if (is.null(veg)) {
    add("IFN : arbres", "colonne VEGET absente de ARBRE.csv : veg_state vide (NA) ; dynamics ne peut pas isoler les arbres vivants à la 1re visite")
    veg <- rep(NA_character_, nrow(trees_raw))
  } else {
    if (any(!is_v2 & is.na(veg))) {
      add("IFN : arbres", sprintf("%d arbre(s) de 1re visite sans VEGET (vide) : état à la 1re visite inconnu",
                                  sum(!is_v2 & is.na(veg))))
    }
    bad_v <- rep(FALSE, length(veg))
    for (cp in unique(t_camp[!is.na(veg)])) {
      ok_codes <- IFN_VEGET_CODES(cp)
      if (!is.null(ok_codes)) bad_v <- bad_v | (t_camp == cp & !is.na(veg) & !veg %in% ok_codes)
    }
    if (any(bad_v)) {
      add("IFN : arbres", sprintf(
        "%d valeur(s) de VEGET hors modalités de leur campagne (DOM8M1 2008-2018 : 0, A, 5, C ; DOM8M2 depuis 2019 : 0, 1, 5, C), mises à vide (NA), ex. « %s » en %d",
        sum(bad_v), veg[bad_v][1], t_camp[bad_v][1]))
      veg[bad_v] <- NA_character_
    }
  }
  # VEGET5 : état à la 2e visite ; modalités selon la campagne de la ligne.
  veg5 <- txt_col("VEGET5")
  if (is.null(veg5)) {
    add("IFN : arbres", paste(
      "colonne VEGET5 absente de ARBRE.csv (export d'avant 2010 ?) : veg_state_5y vide (NA) ;",
      "aucune mortalité ne peut être ajustée"))
    veg5 <- rep(NA_character_, nrow(trees_raw))
  } else {
    if (any(is_v2 & is.na(veg5))) {
      add("IFN : arbres", sprintf("%d ligne(s) de 2e visite sans VEGET5 (vide) : état à la 2e visite inconnu",
                                  sum(is_v2 & is.na(veg5))))
    }
    if (any(!is_v2 & !is.na(veg5))) {
      add("IFN : arbres", sprintf(
        "%d ligne(s) de 1re visite avec VEGET5 renseigné (attendu vide) : conservé tel quel",
        sum(!is_v2 & !is.na(veg5))))
    }
    bad_5 <- rep(FALSE, length(veg5))
    for (cp in unique(t_camp[!is.na(veg5)])) {
      bad_5 <- bad_5 | (t_camp == cp & !is.na(veg5) & !veg5 %in% IFN_VEGET5_CODES(cp))
    }
    if (any(bad_5)) {
      add("IFN : arbres", sprintf(
        "%d valeur(s) de VEGET5 hors modalités de leur campagne (VEGET5 2010-14, VEGET56 2015-16, VEGET57 2017-18, VEGET59 depuis 2019), mises à vide (NA), ex. « %s » en %d",
        sum(bad_5), veg5[bad_5][1], t_camp[bad_5][1]))
      veg5[bad_5] <- NA_character_
    }
    seen5 <- veg5[is_v2 & !is.na(veg5)]
    if (length(seen5)) {
      cls <- unname(IFN_VEGET5_CLASSES[seen5])
      tab <- table(cls)
      add("IFN : arbres", sprintf("VEGET5 des lignes de 2e visite : %s",
                                  paste(sprintf("%s %d", names(tab), as.integer(tab)), collapse = " ; ")))
    }
  }
  # IR5 : accroissement radial de 5 ans (m), une partie des arbres seulement.
  ir5 <- if ("IR5" %in% names(trees_raw)) .ifn_num(trees_raw$IR5, "ARBRE.csv IR5") else NULL
  if (is.null(ir5)) {
    add("IFN : arbres", "colonne IR5 absente de ARBRE.csv : radial_incr_5y_m vide (NA) ; aucun accroissement à ajuster par IR5")
    ir5 <- rep(NA_real_, nrow(trees_raw))
  } else {
    if (any(!is.na(ir5) & ir5 < 0)) {
      stop("ARBRE.csv : IR5 négatif (accroissement radial en m, attendu positif ou nul)", call. = FALSE)
    }
    live <- !is.na(c13) & (is.na(veg5) | veg5 == "0")
    add("IFN : arbres", sprintf(
      "IR5 (m) renseigné sur %d ligne(s) sur %d (%s %%) ; absent = non mesuré, jamais complété",
      sum(!is.na(ir5)), length(ir5), fr_num(100 * mean(!is.na(ir5)), 1)))
    if (any(!is.na(ir5) & !live)) {
      add("IFN : arbres", sprintf("%d ligne(s) avec IR5 renseigné sur un arbre sans C13 ou non vivant à la 2e visite : conservées telles quelles",
                                  sum(!is.na(ir5) & !live)))
    }
  }
  # V : volume bois fort tige en m3 de l'export, repris sans conversion ; vide -> NA, jamais deviné.
  v_present <- "V" %in% names(trees_raw)
  vol <- if (v_present) .ifn_num(trees_raw$V, "ARBRE.csv V") else rep(NA_real_, nrow(trees_raw))
  if (any(!is.na(vol) & vol < 0)) {
    stop("ARBRE.csv : V négatif (volume en m3, attendu positif ou nul)", call. = FALSE)
  }
  if (!v_present) {
    add("IFN : arbres", "colonne V absente de ARBRE.csv : stem_volume_m3 vide (NA) pour tous les arbres ; aucune comparaison au volume de l'IFN possible")
  } else {
    n_v <- sum(!is.na(vol[kept])); n_k <- sum(kept)
    add("IFN : arbres", sprintf(
      "stem_volume_m3 (m3, colonne V de ARBRE.csv : volume bois fort tige de l'IFN, repris sans conversion) renseigné sur %d ligne(s) retenue(s) sur %d (%s %%) ; absent = vide (NA), jamais calculé",
      n_v, n_k, fr_num(if (n_k > 0L) 100 * n_v / n_k else 0, 1)))
    if (any(!is.na(vol[kept]) & is.na(c13[kept]))) {
      add("IFN : arbres", sprintf("%d ligne(s) avec V mais sans C13 : conservées telles quelles",
                                  sum(!is.na(vol[kept]) & is.na(c13[kept]))))
    }
  }
  # Poids : 1re visite, cercle de la classe ; 2e visite, W de l'export, vide s'il manque.
  w_raw_all <- if ("W" %in% names(trees_raw)) .ifn_num(trees_raw$W, "ARBRE.csv W") else rep(NA_real_, nrow(trees_raw))
  w <- ifelse(is_v2, w_raw_all, 10000 / (pi * radius^2))
  if (any(is_v2)) {
    no_w <- is_v2 & !is.na(c13) & is.na(w_raw_all)
    if (any(no_w)) {
      add("IFN : arbres", sprintf(
        "%d arbre(s) de 2e visite avec C13 mais sans W : weight_ha vide (le cercle de recherche d'une recrue n'est pas documenté, poids non deviné)",
        sum(no_w)))
    }
    n_noc13 <- sum(is_v2 & is.na(c13))
    if (n_noc13 > 0L) {
      alive_noc13 <- sum(is_v2 & is.na(c13) & !is.na(veg5) & veg5 == "0")
      add("IFN : arbres", sprintf(
        "%d ligne(s) de 2e visite sans C13 : d130 et weight_ha vides (coupés, non retrouvés attendus)%s",
        n_noc13, if (alive_noc13 > 0L) sprintf(" ; dont %d déclarée(s) vivante(s) (VEGET5 = 0) : anormal", alive_noc13) else ""))
    }
    n_under <- sum(is_v2 & !is.na(c13) & c13 < IFN_C13_MIN_M)
    if (n_under > 0L) {
      add("IFN : arbres", sprintf(
        "%d ligne(s) de 2e visite avec C13 sous le seuil de %s m (remesure sous le seuil) : conservées, sans poids de cercle",
        n_under, fr_num(IFN_C13_MIN_M)))
    }
  }
  trees <- data.frame(
    plot_id = trees_raw$IDP,
    campaign = t_camp,
    tree_id = as.character(tree_ids),
    species = trees_raw$ESPAR,
    d130 = ifn_d130_cm(c13),
    h = ifelse(!is.na(h) & h > 0, h, NA_real_),
    weight_ha = w,
    veg_state = veg,
    veg_state_5y = veg5,
    radial_incr_5y_m = ir5,
    stem_volume_m3 = vol,
    stringsAsFactors = FALSE
  )[kept, , drop = FALSE]
  if (anyDuplicated(trees[, c("plot_id", "campaign", "tree_id")])) {
    stop("ARBRE.csv : (IDP, CAMPAGNE, A) en double", call. = FALSE)
  }
  if ("W" %in% names(trees_raw)) {
    w_raw <- w_raw_all[kept]
    is_v2_k <- is_v2[kept]
    disagree <- !is_v2_k & !is.na(w_raw) & abs(w_raw - trees$weight_ha) > 0.01 * trees$weight_ha
    if (any(disagree)) {
      add("IFN : arbres", sprintf(
        "%d arbre(s) de 1re visite dont la colonne W du fichier diffère de plus de 1 %% du poids du cercle (ex. W = %s contre %s) ; le poids du cercle (IMOT 2025 p. 61) est retenu",
        sum(disagree), fr_num(w_raw[disagree][1], 2), fr_num(trees$weight_ha[disagree][1], 2)))
    }
  }
  # Appariement (comptes seulement : la jointure est faite par dynamics, spec §6).
  if (any(is_v2) && !made_up_id) {
    k1 <- paste(trees_raw$IDP, tree_ids)[!is_v2]
    k2 <- paste(trees_raw$IDP, tree_ids)[is_v2]
    recruits <- !k2 %in% k1
    revisited_plots <- unique(trees_raw$IDP[is_v2])
    lost <- !paste(trees_raw$IDP, tree_ids)[!is_v2] %in% k2 & trees_raw$IDP[!is_v2] %in% revisited_plots
    c13_rec <- c13[is_v2][recruits]
    add("IFN : arbres", sprintf(
      "appariement par (IDP, A) : %d arbre(s) revu(s), %d recrue(s) (2e visite sans 1re ; %d sous le seuil de %s m), %d arbre(s) de 1re visite sans ligne de 2e visite sur une placette revisitée",
      sum(!recruits), sum(recruits), sum(!is.na(c13_rec) & c13_rec < IFN_C13_MIN_M),
      fr_num(IFN_C13_MIN_M), sum(lost)))
  }
  rownames(trees) <- NULL
  add("IFN : arbres", sprintf(
    "%d ligne(s) d'arbre retenue(s) sur %d (%d de 1re visite, %d de 2e visite) ; d130 = C13 x 100 / pi, C13 en m ; poids par cercle de 6, 9 ou 15 m en 1re visite",
    nrow(trees), nrow(trees_raw), sum(!is_v2[kept]), sum(is_v2[kept])))

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
    .ifn_read_csv(paths[["inputs.ifn_placette"]], c("CAMPAGNE", "IDP", "XL", "YL", "VISITE")),
    .ifn_read_csv(paths[["inputs.ifn_arbre"]], c("CAMPAGNE", "IDP", "ESPAR", "C13")),
    .ifn_read_csv(paths[["inputs.ifn_flore"]], c("CAMPAGNE", "IDP", "CD_REF", "ABOND")),
    precision_m = precision_m, taxref_version = taxref_version
  )
  res <- ifn_station_trophic(res, zone_dir, validate)  # trophic (mission 024), avant toute écriture
  for (i in seq_len(nrow(res$report))) report_add(report, res$report$section[i], res$report$text[i])
  invisible(res)
}

IFN_PLOTS_TYPES <- c(plot_id = "string", campaign = "int32", x = "float64", y = "float64",
                     loc_precision_m = "float64", source = "string", ser_code = "string",
                     trophic = "float64", coarse_hydric_700m = "float64",
                     coarse_bioclim_700m = "float64", visit = "int32", date_point = "string",
                     incident_nature = "int32", incident_intensity = "int32",
                     harvest_5y = "string", clearing_5y = "int32", planting_5y = "int32")
IFN_TREES_TYPES <- c(plot_id = "string", campaign = "int32", tree_id = "string",
                     species = "string", d130 = "float64", h = "float64", weight_ha = "float64",
                     veg_state = "string", veg_state_5y = "string",
                     radial_incr_5y_m = "float64", stem_volume_m3 = "float64")
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
  res <- ifn_station_coarse(res, zone_dir, report)  # coarse_*_700m et ser_code (mission 024)
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
