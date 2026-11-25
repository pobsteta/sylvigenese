# Mission 023 — contrats et jeu fictif IFN pour la dynamique

## Mission

**En une phrase (quoi, et pourquoi) :** Étendre les contrats d'entrée IFN (inputs.ifn_*) et de sortie de prepare (prepare.ifn_*), le générateur du jeu fictif et R/prepare_ifn.R aux colonnes établies par 022 (accroissement radial à 5 ans, état à la revisite, arbres recrutés), avec des valeurs synthétiques marquées provisoires, pour que dynamics ait de quoi s'ajuster sur le jeu fictif (M2a).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui, une fois 022 rendu | |
| A-t-il les moyens ? | oui : validateur, générateur, tests existants | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** les variables de station aux placettes (024) ; le module dynamics (025).

## Harnais

- **Peut (périmètre) :** `contracts/tables/inputs/ifn_*`, `contracts/tables/prepare/ifn_*`, leurs cas dans `contracts/tests/` et `tests/contracts/`, `contracts/catalog.yml` (entrées IFN), la partie IFN de `tools/fixtures/make_zone_fictive.py` et `tests/fixtures/zone_fictive/inputs/ifn/`, `R/prepare_ifn.R`, `R/tests/testthat/test-prepare-ifn.R`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** présenter une valeur synthétique comme écologique ; toucher à la garde (R/ifn_guard.R).
- **Sources autorisées :** docs/referentiels/ifn-dynamique.md (022), docs/referentiels/ifn-placettes.md, docs/spec.md §3 et §6, docs/adr/0002-contrats-et-formats.md.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- les accroissements, morts et recrues du jeu fictif : synthétiques, provisoires, sans gel (remplacés par l'IFN réel en M2b).

## Dépend de / rouge attendu jusqu'à

- dépend de 022 ; précède 024 et 025. Rouge attendu : les tests de 026 qui portent sur dynamics, jusqu'à 025.

## Tests

- contrats : un fichier conforme et un fautif par nouvelle colonne ; jeu fictif régénéré à l'identique ; `make prepare` et `make validate` verts.

## Terrain

- **Échantillon que Pascal vérifiera :** `ifn/trees.parquet` du jeu fictif : accroissements et états à la revisite lisibles, marqués synthétiques.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

`make prepare ZONE=zone_fictive` produit des tables IFN qui portent accroissement, état à 5 ans et recrues, conformes aux contrats.
