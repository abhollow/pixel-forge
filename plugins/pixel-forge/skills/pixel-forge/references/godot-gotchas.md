# Godot 4 gotchas (learned the hard way)

Each of these costs at least one round when you hit it (Godot 4.3 to 4.7).
Several only show up on a phone, in a bot log, or in a windowed render. Read the matching section
before writing shaders, physics, drawing code, saves or audio. Format: rule,
why, fix.

## Contents
1. Project file, import and version control
   1.1 Never comment `project.godot` · 1.2 Run `--import` after new classes and
   new art · 1.3 `.gdignore` source and review folders · 1.4 Orphan `.uid`
   files · 1.5 Cache and version control
2. Physics and scene resources
   2.1 Defer add/free/toggle in collision callbacks · 2.2 Shared sub-resource
   shapes · 2.3 Queued-for-deletion nodes still show up · 2.4 Gameplay ranges
   are not hitboxes
3. GDScript
   3.1 Typed parameters and freed objects · 3.2 Type inference traps ·
   3.3 `match` needs constants · 3.4 Multi-line lambdas · 3.5 Parenthesise
   range expressions · 3.6 Name clashes and shadowing · 3.7 Comparing Variants
   · 3.8 Floating-point edges
4. Shaders
   4.1 Never raw elapsed time · 4.2 Wrap at TAU x N, integer multipliers ·
   4.3 `COLOR` already includes the texture · 4.4 `return` in `fragment()` ·
   4.5 `highp` for world coordinates · 4.6 Unwritten uniforms read as null
5. Drawing and motion
   5.1 `queue_redraw()` on every reset path · 5.2 Negative-width
   `draw_texture_rect` · 5.3 Facing flicker on grid paths · 5.4 AStarGrid
   doors inside solid cells · 5.5 Hidden is not idle
6. Lifecycle, time and pausing
   6.1 One per-unit reset entry point · 6.2 Pausing · 6.3 Pause-proof timers ·
   6.4 Frame caps, time scale and bots
7. Loading art
   7.1 `ResourceLoader.list_directory` in exports · 7.2 Density sets with
   `set_size_override`
8. Audio
9. UI and layout

---

## 1. Project file, import and version control

### 1.1 Never put comments in `project.godot`
The editor rewrites the file on save: it strips comments, reorders keys and
**drops keys that hold the default value**. Godot config files only accept
`;` comments, and `#` lines get folded into keys. A `#` comment in
`[display]` can become a garbage key that swallows the next setting (such as
`window/stretch/aspect="keep"`); the editor also reorders keys like
`run/max_fps` on its own, and opening a project in a newer editor strips
comments and default-valued keys.
- Put the rationale in `forge.json` or the bible, never in `project.godot`.
- A missing default-valued key (`aspect="keep"`, the default bus layout) is
  not a bug. Check the effective value instead, in the smoke test:
  ```gdscript
  check("stretch aspect is keep",
      ProjectSettings.get_setting("display/window/stretch/aspect") == "keep")
  ```
- Record the engine version in `forge.json` (`godot_version`) and pin CI to it
  (`delivery.md`).

### 1.2 Run `--import` after a new `class_name` and after new art
A new `class_name` is unknown ("Could not find type Pickup") until the global
class cache is refreshed. New sprites don't draw until they're imported:
buildings, animation frames and critters from a fresh art build all fail to
draw until an import.
```bash
timeout 300 "$G" --headless --path . --import
```
End every art build with it, run it after adding any `class_name`, and run
it first in CI.

### 1.3 `.gdignore` the source-art and review folders
Godot imports every image under the project unless a folder has a
`.gdignore`. Without one, every raw generation and review screenshot gets an
`.import` file and a cached copy, and `.godot/` can grow past a gigabyte;
with one, hundreds of MB of originals stay out of the import and the APK.
- Put an empty `.gdignore` in `raw_art/` and `docs/screens/` (or all of
  `docs/`).
