# Steering Pixel Forge

How this package evolves. Read this before changing anything in the repo —
it is written for the Claude session doing the change as much as for people.

## The loop

```
make a game with Pixel Forge
   → /pixel-forge:retro in the game  →  <game>/docs/pixel-forge-proposals.md
   → open THIS repo in Claude Code: "apply <path to proposals>"
   → edit, test, bump version, CHANGELOG, commit, push
   → users: /plugin marketplace update pixel-forge
```

## Principles

1. **Every rule carries its reason.** State the rule, then one line of *why*
   as a general fact (the engine behaviour, the cost, the failure it prevents).
   If you can't say why, it isn't a lesson yet. Keep the evidence (commits,
   playtest notes) in the proposal, not in the shipped docs.
2. **Framework only.** Lift tools and rules that any pixel game can use. No
   game names, game-specific examples, hard-coded paths, or personal details
   (people, pets, emails, machine paths) in anything under `plugins/`.
   `tools/check_package.py` flags real user paths; keep your own private
   words (your game names, people, places) in a gitignored
   `tools/denylist.local.txt` (one regex per line) and the checker fails on
   any of them.
3. **Defaults, not dogma.** Collaboration rules are defaults; a project's `CLAUDE.md` *How we work* overrides them.
4. **Fix what's wrong, loudly.** When a lesson contradicts the skill, change
   the skill and say so in the CHANGELOG.
5. **Keep the main SKILL.md lean.** It is loaded into context; details belong in
   `references/`. Command skills stay short and point at references.

## Where things go

| Kind of change | File(s) |
|---|---|
| A process/collaboration lesson | `references/collaboration.md`, maybe a working agreement in `SKILL.md` |
| Stage flow, round, exit criteria | `references/production-playbook.md`, `SKILL.md` arc table, tracker `stages.json` (keep all three identical) |
| Godot engine trap | `references/godot-gotchas.md` (rule → evidence → fix) |
| Testing habit | `references/testing-discipline.md` |
| Art / Magnific lesson | `art-direction.md`, `magnific-pipeline.md`, `art-pipeline-lessons.md`, `large-backgrounds.md`, `animation.md` |
| Audio | `references/audio.md`, `scripts/synth_sfx.py` presets |
| Design/balance pattern | `references/design-patterns.md` |
| Code architecture | `references/architecture.md`, `assets/godot/` templates |
| A new tool | `scripts/<name>.py` + a test in `tests/run_tests.py` + a row in `SKILL.md` and the relevant reference |
| A new GDScript template | `assets/godot/` + scaffolder copy list in `scripts/new_godot_project.py` |
| New project doc or doc field | `assets/project/` + `references/project-docs.md` |
| A recurring ritual | a new command skill `skills/<name>/SKILL.md` (`disable-model-invocation: true`) + README + `SKILL.md` command table |
| Tracker | `plugins/pixel-forge/tracker/` |

## Checks before committing

```bash
python tools/check_package.py          # frontmatter, links, script --help, versions
python -I tests/run_tests.py           # Python tools
```

If you changed GDScript templates or the scaffolder, scaffold a throwaway game
into a short temp path and run its smoke test with the console Godot exe.
With the Claude Code CLI: `claude plugin validate .`

## Versioning and release

- `plugins/pixel-forge/.claude-plugin/plugin.json` `version` is the release
  number. Users only receive changes when it changes.
  - patch (1.0.1): fixes, wording, small additions
  - minor (1.1.0): new tools, commands, references
  - major (2.0.0): changed conventions that existing games must migrate to
    (forge.json fields, doc layout, template structure)
- Add a `CHANGELOG.md` entry: what changed and why.
- Commit, push, and tag `vX.Y.Z`.
- Games vendor the scripts in `tools/forge/` with a VERSION file;
  `/pixel-forge:doctor` offers to refresh them. Note breaking script changes in
  the CHANGELOG so that refresh can warn.
- Rebuild the claude.ai zip with `tools/build_skill_zip.py` and attach it to
  the GitHub release (`gh release create vX.Y.Z dist/pixel-forge-skill.zip`).
