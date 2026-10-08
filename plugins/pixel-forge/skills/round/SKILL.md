---
name: round
description: Run one agreed batch end to end — build, test, render and look, log the decision, update docs, commit per agreement, numbered report.
argument-hint: "[the batch, or leave empty to use the user's last numbered list]"
disable-model-invocation: true
---

# Round

The batch: $ARGUMENTS

Load the `pixel-forge` skill. Read the game's `CLAUDE.md` *How we work*
section — it says what needs asking and whether to commit/push.

## 0. Agree

If the batch isn't already agreed as a numbered list, propose one (each item a
line, with your recommendation) and wait. Inside an agreed batch, don't check
in per step. **New mechanics or rules need a yes even mid-batch**; visual-only
polish doesn't. If a request would break the game's core constraint, say so
before building.

## 1. Build

- Numbers go in the tuning block with a dated comment.
- Visuals go in the read-only life/effects layer (never write rules from it).
- New art goes through an art slot with a code-drawn fallback.
- Multi-line GDScript edits: use the Edit tool or an anchor-asserting script —
  never line-number `sed`.

## 2. Test

- `"$GODOT" --headless --path . --import` if art or a `class_name` was added.
- Smoke test with `timeout`; twice if randomness is involved.
- Each fix gets a check; prove it fails without the fix.
- Bots only if the agreement or the user says so.

## 3. Look

Render every scene the batch touched with `tools/capture.gd` (windowed),
grep the log for `SCRIPT ERROR` and `SHADER ERROR`, and read the images. For
more than ~6 images, hand them to the `visual-qa` agent with what to check.
Fix what reads badly before reporting.

## 4. Log

- Append a dated entry to `docs/handoff.md`: what changed (knobs, files), why,
  rejected alternatives, who decided, tests, known limits.
- Update `docs/status.md` front-matter, `docs/assets.md` (new art + credits),
  and the `CLAUDE.md` *Current state* block.

## 5. Deliver

- Commit/push per the agreement (descriptive subject; body by Bugs /
  Gameplay / Art / Cleanup; "Smoke test at N checks"). Push failures with a 5xx
  get a retry loop. If the agreement is "only when asked", leave it and say so.
- Send the key renders as files with captions.

## Report

Mirror the user's numbering. Per item: what changed, the knob and file, how it
was verified. Then: test count · bot result (if run) · credits spent ·
commit/push status · "Worth your eye" · decisions you may want to override ·
open questions.
