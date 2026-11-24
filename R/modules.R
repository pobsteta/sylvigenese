# Squelette des modules R : prepare, biomes, dynamics (BRIEF §12, spec §2).
# Chaque module lit config.yml, fait valider ce fichier par le validateur, puis rend
# son code de sortie : 0 (tout va bien) ou 2 (impossible, message sur stderr).
# Aucune logique métier ici.

#' Exécute un module et renvoie 0 ou 2.
#' `depends_on` ne sert qu'à ordonner les cibles de `_targets.R`.
run_module <- function(name, config_path = "config.yml", depends_on = NULL) {
  tryCatch({
    read_config(config_path)
    status <- call_validator(c("config", config_path))
    if (status != 0L) {
      stop(sprintf("config.yml non conforme (validateur, code %d)", status), call. = FALSE)
    }
    message(sprintf("[%s] config.yml lu et conforme ; rien d'autre à faire (squelette).", name))
    0L
  }, error = function(e) {
    message(sprintf("[%s] erreur : %s", name, conditionMessage(e)))
    2L
  })
}

run_prepare <- function(config_path = "config.yml", depends_on = NULL) {
  run_module("prepare", config_path, depends_on)
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
