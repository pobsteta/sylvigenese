# prepare : arbres détectés sur le MNH et peuplements nemeton (spec §4 ; mission 018).
#
# Lit les entrées de <zone>/inputs/ (et les sorties de prepare_grid et de biomes) et écrit sous <zone>/ :
# trees_init/ est une étape à part, après biomes (décision de l'orchestrateur, 24/11/2026) :
#   trees_init/trees.parquet   un arbre par maximum local du MNH à 50 cm (contrat prepare.trees_init)
#   stands.parquet             (prepare_stands, étape prepare) les polygones nemeton (contrat prepare.stands)
#   rapport_arbres.html        ce que ce module a détecté, attribué, écarté
#
# Règles (spec §4) :
#  - §4.3 détection sur chm.tif à sa résolution d'origine (50 cm, jamais rééchantillonné) ;
#  - §4.1 essence = celle du polygone nemeton qui contient l'arbre (species_source = nemeton) ;
#    un polygone est mono-essence, et le rapport le dit ;
#  - §4.2 hors polygone : essence du type de végétation (species_source = vegetation_type), lue
#    dans vegetation_map.tif/.csv et biomes/*.yml (sorties de la mission 020) ; l'arbre est signalé ;
#  - §4.3 d130 par la méthode de l'« étage B » de tarif-nemeton, réécrite ici :
#      ln D = a + b ln H     (D en cm, H en m)
#    a et b viennent de params/allometry.parquet (modèle « etage_b ») ; aucun coefficient n'est
#    écrit dans ce fichier ; d130_source = tarif_etage_b ;
#  - §4.5 un polygone « synthetic_ml » a déjà sa hauteur issue du MNH : le MNH n'est pas
#    compté une seconde fois, et le rapport le dit ;
#  - signaler plutôt que deviner : un arbre dont l'essence ou les coefficients manquent n'est
#    pas écrit, et figure au rapport avec son motif ; aucune valeur par défaut.
#
# Méthode de détection (réécrite, pas copiée) : principe du maximum local à fenêtre variable
# selon la hauteur (Popescu et Wynne 2004, PE&RS 70(5) ; implémenté dans lidR::lmf) sur un MNH
# lissé par une médiane. lidR n'est pas installable ici (r-universe injoignable, constaté le
# 24/11/2026) : la détection est écrite avec terra::focal. Les valeurs de fenêtre, de hauteur
# minimale et de lissage ci-dessous sont PROVISOIRES.
#
# Non fait ici (à dire) : l'inventaire vidéo (inputs/inventaire_video.gpkg) n'est pas utilisé :
# les codes libres de nemeton (« chene_sessile ») n'ont pas de table vers l'espar dans le dépôt.
# Aucun arbre ne porte donc species_source ou d130_source = inventaire_video.

# ------------------------------------------------------------------ paramètres PROVISOIRES
# Hauteur minimale d'un arbre détecté (m).
TREES_HMIN_M <- 5
# Fenêtre de maximum local (diamètre, m) : pente par mètre de hauteur, bornes basse et haute.
TREES_WINDOW_SLOPE <- 0.2
TREES_WINDOW_MIN_M <- 4.5
TREES_WINDOW_MAX_M <- 8
# Lissage du MNH : médiane sur une fenêtre carrée de ce nombre de cellules (impair).
TREES_SMOOTH_CELLS <- 3L
# Départage des plateaux : décalage minuscule par numéro de cellule (inférieur au cm).
TREES_TIE_EPS <- 1e-12

TREES_SPECIES_PATTERN <- "^[0-9]{2}[A-Z0-9]{0,3}$"

# ------------------------------------------------------------------ Parquet (paquet arrow)
# Voie commune du projet : le paquet R « arrow » (décision de l'orchestrateur, 24/11/2026).

.require_arrow <- function() {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("le paquet R « arrow » est absent : impossible de lire ou d'écrire du Parquet", call. = FALSE)
  }
}

