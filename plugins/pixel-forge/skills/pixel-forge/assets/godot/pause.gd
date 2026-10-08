extends CanvasLayer
## The pause screen over the game: the world dims and stops; Resume, and the
## volume settings. It opens from the corner button, P or Esc, the Android
## back button, and BY ITSELF whenever the app loses focus (switching apps, a
## call, the window left) - and the game is saved as it opens, because a phone
## may never resume the process. It never resumes play on its own: dropping
## someone back into danger after a phone call is a cheap hit.
##
## Wiring (main.gd does this):
##     pause_ui = preload("res://scripts/pause.gd").new()
##     pause_ui.main = self            # needs main.save_game() -> bool
##     add_child(pause_ui)
##   and in main._notification: APPLICATION_FOCUS_OUT / APPLICATION_PAUSED /
##   WM_GO_BACK_REQUEST -> pause_ui.open() (only for the live game, see _live()).
##
## It is in the "pause_ui" group so harnesses (tools/capture.gd) can close it:
## a capture window loses focus and the game would pause itself mid-shot.
## Sizes follow the viewport, so it fits 320x180 and 1080x1920 alike.

var main: Node
var overlay: Control
var button: Button          # the corner pause button
var resume_button: Button
var _panel: Control
var _settings: Control
var _saved: Label


func _ready() -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS   # it has to work while everything else is paused
	add_to_group("pause_ui")
	var vp: Vector2 = get_viewport().get_visible_rect().size
	var fs: int = clampi(int(minf(vp.x, vp.y) / 18.0), 8, 28)

	# the corner button, visible while playing
	button = Button.new()
	button.text = "II"
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", fs)
	var side := roundf(fs * 2.4)
	var margin := roundf(fs * 0.5)
	button.custom_minimum_size = Vector2(side, side)
	button.pressed.connect(open)
	add_child(button)
	# pinned to the top-right corner with explicit offsets (a preset computed
	# from the minimum size before it updates would overhang the edge)
	button.anchor_left = 1.0
	button.anchor_right = 1.0
	button.offset_left = -side - margin
	button.offset_right = -margin
	button.offset_top = margin
	button.offset_bottom = margin + side

	overlay = Control.new()
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.visible = false
	add_child(overlay)
	var dim := ColorRect.new()
	dim.color = Color(0.01, 0.01, 0.03, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP   # the world underneath takes no taps
	overlay.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(center)

	_panel = _box(fs)
	center.add_child(_panel)
	var col: VBoxContainer = _panel.get_child(0)
	col.add_child(_label("PAUSED", fs + 4))
	resume_button = _button("Resume", close, fs)
	col.add_child(resume_button)
	col.add_child(_button("Settings", _show_settings, fs))
	_saved = _label("", maxi(8, fs - 6))
	_saved.modulate = Color(1, 1, 1, 0.7)
	col.add_child(_saved)

	_settings = _box(fs)
	_settings.visible = false
	center.add_child(_settings)
	var sc: VBoxContainer = _settings.get_child(0)
	sc.add_child(_label("SETTINGS", fs + 2))
	for row in [["Music", "music"], ["Sound", "sfx"]]:
		var line := HBoxContainer.new()
		line.add_theme_constant_override("separation", int(fs * 0.5))
		var l := _label(row[0], fs)
		l.custom_minimum_size = Vector2(fs * 4.5, 0)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
		line.add_child(l)
		var s := HSlider.new()
		s.min_value = 0.0
		s.max_value = 1.0
		s.step = 0.05
		s.value = Session.settings.get(row[1], 0.5)
		s.custom_minimum_size = Vector2(fs * 7, fs * 1.4)
		s.focus_mode = Control.FOCUS_NONE
		s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var key: String = row[1]
		s.value_changed.connect(_on_slider.bind(key))
		line.add_child(s)
		sc.add_child(line)
	sc.add_child(_button("Back", _back, fs))


func is_open() -> bool:
	return overlay.visible


func open() -> void:
	if overlay.visible:
		return
	var ok: bool = main != null and main.has_method("save_game") and main.save_game()
	_saved.text = "game saved" if ok else ""
	_back()
	overlay.visible = true
	button.visible = false
	get_tree().paused = true


func close() -> void:
	if overlay.visible:
		Session.save_settings()
	overlay.visible = false
	button.visible = true
	get_tree().paused = false


func _show_settings() -> void:
	_panel.visible = false
	_settings.visible = true


func _back() -> void:
	_settings.visible = false
	_panel.visible = true


func _on_slider(value: float, key: String) -> void:
	Session.settings[key] = value
	Session.apply()   # live; written to disk when the pause screen closes


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and (event.keycode == KEY_ESCAPE or event.keycode == KEY_P):
		if overlay.visible:
			close()
		else:
			open()
		get_viewport().set_input_as_handled()


func _box(fs: int) -> PanelContainer:
	var p := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.04, 0.06, 0.85)
	sb.border_color = Color(1, 1, 1, 0.12)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(maxi(2, int(fs * 0.33)))
	sb.set_content_margin_all(fs)
	p.add_theme_stylebox_override("panel", sb)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", maxi(4, int(fs * 0.5)))
	p.add_child(col)
	return p


func _label(text: String, fs: int) -> Label:
	var l := Label.new()
	l.text = text
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", fs)
	return l


func _button(text: String, on_press: Callable, fs: int) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(fs * 8, fs * 2.2)   # thumb-sized
	b.add_theme_font_size_override("font_size", fs)
	b.pressed.connect(on_press)
	return b
