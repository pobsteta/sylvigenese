# Entrées externes de `prepare` : ce que produisent réellement nemeton, sylvostation, typopeuplement et tarif-nemeton (mission 008)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Mission redite :** décrire, d'après leurs dépôts, les fichiers, formats, colonnes, unités, CRS, résolutions et dates réellement produits par les quatre dépôts, pour écrire les contrats d'entrée de `prepare` et les règles d'état initial de `docs/spec.md` avant M0 (critique, points B1, B2, B6, I4, I7).
- **Décision éclairée :** quels contrats d'entrée écrire dans la spec, et quelle règle de priorité pour l'état initial (nemeton, puis MNH pour `h`, puis le biome pour combler).
- **Fichier tabulaire :** `docs/referentiels/entrees-externes.csv` (une ligne par fichier ou colonne ; la colonne `source_fichier_ligne` donne le fichier et la ligne lus ; la colonne `ecart` dit ce qui diverge).
- **Méthode :** lecture seule du code, des schémas et de la documentation de chaque dépôt (outils de lecture et de recherche de texte). **Aucune exécution** : aucun pipeline lancé, aucun GeoTIFF ni GeoPackage ouvert. Ce qui est dit des fichiers binaires vient donc du code qui les écrit ou de la documentation, jamais du fichier.

## Sources et commits

| Dépôt | Commit indiqué par l'orchestrateur | Vérifié dans le clone | Version | Licence |
|---|---|---|---|---|
| nemeton | bd6fbe5 | `.git/refs/heads/main` = bd6fbe5c1a7c… | 2026.11.45 (`DESCRIPTION:4`, tag `v2026.11.45`) | GPL-3 (`DESCRIPTION:20`, `LICENSE.md:1,7-8`) |
| sylvostation | 2864d70 | `.git/logs/HEAD:1` = 2864d70ef807… | 2026.11.0 en développement (`DESCRIPTION:4`) | GPL (>= 3) (`DESCRIPTION:12`) ; le README dit GPL-3 (`README.md:63`) |
| typopeuplement | 149fee3 | `.git/logs/HEAD:1` = 149fee332a14… | 0.1.0 dans le dépôt (`DESCRIPTION:4`, `pyproject.toml:7`) ; tag `v2026.11.2` | GPL-3 (`DESCRIPTION:19`, `pyproject.toml:11`) |
| tarif-nemeton | 0f51b96 | `.git/logs/HEAD:1` = 0f51b9606165… ; clone superficiel, `origin/main` seule | méthodologie v2.23 du 3 octobre 2026 (`README.md:8`) | **aucune** : « licence à définir avant toute ouverture » (`README.md:90`) |

Les clones sont superficiels (fichier `.git/shallow`) : pas d'historique, pas de branches autres que `main`.

## Écarts relevés entre sources (résumé)

1. **Précision des placettes IFN.** sylvostation : 700 m (`config.yml:26`, `R/utils.R:99`). tarif-nemeton : « coordonnées IFN publiques à ±700 m » (`resultats/etage_b/LISEZMOI.md:29`). `CLAUDE.md` de sylvigenese : « floutées au kilomètre » ; critique I4 : « raster fin = résolution inférieure à 1 km ». Trois sources sur quatre disent 700 m.
2. **Trois mailles.** typopeuplement 26,6 m (ADR 0005, `docs/spec.md:105-108`), sylvostation 20 m (`config.yml:17`, ADR 0007), sylvigenese 25 m (ADR 0001). Aucune n'est multiple d'une autre.
3. **Trois sens de « potentialité de station »** (voir B6 ci-dessous) ; **aucune des trois sources ne fournit** la couche « par essence, hauteur dominante atteignable » du BRIEF §4.
4. **TAXREF.** `config.yml:47-48` de sylvostation : version 18. L'IFN livre `espar-cdref13.csv` en TAXREF v13.0 (`R/controle_essence.R:123-127`). Les deux versions coexistent dans sylvostation.
5. **ESPAR.** Deux caractères avec zéro dans `ARBRE` (« 09 »), sans zéro dans `espar-cdref13.csv` (« 9 ») : `R/controle_essence.R:225`.
6. **Nombre d'indicateurs nemeton :** 41 (`DESCRIPTION:11`, `README.md:26`) contre 44 (`README.md:18`, `R/indicators-core.R:9-11`, `R/data-massif_demo.R:34`). Le tableau du README liste 42 codes (comptage de l'acquéreur).
7. **Codes d'essence de P1 dans nemeton :** la doc donne des codes à 4 lettres (`R/indicators-productive.R:26,81`), le jeu `massif_demo_units` des codes espar à 2 chiffres, non reconnus par P2 (`R/data-massif_demo.R:18-19,77-80`).
8. **COG.** typopeuplement décide « toute livraison publiée en COG » (ADR 0013) mais `ecrire_livrables()` écrit des GeoTIFF simples (`R/typer_peuplements.R:286-288`). sylvostation écrit un COG si GDAL le permet, sinon un GeoTIFF tuilé DEFLATE (`R/sorties.R:65-76`).
9. **Branche `synth-arbres`** citée par le BRIEF §9 : absente du clone de tarif-nemeton.
10. **Export glTF, niveaux de détail, stades** attendus par le BRIEF §9 : **absents** de `synth_arbres.py` (voir la section tarif-nemeton).

---

## 1. nemeton (package R, GPL-3)

### Ce qu'il produit

