# Exporting to Android and iOS

Godot 4. The first export is the painful one; after that it's a button. A
first debug APK of a small pixel game easily lands around 100 MB and is not
store-ready; this file is how to see why and fix it. Release-day checks are
in `delivery.md`.

## Contents
1. Both platforms, first
2. Android
3. Debug builds vs release builds
4. Export-size checklist
5. iOS
6. Sizing assets for stores
7. Common export failures

---

## 1. Both platforms, first

1. **Export templates must match the editor version exactly**
   (`godot_version` in `forge.json`). A mismatch produces confusing failures
   that look like project bugs.
2. **Identity.** Set `config/name`, a real package / bundle id, and the
   version before the first build anyone else installs. A fresh preset still
   has `package/unique_name="com.example.$genname"` and an empty
   `version/name`, and both are easy to ship by accident.
   - `version/name`: human version plus the commit, e.g. `1.0.0+abc1234`.
   - `version/code`: increment for every upload.
3. **Icon.** One 1024x1024 PNG is the source, **nearest-upscaled** from the
   small pixel original rather than redrawn, so it matches the game.
4. **Android adaptive icons must be wired in the preset.** Making
   `icon_192.png`, `icon_fg_432.png` and `icon_bg_432.png` isn't enough: if
   `launcher_icons/*` stays empty, the APK gets a flat-colour background and
   a foreground generated from the 512 project icon. Add a smoke check:
   ```gdscript
   var cfg := ConfigFile.new()
   if cfg.load("res://export_presets.cfg") == OK:
   	for key in ["launcher_icons/main_192x192",
   			"launcher_icons/adaptive_foreground_432x432",
   			"launcher_icons/adaptive_background_432x432"]:
   		var path: String = cfg.get_value("preset.0.options", key, "")
   		check("export icon %s is set and exists" % key, path != "" and FileAccess.file_exists(path))
   ```
5. **`export_presets.cfg` is safe to commit in Godot 4.** Keystore passwords
   live in `.godot/export_credentials.cfg`, which is ignored with `.godot/`.
   Don't gitignore the presets. Grep it for `keystore|password` before each
   commit anyway (`delivery.md`).

---

## 2. Android

**Setup:**

1. Install Android Studio (for the SDK and build tools) or the standalone
   command-line tools.
2. Editor Settings → Export → Android: set the Android SDK path and Java
   SDK path.
3. Generate a debug keystore if the editor hasn't:
   ```bash
   keytool -keyalg RSA -genkeypair -alias androiddebugkey \
     -keypass android -keystore debug.keystore -storepass android \
     -dname "CN=Android Debug,O=Android,C=US" -validity 9999 -deststoretype pkcs12
   ```
   Point Editor Settings at it.
4. For a release build, generate a **separate** upload keystore and keep it
   somewhere you will still have it in five years, outside the repo. Losing it
   means you can never update the app under that listing. The user creates and
   stores it; never put its passwords in a file Claude writes.

**Export preset settings that matter:**

- **Format: AAB** for the Play Store, **APK** for sideloading and testing.
- **Min SDK**: 21 unless you need something newer. Higher cuts off devices
  for no benefit in a 2D game.
- **Target SDK**: whatever Play currently requires; this changes yearly.
- **Architectures**: `arm64-v8a` is required and enough. `armeabi-v7a`
  roughly doubles the native library size.
- **Screen orientation**: match `display/window/handheld/orientation`.
- **Immersive mode** on for a full-screen game.
- **Texture format**: with Lossless compression (as configured for pixel
  art) the ETC/ASTC options are irrelevant; you're shipping lossless PNG
  data, which is correct because pixel art files are tiny. The Android export
  adds `textures/vram_compression/import_etc2_astc=true` to `project.godot`;
  harmless.
- **Exclude filter:** `exclude_filter="tools/*, docs/*"` from day one
  (section 4).
- **Export path:** no colon in the file name; Windows signing fails with an
  `IOException` in `canonicalize`. The build writes an `.apk.idsig` (v4
  signature) next to the APK: gitignore `*.idsig`, `*.apk`, `*.aab`.

**Testing on device:** enable Developer Options and USB debugging, then
**One-Click Deploy** (the phone icon in the toolbar). Far faster than
exporting an APK each time. Otherwise the user sideloads the APK.

---

## 3. Debug builds vs release builds

Say which one you built, every time.

| | Debug APK | Release AAB |
|---|---|---|
| Purpose | The playtest vehicle on the user's phone | Store upload |
| Template | Debug | Release |
| Signing | Debug keystore | The user's upload keystore |
| Dev tools | Allowed, gated by `OS.is_debug_build()` (e.g. a DEV level select) | Must be absent: run the dev-flag grep (`delivery.md`) |
| Built from | Any commit; note the hash | A **tagged** commit; hash in `version/name` |

