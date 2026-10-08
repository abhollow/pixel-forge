# Art direction

How to set the look, keep every asset inside it, and know what the user
likes. This is the "what and why" layer above `magnific-pipeline.md` (how to
generate), `art-pipeline-lessons.md` (how to cut and clean) and
`pixel-conversion.md` (the scripts).

## Contents
1. The loop
2. Mood frames: the target
3. Palette from the frame
4. The style anchor
5. What actually makes it one game
6. Judging rounds: decision images
7. The taste profile
8. Density tiers: chunky or detailed
9. Colour rules
10. Art first? The waiver branch
11. Reuse, tint and code before generating

---

## 1. The loop

```
4 mood frames ──► user picks one ──► palette extracted from it
                  ("the mood frame you pick IS the target")
      │
      ▼
upload a style anchor ──► style-reference EVERY kit sheet to it
      │
      ▼
cut, convert, render in game ──► judge against the frame AT GAME SCALE
      │                                 │
      └────────── next round ◄──────────┘
```

Run every art round through this loop: mood frames from one model at the
game's aspect, one frame chosen, the palette extracted from that frame, one
uploaded style anchor passed on almost every sheet, and every round judged
against the chosen frame. When the game drifts from the frame, the fix starts
from measuring the gap (§2).

If the user hands over art direction (asks you to do the art at your
discretion, with no approval rounds), still hold **one vibe checkpoint** (the
mood frame pick), then work at your discretion. Keep showing the picks and the
credit spend each round anyway.

Offer choices as numbered options with a recommendation, in text. Pop-up
question widgets interrupt and tend to get dismissed.

## 2. Mood frames: the target

- Generate **4 mood frames** in one call (`count: 4`), framed as **an in-game
  screenshot**, not a poster: camera angle, scale of the buildings and people,
  light, and the palette words. `seedream-5-pro` at the game's aspect (16:9
  for landscape) works well.
- Skeleton:

  > Beautiful pixel art game screenshot, <camera: e.g. high three-quarter
  > top-down view like a 16-bit RPG>, looking down onto <scene>... <what the
  > player looks at>... <mood and light: e.g. peaceful, serene, golden
  > afternoon light, a place you want to sit and watch>. <palette: e.g. muted
  > earthy palette of <colour words>>. The ONLY saturated colour in the whole
  > image is <the reserved colour>. Detailed crisp pixel art, hard-edged
  > pixels, limited colour palette, no anti-aliasing, no text, no UI, no
  > border, no frame, no watermark

- The user picks one. Record it in `docs/bible.md` (Art direction: frame file,
  creation id, model) with the line **"The mood frame you pick IS the target."**
- When the game looks far off the frame, **measure the gap**
  before regenerating: how big the key objects are in the frame versus in the
  game (buildings about 110 px wide in the frame against far smaller sprites
  in game is a typical finding), whether they are painted together or placed
  apart, what fills the edges (forest pressing in versus empty ground), and
  how warm the palette is. The fix follows from the measurement, not from
  another roll.

## 3. Palette from the frame

- Extract from the chosen frame:
  `python "$FORGE/scripts/make_palette.py" extract raw_art/mood/mood_c.png -n 44 -o art/extracted`
  (40–50 colours is a good start for a detailed frame). If `python` is the
  Windows Store stub, use `py -3` or `python3` (see `windows-and-shell.md`).
- Merge it into the palette-as-code file with `palette_build.py` (named groups,
  reserved colours, sub-palettes; see `pixel-conversion.md` §5).
- **Check coverage** against the frame: the share of frame pixels more than 28
  RGB units from any palette colour. Around 20% is high; cluster the misses
  and add the five or six colours that close most of the gap.
  `python "$FORGE/scripts/palette_build.py" coverage raw_art/mood/mood_c.png --palette art/palette.hex --suggest 6`
- A palette grows over a project and that is fine: with sub-palettes keeping
  each asset class clean, a master palette can grow from a couple of dozen
  colours to 80 or more and stay coherent.

## 4. The style anchor

- Pick **one strong in-game image** (for example a crop of the best finished
  background or kit sheet), upload it once (`magnific-pipeline.md` §4) and
  pass it as `{type: "style", identifier}` on every kit sheet. If the anchor
  is already a Magnific creation, pass its creation id; upload only local
  files.
- Once the anchor exists, "in exactly the painting style of the reference"
  plus the framing and keying lines replaces most of the long constant block.
- New members of an existing family get the earlier sheet as an
  `{type: "image"}` reference plus "matching the reference ... EXACTLY in
  style, size ... framing" (`magnific-pipeline.md` §7).
