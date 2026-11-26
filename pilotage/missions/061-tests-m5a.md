# Mission 061 — Tests d'acceptation de M5a

## Mission

**En une phrase :** Tests d'acceptation de M5a (`tests/m5/`), écrits sans lire le code du moteur, et générateur de SER fictive en aide de test, pour que M5a ne se juge pas lui-même. Le générateur produit, à toute taille N, des sorties de `prepare` synthétiques conformes aux contrats, avec `zone.yml` à `fictive: true` et deux codes de SER. Détail ci-dessous. (plan `docs/plans/m5a.md`, mission C ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `testeur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `tests/m5/` (tests, aide, générateur en ligne de commande)
- **Ne doit pas :** lire `simulate/src` ; sauter un test ; écrire une valeur présentée comme écologique ; toucher `tests/m3/reference/`
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- chaque critère a un test discriminant ; rouge attendu jusqu'à D et E ; générateur rejoué à l'octet près à graine égale
