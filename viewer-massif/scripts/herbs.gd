class_name Herbs
extends Node3D
## Strate herbacee : generee uniquement autour du point regarde, par dalles de 10 m.
## Chaque plante est tiree selon l'adequation station (F, R) + lumiere au sol,
## elle-meme deduite du couvert des arbres. C'est le niveau "petite plante".

const CHUNK := 10.0
const RADIUS := 3
const PER_CHUNK := 260
const MAX_DIST := 160.0

# Feuilles vues des deux cotes, eclairees comme si elles regardaient vers le haut.
const SHADER_CODE := """
shader_type spatial;
render_mode cull_disabled;

void fragment() {
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 1.0;
	NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
}
"""

var station: Station
var forest: Forest
var plants: Array = []

var _meshes: Array = []
var _chunks := {}
var _material: ShaderMaterial


func setup(p_station: Station, p_forest: Forest, p_plants: Array) -> void:
	station = p_station
	forest = p_forest
	plants = p_plants
	var shader := Shader.new()
	shader.code = SHADER_CODE
	_material = ShaderMaterial.new()
	_material.shader = shader
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	for p in plants:
		_meshes.append(_build_plant(p, rng))


func invalidate() -> void:
	for key in _chunks.keys():
		var node: Node3D = _chunks[key]
		node.queue_free()
	_chunks.clear()


func chunk_count() -> int:
	return _chunks.size()


func update(focus: Vector3, cam_dist: float) -> void:
	if cam_dist > MAX_DIST:
		if not _chunks.is_empty():
			invalidate()
		return
	var c := Vector2i(floori(focus.x / CHUNK), floori(focus.z / CHUNK))
	var wanted := {}
	var created := 0
	for dz in range(-RADIUS, RADIUS + 1):
		for dx in range(-RADIUS, RADIUS + 1):
			var key := c + Vector2i(dx, dz)
			wanted[key] = true
			if not _chunks.has(key) and created < 3:
				_chunks[key] = _build_chunk(key)
				created += 1
	for key in _chunks.keys():
		if not wanted.has(key):
			var node: Node3D = _chunks[key]
			node.queue_free()
			_chunks.erase(key)


func _build_chunk(key: Vector2i) -> Node3D:
	var holder := Node3D.new()
	var ox := key.x * CHUNK
	var oz := key.y * CHUNK
	holder.position = Vector3(ox, 0.0, oz)
	add_child(holder)

	var rng := RandomNumberGenerator.new()
	rng.seed = hash(key)
	var nsp := plants.size()
	var lists: Array = []
	for s in nsp:
		lists.append([])
	var weights := PackedFloat32Array()
	weights.resize(nsp)

	for n in PER_CHUNK:
		var x := ox + rng.randf() * CHUNK
		var z := oz + rng.randf() * CHUNK
		if x < 0.0 or z < 0.0 or x > Station.SIZE or z > Station.SIZE:
			continue
		var fv := station.f_at(x, z)
		var rv := station.r_at(x, z)
		var lv := 8.5 - 6.5 * forest.cover_at(x, z)
		var total := 0.0
		for s in nsp:
			var w := Biome.herb_suitability(plants[s], fv, rv, lv)
			weights[s] = w
			total += w
		if total < 0.05 or rng.randf() > minf(1.0, total * 1.5):
			continue  # sol nu
		var pick := rng.randf() * total
		var chosen := nsp - 1
		for s in nsp:
			pick -= weights[s]
			if pick <= 0.0:
				chosen = s
				break
		var size := rng.randf_range(0.6, 1.3)
		var b := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * size)
		lists[chosen].append(Transform3D(b, Vector3(x - ox, station.height_at(x, z), z - oz)))

	for s in nsp:
		var list: Array = lists[s]
		if list.is_empty():
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = _meshes[s]
		mm.instance_count = list.size()
		for i in list.size():
			var tr: Transform3D = list[i]
			mm.set_instance_transform(i, tr)
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = _material
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		holder.add_child(mmi)
	return holder


static func _tri(st: SurfaceTool, a: Vector3, ca: Color, b: Vector3, cb: Color, c: Vector3, cc: Color) -> void:
	st.set_normal(Vector3.UP)
	st.set_color(ca)
	st.add_vertex(a)
	st.set_normal(Vector3.UP)
	st.set_color(cb)
	st.add_vertex(b)
	st.set_normal(Vector3.UP)
	st.set_color(cc)
	st.add_vertex(c)


## Petite plante procedurale : des "brins" en rosette (tiges, frondes ou feuilles
## de graminee), plus ou moins etales selon le port. Chaque brin peut porter des
## paires de folioles, et la plante une fleur ou des baies.
func _build_plant(p: Dictionary, rng: RandomNumberGenerator) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n: int = int(p["brins"])
	var leaflets: int = int(p["folioles"])
	var hgt: float = p["h"]
	var width: float = p["largeur"]
	var lean: float = p["port"]
	var hex: String = p["couleur"]
	var col := Color(hex).srgb_to_linear()
	var dark := col.darkened(0.35)
	var light := col.lightened(0.12)
	var stem_w := width if leaflets == 0 else 0.006 + hgt * 0.006
	for b in n:
		var a := TAU * (b + rng.randf() * 0.6) / n
		var dir := Vector3(cos(a), 0.0, sin(a))
		var side := Vector3(-dir.z, 0.0, dir.x)
		var blade := hgt * rng.randf_range(0.75, 1.0)
		# axe du brin : courbe qui s'incline vers l'exterieur
		var pts: Array = []
		for i in 5:
			var t := i / 4.0
			pts.append(dir * (blade * lean * pow(t, 1.5)) + Vector3.UP * (blade * (t - 0.35 * lean * t * t)))
		for i in 4:
			var p0: Vector3 = pts[i]
			var p1: Vector3 = pts[i + 1]
			var w0 := side * stem_w * 0.5 * (1.0 - i / 4.0)
			var w1 := side * stem_w * 0.5 * (1.0 - (i + 1) / 4.0)
			var ca := dark.lerp(col, i / 4.0)
			var cb := dark.lerp(col, (i + 1) / 4.0)
			_tri(st, p0 - w0, ca, p0 + w0, ca, p1 + w1, cb)
			_tri(st, p0 - w0, ca, p1 + w1, cb, p1 - w1, cb)
		for m in leaflets:
			var t := (m + 1.0) / (leaflets + 1.0)
			var fi := t * 4.0
			var i0 := mini(int(fi), 3)
			var q0: Vector3 = pts[i0]
			var q1: Vector3 = pts[i0 + 1]
			var base := q0.lerp(q1, fi - i0)
			var tangent := (q1 - q0).normalized()
			var leaf := width * (1.0 - 0.6 * t) * rng.randf_range(0.85, 1.1)
			for sgn in [-1.0, 1.0]:
				var tip: Vector3 = base + side * sgn * leaf + tangent * leaf * 0.35 - Vector3.UP * leaf * 0.12
				_tri(st, base - tangent * leaf * 0.22, col, base + tangent * leaf * 0.22, col, tip, light)
	if p.has("fleur"):
		var fhex: String = p["fleur"]
		var fc := Color(fhex).srgb_to_linear()
		var s := maxf(width * 0.5, 0.025)
		for q in 5:
			var a := TAU * q / 5.0
			var top := Vector3(cos(a), 0.0, sin(a)) * hgt * lean * 0.35 + Vector3.UP * hgt * 0.9
			var d := Vector3(cos(a + 1.3), 0.0, sin(a + 1.3)) * s
			_tri(st, top - d, fc, top + d, fc, top + Vector3.UP * s * 1.8, fc)
	return st.commit()
