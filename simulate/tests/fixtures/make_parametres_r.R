# Produit les valeurs de référence R de tests/parametres.rs (mission 035).
#
# Usage, depuis la racine du dépôt :
#   Rscript simulate/tests/fixtures/make_parametres_r.R
#
# Les fonctions sont prises telles quelles dans le code du dépôt, par leur nom, sans recopie :
# dyn_ncs, dyn_eta, dyn_write_params et DYN_PARAM_COLUMNS dans R/dynamics.R ; .require_arrow
# dans R/commun.R. Le reste de ces fichiers n'est pas évalué.
#
# Sorties (versionnées, sous simulate/tests/fixtures/parametres/) :
#   splines_noeuds.csv   cas, x, y : les nœuds de chaque cas ;
#   splines_valeurs.csv  cas, x, valeur : dyn_ncs aux abscisses d'essai (dedans, aux nœuds, hors
#                        des nœuds extrêmes) ;
#   params_essai.parquet un petit jeu au contrat dynamics_params, écrit par dyn_write_params ;
#   eta_valeurs.csv      ligne, d130, ba_plot, trophic, ser_code, eta : dyn_eta du jeu
#                        growth_gam de l'essence 09, et le nombre de SER sans effet.
#
# Les nombres du jeu d'essai sont FICTIFS, sans aucun sens écologique (provisoire = TRUE) : ils
# ne servent qu'à vérifier que Rust relit comme R. Nombres écrits en %.17g (aller-retour exact).

pick <- function(file, names) {
  env <- new.env(parent = globalenv())
  exprs <- parse(file, keep.source = FALSE, encoding = "UTF-8")
  for (e in exprs) {
    if (is.call(e) && identical(e[[1L]], as.name("<-")) && is.name(e[[2L]]) &&
        as.character(e[[2L]]) %in% names) {
      eval(e, envir = env)
    }
  }
  missing <- setdiff(names, ls(env, all.names = TRUE))
  if (length(missing)) stop("introuvable dans ", file, " : ", paste(missing, collapse = ", "))
  env
}

dyn <- pick("R/dynamics.R", c("dyn_ncs", "dyn_eta", "dyn_write_params", "DYN_PARAM_COLUMNS"))
com <- pick("R/commun.R", ".require_arrow")
environment(dyn$dyn_write_params) <- dyn
assign(".require_arrow", com$.require_arrow, envir = dyn)

out <- "simulate/tests/fixtures/parametres"
dir.create(out, recursive = TRUE, showWarnings = FALSE)
fmt <- function(v) sprintf("%.17g", v)

# ------------------------------------------------------------------ splines seules
cases <- list(
  deux_noeuds = list(x = c(0, 10), y = c(-1, 3)),
  trois_noeuds = list(x = c(-2, 0.5, 4), y = c(0.7, -0.2, 1.1)),
  cinq_irreguliers = list(x = c(7.5, 12, 23.7, 41, 88.3), y = c(-0.41, -0.12, 0.05, 0.11, -0.3)),
  huit_grands = list(x = c(0, 3, 9, 10, 15.5, 30, 31, 60), y = c(1200, -350, 47, 980, -2.5, 15, 600, -800)),
  six_reguliers = list(x = seq(0, 50, by = 10), y = c(0, 0.3, 0.1, -0.2, 0.4, 0.15))
)
nodes <- do.call(rbind, lapply(names(cases), function(k) {
  data.frame(cas = k, x = fmt(cases[[k]]$x), y = fmt(cases[[k]]$y))
}))
write.csv(nodes, file.path(out, "splines_noeuds.csv"), row.names = FALSE, quote = FALSE)

vals <- do.call(rbind, lapply(names(cases), function(k) {
  xk <- cases[[k]]$x
  lo <- min(xk); hi <- max(xk); w <- hi - lo
  set.seed(35L)
  xs <- sort(c(xk, lo - 0.3 * w, lo - 1e-9, hi + 1e-9, hi + 2 * w,
               lo + w * c(0.001, 0.25, 0.5, 0.999), stats::runif(25, lo, hi)))
  data.frame(cas = k, x = fmt(xs), valeur = fmt(dyn$dyn_ncs(xk, cases[[k]]$y, xs)))
}))
write.csv(vals, file.path(out, "splines_valeurs.csv"), row.names = FALSE, quote = FALSE)

