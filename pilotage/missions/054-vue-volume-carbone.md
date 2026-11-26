# Mission 054 — la vue montre le volume et le carbone

## Mission

**En une phrase :** La fiche de cellule de la vue iTowns lit la fiche v3 et montre, année par année, le volume aérien total et le carbone aérien (racines à part, provisoire), « volume partiel » avec la part de surface terrière non calculée, et « sol et bois mort non comptés » (décisions Q3 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `afficheur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `viewer-web/` (src, test).
- **Ne doit pas :** recalculer un chiffre ; afficher un chiffre sans « provisoire » ; casser la vue v1 et v2.
- **Câblé :** aucune commande git qui écrit.

## Tests

- `node --test` ; tests de vue de 052 verts ; captures à deviceScaleFactor 2.
