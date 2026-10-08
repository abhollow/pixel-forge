# Magnific MCP → game asset pipeline

How to generate art (and audio) with the Magnific connector, get it onto disk,
and keep a record that outlives expiring links. Tool names are from the
Magnific MCP connector; parameter sets change between versions, so if a call is
rejected, read the live tool schema rather than guessing.

Read `art-direction.md` first (the look and the loop), then this, then
`art-pipeline-lessons.md` (cutting and cleaning) and `pixel-conversion.md`.

## Contents
1. Environment: who downloads
2. Order of operations
3. Before you spend: balance, models, cost
4. Downloads and uploads
5. The ledger and batch records
6. Consistency: anchor and family references
7. Prompt recipes
8. References override prompts; user photos
9. Other Magnific tools
10. Cost control and the credit report
11. When the connector drops
12. Common failures

---

## 1. Environment: who downloads

| | Claude Code (local) | claude.ai / Cowork sandbox |
|---|---|---|
| Download outputs | **Claude does**: `curl` / `urllib` on the signed URL from `creations_wait` or `creations_register_download`. Links expire: download immediately. | CDN blocked (403). The **user** downloads each pick and uploads it into the chat. |
| Upload references | **Claude does**: `creations_request_upload` → PUT → `creations_finalize_upload` | User uploads; or use an existing creation id as the reference |
| See the result in game | Claude renders and looks (windowed `capture.gd`) | No Godot window; the user plays and reports |
| Commit | Claude commits and pushes with git / gh | `stage_push.py` zip; the user commits |

In Claude Code, Claude generates, downloads, picks, converts and places every
asset; the user never needs to download a pick. "Every pick comes through the
user" is the sandbox branch only.

## 2. Order of operations

**Claude Code:**

```
account_balance, images_models_list onlyRecommended, simulate_cost
    → tell the user the plan and the spend (unless a budget is pre-agreed)
folders_create                       once per game; pass folderReference on every call
images_generate                      count 2 once anchored, 4 for mood/exploration
    ↓                                 flat #FF00FF (#00FF00 for red/pink/orange subjects)
    ↓                                 style anchor in references[]; code while it renders
creations_wait                       returns signed pikaso.cdnpk.net URLs
fetch_art.py                         → raw_art/<batch>/, rows appended to docs/assets.md
contact_sheet.py                     options at game size → Read it → pick, with reasons
art/manifest.json line + art_build.py   key, cut, convert (art-pipeline-lessons.md)
godot --headless --import            new sprites don't draw until this runs
capture.gd                           render in game, judge against the mood frame
report                               picks, decision image, credits this round and total
```

**Sandbox:** `images_generate` → `creations_show` (the user sees the options
inline) → say exactly what to check in each option (direction, empty areas,
matching frames) → the user downloads the pick and uploads it → save it to
`raw_art/` → same cut and convert steps.

**Raw art policy.** `raw_art/` gets a `.gdignore`. Commit it if small (tens of
MB is fine); gitignore it when large and rely on the `docs/assets.md` ledger of
creation ids (`creations_get` re-issues a URL). Raw generations add up fast (a
few MB each, all options kept): gigabytes over a project. Git LFS is an option
for a large `raw_art/`. Review renders go to `docs/screens/` (gitignored)
except `docs/screens/keep/` (decision images, committed). Music ships as
OGG/MP3 at 128k, not WAV (`audio.md` §7).

**Key locally, not with `images_remove_background`.** A flat magenta or green
background keyed by the forge scripts gives hard pixel edges, costs nothing and
handles whole sheets.

## 3. Before you spend: balance, models, cost

- `account_balance` at the start of an art round. If it reports that unlimited
  generation is not active in this session, tell the user before any paid
  generation. Say what you plan to generate and roughly what it costs, unless
  the user has already authorised a budget for the batch. Report the spend
  afterwards.
- `images_models_list` with `onlyRecommended`, then `simulate_cost` for any
  batch over a few images. Slugs are confusing; check them, don't guess.

Credits are at the time of writing; check `simulate_cost` for current prices.

| Slug | Shown as | Used for | Credits |
|---|---|---|---|
| `seedream-5-pro` | Seedream 5 Pro | Mood frames, concept and pitch art, painted backgrounds | 100 per image (default/2k) |
| `imagen-nano-banana-2` | "Google Nano Banana Pro" | **The sprite workhorse**: kit sheets, icons, title, animation sheets; map sections at 4k | 75 at 2k, 150 at 4k |
| `imagen-nano-banana-2-lite` | Nano Banana lite | Cheap drafts | not measured |
| `gpt-2` / `gpt-2-mini` | GPT image | Text, layout, UI mockups | not measured |
| `auto` | auto | Ground textures, clouds | 75 |
| `images_reimagine`, `imagen-nano-banana` | | Recolour of a painted background | 50 |
| `images_reimagine`, `flux` + `keepStructure` | | `keepStructure` is **Flux only**, and Flux ignored the layout | 60 |

