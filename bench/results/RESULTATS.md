# Résultats du banc d'essai (mission 005)

> **MESURES PRÉLIMINAIRES.** Faites dans un conteneur à 4 cœurs et 16 Go (MemTotal 16 087 Mo, ~13,6 Go
> réellement utilisables avant l'arrêt par le noyau), CPU Intel Xeon 2,1 GHz (`machine.json`). Ce n'est
> pas la machine de référence de Pascal (i7-4940MX 3,1 GHz, 4 cœurs physiques / 8 logiques, 31 Go). Les
> mesures portent sur le code repris après les amendements AM1 à AM4 (SPEC §11). Les chiffres
> « (E) » sont des extrapolations (Y=10 mesuré, voir §1). Ce document présente des faits ; il ne choisit pas le langage.

Mission : mesurer les cinq variantes (`r-base`, `r-rcpp`, `py-numpy`, `py-numba`, `rust`) selon SPEC §9, sur une
même machine, pour éclairer l'ADR 0001 (vitesse, mémoire, robustesse à l'échelle d'une SER).

Fichiers : `mesures.csv`, `identite.csv`, `ecarts.csv`, `robustesse.csv`, `machine.json`, `run_bench.sh`
(rejouable ; voir `LANCER_CHEZ_SOI.md`). Graine 42. Essais un par un. Mémoire maximale : « Maximum resident set size »
de `/usr/bin/time -v`. Le CSV porte aussi `init_s`, `step_mean_s`, `write_s`, le code de sortie.

## 1. Tableau principal (variante × N × T)

Temps de 100 ans en secondes, tel que donné par `timing.json` (`total_s`, hors écriture). « (E) » : mesuré sur
Y=10 années, **extrapolé** à 100 ans par `init_s + 100 × step_mean_s` (SPEC §9). Sans « (E) » : Y=100 mesuré.
Le temps réel (`/usr/bin/time`, démarrage et compilation JIT compris) est celui de l'essai tel que lancé (Y mesuré, non
extrapolé). La mémoire est celle de T=1 ; T=4 est identique à moins de 1 %. « sauté » : une taille inférieure de
la même variante a échoué (SPEC §9). `r-base` et `py-numpy` ne parallélisent pas (README) ; leur T=4 est donc
une répétition à l'identique.

| Variante | N | Y mesuré | T=1 : temps 100 ans (s) | T=4 : temps 100 ans (s) | Mémoire max (Mo) | Temps réel T=1 / T=4 (s, /usr/bin/time) |
|---|---|---|---|---|---|---|
| rust | 500 | 100 | 11.7 | 3.7 | 60.3 | 12 / 4 |
| rust | 1000 | 100 | 52.8 | 15.1 | 221.5 | 53 / 15 |
| rust | 2000 | 10 | 233 (E) | 62.3 (E) | 867.6 | 25 / 7 |
| rust | 4000 | 10 | 926 (E) | 246 (E) | 3456.4 | 98 / 30 |
| rust | 8000 | 10 | hors mémoire (tué par l'OOM : code 137) | sauté | 13594.7 (au moment de l'arrêt) | 22 / — |
| py-numpy | 500 | 100 | 20.6 | 20.7 | 137.2 | 21 / 21 |
| py-numpy | 1000 | 100 | 89.9 | 84.9 | 356.9 | 90 / 85 |
| py-numpy | 2000 | 10 | 425 (E) | 393 (E) | 1234.4 | 46 / 41 |
| py-numpy | 4000 | 10 | 2 639 (E) | 2 654 (E) | 4508.2 | 274 / 275 |
| py-numpy | 8000 | 10 | hors mémoire (tué par l'OOM : code 137) | sauté | 13601.9 (au moment de l'arrêt) | 73 / — |
| py-numba | 500 | 100 | 11.0 | 6.5 | 218.0 | 12 / 7 |
| py-numba | 1000 | 100 | 43.2 | 29.3 | 362.1 | 44 / 30 |
| py-numba | 2000 | 10 | 203 (E) | 114 (E) | 928.0 | 24 / 13 |
| py-numba | 4000 | 10 | 970 (E) | 533 (E) | 3245.8 | 102 / 57 |
| py-numba | 8000 | 10 | 5 399 (E) | 2 435 (E) | 12498.8 | 564 / 257 |
| r-base | 500 | 100 | 55.1 | 55.2 | 419.6 | 55 / 56 |
| r-base | 1000 | 100 | 238 | 231 | 1343.3 | 238 / 232 |
| r-base | 2000 | 10 | 1 101 (E) | 1 129 (E) | 4793.7 | 116 / 118 |
| r-base | 4000 | 10 | hors mémoire (tué par l'OOM : code 137) | sauté | 13594.7 (au moment de l'arrêt) | 123 / — |
| r-base | 8000 | 10 | sauté | sauté | — | — / — |
| r-rcpp | 500 | 100 | 30.9 | 27.0 | 273.2 | 31 / 27 |
| r-rcpp | 1000 | 100 | 145 | 141 | 835.1 | 145 / 142 |
| r-rcpp | 2000 | 10 | 997 (E) | 825 (E) | 2665.9 | 107 / 89 |
| r-rcpp | 4000 | 10 | 6 300 (E) | 6 501 (E) | 8993.4 | 663 / 688 |
| r-rcpp | 8000 | 10 | hors mémoire (tué par l'OOM : code 137) | sauté | 13594.9 (au moment de l'arrêt) | 104 / — |