An APK left in the repo root and built days before HEAD still carries
whatever has since been fixed (un-re-encoded music, `tools/` scripts inside).
Rebuild from the commit you mean to test, and say which commit it is.

---

## 4. Export-size checklist

Where a first debug APK's size goes: `libgodot_android.so` about 25 MB;
imported music usually most of the rest (twenty-odd tracks at 48 kHz stereo,
about 195 kbps, comes to around 65 MB); all sprites together a few MB; plus
compiled `tools/*.gd` (smoke test, bot) and docs reference images that the
`all_resources` preset sweeps in. Music is the budget; pixel art is nothing.

1. **Exclude non-game folders:** `exclude_filter="tools/*, docs/*"` in the
   preset. Check the APK afterwards (`unzip -l Game.apk | sort -n | tail -20`
   lists the biggest entries).
2. **`.gdignore` in `raw_art/`** (and `docs/screens/`), so source art is never
   imported or exported; that keeps hundreds of MB of originals out.
3. **Re-encode music to 128 kbps / 44.1 kHz** with
   `scripts/audio_encode.py reencode audio/music --format keep --rate 44100 --in-place`
   (128k is its default bitrate; it verifies durations with ffprobe and
   reports the size saved). That keeps the same filenames, so no code changes. Then re-import,
   run the smoke test, and give the user a one-line rollback (`git checkout
   HEAD -- audio/<file>`). Expect roughly a third off the music. Never ship
   WAV music; loops go in OGG (`audio.md`).
4. **Find unused assets** before release: grep every asset filename across
   `scripts/`, `scenes/` and `data/`, **including pattern-built paths**
   (`"water2_%02d.png"`, `"%s_f%d.png"`): grep for the prefix too before
   calling a file unused.
5. **One architecture** (`arm64-v8a`).
6. **No `override.cfg`, probe scripts or test saves** in the build: they
   belong to `tools/` or are gitignored (`windows-and-shell.md`).
7. Re-measure the APK after the changes and report before/after.

---

## 5. iOS

Requires macOS and Xcode. There's no way around this.

1. Export from Godot; it produces an **Xcode project**, not an IPA.
2. Open the Xcode project, set your signing team, build to a device or
   Archive for the App Store.
3. An Apple Developer account ($99/yr) is needed to run on a physical
   device beyond a 7-day free provisioning profile, and to submit.

**Settings that matter:**

- Bundle identifier must match the App ID in your Apple developer account
  exactly.
- Provide all required launch screen and icon sizes; Godot generates most
  from your 1024x1024.
- **Privacy manifest**: Apple requires declaring data collection. A game
  with no analytics and no network still needs the manifest declaring that
  it collects nothing.
- If you add any analytics or ad SDK, the requirements grow substantially.
  For a first game, ship without them.

---

## 6. Sizing assets for stores

| Asset | Size |
|---|---|
| App icon source | 1024x1024 PNG, no transparency, no rounded corners |
| Android adaptive icon layers | 432x432 foreground and background (plus 192x192 main) |
| Play feature graphic | 1024x500 |
| Play screenshots | at least 2, 16:9 or 9:16, min 320 px on the short side |
| App Store screenshots | 6.7" (1290x2796) and 6.5" sets |

Capture screenshots at the design resolution with `tools/capture.gd` and
**nearest-upscale** them to the required size. Screen-recording a phone gives
a bilinear-filtered, slightly soft image that undersells the art. Store-page
copy and trailers: `launch-and-marketing.md`.

---

## 7. Common export failures

| Symptom | Cause |
|---|---|
| "Export templates not found" | Templates missing or version mismatch |
| `Couldn't find the given section "preset.0" and key "runnable"` | The preset was written by a newer Godot than the one reading it (e.g. CI on an older version than the editor). Pin one version |
| Android build fails at gradle | Wrong SDK path, or missing build-tools version |
| App installs but shows a black screen | `run/main_scene` not set, or the scene fails on load; check `adb logcat` |
| New art missing or drawn as rectangles | Files never imported: run `--import` (or open the editor) before exporting |
| Art found in the editor, missing in the export | Listing `res://` with `DirAccess`; use `ResourceLoader.list_directory` (`godot-gotchas.md` 7.1) |
| Art is blurry only on device | Texture compress mode wasn't Lossless and the textures weren't reimported |
| Play rejects the AAB | Target SDK below the current requirement, or missing a 64-bit architecture |
| Signing fails on Windows with `IOException` in `canonicalize` | A colon in the export file name |
| Huge build | Music bitrate first; then `tools/`/`docs/` or `raw_art/` included, or `armeabi-v7a` (section 4) |
