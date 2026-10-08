# Animation

Frames, derived cycles, code motion and effects: what each is good for, how to
generate frames that actually differ, and how to check them. Each failure
below costs at least one round if you don't know it in advance.

Commands use `python "$FORGE/scripts/..."` (vendored as `tools/forge/` inside a
game). If `python` is the Windows Store stub, use `py -3` or `python3`. Flags
shown are the common ones; `--help` is the authority.

## Contents
1. Decide first: code, derived or drawn
2. Generating frames
3. Cutting frames
4. Check the cycle
5. Derived cycles: walk and sway
6. Code motion
7. In the engine
8. Effects, and proving it animates

---

## 1. Decide first: code, derived or drawn

| Subject | Use | Why |
|---|---|---|
| Under about 20 px (critters, tiny props) | **Code motion**: hop, squash, waddle, bob | At about 18 px legs are 1–2 px, pose changes vanish, and more generations won't fix that |
| Vehicles | Bob only (`make_walk_frames.py --legs 0 --bob 1`) or a code bob | A bob reads; drawn frames add little |
| Plants, flags, foliage | Sway frames or a sway shader | `make_sway_frames.py`, `sway_sprite.gdshader` |
| Characters 24 px and up | **Two drawn poses** (contact and passing), or a generated sheet with every frame's pose named | Large enough for poses to read |
| Birds | 2–4 flap frames + flap-then-coast in code | Coasting reads better than a looping flap |
| Magic, impacts, weather | **Code-drawn**, randomised per use | Effect sprites repeat and look cartoonish (§8) |

`images_retouch` on an approved frame is an option but untested here; drawn
poses work.

## 2. Generating frames

- **One sheet for the whole cycle**, every frame in it: "every frame the same
  size and scale, evenly spaced... Same <subject>, same colours, same size in
  every frame." Separate generations drift.
- **Generate facing RIGHT and mirror in code.** Direction is unreliable, and
  the model will not draw a mirrored stride. "ALL frames facing RIGHT, exactly
  the same <subject>, same size and same colours in every frame."
- **Name every frame's pose.** "legs alternating" returns near-identical
  frames; asking for a *subtle* stride makes duplicates more likely. Template
  (here for a creature that walks sideways):

  > The LEGS MUST BE CLEARLY DIFFERENT IN EVERY FRAME, exaggerated walk poses.
  > ROW 1, <MOTION, e.g. SIDEWAYS SCUTTLE> moving to the RIGHT, <body
  > orientation, e.g. body facing camera>: frame 1 right legs stretched far out
  > right, left legs tucked under; frame 2 all legs straight down, body raised;
  > frame 3 left legs stretched far out left, right legs tucked under; frame 4
  > all legs bent, body low and tilted right.

  For a four-legged runner: "Top row: 4 frames of a galloping run cycle (legs
  gathered, legs reaching forward, legs fully stretched, legs pushing off).
  Bottom row: 4 frames of an attack...". For a slow walker: "the same
  <subject> in the same position in every frame, only the legs moving".
- **Use the approved sprite as the reference for its own cycle** so it
  matches. But a reference can also lock the pose: sheets made with an earlier
  option as the reference keep its stiff legs, while words-only sheets move
  better. When poses matter, run 2 with the reference and 2 without.
- **Directional sets:** a sideways set mirrored for left, plus toward and away
  sets chosen by the dominant axis of movement; no 45° sprites. Draw rear
  views at 3/4 so one horizontal flip covers both diagonals.
- **Sequences** (dig, hatch, spawn): name each stage. "frame 1 a small rounded
  mound of earth, nothing visible; frame 2 the mound cracking open with just
  the tips of <the creature's claws or ears> poking out..."
- **Save every option**, build `<subject>_options_at_game_size.png`, and look at
  the motion at game size before asking the user (`art-direction.md` §6).
  Skip that and the usual first verdict is that all the walk cycles look the
  same.

## 3. Cutting frames

