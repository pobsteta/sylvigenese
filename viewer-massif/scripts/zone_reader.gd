## Lecture de `massif/` (plan T5, T7 ; contrats assets.massif_index et assets.massif_block v2). Clé manquante, version de
## schéma inconnue, année absente, point hors emprise, zone sans `massif/` : erreur en français qui nomme la cause ; aucune
## valeur par défaut, jamais l'année voisine. Résultats : {ok, error, ...}.
extends RefCounted

const INDEX_KEYS := ["schema_version", "zone", "block_size_m", "provisoire", "notes", "models", "stage_models", "years"]
const BLOCK_KEYS := ["schema_version", "block_id", "year", "vertical_datum", "origin", "trees", "ground", "cells", "seedlings_simulated", "mentions", "provisoire"]
const TREE_KEYS := ["tree_id", "species", "stage", "x", "y", "z", "h", "d130", "hcb", "cw"]


static func _err(msg: String) -> Dictionary:
	return {"ok": false, "error": msg, "data": {}}


static func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return _err("fichier introuvable : " + path)
	var text := FileAccess.get_file_as_string(path)
	var json := JSON.new()
	if json.parse(text) != OK:
		return _err("%s : JSON illisible (ligne %d : %s)" % [path, json.get_error_line(), json.get_error_message()])
	if typeof(json.data) != TYPE_DICTIONARY:
		return _err(path + " : un objet JSON est attendu")
	return {"ok": true, "error": "", "data": json.data}


static func read_index(zone_dir: String) -> Dictionary:
	var path := zone_dir.path_join("massif").path_join("index.json")
	if not FileAccess.file_exists(path):
		return _err("zone sans massif/ : %s est introuvable (la zone doit porter massif/index.json, écrit par `assets`)" % path)
	var r := _read_json(path)
	if not r["ok"]:
		return r
	var d: Dictionary = r["data"]
	for k in INDEX_KEYS:
		if not d.has(k):
			return _err("%s : clé manquante « %s »" % [path, k])
	if int(d["schema_version"]) != 1:
		return _err("%s : schema_version %s inconnu (la vue lit la version 1)" % [path, str(d["schema_version"])])
	if typeof(d["stage_models"]) != TYPE_ARRAY or d["stage_models"].is_empty():
		return _err("%s : « stage_models » doit être une liste non vide (le fichier de modèle de chaque essence et stade ; index écrit par une version antérieure d'`assets` : le relancer)" % path)
	for m in d["stage_models"]:
		for k in ["species", "stage", "file", "kind"]:
			if not m.has(k):
				return _err("%s : une entrée de stage_models n'a pas la clé « %s »" % [path, k])
	if typeof(d["years"]) != TYPE_ARRAY:
		return _err(path + " : « years » doit être une liste")
	for y in d["years"]:
		for k in ["year", "blocks"]:
			if not y.has(k):
				return _err("%s : une année n'a pas la clé « %s »" % [path, k])
		for b in y["blocks"]:
			for k in ["block_id", "file", "sw", "size_m"]:
				if not b.has(k):
					return _err("%s : un bloc n'a pas la clé « %s »" % [path, k])
	return r


## Modèles de l'index par couple : « essence|stade » -> {species, stage, file, kind}. La vue ne reconstruit aucun nom de fichier.
static func stage_models(index: Dictionary) -> Dictionary:
	var out := {}
	for m in index.get("stage_models", []):
		out[stage_key(str(m["species"]), str(m["stage"]))] = m
	return out


static func stage_key(species: String, stage: String) -> String:
	return "%s|%s" % [species, stage]


