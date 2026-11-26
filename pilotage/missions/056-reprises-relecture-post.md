# Mission 056 — reprises de la relecture de post (code)

## Mission

**En une phrase :** Reprendre les points de la première relecture de la PR n° 10 côté code : domaine du tarif écrit au rapport de post (décision de Pascal du 26/11/2026), sources justes sur le jeu fictif, descriptions périmées, petits résineux comptés au lieu de refuser le run, profil NEMETON et E(D) tenus par des tests discriminants, vue qui signale au lieu d'ajouter, « < 0,1 » pour une valeur positive sous la précision (journal du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner. Fiche écrite après coup par l'orchestrateur (relecture 2), la consigne faisait foi.

## Harnais

- **Peut :** `python/sylvigenese/post.py`, `assets_lib/cell_sheets.py`, leurs tests (`python/tests/test_post.py`, `test_cell_sheets_v3.py`), les descriptions de `contracts/json/post.schema.json` et `contracts/tables/params/tarif.schema.json`, la docstring de tête de `tests/post/helpers_post.py`, `viewer-web/src/volume.ts` et son test.
- **Ne doit pas :** modifier un test ou une assertion de `tests/post` ou `tests/m4` ; inventer une valeur ; mettre une valeur réelle de tarif-nemeton dans un test.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Mutations du profil NEMETON (`sx`, `x0`, `k0/k1`, `lam`) et de E(D) détectées ; `run_tests.sh post`, python, contrats, node verts.
