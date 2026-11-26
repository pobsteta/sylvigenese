# Outils de M6a : Godot 4.6.3, GUT 9.6.1, glTF-Validator, MSFT_lod, shader d'herbe (mission 067)

## En-tête

- **Source :** pages et fichiers cités ligne par ligne ci-dessous ; clone en lecture seule de `godot-forest-demo` dans `/tmp/claude-0/gfd` (commit `623212ffeb4efbf4c95323a4a6a57e726be4f6e9`, voir `docs/referentiels/godot-forest-demo.md`).
- **Date de consultation :** 26/11/2026.
- **Propriétaire :** Pascal.
- **Mission redite :** relever licences et empreintes de Godot 4.6.3, de ses modèles d'export et de GUT 9.6.1 ; lire la licence du glTF-Validator ; lire la spécification `MSFT_lod` et ce que Godot 4.6.3 en lit ; établir la licence du shader d'herbe et l'origine des textures d'herbe.
- **Décision éclairée :** M6a, missions F (vue Godot) et G (CI) : quelles versions figer, quelles licences porter dans `CREDITS.md`, ce qui peut être copié de `godot-forest-demo`.
- **Outils de la session :** pas d'outil d'exécution ni de téléchargement de fichiers binaires. **Aucune empreinte n'a été recalculée** (le test de la fiche n'est pas rempli sur ce point). Les empreintes ci-dessous sont celles que **publie** la release, lues par deux lectures indépendantes du même fichier.
- **Hôtes inaccessibles (réseau) :** `zenodo.org`, `doi.org`, `api.datacite.org`, `opengameart.org`, `forum.godotengine.org`, `docs.godotengine.org`, `www.npmjs.com` (403). Passent : `github.com` (avec redirection vers `release-assets.githubusercontent.com`), `raw.githubusercontent.com`.
- **Écarts entre sources relevés :**
  1. README de `godot-forest-demo` (`README.md:21`) : textures **et** shaders d'herbe « MIT licensed » ; README amont de SimpleGrassTextured : texture `grassbushcc008.png` en **CC0**, shaders en MIT. Les deux ne concordent pas pour la texture.
  2. Le plan (`m6a.md:92`) lit la licence de GUT dans `addons/gut/LICENSE.md` de `main` ; la mention porte sur `main`, pas sur l'étiquette `v9.6.1` (archive d'étiquette refusée, 403).

## 1. Godot 4.6.3-stable

| Élément | Constat | Lu où |
|---|---|---|
| Licence | MIT : « Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur. » puis l'octroi de permission MIT | `godotengine/godot`, étiquette `4.6.3-stable`, `LICENSE.txt` lignes 1-6 (raw) |
| Binaire Linux | `Godot_v4.6.3-stable_linux.x86_64.zip` | `SHA512-SUMS.txt` de la release |
| SHA-512 publié | `a035258da32b77f966a5376f9fa29c30a6adde826a85ba918e1605bd1fc9823eba7d85f1dd5e748956bd2ba72827c0025ffa11bb82aec91128c407a2e723c99c` | idem |
| Modèles d'export | `Godot_v4.6.3-stable_export_templates.tpz` (il existe aussi un `…_mono_export_templates.tpz` : **ne pas le prendre**) | idem |
| SHA-512 publié | `da606b61c10157844f8300172df374472665f95015495cb1a7cd132c40ede404faa96cc1016a4b9662db9909ddea69632c4948b2cd11163438dad4808881fb68` | idem |
| URL de téléchargement | `https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/<fichier>` (302 vers `release-assets.githubusercontent.com`) | `SHA512-SUMS.txt` : 302 observé le 26/11/2026 |
| Accord des deux lectures | zip et `.tpz` lus deux fois, découpés en 4 tronçons de 32 puis en 8 tronçons de 16 caractères : concordance complète. Le début `a035258d…` et `da606b61…` concorde avec le plan (`m6a.md:88,90`) | deux appels de lecture |
| Tailles | 71,8 Mo et 1,26 Go : chiffres du plan, non remesurés | `docs/plans/m6a.md:88,90` |

