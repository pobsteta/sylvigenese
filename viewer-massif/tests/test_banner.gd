## Bandeau d'écran (plan T6, T8, §6 ; ADR 0007 choix 9 ; spec §10) : « provisoire » dès que le bloc l'est, « semis non
## simulés » quand le recrutement n'est pas par cohortes (seedlings_simulated faux), modèles génériques comptés et dits,
## stade de l'arbre dit, sol à 25 m dit.
extends "res://tests/support.gd"

const S := "res://scripts/banner.gd"


func _textes(block: Dictionary, index: Dictionary) -> String:
	var B = need(S)
	if B == null:
		return ""
	return str(B.text(block, index)).to_lower()


func test_provisoire_est_dit() -> void:
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	assert_string_contains(_textes(b, idx), "provisoire")


func test_semis_non_simules_en_ifn_direct() -> void:
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	assert_false(b["seedlings_simulated"])
	assert_string_contains(_textes(b, idx), "semis non simulés")


func test_pas_de_semis_non_simules_quand_ils_le_sont() -> void:
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	b["seedlings_simulated"] = true
	b["provisoire"] = false
	var t := _textes(b, idx)
	assert_false(t.contains("semis non simulés"), "le bandeau ne dit pas ce qui est faux")


func test_le_modele_generique_est_compte_et_dit() -> void:
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	var t := _textes(b, idx)
	assert_string_contains(t, "générique")
	assert_true(t.contains("1"), "le nombre d'arbres génériques (1) est donné")


func test_le_stade_est_celui_de_l_arbre_et_le_sol_est_a_25_m() -> void:
	var b := read_json(zone_path() + "/massif/2022/t_700000_6500000.json")
	var idx := read_json(zone_path() + "/massif/index.json")
	var t := _textes(b, idx)
	assert_string_contains(t, "stade de l'arbre")
	assert_string_contains(t, "25 m")
