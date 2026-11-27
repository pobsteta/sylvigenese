## Mission 072, reprise du 26/11/2026 : (1) le bandeau nomme les modèles « non calé » d'après les extras des .glb et compte les
## arbres, sans supposer le groupe ; (2) les semis sont dessinés sous un plafond lu dans config.yml (viewer.seedlings.max_instances)
## et le disent quand il tronque ; les effectifs du bloc restent ceux de `massif/`.
extends "res://tests/support.gd"


func test_le_non_cale_est_nomme_et_compte_sans_supposer_le_groupe() -> void:
	var M = need("res://scripts/main.gd")
	if M == null:
		return
	var t: String = M.non_cale_text({"09_mature": 3, "62_old": 2}, 3)
	assert_string_contains(t, "5 arbre")
	assert_string_contains(t, "09_mature (3)")
	assert_string_contains(t, "62_old (2)")
	assert_false(t.to_lower().contains("résineux"), "le groupe n'est pas supposé")


func test_la_cle_du_plafond_des_semis_est_exigee() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var texte := FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml"))
	var ok: Dictionary = C.parse_text(texte)
	assert_true(ok["ok"], str(ok["error"]))
	assert_gt(int(ok["data"]["seedlings"]["max_instances"]), 0)
	var sans: Dictionary = C.parse_text(texte.replace("max_instances: 20000   #", "autre: 1   #"))
	assert_false(sans["ok"])
	assert_string_contains(sans["error"], "seedlings.max_instances")


func _copy(src: String, dst: String) -> void:
	DirAccess.make_dir_recursive_absolute(dst.get_base_dir())
	var f := FileAccess.open(dst, FileAccess.WRITE)
	f.store_buffer(FileAccess.get_file_as_bytes(src))
	f.close()


## Zone en mode cohortes (semis 40/ha, 0,5 m) dans user://, config.yml avec le plafond demandé.
func _zone_cohortes(nom: String, plafond: int) -> String:
	var src := zone_path()
	var dst := ProjectSettings.globalize_path("user://" + nom)
	for f in ["massif/index.json", "assets/trees/09_mature.glb", "assets/trees/09_old.glb", "assets/trees/generique_resineux.glb", "zone.yml"]:
		_copy(src + "/" + f, dst + "/" + f)
	_copy(src + "/assets/trees/09_mature.glb", dst + "/assets/trees/09_young.glb")
	var b := read_json(src + "/massif/2022/t_700000_6500000.json")
	b["seedlings_simulated"] = true
	b["provisoire"] = false
	for c in b["cells"]:
		c["seedlings"] = [{"species": "09", "seedlings_ha": 40.0, "h_mean_m": 0.5}]
	DirAccess.make_dir_recursive_absolute(dst + "/massif/2022")
	var f2 := FileAccess.open(dst + "/massif/2022/t_700000_6500000.json", FileAccess.WRITE)
	f2.store_string(JSON.stringify(b))
	f2.close()
	var cfg := FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml"))
	cfg = cfg.replace("max_instances: 20000   #", "max_instances: %d   #" % plafond)
	var f3 := FileAccess.open(dst + "/config.yml", FileAccess.WRITE)
	f3.store_string(cfg)
	f3.close()
	return dst


func _selftest(zone: String) -> Dictionary:
	var out := []
	var code := OS.execute(OS.get_executable_path(), PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"), "--", "--selftest", "--zone", zone, "--x", "700250", "--y", "6500250", "--year", "2022"]), out, true)
	var texte := ""
	for l in out:
		texte += str(l)
	var comptes := {}
	for ligne in texte.split("\n"):
		if ligne.begins_with("SELFTEST "):
			comptes = JSON.parse_string(ligne.substr(9))
	return {"code": code, "texte": texte, "comptes": comptes}


func test_les_semis_sont_plafonnes_et_l_ecran_le_dit() -> void:
	var r := _selftest(_zone_cohortes("zone_cohortes_plafond", 10))
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("seedlings", -1)), 10, "le plafond de config.yml tronque")
	assert_true(r["comptes"].get("seedlings_truncated", false))


func test_sous_le_plafond_rien_n_est_tronque() -> void:
	var r := _selftest(_zone_cohortes("zone_cohortes_large", 100000))
	assert_eq(r["code"], 0, r["texte"])
	assert_gt(int(r["comptes"].get("seedlings", -1)), 10)
	assert_false(r["comptes"].get("seedlings_truncated", true))