#' Lit un fichier Parquet en data.frame. Les colonnes de texte restent des chaînes (le zéro de
#' tête des codes espar : « 09 », jamais 9).
read_parquet_tbl <- function(path) {
  if (!file.exists(path)) stop(sprintf("fichier Parquet absent : %s", path), call. = FALSE)
  .require_arrow()
  as.data.frame(arrow::read_parquet(path), stringsAsFactors = FALSE)
}

#' Écrit un data.frame en Parquet avec un schéma explicite : `types` nomme le type de chaque
#' colonne (« string », « float64 » ou « int32 »), pour qu'une colonne vide ne devienne pas
#' « null ». Pas de partition.
write_parquet_tbl <- function(df, path, types) {
  .require_arrow()
  if (!setequal(names(df), names(types))) {
    stop("erreur interne : colonnes et types du Parquet ne correspondent pas", call. = FALSE)
  }
  arrow_types <- list(string = arrow::string(), float64 = arrow::float64(), int32 = arrow::int32())
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  sch <- do.call(arrow::schema, lapply(names(types), function(n) arrow::field(n, arrow_types[[types[[n]]]])))
  arrow::write_parquet(arrow::arrow_table(df[, names(types), drop = FALSE], schema = sch), path)
  invisible(path)
}

#' Codes espar du référentiel contracts/species.csv (première colonne, en chaîne : « 09 »).
#' Les colonnes de commentaire contiennent des virgules : seule la première est lue.
read_species_codes <- function(path) {
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  codes <- sub(",.*$", "", lines[-1L])
  codes[nzchar(codes)]
}

# ------------------------------------------------------------------ allométrie de l'étage B

#' Coefficients a et b du modèle « etage_b » par essence, lus dans params/allometry.parquet.
#' Rend un data.frame (species, a, b). Arrête si le fichier n'a pas la forme du contrat.
read_etage_b_coefficients <- function(path) {
  rows <- read_parquet_tbl(path)
  need <- c("species", "model", "term", "value")
  if (!all(need %in% names(rows))) {
    stop(sprintf("%s : colonnes %s attendues", path, paste(need, collapse = ", ")), call. = FALSE)
  }
  rows <- rows[rows$model == "etage_b" & !is.na(rows$species) & nzchar(rows$species), ]
  a <- rows[rows$term == "a", c("species", "value")]
  b <- rows[rows$term == "b", c("species", "value")]
  names(a)[2] <- "a"; names(b)[2] <- "b"
  coef <- merge(a, b, by = "species")
  if (anyDuplicated(coef$species) > 0L) {
    stop(sprintf("%s : plusieurs jeux de coefficients etage_b pour une même essence", path),
         call. = FALSE)
  }
  coef
}

#' d130 (cm) = exp(a + b ln H), H en m (étage B de tarif-nemeton, spec §4.3). NA si l'essence n'a
#' pas de coefficients : aucune valeur par défaut.
d130_etage_b <- function(species, h, coef) {
  i <- match(species, coef$species)
  exp(coef$a[i] + coef$b[i] * log(h))
}

# ------------------------------------------------------------------ détection des arbres

#' Nombre impair de cellules d'une fenêtre de `w_m` mètres sur une maille de `res` m.
window_cells <- function(w_m, res) {
  2L * as.integer(floor(w_m / res / 2)) + 1L
}

#' Diamètre (m) de la fenêtre de maximum local pour un arbre de hauteur `h` (PROVISOIRE).
tree_window_m <- function(h) {
  pmin(pmax(TREES_WINDOW_SLOPE * h, TREES_WINDOW_MIN_M), TREES_WINDOW_MAX_M)
}

