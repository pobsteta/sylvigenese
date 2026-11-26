# Plan de M6a : les arbres du générateur dans les deux vues, et la vue massif sous Godot (26/11/2026)

> Plan rendu par un `dev` (temps « prendre »), **à valider** par l'orchestrateur, et par Pascal pour
> les questions Q1 à Q5, à poser une par une. Les choix T1 à T12 sont ceux que le `dev` propose de
> trancher lui-même, avec leur raison. Pascal peut défaire chacun d'eux.
> Sources lues : CLAUDE.md ; BRIEF §3, §4, §9 à §13 ; spec §2, §9, §11 ; ADR 0003 et 0006 ;
> `viewer-massif/project.godot` ; `python/sylvigenese/assets.py` et `assets_lib/` ; `contracts/`
> (`catalog.yml`, `massif_block.schema.json`, `gltf_generic.schema.json`, `validator/gltf.py`,
> `species.csv`) ; `viewer-web/src/sheet.ts` ; `docs/referentiels/itowns-instancing.md` et
> `godot-forest-demo.md` ; `R/biomes.R` et `biomes/*.yml` ; plans de M5a et de la suite de M4a ; fin du
> journal ; kanban ; `.github/workflows/ci.yml` ; `tools/ci/run_tests.sh`. Hors dépôt, en lecture seule :
> `/home/user/tarif-nemeton` (commit 4ee122c, `code/synth_arbres.py`, `synth_essences.py`,
> `synth_population.py`, `synth_calage.py`, `architecture_modeles.py`, `synth_planches.py`,
> `resultats/synth_arbres/`). Une génération d'essai a été lancée dans le conteneur, rien n'a été écrit.

**En une phrase :** il s'agit de faire entrer les arbres du générateur de tarif-nemeton dans les deux
vues, sous forme de modèles `.glb` à trois niveaux de détail et quatre stades par essence (la vue
iTowns et une vue massif Godot neuve), puis de bâtir cette vue massif (terrain, arbres, strate
herbacée et semis autour de la caméra) et de la prouver sans carte graphique. Le but : que Pascal
ouvre, depuis la fiche d'une cellule du web, la même place en vue immersive, avec de vrais arbres
d'essence reconnaissable, et que tout ce qui se vérifie sans GPU le soit déjà en CI.

## 1. Ce que M6a doit atteindre, ce qui existe

**Les critères de M6a :**
- **BRIEF §11 :** « arbres du générateur dans les deux vues (sans GPU : export et tests) ».
- **Spec §11 :** « Godot `--headless --import` et tests GUT. Export seulement si les modèles d'export
  sont téléchargeables ; sinon, reporté en M6b et signalé. »
- **BRIEF §10 :** lecture du massif, arbres du générateur, strate herbacée et semis générés autour de
  la caméra d'après le biome et le couvert ; un lien de la vue web ouvre la vue massif aux mêmes
  coordonnées.
- **Je lis les trois comme cumulatifs.** « Reprise du prototype » (BRIEF §3 et §10) tombe : le
  prototype est introuvable (journal du 26/11/2026), M6a part du squelette `viewer-massif/`.

**Ce qui existe :**
- `viewer-massif/project.godot` : un squelette vide (Godot 4.6, aucune scène, aucun test). ADR 0003 :
  projet neuf sous GPL-3, GUT, herbe autour de la caméra reprise de `godot-forest-demo` (CC BY 4.0,
  attribution), blocs MultiMesh réécrits d'après l'idée. Rien de cela n'est mesuré.
- `assets` (Python) écrit deux modèles **génériques** `assets/trees/{feuillu,resineux}.gltf`
  (`extras.generique = true`), les tuiles `tiles/<année>/*.gltf` en `EXT_mesh_gpu_instancing`, les
  fiches et les COG. Il **n'écrit pas `massif/<bloc>.json`**, bien que la spec §2 le dise : le
  contrat `assets.massif_block` (schéma v1 : arbres seuls, positions relatives à une origine
  EPSG:2154 + NGF-IGN69) existe sans producteur.
- Le validateur de `.glb` (`contracts/validator/gltf.py`) ne contrôle que l'en-tête (« à M0 »).
- Le générateur (`tarif-nemeton`, **dépôt privé**, « licence à définir avant toute ouverture ») :
  - `synth_arbres.generer_cale(essence, D, H, hbh, Rh, p, graine)` rend des **segments** (troncs de
    cône : `P0, P1, R0, R1, niveau, axe`), pas un maillage. Il n'écrit ni feuilles ni `.glb`. Seul
    l'export CSV (`exporter_cylindres`) existe.
  - Un hêtre de 40 cm et 28 m fait **38 900 segments** (9,4 km de bois) en 0,6 s ; un épicéa de
    40 cm, 45 490 ; un pin de 25 cm, 3 504 ; un hêtre de 8 cm, 384. Mesuré ici, numpy seul.
  - Onze essences (`ORDRE` de `synth_essences.py`). Dans `contracts/species.csv`, 13 codes espar
    (02, 03, 09, 11, 12P, 12V, 15S, 17C, 52, 61, 62, 63, 64) ont un `tarif_nemeton_code` ; tous les
    autres (10 châtaignier, 13G aulne, 22M merisier, etc.) n'ont **aucun modèle**.
  - Dépendances : numpy pour un arbre ; pandas et scipy pour la population et le calage.
  - Piège : `forme_tige()` lit `resultats/synth_arbres/bornes_dimensions.csv` **relativement au
    dossier courant** et, s'il est absent, rend 1 sans rien dire. Lancé d'ailleurs, le générateur
    donne d'autres résineux, sans erreur.
  - Les bornes d'architecture sont, selon leur propre en-tête, des « HYPOTHÈSES de départ ». Les
    sources des modèles architecturaux sont dans `donnees/modeles_architecturaux_sources.csv` ;
    plusieurs attributions y sont marquées « à confirmer ».
