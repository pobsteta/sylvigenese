# sylvigenese — spécification de la v1

> Rédigée le 24/11/2026 par Claude (orchestrateur), **par délégation de Pascal**
> (`pilotage/equipe.md`). Elle part du brief retenu (`docs/BRIEF.md`), de l'ADR 0001, des
> arbitrages de la critique du brief (`docs/critique-brief-contradicteur.md`) et des entrées
> réelles décrites par la mission 008 (`docs/referentiels/entrees-externes.md`).
> Toute valeur écologique de ce texte est soit sourcée, soit marquée **provisoire**.

## 1. Parcours utilisateur

**Pascal, ou un utilisateur de nemeton, sur un massif :**
1. Il pose dans `data/<zone>/inputs/` les sorties de nemeton du massif (polygones de
   peuplement), le MNH LiDAR HD avec ses dates de vol, et les sorties de sylvostation et de
   typopeuplement pour la SER.
2. Il lance `make all ZONE=<zone>`, ou les commandes de chaque module, depuis `config.yml`.
   Le massif test se rejoue en moins de 30 min, avec `dynamics` déjà ajusté et versionné.
3. Il ouvre les rapports :
   - `rapport_biomes.html` : cellules sans type de végétation, comblements ;
   - `rapport_hauteur.html` : dépassements du plafond ;
   - `rapport_dynamics.html` : validation par essence ;
   - `rapport_simulation.html` : contrôles, part des paramètres provisoires.
4. Il ouvre la vue web : il fait défiler les années, survole une cellule et lit sa fiche
   (station, type de végétation, composition, volume, carbone, mention « provisoire » le cas
   échéant).
5. Depuis une cellule, il ouvre la vue massif (Godot) aux mêmes coordonnées et s'y déplace,
   jusqu'à l'herbe et aux semis autour de la caméra.

**À l'échelle d'une SER :** même parcours, avec la grille de cohortes (`simulate --level ser`)
et la vue web à l'échelle de la SER.

## 2. Modules, langages, frontières

| Module | Langage | Entrées | Sorties |
|---|---|---|---|
| `prepare` | R (package + `targets`) | `inputs/` (externes, §3) | `grid.tif`, `chm.tif`, `chm_date.tif`, `station_gradients.tif`, `station_type.tif`, `site_potential.tif` + `.csv`, `trees_init/`, `ifn/`, `stands.parquet` |
| `biomes` | R + YAML | sorties de `prepare`, `biomes/*.yml` | `vegetation_map.tif` + `.csv`, `rapport_biomes.html` |
| `dynamics` | R (`mgcv`) | `ifn/` | `params/{growth,mortality,recruitment,height_curve,allometry,tarif}.parquet`, `rapport_dynamics.html` |
| `simulate` | Rust (ADR 0001) | tout ce qui précède, `config.yml` | `sim/trees/year=AAAA/*.parquet`, `sim/cells/year=AAAA/*.parquet`, `sim/run.json` |
| `post` | Python | `sim/`, `params/tarif.parquet` | `sim/summary.parquet` (volume, biomasse, carbone) |
| `assets` | Python | `sim/`, segments de tarif-nemeton | `assets/trees/*.glb`, `tiles/<year>/tileset.json`, `massif/<bloc>.json` |
| `viewer-web` | TypeScript, iTowns | `tiles/`, rasters | page web locale |
| `viewer-massif` | Godot 4, GDScript | `massif/`, `assets/trees/` | application |

**Règles :**
- Les modules ne se parlent que par fichiers. Aucun module n'importe le code d'un autre.
- Chaque contrat a un schéma dans `contracts/` au format Frictionless Table Schema, avec un
  `schema_version` et les unités.
- Un validateur est appelé à la fin de chaque module, et à l'entrée de `prepare` pour les
  entrées externes.
- Le volume, la biomasse et le carbone sont calculés par `post`, qui applique le tarif après
  la simulation (BRIEF §6). `simulate` ne les calcule pas.

## 3. Entrées externes (d'après la mission 008)

