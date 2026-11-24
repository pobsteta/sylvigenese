class_name Biome
extends RefCounted
## Regles de biome : adequation d'une espece a une station par courbes de reponse
## gaussiennes autour de ses optimums (facon Ellenberg).


static func response(v: float, opt: float, tol: float) -> float:
	var d := (v - opt) / tol
	return exp(-0.5 * d * d)


## Arbres : humidite F, reaction R, temperature T.
static func suitability(sp: Dictionary, fv: float, rv: float, tv: float) -> float:
	var a: float = response(fv, sp["F"], sp["tolF"])
	var b: float = response(rv, sp["R"], sp["tolR"])
	var c: float = response(tv, sp["T"], sp["tolT"])
	return a * b * c


## Herbacees : humidite F, reaction R, lumiere au sol L (deduite du couvert).
static func herb_suitability(sp: Dictionary, fv: float, rv: float, lv: float) -> float:
	var a: float = response(fv, sp["F"], sp["tolF"])
	var b: float = response(rv, sp["R"], sp["tolR"])
	var c: float = response(lv, sp["L"], sp["tolL"])
	return a * b * c
