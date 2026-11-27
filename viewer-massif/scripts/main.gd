## Point d'entrée de la vue massif : `godot --path viewer-massif -- --zone <dossier> --x <X> --y <Y> --year <A> [--selftest]`.
## Lit les arguments, la configuration d'affichage, `massif/index.json`, bâtit la scène et affiche le bandeau de mentions.
## `--selftest` : même chargement, sans entrée ni rendu ; écrit une ligne `SELFTEST {json}` (blocs, arbres, génériques, brins
## d'herbe, semis, plafond atteint) et sort à 0. Codes de sortie : 2 arguments, 3 configuration, 4 zone ou année ou point,
## 5 modèles ou blocs. Un refus donne la cause en français (années disponibles, emprise), jamais l'année voisine.
extends Node

const Args := preload("res://scripts/viewer_args.gd")
const Config := preload("res://scripts/viewer_config.gd")
const Reader := preload("res://scripts/zone_reader.gd")
const View := preload("res://scripts/massif_view.gd")
const Banner := preload("res://scripts/banner.gd")


func _die(code: int, msg: String) -> void:
	printerr("viewer-massif : " + msg)
	get_tree().quit(code)


func _ready() -> void:
	var a := Args.parse(OS.get_cmdline_user_args())
	if not a["ok"]:
		_die(2, a["error"])
		return
	var cfg := Config.load_for_zone(a["zone"])
	if not cfg["ok"]:
		_die(3, cfg["error"])
		return
	var idx := Reader.read_index(a["zone"])
	if not idx["ok"]:
		_die(4, idx["error"])
		return
	var here := Reader.resolve(idx["data"], a["x"], a["y"], a["year"])
	if not here["ok"]:
		_die(4, here["error"])
		return
	var view: Node3D = View.new()
	view.name = "massif"
	add_child(view)
	var r: Dictionary = view.setup(a["zone"], idx["data"], cfg["data"], a["x"], a["y"], a["year"])
	if not r["ok"]:
		_die(5, r["error"])
		return
	view.wait_for_grass()
	if a["selftest"]:
		var s: Dictionary = view.stats
		print("SELFTEST " + JSON.stringify({
			"blocks": s["blocks"], "trees": s["trees"], "generic_trees": s["generic_trees"], "cw_zero_trees": s["cw_zero_trees"], "non_cale_trees": s["non_cale_trees"],
			"grass_instances": s["grass_instances"], "seedlings": s["seedlings"], "seedling_generic_species": s["seedling_generic_species"], "truncated": s["truncated"], "seedlings_truncated": s["seedlings_truncated"],
		}))
		get_tree().quit(0)
		return
	_build_environment(view, cfg["data"])
	_build_hud(view, a, here["block_id"], cfg["data"])


func _build_environment(view: Node3D, cfg: Dictionary) -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	view.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-float(cfg["sun"]["elevation_deg"]), float(cfg["sun"]["azimuth_deg"]), 0.0)
	view.add_child(sun)


func _build_hud(view: Node3D, a: Dictionary, block_id: String, cfg: Dictionary) -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var top := Label.new()
	top.text = view.banner_text(block_id)
	var h: Dictionary = cfg["hud"]
	top.position = Vector2(float(h["margin_px"]), float(h["top_margin_px"]))
	top.add_theme_font_size_override("font_size", int(h["title_font_size"]))
	top.add_theme_color_override("font_color", Color(str(h["title_color"])))
	top.add_theme_color_override("font_outline_color", Color(str(h["outline_color"])))
	top.add_theme_constant_override("outline_size", int(h["title_outline_px"]))
	layer.add_child(top)
	var bottom := Label.new()
	bottom.name = "etat"
	bottom.add_theme_font_size_override("font_size", int(h["state_font_size"]))
	bottom.add_theme_color_override("font_outline_color", Color(str(h["outline_color"])))
	bottom.add_theme_constant_override("outline_size", int(h["state_outline_px"]))
	bottom.anchor_top = 1.0
	bottom.anchor_bottom = 1.0
	bottom.offset_left = float(h["margin_px"])
	bottom.offset_top = -float(h["state_height_px"])
	var mention := str(cfg["mention"])
	var lines := [mention.substr(0, 1).to_upper() + mention.substr(1)]
	if view.stats["non_cale_trees"] > 0:
		lines.append(non_cale_text(view.non_cale_models))
	if view.stats["cw_zero_trees"] > 0:
		lines.append("%d arbre(s) de largeur de houppier nulle (cw = 0) non dessiné(s)" % int(view.stats["cw_zero_trees"]))
	lines.append_array(view.notes)
	if view.seedling_message != "":
		lines.append(view.seedling_message)
	if view.grass_message != "":
		lines.append(view.grass_message)
	lines.append("Zone %s, année %d, bloc %s" % [view.zone, a["year"], block_id])
	bottom.text = "\n".join(lines)
	layer.add_child(bottom)


## « Non calé » d'après les extras `calage` des .glb chargés : modèles nommés, arbres comptés, groupe jamais supposé.
static func non_cale_text(models: Dictionary) -> String:
	var parts := []
	var total := 0
	for m in models:
		parts.append("%s (%d)" % [m, models[m]])
		total += int(models[m])
	parts.sort()
	return "%d arbre(s) dépendent de modèles non calés : %s" % [total, ", ".join(parts)]
