# sylvigenese : brief de développement

Version du 24 novembre 2026. Auteur : Pascal Obstétar. Ce document est le cahier des charges du dépôt. Il s'adresse à la personne ou à l'agent de code qui implémente.

## Ma réponse d'abord (fiche n° 15)

> « J'attends de ce projet une plateforme de simulation de croissance des peuplements forestiers au vu des éléments de sortie du projet nemeton. sommieR est le passé, nemeton le présent, sylvigenese un futur envisageable »
>
> — Pascal, le 24 novembre 2026, dit avant toute proposition de Claude, recopié mot pour mot.

## Le brief, tel que Pascal l'a retenu (méthode de l'Impératrice, 24/11/2026)

> Chaque ligne vient d'une réponse de Pascal du 24/11/2026, inscrite au journal
> (`pilotage/journal.md`). Le cahier des charges détaillé suit à partir du §0. Il a été mis à
> jour le même jour pour suivre l'ADR 0001 (§3, §8, §12, §13).

- **Le problème.** sommieR décrit le passé, nemeton le présent. Personne ne montre, de façon
  chiffrée et visible, ce qu'un peuplement peut devenir. sylvigenese est « un futur
  envisageable ».
- **Pour qui.** D'abord Pascal et les utilisateurs de nemeton. Ensuite les gestionnaires et
  les aménagistes forestiers.
- **Coût complet aujourd'hui.**
  - Une licence annuelle NDunes 3D, à 100 € par an (source : Pascal).
  - Le temps passé à construire une scène : inconnu.
  - Aucune trajectoire chiffrée d'un peuplement n'est possible aujourd'hui.
  - *Bénéfice* : sylvigenese remplace la part « donner à voir » de NDunes 3D par une chaîne
    libre.
- **Ce que fait sylvigenese, en v1.** C'est une chaîne de modules reliés par des fichiers.
  - Elle part des sorties de **nemeton, qui sont l'entrée principale** (l'état présent du
    peuplement).
  - Elle les complète par sylvostation et typopeuplement (station, plafond de hauteur), par
    l'IFN (ajustement des modèles) et par le LiDAR HD (hauteur actuelle).
  - Elle simule la croissance des peuplements année par année.
  - Elle la donne à voir sur le web (iTowns) et en vue immersive (Godot).
- **Ce qu'il ne fait pas, en v1 :**
  - l'arbre par arbre à l'échelle d'une SER ;
  - les scénarios climatiques ;
  - la sylviculture interactive ;
  - le rendu photoréaliste ;
  - la plateforme multi-utilisateurs et l'intégration à `nemetonshiny`.
- **Valeur sacrifiée en v1 :** la v1 ne sert pas une décision d'aménagement. Elle montre une
  évolution libre, sans gestion (`management: none`). Cela suit le hors-périmètre retenu, qui
  exclut la sylviculture (arbitrage par délégation, I2).
- **Contraintes :**
  - GPL-3, formats ouverts, logiciels libres ;
  - IFN flouté, jamais croisé avec un raster fin ;
  - rien d'écologique inventé ;
  - EPSG:2154, grille SER à 25 m ;
  - massif test rejouable en moins de 30 min ;
  - 100 ans d'une SER en 5 jours au plus, dans 31 Go, sur le PC de Pascal (i7-4940MX) ;
  - `simulate` en Rust, avec la règle de lisibilité (ADR 0001).

## 0. Consignes à lire avant de coder

