# M5 : coût du noyau de dispersion à K = 3, 20 et 60 cellules (mission 082, 27/11/2026)

> **MESURES DU CONTENEUR, PAS DU PC DE PASCAL** (4 cœurs, 16 Go, Xeon 2,1 GHz ; binaire de
> `cargo build --release --locked`). Tout ce qui est marqué **(E)** est une extrapolation, pas une mesure.
> **RÉGLAGE D'ESSAI, SANS VALEUR ÉCOLOGIQUE** : pour que le contrôle de la mission 080 laisse passer chaque K,
> `kernel_scale_m` est réécrit (forme 1, toutes essences) pour que d99 = 0,99 × K × 25 m ; les autres paramètres
> restent ceux, synthétiques, de `tests/m5/ser_fictive.py`. Aucune des distances ci-dessous n'est celle d'une
> essence réelle.

K désigne ici `kernel_truncation_cells` ; les « classes » de diamètre sont notées C (15 classes pour S = 8).

## Rejouer

Un seul script, depuis la racine : `python3 bench/m5/mesurer_noyau.py` (environ 1 h 15 ; `--petit` pour un essai de
quelques secondes). Il compile `simulate` (`--locked`) et la micro-mesure `bench/m5/noyau_fft/`, génère la SER fictive
sous `data/` (hors dépôt), mesure, et efface `sim/` après chaque exécution et la zone après chaque série. Les
extrapolations (E) viennent de `python3 bench/m5/extrapoler_noyau.py`, qui ne lit que les CSV. Commit de départ :
`50eccfa` (arbre de travail avec les fichiers de `bench/` ajoutés ; `simulate/` inchangé).

| Fichier | Contenu | Renvoi |
|---|---|---|
| `m5_noyau_reglages.csv` | K, portée K × 25 m, `kernel_scale_m` d'essai, d99 | « réglages Lx » |
| `m5_noyau_mesures.csv` | une ligne par exécution de `simulate` : calcul, écriture, durée, écoulé, mémoire résidente | « mesures Lx » |
| `m5_noyau_pas.csv` | calcul et écriture de t0 et de chaque année | « pas Lx » |
| `m5_noyau_fft.csv` | la convolution de dispersion seule (médiane de 5), appel de `simulate::dispersion` | « fft Lx » |
| `m5_noyau_derive.csv` | calcul à K = 3 de cette séance contre M5.md §1, même configuration | « dérive Lx » |
| `m5_noyau_rapports.csv` | rapports calcul et mémoire à K = 3 (même N, S, fils) | « rapports Lx » |
| `m5_noyau_extrapolation.csv`, `m5_noyau_temps_c20.csv` | extrapolations (E) à C20 | « extra Lx », « temps C20 Lx » |

Réglages (réglages L2 à L4) : K = 3 → a = 11,19 m, d99 = 74,25 m ; K = 20 → a = 74,57 m, d99 = 495 m ;
K = 60 → a = 223,70 m, d99 = 1 485 m. Y = 10 ans, graine 42, mode cohorts, `write_step` = 10, une répétition par
exécution. Matrice : N = 1 000 et 2 000 (S = 2, C = 6) à 1 et 4 fils ; N = 1 000 à S = 8, C = 15 (le cas de
référence de M5.md) à 1 et 4 fils ; N = 4 000 (S = 2, C = 6) à 4 fils seulement (disque : 12 Go libres).
Mémoire libre avant : 13 Go sur 16.

## 1. Mesures de `simulate`

