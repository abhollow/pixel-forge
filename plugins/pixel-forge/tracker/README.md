# Idea → Launch tracker

A private project dashboard that lives on claude.ai and checks itself every morning. Each project shows its icon, a progress bar from idea to launch, git health and momentum. A project-manager mascot (Pip by default; give it your own pixel-art portrait or keep just its initial) writes one piece of advice a day and answers questions. You can capture ideas from your phone, press **Start**, and the next morning the folder, git repo and (if you want) private GitHub repo exist.

- **Brain dump** at the top: Enter saves an idea, Shift+Enter adds a line. Each idea has Delete (with Undo) and Start (name, folder, GitHub private / public / local only). Add `#idea` to the page URL for a phone home-screen shortcut that opens straight into it.
- **The desk:** the mascot's daily note, today's focus, up to six nudges (its own first, then ones the page works out: local-only repo, unpushed commits, uncommitted changes, 7+ days without a commit, close to the next stage), and an **Ask** box with three quick questions.
- **The trail:** the nine stages, with every active project's icon where it stands.
- **In development:** stage, momentum (Blazing / Warm / Cooling / Frozen from 14 days of commits), git badge, blocked and parked chips, a big legible percentage, a 14-day heat strip, and details (blocker, since the last check, next up, a progress sparkline, Mark as shipped, Create GitHub repo).
- **Shipped ledger:** version, links, "Idea to launch in N days".
- **Header:** a plain gradient by default, or your own pixel-art image, optionally animated (snow, chimney smoke, firelight, twinkling stars; see "Your own header image"); a sync pill that turns amber when a check was missed, and an optional lo-fi radio with only a Play/Pause button.
- Reduced motion shows a still frame. The animation pauses off-screen and in hidden tabs. Stats, levels and badges are built but off (`gamification: false`).

## How it works

```
 phone / any browser                                   your computer (Claude desktop app open)
┌──────────────────────────────┐                      ┌──────────────────────────────────────────────┐
│ claude.ai artifact page      │                      │ scheduled task "idea-to-launch-morning-check"│
│  idea-to-launch.html         │                      │  runs ~5 AM in the projects root             │
│  brain dump, Start, Ship,    │  live onSnapshot     │                                              │
│  Create GitHub repo, Ask ────┼─── sample (viewer's  │  1 ArtifactData list/get  ──────────────┐    │
│                              │    Claude usage)     │  2 ONE helper command:                  │    │
└──────────────┬───────────────┘                      │    tracker-sync.ps1 / tracker_sync.py   │    │
               │ writes "queued" flags                │    -> JSON {now, setups[], repos[]}     │    │
               v                                      │    (git stats, new folders, gh repos,   │    │
┌──────────────────────────────┐                      │     icon copies)                        │    │
│ artifact database            │ <── ONE pinned ──────│  3 Read docs/status.md, CLAUDE.md,      │    │
│  projects/<id>               │     batch write      │    README, handoff, CHANGELOG           │    │
│  meta/sync   meta/coach      │     (if_version)     │  4 progress, summary, next, coach note ─┘    │
└──────────────────────────────┘                      └──────────────────────────────────────────────┘
```

The page holds no data. Everything is in the artifact's database, so you can republish the page (new look, new mascot) at the same URL without losing anything.

## Stages

The same table drives the page, the morning check and each project's `docs/status.md` (`stages.json` is the canonical copy).

| id | Stage | Progress | Leave the stage when |
|---|---|---|---|
| `idea` | Idea | 0–9 | the project has its own folder |
| `concept` | Concept | 10–19 | pitch, hook, comparables and scope are in `docs/concept.md` |
| `design` | Design | 20–34 | `docs/bible.md`, `forge.json` and a locked palette exist |
| `prototype` | Prototype | 35–49 | the grey-box loop is playable and the playtest gate is answered or waived in writing |
| `core` | Core build | 50–64 | the core loop works end to end and the art direction is locked |
| `content` | Art & content | 65–79 | every needed asset is at acceptable quality and content lives in data |
| `polish` | Polish & test | 80–89 | a full session runs with no placeholders, human playtests are done, the smoke test is green |
| `launch` | Launch prep | 90–99 | release build signed, store page ready, trailer made |
| `shipped` | Shipped | 100 | public release |

