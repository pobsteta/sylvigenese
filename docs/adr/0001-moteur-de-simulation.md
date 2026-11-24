# ADR 0001 — langage du moteur de simulation (`simulate`)

- **Date :** 2026-11-24
- **Statut :** proposée
- **Proposée par :** Claude (orchestrateur), à la demande de Pascal
- **Tranchée par :** Pascal (à trancher)

## La décision en une phrase

Proposition : le module `simulate` devient un exécutable **Rust** autonome
(`sylvigenese-sim run config.yml`), qui lit et écrit les contrats de `data/<zone>/`
(parquet, GeoTIFF). Avant l'adoption, un **banc d'essai** à l'échelle d'une SER le compare à
un prototype Python, sur les mêmes contrats.

## Contexte

**Pourquoi décider maintenant.** Le brief (§3, §8) prévoit GAMA, avec un repli en R ou en
Python « si GAMA ne tient pas la charge au niveau SER ». Le 24/11/2026, Pascal a demandé de
comparer **Python, R et Rust**, et a posé trois exigences :

1. traiter des **SER entières** ;
2. avec **spatialisation**. Cela corrige l'orchestrateur, qui avait dit le contraire en
   s'appuyant sur la « concurrence non spatialisée » de BRIEF §6. Ce passage ne décrit que
   la limite des modèles ajustés sur l'IFN, dont les placettes ont des coordonnées
   floutées. La simulation, elle, reste spatiale : dispersion des graines depuis les
   semenciers voisins (§7.1), lumière sous le couvert des cellules voisines (§7.3),
   concurrence arbre à arbre au niveau massif, transitions entre stations voisines (§5) ;
3. la **rapidité** et la **robustesse** comptent par-dessus tout.

Le moteur conditionne M3 et M5. Le choisir après M0 obligerait à réécrire le squelette.

**Ordre de grandeur, à vérifier par l'`acquereur`.** La France métropolitaine compte
86 SER (IGN). Sa surface d'environ 550 000 km² donne une SER moyenne d'environ
6 400 km² ; les SER réelles varient beaucoup autour de cette moyenne. Sur la grille de
`config.yml` :
- à 25 m (625 m² par cellule), une SER moyenne fait environ 10 millions de cellules ;
- à 10 m, elle en fait environ 64 millions.

On multiplie ensuite par le taux de boisement de la SER, par le nombre d'essences en
cohortes et par 100 pas annuels. Le calcul de voisinage (noyau de dispersion, ombrage)
s'applique à chaque pas, sur toute la grille.

**Options envisagées.**

| | A. R | B. Python | C. Rust | D. cœur C++ ou Rust dans un paquet R (Rcpp, extendr) | E. GAMA (brief actuel) | F. Capsis |
|---|---|---|---|---|---|---|
| Vitesse sur grille et voisinage | bonne si tout passe par `terra` (C++) ; une boucle annuelle en R pur est lente | bonne avec numpy, scipy.ndimage, numba ; le code hors noyau compilé reste lent | native, avec parallélisme sûr (rayon) | native pour le cœur | inconnue à l'échelle SER ; le brief en doute | inconnue à l'échelle SER |
| Robustesse | typage dynamique ; erreurs à l'exécution | typage dynamique (annotations non contraignantes) | typage statique, pas de pointeur nul, pas de course de données à la compilation, erreurs explicites (`Result`) | cœur robuste, interface R dynamique | JVM, typage partiel du GAML | Java, typage statique |
| Spatial (raster, vecteur, EPSG:2154) | le plus riche : `terra`, `sf`, `lidR` | riche : rasterio, geopandas, pyproj | plus jeune : `gdal` (liaison à GDAL), `geo`, `proj`, `ndarray` | celui de R | lecture SIG native | limitée |
| Parquet | `arrow` | `pyarrow`, `polars` | `arrow`, `parquet`, `polars` (natifs) | celui de R | non natif (conversion) | non natif |
| Cohérence avec l'existant | `nemeton`, `sylvostation`, `prepare`, `dynamics` sont en R | `assets` (`synth_arbres.py`) | rien d'existant | R | rien | communauté forestière, RReShar |
| Test du successeur | lu par les forestiers modélisateurs | très répandu | peu répandu chez les forestiers | deux langages à tenir | GAML de niche | Java, charte |

