## Caméra libre de la vue (souris + ZQSD/WASD, A/E ou Q/E pour monter et descendre, Maj pour aller vite ; flèches pour tourner
## la tête sans souris, mission 091). Clic pour capturer la
## souris, Échap pour la rendre. Sans effet en --selftest (aucune entrée). Réglages : bloc `viewer.camera` de config.yml
## (provisoires, « illustration, non mesurée »), donnés par `configure` ; aucune valeur par défaut ici.
extends Camera3D

var speed_m_s: float
var fast_factor: float
var mouse_sensitivity: float
var pitch_limit_rad: float
var key_turn_rad_s: float


## `cam` : la carte `viewer.camera` de config.yml (clés lues : speed_m_s, fast_factor, mouse_sensitivity, pitch_limit_rad, key_turn_rad_s).
func configure(cam: Dictionary) -> void:
	speed_m_s = float(cam["speed_m_s"])
	fast_factor = float(cam["fast_factor"])
	mouse_sensitivity = float(cam["mouse_sensitivity"])
	pitch_limit_rad = float(cam["pitch_limit_rad"])
	key_turn_rad_s = float(cam["key_turn_rad_s"])


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotation.y -= event.relative.x * mouse_sensitivity
		rotation.x = clampf(rotation.x - event.relative.y * mouse_sensitivity, -pitch_limit_rad, pitch_limit_rad)


## Direction de déplacement (repère de la caméra : x droite, y haut, -z devant) d'après l'ensemble des touches physiques tenues.
## Touches physiques : W A S D donnent Z Q S D sur un clavier AZERTY, sans changement.
static func move_direction(held: Dictionary) -> Vector3:
	var dir := Vector3.ZERO
	if held.get(KEY_W, false):
		dir.z -= 1.0
	if held.get(KEY_S, false):
		dir.z += 1.0
	if held.get(KEY_A, false):
		dir.x -= 1.0
	if held.get(KEY_D, false):
		dir.x += 1.0
	if held.get(KEY_E, false):
		dir.y += 1.0
	if held.get(KEY_Q, false):
		dir.y -= 1.0
	return dir


## Rotation de la tête aux flèches : (lacet, tangage) en nouvelles valeurs de rotation.y et rotation.x. Flèche gauche tourne vers
## la gauche (rotation.y augmente), flèche haut lève le regard ; le tangage reste dans la limite de config.yml.
static func turned(yaw: float, pitch: float, held: Dictionary, rate_rad_s: float, pitch_limit: float, delta: float) -> Vector2:
	var dyaw := (1.0 if held.get(KEY_LEFT, false) else 0.0) - (1.0 if held.get(KEY_RIGHT, false) else 0.0)
	var dpitch := (1.0 if held.get(KEY_UP, false) else 0.0) - (1.0 if held.get(KEY_DOWN, false) else 0.0)
	return Vector2(yaw + dyaw * rate_rad_s * delta, clampf(pitch + dpitch * rate_rad_s * delta, -pitch_limit, pitch_limit))


func _held() -> Dictionary:
	var held := {}
	for k in [KEY_W, KEY_S, KEY_A, KEY_D, KEY_E, KEY_Q, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN]:
		held[k] = Input.is_physical_key_pressed(k)
	return held


func _process(delta: float) -> void:
	var held := _held()
	var t := turned(rotation.y, rotation.x, held, key_turn_rad_s, pitch_limit_rad, delta)
	rotation.y = t.x
	rotation.x = t.y
	var dir := move_direction(held)
	if dir != Vector3.ZERO:
		var speed := speed_m_s * (fast_factor if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
		global_position += global_transform.basis * dir.normalized() * speed * delta
