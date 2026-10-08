extends Node2D
## {{GAME_NAME}} - the rules. A grey-box placeholder (tap the box before the
## time runs out) that shows the shape the real game grows on. Replace the toy
## with the loop from docs/bible.md and keep the shape:
##
## 1. Tuning knobs live in ONE block below; every rule reads them from there.
## 2. The rules own what the game keeps score with. The visual layer
##    (tick_visuals, _draw) reads it, never writes it, and has its own RNG.
##    tools/smoke_test.gd proves it. (This is what lets "make it feel alive"
##    rounds run without moving the balance or the bot's results.)
## 3. Systems sit in one registry; configure/tick loop over all of them, so a
##    new system cannot miss a reset. (A system configured in one place but
##    not another carries events into retries.)
## 4. A unit (round / level / wave) starts in begin_unit(), which snapshots
##    what a retry rolls back to - NOT the save file, which autosave overwrites.
## 5. tick(dt) runs the rules for dt seconds. _process calls it; the smoke test,
##    the bot and tools/capture.gd call it by hand for fast, repeatable runs.
## 6. Input reaches the rules through public functions (tap(pos)) - the same
##    path the bot takes. Draw and hit-test share geometry (box_rect()).
## 7. Art drops into slots: tex("box") is null until art/sprites/box.png exists,
##    and the code-drawn box stands in. No code change when the art lands.

# --- tuning knobs -------------------------------------------------------------
# The numbers to argue about after playing. Date each change and say who asked:
#     const UNIT_TIME := 25.0   # 30 -> 25 (user, YYYY-MM-DD: "rounds drag")
const UNIT_TIME := 30.0        # seconds per round
const UNIT_GOAL := 8           # hits to clear round 1
const GOAL_STEP := 2           # extra hits each later round
const HOP_EVERY := 1.8         # seconds before the box hops away on its own
const HOP_SPEEDUP := 0.9       # each round it hops this much sooner
const BOX_SHARE := 0.1         # box size, as a share of the short screen side
const AUTOSAVE_EVERY := 20.0   # seconds; the live game only

# --- grey-box colours (art replaces most of them) ------------------------------
const C_BG := Color("1d2027")
const C_BOX := Color("d9a441")
const C_OUTLINE := Color("0e0f13")
const C_TEXT := Color("e8e2d0")
const C_SPARK := Color("f4e9b8")

const ART_DIRS := ["res://art/sprites/"]

enum State { PLAYING, CLEARED, FAILED }

# --- rules state: what the game keeps score with --------------------------------
var unit := 1
var state: int = State.PLAYING
var score := 0                 # hits this round
var total := 0                 # banked from cleared rounds
var misses := 0
var time_left := UNIT_TIME
var box_pos := Vector2.ZERO
var stats := {"hits": 0, "misses": 0, "cleared": 0, "failed": 0}
var rng := RandomNumberGenerator.new()       # the rules' dice

# --- visual layer: reads the rules, never writes them ----------------------------
var vis_rng := RandomNumberGenerator.new()   # its own dice: looks never shift a rules roll
var phase := 0.0                             # wrapped on the CPU, never raw time
var sparks: Array = []                       # [pos, vel, life]

var art := {}
var systems: Array = []
var pause_ui: CanvasLayer
var running := true            # false: a harness drives tick() by hand
var _unit_start := {}
var _autosave_t := 0.0


# --- systems: configure() at every unit start, tick() from the spine ------------
# Never their own _process: one owner of time gives a fixed order and makes
# pausing, tests and the bot behave the same.

class Clock extends RefCounted:
	var main

	func configure(m, _unit: int) -> void:
		main = m
		main.time_left = UNIT_TIME

	func tick(dt: float) -> void:
		main.time_left = maxf(0.0, main.time_left - dt)


class Hopper extends RefCounted:
	var main
	var every := HOP_EVERY
	var t := 0.0

	func configure(m, u: int) -> void:
		main = m
		every = HOP_EVERY * pow(HOP_SPEEDUP, u - 1)
		t = 0.0

	func tick(dt: float) -> void:
		t += dt
		if t >= every:
			t = 0.0
			main.hop()


## Every system, in tick order. Add new ones here and nowhere else.
func _build_systems() -> void:
	systems = [Clock.new(), Hopper.new()]


