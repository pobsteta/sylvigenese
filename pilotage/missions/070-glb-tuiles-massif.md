# Mission 070 — glb tuiles massif (M6a, mission D du plan)

## Mission

**En une phrase :** Du segment au `.glb`, aux tuiles et au bloc massif : lecture des exemplaires (Parquet), conversion z-up → y-up (T6), maillage, trois niveaux de détail, quatre stades, `.glb` identique à l'octet près à chaque exécution ; tuiles iTowns bâties des mêmes sommets ; `massif/index.json` et `massif/<année>/<bloc>.json` v2 lus dans `sim/` (ou `trees_init/`) ; fonction unique du stade d'un arbre ; script documenté `tools/rejouer_exemplaires_reels` qui rejoue la construction des `.glb` sur l'export réel (B2).

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne D), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `dev` (Python) — **Temps de la main :** donner.

## Harnais

- **Peut :** `python/sylvigenese/assets.py`, `python/sylvigenese/assets_lib/` (nouveaux `exemplars.py`, `lod.py`, `glb.py`, `stages.py`, `massif.py` ; `models.py`, `tiles.py`, `sim_state.py`, `initial_state.py`), `python/tests/`, `tools/rejouer_exemplaires_reels*`
- **Ne doit pas :** importer du code de tarif-nemeton ; deviner un modèle pour une essence sans exemplaire ; casser l'identité à l'octet près ; changer `tiles/` des années ou le décompte des instances (14 080) ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit dans sylvigenese ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- tests unitaires (§6) ; `tests/m4` rouvert par C vert ; `contracts/validate` vert sur `assets/trees/*.glb` et `massif/`