- **Cut every frame with one shared box and one scale:**
  ```bash
  python "$FORGE/scripts/slice_sheet.py" --src raw_art/b12/enemy_run.png --prefix erun \
      --sizes 54x30 --rows 2 --shared-box --anchor bottom --clean-fringe --out-dir art/sprites
  ```
  Cropping frames separately gives a frame with a longer limb a smaller body,
  and the animation jitters. Check the cut with `--debug-sheet`.
- **One scale per character, from one measured feature.** Measure a body
  feature by its colour (a shell or torso width) so dust or debris in dig
  frames doesn't shrink the character (`--scale-by colour:HEX --feature-px P`).
  A bird uses one scale for flying and perched, set by the perched width
  (`--scale-by ref:N`).
- **Choose the anchor deliberately, and keep it between sets.**
  - Standing frames sit on the bottom edge (`--anchor bottom`).
  - If flight frames are centred while standing birds are anchored at the
    feet, the bird **drops on take-off**. Fix: lift flight frames by half
    their height.
  - A long-necked bird is aligned on its beak and body line (`--anchor right`
    for a right-facing beak); per-frame centring makes the body jump.
  - Sequences (an emerging creature): one shared box anchored on a fixed
    feature, such as the tip of the shell.
- **Thin legs and necks:** cut bigger rather than lose them (24 → 30 px often
  saves them), or widen the alpha first (`art-pipeline-lessons.md` §7).

## 4. Check the cycle

**The model draws the same pose twice.** About half of all "two drawn poses"
come back under 12% different.

```bash
python "$FORGE/scripts/check_cycle.py" art/sprites/hero_walk_f*.png            # frames in cycle order, same size
python "$FORGE/scripts/check_cycle.py" art/sprites/hero_walk_f*.png --strict   # exit 1 if anything is flagged
```

`check_cycle.py` reports two numbers per cycle; you need both, plus a look.
It flags steps less different than 12% (`--min-diff`) and drift over 25%
(`--max-drift`), and suggests mirroring frame 0 for a near-duplicate:

| Metric | Meaning | Reading |
|---|---|---|
| Motion: % of pixels that differ, widest gap **across the cycle** (not a fixed pair) | Is anything moving? | Under 8%: identical. 12%: the floor. 18–25%: comfortable. 40%+: lively |
| Drift: opaque-pixel count vs frame 0 | Structural damage | More than about 25% off: ghosted or clipped |

- On a duplicate pose, discard it and **mirror pose A in code**
  (`make_walk_frames.py --mirror-a`; a near-duplicate around 6% typically
  rises to about 16%), or regenerate with the poses spelled out.
- **The model will not draw a mirrored stride.** Asked five ways, including
  "this is not a copy of the first pose", it returns a copy every time. Design
  around it: a two-pose contact/passing cycle needs no mirrored pose.
- **Leg depth belongs to the pose.** A standing pose has its feet closer
  together: the same leg setting can give it under 9% motion against 18–26%
  for its siblings. Tune per pose, not per character.
- Compare the widest pair: a `step` cycle puts its motion in frames 1 and 3, so
  comparing frames 0 and 2 reads 0%.

## 5. Derived cycles: walk and sway

**Two genuinely drawn poses beat any amount of pixel manipulation.** Deriving a
frame instead of drawing it is the usual source of animation bugs.

`make_walk_frames.py` modes, best first. It writes `<prefix>_f0.png ...` to
`--out-dir` (default `art/sprites`) and prints `check_cycle.py`'s verdict:

```bash
# two drawn poses, A-B, no pixel operations
python "$FORGE/scripts/make_walk_frames.py" --src art/sprites/hero_a.png --src2 art/sprites/hero_b.png --pair --prefix hero_walk
# two poses with a bob: A, A+bob, B, B+bob
python "$FORGE/scripts/make_walk_frames.py" --src art/sprites/hero_a.png --src2 art/sprites/hero_b.png --prefix hero_walk
# the model drew B as a copy of A: make B by mirroring A
python "$FORGE/scripts/make_walk_frames.py" --src art/sprites/enemy_a.png --mirror-a --pair --prefix enemy_walk
# one pose: lift one leg at a time ("step") plus a bob; never mirrors anything
python "$FORGE/scripts/make_walk_frames.py" --src art/sprites/hero_a.png --prefix hero_walk --legs 0.34
# vehicles: bob only
python "$FORGE/scripts/make_walk_frames.py" --src art/sprites/cart.png --prefix cart --legs 0 --bob 1
```

