# Playtesting and iteration

Three instruments, each good at different things: **people** (fun, clarity,
feel, onboarding), **bots** (balance, durations, engine errors, regressions),
and **renders** (what the screen actually shows). Testing code itself is in
`testing-discipline.md`.

## Contents
1. Human playtests
2. Turning feedback into changes
3. Bots: what they are for
4. Running a bot
5. Seeing the game: capture, watch, device preview
6. Comparing options

---

## 1. Human playtests

**The prototype gate** (strangers, early):

- **Don't explain anything.** Hand it over and stay silent. Every word of
  explanation is a bug report you are suppressing.
- **Watch hands and face, not words.** Hesitation marks unclear design.
- **Three to five people** is plenty; the same two problems show up for everyone.
- **Ask what they expected to happen**, not whether they liked it.
- **Time the first meaningful choice.** Past ~60 seconds, front-load it.
- Questions that get real answers: What did you think you were supposed to do?
  What were you trying to do when you hesitated? One thing to change? Would you
  open this again tomorrow — honestly?

If two of five bounce off the loop itself, go back to Design. That is the
process working.

**The developer's own playtests** (most rounds): the user plays a build —
desktop, or a phone with a side-loaded **debug** APK — and sends a numbered
list mixing bugs, feel, art and ideas. Make that easy:

- A **debug-only level select** (`if OS.is_debug_build()`) so any level is one
  tap away. Mark levels that have no art yet.
- Each level doc ends with **4–5 "what to feel for" questions**.
- In Claude Code you can launch the game for them (`godot --path .`, or the
  Godot MCP `run_project`) and tail the debug output for errors while they play.

## 2. Turning feedback into changes

1. **Answer per number**, in their numbering.
2. **Sort** each item: *broken* and *unclear* → fix now (confusion is a design
   bug); *missing* → usually `docs/later.md`; *taste* → change it if it's theirs,
   ignore a stranger's unless it repeats.
3. **Reproduce and measure before changing** — a feature reported as missing
   often already works, and something else undermines it.
4. **Change the right knob.** For "a little stronger" or "split the difference",
   change one number in the tuning block and name it in the report. Expect a
   second round on sizes (2x was too much → try the in-between).
5. **Hit the binding constraint.** Retry easing that slows spawning does
   nothing once the field is at its cap; scale the cap.
6. **When the human says it isn't fun, believe them over the numbers.** "Too
   much going on" becomes a global density multiplier with the ramp shape kept.
7. **Onboarding is judged by people.** A bot can clear level 1 while a new
   human fails it twice. Give level 1 its own beginner knob block.
8. Smoke test, render if visual, report with knobs and commit status.

By default, **tackle feedback from a human-playtest standpoint; don't run bots
for every change unless the user asks.** Offer a bot run; don't start one. Why:
bot runs are slow, and they don't measure the feel a human reported.

## 3. Bots: what they are for

| Good for | Not for |
|---|---|
| Unattended systemic passes (an overnight campaign across every level) | Fun, feel, readability |
| Measuring unit length against a target (e.g. ~5 min a level) | Onboarding difficulty — the bot isn't new |
| Finding engine errors (a flood of `SCRIPT ERROR` lines can expose an upgrade that silently does nothing) | Validating a feel change the user described |
| Before/after on a specific complaint (losses to the first hazard, before vs after) | Small samples — 4 runs is a coin flip |
| Regression checks after refactors (catches sudden slowdowns) | |

Framing for the user: **a bot clear means a competent player can clear it; a
bot failure means play it yourself — not that it's impossible.** A bot sees in
the dark, reacts instantly and buys optimally; budget roughly 1.5x the bot's
time for a person.

Bot bugs masquerade as game bugs: lost in narrow corridors, trapped on an
obstacle corner, wedged by a frame-rate cap. Each needed a debug trace to tell apart.
Report bot-tooling fixes separately from game fixes.

## 4. Running a bot

Template: `assets/godot/playtest_bot.gd` (copied to `tools/`), runner
`assets/godot/run_bots.sh`, summary `scripts/bot_report.py`.

- The bot drives the **same paths a tap takes** — public action functions, or an
  injectable input object (a virtual joystick that exposes `direction` lets a
  bot steer it). Design input to be injectable.
- Human-paced: a reaction time between acts (`REACT ≈ 1.0 s`), fixed `STEP`.
- Args after `++`: level, unit, seeds, time scale, limit, `out=` JSONL, `debug=1`.
- With a time scale, raise `Engine.physics_ticks_per_second` with it and run
  with `--max-fps 0`. Why: at 4x time scale a 60 fps cap packs 4 physics steps
  into each steering frame, which wedges the bot and looks like a regression.
- One JSON line per attempt: result, time, goal vs earned, hits with positions,
  traces sampled every N seconds, stuck events.
- Give each parallel run its **own user dir** (`override.cfg` →
  `config/use_custom_user_dir`), removed on exit; never commit `override.cfg`.
- After every run: `grep -c "SCRIPT ERROR"` the logs.
- **Probe scripts** extend the bot and override a sample hook to log one
  system's state every couple of seconds.
- Long runs go in the background (`run_in_background`) and are polled; the Bash
  tool stops at 600 s.

## 5. Seeing the game: capture, watch, device preview

In Claude Code you can render the real game and look at it — do it every
round something visual changes.

- **`assets/godot/capture.gd`** — run **windowed** (no `--headless`). Boots the
  main scene, applies a named scenario (jump to a level, force an event, pin
  the time of day), waits, grabs `root.get_texture().get_image()`, saves to
  `docs/screens/`. Traps it handles: the game auto-pauses when the test window
  loses focus (unpause every frame); a paused tree doesn't redraw (queue a
  redraw on every layer, wait for `frame_post_draw`); hide intro/tutorial
  overlays; neutralise timers that would move hand-placed actors.
- **Grep the capture log for `SHADER ERROR`.** Why: the headless suite runs
  without a real renderer, so a shader error can pass it and render a level
  solid white.
- **`watch.gd`** — real-time frames every few seconds, for things only motion
  shows: actors inside walls, stuck walkers, effects left behind.
- **`device_preview.gd`** — a SubViewport at phone resolution with the logical
  size override, so you see what a phone shows without a phone.
- **Size for the game scale.** Check at 1x; use 2x close-ups only to inspect
  detail. Why: details that look fine in a close-up (a 9 px arrow, a 1 px
  spark) vanish at game scale.
- **Effects hide behind the HUD** — frame shots away from it or hide the HUD.
- **Measure instead of eyeballing**: count pixels of a colour, diff two frames
  to prove water moves (thousands of water pixels change, land stays put).
- Many screenshots fill the context fast and force compactions. Hand batches to
  the **visual-qa** agent, which reads them and returns text.
- Send the user the key renders as files, **full size** — shrinking hides the
  difference they are judging.

## 6. Comparing options

For any taste decision (art option, size, density, layout), build a **decision
image**: options side by side at game scale on the real background next to a
known sprite, captioned, with your recommendation and why
(`scripts/contact_sheet.py`). Name the sheets
`<subject>_options_at_game_size.png`; for detail level, compare today / 2x / 4x
side by side at the target screen resolution. Don't change the game to
compare — build the variants beside it.
