#!/usr/bin/env python3
"""Palette as code: named colour groups, reserved colours and sub-palettes
per asset class, written from one palettes.json.

    python palette_build.py init art/palettes.json          # a starter file to edit
    python palette_build.py build art/palettes.json         # -> .hex / .png / _preview.png
    python palette_build.py coverage --palette art/palette.hex raw_art/mood/mood_c.png --suggest 6

Why: nearest-colour quantising is only as good as the candidate set. A grey
cloud on dark slate snaps to green-greys or browns when they are offered;
cool grass shadows snap to blue-grey stone when land and water share a
palette; mid-greys snap to brown when the palette jumps from 8f918a to
2d2a2d. The fix is a master palette built from named groups, and
per-asset-class SUB-palettes (world, build, water, greys...) that leave out
what that class must never land on. Some colours are RESERVED (e.g. a red
that only the player's power may use); they stay in the master palette for
UI and code-drawn effects but are removed from every art sub-palette unless
that palette allows them.

palettes.json:

    {
      "out_dir": "art",
      "groups": {
        "ui":     ["f4f6f0", "2d251d", "6c5a4a"],
        "warm":   {"file": "art/warm_extracted.hex"},
        "flames": ["2d0400", "8c2519", "ea6b5d"],
        "water":  ["1f3634", "2b4744", "3a5c57"]
      },
      "reserved": ["flames"],
      "master": ["ui", "warm", "flames", "water"],
      "palettes": {
        "palette_world": ["warm", "f4f6f0"],
        "palette_water": {"groups": ["water"], "add": ["c3c7c0"]},
        "palette_enemy": {"groups": ["warm", "flames"], "allow_reserved": true}
      }
    }

Entries in a group list are hex colours; entries in "reserved", "master" and
a palette's list are group names or hex colours. Group files are read
relative to the JSON file's folder (then the current folder).

coverage: the share of a reference image's pixels farther than --threshold
RGB units from every palette colour (e.g. 20% of a mood frame at 28),
plus k-means clusters of the misses -- the colours worth adding.
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

EXAMPLE = {
    "out_dir": "art",
    "groups": {
        "ui": ["f4f6f0", "0e101a", "2d251d", "6c5a4a", "ab927c", "eacdb3"],
        "greens": ["1c3519", "2c5222", "3f702c", "5a9136", "7cb043", "a5cc5e"],
        "stone": ["2d2a2d", "5b5850", "8f918a", "c3c7c0"],
        "water": ["1f3634", "2b4744", "3a5c57", "4e7069", "6a8c82", "93b2a6"],
        "accent": ["8c2519", "ea6b5d"]
    },
    "reserved": ["accent"],
    "master": ["ui", "greens", "stone", "water", "accent"],
    "palettes": {
        "palette_world": ["ui", "greens", "stone"],
        "palette_water": {"groups": ["water"], "add": ["c3c7c0", "f4f6f0"]},
        "palette_greys": ["stone", "f4f6f0", "0e101a"],
        "palette_all": {"groups": ["ui", "greens", "stone", "water", "accent"], "allow_reserved": True}
    }
}


def _norm(c):
    return fi.rgb_to_hex(fi.hex_to_rgb(c))


def resolve_groups(data, base_dirs):
    groups = {}
    for name, g in data.get("groups", {}).items():
        if isinstance(g, dict) and "file" in g:
            g = g["file"]
        if isinstance(g, str):
            path = g
            for b in base_dirs:
                if os.path.exists(os.path.join(b, g)):
                    path = os.path.join(b, g)
                    break
            with open(path, encoding="utf-8") as fh:
                cols = [fi.rgb_to_hex(c) for c in fi.parse_palette_text(fh.read())]
        else:
            cols = [_norm(c) for c in g]
        groups[name] = list(dict.fromkeys(cols))
    return groups


def expand(entries, groups):
    out = []
    for e in entries:
        if e in groups:
            out += groups[e]
        else:
            out.append(_norm(e))
    return list(dict.fromkeys(out))


def write_set(out_dir, name, colours, labelled=None):
    """name.hex, name.png (1 px per colour), name_preview.png."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, name)
    with open(base + ".hex", "w", newline="\n", encoding="utf-8") as fh:
        fh.write("\n".join(colours) + "\n")
    strip = Image.new("RGB", (max(1, len(colours)), 1))
    strip.putdata([fi.hex_to_rgb(c) for c in colours])
    strip.save(base + ".png")
    preview(colours, base + "_preview.png", labelled)


