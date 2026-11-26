## Scène du massif (BRIEF §10 ; plan T6, T8, T13, T14) : terrain des blocs, arbres en MultiMesh, herbe et semis autour de la
## caméra. Un MultiMeshInstance3D par (bloc, case de 25 m, modèle, niveau de détail) : la plage de visibilité d'un MultiMesh
## vaut pour toute l'instance (distance au centre de ses instances), un MultiMesh par bloc entier donnerait un niveau de
## détail unique à 500 m de large ; la case de 25 m (maille du sol) garde la distance juste à une demi-case près.
## Repère : monde de Godot = repère T6 centré sur l'origine du bloc du point demandé ; chaque bloc voisin est décalé de la
## différence de ses origines. Aucune valeur écologique ici : tout vient de `massif/`, des .glb et du bloc `viewer` de config.yml.
extends Node3D

const Frame := preload("res://scripts/frame.gd")
const Reader := preload("res://scripts/zone_reader.gd")
const Loader := preload("res://scripts/tree_model_loader.gd")
const Terrain := preload("res://scripts/terrain.gd")
const GrassLib := preload("res://scripts/grass.gd")
const SeedLib := preload("res://scripts/seedlings.gd")
const Hashing := preload("res://scripts/hashing.gd")
const Gate := preload("res://scripts/request_gate.gd")
const Banner := preload("res://scripts/banner.gd")
const GRASS_SHADER := preload("res://shaders/grass.gdshader")
const GRASS_TEXTURE := preload("res://textures/grassbushcc008.png")

## Rayon (m) des blocs chargés autour du point demandé : réglage d'affichage, sans lien avec l'écologie.
const VIEW_RADIUS_M := 1000.0
## Côté (m) d'une case de MultiMesh d'arbres.
const CHUNK_M := 25.0
## Hauteur des yeux (m) de la caméra posée au point demandé.
const EYE_M := 1.7
## Surface d'un hectare (m2), pour l'aire de cellule en ha.
const M2_PER_HA := 10000.0

var zone := ""
var year := 0
var index: Dictionary = {}
var cfg: Dictionary = {}
var ref_origin: Dictionary = {}
var blocks := {}            # block_id -> {data, off: Vector3 (bloc, repère du fichier : décalage à l'origine de référence), entry}
var block_at := {}          # Vector2i (origine / taille) -> block_id
var block_size := 500.0
var model_cache := {}       # chemin .glb -> résultat du chargeur
var species_model := {}     # code espar -> {model, kind}
var seedling_models := {}   # code espar -> {path, res} ou {missing: raison}
var stats := {"blocks": 0, "trees": 0, "generic_trees": 0, "non_cale_trees": 0, "grass_instances": 0, "seedlings": 0, "truncated": false}
var notes: Array = []        # lignes de signalement pour l'écran
var grass_message := ""
var camera: Camera3D

var _gate := Gate.new()
var _thread: Thread
var _pending_center: Variant = null
var _last_center := Vector2(INF, INF)
var _grass_mmi: MultiMeshInstance3D
var _grass_material: ShaderMaterial
var _seedling_nodes: Array = []
var _materials := {}
var _flat_normal: ImageTexture


func setup(zone_dir: String, idx: Dictionary, config: Dictionary, x: float, y: float, yr: int) -> Dictionary:
	zone = str(idx["zone"])
	year = yr
	index = idx
	cfg = config
	block_size = float(idx["block_size_m"])
	for m in idx["models"]:
		species_model[str(m["species"])] = m
	var here := Reader.resolve(idx, x, y, yr)
	if not here["ok"]:
		return {"ok": false, "error": here["error"]}
	var ids := Reader.blocks_around(idx, yr, x, y, VIEW_RADIUS_M)
	if not ids.has(here["block_id"]):
		ids.append(here["block_id"])
	# le bloc du point est lu en premier : son origine sert de référence au monde
	ids.erase(here["block_id"])
	ids.push_front(here["block_id"])
	for id in ids:
		var entry := Reader.block_entry(idx, yr, id)
		var r := Reader.read_block(zone_dir.path_join("massif").path_join(str(entry["file"])))
		if not r["ok"]:
			return {"ok": false, "error": r["error"]}
		var data: Dictionary = r["data"]
		if blocks.is_empty():
			ref_origin = data["origin"]
		var o: Dictionary = data["origin"]
		var off := Vector3(float(o["x"]) - float(ref_origin["x"]), float(o["y"]) - float(ref_origin["y"]), float(o["z"]) - float(ref_origin["z"]))
		blocks[id] = {"data": data, "off": off, "entry": entry}
		block_at[Vector2i(floori(float(o["x"]) / block_size), floori(float(o["y"]) / block_size))] = id
	stats["blocks"] = blocks.size()
	_make_flat_normal()
	_set_global_shader_textures()
	for id in blocks:
		var rr := _build_block(zone_dir, id)
		if not rr["ok"]:
			return rr
	var sr := _load_seedling_models(zone_dir)
	if not sr["ok"]:
		return sr
	_make_grass_nodes()
	var cam_xy := Vector2(x - float(ref_origin["x"]), y - float(ref_origin["y"]))
	var ground := height_world(cam_xy.x, cam_xy.y)
	if is_nan(ground):
		return {"ok": false, "error": "sol introuvable au point demandé"}
	camera = Camera3D.new()
	camera.set_script(load("res://scripts/camera_fly.gd"))
	camera.fov = Loader.FOV_DEG
	camera.far = 4000.0
	camera.position = Frame.block_to_godot(cam_xy.x, cam_xy.y, ground + EYE_M)
	camera.current = true
	add_child(camera)
	request_grass(cam_xy)
	return {"ok": true, "error": ""}


