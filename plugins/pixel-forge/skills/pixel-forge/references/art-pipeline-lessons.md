# Art pipeline lessons

What goes wrong turning Magnific output into game sprites, and how to avoid
it. Read before cutting any sheet.
Complements `magnific-pipeline.md` (generating), `pixel-conversion.md` (the
scripts) and `animation.md` (frames).

Commands use `python "$FORGE/scripts/..."`; inside a game call the vendored
copy in `tools/forge/`. If `python` is the Windows Store stub, use `py -3` or
`python3`. Flags shown are the common ones; each script's `--help` is the
authority.

## Contents
1. Where the art comes from
2. Keying
3. Despill, and the order that matters
4. Cutting sheets: profile, blob, boxes
5. Glows, reserved colours and sub-palettes
6. Recolour, don't tint
7. Thin features and edges
8. Scale and anchors
9. Size against each other; readability
10. Measure, don't eyeball
11. Verify by looking
12. Art slots and the import step
13. Record every transform

---

## 1. Where the art comes from

In Claude Code you download every option yourself into `raw_art/<batch>/` and
log it in `docs/assets.md`; in the claude.ai sandbox the user downloads the
pick and uploads it (`magnific-pipeline.md` §1). Either way:

- Keep **all options**, not just the pick; later re-cuts start from them.
- `raw_art/` has a `.gdignore` so Godot never imports it. Commit it if small;
  gitignore it when large and rely on the creation-id ledger
  (`magnific-pipeline.md` §2).

## 2. Keying

- **Magenta `#FF00FF` by default. Green `#00FF00` for pink, red or orange
  subjects.** A magenta key eats a pink subject; buildings with red cracks or
  banners go on green.
- **Key by ratio, not exact colour.** A "magenta" background can measure
  `(252, 52, 252)`. The cutter keys `g < 0.62*r and g < 0.62*b`.
- **Key only background connected to the border.** Every subject is walled in
  by its outline, so anything enclosed is subject whatever its colour. A
  colour-only rule punches holes in a hot-pink shirt. Never widen the colour
  rule to fix a miss.
- **Corner-colour key** when a sheet comes back on some other flat colour (for
  example flat dark rose): `--key corner`.
- **Do colour maths in float32.** int16 overflows and keys white as pink.
- **Key to transparent BLACK before resizing.** A transparent pixel still
  carries its RGB into the resize average; transparent magenta leaves a pink
  fringe.
- **Clean the fringe after downscaling** (`--clean-fringe`), never on a subject
  coloured like the key.
- **Refill pinholes.** Downscale-then-threshold can punch small holes through
  solid areas; enclosed specks under about 6 px are refilled. Sweep for
  enclosed transparency afterwards, but inspect: gaps between a tool handle and
  a body are real.

## 3. Despill, and the order that matters

**Symptom:** walls come back `403040` instead of brown-grey, and the palette
then snaps those purples to heather. The key colour has cast into the shadows.

**Despill:** where `min(r, b) > g`, pull red and blue down by the excess
(magenta key); for a green key, pull green down to `max(r, b)`. Leave pure key
pixels alone.

**Order:**

1. Key the **raw** sheet, magenta plus its darker shadow.
2. Despill **only inside the kept mask**.
3. Cut.
4. Convert (`pixel-conversion.md`).

