---
name: start
description: Start a new game from an idea — talk it out, research comparables, cut scope, and write docs/concept.md.
argument-hint: "[the idea, in a sentence or two]"
disable-model-invocation: true
---

# Start a new game

The idea: $ARGUMENTS

Load the `pixel-forge` skill if it isn't loaded, then read
`${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/references/concept-and-research.md`
and `collaboration.md` in the same folder. Stage: **Idea → Concept**. Exit
criterion: a pitch the user can say in one breath, a named hook, comparables,
and a scoped feature list in `docs/concept.md`.

## Steps

1. **Talk it out.** If no idea was given, ask for it. Then ask, as one short
   numbered list (not a pop-up):
   1. What is the moment — the most satisfying five seconds of play?
   2. Which games is it like, and what do you love in them?
   3. How long is a session, and why come back tomorrow?
   4. What's the constraint — hours a week, deadline, platform?
   Collect; don't fix the idea yet. Quote the moment back.
2. **Research — actually search the web.** 3–5 comparables by *mechanic*, not
   theme; what players praise and complain about; how crowded the niche is;
   monetisation norms if mobile. Report concretely: "these four do X; none do Z."
3. **Find the gap and sharpen the hook** — recombine, subtract, or specify.
   Offer 2–3 shapes, each one line, with your recommendation.
4. **Cut scope.** Sort features into Hook / Support / Later / Cut. Assume the
   first list is 5–10x too big and say so kindly. Check it against their hours.
5. **Flag IP** if the idea leans on someone else's game, names or characters.
6. **Write `docs/concept.md`** (template:
   `${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/assets/project/docs/concept.md`).
   If no project folder exists yet, write it in the current folder and offer
   `/pixel-forge:new-project` next.
7. Optionally offer **4 mood frames** (one Magnific call, count 4) to make the
   look concrete — say the credit cost first.

## Report

The one-line pitch, the hook, the comparables table, the scope table, the two
biggest risks, and numbered next steps with a recommendation (usually: lock
the bible, then scaffold).