| Source | Ce qui est lu | Règle |
|---|---|---|
| nemeton | Polygones de peuplement : essence, `dbh` moyen, hauteur, densité, âge (GeoPackage, EPSG:2154). Placettes de l'inventaire vidéo (`inventaire_video.gpkg`, schéma 1.7.0) quand elles existent. | **Entrée principale.** Elle fixe la composition et la densité de départ par polygone. |
| MNH LiDAR HD | MNH IGN déjà produit (GeoTIFF, 50 cm), et dates de vol par dalle | Il donne la hauteur actuelle et H0 par cellule. Les trous ZICAD sont signalés. |
| tarif-nemeton | Chaîne « étage B » : essence BD Forêt v2 sous le sommet, `ln D = a + b ln H (+ c ln CPA)`. Allométries `hcb = H(1 − CR)`, étendue E. Tarif (essence, D, H) vers volume, biomasse et carbone. Segments de troncs de cône (`synth_arbres.py`). | Essence et d130 des arbres détectés, `hcb` et `cw = 2E`, tarif. **Lu à l'exécution, jamais copié** tant que sa licence n'est pas fixée par Pascal. |
| sylvostation | Bandes `trophic`, `hydric`, `bioclim` (Tichý 2023), type de station, `fertilite.csv` (H0 à 50 ans par essence et par type) | Gradients et forme de la courbe de hauteur (provisoire). |
| typopeuplement | `h_pot` par famille d'essences, appris sur le MNH | **Plafond de hauteur.** Les dépassements, environ 10 % par construction, sont signalés et jamais corrigés. |
| IFN | Données brutes, dont `IGN_DB_documentation_generale.pdf` et `metadonnees.csv` | Ajustement de `dynamics`. Coordonnées floutées à environ 700 m. Garde de sylvostation reprise telle quelle. |

## 4. État initial (règle de priorité)

Pour chaque cellule de 25 m et chaque arbre détecté :
1. **Composition et densité** : polygone nemeton qui contient la cellule.
2. **Hauteur** : celle du MNH à la date de vol `chm_date`, avancée jusqu'à l'année de départ
   `t0` par la courbe de hauteur.
3. **Essence et d130 des arbres détectés** : chaîne « étage B ». Colonnes `species_source` et
   `d130_source` (`nemeton`, `tarif_etage_b`, `provisoire`).
4. **Ce qui manque** est comblé par le type de végétation (`biomes/*.yml`). Chaque comblement
   est une ligne de `rapport_biomes.html`.
5. En v1, le niveau massif ne contient que les **arbres détectés**. Les arbres dominés relèvent
   des cohortes de la cellule, et le rapport le dit.
6. Les cohortes de semis initiales sont tirées du type de végétation, car `regen_engines.R`
   de nemeton ne fournit pas d'état de semis.

## 5. Hauteur (BRIEF §6, précisé)

- **H0 par cellule** : percentile 95 du MNH sur la cellule. **Provisoire**, à sourcer.
- **Plafond par essence et par cellule** : `h_pot` de typopeuplement, attribué par famille.
- **Courbe** : `dH/dt = r_s · (1 − H/Hmax)`. Le paramètre `r_s` se cale sur la fertilité IFN
  de sylvostation (H0 à 50 ans par essence) et reste **provisoire** tant que sa forme n'est
  pas sourcée (BRIEF §14.5 ; la courbe non asymptotique de Bontemps et Duplat reste une
  alternative).
- **Hauteur au-dessus du plafond** : accroissement en hauteur nul, plus une ligne de
  `rapport_hauteur.html`.
- **Hauteur d'un arbre** : elle se déduit de H0 de sa cellule et de son rang en diamètre
  (BRIEF §6.2).

## 6. Dynamique (`dynamics`, `simulate`)

