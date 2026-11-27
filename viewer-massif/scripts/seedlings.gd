## Semis (plan T8) : par cellule et par essence, effectif d'espérance exacte `seedlings_ha x aire de la cellule (ha)`, arrondi
## aléatoire (la partie entière, plus 1 avec la probabilité de la partie fractionnaire), tiré par hachage de
## (zone, cell_id, essence) : même effectif à chaque passage. Aucune valeur écologique ici : les effectifs viennent de `massif/`.
extends RefCounted

const Hashing := preload("res://scripts/hashing.gd")


static func count(zone: String, cell_id: int, species: String, seedlings_ha: float, cell_area_ha: float) -> int:
	var expected := seedlings_ha * cell_area_ha
	if expected <= 0.0:
		return 0
	var whole := floori(expected)
	var frac := expected - float(whole)
	var h := Hashing.mix(Hashing.mix(Hashing.of_string(zone), cell_id), Hashing.of_string(species))
	return whole + (1 if Hashing.unit(Hashing.mix(h, 0x5EED)) < frac else 0)


## Positions des `n` semis d'une cellule (x est, y nord, relatifs au bloc), dans la cellule de centre (cx, cy).
static func positions(zone: String, cell_id: int, cx: float, cy: float, cell_size: float, species: String, n: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	var h0 := Hashing.mix(Hashing.mix(Hashing.of_string(zone), cell_id), Hashing.of_string(species))
	for rank in range(n):
		var h := Hashing.mix(h0, rank + 1)
		out.append(Vector2(cx + (Hashing.unit(Hashing.mix(h, 1)) - 0.5) * cell_size, cy + (Hashing.unit(Hashing.mix(h, 2)) - 0.5) * cell_size))
	return out
