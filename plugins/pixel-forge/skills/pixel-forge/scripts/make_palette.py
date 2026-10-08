#!/usr/bin/env python3
"""
make_palette.py - build the locked project palette.

A shared palette is one way to make independently generated assets read
as one game. It is a tool, not a rule: a game can ship hundreds of sprites
with no palette at all (hard alpha, integer scale and one-sheet generation
carry the look), or lock every sprite to a palette extracted from its chosen
mood frame. Lock when sheets drift apart in colour.

Two modes:

  extract  pull the N dominant colours out of reference art you like
           (e.g. the chosen mood frame -> 44 colours)
             python make_palette.py extract raw_art/mood/mood_c.png -n 44 -o art/extracted

  ramp     build one procedurally from base hues, each with a shading ramp
             python make_palette.py ramp --hues 200,35,140,15 --steps 4 -o art/palette

Both write <o>.hex (for pixelize.py --palette), <o>.png (1 px per colour) and
<o>_preview.png (big swatches, to look at). For named groups, reserved
colours and per-asset sub-palettes, feed the .hex into palette_build.py.
"""

import argparse
import colorsys
import os

import numpy as np
from PIL import Image


def extract(paths, n):
    pixels = []
    for p in paths:
        img = Image.open(p).convert("RGBA")
        a = np.array(img).reshape(-1, 4)
        pixels.append(a[a[:, 3] > 16][:, :3])
    allpx = np.concatenate(pixels, axis=0)
    if not len(allpx):
        raise SystemExit("no opaque pixels in the input image(s)")
    strip = Image.fromarray(allpx.reshape(-1, 1, 3).astype("uint8"), "RGB")
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[: n * 3], dtype=np.uint8).reshape(-1, 3)
    return sort_palette(pal)


def ramp(hues, steps, sat=0.62, lo=0.18, hi=0.92):
    cols = []
    for hue in hues:
        for i in range(steps):
            t = i / max(1, steps - 1)
            v = lo + (hi - lo) * t
            # desaturate the highlights, deepen the shadows - reads as light
            s = sat * (1.0 - 0.45 * t) + 0.08
            r, g, b = colorsys.hsv_to_rgb((hue % 360) / 360.0, min(s, 1.0), v)
            cols.append((int(r * 255), int(g * 255), int(b * 255)))
    # every palette needs true anchors at both ends
    cols = [(14, 16, 26)] + cols + [(244, 246, 240)]
    return np.array(cols, dtype=np.uint8)


def sort_palette(pal):
    """Order by hue then luma, so the palette file is readable by a human."""
    def key(c):
        r, g, b = [v / 255 for v in c]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return (round(h * 12), v) if s > 0.12 else (-1, v)
    return np.array(sorted([tuple(int(x) for x in c) for c in pal], key=key),
                    dtype=np.uint8)


def write(pal, out):
    base = os.path.splitext(out)[0]
    d = os.path.dirname(os.path.abspath(base))
    os.makedirs(d, exist_ok=True)
    with open(base + ".hex", "w", newline="\n", encoding="utf-8") as fh:
        for c in pal:
            fh.write("%02x%02x%02x\n" % tuple(int(x) for x in c))
    Image.fromarray(pal.reshape(1, -1, 3), "RGB").save(base + ".png")

    sw, cols = 48, min(8, len(pal))
    rows = (len(pal) + cols - 1) // cols
    prev = Image.new("RGB", (cols * sw, rows * sw), (20, 20, 20))
    for i, c in enumerate(pal):
        block = Image.new("RGB", (sw - 2, sw - 2), tuple(int(x) for x in c))
        prev.paste(block, ((i % cols) * sw + 1, (i // cols) * sw + 1))
    prev.save(base + "_preview.png")

    print(f"{len(pal)} colors")
    print(f"  {base}.hex          -> pass to pixelize.py --palette")
    print(f"  {base}.png          -> 1px-per-color strip")
    print(f"  {base}_preview.png  -> look at this one")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    e = sub.add_parser("extract", help="derive a palette from reference images")
    e.add_argument("images", nargs="+")
    e.add_argument("-n", type=int, default=24, help="number of colors")
    e.add_argument("-o", "--output", default="palette")

    r = sub.add_parser("ramp", help="generate a palette from base hues")
    r.add_argument("--hues", default="205,40,150,10",
                   help="comma-separated hue degrees, 0-360")
    r.add_argument("--steps", type=int, default=4, help="shades per hue")
    r.add_argument("--sat", type=float, default=0.62)
    r.add_argument("-o", "--output", default="palette")

    a = p.parse_args()
    if a.mode == "extract":
        pal = extract(a.images, a.n)
    else:
        hues = [float(h) for h in a.hues.split(",") if h.strip()]
        pal = sort_palette(ramp(hues, a.steps, a.sat))
    write(pal, a.output)


if __name__ == "__main__":
    main()
