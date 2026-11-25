# prepare : variables de station aux placettes IFN (spec §6, « Variables à l'ajustement »,
# « Données d'ajustement », « Garde IFN » ; mission 024 ; BRIEF §4).
#
# Remplit, dans ifn/plots.parquet, les quatre colonnes de station que M1a laissait vides :
#   trophic              moyenne des valeurs indicatrices de la flore de la placette, méthode de
#                        sylvostation (https://github.com/pobsteta/sylvostation, commit 2864d70,
#                        R/placettes.R l.485-520, compute_gradients()) : par placette, moyenne simple
#                        des valeurs de réaction (« grad_ph ») et, à part, des valeurs de nutriments
#                        (« grad_azote ») des taxons présents qui en ont une ; trophic = moyenne des
#                        deux (une seule si l'autre manque). Pondération par ABOND et exclusion des
#                        essences arborées : options de sylvostation, désactivées par défaut chez elle
#                        comme ici (abundance_weights = FALSE, exclude_cd_ref = NULL) ;
#   coarse_hydric_700m   moyenne de la bande `hydric` de inputs/station_gradients.tif sur les mailles
#   coarse_bioclim_700m  dont le centre est à 700 m ou moins de la position floutée (bande `bioclim`),
#                        à la maille de l'entrée, sans rééchantillonnage ;
#   ser_code             SER sous-jacente majoritaire (ser.tif + ser.csv : jamais L1 à L5) sur les
#                        mailles du même disque. Règle PROVISOIRE, à confirmer avec Pascal en M2b.
#
# En deux temps, comme R/prepare_ifn.R :
#   ifn_station_trophic()  appelé par prepare_ifn_check(), AVANT la première écriture : lit et fait
#                          valider params/indicator_values.csv (contrat params.indicator_values) ;
#   ifn_station_coarse()   appelé par prepare_ifn(), APRÈS prepare_grid() : il lit ser.tif et ser.csv
#                          écrits par la grille, et inputs/station_gradients.tif validé par elle.
#
# Règles :
#  - garde IFN (R/ifn_guard.R, reprise telle quelle de sylvostation) : toute lecture de raster à une
#    placette passe par ifn_disc_values(), qui appelle assert_no_fine_extract_on_ifn() en premier avec
#    le nom de la variable produite ; seuls les noms préfixés `coarse_` passent. Aucune valeur n'est
#    lue à la maille de la placette ;
#  - flore et écologie ne sont relevées qu'en 1re visite (docs/referentiels/ifn-dynamique.md §6) : la
#    ligne de 2e visite reprend les quatre valeurs de la 1re visite du même IDP, et le rapport le dit ;
#  - la jointure flore / valeurs indicatrices se fait sur le CD_REF tel quel : les CD_REF de l'IFN sont
#    en TAXREF v13 et ne sont pas convertis (TAXREF injoignable) ; le rapport le dit ;
#  - signaler plutôt que deviner : taxons sans valeur, placettes sans valeur, mailles hors emprise ou
#    sans valeur, ex æquo de SER, table absente ou synthétique : chacun est une ligne de la section
#    « IFN : station » de rapport_prepare.html. Rien n'est complété.

IFN_STATION_SECTION <- "IFN : station"
# Rayon du disque (m) : 700 m, précision de localisation des placettes IFN (spec §6, coarse_*_700m).
IFN_STATION_RADIUS_M <- 700
# Table des valeurs indicatrices, sous le dossier de la zone (contrat params.indicator_values).
IFN_INDICATOR_FILE <- file.path("params", "indicator_values.csv")
# Bandes de station_gradients.tif lues aux placettes, et nom de la colonne produite.
IFN_COARSE_BANDS <- c(coarse_hydric_700m = "hydric", coarse_bioclim_700m = "bioclim")
# Nom (préfixé coarse_) sous lequel ser.tif est lu dans le disque, pour la garde.
IFN_COARSE_SER <- "coarse_ser_700m"

# ------------------------------------------------------------------ outils

.station_report <- function() {
  data.frame(section = character(0), text = character(0), stringsAsFactors = FALSE)
}

