## Identifiant de requête (plan T8) : le fil de calcul de l'herbe rend un résultat marqué de l'identifiant de sa requête ;
## seul le résultat de la dernière requête est accepté, un résultat périmé est jeté.
extends RefCounted

var _last := 0
var _mutex := Mutex.new()


func next_id() -> int:
	_mutex.lock()
	_last += 1
	var id := _last
	_mutex.unlock()
	return id


func accept(id: int) -> bool:
	_mutex.lock()
	var ok := id == _last
	_mutex.unlock()
	return ok
