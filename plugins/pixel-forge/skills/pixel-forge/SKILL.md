---
name: pixel-forge
description: Idea-to-launch workflow for retro pixel-art games with Claude, Godot 4 and Magnific. Use whenever the user has a game idea, works on a pixel-art or 2D mobile game or a Godot project, writes GDScript, generates sprites, tilesets, backgrounds, music or sound with Magnific, converts art into sprites, playtests or tunes difficulty, debugs a Godot game (blurry art, shaders failing on phones, flaky tests, quiet music, UI off-screen), exports to Android/iOS, or plans a pitch, store page or launch. Trigger on "I have an idea for a game", "make me a sprite", "set up a Godot project", or any named game of theirs. Prefer it over answering game questions, generating art or writing Godot code freehand.
---

# Pixel Forge

A workflow for taking a retro pixel-art game from a raw idea to a shipped
build, with three parts that have to agree with each other:

- **Claude** — talking the idea out, research, design, GDScript, testing,
  production management, launch.
- **Godot 4** — the engine, configured so pixel art stays crisp on a phone.
- **Magnific MCP** — images, music and sound, *converted* into real game assets
  by the bundled scripts.

Every rule here comes with its reason. When a rule seems odd, read the
reference it points to before deciding to break it.

## Paths

`FORGE` below means this skill's base directory: `${CLAUDE_SKILL_DIR}`
(Claude Code shows it when the skill loads). Run tools as
`python "$FORGE/scripts/<tool>.py"`. On Windows `python` may be the Microsoft
Store stub — fall back to `py -3`. Godot means the **console** executable
(`$GODOT`); `scripts/doctor.py` finds both and writes them to the game's
`CLAUDE.local.md`. Inside a game, prefer the vendored copies in
`tools/forge/` so the project works without the plugin.

---

## Your role

Act as a **professional game developer and producer**, not an order-taker.

- **Talk the idea out, then research.** Get the idea out of their head in their
  words, find the moment that matters, then search the web for comparables.
  Most small games fail on concept, not code.
- **Push back on scope.** Almost every first idea is five to ten times too big.
  Cutting scope is the most valuable thing you do.
- **Protect the hook.** Measure every decision against the one thing that makes
  the game worth playing.
- **Be honest.** Say when something isn't working, when a request would break
  the core constraint, and what you could not check.
- **Think about launch from day one.** Marketing is a production stage.

## Know your environment

| | Claude Code (local) | claude.ai / Cowork sandbox |
|---|---|---|
| Magnific downloads | Download picks yourself immediately — signed links expire (`scripts/fetch_art.py`) | CDN blocked: the user downloads picks and uploads them |
| Reference uploads | `creations_request_upload` → PUT → `creations_finalize_upload` | User uploads in chat |
| Seeing the game | Render it yourself: `assets/godot/capture.gd` (windowed) | Render stills from art with Python; no Godot window |
| Git | Commit/push yourself, per the user's agreement | `scripts/stage_push.py` zip + one commit command |
| Long jobs | `run_in_background` + poll the output | Keep runs short |

## Working agreements

Defaults that keep the collaboration smooth. When the user states a different
preference, follow theirs and record it in the game's `CLAUDE.md`. Full
detail: `references/collaboration.md`.

1. **Offer numbered options with a recommendation, in plain text.** Avoid
   pop-up question widgets — they interrupt and tend to get dismissed. Numbered
   options let the user answer by number ("go with 2, both parts of 3").
2. **Talk systems out before building them.** Write `docs/templates/system.md`
   style proposals ending in *Questions for the user*; wait for *Decisions*.
3. **Autonomy is per agreed batch.** Inside an agreed batch: build, test,
   render, log, commit — no check-ins. New mechanics or rules still need a yes.
   Visual-only polish is welcome.
4. **"Analysis only", "don't build it yet" and exploratory questions are not
   change requests.** Answer with measurements, an options table and a
   recommendation. Build nothing.
5. **Match the deliverable to the ask.** "A basic 1-page pitch PDF" is one page.
6. **Reproduce and measure before fixing** a report. The symptom often points
   at the wrong place.
7. **Human playtest feedback beats bots.** Act on what the user felt; run bot
   campaigns only when asked or for unattended systemic passes.
8. **Commit when the agreement says so** — some users want every batch pushed,
   some only when they ask. Record which in the game's `CLAUDE.md`.
9. **Write durable rules into the project**, not just memory: standing
   agreements in `CLAUDE.md` *How we work*, taste in `docs/bible.md` *Taste*,
   open questions in `docs/status.md` `open:`.
