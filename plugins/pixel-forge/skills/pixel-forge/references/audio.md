# Audio

Sound effects, ambience and music: placeholders, generating with Magnific,
checking what you can't hear, and wiring it into Godot so it never clicks,
stalls or stays ducked.

Commands use `python "$FORGE/scripts/..."` (vendored as `tools/forge/` inside a
game). If `python` is the Windows Store stub, use `py -3` or `python3`. Flags
shown are the common ones; `--help` is the authority. ffmpeg and ffprobe are
checked by `doctor.py`.

## Contents
1. Policy
2. Placeholders: synth_sfx.py, synth_music.py
3. Sound effects with Magnific
4. Music with Magnific
5. Checking what you can't hear
6. Loudness and the mix
7. Formats, loops and size
8. In Godot: buses, voices, beds, playlist
9. Ducking, pausing and the app lifecycle
10. Web pages and web builds
11. Taste: what to record

---

## 1. Policy

- **Placeholders first.** Synthesised sounds go in as soon as a mechanic needs
  feedback; filenames are the contract, so real sounds drop in later with no
  code change. A whole prototype can run on synthesised effects, beds and
  music; stay on placeholders until the user asks for generated audio.
- **The user's own sounds win.** If the user has their own music or a sound
  they like, use it; a generated cue may end up replaced by the user's own
  file after a round or two.
- **Say you can't listen.** "I can't listen to them myself, so both files are
  attached for you to preview." Then verify by numbers (§5) and send the files.
- **Generated audio downloads work in Claude Code** (curl on the signed URL,
  same as images; `magnific-pipeline.md` §4). In the claude.ai sandbox the user
  downloads it.
- **Keep the most frequent cue plain.** A cue that fires dozens of times a
  level stays a plain synthesised tone; anything with character in it grates.

## 2. Placeholders: synth_sfx.py, synth_music.py

```bash
python "$FORGE/scripts/synth_sfx.py" --list                                      # the 36 presets
python "$FORGE/scripts/synth_sfx.py" --preset rain-loop -o audio/rain_loop.ogg
python "$FORGE/scripts/synth_sfx.py" --preset tone -o audio/hit.wav --freq 220 --seconds 0.2
python "$FORGE/scripts/synth_sfx.py" --all audio/placeholder --format ogg       # every preset at once
python "$FORGE/scripts/synth_music.py" --example adventure > audio/songs/adventure.json  # start from a built-in
python "$FORGE/scripts/synth_music.py" audio/songs/adventure.json -o audio/music_adventure.ogg
```

- `synth_sfx.py` has 36 presets: beds (wind, rain, storm, crickets, crackle,
  crowd, festival), one-shots (hit, blip, coin, chime, pop, chop, hammer, splash,
  bang...), rewards (purchase-arp, sparkle-arp, grain, complete, fanfare) and
  weather (thunder, thunder-roll, rumble, gust). Loops are written seamless.
  `--seed` gives another take of the same sound; `--variant` picks one of a
  preset's variants. OGG and MP3 need ffmpeg (without it you get WAV and a
  warning). The positional form (`synth_sfx.py wind-loop -o ...`) also works.
- `synth_music.py` builds a seamless loop from a JSON song spec (bpm, chords,
  arpeggio, melody, drums, levels, seed), normalised to `--peak -12` dBFS and
  `--rms -25` dBFS by default, written as WAV, OGG or MP3. Its built-ins
  (`--list`: menu, calm, adventure, journey) are soft triangle pads, a sparse
  pulse arpeggio and a triangle bass. `--demo NAME` renders one directly.
- **Phone speakers can't play sub-bass.** Raw brown noise (in thunder, for
  example) is about 6x hotter than the mid band, so an untuned mix is pure
  sub-bass a phone speaker cannot reproduce at all. Set layer gains by
  measured RMS.

## 3. Sound effects with Magnific

`audio_sfx_generate`:

| Param | Value that works |
|---|---|
| `durationSeconds` | 1–4 |
| `variations` | 3 (play one at random in game) |
| `promptInfluence` | optional, 0.5 |
| Cost | about 10 credits each (at the time of writing) |

- **End every prompt with "no voice, no music".**
- Describe the reward, not just the object. Template:

  > Video game <reward type, e.g. power-up> chime crossed with <a familiar
  > sound, e.g. a cash register deposit>: a bright rising synth sparkle, <the
  > familiar layer, e.g. a soft register 'ka-ching' with a coin drop>, and
  > underneath a subtle <material layer: the sound of the thing collected
  > landing>. Short, rewarding, clean, close mic, no voice, no music

