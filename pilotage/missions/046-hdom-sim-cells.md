# Mission 046 — simulate écrit la hauteur dominante de chaque cellule et de chaque année

## Mission

**En une phrase :** Ajouter `h_dom_m` à `sim/cells` pour chaque cellule et chaque année (décision de Pascal, Q1 du 25/11/2026), pour que la fiche montre la courbe de H_dom à côté du plafond de station (plan §2 mission F ; contrat de 044).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src/sorties.rs` (et le module qui calcule H_dom s'il faut l'exposer), les tests de `simulate`.
- **Ne doit pas :** changer un résultat existant de `sim/trees` ; macros maison ou génériques avancés (ADR 0001) ; toucher `tests/m3/reference/nominal.json` sans le dire.
- **Câblé :** aucune commande git qui écrit.

## Tests

- `cargo test --locked` vert, identité 1 à N fils gardée ; une cellule de H_dom connue écrite à l'identique ; `make validate` vert.
