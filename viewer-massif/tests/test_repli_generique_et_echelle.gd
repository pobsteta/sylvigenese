## Mission 075 (reprises de la relecture de la PR n° 12) :
## (1) le fichier de modèle de chaque (essence, stade) est dit par `massif/index.json` (stage_models), générique compris : un
##     stade sans exemplaire d'une essence qui en a d'autres (cas réel : Picea abies, mature, 1 arbre en 2022) est dessiné par le
##     générique, la vue lit le fichier sans le reconstruire, les comptes de génériques sont justes (vue, bandeau, autotest) ;
## (2) l'échelle d'un générique est (r, h, r) d'un modèle de 1 m x 1 m (comme iTowns, models.py) : un générique de 12 m de haut
##     et cw = 4 m a un houppier de 2 m de rayon ; une clé de dimension absente sur un modèle du générateur est refusée ;
## (3) le bandeau dit d'où vient le stade : h / h_pot, seuils de biomes/stades/stage_breaks.yml.
## Fixture : tests/fixtures/zone_m6_stade_manquant (hêtre 09 aux stades mature et old seulement + un hêtre young : générique
## feuillu) ; les autres zones sont copiées dans user:// et modifiées ici.
extends "res://tests/support.gd"

const VIEW := "res://scripts/massif_view.gd"
const STADE_MANQUANT := "zone_m6_stade_manquant"


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


## Copie d'une zone d'essai dans user:// (index, bloc de 2022, .glb, zone.yml) ; rend le chemin absolu de la copie.
func _copie(source: String, nom: String) -> String:
	var src := zone_path(source)
	var dst := ProjectSettings.globalize_path("user://" + nom)
	for f in ["massif/index.json", "massif/2022/t_700000_6500000.json", "zone.yml"]:
		_ecrire(dst + "/" + f, FileAccess.get_file_as_bytes(src + "/" + f))
	for f in DirAccess.get_files_at(src + "/assets/trees"):
		_ecrire(dst + "/assets/trees/" + f, FileAccess.get_file_as_bytes(src + "/assets/trees/" + f))
	return dst


func _ecrire_json(chemin: String, d: Dictionary) -> void:
	_ecrire(chemin, JSON.stringify(d).to_utf8_buffer())


# --- (1) repli générique par stade ------------------------------------------------------------------------------------

func test_l_index_dit_le_fichier_du_stade_sans_exemplaire() -> void:
	var idx := read_json(zone_path(STADE_MANQUANT) + "/massif/index.json")
	var par := {}
	for m in idx["stage_models"]:
		par["%s|%s" % [m["species"], m["stage"]]] = m
	assert_eq(par["09|mature"]["file"], "09_mature.glb")
	assert_eq(par["09|young"]["kind"], "generic", "le hêtre young n'a pas d'exemplaire")
	assert_eq(par["09|young"]["file"], "generique_feuillu.glb", "le fichier est dit : jamais 09_young.glb")
	assert_false(FileAccess.file_exists(zone_path(STADE_MANQUANT) + "/assets/trees/09_young.glb"), "le cas : ce fichier n'existe pas")
	assert_true(FileAccess.file_exists(zone_path(STADE_MANQUANT) + "/assets/trees/" + par["09|young"]["file"]))


func test_autotest_sur_une_zone_avec_un_stade_sans_exemplaire_dessine_le_generique_et_le_compte() -> void:
	var r := _selftest(zone_path(STADE_MANQUANT))
	assert_eq(r["code"], 0, r["texte"])
	var c: Dictionary = r["comptes"]
	assert_eq(int(c.get("trees", -1)), 5)
	assert_eq(int(c.get("generic_trees", -1)), 2, "62 (aucun exemplaire) et 09 young (stade sans exemplaire) : deux génériques")


func test_le_bandeau_compte_le_generique_d_un_stade_sans_exemplaire() -> void:
	var B = need("res://scripts/banner.gd")
	if B == null:
		return
	var b := read_json(zone_path(STADE_MANQUANT) + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path(STADE_MANQUANT) + "/massif/index.json")
	assert_eq(B.generic_count(b, idx), 2)
	assert_string_contains(str(B.text(b, idx)), "2 arbres dessinés par un modèle générique")
	# la zone d'essai sans stade manquant : un seul générique (62), comme avant
	var b1 := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var i1 := read_json(zone_path() + "/massif/index.json")
	assert_eq(B.generic_count(b1, i1), 1)


func test_un_arbre_dont_le_couple_n_est_pas_dans_l_index_est_refuse_en_code_5() -> void:
	var zone := _copie(STADE_MANQUANT, "zone_couple_absent")
	var idx := read_json(zone + "/massif/index.json")
	var gardes := []
	for m in idx["stage_models"]:
		if not (m["species"] == "09" and m["stage"] == "young"):
			gardes.append(m)
	idx["stage_models"] = gardes
	_ecrire_json(zone + "/massif/index.json", idx)
	var r := _selftest(zone)
	assert_eq(r["code"], 5, r["texte"])
	assert_string_contains(r["texte"], "09")
	assert_string_contains(r["texte"], "young")
	assert_string_contains(r["texte"], "stage_models")


func test_la_vue_lit_le_fichier_de_l_index_sans_le_reconstruire() -> void:
	# l'index renvoie le stade young du hêtre à 09_old.glb : la vue le suit (aucun nom <espar>_<stade> n'est refabriqué)
	var zone := _copie(STADE_MANQUANT, "zone_fichier_dit")
	var idx := read_json(zone + "/massif/index.json")
	for m in idx["stage_models"]:
		if m["species"] == "09" and m["stage"] == "young":
			m["file"] = "09_old.glb"
			m["kind"] = "own"
	_ecrire_json(zone + "/massif/index.json", idx)
	DirAccess.remove_absolute(zone + "/assets/trees/generique_feuillu.glb")
	var r := _selftest(zone)
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("generic_trees", -1)), 1, "seul 62 reste générique d'après l'index")


