---
name: art
description: Take one asset or a batch through the art pipeline — generate with Magnific, download, compare at game scale, cut, convert, import, render and log.
argument-hint: "[what to make, e.g. 'wolf run cycle, 4 frames, ~24px tall']"
disable-model-invocation: true
---

# Art

Brief: $ARGUMENTS

Load the `pixel-forge` skill. Read, in its `references/` folder,
`art-direction.md`, `magnific-pipeline.md` and `art-pipeline-lessons.md`
(and `animation.md` for frames, `large-backgrounds.md` for maps/backgrounds).
Tools are in `tools/forge/` inside the game, or
`${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/scripts/`.

## 1. Before generating

- Is the **mechanic built** with an art slot? If not, build that first (or at
  least the slot) so the pick drops in.
- Is art direction locked (style anchor + bible)? If not, start with 4 mood
  frames instead.
- **Code instead?** Motion under ~20 px, varied effects, recolours, things the
  game animates — say so and skip generation where code wins.
- **Reuse?** Check `docs/assets.md` for existing sprites to tint, scale or flip.
- Check `account_balance`; state the planned spend (models/costs in
  `magnific-pipeline.md`); `simulate_cost` for big batches.

## 2. Generate

- Model and size per `magnific-pipeline.md` (sheets: Nano Banana Pro at 2k).
- Flat `#FF00FF` background; `#00FF00` for pink/red/orange subjects.
- Prompt: style-anchor line, the bible's perspective and light, the display
  size ("shown about 24 px tall, so extremely bold and simple"), "each item
  fully isolated with wide gaps", per-frame poses for animation, facing RIGHT,
  what must be empty, "no text, no ground, no scenery".
- `count` 2 once anchored, 4 when exploring. Pass the style anchor as a
  `style` reference; family members as an `image` reference.

## 3. Download and compare

- In Claude Code, download **immediately** (links expire):
  `python tools/forge/fetch_art.py batch.txt --batch bNN` → `raw_art/bNN/` + ledger rows.
  In the claude.ai sandbox, ask the user to download and upload the pick.
- Build a decision image at **game scale** on the real background beside a
  known sprite (`contact_sheet.py`). Pick with reasons, or send it to the user
  with your recommendation if it's a taste call.

## 4. Cut and convert

- `slice_sheet.py` (`--mode blob` for loose sheets; `--shared-box` for frames),
  key from raw, despill inside the mask, hard alpha, box downscale, explicit
  `--target` (longest side). Sub-palette only if the game uses one.
- Add the line to `art/manifest.json` so `art_build.py` can rebuild it.
- Frames: `check_cycle.py` — duplicates under ~12% different get pose A mirrored.

## 5. Into the game

`"$GODOT" --headless --path . --import`, then `tools/capture.gd` for the scenes
that show it. Read the render. Size against neighbours; expect "too small" →
"too big" → in between.

## 6. Log and report

`docs/assets.md`: file, creation id, model, prompt ref, cutter; credits table.
Report: the render, what you picked and why, credits spent, how to swap to
another option (one manifest line), anything you couldn't judge.
