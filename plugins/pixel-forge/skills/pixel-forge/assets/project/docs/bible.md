# {{GAME_NAME}} — bible

The locked decisions every prompt, script and line of code references.
Revise in place when a decision changes, and log the change in handoff.md —
a stale bible is worse than none.

**Last verified:** {{DATE}}

## Design

| Field | Locked | Why |
|---|---|---|
| Hook | | |
| Genre loop | | |
| Units | (name them now: run / level / round / wave …) | Naming debt is permanent once code exists |
| Session length | ~5 min per playable unit | Mobile sessions run ~5 min |
| Win / end condition | one condition the player can see | |

## Technical

| Field | Locked | Why |
|---|---|---|
| Engine | Godot {{GODOT_VERSION}} | |
| Viewport | {{VIEW_W}}x{{VIEW_H}} | |
| Pixel scale | {{PIXEL_SCALE}}x | art canvas = viewport / scale |
| Aspect | {{ASPECT}} | keep = painted fixed scenes; expand = tiles/scrolling |
| Orientation | {{ORIENTATION}} | |
| Perspective | {{PERSPECTIVE}} | Mixing perspectives is the classic break |
| Sprite unit | {{CELL}} px | |
| Density | 1x (optionally a 2x detail set later) | |

## Visual rules

| Field | Rule |
|---|---|
| Style anchor | (the chosen mood frame / style image — file + Magnific creation id) |
| Palette | (art/palette.hex, how many colours, sub-palettes, reserved colours) |
| Outline | (1px dark outer edge / none) |
| Light direction | top-left |
| Alpha | hard alpha only — every pixel opaque or gone |
| Semantic colours | (colours that mean something, e.g. "red = the enemy only") |

## Taste

Record the user's preferences as rules the moment they say them, so they are
never relearned. Art, UI, audio, motion. Quote them.

- (e.g. "cozy, not gritty" — or the reverse)
- (e.g. "chunky pixels over fine detail")
- (e.g. "UI minimal; text only for numbers the player acts on")
- (e.g. "sound effects carry the game; music stays under them")

## Layer stack

| z / order | Layer | Notes |
|---|---|---|
| | ground | |
| | world (depth-sorted by foot y) | |
| | effects / life | |
| | night / weather overlays | |
| | HUD (CanvasLayer) | |
| | pause / menus (process always) | |

## Audio

| Bus | Level | Notes |
|---|---|---|
| Music | | sits under SFX |
| SFX | | |
