# Mission 032 — identifiants Python et TypeScript en anglais

## Mission

**En une phrase (quoi, et pourquoi) :** Renommer en anglais les identifiants (fonctions, classes, variables, modules) du code Python (`python/`) et TypeScript (`viewer-web/`), sans changer aucun comportement ni aucun message utilisateur (qui restent en français), pour appliquer la règle de CLAUDE.md maintenue par Pascal le 25/11/2026.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | |
| A-t-il les moyens ? | oui : suites de tests existantes (pytest python, npm test, tests/m4) | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** le R (déjà en anglais), les tests d'acceptation (tests/m1, m2, m4 : leurs noms de tests en français sont des phrases de test, admises), les contrats et les noms de colonnes.

## Harnais

- **Peut (périmètre) :** `python/` (code et tests unitaires), `viewer-web/src`, `viewer-web/test`, `viewer-web/scripts`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit.
- **Ne doit pas :** changer un comportement, un message utilisateur, un nom de fichier de sortie, une interface lue par les tests d'acceptation (`window.sylvigenese` et ses clés, `data-testid`, cibles make, options de ligne de commande).
- **Sources autorisées :** CLAUDE.md (Langue).

## Valeur provisoire

- aucune.

## Dépend de / rouge attendu jusqu'à

- aucune ; tourne en parallèle de 031 (périmètres disjoints).

## Tests

- pytest python, contracts/tests, npm run typecheck, npm test, tests/m4 : verts avant et après ; une recherche montre qu'aucun identifiant en français ne reste dans le périmètre (liste des exceptions justifiées).

## Terrain

- **Échantillon que Pascal vérifiera :** aucun changement visible ; le relecteur vérifie la règle.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
