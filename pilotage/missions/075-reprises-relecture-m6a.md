# Mission 075 — reprises de la relecture de la PR n° 12 (M6a)

## Mission

**En une phrase :** Reprendre les points « à reprendre » de la relecture de la PR n° 12 (journal du 26/11/2026) : repli générique par stade lisible par la vue, échelle explicite des génériques dans Godot, glTF-Validator de Khronos dans le job m6, commande de la fiche utilisable telle quelle, ADR 0007 à jour, et les mineurs.

## L'Homme

- **Agents :** `dev` A (python, contrats, vue Godot : points 1 et 2, bandeau), `dev` B (CI et commande de la fiche : points 3 et commande), `archiviste` (ADR 0007, plan, M6.md, CREDITS) — **Temps de la main :** donner.

## Harnais

- **Peut :** A : `python/sylvigenese/assets_lib/`, `python/tests/`, `contracts/`, `viewer-massif/scripts/`, `viewer-massif/tests/` (ajouts) ; B : `.github/workflows/ci.yml`, `tools/ci/`, `tools/viewer-massif`, `viewer-web/src/`, `viewer-web/test/`, `tests/m4/` et `tests/m6/` (forme de la commande seulement), `README.md` ; archiviste : `docs/adr/0007-*.md`, `docs/plans/m6a.md`, `bench/results/M6.md`, `viewer-massif/CREDITS.md`.
- **Ne doit pas :** inventer une valeur ; ajouter une valeur par défaut silencieuse ; filtrer une erreur ; sauter un test.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- Cas « essence avec un stade sans exemplaire » testé en Python, en contrat et en GUT, et autotest sur une zone qui le contient ; générique de la vue Godot à (r, h, r) comme iTowns ; glTF-Validator vert sur les `.glb` du jeu fictif en CI ; commande de la fiche lancée telle quelle depuis la racine.
