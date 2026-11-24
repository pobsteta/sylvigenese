# godot-forest-demo : étude pour la base de `viewer-massif` (mission 007)

## En-tête

- **Source étudiée :** `GamesNotDeveloped/godot-forest-demo`, clone en lecture seule dans `/tmp/claude-0/gfd`, commit `623212ffeb4efbf4c95323a4a6a57e726be4f6e9` (journal git : un seul enregistrement, « clone », dépôt peu profond ; le dépôt amont affiche « 2 Commits » et 34 étoiles). Godot **4.6**, Forward Plus, moteur physique Jolt (`project.godot` lignes 39 et 60).
- **Date de consultation :** 24/11/2026.
- **Propriétaire :** Pascal.
- **Donnée externe non fiable :** lue seulement, rien exécuté, aucun code ni ressource copié dans le dépôt.
- **Mission redite :** étudier le projet pour dire, sources à l'appui, ce que `viewer-massif` (BRIEF §10, jalon M6) peut en reprendre, en adapter ou seulement en apprendre, et sous quelles licences. Décision éclairée : la base de `viewer-massif`.
- **Écarts entre sources relevés :**
  - Licence d'UniPlayer : absente du clone, « BSD-3-Clause » sur la page GitHub amont (fichier non lu).
  - README : « MIT » pour l'herbe. Les 16 shaders portent « Copyright (c) 2023 IcterusGames » et un avis MIT, les textures n'ont aucune licence dans le clone.
  - `plugin.cfg` de `gnd_biomes` : `author="OpenAI"`, alors que le README parle d'une « initial implementation ». Le fichier `.codex` à la racine est vide.
  - Le fil du forum n'a pas pu être lu (voir plus bas).
- **Inventaire des licences : 11 fichiers** (`LICENSE`, `addons/debug_menu/LICENSE.md` et 9 `license.txt`), tous lus. Détail dans `docs/referentiels/godot-forest-demo-licences.csv`.

## 1. Architecture du projet

Une scène de démonstration, `levels/test_biomes.tscn` (100 m sur 100 m), et trois briques maison. Aucune ne lit de données externes autres que des PNG.

| Brique | Fichier | Ce qu'elle fait |
|---|---|---|
| Terrain | `scenery/TerrainPatch3D.gd` | Maillage régulier, 160 × 160 subdivisions dans la scène, hauteur = bruit simplex (`FastNoiseLite`) × `height_scale` (18,93). Collision par `ConcavePolygonShape3D`. |
| Végétation | `addons/gnd_biomes/Biomes.gd` et `BiomeScatterEntry.gd` | Grille jitterée par hachage (graine, cellule), choix pondéré d'une entrée (`probability`), hauteur du sol par lancer de rayon physique, échelle et rotation aléatoires. Les instances sont regroupées par morceau de `chunk_size` (16 m) et par entrée, un `MultiMeshInstance3D` par pièce de maillage. |
| Herbe | `TerrainPatch3D.gd` (lignes 394-601) | Un seul `MultiMeshInstance3D` recentré sur la caméra, reconstruit dans un thread quand la caméra a bougé de `grass_rebuild_distance` (2,26 m). Rayon 15 m, espacement 0,2 m, 10 000 instances au plus. |
| Addon « Custom Biomes » | `addons/gnd_biomes/` | Outil d'éditeur : `@tool`, peinture de masque (`MaskPainterPanel.gd`), brouillard automatique (`AutoBiomesFog.gd`). Il génère à partir de masques PNG, pas d'un catalogue. |

- **Niveaux de détail :**
  - Le morceau proche utilise le maillage complet. Au-delà de `billboard_lod_distance` (20 à 40 m dans la scène), il bascule sur un imposteur en croix orientée (`BILLBOARD_FIXED_Y`) par `visibility_range_begin/end` (`Biomes.gd` lignes 519-532).
  - Un « LOD de densité » masque une fraction des instances avec la distance, par `visible_instance_count` (lignes 1219-1267). Dans la scène : de 100 % à 30 m jusqu'à 10 % à 50 m.
  - Les imports glTF demandent `meshes/generate_lods=true`, et `project.godot` fixe `mesh_lod/lod_change/threshold_pixels=2.0`.
