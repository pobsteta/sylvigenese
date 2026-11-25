# Mission 026 — tests d'acceptation de M2a

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests d'acceptation de M2a dans tests/m2/ à partir de la spec et des référentiels, sans lire le code : ajustement et rapport par essence, validation croisée par blocs, contrats des params, garde IFN sur le chemin de la station, colonnes de station remplies, pour que le jalon ne s'auto-évalue pas.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | |
| A-t-il les moyens ? | oui : jeu fictif, contrats, référentiel 022 | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `testeur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** lire R/ ; modifier tests/m1/ sauf pour un test devenu faux par une décision inscrite au journal.

## Harnais

- **Peut (périmètre) :** `tests/m2/` ; le branchement de `tests/m2` dans `tools/ci/run_tests.sh` est fait par l'orchestrateur.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** sauter un test ; affaiblir une assertion pour la faire passer.
- **Sources autorisées :** docs/spec.md §6 et §11, docs/BRIEF.md §6, docs/referentiels/ifn-dynamique.md, contracts/, les fiches 023 à 025.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- aucune.

## Dépend de / rouge attendu jusqu'à

- dépend de 022 ; rouge attendu jusqu'aux rendus de 023, 024 et 025.

## Tests

- chaque critère du jalon M2a a au moins un test discriminant (une zone variante qui le ferait échouer).

## Terrain

- **Échantillon que Pascal vérifiera :** la liste des tests et de ce qu'ils prouvent, en français.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

tests/m2 tout vert après 025, et rouge si l'on casse une règle (essai sur une variante).
