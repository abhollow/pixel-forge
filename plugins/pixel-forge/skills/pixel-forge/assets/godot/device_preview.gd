extends SceneTree
## The game as a phone of a given resolution shows it - without a phone. The
## game is laid out at its own viewport size and drawn into a SubViewport the
## size of the device screen, exactly as canvas_items stretch does on the
## device: size_2d_override = the logical size, size_2d_override_stretch on.
## aspect "keep" letterboxes; "expand" shows more world on the long side.
## (E.g. size=1920x1080 for a 960x540 layout, to judge whether detailed 2x
## sprites are worth it.)
##     godot --path . --script res://tools/device_preview.gd ++ size=1080x2400
## Options after ++ :  size=WxH (device pixels)  out=docs/screens/device_WxH.png
##                     settle=1.0 (seconds of game time before the shot)
## Not headless (headless renders nothing). Grep for SHADER ERROR afterwards.
##
## Text and UI drawn at full resolution look sharper here than in a plain
## capture - that is what the phone shows. Judge pixel-art density here.

const MAIN_SCENE := "res://scenes/main.tscn"
const STEP := 0.05


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var dev := Vector2i(1080, 2400)
	var out := ""
	var settle := 1.0
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"size":
				var wh := kv[1].to_lower().split("x")
				if wh.size() == 2:
					dev = Vector2i(int(wh[0]), int(wh[1]))
			"out": out = kv[1]
			"settle": settle = float(kv[1])
	if DisplayServer.get_name() == "headless":
		print("device_preview.gd needs a window: run it WITHOUT --headless")
		quit(1)
		return
	if out == "":
		out = "docs/screens/device_%dx%d.png" % [dev.x, dev.y]
	if not (out.begins_with("res://") or out.begins_with("user://") or out.is_absolute_path()):
		out = "res://" + out
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out.get_base_dir()))

	var base := Vector2(ProjectSettings.get_setting("display/window/size/viewport_width"),
			ProjectSettings.get_setting("display/window/size/viewport_height"))
	var aspect: String = ProjectSettings.get_setting("display/window/stretch/aspect")
	var k := minf(dev.x / base.x, dev.y / base.y)   # device pixels per game pixel
	var logical := base
	var frame := Vector2i(roundi(base.x * k), roundi(base.y * k))
	if aspect != "keep":
		# expand (and its keep_width/keep_height cousins): the layout grows
		# along the long side and fills the screen
		logical = (Vector2(dev) / k).floor()
		frame = dev
	print("device %dx%d, %.2f device px per game px, layout %dx%d, aspect %s" % [
			dev.x, dev.y, k, logical.x, logical.y, aspect])

	var sub := SubViewport.new()
	sub.size = frame
	sub.size_2d_override = Vector2i(logical)
	sub.size_2d_override_stretch = true
	sub.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	sub.transparent_bg = false
	root.add_child(sub)
	Session.use_test_paths("device_preview")
	seed(7)
	var game = load(MAIN_SCENE).instantiate()
	sub.add_child(game)
	await process_frame
	if "running" in game:
		game.running = false
	if game.has_method("begin_unit"):
		game.begin_unit(1, false)
	var t := 0.0
	while t < settle:
		if game.has_method("tick"):
			game.tick(STEP)
		if game.has_method("tick_visuals"):
			game.tick_visuals(STEP)
		t += STEP
	_redraw_all(sub)
	for i in 3:
		await process_frame
		paused = false
	await RenderingServer.frame_post_draw
	var img := sub.get_texture().get_image()
	if frame != dev:   # letterbox onto the full device screen
		var full := Image.create(dev.x, dev.y, false, img.get_format())
		full.fill(Color.BLACK)
		full.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), (dev - frame) / 2)
		img = full
	img.save_png(ProjectSettings.globalize_path(out))
	print("  saved %s (%dx%d)" % [out, img.get_width(), img.get_height()])
	Session.delete_test_files()
	quit(0)


func _redraw_all(n: Node) -> void:
	if n is CanvasItem:
		(n as CanvasItem).queue_redraw()
	for c in n.get_children():
		_redraw_all(c)
