# Mission 039 — tests-m3

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests d'acceptation de M3a (tests/m3/) depuis la spec, le plan et les contrats seuls, sans lire le code : 100 ans sur une copie du jeu fictif, validateur, identité entre fils, recalcul Python indépendant d'arbres choisis, codes 2, 3 et 4.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `testeur` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `tests/m3/` ; le branchement dans tools/ci/run_tests.sh est fait par l'orchestrateur
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- rouge attendu jusqu'à 038

## Tests

- chaque critère de M3a (spec §11) a un test discriminant

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