Statut « hors mémoire (tué par l'OOM : code 137) » : le noyau a tué l'essai (le garde RSS à 85 % de la mémoire
totale n'a pas eu le temps d'agir avant, ou le seuil réel du conteneur est plus bas). **Le code 4 (« Mémoire
insuffisante » intercepté, SPEC AM3) n'a jamais été obtenu** : l'allocation réussit (sur-allocation du noyau),
puis le processus est tué. Ce sont des « hors mémoire » au sens du protocole. Aucun essai « hors temps » (plafond de
45 min jamais atteint ; le plus long : r-rcpp N=4000, ≈11 min). La mémoire de rust à N=8000 n'est pas mesurée (tué
à 13,6 Go, 22 s après le début) ; elle est extrapolée au §6.

## 2. Identité au bit près, T=1 contre T=4

`identite.csv` : comparaison par `cmp` de `state_final.f32` et de `summary.csv`, à chaque taille où T=1 et T=4 ont réussi.
**20 comparaisons sur 20 identiques** (rust 500 à 4000 ; py-numpy 500 à 4000 ; py-numba 500 à 8000 ; r-base 500 à 2000 ;
r-rcpp 500 à 4000). Aucune différence. Les cases absentes sont celles des tailles hors mémoire ou sautées.

## 3. Écart relatif maximal entre variantes (summary.csv)

Écart relatif `|a−b| / max(|a|,|b|)` sur `sum_B`, `sum_D`, `mean_H`, toutes années et essences (`ecarts.csv` donne toutes
les paires ; sorties T=1). Tolérance attendue : 1e-6.

| N | Écart max (toutes paires) | Paire et position |
|---|---|---|
| 500 | 1,41e-12 | `py-numba` et `py-numpy` contre `r-base`, `r-rcpp`, `rust` : sum_D, année 23, essence 2 |
| 1000 | 2,13e-13 | `rust` contre toutes les autres : sum_D, année 19, essence 1 |
| 2000 | 1,95e-14 | `py-*` contre `r-*` et `rust` : sum_D, année 1, essence 4 |
| 4000 | 1,36e-14 | `py-*` contre `r-rcpp` et `rust` : sum_D, année 4, essence 5 |
| 8000 | — | une seule variante (py-numba) a réussi : aucune comparaison possible |

Tous très en dessous de 1e-6. `py-numba` et `py-numpy` sont identiques entre elles (écart 0) à toutes les tailles ;
`r-base`, `r-rcpp` et `rust` le sont entre eux à N=500, 2000, 4000 (là où ils ont tous réussi).

## 4. Robustesse (N=200, Y=20, T=1)