- Output sizes are not what you ask for. Typical: 1536x1536 (1:1), 2048x1152
  (16:9), 1152x2048 (9:16); 2k sheets about 2,560–2,750 px wide; a Nano Banana
  reimagine can return 1344x768 for a 2560x1440 source. Measure what came
  back.
- `count` is variants of one prompt in one call (1–8). **count 2** is enough
  once a style anchor exists; use **4** for mood frames and exploration; 2–4
  for most sprite rounds. Never make four separate calls.
- Rounds add up: 4 Seedream mood frames are about 400 credits, a pair of
  anchored kit sheets 150–300, and one creature with a couple of animation
  rounds can reach several hundred. Location art made before the layout
  settles is the biggest waste (`art-direction.md` §10).

## 4. Downloads and uploads

**Download (Claude Code).** `creations_wait` (poll every 20–30 s) or
`creations_register_download` returns signed URLs like
`https://pikaso.cdnpk.net/private/production/<id>/render.png?token=exp=...~hmac=...`.
Fetch them **in the same turn**:

```bash
curl -sSfL -o raw_art/b07/houses_a.png "<signed url>"
# or a whole batch: a text file of lines "label variant url [creation_id] [model]"
python "$FORGE/scripts/fetch_art.py" raw_art/b07.txt --batch b07 --prompt-ref "docs/art-prompts.md#b07"
```

`fetch_art.py` saves `raw_art/<batch>/<label>_<variant>.png`, retries (a 403
means expired or blocked), checks each file opens as an image, writes a
labelled 2x2 `sheet_<label>.jpg` to look at with `Read`, drops a `.gdignore`
into `raw_art/`, and appends rows to `docs/assets.md` (§5). Always put the
creation id on each line. `--model` fills lines that don't name one; `-` reads
the lines from stdin. If `python` is the Windows Store stub, use `py -3` or
`python3` (`windows-and-shell.md`). PowerShell's `Invoke-WebRequest` also
works. A link that has expired (old reference images often have by the end of
a project) comes back fresh from `creations_get` with the creation id.

**Upload (a local image as a reference: a style anchor, a plan, a user photo,
an old asset):**

```
creations_request_upload {mimeType: "image/png", count: 1}  → presigned proxyUploadUrl + path
curl -X PUT --data-binary @raw_art/anchor/style.png "<proxyUploadUrl>"
creations_finalize_upload {path, fileName}                  → identifier
images_generate {..., references: [{type: "style", identifier: "<identifier>"}]}
```

Reference types: `image` (follow this subject/layout), `style` (paint like
this), plus `character`, `product`, `locations`; up to 12 per call.

## 5. The ledger and batch records

The creation id is the durable handle; the URL is not. Batch files that hold
only labels and signed URLs, with the prompts unrecorded and the models only
in prose, lose the recipe behind every asset.

- `docs/assets.md`, one row per game asset:
  `game asset | raw file | Magnific creation id | model | prompt ref | notes`
  (size, palette, reference used, cutter).
- `fetch_art.py` adds one row per downloaded file under "## Raw batches":
  `Date | Batch | Label | Variant | File | Creation id | Model | Prompt ref`.
- Per batch, keep the prompt, model, resolution, aspect, references, count,
  creation ids and the chosen variant. Put the full prompt text where
  `--prompt-ref` points (for example a `docs/art-prompts.md#b07` section).
- Record which image is the style anchor and its creation id in the bible.

## 6. Consistency: anchor and family references

1. **Style anchor.** One uploaded in-game image passed as `{type: "style"}` on
   every sheet (`art-direction.md` §4). `library_create` / `@name` is
   available for a recurring character if you want to try it, but the anchor
   plus family references usually suffice.
2. **Family references.** For new members of a set, pass the earlier sheet as
   `{type: "image"}` and say "matching the reference ... EXACTLY". This builds
   consistent families: for example bronze-rimmed tablets for actions and
   buildings, gold rims for rare items, and a "charred black obsidian tablet
   with a dark iron rim and a faint red glow" for the enemy's.
3. **One sheet per character.** Every state of a character in one generation;
   separate generations drift.
4. **One prompt style.** Keep the framing, view, light and keying lines
   identical across a batch.

## 7. Prompt recipes

**Character sheet skeleton (one subject, frames in rows):**

