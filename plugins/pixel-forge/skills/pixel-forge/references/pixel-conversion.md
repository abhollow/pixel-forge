# Conversion: illustration → sprite

The scripts that turn a Magnific image into game-ready pixels, the order to
run them, and the settings that work. Lessons behind them are in
`art-pipeline-lessons.md`.

Commands use `python "$FORGE/scripts/..."` (FORGE = the skill's base
directory). Inside a game, call the vendored copy in `tools/forge/`; game files
never reference the plugin path. If `python` is the Windows Store stub, use
`py -3` or `python3`. Flags shown are the common ones; each script's `--help`
is the authority.

## Contents
1. Why this step exists
2. The scripts, in order
3. pixelize.py
4. Settings that work, by asset type
5. Palettes
6. art_build.py: one manifest, one rebuild
7. HD: re-cut at 2x
8. Downscaling: BOX, and the Python-free route
9. Atlases (optional)
10. Troubleshooting

---

## 1. Why this step exists

An AI "pixel art" image is an illustration *of* pixel art. Under a magnifier
it has anti-aliased edges, soft gradients, thousands of colours, and blocks that
don't land on a grid. Put it in an engine at 32 px with nearest filtering and
it turns to mush; put it in at 1024 px and one sprite eats more memory than the
rest of the game. The fix is deterministic, not creative.

## 2. The scripts, in order

| Step | Script | Does |
|---|---|---|
| 0 | `fetch_art.py` | Download signed URLs to `raw_art/<batch>/`, append rows to `docs/assets.md` |
| 1 | `slice_sheet.py` (`--mode blob`, `--shared-box`, `--despill`) or `cut_boxes.py` | Key from raw, despill inside the mask, cut, fit to size, hard alpha |
| 2 | `pixelize.py` or `prep_sprite.py` | BOX downscale, optional palette lock, hard alpha |
| 3 | `remap_reserved.py`, `soften_edges.py`, `recolor.py` | Post-passes: reserved colours, edges into ground, hue shifts |
| 4 | `godot --headless --path . --import` | Without it new sprites don't draw |
| 5 | `contact_sheet.py`, `capture.gd` | Look at it at game scale |

`art_build.py` runs steps 1–3 for every sprite from `art/manifest.json` (§6)
and then tells you to run step 4.
Supporting: `make_palette.py`, `palette_build.py` (§5), `despill.py`
standalone, `check_cycle.py` and `measure_hues.py` (measurement),
`make_walk_frames.py` / `make_sway_frames.py` (`animation.md`).

## 3. pixelize.py

```bash
python "$FORGE/scripts/pixelize.py" INPUT [INPUT...] (-o OUT | -O OUTDIR) (--target N | --keep-size) [options]
python "$FORGE/scripts/pixelize.py" raw_art/cut/*.png -O art/sprites --keep-size --palette art/palette_build.hex
```

| Flag | Does |
|---|---|
| `--target N` | Output size of the **LONGEST side**, in pixels. |
| `--keep-size` | No rescale: palette-lock and harden art already cut to size (after `slice_sheet.py`, `cut_boxes.py`, `art_build.py`). |
| `--detect` | Guess the faux-pixel grid and divide by it. Only for a single illustration with a visible grid. |
| `--palette FILE` | Lock colours to a `.hex` or palette `.png`. Use the asset class's sub-palette. Optional. |
| `--colors N` | Derive an N-colour palette from this image alone (median cut). One-offs only. |
| `--alpha-threshold N` | Alpha cutoff 0–255, default 128. |
| `--trim` | Crop the transparent border first, so `--target` measures the subject. |
| `--no-pad` | Don't pad to a square. Use for cut sprites, tiles and backgrounds. |
| `--bg-key HEX` / `--bg-tolerance N` | Chroma-key a halo colour. Prefer keying in the cutter. |
| `--resample` | Downscale filter; default `box`. Leave it. |
| `--upscale N` | Integer nearest upscale, previews only. |
| `--report FILE` | JSON summary. |