- Delivery: download to `audio/`, register it in the sound table, and give it a
  per-cue trim knob in code (for example an `SFX_TRIM` table). Report the
  credits.

## 4. Music with Magnific

`audio_music_generate` (credits at the time of writing):

| Model | Use | Typical |
|---|---|---|
| `google-lyria-3-pro` | Full loops and playlist tracks | 170–180 s per track, about 160 credits |
| `elevenlabs-music-generation-v2` | Short stingers and promo beds | 16 s instrumental, a few hundred credits |

**Lyria recipe:** tempo, mood or key, instruments, texture, a scene, then the
fixed suffix:

> <tempo, e.g. 72 BPM>, <mood and instruments, e.g. minor Rhodes, music box>,
> <texture, e.g. fireplace crackle / vinyl / tape>, <the scene, e.g. "a quiet
> town on a rainy afternoon">. No vocals. Steady groove all the way through,
> no long intro and no fade-out.

- The suffix keeps tracks loopable and crossfadable.
- **The content filter rejects some words silently.** A prompt containing
  "study beat" can be rejected, and so can a retry containing "breathy". A
  plain rewording passes. If a generation returns nothing, reword before
  retrying.
- **Stingers** (ElevenLabs): give the shape in seconds, e.g. "builds to a big
  hit around 11 seconds... final stinger".
- Iterate by the mood words the user gives ("brighter", "more lo-fi", a scene
  and a time of day).
- Post-process every track (§7) and keep the raw file as `*_raw.mp3`.

## 5. Checking what you can't hear

- **Duration** with ffprobe, against what you asked for.
- **Peak level** (dBFS) and, for music, RMS or integrated loudness.
- **Loop seam**: compare the last and first samples (level and slope) of a loop;
  a jump is a click.
- **Silence**: no long silent head or tail on playlist tracks.
- Send the files (and say which numbers you checked: peak level and loop seam
  at least), then wait for the user's ear.

## 6. Loudness and the mix

- **Effects in front, music under** is a good default; confirm it with the
  user. Normalise music to −12 dBFS peak and run the Music bus at about 50%
  (about −25 dB RMS before the bus) so the music stays subtle and the effects
  carry the game.
- **Normalise music; trim effects in code.** Effects measuring RMS anywhere
  from −35 to −18 dBFS can be deliberate: a quiet pickup is meant to be quiet,
  so normalising the effect FILES would be wrong. Use one per-cue dB trim
  table instead.
- **Line up tracks from different sources** with one loudnorm pass to
  I = −18 LUFS, true peak −1.5 (`audio_encode.py loudnorm`, two-pass; music on
  a web page uses the same `loudnorm=I=-18:TP=-1.5:LRA=11`). Then the Music
  slider means the same thing for every track. Leave effects alone.
- **Timing between senses:** fire a lightning flash before its thunder with a
  random 0.15–1.3 s gap.

## 7. Formats, loops and size

- **Ship OGG or MP3 at 128 kbps, 44.1 kHz, not WAV.** Music dominates a mobile
  build: a couple of dozen tracks at 48 kHz stereo (about 195 kbps) can be
  most of a debug APK, and re-encoding at 128 kbps / 44.1 kHz cuts them by
  about a third with no code change. Re-committing multi-MB music WAVs on
  every regeneration bloats the repo pack to hundreds of MB.
- **Loops must be OGG.** Godot loops Ogg sample-accurately; MP3 cannot.
- **Re-encode with `audio_encode.py`** (ffmpeg wrapper with three subcommands:
  `loudnorm`, `reencode` at 128k / 44.1 kHz, `probe`). Every output is checked
  with ffprobe against the source duration, sizes before and after are
  printed, and encoding a loop to MP3 prints a warning. Inputs are files,
  folders (`--recursive`) or globs; names are kept. Then re-import, run the
  smoke test, and give the user a one-line rollback
  (`git checkout HEAD -- audio/<file>`):
  ```bash
  python "$FORGE/scripts/audio_encode.py" loudnorm audio/music -O audio/music_norm
  python "$FORGE/scripts/audio_encode.py" reencode audio/music_norm -O audio/music --format ogg
  # keep the same MP3 filenames: smaller files, no code change
  python "$FORGE/scripts/audio_encode.py" reencode audio/music --format keep --rate 44100 --in-place
  python "$FORGE/scripts/audio_encode.py" probe audio/music
  ```
  It finds ffmpeg on PATH, in `$FFMPEG`, or under WinGet's packages folder
  (`--which` shows where).
