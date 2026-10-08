# Windows and the shell

Claude Code on Windows 11 runs Git Bash as the Bash tool, with PowerShell
beside it. These traps cost time on every project until they're known.
Run `scripts/doctor.py` first: it finds Python, Godot, git, gh, ffmpeg and
node, checks `core.longpaths`, and `--write-local CLAUDE.local.md` records
the machine paths (gitignored) so later sessions don't rediscover them.

## Contents
1. Python
2. Finding Godot
3. Running Godot from the shell
4. Jobs longer than 10 minutes
5. Editing files safely
6. gh and GitHub
7. git on Windows
8. ffmpeg and other tools
9. Where `user://` lives, and redirecting it for tests
10. Skills, plugins, memory and scratch folders

---

## 1. Python

`python` can be the Microsoft Store stub: it prints "Python was not found;
run without arguments to install from the Microsoft Store" and does
nothing. The `py` launcher usually works when `python` doesn't.
- Try `python`, then `py -3`, then `python3`, and keep the first that
  imports Pillow and numpy:
  ```bash
  for c in python "py -3" python3; do $c -c "import PIL, numpy" 2>/dev/null && { echo "$c"; break; }; done
  ```
- Missing packages: `py -3 -m pip install pillow numpy`.
- A Python tool that calls another uses `sys.executable`, never a literal
  `python3`.
- No Python at all: image work can run as GDScript in headless Godot (frame
  cutters, e.g. `assets/godot/cut_frames.gd`). Godot's `Image.resize` has no
  box filter, so average blocks by hand when shrinking pixel art.

## 2. Finding Godot

Use the **console** build on Windows
(e.g. `Godot_v4.7.2-stable_win64_console.exe`): the plain exe doesn't attach
stdout, so you see no test output.

