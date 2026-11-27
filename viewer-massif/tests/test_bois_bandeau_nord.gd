## Mission 085 (demande de Pascal du 27/11/2026) : (1) le bois a sa couleur, les cartes de feuillage la leur ;
## (2) la ligne « non calés » du bandeau est courte et aucune ligne ne dépasse la largeur de l'écran ;
## (3) la flèche du nord suit le repère de la vue (x = est, z = -nord) et le cap de la caméra.
extends "res://tests/support.gd"

const VIEW := "res://scripts/massif_view.gd"
const MAIN := "res://scripts/main.gd"
const COMPASS := "res://scripts/compass.gd"
const LOADER := "res://scripts/tree_model_loader.gd"


func _config() -> Dictionary:
	var C = need("res://scripts/viewer_config.gd")
	var r: Dictionary = C.parse_text(FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://").path_join("../config.yml")))
	assert_true(r["ok"], str(r["error"]))
	return r["data"]


func _two_surface_res() -> Dictionary:
	var L = need(LOADER)
	return L.load_glb(ProjectSettings.globalize_path(FIXTURES + "arbre_ecorce_feuillage.glb"), FOV_DEG_ESSAI)


# --- 1. le bois et le feuillage ------------------------------------------------------------------------------------

func test_le_chargeur_dit_le_role_de_chaque_surface() -> void:
	var res := _two_surface_res()
	assert_true(res["ok"], str(res["error"]))
	for lv in res["levels"]:
		assert_eq(lv["surface_roles"], ["wood", "foliage"], "primitive 0 = écorce, primitive 1 = feuillage")
		assert_eq((lv["mesh"] as Mesh).get_surface_count(), 2)


## Écrit sous user:// une copie d'un .glb de la fixture dont le JSON a subi `ancien` -> `nouveau` (même longueur : le fichier reste
## un .glb valide) ; rend son chemin absolu.
func _glb_modifie(source: String, ancien: String, nouveau: String, nom: String, permuter_materiaux := false) -> String:
	assert_eq(ancien.length(), nouveau.length(), "même longueur")
	var src := FileAccess.get_file_as_bytes(source)
	var json_len := int(src.decode_u32(12))
	var texte := src.slice(20, 20 + json_len).get_string_from_utf8()
	assert_true(texte.contains(ancien), "la fixture contient « %s »" % ancien)
	texte = texte.replace(ancien, nouveau)
	if permuter_materiaux:   # matériau 0 <-> 1 sur toutes les primitives, par un intermédiaire de même longueur
		texte = texte.replace("\"material\":0", "\"material\":9").replace("\"material\":1", "\"material\":0").replace("\"material\":9", "\"material\":1")
	var js := texte.to_utf8_buffer()
	assert_eq(js.size(), json_len)
	var chemin := "user://" + nom
	var f := FileAccess.open(chemin, FileAccess.WRITE)
	f.store_buffer(src.slice(0, 20))
	f.store_buffer(js)
	f.store_buffer(src.slice(20 + json_len))
	f.close()
	return ProjectSettings.globalize_path(chemin)


func test_les_modeles_de_la_fixture_et_les_generiques_portent_ecorce_puis_feuillage() -> void:
	var L = need(LOADER)
	for n in ["09_mature", "09_old", "09_young", "generique_resineux"]:
		var res: Dictionary = L.load_glb(zone_path() + "/assets/trees/%s.glb" % n, FOV_DEG_ESSAI)
		assert_true(res["ok"], str(res["error"]))
		for lv in res["levels"]:
			assert_eq(lv["surface_roles"], ["wood", "foliage"], n)


func test_un_materiau_mal_nomme_est_refuse_par_une_erreur_nommee() -> void:
	var L = need(LOADER)
	var chemin := _glb_modifie(zone_path() + "/assets/trees/09_mature.glb", "09_mature_ecorce", "09_mature_ecorXe", "ecorce_mal_nomme.glb")
	var res: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
	assert_false(res["ok"], "un rôle inconnu sur un modèle du générateur n'est pas coloré en silence")
	assert_string_contains(str(res["error"]), "_ecorce puis _feuillage")
	assert_string_contains(str(res["error"]), "09_mature_ecorXe")
	assert_string_contains(str(res["error"]), "le niveau 0")


func test_un_generique_au_feuillage_mal_nomme_est_refuse() -> void:
	var L = need(LOADER)
	var chemin := _glb_modifie(zone_path() + "/assets/trees/generique_resineux.glb", "generique_resineux_feuillage", "generique_resineux_feuillagX", "generique_mal_nomme.glb")
	var res: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
	assert_false(res["ok"])
	assert_string_contains(str(res["error"]), "_ecorce puis _feuillage")


func test_une_primitive_sans_materiau_est_refusee() -> void:
	var L = need(LOADER)
	var chemin := _glb_modifie(zone_path() + "/assets/trees/09_old.glb", "\"material\":0", "\"materiaX\":0", "sans_materiau.glb")
	var res: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
	assert_false(res["ok"])
	assert_string_contains(str(res["error"]), "(sans matériau)")


## Mission 086 : un indice de matériau ou de maillage négatif ou hors liste, ou un élément de `materials` qui n'est pas un
## objet, est refusé par une erreur nommée (jamais lu depuis la fin de la liste, jamais un plantage).
func _g_essai(material, materials: Array = [{"name": "a_ecorce"}, {"name": "a_feuillage"}]) -> Dictionary:
	return {"materials": materials, "meshes": [{"primitives": [{"material": 0}, {"material": material}]}]}


func test_un_indice_de_materiau_negatif_ou_hors_liste_est_refuse() -> void:
	var L = need(LOADER)
	# Témoin : l'indice 1 valide donne bien écorce puis feuillage.
	var bon := _g_essai(1)
	assert_eq(L._surface_roles(bon, 0), ["wood", "foliage"])
	assert_eq(L._check_roles("t.glb", 0, bon, 0, L._surface_roles(bon, 0)), "")
	for mauvais in [-1, -2, 2, 7, 1.5, "1", null]:
		var g := _g_essai(mauvais)
		var roles: Array = L._surface_roles(g, 0)
		assert_eq(roles, ["wood", "unknown"], "indice %s : jamais le matériau de la fin de la liste" % str(mauvais))
		var erreur: String = L._check_roles("t.glb", 0, g, 0, roles)
		assert_ne(erreur, "", "indice %s refusé" % str(mauvais))
		assert_string_contains(erreur, "_ecorce puis _feuillage")
		assert_string_contains(erreur, "invalide")


func test_un_element_de_materials_qui_n_est_pas_un_objet_est_refuse_sans_planter() -> void:
	var L = need(LOADER)
	for element in [3, "x", null, [1]]:
		var g := _g_essai(1, [{"name": "a_ecorce"}, element])
		var roles: Array = L._surface_roles(g, 0)
		assert_eq(roles, ["wood", "unknown"])
		var erreur: String = L._check_roles("t.glb", 0, g, 0, roles)
		assert_string_contains(erreur, "t.glb")
		assert_string_contains(erreur, "invalide")
	# `materials` absent ou qui n'est pas une liste : primitives sans matériau valide, refus.
	var sans := {"meshes": [{"primitives": [{"material": 0}, {"material": 1}]}]}
	assert_eq(L._surface_roles(sans, 0), ["unknown", "unknown"])
	assert_ne(L._check_roles("t.glb", 0, sans, 0, L._surface_roles(sans, 0)), "")
	var pas_liste := {"materials": {"a": 1}, "meshes": [{"primitives": [{"material": 0}]}]}
	assert_eq(L._surface_roles(pas_liste, 0), ["unknown"])


func test_un_indice_de_maillage_negatif_ou_hors_liste_est_refuse() -> void:
	var L = need(LOADER)
	var g := _g_essai(1)
	for mauvais in [-1, 1, 5]:
		assert_eq(L._surface_roles(g, mauvais), [], "maillage %d : aucune primitive lue, pas le dernier maillage" % mauvais)
		var erreur: String = L._check_roles("t.glb", 2, g, mauvais, ["wood", "foliage"])
		assert_ne(erreur, "", "maillage %d refusé même si les rôles passés sont corrects" % mauvais)
		assert_string_contains(erreur, "le niveau 2")
		assert_string_contains(erreur, "maillage %d" % mauvais)


func test_l_ordre_ecorce_puis_feuillage_est_exige() -> void:
	# le feuillage en première primitive et l'écorce en seconde : refusé, le contrat fixe l'ordre
	var L = need(LOADER)
	var chemin := _glb_modifie(zone_path() + "/assets/trees/09_young.glb", "09_young_ecorce", "09_young_ecorce", "ordre_inverse.glb", true)
	var res: Dictionary = L.load_glb(chemin, FOV_DEG_ESSAI)
	assert_false(res["ok"], "rôles inversés : refusé, jamais deviné")
	assert_string_contains(str(res["error"]), "_ecorce puis _feuillage")


func test_le_bois_et_le_feuillage_ont_des_couleurs_distinctes() -> void:
	var V = need(VIEW)
	var view: Node3D = V.new()
	view.cfg = _config()
	add_child_autofree(view)
	var res := _two_surface_res()
	view.paint_model(res)
	for lv in res["levels"]:
		var mesh: Mesh = lv["mesh"]
		var wood := (mesh.surface_get_material(0) as StandardMaterial3D).albedo_color
		var leaf := (mesh.surface_get_material(1) as StandardMaterial3D).albedo_color
		assert_ne(wood, leaf, "le tronc n'a pas la couleur du feuillage")
		assert_eq(wood, Color(str(view.cfg["wood"]["color"])), "le bois : viewer.wood.color")
		assert_eq(leaf, Color("#4f7a32"), "les cartes : extras.feuillage.couleur du modèle")


func test_une_instance_n_ecrase_plus_le_maillage_par_la_couleur_du_feuillage() -> void:
	var src := FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://scripts/massif_view.gd"))
	assert_false(src.contains("mi.material_override = _material_for"), "plus de material_override sur les arbres et les semis")


# --- 2. le bandeau ---------------------------------------------------------------------------------------------------

func _beaucoup_de_modeles() -> Dictionary:
	var d := {}
	for i in range(40):
		d["modele_%02d_mature" % i] = 40 - i
	return d


func test_la_ligne_non_cale_est_courte_et_compte_tout() -> void:
	var M = need(MAIN)
	var models := _beaucoup_de_modeles()
	var total := 0
	for m in models:
		total += int(models[m])
	var t: String = M.non_cale_text(models, 3)
	assert_string_contains(t, "%d arbre(s)" % total)
	assert_string_contains(t, "40 modèle(s)")
	assert_string_contains(t, "modele_00_mature (40)")
	assert_string_contains(t, "… et 37 autres")
	assert_false(t.contains("modele_03_mature"), "les modèles au-delà du plafond ne sont pas listés")
	assert_lt(t.length(), 150, "une ligne courte")


func test_peu_de_modeles_aucun_autre() -> void:
	var M = need(MAIN)
	var t: String = M.non_cale_text({"a": 1, "b": 2}, 3)
	assert_false(t.contains("autre"))
	assert_string_contains(t, "b (2), a (1)")


func test_le_plafond_vient_de_config() -> void:
	assert_gt(int(_config()["hud"]["listed_models"]), 0)


func test_aucune_ligne_du_bandeau_ne_depasse_l_ecran() -> void:
	var M = need(MAIN)
	var largeur := 600.0
	var parent := Control.new()
	parent.size = Vector2(largeur, 300)
	add_child_autofree(parent)
	var label := Label.new()
	M.wrap_label(label)
	label.anchor_right = 1.0
	label.text = "\n".join(["ligne courte", "Sol : grille de 25 m, lissé", M.non_cale_text(_beaucoup_de_modeles(), 3),
		"Stade de l'arbre : h / h_pot (hauteur de l'arbre sur le plafond de la station), seuils de biomes/stades/stage_breaks.yml, et encore du texte pour forcer le retour à la ligne"])
	parent.add_child(label)
	await get_tree().process_frame
	await get_tree().process_frame
	assert_lte(label.size.x, largeur, "l'étiquette n'est pas plus large que l'écran")
	assert_lte(label.get_minimum_size().x, largeur, "aucun mot insécable ne force une ligne plus large que l'écran")
	assert_gt(label.get_line_count(), 4, "la ligne trop longue passe à la ligne au lieu d'être coupée")


# --- 3. le nord ------------------------------------------------------------------------------------------------------

func test_cap_zero_la_fleche_va_vers_le_haut() -> void:
	var C = need(COMPASS)
	# regard vers le nord = -z de la vue
	assert_almost_eq(C.screen_angle(Vector3(0, 0, -1)), 0.0, 0.0001)
	var tip: Vector2 = C.arrow_points(C.screen_angle(Vector3(0, 0, -1)), 10.0)[0]
	assert_almost_eq(tip.x, 0.0, 0.001)
	assert_lt(tip.y, 0.0, "écran : y vers le bas, la pointe est en haut")


func test_cap_90_vers_l_est_la_fleche_va_vers_la_gauche() -> void:
	var C = need(COMPASS)
	var f := Vector3(1, 0, 0)   # est = +x
	assert_almost_eq(C.heading_deg(f), 90.0, 0.001)
	var tip: Vector2 = C.arrow_points(C.screen_angle(f), 10.0)[0]
	assert_almost_eq(tip.x, -10.0, 0.001)
	assert_almost_eq(tip.y, 0.0, 0.001)


func test_cap_180_bas_et_cap_270_droite() -> void:
	var C = need(COMPASS)
	var sud: Vector2 = C.arrow_points(C.screen_angle(Vector3(0, 0, 1)), 10.0)[0]
	assert_almost_eq(sud.x, 0.0, 0.001)
	assert_almost_eq(sud.y, 10.0, 0.001)
	var ouest: Vector2 = C.arrow_points(C.screen_angle(Vector3(-1, 0, 0)), 10.0)[0]
	assert_almost_eq(ouest.x, 10.0, 0.001)
	assert_almost_eq(C.heading_deg(Vector3(-1, 0, 0)), 270.0, 0.001)


func test_l_inclinaison_ne_change_pas_le_cap_et_le_regard_vertical_n_a_pas_de_cap() -> void:
	var C = need(COMPASS)
	assert_almost_eq(C.screen_angle(Vector3(1, -0.7, 0)), C.screen_angle(Vector3(1, 0, 0)), 0.0001)
	assert_true(is_nan(C.screen_angle(Vector3(0, -1, 0))))


func test_la_fleche_suit_la_camera_quand_elle_tourne() -> void:
	var C = need(COMPASS)
	var h: Dictionary = _config()["hud"]
	var cam := Camera3D.new()
	add_child_autofree(cam)
	var compass := Control.new()
	compass.set_script(C)
	add_child_autofree(compass)
	compass.configure(h, cam)
	compass._process(0.0)
	assert_almost_eq(compass.angle_rad, 0.0, 0.0001, "caméra sans rotation : regard vers le nord, flèche en haut")
	cam.rotation.y = -PI / 2.0   # la caméra tourne vers l'est (+x)
	compass._process(0.0)
	assert_almost_eq(compass.angle_rad, -PI / 2.0, 0.0001, "regard vers l'est : flèche vers la gauche")
	cam.rotation.y = PI / 2.0    # vers l'ouest
	compass._process(0.0)
	assert_almost_eq(compass.angle_rad, PI / 2.0, 0.0001, "regard vers l'ouest : flèche vers la droite")