Progress moves 0–3 points a day and only on evidence, jumps only on a clear stage change, and never drops unless the notes record a redesign. Only clear evidence of a public release marks a project shipped; otherwise you press **Mark as shipped**.

## What's in this folder

| Path | What |
|---|---|
| `page/idea-to-launch.html` | The page. One self-contained file; everything personal is in the `CONFIG` block at the top. |
| `mascot/make_mascot.py` | Turns a generated portrait on green into a small transparent PNG (see below). |
| `sync/tracker-sync.ps1` | Sync helper for Windows PowerShell 5.1+. |
| `sync/tracker_sync.py` | The same helper in Python 3 for macOS, Linux and Windows. Same flags, same JSON. |
| `sync/tracker.config.example.json` | Example `tracker.config.json`. |
| `tasks/morning-check.md.tmpl` | The scheduled-task prompt with `{{PLACEHOLDERS}}`. |
| `stages.json` | The stage table. |

No artwork ships with the tracker: the header is a gradient and the mascot shows its initial until you add images of your own.

## Set it up

The quick way: run **`/pixel-forge:tracker-setup`** in Claude Code (desktop app) and answer three questions. It does everything below.

By hand:

1. **Working folder.** Make `<projects root>/_tracker/` (folders starting with `_` are never treated as projects). Copy in the page and the helper you'll use, plus your own header image and mascot portrait if you have them (both optional).
2. **Config.** Edit the `CONFIG` block (table below). On Windows set `pathSep: "\\"`.
3. **Publish.** Ask Claude to publish `_tracker/idea-to-launch.html` as an Artifact with any header image, mascot image and tracks as supporting files and capabilities `{db: {}, assets: {}, user: {}, sample: {}}`. Note the URL.
4. **`tracker.config.json`** next to the helper: `{ "root": "<projects root>", "gitignoreTemplate": "godot" }` (`godot`, `node` or `generic` picks the `.gitignore` for folders started from the page). A relative `root` is relative to this file.
5. **Seed.** Run the helper once with `-DryRun` / `--dry-run` and add a `projects/<id>` document per folder (status `active`, `folder`, git fields) plus `meta/sync`.
6. **Scheduled task,** created from a session whose working folder is the projects root (see the lesson below): fill `tasks/morning-check.md.tmpl`, schedule it daily (for example cron `0 5 * * *`).
7. **Run it once with you watching** and choose "Always allow" for the helper command and for `ArtifactData`.
8. **Phone:** open `<artifact URL>#idea` signed in to claude.ai and add it to the home screen.

### CONFIG

