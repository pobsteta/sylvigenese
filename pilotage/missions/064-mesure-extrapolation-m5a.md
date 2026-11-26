# Mission 064 — Mesure et extrapolation

## Mission

**En une phrase :** Mesure et extrapolation : lancer `bench/m5` à N = 1 000, 2 000 et 4 000, avec T = 1 et T = 4, sur Y = 10 ans, extrapolés à 100 ans comme au banc §9. Il compare l'estimation de mémoire à la mémoire résidente, extrapole à C20 (48 millions de cellules, N équivalent ≈ 6 930) et au-delà, et dit le verdict face à la cible de 5 jours et 31 Go (selon Q5). (plan `docs/plans/m5a.md`, mission F ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `analyste` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `bench/results/M5.md`, `bench/results/m5_*.csv`, `bench/results/LANCER_CHEZ_SOI.md` (section M5)
- **Ne doit pas :** modifier le code ; présenter une extrapolation comme une mesure ; transposer un temps du conteneur au PC de Pascal sans le dire
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- chaque chiffre renvoie à une ligne de CSV ; écart estimation / mémoire résidente par taille ; rejouable par un seul script