- **Réserve sur « MIT » pour le binaire exporté :** le texte lu est celui du moteur. Un export embarque aussi des composants tiers avec leurs propres licences (connaissance générale, non lue ici : `COPYRIGHT.txt` du dépôt Godot). `CREDITS.md` de `viewer-massif` devra citer ces avis ; à lire avant la première livraison d'un binaire.
- **Le fichier `SHA512-SUMS.txt`** est lu par un modèle de lecture (la citation des lignes entières est refusée au-delà de 125 caractères). Le recalcul `sha512sum` sur le fichier téléchargé reste à faire en CI (étape du job `m6`).

## 2. GUT 9.6.1 (`bitwes/Gut`)

| Élément | Constat | Lu où |
|---|---|---|
| Version | `version="9.6.1"`, `author="Butch Wesley"` | `addons/gut/plugin.cfg` de `main` (raw) |
| Compatibilité | « GUT versions 9.x are for Godot 4.x » ; ligne `[9.6.1](…/releases/tag/v9.6.1) \| 4.6.x`; la branche `main` donne aussi 4.6.x | `README.md` de `main` (raw) |
| Licence | MIT : « Copyright (c) 2018 Tom "Butch" Wesley » | `addons/gut/LICENSE.md` lignes 1-3 (raw, `main`) |
| Empreinte | **absente** : aucune empreinte publiée trouvée ; la page des versions, l'archive d'étiquette et l'API sont refusées (403) | absent |
| Reste à faire | télécharger `v9.6.1` depuis un hôte autorisé, relire `plugin.cfg` et `LICENSE.md` de **l'étiquette**, calculer et noter le SHA-512 de l'archive | voir URL ci-dessous |

## 3. glTF-Validator de Khronos

| Élément | Constat | Lu où |
|---|---|---|
| Licence | **Apache License, Version 2.0, January 2004** : texte intégral lu au début et à l'annexe (modèle « Copyright [yyyy] [name of copyright owner] » non rempli) | `KhronosGroup/glTF-Validator`, `LICENSE` (raw, `main`) |
| Pas d'autre licence dans le dépôt lue | `README.md` : aucune section de licence ; `pubspec.yaml` (nom `gltf`, version `2.0.0-dev.3.11`) : aucun champ de licence | `README.md`, `pubspec.yaml` (raw, `main`) |
| `CONTRIBUTING.md` | « SPDX-FileCopyrightText: 2026 The Khronos Group, Inc. » ; « SPDX-License-Identifier: CC-BY-4.0 » (concerne ce document) ; renvoie à un accord de contributeur (CLA) non lu | `CONTRIBUTING.md` (raw) |
| Paquet npm `gltf-validator` | le README renvoie à `https://www.npmjs.com/package/gltf-validator` et à la construction `dart run grinder npm` ; **page npm : 403**, champ `license` du `package.json` publié **non lu** | `README.md` ; npmjs : refusé |
| Conclusion | « Apache-2.0 » est **lu** pour le dépôt source (le point M5 de la critique est levé pour le dépôt). Pour le **paquet npm** que le job `m6` installerait : **non lu**. | |

## 4. MSFT_lod et MSFT_screencoverage

Spécification : `KhronosGroup/glTF`, `extensions/2.0/Vendor/MSFT_lod/README.md` (raw, `main`, lue le 26/11/2026 par résumé ; citations longues refusées).