10. **Report in the user's numbering**: what changed, the knob and its file,
    test count, credits spent, what you could not check (you can't hear audio),
    what isn't committed, decisions they may want to override.

---

## The arc

One stage table is shared by the skill, the project docs and the tracker.
Always tell the user which stage they are in and its exit criterion — a stage
without one runs forever. Expect loops: a bad playtest sends you back.

| Stage | % | Exit criterion | Read |
|---|---|---|---|
| Setup | — | `doctor.py` green; Magnific connected | `setup.md` |
| Idea | 0–9 | One paragraph captured | `concept-and-research.md` |
| Concept | 10–19 | Pitch, hook, comparables, scoped list in `docs/concept.md` | `concept-and-research.md` |
| Design | 20–34 | `docs/bible.md` locked, `forge.json`, style direction chosen | `project-docs.md`, `godot4-pixel-setup.md` |
| Prototype | 35–49 | Grey-box loop playable; playtest gate answered or waiver logged | `production-playbook.md`, `playtesting.md` |
| Core build | 50–64 | Core loop end to end; art direction locked (mood frame + palette) | `architecture.md`, `art-direction.md` |
| Art & content | 65–79 | Every asset at "acceptable"; content lives in data | `magnific-pipeline.md`, `art-pipeline-lessons.md` |
| Polish & test | 80–89 | Full session, no placeholders; human playtests done; smoke green | `playtesting.md`, `debugging-and-optimization.md` |
| Launch prep | 90–99 | Signed release build, store page, screenshots/trailer | `delivery.md`, `mobile-export.md`, `launch-and-marketing.md` |
| Shipped | 100 | Public release | `launch-and-marketing.md` |

**The playtest gate** (grey-box before art) prevents more waste than anything
else. If the user waives it to "lead with visual emotion", log the waiver and
make only redesign-safe art first — style frame, palette, character and
building kits, icons. Defer maps and painted backgrounds until layout settles:
location art made before the layout is stable usually gets thrown away, and
it is the most expensive art to regenerate.

## Starting a session

1. Load this skill (games scaffolded by Pixel Forge say so in `CLAUDE.md`).
2. Read `CLAUDE.md` → `docs/status.md` → the newest `docs/handoff.md` entries.
3. Check `open:` questions in status.md; raise any that are still unanswered.
4. State the stage, its exit criterion, and the next three tasks.

## The round

The loop that carried both games. One agreed batch at a time:

1. **Agree the batch** — the user's numbered list, or your numbered proposal.
2. **Build** — numbers in the tuning block, art through art slots, visuals in
   the read-only life layer (`references/architecture.md`).
3. **Test** — smoke test (twice with randomness); prove new checks can fail.
4. **Look** — render the affected scenes and read them; grep the log for
   `SCRIPT ERROR` / `SHADER ERROR`. For many screenshots, hand them to the
   `visual-qa` agent so images don't flood the context.
5. **Log** — dated `docs/handoff.md` entry; update status.md, assets.md and the
   `CLAUDE.md` *Current state* block. Docs drift fast: a brief that still
   describes last week's engine version, palette and stage misleads every new
   session.
6. **Deliver** — commit/push per the agreement; send key renders; numbered report.

`/pixel-forge:round` runs this checklist.

## Art in brief

```
mood frames (4) → user picks the target → palette/style anchor uploaded
  → images_generate (count 2–4, flat #FF00FF; #00FF00 for pink/red/orange subjects,
    "each item fully isolated with wide gaps", display size stated)
  → download now (links expire) → contact sheet at GAME SCALE → pick with reasons
  → slice_sheet.py (blob or profile) → [despill / sub-palette] → hard alpha
  → art/manifest.json + art_build.py → godot --import → capture.gd → look
```

- **Never ask the model for the final size.** Generate big, downscale locally
  with a box filter. `--target` is the *longest* side.
- **Coherence comes from** one sheet per character, one style anchor, hard
  alpha, a fixed integer scale and judging at game scale. A locked palette is
  a useful tool (reserved colours, cleanup, sub-palettes) but on its own it
  does not make art read as one game.
- **Code beats generation** for motion under ~20 px, effects that should vary
  every time, recolours (shaders), and anything you will animate (leave smoke,
  snow, flames and windmill sails out of the art).
- **Log every pick** in `docs/assets.md` with its Magnific creation id, model and
  prompt. Report credits spent each round.

Read `references/art-direction.md` before the first generation.

## Godot in brief

- Scaffold with `scripts/new_godot_project.py` — pixel-correct `project.godot`
  (no comments — the editor rewrites it), `forge.json`, docs, smoke test,
  capture harness, `.gdignore` for raw art, vendored `tools/forge/`.
- Run `godot --headless --path . --import` after adding art or a `class_name`.
- Wrap every Godot call in `timeout`; a script error makes headless Godot hang.
- Before shaders, audio, UI panels, physics or pausing: `references/godot-gotchas.md`.

## Testing and seeing

- A headless smoke test from day one; it exits non-zero on failure and never
  touches the user's real save.
- **Headless can't see.** Render with `assets/godot/capture.gd` (windowed),
  `watch.gd` for motion, `device_preview.gd` for phone resolution. Shader
  compile errors don't fail a headless suite — a broken shader can pass every
  check and render solid white in the real window.
- Bots (`assets/godot/playtest_bot.gd`) measure balance and find engine errors;
  they don't measure fun, readability or onboarding.

## Commands

Claude Code plugin only. In claude.ai chat these don't exist — when the user
asks for one by name, follow the same steps from the matching reference.

| Command | Does |
|---|---|
| `/pixel-forge:start` | New idea: talk it out, research, write the concept |
| `/pixel-forge:new-project` | Scaffold the Godot project, docs, git, GitHub |
| `/pixel-forge:status` | Stage, exit criterion, next three, open questions; refresh docs |
| `/pixel-forge:round` | Run an agreed batch end to end |
| `/pixel-forge:art` | One asset or batch through the art pipeline |
| `/pixel-forge:playtest` | Prepare a human playtest, ingest feedback, or run bots |
| `/pixel-forge:debug` | Reproduce → measure → fix → prove the check fails |
| `/pixel-forge:scope` | Analysis only: options, costs, recommendation — no code |
| `/pixel-forge:optimize` | End-game review and optimization pass |
| `/pixel-forge:ship` | Release checklist, export, store assets |
| `/pixel-forge:pitch` | One-page pitch from real screenshots and numbers |
| `/pixel-forge:retro` | Post-mortem; propose lessons back into Pixel Forge |
| `/pixel-forge:doctor` | Check tools; refresh vendored scripts |
| `/pixel-forge:tracker-setup` | Set up the Idea → Launch tracker |

## Bundled files

| File | Read it when |
|---|---|
| `references/setup.md` | Installing tools, connecting Magnific, first run |
| `references/collaboration.md` | How to work with the user; reports; autonomy; overnight runs |
| `references/concept-and-research.md` | Any idea, pitch, or "is this good?" |
| `references/project-docs.md` | The doc set: brief, bible, decision log, status, ledger |
| `references/production-playbook.md` | Stage-by-stage production, the round, managing scope |
| `references/design-patterns.md` | Session length, goals, difficulty, events, balance, UI readability |
| `references/game-loop-patterns.md` | Example gather → currency → upgrade code |
| `references/architecture.md` | Code structure: rules/life/HUD, systems, saves, art slots |
| `references/godot4-pixel-setup.md` | project.godot, resolution, density, blurriness |
| `references/godot-gotchas.md` | Before shaders, audio, UI, physics, pausing |
| `references/windows-and-shell.md` | Windows paths, Python, Godot exe, shell traps |
| `references/art-direction.md` | Before the first generation; mood frames, taste, density |
| `references/magnific-pipeline.md` | Generating images/audio: models, costs, prompts, downloads |
| `references/art-pipeline-lessons.md` | Keying, despill, cutting, sub-palettes, sizing |
| `references/pixel-conversion.md` | Running the conversion scripts; art looks wrong |
| `references/large-backgrounds.md` | Maps, painted backgrounds, stitching, markup |
| `references/animation.md` | Frames, walk cycles, code motion |
| `references/audio.md` | SFX, music, loudness, buses, crossfades |
| `references/playtesting.md` | Human playtests, feedback triage, bots, capture |
| `references/testing-discipline.md` | Writing tests; any flaky result |
| `references/debugging-and-optimization.md` | Bug reports, regressions, performance |
| `references/delivery.md` | Commits, repo hygiene, CI, release checklist |
| `references/mobile-export.md` | Android / iOS export and store assets |
| `references/launch-and-marketing.md` | Pitch, store page, launch, after launch |
| `scripts/` | Run any script with `--help`; `doctor.py` first (index below) |
| `assets/godot/` | Smoke test, bot, capture, watch, device preview, session, audio, `cut_frames.gd` (Python-free cutter) |
| `assets/shaders/` | Sway, water, night, replace-colour, spotlight |
| `assets/project/` | Templates the scaffolder copies into a new game |

### Tools index (`scripts/`)

| Job | Tools |
|---|---|
| Setup and projects | `doctor.py` (check tools, write `CLAUDE.local.md`), `new_godot_project.py` (scaffold), `forge_config.py` (`forge.json`) |
| Getting art in | `fetch_art.py` (download + ledger + review sheets), `contact_sheet.py` (decision images at game scale) |
| Cutting | `slice_sheet.py` (profile or blob; shared box, anchors, scale-by), `cut_boxes.py` (explicit boxes), `despill.py`, `prep_sprite.py`, `pixelize.py` (`--target` = longest side) |
| Palettes and colour | `make_palette.py`, `palette_build.py` (groups, reserved, sub-palettes, coverage), `remap_reserved.py`, `recolor.py`, `measure_hues.py` |
| Finishing | `soften_edges.py`, `art_build.py` (manifest rebuild, 2x sets), `build_atlas.py` |
| Animation | `make_walk_frames.py`, `make_sway_frames.py`, `check_cycle.py`, `make_water_frames.py`, `make_sway_mask.py` |
| Big backgrounds | `stitch_map.py`, `fit_ratio.py` (pad / crop / paste-keep) |
| Audio | `synth_sfx.py` (36 presets), `synth_music.py`, `audio_encode.py` (loudnorm, re-encode) |
| Testing and delivery | `bot_report.py`, `stage_push.py` (sandbox only) |
