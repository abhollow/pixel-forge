#!/usr/bin/env python3
"""
Slices a generated sprite sheet into individual game-ready PNGs.

It FINDS each sprite instead of cutting a fixed grid: generated sheets never
space their subjects evenly, and a grid cut clips limbs and centres badly.
Each sprite keeps its aspect ratio, scaled to fit its target box (BOX
downscale, transparent keyed to black first, hard alpha, pinholes closed).

Two ways to find sprites:

  --mode profile (default)  split by row then column occupancy profiles.
        Right for tidy sheets and animation strips (--rows, --shared-box).
        It MERGES sheets whose rows overlap vertically.
  --mode blob               each sprite is its own connected blob, grown by
        --grow px so loose parts (a ladder, a smoke puff) stay attached;
        specks dropped; read in rows by vertical centre, left to right;
        the count must match --sizes; the cut is a tight box round the real
        pixels, not the grown blob. Building kits usually need this.

Keying (--key): magenta (default), green (for pink/red subjects), auto (from
the border), corner (whatever flat colour the corners are). The key is a
RATIO test, not an exact colour, and only background connected to the image
border is keyed, so a hot-pink shirt inside an outline survives. Enclosed
pockets of pure key (between an arm and a body) are keyed too.

--despill pulls the magenta/green cast out of the kept pixels AFTER keying
from the raw sheet (keying after despill turns drop shadows grey and merges
neighbours).

Scaling a SET (animation frames, a creature's states):
  --shared-box          one box for every frame, aligned by --anchor, one
                        scale for all. Without it each frame is scaled on its
                        own and a frame with a longer limb gets a smaller body.
  --scale-by set        one scale for all (the largest that fits every box)
  --scale-by ref:N      sprite N's fit scale for all (e.g. a bird's frames
                        scaled by the perched frame)
  --scale-by colour:HEX[:TOL] --feature-px P
                        measure the width of a feature colour (a beetle's
                        orange shell) so the feature is P px wide in every
                        frame; frames full of flying dust no longer shrink it
  --scale K             an explicit factor (the one printed for a sibling sheet)
  --anchor bottom|centre|top|left|right   where each sprite sits in its box
                        (feet on the ground = bottom; beak-aligned = right)

    python slice_sheet.py --src raw/player_sheet.png --prefix player \\
        --sizes 16x16,16x16,16x20,20x20,20x28
    python slice_sheet.py raw_art/b7/homes_a.png --mode blob --prefix home \\
        --sizes 105x82,105x75,105x78,70x68,65x55,58x72 --despill
    python slice_sheet.py --src raw/wolf.png --prefix wanim --sizes 54x30 \\
        --rows 2 --shared-box --anchor bottom --clean-fringe
    python slice_sheet.py --src raw/pink_bird.png --key green --prefix bird --sizes 30x30
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402
import forge_ndimage as ndi  # noqa: E402


# ---------------------------------------------------------------------------
# finding sprites
# ---------------------------------------------------------------------------

def spans(profile, threshold, gap, min_len=0):
    """1-D occupancy profile -> [start, end) runs; gaps < `gap` merge; runs
    shorter than `min_len` are dropped (a stray fragment would otherwise
    become its own sprite and throw the grid out)."""
    occ = np.asarray(profile) > threshold
    if not occ.any():
        return []
    d = np.diff(np.concatenate([[0], occ.astype(np.int8), [0]]))
    starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
    merged = []
    for s, e in zip(starts, ends):
        if merged and s - merged[-1][1] < gap:
            merged[-1][1] = int(e)
        else:
            merged.append([int(s), int(e)])
    return [r for r in merged if (r[1] - r[0]) >= min_len]


def find_profile(fg, solid, rows, gap, row_gap):
    """Profile mode. `solid` is fg without specks (used for projection and
    the tight boxes); returns sprites as dicts with box + own-mask region."""
    h, w = fg.shape
    row_bounds = [(0, h)]
    if rows > 1:
        rg = row_gap if row_gap is not None else gap * 2
        row_bounds = [tuple(r) for r in spans(solid.sum(axis=1), 0, rg, int(h * 0.04))]
        if len(row_bounds) != rows:
            print(f"WARNING: asked for {rows} rows, found {len(row_bounds)} "
                  f"(try --row-gap, or --mode blob if rows overlap)")
    found = []
    for (y0, y1) in row_bounds:
        for (x0, x1) in spans(solid[y0:y1].sum(axis=0), 0, gap, int(w * 0.04)):
            bb = fi.tight_bbox(solid[y0:y1, x0:x1])
            if bb is None:
                continue
            box = (x0 + bb[0], y0 + bb[1], x0 + bb[2], y0 + bb[3])
            region = (x0, y0, x1, y1)
            own = fg[y0:y1, x0:x1].copy()
            found.append({"box": box, "region": region, "own": own})
    return found


def find_blobs(fg, grow, speck_frac):
    """Blob mode: connected blobs, plus own-pixel masks so a neighbour
    reaching into the box is not cut along with the sprite."""
    h, w = fg.shape
    grown = ndi.binary_dilation(fg, grow)
    labels, n = ndi.label(grown)
    if n == 0:
        return [], 0
    objs = ndi.find_objects(labels, n)
    areas = ndi.sizes(labels, n)
    keep, specks = [], 0
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        if areas[i] <= speck_frac * fg.size:
            specks += 1
            continue
        own = fg[sl] & (labels[sl] == i + 1)
        bb = fi.tight_bbox(own)
        if bb is None:
            continue
        y0, x0 = sl[0].start, sl[1].start
        keep.append({"box": (x0 + bb[0], y0 + bb[1], x0 + bb[2], y0 + bb[3]),
                     "region": (x0, y0, sl[1].stop, sl[0].stop), "own": own})
    if not keep:
        return [], specks
    # reading order: rows by vertical centre (a row = centres within half the
    # height of the row's first sprite), then left to right
    def cy(s):
        return (s["box"][1] + s["box"][3]) / 2
    keep.sort(key=cy)
    rows, cur = [], [keep[0]]
    for s in keep[1:]:
        hh = cur[0]["box"][3] - cur[0]["box"][1]
        if cy(s) - cy(cur[0]) > hh / 2:
            rows.append(cur)
            cur = [s]
        else:
            cur.append(s)
    rows.append(cur)
    return [s for row in rows for s in sorted(row, key=lambda s: s["box"][0])], specks


# ---------------------------------------------------------------------------
# cutting and scaling
# ---------------------------------------------------------------------------

def crop_own(rgb, sprite, box):
    """RGBA crop of `box` (may reach past the sheet) showing only this
    sprite's own pixels."""
    bx0, by0, bx1, by1 = box
    out = np.zeros((by1 - by0, bx1 - bx0, 4), np.uint8)
    rx0, ry0, rx1, ry1 = sprite["region"]
    ix0, iy0 = max(bx0, rx0), max(by0, ry0)
    ix1, iy1 = min(bx1, rx1), min(by1, ry1)
    if ix1 <= ix0 or iy1 <= iy0:
        return out
    own = sprite["own"][iy0 - ry0:iy1 - ry0, ix0 - rx0:ix1 - rx0]
    tgt = out[iy0 - by0:iy1 - by0, ix0 - bx0:ix1 - bx0]
    tgt[..., :3] = rgb[iy0:iy1, ix0:ix1, :3]
    tgt[..., 3] = np.where(own, 255, 0)
    return out