E et F restent écartés comme **moteurs** : E par le doute du brief lui-même et sa lecture
non native du parquet, F parce que ses modules appartiennent à leurs auteurs et suivent une
charte, alors que nos modèles sont ajustés par nous. Capsis reste une **référence de
validation** possible pour M3 et M5.

**Pourquoi C plutôt que D.** Les modules ne se parlent que par fichiers (BRIEF §0.2). Un
exécutable autonome respecte ce contrat sans lier le moteur à une session R. D reste le
meilleur second choix si Pascal veut que `simulate` se lance depuis le pipeline `targets`.
`targets` peut de toute façon appeler un exécutable.

**Le banc d'essai (condition de l'adoption).** On génère une grille synthétique à la taille
d'une SER, avec un noyau de dispersion, un ombrage de voisinage et une croissance bornée par
le plafond de station, sur 100 pas, à graine fixée. On l'écrit en Rust et en Python (numpy
et numba), et on mesure :
- le temps total ;
- la mémoire maximale ;
- l'identité des sorties à graine égale ;
- le comportement sur des entrées invalides (erreur explicite attendue, jamais une valeur
  silencieuse, BRIEF §0.6).

Le seuil d'écart qui justifie Rust est **à fixer par Pascal** avant la mesure.

## Le crible FRANCE

| Lettre | Question | Réponse (une ligne) | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|---|
| **F**rugale | La solution la plus simple qui tienne ? | un exécutable, un `config.yml`, des fichiers ouverts en entrée et en sortie | un langage de plus dans le dépôt (R, Python, Rust, TypeScript, GDScript) | à trancher par Pascal |
| **R**esponsable | Qui fait quoi, avec quels moyens ? | les agents `dev` et `testeur` écrivent le moteur ; Pascal relit les PR | Pascal relit du Rust, qu'il pratique moins que R | à trancher par Pascal |
| **A**nticiper | Si l'imprévu arrive ? De quoi dépend-on ? | les contrats de fichiers rendent le moteur remplaçable ; dépendance à GDAL et PROJ par liaison | les liaisons GDAL en Rust sont moins éprouvées que `terra` et rasterio | à trancher par Pascal |
| **N**ovateur | Toutes les idées écoutées ? | six options, dont GAMA, Capsis et un cœur dans R | — | — |
| **C**oût | Que coûte la décision à l'ensemble ? | écriture plus lente au départ que Python ; le banc d'essai coûte une mission | du temps avant M3 | à trancher par Pascal |
| **É**cologique | Que réutilise-t-on, qui réutilisera ? | Rust réutilise peu de l'existant forestier ; l'exécutable sous GPL-3 est réutilisable par `nemeton` et par d'autres | les modèles R de `dynamics` ne sont pas réutilisés tels quels : leurs coefficients passent par `params/` | à trancher par Pascal |

## Valeurs sacrifiées

- **La continuité avec l'écosystème R** (`nemeton`, `sylvostation`) : sacrifiée pour le
  cœur seulement, au profit de la vitesse et de la robustesse, que Pascal place au premier
  rang. `prepare`, `biomes` et `dynamics` restent en R.
- **La lisibilité par un forestier modélisateur** (test du successeur) : en partie
  sacrifiée. Contrepartie : le moteur ne contient aucun coefficient (BRIEF §8), et tout le
  savoir écologique reste lisible dans `params/` et `biomes/`.

## Sources

- BRIEF §0.2, §0.6, §3, §5, §6, §7, §8 (Pascal Obstétar, 24/11/2026).
- Demande de Pascal du 24/11/2026 (SER entières, spatialisation, rapidité, robustesse) :
  `pilotage/journal.md`.
- IGN, Inventaire forestier : les 86 sylvoécorégions (à citer précisément : `acquereur`).
- Capsis, noyau sous LGPL, modules à leurs auteurs selon une charte :
  [HAL hal-00930711](https://hal.archives-ouvertes.fr/hal-00930711),
  [modèles Capsis](https://capsis.cirad.fr/capsis/models).
- GAMA, mode sans interface et optimisation :
  [Running Headless](https://gama-platform.org/wiki/next/RunningHeadless),
  [Optimizing Models](https://gama-platform.org/wiki/next/OptimizingModels).
- Les propriétés de Rust (typage, absence de course de données, `Result`) : *The Rust
  Programming Language*, chapitres 9 et 16 (à citer par le `contradicteur`).

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
