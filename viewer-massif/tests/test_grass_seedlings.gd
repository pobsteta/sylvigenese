## Herbe et semis autour de la caméra (plan T8, décision Q4 de Pascal) :
## - nombre de brins proportionnel à herb_cover de la cellule ; à couvert nul, la cellule est VIDE ;
## - tirage par hachage déterministe de (zone, cell_id, rang) : mêmes positions à deux appels ;
## - plafond d'instances : il tronque ET le dit ;
## - semis : effectif d'une cellule d'espérance seedlings_ha x 0,0625 ha, arrondi aléatoire, déterministe ;
## - requête périmée d'un fil de calcul : jetée (identifiant de requête).
extends "res://tests/support.gd"

const G := "res://scripts/grass.gd"
const SE := "res://scripts/seedlings.gd"
const RG := "res://scripts/request_gate.gd"
const PARAMS := {"blades_per_m2_at_full_cover": 4.0, "max_instances": 200000}


func test_a_couvert_nul_la_cellule_n_a_aucun_brin() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var p: PackedVector2Array = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 0.0, PARAMS)
	assert_eq(p.size(), 0, "herb_cover = 0 : herbe vide")


func test_le_nombre_de_brins_suit_le_couvert() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var plein: int = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 1.0, PARAMS).size()
	assert_almost_eq(float(plein), 4.0 * 625.0, 1.0, "couvert 1 : densité de config x aire de la cellule")
	for c in [0.1, 0.3, 0.5, 0.75]:
		var n: int = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, c, PARAMS).size()
		assert_almost_eq(float(n), c * plein, 2.0, "couvert %s : proportionnel" % c)


func test_les_brins_restent_dans_leur_cellule() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var p: PackedVector2Array = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 0.4, PARAMS)
	assert_gt(p.size(), 0)
	for v in p:
		assert_between(v.x, 100.0 - 0.0001, 125.0 + 0.0001, "x dans [100 ; 125]")
		assert_between(v.y, 75.0 - 0.0001, 100.0 + 0.0001, "y dans [75 ; 100]")


func test_deux_appels_donnent_les_memes_positions() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var a: PackedVector2Array = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 0.4, PARAMS)
	var b: PackedVector2Array = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 0.4, PARAMS)
	assert_eq(a.size(), b.size())
	assert_true(a == b, "mêmes plantes à chaque passage")


func test_le_hachage_depend_de_la_zone_et_de_la_cellule() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var a: PackedVector2Array = Gr.positions("zone_m6", 17, 112.5, 87.5, 25.0, 0.4, PARAMS)
	var autre_cellule: PackedVector2Array = Gr.positions("zone_m6", 18, 112.5, 87.5, 25.0, 0.4, PARAMS)
	var autre_zone: PackedVector2Array = Gr.positions("zone_x", 17, 112.5, 87.5, 25.0, 0.4, PARAMS)
	assert_false(a == autre_cellule, "deux cellules ne tirent pas les mêmes brins")
	assert_false(a == autre_zone, "deux zones ne tirent pas les mêmes brins")


func _cellules(n: int, cover: float) -> Array:
	var out := []
	for i in range(n):
		out.append({"cell_id": i, "x": 12.5 + 25.0 * (i % 20), "y": 12.5 + 25.0 * (i / 20), "herb_cover": cover})
	return out


func test_le_plafond_tronque_et_le_dit() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var p := {"blades_per_m2_at_full_cover": 4.0, "max_instances": 1000}
	var r: Dictionary = Gr.build("zone_m6", _cellules(10, 1.0), 25.0, p)
	assert_eq(r["positions"].size(), 1000, "le plafond tronque")
	assert_true(r["truncated"], "et le dit")
	assert_string_contains(str(r["message"]).to_lower(), "plafond", "le message de l'écran nomme le plafond")
	var l: Dictionary = Gr.build("zone_m6", _cellules(10, 1.0), 25.0, {"blades_per_m2_at_full_cover": 4.0, "max_instances": 100000})
	assert_eq(l["positions"].size(), 25000)
	assert_false(l["truncated"], "sous le plafond : rien n'est dit")


func test_build_a_couvert_nul_est_vide_et_ne_signale_rien() -> void:
	var Gr = need(G)
	if Gr == null:
		return
	var r: Dictionary = Gr.build("zone_m6", _cellules(10, 0.0), 25.0, PARAMS)
	assert_eq(r["positions"].size(), 0)
	assert_false(r["truncated"])


func test_semis_deterministes_et_d_esperance_seedlings_ha_fois_0_0625() -> void:
	var Se = need(SE)
	if Se == null:
		return
	var n_cellules := 2000
	var seedlings_ha := 40.0
	var total := 0
	for i in range(n_cellules):
		var a: int = Se.count("zone_m6", i, "09", seedlings_ha, 0.0625)
		assert_eq(a, Se.count("zone_m6", i, "09", seedlings_ha, 0.0625), "cellule %d : deux appels, même effectif" % i)
		assert_between(a, 2, 3, "2,5 attendu en moyenne : arrondi au plus proche entier voisin")
		total += a
	var attendu := n_cellules * seedlings_ha * 0.0625
	var tolerance := 5.0 * sqrt(n_cellules * 0.25)       # cinq écarts-types d'un arrondi de Bernoulli
	assert_almost_eq(float(total), attendu, tolerance, "somme sur %d cellules (tolérance %.0f)" % [n_cellules, tolerance])


func test_semis_zero_donne_zero() -> void:
	var Se = need(SE)
	if Se == null:
		return
	for i in range(50):
		assert_eq(Se.count("zone_m6", i, "09", 0.0, 0.0625), 0)


func test_une_requete_perimee_est_jetee() -> void:
	var R = need(RG)
	if R == null:
		return
	var gate = R.new()
	var a: int = gate.next_id()
	var b: int = gate.next_id()
	assert_ne(a, b)
	assert_false(gate.accept(a), "résultat du fil de la requête précédente : jeté")
	assert_true(gate.accept(b), "dernière requête : acceptée")