# --- sol ---------------------------------------------------------------------------------------------------------

## Altitude (m) relative à l'origine de référence au point (x, y) du repère du fichier relatif à cette origine ; NAN hors des
## blocs chargés.
func height_world(x: float, y: float) -> float:
	var key := Vector2i(floori((x + float(ref_origin["x"])) / block_size), floori((y + float(ref_origin["y"])) / block_size))
	if not block_at.has(key):
		return NAN
	var b: Dictionary = blocks[block_at[key]]
	var off: Vector3 = b["off"]
	return Terrain.height_at(b["data"], x - off.x, y - off.y) + off.z


# --- arbres ------------------------------------------------------------------------------------------------------

func _model_file(zone_dir: String, species: String, stage: String) -> Dictionary:
	if not species_model.has(species):
		return {"ok": false, "error": "l'essence %s n'a pas de modèle dans massif/index.json : la vue ne devine pas" % species}
	var m: Dictionary = species_model[species]
	var name := str(m["model"]) if str(m["kind"]) == "generic" else "%s_%s" % [str(m["model"]), stage]
	return {"ok": true, "error": "", "path": zone_dir.path_join("assets").path_join("trees").path_join(name + ".glb")}


func _load_model(path: String) -> Dictionary:
	if not model_cache.has(path):
		model_cache[path] = Loader.load_glb(path)
	return model_cache[path]


func _material_for(res: Dictionary) -> Variant:
	var extras: Dictionary = res["extras"]
	var color := ""
	if extras.has("feuillage") and extras["feuillage"].has("couleur"):
		color = str(extras["feuillage"]["couleur"])
	elif extras.has("groupe"):
		color = str(cfg["foliage"]["color_by_group"].get(str(extras["groupe"]), ""))
	if color == "":
		return null
	if not _materials.has(color):
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(color)
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		_materials[color] = m
	return _materials[color]


