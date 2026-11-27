# Mission 078 — post refuse un massif simulé en cohortes

## Mission

**En une phrase :** Faire refuser par `post` (code 2, message nommé) un massif dont `sim/run.json` dit `recruitment: cohorts`, tant que le tarif n'est pas validé sur ces trajectoires (kanban M5b, relecture de M5a), et le dire dans la fiche de la vue.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `python/sylvigenese/post.py` et ses tests, `tests/post/`, `python/sylvigenese/assets.py` et `assets_lib/` (note des fiches seulement), leurs tests.
- **Ne doit pas :** changer un résultat de post en `ifn_direct` ; ajouter une option qui contourne le refus sans le dire.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- Massif en `cohorts` refusé, code 2 ; `ifn_direct` inchangé (sorties identiques) ; note des fiches testée.
