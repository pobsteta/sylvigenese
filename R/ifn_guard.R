# Garde IFN (spec §6 ; mission 019).
#
# Reprise TELLE QUELLE de sylvostation, `R/utils.R` lignes 1 à 157 (FINE_VARIABLES,
# COARSE_VARIABLES, mark_ifn(), assert_no_fine_extract_on_ifn() et leurs aides), dépôt
# /tmp/claude-0/repos/sylvostation, licence GNU GPL (>= 3) : même famille que la licence
# GPL-3 de sylvigenese. Seul cet en-tête a été ajouté ; le corps n'est pas modifié.
# Seuil de précision de point : 25 m (argument `max_precision_m`). Toute variable qui n'est
# pas préfixée `coarse_` (ou listée dans COARSE_VARIABLES) est traitée comme fine, donc
# `station_gradients` (nom du raster) est refusée aux placettes IFN.

#' Variables fines (interdites aux placettes IFN)
#'
#' Variables dont la résolution est bien plus fine que la précision de localisation
#' des placettes de l'IFN (700 m). La correspondance est insensible à la casse. Les
#' noms commençant par `lidar_`, `mnt_`, `mhc_` ou `k_` (facteur de rayonnement,
#' mission 021) sont aussi considérés comme fins.
#' @format Un vecteur de caractères.
#' @export
FINE_VARIABLES <- c(
  "pente", "exposition", "courbure", "courbure_plan", "courbure_profil",
  "tpi", "twi", "mrvbf", "hauteur_reseau", "rayonnement",
  "mnt", "mhc", "metriques_lidar",
  # couches de derive_terrain() (mission 005)
  "exposition_cos", "exposition_sin", "surface_drainee",
  "tpi_100", "tpi_300", "tpi_1000",
  # facteur de rayonnement r.sun et indice hydrique de la grille (mission 021). Nom sans
  # resolution depuis la mission 025 (ancien nom : grad_hydrique_25m). Ce n'est pas
  # `grad_hydrique`, colonne des placettes IFN (pas une variable fine).
  sprintf("k_%02d", 1:12), "k_sv", "is_topo", "nj_topo", "is_plat",
  "grad_hydrique_carte",
  # mission 039 : temperature corrigee du relief a la cellule (MNT fin), et sa version sur le
  # MNT de 250 m avant moyenne dans 700 m ; bilan lateral de Piedallu (tableau 20). Le MNT de
  # 250 m lui-meme (`mnt_250`) est fin par le prefixe `mnt_`.
  "t_corr", "t_corr_sv", "t_corr_250",
  "curv150", "idr_1500", "moore", "p_depart", "p_equilibre", "p_apports",
  "bilan_lateral", "ru_bilan_lateral"
)

#' Variables à maille large (autorisées aux placettes IFN)
#'
#' Prédicteurs de maille kilométrique ou plus grossière. Une variable est aussi
#' « large » si son nom porte le préfixe `coarse_`.
#' @format Un vecteur de caractères.
#' @export
COARSE_VARIABLES <- c("climat_km", "pedopaysage", "geologie_700m")

.FINE_PREFIXES <- c("lidar_", "mnt_", "mhc_", "k_")

#' Marquer des points comme placettes IFN
#'
#' Pose `attr(x, "source") <- "ifn"` et, pour un tableau, deux colonnes :
#' `source = "ifn"` et `loc_precision_m` (700 m par défaut ; dans le pipeline, la
#' valeur vient de `read_config()$ifn_precision_m`). Les colonnes survivent aux
#' sous-ensembles, à `rbind` et aux jointures, l'attribut non toujours.
#'
#' @param x Un objet (`data.frame`, `sf`, ...).
#' @param precision_m Précision de localisation, en mètres (nombre positif).
#' @return `x`, marqué.
#' @examples
#' p <- mark_ifn(data.frame(x = 1, y = 2))
#' p$loc_precision_m
#' @export
mark_ifn <- function(x, precision_m = 700) {
  if (!is.numeric(precision_m) || length(precision_m) != 1L ||
      !is.finite(precision_m) || precision_m <= 0) {
    stop("`precision_m` doit \u00eatre un nombre positif.", call. = FALSE)
  }
  if (is.data.frame(x)) {
    x[["source"]] <- "ifn"
    x[["loc_precision_m"]] <- precision_m
  }
  attr(x, "source") <- "ifn"
  x
}

# TRUE si la précision de localisation n'est pas garantie <= max_precision_m
# (colonne absente, NA, ou trop grossière).
.precision_insuffisante <- function(points, max_precision_m) {
  if (!is.data.frame(points) || !"loc_precision_m" %in% names(points)) return(TRUE)
  p <- points[["loc_precision_m"]]
  if (!is.numeric(p) || anyNA(p)) return(TRUE)
  any(p > max_precision_m)
}

