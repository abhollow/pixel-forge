#!/usr/bin/env python3
"""
Turns one AI-generated "pixel art" image (or a regular grid of them) into
pixel art the game can use: trim, square-pad, box downscale, optional palette
snap, hard alpha.

Image models don't produce pixel art -- they produce a high-resolution
painting OF pixel art: soft anti-aliased edges, a pixel grid that drifts, and
hundreds of near-duplicate colours. Dropped into the game at 24x24 that reads
as a blurry smudge.

  1. trim      crop away empty margin so the subject fills the frame
  2. downscale box-average to the target size (area mean, not bilinear;
               transparent keyed to black first so nothing fringes)
  3. quantize  OPTIONAL: snap every colour to a palette (--palette). A game
               can ship hundreds of sprites with no palette lock -- hard
               alpha, integer scale and one-sheet generation do the work.
               Lock when a sprite's colours drift from the rest.
  4. harden    threshold alpha so edges are on/off, never feathered

For sheets with unevenly spaced subjects use slice_sheet.py instead; --cols /
--rows here cut an exact grid.

    python prep_sprite.py raw/crate.png -o art/sprites/crate.png -s 32x32
    python prep_sprite.py raw/player_sheet.png -o art/sprites/player -s 24x24 --cols 4
    python prep_sprite.py raw/x.png -o out.png -s 32x32 --palette art/palette.hex
    python prep_sprite.py raw/bg.png -o art/bg.png --no-square      # size = forge.json art canvas
"""

import argparse
import os
import sys

import numpy as np

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip install Pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402


def trim(arr, alpha_floor=8):
    """Crop to the subject. Uses alpha when present, otherwise the corner colour."""
    if fi.has_alpha(arr):
        bb = fi.tight_bbox(arr[..., 3] > alpha_floor)
    else:
        bg = arr[0, 0, :3].astype(int)
        diff = np.abs(arr[..., :3].astype(int) - bg).sum(axis=2)
        bb = fi.tight_bbox(diff > 30)
    if not bb:
        return arr
    return arr[bb[1]:bb[3], bb[0]:bb[2]]


def fit_square(arr):
    """Pad to a square so the downscale doesn't distort the aspect ratio."""
    h, w = arr.shape[:2]
    if w == h:
        return arr
    side = max(w, h)
    out = np.zeros((side, side, 4), np.uint8)
    out[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = arr
    return out


def process(arr, size, palette=None, alpha_threshold=128, no_trim=False, no_square=False):
    if not no_trim:
        arr = trim(arr)
    if not no_square:
        arr = fit_square(arr)
    arr = fi.resize_rgba(arr, size, "box")
    if palette is not None:
        arr = fi.lock_rgba(arr, palette)
    return fi.hard_alpha(arr, alpha_threshold)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True, help="output PNG, or output directory when slicing a grid")
    ap.add_argument("-s", "--size", default=None, type=fi.parse_size,
                    help="target size, e.g. 24x24 (default: the art canvas from forge.json)")
    ap.add_argument("--cols", type=int, default=1, help="grid columns to slice")
    ap.add_argument("--rows", type=int, default=1, help="grid rows to slice")
    ap.add_argument("--palette", default=None, help="optional palette .hex/.txt/.png to snap to")
    ap.add_argument("--alpha-threshold", type=int, default=128)
    ap.add_argument("--no-quantize", action="store_true", help="ignore --palette (kept for old commands)")
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--no-square", action="store_true",
                    help="skip square padding (non-square subjects already framed, backgrounds)")
    args = ap.parse_args()

    if args.size is None:
        cfg = fi.forge_cfg()
        args.size = (cfg.get("art_w") or 180, cfg.get("art_h") or 320)
        print(f"size from forge.json: {args.size[0]}x{args.size[1]} (the art canvas)")
    pal = None if (args.no_quantize or not args.palette) else fi.load_palette(args.palette)
    src = np.array(Image.open(args.input).convert("RGBA"))

    if args.cols == 1 and args.rows == 1:
        out = process(src, args.size, pal, args.alpha_threshold, args.no_trim, args.no_square)
        fi.save_rgba(out, args.output)
        print(f"{args.input} -> {args.output}  {out.shape[1]}x{out.shape[0]}  {fi.colour_count(out)} colours")
        return

    os.makedirs(args.output, exist_ok=True)
    h, w = src.shape[:2]
    cw, ch = w // args.cols, h // args.rows
    n = 0
    for r in range(args.rows):
        for c in range(args.cols):
            cell = src[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            out = process(cell, args.size, pal, args.alpha_threshold, args.no_trim, args.no_square)
            path = os.path.join(args.output, f"{n:02d}.png")
            fi.save_rgba(out, path)
            print(f"  cell {r},{c} -> {path}  {out.shape[1]}x{out.shape[0]}  {fi.colour_count(out)} colours")
            n += 1
    print(f"Sliced {n} sprites into {args.output}/")


if __name__ == "__main__":
    main()
