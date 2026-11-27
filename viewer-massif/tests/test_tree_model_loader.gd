## Chargement à l'exécution d'un .glb (plan T13) : les .glb sont dans data/<zone>/assets/trees/, hors res:// ; la vue les
## charge par GLTFDocument.append_from_file puis generate_scene ; Godot n'applique pas MSFT_lod : notre chargeur lit l'extension
## et pose les niveaux (visibility_range). Fixture : tests/fixtures/zone_m6/assets/trees/*.glb (écrits par make_zone_m6.py,
## indépendamment de `assets`). Si SYLVIGENESE_M6_TREES_DIR est posée (CI, mission 073), les .glb produits par `assets`
## passent par les mêmes contrôles.
extends "res://tests/support.gd"

const S := "res://scripts/tree_model_loader.gd"
const FIXTURE_GLB := ["09_mature", "09_old", "generique_resineux"]


func _chemins() -> Array:
	var out := []
	for n in FIXTURE_GLB:
		out.append(zone_path() + "/assets/trees/" + n + ".glb")
	var d := OS.get_environment("SYLVIGENESE_M6_TREES_DIR")
	if d != "":
		for f in DirAccess.get_files_at(d):
			if f.ends_with(".glb"):
				out.append(d.path_join(f))
	return out


func _triangles(mesh: Mesh) -> int:
	var n := 0
	for s in range(mesh.get_surface_count()):
		var a := mesh.surface_get_arrays(s)
		n += (a[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
	return n


func test_un_glb_se_charge_a_l_execution_avec_trois_niveaux() -> void:
	var L = need(S)
	if L == null:
		return
	for chemin in _chemins():
		var r: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
		assert_true(r.get("ok", false), "%s : %s" % [chemin, r.get("error", "")])
		if not r.get("ok", false):
			continue
		assert_eq(r["levels"].size(), 3, chemin)
		var attendu := glb_triangles(glb_json(chemin))
		for k in range(3):
			var m: Mesh = r["levels"][k]["mesh"]
			assert_not_null(m, "LOD%d sans maillage" % k)
			assert_eq(_triangles(m), attendu[k], "%s LOD%d : triangles du .glb" % [chemin, k])
			assert_eq(int(r["levels"][k]["triangles"]), attendu[k])
		assert_gt(attendu[0], attendu[1])
		assert_gt(attendu[1], attendu[2])


func test_lod0_va_de_zero_a_H_ref_en_y_et_la_cime_va_vers_moins_z() -> void:
	var L = need(S)
	if L == null:
		return
	for chemin in _chemins():
		var r: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
		if not r.get("ok", false):
			fail_test("%s : %s" % [chemin, r.get("error", "")])
			continue
		var h_ref := float(glb_json(chemin).get("extras", {}).get("H_ref_m", 0.0))
		var box: AABB = (r["levels"][0]["mesh"] as Mesh).get_aabb()
		assert_almost_eq(box.position.y, 0.0, 0.01 * maxf(h_ref, 1.0), chemin + " : base en y = 0")
		if h_ref > 0.0:
			assert_almost_eq(box.end.y, h_ref, 0.01 * h_ref, chemin + " : sommet de LOD0 = H_ref_m à 1 %")
	# l'arbre d'essai penche vers l'est (+x) et le nord du générateur (-z de glTF) : le chargeur ne retourne rien
	var r2: Dictionary = L.load_glb(zone_path() + "/assets/trees/09_mature.glb", FOV_DEG_ESSAI)
	if r2.get("ok", false):
		var b2: AABB = (r2["levels"][0]["mesh"] as Mesh).get_aabb()
		assert_lt(b2.position.z, -2.0, "la cime est au nord : -z")
		assert_lt(b2.end.z, 1.0, "rien au sud")
		assert_gt(b2.end.x, 2.5, "la cime est à l'est : +x")


func test_les_extras_du_glb_sont_rendus_tels_quels() -> void:
	var L = need(S)
	if L == null:
		return
	var r: Dictionary = L.load_glb(zone_path() + "/assets/trees/09_mature.glb", FOV_DEG_ESSAI)
	assert_true(r.get("ok", false), str(r.get("error", "")))
	assert_eq(r["extras"]["species"], "09")
	assert_eq(r["extras"]["stage"], "mature")
	assert_true(r["extras"]["synthetique"])
	assert_true(r["extras"]["provisoire"])
	var g: Dictionary = L.load_glb(zone_path() + "/assets/trees/generique_resineux.glb", FOV_DEG_ESSAI)
	assert_true(g.get("ok", false), str(g.get("error", "")))
	assert_true(g["extras"]["generique"], "le générique est signalé")


func test_les_visibility_range_sont_poses_d_apres_msft_lod() -> void:
	var L = need(S)
	if L == null:
		return
	for chemin in _chemins():
		var r: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
		if not r.get("ok", false):
			fail_test("%s : %s" % [chemin, r.get("error", "")])
			continue
		var lv: Array = r["levels"]
		assert_almost_eq(float(lv[0]["visibility_range_begin"]), 0.0, 0.0001, "LOD0 visible dès la caméra")
		assert_gt(float(lv[0]["visibility_range_end"]), 0.0)
		assert_gt(float(lv[1]["visibility_range_begin"]), 0.0)
		assert_gt(float(lv[2]["visibility_range_begin"]), float(lv[1]["visibility_range_begin"]), "niveaux de plus en plus loin")
		assert_gt(float(lv[1]["visibility_range_end"]), float(lv[1]["visibility_range_begin"]))
		assert_almost_eq(float(lv[2]["visibility_range_end"]), 0.0, 0.0001, "LOD2 jusqu'à l'infini (0 = sans fin)")
		# les niveaux se recouvrent d'au plus la marge de fondu de config.yml (viewer.lod.fade_margin_m = 5 m)
		assert_almost_eq(float(lv[1]["visibility_range_begin"]), float(lv[0]["visibility_range_end"]), 5.001, chemin)
		assert_almost_eq(float(lv[2]["visibility_range_begin"]), float(lv[1]["visibility_range_end"]), 5.001, chemin)


func test_un_glb_tronque_ou_absent_est_une_erreur_lisible() -> void:
	var L = need(S)
	if L == null:
		return
	assert_false(L.load_glb(zone_path() + "/assets/trees/n_existe_pas.glb", FOV_DEG_ESSAI).get("ok", true))
	var src := FileAccess.get_file_as_bytes(zone_path() + "/assets/trees/09_mature.glb")
	var chemin := "user://tronque.glb"
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_buffer(src.slice(0, 200))
	f.close()
	var r: Dictionary = L.load_glb(ProjectSettings.globalize_path(chemin), FOV_DEG_ESSAI)
	assert_false(r.get("ok", true), "un .glb tronqué ne doit pas être accepté")
	assert_ne(str(r.get("error", "")), "")


func test_un_glb_sans_msft_lod_est_refuse() -> void:
	var L = need(S)
	if L == null:
		return
	var src := FileAccess.get_file_as_bytes(zone_path() + "/assets/trees/09_mature.glb")
	var json_len := int(src.decode_u32(12))
	var js := src.slice(20, 20 + json_len).get_string_from_utf8().replace("MSFT_lod", "XSFT_lod").to_utf8_buffer()
	assert_eq(js.size(), json_len, "même longueur : le fichier reste un .glb valide")
	var chemin := "user://sans_lod.glb"
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_buffer(src.slice(0, 20))
	f.store_buffer(js)
	f.store_buffer(src.slice(20 + json_len))
	f.close()
	var r: Dictionary = L.load_glb(ProjectSettings.globalize_path(chemin), FOV_DEG_ESSAI)
	assert_false(r.get("ok", true), "trois niveaux exigés : pas de repli silencieux sur un seul")
