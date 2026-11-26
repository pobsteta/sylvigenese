# Mission 052 — tests d'acceptation de post

## Mission

**En une phrase :** Écrire `tests/post/` sans lire le code de `post` ni d'`import_tarif`, à partir du plan, des contrats de 051 et des décisions Q1 à Q6 du 26/11/2026, pour que le calcul du volume et du carbone ne se juge pas lui-même (plan `docs/plans/post-volume-carbone.md`, mission C).

## L'Homme

- **Agent :** `testeur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `tests/post/` (nouveaux fichiers, aides), la section `post` de `tools/ci/run_tests.sh` et son job dans `.github/workflows/ci.yml`.
- **Ne doit pas :** lire `python/sylvigenese/post.py`, `import_tarif.py`, `assets_lib/` ; sauter un test ; affaiblir un test existant.
- **Câblé :** aucune commande git qui écrit ; peu d'années simulées (durée de la CI).

## Tests

- Recalcul indépendant, sur le `tarif.parquet` synthétique, du volume aérien total, de la biomasse et du carbone aérien d'arbres connus ; hors domaine compté, jamais extrapolé (Q5) ; summary, summary_zone et post.json conformes ; fiche v3 avec « volume partiel » ; refus en code 2. Rouges jusqu'à 053.
