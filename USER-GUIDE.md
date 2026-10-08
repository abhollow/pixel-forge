# Pixel Forge — User Guide

Make a retro pixel-art game from scratch with **Claude Code**, **Godot 4** and
**Magnific**. You bring the idea and the taste; Pixel Forge gives Claude the
process, templates and tools to take it from idea to a shipped build.

## 1. Install the tools (once per machine, ~30 min)

| Tool | Windows (PowerShell) | macOS (Terminal) |
|---|---|---|
| Git (Pixel Forge needs it) | `winget install Git.Git` | `xcode-select --install` |
| Claude Code | `irm https://claude.ai/install.ps1 \| iex` | `curl -fsSL https://claude.ai/install.sh \| bash` |
| Python 3 | `winget install Python.Python.3.12` | `brew install python` |
| Godot 4 | `winget install GodotEngine.GodotEngine` | `brew install --cask godot` |
| GitHub CLI *(optional)* | `winget install GitHub.cli` | `brew install gh` |
| ffmpeg *(optional, audio)* | `winget install Gyan.FFmpeg` | `brew install ffmpeg` |

Then the Python libraries: `python -m pip install pillow numpy scipy`
(on Windows, use `py -3 -m pip …` if `python` opens the Microsoft Store).
Open Godot once and install the export templates (*Editor → Manage Export Templates*).

## 2. Connect Magnific (art, music and sound generation)

```
claude mcp add --transport http --scope user magnific https://mcp.magnific.com
```

Start `claude`, type `/mcp`, select **magnific** and finish the sign-in in your
browser (or run `claude mcp login magnific` from the shell). Generation spends your Magnific credits — Claude
tells you the cost before big batches.

## 3. Install Pixel Forge

Inside Claude Code:

```
/plugin marketplace add abhollow/pixel-forge
/plugin install pixel-forge@pixel-forge
```

If it says so, run `/reload-plugins`. Check it with `/plugin list`.
Using the Claude **desktop app** instead? In the Code tab click **+** next to the
prompt box → **Plugins** → **Add plugin**, and add the marketplace `abhollow/pixel-forge`.

**Updating:** `/plugin` → **Marketplaces** → *Update marketplace* (or turn on
*Enable auto-update* there once), then `/reload-plugins`.

## 4. Check your setup

Make an empty folder for your game, open a terminal there, run `claude`, then:

```
/pixel-forge:doctor
```

It checks Python, Godot, git and Magnific and tells you exactly what to fix.

## 5. Make your game

| Step | Type this | What happens |
|---|---|---|
| **Idea** | `/pixel-forge:start a cozy fishing game where…` | Claude talks the idea out with you, researches similar games, finds the gap, cuts scope, writes `docs/concept.md` |
| **Project** | `/pixel-forge:new-project` | Answers a few numbered questions (portrait/landscape, chunky or detailed pixels…) and creates a Godot project tuned for crisp pixel art, plus its docs, tests and git repo |
| **Build** | `/pixel-forge:round` + a numbered list of what you want | Claude builds the batch, tests it, screenshots it, logs decisions, and reports back in your numbering |
| **Art** | `/pixel-forge:art hero walk cycle, ~24 px tall` | Generates options, shows them side by side at game size, cuts the pick into real sprites, drops them in |
| **Play** | `/pixel-forge:playtest feedback 1. too hard 2. …` | You play (open the folder in Godot, press ▶); your notes become numbered fixes |
| **Bugs** | `/pixel-forge:debug the music cuts out after pausing` | Reproduce → measure → fix → a test that proves it |
| **Ship** | `/pixel-forge:ship android` | Release checklist, signed build, store screenshots |

Start every session with **`/pixel-forge:status`** — where you are, what's
next, and any questions waiting on you. Other commands: `scope` (weigh an idea
without building it), `optimize`, `pitch` (one-page pitch), `retro`, and
`tracker-setup` (a dashboard for all your projects).

## Tips

- **Talk in numbered lists.** Claude replies item by item; approve by number ("do 1 and 3").
- **Grey-box first.** Make the game fun as coloured rectangles before spending credits on art.
- **Tell Claude your rules once** — "commit and push after every batch", "ask before adding mechanics" — it records them in your game's `CLAUDE.md`.
- **Your game's `docs/` folder is its memory** — concept, design bible, decision log, status. Any new session picks up where you left off.
- Stuck? Ask in plain words. Every command is just a shortcut for a workflow Claude already knows.

Project home: <https://github.com/abhollow/pixel-forge> · MIT licensed
