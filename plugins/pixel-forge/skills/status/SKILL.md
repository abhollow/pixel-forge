---
name: status
description: Where is this game? Stage, exit criterion, next three tasks, open questions — and refresh the docs that drift.
disable-model-invocation: true
---

# Status

Load the `pixel-forge` skill. Then:

1. Read `CLAUDE.md`, `docs/status.md`, the last 3–5 entries of
   `docs/handoff.md`, and `git log --oneline -15`.
2. **Measure the current truth** from the project, not the docs:
   - engine version (`project.godot` `config/features`), viewport and aspect;
   - palette size (`art/palette.hex` line count) and sprite count;
   - smoke test: run it (with `timeout`) and take the check count;
   - uncommitted changes and unpushed commits (`git status -sb`).
3. **Place the stage** using the shared table in the `pixel-forge` skill.
   Progress moves on evidence; it never goes down except for a logged redesign.
4. **Refresh the drift-prone docs:**
   - rewrite the `## Current state` block in `CLAUDE.md`;
   - update `docs/status.md` front-matter (`stage`, `progress`, `next`,
     `blockers`, `open`, `updated`);
   - list any hard rule in `CLAUDE.md` or `docs/bible.md` that the code now
     contradicts — ask before editing a *rule*; just fix stale *facts*.
5. Don't commit unless the standing agreement says to.

## Report

```
Stage: <name> (<progress>%) — exit: <criterion>
Since last time: <2–4 bullets from handoff/git>
Next three: 1. … 2. … 3. …
Open questions for you: 1. … (recommendation)
Blockers: …
Health: N smoke checks pass · <uncommitted/unpushed> · docs refreshed: <which>
```
