# Mission 057 — tests du sapin exact et de la fiche v3 dans le navigateur

## Mission

**En une phrase :** Ajouter à `tests/post` le recalcul exact d'un résineux (le sapin du point connu, formule synthétique du contrat) et la vérification de la fiche v3 dans Chromium, que la première relecture de la PR n° 10 a trouvés manquants, sans lire le code de post ni de la vue.

## L'Homme

- **Agent :** `testeur` — **Modèle :** opus — **Temps de la main :** donner. Fiche écrite après coup par l'orchestrateur (relecture 2), la consigne faisait foi.

## Harnais

- **Peut :** `tests/post/` (nouveaux fichiers, fonctions ajoutées en fin de `helpers_post.py`, sonde Playwright), le job `post` de `.github/workflows/ci.yml` (Node, Chromium) et le commentaire de sa section dans `tools/ci/run_tests.sh`.
- **Ne doit pas :** lire `python/sylvigenese/post.py`, `assets_lib/`, `viewer-web/src` ; sauter ou affaiblir un test ; toucher la docstring de tête de `helpers_post.py`.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Neuf formes fausses distinguées par l'oracle ; `synth_p2/3` simulé et vue faussée détectés ; règle de lecture adaptée à « < 0,1 » (décision du 26/11/2026) et discriminante ; `run_tests.sh post` vert.
