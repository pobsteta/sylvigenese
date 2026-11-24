# iTowns : instanciation glTF dans `OGC3DTilesLayer` (mission 016)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Mission redite :** établir, code lu, si iTowns (`OGC3DTilesLayer`) et sa dépendance 3d-tiles-renderer prennent en charge `EXT_mesh_gpu_instancing`, 3D Tiles 1.1 et i3dm.
- **Décision éclairée :** spec §12 (« Prise en charge de l'instanciation glTF dans iTowns ») et jalon M4 (100 000 instances chargées et dessinées) : quel format de tuiles viser (glTF avec `EXT_mesh_gpu_instancing`, ou i3dm).

## Sources réellement consultées

- **Clone local, lecture seule** : `/tmp/claude-0/repos/itowns` (branche par défaut ; commit non relevé, `.git` non lu). Version `2.46.0` (`/tmp/claude-0/repos/itowns/packages/Main/package.json:3`).
- **`node_modules` absent du clone** : le code de `three` et de `3d-tiles-renderer` n'y est pas. Je l'ai lu sur GitHub, aux versions exactes de `package-lock.json` :
  - https://raw.githubusercontent.com/mrdoob/three.js/r182/examples/jsm/loaders/GLTFLoader.js (three 0.182.0)
  - https://github.com/NASA-AMMOS/3DTilesRendererJS/tree/v0.5.3/src/three/... (3d-tiles-renderer 0.5.3)
  Ces lectures de GitHub ont été faites par un outil qui résume la page : **les numéros de ligne de ces fichiers extérieurs ne sont pas donnés** (l'outil ne les restitue pas de façon fiable). Les citations de code sont faites par noms de classe, de constante et de méthode.

## Versions

| Élément | Version | Emplacement |
|---|---|---|
| `3d-tiles-renderer` | `^0.5.3`, résolue 0.5.3 | `packages/Main/package.json:58` ; `package-lock.json:4421-4423` |
| `three` | `^0.182.0`, résolue 0.182.0 | `packages/Main/package.json:73` ; `package-lock.json:11630-11631` |

(chemins relatifs à `/tmp/claude-0/repos/itowns/`)

## Constats

### A. `EXT_mesh_gpu_instancing` : prise en charge **par three, non par iTowns lui-même**

- Dans `GLTFLoader.js` de three r182 : constante `EXTENSIONS.EXT_MESH_GPU_INSTANCING = 'EXT_mesh_gpu_instancing'`, classe `GLTFMeshGpuInstancing` (méthode `createNodeMesh` : construit un `InstancedMesh` à partir des accesseurs TRANSLATION, ROTATION, SCALE), et enregistrement dans le constructeur de `GLTFLoader` (`this.register(function (parser) { return new GLTFMeshGpuInstancing(parser); })`). Elle est donc active par défaut.
- iTowns : `packages/Main/src/Parser/iGLTFLoader.js:3` importe `GLTFLoader` de `three/addons`, `:21` l'instancie (`this.glTFLoader = new GLTFLoader()`), `:162` lui délègue le `parse` des glTF 2.0 (le glTF 1.0 va au chargeur historique, `:159-160`). Les extensions par défaut de three sont donc héritées.
- **Aucune occurrence** de `EXT_mesh_gpu_instancing` dans le clone (recherche de texte sur tout le dépôt hors `node_modules`) : ni code, ni test, ni exemple, ni changelog. **Aucun test d'iTowns ne couvre cette extension.** Prise en charge = héritée, non testée par iTowns.
- `OGC3DTilesLayer.js:30-33` : `itownsGLTFLoader = new iGLTFLoader()` + trois extensions Cesium enregistrées (`GLTFMeshFeaturesExtension`, `GLTFStructuralMetadataExtension`, `GLTFCesiumRTCExtension`) ; `:412` : `this.tilesRenderer.manager.addHandler(/\.gltf$/, itownsGLTFLoader)`.
- **Point d'attention (déduction, non éprouvée) :** le gestionnaire n'est déclaré que pour `/\.gltf$/` (`:412`). Une tuile de contenu `.glb` ne correspond pas à ce motif ; d'après le code de 3d-tiles-renderer 0.5.3 (`TilesRenderer.parseTile`, cas `'gltf'` et `'glb'`), il utilise alors le gestionnaire de `path.gltf` / `path.glb` s'il existe, sinon crée un `new GLTFLoader(manager)`. Un `.glb` pourrait donc passer par un chargeur sans le Draco, le KTX2 et le meshopt réglés par iTowns (`:96-143`). **À tester** avec un `.glb` réel avant M4.

### B. i3dm : pris en charge **par 3d-tiles-renderer, câblé sans test dans iTowns**

- 3d-tiles-renderer 0.5.3 : `src/three/renderer/loaders/I3DMLoader.js` existe ; il crée un `InstancedMesh` par maillage glTF (`new InstancedMesh(geometry, material, INSTANCES_LENGTH)`) et lit POSITION ou POSITION_QUANTIZED, NORMAL_UP/NORMAL_RIGHT (ou leur forme oct32p), SCALE et SCALE_NON_UNIFORM, RTC_CENTER, EAST_NORTH_UP. `TilesRenderer.parseTile` oriente `case 'i3dm'` vers ce chargeur (à côté de b3dm, pnts, cmpt, gltf/glb).
- iTowns ne code rien de propre pour l'i3dm. Seule trace : `OGC3DTilesLayer.js:598-605` (`getC3DTileFeatureFromIntersectsArray`) utilise `instanceId` d'une intersection comme identifiant d'objet de repli (`batchId = ... ?? instanceId`), et `changelog.md:168` : « **i3dm:** use instanceId to get info (683e55d) ».
- Aucun exemple ni test fonctionnel ne charge de tuile i3dm (recherche `i3dm` : une seule occurrence, `changelog.md:168`).

### C. 3D Tiles 1.1 : **partiel, déduit** du code, non annoncé par iTowns

- `OGC3DTilesLayer.js:410` : `this.tilesRenderer.registerPlugin(new ImplicitTilingPlugin())` : le pavage implicite (fonction de 3D Tiles 1.1) est actif.
- `OGC3DTilesLayer.js:31-32` : métadonnées structurées (`EXT_structural_metadata`) et `EXT_mesh_features` enregistrées sur le chargeur glTF.
- Contenu glTF direct (sans b3dm), fonction de 3D Tiles 1.1 : géré par 3d-tiles-renderer (cas `'gltf'`/`'glb'` de `parseTile`, commenté « 3DTILES_content_gltf » dans le code lu), sous réserve du point A.
- **Non trouvé :** la chaîne « 3D Tiles 1.1 » n'apparaît ni dans `OGC3DTilesLayer.js` ni dans `changelog.md`. La README de 3d-tiles-renderer 0.5.3 dit seulement « supports most of the 3D Tiles spec features with a few exceptions » et renvoie à un jalon GitHub que je n'ai pas lu : **la liste des fonctions non prises en charge est inconnue**.
- `changelog.md:340` : « **3dtiles:** add new OGC3DTilesLayer using 3d-tiles-renderer-js (a2fedd8) ». Mises à jour de la dépendance : `:138`, `:242`, `:243`.

### D. Autre instanciation dans iTowns (hors 3D Tiles)

`packages/Main/src/Converter/Feature2Mesh.js:1085-1088` (`createInstancedMesh`, `new THREE.InstancedMesh(...)`) et `:1121-1171` (`pointsToInstancedMeshes`) : instanciation de modèles sur des **points de couche vectorielle** ; exemple `examples/misc_instancing.html`, test `test/functional/misc_instancing.js`, `packages/Main/test/unit/feature2mesh.js:120-128`. Ce n'est pas une couche `OGC3DTilesLayer`. Chemin alternatif possible pour M4, avec ses propres limites (non évaluées ici).

## Réponse en une ligne

Dans `OGC3DTilesLayer`, glTF avec `EXT_mesh_gpu_instancing` et i3dm sont **pris en charge par les dépendances (three r182, 3d-tiles-renderer 0.5.3)**, et **jamais testés ni exemplifiés par iTowns** ; 3D Tiles 1.1 est **partiel** (pavage implicite, métadonnées, contenu glTF), sans liste officielle. Aucun rendu de 100 000 instances n'a été exécuté : la prise en charge réelle se prouve par un essai au jalon M4.

## Limites

- Rien n'a été exécuté (pas de navigateur, pas de test).
- Fichiers extérieurs lus sans numéros de ligne (voir plus haut).
- Version de three et de 3d-tiles-renderer : celles du `package-lock.json` du clone ; l'exemple de Pascal pourra en utiliser d'autres.