Despilling first turns magenta drop shadows grey; they then count as sprite,
bridge the gaps, and neighbours merge (typical when the prompt asked for "its
own small ground shadow"). Cutting shadowed sheets raw with no despill at all
is a workaround; the packaged cutter does both in the right order:

```bash
python "$FORGE/scripts/slice_sheet.py" --src raw_art/b07/kit_a.png --prefix kit \
    --mode blob --sizes 105x82,105x75,... --despill --out-dir art/sprites   # one size per item
python "$FORGE/scripts/despill.py" in.png -o out.png     # standalone, on already-keyed art
```

## 4. Cutting sheets: profile, blob, boxes

| Sheet | Cutter | Why |
|---|---|---|
| Clean grid, rows well apart | `slice_sheet.py` (profile mode, default) | Splits on row and column projections |
| Rows overlap, items have loose bits (ladders, smoke), baked shadows | `slice_sheet.py --mode blob` | Profile mode merges overlapping rows |
| Animation frames | `slice_sheet.py --shared-box` | One box for every frame (`animation.md` §3) |
| Mixed sizes, glows, loose effects | `cut_boxes.py` with a JSON box file | Names and boxes are game data |

- **Profile mode:** column gap (`--gap`) and row gap (`--row-gap`) are
  independent. A splayed stride needs a large column gap, which would also
  merge grid rows. Spans under about 4% of the sheet are dropped as specks.
- **Blob mode:** grow each blob (`--grow`, about 12 px) so loose parts stay
  attached, label, drop specks (0.2% of the area), order by row centre,
  **assert the count matches the sizes given**, then cut a tight box around
  the real pixels (not the grown blob).
- **Filter specks before projecting** (`--speck`). A stray speck taken for an
  extra row shifts every frame down.
- **Look at the cut before trusting it:** `--debug-sheet docs/screens/cut.png`
  writes the sheet with numbered boxes; `--expect N` asserts the count.
- **Animation rows:** `--rows 2 --shared-box` (or split two-row sheets with
  PIL first).
- **Explicit boxes** (`cut_boxes.py`): a JSON file of items, each with
  `sheet`, `box` `[x0, y0, x1, y1]`, `size`, and optional `mode` (`body` =
  largest piece only, `all`, `glow` = pink glow recoloured warm white), `key`
  (`magenta`, `green`, `corner`, `hue`, `auto`), `unblue`, `palette`. Measure
  each box once on the raw sheet.

```bash
python "$FORGE/scripts/cut_boxes.py" art/boxes/icons.json --out-dir art/sprites --debug-dir docs/screens
```

## 5. Glows, reserved colours and sub-palettes

- **Glows blend with the key into pink.** Key glowing art by hue (for example
  `(r > g+28) & (b > g+28)` counts as halo on a title) and recolour glows to
  warm white before locking. Otherwise the pink snaps to a reserved red.
- **Remap reserved colours after conversion.** Any pixel that lands on a
  semantically reserved colour gets remapped (for example stray reds turned
  into the outline colour). It edits in place unless given `-o` / `-O`;
  `--hue LO-HI` covers art that was never palette-locked, `--x-range` spares a
  part that may keep the colour.
  ```bash
  python "$FORGE/scripts/remap_reserved.py" art/sprites/*.png --palettes art/palettes.json \
      --to nearest --palette art/palette_build.hex
  ```
- **Nearest-colour quantising is only as good as the candidates.** Give each
  asset class its own sub-palette (`palette_build.py`, `pixel-conversion.md`
  §5). Typical cases:
  - A grey rain cloud on dark slate snaps to tan and yellow-green, because
    the palette maps mid greys to yellow-greens. Fix: a greys-only
    sub-palette, and quantise the icon's interior to greys before locking.
  - Blue-leaning greys snap to green-greys and speckle, because the palette
    has no blue-greys. Fix: neutralise them to plain grey first. Slate that
    leans blue in a game where blue is reserved becomes warm grey.
  - Mid-greys collapse where the palette jumps from `8f918a` to `2d2a2d`.
    Fix: lift them.
  - Cool grass shadows snap to blue-grey stone. Fix: quantise land and water
    separately.
  - A straw roof comes out pinkish. Fix: check the mapping on a preview.
- **None of this is mandatory for coherence.** A game can ship with almost no
  sprites on its palette and still read as one (`art-direction.md` §5). Use
  sub-palettes where colour carries meaning or quantising cleans up strays.

## 6. Recolour, don't tint

- **Multiplying muddies.** A green plant multiplied by brown to make a rotting
  variant looks muddy (and brown may already mean something). A shader
  mapping the greens onto a new ramp by brightness keeps it bright and
  distinct.
- **Check the new colour against the ground it sits on.** Gold vanishes into
  pale sand.
- **Replace Color** (`assets/shaders/replace_color.gdshader`, the image-editor
  model): sample hue, full radius, fade radius, saturation and value gates, a
  region exclusion. Measure the hue window first: with a vest at 50–58° and a
  bag at 60–73°, a 45–72° window turns the bag red too.
- **In a canvas shader, `COLOR` already holds texture × modulate.** Start from
  `vec4 c = COLOR;`. Sampling `TEXTURE` again and multiplying by `COLOR`
  squares every channel (skin goes deep red). See `godot-gotchas.md`.
- **Offline recolour of a painting** keeps its measured layout; regenerating
  would not. The usual pass shifts greens and olives toward fresh green and
  leaves wood and stone alone. `recolor.py`'s defaults are that pass (hues
  38–150° pulled toward 102°); other hues are untouched bit for bit:
  ```bash
  python "$FORGE/scripts/recolor.py" raw_art/b02/backdrop.png -o raw_art/clean/backdrop_lush.png
  python "$FORGE/scripts/recolor.py" tunic.png -o tunic_red.png --hue-range 45-72 --toward 0 --pull 1 --sat-gain 0
  ```

