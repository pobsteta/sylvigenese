# prepare : arbres détectés sur le MNH, houppiers et peuplements nemeton (spec §4 ; mission 018).
#
# Lit les entrées de <zone>/inputs/ (et les sorties de prepare et de biomes) et écrit sous <zone>/ :
# trees_init/ est une étape à part, après biomes (décision de l'orchestrateur, 24/11/2026) :
#   trees_init/trees.parquet   un arbre par maximum local du MNH à 50 cm, avec la surface projetée
#                              de son houppier (contrat prepare.trees_init)
#   stands.parquet             (prepare_stands, étape prepare) les polygones nemeton (contrat prepare.stands)
#   rapport_arbres.html        ce que ce module a détecté, attribué, écarté, et ce qu'il ne fait pas
#
# Règles (spec §4) :
#  - §4.3 détection sur chm.tif à sa résolution d'origine (50 cm, jamais rééchantillonné), puis
#    segmentation des houppiers et surface projetée `crown_area` (m²) de chaque arbre ;
#  - §4.1 essence = celle du polygone nemeton qui contient l'arbre (species_source = nemeton) ;
#    un polygone est mono-essence, et le rapport le dit ; si l'arbre tombe dans plusieurs
#    polygones qui se recouvrent, le plus petit stand_id l'emporte (même règle que stand_map.tif) ;
#  - §4.2 hors polygone : essence dominante de la strate arborée du type de végétation
#    (species_source = vegetation_type), lue dans vegetation_map.tif/.csv et biomes/*.yml
#    (sorties de la mission 020) ; l'arbre est signalé. Règle PROVISOIRE ;
#  - §4.3 d130 par la méthode de l'« étage B » de tarif-nemeton, réécrite ici, coefficients lus
#    dans params/allometry.parquet (modèle « etage_b », termes a, b et c ; aucun coefficient
#    n'est écrit dans ce fichier) :
#      essence avec a, b et c : ln D = a + b ln H + c ln CPA   d130_source = tarif_etage_b
#      essence avec a et b    : ln D = a + b ln H               d130_source = tarif_etage_b_ifn
#      essence sans a ou b    : ARRÊT, code non nul, rien n'est écrit (pas de d130 deviné)
#    D en cm, H en m (hauteur du MNH), CPA = crown_area en m². Le terme du houppier est réintégré
#    par décision de Pascal du 24/11/2026 ;
#  - §4.5 un polygone « synthetic_ml » a déjà sa hauteur issue du MNH : le MNH n'est pas
#    compté une seconde fois, et le rapport le dit ;
#  - signaler plutôt que deviner : un arbre dont l'essence manque n'est pas écrit et figure au
#    rapport avec son motif ; aucune valeur par défaut.
#
# SOURCE DE LA MÉTHODE (lecture seule, réécrite ici, rien n'est copié) : tarif-nemeton,
# https://github.com/pobsteta/tarif-nemeton, commit 0f51b9606165237b7cae2dda8809081adef869ac.
#   code/etage_b_arbres_lidar.R   l.13  fenêtre variable f_ws, de 3 à 5,6 m selon la hauteur ;
#                                 l.17  MNH lissé par une médiane 3 x 3 (focal, w = 3) ;
#                                 l.18  sommets par lidR::lmf(f_ws, hmin = 5) : hauteur minimale 5 m ;
#                                 l.19  houppiers par lidR::dalponte2016 (th_tree = 5, th_seed = 0.45,
#                                       th_cr = 0.55, max_cr = 24) ;
#                                 l.20  surface projetée du houppier par terra::expanse.
#   code/etage_b_allometrie_D.py  l.2 et l.17 : ln D = a + b ln H + c ln CPA, par essence, calé sur
#                                 le TLS de BioDiv (réserve de l'auteur : la surface de houppier
#                                 segmentée dans un MNH aéroporté n'est pas celle du TLS).
#   code/etage_b_allometrie_ifn.py  l.6 et l.32 : ln D = a + b ln H, calé sur l'IFN.
# Méthodes citées : Popescu et Wynne 2004, PE&RS 70(5) (maximum local à fenêtre variable) ;
# Dalponte et Coomes 2016, Methods in Ecology and Evolution 7(10) (croissance de région depuis
# les sommets).
#
# ÉCARTS avec tarif-nemeton, tous dits au rapport :
#  - lidR n'est pas installable ici (r-universe injoignable, constaté le 24/11/2026) : la détection
#    et la croissance de région sont écrites avec terra et R de base ;
#  - fenêtre de maximum local carrée, d'un nombre IMPAIR de cellules (lmf : fenêtre circulaire) ;
#  - la hauteur écrite `h` est le maximum du MNH brut sur 3 x 3 cellules autour du sommet (tarif-
#    nemeton écrit la hauteur du MNH lissé) ;
#  - la croissance de région est écrite d'après la description publiée de Dalponte et Coomes 2016 :
#    à chaque passe tous les voisins (4-connexité) d'une région sont examinés avec la moyenne de la
#    passe précédente ; max_cr est lu comme un diamètre en cellules (demi-largeur de 12 cellules
#    pour 24). Le code de lidR n'a pas pu être relu : ces deux détails sont à vérifier.
# Toutes les valeurs ci-dessous sont celles de tarif-nemeton, où les coefficients de l'étage B ont
# été calés : elles sont PROVISOIRES, non recalées sur ce MNH.
#
# Outils communs (rapport, lecture en EPSG:2154, validation, Parquet) : R/commun.R, commun à
# tous les modules R (spec §2) ; ce fichier n'appelle aucune fonction de R/prepare_grid.R.
#
# Non fait ici (à dire) :
#  - l'inventaire vidéo (inputs/inventaire_video.gpkg) est lu et validé mais N'EST PAS UTILISÉ en
#    M1a : la spec ne donne aucune règle d'usage pour l'état initial (décision du 24/11/2026) ;
#    aucun arbre ne porte species_source ou d130_source = inventaire_video ;
#  - la hauteur n'est pas avancée jusqu'à t0 (spec §4.4) : elle attend la courbe de hauteur de
#    dynamics (M2).

