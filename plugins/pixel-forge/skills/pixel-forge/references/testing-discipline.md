# Testing discipline

A headless smoke test that grows with the game (hundreds of checks by the
end) catches real bugs most rounds, including ones that delete or block
things silently in play. The template is `assets/godot/smoke_test.gd`
(copied to `tools/smoke_test.gd`): helpers
`check`/`sim`/`press`/`drag`/`tap`/`pick` through `root.push_input`, its own
save path, the "visual layer never changes scored state" check, and
`quit(1)` on any failure. These are the habits that make a suite
trustworthy rather than merely green.

Bot playtests (when to run them, how to read them) are in `playtesting.md`.
Finding and fixing what a test exposes is in `debugging-and-optimization.md`.

## Contents
1. Run it
2. Before you run anything: what does it delete?
3. Prove a new check can fail
4. A flaky check is a bug report
5. The game keeps running during every await
6. Time: wait on conditions, not frames
7. Test behaviour and properties, not internals or counts
8. Read every log
9. What headless can't see
10. CI: pass means exit code 0

---

## 1. Run it

```bash
G="${GODOT:-godot}"
timeout 300 "$G" --headless --path . --import                            # after pulling, new class_name, new art
timeout 600 "$G" --headless --path . --script res://tools/smoke_test.gd 2>&1 | tee smoke.log
grep -cE "SCRIPT ERROR|SHADER ERROR" smoke.log                          # must be 0
```

- Wrap every Godot call in `timeout`: a script error makes headless Godot
  wait in the debugger forever (`windows-and-shell.md`).
- Run it **twice** before shipping anything involving randomness, and
  **five to eight times** when chasing a flake. A fix isn't done until it's
  green several runs in a row.
- In the claude.ai sandbox, `scripts/stage_push.py` also runs it in a fresh
  clone of the user's repo: a test can pass locally every time and fail in a
  clean clone, because it depends on an untracked or ignored file. In Claude
  Code, CI on push does that job (`delivery.md`).

## 2. Before you run anything: what does it delete?

