# ADR 0006 — le niveau SER : des cohortes d'adultes en classes de diamètre fixes, en f32, sur les cellules forestières

- **Date :** 2026-11-26
- **Statut :** proposée (à trancher par l'orchestrateur, par délégation de Pascal ; Pascal peut la défaire)
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
   « en régime » (Q2) ; survie par la lumière sous couvert et la tolérance à l'ombre seules (Q3) ; passage
   à 7,5 cm calé sur le flux IFN, borné par le stock (Q1) ; le manque est compté (`seedling_stock_limited`).
7. **Dispersion (T2).** FFT réelle, essence par essence, sur toute la grille, zone tampon comprise
   (largeur du noyau tronqué, `simulate.regeneration.kernel_truncation_cells`) ; la zone tampon est source
   de graines seulement, son bord est absorbant (spec §7). Le noyau est normalisé (somme 1 à 1e-12).
   Forme du noyau fixée au contrat `params/regeneration` : exponentielle-puissance
   k(r) ∝ exp(−(r / a)^b), a et b étant des paramètres par essence, **sans valeur** (à sourcer, mission
   059). Cette forme est la seule hypothèse de modèle que le contrat porte : si le référentiel de la
   mission 059 ne publie qu'une autre forme (par ex. 2Dt), le contrat change avant le code.
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

## Conséquences

- **Mémoire à C20 (risque n° 1, plan §6).** 4 octets × S × K par cellule forestière : avec S = 8 essences
  et K = 15 classes, 480 octets par cellule, soit environ 23 Go si les 48 millions de cellules étaient
  toutes forestières, pour 28 Go utilisables. Le taux de boisement de C20 n'est pas connu du dépôt. Les
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
  `cohorts`.

## Réversibilité

Changer K ou w : `config.yml` seul. Changer la forme des classes (option c) : nouveau contrat
`sim.cohorts`, donc nouvelle ADR. Revenir au niveau massif seul : `simulate.level: massif` n'est pas
touché.