**`--target` is the longest side, and never let it guess.** You must pass one
of `--target`, `--keep-size` or `--detect`.
- A 960x2160 map converted with `--target 960` comes out 427x960, and the game
  blows it up 2.25x. It needs `--target 2160`.
- Left to guess the grid, it finds the 2 px grid in 2x cuts and halves them
  back to 1x. On art you already cut to size, use `--keep-size`.

**Order inside the script:** chroma-key (optional) → trim → **BOX** downscale
(area average; bicubic and Lanczos ring and invent colours) → quantise to the
palette (luma-weighted nearest colour) → **harden alpha** (every pixel opaque or
gone; non-negotiable) → pad (optional) → integer upscale (previews only; scale
in the engine).

`prep_sprite.py` does trim, box-average, optional palette snap and hard alpha,
and slices simple strips with `--cols` / `--rows`.

## 4. Settings that work, by asset type

| Asset | Settings | Notes |
|---|---|---|
| Kit sprites (buildings, props) | `slice_sheet.py --mode blob --despill` to listed sizes, then `pixelize.py --keep-size --palette <sub-palette>` (or `slice_sheet.py --palette`), then `remap_reserved.py` | The standard kit path |
| Chunky sprites, no palette | Key, BOX fit to box, hard alpha, no quantising | Coherence comes from the pipeline, not the palette (`art-direction.md` §5) |
| Animation frames | `slice_sheet.py --shared-box`, one scale per set | `animation.md` |
| Character portrait | BOX to the final grid (112–128 px), flood-fill key of the flat background from the border, fringe pass, 32–36 colours, hard alpha | A portrait from a photo holds up at 112 px, 36 colours median cut |
| Detailed scene / header | About **640 px wide, about 200 colours, max-coverage, no dither** | At 480 px / 48 colours median cut, small details (a figure in a window, a fireplace) vanish; 640 / 200 keeps them |
| Painted map | `--target` = the map's long side, **no palette lock** | `large-backgrounds.md` §7 |
| HD set | Same cuts at 2x sizes, same palette, `--keep-size` | §7 |

`pixelize.py --colors` uses median cut. For a detailed scene, use PIL directly
unless `pixelize.py --help` lists a max-coverage option:

```python
from PIL import Image
im = Image.open(src).convert("RGB")
w = 640; h = round(im.height * w / im.width)
small = im.resize((w, h), Image.Resampling.BOX)
small.quantize(colors=200, method=Image.Quantize.MAXCOVERAGE,
               dither=Image.Dither.NONE).convert("RGB").save(dst)
```

## 5. Palettes

**Palette locking is a tool, not the glue** (`art-direction.md` §5). Use it for
reserved and semantic colours, for cleaning strays, and per asset class.

**`make_palette.py`** builds a starting palette:

```bash
python "$FORGE/scripts/make_palette.py" extract raw_art/mood/mood_c.png -n 44 -o art/extracted   # from the mood frame
python "$FORGE/scripts/make_palette.py" ramp --hues 195,45,140,20 --steps 4 -o art/palette        # procedural ramps
```

It writes `.hex`, `.png` (one pixel per colour) and `_preview.png` (look at
this one). Extract from the chosen mood frame; ramp mode (N hues × M shades plus
a near-black and near-white) suits a game with no reference art.

**`palette_build.py`**: the palette as code. One `art/palettes.json` holds:
- **named groups**: for example the grey-box UI colours, the colours extracted
  from the mood frame, extras, greens, water, fire;
- **reserved colours**: semantic colours kept out of art sub-palettes (for
  example a fire red and a player blue) and code-only colours (for example a
  resource yellow that only code draws);
- **sub-palettes per asset class**: for example world (trees, plants), build
  (buildings, people), water and map, plus per-asset subsets (greys for
  clouds, effects, stone).

```bash
python "$FORGE/scripts/palette_build.py" init art/palettes.json      # starter file to edit
python "$FORGE/scripts/palette_build.py" build art/palettes.json     # write every palette
```

Shape (`palette_build.py --help` has the full schema):

