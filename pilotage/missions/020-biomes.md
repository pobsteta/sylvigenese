# Mission 020 — biomes

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire le module `biomes` (R + YAML) : un catalogue de types de végétation pour le jeu fictif (`biomes/*.yml`, marqué provisoire), la carte `vegetation_map.tif` et sa table, et `rapport_biomes.html` (cellules forestières sans type, comblements, peuplements mono-essence), plus le contrat de la légende `inputs/types.csv` de sylvostation, pour remplir le critère M1a (spec §4, §11).

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

- **Peut (périmètre) :** `R/biomes.R`, `biomes/`, `R/tests/testthat/test-biomes.R`, `contracts/tables/inputs/station_types.schema.json` et son entrée dans `contracts/catalog.yml`, avec ses cas dans `contracts/tests/`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** présenter le catalogue fictif comme écologique ; faire un commit git.
- **Sources autorisées :** docs/spec.md §4, §8, §11, contracts/json/biome.schema.json.

## Valeur provisoire

- compositions et densités du catalogue fictif : synthétiques, provisoires

## Dépend de / rouge attendu jusqu'à

- 017 ; ordre de fusion : après 017

## Tests

- aucune cellule forestière sans type de végétation qui ne soit pas signalée dans le rapport ; sorties validées ; tests de 021

## Terrain

- **Échantillon que Pascal vérifiera :** `make prepare biomes ZONE=zone_fictive`, puis `rapport_biomes.html` ouvert dans un navigateur.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.
