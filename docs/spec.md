# sylvigenese — spécification de la v1

> Version 1.1 du 24/11/2026, rédigée par Claude (orchestrateur), **par délégation de Pascal**
> (`pilotage/equipe.md`).
>
> Sources :
> - le brief retenu (`docs/BRIEF.md`) ;
> - les ADR 0001 à 0003 ;
> - les arbitrages de la critique du brief (`docs/critique-brief-contradicteur.md`) ;
> - les entrées réelles décrites par la mission 008 (`docs/referentiels/entrees-externes.md`) ;
> - la critique de la spec v1.0 (`docs/critique-spec-contradicteur.md`), dont tous les points
>   sont retenus.
>
> Toute valeur écologique de ce texte est sourcée, ou marquée **provisoire**.

## 1. Parcours utilisateur

**Pascal, ou un utilisateur de nemeton, sur un massif :**

1. Il pose ses entrées (§3) dans `data/<zone>/inputs/`. Pour nemeton, il exporte d'abord ses
   polygones au contrat `nemeton_stands.gpkg`, avec la petite fonction R fournie par
   `prepare`.
2. Il lance `make all ZONE=<zone>`, qui lit `config.yml`. Le massif test se rejoue en moins de
   30 min, avec `dynamics` déjà ajusté et versionné.
3. Il lit les rapports, en HTML :
   - `rapport_biomes.html` : cellules sans type de végétation, comblements, peuplements
     mono-essence ;
   - `rapport_hauteur.html` : dépassements du plafond ;
   - `rapport_dynamics.html` : validation, limites connues ;
   - `rapport_simulation.html` : contrôles, valeurs mises à zéro, part des paramètres
     provisoires.
4. Il ouvre la vue web (servie en local). Il fait défiler les années et lit la fiche d'une
   cellule : station, type de végétation, composition, volume, carbone, et la mention
   « provisoire » le cas échéant.
5. La fiche affiche une commande à copier,
   `viewer-massif -- --x <X> --y <Y> --year <A>`, qui ouvre la vue massif aux mêmes
   coordonnées. Un navigateur ne peut pas lancer une application locale.

**À l'échelle d'une SER**, le parcours est le même, avec `simulate --level ser`.

## 2. Modules, langages, frontières

