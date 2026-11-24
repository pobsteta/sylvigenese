class_name Forest
extends Node3D
## Peuplement : un arbre = une instance MultiMesh. La croissance (hauteur selon
## l'age, mortalite) est calculee dans le shader a partir de l'annee courante,
## donc changer d'annee ne coute rien cote CPU.
## Dans le vrai projet : positions issues de lidR, trajectoires issues de GAMA.

const SPACING := 8.0
const CHUNKS := 8
const COVER_CELL := 20.0

const SHADER_CODE := """
shader_type spatial;

uniform float annee = 60.0;
uniform float hmax = 30.0;
uniform float k = 0.03;
uniform float houppier = 0.4;
uniform float longev = 200.0;
uniform vec3 couleur = vec3(0.03, 0.2, 0.03);  // lineaire

varying float v_tint;

void vertex() {
	float birth = INSTANCE_CUSTOM.x;
	float vigor = INSTANCE_CUSTOM.y;
	float age = annee - birth;
	float h = 0.0;
	if (age > 0.0) {
		h = hmax * (0.35 + 0.65 * vigor) * pow(1.0 - exp(-k * age), 1.4);
		float seuil = 0.25 + 0.3 * clamp(age / 150.0, 0.0, 1.0);
		if (vigor < seuil) { h = 0.0; }
		if (age > longev * (0.7 + 0.6 * vigor)) { h = 0.0; }
	}
	float w = max(houppier * h, 0.25 * step(0.001, h));
	VERTEX *= vec3(w, h, w);
	v_tint = INSTANCE_CUSTOM.z;
}

void fragment() {
	ALBEDO = couleur * (0.8 + 0.4 * v_tint);
	ROUGHNESS = 0.9;
}
"""

var station: Station
var species: Array = []
var year := 60.0

var _pos := PackedVector3Array()
var _sp := PackedInt32Array()
var _vigor := PackedFloat32Array()
var _birth := PackedFloat32Array()
var _cells: Array = []
var _cover_n := 0
var _materials: Array = []


func setup(p_station: Station, p_species: Array) -> void:
	station = p_station
	species = p_species
	var nsp := species.size()

	var shader := Shader.new()
	shader.code = SHADER_CODE
	var meshes: Array = []
	for sp in species:
		meshes.append(_build_mesh(sp, shader))

	_cover_n = int(ceil(Station.SIZE / COVER_CELL))
	_cells.resize(_cover_n * _cover_n)
	for i in _cells.size():
		_cells[i] = []

	var groups: Array = []
	groups.resize(CHUNKS * CHUNKS * nsp)
	for i in groups.size():
		groups[i] = []

	var rng := RandomNumberGenerator.new()
	rng.seed = 2026
	var n := int(Station.SIZE / SPACING)
	var chunk_size := Station.SIZE / CHUNKS
	var suit := PackedFloat32Array()
	suit.resize(nsp)

	for gz in n:
		for gx in n:
			if rng.randf() < 0.08:
				continue
			var x := (gx + rng.randf()) * SPACING
			var z := (gz + rng.randf()) * SPACING
			var fv := station.f_at(x, z)
			var rv := station.r_at(x, z)
			var tv := station.t_at(x, z)
			var total := 0.0
			for s in nsp:
				var v := Biome.suitability(species[s], fv, rv, tv)
				v = v * v
				suit[s] = v
				total += v
			if total < 0.003:
				continue
			var pick := rng.randf() * total
			var chosen := nsp - 1
			for s in nsp:
				pick -= suit[s]
				if pick <= 0.0:
					chosen = s
					break
			var s_lin := sqrt(suit[chosen])
			var vig := clampf(sqrt(s_lin) * rng.randf_range(0.5, 1.0), 0.26, 1.0)
			var b := rng.randf_range(-45.0, 20.0)
			if rng.randf() < 0.18:
				b = rng.randf_range(30.0, 150.0)
			var idx := _pos.size()
			_pos.append(Vector3(x, station.height_at(x, z), z))
			_sp.append(chosen)
			_vigor.append(vig)
			_birth.append(b)
			var cx := mini(int(x / chunk_size), CHUNKS - 1)
			var cz := mini(int(z / chunk_size), CHUNKS - 1)
			groups[(cz * CHUNKS + cx) * nsp + chosen].append(idx)
			var ccx := mini(int(x / COVER_CELL), _cover_n - 1)
			var ccz := mini(int(z / COVER_CELL), _cover_n - 1)
			_cells[ccz * _cover_n + ccx].append(idx)

	for cz in CHUNKS:
		for cx in CHUNKS:
			var center := Vector3((cx + 0.5) * chunk_size, 0.0, (cz + 0.5) * chunk_size)
			center.y = station.height_at(center.x, center.z)
			for s in nsp:
				var list: Array = groups[(cz * CHUNKS + cx) * nsp + s]
				if list.is_empty():
					continue
				var mm := MultiMesh.new()
				mm.transform_format = MultiMesh.TRANSFORM_3D
				mm.use_custom_data = true
				mm.mesh = meshes[s]
				mm.instance_count = list.size()
				for i in list.size():
					var ti: int = list[i]
					var rot := Basis(Vector3.UP, rng.randf() * TAU)
					mm.set_instance_transform(i, Transform3D(rot, _pos[ti] - center))
					mm.set_instance_custom_data(i, Color(_birth[ti], _vigor[ti], rng.randf(), 0.0))
				var mmi := MultiMeshInstance3D.new()
				mmi.multimesh = mm
				mmi.position = center
				var half := chunk_size * 0.5 + 12.0
				mmi.custom_aabb = AABB(Vector3(-half, -250.0, -half), Vector3(half * 2.0, 520.0, half * 2.0))
				add_child(mmi)

	set_year(year)


