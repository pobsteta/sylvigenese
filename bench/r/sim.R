#!/usr/bin/env Rscript
# Banc d'essai sylvigenese -- interface en ligne de commande (R).
# Exemple : Rscript bench/r/sim.R --variant r-base --n 500 --years 100 --seed 42 --threads 1 --out /tmp/x
args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", args, value = TRUE)[1])))
source(file.path(here, "R", "core.R"))

# AM2 : entier écrit en chiffres décimaux (et rien d'autre), borné ; sinon refus (code 2).
parse_uint <- function(name, txt, lo, hi) {
  if (!is.character(txt) || length(txt) != 1 || is.na(txt) || !grepl("^[0-9]+$", txt))
    fail(sprintf("Valeur refusée pour %s : « %s » n'est pas un entier écrit en chiffres décimaux.", name, txt))
  v <- as.numeric(txt)
  if (v < lo || v > hi)
    fail(sprintf("Valeur refusée pour %s : %s est hors de l'intervalle [%s, %s].", name, txt,
                 format(lo, scientific = FALSE), format(hi, scientific = FALSE)))
  v
}

parse_cli <- function(a) {
  opt <- list(variant = "r-base", n = 500L, years = 100L, seed = 42, threads = 1L,
              out = NULL, inject_nan = NA, hmax_zero = FALSE)
  i <- 1
  need <- function() { if (i + 1 > length(a)) fail(paste0("Option sans valeur : ", a[i])); a[i + 1] }
  while (i <= length(a)) {
    switch(a[i],
      "--variant" = { opt$variant <- need(); i <- i + 1 },
      "--n" = { opt$n <- as.integer(parse_uint("--n", need(), 2, 46340)); i <- i + 1 },  # n^2 < 2^31
      "--years" = { opt$years <- as.integer(parse_uint("--years", need(), 1, 1e6)); i <- i + 1 },
      "--seed" = { opt$seed <- parse_uint("--seed", need(), 0, 2^53 - 1); i <- i + 1 },
      "--threads" = { opt$threads <- as.integer(parse_uint("--threads", need(), 1, 1024)); i <- i + 1 },
      "--out" = { opt$out <- need(); i <- i + 1 },
      "--inject-nan" = { opt$inject_nan <- as.integer(parse_uint("--inject-nan", need(), 0, 1e6)); i <- i + 1 },
      "--hmax-zero" = { opt$hmax_zero <- TRUE },
      fail(paste0("Option inconnue : ", a[i])))
    i <- i + 1
  }
  if (is.null(opt$out)) fail("Option --out obligatoire.")
  if (!opt$variant %in% c("r-base", "r-rcpp")) fail("--variant doit valoir r-base ou r-rcpp.")
  opt
}

opt <- parse_cli(commandArgs(trailingOnly = TRUE))
load_cpp(here)                       # compilation hors chronomètre (cache dans bench/r/.cache)
dir.create(opt$out, showWarnings = FALSE, recursive = TRUE)
# r-base est mono-fil : le nombre de fils effectif (1) est celui qu'on inscrit dans timing.json.
threads_eff <- if (opt$variant == "r-base") 1L else opt$threads
oom <- function(e) {                      # AM3 : échec d'allocation -> code 4
  msg <- conditionMessage(e)
  if (grepl("cannot allocate|bad_alloc|vector memory", msg)) {
    taille <- regmatches(msg, regexpr("[0-9.]+ [KMGT]b", msg))
    fail(paste0("Mémoire insuffisante", if (length(taille)) paste0(" : allocation de ", taille, " impossible") else "",
                " (n = ", opt$n, ", variante ", opt$variant, ")."), code = 4L)
  }
  stop(e)
}
res <- tryCatch(run_sim(opt$variant, opt$n, opt$years, opt$seed, threads_eff, opt$inject_nan, opt$hmax_zero),
                error = oom)

tw <- proc.time()[["elapsed"]]
writeLines(format_summary(res$summary), file.path(opt$out, "summary.csv"))
con <- file(file.path(opt$out, "state_final.f32"), "wb")
for (nm in c("B", "D", "H")) writeBin(as.vector(res$state[[nm]]), con, size = 4L, endian = "little")
close(con)
write_s <- proc.time()[["elapsed"]] - tw
tm <- res$timing
writeLines(sprintf(paste0('{"lang": "%s", "n": %d, "years": %d, "threads": %d, "init_s": %.6f, ',
                          '"step_mean_s": %.6f, "total_s": %.6f, "write_s": %.6f}'),
                   opt$variant, opt$n, opt$years, threads_eff, tm$init_s, tm$step_mean_s,
                   tm$total_s, write_s), file.path(opt$out, "timing.json"))
