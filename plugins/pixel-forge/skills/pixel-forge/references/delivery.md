# Delivery: commits, CI, releases, showcase

How work leaves the session: commits and pushes, repo hygiene, CI, the
release checklist, and showcase artifacts. Export mechanics are in
`mobile-export.md`; how to report a round to the user is in
`collaboration.md`.

## Contents
1. Two environments
2. When and where to commit
3. Commit hygiene checklist
4. Commit messages
5. Pushing
6. Repo hygiene
7. CI
8. Release checklist
9. Tagging a release
10. Showcase artifacts

---

## 1. Two environments

| | Claude Code (local) | claude.ai / Cowork sandbox |
|---|---|---|
| Magnific outputs | Claude downloads each signed URL immediately (curl or urllib; links expire) and uploads references itself (`creations_request_upload` -> PUT -> `creations_finalize_upload`) | CDN blocked (403): the user downloads picks and uploads them |
| Seeing the game | Windowed capture (`debugging-and-optimization.md`) | No Godot window: offline stills; the user plays |
| Git | `git` and `gh` directly | `scripts/stage_push.py`: clone the user's repo, copy the project over it, run the tests in the clone, zip it, hand over one commit command; say when the repo is behind |
| Questions | Numbered options with a recommendation, in text | Same |

Never use modal question widgets in either: they interrupt the user's flow,
tend to get dismissed, and the answer comes back in prose anyway.

## 2. When and where to commit

- **Commit only when the user asks, or under a standing agreement.** Record
  the agreement in `CLAUDE.md` under "How we work". Common agreements:
  commit only on "commit and push" (usually after one to three feedback
  rounds), or "commit and push at the end of every batch".
- **Commit to the user's branch, usually `main`.** Don't open a side branch
  unasked: if the user wants the work on `main`, a side branch only adds a
  merge round.
