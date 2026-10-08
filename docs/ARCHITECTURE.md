# How the package fits together

## One repo, three audiences

- **Claude Code users** install the plugin from this repo's marketplace and
  get everything: the main skill, command skills, agents, the SessionStart
  hook and the tracker.
- **claude.ai / desktop chat users** upload `dist/pixel-forge-skill.zip`, built
  from the same main skill folder by `tools/build_skill_zip.py`.
- **Maintainers** (you, and the Claude session you open here) edit, test and
  release per `docs/STEERING.md`.

## Components

```
plugins/pixel-forge/
  skills/pixel-forge/        MAIN SKILL — model-invoked on any game work
    SKILL.md                 role, environment, working agreements, the arc,
                             the round, art/Godot/testing in brief, file index
    references/*.md          detail, read on demand (one topic per file)
    scripts/*.py             tools (Pillow + numpy); every one has --help
    assets/godot/            GDScript templates copied into games' tools/ and scripts/
    assets/shaders/          shader templates
    assets/project/          files the scaffolder copies into a new game
  skills/<command>/SKILL.md  user-invoked workflows (/pixel-forge:<command>);
                             short, they point into the main skill's references
  agents/*.md                subagents for context-heavy or parallel work
  hooks/                     SessionStart: resume a forge game from its docs
  tracker/                   Idea → Launch tracker (page, sync, task template)
```

### Why commands are skills

Claude Code now prefers skills over the legacy `commands/` folder. Each
command skill sets `disable-model-invocation: true`, so it costs no context
until the user types it, and Claude can't trigger it by accident.

### Why games vendor the scripts

A plugin's install path changes on every update and doesn't exist on another
machine or in CI, so a game must never call tools through it. The scaffolder copies
`scripts/*.py` into the game's `tools/forge/` with a VERSION file; the hook and
`/pixel-forge:doctor` notice when it's behind the installed plugin.

### Why the docs live in the game

Auto-memory is keyed by the folder a session started in, and sessions that
start in a scratch folder orphan it. Chat context gets compacted. So the
durable state is files in the game — `CLAUDE.md` (loaded automatically),
`docs/status.md` (machine-readable), `docs/handoff.md` (append-only "why").

### Path variables

- In SKILL.md bodies Claude Code substitutes `${CLAUDE_SKILL_DIR}` and
  `${CLAUDE_PLUGIN_ROOT}` with absolute paths. References are read later with
  the Read tool and are *not* substituted, so they use paths relative to the
  skill folder (`scripts/x.py`) and the `$FORGE` convention from SKILL.md.
- The zip builder rewrites the variables to plain words for claude.ai.

## The shared stage table

`SKILL.md` (arc), `assets/project/docs/status.md` (template) and
`tracker/stages.json` must list the same nine stages with the same ids and
percent bands. `tools/check_package.py` enforces it.
