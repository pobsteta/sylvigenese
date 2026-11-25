# Mission 033 — contrats-m3

## Mission

**En une phrase (quoi, et pourquoi) :** Amender les contrats de M3a : run.json (sorties de domaine, plafonds, bords, cellules mêlées), sim.cells avec la colonne de semis facultative jusqu'à M5, nouveau contrat de la table de signalements de la simulation, paramètres de courbe de Korf et d'allométries hcb/cw dans dynamics_params ou allometry.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `contracts/` (schémas, catalogue, README) et `contracts/tests/`
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- aucune ; précède B, C, D (lecture des contrats)

## Tests

- un cas conforme et un fautif par contrat amendé ou nouveau

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
