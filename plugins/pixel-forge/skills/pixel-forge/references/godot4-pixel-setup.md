# Godot 4 setup for pixel art on mobile

Read this before choosing a resolution, before editing `project.godot`,
before answering "why is my art blurry", and before trusting a tutorial
written for Godot 3. Target Godot 4.3+, and record the exact version in
`forge.json`.

## Contents
1. Choose the resolution and the art density
2. The settings that matter
3. `project.godot` belongs to the editor
4. Keep source art out of the import
5. More detail without changing the layout (density sets)
6. Godot 4 API changes that break old tutorials
7. Camera and zoom
8. Touch input that works everywhere
9. Layout that survives every phone
10. Fonts and UI text
11. Quick blurriness checklist

---

## 1. Choose the resolution and the art density

Pick the logical resolution by the **short side** and by **how busy the
screen is**: many small actors on screen need a higher base. Prefer a size
that divides common phone screens exactly.

| Kind of game | Viewport | Short side | Why |
|---|---|---|---|
| Painted single-screen levels, chunky look | 360x640 portrait, art at 2x (180x320 art canvas) | 360 | One painted background per level; chunky by choice |
| Busy portrait game, detailed sprites | 540x960 portrait | 540 | Room for many small actors at a finer density |
| Busy landscape map (many walkers) | 960x540 landscape | 540 | Exact 2x on 1080p phones, 4x on 4K |

For a detailed landscape game, 320x180 and 640x360 read as blocky and
1280x720 makes the pixel art disappear; 960x540 sits between. If the size
changes after grey-boxing, scale every layout number in one scripted pass
(x3 from 320x180 to 960x540) and keep outlines 1 px on purpose.

- Ask what look the user wants against something they know (a game they
  like, a reference image), then propose a size with this table.
- Changing it later is a deliberate decision for the user, not a quiet
  edit: it touches every layout number, the bible and `forge.json`.
- Two numbers, not one: the **logical canvas** (layout, what the code works
  in) and the **art density** (how many texture pixels per canvas pixel).
  Section 5 raises density without touching layout.

---

## 2. The settings that matter

### Texture filtering — the big one

`Rendering → Textures → Canvas Textures → Default Texture Filter` = **Nearest**
(`textures/canvas_textures/default_texture_filter=0`)

Default is Linear, which blurs every sprite. If a project looks soft and
nothing else explains it, this is the reason 90% of the time. Per-node
override: `CanvasItem → Texture → Filter`, for the rare element you want
smooth (e.g. a trodden-path wear layer drawn with Linear on purpose).

### Import settings

Per-texture in the Import dock, or as project-wide defaults:

- **Compress Mode: Lossless** — VRAM compression (S3TC/ETC) is built for
  photos and mangles hard-edged pixel art.
- **Mipmaps: off** — mipmaps blur at distance, and a 2D game has no distance.
- **Fix Alpha Border: off** — designed to help bilinear filtering, pointless
  with nearest.

If you change these after importing, hit **Reimport** — Godot caches.

### Stretch mode

`Display → Window → Stretch`:

| mode | Result |
|---|---|
| `canvas_items` | Scales the 2D canvas; renders at the **device** resolution, so sprites can land on fractional positions and look smooth in motion. **Best default for mobile pixel art.** |
| `viewport` | Renders at exact viewport size then scales up wholesale. Maximum chunkiness, hard pixel grid, but UI text gets chunky too and non-integer screen ratios give letterboxing. |
| `disabled` | Game renders at physical resolution. A 360x640 design becomes a postage stamp on a 1440p phone. Almost never right. |

Because `canvas_items` renders at device resolution, full-screen shaders run
per device pixel (`debugging-and-optimization.md`), and a phone has spare
pixels for denser art (section 5).

Aspect is a real choice, recorded in `forge.json`:

| aspect | Right for | Why |
|---|---|---|
| **`keep`** | Painted, fixed-layout scenes: one background image per screen, gameplay zones measured off that art | Letterboxes to the design ratio, so the art and every zone line stay exactly where they were painted. |
| **`expand`** | Tile maps, scrolling worlds, anything that can generate more world at the edges | Shows more world on taller phones instead of bars. |

**`expand` breaks a painted fixed-layout game on a real phone**: with one
painted background per level, a taller screen shows unpainted void, UI
anchored to the edges drifts off the art, and gameplay zones no longer line
up with the ground and water they were measured from. `keep` fixes all three
at once.

### Screen size is a setting, not a constant

`forge.json` holds `view_w`, `view_h`, `pixel_scale`, `aspect`, `cell` and
`godot_version`; every forge tool reads its defaults from it
(`scripts/forge_config.py`). The **art canvas** is viewport / pixel_scale:
360x640 at 2x gives a 180x320 canvas drawn doubled. In code, mirror the
numbers into one static class (e.g. `class_name Zones` with static vars),
not an autoload, and never scatter 360 and 640 through scripts.

### Pixel snapping

`Rendering → 2D → Snap`: `snap_2d_transforms_to_pixel`,
`snap_2d_vertices_to_pixel`. They stop a sprite moving at 0.5 px/frame from
shimmering. Plenty of pixel games ship without them. Treat them as the fix
for shimmer, not a requirement.

