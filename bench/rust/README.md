# Banc d'essai — variante Rust (`bench-sim`)

Exploration jetable (mission 004, ADR 0001 point B3). Implémente à la lettre
`bench/SPEC.md`. **Aucune valeur n'est écologique** : les paramètres sont synthétiques.

## Versions

- rustc 1.97.0 (2d8144b78 2026-07-07), cargo 1.97.0 (édition 2024)
- Crates directes : `rustfft` 6.4.1 (FFT), `rayon` 1.12.0 (parallélisme)
- Crates indirectes (voir `Cargo.lock`, versionné) : rayon-core 1.13.0, num-complex 0.4.6,
  num-traits 0.2.19, num-integer 0.1.47, transpose 0.2.3, strength_reduce 0.2.4,
  primal-check 0.3.4, either 1.19.0, crossbeam-deque 0.8.8, crossbeam-epoch 0.9.21,
  crossbeam-utils 0.8.23, autocfg 1.5.1
- Stockage : `Vec<f32>` (pas de ndarray)

## Installation et lancement

```
cd bench/rust
cargo build --release          # télécharge les crates depuis crates.io
cargo test                     # tests unitaires et d'intégration
target/release/bench-sim --n 500 --years 100 --seed 42 --threads 1 --out out-n500/rust
```

Options : `--n N --years Y --out DIR` (obligatoires), `--seed S` (42), `--threads T` (1),
`--inject-nan ANNEE` (H[0,0] = NaN au début de cette année : le contrôle doit arrêter),
`--hmax-zero` (Hmax[0,0] = 0 : refusé avant le premier pas). Code de sortie 1 pour une
erreur d'exécution ou de contrôle, 2 pour une ligne de commande invalide. Messages en français.

Sorties : `summary.csv`, `state_final.f32`, `timing.json` (format du §7). Elles ne sont
écrites qu'à la fin d'une exécution réussie.

## Choix d'implémentation

- **FFT sur toute la grille** (pas de tuiles), remplissage à zéro jusqu'à
  `p >= N + 16`, `p` de la forme 2^a·3^b·5^c (N = 500 donne p = 540). Lignes, transposition,
  lignes. Noyau transformé une seule fois. Convolution linéaire (bord à zéro), pas de tore.
- **Déterminisme** : toutes les opérations sont par cellule ou par ligne FFT (indépendantes) ;
  les réductions de `summary.csv` sont faites en f64 dans l'ordre des lignes (somme par ligne
  j croissant, puis lignes i croissant), jamais par `par_iter().sum()`. Sorties identiques
  au bit près entre 1 et 4 fils (testé).
- **Robustesse** : `overflow-checks = true` en release ; `wrapping_mul`/`wrapping_add`
  explicites dans l'aléa seulement ; erreurs par `Result` (type `Erreur`, message français) ;
  plafond de hauteur écrit `if h > hmax` (et non `f32::min`, qui masquerait un NaN).
- Étapes 4 à 7 traitées essence par essence (L est calculée avant, à l'étape 3) : même résultat.

## Ambiguïtés de la spec (non tranchées par l'agent : choix provisoires, à confirmer)

Voir le rendu de la mission ; liste reprise dans la description de la PR.

1. **A1 — arrondi f32** : l'état est arrondi en f32 après chaque étape numérotée qui l'écrit
   (4, 5, 6, 7), pas seulement en fin de pas.
2. **A2 — blocs de lignes** (§7) : taille de bloc non précisée ; ici un bloc = une ligne.
   Le choix change les derniers chiffres des sommes f64.
3. **A3 — année 0** : `summary.csv` contient les années 1 à Y seulement.
4. **A4 — format 17 chiffres** : notation scientifique `{:.16e}` (ex. `1.2345678901234567e3`).
5. **A5 — `total_s`** : init + pas, hors écriture (`write_s` à part) ; `step_mean_s` = temps
   des pas (contrôle et résumé compris) / Y.
6. **A6 — contrôle** : seuls NaN, négatif et `D > Dmax` arrêtent (littéral). Un `+inf` dans B ou H
   n'arrête pas directement ; il est attrapé s'il produit ensuite un NaN. `--inject-nan` hors de
   1..Y est refusé (spec muette).
7. **A7 — ordre du contrôle** : premier défaut dans l'ordre essence, ligne, colonne, puis B, D, H.
8. **A8 — « refusé à la lecture »** (`--hmax-zero`) : toute valeur de Hmax <= 0 ou non finie est
   refusée, après l'initialisation et avant le premier pas.
