# ADR 0007 — les arbres du générateur entrent par fichiers, en `.glb` à trois niveaux de détail, et la vue massif ne lit que `massif/` et `assets/trees/`

- **Date :** 2026-11-26
- **Statut :** acceptée le 27/11/2026 par l'orchestrateur, par délégation de Pascal, après deux relectures de la PR n° 12 ; le point « Licence » a été tranché par Pascal (Q1 du 26/11/2026 : vrais exemplaires et .glb réels hors dépôt) ; Pascal peut la défaire
- **Proposée par :** `dev` de la mission 068 (plan `docs/plans/m6a.md` §3 ligne B, §4 et §5, choix T1, T2, T5, T6, T7, T11, T13, T14 ; réponses de Pascal Q1 à Q8 du 26/11/2026)
- **Tranchée par :** — (en attente)
- **Mise à jour du 26/11/2026** (mission 075, d'après le journal du 26/11/2026 : décisions de Pascal, choix
  tranchés par délégation par l'orchestrateur, relecture de la PR n° 12) : choix 1, 4, 5, 7, 11, 12, 13 et
  « Conséquences » précisés ; le sens des décisions de Pascal (Q1 à Q8, résineux non calés) n'est pas changé.
- **Mise à jour du 27/11/2026** (seconde relecture de la PR n° 12, mineurs ; journal du 27/11/2026) : choix 4, 7 et
  10 complétés (`stage_models`, modèle par essence et stade, convention du modèle générique, refus des clés de
  dimension absentes, arbre de cw nul) ; rien de ce qui précède n'est effacé ni son sens changé.

## La décision en une phrase

Les arbres du générateur de tarif-nemeton entrent dans sylvigenese **par fichiers** (exemplaires
Parquet, repère z-up dit) ; `assets` en fait **un `.glb` par (essence, stade)** à **trois niveaux de
détail** (`MSFT_lod`), converti une fois en y-up, et écrit `massif/index.json` et
`massif/<année>/<bloc>.json` (version 2) ; `viewer-massif` **ne lit que `massif/` et `assets/trees/`** ;
le stade d'**un arbre** est h / h_pot de l'arbre avec les seuils des biomes, lus dans **un fichier
unique** ; une essence sans modèle est dessinée par un **modèle générique signalé**, jamais
empruntée. Les formats sont fixés par les contrats de la mission 068 (`contracts/catalog.yml`).

## Contexte

- Le générateur (`tarif-nemeton`, dépôt privé sans licence) rend des **segments** (troncs de cône), pas
  un maillage ; jusqu'à 45 000 segments par arbre ; z-up ; onze essences. Le BRIEF §4 prévoit un fichier
  `<species>_<stage>.glb` avec ses niveaux de détail ; la spec §9 disait « un fichier par niveau de
  détail » : deux sources se contredisaient.
- Le BRIEF §10 parle de « lecture de `sim/` » par la vue massif ; la spec §2 et l'ADR 0003 donnent
  `massif/` et `assets/trees/`. Godot ne lit pas Parquet, et `sim/` a deux formes (`ifn_direct`,
  `cohorts`).
- Décisions de Pascal du 26/11/2026 : **Q1** par fichiers (script d'export ajouté à `tarif-nemeton` par
  une PR qu'il fusionne ; aucun code du générateur dans sylvigenese) ; **Q2** feuillage en cartes, couleur
  unie, provisoire ; **Q3** essence sans modèle = générique signalé, sans emprunt ; **Q4** herbe et semis
  autour de la caméra, apparence en constantes d'affichage `provisoire: true` ; **Q6** dimensions de
  référence des exemplaires depuis `sim/trees` (D, H) et la calibration de tarif-nemeton (houppier,
  rameaux), repli sur un fichier de paramètres sourcé ; **Q7** commande complète à copier ; **Q8** stade
  de chaque arbre = h / h_pot de l'arbre avec les seuils des biomes.

## Choix

1. **Entrée du générateur par fichiers (Q1).** Contrat `assets.exemplars` : un fichier Parquet par
   (essence, stade), `<essence>_<stade>.parquet`, une ligne par segment (`x0 y0 z0 x1 y1 z1 r0_m r1_m
   niveau axe`), métadonnées Parquet `frame = z-up`, `units = m`, `essence`, `stage`, `D_cm`, `H_m`,
   `hbh_m`, `Rh_m`, `b_cible`, `seed`, `source_commit`, `synthetic = true`. La CI publique juge sur une
   fixture synthétique de même schéma ; **les vrais exemplaires restent hors dépôt** (Q1 de Pascal, journal du
   26/11/2026). Le contrat porte aussi **`calage`** (`calé` | `non calé`, **obligatoire** pour un modèle du
   générateur, lu dans l'export et recopié, **absent = refus**, code 2, rien n'en est déduit) et
   **`calage_raisons`** (facultatif) ; **`b_cible` n'est facultatif que si `calage` = `non calé`** (journal du
   26/11/2026, 071 et 070). Les **résineux** du générateur (pin, épicéa, douglas, mélèze, sapin) sont générés aux
   4 stades mais **non calés** pour la densité des rameaux et, pour jeune et perche, extrapolés (calage sans
   petits arbres) : décision de Pascal du 26/11/2026, dite dans les extras du modèle et à l'écran. Le critère « arbres du
   générateur dans les deux vues » est rempli **en deux temps** (fixture en CI, puis jeu de contrôle réel,
   plan §6) : tant que le second manque, il est dit « rempli sur la fixture ».
2. **Un seul constructeur de maillage, deux sorties (T1).** `assets` bâtit chaque modèle une fois et
   écrit le `.glb` (Godot) ; les tuiles iTowns, en `.gltf` + `.bin` (le gestionnaire d'`OGC3DTilesLayer`
   n'est enregistré que pour `.gltf`), reprennent les mêmes sommets du niveau LOD2.
3. **Un `.glb` par (essence, stade), trois niveaux par `MSFT_lod` (T2).** Nœud principal = LOD0,
   `MSFT_lod.ids` vers LOD1 et LOD2, `extras.MSFT_screencoverage` pour les seuils d'écran. Godot
   n'applique pas `MSFT_lod` (absent de `gltf_document.cpp` en 4.6.3) : le chargeur de la vue (T13) **lit
   l'extension à la main** et pose les `visibility_range`. **Le dernier niveau n'a pas de fin** : la distance
   de coupure est rendue à part, **non appliquée** (journal du 26/11/2026, 072). **La spec §9 est accordée au BRIEF** : un fichier par (essence, stade), pas un fichier
   par niveau. Autre voie (`<species>_<stage>_lod<n>.glb`) écartée, non interdite.
4. **Nom, alias, générique.** Les `.glb` sont nommés par **code espar** ; **deux codes de la même
   essence** (même `tarif_nemeton_code` dans `species.csv` : 02 et 03, 12P et 12V) **ne donnent pas deux
   fichiers** : le fichier porte le premier code, l'autre est un alias ; `massif/index.json` dit, par code,
   le modèle utilisé (`own`, `alias`, `generic`). Une essence sans exemplaire est dessinée par
   `generique_feuillu.glb` ou `generique_resineux.glb` (`extras.generique`), signalée, comptée
   (`trees_by_kind`), jamais empruntée à une essence voisine (Q3). **Le modèle est dit par essence et par
   stade** : une essence peut avoir un modèle propre à certains stades et le **repli générique** à d'autres
   (relecture de la PR n° 12, journal du 26/11/2026) ; la mission 075 (partie A) l'écrit dans
   `massif/index.json`, **le détail est fixé par le contrat** (`contracts/`), pas ici. *Ajout du 27/11/2026 :* c'est fait, la clé **`stage_models`** de
   `massif/index.json` (contrat `massif_index` 0.2) dit, par couple (essence, stade), le fichier de modèle et sa
   sorte (`own`, `alias`, `generic`) ; la vue la lit telle quelle, un couple absent est un arrêt nommé (code 5).
   Le validateur de `.glb` refuse un code
   alias, un code sans modèle propre, et un `extras` qui ne redit pas le nom.
5. **Extras des `.glb`.** `species`, `stage`, **`source_commit`** (commit de `tarif-nemeton`),
   `essence_generateur`, `D_cm`, `H_m`, `hbh_m`, `Rh_m`, `b_cible`, `graine`, `H_ref_m`,
   `rayon_houppier_ref_m`, `provisoire` et `synthetique` vrais (« arbre synthétique ; ne valide aucun tarif »,
   BRIEF §9), `feuillage` (cartes, couleur unie, Q2), **`calage`** et `calage_raisons` (choix 1). **Le modèle générique
   n'a pas de `calage`** et n'a pas à porter les extras dimensionnels (journal du 26/11/2026, 068). Pas d'`KHR_mesh_quantization` : sommets float32.
6. **Repères (T6).** Le générateur est **z-up**, glTF est **y-up** : la conversion (x, y, z) →
   (x, z, −y) est faite **une fois, dans `assets`**. Le validateur contrôle que le LOD0 va de y = 0 à
   y = `H_ref_m` à 1 %. Dans `massif/` : x est, y nord, z haut, positions relatives à l'origine du bloc
   (EPSG:2154, NGF-IGN69). **Repère de Godot** : x est, y haut, z = −nord (conversion par la vue). Le
   terrain est le MNT de la grille à 25 m, pas le LiDAR : le sol est lisse, dit à l'écran.
7. **Disposition de `massif/` (T5).** `massif/index.json` (années, blocs, emprises, **modèle par essence et
   stade** (`stage_models`, ajout du 27/11/2026 ; `models` garde le modèle par essence), comptes) et `massif/<année>/<bloc>.json`, bloc = tuile de 500 m de `tiles/` (`t_<x>_<y>`). Version 2
   du bloc : arbres, `ground` (altitudes aux nœuds de 25 m), `cells[]` (biome, `herb_cover`,
   `shrub_cover`, `seedlings[]` si et seulement si `cohorts`), `mentions[]`, `provisoire`. **`hcb` peut être nul** (absent de `trees_init`) : jamais 0, la **mention est
   obligatoire** et comptée par bloc (journal du 26/11/2026, 070). L'herbe et les semis sont dessinés sous un
   **plafond d'instances, signalé à l'écran** (herbe : 200 000 ; semis : `viewer.seedlings.max_instances`, 20 000,
   provisoire) ; le bloc garde les comptes entiers (journal du 26/11/2026, 072). Pas de
   composition herbacée (noms fictifs, aucun modèle d'herbe). JSON : un bloc fictif pèse environ 0,5 Mo ; à
   rouvrir si un massif réel donne des blocs de plusieurs dizaines de Mo.
8. **La vue ne lit que `massif/` et `assets/trees/`.** Le « lecture de `sim/` » du BRIEF §10 s'entend
   « les résultats de `sim/`, par `assets` ». Écart à inscrire à la spec §2 (fait par la mission 068).
9. **Stade d'un arbre (T11, Q8).** h / h_pot **de l'arbre**, avec les seuils 0,25 / 0,60 / 0,90, lus
   dans **`biomes/stades/stage_breaks.yml`** (contrat `biomes.stage_breaks`, provisoire, sans source
   citée), lu par `biomes` (R) et `assets` (Python) : une seule copie des valeurs. **C'est une extension
   de BRIEF §6**, qui définit le stade du **peuplement** (H0 / h_pot de la cellule) : un arbre de 10 m dans
   un peuplement mature est « pole ». Pascal l'a voulu (le sous-étage se voit) ; il peut la défaire (le
   stade de la cellule pour tous ses arbres, option b de Q8). La vue dit « stade de l'arbre ». Le fichier
   est dans un sous-dossier parce que R lit tout `biomes/*.yml` comme un catalogue ; `R/biomes.R` garde
   `BIOMES_STAGE_BREAKS` jusqu'à sa reprise (mission « D/R »), sans changer un résultat.
10. **Dimensions de référence (Q6).** Les dimensions d'un exemplaire (D, H, hbh, Rh, b_cible) sont des
    valeurs **dendrométriques**, pas des réglages d'affichage : D et H = quantiles de `sim/trees` par
    essence et stade ; hbh, Rh, b_cible = calibration de `tarif-nemeton` (`synth_calage.py`,
    `bornes_dimensions.csv`) ; repli = `params/model_dimensions.csv` (contrat écrit, **fichier de valeurs
    non écrit** : à sourcer), `provisoire`, une source par ligne. Chaque arbre est mis à l'échelle de sa
    hauteur simulée (et de sa largeur de houppier, échelle non uniforme, dite).
    *Ajout du 27/11/2026 (seconde relecture de la PR n° 12 ; choix accepté par délégation) :*
    - **Modèle générique** : 1 m × 1 m, mis à l'échelle (r, h, r) avec r = cw / 2, **dans les deux vues**
      (Godot et iTowns) ; la hauteur ne remplace jamais le rayon.
    - **Modèle du générateur** : une clé de dimension absente (`H_ref_m`, `rayon_houppier_ref_m`) ou un rayon
      nul ou non positif est **refusé et nommé** ; aucune valeur de repli, la hauteur n'est pas substituée.
    - **Arbre de cw nul** : non dessiné, **compté** (`cw_zero_trees`) et **dit à l'écran** (choix accepté par
      délégation le 27/11/2026).
11. **Réglages d'affichage (Q2, Q4).** Blocs `assets.models` (budgets de triangles, `MSFT_screencoverage`,
    `exemplars_dir`) et `viewer` (herbe, feuillage, fondu) de `config.yml`, `provisoire: true`,
    « illustration, non mesurée », jamais lus par le moteur. **`config.yml` est cherché sans valeur de repli** : introuvable, la vue sort avec le
    **code 3** (le lanceur et le job `m6` partent de la racine du dépôt ; journal du 26/11/2026, 072). Le nombre de brins d'herbe suit `herb_cover`,
    celui des semis suit `sim/cells` : seule l'apparence est en constantes.
