# Project docs: the files that carry a game between sessions

Chat context gets compacted; files don't. A dated decision log carries a
project through any number of compactions — chat memory doesn't. These are the
files `new_godot_project.py` writes from `assets/project/`, what each is for,
and how to keep them true.

## Contents
1. The set
2. CLAUDE.md — the working brief
3. docs/bible.md — locked decisions
4. docs/handoff.md — the decision log
5. docs/status.md — machine-readable state
6. docs/assets.md and docs/art-manifest.md
7. Per-system, per-level and playtest docs
8. forge.json
9. The doc sweep: stopping drift

---

## 1. The set

| File | Holds | Changes |
|---|---|---|
| `CLAUDE.md` | How to work on this game: current state, hard rules, agreements, layout | *Current state* every round |
| `CLAUDE.local.md` | Machine paths (Godot exe, gh, python) — gitignored | When the machine changes |
| `docs/concept.md` | Pitch, hook, moment, loop, comparables, scope, risks | Rarely |
| `docs/bible.md` | Locked design, technical and visual decisions; taste | Revised in place when a decision changes |
| `docs/handoff.md` | Append-only dated decision log with rejected alternatives | Every round |
| `docs/status.md` | Stage, progress, next three, blockers, open questions (YAML front-matter) | Every round |
| `docs/later.md` | Parked ideas — not rejected, not approved | When something is parked or revived |
| `docs/assets.md` | Asset ledger: file, Magnific creation id, model, prompt, cutter | Every art round |
| `docs/art-manifest.md` | Art rules and measured facts; exact commands | When art rules change |
| `docs/templates/` | System design, level, playtest report templates | — |
| `forge.json` | Screen settings and versions every tool reads | When the canvas changes |

## 2. CLAUDE.md — the working brief

Claude Code loads it automatically, so it is the first thing every session
sees. Keep it short and **current**:

- **Current state** block at the top — stage, engine version, resolution,
  palette size, test count, last-verified date. Rewrite it every round.
- **What the game is**: the hook, the thing to protect, and the constraint the
  design rests on ("if a change makes the main currency abundant, it breaks
  the game").
- **Hard rules**, numbered. When one is superseded, *edit it*. Why: a
  "REDESIGN" banner stacked on top leaves stale rules underneath (an old engine
  version, an abandoned palette lock) that later sessions still follow.
- **Wording and voice** for player-facing text (a character's pronouns, terms
  never to use). Rules like these get lost if they live only in the log.
- **Do not add**: features cut on purpose.
- **How we work**: the user's standing agreements (commits, autonomy, tests,
  saves). See `collaboration.md`.
- **Round checklist**, **Layout** (every file → purpose → run command), and
  **Dev flags to remove before release**.

## 3. docs/bible.md — locked decisions

Hook, loop, **units named early** (if the code names the unit before the
design does, the names diverge — a `level_index` that actually counts rounds),
session length, end condition; engine, viewport, scale, aspect, orientation,
perspective, sprite unit, density; style anchor, palette and reserved colours,
outline, light direction, hard alpha; a **Taste** section in the user's words;
the layer stack; audio buses. Each row has a *Why*. Revise in place; log the
change.

## 4. docs/handoff.md — the decision log

Append-only and dated. It works better than any status file because it
records **why not X**:

An entry, shape only (the values are illustrative):

```
**YYYY-MM-DD — Enemy patrols, stage 1 (user's call).**
- Enemies patrol between waypoints on their own; PATROL_SPEED in main.gd.
- Rejected: a squad-leader unit — implies command mechanics nobody designed.
- Who decided: user.
- Tests: N smoke checks pass. Bot: 3/3 seeds win, no level lost.
- Known limits: patrols can clip through the gate gap.
```

Credit decisions: "(user's call)" or "(assistant's call, offered for override,
not overridden)". Write the entry *before* reporting, so the report can quote it.

## 5. docs/status.md — machine-readable state

YAML front-matter read by the tracker and `/pixel-forge:status`:

```yaml
---
stage: core          # idea|concept|design|prototype|core|content|polish|launch|shipped
progress: 58
next: [Enemy wave 3, Two-tap placement, Save on focus loss]
blockers: ""
open: ["Hero shader is darker than authored — fix it (brightens the hero)?"]
parked: false
updated: YYYY-MM-DD
---
```

(Illustrative values.)

Progress moves on evidence, a few points per round; it jumps only at a stage
change and never goes down except for a recorded redesign. **`open:` is where
unanswered questions live** — repeat them in every report until answered.

## 6. docs/assets.md and docs/art-manifest.md

- **assets.md** is the ledger: every game asset → raw file → Magnific creation
  id → model and size → prompt reference → cutter → notes. Signed download
  links expire; the creation id is the durable handle. `scripts/fetch_art.py`
  appends raw-batch rows automatically. Keep a credits table.
- **art-manifest.md** is the *rules*: texture vs drawn size vs hitbox per
  entity, measured facts (minimum readable size, hue windows), the exact
  command for every asset, rejected approaches with the measurement that
  rejected them. Every art transform is a committed script. Why: a one-off
  transform described only in prose can't be re-run when the source art
  changes.

## 7. Per-system, per-level and playtest docs

- `docs/<system>.md` from `templates/system.md` — talk-out doc ending in
  *Questions for the user* → *Decisions (user, date)*.
- `docs/levels/NN-name.md` from `templates/level.md` — status in the user's
  words, mechanic table, signature event, history by pass, tuning knobs (exact
  data block and keys), and **4–5 "what to feel for" playtest questions**.
- `docs/playtest-YYYY-MM-DD.md` from `templates/playtest.md` — human or bot.

Content tables live in code or `data/` — the doc may show them, but generate
or test the doc copy so it can't silently diverge. Why: a table duplicated by
hand into a doc drifts from the code at the first tuning pass.

## 8. forge.json

```json
{ "view_w": 960, "view_h": 540, "pixel_scale": 1, "aspect": "expand", "cell": 32,
  "godot_version": "4.7", "forge_version": "1.0.0", "palette": "art/palette.hex",
  "tracker": { "id": "my-game", "icon": "art/ui/icon.png" } }
```

Every forge tool reads its defaults from here (`scripts/forge_config.py`), so
nothing hard-codes a resolution. The CI workflow reads `godot_version` so CI
runs the same engine as the developer. Why: CI on a different engine version
than the project gives false passes and false failures.

## 9. The doc sweep: stopping drift

Docs drift: READMEs quoting old check counts, level docs saying "awaiting
playtest" after tuning, a manifest contradicting itself. At the end of every
round (the round checklist), and in a fuller pass before each stage gate:

1. Rewrite the `CLAUDE.md` *Current state* block from the code (engine version
   from `project.godot`, palette size from the file, test count from the run).
2. Update status.md front-matter.
3. Grep the docs for superseded rules named in today's handoff entry.
4. Give every doc a one-line **Status / last verified** at the top.

`/pixel-forge:status` does steps 1–2.
