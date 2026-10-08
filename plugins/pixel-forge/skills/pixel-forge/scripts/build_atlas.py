#!/usr/bin/env python3
"""
build_atlas.py - pack pixel sprites into a uniform-grid sheet plus a
manifest, and print the exact Godot settings to use.

A uniform grid (rather than tight packing) is deliberate: it maps directly
onto Sprite2D hframes/vframes and AnimatedSprite2D frames with no runtime
lookup. Smaller sprites are centred in their cell, never scaled (non-integer
scaling destroys pixel art).

Often you need no atlas at all: a game with a few hundred sprites ships fine
as individual PNGs loaded by name (ResourceLoader.list_directory works in
exported builds), which is simpler. Pack when a node wants hframes/vframes.

    python build_atlas.py art/sprites/hero_walk_f*.png -o art/hero_walk.png --cell 24 --row
    python build_atlas.py art/sprites/icons/ -o art/icons.png --cell 32
    python build_atlas.py art/sprites/dw_*.png -o art/deer.png --cell 17x20 --row
"""

import argparse
import glob
import json
import math
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def collect(inputs):
    files = []
    for item in inputs:
        if os.path.isdir(item):
            files += sorted(glob.glob(os.path.join(item, "*.png")))
        else:
            files += sorted(glob.glob(item)) or ([item] if os.path.exists(item) else [])
    return list(dict.fromkeys(files))


def parse_cell(text):
    if "x" in text.lower():
        w, h = text.lower().split("x")
        return int(w), int(h)
    return int(text), int(text)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", help="sprite PNGs, globs, or a folder")
    p.add_argument("-o", "--output", required=True, help="output sheet path")
    p.add_argument("--cell", required=True, help="cell size: N or WxH (every sprite must fit)")
    p.add_argument("--cols", type=int, help="columns (default: near-square)")
    p.add_argument("--row", action="store_true", help="lay out in a single row (animation strips)")
    p.add_argument("--manifest", help="manifest path (default: <output>.json)")
    args = p.parse_args()

    files = collect(args.inputs)
    if not files:
        raise SystemExit("no input PNGs found")
    cw, ch = parse_cell(args.cell)
    n = len(files)
    cols = n if args.row else (args.cols or math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)

    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    frames = []
    for i, path in enumerate(files):
        img = Image.open(path).convert("RGBA")
        if img.size[0] > cw or img.size[1] > ch:
            raise SystemExit(f"{path} is {img.size[0]}x{img.size[1]}, bigger than the {cw}x{ch} cell. "
                             f"Cut it smaller first (slice_sheet.py / pixelize.py --target).")
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(img, ((cw - img.size[0]) // 2, (ch - img.size[1]) // 2))
        cx, cy = (i % cols) * cw, (i // cols) * ch
        sheet.paste(canvas, (cx, cy))
        frames.append({"name": os.path.splitext(os.path.basename(path))[0], "index": i,
                       "col": i % cols, "row": i // cols, "x": cx, "y": cy, "w": cw, "h": ch})

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    sheet.save(args.output)
    manifest_path = args.manifest or os.path.splitext(args.output)[0] + ".json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump({"sheet": os.path.basename(args.output), "cell": [cw, ch], "cols": cols, "rows": rows,
                   "frames": frames}, fh, indent=2)

    print(f"sheet    : {args.output}  ({cols * cw}x{rows * ch})")
    print(f"manifest : {manifest_path}")
    print(f"frames   : {n}")
    print()
    print("In Godot, on the Sprite2D using this texture set:")
    print(f"    hframes = {cols}")
    print(f"    vframes = {rows}")
    print("    frame   = <index from the manifest>")
    print()
    print("For AnimatedSprite2D: SpriteFrames -> Add frames from sprite sheet,")
    print(f"    Horizontal {cols}, Vertical {rows}")


if __name__ == "__main__":
    main()
