# Game architecture

The code shapes that hold up in a 2D game with many event systems, many
levels and a living world, and the ones that hurt. Read before scaffolding
the rules script, before adding a system, and when a file passes about 1,500
lines.

## Contents
1. Rules / Life / HUD: the split that matters most
2. Static helpers, not a presumptive autoload
3. The spine: a system registry and one reset entry point
4. Run lifecycle: snapshot and rollback
5. One tuning block
6. Content lives in data
7. Art slots
8. Drawing: shared geometry, depth sort, a documented layer stack
9. Saves
10. App lifecycle: pause and save on focus loss
11. A menu over a showcase world
12. Input a bot can drive
13. Effects and juice in code
14. Dev flags
15. Keeping code and docs honest

---

## 1. Rules / Life / HUD: the split that matters most

| Layer | Owns | Contract |
|---|---|---|
| **Rules** (`main.gd` or `sim/`) | Every number the game keeps score with; the tuning block | The only writer of game state |
| **Life** (`life.gd`) | Ambience, critters, weather, day/night, effects, sound beds | **Reads the rules, never writes them. Own RNG.** |
| **HUD** (`hud.gd`, screen space) | What the player acts on | The only state it keeps is its own animation |

`life.gd` holds all the "make it feel alive" work. Rules code that needs
randomness for looks uses a separate `vis_rng`, so the visual layer can never
shift the simulation's random rolls (or the playtest bot's results). Any
visual that draws from the global RNG (a HUD effect such as shooting stars)
moves to its own RNG too. A smoke check runs 30 s of life with weather and
asserts nothing scored changed (snippet in `testing-discipline.md` 9).

Why: with this contract, any number of "living world" rounds can't break
balance, because the bot's numbers stay identical across visual work. Put the
contract in a header comment at the top of each layer's script, and add the
invariant check on day one.

## 2. Static helpers, not a presumptive autoload

Don't scaffold a `Game` autoload up front. A speculative global (say, a
credits/upgrades economy) tends to become boilerplate nothing uses, and its
shape can cut against the design (an economy in a game with no
monetization). Use these instead:
- **`Session`** (`assets/godot/session.gd`): a static class preloaded where
  needed (`const Session = preload("res://scripts/session.gd")`) holding
  settings (`ConfigFile`), audio bus setup, the atomic save, an overridable
  `save_path`, and a `resume` flag between scenes.
- **Static `class_name` data classes:** e.g. `Zones` (static vars plus
  `apply(level)`), `Levels`, `Upgrades`, `SaveGame`, `UiTheme`. A static
  class also breaks dependency cycles: the spine holds the systems, and the
  systems need shared data such as zone boundaries, so that data lives in a
  static class both can read.
- **Flags between scenes:** instantiate the next scene, set its fields
  (`start_fresh`, the music player to hand over) before `add_child`, then swap
  `current_scene`.

## 3. The spine: a system registry and one reset entry point

One scene-root script (the spine) owns the systems. Systems read shared state
off `game` and never own it, which keeps coupling one-directional.

**The bug this prevents.** When systems are built, ticked and configured by
hand in several places, one gets missed: a system left off the configure
list carries an event in progress into a retry, and others freeze after one.
Loop over a registry instead:
```gdscript
const SYSTEMS := [          # [script, parent node, z]
	[Wind, "", 0],
	[Spawner, "world", -2],
	[Critters, "world", 2],
]
var systems: Array = []

func begin_level() -> void:          # the ONE per-unit entry point
	# ...reset counters, wipe the world...
	for s in systems:
		s.configure(level_data)

func _process(delta: float) -> void:
	for s in systems:
		s.tick(delta)
```

**System contract** (a small system such as wind is the cleanest model):
- `var game`: back-reference to the spine.
- `configure(data)`: read its block from the level data with defaults, reset
  timers, clear arrays, `queue_redraw()`. The first event comes early
  (`every * 0.4`).
- `active() -> bool`. Every query returns zero or empty when inactive, so no
  other system needs to know which level it is on.
- `tick(delta)`: called by the spine, not `_process`, for a deterministic
  order and one place that decides pause behaviour.
- Optional `set_live(...)` for another system to drive it (a storm event
  drives the wind).

Every retry, next-unit and load path goes through `begin_level()`; every
clear path calls `queue_redraw()` (`godot-gotchas.md` 5.1, 6.1).

## 4. Run lifecycle: snapshot and rollback

In the spine:
- `begin_level()`: snapshot `_level_start` (currency, owned upgrades, index),
  reset counters, wipe the world, reset weather and spawner, configure every
  system, seed the opening state, **save immediately**.
- `fail_level()` then `retry_level()` rolls back to the snapshot. The
  snapshot is deliberately NOT the save file: autosave overwrites that
  mid-level.
- `_reapply_owned()` is the single path that applies owned upgrades, used by
  retry, load and new level.
- `finish_level()`: shake and banner in the world, then the panel 0.85 s
  later on a pause-proof timer. Why: a panel that appears instantly makes
  finishing a level feel like a form submission.

