# Banc d'essai — implémentation Python (py-numpy, py-numba)

Exploration jetable, selon `bench/SPEC.md` (sections 1 à 10). Aucune valeur n'est
écologique : les paramètres sont synthétiques.

## Versions utilisées

Python 3.13.18 ; numpy 2.5.3 ; scipy 1.18.1 ; numba 0.68.1 ; pytest 9.1.1.

## Installation

    pip install numpy scipy numba pytest

## Lancement

    python3 bench/python/sim.py --variant py-numpy --n 500 --years 100 --seed 42 --threads 1 --out /tmp/x
    python3 bench/python/sim.py --variant py-numba --n 500 --years 100 --seed 42 --threads 4 --out /tmp/y

Options : `--inject-nan ANNÉE` (doit être dans 1 … Y), `--hmax-zero`.
Codes de sortie : 0 ok ; 2 entrée refusée (avant le premier pas) ; 3 contrôle du §6.8
déclenché (message en français : année, cellule, essence).
Sorties dans `--out` : `summary.csv` (`%.16e`), `state_final.f32`, `timing.json`.

## Tests

    cd bench/python && python3 -m pytest -q

Les tests de fils lancent `sim.py` en sous-processus (le nombre de fils numba est fixé à
l'import).

## Choix d'implémentation

- **FFT sur toute la grille** (pas de tuiles), remplissage à zéro jusqu'à
  `next_fast_len(max(N+16, 33))`, `scipy.fft.rfft2/irfft2` avec `workers=T`.
- Les graines, la dispersion et la mise à jour sont faites essence par essence ; la lumière
  (étape 3) est calculée d'abord sur l'état d'avant le pas. C'est équivalent à l'ordre
  de la spec (les essences ne se couplent que par la lumière).
- **Fils** : `py-numba` : `NUMBA_NUM_THREADS=T` + `numba.set_num_threads(T)` (vérifié),
  `prange` sur les lignes, aucune réduction parallèle. `py-numpy` : numpy est
  mono-fil ; seul `scipy.fft` utilise `workers=T`.
- Réductions de `summary.csv` : somme par ligne en f64 dans l'ordre j, puis sommes de
  lignes dans l'ordre i (SPEC §10, P2).
- `py-numba` : la compilation (ou le chargement du cache `__pycache__`) est faite avant
  la mesure et n'est pas comprise dans `init_s` ; elle est écrite sur stderr.
- `total_s` = init + pas, hors écriture ; `lang` = nom de la variante.
