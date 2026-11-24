# Pipeline R de sylvigenese : prepare -> biomes, prepare -> dynamics (spec §2).
# Squelette (mission 012) : chaque cible lit config.yml et appelle le validateur.
# Lancer : Rscript -e 'targets::tar_make()'   (nécessite le paquet R `targets`)

library(targets)

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
  tar_target(dynamics, {
    s <- run_dynamics(config_file, depends_on = prepare)
    check_status(s, "dynamics")
  })
)