| N | S × C | Fils | K | Calcul (s) | Écriture (s) | Durée (s) | Mémoire résidente (octets) | Estimation du moteur (octets) | Cellules de la zone tampon | Ligne |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 000 | 2 × 6 | 1 | 3 | 25,42 | 3,36 | 28,84 | 249 147 392 | 249 248 896 | 12 036 | mesures L2 |
| 1 000 | 2 × 6 | 1 | 20 | 26,04 | 3,52 | 29,62 | 252 989 440 | 252 016 864 | 81 600 | mesures L4 |
| 1 000 | 2 × 6 | 1 | 60 | 23,34 | 3,16 | 26,56 | 259 244 032 | 256 881 024 | 254 400 | mesures L6 |
| 1 000 | 2 × 6 | 4 | 3 | 9,93 | 3,35 | 13,35 | 249 233 408 | 249 248 896 | 12 036 | mesures L3 |
| 1 000 | 2 × 6 | 4 | 20 | 9,93 | 3,13 | 13,13 | 252 813 312 | 252 016 864 | 81 600 | mesures L5 |
| 1 000 | 2 × 6 | 4 | 60 | 9,93 | 3,02 | 13,03 | 259 289 088 | 256 881 024 | 254 400 | mesures L7 |
| 2 000 | 2 × 6 | 1 | 3 | 97,27 | 12,61 | 110,17 | 970 727 424 | 964 839 424 | 24 036 | mesures L8 |
| 2 000 | 2 × 6 | 1 | 20 | 91,91 | 11,23 | 103,37 | 969 318 400 | 969 002 496 | 161 600 | mesures L10 |
| 2 000 | 2 × 6 | 1 | 60 | 96,90 | 11,73 | 108,94 | 984 334 336 | 984 089 344 | 494 400 | mesures L12 |
| 2 000 | 2 × 6 | 4 | 3 | 30,59 | 12,07 | 42,93 | 974 749 696 | 964 839 424 | 24 036 | mesures L9 |
| 2 000 | 2 × 6 | 4 | 20 | 30,11 | 12,10 | 42,45 | 969 158 656 | 969 002 496 | 161 600 | mesures L11 |
| 2 000 | 2 × 6 | 4 | 60 | 33,38 | 12,44 | 46,13 | 984 813 568 | 984 089 344 | 494 400 | mesures L13 |
| 4 000 | 2 × 6 | 4 | 3 | 133,35 | 55,10 | 189,44 | 3 830 513 664 | 3 827 104 768 | 48 036 | mesures L20 |
| 4 000 | 2 × 6 | 4 | 20 | 131,45 | 53,56 | 185,98 | 3 834 757 120 | 3 831 760 864 | 321 600 | mesures L21 |
| 4 000 | 2 × 6 | 4 | 60 | 125,28 | 52,62 | 178,88 | 3 875 266 560 | 3 871 368 064 | 974 400 | mesures L22 |
| 1 000 | 8 × 15 | 1 | 3 | 213,81 | 21,27 | 235,23 | 970 133 504 | 970 116 736 | 12 036 | mesures L14 |
| 1 000 | 8 × 15 | 1 | 20 | 232,65 | 21,34 | 254,11 | 978 038 784 | 977 037 664 | 81 600 | mesures L16 |
| 1 000 | 8 × 15 | 1 | 60 | 207,04 | 21,01 | 228,24 | 991 961 088 | 989 199 744 | 254 400 | mesures L18 |
| 1 000 | 8 × 15 | 4 | 3 | 65,90 | 20,43 | 86,45 | 970 354 688 | 970 116 736 | 12 036 | mesures L15 |
| 1 000 | 8 × 15 | 4 | 20 | 70,68 | 20,72 | 91,52 | 978 059 264 | 977 037 664 | 81 600 | mesures L17 |
| 1 000 | 8 × 15 | 4 | 60 | 70,96 | 22,74 | 93,85 | 992 460 800 | 989 199 744 | 254 400 | mesures L19 |

Le calcul couvre t0 et les 10 années ; la mémoire résidente est celle de `/usr/bin/time -v`, égale au VmHWM du
moteur dans les 22 lignes (colonnes `rss_time_bytes` et `memory_peak_rss_bytes`).

### 1.1 Le temps

- **K n'a pas d'effet détectable sur le calcul.** Les rapports à K = 3 (rapports L2 à L15) vont de 0,92 à 1,09, sans
  ordre : à N = 4 000, 0,99 (K = 20) et 0,94 (K = 60) ; à N = 2 000, 4 fils, 0,98 puis 1,09 ; à S = 8, 4 fils, 1,07
  puis 1,08. Les 4 fils à N = 1 000, S = 2 donnent 9,93 s aux trois K. Une seule répétition par
  exécution, et K a été joué **toujours dans l'ordre 3, 20, 60**, sans alternance : une dérive de la machine dans le
  temps se confond donc avec l'effet de K. Conclusion : **aucun effet de K au-dessus du bruit d'une seule
  exécution** ; la micro-mesure de la section 2 le justifie (au plus 0,3 à 0,6 s de FFT en plus sur des calculs de 65
  à 133 s).