# ------------------------------------------------------------------ jeu d'essai au contrat
# \u00e9 : le script reste juste sous LC_ALL=C (pas de littéral non ASCII).
src <- "jeu d'essai de la mission 035 (valeurs fictives, sans sens \u00e9cologique)"
row <- function(species, group, model, term, variable, x, value) {
  data.frame(species = species, species_group = group, model = model, term = term,
             variable = variable, x = x, value = value, provisoire = TRUE, source = src,
             stringsAsFactors = FALSE)
}
spl <- function(species, group, model, v, xk, yk) {
  row(species, group, model, sprintf("s(%s)[%02d]", v, seq_along(xk)), v, xk, yk)
}
NAc <- NA_character_
params <- rbind(
  row("09", NAc, "growth_gam", "intercept", NAc, NA, -1.234),
  spl("09", NAc, "growth_gam", "d130", c(7.5, 20, 35, 55, 90), c(-0.4, -0.05, 0.12, 0.2, 0.05)),
  spl("09", NAc, "growth_gam", "ba_plot", c(0, 10, 25, 50), c(0.3, 0.1, -0.15, -0.5)),
  spl("09", NAc, "growth_gam", "trophic", c(2.1, 3.4, 5.9), c(-0.2, 0.02, 0.18)),
  row("09", NAc, "growth_gam", c("ser_code=A11", "ser_code=B21"), "ser_code", NA, c(0.05, -0.07)),
  row("09", NAc, "growth_gam", c("scale", "tweedie_p"), NAc, NA, c(0.31, 1.42)),
  row(NAc, "feuillu", "growth_gam", "intercept", NAc, NA, -1.5),
  spl(NAc, "feuillu", "growth_gam", "d130", c(7.5, 30, 80), c(-0.3, 0.1, 0)),
  row(NAc, "toutes_essences", "growth_gam", "intercept", NAc, NA, -1.7),
  spl(NAc, "toutes_essences", "growth_gam", "d130", c(7.5, 100), c(-0.2, 0.2)),
  row(NAc, "toutes_essences", "mortality_gam", "intercept", NAc, NA, -4.1),
  row("61", NAc, "chapman_richards", c(sprintf("A_class%d", 1:5), "k", "p"), NAc, NA,
      c(32, 28, 24, 20, 16, 0.021, 1.3))
)
dyn$dyn_write_params(params, file.path(out, "params_essai.parquet"))

# ------------------------------------------------------------------ η de référence
g09 <- params[!is.na(params$species) & params$species == "09" & params$model == "growth_gam", ]
set.seed(20261125L)
nd <- data.frame(
  d130 = c(7.5, 90, 3, 150, stats::runif(16, 5, 100)),
  ba_plot = c(0, 50, -1, 70, stats::runif(16, 0, 55)),
  trophic = c(2.1, 5.9, 1, 7, stats::runif(16, 1.8, 6.2)),
  ser_code = c("A11", "B21", "K13", "A11", rep(c("A11", "B21", "G90", "B21"), 4)),
  stringsAsFactors = FALSE
)
eta <- dyn$dyn_eta(g09, nd)
write.csv(data.frame(ligne = seq_len(nrow(nd)), d130 = fmt(nd$d130), ba_plot = fmt(nd$ba_plot),
                     trophic = fmt(nd$trophic), ser_code = nd$ser_code, eta = fmt(eta)),
          file.path(out, "eta_valeurs.csv"), row.names = FALSE, quote = FALSE)
writeLines(as.character(attr(eta, "unseen_ser")), file.path(out, "eta_ser_sans_effet.txt"))
cat("valeurs de référence écrites dans", out, "\n")
