# Mission 037 — simulate-pas

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire le cœur du pas annuel de simulate (concurrence, accroissement, hauteur avec ancre MNH et Korf, mortalité, recrutement en arrondi aléatoire, contrôles), testé sur des états construits en mémoire, en respectant l'identité entre fils.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui, après 035 | |

**Temps de la main :** prendre (justesse de la simulation). **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus

## Harnais

- **Peut (périmètre) :** `simulate/src/{concurrence,accroissement,hauteur,mortalite,recrutement,pas,controles}.rs`, `simulate/tests/pas.rs`
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- dépend de 035 (et des paramètres de 034 pour les essais sur le jeu fictif)

## Tests

- cargo test : disque de 15 m (14,9 m compte, 15,1 m non), pas exact de Chapman-Richards et de Korf, dH ≥ 0, arrondi aléatoire, code 3

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