#' Détecte les arbres du MNH `chm` (SpatRaster, hauteurs en m, EPSG:2154) : maxima locaux du MNH
#' lissé, fenêtre variable selon la hauteur. Rend un data.frame (row, col, x, y, h) : x et y sont
#' le centre de la cellule (x vers l'est, y vers le nord), h la hauteur maximale du MNH non lissé
#' sur 3 x 3 cellules autour du sommet. Le MNH n'est jamais rééchantillonné.
detect_trees <- function(chm, hmin = TREES_HMIN_M, smooth_cells = TREES_SMOOTH_CELLS) {
  res <- terra::res(chm)[1]
  nc <- terra::ncol(chm)
  smooth <- if (smooth_cells > 1L) {
    terra::focal(chm, w = smooth_cells, fun = "median", na.rm = TRUE)
  } else chm
  v <- terra::values(smooth, mat = FALSE)
  v[is.nan(v)] <- NA
  # départage des plateaux : le sommet est unique, le plus petit numéro de cellule perd
  vj <- v + seq_along(v) * TREES_TIE_EPS
  smooth_j <- terra::setValues(smooth, vj)
  n_cells <- window_cells(tree_window_m(v), res)
  eligible <- !is.na(v) & v >= hmin
  top <- rep(FALSE, length(v))
  for (n in sort(unique(n_cells[eligible]))) {
    fmax <- terra::values(terra::focal(smooth_j, w = n, fun = "max", na.rm = TRUE), mat = FALSE)
    top <- top | (eligible & n_cells == n & !is.na(fmax) & vj == fmax)
  }
  cells <- which(top)
  if (length(cells) == 0L) {
    return(data.frame(row = integer(), col = integer(), x = numeric(), y = numeric(),
                      h = numeric()))
  }
  raw_max <- terra::values(terra::focal(chm, w = 3L, fun = "max", na.rm = TRUE), mat = FALSE)
  xy <- terra::xyFromCell(chm, cells)
  data.frame(row = as.integer((cells - 1L) %/% nc + 1L), col = as.integer((cells - 1L) %% nc + 1L),
             x = xy[, 1], y = xy[, 2], h = raw_max[cells])
}

# ------------------------------------------------------------------ essence : polygone ou végétation

#' Essence dominante de chaque type de végétation : code espar de plus grande part dans la strate
#' arborée du biome de même `id` que le nom du type dans vegetation_map.csv. Rend un vecteur
#' nommé par type ; NA si le type n'a pas de biome, pas de strate arborée, ou une égalité de
#' parts entre essences (le motif est rendu dans l'attribut « motifs »).
vegetation_dominant_species <- function(types, biomes_dir, known_species = NULL) {
  files <- list.files(biomes_dir, pattern = "[.]ya?ml$", full.names = TRUE)
  by_id <- list()
  for (f in files) {
    b <- yaml::yaml.load(paste(readLines(f, warn = FALSE, encoding = "UTF-8"), collapse = "\n"))
    if (is.list(b) && !is.null(b$id)) by_id[[as.character(b$id)]] <- b
  }
  out <- stats::setNames(rep(NA_character_, length(types)), types)
  why <- stats::setNames(rep("", length(types)), types)
  for (t in types) {
    b <- by_id[[t]]
    comp <- if (is.null(b)) NULL else b$strates$arboree$composition
    if (is.null(b)) { why[t] <- "aucun biome de ce nom dans biomes/"; next }
    if (length(comp) == 0L) { why[t] <- "biome sans strate arborée"; next }
    shares <- unlist(comp)
    # les clés de YAML « 09 » peuvent perdre leur zéro : on exige la forme du référentiel
    codes <- names(shares)
    if (!all(grepl(TREES_SPECIES_PATTERN, codes)) ||
        (!is.null(known_species) && !all(codes %in% known_species))) {
      why[t] <- sprintf("code(s) d'essence hors référentiel ou sans zéro de tête (%s) ; les écrire entre guillemets dans le YAML",
                        paste(codes, collapse = ", "))
      next
    }
    top <- which(abs(shares - max(shares)) < 1e-9)
    if (length(top) > 1L) {
      why[t] <- sprintf("égalité de parts entre essences (%s)", paste(codes[top], collapse = ", "))
      next
    }
    out[t] <- codes[top]
  }
  attr(out, "motifs") <- why
  out
}

# ------------------------------------------------------------------ rapport