Look in this order: the `GODOT` env var, `CLAUDE.local.md`, the WinGet
package folder, Program Files, PATH.
```bash
ls "$LOCALAPPDATA"/Microsoft/WinGet/Packages/GodotEngine*/Godot_v*_console.exe
ls "/c/Program Files"/Godot_v*.exe
powershell -NoProfile -Command "(Get-Command 'Godot_v4.7.2-stable_win64_console.exe').Source"
```
- A WinGet install lives at
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_...\`.
  If only the plain exe turns up (e.g. `C:\Program Files\Godot_v4.7.2-stable_win64.exe`),
  look for `_console.exe` beside it.
- Every script and command uses `G="${GODOT:-godot}"`. Never hard-code a
  machine path in a game's tools: a runner script with a literal path breaks
  on every other machine.
- Cache what you found. `$TEMP/godot_path` is lost with the temp folder;
  `CLAUDE.local.md` (written by `scripts/doctor.py --write-local`) is the
  durable place.
- The Godot MCP is optional. It is useful to check that a project loads and
  to launch the game window for the user (`run_project`, then
  `get_debug_output`); all real work runs through the console exe. If you
  wire it, point `GODOT_PATH` at the console exe.

## 3. Running Godot from the shell

- **Wrap every call in `timeout`.** A GDScript error makes headless Godot
  wait in the debugger forever, so a typo looks like a hang (a screenshot run
  "hangs" on a leftover reference until it's wrapped).
  ```bash
  timeout 600 "$G" --headless --path . --script res://tools/smoke_test.gd 2>&1 | tee smoke.log
  grep -cE "SCRIPT ERROR|SHADER ERROR|Parse Error" smoke.log
  ```
- **Kill strays by exe name**, the console exe only, so the user's editor
  survives (Git Bash needs the doubled slashes):
  ```bash
  taskkill //F //IM Godot_v4.7.2-stable_win64_console.exe
  ```
- Windowed runs (capture, watch) open a real window and take focus; say so
  before running them while the user is at the machine.
- Bots and benchmarks: `--max-fps 0` (`godot-gotchas.md` 6.4).

## 4. Jobs longer than 10 minutes

A Bash tool call is capped at 600 s. Smoke x2 plus a screenshot suite plus
bot runs outgrows that within days, and a full bot pass of 10 parallel Godot
processes takes 6-10 minutes on its own.
- Start the job with `run_in_background`, writing to a log or output file
  that ends with a marker (`echo ALL_DONE`).
- Wait for it with an until-loop on that file, itself in the background (or
  in the session's monitor tool), never with chained foreground sleeps:
  ```bash
  until grep -q ALL_DONE out/run.log; do sleep 20; done; tail -5 out/run.log
  ```
- Keep working on something else meanwhile, and read the results when
  notified.

## 5. Editing files safely

The Bash tool mangles inline scripts: heredocs lose backslashes (`\n` inside
Python strings, GDScript line continuations) and tabs, and GDScript is
indented with tabs.

**Never edit by line number.** Line-number `sed` edits break code again and
again: a duplicated call, a function inserted inside another, a literal `\n`
written into scripts, functions squashed onto one line, heredoc patterns
that silently don't match.

- One change: the Edit tool (exact old text -> new text).
- Many changes in a big file: write a Python script **with the Write tool**
  (into the scratchpad, not a heredoc) and run it. Every replacement asserts
  its anchor exists exactly once, so a miss fails loudly and nothing is
  written:
  ```python
  import sys
  path = sys.argv[1]
  s = open(path, encoding="utf-8", newline="").read()
  def rep(old, new, count=1):
      global s
      n = s.count(old)
      assert n == count, f"anchor found {n}x, wanted {count}: {old[:60]!r}"
      s = s.replace(old, new)
  rep("func _reset() -> void:\n", "func _reset() -> void:\n\t_clear_fx()\n")
  open(path, "w", encoding="utf-8", newline="").write(s)
  ```
  This holds up for scripts thousands of lines long, edited daily.
- Re-read the edited region (or run `--check-only` / the smoke test) after a
  scripted edit.

## 6. gh and GitHub

- `gh` installs with `winget install GitHub.cli` (ask first) to
  `C:\Program Files\GitHub CLI\gh.exe`, which is **not on the Bash PATH**.
  - Bash: `"/c/Program Files/GitHub CLI/gh.exe" run list --limit 5`
  - PowerShell: quote the path and use the call operator:
    `& "C:\Program Files\GitHub CLI\gh.exe" run list --limit 5`.
    Without `&` it's a parse error.
- **The user authenticates:** `gh auth login --web` is theirs to run.
- **Git Bash rewrites leading-slash arguments into Windows paths:**
  `gh api /repos/o/r` becomes `C:/Program Files/Git/repos/o/r`. Use
  `MSYS_NO_PATHCONV=1 gh api /repos/o/r`, drop the leading slash
  (`gh api repos/o/r`), or run it from PowerShell.
- Record the gh path in `CLAUDE.local.md`.

## 7. git on Windows

- **Long paths:** `git worktree remove` can fail with "Filename too long".
  Use `git -c core.longpaths=true ...`, or set `git config core.longpaths
  true` once (doctor checks it).
- **Short working paths.** Cloud-synced Desktop folders and scratch folders
  are deep. Video renders and git tests can fail under a deep scratch folder
  and work once moved to a short temp dir (`%TEMP%\pf-tmp`). Put bisect
  worktrees at a short path beside the repo.
- **Line endings:** `.gitattributes` with `* text=auto eol=lf` (`delivery.md`).
  Files that differ only by CRLF stay out of commits.
- **Scripts write LF.** Open files with `newline=""` in Python (as above) so
  nothing converts line endings behind your back.

## 8. ffmpeg and other tools

- **ffmpeg** (for `scripts/audio_encode.py`): `winget install Gyan.FFmpeg`
  after asking. It isn't on PATH until a restart; find it at
  `"$LOCALAPPDATA"/Microsoft/WinGet/Packages/Gyan.FFmpeg*/*/bin/ffmpeg.exe`
  and record the path in `CLAUDE.local.md`. `ffprobe` sits beside it.
- **Node** (for `npx` tools and the Godot MCP): via winget.
- **Chrome** prints HTML to PDF headless (`delivery.md` 10).
- **The Claude desktop app** puts no `claude` on PATH; its bundled CLI is at
  `%APPDATA%\Claude\claude-code\<version>\claude.exe`.
- Ask before installing anything unless the user has granted standing
  permission (record it in `CLAUDE.md`).

## 9. Where `user://` lives, and redirecting it for tests

`user://` is `%APPDATA%\Godot\app_userdata\<application/config/name>`: the
project's **display name**, not its folder. A backup taken of a folder named
after the project directory backs up nothing, and renamed projects leave
stale folders behind. Ask Godot instead of guessing:
```gdscript
print(ProjectSettings.globalize_path("user://"))
```
Redirect unattended runs so they never touch the player's save. The bot
runner writes an `override.cfg` at the project root and removes it on exit:
```bash
printf '[application]\nconfig/use_custom_user_dir=true\nconfig/custom_user_dir_name="%s"\n' "MyGameBot$$" > override.cfg
trap 'rm -f override.cfg' EXIT
```
- Every Godot process started on the project reads `override.cfg` while it
  exists, so two runners at once race on it. Run one runner at a time, or
  give the smoke test its own save path instead (`Session.save_path`,
  `testing-discipline.md` 2).
- `override.cfg` is in `.gitignore`, and never in an export.

## 10. Skills, plugins, memory and scratch folders

- `npx skills add <source> -g`: without `-g` the skill installs into the
  session folder and vanishes with a scratch session.
- **Auto-memory follows the folder the session started in.** A session that
  begins in a scratch workspace and then changes directory into a project
  saves its memory notes under the scratch key; sessions opened in the
  project never load them. Put durable rules (save safety, autonomy,
  "no bot runs unless asked") in the project's `CLAUDE.md` and
  `docs/status.md`, and start sessions in the project folder.
- Create scheduled tasks from the project root, never from a scratch
  session (the task runs in its creation folder).
- User-level hooks change behaviour. A SessionStart hook that injects a
  persona (e.g. "delete over add") shapes decisions without saying so. If
  your instincts run against the brief, check for one.
