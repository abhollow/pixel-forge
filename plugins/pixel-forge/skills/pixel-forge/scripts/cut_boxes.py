#!/usr/bin/env python3
"""Cut sprites out of sheets by EXPLICIT boxes listed in a JSON file.

    python cut_boxes.py art/boxes/icons.json --out-dir raw_art/cut
    python cut_boxes.py art/boxes/icons.json --only icon_heart,icon_coin --debug-dir docs/screens

Why: some sheets mix sizes and loose bits -- rain under a cloud, sparks round
a burst, pebbles round rocks -- and blob or profile cutting tangles them. A
box per item, measured once on the raw sheet,
is exact and repeatable. Icon sheets that came back on a flat non-magenta
colour are keyed on that colour (corner key).

Box file (paths relative to the JSON file's folder, then the current folder):

    {
      "defaults": {"key": "magenta", "mode": "body", "despill": true},
      "items": {
        "fx_crack":    {"sheet": "../../raw_art/b12/fx_a.png",
                        "box": [80, 800, 1170, 1480], "size": "100x64", "mode": "all"},
        "icon_heart":  {"sheet": "../../raw_art/b12/icons_a.png", "box": [150, 470, 740, 1070],
                        "size": "32x32", "key": "corner", "corner_at": [8, 8], "unblue": true},
        "glow_orb":    {"sheet": "...", "box": [...], "size": "24x24", "mode": "glow"}
      }
    }

Per item: sheet, box [x0, y0, x1, y1] (sheet pixels), size "WxH" (fit, aspect
kept) or scale (factor), and optionally:
  mode     body = keep only the biggest piece (the cloud without its rain)
           all  = every piece bigger than `speck` px (the burst's sparks)
           glow = all pieces, and pink glow recoloured warm white (the model
                  blends glows with the magenta key into pink, and pink snaps
                  to red)
  key      magenta | green | corner | hue | auto   (hue = r and b both above g
           by key_tol, default 28: kills a pink halo; tan/red/blue survive)
  key_tol, corner_at [x, y], speck (default 30), despill (default true for
  magenta/green/hue), unblue (blue-leaning pixels -> neutral grey, for
  palettes with no blue-greys), pad (true = centre on the full WxH canvas by
  `anchor`; default: the fitted size), palette (lock after cutting), out
  (file name, default <name>.png).
"items" may also be a list of objects with a "name". --density 2 cuts the
same boxes again at twice every size (the HD set, always from raw).
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


def warm_glow(x):
    """Pink (glow blended with the magenta key) -> warm white, by brightness."""
    x = x.astype(np.float32)
    hi = np.maximum(x[..., 0], x[..., 2])
    pink = np.minimum(x[..., 0], x[..., 2]) > x[..., 1] + 12
    out = x.copy()
    out[..., 0] = np.where(pink, hi, x[..., 0])
    out[..., 1] = np.where(pink, hi * 0.94, x[..., 1])
    out[..., 2] = np.where(pink, hi * 0.70, x[..., 2])
    return out


def unblue(x):
    """Blue-leaning pixels to neutral grey of the same luma: a palette with no
    blue-greys would snap them to green-greys and speckle (grey slate, stone)."""
    x = x.astype(np.float32)
    lum = x[..., 0] * 0.3 + x[..., 1] * 0.59 + x[..., 2] * 0.11
    blue = (x[..., 2] > x[..., 0] + 4) & (x[..., 2] >= x[..., 1] - 6)
    out = x.copy()
    for c in range(3):
        out[..., c] = np.where(blue, lum, x[..., c])
    return out


def resolve(path, base_dirs):
    if os.path.isabs(path):
        return path
    for b in base_dirs:
        p = os.path.join(b, path)
        if os.path.exists(p):
            return p
    return os.path.join(base_dirs[-1], path)


def cut_item(arr, item, density=1.0):
    """arr: full sheet RGB uint8. Returns an RGBA uint8 sprite."""
    x0, y0, x1, y1 = [int(v) for v in item["box"]]
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        raise SystemExit("box %s is outside the sheet (%dx%d)" % (item["box"], w, h))
    key = item.get("key", "magenta")
    if key == "auto":
        key = fi.detect_key(arr)
    if key == "corner":
        bg = fi.key_candidates(arr, "corner", float(item.get("key_tol", 48.0)), item.get("corner_at", [8, 8]))
    else:
        bg = fi.key_candidates(arr, key, float(item.get("key_tol", 28.0 if key == "hue" else 60.0)))
    a = arr[y0:y1, x0:x1].astype(np.float32)
    fg = ~bg[y0:y1, x0:x1]
    labels, n = ndi.label(fg)
    if n == 0:
        raise SystemExit("nothing but background in box %s" % (item["box"],))
    sz = ndi.sizes(labels, n)
    mode = item.get("mode", "body")
    if mode == "body":
        fg = labels == (int(np.argmax(sz)) + 1)
    else:
        keep = np.zeros(n + 1, bool)
        keep[1:] = sz > int(item.get("speck", 30))
        fg = keep[labels]
    if mode == "glow":
        a = warm_glow(a)
    elif item.get("despill", key in ("magenta", "green", "hue")):
        a = fi.despill(a, "green" if key == "green" else "magenta", 1.0, where=fg)
    if item.get("unblue"):
        a = unblue(a)
    bb = fi.tight_bbox(fg)
    if bb is None:
        raise SystemExit("nothing kept in box %s" % (item["box"],))
    rgba = np.dstack([np.clip(a, 0, 255), np.where(fg, 255, 0)]).astype(np.uint8)
    crop = rgba[bb[1]:bb[3], bb[0]:bb[2]]
    if "scale" in item:
        k = float(item["scale"]) * density
        return fi.scale_sprite(crop, k)
    size = fi.parse_size(item["size"])
    size = (max(1, round(size[0] * density)), max(1, round(size[1] * density)))
    k = fi.fit_factor((crop.shape[1], crop.shape[0]), size)
    small = fi.scale_sprite(crop, k)
    if item.get("pad", False):
        small, _ = fi.place(small, size, item.get("anchor", "centre"))
    return small


def load_items(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    defaults = data.get("defaults", {})
    raw = data.get("items", data if isinstance(data, list) else {})
    items = []
    if isinstance(raw, dict):
        for name, it in raw.items():
            items.append(dict(defaults, **it, name=name))
    else:
        for it in raw:
            if "name" not in it:
                raise SystemExit("every item in a list needs a \"name\"")
            items.append(dict(defaults, **it))
    return data, items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("boxes", help="the JSON box file")
    ap.add_argument("--out-dir", default="raw_art/cut", help="where sprites go (default raw_art/cut)")
    ap.add_argument("--only", default=None, help="comma list of item names to cut")
    ap.add_argument("--density", type=float, default=1.0,
                    help="multiply every size/scale (2 = the HD set, cut again from raw)")
    ap.add_argument("--palette", default=None, help="lock every item to this palette (item 'palette' wins)")
    ap.add_argument("--debug-dir", default=None, help="write each sheet with its boxes drawn here")
    ap.add_argument("--report", default=None, help="write a JSON list of what was cut")
    a = ap.parse_args()

    data, items = load_items(a.boxes)
    base = [os.path.dirname(os.path.abspath(a.boxes)), os.getcwd()]
    only = set(a.only.split(",")) if a.only else None
    sheets, written = {}, []
    os.makedirs(a.out_dir, exist_ok=True)
    for it in items:
        if only and it["name"] not in only:
            continue
        if "sheet" not in it or "box" not in it:
            raise SystemExit("item %s needs 'sheet' and 'box'" % it["name"])
        sp = resolve(it["sheet"], base)
        if sp not in sheets:
            sheets[sp] = np.array(Image.open(sp).convert("RGB"))
        sprite = cut_item(sheets[sp], it, a.density)
        pal_path = it.get("palette") or a.palette
        if pal_path:
            sprite = fi.lock_rgba(sprite, fi.load_palette(resolve(pal_path, base)))
        name = it.get("out", it["name"] + ".png")
        dest = os.path.join(a.out_dir, name)
        fi.save_rgba(sprite, dest)
        written.append({"name": it["name"], "file": dest, "size": [sprite.shape[1], sprite.shape[0]],
                        "sheet": sp, "box": it["box"], "mode": it.get("mode", "body")})
        print("  %-22s %3dx%-3d  %s  box %s" % (name, sprite.shape[1], sprite.shape[0], it.get("mode", "body"), it["box"]))
    if a.debug_dir:
        from PIL import ImageDraw
        os.makedirs(a.debug_dir, exist_ok=True)
        for sp, arr in sheets.items():
            img = Image.fromarray(arr)
            d = ImageDraw.Draw(img)
            for w in written:
                if w["sheet"] == sp:
                    d.rectangle(w["box"], outline=(255, 255, 0), width=4)
                    d.text((w["box"][0] + 6, w["box"][1] + 4), w["name"], fill=(255, 255, 0))
            k = min(1.0, 1600 / max(img.size))
            img = img.resize((int(img.width * k), int(img.height * k)), Image.Resampling.BOX)
            out = os.path.join(a.debug_dir, "boxes_" + os.path.splitext(os.path.basename(sp))[0] + ".png")
            img.save(out)
            print("debug:", out)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            json.dump({"boxes": a.boxes, "sprites": written}, fh, indent=2)
    print("cut %d item(s) into %s" % (len(written), a.out_dir))


if __name__ == "__main__":
    main()
