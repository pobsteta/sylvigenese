# Mission 053 — import_tarif écrit params/tarif, post calcule volume et carbone, assets écrit la fiche v3

## Mission

**En une phrase :** `import_tarif` lit `parametres_tarif_v5.csv` de tarif-nemeton (commit cité) et écrit `params/tarif.parquet` au contrat de 051 ; `post` calcule par arbre vivant le volume aérien total, la biomasse, le carbone aérien et, à part, le carbone des racines (provisoire), puis écrit `sim/summary`, `sim/summary_zone`, `sim/post.json` et `rapport_post.html` ; `assets` écrit la fiche v3 quand le summary existe (plan mission D ; décisions Q1 à Q6).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `python/sylvigenese/import_tarif.py`, `post.py`, `assets_lib/cell_sheets.py` (fiche v3), leurs tests sous `python/tests`, la cible `post` du Makefile.
- **Ne doit pas :** extrapoler hors domaine ni emprunter un tarif (Q5) ; inventer une constante ; lire le code de tarif-nemeton (seulement ses CSV) ; modifier `tests/post`.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Tests de 052 verts ; `make all` puis `make validate` verts sur le jeu fictif ; rejeu identique à l'octet près.