### Renderer

`gl_compatibility` for a 2D mobile game. Widest device support, lowest
overhead, and nothing in 2D pixel art needs `forward_plus`. Set both
`renderer/rendering_method` and `renderer/rendering_method.mobile`.

---

## 3. `project.godot` belongs to the editor

- **Never write comments into it.** The editor rewrites the file on every
  save, strips comments and reorders keys, and `#` lines get folded into
  keys: a `#` comment can swallow `window/stretch/aspect="keep"`. The "why"
  for each setting goes in `forge.json` notes or the bible.
- **Default-valued keys disappear** when the editor saves (`aspect="keep"`,
  the default bus layout). Absence is not a bug. Check effective values in
  the smoke test with `ProjectSettings.get_setting()`.
- **Pin the engine version.** Record `godot_version` in `forge.json`; CI,
  export templates and the README read it. A CI running an older Godot than
  the editor flips `config/features` between them and can fail to read
  presets the editor wrote.
- Expect harmless churn: an Android export adds
  `textures/vram_compression/import_etc2_astc=true`; the editor reorders
  keys. Leave line-ending-only diffs out of commits (`delivery.md`).

---

## 4. Keep source art out of the import

Godot imports every image under the project folder. Put an empty
`.gdignore` in `raw_art/` and `docs/screens/` (or all of `docs/`) at
scaffold time. Skip it and every raw generation and screenshot gets
imported, and `.godot/` can reach gigabytes. Never `.gdignore` `tools/` (the
test and capture scripts run from there); keep it out of builds with the
export filter (`mobile-export.md`).

---

## 5. More detail without changing the layout (density sets)

A phone renders a 960x540 `canvas_items` game at 1920x1080, so each game
pixel is 2x2 screen pixels. Feed it 2x textures drawn at 1x size and the
extra detail shows; the layout, hit boxes and every number stay the same.
Re-cut the world sprites at 2x from the raw art, locked to the same palette
(a full world set is typically a couple of MB). Offer it to the user against
the alternative, a 4x painted set without a palette lock; the palette-locked
2x set stays consistent with the base art.

```gdscript
const HD_MIN_SCALE := 1.5
var art := {}      # what draws
var art_1x := {}   # base set
var art_hd := {}   # detailed set, same keys

func _load_art() -> void:
	for f in ResourceLoader.list_directory("res://art/sprites/"):
		if f.ends_with(".png"):
			art[f.get_basename()] = load("res://art/sprites/" + f)
	art_1x = art.duplicate()
	for f in ResourceLoader.list_directory("res://art/sprites_hd/"):
		var key: String = f.get_basename()
		if f.ends_with(".png") and art_1x.has(key):
			var t := ImageTexture.create_from_image(load("res://art/sprites_hd/" + f).get_image())
			t.set_size_override(Vector2i(art_1x[key].get_size()))   # draws at 1x size
			art_hd[key] = t

func render_scale() -> float:   # screen pixels per game pixel
	var vp := get_viewport()
	return float(vp.size.y) / maxf(1.0, vp.get_visible_rect().size.y)

func _apply_density() -> void:
	var hd := render_scale() >= HD_MIN_SCALE and not art_hd.is_empty()
	for key in art_hd:
		art[key] = art_hd[key] if hd else art_1x[key]

func tex1x(key: String) -> Texture2D:   # for code that reads a sprite's own pixels
	return art_1x.get(key, art.get(key))
```
- Call `_apply_density()` at start and on `get_viewport().size_changed`.
- `draw_texture_rect_region` uses override units.
- Code that reads pixels (plot outlines, snow on roofs) uses `tex1x()`.
- A desktop window at 1x keeps the base set: 2x art squeezed into 1x pixels
  looks worse, not better.
- Flames, icons, effects, the HUD and the title can stay at base density:
  the chunky pixels are part of the look.
- Costs: about 4x sprite memory; code-drawn visuals (often hundreds of them)
  stay chunky and need a gradual redraw.
- Build the HD set from the same art manifest as the base set
  (`scripts/art_build.py`), so the two can't drift.

---

## 6. Godot 4 API changes that break old tutorials

Most pixel-art Godot content online is Godot 3. These are the ones that bite:

| Godot 3 | Godot 4 |
|---|---|
| `TileMap` with layers | `TileMapLayer` node, one per layer (4.3+). `TileMap` is deprecated. |
| `Camera2D.smoothing_enabled` | `position_smoothing_enabled` / `position_smoothing_speed` |
| `Camera2D.current` | `enabled` (and `make_current()`) |
| `yield(get_tree().create_timer(1), "timeout")` | `await get_tree().create_timer(1.0).timeout` |
| `connect("sig", self, "_on_sig")` | `sig.connect(_on_sig)` — typed signal objects |
| `KinematicBody2D` | `CharacterBody2D`, and `move_and_slide()` takes no arguments; set `velocity` first |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `File.new()` | `FileAccess.open(path, FileAccess.READ)` |
| `Directory.new()` | `DirAccess.open(path)` — but use `ResourceLoader.list_directory` to list imported art in an export |
| `export var x` | `@export var x` |
| `onready var x` | `@onready var x` |
| `Tween` node | `create_tween()` on any Node, returns a `Tween` |
| `instance()` | `instantiate()` |