- `library_create` / `@name` characters exist, but the anchor plus family
  references usually do the job without them.

## 5. What actually makes it one game

Palette locking is a tool, not the glue.

- Palette quantisation is not what makes art cohesive. A game can ship with
  almost none of its sprites on its palette (single small sprites carrying
  hundreds of colours) and still read as one game. Coherence comes from:
  - every state of a character generated in **one sheet**;
  - one consistent prompt style and one style anchor;
  - **hard alpha** on every sprite;
  - art drawn at a **fixed integer scale** (for example half-density art at
    2x);
  - judging every asset **at game scale** beside its neighbours.
- Use sub-palettes to *enforce colour rules* (§9) and clean up strays, and
  leave painted maps unlocked.
- So: make one-sheet generation, the anchor, hard alpha, integer scale and
  game-scale judging mandatory. Use palette quantisation where it earns its
  place: reserved and semantic colours, cleanup, sub-palettes per asset class.

## 6. Judging rounds: decision images

Every art decision is made from an image built for that decision, at the size
the player will see it.

| Image | What it shows | Example file |
|---|---|---|
| Options at game size | Each option keyed, scaled to its in-game size, on the real background beside existing sprites | `<subject>_options_at_game_size.png` (beside the hero and a typical prop) |
| In game | The pick's frames composited in the real scene | `<subject>_in_game.png` |
| Side by side at device size | Today vs option A vs option B, rendered at the phone's resolution, captioned | `compare_<topic>.png` at 1920x1080 |
| Diagnostic triptych | raw art / scaled to game / scaled + palette, to explain *why* something looks wrong | `why_<problem>.png` |
| Section candidates | Candidate map sections at game size | `<map>_section_N_gamesize.png` |

- Build them with `contact_sheet.py`: each option keyed, scaled to its game
  size (`--game-width` / `--game-height`), on a background beside a reference
  sprite, nearest-upscaled and captioned (`--letters`, `--captions`,
  `--title`; `--frame WxH` for a device-sized panel):
  ```bash
  python "$FORGE/scripts/contact_sheet.py" raw_art/b07/crate_*.png --game-width 18 \
      --reference art/sprites/hero_00.png --background art/bg_level1.png --letters \
      -o docs/screens/keep/crate_options_at_game_size.png
  python "$FORGE/scripts/contact_sheet.py" --grid raw_art/b07/*.png -o raw_art/b07/sheet.jpg   # raw batch review
  ```
- Save every option as `raw_art/<batch>/<subject>_option_N.png`, plus
  `<subject>_options_at_game_size.png` and `<subject>_in_game.png`
  (`contact_sheet.py --subject DIR` follows that naming).
  Decision images go in `docs/screens/keep/` (committed); other renders in
  `docs/screens/` (gitignored).
- **Send them full size** and tell the user to open them full size: shrinking
  them hides most of the difference.
- Give a **recommendation with reasons** and admit limits: which option stays
  clearest when shrunk, which frames differ most, and what none of them gets
  right ("none is a true rear view").
- In Claude Code you render the real game yourself (`capture.gd`, see
  `art-pipeline-lessons.md` §11), so the in-game image is always available.

## 7. The taste profile

Record the user's art, UI and audio preferences as **rules** in a "Taste"
section of `docs/bible.md`, with the date and the user's own words that set
each one. Add to it whenever feedback reveals a preference, so the next
session doesn't relearn it. Taste is per game: the same user may want chunky
art for one game and fairly detailed sprites for the next, so ask at the start
of each game instead of carrying it over.

