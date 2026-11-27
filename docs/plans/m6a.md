# Plan de M6a : les arbres du générateur dans les deux vues, et la vue massif sous Godot (26/11/2026)

> Plan rendu par un `dev` (temps « prendre »), **à valider** par l'orchestrateur. **Amendé le 26/11/2026**
> après les réponses de Pascal (Q1 à Q8, **toutes tranchées le 26/11/2026**, journal), la critique du
> contradicteur (B1 à B3, R1 à R4, M1 à M5) et l'examen de `godot-forest-demo`. Les choix T1 à T14 sont ceux
> que le `dev` propose de trancher lui-même, avec leur raison. Pascal peut défaire chacun d'eux.
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
vues, sous forme de modèles `.glb` à trois niveaux de détail et quatre stades par essence, lus **par fichiers**
(la vue iTowns et une vue massif Godot neuve), puis de bâtir cette vue massif (terrain, arbres, strate
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
6. Le lien web → massif qui dit la zone (Q7).
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
  reporté en M6b au titre de la clause de la spec. Il se fait en CI, pas dans ce conteneur. Q5 étant tranchée (Linux seul), la CI **n'extrait du `.tpz`
  que le gabarit `linux_release`** (T10, R4) : le `.tpz` de 1,26 Go se télécharge, le reste n'est pas gardé.
- **Conséquence 2 : GUT ne s'obtient pas ici.** Un agent du conteneur ne pourrait ni lancer GUT ni le
  mettre à jour. D'où T10 (GUT 9.6.1 versionné dans le dépôt, licence jointe).
- Le dépôt n'a pas d'accès GitHub pour cette session : je n'ai pas lu les notes de version. Les
  versions 4.6.4 et suivantes de la série 4.6 peuvent sortir ; la CI fige 4.6.3.

## 3. Découpage proposé (8 missions, numéros à donner par l'orchestrateur)

| # | Agent | Mission en une phrase (quoi, pourquoi) | Peut | Ne doit pas | Tests |
|---|---|---|---|---|---|
| A | `acquereur` | **Référentiel du générateur et des outils** : formats de sortie, dépendances, auteurs (git), licences des jeux de données qui ont calé `bornes_dimensions.csv` (QSM BioDiv, Wytham, Demol, etc.), état des attributions architecturales « à confirmer » ; licences et empreintes de Godot 4.6.3, des modèles d'export et de GUT 9.6.1 ; ce que `godot-forest-demo` impose à reprendre (CC BY 4.0). Fournit à E et à Pascal les licences des jeux de calage ; **lit aussi la licence du glTF-Validator de Khronos** (M5 de la critique : « Apache-2.0 » n'est pas lu). | `docs/referentiels/generateur-arbres.{md,csv}`, `docs/referentiels/godot-gut.md` | copier du code ou une table de tarif-nemeton ; écrire une licence « présumée » | chaque ligne porte fichier et ligne ou `absent` ; empreintes recalculées sur le fichier téléchargé |
| B | `dev` | **Contrats de M6a et projet d'ADR 0007 (arbres du générateur et vue massif)**, avant tout code, comme 033 et 060. Contenu : `massif_block` v2 (§4) ; `massif/index.json` ; règle de nom des `.glb` et de leurs extras ; validateur de `.glb` renforcé ; seuils des stades sortis de `R/biomes.R` vers un fichier unique lu par R et par Python (T11) ; accord de la spec §9 (« un fichier par niveau de détail ») avec le BRIEF §4 (T2) ; **contrat des exemplaires** (Parquet, repère z-up, voir §4) ; **fichier de paramètres des dimensions de référence** (selon Q6). | `contracts/` (schémas, `catalog.yml`, `README.md`, `validator/`, `tests/`), `config.yml`, `docs/adr/0007-arbres-generateur-vue-massif.md` (« proposée »), `docs/spec.md` (§2, §9, §10 : mise en accord seulement), `biomes/` (fichier des seuils de stade) | toucher `python/`, `R/`, `simulate/`, `viewer-*` ; affaiblir un contrat ; mettre une valeur écologique dans un schéma | un cas conforme et un cas fautif par règle nouvelle ; un `.glb` tronqué, sans nœud LOD2, ou sans `extras.source_commit`, refusé ; `make validate` vert |
| C | `testeur` | **Tests d'acceptation de M6a**, écrits sans lire le code de D et de F : côté Python (`tests/m6/`, avec un analyseur de `.glb` indépendant) et côté Godot (`viewer-massif/tests/`, GUT). Le testeur reprend aussi les tests de `tests/m4` qui épinglent les modèles génériques (voir risque « tests de M4 »). Il fournit la fixture d'exemplaires (§5, mission D). | `tests/m6/`, `viewer-massif/tests/`, `tests/m4/` (les seuls tests dépendant du modèle générique), `tests/fixtures/` (exemplaires synthétiques) | lire `python/sylvigenese/assets_lib` modifié par D ni les scripts de F ; sauter un test ; écrire une valeur présentée comme écologique | voir §6 ; rouge attendu jusqu'à D, E et F |
| D | `dev` (Python) | **Du segment au `.glb`, aux tuiles et au bloc massif** : lecture des exemplaires (Parquet), conversion z-up → y-up (T6), maillage, trois niveaux de détail, quatre stades, `.glb` identique à l'octet près à chaque exécution ; tuiles iTowns bâties des mêmes sommets ; `massif/index.json` et `massif/<année>/<bloc>.json` v2 lus dans `sim/` (ou `trees_init/`) ; fonction unique du stade d'un arbre ; **script documenté `tools/rejouer_exemplaires_reels` qui rejoue la construction des `.glb` sur l'export réel** (B2). | `python/sylvigenese/assets.py`, `python/sylvigenese/assets_lib/` (nouveaux `exemplars.py`, `lod.py`, `glb.py`, `stages.py`, `massif.py` ; `models.py`, `tiles.py`, `sim_state.py`, `initial_state.py`), `python/tests/`, `tools/rejouer_exemplaires_reels*` | importer du code de tarif-nemeton ; deviner un modèle pour une essence sans exemplaire ; casser l'identité à l'octet près ; changer `tiles/` des années ou le décompte des instances (14 080) | tests unitaires (§6) ; `tests/m4` rouvert par C vert ; `contracts/validate` vert sur `assets/trees/*.glb` et `massif/` |
| E | `dev` (dépôt tarif-nemeton) | **Export des exemplaires (Q1 tranchée : par fichiers).** Mission **à part**, **validée par Pascal** avant lancement ; sa PR se fait **sur `tarif-nemeton`**, fusionnée par Pascal. Un script court qui, pour chaque essence et chaque stade demandés, écrit les segments en **Parquet** (essence, D, H, hbh, Rh, b_cible, graine, commit en métadonnées, repère z-up dit), en fixant le dossier courant et en **échouant** si `bornes_dimensions.csv` est introuvable. Les dimensions viennent de Q6. | `tarif-nemeton/code/synth_export_exemplaires.py` (nouveau), `tarif-nemeton/resultats/synth_arbres/exemplaires/` | modifier `synth_arbres.py`, `synth_essences.py`, `synth_calage.py` ou les bornes ; changer un modèle tiré ; copier du code dans `sylvigenese` | mêmes segments, à l'octet près, que `synth_arbres.py --cylindres` pour un cas ; refus si bornes absentes ; la fixture de `sylvigenese` a le même schéma Parquet |
| F | `afficheur` | **La vue massif Godot** (`viewer-massif/`) : arguments `--zone --x --y --year`, lecture de `massif/`, repère (T6), terrain, **chargement des `.glb` à l'exécution** (T13), arbres en blocs MultiMesh (un par bloc, modèle et niveau, `visibility_range`), strate herbacée et semis autour de la caméra (T8), **global uniforms déclarés dans `project.godot`**, rendu Compatibility en repli (T14), bandeau de mentions « provisoire », sortie de contrôle `--selftest`. | `viewer-massif/` (scènes, scripts, `export_presets.cfg`, `CREDITS.md`, `addons/gut/` versionné, `README.md`), `docs/referentiels/godot-forest-demo.md` (attribution seulement) | lire `sim/` ou du Parquet ; ouvrir une valeur écologique dans un script ; **copier de `godot-forest-demo` autre chose que le shader d'herbe MIT (SimpleGrassTextured, IcterusGames, commit 623212f : avis de copyright gardé, `CREDITS.md`)** ; copier une texture d'herbe dont l'origine n'est pas établie (T8) ; mesurer des images par seconde (M6b) | GUT de C verts ; `--headless --import` sans erreur ; `--selftest` à 0 |
| G | `dev` | **CI, export et lien web** : job `m6` (Godot 4.6.3 et GUT figés, empreintes vérifiées, import, GUT, export **Linux seul** (Q5), exécution de `--selftest` sur le binaire exporté ; **extraction du seul gabarit `linux_release`** du `.tpz`) ; section `m6` de `run_tests.sh` ; la commande de la fiche dit la zone (T7) ; versions dans le README. | `.github/workflows/ci.yml` (job `m6`), `tools/ci/run_tests.sh`, `tools/viewer-massif*` (lanceur), `viewer-web/src/sheet.ts` et ses tests, `README.md` | élargir le réseau de l'exécuteur au-delà de github.com ; relever un délai sans le dire au journal ; changer `tests/m4` hors de la ligne de commande | job `m6` **mesuré à froid** (cache purgé après 7 jours) et à chaud, délai relevé au journal ; la commande de la fiche est celle que le viewer accepte (test croisé), forme selon Q7 |
| H | `analyste` | **Mesures sans GPU, jeu de contrôle réel et note M6b** : **rapport du jeu de contrôle hors dépôt** (arbres réels traités ; B2) ; tailles des `.glb`, sommets et triangles par niveau de détail ; temps de génération ; nombre d'instances d'herbe et de semis par cellule du jeu fictif ; temps de chargement d'un bloc en mode sans rendu ; rédaction de `LANCER_CHEZ_SOI.md` (section M6) pour le PC de Pascal. | `bench/results/M6.md`, `bench/results/m6_*.csv`, `bench/results/LANCER_CHEZ_SOI.md` (section M6), `bench/results/m6_controle_reel.md` | modifier le code ; présenter un compte de triangles comme des images par seconde | chaque chiffre renvoie à une ligne de CSV ; rejouable par un seul script |

