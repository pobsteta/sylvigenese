class_name Station
extends RefCounted
## Terrain fictif + gradients stationnels (F humidite, R reaction, T temperature).
## Dans le vrai projet : MNT LiDAR HD et rasters sylvostation a la place du bruit.

const SIZE := 2000.0   # metres
const N := 129         # sommets par cote

const TYPE_NAMES := [
	"Sèche acide", "Sèche neutre", "Sèche calcaire",
	"Fraîche acide", "Fraîche neutre", "Fraîche calcaire",
	"Humide acide", "Humide neutre", "Humide calcaire",
]
const TYPE_COLORS := [
	Color("#b89a5a"), Color("#c2ad6e"), Color("#d6cfa0"),
	Color("#7d8a4a"), Color("#6f9a55"), Color("#8fb26a"),
	Color("#4f8a7a"), Color("#3f8f96"), Color("#4a7fb0"),
]

var cell := SIZE / float(N - 1)
var h := PackedFloat32Array()
var f := PackedFloat32Array()
var r := PackedFloat32Array()
var t := PackedFloat32Array()


func _init(seed_value: int = 7) -> void:
	h.resize(N * N)
	f.resize(N * N)
	r.resize(N * N)
	t.resize(N * N)

	var relief := FastNoiseLite.new()
	relief.seed = seed_value
	relief.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	relief.frequency = 0.0011
	relief.fractal_octaves = 4

	var geol := FastNoiseLite.new()
	geol.seed = seed_value + 1
	geol.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	geol.frequency = 0.0009
	geol.fractal_octaves = 2

	for j in N:
		for i in N:
			var x := i * cell
			var z := j * cell
			var talweg := 1000.0 + 220.0 * sin(x / 320.0)
			var dz := (z - talweg) / 130.0
			h[j * N + i] = 600.0 + 220.0 * relief.get_noise_2d(x, z) - 70.0 * exp(-0.5 * dz * dz)

	for j in N:
		for i in N:
			var k := j * N + i
			# position topographique : altitude - moyenne du voisinage
			var sum := 0.0
			var cnt := 0
			for dj in [-4, -2, 0, 2, 4]:
				for di in [-4, -2, 0, 2, 4]:
					var ii := clampi(i + di, 0, N - 1)
					var jj := clampi(j + dj, 0, N - 1)
					sum += h[jj * N + ii]
					cnt += 1
			var tpi := h[k] - sum / cnt
			var gx := (h[j * N + mini(i + 1, N - 1)] - h[j * N + maxi(i - 1, 0)]) / (2.0 * cell)
			var gz := (h[mini(j + 1, N - 1) * N + i] - h[maxi(j - 1, 0) * N + i]) / (2.0 * cell)
			var slope := sqrt(gx * gx + gz * gz)
			var x := i * cell
			var z := j * cell
			f[k] = clampf(5.2 - tpi * 0.22 - slope * 2.5, 1.5, 9.0)
			r[k] = clampf(4.8 + 5.0 * geol.get_noise_2d(x, z), 1.5, 8.5)
			t[k] = clampf(6.5 - (h[k] - 400.0) / 100.0 * 0.6, 2.0, 8.0)


func _bilinear(a: PackedFloat32Array, x: float, z: float) -> float:
	var gx := clampf(x / cell, 0.0, N - 1.001)
	var gz := clampf(z / cell, 0.0, N - 1.001)
	var i := int(gx)
	var j := int(gz)
	var fx := gx - i
	var fz := gz - j
	var k := j * N + i
	return lerpf(lerpf(a[k], a[k + 1], fx), lerpf(a[k + N], a[k + N + 1], fx), fz)


func height_at(x: float, z: float) -> float:
	return _bilinear(h, x, z)


func f_at(x: float, z: float) -> float:
	return _bilinear(f, x, z)


func r_at(x: float, z: float) -> float:
	return _bilinear(r, x, z)


func t_at(x: float, z: float) -> float:
	return _bilinear(t, x, z)


static func type_index(fv: float, rv: float) -> int:
	var a := 0 if fv < 4.2 else (1 if fv < 6.5 else 2)
	var b := 0 if rv < 3.8 else (1 if rv < 6.0 else 2)
	return a * 3 + b


func build_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in N:
		for i in N:
			var k := j * N + i
			var c: Color = TYPE_COLORS[type_index(f[k], r[k])]
			st.set_color(c.darkened(0.2).srgb_to_linear())
			st.add_vertex(Vector3(i * cell, h[k], j * cell))
	for j in N - 1:
		for i in N - 1:
			var a := j * N + i
			st.add_index(a)
			st.add_index(a + 1)
			st.add_index(a + N)
			st.add_index(a + 1)
			st.add_index(a + N + 1)
			st.add_index(a + N)
	st.generate_normals()
	return st.commit()
