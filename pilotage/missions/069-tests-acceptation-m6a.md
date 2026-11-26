# Mission 069 — tests acceptation m6a (M6a, mission C du plan)

## Mission

**En une phrase :** Tests d'acceptation de M6a, écrits sans lire le code de D et de F : côté Python (`tests/m6/`, avec un analyseur de `.glb` indépendant) et côté Godot (`viewer-massif/tests/`, GUT). Le testeur reprend aussi les tests de `tests/m4` qui épinglent les modèles génériques (voir risque « tests de M4 »). Il fournit la fixture d'exemplaires (§5, mission D).

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne C), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `testeur` — **Temps de la main :** donner.

## Harnais

- **Peut :** `tests/m6/`, `viewer-massif/tests/`, `tests/m4/` (les seuls tests dépendant du modèle générique), `tests/fixtures/` (exemplaires synthétiques)
- **Ne doit pas :** lire `python/sylvigenese/assets_lib` modifié par D ni les scripts de F ; sauter un test ; écrire une valeur présentée comme écologique ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit dans sylvigenese ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- voir §6 ; rouge attendu jusqu'à D, E et F