## 7. Thin features and edges

- **Thin features vanish on downscale** (legs, rope, a long bird neck at 24
  px). Widen the alpha before shrinking, and fill the background with the
  outline colour first, or the widened edge picks up the key (green legs on a
  green-keyed sheet). Or cut bigger (24 → 30 px often saves a thin neck).
- **Hard alpha is the default**: every pixel fully opaque or gone. Semi-
  transparent edges show as a fringe with nearest filtering.
- **The one deliberate exception: sit world sprites into painted ground.**
  `soften_edges.py` makes the silhouette rim half-transparent and pushes it
  toward the ground colour (for example rim alpha 150, 35% toward the
  ground), combined with code-drawn foot shadows and a ground decal. **Feather
  inward only**, or a coloured halo appears.

```bash
python "$FORGE/scripts/soften_edges.py" art/sprites_hd/tree_*.png --ground 5f7a4c --alpha 150 --toward 0.35
```

`--ground` is the hex colour of the ground the sprite stands on. It edits in
place unless given `-o` / `-O`, and running it twice changes nothing.

## 8. Scale and anchors

- **Scale from the subject, not the box.** A creature whose dig frames carry
  dust is scaled by its body width (measured by the body colour), because the
  dust would shrink it if the whole box were measured
  (`slice_sheet.py --scale-by colour:HEX --feature-px P`). A figure holding a
  tool has a bigger box than one with empty hands: pick the plainest pose as
  the reference and scale every box from it (`--scale-by ref:N`).
- **One scale per frame set** (`--scale-by set` or `--shared-box`). A bird
  uses one scale for flying and perched, set by the perched width.
- **Choose anchors deliberately** (`--anchor bottom` for feet on the ground,
  `right` for beak-aligned) and keep them the same between sets. Details and
  the take-off drop bug: `animation.md` §3.
- **Keep the pixel scale exact.** Slice so the sprite draws at exactly the
  game's scale (55 px wide drawn at 110 = 2x), never stretched. Record
  **texture size, drawn size and hitbox** as three separate numbers; art can
  be bigger than the hitbox (for example a 24x24 texture drawn at 48 over a
  24x24 hitbox).

## 9. Size against each other; readability

- **Render new art beside existing art at game scale before accepting** (the
  hero, a typical prop, the new sprite). Sizes judged in isolation are wrong.
- **Expect size feedback both ways:** "double it", then "still too small",
  then "back to the original size". With sizes in `art/manifest.json`, each is
  a one-line edit and a rebuild (`pixel-conversion.md` §6).
- **Readability beats realism.** A small creature may need to be a third of a
  person's height to be spotted mid-game; 9 px arrows, 1 px sparks and small
  speech bubbles are invisible at game scale. Check at 1x; use 2x close-ups
  only to inspect detail.
- **Floors:** 24x24 is the smallest readable person at half density; 16x16
  reads as a coloured blob. Below about 20 px, poses stop reading and code
  motion takes over (`animation.md` §6).

## 10. Measure, don't eyeball

- **Hue histograms.** Measure sprites before tinting or recolouring them. A
  typical crowd sprite: pink clothing 320–350°, skin 10–30°, red shorts
  350–2°. Flushed faces sit in the red band, so a tint should exclude red
  above about 32% of the sprite's height. Measure even 17x24 sprites; don't
  guess. `measure_hues.py` prints the histogram and its clusters (the windows
  for a recolour shader); `--region x0,y0,x1,y1` measures one part of each
  sprite, `--plot` writes a histogram image:
  `python "$FORGE/scripts/measure_hues.py" art/sprites/npc_*.png --region 4,8,20,18 --plot docs/screens/hues.png`