def shared_boxes(sprites, anchor):
    """One box size for all frames (largest frame + 1 px margin each side),
    aligned on each frame by the anchor."""
    bw = max(s["box"][2] - s["box"][0] for s in sprites) + 2
    bh = max(s["box"][3] - s["box"][1] for s in sprites) + 2
    out = []
    for s in sprites:
        x0, y0, x1, y1 = s["box"]
        if anchor == "left":
            bx = x0 - 1
        elif anchor == "right":
            bx = x1 + 1 - bw
        else:
            bx = (x0 + x1) // 2 - bw // 2
        if anchor == "bottom":
            by = y1 + 1 - bh
        elif anchor in ("top",):
            by = y0 - 1
        elif anchor in ("left", "right", "centre", "center"):
            by = (y0 + y1) // 2 - bh // 2
        else:
            by = y0 - 1
        out.append((bx, by, bx + bw, by + bh))
    return out


def feature_width(arr, colour, tol):
    a = arr.astype(np.float32)
    near = (np.sqrt(((a[..., :3] - np.array(colour, np.float32)) ** 2).sum(axis=2)) < tol) & (arr[..., 3] > 0)
    xs = np.nonzero(near.any(axis=0))[0]
    return int(xs.max() - xs.min() + 1) if len(xs) else 0


def choose_scales(crops, sizes, scale_by, feature_px, explicit, shared):
    fits = [fi.fit_factor((c.shape[1], c.shape[0]), t) for c, t in zip(crops, sizes)]
    if explicit:
        return [explicit] * len(crops), "explicit"
    if scale_by == "fit" and not shared:
        return fits, "fit"
    if scale_by in ("fit", "set"):
        return [min(fits)] * len(crops), "set"
    if scale_by.startswith("ref:"):
        n = int(scale_by[4:])
        if not 0 <= n < len(crops):
            raise SystemExit(f"--scale-by {scale_by}: only {len(crops)} sprites")
        return [fits[n]] * len(crops), scale_by
    if scale_by.startswith("colour:") or scale_by.startswith("color:"):
        parts = scale_by.split(":")
        colour = fi.hex_to_rgb(parts[1])
        tol = float(parts[2]) if len(parts) > 2 else 40.0
        if not feature_px:
            raise SystemExit("--scale-by colour:... needs --feature-px (the feature's width in the output)")
        widths = [feature_width(c, colour, tol) for c in crops]
        good = [x for x in widths if x > 0]
        if not good:
            raise SystemExit(f"--scale-by {scale_by}: that colour was not found in any sprite")
        print(f"feature widths (source px): {widths}")
        return [feature_px / float(np.median(good))] * len(crops), scale_by
    raise SystemExit(f"unknown --scale-by {scale_by}")