func _build_block(zone_dir: String, id: String) -> Dictionary:
	var b: Dictionary = blocks[id]
	var data: Dictionary = b["data"]
	var off: Vector3 = b["off"]
	var root := Node3D.new()
	root.name = "bloc_" + id
	root.position = Frame.block_to_godot(off.x, off.y, off.z)
	add_child(root)
	var ground := MeshInstance3D.new()
	ground.mesh = Terrain.build_mesh(data)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.36, 0.33, 0.24)
	gm.cull_mode = BaseMaterial3D.CULL_DISABLED
	ground.material_override = gm
	ground.name = "sol"
	root.add_child(ground)
	var groups := {}   # "case|chemin" -> {path, chunk, items: [Transform3D relative au bloc]}
	for t in data["trees"]:
		var mf := _model_file(zone_dir, str(t["species"]), str(t["stage"]))
		if not mf["ok"]:
			return {"ok": false, "error": "%s : arbre %s : %s" % [id, str(t["tree_id"]), mf["error"]]}
		var res := _load_model(mf["path"])
		if not res["ok"]:
			return {"ok": false, "error": res["error"]}
		if _material_for(res) == null:
			return {"ok": false, "error": "%s : ni feuillage.couleur ni groupe connu dans les extras : la vue ne devine pas la couleur" % mf["path"]}
		var extras: Dictionary = res["extras"]
		var height := float(res["height_m"])
		var sy := float(t["h"]) / height
		var sxz := sy
		var rayon := float(extras.get("rayon_houppier_ref_m", 0.0))
		if rayon > 0.0 and float(t["cw"]) > 0.0:
			sxz = float(t["cw"]) / (2.0 * rayon)
		var yaw := Hashing.unit(Hashing.mix(Hashing.of_string(zone + "|" + str(t["tree_id"])), 7)) * TAU
		var basis := Basis(Vector3.UP, yaw) * Basis.from_scale(Vector3(sxz, sy, sxz))
		var key := Vector2i(floori(float(t["x"]) / CHUNK_M), floori(float(t["y"]) / CHUNK_M))
		var gk := "%d,%d|%s" % [key.x, key.y, mf["path"]]
		if not groups.has(gk):
			groups[gk] = {"path": mf["path"], "items": []}
		groups[gk]["items"].append(Transform3D(basis, Frame.block_to_godot(float(t["x"]), float(t["y"]), float(t["z"]))))
		stats["trees"] += 1
		if str(species_model[str(t["species"])]["kind"]) == "generic":
			stats["generic_trees"] += 1
		if str(extras.get("calage", "")) == "non calé":
			stats["non_cale_trees"] += 1
	for gk in groups:
		var grp: Dictionary = groups[gk]
		var res := _load_model(grp["path"])
		var fade := float(cfg["lod"]["fade_margin_m"])
		var items: Array = grp["items"]
		var center := Vector3.ZERO
		for tr in items:
			center += tr.origin
		center /= float(items.size())
		for k in range(3):
			var lv: Dictionary = res["levels"][k]
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = lv["mesh"]
			mm.instance_count = items.size()
			for i in range(items.size()):
				mm.set_instance_transform(i, Transform3D(items[i].basis, items[i].origin - center))
			var mi := MultiMeshInstance3D.new()
			mi.multimesh = mm
			mi.position = center
			mi.material_override = _material_for(res)
			mi.visibility_range_begin = float(lv["visibility_range_begin"])
			mi.visibility_range_end = float(lv["visibility_range_end"])
			mi.visibility_range_begin_margin = fade if mi.visibility_range_begin > 0.0 else 0.0
			mi.visibility_range_end_margin = fade if mi.visibility_range_end > 0.0 else 0.0
			mi.name = "arbres_%s_lod%d" % [str(gk).validate_node_name(), k]
			root.add_child(mi)
	if bool(stats["non_cale_trees"] > 0) and notes.find("non calé") < 0:
		notes.append("non calé")
	return {"ok": true, "error": ""}


# --- herbe et semis ------------------------------------------------------------------------------------------------

func _make_flat_normal() -> void:
	# normale plate (0,5 ; 0,5 ; 1) : le shader lit une texture de normales, nous n'en copions aucune (origine non établie)
	var img := Image.create(4, 4, false, Image.FORMAT_RGB8)
	img.fill(Color(0.5, 0.5, 1.0))
	_flat_normal = ImageTexture.create_from_image(img)


func _set_global_shader_textures() -> void:
	# textures globales de SimpleGrassTextured, fabriquées ici : déplacement et mouvement neutres, motif de vent en bruit
	var neutral := Image.create(4, 4, false, Image.FORMAT_RGB8)
	neutral.fill(Color(0.5, 0.5, 0.0))
	RenderingServer.global_shader_parameter_set("sgt_normal_displacement", ImageTexture.create_from_image(neutral))
	var black := Image.create(4, 4, false, Image.FORMAT_RGB8)
	black.fill(Color(0, 0, 0))
	RenderingServer.global_shader_parameter_set("sgt_motion_texture", ImageTexture.create_from_image(black))
	var noise := FastNoiseLite.new()
	noise.seed = 1
	noise.frequency = 0.05
	var img := noise.get_image(64, 64)
	RenderingServer.global_shader_parameter_set("sgt_wind_pattern", ImageTexture.create_from_image(img))


## Brin d'herbe : deux carrés croisés de 1 m de côté, pied en y = 0 (l'échelle vient de viewer.grass.blade_height_m).
static func blade_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for rot in [0.0, PI / 2.0]:
		var dx := Vector3(cos(rot), 0, sin(rot)) * 0.5
		var q := [-dx, dx, dx + Vector3.UP, -dx + Vector3.UP]
		var uv := [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.UP)
			st.set_uv(uv[i])
			st.add_vertex(q[i])
	return st.commit()