def preview(colours, path, labelled=None):
    sw, pad, cols = 40, 6, 12
    rows_spec = labelled or [("", colours)]
    lines = []
    for label, cs in rows_spec:
        for i in range(0, max(1, len(cs)), cols):
            lines.append((label if i == 0 else "", cs[i:i + cols]))
    label_w = 90 if labelled else 0
    img = Image.new("RGB", (pad + label_w + cols * (sw + pad), pad + len(lines) * (sw + pad)), (20, 20, 20))
    d = ImageDraw.Draw(img)
    for r, (label, cs) in enumerate(lines):
        y = pad + r * (sw + pad)
        if label:
            d.text((pad, y + sw // 2 - 6), label[:14], fill=(220, 220, 220))
        for i, c in enumerate(cs):
            x = pad + label_w + i * (sw + pad)
            d.rectangle([x, y, x + sw - 1, y + sw - 1], fill=fi.hex_to_rgb(c))
    img.save(path)


def build(path, out_dir=None):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    base_dirs = [os.path.dirname(os.path.abspath(path)), os.getcwd()]
    groups = resolve_groups(data, base_dirs)
    reserved = set(expand(data.get("reserved", []), groups))
    master_names = data.get("master") or list(groups)
    master = expand(master_names, groups)
    out_dir = out_dir or data.get("out_dir", "art")
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(os.getcwd(), out_dir)
    labelled = [(n, groups[n]) for n in master_names if n in groups]
    loose = [c for c in master if not any(c in groups[n] for n in master_names if n in groups)]
    if loose:
        labelled.append(("extra", loose))
    write_set(out_dir, data.get("master_name", "palette"), master, labelled)
    print("%-18s %3d colours (master; %d reserved)" % (data.get("master_name", "palette") + ".hex",
                                                      len(master), len(reserved & set(master))))
    for name, spec in data.get("palettes", {}).items():
        if isinstance(spec, dict):
            cols = expand(spec.get("groups", []), groups) + expand(spec.get("add", []), groups)
            drop = set(expand(spec.get("drop", []), groups))
            allow = bool(spec.get("allow_reserved", False))
        else:
            cols, drop, allow = expand(spec, groups), set(), False
        cols = list(dict.fromkeys(c for c in cols if c not in drop and (allow or c not in reserved)))
        if not cols:
            raise SystemExit("sub-palette %s is empty (all reserved?)" % name)
        write_set(out_dir, name, cols)
        print("%-18s %3d colours%s" % (name + ".hex", len(cols), " (reserved allowed)" if allow else ""))
    print("written to", out_dir)


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------

def kmeans(x, k, iters=25, seed=1):
    rng = np.random.default_rng(seed)
    x = x.astype(np.float32)
    centres = [x[rng.integers(len(x))]]
    for _ in range(1, k):                               # k-means++ seeding
        d = np.min(((x[:, None, :] - np.array(centres)[None]) ** 2).sum(-1), axis=1)
        if d.sum() <= 0:
            break
        centres.append(x[rng.choice(len(x), p=d / d.sum())])
    c = np.array(centres)
    for _ in range(iters):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        new = np.array([x[lab == i].mean(0) if (lab == i).any() else c[i] for i in range(len(c))])
        if np.allclose(new, c, atol=0.5):
            break
        c = new
    lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
    return c, np.bincount(lab, minlength=len(c))


def nearest_dist(px, pal):
    pal = np.asarray(pal, np.float32)
    out = np.empty(len(px), np.float32)
    for i in range(0, len(px), 65536):
        b = px[i:i + 65536].astype(np.float32)
        out[i:i + 65536] = np.sqrt(((b[:, None, :] - pal[None]) ** 2).sum(-1).min(1))
    return out


def palette_from_any(path):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        groups = resolve_groups(data, [os.path.dirname(os.path.abspath(path)), os.getcwd()])
        return np.array([fi.hex_to_rgb(c) for c in expand(data.get("master") or list(groups), groups)], np.uint8)
    return fi.load_palette(path)


def coverage(palette_path, images, threshold=28.0, suggest=6, max_px=300000, miss_map=None):
    pal = palette_from_any(palette_path)
    px_all = []
    for p in images:
        a = np.array(Image.open(p).convert("RGBA"))
        px_all.append(a[a[..., 3] > 16][:, :3])
    px = np.concatenate(px_all)
    if not len(px):
        raise SystemExit("no opaque pixels in the reference image(s)")
    rng = np.random.default_rng(0)
    sample = px if len(px) <= max_px else px[rng.choice(len(px), max_px, replace=False)]
    d = nearest_dist(sample, pal)
    miss = d > threshold
    share = miss.mean() * 100
    print("palette %s: %d colours" % (palette_path, len(pal)))
    print("%.1f%% of reference pixels are more than %g RGB units from every palette colour"
          % (share, threshold))
    result = {"palette": palette_path, "colours": int(len(pal)), "threshold": threshold,
              "miss_percent": round(float(share), 2), "suggest": []}
    if suggest and miss.sum() >= suggest:
        m = sample[miss]
        if len(m) > 20000:
            m = m[rng.choice(len(m), 20000, replace=False)]
        centres, counts = kmeans(m, suggest)
        order = np.argsort(-counts)
        added = np.concatenate([pal.astype(np.float32), centres.astype(np.float32)])
        after = (nearest_dist(sample, added) > threshold).mean() * 100
        print("colours to add (cluster centres of the misses, biggest first):")
        for i in order:
            hx = fi.rgb_to_hex(np.clip(np.round(centres[i]), 0, 255))
            pct = counts[i] / max(1, counts.sum()) * share
            print("  %s   ~%.1f%% of the image" % (hx, pct))
            result["suggest"].append({"hex": hx, "percent": round(float(pct), 2)})
        print("with all %d added: %.1f%% would miss" % (len(centres), after))
        result["miss_after_percent"] = round(float(after), 2)
    if miss_map:
        a = np.array(Image.open(images[0]).convert("RGB"))
        dd = nearest_dist(a.reshape(-1, 3), pal).reshape(a.shape[:2])
        grey = (a.mean(-1, keepdims=True) * 0.35 + 40).repeat(3, -1)
        out = np.where((dd > threshold)[..., None], a, grey).astype(np.uint8)
        Image.fromarray(out).save(miss_map)
        print("miss map (misses in colour, the rest greyed):", miss_map)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write every palette from palettes.json")
    b.add_argument("json", help="palettes.json")
    b.add_argument("--out-dir", default=None, help="override the file's out_dir")
    i = sub.add_parser("init", help="write a starter palettes.json")
    i.add_argument("json", nargs="?", default="art/palettes.json")
    i.add_argument("--force", action="store_true")
    c = sub.add_parser("coverage", help="how much of a reference image the palette can reach")
    c.add_argument("images", nargs="+", help="reference image(s), e.g. the chosen mood frame")
    c.add_argument("--palette", required=True, help=".hex/.png palette or palettes.json (its master)")
    c.add_argument("--threshold", type=float, default=28.0, help="RGB distance that counts as a miss (default 28)")
    c.add_argument("--suggest", type=int, default=6, help="how many colours to suggest (0 = none)")
    c.add_argument("--miss-map", default=None, help="write an image showing the missed pixels")
    c.add_argument("--json", action="store_true", help="also print the result as JSON")
    a = ap.parse_args()
    if a.cmd == "init":
        if os.path.exists(a.json) and not a.force:
            raise SystemExit("%s exists (use --force)" % a.json)
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(EXAMPLE, fh, indent=2)
            fh.write("\n")
        print("wrote", a.json, "- edit the groups, then: palette_build.py build", a.json)
    elif a.cmd == "build":
        build(a.json, a.out_dir)
    else:
        r = coverage(a.palette, a.images, a.threshold, a.suggest, miss_map=a.miss_map)
        if a.json:
            print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