**Mission C, ce qu'elle couvre** (le détail est au §6).

**Ordre des vagues :**
1. Q1 à Q8 sont **tranchées** (journal du 26/11/2026) : **Q6** (change B, D, E), **Q7** (change G et M6b),
   **Q8** (change B, D et l'ADR 0007).
2. Vague 1 : A (courte).
3. Vague 2 : B. L'orchestrateur tranche l'ADR 0007 par délégation, sauf T-licence (voir Q1).
4. Vague 3 : C et D ; **E** (dépôt `tarif-nemeton`) part à part, **après validation de Pascal** ; D ne
   dépend que de la fixture jusque-là. D et F n'écrivent pas dans les mêmes dossiers, mais F
   lit le contrat de B et les fichiers de la fixture : F peut partir en parallèle de D dès que C
   a livré ses tests.
5. Vague 4 : F, puis G (G touche `ci.yml` et `run_tests.sh`, qui servent aussi aux autres : après F).
6. Vague 5 : H, puis la relecture. Le plafond humain est de 3 PR ouvertes : M6a tient en une PR
   (`sylvigenese`), plus une PR de `tarif-nemeton` pour E ; **le jeu de contrôle réel (H) attend la fusion de
   cette dernière** ; sans lui, le critère a n'est pas rempli (§6).

## 4. Contrats à ajouter ou à modifier (mission B)

- **Qui lit quoi.** `viewer-massif` ne lit que **`massif/` et `assets/trees/`** (spec §2 et ADR 0003).
  Le BRIEF §10 parle de « lecture de `sim/` » : je l'entends comme « les résultats de `sim/`, par
  `assets` ». Raisons : Godot ne lit pas Parquet ; un seul module (`assets`) lit `sim/` ; la vue ne
  dépend pas de la forme de `sim/` (aujourd'hui deux formes, `ifn_direct` et `cohorts`). Écart à
  inscrire à la spec §2.
- **Exemplaires (nouveau contrat `assets.exemplars`, B).** Un fichier **Parquet** (et non CSV : jusqu'à
  45 000 segments par arbre, 44 arbres) : segments `x0 y0 z0 x1 y1 z1 r0_m r1_m niveau axe`, **repère du
  générateur z-up dit dans les métadonnées** (T6), plus essence, stade, `D_cm`, `H_m`, `hbh_m`, `Rh_m`,
  `b_cible`, `graine`, commit. La fixture synthétique de la CI a le même schéma.
- **`assets/trees/<espar>_<stade>.glb`** (contrat `assets.tree_model`, règle de nom `species_stage`
  déjà au catalogue ; `<stade>` ∈ `young|pole|mature|old`) : trois niveaux de détail par l'extension **`MSFT_lod`** et `extras.MSFT_screencoverage` (T2), et non des nœuds
  de convention maison ; **aucune extension `KHR_mesh_quantization` n'est promise** (M3 : sommets en float32 ;
  à rouvrir si H mesure des `.glb` trop lourds) ;
  `extras` : `species`, `stage`, `source` (commit de tarif-nemeton), `essence_generateur`, `D_cm`,
  `H_m`, `hbh_m`, `Rh_m`, `graine`, `H_ref_m`, `rayon_houppier_ref_m`, `provisoire: true`,
  `synthetique: true` (« arbre synthétique ; ne valide aucun tarif », BRIEF §9), `feuillage`
  (Q2 : cartes, couleur unie par essence). Le validateur lit les accesseurs, les bornes et l'extension `MSFT_lod`.
- **Alias d'essences (M2).** `species.csv` compte 13 codes espar pour 11 essences du générateur : les
  `.glb` sont nommés par **code espar**, mais **deux codes de la même essence ne donnent pas deux modèles** :
  un alias (colonne du contrat ou table de B) renvoie vers le même fichier ; le nom du modèle utilisé reste
  dans `massif/index.json`. Pas de doublon, pas d'emprunt entre essences différentes (Q3).
- **Modèle générique, repli signalé** (Q3 tranchée) : `assets/trees/generique_<groupe>.glb`,
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
- **`config.yml`**, deux familles à ne pas confondre (B1) :
  - **dimensions de référence des exemplaires** (D, H, hbh, Rh, b_cible par essence et par stade) : valeurs
    **dendrométriques**, **pas des réglages d'affichage**. Leur source est l'objet de **Q6** (quantiles de
    `sim/trees` ; `b_cible` et houppier depuis `synth_calage.py` ; à défaut, fichier de paramètres sourcé,
    `provisoire: true`) ;
  - **réglages d'affichage** : bloc `assets.models` (budgets de triangles par niveau, `exemplars_dir` ou
    `external.tarif_nemeton_dir`) et bloc `viewer` (rayon d'herbe, plafond d'instances, distances de bascule,
    constantes d'herbe et de feuillage), `provisoire: true`, « illustration, non mesurée », aucune lue par le
    moteur (Q2, Q4).
- **Stades** : fichier unique des seuils (aujourd'hui `BIOMES_STAGE_BREAKS` en dur dans `R/biomes.R`),
  lu par `biomes` (R) et par `assets` (Python) (T11). La mission B écrit le fichier et le schéma ; le
  `dev` de R adapte `R/biomes.R` dans une reprise séparée, sans changer un résultat. Le stade d'un
  **arbre** (T11) étend la définition du BRIEF §6 : Q8.
- **ADR 0007** : T1, T2, T5, T6, T7, T11, T13 et T14, avec le crible FRANCE. L'entrée du générateur par
  fichiers (Q1) y est inscrite comme décision de Pascal ; T11 attend Q8, T7 attend Q7, les dimensions Q6.

## 5. Choix techniques (le `dev` propose de trancher, avec sa raison)

- **T1. Un seul constructeur de maillage, deux sorties.** `assets` construit chaque modèle une fois à
  partir des segments, écrit le `.glb` (Godot) et reprend **les mêmes sommets** dans le contenu `.gltf`
  des tuiles (iTowns).
  - Raison : deux chemins diraient deux arbres différents dans les deux vues. Un test compare les
    octets des sommets.
  - Les tuiles restent en `.gltf` + `.bin` : le gestionnaire de `OGC3DTilesLayer` n'est enregistré que
    pour `/\.gltf$/` (`itowns-instancing.md`, point A) et un contenu `.glb` serait à éprouver. Les `.glb`
    sont les modèles du dossier `assets/trees/`, lus par Godot.
- **T2. Un fichier `.glb` par (essence, stade), trois niveaux de détail par `MSFT_lod`** (B3 : nœud
  principal = LOD0, `MSFT_lod.ids` vers les deux nœuds plus grossiers, `extras.MSFT_screencoverage` pour les
  seuils). Godot n'applique pas `MSFT_lod` seul : c'est notre chargeur (T13) qui lit l'extension et pose les
  `visibility_range`. Les validateurs contrôlent que l'extension est déclarée.
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
  (absents). Le validateur du projet est renforcé ; **le glTF-Validator de Khronos** (paquet npm, licence
  **à lire par A, non supposée**) est ajouté au job `m6` : la spec §9 le renvoie à « M4 » et il n'a pas
  été fait.
- **T5. Disposition de `massif/`** : `massif/index.json` et `massif/<année>/<bloc>.json`, bloc = tuile
  de 500 m de `tiles/` (mêmes identifiants `t_<x>_<y>`). Le catalogue dit `massif/*.json` : il passe à
  `massif/index.json` et `massif/*/*.json`. JSON et non binaire : un bloc de 500 m du jeu fictif porte
  de 3 000 à 4 000 arbres (14 080 sur 4 blocs), de l'ordre de 0,5 Mo ; le contrat existe déjà ; GDScript
  sait lire du JSON. Si un massif réel donne des blocs de plusieurs dizaines de Mo, le format se
  rouvre (risque).
- **T6. Repères** (R2). Trois repères, dits dans les contrats : le **générateur est z-up** (`UP = (0, 0, 1)`
  dans `synth_arbres.py`) ; **glTF est y-up**. La conversion z-up → y-up est faite **une fois, dans
  `assets`** : (x, y, z) → (x, z, −y). **Test (pytest, indépendant)** : l'étendue de `LOD0` en **+Y** égale
  `H_ref_m` à 1 % et la base est en y = 0 ; un segment connu de l'exemplaire se retrouve au point converti
  attendu (cas asymétrique, x ≠ y). **Repère de Godot** : x = est, y = haut (altitude NGF moins celle de l'origine du bloc), **z = −nord**
  (le nord est devant, comme `−Z` de Godot, et le repère reste direct). Les positions restent relatives
  à l'origine du bloc (float32 sûr : quelques km donnent moins de 0,3 mm).
  - Piège connu du projet (x et y inversés, « la Somalie ») : un test GUT pose quatre arbres aux
    extrémités nord, sud, est, ouest, avec des coordonnées asymétriques, et un test pytest relit
    l'altitude de leur pied.
  - Le terrain est la **MNT de la grille (25 m)**. Ce n'est pas le LiDAR à 1 m : le sol sera lisse et
    le pied d'arbre posé à moins de 0,5 m près de ce sol, par construction. Dit à l'écran (risque).
- **T7. Lancement et lien web.** La vue se lance par `godot --path viewer-massif -- --zone <dossier>
  --x <X> --y <Y> --year <A>`, enveloppée dans `tools/viewer-massif` (script). Le lien depuis la fiche
  web est **la question Q7** (commande à copier, ou gestionnaire d'URL `x-scheme-handler` installé sur le PC
  de Pascal en M6b). Dans les deux cas la vue accepte ce même jeu d'arguments : il dit **où sont les
  données**, pas seulement la place (un lien `https` ne lance pas un programme). Une année qui n'est pas dans `massif/index.json`, un point hors
  de toute emprise ou une zone sans `massif/` : le code de sortie est non nul et le message donne les
  années ou l'emprise. Jamais l'année voisine.
  - Le test pinne ce changement dans `viewer-web` (`sheet.ts`) selon Q7 ; `tests/m4` en dépend, d'où G après F.
- **T8. Herbe et semis autour de la caméra** (BRIEF §10 ; Q4 tranchée ; examen de `godot-forest-demo`) :
  - **Copié : le seul shader d'herbe MIT** (SimpleGrassTextured, IcterusGames, commit source `623212f`),
    **avis de copyright gardé en tête de fichier**, une ligne dans `CREDITS.md`. Rien d'autre de la démo
    (son dépôt est en CC BY 4.0 : aucun code de ce dépôt n'est recopié). **Avant copie, A ou F vérifie
    l'origine de `grassbushcc008.png`** et des autres textures d'herbe ; sans origine ni licence lisibles,
    la texture n'entre pas (herbe sans texture ou texture que nous fabriquons).
  - **Réécrit d'après l'idée :** un MultiMesh d'herbe **recentré autour de la caméra** quand elle a bougé de
    plus de `d` mètres, **calculé dans un fil**, avec un **identifiant de requête** (un résultat périmé est
    jeté), un **plafond d'instances signalé** à l'écran quand il tronque, et le **hachage de cellule**.
  - **Densité tirée du couvert de la cellule :** nombre de brins proportionnel à `herb_cover` du bloc
    (biome), jamais à la composition ni à une répartition aléatoire par biome. Tirage par **hachage
    déterministe** de (zone, `cell_id`, essence ou strate, rang) : mêmes plantes à chaque passage.
  - **Global uniforms** du shader **déclarés dans `project.godot`** ; un test GUT vérifie leur présence
    (sinon le shader échoue au chargement sans bruit).
  - **Semis :** par cellule et par essence, `round(seedlings_ha × 0,0625 ha)` avec arrondi aléatoire à
    espérance exacte (idée de M3a), à la hauteur `h_mean_m`, sans autre source que `sim/cells`.
    **Forme (M4) : le modèle `young` de l'essence réduit à l'échelle de la hauteur du semis.** Conséquence
    **visible**, à dire à Pascal (Q4) : un semis est un **jeune arbre en miniature**, pas une plantule ; le
    générateur commence à D = 8 cm, le plus petit `young` a déjà un houppier ramifié. L'aspect se juge en M6b.
  - **Constantes d'apparence** (hauteur de brin, couleur, densité à couvert 1, taille des cartes de
    feuillage) : bloc `viewer` de `config.yml`, `provisoire: true`, « illustration, non mesurée », signalées
    dans la vue.
  - Sans cohortes (`ifn_direct`) : aucun semis dessiné, la mention « semis non simulés » est à l'écran.
- **T9. Pas de rendu dans les tests.** Trois étages, aucun ne demande de carte graphique : pytest
  (maillage, `.glb`, contrats) ; GUT en `--headless` (logique, arbre de scène, rendu factice de Godot) ;
  `--headless --import`, export, puis exécution du binaire exporté avec `--selftest`, qui charge la
  zone fictive, bâtit la scène, écrit des comptes (arbres, instances d'herbe, semis, blocs) et sort à 0.
  Aucune image par seconde, aucun pixel : c'est M6b.
- **T10. Versions figées** : Godot **4.6.3-stable** (dernière 4.6.x, MIT), GUT **9.6.1** (MIT), avec les
  empreintes SHA-512 de la release vérifiées dans le job. **Export Linux seul (Q5)** : le job télécharge le
  `.tpz` (1,26 Go), **n'extrait que le gabarit `linux_release`** (et `version.txt`) vers le dossier des
  modèles de la version, et ne met en cache que cela (R4 : cache limité, purgé après 7 jours sans accès). La
  durée **à froid** est mesurée au premier passage et inscrite au journal. `GODOT_VERSION` de `ci.yml` (aujourd'hui
  `4.6-stable`) passe à `4.6.3-stable`. GUT est **versionné** dans `viewer-massif/addons/gut/` avec son
  `LICENSE.md` (le conteneur ne peut pas le télécharger, un agent ne pourrait donc pas lancer les
  tests) ; la source est dite dans `CREDITS.md`. Passer à 4.7.x demande GUT 9.7.1 : décision à part.
- **T11. Stade d'un arbre** (affichage ; **dépend de Q8**) : h / h_pot de sa cellule, par les **mêmes seuils provisoires**
  que les biomes (0,25, 0,60, 0,90), lus dans le fichier unique que crée B. Attention (M1) : le BRIEF §6 définit le stade du **peuplement** (H0 / h_pot de la cellule), pas celui d'un
  **arbre** ; appliquer les mêmes seuils à un arbre étend la définition (Q8). Raison : le contrat de
  l'énumération `stage` dit « position de la hauteur observée sur la courbe de hauteur » et un seul
  jeu de seuils garde le stade d'un arbre et celui de son biome cohérents ; deux copies de la valeur
  dériveraient. Les dimensions de référence (D, H, hbh, Rh, b_cible) du modèle de chaque stade viennent de **Q6**, pas d'un
  réglage d'affichage ;
  l'instance est mise à l'échelle de h et de la largeur de houppier `cw` de `sim/trees` (échelle
  non uniforme comme en M4, dite : la tige s'épaissit avec le houppier).
- **T12. Pas d'exemplaire, pas de modèle propre.** Q3 tranchée : une essence sans exemplaire est dessinée par
  le **modèle générique feuillu ou résineux**, jamais par une essence voisine (règle de M5a) ; elle est
  comptée dans `massif/index.json`, signalée à l'écran et à la fiche, son arbre reste compté. Les alias de
  code (M2, §4) ne sont pas des emprunts : même essence. Pour les exemplaires : le même (essence, stade, graine) redonne le même `.glb`
  à l'octet près, sur la même machine ; l'identité entre machines (numpy, flottants) n'est pas promise
  (même réserve que rustfft au kanban).

- **T13. Chargement des `.glb` à l'exécution (B3).** Les `.glb` sont dans `data/<zone>/assets/trees/`,
  **hors `res://`** : l'importeur ne les voit pas. La vue les charge par `GLTFDocument.append_from_file`
  puis `generate_scene` ; `MSFT_lod` n'étant pas appliquée par Godot, notre chargeur la lit dans le JSON du
  `GLTFState` et pose les niveaux. Rendu : **un `MultiMeshInstance3D` par (bloc, modèle, niveau de
  détail)**, avec `visibility_range_begin/end` (et marge de fondu) tirés du bloc `viewer`, et non un nœud de
  bascule maison par arbre. **Test GUT de chargement à l'exécution** d'un `.glb` de la fixture. L'export
  n'embarque aucun modèle.
- **T14. Rendu de repli (R1).** Godot 4.6 démarre en Forward+ (Vulkan) par défaut ; si le Vulkan du PC de
  Pascal ou de l'exécuteur manque, rien ne s'affiche. **M6a règle le rendu Compatibility (OpenGL) en repli**
  (`--rendering-method gl_compatibility` documenté dans le lanceur, `project.godot` sans verrou) ; **la
  preuve** que la vue y tient (images, shader d'herbe) est **M6b**. Le shader copié est relu pour ce mode.

## 6. Tests sans GPU et job de CI

**Python (`tests/m6`, mission C, sans lire D) :**
- **Analyseur de `.glb` indépendant** (entête, bloc JSON, bloc binaire, accesseurs, bornes).
- Pour chaque couple (essence, stade) de la fixture : `MSFT_lod` avec trois niveaux ; triangles strictement
  décroissants et sous les budgets de `config.yml` ; **l'étendue de LOD0 en +Y fait `H_ref_m` à 1 %** (R2) ;
  aucun sommet non fini ; extras `source`, `synthetique`, `provisoire` présents ; nom
  `<espar>_<stade>` conforme au catalogue et à `species.csv`.
- **Identité** : deux exécutions, mêmes octets ; un exemplaire modifié d'un segment, octets différents.
- **Les mêmes sommets dans les deux vues** : les sommets du modèle de la tuile égalent ceux du
  `LOD2` du `.glb`.
- **Alias** (M2) : deux codes espar de la même essence donnent le même `.glb` ; deux essences différentes
  n'en partagent jamais.
- **Repère** : un arbre de `trees_init` aux coordonnées connues (Lambert-93, EPSG:2154) se retrouve
  dans `massif/<année>/<bloc>.json` à sa place, avec quatre arbres aux extrémités (cas asymétrique) et
  l'altitude de son pied égale à celle de `altitude.py` ; le bloc dit `crs` et `vertical_datum`.
- **Cohérence entre fichiers** : somme des arbres des blocs = instances de `tiles/index.json` ; avec
  `cohorts`, `seedlings[]` égaux à `sim/cells` ; avec `ifn_direct`, `seedlings_simulated: false`.
- **Refus et replis** : essence sans exemplaire (modèle **générique** signalé et compté, jamais emprunté ; Q3) ; exemplaire
  corrompu ; `bornes_dimensions.csv` absent côté export (E) ; année demandée absente de l'index.
- **Non-régression de M4** : 14 080 instances, mêmes positions au dixième de mètre, mêmes années.
  Les tests qui épinglent « feuillu et résineux » (`test_m4_tuile.py:121`, `test_m4_instances.py:114`,
  `test_m4_variantes.py:72`, `test_m4t_instances.py:103`) sont **réécrits par le testeur** pour dire
  « un modèle par (essence, stade) » : c'est un changement voulu, dit dans la PR.

**Jeu de contrôle hors dépôt (B2).** La CI ne voit que la fixture synthétique (Q1) : elle prouve le
maillage, le `.glb`, le repère et les deux vues, **pas** que les vrais exemplaires passent. D'où :
- **Qui lance quoi.** Une fois la PR de E fusionnée par Pascal, **Pascal (ou l'orchestrateur ici, s'il a les
  données) lance l'export réel** dans `tarif-nemeton` ; ni la CI ni un agent sans accès.
- **Un script documenté** (`tools/rejouer_exemplaires_reels`, mission D) **rejoue la construction des `.glb`**
  sur cet export : mêmes commandes qu'en CI, chemin en argument, aucune donnée copiée dans le dépôt.
- **Un rapport** (`bench/results/m6_controle_reel.md`, mission H) **compte les arbres réels traités** :
  exemplaires lus par essence et stade, `.glb` produits et validés, triangles par niveau, arbres du massif
  test par modèle propre, par alias ou générique, refus. Chaque chiffre renvoie à une ligne de CSV.
- **Ce que devient le critère a** : rempli **en deux temps** : (1) **en CI**, sur la fixture, le chemin complet
  (segments → `.glb` → tuiles et vue) ; (2) **au jeu de contrôle**, le même chemin sur les **vrais
  exemplaires**, une fois, avec le rapport. **Sans (2), le critère a n'est pas rempli** : M6a est dit
  « rempli sur la fixture, contrôle réel en attente de E ». Prix de tenir : M6a ne se clôt qu'après la PR de
  `tarif-nemeton` et le passage de Pascal ; prix de plier : un critère vidé, des arbres réels jamais
  éprouvés.

**GUT (`viewer-massif/tests/`, mission C) :**
- Passage Lambert-93 → Godot (T6) sur quatre points asymétriques, aller et retour exact à 1 mm.
- **Chargement à l'exécution** d'un `.glb` de la fixture (T13) : trois niveaux, étendue de LOD0 = `H_ref_m`,
  `visibility_range` posés d'après `MSFT_lod`.
- **Global uniforms** du shader d'herbe présents dans `project.godot` ; résultat de fil d'une requête
  périmée jeté (identifiant de requête).
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
- **Rendu de repli** (T14) : `--selftest` sort à 0 avec `--rendering-method gl_compatibility`.
- `godot --headless --path viewer-massif --import` : code 0, aucune ligne `ERROR` dans le journal.
- GUT : `godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit` : code 0, aucun test sauté.
- **Export** (T9, T10) : `godot --headless --export-release "Linux"` ; le fichier existe, il n'est pas
  vide, le binaire exporté lancé avec `--selftest` et la zone fictive sort à 0 et écrit ses comptes.
  **Linux seul (Q5).** Si les modèles ne sont pas disponibles un jour, le job échoue (il ne saute
  pas l'export en silence).
- **Job `m6`** : Godot et GUT figés (T10), **gabarit `linux_release` seul** en cache (clé : version ; purgé après 7 jours,
  le cas **à froid** compte), `m6` de `run_tests.sh`, délai **mesuré à froid et à chaud** à la première
  exécution (1,26 Go téléchargés), noté au journal ; les 20 min ne sont qu'une hypothèse. Le glTF-Validator de Khronos y passe sur les `.glb` et sur les
  tuiles.

## 7. Questions pour Pascal

**Tranchées par Pascal le 26/11/2026 (journal) :** Q1 à Q8 (Q6 à Q8 après l'amendement du plan ; la réponse
est rappelée en tête de chaque question).

**Q1. Entrée du générateur — tranchée par Pascal le 26/11/2026 : par fichiers.** Un script d'export des
segments est ajouté à `tarif-nemeton` par une PR que Pascal fusionne (mission E) ; `assets` lit ce fichier et
construit les `.glb` ; aucun code du générateur dans `sylvigenese` ; la CI publique juge sur une fixture
synthétique, les vrais arbres restent hors dépôt. *Conséquence (critique B2) :* jeu de contrôle réel hors
dépôt, critère a rempli en deux temps (§6).

**Q2. Feuillage — tranchée par Pascal le 26/11/2026 :** cartes simples en bout de branche, **couleur unie par
essence**, provisoires et signalées dans les vues (illustration, aucune densité ni indice foliaire inventé).

**Q3. Essence sans modèle — tranchée par Pascal le 26/11/2026 :** modèle générique feuillu ou résineux,
signalé dans la fiche et compté au rapport ; aucun emprunt à une essence voisine ; décomptes d'arbres
inchangés.

**Q4. Herbe et semis — tranchée par Pascal le 26/11/2026 :** dessinés autour de la caméra ; **nombre tiré des
sorties** (couvert, comptes de semis) ; **apparence en constantes d'affichage** dans `config.yml`,
« illustration, non mesurée », `provisoire: true`, signalées dans la vue, aucune lue par le moteur.
*Conséquence à lui dire (M4) :* un semis est le modèle `young` réduit (T8), un jeune arbre en miniature.

**Q5. Système — tranchée par Pascal le 26/11/2026 :** Linux (i7-4940MX, 31 Go) ; export Linux seul, testé en
CI jusqu'à l'autotest ; M6b sur son PC avec le même exécutable. *Risque ajouté (R1) :* Vulkan, voir T14.

**Q6. D'où viennent les dimensions de référence des exemplaires (D, H, hbh, Rh, b_cible, par essence et par
stade) ? — tranchée par Pascal le 26/11/2026 : option (a), repli sur (b).** D et H en quantiles de `sim/trees` par
essence et par stade ; hauteur et rayon du houppier et densité des rameaux depuis la calibration de `tarif-nemeton`
(`synth_calage.py`) ; repli sur un fichier de paramètres sourcé, `provisoire: true`, pour une essence trop peu
présente ; chaque arbre mis à l'échelle de sa hauteur simulée. *(Texte de la question gardé ci-dessous.)*
- *Contexte.* Pour produire un arbre par (essence, stade), il faut dire sa taille. Ce **ne sont pas des
  réglages d'affichage** (Q4 ne les couvre pas) : ce sont des valeurs dendrométriques ; si elles sont
  fausses, les 44 modèles le sont, et leurs `extras` diraient « 28 m » d'un arbre qui n'a pas cette taille.
  Le générateur donne des défauts (`hbh = 0,45 H`, `Rh = 0,12 D + 0,8`, `b_cible` absent) qui ne sont pas les
  valeurs calées (`synth_calage.py` ajuste `H(D)`, la part de houppier et l'étendue du houppier par essence
  dans `bornes_dimensions.csv`) ; les bornes d'architecture sont, selon leur en-tête, des hypothèses.
- *Options :*
  - **(a) Les données.** D et H = **quantiles de `sim/trees` par essence et par stade** ; `hbh`, `Rh` et
    `b_cible` depuis la **calibration de `tarif-nemeton`** (`synth_calage.py`, `bornes_dimensions.csv`), lue
    par le script d'export (E) ;
  - **(b) Un fichier de paramètres** `provisoire: true`, une source par ligne, écrit par B ;
  - **(c) Des valeurs posées à la main** comme constantes d'affichage (la lecture que ce plan écarte).
- *Proposition :* **(a)**, repli sur **(b)** pour toute essence que `sim/trees` ne peuple pas assez (elle est
  alors signalée). Aucune valeur écologique posée par nous ; chaque modèle a la taille des arbres montrés.
- *Si (a) :* les exemplaires dépendent d'une exécution de `sim/` ; E reçoit D et H en entrée ; le jeu de
  contrôle réel passe par une simulation ; la fixture porte ses quantiles de démonstration.
- *Si (b) :* un fichier de plus à sourcer ; exemplaires indépendants de la simulation ; l'échelle à
  l'instance (T11) déforme davantage les modèles.
- *Si (c) :* un chiffre de forêt sans source, contre « ne rien inventer d'écologique » : déconseillé.

**Q7. Comment le lien de la fiche web ouvre-t-il la vue massif ? — tranchée par Pascal le 26/11/2026 : option (a) en
M6a.** La fiche affiche la commande complète à copier (zone, x, y, année), testée en CI ; un vrai lien `sylvigenese://`
reste possible en M6b, installé avec lui sur son PC. *(Texte de la question gardé ci-dessous.)*
- *Contexte.* La fiche porte une commande (`viewer-massif -- --x … --y … --year …`) qui ne dit pas où est la
  zone ; un lien `https` ne lance pas un programme.
- *Options :* **(a)** commande complète à copier (`--zone`, `--x`, `--y`, `--year`) ; **(b)** gestionnaire
  d'URL `x-scheme-handler` (par ex. `sylvigenese://massif?zone=…&x=…&y=…&year=…`) installé sur votre PC par un
  fichier `.desktop` en M6b.
- *Proposition :* **(a) en M6a** (testé en CI : la commande de la fiche est celle que la vue accepte),
  **(b) en M6b** si (a) vous gêne ; (b) modifie votre machine et se fait avec vous.
- *Si (a) seul :* un copier-coller par visite, rien à installer.
- *Si (b) :* un clic, mais une installation chez vous, un fichier à maintenir, un lien qui ne marche que là.

**Q8. Le stade d'un arbre se calcule-t-il comme celui d'un peuplement ? — tranchée par Pascal le 26/11/2026 :
option (a).** Stade de chaque arbre = h / h_pot de l'arbre avec les seuils des biomes (le sous-étage se voit) ;
extension du BRIEF §6 écrite dans l'ADR 0007. *(Texte de la question gardé ci-dessous.)*
- *Contexte.* BRIEF §6 : le stade (`young`, `pole`, `mature`, `old`) est celui du **peuplement**, par
  H0 / h_pot de la cellule (seuils provisoires 0,25 / 0,60 / 0,90). Le plan l'applique à **chaque arbre**
  (h / h_pot) pour choisir son modèle : extension, non lecture du BRIEF. Un arbre de 10 m dans un peuplement
  mature serait « jeune ».
- *Options :* **(a)** h / h_pot de l'arbre, mêmes seuils, fichier unique (T11) ; **(b)** le stade de la
  **cellule** pour tous ses arbres (BRIEF §6 tel quel) ; **(c)** autre critère (par ex. D / D_max), à définir.
- *Proposition :* **(a)**, inscrite à l'ADR 0007 comme extension de BRIEF §6 et dite à l'écran (« stade de
  l'arbre »).
- *Si (b) :* tous les arbres d'une cellule ont la même silhouette, le sous-étage disparaît.
- *Si (c) :* une règle de plus, à sourcer.

## 8. Risques

- **Le générateur ne fabrique pas des arbres affichables.** Des segments, jusqu'à 45 000 par arbre, sans
  feuillage. Le maillage, les trois niveaux de détail et le feuillage sont à **écrire** ; la qualité du
  rendu se juge à l'œil, donc en M6b. Ce que la CI prouve : forme du fichier, budget, repère, identité.
- **Les bornes du générateur sont des hypothèses.** Son en-tête le dit (« à corriger après lecture des
  planches »), et plusieurs attributions sont « à confirmer ». Les arbres affichés sont donc
  **synthétiques et provisoires** : `extras` et bandeau le disent, et BRIEF §9 aussi (« ils ne valident
  aucun tarif »).
- **Licence et publication** : Q1 tranchée (par fichiers). Aucun code du générateur dans `sylvigenese` ;
  tout fichier dérivé (exemplaires, `.glb` réels) reste hors dépôt tant que Pascal n'a pas dit qu'il peut
  être versionné.
- **Critère a vidé par la voie par fichiers** (B2) : traité par le jeu de contrôle réel (§6). Reste : E est
  dans un autre dépôt, validée et fusionnée par Pascal ; si elle traîne, M6a reste « rempli sur la fixture ».
- **Vulkan** (R1) : T14 ; la preuve du repli Compatibility est M6b.
- **Textures d'herbe** : origine de `grassbushcc008.png` non établie ; vérifiée avant copie (T8).
- **Tailles et durées** (R4) : `.tpz` de 1,26 Go (gabarit Linux seul extrait), cache purgé après 7 jours, job
  `m6` mesuré à froid ; exemplaires en Parquet.
- **Dimensions de référence** (B1) : Q6.
- **Extension de BRIEF §6** : stade d'un arbre et non d'un peuplement (Q8).
- **Piège du dossier courant** (générateur) : une exécution depuis un autre dossier rend des résineux
  différents sans erreur. E doit échouer au lieu de passer.
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
  (`itowns-instancing.md`). M6a ne le promet pas : tuiles en `.gltf` (T1) ; les niveaux `MSFT_lod` sont lus par notre chargeur Godot, non par iTowns (tuiles : LOD2).
- **Durée de la CI** : le job `m6` télécharge 1,26 Go de modèles d'export ; à froid, il pèse sur les
  20 minutes (T10). Le plus long job actuel dure environ 12 min. Un dépassement se dit au journal.
- **Disque du conteneur** : 5,7 Go libres. Godot (72 Mo) tient ; le `.tpz` entier (1,26 Go) tient à peine et reste en CI.
- **Hors de ce plan, et à inscrire au kanban :**
  - le lien web → massif sur une zone réelle et le rendu à l'œil (M6b) ;
  - `assets` ne sait toujours pas lire le niveau SER (refus code 2 depuis M5a) : la vue massif ne montre
    donc que le niveau massif ;
  - l'obtention d'une licence pour `tarif-nemeton` si Pascal ouvre ce dépôt ;
  - les modèles d'herbe et de sous-bois sourcés (aucun aujourd'hui) ;
  - la remontée de la vue à l'écran des signalements de `sim/flags.parquet` (aujourd'hui seulement
    les mentions du bloc).

## 9. Ce qui relève de M6b (PC de Pascal, critère b)

- Lancer `viewer-massif` depuis la fiche d'une cellule (Q7), sur le PC Linux de Pascal ; **preuve du rendu
  Compatibility** (T14) si Vulkan manque.
- Images par seconde et fluidité avec le nombre d'arbres, d'herbes et de semis du massif test réel (le
  BRIEF ne fixe pas de seuil pour la vue massif : à fixer avec lui).
- L'aspect des semis (modèle `young` réduit) et de l'herbe (shader copié).
- Le jeu de contrôle réel (§6) : lancer l'export, lire le rapport.
- L'aspect des 44 modèles (11 essences × 4 stades) et du feuillage, planche par planche, face aux
  planches PDF du générateur.
- Le sol à 25 m, la marche, la caméra ; l'exécution de l'export Linux.
- Le massif test réel (données hors dépôt), et la décision sur les `.glb` versionnables.
- **Échantillon terrain que Pascal vérifie** : 4 arbres (nord, sud, est, ouest du bloc fictif) à leurs
  coordonnées Lambert-93 : ouvrir la vue en (x, y), vérifier que l'arbre le plus au nord est devant lui
  et le plus à l'est à sa droite ; un hêtre, un sapin et un épicéa aux quatre stades, comparés à la
  fiche web de la même cellule (essence, hauteur) ; une cellule dont le couvert herbacé est nul (aucune
  herbe) et une dont il est élevé (herbe) ; une cellule à semis (mode `cohorts`).
