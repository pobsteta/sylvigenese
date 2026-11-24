# Mission 019 — prepare-ifn

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire dans `prepare` (R) la préparation des tables IFN (`ifn/plots.parquet`, `ifn/trees.parquet`, `ifn/flora.parquet` : d130 = c13/(10π), poids par cercle 6, 9 et 15 m, gradients à la placette) avec la garde `assert_no_fine_extract_on_ifn()` reprise de sylvostation, pour que `dynamics` s'ajuste sans croiser l'IFN avec un raster fin (spec §6).

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

- **Peut (périmètre) :** `R/prepare_ifn.R`, `R/ifn_guard.R`, `R/tests/testthat/test-prepare-ifn.R`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** lire `station_gradients.tif` aux placettes IFN ; modifier la garde de sylvostation ; faire un commit git.
- **Sources autorisées :** docs/spec.md §6, docs/referentiels/ifn-placettes.md, /tmp/claude-0/repos/sylvostation/R/utils.R (lecture seule, garde à reprendre avec citation).

## Valeur provisoire

- aucune

## Dépend de / rouge attendu jusqu'à

- aucune

## Tests

- les tables passent contracts/validate ; la garde refuse un raster fin ; tests de 021

## Terrain

- **Échantillon que Pascal vérifiera :** `make prepare biomes ZONE=zone_fictive`, puis `rapport_biomes.html` ouvert dans un navigateur.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.
