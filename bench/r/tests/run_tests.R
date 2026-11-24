#!/usr/bin/env Rscript
# Lance tous les tests : Rscript bench/r/tests/run_tests.R
args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", args, value = TRUE)[1])))
invisible(Sys.setlocale("LC_ALL", "C.UTF-8"))   # messages en français (UTF-8)
res <- testthat::test_dir(here, reporter = "summary", stop_on_failure = FALSE)
df <- as.data.frame(res)
cat(sprintf("\nBilan : %d tests, %d échecs, %d erreurs, %d ignorés\n",
            sum(df$nb), sum(df$failed), sum(df$error), sum(df$skipped)))
quit(status = if (sum(df$failed) + sum(df$error) > 0) 1L else 0L)
