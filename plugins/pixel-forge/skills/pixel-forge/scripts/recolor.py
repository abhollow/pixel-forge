#!/usr/bin/env python3
"""Shift one hue range of a painting toward a target hue; leave every other
hue alone.

    python recolor.py raw_art/b2/meadow.png -o raw_art/clean/meadow_spring.png      # greens -> fresh green
    python recolor.py forest.png -o forest_warm.png --amount 0.4 --width 960
    python recolor.py jacket.png -o red.png --hue-range 45-72 --toward 0 --pull 1 --sat-gain 0
    python recolor.py --self-test

Why: recolouring an approved painting keeps its measured layout -- when
building, path and spawn positions were measured off a background,
regenerating it means re-measuring them all. The defaults turn yellow-greens
and olives into spring green and leave wood, roofs, paths, stone and water
put; the range and target are parameters, and the work is vectorised.

Recolour, don't tint: a tint multiplies everything; this moves only pixels
inside --hue-range (with soft --soft edges so there is no band), and only
ones that are saturated and bright enough to have a hue (--min-sat,
--min-val). Defaults: hues 38..150 pulled 65% toward 102,
saturation x1.7 capped at 0.78, value +10%.

Run before pixelize.py (palette lock comes after).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def rgb_to_hsv(x):
    """x float 0..1 (..., 3) -> h degrees, s, v."""
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn
    dd = np.where(d == 0, 1, d)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) * 60.0
    h = np.where(d == 0, 0.0, h)
    s = np.where(mx == 0, 0.0, d / np.where(mx == 0, 1, mx))
    return h, s, mx


def hsv_to_rgb(h, s, v):
    h = (h % 360.0) / 60.0
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1)


def recolor(rgb, lo=38.0, hi=150.0, toward=102.0, amount=1.0, pull=0.65, sat_gain=0.7,
            sat_max=0.78, val_gain=0.10, min_sat=0.10, min_val=0.08, soft_lo=12.0, soft_hi=20.0):
    """rgb uint8 (..., 3) -> uint8. Pixels outside the range are untouched bit-for-bit."""
    x = np.asarray(rgb).astype(np.float32) / 255.0
    h, s, v = rgb_to_hsv(x)
    if lo <= hi:
        inside = (h > lo) & (h < hi)
        dist_lo, dist_hi = h - lo, hi - h
    else:                                   # range wraps through 0 (reds)
        inside = (h > lo) | (h < hi)
        dist_lo, dist_hi = (h - lo) % 360, (hi - h) % 360
    sel = inside & (s > min_sat) & (v > min_val)
    w = np.clip(dist_lo / max(soft_lo, 1e-6), 0, 1) * np.clip(dist_hi / max(soft_hi, 1e-6), 0, 1) * amount
    dh = ((toward - h + 180.0) % 360.0) - 180.0          # shortest way round the wheel
    h2 = h + dh * pull * w
    s2 = np.minimum(sat_max, s * (1.0 + sat_gain * w)) if sat_gain else s
    v2 = np.minimum(1.0, v * (1.0 + val_gain * w))
    new = hsv_to_rgb(h2, s2, v2)
    out = np.where(sel[..., None], new, x)
    res = (out * 255.0).clip(0, 255)
    res = np.where(sel[..., None], res.round(), np.asarray(rgb).astype(np.float32))
    return res.astype(np.uint8)


def self_test():
    # olive goes greener and richer, timber brown untouched
    t = recolor(np.array([[[118, 118, 64], [107, 80, 59]]], np.uint8))[0]
    assert t[0][1] > t[0][0] + 10 and t[0][1] > 118, t[0]
    assert tuple(t[1]) == (107, 80, 59), t[1]
    # grey has no hue: untouched; a blue outside the range: untouched
    g = recolor(np.array([[[128, 128, 128], [40, 60, 200]]], np.uint8))[0]
    assert tuple(g[0]) == (128, 128, 128) and tuple(g[1]) == (40, 60, 200), g
    # wrap-around range: reds (340..20) toward orange 30
    r = recolor(np.array([[[200, 30, 40]]], np.uint8), lo=330, hi=25, toward=30, pull=1.0, sat_gain=0,
                soft_lo=1, soft_hi=1)[0][0]
    assert r[1] > 60, r
    # vectorised HSV round-trip is exact enough
    rng = np.random.default_rng(3)
    x = rng.random((50, 3)).astype(np.float32)
    back = hsv_to_rgb(*rgb_to_hsv(x))
    assert np.abs(back - x).max() < 1e-5
    print("recolor self-test OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?")
    ap.add_argument("-o", "--output")
    ap.add_argument("--hue-range", default="38-150", help="hues to move, degrees LO-HI (wraps: 330-25)")
    ap.add_argument("--toward", type=float, default=102.0, help="target hue in degrees (default 102, fresh green)")
    ap.add_argument("--amount", type=float, default=1.0, help="overall strength 0..1")
    ap.add_argument("--pull", type=float, default=0.65, help="fraction of the way to the target hue")
    ap.add_argument("--sat-gain", type=float, default=0.7, help="saturation x(1+gain) inside the range")
    ap.add_argument("--sat-max", type=float, default=0.78, help="cap on the boosted saturation")
    ap.add_argument("--val-gain", type=float, default=0.10, help="brightness x(1+gain) inside the range")
    ap.add_argument("--min-sat", type=float, default=0.10, help="greyer pixels have no hue to move")
    ap.add_argument("--min-val", type=float, default=0.08, help="darker pixels are left alone")
    ap.add_argument("--soft", default="12,20", help="degrees of soft edge at the LO,HI ends of the range")
    ap.add_argument("--width", type=int, default=0, help="downscale to this width first (faster)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if not a.input or not a.output:
        ap.error("give INPUT and -o OUTPUT (or --self-test)")
    lo, hi = (float(v) for v in a.hue_range.split("-"))
    sl, sh = (float(v) for v in a.soft.split(","))
    im = Image.open(a.input)
    alpha = im.getchannel("A") if im.mode in ("RGBA", "LA") else None
    rgb = im.convert("RGB")
    if a.width:
        size = (a.width, round(rgb.height * a.width / rgb.width))
        rgb = rgb.resize(size, Image.Resampling.BOX)
        alpha = alpha.resize(size, Image.Resampling.BOX) if alpha else None
    out = recolor(np.asarray(rgb), lo, hi, a.toward, a.amount, a.pull, a.sat_gain, a.sat_max,
                  a.val_gain, a.min_sat, a.min_val, sl, sh)
    img = Image.fromarray(out, "RGB")
    if alpha is not None:
        img.putalpha(alpha)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    img.save(a.output)
    moved = int((out != np.asarray(rgb)).any(-1).sum())
    print("%s -> %s  %d px recoloured (%.1f%%)" % (a.input, a.output, moved, 100.0 * moved / out[..., 0].size))


if __name__ == "__main__":
    main()
