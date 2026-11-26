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
| `inputs.ser` | `ser_code` tel que publié par l'IGN, `L1` à `L5` compris pour les alluvions (motif `[A-K][0-9]{2}\|L[1-5]`) ; couche `ser`. La SER sous-jacente des alluvions est calculée par `prepare` (spec §7) : `prepare.ser` n'a jamais `L1` à `L5` |
| `inputs.forest_mask` | couche `forest_mask`, géométrie seule |
| `inputs.station_types` | légende `inputs/types.csv` de sylvostation, séparée par `;` : `id` (valeur de `station_type.tif`), `type` (nom), `area_ha`, `part_surface`, `trophic`, `hydric`, `bioclim`, `n_placettes` |
| `inputs.ifn_placette`, `ifn_arbre`, `ifn_flore` | fichiers `inputs/ifn/PLACETTE.csv`, `ARBRE.csv`, `FLORE.csv` (colonnes de l'IFN : PLACETTE `IDP`, `CAMPAGNE`, `XL`, `YL`, `VISITE`, et facultatives `DATEPOINT`, `NINCID`, `INCID`, `PRELEV5`, `DEF5`, `INSTP5` ; ARBRE `IDP`, `CAMPAGNE`, `A`, `ESPAR`, `C13` **en mètres**, `VEGET`, `VEGET5` (facultative), `IR5` (m), `HTOT`, `V`, `W` (facultative) ; FLORE `CD_REF`, `ABOND` ; une ligne par visite, voir `docs/referentiels/ifn-dynamique-colonnes.csv`). **Les colonnes réelles de l'export IFN seront vérifiées au jalon M1b** (le dictionnaire `metadonnees.csv` n'a pas pu être lu, `docs/referentiels/ifn-placettes.md`) |
| tables de catégories (`station_type.csv`, `site_potential.csv`, `stand_map.csv`, `vegetation_map.csv`) | `value`, `name` (pour `site_potential.csv`, `value` est le numéro de bande ; pour `stand_map.csv`, `name` est le `stand_id`) |
| `ser.csv` | `value`, `name` (la SER sous-jacente, jamais L1 à L5, non unique), `alluvium_code` (L1 à L5, vide hors alluvions) : une valeur de `ser.tif` par couple distinct |
| `prepare.trees_init` | listes fermées : `species_source` ∈ {`nemeton`, `vegetation_type`, `inventaire_video`}, `d130_source` ∈ {`tarif_etage_b` (avec houppier : ln D = a + b ln H + c ln CPA), `tarif_etage_b_ifn` (sans coefficient c : ln D = a + b ln H), `inventaire_video`, `nemeton`} ; colonne `crown_area` (m², > 0, obligatoire, PROVISOIRE) |
| `prepare.ifn_plots` (`ifn/plots.parquet`) | `plot_id`, `campaign`, `x`, `y`, `loc_precision_m`, `source`, `ser_code`, `trophic`, `coarse_hydric_700m`, `coarse_bioclim_700m`, `visit`, `date_point`, `incident_nature`, `incident_intensity`, `harvest_5y`, `clearing_5y`, `planting_5y` (une ligne par visite) |
| `prepare.ifn_trees` (`ifn/trees.parquet`) | `plot_id`, `campaign`, `tree_id`, `species`, `d130` (cm, = C13 × 100 / π ; vide si C13 manque), `h`, `weight_ha`, `veg_state`, `veg_state_5y`, `radial_incr_5y_m` (m), `stem_volume_m3` (m³, facultative ; colonne `V` de ARBRE.csv : volume bois fort tige de l'IFN, repris sans conversion ; deux libellés, voir le schéma) |
| `prepare.ifn_flora` (`ifn/flora.parquet`) | `plot_id`, `campaign`, `cd_ref`, `taxref_version`, `abundance` |
| `prepare.stands` | `stand_id`, `species`, `d130`, `h`, `density_ha`, `age`, `source`, `stand_id_source` |
| `params/*.parquet` (allometry, growth, mortality, recruitment, height_curve ; **tarif a son propre contrat**, ligne suivante) | format long : `species`, `species_group` (au moins l'un des deux), `model`, `term`, `value`, `provisoire`, `source` ; `dynamics_params` ajoute `variable` et `x` |
| `dynamics.regeneration` (`params/regeneration.parquet`, **mission 060**, ADR 0006 projet) | format long : `species`, `species_group` (au moins l'un des deux), `term`, `value`, `unit`, `provisoire`, `source` ; **aucune valeur dans le schéma** ; termes (liste fermée) : `kernel_scale_m`, `kernel_shape` (noyau exponentielle-puissance, normalisé ; depuis les distances à 50 % et 99 % de la classe de Lososová et al. 2023, mission 062), `maturity_height_m` (maturité en hauteur, comme TreeMig ; remplace `maturity_d130_cm`, version 0.2), `fecundity_seeds_per_m2_ba_yr`, `establishment_share`, `seedling_height_growth_m_yr`, `shade_tolerance`, `light_extinction_coef`, `seedling_survival_full_light_yr` (lumière et ombre seules, Q3), `passage_height_m`, `stress_mortality` (mortalité annuelle de stress à l'ombre, TreeMig éq. 40 ; version 0.3, mission 066 : plus de constante dans le code) ; valeurs du jeu fictif synthétiques et `provisoire` vrai ; sur une zone réelle, une essence sans valeur pour un terme lu arrête `simulate` (code 2), aucun emprunt |
| `prepare.cohorts_init` (`cohorts_init.parquet`, mission 060) | `cell_id`, `species`, `d_class` (rang 0 à K − 1), `stems_ha`, `source` ; cellules forestières seules ; clé (`cell_id`, `species`, `d_class`) ; les semis initiaux n'y sont pas (déduits à t0 par le moteur, Q2) |
| `simulate.cohorts` (`sim/cohorts/year=AAAA/`, mission 060) | `cell_id`, `year` (partition), `species`, `d_class`, `stems_ha` ; niveau SER ; aux années écrites seulement (`write_step`) ; clé (`cell_id`, `year`, `species`, `d_class`) |
| `import_tarif.tarif` (`params/tarif.parquet`, **mission 051**, projet d'ADR 0005) | le modèle NEMETON v5 et son domaine, **sans aucune valeur** : `essence` (code espar) ou `groupe` (`feuillu`, `resineux`), `modele`, `terme`, `valeur`, `unite`, `source_code`, `source_biblio` (colonnes du `resultats/tarif_v5/parametres_tarif_v5.csv` de tarif-nemeton, mission 050), plus `source_commit` et `provisoire` ajoutées par `import_tarif` ; `modele` ∈ {`volume_feuillus` (ln V = ln(π/4·D²·H) + a + b ln(D/30) + c ln(H/25)), `profil_tige_resineux`, `expansion_resineux`, `infradensite`, `fraction_carbone`, `racines` (provisoire, GIEC 2006 tableau 4.4), `domaine` (`dbh_min`, `dbh_max`, `h_min`, `h_max`, `hd_min`, `hd_max`)} ; hors domaine ou essence sans tarif : l'arbre n'est pas calculé, ni extrapolé ni emprunté (décision Q5) ; clé (`essence`, `groupe`, `modele`, `terme`) ; **termes nommés par la mission 053** (forme NEMETON v5 : `a`, `b`, `c`, `sigma_log`, `facteur_biais_sigma2` ; profil `k0`, `k1`, `beta`, `lam`, `a`, `x0`, `sx`, `h_ref`, `D_ref`, `n_points`, `marge_sommet`, `u_min` ; E(D) `a`, `b`, `D_plafond`, `D_ref` ; infradensité `rho_moyenne`, `rho_pente_10cm`, `D_ref`, `pas_D`, `facteur_arbre_entier` ou `infradensite` constante ; `fraction` ; `ratio` ; forme synthétique du jeu fictif `synth_p1`, `synth_p2`, `synth_E`), formules et correspondance avec `parametres_tarif_v5.csv` dans la description du schéma |
| `dynamics.height_curve` : modèle `korf` (mission 033) | deuxième forme de courbe de hauteur dominante, pour le hêtre (09), décision de Pascal du 25/11/2026 : termes `a`, `b`, `c`, `p_f_class1` à `p_f_class5`, et le point de départ `t_ref0` (ans), `h_ref0` (m), `age_ref` (ans) qui sert à choisir la classe (mission 040, provisoires et sourcés) ; formule de récurrence annuelle dans la description du contrat (Bontemps et al. 2007, reprise de nemeton, provisoire) |
| `import_tarif.allometry` : modèles `hcb` et `cw` (mission 033) | `hcb` : `CR_a`, `CR_b`, `CR_min`, `CR_max` (hcb = h (1 − CR), CR = CR_a + CR_b ln d130, borné) ; `cw` : `R_a`, `R_b` (cw = 2 E, ln E = R_a + R_b ln d130) ; formes dans la description du contrat, aucune valeur dans le contrat |
| `simulate.trees` | `status` ∈ {`alive`, `dead`} (les autres colonnes viennent du BRIEF §4 ; `year` est dans le nom du dossier) |
| `simulate.cells` | `cell_id`, `year`, `species`, `stems_ha`, `basal_area_m2_ha`, `d130_mean` ; facultatives jusqu'à M5 (« semis non simulés », décision de Pascal du 25/11/2026) : `seedlings_ha`, `seedling_h_mean` ; **facultative** (mission 044, décision de Pascal Q1 du 25/11/2026) : `h_dom_m`, hauteur dominante de la cellule pour l'année, m, même valeur sur toutes les lignes d'une cellule et d'une année, jamais corrigée au plafond ; `simulate` l'écrira à la mission 046, et la fiche v2 comme `assets` l'exigent ; `cell_id` = ligne × largeur + colonne dans `grid.tif`, depuis le coin nord-ouest, à partir de 0 |
| `simulate.flags` (`sim/flags.parquet`, mission 033) | `year`, `entity` (tree_id, ou cell_id en décimal), `kind` (minuscules et underscores), `message` (français), `value` (vide permis) ; une table sans ligne est conforme ; `post` la met en page |
| `post.summary` (`sim/summary.parquet`), **version 0.2** (mission 051, décisions Q3 à Q5 du 26/11/2026) | `cell_id`, `year`, `species`, `volume_m3_ha` (**volume aérien total**, tige et branches, m³/ha, seul volume : ni bois fort ni au-dessus de 7 cm), `biomass_t_ha` (biomasse aérienne sèche), `carbon_t_ha` (**carbone aérien**, tC/ha), `stems_not_computed_ha` (tiges vivantes non calculées, tiges/ha), `basal_area_not_computed_share` (part de G de l'essence non calculée, 0 à 1), `provisoire` ; **facultative et provisoire** : `carbon_roots_t_ha` (carbone des racines, à part, jamais additionné à `carbon_t_ha`) ; une ligne par (cellule, essence) vivante, comme `sim/cells` ; sommes sur les arbres vivants calculés ; part = 1 : la somme est vide, les valeurs valent 0 et ne se lisent jamais sans la part |
| `post.summary_zone` (`sim/summary_zone.parquet`, mission 051) | clé (`year`, `vegetation_type`, `species`) ; `forest_area_ha`, totaux `volume_m3`, `biomass_t`, `carbon_t` (et `carbon_roots_t` facultatif), moyennes par hectare `volume_m3_ha`, `biomass_t_ha`, `carbon_t_ha` (et `carbon_roots_t_ha`) sur la surface forestière du type, **flux de mortalité de l'année** `dead_volume_m3`, `dead_carbon_t`, `dead_stems_not_computed` (pas un stock de bois mort), `stems_not_computed`, `basal_area_not_computed_share`, `provisoire` ; une cellule sans type de végétation n'entre dans aucune ligne (aucun type inventé, mission 053) : elle reste dans `summary` et est comptée dans `post.json` |
| `post.run` (`sim/post.json`, mission 051) | provenance et comptes, tout obligatoire : `schema_version` = 1, `run_config_sha256` (copié de `config_sha256` de `sim/run.json`), `inputs_sha256.{sim_run, sim_trees, params_tarif}`, `tarif_commit`, `models[].{model, source, commit, provisoire}`, `tree_years_computed`, `tree_years_not_computed`, `out_of_domain` (par essence : `dbh_below`, `dbh_above`, `h_below`, `h_above`, `hd_below`, `hd_above`, première raison), `without_tarif` (par essence, ≥ 1), `without_vegetation_type.{cells, tree_years}` (mission 053 : cellules qui portent des arbres sans type de végétation, hors de `summary_zone`), `provisional_share`, `duration_s` ; un compte nul s'écrit 0 |
| `simulate.run` (`sim/run.json`) | tout est obligatoire (mission 033) : `schema_version`, `level`, `seed`, `t0`, `years`, `threads`, `memory_estimate_bytes`, `duration_s`, `config_sha256`, `zeroed_values`, `provisional_share`, et les comptes `domain_outputs` (par variable : `below`, `above`), `cells_at_height_ceiling`, `edge_disks`, `mixed_cells`, `recruits`, `deaths` ; un compte nul s'écrit 0 ; **mission 060 (M5a)** : `recruitment` (mode) marque un `run.json` de M5a et rend exigés `not_simulated` (`semis`, `sous_bois`, `gibier`, `fructification` : en `cohorts`, les trois derniers et jamais `semis` ; en `ifn_direct`, au moins `semis`), `memory_estimate_max_bytes`, `memory_peak_rss_bytes` (entier ou `null` hors de Linux) ; en `cohorts` s'y ajoutent `seedling_stock_limited`, `gaps_recolonised`, `buffer_cells` (refusés en `ifn_direct` et sans `recruitment`) ; un `run.json` de M3a, sans `recruitment`, reste conforme |
| `config` (`config.yml`) | **mission 068 (M6a)** : blocs `assets.models.{provisoire, exemplars_dir (facultatif), triangle_budgets.{lod0, lod1, lod2}, screencoverage[3]}` et `viewer.{provisoire, mention (« illustration, non mesurée »), grass.{…}, seedlings.max_instances (plafond de dessin des semis), foliage.{card_size_m, color_by_group, color_by_essence (facultatif)}, lod.fade_margin_m}` : réglages d'AFFICHAGE provisoires, jamais lus par le moteur, **sans aucune dimension dendrométrique** (Q6) ; `schema_version`, `zone`, `crs`, `grid.resolution_m`, `management` ; facultatifs : `external.tarif_nemeton_dir`, `external.raf20_grid`, `simulate.{level, seed, t0, years, threads}` ; **mission 044** : bloc `assets.year_step` (entier ≥ 1, une année retenue sur N ; le dépôt écrit 10), exigé par `assets` dès que `sim/` existe (le schéma ne peut pas savoir si `sim/` existe : sans le bloc, `assets` s'arrête, code 2, aucune valeur par défaut) ; toute autre clé est refusée ; **mission 060 (M5a)** : `simulate.recruitment` ∈ {`ifn_direct`, `cohorts`} (non imposé par le schéma, pour que les configs de M3a restent conformes ; `simulate` s'arrête, code 2, sans lui), bloc `simulate.regeneration.{kernel_truncation_cells, zero_threshold}` exigé quand `recruitment` vaut `cohorts`, bloc `simulate.ser.{diameter_class_width_cm, diameter_classes, write_step}` exigé quand `level` vaut `ser` |
| `assets.cell_sheet` (`web/cells/<tuile>.json`), **version 1** (état initial, sans `sim/`) | `schema_version` = 1, `tile`, `cells[].{cell_id, x, y, station_type, vegetation_type, years[].{year, provisoire, composition[].{species, share}, volume_m3_ha, carbon_t_ha}}` ; facultatifs par année : `h0_m`, `density_trees_ha`, `notes[]` ; `volume_m3_ha` et `carbon_t_ha` valent `null` quand ils ne sont pas calculés (état initial : `post` vient après la simulation), et `notes` le dit. **Inchangée par la mission 044** : refuse seulement, en plus, les clés de la version 2 (`source`, `notes` du document) |
| `assets.cell_sheet`, **version 2** (mission 044, quand `sim/` existe ; la vue refuse la version 1 dès qu'un `sim/` existe) | document : `schema_version` = 2, `tile`, `source` = `sim` (toutes les années, t0 compris, viennent de `sim/`), `notes[]` (écrites une fois pour toute la fiche, et non plus par cellule et par année ; l'une contient « non validée écologiquement », l'autre « volume et carbone non calculés ») ; cellule : `cell_id`, `x`, `y`, `station_type`, `vegetation_type` (état initial : il n'évolue pas), `h_ceiling_m` (plafond de la station, `null` = inconnu, dit par la fiche), `years[]` ; année : `year`, `provisoire`, `stems_ha`, `basal_area_m2_ha`, `d130_mean_cm` (moyenne pondérée par les tiges, `null` sans tige), `h_dom_m` (de `sim/cells`, jamais corrigée), `composition[].{species, stems_ha, basal_area_m2_ha, share}` (**`share` = part des TIGES**), `flags[].{kind, message, value}` (recopiés de `sim/flags.parquet` : `hdom_au_dessus_du_plafond`, `trouee_sans_recrue`… ; `[]` = rien à signaler), `volume_m3_ha` et `carbon_t_ha` toujours `null` (décision de Pascal Q2 : `post` est une mission à part après M4a ; la version 3, mission 051, les remplit) ; facultatif : `h0_m` (réservé à t0). Plus de `density_trees_ha` ni de `notes` par année |
| `assets.cell_sheet`, **version 3** (mission 051, quand `sim/summary.parquet` existe ; la version 2 reste pour un `sim/` sans `post`) | document : `schema_version` = 3, `tile`, `source` = `sim`, `tarif.{name, commit, provisoire = vrai}` (tarif NEMETON v5 figé à un commit, décision Q1), `notes[]` (contient « non validée écologiquement », la définition « volume aérien total », « carbone aérien », « sol et bois mort » (non modélisés, hors v1), « volume partiel » dès qu'une année a une part non calculée, « racines » dès qu'une année porte le carbone des racines ; ne contient plus « volume et carbone non calculés ») ; cellule : comme la v2 ; année : tout ce que porte la v2, sauf que `volume_m3_ha` (**aérien total**) et `carbon_t_ha` (**aérien**) sont des nombres, plus `stems_not_computed_ha`, `basal_area_not_computed_share` (0 à 1), `volume_partiel` (vrai si et seulement si la part est > 0), `root_carbon_t_ha` (**facultatif**, provisoire : année `provisoire` vraie), `not_computed_reason` ; **part = 1 : rien n'est calculé, `volume_m3_ha`, `carbon_t_ha` et `root_carbon_t_ha` valent `null` et `not_computed_reason` est obligatoire** (jamais 0) ; `composition[]` ajoute `volume_m3_ha`, `carbon_t_ha` et `basal_area_not_computed_share` ; aucune autre grandeur (ni bois fort, ni CO2, ni sol) n'est admise |
| `assets.tiles_index` (`tiles/index.json`, mission 044) | `schema_version` = 1, `source` (`sim` ou `trees_init`), `t0`, `provisoire`, `notes[]`, `years[].{year, instances (vivants dessinés), tileset (`<année>/tileset.json`), tiles[].{tile (`t_<x>_<y>`), instances}}`. Mode `sim` : en plus `year_step`, `run_config_sha256` (copié de `sim/run.json`), `basal_area_map.{unit = m2/ha, scale_min_m2_ha, scale_max_m2_ha, mention}` (échelle fixe de toutes les années) et `years[].dead` (morts non dessinés) ; `notes` contient « non validée écologiquement » ; mode `trees_init` : une seule année et aucune de ces clés |
| `assets.basal_area_raster` (`web/rasters/g_<année>.tif`, mission 044, décision de Pascal Q3) | surface terrière par cellule, m2/ha ; COG avec aperçus, Float32, une bande, maille de 25 m, EPSG:2154 ; un fichier par année de `tiles/index.json`, lu avec l'échelle fixe de `basal_area_map` |
| `assets.massif_block` (`massif/<année>/<bloc>.json`), **version 1** (inchangée) | `schema_version`, `block_id`, `year`, `crs`, `vertical_datum` (`NGF-IGN69`), `origin.{x, y, z}`, `trees[].{tree_id, species, stage, x, y, z, h, d130, hcb, cw}` (positions relatives à l'origine) |
| `assets.massif_block`, **version 2** (mission 068, M6a ; ADR 0007 projet) | tout ce que porte la v1, plus `ground.{resolution_m = 25, nx, ny, z[]}` (altitude NGF-IGN69 aux nœuds de 25 m, ligne 0 au nord ; le validateur contrôle `len(z) = nx × ny`), `cells[].{cell_id, x, y (relatifs à l'origine), biome (ou `null`), biome_provisoire, herb_cover, shrub_cover (0 à 1 ou `null` : jamais de valeur par défaut), seedlings[].{species, seedlings_ha, h_mean_m}}`, `seedlings_simulated`, `mentions[]` (l'une dit « non validée écologiquement »), `provisoire` ; **`seedlings` est présent dans chaque cellule si et seulement si `seedlings_simulated` est vrai** (`sim/run.json` : `recruitment = cohorts`) ; pas de composition herbacée (Q4). Le `stage` d'un arbre est h / h_pot de l'arbre avec les seuils de `biomes/stades/stage_breaks.yml` (extension de BRIEF §6, Q8). Le chemin du catalogue passe de `massif/*.json` à `massif/*/*.json` ; une v1 reste contrôlable par son nom de contrat |
| `assets.massif_index` (`massif/index.json`, mission 068) | `schema_version` = 1, `zone`, `fictive`, `crs`, `vertical_datum`, `source` (`sim` ou `trees_init`), `block_size_m`, `recruitment` (mode `sim` seulement), `provisoire`, `notes[]`, `models[].{species, model, kind (`own`, `alias` avec `alias_of`, `generic`)}`, `years[].{year, trees, trees_by_kind.{own, alias, generic}, blocks[].{block_id (`t_<x>_<y>`), file (`<année>/<bloc>.json`), sw.{x, y}, size_m, trees}}` |
| `assets.exemplars` (`assets/exemplars/<essence>_<stade>.parquet`, mission 068, décision Q1) | un arbre synthétique du générateur de tarif-nemeton ; une ligne par segment : `x0 y0 z0 x1 y1 z1` (m), `r0_m`, `r1_m`, `niveau` (≥ −1), `axe`, facultative `racine_niveau1` ; **repère z-up du générateur dit dans les métadonnées Parquet** : `frame` = `z-up`, `units` = `m`, `essence`, `stage`, `D_cm`, `H_m`, `hbh_m`, `Rh_m`, `b_cible` (obligatoire et fini, sauf si `calage` = `non calé` : clé alors absente, jamais NaN ni inventée ; `calage` ∈ {`calé`, `non calé`} est obligatoire, `calage_raisons` facultatif), `seed`, `source_commit`, `synthetic` = `true` ; nom = `<essence>_<stade>.parquet` d'après les métadonnées ; **aucune valeur dans le contrat** (Q6) |
| `params.model_dimensions` (`params/model_dimensions.csv`, mission 068, repli de Q6) | `essence` (`tarif_nemeton_code`), `stage`, `term` (`D_cm`, `H_m`, `hbh_m`, `Rh_m`, `b_cible`), `value`, `unit`, `provisoire`, `source` (jamais vide) ; clé (`essence`, `stage`, `term`) ; **le contrat ne contient aucune valeur et aucun fichier de valeurs n'est écrit** : il reste à sourcer |
| `biomes.stage_breaks` (`biomes/stades/stage_breaks.yml`, mission 068, décision Q8) | `schema_version`, `provisoire`, `source`, `ratio` = `h / h_pot`, `stages` (les quatre), `breaks` (trois seuils strictement croissants, borne basse incluse) ; lu par `biomes` (R) et `assets` (Python) ; sous-dossier `stades/` parce que R lit tout `biomes/*.yml` comme un catalogue |
| `zone_marker` (`<zone>/zone.yml`, facultatif) | `schema_version`, `fictive` (booléen), `reason` ; `fictive: true` dispense `assets` de la grille RAF20 (ondulation 0, dite) ; les copies de zone héritent du marqueur |
| `assets.gltf` (`assets/trees/*.gltf`, `tiles/*/*.gltf`) | glTF 2.0 en JSON avec `.bin` externe (pas de `.glb` pour le contenu de tuile, référentiel iTowns point A) : `asset.version` = `2.0`, `scenes`, `nodes`, `meshes`, `buffers[].uri` en `.bin`, `extras.{generique, provisoire}` vrais ; contrôle de forme seulement (glTF-Validator : M4) |
| `assets.tree_model` (`assets/trees/*.glb`, **mission 068**) | `.glb` lu en entier, refusé s'il est tronqué ; nom `<espar>_<stade>.glb` (BRIEF §4) avec un code espar de `species.csv` **qui a un modèle propre** (`tarif_nemeton_code` non vide) et qui est le **premier** de son essence (les autres codes sont des alias : pas de doublon, pas de fichier propre), ou `generique_feuillu` / `generique_resineux` (repli signalé, Q3) ; **trois niveaux de détail par `MSFT_lod`** (T2) : un nœud principal LOD0, `ids` = LOD1 et LOD2, triangles strictement décroissants, `extras.MSFT_screencoverage` de trois nombres décroissants, extension dans `extensionsUsed` ; accesseurs bornés, `POSITION` avec `min` et `max`, sommets finis, indices valides ; **repère y-up** : LOD0 de y = 0 à y = `H_ref_m` à 1 % ; `extras` (`json/tree_model_extras.schema.json`) : `species`, `stage`, **`source_commit`**, `essence_generateur`, `D_cm`, `H_m`, `hbh_m`, `Rh_m`, `b_cible` (facultatif si `calage` = « non calé »), `graine`, `calage` (« calé » \| « non calé », obligatoire pour un modèle du générateur, interdit pour le générique ; « non calé » = résineux du générateur) et `calage_raisons` (chaîne ou liste, facultatif), `H_ref_m`, `rayon_houppier_ref_m`, `provisoire` = vrai, `synthetique` = vrai, `feuillage.{type = cartes_couleur_unie, couleur}` ; un générateur : `generique` = vrai, `groupe`, `provisoire`, `synthetique` ; `extras` redit l'essence, le stade et l'essence du générateur du nom |
| énumération `stage` (`json/enums/stage.json`, **provisoire**) | `young`, `pole`, `mature`, `old` |

Noms repris tels quels d'une source : `nemeton_stands` (spec §3), `inventaire_video`
(schéma nemeton 1.7.0), `fertilite.csv` (sylvostation), `trees_init` et `sim/trees`
(BRIEF §4), clés du biome (BRIEF §5, en français pour rester lisibles par un forestier),
`species.csv` (mission 011).

## Ce que les contrats de la mission 044 ne contrôlent pas

Le validateur lit un fichier à la fois (voir « Hors de M0 ») ; ces règles reviennent donc à
`assets` (mission 047) et aux tests d'acceptation (mission 045) :

- la suite des années de l'index (t0, t0 + N, t0 + 2N…, puis la dernière année), leur ordre, et
  leur unicité ; l'unicité des années d'une cellule de la fiche ;
- que chaque année de l'index ait son `tiles/<année>/`, son `web/rasters/g_<année>.tif` (en mode
  `sim`) et une fiche portant la même liste d'années ; que l'année du nom de fichier d'un
  `g_<année>.tif` soit celle de l'index ;
- que `scale_max_m2_ha` dépasse `scale_min_m2_ha` ;
- que `instances` d'une année soit la somme de ses tuiles, et égal au nombre d'arbres vivants de
  `sim/trees` ;
- que `h_dom_m` d'une cellule soit le même sur toutes ses lignes de `sim/cells`, et que la fiche
  recopie `sim/cells` et `sim/flags.parquet` à l'identique ;
- que `year_step` de `config.yml` soit celui de l'index, et `run_config_sha256` celui de `run.json` ;
- les extras du `tileset.json` (`etat`, `source`, `annee`, `instances`), prévus au plan §3 mais
  hors du périmètre de la mission 044 : `tileset.schema.json` n'est pas modifié ;
- avec `--require-outputs`, `tiles/index.json` et les `g_*.tif` sont exigés comme toute sortie,
  même sans `sim/` ; le jeu fictif sans `sim/` ne passe donc pas ce mode (aucun test ne l'emploie).

## Ce que les contrats de la mission 051 ne contrôlent pas

Le validateur lit un fichier à la fois ; ces règles reviennent à `post` (mission 053), à `assets` et
aux tests d'acceptation (mission 052) :

- que `essence` et `groupe` d'une ligne de `params/tarif.parquet` ne soient pas renseignés tous les
  deux, et que chaque modèle ait tous ses termes (a, b, c de `volume_feuillus` ; les termes du profil
  et de E(D) sont ceux de la mission 050) ;
- que `carbon_roots_t_ha` soit accompagnée de `provisoire` vrai sur toutes ses lignes ;
- qu'aucune ligne de `sim/summary.parquet` n'existe pour une cellule sans arbre vivant, et qu'il y en ait
  une pour chaque couple (cellule, essence) vivant ; que `stems_not_computed_ha` plus les tiges calculées
  fasse les `stems_ha` de `sim/cells` ;
- que `sim/summary_zone.parquet` soit égal à la somme de `sim/summary.parquet` par type de végétation,
  et que ses moyennes valent total / `forest_area_ha` ;
- que `run_config_sha256` de `sim/post.json` soit celui de `sim/run.json` et de `config.yml`, que les
  empreintes soient celles des fichiers lus, que `tarif_commit` soit le `source_commit` de
  `params/tarif.parquet`, et que `tree_years_not_computed` soit la somme de `out_of_domain` et de
  `without_tarif` ;
- que la fiche v3 recopie `sim/summary.parquet` (sommes par cellule) et que `volume_partiel`, `notes`
  et `tarif` suivent le contenu du summary ; la cohérence entre l'année et la composition de la fiche
  (somme des essences) n'est pas non plus lue ;
- que la part vaille exactement 1 quand aucune tige n'est calculée (c'est `post` qui l'écrit, et non un
  quotient arrondi).

## Ce que les contrats de la mission 060 (M5a) ne contrôlent pas

Le validateur lit un fichier à la fois ; ces règles reviennent à `simulate` (code 2) et aux tests
d'acceptation de M5a :

- que `d_class` soit inférieur à K (`simulate.ser.diameter_classes`), qu'un `cell_id` de `cohorts_init`
  soit dans la grille et forestier ;
- que `sim/cells` porte `seedlings_ha` et `seedling_h_mean` si et seulement si `run.json` dit
  `recruitment = cohorts` (la règle est testée dans `contracts/tests/test_m5a_contracts.py`) ;
- que les années de `sim/cohorts` et de `sim/cells` au niveau SER soient t0, t0 + N, … et la dernière
  (N = `write_step`) ;
- que `params/regeneration.parquet` donne, pour chaque essence simulée, tous les termes que le moteur lit ;
- que `cohorts_init` et `sim.cohorts` n'aient aucune ligne pour une cellule non forestière.

## Hors de M0

- contrôle des pixels (plages de valeurs, couverture du nodata) : seuls les en-têtes sont lus ;
- validation complète du contenu glTF (Khronos glTF-Validator), prévue en M4 ;
- contrôles croisés entre fichiers (un `station` de biome présent dans `station_type.csv`,
  une somme de composition égale à 1, un `cell_id` dans la grille) ;
- vérification d'un `schema_version` dans les fichiers Parquet ;
- lecture d'un Parquet par groupes de lignes : un fichier est lu en entier (3 millions
  d'arbres : 1,6 s et 0,9 Go de mémoire).

## Ce que les contrats de la mission 068 (M6a) ne contrôlent pas

Le validateur lit un fichier à la fois ; ces règles reviennent à `assets` (mission D), aux tests
d'acceptation (mission C) et à la vue :

- que la somme des arbres des blocs d'une année soit celle de `tiles/index.json` ; que `trees` de
  `massif/index.json` soit la somme de `trees_by_kind` et celle de ses blocs ; que chaque fichier listé
  existe et que `models[]` couvre toutes les essences des blocs ;
- que `models[].model` soit le nom d'un fichier de `assets/trees/`, que l'alias pointe vers un code de même
  essence (le validateur de `.glb` le contrôle de son côté, par `species.csv`) ;
- que les `seedlings[]` d'un bloc soient ceux de `sim/cells`, et `seedlings_simulated` celui de `sim/run.json` ;
- que les altitudes de `ground.z` soient celles de `altitude.py`, et le repère des arbres (quatre arbres aux
  extrémités, cas asymétrique) ;
- que les segments d'un exemplaire soient ceux du générateur à l'octet près (mission E) ; que le `.glb` soit
  construit de ses segments (T1 : mêmes sommets dans les tuiles) ;
- que les `extras` du `.glb` (`D_cm`, `H_m`…) soient les métadonnées de l'exemplaire, et que ces dimensions
  soient celles de la décision Q6 ;
- le glTF-Validator de Khronos (job `m6` de la CI, plan T4) : le validateur du projet n'en tient pas lieu ;
- que `R/biomes.R` lise `biomes/stades/stage_breaks.yml` : tant que la reprise de R n'est pas faite,
  `BIOMES_STAGE_BREAKS` garde ses valeurs et un test compare les deux ;
- que `viewer.*` et `assets.models.*` soient mesurés : ce sont des constantes d'illustration.
