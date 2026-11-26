## Constantes d'affichage de la vue : bloc `viewer:` de config.yml (mission 068 ; décisions Q2 et Q4 du 26/11/2026).
## PROVISOIRE, « illustration, non mesurée » : seule l'apparence est là ; le nombre de brins suit le couvert du bloc et le
## nombre de semis suit sim/cells. Aucune valeur de repli : si config.yml est introuvable ou incomplet, la vue s'arrête
## et dit où elle a cherché. Lecteur minimal du sous-ensemble de YAML employé par ce bloc (cartes imbriquées par
## indentation, cartes en ligne `{a: b, c: d}`, nombres, booléens, chaînes entre guillemets).
extends RefCounted

const REQUIRED := ["grass.radius_m", "grass.recenter_distance_m", "grass.max_instances", "grass.blade_height_m",
	"grass.blades_per_m2_at_full_cover", "grass.color", "foliage.color_by_group", "lod.fade_margin_m", "mention", "provisoire"]


static func candidates(zone_dir: String) -> Array:
	var out := [zone_dir.path_join("config.yml"), zone_dir.path_join("../../config.yml"), "config.yml"]
	out.append(ProjectSettings.globalize_path("res://").path_join("../config.yml"))
	out.append(OS.get_executable_path().get_base_dir().path_join("config.yml"))
	return out


static func load_for_zone(zone_dir: String) -> Dictionary:
	var tried := []
	for p in candidates(zone_dir):
		if FileAccess.file_exists(p):
			var r := parse_text(FileAccess.get_file_as_string(p))
			if not r["ok"]:
				r["error"] = "%s : %s" % [p, r["error"]]
			else:
				r["source"] = p
			return r
		tried.append(p)
	return {"ok": false, "error": "config.yml introuvable (bloc viewer des constantes d'affichage) ; cherché dans : " + ", ".join(tried), "data": {}}


static func _scalar(s: String) -> Variant:
	s = s.strip_edges()
	if s.length() >= 2 and s.begins_with("\"") and s.ends_with("\""):
		return s.substr(1, s.length() - 2)
	if s == "true":
		return true
	if s == "false":
		return false
	if s.is_valid_float():
		return float(s)
	return s


static func _inline_map(s: String) -> Dictionary:
	var out := {}
	for part in s.substr(1, s.length() - 2).split(","):
		var kv := part.split(":", true, 1)
		if kv.size() == 2:
			out[kv[0].strip_edges()] = _scalar(kv[1])
	return out


static func parse_text(text: String) -> Dictionary:
	var lines := text.split("\n")
	var start := -1
	for i in range(lines.size()):
		if lines[i].begins_with("viewer:"):
			start = i
			break
	if start < 0:
		return {"ok": false, "error": "bloc « viewer: » absent", "data": {}}
	var root := {}
	var stack := [{"indent": -1, "map": root}]
	for i in range(start + 1, lines.size()):
		var raw := lines[i]
		var stripped := raw.strip_edges()
		if stripped == "" or stripped.begins_with("#"):
			continue
		var indent := raw.length() - raw.lstrip(" ").length()
		if indent == 0:
			break
		while stack.size() > 1 and stack[-1]["indent"] >= indent:
			stack.pop_back()
		var kv := stripped.split(":", true, 1)
		if kv.size() != 2:
			return {"ok": false, "error": "ligne illisible dans le bloc viewer : " + stripped, "data": {}}
		var key := kv[0].strip_edges()
		var val := kv[1].strip_edges()
		var cur: Dictionary = stack[-1]["map"]
		if val == "":
			var sub := {}
			cur[key] = sub
			stack.append({"indent": indent, "map": sub})
		elif val.begins_with("{") and val.ends_with("}"):
			cur[key] = _inline_map(val)
		else:
			cur[key] = _scalar(val)
	for path in REQUIRED:
		var node = root
		for part in path.split("."):
			if typeof(node) != TYPE_DICTIONARY or not node.has(part):
				return {"ok": false, "error": "viewer.%s manquant" % path, "data": {}}
			node = node[part]
	return {"ok": true, "error": "", "data": root, "source": ""}
