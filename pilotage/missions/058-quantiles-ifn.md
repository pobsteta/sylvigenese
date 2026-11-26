# Mission 058 — quantiles IFN de surface terrière et de tiges/ha

## Mission

**En une phrase :** Exécuter et tester le script `tools/referentiels/ifn_g_tiges.py` de l'acquéreur sur l'export DataIFN 2021-2025, pour donner au critère M3b des quantiles 5 à 95 % sourcés de G et de tiges/ha (France, GRECO, SER), sans fixer les bornes, qui reviennent à Pascal (demande de Pascal du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** le script et son test, `docs/referentiels/ifn-g-tiges.{md,csv}`, la section `contrats` de `tools/ci/run_tests.sh` ; données brutes sous `data/ifn/` (hors dépôt).
- **Ne doit pas :** versionner les données ; inventer une valeur ; croiser une placette IFN avec un raster fin.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Auto-test du script ; pytest sur un jeu construit à la main ; rejeu identique du CSV.
