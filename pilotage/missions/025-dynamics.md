# Mission 025 — module dynamics

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire le module `dynamics` (R, mgcv) qui ajuste par essence ou groupe d'essences l'accroissement radial annualisé, la mortalité à 5 ans et le recrutement à 7,5 cm sur ifn/, les valide par validation croisée spatiale par blocs contre un modèle nul, écrit params/{growth,mortality,recruitment,height_curve}.parquet aux contrats et rapport_dynamics.html (biais, erreur, domaine de validité par essence, limites connues), pour remplir le critère M2a (spec §11).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | non en partie : formes de modèle à proposer ; l'agent rend d'abord un plan court (formes, variables, blocs, modèle nul) que l'orchestrateur valide | |
| A-t-il les moyens ? | oui : mgcv installé, jeu fictif de 023 et 024 | |

**Temps de la main :** prendre (modèle statistique qui engage la justesse de la simulation). **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** opus
- **Ce qui ne lui est pas demandé :** la simulation (M3) ; les cohortes de régénération (M5).

## Harnais

- **Peut (périmètre) :** `R/dynamics.R`, `R/tests/testthat/test-dynamics.R`, `contracts/tables/params/` (contrats des quatre tables) et leurs cas, `run_dynamics` dans `R/modules.R`, cible `dynamics` du Makefile et de `_targets.R`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** appeler le code d'un autre module (seulement R/commun.R, R/config.R, R/validateur.R) ; présenter un coefficient du jeu fictif comme écologique ; corriger silencieusement une donnée.
- **Sources autorisées :** docs/BRIEF.md §6, docs/spec.md §6 et §11, docs/referentiels/ifn-dynamique.md, docs/adr/0001 et 0002, R/commun.R.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- la courbe de hauteur (forme par essence) : provisoire tant qu'elle n'est pas sourcée (BRIEF §6, hauteur, point 1) ; taille des blocs de validation croisée : provisoire, justifiée dans le rapport.

## Dépend de / rouge attendu jusqu'à

- dépend de 023 et 024. Les tests de 026 sur dynamics sont rouges jusqu'à son rendu.

## Tests

- ajustement reproductible (graine) ; validation croisée par blocs : RMSE ou log-vraisemblance comparée au modèle nul et écrite au rapport ; contrats des sorties ; tests de 026.

## Terrain

- **Échantillon que Pascal vérifiera :** `rapport_dynamics.html` du jeu fictif : un tableau par essence (n, biais, erreur, domaine), et la liste des limites connues.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

`make dynamics ZONE=zone_fictive` écrit les quatre tables conformes et un rapport par essence, et la CI le rejoue.
