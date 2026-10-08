---
name: retro
description: Post-mortem a game or milestone and propose concrete improvements back into Pixel Forge itself (lessons, scripts, templates).
argument-hint: "[milestone, e.g. 'shipped v1.0' or 'end of week 1']"
disable-model-invocation: true
---

# Retro

Milestone: $ARGUMENTS

This is how Pixel Forge improves: every game feeds lessons back into the
package. Load the `pixel-forge` skill.

## 1. Gather evidence (read-only)

- `docs/handoff.md` (all entries), `docs/status.md`, `docs/later.md`,
  `docs/assets.md` (credits), playtest reports.
- `git log --format='%ad %s' --date=short` — fix commits are where gotchas live.
- `CLAUDE.md` *How we work* and the bible's *Taste* — corrections the user made.
- `tools/` — scripts written for this game that aren't in Pixel Forge yet.

## 2. Write the post-mortem

`docs/retro-YYYY-MM-DD.md`:

- **Timeline** — stage by stage, with dates.
- **What worked** — keep doing.
- **What cost the most** — time, credits, rework — and the root cause.
- **Corrections from the user** — quoted, dated.
- **Surprises** — engine, tools, Magnific, platform.

## 3. Propose upstream changes

For each lesson, check whether Pixel Forge already says it (read the installed
skill's references). Then write `docs/pixel-forge-proposals.md`:

| # | Lesson (one line) | Evidence (commit/file/quote) | Change to Pixel Forge (file + what to add/fix) | Generic? |
|---|---|---|---|---|

Include new tools worth lifting (path, what to generalise — no hard-coded
paths or game names), template changes, and anything in Pixel Forge that
turned out **wrong**.

## 4. Hand it over

Tell the user how to apply it: open the Pixel Forge repo in Claude Code and
ask to apply `<game>/docs/pixel-forge-proposals.md` — that session follows
the repo's `docs/STEERING.md` (edit, bump version, CHANGELOG, push). Don't edit
the installed plugin copy; it is replaced on update.
