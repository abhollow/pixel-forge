#!/usr/bin/env bash
# Pixel Forge SessionStart hook.
# In a Pixel Forge game (forge.json at the project root), remind Claude to load
# the skill and resume from the project's own docs. Silent everywhere else.
# Plain stdout from a SessionStart hook is added to Claude's context.

dir="${CLAUDE_PROJECT_DIR:-$PWD}"

if [ -f "$dir/forge.json" ]; then
  stage=""
  progress=""
  if [ -f "$dir/docs/status.md" ]; then
    stage=$(sed -n 's/^stage:[[:space:]]*//p' "$dir/docs/status.md" | head -n 1 | tr -d '\r')
    progress=$(sed -n 's/^progress:[[:space:]]*//p' "$dir/docs/status.md" | head -n 1 | tr -d '\r')
  fi
  echo "This folder is a Pixel Forge game (forge.json found)."
  echo "Before project work: load the pixel-forge skill, then read CLAUDE.md, docs/status.md and the newest entries of docs/handoff.md, and state the current stage and its exit criterion."
  if [ -n "$stage" ]; then
    echo "docs/status.md says: stage=${stage} progress=${progress:-?}%. Raise any unanswered 'open:' questions listed there."
  fi

  vendored=""
  if [ -f "$dir/tools/forge/VERSION" ]; then
    vendored=$(head -n 1 "$dir/tools/forge/VERSION" | tr -d '\r[:space:]')
  fi
  plugin=""
  if [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json" ]; then
    plugin=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json" | head -n 1)
  fi
  if [ -n "$vendored" ] && [ -n "$plugin" ] && [ "$vendored" != "$plugin" ]; then
    echo "The game's vendored tools/forge is v${vendored}; the installed Pixel Forge is v${plugin}. Offer /pixel-forge:doctor to refresh it."
  fi
elif [ -f "$dir/project.godot" ]; then
  echo "Godot project detected. The pixel-forge skill covers Godot pixel-art work; /pixel-forge:new-project's conventions (forge.json, docs/status.md) are not set up here yet."
fi

exit 0
