## Mission 077 (préparation de M6b) : les constantes d'affichage de la vue viennent du bloc `viewer` de config.yml, sans valeur
## par défaut dans les scripts. Une clé absente arrête la vue en code 3 (jamais une valeur devinée) ; le champ de vision passé
## au chargeur convertit les seuils d'écran en distances ; des semis dessinés par un modèle générique sont dits à l'écran
## (aucune largeur de houppier n'existe pour un semis : échelle de la hauteur, rien d'inventé).
## Le test qui interdit le retour d'un littéral d'affichage dans les scripts est en pytest : contracts/tests/test_m6b_affichage.py.
extends "res://tests/support.gd"


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


func _ecrire(chemin: String, octets: PackedByteArray) -> void:
	DirAccess.make_dir_recursive_absolute(chemin.get_base_dir())
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_buffer(octets)
	f.close()


func _copie(source: String, nom: String) -> String:
	var src := zone_path(source)
	var dst := ProjectSettings.globalize_path("user://" + nom)
	for f in ["massif/index.json", "massif/2022/t_700000_6500000.json", "zone.yml"]:
		_ecrire(dst + "/" + f, FileAccess.get_file_as_bytes(src + "/" + f))
	for f in DirAccess.get_files_at(src + "/assets/trees"):
		_ecrire(dst + "/assets/trees/" + f, FileAccess.get_file_as_bytes(src + "/assets/trees/" + f))
	return dst


## Écrit des semis (« 09 », 160 par hectare, soit 10 par cellule) dans toutes les cellules du bloc de 2022 de la copie.
func _avec_semis(zone: String) -> void:
	var chemin := zone + "/massif/2022/t_700000_6500000.json"
	var b := read_json(chemin)
	b["seedlings_simulated"] = true
	for c in b["cells"]:
		c["seedlings"] = [{"species": "09", "seedlings_ha": 160.0, "h_mean_m": 0.5}]
	_ecrire(chemin, JSON.stringify(b).to_utf8_buffer())


func _config_du_depot() -> String:
	return FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml"))


func test_le_config_du_depot_porte_toutes_les_cles_exigees_par_la_vue() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var r: Dictionary = C.parse_text(_config_du_depot())
	assert_true(r["ok"], str(r["error"]))
	assert_eq(float(r["data"]["camera"]["eye_height_m"]), 1.7)
	assert_eq(float(r["data"]["camera"]["fov_deg"]), 75.0)
	assert_eq(float(r["data"]["view"]["radius_m"]), 1000.0)
	assert_eq(r["data"]["ground"]["color"], "#5c543d")


func test_une_cle_d_affichage_retiree_est_nommee() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	# clés dont le nom est unique dans le bloc : la ligne retirée est la seule de ce nom
	for chemin in ["camera.eye_height_m", "camera.speed_m_s", "camera.fast_factor", "camera.mouse_sensitivity", "camera.pitch_limit_rad", "camera.key_turn_rad_s", "seedlings.generic_radius_over_height",
			"sun.elevation_deg", "hud.title_font_size", "hud.state_height_px", "hud.margin_px", "grass.wind_noise_frequency", "lod.chunk_m"]:
		var feuille := str(chemin).get_slice(".", 1)
		var lignes := []
		var retirees := 0
		for l in _config_du_depot().split("\n"):
			if l.strip_edges().begins_with(feuille + ":"):
				retirees += 1
				continue
			lignes.append(l)
		assert_eq(retirees, 1, "la clé « %s » est unique dans config.yml" % feuille)
		var r: Dictionary = C.parse_text("\n".join(lignes))
		assert_false(r["ok"], "sans « %s » le bloc est refusé" % chemin)
		assert_string_contains(str(r["error"]), "viewer." + str(chemin))


func test_sans_champ_de_vision_la_vue_s_arrete_en_code_3() -> void:
	var zone := _copie("zone_m6", "zone_sans_fov")
	var texte := _config_du_depot().replace("    fov_deg: 75", "")
	_ecrire(zone + "/config.yml", texte.to_utf8_buffer())
	var r := _selftest(zone)
	assert_eq(r["code"], 3, r["texte"])
	assert_string_contains(r["texte"], "viewer.camera.fov_deg")


func test_le_chargeur_refuse_un_champ_de_vision_hors_de_0_a_180() -> void:
	var L = need("res://scripts/tree_model_loader.gd")
	if L == null:
		return
	for fov in [0.0, -5.0, 180.0]:
		var r: Dictionary = L.load_glb(zone_path() + "/assets/trees/09_mature.glb", fov)
		assert_false(r["ok"], "fov = %s refusé" % str(fov))
		assert_string_contains(str(r["error"]), "fov_deg")


func test_un_champ_de_vision_plus_large_rapproche_les_distances_de_niveau_de_detail() -> void:
	var L = need("res://scripts/tree_model_loader.gd")
	if L == null:
		return
	var etroit: Dictionary = L.load_glb(zone_path() + "/assets/trees/09_mature.glb", 40.0)
	var large: Dictionary = L.load_glb(zone_path() + "/assets/trees/09_mature.glb", 100.0)
	assert_true(etroit["ok"] and large["ok"])
	assert_gt(float(etroit["levels"][0]["visibility_range_end"]), float(large["levels"][0]["visibility_range_end"]))
	# d = H / (2 tan(fov/2) c) : le rapport des distances est celui des tangentes
	var attendu := tan(deg_to_rad(100.0) / 2.0) / tan(deg_to_rad(40.0) / 2.0)
	assert_almost_eq(float(etroit["levels"][0]["visibility_range_end"]) / float(large["levels"][0]["visibility_range_end"]), attendu, 0.001)


