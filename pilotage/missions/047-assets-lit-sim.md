# Mission 047 — assets lit sim/ et écrit une tuile et une fiche par année retenue

## Mission

**En une phrase :** Faire lire `sim/` par `assets`, qui écrit pour chaque année retenue une tuile 3D des seuls arbres vivants, les fiches d'évolution, `tiles/index.json` et la carte de surface terrière `web/rasters/g_<année>.tif`, pour donner à voir le futur simulé (plan §2 mission C ; contrats de 044 ; tests de 045).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `python/sylvigenese/assets.py`, `assets_lib/` (nouveau `sim_state.py`), `python/tests/test_assets*.py`, cible `assets` du Makefile.
- **Ne doit pas :** importer `simulate` ou `post` ; interpoler entre années ; inventer une valeur absente de `sim/` ; écrire un `.glb` comme contenu de tuile.
- **Câblé :** aucune commande git qui écrit ; écriture atomique ; mode état initial gardé quand `sim/` est absent.

## Tests

- Tests unitaires ; l'arbre (700 012,5 ; 6 500 987,5) tombe dans la bonne tuile et la bonne cellule ; rejeu identique à l'octet près ; tests de 045 côté assets verts.
