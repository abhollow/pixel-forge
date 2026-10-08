#!/usr/bin/env python3
"""Hue histogram of a sprite set -- measure the window before writing a
recolour shader.

    python measure_hues.py art/sprites/npc_*.png
    python measure_hues.py art/sprites/npc_*.png --region 4,8,20,18 --plot docs/screens/hues.png
    python measure_hues.py art/sprites/player_*.png --json

Why: a hue-swap shader recolours everything inside its window. Say a vest
sits at 50-58 degrees and a bag right beside it at 60-73: a guessed 45-72
window turns the bag too, while the measured histogram shows the valley
between them and a tight window fixes it. Guessing a window is how a
recolour leaks into the wrong part.

Counts opaque pixels with saturation >= --min-sat and value >= --min-val
(greys and near-black have no meaningful hue), in --bin-degree bins, over
all files (or one --region x0,y0,x1,y1 of each). Prints a text histogram
and the clusters: runs of bins separated by a valley, each with its hue
range, share of pixels and a sample colour -- the windows to put in the
shader (leave a degree or two of margin from the neighbouring cluster).
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from recolor import rgb_to_hsv  # noqa: E402


def gather(paths, region=None, min_sat=0.2, min_val=0.15):
    hs, cols = [], []
    for p in paths:
        a = np.array(Image.open(p).convert("RGBA"))
        if region:
            x0, y0, x1, y1 = region
            a = a[y0:y1, x0:x1]
        px = a[a[..., 3] > 0][:, :3]
        if not len(px):
            continue
        h, s, v = rgb_to_hsv(px.astype(np.float32) / 255.0)
        keep = (s >= min_sat) & (v >= min_val)
        hs.append(h[keep])
        cols.append(px[keep])
    if not hs:
        return np.zeros(0), np.zeros((0, 3), np.uint8)
    return np.concatenate(hs), np.concatenate(cols)


def clusters(hist, floor):
    """Runs of bins above `floor` (wrapping round 360), split at valleys
    deeper than half the smaller neighbouring peak. Returns (first, last) bins."""
    n = len(hist)
    on = hist > floor
    if not on.any():
        return []
    if on.all():
        runs = [list(range(n))]
    else:
        start = int(np.argmin(on))        # an empty bin, so a run across 0 deg stays whole
        runs, cur = [], []
        for k in range(1, n + 1):
            i = (start + k) % n
            if on[i]:
                cur.append(i)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
    out = []
    for run in runs:
        vals = hist[run]
        cuts = [k for k in range(1, len(run) - 1)
                if vals[k] <= vals[k - 1] and vals[k] <= vals[k + 1]
                and vals[k] < 0.5 * min(vals[:k].max(), vals[k + 1:].max())]
        bounds = [0] + cuts + [len(run)]
        for c0, c1 in zip(bounds[:-1], bounds[1:]):
            out.append((run[c0], run[c1 - 1]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+", help="sprite PNGs (globs ok)")
    ap.add_argument("--region", help="x0,y0,x1,y1 to measure inside each sprite (e.g. the torso)")
    ap.add_argument("--bin-degree", type=float, default=2.0, help="histogram bin width in degrees (default 2)")
    ap.add_argument("--min-sat", type=float, default=0.2)
    ap.add_argument("--min-val", type=float, default=0.15)
    ap.add_argument("--floor", type=float, default=0.5, help="bins under this %% of pixels count as empty")
    ap.add_argument("--plot", help="write a histogram image here (bars in their own hue)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    paths = []
    for f in a.images:
        paths += sorted(glob.glob(f)) if any(c in f for c in "*?[") else [f]
    region = tuple(int(v) for v in a.region.split(",")) if a.region else None
    h, cols = gather(paths, region, a.min_sat, a.min_val)
    if not len(h):
        raise SystemExit("no saturated opaque pixels found (lower --min-sat?)")
    nb = int(round(360 / a.bin_degree))
    hist, edges = np.histogram(h, bins=nb, range=(0, 360))
    pct = 100.0 * hist / hist.sum()
    found = []
    for b0, b1 in clusters(pct, a.floor):
        lo, hi = edges[b0], edges[b1 + 1]
        sel = ((h >= lo) & (h < hi)) if lo < hi else ((h >= lo) | (h < hi))
        share = 100.0 * sel.sum() / len(h)
        sample = np.median(cols[sel], axis=0).astype(int) if sel.any() else [0, 0, 0]
        found.append({"from_deg": round(float(lo), 1), "to_deg": round(float(hi), 1),
                      "percent": round(float(share), 1), "sample": "%02x%02x%02x" % tuple(sample)})
    found.sort(key=lambda c: -c["percent"])
    result = {"files": len(paths), "pixels": int(len(h)), "bin_degree": a.bin_degree, "clusters": found}
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print("%d file(s), %d saturated pixels" % (len(paths), len(h)))
        peak = pct.max()
        for i in range(nb):
            if pct[i] >= a.floor:
                print("  %5.1f-%5.1f %5.1f%% %s" % (edges[i], edges[i + 1], pct[i], "#" * int(round(40 * pct[i] / peak))))
        print("clusters (biggest first) -- shader windows:")
        for c in found:
            print("  %5.1f .. %5.1f deg  %5.1f%%  e.g. #%s" % (c["from_deg"], c["to_deg"], c["percent"], c["sample"]))
    if a.plot:
        from recolor import hsv_to_rgb
        W, H = nb * 4, 160
        img = np.full((H + 12, W, 3), 24, np.uint8)
        for i in range(nb):
            bh = int(round(H * pct[i] / pct.max()))
            c = (hsv_to_rgb(np.array([edges[i] + a.bin_degree / 2]), np.array([0.8]), np.array([0.95]))[0] * 255)
            img[H - bh:H, i * 4:i * 4 + 3] = c.astype(np.uint8)
            img[H + 4:H + 12, i * 4:i * 4 + 4] = c.astype(np.uint8)
        os.makedirs(os.path.dirname(os.path.abspath(a.plot)), exist_ok=True)
        Image.fromarray(img).resize((W * 2, (H + 12) * 2), Image.Resampling.NEAREST).save(a.plot)
        print("plot:", a.plot, file=sys.stderr if a.json else sys.stdout)


if __name__ == "__main__":
    main()
