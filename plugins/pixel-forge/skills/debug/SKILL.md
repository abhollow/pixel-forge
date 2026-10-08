---
name: debug
description: Fix a reported bug the disciplined way — reproduce, measure, find the real cause, fix, and prove a new check fails without the fix.
argument-hint: "[the bug report, in the user's words]"
disable-model-invocation: true
---

# Debug

Report: $ARGUMENTS

Load the `pixel-forge` skill; read `references/debugging-and-optimization.md`
and skim `references/godot-gotchas.md` for the area involved (shaders, audio,
physics, UI, pausing).

1. **Restate** the report and what "fixed" will look like to the user.
2. **Reproduce the exact scene** — a capture scenario, a smoke-test section, or
   a probe script. If you can't reproduce it, say what you tried and ask for one
   detail (level, time, what they tapped).
3. **Measure before changing anything.** Count it (how many facing flips per
   minute, how many `SCRIPT ERROR` lines per run), print the state at the
   moment of failure, check the file's loudness, the panel's real width, what
   the end condition actually requires. The symptom often points at the wrong
   place: "quiet music on one level" can be a volume-ducking bug on every
   level; a round that "won't end" can have a hidden second end condition; a
   "layering" bug can be a different object drawn on top.
4. **Grep the logs** for `SCRIPT ERROR` and `SHADER ERROR`. Headless runs can't
   see shader compile errors — use a windowed capture.
5. **Fix the cause**, not the symptom. Then check the same pattern elsewhere —
   a copied shader bug or a missing `queue_redraw()` on a reset path usually
   exists in more than one place.
6. **Add a check that fails on the old code** — put the bug back, watch it fail,
   restore the fix.
7. If the fix changes tuned balance, **offer it** with the measured effect
   rather than imposing it.
8. Smoke test (×2 if random), render if visual, log in `docs/handoff.md`.

## Report

Cause (one line), how you proved it, the fix (files), the new check, anything
else found with the same pattern, and what's committed.
