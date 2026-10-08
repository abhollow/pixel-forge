#!/usr/bin/env python3
"""
Builds a looping water animation out of a static background.

Generating wave frames with an image model would not work: separate generations
are not frame-coherent, so the scene, the palette and the foam would all jitter
between frames. Instead this displaces rows of the EXISTING art vertically with
a travelling sine, which is the technique old console games used and is coherent
by construction.

Only the strip from --water-top down is exported, so the frames stay small and
nothing above the shoreline can move. The amplitude fades to zero at the top of
the strip, so it blends into the static shore with no seam.

Re-run whenever the source background changes, or the waves will be displacing
rows of the OLD art and will not match what is on screen. For water that is not
a horizontal band, use the hue-detecting shader (assets/shaders/water.gdshader).

    # in-game level, full 360x640 resolution
    python make_water_frames.py --src raw/background_level1.png \\
        --prefix water --width 360 --height 640 --water-top 390

    # title screen, deliberately chunkier at half resolution
    python make_water_frames.py --src raw/menu_source_fitted.png \\
        --prefix menu_water --width 180 --height 320 --water-top 196

--width/--height default to the art canvas from forge.json.
"""

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def build(src_path, prefix, gw, gh, water_top, frames, amp_shore, amp_deep, fade, out_dir):
    src = np.array(Image.open(src_path).convert("RGB"))
    sh, sw = src.shape[:2]
    scale = sh / gh
    top = int(water_top * scale)
    strip_h = sh - top
    out_h = gh - water_top
    os.makedirs(out_dir, exist_ok=True)

    # Amplitudes are given in output pixels; convert to source pixels so the
    # motion looks the same whatever resolution the art came in at.
    a_shore = amp_shore * scale
    a_deep = amp_deep * scale
    rows = np.arange(strip_h)
    t = rows / strip_h
    # Ramp in from zero so the top edge matches the static art exactly, then
    # ease off with depth -- the shore laps, the deep just swells.
    amp = np.minimum(1.0, t / fade) * (a_shore + (a_deep - a_shore) * t)
    written = []
    for f in range(frames):
        phase = 2.0 * math.pi * f / frames
        # Two components so it doesn't read as one mechanical sine.
        y_src = rows + top + amp * (0.70 * np.sin(phase + rows * 0.011)
                                    + 0.30 * np.sin(2.0 * phase + rows * 0.027 + 1.3))
        # Clamp rather than wrap: wrapping would drag deep water onto the shore.
        idx = np.clip(y_src.astype(int), top, sh - 1)
        frame = src[idx]
        small = Image.fromarray(frame, "RGB").resize((gw, out_h), Image.Resampling.BOX)
        path = os.path.join(out_dir, f"{prefix}_{f:02d}.png")
        small.save(path)
        written.append(path)
        print(f"  {prefix}_{f:02d}.png  {gw}x{out_h}  {os.path.getsize(path) / 1024:.0f} KB")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--width", type=int, default=None, help="default: art canvas width from forge.json")
    ap.add_argument("--height", type=int, default=None, help="default: art canvas height from forge.json")
    ap.add_argument("--out-dir", default="art/sprites", help="default: art/sprites")
    ap.add_argument("--water-top", type=int, required=True, help="in OUTPUT pixels; a little above the foam line")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--amp-shore", type=float, default=2.8, help="output-pixel displacement at the shoreline")
    ap.add_argument("--amp-deep", type=float, default=1.3)
    ap.add_argument("--fade", type=float, default=0.12, help="fraction of the strip over which amplitude ramps in")
    a = ap.parse_args()

    if not a.width or not a.height:
        import forge_image as fi
        cfg = fi.forge_cfg()
        a.width = a.width or cfg.get("art_w") or 180
        a.height = a.height or cfg.get("art_h") or 320
        print(f"size {a.width}x{a.height} (forge.json art canvas{'' if cfg.get('_path') else ' defaults'})")
    print(f"Building {a.frames} frames from {os.path.basename(a.src)}...")
    build(a.src, a.prefix, a.width, a.height, a.water_top, a.frames, a.amp_shore, a.amp_deep, a.fade, a.out_dir)
    print(f"\nStrip sits at y={a.water_top}, {a.height - a.water_top}px tall.")


if __name__ == "__main__":
    main()