#' CD_REF des essences arborées du référentiel contracts/species.csv : colonne `taxref_cd_ref`
#' (TAXREF v18) et CD_REF v13 écrits « v13=NNN » dans la colonne `ecart` (même référentiel), pour
#' reconnaître les deux versions sans conversion.
ifn_tree_cd_ref <- function(species_csv = file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."),
                                                    "contracts", "species.csv")) {
  check_input_file(species_csv)
  # Lu ligne à ligne (comme read_species_codes) : les commentaires contiennent des virgules, et les
  # quatre premières colonnes (espar, latin, taxref_cd_ref, taxref_version) n'en contiennent pas.
  lines <- readLines(species_csv, warn = FALSE, encoding = "UTF-8")
  if (!startsWith(lines[1], "espar,latin,taxref_cd_ref,")) {
    stop("contracts/species.csv : en-tête inattendu (espar, latin, taxref_cd_ref attendus)", call. = FALSE)
  }
  lines <- lines[-1L]
  v18 <- suppressWarnings(as.integer(vapply(strsplit(lines, ",", fixed = TRUE),
                                            function(f) if (length(f) >= 3) f[3] else NA_character_,
                                            character(1))))
  m <- regmatches(lines, regexpr("v13=[0-9]+", lines))
  v13 <- as.integer(sub("v13=", "", m, fixed = TRUE))
  sort(unique(c(v18[!is.na(v18)], v13)))
}

#' Lit params/indicator_values.csv d'une zone (validé par son contrat si `validate`). Rend NULL si
#' le fichier est absent (trophic restera vide, et le rapport le dira).
ifn_read_indicators <- function(zone_dir, validate = TRUE) {
  path <- file.path(zone_dir, IFN_INDICATOR_FILE)
  if (!file.exists(path)) return(NULL)
  if (validate) validate_file("params.indicator_values", path, what = "entrée")
  d <- utils::read.table(path, sep = ";", header = TRUE, colClasses = "character",
                         quote = "\"", comment.char = "", encoding = "UTF-8",
                         stringsAsFactors = FALSE, na.strings = "")
  need <- c("cd_ref", "taxref_version", "reaction", "nutrients", "source", "synthetic", "provisoire")
  miss <- setdiff(need, names(d))
  if (length(miss)) {
    stop(sprintf("%s : colonne(s) absente(s) : %s", IFN_INDICATOR_FILE, paste(miss, collapse = ", ")),
         call. = FALSE)
  }
  data.frame(cd_ref = as.integer(d$cd_ref), taxref_version = d$taxref_version,
             reaction = as.numeric(d$reaction), nutrients = as.numeric(d$nutrients),
             source = d$source, synthetic = tolower(d$synthetic) == "true",
             provisoire = tolower(d$provisoire) == "true", stringsAsFactors = FALSE)
}

# ------------------------------------------------------------------ trophic