**Template** (fill in what the user tells you; leave out what they haven't):

```
## Taste
- Mood: <cozy / gritty / eerie / bright>; <what the world should feel like to be in>.
- Shapes: <organic and irregular / clean and geometric>; <how uniform scale,
  edges and placement may look>.
- Pixels: <chunky / fairly detailed>; <which classes stay chunky: icons,
  effects, HUD, title>.
- Indicators: <how subtle>; <when they show>; <the line between "blends in"
  and "can't see it">.
- UI: <minimal / rich>; <opaque / semi-transparent>; <what gets text>;
  <what is prominent>.
- Effects: <randomised per use / fixed sprites>.
- Colour: <reserved and semantic colours, with the reason>.
- Audio: <music level vs. SFX>; <gaps or crossfades between tracks>.
```

Other signals worth recording when they appear: the user thinks in
image-editor terms ("replace color", "fuzziness"; map requests onto those
knobs); the user prefers code transforms to new art (scale, tint or move it in
code before generating); the user judges animation at game size (check motion
there before showing it).

## 8. Density tiers: chunky or detailed

Decide two things separately and record both in the bible:

1. **Logical canvas** (the layout grid). Pick by the short side and how busy
   the screen is (`godot4-pixel-setup.md`). Prefer an exact integer fraction
   of the target device (960x540 is exactly 2x on a 1080p phone). Too small a
   canvas for a busy screen looks blocky; too large and the pixel art
   disappears.
2. **Art density** (pixels per logical pixel for each asset class).
   - Chunky: art authored at the logical size, drawn at an integer scale
     (half-density art at 2x is common; 24x24 is the floor for a readable
     person, and 16x16 reads as a coloured blob).
   - Detailed (HD): re-cut the same raw art at 2x into `art/sprites_hd/`, same
     palette, drawn at 1x size with `ImageTexture.set_size_override()`, chosen
     at runtime when the render scale is at least 1.5 (phones). The desktop
     window keeps 1x, because squeezed 2x sprites look worse. Recipe:
     `pixel-conversion.md` §7.
   - **Keep some things chunky.** Flames, icons, effects, HUD and title often
     look best at base density; HD is for clarity on very small objects such
     as people.
   - Avoid: 4x "painted" art with no palette. Each sheet keeps its own colours
     (a cool grey stone, orange barrels) and clashes with the chunky
     code-drawn parts.
   - Hidden cost: code-drawn visuals stay at base density (often hundreds of
     draw calls across a game) and need a gradual redraw sweep.

Before switching tiers, show today / A / B side by side at device resolution
with pros and cons, and build nothing until the user picks.

## 9. Colour rules

- Write **semantic colours** into the bible as a rule with a reason. For
  example: red belongs to the enemy and blue to the player, so only fire and
  the enemy's kit carry red and blood is a muted dark red; or brown means rot,
  so a recoloured healthy plant must stay bright.
- Enforce them in three places:
  1. **Prompt lines**: "No saturated blue or red anywhere", "water in muted
     teal-grey, NOT saturated blue", "(no pink, no purple)" where the key or a
     tint shader must stay safe.
  2. **Picks**: reject sheets that come back with a forbidden colour (red
     roofs in a game where red is reserved) in favour of the alternate.
  3. **Conversion**: sub-palettes without the reserved colours (for example
     `palette_build.hex` and `palette_world.hex` leaving out the reserved red
     and blue), then `remap_reserved.py` on anything that still lands on one.
     The enemy kit and the title may use the full palette.
- Tint shaders need their own exclusions. A crowd tint that includes yellow
  and orange can read as bare skin; leave those out of the tint colours.

## 10. Art first? The waiver branch

The default is no production art until the grey-box loop has passed the
playtest gate (`production-playbook.md`). Users sometimes waive it to lead
with the visuals. When they do:

1. **Record the waiver** in `docs/handoff.md` (date, the user's words, who
   decided).
2. **Say the cost once.** Location art made before the layout settles is
   usually thrown away: backgrounds get redone many times as the design moves
   (sprites on a painted backdrop, painted per-area backdrops, tile terrain,
   one painted map, the map repainted per screen) and can end as plain ground
   after a redesign. Most of the credits spent early on terrain and maps get
   shelved. The character, creature and building kits survive every pivot.
3. **Do redesign-safe art first**: mood frame, palette, style anchor,
   character, creature and building kits, icons, title.
4. **Defer location art** (maps, painted backgrounds) until the layout and the
   size of play areas settle (`large-backgrounds.md` §1): work on the
   mechanics and sprites first, then the map look once the play areas have
   their final size.

## 11. Reuse, tint and code before generating

Check what exists before paying for anything. Keep the asset inventory in
`docs/assets.md` and read it before every batch; assets that exist but are
never used are common.

- **Reuse and tint.** A secondary character can be a tinted copy of an
  existing sprite at 1x; per-level crowd colours can come from one tint
  shader; a new level can reuse an existing creature until its own frames
  exist.
- **Composite.** A big pile can be three large pile sprites grouped.
- **Code motion.** Hop, squash, bob, tilt and flap-then-coast often read better
  than generated frames, and below about 20 px they are the only thing that
  reads (`animation.md`).
- **Code-drawn effects beat effect sprites for variety.** Effect sprites tend
  to look too much like a cartoon and repeat; procedural effects randomised on
  every use don't. Keep waves, wakes, rain, darkness and spray in code too.
  Effects are motion, not pictures.
- **Leave out what code will animate** (an empty brazier, a windmill without
  sails, no smoke or falling snow) so the art has slots for it
  (`magnific-pipeline.md` §7).
