#!/usr/bin/env python3
"""Soften a sprite's outer rim so it sits INTO the ground instead of standing
out on it.

    python soften_edges.py art/sprites/tree_*.png --ground 5f7a4c
    python soften_edges.py art/sprites_hd/tree_*.png --ground 5f7a4c --alpha 150 --toward 0.35 -O out/

Every opaque pixel that touches transparency (the silhouette's rim) is made
half-transparent (--alpha) and pushed part of the way (--toward) toward the
ground colour, so the hard dark outline melts into whatever is behind it --
like painted buildings on trodden earth. A good start for trees on grass:
rim alpha 150, 35% toward the ground green, with code-drawn foot shadows
underneath.

Feather INWARD only: the pass never adds pixels outside the silhouette (a
grown, coloured halo looks worse than a hard edge). Pixels already
semi-transparent are left alone, so running it twice changes nothing.
Run it on final, palette-locked sprites -- the softened rim is deliberately
off-palette and semi-transparent. --width 2 softens two rings (the inner one
half as much).
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


def rim(opaque):
    pad = np.pad(opaque, 1)
    inside = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return opaque & ~inside


def soften(arr, ground, alpha=150, toward=0.35, width=1):
    """Returns (new RGBA array, rim pixels changed)."""
    im = np.asarray(arr).astype(np.float32).copy()
    full = im[..., 3] >= 255          # only fully opaque pixels change: idempotent
    g = np.array(ground, np.float32)
    total = 0
    core = im[..., 3] > 0
    for ring in range(width):
        r = rim(core) & full
        k = 1.0 / (ring + 1)
        a_target = 255 - (255 - alpha) * k
        im[r, :3] = im[r, :3] * (1 - toward * k) + g * toward * k
        im[r, 3] = a_target
        total += int(r.sum())
        core = core & ~rim(core)
    return im.clip(0, 255).astype(np.uint8), total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="sprite PNG(s)")
    ap.add_argument("--ground", required=True, help="ground colour the rim leans toward, hex (e.g. 5f7a4c)")
    ap.add_argument("--alpha", type=int, default=150, help="rim alpha 0-255 (default 150)")
    ap.add_argument("--toward", type=float, default=0.35, help="0..1 push toward the ground colour (default 0.35)")
    ap.add_argument("--width", type=int, default=1, help="rings to soften (default 1)")
    ap.add_argument("-o", "--output", help="output file (single input)")
    ap.add_argument("-O", "--outdir", help="output directory (keeps names); default: in place")
    a = ap.parse_args()
    if a.output and len(a.inputs) > 1:
        ap.error("-o takes one input; use -O DIR")
    ground = fi.hex_to_rgb(a.ground)
    for path in a.inputs:
        arr = np.array(Image.open(path).convert("RGBA"))
        out, n = soften(arr, ground, a.alpha, a.toward, a.width)
        dest = a.output or (os.path.join(a.outdir, os.path.basename(path)) if a.outdir else path)
        fi.save_rgba(out, dest)
        print("softened %s: %d rim px%s" % (path, n, "" if dest == path else " -> " + dest))


if __name__ == "__main__":
    main()