| Module | Langage | Entrées | Sorties |
|---|---|---|---|
| `prepare` | R (package + `targets`) | `inputs/` (§3) | `grid.tif`, `dtm.tif`, `forest_mask.tif`, `ser.tif` (+ `.csv`), `h0.tif`, `chm_date.tif`, `station_gradients.tif`, `station_type.tif` (+ `.csv`), `site_potential.tif` (+ `.csv`), `stand_map.tif` (+ `.csv`), `ifn/`, `stands.parquet` |
| `prepare`, étape `trees` | R | sorties de `prepare`, `vegetation_map.tif` (+ `.csv`), `params/allometry.parquet` | `trees_init/`, `rapport_arbres.html` |
| `import_tarif` | Python | dossier de tarif-nemeton, `external.tarif_nemeton_dir` dans `config.yml` | `params/tarif.parquet`, `params/allometry.parquet` |
| `biomes` | R + YAML | sorties de `prepare`, `biomes/*.yml` | `vegetation_map.tif` (+ `.csv`), `rapport_biomes.html` |
| `dynamics` | R (`mgcv`) | `ifn/` | `params/{growth,mortality,recruitment,height_curve}.parquet`, `rapport_dynamics.html` |
| `simulate` | Rust (ADR 0001) | ce qui précède, `config.yml` | `sim/trees/year=AAAA/*.parquet`, `sim/cells/year=AAAA/*.parquet`, `sim/run.json` |
| `post` | Python | `sim/`, `params/tarif.parquet` | `sim/summary.parquet`, avec la clé (cellule, année, essence) |
| `assets` | Python | `sim/`, `params/allometry.parquet`, segments de tarif-nemeton (s'ils existent) | `assets/trees/*.glb`, `tiles/<year>/tileset.json`, `web/cells/<tuile>.json`, `web/rasters/*.tif` (COG), `massif/<bloc>.json` |
| `viewer-web` | TypeScript, iTowns | `tiles/`, `web/` | page web locale |
| `viewer-massif` | Godot 4.6.x, GDScript | `massif/`, `assets/trees/` | application |

**Règles :**
- Aucun module n'importe le code d'un autre. Les outils transverses sans logique métier
  (`R/config.R`, `R/validateur.R`, `R/commun.R` : rapports HTML, lecture en EPSG:2154,
  écriture des grilles et des tables de catégories) sont communs à tous les modules R.
- L'étape `trees` appartient à `prepare` mais tourne après `biomes`, dont elle lit la carte
  des types de végétation pour les arbres hors polygone (§4.2). Ordre : `prepare` → `biomes`
  → `trees` (décision de l'orchestrateur, par délégation, du 24/11/2026).
- **Contrats** (ADR 0002), en trois couches :
  - Table Schema (Frictionless, version figée) pour le Parquet et le CSV ;
  - JSON Schema pour le YAML et le JSON, avec les schémas officiels de CesiumGS pour
    `tileset.json` ;
  - `contracts/geotiff_profile.json` pour les rasters.
- **Un seul validateur** en ligne de commande, `contracts/validate` (Python, pyarrow et
  frictionless-py). Chaque module l'appelle en sous-processus, à la fin de son travail ;
  `prepare` l'appelle aussi à l'entrée. C'est un passage par fichiers, pas un import. Rust
  vérifie en plus le profil GeoTIFF à la lecture.
- Le volume, la biomasse et le carbone sont calculés par `post`, en post-traitement.

## 3. Entrées externes

| Fichier (`inputs/`) | Source | Contenu |
|---|---|---|
| `nemeton_stands.gpkg`, couche `stands` | nemeton : export R fourni par `prepare`, car nemeton rend un objet `sf` sans export | `stand_id`, `species_espar` (une essence par polygone), `dbh_cm`, `height_m`, `density_ha`, `age_yr`, `source` (`inventaire`, `synthetic_ml`, …), `stand_id_source`. EPSG:2154. |
| `inventaire_video.gpkg` (facultatif) | nemeton, schéma 1.7.0 | placettes de 15 m : arbres avec `dbh_cm`, `h_m`, `essence_arbre`, `h_source`, `dbh_source` |
| `chm.tif` | MNH LiDAR HD IGN, 50 cm | gardé à sa résolution d'origine, il n'entre jamais dans `simulate` |
| `dtm.tif` | MNT LiDAR HD, ou RGE ALTI | altitude NGF-IGN69 |
| `lidar_tiles.gpkg` | IGN | une dalle par entité, avec sa date de vol |
| `forest_mask.gpkg` | définition de la forêt par l'IFN | masque forestier |
| `ser.gpkg` | IGN, sylvoécorégions et alluvions, sous la forme brute | `ser_code`, code de SER tel que publié par l'IGN, **L1 à L5 compris** pour les alluvions. C'est `prepare` qui produit la SER sous-jacente (`ser.tif` et sa table : `ser_code` jamais L1 à L5, `alluvium_code` ∈ {L1 … L5} ou NULL ; une valeur de `ser.tif` par couple distinct, de sorte que chaque cellule garde son origine), §7 |
| `station_gradients.tif`, `station_type.tif`, `fertilite.csv` | sylvostation | `trophic`, `hydric`, `bioclim` (Tichý 2023) ; type de station ; H0 à 50 ans par essence et par type |
| `h_pot.tif` | typopeuplement | plafond par famille d'essences. **S'il manque : erreur, code 2.** |
| `ifn/` (brut) | IFN, données brutes | ajustement de `dynamics` ; coordonnées floutées à environ 700 m |
| dossier tarif-nemeton | `external.tarif_nemeton_dir` | lu seulement par `import_tarif`. **Jamais copié dans le dépôt.** Sa licence est réservée à Pascal. |

**Jeu fictif (M0) :**
- Il a les mêmes formats et les mêmes noms de colonnes que les sources réelles, avec des
  mailles différentes : gradients à 20 m, `h_pot` à 26,6 m.
- Ses paramètres de tarif et d'allométrie sont **synthétiques** et marqués
  `provisoire: true`.
- La CI ne touche jamais aux dépôts privés.

## 4. État initial

1. **Essence et densité** : celles du polygone nemeton qui contient la cellule ou l'arbre.
   Un polygone porte une seule essence : il est mono-essence, et le rapport le dit.
2. **Hors polygone nemeton** : l'essence vient du type de végétation, avec
   `species_source = vegetation_type`, et la cellule est signalée. La BD Forêt v2 n'est pas
   utilisée, car sylvostation l'a désactivée pour une licence contradictoire.
3. **Arbres détectés** : détection sur `chm.tif` à 50 cm, puis segmentation des houppiers
   et surface projetée de chaque houppier (`crown_area`, m²), comme l'étage B de
   tarif-nemeton (`code/etage_b_arbres_lidar.R`). Le d130 est donné par
   `ln D = a + b ln H + c ln CPA` (`code/etage_b_allometrie_D.py`), réécrite dans `prepare`
   avec citation (décision de Pascal du 24/11/2026 : le terme du houppier est réintégré).
   Les coefficients viennent de `params/allometry.parquet`. Pour une essence sans
   coefficient `c`, le modèle `ln D = a + b ln H` (calé sur l'IFN,
   `code/etage_b_allometrie_ifn.py`) s'applique, et `d130_source` le dit ; une essence sans
   aucun coefficient est une erreur explicite. Réserve de tarif-nemeton : la surface de
   houppier segmentée dans un MNH aéroporté n'est pas celle mesurée au TLS, d'où le statut
   provisoire. Les colonnes `species_source` et `d130_source` sont remplies.
4. **Hauteur** : celle du MNH à la date de vol (`chm_date`, en jours depuis le 1970-01-01),
   avancée jusqu'à `t0` par la courbe de hauteur.
5. **Polygones `source = synthetic_ml`** : leur hauteur vient déjà du MNH. Le MNH n'est pas
   compté une seconde fois, et le rapport le signale.
6. En v1, le niveau massif ne contient que les **arbres détectés**. Les arbres dominés
   relèvent des cohortes de la cellule.
7. **Cohortes de semis initiales** : tirées du type de végétation.

## 5. Hauteur

- **H0 par cellule de 25 m** (`h0.tif`) : même estimateur que le `h_dom` sur lequel
  typopeuplement apprend `h_pot`. Il est à lire dans son code. En attendant, le percentile 95
  du MNH est **provisoire**.
- **Plafond** : `h_pot` de typopeuplement, attribué par famille d'essences.
- **Courbe** : forme différentielle autonome de Chapman-Richards, qui n'a pas besoin de l'âge.
  nemeton l'utilise déjà (`data-raw/site_index_curves.R`). Ses paramètres sont calés sur la
  fertilité de sylvostation. Elle est **provisoire** (BRIEF §14.5).
- **Au-dessus du plafond** : on écrit `si dH < 0 alors dH = 0`, sans fonction `min`. Chaque
  cas est une ligne de `rapport_hauteur.html`. Environ 10 % des cas sont attendus, par
  construction de `h_pot`.
- **Hauteur d'un arbre** : elle se déduit de H0 et du rang de l'arbre en diamètre.

## 6. Dynamique

- **Variables à l'ajustement et en simulation :**

  | Variable | À l'ajustement (IFN) | En simulation |
  |---|---|---|
  | `trophic` | flore de la placette (sylvostation, `R/placettes.R`) | raster prédit |
  | `hydric`, `bioclim` | `coarse_*_700m` | rasters |
  | concurrence | surface terrière de la placette, chaque arbre pondéré par l'inverse de la surface de son cercle (6, 9 ou 15 m selon sa classe de dimension, IMOT 2025 p. 61) | surface terrière dans un disque de 15 m (706,9 m²), avec tous les arbres simulés, et surface terrière des arbres plus gros |

  Le décalage entre les deux colonnes est une **limite connue**, écrite dans
  `rapport_dynamics.html`. Un test vérifie que la garde IFN refuse `station_gradients.tif`
  aux placettes.
- **Données d'ajustement** (`docs/referentiels/ifn-dynamique.md`, règles provisoires décidées le
  25/11/2026 par délégation, à vérifier sur un export réel en M2b) :
  - les deux visites d'un point se joignent par `IDP` et le numéro d'arbre `A` ; la campagne
    de 2e visite vaut celle de la 1re plus 5 ; `VISITE` vient de `PLACETTE.csv` ; la jointure
    est faite par `dynamics`, `prepare` garde une ligne par visite ;
  - accroissement : `IR5` (cumul de 5 cernes, en m) quand il existe ; la différence de `C13`
    entre visites sert de contrôle, écrit au rapport ;
  - mortalité : population à risque = arbres vivants sur pied à la 1re visite (`VEGET` = 0) ;
    mort = codes de mort naturelle de `VEGET5` (selon la campagne) ; arbres coupés (6, 7),
    non retrouvés (N) ou perdus (T) : retirés de la population et comptés au rapport ;
    placettes à incident (`NINCID` ≠ 0), défrichées (`DEF5` ≥ 1) ou plantées (`INSTP5` = 1) :
    écartées et comptées ; `PRELEV5`, sans modalités documentées, est gardée et signalée ;
    une placette sans valeur de station est exclue de l'ajustement et comptée ;
  - recrutement : arbres de 2e visite sans 1re visite et recensables (`C13` ≥ 0,235 m) ; leur
    poids suit `W` de l'export, sinon il est signalé, jamais deviné ;
  - intervalle : `DATEPOINT` des deux visites s'il existe, sinon 5 ans, et le rapport le dit ;
  - station d'un arbre revu : flore et écologie de la 1re visite (seules relevées) ; décalage
    écrit au rapport ;
  - valeurs indicatrices : Tichý et al. 2023 (Zenodo 10.5281/zenodo.7427088), comme
    sylvostation ; leur licence reste à confirmer par Pascal avant tout usage hors du jeu fictif.
- **Garde IFN** : celle de sylvostation, reprise telle quelle (`R/utils.R`). Toute source
  qui n'est pas préfixée `coarse_` est traitée comme fine, et le seuil de précision d'un point
  est de 25 m.
- **Recrutement** :
  - M3 : modèle IFN direct ;
  - M5 : cohortes calées sur ce modèle. Le `tree_id` d'une recrue est (cellule, année, rang).
- **Gestion** : `management: none`.
- **Aléa** : `u(seed, year, entity, species, draw_kind)`, sur le principe du générateur à
  compteur du banc (`bench/SPEC.md` §2). Sorties identiques au bit près quel que soit le
  nombre de fils.
- **Contrôles** :
  - une valeur telle que |Q| < 1e-9 × max(Q), due à l'arrondi de la FFT, est mise à zéro et
    comptée dans `run.json` ;
  - au-delà : arrêt, code 3, message en français.
- **Codes de sortie** : 2 pour une entrée refusée, 3 pour un contrôle échoué, 4 pour une
  mémoire insuffisante. Avant le premier pas, le moteur estime la mémoire nécessaire et la
  compare à `MemAvailable`. Le noyau Linux tue un programme qui sur-alloue (code 137) : le
  moteur doit donc refuser avant.

## 7. Grille et emprise

- Une seule grille de simulation, à **25 m**, en EPSG:2154, définie par `grid.tif`.
- **Rééchantillonnage** :
  - bilinéaire pour les entrées continues de maille proche (20 et 26,6 m) ;
  - mode pour les entrées catégorielles ;
  - le MNH à 50 cm n'est **jamais** rééchantillonné : `prepare` l'agrège en `h0.tif`.
- **Zone tampon** de la largeur du noyau de dispersion. Ses cellules sont sources de graines
  seulement, et le bord est absorbant.
- **Alluvions** : rattachées à la SER sous-jacente (`ser_code`), et repérées par `alluvium_code`. Dans la couche IGN brute, les alluvions forment leurs propres SER (L1 à L5). `prepare` leur attribue la SER voisine qui partage avec elles la plus longue frontière, et chaque attribution est une ligne de rapport (décision de Pascal du 24/11/2026).
- **YAML** : le contrat refuse les écritures qui se lisent différemment en YAML 1.1 et en YAML 1.2 (entiers à zéro de tête, `yes`, `no`, `on`, `off`, `y`, `n`), pour que tous les modules lisent la même valeur.

## 8. Nomenclatures

- **Essences** : `espar`, toujours en chaîne de caractères, avec son zéro de tête. La table
  `contracts/species.csv` fait la correspondance avec nemeton, tarif-nemeton et TAXREF
  (CD_REF, **v18**, comme sylvostation ; les fichiers IFN en v13 sont convertis). La règle de
  `Quercus_spec` est écrite dans cette table.
- **Valeurs indicatrices** : Tichý et al. 2023. **Tolérance à l'ombre** : Niinemets et
  Valladares 2006.
- **Types de végétation** : `vegetation_type`.
- **Catégories** (station, végétation) : codées par leur **nom**, avec une table `.csv`.
  Jamais par un indice qui dépend de l'ordre.
- **Stades** : énumération `stage` dans `contracts/`, de quatre valeurs tirées de la position
  sur la courbe de hauteur (BRIEF §6.3). Elle est **provisoire**.

## 9. Formats

- **Profil GeoTIFF** (`contracts/geotiff_profile.json`) :
  - tuiles de 256 × 256, entrelacement PLANARCONFIG=2 ;
  - compression Deflate ou aucune, PREDICTOR 1 ou 2 ;
  - valeurs en Float32 ou UInt16 ;
  - nodata dans la balise 42113, GeoKey EPSG 2154 obligatoire ;
  - BigTIFF refusé ;
  - aligné sur `grid.tif`.

  Des fichiers d'essai écrits par `terra` et par `rasterio` sont relus par les tests Rust.
- **Parquet** : partitions `year=AAAA`.
- **3D** :
  - glTF 2.0, un fichier par niveau de détail ;
  - 3D Tiles 1.1 avec instanciation, ou i3dm en repli, selon l'examen du code d'iTowns (mission
    de M0) ;
  - conversion de l'altitude NGF-IGN69 en hauteur ellipsoïdale avec la grille RAF20, dont le
    chemin est donné dans `config.yml`. Si elle manque : erreur ;
  - `massif/*.json` reste en NGF-IGN69, avec son origine locale.
- **Rasters web** : COG avec aperçus.
- **Fiche de cellule** : `web/cells/<tuile>.json`.
- **`config.yml`** : JSON Schema.

## 10. Statut « provisoire »

- Chaque paramètre porte `provisoire` et sa source.
- `run.json` donne la part des paramètres provisoires.
- Les vues affichent « résultat provisoire » dès qu'un paramètre utilisé l'est.
- Toute diffusion hors du dépôt est réservée à Pascal.

## 11. Critères d'acceptation

> Ordre (décision de Pascal du 25/11/2026) : M2a, puis une **tranche de M4a sur l'état
> initial** (vue iTowns des arbres de `trees_init`, de la carte des types de végétation et de
> la fiche de cellule, sans simulation), puis M3a, la suite de M4a, M5a et M6a.

| Jalon | a (agents, jeu fictif) | b (avec Pascal) |
|---|---|---|
| M0 | Validateur testé sur un fichier conforme et un fichier fautif par contrat. CI verte, durée relevée par la CI elle-même. Squelette des modules. `.claude/test-command`. | — |
| M1 | `prepare` et `biomes` sur le jeu fictif. Aucune cellule forestière sans type de végétation qui ne soit pas signalée. Garde IFN testée. | Massif test réel. |
| M2 | Ajustement sur un extrait IFN. Validation croisée spatiale par blocs. Rapport par essence. | SER pilote : RMSE inférieure à celle du modèle nul. |
| M3 | 100 ans sur le massif fictif. Identité entre 1 et N fils. Contrôles. Non-régression. | Validation à 5 ans sur les placettes revisitées. Surface terrière et tiges par hectare entre les quantiles 5 et 95 % de l'IFN. |
| M4 | 100 000 instances chargées et dessinées (comptées par l'API). Images par seconde relevées comme référence locale, sans seuil. | Médiane d'au moins 30 images par seconde sur la machine et le navigateur de Pascal. |
| M5 | Mesure à N = 1000, 2000 et 4000 et extrapolation (lois de `bench/results/RESULTATS.md` §6). Estimation de mémoire du moteur à moins de 10 % de la mémoire résidente mesurée. | SER pilote ; recrutement dans l'intervalle de confiance IFN ; comparaison avec MARGOT. |
| M6 | Godot `--headless --import` et tests GUT. Export seulement si les modèles d'export sont téléchargeables ; sinon, reporté en M6b et signalé. | Sur le PC de Pascal. |

## 12. Besoins en référentiels

- Documentation IFN : établie (`docs/referentiels/ifn-placettes.md`, `docs/referentiels/ifn-dynamique.md`). **`C13` est en mètres dans l'export des données brutes** (`metadonnees.csv` l. 35 et 203), alors que l'IMOT le saisit en millimètres : `d130 = C13 × 100 / π` en cm, et les bornes des cercles valent 0,235, 0,705 et 1,175 m (décision du 25/11/2026).
- Table `species.csv`.
- Estimateur `h_dom` de typopeuplement.
- Prise en charge de l'instanciation glTF dans iTowns.
- Disponibilité de la grille RAF20.
- MARGOT.
- Licences des données à citer dans les vues.

## 13. Hors périmètre de la v1

- L'arbre par arbre à l'échelle d'une SER.
- Les scénarios climatiques.
- La sylviculture.
- Le rendu photoréaliste.
- La plateforme multi-utilisateurs.
- La vue France.
- L'hébergement public.
