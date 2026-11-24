# Banc d'essai : implémentation R (variantes `r-base` et `r-rcpp`)

Exploration jetable (mission 003, ADR 0001 point B3). Implémente `bench/SPEC.md` (y compris
sa section 10, précisions P1 à P9). Aucune valeur n'est écologique.

## Versions utilisées

R 4.3.3, Rcpp 1.0.12, RcppParallel 5.1.7, testthat 3.2.1, jsonlite (tests), g++ 13.3.0 (Ubuntu 24.04).
Tout vient d'apt : `apt-get install -y r-base-core r-cran-rcpp r-cran-rcppparallel r-cran-testthat r-cran-jsonlite g++`.
(`time` d'apt a servi à mesurer la mémoire : `apt-get install -y time`.)

## Lancement

```
Rscript bench/r/sim.R --variant r-base --n 500 --years 100 --seed 42 --threads 1 --out /tmp/x
Rscript bench/r/sim.R --variant r-rcpp --n 500 --years 100 --seed 42 --threads 4 --out /tmp/y
```
Options : `--variant {r-base,r-rcpp}`, `--n`, `--years`, `--seed`, `--threads`, `--out`,
`--inject-nan ANNÉE`, `--hmax-zero`. Sorties : `summary.csv`, `state_final.f32`, `timing.json`.
Code de sortie 1 et message en français sur contrôle échoué (§6.8) ou entrée invalide (P8).

La première exécution compile `src/bench.cpp` (environ 8 s) dans `bench/r/.cache/` (réutilisé ensuite,
hors chronomètre ; variable `SYLVI_CACHE` pour changer le dossier). Lancer une première fois seul avant
de lancer des exécutions en parallèle.

Tests : `Rscript bench/r/tests/run_tests.R`.

## Ce qui est en R, ce qui est en C++

- **L'aléa du §2 est calculé en C++ (Rcpp) dans les deux variantes** : R de base n'a pas d'entier non signé
  64 bits modulo 2^64. **`r-base` dépend donc de Rcpp pour l'aléa seulement** (`u_vec`), ainsi que pour
  l'arrondi f32 (`to_f32`, P1), le contrôle (`check_state`) et les réductions du §7 (`row_summary`,
  `sum()` de R accumule en long double, ce que le §7 n'autorise pas). Le reste de `r-base` est du R vectorisé.
- `r-rcpp` : en plus, `step_cells` fait les étapes 3 à 7 par cellule en C++, parallélisées avec RcppParallel
  (TBB), `--threads T` via `setThreadOptions`. Chaque cellule est indépendante et l'aléa ne dépend que de
  `(seed, year, c, s)` : sorties identiques au bit près entre fils (testé, T=1 contre T=4).
- `r-base` n'a pas de parallélisme : `--threads` est accepté et ignoré (noté dans `timing.json`).
- La FFT (étape 2) est `stats::fft` dans les deux variantes, sur **toute la grille** (pas de tuiles), donc
  monothread aussi dans `r-rcpp`. Remplissage à zéro à la plus petite taille 2^a·3^b·5^c ≥ N + 16
  (N=500 donne 540 ; N=1000 donne 1024), tailles où `stats::fft` est efficace. Deux essences sont traitées par FFT
  complexe (réelle et imaginaire), le noyau étant réel : 4 FFT directes et 4 inverses par pas au lieu de 8 et 8.
- Disposition : l'état est une matrice `ncell x 8` (colonne = essence), `c = i*N + j`. Pour la FFT on
  utilise `matrix(v, N, N)`, indexée [j, i] ; le noyau étant symétrique, le résultat est le même.
- Les nombres R sont des doubles : l'état « f32 » est un double arrondi par un cast `float` en C++.
  La mémoire de R est donc environ double de celle d'un vrai f32.
- Parcours du contrôle (P7) : essence, puis cellule (ligne, colonne), puis B, D, H.