func test_un_index_sans_stage_models_est_refuse_en_code_4() -> void:
	var zone := _copie(STADE_MANQUANT, "zone_sans_stage_models")
	var idx := read_json(zone + "/massif/index.json")
	idx.erase("stage_models")
	_ecrire_json(zone + "/massif/index.json", idx)
	var r := _selftest(zone)
	assert_eq(r["code"], 4, r["texte"])
	assert_string_contains(r["texte"], "stage_models")


# --- (2) échelle des génériques ----------------------------------------------------------------------------------------

func test_un_generique_de_12_m_de_haut_et_cw_4_m_a_un_houppier_de_2_m_de_rayon() -> void:
	var V = need(VIEW)
	if V == null:
		return
	var s: Dictionary = V.instance_scale({"generique": true, "groupe": "feuillu", "provisoire": true}, 1.0, 12.0, 4.0, "essai")
	assert_true(s["ok"], str(s["error"]))
	# modèle de 1 m x 1 m : l'échelle (r, h, r) EST la taille de l'arbre
	assert_almost_eq(float(s["sxz"]) * 1.0, 2.0, 0.0001, "rayon du houppier = cw / 2 = 2 m")
	assert_almost_eq(float(s["sy"]) * 1.0, 12.0, 0.0001, "hauteur = h = 12 m")


func test_l_echelle_d_un_modele_du_generateur_suit_ses_dimensions_de_reference() -> void:
	var V = need(VIEW)
	if V == null:
		return
	var s: Dictionary = V.instance_scale({"H_ref_m": 12.0, "rayon_houppier_ref_m": 3.0}, 12.0, 24.0, 4.0, "essai")
	assert_true(s["ok"], str(s["error"]))
	assert_almost_eq(float(s["sxz"]), 2.0 / 3.0, 0.0001, "rayon 2 m sur un modèle de rayon 3 m")
	assert_almost_eq(float(s["sy"]), 2.0, 0.0001, "24 m sur un modèle de 12 m")


func test_une_dimension_absente_d_un_modele_du_generateur_est_refusee_et_nommee() -> void:
	var V = need(VIEW)
	if V == null:
		return
	var sans_rayon: Dictionary = V.instance_scale({"H_ref_m": 12.0}, 12.0, 12.0, 4.0, "09_mature")
	assert_false(sans_rayon["ok"], "pas de repli sur la hauteur : le rayon manque")
	assert_string_contains(sans_rayon["error"], "rayon_houppier_ref_m")
	assert_string_contains(sans_rayon["error"], "09_mature")
	var sans_h: Dictionary = V.instance_scale({"rayon_houppier_ref_m": 2.0}, 12.0, 12.0, 4.0, "09_mature")
	assert_false(sans_h["ok"])
	assert_string_contains(sans_h["error"], "H_ref_m")
	var nul: Dictionary = V.instance_scale({"H_ref_m": 12.0, "rayon_houppier_ref_m": 0.0}, 12.0, 12.0, 4.0, "09_mature")
	assert_false(nul["ok"], "un rayon de référence nul n'est pas une échelle")


func test_un_generique_qui_ne_mesure_pas_1_m_est_refuse() -> void:
	var V = need(VIEW)
	if V == null:
		return
	var s: Dictionary = V.instance_scale({"generique": true, "groupe": "resineux"}, 12.0, 12.0, 4.0, "generique_resineux")
	assert_false(s["ok"], "la convention de assets : un générique mesure 1 m x 1 m")
	assert_string_contains(s["error"], "1 m")


func test_les_generiques_de_la_fixture_ont_1_m_de_haut_et_la_vue_les_accepte() -> void:
	var L = need("res://scripts/tree_model_loader.gd")
	if L == null:
		return
	for n in ["generique_resineux", "generique_feuillu"]:
		var r: Dictionary = L.load_glb(zone_path(STADE_MANQUANT) + "/assets/trees/" + n + ".glb", FOV_DEG_ESSAI)
		assert_true(r.get("ok", false), str(r.get("error", "")))
		assert_almost_eq(float(r["height_m"]), 1.0, 0.001, n + " : 1 m de haut")


func test_un_arbre_de_houppier_nul_n_est_pas_dessine_et_est_dit() -> void:
	var zone := _copie("zone_m6", "zone_cw_nul")
	var chemin := zone + "/massif/2022/t_700000_6500000.json"
	var b := read_json(chemin)
	b["trees"][0]["cw"] = 0.0
	_ecrire_json(chemin, b)
	var r := _selftest(zone)
	assert_eq(r["code"], 0, r["texte"])
	assert_eq(int(r["comptes"].get("trees", -1)), 3, "l'arbre de cw = 0 n'est pas dessiné")
	assert_eq(int(r["comptes"].get("cw_zero_trees", -1)), 1, "il est compté")


# --- (3) bandeau : d'où vient le stade --------------------------------------------------------------------------------

func test_le_bandeau_dit_que_le_stade_vient_de_h_sur_h_pot() -> void:
	var B = need("res://scripts/banner.gd")
	if B == null:
		return
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	var t := str(B.text(b, idx))
	assert_string_contains(t, "h / h_pot")
	assert_string_contains(t, "plafond de la station")
	assert_string_contains(t, "biomes/stades/stage_breaks.yml")
	assert_false(t.contains("sa hauteur sur celle de sa cellule"), "l'ancienne phrase était inexacte")
