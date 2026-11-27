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

## Champ de vision vertical (degrés) de la caméra de la vue : sert à convertir les seuils d'écran en distances.
const FOV_DEG := 75.0


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


static func _distance(height_m: float, coverage: float) -> float:
	return height_m / (2.0 * tan(deg_to_rad(FOV_DEG) / 2.0) * coverage)


static func _triangles(g: Dictionary, mesh_index: int) -> int:
	var prim: Dictionary = g["meshes"][mesh_index]["primitives"][0]
	return int(g["accessors"][int(prim["indices"])]["count"]) / 3


static func load_glb(path: String) -> Dictionary:
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
		if mesh_of[k] >= meshes.size():
			return _fail("%s : maillage %d absent après lecture" % [path, mesh_of[k]])
		var imported: ImporterMesh = meshes[mesh_of[k]].mesh
		levels.append({"mesh": imported.get_mesh(), "triangles": _triangles(g, mesh_of[k]), "visibility_range_begin": 0.0, "visibility_range_end": 0.0})
	var height := (levels[0]["mesh"] as Mesh).get_aabb().end.y
	if height <= 0.0:
		return _fail(path + " : le niveau 0 n'a pas de hauteur (sommet en y <= 0)")
	var d0 := _distance(height, float(coverage[0]))
	var d1 := _distance(height, float(coverage[1]))
	levels[0]["visibility_range_end"] = d0
	levels[1]["visibility_range_begin"] = d0
	levels[1]["visibility_range_end"] = d1
	levels[2]["visibility_range_begin"] = d1
	return {
		"ok": true, "error": "", "extras": g.get("extras", {}), "levels": levels, "height_m": height,
		"cutoff_distance": _distance(height, float(coverage[2])),
	}
