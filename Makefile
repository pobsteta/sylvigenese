# sylvigenese : parcours d'un bout à l'autre (BRIEF §12, spec §2). Squelette de la mission 012.
# Chaque cible lance un module ; chaque module lit config.yml et appelle le validateur.
# Tout se lance depuis la racine du dépôt.

CONFIG ?= config.yml
ZONE   ?= zone_fictive

# Le jeu fictif est versionné sous tests/fixtures ; les autres zones sont sous data/ (hors dépôt).
ifeq ($(ZONE),zone_fictive)
ZONE_DIR = tests/fixtures/zone_fictive
else
ZONE_DIR = data/$(ZONE)
endif

R_LOAD = for (f in list.files("R", pattern = "[.]R$$", full.names = TRUE)) source(f)
PY     = PYTHONPATH=python python3 -m sylvigenese

.PHONY: all validate validate-config prepare import_tarif biomes trees dynamics simulate post assets \
        viewer-web viewer test test-r test-rust test-python test-web

all: prepare import_tarif biomes trees dynamics simulate post assets viewer-web

# Contrôle des fichiers d'une zone contre les contrats : make validate ZONE=zone_fictive
validate:
	python3 contracts/validate --zone $(ZONE_DIR)

validate-config:
	python3 contracts/validate config $(CONFIG)

prepare:
	Rscript -e '$(R_LOAD); quit(status = run_prepare("$(CONFIG)"))'

biomes:
	Rscript -e '$(R_LOAD); quit(status = run_biomes("$(CONFIG)"))'

trees:
	Rscript -e '$(R_LOAD); quit(status = run_trees("$(CONFIG)"))'

dynamics:
	Rscript -e '$(R_LOAD); quit(status = run_dynamics("$(CONFIG)"))'

import_tarif:
	$(PY).import_tarif --config $(CONFIG)

post:
	$(PY).post --config $(CONFIG)

assets:
	$(PY).assets --config $(CONFIG)

# simulate (mission 038) : compilé en release, dépendances figées (--locked) ; écrit <zone>/sim/.
# La zone vient de `zone` de $(CONFIG) (jeu fictif sous tests/fixtures, sinon data/<zone>).
simulate:
	cargo run --release --locked --quiet --manifest-path simulate/Cargo.toml -- --config $(CONFIG)

viewer-web:
	node viewer-web/src/main.ts --config $(CONFIG)

# Vue web locale (mission 029) : serveur statique au premier plan sur http://127.0.0.1:$(PORT)/
# (npm ci dans viewer-web une fois ; PORT et ZONE modifiables).
PORT ?= 8080
viewer:
	node viewer-web/src/serveur.ts --zone $(ZONE) --zone-dir $(ZONE_DIR) --port $(PORT)

# Tests : un par langage. Les tests d'intégration appellent le vrai validateur
# (contracts/validate) ; SYLVIGENESE_VALIDATE peut en désigner un autre.
test: test-r test-rust test-python test-web

test-r:
	Rscript R/tests/testthat.R

test-rust:
	cargo test --manifest-path simulate/Cargo.toml

test-python:
	python3 -m pytest python -q -p no:cacheprovider

test-web:
	cd viewer-web && npm test
