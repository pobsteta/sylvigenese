## Lecture de massif/ (plan T5, T7 ; spec §2) : index, bloc, année, point, blocs autour d'une position.
## Clé manquante, schema_version inconnu, année absente, point hors emprise, zone sans massif/ : erreur lisible, aucune
## valeur par défaut, jamais l'année voisine.
extends "res://tests/support.gd"

const S := "res://scripts/zone_reader.gd"
const BLOC := "/massif/2022/t_700000_6500000.json"


func _bloc_modifie(nom: String, modif: Callable) -> String:
	var b := read_json(zone_path() + BLOC)
	modif.call(b)
	var chemin := "user://" + nom + ".json"
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_string(JSON.stringify(b))
	f.close()
	return ProjectSettings.globalize_path(chemin)


func _index_2x2() -> Dictionary:
	var blocs := []
	for x in [700000, 700500]:
		for y in [6500000, 6500500]:
			blocs.append({"block_id": "t_%d_%d" % [x, y], "file": "2022/t_%d_%d.json" % [x, y], "sw": {"x": float(x), "y": float(y)}, "size_m": 500, "trees": 1})
	return {"years": [{"year": 2022, "trees": 4, "blocks": blocs}], "block_size_m": 500}


func test_l_index_se_lit() -> void:
	var Z = need(S)
	if Z == null:
		return
	var r: Dictionary = Z.read_index(zone_path())
	assert_true(r.get("ok", false), str(r))
	assert_eq(r["data"]["zone"], "zone_m6")
	assert_eq(r["data"]["years"].size(), 1)
	assert_eq(int(r["data"]["years"][0]["year"]), 2022)


func test_un_bloc_se_lit_avec_ses_arbres_son_sol_et_ses_cellules() -> void:
	var Z = need(S)
	if Z == null:
		return
	var r: Dictionary = Z.read_block(zone_path() + BLOC)
	assert_true(r.get("ok", false), str(r))
	assert_eq(r["data"]["trees"].size(), 4)
	assert_eq(r["data"]["cells"].size(), 400)
	assert_eq(r["data"]["ground"]["z"].size(), 400)


func test_une_cle_manquante_est_une_erreur_qui_la_nomme() -> void:
	var Z = need(S)
	if Z == null:
		return
	for cle in ["origin", "trees", "ground", "cells", "seedlings_simulated", "mentions", "provisoire", "vertical_datum"]:
		var chemin := _bloc_modifie("sans_" + cle, func(b): b.erase(cle))
		var r: Dictionary = Z.read_block(chemin)
		assert_false(r.get("ok", true), "sans %s : le bloc ne doit pas être lu" % cle)
		assert_string_contains(str(r.get("error", "")), cle)


func test_un_arbre_sans_stade_est_refuse() -> void:
	var Z = need(S)
	if Z == null:
		return
	var chemin := _bloc_modifie("arbre_sans_stade", func(b): b["trees"][0].erase("stage"))
	var r: Dictionary = Z.read_block(chemin)
	assert_false(r.get("ok", true))
	assert_string_contains(str(r.get("error", "")), "stage")


func test_une_version_de_schema_inconnue_est_refusee() -> void:
	var Z = need(S)
	if Z == null:
		return
	var chemin := _bloc_modifie("v9", func(b): b["schema_version"] = 9)
	var r: Dictionary = Z.read_block(chemin)
	assert_false(r.get("ok", true))
	assert_string_contains(str(r.get("error", "")), "schema_version")
	assert_string_contains(str(r.get("error", "")), "9")


func test_un_fichier_absent_ou_pas_du_json_est_une_erreur() -> void:
	var Z = need(S)
	if Z == null:
		return
	assert_false(Z.read_block(zone_path() + "/massif/2022/n_existe_pas.json").get("ok", true))
	var chemin := "user://pas_du_json.json"
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_string("{pas du json")
	f.close()
	assert_false(Z.read_block(ProjectSettings.globalize_path(chemin)).get("ok", true))


func test_une_zone_sans_massif_est_une_erreur_qui_le_dit() -> void:
	var Z = need(S)
	if Z == null:
		return
	var r: Dictionary = Z.read_index(ProjectSettings.globalize_path("res://tests"))
	assert_false(r.get("ok", true))
	assert_string_contains(str(r.get("error", "")), "massif")


func test_le_bloc_d_un_point_et_d_une_annee() -> void:
	var Z = need(S)
	if Z == null:
		return
	var idx: Dictionary = Z.read_index(zone_path())["data"]
	var r: Dictionary = Z.resolve(idx, 700250.0, 6500250.0, 2022)
	assert_true(r.get("ok", false), str(r))
	assert_eq(r["block_id"], "t_700000_6500000")
	assert_eq(r["file"], "2022/t_700000_6500000.json")


func test_une_annee_absente_donne_les_annees_disponibles_jamais_la_voisine() -> void:
	var Z = need(S)
	if Z == null:
		return
	var idx: Dictionary = Z.read_index(zone_path())["data"]
	for an in [2021, 2023, 2032]:
		var r: Dictionary = Z.resolve(idx, 700250.0, 6500250.0, an)
		assert_false(r.get("ok", true), "l'année %d n'existe pas : pas d'année voisine" % an)
		assert_false(r.has("block_id") and str(r.get("block_id", "")) != "", "aucun bloc ne doit être rendu")
		assert_string_contains(str(r.get("error", "")), "2022", "le message donne les années disponibles")


func test_un_point_hors_emprise_donne_l_emprise() -> void:
	var Z = need(S)
	if Z == null:
		return
	var idx: Dictionary = Z.read_index(zone_path())["data"]
	for p in [[701000.0, 6500250.0], [699999.0, 6500250.0], [700250.0, 6500501.0], [700250.0, 6499999.0]]:
		var r: Dictionary = Z.resolve(idx, p[0], p[1], 2022)
		assert_false(r.get("ok", true), str(p))
		var e := str(r.get("error", ""))
		assert_string_contains(e, "700000", "le message donne l'emprise (ouest)")
		assert_string_contains(e, "6500000", "le message donne l'emprise (sud)")


func test_x_et_y_ne_sont_pas_echanges() -> void:
	var Z = need(S)
	if Z == null:
		return
	var idx: Dictionary = Z.read_index(zone_path())["data"]
	# (x, y) échangés tomberaient très loin de la zone
	var r: Dictionary = Z.resolve(idx, 6500250.0, 700250.0, 2022)
	assert_false(r.get("ok", true), "x = 6 500 250 et y = 700 250 sont hors de la zone")


func test_blocs_autour_d_une_position_rayon_et_bord_de_zone() -> void:
	var Z = need(S)
	if Z == null:
		return
	var idx := _index_2x2()
	var cas := [
		[700250.0, 6500250.0, 10.0, ["t_700000_6500000"]],
		[700500.0, 6500500.0, 10.0, ["t_700000_6500000", "t_700000_6500500", "t_700500_6500000", "t_700500_6500500"]],
		[700250.0, 6500250.0, 300.0, ["t_700000_6500000", "t_700000_6500500", "t_700500_6500000"]],
		[700010.0, 6500010.0, 100.0, ["t_700000_6500000"]],
		[700990.0, 6500990.0, 100.0, ["t_700500_6500500"]],
	]
	for c in cas:
		var r: Array = Z.blocks_around(idx, 2022, c[0], c[1], c[2])
		var ids := []
		for b in r:
			ids.append(str(b))
		ids.sort()
		var attendu: Array = c[3].duplicate()
		attendu.sort()
		assert_eq(ids, attendu, "autour de (%s, %s) rayon %s" % [c[0], c[1], c[2]])