#' Écrit rapport_arbres.html (UTF-8), avec les fonctions de rapport_prepare.html (prepare_grid.R).
write_trees_report <- function(report, path) {
  sections <- unique(vapply(report$entries, function(e) e$section, character(1)))
  body <- character()
  for (s in sections) {
    lines <- vapply(Filter(function(e) identical(e$section, s), report$entries),
                    function(e) sprintf("<li>%s</li>", html_escape(e$text)), character(1))
    body <- c(body, sprintf("<h2>%s</h2>", html_escape(s)), "<ul>", lines, "</ul>")
  }
  html <- c("<!DOCTYPE html>", "<html lang=\"fr\">",
            "<head><meta charset=\"utf-8\"><title>Rapport de prepare : arbres</title></head>",
            "<body>", "<h1>Rapport de prepare : arbres détectés et peuplements</h1>", body,
            "</body>", "</html>")
  con <- file(path, open = "wb")
  on.exit(close(con))
  writeLines(enc2utf8(html), con, useBytes = TRUE)
  invisible(path)
}

# ------------------------------------------------------------------ peuplements

#' Lit nemeton_stands.gpkg (couche stands) et rend (1) le sf d'origine, (2) la table
#' stands.parquet aux noms de sylvigenese. Arrête si une essence n'est pas du référentiel.
read_stands <- function(path, known_species) {
  s <- read_layer_2154(path, "stands")
  need <- c("stand_id", "species_espar", "dbh_cm", "height_m", "density_ha", "age_yr", "source",
            "stand_id_source")
  missing_cols <- setdiff(need, names(s))
  if (length(missing_cols) > 0L) {
    stop(sprintf("nemeton_stands.gpkg : colonne(s) absente(s) : %s",
                 paste(missing_cols, collapse = ", ")), call. = FALSE)
  }
  sp <- as.character(s$species_espar)
  bad <- setdiff(unique(sp), known_species)
  if (length(bad) > 0L) {
    stop(sprintf("nemeton_stands.gpkg : essence(s) hors de contracts/species.csv : %s",
                 paste(bad, collapse = ", ")), call. = FALSE)
  }
  tab <- data.frame(stand_id = as.character(s$stand_id), species = sp,
                    d130 = as.numeric(s$dbh_cm), h = as.numeric(s$height_m),
                    density_ha = as.numeric(s$density_ha), age = as.integer(s$age_yr),
                    source = as.character(s$source),
                    stand_id_source = as.character(s$stand_id_source), stringsAsFactors = FALSE)
  list(sf = s, table = tab)
}

STANDS_TYPES <- list(stand_id = "string", species = "string", d130 = "float64", h = "float64",
                     density_ha = "float64", age = "int32", source = "string",
                     stand_id_source = "string")
TREES_TYPES <- list(tree_id = "string", x = "float64", y = "float64", species = "string",
                    d130 = "float64", h = "float64", species_source = "string",
                    d130_source = "string")

# ------------------------------------------------------------------ le module