> Retro 16-bit pixel art sprite sheet of ONE cartoon <subject> for a top-down
> three-quarter view mobile game, on a perfectly flat solid magenta (#FF00FF)
> background, no shadows on the background, no text, no grid lines.
> <palette/feature list>, chunky 1-pixel dark outline, bold and very simple
> shapes because it will be displayed only about <N> pixels wide. <Rows>:
> ROW 1 … ROW 2 … every frame the same size and scale, evenly spaced… Same
> <subject>, same colours, same size in every frame.

**Kit sheet skeleton (anchored):**

> Game sprite sheet in exactly the painting style of the reference <X>,
> everything seen from high above at the same 3/4 angle with light from the
> top-left: (1) … (6) …. Each item fully isolated with wide gaps, arranged in
> 2 rows of 3, consistent scale, on a perfectly flat solid magenta #FF00FF
> background, no ground, no scenery, no text.

Lines that do the work:

- **View, light and outline come from the bible.** A scaffolded
  `docs/art-prompt.md` can say "SIDE-ON view" in a 3/4 top-down game and go
  unnoticed; derive these words from `docs/bible.md`, not a template.
- **Size and readability:** "It will be displayed about 70 pixels wide, so
  bold, readable shapes." For tiny people: "Each will be displayed only 16
  pixels tall, so EXTREMELY bold and simple shapes, big heads, clear
  silhouettes, very few colours."
- **Isolation:** "Each item fully isolated with wide gaps", "NOT touching",
  "no ground, no scenery, no text". Ask for "no shadows on the background"
  unless you want baked ground shadows; if you do, cut the sheet raw
  (`art-pipeline-lessons.md` §3).
- **Several objects, one call, per-object sizes:** "THREE separate objects in
  one row with lots of empty space between them", then "shown about 60 pixels
  wide so keep it simple", "about 10 pixels wide so be extremely bold and
  simple" per object (for example an umbrella, a crate and a boat in one
  call).
- **Per-frame poses, facing RIGHT:** name each frame's pose; "legs alternating"
  returns near-identical frames. Recipes in `animation.md` §2.
- **View and facing:** "seen from the side", "bow pointing RIGHT", "facing
  RIGHT in every frame". Without them vehicles come back diagonal and shapes
  get misread (a round canopy reads as a skydiving parachute).
- **Family members:** "Eight more game UI icons matching the reference icons
  EXACTLY in style, size, chunky pixel-art rendering and <framing, e.g. square
  carved-stone tablet> framing..." with the earlier sheet as `{type: "image"}`.
- **Variants of one asset:** "The SAME title logo '<TITLE>' as the reference
  - exactly the same chunky letter shapes... with a new texture split cleanly
  by word". "the SAME six buildings, but <changed: e.g. CORRUPTED, ruined,
  snowed-in>..." (on `#00FF00` if the change adds reds). Nano Banana Pro
  renders logo text correctly.
- **Empty slots for what code animates:** "with an EMPTY dark iron bowl on top
  (NO fire, NO flame in the bowl)"; "a round stone WINDMILL tower... with NO
  sails at all - only the round wooden hub"; "no chimney smoke, no falling
  snowflakes". The game draws the flame, turns the sails, spawns the smoke.
- **Colour discipline:** "No saturated blue or red anywhere", "water in muted
  teal-grey, NOT saturated blue", "(no pink, no purple)" so the key and tint
  shaders stay safe. Reject sheets that break the rule; keep the alternate.
- **Key colour:** magenta `#FF00FF` by default; pure green `#00FF00` for pink,
  red or orange subjects (pink birds, fire-damaged buildings, a red or orange
  character).
- **Name the wrong answers** to stop the model adding them: "no hand holding
  it", "no text, no border, no frame, no watermark", "no ground, no grass under
  it".
- **Don't ask for the final size.** "16x16 pixel art" gets a large
  illustration *of* pixel art. Generate big, downscale locally.

**The constant block is a starting point**, useful before an anchor exists:

> retro pixel art game sprite, 16-bit era, single object centered in frame,
> flat solid #FF00FF background, crisp hard-edged pixels, limited color
> palette, 1px dark outline, top-left light source, no gradients, no
> anti-aliasing, no drop shadow, no text, no watermark, no border, no frame

For kit sheets add the view line and "no ground, no grass under it, no
scenery". Once the anchor exists, "in exactly the painting style of the
reference" plus framing and keying lines is enough; outlines and shade counts
don't need enforcing.

## 8. References override prompts; user photos

