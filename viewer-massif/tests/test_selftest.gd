## `--selftest` (plan T9, T14 ; mission F) : la vue charge la zone, bâtit la scène, écrit des comptes et sort à 0 ; sans GPU.
## Le test relance Godot lui-même (OS.get_executable_path) sur la zone d'essai : même commande que celle de la fiche web
## (`--zone <dossier> --x <X> --y <Y> --year <A>`) plus `--selftest`. Sortie exigée : une ligne `SELFTEST {json}` sur la sortie
## standard, avec les clés entières blocks, trees, generic_trees, grass_instances, seedlings et le booléen truncated.
## Un refus (année absente, point hors emprise, zone sans massif/) sort avec un code non nul et un message qui donne les
## années ou l'emprise : jamais l'année voisine.
extends "res://tests/support.gd"


func _lancer(zone: String, x: float, y: float, year: int, extra_moteur: Array = [], selftest: bool = true) -> Dictionary:
	var args := ["--headless", "--path", ProjectSettings.globalize_path("res://")]
	args.append_array(extra_moteur)
	args.append("--")
	if selftest:
		args.append("--selftest")
	args.append_array(["--zone", zone, "--x", str(x), "--y", str(y), "--year", str(year)])
	var out := []
	var code := OS.execute(OS.get_executable_path(), PackedStringArray(args), out, true)
	var texte := ""
	for l in out:
		texte += str(l)
	var comptes := {}
	for ligne in texte.split("\n"):
		if ligne.begins_with("SELFTEST "):
			var j = JSON.parse_string(ligne.substr(9))
			if typeof(j) == TYPE_DICTIONARY:
				comptes = j
	return {"code": code, "texte": texte, "comptes": comptes}


func test_selftest_sort_a_zero_et_ecrit_les_comptes_de_la_zone_d_essai() -> void:
	var r := _lancer(zone_path(), 700250.0, 6500250.0, 2022)
	assert_eq(r["code"], 0, r["texte"])
	var c: Dictionary = r["comptes"]
	assert_false(c.is_empty(), "ligne « SELFTEST {json} » absente :\n" + r["texte"])
	assert_eq(int(c.get("blocks", -1)), 1)
	assert_eq(int(c.get("trees", -1)), 4)
	assert_eq(int(c.get("generic_trees", -1)), 1, "62 est dessiné par le générique, compté")
	assert_gt(int(c.get("grass_instances", -1)), 0, "couvert herbacé 0,3 : de l'herbe autour de la caméra")
	assert_le(int(c.get("grass_instances", -1)), 200000, "plafond de config.yml (viewer.grass.max_instances)")
	assert_eq(int(c.get("seedlings", -1)), 0, "ifn_direct : aucun semis dessiné")


func test_selftest_en_rendu_compatibility_sort_a_zero() -> void:
	var r := _lancer(zone_path(), 700250.0, 6500250.0, 2022, ["--rendering-method", "gl_compatibility"])
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("trees", -1)), 4)


func test_selftest_deux_fois_les_memes_comptes() -> void:
	var a := _lancer(zone_path(), 700250.0, 6500250.0, 2022)
	var b := _lancer(zone_path(), 700250.0, 6500250.0, 2022)
	assert_eq(a["code"], 0, a["texte"])
	assert_eq(a["comptes"], b["comptes"], "herbe et semis par hachage déterministe")


func test_couvert_nul_pas_d_herbe() -> void:
	var r := _lancer(zone_path("zone_m6_sans_herbe"), 700250.0, 6500250.0, 2022)
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("grass_instances", -1)), 0, "herb_cover = 0 partout : herbe vide")
	assert_eq(int(r["comptes"].get("trees", -1)), 4)


func test_annee_absente_sort_non_nul_et_donne_les_annees() -> void:
	for an in [2021, 2023]:
		var r := _lancer(zone_path(), 700250.0, 6500250.0, an)
		assert_ne(r["code"], 0, "l'année %d n'est pas dans massif/index.json" % an)
		assert_string_contains(r["texte"], "2022", "le message donne les années disponibles")
		assert_true(r["comptes"].is_empty(), "aucun compte écrit pour une année voisine")


func test_point_hors_emprise_sort_non_nul_et_donne_l_emprise() -> void:
	var r := _lancer(zone_path(), 701000.0, 6500250.0, 2022)
	assert_ne(r["code"], 0)
	assert_string_contains(r["texte"], "700000")
	var x_y_echanges := _lancer(zone_path(), 6500250.0, 700250.0, 2022)
	assert_ne(x_y_echanges["code"], 0, "x et y échangés : hors de la zone")


func test_zone_sans_massif_sort_non_nul() -> void:
	var r := _lancer(ProjectSettings.globalize_path("res://tests"), 700250.0, 6500250.0, 2022)
	assert_ne(r["code"], 0)
	assert_string_contains(r["texte"], "massif")


func test_arguments_manquants_sortent_non_nul() -> void:
	var out := []
	var code := OS.execute(OS.get_executable_path(), PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"), "--", "--selftest", "--zone", zone_path()]), out, true)
	assert_ne(code, 0, "sans --x --y --year la vue ne démarre pas")
