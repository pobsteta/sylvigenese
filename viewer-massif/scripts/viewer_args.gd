## Arguments de la vue massif (plan T7, décision Q7 de Pascal) : `--zone <dossier> --x <X> --y <Y> --year <A>`, plus
## `--selftest` (charge la zone sans rendu, écrit des comptes, sort à 0). Aucune valeur par défaut : une option
## manquante, une valeur non numérique ou une option inconnue est une erreur qui la nomme.
extends RefCounted

const OPTIONS_WITH_VALUE := ["--zone", "--x", "--y", "--year"]


static func _is_number(s: String) -> bool:
	var re := RegEx.new()
	re.compile("^[+-]?[0-9]+(\\.[0-9]+)?$")
	return re.search(s) != null


static func _is_integer(s: String) -> bool:
	var re := RegEx.new()
	re.compile("^[+-]?[0-9]+$")
	return re.search(s) != null


static func _fail(msg: String) -> Dictionary:
	return {"ok": false, "error": msg, "zone": "", "x": 0.0, "y": 0.0, "year": 0, "selftest": false}


## `args` : les arguments utilisateur (ceux qui suivent `--` sur la ligne de commande de Godot).
static func parse(args: PackedStringArray) -> Dictionary:
	var values := {}
	var selftest := false
	var i := 0
	while i < args.size():
		var a := args[i]
		if a == "--selftest":
			selftest = true
			i += 1
		elif a in OPTIONS_WITH_VALUE:
			if i + 1 >= args.size() or args[i + 1].begins_with("--"):
				return _fail("l'option %s demande une valeur" % a)
			values[a] = args[i + 1]
			i += 2
		else:
			return _fail("option inconnue : %s (attendu : --zone <dossier> --x <X> --y <Y> --year <A> [--selftest])" % a)
	for opt in OPTIONS_WITH_VALUE:
		if not values.has(opt):
			return _fail("option manquante : %s (commande : --zone <dossier> --x <X> --y <Y> --year <A>)" % opt)
	for opt in ["--x", "--y"]:
		if not _is_number(values[opt]):
			return _fail("%s : « %s » n'est pas un nombre (mètres, EPSG:2154)" % [opt, values[opt]])
	if not _is_integer(values["--year"]):
		return _fail("--year : « %s » n'est pas une année entière" % values["--year"])
	return {
		"ok": true, "error": "", "zone": values["--zone"], "x": float(values["--x"]), "y": float(values["--y"]),
		"year": int(values["--year"]), "selftest": selftest,
	}