1. **Avancer jalon par jalon** (section 11). Ne pas commencer un jalon tant que les critères d'acceptation du précédent ne sont pas remplis.
2. **Les modules ne se parlent que par fichiers**, aux formats de la section 4. Aucun module n'importe le code d'un autre.
3. **Ne rien inventer d'écologique.** Toute valeur (optimum d'essence, coefficient de croissance, densité) vient d'une source citée ou d'un fichier de paramètres marqué `provisoire: true`.
4. **Données IFN : coordonnées floutées au kilomètre.** Interdiction de croiser une placette IFN avec un raster fin (MNT, LiDAR). Reprendre la garde `assert_no_fine_extract_on_ifn()` de `sylvostation`.
5. **Tout pipeline est rejouable** depuis `config.yml` sur le massif test, en moins de 30 minutes sur un portable.
6. **Signaler plutôt que deviner** : une essence sans modèle, une station sans biome ou un fichier manquant produit une erreur explicite ou une ligne dans un rapport, jamais une valeur par défaut silencieuse.
7. Langue : code et noms de variables en anglais, documentation et messages utilisateur en français.

## 1. Objet

`sylvigenese` simule et donne à voir la construction d'une forêt dans le temps, de la sylvoécorégion (SER) jusqu'à la plante du sous-bois.

- Entrées : données SIG 2D (QGIS), MNT LiDAR HD, sorties de `sylvostation`, `typopeuplement` et `nemeton`, données brutes de l'inventaire forestier national (IFN).
- Sorties : trajectoires de peuplements année par année (essences, tiges, volume, carbone) et leur représentation 3D navigable.

Trois notions sont tenues séparées dans tout le code :

| Notion | Question | Source |
|---|---|---|
| Niche | où l'essence se plaît-elle ? | valeurs indicatrices d'Ellenberg, gradients `sylvostation` |
| Croissance | à quelle vitesse grossit l'arbre ? | modèles ajustés sur l'IFN |
| Architecture | quelle forme prend-il ? | modèles de Hallé, Oldeman et Tomlinson, générateur de `tarif-nemeton` |

## 2. Forme du produit

Ce n'est pas une plateforme monolithique. C'est **une chaîne de cinq modules dans un seul dépôt**, reliés par des fichiers, dont le dernier maillon est une application web de consultation. La plateforme multi-utilisateurs (comptes, dépôt de données, calcul à la demande) est hors périmètre de la version 1 ; l'intégration à `nemetonshiny` sera étudiée ensuite.

Hors périmètre de la version 1 : simulation arbre par arbre à l'échelle d'une SER, scénarios climatiques, sylviculture interactive, rendu photoréaliste.

## 3. Architecture

```
 R : prepare ──► R : biomes ──► Rust : simulate ──► Python : assets/tiles ──► viewers
 (stations,      (catalogue,     (arbres, cohortes,   (glTF, 3D Tiles)         (web iTowns,
  IFN, lidR)      carte)          régénération)                                 Godot massif)
        └────────► R : dynamics (modèles IFN) ──────────┘
```

