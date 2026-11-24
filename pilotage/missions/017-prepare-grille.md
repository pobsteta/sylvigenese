# Mission 017 — prepare-grille

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire dans `prepare` (R) la construction de la grille de 25 m et des rasters alignés : `grid.tif`, `dtm.tif`, `forest_mask.tif`, `ser.tif` avec sa table (SER sous-jacente des alluvions, la voisine de plus longue frontière, signalée), `station_gradients.tif`, `station_type.tif` et sa table, `site_potential.tif` et sa table, `h0.tif` (agrégation du MNH à 50 cm) et `chm_date.tif`, pour que les modules suivants lisent une grille unique (spec §2, §3, §5, §7).

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

- **Peut (périmètre) :** `R/prepare_grid.R`, `R/modules.R` (partie prepare), `_targets.R`, `R/tests/testthat/test-prepare-grid.R`, `contracts/tables/inputs/ser.schema.json` et ses tests dans `contracts/tests/` (l'entrée suit la forme brute de l'IGN : L1 à L5 permis en entrée), `tools/fixtures/` et `tests/fixtures/zone_fictive/` (ser.gpkg remis à la forme brute de l'IGN).
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** réécrire le validateur au-delà du contrat inputs.ser ; recalculer le MNH ; rééchantillonner le MNH à 50 cm autrement que par agrégation ; faire un commit git.
- **Sources autorisées :** docs/spec.md §2-§9, contracts/README.md, contracts/geotiff_profile.json, docs/referentiels/entrees-externes.md, tests de la mission 021.

## Valeur provisoire

- H0 = percentile 95 du MNH sur la cellule : provisoire (spec §5), à remplacer par l'estimateur h_dom de typopeuplement

## Dépend de / rouge attendu jusqu'à

- 021 (tests écrits en parallèle) ; ordre de fusion : 021, puis 017

## Tests

- les sorties passent `contracts/validate` (variante grille avec --grid) ; tests testthat ; tests de 021 sur la grille

## Terrain

- **Échantillon que Pascal vérifiera :** `make prepare biomes ZONE=zone_fictive`, puis `rapport_biomes.html` ouvert dans un navigateur.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.
