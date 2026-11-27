## Repère de la vue (plan T6). `massif/` : x est, y nord, z haut, en mètres relatifs à l'origine du bloc (EPSG:2154,
## altitude NGF-IGN69). Godot : x est, y haut, z = -nord (le nord est devant, le repère reste direct) : (x, y, z) -> (x, z, -y).
## Réserve : Vector3 est en flottants simples ; `godot_to_lambert` n'est exact au millimètre que pour des valeurs
## représentables (les positions du jeu sont relatives, donc petites ; seul le retour absolu est limité à environ 0,5 m
## vers 6,5 millions de mètres).
extends RefCounted


static func block_to_godot(x: float, y: float, z: float) -> Vector3:
	return Vector3(x, z, -y)


static func godot_to_block(v: Vector3) -> Vector3:
	return Vector3(v.x, -v.z, v.y)


static func lambert_to_godot(X: float, Y: float, Z: float, origin: Dictionary) -> Vector3:
	return block_to_godot(X - float(origin["x"]), Y - float(origin["y"]), Z - float(origin["z"]))


static func godot_to_lambert(v: Vector3, origin: Dictionary) -> Vector3:
	var b := godot_to_block(v)
	return Vector3(b.x + float(origin["x"]), b.y + float(origin["y"]), b.z + float(origin["z"]))