## 5. One tuning block

Every number worth arguing about lives in one block at the top of the rules
script, sectioned by system, with a dated comment saying why it has that
value and who decided.
```gdscript
# --- storms -------------------------------------------------------------
const GENTLE_STORM := 0.5   # YYYY-MM-DD, user: level 1's first storm lost 5/6 bot runs at 1.0; 0/6 at 0.5
```
- Head the block "These are the numbers to fight about after playing". The
  bot measures; change one dial at a time.
- Keep **pressure apart from layout**: keep difficulty (`PRESSURE`) separate
  from placement `DATA` (e.g. in `layouts.gd`), so re-painting a level's
  layout never changes how it plays.
- Per-level values belong in the level data (section 6). Turn a per-level
  variation into one number ("stronger wind" becomes 60 -> 85 px/s).
- Group onboarding knobs: give level 1 one `beginner` block (storm interval,
  meter decay, fail grace, fail easing, spawn scale).
- Report changes by knob and file ("`GENTLE_STORM` (0.5) in main.gd").

## 6. Content lives in data

Tables of content (levels, structures, upgrades, events) live in exactly one
place, and docs are generated from it or tested against it.
- Tables kept as consts in the rules script and copied by hand into a doc
  drift apart, while `data/` stays empty. Move them to `data/*.json` (or
  `.tres`), load them, and either generate the doc table or add a check that
  the doc matches.
- One dict per level in `levels.gd` works well: identity (name, background,
  music, accent colour), geometry (zone overrides), one block per mechanic
  with `first` / `every` (with jitter) / `len`, per-wave arrays
  (`"share": [0.2, 0.3, 0.6, 0.8]`), gates (`storms_need`, `no_storms`),
  scales. Wave templates in `waves.gd`, economy in `upgrades.gd` with
  `total_cost()` for a solvability test.
- Content patterns for designing these tables: `game-loop-patterns.md`,
  `design-patterns.md`.

## 7. Art slots

Mechanics land before art. Each visual is a slot that draws a code
placeholder until its file exists, so art drops in with no code change.
```gdscript
func tex(sprite: String) -> Texture2D:      # null -> caller draws the grey-box
	return art.get(sprite)

func _draw_sprite(sprite: String, r: Rect2, flip: bool) -> void:
	var t := tex(sprite)
	if t == null:
		_rect_outlined(self, r, C_PLACEHOLDER)
	elif flip:
		draw_texture_rect(t, Rect2(r.position.x, r.position.y, -r.size.x, r.size.y), false)
	else:
		draw_texture(t, r.position)
```
- Load by file name with `ResourceLoader.list_directory` (works in exports;
  `godot-gotchas.md` 7.1). Exported `Array[Texture2D]` slots per state and
  facing on entity scenes, and `preload` consts in code, also work.
- **At content lock, convert slots to `preload` consts and delete the
  fallbacks.** A missing file then fails loudly at load instead of drawing a
  silent rectangle. Do it in the polish pass together with the unused-sprite
  sweep (`mobile-export.md` 4); it typically removes hundreds of lines.

## 8. Drawing: shared geometry, depth sort, a documented layer stack

**Draw and hit-test call the same geometry functions.** Head them with a
comment ("geometry: draw and hit-test must agree, so both call these") and
route both through them (`building_rect`, `building_foot`, `enemy_rect`).

**You hit what you see.** A tap anywhere on an object's picture selects it;
where pictures overlap, the front-most wins (same order as the depth sort).
One rect per object: a hit rect that merges several objects into one box (a
stand of trees) makes one action hit them all.

**Depth-sort by foot y, with typed items:**
```gdscript
const K_BUILDING := 0
const K_WALKER := 2
var items := []
for i in buildings.size():
	items.append([building_foot(i).y, K_BUILDING, i])
for i in walkers.size():
	items.append([walkers[i].pos.y, K_WALKER, i])
items.sort_custom(func(a, b): return a[0] < b[0])
for it in items:
	match it[1]:
		K_BUILDING: _draw_building(it[2])
		K_WALKER: _draw_walker(it[2])
```
Everything that can overlap goes in the one list. Things on a separate layer
(trees on a flora layer) draw under characters until they join it; walkers
passing between buildings join it too.

**Document the layer stack** (z-index and node order) in the bible. Two
example stacks:
- By node order, back to front: Ground (z -2), water shader rect, Back
  (decals), Trails (Linear filter), Scorch shader, Flora (z -1, sway
  material), Main (depth-sorted), Life, Night overlay, Sky (fireworks above
  the night on purpose), Fog, HUD `CanvasLayer`, Pause layer 20.
- By z-index: background -10, water -9, ground decals -5, moving platforms
  -2, surf -1, critters 2-3, birds 45, night 50, night lights 52, fx 55,
  popups 60.

## 9. Saves

`assets/godot/session.gd` implements these:
- **Atomic write:** write `save.dat.tmp`, then rename over the old file, so a
  crash mid-write never leaves a broken save.