12. **Lancement (T7, Q7).** `tools/viewer-massif -- --zone <dossier> --x <X> --y <Y> --year <A>`,
    **lancé depuis la racine du dépôt** (lanceur qui appelle Godot ; choix par délégation du 26/11/2026, relecture
    de la PR n° 12) ; la fiche web affiche **la commande complète à copier** (testée en CI) ; un lien
    `sylvigenese://` reste possible en M6b, installé avec Pascal. Une année absente de
    `massif/index.json`, un point hors de toute emprise ou une zone sans `massif/` : code de sortie non nul,
    le message donne les années ou l'emprise, **jamais l'année voisine**.
13. **Chargement des `.glb` à l'exécution (T13).** Les `.glb` sont dans `data/<zone>/assets/trees/`,
    hors `res://` : la vue les charge par `GLTFDocument.append_from_file` et `generate_scene`, lit
    `MSFT_lod` dans le JSON et pose les niveaux ; des `MultiMeshInstance3D` **par case de 25 m** (case, modèle, niveau), **et non un par bloc** : le niveau de
    détail se décide par case (journal du 26/11/2026, 072).
14. **Rendu de repli (T14).** Godot démarre en Forward+ (Vulkan) ; M6a règle le rendu Compatibility
    (OpenGL) en repli, `project.godot` sans verrou ; la preuve du rendu est M6b.