func test_des_semis_dessines_par_un_generique_sont_comptes_et_la_mention_est_dite() -> void:
	var zone := _copie("zone_m6_stade_manquant", "zone_semis_generique")
	_avec_semis(zone)
	var r := _selftest(zone)
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("seedling_generic_species", -1)), 1, "le modèle young du hêtre est le générique")
	assert_gt(int(r["comptes"].get("seedlings", 0)), 0, "des semis sont dessinés")
	var S = need("res://scripts/seedlings.gd")
	if S == null:
		return
	var note: String = S.generic_note(0.25)
	assert_string_contains(note, "semis génériques")
	assert_string_contains(note, "largeur non connue")
	assert_string_contains(note, "rayon = 0,25 x la hauteur")
	assert_string_contains(note, "illustration, non mesurée")
	assert_string_contains(note, "sans source")   # mission 092 : comme config.yml, la note ne laisse pas croire à une valeur sourcée


## Mission 092 : la vérification de 1 m de haut d'un modèle générique vaut aussi pour les semis (comme pour les arbres).
func test_un_generique_de_semis_qui_ne_mesure_pas_1_m_est_refuse_en_code_5_et_nomme() -> void:
	var zone := _copie("zone_m6_stade_manquant", "zone_semis_generique_haut")
	_avec_semis(zone)
	# le fichier du générique feuillu (young du hêtre) devient un modèle de ~12 m : arbre y01 le dessine sans erreur (extras sans
	# « generique »), mais l'index le dit générique : la vérification des semis le refuse
	_ecrire(zone + "/assets/trees/generique_feuillu.glb", FileAccess.get_file_as_bytes(zone_path("zone_m6_stade_manquant") + "/assets/trees/09_mature.glb"))
	var r := _selftest(zone)
	assert_eq(r["code"], 5, r["texte"])
	assert_string_contains(r["texte"], "semis de l'essence 09")
	assert_string_contains(r["texte"], "un modèle générique mesure 1 m")


func test_la_verification_de_taille_du_generique_est_la_meme_pour_arbres_et_semis() -> void:
	var V = need("res://scripts/massif_view.gd")
	if V == null:
		return
	assert_eq(V.generic_size_error(1.0, "x"), "")
	assert_eq(V.generic_size_error(1.005, "x"), "", "dans la tolérance de 1 cm")
	var e: String = V.generic_size_error(12.0, "semis de l'essence 09")
	assert_string_contains(e, "semis de l'essence 09")
	assert_string_contains(e, "12.000 m")
	var arbre: Dictionary = V.instance_scale({"generique": true}, 12.0, 12.0, 4.0, "semis de l'essence 09")
	assert_eq(arbre["error"], e, "même message pour un arbre")


## Mission 091 : un semis générique est mis à (r, h, r), r = h x rapport de config.yml (le bloc ne donne pas de cw) ; un semis du
## générateur garde sa forme (échelle uniforme h / hauteur du modèle).
func test_l_echelle_d_un_semis_generique_est_r_h_r_et_celle_d_un_exemplaire_est_uniforme() -> void:
	var S = need("res://scripts/seedlings.gd")
	if S == null:
		return
	var g: Vector3 = S.scale(true, 0.5, 1.0, 0.25)
	assert_almost_eq(g.y, 0.5, 1e-6, "hauteur = h (modèle générique de 1 m)")
	assert_almost_eq(g.x, 0.125, 1e-6, "rayon = h x rapport = 0,5 x 0,25")
	assert_almost_eq(g.z, g.x, 1e-6)
	var e: Vector3 = S.scale(false, 0.5, 2.0, 0.25)
	assert_eq(e, Vector3(0.25, 0.25, 0.25), "exemplaire : h / hauteur du modèle sur les trois axes, le rapport ne sert pas")


func test_le_rapport_des_semis_generiques_vient_de_config_yml_et_est_marque_non_mesure() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var texte := _config_du_depot()
	var r: Dictionary = C.parse_text(texte)
	assert_true(r["ok"], str(r["error"]))
	var rapport := float(r["data"]["seedlings"]["generic_radius_over_height"])
	assert_gt(rapport, 0.0)
	for l in texte.split("\n"):
		if l.strip_edges().begins_with("generic_radius_over_height:"):
			assert_string_contains(l, "non mesurée")
			assert_string_contains(l, "SANS SOURCE")


func test_des_semis_dessines_par_un_exemplaire_ne_disent_pas_generique() -> void:
	var zone := _copie("zone_m6", "zone_semis_exemplaire")
	_avec_semis(zone)
	var r := _selftest(zone)
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("seedling_generic_species", -1)), 0)
	assert_gt(int(r["comptes"].get("seedlings", 0)), 0)


func test_un_commentaire_de_fin_de_ligne_n_est_pas_une_valeur() -> void:
	var C = need("res://scripts/viewer_config.gd")
	if C == null:
		return
	var r: Dictionary = C.parse_text(_config_du_depot())
	assert_true(r["ok"], str(r["error"]))
	assert_eq(typeof(r["data"]["seedlings"]["max_instances"]), TYPE_FLOAT, "20000 est un nombre, pas « 20000   # plafond… »")
	assert_eq(float(r["data"]["seedlings"]["max_instances"]), 20000.0)
	assert_eq(typeof(r["data"]["camera"]["fov_deg"]), TYPE_FLOAT)
	assert_eq(r["data"]["grass"]["color"], "#5b7f3a", "un # entre guillemets reste dans la valeur")
	assert_eq(typeof(r["data"]["view"]), TYPE_DICTIONARY, "« view:   # commentaire » ouvre une carte")