| Key | Default | Meaning |
|---|---|---|
| `title`, `tagline` | "Idea → Launch", generic line | Header text. The arrow is drawn in amber. |
| `about` | `""` | What you make, for the mascot's advice ("mostly pixel-art mobile games in Godot"). |
| `projectsLabel`, `pathSep`, `machineLabel` | `PROJECTS`, `/`, `this computer` | How folders and your machine are named on the page. |
| `checkTimeLabel`, `staleHours` | `5 AM`, `26` | When the check runs; when the sync pill says a check was missed. |
| `mascot` | Pip, no image | `name`, `role`, `img` (`null` shows the name's initial), `size` (native pixel grid, shown 1× and 0.5×), `alt`, `glyph`, `persona` (the prompt the Ask box sends; the morning check uses the same text). |
| `tracks`, `radio` | `[]` | MP3 files next to the page. Empty hides the radio. `volume`, `crossfadeMs`, `leadSeconds`. |
| `scene` | `null` | `null` for the plain gradient header, or your own header (an object, or the path of a JSON file holding it): see below. |
| `gamification` | `false` | XP, levels, streaks and badges. |
| `stages` | the table above | `id`, `name`, `min`, `glyph`, `color`. |

### Your own header image

Generate a wide pixel-art scene (about 21:9) with open sky on the left for the title and **leave out anything the page animates** ("no chimney smoke, no falling snowflakes"). Pixelize it at about 640 px wide with about 200 colours, no dither: at 480 px and 48 colours, small details (a figure in a window) disappear. Publish it next to the page as `header.png` and set `CONFIG.scene = { img: "header.png", alt: "..." }`. That alone gives a still header. Each effect below is optional and switched on by adding its key; coordinates are pixels of the image (find them by cropping with a 4 px grid overlay). You can also keep the object in a `scene.json` published next to the page and set `CONFIG.scene = "scene.json"`.

| Key | Example | Effect |
|---|---|---|
| `img`, `alt` | `"header.png"`, a one-line description | The image (required) and its text for screen readers. |
| `focus` | `"68% 72%"` | Which part stays in view when the header crops (CSS `object-position`). |
| `starRegion` | `{x0: 1, y0: 1, x1: 360, y1: 85}` | Bright isolated pixels inside this box twinkle (bounds exclusive). |
| `chimney` | `{x: 516, y: 16}` | Where smoke puffs start. |
| `fire` | `{x0: 416, x1: 428, base: 206}` | Columns of flickering flame tongues, and their bottom row. |
| `fireRect` | `{x0: 402, y0: 184, x1: 442, y1: 213}` | Warm pixels inside this box get an extra fire layer. |
| `halo` | `{x: 422, y: 201, r: 34}` | A round glow around the fire. |
| `spill` | `{x: 425, y: 224, r: 120, squash: 0.26}` | Flattened light spilling onto the ground. |
| `roofLine` | `{x0: 413, x1: 544, y0: 25, slope: 0.145}` | Gusts strip powder off this line (y = y0 + (x − x0) × slope). |
| `warmPixels` | `{rMin: 160, rOverB: 60, gOverB: 5}` | Which pixels count as window light. The glow layers are computed from the image's own warm pixels, so any lit scene works; `glow: false` switches them off. |
| `flakes` | `1400` | Snow amount; 0 or absent = none. |
| `wind`, `fireIntensity`, `flickerSeconds`, `smokeEvery`, `fps` | 1, 1, 0.09, 0.15, 33 | Gust strength, flicker depth (0.5 calmer, 0 steady), flicker speed, seconds between smoke puffs, frame rate. |

## Project status files

The morning check prefers facts over guesses. If a project's `docs/status.md` starts with YAML front matter, it is used first:

```yaml
---
stage: prototype        # a stage id
progress: 42            # optional, inside the stage's band
next: [Grey-box the core loop, Ask two friends to play it]
blockers: null
parked: false           # parked projects get no "7 days without a commit" nudge
updated: 2025-01-15
---
```

A `forge.json` with `"tracker": {"id": "my-game", "icon": "icon.png"}` fixes the project's document id and icon. Without one, the helper's `-Icons` looks for `project.godot`'s `config/icon`, then files named `icon*`, `app_icon` or `logo` (skipping `.godot`, `.git`, `raw*`, `video`, `capture`). A root `icon.png` is the surest.

## Database

- `projects/<kebab-id>`: `name`, `kind`, `status` (`idea` | `active` | `shipped`), `progress`, `stage`, `folder`, `icon` (asset id, served at `/_blob/<id>`), `pixelArt`, `summary`, `recent[]`, `next[]`, `blockers`, `parked`, `lastCommitAt`, `commits7d`, `commitsTotal`, `firstCommitAt`, `activity{date:n}`, `git{isRepo, remoteUrl, branch, upstream, ahead, behind, dirty, at}`, `startedAt`, `shippedAt`, `version`, `links[]`, `history[{d,p}]` (60 at most), `checkedAt`.
  Ideas: `status: "idea"`, `note`, `name`, `createdAt`, `source: "brain-dump"`. Setup flow: `setup` (`queued` → `done` | `error`) + `folderRequested`, `setupError`; `github` (`private` | `public`) + `githubStatus` (`queued` → `done` | `error`), `githubUrl`, `githubError`.
- `meta/sync`: `{lastRun, by, summary, lastQuick}` (`lastQuick` = when git stats were last read; the page shows it as "Git synced …").
- `meta/coach`: `{date, message, focus{id, title, why}, nudges[{id, kind, text}]}`, kind `attention` | `momentum` | `tip`.

## The sync helper

```
powershell -NoProfile -ExecutionPolicy Bypass -File tracker-sync.ps1 [-Root DIR] [-Req "..."] [-Icons] [-IconsDir DIR] [-DryRun]
python3 tracker_sync.py [--root DIR] [--req "..."] [--icons] [--icons-dir DIR] [--dry-run]
```

- Reads every top-level folder of the root (skipping `_*` and `.*`): git stats for repos (one level of nested repos too, e.g. `GAME/game-repo`), the newest file time otherwise. Uses `git --no-optional-locks status`, so it never writes into a repo while reading.
- `-Req "id|folder|name|create|github|note;;..."` sets up started projects: `create` 1 makes the folder with README, `.gitignore`, `git init -b main` and a first commit, and refuses existing folders and odd names; `github private|public` runs `gh repo create --source --remote origin --push` with a free kebab-case name (`-2` … `-5` if taken), and refuses repos that already have a remote. Without `gh` it reports an error instead.
- `-DryRun` creates nothing (no folders, commits or GitHub repos) and reports what it would do. `-Icons` still writes its icon copies, which live in the tracker's own folder.
- Output: one JSON object `{now, setups[], repos[]}`. Both helpers print the same fields in the same order.

## Choices and trade-offs

- **claude.ai artifact database (the default).** No server. The page works from any device when your computer is off, and Ask runs on the viewer's own Claude usage through the `sample` capability. The cost: things you start on the page wait for the next check (up to a day), and the check runs only while the Claude desktop app is open. A missed run fires the next time the app starts, so the page says "around 5 AM" and flags a check older than 26 hours.
- **A server on your home network.** Folders appear instantly, but the page is dead whenever the computer sleeps, it needs something like Tailscale away from home, and Ask needs an API key. More to run for a small gain.
- **Extra syncs during the day.** A second, lighter task (git badges and setups only) every few hours would keep badges fresher, but every run spends Claude usage and adds a session to the list. One rich daily check is usually enough.

## Permissions: one command, one "Always allow"

Unattended runs stall on the first permission prompt, so the task is designed around exactly one shell command (the helper) plus `ArtifactData`, with `Read`/`Glob`/`Grep` inside the projects root, which is the task's working folder. No git, no file writes, no image tools.

1. After creating the task, **run it once while you watch**. Approve the helper command and `ArtifactData` with **"Always allow"**. Later runs then go through on their own.
2. Claude can't add permission rules for itself. If you'd rather pre-approve, paste this into `~/.claude/settings.json` yourself (allow rules there also apply to scheduled-task sessions), with your own path:

```json
{
  "permissions": {
    "allow": [
      "PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\Users\\you\\Projects\\_tracker\\tracker-sync.ps1\" *)",
      "ArtifactData"
    ]
  }
}
```

On macOS or Linux use `"Bash(python3 \"/Users/you/Projects/_tracker/tracker_sync.py\" *)"` instead. The trailing ` *` also matches the bare command, so one rule covers runs with and without `-Req`. Keep the rule exactly as the task runs the command. If the approval prompt names the database tool differently, use that name.

## Create the task from the projects root

A scheduled task runs in the working folder of the session that created it. A task created from a temporary scratch session runs in a folder that later disappears, and every check then fails to read the projects. Before creating the task, make sure the session's working folder **is** the projects root (switch to it first). The setup skill checks this.

## Make a mascot from your own image or photo (Magnific)

Any small pixel-art portrait on a transparent background works as `CONFIG.mascot.img`. To make one from a photo (a pet, a toy, a drawing, yourself):

1. Crop the photo to the head and shoulders (any editor or PIL) and save a JPEG or PNG.
2. Upload it as a reference: `creations_request_upload` (`mimeType: "image/jpeg"`) → `PUT` the file bytes to the returned URL (`curl -X PUT --upload-file head.jpg "<url>"`) → `creations_finalize_upload` with the returned `path` and a `fileName`. Keep the creation identifier.
3. `images_generate` with `mode: "imagen-nano-banana-2"` (listed as Nano Banana Pro), `aspectRatio: "1:1"`, `count: 3`, `references: [{type: "image", identifier: "<id>"}]` and a prompt like:
   > Pixel art portrait of the exact `<subject>` in the reference photo, head and shoulders, friendly expression. Keep its real markings and colours. 16-bit style, crisp hard-edged pixels, limited palette, no anti-aliasing, no text. Flat pure green #00FF00 background.

   Name the subject plainly in place of `<subject>`. Check the cost first with `simulate_cost`.
4. Download your pick (`creations_register_download` gives a signed URL; fetch it with curl into `raw_art/`).
5. Convert: `python3 mascot/make_mascot.py raw_art/pick.png mascot.png 112 36`. It BOX-resizes to a 112 px grid, keys the green by flood fill from the border, cleans the green fringe and reduces to about 36 colours with transparency.
6. Publish `mascot.png` with the page and set `CONFIG.mascot` (`img`, `size: 112`, `name`, `alt`, `persona`).

## Music for the radio (Lyria)

Generate with `audio_music_generate`, `model: "google-lyria-3-pro"`, `durationSeconds: 170`–`180`. At the time of writing that's about 160 credits per three-minute track. A good prompt gives BPM, mood or key, instruments, texture (vinyl crackle, tape warmth) and a scene, and always ends with the same line:

> Lo-fi hip-hop at 88 BPM, warm and bright, for a slow, sunny morning. Mellow Rhodes chords, soft plucked guitar, dusty drums, round bass, light vinyl crackle. **No vocals. Steady groove all the way through, no long intro and no fade-out.**

- The content filter can reject a prompt **silently** over a single word (phrases like "study beat" or "breathy" have tripped it). Plain rewording passes.
- Normalize so tracks sit at the same level: `ffmpeg -i raw.mp3 -af loudnorm=I=-18:TP=-1.5:LRA=11 -ar 44100 -b:a 128k morning.mp3`. Keep the raw files.
- Publish 3–5 tracks (2–3 MB each) next to the page and list them in `CONFIG.tracks`. The radio shuffles, crossfades 4.5 s before each track ends, starts on the first tap if the browser blocks autoplay, and plays tracks back to back on iPhones, which ignore volume.

Some themes to start from:

| Theme | Starting point |
|---|---|
| Slow Morning | 80 BPM, warm Rhodes, soft brushed drums, light vinyl crackle |
| Rainy Window | 72 BPM, minor-key piano, rain on glass, tape hiss |
| Deep Focus | 85 BPM, steady minimal groove, warm keys, no lead melody |
| Arcade Dusk | 90 BPM, lo-fi drums under soft chiptune leads |
| Night Drive | 95 BPM chillhop, round bass, hazy synth pads |
| Sunday Market | upbeat lo-fi, plucky guitar, light percussion |

## Good to know

- **Ask** runs on the viewer's Claude usage. If sampling isn't available, the box hides itself.
- No artwork or music ships with the tracker. Anything you add (a header image, a mascot portrait, tracks) is yours and is published only with your own copy of the page.
- Everything personal (names, paths, the mascot, the music) lives in `CONFIG`, `tracker.config.json` and the scheduled task's prompt, never in the shared code.
