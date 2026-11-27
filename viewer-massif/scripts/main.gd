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
const Compass := preload("res://scripts/compass.gd")


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


## Étiquette de texte qui revient à la ligne : aucune ligne ne dépasse la largeur donnée par ses ancres (jamais coupée à droite).
static func wrap_label(label: Label) -> void:
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.clip_text = false


func _build_hud(view: Node3D, a: Dictionary, block_id: String, cfg: Dictionary) -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var h: Dictionary = cfg["hud"]
	var margin := float(h["margin_px"])
	var north := float(h["north_size_px"])
	var top := Label.new()
	top.text = view.banner_text(block_id)
	wrap_label(top)
	top.anchor_right = 1.0
	top.offset_left = margin
	top.offset_right = -(north + 2.0 * margin)   # la flèche du nord occupe le coin haut droit
	top.offset_top = float(h["top_margin_px"])
	top.add_theme_font_size_override("font_size", int(h["title_font_size"]))
	top.add_theme_color_override("font_color", Color(str(h["title_color"])))
	top.add_theme_color_override("font_outline_color", Color(str(h["outline_color"])))
	top.add_theme_constant_override("outline_size", int(h["title_outline_px"]))
	layer.add_child(top)
	var compass := Control.new()
	compass.set_script(Compass)
	compass.anchor_left = 1.0
	compass.anchor_right = 1.0
	compass.offset_left = -(north + margin)
	compass.offset_right = -margin
	compass.offset_top = float(h["top_margin_px"])
	compass.offset_bottom = float(h["top_margin_px"]) + north
	compass.name = "nord"
	compass.call("configure", h, view.camera)
	layer.add_child(compass)
	var bottom := Label.new()
	bottom.name = "etat"
	wrap_label(bottom)
	bottom.add_theme_font_size_override("font_size", int(h["state_font_size"]))
	bottom.add_theme_color_override("font_outline_color", Color(str(h["outline_color"])))
	bottom.add_theme_constant_override("outline_size", int(h["state_outline_px"]))
	bottom.anchor_top = 1.0
	bottom.anchor_bottom = 1.0
	bottom.anchor_right = 1.0
	bottom.grow_vertical = Control.GROW_DIRECTION_BEGIN   # trop de lignes : le bandeau monte, il ne sort pas de l'écran
	bottom.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	bottom.offset_left = margin
	bottom.offset_right = -margin
	bottom.offset_top = -float(h["state_height_px"])
	var mention := str(cfg["mention"])
	var lines := [mention.substr(0, 1).to_upper() + mention.substr(1)]
	if view.stats["non_cale_trees"] > 0:
		lines.append(non_cale_text(view.non_cale_models, int(h["listed_models"])))
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


## « Non calé » d'après les extras `calage` des .glb chargés : arbres et modèles comptés, groupe jamais supposé. Les `listed`
## modèles qui portent le plus d'arbres sont nommés (à égalité, par nom) ; les autres sont dits « … et K autres ».
static func non_cale_text(models: Dictionary, listed: int) -> String:
	var names := models.keys()
	names.sort_custom(func(x, y): return int(models[x]) > int(models[y]) or (int(models[x]) == int(models[y]) and str(x) < str(y)))
	var total := 0
	for m in models:
		total += int(models[m])
	var text := "%d arbre(s) dépendent de %d modèle(s) non calé(s)" % [total, names.size()]
	var parts := []
	for i in range(mini(listed, names.size())):
		parts.append("%s (%d)" % [names[i], int(models[names[i]])])
	if parts.is_empty():
		return text
	text += " : " + ", ".join(parts)
	var rest := names.size() - parts.size()
	if rest > 0:
		text += " … et %d autre%s" % [rest, "s" if rest > 1 else ""]
	return text
