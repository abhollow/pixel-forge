---
name: optimize
description: End-game review and optimization pass — parallel read-only reviewers, verified findings, fixes in batches, regression checks, size trim.
disable-model-invocation: true
---

# Optimize

Load the `pixel-forge` skill; read `references/debugging-and-optimization.md`
(the recipe and the mobile 2D checklist) and `references/delivery.md`.

1. **Baseline**: smoke test count, a windowed capture of every level, bot
   numbers if the game has a bot and the user wants them, export size if known.
2. **Review in parallel.** Launch three `code-reviewer` agents at once, each
   with one scope — (a) core loop and systems, (b) events and content,
   (c) UI, audio, shaders and export. Their brief: read-only; grep the whole
   project before calling anything dead (tests use internals); for each
   finding give file:line, how often it runs, cost estimate, minimal fix, and
   risk (none / low / medium); rank; under 1,200 words.
3. **Verify every claim yourself** before acting on it.
4. **Apply in batches**, smoke test between batches. Keep balance-changing bug
   fixes separate and *offer* them with measured effect.
5. **Cleanup**: delete code-drawn fallbacks for art that always exists (switch
   slots to `preload`), unused sprites (grep file names *and* pattern-built
   paths), stray probe scripts and orphan `.uid` files.
6. **Size**: re-encode music (`audio_encode.py reencode`, verify durations),
   export excludes for `tools/*` and `docs/*`, `.gdignore` on raw art.
7. **Regression check**: smoke ×2, windowed captures compared to baseline, bot
   rerun if used. If a number regresses, suspect the harness first (a 60 fps cap
   broke a time-scaled bot) and bisect in a git worktree
   (`git -c core.longpaths=true worktree add`).

## Report

Findings fixed (by area, with measured effect), findings deliberately left
(with why), size before/after, test and regression results, commit status.
