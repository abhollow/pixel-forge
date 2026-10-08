#!/usr/bin/env python3
"""
Builds a walk cycle from one approved sprite (or two drawn poses).

Asking an image model for separate frames does not work: generations are not
frame-coherent, so proportions and palette drift and the cycle flickers.
Frames derived from the ONE approved sprite are coherent by construction and
free. (When the model CAN draw a sheet of poses in one generation, cut it with
slice_sheet.py --shared-box instead; this is for single sprites.)

Styles:
  step (default)  4 frames: rest, left leg lifted + bob, rest, right leg
                  lifted + bob. Only a shallow band at the very bottom moves,
                  split left/right at the CONTENT centroid of that band (a
                  sprite carrying a tool is not centred on its own body). It
                  never mirrors anything: mirroring a band flips the torso
                  and produces a second tool on the wrong side.
  --src2 B        4 frames from two REAL drawn poses: A, A+bob, B, B+bob.
  --pair          2 frames: A, B. No pixel operations at all.
  --mirror-a      make pose B by mirroring A horizontally. The model repeats
                  poses: "two drawn poses" often come back under 12%
                  different; mirroring A typically lifts a ~6% pair to 15%+.
                  Use when check_cycle.py flags a near-duplicate.

At ~24 px the bob is what sells it -- a leg lift alone looks like a glitch,
a bob alone like hovering. Vehicles: --legs 0 (bob only). Below ~18 px wide
legs are 1-2 px and poses vanish; animate in code instead (a 2 px hop per
step, a squash on landing).

    python make_walk_frames.py --src art/sprites/player_00.png --prefix player_walk
    python make_walk_frames.py --src a.png --src2 b.png --prefix enemy_walk
    python make_walk_frames.py --src a.png --mirror-a --pair --prefix enemy_walk

Writes <out-dir>/<prefix>_f0.png ... and prints check_cycle's verdict.
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def leg_band(h, frac):
    """Row range of the leg band, capped so it can never reach the torso."""
    frac = min(frac, 0.34)
    return h - max(2, int(round(h * frac))), h


def step_legs(arr, frac, side, lift):
    """Lift ONE leg (the half of the bottom band on `side` of the content
    centroid) by `lift` px, leaving the other planted."""
    if frac <= 0.0 or lift <= 0:
        return arr.copy()
    h, w = arr.shape[:2]
    cut, _ = leg_band(h, frac)
    band = arr[cut:h]
    xs = np.nonzero(band[..., 3] > 0)[1]
    if not len(xs):
        return arr.copy()
    cx = xs.mean()
    out = arr.copy()
    out[cut:h] = 0
    moving = (np.arange(w) < cx) == (side == "left")
    for y in range(cut, h):
        sy = np.where(moving, y + lift, y)
        valid = (sy >= cut) & (sy < h)
        src = np.zeros((w, 4), np.uint8)
        src[valid] = arr[sy[valid], np.arange(w)[valid]]
        keep = src[:, 3] > 0
        out[y, keep] = src[keep]
    return out


def bob(arr, dy):
    """Shift up by dy, transparent at the bottom."""
    if dy == 0:
        return arr.copy()
    out = np.zeros_like(arr)
    out[:-dy] = arr[dy:]
    return out


def fit_like(arr, ref_shape):
    """Bottom-centre a second pose on the first pose's canvas."""
    if arr.shape == ref_shape:
        return arr
    h, w = ref_shape[:2]
    out = np.zeros(ref_shape, np.uint8)
    ah, aw = arr.shape[:2]
    ox, oy = (w - aw) // 2, h - ah
    sx0, sy0 = max(0, -ox), max(0, -oy)
    out[max(0, oy):max(0, oy) + min(ah, h), max(0, ox):max(0, ox) + min(aw, w)] = \
        arr[sy0:sy0 + min(ah, h), sx0:sx0 + min(aw, w)]
    return out


def build(img, legs=0.34, bob_px=1, lift=1, pose_b=None, pair=False, mirror_a=False):
    if mirror_a:
        pose_b = img[:, ::-1].copy()
    if pose_b is not None:
        pose_b = fit_like(pose_b, img.shape)
        if pair:
            return [img, pose_b], "pair"
        return [img, bob(img, bob_px), pose_b, bob(pose_b, bob_px)], "two-pose"
    if pair:
        raise SystemExit("--pair needs --src2 or --mirror-a")
    return [img, bob(step_legs(img, legs, "left", lift), bob_px),
            img, bob(step_legs(img, legs, "right", lift), bob_px)], "step"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="the approved sprite (pose A)")
    ap.add_argument("--src2", default=None, help="a second drawn pose (B)")
    ap.add_argument("--pair", action="store_true", help="bare 2-frame A-B cycle, no bob, no pixel ops")
    ap.add_argument("--mirror-a", action="store_true", help="pose B = pose A mirrored")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out-dir", default="art/sprites")
    ap.add_argument("--legs", type=float, default=0.34, help="fraction of the height that is legs; 0 = bob only")
    ap.add_argument("--bob", type=int, default=1, help="px lifted on alternate frames")
    ap.add_argument("--lift", type=int, default=1, help="px a single leg lifts in step style")
    ap.add_argument("--style", choices=["step"], default="step", help="kept for old commands; step is the only style")
    a = ap.parse_args()
    img = np.array(Image.open(a.src).convert("RGBA"))
    pose_b = np.array(Image.open(a.src2).convert("RGBA")) if a.src2 else None
    frames, style = build(img, a.legs, a.bob, a.lift, pose_b, a.pair, a.mirror_a)
    os.makedirs(a.out_dir, exist_ok=True)
    for i, f in enumerate(frames):
        Image.fromarray(f, "RGBA").save(os.path.join(a.out_dir, f"{a.prefix}_f{i}.png"))
    print(f"  {a.prefix}_f0..f{len(frames) - 1}.png  {img.shape[1]}x{img.shape[0]}  style {style}"
          f"  bob {0 if style == 'pair' else a.bob}px  -> {a.out_dir}")
    from check_cycle import analyse
    r = analyse(frames)
    print(f"  cycle: widest step {r['widest_step']:.1f}%, narrowest {r['narrowest_step']:.1f}%")
    for fl in r["flags"]:
        print("  FLAG:", fl)


if __name__ == "__main__":
    main()
