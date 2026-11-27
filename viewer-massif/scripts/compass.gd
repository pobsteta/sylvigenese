## Flèche du nord à l'écran (mission 085, demande de Pascal du 27/11/2026). Repère de la vue : x = est, y = haut, z = -nord
## (frame.gd) ; la caméra regarde vers -z quand son cap est nul, donc vers le nord.
## Convention : le cap est l'angle horaire du regard depuis le nord (nord 0, est 90 degrés). La flèche montre où est le nord
## SUR L'ÉCRAN : elle tourne de -cap, dans le sens horaire de l'écran. Cap 0 : flèche vers le haut ; cap 90 (le regard va à
## l'est) : flèche vers la gauche ; cap 180 : vers le bas ; cap 270 (ouest) : vers la droite. Seule la direction horizontale du
## regard compte : l'inclinaison de la caméra ne change rien.
## Taille et couleurs : bloc `viewer.hud` de config.yml (north_size_px, north_color, outline_color), via `configure`.
extends Control

## Proportions du dessin de la flèche, en part du rayon de la flèche `r` ou de la taille du contrôle (`north_size_px`). Ce sont des
## choix de dessin, « illustration, non mesurée », sans sens physique ni écologique : nommés ici avec leur raison et acceptés
## explicitement par la garde contracts/tests/test_m6b_affichage.py (ALLOWED_CONSTS). La taille et les couleurs viennent du
## bloc `viewer.hud` de config.yml.
## Rayon de la flèche = cette part de la taille du contrôle : laisse la place du « N » et du contour dans le carré.
const ARROW_RADIUS_SHARE := 0.32
## Aile de la flèche : écart latéral (part de r) ; la flèche est une pointe à deux ailes et un creux, comme une boussole.
const ARROW_WING_SPAN := 0.5
## Aile de la flèche : recul vers l'arrière (part de r), au-delà du centre : la pointe est à -r, les ailes à +0,7 r.
const ARROW_WING_DEPTH := 0.7
## Creux de la flèche entre les ailes (part de r) : moins reculé que les ailes, il donne la forme d'une pointe de flèche.
const ARROW_NOTCH_DEPTH := 0.3
## Taille de la police du « N » (part de la taille du contrôle) : lisible sans déborder du carré.
const LABEL_FONT_SHARE := 0.3
## Distance du « N » au centre (part de r) : au-delà de la pointe (1 r) pour ne pas la recouvrir.
const LABEL_DISTANCE := 1.35
## Décalage de la ligne de base du « N » (part de la hauteur du texte) : centre optique de la lettre sur son point d'ancrage.
const LABEL_BASELINE_SHARE := 0.25

var camera: Camera3D
var angle_rad := 0.0          # angle de la flèche à l'écran (radians, horaire, 0 = vers le haut)
var _color: Color
var _outline: Color
var _outline_px: float
var _size_px: float


## `hud` : la carte `viewer.hud` de config.yml ; `cam` : la caméra suivie.
func configure(hud: Dictionary, cam: Camera3D) -> void:
	camera = cam
	_size_px = float(hud["north_size_px"])
	_color = Color(str(hud["north_color"]))
	_outline = Color(str(hud["outline_color"]))
	_outline_px = float(hud["state_outline_px"])
	custom_minimum_size = Vector2(_size_px, _size_px)
	size = custom_minimum_size
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Angle de la flèche (radians, horaire à l'écran, 0 = vers le haut) pour un regard `forward` dans le repère de la vue.
## NAN si le regard est vertical (aucune direction horizontale : le cap n'existe pas).
static func screen_angle(forward: Vector3) -> float:
	var horizontal := Vector2(forward.x, forward.z)
	if horizontal.is_zero_approx():
		return NAN
	return -atan2(horizontal.x, -horizontal.y)


## Cap en degrés (0 = nord, 90 = est) d'un regard dans le repère de la vue ; NAN si vertical.
static func heading_deg(forward: Vector3) -> float:
	var a := screen_angle(forward)
	return NAN if is_nan(a) else fposmod(rad_to_deg(-a), 360.0)


## Contour de la flèche (pointe, aile droite, creux, aile gauche), centré sur l'origine, tourné de `angle` ; rayon `r`.
static func arrow_points(angle: float, r: float) -> PackedVector2Array:
	var base := [Vector2(0.0, -r), Vector2(r * ARROW_WING_SPAN, r * ARROW_WING_DEPTH), Vector2(0.0, r * ARROW_NOTCH_DEPTH), Vector2(-r * ARROW_WING_SPAN, r * ARROW_WING_DEPTH)]
	var out := PackedVector2Array()
	for p in base:
		out.append((p as Vector2).rotated(angle))
	return out


func _process(_delta: float) -> void:
	if camera == null or not camera.is_inside_tree():
		return
	var a := screen_angle(-camera.global_transform.basis.z)
	if not is_nan(a) and not is_equal_approx(a, angle_rad):
		angle_rad = a
		queue_redraw()


func _draw() -> void:
	var c := Vector2(_size_px, _size_px) / 2.0
	var r := _size_px * ARROW_RADIUS_SHARE
	var pts := arrow_points(angle_rad, r)
	var shifted := PackedVector2Array()
	for p in pts:
		shifted.append(p + c)
	draw_colored_polygon(shifted, _color)
	var closed := shifted.duplicate()
	closed.append(shifted[0])
	draw_polyline(closed, _outline, _outline_px / 2.0, true)
	var font := ThemeDB.fallback_font
	var fs := int(_size_px * LABEL_FONT_SHARE)
	var label_size := font.get_string_size("N", HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
	var at := c + Vector2(0.0, -r * LABEL_DISTANCE).rotated(angle_rad) - Vector2(label_size.x / 2.0, -label_size.y * LABEL_BASELINE_SHARE)
	draw_string_outline(font, at, "N", HORIZONTAL_ALIGNMENT_LEFT, -1, fs, int(_outline_px), _outline)
	draw_string(font, at, "N", HORIZONTAL_ALIGNMENT_LEFT, -1, fs, _color)