func _ready() -> void:
	Session.setup()
	rng.randomize()
	vis_rng.randomize()
	_load_art()
	_build_systems()
	pause_ui = preload("res://scripts/pause.gd").new()
	pause_ui.main = self
	add_child(pause_ui)
	begin_unit(1, false)
	_start.call_deferred()


## The live game continues its save. (When a menu arrives, it decides: New Game
## calls Session.delete_save(), Continue sets Session.resume.)
func _start() -> void:
	if _live() and Session.has_save():
		load_game()


## True only for the game the player is actually in - not the smoke test, the
## bot or a capture harness. Autosave and auto-pause check it.
func _live() -> bool:
	return running and is_inside_tree() and get_tree().current_scene == self


# --- the run ---------------------------------------------------------------------

func begin_unit(n: int, save := true) -> void:
	unit = n
	_unit_start = {"unit": unit, "total": total}   # what a retry rolls back to
	state = State.PLAYING
	score = 0
	misses = 0
	for s in systems:
		s.configure(self, unit)
	hop()
	if save and _live():
		save_game()


func retry_unit() -> void:
	total = _unit_start.total
	begin_unit(_unit_start.unit)


func goal() -> int:
	return UNIT_GOAL + GOAL_STEP * (unit - 1)


## The rules, dt seconds on.
func tick(dt: float) -> void:
	if state != State.PLAYING:
		return
	for s in systems:
		s.tick(dt)
	if time_left <= 0.0:
		if score >= goal():
			_finish_unit()
		else:
			_fail_unit()


func _finish_unit() -> void:
	state = State.CLEARED
	total += score
	stats["cleared"] += 1
	if _live():
		save_game()


func _fail_unit() -> void:
	state = State.FAILED
	stats["failed"] += 1


## A tap at pos (viewport coordinates). The player's input and the bot's.
func tap(pos: Vector2) -> void:
	match state:
		State.PLAYING:
			if box_rect().has_point(pos):
				score += 1
				stats["hits"] += 1
				_burst(box_rect().get_center())
				hop()
			else:
				misses += 1
				stats["misses"] += 1
		State.CLEARED:
			begin_unit(unit + 1)
		State.FAILED:
			retry_unit()


func hop() -> void:
	var r := play_rect().grow(-box_size())
	box_pos = Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y)).round()


## Everything the game keeps score with. The smoke test compares it before and
## after a long run of the visual layer: it must not change.
func rules_snapshot() -> Array:
	return [unit, state, score, total, misses, time_left, box_pos, stats.duplicate(), rng.state]


# --- geometry: draw and hit-test both call these ----------------------------------

func view_size() -> Vector2:
	return get_viewport_rect().size


func font_size() -> int:
	return clampi(int(minf(view_size().x, view_size().y) / 20.0), 8, 32)


func box_size() -> float:
	return roundf(minf(view_size().x, view_size().y) * BOX_SHARE)


func box_rect() -> Rect2:
	var s := box_size()
	return Rect2(box_pos - Vector2(s, s) * 0.5, Vector2(s, s))


func play_rect() -> Rect2:
	var top := float(font_size()) * 2.5
	return Rect2(0.0, top, view_size().x, view_size().y - top)


# --- the frame -------------------------------------------------------------------

func _process(delta: float) -> void:
	if running:
		tick(delta)
		if _live():
			_autosave_t += delta
			if _autosave_t >= AUTOSAVE_EVERY:
				_autosave_t = 0.0
				save_game()
	tick_visuals(delta)
	queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	# Mouse events only: phones turn touches into mouse events
	# (emulate_mouse_from_touch), so one path serves both.
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var e := make_input_local(event) as InputEventMouseButton
		tap(e.position)
		get_viewport().set_input_as_handled()


## Save on the way out; pause (and save) whenever the app loses focus.
func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_WM_GO_BACK_REQUEST:
			if _live() and pause_ui != null and not pause_ui.is_open():
				pause_ui.open()
		NOTIFICATION_WM_CLOSE_REQUEST:
			if _live():
				save_game()


# --- visual layer: reads rules state, writes only its own -------------------------

