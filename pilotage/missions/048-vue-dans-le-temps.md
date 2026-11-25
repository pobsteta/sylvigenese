# Mission 048 — la vue iTowns fait défiler les années

## Mission

**En une phrase :** Donner à la vue un curseur d'années (celles de `tiles/index.json`), la fiche de l'année choisie avec le tableau de son évolution (H_dom à côté du plafond), et la carte de surface terrière au sol à échelle fixe, pour que Pascal suive une cellule dans le temps (spec §1 point 4 ; plan §2 mission D ; décisions Q1 et Q3).

## L'Homme

- **Agent :** `afficheur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `viewer-web/` (src, test, configuration).
- **Ne doit pas :** dépendre du réseau ; afficher un chiffre sans « provisoire » ou sans « non validée écologiquement » pour la trajectoire ; garder en mémoire plus de deux années de tuiles.
- **Câblé :** aucune commande git qui écrit.

## Tests

- `node --test` (choix de l'année, mise en forme de l'évolution) ; sonde de 045 verte ; captures à deviceScaleFactor 2 en t0 et en dernière année.