- **Instanciation :** `MultiMesh` partout. Pas de GPUParticles, pas de tuiles chargées à la volée, pas de culling propre : les morceaux sont tous générés en une passe à `_ready`, dans le fil principal (`Biomes._generate`, lignes 372-494).
- **Shaders :** vent partagé par variables globales (`gnd_wind_*`, `materials/tree_wind.gdshader`) ; herbe SimpleGrassTextured avec déplacement par le joueur et cartes de mouvement (16 fichiers, MIT) ; ciel nuageux et rayons de soleil (`scenery/`, origine non indiquée).
- **Performances annoncées :** aucune. Le README n'en contient pas (0 occurrence de « fps », « performance », « trees », etc.), la page GitHub non plus. Ordre de grandeur de la scène d'essai, calculé par moi à partir du `.tscn` : pour les arbres, espacement moyen 1,9 m sur 100 × 100 m, soit environ 2 770 candidats avant masque, plafonnés à 5 000 par défaut. Aucune mesure n'est fournie.

## 2. Correspondance avec BRIEF §10 (Massif : Godot 4, reprise du prototype)

| Besoin de §10 | Ce que fait le projet | Couverture |
|---|---|---|
| Lecture de `sim/` | Aucune lecture de fichier de données (`DirAccess` apparaît une seule fois, pour créer un dossier). Seuls des PNG de masque sont chargés. | **Absent** |
| Arbres du générateur (glTF de §9) | Importe des `scene.gltf` à l'édition, avec LOD générés. Aucun chargement glTF à l'exécution (`GLTFDocument` : 0 occurrence). | **Partiel** : l'import par l'éditeur existe, le chargement dynamique de nos `.glb` non |
| Placer les arbres du générateur | Placement par hachage et lancer de rayon, indépendant de `sim/trees.parquet`. | **Absent**, mais le mécanisme de morceaux de MultiMesh est réutilisable |
| Strate herbacée autour de la caméra | Herbe recentrée sur la caméra, thread, rayon et plafond réglables | **Oui** pour la mécanique ; **non** pour le pilotage : il vient d'un masque PNG, pas du biome et du couvert |
| Semis autour de la caméra, d'après biome et couvert | Pas de notion de semis ni de strate. Une entrée `Biomes` avec échelle réduite pourrait en tenir lieu. | **Absent** |
| Biome (BRIEF §5) | Un « biome » ici est un nœud avec une liste d'entrées pondérées, pas notre YAML (`strates`, `condition`, `composition`) | **Écart de sens** : même mot, autre objet |
| Ouvrir aux coordonnées de la vue web | Rien (pas de paramètre de lancement, pas de CRS) | **Absent** |

## 3. Licences

Tableau complet : `docs/referentiels/godot-forest-demo-licences.csv` (22 lignes). Résumé :

