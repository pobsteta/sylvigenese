## Mission 091 : la caméra se déplace et tourne au clavier seul (carte M6b « caméra figée vers le nord sans clavier »).
## Déplacement : W A S D, Q et E ; rotation : flèches, à la vitesse viewer.camera.key_turn_rad_s de config.yml, tangage borné par
## viewer.camera.pitch_limit_rad. Les fonctions testées sont pures (touches tenues -> direction, rotation) : aucune entrée réelle.
extends "res://tests/support.gd"

const CAM := "res://scripts/camera_fly.gd"


func test_les_touches_de_deplacement_donnent_la_direction_attendue() -> void:
	var C = need(CAM)
	if C == null:
		return
	assert_eq(C.move_direction({KEY_W: true}), Vector3(0, 0, -1), "W : devant (-z)")
	assert_eq(C.move_direction({KEY_S: true}), Vector3(0, 0, 1))
	assert_eq(C.move_direction({KEY_A: true}), Vector3(-1, 0, 0))
	assert_eq(C.move_direction({KEY_D: true}), Vector3(1, 0, 0))
	assert_eq(C.move_direction({KEY_E: true}), Vector3(0, 1, 0), "E monte")
	assert_eq(C.move_direction({KEY_Q: true}), Vector3(0, -1, 0), "Q descend")
	assert_eq(C.move_direction({KEY_W: true, KEY_S: true}), Vector3.ZERO, "deux sens opposés s'annulent")
	assert_eq(C.move_direction({}), Vector3.ZERO)


func test_les_fleches_tournent_la_tete_a_la_vitesse_de_config() -> void:
	var C = need(CAM)
	if C == null:
		return
	var limite := 1.5
	var g: Vector2 = C.turned(0.0, 0.0, {KEY_LEFT: true}, 1.2, limite, 0.5)
	assert_almost_eq(g.x, 0.6, 1e-6, "flèche gauche : +1,2 rad/s x 0,5 s")
	assert_almost_eq(g.y, 0.0, 1e-6)
	var d: Vector2 = C.turned(0.0, 0.0, {KEY_RIGHT: true}, 1.2, limite, 0.5)
	assert_almost_eq(d.x, -0.6, 1e-6)
	var h: Vector2 = C.turned(0.0, 0.0, {KEY_UP: true}, 1.2, limite, 0.5)
	assert_almost_eq(h.y, 0.6, 1e-6, "flèche haut : le regard se lève")
	var b: Vector2 = C.turned(0.0, 0.0, {KEY_DOWN: true}, 1.2, limite, 0.5)
	assert_almost_eq(b.y, -0.6, 1e-6)
	assert_eq(C.turned(0.3, 0.2, {}, 1.2, limite, 0.5), Vector2(0.3, 0.2), "aucune touche : rien ne bouge")


func test_le_tangage_reste_dans_la_limite_de_config() -> void:
	var C = need(CAM)
	if C == null:
		return
	var t: Vector2 = C.turned(0.0, 1.4, {KEY_UP: true}, 1.2, 1.5, 1.0)
	assert_almost_eq(t.y, 1.5, 1e-6, "borné à pitch_limit_rad")
	t = C.turned(0.0, -1.4, {KEY_DOWN: true}, 1.2, 1.5, 1.0)
	assert_almost_eq(t.y, -1.5, 1e-6)


func test_configure_lit_la_vitesse_de_rotation_dans_config() -> void:
	var C = need(CAM)
	var L = need("res://scripts/viewer_config.gd")
	if C == null or L == null:
		return
	var r: Dictionary = L.parse_text(FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml")))
	assert_true(r["ok"], str(r["error"]))
	var cam = C.new()
	cam.configure(r["data"]["camera"])
	assert_gt(cam.key_turn_rad_s, 0.0)
	assert_eq(cam.key_turn_rad_s, float(r["data"]["camera"]["key_turn_rad_s"]))
	cam.free()
