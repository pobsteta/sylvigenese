# Mission 035 — simulate-fondations

## Mission

**En une phrase (quoi, et pourquoi) :** Poser les fondations Rust de simulate : Cargo.toml et Cargo.lock (toutes les crates figées), modules erreurs, alea (générateur à compteur chaîné, table de référence publiée), parametres (relecture des splines aux nœuds et recherche essence → groupe → toutes_essences), memoire (estimation, MemAvailable), etat (état en colonnes), avec leurs tests unitaires.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui : Rust 1.97, crates.io joignable | |

**Temps de la main :** prendre (fondations qui engagent la suite). **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus

## Harnais

- **Peut (périmètre) :** `simulate/Cargo.toml`, `simulate/Cargo.lock`, `simulate/src/{erreurs,alea,parametres,memoire,etat}.rs`, leurs tests sous `simulate/tests/`
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- aucune ; précède 036, 037, 038

## Tests

- cargo test : table de u, spline contre valeurs de R à 1e-10, recherche des paramètres, estimation mémoire, licences des crates

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
