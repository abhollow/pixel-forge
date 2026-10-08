---
name: pitch
description: Make a one-page pitch (PDF or slide) for a game from real screenshots and numbers pulled from the code.
argument-hint: "[audience and format, e.g. 'one page PDF for a friend']"
disable-model-invocation: true
---

# Pitch

Brief: $ARGUMENTS

Load the `pixel-forge` skill; read the *Pitches and showcase pieces* section
of `references/launch-and-marketing.md`.

**Match the format.** One page means one page. A pitch shows the game; it
doesn't design more of it. If the brief is unclear, ask one numbered question
(format, audience) and default to a one-page PDF.

1. **Facts from the project, not memory**: hook and pitch line from
   `docs/concept.md`; counts from the code (levels, units, upgrades, tracks,
   smoke checks); stage from `docs/status.md`. Nothing made up.
2. **Screenshots**: `tools/capture.gd` scenarios for the 3–4 best moments
   (hook mid-action first), cropped with PIL, nearest-upscaled. If there's no
   playable build yet, concept art — say it's concept art.
3. **Layout**: title + one-line pitch, the hook, 3–4 images with captions,
   "how it plays" in 3 bullets, status/next, contact. The game's palette and
   title font if it has them.
4. **Build**: HTML → headless Chrome `--print-to-pdf --no-pdf-header-footer`;
   render a PNG and check it's exactly one page. (Or the Slides artifact type
   when Artifacts are available and a deck was asked for.)
5. Flag IP if the pitch leans on someone else's game.

## Report

The file (sent), the facts used and where they came from, and the credits
spent if any art was generated.
