extends SceneTree
## Headless smoke test: boots the REAL main scene and drives it - no mocks -
## printing one line per check and a summary. Run (sh tools/run_tests.sh does
## both, with a timeout, and fails on SCRIPT ERROR):
##     godot --headless --path . --import          # after pulling or adding a class_name
##     godot --headless --path . --script res://tools/smoke_test.gd
## Ends with "=== N checks, M failed ===" and exits 1 on any failure, so CI
## gates on the exit code. Optional: ++ max=480 (watchdog seconds).
##
## Rules that earned their place (references/testing-discipline.md):
## * Prove a new check can FAIL: break the fix, watch it fail, put it back.
## * Wait on conditions or sim(seconds), never on frame counts: a frame is not
##   1/60 s headless, and run/max_fps changes it again.
## * A flaky check is a bug report. Put the values in its label and instrument
##   it before loosening anything; loosen only once the long case is proven
##   legitimate.
## * The game keeps running during every await. Park what could interfere
##   (spawners, hazards, protection timers) in ONE place: neutralize().
## * Unique variable prefixes per section (a long _run() hits "variable
##   already declared"); assert properties, not counts that grow with content.
## * This suite never touches the player's save: Session points at test files
##   before the game exists, and they are deleted at the end.

const MAIN_SCENE := "res://scenes/main.tscn"
const STEP := 0.1          # seconds per hand-driven rules tick (advance)

var failures: Array[String] = []
var checks := 0
var game


func _initialize() -> void:
	var max_s := 480.0   # below run_tests.sh's 600 s timeout, so the summary still prints
	for a in OS.get_cmdline_user_args():
		if String(a).begins_with("max="):
			max_s = float(String(a).get_slice("=", 1))
	# Watchdog: a script error aborts _run() silently and the test would wait
	# forever. Fail loudly instead.
	create_timer(max_s, true, false, true).timeout.connect(_watchdog)
	_run.call_deferred()


func _watchdog() -> void:
	print("\n=== WATCHDOG: the suite did not finish (did a script error above abort it?) ===")
	print("=== %d checks, %d failed ===" % [checks, failures.size() + 1])
	quit(2)


# --- helpers ---------------------------------------------------------------------

func check(label: String, condition: bool) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		print("  FAIL  %s" % label)
	else:
		print("  ok    %s" % label)


func section(title: String) -> void:
	print("\n[%s]" % title)


func frames(n: int) -> void:
	for i in n:
		await process_frame


## Let the game run for `seconds` of game time, accumulating real delta.
func sim(seconds: float) -> void:
	var t := 0.0
	var guard := 0
	while t < seconds and guard < 2000000:
		await process_frame
		t += root.get_process_delta_time()
		guard += 1


## Like sim(), but parks everything that could interfere EVERY frame: setting a
## flag once is not enough, because spawners keep spawning.
func sim_undisturbed(seconds: float) -> void:
	var t := 0.0
	var guard := 0
	while t < seconds and guard < 2000000:
		await process_frame
		neutralize()
		t += root.get_process_delta_time()
		guard += 1


## Run the rules by hand: fast and repeatable (a whole suite can run in a few
## seconds this way). Needs game.running = false, or _process ticks too.
func advance(seconds: float, dt: float = STEP) -> void:
	var t := 0.0
	while t < seconds - 0.0001:
		game.tick(dt)
		t += dt


## True once cond() holds; false after max_seconds of game time.
func wait_until(cond: Callable, max_seconds: float = 5.0) -> bool:
	var t := 0.0
	while not cond.call():
		if t >= max_seconds:
			return false
		await process_frame
		t += root.get_process_delta_time()
	return true


## The one place that parks hazards and protection timers. Register every new
## one here as it is added, e.g.  game.spawner.active = false;  game.player.grace = 0.0
func neutralize() -> void:
	pass


# Synthetic input through the real viewport: GUI hit-tests, then
# _unhandled_input - exactly what a finger does. Positions are viewport
# (logical) coordinates.
func press(pos: Vector2) -> void:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = true
	e.position = pos
	e.global_position = pos
	root.push_input(e, true)


