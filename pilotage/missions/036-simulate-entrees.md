# Mission 036 — simulate-entrees

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les entrées de simulate : lecture de trees_init, params, rasters de prepare et config.yml, contrôle d'alignement, affectation des arbres aux cellules (code 2 hors grille), avec le test du point du terrain.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui, après 035 | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `simulate/src/{entrees,grille,config}.rs`, `simulate/tests/entrees.rs`
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- dépend de 035

## Tests

- cargo test ; un arbre en (700 012,5 ; 6 500 987,5) tombe dans cell_id 0

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
