# Large backgrounds and maps

Painted backgrounds and maps bigger than one screen: when to make them, how to
get a model to follow a layout, and how to stitch, edit and animate them.
Sprite work is in `art-pipeline-lessons.md`; generation basics in
`magnific-pipeline.md`.

Commands use `python "$FORGE/scripts/..."` (vendored as `tools/forge/` inside a
game). If `python` is the Windows Store stub, use `py -3` or `python3`. Flags
shown are the common ones; `--help` is the authority.

## Contents
1. Defer until footprints settle
2. Fit the game to the art
3. One-screen backgrounds: prompting
4. Maps from a plan
5. Paint per screen, stitch
6. Model-friendly ratios and paste-back
7. Palette and conversion
8. Editing a painted map
9. The markup loop
10. Animated scenery
11. Tiles
12. Stills and wallpapers

---

## 1. Defer until footprints settle

Background art is the art most likely to be thrown away.

- Location art made before the layout settles is usually thrown away. Terrain
  tends to cycle through approaches as the design moves (sprites on a painted
  backdrop → painted per-area backdrops → tile-and-sprite terrain → one
  painted map → the map repainted per screen) and can still end as **plain
  ground** after a redesign. Most of the credits spent early on terrain and
  maps get shelved; the sprite kit survives every pivot.
- Generate backgrounds after the playable footprint (play areas, building
  sizes, scroll extent) is fixed. Until then use plain ground plus sprites:
  work on the mechanics and sprites first, then the map look once the size of
  the play areas is known.
- What tends to pass as shippable: one painted image with the mechanics on
  top. Terrain assembled from tiles and scattered sprites tends to fail. A
  strong pattern for a map: a painted map with a bare-earth patch per play
  area, and the structures built from sprites on top.

## 2. Fit the game to the art

- **Never fit the art to the zones.** Generate at the target aspect, then
  measure where things actually fell and set the gameplay lines there: set
  zones from the art, measure layouts off a grid overlay, and find hotspot
  coordinates (a chimney, a fireplace) by cropping with a 4 px grid overlay.
- **Keep layout data and tuning data apart**, so a repainted background never
  changes how an area plays.
- **Prefer placing sprites on painted ground to measuring painted objects.**
  Learning plot outlines off a painting by soil colour works but is fragile; a
  sprite kit on plain painted ground is sturdier.
- **Composite from existing art when it's enough** (a big pile as three pile
  sprites).

## 3. One-screen backgrounds: prompting

- **Generate at the target aspect** (9:16 backgrounds come back 1152x2048).
- **Give band proportions as percentages**, top to bottom. The model follows
  them closely enough to measure zones from.
- **Name what must be empty**: "Almost completely EMPTY ground, no rocks, no
  boulders, no furniture". Anything decorative on the play area reads as an
  obstacle or hides sprites.
- **Reserve space** for gameplay furniture: "the FAR RIGHT of this band is a
  plain flat concrete plaza with nothing on it".
- **Check every element for direction**, not just the obvious one: art can
  come back with flags blowing right and trees and kite tails blowing left.
  Run the prompt both ways at once and mirror whichever is consistent.