- **Overnight or unattended runs** (unless the agreement is push every
  batch): work on a branch or leave the changes uncommitted, comment each
  change in code with its playtest reason, and write
  `docs/playtest-YYYY-MM-DD.md` (results table, global changes with file and
  function, per level Changed / Result / Suggest, "suggested, not
  implemented"). End it with "Nothing is committed: review with `git diff`."
- **State the commit status at the end of every report:** "Nothing is
  committed yet" or "Pushed to main as `abc1234`".

## 3. Commit hygiene checklist

Before every commit:
1. `git status` and `git diff --stat`. Know every file you're committing.
   Stage by path or check status after staging: `git add -A --intent-to-add`
   can pick up `override.cfg`.
2. **No secrets:** `git diff --cached -- export_presets.cfg | grep -iE
   "password|keystore"` shows no password values.
3. **Skip line-ending-only diffs.** `project.godot` and `export_presets.cfg`
   often show as modified for CRLF alone:
   `git diff --ignore-cr-at-eol --quiet -- project.godot && echo "line endings only"`.
   Leave those out.
4. **Delete strays:** throwaway probe and `_shots` scripts **and their
   `.uid` files**, `override.cfg`, test saves, APKs, `*.idsig`.
5. **Raw art per policy** (section 6).
6. Smoke test green just before the commit (twice if randomness is
   involved), logs free of `SCRIPT ERROR`.
7. A descriptive subject, a body, and the `Co-Authored-By` trailer the
   session's instructions give.

## 4. Commit messages

Two styles work; use the user's.
- **A round with many fixes:**
  ```
  Playtest fixes and optimizations

  Bugs
  - Pickup and NPC collision boxes were shared by every instance ...
  Performance
  - Hide the screen grade when neutral ...
  Cleanup
  - Drop code-drawn fallbacks for art that always exists ...
  Gameplay
  - Vehicle hitbox 32 -> 28; pickup reach unchanged ...

  Smoke test at <N> checks.

  Co-Authored-By: ...
  ```
- **A batch of features:** one long player-facing subject ("NPCs walk round
  and behind buildings; a calmer playlist; a level-clear fanfare..."),
  details in the body.

## 5. Pushing

- On Windows, `gh` usually isn't on the Bash PATH: full path and PowerShell
  `&` (`windows-and-shell.md`). The user runs `gh auth login --web`
  themselves; never handle their credentials.
- **Retry on a 5xx.** GitHub occasionally returns 500 on push; a background
  loop usually lands it on the next try:
  ```bash
  for i in 1 2 3 4 5 6 7 8 9 10; do git push origin main && break; sleep 60; done
  ```
  Tell the user when it lands.
- Creating a repo or installing `gh` needs the user's OK first.

## 6. Repo hygiene

**Raw art.** `raw_art/` always gets a `.gdignore`.
- Commit it when it's small (tens of MB): the download links expire, so the
  repo may be the only durable copy.
- Gitignore it when it's large (raw generations are a few MB each, with all
  options kept, so gigabytes over a project) and rely on the
  `docs/assets.md` ledger of Magnific creation IDs: `creations_get` issues a
  fresh URL for any original. The signed URL is not durable; the creation ID
  is.

**Renders.** Review renders go to `docs/screens/`, gitignored except
`docs/screens/keep/` (decision images). Committing renders and WAVs every
round bloats the repo fast: hundreds of MB of pack in a week, thousands of
`docs/screens` file changes, music WAVs re-committed on every regeneration.

**Audio** ships as OGG/MP3 at 128 kbps, not WAV.

`.gitignore` essentials:
```
.godot/
override.cfg
CLAUDE.local.md
*.apk
*.aab
*.idsig
docs/screens/*
!docs/screens/.gdignore
!docs/screens/keep/
# raw_art/        <- only when large; then the ledger is mandatory
```
`.gitattributes` (stops CRLF warnings on Windows):
```
* text=auto eol=lf
*.png binary
*.wav binary
*.ogg binary
*.mp3 binary
```
- Commit `*.import` and `*.uid` (`godot-gotchas.md` 1.5).
- Check weight at every milestone: `git count-objects -vH` (`size-pack`).
  Biggest blobs:
  `git rev-list --objects --all | git cat-file --batch-check='%(objectsize) %(rest)' | sort -n | tail -10`.
- Game files never reference the plugin's install path. Forge scripts are
  vendored in `tools/forge/` with `tools/forge/VERSION`. Build scripts that
  hard-code a session-UUID path under `%APPDATA%\Claude\` break on
  reinstall.

## 7. CI

The smoke-test workflow template is in `assets/godot/`. What it must do (a CI
job that can't fail stays green while the game is broken;
`testing-discipline.md` 10):
```yaml
name: Smoke test
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: bash            # -eo pipefail: Godot's exit code survives tee
    steps:
      - uses: actions/checkout@v5
      - name: Install Godot (pinned in forge.json)
        run: |
          V=$(jq -r .godot_version forge.json)
          wget -q "https://github.com/godotengine/godot/releases/download/${V}-stable/Godot_v${V}-stable_linux.x86_64.zip"
          unzip -q "Godot_v${V}-stable_linux.x86_64.zip"
          mv "Godot_v${V}-stable_linux.x86_64" godot && chmod +x godot
      - name: Import first (class cache)
        run: timeout 300 ./godot --headless --path . --import
      - name: Smoke test
        run: |
          timeout 900 ./godot --headless --path . --script res://tools/smoke_test.gd 2>&1 | tee result.txt
          if grep -E "SCRIPT ERROR|SHADER ERROR" result.txt; then exit 1; fi
```
- Pass = exit code 0 from a suite that calls `quit(1)` on failure. Never
  `grep "0 failed"` (it matches "10 failed").
- The engine version comes from `forge.json`, never a literal: a CI job on
  an older Godot than the editor tests something else.
- Check `gh run list` after pushing when CI exists, and say if it's red.

## 8. Release checklist

Run all of it before a build anyone outside the team installs.
1. **Dev flags and placeholders:**
   `grep -rnE "DEV_[A-Z_]+ *:?= *true|TEMPORARY|grey-box|placeholder|working title" scripts scenes`
   is clean; dev-only UI is gated by `OS.is_debug_build()`
   (`architecture.md` 14). A leftover `DEV_* := true` or a "working title -
   grey-box build" label on the menu is the usual miss.
2. **No placeholder art or text:** code-drawn fallbacks gone, art slots
   converted to `preload` consts.
3. **Saves:** survive an app kill, a deleted file and a deliberately
   corrupted file; carry a version; settings survive a save wipe.
4. **Identity:** real package name, `version/name` with the commit hash,
   `version/code` incremented (`mobile-export.md` 1).
5. **Icons** wired, with the smoke check passing.
6. **Size:** export excludes set, music at 128k, unused assets removed, APK or
   AAB size measured (`mobile-export.md` 4).
7. **Tests:** smoke green on CI at the pinned version; logs free of
   `SCRIPT ERROR` / `SHADER ERROR`; a windowed render sweep of every level or
   screen, looked at.
8. **Doc sweep:** `CLAUDE.md` Current state, README counts, level doc
   statuses, file header comments all match the code. A README still naming
   an old engine version and an old check count is the usual miss.
9. **Build:** release template, the user's upload keystore, AAB, from a tagged
   commit (section 9).
10. **Store assets:** screenshots at design resolution, nearest-upscaled;
    feature graphic; privacy declarations (`mobile-export.md`,
    `launch-and-marketing.md`).
11. **A stranger** installs from the store listing and plays without help
    (`production-playbook.md`).

## 9. Tagging a release

Build every release from a tag so the build can be traced and rebuilt.
Without tags, an APK lying around can predate HEAD and nobody can tell.
```bash
git tag -a v1.0.0 -m "First store release"
git push origin v1.0.0          # only when the user has asked to push
```
Set `version/name` to `1.0.0+<short hash>` before exporting.

## 10. Showcase artifacts

Status and showcase pieces are part of delivery; a one-page pitch deck at
the end of a milestone is a common ask.
- **Use real screenshots and numbers taken from the code:** crops from the
  windowed render sweep, and headline counts read from the code (levels,
  upgrades, minutes per level, music tracks, smoke checks). Nothing made up.
- **Match the format asked for.** If the user asks for a basic one-page PDF,
  don't build more. A one-page PDF: write HTML, print it with headless Chrome
  (`--print-to-pdf --no-pdf-header-footer`), render a PNG and check the page
  count.
- **Reference sheets** rendered by script are cheap and useful: a contact
  sheet of every level background (`docs/levels-reference.png`), an
  events-per-level matrix. Keep them in a `.gdignore`d folder so they never
  ship.
- Publish decks and pages with the session's artifact or document tools;
  trailers and store pages are in `launch-and-marketing.md`.
