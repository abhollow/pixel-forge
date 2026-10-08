#!/usr/bin/env python3
"""Stitch a large background from screen-sized painted sections, blending each
overlap through a DITHERED mask.

    python stitch_map.py --sections 0:raw_art/map/r0.png 405:raw_art/map/r405.png \\
        810:raw_art/map/r810.png 1215:raw_art/map/r1215.png 1620:raw_art/map/r1620.png \\
        --width 960 --section-size 540 -o art/map.png
    python stitch_map.py --axis x --sections 0:a.png 1700:b.png --height 1080 --section-size 1920 -o wide.png

Why: asked to paint a whole 960x2160 map as ONE image, the model paints a
distant vista -- every flower and tuft comes out a 1-2 px smear at game size.
Painted a screen (960x540) at a time it draws them at game scale. Sections
overlap (e.g. 135 px, sections at y = 0, 405, 810, 1215, 1620); in each
overlap every pixel comes from the upper or the lower section,
picked at random with a probability that ramps across the overlap. Dithered,
not cross-faded: no seam, and no soft double-exposed band.

Each section is resized to --width x --section-size first (--resample).
Don't palette-lock painterly ground afterwards: a strict palette flattens a
meadow to one green and drops the flowers.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402


def stitch(sections, across, section_size, total=None, seed=7, resample="lanczos"):
    """sections: [(offset, image path)] along y. Returns uint8 RGB (H, W, 3)."""
    sections = sorted(sections, key=lambda s: s[0])
    total = total or (sections[-1][0] + section_size)
    out = np.zeros((total, across, 3), np.float32)
    rng = np.random.default_rng(seed)
    filled = 0
    for off, path in sections:
        img = Image.open(path).convert("RGB").resize((across, section_size), fi.RESAMPLE[resample])
        sec = np.asarray(img, np.float32)
        if off > filled:
            raise SystemExit("gap: section at %d starts after the previous one ends (%d)" % (off, filled))
        ov = min(filled - off, section_size)
        if ov > 0:
            ramp = np.linspace(0, 1, ov + 2)[1:-1][:, None]   # never all-old or all-new at the ends
            take = rng.random((ov, across)) < ramp
            region = out[off:off + ov]
            region[take] = sec[:ov][take]
        end = min(total, off + section_size)
        out[off + ov:end] = sec[ov:end - off]
        filled = max(filled, end)
    if filled < total:
        print("WARNING: rows %d..%d are empty" % (filled, total))
    return out.clip(0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sections", nargs="+", required=True, help="OFFSET:FILE pairs (offset in output px)")
    ap.add_argument("--axis", choices=["y", "x"], default="y", help="stack down (y, default) or across (x)")
    ap.add_argument("--width", type=int, help="output width (axis y): every section is resized to it")
    ap.add_argument("--height", type=int, help="output height (axis x)")
    ap.add_argument("--section-size", type=int, required=True,
                    help="each section's length along the axis after resizing (e.g. 540)")
    ap.add_argument("--total", type=int, default=None, help="output length along the axis (default: last offset + section)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--resample", choices=sorted(fi.RESAMPLE), default="lanczos",
                    help="section resize filter (default lanczos: painterly ground, not sprites)")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    secs = []
    for s in a.sections:
        off, _, path = s.partition(":")
        if not path or not off.strip().isdigit():
            ap.error("sections look like 405:raw_art/map/r405.png, got %r" % s)
        secs.append((int(off), path))
    if a.axis == "y":
        if not a.width:
            ap.error("--axis y needs --width")
        out = stitch(secs, a.width, a.section_size, a.total, a.seed, a.resample)
    else:
        if not a.height:
            ap.error("--axis x needs --height")
        # stitch rotated sections, rotate back
        tmp = []
        tdir = os.path.dirname(os.path.abspath(a.output))
        os.makedirs(tdir, exist_ok=True)
        for i, (off, path) in enumerate(secs):
            p = os.path.join(tdir, "_stitch_tmp_%d.png" % i)
            Image.open(path).convert("RGB").transpose(Image.Transpose.TRANSPOSE).save(p)
            tmp.append((off, p))
        try:
            out = stitch(tmp, a.height, a.section_size, a.total, a.seed, a.resample).transpose(1, 0, 2)
        finally:
            for _, p in tmp:
                os.remove(p)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    Image.fromarray(out).save(a.output)
    print("wrote %s  %dx%d from %d sections" % (a.output, out.shape[1], out.shape[0], len(secs)))


if __name__ == "__main__":
    main()
