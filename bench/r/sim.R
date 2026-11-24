#!/usr/bin/env Rscript
# Banc d'essai sylvigenese -- interface en ligne de commande (R).
# Exemple : Rscript bench/r/sim.R --variant r-base --n 500 --years 100 --seed 42 --threads 1 --out /tmp/x
args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", args, value = TRUE)[1])))
source(file.path(here, "R", "core.R"))

parse_cli <- function(a) {
  opt <- list(variant = "r-base", n = 500L, years = 100L, seed = 42, threads = 1L,
              out = NULL, inject_nan = NA, hmax_zero = FALSE)
  i <- 1
  need <- function() { if (i + 1 > length(a)) fail(paste0("Option sans valeur : ", a[i])); a[i + 1] }
  while (i <= length(a)) {
    switch(a[i],
      "--variant" = { opt$variant <- need(); i <- i + 1 },
      "--n" = { opt$n <- as.integer(need()); i <- i + 1 },
      "--years" = { opt$years <- as.integer(need()); i <- i + 1 },
      "--seed" = { opt$seed <- as.numeric(need()); i <- i + 1 },
      "--threads" = { opt$threads <- as.integer(need()); i <- i + 1 },
      "--out" = { opt$out <- need(); i <- i + 1 },
      "--inject-nan" = { opt$inject_nan <- as.integer(need()); i <- i + 1 },
      "--hmax-zero" = { opt$hmax_zero <- TRUE },
      fail(paste0("Option inconnue : ", a[i])))
    i <- i + 1
  }
  if (is.null(opt$out)) fail("Option --out obligatoire.")
  if (!opt$variant %in% c("r-base", "r-rcpp")) fail("--variant doit valoir r-base ou r-rcpp.")
  if (is.na(opt$n) || opt$n < 2 || is.na(opt$years) || opt$years < 0 || is.na(opt$threads) || opt$threads < 1)
    fail("Valeur invalide pour --n, --years ou --threads.")
  opt
}

opt <- parse_cli(commandArgs(trailingOnly = TRUE))
load_cpp(here)                       # compilation hors chronomètre (cache dans bench/r/.cache)
dir.create(opt$out, showWarnings = FALSE, recursive = TRUE)
res <- run_sim(opt$variant, opt$n, opt$years, opt$seed, opt$threads, opt$inject_nan, opt$hmax_zero)

tw <- proc.time()[["elapsed"]]
writeLines(format_summary(res$summary), file.path(opt$out, "summary.csv"))
con <- file(file.path(opt$out, "state_final.f32"), "wb")
for (nm in c("B", "D", "H")) writeBin(as.vector(res$state[[nm]]), con, size = 4L, endian = "little")
close(con)
write_s <- proc.time()[["elapsed"]] - tw
tm <- res$timing
writeLines(sprintf(paste0('{"lang": "%s", "n": %d, "years": %d, "threads": %d, "init_s": %.6f, ',
                          '"step_mean_s": %.6f, "total_s": %.6f, "write_s": %.6f}'),
                   opt$variant, opt$n, opt$years, opt$threads, tm$init_s, tm$step_mean_s,
                   tm$total_s, write_s), file.path(opt$out, "timing.json"))
