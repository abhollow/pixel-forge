---
name: new-project
description: Scaffold a Pixel Forge game — pixel-correct Godot project, forge.json, docs, smoke test, capture harness, vendored tools, git and optional GitHub repo.
argument-hint: "[game name] [folder]"
disable-model-invocation: true
---

# New project

Arguments: $ARGUMENTS

Load the `pixel-forge` skill. Read
`${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/references/godot4-pixel-setup.md`
(resolution and aspect) and `project-docs.md`.

## 1. Settle the bible's technical rows first

Ask as one numbered list, with a recommended default for each:

1. Orientation — portrait or landscape?
2. Resolution and pixel scale — chunky (e.g. 360x640 at 2x) or detailed
   (e.g. 960x540 at 1x)? Pick by the short side and how busy the screen is.
3. Aspect — `keep` for painted fixed-layout scenes, `expand` for tiles and
   scrolling worlds.
4. Perspective — side-on, top-down, or three-quarter.
5. Sprite unit — 16, 24 or 32 px.
6. Folder — a short path (deep paths break Windows tools). Default: next to
   their other games.
7. GitHub — private repo, public, or local only?

## 2. Check the machine

`python "${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/scripts/doctor.py"` — fall
back to `py -3` on Windows. Install nothing without the user's OK.

## 3. Scaffold

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/scripts/new_godot_project.py" "<folder>" \
  --name "<Game Name>" --width W --height H --scale S --aspect keep|expand \
  --orientation portrait|landscape --perspective side|top-down|three-quarter --cell N
```

Then:

- `python tools/forge/doctor.py --write-local CLAUDE.local.md` inside the game.
- `"$GODOT" --headless --path "<folder>" --import`, then run the smoke test.
  Wrap Godot calls in `timeout`.
- If `docs/concept.md` exists elsewhere (from `/pixel-forge:start`), move it in
  and fill the *What the game is* block of `CLAUDE.md` from it.
- Write the technical rows into `docs/bible.md`; set status.md to `design`.

## 4. Git and GitHub

The scaffolder runs `git init -b main`. First commit after the user has seen
the result. For GitHub, confirm visibility, then
`gh repo create <slug> --private --source . --remote origin --push` (on
Windows call `gh` by full path from PowerShell with `&`). The user runs
`gh auth login` themselves if needed.

## 5. Tracker

If the user has the Idea → Launch tracker, add `"tracker": {"id": "<slug>",
"icon": "<path>"}` to `forge.json` so the morning check picks it up.

## Report

What was created (tree), smoke test result, the repo URL, the stage
(Design, exit: bible locked), and numbered next steps.