Godot 4.4+ also writes a `.uid` file beside every script and shader: commit
them, and delete them with their script (`godot-gotchas.md` 1.4).

---

## 7. Camera and zoom

```gdscript
extends Camera2D

@export var target: Node2D
@export var lerp_speed := 5.0

func _ready() -> void:
	position_smoothing_enabled = true
	position_smoothing_speed = lerp_speed
	# clamp to level bounds so the camera never shows past the art
	limit_left = 0
	limit_top = 0

func _process(delta: float) -> void:
	if target:
		global_position = global_position.lerp(target.global_position, delta * lerp_speed)
```

- Camera smoothing and pixel snapping fight slightly. If the result
  shimmers, turn smoothing off or round: `global_position =
  global_position.round()`. A menu camera drifting on slow sines rounds to
  whole pixels the same way.
- **Only zoom steps of 1.5x, 2x and 0.5x stay sharp**; anything else
  resamples pixels unevenly. A screenshot harness can use 2x close-ups.
- Screen shake goes on `camera.offset` (or a world-node offset), never on
  the camera position (`architecture.md`).

---

## 8. Touch input that works everywhere

Mouse handlers fire on touch with `input_devices/pointing/emulate_mouse_from_touch`
(on by default), so you can develop on desktop and ship to phone without
branching. A tap-driven game can use mouse events only. Touch-only controls
(a floating joystick) need the reverse,
`input_devices/pointing/emulate_touch_from_mouse=true`, to be testable with a
desktop mouse.

```gdscript
func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch and event.pressed:
		_tap_at(event.position)
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		_tap_at(event.position)
```

- **Tap vs drag:** if dragging scrolls and tapping acts, a press only counts
  as a tap when it moved less than a few pixels (e.g. `TAP_SLOP` 4 px), so
  scrolling never triggers an action.
- For tappable objects either use `Area2D` with `input_pickable = true`
  (Godot does the hit test under a scaled canvas), or hit-test with the same
  geometry functions the draw code uses (`architecture.md`).
- Tap targets at least 48x48 **screen** pixels. At a 360-wide viewport on a
  1080-wide phone that's a 16x16 sprite. Anything under 12 design pixels will
  frustrate people. The tap rect covers the whole sprite, not its footprint:
  a rect that covers only a building's footprint makes tapping its roof do
  nothing.

---

## 9. Layout that survives every phone

- Anchor UI to screen edges (`Control` anchor presets), never to absolute
  coordinates.
- Notches: query `DisplayServer.get_display_safe_area()` — but with `keep`,
  **only count the part of the inset that reaches past the letterbox bar.**
  On a tall phone the black bar already clears the notch; adding the full
  inset pushes top buttons down for nothing. Apply insets to the individual
  elements near the edge, not the whole layer:
  ```gdscript
  static func inset_in_game(inset_px: float, win: Vector2, vis: Vector2) -> float:
      var scale := minf(win.x / vis.x, win.y / vis.y)
      var bar := (win.y - vis.y * scale) * 0.5      # letterbox bar, screen px
      return maxf(0.0, inset_px - bar) / scale      # game px actually covered
  ```
- Test at 9:16 and 21:9 (`assets/godot/device_preview.gd` renders any device
  size). With `expand`, make sure nothing important lives at the edge and no
  unpainted background shows.

---

## 10. Fonts and UI text

Two approaches both work; pick one per project and write it in the bible.

| Option | How | When |
|---|---|---|
| **Pixel text** | A bitmap font, or a TTF imported with **Antialiasing: None**, **Hinting: None**, **MSDF: off**, at integer multiples of its design size | Text drawn in the world at art density, or a game where every element is chunky |
| **Crisp full-resolution UI** | HUD and menus drawn at full resolution in a smooth bold font, e.g. a bold `FontVariation` over `ThemeDB.fallback_font` (no extra font file), 5 px label outlines, plus one TTF title font shipped with its OFL licence | Small text on a phone, lots of numbers; text stays sharp against chunky art |

Don't mix the two inside one panel. A smooth font next to hard pixels in the
same element reads as a bug; a consistently crisp HUD over a chunky world
reads as a choice. Ship every font's licence beside it.

---

## 11. Quick blurriness checklist

1. Default texture filter set to Nearest?
2. Texture import compress mode Lossless, mipmaps off, and **reimported**?
3. Stretch mode `canvas_items` (not `disabled`)?
4. Is any node scaled by a non-integer factor? (`Sprite2D.scale = 1.5` will
   never look right; use 1, 2, 3.) Camera zoom other than 0.5x, 1.5x or 2x?
5. Is the sprite PNG actually small, or is it a 1024 px image scaled down in
   the engine? Run it through `scripts/pixelize.py` (pass an explicit
   `--target`: it is the **longest** side).
6. 2x density art in a 1x window? It looks worse; check `render_scale()`.
