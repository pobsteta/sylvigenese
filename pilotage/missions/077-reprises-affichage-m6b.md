# Mission 077 — reprises d'affichage de la vue massif (préparation de M6b)

## Mission

**En une phrase :** Avant l'essai sur le PC de Pascal, sortir des scripts de la vue les dernières constantes d'affichage vers le bloc `viewer` de `config.yml`, dessiner les semis génériques à (r, h, r), dire dans les notes de l'index une essence à semis sans modèle jeune, et faire produire par `bench/m6/mesurer.py` le scénario 2022 écrit à la main (kanban, cycle 9).

## L'Homme

- **Agent :** `afficheur` — **Temps de la main :** donner.

## Harnais

- **Peut :** `viewer-massif/scripts/`, `viewer-massif/tests/` (ajouts), `config.yml` (bloc `viewer`), `contracts/json/config.schema.json` et ses tests, `python/sylvigenese/assets_lib/massif.py` (notes seulement) et ses tests, `bench/m6/mesurer.py`.
- **Ne doit pas :** mettre une valeur écologique dans un script ou dans `config.yml` ; changer un décompte ; mesurer des images par seconde.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD` (Godot 4.6.3 headless, GUT, selftest).

## Tests

- Plus aucune constante d'affichage en dur dans les scripts (test qui le vérifie) ; semis générique à (r, h, r) en GUT ; note de l'index testée ; `mesurer.py` écrit la ligne 2022 de `m6_selftest.csv`.