- **A version field.** Reject or migrate on mismatch. A save format shipped
  without one can't be migrated safely later.
- **Skip derived state:** e.g. `SAVE_SKIP := ["grid", "wear_tex", "walkers",
  "critters", "particles"]` plus any `Object`: rebuilt on load or purely
  visual.
- **Load = build fresh, then overlay.** Run the normal reset, lay the saved
  numbers over it, rebuild derived state (walk grids, walkers). Read fields
  added later with `data.get(key, default)`.
- **Validate:** a missing or corrupt file returns `{}`; clamp every field on
  load.
- **Autosave only when live.** `_live()` is true only when this scene is
  `current_scene` and not the menu showcase, a test or the bot. Autosave on a
  timer (20-60 s), on unit start and purchase, and on pause/close.
- **Tests get their own path** (`Session.save_path` override), never the
  player's save (`testing-discipline.md` 2).
- **Settings in a separate file**, so wiping a save doesn't also reset the
  volume sliders.

## 10. App lifecycle: pause and save on focus loss

```gdscript
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		if _live() and not pause_ui.is_open():
			pause_ui.open()          # opening the pause screen saves
	elif what == NOTIFICATION_WM_CLOSE_REQUEST:
		if _live():
			save_game()
```
- Save as the pause opens: Android may never resume this process.
- Mute Master while paused; on resume unmute only. **Never auto-resume
  play**: dropping the player straight back into a busy moment after a phone
  call is a cheap hit.
- Android back: handle `NOTIFICATION_WM_GO_BACK_REQUEST` as pause, with
  `application/config/quit_on_go_back=false`.
- `DisplayServer.screen_set_keep_on(true)` during play.
- The pause screen runs `PROCESS_MODE_ALWAYS` with a `MOUSE_FILTER_STOP` dim
  layer.

## 11. A menu over a showcase world

The menu instantiates `main.tscn` with `showcase = true`. No rules run;
walkers, ambient animation and a slow camera drift do (sines rounded to
whole pixels), behind a gradient wash for legibility. The backdrop can pick
between a few staged scenes (a grown late-game map, an enemy stronghold at
dusk). It costs no art, shows the game in its first second, and doubles as
trailer footage. `_live()` is false in showcase, so it never saves.

## 12. Input a bot can drive

Every player action is a public function, and the input layer only calls it.
Tests and bots call the same functions.
- Joystick games: the floating joystick exposes `direction` and `active`; the
  bot sets `game.joystick.direction = dir`. That makes an overnight bot
  possible without touching game code.
- Tap games: the bot calls `use_tool()`, `harvest()`, `build()`, the same
  paths a tap takes; the smoke test's `pick()` goes through the real UI (tap
  the tool, then the target).
- **Destructive actions take two taps** ("TAP AGAIN TO ERASE"), and only when
  there is something to lose. Placement takes two taps too: a red-tinted ghost,
  then confirm.

## 13. Effects and juice in code

- **Code-drawn effects, varied every use.** An effect drawn in code can look a
  little different each time, which a sprite effect can't. Small pixel
  helpers (`_px_line`, `_px_path`, `_px_oval`, `_px_ring`) draw them on whole
  pixels.
- **Screen shake is an offset**, never the camera position: with a
  `Camera2D`, set `camera.offset` from a rounded random vector; without one,
  tween the world node, kill the previous shake tween first and always return
  to zero.
- Leave anything you will animate in code out of the generated art (empty
  chimneys without smoke, windmills without sails), then draw it
  (`art-direction.md`).

## 14. Dev flags

- Name every dev switch `DEV_*` and list it in `CLAUDE.md` under "Dev flags
  to remove before release" the moment you add it. A `DEV_* := true #
  TEMPORARY` flag and a menu label like "working title - grey-box build" are
  easy to ship by accident.
- Gate dev-only UI with `OS.is_debug_build()`. A DEV level select that lives
  only in debug builds is available exactly where playtesting happens.
- Before any release build:
  ```bash
  grep -rnE "DEV_[A-Z_]+ *:?= *true|TEMPORARY|grey-box|placeholder|working title" scripts scenes
  ```

## 15. Keeping code and docs honest

- **Split the monolith past about 1,500 lines.** A rules script heading for
  several thousand lines, with entities as untyped Dictionaries, makes
  exact-string edits and recovery after context compaction fragile. After the
  playtest gate, split by concern (simulation, economy, enemy, build,
  drawing).
- **Name the units in the bible before code exists** (run, level, round,
  wave). Otherwise an early name sticks to the wrong concept (a
  `level_index` that actually counts rounds).
- **Sweep docs and header comments at the end of every iteration.** They
  drift: `CLAUDE.md` keeps an old engine version, a palette size "locked"
  after it changed, "no art by design" after art arrived; a script header
  still says "GREY-BOX PROTOTYPE"; a header describes a goal rule that was
  removed. Rewrite superseded rules in place (`project-docs.md`).
