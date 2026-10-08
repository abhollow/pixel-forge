# {{GAME_NAME}}

A Godot {{GODOT_VERSION}} pixel-art game, built with Pixel Forge.

## Run

Open the folder in Godot {{GODOT_VERSION}} and press Play, or:

```bash
godot --path .
```

## Test

```bash
sh tools/run_tests.sh                       # import + smoke test, with a timeout
```

or by hand:

```bash
godot --headless --path . --import          # after pulling or adding art
godot --headless --path . --script res://tools/smoke_test.gd
```

Renders for review: `godot --path . --script res://tools/capture.gd ++ scenario=main`
(`++ list=1` lists scenarios).

The smoke test uses its own save path and never touches your real save.

## Layout

- `scenes/`, `scripts/` — the game
- `art/` — game-ready art (rebuilt from `raw_art/` by `tools/forge/art_build.py`)
- `raw_art/` — Magnific originals; **not disposable** (signed links expire). Ignored by Godot via `.gdignore`.
- `docs/` — concept, bible, status, decision log, asset ledger
- `tools/` — tests, capture harness, vendored forge scripts

If sprites show as coloured rectangles, run the `--import` command above (or
delete `.godot/` and reopen the editor).
