---
name: scope
description: Analysis only — weigh a feature or change with measurements, an options table and a recommendation. Writes no game code.
argument-hint: "[the idea or change to weigh up]"
disable-model-invocation: true
---

# Scope (analysis only)

Question: $ARGUMENTS

**Build nothing.** The user asked for analysis — scope, pros and cons — not a
build. Read freely, measure freely, render comparison images if useful — but
no edits to the game's code, scenes or art.

Load the `pixel-forge` skill.

1. **Restate the idea** and the hook it serves (or threatens).
2. **Measure.** What does the code assume today that this would break? Count
   the places ("~40 places assume the camera never zooms"). If the question is
   visual, measure the reference art instead of guessing — often the
   difference the user sees is spacing or background detail, not sprite size.
3. **Options table:**

   | # | Option | Work | Risk | What it gives | What it costs |
   |---|---|---|---|---|---|

   Include "don't do it" when that's honest, and a cheaper option that gets
   most of the value.
4. **Side-by-side** if taste decides it: build the variants *beside* the game
   (decision image at device resolution), not in it.
5. **Recommendation** with the reason, and **questions** whose answers would
   change it, numbered.
6. Optionally record it in `docs/later.md` or as a draft system doc
   (`docs/templates/system.md`) — ask first.
