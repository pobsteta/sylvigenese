## Chargement à l'exécution d'un modèle d'arbre `.glb` (plan T13). Les .glb sont dans data/<zone>/assets/trees/, hors res:// :
## l'importeur ne les voit pas ; ils sont lus par GLTFDocument.append_from_file puis generate_scene. Godot ne lit pas
## l'extension MSFT_lod : ce chargeur lit lui-même le JSON du .glb (nœud principal = LOD0, `ids` = LOD1 et LOD2,
## `extras.MSFT_screencoverage` = seuils d'écran) et pose les plages de visibilité. Trois niveaux exigés : pas de repli
## silencieux sur un seul.
##
## Seuil d'écran -> distance : un arbre de hauteur H couvre la fraction c de la hauteur de l'écran à la distance
## d = H / (2 tan(fov/2) c). Le niveau k finit là où la couverture tombe à MSFT_screencoverage[k] ; le dernier niveau n'a pas de
## fin (0 = sans fin ; la distance du dernier seuil est rendue à part, `cutoff_distance`, non appliquée).
extends RefCounted

## Le champ de vision vertical (degrés) de la caméra vient de config.yml (`viewer.camera.fov_deg`) : il convertit les seuils
## d'écran en distances ; il est passé à `load_glb`, sans valeur par défaut.


static func _fail(msg: String) -> Dictionary:
	return {"ok": false, "error": msg, "extras": {}, "levels": []}


## Bloc JSON d'un .glb, après contrôle de l'entête et de la longueur déclarée (un fichier tronqué est refusé).
static func _read_json_chunk(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"ok": false, "error": "modèle introuvable : " + path}
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < 20:
		return {"ok": false, "error": "%s : fichier trop court pour un .glb (%d octets)" % [path, bytes.size()]}
	if bytes.decode_u32(0) != 0x46546C67:
		return {"ok": false, "error": path + " : ce n'est pas un .glb (nombre magique glTF absent)"}
	if bytes.decode_u32(4) != 2:
		return {"ok": false, "error": "%s : version glTF %d non prise en charge (2 attendue)" % [path, bytes.decode_u32(4)]}
	if int(bytes.decode_u32(8)) != bytes.size():
		return {"ok": false, "error": "%s : .glb tronqué ou altéré (longueur déclarée %d, lue %d octets)" % [path, bytes.decode_u32(8), bytes.size()]}
	var json_len := int(bytes.decode_u32(12))
	if bytes.decode_u32(16) != 0x4E4F534A or 20 + json_len > bytes.size():
		return {"ok": false, "error": path + " : bloc JSON absent ou hors du fichier"}
	var json := JSON.new()
	if json.parse(bytes.slice(20, 20 + json_len).get_string_from_utf8()) != OK or typeof(json.data) != TYPE_DICTIONARY:
		return {"ok": false, "error": path + " : bloc JSON illisible"}
	return {"ok": true, "json": json.data}


static func _distance(height_m: float, coverage: float, fov_deg: float) -> float:
	return height_m / (2.0 * tan(deg_to_rad(fov_deg) / 2.0) * coverage)


## Indice de maillage valide dans `meshes` ? Un indice NÉGATIF est refusé (GDScript indexerait depuis la fin : un autre maillage).
static func _mesh_index_valid(g: Dictionary, mesh_index: int) -> bool:
	return g.has("meshes") and g["meshes"] is Array and mesh_index >= 0 and mesh_index < (g["meshes"] as Array).size() \
		and g["meshes"][mesh_index] is Dictionary


## Primitives d'un maillage : liste vide si l'indice est négatif, hors de la liste ou ne désigne pas un objet (jamais un autre maillage).
static func _primitives(g: Dictionary, mesh_index: int) -> Array:
	if not _mesh_index_valid(g, mesh_index):
		return []
	var prims = g["meshes"][mesh_index].get("primitives", [])
	return prims if prims is Array else []


