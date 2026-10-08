# Setup: Claude, Godot, Python, Magnific

Stage 0. About 30 minutes, once. Run `scripts/doctor.py` first and last — it
finds what's installed, prints the install command for what isn't, and writes
machine paths into a game's `CLAUDE.local.md`. Never install anything without
the user's OK unless they have given standing permission; credentials (GitHub
login, Magnific OAuth) are always theirs to enter.

## Contents
1. Pixel Forge itself
2. Godot 4
3. Python and the scripts
4. Magnific
5. Optional tools: git/gh, ffmpeg, Godot MCP
6. Verify the whole chain
7. Common errors

---

## 1. Pixel Forge itself

**Claude Code (recommended — full workflow):**

```
/plugin marketplace add abhollow/pixel-forge
/plugin install pixel-forge@pixel-forge
```

Update later with `/plugin marketplace update pixel-forge`, then update the
plugin from `/plugin` → Installed. Third-party marketplaces don't auto-update
unless the user turns it on.

The Claude **desktop app** has no `claude` on PATH; its bundled CLI lives at
`%APPDATA%\Claude\claude-code\<version>\claude.exe` if a shell command is needed.

**claude.ai / Claude desktop chat (skill only):** upload `pixel-forge-skill.zip`
(built by `tools/build_skill_zip.py` in the Pixel Forge repo) under Customize →
Skills. Scripts need code execution enabled. The slash commands, agents and
tracker are Claude Code only; in chat, ask for the same workflows by name
("run the round checklist").

## 2. Godot 4

- The **standard** build, not .NET — GDScript is the right choice here.
- Version 4.3 or newer; pick the current stable 4.x and stay on it for the
  project. Record the version in `forge.json` (`godot_version`) so CI matches.
- Windows: `winget install GodotEngine.GodotEngine` puts it under
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\GodotEngine*`. Use the
  **`_console.exe`** for all command-line runs — the plain exe prints nothing.
  Set `GODOT` to its path; `doctor.py` finds it.
- First run: Editor → Manage Export Templates → Download and Install. Templates
  must match the editor version exactly; do it now, not at export time.

## 3. Python and the scripts

Need Python 3.9+ with Pillow and numpy (scipy optional, used if present).

```bash
python --version        # Windows may answer with the Microsoft Store stub
py -3 --version         # the Windows launcher — use this if `python` fails
python -m pip install pillow numpy scipy
```

On Windows, install from python.org and **tick "Add python.exe to PATH"**; or
turn off the Store aliases (Settings → Apps → Advanced app settings → App
execution aliases). If Python can't be installed, `assets/godot/cut_frames.gd`
does keying and frame cutting inside Godot instead.

For someone who has never used a terminal, go one step at a time and wait for
each to succeed: open Terminal → check Python → install → `pip install` →
`python scripts/doctor.py`.

## 4. Magnific

A remote MCP server; OAuth against the user's Magnific account. Generation
draws on the same credit balance as the Magnific web app.

| Field | Value |
|---|---|
| Name | `Magnific` |
| URL | `https://mcp.magnific.com` |
| Auth | OAuth — the user signs in when prompted |

**Claude Code:** `claude mcp add --transport http --scope user magnific https://mcp.magnific.com`, then `/mcp` → select magnific → sign in (or `claude mcp login magnific`).
**claude.ai / desktop:** Customize →
Connectors → Add custom connector → name and URL → sign in.

Confirm with `account_balance`. If it says unlimited isn't active, tell the
user before any paid generation and preflight big batches with `simulate_cost`.

If the connector **disconnects mid-round**, use what already finished, ask the
user to reconnect from connector settings, and stub the remaining slots so the
art drops in later. OAuth window never opens → no trailing slash, no `www.`.
"Couldn't register with the sign-in service" → remove and re-add.

## 5. Optional tools

| Tool | Why | Install (Windows) | Notes |
|---|---|---|---|
| git | Version control | `winget install Git.Git` | `git config --global core.longpaths true` (deep paths break worktrees on Windows) |
| gh | Create/push GitHub repos | `winget install GitHub.cli` | Not on the Bash PATH: `C:\Program Files\GitHub CLI\gh.exe`; call from PowerShell with `&`. The user runs `gh auth login --web`. |
| ffmpeg | Re-encode music, loudness | `winget install Gyan.FFmpeg` | Not on PATH until a restart; `scripts/audio_encode.py` searches WinGet packages |
| Node.js | Godot MCP, other MCP servers | `winget install OpenJS.NodeJS.LTS` | |
| Godot MCP | Launch the game for the user and read its debug output | `claude mcp add godot -- npx @coding-solo/godot-mcp` with `GODOT_PATH` = the console exe | Optional; real work runs through the console exe |

macOS: `brew install --cask godot`, `brew install python gh ffmpeg node`.
Linux: the distro's packages, or the Godot download.

## 6. Verify the whole chain

1. `python "$FORGE/scripts/doctor.py"` — all green.
2. Scaffold a throwaway game into a **short** path (`new_godot_project.py`).
3. Generate one test sprite (count 2, magenta background), download it with
   `fetch_art.py`, cut it with `slice_sheet.py`.
4. `godot --headless --path <game> --import`, then the smoke test.
5. `tools/capture.gd` windowed — the sprite is crisp at phone size.

If that works, every later problem is a content problem, not a setup problem.

## 7. Common errors

| Error | Fix |
|---|---|
| `'python' is not recognized` / opens the Store | `py -3`, or reinstall with PATH ticked |
| `No module named PIL` | `python -m pip install pillow numpy` |
| `externally-managed-environment` | `python -m pip install --user pillow numpy` |
| Godot prints nothing | You ran the GUI exe — use `*_console.exe` |
| Headless Godot never exits | A script error made the debugger wait — wrap runs in `timeout`, grep `SCRIPT ERROR` |
| "Could not find type X" | `godot --headless --path . --import`; if it persists, delete `.godot/` |
| "Filename too long" | `git config --global core.longpaths true`; work from a shorter path |
| `npx skills add` skills vanish | They installed into a scratch session folder — add `-g` |

More Windows traps: `windows-and-shell.md`.
