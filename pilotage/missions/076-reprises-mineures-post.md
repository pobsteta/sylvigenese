# Mission 076 — reprises mineures de la relecture de post

## Mission

**En une phrase :** Solder les reprises mineures de la seconde relecture de la PR n° 10 (post, journal du 26/11/2026) : facteurs 0,9, 1,1 et 2 m du domaine lus et non écrits en dur au rapport, chemin local retiré de `docs/referentiels/ifn-g-tiges.csv`, docstring de `exclude_incomplete`, rejeu du CSV des quantiles prouvé.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `python/sylvigenese/post.py`, `python/sylvigenese/import_tarif.py`, leurs tests, `tests/post/`, le script des quantiles IFN et `docs/referentiels/ifn-g-tiges.*`.
- **Ne doit pas :** changer un résultat de post ; inventer une valeur ; écrire une donnée IFN dans le dépôt.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- Un test prouve que les facteurs du rapport viennent de la source lue ; le CSV des quantiles se rejoue à l'identique (ou l'écart est dit) ; section post verte, aucun sauté.