def debug_sheet(rgb, sprites, path, boxes=None):
    img = Image.fromarray(rgb[..., :3].astype(np.uint8), "RGB")
    k = min(1.0, 1600 / max(img.size))
    if k < 1:
        img = img.resize((int(img.width * k), int(img.height * k)), Image.Resampling.BOX)
    d = ImageDraw.Draw(img)
    for i, s in enumerate(sprites):
        b = (boxes[i] if boxes else s["box"])
        r = [int(b[0] * k), int(b[1] * k), int(b[2] * k) - 1, int(b[3] * k) - 1]
        d.rectangle(r, outline=(255, 255, 0), width=2)
        d.rectangle([r[0], r[1], r[0] + 22, r[1] + 14], fill=(0, 0, 0))
        d.text((r[0] + 3, r[1] + 2), "%02d" % i, fill=(255, 255, 0))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)
    print(f"debug sheet: {path}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run(a):
    src_path = a.src
    img = np.array(Image.open(src_path).convert("RGBA"))
    h, w = img.shape[:2]

    if fi.has_alpha(img):
        fg = img[..., 3] > 127
        key = a.key if a.key in ("magenta", "green") else "magenta"
        info = {"key": "alpha", "enclosed_keyed": 0}
    else:
        bg, info = fi.background_mask(img, a.key, a.key_tol,
                                      enclosed="keep" if a.keep_enclosed else "auto")
        fg = ~bg
        key = info["key"]
    print(f"{os.path.basename(src_path)}: {w}x{h}, key {info['key']}"
          + (f", {info['enclosed_keyed']} enclosed key pocket(s) keyed" if info.get("enclosed_keyed") else ""))

    rgb = img[..., :3].copy()
    if a.despill:
        if key in ("magenta", "green"):
            rgb = fi.despill(rgb, key, a.despill_strength, where=fg).round().astype(np.uint8)
        else:
            print("WARNING: --despill needs a magenta or green key; skipped")

    if a.mode == "blob":
        speck = a.speck if a.speck is not None else 0.002
        sprites, dropped = find_blobs(fg, a.grow, speck)
    else:
        speck = a.speck if a.speck is not None else 0.0005
        solid = ndi.drop_small(fg, max(2, int(speck * fg.size)))
        dropped = int(ndi.label(fg & ~solid)[1])
        sprites = find_profile(fg, solid, a.rows, a.gap, a.row_gap)
    if dropped:
        print(f"ignored {dropped} speck(s)")
    if not sprites:
        raise SystemExit("no sprites found -- wrong --key? (try --key auto, or --debug-sheet to look)")

    sizes = fi.parse_sizes(a.sizes)
    expect = a.expect or (len(sizes) if len(sizes) > 1 else None)
    boxes = shared_boxes(sprites, a.anchor or "top") if a.shared_box else [s["box"] for s in sprites]
    if a.debug_sheet:
        debug_sheet(rgb, sprites, a.debug_sheet, boxes)
    if expect and len(sprites) != expect:
        listing = ", ".join("%d:%dx%d@%d,%d" % (i, s["box"][2] - s["box"][0], s["box"][3] - s["box"][1],
                                                s["box"][0], s["box"][1]) for i, s in enumerate(sprites))
        msg = f"found {len(sprites)} sprites, {expect} expected ({len(sizes)} sizes given): {listing}"
        if a.mode == "blob":
            msg += "\n  merged neighbours -> lower --grow; split parts -> raise --grow; specks -> raise --speck"
        else:
            msg += "\n  rows overlapping -> --mode blob; split figures -> raise --gap"
        raise SystemExit(msg)
    if len(sizes) == 1:
        sizes = sizes * len(sprites)

    crops = [crop_own(rgb, s, b) for s, b in zip(sprites, boxes)]
    scales, how = choose_scales(crops, sizes, a.scale_by, a.feature_px, a.scale, a.shared_box)
    if how != "fit":
        print(f"one scale for the set ({how}): {scales[0]:.5f}  "
              f"(pass --scale {scales[0]:.5f} to cut a sibling sheet at the same scale)")

    pal = fi.load_palette(a.palette) if a.palette else None
    os.makedirs(a.out_dir, exist_ok=True)
    print(f"Found {len(sprites)} sprites in {os.path.basename(src_path)}")
    written = []
    for i, (crop, target, k) in enumerate(zip(crops, sizes, scales)):
        small = fi.scale_sprite(crop, k, a.resample)
        out, overflow = fi.place(small, target, a.anchor or "centre")
        if overflow:
            print(f"  WARNING {a.prefix}_{i:02d}: {small.shape[1]}x{small.shape[0]} overflows "
                  f"{target[0]}x{target[1]} by {overflow}px (cropped)")
        if a.clean_fringe:
            out = fi.clean_fringe(out, key)
        if pal is not None:
            out = fi.lock_rgba(out, pal)
        path = os.path.join(a.out_dir, f"{a.prefix}_{i:02d}.png")
        fi.save_rgba(out, path)
        written.append({"file": path, "size": list(target), "source_box": list(boxes[i]), "scale": k})
        print(f"  {a.prefix}_{i:02d}.png  source {crop.shape[1]}x{crop.shape[0]}  ->  {target[0]}x{target[1]}")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            json.dump({"src": src_path, "key": info["key"], "mode": a.mode, "sprites": written}, fh, indent=2)
    return written


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", nargs="?", help="the sheet (same as --src)")
    ap.add_argument("--src", help="the sheet to slice")
    ap.add_argument("--prefix", required=True, help="output names: <prefix>_00.png, _01 ...")
    ap.add_argument("--sizes", required=True,
                    help="one WxH for all, or a comma list, one per sprite in reading order")
    ap.add_argument("--mode", choices=["profile", "blob"], default="profile",
                    help="profile (row/column projection; default) or blob (connected blobs; "
                         "for sheets whose rows overlap)")
    ap.add_argument("--out-dir", default="art/sprites")
    ap.add_argument("--key", choices=["magenta", "green", "auto", "corner"], default="magenta",
                    help="background key (ratio-based): magenta, green for pink subjects, auto, corner colour")
    ap.add_argument("--key-tol", type=float, default=60.0, help="tolerance for --key corner")
    ap.add_argument("--keep-enclosed", action="store_true",
                    help="never key enclosed pockets of key colour (border-connected background only)")
    ap.add_argument("--despill", action="store_true",
                    help="remove the key's colour cast inside the kept pixels (after keying)")
    ap.add_argument("--despill-strength", type=float, default=1.0)
    ap.add_argument("--rows", type=int, default=1, help="profile mode: rows on the sheet")
    ap.add_argument("--gap", type=int, default=12,
                    help="profile mode: columns closer than this are one sprite")
    ap.add_argument("--row-gap", type=int, default=None,
                    help="profile mode: same for rows (default 2x --gap). Figures with wide internal "
                         "gaps need a LARGE --gap and a SMALL --row-gap, or the rows merge.")
    ap.add_argument("--grow", type=int, default=12,
                    help="blob mode: px a blob is grown so loose parts stay attached")
    ap.add_argument("--speck", type=float, default=None,
                    help="ignore pieces smaller than this fraction of the sheet area "
                         "(default 0.0005 profile, 0.002 blob [of the grown blob])")
    ap.add_argument("--expect", type=int, default=None,
                    help="assert this many sprites (implied by a list of --sizes)")
    ap.add_argument("--shared-box", action="store_true",
                    help="ANIMATION FRAMES: one box and one scale for every frame, aligned by --anchor")
    ap.add_argument("--anchor", choices=["centre", "center", "bottom", "top", "left", "right"],
                    default=None,
                    help="where each sprite sits in its box (default centre); with --shared-box also how "
                         "frames are aligned (default top)")
    ap.add_argument("--scale-by", default="fit",
                    help="fit (each its own; default), set, ref:N, colour:HEX[:TOL] (with --feature-px)")
    ap.add_argument("--feature-px", type=float, default=None,
                    help="with --scale-by colour: the feature's width in output px")
    ap.add_argument("--scale", type=float, default=None, help="explicit scale factor for every sprite")
    ap.add_argument("--resample", choices=sorted(fi.RESAMPLE), default="box",
                    help="downscale filter (default box)")
    ap.add_argument("--clean-fringe", action="store_true",
                    help="remove leftover key-coloured pixels on the edge (never on a subject coloured like the key)")
    ap.add_argument("--palette", default=None, help="optional: lock to this palette after cutting")
    ap.add_argument("--debug-sheet", default=None,
                    help="write the sheet with numbered boxes here (look at it before trusting a cut)")
    ap.add_argument("--report", default=None, help="write a JSON list of what was cut")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    a.src = a.src or a.sheet
    if not a.src:
        ap.error("give the sheet (positional or --src)")
    if a.anchor == "center":
        a.anchor = "centre"
    run(a)


if __name__ == "__main__":
    main()
