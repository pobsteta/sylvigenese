# Tests du squelette R (mission 012). Lancés par `make test-r` depuis la racine du dépôt.
# Le validateur est remplacé par un faux script pour les cas 0 / 3 / absent ;
# un test d'intégration appelle le vrai validateur (rouge tant que la mission 009
# n'est pas dans l'arbre ; SYLVIGENESE_VALIDATE peut le désigner).

# test_dir() change de dossier courant : la racine du dépôt vient du lanceur.
racine <- Sys.getenv("SYLVIGENESE_ROOT", unset = normalizePath("../../.."))

faux_validateur <- function(code) {
  f <- tempfile(fileext = ".py")
  writeLines(c("import sys", sprintf("sys.exit(%d)", code)), f)
  f
}

copie_config <- function() {
  f <- tempfile(fileext = ".yml")
  file.copy(file.path(racine, "config.yml"), f)
  f
}

# Exécute `code` avec SYLVIGENESE_VALIDATE = chemin, puis remet l'ancienne valeur.
avec_validateur <- function(chemin, code) {
  ancien <- Sys.getenv("SYLVIGENESE_VALIDATE", unset = NA)
  Sys.setenv(SYLVIGENESE_VALIDATE = chemin)
  on.exit(if (is.na(ancien)) Sys.unsetenv("SYLVIGENESE_VALIDATE")
          else Sys.setenv(SYLVIGENESE_VALIDATE = ancien), add = TRUE)
  force(code)
}

test_that("read_config lit config.yml du dépôt", {
  cfg <- read_config(file.path(racine, "config.yml"))
  expect_equal(cfg$crs, "EPSG:2154")
  expect_equal(cfg$grid$resolution_m, 25)
  expect_equal(cfg$management, "none")
})

test_that("read_config refuse un fichier absent", {
  expect_error(read_config("/nulle/part/config.yml"), "introuvable")
})

test_that("chaque module rend 0 si le validateur dit 0", {
  avec_validateur(faux_validateur(0), {
    for (f in list(run_prepare, run_biomes, run_dynamics)) {
      expect_equal(suppressMessages(f(copie_config())), 0L)
    }
  })
})

test_that("chaque module rend 2 si le validateur refuse la config", {
  avec_validateur(faux_validateur(3), {
    for (f in list(run_prepare, run_biomes, run_trees, run_dynamics)) {
      expect_equal(suppressMessages(f(copie_config())), 2L)
    }
  })
})

test_that("trees rend 2 si le dossier de la zone est introuvable, sans rien écrire", {
  config <- copie_config()
  texte <- readLines(config, encoding = "UTF-8")
  writeLines(sub("^zone: zone_fictive", "zone: zone_absente", texte), config)
  msgs <- character()
  avec_validateur(faux_validateur(0), {
    status <- withCallingHandlers(run_trees(config),
      message = function(m) { msgs <<- c(msgs, conditionMessage(m)); invokeRestart("muffleMessage") })
  })
  expect_equal(status, 2L)
  expect_match(paste(msgs, collapse = "\n"), "introuvable")
})

test_that("rend 2 si le validateur est absent", {
  avec_validateur("/nulle/part/validate", {
    expect_equal(suppressMessages(run_prepare(copie_config())), 2L)
  })
})

test_that("rend 2 si config.yml est absent", {
  avec_validateur(faux_validateur(0), {
    expect_equal(suppressMessages(run_biomes("/nulle/part/config.yml")), 2L)
  })
})

test_that("check_status arrête le pipeline sur un code non nul", {
  expect_silent(check_status(0L, "prepare"))
  expect_error(check_status(2L, "prepare"), "prepare")
})

test_that("_targets.R est du R valide et nomme les trois modules", {
  texte <- paste(deparse(parse(file.path(racine, "_targets.R"))), collapse = "\n")
  for (m in c("run_prepare", "run_biomes", "run_dynamics")) expect_match(texte, m)
})

test_that("intégration : le vrai validateur accepte config.yml", {
  # Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
  ancien_wd <- setwd(racine)
  on.exit(setwd(ancien_wd), add = TRUE)
  expect_equal(suppressMessages(run_prepare(file.path(racine, "config.yml"))), 0L)
})