#' Indice trophique par ligne de `plots` (méthode de sylvostation, voir l'en-tête). Pure.
#'
#' @param plots data.frame `plot_id`, `campaign`, `visit`.
#' @param flora data.frame `plot_id`, `campaign`, `cd_ref`.
#' @param indicators data.frame `cd_ref`, `reaction`, `nutrients` (NA permis).
#' @param exclude_cd_ref CD_REF retirés de l'indice (essences arborées), ou NULL.
#' @return liste : `trophic` (un nombre par ligne de `plots`, NA sans valeur), `n_taxa` (taxons avec
#'   au moins une valeur, par ligne), `unmatched` (data.frame cd_ref, n_rows : taxons sans aucune
#'   valeur), `excluded_rows` (lignes de flore retirées), `copied` (lignes de 2e visite qui reprennent
#'   leur 1re visite), `orphans` (lignes de 2e visite sans 1re visite), `flora_v2` (lignes de flore
#'   à une campagne de 2e visite, ignorées).
ifn_trophic <- function(plots, flora, indicators, exclude_cd_ref = NULL) {
  key_p <- paste(plots$plot_id, plots$campaign)
  key_f <- paste(flora$plot_id, flora$campaign)
  v1 <- plots$visit == 1L
  flora_v2 <- sum(key_f %in% key_p[!v1])
  keep <- key_f %in% key_p[v1]
  excluded_rows <- 0L
  if (!is.null(exclude_cd_ref)) {
    drop <- keep & flora$cd_ref %in% exclude_cd_ref
    excluded_rows <- sum(drop)
    keep <- keep & !drop
  }
  fl <- flora[keep, , drop = FALSE]
  kf <- key_f[keep]
  idx <- match(fl$cd_ref, indicators$cd_ref)
  reac <- indicators$reaction[idx]
  nutr <- indicators$nutrients[idx]
  # Moyenne simple par placette des valeurs présentes (sylvostation : poids 1, NA retirés).
  mean_by <- function(v) {
    ok <- !is.na(v)
    s <- tapply(v[ok], factor(kf[ok], levels = key_p), sum)
    n <- tapply(rep(1, sum(ok)), factor(kf[ok], levels = key_p), sum)
    out <- as.numeric(s) / as.numeric(n)
    out[is.na(n)] <- NA_real_
    out
  }
  m_r <- mean_by(reac)
  m_n <- mean_by(nutr)
  both <- cbind(m_r, m_n)
  trophic <- ifelse(rowSums(!is.na(both)) == 0, NA_real_, rowMeans(both, na.rm = TRUE))
  has_val <- !is.na(reac) | !is.na(nutr)
  n_taxa <- as.integer(tapply(has_val, factor(kf, levels = key_p), sum))
  n_taxa[is.na(n_taxa)] <- 0L
  no_val <- fl$cd_ref[!has_val]
  unmatched <- if (length(no_val)) {
    t <- table(no_val)
    data.frame(cd_ref = as.integer(names(t)), n_rows = as.integer(t))
  } else data.frame(cd_ref = integer(0), n_rows = integer(0))
  # 2e visite : reprend la 1re visite du même IDP (flore relevée en 1re visite seulement).
  first <- match(plots$plot_id, plots$plot_id[v1])
  first_row <- which(v1)[first]
  v2 <- !v1
  orphans <- v2 & is.na(first_row)
  copy <- v2 & !orphans
  trophic[v2] <- NA_real_
  trophic[copy] <- trophic[first_row[copy]]
  n_taxa[v2] <- 0L
  n_taxa[copy] <- n_taxa[first_row[copy]]
  list(trophic = trophic, n_taxa = n_taxa, unmatched = unmatched, excluded_rows = excluded_rows,
       copied = sum(copy), orphans = sum(orphans), flora_v2 = flora_v2)
}

