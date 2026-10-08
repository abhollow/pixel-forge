#!/usr/bin/env python3
"""
Builds a gentle sway cycle out of a single static sprite.

The horizontal cousin of make_water_frames.py: rows are displaced sideways by
a sine whose amplitude grows toward the TOP of the sprite, so the base stays
planted and only the tips move. A uniform shift would just look like the
whole clump sliding. Offsets are whole pixels, so the art never blurs.

Frames are derived from the one approved sprite rather than generated
separately -- separate generations are not frame-coherent and flicker. For a
sprite drawn in-engine, the per-sprite shader (assets/shaders/sway_sprite.
gdshader) does the same thing with no extra textures; use frames when the
target has no shader budget or the motion should be hand-picked.

    python make_sway_frames.py --src art/sprites/grass_00.png --prefix grass_sway --amp 2
    python make_sway_frames.py --src tree.png --prefix tree --frames 6 --anchor 0.5 --out-dir art/anim
"""

import argparse
import math
import os

import numpy as np
from PIL import Image


def sway(arr, phase, amp, anchor):
    h, w = arr.shape[:2]
    out = np.zeros_like(arr)
    for y in range(h):
        # 1 at the top, 0 at the base; `anchor` = share of the bottom held still
        t = 1.0 - (y / max(1, h - 1))
        weight = max(0.0, (t - anchor) / max(1e-6, 1.0 - anchor))
        dx = int(round(amp * weight * math.sin(phase)))
        if dx > 0:
            out[y, dx:] = arr[y, :w - dx]
        elif dx < 0:
            out[y, :w + dx] = arr[y, -dx:]
        else:
            out[y] = arr[y]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out-dir", default="art/sprites")
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--amp", type=float, default=1.0, help="peak horizontal displacement in px")
    ap.add_argument("--anchor", type=float, default=0.35, help="fraction of the sprite held still at the base")
    ap.add_argument("--pad", type=int, default=0,
                    help="widen the canvas by this many px each side so the sway never clips")
    a = ap.parse_args()
    arr = np.array(Image.open(a.src).convert("RGBA"))
    if a.pad:
        arr = np.pad(arr, ((0, 0), (a.pad, a.pad), (0, 0)))
    os.makedirs(a.out_dir, exist_ok=True)
    for f in range(a.frames):
        phase = 2.0 * math.pi * f / a.frames
        Image.fromarray(sway(arr, phase, a.amp, a.anchor), "RGBA").save(
            os.path.join(a.out_dir, f"{a.prefix}_f{f}.png"))
    print(f"  {a.prefix}_f0..f{a.frames - 1}.png  {arr.shape[1]}x{arr.shape[0]}  amp {a.amp}px  -> {a.out_dir}")


if __name__ == "__main__":
    main()
