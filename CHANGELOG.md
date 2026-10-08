# Changelog

Each entry says what changed and why. Versions follow
`plugins/pixel-forge/.claude-plugin/plugin.json`.

## 1.0.0 — 2026-10-07

First public release.

- **Main skill** `pixel-forge`: the nine-stage arc from idea to shipped with
  exit criteria, working agreements, the round loop, and 24 references —
  concept and research, project docs, production, playtesting, design and
  balance patterns, architecture, Godot pixel setup and gotchas, testing,
  debugging and optimization, delivery, mobile export, Windows/shell notes,
  art direction, the Magnific pipeline, cutting and conversion, large
  backgrounds, animation, audio, launch and marketing, setup.
- **13 commands**: start, new-project, status, round, art, playtest, debug,
  scope, optimize, ship, pitch, retro, doctor — plus tracker-setup.
- **4 agents**: visual-qa, code-reviewer, game-researcher, balance-analyst.
- **SessionStart hook** that resumes a Pixel Forge game from its own docs.
- **Python tools**: doctor, scaffolder, fetch_art, contact_sheet, slice_sheet
  (profile and blob modes), cut_boxes, despill, pixelize, prep_sprite,
  make_palette, palette_build, remap_reserved, recolor, measure_hues,
  soften_edges, art_build (manifest rebuilds with 2x sets), build_atlas,
  make_walk_frames, make_sway_frames, check_cycle, make_water_frames,
  make_sway_mask, stitch_map, fit_ratio, synth_sfx, synth_music,
  audio_encode, bot_report, stage_push. Tested by `tests/run_tests.py`.
- **Godot templates**: grey-box main scene with a tuning block and systems
  registry, Session (settings, buses, atomic saves), pause, audio and
  crossfading music, smoke test, playtest bot and runner, windowed capture,
  motion watch, device preview, a GDScript frame cutter; shaders for sway,
  water, night lighting, replace-colour, spotlight and a heal/corrupt overlay.
- **Project scaffold**: pixel-correct `project.godot`, `forge.json`,
  `CLAUDE.md` working brief, bible, decision log, status (tracker-readable
  front-matter), later list, asset ledger, art manifest, system / level /
  playtest templates, `.gitignore`, `.gdignore`s, CI.
- **Idea → Launch tracker**: a claude.ai artifact dashboard with a daily
  scheduled check of every project folder.