- **Écart avec M5.md.** Dans cette séance, K = 3 est de **6 % à 56 % plus lent** que les mesures de M5.md §1 à même
  configuration (`m5_noyau_derive.csv`, ligne par ligne : L2 N = 1 000, 1 fil, 25,4 s contre 19,9 s, +28 % ; L3
  N = 1 000, 4 fils, +56 % ; L4 N = 2 000, 1 fil, +22 % ; L5 N = 2 000, 4 fils, +18 % ; L6 N = 4 000, 4 fils, 133 s
  contre 118 s, +13 % ; L7 S = 8, N = 1 000, 1 fil, +10 % ; L8 4 fils, +6 %). C'est une dérive entre séances,
  plus grande que l'effet de K. Les comparaisons de ce document se font donc **à
  l'intérieur de la séance**.
- **Écriture** : sans lien avec K (3,0 à 3,5 s à N = 1 000, 11,2 à 12,6 s à N = 2 000, 52,6 à 55,1 s à N = 4 000).

### 1.2 La mémoire

| N | S × C | K = 3 | K = 20 | K = 60 | K = 60 contre K = 3 | Lignes |
|---|---|---|---|---|---|---|
| 1 000 | 2 × 6 (4 fils) | 249,2 Mo | 252,8 Mo | 259,3 Mo | +10,1 Mo (+4,0 %) | mesures L3, L5, L7 |
| 2 000 | 2 × 6 (4 fils) | 974,7 Mo | 969,2 Mo | 984,8 Mo | +10,1 Mo (+1,0 %) | mesures L9, L11, L13 |
| 4 000 | 2 × 6 (4 fils) | 3 830,5 Mo | 3 834,8 Mo | 3 875,3 Mo | +44,8 Mo (+1,2 %) | mesures L20 à L22 |
| 1 000 | 8 × 15 (4 fils) | 970,4 Mo | 978,1 Mo | 992,5 Mo | +22,1 Mo (+2,3 %) | mesures L15, L17, L19 |

(Mo = 10^6 octets ; à 1 fil les valeurs sont les mêmes à moins de 1 Mo près, sauf N = 2 000 : 970,7 ; 969,3 ;
984,3.) L'effet est une hausse de 1 à 4 % à K = 60, et pas de signal à K = 20 (variations de ±0,6 % au niveau du
bruit de mesure). La formule de `estimer_ser` (`bench/m5/extrapoler_noyau.py`, extra L2 à L10) retrouve **à l'octet près**
les 22 estimations du moteur, et celles-ci restent à moins de 1,1 % de la mémoire résidente : le terme qui grandit
avec K est celui des spectres, `16 × (colonnes_fft/2 + 1) × lignes_fft × candidates`, plus le tableau de la FFT.

## 2. La FFT de dispersion et la zone tampon, séparées (micro-mesure)

`simulate` n'écrit pas le temps de la dispersion à part. Je l'ai donc mesuré hors du moteur, par un petit programme
(`bench/m5/noyau_fft/`) qui appelle `simulate::dispersion` sans le modifier : un plan, le spectre d'un noyau, puis
une convolution sur une grille N × N (médiane de 5). La zone tampon n'a pas de coût propre en temps : elle n'existe
que dans la **taille du tableau de la FFT**, `taille_rapide(N + 2K)` de côté, et dans la mémoire de ce tableau.

| N | Fils | K | Côté de la FFT | Cellules de la zone tampon | Une convolution (s) | Spectre du noyau, une fois (s) | Ligne |
|---|---|---|---|---|---|---|---|
| 1 000 | 4 | 3 | 1 008 | 12 036 | 0,0235 | 0,037 | fft L3 |
| 1 000 | 4 | 20 | 1 050 | 81 600 | 0,0292 | 0,044 | fft L5 |
| 1 000 | 4 | 60 | 1 120 | 254 400 | 0,0315 | 0,085 | fft L7 |
| 2 000 | 1 | 3 | 2 016 | 24 036 | 0,171 | 0,104 | fft L8 |
| 2 000 | 1 | 60 | 2 160 | 494 400 | 0,202 | 0,104 | fft L12 |
| 4 000 | 4 | 3 | 4 032 | 48 036 | 0,500 | 0,434 | fft L15 |
| 4 000 | 4 | 20 | 4 050 | 321 600 | 0,503 | 0,412 | fft L17 |
| 4 000 | 4 | 60 | 4 200 | 974 400 | 0,516 | 0,433 | fft L19 |
| 4 000 | 1 | 3 | 4 032 | 48 036 | 0,787 | 0,441 | fft L14 |
| 4 000 | 1 | 60 | 4 200 | 974 400 | 0,858 | 0,514 | fft L18 |

