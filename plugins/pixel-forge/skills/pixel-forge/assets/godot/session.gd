class_name Session
extends RefCounted
## What lasts between scenes and between runs: the player's settings, the
## audio buses they set, and the save file. Static - no autoload needed;
## call it from anywhere as Session.write_save(...), Session.settings.music.
##
## Rules this file keeps:
## - The save is written to a .tmp file and renamed into place, so a crash
##   mid-write never leaves a broken save. It carries SAVE_VERSION.
## - Tests, bots and capture runs point save_path / settings_path elsewhere
##   (use_test_paths), never at the player's own save - otherwise a smoke test
##   erases the developer's real save on every run.
## - Settings live in their own file, so wiping a save keeps the volume sliders.
## - Loading fills keys added after a save was written from defaults.
## - A run can redirect both files from the command line:
##     godot --path . ++ save=user://bot_1.dat settings=user://bot_1.cfg

const SAVE_VERSION := 1
const DEFAULT_SETTINGS := {"music": 0.5, "sfx": 0.9}
## Buses made at runtime if default_bus_layout.tres lacks them: [name, send].
## The player's Music slider owns "Music"; ducking moves "MusicTrack" (a child
## of Music), so a duck never overwrites the player's setting.
const BUSES := [["SFX", "Master"], ["Music", "Master"], ["Ambience", "Master"], ["MusicTrack", "Music"]]

const PLAYER_SAVE := "user://save.dat"
const PLAYER_SETTINGS := "user://settings.cfg"

static var save_path := PLAYER_SAVE
static var settings_path := PLAYER_SETTINGS
static var settings := DEFAULT_SETTINGS.duplicate()
static var resume := false   # set by a menu: the game scene loads the save as it starts
static var _ready_done := false


## Once per run: command-line redirects, the buses, saved settings applied.
static func setup() -> void:
	if _ready_done:
		return
	_ready_done = true
	apply_cmdline()
	ensure_buses()
	settings = DEFAULT_SETTINGS.duplicate()
	var cfg := ConfigFile.new()
	if cfg.load(settings_path) == OK:
		for k in settings:
			settings[k] = cfg.get_value("settings", k, settings[k])
	apply()


## Point the save and the settings at throwaway files (smoke test, bot,
## capture). Call before the game scene is created.
static func use_test_paths(tag: String = "test") -> void:
	save_path = "user://%s_save.dat" % tag
	settings_path = "user://%s_settings.cfg" % tag
	_ready_done = false


## `++ save=PATH settings=PATH` on the command line redirect the files.
static func apply_cmdline() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() != 2:
			continue
		if kv[0] == "save":
			save_path = kv[1]
		elif kv[0] == "settings":
			settings_path = kv[1]


static func ensure_buses() -> void:
	for b in BUSES:
		if AudioServer.get_bus_index(b[0]) == -1:
			AudioServer.add_bus()
			var i: int = AudioServer.bus_count - 1
			AudioServer.set_bus_name(i, b[0])
			AudioServer.set_bus_send(i, b[1])


## Settings to the buses. 0 mutes the bus outright (not -80 dB).
static func apply() -> void:
	var levels := [["Music", settings.music], ["SFX", settings.sfx], ["Ambience", settings.sfx]]
	for pair in levels:
		var i: int = AudioServer.get_bus_index(pair[0])
		if i >= 0:
			AudioServer.set_bus_volume_db(i, linear_to_db(maxf(0.0001, pair[1])))
			AudioServer.set_bus_mute(i, pair[1] <= 0.001)


static func save_settings() -> bool:
	var cfg := ConfigFile.new()
	for k in settings:
		cfg.set_value("settings", k, settings[k])
	return cfg.save(settings_path) == OK


# --- the saved game ----------------------------------------------------------

## A test run's cleanup: its save and settings files. Refuses on the
## player's own paths, so a harness can never wipe a real save.
static func delete_test_files() -> void:
	if save_path == PLAYER_SAVE or settings_path == PLAYER_SETTINGS:
		push_warning("Session.delete_test_files: not on test paths - nothing deleted")
		return
	delete_save()
	if FileAccess.file_exists(settings_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(settings_path))


static func has_save() -> bool:
	return FileAccess.file_exists(save_path)


static func delete_save() -> void:
	for p in [save_path, save_path + ".tmp"]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(p))


## Written to a temporary file first and swapped in, so a crash mid-write
## never leaves a broken save. Adds "version". False if it could not write.
static func write_save(data: Dictionary) -> bool:
	var d := data.duplicate()
	d["version"] = SAVE_VERSION
	var tmp: String = save_path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_warning("could not write %s: %s" % [tmp, FileAccess.get_open_error()])
		return false
	f.store_var(d)
	f.close()
	var real := ProjectSettings.globalize_path(save_path)
	if FileAccess.file_exists(save_path):
		DirAccess.remove_absolute(real)
	return DirAccess.rename_absolute(ProjectSettings.globalize_path(tmp), real) == OK


## The saved game, with every key missing from it filled from `defaults`.
## {} when there is no save, it is unreadable, or it is from a newer version.
## A crash between removing the old save and renaming the new one leaves only
## the .tmp, which is complete - it is read instead.
static func read_save(defaults: Dictionary = {}) -> Dictionary:
	var path := save_path
	if not FileAccess.file_exists(path):
		path = save_path + ".tmp"
		if not FileAccess.file_exists(path):
			return {}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var v: Variant = f.get_var()
	f.close()
	if not (v is Dictionary):
		push_warning("save file was unreadable; starting fresh")
		return {}
	var d: Dictionary = v
	var ver: int = int(d.get("version", 0))
	if ver > SAVE_VERSION:
		push_warning("save is from a newer version (%d); not loaded" % ver)
		return {}
	if ver < SAVE_VERSION:
		d = _migrate(d, ver)
	for k in defaults:
		if not d.has(k):
			d[k] = defaults[k]
	return d


## Bring an older save up to SAVE_VERSION. Add a step per version bump, e.g.
##   if _from < 2: d["coins"] = d.get("gold", 0)
static func _migrate(d: Dictionary, _from: int) -> Dictionary:
	d["version"] = SAVE_VERSION
	return d
