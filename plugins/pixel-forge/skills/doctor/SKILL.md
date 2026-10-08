---
name: doctor
description: Check the machine for everything Pixel Forge needs (Python, Godot, git, gh, ffmpeg, Magnific) and refresh a game's vendored forge scripts.
disable-model-invocation: true
---

# Doctor

Load the `pixel-forge` skill; `references/setup.md` has install steps.

1. Run the check (fall back to `py -3` if `python` is the Store stub):

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/scripts/doctor.py"
   ```

2. **Magnific**: call `account_balance`. If the tools are missing, give the
   connector steps from `setup.md` §4. Note whether unlimited is active.
3. **Inside a game folder** (has `forge.json`):
   - `doctor.py --write-local CLAUDE.local.md` to record machine paths;
     make sure `CLAUDE.local.md` is in `.gitignore`.
   - Compare `tools/forge/VERSION` with the plugin version
     (`${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`). If older, list what
     changed (the repo's CHANGELOG if available) and offer to refresh:
     copy `${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge/scripts/*.py` over
     `tools/forge/`, write the new VERSION, run the smoke test and
     `art_build.py --dry-run` if the game uses a manifest.
   - Check `forge.json` `godot_version` against the installed Godot and the CI
     workflow's version.
   - Check `.gdignore` exists in `raw_art/` and `docs/screens/`.
4. **Duplicate skills**: if another pixel-art game skill is installed that
   covers the same ground, mention it — two skills competing for the same
   requests make triggering unpredictable.

Install nothing without the user's OK; for each missing tool give the one-line
install command. Report a green/red table and the fixes.
