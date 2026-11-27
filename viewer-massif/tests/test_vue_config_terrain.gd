## Tests de la mission 072 (écrits avec la vue, en plus des tests d'acceptation de la mission 069) : lecture du bloc `viewer` de
## config.yml, hauteur du sol, positions des semis, brin d'herbe.
extends "res://tests/support.gd"


func test_le_bloc_viewer_du_config_du_depot_se_lit() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var texte := FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml"))
	var r: Dictionary = C.parse_text(texte)
	assert_true(r["ok"], str(r["error"]))
	assert_eq(int(r["data"]["grass"]["max_instances"]), 200000)
	assert_eq(r["data"]["grass"]["color"], "#5b7f3a")
	assert_true(r["data"]["provisoire"])
	assert_eq(r["data"]["foliage"]["color_by_group"]["resineux"], "#2f5a3a")


func test_une_cle_manquante_du_bloc_viewer_est_nommee() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var r: Dictionary = C.parse_text("viewer:\n  provisoire: true\n  grass:\n    radius_m: 40\n")
	assert_false(r["ok"])
	assert_string_contains(r["error"], "viewer.")
	assert_false(C.parse_text("autre: 1\n")["ok"], "bloc viewer absent")


func test_le_sol_est_interpole_entre_centres_de_cellule() -> void:
	var T = need("res://scripts/terrain.gd")
	if T == null:
		return
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var z: Array = b["ground"]["z"]
	var o: float = b["origin"]["z"]
	# centre de la cellule (ligne 0, colonne 0) : x = 12,5 ; y = 487,5
	assert_almost_eq(T.height_at(b, 12.5, 487.5), float(z[0]) - o, 0.001)
	# milieu entre deux centres voisins d'une même ligne
	assert_almost_eq(T.height_at(b, 25.0, 487.5), (float(z[0]) + float(z[1])) / 2.0 - o, 0.001)
	# au bord du bloc : valeur du centre le plus proche, pas d'extrapolation
	assert_almost_eq(T.height_at(b, 0.0, 500.0), float(z[0]) - o, 0.001)
	# le nord est la ligne 0 : y = 12,5 est la dernière ligne
	assert_almost_eq(T.height_at(b, 12.5, 12.5), float(z[19 * 20]) - o, 0.001)


func test_le_maillage_du_terrain_couvre_le_bloc_dans_le_repere_de_godot() -> void:
	var T = need("res://scripts/terrain.gd")
	if T == null:
		return
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var box: AABB = (T.build_mesh(b) as Mesh).get_aabb()
	assert_almost_eq(box.position.x, 0.0, 0.01)
	assert_almost_eq(box.end.x, 500.0, 0.01)
	assert_almost_eq(box.position.z, -500.0, 0.01, "le nord est -z")
	assert_almost_eq(box.end.z, 0.0, 0.01)


func test_les_semis_restent_dans_leur_cellule_et_sont_deterministes() -> void:
	var S = need("res://scripts/seedlings.gd")
	if S == null:
		return
	var a: PackedVector2Array = S.positions("zone_m6", 5, 112.5, 87.5, 25.0, "09", 6)
	assert_eq(a.size(), 6)
	assert_true(a == S.positions("zone_m6", 5, 112.5, 87.5, 25.0, "09", 6))
	for v in a:
		assert_between(v.x, 100.0, 125.0)
		assert_between(v.y, 75.0, 100.0)


func test_le_brin_d_herbe_a_son_pied_en_y_zero_et_un_metre_de_haut() -> void:
	var V = need("res://scripts/massif_view.gd")
	if V == null:
		return
	var box: AABB = V.blade_mesh().get_aabb()
	assert_almost_eq(box.position.y, 0.0, 0.001)
	assert_almost_eq(box.end.y, 1.0, 0.001)
