# Mission 043 — tenir la durée de la suite de tests sous le plafond de la CI

## Mission

**En une phrase (quoi, et pourquoi) :** Faire tenir la suite de tests largement sous le plafond de 45 min de la CI, sans retirer ni affaiblir aucun test, parce qu'elle dure déjà 33 à 44 min (plan de la suite de M4a, §6, mission E) et que la suite de M4a va l'allonger.

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `tools/ci/run_tests.sh`, `.github/workflows/ci.yml`, cibles `test*` du `Makefile`. Pistes, dans l'ordre : écrire la durée de chaque section dans le journal de la CI ; découper la CI en tâches parallèles ; paralléliser ce qui est indépendant dans une même tâche.
- **Ne doit pas :** modifier une assertion, le nombre d'années simulées d'un test, une tolérance, ou sauter un test ; relever le plafond de 45 min ; changer le nom « CI » du workflow (lu par `release.yml`) ; casser `.claude/test-command`.
- **Câblé :** aucune commande git qui écrit.

## Tests

- La CI relève elle-même la durée de chaque section.
- Même liste de tests passés qu'avant : comparaison des identifiants pytest et des comptes testthat, cargo et node.
- La release suit toujours la CI sur `main` : `release.yml` attend la conclusion du workflow « CI », et un découpage en plusieurs tâches ne doit pas la déclencher trop tôt ni l'empêcher.