- Never in `tools/`: the smoke test and capture scripts run from
  `res://tools/`. Keep `tools/` out of builds with the export filter
  (`mobile-export.md`).

### 1.4 Delete the `.uid` with the script
Godot 4.4+ writes a `.uid` next to every script and shader. Deleting the
script leaves an orphan (`tools/_dump_map.gd.uid` with no script), which is
easy to commit by accident. When you delete a throwaway script, delete its
`.uid` in the same step, and check `git status` for orphans before
committing.

### 1.5 Cache and version control
- **Never commit `.godot/`.** A stale copy after pulling is the usual cause
  of "could not find type" errors. Delete it and re-import. If sprites show
  as coloured rectangles, same fix.
- **Commit `*.import` and `*.uid`** (Godot's own recommendation). If a
  project ignores `*.import`, every import-dependent option (loop flags,
  filter) must be set in code, e.g. `stream.loop` set in `audio.gd`.
- `export_presets.cfg` is safe to commit in Godot 4: credentials live in
  `.godot/export_credentials.cfg`. Grep it before committing anyway.
- Raw art: see the policy in `delivery.md` (commit when small, ledger of
  creation IDs when large).

---

## 2. Physics and scene resources

### 2.1 Defer anything that adds, frees or toggles physics objects from a collision callback
Signals like `body_entered` fire while the physics server is flushing.
Adding an `Area2D`, freeing a body, or flipping `disabled` there fails with
"Can't change this state while flushing queries", and added shapes come out
dead. Typical case: a hit (`body_entered` -> `get_hit()` ->
`spawner.scatter()`) that spawns dropped pickups inside the flush, giving
over a hundred errors in one bot run and pickups with dead collision.
```gdscript
spawner.scatter.call_deferred(lost_units, at)     # add
shape.set_deferred("disabled", true)              # toggle
body.queue_free()                                 # free
```
In tests, step out of the physics frame (`await process_frame`) before
freeing or disabling.

### 2.2 Sub-resource shapes are shared by every instance
A `RectangleShape2D` declared as a sub-resource in a `.tscn` is one object
for every instance unless it is local to the scene. A script that resizes it
resizes all of them: every pickup takes the size of whichever refreshed last
(large piles shrink to 16x16 and progress resets), and NPC hitboxes flip
between sizes. Balance may have been tuned with the bug in place.
```
[sub_resource type="RectangleShape2D" id="RectangleShape2D_1"]
resource_local_to_scene = true
```
or `shape = shape.duplicate()` in `_ready()`. Grep `.tscn` files for shapes
that scripts mutate. Add a check: resize one instance, assert another is
unchanged. Re-check balance after the fix.

### 2.3 Nodes queued for deletion are still found by searches
`queue_free()` doesn't remove the node until the end of the frame. Two piles
can merge into each other on the same tick and both vanish; a pile that
merged away can still be collected the same frame.
- Queries over world children skip `is_queued_for_deletion()`.
- After a node frees itself, `return` from the function immediately.

### 2.4 Derive gameplay ranges from named constants, not collision shapes
A vehicle's pickup reach computed from its hitbox means shrinking the hitbox
(32 -> 28, to cut unfair hits) also shrinks the reach. Keep hitbox, art size
and reach as separate constants (`VEHICLE_HIT_*`, reach footprint).

---

## 3. GDScript

### 3.1 A typed parameter rejects a freed object before your check runs
`func _alive(p: Pickup)` raises "Invalid type in function... previously
freed" on the call, before `is_instance_valid()` inside it runs, and the
error aborts the calling function. Typical symptom: a helper creature
chasing a pickup freezes mid-air whenever something else collects its target
first, logging tens of thousands of errors while a paid upgrade silently
does nothing.
```gdscript
func _alive(p) -> bool:          # untyped (or Object) on purpose
	return is_instance_valid(p) and not p.is_queued_for_deletion()
```
Liveness checks take untyped or `Object` parameters. Grep every bot and test
log for `SCRIPT ERROR` (`testing-discipline.md`).

### 3.2 Type inference traps
- **`:=` can't infer through an untyped variable.** `var i := x if c else
  randi() % game.spawns.size()` fails when `game` is untyped, and the error
  can surface in a *different* script ("Nonexistent function 'new' in base
  'GDScript'") or as a flood of `Nil` errors. Write `var i: int = ...`.
- `var c := img.get_pixel(x, y)` in a throwaway tool gives "Cannot infer the
  type". Write `var c: Color = ...`.

### 3.3 `match` needs constant patterns
`match kind: main.Ability.DASH:` through an untyped reference fails. Use
`if/elif` when the pattern isn't a literal or a local constant.

### 3.4 Multi-line lambdas can fail to parse
A multi-line lambda can cause a parse error. Assign it to a local
`Callable` first, or use a named function. One-line lambdas
(`func(p): return p.playing`) are fine.

### 3.5 Parenthesise expressions used as a range
`for k in 2 if c else 1:` doesn't parse. Write `for k in (2 if c else 1):`.

### 3.6 Name clashes and shadowing
- A variable and a function can't share a name in one class (`var
  pickup_reach` + `func pickup_reach()`). Constants clash the same way
  (`BUILD_TIME`; rename one, e.g. `RAISE_TIME`).
- A local shadowing a parameter (`top`) or a loop variable shadowing a member
  (`c` vs a member `c`) compiles with only a warning. Keep warnings visible
  and read them.
- Long functions reuse names by accident. Duplicate locals (`p0`, `up`, `wy`)
  in a several-thousand-line smoke test are parse errors. Give each section
  its own prefix (`wl_`, `bt_`, `ep_`). After a regex rename, check it didn't
  change text inside strings.

### 3.7 Comparing values that may be different types
`_target == p` when `_target` may hold a `Vector2` or a Node raises Variant
comparison errors. Use `is_same(a, b)`.

### 3.8 Floating-point edges
Pushing something to *exactly* a boundary leaves it a hair inside half the
time. Push a fraction past (`edge + 0.03`, `half_width - 0.5`).

---

## 4. Shaders

### 4.1 Never pass raw elapsed time
A shader fed `uniform float t` with elapsed seconds freezes **on phones only**
a few minutes in: mobile GPUs run fragments at half precision, so as `t`
grows its smallest step grows (4 updates a second after five minutes, 2 after
ten). `sin(t * speed)` with a large `t` also jumps phase whenever `speed`
changes. Accumulate a phase on the CPU and wrap it:
```gdscript
phase = fposmod(phase + delta * speed, TAU)
material.set_shader_parameter("phase", phase)
```
Every shader in `assets/shaders/` takes a `phase` uniform for this reason.

### 4.2 Wrap at TAU x N and use only whole-number multipliers
A shader that needs several speeds uses `phase * 2.0`, `phase * 3.0` and so
on. Those only stay seamless across the wrap if the wrap is a multiple of TAU
and every multiplier is an integer. `assets/shaders/water.gdshader` gets
`fposmod(elapsed * 0.6, TAU * 10.0)` and uses `phase`, `phase * 2.0`,
`phase * 3.0`; sway wraps at TAU.

### 4.3 In a canvas shader, `COLOR` already is texture x modulate
At the start of `fragment()`, `COLOR` holds the sampled texture multiplied by
the node's modulate. `texture(TEXTURE, UV) * COLOR` squares every channel: a
tint shader written that way darkens everything (mid-grey 808080 becomes
404040) and turns skin deep red. The bug spreads by copy-paste from one tint
shader to the next, so grep every shader for it.
```glsl
void fragment() {
	vec4 c = COLOR;          // texture * modulate, already
	// ...recolour c...
	COLOR = c;
}
```
If you resample `TEXTURE` (sway, water), multiply by the modulate passed
through a varying from `vertex()`, never by `COLOR`. Never write
`texture(TEXTURE, UV) * COLOR`.

### 4.4 `return` inside `fragment()` is a compile error the headless test misses
An optimisation early-out can make a night shader fail to compile, and the
level renders solid white while the headless smoke test passes. Only a
windowed render's log shows `SHADER ERROR: Using 'return' in the 'fragment'
processor function is incorrect`.
```glsl
if (top > 0.0) {            // gate the work instead of returning
	for (int i = 0; i < 24; i++) { ... }
}
```
Every shader edit gets a windowed render, and its log is grepped for
`SHADER ERROR` (`debugging-and-optimization.md`).

### 4.5 Use `highp` for world-space maths on big maps
Half precision has a 10-bit mantissa: past 2,048 its step is 2 units, so a
shader working in world pixels on a map taller than that (world y reaching
2,160, say) can no longer address every pixel.
```glsl
highp vec2 p = floor(UV * rect_size / 3.0) * 3.0;
```

### 4.6 A uniform you never set reads back as `null`
`material.get_shader_parameter("x")` on an unset uniform returns `null`, and
`float(null)` is a hard error (a screen-grade strength read back this way is
the usual case). Mirror uniform values in script variables and read those.

Full-screen shader cost is a performance topic: `debugging-and-optimization.md`.

---

## 5. Drawing and motion

### 5.1 Every clear, reset and deactivate path calls `queue_redraw()`
`_draw()` output stays on screen until the next redraw. A `tick()` that
returns early while inactive never queues one, so clearing the arrays leaves
the last frame frozen: birds frozen mid-air after a failed level, and a
review then finds other systems frozen the same way.
```gdscript
func _clear() -> void:
	birds.clear()
	queue_redraw()
```
Add a smoke check: after a retry, the system draws nothing.

### 5.2 A negative width in `draw_texture_rect` mirrors in place
The rect keeps its position; it does not extend leftward. Code that assumes
it does offsets every flipped draw (walkers, enemies, animals, clouds) by its
own width.
```gdscript
draw_texture_rect(t, Rect2(r.position.x, r.position.y, -r.size.x, r.size.y), false)
```
Wrap it in one `_draw_sprite(sprite, rect, flip)` helper so the rule lives in
one place.

### 5.3 Facing flickers on grid paths
Grid paths zigzag, so "face the way you're moving" flips the sprite on every
vertical leg; a probe can count hundreds of flips that drop to a handful
after the fix.
```gdscript
if dx != 0.0:
	w.left = dx < 0.0       # hold facing until there is sideways movement
```
Measure flips with a probe before and after. (A player-steered character can
flip only past a deadzone, e.g. 0.25.)

### 5.4 An AStarGrid2D door inside a solid cell gives an empty path
An empty path makes walkers fall back to a straight line **through** the
building. Put doors outside the footprint
(`foot.end.y + GRID_CELL * 2 + 3`), and add a smoke check that asserts zero
ticks spent inside buildings. Never let an empty path silently become a
straight line.

### 5.5 Hidden is not idle
A hidden node still runs `_process()` and `_draw()` work you wrote: a
tutorial's ring helper keeps redrawing invisible rings all session, and a
`PanelContainer.new()` created only to borrow its stylebox leaks.
- `if not is_visible_in_tree(): return` at the top of helpers.
- Never instantiate a Control just to read its theme; build the stylebox in
  a static helper (`UiTheme.panel_box()`).
- Set theme overrides on change, not every frame
  (`debugging-and-optimization.md`).

---

## 6. Lifecycle, time and pausing

### 6.1 One per-unit reset entry point that every system hooks
Systems configured only in `apply_level_data()`, when `retry_level()` and
`next_level()` call only `begin_level()`, carry their state into the retry:
an event in progress keeps running and costs the player. Configure and reset
every system from the one function that starts a unit (level, round, wave),
ideally by looping a registry. Pattern in `architecture.md`.

### 6.2 Pausing
`get_tree().paused = true` freezes `_process`, tweens and pausable audio. UI
that must work during it (panels, tutorial, intro cards) lives on a
`CanvasLayer` with `process_mode = PROCESS_MODE_ALWAYS`. Pausing behind an
overlay is also the simplest way to stage a tutorial: spawn what the steps
point at, and it stays where you put it.

### 6.3 Pause-proof timers and tweens
- `get_tree().create_timer(0.85, true, false, true)`: process while paused,
  not physics, **ignore time scale**. The end-of-level panel is the typical
  case. The last argument matters when a bot runs at `time_scale` 4.
- Fades that must run while paused:
  `tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)`. A crossfade frozen by
  the pause panel leaves the first song of a level barely audible.

### 6.4 Frame caps, time scale and bots
- `run/max_fps` applies to headless runs too. After adding `run/max_fps=60`
  (battery), a smoke check that waits a fixed number of frames sits right on
  the edge, and a time-scaled bot's clear rate on a tight level can drop from
  all runs to none.
- At `Engine.time_scale = 4` with a 60 fps cap, four physics steps run in
  every frame the bot steers on, so it wedges on corners. Bots and benchmarks
  pass `--max-fps 0`.
- A time-scaled bot keeps the physics step at 1/60 of a game second:
  ```gdscript
  Engine.time_scale = ts
  Engine.physics_ticks_per_second = 60 * ts
  Engine.max_physics_steps_per_frame = 64
  ```
- Tests wait on conditions or `sim(seconds)`, never frame counts
  (`testing-discipline.md`).

---

## 7. Loading art

### 7.1 Use `ResourceLoader.list_directory` to find art in an exported build
In an export the PNGs are remapped, so a `DirAccess` scan finds nothing
useful. Load every sprite by file name instead, which also makes art slots
data-driven:
```gdscript
for f in ResourceLoader.list_directory("res://art/sprites/"):
	if f.ends_with(".png"):
		art[f.get_basename()] = load("res://art/sprites/" + f)
