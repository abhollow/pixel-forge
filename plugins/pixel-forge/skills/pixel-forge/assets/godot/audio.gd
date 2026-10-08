extends Node
## All of the game's sound: a pool of SFX voices with per-sound caps and trims,
## an ambience bed that fades (never clicks), the music playlist (music.gd),
## ducking and pausing. Copy to
## scripts/audio.gd together with scripts/music.gd, then in main.gd:
##     audio = preload("res://scripts/audio.gd").new()
##     add_child(audio)
##     audio.play("pickup")
##
## Buses (Session.ensure_buses / default_bus_layout.tres):
##     Master <- SFX, Ambience, Music <- MusicTrack
## The player's sliders own Music and SFX. Ducks move the MusicTrack BUS while
## crossfades move the PLAYERS, so the two never fight over one volume_db and a
## duck never overwrites the player's setting.
##
## Filenames are the contract: drop a real recording over a placeholder and no
## code changes. Every stream is loaded in _ready (loading on the frame a sound
## first plays hitches - and those are the frames that matter).

const POOL_SIZE := 12

## key -> path. Missing files are skipped, so placeholders can come later.
const SOUNDS := {
	# "pickup": "res://audio/pickup.ogg",
	# "hit": "res://audio/hit.wav",
}

## Per-key voice cap: a sound that fires several times a second steals its own
## oldest voice instead of stacking into mush (e.g. a pickup capped at 3).
const MAX_VOICES := {
	# "pickup": 3,
}

## Per-key level trim in dB, applied on top of the call. Balance the MIX here,
## not by normalising the files: a quiet, frequent sound is quiet on purpose.
const SFX_TRIM := {
	# "purchase": -7.0,
}

var sfx_enabled := true
var music: Node                  # music.gd, on the MusicTrack bus

var _streams := {}
var _pool: Array[AudioStreamPlayer] = []
var _keys: Array[String] = []
var _started: Array[float] = []
var _next := 0
var _bed: AudioStreamPlayer
var _bed_path := ""
var _bed_tw: Tween
var _duck_tw: Tween


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS   # pause-screen and result sounds still play
	Session.ensure_buses()
	for key in SOUNDS:
		if ResourceLoader.exists(SOUNDS[key]):
			_streams[key] = load(SOUNDS[key])
	for i in POOL_SIZE:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		p.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(p)
		_pool.append(p)
		_keys.append("")
		_started.append(0.0)
	_bed = AudioStreamPlayer.new()
	_bed.bus = "Ambience"
	_bed.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(_bed)
	music = preload("res://scripts/music.gd").new()
	music.bus = "MusicTrack"
	add_child(music)


func play(key: String, pitch: float = 1.0, volume_db: float = 0.0) -> void:
	if not sfx_enabled or not _streams.has(key):
		return
	var i := _claim_voice(key)
	var p := _pool[i]
	_keys[i] = key
	_started[i] = Time.get_ticks_msec() / 1000.0
	p.stream = _streams[key]
	p.pitch_scale = clampf(pitch, 0.4, 2.5)
	p.volume_db = volume_db + float(SFX_TRIM.get(key, 0.0))
	p.play()


## Only when the source is on screen: sounds from places the player cannot
## see are noise.
func play_near(key: String, world_pos: Vector2, pitch: float = 1.0, volume_db: float = 0.0) -> void:
	var vp := get_viewport()
	var screen_pos: Vector2 = vp.get_canvas_transform() * world_pos
	if vp.get_visible_rect().grow(16.0).has_point(screen_pos):
		play(key, pitch, volume_db)


func _claim_voice(key: String) -> int:
	var cap: int = MAX_VOICES.get(key, 0)
	if cap > 0:
		var live: Array[int] = []
		for i in _pool.size():
			if _keys[i] == key and _pool[i].playing:
				live.append(i)
		if live.size() >= cap:
			var oldest: int = live[0]
			for i in live:
				if _started[i] < _started[oldest]:
					oldest = i
			return oldest
	var idx := _next
	_next = (_next + 1) % _pool.size()
	return idx


## A looping ambience bed (rain, crowd, wind), faded in. Loops must be OGG: Godot
## loops Ogg sample-accurately, MP3 cannot. The loop flag is set here, in code.
func play_bed(path: String, volume_db: float = -8.0, fade: float = 1.2) -> void:
	if path == _bed_path and _bed.playing:
		return
	if not ResourceLoader.exists(path):
		push_warning("audio: no bed at %s" % path)
		return
	var s: AudioStream = load(path)
	if s is AudioStreamWAV:
		(s as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_FORWARD
	elif "loop" in s:
		s.set("loop", true)
	_kill(_bed_tw)
	_bed_path = path
	_bed.stream = s
	_bed.volume_db = volume_db - 30.0
	_bed.play()
	_bed_tw = _tween()
	_bed_tw.tween_property(_bed, "volume_db", volume_db, fade)


func stop_bed(fade: float = 1.6) -> void:
	if not _bed.playing:
		return
	_kill(_bed_tw)
	_bed_path = ""
	_bed_tw = _tween()
	_bed_tw.tween_property(_bed, "volume_db", _bed.volume_db - 30.0, fade)
	_bed_tw.tween_callback(_bed.stop)


## Duck the music under a moment (a sting, a voice) - relative, on MusicTrack.
func duck_music(to_db: float = -12.0, time: float = 0.9) -> void:
	_tween_bus("MusicTrack", to_db, time)


## Every reset path calls this: a duck left on carries into the next round.
func restore_music(time: float = 1.4) -> void:
	_tween_bus("MusicTrack", 0.0, time)


## Silence ALL music for a sting and resume after (pausing, not ducking, so
## neither the player's slider nor a bed on the Music bus is touched).
func pause_music(on: bool) -> void:
	music.pause(on)


## App lifecycle: mute everything on focus loss / Android pause, unmute on
## return. The game itself stays paused until the player resumes it.
static func mute_all(on: bool) -> void:
	var i := AudioServer.get_bus_index("Master")
	if i >= 0:
		AudioServer.set_bus_mute(i, on)


func _tween() -> Tween:
	# Survives a paused tree: a fade frozen by the pause screen leaves the next
	# track stuck at partial volume.
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	return tw


func _kill(tw: Tween) -> void:
	if tw != null and tw.is_valid():
		tw.kill()


func _tween_bus(bus_name: String, to_db: float, time: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	_kill(_duck_tw)
	_duck_tw = _tween()
	_duck_tw.tween_method(func(v: float) -> void: AudioServer.set_bus_volume_db(idx, v),
			AudioServer.get_bus_volume_db(idx), to_db, time)