func tick_visuals(dt: float) -> void:
	phase = fposmod(phase + dt * 3.0, TAU)
	for s in sparks:
		var v: Vector2 = s[1]
		s[0] += v * dt
		v.y += 90.0 * dt
		s[1] = v
		s[2] -= dt
	sparks = sparks.filter(func(s): return s[2] > 0.0)


func _burst(at: Vector2) -> void:
	for i in 8:
		var a := vis_rng.randf() * TAU
		sparks.append([at, Vector2(cos(a), sin(a)) * vis_rng.randf_range(20.0, 60.0), 0.5])


func _draw() -> void:
	var vs := view_size()
	draw_rect(Rect2(Vector2.ZERO, vs), C_BG)
	var pulse := roundf(sin(phase))   # whole pixels: pixel art moves in steps
	_draw_slot("box", box_rect().grow(pulse), C_BOX)
	for s in sparks:
		draw_rect(Rect2((s[0] as Vector2).round(), Vector2(2, 2)), Color(C_SPARK, clampf(s[2] * 2.0, 0.0, 1.0)))
	var font := ThemeDB.fallback_font
	var fs := font_size()
	var line := "ROUND %d   %d/%d   %ds" % [unit, score, goal(), ceili(time_left)]
	draw_string(font, Vector2(fs * 0.6, fs * 1.4), line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, C_TEXT)
	if state != State.PLAYING:
		var msg := "CLEARED - tap for round %d" % (unit + 1) if state == State.CLEARED else "OUT OF TIME - tap to retry"
		draw_string(font, Vector2(0.0, vs.y * 0.5), msg, HORIZONTAL_ALIGNMENT_CENTER, vs.x, fs, C_TEXT)


## A sprite into its rect, mirrored if asked; the code-drawn box until the art
## exists. A negative width mirrors the texture IN PLACE: the rect keeps its
## position (it does not run leftward from it).
func _draw_slot(slot: String, r: Rect2, fill: Color, flip := false) -> void:
	var t: Texture2D = tex(slot)
	if t == null:
		draw_rect(r, C_OUTLINE)
		draw_rect(r.grow(-1.0), fill)
	elif flip:
		draw_texture_rect(t, Rect2(r.position, Vector2(-r.size.x, r.size.y)), false)
	else:
		draw_texture_rect(t, r, false)


# --- art slots ---------------------------------------------------------------------

## The sprite for an art slot, or null - callers then draw the grey-box.
func tex(slot: String) -> Texture2D:
	return art.get(slot)


## Every PNG in ART_DIRS, keyed by file name without extension.
func _load_art() -> void:
	art.clear()
	for dir in ART_DIRS:
		for f in list_art(dir):
			var t = load(dir + f)
			if t is Texture2D:
				art[f.get_basename()] = t


## PNG names in a res:// folder - in the editor AND in an exported game, where
## the PNGs themselves are remapped away and a plain DirAccess scan finds only
## .import files. ResourceLoader.list_directory (Godot 4.4+) handles both; on
## 4.3 the .import/.remap suffixes are stripped by hand.
static func list_art(dir: String) -> PackedStringArray:
	var out := PackedStringArray()
	if ResourceLoader.has_method("list_directory"):
		for f in ResourceLoader.call("list_directory", dir):
			if String(f).ends_with(".png"):
				out.append(f)
		return out
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		var n := f.trim_suffix(".remap").trim_suffix(".import")
		if n.ends_with(".png") and not out.has(n):
			out.append(n)
	return out


# --- saving ---------------------------------------------------------------------------

## The run to disk: only what can't be rebuilt. Mid-round, the round's START is
## saved, so quitting restarts the round (simple, and impossible to exploit).
func save_game() -> bool:
	var d := {"unit": _unit_start.get("unit", unit), "total": _unit_start.get("total", total),
			"stats": stats.duplicate()}
	if state == State.CLEARED:
		d["unit"] = unit + 1
		d["total"] = total
	return Session.write_save(d)


## Pick up the save: the round is built fresh, the numbers laid over it.
func load_game() -> bool:
	var d := Session.read_save({"unit": 1, "total": 0, "stats": {}})
	if d.is_empty():
		return false
	total = int(d.total)
	for k in d.stats:
		stats[k] = d.stats[k]
	begin_unit(int(d.unit), false)
	return true