func drag(pos: Vector2, rel: Vector2) -> void:
	var e := InputEventMouseMotion.new()
	e.button_mask = MOUSE_BUTTON_MASK_LEFT
	e.position = pos
	e.global_position = pos
	e.relative = rel
	root.push_input(e, true)


func release(pos: Vector2) -> void:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = false
	e.position = pos
	e.global_position = pos
	root.push_input(e, true)


func tap(pos: Vector2) -> void:
	press(pos)
	release(pos)


## Tap a Control where it is on screen, through the real GUI hit-test - the
## way a player presses it. False if it is hidden.
func pick(node: Control) -> bool:
	if node == null or not node.is_visible_in_tree():
		return false
	tap(node.get_global_transform_with_canvas() * (node.size * 0.5))
	return true


func read_forge_json() -> Dictionary:
	var f := FileAccess.open("res://forge.json", FileAccess.READ)
	if f == null:
		return {}
	var v: Variant = JSON.parse_string(f.get_as_text())
	return v if v is Dictionary else {}


# --- the suite ----------------------------------------------------------------------

func _run() -> void:
	# Never the player's own save or settings.
	Session.use_test_paths("smoke_test")
	Session.delete_save()

	game = load(MAIN_SCENE).instantiate()
	root.add_child(game)
	await frames(3)

	section("boot")
	check("the main scene loads", game != null and game.is_inside_tree())
	check("the test runs on its own save file, never the player's (%s)" % Session.save_path,
			Session.save_path.begins_with("user://smoke_test"))

	section("project settings")
	# The editor rewrites project.godot and drops keys that hold default
	# values, so read the EFFECTIVE setting, never the file.
	var ps_cfg := read_forge_json()
	check("forge.json is readable", not ps_cfg.is_empty())
	check("textures filter NEAREST (the pixel-art setting)",
			ProjectSettings.get_setting("rendering/textures/canvas_textures/default_texture_filter") == 0)
	check("stretch mode canvas_items",
			ProjectSettings.get_setting("display/window/stretch/mode") == "canvas_items")
	check("stretch aspect matches forge.json (%s)" % ps_cfg.get("aspect", "?"),
			ProjectSettings.get_setting("display/window/stretch/aspect") == ps_cfg.get("aspect", ""))
	check("viewport size matches forge.json",
			ProjectSettings.get_setting("display/window/size/viewport_width") == int(ps_cfg.get("view_w", -1))
			and ProjectSettings.get_setting("display/window/size/viewport_height") == int(ps_cfg.get("view_h", -1)))
	check("2D transforms snap to whole pixels",
			ProjectSettings.get_setting("rendering/2d/snap/snap_2d_transforms_to_pixel") == true)
	check("no autoloads (static helpers instead)",
			ProjectSettings.get_property_list().all(func(p): return not String(p.name).begins_with("autoload/")))

	section("a tap scores")
	game.running = false   # the clock is ours from here: advance() drives it
	game.begin_unit(1, false)
	var tp_before: int = game.score
	tap(game.box_rect().get_center())
	await frames(1)
	check("tapping the box scores (%d -> %d)" % [tp_before, game.score], game.score == tp_before + 1)
	var tp_miss: int = game.misses
	tap(Vector2(1, game.view_size().y - 1))
	await frames(1)
	check("tapping empty ground does not (misses %d -> %d)" % [tp_miss, game.misses],
			game.score == tp_before + 1 and game.misses == tp_miss + 1)

	section("the run: clear, fail, retry")
	game.begin_unit(1, false)
	game.score = game.goal()
	advance(game.UNIT_TIME + 1.0)
	check("reaching the goal clears the round", game.state == game.State.CLEARED)
	var rn_total: int = game.total
	game.tap(Vector2.ZERO)
	check("a tap after clearing starts the next round", game.unit == 2 and game.state == game.State.PLAYING)
	advance(game.UNIT_TIME + 1.0)
	check("running out of time fails it", game.state == game.State.FAILED)
	game.score = 3
	game.tap(Vector2.ZERO)
	check("retry rolls back to the round's start (unit %d, total %d)" % [game.unit, game.total],
			game.unit == 2 and game.total == rn_total and game.score == 0 and game.state == game.State.PLAYING)
	check("every system was reset with it (clock full)", is_equal_approx(game.time_left, game.UNIT_TIME))

	section("the visual layer never changes scored state")
	# The rule that lets "make it feel alive" work run unattended: run the
	# visual layer hard and compare everything the game keeps score with,
	# including the rules RNG's state (visuals must use their own dice).
	game.begin_unit(1, false)
	var vl_before: Array = game.rules_snapshot()
	for i in 20:
		game._burst(game.box_rect().get_center())
	for i in 600:   # 60 s of visuals
		game.tick_visuals(0.1)
	check("60 s of visuals change nothing the game keeps score with", game.rules_snapshot() == vl_before)
	check("and the phase stays wrapped (%.2f)" % game.phase, game.phase >= 0.0 and game.phase < TAU)

	section("art slots")
	# Every PNG dropped into art/sprites/ lands in a slot by file name; a slot
	# with no file is null, and the grey-box draws in its place.
	var as_names: PackedStringArray = game.list_art("res://art/sprites/")
	check("every sprite in art/sprites/ loaded into a slot (%d)" % as_names.size(),
			Array(as_names).all(func(n): return game.tex(String(n).get_basename()) is Texture2D))
	check("a missing slot is null, so the grey-box draws", game.tex("no_such_sprite_xyz") == null)
	# When the box art lands, uncomment:
	# check("the box has its art", game.tex("box") != null)

	section("UI through real taps")
	var ui_pause = game.pause_ui
	check("the pause button is on screen", ui_pause.button.is_visible_in_tree())
	pick(ui_pause.button)
	await frames(2)
	check("tapping it pauses the game", paused and ui_pause.is_open())
	# Park the box clear of the pause panel first: a tap on a random spot can
	# land on a pause-screen button and turn this check into a coin flip.
	game.box_pos = game.play_rect().position + Vector2.ONE * game.box_size()
	var ui_spot: Vector2 = game.box_rect().get_center()
	tap(ui_spot)
	await frames(1)
	check("the world takes no taps while paused",
			game.score == 0 and paused and not ui_pause._panel.get_global_rect().has_point(ui_spot))
	pick(ui_pause.resume_button)
	await frames(2)
	check("Resume un-pauses", not paused and not ui_pause.is_open())

	section("saving")
	Session.delete_save()
	game.begin_unit(3, false)
	game.total = 42
	game._unit_start = {"unit": 3, "total": 42}
	check("the game saves", game.save_game() and Session.has_save())
	check("atomically: no .tmp left behind", not FileAccess.file_exists(Session.save_path + ".tmp"))
	game.begin_unit(1, false)
	game.total = 0
	var sv_loaded: bool = game.load_game()   # call first: a label is formatted before its condition runs
	check("and loads back where it was (unit %d, total %d)" % [game.unit, game.total],
			sv_loaded and game.unit == 3 and game.total == 42)
	var sv_read: Dictionary = Session.read_save({"added_later": 7})
	check("keys added after a save was written load with their defaults", sv_read.get("added_later") == 7)
	check("the save carries its version", sv_read.get("version") == Session.SAVE_VERSION)

	section("lifecycle")
	# Losing focus (a call, switching apps) pauses AND saves - for the live game only.
	Session.delete_save()
	game._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	check("a test-driven game never auto-pauses or saves", not paused and not Session.has_save())
	game.running = true
	current_scene = game
	game._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	check("the live game pauses when the app loses focus", paused and ui_pause.is_open())
	check("and saves as it pauses", Session.has_save())
	ui_pause.close()
	current_scene = null
	game.running = false

	# --- add a section per feature above this line ---

	Session.delete_test_files()
	_finish()


func _finish() -> void:
	paused = false
	print("\n=== %d checks, %d failed ===" % [checks, failures.size()])
	for f in failures:
		print("  FAILED: %s" % f)
	quit(1 if failures.size() > 0 else 0)
