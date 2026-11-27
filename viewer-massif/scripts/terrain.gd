## Terrain d'un bloc (plan T6) : la MNT de la grille de 25 m (`ground.z`, altitudes NGF-IGN69 aux centres de cellule, ligne 0 au
## nord), PAS le LiDAR à 1 m : le sol est lisse (dit à l'écran). Les hauteurs rendues sont relatives à l'origine du bloc.
extends RefCounted

const Frame := preload("res://scripts/frame.gd")


## Altitude (m, relative à origin.z) au point (x, y) du bloc : interpolation bilinéaire entre centres de cellule, valeur du
## bord au-delà du premier et du dernier centre.
static func height_at(block: Dictionary, x: float, y: float) -> float:
	var g: Dictionary = block["ground"]
	var res := float(g["resolution_m"])
	var nx := int(g["nx"])
	var ny := int(g["ny"])
	var fx := clampf(x / res - 0.5, 0.0, float(nx - 1))
	var fy := clampf((float(ny) * res - y) / res - 0.5, 0.0, float(ny - 1))
	var j0 := mini(int(floor(fx)), nx - 2)
	var i0 := mini(int(floor(fy)), ny - 2)
	var tx := fx - float(j0)
	var ty := fy - float(i0)
	var z: Array = g["z"]
	var a: float = lerpf(float(z[i0 * nx + j0]), float(z[i0 * nx + j0 + 1]), tx)
	var b: float = lerpf(float(z[(i0 + 1) * nx + j0]), float(z[(i0 + 1) * nx + j0 + 1]), tx)
	return lerpf(a, b, ty) - float(block["origin"]["z"])


## Maillage du terrain en coordonnées de Godot (repère T6), relatif à l'origine du bloc ; les bords sont prolongés jusqu'à
## l'arête du bloc pour que deux blocs voisins se touchent.
static func build_mesh(block: Dictionary) -> ArrayMesh:
	var g: Dictionary = block["ground"]
	var res := float(g["resolution_m"])
	var nx := int(g["nx"])
	var ny := int(g["ny"])
	var xs := PackedFloat32Array([0.0])
	for j in range(nx):
		xs.append((float(j) + 0.5) * res)
	xs.append(float(nx) * res)
	var ys := PackedFloat32Array([float(ny) * res])
	for i in range(ny):
		ys.append(float(ny) * res - (float(i) + 0.5) * res)
	ys.append(0.0)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for r in range(ys.size() - 1):
		for c in range(xs.size() - 1):
			var p00 := Frame.block_to_godot(xs[c], ys[r], height_at(block, xs[c], ys[r]))
			var p10 := Frame.block_to_godot(xs[c + 1], ys[r], height_at(block, xs[c + 1], ys[r]))
			var p01 := Frame.block_to_godot(xs[c], ys[r + 1], height_at(block, xs[c], ys[r + 1]))
			var p11 := Frame.block_to_godot(xs[c + 1], ys[r + 1], height_at(block, xs[c + 1], ys[r + 1]))
			for v in [p00, p10, p11, p00, p11, p01]:
				st.add_vertex(v)
	st.generate_normals()
	return st.commit()
