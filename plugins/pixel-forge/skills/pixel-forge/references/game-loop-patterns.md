# Gameplay patterns: the gather → currency → upgrade loop

Working Godot 4 GDScript for the genre most small pixel games land in:
collect a resource, convert it to currency, spend currency on tools that
collect faster. Adapt rather than copy blindly.

This is illustrative code for one genre. It calls a `Game` singleton for
brevity; in a real project prefer the patterns in `architecture.md` (a static
`Session` class for saves and settings, a scene-root spine that owns the
systems). Two economy shapes:

- **Levelled upgrades** (below): one row per upgrade, cost grows by `cost_mult`.
- **Tiered one-shot unlocks**: each upgrade is bought once, has a `tier` and
  `needs` prerequisites, the shop shows one tier per unit, and one upgrade is
  retained per finished level. Test solvability with a
  `total_cost()` check against what a unit can earn.

**The rule that matters most: data, not duplication.** Adding a new upgrade
or a new collectible should mean adding a dictionary entry, not duplicating
a scene. Every hour spent on this up front pays back tenfold.

---

## 1. Upgrades as data

`data/upgrades.gd`:

```gdscript
extends RefCounted
class_name Upgrades

const DATA := {
	"pickaxe": {
		"name": "Pickaxe",
		"desc": "Gather more per swing",
		"base_cost": 25,
		"cost_mult": 1.6,
		"max_level": 8,
		"effect": "gather_amount",
		"per_level": 1.0,
	},
	"boots": {
		"name": "Boots",
		"desc": "Move faster",
		"base_cost": 40,
		"cost_mult": 1.8,
		"max_level": 5,
		"effect": "move_speed",
		"per_level": 12.0,
	},
}

static func cost(id: String, level: int) -> int:
	var d: Dictionary = DATA[id]
	return int(d.base_cost * pow(d.cost_mult, level))

static func value(id: String, level: int) -> float:
	return DATA[id].per_level * level
```

Now the shop UI is one scene that iterates `Upgrades.DATA`, and adding
content is a five-line edit. `cost_mult` between 1.5 and 1.9 gives the
familiar accelerating-cost curve; below 1.3 the player outruns your content.

## 2. A collectible

```gdscript
extends Area2D
class_name Collectible

@export var value: int = 1
@export var bob_height: float = 2.0

var _base_y: float
var _collected := false

func _ready() -> void:
	_base_y = position.y
	input_pickable = true
	input_event.connect(_on_input_event)

func _process(_delta: float) -> void:
	# programmatic motion instead of generated animation frames
	position.y = _base_y + sin(Time.get_ticks_msec() / 400.0) * bob_height

func _on_input_event(_vp: Node, event: InputEvent, _idx: int) -> void:
	if event is InputEventScreenTouch and event.pressed:
		collect()
	elif event is InputEventMouseButton and event.pressed:
		collect()

func collect() -> void:
	if _collected:
		return
	_collected = true
	set_process(false)
	Game.add_credits(value)
	var tw := create_tween().set_parallel()
	tw.tween_property(self, "scale", Vector2(1.4, 1.4), 0.12)
	tw.tween_property(self, "modulate:a", 0.0, 0.12)
	await tw.finished
	queue_free()
```

The tween on collect is doing real work. A pickup that just vanishes feels
broken; 120ms of scale-and-fade is the difference between a prototype and a
game, and costs nothing.

## 3. Spawning a field of them

```gdscript
extends Node2D

@export var collectible_scene: PackedScene
@export var count: int = 20
@export var area: Rect2 = Rect2(16, 120, 328, 420)
@export var min_gap: float = 20.0

func _ready() -> void:
	randomize()
	_spawn_field()

func _spawn_field() -> void:
	var placed: Array[Vector2] = []
	var attempts := 0
	while placed.size() < count and attempts < count * 30:
		attempts += 1
		var p := Vector2(
			randf_range(area.position.x, area.end.x),
			randf_range(area.position.y, area.end.y)
		).round()  # keep spawns on whole pixels
		var ok := true
		for q in placed:
			if p.distance_to(q) < min_gap:
				ok = false
				break
		if not ok:
			continue
		placed.append(p)
		var node := collectible_scene.instantiate()
		node.position = p
		add_child(node)
```

Rejection sampling with a minimum gap looks far better than pure random,
which clumps. `.round()` keeps everything on the pixel grid.

## 4. Shop UI driven by the data

```gdscript
extends VBoxContainer

@export var row_scene: PackedScene

func _ready() -> void:
	for id in Upgrades.DATA:
		var row := row_scene.instantiate()
		add_child(row)
		row.setup(id)
		row.purchased.connect(_refresh)

func _refresh() -> void:
	for row in get_children():
		if row.has_method("refresh"):
			row.refresh()
```

And a row:

```gdscript
extends HBoxContainer
signal purchased

var _id: String

@onready var _label: Label = $Label
@onready var _button: Button = $Button

func setup(id: String) -> void:
	_id = id
	refresh()
	_button.pressed.connect(_on_pressed)

func refresh() -> void:
	var lvl := Game.upgrade_level(_id)
	var d: Dictionary = Upgrades.DATA[_id]
	_label.text = "%s  Lv%d" % [d.name, lvl]
	if lvl >= d.max_level:
		_button.text = "MAX"
		_button.disabled = true
	else:
		var c := Upgrades.cost(_id, lvl)
		_button.text = str(c)
		_button.disabled = Game.credits < c

func _on_pressed() -> void:
	var lvl := Game.upgrade_level(_id)
	if Game.spend_credits(Upgrades.cost(_id, lvl)):
		Game.upgrades[_id] = lvl + 1
		Game.upgrade_purchased.emit(_id, lvl + 1)
		Game.save_game()
		purchased.emit()
```

## 5. Applying upgrades

Read them where they're used rather than caching in a dozen places:

```gdscript
func gather_amount() -> float:
	return 1.0 + Upgrades.value("pickaxe", Game.upgrade_level("pickaxe"))

func move_speed() -> float:
	return 60.0 + Upgrades.value("boots", Game.upgrade_level("boots"))
```

## 6. Saving

The scaffolded `Game` autoload already has `save_game()` / `load_game()`
using `FileAccess` and `JSON`. Notes:

- Save on meaningful events (purchase, level end) and on
  `NOTIFICATION_APPLICATION_PAUSED` — mobile apps get killed without warning.
- Keep a `"version"` field from day one. Migrating a save format you didn't
  version is miserable.
- `user://` is the only writable path; `res://` is read-only in an export.

```gdscript
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_PAUSED \
			or what == NOTIFICATION_WM_CLOSE_REQUEST:
		Game.save_game()
```

## 7. Pacing a level

Working backwards from a target session length:

- Decide the unit length first. Mobile sessions run ~5 min
  (`design-patterns.md` §1); expect to try a few lengths before one feels
  right, and give longer units (~10 min) pause and save. Then count the
  meaningful decisions in it (roughly one purchase every 60–90 seconds).
- Set `base_cost` so the first upgrade lands about 45 seconds in. An early
  win teaches the loop.
- `cost_mult` around 1.6–1.7 keeps later purchases feeling earned without
  a wall.
- Resource density should fall slightly as the level goes on, so upgrades
  feel like they're keeping pace rather than trivializing things.
- For a relaxed pace specifically: no fail state, no timer, and let the
  player over-collect. Pressure comes from scarcity; remove scarcity and
  the game becomes the calm thing you wanted.

Playtest with the numbers exposed on screen (`print` or a debug Label)
before tuning blind.