#' Remplit `res$plots$trophic` (résultat de ifn_tables()) et ajoute ses lignes à `res$report`.
#' À appeler avant toute écriture : seule la table des valeurs indicatrices est lue (et validée).
#' `exclude_trees` : retirer les essences arborées de contracts/species.csv (option de sylvostation,
#' désactivée par défaut chez elle comme ici).
ifn_station_trophic <- function(res, zone_dir, validate = TRUE, exclude_trees = FALSE,
                                species_csv = file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."),
                                                        "contracts", "species.csv")) {
  rep_df <- .station_report()
  add <- function(text) rep_df[nrow(rep_df) + 1L, ] <<- list(IFN_STATION_SECTION, text)
  plots <- res$plots
  flora <- res$flora
  v1 <- plots$visit == 1L
  ind <- ifn_read_indicators(zone_dir, validate)
  if (is.null(ind)) {
    plots$trophic <- NA_real_
    add(sprintf(paste(
      "%s absent : trophic vide (NA) pour les %d ligne(s) de placette ; les valeurs indicatrices",
      "(Tichý et al. 2023, Zenodo 10.5281/zenodo.7427088) ne sont pas fournies (licence réservée à",
      "Pascal, Q9) et ne sont jamais inventées"), IFN_INDICATOR_FILE, nrow(plots)))
  } else {
    trees_cd <- ifn_tree_cd_ref(species_csv)
    tr <- ifn_trophic(plots, flora, ind, if (exclude_trees) trees_cd else NULL)
    plots$trophic <- tr$trophic
    if (any(ind$synthetic)) {
      add(sprintf(
        "%s : %d taxon(s), valeurs SYNTHÉTIQUES (%d ligne(s) synthetic = true, source « %s ») : trophic n'a aucun sens écologique, il sert seulement à faire tourner la chaîne",
        IFN_INDICATOR_FILE, nrow(ind), sum(ind$synthetic), paste(unique(ind$source[ind$synthetic]), collapse = ", ")))
    } else {
      add(sprintf("%s : %d taxon(s), source « %s »", IFN_INDICATOR_FILE, nrow(ind),
                  paste(unique(ind$source), collapse = ", ")))
    }
    if (any(ind$provisoire)) {
      add(sprintf("%s : %d valeur(s) marquées provisoire = true", IFN_INDICATOR_FILE, sum(ind$provisoire)))
    }
    flora_versions <- unique(flora$taxref_version)
    add(sprintf(paste(
      "jointure flore / valeurs indicatrices sur le CD_REF tel quel : flore en TAXREF v%s (version de",
      "l'IFN), table en v%s ; CD_REF NON convertis en v18 (TAXREF injoignable, conversion bloquée)%s"),
      paste(flora_versions, collapse = ", "), paste(unique(ind$taxref_version), collapse = ", "),
      if (!all(unique(ind$taxref_version) %in% flora_versions))
        " ; versions différentes : un même CD_REF peut désigner deux taxons, appariement non garanti" else ""))
    add(paste(
      "trophic : méthode de sylvostation (R/placettes.R, commit 2864d70) : par placette, moyenne simple",
      "des valeurs de réaction et, à part, des valeurs de nutriments des taxons présents qui en ont une,",
      "puis moyenne des deux ; sans pondération par ABOND ; filtre des relevés de sylvostation (saison",
      "de DATEECO, INCO_FLOR) non appliqué, ces colonnes n'étant pas lues"))
    fl_v1 <- paste(flora$plot_id, flora$campaign) %in% paste(plots$plot_id, plots$campaign)[v1]
    n_tree_rows <- sum(fl_v1 & flora$cd_ref %in% trees_cd)
    n_tree_taxa <- length(unique(flora$cd_ref[fl_v1 & flora$cd_ref %in% trees_cd]))
    if (exclude_trees) {
      add(sprintf(
        "%d taxon(s) d'essences arborées (contracts/species.csv) retirés de l'indice (%d ligne(s) de relevé) : trophic ne décrit pas le peuplement en place",
        n_tree_taxa, tr$excluded_rows))
    } else {
      add(sprintf(
        "%d taxon(s) de la flore sont des essences arborées (contracts/species.csv ; %d ligne(s) de relevé) : gardés dans l'indice, comme sylvostation par défaut (exclude_cd_ref = NULL) ; trophic décrit donc aussi le peuplement en place",
        n_tree_taxa, n_tree_rows))
    }
    if (nrow(tr$unmatched)) {
      add(sprintf(
        "%d taxon(s) de la flore de 1re visite sans valeur indicatrice (%d ligne(s) de relevé), retirés de la moyenne, jamais complétés : CD_REF %s",
        nrow(tr$unmatched), sum(tr$unmatched$n_rows), paste(utils::head(tr$unmatched$cd_ref, 20), collapse = ", ")))
    } else {
      add("tous les taxons de la flore de 1re visite ont une valeur indicatrice")
    }
    with_flora <- paste(plots$plot_id, plots$campaign) %in% paste(flora$plot_id, flora$campaign)
    n_ok <- sum(v1 & !is.na(plots$trophic))
    n_flora_na <- sum(v1 & with_flora & is.na(plots$trophic))
    n_noflora <- sum(v1 & !with_flora)
    add(sprintf(
      "trophic renseigné sur %d placette(s) de 1re visite sur %d (de %s à %s) ; %d placette(s) de 1re visite avec flore mais sans trophic (aucun taxon avec valeur) ; %d placette(s) de 1re visite sans relevé floristique : trophic vide",
      n_ok, sum(v1), fr_num(suppressWarnings(min(plots$trophic, na.rm = TRUE)), 2),
      fr_num(suppressWarnings(max(plots$trophic, na.rm = TRUE)), 2), n_flora_na, n_noflora))
    if (tr$flora_v2 > 0L) {
      add(sprintf("%d ligne(s) de flore à une campagne de 2e visite (attendu : aucune) : ignorées", tr$flora_v2))
    }
    if (tr$orphans > 0L) {
      add(sprintf("%d ligne(s) de 2e visite sans 1re visite : trophic vide (aucune flore)", tr$orphans))
    }
  }
  res$plots <- plots
  res$report <- rbind(res$report, rep_df)
  res
}

