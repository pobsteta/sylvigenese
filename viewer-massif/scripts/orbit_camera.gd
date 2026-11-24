class_name OrbitCamera
extends Camera3D
## Camera orbitale : molette = zoom continu de 7 km a 1,2 m,
## clic droit = tourner, clic gauche ou fleches = se deplacer.

const D_MIN := 1.2
const D_MAX := 7000.0

var station: Station
var focus := Vector3(1000.0, 0.0, 1000.0)
var distance := 2600.0
var yaw := 0.6
var pitch := -0.75


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(D_MIN, distance * 0.88)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = minf(D_MAX, distance * 1.14)
	elif event is InputEventMagnifyGesture:
		distance = clampf(distance / event.factor, D_MIN, D_MAX)
	elif event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			yaw -= event.relative.x * 0.005
			pitch = clampf(pitch - event.relative.y * 0.005, -1.5, -0.05)
		elif event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			_pan(-event.relative.x * 0.0015, event.relative.y * 0.0015)


func _pan(dx: float, dy: float) -> void:
	var right := Vector3(cos(yaw), 0.0, -sin(yaw))
	var forward := Vector3(-sin(yaw), 0.0, -cos(yaw))
	focus += (right * dx + forward * dy) * distance


func _process(delta: float) -> void:
	var move := Input.get_vector("ui_left", "ui_right", "ui_down", "ui_up")
	if move != Vector2.ZERO:
		_pan(move.x * delta * 0.6, move.y * delta * 0.6)
	focus.x = clampf(focus.x, 0.0, Station.SIZE)
	focus.z = clampf(focus.z, 0.0, Station.SIZE)
	focus.y = station.height_at(focus.x, focus.z)

	var offset := Vector3(sin(yaw) * cos(pitch), -sin(pitch), cos(yaw) * cos(pitch)) * distance
	var target := focus + Vector3(0.0, minf(distance * 0.15, 1.5), 0.0)
	var p := target + offset
	if p.x >= 0.0 and p.x <= Station.SIZE and p.z >= 0.0 and p.z <= Station.SIZE:
		p.y = maxf(p.y, station.height_at(p.x, p.z) + 0.4)
	position = p
	near = clampf(distance * 0.02, 0.05, 5.0)
	far = 30000.0
	look_at(target, Vector3.UP)
