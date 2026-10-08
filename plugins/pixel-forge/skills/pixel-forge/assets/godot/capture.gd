extends SceneTree
## Renders the real game in a WINDOW and saves PNGs: how Claude sees the game.
##     godot --path . --script res://tools/capture.gd ++ scenario=main,round_end
## Options after ++ :
##     scenario=a,b,c   which scenarios (default main; list=1 prints them)
##     out=docs/screens folder (relative to the project, or res://, user://, absolute)
##     scale=1          output size = viewport x scale, nearest-neighbour
##     wait=3           frames to wait before the grab
##     sheet=1          also write contact_sheet.png when there are 2+ shots
##
## NEVER --headless: headless has no renderer (blank images) and never compiles
## shaders, so a broken shader passes there. A shader that fails to compile
## (e.g. a `return` in fragment()) can draw the level solid white while the
## headless smoke test passes; only a windowed render's log shows SHADER ERROR.
## So after every run, grep the output for SHADER ERROR and SCRIPT ERROR, then
## Read the PNGs. Shots land in docs/screens/ (gitignored); copy the ones that
## record a decision into docs/screens/keep/.
##
## Each scenario boots a FRESH game, drives time by hand (advance) so the shot
## is repeatable, and sets up exactly the state to show. Add one: write
## _sc_<name>(g) and register it in _initialize(). Common traps, each of which
## costs a round when missed, handled here:
## * the window loses focus and the game pauses itself -> _unstick() every frame
## * a paused or hand-driven game does not redraw -> queue_redraw() on EVERY
##   CanvasItem, then wait frames AND RenderingServer.frame_post_draw, or the
##   PNG shows the previous frame
## * hand-placed state gets undone by the first tick (timers firing) -> park
##   the timers in the scenario (e.g. g.systems[1].every = INF)
## * things invisible at game scale (1 px sparks, 9 px arrows) -> judge shots
##   at scale=1; use scale=2+ only to inspect detail

const MAIN_SCENE := "res://scenes/main.tscn"
const STEP := 0.05

var game
var scenarios := {}
var out_dir := "res://docs/screens"
var out_scale := 1
var wait := 3
var sheet := true
var allow_pause := false     # a scenario that shows the pause screen sets this
var view := Vector2i.ZERO
var shots: Array[String] = []


func _initialize() -> void:
	scenarios = {
		"main": _sc_main,             # the game a second in
		"busy": _sc_busy,             # mid-round, effects flying
		"round_end": _sc_round_end,   # the round-cleared banner
		"paused": _sc_paused,         # the pause screen over the world
	}
	_run.call_deferred()


# --- scenarios: set up exactly the state to show --------------------------------

func _sc_main(g) -> void:
	advance(g, 1.0)


func _sc_busy(g) -> void:
	g.score = 3
	advance(g, 0.5)
	for i in 3:
		g._burst(g.box_rect().get_center())
		advance(g, 0.1)


func _sc_round_end(g) -> void:
	g.score = g.goal()
	advance(g, g.UNIT_TIME + 0.1)


func _sc_paused(g) -> void:
	advance(g, 1.0)
	allow_pause = true
	g.pause_ui.open()


# --- harness ------------------------------------------------------------------------

func _run() -> void:
	var names: PackedStringArray = ["main"]
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"scenario", "scenarios": names = kv[1].split(",", false)
			"out": out_dir = kv[1]
			"scale": out_scale = maxi(1, int(kv[1]))
			"wait": wait = maxi(1, int(kv[1]))
			"sheet": sheet = kv[1] != "0"
			"list":
				print("scenarios: ", ", ".join(PackedStringArray(scenarios.keys())))
				quit(0)
				return
	if DisplayServer.get_name() == "headless":
		print("capture.gd needs a window: run it WITHOUT --headless")
		quit(1)
		return
	if not (out_dir.begins_with("res://") or out_dir.begins_with("user://") or out_dir.is_absolute_path()):
		out_dir = "res://" + out_dir
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	view = Vector2i(ProjectSettings.get_setting("display/window/size/viewport_width"),
			ProjectSettings.get_setting("display/window/size/viewport_height"))
	DisplayServer.window_set_size(view)   # the frame is exactly the logical size
	Session.use_test_paths("capture")     # a capture never touches the player's save
	var bad := 0
	for n in names:
		if not scenarios.has(n):
			print("unknown scenario '%s' (have: %s)" % [n, ", ".join(PackedStringArray(scenarios.keys()))])
			bad += 1
			continue
		await _boot()
		await scenarios[n].call(game)
		await shot(n)
		allow_pause = false
		paused = false
		game.queue_free()
		await process_frame
	if sheet and shots.size() > 1:
		_contact_sheet()
	Session.delete_test_files()
	# worded so that the reminder itself never matches the error grep
	print("\nNext: grep this output for shader and script errors (the patterns are in the")
	print("header of tools/capture.gd) - a broken shader still lets every shot save.")
	print("Then Read the PNGs in %s." % out_dir)
	quit(1 if bad > 0 else 0)


