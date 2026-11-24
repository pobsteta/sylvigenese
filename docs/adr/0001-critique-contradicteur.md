# Critique de l'ADR 0001 par le `contradicteur` (24/11/2026)

> Rendue le 24/11/2026. Recopiée ici sans adoucissement pour que la trace reste dans le
> dépôt. Les arbitrages sont à rendre par Pascal et seront reportés dans l'ADR.

**Question de contrôle du contradicteur.** Quel problème résout-on, et pour qui : simuler une
SER entière, sur quelle machine, en combien de temps, et au bénéfice de quel lecteur ?

## Bloquant

**B1. Pas de cible chiffrée ; l'ADR contredit le BRIEF sans l'amender.**
- Le seul chiffre du brief (§0.5, moins de 30 min sur un portable) vaut pour le massif test.
  Rien n'est fixé pour une SER : ni machine, ni temps, ni mémoire. Un écart relatif entre
  langages ne dit pas si l'un d'eux tient le besoin.
- Il faudrait amender §3, §8, §12 et §13 du brief (GAMA, `gama/`, scénario GAMA, licence
  « cohérente avec GAMA »).
- §2 exclut l'arbre à arbre à l'échelle SER. La spatialisation n'est donc pas la même aux
  deux niveaux : arbres au massif, cohortes par cellule à la SER.

