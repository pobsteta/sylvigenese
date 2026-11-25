# Squelette des modules R : prepare, biomes, dynamics (BRIEF §12, spec §2).
# Chaque module lit config.yml, fait valider ce fichier par le validateur, puis rend
# son code de sortie : 0 (tout va bien) ou 2 (impossible, message sur stderr).
# Aucune logique métier ici.
#
# Chargement : tout R/*.R est lu avant l'appel d'un module (Makefile, _targets.R,
# R/tests/testthat.R). R/commun.R (rapports, lecture en EPSG:2154, écriture des grilles,
# validation, Parquet), R/config.R et R/validateur.R sont les outils communs à tous les modules R
# (spec §2) ; aucun module n'appelle le code d'un autre.

#' Dit un message sur la sortie d'erreur, en UTF-8 lisible quelle que soit la locale.
#' `message()` écrit sous LC_ALL=C les caractères accentués en octets échappés (entr\303\251e) ;
#' ici le texte part tel quel, en octets UTF-8. Reste un vrai message R : `suppressMessages()` et
#' les gestionnaires `message =` des tests le voient comme avant.
say_utf8 <- function(text) {
  # Sous LC_ALL=C, les littéraux accentués du code source n'ont pas d'encodage déclaré mais sont
  # de l'UTF-8 valide : on les déclare tels quels ; enc2utf8() les écrirait <c3><a9>.
  text <- paste(text, collapse = "")
  if (identical(Encoding(text), "unknown") && validUTF8(text)) Encoding(text) <- "UTF-8"
  text <- enc2utf8(text)
  withRestarts({
    signalCondition(simpleMessage(paste0(text, "\n"), call = NULL))
    writeLines(text, con = stderr(), useBytes = TRUE)
  }, muffleMessage = function() NULL)
  invisible(NULL)
}

#' Exécute un module et renvoie 0 ou 2.
#' `depends_on` ne sert qu'à ordonner les cibles de `_targets.R`.
#' `work` : fonction(config, config_path) du module ; absente, le module est un squelette.
run_module <- function(name, config_path = "config.yml", depends_on = NULL, work = NULL) {
  tryCatch({
    read_config(config_path)
    status <- call_validator(c("config", config_path))
    if (status != 0L) {
      stop(sprintf("config.yml non conforme (validateur, code %d)", status), call. = FALSE)
    }
    if (is.null(work)) {
      say_utf8(sprintf("[%s] config.yml lu et conforme ; rien d'autre à faire (squelette).", name))
    } else {
      cfg <- read_config(config_path)
      work(cfg, config_path)
    }
    0L
  }, error = function(e) {
    say_utf8(sprintf("[%s] erreur : %s", name, conditionMessage(e)))
    2L
  })
}

# prepare : grille et rasters alignés, dont stand_map (mission 017, R/prepare_grid.R), tables IFN
# (019, R/prepare_ifn.R) et peuplements stands.parquet (018, R/prepare_trees.R).
run_prepare <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("prepare", config_path, depends_on, work = function(cfg, config_path) {
    zone_dir <- prepare_zone_dir(cfg)
    if (!dir.exists(zone_dir)) {
      stop(sprintf("dossier de la zone introuvable : %s", zone_dir), call. = FALSE)
    }
    # Les entrées IFN et les peuplements nemeton (essences du référentiel) sont contrôlés AVANT
    # la première écriture (grid.tif, ...) : une entrée refusée ne laisse aucune sortie à moitié
    # produite. Les signalements IFN vont dans le même rapport_prepare.html que ceux de la grille.
    report <- new_report()
    ifn <- prepare_ifn_check(zone_dir, report)
    stands <- prepare_stands_check(zone_dir)
    prepare_grid(zone_dir, cfg, report = report)
    prepare_ifn(zone_dir, checked = ifn)
    prepare_stands(zone_dir, cfg, checked = stands)
  })
}

# biomes : types de végétation, carte et rapport (mission 020, R/biomes.R).
run_biomes <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("biomes", config_path, depends_on, work = function(cfg, config_path) {
    zone_dir <- prepare_zone_dir(cfg)
    if (!dir.exists(zone_dir)) {
      stop(sprintf("dossier de la zone introuvable : %s", zone_dir), call. = FALSE)
    }
    biomes_run(zone_dir, cfg)
  })
}

# trees : arbres détectés, trees_init/ (mission 018, R/prepare_trees.R). Après biomes :
# l'essence hors polygone vient de vegetation_map ; sans elle, erreur (code 2).
run_trees <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("trees", config_path, depends_on, work = function(cfg, config_path) {
    zone_dir <- prepare_zone_dir(cfg)
    if (!dir.exists(zone_dir)) {
      stop(sprintf("dossier de la zone introuvable : %s", zone_dir), call. = FALSE)
    }
    prepare_trees(zone_dir, cfg)
  })
}

run_dynamics <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("dynamics", config_path, depends_on)
}

#' Pour `targets` : arrête le pipeline si un module n'a pas rendu 0.
check_status <- function(status, name) {
  if (!identical(status, 0L)) {
    stop(sprintf("le module %s a échoué (code %s)", name, status), call. = FALSE)
  }
  invisible(status)
}
