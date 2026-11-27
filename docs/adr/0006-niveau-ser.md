# ADR 0006 — le niveau SER : des cohortes d'adultes en classes de diamètre fixes, en f32, sur les cellules forestières

- **Date :** 2026-11-26
- **Statut :** acceptée le 26/11/2026 par l'orchestrateur, par délégation de Pascal (choix 12 confirmé par Pascal le même jour) ; Pascal peut la défaire
- **Proposée par :** `dev` de la mission 060 (plan `docs/plans/m5a.md`, §3 et §4, choix T1, T2, T4, T7 et T8)
- **Tranchée par :** — (en attente)

## La décision en une phrase

Au niveau SER, il n'y a pas d'arbres individuels : chaque cellule **forestière** porte, par essence,
un vecteur de **K classes de diamètre fixes** (densités de tiges en **f32**, dernière classe ouverte),
qu'on fait avancer en **espérance** (sans tirage) par une matrice de transfert entre classes ; les
semis sont des cohortes à part, et la dispersion des graines se fait par FFT. Les formats sont fixés
par les contrats `cohorts_init`, `sim.cohorts`, `params/regeneration`, `config` (blocs `ser` et
`regeneration`) et `run` (mission 060).

## Contexte

- Le BRIEF §3 pose les cohortes au niveau SER « sans leur forme » ; aucune ADR n'en décide. Le BRIEF §11
  attend « une SER fictive simulée ; recrutement calé sur le modèle IFN » ; la spec §11 chiffre la mesure
  (N = 1 000, 2 000, 4 000) et l'estimation de mémoire à moins de 10 % de la mémoire résidente.
- Le modèle d'accroissement de l'IFN prend `bal`, la surface terrière des arbres plus gros que l'arbre
  considéré (`dynamics_params`, variable `bal`). Le niveau SER doit donc en garder une trace.