```json
{
  "out_dir": "art",
  "groups": {"ui": ["f4f6f0", "2d251d"], "warm": {"file": "art/extracted.hex"},
             "flames": ["8c2519", "ea6b5d"], "water": ["1f3634", "2b4744"]},
  "reserved": ["flames"],
  "master": ["ui", "warm", "flames", "water"],
  "palettes": {"palette_world": ["warm", "f4f6f0"],
               "palette_water": {"groups": ["water"]},
               "palette_enemy": {"groups": ["warm", "flames"], "allow_reserved": true}}
}
```

`build` writes the master `art/palette.hex` (the path in `forge.json`) and one
`.hex`, `.png` and `_preview.png` per sub-palette. Reserved groups stay in the
master (for UI and code-drawn effects) and are left out of every sub-palette
unless it sets `allow_reserved`.

**Sizing reality.** A common rule of thumb says past about 48 colours a
palette stops unifying. A master palette can grow well past that (80 or more)
and stay coherent when each asset class quantises against its own small
sub-palette. Keep sub-palettes tight; let the master grow. Painterly maps are
better unlocked.

**Coverage check.** Measure the share of a reference's pixels more than 28 RGB
units from any palette colour, and get the colours worth adding (k-means of
the misses). Around 20% missed is high; adding five or six clustered misses
usually closes most of the gap.

```bash
python "$FORGE/scripts/palette_build.py" coverage raw_art/mood/mood_c.png --palette art/palette.hex \
    --suggest 6 --miss-map docs/screens/palette_misses.png
```

## 6. art_build.py: one manifest, one rebuild

Every sprite is rebuilt from `raw_art/` by one command, reading
`art/manifest.json`. One entry per sheet: `sheet`, `cutter` (`blob`,
`profile`, `boxes` for a `cut_boxes.py` file, `plate` for a `pixelize.py`
background), `key`, `prefix`, `sizes`, `despill`, `shared_box`, `anchor`,
`scale_by`, `palette`, `post` (`soften_edges`, `remap_reserved`, `recolor`),
`hd` (`[2]`), `stretch` (resize a sheet that came back at another size),
`enabled`. `--help` lists every field.

```bash
G="${GODOT:-godot}"
python tools/forge/art_build.py --init          # starter art/manifest.json
python tools/forge/art_build.py                 # rebuild what changed
python tools/forge/art_build.py --only kit --force   # one prefix, even if unchanged
python tools/forge/art_build.py --list          # each entry and whether it is up to date
timeout 400 "$G" --headless --path . --import   # art_build prints this as its last step; run it
```

- **Incremental:** entries rebuild only when the raw sheet or their settings
  change (`--force` overrides, `--dry-run` prints the commands, `--no-hd` skips
  the density sets). Stale outputs are removed.
- **Resizing is a one-line edit and a rebuild.** Scaling every sprite by 1.25
  (re-cut from the raw art) and later putting one class back to its original
  size is a change to one line per prefix.
- The 1x and HD builds read the **same** manifest; HD sets are re-cut from raw
  and checked to be 2x within 2 px. A declarative manifest keeps the two in
  sync; don't parse shell build scripts to do it.
- Record each entry's purpose and any hand-tuned numbers in
  `docs/art-manifest.md`.

## 7. HD: re-cut at 2x

**Why:** Magnific sheets arrive about 2,560–2,750 px wide, so a house is 500–700
px before being pixelised to about 105 px (about 1/36 of the pixels), and a
creature's walk frame goes from about 430 px tall to 20 px. A phone renders
`canvas_items` at device resolution, so a 960x540 layout has about 2x the
screen pixels available.

**Recipe:**
1. Re-cut every world sprite from `raw_art/` at 2x sizes into
   `art/sprites_hd/`, same sub-palettes, locked with `--keep-size` (never a
   grid guess). Verify every HD sprite is 2x its 1x twin within 2 px. (The HD
   set stays small on disk: a few MB.)
2. Load each as an `ImageTexture` drawn at the 1x size:
   ```gdscript
   var t := ImageTexture.create_from_image(img)
   t.set_size_override(art_1x[key].get_size())
   ```
   Region draws use override units. Code that reads a sprite's own pixels
   (outlines, snow on roofs) uses the 1x texture.
