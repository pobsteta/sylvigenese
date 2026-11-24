# Point d'entrée : Rscript R/tests/testthat.R   (depuis la racine du dépôt).
# Sort avec un code non nul si un test échoue.
library(testthat)
Sys.setenv(SYLVIGENESE_ROOT = normalizePath("."))
for (f in list.files("R", pattern = "[.]R$", full.names = TRUE)) source(f)
test_dir("R/tests/testthat", reporter = "summary", stop_on_failure = TRUE)