func _make_grass_nodes() -> void:
	var g: Dictionary = cfg["grass"]
	_grass_material = ShaderMaterial.new()
	_grass_material.shader = GRASS_SHADER
	_grass_material.set_shader_parameter("albedo", Color(str(g["color"])))
	_grass_material.set_shader_parameter("texture_albedo", GRASS_TEXTURE)
	_grass_material.set_shader_parameter("texture_normal", _flat_normal)
	_grass_material.set_shader_parameter("texture_frames", Vector2(1, 1))
	_grass_material.set_shader_parameter("light_mode", 0)
	_grass_material.set_shader_parameter("interactive_mode", false)
	_grass_material.set_shader_parameter("scale_h", float(g["blade_height_m"]))
	_grass_material.set_shader_parameter("scale_w", float(g["blade_height_m"]))
	_grass_material.set_shader_parameter("grass_size_y", float(g["blade_height_m"]))
	_grass_mmi = MultiMeshInstance3D.new()
	_grass_mmi.name = "herbe"
	_grass_mmi.material_override = _grass_material
	_grass_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_grass_mmi)


func _load_seedling_models(zone_dir: String) -> Dictionary:
	for id in blocks:
		var data: Dictionary = blocks[id]["data"]
		if not bool(data["seedlings_simulated"]):
			continue
		for c in data["cells"]:
			for s in c["seedlings"]:
				var sp := str(s["species"])
				if seedling_models.has(sp):
					continue
				var mf := _model_file(zone_dir, sp, "young")
				if not mf["ok"] or not FileAccess.file_exists(mf["path"]):
					seedling_models[sp] = {"missing": "pas de modèle « young » pour l'essence %s" % sp}
					notes.append("semis de l'essence %s non dessinés : pas de modèle" % sp)
					continue
				var res := _load_model(mf["path"])
				if not res["ok"]:
					return {"ok": false, "error": res["error"]}
				seedling_models[sp] = {"path": mf["path"], "res": res}
	return {"ok": true, "error": ""}


## Calcul de l'herbe et des semis autour de `center` (repère du fichier relatif à l'origine de référence) : fil de travail,
## lit seulement des données déjà chargées.
func _compute(id: int, center: Vector2) -> Dictionary:
	var g: Dictionary = cfg["grass"]
	var radius := float(g["radius_m"])
	var cells := []
	var seedling_cells := []
	var unknown_cover := 0
	var cell_size := 0.0
	for bid in blocks:
		var b: Dictionary = blocks[bid]
		var off: Vector3 = b["off"]
		cell_size = float(b["data"]["ground"]["resolution_m"])
		for c in b["data"]["cells"]:
			var cx := float(c["x"]) + off.x
			var cy := float(c["y"]) + off.y
			var d := Vector2(cx, cy).distance_to(center)
			if d > radius:
				continue
			if c["herb_cover"] == null:
				unknown_cover += 1
			cells.append({"cell_id": int(c["cell_id"]), "x": cx, "y": cy, "herb_cover": c["herb_cover"], "d": d})
			if bool(b["data"]["seedlings_simulated"]):
				seedling_cells.append({"cell": c, "cx": cx, "cy": cy, "d": d})
	cells.sort_custom(func(a, b): return a["d"] < b["d"])
	var built := GrassLib.build(zone, cells, cell_size, g)
	var pos: PackedVector2Array = built["positions"]
	var zh := Hashing.of_string(zone + "|herbe")
	var buf := PackedFloat32Array()
	buf.resize(pos.size() * 12)
	for i in range(pos.size()):
		var p := pos[i]
		var h := height_world(p.x, p.y)
		if is_nan(h):
			h = 0.0
		var yaw := Hashing.unit(Hashing.mix(zh, i)) * TAU
		var cs := cos(yaw)
		var sn := sin(yaw)
		var o := i * 12
		# transformation : rotation autour de y, position (x, h, -y) relative au centre (x, 0, -y)
		buf[o] = cs
		buf[o + 1] = 0.0
		buf[o + 2] = sn
		buf[o + 3] = p.x - center.x
		buf[o + 4] = 0.0
		buf[o + 5] = 1.0
		buf[o + 6] = 0.0
		buf[o + 7] = h
		buf[o + 8] = -sn
		buf[o + 9] = 0.0
		buf[o + 10] = cs
		buf[o + 11] = -(p.y - center.y)
	var seedlings := {}   # essence -> Array[Transform3D] relatives au centre
	var cell_area_ha := cell_size * cell_size / M2_PER_HA
	for sc in seedling_cells:
		var c: Dictionary = sc["cell"]
		for s in c["seedlings"]:
			var sp := str(s["species"])
			if not seedling_models.has(sp) or seedling_models[sp].has("missing"):
				continue
			var n := SeedLib.count(zone, int(c["cell_id"]), sp, float(s["seedlings_ha"]), cell_area_ha)
			if n == 0:
				continue
			var res: Dictionary = seedling_models[sp]["res"]
			var sc_h := float(s["h_mean_m"]) / float(res["height_m"])
			if not seedlings.has(sp):
				seedlings[sp] = []
			for p in SeedLib.positions(zone, int(c["cell_id"]), sc["cx"], sc["cy"], cell_size, sp, n):
				var h2 := height_world(p.x, p.y)
				seedlings[sp].append(Transform3D(Basis.from_scale(Vector3(sc_h, sc_h, sc_h)), Vector3(p.x - center.x, 0.0 if is_nan(h2) else h2, -(p.y - center.y))))
	return {"id": id, "center": center, "buffer": buf, "count": pos.size(), "truncated": built["truncated"], "message": built["message"], "seedlings": seedlings, "unknown_cover": unknown_cover}


