#!/usr/bin/env python3
"""Remove the key colour's cast (magenta or green) from a subject.

    python despill.py cut/home_00.png -o clean/home_00.png          # sprite with alpha
    python despill.py raw_art/b7/sheet.png -o clean/sheet.png --key auto
    python despill.py --self-test

Why: image models generating on flat #FF00FF tint the subject's shadows and
edges purple: a brown-grey wall comes back as a purple-grey like 403040, and
a palette then snaps those purples to heather. Classic despill: where both red
and blue exceed green, pull them back toward green by the excess (green key:
pull green down to the larger of red and blue).

Where it applies -- the order matters:
  * an image WITH alpha (already keyed): only inside the kept alpha.
  * an opaque sheet: everywhere EXCEPT what a cutter will key -- key-coloured
    regions connected to the border (the background and its drop shadows)
    and enclosed pockets of pure key -- so the cutter still finds them.
The best order is "key from the raw sheet, then despill inside the kept mask"
(slice_sheet.py --despill does exactly that). Despilling a raw sheet first
turns magenta DROP SHADOWS grey; they then count as sprite, bridge the gaps,
and neighbours merge (worst on a tightly packed kit of buildings).

Never despill a subject that genuinely contains the key hue (a pink flower
on magenta -- generate it on green instead). --edge N limits the pass to N px
inside the silhouette, where most spill sits.
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


def despill_array(arr, key="auto", strength=1.0, edge=0):
    """RGBA uint8 in, RGBA uint8 out. Returns (array, key used, pixels changed)."""
    arr = np.asarray(arr, np.uint8)
    if arr.shape[2] == 3:
        arr = np.dstack([arr, np.full(arr.shape[:2], 255, np.uint8)])
    if fi.has_alpha(arr):
        where = arr[..., 3] > 0
        if key == "auto":
            # judge the key from what the cast leans toward inside the sprite
            px = arr[where][:, :3].astype(np.float32)
            mag = np.clip(np.minimum(px[:, 0], px[:, 2]) - px[:, 1], 0, None).mean() if len(px) else 0
            grn = np.clip(px[:, 1] - np.maximum(px[:, 0], px[:, 2]), 0, None).mean() if len(px) else 0
            key = "green" if grn > mag else "magenta"
    else:
        if key == "auto":
            key = fi.detect_key(arr)
        if key not in ("magenta", "green"):
            return arr.copy(), key, 0
        # leave alone exactly what a cutter will key: key-coloured regions
        # connected to the border (background AND its drop shadows) and
        # enclosed pockets of pure key; clean everything that will be kept
        bg, _ = fi.background_mask(arr, key)
        where = ~bg
    if key not in ("magenta", "green"):
        return arr.copy(), key, 0
    if edge > 0:
        where = fi.edge_band(where, edge)
    rgb = fi.despill(arr, key, strength, where)
    out = arr.copy()
    new = np.round(rgb).astype(np.uint8)
    changed = int((np.abs(new.astype(int) - arr[..., :3].astype(int)).sum(axis=2) > 0).sum())
    out[..., :3] = new
    return out, key, changed


def self_test():
    # a purple shadow goes neutral, brown stays brown,
    # the pure key stays magenta (opaque sheet mode).
    t, key, _ = despill_array(np.array([[[64, 48, 64], [120, 80, 50], [255, 0, 255]]], np.uint8), "magenta")
    t = t[0]
    assert abs(int(t[0][0]) - int(t[0][2])) < 2 and t[0][0] <= 50, t[0]
    assert tuple(t[1][:3]) == (120, 80, 50), t[1]
    assert tuple(t[2][:3]) == (255, 0, 255), t[2]
    # green key: a green-tinted edge on a pink subject loses the green; pink stays; key stays
    g, key, _ = despill_array(np.array([[[150, 170, 140], [240, 120, 170], [0, 255, 0]]], np.uint8), "green")
    g = g[0]
    assert g[0][1] <= 150 and tuple(g[1][:3]) == (240, 120, 170) and tuple(g[2][:3]) == (0, 255, 0), g
    # alpha mode: only inside the kept alpha
    a = np.array([[[90, 40, 90, 255], [90, 40, 90, 0]]], np.uint8)
    o, key, n = despill_array(a, "auto")
    assert key == "magenta" and n == 1 and o[0][0][0] == 40 and tuple(o[0][1]) == (90, 40, 90, 0), o
    print("despill self-test OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="PNG(s) to despill")
    ap.add_argument("-o", "--output", help="output file (single input)")
    ap.add_argument("-O", "--outdir", help="output directory (several inputs; keeps names)")
    ap.add_argument("--key", choices=["auto", "magenta", "green"], default="auto",
                    help="which cast to remove (default auto: from the border, or the cast inside the alpha)")
    ap.add_argument("--strength", type=float, default=1.0, help="0..1, how much of the excess to remove")
    ap.add_argument("--edge", type=int, default=0,
                    help="only within N px of the silhouette edge (0 = everywhere inside)")
    ap.add_argument("--self-test", action="store_true", help="run the built-in checks and exit")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if not a.inputs:
        ap.error("give input PNG(s), or --self-test")
    if a.output and len(a.inputs) > 1:
        ap.error("-o takes one input; use -O DIR for several")
    if not a.output and not a.outdir:
        ap.error("give -o FILE or -O DIR (despill never overwrites its input silently)")
    for path in a.inputs:
        arr = np.array(Image.open(path).convert("RGBA"))
        out, key, n = despill_array(arr, a.key, a.strength, a.edge)
        dest = a.output or os.path.join(a.outdir, os.path.basename(path))
        fi.save_rgba(out, dest)
        print("%s -> %s  key %s, %d px changed" % (path, dest, key, n))


if __name__ == "__main__":
    main()
