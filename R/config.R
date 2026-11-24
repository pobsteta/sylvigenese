# Lecture de config.yml (BRIEF §12, spec §2).
# Le contrôle des clés est fait par le validateur (contracts/json/config.schema.json),
# pas ici : ce fichier ne fait que lire.

#' Lit config.yml et renvoie son contenu sous forme de liste.
#' Arrête avec un message en français si le fichier est absent ou illisible.
read_config <- function(path = "config.yml") {
  if (!file.exists(path)) {
    stop(sprintf("config.yml introuvable : %s", path), call. = FALSE)
  }
  cfg <- tryCatch(
    # UTF-8 explicite : sans lui, les accents des commentaires échouent en locale C.
    yaml::yaml.load(paste(readLines(path, warn = FALSE, encoding = "UTF-8"),
                          collapse = "\n")),
    error = function(e) {
      stop(sprintf("config.yml illisible (%s) : %s", path, conditionMessage(e)),
           call. = FALSE)
    }
  )
  if (!is.list(cfg)) {
    stop(sprintf("config.yml vide ou mal formé : %s", path), call. = FALSE)
  }
  cfg
}
