extends SceneTree
## Watches the real game run in REAL TIME (not driven by hand, not headless)
## and saves a frame every few seconds - for what only shows in motion:
## critters stuck in walls, actors frozen after a reset, effects left behind,
## facing that flickers. (A good start: a frame every 4 s for 40 s.)
##     godot --path . --script res://tools/watch.gd ++ every=4 for=40
## Options after ++ :  every=SECONDS  for=SECONDS  out=docs/screens  prefix=watch
##                     sheet=1 (also a contact sheet of all frames)
## Writes <out>/<prefix>_00.png, _01, ... Grep the output for SHADER ERROR and
## SCRIPT ERROR afterwards, as with capture.gd.
##
## ACTS schedules things to happen along the way (seconds -> method name on
## this script), so effects show in motion too.

const MAIN_SCENE := "res://scenes/main.tscn"
const ACTS := {3.0: "_act_tap_box", 6.0: "_act_tap_box", 9.0: "_act_tap_box"}

var game
var every := 4.0
var duration := 40.0
var out_dir := "res://docs/screens"
var prefix := "watch"
var sheet := false
var saved: Array[String] = []


func _act_tap_box() -> void:
	game.tap(game.box_rect().get_center())


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"every": every = maxf(0.1, float(kv[1]))
			"for": duration = float(kv[1])
			"out": out_dir = kv[1]
			"prefix": prefix = kv[1]
			"sheet": sheet = kv[1] != "0"
	if DisplayServer.get_name() == "headless":
		print("watch.gd needs a window: run it WITHOUT --headless")
		quit(1)
		return
	if not (out_dir.begins_with("res://") or out_dir.begins_with("user://") or out_dir.is_absolute_path()):
		out_dir = "res://" + out_dir
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var view := Vector2i(ProjectSettings.get_setting("display/window/size/viewport_width"),
			ProjectSettings.get_setting("display/window/size/viewport_height"))
	DisplayServer.window_set_size(view)
	Session.use_test_paths("watch")
	seed(7)
	game = load(MAIN_SCENE).instantiate()
	root.add_child(game)
	await process_frame
	var pending := ACTS.keys()
	pending.sort()
	var t := 0.0
	var n := 0
	while t < duration + 0.001:
		await process_frame
		_unstick()
		t += root.get_process_delta_time()
		while not pending.is_empty() and t >= float(pending[0]):
			call(ACTS[pending[0]])
			pending.remove_at(0)
		if t >= (n + 1) * every:
			await RenderingServer.frame_post_draw
			var img := root.get_texture().get_image()
			if img.get_size() != view:
				img.resize(view.x, view.y, Image.INTERPOLATE_NEAREST)
			var path := out_dir.path_join("%s_%02d.png" % [prefix, n])
			img.save_png(ProjectSettings.globalize_path(path))
			saved.append(path)
			print("  %s at %.1fs" % [path, t])
			n += 1
	if sheet and saved.size() > 1:
		_contact_sheet(view)
	Session.delete_test_files()
	print("\nNext: grep this output for shader and script errors, then Read the frames.")
	quit(0)


## The window loses focus and the game would pause itself: undo it.
func _unstick() -> void:
	paused = false
	for p in get_nodes_in_group("pause_ui"):
		if p.has_method("is_open") and p.has_method("close") and p.is_open():
			p.close()


func _contact_sheet(cell: Vector2i) -> void:
	var gap := 4
	var cols := int(ceil(sqrt(float(saved.size()))))
	var rows := int(ceil(float(saved.size()) / cols))
	var img := Image.create(cols * cell.x + (cols + 1) * gap, rows * cell.y + (rows + 1) * gap, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.08, 0.08, 0.1))
	for i in saved.size():
		var f := Image.load_from_file(ProjectSettings.globalize_path(saved[i]))
		f.convert(Image.FORMAT_RGBA8)
		img.blit_rect(f, Rect2i(Vector2i.ZERO, f.get_size()),
				Vector2i(gap + (i % cols) * (cell.x + gap), gap + (i / cols) * (cell.y + gap)))
	var path := out_dir.path_join("%s_sheet.png" % prefix)
	img.save_png(ProjectSettings.globalize_path(path))
	print("  ", path)
