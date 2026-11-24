# `contracts/` : les contrats de fichiers de sylvigenese

> Mission 009, version des contrats **0.1** (`schema_version` du catalogue et
> `x-schema-version` de chaque schéma). Sources : `docs/spec.md` §2 à §10, `docs/BRIEF.md`
> §4 à §6, ADR 0002, `docs/referentiels/entrees-externes.{md,csv}`, `bench/SPEC.md` (AM3).

Les modules ne se parlent que par fichiers. Chacun appelle ce validateur **en
sous-processus** à la fin de son travail, et `prepare` l'appelle aussi à l'entrée. C'est un
passage par fichiers : aucun module n'importe ce code.

## Les trois couches (ADR 0002)

| Couche | Pour | Où |
|---|---|---|
| Table Schema **v2.0** (Frictionless), figé | Parquet, CSV, attributs des GeoPackage | `tables/**/*.schema.json` |
| JSON Schema 2020-12 | YAML et JSON ; `tileset.json` par les schémas officiels de CesiumGS | `json/*.schema.json`, `json/vendor/3d-tiles-1.1/` |
| Profil GeoTIFF | rasters | `geotiff_profile.json` (et son schéma) |

`catalog.yml` relie chaque contrat à sa couche, à son schéma, à ses options et à son
chemin sous `data/<zone>/`.

**Pourquoi la v2.0 de Table Schema** (`$schema` :
`https://datapackage.org/profiles/2.0/tableschema.json`) : `fieldsMatch: subset` permet de
ne déclarer que les colonnes lues dans un fichier externe qui en a d'autres (IFN brut,
inventaire vidéo, dalles IGN), et `exclusiveMinimum` dit « strictement positif ».
frictionless-py 5.21.0 suit la v2 par défaut.

**GeoPackage** : extension `x-geopackage` du Table Schema (couche, types de géométrie,
EPSG), lue avec `sqlite3`, sans GDAL.

## Utilisation

```
contracts/validate <contrat> <chemin> [<chemin>...]
contracts/validate --contract <contrat> <chemin>...
contracts/validate --zone <dossier> [--require-outputs]   # tout le catalogue sous <dossier>
contracts/validate --list                  # liste des contrats et de leurs noms courts
options : --grid <grid.tif>  (alignement, variante grille)   --max-errors <N>  (50)
```

Un contrat se désigne par son nom complet (`prepare.trees_init`) ou par son nom court
(`trees_init`). Un nom court ambigu (`dtm`, `ser`, `station_type`…, qui existent en entrée
et en sortie de `prepare`) est refusé, avec les noms complets à choisir.

Un chemin Parquet peut être un fichier ou un dossier (`trees_init/`, `sim/trees/`) : tous
les `.parquet` qu'il contient sont contrôlés. Les colonnes chaîne peuvent être écrites en
`string`, `large_string`, `string_view` ou dictionnaire de chaînes.

**Partitions `year=AAAA`** (`sim/trees/`, `sim/cells/`) : convention Hive standard (ADR
0002), comme l'écrit `pyarrow.dataset.write_dataset(partitioning_flavor="hive")`. L'année
n'est que dans le nom du dossier ; le validateur reconstitue la colonne `year` avant le
contrôle. **Un fichier qui contient aussi une colonne `year` est refusé** (code 3) : l'année
aurait deux sources qui pourraient diverger.

**Mode `--zone`** : les entrées sont sous `<dossier>/inputs/`, les sorties directement sous
`<dossier>/` (BRIEF §4). Pour le jeu fictif : `contracts/validate --zone
tests/fixtures/zone_fictive`. Les entrées sont obligatoires ; les sorties sont contrôlées
si elles existent, et deviennent obligatoires avec `--require-outputs` (les entrées
facultatives, comme `inventaire_video.gpkg`, le restent). `grid.tif`, s'il est présent,
sert à vérifier l'alignement. Un fichier en écart ou impossible à contrôler n'arrête pas
le contrôle des suivants.

### Codes de sortie