- Décisions de Pascal du 26/11/2026 : Q1 (passage à la futaie : flux du modèle IFN sous couvert, borné
  par le stock de semis), Q2 (stock initial de semis « en régime », déduit, provisoire), Q3 (lumière et
  ombre seules ; gibier, sous-bois et fructification non simulés), Q4 (deux modes, `ifn_direct` et
  `cohorts`, même module de semis pour les deux niveaux), Q5 (clôture sur la mesure, l'extrapolation et
  l'estimation de mémoire).
- Décisions de l'orchestrateur du 26/11/2026 (par délégation), prises au fil des missions 062 et 063 et
  rattrapées ici par la mission 066 : voir les choix 11 à 16.
- Cible du projet : la SER C20 (48 millions de cellules de 25 m, N équivalent ≈ 6 930) en 5 jours et
  31 Go sur le PC de Pascal (28 Go utilisables).

## Options pesées : la forme des adultes (T1)

| Option | Pour | Contre |
|---|---|---|
| (a) **Une cohorte moyenne par essence** : 2 valeurs (tiges, d moyen) | mémoire minimale (≈ 8 octets par essence et cellule) | `bal` n'existe plus : il faudrait l'inventer (ce que le projet s'interdit) ; la distribution des diamètres, donc la mortalité et le passage, est perdue |
| (b) **Classes de diamètre fixes, K par essence** (**proposée**) | `bal` exact à la résolution d'une classe ; mémoire connue d'avance (4 × S × K octets par cellule forestière) ; transfert entre classes simple (matrice d'Usher) ; état initial lisible (`cohorts_init`) | largeur et nombre des classes sont des réglages qui changent les résultats (erreur de discrétisation à dire au rapport) ; mémoire élevée à C20 (voir Conséquences) |
| (c) **Liste de cohortes de longueur variable** | fidèle à la structure réelle | mémoire imprévisible, donc estimation à 10 % invérifiable ; écriture et identité entre fils plus fragiles |

## Choix retenus

1. **Classes fixes.** Le rang `d_class` de 0 à K − 1 (K = `simulate.ser.diameter_classes`) ; la classe
   k couvre [d_min + k·w, d_min + (k + 1)·w[ cm avec d_min = 7,48 cm (C13 = 0,235 m, seuil du modèle de
   recrutement) et w = `simulate.ser.diameter_class_width_cm` ; la dernière classe est ouverte.
   Largeur et nombre sont dans `config.yml`, jamais dans le code.
2. **Transfert entre classes.** Une fraction Δd / w de la classe passe à la suivante (Δd : accroissement
   du modèle IFN pris au centre de la classe) ; les tiges sont conservées dans le transfert, la mortalité
   les retire, le recrutement les ajoute à la classe 0.
3. **f32.** Les densités sont en f32 (la moitié de la mémoire de f64) ; les sommes (surface terrière,
   `bal`, flux) sont faites en f64. Le contrat `sim.cohorts` est de type nombre : il accepte f32.
4. **Cellules forestières seules.** Une cellule non forestière n'a ni classes ni ligne dans
   `cohorts_init` ni dans `sim.cohorts`. Le moteur indexe les cellules forestières de façon dense.
5. **Espérances, sans tirage (T4).** L'accroissement, la mortalité (N × p) et le passage sont calculés
   en espérance au niveau SER : une classe est une densité, un tirage ajouterait du bruit sans
   information, et le test du calage de Q1 est ainsi exact. Au niveau massif, la mort tirée et l'arrondi
   aléatoire des recrues sont gardés (décision de Pascal du 25/11/2026).
6. **Semis.** Cohortes de semis par cellule et essence (densité, hauteur) aux deux niveaux ; état initial
   « en régime » (Q2) ; survie par la lumière sous couvert et la tolérance à l'ombre seules (Q3, forme
   précisée au choix 13) ; passage à 7,5 cm calé sur le flux IFN, borné par le stock (Q1) ; le manque est
   compté (`seedling_stock_limited`). Le stock initial est l'état stationnaire de la dynamique des classes
   annuelles à la survie de la cellule (reprise de la mission 062), signalé au rapport comme déduit des
   modèles et non observé.
7. **Dispersion (T2).** FFT réelle, essence par essence, sur toute la grille, zone tampon comprise
   (largeur du noyau tronqué, `simulate.regeneration.kernel_truncation_cells`) ; la zone tampon est source
   de graines seulement, son bord est absorbant (spec §7). Le noyau est normalisé (somme 1 à 1e-12).
   Forme du noyau fixée au contrat `params/regeneration` : exponentielle-puissance
   k(r) ∝ exp(−(r / a)^b), a et b étant des paramètres par essence, **sans valeur dans le contrat**. Les
   valeurs se dérivent des deux distances de la classe de dispersion de l'essence dans Lososová et al.
   2023 (tableau 1, p. 1488 : d50 et d99, distances contenant 50 % et 99 % des graines) : en deux
   dimensions, la part des graines tombées à moins de r est P(2 / b, (r / a)^b) (gamma incomplète
   régularisée), et a, b résolvent P(2 / b, (d50 / a)^b) = 0,5 et P(2 / b, (d99 / a)^b) = 0,99 (décision de
   l'orchestrateur du 26/11/2026, mission 062). Cette dérivation est marquée `provisoire` avec la classe et
   les deux distances en source ; une essence sans classe lue n'a pas de noyau (code 2).
   **K couvre d99** (décision de Pascal du 27/11/2026, mission 080) : `simulate` refuse (code 2, message
   nommé avec l'essence, son d99 et le K demandé), aux deux niveaux, un `kernel_truncation_cells` tel que
   K × 25 m < d99 pour une essence présente, d99 étant recalculé exactement de `kernel_scale_m` et
   `kernel_shape` (rayon où P(2 / b, (r / a)^b) = 0,99) ; la renormalisation ne déplace ainsi au plus que 1 %
   des graines. Aucun terme de plus au contrat.
   Convolution directe écartée : environ 4 jours à C20 pour 8 essences.
8. **Règle |Q| (T3).** Mise à zéro symétrique de |Q| < `zero_threshold` × max|Q| par (essence, année),
   comptée dans `zeroed_values` ; une valeur négative au-delà du seuil arrête le moteur (code 3).
9. **Sorties (T8).** Pas de `sim/trees` au niveau SER. `sim/cells` et `sim/cohorts` sont écrits à t0,
   tous les `simulate.ser.write_step` ans et à la dernière année ; les autres années n'existent pas et
   ne sont jamais interpolées. À N = 4 000, une année de `sim/cells` fait environ 50 millions de lignes.
10. **Mémoire (T7).** `run.json` porte `memory_estimate_max_bytes` (la plus grande estimation faite
    avant les pas) et `memory_peak_rss_bytes` (`VmHWM`, `null` hors de Linux, jamais deviné). L'estimation
    est une formule fermée (classes, semis, couches f64, tampons de FFT, tampon d'écriture) plus une part
    fixe du programme mesurée et écrite avec sa mesure.

11. **Maturité en hauteur (mission 062).** Un arbre est semencier quand sa hauteur atteint
    `maturity_height_m`, comme le paramètre de hauteur de maturité de TreeMig (éq. 13, p. 9 de
    TreeMigDocu_251218_Model.pdf). Le terme `maturity_d130_cm` de la version 0.1 du contrat est retiré, sans
    conversion du diamètre en hauteur (une conversion serait une dérivation non sourcée) : contrat en 0.2.
12. **Refus de `ifn_direct` au niveau SER (mission 063).** Le niveau SER avance des espérances sans tirage (choix 5), alors que
    le recrutement direct du modèle IFN (`ifn_direct`) arrondit au hasard des arbres entiers : `simulate.recruitment:
    ifn_direct` avec `level: ser` est refusé, code 2 ; motif confirmé par Pascal le 26/11/2026 : à cette échelle il n'y a pas d'arbres suivis un par un, donc rien à quoi appliquer un recrutement d'arbres entiers ; `ifn_direct` reste au massif, avec la référence de M3a (Q4). Le niveau SER n'a que le mode `cohorts`.
13. **Survie des semis, forme de TreeMig (mission 062, terme ajouté en 066, ombre reprise en 084b).** Lumière
    relative de la cellule l = exp(−k × couvert projeté), k = `light_extinction_coef` (provisoire) ; le couvert
    projeté (surface des houppiers projetés sur surface de la cellule) tient la place de l'indice foliaire de
    TreeMig (décision de Pascal du 27/11/2026, provisoire, dite au rapport). La lumière est rangée dans
    `light_class_count` classes de largeur égale sur [0, 1] (10 ; décision de Pascal du 27/11/2026, provisoire et
    sans source : TreeMig n'imprime pas ses bornes). Seuil de lumière par essence : la tolérance de Niinemets et
    Valladares 2006 (`shade_tolerance`, 0 à 5) donne klighs par la droite de la mission 083, klighs = borné entre
    `klighs_min` et `klighs_max` de `klighs_intercept` + `klighs_per_shade_tolerance` × N (provisoire, erreur
    ± 1,1 classe, `docs/referentiels/regeneration.md` §15), puis la loi de TreeMig (TreeMigDocu p. 14, après
    l'éq. 29) : seuil = `light_threshold_high_slope` × klighs + `light_threshold_high_intercept` si klighs ≥
    `light_threshold_klighs_break`, sinon max(0, `light_threshold_low_slope` × (klighs −
    `light_threshold_low_klighs_origin`)). Part d'une classe [l_low, l_up] sous le seuil (éq. 39, p. 16) : 0 si
    l_low > seuil, 1 si l_up < seuil, (seuil − l_low) / (l_up − l_low) sinon ; mortalité de stress de la classe
    = `stress_mortality` × part (éq. 40) ; mortalité de la cellule = moyenne des classes pondérée par la part de la
    lumière de la cellule dans chaque classe ; survie s = max(0, `seedling_survival_full_light_yr` − mortalité de
    stress) (éq. 37). **Une seule lumière par cellule** : TreeMig répartit la lumière d'une cellule sur les classes
    par une loi (normale de l'indice foliaire) que le dépôt n'a pas ; avec une seule valeur l, la part est 1 pour
    la classe qui contient l et 0 ailleurs (une borne va à la classe du dessus, l = 1 à la dernière), et la
    fraction de l'éq. 39 ne joue que dans la classe qui contient l, si le seuil y tombe : c'est la forme publiée
    appliquée à notre lumière unique, non une répartition inventée. Une répartition plus riche est une question de
    sens pour Pascal, non décidée. Les dix termes nouveaux (constantes de la correspondance, de la loi, bornes de
    klighs, nombre de classes) sont des termes de `params/regeneration` (contrat 0.4), cherchés comme les autres à
    l'essence, au groupe, puis dans `toutes_essences` : aucun dans le code, absent = code 2 ; nombre de classes
    non entier, `klighs_min` > `klighs_max`, seuil hors de 0 à 1 = code 2. `stress_mortality` (0,184, éq. 40) est
    un terme du contrat depuis la version 0.3 (décision de Pascal du 26/11/2026). Mode `cohorts` : `flags.parquet`
    porte aussi le signalement `classes_lumiere_et_extinction_provisoires`, qui dit les réglages provisoires et
    sans source. Les résultats `cohorts` ont changé avec 084b (nouvelle référence
    `tests/m5/reference/cohorts_ombre_treemig.json`) ; `ifn_direct` est inchangé (`tests/m3/reference/nominal.json`).
14. **Essences candidates prises dans `cohorts_init` (mission 063).** Au niveau SER, les essences simulées
    sont celles de `cohorts_init` ; parmi elles, sont candidates au recrutement celles qui ont les quatre jeux
    de paramètres (T6). Une essence qui n'a que des lignes propres dans `params/` sans cohorte dans la SER
    n'est pas candidate : sans adulte, elle n'aurait ni semenciers ni graines.
15. **Validateur sobre (mission 063).** Au niveau SER, `simulate` appelle le validateur avec le pool mémoire
    d'Arrow du système et un seul fil de calcul : environ 140 Mio au lieu de 240 à 270 Mio à N = 1 000, pour
    10 à 20 % de durée en plus, sans effet sur ses verdicts. Le validateur est un enfant de `simulate` : sa
    mémoire compte dans la mémoire résidente mesurée.
16. **`malloc_trim` (mission 063).** Après l'écriture de t0 et de chaque année écrite, `simulate` appelle
    `malloc_trim(0)` de la glibc (seul bloc `unsafe`, commenté, Linux et glibc seulement) pour rendre au
    système la mémoire libérée : sans lui, la mémoire résidente dépasse l'estimation d'environ 40 Mio à
    N = 1 000. Sans effet sur les résultats ; hors de la glibc, l'estimation peut être sous la mémoire
    résidente.

## Conséquences

- **Mémoire à C20 (risque n° 1, plan §6).** 4 octets × S × K par cellule forestière : avec S = 8 essences
  et K = 15 classes, 480 octets par cellule, soit environ 23 Go si les 48 millions de cellules étaient
  toutes forestières, pour 28 Go utilisables. Le taux de boisement de C20 est de 38 % (`docs/referentiels/surfaces-ser.csv` : 11 440 km² de
  surface boisée sur 29 980 km²), soit environ 18,3 millions de cellules forestières et, à 480 octets,
  environ 8,8 Go pour les seules classes ; environ 21,5 Go au total estimés (cas de référence S = 8, K = 15,
  Σ A = 32, cellules forestières seules, carré : `bench/results/M5.md` §4 ; la mesure et l'extrapolation sont dans `bench/results/M5.md`). Les
  leviers, chiffrés par la mission F (064) : moins de classes, essences regroupées, cellules forestières
  seules (déjà retenu), découpage de la SER en blocs. Un verdict négatif est porté à Pascal avant M5b
  (Q5).
- **Deux chemins de recrutement** (`ifn_direct`, `cohorts`) à tester tous les deux ; `nominal.json` de
  M3a reste la référence de `ifn_direct`, `cohorts` aura la sienne, « technique, non validée
  écologiquement ».
- **Rétrocompatibilité.** `recruitment` n'est pas imposé par le schéma de `config.yml` (les configs de
  M3a restent conformes) : c'est `simulate` qui s'arrête (code 2) sans lui. Les clés de `run.json` propres
  à M5a ne sont exigées que si `recruitment` y figure ; un `run.json` de M3a reste conforme.
- **Ce que le validateur ne contrôle pas** (règles entre fichiers, tenues par les tests et le moteur) :
  `d_class` < K ; `cell_id` dans la grille et forestier ; colonnes de semis de `sim/cells` présentes si et
  seulement si `run.json` dit `cohorts` ; années de `sim/cohorts` = suite de `write_step` ; termes de
  `params/regeneration` lus par le moteur présents pour chaque essence (code 2 sinon).
- **`post` et `assets`** ne lisent pas le niveau SER : ils le refusent (code 2) jusqu'à M5b.
- La mention « gibier, sous-bois et fructification non simulés » est écrite dans `run.json`
  (`not_simulated`), le rapport et la fiche ; la mention « semis non simulés » ne l'est plus en mode
  `cohorts`. En mode `cohorts`, `sim/flags.parquet` porte aussi, à t0, `stock_initial_en_regime` (Q2) et
  `lumiere_et_ombre_seules` (Q3) ; la note de l'index des tuiles (`assets`) dit les semis simulés, techniques
  et non validés, et non « semis non simulés » (mission 066).

## Réversibilité

Changer K ou w : `config.yml` seul. Changer la forme des classes (option c) : nouveau contrat
`sim.cohorts`, donc nouvelle ADR. Revenir au niveau massif seul : `simulate.level: massif` n'est pas
touché.