## Le crible FRANCE

| Lettre | Réponse | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|
| **F**rugale | Un seul constructeur de maillage, deux sorties ; une copie des seuils de stade ; pas de doublon de `.glb` pour un alias | Un fichier de plus à lire pour R (reprise à part) ; un fichier d'index à écrire | oui |
| **R**esponsable | Le critère « arbres du générateur » n'est dit rempli qu'en deux temps ; l'extension de BRIEF §6 est écrite, avec sa sortie de secours | M6a ne se clôt qu'après la PR de `tarif-nemeton` et le passage de Pascal | oui (Pascal a choisi) |
| **A**nticiper | Aucun code ni donnée du générateur dans le dépôt tant que la licence n'est pas dite ; contrats avant le code ; formats ouverts (glTF, Parquet, JSON) | Un chemin par fichiers, plus long qu'un import | oui |
| **N**ovateur | `MSFT_lod` et chargement à l'exécution plutôt qu'un nœud de bascule maison | Chargeur à écrire, `MSFT_lod` non appliqué par Godot | oui |
| **C**oût | Pas de valeur inventée : dimensions sourcées ou signalées, repli générique ; constantes d'affichage marquées | Des arbres génériques tant que `model_dimensions.csv` n'est pas sourcé | oui |
| **É**cologique | Aucune valeur écologique dans un schéma ; `provisoire` et « synthétique » dans les fichiers et à l'écran | Bandeau et mentions à tenir | oui |

