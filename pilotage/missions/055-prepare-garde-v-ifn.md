# Mission 055 — prepare garde le volume V de l'IFN

## Mission

**En une phrase :** Faire garder par `prepare` la colonne `V` (volume bois fort tige) des arbres IFN dans `ifn_trees`, avec sa définition citée, pour que le critère b de `post` (écart au V de l'IFN sur la SER pilote, décision de Pascal Q6 du 26/11/2026) soit possible sans croiser l'IFN avec aucun raster fin (plan §2 mission F).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `R/prepare_*.R` qui écrit `ifn_trees`, son test testthat, le contrat `ifn_trees` (colonne facultative), l'extrait IFN fictif s'il doit porter `V`.
- **Ne doit pas :** affaiblir la garde `assert_no_fine_extract_on_ifn()` ; croiser une placette IFN avec un raster fin ; inventer un V.
- **Câblé :** aucune commande git qui écrit.

## Tests

- testthat : V lu et gardé, unité dite ; un V absent reste NA et est signalé ; garde IFN intacte ; `make validate` vert.
