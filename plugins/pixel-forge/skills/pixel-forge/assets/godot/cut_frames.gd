extends SceneTree
## Cuts animation frames (or loose objects) out of a generated sprite sheet,
## with no Python - Godot alone (for a machine or sandbox where Python is
## missing). Copy to tools/cut_frames.gd.
##     godot --headless --path . --script res://tools/cut_frames.gd ++ spec=raw_art/enemy/cut.json
##     godot --headless --path . --script res://tools/cut_frames.gd ++ self_test=1
## Then  godot --headless --path . --import  - new sprites do not draw until
## the import cache knows them.
##
## The spec is JSON: one object, or a list of them.
## {
##   "sheet": "raw_art/enemy/walk_option_C.png",  project-relative, res:// or absolute
##   "key": "magenta",       magenta | green | corner (top-left pixel) | "#rrggbb"
##   "tolerance": 0.45,      RGB distance from the key still counted as background
##   "rows": ["side", "front", "back"],   one name per row of frames, top to bottom
##   "frames": 4,            frames per row, or a list per row [4, 4, 2]; asserted
##   "scale_by": {"color": "#e07020", "tol": 0.25, "width": 16},
##                           scale so this FEATURE is `width` px wide, measured on
##                           frame [row, frame] (default the first). Scale from the
##                           subject, not the box: frames carrying flying dust
##                           would shrink the body if the box were measured.
##   "width": 16,            ...or the widest frame becomes this wide
##   "height": 24,           ...or the tallest frame becomes this tall
##   "scale": 0.25,          ...or a plain factor (default 1)
##   "anchor": "bottom",     bottom | top | centre | left | right | bottom-left |
##                           bottom-right: where each frame sits in the shared
##                           canvas. Feet on the ground: bottom. Flying: centre.
##   "shared": "row",        one canvas per row (default) or "all" rows
##   "out": "art/sprites/enemy_{row}_f{i}.png",   {row} name, {i} frame, {n} overall
##   "gap": 6,               background px that separate frames / rows
##   "speck": 8              shorter runs are noise, not frames
## }
## What it does, in order (each step prevents a known failure): frames found by projection
## on the key, rows first; ONE scale factor for every frame of the spec, so the
## subject is the same size walking and jumping; key to transparent BLACK
## before resizing (magenta left in would blend into a pink fringe); a manual
## box-average downscale (Godot's Image.resize has no box filter, and Lanczos
## rings); hard alpha (0 or 255); each set on one shared canvas, anchored -
## cropping frames separately makes them jitter.

var failed := false


func _initialize() -> void:
	var spec_path := ""
	var self_test := false
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() == 2 and kv[0] == "spec":
			spec_path = kv[1]
		elif kv.size() == 2 and kv[0] == "self_test":
			self_test = kv[1] == "1"
	if self_test:
		quit(_self_test())
		return
	if spec_path == "":
		print("usage: ++ spec=path/to/cut.json   (or ++ self_test=1)")
		quit(2)
		return
	var f := FileAccess.open(_abs(spec_path), FileAccess.READ)
	if f == null:
		print("cannot read spec %s" % spec_path)
		quit(1)
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	var specs: Array = parsed if parsed is Array else [parsed]
	for s in specs:
		if not (s is Dictionary):
			print("spec entries must be objects")
			quit(1)
			return
		cut(s)
	print("\n%s. Next: godot --headless --path . --import" % ("FAILED" if failed else "done"))
	quit(1 if failed else 0)


## A path from a spec: project-relative unless res://, user:// or absolute.
func _abs(p: String) -> String:
	if p.begins_with("res://") or p.begins_with("user://"):
		return ProjectSettings.globalize_path(p)
	if p.is_absolute_path():
		return p
	return ProjectSettings.globalize_path("res://" + p)


func _fail(msg: String) -> Array:
	print("  FAIL  " + msg)
	failed = true
	return []


