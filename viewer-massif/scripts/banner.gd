## Bandeau de mentions (plan T6, T8, §6 ; ADR 0007 choix 9 ; spec §10) : cinq lignes courtes au plus (règle du 1664).
## « provisoire » dès que le bloc l'est ; « semis non simulés » quand le recrutement n'est pas par cohortes ; les arbres
## dessinés par un modèle générique sont comptés et dits ; le stade est celui de l'arbre ; le sol est à 25 m.
extends RefCounted


## Nombre d'arbres du bloc dessinés par un modèle générique d'après `index.models` (essence -> modèle, sorte).
static func generic_count(block: Dictionary, index: Dictionary) -> int:
	var kinds := {}
	for m in index.get("models", []):
		kinds[str(m["species"])] = str(m["kind"])
	var n := 0
	for t in block.get("trees", []):
		if kinds.get(str(t["species"]), "") == "generic":
			n += 1
	return n


static func text(block: Dictionary, index: Dictionary) -> String:
	var lines := []
	if bool(block.get("provisoire", true)) or bool(index.get("provisoire", true)):
		lines.append("PROVISOIRE : trajectoire non validée écologiquement")
	if not bool(block.get("seedlings_simulated", false)):
		lines.append("Semis non simulés")
	var g := generic_count(block, index)
	if g > 0:
		lines.append("%d arbre%s dessiné%s par un modèle générique" % [g, "s" if g > 1 else "", "s" if g > 1 else ""])
	lines.append("Stade de l'arbre : sa hauteur sur celle de sa cellule")
	var res := int(block.get("ground", {}).get("resolution_m", 25))
	lines.append("Sol : grille de %d m, lissé" % res)
	return "\n".join(lines)