# ------------------------------------------------------------------ paramètres PROVISOIRES
# (valeurs de tarif-nemeton, code/etage_b_arbres_lidar.R, lignes citées en tête de fichier)
# Hauteur minimale d'un arbre détecté (m) : lmf(hmin = 5), l.18 ; th_tree = 5, l.19.
TREES_HMIN_M <- 5
# Fenêtre de maximum local (diamètre, m) selon la hauteur h : f_ws, l.13 :
#   3 m si h < 2 m ; sinon 3 + 2,6 (1 - exp(-0,08 (h - 2))) (de 3 m vers 5,6 m).
TREES_WINDOW_BASE_M <- 3
TREES_WINDOW_GAIN_M <- 2.6
TREES_WINDOW_RATE <- 0.08
TREES_WINDOW_H0_M <- 2
# Lissage du MNH : médiane sur une fenêtre carrée de ce nombre de cellules (impair), l.17.
TREES_SMOOTH_CELLS <- 3L
# Croissance de région (dalponte2016, l.19).
TREES_CROWN_TH_TREE <- 5      # hauteur minimale d'une cellule de houppier (m)
TREES_CROWN_TH_SEED <- 0.45   # la cellule doit dépasser cette part de la hauteur du sommet
TREES_CROWN_TH_CR <- 0.55     # ... et cette part de la hauteur moyenne du houppier en cours
TREES_CROWN_MAX_CR <- 24      # diamètre maximal du houppier, en cellules (12 m à 50 cm)
# Une cellule ne peut pas dépasser le sommet de plus de cette part (Dalponte et Coomes 2016).
TREES_CROWN_OVERSHOOT <- 0.05
# Départage des plateaux : décalage minuscule par numéro de cellule (inférieur au cm).
TREES_TIE_EPS <- 1e-12

# Valeurs de d130_source (contrat prepare.trees_init).
D130_SOURCE_CROWN <- "tarif_etage_b"       # ln D = a + b ln H + c ln CPA
D130_SOURCE_HEIGHT <- "tarif_etage_b_ifn"  # ln D = a + b ln H (essence sans coefficient c)

TREES_SPECIES_PATTERN <- "^[0-9]{2}[A-Z0-9]{0,3}$"

# Lecture et écriture du Parquet : read_parquet_tbl et write_parquet_tbl, dans R/commun.R.

#' Codes espar du référentiel contracts/species.csv (première colonne, en chaîne : « 09 »).
#' Les colonnes de commentaire contiennent des virgules : seule la première est lue.
read_species_codes <- function(path) {
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  codes <- sub(",.*$", "", lines[-1L])
  codes[nzchar(codes)]
}