## Nom du matériau d'une primitive, "" si elle n'en a pas de valide : pas de clé `material`, indice non entier, NÉGATIF
## (GDScript indexerait depuis la fin : un indice négatif n'est jamais un matériau) ou hors de la liste, liste absente,
## élément qui n'est pas un objet. Rien n'est deviné : "" donne le rôle « unknown », que `_check_roles` refuse.
static func _material_name(g: Dictionary, prim) -> String:
	var index := _material_index(g, prim)
	if index < 0:
		return ""
	return str((g["materials"][index] as Dictionary).get("name", ""))


## Indice valide du matériau de la primitive dans `materials`, -1 sinon (voir `_material_name`).
static func _material_index(g: Dictionary, prim) -> int:
	if not (prim is Dictionary) or not prim.has("material") or not g.has("materials") or not (g["materials"] is Array):
		return -1
	var raw = prim["material"]
	if not (raw is int or raw is float):
		return -1
	var index := int(raw)
	if float(raw) != float(index) or index < 0 or index >= (g["materials"] as Array).size():
		return -1
	if not (g["materials"][index] is Dictionary):
		return -1
	return index


## Libellé du matériau d'une primitive pour le message d'erreur : « nom » ou la cause précise du refus.
static func _material_label(g: Dictionary, prim) -> String:
	if not (prim is Dictionary) or not prim.has("material"):
		return "(sans matériau)"
	var index := _material_index(g, prim)
	if index < 0:
		return "(matériau %s invalide : indice hors de la liste, négatif ou élément qui n'est pas un objet)" % str(prim["material"])
	return "« %s »" % str((g["materials"][index] as Dictionary).get("name", ""))


## Rôle de chaque primitive d'un maillage, d'après le nom de son matériau dans le .glb. Contrat assets.tree_model (mission
## 084c ; assets écrit `<fichier>_<primitive>`, lod.py BARK puis FOLIAGE) : chaque niveau porte DEUX primitives, la première au
## matériau dont le nom se termine par « _ecorce » (« wood »), la seconde par « _feuillage » (« foliage »). Une primitive dont le
## matériau est absent ou autrement nommé est « unknown » : `_check_roles` la refuse, la vue ne devine aucune couleur.
static func _surface_roles(g: Dictionary, mesh_index: int) -> Array:
	var roles := []
	for prim in _primitives(g, mesh_index):
		var name := _material_name(g, prim)
		if name.ends_with("_ecorce"):
			roles.append("wood")
		elif name.ends_with("_feuillage"):
			roles.append("foliage")
		else:
			roles.append("unknown")
	return roles


## Erreur nommée si les rôles d'un niveau ne sont pas [wood, foliage] (deux primitives, écorce puis feuillage) ; "" sinon.
## Aucun modèle n'échappe à la règle : ni ceux du générateur, ni les génériques, ni les fixtures (qui la suivent aussi).
static func _check_roles(path: String, level: int, g: Dictionary, mesh_index: int, roles: Array) -> String:
	if not _mesh_index_valid(g, mesh_index):
		return "%s : le niveau %d désigne le maillage %d, absent de la liste des maillages du .glb (indice négatif ou hors de la liste) : le rôle (bois ou feuillage) n'est pas deviné" % [path, level, mesh_index]
	if roles == ["wood", "foliage"]:
		return ""
	var names := []
	for prim in _primitives(g, mesh_index):
		var label := _material_label(g, prim)
		names.append(label)
	return "%s : le niveau %d porte %d primitive(s), de matériaux %s ; le contrat des .glb d'arbres exige deux primitives dont les matériaux se terminent par _ecorce puis _feuillage : le rôle (bois ou feuillage) n'est pas deviné" % [path, level, roles.size(), ", ".join(names)]


## Triangles d'un niveau : la somme de toutes ses primitives (écorce et feuillage), comme le validateur des .glb.
static func _triangles(g: Dictionary, mesh_index: int) -> int:
	var n := 0
	for prim in _primitives(g, mesh_index):
		n += int(g["accessors"][int(prim["indices"])]["count"]) / 3
	return n