- Le lien web : la fiche porte `viewer-massif -- --x <X> --y <Y> --year <A>` (`sheet.ts`). La
  commande ne dit pas **où est la zone**, et `viewer-massif` n'est pas un exécutable.
- Le stade (`young, pole, mature, old`) d'une cellule vient de H0 / h_pot avec les seuils
  provisoires 0,25 / 0,60 / 0,90, **écrits en dur dans `R/biomes.R`**.
- Les biomes (`biomes/*.yml`) donnent `couvert` des strates arbustive et herbacée (jeu fictif :
  valeurs synthétiques, `provisoire: true`) et une composition herbacée aux noms fictifs. **Aucune
  hauteur d'herbe, aucun modèle d'herbe.** `sim/cells` porte `seedlings_ha` et `seedling_h_mean` en
  mode `cohorts` seulement.

**Ce qui manque :**
1. Un chemin du générateur vers des `.glb` : segments, maillage, trois niveaux de détail, quatre
   stades par essence.
2. Les tuiles iTowns bâties avec ces modèles à la place des génériques.
3. Le producteur de `massif/<bloc>.json`, et un contrat qui porte aussi le terrain, les couverts et
   les semis (la vue ne lit pas Parquet).
4. Toute la vue Godot : lecture, repère, terrain, arbres, herbe et semis, mentions « provisoire ».
5. Les tests sans GPU de cette vue, et le job de CI qui les lance.
6. Le lien web → massif qui dit la zone.
7. L'état des licences et des versions (Godot, GUT, générateur et ses données de calage).

## 2. Faits vérifiés pour cette session (réseau, 26/11/2026)

| Élément | Constat | Licence |
|---|---|---|
| Godot 4.6.3-stable, `Godot_v4.6.3-stable_linux.x86_64.zip` | redirection 302 puis 200, 71,8 Mo ; **dernière 4.6.x** (4.6.4 et 4.6.5 : 404) ; empreintes dans `SHA512-SUMS.txt` de la release (zip : `a035258d…`) | MIT (`LICENSE.txt` du dépôt Godot, première ligne lue) |
| Godot 4.6-stable | même schéma, 302 | idem |
| Modèles d'export 4.6.3 (`…_export_templates.tpz`) | **téléchargeables** (302 puis 200), mais **1,26 Go** ; empreinte `da606b61…` | MIT |
| Godot 4.7 et 4.7.1 | existent (302) ; `master` du dépôt est en 4.8 beta | MIT |
| GUT (`bitwes/Gut`) | README : 9.x pour Godot 4 ; **9.6.1 pour 4.6.x**, 9.7.1 pour 4.7.x ; `plugin.cfg` de `main` : 9.6.1 ; la page des versions, l'archive d'étiquette et l'API GitHub sont **refusées depuis ce conteneur** (403) ; seuls les fichiers `raw.githubusercontent.com` passent | **MIT** (`addons/gut/LICENSE.md`, copyright 2018 Tom « Butch » Wesley, lu) |
| Disque du conteneur | 5,7 Go libres | — |

- **Conséquence 1 : l'export est faisable.** Ses modèles sont téléchargeables : il n'est donc **pas**
  reporté en M6b au titre de la clause de la spec. Il se fait en CI (téléchargement et cache de 1,26 Go),
  pas dans ce conteneur (extraire les modèles de Linux et de Windows demanderait plusieurs Go sur 5,7).
- **Conséquence 2 : GUT ne s'obtient pas ici.** Un agent du conteneur ne pourrait ni lancer GUT ni le
  mettre à jour. D'où T10 (GUT 9.6.1 versionné dans le dépôt, licence jointe).
- Le dépôt n'a pas d'accès GitHub pour cette session : je n'ai pas lu les notes de version. Les
  versions 4.6.4 et suivantes de la série 4.6 peuvent sortir ; la CI fige 4.6.3.

## 3. Découpage proposé (8 missions, numéros à donner par l'orchestrateur)

