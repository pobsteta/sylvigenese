# Tests GUT de viewer-massif (mission 069)

Tests d'acceptation de M6a, écrits **sans lire** les scripts de la vue (mission 072) : ils appellent l'interface ci-dessous. Un script ou une fonction absents font **échouer** le test (rouge), jamais sauter. **Godot n'est pas installé dans l'environnement qui les a écrits** : ils ne tournent qu'en CI (mission 073). Ils visent GUT 9.6.1 (`extends GutTest`, `assert_eq`, `assert_almost_eq`, `assert_string_contains`, `fail_test`…) et Godot 4.6.3.

Lancer (depuis `viewer-massif/`) : `godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit`. `tests/fixtures/` porte un `.gdignore` : l'importeur ne voit pas les `.glb` d'essai (les tests les lisent par chemin absolu).

## Interface exigée de la vue (`res://scripts/`)

Toute fonction est `static` (appelée sur le script chargé), sauf `RequestGate` (instance). Tout résultat « avec erreur possible » est un `Dictionary` `{ok: bool, error: String, ...}` ; **`error` est en français et nomme la cause**.

| Script | Fonction | Rend |
|---|---|---|
| `viewer_args.gd` | `parse(args: PackedStringArray)` : `--zone <dossier> --x <X> --y <Y> --year <A>` (+ `--selftest`) | `{ok, error, zone, x: float, y: float, year: int, selftest: bool}` ; option manquante, valeur non numérique ou option inconnue : `ok = false`, `error` nomme l'option |
| `frame.gd` | `block_to_godot(x, y, z)` ; `godot_to_block(v: Vector3)` ; `lambert_to_godot(X, Y, Z, origin: Dictionary{x,y,z})` ; `godot_to_lambert(v, origin)` | `Vector3` ; bloc : x est, y nord, z haut (relatifs à l'origine du bloc) ; Godot : `(x, z, -y)` |
| `zone_reader.gd` | `read_index(zone_dir)` ; `read_block(chemin)` ; `resolve(index, x, y, year)` ; `blocks_around(index, year, x, y, radius_m)` | `{ok, error, data}` ; `resolve` : `{ok, error, block_id, file}` (année absente : `error` donne les années ; point hors emprise : `error` donne l'emprise ; jamais l'année voisine) ; `blocks_around` : `Array` de `block_id` |
| `tree_model_loader.gd` | `load_glb(chemin_absolu, fov_deg)` (champ de vision de `viewer.camera.fov_deg`, sans valeur par défaut, mission 077) | `{ok, error, extras: Dictionary, levels: [3 x {mesh: Mesh, triangles: int, visibility_range_begin: float, visibility_range_end: float}]}` ; 0 = sans fin pour `end` du dernier niveau |
| `grass.gd` | `positions(zone, cell_id, cx, cy, cell_size, herb_cover, params)` ; `build(zone, cells, cell_size, params)` | `PackedVector2Array` (x est, y nord, relatifs au bloc) ; `build` : `{positions, truncated: bool, message: String}` ; `params` : `blades_per_m2_at_full_cover`, `max_instances` (clés de `config.yml` `viewer.grass`) |
| `seedlings.gd` | `count(zone, cell_id, species, seedlings_ha, cell_area_ha)` | `int`, arrondi aléatoire à espérance exacte, déterministe |
| `request_gate.gd` | `new()`, `next_id() -> int`, `accept(id) -> bool` | seule la dernière requête est acceptée |
| `banner.gd` | `text(block: Dictionary, index: Dictionary)` | `String` : « provisoire », « semis non simulés » (si `seedlings_simulated` faux), « générique » et leur nombre, « stade de l'arbre », « 25 m » |

`--selftest` : voir `test_selftest.gd` (ligne `SELFTEST {json}` : `blocks`, `trees`, `generic_trees`, `grass_instances`, `seedlings`, `truncated`).

Autres exigences relues par les tests : `project.godot` déclare `[shader_globals]` pour chaque `global uniform` des `.gdshader` ; le shader d'herbe garde l'avis de copyright d'IcterusGames (MIT) ; `CREDITS.md` cite IcterusGames, `623212f` et GUT.

## Fixtures

`tests/fixtures/make_zone_m6.py` écrit `zone_m6/` (un bloc de 500 m, 4 arbres aux extrémités nord, sud, est, ouest, 3 `.glb` d'arbres synthétiques écrits à la main, plus `09_young.glb` (modèle des semis)) et `zone_m6_sans_herbe/`. Valeurs synthétiques, aucune écologique. Les fichiers versionnés sont ceux du script ; ils sont conformes aux contrats `assets.massif_index`, `assets.massif_block` et `assets.tree_model`.

Si `SYLVIGENESE_M6_TREES_DIR` pointe vers `data/<zone>/assets/trees/`, les `.glb` produits par `assets` passent par les mêmes contrôles de chargement.

`zone_m6_stade_manquant/` (mission 075) : la même zone avec un hêtre jeune (`09`, stade `young`) dont l'essence n'a des exemplaires qu'aux stades `mature` et `old` ; l'index dit `generique_feuillu.glb` pour ce couple (`stage_models`). `test_repli_generique_et_echelle.gd` s'en sert, et construit dans `user://` les zones fautives (couple absent de l'index, `stage_models` absent, `cw` nul).

`tests/fixtures/arbre_ecorce_feuillage.glb` (mission 085) : un arbre à deux primitives par niveau, matériaux `arbre_ecorce` et `arbre_feuillage`, comme ceux de `assets` ; `test_bois_bandeau_nord.gd` s'en sert pour les couleurs du bois et du feuillage, et teste le bandeau (lignes courtes, à la ligne) et la flèche du nord (convention : `scripts/compass.gd`).
