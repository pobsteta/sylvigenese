## Socle commun des tests GUT de viewer-massif (mission 069). Étape visée : BRIEF §10 (vue massif), plan docs/plans/m6a.md §5 T6 à T14 et §6.
## Les tests ne lisent pas les scripts de la vue : ils appellent l'interface décrite dans tests/README.md. Un script absent
## fait ÉCHOUER le test (rouge), jamais sauter : voir `need`.
extends GutTest

const FIXTURES := "res://tests/fixtures/"
## Champ de vision (degrés) passé au chargeur dans les tests : la vue le lit dans config.yml (viewer.camera.fov_deg), ici une valeur d'essai.
const FOV_DEG_ESSAI := 75.0


## Chemin absolu (système de fichiers) d'une zone d'essai : tests/fixtures porte un .gdignore, hors de l'importeur.
func zone_path(name: String = "zone_m6") -> String:
	return ProjectSettings.globalize_path(FIXTURES + name)


## Charge un script de la vue ; s'il manque, le test échoue (et rend null : le test doit alors rendre la main).
func need(path: String) -> Variant:
	var s = load(path)
	if s == null:
		fail_test("script de la vue absent : " + path + " (interface : viewer-massif/tests/README.md)")
	return s


func read_text(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		fail_test("fichier illisible : " + path)
		return ""
	return f.get_as_text()


func read_json(path: String) -> Dictionary:
	var d = JSON.parse_string(read_text(path))
	if typeof(d) != TYPE_DICTIONARY:
		fail_test("JSON illisible : " + path)
		return {}
	return d


## JSON du bloc de tête d'un .glb, relu octet par octet (indépendant du chargeur de la vue).
func glb_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		fail_test("glb illisible : " + path)
		return {}
	var magic := f.get_32()
	var version := f.get_32()
	f.get_32()
	var json_len := f.get_32()
	var kind := f.get_32()
	assert_eq(magic, 0x46546C67, "nombre magique glTF : " + path)
	assert_eq(version, 2)
	assert_eq(kind, 0x4E4F534A, "premier bloc JSON")
	return JSON.parse_string(f.get_buffer(json_len).get_string_from_utf8())


## Triangles des trois niveaux d'un .glb d'après son JSON (nœud MSFT_lod, puis ses ids).
func glb_triangles(g: Dictionary) -> Array:
	var lead := -1
	for i in range(g["nodes"].size()):
		if g["nodes"][i].has("extensions") and g["nodes"][i]["extensions"].has("MSFT_lod"):
			lead = i
	var ids: Array = [lead] + g["nodes"][lead]["extensions"]["MSFT_lod"]["ids"]
	var out := []
	for n in ids:
		var prim: Dictionary = g["meshes"][g["nodes"][int(n)]["mesh"]]["primitives"][0]
		out.append(int(g["accessors"][int(prim["indices"])]["count"]) / 3)
	return out