nemeton n'a pas de fichier de sortie unique. Il rend, en mémoire R, un objet `sf` (`nemeton_compute()`) : les unités d'entrée, plus une colonne par indicateur (codes `C1` à `N5`) et une colonne `<code>_status` (`R/indicators-core.R:17-19`). L'**unité spatiale est le polygone** (parcelle ou unité de gestion), `POLYGON` ou `MULTIPOLYGON`, CRS obligatoire (`R/nemeton-class.R:15-20`). Je n'ai pas trouvé de fonction d'export unique de cet objet ; l'export GeoPackage ou PDF est attribué à `nemetonshiny`, qui n'est pas dans ce dépôt (`README.md:153`). `st_write`, `writeRaster` et équivalents apparaissent dans 27 fichiers R (recherche de texte, décompte seul : je n'ai pas ouvert chacun).

Produits fichiers que j'ai pu documenter :

| Produit | Format et contenu | Source |
|---|---|---|
| `inventaire_video.gpkg` (schéma 1.7.0, EPSG:2154) | GeoPackage : couches `placettes`, `centres_mesures`, `cibles`, `arbres`, `detections`, `houppiers`, `parcelles`, `ugf`, `projet` ; rasters `mnt`, `mnh` (Float32, 0,5 m, nodata −9999) | `inst/inventaire_video/inventaire_video.schema.json:3-4,21-205,206-223` |
| couche `houppiers` | polygones : `plot_id`, `houppier_id`, `h_max` (m), `surface_m2`, `x_sommet`, `y_sommet` | `schema.json:145-150` |
| `segment_houppiers()` | `sf` polygones : `houppier_id`, `h_max` (m), `surface_m2`, `x_sommet`, `y_sommet` ; hauteurs admises 1 à 70 m ; MNH agrégé à 0,5 m par maximum | `R/houppiers.R:151,155,182-193` |
| `compute_dtm_chm_from_laz()` | `dtm.tif`, `chm.tif`, 1 m par défaut, à partir de nuages COPC de l'IGN avec lasR | `R/lidar_processing.R:30,47-55` |
| `massif_demo_units` | jeu **entièrement synthétique** (20 polygones, EPSG:2154) | `R/data-massif_demo.R:8,54-58` |

### Ce qu'il prend en entrée (utile pour nous)

- **Oui, nemeton prend du LiDAR HD** : nuages COPC (`compute_dtm_chm_from_laz()`), MNT et MNH de l'IGN (`inst/NOTICE:42-47`), et un MNH issu d'Open-Canopy sans LiDAR (`README.md:84-125`).
- Un inventaire de peuplement **par polygone** (colonnes `species`, `dbh`, `height`, `density`, `age`) fourni par l'utilisateur, ou à défaut tiré du MNH (voir B1).

### Réponses aux questions de la critique

**B1 : liste d'arbres, peuplements ou indicateurs ?** Les trois, à des échelles différentes, et **aucune ne couvre le massif entier par arbre avec essence et d130** :

