# Appel du validateur des contrats en sous-processus (spec §2, ADR 0002).
# Aucun import du code du validateur : c'est un passage par fichiers.

#' Chemin du validateur : variable SYLVIGENESE_VALIDATE si elle existe,
#' sinon contracts/validate depuis le dossier courant (la racine du dépôt).
validator_path <- function() {
  env <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = "")
  if (nzchar(env)) env else file.path("contracts", "validate")
}

#' Lance `python3 <validateur> <args>` et renvoie son code de sortie
#' (0 conforme, 2 contrôle impossible, 3 non conforme).
#' Arrête si le validateur est absent : on ne devine pas qu'un fichier est conforme.
call_validator <- function(args) {
  validator <- validator_path()
  if (!file.exists(validator)) {
    stop(sprintf("validateur introuvable : %s (mission 009)", validator), call. = FALSE)
  }
  status <- suppressWarnings(system2("python3", c(validator, args)))
  as.integer(status)
}
