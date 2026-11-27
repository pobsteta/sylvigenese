## Hachage déterministe (plan T8) : mêmes plantes à chaque passage, sur toute machine (entiers de 32 bits, aucune dépendance
## à la graine du moteur). Brique de `grass.gd` et `seedlings.gd`.
extends RefCounted

const MASK := 0xFFFFFFFF


## FNV-1a 32 bits d'une chaîne.
static func of_string(s: String) -> int:
	var h := 2166136261
	for b in s.to_utf8_buffer():
		h = ((h ^ b) * 16777619) & MASK
	return h


## Mélange d'un entier dans un hachage (finalisation de MurmurHash3).
static func mix(h: int, v: int) -> int:
	h = (h ^ (v & MASK)) & MASK
	h = (h * 0x85ebca6b) & MASK
	h ^= h >> 13
	h = (h * 0xc2b2ae35) & MASK
	h ^= h >> 16
	return h & MASK


## Hachage vers [0 ; 1[.
static func unit(h: int) -> float:
	return float(h & MASK) / 4294967296.0
