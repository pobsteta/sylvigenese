## Caméra libre de la vue (souris + ZQSD/WASD, A/E ou Q/E pour monter et descendre, Maj pour aller vite). Clic pour capturer la
## souris, Échap pour la rendre. Sans effet en --selftest (aucune entrée).
extends Camera3D

const SPEED_M_S := 6.0
const FAST_FACTOR := 5.0
const MOUSE_SENS := 0.003


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotation.y -= event.relative.x * MOUSE_SENS
		rotation.x = clampf(rotation.x - event.relative.y * MOUSE_SENS, -1.5, 1.5)


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
		var speed := SPEED_M_S * (FAST_FACTOR if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
		global_position += global_transform.basis * dir.normalized() * speed * delta
