# Squelette des modules R : prepare, biomes, dynamics (BRIEF §12, spec §2).
# Chaque module lit config.yml, fait valider ce fichier par le validateur, puis rend
# son code de sortie : 0 (tout va bien) ou 2 (impossible, message sur stderr).
# Aucune logique métier ici.

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
      message(sprintf("[%s] config.yml lu et conforme ; rien d'autre à faire (squelette).", name))
    } else {
      cfg <- read_config(config_path)
      work(cfg, config_path)
    }
    0L
  }, error = function(e) {
    message(sprintf("[%s] erreur : %s", name, conditionMessage(e)))
    2L
  })
}

# prepare : grille et rasters alignés (mission 017, R/prepare_grid.R). Les tables IFN
# (019) et les arbres (018) s'ajoutent à `work` dans leurs missions.
run_prepare <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("prepare", config_path, depends_on, work = function(cfg, config_path) {
    zone_dir <- prepare_zone_dir(cfg)
    if (!dir.exists(zone_dir)) {
      stop(sprintf("dossier de la zone introuvable : %s", zone_dir), call. = FALSE)
    }
    prepare_grid(zone_dir, cfg)
    prepare_ifn(zone_dir)
  })
}

run_biomes <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("biomes", config_path, depends_on)
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
