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


## Échelle (x, y, z) d'un semis. `h_mean_m` : hauteur moyenne du semis (bloc massif) ; `model_height_m` : hauteur mesurée du modèle.
## Le bloc ne donne AUCUNE largeur de houppier de semis. Modèle du générateur : forme naturelle conservée, échelle uniforme
## h / hauteur du modèle. Générique (1 m de haut, 1 m de rayon) : (r, h, r) avec r = h x `radius_over_height`, rapport
## provisoire et SANS SOURCE de viewer.seedlings.generic_radius_over_height (illustration, non mesurée), dit à l'écran.
static func scale(is_generic: bool, h_mean_m: float, model_height_m: float, radius_over_height: float) -> Vector3:
	var sy := h_mean_m / model_height_m
	if not is_generic:
		return Vector3(sy, sy, sy)
	return Vector3(h_mean_m * radius_over_height, sy, h_mean_m * radius_over_height)


## Ligne de l'écran quand des semis sont dessinés par un générique : dit que la largeur est inventée pour l'affichage.
static func generic_note(radius_over_height: float) -> String:
	return "semis génériques : largeur non connue, rayon = %s x la hauteur (illustration, non mesurée)" % ("%.2f" % radius_over_height).replace(".", ",")
