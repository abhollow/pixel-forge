#!/usr/bin/env python3
"""The project's settings, in one place: forge.json at the game's root.

    python forge_config.py init --width 480 --height 854 --scale 2 --aspect keep
    python forge_config.py init --tracker-id my-game --tracker-icon star   (updates one field)
    python forge_config.py show

Every tool reads its defaults from here instead of hard-coding a resolution, so
a 360x640 phone game and a 960x540 landscape game use the same scripts.

    view_w, view_h   the game's viewport in screen pixels (project.godot size)
    pixel_scale      screen pixels per ART pixel. 2 means art is drawn at half
                     the viewport's resolution and doubled -- chunky. 1 means
                     native, detailed pixel art. The ART CANVAS is view / scale.
    aspect           "keep" (letterbox; right for painted, fixed-layout scenes)
                     or "expand" (show more world on odd screens; right for tile
                     maps and scrolling worlds). See godot4-pixel-setup.md.
    orientation      "portrait" or "landscape"
    perspective      "side", "top-down" or "three-quarter" ("" until the bible
                     picks one)
    cell             the sprite/tile unit, in art pixels.
    godot_version    the ONE Godot version this game is built and tested with
                     ("4.7.2"). project.godot, CI and the README all follow it.
    forge_version    the Pixel Forge version vendored into tools/forge/.
    palette          the master palette file, relative to the game root.
    tracker          {"id": ..., "icon": ...} for the Idea-to-Launch tracker.

Older or minimal forge.json files (just the five size keys) load unchanged:
every missing key takes its default. Keys this file does not know are kept when it rewrites.

Other scripts import load() -- it searches upward from the current directory
for forge.json, so they work from anywhere inside the project. Run with
python, or `py -3` / python3 where `python` is the Microsoft Store stub.
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_FORGE_VERSION = "1.0.0"

DEFAULTS = {
    "view_w": 360,
    "view_h": 640,
    "pixel_scale": 2,
    "aspect": "keep",
    "orientation": "portrait",
    "perspective": "",
    "cell": 32,
    "godot_version": "4.3",
    "forge_version": FALLBACK_FORGE_VERSION,
    "palette": "art/palette.hex",
    "tracker": {"id": "", "icon": ""},
}

ASPECTS = ("keep", "expand")
ORIENTATIONS = ("portrait", "landscape")
PERSPECTIVES = ("side", "top-down", "three-quarter")


def forge_version():
    """The running Pixel Forge version.

    A vendored copy (tools/forge/) carries a VERSION file next to its scripts;
    inside the plugin the version is in .claude-plugin/plugin.json, two levels
    above the skill directory."""
    vf = os.path.join(HERE, "VERSION")
    if os.path.isfile(vf):
        with open(vf, encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    pj = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".claude-plugin", "plugin.json"))
    if os.path.isfile(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                v = str(json.load(f).get("version", "")).strip()
                if v:
                    return v
        except (OSError, ValueError):
            pass
    return FALLBACK_FORGE_VERSION


def find(start="."):
    d = os.path.abspath(start)
    while True:
        p = os.path.join(d, "forge.json")
        if os.path.exists(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _merge(cfg, data):
    for k, v in data.items():
        if k == "tracker" and isinstance(v, dict):
            cfg["tracker"].update(v)
        else:
            cfg[k] = v
    return cfg


def load(start="."):
    """Settings in effect at `start`: defaults, overlaid by the nearest forge.json.

    Adds derived keys art_w, art_h (the art canvas) and _path (None when no
    forge.json was found)."""
    cfg = copy.deepcopy(DEFAULTS)
    p = find(start)
    if p:
        with open(p, encoding="utf-8") as f:
            _merge(cfg, json.load(f))
    scale = max(1, int(cfg["pixel_scale"]))
    cfg["art_w"] = int(cfg["view_w"]) // scale
    cfg["art_h"] = int(cfg["view_h"]) // scale
    cfg["_path"] = p
    return cfg


def write(path, cfg):
    """Write forge.json: every known key (defaults filled in), plus any unknown
    keys already in cfg. Derived keys (art_w, art_h, _*) are dropped."""
    out = copy.deepcopy(DEFAULTS)
    _merge(out, {k: v for k, v in cfg.items()
                 if not k.startswith("_") and k not in ("art_w", "art_h")})
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    return out


def _major_minor_patch(v):
    parts = str(v).strip().split(".")
    if len(parts) < 2 or not all(p.isdigit() for p in parts[:3]):
        raise argparse.ArgumentTypeError(f"not a Godot version: {v!r} (want e.g. 4.3 or 4.7.2)")
    return ".".join(parts[:3])


def _self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        # a minimal file: five keys only
        with open(os.path.join(d, "forge.json"), "w") as f:
            json.dump({"view_w": 960, "view_h": 540, "pixel_scale": 1, "aspect": "expand", "cell": 16}, f)
        sub = os.path.join(d, "art", "sprites")
        os.makedirs(sub)
        c = load(sub)
        assert c["_path"] and c["view_w"] == 960 and c["art_w"] == 960, c
        assert c["godot_version"] == DEFAULTS["godot_version"] and c["tracker"] == {"id": "", "icon": ""}, c
        # rewrite keeps unknown keys, fills new ones, merges tracker
        c["custom"] = 7
        c["tracker"]["id"] = "x"
        write(c["_path"], c)
        with open(c["_path"]) as f:
            raw = json.load(f)
        assert raw["custom"] == 7 and raw["tracker"] == {"id": "x", "icon": ""} and "art_w" not in raw, raw
        assert set(DEFAULTS) <= set(raw), raw
        # defaults are not shared between loads
        a = load(d)
        a["tracker"]["icon"] = "changed"
        assert DEFAULTS["tracker"]["icon"] == "", DEFAULTS
    assert _major_minor_patch("4.7.2.stable") == "4.7.2"
    print("forge_config self-test: ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="run the built-in checks and exit")
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("init", help="write forge.json in the current directory (updates only the flags given if it exists)")
    i.add_argument("--width", type=int)
    i.add_argument("--height", type=int)
    i.add_argument("--scale", type=int, help="screen pixels per art pixel")
    i.add_argument("--aspect", choices=ASPECTS)
    i.add_argument("--orientation", choices=ORIENTATIONS)
    i.add_argument("--perspective", choices=PERSPECTIVES)
    i.add_argument("--cell", type=int)
    i.add_argument("--godot-version", type=_major_minor_patch, help="e.g. 4.7.2")
    i.add_argument("--forge-version", help="default: this forge's version")
    i.add_argument("--palette", help="master palette path, relative to the game root")
    i.add_argument("--tracker-id")
    i.add_argument("--tracker-icon")
    sub.add_parser("show", help="print the settings in effect here")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if a.cmd is None:
        ap.print_help()
        return 2
    if a.cmd == "init":
        path = os.path.abspath("forge.json")
        cfg = copy.deepcopy(DEFAULTS)
        cfg["forge_version"] = forge_version()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _merge(cfg, json.load(f))
        given = {"view_w": a.width, "view_h": a.height, "pixel_scale": a.scale, "aspect": a.aspect,
                 "orientation": a.orientation, "perspective": a.perspective, "cell": a.cell,
                 "godot_version": a.godot_version, "forge_version": a.forge_version, "palette": a.palette}
        cfg.update({k: v for k, v in given.items() if v is not None})
        if a.orientation is None and (a.width is not None or a.height is not None):
            cfg["orientation"] = "landscape" if int(cfg["view_w"]) > int(cfg["view_h"]) else "portrait"
        if a.tracker_id is not None:
            cfg["tracker"]["id"] = a.tracker_id
        if a.tracker_icon is not None:
            cfg["tracker"]["icon"] = a.tracker_icon
        write(path, cfg)
        c = load()
        print(f"forge.json: {c['view_w']}x{c['view_h']} viewport, art canvas {c['art_w']}x{c['art_h']} "
              f"at {c['pixel_scale']}x, aspect {c['aspect']}, {c['orientation']}, Godot {c['godot_version']}")
    else:
        c = load()
        print(json.dumps({k: v for k, v in c.items() if not k.startswith("_")}, indent=2))
        print("from:", c["_path"] or "(defaults -- no forge.json found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
