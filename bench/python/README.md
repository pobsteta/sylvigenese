# Banc d'essai — implémentation Python (py-numpy, py-numba)

Exploration jetable, selon `bench/SPEC.md` (sections 1 à 10). Aucune valeur n'est
écologique : les paramètres sont synthétiques.

## Versions utilisées

Python 3.13.18 ; numpy 2.5.3 ; scipy 1.18.1 ; numba 0.68.1 ; pytest 9.1.1.

## Installation

    pip install -r bench/python/requirements.txt   # versions exactes

## Lancement

    python3 bench/python/sim.py --variant py-numpy --n 500 --years 100 --seed 42 --threads 1 --out /tmp/x
    python3 bench/python/sim.py --variant py-numba --n 500 --years 100 --seed 42 --threads 4 --out /tmp/y

Options : `--inject-nan ANNÉE` (doit être dans 1 … Y), `--hmax-zero`.
Les entiers (`--n`, `--years`, `--seed` dans [0, 2^53), `--threads`, `--inject-nan`) doivent être écrits
en chiffres ; tout le reste est refusé (SPEC AM2).
Codes de sortie (SPEC AM3) : 0 ok ; 2 entrée refusée (avant le premier pas) ; 3 contrôle du §6.8
déclenché (message en français : année, cellule, essence) ; 4 « Mémoire insuffisante » (`MemoryError`
interceptée).
Sorties dans `--out` : `summary.csv` (`%.16e`), `state_final.f32`, `timing.json`.

## Tests

    cd bench/python && python3 -m pytest -q

Les tests de fils lancent `sim.py` en sous-processus (le nombre de fils numba est fixé à
l'import).

## Choix d'implémentation

- **FFT réelle sur toute la grille** (pas de tuiles), remplissage à zéro jusqu'à
  `next_fast_len(max(N+16, 33))`, `scipy.fft.rfft2/irfft2` (AM1).
- **Déterminisme : voie « FFT sur un seul fil ».** Les FFT s'exécutent toujours avec
  `workers=1`, quel que soit `--threads`. Ainsi l'identité au bit près entre 1 et T fils est
  garantie **par construction** : tout ce qui est parallèle (numba, `prange` sur les lignes)
  est calculé cellule par cellule, sans réduction parallèle, et ne dépend ni de l'ordre ni du
  nombre de fils. Je n'ai pas retenu `workers=T`, dont l'identité n'aurait été
  qu'observée (rien dans la documentation de scipy ne la promet).
  **Coût** : la FFT (8 essences par pas) reste sérielle. À N=500 : `py-numba` passe de 10,96 s
  (1 fil) à 8,17 s (4 fils), au lieu d'environ 7,3 s avec `workers=4` ; `py-numpy` ne gagne rien
  (21,1 s contre 21,0 s), car numpy est mono-fil et seule sa FFT aurait pu l'être.
- Les graines, la dispersion et la mise à jour sont faites essence par essence ; la lumière
  (étape 3) est calculée d'abord sur l'état d'avant le pas. C'est équivalent à l'ordre
  de la spec (les essences ne se couplent que par la lumière).
- **Fils** : `py-numba` : `NUMBA_NUM_THREADS=T` + `numba.set_num_threads(T)` (vérifié),
  `prange` sur les lignes, aucune réduction parallèle. `py-numpy` : numpy est
  mono-fil et la FFT aussi : `--threads` n'a pas d'effet sur son temps.
- Réductions de `summary.csv` : somme par ligne en f64 dans l'ordre j, puis sommes de
  lignes dans l'ordre i (SPEC §10, P2).
- `py-numba` : la compilation (ou le chargement du cache `__pycache__`) est faite avant
  la mesure et n'est pas comprise dans `init_s` ; elle est écrite sur stderr.
- `total_s` = init + pas, hors écriture ; `lang` = nom de la variante.
