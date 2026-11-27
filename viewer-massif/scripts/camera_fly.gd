## Caméra libre de la vue (souris + ZQSD/WASD, A/E ou Q/E pour monter et descendre, Maj pour aller vite). Clic pour capturer la
## souris, Échap pour la rendre. Sans effet en --selftest (aucune entrée). Réglages : bloc `viewer.camera` de config.yml
## (provisoires, « illustration, non mesurée »), donnés par `configure` ; aucune valeur par défaut ici.
extends Camera3D

var speed_m_s: float
var fast_factor: float
var mouse_sensitivity: float
var pitch_limit_rad: float


## `cam` : la carte `viewer.camera` de config.yml (clés lues : speed_m_s, fast_factor, mouse_sensitivity, pitch_limit_rad).
func configure(cam: Dictionary) -> void:
	speed_m_s = float(cam["speed_m_s"])
	fast_factor = float(cam["fast_factor"])
	mouse_sensitivity = float(cam["mouse_sensitivity"])
	pitch_limit_rad = float(cam["pitch_limit_rad"])


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotation.y -= event.relative.x * mouse_sensitivity
		rotation.x = clampf(rotation.x - event.relative.y * mouse_sensitivity, -pitch_limit_rad, pitch_limit_rad)


func _process(delta: float) -> void:
	var dir := Vector3.ZERO
	if Input.is_physical_key_pressed(KEY_W):
		dir.z -= 1.0
	if Input.is_physical_key_pressed(KEY_S):
		dir.z += 1.0
	if Input.is_physical_key_pressed(KEY_A):
		dir.x -= 1.0
	if Input.is_physical_key_pressed(KEY_D):
		dir.x += 1.0
	if Input.is_physical_key_pressed(KEY_E):
		dir.y += 1.0
	if Input.is_physical_key_pressed(KEY_Q):
		dir.y -= 1.0
	if dir != Vector3.ZERO:
		var speed := speed_m_s * (fast_factor if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
		global_position += global_transform.basis * dir.normalized() * speed * delta
