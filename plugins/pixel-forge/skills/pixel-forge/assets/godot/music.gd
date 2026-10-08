extends Node
## A crossfaded playlist: two players, the next track fading in over the last
## FADE seconds of the one before it - no dead air between songs (silent gaps
## between tracks read as the game breaking, even short ones). The fade
## is equal-power (cos/sin): linear dB on both sides dips in the middle, where
## each track sits 20 dB down and the handover sounds like a hole.
## Keeps playing while the game is paused (PROCESS_MODE_ALWAYS).
## Copy to scripts/music.gd. For an SFX voice pool, ambience beds and ducking,
## add scripts/audio.gd too - it uses this file for its music.
##
##     var music := preload("res://scripts/music.gd").new()
##     add_child(music)
##     music.play_list(PackedStringArray(["res://audio/music/a.ogg", "res://audio/music/b.ogg"]))
##
## - Loop flags are set HERE, in code: a loop flag in a .import file is easy to
##   lose, and a looping track never ends, so the playlist stalls on it.
## - The player's slider owns the Music bus; level_db is the mix level under it.
##   Music sits under the effects (a good default: Music bus at 50%).
## - Ship music as OGG/MP3 at 128 kbps, 44.1 kHz: music is often more than half
##   of a mobile build until it is re-encoded.
## - The crossfade starts from the playback position: AudioStreamPlayer has no
##   "about to finish" signal.

const FADE := 5.0
const SILENT_DB := -60.0

var bus := "Music"             # audio.gd sets "MusicTrack" so ducks never fight the slider
var level_db := 0.0
var shuffle := true            # first track fixed, the rest shuffled; reshuffled on wrap
var tracks := PackedStringArray()

var _players: Array[AudioStreamPlayer] = []
var _current := 0              # which player is the one playing out
var _order: Array = []         # indices into tracks, in play order
var _pos := -1
var _fading := false
var _fade_t := 0.0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in 2:
		var p := AudioStreamPlayer.new()
		p.bus = bus
		p.process_mode = Node.PROCESS_MODE_ALWAYS
		p.volume_db = SILENT_DB
		add_child(p)
		_players.append(p)


## Start a playlist. The same list again keeps the song going but re-applies
## the level to the live player (otherwise a new level started at the old
## level_db leaves the track barely audible until the next song).
func play_list(list: PackedStringArray, db: float = 0.0) -> void:
	level_db = db
	if list == tracks and _players[_current].playing:
		if not _fading:
			_players[_current].volume_db = level_db
		return
	tracks = list
	_order = range(tracks.size())
	if shuffle and _order.size() > 2:
		var rest := _order.slice(1)
		rest.shuffle()
		_order = [_order[0]] + rest
	_pos = -1
	_fading = false
	for p in _players:
		p.stop()
	_start(_players[_current], level_db)


func stop() -> void:
	tracks = PackedStringArray()
	_fading = false
	for p in _players:
		p.stop()


func pause(on: bool) -> void:
	for p in _players:
		p.stream_paused = on


func current_player() -> AudioStreamPlayer:
	return _players[_current]


## A stream with its loop flag off, whatever the format.
static func no_loop(s: AudioStream) -> AudioStream:
	if s is AudioStreamWAV:
		(s as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_DISABLED
	elif s != null and "loop" in s:
		s.set("loop", false)
	return s


func _next_index() -> int:
	_pos += 1
	if _pos >= _order.size():
		_pos = 0
		if shuffle and _order.size() > 1:
			var last = _order[-1]
			_order.shuffle()
			if _order[0] == last:   # never the same song twice in a row across the wrap
				_order.push_back(_order.pop_front())
	return _order[_pos]


func _start(p: AudioStreamPlayer, db: float) -> void:
	if tracks.is_empty():
		return
	var path := tracks[_next_index()]
	if not ResourceLoader.exists(path):
		push_warning("music: no track at %s" % path)
		return
	p.stream = no_loop(load(path))
	p.volume_db = db
	p.play()


func _process(delta: float) -> void:
	var now: AudioStreamPlayer = _players[_current]
	if now.stream == null or tracks.is_empty() or now.stream_paused:
		return
	var left: float = now.stream.get_length() - now.get_playback_position()
	if not _fading and (left <= FADE or not now.playing):
		_fading = true             # the next one starts under it, from silence
		_fade_t = 0.0
		_start(_players[1 - _current], SILENT_DB)
	if _fading:
		_fade_t += delta
		var k := clampf(_fade_t / FADE, 0.0, 1.0)
		var nxt: AudioStreamPlayer = _players[1 - _current]
		now.volume_db = level_db + linear_to_db(maxf(0.0001, cos(k * PI * 0.5)))
		nxt.volume_db = level_db + linear_to_db(maxf(0.0001, sin(k * PI * 0.5)))
		if k >= 1.0:
			now.stop()
			_current = 1 - _current
			_fading = false