- **Statut :** « Complete » ; contributeurs : six personnes de Microsoft ; écrit pour glTF 2.0.
- **Licence de la spécification :** Open Web Foundation Agreement Version 1.0 (« made available by Microsoft »), texte de l'OWFa non lu.
- **`ids` :** `MSFT_lod` se pose sur l'objet de meilleure qualité ; `ids` liste les indices des objets de qualité moindre, chacun « lower in quality than the previous level ». Un client qui ne la connaît pas ne charge que le meilleur niveau.
- **Niveau `node` ou `material` :** les deux existent ; un LOD de nœud peut changer géométrie et matériaux.
- **`MSFT_screencoverage` :** n'est **pas une extension** : c'est un tableau dans `extras`, indicatif (exemple de la spec : 0,5 ; 0,2 ; 0,01 pour trois niveaux ; rien ne s'affiche sous le dernier seuil). Concorde avec le plan (§4, T2).
- **Ce que Godot 4.6.3 en lit :**
  - `modules/gltf/gltf_document.cpp`, étiquette `4.6.3-stable`, lu en trois blocs couvrant les 298 565 caractères : **aucune occurrence de `MSFT` ni de `lod`**, sauf `surface_get_lods` dans l'export d'une forme CSG. Pas de numéros de ligne (lecture par blocs de 100 000 caractères).
  - Extensions déclarées comme prises en charge (`get_supported_gltf_extensions_hashset`) : `GODOT_single_root`, `KHR_animation_pointer`, `KHR_lights_punctual`, `KHR_materials_emissive_strength`, `KHR_materials_pbrSpecularGlossiness`, `KHR_materials_unlit`, `KHR_node_visibility`, `KHR_texture_transform`. Les extensions de texture (`modules/gltf/extensions/gltf_document_extension_texture_ktx`, `_webp`) et `physics/` existent dans le dossier.
  - **Conclusion :** `MSFT_lod` n'est pas lue par `GLTFDocument` ; c'est bien notre chargeur (T13) qui la lira.
  - **Non lu :** les autres fichiers de `modules/gltf/` (la liste du dossier peut être incomplète) ; la propriété `GLTFState.json` sur laquelle repose T13 (`docs.godotengine.org` inaccessible) ; **ce que Godot fait d'une extension présente dans `extensionsUsed` mais non prise en charge** (la fonction qui vérifie `extensionsRequired` n'est pas dans les 100 000 premiers caractères lus ; le reste a été parcouru sur les extensions, pas sur cette fonction). À prouver par un test GUT de chargement (déjà prévu).

## 5. godot-forest-demo (commit 623212f) : shader et textures d'herbe

