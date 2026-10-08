# Debugging and optimization

How to find what is really wrong, see it, and make the game faster without
changing how it plays. Engine-specific traps are in `godot-gotchas.md`; test
habits in `testing-discipline.md`.

## Contents
1. Reproduce and measure before fixing
2. See it: windowed capture
3. Motion bugs: watch it run
4. Regressions: suspect the harness, bisect in a worktree
5. The end-game optimization pass
6. Mobile 2D performance checklist
7. Fixes that change balance are offered, not imposed

---

## 1. Reproduce and measure before fixing

A user report names a symptom, often in the wrong place. Measure first, then
change one thing. Typical reports and what measuring tends to find:

| Report | What measuring found |
|---|---|
| Quiet music on one level | A ducking bug on every level: a reset cleared the event without restoring the duck |
| A level that "won't end" | A hidden second end condition |
| Walkers flicker | Facing flipped on every vertical grid leg: a probe counted hundreds of flips, a handful after the fix |
| A repeat layering report after the first fix | Not the object reported: travellers drawn above every building, walking straight into it |
| "The meter should go up on pickup" | Already true; two other rules undermined it, and those were the fix |
| Too many collisions on one level | Bot hit positions: about a third of hits in streets narrower than the vehicle, so collisions were turned off in that area |

- **Probe, don't guess.** A probe is a throwaway script that runs the real
  game and logs the quantity in question: facing flips, hits with
  positions, event phases every 2 s. A probe can `extends
  "res://tools/playtest_bot.gd"` and override its sampling hook.
- **Measure art numerically.** A hue histogram of a set of small sprites
  shows where each material sits (e.g. clothing at 320-350 degrees, skin at
  10-30, red at 350-2), which sets a recolour window that touches only what
  it should. Don't eyeball tiny sprites.
- **When a fix doesn't clear a repeat report, reproduce the exact scene**
  the user described before touching code again.
- **Close the loop:** a check that fails on the old code, then passes
  (`testing-discipline.md` 3). Revert changes that didn't help (a global
  spawn-scale tweak that didn't move the result comes out the same session;
  then measure the real driver).

## 2. See it: windowed capture

In Claude Code you can render the real game and look at it. Headless tests
can't see layering, size, shader failures or things hidden under the HUD.

`assets/godot/capture.gd` (copied to `tools/capture.gd`) is an `extends
SceneTree` script: it boots the main scene, applies a named scenario (jump to
a level, force an event, set the time of day), waits, grabs
`root.get_texture().get_image()`, and writes PNGs and a contact sheet to
`docs/screens/`. Always grep the run's log for `SHADER ERROR`.
```bash
timeout 300 "$G" --path . --script res://tools/capture.gd ++ scenario=main 2>&1 | tee capture.log
grep -c "SHADER ERROR\|SCRIPT ERROR" capture.log
```
Run it **without `--headless`**, then `Read` the PNGs.

Typical catches: a large object hidden under the HUD; a wind front that
never ran (strict `>` against a start at `-FRONT_W`); a prop sitting on the
wrong part of the background art; a shader compile failure; prop size and
centring.

**Harness traps** (each costs a round):
- **The window loses focus and the game auto-pauses.** Unpause and hide the
  pause panel *every frame* of the wait loop, not once.
- **A stale frame.** A paused or un-redrawn game shows the previous frame.
  Call `queue_redraw()` on every layer node, tick the game once
  (`game._process(0.0)`), wait a few frames, then
  `await RenderingServer.frame_post_draw` before `get_image()`. A ground
  layer that isn't redrawn makes every "growth stage" shot identical.
- **A frozen clock.** Nothing time-based appears. Drive time by hand
  (`advance(seconds)` calling `_process(0.05)` in a loop) for repeatable
  shots.
- **The harness's tick changes the scene.** The first tick can drive
  hand-placed enemies away. Neutralise timers for the shot
  (`enemy_left = 999`, `event_t = INF`).
- **Overlays.** Hide intro cards, tutorials and, when it covers the subject,
  the HUD. Pin the time of day so shots don't fall at night by accident.
- **Scale.** Judge at game scale (1x of the logical canvas, nearest-scaled).
  Use 2x close-ups only to inspect detail: 9 px arrows and 1 px sparks that
  read fine at 2x are invisible in play.
- **Phone view without a phone:** `assets/godot/device_preview.gd` renders a
  SubViewport at device size with `size_2d_override` set to the logical
  canvas, which is exactly what a phone shows.
- **Clean up.** Delete one-off shot scripts and their `.uid` files.
- **Send images full size** to the user (shrinking them hides most of the
  difference), with a caption saying what to look at.
- **Context.** Image reads are expensive: hundreds of screenshot reads in one
  session force repeated context compactions. Hand a big batch to a subagent
  that reads the images against a checklist (hidden behind HUD, too small at
  1x, layering, off-palette colour, overlapping labels, identical frames) and
  returns text.

## 3. Motion bugs: watch it run

Stills miss what only shows in motion: critters inside walls, NPCs stuck,
effects left behind. `assets/godot/watch.gd` runs the game in real time (not
driven) and saves a frame every few seconds (e.g. every 4 s for 40 s, with
scheduled player actions). For "does it animate at all", use the pixel diff
in `testing-discipline.md` 9.

