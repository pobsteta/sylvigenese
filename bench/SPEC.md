# Banc d'essai du moteur de simulation : spécification commune

> **Exploration jetable** (décision de Pascal du 24/11/2026, point B3 de la critique de
> l'ADR 0001). Ce code ne deviendra pas le moteur de sylvigenese. Il sert à mesurer, au
> même algorithme, ce que R, Python et Rust tiennent à l'échelle d'une SER.
>
> **Aucune valeur de ce banc n'est écologique.** Les paramètres ci-dessous sont
> **synthétiques**, choisis pour avoir le coût de calcul d'une vraie simulation (BRIEF
> §0.3). Ils ne doivent jamais servir de paramètres de `simulate`.

Les trois implémentations suivent ce texte **à la lettre**. Une ambiguïté se signale à
l'orchestrateur ; on ne la tranche pas seul.

## 1. Données

- **Grille** : `N × N` cellules de 25 m, indice de cellule `c = i * N + j` (ligne `i`,
  colonne `j`, à partir de 0). Tailles : `N ∈ {500, 1000, 2000, 4000, 8000}`.
- **Essences** : `S = 8`, indice `s` de 0 à 7.
- **État par cellule et par essence**, en **f32** :
  - `B[s,c]` : surface terrière des semenciers (m²/ha) ;
  - `D[s,c]` : densité des semis (tiges/ha) ;
  - `H[s,c]` : hauteur moyenne des semis (m).
- **Données fixes** : `Hmax[s,c]` (f32, plafond de hauteur) et `forest[c]` (u8, 1 si la
  cellule est boisée).

## 2. Aléa : générateur à compteur (identique dans les trois langages)

`u(seed, year, cell, sp)` renvoie un nombre dans [0, 1) :

```
M = 2^64 (toute l'arithmétique est modulo 2^64, sur des entiers non signés de 64 bits)
x = seed XOR (year * 0x9E3779B97F4A7C15) XOR (cell * 0xBF58476D1CE4E5B9) XOR (sp * 0x94D049BB133111EB)
x = x + 0x9E3779B97F4A7C15
z = (x XOR (x >> 30)) * 0xBF58476D1CE4E5B9
z = (z XOR (z >> 27)) * 0x94D049BB133111EB
z = z XOR (z >> 31)
u = (z >> 11) * 2^-53          (en f64)
```

Valeurs de référence, à tester dans chaque langage :

| seed | year | cell | sp | u |
|---|---|---|---|---|
| 42 | 0 | 0 | 0 | 0.7415648787718233 |
| 42 | 1 | 0 | 0 | 0.1599103928769201 |
| 42 | 0 | 1 | 0 | 0.14994666025136738 |
| 42 | 0 | 0 | 1 | 0.5322551776720237 |
| 42 | 99 | 999999 | 7 | 0.8685522737309959 |
| 7 | 3 | 123456 | 2 | 0.3924761688504701 |

Le tirage d'une cellule ne dépend que de `(seed, year, cell, sp)`. Le résultat ne dépend
donc ni de l'ordre de parcours ni du nombre de fils.

## 3. État initial (à partir de la graine, `year = 0` réservé à l'initialisation)

Avec `seed` (défaut 42) :
- `forest[c] = 1` si `u(seed, 0, c, 100) < 0.7`, sinon 0 ;
- `Hmax[s,c] = 10 + 30 * u(seed, 0, c, 200 + s)` ;
- `B[s,c] = forest[c] * 5 * u(seed, 0, c, 300 + s)` (f32) ;
- `D[s,c] = 0`, `H[s,c] = 0`.

## 4. Paramètres synthétiques

| Nom | Valeur | Rôle |
|---|---|---|
| `fec` | 100.0 | production de graines par m²/ha de semenciers |
| `alpha` | 50.0 m | portée du noyau exponentiel |
| `R` | 400 m, soit 16 cellules | rayon de troncature du noyau |
| `k` | 0.05 | extinction de la lumière par m²/ha de surface terrière |
| `tol[s]` | `0.5 + 0.25 * s` | sensibilité de l'installation à la lumière |
| `est` | 0.01 | taux d'installation |
| `r[s]` | `0.3 + 0.05 * s` | croissance en hauteur (m/an) |
| `m[s]` | `0.05 + 0.01 * s` | mortalité annuelle de base des semis |
| `h_rec` | 3.0 m | hauteur de passage aux semenciers |
| `g` | 0.0001 | m²/ha de surface terrière par tige recrutée |
| `Dmax` | 1.0e6 | borne de contrôle de `D` |

## 5. Noyau de dispersion

`K[di,dj] = exp(-d / alpha)` avec `d = 25 * sqrt(di² + dj²)`, pour `|di|, |dj| ≤ 16` et
`d ≤ 400` ; 0 ailleurs. Il est normalisé pour que la somme vaille 1. Il est **calculé en
f64**.

## 6. Un pas annuel, pour `year = 1 … Y`

Dans cet ordre, toutes les grandeurs intermédiaires en **f64**, l'état stocké en **f32** :