A smoke test that resets game state can wipe the real save, and a backup
taken by guessing the save folder can miss it (`user://` follows the
project's display name, not its folder; `windows-and-shell.md` 9).
- "Test if you can" or "just test real quick" is not permission to run
  something destructive. Read what the suite deletes first.
- Tests and bots use **their own save path**, never the player's. The
  template points `Session.save_path` at its own file; bot
  runners redirect the whole user dir with `override.cfg`
  (`windows-and-shell.md`).
- Ask the user once per project whether tests may touch their save, and
  record the answer in `CLAUDE.md` ("How we work").

## 3. Prove a new check can fail

Remove the fix, run, watch the check FAIL, put the fix back. A check that
can't fail guards nothing.
- A `_count(game, "Pickup")` helper that ignores its argument and always
  counts NPCs makes every check using it pass for the wrong reason, until a
  new test happens to expose it.
- For a regression check (free a target mid-flight), run it on the old code,
  see it fail, then run it on the fix.
- For an old bug, put it back temporarily to watch its new check fail.

## 4. A flaky check is a bug report

**Instrument, don't loosen.** When a check fails intermittently, print
exactly what was there when it failed before touching a threshold. Put the
values in the check's label so every run records them:
```gdscript
check("with two you can, and it fills both %s vs %s" % [got, want], got == want)
```
Instrumenting this way finds real bugs that a wider tolerance would bury:
two piles arriving on the same tick merging into each other and vanishing
(on every level); an event ending on its first frame when every participant
is blocked.

**"A print makes it pass" means leftover state.** A check that fails every
time without a debug `print` and passes with it is reading timing-dependent
state. Typical case: the label shows `[2, 3]` vs `[1, 5]` because the player
is still in a knockback left by an earlier section, and the print changes
the timing. Fix: clear `_stun` and `_knocking` before the section, then three
green runs. When observing a test changes its result, suspect time-dependent
state carried over from an earlier section, not the logic.

**Loosen only after instrumentation proves the long case is legitimate.** If
"every worker makes a round trip" flakes, instrument it to print the slowest
worker's path; if that trip really takes over 60 s, widen the window to
90 s. If the same check later fails with different workers, treat it as a
real bug (e.g. workers sharing a path stopping at every meeting, fixed with a
40-80 s cooldown).

## 5. The game keeps running during every await

The test drives the live game, so between one line and the next, spawners
spawn, enemies walk, the player gets bumped.

- **Clear what could interfere right before the action**, not at the top of
  the section. A `sim_undisturbed()` helper clears NPCs and stun **every
  frame**, because setting a flag once is undone by the next spawn.
- **One `neutralize(game)` helper** holds every protection timer and hazard
  the harness must clear. Without it, adding one 2 s hit-grace window means
  sprinkling `player._grace = 0.0` into about 20 places.
- **Park the player** somewhere harmless. Left near the action, it can
  collect or knock away things a test is tracking.
- **Put the scene into a stable starting state.** A check about animals
  fleeing a predator needs both placed and the predator's timers set, or the
  first tick drives them off; a check about NPCs gathered at a building flakes
  when they wander home.
- **Reset global state** the section depends on (difficulty multipliers,
  timers another section advanced), or compare the invariant part:
  `spawn_scale() / adapt` rather than `spawn_scale()`.
- **Test invariants, not snapshots, when a background spawner can act.** A
  check "special pickups only pile up with special pickups" fails when the
  game's own spawner drops one nearby. Make the check the exact rule: a
  special pickup never merges into a plain one.
- **Count what you created.** Track the specific objects the section made
  ("only the test's own crates"), or count within the true reach of the rule.
- **Long suites:** give each section its own variable prefix (`wl_`, `bt_`,
  `ep_`). Duplicate locals in one long function are parse errors.

## 6. Time: wait on conditions, not frames

- **Never count frames.** A frame is whatever the fps cap says, and that
  changes. A check "NPCs walk out along a street" that assumes N frames
  breaks when `run/max_fps=60` arrives; wait until the NPC has walked a
  distance instead (it may fade in first). Wait on the condition, with a cap
  so a broken game can't hang the suite:
  ```gdscript
  var n := 0
  while npc.position.distance_to(start) < 40.0 and n < 600:
  	await process_frame
  	n += 1
  ```
- Or use `sim(seconds)`, which accumulates real delta.
- **Compute expected durations from the game's constants, then add margin.**
  Three units that need two 260 px round trips at 60 px/s take about 19 s,
  so simulating 20 s sits on the edge. A 0.56 s animation checked after
  0.5 s fails every time.

## 7. Test behaviour and properties, not internals or counts

- Checks read as statements about the game: "a big wave cannot reach you on
  high ground", "START plays level 1's music". When a design changes, those
  checks say what changed; tests pinned to internals just break.
- **Assert properties, not counts.** "22 sounds" and "5 ambient beds" break
  every time content is added. Assert "every sound loaded", "every bed is
  playing".
- **Pin the tuning that matters** so it can't soften silently ("storms come
  often and last long enough to matter": `STORM_EVERY <= 80 and STORM_LENGTH
  >= 20`).
- **Pure static helpers make hard bugs testable.** A pure `sway_step()` lets
  the suite simulate an hour of frames in a loop; `Hud.inset_in_game()` is
  tested at real phone sizes; `Upgrades.total_cost()` proves the economy is
  solvable.
- **Check the effective project settings** (`godot-gotchas.md` 1.1): the
  stretch aspect, the main scene, the icon path.

## 8. Read every log

A green summary can sit on top of thousands of errors.
- After every smoke, bot and capture run:
  `grep -c "SCRIPT ERROR" run.log` and `grep -c "SHADER ERROR" run.log`.
  Tens of thousands of `SCRIPT ERROR` lines in bot logs can hide a paid
  upgrade that does nothing on every level (`godot-gotchas.md` 3.1).
- Physics-server `ERROR:` lines count too: a hundred "Can't change this state
  while flushing queries" in one bot run is a real bug (`godot-gotchas.md`
  2.1).
- Leak warnings at exit (`ObjectDB instances leaked`, `resources still in
  use`) are easy to ignore on every CI run. Treat them as a warning to fix,
  then a failure.

## 9. What headless can't see

- **Shader compile errors.** Headless runs don't report them: a `return` in
  `fragment()` can turn a level solid white while the smoke test passes.
  Every shader edit gets a windowed render (`assets/godot/capture.gd`) and a
  `SHADER ERROR` grep.
- **Layout.** Open a panel in its worst state (largest numbers, longest
  text) and assert nothing's global rect runs off-screen.
- **Audio.** Duck the music, run the transition, check the bus volume came
  back.
- **"It animates."** Grab two frames a second or so apart and diff them: for
  animated water, thousands of water pixels should change while land pixels
  stay put. Both halves matter: the thing moves, nothing else does.
- **The visual layer never changes scored state.** Snapshot everything the
  game keeps score with, run the life/ambience layer for a while (weather
  included), and compare:
  ```gdscript
  var snap := func(): return [game.energy, game.score, game.buildings.duplicate(), game.inventory.duplicate()]
  var a: Array = snap.call()
  for k in 300:
  	life._process(0.1)
  check("30s of life - rain included - changes nothing the game keeps score with", snap.call() == a)
  ```
  This check is what lets "make the world feel alive" rounds run without
  touching balance (`architecture.md`).
- For everything else, render it and look (`debugging-and-optimization.md`).

## 10. CI: pass means exit code 0

A CI job can stay green on every push while unable to fail:
`godot ... | tee result.txt` without `pipefail` throws away the exit code,
and `grep -q "0 failed"` also matches "10 failed". A job running an older
Godot than the project silently tests something else.
- The suite calls `quit(1)` on any failure; the job runs with
  `set -o pipefail` so the exit code survives `tee`.
- If you also grep the summary, match it exactly:
  `grep -qE '^=== [0-9]+ checks, 0 failed ===$'`.
- Fail on `SCRIPT ERROR` / `SHADER ERROR` lines.
- Import first, and pin the Godot version from `forge.json`.

The workflow template and its setup are in `delivery.md`.