- **Count pixels to answer "is it there?"**: leaf-colour pixel counts, the
  number of arrows in flight.
- **Measure the gap to the target** (`art-direction.md` §2).
- **Pixel-diff motion** and check frame cycles (`animation.md` §4).

## 11. Verify by looking

In Claude Code you can render the real game yourself. Every art change gets a
render of the real sprites in the real scene at game scale before you call it
done. That catches sprites too small (and then merged into one mass), a flood
that looks like a road with lane markings, a sign too small to read, a large
object hidden under the HUD, and a shader that fails to compile.

- **`assets/godot/capture.gd`** (copied into the game's `tools/`): a windowed
  SceneTree capture that boots the scene, runs scenario hooks, unpauses every
  frame, waits, grabs and builds a contact sheet. Run it **without**
  `--headless`, wrapped in `timeout`, then `Read` the PNG:
  ```bash
  G="${GODOT:-godot}"
  timeout 300 "$G" --path . --script res://tools/capture.gd 2>&1 | tee docs/screens/capture.log
  grep -E "SHADER ERROR|SCRIPT ERROR" docs/screens/capture.log
  ```
- **Headless runs cannot catch shader compile errors.** A level can render
  solid white while the headless smoke test passes; only the windowed log
  shows `SHADER ERROR`. Every shader edit gets a windowed render.
- **Harness traps that each cost a round** (more in `testing-discipline.md`):
  a paused game doesn't redraw (queue a redraw on every layer, wait frames and
  `frame_post_draw`); a paused clock means time-based effects never appear
  (drive time by hand); effects hidden behind the HUD; shots that fall at night
  by accident (pin the time of day); the game's own focus-loss auto-pause
  (unpause every frame).
- **Phone view without a phone:** `device_preview.gd` (a SubViewport at device
  size with `size_2d_override`). **Motion:** `watch.gd` (a frame every few
  seconds) catches walkers inside walls and leftover effects that stills miss.
- **Protect the context.** Screenshots add up to hundreds over a project and
  fill the context. For a big batch of shots, have a subagent read them
  against a checklist and return text.
- Delete throwaway capture scripts **and their `.uid`** (a stray
  `_shots.gd.uid` is easy to commit by accident).
- Sandbox: no window. Composite the sprites onto the background offline and
  ask the user to check in game.

## 12. Art slots and the import step

- **Build the mechanic before the art.** Every art-dependent object gets a
  code-drawn placeholder and an art slot: if the texture exists, draw it;
  otherwise draw the placeholder. The art drops in with no code change, and a
  smoke check asserts it loaded.
- **Load by name:** `ResourceLoader.list_directory("res://art/sprites/")` works
  in exported builds; a `DirAccess` scan of imported PNGs does not.
- **At content lock, switch slots to `preload` constants and delete the
  fallbacks**, so missing art becomes a load error instead of a silent
  rectangle. The cleanup also turns up unused sprites to delete.
- **New sprites don't draw until Godot imports them.** This is the most
  repeated art bug (new buildings, new animation frames, new critters). End
  every art build with `timeout 400 "$G" --headless --path . --import`; run it
  after adding a `class_name` too.

## 13. Record every transform

- **Every art transform is a committed script**, and its exact command line
  goes into `docs/art-manifest.md`. One-off transforms that never get
  committed (a logo keyer, an icon splitter, a band remapper, leg widening)
  survive only as prose and can't be rerun.
- `art/manifest.json` + `art_build.py` rebuild every sprite from `raw_art/` in
  one command (`pixel-conversion.md` §6).
- `docs/art-manifest.md` sections: canvas and density; per-asset table
  (slot, texture / drawn / hitbox per state, notes); measured facts (hue
  windows, frame differences, minimum readable size); generating rules (what
  the model gets wrong); the command for every asset; animation; effects;
  backgrounds (band shares, what must stay empty, reserved areas); fonts with
  their licences; app icon layers (and the export preset pointing at them);
  **rejected approaches with the measurement that rejected them** ("16x16 was
  tried and rejected; 24x24 is the floor"). Put a Status / last-verified line
  at the top: manifests drift into contradicting themselves, and briefs keep
  saying "24 colours, locked" long after the palette has grown.