| Module | Rôle | Langage | Pourquoi ce langage |
|---|---|---|---|
| `prepare` | emprise, grille, gradients, arbres détectés, tables IFN | R (package + `targets`) | continuité avec `nemeton`, `sylvostation`, `lasR`, `lidR` |
| `biomes` | catalogue de biomes et carte d'affectation | R + YAML | le catalogue doit rester lisible par un forestier |
| `dynamics` | modèles d'accroissement, mortalité, recrutement | R (`mgcv` ou `glmmTMB`) | ajustement statistique |
| `simulate` | dynamique annuelle | Rust, exécutable autonome | rapidité, mémoire maîtrisée, robustesse (ADR 0001, banc d'essai du 24/11/2026) |
| `assets` | bibliothèque d'arbres 3D et tuiles | Python | le générateur `synth_arbres.py` existe déjà |
| `viewer-web` | globe, SER vers France | TypeScript, iTowns | bibliothèque libre portée par l'IGN, 3D Tiles |
| `viewer-massif` | vue immersive jusqu'à la plante | GDScript, Godot 4 | prototype existant (`nemeton3d_exemple`) |

Deux niveaux de simulation, à ne pas confondre :

- **Niveau massif** (quelques km²) : un agent par arbre.
- **Niveau SER** : un agent par cellule de la grille, portant des cohortes par essence. Les arbres affichés en zoomant sont tirés statistiquement depuis les cohortes.

## 4. Contrats de données

Tous les fichiers vivent sous `data/<zone>/`. Système de coordonnées : EPSG:2154. Grille commune de 10 à 25 m, fixée dans `config.yml`.

| Fichier | Produit par | Contenu |
|---|---|---|
| `grid.tif` | prepare | grille de référence |
| `dtm.tif` | prepare | MNT (LiDAR HD ou fourni) |
| `chm.tif` | prepare | MNH issu du LiDAR HD, avec sa date d'acquisition |
| `stations.tif` | prepare | bandes F, R, T, plus type de station |
| `site_potential.tif` | prepare | potentialité de la station par essence (hauteur dominante atteignable), d'après `typopeuplement` et `sylvostation` |
| `trees_init.parquet` | prepare | arbres détectés par lidR : `tree_id, x, y, species, d130, h`, avec `h` lue sur le MNH |
| `ifn/*.parquet` | prepare | placettes, arbres, flore, valeurs d'Ellenberg moyennes par placette |
| `biomes/*.yml` | biomes | un fichier par biome (section 5) |
| `biome_map.tif` + `biome_map.csv` | biomes | identifiant de biome par cellule et table de correspondance |
| `params/growth.parquet` | dynamics | coefficients par essence ou groupe d'essences |
| `params/mortality.parquet`, `params/recruitment.parquet` | dynamics | idem |
| `sim/trees.parquet` | simulate | partitionné par année : `tree_id, year, species, x, y, d130, h, hcb, cw, status` |
| `sim/cells.parquet` | simulate | par cellule, année, essence : tiges/ha, surface terrière, d moyen, semis/ha, hauteur des semis |
| `sim/summary.parquet` | simulate | par biome et année : volume, biomasse, carbone |
| `assets/trees/<species>_<stage>.glb` | assets | modèles 3D avec niveaux de détail |
| `tiles/<year>/tileset.json` | assets | 3D Tiles instanciées |

Chaque contrat a un schéma dans `contracts/` et un validateur appelé en fin de module.

## 5. Le catalogue de biomes

Pièce centrale : c'est le contrat entre les calculs et la 3D. Un biome décrit, pour une combinaison type de station × type de peuplement × stade, ce qui pousse et en quelle quantité, strate par strate.

```yaml
id: hetraie_sapiniere_fraiche_acide
provisoire: true
condition:
  station: fraiche_acide
  typopeuplement: futaie_irreguliere
  stade: adulte
strates:
  arboree:   {composition: {sapin: 0.5, hetre: 0.4, epicea: 0.1}, tiges_ha: 320}
  arbustive: {composition: {sorbier: 0.6, houx: 0.4}, couvert: 0.15}
  herbacee:  {composition: {myrtille: 0.5, canche: 0.3, fougere_aigle: 0.2}}
  sol:       {litiere: aiguilles, bois_mort_m3_ha: 25}
sources: [typopeuplement vX, relevés IFN SER D11]
```

Règles :

- Le catalogue fixe l'état initial et sert de légende ; la simulation fait ensuite évoluer composition et densité.
- Les gradients continus (F, R, T) modulent à l'intérieur d'un biome : vigueur, transitions entre stations voisines.
- Toute cellule forestière a un biome. Les cellules sans correspondance sont listées dans `rapport_biomes.html`.

## 6. Dynamique des arbres (IFN)

État d'un arbre : essence, `d130`, `h`, hauteur de base du houppier `hcb`, largeur de houppier `cw`. `d130` et `h` sont simulés ; `hcb` et `cw` s'en déduisent par les allométries de `tarif-nemeton` (`synth_calage.py`).

### Hauteur (décision du 24/11/2026)

La hauteur repose sur deux sources, et sur elles seules :

- **Le MNH du LiDAR HD donne la hauteur actuelle.** Il fixe la hauteur initiale de chaque arbre détecté et la hauteur dominante de chaque cellule à la date du vol.
- **La potentialité de la station donne la trajectoire.** `typopeuplement` et `sylvostation` fournissent, par essence, la hauteur dominante atteignable sur la station. La croissance en hauteur suit une courbe bornée par ce plafond, ancrée sur la hauteur observée.

Conséquences pour le code :

1. La hauteur dominante d'une cellule évolue selon une courbe de croissance paramétrée par `site_potential.tif` ; la forme de la courbe est un paramètre par essence, marqué provisoire tant qu'elle n'est pas sourcée.
2. La hauteur d'un arbre se déduit de la hauteur dominante de sa cellule et de son rang en diamètre. Aucune relation H(D) générale n'est appliquée seule.
3. La position de la hauteur observée sur la courbe donne le stade du peuplement, utilisé pour choisir le biome.
4. Une hauteur observée supérieure au plafond de la station n'est pas corrigée : elle est signalée dans `rapport_hauteur.html`, car elle met en cause soit la potentialité, soit l'essence attribuée.
5. Le MNH est une mesure à une seule date. Si un second vol devient disponible, l'écart entre les deux sert à valider la courbe, pas à la remplacer.

### Diamètre, mortalité, recrutement

Trois modèles, ajustés par essence ou par groupe d'essences quand l'effectif est faible :

1. **Accroissement** : accroissement radial sur 5 ans en fonction de `d130`, de la concurrence (surface terrière de la placette, surface terrière des arbres plus gros) et de la station (valeurs d'Ellenberg moyennes de la placette, SER). Ramené à un pas annuel.
2. **Mortalité** : probabilité à 5 ans d'après les placettes revisitées.
3. **Recrutement** : flux d'arbres franchissant 7,5 cm de diamètre.

Exigences : validation croisée spatiale par blocs ; rapport par essence (biais, erreur, domaine de validité) ; les noms exacts des variables IFN sont à vérifier dans la documentation des données brutes avant tout ajustement.

Limites connues à documenter dans le rapport : concurrence non spatialisée, climat des cinq années précédant la mesure, cohérence à contrôler entre le diamètre simulé (IFN) et la hauteur simulée (station) par le rapport H/D.

Chaque arbre simulé reçoit volume par découpe, biomasse et carbone par le tarif NEMETON, appliqué en post-traitement.

## 7. Régénération

Sous 7,5 cm de diamètre, pas d'individus : des cohortes par cellule et par essence (densité, hauteur moyenne). Référence de conception : RReShar (plateforme Capsis).

1. Arrivée des graines selon les semenciers voisins.
2. Installation filtrée par la station (règles de biome).
3. Croissance et survie : lumière sous couvert × tolérance à l'ombre (indice L d'Ellenberg) × concurrence du sous-bois (fougère aigle, molinie, ronce) × pression du gibier.
4. Passage à la futaie à 7,5 cm, calé sur le recrutement observé par l'IFN.

Pression du gibier et fréquence des fructifications sont des paramètres de scénario (faible, moyenne, forte), pas des constantes. Vérifier ce que le module de régénération de `nemeton` (`regen_engines.R`) peut fournir comme état initial.

## 8. Simulation (Rust, ADR 0001)

- Espèces d'agents : `tree`, `cell` (cohortes et régénération), `stand` (agrégation par biome).
- Pas de temps annuel, horizon paramétrable (défaut 100 ans), graine aléatoire fixée et enregistrée.
- Lancement sans interface depuis la ligne de commande ; un script unique `run_simulation` prend `config.yml` et écrit `sim/`.
- Le moteur ne contient aucun coefficient en dur : tout vient de `params/`.
- Cible (ADR 0001) : 100 ans de la plus grande SER (C20, environ 48 millions de cellules à 25 m) en 5 jours au plus, dans 31 Go, sur le PC de Pascal. iLand, LANDIS-II et TreeMig servent de références de validation.

## 9. Arbres 3D et tuiles

- Adapter le générateur de `tarif-nemeton` (branche `synth-arbres`) pour exporter en glTF binaire, trois niveaux de détail, quatre stades par essence.
- Ces arbres servent à la visualisation et aux scans simulés ; ils ne valident aucun tarif.
- Construire les 3D Tiles instanciées à partir de `sim/trees.parquet`, une tuile par année retenue (pas de 5 ou 10 ans).

## 10. Visualisation

**Web (iTowns)** : fond IGN, raster temporel des biomes et des indicateurs, arbres instanciés à l'approche, curseur d'année, fiche de la cellule visée (station, biome, composition, volume, carbone).

**Massif (Godot 4)** : reprise du prototype. Lecture de `sim/`, arbres du générateur, strate herbacée et semis générés autour de la caméra d'après le biome et le couvert.

Passage de l'un à l'autre : un lien depuis la vue web ouvre la vue massif aux mêmes coordonnées. Pas de zoom continu entre les deux moteurs.

## 11. Jalons

> Mis à jour le 24/11/2026, d'après la critique du brief (`docs/critique-brief-contradicteur.md`,
> B3 à B5), par délégation de Pascal. Chaque jalon a deux parties :
> - **a** : code et tests sur le jeu fictif, faits par les agents ;
> - **b** : acceptation sur données réelles, qui demande Pascal (données, réseau, son PC).
>
> Les seuils chiffrés sont dans `docs/spec.md`.

