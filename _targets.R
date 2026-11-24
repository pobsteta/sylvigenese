# Pipeline R de sylvigenese : prepare -> biomes -> trees, prepare -> dynamics (spec §2).
# Squelette (mission 012) : chaque cible lit config.yml et appelle le validateur.
# `prepare` construit en plus la grille de 25 m et ses rasters (mission 017, R/prepare_grid.R).
# Lancer : Rscript -e 'targets::tar_make()'   (nécessite le paquet R `targets`)

library(targets)

# Tout R/*.R : les outils communs (commun.R, config.R, validateur.R, spec §2) et les modules.
for (f in list.files("R", pattern = "[.]R$", full.names = TRUE)) source(f)

list(
  tar_target(config_file, "config.yml", format = "file"),
  tar_target(prepare, {
    s <- run_prepare(config_file)
    check_status(s, "prepare")
  }),
  tar_target(biomes, {
    s <- run_biomes(config_file, depends_on = prepare)
    check_status(s, "biomes")
  }),
  tar_target(trees, {
    s <- run_trees(config_file, depends_on = biomes)
    check_status(s, "trees")
  }),
  tar_target(dynamics, {
    s <- run_dynamics(config_file, depends_on = prepare)
    check_status(s, "dynamics")
  })
)
