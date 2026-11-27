## Repère (plan T6) : massif/ est x est, y nord, z haut, relatif à l'origine du bloc (EPSG:2154, NGF-IGN69) ;
## Godot est x est, y haut, z = -nord (le nord est devant). Piège connu du projet : x et y inversés (« la Somalie »).
## Quatre arbres aux extrémités nord, sud, est, ouest, aux coordonnées asymétriques ; aller et retour exact à 1 mm.
extends "res://tests/support.gd"

const S := "res://scripts/frame.gd"
const ORIGIN := {"x": 700000.0, "y": 6500000.0, "z": 340.0}
# nord, sud, est, ouest : (x, y, z) relatifs au bloc, asymétriques
const POINTS := {"nord": [260.0, 470.0, 3.2], "sud": [240.0, 30.0, 4.1], "est": [475.0, 230.0, 5.0], "ouest": [25.0, 270.0, 6.5]}


func test_bloc_vers_godot_est_x_z_moins_y() -> void:
	var F = need(S)
	if F == null:
		return
	for nom in POINTS:
		var p: Array = POINTS[nom]
		var g: Vector3 = F.block_to_godot(p[0], p[1], p[2])
		assert_almost_eq(g.x, p[0], 0.001, nom + " : x est reste x")
		assert_almost_eq(g.y, p[2], 0.001, nom + " : l'altitude est y (haut)")
		assert_almost_eq(g.z, -p[1], 0.001, nom + " : le nord est -z, pas +z, pas x")


func test_le_nord_est_devant_et_l_est_a_droite() -> void:
	var F = need(S)
	if F == null:
		return
	var n: Vector3 = F.block_to_godot(POINTS["nord"][0], POINTS["nord"][1], POINTS["nord"][2])
	var s: Vector3 = F.block_to_godot(POINTS["sud"][0], POINTS["sud"][1], POINTS["sud"][2])
	var e: Vector3 = F.block_to_godot(POINTS["est"][0], POINTS["est"][1], POINTS["est"][2])
	var w: Vector3 = F.block_to_godot(POINTS["ouest"][0], POINTS["ouest"][1], POINTS["ouest"][2])
	assert_lt(n.z, s.z, "le nord est devant (-Z de Godot) le sud")
	assert_gt(e.x, w.x, "l'est est à droite (+X) de l'ouest")


func test_lambert93_vers_godot_relatif_a_l_origine_du_bloc() -> void:
	var F = need(S)
	if F == null:
		return
	for nom in POINTS:
		var p: Array = POINTS[nom]
		var g: Vector3 = F.lambert_to_godot(ORIGIN["x"] + p[0], ORIGIN["y"] + p[1], ORIGIN["z"] + p[2], ORIGIN)
		assert_almost_eq(g.x, p[0], 0.001, nom)
		assert_almost_eq(g.y, p[2], 0.001, nom)
		assert_almost_eq(g.z, -p[1], 0.001, nom)


func test_aller_et_retour_a_un_millimetre() -> void:
	var F = need(S)
	if F == null:
		return
	for nom in POINTS:
		var p: Array = POINTS[nom]
		var X: float = ORIGIN["x"] + p[0]
		var Y: float = ORIGIN["y"] + p[1]
		var Z: float = ORIGIN["z"] + p[2]
		var g: Vector3 = F.lambert_to_godot(X, Y, Z, ORIGIN)
		var back: Vector3 = F.godot_to_lambert(g, ORIGIN)
		assert_almost_eq(back.x, X, 0.001, nom + " x")
		assert_almost_eq(back.y, Y, 0.001, nom + " y")
		assert_almost_eq(back.z, Z, 0.001, nom + " z")
		var b: Vector3 = F.godot_to_block(F.block_to_godot(p[0], p[1], p[2]))
		assert_almost_eq(b.x, p[0], 0.001)
		assert_almost_eq(b.y, p[1], 0.001)
		assert_almost_eq(b.z, p[2], 0.001)


func test_les_quatre_arbres_du_bloc_d_essai_tombent_au_bon_endroit() -> void:
	var F = need(S)
	if F == null:
		return
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var par_id := {}
	for t in b["trees"]:
		par_id[t["tree_id"]] = F.block_to_godot(t["x"], t["y"], t["z"])
	assert_lt(par_id["n01"].z, par_id["s01"].z, "arbre du nord devant arbre du sud")
	assert_gt(par_id["e01"].x, par_id["w01"].x, "arbre de l'est à droite de l'arbre de l'ouest")
	assert_almost_eq(par_id["n01"].z, -470.0, 0.001)
	assert_almost_eq(par_id["e01"].x, 475.0, 0.001)