- **Backgrounds that blend into surroundings:** fill the edges ("The clearing
  is surrounded on all sides by DENSE dark pine and spruce forest that fills
  every edge and corner").
- **Top-down maps:** "orthographic... uniform scale everywhere, NO perspective,
  NO horizon", and give a scale ("each tree about 1/40 of the image width").
  Without it the first terrain comes back with boulders bigger than the
  houses.
- **Parallax:** one layer per generation ("parallax background layer, SUBJECT,
  horizon at one third").
- **Leave out anything code will animate** (§10).

## 4. Maps from a plan

1. **Make a flat colour-coded plan**: one flat colour per land use, no
   textures. Positions in the plan come from the game's data, so the plan is
   the source of truth for where things are.
2. **Generate fresh** with two references, `{type: "image", <plan>}` and
   `{type: "style", <style anchor>}`, and a prompt that explains the legend.
   Template:

   > The first reference is a colour-coded layout plan for a game map. Paint it
   > as one finished... Plan colours: <colour> = <land use>; for example dark
   > green = dense pine forest...; grey = raised rock cliffs...; teal = a
   > winding river...; brown lines = winding dirt footpaths; light green = lush
   > spring meadow; tan = warm golden meadow; off-white = snowy rocky highland.

3. **Not reimagine.** Reimagining a textured sketch copies its flat tiles
   (Nano Banana's reimagine redraws the sketch at its own size, e.g.
   768x1344); `keepStructure` is Flux only, and Flux keeps nothing of the
   layout.
4. Use `imagen-nano-banana-2` at 4k (150 credits per image at the time of
   writing).

## 5. Paint per screen, stitch

- **One image for a big map paints a vista.** A 960x2160 map in one
  generation comes out with every flower and tuft a 1–2 px smear at game size.
- **Paint one screen at a time** (960x540 each, generated at 4k), each with a
  crop of the plan as the layout reference and the style anchor. Prompt:

  > Redraw the first reference scene exactly - same layout... in the exact
  > pixel art style of the second reference... This is a close view, so draw
  > small things large and readable

- **Overlap and dither.** Paint sections with overlaps (for example at
  y = 0, 405, 810, 1215, 1620 with 135 px overlaps) and blend them through a
  dithered ramp (`rng.random() < linspace`): no seam and no soft cross-fade.

  ```bash
  python "$FORGE/scripts/stitch_map.py" --sections 0:raw_art/map/r0.png 405:raw_art/map/r405.png \
      810:raw_art/map/r810.png 1215:raw_art/map/r1215.png 1620:raw_art/map/r1620.png \
      --width 960 --section-size 540 -o art/map.png
  ```

  Each section is resized to `--width` x `--section-size` and placed at its
  offset; the overlap is whatever the offsets leave (540 − 405 = 135 px here).
  `--axis x` stitches a wide map left to right (with `--height`).

- **Sample before committing.** Send two or three candidate sections at game
  size and let the user pick. Prefer variants that kept the target palette;
  others drift bluer and band.

## 6. Model-friendly ratios and paste-back

- **Generators want standard aspect ratios.** Pad the plan to one (for example
  960x2160 to 9:16) by **carrying its edge on**, not mirroring, so no mirrored
  landmarks appear, generate, then crop back:
  ```bash
  python "$FORGE/scripts/fit_ratio.py" pad art/plan.png -o work/plan_916.png        # nearest friendly ratio; --ratio 9:16 to force
  python "$FORGE/scripts/fit_ratio.py" crop raw_art/map/painted.png --meta work/plan_916.json -o work/painted_fit.png
  ```
  `pad` writes the round-trip JSON next to its output; `crop` takes the
  model's output at whatever resolution it came back and returns the original
  frame at the original size.
- **Outputs come back at the model's own size.** A recolour can return
  1344x768 for a 2560x1440 source; stretched back to 16:9 it lines up. Verify
  with a crop overlay of a landmark, and resize to the mask if sizes differ.
- **Paste gameplay-critical regions back pixel-exact**, with a dithered feather
  at the boundary (for example every play area's core pasted back into the
  painted map):
  ```bash
  python "$FORGE/scripts/fit_ratio.py" paste-keep work/painted_fit.png --source art/map_dump.png \
      --mask art/keep_mask.png --feather 22 -o art/map.png
  ```
  `--source` is the image holding the exact regions (a 1:1 dump of the game);
  white in the mask means keep (`--keep black` for the opposite convention).

## 7. Palette and conversion

- **Don't palette-lock painterly ground.** A strict palette flattens a meadow
  to one green and drops its flowers. Sprites on top keep their sub-palettes.
- **`pixelize.py --target` is the longest side**: a 960x2160 map needs
  `--target 2160` (`pixel-conversion.md` §3).
- **Find features by hue, not palette index** (for example water for effects
  by its teal hue); palette indices break after a repaint.

## 8. Editing a painted map

- **Edit with the map as the single image reference.** One call can remove
  every structure from a map. Template:

  > Edit this painted game map, keeping everything else exactly the same...
  > Remove all <N> <structures> completely... Where each <structure> stood,
  > leave only an irregular, odd-shaped patch of trodden bare earth...

- **Recolour instead of regenerating** when only colour is wrong
  (`recolor.py`); a regeneration loses every measured position.
- **Small factual fixes in PIL**, not a re-roll.

## 9. The markup loop

When the user wants to draw the layout:

1. **Dump the world at 1:1** with a capture scenario (a `capture.gd` scenario
   that renders the whole map, e.g. 960x2160), plus a **flat schematic** of
   the same area.
2. **The user paints a legend** over the schematic in saturated pens (for
   example grey cliffs, orange play areas, red forest, blue water).
3. **Convert the markup to a land-use mask** (`art/terrain.png`, one flat colour
   per land use): threshold each pen colour, morphological close, fill, drop
   specks, then scale into game coordinates after aligning to known positions.
   This is a small per-game script.
4. **Build the plan image** from the mask (§4).

Pitfalls: a grey pen is too close to a painting's own rocks to pick by colour,
so its areas end up traced by hand; red needs explicit thresholds to separate
it from orange. Give the user the **flat schematic, not the painting**, and
pens in saturated colours that cannot occur in it.

## 10. Animated scenery

- **Leave animated elements out of the painting.** End the prompt with, for
  example, "no chimney smoke, no falling snowflakes", and draw snow, smoke,
  fire and window glow in code. Derive masks from the image's own pixels: a
  window glow from warm pixels (`r>160 && r>b+60 && g>b+5`), stars from bright
  isolated pixels in the sky.
- **Sway painted foliage with a mask and a shader.** `make_sway_mask.py` marks
  what may move; `assets/shaders/sway.gdshader` shifts it. Set `--below` above
  rooftops and lawns (a green lawn is darker than the sky and gets caught), and
  `--sky 0` under a saturated sky or building edges wobble. Always look at the
  mask overlaid on the art.
  ```bash
  python "$FORGE/scripts/make_sway_mask.py" --src art/bg_level2.png --out art/bg_level2_sway.png --below ROW --sky ROW
  ```
- **Sway separate tree sprites per sprite**: `sway_sprite.gdshader`, or a
  `draw_set_transform_matrix` shear from the foot for depth-sorted trees.
- **Water:** `make_water_frames.py` animates a horizontal band (sea at the
  bottom of the screen; wrong for a round island). `water.gdshader` finds
  painted water by hue and re-samples it along whole-pixel sine offsets with
  glints, so it works on rivers and lakes.
- **Drive shaders with a CPU-wrapped phase uniform**, never raw `TIME`
  (`godot-gotchas.md`).
- **Verify motion by pixel diff:** thousands of water pixels should change
  over about a second while land pixels stay put (`animation.md` §8).

## 11. Tiles

Tile-and-sprite terrain tends to fail for painted games: mirror-tiled
textures show seams and repeats, altitude bands show as stripes, and
scattered tufts look noisy. If a game does want tiles:

- Models don't make seamless tiles. Generate a texture patch,
  `pixelize.py --target 32 --no-pad`, then mirror-tile or fix the seam by hand.
- Or generate one centre tile and one edge piece and build the terrain set in
  Godot's TileSet terrain editor.

## 12. Stills and wallpapers

A frozen frame of the scene with its code-drawn layers is marketing art. For a
web page, re-implement the canvas layers (snow, glow, fire) for one frame; in
a Godot game, `capture.gd` gives the frame with the code layers already drawn.
Upscale nearest-neighbour to 3840x2160, 1920x1080, 1080x1920 (phone),
3840x1632 (panorama) and native. A menu that runs the game itself behind it (a
showcase or attract mode) is free footage. See `launch-and-marketing.md`.