func tree_count() -> int:
	return _pos.size()


func set_year(y: float) -> void:
	year = y
	for m in _materials:
		var mat: ShaderMaterial = m
		mat.set_shader_parameter("annee", y)


## Meme formule que le shader, cote CPU (pour le couvert et l'affichage).
func tree_height(ti: int, y: float) -> float:
	var sp: Dictionary = species[_sp[ti]]
	var age := y - _birth[ti]
	if age <= 0.0:
		return 0.0
	var vig := _vigor[ti]
	if vig < 0.25 + 0.3 * clampf(age / 150.0, 0.0, 1.0):
		return 0.0
	var longev: float = sp["longev"]
	if age > longev * (0.7 + 0.6 * vig):
		return 0.0
	var hmax: float = sp["hmax"]
	var k: float = sp["k"]
	return hmax * (0.35 + 0.65 * vig) * pow(1.0 - exp(-k * age), 1.4)


## Taux de couvert (0..1) de la cellule de 20 m contenant le point.
func cover_at(x: float, z: float) -> float:
	var ccx := clampi(int(x / COVER_CELL), 0, _cover_n - 1)
	var ccz := clampi(int(z / COVER_CELL), 0, _cover_n - 1)
	var list: Array = _cells[ccz * _cover_n + ccx]
	var area := 0.0
	for item in list:
		var ti: int = item
		var hgt := tree_height(ti, year)
		if hgt > 0.0:
			var ratio: float = species[_sp[ti]]["houppier"]
			var w := ratio * hgt
			area += PI * w * w * 0.25
	return clampf(area / (COVER_CELL * COVER_CELL), 0.0, 1.0)


func _build_mesh(sp: Dictionary, shader: Shader) -> ArrayMesh:
	# Maillage unitaire : hauteur 1, largeur de houppier 1. Le shader met a l'echelle.
	var am := ArrayMesh.new()

	var trunk := CylinderMesh.new()
	trunk.top_radius = 0.02
	trunk.bottom_radius = 0.035
	trunk.height = 0.5
	trunk.radial_segments = 5
	trunk.rings = 0
	trunk.cap_top = false
	trunk.cap_bottom = false
	var st := SurfaceTool.new()
	st.append_from(trunk, 0, Transform3D(Basis(), Vector3(0.0, 0.25, 0.0)))
	st.commit(am)

	var st2 := SurfaceTool.new()
	var forme: String = sp["forme"]
	if forme == "conifere":
		var cone := CylinderMesh.new()
		cone.top_radius = 0.0
		cone.bottom_radius = 0.5
		cone.height = 0.8
		cone.radial_segments = 7
		cone.rings = 0
		cone.cap_top = false
		st2.append_from(cone, 0, Transform3D(Basis(), Vector3(0.0, 0.6, 0.0)))
	else:
		var sph := SphereMesh.new()
		sph.radius = 0.5
		sph.height = 0.62
		sph.radial_segments = 7
		sph.rings = 3
		st2.append_from(sph, 0, Transform3D(Basis(), Vector3(0.0, 0.69, 0.0)))
	st2.commit(am)

	var colors: Array = [sp["tronc"], sp["couleur"]]
	for surf in 2:
		var mat := ShaderMaterial.new()
		mat.shader = shader
		var hex: String = colors[surf]
		var c := Color(hex).srgb_to_linear()
		mat.set_shader_parameter("couleur", Vector3(c.r, c.g, c.b))
		mat.set_shader_parameter("hmax", sp["hmax"])
		mat.set_shader_parameter("k", sp["k"])
		mat.set_shader_parameter("houppier", sp["houppier"])
		mat.set_shader_parameter("longev", sp["longev"])
		am.surface_set_material(surf, mat)
		_materials.append(mat)
	return am