| Code | Sens |
|---|---|
| 0 | tout est conforme |
| 2 | le contrôle n'a pas pu se faire : arguments invalides, contrat inconnu ou ambigu, fichier absent (en mode `--zone` : fichier obligatoire absent, comme `h_pot.tif`, spec §3) ; raster de variante `grille` sans `--grid` (ou, en mode `--zone`, sans `grid.tif` dans la zone) |
| 3 | au moins un fichier est non conforme, y compris un fichier illisible ou d'un autre format |

En mode `--zone`, un fichier non conforme (3) l'emporte sur une entrée absente (2).
L'appelant traduit le code pour lui-même : à l'entrée, `prepare` transforme un 3 en son
propre code 2 (« entrée refusée »).

Messages en français, une ligne par écart sur la sortie d'erreur :
`contracts/validate : <fichier> : contrat <nom> : <écart>`. Un fichier conforme donne
`conforme : <fichier> (contrat <nom>)` sur la sortie standard.

### Installation

- `requirements.txt` et `requirements-tests.txt` : dépendances **directes**, versions
  figées ; on les modifie à la main.
- `requirements.lock` et `requirements-tests.lock` : **verrous** produits par
  `uv pip compile --generate-hashes --universal`, toutes dépendances transitives comprises,
  avec empreintes SHA-256. **La CI installe `pip install --require-hashes -r
  contracts/requirements-tests.lock`** ; un module qui n'a besoin que du validateur installe
  `contracts/requirements.lock`.

Tests : `python3 -m pytest tests/contracts contracts/tests`.

## Règles communes à tous les contrats