What breaks, so you don't try it:
- **Mirroring a leg band flips more than legs.** At any useful depth it flips
  the torso, puts a ghost second tool on the other side, and mirrors about the
  canvas centre instead of the body. The script doesn't offer it; the `step`
  style caps its band at the bottom 34% and splits left from right at the
  content centroid.
- **The motion metric scores the breakage highly**, because a mirrored torso
  changes many pixels. That is why the drift metric exists.

`make_sway_frames.py` shifts rows by whole pixels, growing toward the top, so
the base stays planted (`--anchor`, the fraction held still) and the fronds
move; `--pad` widens the canvas so the sway never clips:

```bash
python "$FORGE/scripts/make_sway_frames.py" --src art/sprites/plant_00.png --prefix plant_sway --amp 2 --frames 4
```

For painted scenery or many sprites, a sway shader is cheaper
(`large-backgrounds.md` §10).

## 6. Code motion

Prefer code transforms to new art: scale, tint or move a sprite in code before
paying for a new generation.

- **Hop, squash, waddle.** For a small creature: a 2 px hop per step, a squash
  on landing, a 1 px waddle. At 18 px the frames alone cannot show a walk; the
  code motion does.
- **Bob.** Vehicles and boats: a whole-sprite bob; a turbulence bob for
  anything airborne.
- **Flap then coast.** "flap then hold the middle frame and coast": flap a few
  beats, hold the mid frame and glide, and **desync the phase per bird** so a
  flock doesn't flap in step.
- **Tilt.** Art drawn at a 3/4 view can be drawn rotated:
  `draw_set_transform(p, ART_TILT * _dir, Vector2(_dir, 1))` with
  `ART_TILT` around 0.44 rad, tinted per instance with `col.lightened(0.35)`.
- **Slots the art leaves empty:** a windmill generated with no sails, so the
  game turns them; an empty fire bowl, so the game draws the flame.
- **Whole pixels.** Round code offsets to whole pixels (camera drift, sway,
  shake) or the art shimmers.

## 7. In the engine

- **Negative width mirrors in place.** `draw_texture_rect` with a negative
  width mirrors the texture inside the same rect; it does not extend leftward.
  Hand-written flipped draws end up offset by their own width; use a single
  `draw_flipped()` helper for all of them (`godot-gotchas.md`).
- **Facing jitter on grid paths.** Grid paths zigzag, so every vertical leg
  flips the walker (hundreds of flips in a short probe). Keep the facing until
  the walker actually moves sideways (`if dx != 0: left = dx < 0`): the flips
  drop to a handful. Measure before and after.
- **Flip deadzone and art constants.** Keep `ART_FACES_LEFT`,
  `ART_SCALE := 2.0`, `BACK_THRESHOLD := 0.45` and a flip deadzone (e.g. 0.25)
  as named constants, not numbers buried in draw code.

## 8. Effects, and proving it animates

- **Code-drawn effects, randomised per use.** Effect sprites tend to look too
  much like a cartoon and repeat. A lightning strike reads better as multiple
  thin strikes generated at random so each looks a little different; a
  ground-shake effect wants a few different animations per use so it doesn't
  repeat. Small pixel-line helpers (line, path, oval, ring) keep code effects
  chunky.
- **Effects never touch the simulation's randomness.** Use a separate visual
  RNG so visual work can't shift balance or the bot's results
  (`architecture.md`).
- **Render several uses side by side** to check variety (several uses of each
  effect in one sheet).
- **Prove it moves.** Pixel-diff two captures: animated water should change
  thousands of pixels over about a second while land pixels stay put. A still
  frame can't show a frozen animation; `watch.gd` captures a frame every few
  seconds and catches things only visible in motion.
- **Every reset redraws.** Birds can freeze mid-air after a failed level
  because the reset emptied the arrays but never queued a redraw
  (`godot-gotchas.md`).
