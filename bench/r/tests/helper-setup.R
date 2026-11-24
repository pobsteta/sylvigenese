# Chargé automatiquement par testthat avant les tests.
ROOT <- normalizePath(file.path(testthat::test_path(), ".."))
source(file.path(ROOT, "R", "core.R"))
load_cpp(ROOT)

# Lance sim.R dans un processus séparé ; renvoie code de sortie et stderr.
run_cli <- function(...) {
  err <- tempfile()
  st <- suppressWarnings(system2("Rscript", shQuote(c(file.path(ROOT, "sim.R"), ...)),
                                 stdout = FALSE, stderr = err))
  list(status = st, stderr = paste(readLines(err, warn = FALSE), collapse = "\n"))
}