| # | Agent | Mission en une phrase (quoi, pourquoi) | Peut | Ne doit pas | Tests |
|---|---|---|---|---|---|
| A | `acquereur` | **Référentiel du générateur et des outils** : formats de sortie, dépendances, auteurs (git), licences des jeux de données qui ont calé `bornes_dimensions.csv` (QSM BioDiv, Wytham, Demol, etc.), état des attributions architecturales « à confirmer » ; licences et empreintes de Godot 4.6.3, des modèles d'export et de GUT 9.6.1 ; ce que `godot-forest-demo` impose à reprendre (CC BY 4.0). Prépare la réponse à Q1. | `docs/referentiels/generateur-arbres.{md,csv}`, `docs/referentiels/godot-gut.md` | copier du code ou une table de tarif-nemeton ; écrire une licence « présumée » | chaque ligne porte fichier et ligne ou `absent` ; empreintes recalculées sur le fichier téléchargé |
| B | `dev` | **Contrats de M6a et projet d'ADR 0007 (arbres du générateur et vue massif)**, avant tout code, comme 033 et 060. Contenu : `massif_block` v2 (§4) ; `massif/index.json` ; règle de nom des `.glb` et de leurs extras ; validateur de `.glb` renforcé ; seuils des stades sortis de `R/biomes.R` vers un fichier unique lu par R et par Python (T11) ; accord de la spec §9 (« un fichier par niveau de détail ») avec le BRIEF §4 (T2). | `contracts/` (schémas, `catalog.yml`, `README.md`, `validator/`, `tests/`), `config.yml`, `docs/adr/0007-arbres-generateur-vue-massif.md` (« proposée »), `docs/spec.md` (§2, §9, §10 : mise en accord seulement), `biomes/` (fichier des seuils de stade) | toucher `python/`, `R/`, `simulate/`, `viewer-*` ; affaiblir un contrat ; mettre une valeur écologique dans un schéma | un cas conforme et un cas fautif par règle nouvelle ; un `.glb` tronqué, sans nœud LOD2, ou sans `extras.source_commit`, refusé ; `make validate` vert |
| C | `testeur` | **Tests d'acceptation de M6a**, écrits sans lire le code de D et de F : côté Python (`tests/m6/`, avec un analyseur de `.glb` indépendant) et côté Godot (`viewer-massif/tests/`, GUT). Le testeur reprend aussi les tests de `tests/m4` qui épinglent les modèles génériques (voir risque « tests de M4 »). Il fournit la fixture d'exemplaires (§5, mission D). | `tests/m6/`, `viewer-massif/tests/`, `tests/m4/` (les seuls tests dépendant du modèle générique), `tests/fixtures/` (exemplaires synthétiques) | lire `python/sylvigenese/assets_lib` modifié par D ni les scripts de F ; sauter un test ; écrire une valeur présentée comme écologique | voir §6 ; rouge attendu jusqu'à D, E et F |
| D | `dev` (Python) | **Du segment au `.glb`, aux tuiles et au bloc massif** : lecture des exemplaires, maillage, trois niveaux de détail, quatre stades, `.glb` identique à l'octet près à chaque exécution ; tuiles iTowns bâties des mêmes sommets ; `massif/index.json` et `massif/<année>/<bloc>.json` v2 lus dans `sim/` (ou `trees_init/`) ; fonction unique du stade d'un arbre. | `python/sylvigenese/assets.py`, `python/sylvigenese/assets_lib/` (nouveaux `exemplars.py`, `lod.py`, `glb.py`, `stages.py`, `massif.py` ; `models.py`, `tiles.py`, `sim_state.py`, `initial_state.py`), `python/tests/` | importer du code de tarif-nemeton ; deviner un modèle pour une essence sans exemplaire ; casser l'identité à l'octet près ; changer `tiles/` des années ou le décompte des instances (14 080) | tests unitaires (§6) ; `tests/m4` rouvert par C vert ; `contracts/validate` vert sur `assets/trees/*.glb` et `massif/` |
| E | `dev` (dépôt tarif-nemeton, si Q1 = a) | **Export des exemplaires** : un script court de `tarif-nemeton` qui, pour chaque essence et chaque stade demandés, écrit les segments (CSV, ou Parquet) avec leurs paramètres (essence, D, H, hbh, Rh, graine, commit), en fixant le dossier courant et en **échouant** si `bornes_dimensions.csv` est introuvable. Il vit dans l'autre dépôt : PR à part, fusion par Pascal. | `tarif-nemeton/code/synth_export_exemplaires.py` (nouveau), `tarif-nemeton/resultats/synth_arbres/exemplaires/` | modifier `synth_arbres.py`, `synth_essences.py` ou les bornes ; changer un modèle tiré | mêmes segments, à l'octet près, que `synth_arbres.py --cylindres` pour un cas ; refus si bornes absentes |
| F | `afficheur` | **La vue massif Godot** (`viewer-massif/`) : arguments `--zone --x --y --year`, lecture de `massif/`, repère (T6), terrain, arbres en blocs MultiMesh avec trois niveaux de détail, strate herbacée et semis autour de la caméra (T8), bandeau de mentions « provisoire », sortie de contrôle `--selftest`. | `viewer-massif/` (scènes, scripts, `export_presets.cfg`, `CREDITS.md`, `addons/gut/` versionné, `README.md`), `docs/referentiels/godot-forest-demo.md` (attribution seulement) | lire `sim/` ou du Parquet ; ouvrir une valeur écologique dans un script ; reprendre un fichier de `godot-forest-demo` hors de la liste de l'ADR 0003 ; mesurer des images par seconde (M6b) | GUT de C verts ; `--headless --import` sans erreur ; `--selftest` à 0 |
| G | `dev` | **CI, export et lien web** : job `m6` (Godot 4.6.3 et GUT figés, empreintes vérifiées, import, GUT, export Linux et, selon Q5, Windows, exécution de `--selftest` sur le binaire exporté) ; section `m6` de `run_tests.sh` ; la commande de la fiche dit la zone (T7) ; versions dans le README. | `.github/workflows/ci.yml` (job `m6`), `tools/ci/run_tests.sh`, `tools/viewer-massif*` (lanceur), `viewer-web/src/sheet.ts` et ses tests, `README.md` | élargir le réseau de l'exécuteur au-delà de github.com ; relever un délai sans le dire au journal ; changer `tests/m4` hors de la ligne de commande | job `m6` sous 20 min (délai à relever, cache des modèles) ; la commande de la fiche est celle que le viewer accepte (test croisé) |
| H | `analyste` | **Mesures sans GPU et note M6b** : tailles des `.glb`, sommets et triangles par niveau de détail ; temps de génération ; nombre d'instances d'herbe et de semis par cellule du jeu fictif ; temps de chargement d'un bloc en mode sans rendu ; rédaction de `LANCER_CHEZ_SOI.md` (section M6) pour le PC de Pascal. | `bench/results/M6.md`, `bench/results/m6_*.csv`, `bench/results/LANCER_CHEZ_SOI.md` (section M6) | modifier le code ; présenter un compte de triangles comme des images par seconde | chaque chiffre renvoie à une ligne de CSV ; rejouable par un seul script |

**Mission C, ce qu'elle couvre** (le détail est au §6).

**Ordre des vagues :**
1. Pascal répond à Q1, puis Q2, Q3, Q4 et Q5, une question à la fois. Q1 change D et E ; Q2 change D ;
   Q3 et Q4 changent B, D et F ; Q5 change G et M6b.