static func load_glb(path: String, fov_deg: float) -> Dictionary:
	if not fov_deg > 0.0 or not fov_deg < 180.0:
		return _fail("champ de vision %s : un angle strictement entre 0 et 180 degrés est exigé (viewer.camera.fov_deg)" % str(fov_deg))
	var head := _read_json_chunk(path)
	if not head["ok"]:
		return _fail(head["error"])
	var g: Dictionary = head["json"]
	if not (g.get("extensionsUsed", []) as Array).has("MSFT_lod"):
		return _fail("%s : extension MSFT_lod absente de extensionsUsed (trois niveaux de détail exigés)" % path)
	var lead := -1
	for i in range(g.get("nodes", []).size()):
		if g["nodes"][i].get("extensions", {}).has("MSFT_lod"):
			lead = i
	if lead < 0:
		return _fail("%s : aucun nœud ne porte MSFT_lod (trois niveaux de détail exigés)" % path)
	var ids: Array = g["nodes"][lead]["extensions"]["MSFT_lod"].get("ids", [])
	if ids.size() != 2:
		return _fail("%s : MSFT_lod doit lister 2 niveaux moins détaillés (%d lus) : trois niveaux exigés" % [path, ids.size()])
	var node_ids := [lead, int(ids[0]), int(ids[1])]
	var coverage: Array = g["nodes"][lead].get("extras", {}).get("MSFT_screencoverage", [])
	if coverage.size() != 3:
		return _fail("%s : extras.MSFT_screencoverage doit donner trois seuils (%d lus)" % [path, coverage.size()])
	for k in range(3):
		if float(coverage[k]) <= 0.0 or (k > 0 and float(coverage[k]) >= float(coverage[k - 1])):
			return _fail("%s : MSFT_screencoverage doit décroître et rester positif" % path)
	var mesh_of := []
	for n in node_ids:
		if n < 0 or n >= g["nodes"].size() or not g["nodes"][n].has("mesh"):
			return _fail("%s : le nœud %d d'un niveau de détail n'a pas de maillage" % [path, n])
		mesh_of.append(int(g["nodes"][n]["mesh"]))

	var state := GLTFState.new()
	var doc := GLTFDocument.new()
	var err := doc.append_from_file(path, state, 0)
	if err != OK:
		return _fail("%s : Godot n'a pas pu lire le .glb (%s)" % [path, error_string(err)])
	var scene := doc.generate_scene(state)
	if scene == null:
		return _fail(path + " : Godot n'a pas pu bâtir la scène du .glb")
	scene.free()
	var meshes := state.get_meshes()
	var levels := []
	for k in range(3):
		if mesh_of[k] < 0 or mesh_of[k] >= meshes.size():
			return _fail("%s : maillage %d absent après lecture" % [path, mesh_of[k]])
		var imported: ImporterMesh = meshes[mesh_of[k]].mesh
		var mesh := imported.get_mesh()
		var roles := _surface_roles(g, mesh_of[k])
		var role_error := _check_roles(path, k, g, mesh_of[k], roles)
		if role_error != "":
			return _fail(role_error)
		if roles.size() != mesh.get_surface_count():
			return _fail("%s : le niveau %d a %d primitive(s) dans le .glb et %d surface(s) après lecture : rôles bois/feuillage incertains" % [path, k, roles.size(), mesh.get_surface_count()])
		levels.append({"mesh": mesh, "surface_roles": roles, "triangles": _triangles(g, mesh_of[k]), "visibility_range_begin": 0.0, "visibility_range_end": 0.0})
	var height := (levels[0]["mesh"] as Mesh).get_aabb().end.y
	if height <= 0.0:
		return _fail(path + " : le niveau 0 n'a pas de hauteur (sommet en y <= 0)")
	var d0 := _distance(height, float(coverage[0]), fov_deg)
	var d1 := _distance(height, float(coverage[1]), fov_deg)
	levels[0]["visibility_range_end"] = d0
	levels[1]["visibility_range_begin"] = d0
	levels[1]["visibility_range_end"] = d1
	levels[2]["visibility_range_begin"] = d1
	return {
		"ok": true, "error": "", "extras": g.get("extras", {}), "levels": levels, "height_m": height,
		"cutoff_distance": _distance(height, float(coverage[2]), fov_deg),
	}