(Les 18 lignes sont dans `m5_noyau_fft.csv`.)

- **Coût de K sur la FFT : de +3 % à +9 %** de K = 3 à K = 60 à N = 4 000 (0,500 → 0,516 s à 4 fils ; 0,787 →
  0,858 s à 1 fil), +18 % à N = 2 000, +34 % à N = 1 000 (4 fils). Il suit le carré du côté de la FFT, qui croît de
  +8,5 % à N = 4 000 (4 032 → 4 200) et de +23 % à N = 1 000 pour K = 60.
- **Le spectre du noyau est calculé une fois par essence candidate** (0,4 à 0,5 s à N = 4 000). Il croît un peu
  avec K : de 0,037 à 0,085 s à N = 1 000, 4 fils (fft L3 et L7), 0,434 à 0,433 s à N = 4 000, 4 fils (fft L15 et
  L19) ; négligeable (une fois par candidate, contre des centaines de secondes de calcul).
- **Part de la FFT dans le calcul (E)** : la boucle du niveau SER (`simulate/src/ser.rs`, 1074 à 1098) fait **une
  convolution par essence candidate et par pas annuel**, sautée si le champ de graines est entièrement nul (1087 à
  1098 : `a_disperser`). Avec 10 pas annuels et le champ non nul (la SER fictive porte des semenciers partout, non
  vérifié année par année), cela fait 10 × 2 = 20 convolutions à S = 2 et 10 × 8 = 80 à S = 8. La FFT pèse alors
  10,0 s sur 133,3 s à N = 4 000, 4 fils, K = 3 (7,5 %) et 10,3 s sur 125,3 s à K = 60 ; à S = 8, N = 1 000,
  4 fils : 1,9 s sur 65,9 s (2,9 %) et 2,5 s sur 71,0 s (3,6 %). **La dispersion est donc de 3 à 8 % du calcul.** Le
  surcoût de K = 60 vaut au plus 0,3 à 0,6 s sur ces calculs. Ce que K pourrait changer ailleurs dans le calcul n'est
  pas démontré : seules les exécutions de la section 1 le disent, sans effet visible.

## 3. Ce que K = 20 et 60 changent au verdict de M5.md §5 pour C20 (extrapolation (E))

**C'est une extrapolation à partir de ces mesures (conteneur, N ≤ 4 000, 4 fils à N = 4 000, S = 8 seulement à
N = 1 000), pas une mesure à C20 ni sur le PC de Pascal.** Elle garde les hypothèses de M5.md §4 (carré de
6 926 × 6 926, 18,30 M de cellules forestières, S = 8, C = 15, Σ A = 32, 8 candidates, 100 ans).

**Mémoire (extra L2 à L4).** La formule du moteur, qui retrouve les 22 estimations mesurées à l'octet près, donne
pour le cas de référence :