static func read_block(path: String) -> Dictionary:
	var r := _read_json(path)
	if not r["ok"]:
		return r
	var d: Dictionary = r["data"]
	if not d.has("schema_version"):
		return _err("%s : clé manquante « schema_version »" % path)
	if int(d["schema_version"]) != 2:
		return _err("%s : schema_version %s non pris en charge (la vue lit la version 2 : terrain, couverts, mentions)" % [path, str(d["schema_version"])])
	for k in BLOCK_KEYS:
		if not d.has(k):
			return _err("%s : clé manquante « %s »" % [path, k])
	for k in ["x", "y", "z"]:
		if not d["origin"].has(k):
			return _err("%s : origin sans « %s »" % [path, k])
	for t in d["trees"]:
		for k in TREE_KEYS:
			if not t.has(k):
				return _err("%s : l'arbre « %s » n'a pas la clé « %s »" % [path, str(t.get("tree_id", "?")), k])
	var g: Dictionary = d["ground"]
	for k in ["resolution_m", "nx", "ny", "z"]:
		if not g.has(k):
			return _err("%s : ground sans « %s »" % [path, k])
	if int(g["nx"]) * int(g["ny"]) != g["z"].size():
		return _err("%s : ground.z compte %d valeurs pour %d x %d nœuds" % [path, g["z"].size(), int(g["nx"]), int(g["ny"])])
	for c in d["cells"]:
		for k in ["cell_id", "x", "y", "herb_cover", "shrub_cover"]:
			if not c.has(k):
				return _err("%s : la cellule %s n'a pas la clé « %s »" % [path, str(c.get("cell_id", "?")), k])
		if d["seedlings_simulated"] and not c.has("seedlings"):
			return _err("%s : seedlings_simulated est vrai mais la cellule %s n'a pas « seedlings »" % [path, str(c["cell_id"])])
	return r


static func _year_entry(index: Dictionary, year: int) -> Dictionary:
	for y in index["years"]:
		if int(y["year"]) == year:
			return y
	return {}


static func _years_text(index: Dictionary) -> String:
	var ys := []
	for y in index["years"]:
		ys.append(str(int(y["year"])))
	return ", ".join(ys)


## Emprise (xmin, ymin, xmax, ymax) des blocs d'une année.
static func extent(entry: Dictionary) -> Rect2:
	var r := Rect2()
	var first := true
	for b in entry["blocks"]:
		var s := float(b["size_m"])
		var box := Rect2(float(b["sw"]["x"]), float(b["sw"]["y"]), s, s)
		r = box if first else r.merge(box)
		first = false
	return r


static func resolve(index: Dictionary, x: float, y: float, year: int) -> Dictionary:
	var entry := _year_entry(index, year)
	if entry.is_empty():
		return {"ok": false, "error": "l'année %d n'est pas dans massif/index.json ; années disponibles : %s" % [year, _years_text(index)], "block_id": "", "file": ""}
	for b in entry["blocks"]:
		var sx := float(b["sw"]["x"])
		var sy := float(b["sw"]["y"])
		var s := float(b["size_m"])
		if x >= sx and x < sx + s and y >= sy and y < sy + s:
			return {"ok": true, "error": "", "block_id": str(b["block_id"]), "file": str(b["file"])}
	var e := extent(entry)
	return {"ok": false, "error": "le point (%.1f ; %.1f) est hors de la zone : emprise x de %.0f à %.0f, y de %.0f à %.0f (EPSG:2154)" % [x, y, e.position.x, e.end.x, e.position.y, e.end.y], "block_id": "", "file": ""}


## Identifiants des blocs de l'année dont le carré rencontre le disque de centre (x, y) et de rayon `radius_m`.
static func blocks_around(index: Dictionary, year: int, x: float, y: float, radius_m: float) -> Array:
	var out := []
	var entry := _year_entry(index, year)
	if entry.is_empty():
		return out
	for b in entry["blocks"]:
		var sx := float(b["sw"]["x"])
		var sy := float(b["sw"]["y"])
		var s := float(b["size_m"])
		var dx := maxf(maxf(sx - x, x - (sx + s)), 0.0)
		var dy := maxf(maxf(sy - y, y - (sy + s)), 0.0)
		if dx * dx + dy * dy <= radius_m * radius_m:
			out.append(str(b["block_id"]))
	return out


## Entrée d'index d'un bloc : {block_id, file, sw, size_m, trees}, ou {} si absent.
static func block_entry(index: Dictionary, year: int, block_id: String) -> Dictionary:
	for b in _year_entry(index, year).get("blocks", []):
		if str(b["block_id"]) == block_id:
			return b
	return {}