- **Dépôt : CC BY 4.0** (`LICENSE` ligne 1, `README.md` lignes 38-41). Il couvre le code maison (terrain, `gnd_biomes`, scènes). FSF, page « Various Licenses and Comments about Them » (https://www.gnu.org/licenses/license-list.html) : CC BY 4.0 est classée comme licence libre sans copyleft, compatible avec toutes les versions de la GPL, mais la FSF déconseille les licences CC pour le logiciel. **Je n'ai pas pu lire cette page** (www.gnu.org n'est pas joignable depuis la session) : l'énoncé vient du résumé d'un moteur de recherche, pas du texte de la page. À reverrifier sur la page elle-même.
- **Modèles Sketchfab : 9 fichiers `license.txt`, tous lus, tous « CC-BY-4.0 »** (ligne 7 de chacun) : bouleau, 2 fleurs, maison, puits, 4 pins, plus un pistolet laser dans l'addon UniPlayer, que la liste de l'orchestrateur ne mentionnait pas. Aucun CC-BY-NC ni « Standard ». Chaque fichier exige le crédit de sa ligne 11. Reprise possible dans un dépôt GPL-3 avec attribution.
- **MIT** : `debug_menu` (Hugo Locurcio, `LICENSE.md`), 16 shaders d'herbe (IcterusGames, avis en tête de fichier). Les deux sont compatibles GPL selon mon savoir général ; la page FSF n'a pas pu être relue pour Expat (MIT) dans la session.
- **CC0** : ciel Poly Haven, selon le README. Page Poly Haven non lue.
- **À ne pas reprendre :** la musique (Pixabay Content License, page non lue, licence qui n'est pas une licence libre à ma connaissance).
- **Non établi (à ne pas supposer) :**
  - textures et maillage d'herbe ;
  - UniPlayer (licence absente du clone, « BSD-3-Clause » sur la page amont, texte non lu) ;
  - `SunShafts*` et `layered_cloud_sky.gdshader` (aucun avis, aucun crédit) ;
  - le statut d'auteur de `gnd_biomes` : `plugin.cfg` déclare `author="OpenAI"`. Le droit d'auteur sur du code produit par un assistant IA est une question juridique que je ne tranche pas.
- **Ce qui est mêlé :** le code sous CC BY 4.0 est exigeant sur l'attribution et sur la mention des modifications. Un dépôt GPL-3 peut l'intégrer, mais le résultat devrait porter ces mentions en plus de l'entête GPL. L'interprétation juridique appartient à Pascal.

## 4. Écarts avec nos contrats (BRIEF §4)

| Contrat | Projet | Écart |
|---|---|---|
| `sim/trees.parquet` (`tree_id, year, species, x, y, d130, h, hcb, cw, status`) | Aucun lecteur de parquet ; aucun CSV, JSON ni GeoTIFF lu | À écrire : lecteur dans Godot (extension native ou conversion préalable). Le choix du format de passage est une décision à poser à Pascal. |
| `dtm.tif` (MNT) | Terrain = bruit simplex, grille régulière centrée sur le nœud | Remplacer par un relief issu du MNT |
| EPSG:2154 | Repère local de Godot (Y vers le haut, origine au centre du nœud), aucune notion de CRS | Prévoir une origine locale et le passage de (x, y, z) Lambert-93 à (x, z, y) Godot. Les valeurs de Lambert-93 (de l'ordre de 10⁶ m) dépassent ce que la simple précision permet d'afficher sans saut : à traiter par un décalage d'origine (règle générale de la simple précision, non mesurée ici). |
| `assets/trees/<species>_<stage>.glb` avec trois LOD | Les `scene.gltf` sont importés à l'édition avec `generate_lods=true` ; pas de chargement à l'exécution | Soit importer nos `.glb` dans le projet à la construction, soit charger à l'exécution (non présent) |
| Échelle des arbres | `scale_min/scale_max` fixes par entrée (0,4 à 2,2 sur la scène) | Chez nous, hauteur et houppier viennent de `h` et `cw` de `sim/trees.parquet` : l'échelle doit être calculée par arbre |
| Échelle de la zone | 100 × 100 m | BRIEF §3 : massif de quelques km², un agent par arbre |
| `biomes/*.yml`, `biome_map.tif` | Masque PNG RGBA8 par entrée | À remplacer ou adapter |

## 5. Synthèse du fil du forum Godot

**Statut : non lu.** Adresse : https://forum.godotengine.org/t/best-approach-for-rendering-a-procedurally-generated-forest-with-thousands-of-trees-in-godot-4-7/141770.

- La récupération directe a échoué : `forum.godotengine.org` ne se résout pas depuis la session (hôte hors de la liste autorisée). Il faut l'autoriser dans les réglages réseau de la session pour relancer.
- Une recherche web a confirmé l'existence et le titre du fil (« Best approach for rendering a procedurally generated forest with thousands of trees in Godot 4.7? », catégorie Help). Elle n'a rendu ni son contenu, ni ses dates, ni ses auteurs. Je n'en tire donc **ni la version de Godot visée** (le titre mentionne 4.7 ; je n'ai rien d'autre), **ni les dates des messages, ni les recommandations du fil**.
- Pour mémoire, le même outil a résumé d'autres fils du forum : MultiMesh par morceaux, imposteurs ou billboards à distance, scènes réelles près de la caméra, `alpha scissor` plutôt que mélange alpha, échantillonnage de Poisson, addons Proton Scatter et Spatial Gardener. Ce résumé est un agrégat de fils différents, de seconde main : **il n'est pas le contenu du fil demandé** et ne doit pas servir à décider.
- **Comparaison avec le projet et avec notre besoin : non faite**, faute de la source. Le BRIEF ne donne pas de chiffre pour la vue massif : le « 100 000 arbres affichés » est le critère de M4, pour la vue web (§11). §10 demande pour le massif la lecture de `sim/`, les arbres du générateur, la strate herbacée et les semis ; §3 précise un massif de « quelques km² » avec un agent par arbre.

## 6. Avis : trois voies et ce que coûte chacune

*Cette partie est un avis de l'acquéreur, pas un fait. Pascal tranche.*

### Voie A : partir du projet (fork)

- **Ce qu'on garde :** terrain, `gnd_biomes`, herbe, joueur, vent, scène d'essai.
- **Ce que ça coûte :**
  - tout ce qui est « Absent » au §2 reste à écrire ;
  - code sous CC BY 4.0 : attribution et mention des modifications à tenir sur tout le dépôt ;
  - il faut retirer ou remplacer la musique, les modèles de décor, `uniplayer` (armes, faim, poison) et les modèles hors de nos essences ;
  - `gnd_biomes` génère tout en une passe dans le fil principal : à l'échelle de quelques km², il faudra le refondre en chargement par morceaux ;
  - l'auteur déclaré du plugin (OpenAI) est un point juridique ouvert ;
  - dépendance à un projet de deux commits dont rien ne dit qu'il sera maintenu.
- **Ce que ça rapporte :** de l'avance sur la scène, le joueur et l'herbe. Mais la partie qui nous importe (lecture de `sim/`, placement par `tree_id`, biome du catalogue) n'y est pas.

### Voie B : reprendre des parties

- **Candidats, par ordre d'intérêt :**
  1. L'herbe recentrée sur la caméra avec reconstruction en thread (`TerrainPatch3D.gd` lignes 394-601) : la mécanique de §10. Il faudra remplacer le masque PNG par une valeur dérivée du biome et du couvert.
  2. Le découpage en morceaux de MultiMesh avec imposteur et LOD de densité (`Biomes.gd`) : réutilisable pour les arbres de `sim/trees.parquet`, à condition de les charger par morceaux autour de la caméra.
  3. Les shaders d'herbe (MIT, avis à conserver) : sous réserve de la licence des textures, non établie.
- **Ce que ça coûte :** chaque morceau repris porte sa licence (CC BY 4.0 pour le code maison, MIT pour les shaders) et son attribution. Le code est écrit pour l'éditeur (`@tool`, `EditorInterface`) : le retirer demande du travail. Il est lisible, mais sans tests (aucun test dans le clone, alors que CLAUDE.md demande « pas de code sans tests ») : il faudra en ajouter.

### Voie C : s'en inspirer seulement

- **Ce qu'on prend :** les idées (MultiMesh par morceau, imposteur par distance de visibilité, herbe centrée sur la caméra, variables de shader globales pour le vent), citées dans la documentation.
- **Ce que ça coûte :** tout est à réécrire sous GPL-3 et à tester, mais sans dette de licence ni d'attribution (une inspiration d'idée ne reprend pas l'expression du code ; avis, non juridique). Le plus de travail initial, le moins de dépendances.

### Ce qui ne dépend pas de la voie

Le lecteur de `sim/`, la conversion Lambert-93 vers Godot, l'échelle par arbre et le chargement par morceaux sont à écrire dans les trois cas. L'écart principal entre les voies est donc la licence et la dette de code, pas les fonctions.

## 7. Points non vérifiés

- Le **fil du forum** : non lu (réseau). Version de Godot, dates, recommandations, comparaison : manquants.
- La **page FSF** « Various Licenses and Comments about Them » : non lue directement. CC BY 4.0 : résumé de recherche seulement. MIT (Expat) et CC0 : non confirmés par la page dans cette session.
- **Licence d'UniPlayer** (texte BSD-3 non lu), **textures et maillage d'herbe**, **ciel (Poly Haven)**, **musique (Pixabay)** : pages ou fichiers non lus.
- **Origine des fichiers `SunShafts*` et `layered_cloud_sky.gdshader`** : aucun avis dans le clone.
- **Droit d'auteur du code de `gnd_biomes`** (auteur déclaré « OpenAI ») : question juridique, non tranchée.
- **Aucune exécution** : performances, fonctionnement dans Godot 4.6, comportement avec nos données non mesurés. Pas de Godot installé.
- Lecture du code : `Biomes.gd` et `TerrainPatch3D.gd` en entier ; `MaskPainterPanel.gd`, `AutoBiomesFog.gd`, `plugin.gd`, les scripts UniPlayer et SunShafts **non relus** pour cet inventaire.
- Nombre exact de fichiers `.gd` et `.gdshader` : non recompté (l'orchestrateur indique environ 60).
- Les 2 commits et les 34 étoiles viennent de la page GitHub (récupérée par un outil de lecture de page) ; le clone n'a qu'un enregistrement.

## 8. Trois points au sol

À vérifier par Pascal sur le terrain ou dans le projet.

1. **Un arbre du clone, côté licence.** Ouvrir un des `objects/pine-tree-*/license.txt` et vérifier sur la page Sketchfab (lien dans le CSV) que le modèle porte bien « CC Attribution » à ce jour : les `license.txt` datent du téléchargement, et l'auteur a pu changer la licence depuis (non vérifié).
2. **Le passage Lambert-93 vers Godot sur un point connu.** Prendre une coordonnée de `sim/trees.parquet` du massif test et vérifier qu'après décalage d'origine, l'arbre se place à moins d'un mètre de la position attendue sur le MNT : c'est là que la précision simple et l'inversion d'axes risquent le plus de se tromper.
3. **L'herbe sous deux biomes.** Sur un point du massif test où le catalogue donne deux strates herbacées différentes (par exemple myrtille et fougère aigle), vérifier que la vue peut les distinguer. Le projet ne sait pas le faire (un seul maillage d'herbe, un masque), c'est donc le test qui dira si la voie B suffit.

## 9. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* La base de `viewer-massif` (jalon M6) : fork, reprise de parties, ou simple inspiration de godot-forest-demo.

## 10. Liste de contrôle

Liste de contrôle passée, avec les points non cochés suivants :

1. **Sources et emplacements :** coché pour le clone (fichier et ligne), les `license.txt` et `LICENSE*`. **Non coché :** la page FSF, le fil du forum, les pages Poly Haven, Pixabay, Sketchfab et IcterusGames (non lues, ou lues seulement par résumé de recherche ou de page).
2. **Décomptes :** coché. 11 fichiers de licence trouvés par recherche de `*icense*`, `LICENSE`, `COPYING`, `NOTICE`, `credits`, `attribution` ; tous lus. 16 shaders avec avis MIT. 9 `license.txt`.
3. **Termes exacts :** coché (Godot 4.6 Forward Plus ; CC BY 4.0 International ; « CC-BY-4.0 » des `license.txt` ; MIT ; BSD-3-Clause et CC0 sous réserve de leurs sources).
4. **Statut dit tel qu'il est :** coché, voir §7.

## 11. Ligne de journal proposée

`2026-11-24 | acquereur | Mission 007 : étude de godot-forest-demo (commit 623212f, Godot 4.6) livrée dans docs/referentiels/. Le projet fournit terrain par bruit, MultiMesh par morceaux et herbe centrée sur la caméra ; il ne lit ni sim/, ni parquet, ni EPSG:2154. Licences : dépôt CC BY 4.0, 9 modèles Sketchfab CC-BY-4.0, herbe MIT ; non établies : UniPlayer, textures d'herbe, SunShafts ; musique à exclure. Fil du forum et page FSF non lus (réseau). Décision de la base de viewer-massif : à Pascal.`