`robustesse.csv` (message complet). Attendu : `--inject-nan 5` → 3, `--hmax-zero` → 2, graine invalide (−1, 1.5, 2^53) → 2.
**25 essais sur 25 conformes** (5 variantes × 5 cas). Tous les messages sont en français et nomment l'année, la cellule et
l'essence (contrôle) ou la valeur refusée (entrée). Exemple, r-rcpp `--inject-nan 5` : « Contrôle échoué :
H[essence 0, cellule 0 (ligne 0, colonne 0)] vaut NaN, année 5. Arrêt. »

## 5. Lignes de code hors tests

Lignes brutes / lignes de code (non vides, hors commentaires `//` et `#`) des fichiers de `bench/<langage>/`, hors
`tests/`, `target/`, `.cache/`, et pour Rust hors modules `#[cfg(test)]` (dans `conv.rs` et `rng.rs`). Compté par un petit
script Python lancé à la main (équivalent de `wc -l` sur les fichiers listés pour le brut).

| Variante | Fichiers | Brutes | Code |
|---|---|---|---|
| rust | `rust/src/*.rs` (7) | 744 | 616 |
| py-numpy | `python/{params,sim,rng,kernel,v_numpy}.py` | 363 | 302 |
| py-numba | `python/{params,sim,rng,kernel,v_numba}.py` | 497 | 417 |
| r-base | `r/sim.R`, `r/R/core.R`, `r/src/bench.cpp` | 454 | 367 |
| r-rcpp | mêmes fichiers (code commun aux deux variantes R, non séparable) | 454 | 367 |

`r-base` embarque du C++ (aléa, arrondi f32, contrôle, réductions) : les 168 lignes de `bench.cpp` sont comprises.

## 6. Tient-elle la cible B1 ? (extrapolation à N=8000 et au-delà)

Cible de Pascal : **au plus 5 jours (432 000 s)** pour 100 ans d'une SER, sur son PC (31 Go, 4 cœurs physiques).
Tout ce paragraphe est une **extrapolation** à partir de mes mesures du conteneur, non une mesure à la taille visée.

- **Loi du temps** : `t(N) = t(N0) × (N/N0)² × ln(N+16) / ln(N0+16)` (grille remplie à N+16, FFT en p² log p), appliquée au
  temps de 100 ans (T=4) de la plus grande taille réussie N0 (4000 ; py-numba 8000 ; r-base 2000). Les rapports observés par
  doublement de N sont de 3,9 à 4,9 pour rust, py-numba, r-base, mais de 6 à 8 pour py-numpy (2000 → 4000 : 6,8) et r-rcpp
  (5,9 puis 7,9 en step_mean_s) : la loi sous-estime alors leurs temps (effets de cache ou de mémoire
  probables, non vérifiés). Version pessimiste (dernier rapport observé, appliqué une fois) : py-numpy ≈ 18 000 s, r-rcpp ≈ 51 000 s à N=8000.
- **Loi de la mémoire** : `RSS(N) = b × N²`, b mesuré à la plus grande taille réussie : rust 227 octets/cellule (N=4000),
  py-numpy 295 (4000), py-numba 205 (8000), r-base 1257 (2000), r-rcpp 589 (4000).
- **Mémoire utilisable** prise à 28 Go sur 31 (marge de 10 % pour le système ; hypothèse).

| Variante | 100 ans à N=8000, T=4 (s) | Mémoire à N=8000 (Go) | Tient à N=8000 ? (≤ 432 000 s et ≤ 31 Go) | Mémoire à N=16 000 (Go) | N maximal en 28 Go | Temps à N=16 000 (s) |
|---|---|---|---|---|---|---|
| rust | 1 065 (E) | 14,5 (E) | oui (extrapolé, non observé) | 58 | ≈ 11 100 | 4 590 |
| py-numpy | 11 500 (E) ; pessimiste 18 000 | 18,9 (E) | oui (extrapolé ; arrêté ici à 13,6 Go) | 76 | ≈ 9 700 | 49 500 |
| py-numba | 2 435 (E, Y=10 mesuré à N=8000) | 12,5 (mesuré) | oui | 52 | ≈ 11 700 | 10 500 |
| r-base | 21 300 (E) | 80 (E) | **non : mémoire** | 322 | ≈ 4 700 | 91 900 |
| r-rcpp | 28 200 (E) ; pessimiste 51 000 | 37,7 (E) | **non : mémoire** | 151 | ≈ 6 900 | 121 400 |