# ------------------------------------------------------------------ allométrie de l'étage B

#' Coefficients du modèle « etage_b » par essence, lus dans params/allometry.parquet.
#' Rend un data.frame (species, a, b, c) : NA là où un terme manque (c est facultatif ; une
#' essence sans a ou sans b n'a pas de modèle). Arrête si le fichier n'a pas la forme du contrat.
read_etage_b_coefficients <- function(path) {
  rows <- read_parquet_tbl(path)
  need <- c("species", "model", "term", "value")
  if (!all(need %in% names(rows))) {
    stop(sprintf("%s : colonnes %s attendues", path, paste(need, collapse = ", ")), call. = FALSE)
  }
  rows <- rows[rows$model == "etage_b" & !is.na(rows$species) & nzchar(rows$species), ]
  species <- sort(unique(rows$species), method = "radix")
  coef <- data.frame(species = species, stringsAsFactors = FALSE)
  for (term in c("a", "b", "c")) {
    x <- rows[rows$term == term, c("species", "value")]
    if (anyDuplicated(x$species) > 0L) {
      stop(sprintf("%s : plusieurs coefficients %s etage_b pour une même essence", path, term),
           call. = FALSE)
    }
    coef[[term]] <- x$value[match(species, x$species)]
  }
  coef
}

#' Essences de `species` sans coefficients a et b dans `coef` : leur d130 n'est pas calculable.
species_without_coefficients <- function(species, coef) {
  has_model <- coef$species[!is.na(coef$a) & !is.na(coef$b)]
  sort(setdiff(unique(species), has_model), method = "radix")
}

#' d130 (cm) de l'étage B de tarif-nemeton (spec §4.3), H en m, CPA (`crown_area`) en m² :
#'   essence avec a, b et c : exp(a + b ln H + c ln CPA)   d130_source = tarif_etage_b
#'   essence avec a et b    : exp(a + b ln H)               d130_source = tarif_etage_b_ifn
#'   sans a ou b            : NA, source NA (aucune valeur par défaut)
#' Rend un data.frame (d130, d130_source).
d130_etage_b <- function(species, h, crown_area, coef) {
  i <- match(species, coef$species)
  a <- coef$a[i]; b <- coef$b[i]; cc <- coef$c[i]
  with_crown <- !is.na(cc)
  ln_d <- a + b * log(h) + ifelse(with_crown, cc * log(crown_area), 0)
  d130 <- exp(ln_d)
  d130[is.na(a) | is.na(b)] <- NA_real_
  source <- ifelse(is.na(d130), NA_character_,
                   ifelse(with_crown, D130_SOURCE_CROWN, D130_SOURCE_HEIGHT))
  data.frame(d130 = d130, d130_source = source, stringsAsFactors = FALSE)
}

# ------------------------------------------------------------------ détection des arbres

#' Nombre impair de cellules d'une fenêtre de `w_m` mètres sur une maille de `res` m.
window_cells <- function(w_m, res) {
  2L * as.integer(floor(w_m / res / 2)) + 1L
}

#' Diamètre (m) de la fenêtre de maximum local pour un arbre de hauteur `h` (f_ws de tarif-nemeton,
#' code/etage_b_arbres_lidar.R l.13) : 3 m sous 2 m de haut, puis croissance vers 5,6 m.
tree_window_m <- function(h) {
  w <- TREES_WINDOW_BASE_M + TREES_WINDOW_GAIN_M * (1 - exp(-TREES_WINDOW_RATE * (h - TREES_WINDOW_H0_M)))
  ifelse(h < TREES_WINDOW_H0_M, TREES_WINDOW_BASE_M, w)
}

#' MNH lissé par une médiane sur `smooth_cells` x `smooth_cells` cellules (l.17 de tarif-nemeton).
smooth_chm <- function(chm, smooth_cells = TREES_SMOOTH_CELLS) {
  if (smooth_cells > 1L) terra::focal(chm, w = smooth_cells, fun = "median", na.rm = TRUE) else chm
}