# ------------------------------------------------------------------ disque de 700 m

#' Valeurs d'un raster (une couche) sur les mailles dont le centre est à `radius_m` ou moins de chaque
#' point. Garde IFN d'abord : `variable` est le nom de la variable produite ; un nom non préfixé
#' `coarse_` (par exemple « station_gradients » ou « hydric ») est refusé aux placettes IFN.
#'
#' @param points data.frame `x`, `y` (EPSG:2154) portant `source` et `loc_precision_m` (mark_ifn()).
#' @param r SpatRaster d'une couche, en EPSG:2154.
#' @return liste, un élément par point : `values` (valeurs non vides du disque), `n_out` (mailles du
#'   disque hors de l'emprise du raster), `n_na` (mailles du disque sans valeur).
ifn_disc_values <- function(points, r, variable, radius_m = IFN_STATION_RADIUS_M) {
  assert_no_fine_extract_on_ifn(points, variable)
  if (terra::nlyr(r) != 1L) stop("erreur interne : ifn_disc_values lit une couche à la fois", call. = FALSE)
  m <- terra::as.matrix(r, wide = TRUE)
  x0 <- terra::xmin(r); y1 <- terra::ymax(r)
  rx <- terra::res(r)[1]; ry <- terra::res(r)[2]
  nr <- nrow(m); nc <- ncol(m)
  lapply(seq_len(nrow(points)), function(k) {
    x <- points$x[k]; y <- points$y[k]
    # Indices (1 = première colonne, première ligne depuis le nord) des centres dans le carré du disque,
    # sur le pavage du raster prolongé au-delà de son emprise.
    j <- seq(ceiling((x - radius_m - x0) / rx + 0.5), floor((x + radius_m - x0) / rx + 0.5))
    i <- seq(ceiling((y1 - y - radius_m) / ry + 0.5), floor((y1 - y + radius_m) / ry + 0.5))
    g <- expand.grid(i = i, j = j)
    cx <- x0 + (g$j - 0.5) * rx
    cy <- y1 - (g$i - 0.5) * ry
    g <- g[(cx - x)^2 + (cy - y)^2 <= radius_m^2, , drop = FALSE]
    inside <- g$i >= 1 & g$i <= nr & g$j >= 1 & g$j <= nc
    v <- m[cbind(g$i[inside], g$j[inside])]
    list(values = v[!is.na(v)], n_out = sum(!inside), n_na = sum(is.na(v)))
  })
}

#' SER majoritaire de chaque disque. `disc` : résultat de ifn_disc_values() sur ser.tif ; `ser_tab` :
#' ser.csv (value, name). Plusieurs valeurs de ser.tif d'une même SER (alluvions) comptent ensemble.
#' Ex æquo : NA, jamais tranché ici. Rend une liste `ser_code`, `tie` (logique), `tie_codes` (texte).
ifn_ser_majority <- function(disc, ser_tab) {
  out <- lapply(disc, function(d) {
    codes <- ser_tab$name[match(d$values, ser_tab$value)]
    codes <- codes[!is.na(codes)]
    if (!length(codes)) return(list(code = NA_character_, tie = FALSE, codes = ""))
    t <- table(codes)
    best <- names(t)[t == max(t)]
    if (length(best) > 1L) {
      return(list(code = NA_character_, tie = TRUE,
                  codes = paste(sprintf("%s %d", best, as.integer(t[best])), collapse = " / ")))
    }
    list(code = best, tie = FALSE, codes = "")
  })
  list(ser_code = vapply(out, `[[`, character(1), "code"),
       tie = vapply(out, `[[`, logical(1), "tie"),
       tie_codes = vapply(out, `[[`, character(1), "codes"))
}