1. **Graines** : `P[s,c] = fec * B[s,c]`.
2. **Dispersion** : `Q[s] = P[s] ⊛ K`, une convolution 2D **par FFT**, avec un bord à zéro
   (pas de repli torique : remplissage à zéro d'au moins 16 cellules). C'est un algorithme
   imposé : la convolution directe est interdite pour cette étape. La FFT peut être faite
   sur toute la grille ou par tuiles avec un recouvrement de 16 cellules ; c'est à
   préciser dans le rendu.
3. **Lumière** : `Btot[c] = Σ_s B[s,c]`, puis `Bbar[c]` = moyenne de `Btot` sur la fenêtre
   3×3 centrée sur `c` (les cellules hors grille ne comptent pas, la moyenne se fait sur
   les cellules présentes), et `L[c] = exp(-k * Bbar[c])`. Convolution directe autorisée.
4. **Installation** : `D[s,c] += forest[c] * est * Q[s,c] * L[c]^tol[s]`.
5. **Croissance** : `H[s,c] += r[s] * L[c] * (1 - H[s,c] / Hmax[s,c])` si `D[s,c] > 0`,
   puis `H[s,c] = min(H[s,c], Hmax[s,c])`.
6. **Mortalité** : `D[s,c] *= 1 - m[s] * (0.8 + 0.4 * u(seed, year, c, s))`.
7. **Recrutement** : si `H[s,c] ≥ h_rec`, alors `B[s,c] += g * D[s,c]`, `D[s,c] = 0`,
   `H[s,c] = 0`.
8. **Contrôle**, à chaque pas : si une valeur de `B`, `D` ou `H` est NaN, négative, ou si
   `D > Dmax`, le programme **s'arrête** avec un code de sortie non nul et un message en
   français qui nomme l'année, la cellule et l'essence (BRIEF §0.6). Jamais de correction
   silencieuse.

## 7. Entrées et sorties

- **Ligne de commande** : `--n N --years Y --seed S --threads T --out DIR`, plus
  `--inject-nan YEAR` (met `H[0,0] = NaN` au début de cette année, pour tester le
  contrôle) et `--hmax-zero` (met `Hmax[0,0] = 0`, entrée invalide qui doit être refusée à
  la lecture, avant le premier pas).
- **`DIR/summary.csv`**, une ligne par année et par essence :
  `year,species,sum_B,sum_D,mean_H`. Les sommes sont calculées en f64, par blocs de lignes
  de grille, dans l'ordre des lignes (réduction déterministe). `mean_H` est la moyenne de
  `H` sur les cellules où `D > 0` ; elle vaut 0 s'il n'y en a aucune. Les nombres sont
  écrits avec 17 chiffres significatifs.
- **`DIR/state_final.f32`** : `B`, puis `D`, puis `H`, chacun `[s][i][j]`, en f32
  little-endian brut.
- **`DIR/timing.json`** : `{"lang": …, "n": …, "years": …, "threads": …, "init_s": …,
  "step_mean_s": …, "total_s": …, "write_s": …}`.

## 8. Ce que chaque implémentation fournit

- Le code, dans `bench/<langage>/`, avec un `README.md` qui dit comment l'installer et
  le lancer, et les versions exactes des outils.
- Des tests : valeurs de référence du générateur (§2), normalisation du noyau (somme = 1 à
  1e-12 près), une FFT comparée à une convolution directe sur une petite grille (écart
  relatif < 1e-9), et l'arrêt avec un message sur `--inject-nan` et `--hmax-zero`.
- **Deux variantes quand le langage s'y prête**, mesurées séparément :
  - **R** : `r-base` (vectorisé, `stats::fft`) et `r-rcpp` (cœur en Rcpp) ;
  - **Python** : `py-numpy` (numpy et scipy.fft) et `py-numba` (boucles en numba, FFT
    scipy) ;
  - **Rust** : une seule (ndarray ou Vec, rustfft, rayon).
- Le parallélisme sur `T` fils quand le langage le permet, avec **des sorties
  identiques au bit près entre `T = 1` et `T = 4`**.

## 9. Mesures (faites par l'orchestrateur, mission séparée)

Sur la même machine, pour chaque variante et chaque `N`, avec `T = 1` et `T = 4` :
- le temps (`timing.json`) ;
- la mémoire maximale (`/usr/bin/time -v`, « Maximum resident set size ») ;
- l'identité au bit près des sorties entre `T = 1` et `T = 4` ;
- l'écart entre langages sur `summary.csv` (écart relatif maximal ; tolérance attendue
  1e-6, à cause des FFT différentes) ;
- le comportement sur `--inject-nan 5` et `--hmax-zero` ;
- le nombre de lignes de code hors tests.

`Y = 100` pour `N ≤ 1000`. Au-delà, `Y = 10`, et le temps de 100 ans est extrapolé à partir
du temps moyen d'un pas (c'est dit comme une extrapolation). Une variante qui dépasse la
mémoire de la machine est notée « hors mémoire » à cette taille : c'est un résultat, pas
un échec du banc.