- **Essence** : `species` (ou `species_espar` dans l'entrée nemeton, comme la spec §3) est
  le code espar **en chaîne**, avec son zéro de tête, au motif `[0-9]{2}[A-Z0-9]{0,3}`
  (les 195 codes de `species.csv`). `9` ou l'entier `9` au lieu de `"09"` sont refusés.
- **Coordonnées** : EPSG:2154, x vers l'est, y vers le nord, en mètres. Toute coordonnée
  (colonnes déclarées par `x-extent`, géométries des GeoPackage, emprise des rasters,
  objets marqués `x-lambert93` des JSON) doit tomber dans l'emprise du Lambert-93 de
  `lambert93_extent.json` : x de 100 000 à 1 300 000, y de 6 000 000 à 7 200 000
  (**provisoire**, fixée par l'orchestrateur). Des x et y inversés sont signalés comme tels.
- **Nombres** : NaN et infinis sont toujours refusés.
- **Tables vides** : refusées, sauf `x-allow-empty: true`.
- **YAML et JSON** : refusés, avec le code 3, une clé en double (on ne garde pas la
  dernière), une clé YAML qui n'est pas une chaîne (`02` non quoté est lu en YAML 1.1 comme
  l'entier 2 : il faut écrire `"02"`), et toute valeur NaN ou infinie (`NaN`, `.nan`,
  `.inf`).
- **YAML 1.1 contre YAML 1.2** : PyYAML et R lisent le YAML 1.1, TypeScript le YAML 1.2.
  Le contrat refuse (code 3), quand ils ne sont pas entre guillemets, exactement ces
  scalaires, clés comprises, avec un message qui dit quoi écrire :
  - entier à zéro de tête : `010`, `-010`, `0o10` ;
  - nombre sexagésimal : `1:30`, `190:20:30` ;
  - nombre avec séparateur `_` : `1_000`, `1_000.5` ;
  - nombre préfixé `0b` (binaire) ou `0x` (hexadécimal) : `0b101`, `0x1F` ;
  - booléen YAML 1.1 autre que `true` et `false` : `yes`, `no`, `on`, `off`, `y`, `n`,
    en toute casse.

  D'autres écarts entre versions existent et **ne sont pas** dans cette règle : par
  exemple `0.5e3`, chaîne en YAML 1.1 et nombre en YAML 1.2, n'est refusé que si le
  schéma attend un nombre. Un alias YAML récursif (`&a [*a]`) est refusé, code 3.
  **Attention pour les modules qui écrivent du YAML** : `yaml.safe_dump` écrit la chaîne
  `"09"` sans guillemets ; il faut quoter ces chaînes (voir `QuotingDumper` dans
  `tests/helpers.py`).
- **Valeur nulle** : elle n'est refusée que par `required` ; les autres contraintes
  (`enum`, `pattern`, bornes) ne s'appliquent qu'aux valeurs présentes.
- **Colonne facultative** (`x-optional: true`) : elle peut manquer ; si elle est là, ses
  contraintes s'appliquent.
- **Contrat hors du sous-ensemble pris en charge** (type, contrainte ou propriété inconnue
  du validateur) : refusé avec le code 2, plutôt que contrôlé à moitié.
- Aucune valeur écologique dans les schémas : seulement des bornes de définition (une part
  entre 0 et 1, un diamètre positif) et des listes de codes.

## Profil GeoTIFF (spec §9)

Tuiles de 256 × 256, PLANARCONFIG=2, Deflate ou aucune compression, PREDICTOR 1 ou 2,
Float32 ou UInt16, nodata dans la balise 42113, GeoKey 3072 = 2154, BigTIFF refusé.
Les variantes `complet` et `grille` refusent aussi, comme le lecteur Rust de `simulate`
(`simulate/src/geotiff.rs`, mission 015) : le pixel « point » (GeoKey 1025 =
RasterPixelIsPoint), le géoréférencement par matrice (balise 34264) et les bandes de types
mixtes, un nombre de valeurs des balises 258 (BitsPerSample) et 339 (SampleFormat)
différent du nombre de bandes, et les tuiles creuses (début et taille nuls). Un test
compare les deux verdicts sur les fichiers de `simulate/tests/fixtures/`.
Quatre variantes :

| Variante | Pour | En plus ou en moins |
|---|---|---|
| `complet` | contrat `geotiff_profile` | le profil seul |
| `grille` | sorties de `prepare` et `biomes`, lues par `simulate` | maille de 25 m, alignement exact sur `grid.tif` (`--grid` obligatoire, sinon code 2) |
| `entree` | `inputs/*.tif` | en-tête, EPSG:2154, nodata, compression Deflate, **LZW** ou aucune (terra et GDAL écrivent en LZW par défaut) ; ni tuilage, ni entrelacement, ni type imposés |
| `cog` | `web/rasters/*.tif` | au moins un aperçu ; entrelacement libre |

L'en-tête est lu en Python pur (`struct`), comme le fera le lecteur Rust de `simulate`.
**Attention pour les modules qui écrivent des rasters** : GDAL (terra, rasterio) écrit
PLANARCONFIG=1 par défaut ; il faut lui donner `INTERLEAVE=BAND`, `TILED=YES`,
`BLOCKXSIZE=256`, `BLOCKYSIZE=256` et `COMPRESS=DEFLATE` (testé dans
`tests/test_real_files.py`).

## Noms fixés par la mission 009

Ni la spec ni le BRIEF ne les donnaient. Ils sont fixés par la mission 009 (décision de
contrat de l'orchestrateur, par délégation de Pascal), en `schema_version` 0.1.

| Contrat (fichier) | Colonnes ou clés |
|---|---|
| `inputs.lidar_tiles` | `flight_date` (date) ; couche `lidar_tiles` |
| `inputs.ser` | `ser_code` (SER sous-jacente, jamais `L1` à `L5`), `alluvium_code` (chaîne ∈ {`L1`, …, `L5`}, NULL hors alluvions ; une chaîne vide est refusée) ; couche `ser` |
| `inputs.forest_mask` | couche `forest_mask`, géométrie seule |
| `inputs.ifn_placette`, `ifn_arbre`, `ifn_flore` | fichiers `inputs/ifn/PLACETTE.csv`, `ARBRE.csv`, `FLORE.csv` (colonnes de l'IFN : `IDP`, `XL`, `YL` ; `ESPAR`, `C13`, `HTOT`, `V`, `W` (facultative) ; `CD_REF`, `ABOND`). **Les colonnes réelles de l'export IFN seront vérifiées au jalon M1b** (le dictionnaire `metadonnees.csv` n'a pas pu être lu, `docs/referentiels/ifn-placettes.md`) |
| tables de catégories (`ser.csv`, `station_type.csv`, `site_potential.csv`, `vegetation_map.csv`) | `value`, `name` (pour `site_potential.csv`, `value` est le numéro de bande) |
| `prepare.trees_init` | listes fermées : `species_source` ∈ {`nemeton`, `vegetation_type`, `inventaire_video`}, `d130_source` ∈ {`tarif_etage_b`, `inventaire_video`, `nemeton`} |
| `prepare.ifn_plots` (`ifn/plots.parquet`) | `plot_id`, `campaign`, `x`, `y`, `loc_precision_m`, `source`, `ser_code`, `trophic`, `coarse_hydric_700m`, `coarse_bioclim_700m` |
| `prepare.ifn_trees` (`ifn/trees.parquet`) | `plot_id`, `campaign`, `tree_id`, `species`, `d130`, `h`, `weight_ha` |
| `prepare.ifn_flora` (`ifn/flora.parquet`) | `plot_id`, `campaign`, `cd_ref`, `taxref_version`, `abundance` |
| `prepare.stands` | `stand_id`, `species`, `d130`, `h`, `density_ha`, `age`, `source`, `stand_id_source` |
| `params/*.parquet` (tarif, allometry, growth, mortality, recruitment, height_curve) | format long : `species`, `species_group` (au moins l'un des deux), `model`, `term`, `value`, `provisoire`, `source` |
| `simulate.trees` | `status` ∈ {`alive`, `dead`} (les autres colonnes viennent du BRIEF §4 ; `year` est dans le nom du dossier) |
| `simulate.cells` | `cell_id`, `year`, `species`, `stems_ha`, `basal_area_m2_ha`, `d130_mean`, `seedlings_ha`, `seedling_h_mean` ; `cell_id` = ligne × largeur + colonne dans `grid.tif`, depuis le coin nord-ouest, à partir de 0 |
| `post.summary` | `cell_id`, `year`, `species`, `volume_m3_ha`, `biomass_t_ha`, `carbon_t_ha`, `provisoire` |
| `simulate.run` (`sim/run.json`) | `schema_version`, `level`, `seed`, `t0`, `years`, `threads`, `zeroed_values`, `provisional_share` ; facultatifs : `memory_estimate_bytes`, `duration_s`, `config_sha256` |
| `config` (`config.yml`) | `schema_version`, `zone`, `crs`, `grid.resolution_m`, `management` ; facultatifs : `external.tarif_nemeton_dir`, `external.raf20_grid`, `simulate.{level, seed, t0, years, threads}` ; toute autre clé est refusée |
| `assets.cell_sheet` (`web/cells/<tuile>.json`) | `schema_version`, `tile`, `cells[].{cell_id, x, y, station_type, vegetation_type, years[].{year, provisoire, composition[].{species, share}, volume_m3_ha, carbon_t_ha}}` |
| `assets.massif_block` (`massif/<bloc>.json`) | `schema_version`, `block_id`, `year`, `crs`, `vertical_datum` (`NGF-IGN69`), `origin.{x, y, z}`, `trees[].{tree_id, species, stage, x, y, z, h, d130, hcb, cw}` (positions relatives à l'origine) |
| `assets.tree_model` | nom `<species>_<stage>.glb` (BRIEF §4) |
| énumération `stage` (`json/enums/stage.json`, **provisoire**) | `young`, `pole`, `mature`, `old` |

Noms repris tels quels d'une source : `nemeton_stands` (spec §3), `inventaire_video`
(schéma nemeton 1.7.0), `fertilite.csv` (sylvostation), `trees_init` et `sim/trees`
(BRIEF §4), clés du biome (BRIEF §5, en français pour rester lisibles par un forestier),
`species.csv` (mission 011).

## Hors de M0

- contrôle des pixels (plages de valeurs, couverture du nodata) : seuls les en-têtes sont lus ;
- validation complète du contenu glTF (Khronos glTF-Validator), prévue en M4 ;
- contrôles croisés entre fichiers (un `station` de biome présent dans `station_type.csv`,
  une somme de composition égale à 1, un `cell_id` dans la grille) ;
- vérification d'un `schema_version` dans les fichiers Parquet ;
- lecture d'un Parquet par groupes de lignes : un fichier est lu en entier (3 millions
  d'arbres : 1,6 s et 0,9 Go de mémoire).
