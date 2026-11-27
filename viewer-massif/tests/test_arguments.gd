## Arguments de la vue (plan T7, décision Q7 de Pascal) : `--zone <dossier> --x <X> --y <Y> --year <A>`.
## La fiche web affiche la commande complète à copier ; la vue accepte ce même jeu d'arguments.
extends "res://tests/support.gd"

const S := "res://scripts/viewer_args.gd"


func _args(a: Array) -> PackedStringArray:
	return PackedStringArray(a)


func test_la_commande_de_la_fiche_est_acceptee() -> void:
	var A = need(S)
	if A == null:
		return
	var r: Dictionary = A.parse(_args(["--zone", "data/zone_fictive", "--x", "700512.5", "--y", "6500937.5", "--year", "2022"]))
	assert_true(r.get("ok", false), str(r))
	assert_eq(r["zone"], "data/zone_fictive")
	assert_almost_eq(float(r["x"]), 700512.5, 0.001)
	assert_almost_eq(float(r["y"]), 6500937.5, 0.001)
	assert_eq(int(r["year"]), 2022)
	assert_false(r.get("selftest", false))


func test_selftest_s_ajoute_sans_changer_le_reste() -> void:
	var A = need(S)
	if A == null:
		return
	var r: Dictionary = A.parse(_args(["--selftest", "--zone", "z", "--x", "1", "--y", "2", "--year", "2022"]))
	assert_true(r.get("ok", false), str(r))
	assert_true(r.get("selftest", false))


func test_une_option_manquante_est_une_erreur_qui_la_nomme() -> void:
	var A = need(S)
	if A == null:
		return
	var tout := {"--zone": "z", "--x": "700000", "--y": "6500000", "--year": "2022"}
	for manque in tout:
		var a := []
		for k in tout:
			if k != manque:
				a.append(k)
				a.append(tout[k])
		var r: Dictionary = A.parse(_args(a))
		assert_false(r.get("ok", true), "sans %s la vue ne doit pas démarrer" % manque)
		assert_string_contains(str(r.get("error", "")), manque, "le message nomme l'option manquante")


func test_une_valeur_non_numerique_est_refusee_sans_valeur_par_defaut() -> void:
	var A = need(S)
	if A == null:
		return
	for cas in [["--x", "abc"], ["--y", "6,5e6x"], ["--year", "20x2"], ["--year", "2022.5"]]:
		var a := ["--zone", "z", "--x", "1", "--y", "2", "--year", "2022"]
		var i := a.find(cas[0])
		a[i + 1] = cas[1]
		var r: Dictionary = A.parse(_args(a))
		assert_false(r.get("ok", true), str(cas))
		assert_string_contains(str(r.get("error", "")), cas[0])


func test_une_option_inconnue_est_signalee() -> void:
	var A = need(S)
	if A == null:
		return
	var r: Dictionary = A.parse(_args(["--zone", "z", "--x", "1", "--y", "2", "--year", "2022", "--zoom", "3"]))
	assert_false(r.get("ok", true))
	assert_string_contains(str(r.get("error", "")), "--zoom")