- **Shader : MIT, copyright (c) 2023 IcterusGames.** Deux sources concordantes :
  - dans le clone, `grass/shaders/grass.gdshader` et `grass/shaders/grass.gdshaderinc` : « Copyright (c) 2023 IcterusGames » ligne 3, texte MIT lignes 5 à 17 (le même avis en tête des 16 fichiers `.gdshader` et `.gdshaderinc`, d'après `godot-forest-demo.md` §3) ;
  - dépôt amont `IcterusGames/SimpleGrassTextured`, `LICENSE` lignes 1-3 (raw, `main`) : « MIT License », « Copyright (c) 2023 IcterusGames ». Sa section licence du `README.md` dit « MIT ».
  - Le dépôt `godot-forest-demo` n'a **pas** de fichier LICENSE dans `grass/` : l'avis n'existe que dans l'en-tête des shaders (à garder tel quel, comme prévu).
- **Uniforms globaux à déclarer** (`grass.gdshaderinc:56-64`) : `sgt_player_position`, `sgt_player_mov`, `sgt_normal_displacement`, `sgt_motion_texture`, `sgt_wind_direction`, `sgt_wind_strength`, `sgt_wind_turbulence`, `sgt_wind_movement`, `sgt_wind_pattern`. Le projet de démonstration les déclare dans `[shader_globals]` (`project.godot:69`, valeurs de textures `:97,101,121` : `grass/normal.png`, `grass/motion.png`, `grass/wind_pattern.png`).
- **Textures :**

| Fichier | Origine | Statut |
|---|---|---|
| `grass/grassbushcc008.png` (utilisée par `grass/grass.tres:4`) | README amont de SimpleGrassTextured : « Texture grassbushcc008.png, Licence CC0, by FabinhoSC https://opengameart.org/content/stylized-grass-and-bush-textures-0 » | **origine déclarée par l'auteur du shader, non confirmée à la source** (opengameart.org inaccessible) ; contredit par `godot-forest-demo/README.md:21` (« MIT licensed ») |
| `grass/normal.png`, `grass/motion.png`, `grass/wind_pattern.png`, `grass/grass.mesh`, `grass/grass.tres` | aucune mention dans le README amont ni dans le clone | **origine non établie** : ne pas copier |

- **Ce que dit la règle de Pascal** (copie du seul shader MIT, textures d'origine établie) : le shader peut être copié avec son avis ; **aucune texture n'a aujourd'hui une origine établie à la source**. `grassbushcc008.png` passerait si la page OpenGameArt confirme CC0 par FabinhoSC ; les autres textures n'ont pas d'origine : l'herbe doit se contenter d'une texture fabriquée par nous ou d'une couleur unie.

## 6. URL à télécharger ou à ouvrir (hôtes hors réseau de la session)

1. `https://opengameart.org/content/stylized-grass-and-bush-textures-0` : auteur, licence, fichier `grassbushcc008` (Pascal ou orchestrateur avec accès).
2. `https://zenodo.org/records/7307956` et `https://zenodo.org/records/4557401` : champ « License » de Wytham et de Demol.
3. `https://doi.org/10.25625/8PB1IF` : licence de BioDiv-3DTrees.
4. `https://github.com/bitwes/Gut/archive/refs/tags/v9.6.1.zip` (et la page des versions) : archive de l'étiquette, SHA-512 à calculer, `LICENSE.md` de l'étiquette.
5. `https://www.npmjs.com/package/gltf-validator` : champ `license` du paquet publié et version à figer.
6. `https://docs.godotengine.org/en/4.6/classes/class_gltfstate.html` : propriété `json` de `GLTFState`.
7. Calcul des empreintes : `sha512sum Godot_v4.6.3-stable_linux.x86_64.zip Godot_v4.6.3-stable_export_templates.tpz` après téléchargement depuis `https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/`.

## 7. Trois points au sol

1. **La texture d'herbe.** Ouvrir la page OpenGameArt et vérifier : auteur FabinhoSC, licence CC0, présence d'un fichier correspondant à `grassbushcc008.png`.
2. **Le binaire exporté.** Après le premier export Linux, lire `COPYRIGHT.txt` du dépôt Godot (étiquette `4.6.3-stable`) pour dresser la liste des avis tiers à mettre dans `CREDITS.md`.
3. **MSFT_lod.** Charger un `.glb` à trois niveaux dans Godot 4.6.3 avec `GLTFDocument.append_from_file` : vérifier qu'il ne plante pas à cause de l'extension non prise en charge et que `GLTFState.json` donne bien le bloc `extensions.MSFT_lod`.

## 8. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Les versions et licences à figer dans le job `m6` et dans `CREDITS.md`, et ce que la mission F peut copier de `godot-forest-demo` (le shader seulement, et aucune texture tant que l'origine n'est pas établie).

## 9. Liste de contrôle

- Sources et emplacements : coché pour Godot (licence, empreintes), GUT (`main`), glTF-Validator (dépôt), MSFT_lod, shader et clone. **Non coché :** empreinte de GUT ; licence du paquet npm du validateur ; texte de l'OWFa ; page OpenGameArt ; `GLTFState.json`.
- Décomptes : coché pour les 4 empreintes tronçons (zip, `.tpz`), 8 extensions prises en charge, 9 uniforms globaux. **Non coché :** recalcul des empreintes sur fichier téléchargé (aucun outil).
- Termes exacts : coché (licences citées telles que lues).
