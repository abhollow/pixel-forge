# {{GAME_NAME}} — art manifest

What the art must be, and why. This stops settled questions being re-argued and
lets anyone produce a matching asset months later.

**Status / last verified:** {{DATE}}

## Canvas and density

- Viewport {{VIEW_W}}x{{VIEW_H}}, art drawn at {{PIXEL_SCALE}}x (integer scale only).
- HUD/UI exempt from the art grid? (yes/no, and why)

## Per-entity table

Texture size, drawn size and hitbox are three different numbers — conflating
them causes distortion.

| Entity / state | Slot (file pattern) | Texture | Drawn at | Hitbox | Anchor | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

## Measured facts

Numbers that were measured, so the next person measures the same way
(minimum readable size, hue windows for recolour shaders, frame-difference %).

## Generating

Prompt rules for this game; what the model reliably gets wrong here.

## Cutting

The exact command that produced each asset, flags included. Every art transform
is a committed script — never a one-off in a scratch folder.

```
python tools/forge/slice_sheet.py raw_art/... --mode blob --prefix ... --sizes ...
```

## Animation

Cycle construction, thresholds, anchors between sets.

## Backgrounds

Band shares top to bottom, what must stay empty, reserved areas, measured zone lines.

## Fonts and licences

## App icon

Source size, adaptive foreground/background layers, safe zone.

## Rejected approaches

With the measurement or reason that rejected each. The section people skip and
later wish they had.
