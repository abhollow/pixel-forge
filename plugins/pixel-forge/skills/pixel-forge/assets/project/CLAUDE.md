# {{GAME_NAME}} — working brief

Load the `pixel-forge` skill before any project work. Then read, in order:
this file, `docs/status.md`, the newest entries at the bottom of
`docs/handoff.md`, and `docs/bible.md`. State the current stage and its exit
criterion before starting.

## Current state

Rewrite this block at the end of every round. Never stack "REDESIGN" banners
above stale rules; edit the rules themselves and log the change in handoff.md.

- **Stage:** idea (0%). Exit: a one-paragraph idea captured in docs/concept.md.
- **Engine:** Godot {{GODOT_VERSION}} · {{VIEW_W}}x{{VIEW_H}} at {{PIXEL_SCALE}}x · aspect `{{ASPECT}}` · {{ORIENTATION}}
- **Perspective:** {{PERSPECTIVE}} · sprite unit {{CELL}} px
- **Palette:** not chosen yet
- **Smoke test:** template only
- **Last verified:** {{DATE}}

## What the game is

- **Hook:** (one sentence, from docs/concept.md)
- **The thing to protect:** (the 5 seconds of play everything is measured against)
- **The constraint the design rests on:** (e.g. "energy is scarce — anything that
  makes it abundant breaks the game")

## Hard rules

1. Every tuning number lives in the one constants block at the top of the rules
   script, with a dated comment saying why it has that value.
2. The visual layer (ambience, effects, life) reads the rules and never writes
   them, and uses its own RNG. A smoke check proves it.
3. Art drops into art slots: code-drawn placeholder until the file exists.
4. `docs/later.md` is parked, not approved. Nothing moves out of it without the user.
5. New mechanics or rules need the user's yes. Visual-only polish inside an
   agreed batch does not.

## Wording and voice

(Player-facing text rules: names, pronouns, tone, words to avoid.)

## Do not add

(Features cut on purpose. One line each; the reasoning is in docs/handoff.md.)

## How we work

Record the user's standing agreements here as they are made. Defaults until then:

- **Options:** numbered, with a recommendation. No pop-up question widgets.
- **Autonomy:** build an agreed batch end to end; ask before new design directions.
- **Commits:** only when the user asks. (Change to "commit and push at the end of
  every batch" if they say so.)
- **Tests:** smoke test on every change. Bot playtests only when asked.
- **Saves:** ask once whether tests may wipe the user's save, and record the answer.
- **Reports:** mirror the user's numbering; name each tuning knob and its file;
  test count; credits spent; what you could not check; what is not committed.

## Round checklist

1. Smoke test (twice when randomness is involved).
2. Render the affected scenes with `tools/capture.gd` and look at them.
3. Append a dated entry to `docs/handoff.md` (what, why, rejected alternatives, who decided).
4. Update `docs/status.md`, `docs/assets.md`, and the **Current state** block above.
5. Commit/push per the agreement above.
6. Report back in the user's numbering.

## Technical

| Field | Value |
|---|---|
| Engine | Godot {{GODOT_VERSION}}, GDScript, gl_compatibility |
| Viewport | {{VIEW_W}}x{{VIEW_H}}, pixel scale {{PIXEL_SCALE}}, stretch canvas_items, aspect {{ASPECT}} |
| Orientation | {{ORIENTATION}} |
| Screen settings | `forge.json` (every forge tool reads it) |

`project.godot` is already configured. Never put comments in it — the editor
rewrites the file. Machine paths (Godot exe, gh, python) live in
`CLAUDE.local.md`, which is gitignored.

## Tooling

Forge scripts are vendored in `tools/forge/` (version in `tools/forge/VERSION`),
so a fresh clone works without the plugin. Refresh them with
`/pixel-forge:doctor` when the plugin updates.

## Layout

```
scenes/main.tscn            entry scene
scripts/main.gd             rules + tuning block
scripts/session.gd          settings, buses, atomic save
tools/smoke_test.gd         headless checks:  godot --headless --path . --script res://tools/smoke_test.gd
tools/capture.gd            windowed renders: godot --path . --script res://tools/capture.gd ++ scenario=main
tools/forge/                vendored Pixel Forge scripts
raw_art/                    Magnific originals (.gdignore)
art/                        game-ready art
docs/                       concept, bible, status, handoff, later, assets
```

## Dev flags to remove before release

(List every DEV_* constant, debug overlay and placeholder string as you add it.)
