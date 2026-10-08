#!/usr/bin/env python3
"""Remap pixels that land on RESERVED palette colours to something else.

    python remap_reserved.py art/sprites/title.png --reserved 2d0400,8c2519,ea6b5d --to 2d251d
    python remap_reserved.py art/sprites/*.png --palettes art/palettes.json --to nearest --palette art/palette_build.hex -O art/sprites
    python remap_reserved.py art/sprites/title.png --hue 340-16 --min-sat 0.35 --to 2d251d

Why: some colours MEAN something -- e.g. red belongs to the enemy alone and
blue to the player. A glow that blended with the magenta key goes pink, pink
snaps to the reserved red, and the title grows stray "enemy" pixels. After
palette
locking, any pixel sitting on a reserved colour is remapped: to one fixed
colour (the outline, usually), or to the nearest NON-reserved colour of a
palette.

Reserved colours come from --reserved (hex list), from the "reserved" list of
a palettes.json (see palette_build.py), or from a hue band (--hue LO-HI with
--min-sat) for art that was never palette-locked. Edits files in place unless
-o / -O is given. --x-range 0.0-0.5 limits it to part of the width (keep a
flame that is allowed to be red).
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402


def reserved_from_json(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    groups = data.get("groups", {})
    out = []
    for r in data.get("reserved", []):
        if r in groups:
            g = groups[r]
            if isinstance(g, dict) or isinstance(g, str):
                raise SystemExit("reserved group %r must be a hex list here" % r)
            out += list(g)
        else:
            out.append(r)
    return [fi.hex_to_rgb(c) for c in out]


def hue_sat(rgb):
    x = rgb.astype(np.float32) / 255.0
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    dd = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) * 60.0
    h = np.where(d == 0, 0, h)
    return h, s


def remap(arr, reserved=None, tol=0.0, to=None, palette=None, hue=None, min_sat=0.35, x_range=None):
    """Returns (new array, pixels changed)."""
    out = np.array(arr, np.uint8, copy=True)
    rgb = out[..., :3].astype(np.float32)
    hit = np.zeros(out.shape[:2], bool)
    if reserved:
        for c in reserved:
            hit |= np.sqrt(((rgb - np.array(c, np.float32)) ** 2).sum(-1)) <= tol
    if hue:
        lo, hi = hue
        h, s = hue_sat(out[..., :3])
        band = (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)
        hit |= band & (s > min_sat)
    hit &= out[..., 3] > 0
    if x_range:
        w = out.shape[1]
        cols = np.zeros(w, bool)
        cols[int(w * x_range[0]):int(np.ceil(w * x_range[1]))] = True
        hit &= cols[None, :]
    n = int(hit.sum())
    if not n:
        return out, 0
    if to == "nearest":
        pal = np.asarray(palette)
        if reserved:
            res = {tuple(c) for c in reserved}
            pal = np.array([c for c in pal if tuple(int(v) for v in c) not in res], np.uint8)
        if not len(pal):
            raise SystemExit("--to nearest: the palette has no non-reserved colours")
        out[hit, :3] = fi.quantize_to_palette(out[hit, :3], pal)
    else:
        out[hit, :3] = np.array(to, np.uint8)
    return out, n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="PNG(s) to fix")
    ap.add_argument("--reserved", help="comma list of reserved hex colours")
    ap.add_argument("--palettes", help="palettes.json whose 'reserved' list to use")
    ap.add_argument("--hue", help="also treat this hue band as reserved, degrees LO-HI (wraps: 340-16)")
    ap.add_argument("--min-sat", type=float, default=0.35, help="saturation floor for --hue (0..1)")
    ap.add_argument("--tol", type=float, default=0.0,
                    help="RGB distance that still counts as 'on' a reserved colour (0 = exact)")
    ap.add_argument("--to", required=True, help="replacement hex colour, or 'nearest' (needs --palette)")
    ap.add_argument("--palette", help="for --to nearest: the palette to pick from (reserved colours excluded)")
    ap.add_argument("--x-range", help="only this part of the width, as fractions LO-HI (e.g. 0-0.5)")
    ap.add_argument("-o", "--output", help="output file (single input)")
    ap.add_argument("-O", "--outdir", help="output directory (keeps names); default: edit in place")
    a = ap.parse_args()

    reserved = []
    if a.reserved:
        reserved += [fi.hex_to_rgb(c) for c in a.reserved.split(",") if c.strip()]
    if a.palettes:
        reserved += reserved_from_json(a.palettes)
    hue = None
    if a.hue:
        lo, hi = a.hue.split("-")
        hue = (float(lo), float(hi))
    if not reserved and not hue:
        ap.error("nothing reserved: give --reserved, --palettes or --hue")
    if a.to == "nearest":
        if not a.palette:
            ap.error("--to nearest needs --palette")
        to, pal = "nearest", fi.load_palette(a.palette)
    else:
        to, pal = fi.hex_to_rgb(a.to), None
    xr = tuple(float(v) for v in a.x_range.split("-")) if a.x_range else None
    if a.output and len(a.inputs) > 1:
        ap.error("-o takes one input; use -O DIR")
    total = 0
    for path in a.inputs:
        arr = np.array(Image.open(path).convert("RGBA"))
        out, n = remap(arr, reserved, a.tol, to, pal, hue, a.min_sat, xr)
        dest = a.output or (os.path.join(a.outdir, os.path.basename(path)) if a.outdir else path)
        if n or dest != path:
            fi.save_rgba(out, dest)
        total += n
        print("%s: %d reserved px remapped%s" % (path, n, "" if dest == path else " -> " + dest))
    print("total %d px" % total)


if __name__ == "__main__":
    main()