| K | Côté de la FFT (E) | Mémoire (E) | Face à 27,9 Go utilisables (31 × 0,9, hypothèse du banc, M5.md §4.2 qui l'arrondit à 28) |
|---|---|---|---|
| 3 | 7 000 | 21,49 Go | marge 6,4 Go (M5.md : 21,5 Go) |
| 20 | 7 000 | 21,49 Go | marge 6,4 Go |
| 60 | 7 056 | 21,55 Go | marge 6,35 Go |

**+63 Mo (+0,3 %) à K = 60, rien à K = 20** (le côté de 6 966 est arrondi au même 7 000 que pour K = 3).
Trois des quatre conditions de M5.md §5 (12 essences ou plus, plus de dix classes de semis, toutes les cellules)
ne bougent pas ; S = 12 passe de 30,38 à 30,46 Go (toujours non, contre 27,9 Go). **La condition du rectangle
englobant se resserre** : le cas « rectangle deux fois plus grand » passe de 27,65 Go (K = 3, sous 27,9 Go) à 27,96 Go
à K = 20 et 60 (extra L5 à L7), soit **0,06 Go au-dessus de 27,9 Go**. Il faut donc que le rectangle reste un peu
sous deux fois la SER pour K = 20 et 60 (encore à la limite à K = 3, 0,25 Go de marge). Les spectres pèsent 3,14 Go
(M5.md §4.2) à K = 3 et 3,19 Go à K = 60. **Le verdict mémoire « oui sous conditions » reste vrai** pour les trois K,
avec une condition resserrée.

**Temps (temps C20 L2 et L3).** Aucun surcoût de K n'est détectable ; je majore donc le calcul de M5.md §4.1 par
le plus grand rapport observé, 1,09 (rapports L13, sans effet établi : K joué dans l'ordre 3, 20, 60) et je laisse l'écriture et le
validateur inchangés :

| Fils | Total à K = 3, M5.md (E) | Total majoré, K = 20 ou 60 (E) | Marge sur 5 jours (432 000 s) |
|---|---|---|---|
| 1 | 137 488 s (38,2 h) | **148 089 s (41,1 h)** | 3,1 → **2,9** |
| 4 | 58 702 s (16,3 h) | **62 154 s (17,3 h)** | 7,4 → **7,0** |

Cette majoration est très prudente : la FFT n'est que de 3 à 8 % du calcul (section 2), et à C20 le tableau de la
FFT ne grossit que de 1,6 % de K = 3 à K = 60 (côté 7 000 → 7 056 ; le côté de la FFT à N = 4 000, lui, grossissait de
8,5 %). À titre de comparaison, la dérive entre séances (6 à 56 %, section 1.1 ; `m5_noyau_derive.csv`) pèse plus que K. **K = 20 et 60
ne changent pas le verdict du temps : « oui », avec une marge de 2,9 (1 fil) à 7,0 (4 fils).**

**Dit autrement.** Le coût de K, que la relecture du cycle 11 disait « non mesuré », est mesuré : au plus +1 à 4 %
de mémoire et rien de détectable en temps jusqu'à N = 4 000. Le verdict de M5.md §5 tient pour les trois valeurs de K, avec la condition du rectangle englobant resserrée.

**Une remarque pour M5b (E, non mesurée).** Le levier « découpage en blocs » de M5.md §6 suppose une couronne de
3 cellules à échanger entre blocs. Avec K = 60, cette couronne vaut 60 cellules (1,5 km) : pour 4 blocs de 3 463 de
côté, le tableau de chaque bloc gagne (3 583 / 3 463)² − 1 = +7 %, au lieu de +0,35 % ((3 469 / 3 463)² − 1). Le levier reste valable, un
peu moins économe.

## 4. Limites

- Une répétition par exécution de `simulate`, et K joué dans l'ordre 3, 20, 60 sans alternance : l'effet de K ne se
  sépare pas d'une dérive dans le temps. Le bruit d'une exécution n'a pas été mesuré (pas de répétition). La micro-mesure de la FFT (médiane de 5) est plus fiable.
- N = 4 000 n'est mesuré qu'à 4 fils, et S = 8, C = 15 qu'à N = 1 000.
- La part de la FFT (section 2) compte 10 pas annuels à champ de graines non nul ; le temps de la dispersion n'est pas écrit par `simulate`.
- Les paramètres du noyau sont d'essai (d99 = 0,99 × K × 25 m, forme 1). Un noyau réel de classe 5 ou 6 de Lososová
  a d'autres a et b, mais ni la taille du tableau de la FFT ni le nombre de convolutions n'en dépendent : seul K
  compte pour le coût. La répartition des graines change les valeurs mises à zéro (règle |Q|), non mesurées ici.
- La SER fictive est forestière à 100 % (comme en M5.md) ; l'extrapolation du temps à C20 est une borne haute.
- Les mesures de ce document datent d'une seule séance, de 6 à 56 % plus lente que celle de M5.md (`m5_noyau_derive.csv`).