## Cut one spec. Returns the written paths ([] on failure).
func cut(spec: Dictionary) -> Array:
	var img := Image.load_from_file(_abs(String(spec.get("sheet", ""))))
	if img == null or img.is_empty():
		return _fail("cannot load sheet %s" % spec.get("sheet", "?"))
	img.convert(Image.FORMAT_RGBA8)
	var w := img.get_width()
	var h := img.get_height()
	var data := img.get_data()
	var key := _key_colour(String(spec.get("key", "magenta")), data)
	var tol := float(spec.get("tolerance", 0.45))
	var gap := int(spec.get("gap", 6))
	var speck := int(spec.get("speck", 8))
	print("%s (%dx%d), key %s" % [spec.get("sheet"), w, h, key.to_html(false)])

	# foreground mask: 1 where the pixel is art
	var fg := PackedByteArray()
	fg.resize(w * h)
	var t2 := tol * tol
	for i in w * h:
		var o := i * 4
		if data[o + 3] < 128:
			continue
		var dr := data[o] / 255.0 - key.r
		var dg := data[o + 1] / 255.0 - key.g
		var db := data[o + 2] / 255.0 - key.b
		if dr * dr + dg * dg + db * db > t2:
			fg[i] = 1

	# rows, then frames within each row, by projection
	var rowocc := PackedByteArray()
	rowocc.resize(h)
	for y in h:
		for x in w:
			if fg[y * w + x] == 1:
				rowocc[y] = 1
				break
	var rows: Array = []   # Array of Arrays of Rect2i
	for r in _spans(rowocc, gap, speck):
		var colocc := PackedByteArray()
		colocc.resize(w)
		for x in w:
			for y in range(r.x, r.y + 1):
				if fg[y * w + x] == 1:
					colocc[x] = 1
					break
		var boxes: Array = []
		for c in _spans(colocc, gap, speck):
			boxes.append(_tight(fg, w, Rect2i(c.x, r.x, c.y - c.x + 1, r.y - r.x + 1)))
		rows.append(boxes)

	# the counts the spec promises
	var names: Array = spec.get("rows", [])
	if names.is_empty():
		for i in rows.size():
			names.append(str(i))
	var found := PackedStringArray()
	for r in rows:
		found.append(str(r.size()))
	if rows.size() != names.size():
		return _fail("expected %d rows, found %d (frames per row: %s) - adjust gap/speck or the sheet" % [
				names.size(), rows.size(), ", ".join(found)])
	var want_frames = spec.get("frames", null)
	for i in rows.size():
		var want := -1
		if want_frames is Array:
			want = int(want_frames[i])
		elif want_frames != null:
			want = int(want_frames)
		if want >= 0 and rows[i].size() != want:
			return _fail("row %s: expected %d frames, found %d (all rows: %s)" % [names[i], want, rows[i].size(), ", ".join(found)])

	# ONE scale for every frame of the spec
	var k := float(spec.get("scale", 1.0))
	if spec.has("scale_by"):
		var sb: Dictionary = spec.scale_by
		var at: Array = sb.get("frame_at", [0, 0])
		var ref: Rect2i = rows[int(at[0])][int(at[1])]
		var fw := _feature_width(data, w, ref, Color(String(sb.get("color", "#ffffff"))), float(sb.get("tol", 0.25)))
		if fw <= 0:
			return _fail("scale_by colour %s not found in frame %s" % [sb.get("color"), at])
		k = float(sb.get("width", fw)) / fw
	elif spec.has("width"):
		var mw := 1
		for r in rows:
			for b in r:
				mw = maxi(mw, b.size.x)
		k = float(spec.width) / mw
	elif spec.has("height"):
		var mh := 1
		for r in rows:
			for b in r:
				mh = maxi(mh, b.size.y)
		k = float(spec.height) / mh

	# cut, key, scale, harden
	var cut_rows: Array = []
	for r in rows:
		var imgs: Array = []
		for b in r:
			imgs.append(_harden(_rescale(_keyed(data, fg, w, b), k)))
		cut_rows.append(imgs)

	# shared canvases, anchored
	var anchor := String(spec.get("anchor", "bottom"))
	var shared_all := String(spec.get("shared", "row")) == "all"
	var all_size := Vector2i.ZERO
	for imgs in cut_rows:
		for im in imgs:
			all_size = _vmax(all_size, im.get_size())
	var pattern := String(spec.get("out", "art/sprites/frame_{row}_f{i}.png"))
	var written: Array = []
	var n := 0
	for ri in cut_rows.size():
		var imgs: Array = cut_rows[ri]
		var size := all_size
		if not shared_all:
			size = Vector2i.ZERO
			for im in imgs:
				size = _vmax(size, im.get_size())
		for i in imgs.size():
			var im: Image = imgs[i]
			var canvas := Image.create(size.x, size.y, false, Image.FORMAT_RGBA8)
			canvas.blit_rect(im, Rect2i(Vector2i.ZERO, im.get_size()), _place(anchor, size, im.get_size()))
			var path := _abs(pattern.replace("{row}", str(names[ri])).replace("{i}", str(i)).replace("{n}", str(n)))
			DirAccess.make_dir_recursive_absolute(path.get_base_dir())
			canvas.save_png(path)
			written.append(path)
			n += 1
		print("  %s: %d frames on %dx%d (scale %.4f)" % [names[ri], imgs.size(), size.x, size.y, k])
	return written


func _vmax(a: Vector2i, b: Vector2i) -> Vector2i:
	return Vector2i(maxi(a.x, b.x), maxi(a.y, b.y))


