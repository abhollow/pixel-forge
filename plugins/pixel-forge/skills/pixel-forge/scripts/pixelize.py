#!/usr/bin/env python3
"""
pixelize.py - turn an AI-generated "pixel art style" illustration into an
actual game-ready pixel image: downscale -> (optional) palette lock ->
hard alpha -> (optional) trim / pad.

AI image models output anti-aliased, high-resolution, thousands-of-colours
images even when you ask for 16x16 pixel art. This does the deterministic
conversion an engine needs.

--target is the LONGEST side of the output, in pixels -- not the width.
  A 960x2160 map converted with --target 960 comes out 427x960, and the game
  then blows it up 2.25x. Pass max(w, h) of the size you want.

You must say how big the output is. One of:
  --target N    long side = N (the usual case)
  --keep-size   no rescale: just palette-lock / harden art you already cut to
                size (use this after slice_sheet / cut_boxes / art_build)
  --detect      guess the faux-pixel grid and divide by it. Only for a single
                illustration with a visible pixel grid. Left to guess on
                2x cuts, it finds their 2-px grid and halves them back to 1x.

The palette is OPTIONAL. A game can ship hundreds of sprites with no palette
lock; hard alpha, integer scale and one-sheet generation carry the look. Lock
to a palette (--palette) when a sheet's colours drift from the rest.

    python pixelize.py hero.png -o hero_32.png --target 32 --palette art/palette.hex
    python pixelize.py raw_art/cut/*.png -O art/sprites --keep-size --palette art/palette_build.hex
    python pixelize.py raw_art/b2/meadow.png -o art/backgrounds/meadow.png --target 960 --no-pad

Requires: Pillow, numpy
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402

# Re-exported: other scripts and older game tools import these from pixelize.
load_palette = fi.load_palette
quantize_to_palette = fi.quantize_to_palette


def auto_palette(rgb, alpha, n_colors):
    """Derive an n-colour palette from the image itself (median cut)."""
    mask = alpha > 0
    if not mask.any():
        mask = np.ones_like(alpha, dtype=bool)
    sub = rgb[mask].reshape(-1, 1, 3).astype(np.uint8)
    tmp = Image.fromarray(sub, "RGB")
    pal_img = tmp.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    raw = pal_img.getpalette()[: n_colors * 3]
    return np.array(raw, dtype=np.uint8).reshape(-1, 3)


def detect_block_size(img, max_block=64):
    """Guess the apparent pixel-block size of a faux-pixel-art image.

    For each candidate factor, downscale and upscale back and measure the
    reconstruction error; keep the LARGEST factor that still reconstructs
    cleanly. Only trust this on one illustration with a visible grid.
    """
    gray = np.array(img.convert("L"), dtype=np.float32)
    h, w = gray.shape
    best, tolerance = 1, 3.0
    for f in range(2, max_block + 1):
        if w // f < 4 or h // f < 4:
            break
        small = np.array(Image.fromarray(gray).resize((w // f, h // f), Image.Resampling.BOX))
        back = np.array(Image.fromarray(small).resize((w, h), Image.Resampling.NEAREST))
        if np.abs(gray - back).mean() <= tolerance:
            best = f
    return best


def output_size(w, h, target):
    """Size whose LONG side is exactly `target`, aspect kept."""
    if w >= h:
        return target, max(1, round(h * target / w))
    return max(1, round(w * target / h)), target


def pixelize(path, target=None, palette=None, colors=None, alpha_threshold=128, trim=False,
             pad_square=True, bg_key=None, bg_tolerance=40, upscale=1, keep_size=False,
             detect=False, resample="box"):
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    rgb, alpha = arr[:, :, :3], arr[:, :, 3]

    # 1. optional chroma-key, for when the background was not removed earlier
    if bg_key is not None:
        key = np.array(bg_key, dtype=np.float32)
        dist = np.abs(rgb.astype(np.float32) - key).sum(axis=2)
        alpha = np.where(dist < bg_tolerance * 3, 0, alpha).astype(np.uint8)
        arr = np.dstack([rgb, alpha])

    # 2. trim to content before scaling, so the target means the subject
    if trim:
        bb = fi.tight_bbox(alpha > alpha_threshold // 2)
        if bb:
            arr = arr[bb[1]:bb[3], bb[0]:bb[2]]

    # 3. downscale (area average; transparent keyed to black first)
    h, w = arr.shape[:2]
    if keep_size:
        new_w, new_h = w, h
    elif target:
        new_w, new_h = output_size(w, h, target)
    elif detect:
        factor = detect_block_size(Image.fromarray(arr, "RGBA"))
        new_w, new_h = max(1, w // factor), max(1, h // factor)
    else:
        raise ValueError("need target, keep_size or detect")
    small = arr if (new_w, new_h) == (w, h) else fi.resize_rgba(arr, (new_w, new_h), resample)

    # 4. quantize (optional)
    srgb, salpha = small[:, :, :3], small[:, :, 3]
    if palette is not None:
        srgb = fi.quantize_to_palette(srgb, palette)
    elif colors:
        srgb = fi.quantize_to_palette(srgb, auto_palette(srgb, salpha, colors))

    # 5. hard alpha - no semi-transparent edge pixels, ever
    salpha = np.where(salpha >= alpha_threshold, 255, 0).astype(np.uint8)
    out = Image.fromarray(np.dstack([srgb, salpha]).astype(np.uint8), "RGBA")

    # 6. pad to a square canvas of exactly `target` (only with --target)
    if pad_square and target and not keep_size:
        canvas = Image.new("RGBA", (target, target), (0, 0, 0, 0))
        canvas.paste(out, ((target - out.size[0]) // 2, (target - out.size[1]) // 2))
        out = canvas

    # 7. optional integer upscale for preview / high-DPI use
    if upscale > 1:
        out = out.resize((out.size[0] * upscale, out.size[1] * upscale), Image.Resampling.NEAREST)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", help="input PNG file(s)")
    p.add_argument("-o", "--output", help="output file (single input only)")
    p.add_argument("-O", "--outdir", help="output directory (many inputs)")
    p.add_argument("--target", type=int,
                   help="LONGEST side of the output in pixels (not the width): "
                        "a 960x2160 map needs --target 2160")
    p.add_argument("--keep-size", action="store_true",
                   help="do not rescale (palette-lock / harden art already cut to size)")
    p.add_argument("--detect", action="store_true",
                   help="guess the faux-pixel grid and divide by it (single illustrations only)")
    p.add_argument("--palette", help="palette .hex/.txt/.png to lock colours to (optional)")
    p.add_argument("--colors", type=int, help="auto-derive an N-colour palette instead")
    p.add_argument("--alpha-threshold", type=int, default=128, help="alpha cutoff, 0-255 (default 128)")
    p.add_argument("--trim", action="store_true", help="crop transparent border before scaling")
    p.add_argument("--no-pad", action="store_true", help="do not pad to a square canvas")
    p.add_argument("--bg-key", help="chroma-key this hex colour to transparent")
    p.add_argument("--bg-tolerance", type=int, default=40)
    p.add_argument("--resample", choices=sorted(fi.RESAMPLE), default="box",
                   help="downscale filter (default box = area average; lanczos rings and adds halo colours)")
    p.add_argument("--upscale", type=int, default=1, help="integer nearest upscale of the result")
    p.add_argument("--report", help="write a JSON summary here")
    args = p.parse_args()

    if args.target == 0:
        args.target = None   # older scripts pass --target 0 meaning "guess"
    modes = sum([bool(args.target), args.keep_size, args.detect])
    if modes == 0:
        p.error("say how big the output is: --target N (LONGEST side), --keep-size (no rescale), "
                "or --detect (guess the pixel grid). Guessing is no longer the default: "
                "it halves 2x art.")
    if modes > 1:
        p.error("use only one of --target, --keep-size, --detect")
    if args.output and len(args.inputs) > 1:
        p.error("-o takes one input; use -O DIR for several")

    pal = fi.load_palette(args.palette) if args.palette else None
    if pal is not None:
        print(f"palette: {len(pal)} colours from {args.palette}")

    key = fi.hex_to_rgb(args.bg_key) if args.bg_key else None

    results = []
    for path in args.inputs:
        out = pixelize(path, target=args.target, palette=pal, colors=args.colors,
                       alpha_threshold=args.alpha_threshold, trim=args.trim,
                       pad_square=not args.no_pad, bg_key=key, bg_tolerance=args.bg_tolerance,
                       upscale=args.upscale, keep_size=args.keep_size, detect=args.detect,
                       resample=args.resample)
        if args.output:
            dest = args.output
        else:
            outdir = args.outdir or "."
            dest = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + ".png")
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        out.save(dest)
        used = fi.colour_count(np.array(out))
        print(f"{path} -> {dest}  {out.size[0]}x{out.size[1]}  {used} colours")
        results.append({"src": path, "dst": dest, "size": list(out.size), "colors": int(used)})

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)


if __name__ == "__main__":
    sys.exit(main())