## 4. Regressions: suspect the harness, bisect in a worktree

**After a performance or harness change, suspect the harness first.** A bot
that cleared a level 4/4 can drop to 0/4 after an optimization pass because
of the harness, not the game: a new `run/max_fps=60` cap plus the bot's 4x
time scale gives four physics steps per steering frame, so the bot wedges on
a corner. The fix is `--max-fps 0` in the bot runner, not a game change.
Other bot problems that look like game bugs: lost in narrow streets, trapped
on a corner, never triggering an event it needs. Each needs a debug trace to
tell apart.

**Bisect in a git worktree** so the working tree stays untouched:
```bash
git -c core.longpaths=true worktree add ../ws-bisect HEAD
# apply the change set one file group at a time; after each group run
# 4 parallel bot runs of the failing case
git -c core.longpaths=true worktree remove ../ws-bisect
```
Keep the worktree path short on Windows (`windows-and-shell.md`). Four runs
per step, because small samples flip by chance: a "2/4" is often noise.

## 5. The end-game optimization pass

Run it when the game is close to content-complete and the user asks to
"go over the code and optimize". Goal: behaviour-preserving, verified. A
pass like this typically turns up several real bugs, removes hundreds of
lines and trims GPU passes.

1. **Baseline.** Smoke test, a bot run if the project has one, windowed
   renders of every level or screen.
2. **Review with three read-only subagents in parallel**, each with a scoped
   brief. Scopes that work: core loop / event systems / UI + audio + shaders
   + export. The brief:
   ```
   Review <scope> in <project path> for performance problems, bugs and dead code.
   DO NOT EDIT any file.
   Grep the whole project before claiming anything is dead: tests and tools
   use internals.
   For each finding give: file:line, how often it runs (per frame / per event /
   once), estimated cost, the minimal fix, risk (none / low / medium).
   Rank findings by value. Under 1,200 words.
   ```
3. **Verify every claim yourself** (read the code, grep the callers). Drop
   the ones that are wrong.
4. **Apply in batches** of related fixes, smoke test between batches.
5. **Windowed renders at the end** of every level or screen, log grepped for
   `SHADER ERROR`. An early-out "optimisation" can break a shader on this
   pass (`godot-gotchas.md` 4.4).
6. **Bot regression run.** On a regression, bisect (section 4).
7. **Report in sections:** Bugs, Performance, Cleanup, and separately "found
   but deliberately left alone" (section 7).

## 6. Mobile 2D performance checklist

| Problem | Why it costs | Fix |
|---|---|---|
| Full-screen `hint_screen_texture` shader at neutral settings | A desaturate grade still runs every frame at native resolution (about 2.6 M px on 1080x2400) while set to "no change" | Hide the node whenever it's neutral. The most expensive thing a 2D frame can do |
| Invisible full-screen `ColorRect` | A tint at alpha 0 still blends every frame | `visible = false` when the target alpha is 0 |
| Full-screen shaders run at device resolution | With `canvas_items` stretch, a night shader looping 24 lights runs per *device* pixel | Gate the work (an early-out can skip about a quarter of the screen); for bigger wins render into a small SubViewport (e.g. 180x320) |
| O(n²) scans of `get_children()` | Every entity scanning all world children: over 100k iterations/s | Build one shared list per frame in a pass that already visits everything; read it |
| Theme overrides every frame | `add_theme_color_override` each frame re-themes and re-shapes a label | Set only on change |
| Per-instance `ShaderMaterial` | Breaks batching | One shared static material when there are no per-instance uniforms (one per colour for tints) |
| Allocation in hot paths | `get("beginner", {})` builds a new dict every call | A shared `const NOT_BEGINNER := {}` |
| Hidden helpers still working | Tutorial rings redrawn all session | Early-out when `not is_visible_in_tree()` |
| Music loaded on the frame it starts | A 1-2 frame stutter | `ResourceLoader.load_threaded_request` for the next track |
| Uncapped frame rate | Physics is 60 Hz without interpolation, so more fps buys nothing and costs battery | `run/max_fps=60`; then bots need `--max-fps 0` (section 4) |
| Dead fallbacks after art lands | Hundreds of lines of code-drawn fallbacks for art that always exists, plus unused sprites | Delete in the polish pass; convert art slots to `preload` consts at content lock (`architecture.md`) |
| Work repeated on every reset | Baking the ground per pixel on every `_reset` | Bake once (`if ground_tex == null`); the smoke test gets much faster |

Known limits worth stating to the user rather than fixing early: a fixed light
array caps lights (e.g. 32, a blocker for zooming out); a 2x density set
costs about 4x sprite memory.

## 7. Fixes that change balance are offered, not imposed

A bug fix that measurably changes difficulty is a design decision. Fixing an
overflow bug (pickups silently vanishing when a pile merges into a nearly
full one) can make a level measurably harder; then revert it and report it
as "found but deliberately left alone", pending a rebalance decision. A
plainly wrong bug still gets fixed (the shared-shape bug,
`godot-gotchas.md` 2.2), but if balance was tuned around it, re-measure after
the fix and say so.
- Apply behaviour-preserving fixes.
- For balance-changing ones: measure the effect, describe it, offer it as a
  numbered option, and log the open decision in `docs/status.md` (`open:`) so
  it isn't lost. A question left only in a chat report is easily forgotten.