- **Set a music budget** early; music dominates mobile build size
  (`mobile-export.md`).

## 8. In Godot: buses, voices, beds, playlist

- **Buses.** Master → SFX, Music, Ambience, with a MusicTrack bus under Music.
  The player's slider owns Music; ducks move MusicTrack, so a duck never
  overwrites the user's volume. Track fades move the players while ducks move
  the bus, so they never fight over one `volume_db`. Buses can also be created
  at runtime (template: `assets/godot/session.gd`).
- **Loop flags in code.** `stream.loop_mode = AudioStreamWAV.LOOP_FORWARD` for
  WAV beds, `stream.loop = true` for OGG beds, and `loop = false` on playlist
  tracks ("Looping must be OFF or the track never ends and the playlist
  stalls"). Loop flags in `.import` files are easy to lose.
- **Voice pool.** Round-robin `AudioStreamPlayer`s (6–14, depending on how busy
  the soundscape is), a per-sound voice cap that steals the oldest (for
  example 3 for pickups), every stream preloaded in `_ready` (no first-play
  hitch), and `PROCESS_MODE_ALWAYS` so menu sounds play while paused.
- **Play world sounds only when visible.** An `sfx_near()` helper plays only
  when the camera can see the source.
- **Beds ease, never click.** Move bed volumes with `move_toward` each frame;
  never set them in a jump.
- **Crossfaded playlist** (`assets/godot/music.gd`): two players on the Music
  bus, `PROCESS_MODE_ALWAYS`, an **equal-power** (cos/sin) crossfade (about
  5 s) started when `stream.get_length() - get_playback_position() <=
  FADE`, because there is no "about to finish" signal. Linear dB on both sides
  dips in the middle. First track fixed, the rest shuffled, no back-to-back
  repeat on reshuffle. **Never leave silence between tracks**: pauses of
  several seconds between tracks feel broken; fade between them instead.
- **Re-apply the base level** when the same playlist carries into the next
  level instead of restarting; skip it and the next level opens barely
  audible.
- **Load the next track early.** Loading a stream on the frame it starts gives
  a 1–2 frame stutter; preload it (on a thread if needed).

## 9. Ducking, pausing and the app lifecycle

- **Every exit path restores the duck.** Music stays ducked across levels
  unless every reset path restores it. Add a smoke check: duck, change level,
  assert the bus level is back.
- **Stings pause the music** (`stream_paused`) rather than ducking it. Ducking
  MusicTrack for a sting leaves the event beds on Music at full volume.
- **Pause-proof fades.** A crossfade frozen by the pause panel makes the first
  song of a level barely audible; music tweens use `TWEEN_PAUSE_PROCESS`.
- **Lifecycle:** on focus loss or `APPLICATION_PAUSED`, pause behind the pause
  panel, mute Master and save; on resume, unmute only and never auto-resume
  gameplay.
- **Settings sliders:** 0 means mute the bus (not −80 dB); convert with
  `linear_to_db`; apply live; store on drag end or panel close.
- More engine traps: `godot-gotchas.md`.

## 10. Web pages and web builds

For music on a web page or in a web build:
- Browsers block autoplay until a user gesture. Try to play; if blocked, start
  on the first gesture anywhere on the page.
- iOS ignores element volume, so crossfades don't work there; play tracks
  back to back.
- Routing through WebAudio gets blocked harder; avoid it for background music.
- Keep the controls minimal by default: autoplay, one Play/Pause control, no
  title or volume unless the user asks for them.

## 11. Taste: what to record

Record audio preferences in the bible's Taste section (`art-direction.md` §7)
as they come up. The kind of note worth keeping:

- **Ambient loops:** a constant loop may get rejected in favour of sparse,
  varied events (for example two crickets with two-tone chirps, three high
  pulses then three low, and 1.5–4 s rests).
- **Reward sounds:** a patter that builds while the reward flies to its
  counter and ends on a two-note chime as it lands; a different material
  sound per resource (knocking logs, clacking stones).
- **Level-up / rank-up:** a festive fanfare rather than a horn.
- **Cash-in style cues:** which way to push ("less slot machine, more power-up
  crossed with a deposit, with a subtle material sound underneath"); the user
  may end up supplying their own file.
- **Music:** level relative to effects; crossfade or gaps; moods named by
  scene and time of day.
