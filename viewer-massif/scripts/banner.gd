## Bandeau de mentions (plan T6, T8, §6 ; ADR 0007 choix 9 ; spec §10) : cinq lignes courtes au plus (règle du 1664).
## « provisoire » dès que le bloc l'est ; « semis non simulés » quand le recrutement n'est pas par cohortes ; les arbres
## dessinés par un modèle générique sont comptés et dits ; le stade vient de h / h_pot ; le sol est à 25 m.
extends RefCounted

const Reader := preload("res://scripts/zone_reader.gd")


## Nombre d'arbres du bloc dessinés par un modèle générique, d'après `index.stage_models` (le fichier de chaque couple
## essence-stade : une essence peut avoir un exemplaire pour un stade et le générique pour un autre).
## Un arbre dont le couple n'est pas dans l'index n'est pas compté ici : la vue le refuse avant d'afficher le bandeau.
static func generic_count(block: Dictionary, index: Dictionary) -> int:
	var models := Reader.stage_models(index)
	var n := 0
	for t in block.get("trees", []):
		var m: Dictionary = models.get(Reader.stage_key(str(t["species"]), str(t["stage"])), {})
		if str(m.get("kind", "")) == "generic":
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
	lines.append("Stade de l'arbre : h / h_pot (hauteur de l'arbre sur le plafond de la station), seuils de biomes/stades/stage_breaks.yml")
	var res := int(block.get("ground", {}).get("resolution_m", 25))
	lines.append("Sol : grille de %d m, lissé" % res)
	return "\n".join(lines)