## Valeurs sacrifiées

**Le rythme** : un export par fichiers, une PR sur un autre dépôt et un jeu de contrôle réel coûtent plus
qu'un import direct du générateur. **La fidélité de forme** : le feuillage en cartes à couleur unie et le sol
à 25 m sont des illustrations ; leur aspect se juge en M6b.

## Licence

Le générateur de `tarif-nemeton` n'a pas de licence (« à définir avant toute ouverture »). Les exemplaires
et les `.glb` réels en sont dérivés : **ils restent hors dépôt** tant que Pascal n'a pas dit qu'ils peuvent
être versionnés. Seule la fixture synthétique, écrite par nous, est versionnée. Cette décision revient à
Pascal (extérieur, ne se défait pas).

*Ajout du 26/11/2026 (mission 075) :* le journal du même jour note que ce point est **déjà tranché par Pascal
(Q1 : exemplaires et `.glb` réels hors dépôt)**. Seule une décision de les versionner resterait à lui.

## Conséquences

- **Ce que le validateur ne contrôle pas** : voir `contracts/README.md`, « Ce que les contrats de la
  mission 068 ne contrôlent pas » (sommes entre fichiers, altitudes, égalité avec `sim/`, **glTF-Validator de
  Khronos, ajouté au job `m6`** par la mission 075 (partie B), sur les `.glb` du jeu fictif ; il ne juge pas les
  extras ni `MSFT_lod` hors de ce que lit le validateur de `contracts/`).
