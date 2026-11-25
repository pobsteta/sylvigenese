# Mission 038 — simulate-sorties

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les sorties et l'assemblage de simulate (Parquet de sim/trees et sim/cells, run.json, table de signalements, codes 0 à 4, appel du validateur), le test d'identité 1 à 7 fils, la non-régression figée, et la cible make simulate.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui, après 036, 037, 033 | |

**Temps de la main :** prendre. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus

## Harnais

- **Peut (périmètre) :** `simulate/src/{sorties,lib,main}.rs`, `simulate/tests/{identite,non_regression}.rs`, `simulate/tests/reference/`, règle `simulate` du Makefile
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- dépend de 033, 036, 037

## Tests

- cargo test ; make simulate ZONE=zone_fictive puis make validate ; durée relevée

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
