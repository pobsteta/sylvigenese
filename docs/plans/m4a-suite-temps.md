# Plan de la suite de M4a : le futur simulé dans `assets` et `viewer-web` (25/11/2026)

> Plan rendu par un `dev` (temps « prendre »), **à valider** par l'orchestrateur, et par Pascal pour
> les questions Q1 à Q3. Les décisions techniques T1 à T10 sont celles que le `dev` propose de
> trancher, avec leur raison. Pascal peut défaire chacune d'elles.
> Sources lues : CLAUDE.md, BRIEF §4, §9 et §10, spec §1, §2, §9, §10 et §11, ADR 0002, plan de M3a,
> fiches 028 à 030, `docs/referentiels/itowns-instancing.md`, code de `assets`, `viewer-web/src` et
> `tests/m4`, contrats `sim.*`, `cell_sheet`, `tileset` et `run`, fin du journal.
> Chiffres relevés sur `tests/fixtures/zone_fictive/sim/`. Ce `sim/` est local et date d'un essai
> antérieur à 042 : ses ordres de grandeur sont sûrs, ses valeurs exactes ne le sont pas.

**En une phrase :** faire lire `sim/` par `assets`, qui écrira une tuile 3D et une fiche par année
retenue, et donner à la vue un choix de l'année et une fiche qui montre l'évolution de la cellule,
pour que Pascal voie le futur simulé et que le critère M4 a (100 000 instances dessinées, comptées
par l'API, et images par seconde relevées) soit prouvé.

## 1. Ce qui existe, ce qui manque

**Ce qui existe** (missions 028 à 030, puis 032) :
- `assets` lit `trees_init/` et écrit l'état initial :
  - deux modèles glTF génériques (feuillu, résineux) ;
  - `tiles/<t0>/tileset.json`, en 3D Tiles 1.1 : quatre tuiles carrées de 500 m, contenu `.gltf`
    avec `EXT_mesh_gpu_instancing` (TRANSLATION, SCALE = (r, h, r), r tiré de `crown_area`) ;
  - les fiches `web/cells/t_<x>_<y>.json`. Le contrat prévoit déjà un tableau `years`, mais une
    seule année y est remplie ;
  - le COG de `vegetation_map`.
  - **Si `sim/` est présent, `assets` s'arrête en erreur** : `make all` casse donc aujourd'hui à
    l'étape `assets`.
- La vue, en iTowns 2.46 publié (three 0.174) :
  - une seule couche `OGC3DTilesLayer`, la carte des types et le MNT local ;
  - la fiche s'ouvre au clic ;
  - le curseur `#annee` est présent mais **désactivé** ;
  - `/api/config.json` liste déjà les années présentes sous `tiles/` ;
  - `window.sylvigenese` expose le compte des instances et les images par seconde.
- `tests/m4` : 83 tests de l'état initial, dont la sonde Playwright (14 080 instances).
- `simulate` écrit `sim/trees/year=AAAA/`, `sim/cells/year=AAAA/`, `flags.parquet` et `run.json`
  (101 années, de 2022 à 2122, 815 Mo). Arbres vivants :

  | Année | Arbres vivants |
  |---|---|
  | 2022 | 14 080 |
  | 2042 | 74 494 |
  | 2052 | **100 624** |
  | 2082 | 183 101 |
  | 2122 | 402 548 |

  Chaque mort est écrite une seule fois, avec le statut `dead`.

**Ce qui manque :**
1. Lire `sim/` : partitions Hive, `status`, `cw` au lieu de `crown_area`.
2. Choisir les années retenues.
3. Écrire une tuile par année.
4. Écrire des fiches qui portent toutes les années retenues.
5. Écrire un index des années.
6. Nettoyer les années périmées. `tiles/2021/` subsiste par exemple, alors que t0 vaut maintenant
   2022.
7. Côté vue : le curseur actif, le changement de couche, la fiche d'évolution, et le comptage et la
   mesure année par année.
8. Les tests d'acceptation de tout cela.
9. Il manque aussi aux sorties de `simulate` :
   - la **hauteur dominante de chaque cellule** : elle n'est connue que des cellules au-dessus du
     plafond, par `flags.parquet`, `hdom_au_dessus_du_plafond` (Q1) ;
   - le **volume et le carbone** : `post` n'est encore qu'un squelette (Q2).

## 2. Découpage proposé (5 missions, numéros à donner par l'orchestrateur)

| # | Agent | Mission en une phrase (quoi, pourquoi) | Peut | Ne doit pas | Tests |
|---|---|---|---|---|---|
| A | `dev` | **Contrats de la suite de M4a** : fixer les formats avant le code, pour que A, B, C et D travaillent sur la même cible. Contenu : fiche v2, `tiles/index.json`, bloc `assets` de `config.yml` (§3). | `contracts/json/{cell_sheet,tiles_index,config}.schema.json`, `contracts/catalog.yml`, `contracts/tests/`, `contracts/README.md` | toucher `python/`, `viewer-web/`, `simulate/` ; affaiblir un contrat existant | un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert |
| B | `testeur` | **Tests d'acceptation de la suite** (`tests/m4/`), écrits sans lire le code, pour que la tranche ne se juge pas elle-même (détail ci-dessous). | `tests/m4/` (nouveaux fichiers, aide, sonde) | lire `python/` ou `viewer-web/src` ; sauter un test ; affaiblir une assertion de 030 | chaque critère a un test discriminant ; rouge attendu jusqu'à C et D |
| C | `dev` | **`assets` lit `sim/`**, pour donner à voir le futur simulé et non plus le seul état initial (détail ci-dessous). | `python/sylvigenese/assets.py`, `assets_lib/` (nouveau `sim_state.py`), `python/tests/test_assets*.py`, cible `assets` du Makefile | importer `simulate` ou `post` ; interpoler ; écrire un `.glb` comme contenu de tuile ; inventer une valeur absente de `sim/` | tests unitaires ; un arbre de coordonnées connues (est 700 012,5 ; nord 6 500 987,5, EPSG:2154) tombe dans la bonne tuile et la bonne cellule ; rejeu identique à l'octet près ; tests de B verts |
| D | `afficheur` | **La vue fait défiler les années**, pour que Pascal suive une cellule dans le temps (spec §1, point 4) (détail ci-dessous). | `viewer-web/` (src, test, configuration) | dépendre du réseau ; afficher un chiffre sans « provisoire » ; garder en mémoire plus de deux années de tuiles | `node --test` (choix de l'année, mise en forme de l'évolution) ; sonde de B verte ; captures à deviceScaleFactor 2 en t0 et en dernière année |
| E | `dev` | **Tenir la durée de la suite de tests sous le plafond de la CI**, sans retirer ni affaiblir un test, car la suite dure déjà 44 min 30 s sous un plafond de 45 min (§6). | `tools/ci/run_tests.sh`, `.github/workflows/ci.yml`, cibles `test*` du Makefile | modifier une assertion ou le nombre d'années d'un test ; relever le plafond sans le dire au journal | durée par section relevée par la CI elle-même ; CI verte ; même liste de tests passés qu'avant (comparaison des identifiants pytest) |

**Mission B (`testeur`), ce qu'elle couvre :**
- t0 et années retenues ;
- une instance par arbre **vivant** de l'année, à sa position ;
- aucun arbre mort dessiné ;
- une fiche qui porte toutes les années, avec des chiffres égaux à ceux de `sim/cells` ;
- l'index des années ;
- les années périmées effacées ;
- les refus : `run.json` absent, partition manquante, bloc `simulate` différent du run ;
- dans la vue :
  - le choix de l'année ;
  - le compte, année par année ;
  - **100 000 instances chargées et dessinées sur la zone de charge** (T8) ;
  - les images par seconde relevées.

**Mission C (`dev`), ce qu'elle produit :**
- les années retenues (T1) ;
- une tuile par année, faite des seuls arbres vivants ;
- des fiches qui portent toute l'évolution de la cellule (§3) ;
- `tiles/index.json` ;
- une écriture atomique (T6) ;
- le mode état initial gardé quand `sim/` est absent.

**Mission D (`afficheur`), ce qu'elle produit :**
- le curseur, sur les années de l'index ;
- un seul tileset en mémoire à la fois, l'ancien gardé jusqu'au chargement du nouveau ;
- la fiche de l'année choisie, avec un tableau de son évolution ;
- la commande `--year` à l'année choisie ;
- dans `window.sylvigenese` : `years`, `setYear(a)`, et le compte et les images par seconde par
  année.

**Missions conditionnelles**, selon les réponses de Pascal :
- **F**, si Q1 est oui (`dev`, Rust) : `simulate` écrit `h_dom_m` dans `sim/cells`. Périmètre : le
  contrat `sim.cells`, `simulate/src/sorties.rs`, et les tests de `simulate`, qui passent à
  l'identité 1 à N fils ; `tests/m3`, avec un ajout du testeur. La référence `nominal.json` n'est
  pas touchée.
- **G**, si Q2 est oui (`dev`, Python) : `post` écrit `sim/summary.parquet` à partir de
  `params/tarif.parquet`, qui est synthétique et provisoire sur le jeu fictif.
- Si Q3 est oui, aucune mission en plus : C écrit `web/rasters/<indicateur>_<année>.tif` et D en fait
  une couche du sol.

**Ordre des vagues :**
1. Pascal répond à Q1, puis Q2, puis Q3 : le contenu de la fiche en dépend.
2. Vague 1 : A, B et E. B part du plan et des schémas de A, comme 039 était partie de 033. E ne
   dépend de rien.
3. Vague 2 : C (et F ou G s'ils sont décidés).
4. Vague 3 : D.

## 3. Contrats à ajouter ou à modifier

- **`cell_sheet` (schema_version 2)** :
  - pour chaque année :
    - `stems_ha`, `basal_area_m2_ha` et `d130_mean_cm`, soit le diamètre moyen pondéré par les
      tiges, recalcul arithmétique exact de `sim/cells` ;
    - la composition par essence, avec `stems_ha` et `basal_area_m2_ha`, et `share` défini comme la
      part des tiges, ce que dit le contrat ;
    - `source`, qui vaut `trees_init` ou `sim` ;
    - `flags[]` de l'année, recopiés de `flags.parquet` (`hdom_au_dessus_du_plafond` avec sa
      valeur, `trouee_sans_recrue`) ;
  - au niveau du document, les `notes` communes (provisoire, semis non simulés, volume et carbone).
    Elles ne sont plus répétées pour chaque cellule et chaque année : la fiche fait aujourd'hui 972
    Ko pour une seule année ;
  - `h0_m` reste réservé à t0 (`h0.tif`), et `h_dom_m` s'ajoute si F est décidée ;
  - la vue refuse la version 1 dès qu'un `sim/` existe.
- **Nouveau contrat `assets.tiles_index`** (`tiles/index.json`, JSON Schema). Il porte :
  - `t0`, `years[]`, `year_step` et `source` ;
  - `run_config_sha256`, copié de `run.json` ;
  - les instances vivantes de chaque année, les morts de chaque année exclues, et le nom des tuiles.

  La vue lit l'index plutôt que de lister les dossiers.
- **`tileset` (extras)** : `etat` vaut `simulé` ou `initial`, avec `source`, `annee` et `instances`
  (vivants seulement). Les tests vérifient ces extras. Le schéma officiel de CesiumGS ne change pas.
- **`config`** : nouveau bloc `assets`, avec `year_step`, un entier supérieur ou égal à 1, **exigé
  dès que `sim/` existe**. Sans lui, `assets` s'arrête avec le code 2 : aucune valeur par défaut
  silencieuse. `config.yml` du dépôt : `year_step: 10`.
- `sim.trees`, `sim.cells` et `run` ne changent pas, sauf si F est décidée (`h_dom_m` dans
  `sim.cells`).

## 4. Choix techniques (le `dev` propose de trancher, avec sa raison)

- **T1. Une année sur N, et non toutes.**
  - Années retenues : t0, t0 + N, t0 + 2N…, et toujours la dernière année. Toutes sont dites dans
    l'index.
  - N vaut 10 dans `config.yml`, et se règle sans code.
  - Raison : le BRIEF §9 dit lui-même « une tuile par année retenue (pas de 5 ou 10 ans) ». Le prix
    se lit dans T2.
  - Avec N = 10, 2052 (100 624 vivants) est une année retenue.
- **T2. Volume.** La mesure de 028 donne environ 27 octets par instance (TRANSLATION et SCALE en
  float32), pour 380 Ko et 14 080 instances. Sur le massif fictif (100 ha) :

  | Pas | Années retenues | Instances cumulées | Volume des tuiles |
  |---|---|---|---|
  | 1 an | 101 | environ 19 millions | environ 520 Mo |
  | 5 ans | 21 | environ 4 millions | environ 110 Mo |
  | 10 ans | 11 | environ 1,9 million | environ 55 Mo |

  - À N = 10, les fiches pèseront environ 10 Mo une fois les notes mises au niveau du document.
  - Un massif réel de 20 km² multiplie ces volumes par 20 environ : environ 1,1 Go à N = 10.
  - On le tient par le pas et par `tiles/` hors dépôt.
  - La quantification (`KHR_mesh_quantization`) diviserait le volume par deux environ. Elle n'est
    pas retenue en M4a : sa lecture par three dans `EXT_mesh_gpu_instancing` n'est pas éprouvée.
    C'est à essayer en M4b si le volume gêne Pascal.
- **T3. Pas d'interpolation entre les années.**
  - Options pesées :
    - (a) aucune ;
    - (b) un morphing de h et cw par `tree_id` ;
    - (c) un pas d'un an.
  - Raison :
    - (b) dessinerait des états que `simulate` n'a pas calculés, alors que la règle est de ne rien
      inventer ;
    - (b) ne saurait que faire des recrues et des morts ;
    - si Pascal veut une évolution continue, (c) l'obtient sans rien inventer, au prix de T2.
- **T4. Source unique dès que `sim/` existe.** Toutes les années, t0 compris, viennent de `sim/` :
  h avancé à la fin de t0, et rayon de houppier = cw / 2, `cw` venant de l'allométrie.
  - Sinon, le houppier mesuré (`crown_area`) sauterait à la première année simulée : ce saut serait
    un artefact.
  - Le mode état initial reste celui de 028 quand `sim/` est absent.
  - `hcb` n'est pas utilisé, car les modèles génériques ont un tronc fixe jusqu'en M6.
- **T5. Arbres morts.** Ils ne sont pas dessinés (instances = `status = alive`). Leur nombre par
  année est écrit dans l'index. Le bois mort n'est pas simulé : rien n'est inventé.
- **T6. Cohérence et reprise.**
  - `assets` refuse (code 2) dans trois cas :
    - un `run.json` absent ;
    - une partition retenue absente ;
    - un bloc `simulate` de `config.yml` (t0, years, seed) différent de `run.json`.
  - Il écrit dans `tiles/.en_cours/`, valide, puis remplace `tiles/`. Les années périmées
    disparaissent ainsi.
  - Le validateur n'est appelé que sur les partitions lues, pas sur les 815 Mo de `sim/`.
- **T7. La vue garde un seul tileset en mémoire** : à 2122, 402 548 instances, soit environ
  80 triangles par arbre et 32 millions de triangles.
  - Changer d'année remplace la couche.
  - La fiche relit le fichier de sa tuile, qui porte toutes les années.
  - Les niveaux de détail (spec §9 : un fichier glTF par niveau de détail) ne viennent que si les
    images par seconde l'exigent au relevé, et pas avant.
- **T8. Le critère des 100 000 instances se prouve sur une zone de charge synthétique**
  (`data/m4_charge`) :
  - le `sim/` y est écrit par l'aide de test : exactement 100 000 vivants et quelques morts, sans
    aucune valeur écologique, la zone étant marquée fictive ;
  - les années réelles du jeu fictif sont, elles, relevées et non jugées.
  - Raison : le jeu fictif n'atteint 100 000 vivants qu'en 2052, à cause d'une trajectoire « non
    validée écologiquement » (décision de Pascal). Si M3b ramène la densité vers des valeurs
    vraisemblables, un critère accroché à cette trajectoire tomberait.
- **T9. La mention « provisoire » est renforcée** sur chaque année simulée par la phrase de Pascal :
  « trajectoire technique, non validée écologiquement (décision du 25/11/2026) ».
  - La carte des types de végétation est dite « état initial », car les types n'évoluent pas dans
    `simulate`.
  - Les semis sont dits « semis non simulés ».
  - Raison : appliquer une décision de Pascal et la spec §10. Ce n'est pas une décision nouvelle.
- **T10. Fiche d'évolution.** Elle prend la forme d'un tableau des années retenues : tiges/ha, G,
  d moyen, essences, signalements. L'année choisie est mise en évidence. Pas de graphique en M4a :
  il ajouterait une dépendance et un test visuel, sans information de plus.

## 5. Questions pour Pascal (une par une, dans cet ordre)

**Q1. La fiche doit-elle montrer la hauteur dominante de la cellule à chaque année ?**
- *Contexte.* La hauteur repose sur le MNH et sur le plafond de la station (votre décision du
  24/11). Mais `simulate` n'écrit la hauteur dominante d'une cellule que lorsqu'elle dépasse le
  plafond (environ 45 % des cellules, signalées). Pour les autres cellules, la fiche ne pourrait
  donner qu'une hauteur recalculée à partir des arbres par un autre estimateur : ce serait inventer.
- *Proposition.* Oui : une mission courte (F) fait écrire `h_dom_m` dans `sim/cells` par
  `simulate`. La fiche montre alors la hauteur dominante, le plafond et le dépassement, année par
  année.
- *Si oui :*
  - une mission Rust de plus avant C, avec un contrat `sim.cells` modifié ;
  - M3a est rouvert sur ses sorties, mais pas sur sa trajectoire ;
  - le dépassement du plafond devient visible dans la vue, ce qui servira M3b.
- *Si non :* la fiche montre tiges/ha, G, d moyen et composition, plus la hauteur des seules cellules
  signalées au-dessus du plafond, et elle dit pourquoi les autres manquent.

**Q2. Le volume et le carbone entrent-ils dans la suite de M4a ?**
- *Contexte.* La spec §1 annonce une fiche avec le volume et le carbone, calculés par `post` à partir
  du tarif. `post` n'est encore qu'un squelette. Sur le jeu fictif, le tarif est synthétique et
  provisoire. Sur un massif réel, il vient de tarif-nemeton, dont la licence vous est réservée.
- *Proposition.* Non pour la suite de M4a. Les deux champs restent vides et la fiche le dit. `post`
  devient une mission à part (G), après M4a, parce qu'elle soulève ses propres questions de tarif.
- *Si oui :* une mission Python de plus en vague 2. La fiche affiche des volumes et des carbones
  calculés sur un tarif synthétique, marqués provisoires. M4a finit plus tard.
- *Si non :* M4a finit plus tôt. La fiche affiche « volume et carbone non calculés (post) » jusqu'à
  G.

**Q3. La vue doit-elle montrer, au sol, une carte d'un indicateur qui change avec l'année ?**
- *Contexte.* Le BRIEF §10 demande un « raster temporel des biomes et des indicateurs ». Or les types
  de végétation ne changent pas dans `simulate` : seule la carte d'un indicateur pourrait évoluer.
- *Proposition.* Oui, un seul indicateur, la **surface terrière par cellule** (G, m²/ha), en COG par
  année retenue, avec une échelle de couleurs fixe sur toutes les années pour que les années se
  comparent. La couche porte la mention « non validée écologiquement ». Sur le jeu fictif, G monte
  jusqu'à environ 350 m²/ha, ce qui se verra.
- *Si oui :* C écrit environ 11 COG de 1 600 cellules, ce qui est négligeable, et D ajoute une
  couche et sa légende.
- *Si non :* seule la carte des types reste, dite « état initial ». Le raster temporel est reporté.
- Le choix de l'indicateur (G, tiges/ha, ou d moyen) relève lui aussi de votre décision.

## 6. Risques

- **Durée des tests : risque immédiat.** La suite dure environ 44 min 30 s (relecteur de la PR #8)
  pour un plafond de la CI de **45 min** (`ci.yml`, `timeout-minutes: 45`). Toute addition la
  fera échouer. Où gagner, sans retirer de test (mission E, ou testeur pour ce qui touche
  `tests/`) :
  1. **Mesurer d'abord** : écrire dans le journal de la CI la durée de chaque section de
     `run_tests.sh`. Aujourd'hui, aucune durée par section n'est connue.
  2. **Découper la CI en tâches parallèles** : R, Rust et contrats ; m1 et m2 ; m3 ; m4. Chacune
     reste sous le plafond, et la durée totale devient celle de la plus longue. C'est le plus gros
     gain, sans toucher un seul test. Le prix : des minutes de CI et des caches cargo et R à régler.
  3. **`tests/m4` ne relance pas 100 ans de `simulate`** :
     - le `sim/` réel est éprouvé par un run de 20 ans sur une copie (environ 25 s, années 2022,
       2032 et 2042) ;
     - la charge est éprouvée sur la zone synthétique (T8) ;
     - les 100 ans restent jugés par `tests/m3`.
  4. `tests/m3` lance quatre runs de 100 ans à la suite : chaîne, t1bis, deux fils, sept fils, soit
     environ 115 + 115 + 60 + 40 s. Lancer t1bis, deux fils et sept fils en parallèle (trois
     processus) sauve 2 à 3 min, assertions inchangées. Cela revient au testeur.
  5. Le bout en bout de 100 ans de `cargo test` (316 s) double celui de `tests/m3`. On peut le
     compiler en release, ou le raccourcir si le relecteur juge que `tests/m3` le couvre. C'est à
     trancher par l'orchestrateur : ce ne serait pas un affaiblissement silencieux.
  6. Les zones variantes de m1, m2 et m4 relancent toute la chaîne R (journal, PR #7) : partir d'une
     copie après la chaîne, comme le fait déjà `clone_zone` de m4.
  - Relever le plafond à 60 min ne serait qu'un pis-aller. S'il est choisi, il doit être dit au
    journal, et non fait en silence.
- **Rendu de 400 000 instances sous Chromium sans GPU (SwiftShader).** 32 millions de triangles en
  2122 peuvent dépasser le délai de 150 s de la page. Le critère se juge sur 100 000 (T8), et la
  dernière année est relevée, pas jugée. Si elle ne charge pas, D le dit, et les niveaux de détail
  deviennent une mission.
- **`sim/` périmé** : c'est déjà le cas de `tests/fixtures/zone_fictive/sim/`, antérieur à 042. T6
  le refuse s'il ne correspond plus à `config.yml`. Les 83 tests de l'état initial de 030 doivent
  tourner sur une zone **sans** `sim/` : aujourd'hui, `clean_chain_outputs` ne l'efface pas, et sur un
  poste où `make simulate` a tourné, ils liraient le futur. C'est à corriger par le testeur (B).
- **Lecture sans jugement.** La vue rendra très visibles une densité de 4 000 tiges/ha et un G
  d'environ 350 m²/ha. La mention de T9 est indispensable. Sans elle, la vue dirait plus que ce que
  M3a prouve.
- **iTowns** : l'instanciation n'est éprouvée qu'à 14 080 instances, et le changement de couche
  `OGC3DTilesLayer` à chaud n'est pas éprouvé. D commence par cet essai.
- **Mémoire de `assets`** : 2 millions de points à N = 10, tenus année par année et jamais tous à la
  fois.

- **Comptes de tests avant et après le découpage de la CI (relevé de la mission 049, reprise de la relecture de
  la PR n° 9, M2).** Méthode : `pytest --collect-only -q` par suite sur une copie `git archive e6e20ed` (avant :
  fusion de M3a, CI en un seul job) et une copie `git archive HEAD` de la branche avant la mission 049 (après :
  044 à 048, CI découpée par 043) ; tests cargo listés par `cargo test --locked -- --list` ; tests node par
  `node --test test/*.test.ts`. Les huit suites pytest sont celles de `run_tests.sh` (sections `contrats`,
  `m1`, `m2`, `m4`, `m3`) : aucune n'a été perdue au découpage.

  | Suite | e6e20ed (avant) | HEAD (après) | Écart | Cause |
  |---|---:|---:|---:|---|
  | `tests/m1` | 143 | 143 | 0 | |
  | `tests/m2` | 93 | 93 | 0 | |
  | `tests/m3` | 178 | 187 | +9 | 045 : `test_m3_hdom.py` (h_dom_m de chaque année égale à celle du moteur) |
  | `tests/m4` | 83 | 191 | +108 | 045 : sept fichiers `test_m4t_*` (charge 5, fiches 18, index 14, instances 15, rasters 10, refus 34, vue 12) |
  | `contracts/tests` | 398 | 494 | +96 | 044 : `test_m4a_temps_contracts.py` (91) ; cas `assets.basal_area_raster` et `assets.tiles_index` dans `test_cases.py` (+4, un conforme et un fautif chacun) ; schéma `tiles_index` au catalogue (+1 dans `test_catalog.py`) |
  | `python/tests` | 66 | 94 | +28 | 047 : `test_assets_sim.py` (26) ; `test_assets.py` (+2, mêmes refus pour `sim/`) |
  | `tools/fixtures/tests` | 27 | 27 | 0 | |
  | `tests/contracts` | 113 | 113 | 0 | |
  | **Total pytest** | **1 101** | **1 342** | **+241** | 9 + 108 + 96 + 28 |
  | cargo (`simulate`) | 171 | 175 | +4 | 046 : deux tests `non_regression` (h_dom_m), listés chacun deux fois par `--list` |
  | node (`viewer-web`) | 21 | 36 | +15 | 048 : `test/temps.test.ts` |

  - **La mission 043 n'a ajouté ni retiré aucun test** : ses commits (`1ab0605`, `b9dfc8b`, `ea5348b`,
    `85d2430`) ne touchent que `ci.yml`, `run_tests.sh`, le journal et la fiche. Tout l'écart vient des missions
    044 à 048. La CI découpée lance les mêmes chemins qu'avant.
  - `tests/m3` à e6e20ed ne se collecte pas sur une copie `git archive` nue : un module lit `chm_date.tif`, fichier
    généré, absent de l'archive. Il a fallu y copier ce fichier (celui du dépôt de travail) pour compter 178.
  - Après la mission 049 : `contracts/tests` 500 (+6 : cas h_dom_m null, tree_id), `python/tests` 96 (+2 : I2),
    node 38 (+2 : M1) ; le reste est inchangé.
