# Mission 059 — Référentiel de la régénération

## Mission

**En une phrase :** Référentiel de la régénération : relever, essence par essence de `contracts/species.csv`, ce que la littérature publie, avec sa source, pour que le contrat des paramètres ne contienne que des grandeurs qui existent. Grandeurs visées : noyau ou distance de dispersion, âge ou diamètre de maturité, fécondité, tolérance à l'ombre (Niinemets et Valladares 2006), L d'Ellenberg (Tichý 2023), croissance en hauteur et survie des semis sous couvert. Sources : paramètres d'espèces de LANDIS-II et de TreeMig, RReShar (Capsis). (plan `docs/plans/m5a.md`, mission A ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `acquereur` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `docs/referentiels/regeneration.{md,csv}`
- **Ne doit pas :** écrire une valeur sans page ni ligne ; combler un manque ; lire un dépôt privé
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- chaque ligne du CSV porte une source vérifiable ou `absent` ; recommandation finale