2. Vague 1 : A (courte, B et la réponse à Q1 en dépendent).
3. Vague 2 : B. L'orchestrateur tranche l'ADR 0007 par délégation, sauf T-licence (voir Q1).
4. Vague 3 : C, D et E (E s'il y a lieu). D et F n'écrivent pas dans les mêmes dossiers, mais F
   lit le contrat de B et les fichiers de la fixture : F peut partir en parallèle de D dès que C
   a livré ses tests.
5. Vague 4 : F, puis G (G touche `ci.yml` et `run_tests.sh`, qui servent aussi aux autres : après F).
6. Vague 5 : H, puis la relecture. Le plafond humain est de 3 PR ouvertes : M6a tient en une PR
   (`sylvigenese`), plus une PR de `tarif-nemeton` pour E.

## 4. Contrats à ajouter ou à modifier (mission B)

- **Qui lit quoi.** `viewer-massif` ne lit que **`massif/` et `assets/trees/`** (spec §2 et ADR 0003).
  Le BRIEF §10 parle de « lecture de `sim/` » : je l'entends comme « les résultats de `sim/`, par
  `assets` ». Raisons : Godot ne lit pas Parquet ; un seul module (`assets`) lit `sim/` ; la vue ne
  dépend pas de la forme de `sim/` (aujourd'hui deux formes, `ifn_direct` et `cohorts`). Écart à
  inscrire à la spec §2.
- **`assets/trees/<espar>_<stade>.glb`** (contrat `assets.tree_model`, règle de nom `species_stage`
  déjà au catalogue ; `<stade>` ∈ `young|pole|mature|old`) : 3 nœuds `LOD0`, `LOD1`, `LOD2` (T2) ;
  `extras` : `species`, `stage`, `source` (commit de tarif-nemeton), `essence_generateur`, `D_cm`,
  `H_m`, `hbh_m`, `Rh_m`, `graine`, `H_ref_m`, `rayon_houppier_ref_m`, `provisoire: true`,
  `synthetique: true` (« arbre synthétique ; ne valide aucun tarif », BRIEF §9), `feuillage`
  (selon Q2). Le validateur lit les accesseurs, les bornes et les trois nœuds.
- **Modèle générique conservé comme repli signalé** (selon Q3) : `assets/trees/generique_<groupe>.glb`,
  `extras.generique: true`. Les `*.gltf` génériques actuels du M4 disparaissent des tuiles.
- **`massif/index.json`** (nouveau, comme `tiles/index.json`) : zone, `fictive`, EPSG:2154, années
  retenues, blocs par année avec leur emprise, nombre d'arbres, mentions, `provisoire`. C'est lui que
  lit la vue pour trouver le bloc de (x, y) et pour dire, sans deviner, quelles années existent.
- **`massif/<année>/<bloc>.json`**, schéma **v2** (v1 inchangé, conforme à l'identique) :
  - `trees[]` : comme en v1, `stage` calculé par la fonction unique (T11), `tree_id` stable ;
  - `ground` : `resolution_m`, `nx`, `ny`, `z` (altitude NGF-IGN69 aux nœuds de 25 m, ligne 0 au
    nord) ; ce que `altitude.py` donne déjà au pied de chaque arbre, pas une autre source ;
  - `cells[]` (une par cellule de 25 m du bloc) : `cell_id`, `x`, `y` (centre), `biome`,
    `herb_cover`, `shrub_cover` (lus dans `biomes/*.yml`, avec leur `provisoire`), `seedlings[]`
    (`species`, `seedlings_ha`, `h_mean_m`) **présent si et seulement si** `sim/run.json` dit
    `recruitment: cohorts` ; sinon `seedlings_simulated: false` ;
  - `mentions[]`, `provisoire` (spec §10) : « trajectoire technique, non validée écologiquement »,
    jeu fictif, Q2 et Q3 de M5a (stock initial déduit, survie par la lumière seule), « gibier,
    sous-bois et fructification non simulés », modèles génériques employés.
  - Pas de composition herbacée dans le contrat de la vue : les noms de la composition du biome sont
    fictifs et aucun modèle d'herbe n'existe (T8, Q4).
- **`config.yml`** : bloc `assets.models` (stades de référence : D par essence et par stade ; budgets de
  triangles par niveau ; `exemplars_dir` ou usage de `external.tarif_nemeton_dir` selon Q1) et bloc
  `viewer` (rayon d'herbe, plafond d'instances, distances de bascule des niveaux de détail), tous
  marqués `provisoire: true`, réglages d'affichage et non écologiques.
- **Stades** : fichier unique des seuils (aujourd'hui `BIOMES_STAGE_BREAKS` en dur dans `R/biomes.R`),
  lu par `biomes` (R) et par `assets` (Python) (T11). La mission B écrit le fichier et le schéma ; le
  `dev` de R adapte `R/biomes.R` dans une reprise séparée, sans changer un résultat.
- **ADR 0007** : T1, T2, T5, T6, T7 et T11, avec le crible FRANCE. La partie « licence du générateur »
  reste « en attente de Pascal » (Q1).

## 5. Choix techniques (le `dev` propose de trancher, avec sa raison)

- **T1. Un seul constructeur de maillage, deux sorties.** `assets` construit chaque modèle une fois à
  partir des segments, écrit le `.glb` (Godot) et reprend **les mêmes sommets** dans le contenu `.gltf`
  des tuiles (iTowns).
  - Raison : deux chemins diraient deux arbres différents dans les deux vues. Un test compare les
    octets des sommets.
  - Les tuiles restent en `.gltf` + `.bin` : le gestionnaire de `OGC3DTilesLayer` n'est enregistré que
    pour `/\.gltf$/` (`itowns-instancing.md`, point A) et un contenu `.glb` serait à éprouver. Les `.glb`
    sont les modèles du dossier `assets/trees/`, lus par Godot.
- **T2. Un fichier `.glb` par (essence, stade), trois niveaux de détail en trois nœuds** (`LOD0`,
  `LOD1`, `LOD2`, `extras.lod`, couverture d'écran indicative).
  - Raison : la règle de nom du catalogue et le BRIEF §4 disent un fichier `<species>_<stage>.glb` avec
    ses niveaux de détail ; la spec §9 dit « un fichier par niveau de détail ». C'est une
    contradiction entre deux sources : je propose de garder le BRIEF et d'accorder la spec.
  - Autre voie : trois fichiers `<species>_<stage>_lod<n>.glb`, qui change la règle de nom et le
    validateur. Écartée, non interdite.
- **T3. Réduction des segments.** Le générateur donne jusqu'à 45 000 segments par arbre : inutilisable
  tel quel (un tube à 6 faces = 540 000 triangles). Règle proposée :
  - `LOD0` : tige et branches de rayon au moins `r_min` (par ex. 1 cm), tubes de 5 à 6 faces, plus le
    feuillage selon Q2 ; `LOD1` : tige et branches de niveaux 1 et 2, tubes de 4 faces ; `LOD2` :
    tige et houppier en croix de deux ou trois plans.
  - Budgets de triangles de départ (réglages d'affichage, **provisoires**, à mesurer par H, jamais
    présentés comme mesurés) : LOD0 20 000, LOD1 2 000, LOD2 200. À 100 000 instances de M4, seul
    LOD2 est plausible dans les tuiles ; le budget des tuiles est un chiffre de H, pas une hypothèse.
  - Raison : la réduction par rayon minimal se dit et se teste ; elle n'invente rien d'écologique.
- **T4. `.glb` écrit à la main** (`struct` et numpy, comme `models.py`), sans `trimesh` ni `pygltflib`
  (absents). Le validateur du projet est renforcé ; **le glTF-Validator de Khronos** (paquet npm,
  Apache-2.0 à vérifier par A) est ajouté au job `m6` : la spec §9 le renvoie à « M4 » et il n'a pas
  été fait.
- **T5. Disposition de `massif/`** : `massif/index.json` et `massif/<année>/<bloc>.json`, bloc = tuile
  de 500 m de `tiles/` (mêmes identifiants `t_<x>_<y>`). Le catalogue dit `massif/*.json` : il passe à
  `massif/index.json` et `massif/*/*.json`. JSON et non binaire : un bloc de 500 m du jeu fictif porte
  de 3 000 à 4 000 arbres (14 080 sur 4 blocs), de l'ordre de 0,5 Mo ; le contrat existe déjà ; GDScript
  sait lire du JSON. Si un massif réel donne des blocs de plusieurs dizaines de Mo, le format se
  rouvre (risque).
- **T6. Repère de Godot** : x = est, y = haut (altitude NGF moins celle de l'origine du bloc), **z = −nord**
  (le nord est devant, comme `−Z` de Godot, et le repère reste direct). Les positions restent relatives
  à l'origine du bloc (float32 sûr : quelques km donnent moins de 0,3 mm).
  - Piège connu du projet (x et y inversés, « la Somalie ») : un test GUT pose quatre arbres aux
    extrémités nord, sud, est, ouest, avec des coordonnées asymétriques, et un test pytest relit
    l'altitude de leur pied.
  - Le terrain est la **MNT de la grille (25 m)**. Ce n'est pas le LiDAR à 1 m : le sol sera lisse et
    le pied d'arbre posé à moins de 0,5 m près de ce sol, par construction. Dit à l'écran (risque).
- **T7. Lancement et lien web.** La vue se lance par `godot --path viewer-massif -- --zone <dossier>
  --x <X> --y <Y> --year <A>`, enveloppée dans `tools/viewer-massif` (script). La commande de la fiche
  devient `viewer-massif --zone <dossier> --x … --y … --year …` : elle ne dit plus seulement la place,
  elle dit **où sont les données**. Une année qui n'est pas dans `massif/index.json`, un point hors
  de toute emprise ou une zone sans `massif/` : le code de sortie est non nul et le message donne les
  années ou l'emprise. Jamais l'année voisine.
  - Le test pinne ce changement dans `viewer-web` (`sheet.ts`) ; `tests/m4` en dépend, d'où G après F.
- **T8. Herbe et semis autour de la caméra** (BRIEF §10, mécanique de `godot-forest-demo`
  réécrite) :
  - un MultiMesh recentré quand la caméra a bougé de plus de `d` mètres, calculé dans un fil ;
  - le tirage est un **hachage déterministe** de (zone, `cell_id`, essence ou strate, rang) : mêmes
    plantes à chaque passage, aucun alea de `random()` ;
  - semis : par cellule et par essence, `round(seedlings_ha × 0,0625 ha)` avec arrondi aléatoire à
    espérance exacte (même idée que M3a), à la hauteur `h_mean_m`, sans autre source que `sim/cells` ; forme : le modèle `young` de l'essence à l'échelle de la hauteur (Q4). Plafond
    d'instances dit à l'écran quand il tronque ;
  - herbe : le nombre de brins est proportionnel à `herb_cover` de la cellule (biome), jamais à la
    composition ; les constantes de rendu (hauteur de brin, couleur, densité à couvert 1) sont dans
    `config.yml` (bloc `viewer`), `provisoire: true`, avec la mention « illustration, non mesurée »
    à l'écran (Q4) ;
  - sans cohortes (`ifn_direct`) : aucun semis dessiné, la mention « semis non simulés » est à
    l'écran. On ne les invente pas pour remplir.
- **T9. Pas de rendu dans les tests.** Trois étages, aucun ne demande de carte graphique : pytest
  (maillage, `.glb`, contrats) ; GUT en `--headless` (logique, arbre de scène, rendu factice de Godot) ;
  `--headless --import`, export, puis exécution du binaire exporté avec `--selftest`, qui charge la
  zone fictive, bâtit la scène, écrit des comptes (arbres, instances d'herbe, semis, blocs) et sort à 0.
  Aucune image par seconde, aucun pixel : c'est M6b.
- **T10. Versions figées** : Godot **4.6.3-stable** (dernière 4.6.x, MIT), GUT **9.6.1** (MIT), avec les
  empreintes SHA-512 de la release vérifiées dans le job. `GODOT_VERSION` de `ci.yml` (aujourd'hui
  `4.6-stable`) passe à `4.6.3-stable`. GUT est **versionné** dans `viewer-massif/addons/gut/` avec son
  `LICENSE.md` (le conteneur ne peut pas le télécharger, un agent ne pourrait donc pas lancer les
  tests) ; la source est dite dans `CREDITS.md`. Passer à 4.7.x demande GUT 9.7.1 : décision à part.
- **T11. Stade d'un arbre** (affichage) : h / h_pot de sa cellule, par les **mêmes seuils provisoires**
  que les biomes (0,25, 0,60, 0,90), lus dans le fichier unique que crée B. Raison : le contrat de
  l'énumération `stage` dit « position de la hauteur observée sur la courbe de hauteur » et un seul
  jeu de seuils garde le stade d'un arbre et celui de son biome cohérents ; deux copies de la valeur
  dériveraient. Les dimensions de référence (D, H) du modèle de chaque stade viennent de l'exemplaire ;
  l'instance est mise à l'échelle de h et de la largeur de houppier `cw` de `sim/trees` (échelle
  non uniforme comme en M4, dite : la tige s'épaissit avec le houppier).
- **T12. Pas d'exemplaire, pas d'arbre.** Une essence sans exemplaire n'est jamais rapprochée d'une
  autre (règle de M5a, « sans emprunt ») : elle est comptée dans `massif/index.json`, signalée à l'écran
  et dessinée selon Q3. Pour les exemplaires : le même (essence, stade, graine) redonne le même `.glb`
  à l'octet près, sur la même machine ; l'identité entre machines (numpy, flottants) n'est pas promise
  (même réserve que rustfft au kanban).

## 6. Tests sans GPU et job de CI

**Python (`tests/m6`, mission C, sans lire D) :**
- **Analyseur de `.glb` indépendant** (entête, bloc JSON, bloc binaire, accesseurs, bornes).
- Pour chaque couple (essence, stade) de la fixture : trois nœuds LOD ; triangles strictement décroissants
  et sous les budgets de `config.yml` ; la boîte englobante de LOD0 fait la hauteur `H_ref_m` à 1 % ;
  aucun sommet non fini ; extras `source`, `synthetique`, `provisoire` présents ; nom
  `<espar>_<stade>` conforme au catalogue et à `species.csv`.
- **Identité** : deux exécutions, mêmes octets ; un exemplaire modifié d'un segment, octets différents.
- **Les mêmes sommets dans les deux vues** : les sommets du modèle de la tuile égalent ceux du
  `LOD2` du `.glb`.
- **Repère** : un arbre de `trees_init` aux coordonnées connues (Lambert-93, EPSG:2154) se retrouve
  dans `massif/<année>/<bloc>.json` à sa place, avec quatre arbres aux extrémités (cas asymétrique) et
  l'altitude de son pied égale à celle de `altitude.py` ; le bloc dit `crs` et `vertical_datum`.
- **Cohérence entre fichiers** : somme des arbres des blocs = instances de `tiles/index.json` ; avec
  `cohorts`, `seedlings[]` égaux à `sim/cells` ; avec `ifn_direct`, `seedlings_simulated: false`.
- **Refus** : essence sans exemplaire (compte et signalement, pas de modèle emprunté) ; exemplaire
  corrompu ; `bornes_dimensions.csv` absent côté export (E) ; année demandée absente de l'index.
- **Non-régression de M4** : 14 080 instances, mêmes positions au dixième de mètre, mêmes années.
  Les tests qui épinglent « feuillu et résineux » (`test_m4_tuile.py:121`, `test_m4_instances.py:114`,
  `test_m4_variantes.py:72`, `test_m4t_instances.py:103`) sont **réécrits par le testeur** pour dire
  « un modèle par (essence, stade) » : c'est un changement voulu, dit dans la PR.

**GUT (`viewer-massif/tests/`, mission C) :**
- Passage Lambert-93 → Godot (T6) sur quatre points asymétriques, aller et retour exact à 1 mm.
- Lecture d'un bloc : clé manquante, `schema_version` inconnu, année absente : erreur lisible, aucune
  valeur par défaut.
- Choix des blocs autour d'une position (rayon, bord de la zone).
- Tirage déterministe : mêmes positions à deux appels ; l'effectif des semis d'une cellule a pour
  espérance `seedlings_ha × 0,0625` (somme sur beaucoup de cellules, tolérance écrite) ; l'herbe d'une
  cellule à `herb_cover = 0` est vide ; le plafond tronque et le dit.
- Niveau de détail choisi selon la distance (seuils du bloc `viewer`).
- Le bandeau contient « provisoire » dès que `provisoire` est vrai, et « semis non simulés » en
  `ifn_direct`.

**Importation, export, exécution (sans GPU) :**
- `godot --headless --path viewer-massif --import` : code 0, aucune ligne `ERROR` dans le journal.
- GUT : `godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit` : code 0, aucun test sauté.
- **Export** (T9, T10) : `godot --headless --export-release "Linux"` ; le fichier existe, il n'est pas
  vide, le binaire exporté lancé avec `--selftest` et la zone fictive sort à 0 et écrit ses comptes.
  Fenêtre Windows : selon Q5. Si les modèles ne sont pas disponibles un jour, le job échoue (il ne saute
  pas l'export en silence).
- **Job `m6`** : Godot et GUT figés (T10), modèles d'export en cache (clé : version), `m6` de
  `run_tests.sh`, délai de 20 min à confirmer par la première exécution (téléchargement de 1,26 Go
  inclus), noté au journal s'il monte. Le glTF-Validator de Khronos y passe sur les `.glb` et sur les
  tuiles.

## 7. Questions pour Pascal (une par une, dans cet ordre)

**Q1. Comment le générateur de tarif-nemeton (dépôt privé) entre-t-il dans sylvigenese (GPL-3, public) ?**
- *Contexte.*
  - `tarif-nemeton` est privé, sans fichier de licence (« licence à définir avant toute ouverture »).
    Au journal git, 8 commits de vous et 2 de l'assistant.
  - Copier `synth_*.py` dans `sylvigenese` revient à **publier** ce code, et ses tables de calage,
    sous GPL-3, avec son histoire : cela ne se défait pas, et c'est réservé à vous (hors délégation).
  - Les bornes de dimensions viennent de jeux de QSM d'autres auteurs (BioDiv, Wytham, Demol) dont les
    licences de redistribution sont à lire (mission A) ; plusieurs attributions architecturales sont
    « à confirmer ».
  - BRIEF §9 : « adapter le générateur » ; BRIEF §0 : « aucun module n'importe le code d'un autre ».
  - Précédent : `import_tarif` lit des CSV de `tarif-nemeton` par `external.tarif_nemeton_dir`, sans
    copier de code.
- *Options :*
  - **(a) Par fichiers.** Un petit script ajouté à `tarif-nemeton` (mission E, PR chez vous) écrit les
    segments des exemplaires ; `assets` les lit par `external.tarif_nemeton_dir`. Aucun code copié.
  - **(b) Copie du code** dans `python/sylvigenese/`, sous GPL-3, après votre décision de licence.
  - **(c) Sous-processus** : `assets` lance `synth_arbres.py --cylindres` de l'autre dépôt (aucune
    modification là-bas).
- *Proposition :* (a).
  - Le principe « par fichiers » est tenu, rien ne devient public sans vous, et le précédent existe.
  - Le prix : la CI du dépôt public n'a pas le générateur. Elle prouve le maillage, le `.glb` et les
    deux vues sur une **fixture synthétique** (segments inventés, quelques centaines), pas sur les vrais
    arbres. Les vrais exemplaires se produisent chez vous ou dans la session ; leurs `.glb` restent hors
    dépôt (`data/<zone>/assets/trees/`) tant que vous n'avez pas dit qu'ils peuvent être versionnés.
- *Si (a) :* M6a est jugé en CI sur la fixture, et par l'`analyste` sur les vrais exemplaires, une fois.
  Mission E est nécessaire.
- *Si (b) :* la CI juge le vrai générateur, mais il faut votre décision de licence et la lecture des
  données de calage d'abord ; le code est dupliqué (deux copies à tenir).
- *Si (c) :* aucune mission E, mais il faut réparer le piège du dossier courant et des valeurs par
  défaut de `Rh` et `hbh` (les valeurs calées sont ailleurs) ; le comportement du générateur est
  pris tel quel, sans tests de notre côté.

**Q2. Les arbres ont-ils des feuilles ?**
- *Contexte.* Le générateur ne produit que le bois (tige, réitérations, branches jusqu'aux rameaux,
  rayon de rameau terminal de l'essence). Il a un indicateur `persistant` par essence. Aucune source
  ne donne forme ni couleur de feuillage.
- *Options :*
  - (a) bois seul : l'arbre est « d'hiver », fidèle au générateur, sans valeur inventée ;
  - (b) bois et feuillage en cartes (petits plans à plat) aux extrémités des rameaux, couleur unie par
    groupe et par persistance, marquée `provisoire` et dite « illustration » ;
  - (c) bois et houppier en volume ombré sans détail.
- *Proposition :* (b) pour `LOD0`, `LOD1` et `LOD2`, avec une seule couleur par couple (feuillu ou résineux ;
  caduc ou persistant), et la mention à l'écran. Les feuilles ne portent aucun chiffre écologique.
- *Si (a) :* une vue d'hiver partout, lisible mais pauvre : à 100 000 instances, `LOD2` ressemblerait à
  une brosse.
- *Si (b) :* des valeurs d'affichage de plus (taille des cartes, densité, couleurs), dans le bloc
  `viewer` de `config.yml`, `provisoire: true`.

**Q3. Une essence qui n'a pas de modèle du générateur : que dessine-t-on ?**
- *Contexte.* Onze essences ont un générateur ; hors jeu fictif (09, 61, 62), beaucoup d'essences réelles
  n'en ont pas (par exemple 10, 13G, 22M). Les rapprocher d'une autre est refusé depuis M5a (« pas
  d'emprunt ») ; ne rien dessiner cacherait des arbres de la simulation.
- *Options :*
  - (a) un modèle générique par groupe (feuillu, résineux), **marqué** sur l'écran et dans
    `massif/index.json` (« modèle générique ») ;
  - (b) ne rien dessiner, compter et signaler ;
  - (c) emprunter l'essence voisine du même genre, dit au rapport.
- *Proposition :* (a). Aucun arbre n'est inventé ni caché ; c'est la voie déjà suivie en M4.
- *Si (b) :* des trous visibles dans la vue pour les essences rares.
- *Si (c) :* une forme d'une autre essence sous le nom de celle-ci, contre la règle de M5a.

**Q4. Herbe et semis : quelles valeurs d'affichage acceptez-vous de poser « à titre d'illustration » ?**
- *Contexte.*
  - Rien dans le dépôt ne dit la hauteur d'une herbe, sa couleur, ni la forme d'un semis. Les biomes
    donnent seulement un couvert (synthétique sur le jeu fictif) et des noms d'herbacées fictifs.
  - Le générateur commence à D = 8 cm : pas de semis de moins de 7,5 cm.
  - Les semis du moteur (`seedlings_ha`, `h_mean_m`) viennent de M5a (valeurs synthétiques sur le jeu
    fictif).
- *Options :*
  - (a) herbe : brins à hauteur et couleur uniques, nombre selon le couvert ; semis : modèle `young`
    de l'essence mis à l'échelle de la hauteur du semis ; les constantes (hauteur du brin, couleur,
    densité de brins à couvert 1) dans `config.yml`, `provisoire: true`, avec « illustration, non
    mesurée » à l'écran ;
  - (b) herbe en simple texture de sol teintée selon le couvert, sans brin ni hauteur ; semis : tige
    et petit houppier simples ;
  - (c) pas de strate herbacée avant d'avoir des sources.
- *Proposition :* (a). BRIEF §10 demande la strate herbacée et les semis, et (a) la fait sans nommer
  aucune herbe ni mesurer rien de plus que ce que `sim/` et les biomes disent.
- *Si (b) :* aucune hauteur à se justifier, mais la strate est plate à l'œil.
- *Si (c) :* BRIEF §10 n'est pas rempli sur ce point : écart à inscrire.

**Q5. Le PC de Pascal : quel système, et que doit-on exporter ?**
- *Contexte.* L'export est faisable (T10), mais il faut savoir pour quelle machine. La vue sans GPU
  ne dit rien du rendu. M6b, c'est votre PC : images par seconde, aspect des 44 modèles, sensation de
  marche, lien depuis votre navigateur.
- *Options :* (a) Windows ; (b) Linux ; (c) macOS ; (d) plusieurs. Windows et Linux s'exportent depuis
  la CI ; macOS demande une notarisation que nous ne ferons pas.
- *Proposition :* Linux seul si c'est votre système ; sinon Windows en plus. Le choix ajoute un préréglage
  d'export, et un test `--selftest` n'est possible en CI que pour Linux.
- *Si Windows :* l'export est testé jusqu'au fichier produit, pas exécuté : la preuve d'exécution est M6b.
- *Si macOS :* M6b se fera depuis l'éditeur Godot, sans export.

## 8. Risques

- **Le générateur ne fabrique pas des arbres affichables.** Des segments, jusqu'à 45 000 par arbre, sans
  feuillage. Le maillage, les trois niveaux de détail et le feuillage sont à **écrire** ; la qualité du
  rendu se juge à l'œil, donc en M6b. Ce que la CI prouve : forme du fichier, budget, repère, identité.
- **Les bornes du générateur sont des hypothèses.** Son en-tête le dit (« à corriger après lecture des
  planches »), et plusieurs attributions sont « à confirmer ». Les arbres affichés sont donc
  **synthétiques et provisoires** : `extras` et bandeau le disent, et BRIEF §9 aussi (« ils ne valident
  aucun tarif »).
- **Licence et publication** : voir Q1. Rien n'est copié avant votre réponse. Tout fichier dérivé
  du générateur et versionné est une publication : par défaut hors dépôt.
- **Piège du dossier courant** (générateur) : une exécution depuis un autre dossier rend des résineux
  différents sans erreur. E doit échouer au lieu de passer ; en (c), il faut le corriger chez vous.
- **Tests de M4.** Quatre tests épinglent « feuillu et résineux » : ils sont réécrits par C, c'est
  voulu. Les décomptes (14 080 instances, positions) doivent rester identiques : s'ils bougent, D a un
  défaut.
- **Contradiction de sources** : « un fichier par niveau de détail » (spec §9) contre un fichier avec
  niveaux (BRIEF §4, catalogue) ; « lecture de `sim/` » (BRIEF §10) contre `massif/` seul (spec §2).
  Tranchées en T2 et au §4, à confirmer par l'ADR 0007.
- **Terrain à 25 m** : lissé. Les pieds d'arbres sont posés comme le fait `altitude.py` (bilinéaire entre
  centres) sur un terrain triangulé : un écart de quelques décimètres entre le tronc et le sol est
  possible sur forte pente. À relever par H sur la fixture, et à regarder en M6b.
- **Taille des blocs JSON** : estimée sur le jeu fictif seulement. Un massif réel de plusieurs
  centaines de milliers d'arbres rouvrira T5 (format binaire, blocs plus petits).
- **Jeu fictif trop dense, trajectoires non validées** : la vue le dit dans le bandeau, avec `cohorts` et
  `ifn_direct` ; semis et herbe de la vue suivent des valeurs synthétiques.
- **Version de Godot** : 4.6.3 aujourd'hui ; 4.7 et 4.7.1 sont sorties, GUT a une branche par version.
  Le passage est une décision, pas une mise à jour silencieuse.
- **iTowns et `.glb`** : le chargement d'un contenu `.glb` par `OGC3DTilesLayer` reste « à éprouver »
  (`itowns-instancing.md`). M6a ne le promet pas : tuiles en `.gltf` (T1).
- **Durée de la CI** : le job `m6` télécharge 1,26 Go de modèles d'export ; sans cache, il pèse sur les
  20 minutes. Le plus long job actuel dure environ 12 min. Un dépassement se dit au journal.
- **Disque du conteneur** : 5,7 Go libres. Godot (72 Mo) tient ; les modèles d'export non.
- **Hors de ce plan, et à inscrire au kanban :**
  - le lien web → massif sur une zone réelle et le rendu à l'œil (M6b) ;
  - `assets` ne sait toujours pas lire le niveau SER (refus code 2 depuis M5a) : la vue massif ne montre
    donc que le niveau massif ;
  - l'obtention d'une licence pour `tarif-nemeton` si Pascal ouvre ce dépôt ;
  - les modèles d'herbe et de sous-bois sourcés (aucun aujourd'hui) ;
  - la remontée de la vue à l'écran des signalements de `sim/flags.parquet` (aujourd'hui seulement
    les mentions du bloc).

## 9. Ce qui relève de M6b (PC de Pascal, critère b)

- Lancer `viewer-massif` depuis la fiche d'une cellule, sur la machine et le système de Pascal.
- Images par seconde et fluidité avec le nombre d'arbres, d'herbes et de semis du massif test réel (le
  BRIEF ne fixe pas de seuil pour la vue massif : à fixer avec lui).
- L'aspect des 44 modèles (11 essences × 4 stades) et du feuillage, planche par planche, face aux
  planches PDF du générateur.
- Le sol à 25 m, la marche, la caméra ; l'exécution de l'export Windows ou macOS s'il y en a un.
- Le massif test réel (données hors dépôt), et la décision sur les `.glb` versionnables.
- **Échantillon terrain que Pascal vérifie** : 4 arbres (nord, sud, est, ouest du bloc fictif) à leurs
  coordonnées Lambert-93 : ouvrir la vue en (x, y), vérifier que l'arbre le plus au nord est devant lui
  et le plus à l'est à sa droite ; un hêtre, un sapin et un épicéa aux quatre stades, comparés à la
  fiche web de la même cellule (essence, hauteur) ; une cellule dont le couvert herbacé est nul (aucune
  herbe) et une dont il est élevé (herbe) ; une cellule à semis (mode `cohorts`).