## A fresh game per scenario, with its clock in our hands and fixed dice.
func _boot() -> void:
	seed(7)
	game = load(MAIN_SCENE).instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	if "running" in game:
		game.running = false
	if "rng" in game:
		game.rng.seed = 7
	if "vis_rng" in game:
		game.vis_rng.seed = 7
	if game.has_method("begin_unit"):
		game.begin_unit(1, false)


## Run the rules and the visual layer forward by hand.
func advance(g, seconds: float) -> void:
	var t := 0.0
	while t < seconds - 0.0001:
		if g.has_method("tick"):
			g.tick(STEP)
		if g.has_method("tick_visuals"):
			g.tick_visuals(STEP)
		t += STEP


## The capture window loses focus, and a game that pauses itself on focus loss
## would freeze mid-shot behind its pause screen. Undo that every frame.
func _unstick() -> void:
	if allow_pause:
		return
	paused = false
	for n in get_nodes_in_group("pause_ui"):
		if n.has_method("is_open") and n.has_method("close"):
			if n.is_open():
				n.close()
		elif n is CanvasItem or n is CanvasLayer:
			n.visible = false


func _redraw_all(n: Node) -> void:
	if n is CanvasItem:
		(n as CanvasItem).queue_redraw()
	for c in n.get_children():
		_redraw_all(c)


func shot(shot_name: String) -> void:
	_unstick()
	_redraw_all(root)
	for i in wait:
		await process_frame
		_unstick()
		_redraw_all(root)
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	var want := view * out_scale
	if img.get_size() != want:
		img.resize(want.x, want.y, Image.INTERPOLATE_NEAREST)
	var path := out_dir.path_join(shot_name + ".png")
	img.save_png(ProjectSettings.globalize_path(path))
	shots.append(path)
	var note := "" if _has_detail(img) else "   <- ONE FLAT COLOUR: nothing drew?"
	print("  saved %s (%dx%d)%s" % [path, img.get_width(), img.get_height(), note])


## False when every sampled pixel is the same colour (a blank frame).
func _has_detail(img: Image) -> bool:
	var first := img.get_pixel(0, 0)
	for y in range(0, img.get_height(), maxi(1, img.get_height() / 16)):
		for x in range(0, img.get_width(), maxi(1, img.get_width() / 16)):
			if not img.get_pixel(x, y).is_equal_approx(first):
				return true
	return false


## Every shot of this run side by side, in order, on one image.
func _contact_sheet() -> void:
	var cell := view * out_scale
	var gap := 4
	var cols := int(ceil(sqrt(float(shots.size()))))
	var rows := int(ceil(float(shots.size()) / cols))
	var sheet_img := Image.create(cols * cell.x + (cols + 1) * gap, rows * cell.y + (rows + 1) * gap,
			false, Image.FORMAT_RGBA8)
	sheet_img.fill(Color(0.08, 0.08, 0.1))
	for i in shots.size():
		var img := Image.load_from_file(ProjectSettings.globalize_path(shots[i]))
		img.convert(Image.FORMAT_RGBA8)
		var at := Vector2i(gap + (i % cols) * (cell.x + gap), gap + (i / cols) * (cell.y + gap))
		sheet_img.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), at)
	var path := out_dir.path_join("contact_sheet.png")
	sheet_img.save_png(ProjectSettings.globalize_path(path))
	print("  saved %s (left to right, top to bottom: %s)" % [path, ", ".join(PackedStringArray(shots.map(func(s): return s.get_file().get_basename())))])