| Jalon | Livrable | Critère a (jeu fictif) | Critère b (réel, avec Pascal) |
|---|---|---|---|
| M0 | squelette, contrats (entrées externes comprises), jeu d'essai fictif, CI | les validateurs passent sur le jeu fictif ; CI verte | — |
| M1 | `prepare` et `biomes` | carte des types de végétation sans cellule orpheline non signalée | idem sur le massif test réel |
| M2 | `dynamics` | ajustement et rapport par essence sur données IFN réduites | validation croisée par blocs sur la SER pilote, meilleure qu'un modèle nul |
| M3 | `simulate` niveau massif, 100 ans, recrutement IFN direct | tests de non-régression, identité entre fils, contrôles | validation à 5 ans et plausibilité à 100 ans (quantiles IFN 5-95 %) |
| M4 | `assets` minimal (glTF génériques) et `viewer-web` sur le massif | 100 000 instances affichées, images par seconde mesurées par script | sur la machine et le navigateur de Pascal |
| M5 | niveau SER en cohortes, régénération | une SER fictive simulée ; recrutement calé sur le modèle IFN | SER pilote complète ; recrutement dans l'intervalle de confiance IFN |
| M6 | arbres du générateur et `viewer-massif` | arbres du générateur dans les deux vues (sans GPU : export et tests) | sur le PC de Pascal |