*Proposition :* une section « Exigences mesurables » à trancher par Pascal (temps cible
pour la plus grande SER à 10 m et à 25 m, machine de référence, mémoire maximale, nombre
d'essences et de variables par cohorte) et une section « Amendements au BRIEF ».

**B2. Ordre de grandeur sous-dimensionné : c'est la mémoire qui limite.**
- Il y a 86 SER, plus 5 SER d'alluvions récentes publiées par l'IGN dans une couche à part.
- C'est la plus grande SER qui dimensionne, pas la moyenne. Le boisement va jusqu'à 75 % dans
  les Landes de Gascogne, et six SER dépassent 70 %.
- La dispersion des graines traverse les cellules non boisées et la frontière de la SER. Il
  faut donc une zone tampon de la largeur du noyau, avec une règle de bord explicite.
- Estimation non sourcée du contradicteur : une SER moyenne à 10 m, avec 15 essences, 4
  variables et des valeurs sur 4 octets, pèse environ 15 Go pour l'état seul. C'est hors de
  portée d'un portable, quel que soit le langage.
- LANDIS PRO tient 10^8 cellules grâce à sa structure de données, pas grâce à son langage
  (Yang et al. 2011).

*Proposition :* l'`acquereur` établit la surface réelle des SER. L'ADR ajoute un budget
mémoire, la zone tampon, un traitement par tuiles avec recouvrement, et choisit la
structure de données avant le langage.

**B3. Banc d'essai inéquitable et insuffisant.**
- R n'y figure pas.
- L'algorithme pèse plus que le langage : une convolution directe coûte O(N·K²), une
  convolution par FFT O(N log N).
- « Identité à graine égale » entre langages est impossible, car les générateurs aléatoires
  diffèrent. Il faut deux critères : identité au bit près dans un même langage, à 1 et à N
  fils ; équivalence statistique d'un langage à l'autre.
- Il manque le niveau massif arbre à arbre, les entrées-sorties, la mémoire par tuile et le
  coût de relecture pour Pascal.
- Les prototypes sont écrits par des agents : leur qualité dépend de la familiarité de
  l'agent avec chaque langage.

*Proposition :* un banc à trois langages, au même algorithme imposé, en deux tailles
(massif test sur portable, plus grande SER sur la machine de référence), avec une relecture
croisée.

## Important

**I1. On s'apprête à réinventer un simulateur de paysage.** Plusieurs moteurs publiés
couvrent nos deux niveaux :
- **TreeMig** (WSL) : cohortes par cellule, banque de graines, dispersion ; cœur Fortran
  piloté par un paquet R.
- **LANDIS-II** (C#, code ouvert) : cohortes et dispersion ; l'extension Density Succession
  suit tiges et DBH.
- **iLand** (C++, GPL-3) : arbre à arbre, champ de lumière ; jusqu'à environ 10^5 ha.
- **SORTIE-ND** : cœur C++ avec une interface R.

Aucun simulateur forestier de paysage établi n'est écrit en Rust. Le schéma dominant du
domaine est un cœur compilé piloté depuis R.

*Proposition :* une option G, « réutiliser ou adapter », à évaluer avant d'écrire le moteur,
au moins comme référence de validation.

**I2. « Pas de course de données » ne veut pas dire « déterministe ».**
- Avec `rayon`, l'ordre des réductions flottantes n'est pas fixe.
- Le générateur aléatoire de numba n'a pas de garantie de reproductibilité par fil.
- En Rust, un dépassement d'entier boucle en silence en mode release.
- Les NaN se propagent en silence dans les trois langages.

*Proposition :* un générateur à compteur adressé par (graine, année, cellule, essence), des
réductions par blocs dans un ordre fixe, un test au bit près à 1 et à N fils,
`overflow-checks = true`, et un contrôle des NaN et des bornes à chaque pas.

**I3. GDAL et PROJ sont inutiles au moteur.** La grille est déjà alignée en EPSG:2154 par
`prepare`. En Rust, le crate `gdal` se lie à une GDAL système, ce qui nuit à la portabilité.

*Proposition :* écrire « `simulate` ne reprojette pas », et lire les rasters par un lecteur
GeoTIFF sans GDAL ou par un contrat raster simple.

**I4. Contradictions internes et jalons.**
- « Réécrire le squelette après M0 » contredit « contrats remplaçables ».
- Un banc à l'échelle SER avant M0 anticipe M5 : il ne peut être qu'une exploration jetable.
- Pascal relit moins bien le Rust : sans contrepartie, la porte n° 3 risque de devenir une
  validation de forme.

*Proposition :* retirer l'argument du squelette, qualifier le banc de jetable, et demander
soit un relecteur Rust compétent, soit une règle de lisibilité.

**I5. Voisinage équivalent à la placette IFN non défini.** C'est un choix écologique, qui
fixe le rayon de voisinage et donc le coût de calcul. *Proposition :* l'ajouter aux questions
ouvertes du BRIEF §14.

## Mineur

- **M1.** Écarter GAMA par l'argument sourcé : selon sa documentation, une grille de
  20 000 × 20 000 à 10 attributs dépasse 32 Go.
- **M2.** Python : citer xarray et dask (`map_overlap`).
- **M3.** extendr sur CRAN : crates à embarquer ; Rcpp est plus éprouvé.
- **M4.** Dire pourquoi Rust plutôt que C++, choix majoritaire du domaine.
- **M5.** Préciser la ligne « Écologique » du crible FRANCE.
- **M6.** Citer le Rust Book (chapitres 3.2, 9 et 16) avec ses adresses.

## Lecture comparative du contradicteur (jugement, non sourcé)

Ne pas trancher le langage avant trois préalables :
1. une cible mesurable et un budget mémoire de la plus grande SER ;
2. une mission courte de réutilisation (TreeMig pour la SER, iLand pour le massif) ;
3. le banc à trois langages, au même algorithme.

S'il faut développer : un cœur Rust autonome sans GDAL ni PROJ, avec un générateur à compteur
et des réductions déterministes, une fine enveloppe R pour `targets`, et un prototype Python à
petite échelle comme oracle de test. L'argument en faveur de Rust est la maîtrise de la
mémoire et le typage statique, pas la vitesse brute face à numba.

## Non vérifié par le contradicteur

- La surface de chaque SER.
- La documentation officielle de `rayon` et de numba (bloquée par le réseau de la session).
- La licence de TreeMig.
- Le langage de LANDIS PRO.
- Les temps de calcul publiés d'iLand et de TreeMig.
- Le mode `bundled` de `gdal-sys`.
- Les wheels de rasterio.
- Les rayons des placettes IFN.
- L'estimation mémoire d'environ 15 Go.

## Sources citées

- [Sylvoécorégions](https://www.data.gouv.fr/datasets/sylvoecoregions) et [SER d'alluvions récentes](https://www.data.gouv.fr/datasets/sylvoecoregions-dalluvions-recentes) (IGN)
- [Memento IFN 2016](https://ofme.org/documents/actualite/201611/161122_memento2016.pdf) ; [DRAAF Nouvelle-Aquitaine](https://agriculture.gouv.fr/telecharger/122281)
- [Yang et al. 2011, LANDIS PRO](https://research.fs.usda.gov/treesearch/39520)
- [LANDIS-II](https://www.landis-ii.org/developers) ; [Density Succession](https://landis-ii-foundation.github.io/Extension-Density-Succession)
- [TreeMig](https://treemig.wsl.ch/en/core-model/)
- [iLand, Rammer et al. 2024](https://portal.fis.tum.de/en/publications/the-individual-based-forest-landscape-and-disturbance-model-iland/)
- [SORTIE-ND](https://bvcentre.ca/forest-dynamics-program/sortie/) ; [necsim-rust](https://github.com/juntyr/necsim-rust)
- [GAMA, Optimizing Models](https://gama-platform.org/wiki/next/OptimizingModels)
- [terra::focal](https://search.r-project.org/CRAN/refmans/terra/html/focal.html) ; [fastfocal](https://ftp.fau.de/cran/web/packages/fastfocal/readme/README.html)
- [NumPy, parallel RNG](https://numpy.org/devdocs/reference/random/parallel.html) ; [numba-users](https://groups.google.com/a/continuum.io/g/numba-users/c/YhCCz6tAfX4)
- [gdal-sys](https://docs.rs/crate/gdal-sys/0.9.1/source/Readme.md) ; [georust/gdal #517](https://www.github.com/georust/gdal/pull/517)
- [CRAN, Using Rust](https://cloud.r-project.org/web/packages/using_rust.html) ; [rextendr, conformité CRAN](https://extendr.github.io/rextendr/dev/articles/cran-compliance.html)