| Niveau | Contenu | Essence | d130 | Surface terrière | Tiges/ha |
|---|---|---|---|---|---|
| Polygone (parcelle, UGF) | colonnes d'entrée `species`, `dbh`, `height`, `density`, `age`, `volume` (`R/data-massif_demo.R:18-31`) | **un seul code** par polygone (espar à 2 chiffres dans le jeu) | **un diamètre moyen** (`dbh`, cm) | non, pas de colonne `G` | oui, `density` en tiges/ha |
| Polygone, estimé du MNH | `synthetic_inventory` : `H_dom`, `dbh` (diamètre quadratique), `density`, `source = "synthetic_ml"`, `hors_domaine` (`R/synthetic_inventory.R:238-246`) ; D tiré de H par une loi puissance, N par l'autoéclaircie de Charru 2012 (`:1-20`) | un code fourni par l'appelant | estimé, signalé hors domaine quand il est borné | non | oui, estimé |
| Houppier (tout le massif) | `segment_houppiers()` : `h_max`, `surface_m2`, sommet | **non** | **non** | non | non (comptable) |
| Arbre (placettes de l'inventaire vidéo seulement) | couche `arbres` : `tree_id`, `dbh_cm`, `h_m`, `essence_arbre`, `statut`, `qualite`, `h_source`, `dbh_source`, position par azimut et distance (`schema.json:88-114`) | oui (`essence_arbre`, 34 codes français snake_case ; `espece` contient le **type de peuplement**) | oui, avec `dbh_source` (estimé ou mesuré) | non | non |
| Indicateurs | 44 colonnes 0 à 100 ou en unités propres (P1 m³/ha, P2 m, C1 tC/ha…) | | | | |

Les placettes de l'inventaire vidéo ont un rayon de 15 m et un seuil de 7,5 cm par défaut (`schema.json:45-46`). C'est un échantillon, pas un inventaire exhaustif. Le schéma porte déjà un équivalent du `species_source` et `d130_source` voulu par la critique B2 : `h_source` (mnh, mesuree, aucune) et `dbh_source` (estime, mesure).

**B2 : d'où viennent essence et d130 des arbres détectés ?** nemeton seul ne les donne pas pour les arbres détectés (voir ci-dessus). Deux chemins documentés ailleurs :
- **tarif-nemeton, étage B** (`resultats/etage_b/arbres_lidar_volumes.csv:1`) : l'arbre détecté dans le MNH (lidR `lmf` puis `dalponte2016`, `code/etage_b_arbres_lidar.R:4-8`) reçoit son **essence du type de peuplement BD Forêt v2 sous son sommet** (`tfv`, `sp` ; les mélanges deviennent `Quercus_spec`, `code/etage_b_volumes.py:9-10,29-31`) et son **d130 par `ln D = a + b ln H + c ln CPA`** calé par essence sur BioDiv (TLS), ou `ln D = a + b ln H` calé sur l'IFN du voisinage (`code/etage_b_allometrie_ifn.py:1-14`).
- **Qualité mesurée par Pascal** : 140 à 160 arbres/ha détectés, d prédit sous-estimé pour les feuillus (hêtre 20,5 contre 32,8 cm ; chênes 25,5 contre 32,1) en vol hors feuilles (`resultats/etage_b/LISEZMOI.md:18-21`). Les arbres dominés manquent : les 140-160 plus gros portent 80 à 92 % du volume IFN (même fichier, l.19-20).
- Aucun chemin « essence par arbre » ne vient de nemeton pour le massif entier. La couche de types BD Forêt est une entrée (`spec` de typopeuplement : « essences, entrée, pas vérité », `docs/spec.md:40`).

**B6 (côté nemeton) : que veut dire sa « potentialité » ?** Le **P2 en mode MNH** est un **indice de station** : la hauteur dominante qu'aurait le peuplement à un âge de référence (50 ans par défaut), interpolée entre **5 classes de fertilité** à l'âge observé (`R/site_index.R:211-259` ; `R/indicators-productive.R:343-357`). Il faut l'âge du peuplement (le MNH ne le donne pas). Hors courbe, la valeur est `NA` avec `p2_status = "hors_courbe"`. Les courbes (`inst/extdata/site_index_curves.csv`, colonnes `species`, `age`, `class_1`…`class_5`, en m) sont des **reconstitutions Chapman-Richards calées sur un point publié par essence** (`data-raw/site_index_curves.R:19-24,59-68`), non les équations d'origine. Essences : QUPE, QURO, CASA, PIAB, ABAL, PSME, PISY, PIPI, POSP, FASY (+ `FASY_NO`, `FASY_NE`, `BROADLEAF_GENUS`, `CONIFER_GENUS`). Les âges de référence des points de calage vont de 25 à 100 ans selon l'essence (`R/site_index.R:185-207`). Dans les autres modes, P2 est une production en m³/ha/an : trois sens pour une même colonne.

**Nomenclature des essences (nemeton).** Quatre systèmes coexistent : `espar` IFN à 2 caractères, code P1 à 4 lettres (24 essences), code « tolérances » latin en snake_case (194), et le code `essence_arbre` de l'inventaire vidéo (34), plus les classes de peuplement `essence_*` (11 en BFC). Le pivot est le **nom latin** de `espar-cdref13` (`R/ifn_espar.R:1-12` ; `inst/extdata/ifn_espar_correspondance.csv:1`). La table passe de `espar` à l'un des deux premiers et au code tolérances ; **la table `essence_arbre` vers `espar` n'est pas dans ce dépôt**.

**Régénération (BRIEF §7, `regen_engines.R`).** Les moteurs rendent des colonnes de **contrainte** par polygone : `njstress`, `istress`, `rew_min`, `deb_stress` (bilan hydrique BILJOU) et `tmax_*`, `vpd_*`, `sensibilite*`… (`R/regen_engines.R:20-24`) ; `regen_rank_species()` classe des essences candidates (`R/regen_rank_species.R:253-262`). **Aucune densité de semis, aucune hauteur de semis** : `regen_engines.R` ne fournit pas d'état initial de régénération.

### Licence

GPL-3. Les données tierces sont listées dans `inst/NOTICE` (IGN Etalab 2.0, Open-Canopy MIT ou CC-BY-4.0 « à confirmer », etc.). La redistribution des courbes de station est autorisée par M. Tran-Ha par communication personnelle, avril 2026 (`README.md:127-131`) : à garder en tête si la table est recopiée dans sylvigenese.

---

## 2. sylvostation (package R et pipeline `targets`, GPL (>= 3))

### Ce qu'il produit

Sous `data/sorties/<ser_code>/` (`config.yml:19-21`, `R/sorties.R:133-166`), préfixé `synth_` en démonstration. **Maille 20 m, EPSG:2154** (`config.yml:17,19` ; ADR 0007). Mode démonstration par défaut (`config.yml:30`, `demo: true`) : tout est synthétique et les critères d'acceptation ne sont pas atteints (`README.md:32-35`). Le mode réel est branché (mission 016) mais ses résultats ne sont pas dans le clone.

| Fichier | Contenu | Source |
|---|---|---|
| `types.tif` | une bande `type_id` (entier, ordre alphabétique des types) | `R/sorties.R:141-144,207-220` |
| `gradients.tif` | 3 bandes : `trophic`, `hydric`, `bioclim` | `_targets.R:718-731` |
| `incertitude.tif` | `sd_cv_trophic`, `aoa_trophic` (trophique seul) | `_targets.R:734-743` |
| `types.gpkg` | couches `types` (`type_id`, `type`, `area_ha`, `synthetic`) et `table_types` | `R/sorties.R:150-158` |
| tables CSV (`;`, UTF-8) | `types`, `fertilite`, `especes_indicatrices`, `cle_terrain`, `cle_resume`, `validation_stats`, `etat_de_preuve`, `legende_types`, `fusions_types`, `effectifs_calibration`, … | `R/sorties.R:60-63,160-166` ; `_targets.R:843-852` |
| couches de la carte hydrique et climat | `is_topo`, `nj_topo`, `is_plat`, `k_sv`, `ru_maille` ; `temperature_corrigee`, `ru_apprise`, `bilan_lateral` | `R/hydrique.R:1356` ; `_targets.R:901-907` |

Les types de données GDAL, les valeurs `nodata` et les noms de fichiers de `write_hydric_grid()` ne sont **pas lus**.

### Réponses aux questions

**Bandes de gradients : F, R, T ?** **Non.** Les trois bandes sont `trophic`, `hydric`, `bioclim`, et ce ne sont pas des valeurs d'Ellenberg par cellule :
- `trophic` : modèle (forêt aléatoire) de la moyenne des valeurs de type Ellenberg `REACTION` et `NUTRIENTS` des plantes de la placette IFN (`grad_trophique = rowMeans(grad_ph, grad_azote)`, `R/placettes.R:515-518`), prédite sur les prédicteurs à maille large.
- `hydric` : `−Istress` calculé par le modèle de bilan hydrique BILJOU, sur climat SAFRAN, réserve utile et rayonnement ; le modèle régional ne sert qu'à la validation croisée (`docs/pipeline.md:86` ; `_targets.R:726-727`).
- `bioclim` : premier axe de (P − ETP) et de la température, centrés-réduits, orienté « plus haut = plus chaud » (`R/pipeline_reel.R:961-1008`, statut « provisoire (mission 016) »).
Le BRIEF §4 parle de « bandes F, R, T » : à renommer ou à redéfinir dans le contrat.

**Ellenberg ou EIVE ?** Ni l'un ni l'autre au sens strict : sylvostation lit les **valeurs de type Ellenberg de Tichý et al. (2023)** (`J. Veg. Sci.` 34, e13168 ; classeur Zenodo, colonnes `LIGHT`, `TEMPERATURE`, `MOISTURE`, `REACTION`, `NUTRIENTS`, `SALINITY`, `R/indicateurs.R:46-56` ; `config.yml:50`). Le mot **EIVE n'apparaît nulle part** dans les trois dépôts R (recherche de texte, une seule occurrence : le fichier `logo.svg` de nemeton, sans rapport). La critique I5 demande EIVE 1.0 : ce serait une **autre table**, à brancher.

**Garde `assert_no_fine_extract_on_ifn()`.** Oui (`R/utils.R:121`). Elle bloque l'extraction d'une variable **fine** sur des points marqués IFN, ou dont la précision de localisation `loc_precision_m` est absente, `NA` ou supérieure à `max_precision_m = 25` m (`R/utils.R:121-157`). **« Fin » est une liste de noms**, non un seuil de résolution : `pente`, `exposition`, `twi`, `tpi_*`, `mnt`, `mhc`, `metriques_lidar`, et les préfixes `lidar_`, `mnt_`, `mhc_`, `k_` (`R/utils.R:9-27,37`) ; sont permis les noms préfixés `coarse_` et `climat_km`, `pedopaysage`, `geologie_700m` (`:35`). Toute variable inconnue non préfixée est traitée comme fine. Le seuil « 1 km » du BRIEF et de la critique I4 n'est pas celui du code ; le plus proche est `min_res_ifn_m = 1000` m, une maille minimale pour une couche **climatique** croisée avec des placettes (`R/placettes.R:440-443`).

**Voisinage et rayon.** Les variables larges aux placettes IFN sont des **moyennes dans un disque de 700 m** (`ifn_precision_m`, `config.yml:26` ; `coarse_*_700m`). La placette IFN elle-même : cercles de 6, 9 et 15 m selon le diamètre (commentaire du code de tarif-nemeton, `code/etage_b_allometrie_ifn.py:6-7`, **pas une source IGN**) ; typopeuplement retient 15 m (706,9 m², ADR 0005 l.11-13). Pour I4 (« disque de même surface que la placette IFN, à sourcer ») la source IGN du rayon n'a pas été lue.

**B6 (côté sylvostation) : « potentialité ».** sylvostation ne produit **pas de raster de potentialité**. Il produit `fertilite.csv` : un **indice de fertilité = hauteur dominante à un âge de référence** (50 ans, « provisoire »), **par essence et par type de station**, calculé sur les placettes IFN mesurées (`HTOT`, `AGE`) : moyenne des 3 plus hauts arbres par placette et essence, courbe guide `h = a + b ln(âge)` par essence (non bornée), indice translaté à l'âge de référence (`R/caracterisation.R:91-125`). Colonnes : `species`, `type`, `n_plots`, `fertilite_moy`, `fertilite_med`, `fertilite_sd`, `age_ref`. La méthode se dit « simple et provisoire, à valider avec un sylviculteur » (l.95-96). Source du cadre : brief technique (`docs/brief-technique.md:109,172`).

**Nomenclature.** Placettes IFN : `ESPAR` (2 caractères) ; passage à `CD_REF` TAXREF v13 par `espar-cdref13.csv` de l'archive IFN (`R/controle_essence.R:123-127`) ; flore en `CD_REF` ; `taxref_version: "18"` dans la config (`config.yml:47-48`). Écart de version et de zéro de tête signalés plus haut.

**Autres points.** Coordonnées placettes : `XL`, `YL`, EPSG:2154, x = est (`R/placettes.R:109-112`). Table `ARBRE` : `C13` (circonférence à 1,30 m ; unité à confirmer), `HTOT`, `V`, `W` (`R/placettes.R:121-123`) : **le d130 est à calculer** à partir de `C13`. Entrées non distribuées : BD Forêt v2 en option désactivée pour « licence contradictoire » (`config.yml:108-110`).

### Licence

GPL (>= 3). Données : IFN (Etalab 2.0), Tichý et al. (CC BY 4.0, `docs/referentiels.md:264`), SoilGrids (CC BY 4.0, `config.yml:82`), BD ALTI (Licence Ouverte, `config.yml:131-132`).

---

## 3. typopeuplement (package R ; prototype Python de référence ; GPL-3)

### Ce qu'il produit

`ecrire_livrables()` écrit, par **AOI** (une forêt ou un massif, jamais la France entière), dans un dossier (`R/typer_peuplements.R:257-278,296`) : `types.tif`, `variables.tif`, `confiance.tif`, `fiche_validation.md`, `carte_types.csv`, `correspondance_types.csv`, `correspondance_niveau_modele.csv`, `temps_etages.csv`. **EPSG:2154** ; maille **26,6 m** décidée (ADR 0005, `docs/spec.md:105-108`), 25 m par défaut dans la fonction.

| Fichier | Bandes | Unités | Source |
|---|---|---|---|
| `types.tif` | `type`, `proba`, `type_second`, `entre_deux` | code entier, appartenance non calibrée, code, 0/1 | `R/typer_peuplements.R:257-260,304-309` |
| `variables.tif` | `G`, `part_resineux`, `part_pb`, `part_bm`, `part_gb`, `N`, `h_dom`, `h_pot`, `hpot`, `h_pot_sd`, `rapport_h`, `c1_<ref>`…`c4_<ref>`, `densite_houppiers` | G m²/ha ; parts 0 à 1 ; N et densité tiges/ha ; hauteurs m ; couverts 0 à 1 | `:261-264,310-313` |
| `confiance.tif` | `hp_incertaine`, `hors_cle`, `niveau_modele`, `non_precomptable`, `part_pb_absente`, `gb_interim`, `part_retours_sous_s1` | 0/1 ; 0 à 2 ; 0 à 1 | `:265-271,314-321` |

Entrées ONF : `G.tif`, `p100GR.tif`, `p100GGB.tif`, `H0_lidar.tif`, `Tx_couv.tif`, `Compo1.tif`, `Typo_etage.tif`, `N.tif` (`R/donnees_lidar.R:14-21,52-57`). `Compo1` = famille (0 non précomptable, 1 feuillus, 2 résineux, 3 mélange).

**Statut.** « Aucune carte de H10 n'est encore publiée », la clé de `config/exemple.json` « n'est pas une typologie », « H0 du jeu ONF non calibrée » (`README.md:25-26,64-69`). SER pilote H10 (Préalpes du Nord), AOI : Vercors drômois, forêt de Léoncel (`README.md:22-23`). Les codes « sans donnée » 250 à 255 sont **décidés** (ADR 0013, l.33-42) mais **non écrits** (`R/typer_peuplements.R:287-288`).

### Réponses aux questions

**B6 : que veut dire `h_pot` ?** Ce n'est **ni un indice de fertilité à âge de référence, ni une asymptote par essence**. C'est la **hauteur dominante observée des peuplements « adultes fermés »** (couvert ≥ 0,7 et `h_dom` ≥ 15 m, valeurs provisoires), **prédite par une forêt aléatoire sur le milieu** (topographie, climat, sol), **par famille d'essences** (pas par essence), puis **relevée par un facteur k** égal au quantile 0,9 du rapport observée/prédite hors sac (`R/hauteur_potentielle.R:9-17,22-38`). Il n'y a pas d'âge. Conséquences :
- la hauteur potentielle est apprise **sur le MNH lui-même** : le risque de circularité est écrit par ADR 0009 (l.37-39) ;
- « environ `1 − quantile_enveloppe` des adultes appris dépassent leur hauteur potentielle » (`R/hauteur_potentielle.R:16-17`) : **environ 10 % des adultes dépassent `h_pot` par construction**. La règle « hauteur au-dessus du plafond = signalée dans `rapport_hauteur.html` » du BRIEF §6 en signalera donc environ 10 % sans que ce soit une anomalie ;
- l'ADR 0009 (acceptée par Pascal le 2026-11-23) en fait un **livrable conditionnel** : critère d'erreur par SER fixé avant les résultats ; sans lui, pas de couche livrée et repli sur la hauteur mesurée ; **cible à terme** : croisement du LiDAR HD avec les séries annuelles de hauteur de `nemetoncanopee` (profondeur « à vérifier ») ;
- `h_pot_sd = k × RMSE` de validation croisée par blocs ; `hp_incertaine` levé quand `h_pot_sd/h_pot` dépasse 0,2 (`:106-114`).

**B1 / B2 (côté typopeuplement).** Pas de liste d'arbres. Un **état de peuplement par pixel** (G, N, parts de catégories de diamètre PB, BM, GB, hauteur dominante), sans essence autre que la famille (feuillus, résineux, mélange). Les parts PB/BM/GB sont des catégories de diamètre, dont les seuils dépendent du référentiel typologique (ADR 0007). Aucun mot `espar`, `TAXREF` ou `CD_REF` dans `R/`, `docs/` ou les configs (recherche de texte : 0 occurrence).

**Nomenclature.** Aucune nomenclature d'essences propre. La spec réclame « les codes d'essences de la BD Forêt v3 et leur correspondance avec ceux de nemeton » (`docs/spec.md:91`) : non fait.

### Licence

GPL-3. Prototype Python (`src/typopeuplement/`, `pyproject.toml`) conservé « comme référence de comparaison » (`README.md:59-60`).

---

## 4. tarif-nemeton (dépôt privé de Pascal, Python et R ; **sans licence**)

**État :** « recherche en cours », coefficients « non stabilisés » à ne pas utiliser en production (`README.md:8`). Dépôt privé, licence à définir (`README.md:90`) : reprendre du code ou des tables dans un dépôt GPL-3 suppose une décision de Pascal sur la licence.

### `synth_arbres.py` : ce qu'il sort

- **Une table de segments** (troncs de cône) en CSV : `x0,y0,z0,x1,y1,z1,r0_m,r1_m,niveau,axe,racine_niveau1`, en mètres, repère local de l'arbre (`code/synth_arbres.py:493-501`). Exemple : `resultats/synth_arbres/exemple_hetre.csv`.
- **Un résumé par arbre** : `V_total`, `V_tige`, `V_branches`, `V_sup2/7/20/30`, `hbh_m`, `Rh_m`, `etendue_max_m`, etc. (`:423-443`), et `population.csv` pour 3 300 arbres (`resultats/synth_arbres/population.csv:1` ; `LISEZMOI.md:24`).
- **Pas de glTF, pas de niveaux de détail, pas de stades** : aucune occurrence de `glb`, `gltf`, `LOD`, `stade`, `.obj`, `.ply`, `parquet` dans les fichiers `code/synth_*.py` (recherche de texte). Le BRIEF §9 (« exporter en glTF binaire, trois niveaux de détail, quatre stades par essence ») décrit un travail à faire, non un état du code. La « branche `synth-arbres` » n'est pas dans le clone.
- **Essences couvertes (11)** : `Fagus_sylvatica`, `Quercus_spec`, `Fraxinus_excelsior`, `Acer_pseudoplatanus`, `Betula_spec`, `Carpinus_betulus`, `Picea_abies`, `Abies_alba`, `Pseudotsuga_menziesii`, `Larix_decidua`, `Pinus_sylvestris` (`code/synth_essences.py:253-255`). `Quercus_spec` et `Betula_spec` sont au niveau du genre.
- **Réserves du dépôt lui-même** : les arbres « ne calent pas le tarif » ; arbres nus, section circulaire, pas de branches mortes ni de voisins (`resultats/synth_arbres/LISEZMOI.md:3-4,137-143`) ; les bornes d'architecture sont des « HYPOTHÈSES de départ » (`code/synth_essences.py:4-7`).

### Modèles architecturaux

**Oui**, appliqués par essence : **Troll** (hêtre, charme), **Rauh** (chênes, frêne, érable sycomore, pin sylvestre, bouleau), **Massart** (épicéa, sapin, douglas, mélèze) (`code/synth_essences.py:9-19`). Statut des sources, tel que le dépôt le dit (`resultats/synth_arbres/LISEZMOI.md:120-132`) : hêtre, chênes, frêne, sapin **sourcés** ; érable sourcé avec nuance ; pin sourcé au niveau du genre, QSM ambigus ; charme et bouleau **peu sourcés** ; épicéa **non établi** ; douglas **sans source** ; mélèze **contredit** par la seule source et par 5 QSM, conservé par choix de Pascal le 20/11/2026. Hallé, Oldeman et Tomlinson 1978 **non consultés** (l.118). Le fichier `donnees/modeles_architecturaux_sources.csv` existe ; je ne l'ai pas ouvert.

### Allométries `hcb` et `cw`

Elles sont dans `code/synth_calage.py` et `resultats/synth_arbres/bornes_dimensions.csv` (coefficients par essence, 11 lignes) :

| Grandeur | Forme | Coefficients | Données |
|---|---|---|---|
| `H` | `H = 1,3 + H_a (1 − exp(−D/H_c))`, résidu sur `ln H` | `H_a`, `H_c` par essence | arbres TLS BioDiv |
| `hcb` (`hbh_m`) | `hcb = H (1 − CR)`, `CR = CR_a + CR_b ln D`, tiré avec résidu et borné à [0,20 ; 0,92] | `CR_a`, `CR_b`, `sd_CR` par essence | idem ; `hcb` du nuage calibrée sur Weiser 2022 (R² 0,91, n = 38), transfert aux nuages BioDiv **non vérifié** (`code/nemeton_hcb_biodiv.py:10-14`) |
| « largeur » de houppier | `ln E = R_a + R_b ln D`, `E` = **étendue maximale** : distance horizontale du pied au point de branche le plus éloigné | `R_a`, `R_b`, `sd_lnR` | idem |

Il **n'existe pas de variable `cw`** dans le dépôt : la grandeur disponible est l'étendue maximale `E` (un rayon). Que `cw = 2 E` ne figure nulle part : à décider (voir questions). Les résidus de `H`, `CR` et `ln E` sont corrélés (`r_H_CR`, `r_H_R`, `r_CR_R`) et le générateur les tire ensemble (`code/synth_population.py:75-101`). Les essences à moins de 30 arbres (bouleau, sapin, douglas, mélèze) reprennent la forme du hêtre ou de l'épicéa, décalée (`code/synth_calage.py:28-30` ; `bornes_dimensions.csv`, colonne `source`). **Exemples de calcul simple, non une mesure** : hêtre à D = 30 cm : `CR` ≈ 0,69 (hcb ≈ 0,31 H), `E` ≈ 4,7 m ; épicéa à D = 30 cm : `CR` ≈ 0,73 (hcb ≈ 0,27 H), `E` ≈ 3,0 m.

### Tarif volume, biomasse et carbone

- **Entrées :** essence, `DBH_cm`, `H_m`. **Sorties** (`resultats/tarif_v5/tables_tarif_v5.csv:1`) : `V_m3` (compartiment tige ou aérien total), `V_aerien_total_m3`, `V_sup7_m3`, `V_sup20_m3`, `V_sup30_m3`, `rho_kg_m3`, `biomasse_t`, `carbone_t`, `CO2_t`, bornes `CO2_IP90_bas`, `CO2_IP90_haut` (`code/nemeton_tarif_v5.py:314-320`).
- **Forme feuillus :** `ln V = ln(π/4·D²H) + a + b ln(D/30) + c ln(H/25)` (`README.md:18`), coefficients dans `resultats/tarif_v5/coefficients_feuillus_v5.csv` pour hêtre, chênes, érable, charme, frêne, bouleau. **Résineux :** profil de tige et expansion `E(D)` par essence (`code/nemeton_tarif_v5.py:77-90`) ; sapin, mélèze et douglas **provisoires**.
- **Carbone :** fraction 0,488 (feuillus) et 0,508 (conifères), Thomas et Martin 2012 (`code/tarif_v0_src/nemeton_tarif_v0.py:43`). **Infradensité :** XyloDensMap (non redistribuée) avec facteur arbre entier (hêtre 0,92, chênes 0,94, frêne 0,93) (`README.md:24-25`).
- **Unités de `D` dans la formule** (cm ou m) : non vérifiées dans le code lu.
- **Pas de fonction importable documentée** : les scripts se lancent en ligne de commande et lisent des chemins fixés sur la machine de Pascal (`/media/pascal/data1/...`, `README.md:67-68`). Le contrat « `params/tarif.parquet` » de la critique I7 est à construire à partir des CSV.

### Nomenclature des essences

Binôme latin avec soulignement (`Fagus_sylvatica`), et deux entrées de genre (`Quercus_spec`, `Betula_spec`). Ni `espar` ni TAXREF. Les passages nécessaires (`Quercus_spec` = espar 02 et 03 ? `Betula_spec` ?) ne sont écrits nulle part.

### Autres sorties utiles

`resultats/etage_b/` : `arbres_lidar.csv` (`treeID`, `dalle`, `x`, `y`, `H`, `cpa`), `arbres_lidar_volumes.csv` (+ `tfv`, `sp`, `strate_ifn`, `D`, `V_total`, `V_sup7`, `CO2_t`, `G`, `rho`), `allometrie_D.csv`, `allometrie_D_ifn.csv`, `mailles_1ha*.csv` (non ouvert). Fontainebleau, Lambert-93, vol des 7-8 mars 2024 hors feuilles (`resultats/etage_b/LISEZMOI.md:3`). C'est la **seule chaîne documentée « arbres détectés vers essence et d130 »** que j'ai trouvée.

---

## Nomenclature des essences : tableau de comparaison

| Dépôt | Code | Exemple hêtre | Source |
|---|---|---|---|
| nemeton (IFN) | `espar` 2 caractères | `09` | `inst/extdata/ifn_espar_correspondance.csv:10` |
| nemeton (P1) | 4 lettres | `FASY` | idem |
| nemeton (tolérances) | binôme snake_case | `fagus_sylvatica` | idem |
| nemeton (vidéo) | français snake_case | `hetre` | `inst/inventaire_video/essences_bdforet_v2.json:10` |
| sylvostation | `ESPAR` ; `CD_REF` TAXREF v13 ; config TAXREF 18 | `09` | `R/controle_essence.R:123-127,225` ; `config.yml:47-48` |
| typopeuplement | famille seulement | 1 = feuillus | `R/donnees_lidar.R:19` |
| tarif-nemeton | binôme avec soulignement | `Fagus_sylvatica` | `code/synth_essences.py:58` |
| sylvigenese (critique I5) | `espar` et `CD_REF` TAXREF figés | | `docs/critique-brief-contradicteur.md:30` |

Le seul pivot commun est le **nom latin**, et seul nemeton en tient une table.

## Licences (récapitulatif)

| Dépôt | Licence | Remarque |
|---|---|---|
| nemeton | GPL-3 | `nemetonshiny` (interface) est sous EUPL-1.2 (`README.md:229`) ; données tierces dans `inst/NOTICE` |
| sylvostation | GPL (>= 3) | libellé du README : GPL-3 |
| typopeuplement | GPL-3 | |
| tarif-nemeton | **aucune** | dépôt privé ; Thomas et Martin 2012, XyloDensMap (non redistribuable, `README.md:79`), données TLS tierces (`README.md:70-79`) à examiner avant toute reprise |

## Ce qui manque : questions à Pascal

1. **Source de la hauteur de plafond.** Aucune des trois sources n'est « par essence, hauteur dominante atteignable » (BRIEF §4, `site_potential.tif`). Quel sens retenir : l'indice de station de nemeton (courbes reconstituées, 10 essences, demande l'âge), la fertilité IFN de sylvostation (table par essence et par type, pas un raster), ou la `h_pot` de typopeuplement (par famille, apprise sur le MNH, environ 10 % de dépassements par construction) ? Ou une nouvelle source (`nemetoncanopee`) ?
2. **Où prendre l'âge ?** nemeton P2 a besoin de l'âge, que le MNH ne donne pas (BD Forêt, inventaire). La règle d'état initial en dépend.
3. **Quelle entrée donne l'essence et le d130 par arbre ?** Chaîne « étage B » de tarif-nemeton (essence du type BD Forêt sous le sommet, d prédit par la hauteur) : acceptable pour un état initial, sachant que le d des feuillus est sous-estimé en vol hors feuilles et que `Quercus_spec` absorbe les mélanges ? Ou imposer l'inventaire vidéo (placettes seulement) ?
4. **Bandes de gradients.** Garder les noms `trophic`, `hydric`, `bioclim` et les contrats à ces noms, ou refaire de vraies bandes F, R, T d'Ellenberg ou EIVE ? Dans ce dernier cas : EIVE 1.0 n'est lu par aucun dépôt.
5. **Précision de l'IFN : 700 m ou 1 km ?** Les trois dépôts disent 700 m ; le CLAUDE.md dit 1 km. Et la garde de sylvostation est une liste de noms plus un seuil de 25 m de précision de point, non « toute résolution < 1 km » : quelle règle écrire pour `assert_no_fine_extract_on_ifn()` de sylvigenese ?
6. **Rayon de la placette IFN** pour le voisinage de concurrence (I4) : 15 m (typopeuplement, 706,9 m²) ou cercles de 6, 9 et 15 m par classe de diamètre (commentaire de tarif-nemeton) ? La source IGN n'a pas été lue.
7. **`cw`.** L'étendue maximale `E` de tarif-nemeton est un rayon ; `cw = 2 E` ? Ou une autre définition ? Et la base du houppier `hcb` suit la première branche vivante (houppiers « très longs », `LISEZMOI.md:140`) : est-ce la définition voulue ?
8. **Grille.** Trois mailles (20, 25, 26,6 m) : quel rééchantillonnage, par qui (`prepare`), avec quelle règle ? Le contrat ne peut pas supposer des rasters alignés.
9. **Licence de tarif-nemeton.** Le brief veut GPL-3 ; le dépôt n'a pas de licence. Quelle licence, et quels fichiers (CSV de coefficients, `synth_*.py`) peuvent entrer dans sylvigenese ?
10. **Branche `synth-arbres` et export glTF.** Existe-t-elle ailleurs que dans le clone ? Le BRIEF §9 la suppose.
11. **Table `essence_arbre` (inventaire vidéo) vers `espar`** : à produire (hors dépôts lus) ; idem `Quercus_spec`, `Betula_spec` vers `espar`.
12. **Régénération.** `regen_engines.R` ne donne aucun état initial de semis : l'état initial des cohortes vient-il du biome seul, comme le BRIEF §7 le suggère implicitement ?
13. **`simuler_itineraire.R` de nemeton** (16 occurrences de surface terrière, non lu) : un simulateur d'itinéraires sylvicoles existe-t-il déjà dans nemeton, et recoupe-t-il `simulate` ?

## Trois points au sol (à vérifier par Pascal sur le terrain)

1. **Un peuplement adulte fermé à âge connu (par exemple une parcelle de hêtre ou de sapin du Vercors, pilote de typopeuplement, ou du massif vosgien D11).** Lire dans le même pixel : la hauteur dominante au MNH, la `h_pot` de typopeuplement, et l'indice de station de nemeton à l'âge connu. Les trois « potentialités » donnent-elles des plafonds compatibles ? C'est le cas le plus sensible : B6, la règle « dépassement signalé », et la trajectoire de hauteur en dépendent.
2. **Une placette de 15 m dans un hêtre-chêne mélangé.** Compter les arbres dominants que le MNH détecte, relever leur essence et leur d130, puis comparer à ce que l'étage B de tarif-nemeton leur attribuerait (essence du type BD Forêt, d prédit). Contrôle de B2 : essence erronée par `Quercus_spec` des mélanges, d sous-estimé des feuillus, arbres dominés absents.
3. **Dix hêtres et dix épicéas de D proche de 30 cm.** Mesurer `hcb` et l'étendue horizontale du houppier (pied → branche la plus éloignée) et comparer aux prévisions de calcul simple : hêtre `hcb` ≈ 0,31 H et `E` ≈ 4,7 m ; épicéa `hcb` ≈ 0,27 H et `E` ≈ 3,0 m. Contrôle des allométries qu'utilisera `hcb` et `cw` dans `sim/trees.parquet`.

## Question de contrôle

Quelle décision cette donnée va-t-elle éclairer ? Elle éclaire **l'écriture des contrats d'entrée de `prepare` et de la règle d'état initial dans `docs/spec.md`, avant M0** : ce que nemeton fournit vraiment (polygones et placettes, pas de liste d'arbres pour tout le massif), où l'essence et le d130 des arbres détectés peuvent venir, ce que « potentialité » veut dire dans chaque source, et quelles règles de garde et de nomenclature reprendre.

## Ligne de journal proposée

`2026-11-24 | acquéreur | mission 008 : entrées externes décrites d'après les dépôts (docs/referentiels/entrees-externes.md et .csv). nemeton rend des polygones et des placettes, pas une liste d'arbres du massif ; aucune des trois sources ne fournit la hauteur de plafond par essence du BRIEF §4 ; sylvostation sort trophic, hydric, bioclim (Tichý, pas EIVE) ; tarif-nemeton n'exporte ni glTF ni LOD ni stades. 13 questions à Pascal.`

## Liste de contrôle

Passée, avec les points **non cochés** suivants.

1. **Sources (fichier et ligne) : coché avec réserves.** Chaque affirmation de ce document renvoie à un fichier et à une ligne dans le CSV ou dans le texte. **Non lu** : `docs/spec.md` et `docs/referentiels.md` de sylvostation (grep seulement), `docs/adr/0007` et `0008` de typopeuplement, `R/chaine.R`, `R/milieu.R`, `R/ser.R` de typopeuplement, `donnees/modeles_architecturaux_sources.csv`, PDF de méthodologie de tarif-nemeton (v2.23), `code/tarif_v0_src/`, vignettes et NEWS de nemeton, `R/simuler_itineraire.R`, `R/ifn_tarifs.R`, les fichiers binaires (GeoPackage, GeoTIFF, `.rda`, `.laz`).
2. **Décomptes complets : NON coché.** Pas d'outil d'exécution : les listes de fichiers viennent d'une recherche par motif, plafonnée à 100 résultats par appel (plusieurs listages tronqués). Les sorties de nemeton ne sont pas toutes listées : `st_write` et équivalents apparaissent dans 27 fichiers R que je n'ai pas tous ouverts ; je n'ai documenté que ceux qui touchent nos besoins (inventaire vidéo, houppiers, LiDAR, régénération, massif de démonstration). Les sorties des modules FORDEAD, RECONFORT, FAST, monitoring ne sont pas décrites. Pour sylvostation, la liste des CSV écrits en mode réel vient de `_targets.R:843-866`, non du dossier de sortie (aucune exécution). Les colonnes des tables de nemeton `ifn_*` ne sont listées que par leur en-tête.
3. **Termes et unités exacts : coché avec réserves.** Les termes sont repris tels que les fichiers les nomment (`dbh_cm`, `h_m`, `loc_precision_m`, `h_pot`…). **Non vérifiés** : unité de `C13` (circonférence, cm ?), échelle numérique des bandes `trophic`, `hydric`, `bioclim`, type GDAL et `nodata` des rasters de sylvostation, CRS des rasters ONF lus par typopeuplement, unité de `D` dans la formule du tarif, unités de `ifn_production_ser.csv`, rayon IGN des cercles de l'IFN.
4. **Statut dit tel quel : coché.** tarif-nemeton : « recherche en cours », sans licence. typopeuplement : aucune carte H10 publiée, `h_pot` livrable conditionnel. sylvostation : démonstration synthétique par défaut, mode réel non rejoué ici. nemeton : jeu de démonstration synthétique, 41 contre 44 indicateurs. Rien n'a été exécuté.