.is_ifn <- function(points) {
  a <- attr(points, "source", exact = TRUE)
  if (is.character(a) && length(a) == 1L && identical(tolower(a), "ifn")) return(TRUE)
  if (is.data.frame(points) && "source" %in% names(points)) {
    s <- points[["source"]]
    if (any(tolower(as.character(s)) == "ifn", na.rm = TRUE)) return(TRUE)
  }
  FALSE
}

.is_coarse <- function(v) {
  # Le préfixe `coarse_` est sensible à la casse (décision mission 011) :
  # `COARSE_climat` est traité comme fin ; COARSE_VARIABLES reste insensible à la casse.
  tolower(v) %in% tolower(COARSE_VARIABLES) || startsWith(v, "coarse_")
}

.is_fine <- function(v) {
  l <- tolower(v)
  !.is_coarse(v) &&
    (l %in% tolower(FINE_VARIABLES) || any(startsWith(l, .FINE_PREFIXES)))
}

#' Règle bloquante : pas d'extraction fine sans précision de localisation suffisante
#'
#' Les placettes de l'IFN sont localisées à 700 m près : y extraire une variable fine
#' (pente, TWI, LiDAR...) produirait un bruit pris pour un signal. La fonction
#' échoue si une variable fine est demandée et que `points` est marqué IFN (voir
#' [mark_ifn()]) **ou** que sa précision de localisation n'est pas garantie : colonne
#' `loc_precision_m` absente, `NA`, ou supérieure à `max_precision_m`. Ainsi le
#' blocage survit à un `rbind` ou à une jointure qui perdrait le marquage, et un
#' mélange de placettes IFN et de points précis est refusé en entier. Par prudence,
#' une variable ni connue comme large ni préfixée `coarse_` est traitée comme fine ; le
#' préfixe est **sensible à la casse** (`COARSE_climat` est traité comme fin). Une colonne
#' `source = "ifn"` seule suffit à bloquer. `variables = character(0)` ou `NULL` passe (rien
#' n'est extrait).
#' Toute fonction d'extraction doit l'appeler en premier.
#'
#' @param points Points à échantillonner (tableau avec colonne `loc_precision_m`).
#' @param variables Vecteur de noms de variables à extraire.
#' @param max_precision_m Précision maximale admise, en mètres (25 par défaut).
#' @return `TRUE` de façon invisible si l'extraction est permise.
#' @examples
#' p <- mark_ifn(data.frame(x = 1, y = 2))
#' assert_no_fine_extract_on_ifn(p, "coarse_climat")
#' try(assert_no_fine_extract_on_ifn(p, "pente"))
#' @export
assert_no_fine_extract_on_ifn <- function(points, variables, max_precision_m = 25) {
  if (is.null(variables)) variables <- character(0)
  if (!is.character(variables) || anyNA(variables)) {
    stop("`variables` doit \u00eatre un vecteur de caract\u00e8res sans NA.", call. = FALSE)
  }
  if (!is.numeric(max_precision_m) || length(max_precision_m) != 1L ||
      is.na(max_precision_m) || max_precision_m <= 0) {
    stop("`max_precision_m` doit \u00eatre un nombre positif.", call. = FALSE)
  }
  est_fine <- vapply(variables, .is_fine, logical(1))
  est_large <- vapply(variables, .is_coarse, logical(1))
  fines <- variables[est_fine]
  inconnues <- variables[!est_fine & !est_large]
  if (!length(fines) && !length(inconnues)) return(invisible(TRUE))

  ifn <- .is_ifn(points)
  imprecis <- .precision_insuffisante(points, max_precision_m)
  if (ifn || imprecis) {
    msg <- if (ifn) {
      "Extraction interdite sur les placettes IFN (localis\u00e9es \u00e0 700 m pr\u00e8s)."
    } else {
      paste0("Extraction interdite : pr\u00e9cision de localisation (`loc_precision_m`) ",
             "absente, NA ou sup\u00e9rieure \u00e0 ", max_precision_m, " m.")
    }
    if (length(fines)) {
      msg <- paste0(msg, " Variables fines : ", paste(fines, collapse = ", "), ".")
    }
    if (length(inconnues)) {
      msg <- paste0(msg, " Variables non reconnues comme larges : ",
                    paste(inconnues, collapse = ", "), ".")
    }
    msg <- paste0(msg, " Seules les variables \u00e0 maille large (pr\u00e9fixe `coarse_` ",
                  "ou COARSE_VARIABLES) sont permises.")
    stop(msg, call. = FALSE)
  }
  invisible(TRUE)
}