#' Remplit coarse_hydric_700m, coarse_bioclim_700m et ser_code de `res$plots`, après prepare_grid() :
#' lit inputs/station_gradients.tif (bandes hydric, bioclim), ser.tif et ser.csv de la zone. Un
#' fichier absent laisse ses colonnes vides et le rapport le dit. Les signalements vont dans `report`
#' (rapport de prepare) et dans `res$report`.
ifn_station_coarse <- function(res, zone_dir, report = NULL) {
  if (is.null(report)) report <- new_report()
  add <- function(text) {
    report_add(report, IFN_STATION_SECTION, text)
    res$report[nrow(res$report) + 1L, ] <<- list(IFN_STATION_SECTION, text)
  }
  plots <- res$plots
  v1 <- plots$visit == 1L
  first_row <- which(v1)[match(plots$plot_id, plots$plot_id[v1])]
  # Une valeur par point : 1re visite, et 2e visite sans 1re (calculée sur ses propres coordonnées) ;
  # la 2e visite avec 1re visite reprend celle-ci.
  own <- v1 | is.na(first_row)
  src_row <- ifelse(own, seq_len(nrow(plots)), first_row)
  pts <- plots[own, , drop = FALSE]
  n_pts <- nrow(pts)
  n_copy <- sum(!own)
  moved <- !own & (plots$x != plots$x[src_row] | plots$y != plots$y[src_row])
  add(sprintf(paste(
    "garde IFN : chaque lecture de raster aux placettes passe par assert_no_fine_extract_on_ifn (seuil",
    "de 25 m) sous un nom préfixé coarse_ (%s) ; aucune valeur n'est lue à la maille de la placette,",
    "seulement des moyennes ou des majorités sur les mailles dont le centre est à %s m ou moins de la",
    "position floutée"), paste(c(names(IFN_COARSE_BANDS), IFN_COARSE_SER), collapse = ", "),
    fr_num(IFN_STATION_RADIUS_M)))
  if (n_copy > 0L) {
    add(sprintf(paste(
      "%d ligne(s) de 2e visite reprennent trophic, coarse_hydric_700m, coarse_bioclim_700m et ser_code",
      "de leur 1re visite (flore et écologie relevées en 1re visite seulement, spec §6) : station vue",
      "5 ans avant la 2e visite%s"), n_copy,
      if (any(moved)) sprintf(" ; %d d'entre elles ont d'autres coordonnées que leur 1re visite : celles de la 1re sont gardées", sum(moved)) else ""))
  }

  # -- gradients de station : moyenne du disque, à la maille de l'entrée
  sg_path <- file.path(zone_dir, "inputs", "station_gradients.tif")
  if (!file.exists(sg_path)) {
    for (col in names(IFN_COARSE_BANDS)) plots[[col]] <- NA_real_
    add(sprintf("inputs/station_gradients.tif absent : %s vides (NA) pour les %d ligne(s)",
                paste(names(IFN_COARSE_BANDS), collapse = " et "), nrow(plots)))
  } else {
    sg <- read_raster_2154(sg_path)
    miss_b <- setdiff(IFN_COARSE_BANDS, names(sg))
    if (length(miss_b)) {
      stop(sprintf("station_gradients.tif : bande(s) %s absente(s) (trouvées : %s)",
                   paste(miss_b, collapse = ", "), paste(names(sg), collapse = ", ")), call. = FALSE)
    }
    for (col in names(IFN_COARSE_BANDS)) {
      band <- IFN_COARSE_BANDS[[col]]
      disc <- ifn_disc_values(pts, sg[[band]], col)
      val <- vapply(disc, function(d) if (length(d$values)) mean(d$values) else NA_real_, numeric(1))
      n_out <- vapply(disc, `[[`, numeric(1), "n_out")
      n_na <- vapply(disc, `[[`, numeric(1), "n_na")
      plots[[col]] <- val[match(src_row, which(own))]
      empty_rows <- is.na(plots[[col]])
      empty_pts <- length(unique(plots$plot_id[empty_rows]))
      cut <- !is.na(val) & (n_out > 0 | n_na > 0)
      add(sprintf(paste(
        "%s : moyenne de la bande %s de inputs/station_gradients.tif (maille de %s m, sans",
        "rééchantillonnage) dans le disque de %s m : %d placette(s) calculée(s) sur %d, de %s à %s ;",
        "%d placette(s) au disque tronqué (%s maille(s) hors de l'emprise du raster, %s sans valeur),",
        "moyenne sur les seules mailles présentes ; %d placette(s) (%d ligne(s)) sans aucune maille",
        "dans le disque : %s vide"), col, band, fr_num(terra::res(sg)[1]), fr_num(IFN_STATION_RADIUS_M),
        sum(!is.na(val)), n_pts, fr_num(suppressWarnings(min(val, na.rm = TRUE)), 2),
        fr_num(suppressWarnings(max(val, na.rm = TRUE)), 2), sum(cut), fr_num(sum(n_out[!is.na(val)])),
        fr_num(sum(n_na[!is.na(val)])), empty_pts, sum(empty_rows), col))
    }
  }

  # -- SER sous-jacente majoritaire dans le disque (règle PROVISOIRE)
  ser_path <- file.path(zone_dir, "ser.tif")
  ser_csv <- file.path(zone_dir, "ser.csv")
  if (!file.exists(ser_path) || !file.exists(ser_csv)) {
    plots$ser_code <- NA_character_
    add(sprintf("ser.tif ou ser.csv absent (grille non écrite) : ser_code vide (NA) pour les %d ligne(s)",
                nrow(plots)))
  } else {
    ser_tab <- utils::read.csv(ser_csv, colClasses = "character", fileEncoding = "UTF-8")
    ser_tab$value <- as.integer(ser_tab$value)
    if (any(ser_tab$name %in% ALLUVIUM_CODES)) {
      stop("ser.csv : un code d'alluvions L1 à L5 figure comme SER (name) : ser_code refusé", call. = FALSE)
    }
    disc <- ifn_disc_values(pts, read_raster_2154(ser_path), IFN_COARSE_SER)
    maj <- ifn_ser_majority(disc, ser_tab)
    plots$ser_code <- maj$ser_code[match(src_row, which(own))]
    n_out <- vapply(disc, `[[`, numeric(1), "n_out")
    n_na <- vapply(disc, `[[`, numeric(1), "n_na")
    none <- vapply(disc, function(d) !length(d$values), logical(1))
    codes <- sort(unique(maj$ser_code[!is.na(maj$ser_code)]))
    add(sprintf(paste(
      "ser_code : SER sous-jacente majoritaire (ser.tif et ser.csv, jamais L1 à L5) sur les mailles de",
      "la grille dans le disque de %s m, règle PROVISOIRE à confirmer avec Pascal en M2b : %d placette(s)",
      "renseignée(s) sur %d (%s) ; %s maille(s) de disque hors de la grille et %s sans SER, non comptées",
      "dans la majorité ; %d placette(s) sans aucune maille de SER dans le disque : ser_code vide"),
      fr_num(IFN_STATION_RADIUS_M), sum(!is.na(maj$ser_code)), n_pts,
      if (length(codes)) paste(codes, collapse = ", ") else "aucune", fr_num(sum(n_out)), fr_num(sum(n_na)),
      sum(none)))
    if (any(maj$tie)) {
      add(sprintf(
        "ser_code : %d placette(s) à égalité entre plusieurs SER dans le disque, laissées vides (jamais tranché ici) : %s",
        sum(maj$tie), paste(utils::head(sprintf("%s (%s)", pts$plot_id[maj$tie], maj$tie_codes[maj$tie]), 10),
                            collapse = " ; ")))
    } else {
      add("ser_code : aucune égalité entre SER dans les disques")
    }
  }
  res$plots <- plots
  res
}