- **A reference image can override the prompt.** Sheets generated with an
  earlier option as the reference keep its flaws (stiff legs, the old
  composition), while words-only sheets can come back better; passing old art
  to fix one thing tends to return the old composition every time. When
  unsure, **run 2 with the reference and 2 without** in parallel. To change
  something the reference shows, drop the reference and describe the style in
  words.
- **Describe a user's photo in words** unless you want that exact subject;
  passing it as a reference copies it.
- **When you do want the exact subject (a portrait from a reference photo):**
  crop the head with PIL, upload it (§4),
  `references: [{type: "image", identifier}]`, prompt "pixel art portrait of
  the exact <subject> in the reference photo... Keep the real markings...",
  1:1, count 3, on `#00FF00`. Expect a faithful result in the first batch;
  pick the option with the truest pixel-art look over the one closest to a
  photo. Conversion: `pixel-conversion.md` §4.

## 9. Other Magnific tools

| Tool | Use for |
|---|---|
| `images_crop` / `images_resize` | Exact, non-AI framing fixes instead of a re-roll |
| `images_expand` | Extend a background to a new aspect ratio |
| `images_reimagine` | Recolour or restyle an existing image; returns its own size (stretch back and verify) |
| `images_variations` | A grid of variants, each its own creation |
| `images_retouch` | Change one region. Untested for animation; drawn poses work (`animation.md`) |
| `images_remove_background` | Cutouts when a flat key is impossible |
| `creations_show` | Show options inline (the sandbox's main view) |
| `creations_get` | Fresh signed URL for an old creation id |
| `folders_create` | One folder per game |
| `audio_sfx_generate`, `audio_music_generate` | See `audio.md` |

Large maps and backgrounds have their own playbook: `large-backgrounds.md`.

## 10. Cost control and the credit report

- `simulate_cost` before any batch over a few images; `count` in one call.
- **Re-roll the approach, not the seed.** Repainting a whole map with the same
  method returns the same result every time; the fix is a different method
  (per-screen sections).
- Fix small factual errors in PIL instead of re-rolling (for example, draw in
  an exact 5x5 window where the model lit about 7x7).
- Keep every raw generation (all options) in `raw_art/`. Regenerating something
  you paid for is the most common waste.
- **Defer location art** until footprints settle (`art-direction.md` §10).
- **Report credits every round:** spent this round (and on what), project
  total, balance. For example: "this round: two kit sheets and 10 SFX, about
  440 credits; project total <N>; balance <M>".

## 11. When the connector drops

If the connector drops mid-round (it reports that it "needs to be reconnected
from connector settings"):

1. Use what already landed (often most of the batch has finished).
2. Ask the user to reconnect Magnific in the connector settings.
3. Wire a stand-in into the art slot so the real art drops in later with no
   code change, and carry on with other work.

## 12. Common failures

Generation-side failures. Cutting and conversion failures are in
`art-pipeline-lessons.md` and `pixel-conversion.md`.

| Symptom | Cause | Fix |
|---|---|---|
| Boulders bigger than houses | It painted a perspective landscape | "orthographic... uniform scale everywhere, NO perspective, NO horizon" (`large-backgrounds.md`) |
| Whole map smeared into 1–2 px blobs | One image for a big map: the model paints a vista | Paint per screen and stitch (`large-backgrounds.md` §5) |
| Character or kit drifts between sheets | Describing instead of referencing | Style anchor + family `{type: "image"}` refs; one sheet per character |
| Reference kept the thing you wanted changed | Reference overrides prompt | Drop it and describe in words; run 2 with, 2 without |
| Walk frames nearly identical | "legs alternating" | Spell out each frame's pose (`animation.md`) |
| Vehicle diagonal, shape misread | View and facing not named | "seen from the side", "pointing RIGHT" |
| Direction mixed within one image | Direction is unreliable | Ask for consistency, run both ways, mirror the consistent one |
| Red roofs in a game where red is reserved | Prompt didn't forbid it | Colour lines in the prompt; pick the alternate; sub-palettes at conversion |
| `keepStructure` rejected | Flux only | Fresh generate from a flat plan + a style ref |
| Reimagine came back a different size | The model's own output size | Stretch back to the source size, verify with a crop overlay |
| Model added a frame, caption or hand | Missing negatives | "no text, no border, no frame", "no hand holding it" |
| Perspective differs between assets | Bible doesn't pin it, or the template is stale | Pin view and light in the bible; derive prompt lines from it |
| Same failure twice in a row | The prompt or the method is wrong | Change the approach; a third roll fails the same way |
| Expired link | Signed URLs carry `exp=` | `creations_get` with the creation id; or re-upload the local raw file |
| Connector "needs to be reconnected" | Session dropped | §11 |