func _key_colour(key: String, data: PackedByteArray) -> Color:
	match key:
		"magenta":
			return Color(1, 0, 1)
		"green":
			return Color(0, 1, 0)
		"corner":
			return Color8(data[0], data[1], data[2])
	return Color(key)


## Runs of 1s in occ separated by more than `gap` 0s; runs shorter than `speck`
## are dropped (a stray speck must not become a row and shift every frame).
func _spans(occ: PackedByteArray, gap: int, speck: int) -> Array:
	var out: Array = []
	var start := -1
	var last := -1
	for i in occ.size():
		if occ[i] == 1:
			if start >= 0 and i - last - 1 > gap:
				out.append(Vector2i(start, last))
				start = -1
			if start < 0:
				start = i
			last = i
	if start >= 0:
		out.append(Vector2i(start, last))
	return out.filter(func(s): return s.y - s.x + 1 >= speck)


## The box shrunk to the art actually inside it.
func _tight(fg: PackedByteArray, w: int, b: Rect2i) -> Rect2i:
	var x0 := b.end.x
	var y0 := b.end.y
	var x1 := b.position.x - 1
	var y1 := b.position.y - 1
	for y in range(b.position.y, b.end.y):
		for x in range(b.position.x, b.end.x):
			if fg[y * w + x] == 1:
				x0 = mini(x0, x)
				x1 = maxi(x1, x)
				y0 = mini(y0, y)
				y1 = maxi(y1, y)
	if x1 < x0:
		return b
	return Rect2i(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


## Width in px of the pixels near `col` inside box b (the feature to scale by).
func _feature_width(data: PackedByteArray, w: int, b: Rect2i, col: Color, tol: float) -> int:
	var x0 := b.end.x
	var x1 := -1
	var t2 := tol * tol
	for y in range(b.position.y, b.end.y):
		for x in range(b.position.x, b.end.x):
			var o := (y * w + x) * 4
			var dr := data[o] / 255.0 - col.r
			var dg := data[o + 1] / 255.0 - col.g
			var db := data[o + 2] / 255.0 - col.b
			if data[o + 3] >= 128 and dr * dr + dg * dg + db * db <= t2:
				x0 = mini(x0, x)
				x1 = maxi(x1, x)
	return x1 - x0 + 1 if x1 >= x0 else 0


## The frame with every background pixel set to transparent BLACK.
func _keyed(data: PackedByteArray, fg: PackedByteArray, w: int, b: Rect2i) -> Image:
	var out := PackedByteArray()
	out.resize(b.size.x * b.size.y * 4)
	for y in b.size.y:
		for x in b.size.x:
			var si := (b.position.y + y) * w + b.position.x + x
			if fg[si] == 1:
				var o := (y * b.size.x + x) * 4
				out[o] = data[si * 4]
				out[o + 1] = data[si * 4 + 1]
				out[o + 2] = data[si * 4 + 2]
				out[o + 3] = data[si * 4 + 3]
	return Image.create_from_data(b.size.x, b.size.y, false, Image.FORMAT_RGBA8, out)


## Box-average downscale by k (area-weighted, alpha-premultiplied); nearest
## for k > 1. Keeps the pixel grid honest where Lanczos rings.
func _rescale(src: Image, k: float) -> Image:
	var sw := src.get_width()
	var sh := src.get_height()
	var ow := maxi(1, roundi(sw * k))
	var oh := maxi(1, roundi(sh * k))
	if ow == sw and oh == sh:
		return src
	if k > 1.0:
		var up := src.duplicate()
		up.resize(ow, oh, Image.INTERPOLATE_NEAREST)
		return up
	var s := src.get_data()
	var out := PackedByteArray()
	out.resize(ow * oh * 4)
	var fx := float(sw) / ow
	var fy := float(sh) / oh
	for oy in oh:
		var y0 := oy * fy
		var y1 := y0 + fy
		for ox in ow:
			var x0 := ox * fx
			var x1 := x0 + fx
			var sr := 0.0
			var sg := 0.0
			var sb := 0.0
			var sa := 0.0
			var sw_total := 0.0
			for sy in range(int(y0), mini(sh, int(ceil(y1)))):
				var wy := minf(y1, sy + 1.0) - maxf(y0, float(sy))
				for sx in range(int(x0), mini(sw, int(ceil(x1)))):
					var wt := wy * (minf(x1, sx + 1.0) - maxf(x0, float(sx)))
					var i := (sy * sw + sx) * 4
					var a := s[i + 3] / 255.0
					sr += s[i] * a * wt
					sg += s[i + 1] * a * wt
					sb += s[i + 2] * a * wt
					sa += a * wt
					sw_total += wt
			var o := (oy * ow + ox) * 4
			if sa > 0.0:
				out[o] = clampi(roundi(sr / sa), 0, 255)
				out[o + 1] = clampi(roundi(sg / sa), 0, 255)
				out[o + 2] = clampi(roundi(sb / sa), 0, 255)
				out[o + 3] = clampi(roundi(sa / sw_total * 255.0), 0, 255)
	return Image.create_from_data(ow, oh, false, Image.FORMAT_RGBA8, out)


## Hard alpha: every pixel fully opaque or fully transparent (black).
func _harden(img: Image) -> Image:
	var d := img.get_data()
	for i in range(0, d.size(), 4):
		if d[i + 3] >= 128:
			d[i + 3] = 255
		else:
			d[i] = 0
			d[i + 1] = 0
			d[i + 2] = 0
			d[i + 3] = 0
	return Image.create_from_data(img.get_width(), img.get_height(), false, Image.FORMAT_RGBA8, d)


func _place(anchor: String, canvas: Vector2i, size: Vector2i) -> Vector2i:
	var free := canvas - size
	var p := Vector2i(free.x / 2, free.y)    # bottom (default): feet on the ground
	match anchor:
		"top":
			p = Vector2i(free.x / 2, 0)
		"centre", "center":
			p = free / 2
		"left":
			p = Vector2i(0, free.y / 2)
		"right":
			p = Vector2i(free.x, free.y / 2)
		"bottom-left":
			p = Vector2i(0, free.y)
		"bottom-right":
			p = Vector2i(free.x, free.y)
	return p


# --- self-test: a synthetic sheet with known answers --------------------------------

func _self_test() -> int:
	var dir := "user://cut_frames_self_test"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	var sheet := Image.create(400, 220, false, Image.FORMAT_RGBA8)
	sheet.fill(Color(1, 0, 1))
	var body := Color8(40, 90, 200)
	var feature := Color8(230, 120, 30)
	# row 0: three 40x60 figures standing on y=90; row 1: three 30x40 figures, then a speck
	for i in 3:
		sheet.fill_rect(Rect2i(20 + i * 120, 30, 40, 60), body)
		sheet.fill_rect(Rect2i(30 + i * 120, 40, 20, 10), feature)        # the feature: 20 px wide
		sheet.fill_rect(Rect2i(25 + i * 120, 140 + i * 4, 30, 40 - i * 4), body)  # different heights
	sheet.set_pixel(390, 210, Color.BLACK)                                 # a speck: not a frame
	var sheet_path := dir + "/sheet.png"
	sheet.save_png(ProjectSettings.globalize_path(sheet_path))
	var paths := cut({"sheet": sheet_path, "key": "magenta", "rows": ["stand", "duck"], "frames": 3,
			"scale_by": {"color": feature.to_html(false), "width": 10}, "anchor": "bottom",
			"out": dir + "/t_{row}_f{i}.png"})
	var res := {"ok": true}   # lambdas capture locals by value: keep the flag in a dictionary
	var report := func(label: String, cond: bool) -> void:
		print("  %s  %s" % ["ok  " if cond else "FAIL", label])
		if not cond:
			res.ok = false
	report.call("six frames written (%d)" % paths.size(), paths.size() == 6)
	if paths.size() == 6:
		var f0 := Image.load_from_file(paths[0])
		report.call("one scale for all: 40x60 at k=0.5 -> 20x30 (%dx%d)" % [f0.get_width(), f0.get_height()],
				f0.get_size() == Vector2i(20, 30))
		var c := f0.get_pixel(10, 25)
		report.call("body colour survives the box average", c.is_equal_approx(body))
		var d2 := Image.load_from_file(paths[5])
		report.call("row 2 shares one canvas (15x20): %dx%d" % [d2.get_width(), d2.get_height()],
				d2.get_size() == Vector2i(15, 20))
		report.call("shorter frame anchored to the bottom (top row empty)", d2.get_pixel(7, 0).a == 0.0 and d2.get_pixel(7, 19).a == 1.0)
		var hard := true
		var pinkish := false
		for p in paths:
			var im := Image.load_from_file(p)
			for y in im.get_height():
				for x in im.get_width():
					var px := im.get_pixel(x, y)
					if px.a > 0.0 and px.a < 1.0:
						hard = false
					if px.a > 0.0 and px.r > 0.6 and px.b > 0.6 and px.g < 0.4:
						pinkish = true
		report.call("hard alpha everywhere", hard)
		report.call("no magenta fringe", not pinkish)
	var bad := cut({"sheet": sheet_path, "key": "magenta", "rows": ["only"], "frames": 3,
			"out": dir + "/bad_{i}.png"})
	failed = false
	report.call("a wrong row count is refused", bad.is_empty())
	print("cut_frames self-test: %s" % ("ok" if res.ok else "FAILED"))
	return 0 if res.ok else 1