#' Détecte les arbres et écrit trees_init/ et rapport_arbres.html (mission 018).
#' À appeler après prepare_grid (forest_mask.tif) et biomes (vegetation_map) ; rend la liste des fichiers écrits.
#' `biomes_dir` : dossier des biomes (biomes/*.yml) ; `species_csv` : référentiel des essences.
prepare_trees <- function(zone_dir, cfg, validate = TRUE,
                          biomes_dir = file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."), "biomes"),
                          species_csv = file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."),
                                                  "contracts", "species.csv")) {
  inp <- function(...) file.path(zone_dir, "inputs", ...)
  out <- function(...) file.path(zone_dir, ...)
  report <- new_report()
  sec <- "Arbres détectés"

  check_input_file(inp("chm.tif"))
  check_input_file(inp("nemeton_stands.gpkg"))
  check_input_file(out("forest_mask.tif"))
  check_input_file(species_csv)
  for (f in c("vegetation_map.tif", "vegetation_map.csv")) {
    if (!file.exists(out(f))) {
      stop(sprintf("%s absent : lancer `make biomes` avant `make trees` (essence hors polygone, spec §4.2)",
                   out(f)), call. = FALSE)
    }
  }
  allometry_path <- file.path(zone_dir, "params", "allometry.parquet")
  if (!file.exists(allometry_path)) {
    stop(sprintf("coefficients d'allométrie absents : %s (import_tarif doit passer avant)",
                 allometry_path), call. = FALSE)
  }
  if (validate) {
    validate_file("inputs.chm", inp("chm.tif"), what = "entrée")
    validate_file("inputs.nemeton_stands", inp("nemeton_stands.gpkg"), what = "entrée")
  }

  known <- read_species_codes(species_csv)
  coef <- read_etage_b_coefficients(allometry_path)

  # -- peuplements nemeton
  st <- read_stands(inp("nemeton_stands.gpkg"), known)
  for (k in seq_len(nrow(st$table))) {
    s <- st$table[k, ]
    report_add(report, "Peuplements nemeton", sprintf(
      "%s : mono-essence, essence %s (une seule essence par polygone, spec §4.1), source %s",
      s$stand_id, s$species, s$source))
    if (identical(s$source, "synthetic_ml")) {
      report_add(report, "Peuplements nemeton", sprintf(
        "%s : source synthetic_ml, sa hauteur vient déjà du MNH ; les arbres détectés portent la hauteur du MNH et elle n'est pas comptée une seconde fois (spec §4.5)",
        s$stand_id))
    }
  }

  # -- détection (MNH à sa résolution d'origine)
  chm <- read_raster_2154(inp("chm.tif"))
  chm_res <- terra::res(chm)[1]
  na_cells <- sum(is.na(terra::values(chm, mat = FALSE)))
  if (na_cells > 0L) {
    report_add(report, sec, sprintf("MNH : %d cellule(s) sans valeur, jamais candidates à un sommet", na_cells))
  }
  det <- detect_trees(chm)
  report_add(report, sec, sprintf(
    "%d maxima locaux détectés sur le MNH de %g m (hauteur minimale %g m, fenêtre %g à %g m selon la hauteur, médiane %dx%d) ; paramètres PROVISOIRES, lidR absent : détection écrite avec terra",
    nrow(det), chm_res, TREES_HMIN_M, TREES_WINDOW_MIN_M, TREES_WINDOW_MAX_M,
    TREES_SMOOTH_CELLS, TREES_SMOOTH_CELLS))

  # -- hors forêt : écartés et dits
  forest <- terra::rast(out("forest_mask.tif"))
  in_forest <- terra::extract(forest, as.matrix(det[, c("x", "y")]))[, 1]
  keep_forest <- !is.na(in_forest) & in_forest == 1
  if (any(!keep_forest)) {
    report_add(report, sec, sprintf(
      "%d sommet(s) hors du masque forestier écarté(s) (forest_mask.tif) ; premier en (%.1f ; %.1f)",
      sum(!keep_forest), det$x[!keep_forest][1], det$y[!keep_forest][1]))
  }
  det <- det[keep_forest, , drop = FALSE]
  det$tree_id <- sprintf("T%04d_%04d", det$row, det$col)

  # -- essence : polygone nemeton, sinon type de végétation
  pts <- sf::st_as_sf(det, coords = c("x", "y"), crs = 2154, remove = FALSE)
  hit <- sf::st_intersects(pts, st$sf)
  poly <- vapply(hit, function(i) if (length(i) == 0L) NA_integer_ else min(i), integer(1))
  det$species <- st$table$species[poly]
  det$species_source <- ifelse(is.na(poly), NA_character_, "nemeton")
  det$stand_id <- st$table$stand_id[poly]

  outside <- is.na(poly)
  if (any(outside)) {
    veg_map <- out("vegetation_map.tif"); veg_csv <- out("vegetation_map.csv")
    {
      vr <- terra::rast(veg_map)
      cats <- utils::read.csv(veg_csv, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
      code <- terra::extract(vr, as.matrix(det[outside, c("x", "y")]))[, 1]
      vname <- cats$name[match(code, cats$value)]
      dom <- vegetation_dominant_species(unique(stats::na.omit(vname)), biomes_dir, known)
      motifs <- attr(dom, "motifs")
      sp <- unname(dom[vname])
      det$species[outside] <- sp
      det$species_source[outside] <- ifelse(is.na(sp), NA_character_, "vegetation_type")
      report_add(report, "Hors polygone nemeton", sprintf(
        "%d arbre(s) hors polygone nemeton : essence du type de végétation (species_source = vegetation_type), arbres signalés (spec §4.2)",
        sum(outside)))
      no_type <- is.na(code)
      if (any(no_type)) {
        report_add(report, "Hors polygone nemeton", sprintf(
          "%d arbre(s) sur une cellule sans type de végétation : NON écrits", sum(no_type)))
      }
      for (t in names(dom)[is.na(dom)]) {
        report_add(report, "Hors polygone nemeton", sprintf(
          "type de végétation « %s » sans essence (%s) : %d arbre(s) NON écrits", t, motifs[[t]],
          sum(vname == t, na.rm = TRUE)))
      }
    }
  }
  no_species <- is.na(det$species)
  det <- det[!no_species, , drop = FALSE]

  # -- d130 : étage B
  det$d130 <- d130_etage_b(det$species, det$h, coef)
  det$d130_source <- ifelse(is.na(det$d130), NA_character_, "tarif_etage_b")
  no_coef <- is.na(det$d130)
  if (any(no_coef)) {
    for (sp in sort(unique(det$species[no_coef]))) {
      report_add(report, sec, sprintf(
        "essence %s sans coefficients etage_b dans allometry.parquet : %d arbre(s) NON écrits (pas de d130 deviné)",
        sp, sum(no_coef & det$species == sp)))
    }
  }
  det <- det[!no_coef, , drop = FALSE]
  det <- det[order(det$tree_id), , drop = FALSE]

  # -- bilan par polygone et par origine d'essence
  for (sid in st$table$stand_id) {
    n <- sum(det$stand_id == sid, na.rm = TRUE)
    report_add(report, "Arbres par polygone", sprintf("%s : %d arbre(s)", sid, n))
    if (n == 0L) {
      report_add(report, "Arbres par polygone", sprintf("%s : AUCUN arbre détecté", sid))
    }
  }
  report_add(report, "Arbres par polygone", sprintf("hors polygone nemeton : %d arbre(s) écrit(s)",
                                                    sum(is.na(det$stand_id))))
  report_add(report, sec, sprintf(
    "d130 par l'étage B de tarif-nemeton (ln D = a + b ln H), coefficients de params/allometry.parquet : %d arbre(s) écrit(s)",
    nrow(det)))
  if (nrow(det) == 0L) {
    stop("aucun arbre écrit : trees_init/ vide, voir rapport_arbres.html", call. = FALSE)
  }

  # -- écriture
  written <- character()
  trees_dir <- out("trees_init")
  if (dir.exists(trees_dir)) unlink(trees_dir, recursive = TRUE)
  write_parquet_tbl(det[, names(TREES_TYPES)], file.path(trees_dir, "trees.parquet"), TREES_TYPES)
  report_path <- out("rapport_arbres.html")
  write_trees_report(report, report_path)
  written <- c(file.path(trees_dir, "trees.parquet"), report_path)

  if (validate) {
    validate_file("prepare.trees_init", trees_dir)
  }
  invisible(written)
}

#' Écrit stands.parquet (étape prepare ; ne dépend pas de biomes). Rend le chemin écrit.
prepare_stands <- function(zone_dir, cfg, validate = TRUE,
                           species_csv = file.path(Sys.getenv("SYLVIGENESE_ROOT", unset = "."),
                                                   "contracts", "species.csv")) {
  path <- file.path(zone_dir, "inputs", "nemeton_stands.gpkg")
  check_input_file(path)
  check_input_file(species_csv)
  if (validate) validate_file("inputs.nemeton_stands", path, what = "entrée")
  st <- read_stands(path, read_species_codes(species_csv))
  out <- file.path(zone_dir, "stands.parquet")
  write_parquet_tbl(st$table, out, STANDS_TYPES)
  if (validate) validate_file("prepare.stands", out)
  invisible(out)
}