3. Pick the set at runtime: HD when `viewport.size.y / visible_rect.size.y >=
   1.5` (true on phones); re-check on `size_changed`. The desktop window keeps
   1x, because 2x sprites squeezed into 1x look worse.
4. Flames, icons, effects, HUD and title stay at base density.

Costs: about 4x sprite memory for the HD set; code-drawn visuals stay chunky
and need their own sweep. Stretch settings: `godot4-pixel-setup.md`.

## 8. Downscaling: BOX, and the Python-free route

- **BOX (area average) is the rule** for every downscale of pixel art.
- Godot's `Image.resize` has no box filter, so cutters written in GDScript and
  run in headless Godot fall back to `Image.INTERPOLATE_LANCZOS`. Treat that
  as a deviation, not a precedent.
- On a machine without working Python (the Windows Store stub is common on a
  fresh machine), copy `assets/godot/cut_frames.gd` to the game's `tools/` and
  run it in headless Godot. It keys, finds frames by projection, applies one
  scale to every frame, keys to transparent black, box-averages, hardens alpha
  and anchors each set on a shared canvas:
  ```bash
  G="${GODOT:-godot}"
  timeout 300 "$G" --headless --path . --script res://tools/cut_frames.gd ++ spec=raw_art/enemy/cut.json
  timeout 400 "$G" --headless --path . --import
  ```
  The spec is JSON: `sheet`, `key` (magenta, green, corner, `#rrggbb`), `rows`
  (one name per row), `frames` (per row), `scale_by` (`{"color", "tol",
  "width"}`) or `width` / `height` / `scale`, `anchor`, `shared`, `out`
  (`art/sprites/enemy_{row}_f{i}.png`). The script's header documents every
  field; `++ self_test=1` checks it.

## 9. Atlases (optional)

Atlases are optional: individual PNGs loaded by name
(`ResourceLoader.list_directory`) or exported `Array[Texture2D]` slots work
fine. Use `build_atlas.py` when you want `hframes`/`vframes` strips:

```bash
python "$FORGE/scripts/build_atlas.py" walk_*.png -o art/hero_walk.png --cell 32 --row
```

Uniform grid, sprites centred never scaled; a sprite bigger than the cell is an
error. It prints the numbers to enter in Godot.

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Map or background chunkier in game than on disk | `--target` was given the short side's size, but it sets the long side | `--target` = the output's longest side |
| 2x cuts came out 1x | Grid guess (`--detect`) on art already cut to size | `--keep-size` on art already cut to size |
| Small details vanished in a scene (a figure in a window) | Too small and too few colours | ~640 px wide, ~200 colours, max-coverage, no dither |
| Detail vanished in a sprite | Target too small for the subject | Bigger target, simpler subject in the prompt, or HD (§7) |
| Mushy, no crisp pixels | Too many colours or a smooth resize | BOX only; a sub-palette or fewer `--colors` |
| Purple or green cast in shadows | Key spill | Despill inside the kept mask (`art-pipeline-lessons.md` §3) |
| Neighbouring sprites merged | Despilled before cutting a sheet with drop shadows, or overlapping rows | Key raw first (`slice_sheet.py --despill`); `--mode blob`; check `--debug-sheet` |
| Pink or green fringe | Key colour bled in the resize | Key to transparent black before resizing; `--clean-fringe` |
| Grey cloud turned tan or green | Palette has no fitting greys | Greys-only sub-palette; quantise the interior to greys first |
| Grass shadows turned blue-grey stone | One palette for land and water | Quantise them separately |
| A reserved colour appears on a prop | Nearest colour landed on it | Sub-palette without it, then `remap_reserved.py` |
| Meadow flattened to one green, flowers gone | Palette lock on painted ground | Don't lock painterly ground |
| Sprite tiny in a big canvas | Not trimmed | `--trim`, or cut tight first |
| Two sprites at different scales | Different framing in the source | Trim both; scale from the subject (`art-pipeline-lessons.md` §8) |
| Bright fringe in engine | Semi-transparent edge | Hard alpha (default); if the halo is opaque, key it |
| New sprite doesn't appear | Not imported | `godot --headless --path . --import` |