- **Mêmes variables** à l'ajustement et en simulation :
  - `d130` ;
  - surface terrière dans un **disque de 15 m (706,9 m²)**, équivalent à la placette IFN
    (provisoire jusqu'à lecture de la source IGN) ;
  - surface terrière des arbres plus gros ;
  - `trophic`, `hydric`, `bioclim` ;
  - SER.
- **Recrutement** :
  - M3 : modèle IFN direct (`params/recruitment.parquet`) ;
  - M5 : remplacé par les cohortes de régénération, calées sur ce modèle.
- **Gestion** : `management: none`, seule valeur de la v1 (valeur sacrifiée, BRIEF).
- **Aléa** : générateur à compteur adressé par (graine, année, cellule ou arbre, essence),
  comme dans le banc (`bench/SPEC.md` §2). Réductions dans un ordre fixe. Sorties identiques au
  bit près quel que soit le nombre de fils.
- **Contrôle à chaque pas** : NaN, valeurs négatives, bornes. Il provoque un arrêt avec un
  message en français et un code de sortie 3. Les codes de sortie sont ceux du banc :
  2 pour une entrée refusée, 3 pour un contrôle échoué, 4 pour un manque de mémoire. Avant de
  démarrer, le moteur estime la mémoire nécessaire et refuse proprement si elle manque.

## 7. Grille et emprise

- Une seule grille, à **25 m**, en EPSG:2154, pour le massif comme pour la SER. Elle est
  définie par `grid.tif`.
- `prepare` rééchantillonne toutes les entrées sur cette grille : bilinéaire pour les
  données continues, mode pour les données catégorielles. Les mailles d'origine sont de 20,
  25 et 26,6 m.
- **Zone tampon** de la largeur du noyau de dispersion. Ses cellules sont sources de graines
  seulement. Le bord est absorbant.
- **Alluvions L1 à L5** : rattachées à la SER sous-jacente, avec un drapeau.

## 8. Nomenclatures

- Essences : code `espar` de l'IFN. Une table `contracts/species.csv` fait la correspondance
  avec les codes de nemeton (34 codes), de tarif-nemeton (`Quercus_spec`…) et avec TAXREF
  (CD_REF, version figée).
- Plantes du sous-bois : TAXREF CD_REF.
- Valeurs indicatrices : Tichý et al. 2023, comme sylvostation.
- Tolérance à l'ombre des semis : Niinemets et Valladares 2006.
- Types de végétation : `vegetation_type` (le « biome » du brief), avec un lien EUNIS quand
  la correspondance est sourcée.
- Stades : classes de développement de l'IFN.

## 9. Formats

- **GeoTIFF, profil fermé** :
  - tuilé, compression Deflate ou aucune ;
  - valeurs en Float32 ou UInt16, `nodata` explicite ;
  - aligné sur `grid.tif`.

  `simulate` le lit sans GDAL et ne reprojette rien.
- **Parquet** : partitions `year=AAAA`.
- **3D** :
  - glTF 2.0, un fichier par niveau de détail (`<espar>_<stade>_lod{0,1,2}.glb`) ;
  - 3D Tiles 1.1 avec `EXT_mesh_gpu_instancing`, après un essai au début de M4, avec repli
    sur i3dm ;
  - altitude NGF-IGN69, convertie en hauteur ellipsoïdale dans `assets` seulement.
- **Vue massif** : `assets` écrit, par bloc de 16 m, un JSON avec l'origine locale et la liste
  des instances, que Godot lit.
- **`config.yml`** : schéma JSON Schema dans `contracts/`.

## 10. Statut « provisoire »

Chaque paramètre porte `provisoire: true|false` et sa source. `sim/run.json` donne la part des
paramètres provisoires. Les fiches de la vue web et la vue massif affichent « résultat
provisoire » dès qu'un paramètre utilisé l'est. Toute diffusion hors du dépôt reste réservée
à Pascal.

## 11. Critères d'acceptation chiffrés

Les jalons a sont faits par les agents sur le jeu fictif. Les jalons b se font avec Pascal.

| Jalon | Critère a (agents) | Critère b (Pascal) |
|---|---|---|
| M0 | Validateurs verts sur le jeu fictif. CI verte en moins de 20 min. Les schémas couvrent toutes les entrées et sorties du §2. | — |
| M1 | `prepare` et `biomes` sur le jeu fictif. Aucune cellule forestière sans type de végétation qui ne soit pas signalée. Garde IFN testée. | Massif test réel. |
| M2 | Ajustement sur un extrait IFN réduit. Rapport par essence : biais, RMSE, domaine. Validation croisée spatiale par blocs. | SER pilote. RMSE inférieure à celle du modèle nul pour chaque essence retenue. |
| M3 | 100 ans sur le massif fictif. Identité entre 1 et N fils. Contrôles. Non-régression contre une référence versionnée. | Validation à 5 ans sur les placettes revisitées. Surface terrière et tiges par hectare entre les quantiles 5 et 95 % de l'IFN, à 100 ans, par SER, essence et stade. |
| M4 | 100 000 instances affichées. Médiane d'au moins 30 images par seconde, mesurée par un script Playwright sans interface (rendu logiciel, valeur de référence locale). | Même mesure sur la machine et le navigateur de Pascal. |
| M5 | SER fictive de taille C20 (48 M cellules) : mémoire estimée sous 31 Go, temps extrapolé sous 5 jours. Recrutement calé sur le modèle IFN. | SER pilote complète. Recrutement dans l'intervalle de confiance IFN sur 10 ans. Comparaison avec MARGOT. |
| M6 | glTF du générateur dans les deux vues. Godot sans interface : export et tests GUT. | Sur le PC de Pascal. |

## 12. Besoins en référentiels (pour l'`acquereur`)

- Documentation des données brutes IFN : variables, `c13`, cercles de placette.
- Table `essence ↔ espar ↔ TAXREF`.
- Tichý et al. 2023 et Niinemets et Valladares 2006 : valeurs par essence.
- MARGOT : trajectoires publiées par SER.
- Licences des données à citer dans les vues : LiDAR HD, IFN, BD Forêt.

## 13. Hors périmètre de la v1

- L'arbre par arbre à l'échelle d'une SER.
- Les scénarios climatiques.
- La sylviculture, interactive ou non (`management: none`).
- Le rendu photoréaliste.
- La plateforme multi-utilisateurs et `nemetonshiny`.
- La vue web à l'échelle de la France.
- L'hébergement public.