func request_grass(center: Vector2) -> void:
	_last_center = center
	var id := _gate.next_id()           # toute requête en vol devient périmée
	if _thread != null and _thread.is_started():
		_pending_center = center
		return
	_thread = Thread.new()
	_thread.start(_compute.bind(id, center))


func _poll_thread() -> void:
	if _thread == null or not _thread.is_started() or _thread.is_alive():
		return
	var r: Dictionary = _thread.wait_to_finish()
	if _gate.accept(int(r["id"])):
		_apply_grass(r)
	if _pending_center != null:
		var c: Vector2 = _pending_center
		_pending_center = null
		_thread = Thread.new()
		_thread.start(_compute.bind(_gate.next_id(), c))
		_last_center = c


## Attend la fin du calcul en cours (autotest : mêmes comptes à chaque passage).
func wait_for_grass() -> void:
	while _thread != null and _thread.is_started():
		var r: Dictionary = _thread.wait_to_finish()
		if _gate.accept(int(r["id"])):
			_apply_grass(r)
		if _pending_center != null:
			var c: Vector2 = _pending_center
			_pending_center = null
			_thread = Thread.new()
			_thread.start(_compute.bind(_gate.next_id(), c))


func _apply_grass(r: Dictionary) -> void:
	var c: Vector2 = r["center"]
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = blade_mesh()
	mm.instance_count = int(r["count"])
	mm.buffer = r["buffer"]
	_grass_mmi.multimesh = mm
	_grass_mmi.position = Vector3(c.x, 0.0, -c.y)
	stats["grass_instances"] = int(r["count"])
	stats["truncated"] = bool(r["truncated"])
	grass_message = str(r["message"])
	if int(r["unknown_cover"]) > 0:
		grass_message += ("\n" if grass_message != "" else "") + "%d cellules au couvert herbacé inconnu : sans herbe" % int(r["unknown_cover"])
	for n in _seedling_nodes:
		n.queue_free()
	_seedling_nodes.clear()
	var total := 0
	for sp in r["seedlings"]:
		var items: Array = r["seedlings"][sp]
		var res: Dictionary = seedling_models[sp]["res"]
		var smm := MultiMesh.new()
		smm.transform_format = MultiMesh.TRANSFORM_3D
		smm.mesh = res["levels"][0]["mesh"]
		smm.instance_count = items.size()
		for i in range(items.size()):
			smm.set_instance_transform(i, items[i])
		var mi := MultiMeshInstance3D.new()
		mi.multimesh = smm
		mi.position = Vector3(c.x, 0.0, -c.y)
		mi.material_override = _material_for(res)
		mi.name = "semis_" + sp
		add_child(mi)
		_seedling_nodes.append(mi)
		total += items.size()
	stats["seedlings"] = total


func _process(_delta: float) -> void:
	_poll_thread()
	if camera == null:
		return
	var cam_xy := Vector2(camera.position.x, -camera.position.z)
	if cam_xy.distance_to(_last_center) > float(cfg["grass"]["recenter_distance_m"]):
		request_grass(cam_xy)


func _exit_tree() -> void:
	if _thread != null and _thread.is_started():
		_thread.wait_to_finish()


## Texte du bandeau (cinq lignes au plus) pour le bloc du point demandé.
func banner_text(block_id: String) -> String:
	return Banner.text(blocks[block_id]["data"], index)
