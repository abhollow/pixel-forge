---
name: ship
description: Release — run the pre-ship checklist, fix what slipped, build a signed release from a tagged commit, and prepare store assets.
argument-hint: "[android | ios | itch | all]"
disable-model-invocation: true
---

# Ship

Target: $ARGUMENTS

Load the `pixel-forge` skill; read `references/delivery.md`,
`references/mobile-export.md` and `references/launch-and-marketing.md`.

## 1. Audit (report everything before fixing anything)

- **Dev leftovers**: grep for `DEV_`, `TEMPORARY`, `TODO`, `grey-box`,
  `working title`, debug overlays, cheat keys; `CLAUDE.md` *Dev flags* list.
- **Export preset**: real `package/unique_name` (not `com.example.$genname`),
  `version/name` and `version/code`, launcher/adaptive icons wired (files
  exist), release (not debug) template, `exclude_filter` covers `tools/*` and
  `docs/*`, `raw_art/` ignored, arm64.
- **Saves**: survive kill and relaunch; a corrupt or missing save doesn't crash;
  a version field exists.
- **Size**: music bitrate, unused assets, WAVs that should be OGG.
- **Devices**: real phone, 16:9 to 21:9, notch, interruption, cold start.
- **CI**: runs the project's Godot version and fails on the exit code.

List findings numbered; ask before changing anything that affects gameplay.

## 2. Fix and verify

Fix the agreed items; smoke ×2; captures of menus and each level.

## 3. Build

- Tag the commit (`git tag vX.Y.Z`) and put the short hash in `version/name`
  or the about screen, so the build is traceable.
- Export from the tag. The user handles keystores and signing passwords —
  never type them; keep the upload keystore backed up.
- Android: AAB for Play, APK for side-loading. iOS: Xcode project on macOS.
- Record the build size.

## 4. Store assets

Icon (1024 source, nearest-upscaled from the real icon), screenshots from
`tools/capture.gd` nearest-upscaled to store sizes, first-line pitch,
description, feature graphic. Search the web for current store requirements.

## Report

Checklist with pass/fixed/waived per item, build path and size, tag, store
asset list, and what the user must do themselves (signing, store console).
