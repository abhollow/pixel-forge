#!/usr/bin/env python3
"""Round-trip an odd-sized image through an image model that wants a
standard aspect ratio -- and paste the parts that must not change back.

    python fit_ratio.py pad  raw_art/map/plan.png -o raw_art/map/plan_916.png
    ... generate / reimagine plan_916.png in Magnific -> raw_art/map/painted.png
    python fit_ratio.py crop raw_art/map/painted.png --meta raw_art/map/plan_916.json -o raw_art/map/painted_fit.png
    python fit_ratio.py paste-keep raw_art/map/painted_fit.png --source raw_art/map/plan.png \\
        --mask raw_art/map/keep.png --feather 22 -o art/map.png

pad   Pads to the nearest model-friendly ratio (1:1 4:3 3:4 3:2 2:3 16:9 9:16
      21:9 by default) by CARRYING THE EDGE: the last row/column is stretched
      across the pad, so the model sees plain continuation -- mirroring would
      paint a second copy of whatever sits at the edge (e.g. 960x2160 ->
      1215x2160 for 9:16).
      Writes <output>.json with what was added, for crop.
crop  Scales the model's output back to the padded size (it may come back at
      another resolution: a model may return 1344x768 for a 2560x1440 plate;
      stretched back, the layout lines up) and cuts the pad off.
paste-keep
      Puts the protected regions (mask) back EXACTLY from --source, melting
      the edge in with a random dither over --feather px, so every measured
      building, path and door still lines up after a repaint. The mask is
      white = keep by default (--keep black for a mask painted the other way
      round, black = keep).
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
import forge_ndimage as ndi  # noqa: E402

RATIOS = "1:1,4:3,3:4,3:2,2:3,16:9,9:16,21:9"


def parse_ratios(text):
    out = []
    for r in text.split(","):
        a, b = r.split(":")
        out.append((r.strip(), int(a) / int(b)))
    return out


def plan_pad(w, h, ratios, side="auto"):
    """Smallest padding (never cropping) that hits one of the ratios."""
    best = None
    for name, r in ratios:
        if w / h <= r:            # too tall/narrow: widen
            nw, nh = int(round(h * r)), h
        else:                     # too wide: heighten
            nw, nh = w, int(round(w / r))
        nw, nh = max(nw, w), max(nh, h)
        added = nw * nh - w * h
        if best is None or added < best[0]:
            best = (added, name, nw, nh)
    _, name, nw, nh = best
    if side == "auto":
        side = "right" if nw > w else "bottom"
    return name, nw, nh, side


def pad_image(img, nw, nh, side):
    w, h = img.size
    out = Image.new(img.mode, (nw, nh))
    if side in ("right", "bottom"):
        ox, oy = 0, 0
    elif side == "left":
        ox, oy = nw - w, 0
    elif side == "top":
        ox, oy = 0, nh - h
    else:   # both: centre
        ox, oy = (nw - w) // 2, (nh - h) // 2
    out.paste(img, (ox, oy))
    N = Image.Resampling.NEAREST
    if ox > 0:
        out.paste(img.crop((0, 0, 1, h)).resize((ox, h), N), (0, oy))
    if ox + w < nw:
        out.paste(img.crop((w - 1, 0, w, h)).resize((nw - ox - w, h), N), (ox + w, oy))
    if oy > 0:
        out.paste(out.crop((0, oy, nw, oy + 1)).resize((nw, oy), N), (0, 0))
    if oy + h < nh:
        out.paste(out.crop((0, oy + h - 1, nw, oy + h)).resize((nw, nh - oy - h), N), (0, oy + h))
    return out, (ox, oy)


def cmd_pad(a):
    img = Image.open(a.input)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    w, h = img.size
    if a.ratio:
        name, r = a.ratio, parse_ratios(a.ratio)[0][1]
        name, nw, nh, side = plan_pad(w, h, [(name, r)], a.side)
    else:
        name, nw, nh, side = plan_pad(w, h, parse_ratios(a.ratios), a.side)
    if a.side in ("left", "right") and nw == w:
        print("note: %s needs height, not width -- padding the bottom" % name)
        side = "bottom"
    out, (ox, oy) = pad_image(img, nw, nh, side if (nw > w or nh > h) else "right")
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    out.save(a.output)
    meta = {"original": [w, h], "padded": [nw, nh], "offset": [ox, oy], "ratio": name, "source": a.input}
    meta_path = a.meta or os.path.splitext(a.output)[0] + ".json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("%s %dx%d -> %s %dx%d (%s, image at %d,%d); meta %s" % (a.input, w, h, a.output, nw, nh, name, ox, oy, meta_path))


def cmd_crop(a):
    if a.meta:
        with open(a.meta, encoding="utf-8") as fh:
            meta = json.load(fh)
        (w, h), (nw, nh), (ox, oy) = meta["original"], meta["padded"], meta["offset"]
    else:
        if not (a.orig and a.padded):
            raise SystemExit("crop needs --meta, or --orig WxH and --padded WxH (and --offset X,Y)")
        w, h = fi.parse_size(a.orig)
        nw, nh = fi.parse_size(a.padded)
        ox, oy = (int(v) for v in (a.offset or "0,0").split(","))
    img = Image.open(a.input)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    if img.size != (nw, nh):
        r0, r1 = img.size[0] / img.size[1], nw / nh
        if abs(r0 - r1) / r1 > 0.02:
            print("WARNING: model output %dx%d is not the padded ratio (%dx%d); stretching anyway"
                  % (img.size[0], img.size[1], nw, nh))
        img = img.resize((nw, nh), fi.RESAMPLE[a.resample])
    out = img.crop((ox, oy, ox + w, oy + h))
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    out.save(a.output)
    print("%s -> %s %dx%d" % (a.input, a.output, w, h))


def paste_keep(base, source, keep, feather=22, seed=3):
    """base, source: uint8 arrays of the same shape; keep: bool mask."""
    depth = ndi.distance_inside(keep, limit=max(1, feather) + 1)
    rng = np.random.default_rng(seed)
    take = keep & (rng.random(keep.shape) < np.clip(depth / max(1, feather), 0, 1))
    out = base.copy()
    out[take] = source[take]
    return out, int(take.sum())


def cmd_paste(a):
    base = Image.open(a.input)
    mode = "RGBA" if base.mode in ("RGBA", "LA", "P") else "RGB"
    base = np.array(base.convert(mode))
    src_img = Image.open(a.source).convert(mode)
    if src_img.size != (base.shape[1], base.shape[0]):
        print("WARNING: source %dx%d resized to the base %dx%d" % (src_img.size + (base.shape[1], base.shape[0])))
        src_img = src_img.resize((base.shape[1], base.shape[0]), Image.Resampling.LANCZOS)
    m = Image.open(a.mask).convert("L")
    if m.size != (base.shape[1], base.shape[0]):
        m = m.resize((base.shape[1], base.shape[0]), Image.Resampling.NEAREST)
    m = np.array(m)
    keep = m < 128 if a.keep == "black" else m >= 128
    out, n = paste_keep(base, np.array(src_img), keep, a.feather, a.seed)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    Image.fromarray(out, mode).save(a.output)
    print("%s: %d px pasted back from %s (feather %d) -> %s" % (a.input, n, a.source, a.feather, a.output))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pad", help="pad to the nearest model-friendly ratio by carrying the edges")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--ratio", help="force one ratio, e.g. 9:16")
    p.add_argument("--ratios", default=RATIOS, help="candidates (default %s)" % RATIOS)
    p.add_argument("--side", choices=["auto", "right", "left", "bottom", "top", "both"], default="auto",
                   help="where the pad goes (auto: right or bottom)")
    p.add_argument("--meta", help="where to write the round-trip JSON (default <output>.json)")
    c = sub.add_parser("crop", help="scale the model's output to the padded size and cut the pad off")
    c.add_argument("input")
    c.add_argument("-o", "--output", required=True)
    c.add_argument("--meta", help="the JSON written by pad")
    c.add_argument("--orig", help="original WxH (without --meta)")
    c.add_argument("--padded", help="padded WxH (without --meta)")
    c.add_argument("--offset", help="X,Y of the original inside the pad (without --meta)")
    c.add_argument("--resample", choices=sorted(fi.RESAMPLE), default="lanczos")
    k = sub.add_parser("paste-keep", aliases=["paste_keep"],
                       help="paste protected mask regions back from the source with a dithered feather")
    k.add_argument("input", help="the repainted image (base)")
    k.add_argument("--source", required=True, help="the image to take kept regions from")
    k.add_argument("--mask", required=True, help="greyscale mask of what to keep")
    k.add_argument("--keep", choices=["white", "black"], default="white", help="which mask value means keep")
    k.add_argument("--feather", type=int, default=22, help="px of dithered edge inside each kept region")
    k.add_argument("--seed", type=int, default=3)
    k.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    {"pad": cmd_pad, "crop": cmd_crop, "paste-keep": cmd_paste, "paste_keep": cmd_paste}[a.cmd](a)


if __name__ == "__main__":
    main()
