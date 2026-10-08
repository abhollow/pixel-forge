#!/usr/bin/env python3
"""Mask of the parts of a background that should move in the wind.

    python make_sway_mask.py --src art/sprites/background_level2.png \\
        --out art/sprites/sway_level2.png --below 96 --sky 56

Trees painted into a background cannot be animated as sprites. Instead a
shader (assets/shaders/sway.gdshader) shifts the pixels this mask marks
sideways over time. White = sways fully, black = never moves; the soft edge
between them is what stops the displacement leaving a visible seam.

Two kinds of pixel qualify:
  * foliage GREEN anywhere above --below (e.g. above a strip of buildings),
    defined as darker than the sky AND leaning green-over-blue. Not by
    saturation: foliage under an overcast sky has almost none, and a
    saturation rule misses nearly all of it while grey sky sits right beside
    it.
  * any strongly coloured pixel above --sky -- kites and flag cloth, up where
    nothing else is saturated. Coloured roofs sit lower and are excluded,
    which is why the colour rule is limited to the sky.

For sprites drawn one by one, a per-sprite vertex shear
(assets/shaders/sway_sprite.gdshader) needs no mask at all.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_ndimage as ndi  # noqa: E402


def sway_mask(im, below, sky, grow=2, soft=1.2):
    im = np.asarray(im).astype(np.float32)
    h, w, _ = im.shape
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    sat = im.max(axis=2) - im.min(axis=2)
    rows = np.arange(h)[:, None].repeat(w, axis=1)
    lum = im.mean(axis=2)
    sky_lum = float(np.median(lum[: max(4, h // 30)]))      # the top rows are sky
    frond = (g > r + 5) & (g > b + 4) & (lum < sky_lum - 25) & (rows < below)
    flag = (sat > 70) & (rows < sky)
    mask = frond | flag
    # room to swing into, then a soft falloff so there is no seam at the edge
    mask = ndi.binary_dilation(mask, grow)
    out = ndi.gaussian_filter(mask.astype(np.float32), soft)
    out = np.clip(out * 1.4, 0, 1)
    out[rows >= below] = 0.0
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--below", type=int, required=True, help="mask nothing below this row")
    ap.add_argument("--sky", type=int, required=True, help="saturated colours count above this row")
    ap.add_argument("--grow", type=int, default=2, help="pixels of room to swing into")
    ap.add_argument("--soft", type=float, default=1.2, help="edge blur")
    a = ap.parse_args()
    soft = sway_mask(Image.open(a.src).convert("RGB"), a.below, a.sky, a.grow, a.soft)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    Image.fromarray((soft * 255).astype(np.uint8), "L").save(a.out)
    h, w = soft.shape
    print(f"{a.out}: {w}x{h}, {(soft > 0.05).mean() * 100:.1f}% of the image sways")


if __name__ == "__main__":
    main()