#' Détecte les arbres du MNH `chm` (SpatRaster, hauteurs en m, EPSG:2154) : maxima locaux du MNH
#' lissé, fenêtre variable selon la hauteur. Rend un data.frame (row, col, x, y, h) : x et y sont
#' le centre de la cellule (x vers l'est, y vers le nord), h la hauteur maximale du MNH non lissé
#' sur 3 x 3 cellules autour du sommet. Le MNH n'est jamais rééchantillonné. `smooth` : le MNH
#' lissé, s'il est déjà calculé (segment_crowns en a besoin aussi).
detect_trees <- function(chm, hmin = TREES_HMIN_M, smooth_cells = TREES_SMOOTH_CELLS,
                         smooth = smooth_chm(chm, smooth_cells)) {
  res <- terra::res(chm)[1]
  nc <- terra::ncol(chm)
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

# ------------------------------------------------------------------ houppiers

#' Segmente les houppiers par croissance de région depuis les sommets `seeds` (data.frame avec
#' `row` et `col` : cellules du MNH lissé `smooth`), d'après Dalponte et Coomes 2016 (principe de
#' lidR::dalponte2016, paramètres TREES_CROWN_* de tarif-nemeton). Une cellule voisine (4-
#' connexité) d'une région y entre si elle est : plus haute que th_tree ; plus haute que th_seed
#' fois la hauteur du sommet ; plus haute que th_cr fois la hauteur moyenne de la région ; pas
#' plus haute que le sommet de plus de 5 % ; à moins de max_cr / 2 cellules du sommet en ligne et
#' en colonne. Une cellule reçoit la première région qui l'accepte (voisins pris dans l'ordre
#' nord, ouest, sud, est). Rend, pour chaque sommet dans l'ordre de `seeds`, le nombre de
#' cellules de son houppier (le sommet compris). Cellules sans valeur : jamais dans un houppier.
segment_crowns <- function(smooth, seeds, th_tree = TREES_CROWN_TH_TREE,
                           th_seed = TREES_CROWN_TH_SEED, th_cr = TREES_CROWN_TH_CR,
                           max_cr = TREES_CROWN_MAX_CR) {
  n <- nrow(seeds)
  if (n == 0L) return(integer())
  nr <- terra::nrow(smooth); nc <- terra::ncol(smooth)
  total <- as.numeric(nr) * nc
  # valeurs en colonnes (numéro de cellule = (col - 1) * nr + row), plus une case « hors raster »
  v <- as.vector(matrix(terra::values(smooth, mat = FALSE), nr, nc, byrow = TRUE))
  v[is.nan(v)] <- NA
  seed_cell <- (as.numeric(seeds$col) - 1) * nr + seeds$row
  lab <- integer(total + 1)
  lab[seed_cell] <- seq_len(n)
  seed_h <- v[seed_cell]
  seed_r <- as.numeric(seeds$row); seed_c <- as.numeric(seeds$col)
  cnt <- rep(1, n); sum_h <- seed_h
  half <- max_cr / 2
  neighbour <- function(cells, d) {
    r <- (cells - 1) %% nr + 1; k <- (cells - 1) %/% nr + 1
    switch(d,
           ifelse(r > 1, cells - 1, total + 1),    # nord
           ifelse(k > 1, cells - nr, total + 1),   # ouest
           ifelse(r < nr, cells + 1, total + 1),   # sud
           ifelse(k < nc, cells + nr, total + 1))  # est
  }
  fresh <- seed_cell
  pending <- numeric()
  repeat {
    around <- unlist(lapply(1:4, function(d) neighbour(fresh, d)), use.names = FALSE)
    cand <- sort(unique(c(pending, around[around <= total])))
    cand <- cand[lab[cand] == 0L]
    cand <- cand[!is.na(v[cand]) & v[cand] > th_tree]
    if (length(cand) == 0L) break
    vc <- v[cand]
    rc <- (cand - 1) %% nr + 1; cc <- (cand - 1) %/% nr + 1
    got_label <- integer(length(cand))
    for (d in 1:4) {
      l <- lab[neighbour(cand, d)]
      k <- which(got_label == 0L & l > 0L)
      if (length(k) == 0L) next
      lk <- l[k]
      ok <- vc[k] > th_seed * seed_h[lk] &
        vc[k] > th_cr * (sum_h[lk] / cnt[lk]) &
        vc[k] <= seed_h[lk] * (1 + TREES_CROWN_OVERSHOOT) &
        abs(rc[k] - seed_r[lk]) < half & abs(cc[k] - seed_c[lk]) < half
      got_label[k[ok]] <- lk[ok]
    }
    got <- which(got_label > 0L)
    if (length(got) == 0L) break
    lab[cand[got]] <- got_label[got]
    cnt <- cnt + tabulate(got_label[got], n)
    sums <- rowsum(vc[got], got_label[got])
    idx <- as.integer(rownames(sums))
    sum_h[idx] <- sum_h[idx] + sums[, 1]
    pending <- cand[got_label == 0L]
    fresh <- cand[got]
  }
  tabulate(lab[seq_len(total)], n)
}

# ------------------------------------------------------------------ essence : polygone ou végétation

#' Essence dominante de chaque type de végétation : code espar de plus grande part dans la strate
#' arborée du biome de même `id` que le nom du type dans vegetation_map.csv. Rend un vecteur
#' nommé par type ; NA si le type n'a pas de biome, pas de strate arborée, ou une égalité de
#' parts entre essences (le motif est rendu dans l'attribut « motifs »). Règle PROVISOIRE.
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

#' Écrit rapport_arbres.html (UTF-8), les lignes groupées par section.
write_trees_report <- function(report, path) {
  write_html_report(report, path, "Rapport de prepare : arbres",
                    "Rapport de prepare : arbres détectés et peuplements")
}

#' Résumé en français d'une série de nombres : minimum, médiane, maximum.
summary_fr <- function(x, digits = 1L) {
  sprintf("minimum %s, médiane %s, maximum %s", fr_num(min(x), digits),
          fr_num(stats::median(x), digits), fr_num(max(x), digits))
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
                    d130 = "float64", h = "float64", crown_area = "float64",
                    species_source = "string", d130_source = "string")

#' Polygone nemeton de chaque point : `hit` vient de sf::st_intersects ; si plusieurs polygones
#' se recouvrent sur le point, celui du plus petit stand_id l'emporte (tri par octets, règle de
#' stand_map.tif, indépendante de l'ordre du fichier). Rend (poly, n_hits) : numéro de ligne du
#' polygone retenu (NA hors polygone) et nombre de polygones qui contiennent le point.
choose_polygon <- function(hit, stand_id) {
  rank <- match(stand_id, sort(stand_id, method = "radix"))
  poly <- vapply(hit, function(i) if (length(i) == 0L) NA_integer_ else i[which.min(rank[i])],
                 integer(1))
  list(poly = poly, n_hits = lengths(hit))
}

# ------------------------------------------------------------------ le module

#' Détecte les arbres, segmente les houppiers et écrit trees_init/ et rapport_arbres.html
#' (mission 018). À appeler après prepare (grid.tif, forest_mask.tif) et biomes (vegetation_map) ;
#' rend la liste des fichiers écrits. Une essence sans aucun coefficient d'allométrie arrête le
#' module avant toute écriture. `biomes_dir` : dossier des biomes (biomes/*.yml) ;
#' `species_csv` : référentiel des essences.
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
  check_input_file(out("grid.tif"))
  allometry_path <- file.path(zone_dir, "params", "allometry.parquet")
  if (!file.exists(allometry_path)) {
    stop(sprintf("coefficients d'allométrie absents : %s (import_tarif doit passer avant)",
                 allometry_path), call. = FALSE)
  }
  has_video <- file.exists(inp("inventaire_video.gpkg"))
  if (validate) {
    validate_file("inputs.chm", inp("chm.tif"), what = "entrée")
    validate_file("inputs.nemeton_stands", inp("nemeton_stands.gpkg"), what = "entrée")
    # la carte des types de végétation doit être au contrat et alignée sur la grille
    validate_file("biomes.vegetation_map", out("vegetation_map.tif"), grid = out("grid.tif"),
                  what = "entrée")
    validate_file("biomes.vegetation_categories", out("vegetation_map.csv"), what = "entrée")
    if (has_video) validate_file("inputs.inventaire_video", inp("inventaire_video.gpkg"), what = "entrée")
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

  # -- détection (MNH à sa résolution d'origine), puis houppiers
  chm <- read_raster_2154(inp("chm.tif"))
  chm_res <- terra::res(chm)[1]
  na_cells <- sum(is.na(terra::values(chm, mat = FALSE)))
  if (na_cells > 0L) {
    report_add(report, sec, sprintf("MNH : %d cellule(s) sans valeur, jamais candidates à un sommet", na_cells))
  }
  smooth <- smooth_chm(chm)
  det <- detect_trees(chm, smooth = smooth)
  cells <- segment_crowns(smooth, det)
  det$crown_area <- cells * chm_res^2
  report_add(report, sec, sprintf(
    "%d maxima locaux détectés sur le MNH de %s m, chacun avec son houppier segmenté ; paramètres PROVISOIRES repris de tarif-nemeton, lidR absent : détection et segmentation écrites avec terra",
    nrow(det), fr_num(chm_res)))

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
  pick <- choose_polygon(hit, st$table$stand_id)
  poly <- pick$poly
  multi <- pick$n_hits > 1L
  if (any(multi)) {
    pairs <- vapply(hit[multi], function(i) paste(sort(st$table$stand_id[i], method = "radix"),
                                                  collapse = " et "), character(1))
    report_add(report, "Recouvrements de polygones", sprintf(
      "%d arbre(s) tombent dans plusieurs polygones nemeton qui se recouvrent : le plus petit stand_id l'emporte (tri par octets, même règle que stand_map.tif, indépendante de l'ordre du fichier)",
      sum(multi)))
    tab <- table(pairs)
    for (p in names(tab)) {
      sp <- unique(st$table$species[st$table$stand_id %in% strsplit(p, " et ", fixed = TRUE)[[1]]])
      report_add(report, "Recouvrements de polygones", sprintf(
        "%s : %d arbre(s) ; %s", p, tab[[p]],
        if (length(sp) > 1L) "essences différentes, l'essence du plus petit stand_id est retenue"
        else "même essence, sans effet sur l'essence"))
    }
  } else {
    report_add(report, "Recouvrements de polygones",
               "aucun arbre dans plusieurs polygones nemeton (règle en cas de recouvrement : le plus petit stand_id l'emporte)")
  }
  det$species <- st$table$species[poly]
  det$species_source <- ifelse(is.na(poly), NA_character_, "nemeton")
  det$stand_id <- st$table$stand_id[poly]

  outside <- is.na(poly)
  if (any(outside)) {
    vr <- terra::rast(out("vegetation_map.tif"))
    cats <- utils::read.csv(out("vegetation_map.csv"), stringsAsFactors = FALSE, fileEncoding = "UTF-8")
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
    report_add(report, "Hors polygone nemeton",
               "l'essence d'un arbre hors polygone est l'essence de plus grande part dans la strate arborée du type de végétation : règle PROVISOIRE, en attente de la décision de Pascal")
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
  } else {
    report_add(report, "Hors polygone nemeton", "aucun arbre hors polygone nemeton")
  }
  no_species <- is.na(det$species)
  det <- det[!no_species, , drop = FALSE]

  # -- d130 : étage B, avec ou sans le terme du houppier. Une essence sans aucun coefficient
  # arrête le module AVANT toute écriture (aucune sortie à moitié).
  lacking <- species_without_coefficients(det$species, coef)
  if (length(lacking) > 0L) {
    n_lack <- vapply(lacking, function(sp) sum(det$species == sp), integer(1))
    stop(sprintf(
      "essence %s : aucun coefficient d'allométrie (a, b) pour le modèle etage_b dans %s ; d130 non calculable pour %d arbre(s), rien n'est écrit. Ajouter les coefficients de cette essence ou corriger l'essence du polygone nemeton ou du type de végétation.",
      paste(lacking, collapse = ", "), allometry_path, sum(n_lack)), call. = FALSE)
  }
  d <- d130_etage_b(det$species, det$h, det$crown_area, coef)
  det$d130 <- d$d130
  det$d130_source <- d$d130_source
  det <- det[order(det$tree_id), , drop = FALSE]
  if (nrow(det) == 0L) {
    stop("aucun arbre écrit : trees_init/ vide, voir le rapport des arbres", call. = FALSE)
  }

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

  # -- d130 et houppiers au rapport
  n_crown <- sum(det$d130_source == D130_SOURCE_CROWN)
  n_height <- sum(det$d130_source == D130_SOURCE_HEIGHT)
  report_add(report, "d130 et houppiers", sprintf(
    "d130 par l'étage B de tarif-nemeton, coefficients de params/allometry.parquet : %d arbre(s) avec le terme du houppier (ln D = a + b ln H + c ln CPA, d130_source = %s) ; %d arbre(s) d'essence sans coefficient c (ln D = a + b ln H, d130_source = %s)",
    n_crown, D130_SOURCE_CROWN, n_height, D130_SOURCE_HEIGHT))
  report_add(report, "d130 et houppiers", sprintf(
    "surface projetée des houppiers (crown_area, m²) : %s",  summary_fr(det$crown_area)))
  report_add(report, "d130 et houppiers",
             "le houppier est PROVISOIRE : la surface segmentée dans un MNH aéroporté n'est pas celle mesurée au TLS (houppiers imbriqués, sous-segmentation) sur laquelle le coefficient c a été calé ; réserve de tarif-nemeton (code/etage_b_allometrie_D.py), à recaler sur des arbres de référence")

  # -- origine et statut des paramètres de détection
  src <- "tarif-nemeton (https://github.com/pobsteta/tarif-nemeton, commit 0f51b9606165237b7cae2dda8809081adef869ac), code/etage_b_arbres_lidar.R"
  sec_p <- "Paramètres de détection"
  report_add(report, sec_p, sprintf(
    "hauteur minimale %s m : lmf(hmin = 5) à la l.18 et th_tree = 5 à la l.19 de %s", fr_num(TREES_HMIN_M), src))
  report_add(report, sec_p, sprintf(
    "médiane %dx%d cellules sur le MNH avant détection : focal(chm, w = 3, fun = median) à la l.17 de %s",
    TREES_SMOOTH_CELLS, TREES_SMOOTH_CELLS, src))
  report_add(report, sec_p, sprintf(
    "fenêtre de maximum local de %s m (arbre de moins de %s m) croissant vers %s m : f_ws à la l.13 de %s, reprise telle quelle (les coefficients de l'étage B y ont été calés) ; ici carrée, d'un nombre impair de cellules (lmf : circulaire)",
    fr_num(TREES_WINDOW_BASE_M), fr_num(TREES_WINDOW_H0_M),
    fr_num(TREES_WINDOW_BASE_M + TREES_WINDOW_GAIN_M), src))
  report_add(report, sec_p, sprintf(
    "houppiers par croissance de région (Dalponte et Coomes 2016) : th_tree = %s, th_seed = %s, th_cr = %s, max_cr = %d cellules (l.19 de %s) ; surface projetée = cellules du houppier x %s m² (tarif-nemeton : expanse du polygone, l.20, même surface)",
    fr_num(TREES_CROWN_TH_TREE), fr_num(TREES_CROWN_TH_SEED), fr_num(TREES_CROWN_TH_CR),
    as.integer(TREES_CROWN_MAX_CR), src, fr_num(chm_res^2)))
  report_add(report, sec_p,
             "écarts avec tarif-nemeton : lidR absent, algorithmes réécrits avec terra ; max_cr lu comme un diamètre en cellules et passes synchrones de la croissance de région, deux détails à vérifier contre lidR ; la hauteur h écrite est le maximum du MNH brut sur 3x3 cellules autour du sommet (tarif-nemeton : MNH lissé)")
  report_add(report, sec_p, "toutes ces valeurs sont PROVISOIRES : reprises de tarif-nemeton, non recalées sur ce MNH")

  # -- ce que ce module ne fait pas encore
  sec_n <- "Ce que ce module ne fait pas"
  report_add(report, sec_n,
             "la hauteur des arbres est celle du MNH à la date de vol (chm_date) : elle n'est pas avancée jusqu'à t0 (spec §4.4) ; l'avance attend la courbe de hauteur de dynamics (M2), pas encore ajustée")
  if (has_video) {
    lay <- sf::st_layers(inp("inventaire_video.gpkg"))
    report_add(report, sec_n, sprintf(
      "inventaire vidéo (inputs/inventaire_video.gpkg) : lu (%s) et %s, mais PAS UTILISÉ en M1a : la spec ne donne aucune règle d'usage pour l'état initial ; aucun arbre ne porte inventaire_video ; son usage (remplacer ou caler les arbres détectés sur ses placettes) est une question pour Pascal en M1b",
      paste(sprintf("%s : %d", lay$name, lay$features), collapse = ", "),
      if (validate) "validé à l'entrée (contrat inputs.inventaire_video)" else "non validé ici (validate = FALSE)"))
  } else {
    report_add(report, sec_n,
               "inventaire vidéo (inputs/inventaire_video.gpkg) absent (facultatif) ; il ne serait de toute façon pas utilisé en M1a")
  }

  # -- écriture
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
