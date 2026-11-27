## Herbe autour de la caméra (plan T8), réécrite d'après l'idée de godot-forest-demo (aucun code recopié) : nombre de brins
## proportionnel à `herb_cover` de la cellule (à couvert nul ou inconnu, cellule vide), tirage par hachage déterministe de
## (zone, cell_id, rang), plafond d'instances qui tronque ET le dit. `params` : clés de `config.yml` viewer.grass
## (`blades_per_m2_at_full_cover`, `max_instances`). Positions : x est, y nord, relatifs au bloc.
extends RefCounted

const Hashing := preload("res://scripts/hashing.gd")


static func positions(zone: String, cell_id: int, cx: float, cy: float, cell_size: float, herb_cover: float, params: Dictionary) -> PackedVector2Array:
	var out := PackedVector2Array()
	if herb_cover <= 0.0:
		return out
	var expected := float(params["blades_per_m2_at_full_cover"]) * cell_size * cell_size * herb_cover
	var whole := floori(expected)
	var zh := Hashing.of_string(zone)
	var h0 := Hashing.mix(zh, cell_id)
	var n := whole + (1 if Hashing.unit(Hashing.mix(h0, 0x7FFFFFF1)) < expected - float(whole) else 0)
	out.resize(n)
	for rank in range(n):
		var h := Hashing.mix(h0, rank)
		out[rank] = Vector2(cx + (Hashing.unit(Hashing.mix(h, 1)) - 0.5) * cell_size, cy + (Hashing.unit(Hashing.mix(h, 2)) - 0.5) * cell_size)
	return out


## `cells` : liste de {cell_id, x, y, herb_cover}, de la plus proche de la caméra à la plus lointaine (le plafond
## coupe donc le lointain). `herb_cover` nul (null) vaut cellule vide.
static func build(zone: String, cells: Array, cell_size: float, params: Dictionary) -> Dictionary:
	var cap := int(params["max_instances"])
	var out := PackedVector2Array()
	var truncated := false
	for c in cells:
		var cover = c.get("herb_cover", null)
		if cover == null:
			continue
		var p := positions(zone, int(c["cell_id"]), float(c["x"]), float(c["y"]), cell_size, float(cover), params)
		if out.size() + p.size() > cap:
			out.append_array(p.slice(0, cap - out.size()))
			truncated = true
			break
		out.append_array(p)
	var msg := ""
	if truncated:
		msg = "plafond de %d brins d'herbe atteint : herbe tronquée au loin" % cap
	return {"positions": out, "truncated": truncated, "message": msg}
