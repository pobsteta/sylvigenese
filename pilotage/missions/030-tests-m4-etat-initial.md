# Mission 030 — tests-m4-etat-initial

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests d'acceptation de la tranche de M4a sur l'état initial (tests/m4/), sans lire le code : tuile 3D conforme et complète (une instance par arbre de trees_init, à sa position), fiches de cellule conformes et cohérentes avec les sorties de prepare et biomes, COG conformes, mention « provisoire », vue qui charge et compte ses instances, pour que la tranche ne s'auto-évalue pas.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | |
| A-t-il les moyens ? | oui : jeu fictif, contrats, Playwright préinstallé | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `testeur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** lire python/ ou viewer-web/src.

## Harnais

- **Peut (périmètre) :** `tests/m4/` ; le branchement dans tools/ci/run_tests.sh est fait par l'orchestrateur.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** sauter un test ; affaiblir une assertion.
- **Sources autorisées :** docs/spec.md §1, §2, §9, §10, §11 ; contracts/ ; fiches 028 et 029 ; docs/referentiels/itowns-instancing.md.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- aucune.

## Dépend de / rouge attendu jusqu'à

- rouge attendu jusqu'aux rendus de 028 et 029.

## Tests

- chaque critère a au moins un test discriminant (zone variante).

## Terrain

- **Échantillon que Pascal vérifiera :** la liste des tests et de ce qu'ils prouvent, en français.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

tests/m4 tout vert après 029.
