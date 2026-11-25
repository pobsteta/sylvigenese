# Mission 045 — tests d'acceptation de la suite de M4a

## Mission

**En une phrase :** Écrire dans `tests/m4/` les tests d'acceptation de la vue dans le temps, sans lire le code qui l'implémente, pour que la tranche ne se juge pas elle-même (plan §2 mission B ; contrats de 044 ; décisions Q1 à Q3).

## L'Homme

- **Agent :** `testeur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `tests/m4/` (nouveaux fichiers, aides, sonde), `tests/m3/` pour un test de `h_dom_m`.
- **Ne doit pas :** lire `python/sylvigenese/`, `viewer-web/src`, `simulate/src` ; sauter un test ; affaiblir une assertion de 030.
- **Câblé :** aucune commande git qui écrit ; garder en tête la durée de la CI (mission 043) : simuler le moins d'années possible.

## Tests

- Chaque critère du plan §2 mission B a un test discriminant ; rouge attendu jusqu'à 046, 047 et 048.