```

### 7.2 Density sets: `ImageTexture.set_size_override`
A 2x sprite drawn at its 1x size: create an `ImageTexture` from the 2x image
and `set_size_override(Vector2i(art_1x[key].get_size()))`. Region draws use
override units. Code that reads a sprite's own pixels uses the 1x texture.
Full recipe in `godot4-pixel-setup.md`.

---

## 8. Audio

- **An AudioStreamPlayer stops when it leaves the tree.** Handing music from
  one scene to another with `remove_child` / `add_child` restarts it silently
  unless you record `get_playback_position()` first and `play(pos)` after.
- **A player under a paused tree pauses** unless `process_mode =
  PROCESS_MODE_ALWAYS`. Music behind a pause panel needs it.
- **Ducking must be undone on every exit path.** A level reset that clears a
  storm event without restoring the duck leaves every level that starts
  mid-duck 10 dB quiet.
- **Test audibility, not flags.** A crossfade that `stop()`s its outgoing
  player resets flags; check `.playing` on every player and the bus level.
- **Set loop flags in code.** Loop settings in `.import` files are easy to
  lose. WAV: `s.loop_mode = AudioStreamWAV.LOOP_FORWARD` for beds,
  `LOOP_DISABLED` for playlist tracks. For OGG/MP3: `stream.loop = true` for
  beds and `false` for playlist tracks, or the track never ends and the
  playlist stalls.

Buses, voice pools and playlists: `audio.md`.

## 9. UI and layout

An unwrapped `Label` is as wide as its whole text, and containers grow to
fit: one long upgrade description can make a shop panel 448 px wide on a
360 px screen. For any text that can be long:
```gdscript
label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
label.custom_minimum_size = Vector2(1, 0)
button.clip_text = true
button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)  # pin to the panel
```
Test it: open the panel in its wordiest state and assert no descendant's
`get_global_rect().end.x` exceeds the screen width.

- Stretch aspect `keep` for painted fixed scenes, `expand` for tiles and
  scrolling (`godot4-pixel-setup.md`). `expand` breaks a painted game.
- Safe-area insets must be reduced by the letterbox bar (formula in
  `godot4-pixel-setup.md`), or UI gets pushed in for nothing.