- **Rétrocompatibilité.** `massif_block` v1 reste conforme à l'identique ; son chemin au catalogue passe de
  `massif/*.json` à `massif/*/*.json`. Les `config.yml` sans `assets.models` ni `viewer` restent conformes.
- **Tests de M4.** Quatre tests épinglent « feuillu et résineux » : ils sont réécrits (mission C) pour
  « un modèle par (essence, stade) », changement voulu ; les 14 080 instances et leurs positions ne bougent pas.
- **Reprise de R** (hors de cette mission) : `R/biomes.R` lira `biomes/stades/stage_breaks.yml` dans une
  reprise séparée ; en attendant, un test compare les deux jeux de valeurs.
- **Vrais exemplaires et `.glb` réels** : hors dépôt (Q1 de Pascal) ; le critère « arbres du générateur » reste
  « rempli sur la fixture » tant que la PR `pobsteta/tarif-nemeton#7` n'est pas fusionnée par Pascal. La
  « Licence » ci-dessus est donc déjà tranchée par Q1 pour le versionnement des réels.
- **Hors de M6a** (kanban) : lien web sur zone réelle et rendu à l'œil (M6b), niveau SER non lu par `assets`
  (refus code 2), modèles d'herbe et de sous-bois sourcés, remontée à l'écran des signalements de
  `sim/flags.parquet`.

## Sources

- `docs/plans/m6a.md` §3 à §8 ; journal du 26/11/2026 (Q1 à Q8, résineux non calés, `godot-forest-demo`, choix par délégation de 068, 070, 072
  et 073, relecture de la PR n° 12, mission 075) ;
- `docs/BRIEF.md` §4, §6, §9, §10 ; `docs/spec.md` §2, §9, §10 ; ADR 0002, 0003, 0006 ;
- extension glTF `MSFT_lod` (Khronos, glTF 2.0) ; `contracts/README.md`.

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
