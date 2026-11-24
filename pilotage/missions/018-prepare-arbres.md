# Mission 018 — prepare-arbres

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire dans `prepare` (R) la détection des arbres sur le MNH à 50 cm et `trees_init/` (essence du polygone nemeton ou du type de végétation, d130 par la méthode étage B réécrite et citée, colonnes species_source et d130_source), ainsi que `stands.parquet`, pour donner au moteur son état initial (spec §4).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | sources ci-dessous |
| A-t-il les moyens ? | oui, en partie | R 4.3.3 avec terra 1.7.65 et sf 1.0.15 ; targets et lidR à installer depuis CRAN ou r-universe, s'ils sont joignables ; sinon le dire |

**Temps de la main :** donner. **Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `R/prepare_trees.R`, `R/tests/testthat/test-prepare-trees.R`.
- **Périmètre étendu aux reprises (accepté par l'orchestrateur, journal du 24/11/2026) :** Makefile, _targets.R et R/modules.R (étape trees), contrat trees_init (crown_area) et ses tests, partie paramètres de tools/fixtures/make_zone_fictive.py, R/tests/testthat/test-modules.R.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** inventer une allométrie : les coefficients viennent de `params/allometry.parquet` ; copier du code de tarif-nemeton ; faire un commit git.
- **Sources autorisées :** docs/spec.md §4, /home/user/tarif-nemeton/code/etage_b_arbres_lidar.R en lecture seule (méthode à citer, pas à copier), lidR si installable (r-lidar.r-universe.dev).

## Valeur provisoire

- paramètres de détection (fenêtre, hauteur minimale) : provisoires

## Dépend de / rouge attendu jusqu'à

- 017 (grille) ; ordre de fusion : après 017

## Tests

- trees_init/ et stands.parquet passent contracts/validate ; l'arbre S03 du jeu fictif est détecté à sa place ; tests de 021

## Terrain

- **Échantillon que Pascal vérifiera :** `make prepare biomes trees ZONE=zone_fictive`, puis `rapport_prepare.html`, `rapport_biomes.html` et `rapport_arbres.html` ouverts dans un navigateur (étape trees ajoutée par la décision du journal du 24/11/2026).

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.