## 12. Arborescence

```
sylvigenese/
  BRIEF.md   README.md   LICENSE   config.yml
  contracts/          schémas et validateurs
  R/                  package R : prepare, biomes, dynamics
  _targets.R          pipeline
  biomes/             catalogue YAML versionné
  simulate/           moteur Rust (exécutable autonome)
  assets/             Python : générateur glTF, tuiles
  viewer-web/         TypeScript, iTowns
  viewer-massif/      projet Godot 4
  tests/              par module, plus un test de bout en bout sur le jeu fictif
  data/               hors dépôt (.gitignore)
```

## 13. Qualité et licence

- Licence GPL-3, cohérente avec `lidR`, `lasR` et iLand.
- Tests : `testthat` (R), `pytest` (Python), `cargo test` (Rust), un scénario de non-régression du moteur, test de bout en bout sur le jeu fictif.
- Versions des outils figées dans le README (R, Rust, Python, Node, Godot).
- Données volumineuses hors dépôt ; seuls les jeux d'essai réduits sont versionnés.

## 14. Questions ouvertes

1. Massif test et SER pilote : lesquels ?
2. Liste des essences de la version 1, et regroupements pour les essences rares.
3. Format exact des sorties de `typopeuplement` à brancher sur le catalogue.
4. Hébergement de la vue web et des tuiles.
5. Forme de la courbe de croissance en hauteur par essence, entre la hauteur observée et le plafond de la station : quelle source ?
