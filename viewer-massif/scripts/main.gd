extends Node3D
## Exemple fictif : du massif a la petite plante dans un seul moteur.
##   > 3000 m  : carte des types de station
##   3000-150 m: peuplement (un arbre = une instance)
##   < 150 m   : strate herbacee generee autour du point regarde
## Lancer avec "-- --shots" pour enregistrer des captures dans user://.

const YEAR_MAX := 200.0
const MAP_DIST := 3000.0

var station: Station
var forest: Forest
var herbs: Herbs
var cam: OrbitCamera
var info: Label
var slider: HSlider
var play: CheckButton
var year_label: Label
var _herb_year := -999.0


func _ready() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/essences.json"))

	station = Station.new(7)
	var ground := MeshInstance3D.new()
	ground.mesh = station.build_mesh()
	var gmat := StandardMaterial3D.new()
	gmat.vertex_color_use_as_albedo = true
	gmat.roughness = 1.0
	gmat.cull_mode = BaseMaterial3D.CULL_DISABLED
	ground.material_override = gmat
	add_child(ground)

	forest = Forest.new()
	add_child(forest)
	forest.setup(station, data["essences"])

	herbs = Herbs.new()
	add_child(herbs)
	herbs.setup(station, forest, data["herbacees"])

	cam = OrbitCamera.new()
	cam.station = station
	add_child(cam)
	cam.make_current()

	_build_sky()
	_build_ui()

	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--dist="):
			cam.distance = float(arg.get_slice("=", 1))
	if "--shots" in OS.get_cmdline_user_args():
		_shots()


func _build_sky() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.45
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48.0, 35.0, 0.0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 350.0
	add_child(sun)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 18)
	layer.add_child(margin)
	var box := VBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(box)

	info = Label.new()
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_theme_font_size_override("font_size", 18)
	info.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	info.add_theme_constant_override("outline_size", 6)
	box.add_child(info)

	var spacer := Control.new()
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(spacer)

	var row := HBoxContainer.new()
	box.add_child(row)
	year_label = Label.new()
	year_label.custom_minimum_size = Vector2(130, 0)
	year_label.add_theme_font_size_override("font_size", 18)
	row.add_child(year_label)
	slider = HSlider.new()
	slider.min_value = 0.0
	slider.max_value = YEAR_MAX
	slider.step = 1.0
	slider.value = forest.year
	slider.custom_minimum_size = Vector2(520, 24)
	row.add_child(slider)
	play = CheckButton.new()
	play.text = "Lecture"
	row.add_child(play)


func _process(delta: float) -> void:
	if play.button_pressed:
		var v := slider.value + delta * 4.0
		slider.value = v if v < YEAR_MAX else 0.0
	if slider.value != forest.year:
		forest.set_year(slider.value)
	# la strate herbacee suit le couvert : on la regenere par tranches de 5 ans
	var bucket := floorf(forest.year / 5.0)
	if bucket != _herb_year:
		_herb_year = bucket
		herbs.invalidate()

	forest.visible = cam.distance < MAP_DIST
	herbs.update(cam.focus, cam.distance)
	year_label.text = "Année %d" % int(forest.year)
	info.text = _describe()


func _describe() -> String:
	var d := cam.distance
	var level := "Plante"
	if d > MAP_DIST:
		level = "Carte des types de station"
	elif d > Herbs.MAX_DIST:
		level = "Peuplement : %d arbres instanciés" % forest.tree_count()
	elif d > 12.0:
		level = "Sous-bois : strate herbacée générée autour du point visé"
	var x := cam.focus.x
	var z := cam.focus.z
	var fv := station.f_at(x, z)
	var rv := station.r_at(x, z)
	var tv := station.t_at(x, z)
	var ranked: Array = []
	for sp in forest.species:
		ranked.append([Biome.suitability(sp, fv, rv, tv), sp["nom"]])
	ranked.sort_custom(func(a, b): return a[0] > b[0])
	var best := ""
	for i in 3:
		best += "%s %d %%   " % [ranked[i][1], int(round(ranked[i][0] * 100.0))]
	var type_name: String = Station.TYPE_NAMES[Station.type_index(fv, rv)]
	return "%s  (distance %s)\nStation visée : %s   F %.1f  R %.1f  T %.1f   alt. %d m   couvert %d %%\nAdéquation : %s" % [
		level, _fmt_dist(d), type_name, fv, rv, tv, int(cam.focus.y),
		int(forest.cover_at(x, z) * 100.0), best,
	]


func _fmt_dist(d: float) -> String:
	if d >= 1000.0:
		return "%.1f km" % (d / 1000.0)
	return "%d m" % int(d)


func _shots() -> void:
	var views := [
		[3300.0, -1.0, "1_carte"],
		[1500.0, -0.6, "2_peuplement"],
		[140.0, -0.35, "3_lisiere"],
		[22.0, -0.3, "4_sous_bois"],
		[1.6, -0.5, "5_plante"],
	]
	cam.focus = Vector3(1010.0, 0.0, 905.0)
	for v in views:
		cam.distance = v[0]
		cam.pitch = v[1]
		for i in 60:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var name_part: String = v[2]
		img.save_png("user://%s.png" % name_part)
	get_tree().quit()