Lecture : le temps ne départage aucune variante pour la cible (toutes ≤ 51 000 s à N=8000, marge ≥ 8 ; même `r-base`
à N=16 000 est à 92 000 s). La **mémoire** sépare : à 31 Go, `r-base` et `r-rcpp` ne passent pas N=8000 ; aucune
variante ne passe N=16 000 sous ces lois. La taille réelle d'une SER en cellules n'est pas connue de moi (à Pascal).
Avertissement : extrapolation de ×2 en N (4000 → 8000) pour la plupart, ×4 pour `r-base` (2000 → 8000), ×2 de plus pour
N=16 000, avec 2 ou 3 points de mesure ; sur une autre machine la mémoire est à peu près la même, le temps non
(T=4 ici ; la machine de Pascal a 4 cœurs physiques et 8 logiques).

## 7. Pareto des causes de coût

**Non mesuré.** Je n'ai pas profilé (FFT, aléa, accès mémoire) : cela demandait d'instrumenter les
implémentations, ce qui est interdit à cette mission. Faits indirects seulement :
- Accélération T=1 → T=4 à la plus grande taille : 3,8 pour rust (N=4000), 2,2 pour py-numba (N=8000), 1,0 pour
  py-numpy, r-base et r-rcpp : ces trois-là ne parallélisent pas leur coût dominant (FFT scipy ou `stats::fft`, noyau
  numpy ou R : mono-fil, d'après les README). C'est un indice, pas une mesure de la part de la FFT.
- `wall_s` − `total_s` (démarrage, compilation JIT ou chargement du cache, écriture) : de 0,03 s (rust, N=500) à ≈ 0,8 s
  (py-numba, N=500) et ≈ 14 s (py-numba, N=8000, dont l'écriture de l'état).
- La mémoire est ce qui arrête les grandes tailles (§6).

## 8. Limites

- **Machine** : conteneur à 4 cœurs, Xeon 2,1 GHz, 16 Go dont ≈ 13,6 Go utilisables ; pas la machine de Pascal. Les temps ne se
  transposent pas tels quels ; `run_bench.sh` se relance chez lui (`LANCER_CHEZ_SOI.md`).
- **Extrapolations** : tous les temps « (E) » (Y=10 → 100 ans) et le §6 (lois en N² log N et N², 2 ou 3 points).
- **Non mesuré** : N=8000 pour rust, py-numpy, r-rcpp (hors mémoire ici) et r-base (sauté) ; N=16 000 ; le Pareto des
  coûts ; T=8 (le conteneur a 4 cœurs : chez Pascal le script mesurera T = 1, cœurs physiques et `nproc`) ; une seule
  répétition par essai (pas de dispersion).
- **Mémoire** : pas de `ulimit -v` (il pénalise inégalement les runtimes multi-fils). Un garde surveille la RSS du groupe
  de processus (via `ps`, seuil 85 % de la mémoire totale) ; le noyau a tué les essais vers 13,6 Go. Les quatre « hors
  mémoire » (rust, py-numpy, r-rcpp à N=8000 ; r-base à N=4000) sont **propres à cette machine** ; sur 31 Go, rust et py-numpy
  y arriveront probablement.
- **Anomalies** : (1) le code de sortie 4 (AM3) n'a jamais été obtenu : les quatre essais hors mémoire finissent par 137 ; les
  messages « Mémoire insuffisante » ne sont pas vérifiés à l'échelle. (2) Une première version du script écrivait une virgule dans le
  statut du CSV : corrigée dans le script et dans les quatre lignes concernées, rien d'autre modifié. (3) Les fichiers
  `*_avant_reprise.csv` (code ancien) ne sont pas utilisés ici. (4) Pendant la montée en taille, j'ai modifié `run_bench.sh`
  (T = 1, cœurs physiques, nproc) par remplacement de fichier : les essais déjà faits utilisaient T ∈ {1, 4}, identique ici
  (4 cœurs physiques = nproc).
