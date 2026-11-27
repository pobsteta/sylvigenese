## project.godot et licences (plan T8, T14, décisions de Pascal du 26/11/2026) :
## - les global uniforms des shaders sont DÉCLARÉS dans project.godot, sinon le shader échoue au chargement sans bruit ;
## - le shader d'herbe copié garde son avis de copyright (MIT, IcterusGames, commit 623212f) et CREDITS.md le dit ;
## - le rendu n'est pas verrouillé en Forward+ (repli Compatibility, T14).
extends "res://tests/support.gd"


func _shaders() -> Array:
	var out := []
	var pile := ["res://"]
	while pile.size() > 0:
		var d: String = pile.pop_back()
		for f in DirAccess.get_files_at(d):
			if f.ends_with(".gdshader") or f.ends_with(".gdshaderinc"):
				out.append(d.path_join(f))
		for s in DirAccess.get_directories_at(d):
			if s != "addons" and s != "tests" and not s.begins_with("."):
				pile.append(d.path_join(s))
	return out


func _globals(shader_texte: String) -> Array:
	var re := RegEx.new()
	re.compile("global\\s+uniform\\s+\\w+\\s+(\\w+)")
	var out := []
	for m in re.search_all(shader_texte):
		out.append(m.get_string(1))
	return out


func test_il_y_a_au_moins_un_shader_d_herbe_avec_des_global_uniforms() -> void:
	var tous := []
	for s in _shaders():
		tous.append_array(_globals(read_text(s)))
	assert_gt(_shaders().size(), 0, "aucun .gdshader dans viewer-massif (shader d'herbe attendu)")
	assert_gt(tous.size(), 0, "le shader d'herbe repris de SimpleGrassTextured emploie des global uniforms")


func test_chaque_global_uniform_est_declare_dans_project_godot() -> void:
	var projet := read_text("res://project.godot")
	var section := projet.substr(projet.find("[shader_globals]")) if projet.contains("[shader_globals]") else ""
	if section != "":
		var fin := section.find("\n[", 5)
		if fin > 0:
			section = section.substr(0, fin)
	for s in _shaders():
		for nom in _globals(read_text(s)):
			assert_true(section.contains(nom + "={") or section.contains("\"" + nom + "\""), "%s : global uniform « %s » absent de [shader_globals] de project.godot" % [s, nom])
	assert_true(projet.contains("[shader_globals]") or _shaders().size() == 0, "section [shader_globals] absente")


func test_le_shader_d_herbe_garde_son_avis_de_copyright_et_les_credits_le_disent() -> void:
	var trouve := false
	for s in _shaders():
		var t := read_text(s)
		if t.contains("IcterusGames"):
			trouve = true
			assert_true(t.to_lower().contains("mit"), s + " : la licence MIT doit être gardée en tête")
			assert_true(t.contains("Copyright") or t.contains("copyright"), s + " : avis de copyright gardé")
	assert_true(trouve, "aucun shader ne porte l'avis d'IcterusGames")
	var c := read_text("res://CREDITS.md")
	assert_string_contains(c, "IcterusGames")
	assert_string_contains(c, "623212f")
	assert_string_contains(c, "GUT")
